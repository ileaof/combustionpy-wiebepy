# -*- coding: utf-8 -*-
"""
backend.py — Seleção do backend de avaliação (com fallback automático).

Backends:  numpy | numba | multiprocessing | cupy | auto

* numpy           — enxame vetorizado em (S, n), 1 núcleo
* numba           — kernel compilado, threads sobre os candidatos
                    (--workers threads)
* multiprocessing — enxame dividido entre --workers processos (NumPy)
* cupy            — GPU NVIDIA (mesmo núcleo com xp = cupy)
* auto            — mini-benchmark com o tamanho REAL do problema
                    (S partículas × n pontos × N estágios); o tempo de
                    compilação (Numba/CuPy) fica fora da medida; o
                    multiprocessing só entra como candidato em problemas
                    grandes (o custo de IPC domina os pequenos)

Backend pedido e indisponível -> WARNING e fallback
(cupy -> numba -> numpy); o programa nunca encerra por falta de GPU.
"""
from __future__ import annotations

import logging
import time
from typing import Optional, Tuple

import numpy as np

from .cpu import (ArrayObjective, BatchObjective, MultiprocessingObjective,
                  NumbaObjective, numba_available)
from .gpu import CupyObjective, cupy_available

log = logging.getLogger("wiebepy")

BACKENDS = ("auto", "numpy", "numba", "multiprocessing", "cupy")
_MP_MIN_WORK = 20_000_000          # S·n·N mínimo para considerar processos


def available_backends() -> list:
    out = ["numpy", "multiprocessing"]
    if numba_available():
        out.insert(1, "numba")
    if cupy_available():
        out.append("cupy")
    return out


def _build(nome, data, param, spec, precision, workers) -> BatchObjective:
    if nome == "numpy":
        return ArrayObjective(data, param, spec, precision)
    if nome == "numba":
        return NumbaObjective(data, param, spec, precision, workers)
    if nome == "multiprocessing":
        return MultiprocessingObjective(data, param, spec, precision, workers)
    if nome == "cupy":
        return CupyObjective(data, param, spec, precision)
    raise ValueError(f"Backend desconhecido: '{nome}'. Válidos: {BACKENDS}.")


def _fallback_chain(nome: str) -> list:
    return {"cupy": ["cupy", "numba", "numpy"],
            "numba": ["numba", "numpy"],
            "multiprocessing": ["multiprocessing", "numpy"],
            "numpy": ["numpy"]}[nome]


def make_objective(nome: str, data, param, spec, precision="float64",
                   workers: Optional[int] = None,
                   population: int = 50) -> BatchObjective:
    """Cria o avaliador pedido, com fallback e WARNING se indisponível."""
    nome = (nome or "auto").lower()
    if nome not in BACKENDS:
        raise ValueError(f"--backend deve ser um de {BACKENDS}.")
    if nome == "auto":
        return choose_auto(data, param, spec, precision, workers, population)[0]
    erros = []
    for cand in _fallback_chain(nome):
        try:
            obj = _build(cand, data, param, spec, precision, workers)
            if cand != nome:
                log.warning("WARNING: backend '%s' indisponível (%s). "
                            "Usando '%s'.", nome, "; ".join(erros), cand)
            return obj
        except Exception as e:                      # noqa: BLE001
            erros.append(f"{cand}: {e}")
    raise RuntimeError("Nenhum backend disponível: " + "; ".join(erros))


def choose_auto(data, param, spec, precision="float64",
                workers: Optional[int] = None, population: int = 50,
                reps: int = 2) -> Tuple[BatchObjective, dict]:
    """Mini-benchmark com o enxame real; devolve (avaliador, tempos)."""
    rng = np.random.default_rng(0)
    X = param.lower + rng.random((population, param.size)) * (
        param.upper - param.lower)
    candidatos = ["numpy"]
    if numba_available():
        candidatos.append("numba")
    if cupy_available():
        candidatos.append("cupy")
    trabalho = population * data.n * param.n_stages
    if (workers or 0) > 1 and trabalho >= _MP_MIN_WORK:
        candidatos.append("multiprocessing")
    tempos, objs = {}, {}
    for nome in candidatos:
        try:
            obj = _build(nome, data, param, spec, precision, workers)
            obj(X[:2])                              # aquecimento/compilação
            t0 = time.perf_counter()
            for _ in range(reps):
                obj(X)
            tempos[nome] = (time.perf_counter() - t0) / reps
            objs[nome] = obj
        except Exception as e:                      # noqa: BLE001
            log.warning("WARNING: backend '%s' falhou no teste (%s).", nome, e)
    melhor = min(tempos, key=tempos.get)
    for nome, obj in objs.items():
        if nome != melhor:
            obj.close()
    log.info("auto: %s", ", ".join(f"{k}={v * 1e3:.2f} ms" for k, v in
                                  sorted(tempos.items(), key=lambda t: t[1])))
    return objs[melhor], tempos
