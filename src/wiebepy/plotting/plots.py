# -*- coding: utf-8 -*-
"""
plots.py — Figuras (Matplotlib).

    fig1_xb              x_b(θ) total
    fig2_contrib_xb      contribuições β_j x_j(θ)
    fig3_dxb             dx_b/dθ
    fig4_contrib_dxb     contribuições β_j dx_j/dθ
    fig5_fit             experimental × ajustado
    fig6_residuals       resíduos
    fig7_convergence     histórico de convergência do PSO (todos os runs)
    fig_comparison       comparação entre números de estágios (RMSE/CV/BIC)
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

import matplotlib
import numpy as np

from ..core.core import multistage_wiebe, stage_contributions
from ..core.derivatives import multistage_wiebe_derivative

CORES = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#ff7f0e"]


def _plt(show: bool):
    if not show:
        matplotlib.use("Agg", force=False)
    import matplotlib.pyplot as plt
    return plt


def _ulabel(angle_unit: str) -> str:
    return "°" if angle_unit == "deg" else "rad"


def make_figures(theta, stages, data=None, fit_result=None,
                 angle_unit: str = "deg", show: bool = False) -> Dict:
    """Cria as figuras disponíveis e devolve {nome: Figure}."""
    plt = _plt(show)
    u = _ulabel(angle_unit)
    th = np.asarray(theta, dtype=float)
    xb = multistage_wiebe(th, stages)
    dxb = multistage_wiebe_derivative(th, stages)
    cx, cd = stage_contributions(th, stages)
    N = len(stages)
    rot = f"θ [{u}]"
    figs = {}

    f, ax = plt.subplots(figsize=(7, 4.2))
    ax.plot(th, xb, "k-", lw=2, label=f"$x_b$ ({N}-Wiebe)")
    ax.set(xlabel=rot, ylabel="$x_b$ [-]", title="Fração de massa queimada",
           ylim=(-0.02, 1.05))
    ax.grid(alpha=0.3); ax.legend()
    figs["fig1_xb"] = f

    f, ax = plt.subplots(figsize=(7, 4.2))
    for j in range(N):
        ax.plot(th, cx[j], color=CORES[j], label=f"$β_{j + 1} x_{{b,{j + 1}}}$")
    ax.plot(th, xb, "k--", lw=1.5, label="$x_b$ total")
    ax.set(xlabel=rot, ylabel="[-]", title="Contribuição de cada estágio")
    ax.grid(alpha=0.3); ax.legend()
    figs["fig2_contrib_xb"] = f

    f, ax = plt.subplots(figsize=(7, 4.2))
    ax.plot(th, dxb, "k-", lw=2)
    ax.set(xlabel=rot, ylabel=f"$dx_b/dθ$ [1/{u}]", title="Taxa de queima")
    ax.grid(alpha=0.3)
    figs["fig3_dxb"] = f

    f, ax = plt.subplots(figsize=(7, 4.2))
    for j in range(N):
        ax.plot(th, cd[j], color=CORES[j],
                label=f"$β_{j + 1}\\,dx_{{b,{j + 1}}}/dθ$")
    ax.plot(th, dxb, "k--", lw=1.5, label="total")
    ax.set(xlabel=rot, ylabel=f"[1/{u}]",
           title="Taxa de queima por estágio")
    ax.grid(alpha=0.3); ax.legend()
    figs["fig4_contrib_dxb"] = f

    if data is not None:
        series = [(k, getattr(data, k)) for k in ("xb", "dxb")
                  if getattr(data, k) is not None]
        dth = data.theta
        f, axs = plt.subplots(len(series), 1, figsize=(7, 3.6 * len(series)),
                              squeeze=False)
        for ax, (k, y) in zip(axs[:, 0], series):
            sim = (multistage_wiebe(dth, stages) if k == "xb"
                   else multistage_wiebe_derivative(dth, stages))
            ax.plot(dth, y, ".", ms=3, color="0.45", label="experimental")
            ax.plot(dth, sim, "r-", lw=1.8, label="ajustado")
            ax.set(xlabel=rot, ylabel="$x_b$" if k == "xb" else
                   f"$dx_b/dθ$ [1/{u}]")
            ax.grid(alpha=0.3); ax.legend()
        axs[0, 0].set_title("Experimental × ajustado")
        f.tight_layout()
        figs["fig5_fit"] = f

        f, axs = plt.subplots(len(series), 1, figsize=(7, 3.2 * len(series)),
                              squeeze=False)
        for ax, (k, y) in zip(axs[:, 0], series):
            sim = (multistage_wiebe(dth, stages) if k == "xb"
                   else multistage_wiebe_derivative(dth, stages))
            ax.plot(dth, sim - y, "-", lw=1, color="C0")
            ax.axhline(0, color="k", lw=0.8)
            ax.set(xlabel=rot, ylabel=f"resíduo {k}")
            ax.grid(alpha=0.3)
        axs[0, 0].set_title("Resíduos (ajustado − experimental)")
        f.tight_layout()
        figs["fig6_residuals"] = f

    if fit_result is not None:
        f, ax = plt.subplots(figsize=(7, 4.2))
        for r in fit_result.runs:
            ax.semilogy(np.maximum(r.history, 1e-300), lw=1,
                        label=f"run {r.run + 1}" if len(fit_result.runs) <= 10
                        else None)
        ax.set(xlabel="iteração", ylabel=f"objetivo ({fit_result.spec.metric})",
               title="Convergência do PSO (antes do refinamento local)")
        ax.grid(alpha=0.3, which="both")
        if len(fit_result.runs) <= 10:
            ax.legend(fontsize=8)
        figs["fig7_convergence"] = f
    for fig in figs.values():
        fig.tight_layout()
    return figs


def comparison_figure(table: List[Dict], show: bool = False):
    plt = _plt(show)
    ns = [l["n_stages"] for l in table]
    f, axs = plt.subplots(1, 2, figsize=(10, 4))
    axs[0].plot(ns, [l["rmse"] for l in table], "o-", label="RMSE treino")
    cv = [l["cv_rmse"] for l in table]
    if all(np.isfinite(cv)):
        axs[0].errorbar(ns, cv, yerr=[l["cv_std"] for l in table], fmt="s--",
                        capsize=3, label="RMSE validação cruzada")
    axs[0].set(xlabel="número de estágios", ylabel="RMSE", yscale="log",
               title="Erro × complexidade")
    axs[0].legend(); axs[0].grid(alpha=0.3, which="both")
    axs[1].plot(ns, [l["delta_aic"] for l in table], "o-", label="ΔAIC")
    axs[1].plot(ns, [l["delta_bic"] for l in table], "s-", label="ΔBIC")
    axs[1].set(xlabel="número de estágios", ylabel="Δ (menor = melhor)",
               title="AIC/BIC (indicativos: resíduos correlacionados)")
    axs[1].legend(); axs[1].grid(alpha=0.3)
    for ax in axs:
        ax.set_xticks(ns)
    f.tight_layout()
    return f


def save_figures(figs: Dict, outdir, dpi: int = 150) -> List[Path]:
    out = []
    d = Path(outdir)
    d.mkdir(parents=True, exist_ok=True)
    for nome, fig in figs.items():
        p = d / f"{nome}.png"
        fig.savefig(p, dpi=dpi)
        out.append(p)
    return out


def close_all(figs: Optional[Dict] = None) -> None:
    import matplotlib.pyplot as plt
    for f in (figs or {}).values():
        plt.close(f)
