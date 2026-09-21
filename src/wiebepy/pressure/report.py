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
    plots/*.png      pressão medida × simulada, diagrama P–V (modelo ×
                     experimental), resíduo, fração queimada, taxa de
                     liberação de calor [kJ/rad] por estágio, temperatura
                     do gás, calor perdido às paredes e volume
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
    from .engine import volume
    V = volume(d.theta, r.Rc, r.settings.engine)[0]
    Qt = r.settings.engine.Q_total
    hrr = Qt * multistage_wiebe_derivative(d.theta, r.stages)     # kJ/rad
    qcum = Qt * multistage_wiebe(d.theta, r.stages)               # kJ
    qw = r.Q_wall if r.Q_wall is not None else np.full(d.n, np.nan)
    _csv(out / "results.csv",
         ["theta_rad", "theta_deg", "V_m3", "P_exp_kPa", "P_sim_kPa",
          "residual_kPa", "Tg_K", "xb", "dxb_dtheta_per_deg",
          "dQ_dtheta_kJ_per_rad", "Q_released_kJ", "Q_wall_J"],
         zip(d.theta, thd, V, d.P, r.P_sim, r.P_sim - d.P, r.Tg, xb, dxb,
             hrr, qcum, qw))
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
    from .engine import volume
    V = volume(d.theta, r.Rc, r.settings.engine)[0] * 1e6
    for sufixo, log in (("", False), ("_loglog", True)):
        f, ax = plt.subplots(figsize=(6.5, 5))
        ax.plot(V, d.P, "+", ms=5, color="0.35", label="experimental")
        ax.plot(V, r.P_sim, "r-", lw=1.5,
                label=f"modelo ({r.settings.n_stages}-Wiebe, Rc {r.Rc:.3f})")
        if log:
            ax.set_xscale("log"); ax.set_yscale("log")
        ax.set(xlabel="Volume [cm³]", ylabel="P [kPa]",
               title="Diagrama P–V" + (" (log-log)" if log else ""))
        ax.grid(alpha=0.3, which="both"); ax.legend(); f.tight_layout()
        f.savefig(pasta / f"pv_diagram{sufixo}.png", dpi=150); plt.close(f)
    f, ax = plt.subplots(figsize=(7, 3.4))
    ax.plot(thd, r.P_sim - d.P, lw=1); ax.axhline(0, color="k", lw=0.8)
    ax.set(xlabel="θ [°]", ylabel="P sim − P med [kPa]", title="Resíduo")
    ax.grid(alpha=0.3); f.tight_layout()
    f.savefig(pasta / "residual.png", dpi=150); plt.close(f)
    Qt = r.settings.engine.Q_total
    th_r = np.linspace(d.theta[0], d.theta[-1], 2000)
    cxr, cdr = stage_contributions(th_r, r.stages)
    f, ax = plt.subplots(figsize=(7, 4.2))
    for j in range(len(r.stages)):
        ax.plot(np.degrees(th_r), Qt * cdr[j], label=f"dQ{j + 1}/dθ")
    ax.plot(np.degrees(th_r), Qt * cdr.sum(axis=0), "k-", lw=2.2,
            label="dQ/dθ total")
    ax.set(xlabel="θ [°]", ylabel="Taxa de liberação de calor [kJ/rad]",
           title="Taxa de liberação de calor por estágio e total")
    ax.grid(alpha=0.3); ax.legend(); f.tight_layout()
    f.savefig(pasta / "heat_release.png", dpi=150); plt.close(f)
    for nome, y, rot, tit in (
            ("temperature", r.Tg, "Temperatura do gás [K]", "Temperatura do gás"),
            ("heat_loss", r.Q_wall, "Calor perdido acumulado [J]",
             "Calor perdido para as paredes (Hohenberg)"),
            ("volume", volume(d.theta, r.Rc, r.settings.engine)[0] * 1e6,
             "Volume [cm³]", "Volume do cilindro")):
        if y is None:
            continue
        f, ax = plt.subplots(figsize=(7, 3.8))
        ax.plot(thd, y, lw=1.8)
        ax.set(xlabel="θ [°]", ylabel=rot, title=tit)
        ax.grid(alpha=0.3); f.tight_layout()
        f.savefig(pasta / f"{nome}.png", dpi=150); plt.close(f)
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
