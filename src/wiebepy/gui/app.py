# -*- coding: utf-8 -*-
"""
app.py — Interface gráfica do wiebepy (Streamlit).

    wiebepy --gui                       (após pip install -e ".[gui]")
    streamlit run src/wiebepy/gui/app.py

Páginas (app_pages/): dados, modelo, ajuste, comparação, exportação,
desempenho e CFD (opcional — OpenFOAM). A física, a otimização e o
paralelismo vêm do pacote wiebepy — a GUI só monta a interface.
"""
import streamlit as st

from wiebepy import __version__
from wiebepy.gui import state as S
from wiebepy.i18n import seletor as seletor_idioma, t as _, tf

st.set_page_config(page_title="wiebepy", page_icon=":material/local_fire_department:",
                   layout="wide")
S.init_state()


@st.dialog(_("Ajuda — wiebepy"), width="large")
def _ajuda(html: str) -> None:
    st.download_button(_("Baixar Help.html (abrir no navegador)"),
                       html.encode("utf-8"), file_name="Help.html",
                       mime="text/html", icon=":material/download:")
    st.iframe(html, height=650)


# url_path fixo: a URL da página não muda com o idioma
page = st.navigation(
    [
        st.Page("app_pages/dados.py", title=_("Dados"), url_path="dados",
                icon=":material/table_chart:", default=True),
        st.Page("app_pages/modelo.py", title=_("Modelo"), url_path="modelo",
                icon=":material/show_chart:"),
        st.Page("app_pages/ajuste.py", title=_("Ajuste"), url_path="ajuste",
                icon=":material/tune:"),
        st.Page("app_pages/comparacao.py", title=_("Comparação"),
                url_path="comparacao", icon=":material/leaderboard:"),
        st.Page("app_pages/exportar.py", title=_("Exportar"),
                url_path="exportar", icon=":material/download:"),
        st.Page("app_pages/desempenho.py", title=_("Desempenho"),
                url_path="desempenho", icon=":material/speed:"),
        st.Page("app_pages/cfd.py", title=_("CFD"), url_path="cfd",
                icon=":material/cloud:"),
        st.Page("app_pages/combustiveis.py", title=_("Combustíveis"),
                url_path="combustiveis", icon=":material/science:"),
    ],
    position="top",
)

with st.container(horizontal=True, vertical_alignment="center"):
    st.title(_("wiebepy — funções Wiebe de 1 a 5 estágios"), anchor=False)
    seletor_idioma()
    if st.button(_("Ajuda"), icon=":material/help:", key="botao_ajuda",
                 help=_("Abre o guia passo a passo (Help.html)")):
        html = S.help_html()
        if html is None:
            st.warning(_("Help.html não encontrado (ele fica na raiz "
                         "do repositório)."))
        else:
            _ajuda(html)

d = st.session_state.data
job = st.session_state.job
with st.container(horizontal=True):
    st.caption(tf("Versão {v}", v=__version__))
    pd_ = st.session_state.pdata
    if st.session_state.mode == "pressure":
        st.caption(tf("Modo pressão · **{nome}** ({n} pontos)",
                      nome=st.session_state.data_name, n=pd_.n)
                   if pd_ is not None
                   else _("Modo pressão · nenhuma curva carregada"))
    else:
        st.caption(tf("Dados: **{nome}** ({n} pontos)",
                      nome=st.session_state.data_name, n=d.n)
                   if d is not None else _("Dados: nenhum carregado"))
    if job is not None and not job["done"]:
        st.caption(tf(":orange[Tarefa em andamento: {tipo}]", tipo=_(job["tipo"])))

page.run()
