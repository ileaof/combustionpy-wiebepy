# -*- coding: utf-8 -*-
"""
cli.py — Subcomando ``wiebepy cfd crevice <subcomando> …``.

    wiebepy cfd crevice doctor                  ambiente (herda o doctor do cfd)
    wiebepy cfd crevice prepare  --config ARQ [--output DIR]
    wiebepy cfd crevice validate --case DIR
    wiebepy cfd crevice run      --case DIR [--workers N] [--distro NOME]
                                                [--follow]
    wiebepy cfd crevice status   --case DIR
    wiebepy cfd crevice cancel   --case DIR
    wiebepy cfd crevice report   --case DIR

O módulo é OPCIONAL: sem ele (e sem casos de fresta) o wiebepy inteiro
funciona exatamente como antes — nada nos modelos single/double/multi
Wiebe é tocado. Códigos de saída: 0 ok | 2 uso/config | 1 erro.
"""
from __future__ import annotations

import argparse
import logging
import signal
from pathlib import Path
from typing import List, Optional

from ..cfd.adapters.base import AdapterError
from ..cfd.config import CaseState, read_state
from ..cfd.runner import RunnerError, make_cancel_poller

log = logging.getLogger("wiebepy")
EXIT_OK, EXIT_ERR, EXIT_USO = 0, 1, 2


def build_crevice_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="wiebepy cfd crevice",
        description="Módulo OPCIONAL crevice_flow: escoamento na fresta "
                    "top-land (pistão/1º anel/cilindro). NÍVEL SUBMODELO: "
                    "pressão da câmara prescrita (o escoamento não a "
                    "modifica) e domínio comunicando APENAS com a câmara "
                    "— NÃO é simulação de blow-by. Sem anéis móveis, sem "
                    "óleo, sem combustão, sem emissões.")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("doctor", help="diagnóstico do ambiente (WSL2/OpenFOAM)")
    s.add_argument("--distro", metavar="NOME")

    s = sub.add_parser("prepare", help="gera o caso de fresta para "
                                       "inspeção (sem executar)")
    s.add_argument("--config", required=True, metavar="ARQ",
                   help="config YAML com a seção crevice: (ver "
                        "examples/crevice/crevice_exemplo.yaml)")
    s.add_argument("--output", metavar="DIR",
                   help="sobrescreve case_directory da config")

    s = sub.add_parser("validate", help="valida o caso antes da execução")
    s.add_argument("--case", required=True, metavar="DIR")

    s = sub.add_parser("run", help="executa o caso validado")
    s.add_argument("--case", required=True, metavar="DIR")
    s.add_argument("--workers", type=int, metavar="N",
                   help="processos MPI do solver (padrão 1 = serial)")
    s.add_argument("--distro", metavar="NOME",
                   help="distribuição WSL2 com o solver")
    s.add_argument("--follow", action="store_true",
                   help="mostra a saída do solver em tempo real")

    s = sub.add_parser("status", help="estado do caso")
    s.add_argument("--case", required=True, metavar="DIR")

    s = sub.add_parser("cancel", help="cancela a execução ativa")
    s.add_argument("--case", required=True, metavar="DIR")

    s = sub.add_parser("report", help="gera o relatório HTML autônomo")
    s.add_argument("--case", required=True, metavar="DIR")
    return p


# ----------------------------------------------------------------- helpers
def _cfg_do_config(arq: str, output: Optional[str]):
    from .config import read_crevice_config
    cfg = read_crevice_config(arq)
    if output:
        cfg.case_directory = output
    return cfg


def _solver_install(distro: Optional[str]):
    from ..cfd.capabilities import doctor
    rep = doctor()
    for dd in rep.distros:
        if distro is not None and dd["name"] != distro:
            continue
        if dd["openfoam"]:
            return dd["openfoam"][0], dd["name"]
    return None, distro


# ----------------------------------------------------------------- comandos
def _cmd_doctor(a) -> int:
    from ..cfd.capabilities import doctor
    rep = doctor()
    print(rep.format())
    best = rep.best()
    if not best:
        print("crevice_flow: sem OpenFOAM — a execução exige o solver; "
              "prepare/validate seguem disponíveis.")
        return EXIT_OK
    print(f"crevice_flow: pronto para executar com OpenFOAM "
          f"{best.get('version')} na distro '{best.get('distro')}'.")
    return EXIT_OK


def _cmd_prepare(a) -> int:
    from .config import CreviceConfig
    from .runner import CreviceRunner
    cfg = _cfg_do_config(a.config, a.output)
    erros = cfg.validate()
    if erros:
        for e in erros:
            log.error("ERRO: %s", e)
        return EXIT_USO
    inst, distro = _solver_install(None)
    runner = CreviceRunner(cfg, distro=distro,
                           solver_info=inst or {"version": None})
    d = runner.prepare()
    log.info("Caso de fresta preparado em %s (estado: %s).", d,
             CaseState.PREPARED.label)
    log.info("Inspecione os arquivos; então: wiebepy cfd crevice validate "
             "--case \"%s\"", d)
    return EXIT_OK


def _cmd_validate(a) -> int:
    from .validation import validate_case
    ok, erros, avisos = validate_case(a.case)
    for w in avisos:
        log.warning("WARNING: %s", w)
    if ok:
        log.info("Caso de fresta válido: %s", a.case)
        return EXIT_OK
    for e in erros:
        log.error("ERRO: %s", e)
    return EXIT_USO


def _cmd_run(a) -> int:
    from .runner import CreviceRunner, _t_end, check_completion
    d = Path(a.case)
    ok, erros, _ = _validate_silent(d)
    if not ok:
        for e in erros:
            log.error("ERRO: %s", e)
        return EXIT_USO
    inst, distro = _solver_install(a.distro)
    runner = CreviceRunner(None, distro=distro, solver_info=inst or {})
    log.info("Executando caso de fresta %s (workers=%s, distro=%s)…", d,
             a.workers or 1, distro or "auto")
    ev, poll = make_cancel_poller(d)

    def _segv(*_):
        ev.set()
    try:
        prev = signal.signal(signal.SIGINT, _segv)
    except ValueError:
        prev = None
    try:
        res = runner.run(d, workers=a.workers or 1, cancel=poll,
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
        log.info("Concluído — relatório: wiebepy cfd crevice report "
                 "--case \"%s\"", d)
        return EXIT_OK
    if res.get("note"):
        log.warning("%s", res["note"])
    return EXIT_ERR


def _validate_silent(d: Path):
    from .validation import validate_case
    return validate_case(d, set_validated=False)


def _cmd_status(a) -> int:
    from ..cfd.validation import case_summary
    for k, v in case_summary(a.case).items():
        log.info("%-16s: %s", k, v)
    return EXIT_OK


def _cmd_cancel(a) -> int:
    from .runner import CreviceRunner
    if CreviceRunner.cancel(a.case):
        log.info("Cancelamento solicitado — o executor atual vai "
                 "interromper o solver (incluindo filhos/MPI).")
        return EXIT_OK
    log.warning("Nenhuma execução ativa no caso %s.", a.case)
    return EXIT_USO


def _cmd_report(a) -> int:
    from .report import write_report
    case = Path(a.case)
    state = read_state(case)
    if state != CaseState.COMPLETED:
        log.warning("Estado do caso: %s — o relatório refletirá apenas o "
                    "que houver de resultados.", state.label)
    p = write_report(case)
    log.info("Relatório gravado em %s", p)
    return EXIT_OK


_COMANDOS = {"doctor": _cmd_doctor, "prepare": _cmd_prepare,
             "validate": _cmd_validate, "run": _cmd_run,
             "status": _cmd_status, "cancel": _cmd_cancel,
             "report": _cmd_report}


def main_crevice(argv: Optional[List[str]] = None) -> int:
    """Entrada do subcomando ``wiebepy cfd crevice``."""
    parser = build_crevice_parser()
    a = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s",
                        force=True)
    try:
        return _COMANDOS[a.cmd](a)
    except (RunnerError, AdapterError) as e:
        log.error("ERRO: %s", e)
        return EXIT_USO


if __name__ == "__main__":
    raise SystemExit(main_crevice())