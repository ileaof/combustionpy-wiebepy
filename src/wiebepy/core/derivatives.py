# -*- coding: utf-8 -*-
"""
derivatives.py — Taxa de queima dx_b/dθ (derivada analítica) e verificação
por diferenças finitas centrais.

    dx_j/dθ = a_j (m_j+1)/Δθ_j · z_j^m_j · exp(−a_j z_j^(m_j+1))   (θ ≥ θ0_j)
    dx_b/dθ = Σ_j β_j dx_j/dθ

Unidade: 1/[unidade angular] (1/grau ou 1/rad).

Com 0 < m_j < 1 a derivada é contínua mas tem inclinação infinita em θ0_j;
por isso a comparação com diferenças finitas exclui uma janela em torno
de cada início (``exclude_window``).
"""
from __future__ import annotations

from typing import Dict

import numpy as np

from .core import get_xp, multistage_wiebe, stage_contributions
from .parameters import as_stages, stages_to_arrays


def multistage_wiebe_derivative(theta, stages, xp=None):
    """dx_b/dθ analítica para 1..5 estágios (mesma assinatura de
    ``multistage_wiebe``)."""
    return stage_contributions(theta, stages, xp, want_x=False)[1].sum(axis=0)


def finite_difference_check(theta, stages, h: float | None = None,
                            rtol: float = 1e-6, atol: float = 1e-8,
                            exclude_window: float = 2.0) -> Dict:
    """Compara a derivada analítica com diferenças finitas centrais.

    h              : passo (default: 1e-5 × amplitude de θ)
    exclude_window : exclui |θ − θ0_j| <= exclude_window·h (singularidade
                     de inclinação quando m_j < 1)

    Retorna dict com max_abs_err, max_rel_err, n_points, ok.
    """
    theta = np.asarray(theta, dtype=float)
    if h is None:
        h = 1e-5 * max(float(np.ptp(theta)), 1.0)
    st = as_stages(stages)
    mask = np.ones(theta.shape, dtype=bool)
    for s in st:
        mask &= np.abs(theta - s.theta0) > exclude_window * h
    th = theta[mask]
    anal = multistage_wiebe_derivative(th, st)
    # FD sobre a soma sem recorte (o clip só remove ruído em 0/1)
    arr = stages_to_arrays(st)
    xp = get_xp(th)
    fp = stage_contributions(th + h, arr, xp, want_dx=False)[0].sum(axis=0)
    fm = stage_contributions(th - h, arr, xp, want_dx=False)[0].sum(axis=0)
    fd = (fp - fm) / (2.0 * h)
    err = np.abs(anal - fd)
    rel = err / np.maximum(np.abs(anal), atol)
    ok = bool(np.all(err <= atol + rtol * np.abs(anal)))
    return {"max_abs_err": float(err.max(initial=0.0)),
            "max_rel_err": float(rel.max(initial=0.0)),
            "n_points": int(th.size), "h": float(h), "ok": ok}


__all__ = ["multistage_wiebe_derivative", "finite_difference_check",
           "multistage_wiebe"]
