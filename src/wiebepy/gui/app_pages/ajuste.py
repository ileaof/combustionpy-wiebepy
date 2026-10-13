# -*- coding: utf-8 -*-
"""Página Ajuste: PSO + refinamento local em segundo plano, com progresso ao
vivo, cancelamento e resultados (parâmetros, estatística dos runs, métricas,
avisos de identificabilidade e gráficos)."""
import time

import pandas as pd
import streamlit as st

from wiebepy.core.parameters import MAX_STAGES
from wiebepy.gui import state as S
from wiebepy.i18n import t as _, tf
from wiebepy.optimization.fit import FitSettings, fit
from wiebepy.parallel.backend import available_backends

st.header(_("Ajuste"), anchor=False)
if st.session_state.mode == "pressure":
    from wiebepy.gui import pressure_ui
    st.caption(_("Modo pressão: ajuste da curva de pressão do cilindro (modelo "
               "0-D do Double Wiebe com N estágios de liberação de calor)."))
    pressure_ui.ajuste()
    st.stop()
d = st.session_state.data
if d is None:
    st.info(_("Carregue dados na página **Dados** para ajustar."),
            icon=":material/info:")
    st.stop()

alvos = [a for a, ok in (("xb", d.xb is not None), ("dxb", d.dxb is not None),
                         ("both", d.xb is not None and d.dxb is not None)) if ok]
NOMES_ALVO = {"xb": "x_b", "dxb": "dx_b/dθ", "both": "x_b e dx_b/dθ"}
backends = ["auto"] + [b for b in available_backends() if b != "multiprocessing"]
job = S.job_ativo()
ocupado = job is not None and not job["done"]

with st.form("form_ajuste"):
    with st.container(horizontal=True):
        n = st.selectbox(_("Número de estágios"), range(1, MAX_STAGES + 1),
                         index=1, key="aj_n",
                         format_func=lambda k: f"{k}-Wiebe")
        alvo = st.selectbox(_("Série ajustada"), alvos, index=0, key="aj_alvo",
                            format_func=lambda k: _(NOMES_ALVO[k]))
        metrica = st.selectbox(_("Função objetivo"),
                               ["rmse", "mse", "mae", "see", "wrmse"],
                               key="aj_metrica")
        runs = st.number_input(_("Runs independentes"), 1, 100, 5, key="aj_runs",
                               help=_("Sementes seed, seed+1, …; para N ≥ 3 "
                                    "prefira 10 ou mais."))
    with st.expander(_("Opções avançadas")):
        with st.container(horizontal=True):
            particulas = st.number_input(_("Partículas"), 4, 5000, 100,
                                         key="aj_particulas")
            iteracoes = st.number_input(_("Iterações"), 1, 20000, 1000,
                                        key="aj_iteracoes")
            paciencia = st.number_input(_("Paciência"), 1, 20000, 200,
                                        key="aj_paciencia",
                                        help=_("iterações sem melhora antes de parar"))
            semente = st.number_input(_("Semente"), 0, 10**9, 42,
                                      key="aj_semente")
        with st.container(horizontal=True):
            beta_mode = st.selectbox(_("Parametrização de β"),
                                     ["stick", "softmax", "explicit"],
                                     key="aj_beta")
            topologia = st.selectbox(_("Topologia do PSO"), ["ring", "global"],
                                     key="aj_topologia")
            fit_a = st.toggle(_("Ajustar a_j"), value=False, key="aj_fit_a")
            polish = st.toggle(_("Refinamento local"), value=True,
                               key="aj_polish")
        with st.container(horizontal=True):
            backend = st.selectbox(_("Backend"), backends, key="aj_backend",
                                   help=_("auto mede os disponíveis com o seu "
                                        "problema e usa o mais rápido"))
            workers = st.number_input(_("Threads (numba)"), 0, 256, 0,
                                      key="aj_workers",
                                      help=_("0 = automático"))
            precisao = st.selectbox(_("Precisão"), ["float64", "float32"],
                                    key="aj_precisao",
                                    help=_("float32 acelera a GPU, mas a busca "
                                         "fica menos precisa"))
    iniciar = st.form_submit_button(_("Iniciar ajuste"), type="primary",
                                    icon=":material/play_arrow:", disabled=ocupado)

if iniciar:
    s = FitSettings(n_stages=int(n), beta_mode=beta_mode, fit_a=fit_a,
                    metric=metrica, fit_target=alvo, particles=int(particulas),
                    iterations=int(iteracoes), patience=int(paciencia),
                    topology=topologia, runs=int(runs), seed=int(semente),
                    backend=backend, workers=int(workers) or None,
                    precision=precisao, polish=polish, parallel_runs="no")

    def tarefa(job, dados=d, s=s):
        def progresso(run, it, melhor, x):
            job.update(etapa=f"run {run + 1}/{s.runs}", iter=it, best=melhor,
                       frac=(run + it / s.iterations) / s.runs)
            return job["cancel"]
        return fit(dados, s, progress=progresso)

    S.iniciar_job("ajuste", tarefa, int(runs))
    st.rerun()


@st.fragment(run_every=0.5)
def painel_progresso():
    job = S.job_ativo("ajuste")
    if job is None:
        return
    if job["done"]:
        if job["error"]:
            st.error(tf("Erro no ajuste: {erro}", erro=job["error"]),
                     icon=":material/error:")
        elif job["result"] is not None:
            st.session_state.fit_result = job["result"]
        st.session_state.job = None
        st.rerun()
    with st.container(border=True):
        if job["best"] is not None:
            texto = tf("{etapa} · iteração {it} · melhor {best:.4e}",
                       etapa=job["etapa"] or _("preparando (escolha do backend)…"),
                       it=job["iter"], best=job["best"])
        else:
            texto = _("preparando (escolha do backend e compilação)…")
        st.progress(min(1.0, job.get("frac", 0.0)), text=texto)
        with st.container(horizontal=True, vertical_alignment="center"):
            st.caption(tf("Decorrido: {s:.0f} s", s=time.time() - job["t0"]))
            if st.button(_("Cancelar"), icon=":material/stop:",
                         disabled=job["cancel"]):
                job["cancel"] = True
        if job["log"]:
            st.code("\n".join(job["log"][-6:]), language=None)


painel_progresso()

r = st.session_state.fit_result
if r is None:
    st.stop()

st.subheader(tf("Resultado — {n}-Wiebe", n=r.settings.n_stages), anchor=False)
if any(x.stopped_by == "cancel" for x in r.runs):
    st.warning(_("Ajuste cancelado: resultado parcial."), icon=":material/warning:")
serie = "xb" if "xb" in r.metrics else "dxb"
m = r.metrics[serie]
o = r.objective_stats
with st.container(horizontal=True):
    st.metric(tf("RMSE ({serie})", serie=_(NOMES_ALVO[serie])),
              f"{m['rmse']:.4e}", border=True)
    st.metric(_("R²"), f"{m['r2']:.6f}", border=True)
    st.metric(_("Durbin-Watson"), f"{m['durbin_watson']:.2f}", border=True,
              help=_("≈ 2: resíduo sem estrutura; ≪ 2: falta estrutura no modelo"))
    st.metric(_("Runs"), o["runs"], border=True)
    st.metric(_("Tempo"), f"{r.elapsed_s:.1f} s", border=True)
st.caption(tf("Backend: {backend}", backend=r.backend))

esq, dir_ = st.columns([3, 2])
with esq:
    st.markdown(_("**Parâmetros do melhor run**"))
    st.dataframe(S.tabela_estagios(r.stages), hide_index=True,
                 column_config={c: st.column_config.NumberColumn(format="%.5g")
                                for c in S.tabela_estagios(r.stages).columns[1:]})
with dir_:
    st.markdown(tf("**Objetivo entre runs ({metrica})**", metrica=r.spec.metric))
    st.dataframe(pd.DataFrame([{k: v for k, v in o.items() if k != "runs"}]),
                 hide_index=True,
                 column_config={c: st.column_config.NumberColumn(format="%.4e")
                                for c in ("best", "mean", "std", "median", "worst")})
with st.container(horizontal=True):
    if st.button(_("Aplicar ao modelo"), icon=":material/check:"):
        S.aplicar_ao_modelo(r.stages)
        st.session_state._modelo_n_pendente = r.settings.n_stages
        st.session_state.pop(f"editor_{r.settings.n_stages}", None)
        st.toast(_("Parâmetros aplicados à página Modelo."), icon=":material/check:")

if r.warnings:
    with st.expander(tf("Avisos de identificabilidade ({n})",
                        n=len(r.warnings)),
                     icon=":material/warning:"):
        for w in r.warnings:
            st.markdown(f"- `{w}`")
else:
    st.success(_("Nenhum aviso de identificabilidade."), icon=":material/verified:")

g1, g2 = st.columns(2)
series = [k for k in ("xb", "dxb") if getattr(d, k) is not None]
for col, k in zip((g1, g2), series):
    col.altair_chart(S.grafico_curvas(d.theta, r.stages, d, k, True))
g3, g4 = st.columns(2)
for col, k in zip((g3, g4), series):
    col.altair_chart(S.grafico_residuos(d, r.stages, k))
conv = S.grafico_convergencia(r)
if conv is not None:
    st.altair_chart(conv)

with st.expander(_("Métricas completas")):
    st.dataframe(pd.DataFrame(r.metrics).T, column_config={
        c: st.column_config.NumberColumn(format="%.5g")
        for c in pd.DataFrame(r.metrics).T.columns})
with st.expander(_("Média e desvio dos parâmetros entre runs")):
    st.dataframe(pd.DataFrame(r.param_stats).T, column_config={
        c: st.column_config.NumberColumn(format="%.5g")
        for c in ("best", "mean", "std")})
