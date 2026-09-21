# -*- coding: utf-8 -*-
"""Entrada/saída, configuração, API MultiStageWiebe e CLI."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from wiebepy import MultiStageWiebe
from wiebepy.cli.parser import _main
from wiebepy.core import DataError, multistage_wiebe
from wiebepy.io.config import ConfigError, load_config, resolve
from wiebepy.io.readers import read_data, theta_grid

from conftest import REF_STAGES

RAIZ = Path(__file__).resolve().parents[1]
EXEMPLOS = RAIZ / "examples"


def _grava(p: Path, texto: str) -> Path:
    p.write_text(texto, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Leitura
# ---------------------------------------------------------------------------
def test_csv_com_cabecalho_e_comentario(tmp_path):
    p = _grava(tmp_path / "d.csv", "# c\ntheta,xb,dxb_dtheta\n0,0,0\n1,0.1,0.1\n"
               "2,0.3,0.2\n3,0.6,0.2\n4,0.9,0.1\n")
    d = read_data(p)
    assert d.n == 5 and d.dxb is not None and d.xb[2] == 0.3


def test_txt_sem_cabecalho_espacos(tmp_path):
    p = _grava(tmp_path / "d.txt", "\n".join(f"{t} {t / 10}" for t in range(8)))
    d = read_data(p)
    assert d.dxb is None and d.xb[-1] == pytest.approx(0.7)


def test_dat_ponto_e_virgula_e_sigma(tmp_path):
    p = _grava(tmp_path / "d.dat", "angle;mfb;sigma\n" + "\n".join(
        f"{t};{t / 10};0.5" for t in range(6)))
    d = read_data(p)
    np.testing.assert_allclose(d.weights, 4.0)


def test_json_e_ordenacao(tmp_path):
    p = _grava(tmp_path / "d.json", json.dumps(
        {"theta": [3, 1, 2, 0, 4], "dxb_dtheta": [0.3, 0.1, 0.2, 0.0, 0.1]}))
    d = read_data(p)
    np.testing.assert_array_equal(d.theta, [0, 1, 2, 3, 4])
    assert d.xb is None and d.dxb[3] == 0.3


@pytest.mark.parametrize("conteudo, trecho", [
    ("a,b\n1,2\n", "theta"),
    ("theta,xb\n0,0\n0,0.1\n1,0.2\n2,0.3\n3,0.4\n", "repetidos"),
    ("theta,xb\n0,x\n", "não numérico"),
])
def test_erros_de_dados(tmp_path, conteudo, trecho):
    p = _grava(tmp_path / "d.csv", conteudo)
    with pytest.raises(DataError, match=trecho):
        read_data(p)


def test_extensao_invalida(tmp_path):
    with pytest.raises(DataError):
        read_data(_grava(tmp_path / "d.xlsx", "x"))


def test_exemplos_sinteticos_existem():
    for n in range(1, 6):
        d = read_data(EXEMPLOS / "data" / f"synthetic_{n}stage.csv")
        assert d.n == 601 and d.xb is not None and d.dxb is not None


def test_theta_grid():
    g = theta_grid(-20, 100, 0.1)
    assert g.size == 1201 and g[0] == -20 and g[-1] == pytest.approx(100)


# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("nome", ["config_example.yaml", "config_example.json",
                                  "config_example.toml"])
def test_configs_de_exemplo(nome):
    cfg = resolve(EXEMPLOS / nome)
    assert 1 <= cfg["model"]["stages"] <= 5
    assert cfg["optimization"]["method"] == "pso"


def test_precedencia_cli(tmp_path):
    p = _grava(tmp_path / "c.yaml", "model: {stages: 4}\nparallel: {workers: 3}\n")
    cfg = resolve(p, {"model": {"stages": 2}, "parallel": {"workers": None}})
    assert cfg["model"]["stages"] == 2 and cfg["parallel"]["workers"] == 3


def test_config_secao_desconhecida(tmp_path):
    with pytest.raises(ConfigError, match="desconhecidas"):
        load_config(_grava(tmp_path / "c.json", '{"modelo": {}}'))


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
def test_api_avaliacao_e_serializacao(tmp_path, stages):
    m = MultiStageWiebe(stages=stages)
    th = np.linspace(-20, 100, 301)
    np.testing.assert_array_equal(m.evaluate(th), multistage_wiebe(th, stages))
    cx, cd = m.contributions(th)
    assert cx.shape == (len(stages), th.size)
    p = m.save(tmp_path / "model.json")
    m2 = MultiStageWiebe.load(p)
    assert m2.stages == m.stages and m2.n_stages == len(stages)
    np.testing.assert_array_equal(m2.derivative(th), m.derivative(th))


def test_api_padroes_e_erros():
    assert MultiStageWiebe(n_stages=4).n_stages == 4
    with pytest.raises(ValueError):
        MultiStageWiebe(n_stages=6)
    with pytest.raises(ValueError):
        MultiStageWiebe(n_stages=2, stages=REF_STAGES[3])


def test_api_fit():
    th = np.linspace(-20, 100, 301)
    xb = multistage_wiebe(th, REF_STAGES[1])
    m = MultiStageWiebe(n_stages=1)
    r = m.fit(th, xb, backend="numpy", runs=1, particles=40, iterations=200,
              parallel_runs="no")
    assert r.metrics["xb"]["rmse"] < 1e-4
    assert m.stages[0].duration == pytest.approx(60.0, rel=1e-2)
    with pytest.raises(ValueError):
        m.fit(th, xb, optimizer="ga")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def test_cli_help_model_e_exemplos(capsys):
    assert _main(["--help-model"]) == 0
    assert "Σ_j β_j" in capsys.readouterr().out
    assert _main(["--help-examples"]) == 0
    out = capsys.readouterr().out
    for termo in ("single-Wiebe", "double-Wiebe", "triple-Wiebe", "4-stage",
                  "5-stage", "--gpu", "--compare-stages", "--workers"):
        assert termo in out


def test_cli_help_e_versao(capsys):
    with pytest.raises(SystemExit) as e:
        _main(["--help"])
    assert e.value.code == 0
    out = capsys.readouterr().out
    for termo in ("--stages", "--backend", "--theta-step", "--save-plots",
                  "unidades", "Formatos de entrada"):
        assert termo.lower() in out.lower()
    with pytest.raises(SystemExit):
        _main(["--version"])


@pytest.mark.parametrize("n", [1, 2, 3, 4, 5])
def test_cli_avaliacao(tmp_path, n):
    assert _main(["--stages", str(n), "--theta-step", "0.5", "--quiet",
                  "--save-plots", "--output", str(tmp_path)]) == 0
    for f in ("results.csv", "parameters.csv", "model.json",
              "configuration_used.yaml", "plots/fig1_xb.png",
              "plots/fig4_contrib_dxb.png"):
        assert (tmp_path / f).exists(), f
    cab = (tmp_path / "results.csv").read_text().splitlines()[0]
    assert f"beta{n}_xb{n}" in cab


def test_cli_modelo_salvo(tmp_path):
    assert _main(["--model", str(EXEMPLOS / "model_2stage.json"), "--quiet",
                  "--output", str(tmp_path)]) == 0
    assert "beta2_xb2" in (tmp_path / "results.csv").read_text()


def test_cli_ajuste(tmp_path):
    assert _main(["--stages", "1", "--optimize", "--input",
                  str(EXEMPLOS / "data" / "synthetic_1stage.csv"),
                  "--fit-target", "xb", "--runs", "1", "--population", "30",
                  "--iterations", "150", "--backend", "numpy", "--json",
                  "--save-plots", "--quiet", "--output", str(tmp_path)]) == 0
    for f in ("results.csv", "parameters.csv", "metrics.csv",
              "run_statistics.csv", "configuration_used.yaml",
              "results.json", "model.json", "warnings.txt",
              "plots/fig5_fit.png", "plots/fig6_residuals.png",
              "plots/fig7_convergence.png"):
        assert (tmp_path / f).exists(), f
    res = json.loads((tmp_path / "results.json").read_text(encoding="utf-8"))
    assert res["n_stages"] == 1 and res["metrics"]["xb"]["rmse"] < 3e-3


def test_cli_erros_de_uso(tmp_path):
    assert _main(["--optimize", "--quiet"]) == 2                 # sem --input
    assert _main(["--stages", "7", "--quiet", "--output", str(tmp_path)]) == 2
    assert _main(["--input", str(tmp_path / "nao.csv"), "--optimize",
                  "--quiet"]) == 2
    assert _main(["--compare-stages", "1", "2", "--quiet"]) == 2


def test_cli_devices(capsys):
    assert _main(["--devices"]) == 0
    assert "Logical cores" in capsys.readouterr().out


@pytest.mark.slow
def test_cli_comparacao(tmp_path):
    assert _main(["--compare-stages", "1", "2", "--input",
                  str(EXEMPLOS / "data" / "synthetic_2stage.csv"),
                  "--fit-target", "xb", "--runs", "2", "--population", "60",
                  "--iterations", "300", "--cv-folds", "3", "--backend",
                  "numpy", "--quiet", "--save-plots", "--output",
                  str(tmp_path)]) == 0
    assert (tmp_path / "comparison.csv").exists()
    assert (tmp_path / "N2" / "model.json").exists()
    assert (tmp_path / "plots" / "comparison.png").exists()
