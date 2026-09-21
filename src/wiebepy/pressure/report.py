# -*- coding: utf-8 -*-
"""
report.py — Arquivos de saída do modo pressão (usados pela CLI e pela GUI).

    results.csv      θ [rad e °], P medida, P simulada, resíduo, Tg, x_b e
                     dx_b/dθ [1/°] dos estágios ajustados
    parameters.csv   Rc e parâmetros de cada estágio (θ0 e Δθ em rad e °)
    metrics.csv      RMSE, MAE, R², AIC, BIC, Durbin-Watson, P máx…
    run_statistics.csv  RMSE (solve_ivp) e RMSE (RK4) de cada run
    warnings.txt     avisos
    results.json     tudo acima
    comparison.csv   (comparação 1..5)
    plots/*.png      pressão medida × simulada, resíduo, x_b e taxa de queima
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Dict, Optional

import numpy as np

from ..core.core import multistage_wiebe, stage_contributions
from ..core.derivatives import multistage_wiebe_derivative
from ..core.parameters import Stage


def _graus(stages):
    return [Stage(s.beta, math.degrees(s.theta0), math.degrees(s.duration),
                  s.m, s.a) for s in stages]


def _csv(path: Path, cab, linhas):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(cab)
        for l in linhas:
            w.writerow([f"{v:.10g}" if isinstance(v, (float, np.floating)) else v
                        for v in l])


def write_outputs(outdir, r, d, comp: Optional[Dict] = None,
                  plots: bool = True) -> Path:
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    thd = np.degrees(d.theta)
    st_deg = _graus(r.stages)
    xb = multistage_wiebe(thd, st_deg)
    dxb = multistage_wiebe_derivative(thd, st_deg)
    _csv(out / "results.csv",
         ["theta_rad", "theta_deg", "P_exp_kPa", "P_sim_kPa", "residual_kPa",
          "Tg_K", "xb", "dxb_dtheta_per_deg"],
         zip(d.theta, thd, d.P, r.P_sim, r.P_sim - d.P, r.Tg, xb, dxb))
    _csv(out / "parameters.csv",
         ["stage", "beta", "theta0_rad", "theta0_deg", "duration_rad",
          "duration_deg", "m", "a"],
         [[j, s.beta, s.theta0, math.degrees(s.theta0), s.duration,
           math.degrees(s.duration), s.m, s.a]
          for j, s in enumerate(r.stages, start=1)] + [["Rc", r.Rc]])
    _csv(out / "metrics.csv", ["metric", "value"], sorted(r.metrics.items()))
    _csv(out / "run_statistics.csv",
         ["run", "seed", "rmse_solve_ivp_kPa", "rmse_rk4_kPa", "iterations",
          "stopped_by", "time_s", "note"],
         [[x.run + 1, x.seed if x.seed is not None else "", x.rmse, x.rmse_rk4,
           x.iterations, x.stopped_by, x.elapsed_s, x.note] for x in r.runs])
    (out / "warnings.txt").write_text("".join(f"{w}\n" for w in r.warnings),
                                      encoding="utf-8")
    from ..io.config import _plain
    (out / "results.json").write_text(json.dumps(_plain(r.to_dict()), indent=2,
                                                 ensure_ascii=False, default=str),
                                      encoding="utf-8")
    if comp is not None:
        cab = list(comp["table"][0])
        _csv(out / "comparison.csv", cab,
             ([l[c] for c in cab] for l in comp["table"]))
    if plots:
        _plots(out / "plots", r, d, st_deg)
    return out


def _plots(pasta: Path, r, d, st_deg):
    import matplotlib
    matplotlib.use("Agg", force=False)
    import matplotlib.pyplot as plt
    pasta.mkdir(parents=True, exist_ok=True)
    thd = np.degrees(d.theta)
    f, ax = plt.subplots(figsize=(7, 4.2))
    ax.plot(thd, d.P, ".", ms=3, color="0.5", label="medida")
    ax.plot(thd, r.P_sim, "r-", lw=1.6,
            label=f"simulada ({r.settings.n_stages}-Wiebe)")
    ax.set(xlabel="θ [°]", ylabel="P [kPa]",
           title=f"Pressão — RMSE {r.metrics.get('rmse', float('nan')):.2f} kPa")
    ax.grid(alpha=0.3); ax.legend(); f.tight_layout()
    f.savefig(pasta / "pressure.png", dpi=150); plt.close(f)
    f, ax = plt.subplots(figsize=(7, 3.4))
    ax.plot(thd, r.P_sim - d.P, lw=1); ax.axhline(0, color="k", lw=0.8)
    ax.set(xlabel="θ [°]", ylabel="P sim − P med [kPa]", title="Resíduo")
    ax.grid(alpha=0.3); f.tight_layout()
    f.savefig(pasta / "residual.png", dpi=150); plt.close(f)
    th = np.linspace(thd[0], thd[-1], 2000)
    cx, cd = stage_contributions(th, st_deg)
    for nome, total, contrib, rot in (
            ("burned_fraction", multistage_wiebe(th, st_deg), cx, "x_b [-]"),
            ("burn_rate", multistage_wiebe_derivative(th, st_deg), cd,
             "dx_b/dθ [1/°]")):
        f, ax = plt.subplots(figsize=(7, 4.2))
        for j in range(len(st_deg)):
            ax.plot(th, contrib[j], label=f"estágio {j + 1}")
        ax.plot(th, total, "k--", lw=1.5, label="total")
        ax.set(xlabel="θ [°]", ylabel=rot); ax.grid(alpha=0.3); ax.legend()
        f.tight_layout(); f.savefig(pasta / f"{nome}.png", dpi=150); plt.close(f)
