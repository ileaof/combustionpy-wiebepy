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


def test_config_defaults_and_validation():
    cfg = CfdConfig.from_dict({"wiebe": CFG_DICT["wiebe"]})
    assert cfg.enabled is False                # CFD desabilitado por padrão
    assert cfg.mode == "prescribed_wiebe"
    assert cfg.validate() == []


def test_config_reactive_is_not_available():
    d = dict(CFG_DICT)
    d["mode"] = "reactive"
    erros = CfdConfig.from_dict(d).validate()
    assert any("não está implementado" in e for e in erros)


def test_config_interval_validation():
    ruim = CfdConfig.from_dict({"interval": {"start": 120, "end": -120},
                                "wiebe": CFG_DICT["wiebe"]})
    assert cfg_has_error(ruim, "end deve ser > start")


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


# ------------------------------------------------------------ case builder
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


def test_case_state_machine(tmp_path):
    from wiebepy.cfd.config import read_state, write_state
    d = tmp_path / "caso"
    d.mkdir()
    assert read_state(d) == CaseState.NOT_CONFIGURED
    write_state(d, CaseState.PREPARED)
    assert read_state(d) == CaseState.PREPARED
    assert read_state(d).label == "Preparado"