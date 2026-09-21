# -*- coding: utf-8 -*-
"""GUI Streamlit (AppTest, sem navegador): páginas, carga de dados, ajuste e
comparação em segundo plano. Pulado se Streamlit não estiver instalado."""
from __future__ import annotations

import time
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

APP = str(Path(__file__).resolve().parents[1] / "src" / "wiebepy" / "gui" / "app.py")
PAGINAS = ["app_pages/dados.py", "app_pages/modelo.py", "app_pages/ajuste.py",
           "app_pages/comparacao.py", "app_pages/exportar.py",
           "app_pages/desempenho.py"]


def _app():
    return AppTest.from_file(APP, default_timeout=60).run()


def _sem_erros(at):
    assert not at.exception, [e.value for e in at.exception]


def _carrega_exemplo(at, nome="synthetic_2stage"):
    at.switch_page("app_pages/dados.py").run()
    at.segmented_control(key="tipo_dado").set_value("xb").run()
    at.segmented_control(key="fonte_dados").set_value("Exemplo sintético").run()
    at.selectbox[0].set_value(nome).run()
    [b for b in at.button if b.label == "Carregar exemplo"][0].click().run()
    _sem_erros(at)
    assert at.session_state["data"] is not None


def _espera_job(at, limite=180):
    t0 = time.time()
    while at.session_state["job"] is not None:
        assert time.time() - t0 < limite, "tarefa não terminou"
        time.sleep(0.5)
        at.run()
    _sem_erros(at)


@pytest.mark.parametrize("pagina", PAGINAS)
def test_paginas_sem_dados(pagina):
    at = _app()
    at.switch_page(pagina).run()
    _sem_erros(at)


def test_botao_ajuda_abre_help():
    at = _app()
    [b for b in at.button if b.key == "botao_ajuda"][0].click().run()
    _sem_erros(at)
    assert len(at.get("iframe")) == 1


def test_modelo_edita_e_valida():
    at = _app()
    at.session_state["mode"] = "xb"
    at.switch_page("app_pages/modelo.py").run()
    at.segmented_control(key="modelo_n").set_value(4).run()
    _sem_erros(at)
    assert len(at.session_state["model_stages"]) == 4
    assert len(at.get("vega_lite_chart")) >= 2


def test_dados_ajuste_e_exportacao():
    at = _app()
    _carrega_exemplo(at)
    at.switch_page("app_pages/ajuste.py").run()
    at.number_input[0].set_value(1).run()                     # runs
    for rotulo, valor in (("Partículas", 40), ("Iterações", 150),
                          ("Paciência", 50)):
        [w for w in at.number_input if w.label == rotulo][0].set_value(valor)
    [s for s in at.selectbox if s.label == "Backend"][0].set_value("numpy")
    [b for b in at.button if "Iniciar" in b.label][0].click().run()
    _espera_job(at)
    r = at.session_state["fit_result"]
    assert r is not None and r.settings.n_stages == 2
    assert r.metrics["xb"]["rmse"] < 1e-2
    [b for b in at.button if b.label == "Aplicar ao modelo"][0].click().run()
    _sem_erros(at)
    at.switch_page("app_pages/modelo.py").run()
    _sem_erros(at)
    at.switch_page("app_pages/exportar.py").run()
    [b for b in at.button if b.label == "Preparar .zip"][0].click().run()
    _sem_erros(at)
    assert len(at.session_state["exp_zip"]) > 10_000


def test_comparacao():
    at = _app()
    _carrega_exemplo(at, "synthetic_1stage")
    at.switch_page("app_pages/comparacao.py").run()
    at.pills[0].set_value([1, 2]).run()
    [w for w in at.number_input if w.label == "Runs por N"][0].set_value(1)
    [w for w in at.number_input if w.label == "Folds da validação cruzada"][0].set_value(3)
    [w for w in at.number_input if w.label == "Partículas"][0].set_value(40)
    [w for w in at.number_input if w.label == "Iterações"][0].set_value(150)
    [s for s in at.selectbox if s.label == "Backend"][0].set_value("numpy")
    [b for b in at.button if b.label == "Comparar"][0].click().run()
    _espera_job(at)
    res = at.session_state["compare_result"]
    assert res is not None and {1, 2} == set(res["results"])
    assert res["recommended"] == 1


# ---------------------------------------------------------------------------
# Modo pressão
# ---------------------------------------------------------------------------
def _carrega_ensaio(at):
    at.switch_page("app_pages/dados.py").run()
    assert at.session_state["mode"] == "pressure"         # tipo padrão
    at.button(key="p_exemplo").click().run()
    _sem_erros(at)
    assert at.session_state["pdata"].n == 459
    labels = [w.label for w in at.selectbox] + [w.label for w in at.number_input]
    for rotulo in ("Separador", "Cabeçalho", "Unidade do ângulo",
                   "Unidade da pressão", "θ mín [rad]", "θ máx [rad]"):
        assert rotulo in labels, rotulo


def test_modo_pressao_ajuste_e_paginas():
    at = _app()
    _carrega_ensaio(at)
    at.switch_page("app_pages/modelo.py").run()
    _sem_erros(at)
    at.switch_page("app_pages/ajuste.py").run()
    [w for w in at.number_input if w.label == "Runs"][0].set_value(1)
    [w for w in at.number_input if w.label == "Partículas"][0].set_value(30)
    [w for w in at.number_input if w.label == "Iterações"][0].set_value(60)
    [b for b in at.button if "Iniciar" in b.label][0].click().run()
    _espera_job(at)
    r = at.session_state["pfit_result"]
    assert r is not None and r.metrics["r2"] > 0.99
    assert any(t.key == "pv_ajuste_log" for t in at.toggle)   # diagrama P–V
    at.toggle(key="pv_ajuste_log").set_value(True).run()
    _sem_erros(at)
    at.button(key="pa_rel_gerar").click().run()               # relatório HTML
    _sem_erros(at)
    rel = at.session_state["_rel_pa_rel"]
    assert rel.startswith(b"<!DOCTYPE html>") and b"Motor e constantes" in rel
    [b for b in at.button if b.key == "pa_aplicar"][0].click().run()
    for p in ("app_pages/modelo.py", "app_pages/exportar.py",
              "app_pages/comparacao.py"):
        at.switch_page(p).run()
        _sem_erros(at)


@pytest.mark.parametrize("texto, sep, cab", [
    ("-2.0\t1.2\n-1.9\t1.3\n-1.8\t1.5\n", "auto", "auto"),
    ("theta;P\n-2.0;1.2\n-1.9;1.3\n-1.8;1.5\n", "auto", "auto"),
    ("ang,p,t\n-2.0,1.2,300\n-1.9,1.3,301\n-1.8,1.5,302\n", ",", "sim"),
    ("# comentario\n-2.0 1.2\n-1.9 1.3\n-1.8 1.5\n", "espaços/tab", "não"),
])
def test_leitura_pressao_formatos(texto, sep, cab):
    from wiebepy.gui.pressure_ui import _ler_tabela
    df = _ler_tabela(texto.encode(), sep, cab)
    assert df.shape[0] == 3 and df.shape[1] >= 2
    assert float(df.iloc[0, 0]) == -2.0 and float(df.iloc[2, 1]) == 1.5


def test_modelo_modo_pressao_simula():
    at = _app()
    _carrega_ensaio(at)
    at.switch_page("app_pages/modelo.py").run()
    _sem_erros(at)
    at.segmented_control(key="pmodelo_n").set_value(3).run()
    _sem_erros(at)
    assert len(at.session_state["pmodel"]["stages"]) == 3
    assert any(m.label == "RMSE [kPa]" for m in at.metric)
    assert any(t.key == "pv_modelo_log" for t in at.toggle)
