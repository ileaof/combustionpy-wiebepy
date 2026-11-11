# -*- coding: utf-8 -*-
"""Misturas de combustíveis (blends) por percentual em base energia, massa
ou volume; padrão B10 do ensaio para as cargas de 45 % e 60 %."""
from __future__ import annotations

import pytest

from wiebepy.cfd.fuels import (
    ENSAIO_PADRAO, FUELS, all_fuel_specs, blend_breakdown, blend_from_text,
    blend_spec, blend_to_text, blend_total_from_injected, compute_blend,
    export_fuels_csv, import_fuels_csv, load_custom_fuels, save_custom_blend,
    validate_blend)


@pytest.fixture
def specs():
    return dict(FUELS)


def test_b10_do_ensaio_e_o_padrao_das_cargas():
    f = FUELS[ENSAIO_PADRAO["fuel"]]
    assert f.LHV_kJ_per_kg == pytest.approx(39191.3)
    assert f.stoich_AFR == pytest.approx(14.74)
    assert set(ENSAIO_PADRAO["cargas"]) == {"45%", "60%"}
    assert ENSAIO_PADRAO["cargas"]["45%"]["m_fuel_kg_per_cycle"] == \
        pytest.approx(9.42754647351e-06)
    assert ENSAIO_PADRAO["cargas"]["60%"]["rpm"] == pytest.approx(3311.0)


def test_base_massa_regra_de_mistura(specs):
    r = compute_blend([("diesel", 90), ("ethanol", 10)], "mass", specs)
    assert r["LHV_kJ_per_kg"] == pytest.approx(0.9 * 42600 + 0.1 * 26840)
    assert r["stoich_AFR"] == pytest.approx(0.9 * 14.5 + 0.1 * 9.0)
    assert sum(c["mass_fraction"] for c in r["components"]) == \
        pytest.approx(1.0)
    assert sum(c["energy_fraction"] for c in r["components"]) == \
        pytest.approx(1.0)


def test_base_energia_devolve_a_fracao_de_energia_declarada(specs):
    r = compute_blend([("B10_ensaio", 70), ("CH4", 30, "intake")],
                      "energy", specs)
    e = {c["fuel"]: c["energy_fraction"] for c in r["components"]}
    assert e["CH4"] == pytest.approx(0.30)
    y = {c["fuel"]: c["mass_fraction"] for c in r["components"]}
    # m_CH4/m_B10 = (0,3/50010)/(0,7/39191,3)
    assert y["CH4"] / y["B10_ensaio"] == pytest.approx(
        (0.3 / 50010.0) / (0.7 / 39191.3))


def test_base_volume_usa_massa_especifica(specs):
    r = compute_blend([("B10_ensaio", 90), ("ethanol", 10)], "volume", specs)
    y = {c["fuel"]: c["mass_fraction"] for c in r["components"]}
    esperado = 0.1 * 789.3 / (0.1 * 789.3 + 0.9 * 816.36)
    assert y["ethanol"] == pytest.approx(esperado)
    v = {c["fuel"]: c["volume_fraction"] for c in r["components"]}
    assert v["ethanol"] == pytest.approx(0.10)


@pytest.mark.parametrize("comps,base,trecho", [
    ([("B10_ensaio", 90), ("CH4", 10)], "volume", "só vale para líquidos"),
    ([("diesel", 90), ("ethanol", 10)], "volume", "massa específica"),
    ([("B10_ensaio", 90), ("ethanol", 20)], "energy", "somam 110"),
    ([("B10_ensaio", 100)], "energy", "pelo menos 2"),
    ([("B10_ensaio", 50), ("xyz", 50)], "mass", "não está cadastrado"),
    ([("B10_ensaio", 50), ("CH4", 50)], "molar", "base do percentual"),
])
def test_receitas_invalidas(specs, comps, base, trecho):
    erros = validate_blend(comps, base, specs)
    assert any(trecho in e for e in erros), erros


def test_dual_fuel_separa_massas_e_converte_massa_injetada(specs):
    f = blend_spec("x", "x", [("B10_ensaio", 70), ("CH4", 30, "intake")],
                   "energy", specs)
    m = 11.5833e-6
    b = blend_breakdown(f, m, specs)
    assert b["m_injected_kg"] + b["m_intake_kg"] == pytest.approx(m)
    assert b["Q_cycle_J"] == pytest.approx(m * f.LHV_kJ_per_kg * 1e3)
    tot = blend_total_from_injected(f, b["m_injected_kg"], specs)
    assert tot == pytest.approx(m)


def test_gravar_reler_e_csv(tmp_path):
    y = tmp_path / "fuels.yaml"
    assert save_custom_blend("B10_CH4_30E", "dual",
                             [("B10_ensaio", 70, "injected"),
                              ("CH4", 30, "intake")], "energy",
                             path=y) == []
    s = all_fuel_specs(y)["B10_CH4_30E"]
    assert s.is_blend and s.blend["basis"] == "energy"
    texto = blend_to_text(s.blend)
    assert blend_from_text(texto)["components"][1]["feed"] == "intake"
    csv = tmp_path / "f.csv"
    export_fuels_csv(csv, ["B10_CH4_30E"], path_yaml=y)
    y2 = tmp_path / "fuels2.yaml"
    res = import_fuels_csv(csv, path_yaml=y2)
    assert res["gravados"] == ["B10_CH4_30E"], res
    assert all_fuel_specs(y2)["B10_CH4_30E"].LHV_kJ_per_kg == \
        pytest.approx(s.LHV_kJ_per_kg)


def test_nome_embutido_e_mistura_aninhada_recusados(tmp_path):
    y = tmp_path / "fuels.yaml"
    assert save_custom_blend("diesel", "x", [("B10_ensaio", 50),
                                              ("ethanol", 50)], "mass",
                             path=y)
    save_custom_blend("M1", "m1", [("B10_ensaio", 50), ("ethanol", 50)],
                      "mass", path=y)
    erros = save_custom_blend("M2", "m2", [("M1", 50), ("CH4", 50)],
                              "energy", path=y)
    assert any("já é uma mistura" in e for e in erros)
    assert "M2" not in load_custom_fuels(y)


# ------------------------------------------------------------------- GUI
def test_gui_padrao_60_e_mistura_dual_fuel():
    pytest.importorskip("streamlit")
    from pathlib import Path
    from streamlit.testing.v1 import AppTest
    app = str(Path(__file__).resolve().parents[1] / "src" / "wiebepy"
              / "gui" / "app.py")
    at = AppTest.from_file(app, default_timeout=60).run()
    at.switch_page("app_pages/dados.py").run()
    assert not at.exception, [e.value for e in at.exception]
    [b for b in at.button if b.key == "p_padrao_60%"][0].click().run()
    assert not at.exception, [e.value for e in at.exception]
    m = at.session_state["engine"]
    assert m.rpm == pytest.approx(3311.0)
    assert m.m_fuel == pytest.approx(1.15832980973e-05)
    assert m.LHV == pytest.approx(39191.3)
    sel = [s for s in at.selectbox if s.key == "e_comb"][0]
    if "B10_CH4_30E" not in sel.options and not any(
            o.startswith("B10_CH4_30E") for o in sel.options):
        pytest.skip("mistura de exemplo não cadastrada em data/")
    sel.set_value("B10_CH4_30E").run()
    assert not at.exception, [e.value for e in at.exception]
    m = at.session_state["engine"]
    assert m.LHV == pytest.approx(all_fuel_specs()["B10_CH4_30E"]
                                  .LHV_kJ_per_kg)
    at.switch_page("app_pages/combustiveis.py").run()
    assert not at.exception, [e.value for e in at.exception]
    at.radio(key="fm_base").set_value("volume").run()
    assert not at.exception, [e.value for e in at.exception]
