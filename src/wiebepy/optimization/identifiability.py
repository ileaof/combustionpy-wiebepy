# -*- coding: utf-8 -*-
"""
identifiability.py — Diagnóstico básico de identificabilidade.

Verifica, sobre o melhor ajuste e a dispersão entre runs:

* estágios com contribuição β_j < 0.5 %;
* inícios θ0 quase coincidentes (e estágios quase idênticos);
* parâmetros de busca presos nos limites;
* parâmetros que variam muito entre runs independentes;
* correlação forte entre parâmetros (|ρ| > 0.95), estimada pela matriz
  (JᵀJ)⁻¹ do jacobiano dos resíduos no ótimo (diferenças finitas).
"""
from __future__ import annotations

from typing import Dict, List, Sequence

import numpy as np

from ..core.core import evaluate_batch
from ..i18n import tf
from ..core.parameters import Parametrization, Stage
from .bounds import at_bounds


def stage_warnings(stages: Sequence[Stage], theta_range: float,
                   beta_min: float = 0.005, rel_close: float = 0.01) -> List[str]:
    out = []
    for j, s in enumerate(stages, start=1):
        if s.beta < beta_min:
            out.append(tf("AVISO: o estágio {j} contribui com menos de "
                          "{pct:.1f}% (beta_{j} = {beta:.3g}).", j=j,
                          pct=beta_min * 100, beta=s.beta))
    for j in range(len(stages) - 1):
        a, b = stages[j], stages[j + 1]
        if abs(b.theta0 - a.theta0) < rel_close * theta_range:
            msg = tf("AVISO: theta0_{a} e theta0_{b} são quase iguais "
                     "({va:.4g} vs {vb:.4g}).", a=j + 1, b=j + 2,
                     va=a.theta0, vb=b.theta0)
            if (abs(b.duration - a.duration) < 0.1 * max(a.duration, b.duration)
                    and abs(b.m - a.m) < 0.1 * max(a.m, b.m)):
                msg += tf(" Os estágios {a} e {b} são quase idênticos "
                          "(redundantes).", a=j + 1, b=j + 2)
            out.append(msg)
    return out


def _lado(inferior: bool) -> str:
    """"inferior"/"superior" traduzidos (entram num molde maior)."""
    from ..i18n import t as _
    return _("inferior") if inferior else _("superior")


def bound_warnings(x: np.ndarray, param: Parametrization) -> List[str]:
    out = []
    mask = at_bounds(x, param.lower, param.upper)
    for i in np.flatnonzero(mask):
        nome = param.names[i]
        inferior = abs(x[i] - param.lower[i]) <= abs(param.upper[i] - x[i])
        # dtheta0 no limite inferior 0 = inícios coincidentes; s_j = 0 ou 1
        # zera estágios — ambos já tratados em stage_warnings, mas o aviso
        # do parâmetro de busca continua útil.
        out.append(tf("AVISO: o parâmetro {nome} atingiu o limite "
                      "{lado} ({valor:.4g}).", nome=nome,
                      lado=_lado(inferior), valor=x[i]))
    return out


def dispersion_warnings(xs: np.ndarray, param: Parametrization,
                        rel: float = 0.10) -> List[str]:
    """xs (runs, P): desvio-padrão entre runs > rel·(faixa do parâmetro)."""
    if xs.shape[0] < 2:
        return []
    span = np.maximum(param.upper - param.lower, 1e-300)
    sd = xs.std(axis=0, ddof=1) / span
    return [tf("AVISO: o parâmetro {nome} varia muito entre os runs "
               "(desvio = {pct:.1f}% da faixa).", nome=param.names[i],
               pct=sd[i] * 100)
            for i in np.flatnonzero(sd > rel)]


def residual_jacobian(x: np.ndarray, param: Parametrization, data,
                      fit_target: str, rel_step: float = 1e-6) -> np.ndarray:
    """Jacobiano (n_res, P) dos resíduos no ponto x (diferenças centrais,
    todos os pontos perturbados avaliados num único lote)."""
    span = param.upper - param.lower
    h = rel_step * np.maximum(span, 1e-12)
    P = x.size
    X = np.repeat(x[None, :], 2 * P, axis=0)
    idx = np.arange(P)
    X[2 * idx, idx] += h
    X[2 * idx + 1, idx] -= h
    params, _ = param.decode(X)
    want_x = fit_target in ("xb", "both")
    want_d = fit_target in ("dxb", "both")
    xb, dxb = evaluate_batch(data.theta, params, np, want_x, want_d)
    partes = []
    if want_x:
        s = np.std(data.xb) if fit_target == "both" else 1.0
        partes.append(xb / (s or 1.0))
    if want_d:
        s = np.std(data.dxb) if fit_target == "both" else 1.0
        partes.append(dxb / (s or 1.0))
    R = np.concatenate(partes, axis=1)             # (2P, n_res)
    return ((R[0::2] - R[1::2]) / (2.0 * h[:, None])).T


def correlation_warnings(x, param, data, fit_target,
                         limit: float = 0.95) -> Dict:
    """Correlações fortes e número de condição de JᵀJ."""
    J = residual_jacobian(np.asarray(x, dtype=float), param, data, fit_target)
    # escala por coluna para o número de condição ser significativo
    col = np.linalg.norm(J, axis=0)
    Js = J / np.where(col > 0, col, 1.0)
    JtJ = Js.T @ Js
    cond = float(np.linalg.cond(JtJ)) if np.all(col > 0) else float("inf")
    cov = np.linalg.pinv(JtJ)
    d = np.sqrt(np.clip(np.diag(cov), 1e-300, None))
    corr = cov / np.outer(d, d)
    avisos = []
    for i in range(len(param.names)):
        if col[i] == 0:
            avisos.append(tf("AVISO: o parâmetro {nome} não tem efeito no "
                             "ajuste (sensibilidade nula).",
                             nome=param.names[i]))
        for k in range(i + 1, len(param.names)):
            if col[i] > 0 and col[k] > 0 and abs(corr[i, k]) > limit:
                avisos.append(tf(
                    "AVISO: {a} e {b} são fortemente correlacionados "
                    "(rho = {rho:+.3f}).", a=param.names[i],
                    b=param.names[k], rho=corr[i, k]))
    return {"warnings": avisos, "condition_number": cond,
            "correlation": corr.tolist(), "names": list(param.names)}
