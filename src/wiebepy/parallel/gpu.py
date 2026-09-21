# -*- coding: utf-8 -*-
"""
gpu.py — Avaliação na GPU NVIDIA via CuPy (opcional).

Usa o MESMO núcleo matemático de core.py com ``xp = cupy`` — nenhuma
equação é duplicada. Os dados experimentais ficam na GPU durante todo o
ajuste; por avaliação sobem só os candidatos (S × P) e descem só S valores
do objetivo (a redução é feita no device).

GPUs de consumo (ex.: RTX 4050) têm throughput FP64 de ~1/64 do FP32:
``--precision float32`` costuma ser muito mais rápido; o padrão científico
continua float64. Nunca é dependência obrigatória.
"""
from __future__ import annotations

from typing import Dict

import numpy as np

from .cpu import ArrayObjective
from .hardware import cupy_info


def cupy_available() -> bool:
    return bool(cupy_info()["available"])


class CupyObjective(ArrayObjective):
    """ArrayObjective com xp = cupy (dados residentes na GPU)."""
    name = "cupy"

    def __init__(self, data, param, spec, precision="float64"):
        if not cupy_available():
            raise RuntimeError("CuPy/GPU CUDA indisponível: "
                               + cupy_info().get("reason", ""))
        import cupy
        super().__init__(data, param, spec, precision, xp=cupy)
        # blocos maiores na GPU (memória do device)
        livre = cupy.cuda.runtime.memGetInfo()[0]
        bytes_el = np.dtype(self.dtype).itemsize
        self.block = max(1, int(livre * 0.25 / (8 * bytes_el * max(self.n, 1))))

    def describe(self) -> str:
        return f"cupy ({cupy_info()['gpu_name']}, {self.precision})"

    def __call__(self, X):
        out = super().__call__(X)
        return out

    def synchronize(self) -> None:
        import cupy
        cupy.cuda.Device().synchronize()


def cupy_points(theta, stages_arrays: Dict, dtype=np.float64):
    """x_b e dx_b/dθ em n pontos na GPU (retorna numpy)."""
    import cupy
    from ..core.core import stage_contributions
    th = cupy.asarray(theta, dtype=dtype)
    cx, cd = stage_contributions(th, stages_arrays, cupy)
    xb = cx.sum(axis=0).clip(0.0, 1.0)
    return cupy.asnumpy(xb), cupy.asnumpy(cd.sum(axis=0))
