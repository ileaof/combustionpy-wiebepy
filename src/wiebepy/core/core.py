# -*- coding: utf-8 -*-
"""
core.py — Função multistage-Wiebe generalizada (N = 1..5), vetorizada.

    z_j(θ) = (θ − θ0_j) / Δθ_j
    x_j(θ) = 1 − exp(−a_j z_j^(m_j+1))            (θ ≥ θ0_j; 0 antes)
    x_b(θ) = Σ_j β_j x_j(θ)

Escrito UMA vez para NumPy e CuPy: toda função recebe/infere ``xp``
(o módulo de arrays). O número de estágios só determina o tamanho dos
arrays — não há ramos por N.

Garantias: com β_j ≥ 0, Σβ_j = 1, Δθ_j > 0 e m_j > 0, cada x_j é monotônica
não decrescente em [0, 1), logo x_b também; o resultado é recortado em
[0, 1] apenas para eliminar ruído de ponto flutuante.
"""
from __future__ import annotations

from typing import Dict, Iterable, Tuple

import numpy as np

from .parameters import stages_to_arrays


def get_xp(*arrays):
    """numpy ou cupy, conforme o tipo dos arrays (cupy só se instalado)."""
    try:
        import cupy
        return cupy.get_array_module(*arrays)
    except ImportError:
        return np


def stage_terms(theta, theta0, duration, m, a, xp=np, want_x=True,
                want_dx=True):
    """x_j e dx_j/dθ de estágios com broadcasting.

    ``theta`` e os parâmetros são broadcastáveis entre si — ex.: theta
    (1, n) com parâmetros (S, 1) produz (S, n). Retorna (x, dx) (qualquer
    um pode ser None se não solicitado).
    """
    z = (theta - theta0) / duration
    ativo = z >= 0.0
    zc = xp.where(ativo, z, 0.0)
    zm = zc ** m                                   # z^m (m > 0: 0^m = 0)
    e = xp.exp(-a * (zc * zm))                     # exp(−a z^(m+1))
    x = xp.where(ativo, 1.0 - e, 0.0) if want_x else None
    dx = (xp.where(ativo, a * (m + 1.0) / duration * zm * e, 0.0)
          if want_dx else None)
    return x, dx


def _arrays(stages, xp, dtype):
    arr = stages if isinstance(stages, dict) else stages_to_arrays(stages)
    return {k: xp.asarray(v, dtype=dtype) for k, v in arr.items()}


def multistage_wiebe(theta, stages, xp=None) -> "np.ndarray":
    """Fração de massa queimada x_b(θ) para 1..5 estágios.

    theta  : array (n,) de ângulos (qualquer unidade, a mesma dos
             parâmetros θ0 e Δθ)
    stages : lista de dicts/Stage com beta, theta0, duration, m, a — ou
             dict de arrays (N,)
    xp     : numpy ou cupy (inferido de theta se omitido)
    """
    return stage_contributions(theta, stages, xp, want_dx=False)[0].sum(
        axis=0).clip(0.0, 1.0)


def stage_contributions(theta, stages, xp=None, want_x=True, want_dx=True):
    """Contribuições individuais β_j x_j e β_j dx_j/dθ, shape (N, n)."""
    xp = xp or get_xp(theta)
    th = xp.asarray(theta, dtype=float)
    p = _arrays(stages, xp, th.dtype)
    col = {k: v[:, None] for k, v in p.items()}
    x, dx = stage_terms(th[None, :], col["theta0"], col["duration"],
                        col["m"], col["a"], xp, want_x, want_dx)
    return (col["beta"] * x if want_x else None,
            col["beta"] * dx if want_dx else None)


def evaluate_batch(theta, params: Dict, xp=np, want_x=True,
                   want_dx=True) -> Tuple:
    """Avalia S candidatos de uma vez.

    theta  : (n,)   params : dict de arrays (S, N)
    Retorna (xb, dxb), cada um (S, n) ou None. Laço apenas sobre os N ≤ 5
    estágios; o trabalho pesado é vetorizado em (S, n).
    """
    S, N = params["beta"].shape
    th = theta[None, :]
    xb = xp.zeros((S, theta.shape[0]), dtype=theta.dtype) if want_x else None
    dxb = xp.zeros_like(xb) if (want_dx and want_x) else (
        xp.zeros((S, theta.shape[0]), dtype=theta.dtype) if want_dx else None)
    for j in range(N):
        x, dx = stage_terms(th, params["theta0"][:, j:j + 1],
                            params["duration"][:, j:j + 1],
                            params["m"][:, j:j + 1], params["a"][:, j:j + 1],
                            xp, want_x, want_dx)
        b = params["beta"][:, j:j + 1]
        if want_x:
            xb += b * x
        if want_dx:
            dxb += b * dx
    if want_x:
        xp.clip(xb, 0.0, 1.0, out=xb)
    return xb, dxb
