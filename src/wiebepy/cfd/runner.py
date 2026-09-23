# -*- coding: utf-8 -*-
"""
runner.py — Preparação, execução, cancelamento e estado do caso CFD.

Responsabilidades (§12, §15):
  • prepare  : gera o caso (case_builder) e marca PREPARED;
  • validate : delega a validation.validate_case;
  • run      : executa via adapter, com lock no diretório (proteção
               contra duas execuções simultâneas), captura de saída em
               logs/, atualização de estado e verificação de término —
               "processo terminou" só vira COMPLETED se os resultados
               cobrem a janela simulada (results.check_completion);
  • cancel   : interrompe a execução (árvore de processos + filhos/MPI)
               e marca CANCELLED preservando logs e resultados parciais.

Uma falha do solver NUNCA derruba o restante do wiebepy e nunca cai
silenciosamente no 0-D.
"""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from .adapters.base import AdapterError, get_adapter
from .case_builder import CaseBuilder
from .config import CfdConfig, CaseState, read_state, write_state
from .results import check_completion
from .validation import validate_case

LOCK_NAME = ".run.lock"
CancelCheck = Optional[Callable[[], bool]]
OutputCb = Optional[Callable[[str], None]]


class RunnerError(RuntimeError):
    """Erro de operação do runner (estado, lock etc.)."""


class RunLock:
    """Lock exclusivo de execução por diretório de caso (§15)."""

    def __init__(self, case_dir: Path):
        self.path = Path(case_dir) / LOCK_NAME

    def acquire(self) -> None:
        if self.path.exists():
            info = {}
            try:
                info = json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
            raise RunnerError(
                "Já existe uma execução (possível) neste caso "
                f"(lock de {info.get('started', '?')}, pid "
                f"{info.get('pid', '?')}). Se tiver certeza de que não há "
                "execução ativa, remova o arquivo "
                f"{self.path.name} e tente novamente.")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"pid": os.getpid(),
                                         "started": time.strftime(
                                             "%Y-%m-%d %H:%M:%S")}),
                             encoding="utf-8")

    def release(self) -> None:
        try:
            self.path.unlink()
        except OSError:
            pass

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *exc):
        self.release()
        return False


class CfdRunner:
    """Orquestra prepare/validate/run/cancel de um caso."""

    def __init__(self, cfg: CfdConfig, engine, distro: Optional[str] = None,
                 solver_info: Optional[Dict] = None):
        self.cfg = cfg
        self.engine = engine          # pressure.engine.EngineConfig (§8: a
                                      # mesma geometria dos modos 0-D)
        self.distro = distro
        self.solver_info = solver_info

    # -------------------------------------------------------------- prepare
    def prepare(self, case_dir=None, heat_enabled: bool = True,
                moving_override: Optional[bool] = None) -> Path:
        """Gera o caso OpenFOAM e marca PREPARED (modo de inspeção sem
        execução — §13)."""
        d = Path(case_dir or self.cfg.case_directory)
        b = CaseBuilder(self.cfg, self.engine, self._solver_info(),
                        heat_enabled=heat_enabled,
                        moving_override=moving_override)
        b.build(d)
        write_state(d, CaseState.PREPARED)
        return d

    def _solver_info(self) -> Dict:
        if self.solver_info is not None:
            return self.solver_info
        from .capabilities import doctor
        d = doctor().best() or {}
        return {"distro": d.get("distro"), "version": d.get("version"),
                "root": d.get("root"), "foamRun": d.get("foamRun"),
                "mpirun": d.get("mpirun"), "gcc": d.get("gcc")}

    # ------------------------------------------------------------- validate
    def validate(self, case_dir) -> Tuple[bool, List[str], List[str]]:
        return validate_case(case_dir, self.cfg.adapter, self.distro)

    # ------------------------------------------------------------------ run
    def run(self, case_dir=None, workers: Optional[int] = None,
            cancel: CancelCheck = None,
            on_output: OutputCb = None) -> Dict:
        """Executa o caso (requer estado VALIDATED). Retorna resumo."""
        d = Path(case_dir or self.cfg.case_directory)
        state = read_state(d)
        if state == CaseState.RUNNING:
            if not (d / LOCK_NAME).exists():
                # execução anterior morreu sem atualizar o estado (ex.:
                # processo do wiebepy interrompido) — recupera e segue
                write_state(d, CaseState.FAILED,
                            error="Execução anterior interrompida sem "
                                  "atualizar o estado (lock ausente); "
                                  "estado recuperado.")
            else:
                raise RunnerError("Caso já está em execução.")
        ok, erros, _ = validate_case(d, self.cfg.adapter, self.distro,
                                     set_validated=False)
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
            ad = get_adapter(self.cfg.adapter, distro=self.distro,
                             installation=self._install(d))
            w = int(workers or self.cfg.workers or 1)
            res = ad.run_case(d, workers=w, on_output=on_output,
                              cancel=cancel)
            if res["status"] == "completed":
                completo, msg = check_completion(d, self.cfg)
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

    def _install(self, case_dir: Path) -> Optional[Dict]:
        """Recupera a instalação registrada no caso (reprodutibilidade)."""
        import yaml
        yml = Path(case_dir) / "case_config.yaml"
        if yml.exists():
            try:
                cfg = yaml.safe_load(yml.read_text(encoding="utf-8")) or {}
                sol = cfg.get("solver") or {}
                if sol.get("root"):
                    return {"root": sol.get("root"),
                            "version": sol.get("version"),
                            "foamRun": sol.get("foamRun"),
                            "mpirun": sol.get("mpirun"),
                            "gcc": sol.get("gcc"),
                            "distro": sol.get("distro")}
            except yaml.YAMLError:
                pass
        return None

    # --------------------------------------------------------------- cancel
    @staticmethod
    def cancel(case_dir) -> bool:
        """Sinaliza cancelamento da execução ativa do caso."""
        case_dir = Path(case_dir)
        state = read_state(case_dir)
        if state != CaseState.RUNNING:
            return False
        flag = case_dir / ".cancel.requested"
        flag.write_text(time.strftime("%Y-%m-%d %H:%M:%S"), encoding="utf-8")
        return True


def make_cancel_poller(case_dir: Path, event: Optional[threading.Event] = None):
    """CancelCheck combinado: evento em memória + flag em disco (permite
    cancelar de outra sessão da GUI/CLI)."""
    ev = event or threading.Event()

    def poll() -> bool:
        if ev.is_set():
            return True
        return (Path(case_dir) / ".cancel.requested").exists()
    return ev, poll


__all__ = ["CfdRunner", "RunLock", "RunnerError", "make_cancel_poller"]