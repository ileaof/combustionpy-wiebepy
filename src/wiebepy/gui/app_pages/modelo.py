# -*- coding: utf-8 -*-
"""Página Modelo: editar os estágios, avaliar x_b e dx_b/dθ e comparar com
os dados carregados."""
import json

import numpy as np
import pandas as pd
import streamlit as st

from wiebepy.core.parameters import MAX_STAGES, Stage, validate_stages
from wiebepy.gui import state as S
from wiebepy.i18n import t as _, tf
from wiebepy.io.readers import theta_grid
from wiebepy.model import MultiStageWiebe
from wiebepy.optimization.objective import fit_metrics

st.header(_("Modelo"), anchor=False)
if st.session_state.mode == "pressure":
    from wiebepy.gui import pressure_ui
    st.caption(_("Modo pressão: ajuste da curva de pressão do cilindro (modelo "
               "0-D do Double Wiebe com N estágios de liberação de calor)."))
    pressure_ui.modelo()
    st.stop()
u = S.unidade()
d = st.session_state.data

atual = len(st.session_state.model_stages or []) or 2
if "_modelo_n_pendente" in st.session_state:        # definido por um botão
    st.session_state.modelo_n = st.session_state.pop("_modelo_n_pendente")
st.session_state.setdefault("modelo_n", atual)
n = st.segmented_control(_("Número de estágios"), list(range(1, MAX_STAGES + 1)),
                         key="modelo_n", format_func=lambda k: f"{k}-Wiebe")
n = n or atual
stages = S.estagios_modelo(n)

with st.container(border=True):
    st.markdown(_("**Parâmetros dos estágios**"))
    tabela = pd.DataFrame([s.to_dict() for s in stages])
    editado = st.data_editor(
        tabela, key=f"editor_{n}", hide_index=False, num_rows="fixed",
        column_config={
            "beta": st.column_config.NumberColumn(
                "β", min_value=0.0, max_value=1.0, format="%.4f",
                help=_("fração da massa do estágio")),
            "theta0": st.column_config.NumberColumn(tf("θ0 [{u}]", u=u),
                                                    format="%.4f",
                                                    help=_("início do estágio")),
            "duration": st.column_config.NumberColumn(tf("Δθ [{u}]", u=u),
                                                      min_value=0.0,
                                                      format="%.4f",
                                                      help=_("duração (> 0)")),
            "m": st.column_config.NumberColumn("m", min_value=0.0, format="%.4f",
                                               help=_("fator de forma (> 0)")),
            "a": st.column_config.NumberColumn("a", min_value=0.0, format="%.4f",
                                               help=_("eficiência (6.908 ⇒ 99.9 %)")),
        })
    novos = [Stage(**{k: float(r[k]) for k in ("beta", "theta0", "duration",
                                              "m", "a")})
             for _i, r in editado.iterrows()]
    with st.container(horizontal=True):
        if st.button(_("Normalizar β (Σβ = 1)"), icon=":material/balance:"):
            soma = sum(s.beta for s in novos)
            if soma > 0:
                S.aplicar_ao_modelo([Stage(s.beta / soma, s.theta0, s.duration,
                                           s.m, s.a) for s in novos])
                st.session_state.pop(f"editor_{n}", None)
                st.rerun()
        fit = st.session_state.fit_result
        if st.button(_("Usar o último ajuste"), icon=":material/history:",
                     disabled=fit is None):
            S.aplicar_ao_modelo(fit.stages)
            st.session_state.pop(f"editor_{fit.settings.n_stages}", None)
            st.session_state._modelo_n_pendente = fit.settings.n_stages
            st.rerun()
        if st.button(_("Restaurar padrão"), icon=":material/restart_alt:"):
            st.session_state.model_stages = None
            st.session_state.pop(f"editor_{n}", None)
            st.rerun()

erros = validate_stages(novos)
if erros:
    for e in erros:
        st.error(e, icon=":material/error:")
    st.stop()
st.session_state.model_stages = [s.to_dict() for s in novos]

with st.expander(_("Grade angular"), expanded=d is None):
    lo, hi = S.faixa_theta()
    with st.container(horizontal=True):
        tmin = st.number_input(tf("θ mínimo [{u}]", u=u), value=lo,
                               key="grade_min")
        tmax = st.number_input(tf("θ máximo [{u}]", u=u), value=hi,
                               key="grade_max")
        passo = st.number_input(tf("Passo [{u}]", u=u),
                                value=0.1 if u == "°" else 0.002,
                                min_value=1e-6, format="%.4g", key="grade_passo")
try:
    theta = theta_grid(tmin, tmax, passo)
except ValueError as e:
    st.error(str(e))
    st.stop()
if theta.size > 200_000:
    st.warning(_("Grade muito fina para os gráficos; usando 200 000 pontos."))
    theta = np.linspace(tmin, tmax, 200_000)

contrib = st.toggle(_("Mostrar contribuição de cada estágio"), value=True,
                    key="modelo_contrib")
esq, dir_ = st.columns(2)
esq.altair_chart(S.grafico_curvas(theta, novos, d, "xb", contrib))
dir_.altair_chart(S.grafico_curvas(theta, novos, d, "dxb", contrib))

if d is not None:
    k = 4 * n - 1
    linhas = []
    for serie, y, sim in (
            ("x_b", d.xb, MultiStageWiebe(stages=novos).evaluate(d.theta)),
            ("dx_b/dθ", d.dxb, MultiStageWiebe(stages=novos).derivative(d.theta))):
        if y is not None:
            m = fit_metrics(y, sim, k, d.weights)
            linhas.append({_("série"): serie, "RMSE": m["rmse"],
                           "MAE": m["mae"], "R²": m["r2"],
                           "Durbin-Watson": m["durbin_watson"]})
    st.markdown(_("**Modelo atual × dados carregados**"))
    st.dataframe(pd.DataFrame(linhas), hide_index=True,
                 column_config={c: st.column_config.NumberColumn(format="%.4g")
                                for c in ("RMSE", "MAE", "R²", "Durbin-Watson")})

modelo = MultiStageWiebe(stages=novos, angle_unit=st.session_state.angle_unit)
st.download_button(_("Baixar model.json"), json.dumps(modelo.to_dict(), indent=2),
                   file_name="model.json", mime="application/json",
                   icon=":material/download:")
