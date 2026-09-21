# -*- coding: utf-8 -*-
"""Backends: NumPy ≡ Numba ≡ multiprocessing ≡ CuPy, fallback e auto."""
from __future__ import annotations

import logging

import numpy as np
import pytest

from wiebepy.core import (Parametrization, multistage_wiebe,
                          multistage_wiebe_derivative, stages_to_arrays)
from wiebepy.optimization.bounds import bounds_from_data
from wiebepy.optimization.objective import FitData, ObjectiveSpec
from wiebepy.parallel import backend as be
from wiebepy.parallel.cpu import (ArrayObjective, MultiprocessingObjective,
                                  NumbaObjective, numba_available,
                                  numba_points)
from wiebepy.parallel.gpu import CupyObjective, cupy_available, cupy_points

from conftest import REF_STAGES

requer_numba = pytest.mark.skipif(not numba_available(),
                                  reason="numba não instalado")
requer_gpu = pytest.mark.skipif(not cupy_available(),
                                reason="CuPy/GPU indisponível")


def _problema(N, target="xb", metric="rmse", pesos=False):
    th = np.linspace(-20, 100, 501)
    st = REF_STAGES[N]
    rng = np.random.default_rng(N)
    d = FitData(th, multistage_wiebe(th, st) + rng.normal(0, 1e-3, th.size),
                multistage_wiebe_derivative(th, st)
                + rng.normal(0, 1e-4, th.size),
                rng.uniform(0.5, 2.0, th.size) if pesos else None)
    P = Parametrization(N, bounds_from_data(-20, 100))
    spec = ObjectiveSpec(metric, target, n_params=P.size).check(d)
    X = P.lower + rng.random((40, P.size)) * (P.upper - P.lower)
    X[0] = P.encode(st)
    return d, P, spec, X


def _compara(a, b, rtol):
    np.testing.assert_allclose(b, a, rtol=rtol, atol=1e-15)


@requer_numba
@pytest.mark.parametrize("target", ["xb", "dxb", "both"])
@pytest.mark.parametrize("metric", ["rmse", "mse", "mae", "see", "wrmse"])
def test_numba_igual_numpy(n_stages, target, metric):
    d, P, spec, X = _problema(n_stages, target, metric, pesos=True)
    ref = ArrayObjective(d, P, spec)(X)
    _compara(ref, NumbaObjective(d, P, spec, workers=2)(X), 1e-12)


@requer_gpu
@pytest.mark.gpu
@pytest.mark.parametrize("target", ["xb", "dxb", "both"])
def test_cupy_igual_numpy(n_stages, target):
    d, P, spec, X = _problema(n_stages, target)
    ref = ArrayObjective(d, P, spec)(X)
    _compara(ref, CupyObjective(d, P, spec)(X), 1e-12)


@requer_gpu
@pytest.mark.gpu
def test_cupy_float32_proximo():
    d, P, spec, X = _problema(3)
    ref = ArrayObjective(d, P, spec)(X)
    f32 = CupyObjective(d, P, spec, "float32")(X)
    np.testing.assert_allclose(f32, ref, rtol=1e-3)


@pytest.mark.slow
def test_multiprocessing_igual_numpy():
    d, P, spec, X = _problema(3, "both")
    ref = ArrayObjective(d, P, spec)(X)
    mp = MultiprocessingObjective(d, P, spec, workers=2)
    try:
        np.testing.assert_array_equal(mp(X), ref)
    finally:
        mp.close()


def test_blocos_nao_alteram_resultado():
    d, P, spec, X = _problema(2)
    a = ArrayObjective(d, P, spec)
    ref = a(X)
    a.block = 7                                   # blocos que não dividem S
    np.testing.assert_array_equal(a(X), ref)


def test_penalidade_e_finitude():
    d, P, spec, X = _problema(3)
    X2 = X.copy()
    X2[:, 1:3] = P.upper[1:3]                     # inícios além de theta0_max
    f = ArrayObjective(d, P, spec)(X2)
    assert np.all(np.isfinite(f))
    assert np.all(f >= ArrayObjective(d, P, spec)(X).min())


@requer_numba
def test_numba_points_igual_numpy(stages):
    th = np.linspace(-20, 100, 5001)
    xb, dx = numba_points(th, stages_to_arrays(stages))
    np.testing.assert_allclose(xb, multistage_wiebe(th, stages), rtol=1e-13,
                               atol=1e-15)
    np.testing.assert_allclose(dx, multistage_wiebe_derivative(th, stages),
                               rtol=1e-13, atol=1e-16)


@requer_gpu
@pytest.mark.gpu
def test_cupy_points_igual_numpy(stages):
    th = np.linspace(-20, 100, 5001)
    xb, dx = cupy_points(th, stages_to_arrays(stages))
    np.testing.assert_allclose(xb, multistage_wiebe(th, stages), rtol=1e-12,
                               atol=1e-15)


def test_fallback_com_warning(monkeypatch, caplog):
    d, P, spec, _ = _problema(2)
    monkeypatch.setattr(be, "_build", _build_sem(be._build, {"cupy", "numba"}))
    with caplog.at_level(logging.WARNING, logger="wiebepy"):
        obj = be.make_objective("cupy", d, P, spec)
    assert obj.name == "numpy"
    assert any("indisponível" in r.message for r in caplog.records)


def _build_sem(original, faltando):
    def fake(nome, *a, **k):
        if nome in faltando:
            raise RuntimeError(f"{nome} simulado ausente")
        return original(nome, *a, **k)
    return fake


def test_auto_escolhe_disponivel():
    d, P, spec, _ = _problema(2)
    obj, tempos = be.choose_auto(d, P, spec, population=20)
    assert obj.name in tempos and tempos[obj.name] == min(tempos.values())
    obj.close()


def test_backend_invalido():
    d, P, spec, _ = _problema(1)
    with pytest.raises(ValueError):
        be.make_objective("tpu", d, P, spec)


def test_precisao_invalida():
    d, P, spec, _ = _problema(1)
    with pytest.raises(ValueError):
        ArrayObjective(d, P, spec, "float16")
