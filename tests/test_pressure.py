# -*- coding: utf-8 -*-
"""Modo pressão: modelo 0-D com N estágios, equivalência com o Double Wiebe,
integradores em lote, ajuste e CLI."""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from wiebepy.core import Stage, stages_to_arrays
from wiebepy.core.validation import DataError
from wiebepy.pressure.engine import EngineConfig
from wiebepy.pressure.fit import (PressureSettings, fit_pressure,
                                  pressure_from_arrays, read_pressure)
from wiebepy.pressure.model import ODEFailure, batch_rk4, simulate

RAIZ = Path(__file__).resolve().parents[1]
ENSAIO = RAIZ / "examples" / "data" / "ensaio_P_exp_carga3_45.txt"
G = math.pi / 180.0
DOIS = [Stage(0.40, -6.54 * G, 25 * G, 0.5, 6.9078),
        Stage(0.60, 10 * G, 55 * G, 1.0, 6.9078)]


@pytest.fixture(scope="module")
def ensaio():
    return read_pressure(ENSAIO, "rad", "bar")


def test_leitura_do_ensaio(ensaio):
    assert ensaio.n == 459
    assert ensaio.theta[0] >= -2.0 and ensaio.theta[-1] <= 2.0
    assert 5000 < ensaio.P.max() < 6000                 # kPa
    assert not ensaio.warnings


def test_unidades_de_pressao_e_angulo():
    th = np.linspace(-100, 100, 201)
    P = 1 + np.exp(-(th / 20) ** 2) * 50
    a = pressure_from_arrays(th, P, "deg", "bar", None, None)
    b = pressure_from_arrays(np.radians(th), P * 100, "rad", "kPa", None, None)
    np.testing.assert_allclose(a.theta, b.theta)
    np.testing.assert_allclose(a.P, b.P)


def test_aviso_de_unidade_angular_trocada():
    th = np.linspace(-2, 2, 300)                        # rad lido como graus
    d = pressure_from_arrays(th, 1 + np.exp(-th ** 2) * 50, "deg", "bar",
                             None, None)
    assert any("unidade angular" in w for w in d.warnings)


def test_pressao_no_modo_xb_e_recusada():
    from wiebepy.io.readers import read_data
    with pytest.raises(DataError, match="PRESSÃO"):
        read_data(ENSAIO, "rad")


def test_n2_igual_ao_double_wiebe(ensaio):
    dw = pytest.importorskip("double_wiebe.simulation")
    from double_wiebe.models import (EngineConfig as DE, SimulationConfig,
                                     WiebeParameters)
    w = WiebeParameters()
    ref = dw.run_simulation(ensaio.theta, ensaio.P, DE(), w,
                            SimulationConfig()).P_sim
    st = [Stage(w.alpha, w.theta01, w.delta1, w.m1, w.a1),
          Stage(1 - w.alpha, w.theta02, w.delta2, w.m2, w.a2)]
    P, _, _ = simulate(ensaio.theta, float(ensaio.P[0]), st, EngineConfig())
    np.testing.assert_allclose(P, ref, rtol=1e-6)


def test_estagio_com_beta_zero_nao_altera(ensaio):
    extra = DOIS + [Stage(0.0, 30 * G, 20 * G, 1.0, 6.9078)]
    a, _, _ = simulate(ensaio.theta, float(ensaio.P[0]), DOIS, EngineConfig())
    b, _, _ = simulate(ensaio.theta, float(ensaio.P[0]), extra, EngineConfig())
    np.testing.assert_allclose(a, b, rtol=1e-9)


def _lote(ensaio, n=3):
    arr = stages_to_arrays(DOIS)
    p = {k: np.tile(v, (n, 1)) for k, v in arr.items()}
    p["duration"][1] *= 1.3
    return np.array([17.0, 16.0, 15.5]), p


def test_rk4_numpy_perto_da_referencia(ensaio):
    Rc, p = _lote(ensaio)
    B = batch_rk4(ensaio.theta, float(ensaio.P[0]), Rc, p, EngineConfig(), 4,
                  "numpy")
    P, _, _ = simulate(ensaio.theta, float(ensaio.P[0]), DOIS, EngineConfig())
    assert np.max(np.abs(B[0] - P)) < 2.0               # kPa (pico ~5000)


def test_rk4_numba_igual_numpy(ensaio):
    pytest.importorskip("numba")
    Rc, p = _lote(ensaio)
    a = batch_rk4(ensaio.theta, float(ensaio.P[0]), Rc, p, EngineConfig(), 4, "numpy")
    b = batch_rk4(ensaio.theta, float(ensaio.P[0]), Rc, p, EngineConfig(), 4, "numba")
    np.testing.assert_allclose(b, a, rtol=1e-12)


def test_rk4_cuda_igual_numpy(ensaio):
    from wiebepy.parallel.gpu import cupy_available
    if not cupy_available():
        pytest.skip("CuPy/GPU indisponível")
    Rc, p = _lote(ensaio)
    a = batch_rk4(ensaio.theta, float(ensaio.P[0]), Rc, p, EngineConfig(), 4, "numpy")
    b = batch_rk4(ensaio.theta, float(ensaio.P[0]), Rc, p, EngineConfig(), 4, "cupy")
    np.testing.assert_allclose(b, a, rtol=1e-12)


def test_candidato_invalido_vira_nan(ensaio):
    Rc, p = _lote(ensaio)
    Rc[0] = 1.0
    B = batch_rk4(ensaio.theta, float(ensaio.P[0]), Rc, p, EngineConfig(), 4, "numpy")
    assert np.isnan(B[0]).all() and np.isfinite(B[1]).all()


def test_ajuste_recupera_pressao_sintetica(ensaio):
    """Pressão gerada pelo modelo com parâmetros conhecidos (+ ruído)."""
    e = EngineConfig(Rc=16.2)
    alvo = [Stage(0.3, -8 * G, 15 * G, 2.0, 6.9078),
            Stage(0.7, 4 * G, 40 * G, 1.2, 6.9078)]
    P, _, _ = simulate(ensaio.theta, float(ensaio.P[0]), alvo, e)
    P = P + np.random.default_rng(0).normal(0, 5.0, P.size)
    d = pressure_from_arrays(ensaio.theta, P, "rad", "kPa", None, None)
    r = fit_pressure(d, PressureSettings(n_stages=2, engine=EngineConfig(),
                                         runs=2, particles=40, iterations=200,
                                         seed=1))
    assert r.metrics["rmse"] < 7.0                       # ≈ nível do ruído
    assert r.Rc == pytest.approx(16.2, abs=0.2)


def test_ajuste_ensaio_real_n2(ensaio):
    r = fit_pressure(ensaio, PressureSettings(n_stages=2, runs=2, particles=40,
                                              iterations=200, seed=3))
    assert r.metrics["r2"] > 0.998
    assert r.metrics["rmse"] < 60.0                      # kPa
    assert abs(sum(s.beta for s in r.stages) - 1) < 1e-9


def test_cli_modo_pressao(tmp_path):
    from wiebepy.cli.parser import _main
    assert _main(["--stages", "1", "--optimize", "--input", str(ENSAIO),
                  "--input-type", "pressure", "--runs", "1", "--population",
                  "30", "--iterations", "80", "--quiet", "--save-plots",
                  "--output", str(tmp_path)]) == 0
    for f in ("results.csv", "parameters.csv", "metrics.csv", "results.json",
              "run_statistics.csv", "plots/pressure.png",
              "plots/pv_diagram.png", "plots/pv_diagram_loglog.png"):
        assert (tmp_path / f).exists(), f
    assert _main(["--input", str(ENSAIO), "--input-type", "pressure",
                  "--quiet", "--output", str(tmp_path / "x")]) == 2
