# -*- coding: utf-8 -*-
"""
validation.py — Verificações de estágios e de dados experimentais.
"""
from __future__ import annotations

from typing import List, Optional

import numpy as np

from .parameters import validate_stages  # noqa: F401  (reexportado)


class DataError(ValueError):
    """Dados de entrada inválidos (mensagem amigável ao usuário)."""


def validate_data(theta, xb=None, dxb=None, weights=None,
                  min_points: int = 5) -> List[str]:
    """Avisos (não fatais) sobre os dados; lança DataError se inutilizáveis.

    Exige θ estritamente crescente e finito, ao menos uma série (xb ou
    dxb) e pesos positivos. Avisa se xb sai de [0, 1] ou decresce.
    """
    theta = np.asarray(theta, dtype=float)
    if theta.ndim != 1 or theta.size < min_points:
        raise DataError(f"São necessários ao menos {min_points} pontos de θ.")
    if not np.all(np.isfinite(theta)):
        raise DataError("θ contém valores não finitos.")
    if np.any(np.diff(theta) <= 0):
        raise DataError("θ deve ser estritamente crescente (ordene os dados "
                        "e remova ângulos repetidos).")
    if xb is None and dxb is None:
        raise DataError("Forneça ao menos uma série: xb ou dxb_dtheta.")
    avisos: List[str] = []
    for nome, s in (("xb", xb), ("dxb_dtheta", dxb), ("weight", weights)):
        if s is None:
            continue
        s = np.asarray(s, dtype=float)
        if s.shape != theta.shape:
            raise DataError(f"{nome} tem {s.size} pontos; θ tem {theta.size}.")
        if not np.all(np.isfinite(s)):
            raise DataError(f"{nome} contém valores não finitos.")
    if weights is not None and np.any(np.asarray(weights) <= 0):
        raise DataError("Pesos devem ser positivos.")
    if xb is not None:
        xb = np.asarray(xb, dtype=float)
        if xb.min() < -0.05 or xb.max() > 1.05:
            avisos.append(f"xb fora de [0, 1] (min {xb.min():.3g}, "
                          f"max {xb.max():.3g}) — verifique a normalização.")
        if np.any(np.diff(xb) < -0.02):
            avisos.append("xb decresce em alguns trechos (ruído?) — o modelo "
                          "Wiebe é monotônico.")
    return avisos


def check_n_stages(n: Optional[int]) -> int:
    from .parameters import MAX_STAGES
    if n is None or not 1 <= int(n) <= MAX_STAGES:
        raise ValueError(f"--stages deve estar entre 1 e {MAX_STAGES}.")
    return int(n)
