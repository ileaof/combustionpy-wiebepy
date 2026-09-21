# -*- coding: utf-8 -*-
"""Núcleo: x_b, derivada analítica e parametrização para N = 1..5."""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pytest

from wiebepy.core import (BETA_MODES, Parametrization, Stage, StageBounds,
                          evaluate_batch, finite_difference_check,
                          multistage_wiebe, multistage_wiebe_derivative,
                          stage_contributions, stages_to_arrays,
                          validate_stages)

from conftest import REF_STAGES


# ---------------------------------------------------------------------------
# Propriedades de x_b
# ---------------------------------------------------------------------------
def test_limites_assintoticos(stages):
    """x_b(−∞) = 0 e x_b(+∞) ≈ 1."""
    th = np.array([-1e6, -1e3, 1e3, 1e6])
    x = multistage_wiebe(th, stages)
    assert x[0] == 0.0 and x[1] == 0.0
    assert x[2] == pytest.approx(1.0, abs=1e-12)
    assert x[3] == pytest.approx(1.0, abs=1e-12)


def test_intervalo_e_monotonicidade(theta, stages):
    x = multistage_wiebe(theta, stages)
    assert x.min() >= 0.0 and x.max() <= 1.0
    assert np.all(np.diff(x) >= 0.0)


def test_zero_antes_do_primeiro_inicio(theta, stages):
    x = multistage_wiebe(theta, stages)
    th0 = min(s.theta0 for s in stages)
    assert np.all(x[theta < th0] == 0.0)


def test_soma_das_contribuicoes(theta, stages):
    cx, cd = stage_contributions(theta, stages)
    assert cx.shape == (len(stages), theta.size)
    np.testing.assert_allclose(cx.sum(axis=0),
                               multistage_wiebe(theta, stages), atol=1e-15)
    np.testing.assert_allclose(cd.sum(axis=0),
                               multistage_wiebe_derivative(theta, stages),
                               atol=1e-15)


def test_integral_da_derivada_igual_incremento(theta, stages):
    d = multistage_wiebe_derivative(theta, stages)
    x = multistage_wiebe(theta, stages)
    assert np.trapezoid(d, theta) == pytest.approx(x[-1] - x[0], abs=2e-3)


def test_invariancia_a_ordem_dos_estagios(theta, stages):
    x1 = multistage_wiebe(theta, stages)
    x2 = multistage_wiebe(theta, list(reversed(stages)))
    np.testing.assert_allclose(x1, x2, atol=1e-15)


def test_estagio_com_peso_zero_nao_altera(theta):
    base = REF_STAGES[2]
    extra = base + [Stage(0.0, 30.0, 20.0, 1.0)]
    np.testing.assert_array_equal(multistage_wiebe(theta, base),
                                  multistage_wiebe(theta, extra))


def test_forma_de_um_estagio():
    """x_j(θ0 + Δθ) = 1 − exp(−a) para um estágio."""
    s = Stage(1.0, 0.0, 40.0, 1.7)
    x = multistage_wiebe(np.array([40.0]), [s])[0]
    assert x == pytest.approx(1.0 - math.exp(-6.908), rel=1e-14)


def test_aceita_dicts(theta):
    st = [{"beta": 0.35, "theta0": -5.0, "duration": 12.0, "m": 2.0,
           "a": 6.908},
          {"beta": 0.65, "theta0": 2.0, "duration": 45.0, "m": 1.3}]
    np.testing.assert_array_equal(multistage_wiebe(theta, st),
                                  multistage_wiebe(theta, REF_STAGES[2]))


# ---------------------------------------------------------------------------
# Derivada analítica × diferenças finitas
# ---------------------------------------------------------------------------
def test_derivada_vs_diferencas_finitas(theta, stages):
    r = finite_difference_check(theta, stages, rtol=1e-5, atol=1e-8)
    assert r["ok"], r
    assert r["n_points"] > 0.95 * theta.size


@pytest.mark.parametrize("m", [0.3, 0.7, 1.0, 1.5, 3.0])
def test_derivada_varios_m(m):
    """Inclui 0 < m < 1 (inclinação infinita em θ0, janela excluída)."""
    th = np.linspace(-10.0, 80.0, 2001)
    st = [Stage(0.4, 0.0, 20.0, m), Stage(0.6, 10.0, 40.0, m)]
    r = finite_difference_check(th, st, rtol=1e-4, atol=1e-7,
                                exclude_window=50.0)
    assert r["ok"], r


# ---------------------------------------------------------------------------
# Validação de estágios
# ---------------------------------------------------------------------------
def test_validacao_estagios(stages):
    assert validate_stages(stages) == []


@pytest.mark.parametrize("ruim, trecho", [
    ([Stage(0.5, 0, 10, 1)], "Σ beta"),
    ([Stage(1.0, 0, 0.0, 1)], "duration_1"),
    ([Stage(1.0, 0, 10, 0.0)], "m_1"),
    ([Stage(1.2, 0, 10, 1), Stage(-0.2, 5, 10, 1)], "beta_1"),
    ([Stage(1 / 6, 0, 10, 1)] * 6, "entre 1 e 5"),
])
def test_validacao_rejeita(ruim, trecho):
    assert any(trecho in e for e in validate_stages(ruim))


# ---------------------------------------------------------------------------
# Lote (S candidatos)
# ---------------------------------------------------------------------------
def test_lote_igual_individual(theta, stages):
    arr = stages_to_arrays(stages)
    params = {k: np.stack([v, v]) for k, v in arr.items()}
    xb, dxb = evaluate_batch(theta, params)
    np.testing.assert_array_equal(xb[0], multistage_wiebe(theta, stages))
    np.testing.assert_allclose(dxb[1],
                               multistage_wiebe_derivative(theta, stages),
                               rtol=1e-15, atol=1e-18)


# ---------------------------------------------------------------------------
# Parametrização
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("mode", BETA_MODES)
@pytest.mark.parametrize("fit_a", [False, True])
def test_encode_decode(stages, mode, fit_a):
    P = Parametrization(len(stages), StageBounds.from_data(-20, 100), mode,
                        fit_a)
    back = P.to_stages(P.encode(stages))
    for a, b in zip(stages, back):
        for k in ("beta", "theta0", "duration", "m", "a"):
            assert getattr(b, k) == pytest.approx(getattr(a, k), abs=1e-12)


@pytest.mark.parametrize("mode", BETA_MODES)
def test_pesos_no_simplex(n_stages, mode):
    P = Parametrization(n_stages, StageBounds.from_data(-20, 100), mode)
    rng = np.random.default_rng(0)
    X = P.lower + rng.random((500, P.size)) * (P.upper - P.lower)
    p, pen = P.decode(X)
    assert np.all(p["beta"] >= 0.0)
    if mode != "explicit":
        np.testing.assert_allclose(p["beta"].sum(axis=1), 1.0, atol=1e-12)
    else:                          # soma > 1 é penalizada, não aceita
        soma = X[:, P.size - (n_stages - 1):].sum(axis=1)
        assert np.all((pen > 0) == (soma > 1.0) | (pen > 0))
    assert np.all(np.diff(p["theta0"], axis=1) >= 0.0)   # ordenação


def test_parametrizacao_tamanho(n_stages):
    P = Parametrization(n_stages, StageBounds.from_data(0, 100))
    # θ0 (N) + Δθ (N) + m (N) + pesos (N−1)
    assert P.size == 4 * n_stages - 1
    P2 = Parametrization(n_stages, StageBounds.from_data(0, 100), fit_a=True)
    assert P2.size == 5 * n_stages - 1


def test_stick_n2_igual_alpha():
    P = Parametrization(2, StageBounds.from_data(-20, 100))
    x = P.encode([Stage(0.37, -5, 12, 2), Stage(0.63, 2, 45, 1.3)])
    assert x[-1] == pytest.approx(0.37)


def test_limite_cumulativo_penalizado():
    P = Parametrization(3, StageBounds.from_data(0.0, 100.0))
    x = P.encode([Stage(0.3, 60, 10, 1), Stage(0.3, 90, 10, 1),
                  Stage(0.4, 120, 10, 1)])
    _, pen = P.decode(x[None, :])
    assert pen[0] > 0.0


def test_n_invalido():
    with pytest.raises(ValueError):
        Parametrization(6, StageBounds.from_data(0, 1))
    with pytest.raises(ValueError):
        Parametrization(0, StageBounds.from_data(0, 1))


# ---------------------------------------------------------------------------
# Validação cruzada com as implementações Single/Double Wiebe (34.11)
# ---------------------------------------------------------------------------
RAIZ = Path(__file__).resolve().parents[2]


def _single():
    caminho = RAIZ / "single_wiebe" / "combustion_gui"
    if not (caminho / "single_wiebe.py").exists():
        pytest.skip("projeto single_wiebe não encontrado")
    sys.path.insert(0, str(caminho))
    try:
        import single_wiebe
    finally:
        sys.path.remove(str(caminho))
    return single_wiebe


def test_n1_igual_single_wiebe():
    sw = _single()
    th = np.linspace(-2.0, 2.0, 459)                  # rad, como no notebook
    th0, dth, m = math.radians(-6.54), math.radians(62.0), 0.504
    ref, dref = sw.burned_fraction(th, th0, dth, m)
    a = sw.DEFAULT_CONFIG.a_wiebe
    st = [Stage(1.0, th0, dth, m, a)]
    np.testing.assert_allclose(multistage_wiebe(th, st), ref,
                               rtol=1e-13, atol=1e-15)
    np.testing.assert_allclose(multistage_wiebe_derivative(th, st), dref,
                               rtol=1e-13, atol=1e-15)


def test_n2_igual_double_wiebe():
    dw = pytest.importorskip("double_wiebe.wiebe")
    from double_wiebe.models import WiebeParameters
    th = np.linspace(-2.0, 2.0, 721)
    w = WiebeParameters()                               # modo contínuo
    ref = dw.double_burned_fraction(th, w)
    st = [Stage(w.alpha, w.theta01, w.delta1, w.m1, w.a1),
          Stage(1 - w.alpha, w.theta02, w.delta2, w.m2, w.a2)]
    np.testing.assert_allclose(multistage_wiebe(th, st), ref["xb"],
                               rtol=1e-13, atol=1e-15)
    np.testing.assert_allclose(multistage_wiebe_derivative(th, st),
                               ref["dxb"], rtol=1e-13, atol=1e-15)
