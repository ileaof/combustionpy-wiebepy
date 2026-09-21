# -*- coding: utf-8 -*-
"""
model.py — Pressão no cilindro com liberação de calor Wiebe de N estágios.

Mesmo modelo 0-D de zona única do Double Wiebe (thermodynamics.py), com
x_b de 1 a 5 estágios (θ em rad):

    dQ/dθ   = Q_total · Σ_j β_j dx_j/dθ                          [kJ/rad]
    h       = 130 V^−0.06 (P·1e−2)^0.8 Tg^−0.4 (Vp + 1.4)^0.8     [W/(m²K)]
    dQw/dθ  = h A_s (Tg − Tw) / (2π rpm/60)                       [J/rad]
    dP/dθ   = 1/V · [(κ−1)(dQ/dθ − dQw/1000) − κ P dV/dθ]         [kPa/rad]
    dTg/dθ  = T1/(P1 V1) · (V dP/dθ + P dV/dθ)                    [K/rad]

Integradores:
* ``simulate`` — REFERÊNCIA: solve_ivp (DOP853, rtol = atol = 1e-9)
  avaliado exatamente nos ângulos experimentais; com N = 2 reproduz o
  Double Wiebe (verificado em tests/test_pressure.py);
* ``batch_rk4`` — RK4 de passo fixo em LOTE (S candidatos), com o laço
  sobre os candidatos em Numba (CPU) ou num kernel CUDA (1 thread por
  candidato); fallback NumPy vetorizado. Mesma semântica de falha:
  RHS não finita ou > 1e12, P ou T ≤ 0 → linha NaN (penalidade).
"""
from __future__ import annotations

import math
from typing import Dict, Optional

import numpy as np

from ..core.parameters import as_stages, stages_to_arrays
from .engine import EngineConfig, volume

_LIMITE = 1.0e12


class ODEFailure(Exception):
    """Integração não física (penalizada na calibração)."""


# =============================================================================
# Referência (solve_ivp)
# =============================================================================
def _dxb(theta: float, p: Dict[str, np.ndarray]) -> float:
    z = (theta - p["theta0"]) / p["duration"]
    ativo = z >= 0.0
    zc = np.where(ativo, z, 0.0)
    zm = zc ** p["m"]
    dx = p["a"] * (p["m"] + 1.0) / p["duration"] * zm * np.exp(-p["a"] * zc * zm)
    return float(np.sum(p["beta"] * np.where(ativo, dx, 0.0)))


def simulate(theta, P1: float, stages, engine: EngineConfig, Rc: Optional[float] = None,
             method: str = "DOP853", rtol: float = 1e-9, atol: float = 1e-9):
    """(P_sim [kPa], Tg [K], Q_wall [J]) nos ângulos ``theta`` [rad].
    Levanta ODEFailure se a integração falhar."""
    from scipy.integrate import solve_ivp
    theta = np.asarray(theta, dtype=float)
    Rc = engine.Rc if Rc is None else float(Rc)
    p = stages_to_arrays(as_stages(stages))
    k, T1, Tw = engine.kappa, engine.T1, engine.Tw
    Qt, fac = engine.Q_total, (engine.Vp + 1.4) ** 0.8
    om2pi = 2.0 * math.pi * engine.omega_rev_s
    V1 = float(volume(theta[0], Rc, engine)[0])
    dTg0 = T1 / (P1 * V1)

    def rhs(th, y):
        P, Tg, _ = y
        V, dV, As = volume(th, Rc, engine)
        dQ = Qt * _dxb(th, p)
        if engine.heat_transfer:
            h = 130.0 * V ** (-0.06) * (P * 1e-2) ** 0.8 * Tg ** (-0.4) * fac
            dQw = h * As * (Tg - Tw) / om2pi
        else:
            dQw = 0.0
        dP = (1.0 / V) * ((k - 1.0) * (dQ - dQw / 1000.0) - k * P * dV)
        out = np.array([dP, dTg0 * (V * dP + P * dV), dQw])
        if not np.all(np.isfinite(out)) or np.max(np.abs(out)) > _LIMITE:
            raise ODEFailure("RHS não física")
        return out

    try:
        with np.errstate(all="ignore"):
            sol = solve_ivp(rhs, (theta[0], theta[-1]), [P1, T1, 0.0],
                            method=method, t_eval=theta, rtol=rtol, atol=atol)
    except (ValueError, FloatingPointError, OverflowError, ODEFailure):
        raise ODEFailure("integração interrompida (RHS não física)") from None
    if (not sol.success or sol.y.shape[1] != theta.size
            or not np.all(np.isfinite(sol.y))):
        raise ODEFailure(f"integração falhou: {sol.message}")
    P, Tg, Qw = sol.y
    if np.any(P <= 0) or np.any(Tg <= 0):
        raise ODEFailure("pressão ou temperatura não positiva")
    return P, Tg, Qw


# =============================================================================
# RK4 em lote — NumPy (fallback; laço em Python sobre os passos)
# =============================================================================
def batch_rk4_numpy(theta, P1: float, Rc, params: Dict, engine: EngineConfig,
                    substeps: int = 4) -> np.ndarray:
    theta = np.asarray(theta, dtype=float)
    Rc = np.asarray(Rc, dtype=float)
    S, n = Rc.shape[0], theta.size
    c = engine.constants()
    col = {k: np.asarray(v, dtype=float) for k, v in params.items()}
    with np.errstate(all="ignore"):              # Rc <= 1 vira NaN abaixo
        V1 = volume(theta[0], Rc, engine)[0]
        dTg0 = c["T1"] / (P1 * V1)

    def rhs(th, P, Tg):
        V, dV, As = volume(th, Rc, engine)
        z = (th - col["theta0"]) / col["duration"]
        ativo = z >= 0.0
        zc = np.where(ativo, z, 0.0)
        zm = zc ** col["m"]
        dx = col["a"] * (col["m"] + 1.0) / col["duration"] * zm * np.exp(
            -col["a"] * zc * zm)
        dQ = c["Qtot"] * np.sum(col["beta"] * np.where(ativo, dx, 0.0), axis=1)
        if c["heat"]:
            h = (130.0 * V ** (-0.06) * (P * 1e-2) ** 0.8 * Tg ** (-0.4)
                 * c["Vp_fac"])
            dQw = h * As * (Tg - c["Tw"]) / c["om2pi"]
        else:
            dQw = np.zeros(S)
        dP = (1.0 / V) * ((c["kappa"] - 1.0) * (dQ - dQw / 1000.0)
                          - c["kappa"] * P * dV)
        return dP, dTg0 * (V * dP + P * dV), dQw

    def ok(k):
        return np.all([np.isfinite(v) & (np.abs(v) <= _LIMITE) for v in k],
                      axis=0)

    vivo = (Rc > 1.0) & np.all(col["duration"] > 0, axis=1)
    P = np.full(S, float(P1))
    Tg = np.full(S, c["T1"])
    out = np.full((S, n), np.nan)
    out[:, 0] = P1
    with np.errstate(all="ignore"):
        for i in range(n - 1):
            a = float(theta[i])
            h = (float(theta[i + 1]) - a) / substeps
            for _ in range(substeps):
                k1 = rhs(a, P, Tg); vivo &= ok(k1)
                k2 = rhs(a + h / 2, P + h / 2 * k1[0], Tg + h / 2 * k1[1]); vivo &= ok(k2)
                k3 = rhs(a + h / 2, P + h / 2 * k2[0], Tg + h / 2 * k2[1]); vivo &= ok(k3)
                k4 = rhs(a + h, P + h * k3[0], Tg + h * k3[1]); vivo &= ok(k4)
                P = np.where(vivo, P + h / 6 * (k1[0] + 2 * k2[0] + 2 * k3[0] + k4[0]), P)
                Tg = np.where(vivo, Tg + h / 6 * (k1[1] + 2 * k2[1] + 2 * k3[1] + k4[1]), Tg)
                vivo &= (P > 0) & (Tg > 0) & np.isfinite(P) & np.isfinite(Tg)
                a += h
            out[:, i + 1] = P
    out[~vivo] = np.nan
    return out


# =============================================================================
# RK4 em lote — Numba (prange sobre candidatos)
# =============================================================================
_NUMBA = {}


def _numba_kernel():
    if "k" in _NUMBA:
        return _NUMBA["k"]
    from numba import njit, prange

    @njit(cache=True, inline="always")
    def rhs(th, P, Tg, Vc, A_cyl, A_head, Vd, R, bore, rod, r_cr, kappa, Tw,
            Qtot, Vp_fac, om2pi, heat, beta, th0, dur, m, a, s, dTg0):
        sn = math.sin(th)
        cs = math.cos(th)
        raiz = math.sqrt(R * R - sn * sn)
        V = Vc + Vd / 2.0 * (R + 1.0 - cs - raiz)
        dV = Vd * sn / 2.0 * (1.0 + cs / raiz)
        y = rod + r_cr - r_cr * cs - math.sqrt(rod * rod - r_cr * r_cr * sn * sn)
        As = A_head + math.pi * bore * y + A_cyl
        dxb = 0.0
        for j in range(beta.shape[1]):
            z = (th - th0[s, j]) / dur[s, j]
            if z >= 0.0:
                zm = z ** m[s, j]
                dxb += beta[s, j] * (a[s, j] * (m[s, j] + 1.0) / dur[s, j]
                                     * zm * math.exp(-a[s, j] * z * zm))
        dQ = Qtot * dxb
        dQw = 0.0
        if heat:
            h = 130.0 * V ** (-0.06) * (P * 1e-2) ** 0.8 * Tg ** (-0.4) * Vp_fac
            dQw = h * As * (Tg - Tw) / om2pi
        dP = (1.0 / V) * ((kappa - 1.0) * (dQ - dQw / 1000.0) - kappa * P * dV)
        return dP, dTg0 * (V * dP + P * dV), dQw

    @njit(cache=True, inline="always")
    def ok3(a, b, c):
        return (a == a and b == b and c == c and abs(a) <= 1e12
                and abs(b) <= 1e12 and abs(c) <= 1e12)

    @njit(parallel=True, cache=True)
    def kernel(theta, P1, Rc, beta, th0, dur, m, a, Vd, R, bore, stroke, rod,
               kappa, T1, Tw, Qtot, Vp_fac, om2pi, heat, substeps, out):
        S = Rc.shape[0]
        n = theta.shape[0]
        r_cr = stroke / 2.0
        A_head = 2.0 * math.pi * (bore / 2.0) ** 2
        for s in prange(S):
            for i in range(n):
                out[s, i] = np.nan
            if Rc[s] <= 1.0:
                continue
            Vc = Vd / (Rc[s] - 1.0)
            A_cyl = math.pi * bore * stroke / (Rc[s] - 1.0)
            t0 = theta[0]
            V1 = Vc + Vd / 2.0 * (R + 1.0 - math.cos(t0)
                                  - math.sqrt(R * R - math.sin(t0) ** 2))
            dTg0 = T1 / (P1 * V1)
            P = P1
            Tg = T1
            out[s, 0] = P
            vivo = True
            for i in range(n - 1):
                ang = theta[i]
                h = (theta[i + 1] - ang) / substeps
                for _ in range(substeps):
                    k1p, k1t, k1w = rhs(ang, P, Tg, Vc, A_cyl, A_head, Vd, R, bore, rod, r_cr, kappa, Tw, Qtot, Vp_fac, om2pi, heat, beta, th0, dur, m, a, s, dTg0)
                    if not ok3(k1p, k1t, k1w):
                        vivo = False
                        break
                    k2p, k2t, k2w = rhs(ang + h / 2, P + h / 2 * k1p, Tg + h / 2 * k1t, Vc, A_cyl, A_head, Vd, R, bore, rod, r_cr, kappa, Tw, Qtot, Vp_fac, om2pi, heat, beta, th0, dur, m, a, s, dTg0)
                    if not ok3(k2p, k2t, k2w):
                        vivo = False
                        break
                    k3p, k3t, k3w = rhs(ang + h / 2, P + h / 2 * k2p, Tg + h / 2 * k2t, Vc, A_cyl, A_head, Vd, R, bore, rod, r_cr, kappa, Tw, Qtot, Vp_fac, om2pi, heat, beta, th0, dur, m, a, s, dTg0)
                    if not ok3(k3p, k3t, k3w):
                        vivo = False
                        break
                    k4p, k4t, k4w = rhs(ang + h, P + h * k3p, Tg + h * k3t, Vc, A_cyl, A_head, Vd, R, bore, rod, r_cr, kappa, Tw, Qtot, Vp_fac, om2pi, heat, beta, th0, dur, m, a, s, dTg0)
                    if not ok3(k4p, k4t, k4w):
                        vivo = False
                        break
                    P = P + h / 6.0 * (k1p + 2.0 * k2p + 2.0 * k3p + k4p)
                    Tg = Tg + h / 6.0 * (k1t + 2.0 * k2t + 2.0 * k3t + k4t)
                    ang = ang + h
                    if not (P > 0.0 and Tg > 0.0 and P == P and Tg == Tg):
                        vivo = False
                        break
                if not vivo:
                    for q in range(n):
                        out[s, q] = np.nan
                    break
                out[s, i + 1] = P

    _NUMBA["k"] = kernel
    return kernel


def batch_rk4_numba(theta, P1, Rc, params, engine: EngineConfig,
                    substeps: int = 4) -> np.ndarray:
    k = _numba_kernel()
    c = engine.constants()
    th = np.ascontiguousarray(theta, dtype=np.float64)
    Rc = np.ascontiguousarray(Rc, dtype=np.float64)
    arr = {kk: np.ascontiguousarray(v, dtype=np.float64) for kk, v in params.items()}
    out = np.empty((Rc.shape[0], th.size))
    k(th, float(P1), Rc, arr["beta"], arr["theta0"], arr["duration"], arr["m"],
      arr["a"], c["Vd"], c["R"], c["bore"], c["stroke"], c["rod"], c["kappa"],
      c["T1"], c["Tw"], c["Qtot"], c["Vp_fac"], c["om2pi"], c["heat"],
      int(substeps), out)
    return out


# =============================================================================
# RK4 em lote — CUDA (CuPy RawKernel, 1 thread por candidato)
# =============================================================================
_CUDA_SRC = r"""
#define RL(x) ((real)(x))
#define PI RL(3.141592653589793)
__device__ __forceinline__ bool ok3(real a, real b, real c) {
    const real L = RL(1.0e12);
    return isfinite(a) && isfinite(b) && isfinite(c) && fabs(a) <= L
        && fabs(b) <= L && fabs(c) <= L;
}
__device__ __forceinline__ void rhs(real th, real P, real Tg, real Vc,
        real A_cyl, real A_head, real Vd, real R, real bore, real rod,
        real r_cr, real kappa, real Tw, real Qtot, real Vp_fac, real om2pi,
        int heat, const real* bt, const real* t0, const real* du,
        const real* mm, const real* aa, int N, real dTg0,
        real* dP, real* dT, real* dW) {
    const real sn = sin(th), cs = cos(th);
    const real raiz = sqrt(R * R - sn * sn);
    const real V = Vc + Vd / RL(2.0) * (R + RL(1.0) - cs - raiz);
    const real dV = Vd * sn / RL(2.0) * (RL(1.0) + cs / raiz);
    const real y = rod + r_cr - r_cr * cs - sqrt(rod * rod - r_cr * r_cr * sn * sn);
    const real As = A_head + PI * bore * y + A_cyl;
    real dxb = RL(0.0);
    for (int j = 0; j < N; ++j) {
        const real z = (th - t0[j]) / du[j];
        if (z >= RL(0.0)) {
            const real zm = pow(z, mm[j]);
            dxb += bt[j] * (aa[j] * (mm[j] + RL(1.0)) / du[j] * zm
                            * exp(-aa[j] * z * zm));
        }
    }
    const real dQ = Qtot * dxb;
    real qw = RL(0.0);
    if (heat) {
        const real h = RL(130.0) * pow(V, RL(-0.06)) * pow(P * RL(1.0e-2), RL(0.8))
            * pow(Tg, RL(-0.4)) * Vp_fac;
        qw = h * As * (Tg - Tw) / om2pi;
    }
    *dP = (RL(1.0) / V) * ((kappa - RL(1.0)) * (dQ - qw / RL(1000.0)) - kappa * P * dV);
    *dT = dTg0 * (V * *dP + P * dV);
    *dW = qw;
}
extern "C" __global__ void rk4_pressure(const double* theta, const real P1,
        const real* Rc, const real* beta, const real* th0, const real* dur,
        const real* m, const real* a, const int S, const int N, const int n,
        const real Vd, const real R, const real bore, const real stroke,
        const real rod, const real kappa, const real T1, const real Tw,
        const real Qtot, const real Vp_fac, const real om2pi, const int heat,
        const int substeps, double* out) {
    const int s = blockDim.x * blockIdx.x + threadIdx.x;
    if (s >= S) return;
    double* row = out + (size_t)s * n;
    const real rc = Rc[s];
    if (!(rc > RL(1.0))) return;
    const real *bt = beta + s * N, *t0 = th0 + s * N, *du = dur + s * N,
               *mm = m + s * N, *aa = a + s * N;
    const real r_cr = stroke / RL(2.0);
    const real A_head = RL(2.0) * PI * (bore / RL(2.0)) * (bore / RL(2.0));
    const real Vc = Vd / (rc - RL(1.0));
    const real A_cyl = PI * bore * stroke / (rc - RL(1.0));
    const real ti = (real)theta[0];
    const real V1 = Vc + Vd / RL(2.0) * (R + RL(1.0) - cos(ti) - sqrt(R * R - sin(ti) * sin(ti)));
    const real dTg0 = T1 / (P1 * V1);
    real P = P1, Tg = T1;
    for (int i = 0; i < n - 1; ++i) {
        real ang = (real)theta[i];
        const real h = ((real)theta[i + 1] - ang) / (real)substeps;
        const real h2 = h / RL(2.0);
        for (int q = 0; q < substeps; ++q) {
            real a1, b1, c1, a2, b2, c2, a3, b3, c3, a4, b4, c4;
            rhs(ang, P, Tg, Vc, A_cyl, A_head, Vd, R, bore, rod, r_cr, kappa, Tw, Qtot, Vp_fac, om2pi, heat, bt, t0, du, mm, aa, N, dTg0, &a1, &b1, &c1);
            if (!ok3(a1, b1, c1)) return;
            rhs(ang + h2, P + h2 * a1, Tg + h2 * b1, Vc, A_cyl, A_head, Vd, R, bore, rod, r_cr, kappa, Tw, Qtot, Vp_fac, om2pi, heat, bt, t0, du, mm, aa, N, dTg0, &a2, &b2, &c2);
            if (!ok3(a2, b2, c2)) return;
            rhs(ang + h2, P + h2 * a2, Tg + h2 * b2, Vc, A_cyl, A_head, Vd, R, bore, rod, r_cr, kappa, Tw, Qtot, Vp_fac, om2pi, heat, bt, t0, du, mm, aa, N, dTg0, &a3, &b3, &c3);
            if (!ok3(a3, b3, c3)) return;
            rhs(ang + h, P + h * a3, Tg + h * b3, Vc, A_cyl, A_head, Vd, R, bore, rod, r_cr, kappa, Tw, Qtot, Vp_fac, om2pi, heat, bt, t0, du, mm, aa, N, dTg0, &a4, &b4, &c4);
            if (!ok3(a4, b4, c4)) return;
            P = P + h / RL(6.0) * (a1 + RL(2.0) * a2 + RL(2.0) * a3 + a4);
            Tg = Tg + h / RL(6.0) * (b1 + RL(2.0) * b2 + RL(2.0) * b3 + b4);
            ang = ang + h;
            if (!(P > RL(0.0)) || !(Tg > RL(0.0)) || !isfinite(P) || !isfinite(Tg)) return;
        }
        if (i == 0) row[0] = (double)P1;
        row[i + 1] = (double)P;
    }
}
"""
_CUDA = {}


def _cuda_kernel(precision: str):
    if precision not in _CUDA:
        import cupy as cp
        tipo = "double" if precision == "float64" else "float"
        _CUDA[precision] = cp.RawKernel(f"typedef {tipo} real;\n" + _CUDA_SRC,
                                        "rk4_pressure", options=("-fmad=false",))
    return _CUDA[precision]


def batch_rk4_cuda_device(theta_d, P1, Rc, params, engine: EngineConfig,
                          substeps: int = 4, precision: str = "float64"):
    """Como batch_rk4, mas devolve cupy (S, n) float64 na GPU. Linha com
    NaN = candidato falho (o kernel só escreve linhas bem-sucedidas)."""
    import cupy as cp
    dt = np.float64 if precision == "float64" else np.float32
    c = engine.constants()
    Rc = np.ascontiguousarray(Rc, dtype=dt)
    S, N = params["beta"].shape
    n = int(theta_d.size)
    out = cp.full((S, n), cp.nan, dtype=cp.float64)
    arr = [cp.asarray(np.ascontiguousarray(params[k], dtype=dt))
           for k in ("beta", "theta0", "duration", "m", "a")]
    args = (theta_d, dt(P1), cp.asarray(Rc), *arr, np.int32(S), np.int32(N),
            np.int32(n), *(dt(c[k]) for k in ("Vd", "R", "bore", "stroke",
                                               "rod", "kappa", "T1", "Tw",
                                               "Qtot", "Vp_fac", "om2pi")),
            np.int32(c["heat"]), np.int32(substeps), out)
    _cuda_kernel(precision)(((S + 127) // 128,), (128,), args)
    # linhas incompletas (falha no meio) ficam com NaN na cauda
    return out


def batch_rk4(theta, P1, Rc, params, engine: EngineConfig, substeps: int = 4,
              backend: str = "numba", precision: str = "float64") -> np.ndarray:
    """P_sim (S, n) [kPa] para S candidatos; NaN = candidato falho."""
    if backend == "numba":
        return batch_rk4_numba(theta, P1, Rc, params, engine, substeps)
    if backend == "cupy":
        import cupy as cp
        out = batch_rk4_cuda_device(cp.asarray(np.asarray(theta, float)), P1,
                                    Rc, params, engine, substeps, precision)
        out = cp.asnumpy(out)
        out[np.isnan(out).any(axis=1)] = np.nan
        return out
    return batch_rk4_numpy(theta, P1, Rc, params, engine, substeps)
