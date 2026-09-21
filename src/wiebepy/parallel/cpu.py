# -*- coding: utf-8 -*-
"""
cpu.py — Avaliadores da função objetivo em CPU.

* ``ArrayObjective``           — núcleo xp (NumPy aqui; CuPy em gpu.py),
                                 enxame avaliado em blocos (S_bloco, n)
* ``NumbaObjective``           — kernel njit (prange sobre candidatos), sem
                                 materializar matrizes (S, n)
* ``MultiprocessingObjective`` — divide o enxame entre processos; cada
                                 processo usa o avaliador NumPy

Todos devolvem exatamente a mesma grandeza: acumuladores (S, 6) ->
``objective_from_acc`` (métrica única). O kernel Numba é uma
implementação separada (Numba não opera sobre a camada xp) e é validado
contra o NumPy em tests/test_backends.py.
"""
from __future__ import annotations

import math
from typing import Dict, Optional

import numpy as np

from ..core.core import evaluate_batch
from ..core.parameters import Parametrization
from ..optimization.objective import (FitData, ObjectiveSpec, accumulate,
                                      objective_from_acc)

_DTYPES = {"float64": np.float64, "float32": np.float32}
_ELEMENTOS_POR_BLOCO = 2_000_000       # ~16 MB por matriz float64 (S_b × n)


class BatchObjective:
    """Interface: chamado com X (S, P) numpy, devolve objetivo (S,) numpy."""
    name = "base"

    def __init__(self, data: FitData, param: Parametrization,
                 spec: ObjectiveSpec, precision: str = "float64"):
        if precision not in _DTYPES:
            raise ValueError(f"--precision deve ser um de {sorted(_DTYPES)}.")
        self.data, self.param, self.spec = data, param, spec
        self.precision = precision
        self.dtype = _DTYPES[precision]
        self.n = data.n
        self.sumw = float(np.sum(data.weights)) if data.weights is not None \
            else float(data.n)

    def __call__(self, X: np.ndarray) -> np.ndarray:
        raise NotImplementedError

    def describe(self) -> str:
        return self.name

    def close(self) -> None:
        pass


# =============================================================================
# Núcleo xp (NumPy / CuPy)
# =============================================================================
class ArrayObjective(BatchObjective):
    """Avaliação vetorizada em (S, n) com o núcleo único de core.py."""
    name = "numpy"

    def __init__(self, data, param, spec, precision="float64", xp=np):
        super().__init__(data, param, spec, precision)
        self.xp = xp
        dt = self.dtype
        self.dev = {
            "theta": xp.asarray(data.theta, dtype=dt),
            "xb": None if data.xb is None else xp.asarray(data.xb, dtype=dt),
            "dxb": None if data.dxb is None else xp.asarray(data.dxb, dtype=dt),
            "w": xp.asarray(data.weights if data.weights is not None
                            else np.ones(data.n), dtype=dt),
        }
        self.block = max(1, _ELEMENTOS_POR_BLOCO // max(self.n, 1))

    def accumulators(self, X):
        """X (S, P) -> (acumuladores (S, 6), penalidade (S,)) no device."""
        xp = self.xp
        Xd = xp.asarray(X, dtype=self.dtype)
        params, pen = self.param.decode(Xd, xp)
        S = Xd.shape[0]
        acc = xp.empty((S, 6), dtype=self.dtype)
        for i in range(0, S, self.block):
            sl = slice(i, i + self.block)
            p = {k: v[sl] for k, v in params.items()}
            xb, dxb = evaluate_batch(self.dev["theta"], p, xp,
                                     self.spec.want_x, self.spec.want_d)
            acc[sl] = accumulate(xb, dxb, self.dev, xp)
        return acc, pen

    def __call__(self, X):
        acc, pen = self.accumulators(X)
        J = objective_from_acc(acc.astype(self.xp.float64),
                               pen.astype(self.xp.float64), self.spec,
                               self.n, self.sumw, self.xp)
        return np.asarray(J) if self.xp is np else self.xp.asnumpy(J)


# =============================================================================
# Numba
# =============================================================================
_NUMBA_KERNELS: Dict[str, object] = {}


def numba_available() -> bool:
    try:
        import numba  # noqa: F401
        return True
    except ImportError:
        return False


def _compile_numba():
    """Compila (uma vez por processo) os kernels njit."""
    if _NUMBA_KERNELS:
        return _NUMBA_KERNELS
    from numba import njit, prange

    @njit(parallel=True, cache=True)
    def acc_kernel(theta, xexp, dexp, w, has_x, has_d, beta, theta0, dur,
                   m, a, out):
        S, N = beta.shape
        n = theta.shape[0]
        for s in prange(S):
            sse_x = 0.0; sae_x = 0.0; wsse_x = 0.0
            sse_d = 0.0; sae_d = 0.0; wsse_d = 0.0
            for i in range(n):
                th = theta[i]
                xb = 0.0
                dx = 0.0
                for j in range(N):
                    z = (th - theta0[s, j]) / dur[s, j]
                    if z >= 0.0:
                        zm = z ** m[s, j]
                        e = math.exp(-a[s, j] * (z * zm))
                        xb += beta[s, j] * (1.0 - e)
                        dx += beta[s, j] * (a[s, j] * (m[s, j] + 1.0)
                                            / dur[s, j] * zm * e)
                if xb < 0.0:
                    xb = 0.0
                elif xb > 1.0:
                    xb = 1.0
                if has_x:
                    r = xb - xexp[i]
                    sse_x += r * r; sae_x += abs(r); wsse_x += w[i] * r * r
                if has_d:
                    r = dx - dexp[i]
                    sse_d += r * r; sae_d += abs(r); wsse_d += w[i] * r * r
            out[s, 0] = sse_x; out[s, 1] = sae_x; out[s, 2] = wsse_x
            out[s, 3] = sse_d; out[s, 4] = sae_d; out[s, 5] = wsse_d

    @njit(parallel=True, cache=True)
    def points_kernel(theta, beta, theta0, dur, m, a, xb_out, dx_out):
        n = theta.shape[0]
        N = beta.shape[0]
        for i in prange(n):
            th = theta[i]
            xb = 0.0
            dx = 0.0
            for j in range(N):
                z = (th - theta0[j]) / dur[j]
                if z >= 0.0:
                    zm = z ** m[j]
                    e = math.exp(-a[j] * (z * zm))
                    xb += beta[j] * (1.0 - e)
                    dx += beta[j] * (a[j] * (m[j] + 1.0) / dur[j] * zm * e)
            xb_out[i] = min(max(xb, 0.0), 1.0)
            dx_out[i] = dx

    _NUMBA_KERNELS["acc"] = acc_kernel
    _NUMBA_KERNELS["points"] = points_kernel
    return _NUMBA_KERNELS


def set_numba_threads(workers: Optional[int]) -> None:
    if not workers or not numba_available():
        return
    import numba
    numba.set_num_threads(max(1, min(int(workers),
                                     numba.config.NUMBA_NUM_THREADS)))


def numba_points(theta, stages_arrays: Dict, dtype=np.float64):
    """x_b e dx_b/dθ em n pontos com o kernel Numba (paralelo em θ)."""
    k = _compile_numba()["points"]
    th = np.ascontiguousarray(theta, dtype=dtype)
    arr = {kk: np.ascontiguousarray(v, dtype=dtype)
           for kk, v in stages_arrays.items()}
    xb = np.empty_like(th)
    dx = np.empty_like(th)
    k(th, arr["beta"], arr["theta0"], arr["duration"], arr["m"], arr["a"],
      xb, dx)
    return xb, dx


class NumbaObjective(BatchObjective):
    """Kernel njit: prange sobre candidatos, laço em pontos e estágios."""
    name = "numba"

    def __init__(self, data, param, spec, precision="float64",
                 workers: Optional[int] = None):
        super().__init__(data, param, spec, precision)
        if not numba_available():
            raise RuntimeError("Numba não instalado (pip install numba).")
        self.kernel = _compile_numba()["acc"]
        self.workers = workers
        set_numba_threads(workers)
        dt = self.dtype
        z = np.zeros(1, dtype=dt)
        self.th = np.ascontiguousarray(data.theta, dtype=dt)
        self.xe = z if data.xb is None else np.ascontiguousarray(data.xb, dtype=dt)
        self.de = z if data.dxb is None else np.ascontiguousarray(data.dxb, dtype=dt)
        self.w = np.ascontiguousarray(
            data.weights if data.weights is not None else np.ones(data.n),
            dtype=dt)

    def describe(self) -> str:
        import numba
        return f"numba ({numba.get_num_threads()} threads)"

    def __call__(self, X):
        params, pen = self.param.decode(np.asarray(X, dtype=self.dtype))
        p = {k: np.ascontiguousarray(v) for k, v in params.items()}
        acc = np.empty((X.shape[0], 6), dtype=np.float64)
        self.kernel(self.th, self.xe, self.de, self.w, self.spec.want_x,
                    self.spec.want_d, p["beta"], p["theta0"], p["duration"],
                    p["m"], p["a"], acc)
        return objective_from_acc(acc, pen.astype(np.float64), self.spec,
                                  self.n, self.sumw)


# =============================================================================
# Multiprocessing (enxame dividido entre processos)
# =============================================================================
_WORKER_OBJ: Optional[ArrayObjective] = None


def _mp_init(data, param, spec, precision):
    global _WORKER_OBJ
    _WORKER_OBJ = ArrayObjective(data, param, spec, precision)


def _mp_eval(X):
    return _WORKER_OBJ(X)


class MultiprocessingObjective(BatchObjective):
    """ProcessPoolExecutor (spawn — seguro no Windows) com um avaliador
    NumPy por processo; o enxame é dividido em ``workers`` blocos.
    O pool é criado uma vez e reutilizado em todas as iterações."""
    name = "multiprocessing"

    def __init__(self, data, param, spec, precision="float64",
                 workers: Optional[int] = None):
        super().__init__(data, param, spec, precision)
        import os
        from .procs import spawn_pool
        self.workers = max(1, workers or (os.cpu_count() or 2) - 1)
        self.pool = spawn_pool(self.workers, _mp_init,
                               (data, param, spec, precision))

    def describe(self) -> str:
        return f"multiprocessing ({self.workers} processos, NumPy)"

    def __call__(self, X):
        X = np.asarray(X, dtype=float)
        blocos = [b for b in np.array_split(X, self.workers) if b.shape[0]]
        return np.concatenate(list(self.pool.map(_mp_eval, blocos)))

    def close(self) -> None:
        if self.pool is not None:
            self.pool.shutdown(wait=True, cancel_futures=True)
            self.pool = None
