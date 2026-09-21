# -*- coding: utf-8 -*-
"""
fit.py — Ajuste de N estágios a dados experimentais (múltiplos runs).

Cada run: PSO (enxame avaliado em lote pelo backend escolhido) seguido de
refinamento local a partir dos ``polish_starts`` melhores pontos DISTINTOS
do enxame: mínimos quadrados (scipy least_squares, TRF) para métricas
quadráticas (rmse, mse, see, wrmse) e L-BFGS-B para mae. O problema é mal
condicionado (vales estreitos): o PSO localiza a região e o refinamento
converge com precisão; aceita-se o refinamento só se o objetivo (calculado
pelo próprio backend) diminuir. Runs independentes usam sementes seed + i.
Em "auto", rodam em processos paralelos só com o backend NumPy (de 1 núcleo):
medido nesta máquina, com Numba (já multithread) ou GPU os runs sequenciais
são mais rápidos que processos (custo de criação e 1 thread por processo).
Com --precision float32 a busca é feita em float32, mas os objetivos
reportados são recalculados em float64.

Resultado: melhor run, estatísticas do objetivo (best/mean/std/median/worst),
média e desvio dos parâmetros entre runs, métricas completas e avisos de
identificabilidade.
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import asdict, dataclass, field
from typing import Callable, Dict, List, Optional

import numpy as np

from ..core.core import multistage_wiebe
from ..core.derivatives import multistage_wiebe_derivative
from ..core.parameters import A_DEFAULT, Parametrization, Stage
from .bounds import bounds_from_data, effective_theta0_bounds
from .identifiability import (bound_warnings, correlation_warnings,
                              dispersion_warnings, stage_warnings)
from .objective import FitData, ObjectiveSpec, fit_metrics
from .pso import PSOConfig, pso

log = logging.getLogger("wiebepy")


@dataclass
class FitSettings:
    """Tudo que define um ajuste (serializável em YAML/JSON)."""
    n_stages: int = 2
    beta_mode: str = "stick"
    fit_a: bool = False
    a_fixed: float = A_DEFAULT
    bounds: Dict = field(default_factory=dict)      # sobrescritas
    metric: str = "rmse"
    fit_target: Optional[str] = None                # None -> conforme dados
    w_x: float = 1.0
    w_d: float = 1.0
    particles: int = 100
    iterations: int = 1000
    patience: int = 200
    topology: str = "ring"
    runs: int = 5
    seed: Optional[int] = 42
    backend: str = "auto"
    workers: Optional[int] = None
    precision: str = "float64"
    polish: bool = True
    polish_starts: int = 5
    parallel_runs: str = "auto"                     # auto | yes | no

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class RunResult:
    run: int
    seed: Optional[int]
    x: np.ndarray
    objective: float
    objective_pso: float
    history: List[float]
    iterations: int
    stopped_by: str
    elapsed_s: float
    n_evals: int

    def to_dict(self) -> Dict:
        d = asdict(self)
        d["x"] = self.x.tolist()
        return d


@dataclass
class FitResult:
    settings: FitSettings
    param: Parametrization
    spec: ObjectiveSpec
    runs: List[RunResult]
    best: RunResult
    stages: List[Stage]
    objective_stats: Dict
    param_stats: Dict
    metrics: Dict
    warnings: List[str]
    identifiability: Dict
    backend: str
    elapsed_s: float
    theta0_bounds: List[tuple]

    def to_dict(self) -> Dict:
        return {
            "n_stages": self.settings.n_stages,
            "settings": self.settings.to_dict(),
            "parametrization": self.param.to_dict(),
            "parameter_names": list(self.param.names),
            "objective": {"metric": self.spec.metric,
                          "fit_target": self.spec.fit_target},
            "stages": [s.to_dict() for s in self.stages],
            "best_run": self.best.to_dict(),
            "runs": [r.to_dict() for r in self.runs],
            "objective_stats": self.objective_stats,
            "param_stats": self.param_stats,
            "metrics": self.metrics,
            "warnings": self.warnings,
            "identifiability": {k: v for k, v in self.identifiability.items()
                                if k != "correlation"},
            "backend": self.backend,
            "elapsed_s": self.elapsed_s,
            "theta0_bounds": self.theta0_bounds,
        }


# =============================================================================
# Blocos
# =============================================================================
def build_problem(data: FitData, s: FitSettings):
    """(Parametrization, ObjectiveSpec) para os dados e as configurações."""
    b = bounds_from_data(float(data.theta.min()), float(data.theta.max()),
                         s.bounds)
    param = Parametrization(s.n_stages, b, s.beta_mode, s.fit_a, s.a_fixed)
    spec = ObjectiveSpec(s.metric, s.fit_target or data.default_target(),
                         s.w_x, s.w_d, n_params=param.size).check(data)
    return param, spec


def _residuals_fn(param: Parametrization, data: FitData, spec: ObjectiveSpec):
    """Resíduos em lote R(X) (S, n_res) coerentes com a métrica: pesos √w
    na wrmse, séries normalizadas no alvo "both" e a penalidade suave como
    resíduo extra √(n·pen)."""
    w = np.sqrt(data.weights) if (spec.metric == "wrmse"
                                  and data.weights is not None) else None

    def R(X):
        p, pen = param.decode(np.atleast_2d(X))
        from ..core.core import evaluate_batch
        xb, dxb = evaluate_batch(data.theta, p, np, spec.want_x, spec.want_d)
        partes = []
        for sim, y, esc, peso in ((xb, data.xb, spec.scale_x, spec.w_x),
                                  (dxb, data.dxb, spec.scale_d, spec.w_d)):
            if sim is None:
                continue
            r = sim - y[None, :]
            if w is not None:
                r = r * w[None, :]
            if spec.fit_target == "both":
                r = r * (np.sqrt(peso) / esc)
            partes.append(r)
        partes.append(np.sqrt(data.n * pen)[:, None])
        return np.concatenate(partes, axis=1)
    return R


def _distinct_starts(pso_res, param: Parametrization, k: int,
                     min_dist: float = 0.02) -> List[np.ndarray]:
    """Até k melhores pbest que distam > min_dist (norma-∞ relativa à faixa)
    uns dos outros."""
    if pso_res.pbest is None:
        return [pso_res.x]
    span = np.maximum(param.upper - param.lower, 1e-300)
    out: List[np.ndarray] = []
    for i in np.argsort(pso_res.pbest_f):
        c = pso_res.pbest[i]
        if all(np.max(np.abs(c - o) / span) > min_dist for o in out):
            out.append(c)
        if len(out) >= k:
            break
    return out


def refine(obj, x_starts, param: Parametrization, data: FitData,
           spec: ObjectiveSpec):
    """Refinamento local multi-início; devolve (x, objetivo) do melhor."""
    from scipy.optimize import least_squares, minimize
    lo, hi = param.lower, param.upper
    h = 1e-7 * np.maximum(hi - lo, 1e-12)
    melhor_x, melhor_f = None, np.inf
    if spec.metric in ("rmse", "mse", "see", "wrmse"):
        R = _residuals_fn(param, data, spec)

        def jac(v):
            X = np.repeat(v[None, :], v.size + 1, axis=0)
            passo = np.where(v + h <= hi, h, -h)
            X[np.arange(1, v.size + 1), np.arange(v.size)] += passo
            M = R(X)
            return ((M[1:] - M[0]) / passo[:, None]).T

        for x0 in x_starts:
            r = least_squares(lambda v: R(v[None, :])[0], np.clip(x0, lo, hi),
                              jac=jac, bounds=(lo, hi), method="trf",
                              x_scale="jac", max_nfev=200)
            x = np.clip(r.x, lo, hi)
            f = float(obj(x[None, :])[0])
            if f < melhor_f:
                melhor_x, melhor_f = x, f
    else:                                            # mae: L-BFGS-B
        def fg(v):
            X = np.repeat(v[None, :], v.size + 1, axis=0)
            passo = np.where(v + h <= hi, h, -h)
            X[np.arange(1, v.size + 1), np.arange(v.size)] += passo
            f = obj(X)
            return float(f[0]), (f[1:] - f[0]) / passo

        for x0 in x_starts:
            r = minimize(fg, np.clip(x0, lo, hi), jac=True, method="L-BFGS-B",
                         bounds=list(zip(lo, hi)), options={"maxiter": 500})
            x = np.clip(r.x, lo, hi)
            f = float(obj(x[None, :])[0])
            if f < melhor_f:
                melhor_x, melhor_f = x, f
    return melhor_x, melhor_f


def single_run(obj, param: Parametrization, s: FitSettings, run: int,
               seed: Optional[int], callback=None, data: FitData = None,
               spec: ObjectiveSpec = None,
               x0: Optional[np.ndarray] = None) -> RunResult:
    cfg = PSOConfig(particles=s.particles, iterations=s.iterations,
                    patience=s.patience, topology=s.topology, seed=seed)
    r = pso(obj, param.lower, param.upper, cfg, x0=x0, callback=callback)
    x, f = r.x, r.fun
    t = r.elapsed_s
    if s.polish and r.stopped_by != "cancel":
        t0 = time.perf_counter()
        inicios = _distinct_starts(r, param, max(1, s.polish_starts))
        xp_, fp_ = refine(obj, inicios, param, data, spec)
        t += time.perf_counter() - t0
        if fp_ < f:
            x, f = xp_, fp_
    return RunResult(run=run, seed=seed, x=x, objective=f, objective_pso=r.fun,
                     history=r.history, iterations=r.iterations,
                     stopped_by=r.stopped_by, elapsed_s=t, n_evals=r.n_evals)


def _run_worker(args):
    """Top-level (picklable): um run completo num processo filho."""
    data, s, run, seed, backend = args
    from ..parallel.backend import make_objective
    from ..parallel.cpu import set_numba_threads
    set_numba_threads(1)                    # sem oversubscription
    param, spec = build_problem(data, s)
    obj = make_objective(backend, data, param, spec, s.precision, 1,
                         s.particles)
    try:
        return single_run(obj, param, s, run, seed, data=data, spec=spec)
    finally:
        obj.close()


def _seeds(s: FitSettings) -> List[Optional[int]]:
    return [None if s.seed is None else int(s.seed) + i for i in range(s.runs)]


def fit(data: FitData, s: FitSettings,
        progress: Optional[Callable[[int, int, float, np.ndarray], bool]] = None
        ) -> FitResult:
    """Ajusta N estágios com ``s.runs`` runs independentes.

    progress(run, iteração, melhor, x) -> True cancela (só runs sequenciais).
    """
    from ..parallel.backend import make_objective
    t0 = time.perf_counter()
    param, spec = build_problem(data, s)
    obj = make_objective(s.backend, data, param, spec, s.precision,
                         s.workers, s.particles)
    backend_desc = obj.describe()
    log.info("Execution backend : %s", backend_desc)
    workers = s.workers or max(1, (os.cpu_count() or 2) - 1)
    paralelo = (s.parallel_runs == "yes" or (
        s.parallel_runs == "auto" and s.runs >= 2 and workers >= 2
        and obj.name == "numpy"))
    seeds = _seeds(s)
    runs: List[RunResult] = []
    try:
        if paralelo:
            from ..parallel.procs import spawn_pool
            n_proc = min(workers, s.runs)
            log.info("Runs em paralelo: %d processos (%s por processo)",
                     n_proc, obj.name)
            with spawn_pool(n_proc) as ex:
                futs = [ex.submit(_run_worker, (data, s, i, seeds[i], obj.name))
                        for i in range(s.runs)]
                for i, fu in enumerate(futs):
                    runs.append(fu.result())
                    log.info("Run %02d/%02d  objetivo = %.6e", i + 1, s.runs,
                             runs[-1].objective)
            backend_desc = f"{obj.name} × {n_proc} processos (runs paralelos)"
        else:
            for i in range(s.runs):
                cb = None
                if progress is not None:
                    def cb(it, fb, xb, _i=i):
                        return progress(_i, it, fb, xb)
                runs.append(single_run(obj, param, s, i, seeds[i], cb,
                                       data=data, spec=spec))
                log.info("Run %02d/%02d  objetivo = %.6e  (%.1f s, %s)",
                         i + 1, s.runs, runs[-1].objective,
                         runs[-1].elapsed_s, runs[-1].stopped_by)
    finally:
        obj.close()
    return summarize(data, s, param, spec, runs, backend_desc,
                     time.perf_counter() - t0)


def summarize(data, s, param, spec, runs, backend_desc, elapsed) -> FitResult:
    """Estatísticas, métricas e identificabilidade a partir dos runs."""
    if s.precision != "float64":
        from ..parallel.cpu import ArrayObjective
        ref = ArrayObjective(data, param, spec, "float64")
        f64 = ref(np.array([r.x for r in runs]))
        for r, v in zip(runs, f64):
            r.objective = float(v)
    vals = np.array([r.objective for r in runs])
    best = runs[int(np.argmin(vals))]
    stages = param.to_stages(best.x)
    ostats = {"best": float(vals.min()), "mean": float(vals.mean()),
              "std": float(vals.std(ddof=1)) if vals.size > 1 else 0.0,
              "median": float(np.median(vals)), "worst": float(vals.max()),
              "runs": int(vals.size)}
    # estatísticas dos parâmetros físicos entre runs
    todos = np.array([[[getattr(st, k) for k in
                        ("beta", "theta0", "duration", "m", "a")]
                       for st in param.to_stages(r.x)] for r in runs])
    pstats = {}
    for j in range(s.n_stages):
        for c, k in enumerate(("beta", "theta0", "duration", "m", "a")):
            v = todos[:, j, c]
            pstats[f"{k}_{j + 1}"] = {
                "best": float(getattr(stages[j], k)), "mean": float(v.mean()),
                "std": float(v.std(ddof=1)) if v.size > 1 else 0.0}
    # métricas completas
    metrics = {}
    k = param.size
    if data.xb is not None:
        metrics["xb"] = fit_metrics(data.xb, multistage_wiebe(data.theta, stages),
                                    k, data.weights)
    if data.dxb is not None:
        metrics["dxb"] = fit_metrics(
            data.dxb, multistage_wiebe_derivative(data.theta, stages), k,
            data.weights)
    R = float(np.ptp(data.theta))
    avisos = (stage_warnings(stages, R) + bound_warnings(best.x, param)
              + dispersion_warnings(np.array([r.x for r in runs]), param))
    try:
        ident = correlation_warnings(best.x, param, data, spec.fit_target)
        avisos += ident["warnings"]
    except np.linalg.LinAlgError as e:           # pragma: no cover
        ident = {"warnings": [], "condition_number": float("inf"),
                 "error": str(e)}
    return FitResult(settings=s, param=param, spec=spec, runs=runs,
                     best=best, stages=stages, objective_stats=ostats,
                     param_stats=pstats, metrics=metrics, warnings=avisos,
                     identifiability=ident, backend=backend_desc,
                     elapsed_s=elapsed,
                     theta0_bounds=effective_theta0_bounds(param.bounds,
                                                           s.n_stages))
