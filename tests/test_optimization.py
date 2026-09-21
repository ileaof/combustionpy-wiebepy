# -*- coding: utf-8 -*-
"""PSO, ajuste, runs, identificabilidade e comparação de estágios."""
from __future__ import annotations

import numpy as np
import pytest

from wiebepy.core import Stage, multistage_wiebe, multistage_wiebe_derivative
from wiebepy.optimization.compare import block_folds, compare_stages, recommend
from wiebepy.optimization.fit import FitSettings, fit
from wiebepy.optimization.identifiability import stage_warnings
from wiebepy.optimization.objective import FitData, fit_metrics
from wiebepy.optimization.pso import PSOConfig, pso

from conftest import REF_STAGES

RAPIDO = dict(particles=60, iterations=300, patience=80, runs=2,
              backend="numpy", parallel_runs="no")


def _dados(N, ruido=1e-3, seed=0, com_d=False):
    th = np.linspace(-20, 100, 401)
    st = REF_STAGES[N]
    rng = np.random.default_rng(seed)
    xb = multistage_wiebe(th, st) + rng.normal(0, ruido, th.size)
    dxb = multistage_wiebe_derivative(th, st) if com_d else None
    return FitData(th, xb, dxb)


# ---------------------------------------------------------------------------
# PSO
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("topology", ["ring", "global"])
def test_pso_minimiza_esfera(topology):
    f = lambda X: np.sum((X - 0.3) ** 2, axis=1)  # noqa: E731
    r = pso(f, -np.ones(4), np.ones(4),
            PSOConfig(particles=30, iterations=300, seed=1, topology=topology))
    assert r.fun < 1e-8
    np.testing.assert_allclose(r.x, 0.3, atol=1e-4)
    assert all(np.diff(r.history) <= 0)           # histórico monotônico


def test_pso_respeita_limites_e_reproduz():
    f = lambda X: np.sum(X, axis=1)  # noqa: E731
    c = PSOConfig(particles=10, iterations=50, seed=7)
    a = pso(f, np.zeros(3), np.ones(3), c)
    b = pso(f, np.zeros(3), np.ones(3), c)
    assert np.all(a.x >= 0) and np.all(a.x <= 1)
    np.testing.assert_array_equal(a.x, b.x)
    assert a.history == b.history


def test_pso_cancelamento():
    r = pso(lambda X: np.sum(X ** 2, axis=1), -np.ones(2), np.ones(2),
            PSOConfig(particles=8, iterations=1000, seed=0),
            callback=lambda it, f, x: it >= 5)
    assert r.stopped_by == "cancel" and r.iterations == 5


def test_pso_config_invalida():
    with pytest.raises(ValueError):
        PSOConfig(particles=1).check()
    with pytest.raises(ValueError):
        PSOConfig(topology="estrela").check()


# ---------------------------------------------------------------------------
# Ajuste
# ---------------------------------------------------------------------------
def test_ajuste_n1_recupera_parametros():
    d = _dados(1, ruido=5e-4)
    r = fit(d, FitSettings(n_stages=1, **RAPIDO, seed=3))
    s, v = r.stages[0], REF_STAGES[1][0]
    assert s.beta == pytest.approx(1.0)
    assert s.theta0 == pytest.approx(v.theta0, abs=0.5)
    assert s.duration == pytest.approx(v.duration, rel=0.03)
    assert s.m == pytest.approx(v.m, rel=0.05)
    assert r.metrics["xb"]["rmse"] < 7e-4


@pytest.mark.slow
def test_ajuste_n2_recupera_parametros():
    d = _dados(2, ruido=5e-4)
    r = fit(d, FitSettings(n_stages=2, particles=100, iterations=600,
                           runs=4, backend="numpy", parallel_runs="no",
                           seed=11))
    for s, v in zip(r.stages, REF_STAGES[2]):
        assert s.beta == pytest.approx(v.beta, abs=0.03)
        assert s.theta0 == pytest.approx(v.theta0, abs=1.0)
        assert s.duration == pytest.approx(v.duration, rel=0.08)


def test_estatisticas_dos_runs():
    d = _dados(2)
    r = fit(d, FitSettings(n_stages=2, **RAPIDO, seed=5))
    o = r.objective_stats
    assert o["runs"] == 2
    assert o["best"] <= o["median"] <= o["worst"]
    assert o["best"] == pytest.approx(min(x.objective for x in r.runs))
    assert set(r.param_stats) >= {"beta_1", "theta0_2", "m_1"}


def test_reprodutibilidade_por_seed():
    d = _dados(2)
    a = fit(d, FitSettings(n_stages=2, **RAPIDO, seed=9))
    b = fit(d, FitSettings(n_stages=2, **RAPIDO, seed=9))
    np.testing.assert_array_equal(a.best.x, b.best.x)


@pytest.mark.slow
def test_runs_paralelos_iguais_aos_sequenciais():
    d = _dados(2)
    base = dict(RAPIDO, parallel_runs="no")
    seq = fit(d, FitSettings(n_stages=2, **base, seed=4))
    par = fit(d, FitSettings(n_stages=2, **dict(base, parallel_runs="yes"),
                             workers=2, seed=4))
    for a, b in zip(seq.runs, par.runs):
        np.testing.assert_allclose(a.x, b.x, rtol=1e-10)


@pytest.mark.parametrize("mode", ["stick", "softmax", "explicit"])
def test_modos_de_beta_ajustam(mode):
    d = _dados(2)
    r = fit(d, FitSettings(n_stages=2, beta_mode=mode, **RAPIDO, seed=2))
    assert sum(s.beta for s in r.stages) == pytest.approx(1.0, abs=1e-9)
    assert r.metrics["xb"]["rmse"] < 5e-3


def test_fit_a_e_alvo_both():
    d = _dados(2, com_d=True)
    r = fit(d, FitSettings(n_stages=2, fit_a=True, fit_target="both",
                           **RAPIDO, seed=1))
    assert r.param.size == 9
    assert "dxb" in r.metrics and r.spec.fit_target == "both"


@pytest.mark.parametrize("metric", ["mae", "wrmse", "see", "mse"])
def test_outras_metricas(metric):
    d = _dados(1)
    r = fit(d, FitSettings(n_stages=1, metric=metric, **RAPIDO, seed=1))
    assert np.isfinite(r.best.objective)


def test_alvo_ausente_erro():
    d = _dados(1)
    with pytest.raises(ValueError):
        fit(d, FitSettings(n_stages=1, fit_target="dxb", **RAPIDO))


# ---------------------------------------------------------------------------
# Métricas e identificabilidade
# ---------------------------------------------------------------------------
def test_fit_metrics_valores():
    y = np.array([0.0, 1.0, 2.0, 3.0])
    m = fit_metrics(y, y + np.array([1.0, -1.0, 1.0, -1.0]), k=1)
    assert m["rmse"] == pytest.approx(1.0) and m["mae"] == pytest.approx(1.0)
    assert m["see"] == pytest.approx(np.sqrt(4 / 3))
    assert m["r2"] == pytest.approx(1 - 4 / 5)
    assert m["aic"] == pytest.approx(4 * np.log(1.0) + 2)
    assert m["bic"] == pytest.approx(np.log(4))
    assert m["durbin_watson"] == pytest.approx(12 / 4)


def test_avisos_de_estagios():
    st = [Stage(0.002, 0.0, 10, 1), Stage(0.5, 10.0, 20, 1),
          Stage(0.498, 10.1, 20.5, 1.02)]
    w = stage_warnings(st, theta_range=120.0)
    assert any("Stage 1 contributes less than 0.5%" in x for x in w)
    assert any("theta0_2 and theta0_3 are nearly identical" in x for x in w)
    assert any("redundant" in x for x in w)


def test_aviso_de_limite_no_ajuste():
    d = _dados(1)
    r = fit(d, FitSettings(n_stages=1, bounds={"m": [0.05, 1.0]}, **RAPIDO))
    assert any("m_1 reached upper bound" in w for w in r.warnings)


# ---------------------------------------------------------------------------
# Comparação 1..5
# ---------------------------------------------------------------------------
def test_block_folds_particao():
    folds = block_folds(403, 5)
    soma = sum(f.astype(int) for f in folds)
    assert np.all(soma == 1)
    assert all(abs(f.sum() - 403 / 5) < 10 for f in folds)


def test_recomendacao_parcimonia():
    tab = [{"n_stages": 1, "cv_rmse": 0.010, "bic": -10.0, "structural_warnings": 0},
           {"n_stages": 2, "cv_rmse": 0.00200, "bic": -45.0, "structural_warnings": 0},
           {"n_stages": 3, "cv_rmse": 0.00198, "bic": -52.0, "structural_warnings": 0},
           {"n_stages": 4, "cv_rmse": 0.00197, "bic": -49.0, "structural_warnings": 2}]
    n, motivo = recommend(tab, 0.05)
    assert n == 2 and "validação cruzada" in motivo
    for l in tab:
        l["cv_rmse"] = float("nan")
    n, motivo = recommend(tab, 0.05)
    assert n == 3 and "BIC" in motivo


@pytest.mark.slow
def test_comparacao_identifica_n2():
    d = _dados(2, ruido=1e-3, seed=3)
    res = compare_stages(d, [1, 2, 3], FitSettings(
        particles=80, iterations=500, patience=100, runs=3, backend="numpy",
        parallel_runs="no", seed=1), cv_folds=4)
    assert res["recommended"] == 2
    tab = {l["n_stages"]: l for l in res["table"]}
    assert tab[1]["cv_rmse"] > 2 * tab[2]["cv_rmse"]
    assert tab[2]["durbin_watson"] > 1.5 > tab[1]["durbin_watson"]
