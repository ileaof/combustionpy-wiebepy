# -*- coding: utf-8 -*-
"""Página Comparação: ajusta vários números de estágios e recomenda N por
validação cruzada em blocos (AIC/BIC como indicativos)."""
import time

import pandas as pd
import streamlit as st

from wiebepy.gui import state as S
from wiebepy.optimization.compare import compare_stages
from wiebepy.optimization.fit import FitSettings
from wiebepy.parallel.backend import available_backends

st.header("Comparação entre números de estágios", anchor=False)
d = st.session_state.data
if d is None:
    st.info("Carregue dados na página **Dados** para comparar modelos.",
            icon=":material/info:")
    st.stop()

st.caption("Mais estágios sempre reduzem o erro de treino. A recomendação usa o "
           "menor N cujo erro de validação cruzada fica a até 5 % do melhor e que "
           "não tem estágios desprezíveis ou coincidentes; AIC/BIC são "
           "indicativos (supõem resíduos independentes).")

alvos = [a for a, ok in (("xb", d.xb is not None), ("dxb", d.dxb is not None),
                         ("both", d.xb is not None and d.dxb is not None)) if ok]
NOMES_ALVO = {"xb": "x_b", "dxb": "dx_b/dθ", "both": "x_b e dx_b/dθ"}
job = S.job_ativo()
ocupado = job is not None and not job["done"]

with st.form("form_comparacao"):
    ns = st.pills("Números de estágios", [1, 2, 3, 4, 5], selection_mode="multi",
                  default=[1, 2, 3, 4, 5], format_func=lambda k: f"{k}-Wiebe")
    with st.container(horizontal=True):
        alvo = st.selectbox("Série ajustada", alvos, format_func=NOMES_ALVO.get)
        runs = st.number_input("Runs por N", 1, 50, 5)
        folds = st.number_input("Folds da validação cruzada", 0, 20, 5,
                                help="0 desliga a validação cruzada (usa BIC)")
    with st.expander("Opções avançadas"):
        with st.container(horizontal=True):
            particulas = st.number_input("Partículas", 4, 5000, 100)
            iteracoes = st.number_input("Iterações", 1, 20000, 1000)
            semente = st.number_input("Semente", 0, 10**9, 42)
            backend = st.selectbox("Backend", ["auto"] + [
                b for b in available_backends() if b != "multiprocessing"])
    iniciar = st.form_submit_button("Comparar", type="primary",
                                    icon=":material/play_arrow:", disabled=ocupado)

if iniciar:
    if not ns or len(ns) < 2:
        st.error("Escolha ao menos dois números de estágios.")
    else:
        base = FitSettings(fit_target=alvo, runs=int(runs),
                           particles=int(particulas), iterations=int(iteracoes),
                           seed=int(semente), backend=backend,
                           parallel_runs="no")
        lista = sorted(ns)

        def tarefa(job, dados=d, base=base, lista=lista, folds=int(folds)):
            def progresso(fase, k, it, melhor):
                rotulo = (f"ajuste {k}-Wiebe" if fase == "fit"
                          else f"validação cruzada, fold {k + 1}/{folds}")
                job.update(etapa=rotulo, iter=it, best=melhor)
                return job["cancel"]
            return compare_stages(dados, lista, base, folds, progress=progresso)

        S.iniciar_job("comparação", tarefa, len(lista))
        st.rerun()


@st.fragment(run_every=0.5)
def painel_progresso():
    job = S.job_ativo("comparação")
    if job is None:
        return
    if job["done"]:
        if job["error"]:
            st.error(f"Erro na comparação: {job['error']}", icon=":material/error:")
        elif job["result"] is not None:
            st.session_state.compare_result = job["result"]
        st.session_state.job = None
        st.rerun()
    with st.container(border=True):
        feitos = sum("=== Modelo" in l for l in job["log"])
        st.progress(min(1.0, max(feitos - 1, 0) / max(job["total"], 1)),
                    text=f"{job['etapa'] or 'preparando…'} · iteração {job['iter']}")
        with st.container(horizontal=True, vertical_alignment="center"):
            st.caption(f"Decorrido: {time.time() - job['t0']:.0f} s")
            if st.button("Cancelar", icon=":material/stop:",
                         disabled=job["cancel"]):
                job["cancel"] = True
        if job["log"]:
            st.code("\n".join(job["log"][-6:]), language=None)


painel_progresso()

res = st.session_state.compare_result
if res is None:
    st.stop()

if res.get("cancelled"):
    st.warning("Comparação cancelada: resultados parciais, não use a "
               "recomendação.", icon=":material/warning:")
st.success(f"Modelo recomendado: **{res['recommended']}-Wiebe** — {res['reason']}.",
           icon=":material/recommend:")

tab = pd.DataFrame(res["table"])
colunas = {"n_stages": "N", "k": "k", "rmse": "RMSE", "cv_rmse": "CV RMSE",
           "mae": "MAE", "see": "SEE", "r2": "R²", "delta_aic": "ΔAIC",
           "delta_bic": "ΔBIC", "durbin_watson": "Durbin-Watson",
           "n_warnings": "avisos", "time_s": "tempo [s]"}
vis = tab[list(colunas)].rename(columns=colunas)
st.dataframe(vis, hide_index=True, column_config={
    c: st.column_config.NumberColumn(format="%.4g")
    for c in ("RMSE", "CV RMSE", "MAE", "SEE", "R²", "ΔAIC", "ΔBIC",
              "Durbin-Watson", "tempo [s]")})
g1, g2 = st.columns(2)
erro, crit = S.grafico_comparacao(res["table"])
g1.altair_chart(erro)
g2.altair_chart(crit)

st.subheader("Detalhe de um modelo", anchor=False)
ns_disp = sorted(res["results"])
escolhido = st.segmented_control("Modelo", ns_disp, default=res["recommended"],
                                 format_func=lambda k: f"{k}-Wiebe",
                                 key="comp_detalhe")
if escolhido:
    r = res["results"][escolhido]
    st.dataframe(S.tabela_estagios(r.stages), hide_index=True)
    with st.container(horizontal=True):
        if st.button("Aplicar ao modelo", icon=":material/check:",
                     key="comp_aplicar"):
            S.aplicar_ao_modelo(r.stages)
            st.session_state._modelo_n_pendente = escolhido
            st.session_state.pop(f"editor_{escolhido}", None)
            st.toast("Parâmetros aplicados à página Modelo.",
                     icon=":material/check:")
        if st.button("Usar como resultado de ajuste", icon=":material/tune:",
                     key="comp_usar"):
            st.session_state.fit_result = r
            st.toast("Disponível na página Ajuste.", icon=":material/check:")
    series = [k for k in ("xb", "dxb") if getattr(d, k) is not None]
    cols = st.columns(len(series))
    for col, k in zip(cols, series):
        col.altair_chart(S.grafico_curvas(d.theta, r.stages, d, k, True))
    if r.warnings:
        with st.expander(f"Avisos ({len(r.warnings)})", icon=":material/warning:"):
            for w in r.warnings:
                st.markdown(f"- `{w}`")
