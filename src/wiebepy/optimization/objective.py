# -*- coding: utf-8 -*-
"""
objective.py — Dados de ajuste, métricas e função objetivo.

Métricas (r = simulado − experimental, n pontos, k parâmetros livres):

    MSE   = Σ r² / n              RMSE  = √MSE
    MAE   = Σ |r| / n             SEE   = √(Σ r² / (n − k))
    WRMSE = √(Σ w r² / Σ w)       (pesos do arquivo; w = 1/σ² se houver σ)

Alvo do ajuste (``fit_target``):
    "xb"   — ajusta a fração queimada
    "dxb"  — ajusta a taxa de queima dx_b/dθ
    "both" — J = w_x·J(x_b)/s_x + w_d·J(dx_b)/s_d, onde s_x e s_d são os
             desvios-padrão das séries experimentais (pesos com significado
             independente da escala de cada série)

Todos os backends calculam os mesmos acumuladores por candidato
(Σr², Σ|r|, Σw r² de cada série) e chamam ``objective_from_acc`` — a
métrica é definida num único lugar.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

import numpy as np

from ..core.parameters import PENALTY
from ..core.validation import DataError, validate_data

METRICS = ("rmse", "mse", "mae", "see", "wrmse")
FIT_TARGETS = ("xb", "dxb", "both")

# ordem das colunas dos acumuladores
ACC_COLS = ("sse_x", "sae_x", "wsse_x", "sse_d", "sae_d", "wsse_d")


@dataclass
class FitData:
    """Série experimental: θ e ao menos uma de xb / dxb_dtheta."""
    theta: np.ndarray
    xb: Optional[np.ndarray] = None
    dxb: Optional[np.ndarray] = None
    weights: Optional[np.ndarray] = None
    angle_unit: str = "deg"
    source: str = ""
    warnings: list = field(default_factory=list)

    def __post_init__(self):
        self.theta = np.ascontiguousarray(self.theta, dtype=float)
        for k in ("xb", "dxb", "weights"):
            v = getattr(self, k)
            if v is not None:
                setattr(self, k, np.ascontiguousarray(v, dtype=float))
        self.warnings = validate_data(self.theta, self.xb, self.dxb,
                                      self.weights)

    @property
    def n(self) -> int:
        return int(self.theta.size)

    def default_target(self) -> str:
        if self.xb is not None and self.dxb is not None:
            return "both"
        return "xb" if self.xb is not None else "dxb"

    def subset(self, mask) -> "FitData":
        m = np.asarray(mask, dtype=bool)
        return FitData(self.theta[m],
                       None if self.xb is None else self.xb[m],
                       None if self.dxb is None else self.dxb[m],
                       None if self.weights is None else self.weights[m],
                       self.angle_unit, self.source)


@dataclass
class ObjectiveSpec:
    """Como o objetivo é calculado."""
    metric: str = "rmse"
    fit_target: str = "xb"
    w_x: float = 1.0
    w_d: float = 1.0
    n_params: int = 0              # k (para SEE)
    scale_x: float = 1.0           # usados só no alvo "both"
    scale_d: float = 1.0

    def check(self, data: FitData) -> "ObjectiveSpec":
        if self.metric not in METRICS:
            raise ValueError(f"--objective deve ser um de {METRICS}.")
        if self.fit_target not in FIT_TARGETS:
            raise ValueError(f"--fit-target deve ser um de {FIT_TARGETS}.")
        if self.fit_target in ("xb", "both") and data.xb is None:
            raise DataError("O alvo exige a coluna xb nos dados.")
        if self.fit_target in ("dxb", "both") and data.dxb is None:
            raise DataError("O alvo exige a coluna dxb_dtheta nos dados.")
        if self.fit_target == "both":
            self.scale_x = float(np.std(data.xb)) or 1.0
            self.scale_d = float(np.std(data.dxb)) or 1.0
        return self

    @property
    def want_x(self) -> bool:
        return self.fit_target in ("xb", "both")

    @property
    def want_d(self) -> bool:
        return self.fit_target in ("dxb", "both")


def _metric(sse, sae, wsse, n, k, sumw, metric, xp):
    if metric == "rmse":
        return xp.sqrt(sse / n)
    if metric == "mse":
        return sse / n
    if metric == "mae":
        return sae / n
    if metric == "see":
        return xp.sqrt(sse / max(n - k, 1))
    return xp.sqrt(wsse / sumw)                     # wrmse


def objective_from_acc(acc, pen, spec: ObjectiveSpec, n: int, sumw: float,
                       xp=np):
    """Acumuladores (S, 6) + penalidade (S,) -> objetivo (S,)."""
    J = xp.zeros(acc.shape[0], dtype=acc.dtype)
    if spec.want_x:
        Jx = _metric(acc[:, 0], acc[:, 1], acc[:, 2], n, spec.n_params, sumw,
                     spec.metric, xp)
        J = J + (spec.w_x * Jx / spec.scale_x if spec.fit_target == "both"
                 else Jx)
    if spec.want_d:
        Jd = _metric(acc[:, 3], acc[:, 4], acc[:, 5], n, spec.n_params, sumw,
                     spec.metric, xp)
        J = J + (spec.w_d * Jd / spec.scale_d if spec.fit_target == "both"
                 else Jd)
    J = J + pen
    return xp.where(xp.isfinite(J), J, PENALTY)


def accumulate(xb, dxb, data_dev: Dict, xp=np):
    """Resíduos (S, n) -> acumuladores (S, 6). Séries ausentes ficam 0."""
    S = (xb if xb is not None else dxb).shape[0]
    acc = xp.zeros((S, 6), dtype=(xb if xb is not None else dxb).dtype)
    w = data_dev["w"]
    for serie, sim, c in (("xb", xb, 0), ("dxb", dxb, 3)):
        if sim is None:
            continue
        r = sim - data_dev[serie][None, :]
        r2 = r * r
        acc[:, c] = r2.sum(axis=1)
        acc[:, c + 1] = xp.abs(r).sum(axis=1)
        acc[:, c + 2] = (r2 * w[None, :]).sum(axis=1)
    return acc


# =============================================================================
# Métricas de relatório (um candidato, numpy)
# =============================================================================
def fit_metrics(y, yhat, k: int, weights=None) -> Dict[str, float]:
    """RMSE, MSE, MAE, SEE, WRMSE, R², SSE, AIC, BIC, Durbin-Watson e
    autocorrelação lag-1 dos resíduos (r = yhat − y)."""
    y = np.asarray(y, dtype=float)
    r = np.asarray(yhat, dtype=float) - y
    n = y.size
    w = np.ones(n) if weights is None else np.asarray(weights, dtype=float)
    sse = float(np.sum(r * r))
    sst = float(np.sum((y - y.mean()) ** 2))
    sse_pos = max(sse, 1e-300)
    rc = r - r.mean()
    den = float(np.sum(rc * rc))
    return {
        "n": n, "k": k, "sse": sse,
        "rmse": float(np.sqrt(sse / n)), "mse": sse / n,
        "mae": float(np.mean(np.abs(r))),
        "see": float(np.sqrt(sse / max(n - k, 1))),
        "wrmse": float(np.sqrt(np.sum(w * r * r) / np.sum(w))),
        "r2": (1.0 - sse / sst) if sst > 0 else float("nan"),
        # AIC/BIC gaussianos (supõem resíduos independentes — ver README)
        "aic": n * np.log(sse_pos / n) + 2 * k,
        "bic": n * np.log(sse_pos / n) + k * np.log(n),
        "durbin_watson": (float(np.sum(np.diff(r) ** 2)) / den
                          if den > 0 else float("nan")),
        "lag1_autocorr": (float(np.sum(rc[1:] * rc[:-1])) / den
                          if den > 0 else float("nan")),
    }
