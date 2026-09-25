# -*- coding: utf-8 -*-
"""
monitor_crevice.py — Monitor do caso demo de fresta em execução.

Imprime progresso (tempo físico simulado / tempo alvo, último passo,
estimativa de conclusão) sem interferir na execução.
"""
import re
import sys
import time
from pathlib import Path

case = Path(sys.argv[1] if len(sys.argv) > 1 else "results/crevice_exemplo")
alvo = float(sys.argv[2]) if len(sys.argv) > 2 else 0.04
log = case / "logs" / "foamRun.log"
if not log.exists():
    print("log ainda não existe")
    raise SystemExit(0)

re_time = re.compile(r"^Time = ([0-9.eE+-]+)")
re_exec = re.compile(r"ExecutionTime = ([0-9.eE+-]+)")
ult_t = 0.0
while True:
    txt = log.read_text(encoding="utf-8", errors="replace")
    for l in txt.splitlines():
        m = re_time.match(l.strip())
        if m:
            ult_t = float(m.group(1))
    if "End" in txt:
        print(f"FOI ATÉ 'End' em t={ult_t:.4g} s (alvo {alvo})")
        break
    m = re_exec.search(txt)
    exec_s = float(m.group(1)) if m else 0.0
    frac = ult_t / alvo if alvo else 0.0
    eta = exec_s / frac * (1 - frac) if frac > 0.01 else float("nan")
    print(f"t = {ult_t:.4g} s ({100*frac:.1f} % de {alvo}) | "
          f"execução {exec_s:.0f} s | ETA ~{eta/60:.0f} min")
    time.sleep(60)