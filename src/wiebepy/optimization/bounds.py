# -*- coding: utf-8 -*-
"""
bounds.py — Limites do espaço de busca a partir dos dados e da configuração.

Padrão (R = θ_max − θ_min dos dados):

    theta0_1   ∈ [θ_min, θ_max − 0.05 R]
    dtheta0_j  ∈ [0, 0.5 R]              (incremento entre inícios, j ≥ 2)
    duration_j ∈ [0.01 R, 1.5 R]
    m_j        ∈ [0.05, 5]
    a_j        ∈ [1, 15]                 (só se --fit-a)
    s_j        ∈ [0, 1]  | z_j ∈ [−8, 8] | beta_j ∈ [0, 1]

Limite cumulativo: theta0_N <= theta0_max (padrão θ_max); violações são
penalizadas suavemente na função objetivo (ver Parametrization.decode).
Qualquer limite pode ser sobrescrito pela seção ``bounds`` do arquivo de
configuração.
"""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np

from ..core.parameters import StageBounds

_CAMPOS = ("theta0", "dtheta0", "duration", "m", "a", "z")


def bounds_from_data(theta_min: float, theta_max: float,
                     overrides: Optional[Dict] = None) -> StageBounds:
    """StageBounds padrão para o intervalo dos dados + sobrescritas."""
    b = StageBounds.from_data(theta_min, theta_max)
    for k, v in (overrides or {}).items():
        if k == "theta0_max":
            b.theta0_max = None if v is None else float(v)
        elif k in _CAMPOS:
            lo, hi = float(v[0]), float(v[1])
            if not lo < hi:
                raise ValueError(f"Limite inválido para {k}: [{lo}, {hi}].")
            setattr(b, k, (lo, hi))
        else:
            raise ValueError(f"Limite desconhecido: '{k}'. Válidos: "
                             f"{list(_CAMPOS) + ['theta0_max']}.")
    if b.m[0] <= 0 or b.duration[0] <= 0 or b.a[0] <= 0:
        raise ValueError("Limites inferiores de m, duration e a devem ser > 0.")
    return b


def effective_theta0_bounds(b: StageBounds, n_stages: int) -> List[tuple]:
    """Intervalo alcançável de cada theta0_j (cumulativo), para relatório."""
    out = []
    for j in range(n_stages):
        lo = b.theta0[0] + j * b.dtheta0[0]
        hi = b.theta0[1] + j * b.dtheta0[1]
        if b.theta0_max is not None:
            hi = min(hi, b.theta0_max)
        out.append((float(lo), float(hi)))
    return out


def at_bounds(x: np.ndarray, lower: np.ndarray, upper: np.ndarray,
              rel_tol: float = 1e-3) -> np.ndarray:
    """Máscara dos parâmetros a menos de rel_tol·(faixa) de um limite."""
    span = np.maximum(upper - lower, 1e-300)
    return (np.abs(x - lower) <= rel_tol * span) | (
        np.abs(upper - x) <= rel_tol * span)
