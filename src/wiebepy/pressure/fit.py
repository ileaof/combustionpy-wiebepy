# -*- coding: utf-8 -*-
"""
fit.py — Ajuste da curva de PRESSÃO com liberação de calor de N estágios.

Como no Double Wiebe: o objetivo é o RMSE entre a pressão simulada pelo
modelo 0-D e a medida; os parâmetros são os dos N estágios (e Rc, por
padrão). Com N = 2 o problema é o do Double Wiebe.

Cada run:
1. PSO (topologia em anel) com o enxame integrado EM LOTE por RK4 de passo
   fixo (Numba, CUDA ou NumPy);
2. refinamento por mínimos quadrados (TRF) a partir dos melhores pontos
   distintos do enxame, com o jacobiano em lote (RK4 float64);
3. REVALIDAÇÃO com a referência solve_ivp (DOP853, 1e-9) — é esse o RMSE
   relatado. Se a referência falhar no melhor candidato (fronteira de
   falha do passo adaptativo), testa-se o próximo melhor; o fato é
   registrado nos avisos.

Ângulos em rad (θ = 0 no PMS de combustão); pressão em kPa.
"""
from __future__ import annotations

import logging
import math
import time
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence

import numpy as np

from ..core.parameters import (A_DEFAULT, PENALTY, Parametrization, Stage,
                               StageBounds)
from ..optimization.identifiability import (bound_warnings,
                                            dispersion_warnings,
                                            stage_warnings)
from ..optimization.pso import PSOConfig, pso
from .engine import EngineConfig
from .model import ODEFailure, batch_rk4, simulate

log = logging.getLogger("wiebepy")

PRESSURE_FACTORS_KPA = {"bar": 100.0, "kPa": 1.0, "MPa": 1000.0, "Pa": 1e-3}
GRAU = math.pi / 180.0


# =============================================================================
# Dados
# =============================================================================
@dataclass
class PressureData:
    theta: np.ndarray          # rad
    P: np.ndarray              # kPa
    source: str = ""
    warnings: list = field(default_factory=list)

    def __post_init__(self):
        self.theta = np.ascontiguousarray(self.theta, dtype=float)
        self.P = np.ascontiguousarray(self.P, dtype=float)
        if self.theta.size < 20 or self.theta.shape != self.P.shape:
            raise ValueError("São necessários ≥ 20 pares (θ, P).")
        if np.any(np.diff(self.theta) <= 0):
            raise ValueError("θ deve ser estritamente crescente.")
        if not np.all(np.isfinite(self.P)) or np.any(self.P <= 0):
            raise ValueError("Pressões devem ser finitas e positivas.")
        faixa = np.degrees(np.ptp(self.theta))
        self.warnings = []
        if faixa < 20:
            self.warnings.append(
                f"θ cobre só {faixa:.2f}° — confira a unidade angular (o "
                "arquivo pode estar em radianos).")
        if self.P.max() < 5 * self.P.min() and self.P.max() < 500:
            self.warnings.append("Pressão com pouca variação/valores baixos — "
                                 "confira a unidade (bar, kPa, MPa, Pa).")

    @property
    def n(self) -> int:
        return int(self.theta.size)

    def subset(self, mask) -> "PressureData":
        return PressureData(self.theta[mask], self.P[mask], self.source)


def read_pressure(path, angle_unit: str = "rad", pressure_unit: str = "bar",
                  theta_min: Optional[float] = -2.0,
                  theta_max: Optional[float] = 2.0) -> PressureData:
    """Arquivo θ, P (2 colunas; cabeçalho opcional; separador detectado).
    theta_min/theta_max em rad, aplicados após a conversão."""
    from ..io.readers import _parse_table
    p = Path(path)
    cols = _parse_table(p.read_text(encoding="utf-8-sig"), p.name)
    serie = next((cols[k] for k in ("xb", "dxb") if k in cols), None)
    if "theta" not in cols or serie is None:
        chaves = list(cols)
        if len(chaves) >= 2:
            serie = cols[chaves[1]]
        else:
            raise ValueError(f"{p.name}: são necessárias as colunas θ e P.")
    return pressure_from_arrays(cols.get("theta", cols[list(cols)[0]]), serie,
                                angle_unit, pressure_unit, theta_min,
                                theta_max, p.name)


def pressure_from_arrays(theta, P, angle_unit="rad", pressure_unit="bar",
                         theta_min: Optional[float] = -2.0,
                         theta_max: Optional[float] = 2.0,
                         source: str = "") -> PressureData:
    if pressure_unit not in PRESSURE_FACTORS_KPA:
        raise ValueError(f"Unidade de pressão: {list(PRESSURE_FACTORS_KPA)}.")
    th = np.asarray(theta, float) * (1.0 if angle_unit == "rad" else GRAU)
    Pk = np.asarray(P, float) * PRESSURE_FACTORS_KPA[pressure_unit]
    ordem = np.argsort(th, kind="stable")
    th, Pk = th[ordem], Pk[ordem]
    m = np.ones(th.size, bool)
    if theta_min is not None:
        m &= th >= theta_min
    if theta_max is not None:
        m &= th <= theta_max
    return PressureData(th[m], Pk[m], source)


# =============================================================================
# Configuração e parametrização
# =============================================================================
DEFAULT_BOUNDS_DEG = {
    "theta0": (-30.0, 10.0),      # início do 1º estágio [°]
    "dtheta0": (0.0, 40.0),       # incremento entre inícios [°]
    "duration": (2.0, 90.0),      # [°]
    "theta0_max": 40.0,           # último início [°]
}


@dataclass
class PressureSettings:
    n_stages: int = 2
    engine: EngineConfig = field(default_factory=EngineConfig)
    fit_rc: bool = True
    rc_bounds: tuple = (14.0, 20.0)
    beta_mode: str = "stick"
    fit_a: bool = False
    a_fixed: float = 6.9078
    m_bounds: tuple = (0.05, 3.0)
    bounds_deg: Dict = field(default_factory=lambda: dict(DEFAULT_BOUNDS_DEG))
    particles: int = 60
    iterations: int = 400
    patience: int = 100
    topology: str = "ring"
    runs: int = 3
    seed: Optional[int] = 42
    backend: str = "auto"          # auto | numba | cupy | numpy
    precision: str = "float64"
    workers: Optional[int] = None
    substeps: int = 4
    polish: bool = True
    polish_starts: int = 3

    def to_dict(self) -> Dict:
        d = asdict(self)
        d["engine"] = self.engine.to_dict()
        return d


class PressureParam:
    """Vetor de busca = [Rc?] + vetor de estágios (Parametrization, rad)."""

    def __init__(self, s: PressureSettings):
        b = s.bounds_deg
        sb = StageBounds(theta0=tuple(v * GRAU for v in b["theta0"]),
                         dtheta0=tuple(v * GRAU for v in b["dtheta0"]),
                         duration=tuple(v * GRAU for v in b["duration"]),
                         m=tuple(s.m_bounds),
                         theta0_max=b.get("theta0_max", 40.0) * GRAU)
        self.stages = Parametrization(s.n_stages, sb, s.beta_mode, s.fit_a,
                                      s.a_fixed)
        self.fit_rc = s.fit_rc
        self.rc_fixo = s.engine.Rc
        pre = ["Rc"] if s.fit_rc else []
        self.names = pre + list(self.stages.names)
        self.lower = np.concatenate([[s.rc_bounds[0]] if s.fit_rc else [],
                                     self.stages.lower])
        self.upper = np.concatenate([[s.rc_bounds[1]] if s.fit_rc else [],
                                     self.stages.upper])
        self.n_stages = s.n_stages

    @property
    def size(self) -> int:
        return len(self.names)

    def split(self, X):
        X = np.atleast_2d(X)
        if self.fit_rc:
            return X[:, 0], X[:, 1:]
        return np.full(X.shape[0], self.rc_fixo), X

    def decode(self, X):
        Rc, Xs = self.split(X)
        params, pen = self.stages.decode(Xs)
        return Rc, params, pen

    def to_model(self, x):
        Rc, Xs = self.split(np.asarray(x, float)[None, :])
        return float(Rc[0]), self.stages.to_stages(Xs[0])

    def encode(self, Rc, stages):
        v = self.stages.encode(stages)
        return np.concatenate([[Rc], v]) if self.fit_rc else v


# =============================================================================
# Avaliação
# =============================================================================
def _resolver_backend(nome: str) -> str:
    from ..parallel.cpu import numba_available
    from ..parallel.gpu import cupy_available
    if nome == "auto":
        return "numba" if numba_available() else ("cupy" if cupy_available()
                                                  else "numpy")
    if nome == "numba" and not numba_available():
        log.warning("WARNING: numba indisponível; usando numpy.")
        return "numpy"
    if nome == "cupy" and not cupy_available():
        log.warning("WARNING: CuPy/GPU indisponível; usando %s.",
                    "numba" if numba_available() else "numpy")
        return "numba" if numba_available() else "numpy"
    return nome


class PressureObjective:
    """RMSE de pressão (S,) para o enxame X (S, P); ``mask`` restringe os
    pontos usados (validação cruzada)."""

    def __init__(self, data: PressureData, param: PressureParam,
                 s: PressureSettings, mask: Optional[np.ndarray] = None,
                 backend: Optional[str] = None, precision: Optional[str] = None):
        self.data, self.param, self.s = data, param, s
        self.mask = np.ones(data.n, bool) if mask is None else np.asarray(mask)
        self.backend = backend or _resolver_backend(s.backend)
        self.precision = precision or s.precision
        if self.backend == "numba" and s.workers:
            from ..parallel.cpu import set_numba_threads
            set_numba_threads(s.workers)

    def pressures(self, X, backend=None, precision=None):
        Rc, params, pen = self.param.decode(np.asarray(X, float))
        P = batch_rk4(self.data.theta, float(self.data.P[0]), Rc, params,
                      self.s.engine, self.s.substeps, backend or self.backend,
                      precision or self.precision)
        return P, pen

    def __call__(self, X):
        P, pen = self.pressures(X)
        r = P[:, self.mask] - self.data.P[self.mask][None, :]
        J = np.sqrt(np.mean(r * r, axis=1)) + pen
        return np.where(np.isfinite(J), J, PENALTY)


def reference_rmse(data: PressureData, param: PressureParam, x,
                   mask: Optional[np.ndarray], engine: EngineConfig) -> float:
    """RMSE com a referência solve_ivp (PENALTY se a integração falhar)."""
    Rc, stages = param.to_model(x)
    try:
        P, _, _ = simulate(data.theta, float(data.P[0]), stages,
                           engine, Rc)
    except ODEFailure:
        return float(PENALTY)
    m = np.ones(data.n, bool) if mask is None else mask
    return float(np.sqrt(np.mean((P[m] - data.P[m]) ** 2)))


# =============================================================================
# Um run
# =============================================================================
@dataclass
class PressureRun:
    run: int
    seed: Optional[int]
    x: np.ndarray
    rmse: float                    # referência solve_ivp
    rmse_rk4: float
    history: List[float]
    iterations: int
    stopped_by: str
    elapsed_s: float
    note: str = ""

    def to_dict(self):
        d = asdict(self)
        d["x"] = self.x.tolist()
        return d


def _inicios(r, param: PressureParam, k: int) -> List[np.ndarray]:
    span = np.maximum(param.upper - param.lower, 1e-300)
    out: List[np.ndarray] = []
    for i in np.argsort(r.pbest_f):
        c = r.pbest[i]
        if all(np.max(np.abs(c - o) / span) > 0.02 for o in out):
            out.append(c)
        if len(out) >= k:
            break
    return out


def _refinar(obj: PressureObjective, x0, param: PressureParam):
    """Mínimos quadrados (TRF) com resíduos e jacobiano em lote (RK4 f64)."""
    from scipy.optimize import least_squares
    lo, hi = param.lower, param.upper
    h = 1e-7 * np.maximum(hi - lo, 1e-12)
    m = obj.mask
    back = obj.backend if obj.backend != "cupy" else (
        "numba" if _resolver_backend("numba") == "numba" else "numpy")

    def R(X):
        P, pen = obj.pressures(X, back, "float64")
        r = P[:, m] - obj.data.P[m][None, :]
        r = np.where(np.isfinite(r), r, 1e5)
        return np.concatenate([r, np.sqrt(m.sum() * pen)[:, None]], axis=1)

    def jac(v):
        X = np.repeat(v[None, :], v.size + 1, axis=0)
        passo = np.where(v + h <= hi, h, -h)
        X[np.arange(1, v.size + 1), np.arange(v.size)] += passo
        M = R(X)
        return ((M[1:] - M[0]) / passo[:, None]).T

    r = least_squares(lambda v: R(v[None, :])[0], np.clip(x0, lo, hi),
                      jac=jac, bounds=(lo, hi), method="trf", x_scale="jac",
                      max_nfev=100)
    return np.clip(r.x, lo, hi)


def single_run(obj: PressureObjective, param: PressureParam,
               s: PressureSettings, run: int, seed: Optional[int],
               callback=None, x0=None) -> PressureRun:
    t0 = time.perf_counter()
    r = pso(obj, param.lower, param.upper,
            PSOConfig(particles=s.particles, iterations=s.iterations,
                      patience=s.patience, topology=s.topology, seed=seed),
            x0=x0, callback=callback)
    candidatos = [r.x]
    if s.polish and r.stopped_by != "cancel":
        for xi in _inicios(r, param, s.polish_starts):
            try:
                candidatos.append(_refinar(obj, xi, param))
            except Exception as e:                    # noqa: BLE001
                log.debug("refinamento falhou: %s", e)
    rk4 = obj(np.array(candidatos))
    ordem = np.argsort(rk4)
    nota = ""
    melhor_x, melhor_ref = candidatos[int(ordem[0])], float(PENALTY)
    for i in ordem:                                   # revalidação solve_ivp
        ref = reference_rmse(obj.data, param, candidatos[int(i)], obj.mask,
                             s.engine)
        if ref < PENALTY:
            melhor_x, melhor_ref = candidatos[int(i)], ref
            if i != ordem[0]:
                nota = ("a referência solve_ivp falhou no melhor candidato do "
                        "RK4; usado o próximo que valida")
            break
    return PressureRun(run=run, seed=seed, x=melhor_x, rmse=melhor_ref,
                       rmse_rk4=float(obj(melhor_x[None, :])[0]),
                       history=r.history, iterations=r.iterations,
                       stopped_by=r.stopped_by,
                       elapsed_s=time.perf_counter() - t0, note=nota)


# =============================================================================
# Ajuste completo
# =============================================================================
@dataclass
class PressureFitResult:
    settings: PressureSettings
    param: PressureParam
    runs: List[PressureRun]
    best: PressureRun
    Rc: float
    stages: List[Stage]
    P_sim: np.ndarray
    Tg: np.ndarray
    metrics: Dict
    objective_stats: Dict
    warnings: List[str]
    backend: str
    elapsed_s: float
    Q_wall: Optional[np.ndarray] = None      # calor perdido acumulado [J]

    def to_dict(self) -> Dict:
        return {"mode": "pressure", "n_stages": self.settings.n_stages,
                "settings": self.settings.to_dict(), "Rc": self.Rc,
                "stages_rad": [s.to_dict() for s in self.stages],
                "stages_deg": [dict(s.to_dict(), theta0=math.degrees(s.theta0),
                                    duration=math.degrees(s.duration))
                               for s in self.stages],
                "parameter_names": self.param.names,
                "metrics": self.metrics, "objective_stats": self.objective_stats,
                "runs": [r.to_dict() for r in self.runs],
                "warnings": self.warnings, "backend": self.backend,
                "elapsed_s": self.elapsed_s}


def pressure_metrics(P_exp, P_sim, k: int) -> Dict:
    from ..optimization.objective import fit_metrics
    m = fit_metrics(P_exp, P_sim, k)
    m["max_abs_err"] = float(np.max(np.abs(P_sim - P_exp)))
    i = int(np.argmax(P_sim))
    m["P_max_sim_kPa"] = float(P_sim[i])
    m["P_max_exp_kPa"] = float(np.max(P_exp))
    return m


def fit_pressure(data: PressureData, s: PressureSettings,
                 progress: Optional[Callable] = None) -> PressureFitResult:
    """Ajusta N estágios à curva de pressão (``s.runs`` runs)."""
    t0 = time.perf_counter()
    param = PressureParam(s)
    obj = PressureObjective(data, param, s)
    log.info("Execution backend : %s (%s)", obj.backend, obj.precision)
    runs: List[PressureRun] = []
    for i in range(s.runs):
        seed = None if s.seed is None else s.seed + i
        cb = None
        if progress is not None:
            def cb(it, fb, xb, _i=i):
                return progress(_i, it, fb, xb)
        runs.append(single_run(obj, param, s, i, seed, cb))
        log.info("Run %02d/%02d  RMSE = %.4f kPa (RK4 %.4f)  %.1f s%s", i + 1,
                 s.runs, runs[-1].rmse, runs[-1].rmse_rk4, runs[-1].elapsed_s,
                 f"  [{runs[-1].note}]" if runs[-1].note else "")
    return summarize_pressure(data, s, param, runs, obj.backend,
                              time.perf_counter() - t0)


def summarize_pressure(data, s, param, runs, backend, elapsed) -> PressureFitResult:
    vals = np.array([r.rmse for r in runs])
    best = runs[int(np.argmin(vals))]
    Rc, stages = param.to_model(best.x)
    avisos = []
    try:
        P_sim, Tg, Qw = simulate(data.theta, float(data.P[0]), stages,
                                 s.engine, Rc)
    except ODEFailure:
        P_sim = Tg = Qw = np.full(data.n, np.nan)
        avisos.append("WARNING: a referência solve_ivp falhou em todos os runs; "
                      "resultado inválido.")
    metrics = pressure_metrics(data.P, P_sim, param.size) if np.all(
        np.isfinite(P_sim)) else {}
    validos = vals[vals < PENALTY]
    ostats = {"best": float(vals.min()),
              "mean": float(validos.mean()) if validos.size else float("nan"),
              "std": float(validos.std(ddof=1)) if validos.size > 1 else 0.0,
              "median": float(np.median(vals)), "worst": float(vals.max()),
              "runs": int(vals.size)}
    avisos += [f"WARNING: run {r.run + 1}: {r.note}." for r in runs if r.note]
    avisos += stage_warnings(stages, float(np.ptp(data.theta)))
    avisos += bound_warnings(best.x, param)
    avisos += dispersion_warnings(np.array([r.x for r in runs]), param)
    return PressureFitResult(settings=s, param=param, runs=runs, best=best,
                             Rc=Rc, stages=stages, P_sim=P_sim, Tg=Tg,
                             Q_wall=Qw,
                             metrics=metrics, objective_stats=ostats,
                             warnings=avisos, backend=backend,
                             elapsed_s=elapsed)


# =============================================================================
# Comparação 1..5 (mesmos critérios do modo x_b)
# =============================================================================
def compare_pressure(data: PressureData, ns: Sequence[int],
                     base: PressureSettings, cv_folds: int = 5,
                     cv_tol: float = 0.05, progress=None) -> Dict:
    from ..optimization.compare import block_folds, recommend
    ns = sorted(set(int(n) for n in ns))
    res: Dict[int, PressureFitResult] = {}
    tempos = {}
    for N in ns:
        log.info("=== Modelo %d-Wiebe (pressão) ===", N)
        t0 = time.perf_counter()
        cb = None
        if progress is not None:
            def cb(run, it, fb, xb, _N=N):
                return progress("fit", _N, it, fb)
        res[N] = fit_pressure(data, replace(base, n_stages=N), cb)
        tempos[N] = time.perf_counter() - t0
    # refinamento aninhado: N+1 sem um estágio -> candidato para N
    for N in sorted(ns, reverse=True):
        if N + 1 not in res:
            continue
        s = replace(base, n_stages=N)
        param = PressureParam(s)
        obj = PressureObjective(data, param, s)
        maior = res[N + 1]
        for j in range(N + 1):
            resto = [st for i, st in enumerate(maior.stages) if i != j]
            soma = sum(st.beta for st in resto)
            if soma <= 0:
                continue
            resto = [Stage(st.beta / soma, st.theta0, st.duration, st.m, st.a)
                     for st in resto]
            x0 = np.clip(param.encode(maior.Rc, resto), param.lower, param.upper)
            try:
                x = _refinar(obj, x0, param)
            except Exception:                         # noqa: BLE001
                continue
            ref = reference_rmse(data, param, x, None, s.engine)
            if ref < res[N].best.rmse * (1 - 1e-9):
                log.info("N=%d: candidato aninhado (de N=%d) %.4f -> %.4f kPa",
                         N, N + 1, res[N].best.rmse, ref)
                extra = PressureRun(run=len(res[N].runs), seed=None, x=x,
                                    rmse=ref, rmse_rk4=float(obj(x[None])[0]),
                                    history=[], iterations=0,
                                    stopped_by="nested", elapsed_s=0.0)
                res[N] = summarize_pressure(data, s, res[N].param,
                                            res[N].runs + [extra],
                                            res[N].backend, res[N].elapsed_s)
    linhas = []
    for N in ns:
        r = res[N]
        s = replace(base, n_stages=N)
        cv = {"cv_rmse": float("nan"), "cv_std": float("nan")}
        if cv_folds >= 2:
            erros = []
            s1 = replace(s, runs=1, iterations=max(100, s.iterations // 4),
                         patience=max(50, s.patience // 4))
            for i, teste in enumerate(block_folds(data.n, cv_folds)):
                param = PressureParam(s1)
                obj = PressureObjective(data, param, s1, mask=~teste)
                cb = None
                if progress is not None:
                    def cb(it, fb, xb, _i=i):
                        return progress("cv", _i, it, fb)
                run = single_run(obj, param, s1, 0,
                                 None if s.seed is None else s.seed + 1000 + i,
                                 cb, x0=r.best.x)
                erros.append(reference_rmse(data, param, run.x, teste, s.engine))
            e = np.array(erros)
            cv = {"cv_rmse": float(e.mean()),
                  "cv_std": float(e.std(ddof=1)) if e.size > 1 else 0.0}
        m = r.metrics or {}
        estr = [w for w in r.warnings if "contributes less" in w
                or "nearly identical" in w]
        linhas.append({"n_stages": N, "k": r.param.size, "series": "P",
                       "rmse": m.get("rmse", float("nan")),
                       "mae": m.get("mae", float("nan")),
                       "see": m.get("see", float("nan")),
                       "r2": m.get("r2", float("nan")),
                       "aic": m.get("aic", float("nan")),
                       "bic": m.get("bic", float("nan")),
                       "durbin_watson": m.get("durbin_watson", float("nan")),
                       "lag1_autocorr": m.get("lag1_autocorr", float("nan")),
                       **cv, "objective_run_std": r.objective_stats["std"],
                       "n_warnings": len(r.warnings),
                       "structural_warnings": len(estr),
                       "time_s": tempos[N]})
    amin = min(l["aic"] for l in linhas)
    bmin = min(l["bic"] for l in linhas)
    for l in linhas:
        l["delta_aic"], l["delta_bic"] = l["aic"] - amin, l["bic"] - bmin
    rec, motivo = recommend(linhas, cv_tol)
    return {"table": linhas, "results": res, "recommended": rec,
            "reason": motivo, "cv_folds": cv_folds, "cv_tol": cv_tol,
            "cancelled": any(x.stopped_by == "cancel" for r in res.values()
                             for x in r.runs), "mode": "pressure"}
