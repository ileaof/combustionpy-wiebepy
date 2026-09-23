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
            "case_directory": "results/cfd/case_001",
            "wsl_distro": "Ubuntu-22.04",
            "workers": 1,
            "interval_start": -120.0, "interval_end": 120.0,
            "P0_kPa": 250.0, "T0_K": 800.0, "Tw_K": 440.0,
            "turbulence_model": "laminar",
            "moving_piston": True,
            "n_radial": 16, "n_axial": 24,
            "distribution": "uniform",
            "fuel_name": "diesel",   # ensaio de referência: Diesel
            "wiebe_origem": "modelo atual",
            "wiebe_model": "results/model.json",
            # motor (mesmos parâmetros dos modos 0-D)
            "bore_mm": 86.0, "stroke_mm": 70.0, "rod_length_mm": 117.5,
            "Rc": 17.0, "rpm": 3396.20,
            "m_fuel_kg_per_cycle": 9.42754647351e-6,
            "LHV_kJ_per_kg": 39191.3, "T1_K": 308.15,
        }
    return st.session_state.cfd_form


def _cfg_do_form() -> "CfdConfig":
    f = _form()
    origem = f["wiebe_origem"]
    if origem == "model.json":
        wiebe = {"source": "model", "model": f["wiebe_model"]}
    else:  # estágios do modelo atual (unidade da GUI → deg)
        n = len(st.session_state.model_stages or []) or 1
        em_rad = st.session_state.angle_unit == "rad"
        stages = []
        for s in S.estagios_modelo(n):
            t0, du = float(s.theta0), float(s.duration)
            if em_rad:
                t0, du = math.degrees(t0), math.degrees(du)
            stages.append({"beta": float(s.beta), "theta0": t0,
                           "duration": du, "m": float(s.m)})
        wiebe = {"source": "parameters", "parameters": stages}
    return CfdConfig.from_dict({
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
        "wiebe": wiebe,
    })


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
        help="Modelo atual = estágios definidos na página Modelo. Os "
             "parâmetros calibrados definem a liberação de calor; o CFD "
             "não recalibra o Wiebe.")
    if f["wiebe_origem"] == "model.json":
        f["wiebe_model"] = st.text_input("Arquivo model.json",
                                         f["wiebe_model"])
    else:
        n = len(st.session_state.model_stages or []) or 1
        st.dataframe(S.tabela_estagios(S.estagios_modelo(n)),
                     use_container_width=True, hide_index=True)

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
        return str(write_report(case_dir, res))
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
        df = pd.DataFrame({"θ [°CA]": r["ca_deg"],
                           "p̄ [MPa]": r["p_mean"] / 1e6,
                           "T̄ [K]": r["T_mean"]})
        st.altair_chart(alt.Chart(df.melt("θ [°CA]")).mark_line().encode(
            x=alt.X("θ [°CA]:Q"), y=alt.Y("value:Q", title=None),
            color="variable:N").properties(height=300), use_container_width=True)
        st.markdown("Relatório completo (proveniência, balanços, limites): "
                    f"`{case_dir / 'report.html'}` — gere/atualize com o "
                    "botão **Relatório HTML**.")