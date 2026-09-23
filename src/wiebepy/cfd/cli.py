# -*- coding: utf-8 -*-
"""
cli.py — Subcomando CFD: ``wiebepy cfd <subcomando> …``.

Integrado ao parser existente sem alterar as opções atuais: o parser
principal detecta o primeiro argumento ``cfd`` e delega para cá
(parser.py). Comandos:

    wiebepy cfd doctor                 diagnóstico do ambiente
    wiebepy cfd prepare  --config caso.yaml [--no-heat] [--fixed-piston]
                                       [--output DIR]
    wiebepy cfd validate --case DIR [--distro NOME]
    wiebepy cfd run      --case DIR [--workers N] [--config ARQ]
                                       [--distro NOME] [--follow]
    wiebepy cfd status   --case DIR
    wiebepy cfd cancel   --case DIR
    wiebepy cfd report   --case DIR

``prepare`` é o modo de preparação sem execução: gera o caso para
inspeção dos arquivos. ``run`` exige estado VALIDATED e verifica, ao
final, se a janela foi coberta ('processo terminou' ≠ 'convergiu').
Códigos de saída: 0 ok | 2 erro de uso/configuração | 1 erro inesperado.
"""
from __future__ import annotations

import argparse
import logging
import signal
from pathlib import Path
from typing import List, Optional

from ..io.config import ConfigError, resolve
from ..pressure.engine import EngineConfig
from .adapters.base import AdapterError
from .config import CfdConfig, CfdConfigError, CaseState, cfd_config_from_cfg
from .runner import CfdRunner, RunnerError, make_cancel_poller
from .validation import case_summary, validate_case

log = logging.getLogger("wiebepy")
EXIT_OK, EXIT_ERR, EXIT_USO = 0, 1, 2


def build_cfd_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="wiebepy cfd",
        description="Módulo CFD opcional do wiebepy (OpenFOAM 13 via WSL2). "
                    "O CFD é sempre opcional: com cfd.enabled=false o "
                    "restante do programa funciona sem este subcomando. "
                    "Liberação de calor PRESCRITA pela Wiebe calibrada "
                    "(modo prescribed_wiebe): NÃO prevê cinética química, "
                    "frente de chama ou emissões; a comparação com ensaio "
                    "é diagnóstica, nunca validação. Ver README (seção CFD) "
                    "e docs/cfd/.")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("doctor", help="diagnóstico do ambiente (WSL2, "
                                      "OpenFOAM)")
    s.add_argument("--distro", help="distribuição WSL2 específica")

    s = sub.add_parser("prepare", help="gera o caso para inspeção (sem "
                                       "executar)")
    s.add_argument("--config", required=True, metavar="ARQ",
                   help="configuração YAML/JSON do caso (engine + cfd)")
    s.add_argument("--output", metavar="DIR",
                   help="sobrescreve cfd.case_directory")
    s.add_argument("--no-heat", action="store_true",
                   help="gera o caso sem fonte de calor (compressão motrada; "
                        "usa max_Co 0,25)")
    s.add_argument("--fixed-piston", action="store_true",
                   help="gera com pistão fixo (volume constante)")

    s = sub.add_parser("validate", help="valida o caso antes da execução")
    s.add_argument("--case", required=True, metavar="DIR",
                   help="diretório do caso (com case_config.yaml)")
    s.add_argument("--distro", metavar="NOME",
                   help="distribuição WSL2 com o solver")

    s = sub.add_parser("run", help="executa o caso validado")
    s.add_argument("--case", required=True, metavar="DIR",
                   help="diretório do caso (estado VALIDATED)")
    s.add_argument("--config", metavar="ARQ",
                   help="configuração (workers/distro; o caso prevalece "
                        "para a física)")
    s.add_argument("--workers", type=int, metavar="N",
                   help="processos MPI do SOLVER (padrão: configuração)")
    s.add_argument("--distro", metavar="NOME")
    s.add_argument("--follow", action="store_true",
                   help="mostra a saída do solver no terminal")

    s = sub.add_parser("status", help="estado do caso")
    s.add_argument("--case", required=True, metavar="DIR")

    s = sub.add_parser("cancel", help="cancela a execução ativa")
    s.add_argument("--case", required=True, metavar="DIR")

    s = sub.add_parser("report", help="gera o relatório HTML do caso")
    s.add_argument("--case", required=True, metavar="DIR")
    return p


# ----------------------------------------------------------------- helpers
def _cfg_from_file(path: Optional[str]):
    cfg = resolve(path, {})
    return cfg, cfd_config_from_cfg(cfg)


def _engine_from_case(case_dir: Path) -> EngineConfig:
    import yaml
    yml = Path(case_dir) / "case_config.yaml"
    if not yml.exists():
        raise CfdConfigError(f"Caso sem case_config.yaml: {case_dir}")
    info = yaml.safe_load(yml.read_text(encoding="utf-8")) or {}
    return EngineConfig.from_dict(info.get("engine") or {})


def _engine_from_cfg(cfg: dict) -> EngineConfig:
    return EngineConfig.from_dict(cfg.get("engine") or {})


def _solver_install(distro: Optional[str]):
    from .capabilities import doctor
    rep = doctor()
    for dd in rep.distros:
        if distro is not None and dd["name"] != distro:
            continue
        if dd["openfoam"]:
            return dd["openfoam"][0], dd["name"]
    return None, distro


# ----------------------------------------------------------------- comandos
def _cmd_doctor(a) -> int:
    from .capabilities import doctor
    rep = doctor()
    print(rep.format())
    if a.distro and not any(d["name"] == a.distro for d in rep.distros):
        print(f"AVISO: distribuição '{a.distro}' não listada.")
    return EXIT_OK


def _cmd_prepare(a) -> int:
    cfg_full, cfg = _cfg_from_file(a.config)
    erros = cfg.validate()
    if erros:
        for e in erros:
            log.error("ERRO: %s", e)
        return EXIT_USO
    if a.output:
        cfg.case_directory = a.output
    inst, distro = _solver_install(cfg.wsl_distro)
    runner = CfdRunner(cfg, engine=_engine_from_cfg(cfg_full),
                       distro=distro,
                       solver_info=inst or {"version": None})
    d = runner.prepare(heat_enabled=not a.no_heat,
                       moving_override=False if a.fixed_piston else None)
    log.info("Caso preparado em %s (estado: %s).", d,
             CaseState.PREPARED.label)
    log.info("Inspecione os arquivos; então: wiebepy cfd validate --case "
             "\"%s\"", d)
    return EXIT_OK


def _cmd_validate(a) -> int:
    ok, erros, avisos = validate_case(a.case, distro=a.distro)
    for w in avisos:
        log.warning("WARNING: %s", w)
    if ok:
        log.info("Caso válido: %s", a.case)
        return EXIT_OK
    for e in erros:
        log.error("ERRO: %s", e)
    return EXIT_USO


def _cmd_run(a) -> int:
    if a.config:
        cfg_full, cfg = _cfg_from_file(a.config)
    else:
        cfg_full, cfg = {}, CfdConfig()
    distro = a.distro or cfg.wsl_distro
    engine = _engine_from_case(a.case)
    runner = CfdRunner(cfg, engine=engine, distro=distro)
    ok, erros, _ = validate_case(a.case, cfg.adapter, distro,
                                 set_validated=False)
    if not ok:
        for e in erros:
            log.error("ERRO: %s", e)
        return EXIT_USO
    log.info("Executando caso %s (workers=%s, distro=%s)…", a.case,
             a.workers or cfg.workers or 1, distro or "auto")
    ev, poll = make_cancel_poller(a.case)
    import threading

    def _segv(*_):
        ev.set()
    try:
        prev = signal.signal(signal.SIGINT, _segv)
    except ValueError:
        prev = None
    try:
        res = runner.run(a.case, workers=a.workers, cancel=poll,
                         on_output=(lambda linha: print(linha))
                         if a.follow else None)
    except (RunnerError, AdapterError) as e:
        log.error("ERRO: %s", e)
        return EXIT_USO
    finally:
        if prev is not None:
            signal.signal(signal.SIGINT, prev)
    log.info("Status: %s (%.1f s)", res["status"], res["elapsed_s"])
    for s in res.get("steps", []):
        log.info("  %s: rc=%s (%s s) — %s", s["step"], s["returncode"],
                 s["elapsed_s"], s["log"])
    if res["status"] == "completed":
        log.info("Concluído — relatório: wiebepy cfd report --case \"%s\"",
                 a.case)
        return EXIT_OK
    if res.get("note"):
        log.warning("%s", res["note"])
    return EXIT_ERR


def _cmd_status(a) -> int:
    for k, v in case_summary(a.case).items():
        log.info("%-16s: %s", k, v)
    return EXIT_OK


def _cmd_cancel(a) -> int:
    if CfdRunner.cancel(a.case):
        log.info("Cancelamento solicitado — o executor atual vai "
                 "interromper o solver (incluindo filhos/MPI).")
        return EXIT_OK
    log.warning("Nenhuma execução ativa no caso %s.", a.case)
    return EXIT_USO


def _cmd_report(a) -> int:
    from .config import read_state
    from .results import read_results
    from .reporting import write_report
    case = Path(a.case)
    state = read_state(case)
    if state != CaseState.COMPLETED:
        log.warning("Estado do caso: %s — o relatório refletirá apenas o "
                    "que houver de resultados.", state.label)
    engine = _engine_from_case(case)
    import yaml
    from ..core.parameters import as_stages
    info = yaml.safe_load((case / "case_config.yaml").read_text(
        encoding="utf-8")) or {}
    try:
        stages = as_stages(info.get("wiebe_stages") or [])
    except Exception:                                   # noqa: BLE001
        stages = None
    res = read_results(case, engine=engine, stages=stages)
    from .reporting import load_exp_data
    exp_data = load_exp_data(case, engine=engine)
    p = write_report(case, res, exp_data=exp_data)
    log.info("Relatório gravado em %s", p)
    return EXIT_OK


_COMANDOS = {"doctor": _cmd_doctor, "prepare": _cmd_prepare,
             "validate": _cmd_validate, "run": _cmd_run,
             "status": _cmd_status, "cancel": _cmd_cancel,
             "report": _cmd_report}


def main_cfd(argv: Optional[List[str]] = None) -> int:
    """Entrada do subcomando ``wiebepy cfd``."""
    parser = build_cfd_parser()
    a = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s",
                        force=True)
    try:
        return _COMANDOS[a.cmd](a)
    except (CfdConfigError, ConfigError, AdapterError, RunnerError,
            FileNotFoundError) as e:
        log.error("ERRO: %s", e)
        return EXIT_USO
    except KeyboardInterrupt:
        log.error("Interrompido.")
        return EXIT_ERR
    except Exception as e:                              # noqa: BLE001
        log.error("ERRO inesperado (%s): %s — reporte com o log do caso.",
                  type(e).__name__, e)
        return EXIT_ERR


__all__ = ["main_cfd", "build_cfd_parser"]