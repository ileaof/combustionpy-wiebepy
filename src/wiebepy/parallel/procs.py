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


def spawn_pool(workers: int, initializer=None, initargs=()):
    """ProcessPoolExecutor (spawn) com filhos de 1 thread de BLAS; os
    processos são criados já na construção (antes de restaurar o ambiente)."""
    import multiprocessing as mp
    from concurrent.futures import ProcessPoolExecutor
    with single_threaded_children():
        pool = ProcessPoolExecutor(workers, mp_context=mp.get_context("spawn"),
                                   initializer=initializer, initargs=initargs)
        # força a criação de todos os processos enquanto o ambiente vale
        list(pool.map(_noop, range(workers)))
    return pool


def _noop(_):
    return None
