# -*- coding: utf-8 -*-
"""Testes do módulo CFD opcional (fonte Wiebe, config, geometria,
combustíveis, case builder).

Estes testes NÃO exigem OpenFOAM/WSL2: com CFD desabilitado o restante
do wiebepy não deve importar nada deste pacote (ver test_import_off).
Os testes que exigem solver real estão marcados com
@pytest.mark.skipif(sem OpenFOAM) e são executados em ambiente de
desenvolvimento (ver docs/cfd/install.md).
"""
import math
from pathlib import Path

import numpy as np
import pytest
import yaml

from wiebepy.cfd import cfd_enabled
from wiebepy.cfd.config import CfdConfig, CaseState
from wiebepy.cfd.fuels import FUELS, fuel_summary
from wiebepy.cfd.geometry import PistonKinematics, motion_report
from wiebepy.cfd.sources import (DEG_PER_S_PER_RPM, RAD_PER_S_PER_RPM,
                                 dtheta_dt, energy_check, function1_table,
                                 qdot_power, qdot_time_series, table_text)
from wiebepy.core.core import multistage_wiebe
from wiebepy.core.derivatives import multistage_wiebe_derivative
from wiebepy.pressure.engine import EngineConfig

ENGINE = EngineConfig(bore=0.086, stroke=0.070, rod_length=0.1175, Rc=17.0,
                      rpm=3396.20, m_fuel=9.42754647351e-6, LHV=39191.3,
                      T1=308.15, Tw=440.0)

CFG_DICT = {
    "enabled": True,
    "mode": "prescribed_wiebe",
    "interval": {"angle_unit": "deg", "start": -120, "end": 120},
    "initial": {"P_kPa": 250, "T_K": 800},
    "walls": {"Tw_K": 440},
    "turbulence": {"model": "laminar"},
    "fuel": {"name": "diesel", "feed": "premixed_gas"},
    "wiebe": {"source": "parameters",
              "parameters": [{"beta": 1.0, "theta0": -5, "duration": 40,
                              "m": 2.0}]},
}


# ------------------------------------------------------------------ config
def test_cfd_disabled_by_default():
    assert cfd_enabled({}) is False
    assert cfd_enabled({"cfd": None}) is False
    assert cfd_enabled({"cfd": {"enabled": False}}) is False
    assert cfd_enabled({"cfd": {"enabled": True}}) is True


def test_derived_interval_duration_s_conversoes():
    """Duração física da janela: Δθ[rad] / (2π·RPM/60); deg e rad
    (mesma janela) devem dar o MESMO valor em segundos."""
    cfg = CfdConfig.from_dict({"wiebe": CFG_DICT["wiebe"]})
    d = cfg.derived(ENGINE)
    # −120°…+120° = 240° = 2/3 de volta a 3396,2 rpm:
    # 2/3 × (60/3396,2) s = 0,011776 s
    esperado = (240.0 / 360.0) * (60.0 / ENGINE.rpm)
    assert math.isclose(d["interval_duration_s"], esperado, rel_tol=1e-12)
    # a mesma janela em rad produz o mesmo tempo
    cfg_rad = CfdConfig.from_dict({"wiebe": CFG_DICT["wiebe"],
                                   "interval": {"angle_unit": "rad",
                                                "start": -2.0943951023931953,
                                                "end": 2.0943951023931953}})
    assert math.isclose(cfg_rad.derived(ENGINE)["interval_duration_s"],
                        esperado, rel_tol=1e-9)
    # coerência com a conversão da fonte: Δθ[rad] / (dθ/dt) = duração
    from wiebepy.cfd.sources import dtheta_dt
    assert math.isclose(
        (cfg_rad.derived(ENGINE)["interval_end_rad"]
         - cfg_rad.derived(ENGINE)["interval_start_rad"])
        / dtheta_dt("rad", ENGINE.rpm),
        esperado, rel_tol=1e-12)


def test_config_defaults_and_validation():
    cfg = CfdConfig.from_dict({"wiebe": CFG_DICT["wiebe"]})
    assert cfg.enabled is False                # CFD desabilitado por padrão
    assert cfg.mode == "prescribed_wiebe"
    assert cfg.validate() == []


def test_config_reactive_validacao():
    """Modo reativo (R2): volume fixo, mecanismo obrigatório e regras
    bloqueantes (pistão móvel é R3; PaSR é degrau futuro)."""
    base = {"mode": "reactive",
            "reaction": {"mechanism": "inexistente_mecanismo"}}
    erros = CfdConfig.from_dict(base).validate()
    assert any("moving_piston=false" in e for e in erros)
    assert any("não encontrado" in e for e in erros)
    # mecanismo existente + volume fixo valida
    mecanismo = str(Path(__file__).resolve().parent.parent
                    / "examples" / "cfd" / "mechanisms" / "burke2012")
    ok = CfdConfig.from_dict({"mode": "reactive",
                              "geometry": {"moving_piston": False},
                              "walls": {"model": "adiabatic"},
                              "reaction": {"mechanism": mecanismo}})
    assert ok.validate() == []
    # parede a T fixa no modo reativo é bloqueante (portão R2c: ∫Q̇dVdt = ΔU
    # só fecha sem troca de calor com as paredes)
    ruim = CfdConfig.from_dict({"mode": "reactive",
                                "geometry": {"moving_piston": False},
                                "reaction": {"mechanism": mecanismo}})
    assert cfg_has_error(ruim, "walls.model=adiabatic")
    # pistão móvel com reação é bloqueante (R3 — verificação pendente)
    ruim = CfdConfig.from_dict({"mode": "reactive",
                                "geometry": {"moving_piston": True},
                                "reaction": {"mechanism": mecanismo}})
    assert cfg_has_error(ruim, "moving_piston=false")
    # modelo de combustão diferente de laminar é bloqueante no R2
    ruim = CfdConfig.from_dict({"mode": "reactive",
                                "geometry": {"moving_piston": False},
                                "reaction": {"mechanism": mecanismo,
                                             "combustion_model": "PaSR"}})
    assert cfg_has_error(ruim, "laminar")
    # φ ≤ 0 é bloqueante
    ruim = CfdConfig.from_dict({"mode": "reactive",
                                "geometry": {"moving_piston": False},
                                "reaction": {"mechanism": mecanismo,
                                             "equivalence_ratio": 0.0}})
    assert cfg_has_error(ruim, "equivalence_ratio deve ser > 0")
    # composição explícita que não soma 1 é bloqueante
    ruim = CfdConfig.from_dict({"mode": "reactive",
                                "geometry": {"moving_piston": False},
                                "reaction": {"mechanism": mecanismo,
                                             "composition":
                                                 {"H2": 0.5, "O2": 0.5,
                                                  "N2": 0.5}}})
    assert cfg_has_error(ruim, "devem somar 1")


def test_config_interval_validation():
    ruim = CfdConfig.from_dict({"interval": {"start": 120, "end": -120},
                                "wiebe": CFG_DICT["wiebe"]})
    assert cfg_has_error(ruim, "end deve ser > start")


def test_config_wall_model_e_gas_validation():
    # modelo de parede inválido é bloqueante
    ruim = CfdConfig.from_dict({"walls": {"model": "qualquer"},
                                "wiebe": CFG_DICT["wiebe"]})
    assert cfg_has_error(ruim, "fixed_temperature ou adiabatic")
    # adiabatic com Tw explícito é bloqueante (nenhuma inferência silenciosa)
    ruim = CfdConfig.from_dict({"walls": {"model": "adiabatic", "Tw_K": 500},
                                "wiebe": CFG_DICT["wiebe"]})
    assert cfg_has_error(ruim, "não usa Tw_K")
    # adiabatic sem Tw_K (padrão) valida
    ok = CfdConfig.from_dict({"walls": {"model": "adiabatic"},
                              "wiebe": CFG_DICT["wiebe"]})
    assert ok.validate() == []
    # gas com Cp ≤ 0 é bloqueante
    ruim = CfdConfig.from_dict({"gas": {"Cp_J_kgK": 0},
                                "wiebe": CFG_DICT["wiebe"]})
    assert cfg_has_error(ruim, "devem ser > 0")


def cfg_has_error(cfg, trecho):
    return any(trecho in e for e in cfg.validate())


def test_wiebe_stages_deg_conversion():
    cfg = CfdConfig.from_dict({
        "wiebe": {"source": "parameters",
                  "parameters": [{"beta": 1.0, "theta0": -10, "duration": 45,
                                  "m": 2.0}]},
        "interval": {"angle_unit": "deg", "start": -120, "end": 120},
    })
    stages = cfg.load_wiebe_stages()
    th = np.linspace(-1.5, 1.5, 4000)
    x = multistage_wiebe(th, stages)
    assert x[-1] == pytest.approx(1.0, abs=1e-9)
    # pico da derivada: z_pico = (m/(a(m+1)))^(1/(m+1)) ≈ 0,459 (m=2,
    # a=6,908); θ_pico = θ0 + z_pico·Δθ
    dxb = multistage_wiebe_derivative(th, stages)
    th_peak = th[np.argmax(dxb)]
    assert math.degrees(th_peak) == pytest.approx(
        -10 + 0.4587 * 45, abs=2.0)


# ------------------------------------------------------------- fonte Wiebe
@pytest.mark.parametrize("n_stages", [1, 2, 3, 4, 5])
@pytest.mark.parametrize("unit, w", [("deg", DEG_PER_S_PER_RPM),
                                     ("rad", RAD_PER_S_PER_RPM)])
def test_energy_conservation_n1_a_n5(n_stages, unit, w):
    """§17: conservação ∫Q̇dt = m_f·PCI·Δx_b para N = 1..5 e unidades
    angular deg e rad; conversões dθ/dt explícitas."""
    stages = _stages(n_stages)
    theta = _grid(unit)
    m_f, lhv = 1.0e-5, 45000.0
    chk = energy_check(theta, stages, m_f, lhv, unit, 3000.0)
    assert chk["ok"], chk
    assert chk["rel_error"] < 1e-3
    assert abs(dtheta_dt(unit, 3000.0) - w * 3000.0) < 1e-9 * w * 3000.0


@pytest.mark.parametrize("n_stages", [1, 2, 3, 4, 5])
def test_qdot_units_and_peak(n_stages):
    """Q̇ em W: m_f[kg]·PCI[kJ/kg] → kJ/s = kW → ×1e3 = W (§7)."""
    stages = _stages(n_stages)
    theta = _grid("rad")
    m_f, lhv = 2.0e-5, 50000.0
    q = qdot_power(theta, stages, m_f, lhv, "rad", 1500.0)
    # energia integrada em θ (rad) × dθ/dt → J
    w = dtheta_dt("rad", 1500.0)
    E = np.trapezoid(q, theta) / w
    esperado = m_f * lhv * 1e3 * (multistage_wiebe(theta, stages)[-1]
                                  - multistage_wiebe(theta, stages)[0])
    assert E == pytest.approx(esperado, rel=1e-3)


@pytest.mark.parametrize("n_stages", [1, 2, 3, 4, 5])
def test_function1_table_conserves_energy(n_stages):
    """Tabela Q(CA) para o fvModel heatSource: integral em segundos
    confere com a energia do ciclo; formato do OpenFOAM 13."""
    stages = _stages(n_stages)
    theta = _grid("rad")
    pares = function1_table(theta, stages, 1e-5, 45000.0, "rad", 3000.0)
    assert len(pares) >= 400
    ca = np.array([p[0] for p in pares])
    q = np.array([p[1] for p in pares])
    assert ca[0] == pytest.approx(math.degrees(theta[0]), abs=1e-6)
    assert ca[-1] == pytest.approx(math.degrees(theta[-1]), abs=1e-6)
    E_s = np.trapezoid(q, ca) / (6.0 * 3000.0)
    chk = energy_check(theta, stages, 1e-5, 45000.0, "rad", 3000.0)
    assert abs(E_s - chk["integral_J"]) / chk["integral_J"] < 0.005
    texto = table_text(theta, stages, 1e-5, 45000.0, "rad", 3000.0)
    assert texto.rstrip().endswith(");")   # entrada de dicionário OF13


def test_function1_table_density_uniform_conservative():
    """Tabela q'''(CA) = Q̇(CA)/V₀(CA): q'''·V₀ reproduz Q̇ ponto a ponto
    (distribuição uniforme §7) e ∫q'''·V₀dt = energia do ciclo; formato
    de dicionário OF13."""
    from wiebepy.cfd.sources.wiebe_heat_release import (
        function1_table_density, table_text_density)
    from wiebepy.cfd.geometry import PistonKinematics
    stages = _stages(3)
    theta = _grid("rad")
    k = PistonKinematics(bore=ENGINE.bore, stroke=ENGINE.stroke,
                         rod_length=ENGINE.rod_length, Rc=ENGINE.Rc,
                         rpm=ENGINE.rpm)
    V0 = k.volume(theta)
    pares = function1_table_density(theta, stages, 1e-5, 45000.0, "rad",
                                    3000.0, V0)
    assert len(pares) >= 400
    ca = np.array([p[0] for p in pares])
    q3 = np.array([p[1] for p in pares])
    V0u = np.interp(ca, np.degrees(theta), V0)
    # identidade ponto a ponto: q'''·V₀ = Q̇
    from wiebepy.cfd.sources.wiebe_heat_release import qdot_power
    q_ref = qdot_power(np.radians(ca), stages, 1e-5, 45000.0, "rad", 3000.0)
    assert q3 * V0u == pytest.approx(q_ref, rel=1e-6)
    # energia: ∫ q'''·V₀ dCA/(6·RPM) = ciclo
    E_s = np.trapezoid(q3 * V0u, ca) / (6.0 * 3000.0)
    chk = energy_check(theta, stages, 1e-5, 45000.0, "rad", 3000.0)
    assert abs(E_s - chk["integral_J"]) / chk["integral_J"] < 0.005
    # pistão fixo: volume escalar → q''' = Q̇/V₀ constante na razão,
    # e q'''·V₀ reproduz Q̇ ponto a ponto
    pares_fixo = function1_table_density(theta, stages, 1e-5, 45000.0,
                                         "rad", 3000.0, float(V0[0]))
    q3f = np.array([p[1] for p in pares_fixo])
    assert q3f * float(V0[0]) == pytest.approx(q_ref, rel=1e-6)
    texto = table_text_density(theta, stages, 1e-5, 45000.0, "rad", 3000.0, V0)
    assert texto.rstrip().endswith(");")


def test_case_builder_writes_q_density_table(tmp_path):
    """Com distribuição uniforme + pistão móvel, o fvModels prescreve a
    densidade q''' (não Q): o modo Q do OF13 congela 1/V(zone) na
    construção e não é conservativo com malha móvel."""
    from wiebepy.cfd.case_builder import CaseBuilder
    cfg = CfdConfig.from_dict(CFG_DICT)
    b = CaseBuilder(cfg, ENGINE, solver_info={"version": "13"},
                    heat_enabled=True, moving_override=True)
    d = b.build(tmp_path / "caso_q")
    fv = (d / "constant/fvModels").read_text(encoding="utf-8")
    assert "\n    q\n" in fv          # campo q, não Q
    assert "\n    Q\n" not in fv
    import yaml as _yaml
    cc = _yaml.safe_load((d / "case_config.yaml").read_text(encoding="utf-8"))
    assert cc["heat_source"]["table_form"] == "q_density_W_per_m3"   # entrada de dicionário OF13


def test_case_builder_region_toposetdict_em_system(tmp_path):
    """Com distribution=region, o topoSetDict é gravado em
    <caso>/system/ (onde a validação e o adapter o procuram) e NÃO em
    <caso>/constant/system/ — antes da correção o modo region nunca
    chegou a executar (verification.md §3e)."""
    from wiebepy.cfd.case_builder import CaseBuilder
    cfg_dict = dict(CFG_DICT)
    cfg_dict["heat_source"] = {"distribution": "region",
                               "region": "zonaTeste"}
    cfg = CfdConfig.from_dict(cfg_dict)
    b = CaseBuilder(cfg, ENGINE, solver_info={"version": "13"},
                    heat_enabled=True, moving_override=True)
    d = b.build(tmp_path / "caso_region")
    ts = d / "system/topoSetDict"
    assert ts.is_file()
    assert not (d / "constant/system/topoSetDict").exists()
    assert "cellZoneSet" in ts.read_text(encoding="utf-8")
    assert "zonaTeste" in ts.read_text(encoding="utf-8")
    # no modo region o fvModels ainda usa Q (limitação OF13, §3e)
    fv = (d / "constant/fvModels").read_text(encoding="utf-8")
    assert "\n    Q\n" in fv


def _stages(n):
    betas = np.array([1.0 / n] * n)
    ts = []
    th0 = -15.0
    for j in range(n):
        ts.append({"beta": float(betas[j]), "theta0": th0 + 10 * j,
                   "duration": 35.0, "m": 2.0})
    return ts


def _grid(unit):
    a0, a1 = (math.radians(-40), math.radians(100))
    return np.linspace(a0, a1, 4000)


# ------------------------------------------------------------- geometria
def test_piston_kinematics_reuses_engine_volume():
    k = PistonKinematics(bore=ENGINE.bore, stroke=ENGINE.stroke,
                         rod_length=ENGINE.rod_length, Rc=ENGINE.Rc,
                         rpm=ENGINE.rpm)
    Vc = ENGINE.Vd / (ENGINE.Rc - 1.0)
    th = np.linspace(-math.pi, math.pi, 721)
    V = k.volume(th)
    assert V.min() == pytest.approx(Vc, rel=1e-6)
    assert V.max() == pytest.approx(Vc + ENGINE.Vd, rel=1e-6)
    # y(0) = 0 (PMP) e V(0) = V_min
    assert k.piston_displacement(0.0) == pytest.approx(0.0, abs=1e-12)
    assert V[360] == pytest.approx(Vc, rel=1e-6)


def test_motion_report_hypotheses():
    k = PistonKinematics(bore=ENGINE.bore, stroke=ENGINE.stroke,
                         rod_length=ENGINE.rod_length, Rc=ENGINE.Rc,
                         rpm=ENGINE.rpm)
    rep = motion_report(k, math.radians(-120), math.radians(120))
    Vc = ENGINE.Vd / (ENGINE.Rc - 1.0)
    # no intervalo [-120°, 120°] o volume máximo é nas extremidades
    assert rep["V_min_m3"] == pytest.approx(Vc, rel=1e-6)
    assert rep["V_max_m3"] == pytest.approx(k.volume(math.radians(120)),
                                            rel=1e-6)
    assert rep["V_start_m3"] == pytest.approx(rep["V_end_m3"], rel=1e-12)
    assert rep["hypotheses"]


# ---------------------------------------------------------- combustíveis
def test_fuels_registry_sources():
    for nome, f in FUELS.items():
        assert f.LHV_kJ_per_kg > 0
        assert f.LHV_source, f"combustível {nome} sem fonte citada"
        assert f.mechanism is None            # modo reativo é futuro
    assert FUELS["diesel"].LHV_kJ_per_kg > FUELS["ethanol"].LHV_kJ_per_kg
    s = fuel_summary("CH4", 1e-5)
    assert s["Q_cycle_J"] == pytest.approx(
        1e-5 * FUELS["CH4"].LHV_kJ_per_kg * 1e3, rel=1e-9)
    # CH4 puro ≠ gás natural (§10)
    assert "gás natural" in FUELS["CH4"].remarks.lower()


# ------------------------------------------ cadastro permanente + CSV
def _registro_exemplo(nome="C3H8"):
    return {
        "name": nome, "display": "Propano", "formula": "C3H8",
        "phase": "gas", "feed": "premixed_gas (vaporizado)",
        "LHV_kJ_per_kg": 46350.0,
        "LHV_source": "NIST WebBook (LHV, 25 °C)",
        "stoich_AFR": 15.7, "molar_mass_kg_per_kmol": 44.096,
        "remarks": "teste", "validity": "", "mechanism": None,
    }


def test_custom_fuel_save_load_delete_roundtrip(tmp_path, monkeypatch):
    from wiebepy.cfd import fuels as fuels_mod
    from wiebepy.cfd.fuels import (all_fuel_specs, delete_custom_fuel,
                                   fuel_names, fuel_summary, load_custom_fuels,
                                   save_custom_fuel)
    yaml_path = tmp_path / "fuels_custom.yaml"
    # get_fuel/fuel_summary resolvem pelo caminho padrão — redireciona p/ tmp
    monkeypatch.setattr(fuels_mod, "custom_fuels_path", lambda: yaml_path)
    assert load_custom_fuels(yaml_path) == {}
    assert save_custom_fuel(_registro_exemplo(), yaml_path) == []
    customs = load_custom_fuels(yaml_path)
    assert "C3H8" in customs
    assert customs["C3H8"]["LHV_source"] == "NIST WebBook (LHV, 25 °C)"
    # registro combinado inclui o cadastrado; embutidos preservados
    specs = all_fuel_specs(yaml_path)
    assert "C3H8" in specs and "CH4" in specs
    assert specs["C3H8"].LHV_kJ_per_kg == pytest.approx(46350.0)
    assert set(FUELS) <= set(specs)
    assert fuel_names(yaml_path) == list(FUELS) + ["C3H8"]
    assert fuel_summary("C3H8", 1e-5)["Q_cycle_J"] == pytest.approx(
        1e-5 * 46350.0 * 1e3, rel=1e-9)
    # embutido nunca é alterado; cadastro sobrepõe com marcação
    assert save_custom_fuel(_registro_exemplo("diesel"), yaml_path) == []
    specs2 = all_fuel_specs(yaml_path)
    assert specs2["diesel"].LHV_kJ_per_kg == pytest.approx(46350.0)
    assert FUELS["diesel"].LHV_kJ_per_kg == pytest.approx(42_600.0)
    assert "sobrepõe" in specs2["diesel"].remarks
    # remoção: remove o cadastro (embutido volta a valer intacto)
    assert delete_custom_fuel("C3H8", yaml_path) is True
    assert delete_custom_fuel("diesel", yaml_path) is True
    assert all_fuel_specs(yaml_path)["diesel"].LHV_kJ_per_kg == \
        pytest.approx(42_600.0)
    assert delete_custom_fuel("C3H8", yaml_path) is False
    assert load_custom_fuels(yaml_path) == {}


def test_custom_fuel_validation_sem_fonte(tmp_path):
    from wiebepy.cfd.fuels import (custom_fuels_path, load_custom_fuels,
                                   save_custom_fuel)
    yaml_path = tmp_path / "fuels_custom.yaml"
    r = _registro_exemplo()
    r["LHV_source"] = ""                     # propriedade sem fonte: negada
    erros = save_custom_fuel(r, yaml_path)
    assert any("fonte do PCI" in e for e in erros)
    assert load_custom_fuels(yaml_path) == {}
    r["LHV_kJ_per_kg"] = -1
    assert save_custom_fuel(r, yaml_path)
    r["LHV_kJ_per_kg"] = 100.0
    r["LHV_source"] = "ok"
    r["name"] = "com espaco"
    assert save_custom_fuel(r, yaml_path)
    r["name"] = "ok_nome"
    r["mechanism"] = "GRI3.0"
    erros = save_custom_fuel(r, yaml_path)
    assert any("reativo" in e for e in erros)
    # caminho padrão (permanente): data/fuels_custom.yaml na raiz
    assert custom_fuels_path().as_posix() == "data/fuels_custom.yaml"


def test_fuel_csv_export_import_roundtrip(tmp_path):
    from wiebepy.cfd.fuels import (all_fuel_specs, export_fuels_csv,
                                   import_fuels_csv, save_custom_fuel)
    yaml_path = tmp_path / "fuels_custom.yaml"
    save_custom_fuel(_registro_exemplo(), yaml_path)
    csv_path = tmp_path / "fuels.csv"
    nomes = export_fuels_csv(csv_path, path_yaml=yaml_path)
    assert nomes == list(FUELS) + ["C3H8"]
    texto = csv_path.read_text(encoding="utf-8-sig")
    assert texto.splitlines()[0].split(";")[0] == "name"
    # ler de volta: grava cada linha como cadastro permanente
    res = import_fuels_csv(csv_path, path_yaml=yaml_path)
    assert sorted(res["gravados"]) == sorted(list(FUELS) + ["C3H8"])
    assert res["erros"] == []
    specs = all_fuel_specs(yaml_path)
    # os embutidos passam a ser servidos do CSV (sobrepõe, valores iguais)
    assert specs["H2"].LHV_kJ_per_kg == pytest.approx(
        FUELS["H2"].LHV_kJ_per_kg, rel=1e-12)
    assert specs["C3H8"].LHV_kJ_per_kg == pytest.approx(46350.0)
    # CSV editado sem fonte do PCI → linha rejeitada, lote não aborta
    import csv as _csv
    with csv_path.open("r", newline="", encoding="utf-8-sig") as fh:
        linhas_csv = list(_csv.reader(fh, delimiter=";"))
    cab, corpo = linhas_csv[0], linhas_csv[1:]
    idx_fonte = cab.index("LHV_source")
    quebrada = list(corpo[0])
    quebrada[idx_fonte] = ""                 # H2 sem fonte
    csv2 = tmp_path / "quebrado.csv"
    with csv2.open("w", newline="", encoding="utf-8-sig") as fh:
        w = _csv.writer(fh, delimiter=";")
        w.writerow(cab)
        w.writerow(quebrada)
        w.writerows(corpo[1:])
    res2 = import_fuels_csv(csv2, path_yaml=yaml_path)
    assert res2["erros"] and "H2" in res2["erros"][0]
    assert len(res2["gravados"]) == len(corpo) - 1   # C3H8 + demais embutidos
    specs3 = all_fuel_specs(yaml_path)
    assert specs3["C3H8"].LHV_kJ_per_kg == pytest.approx(46350.0)


def test_fuel_csv_import_csv_sem_coluna_name(tmp_path):
    from wiebepy.cfd.fuels import import_fuels_csv
    csv_path = tmp_path / "sem_name.csv"
    csv_path.write_text("a;b\n1;2\n", encoding="utf-8-sig")
    with pytest.raises(ValueError):
        import_fuels_csv(csv_path)


def test_config_aceita_combustivel_cadastrado(tmp_path, monkeypatch):
    from wiebepy.cfd import fuels as fuels_mod
    from wiebepy.cfd.fuels import save_custom_fuel
    yaml_path = tmp_path / "fuels_custom.yaml"
    save_custom_fuel(_registro_exemplo("C3H8"), yaml_path)
    monkeypatch.setattr(fuels_mod, "custom_fuels_path",
                        lambda: yaml_path)
    cfg = CfdConfig.from_dict({**CFG_DICT,
                               "fuel": {"name": "C3H8",
                                        "feed": "premixed_gas"}})
    assert cfg.validate() == []


# --------------------------------------- comparação experimental (relatório)
def _res_sintetico():
    ca = np.linspace(-120.0, 120.0, 241)
    p = 250.0 + 9000.0 * np.exp(-0.5 * ((ca - 5.0) / 15.0) ** 2)  # kPa
    V = 5e-5 + 3e-4 * 0.5 * (1.0 + np.cos(np.radians(ca)))
    return {"ca_deg": ca, "p_mean_kPa": p, "V_m3": V}


def _exp_sintetico(ca):
    p_exp = 250.0 + 8600.0 * np.exp(-0.5 * ((ca - 5.0) / 16.0) ** 2)
    return {"source": "sintetico", "ca_deg": np.asarray(ca, float),
            "p_kPa": p_exp, "offset_deg": 0.0,
            "V_m3": 5e-5 + 3e-4 * 0.5 * (1.0 + np.cos(np.radians(ca))),
            "units": {"angle": "deg", "pressure": "kPa"}, "warnings": []}


def test_metricas_experimental_valores():
    from wiebepy.cfd.reporting import _metricas_experimental
    res = _res_sintetico()
    exp = _exp_sintetico(res["ca_deg"][::2])
    met = dict((k, v) for k, v in _metricas_experimental(res, exp))
    assert met["pontos experimentais na janela CFD"] == 121
    assert met["p_max CFD [kPa]"] == pytest.approx(9250.0, rel=1e-6)
    assert met["CA de p_max CFD [°]"] == pytest.approx(5.0, abs=1.0)
    assert met["erro de fase de p_max [°]"] == pytest.approx(0.0, abs=1.0)
    dif = np.interp(exp["ca_deg"], res["ca_deg"],
                    res["p_mean_kPa"]) - exp["p_kPa"]
    assert met["RMSE na sobreposição [kPa]"] == pytest.approx(
        float(np.sqrt(np.mean(dif ** 2))), rel=1e-6)
    assert met["diferença média (viés) [kPa]"] == pytest.approx(
        float(np.mean(dif)), rel=1e-6)


def test_metricas_experimental_sem_sobreposicao():
    from wiebepy.cfd.reporting import _metricas_experimental
    res = _res_sintetico()
    exp = _exp_sintetico(np.linspace(500.0, 700.0, 50))
    met = _metricas_experimental(res, exp)
    assert met and "sobreposição" in met[0][0]


def test_report_html_com_experimental(tmp_path):
    from wiebepy.cfd.reporting import report_html
    res = _res_sintetico()
    exp = _exp_sintetico(res["ca_deg"][::2])
    h = report_html(tmp_path, res, exp_data=exp)
    assert "Comparação experimental" in h
    assert "Diagrama P–V (CFD vs experimental)" in h
    assert "p_max experimental [kPa]" in h
    assert "RMSE na sobreposição [kPa]" in h
    assert "alinhamento de fase declarado" in h
    # figuras embutidas (p×θ e P–V com exp; res sintético só tem p e V)
    assert h.count("<img") >= 2
    # sem dados experimentais: sem a seção
    h2 = report_html(tmp_path, res)
    assert "Comparação experimental" not in h2


def test_load_exp_data_csv_unidades_e_offset(tmp_path):
    from wiebepy.cfd.reporting import load_exp_data
    csv = tmp_path / "exp.csv"
    th = np.linspace(-1.0, 1.0, 41)          # rad
    p = 100.0 + 9000.0 * np.exp(-0.5 * ((np.degrees(th) - 5.0) / 15.0) ** 2)
    csv.write_text("\n".join(f"{t:.6f},{v:.6f}"
                             for t, v in zip(th, p)) + "\n",
                   encoding="utf-8")
    exp = load_exp_data(tmp_path, cfg=CfdConfig.from_dict(
        {**CFG_DICT, "comparison": {
            "experimental": "exp.csv",
            "experimental_angle_unit": "rad",
            "experimental_pressure_unit": "kPa",
            "experimental_offset_deg": 3.5}}), engine=ENGINE)
    assert "exp.csv" in exp["source"]
    assert np.allclose(exp["ca_deg"], np.degrees(th) + 3.5)
    assert exp["p_kPa"][np.argmax(exp["p_kPa"])] == pytest.approx(
        p.max(), rel=1e-6)
    assert "V_m3" in exp and len(exp["V_m3"]) == 41
    assert exp["units"] == {"angle": "rad", "pressure": "kPa"}


def test_load_exp_data_bar_e_sem_arquivo(tmp_path):
    from wiebepy.cfd.reporting import load_exp_data
    # ensaio real (θ rad, P bar): valores convertidos para kPa
    src = Path(__file__).resolve().parents[1] / "examples" / "data" / \
        "ensaio_P_exp_carga3_45.txt"
    cfg = CfdConfig.from_dict({**CFG_DICT, "comparison": {
        "experimental": str(src),
        "experimental_angle_unit": "rad",
        "experimental_pressure_unit": "bar"}})
    exp = load_exp_data(tmp_path, cfg=cfg, engine=ENGINE)
    assert "erro" not in exp
    assert len(exp["ca_deg"]) > 100
    assert exp["p_kPa"].max() > exp["p_kPa"].min() * 5
    # arquivo declarado e ausente → erro explícito, sem substituição
    cfg2 = CfdConfig.from_dict({**CFG_DICT, "comparison": {
        "experimental": "inexistente.csv"}})
    exp2 = load_exp_data(tmp_path, cfg=cfg2)
    assert exp2 and "não encontrado" in exp2["erro"]


def test_config_valida_unidades_experimentais():
    base = {**CFG_DICT, "comparison": {
        "experimental": "x.csv", "experimental_pressure_unit": "atm"}}
    erros = CfdConfig.from_dict(base).validate()
    assert any("experimental_pressure_unit" in e for e in erros)
    base["comparison"]["experimental_pressure_unit"] = "bar"
    base["comparison"]["experimental_angle_unit"] = "deg"
    assert CfdConfig.from_dict(base).validate() == []


# ------------------------------------------------------------ case builder
def test_case_builder_reactive_r2(tmp_path):
    """Modo reativo (R2): volume fixo, química fornece o calor.

    Verificações estruturais do caso gerado:
      • SEM fvModels e SEM dynamicMeshDict (as duas fontes de calor nunca
        coexistem; malha fixa — ignição espontânea pela cinética);
      • reactions/speciesThermo COPIADOS do mecanismo (bytes idênticos);
      • physicalProperties/combustionProperties/chemistryProperties no
        formato dos tutoriais reativos do OF13;
      • campos 0/ com uma fração mássica por espécie do mecanismo;
      • controlDict em tempo FÍSICO [s] com adjustTimeStepToChemistry,
        Qdot e QdotIntegral.
    """
    from wiebepy.cfd.case_builder import CaseBuilder
    mecanismo = Path(__file__).resolve().parent.parent / "examples" / "cfd" \
        / "mechanisms" / "burke2012"
    cfg_dict = {
        "enabled": True,
        "mode": "reactive",
        "geometry": {"moving_piston": False},
        "initial": {"P_kPa": 250, "T_K": 800},
        "interval": {"start": 0.0, "end": 2.0e-3},
        "numerics": {"write_interval_deg": 1.0e-4},
        "walls": {"model": "adiabatic"},
        "turbulence": {"model": "laminar"},
        "reaction": {"mechanism": str(mecanismo),
                     "equivalence_ratio": 1.0},
    }
    cfg = CfdConfig.from_dict(cfg_dict)
    assert cfg.validate() == []
    b = CaseBuilder(cfg, ENGINE, solver_info={"version": "13"})
    caso = b.build(tmp_path / "reactivo")

    # fontes de calor: NENHUMA das duas
    assert not (caso / "constant" / "fvModels").exists()
    assert not (caso / "constant" / "dynamicMeshDict").exists()
    # mecanismo copiado byte a byte (nunca redigitado)
    for f in ("reactions", "speciesThermo"):
        assert (caso / "constant" / f).read_bytes() \
            == (mecanismo / f).read_bytes()
    phys = (caso / "constant" / "physicalProperties").read_text("utf-8")
    assert "multicomponentMixture" in phys and 'defaultSpecie    N2;' in phys
    assert '#include "speciesThermo"' in phys
    chem = (caso / "constant" / "chemistryProperties").read_text("utf-8")
    assert "#include \"reactions\"" in chem and "seulex" in chem
    comb = (caso / "constant" / "combustionProperties").read_text("utf-8")
    assert "combustionModel  laminar;" in comb

    # campos iniciais no diretório do tempo inicial (0 s) — 13 espécies
    esp = b._mech["species"]
    t0 = caso / "0"
    for f in ("p", "T", "U") + tuple(esp) + ("Ydefault",):
        assert (t0 / f).exists(), f
    # φ = 1 com ar: X = (2/6,76; 1/6,76; 3,76/6,76) — frações mássicas
    # derivadas das massas molares do PRÓPRIO speciesThermo
    mw = b._mech["molWeight"]
    X = {"H2": 2 / 6.76, "O2": 1 / 6.76, "N2": 3.76 / 6.76}
    mixm = sum(x * mw[s] for s, x in X.items())
    for sp, x in X.items():
        y_esp = x * mw[sp] / mixm
        y_txt = (t0 / sp).read_text("utf-8")
        linha = [l for l in y_txt.splitlines()
                 if l.startswith("internalField")][0]
        y_arquivo = float(linha.split("uniform")[1].rstrip(";"))
        assert math.isclose(y_arquivo, y_esp, rel_tol=1e-6)
    # soma das frações mássicas = 1
    assert math.isclose(sum(b._Y0.values()), 1.0, rel_tol=1e-12)

    # controlDict: tempo físico, sem userTime engine
    cd = (caso / "system" / "controlDict").read_text("utf-8")
    assert "userTime" not in cd
    assert "solver          multicomponentFluid;" in cd
    assert "startTime       0;" in cd
    assert "endTime         0.002;" in cd
    assert "maxDeltaT       0.001;" in cd
    assert "#includeFunc adjustTimeStepToChemistry" in cd
    assert "QdotIntegral" in cd and "volIntegrate" in cd
    # campos auxiliares multiply NÃO gravam por passo (writeTime)
    assert cd.count("writeControl    writeTime;") >= 13
    # documentação do caso
    info = yaml.safe_load((caso / "case_config.yaml").read_text("utf-8"))
    assert info["mode"] == "reactive"
    assert info["features"]["heat_source"] is False
    assert info["interval"]["time_unit"] == "s"
    assert info["chamber"]["model"] == "fixed_volume"
    assert "H2" in info["reaction"]["initial_composition"]["mass_fractions_Y"]
    # validação estática do caso passa (sem solver — adapter mockado abaixo)
    from wiebepy.cfd.config import write_state
    write_state(caso, CaseState.PREPARED)
    import wiebepy.cfd.validation as val
    class _Adaptador:
        def check_runnable(self):
            return []
    import unittest.mock as mock
    with mock.patch.object(val, "get_adapter", return_value=_Adaptador()):
        ok, erros, avisos = val.validate_case(caso, "openfoam")
    assert ok, erros


def test_case_builder_reactive_composicao_explicita(tmp_path):
    """composition explícita (frações mássicas) sobrepõe φ e é normalizada."""
    from wiebepy.cfd.case_builder import CaseBuilder
    mecanismo = Path(__file__).resolve().parent.parent / "examples" / "cfd" \
        / "mechanisms" / "burke2012"
    cfg = CfdConfig.from_dict({
        "mode": "reactive", "geometry": {"moving_piston": False},
        "walls": {"model": "adiabatic"},
        "reaction": {"mechanism": str(mecanismo),
                     "composition": {"H2": 0.0285, "O2": 0.2262,
                                     "N2": 0.7453}}})
    b = CaseBuilder(cfg, ENGINE, solver_info={"version": "13"})
    y = b._Y0
    assert math.isclose(sum(y.values()), 1.0, rel_tol=1e-9)
    assert math.isclose(y["H2"], 0.0285, rel_tol=1e-6)
    # espécie fora do mecanismo é bloqueante
    cfg2 = CfdConfig.from_dict({
        "mode": "reactive", "geometry": {"moving_piston": False},
        "reaction": {"mechanism": str(mecanismo),
                     "composition": {"CH4": 1.0}}})
    with pytest.raises(ValueError, match="fora do mecanismo"):
        CaseBuilder(cfg2, ENGINE, solver_info={"version": "13"})


def test_case_builder_reactive_campos_pares_incompletos(tmp_path):
    """Mecanismo incompleto (sem reactions) é bloqueante com mensagem
    explícita — nenhuma inferência silenciosa."""
    from wiebepy.cfd.case_builder import CaseBuilder
    mecanismo = Path(__file__).resolve().parent.parent / "examples" / "cfd" \
        / "mechanisms" / "burke2012"
    quebrado = tmp_path / "mecanismo_quebrado"
    quebrado.mkdir()
    (quebrado / "speciesThermo").write_text("species 1 ( N2 );\nN2\n{\n}\n",
                                            encoding="utf-8")
    cfg = CfdConfig.from_dict({
        "mode": "reactive", "geometry": {"moving_piston": False},
        "reaction": {"mechanism": str(quebrado)}})
    with pytest.raises(ValueError, match="ausente"):
        CaseBuilder(cfg, ENGINE, solver_info={"version": "13"})


def test_case_builder_generates_openfoam_case(tmp_path):
    from wiebepy.cfd.case_builder import CaseBuilder
    cfg = CfdConfig.from_dict(CFG_DICT)
    b = CaseBuilder(cfg, ENGINE, solver_info={"version": "13"},
                    heat_enabled=True, moving_override=True)
    d = b.build(tmp_path / "caso")
    t0 = d / "-120"
    assert (t0 / "p").exists() and (t0 / "T").exists() and (t0 / "U").exists()
    assert (d / "constant/dynamicMeshDict").exists()
    fv = (d / "constant/fvModels").read_text(encoding="utf-8")
    assert "heatSource" in fv and "table" in fv
    assert fv.rstrip().endswith(");") or ");" in fv
    ctrl = (d / "system/controlDict").read_text(encoding="utf-8")
    assert "solver          fluid;" in ctrl
    assert "type            engine;" in ctrl
    assert "startTime       -120;" in ctrl
    # sem CRLF (o parser de listas do OpenFOAM não tolera \r)
    for p in d.rglob("*"):
        if p.is_file():
            assert b"\r\n" not in p.read_bytes(), f"CRLF em {p.name}"
    # verificação de energia registrada no caso
    import yaml
    cc = yaml.safe_load((d / "case_config.yaml").read_text(encoding="utf-8"))
    assert cc["heat_source"]["energy_check"]["ok"] is True
    assert cc["features"] == {"moving_piston": True, "heat_source": True}


def test_case_builder_fixed_cold_no_heat(tmp_path):
    from wiebepy.cfd.case_builder import CaseBuilder
    cfg = CfdConfig.from_dict(CFG_DICT)
    b = CaseBuilder(cfg, ENGINE, solver_info={"version": "13"},
                    heat_enabled=False, moving_override=False)
    d = b.build(tmp_path / "v1")
    assert not (d / "constant/fvModels").exists()
    assert not (d / "constant/dynamicMeshDict").exists()
    cc = yaml.safe_load((d / "case_config.yaml").read_text(encoding="utf-8"))
    assert cc["features"] == {"moving_piston": False, "heat_source": False}


def test_case_builder_komega_sst_campos(tmp_path):
    # kOmegaSST: campo omega (não epsilon), BCs de parede coerentes,
    # schemes e solvers com omega no grupo
    from wiebepy.cfd.case_builder import CaseBuilder
    d_cfg = dict(CFG_DICT)
    d_cfg["turbulence"] = {"model": "kOmegaSST", "wall_functions": True}
    cfg = CfdConfig.from_dict(d_cfg)
    b = CaseBuilder(cfg, ENGINE, solver_info={"version": "13"},
                    heat_enabled=True, moving_override=True)
    d = b.build(tmp_path / "sst")
    t0 = d / "-120"
    om = (t0 / "omega").read_text(encoding="utf-8")
    assert "omegaWallFunction" in om and "uniform" in om
    assert not (t0 / "epsilon").exists()
    for nome in ("k", "nut", "alphat"):
        assert (t0 / nome).exists()
    mt = (d / "constant/momentumTransport").read_text(encoding="utf-8")
    assert "kOmegaSST" in mt and "RAS" in mt
    esc = (d / "system/fvSchemes").read_text(encoding="utf-8")
    assert "div(phi,omega)" in esc and "wallDist" in esc
    sol = (d / "system/fvSolution").read_text(encoding="utf-8")
    assert "epsilon|omega" in sol


def test_case_builder_kepsilon_campos(tmp_path):
    from wiebepy.cfd.case_builder import CaseBuilder
    d_cfg = dict(CFG_DICT)
    d_cfg["turbulence"] = {"model": "kEpsilon", "wall_functions": True}
    cfg = CfdConfig.from_dict(d_cfg)
    b = CaseBuilder(cfg, ENGINE, solver_info={"version": "13"},
                    heat_enabled=True, moving_override=True)
    d = b.build(tmp_path / "ke")
    t0 = d / "-120"
    assert (t0 / "epsilon").read_text(encoding="utf-8").count(
        "epsilonWallFunction") == 3
    assert not (t0 / "omega").exists()


def test_case_builder_paredes_adiabaticas(tmp_path):
    # model: adiabatic → T com zeroGradient nas três paredes
    from wiebepy.cfd.case_builder import CaseBuilder
    d_cfg = dict(CFG_DICT)
    d_cfg["walls"] = {"model": "adiabatic"}
    cfg = CfdConfig.from_dict(d_cfg)
    b = CaseBuilder(cfg, ENGINE, solver_info={"version": "13"},
                    heat_enabled=True, moving_override=True)
    d = b.build(tmp_path / "adiab")
    t = (d / "-120/T").read_text(encoding="utf-8")
    assert t.count("zeroGradient") >= 3 and "fixedValue" not in t.split(
        "boundaryField")[1]


def test_case_builder_grade_converge_para_m_pequeno(tmp_path):
    # fonte calibrada (m=0.075): grade fixa de 0,1° NÃO fecha o
    # fechamento (déficit 0,29 % na 1ª célula de queima); o builder
    # refina a grade da verificação e da tabela até passar (0,02°) e
    # registra o passo em case_config.yaml
    import yaml as _yaml
    from wiebepy.cfd.case_builder import CaseBuilder
    modelo = str(Path(__file__).resolve().parent.parent
                 / "examples/model_cfd_calibrated.json")
    d_cfg = dict(CFG_DICT)
    d_cfg["wiebe"] = {"source": "model", "model": modelo}
    cfg = CfdConfig.from_dict(d_cfg)
    b = CaseBuilder(cfg, ENGINE, solver_info={"version": "13"},
                    heat_enabled=True, moving_override=True)
    d = b.build(tmp_path / "m075")
    info = _yaml.safe_load((d / "case_config.yaml").read_text(
        encoding="utf-8"))
    chk = info["heat_source"]["energy_check"]
    assert chk["ok"] is True and chk["rel_error"] <= 1e-3
    assert info["heat_source"]["table_step_CA_deg"] < 0.1


def test_case_builder_fonte_inconsistente_levanta_erro(monkeypatch):
    # mecanismo de segurança: se o fechamento não fecha em NENHUMA grade
    # (até 0,005°), o builder levanta erro — nunca aceita silenciosamente
    import wiebepy.cfd.case_builder as cb
    from wiebepy.cfd.case_builder import CaseBuilder
    monkeypatch.setattr(
        cb, "energy_check",
        lambda *a, **k: {"integral_J": 100.0, "expected_J": 369.0,
                         "rel_error": 0.5, "ok": False})
    d_cfg = dict(CFG_DICT)
    cfg = CfdConfig.from_dict(d_cfg)
    with pytest.raises(ValueError, match="0,005"):
        CaseBuilder(cfg, ENGINE, solver_info={"version": "13"},
                    heat_enabled=True, moving_override=True)


def test_case_builder_gas_cp_equivalencia(tmp_path):
    # teste de equivalência termodinâmica: Cp 1063 com molWeight 28.96
    # dá γ = 1,37 (o κ do 0-D) — escrito no physicalProperties e
    # registrado no case_config.yaml
    from wiebepy.cfd.case_builder import CaseBuilder
    d_cfg = dict(CFG_DICT)
    d_cfg["gas"] = {"Cp_J_kgK": 1063.0, "molWeight_kg_kmol": 28.96}
    cfg = CfdConfig.from_dict(d_cfg)
    b = CaseBuilder(cfg, ENGINE, solver_info={"version": "13"},
                    heat_enabled=True, moving_override=True)
    d = b.build(tmp_path / "gamma")
    pp = (d / "constant/physicalProperties").read_text(encoding="utf-8")
    assert "Cp              1063" in pp and "molWeight       28.96" in pp
    import yaml as _yaml
    info = _yaml.safe_load((d / "case_config.yaml").read_text(
        encoding="utf-8"))
    assert info["gas_model"]["gamma"] == pytest.approx(1.37, abs=0.002)
    assert info["walls"]["model"] == "fixed_temperature"


def test_case_state_machine(tmp_path):
    from wiebepy.cfd.config import read_state, write_state
    d = tmp_path / "caso"
    d.mkdir()
    assert read_state(d) == CaseState.NOT_CONFIGURED
    write_state(d, CaseState.PREPARED)
    assert read_state(d) == CaseState.PREPARED
    assert read_state(d).label == "Preparado"

# ------------------------------------------------- R1: multicomponente
def _cfg_multicomponente() -> CfdConfig:
    d = dict(CFG_DICT)
    d["gas"] = {"model": "multicomponent_inert"}
    return CfdConfig.from_dict(d)


def test_case_builder_multicomponente_physical_properties(tmp_path):
    """R1 (roadmap reativo §2): gás multicomponente inerte N2+O2 com
    polinômios NASA (janaf/sutherland), formato do tutorial OF13
    multicomponentFluid/counterFlowFlame2D."""
    from wiebepy.cfd.case_builder import CaseBuilder
    b = CaseBuilder(_cfg_multicomponente(), ENGINE,
                    solver_info={"version": "13"}, heat_enabled=True,
                    moving_override=True)
    d = b.build(tmp_path / "r1")
    pp = (d / "constant/physicalProperties").read_text(encoding="utf-8")
    assert "coefficientWilkeMulticomponentMixture" in pp
    assert "janaf" in pp and "sutherland" in pp
    assert "species          ( N2 O2 );" in pp
    assert "defaultSpecie    N2" in pp
    # proveniência: massa molar de N2/O2 do tutorial OF13 (GRI thermo)
    assert "28.0134" in pp and "31.9988" in pp
    # polinômios NASA copiados (bloco N2, coeficiente independente high)
    assert "-922.798" in pp
    # SEM combustionProperties: o combustionModel::New do OF13 cai em
    # noCombustion (R=0) — transporte de espécies sem reação
    assert not (d / "constant/combustionProperties").exists()
    # o restante de constant/ continua escrito (dynamicMeshDict é
    # obrigatório para o pistão móvel do caso de verificação)
    assert (d / "constant/dynamicMeshDict").exists()
    assert (d / "constant/momentumTransport").exists()
    # o caso simple continua intacto (regressão)
    b2 = CaseBuilder(CfdConfig.from_dict(CFG_DICT), ENGINE,
                     solver_info={"version": "13"}, heat_enabled=True,
                     moving_override=True)
    d2 = b2.build(tmp_path / "simple")
    pp2 = (d2 / "constant/physicalProperties").read_text(encoding="utf-8")
    assert "pureMixture" in pp2
    t0 = d2 / "-120"
    assert not (t0 / "N2").exists()


def test_case_builder_multicomponente_solver_e_campos(tmp_path):
    """R1: controlDict usa multicomponentFluid; 0/ tem N2 e O2
    (frações mássicas do ar seco, razão molar 3,76:1); fvSchemes tem
    div(phi,Yi_h); fvSolution tem Yi/YiFinal; functionObjects de massa
    por espécie; case_config registra modelo e proveniência."""
    from wiebepy.cfd.case_builder import CaseBuilder
    b = CaseBuilder(_cfg_multicomponente(), ENGINE,
                    solver_info={"version": "13"}, heat_enabled=True,
                    moving_override=True)
    d = b.build(tmp_path / "r1")
    cd = (d / "system/controlDict").read_text(encoding="utf-8")
    assert "solver          multicomponentFluid;" in cd
    # conservação de massa por espécie: multiply (rho·Yi) + volIntegrate;
    # campos auxiliares multiply com writeControl writeTime — sem isso o
    # OF13 grava ρ·Yi TODO passo (um diretório de tempo por passo, bug
    # registrado no caso R2 de verificação)
    assert "massN2" in cd and "massO2" in cd and "specieMass" in cd
    assert cd.count("writeControl    writeTime;") >= 2
    # frações mássicas: N2 = 3,76·M_N2/(3,76·M_N2 + M_O2) = 0,76695…
    # (campos ficam no diretório do tempo inicial, ex. -120/)
    t0 = d / "-120"
    n2 = (t0 / "N2").read_text(encoding="utf-8")
    o2 = (t0 / "O2").read_text(encoding="utf-8")
    y_n2 = 3.76 * 28.0134 / (3.76 * 28.0134 + 31.9988)
    assert f"uniform {y_n2:.6f}"[:14] in n2
    assert "uniform 0.2330" in o2
    fs = (d / "system/fvSchemes").read_text(encoding="utf-8")
    assert "div(phi,Yi_h)   Gauss limitedLinear 1;" in fs
    fsol = (d / "system/fvSolution").read_text(encoding="utf-8")
    assert '"Yi"' in fsol and '"YiFinal"' in fsol
    import yaml as _yaml
    info = _yaml.safe_load((d / "case_config.yaml").read_text(
        encoding="utf-8"))
    gt = info["gas_thermo"]
    assert gt["model"] == "multicomponent_inert"
    assert gt["species"] == ["N2", "O2"]
    assert "GRI-Mech" in gt["provenance"]
    assert "IGNORADOS" in gt["notice"]


def test_cfd_config_gas_model_validacao():
    """gas.model aceita simple (default) e multicomponent_inert; valor
    desconhecido é erro de validação."""
    c = CfdConfig.from_dict({})
    assert c.gas_model == "simple"
    # base válida (wiebe do CFG_DICT) + gas.model multicomponente
    d = dict(CFG_DICT)
    d["gas"] = {"model": "multicomponent_inert"}
    c = CfdConfig.from_dict(d)
    assert c.gas_model == "multicomponent_inert"
    assert c.validate() == []
    d["gas"] = {"model": "nao_existe"}
    c = CfdConfig.from_dict(d)
    assert any("gas.model" in e for e in c.validate())
