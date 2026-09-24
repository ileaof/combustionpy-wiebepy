# -*- coding: utf-8 -*-
"""Página CFD (opcional): casos OpenFOAM 3D com fonte de calor Wiebe
prescrita.

Módulo independente: com cfd.enabled=false (padrão) nada daqui é
importado pelas demais páginas e os resultados CFD existentes NÃO são
removidos ao desabilitar. O modo reativo (4.2) aparece como
indisponível — nunca é substituído silenciosamente pela fonte Wiebe.
"""
import math
import threading
import time
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st
import yaml

from wiebepy.gui import state as S
from wiebepy.core.parameters import (A_DEFAULT, MAX_STAGES, Stage, as_stages,
                                     default_stages, validate_stages)
from wiebepy.cfd.fuels import fuel_names

S.init_state()   # idempotente (app.py já chama; garante standalone)

st.header("CFD — escoamento 3D no cilindro (opcional)", anchor=False)
st.caption(
    "Casos OpenFOAM 13 (WSL2 no Windows) com liberação de calor GLOBAL "
    "prescrita pela Wiebe calibrada (modo 4.1). NÃO prevê cinética "
    "química, frente de chama ou emissões. O restante do wiebepy não "
    "depende desta página; desabilitar o CFD não apaga resultados.")

# ------------------------------------------------------------------ helpers
# Registro combinado: embutidos (ordem do FUELS) + combustíveis
# cadastrados na aba "Combustíveis" (data/fuels_custom.yaml).
def _lista_combustiveis() -> list:
    return fuel_names()


_TURB = {"laminar": False, "kEpsilon": True, "kOmegaSST": True}


def _form() -> dict:
    """Estado do formulário (persistente entre execuções)."""
    if "cfd_form" not in st.session_state:
        st.session_state.cfd_form = {
            # caso de referência atual: case_006 (equivalência γ=1,37,
            # fonte calibrada, RMSE/R² documentados em verification.md §3).
            # Preencher com case_012 só se recriando o par calibrado
            # (Rc 15,635 + model_cfd_duo_rc15635.json) JUNTOS — §3d.
            "case_directory": "results/cfd/case_006",
            "wsl_distro": "Ubuntu-22.04",
            "workers": 1,
            "interval_start": -120.0, "interval_end": 120.0,
            # condições do ensaio Diesel de referência em −120° CA
            # (P_exp-Carga-3_45%: 1,276 bar; T1 do motor)
            "P0_kPa": 127.6, "T0_K": 308.15, "Tw_K": 440.0,
            # referência de comparação com o ensaio: kEpsilon + malha
            # refinada (perda às paredes 44,1 J vs alvo Hohenberg 53,7 J)
            "turbulence_model": "kEpsilon",
            "moving_piston": True,
            "n_radial": 24, "n_axial": 36,
            "distribution": "uniform",
            "fuel_name": "diesel",   # ensaio de referência: Diesel
            # fonte do case_006: Wiebe calibrada 0-D (examples/, não a
            # manual model_cfd.json) — procedência em verification.md §3c
            "wiebe_origem": "model.json",
            "wiebe_model": "examples/model_cfd_calibrated.json",
            "wiebe_stages": None,   # None = inicializar do modelo atual (deg)
            # motor (mesmos parâmetros dos modos 0-D)
            "bore_mm": 86.0, "stroke_mm": 70.0, "rod_length_mm": 117.5,
            "Rc": 17.0, "rpm": 3396.20,
            "m_fuel_kg_per_cycle": 9.42754647351e-6,
            "LHV_kJ_per_kg": 39191.3, "T1_K": 308.15,
            # gás (equivalência GUI↔CLI, cfd.gas): default = case_006
            # (Cp 1063 + M 28,96 ⇒ γ=1,370 = κ do 0-D; §3c do
            # verification.md). model: simple | multicomponent_inert (R1)
            "gas_model": "simple", "gas_Cp": 1063.0,
            "gas_molWeight": 28.96, "gas_mu": 5.5e-05, "gas_Pr": 0.7,
            # numérica (cfd.numerics): padrões seguros — max_Co 0,5
            # abortou neste motor (verification.md §5b)
            "deltaT_s": 1.0e-6, "max_Co": 0.25, "write_interval_deg": 10.0,
            # comparação com o ensaio (cfd.comparison; relatório
            # diagnóstico): case_006
            "exp_file": "examples/data/ensaio_P_exp_carga3_45.txt",
            "exp_angle_unit": "rad", "exp_pressure_unit": "bar",
            "exp_offset_deg": 0.0,
        }
    return st.session_state.cfd_form


def _estagios_fonte_deg() -> list | None:
    """Estágios do modelo ATUAL (fonte sugerida da Wiebe prescrita),
    convertidos para DEG. Modo pressão: pmodel (rad interno); modo xb:
    model_stages (unidade da sessão)."""
    if st.session_state.get("mode") == "pressure":
        pm = st.session_state.pmodel
        if pm and pm.get("stages"):
            return [{"beta": float(s.beta),
                     "theta0": math.degrees(float(s.theta0)),
                     "duration": math.degrees(float(s.duration)),
                     "m": float(s.m), "a": float(s.a)}
                    for s in as_stages(pm["stages"])]
        return None
    ms = st.session_state.model_stages
    if not ms:
        return None
    em_rad = st.session_state.angle_unit == "rad"
    out = []
    for s in as_stages(ms):
        t0, du = float(s.theta0), float(s.duration)
        if em_rad:
            t0, du = math.degrees(t0), math.degrees(du)
        out.append({"beta": float(s.beta), "theta0": t0, "duration": du,
                    "m": float(s.m), "a": float(s.a)})
    return out


def _cfg_do_form() -> "CfdConfig":
    f = _form()
    origem = f["wiebe_origem"]
    if origem == "model.json":
        wiebe = {"source": "model", "model": f["wiebe_model"]}
    else:  # estágios editáveis nesta página (deg) — fonte: modelo atual
        stages = list(f.get("wiebe_stages") or [])
        if not stages:
            stages = _estagios_fonte_deg() or []
        if not stages:
            lo, hi = S.faixa_theta()
            stages = [s.to_dict() for s in default_stages(1, lo, hi,
                                                          A_DEFAULT)]
        stages = [{k: s[k] for k in ("beta", "theta0", "duration", "m")}
                  for s in stages]
        wiebe = {"source": "parameters", "parameters": stages}
    cfg_dict = {
        "mode": "prescribed_wiebe",
        "case_directory": f["case_directory"],
        "workers": int(f["workers"]),
        "wsl_distro": f["wsl_distro"] or None,
        "geometry": {"type": "simplified_cylinder",
                     "moving_piston": bool(f["moving_piston"]),
                     "n_radial": int(f["n_radial"]),
                     "n_axial": int(f["n_axial"])},
        "interval": {"angle_unit": "deg", "start": float(f["interval_start"]),
                     "end": float(f["interval_end"])},
        "initial": {"P_kPa": float(f["P0_kPa"]), "T_K": float(f["T0_K"])},
        "walls": {"Tw_K": float(f["Tw_K"]), "model": "fixed_temperature"},
        "turbulence": {"model": f["turbulence_model"],
                       "wall_functions": _TURB[f["turbulence_model"]]},
        "heat_source": {"distribution": f["distribution"], "region": None},
        "fuel": {"name": f["fuel_name"], "feed": "premixed_gas"},
        # equivalência GUI↔CLI: mesmas chaves de examples/config_*.yaml
        "gas": {"model": f["gas_model"], "Cp_J_kgK": float(f["gas_Cp"]),
                "molWeight_kg_kmol": float(f["gas_molWeight"]),
                "mu_Pa_s": float(f["gas_mu"]), "Pr": float(f["gas_Pr"])},
        "numerics": {"deltaT_s": float(f["deltaT_s"]),
                     "max_Co": float(f["max_Co"]),
                     "write_interval_deg": float(f["write_interval_deg"])},
        "wiebe": wiebe,
    }
    if (f["exp_file"] or "").strip():
        cfg_dict["comparison"] = {
            "criterion": "same_rpm_same_energy",
            "experimental": f["exp_file"].strip(),
            "experimental_angle_unit": f["exp_angle_unit"],
            "experimental_pressure_unit": f["exp_pressure_unit"],
            "experimental_offset_deg": float(f["exp_offset_deg"]),
        }
    return CfdConfig.from_dict(cfg_dict)


def _engine_cfg() -> dict:
    f = _form()
    return {k: f[k] for k in ("bore_mm", "stroke_mm", "rod_length_mm", "Rc",
                              "rpm", "m_fuel_kg_per_cycle", "LHV_kJ_per_kg",
                              "T1_K", "Tw_K")}


def _solver_install(distro):
    from wiebepy.cfd.capabilities import doctor
    rep = doctor()
    for dd in rep.distros:
        if distro and dd["name"] != distro:
            continue
        if dd["openfoam"]:
            return dd["openfoam"][0], dd["name"]
    return None, distro


def _runner():
    from wiebepy.cfd.runner import CfdRunner
    from wiebepy.pressure.engine import EngineConfig
    f = _form()
    cfg = _cfg_do_form()
    inst, distro = _solver_install(f["wsl_distro"])
    engine = EngineConfig.from_dict({"engine": _engine_cfg()})
    return CfdRunner(cfg, engine=engine, distro=distro,
                     solver_info=inst or {"version": None})


# ------------------------------------------------- tarefa em segundo plano
def _iniciar_cfd_job(tipo: str, alvo) -> None:
    job = {"tipo": tipo, "t0": time.time(), "done": False, "result": None,
           "error": None, "log": []}
    st.session_state.cfd_job = job

    def corpo():
        try:
            job["result"] = alvo(job)
        except Exception as e:                          # noqa: BLE001
            job["error"] = f"{type(e).__name__}: {e}"
        finally:
            job["done"] = True

    job["thread"] = threading.Thread(target=corpo, daemon=True)
    job["thread"].start()


def _job() -> dict | None:
    return st.session_state.get("cfd_job")


# =============================================================== formulário
with st.expander("Configuração do caso", expanded=True):
    c1, c2 = st.columns(2)
    with c1:
        f = _form()
        f["case_directory"] = st.text_input(
            "Diretório do caso", f["case_directory"])
        f["wsl_distro"] = st.text_input(
            "Distribuição WSL2 (Windows)", f["wsl_distro"])
        f["workers"] = st.number_input(
            "Processos MPI do SOLVER", 1, 64, f["workers"],
            help="Paralelismo do SOLVER (decomposePar/mpirun), distinto "
                 "dos backends CPU/GPU do wiebepy.")
        a1, a2 = st.columns(2)
        f["interval_start"] = a1.number_input("Início [°CA]",
                                              f["interval_start"])
        f["interval_end"] = a2.number_input("Fim [°CA]", f["interval_end"])
        b1, b2, b3 = st.columns(3)
        f["P0_kPa"] = b1.number_input("P inicial [kPa]", f["P0_kPa"])
        f["T0_K"] = b2.number_input("T inicial [K]", f["T0_K"])
        f["Tw_K"] = b3.number_input("Paredes [K]", f["Tw_K"])
    with c2:
        f["turbulence_model"] = st.select_slider(
            "Turbulência", ["laminar", "kEpsilon", "kOmegaSST"],
            f["turbulence_model"])
        f["moving_piston"] = st.toggle("Pistão móvel", f["moving_piston"])
        g1, g2 = st.columns(2)
        f["n_radial"] = g1.number_input("Células radiais", 4, 64,
                                        f["n_radial"])
        f["n_axial"] = g2.number_input("Células axiais", 4, 96, f["n_axial"])
        f["distribution"] = st.select_slider(
            "Distribuição da fonte", ["uniform", "region"], f["distribution"],
            help="uniform = referência (§7); region usa potência total Q "
                 "e herda uma limitação do OF13 com pistão móvel.")
        lista = _lista_combustiveis()
        if f["fuel_name"] not in lista:
            f["fuel_name"] = "diesel"     # ensaio de referência: Diesel
        f["fuel_name"] = st.select_slider("Combustível", lista,
                                          f["fuel_name"],
                                          help="Inclui combustíveis "
                                               "cadastrados na aba "
                                               "'Combustíveis'.")
    st.markdown("**Motor** (mesmos parâmetros dos modos 0-D)")
    e = st.columns(4)
    f["bore_mm"] = e[0].number_input("Diâmetro [mm]", f["bore_mm"])
    f["stroke_mm"] = e[1].number_input("Curso [mm]", f["stroke_mm"])
    f["rod_length_mm"] = e[2].number_input("Biela [mm]", f["rod_length_mm"])
    f["Rc"] = e[3].number_input("Rc [-]", f["Rc"])
    e2 = st.columns(4)
    f["rpm"] = e2[0].number_input("Rotação [rpm]", f["rpm"])
    f["m_fuel_kg_per_cycle"] = e2[1].number_input(
        "m combustível [kg/ciclo]", f["m_fuel_kg_per_cycle"],
        format="%.6e")
    f["LHV_kJ_per_kg"] = e2[2].number_input("PCI [kJ/kg]", f["LHV_kJ_per_kg"])
    f["T1_K"] = e2[3].number_input("T1 [K]", f["T1_K"])
    st.markdown("**Estágios Wiebe (1–5)** — fonte do calor prescrito")
    f["wiebe_origem"] = st.radio(
        "Origem", ["modelo atual", "model.json"],
        index=["modelo atual", "model.json"].index(f["wiebe_origem"]),
        horizontal=True,
        help="Modelo atual = estágios do modelo 0-D (modo pressão: "
             "parâmetros da aba Modelo), editáveis AQUI. Os parâmetros "
             "prescritos definem a liberação de calor; o CFD não recalibra "
             "o Wiebe. A edição nesta página não altera o modelo 0-D.")
    if f["wiebe_origem"] == "model.json":
        f["wiebe_model"] = st.text_input("Arquivo model.json",
                                         f["wiebe_model"])
    else:
        fonte = _estagios_fonte_deg()
        if f.get("wiebe_stages") is None:
            f["wiebe_stages"] = fonte or [
                s.to_dict() for s in default_stages(1, -120.0, 120.0,
                                                    A_DEFAULT)]
        n_atual = max(1, len(f["wiebe_stages"]))
        if "_cfd_n_pendente" in st.session_state:
            st.session_state.cfd_wiebe_n = \
                st.session_state.pop("_cfd_n_pendente")
        st.session_state.setdefault("cfd_wiebe_n", n_atual)
        n = st.segmented_control(
            "Número de estágios", list(range(1, MAX_STAGES + 1)),
            key="cfd_wiebe_n", format_func=lambda k: f"{k}-Wiebe",
            help="Mudar o número re-cria a tabela (estágios extras entram "
                 "com padrões); use os botões abaixo para re-sincronizar "
                 "com o modelo atual.")
        n = int(n or n_atual)
        atual = list(f["wiebe_stages"])
        if len(atual) != n:                     # trunca / completa
            if len(atual) > n:
                atual = atual[:n]
            else:
                lo, hi = S.faixa_theta()
                atual = atual + [s.to_dict() for s in
                                 default_stages(n, lo, hi,
                                                A_DEFAULT)[len(atual):]]
            f["wiebe_stages"] = atual
            st.session_state.pop(f"cfd_editor_{n}", None)
        tab = pd.DataFrame([{"beta": s["beta"], "theta0": s["theta0"],
                             "duration": s["duration"], "m": s["m"],
                             "a": s.get("a", A_DEFAULT)}
                            for s in atual])
        ed = st.data_editor(tab, key=f"cfd_editor_{n}", num_rows="fixed",
                            hide_index=True,
                            column_config={
                                "beta": st.column_config.NumberColumn(
                                    "β", min_value=0.0, max_value=1.0,
                                    format="%.4f",
                                    help="fração da massa do estágio"),
                                "theta0": st.column_config.NumberColumn(
                                    "θ0 [°]", format="%.4f",
                                    help="início do estágio [°CA]"),
                                "duration": st.column_config.NumberColumn(
                                    "Δθ [°]", min_value=1e-6, format="%.4f",
                                    help="duração (> 0) [°CA]"),
                                "m": st.column_config.NumberColumn(
                                    "m", min_value=0.0, format="%.4f",
                                    help="fator de forma (> 0)"),
                                "a": st.column_config.NumberColumn(
                                    "a", min_value=0.0, format="%.4f",
                                    help="eficiência (6.908 ⇒ 99,9 %)")})
        f["wiebe_stages"] = [{"beta": float(r.beta), "theta0": float(r.theta0),
                              "duration": float(r.duration),
                              "m": float(r.m), "a": float(r.a)}
                             for r in ed.itertuples()]
        erros_w = validate_stages([Stage(float(r["beta"]), float(r["theta0"]),
                                         float(r["duration"]), float(r["m"]),
                                         float(r["a"]))
                                   for r in f["wiebe_stages"]])
        for er in erros_w:
            st.error(er, icon=":material/error:")
        with st.container(horizontal=True):
            if st.button("Usar estágios do modelo atual",
                         icon=":material/history:",
                         disabled=fonte is None,
                         help="Descarta as edições desta página e volta aos "
                              "estágios do modelo 0-D atual."):
                f["wiebe_stages"] = fonte
                st.session_state.cfd_wiebe_n = len(fonte)
                st.session_state.pop(f"cfd_editor_{len(fonte)}", None)
                st.rerun()
            if st.button("Normalizar β (Σβ = 1)",
                         icon=":material/balance:"):
                soma = sum(s["beta"] for s in f["wiebe_stages"])
                if soma > 0:
                    f["wiebe_stages"] = [
                        {**s, "beta": s["beta"] / soma}
                        for s in f["wiebe_stages"]]
                    st.session_state.pop(f"cfd_editor_{n}", None)
                    st.rerun()

    st.markdown("**Gás, numérica e comparação** (equivalência GUI↔CLI)")
    gcol, ncol = st.columns(2)
    with gcol:
        f["gas_model"] = st.select_slider(
            "Modelo do gás", ["simple", "multicomponent_inert"],
            f["gas_model"],
            help="simple = Cp/γ constantes (referência case_006); "
                 "multicomponent_inert = N₂+O₂ com NASA janaf (degrau R1 "
                 "do roadmap reativo; sem reação).")
        f["gas_Cp"] = st.number_input(
            "Cp do gás [J/(kg·K)]", f["gas_Cp"],
            disabled=f["gas_model"] != "simple",
            help="1063,0 ⇒ γ=1,370 (κ do 0-D; case_006). Ignorado no modo "
                 "multicomponente.")
        f["gas_molWeight"] = st.number_input(
            "Massa molar [kg/kmol]", f["gas_molWeight"],
            disabled=f["gas_model"] != "simple",
            help="28,96 = ar seco. Ignorado no modo multicomponente "
                 "(N₂+O₂ definidos pela mistura).")
        f["gas_mu"] = st.number_input(
            "Viscosidade [Pa·s]", f["gas_mu"], format="%.2e",
            disabled=f["gas_model"] != "simple",
            help="Ignorado no modo multicomponente (sutherland do GRI).")
        f["gas_Pr"] = st.number_input(
            "Pr [-]", f["gas_Pr"],
            disabled=f["gas_model"] != "simple",
            help="Ignorado no modo multicomponente.")
    with ncol:
        f["deltaT_s"] = st.number_input(
            "Δt [s]", f["deltaT_s"], format="%.2e",
            help="Passo de tempo do solver.")
        f["max_Co"] = st.number_input(
            "max_Co [-]", f["max_Co"],
            help="0,5 ABORTOU neste motor (T negativo perto do PMS — "
                 "verification.md §5b); 0,25 é o padrão seguro.")
        f["write_interval_deg"] = st.number_input(
            "Escrita a cada [°CA]", f["write_interval_deg"],
            help="Intervalo entre tempos salvos (writeInterval em °CA).")
    with st.expander("Comparação com o ensaio (diagnóstica)", expanded=False):
        st.caption("Sobreposição da pressão medida no relatório HTML. "
                   "Comparação DIAGNÓSTICA — nunca validação (calibrar ≠ "
                   "validar). Deixe o caminho vazio para desativar.")
        f["exp_file"] = st.text_input("Arquivo do ensaio (θ,P)", f["exp_file"])
        c3, c4, c5 = st.columns(3)
        f["exp_angle_unit"] = c3.select_slider(
            "Unidade do ângulo", ["rad", "deg"], f["exp_angle_unit"])
        f["exp_pressure_unit"] = c4.select_slider(
            "Unidade da pressão", ["kPa", "bar", "MPa", "Pa", "psi"],
            f["exp_pressure_unit"])
        f["exp_offset_deg"] = c5.number_input(
            "Deslocamento [°CA]", f["exp_offset_deg"],
            help="Offset angular aplicado ao ensaio (sincronismo do "
                 "encoder).")

# ========================================================== estado e ações
case_dir = Path(_form()["case_directory"])
from wiebepy.cfd.config import CaseState, read_state   # noqa: E402
state = read_state(case_dir)

with st.container(horizontal=True, vertical_alignment="center"):
    st.metric("Estado do caso", state.label, border=True)
    st.metric("Solver", (st.session_state.get("cfd_solver")
                         or "não verificado"), border=True)
    ocupado = (st.session_state.get("cfd_job") or {}).get("done") is False
    if ocupado:
        st.metric("Ação", f":orange[{_job()['tipo']}…]", border=True)

with st.container(horizontal=True):
    rodar = st.button("Preparar caso", icon=":material/build:",
                      disabled=ocupado,
                      help="Gera o caso OpenFOAM para inspeção "
                           "(modo preparação sem execução).")
    validar = st.button("Validar", icon=":material/fact_check:",
                        disabled=ocupado or not case_dir.exists())
    executar = st.button("Executar", icon=":material/play_arrow:",
                         type="primary", disabled=ocupado)
    cancelar = st.button("Cancelar execução", icon=":material/cancel:",
                         disabled=not ocupado,
                         help="Interrompe o solver ativo (incluindo "
                              "processos MPI); logs e parciais preservados.")
    relatorio = st.button("Relatório HTML", icon=":material/description:",
                          disabled=ocupado or state != CaseState.COMPLETED)

if rodar:
    cfg = _cfg_do_form()
    erros = cfg.validate()
    if erros:
        for e in erros:
            st.error(f"Configuração inválida: {e}", icon=":material/error:")
    else:
        def _prep(job):
            runner = _runner()
            return str(runner.prepare(heat_enabled=True))
        _iniciar_cfd_job("preparação do caso", _prep)
        st.rerun()

if validar:
    def _val(job):
        from wiebepy.cfd.validation import validate_case
        ok, erros, avisos = validate_case(str(case_dir),
                                          distro=_form()["wsl_distro"])
        return {"ok": ok, "erros": erros, "avisos": avisos}
    _iniciar_cfd_job("validação do caso", _val)

if executar:
    def _run(job):
        from wiebepy.cfd.validation import validate_case
        ok, erros, _ = validate_case(str(case_dir),
                                     distro=_form()["wsl_distro"],
                                     set_validated=False)
        if not ok:
            raise RuntimeError("Caso não validado: " + "; ".join(erros))
        runner = _runner()
        return runner.run(str(case_dir), workers=int(_form()["workers"]),
                          on_output=(lambda l: job["log"].append(l)))
    _iniciar_cfd_job("execução CFD", _run)

if cancelar:
    from wiebepy.cfd.runner import CfdRunner
    if CfdRunner.cancel(str(case_dir)):
        st.toast("Cancelamento solicitado — o executor vai interromper o "
                 "solver.", icon=":material/cancel:")
    else:
        st.warning("Nenhuma execução ativa neste caso.")

if relatorio:
    def _rep(job):
        from wiebepy.core.parameters import as_stages
        from wiebepy.cfd.reporting import write_report
        from wiebepy.cfd.results import read_results
        from wiebepy.pressure.engine import EngineConfig
        engine = EngineConfig.from_dict({"engine": _engine_cfg()})
        info = yaml.safe_load((case_dir / "case_config.yaml").read_text(
            encoding="utf-8")) or {}
        try:
            stages = as_stages(info.get("wiebe_stages") or [])
        except Exception:                               # noqa: BLE001
            stages = None
        res = read_results(case_dir, engine=engine, stages=stages)
        # dados experimentais: prioridade ao ensaio carregado (aba Dados)
        exp = None
        pd_ = st.session_state.get("pdata")
        if pd_ is not None:
            import numpy as _np
            from wiebepy.pressure.engine import volume
            ca = _np.degrees(_np.asarray(pd_.theta, float))
            V, _, _ = volume(_np.radians(ca), engine.Rc, engine)
            exp = {"source": pd_.source or "ensaio carregado (aba Dados)",
                   "ca_deg": ca, "p_kPa": _np.asarray(pd_.P, float),
                   "offset_deg": 0.0, "V_m3": _np.asarray(V, float),
                   "warnings": list(getattr(pd_, "warnings", []) or [])}
        else:
            from wiebepy.cfd.reporting import load_exp_data
            exp = load_exp_data(case_dir, engine=engine)
        return str(write_report(case_dir, res, exp_data=exp))
    _iniciar_cfd_job("geração do relatório", _rep)

# ------------------------------------------------------- progresso do job
@st.fragment(run_every=1.0)
def _painel_job():
    job = st.session_state.get("cfd_job")
    if job is None:
        return
    if not job["done"]:
        st.info(f"{job['tipo']} em andamento ({time.time() - job['t0']:.0f} "
                "s)… o log do solver aparece abaixo.", icon=":material/hourglass_top:")
        linhas = job["log"][-12:]
        if linhas:
            st.code("\n".join(linhas), language=None)
        return
    st.session_state.cfd_job = None
    if job["error"]:
        st.error(f"Erro em {job['tipo']}: {job['error']}",
                 icon=":material/error:")
    else:
        r = job["result"]
        st.toast(f"{job['tipo']}: concluído.", icon=":material/check_circle:")
        if isinstance(r, dict) and "status" in r:
            if r["status"] == "completed":
                st.success("Processo do solver terminou sem erro. "
                           "**Processo terminou ≠ convergiu**: verifique o "
                           "fechamento de energia no relatório.")
            else:
                st.warning(f"Processo terminou com status '{r['status']}'."
                           + (f" {r['note']}" if r.get("note") else ""))
    st.rerun()

_painel_job()

# ============================================ diagnóstico e resultados
with st.expander("Diagnóstico do ambiente (doctor)"):
    if st.button("Executar diagnóstico", icon=":material/stethoscope:"):
        from wiebepy.cfd.capabilities import doctor
        st.code(doctor().format(), language=None)

res_prontos = state == CaseState.COMPLETED
if res_prontos or state in (CaseState.CANCELED, CaseState.FAILED):
    with st.expander("Resultados (0-D extraídos do caso 3D)",
                     expanded=res_prontos):
        if state != CaseState.COMPLETED:
            st.warning(f"Estado do caso: {state.label} — resultados "
                       "parciais podem estar disponíveis nos diretórios "
                       "de tempo gravados.")
        try:
            from wiebepy.core.parameters import as_stages
            from wiebepy.cfd.results import read_results
            from wiebepy.pressure.engine import EngineConfig
            engine = EngineConfig.from_dict({"engine": _engine_cfg()})
            info = yaml.safe_load((case_dir / "case_config.yaml")
                                  .read_text(encoding="utf-8")) or {}
            stages = None
            try:
                stages = as_stages(info.get("wiebe_stages") or [])
            except Exception:                           # noqa: BLE001
                pass
            r = read_results(case_dir, engine=engine, stages=stages)
        except Exception as e:                          # noqa: BLE001
            st.info(f"Resultados ainda não legíveis: {e}")
            st.stop()
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("p̄ máx", f"{r['p_mean'].max() / 1e6:.2f} MPa")
        m2.metric("T̄ máx", f"{r['T_mean'].max():.0f} K")
        m3.metric("Trabalho indicado",
                  f"{r['indicated_work_J']:.1f} J")
        m4.metric("Perda nas paredes", f"{r['wall_loss_J']:.1f} J")
        hs = info.get("heat_source", {}).get("energy_check", {})
        st.caption("Energia prescrita pela Wiebe: "
                   f"{hs.get('integral_J', float('nan')):.1f} J "
                   f"(erro {hs.get('rel_error', float('nan')):.1e}). "
                   "Média de volume do solver (não confundir com sonda "
                   "nem com pressão medida).")
        # campo SEM colchete: "[...]" no nome do campo é interpretado pelo
        # Vega como acesso aninhado (gráfico em branco); unidades no title
        df = pd.DataFrame({"θ": r["ca_deg"],
                           "p̄ [MPa]": r["p_mean"] / 1e6,
                           "T̄ [K]": r["T_mean"]})
        st.altair_chart(alt.Chart(df.melt("θ")).mark_line().encode(
            x=alt.X("θ:Q", title="θ [°CA]"), y=alt.Y("value:Q", title=None),
            color="variable:N").properties(height=300), use_container_width=True)
        st.markdown("Relatório completo (proveniência, balanços, limites): "
                    f"`{case_dir / 'report.html'}` — gere/atualize com o "
                    "botão **Relatório HTML**.")