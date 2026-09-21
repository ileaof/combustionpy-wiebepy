# -*- coding: utf-8 -*-
"""
pso.py — Particle Swarm Optimization com avaliação do enxame EM LOTE.

PSO com fator de inércia (Shi & Eberhart; coeficientes de constrição de
Clerc & Kennedy: w = 0.7298, c1 = c2 = 1.49618):

    v ← w·v + c1·r1·(p_best − x) + c2·r2·(g_best − x)
    x ← x + v                      (recortado nos limites; v zerada na borda)

A função objetivo recebe o enxame inteiro (S, P) e devolve (S,) — é isso
que permite usar NumPy vetorizado, Numba, multiprocessing ou GPU sem mudar
o otimizador. Reprodutível: toda a aleatoriedade vem de
``numpy.random.default_rng(seed)``.

Topologia: "ring" (padrão) — cada partícula segue o melhor de sua
vizinhança em anel (±2 vizinhos), o que retarda a convergência prematura
em problemas multimodais como o ajuste de vários estágios; "global" — todas
seguem o melhor do enxame (converge mais rápido, cai mais em ótimos locais).

Parada: número máximo de iterações ou ``patience`` iterações seguidas sem
melhora relativa maior que ``tol`` no melhor objetivo.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional

import numpy as np


@dataclass
class PSOConfig:
    particles: int = 50
    iterations: int = 500
    inertia: float = 0.7298
    c1: float = 1.49618
    c2: float = 1.49618
    vmax_frac: float = 0.25        # |v| <= vmax_frac · (upper − lower)
    tol: float = 1e-10             # melhora relativa mínima
    patience: int = 100            # iterações sem melhora antes de parar
    topology: str = "ring"         # ring | global
    neighbors: int = 2             # vizinhos de cada lado (ring)
    seed: Optional[int] = None

    def check(self) -> "PSOConfig":
        if self.particles < 2 or self.iterations < 1:
            raise ValueError("PSO exige --population >= 2 e --iterations >= 1.")
        if self.topology not in ("ring", "global"):
            raise ValueError("topology deve ser 'ring' ou 'global'.")
        return self


@dataclass
class PSOResult:
    x: np.ndarray
    fun: float
    history: List[float] = field(default_factory=list)
    iterations: int = 0
    n_evals: int = 0
    stopped_by: str = "iterations"      # iterations | patience | cancel
    elapsed_s: float = 0.0
    pbest: Optional[np.ndarray] = None  # melhores posições de cada partícula
    pbest_f: Optional[np.ndarray] = None


def pso(f_batch: Callable[[np.ndarray], np.ndarray], lower, upper,
        cfg: PSOConfig, x0: Optional[np.ndarray] = None,
        callback: Optional[Callable[[int, float, np.ndarray], bool]] = None
        ) -> PSOResult:
    """Minimiza ``f_batch`` na caixa [lower, upper].

    x0       : ponto inicial opcional (vira a partícula 0)
    callback : callback(iteração, melhor_valor, melhor_x) -> True cancela
    """
    cfg.check()
    t0 = time.perf_counter()
    rng = np.random.default_rng(cfg.seed)
    lo = np.asarray(lower, dtype=float)
    hi = np.asarray(upper, dtype=float)
    span = hi - lo
    S, P = cfg.particles, lo.size
    vmax = cfg.vmax_frac * span

    X = lo + rng.random((S, P)) * span
    if x0 is not None:
        X[0] = np.clip(np.asarray(x0, dtype=float), lo, hi)
    V = (rng.random((S, P)) * 2.0 - 1.0) * vmax * 0.1
    f = np.asarray(f_batch(X), dtype=float)
    n_evals = S
    pbest, fp = X.copy(), f.copy()
    g = int(np.argmin(fp))
    gbest, fg = pbest[g].copy(), float(fp[g])
    history = [fg]
    sem_melhora = 0
    parou = "iterations"
    k = max(1, min(cfg.neighbors, (S - 1) // 2))
    viz = np.stack([(np.arange(S) + d) % S for d in range(-k, k + 1)])

    it = 0
    for it in range(1, cfg.iterations + 1):
        r1 = rng.random((S, P))
        r2 = rng.random((S, P))
        if cfg.topology == "ring":
            guia = pbest[viz[np.argmin(fp[viz], axis=0), np.arange(S)]]
        else:
            guia = gbest
        V = (cfg.inertia * V + cfg.c1 * r1 * (pbest - X)
             + cfg.c2 * r2 * (guia - X))
        np.clip(V, -vmax, vmax, out=V)
        X = X + V
        fora = (X < lo) | (X > hi)
        X = np.clip(X, lo, hi)
        V[fora] = 0.0
        f = np.asarray(f_batch(X), dtype=float)
        n_evals += S
        melhor = f < fp
        pbest[melhor] = X[melhor]
        fp[melhor] = f[melhor]
        g = int(np.argmin(fp))
        if fp[g] < fg - cfg.tol * max(abs(fg), 1e-300):
            sem_melhora = 0
        else:
            sem_melhora += 1
        if fp[g] < fg:
            fg, gbest = float(fp[g]), pbest[g].copy()
        history.append(fg)
        if callback is not None and callback(it, fg, gbest):
            parou = "cancel"
            break
        if sem_melhora >= cfg.patience:
            parou = "patience"
            break
    return PSOResult(x=gbest, fun=fg, history=history, iterations=it,
                     n_evals=n_evals, stopped_by=parou,
                     elapsed_s=time.perf_counter() - t0,
                     pbest=pbest, pbest_f=fp)
