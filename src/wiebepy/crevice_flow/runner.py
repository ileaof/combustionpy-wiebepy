# -*- coding: utf-8 -*-
"""
runner.py — Preparação, execução, cancelamento e estado do caso de fresta.

Reutiliza a infra-estrutura do ``wiebepy.cfd`` (sem alterá-la): o lock de
execução (``RunLock``), o enum de estados (``CaseState`` — "processo
terminou" ≠ "concluído") e o adapter OpenFOAM (``get_adapter``), que já
encerra a árvore de processos/MPI no cancelamento (§15).

A verificação de conclusão é específica deste módulo: além do 'End' no
log do foamRun, a série temporal de postProcessing tem que cobrir a
janela em TEMPO DO SOLVER (t = (θ−θ0)/(6·rpm)); uma execução que morreu
no meio NUNCA é marcada como completed.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from ..cfd.adapters.base import get_adapter
from ..cfd.config import CaseState, read_state, write_state
from ..cfd.runner import RunLock, RunnerError, make_cancel_poller
from .case import CreviceCaseBuilder
from .config import CreviceConfig, read_crevice_config
from .validation import validate_case

CancelCheck = Optional[Callable[[], bool]]
OutputCb = Optional[Callable[[str], None]]


def check_completion(case_dir, t_end_s: float) -> Tuple[bool, str]:
    """"processo terminou" ≠ "convergiu": exige 'End' no log e último
    tempo gravado ≥ fim da janela (tolerância de gravação = 2 %)."""
    case_dir = Path(case_dir)
    log = case_dir / "logs" / "foamRun.log"
    if not log.exists():
        return False, "Log do foamRun não encontrado (logs/foamRun.log)."
    texto = log.read_text(encoding="utf-8", errors="replace")
    if "End" not in texto:
        return False, ("O solver terminou sem a mensagem final 'End' — "
                       "execução provavelmente interrompida.")
    fim = float(t_end_s)
    tol = max(1e-12, 0.02 * abs(fim))
    ultimo = _last_time(case_dir)
    if ultimo is None:
        return False, "Sem série temporal em postProcessing (fluxoMassaCamara)."
    if ultimo < fim - tol:
        return False, (f"Último ponto registrado ({ultimo:.6g} s) não cobre "
                       f"o fim da janela ({fim:.6g} s).")
    return True, "Janela simulada coberta e solver encerrado com 'End'."


def _last_time(case_dir: Path) -> Optional[float]:
    """Último 'Time' da série do functionObject de fluxo (pasta
    postProcessing/fluxoMassaCamara/*.dat, colunas: Time + soma(phi))."""
    pp = case_dir / "postProcessing" / "fluxoMassaCamara"
    if not pp.is_dir():
        return None
    ultimo = None
    # subpastas por startTime (restart gera 0/, 0.013889/, ...);
    # concatena igual a results.py (_dat).
    for dat in sorted(pp.glob("*/*.dat")) or sorted(pp.glob("*.dat")):
        for linha in dat.read_text(encoding="utf-8",
                                   errors="replace").splitlines():
            linha = linha.strip()
            if not linha or linha.startswith("#"):
                continue
            try:
                ultimo = float(linha.split()[0])
            except (ValueError, IndexError):
                continue
    return ultimo


class CreviceRunner:
    """Orquestra prepare/validate/run/cancel de um caso de fresta."""

    def __init__(self, cfg: CreviceConfig, distro: Optional[str] = None,
                 solver_info: Optional[Dict] = None):
        self.cfg = cfg
        self.distro = distro
        self.solver_info = solver_info

    # -------------------------------------------------------------- prepare
    def prepare(self, case_dir=None) -> Path:
        """Gera o caso OpenFOAM e marca PREPARED (inspeção sem execução).
        NUNCA sobrescreve um caso já executado: se existir estado
        COMPLETED/RUNNING no diretório, exige diretório novo."""
        d = Path(case_dir or self.cfg.case_directory)
        estado = read_state(d)
        if estado in (CaseState.RUNNING, CaseState.COMPLETED):
            raise RunnerError(
                f"O diretório {d} já tem um caso {estado.label.lower()} — "
                "use outro case_directory para não sobrescrever "
                "resultados anteriores.")
        info = self.solver_info or _solver_info_fallback(self.distro)
        b = CreviceCaseBuilder(self.cfg, solver_info=info)
        b.build(d)
        write_state(d, CaseState.PREPARED,
                    modulo="wiebepy.crevice_flow",
                    descricao="submodelo de fresta top-land (não é "
                              "blow-by)")
        return d

    # ------------------------------------------------------------- validate
    def validate(self, case_dir=None) -> Tuple[bool, List[str], List[str]]:
        d = Path(case_dir or self.cfg.case_directory)
        return validate_case(d)

    # ------------------------------------------------------------------ run
    def run(self, case_dir=None, workers: int = 1,
            cancel: CancelCheck = None,
            on_output: OutputCb = None) -> Dict:
        """Executa o caso (requer estado VALIDATED). Retorna o resumo do
        adapter; marca COMPLETED só se a janela foi coberta."""
        d = Path(case_dir or self.cfg.case_directory)
        state = read_state(d)
        if state == CaseState.RUNNING:
            if (d / ".run.lock").exists():
                raise RunnerError("Caso já está em execução.")
            write_state(d, CaseState.FAILED,
                        error="Execução anterior interrompida sem "
                              "atualizar o estado (lock ausente); estado "
                              "recuperado.")
        ok, erros, _ = validate_case(d, set_validated=False)
        if not ok:
            raise RunnerError("Caso inválido: " + "; ".join(erros))
        write_state(d, CaseState.RUNNING)
        lock = RunLock(d)
        try:
            lock.acquire()
        except RunnerError as e:
            write_state(d, CaseState.FAILED, error=str(e))
            raise
        try:
            ad = get_adapter("openfoam", distro=self.distro,
                             installation=_install(d))
            res = ad.run_case(d, workers=int(workers or 1),
                              on_output=on_output, cancel=cancel)
            if res["status"] == "completed":
                completo, msg = check_completion(d, _t_end(d))
                if completo:
                    write_state(d, CaseState.COMPLETED, summary=res)
                else:
                    res2 = dict(res)
                    res2["note"] = msg
                    write_state(d, CaseState.FAILED, error=msg,
                                summary=res2)
                    res = res2
            elif res["status"] == "cancelled":
                write_state(d, CaseState.CANCELLED, summary=res)
            else:
                write_state(d, CaseState.FAILED, error="Solver falhou",
                            summary=res)
            return res
        finally:
            lock.release()

    # --------------------------------------------------------------- cancel
    @staticmethod
    def cancel(case_dir=None) -> bool:
        """Sinaliza cancelamento da execução ativa (flag em disco lida
        pelo poller do adapter — mesmo mecanismo do cfd)."""
        case_dir = Path(case_dir or ".")
        state = read_state(case_dir)
        if state != CaseState.RUNNING:
            return False
        flag = case_dir / ".cancel.requested"
        import time
        flag.write_text(time.strftime("%Y-%m-%d %H:%M:%S"),
                        encoding="utf-8")
        return True


def _install(case_dir: Path) -> Optional[Dict]:
    """Instalação OpenFOAM registrada no caso (reprodutibilidade)."""
    import yaml
    yml = Path(case_dir) / "case_config.yaml"
    if yml.exists():
        try:
            cfg = yaml.safe_load(yml.read_text(encoding="utf-8")) or {}
            info = cfg.get("solver_info") or {}
            if info.get("root"):
                return {"root": info.get("root"),
                        "version": info.get("version"),
                        "foamRun": info.get("foamRun"),
                        "mpirun": info.get("mpirun"),
                        "gcc": info.get("gcc"),
                        "distro": info.get("distro")}
        except yaml.YAMLError:
            pass
    return None


def _t_end(case_dir: Path) -> float:
    """Tempo final do caso (endTime do controlDict)."""
    texto = (Path(case_dir) / "system" / "controlDict").read_text(
        encoding="utf-8", errors="replace")
    for linha in texto.splitlines():
        if linha.strip().startswith("endTime"):
            return float(linha.split()[1].rstrip(";"))
    raise RunnerError("endTime ausente no system/controlDict do caso.")


def _solver_info_fallback(distro: Optional[str]) -> Dict:
    """Consulta o doctor do wiebepy.cfd quando a GUI/CLI não passa
    solver_info (mesma origem dos casos de câmara)."""
    try:
        from ..cfd.capabilities import doctor
        d = doctor().best() or {}
        return {"distro": d.get("distro"), "version": d.get("version"),
                "root": d.get("root"), "foamRun": d.get("foamRun"),
                "mpirun": d.get("mpirun"), "gcc": d.get("gcc")}
    except Exception:                                   # noqa: BLE001
        # sem WSL/solver o caso ainda pode ser gerado e inspecionado;
        # a proveniência fica marcada como não resolvida
        return {"distro": distro, "version": None, "root": None,
                "foamRun": None, "mpirun": None, "gcc": None}


def load_config(path) -> CreviceConfig:
    """Lê + valida a config YAML (chamado único da CLI/GUI)."""
    cfg = read_crevice_config(path)
    avisos = cfg.validate()
    return cfg


__all__ = ["CreviceRunner", "RunnerError", "RunLock", "check_completion",
           "make_cancel_poller", "load_config"]