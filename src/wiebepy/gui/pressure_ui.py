# -*- coding: utf-8 -*-
"""
pressure_ui.py — Interface do MODO PRESSÃO (ajuste da curva de pressão do
cilindro com liberação de calor Wiebe de 1 a 5 estágios, modelo 0-D do
Double Wiebe). Chamado pelas páginas quando o tipo de dado é "pressão".
Ângulos exibidos em graus; internamente em rad.
"""
from __future__ import annotations

import io
import json
import math
import tempfile
import time
import zipfile
from dataclasses import replace
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

from ..core.core import multistage_wiebe
from ..core.derivatives import multistage_wiebe_derivative
from ..core.parameters import MAX_STAGES, Stage, as_stages, validate_stages
from ..pressure.engine import EngineConfig
from ..pressure.fit import (PRESSURE_FACTORS_KPA, PressureSettings,
                            compare_pressure, fit_pressure,
                            pressure_from_arrays, pressure_metrics)
from ..pressure.model import ODEFailure, simulate
from . import state as S

G = math.pi / 180.0
EXEMPLO = "ensaio_P_exp_carga3_45"


def _exemplo_path():
    p = Path(__file__).resolve().parents[3] / "examples" / "data" / f"{EXEMPLO}.txt"
    return p if p.exists() else None


# =============================================================================
# Dados
# =============================================================================
def dados() -> None:
    st.caption("Arquivo com duas colunas: ângulo do virabrequim e pressão do "
               "cilindro (θ = 0 no PMS de combustão). O ajuste segue a mesma "
               "abordagem do Double Wiebe, com 1 a 5 estágios de liberação de "
               "calor.")
    with st.container(border=True):
        with st.container(horizontal=True):
            ang = st.segmented_control("Unidade do ângulo no arquivo",
                                       ["rad", "deg"], default="rad",
                                       key="p_ang",
                                       format_func=lambda u: "radianos" if u == "rad" else "graus")
            pun = st.segmented_control("Unidade da pressão",
                                       list(PRESSURE_FACTORS_KPA), default="bar",
                                       key="p_un")
        with st.container(horizontal=True):
            tmin = st.number_input("θ mínimo usado [°]", value=-114.59,
                                   format="%.2f", key="p_tmin",
                                   help="Janela do ajuste (padrão = −2 a 2 rad, "
                                        "a mesma do Double Wiebe).")
            tmax = st.number_input("θ máximo usado [°]", value=114.59,
                                   format="%.2f", key="p_tmax")
        origem = st.segmented_control("Origem", ["Arquivo", "Ensaio de exemplo"],
                                      default="Arquivo", key="p_origem")
        arq = None
        if origem == "Arquivo":
            arq = st.file_uploader("Arquivo de pressão",
                                   type=["txt", "csv", "dat", "tsv"], key="p_upl")
        else:
            st.caption("Ensaio real P_exp-Carga-3_45% (θ em rad, P em bar), o "
                       "mesmo usado no Double Wiebe.")
        carregar = st.button("Carregar pressão", type="primary",
                             icon=":material/upload:",
                             disabled=(origem == "Arquivo" and arq is None)
                             or (origem != "Arquivo" and _exemplo_path() is None))
    motor()
    if carregar:
        try:
            if origem == "Arquivo":
                bruto = arq.getvalue().decode("utf-8-sig")
                nome = arq.name
            else:
                bruto = _exemplo_path().read_text(encoding="utf-8")
                nome = _exemplo_path().name
                ang, pun = "rad", "bar"
            from ..io.readers import _parse_table
            cols = _parse_table(bruto, nome)
            chaves = list(cols)
            th = cols.get("theta", cols[chaves[0]])
            P = cols[[k for k in chaves if k != "theta"][0]]
            d = pressure_from_arrays(th, P, ang or "rad", pun or "bar",
                                     (tmin or -114.59) * G, (tmax or 114.59) * G,
                                     nome)
        except (ValueError, IndexError, KeyError) as e:
            st.error(f"Não foi possível ler a pressão: {e}")
        else:
            st.session_state.pdata = d
            st.session_state.mode = "pressure"
            st.session_state.data_name = nome
            st.session_state.pmodel = None
            st.rerun()

    d = st.session_state.pdata
    if d is None:
        st.info("Nenhuma curva de pressão carregada.", icon=":material/info:")
        return
    with st.container(horizontal=True):
        st.metric("Pontos", d.n, border=True)
        st.metric("θ [°]", f"{math.degrees(d.theta[0]):.1f} … "
                           f"{math.degrees(d.theta[-1]):.1f}", border=True)
        st.metric("P máx [kPa]", f"{d.P.max():.0f}", border=True)
        st.metric("θ de P máx [°]", f"{math.degrees(d.theta[np.argmax(d.P)]):.2f}",
                  border=True)
    for w in d.warnings:
        st.warning(w, icon=":material/warning:")
    df = pd.DataFrame({"θ": np.degrees(d.theta), "P": d.P})
    st.altair_chart(alt.Chart(df).mark_line().encode(
        x=alt.X("θ:Q", title="θ [°]"), y=alt.Y("P:Q", title="P [kPa]")
    ).properties(title="Pressão medida", height=320).interactive())


def motor() -> EngineConfig:
    """Editor dos dados do motor (padrões = motor do ensaio do Double Wiebe)."""
    e = st.session_state.engine
    with st.expander("Motor (geometria e combustível)"):
        with st.container(horizontal=True):
            bore = st.number_input("Diâmetro [mm]", value=e.bore * 1e3, key="e_bore")
            stroke = st.number_input("Curso [mm]", value=e.stroke * 1e3, key="e_stroke")
            rod = st.number_input("Biela [mm]", value=e.rod_length * 1e3, key="e_rod")
            rpm = st.number_input("Rotação [rpm]", value=e.rpm, key="e_rpm")
        with st.container(horizontal=True):
            rc = st.number_input("Rc (inicial/fixo)", value=e.Rc, key="e_rc")
            mf = st.number_input("Massa de comb. [kg/ciclo]", value=e.m_fuel,
                                 format="%.6e", key="e_mf")
            lhv = st.number_input("PCI [kJ/kg]", value=e.LHV, key="e_lhv")
            kap = st.number_input("κ", value=e.kappa, format="%.3f", key="e_k")
        with st.container(horizontal=True):
            t1 = st.number_input("T inicial [K]", value=e.T1, key="e_t1")
            tw = st.number_input("T parede [K]", value=e.Tw, key="e_tw")
            ht = st.toggle("Perda de calor (Hohenberg)", value=e.heat_transfer,
                           key="e_ht")
    novo = EngineConfig(bore=bore / 1e3, stroke=stroke / 1e3,
                        rod_length=rod / 1e3, rpm=rpm, Rc=rc, m_fuel=mf,
                        LHV=lhv, kappa=kap, T1=t1, Tw=tw, heat_transfer=ht)
    erros = novo.validate()
    for er in erros:
        st.error(er)
    if not erros:
        st.session_state.engine = novo
    return st.session_state.engine


# =============================================================================
# Gráficos
# =============================================================================
def grafico_pressao(d, P_sim):
    df = pd.concat([
        pd.DataFrame({"θ": np.degrees(d.theta), "P": d.P, "curva": "medida"}),
        pd.DataFrame({"θ": np.degrees(d.theta), "P": P_sim, "curva": "simulada"})])
    return alt.Chart(df).mark_line().encode(
        x=alt.X("θ:Q", title="θ [°]"), y=alt.Y("P:Q", title="P [kPa]"),
        color=alt.Color("curva:N", title=None,
                        scale=alt.Scale(domain=["medida", "simulada"],
                                        range=["#8a93a3", "#d62728"])),
        strokeDash=alt.condition(alt.datum.curva == "medida", alt.value([1, 0]),
                                 alt.value([6, 3]))
    ).properties(title="Pressão: medida × simulada", height=340).interactive()


def grafico_residuo(d, P_sim):
    df = pd.DataFrame({"θ": np.degrees(d.theta), "resíduo": P_sim - d.P})
    return (alt.Chart(df).mark_line().encode(
        x=alt.X("θ:Q", title="θ [°]"), y=alt.Y("resíduo:Q", title="P sim − P med [kPa]"))
        + alt.Chart(pd.DataFrame({"y": [0]})).mark_rule().encode(y="y:Q")
    ).properties(title="Resíduo de pressão", height=260).interactive()


def _graus(stages):
    return [Stage(s.beta, math.degrees(s.theta0), math.degrees(s.duration), s.m, s.a)
            for s in as_stages(stages)]


def graficos_queima(d, stages_rad):
    """x_b e dx_b/dθ (por grau) dos estágios, com contribuições."""
    st_deg = _graus(stages_rad)
    th = np.linspace(math.degrees(d.theta[0]), math.degrees(d.theta[-1]), 1500)
    antes = st.session_state.angle_unit
    st.session_state.angle_unit = "deg"
    try:
        return (S.grafico_curvas(th, st_deg, None, "xb", True),
                S.grafico_curvas(th, st_deg, None, "dxb", True))
    finally:
        st.session_state.angle_unit = antes


def tabela(Rc, stages_rad):
    linhas = [{"estágio": j, "β": s.beta, "θ0 [°]": math.degrees(s.theta0),
               "Δθ [°]": math.degrees(s.duration), "m": s.m, "a": s.a}
              for j, s in enumerate(as_stages(stages_rad), start=1)]
    return pd.DataFrame(linhas), Rc


# =============================================================================
# Modelo (parâmetros editáveis + simulação solve_ivp)
# =============================================================================
def modelo() -> None:
    d = st.session_state.pdata
    e = st.session_state.engine
    atual = st.session_state.pmodel
    n_padrao = len(atual["stages"]) if atual else 2
    if "_pmodelo_n_pendente" in st.session_state:
        st.session_state.pmodelo_n = st.session_state.pop("_pmodelo_n_pendente")
    st.session_state.setdefault("pmodelo_n", n_padrao)
    n = st.segmented_control("Número de estágios", list(range(1, MAX_STAGES + 1)),
                             key="pmodelo_n", format_func=lambda k: f"{k}-Wiebe")
    n = n or n_padrao
    if atual is None or len(atual["stages"]) != n:
        padrao = [Stage(1 / n, (-10 + 12 * j) * G, (20 + 15 * j) * G,
                        2.0 if j == 0 else 1.0, 6.9078) for j in range(n)]
        atual = {"Rc": e.Rc, "stages": [s.to_dict() for s in padrao]}
        st.session_state.pmodel = atual
    with st.container(border=True):
        rc = st.number_input("Rc", value=float(atual["Rc"]), format="%.4f",
                             key=f"pm_rc_{n}")
        tab = pd.DataFrame([{"beta": s.beta, "theta0": math.degrees(s.theta0),
                             "duration": math.degrees(s.duration), "m": s.m,
                             "a": s.a} for s in as_stages(atual["stages"])])
        ed = st.data_editor(tab, key=f"peditor_{n}", num_rows="fixed",
                            column_config={
                                "beta": st.column_config.NumberColumn("β", min_value=0.0, max_value=1.0, format="%.4f"),
                                "theta0": st.column_config.NumberColumn("θ0 [°]", format="%.3f"),
                                "duration": st.column_config.NumberColumn("Δθ [°]", min_value=0.0, format="%.3f"),
                                "m": st.column_config.NumberColumn("m", min_value=0.0, format="%.4f"),
                                "a": st.column_config.NumberColumn("a", min_value=0.0, format="%.4f")})
        stages = [Stage(float(r.beta), float(r.theta0) * G, float(r.duration) * G,
                        float(r.m), float(r.a)) for r in ed.itertuples()]
        with st.container(horizontal=True):
            if st.button("Normalizar β", icon=":material/balance:"):
                soma = sum(s.beta for s in stages) or 1.0
                st.session_state.pmodel = {"Rc": rc, "stages": [
                    Stage(s.beta / soma, s.theta0, s.duration, s.m, s.a).to_dict()
                    for s in stages]}
                st.session_state.pop(f"peditor_{n}", None)
                st.rerun()
            fit = st.session_state.pfit_result
            if st.button("Usar o último ajuste", icon=":material/history:",
                         disabled=fit is None):
                aplicar(fit.Rc, fit.stages)
                st.rerun()
    erros = validate_stages(stages)
    if erros:
        for er in erros:
            st.error(er)
        return
    st.session_state.pmodel = {"Rc": rc, "stages": [s.to_dict() for s in stages]}
    if d is None:
        st.info("Carregue uma curva de pressão (página Dados) para simular.")
    else:
        try:
            P_sim, _, _ = simulate(d.theta, float(d.P[0]), stages, e, rc)
        except ODEFailure as ex:
            st.error(f"A simulação falhou com estes parâmetros: {ex}")
        else:
            m = pressure_metrics(d.P, P_sim, 4 * n)
            with st.container(horizontal=True):
                st.metric("RMSE [kPa]", f"{m['rmse']:.3f}", border=True)
                st.metric("R²", f"{m['r2']:.6f}", border=True)
                st.metric("P máx sim/med [kPa]",
                          f"{m['P_max_sim_kPa']:.0f} / {m['P_max_exp_kPa']:.0f}",
                          border=True)
            st.altair_chart(grafico_pressao(d, P_sim))
    g1, g2 = st.columns(2)
    if d is not None:
        a, b = graficos_queima(d, stages)
        g1.altair_chart(a)
        g2.altair_chart(b)


def aplicar(Rc, stages_rad) -> None:
    n = len(stages_rad)
    st.session_state.pmodel = {"Rc": float(Rc),
                               "stages": [s.to_dict() for s in stages_rad]}
    st.session_state.pop(f"peditor_{n}", None)
    st.session_state.pop(f"pm_rc_{n}", None)
    st.session_state._pmodelo_n_pendente = n


# =============================================================================
# Ajuste
# =============================================================================
def _settings_form(chave: str, comparacao: bool = False):
    from ..parallel.backend import available_backends
    backends = ["auto"] + [b for b in available_backends()
                           if b in ("numba", "cupy", "numpy")]
    with st.container(horizontal=True):
        n = None if comparacao else st.selectbox(
            "Número de estágios", range(1, MAX_STAGES + 1), index=1,
            format_func=lambda k: f"{k}-Wiebe", key=f"{chave}_n")
        runs = st.number_input("Runs" + (" por N" if comparacao else ""), 1, 50,
                               3, key=f"{chave}_runs")
        fit_rc = st.toggle("Ajustar Rc", value=True, key=f"{chave}_rc",
                           help="Como no Double Wiebe; desligado, usa o Rc do motor.")
    with st.expander("Opções avançadas"):
        with st.container(horizontal=True):
            part = st.number_input("Partículas", 4, 2000, 60, key=f"{chave}_p")
            it = st.number_input("Iterações", 1, 20000, 400, key=f"{chave}_it")
            seed = st.number_input("Semente", 0, 10**9, 42, key=f"{chave}_seed")
            sub = st.number_input("Sub-passos RK4", 1, 32, 4, key=f"{chave}_sub")
        with st.container(horizontal=True):
            backend = st.selectbox("Backend", backends, key=f"{chave}_be",
                                   help="numba (CPU) é o mais rápido na maioria "
                                        "dos casos; cupy usa a GPU")
            prec = st.selectbox("Precisão", ["float64", "float32"], key=f"{chave}_pr")
            rc_lo = st.number_input("Rc mín", value=14.0, key=f"{chave}_rclo")
            rc_hi = st.number_input("Rc máx", value=20.0, key=f"{chave}_rchi")
        with st.container(horizontal=True):
            d_lo = st.number_input("Δθ mín [°]", value=2.0, key=f"{chave}_dlo")
            d_hi = st.number_input("Δθ máx [°]", value=90.0, key=f"{chave}_dhi")
            t_lo = st.number_input("θ0₁ mín [°]", value=-30.0, key=f"{chave}_tlo")
            t_hi = st.number_input("θ0₁ máx [°]", value=10.0, key=f"{chave}_thi")
    s = PressureSettings(
        n_stages=int(n or 2), engine=st.session_state.engine, fit_rc=fit_rc,
        rc_bounds=(rc_lo, rc_hi), particles=int(part), iterations=int(it),
        runs=int(runs), seed=int(seed), backend=backend, precision=prec,
        substeps=int(sub),
        bounds_deg={"theta0": (t_lo, t_hi), "dtheta0": (0.0, 40.0),
                    "duration": (d_lo, d_hi), "theta0_max": 40.0})
    return s


def ajuste() -> None:
    d = st.session_state.pdata
    if d is None:
        st.info("Carregue uma curva de pressão na página **Dados**.")
        return
    job = S.job_ativo()
    ocupado = job is not None and not job["done"]
    with st.form("form_pajuste"):
        s = _settings_form("pa")
        ok = st.form_submit_button("Iniciar ajuste", type="primary",
                                   icon=":material/play_arrow:", disabled=ocupado)
    if ok:
        def tarefa(job, d=d, s=s):
            def prog(run, it, best, x):
                job.update(etapa=f"run {run + 1}/{s.runs}", iter=it, best=best,
                           frac=(run + it / s.iterations) / s.runs)
                return job["cancel"]
            return fit_pressure(d, s, prog)
        S.iniciar_job("ajuste de pressão", tarefa, s.runs)
        st.rerun()
    painel("ajuste de pressão", "pfit_result")
    r = st.session_state.pfit_result
    if r is None:
        return
    st.subheader(f"Resultado — {r.settings.n_stages}-Wiebe (pressão)", anchor=False)
    if not r.metrics:
        st.error("A referência solve_ivp falhou: resultado inválido.")
        return
    m = r.metrics
    with st.container(horizontal=True):
        st.metric("RMSE [kPa]", f"{m['rmse']:.3f}", border=True)
        st.metric("R²", f"{m['r2']:.6f}", border=True)
        st.metric("Rc", f"{r.Rc:.4f}", border=True)
        st.metric("P máx sim/med [kPa]",
                  f"{m['P_max_sim_kPa']:.0f} / {m['P_max_exp_kPa']:.0f}", border=True)
        st.metric("Tempo", f"{r.elapsed_s:.1f} s", border=True)
    st.caption(f"RMSE da referência solve_ivp (DOP853). Backend da busca: "
               f"{r.backend}. Runs: " + ", ".join(f"{x.rmse:.3f}" for x in r.runs))
    df, _ = tabela(r.Rc, r.stages)
    st.dataframe(df, hide_index=True, column_config={
        c: st.column_config.NumberColumn(format="%.5g") for c in df.columns[1:]})
    if st.button("Aplicar ao modelo", icon=":material/check:", key="pa_aplicar"):
        aplicar(r.Rc, r.stages)
        st.toast("Parâmetros aplicados à página Modelo.")
    if r.warnings:
        with st.expander(f"Avisos ({len(r.warnings)})", icon=":material/warning:"):
            for w in r.warnings:
                st.markdown(f"- `{w}`")
    st.altair_chart(grafico_pressao(d, r.P_sim))
    st.altair_chart(grafico_residuo(d, r.P_sim))
    a, b = graficos_queima(d, r.stages)
    g1, g2 = st.columns(2)
    g1.altair_chart(a)
    g2.altair_chart(b)


def painel(tipo: str, destino: str) -> None:
    @st.fragment(run_every=0.5)
    def _painel():
        job = S.job_ativo(tipo)
        if job is None:
            return
        if job["done"]:
            if job["error"]:
                st.error(f"Erro: {job['error']}")
            elif job["result"] is not None:
                st.session_state[destino] = job["result"]
            st.session_state.job = None
            st.rerun()
        with st.container(border=True):
            txt = (f"{job['etapa']} · iteração {job['iter']} · melhor "
                   f"{job['best']:.4f} kPa (RK4)" if job["best"] is not None
                   else "preparando (compilação do kernel na 1ª vez)…")
            st.progress(min(1.0, job.get("frac", 0.0)), text=txt)
            with st.container(horizontal=True, vertical_alignment="center"):
                st.caption(f"Decorrido: {time.time() - job['t0']:.0f} s")
                if st.button("Cancelar", icon=":material/stop:",
                             disabled=job["cancel"], key=f"cancel_{destino}"):
                    job["cancel"] = True
            if job["log"]:
                st.code("\n".join(job["log"][-6:]), language=None)
    _painel()


# =============================================================================
# Comparação
# =============================================================================
def comparacao() -> None:
    d = st.session_state.pdata
    if d is None:
        st.info("Carregue uma curva de pressão na página **Dados**.")
        return
    job = S.job_ativo()
    ocupado = job is not None and not job["done"]
    with st.form("form_pcomp"):
        ns = st.pills("Números de estágios", [1, 2, 3, 4, 5], selection_mode="multi",
                      default=[1, 2, 3], format_func=lambda k: f"{k}-Wiebe")
        folds = st.number_input("Folds da validação cruzada", 0, 20, 5)
        s = _settings_form("pc", comparacao=True)
        ok = st.form_submit_button("Comparar", type="primary",
                                   icon=":material/play_arrow:", disabled=ocupado)
    if ok:
        if not ns or len(ns) < 2:
            st.error("Escolha ao menos dois números de estágios.")
        else:
            lista = sorted(ns)

            def tarefa(job, d=d, s=s, lista=lista, folds=int(folds)):
                def prog(fase, k, it, best):
                    job.update(etapa=(f"ajuste {k}-Wiebe" if fase == "fit"
                                      else f"validação cruzada, fold {k + 1}"),
                               iter=it, best=best)
                    return job["cancel"]
                return compare_pressure(d, lista, s, folds, progress=prog)
            S.iniciar_job("comparação de pressão", tarefa, len(lista))
            st.rerun()
    painel("comparação de pressão", "pcompare_result")
    res = st.session_state.pcompare_result
    if res is None:
        return
    if res.get("cancelled"):
        st.warning("Comparação cancelada: resultados parciais.")
    st.success(f"Modelo recomendado: **{res['recommended']}-Wiebe** — "
               f"{res['reason']}.", icon=":material/recommend:")
    tab = pd.DataFrame(res["table"])
    cols = {"n_stages": "N", "k": "k", "rmse": "RMSE [kPa]",
            "cv_rmse": "CV RMSE [kPa]", "r2": "R²", "delta_aic": "ΔAIC",
            "delta_bic": "ΔBIC", "durbin_watson": "Durbin-Watson",
            "n_warnings": "avisos", "time_s": "tempo [s]"}
    st.dataframe(tab[list(cols)].rename(columns=cols), hide_index=True,
                 column_config={c: st.column_config.NumberColumn(format="%.5g")
                                for c in list(cols.values())[2:]})
    e1, e2 = S.grafico_comparacao(res["table"])
    g1, g2 = st.columns(2)
    g1.altair_chart(e1)
    g2.altair_chart(e2)
    esc = st.segmented_control("Detalhe", sorted(res["results"]),
                               default=res["recommended"], key="pc_det",
                               format_func=lambda k: f"{k}-Wiebe")
    if esc:
        r = res["results"][esc]
        df, _ = tabela(r.Rc, r.stages)
        st.caption(f"Rc = {r.Rc:.4f}")
        st.dataframe(df, hide_index=True)
        with st.container(horizontal=True):
            if st.button("Aplicar ao modelo", key="pc_aplicar",
                         icon=":material/check:"):
                aplicar(r.Rc, r.stages)
                st.toast("Parâmetros aplicados à página Modelo.")
            if st.button("Usar como resultado de ajuste", key="pc_usar",
                         icon=":material/tune:"):
                st.session_state.pfit_result = r
                st.toast("Disponível na página Ajuste.")
        st.altair_chart(grafico_pressao(d, r.P_sim))


# =============================================================================
# Exportação
# =============================================================================
def zip_pressao(r, d, comp=None) -> bytes:
    from ..pressure.report import write_outputs
    with tempfile.TemporaryDirectory() as tmp:
        out = write_outputs(Path(tmp), r, d, comp, plots=True)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for p_ in sorted(out.rglob("*")):
                if p_.is_file():
                    z.write(p_, p_.relative_to(out).as_posix())
        return buf.getvalue()


def exportar() -> None:
    d = st.session_state.pdata
    r = st.session_state.pfit_result
    comp = st.session_state.pcompare_result
    if d is None or (r is None and comp is None):
        st.info("Faça um ajuste ou uma comparação de pressão para exportar.")
        return
    alvo = r if r is not None else comp["results"][comp["recommended"]]
    df, _ = tabela(alvo.Rc, alvo.stages)
    st.caption(f"{alvo.settings.n_stages}-Wiebe · Rc = {alvo.Rc:.4f} · "
               f"RMSE = {alvo.metrics.get('rmse', float('nan')):.3f} kPa")
    st.dataframe(df, hide_index=True)
    if st.button("Preparar .zip", type="primary", icon=":material/folder_zip:"):
        st.session_state.exp_pzip = zip_pressao(alvo, d, comp)
    if st.session_state.get("exp_pzip"):
        st.download_button("Baixar resultados_pressao.zip", st.session_state.exp_pzip,
                           file_name="wiebepy_pressao.zip", mime="application/zip",
                           icon=":material/download:")
