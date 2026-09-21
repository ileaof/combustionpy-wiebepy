# -*- coding: utf-8 -*-
"""
app.py — Interface gráfica do wiebepy (Streamlit).

    wiebepy --gui                       (após pip install -e ".[gui]")
    streamlit run src/wiebepy/gui/app.py

Páginas (app_pages/): dados, modelo, ajuste, comparação, exportação e
desempenho. A física, a otimização e o paralelismo vêm do pacote wiebepy
— a GUI só monta a interface.
"""
import streamlit as st

from wiebepy import __version__
from wiebepy.gui import state as S

st.set_page_config(page_title="wiebepy", page_icon=":material/local_fire_department:",
                   layout="wide")
S.init_state()


@st.dialog("Ajuda — wiebepy", width="large")
def _ajuda(html: str) -> None:
    st.download_button("Baixar Help.html (abrir no navegador)",
                       html.encode("utf-8"), file_name="Help.html",
                       mime="text/html", icon=":material/download:")
    st.iframe(html, height=650)


page = st.navigation(
    [
        st.Page("app_pages/dados.py", title="Dados", icon=":material/table_chart:",
                default=True),
        st.Page("app_pages/modelo.py", title="Modelo", icon=":material/show_chart:"),
        st.Page("app_pages/ajuste.py", title="Ajuste", icon=":material/tune:"),
        st.Page("app_pages/comparacao.py", title="Comparação",
                icon=":material/leaderboard:"),
        st.Page("app_pages/exportar.py", title="Exportar",
                icon=":material/download:"),
        st.Page("app_pages/desempenho.py", title="Desempenho",
                icon=":material/speed:"),
    ],
    position="top",
)

with st.container(horizontal=True, vertical_alignment="center"):
    st.title("wiebepy — funções Wiebe de 1 a 5 estágios", anchor=False)
    if st.button("Ajuda", icon=":material/help:", key="botao_ajuda",
                 help="Abre o guia passo a passo (Help.html)"):
        html = S.help_html()
        if html is None:
            st.warning("Help.html não encontrado (ele fica na raiz do repositório).")
        else:
            _ajuda(html)

d = st.session_state.data
job = st.session_state.job
with st.container(horizontal=True):
    st.caption(f"Versão {__version__}")
    st.caption(f"Dados: **{st.session_state.data_name}** ({d.n} pontos)"
               if d is not None else "Dados: nenhum carregado")
    if job is not None and not job["done"]:
        st.caption(f":orange[Tarefa em andamento: {job['tipo']}]")

page.run()
