# -*- coding: utf-8 -*-
"""
wsl.py — Utilitários de execução no WSL2 (Windows) e local (Linux).

O adapter OpenFOAM executa o solver no WSL2 quando o wiebepy roda no
Windows. Nada aqui é executado no import — apenas quando o usuário
prepara/executa um caso CFD ou pede o diagnóstico (``wiebepy cfd
doctor``). Sem WSL2 ou solver instalado, o restante do wiebepy continua
100 % funcional.

TRANSPORTE DE SCRIPT: o wsl.exe do Windows destrói a citação dos
argumentos (``bash -lc 'x=$d; echo $x'`` chega quebrado ao bash do WSL).
Por isso todo comando é enviado como SCRIPT via stdin de ``bash -l``
(``wsl -d D [--cd DIR] -- bash -l``), o que preserva variáveis, globs,
aspas e pipes.
"""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

WSL_EXE = "wsl.exe"
RUN_TIMEOUT_PROBE = 60  # sondas rápidas (diagnóstico)


class WslError(RuntimeError):
    """Falha ao executar um comando no WSL."""


def on_windows() -> bool:
    import sys
    return sys.platform.startswith("win")


def wsl_available() -> bool:
    return on_windows() and shutil.which(WSL_EXE) is not None


def run_wsl(distro: Optional[str], script: str, timeout: int = 600,
            cwd_win: Optional[Path] = None,
            stdin_data: Optional[bytes] = None) -> "tuple[int, str, str]":
    """Executa ``script`` (bash) na distribuição WSL indicada (via stdin).

    Retorna (código, stdout, stderr). Falhas de invocação (wsl ausente,
    distro inexistente) levantam WslError; o código do script é
    retornado ao chamador.
    """
    if not wsl_available():
        raise WslError("WSL2 não disponível nesta máquina (wsl.exe não "
                       "encontrado). Instale o solver no WSL2 ou no Linux "
                       "nativo — ver docs/cfd/install.md.")
    cmd = [WSL_EXE]
    if distro:
        cmd += ["-d", distro]
    if cwd_win is not None:
        cmd += ["--cd", str(cwd_win)]
    cmd += ["--", "bash", "-l"]
    try:
        p = subprocess.run(cmd, input=script.encode("utf-8"),
                           capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        raise WslError(f"Tempo esgotado ({timeout} s) executando no WSL: "
                       f"{script[:120]}") from e
    except OSError as e:
        raise WslError(f"Falha ao invocar wsl.exe: {e}") from e
    out = p.stdout.decode("utf-8", errors="replace")
    err = p.stderr.decode("utf-8", errors="replace")
    return p.returncode, out, err


def list_distros() -> List[str]:
    """Distribuições WSL registradas (nome padrão incluído)."""
    if not wsl_available():
        return []
    p = subprocess.run([WSL_EXE, "-l", "-q"], capture_output=True)
    if p.returncode != 0:
        return []
    s = p.stdout
    if s.startswith(b"\xff\xfe") or s.startswith(b"\xfe\xff"):
        texto = s.decode("utf-16", errors="replace")
    else:
        try:
            texto = s.decode("utf-16")
        except UnicodeDecodeError:
            texto = s.decode("utf-8", errors="replace")
    nomes = [n.strip() for n in texto.splitlines() if n.strip()]
    # docker-desktop* e afins não são ambientes úteis para o solver
    return [n for n in nomes
            if not n.lower().startswith(("docker-desktop", "docker"))]


def wsl_path(distro: str, win_path: Path) -> str:
    """Converte um caminho Windows em caminho dentro do WSL (wslpath)."""
    code, out, err = run_wsl(distro, f"wslpath -a '{win_path}'",
                             timeout=RUN_TIMEOUT_PROBE)
    if code != 0:
        raise WslError(f"wslpath falhou para {win_path}: {err.strip()}")
    return out.strip().replace("\\", "/")


def detect_openfoam(distro: Optional[str]) -> List[Dict]:
    """Procura instalações OpenFOAM (/opt/openfoam*) na distribuição.

    Retorna lista de dicts {root, version, foamRun, gcc, mpirun, distro}
    — vazia se nenhuma instalação for encontrada. Sem download e sem
    detecção pesada: apenas ls/source/which.
    """
    script = r"""
for d in /opt/openfoam* /usr/lib/openfoam*; do
  [ -d "$d" ] || continue
  source "$d/etc/bashrc" 2>/dev/null || continue
  echo "OF|$d|$WM_PROJECT_VERSION|$(command -v foamRun)|$(command -v gcc)|$(command -v mpirun)"
done
"""
    code, out, err = run_wsl(distro, script, timeout=RUN_TIMEOUT_PROBE)
    res = []
    if code == 0:
        for line in out.splitlines():
            if line.startswith("OF|"):
                _, root, ver, fr, gcc, mpi = line.split("|", 5)
                res.append({"root": root.strip(), "version": ver.strip(),
                            "foamRun": fr.strip(),
                            "gcc": gcc.strip(), "mpirun": mpi.strip(),
                            "distro": distro})
    return res