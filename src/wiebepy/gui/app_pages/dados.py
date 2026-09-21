# -*- coding: utf-8 -*-
"""Página Dados: carregar arquivo experimental ou exemplo sintético."""
import altair as alt
import pandas as pd
import streamlit as st

from wiebepy.core.validation import DataError
from wiebepy.gui import state as S
from wiebepy.io.readers import read_data

st.header("Dados experimentais", anchor=False)
TIPOS = {"xb": "Fração queimada (x_b, dx_b/dθ)",
         "pressure": "Pressão do cilindro (ensaio)"}
tipo = st.segmented_control("Tipo de dado", list(TIPOS), format_func=TIPOS.get,
                            default=st.session_state.mode, key="tipo_dado")
tipo = tipo or st.session_state.mode
if tipo != st.session_state.mode:
    st.session_state.mode = tipo
if tipo == "pressure":
    from wiebepy.gui import pressure_ui
    pressure_ui.dados()
    st.stop()
st.caption("Arquivo .csv, .txt, .dat ou .json com θ e x_b e/ou dx_b/dθ "
           "(colunas theta, xb, dxb_dtheta; weight ou sigma opcionais). "
           "Para ajustar a curva de pressão, escolha “Pressão do cilindro”.")

with st.container(border=True):
    unidade = st.segmented_control(
        "Unidade angular dos dados", ["deg", "rad"], key="angle_unit_sel",
        default=st.session_state.angle_unit,
        format_func=lambda u: "graus" if u == "deg" else "radianos")
    fonte = st.segmented_control("Origem", ["Arquivo", "Exemplo sintético"],
                                 default="Arquivo", key="fonte_dados")
    if fonte == "Arquivo":
        arq = st.file_uploader("Arquivo de dados",
                               type=["csv", "txt", "dat", "tsv", "json"])
        carregar = st.button("Carregar arquivo", icon=":material/upload:",
                             disabled=arq is None, type="primary")
    else:
        exemplos = S.exemplos_disponiveis()
        if not exemplos:
            st.info("Exemplos não encontrados (ficam em examples/data no clone "
                    "do repositório).")
            carregar, escolhido = False, None
        else:
            escolhido = st.selectbox("Exemplo", list(exemplos),
                                     format_func=lambda k: k.replace("_", " "))
            st.caption("Dados gerados com parâmetros conhecidos e ruído "
                       "(ver examples/data/true_parameters.json).")
            carregar = st.button("Carregar exemplo", icon=":material/upload:",
                                 type="primary")

if carregar:
    u = unidade or "deg"
    try:
        dados = (S.ler_upload(arq, u) if fonte == "Arquivo"
                 else read_data(S.exemplos_disponiveis()[escolhido], u))
    except (DataError, ValueError) as e:
        st.error(f"Não foi possível ler os dados: {e}")
    else:
        st.session_state.data = dados
        st.session_state.mode = "xb"
        st.session_state.data_name = dados.source
        st.session_state.angle_unit = u
        st.session_state.model_stages = None      # refaz padrões na nova faixa
        st.rerun()

d = st.session_state.data
if d is None:
    st.info("Nenhum dado carregado. O restante da interface funciona sem dados "
            "(página Modelo), mas ajuste e comparação precisam deles.",
            icon=":material/info:")
    st.stop()

u = S.unidade()
with st.container(horizontal=True):
    st.metric("Pontos", d.n, border=True)
    st.metric(f"θ mín [{u}]", f"{d.theta.min():.3g}", border=True)
    st.metric(f"θ máx [{u}]", f"{d.theta.max():.3g}", border=True)
    st.metric("Séries", " + ".join(n for n, v in (("x_b", d.xb), ("dx_b/dθ", d.dxb))
                                   if v is not None), border=True)
    st.metric("Pesos", "sim" if d.weights is not None else "não", border=True)
for w in d.warnings:
    st.warning(w, icon=":material/warning:")

esq, dir_ = st.columns(2)
if d.xb is not None:
    df = pd.DataFrame({"θ": d.theta, "x_b": d.xb})
    esq.altair_chart(alt.Chart(df).mark_circle(size=10).encode(
        x=alt.X("θ:Q", title=f"θ [{u}]"), y="x_b:Q").properties(
        title="Fração de massa queimada", height=300).interactive())
if d.dxb is not None:
    df = pd.DataFrame({"θ": d.theta, "dxb": d.dxb})
    dir_.altair_chart(alt.Chart(df).mark_circle(size=10, color="#d62728").encode(
        x=alt.X("θ:Q", title=f"θ [{u}]"),
        y=alt.Y("dxb:Q", title=f"dx_b/dθ [1/{u}]")).properties(
        title="Taxa de queima", height=300).interactive())

with st.expander("Tabela de dados"):
    tab = {"θ": d.theta}
    if d.xb is not None:
        tab["x_b"] = d.xb
    if d.dxb is not None:
        tab["dx_b/dθ"] = d.dxb
    if d.weights is not None:
        tab["peso"] = d.weights
    st.dataframe(pd.DataFrame(tab), hide_index=True, height=300)
