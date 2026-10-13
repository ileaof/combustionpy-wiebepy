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
import numpy as np
import pandas as pd
import streamlit as st

from wiebepy.i18n import t as _, tf
from wiebepy.i18n import t as _, tf
import yaml

from wiebepy.gui import state as S
from wiebepy.core.parameters import (A_DEFAULT, MAX_STAGES, Stage, as_stages,
                                     default_stages, validate_stages)
from wiebepy.cfd.fuels import fuel_names

S.init_state()   # idempotente (app.py já chama; garante standalone)

st.header(_("CFD — escoamento 3D no cilindro (opcional)"), anchor=False)
st.caption(
    _("Casos OpenFOAM 13 (WSL2 no Windows) com liberação de calor GLOBAL "
    "prescrita pela Wiebe calibrada (modo 4.1). NÃO prevê cinética "
    "química, frente de chama ou emissões. O restante do wiebepy não "
    "depende desta página; desabilitar o CFD não apaga resultados."))

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
        # conexão gravada pelo doctor (GUI "Conectar OpenFOAM ao código"
        # ou CLI "wiebepy cfd doctor --connect") define a distro padrão
        try:
            from wiebepy.cfd.capabilities import load_connection
            _conn = load_connection()
            if _conn and _conn.get("distro"):
                st.session_state.cfd_form["wsl_distro"] = _conn["distro"]
        except Exception:                            # noqa: BLE001
            pass  # sem conexão: mantém o padrão literal
    return st.session_state.cfd_form


def _ensaio_id(d) -> tuple:
    """Identidade do ensaio carregado na aba Dados (nome + conteúdo)."""
    return (st.session_state.get("data_name") or d.source or "", int(d.n),
            round(float(np.sum(d.P)), 6))


def _modelo_id(pm) -> tuple | None:
    if not pm or not pm.get("stages"):
        return None
    return (round(float(pm.get("Rc") or 0.0), 8),
            tuple(tuple(round(float(v), 10) for v in
                        (s.beta, s.theta0, s.duration, s.m, s.a))
                  for s in as_stages(pm["stages"])))


def _csv_do_ensaio(nome: str) -> str:
    """Nome do arquivo com o ensaio carregado, gravado DENTRO do caso."""
    base = "".join(c if c.isalnum() or c in "-_" else "_"
                   for c in Path(nome or "ensaio").stem)
    return f"ensaio_{base}.csv"


def _p_inicial_do_ensaio(d, theta_deg: float, e) -> tuple:
    """P [kPa] do ensaio no início da janela CFD. Fora da faixa lida,
    extrapola por compressão politrópica (κ do motor) a partir do ponto
    medido mais próximo — declarado na interface."""
    from wiebepy.pressure.engine import volume
    th = np.degrees(d.theta)
    if th[0] <= theta_deg <= th[-1]:
        return (float(np.interp(theta_deg, th, d.P)),
                _("interpolada no ensaio"))
    i = 0 if theta_deg < th[0] else -1
    V0, _dV0, _dd0 = volume(math.radians(float(th[i])), e.Rc, e)
    V1, _dV1, _dd1 = volume(math.radians(theta_deg), e.Rc, e)
    return (float(d.P[i] * (V0 / V1) ** e.kappa),
            tf("extrapolada de {ca:.1f}° (politrópica, κ = {k:g})",
               ca=th[i], k=e.kappa))


def _sincronizar_ensaio(f) -> str | None:
    """O ensaio carregado (aba Dados) define o caso CFD: motor, P e T
    iniciais, comparação e — quando o modelo 0-D estiver ajustado — a
    Wiebe e o Rc do MESMO ajuste. Só sobrescreve o formulário quando o
    ensaio ou o modelo mudam; edições feitas aqui depois são mantidas."""
    d = st.session_state.get("pdata")
    if d is None:
        return None
    eid = _ensaio_id(d)
    if f.get("_ensaio_id") != eid:
        e = st.session_state.engine
        f.update({"bore_mm": e.bore * 1e3, "stroke_mm": e.stroke * 1e3,
                  "rod_length_mm": e.rod_length * 1e3, "rpm": e.rpm,
                  "Rc": e.Rc, "m_fuel_kg_per_cycle": e.m_fuel,
                  "LHV_kJ_per_kg": e.LHV, "T1_K": e.T1, "T0_K": e.T1,
                  "Tw_K": e.Tw,
                  "exp_file": _csv_do_ensaio(eid[0]),
                  "exp_angle_unit": "rad", "exp_pressure_unit": "kPa",
                  "exp_offset_deg": 0.0})
        P0, como = _p_inicial_do_ensaio(
            st.session_state.get("pdata_full") or d,
            float(f["interval_start"]), e)
        f["P0_kPa"] = round(P0, 3)
        f["_P0_origem"] = como
        f["_ensaio_id"] = eid
        f["_modelo_id"] = None
    mid = _modelo_id(st.session_state.get("pmodel"))
    if mid is not None and f.get("_modelo_id") != mid:
        fonte = _estagios_fonte_deg()
        if fonte:
            f["wiebe_origem"] = "modelo atual"
            f["wiebe_stages"] = fonte
            st.session_state["_cfd_n_pendente"] = len(fonte)
            for k in [k for k in st.session_state
                      if str(k).startswith("cfd_editor_")]:
                st.session_state.pop(k, None)
            # Wiebe e Rc saem do mesmo ajuste: usar um sem o outro
            # desfaz a calibração (verification.md §3d)
            f["Rc"] = float(st.session_state.pmodel.get("Rc") or f["Rc"])
        f["_modelo_id"] = mid
    return eid[0]


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


def _cfg_do_form(f=None) -> "CfdConfig":
    from wiebepy.cfd.config import CfdConfig
    # f pode ser um SNAPSHOT capturado no clique: dentro da thread de
    # fundo st.session_state não reflete a sessão (o padrão do projeto é
    # snapshot fora da thread — ver _iniciar_cfd_job).
    if f is None:
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


def _engine_cfg(f=None) -> dict:
    # chaves PLANAS: EngineConfig.from_dict não desembrulha {"engine": …}
    if f is None:
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


def _runner(f=None):
    from wiebepy.cfd.runner import CfdRunner
    from wiebepy.pressure.engine import EngineConfig
    if f is None:
        f = _form()
    cfg = _cfg_do_form(f)
    inst, distro = _solver_install(f["wsl_distro"])
    engine = EngineConfig.from_dict(_engine_cfg(f))
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
with st.expander(_("Configuração do caso"), expanded=True):
    _ensaio_nome = _sincronizar_ensaio(_form())
    if _ensaio_nome:
        _f = _form()
        st.info(tf("Ensaio carregado: **{nome}**. Motor, P inicial "
                   "({p:.1f} kPa, {origem}), comparação", nome=_ensaio_nome,
                   p=_f["P0_kPa"], origem=_f.get("_P0_origem", ""))
                + (_(" e Wiebe/Rc do modelo ajustado")
                   if _f.get("_modelo_id") else
                   _(" (ajuste o modelo 0-D para trazer a Wiebe e o Rc)"))
                + _(" vêm deste ensaio; o caso grava uma cópia dele."),
                icon=":material/link:")
    c1, c2 = st.columns(2)
    with c1:
        f = _form()
        f["case_directory"] = st.text_input(
            _("Diretório do caso"), f["case_directory"])
        f["wsl_distro"] = st.text_input(
            _("Distribuição WSL2 (Windows)"), f["wsl_distro"])
        f["workers"] = st.number_input(
            _("Processos MPI do SOLVER"), 1, 64, f["workers"],
            help=_("Paralelismo do SOLVER (decomposePar/mpirun), distinto "
                 "dos backends CPU/GPU do wiebepy."))
        a1, a2 = st.columns(2)
        f["interval_start"] = a1.number_input(_("Início [°CA]"),
                                              f["interval_start"])
        f["interval_end"] = a2.number_input(_("Fim [°CA]"), f["interval_end"])
        b1, b2, b3 = st.columns(3)
        f["P0_kPa"] = b1.number_input(_("P inicial [kPa]"), f["P0_kPa"])
        f["T0_K"] = b2.number_input(_("T inicial [K]"), f["T0_K"])
        f["Tw_K"] = b3.number_input(_("Paredes [K]"), f["Tw_K"])
    with c2:
        f["turbulence_model"] = st.select_slider(
            _("Turbulência"), ["laminar", "kEpsilon", "kOmegaSST"],
            f["turbulence_model"])
        f["moving_piston"] = st.toggle(_("Pistão móvel"), f["moving_piston"])
        g1, g2 = st.columns(2)
        f["n_radial"] = g1.number_input(_("Células radiais"), 4, 64,
                                        f["n_radial"])
        f["n_axial"] = g2.number_input(_("Células axiais"), 4, 96, f["n_axial"])
        f["distribution"] = st.select_slider(
            _("Distribuição da fonte"), ["uniform", "region"], f["distribution"],
            help=_("uniform = referência (§7); region usa potência total Q "
                 "e herda uma limitação do OF13 com pistão móvel."))
        lista = _lista_combustiveis()
        if f["fuel_name"] not in lista:
            f["fuel_name"] = "diesel"     # ensaio de referência: Diesel
        f["fuel_name"] = st.select_slider(_("Combustível"), lista,
                                          f["fuel_name"],
                                          help=_("Inclui combustíveis "
                                               "cadastrados na aba "
                                               "'Combustíveis'."))
    st.markdown(_("**Motor** (mesmos parâmetros dos modos 0-D)"))
    e = st.columns(4)
    f["bore_mm"] = e[0].number_input(_("Diâmetro [mm]"), f["bore_mm"])
    f["stroke_mm"] = e[1].number_input(_("Curso [mm]"), f["stroke_mm"])
    f["rod_length_mm"] = e[2].number_input(_("Biela [mm]"), f["rod_length_mm"])
    f["Rc"] = e[3].number_input(_("Rc [-]"), f["Rc"])
    e2 = st.columns(4)
    f["rpm"] = e2[0].number_input(_("Rotação [rpm]"), f["rpm"])
    f["m_fuel_kg_per_cycle"] = e2[1].number_input(
        _("m combustível [kg/ciclo]"), f["m_fuel_kg_per_cycle"],
        format="%.6e")
    f["LHV_kJ_per_kg"] = e2[2].number_input(_("PCI [kJ/kg]"), f["LHV_kJ_per_kg"])
    f["T1_K"] = e2[3].number_input(_("T1 [K]"), f["T1_K"])
    st.markdown(_("**Estágios Wiebe (1–5)** — fonte do calor prescrito"))
    f["wiebe_origem"] = st.radio(
        _("Origem"), ["modelo atual", "model.json"], format_func=_,
        index=["modelo atual", "model.json"].index(f["wiebe_origem"]),
        horizontal=True,
        help=_("Modelo atual = estágios do modelo 0-D (modo pressão: "
             "parâmetros da aba Modelo), editáveis AQUI. Os parâmetros "
             "prescritos definem a liberação de calor; o CFD não recalibra "
             "o Wiebe. A edição nesta página não altera o modelo 0-D."))
    if f["wiebe_origem"] == "model.json":
        f["wiebe_model"] = st.text_input(_("Arquivo model.json"),
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
            _("Número de estágios"), list(range(1, MAX_STAGES + 1)),
            key="cfd_wiebe_n", format_func=lambda k: f"{k}-Wiebe",
            help=_("Mudar o número re-cria a tabela (estágios extras entram "
                 "com padrões); use os botões abaixo para re-sincronizar "
                 "com o modelo atual."))
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
                                    help=_("fração da massa do estágio")),
                                "theta0": st.column_config.NumberColumn(
                                    _("θ0 [°]"), format="%.4f",
                                    help=_("início do estágio [°CA]")),
                                "duration": st.column_config.NumberColumn(
                                    _("Δθ [°]"), min_value=1e-6, format="%.4f",
                                    help=_("duração (> 0) [°CA]")),
                                "m": st.column_config.NumberColumn(
                                    "m", min_value=0.0, format="%.4f",
                                    help=_("fator de forma (> 0)")),
                                "a": st.column_config.NumberColumn(
                                    "a", min_value=0.0, format="%.4f",
                                    help=_("eficiência (6.908 ⇒ 99,9 %)"))})
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
            if st.button(_("Usar estágios do modelo atual"),
                         icon=":material/history:",
                         disabled=fonte is None,
                         help=_("Descarta as edições desta página e volta aos "
                              "estágios do modelo 0-D atual.")):
                f["wiebe_stages"] = fonte
                st.session_state.cfd_wiebe_n = len(fonte)
                st.session_state.pop(f"cfd_editor_{len(fonte)}", None)
                st.rerun()
            if st.button(_("Normalizar β (Σβ = 1)"),
                         icon=":material/balance:"):
                soma = sum(s["beta"] for s in f["wiebe_stages"])
                if soma > 0:
                    f["wiebe_stages"] = [
                        {**s, "beta": s["beta"] / soma}
                        for s in f["wiebe_stages"]]
                    st.session_state.pop(f"cfd_editor_{n}", None)
                    st.rerun()

    st.markdown(_("**Gás, numérica e comparação** (equivalência GUI↔CLI)"))
    gcol, ncol = st.columns(2)
    with gcol:
        f["gas_model"] = st.select_slider(
            _("Modelo do gás"), ["simple", "multicomponent_inert"],
            f["gas_model"],
            help=_("simple = Cp/γ constantes (referência case_006); "
                 "multicomponent_inert = N₂+O₂ com NASA janaf (degrau R1 "
                 "do roadmap reativo; sem reação)."))
        f["gas_Cp"] = st.number_input(
            _("Cp do gás [J/(kg·K)]"), f["gas_Cp"],
            disabled=f["gas_model"] != "simple",
            help=_("1063,0 ⇒ γ=1,370 (κ do 0-D; case_006). Ignorado no modo "
                 "multicomponente."))
        f["gas_molWeight"] = st.number_input(
            _("Massa molar [kg/kmol]"), f["gas_molWeight"],
            disabled=f["gas_model"] != "simple",
            help=_("28,96 = ar seco. Ignorado no modo multicomponente "
                 "(N₂+O₂ definidos pela mistura)."))
        f["gas_mu"] = st.number_input(
            _("Viscosidade [Pa·s]"), f["gas_mu"], format="%.2e",
            disabled=f["gas_model"] != "simple",
            help=_("Ignorado no modo multicomponente (sutherland do GRI)."))
        f["gas_Pr"] = st.number_input(
            _("Pr [-]"), f["gas_Pr"],
            disabled=f["gas_model"] != "simple",
            help=_("Ignorado no modo multicomponente."))
    with ncol:
        f["deltaT_s"] = st.number_input(
            _("Δt [s]"), f["deltaT_s"], format="%.2e",
            help=_("Passo de tempo do solver."))
        f["max_Co"] = st.number_input(
            _("max_Co [-]"), f["max_Co"],
            help=_("0,5 ABORTOU neste motor (T negativo perto do PMS — "
                 "verification.md §5b); 0,25 é o padrão seguro."))
        f["write_interval_deg"] = st.number_input(
            _("Escrita a cada [°CA]"), f["write_interval_deg"],
            help=_("Intervalo entre tempos salvos (writeInterval em °CA)."))
    with st.expander(_("Comparação com o ensaio (diagnóstica)"), expanded=False):
        st.caption(_("Sobreposição da pressão medida no relatório HTML. "
                   "Comparação DIAGNÓSTICA — nunca validação (calibrar ≠ "
                   "validar). Deixe o caminho vazio para desativar."))
        f["exp_file"] = st.text_input(_("Arquivo do ensaio (θ,P)"), f["exp_file"])
        c3, c4, c5 = st.columns(3)
        f["exp_angle_unit"] = c3.select_slider(
            _("Unidade do ângulo"), ["rad", "deg"], f["exp_angle_unit"])
        f["exp_pressure_unit"] = c4.select_slider(
            _("Unidade da pressão"), ["kPa", "bar", "MPa", "Pa", "psi"],
            f["exp_pressure_unit"])
        f["exp_offset_deg"] = c5.number_input(
            _("Deslocamento [°CA]"), f["exp_offset_deg"],
            help=_("Offset angular aplicado ao ensaio (sincronismo do "
                 "encoder)."))

# ============================================ geometria do cilindro (Fase C)
with st.expander(_("Geometria do cilindro (esquema)"), expanded=False):
    st.caption(_("Corte lateral com DIÂMETRO e ALTURA da câmara rotulados — "
               "valores direto do formulário. Altura instantânea h(θ) = "
               "folga + deslocamento do pistão (PMS no topo)."))
    f["theta_viz_deg"] = st.slider(_("Posição do pistão θ [°CA]"),
                                   -180.0, 180.0,
                                   f.get("theta_viz_deg", -45.0), 1.0,
                                   key="theta_viz")
    _bore = float(f["bore_mm"]) * 1e-3
    _stroke = float(f["stroke_mm"]) * 1e-3
    _rod = float(f["rod_length_mm"]) * 1e-3
    _rc = float(f["Rc"])
    _folga = _stroke / max(_rc - 1.0, 1e-9)
    _r, _l = _stroke / 2.0, _rod
    _th = math.radians(float(f["theta_viz_deg"]))
    _y = (_l + _r - _r * math.cos(_th)
          - math.sqrt(_l * _l - _r * _r * math.sin(_th) ** 2))
    _h = _folga + _y                  # altura da câmara em θ
    _hp = 0.22 * _stroke              # altura visual do pistão

    import pandas as _pd
    _df_geo = _pd.DataFrame({
        "x": [-_bore / 2, -_bore / 2, _bore / 2, _bore / 2],
        "z": [0.0, _folga + _stroke, 0.0, _folga + _stroke],
        "parede": ["cabeçote", "liner E", "cabeçote", "liner D"]})
    _chart = alt.layer(
        alt.Chart(_pd.DataFrame({"x": [-_bore / 2, _bore / 2],
                                 "z": [0.0, 0.0]})).mark_rule(
            size=4, color="#264653").encode(x="x:Q", y="z:Q"),
        alt.Chart(_df_geo.iloc[[1, 3]]).mark_line(
            size=4, color="#264653").encode(x="x:Q", y="z:Q",
                                            detail="parede:N"),
        alt.Chart(_pd.DataFrame({
            "x": [-_bore / 2 + 0.01 * _stroke, _bore / 2 - 0.01 * _stroke],
            "z1": [_folga + _y, _folga + _y],
            "z2": [_folga + _y + _hp, _folga + _y + _hp]}))
        .mark_rect(color="#8d6e63", opacity=0.85).encode(
            x="x:Q", y="z1:Q", y2="z2:Q"),
        alt.Chart(_pd.DataFrame({
            "x": [0.0], "z": [_h / 2],
            "rot": [tf("altura h(θ) = {h:.1f} mm",
                       h=_h * 1e3)]})).mark_text(
            color="#b3402a", fontSize=12, dy=-6).encode(
            x="x:Q", y="z:Q", text="rot:N"),
        alt.Chart(_pd.DataFrame({
            "x": [0.0], "z": [_folga + _stroke + 0.06 * _stroke],
            "rot": [tf("diâmetro = {d:.1f} mm  |  curso = {s:.1f} mm"
                       "  |  Rc = {rc:.2f}", d=float(f["bore_mm"]),
                       s=float(f["stroke_mm"]), rc=_rc)]})).mark_text(
            color="#264653", fontSize=12).encode(
            x="x:Q", y="z:Q", text="rot:N"),
    ).encode(
        x=alt.X("x:Q", scale=alt.Scale(domain=[-_bore * 0.6,
                                               _bore * 0.6]),
                axis=None),
        y=alt.Y("z:Q", scale=alt.Scale(domain=[_folga + _stroke * 1.15,
                                               -0.08 * _stroke]),
                title=_("z abaixo do cabeçote [m]")))
    st.altair_chart(_chart, use_container_width=True)
    st.caption(tf("h(θ = {ca:.0f}°) = {h:.2f} mm · "
                  "V(θ) = π·(D/2)²·h = {v:.2f} cm³",
                  ca=f["theta_viz_deg"], h=_h * 1e3,
                  v=math.pi * (_bore / 2) ** 2 * _h * 1e6))

    _g1, _g2 = st.columns(2)
    if _g1.button(_("Exportar CSV de geometria"), key="geo_csv"):
        ths = np.arange(-180.0, 180.5, 1.0)
        ys = np.array([_l + _r - _r * math.cos(math.radians(t))
                       - math.sqrt(_l * _l - _r * _r
                                   * math.sin(math.radians(t)) ** 2)
                       for t in ths])
        hs = _folga + ys
        vs = math.pi * (_bore / 2) ** 2 * hs
        csv_geo = "theta_deg,y_pistao_m,h_camara_m,V_m3\n" + "\n".join(
            f"{t:.1f},{y:.8g},{h:.8g},{v:.8g}"
            for t, y, h, v in zip(ths, ys, hs, vs))
        st.download_button(_("Baixar geometria.csv"), csv_geo,
                           "geometria_cilindro.csv", "text/csv",
                           key="geo_csv_dl")
    if _g2.button(_("Exportar PNG do esquema"), key="geo_png"):
        import io as _io
        import matplotlib as _mpl
        _mpl.use("Agg")
        import matplotlib.pyplot as _plt
        fig, ax = _plt.subplots(figsize=(5, 5.5), dpi=130)
        ax.plot([-_bore/2, _bore/2], [0, 0], lw=4, color="#264653")
        for xe in (-_bore/2, _bore/2):
            ax.plot([xe, xe], [0, _folga + _stroke], lw=4, color="#264653")
        ax.add_patch(_plt.Rectangle((-_bore/2, _folga + _y), _bore, _hp,
                                    color="#8d6e63", alpha=0.85))
        ax.annotate("", xy=(-_bore*0.55, 0), xytext=(-_bore*0.55, _h),
                    arrowprops=dict(arrowstyle="<->", color="#b3402a"))
        ax.text(-_bore*0.53, _h/2, f"h = {_h*1e3:.1f} mm",
                color="#b3402a", fontsize=9)
        ax.annotate("", xy=(-_bore/2, _folga + _stroke*1.08),
                    xytext=(_bore/2, _folga + _stroke*1.08),
                    arrowprops=dict(arrowstyle="<->", color="#264653"))
        ax.text(0, _folga + _stroke*1.12,
                tf("diâmetro = {d:.1f} mm", d=float(f["bore_mm"])),
                ha="center", color="#264653", fontsize=9)
        ax.set_xlim(-_bore*0.75, _bore*0.75)
        ax.set_ylim(_folga + _stroke*1.2, -0.05*_stroke)
        ax.set_aspect("equal")
        ax.axis("off")
        buf = _io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")
        _plt.close(fig)
        st.download_button(_("Baixar esquema.png"), buf.getvalue(),
                           "esquema_cilindro.png", "image/png",
                           key="geo_png_dl")

# ========================================================== estado e ações
case_dir = Path(_form()["case_directory"])
from wiebepy.cfd.config import CaseState, read_state   # noqa: E402
state = read_state(case_dir)

with st.container(horizontal=True, vertical_alignment="center"):
    st.metric(_("Estado do caso"), _(state.label), border=True)
    st.metric(_("Solver"), (st.session_state.get("cfd_solver")
                            or _("não verificado")), border=True)
    ocupado = (st.session_state.get("cfd_job") or {}).get("done") is False
    if ocupado:
        st.metric(_("Ação"), f":orange[{_(_job()['tipo'])}…]", border=True)

with st.container(horizontal=True):
    rodar = st.button(_("Preparar caso"), icon=":material/build:",
                      disabled=ocupado,
                      help=_("Gera o caso OpenFOAM para inspeção "
                           "(modo preparação sem execução)."))
    validar = st.button(_("Validar"), icon=":material/fact_check:",
                        disabled=ocupado or not case_dir.exists())
    executar = st.button(_("Executar"), icon=":material/play_arrow:",
                         type="primary", disabled=ocupado)
    cancelar = st.button(_("Cancelar execução"), icon=":material/cancel:",
                         disabled=not ocupado,
                         help=_("Interrompe o solver ativo (incluindo "
                              "processos MPI); logs e parciais preservados."))
    relatorio = st.button(_("Relatório HTML"), icon=":material/description:",
                          disabled=ocupado or state != CaseState.COMPLETED)

if rodar:
    fs = dict(_form())                 # snapshot fora da thread
    pdata_prep = (st.session_state.get("pdata_full")
                  or st.session_state.get("pdata"))
    cfg = _cfg_do_form(fs)
    erros = cfg.validate()
    if erros:
        for e in erros:
            st.error(tf("Configuração inválida: {erro}", erro=e),
                     icon=":material/error:")
    else:
        def _prep(job):
            runner = _runner(fs)
            d = runner.prepare(heat_enabled=True)
            # cópia do ensaio carregado dentro do caso: o relatório
            # compara sempre com a carga que gerou o caso
            if (pdata_prep is not None and fs.get("_ensaio_id")
                    and fs["exp_file"] == _csv_do_ensaio(fs["_ensaio_id"][0])):
                from wiebepy.cfd.reporting import write_exp_csv
                write_exp_csv(Path(d) / fs["exp_file"], pdata_prep.theta,
                              pdata_prep.P, fs["_ensaio_id"][0])
            return str(d)
        _iniciar_cfd_job("preparação do caso", _prep)
        st.rerun()

if validar:
    fs = dict(_form())
    def _val(job):
        from wiebepy.cfd.validation import validate_case
        ok, erros, avisos = validate_case(str(case_dir),
                                          distro=fs["wsl_distro"])
        return {"ok": ok, "erros": erros, "avisos": avisos}
    _iniciar_cfd_job("validação do caso", _val)

if executar:
    fs = dict(_form())
    def _run(job):
        from wiebepy.cfd.validation import validate_case
        ok, erros, _info = validate_case(str(case_dir),
                                     distro=fs["wsl_distro"],
                                     set_validated=False)
        if not ok:
            raise RuntimeError(_("Caso não validado: ") + "; ".join(erros))
        runner = _runner(fs)
        return runner.run(str(case_dir), workers=int(fs["workers"]),
                          on_output=(lambda l: job["log"].append(l)))
    _iniciar_cfd_job("execução CFD", _run)

if cancelar:
    from wiebepy.cfd.runner import CfdRunner
    if CfdRunner.cancel(str(case_dir)):
        st.toast(_("Cancelamento solicitado — o executor vai interromper o "
                 "solver."), icon=":material/cancel:")
    else:
        st.warning(_("Nenhuma execução ativa neste caso."))

if relatorio:
    # O relatório usa SÓ o que o caso gravou (motor e ensaio do
    # case_config.yaml): trocar a carga na aba Dados depois de rodar não
    # pode mudar a comparação de um caso já calculado.
    _info_caso = yaml.safe_load((case_dir / "case_config.yaml").read_text(
        encoding="utf-8")) or {}
    _pd = st.session_state.get("pdata")
    if _pd is not None:
        from wiebepy.cfd.reporting import load_exp_data
        from wiebepy.pressure.engine import EngineConfig
        _exp_caso = load_exp_data(
            case_dir, engine=EngineConfig.from_dict(
                _info_caso.get("engine") or {}))
        _mesmo = False
        if _exp_caso and "p_kPa" in _exp_caso:
            _ca = np.degrees(_pd.theta)
            _m = ((_ca >= _exp_caso["ca_deg"][0])
                  & (_ca <= _exp_caso["ca_deg"][-1]))
            _mesmo = bool(_m.sum() >= 20 and np.max(np.abs(
                np.interp(_ca[_m], _exp_caso["ca_deg"], _exp_caso["p_kPa"])
                / _pd.P[_m] - 1.0)) < 0.01)
        if not _mesmo:
            st.warning(
                tf("O ensaio carregado ({carregado}) não é o deste caso; "
                   "o relatório usa o ensaio gravado no caso ({do_caso}).",
                   carregado=st.session_state.get("data_name"),
                   do_caso=(_exp_caso or {}).get("source", _("nenhum"))),
                icon=":material/warning:")
    def _rep(job):
        from wiebepy.core.parameters import as_stages
        from wiebepy.cfd.reporting import load_exp_data, write_report
        from wiebepy.cfd.results import read_results
        from wiebepy.pressure.engine import EngineConfig
        engine = EngineConfig.from_dict(_info_caso.get("engine") or {})
        try:
            stages = as_stages(_info_caso.get("wiebe_stages") or [])
        except Exception:                               # noqa: BLE001
            stages = None
        res = read_results(case_dir, engine=engine, stages=stages)
        exp = load_exp_data(case_dir, engine=engine)
        return str(write_report(case_dir, res, exp_data=exp))
    _iniciar_cfd_job("geração do relatório", _rep)

# ================================================ crevice_flow (opcional)
# O módulo é opcional: sem config de fresta, esta seção não afeta nenhum
# outro modo do wiebepy (modelos Wiebe intocados).
try:
    from wiebepy.crevice_flow.config import read_crevice_config  # noqa: E402
    _CREVICE_OK = True
except ImportError:                                     # noqa: BLE001
    _CREVICE_OK = False

with st.expander(_("Fresta top-land (crevice_flow — opcional)"),
                 expanded=False):
    if not _CREVICE_OK:
        st.info(_("Módulo crevice_flow não instalado — os demais modos "
                "funcionam normalmente."))
    else:
        st.markdown(
            _("Submodelo: pressão da câmara **prescrita** (o escoamento não "
            "a modifica) e fresta comunicando **apenas** com a câmara — "
            "**não é blow-by**. Sem anéis móveis, óleo, combustão ou "
            "emissões."))
        cfg_path = st.text_input(
            _("Config do caso de fresta (seção crevice:)"),
            "examples/crevice/crevice_exemplo.yaml", key="crevice_cfg")
        cr_case = st.text_input(
            _("Diretório do caso:"), "results/crevice_exemplo",
            key="crevice_case")
        cr_dir = Path(cr_case)
        cr_state = read_state(cr_dir)
        c1, c2, c3, c4, c5 = st.columns(5)
        cr_prep = c1.button(_("Preparar"), key="cr_prep",
                            icon=":material/build:", disabled=ocupado)
        cr_val = c2.button(_("Validar"), key="cr_val",
                           icon=":material/fact_check:",
                           disabled=ocupado or not cr_dir.exists())
        cr_run = c3.button(_("Executar"), key="cr_run", type="primary",
                           icon=":material/play_arrow:", disabled=ocupado)
        cr_can = c4.button(_("Cancelar"), key="cr_can",
                           icon=":material/cancel:", disabled=not ocupado)
        cr_rep = c5.button(_("Relatório HTML"), key="cr_rep",
                           icon=":material/description:",
                           disabled=ocupado)
        st.metric(_("Estado do caso de fresta"), _(cr_state.label),
                  border=True)
        with st.expander(_("Logs e resultados do caso de fresta")):
            log_dir = cr_dir / "logs"
            if log_dir.is_dir():
                for lg in sorted(log_dir.glob("*.log")):
                    st.caption(lg.name)
                    st.code(lg.read_text(encoding="utf-8",
                                         errors="replace")[-3000:],
                            language=None)
            if (cr_dir / "report.html").exists():
                rep_html = (cr_dir / "report.html").read_text(
                    encoding="utf-8", errors="replace")
                st.download_button(_("Baixar relatório HTML do caso"),
                                   rep_html, "report.html", "text/html",
                                   key="cr_dl_rep")

        if cr_prep:
            cfg_snap = str(cfg_path)
            def _cr_prep(job):
                from wiebepy.crevice_flow.runner import (CreviceRunner,
                                                         load_config)
                cfg = load_config(cfg_snap)
                cfg.case_directory = cr_case
                from wiebepy.cfd.capabilities import doctor
                best = doctor().best() or {}
                return str(CreviceRunner(cfg, solver_info=best)
                           .prepare(cr_case))
            _iniciar_cfd_job("preparação do caso de fresta", _cr_prep)
            st.rerun()

        if cr_val:
            case_snap = str(cr_dir)
            def _cr_val(job):
                from wiebepy.crevice_flow.validation import validate_case
                ok, erros, avisos = validate_case(case_snap)
                return {"ok": ok, "erros": erros, "avisos": avisos}
            _iniciar_cfd_job("validação do caso de fresta", _cr_val)

        if cr_run:
            case_snap, cfg_snap = str(cr_dir), str(cfg_path)
            def _cr_run(job):
                from wiebepy.crevice_flow.runner import (CreviceRunner,
                                                         load_config)
                cfg = load_config(cfg_snap)
                cfg.case_directory = case_snap
                from wiebepy.cfd.capabilities import doctor
                best = doctor().best() or {}
                runner = CreviceRunner(cfg, solver_info=best)
                return runner.run(case_snap, workers=1,
                                  on_output=(lambda l:
                                             job["log"].append(l)))
            _iniciar_cfd_job("execução do caso de fresta", _cr_run)

        if cr_can:
            from wiebepy.crevice_flow.runner import CreviceRunner
            if CreviceRunner.cancel(str(cr_dir)):
                st.toast(_("Cancelamento solicitado — o executor vai "
                         "interromper o solver."), icon=":material/cancel:")
            else:
                st.warning(_("Nenhuma execução ativa no caso de fresta."))

        if cr_rep:
            case_snap = str(cr_dir)
            def _cr_rep(job):
                from wiebepy.crevice_flow.report import write_report
                return str(write_report(case_snap))
            _iniciar_cfd_job("relatório da fresta", _cr_rep)

# ------------------------------------------------------- progresso do job
@st.fragment(run_every=1.0)
def _painel_job():
    job = st.session_state.get("cfd_job")
    if job is None:
        return
    if not job["done"]:
        st.info(tf("{tipo} em andamento ({s:.0f} s)… o log do solver "
                   "aparece abaixo.", tipo=_(job["tipo"]),
                   s=time.time() - job["t0"]),
                icon=":material/hourglass_top:")
        linhas = job["log"][-12:]
        if linhas:
            st.code("\n".join(linhas), language=None)
        return
    st.session_state.cfd_job = None
    if job["error"]:
        st.error(tf("Erro em {tipo}: {erro}", tipo=_(job["tipo"]),
                    erro=job["error"]), icon=":material/error:")
    else:
        r = job["result"]
        st.toast(tf("{tipo}: concluído.", tipo=_(job["tipo"])),
                 icon=":material/check_circle:")
        if isinstance(r, dict) and "status" in r:
            if r["status"] == "completed":
                st.success(_("Processo do solver terminou sem erro. "
                           "**Processo terminou ≠ convergiu**: verifique o "
                           "fechamento de energia no relatório."))
            else:
                st.warning(tf("Processo terminou com status “{status}”.",
                              status=r["status"])
                           + (f" {r['note']}" if r.get("note") else ""))
    st.rerun()

_painel_job()

# ============================================ diagnóstico e resultados
with st.expander(_("Diagnóstico do ambiente (doctor)")):
    from wiebepy.cfd.capabilities import (connect_openfoam, doctor,
                                          load_connection)

    conn = load_connection()
    if conn:
        st.success(tf("Conectado: OpenFOAM {versao} na distro "
                      "“{distro}” ({raiz})",
                      versao=conn.get("version") or "?",
                      distro=conn.get("distro"), raiz=conn.get("root")))
    else:
        st.info(_("Nenhuma conexão gravada — detectar e conectar preenche a "
                "distro usada pelos casos."))

    b1, b2 = st.columns(2)
    if b1.button(_("Executar diagnóstico"), icon=":material/stethoscope:",
                 use_container_width=True):
        st.session_state["cfd_doctor"] = doctor().format()
    if b2.button(_("Conectar OpenFOAM ao código"), icon=":material/cable:",
                 use_container_width=True,
                 help=_("Detecta a instalação, VERIFICA que o foamRun "
                      "executa (probe -help), grava a conexão e ajusta a "
                      "distro do formulário. Procura primeiro na distro "
                      "configurada; sem instalação lá, usa a melhor de "
                      "qualquer distro.")):
        f_doc = _form()
        conn_nova, msgs = connect_openfoam(
            distro=f_doc["wsl_distro"] or None)
        if conn_nova is None:
            st.error(_("Não foi possível conectar:") + "\n\n"
                     + "\n".join(f"• {m}" for m in msgs)
                     + "\n\n" + _("Instale o OpenFOAM no WSL2 seguindo "
                                   "docs/cfd/install.md e conecte "
                                   "novamente."))
            st.session_state["cfd_doctor"] = doctor().format()
        else:
            # conectado: a sessão passa a usar a distro conectada
            if conn_nova.get("distro"):
                f_doc["wsl_distro"] = conn_nova["distro"]
            st.session_state["cfd_doctor"] = (
                "\n".join(msgs) + "\n\n" + doctor().format())
    if st.session_state.get("cfd_doctor"):
        st.code(st.session_state["cfd_doctor"], language=None)

res_prontos = state == CaseState.COMPLETED
if res_prontos or state in (CaseState.CANCELLED, CaseState.FAILED):
    with st.expander(_("Resultados (0-D extraídos do caso 3D)"),
                     expanded=res_prontos):
        if state != CaseState.COMPLETED:
            st.warning(tf("Estado do caso: {estado} — resultados parciais "
                          "podem estar disponíveis nos diretórios de "
                          "tempo gravados.", estado=_(state.label)))
        try:
            from wiebepy.core.parameters import as_stages
            from wiebepy.cfd.results import read_results
            from wiebepy.pressure.engine import EngineConfig
            info = yaml.safe_load((case_dir / "case_config.yaml")
                                  .read_text(encoding="utf-8")) or {}
            # motor gravado no caso, não o do formulário atual
            engine = EngineConfig.from_dict(info.get("engine") or {})
            stages = None
            try:
                stages = as_stages(info.get("wiebe_stages") or [])
            except Exception:                           # noqa: BLE001
                pass
            r = read_results(case_dir, engine=engine, stages=stages)
        except Exception as e:                          # noqa: BLE001
            st.info(tf("Resultados ainda não legíveis: {erro}", erro=e))
            st.stop()
        m1, m2, m3, m4 = st.columns(4)
        m1.metric(_("p̄ máx"), f"{r['p_mean'].max() / 1e6:.2f} MPa")
        m2.metric(_("T̄ máx"), f"{r['T_mean'].max():.0f} K")
        m3.metric(_("Trabalho indicado"),
                  f"{r['indicated_work_J']:.1f} J")
        m4.metric(_("Perda nas paredes"), f"{r['wall_loss_J']:.1f} J")
        hs = info.get("heat_source", {}).get("energy_check", {})
        st.caption(tf("Energia prescrita pela Wiebe: {q:.1f} J "
                      "(erro {erro:.1e}). Média de volume do solver "
                      "(não confundir com sonda nem com pressão medida).",
                      q=hs.get("integral_J", float("nan")),
                      erro=hs.get("rel_error", float("nan"))))
        # campo SEM colchete: "[...]" no nome do campo é interpretado pelo
        # Vega como acesso aninhado (gráfico em branco); unidades no title
        df = pd.DataFrame({"θ": r["ca_deg"],
                           "p̄ [MPa]": r["p_mean"] / 1e6,
                           "T̄ [K]": r["T_mean"]})
        st.altair_chart(alt.Chart(df.melt("θ")).mark_line().encode(
            x=alt.X("θ:Q", title="θ [°CA]"), y=alt.Y("value:Q", title=None),
            color="variable:N").properties(height=300), use_container_width=True)
        st.markdown(tf("Relatório completo (proveniência, balanços, "
                       "limites): `{arquivo}` — gere/atualize com o botão "
                       "**Relatório HTML**.",
                       arquivo=case_dir / "report.html"))