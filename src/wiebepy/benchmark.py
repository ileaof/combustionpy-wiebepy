# -*- coding: utf-8 -*-
"""
benchmark.py — Benchmark reproduzível dos backends.

Dois cenários:

1. "points": x_b e dx_b/dθ de UM modelo em n pontos
   (n = 1e3, 1e4, 1e5, 1e6) — NumPy serial, NumPy multiprocessing,
   Numba (paralelo em θ) e CuPy (float64/float32, incluindo a cópia do
   resultado para a CPU).
2. "objective": função objetivo de S candidatos × n pontos, como no PSO
   (S = 20, 100, 1000; n = 1e3, 1e4 [, 1e5 no modo completo]) — é o
   cenário que determina o tempo de um ajuste.

Cada medida: aquecimento (compilação Numba/NVRTC fora da medida), média e
desvio de ``reps`` repetições, speedup vs NumPy, vazão, memória de pico e
erro máximo relativo vs NumPy float64. Nenhum ganho é assumido: tudo é
medido nesta máquina.
"""
from __future__ import annotations

import csv
import time
import tracemalloc
from pathlib import Path
from typing import Callable, Dict, List, Optional

import numpy as np

from .core.core import stage_contributions
from .core.parameters import Parametrization, default_stages, stages_to_arrays
from .optimization.bounds import bounds_from_data
from .optimization.objective import FitData, ObjectiveSpec
from .parallel.cpu import (ArrayObjective, MultiprocessingObjective,
                           NumbaObjective, numba_available, numba_points,
                           set_numba_threads)
from .parallel.gpu import CupyObjective, cupy_available, cupy_points

POINTS_SIZES = (1_000, 10_000, 100_000, 1_000_000)
OBJ_S = (20, 100, 1000)
OBJ_N_QUICK = (1_000, 10_000)
OBJ_N_FULL = (1_000, 10_000, 100_000)


def _time(fn: Callable, reps: int):
    fn()                                          # aquecimento
    ts = []
    for _ in range(reps):
        t0 = time.perf_counter()
        out = fn()
        ts.append(time.perf_counter() - t0)
    return float(np.mean(ts)), float(np.std(ts)), out


def _numpy_points(theta, arr, dtype=np.float64):
    th = np.asarray(theta, dtype=dtype)
    a = {k: v.astype(dtype) for k, v in arr.items()}
    cx, cd = stage_contributions(th, a, np)
    return cx.sum(axis=0).clip(0, 1), cd.sum(axis=0)


def _mp_points_worker(args):
    th, arr = args
    return _numpy_points(th, arr)


def _peak_numpy(fn) -> int:
    tracemalloc.start()
    fn()
    pico = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    return int(pico)


def bench_points(n_stages=3, sizes=POINTS_SIZES, reps=3, workers=None,
                 log=print) -> List[Dict]:
    stages = default_stages(n_stages, -20.0, 100.0)
    arr = stages_to_arrays(stages)
    linhas = []
    pool = None
    if workers and workers > 1:
        from .parallel.procs import spawn_pool
        pool = spawn_pool(workers)
    try:
        for n in sizes:
            th = np.linspace(-20.0, 100.0, int(n))
            t_np, s_np, ref = _time(lambda: _numpy_points(th, arr), reps)
            casos = {"numpy": (t_np, s_np, ref, _peak_numpy(
                lambda: _numpy_points(th, arr)))}
            if pool is not None:
                def mp_fn():
                    partes = np.array_split(th, workers)
                    res = list(pool.map(_mp_points_worker,
                                        [(p, arr) for p in partes]))
                    return (np.concatenate([r[0] for r in res]),
                            np.concatenate([r[1] for r in res]))
                t, s, out = _time(mp_fn, reps)
                casos[f"multiprocessing ({workers})"] = (t, s, out, None)
            if numba_available():
                set_numba_threads(workers)
                t, s, out = _time(lambda: numba_points(th, arr), reps)
                casos["numba"] = (t, s, out, 2 * th.nbytes)
            if cupy_available():
                import cupy
                for prec, dt in (("float64", np.float64), ("float32", np.float32)):
                    pool_gpu = cupy.get_default_memory_pool()
                    pool_gpu.free_all_blocks()
                    fn = lambda dt=dt: cupy_points(th, arr, dt)  # noqa: E731
                    t, s, out = _time(fn, reps)
                    casos[f"cupy {prec}"] = (t, s, out, int(pool_gpu.total_bytes()))
            for nome, (t, s, out, mem) in casos.items():
                erro = float(np.max(np.abs(out[0] - ref[0])))
                linhas.append({
                    "scenario": "points", "backend": nome, "n_points": int(n),
                    "candidates": 1, "n_stages": n_stages,
                    "time_s": t, "std_s": s, "speedup_vs_numpy": t_np / t,
                    "throughput_per_s": n / t, "memory_bytes": mem,
                    "max_abs_err_xb_vs_numpy": erro})
                log(f"  points  n={int(n):>9,d}  {nome:<22} {t * 1e3:10.3f} ms "
                    f"± {s * 1e3:7.3f}  speedup {t_np / t:7.2f}×  err {erro:.1e}")
    finally:
        if pool is not None:
            pool.shutdown()
    return linhas


def bench_objective(n_stages=3, S_list=OBJ_S, n_list=OBJ_N_QUICK, reps=3,
                    workers=None, log=print) -> List[Dict]:
    stages = default_stages(n_stages, -20.0, 100.0)
    linhas = []
    for n in n_list:
        th = np.linspace(-20.0, 100.0, int(n))
        from .core.core import multistage_wiebe
        rng = np.random.default_rng(0)
        data = FitData(th, multistage_wiebe(th, stages)
                       + rng.normal(0, 1e-3, th.size))
        param = Parametrization(n_stages, bounds_from_data(-20.0, 100.0))
        spec = ObjectiveSpec("rmse", "xb", n_params=param.size).check(data)
        avaliadores = {"numpy": lambda: ArrayObjective(data, param, spec)}
        if numba_available():
            avaliadores["numba"] = lambda: NumbaObjective(data, param, spec,
                                                          workers=workers)
        if workers and workers > 1:
            avaliadores[f"multiprocessing ({workers})"] = (
                lambda: MultiprocessingObjective(data, param, spec,
                                                 workers=workers))
        if cupy_available():
            avaliadores["cupy float64"] = lambda: CupyObjective(data, param, spec)
            avaliadores["cupy float32"] = lambda: CupyObjective(
                data, param, spec, "float32")
        for S in S_list:
            X = param.lower + rng.random((S, param.size)) * (
                param.upper - param.lower)
            ref = None
            t_np = None
            for nome, cria in avaliadores.items():
                obj = cria()
                try:
                    t, s, out = _time(lambda: obj(X), reps)
                finally:
                    obj.close()
                if nome == "numpy":
                    ref, t_np = out, t
                    mem = _peak_numpy(lambda: ArrayObjective(
                        data, param, spec)(X))
                else:
                    mem = None
                erro = float(np.max(np.abs(out - ref) / np.maximum(
                    np.abs(ref), 1e-300)))
                linhas.append({
                    "scenario": "objective", "backend": nome,
                    "n_points": int(n), "candidates": int(S),
                    "n_stages": n_stages, "time_s": t, "std_s": s,
                    "speedup_vs_numpy": t_np / t,
                    "throughput_per_s": S * n / t, "memory_bytes": mem,
                    "max_rel_err_objective_vs_numpy": erro})
                log(f"  objective S={S:>5d} n={int(n):>7,d}  {nome:<22} "
                    f"{t * 1e3:10.3f} ms ± {s * 1e3:7.3f}  speedup "
                    f"{t_np / t:7.2f}×  err {erro:.1e}")
    return linhas


def run_benchmark(n_stages: int = 3, full: bool = False, reps: int = 3,
                  workers: Optional[int] = None, csv_path=None,
                  log=print) -> List[Dict]:
    log("Cenário 1 — avaliação em n pontos (um modelo)")
    linhas = bench_points(n_stages, POINTS_SIZES, reps, workers, log)
    log("Cenário 2 — função objetivo em lote (S candidatos × n pontos, PSO)")
    linhas += bench_objective(n_stages, OBJ_S,
                              OBJ_N_FULL if full else OBJ_N_QUICK, reps,
                              workers, log)
    if csv_path:
        p = Path(csv_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        campos = sorted({k for l in linhas for k in l},
                        key=lambda k: list(linhas[0]).index(k)
                        if k in linhas[0] else 99)
        with open(p, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=campos)
            w.writeheader()
            w.writerows(linhas)
    return linhas
