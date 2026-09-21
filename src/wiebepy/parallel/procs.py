# -*- coding: utf-8 -*-
"""
procs.py — Pools de processos sem sobreinscrição de threads.

Cada processo filho herda do pai as variáveis de ambiente de threads de
BLAS/OpenMP. Sem limitá-las, W processos × (núcleos) threads de
OpenBLAS/MKL disputam a CPU (ex.: 4 × 20 = 80 threads em 20 núcleos) e o
SVD do refinamento local fica dezenas de vezes mais lento. Os filhos
são criados (spawn) com 1 thread de BLAS/OpenMP; o paralelismo vem dos
próprios processos.
"""
from __future__ import annotations

import os
from contextlib import contextmanager

_VARS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
         "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMBA_NUM_THREADS")


@contextmanager
def single_threaded_children():
    """Enquanto ativo, processos criados herdam 1 thread de BLAS/OpenMP."""
    antigos = {k: os.environ.get(k) for k in _VARS}
    try:
        for k in _VARS:
            os.environ[k] = "1"
        yield
    finally:
        for k, v in antigos.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


class _Resultado:
    """Adaptador de AsyncResult com a interface de Future (.result())."""

    def __init__(self, ar):
        self._ar = ar

    def result(self, timeout=None):
        return self._ar.get(timeout)


class SpawnPool:
    """multiprocessing.Pool (spawn) com interface mínima de executor:
    map, submit(...).result(), shutdown e gerenciador de contexto.

    Usa Pool (e não ProcessPoolExecutor) porque o Pool cria TODOS os
    processos na construção; o ProcessPoolExecutor do Python 3.12 os cria
    sob demanda, de forma síncrona no processo principal, o que custava
    ~0.5 s por chamada até o pool "encher"."""

    def __init__(self, workers: int, initializer=None, initargs=()):
        import multiprocessing as mp
        with single_threaded_children():
            self._pool = mp.get_context("spawn").Pool(
                processes=workers, initializer=initializer,
                initargs=initargs)
        self.workers = workers

    def map(self, fn, iterable):
        return self._pool.map(fn, list(iterable), chunksize=1)

    def submit(self, fn, *args):
        return _Resultado(self._pool.apply_async(fn, args))

    def shutdown(self, wait: bool = True, cancel_futures: bool = False):
        if self._pool is None:
            return
        if cancel_futures or not wait:
            self._pool.terminate()
        else:
            self._pool.close()
        self._pool.join()
        self._pool = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.shutdown()
        return False


def spawn_pool(workers: int, initializer=None, initargs=()) -> SpawnPool:
    """Pool de processos (spawn) com filhos de 1 thread de BLAS/OpenMP,
    todos criados já na construção."""
    return SpawnPool(workers, initializer, initargs)
