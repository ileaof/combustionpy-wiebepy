# -*- coding: utf-8 -*-
"""
adapters.openfoam — Adapter para o OpenFOAM Foundation 13.

DECISÃO DE SOLVER (registrada em docs/cfd/architecture.md):
  • Distribuição: OpenFOAM Foundation (openfoam.org), versão 13
    (testado com a instalação /opt/openfoam13, WSL2 Ubuntu-22.04, build
    linux64GccDPInt32Opt).
  • Solver transiente compressível: ``foamRun`` com ``solver fluid``.
  • Movimento do pistão: fvMeshMovers ``multiValveEngine`` (somente
    pistão) com Function1 ``crankConnectingRodMotion``; o tempo do
    usuário é o ângulo de manivela (userTime type engine, omega em rpm).
  • Fonte de calor: fvModel nativo ``heatSource`` (cellZone + q Function1
    tipo table) com a densidade prescrita diretamente,
    q'''(CA) = Q̇(CA)/V₀(CA) [W/m³] — conservativo sobre os volumes
    atuais da malha, com malha móvel e em paralelo. (O modo Q — potência
    total — congela 1/V(zone) na construção no OF13 e não é conservativo
    com malha móvel; ver case_builder.)
  • Paralelismo: decomposePar + mpirun -np N foamRun -parallel +
    reconstructPar (paralelismo do SOLVER, distinto dos backends do
    wiebepy).

No Windows, a execução é via WSL2 (wsl.exe); no Linux, direto. A GUI e a
CLI funcionam no Windows mesmo sem WSL2/solver — só a execução CFD exige
o ambiente (ver capabilities.doctor).
"""
from __future__ import annotations

import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional

from ..wsl import WslError, detect_openfoam, list_distros, on_windows, \
    wsl_available
from .base import AdapterError, CfdAdapter, CancelCheck, OutputCb

CANCELLED, FAILED, COMPLETED = "cancelled", "failed", "completed"


class OpenFoamAdapter(CfdAdapter):
    """Adapter OpenFOAM 13 (Foundation) — WSL2 no Windows, nativo no Linux."""

    name = "openfoam"

    def __init__(self, distro: Optional[str] = None,
                 installation: Optional[Dict] = None):
        self._distro = distro
        self._install = installation
        if self._install is not None and not self._distro:
            # a instalação registrada no caso prevalece (reprodutibilidade)
            self._distro = self._install.get("distro")
        self._cancel_lock = threading.Lock()
        self._cancel_requested = False
        self._proc: Optional[subprocess.Popen] = None

    # ------------------------------------------------------------- ambiente
    def _resolve_install(self) -> Optional[Dict]:
        if self._install is not None:
            return self._install
        distros = ([self._distro] if self._distro
                   else (list_distros() if on_windows() else [None]))
        for d in distros:
            insts = detect_openfoam(d)
            if insts:
                self._distro = d
                self._install = insts[0]
                return self._install
        return None

    def diagnose(self) -> Dict:
        try:
            inst = self._resolve_install()
        except WslError as e:
            return {"adapter": self.name, "ok": False, "error": str(e)}
        if inst is None:
            return {"adapter": self.name, "ok": False,
                    "error": "OpenFOAM não encontrado (ver "
                             "docs/cfd/install.md)."}
        return {"adapter": self.name, "ok": bool(inst["foamRun"]),
                "distro": inst.get("distro"),
                "version": inst.get("version"),
                "root": inst.get("root"),
                "foamRun": inst.get("foamRun"),
                "mpirun": inst.get("mpirun")}

    def check_runnable(self) -> List[str]:
        d = self.diagnose()
        if not d.get("ok"):
            return [d.get("error", "Ambiente do solver indisponível.")]
        errs = []
        if on_windows() and not d.get("distro"):
            errs.append("Distribuição WSL2 não identificada.")
        if not d.get("foamRun"):
            errs.append("foamRun não encontrado no OpenFOAM detectado.")
        return errs

    # -------------------------------------------------------------- execução
    def _bash_cmd(self, cmd: str) -> str:
        """Envolve um comando no ambiente do OpenFOAM (script bash)."""
        root = self._install["root"]
        return (f"source {root}/etc/bashrc >/dev/null 2>&1\n"
                f"{cmd}\n")

    def _spawn(self, cmd: str, case_dir: Path, log_path: Path,
               on_output: OutputCb = None) -> subprocess.Popen:
        """Inicia um passo do solver, capturando a saída para o log.

        ``cmd`` é um script bash enviado via stdin (o wsl.exe destrói a
        citação de argumentos); no Linux usa-se bash -l com stdin igual.
        """
        log_path.parent.mkdir(parents=True, exist_ok=True)
        logf = open(log_path, "wb")
        flags = 0
        if os.name == "nt":
            flags = subprocess.CREATE_NEW_PROCESS_GROUP
        argv = self._argv(case_dir)
        p = subprocess.Popen(argv, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, stdin=subprocess.PIPE,
                             creationflags=flags)
        self._proc = p
        try:
            p.stdin.write(cmd.encode("utf-8"))
            p.stdin.close()
        except OSError:
            pass

        def _drain():
            for line in iter(p.stdout.readline, b""):
                logf.write(line)
                logf.flush()
                if on_output:
                    on_output(line.decode("utf-8", errors="replace").rstrip())
            logf.close()
        threading.Thread(target=_drain, daemon=True).start()
        return p

    def _argv(self, case_dir: Path) -> List[str]:
        if on_windows():
            argv = ["wsl.exe"]
            if self._distro:
                argv += ["-d", self._distro]
            argv += ["--cd", str(case_dir), "--", "bash", "-l"]
        else:
            argv = ["bash", "-l"]
        return argv

    def _cancel_tree(self, case_wsl: str) -> None:
        """Cancela: mata a árvore local (wsl.exe/bash) e os processos do
        solver dentro do WSL (foamRun/mpirun deste caso)."""
        with self._cancel_lock:
            self._cancel_requested = True
            p = self._proc
            if p is not None and p.poll() is None:
                try:
                    if os.name == "nt":
                        subprocess.run(["taskkill", "/T", "/F", "/PID",
                                        str(p.pid)], capture_output=True)
                    else:
                        p.terminate()
                except OSError:
                    pass
            # encerra também os filhos dentro do WSL (MPI etc.)
            try:
                if on_windows():
                    subprocess.run(
                        ["wsl.exe"] + (["-d", self._distro] if self._distro
                                       else []) +
                        ["--", "bash", "-l"],
                        input=b"pkill -f foamRun 2>/dev/null; "
                              b"pkill -f mpirun 2>/dev/null; true\n",
                        capture_output=True, timeout=30)
                else:
                    subprocess.run(["pkill", "-f", "foamRun"],
                                   capture_output=True, timeout=30)
            except (OSError, subprocess.TimeoutExpired):
                pass

    def run_case(self, case_dir: Path, workers: int = 1,
                 on_output: OutputCb = None,
                 cancel: CancelCheck = None) -> Dict:
        """Executa: blockMesh [→ topoSet] [→ decomposePar] → foamRun
        [→ reconstructPar]. Cancelamento encerra filhos/MPI (§15)."""
        errs = self.check_runnable()
        if errs:
            raise AdapterError("; ".join(errs))
        case_dir = Path(case_dir).resolve()
        logs = case_dir / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        etapas: List[Dict] = []
        status = COMPLETED
        t0 = time.perf_counter()
        self._cancel_requested = False
        try:
            passos = [("blockMesh", "blockMesh 2>&1")]
            # cellZone por topoSet (distribution=region) — dict gerado
            # apenas quando presente
            if (case_dir / "system" / "topoSetDict").exists():
                passos.append(("topoSet", "topoSet 2>&1"))
            if workers > 1:
                passos.append(("decomposePar", "decomposePar -force 2>&1"))
            if workers > 1:
                run_cmd = (f"mpirun --allow-run-as-root -np {workers} "
                           f"foamRun -parallel 2>&1")
            else:
                run_cmd = "foamRun 2>&1"
            passos.append(("foamRun", run_cmd))
            if workers > 1:
                # serial: os campos já são completos; paralelo: recompõe
                passos.append(("reconstructPar",
                               "reconstructPar -latestTime 2>&1"))

            for nome, cmd in passos:
                if cancel is not None and cancel():
                    status = CANCELLED
                    break
                if status == CANCELLED:
                    break
                t1 = time.perf_counter()
                out = self._run_step(nome, cmd, case_dir, logs, on_output,
                                     cancel)
                etapas.append({"step": nome, "returncode": out,
                               "elapsed_s": round(time.perf_counter() - t1, 1),
                               "log": f"logs/{nome}.log"})
                if out != 0:
                    status = CANCELLED if (
                        cancel is not None and cancel()) else FAILED
                    break
        finally:
            self._proc = None
        return {"status": status, "steps": etapas,
                "elapsed_s": round(time.perf_counter() - t0, 1),
                "adapter": self.name, "version": self._install["version"],
                "workers": workers}

    def _run_step(self, nome: str, cmd: str, case_dir: Path,
                  logs: Path, on_output: OutputCb,
                  cancel: CancelCheck) -> int:
        p = self._spawn(self._bash_cmd(cmd), case_dir, logs / f"{nome}.log",
                        on_output)
        while p.poll() is None:
            if cancel is not None and cancel():
                self._cancel_tree(self._wsl_case_path(case_dir))
                time.sleep(1.0)
                if p.poll() is None:
                    p.kill()
                return 130
            time.sleep(0.5)
        return p.returncode or 0

    def _wsl_case_path(self, case_dir: Path) -> str:
        from ..wsl import run_wsl
        code, out, _ = run_wsl(self._distro, f"wslpath -a '{case_dir}'",
                               timeout=30)
        return out.strip() if code == 0 else str(case_dir)


__all__ = ["OpenFoamAdapter", "AdapterError"]