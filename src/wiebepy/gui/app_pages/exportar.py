# -*- coding: utf-8 -*-
"""Página Exportar: os mesmos arquivos da CLI, num .zip ou individualmente."""
import json

import streamlit as st

from wiebepy.gui import state as S
from wiebepy.model import MultiStageWiebe

st.header("Exportar", anchor=False)
if st.session_state.mode == "pressure":
    from wiebepy.gui import pressure_ui
    st.caption("Modo pressão: ajuste da curva de pressão do cilindro (modelo "
               "0-D do Double Wiebe com N estágios de liberação de calor).")
    pressure_ui.exportar()
    st.stop()
d = st.session_state.data
fit = st.session_state.fit_result
comp = st.session_state.compare_result

opcoes = {"modelo": "Modelo atual (página Modelo)"}
if fit is not None:
    opcoes["ajuste"] = f"Último ajuste ({fit.settings.n_stages}-Wiebe)"
if comp is not None:
    opcoes["comparacao"] = (f"Comparação (recomendado "
                            f"{comp['recommended']}-Wiebe)")
fonte = st.segmented_control("O que exportar", list(opcoes),
                             format_func=opcoes.get, default="ajuste"
                             if fit is not None else "modelo", key="exp_fonte")
fonte = fonte or "modelo"

if fonte == "modelo":
    n = len(st.session_state.model_stages or []) or 2
    stages, fr, cp = S.estagios_modelo(n), None, None
elif fonte == "ajuste":
    stages, fr, cp = fit.stages, fit, None
else:
    r = comp["results"][comp["recommended"]]
    stages, fr, cp = r.stages, r, comp

st.dataframe(S.tabela_estagios(stages), hide_index=True)
graficos = st.toggle("Incluir gráficos PNG no .zip", value=True)

with st.container(border=True):
    st.markdown("**Pacote completo**")
    st.caption("results.csv, parameters.csv, model.json" +
               (", metrics.csv, run_statistics.csv, warnings.txt, results.json"
                if fr is not None else "") +
               (", comparison.csv" if cp is not None else "") +
               (" e plots/*.png" if graficos else ""))
    if st.button("Preparar .zip", icon=":material/folder_zip:", type="primary"):
        with st.spinner("Gerando arquivos…"):
            st.session_state.exp_zip = S.zip_resultados(stages, d, fr, cp,
                                                        graficos)
    if st.session_state.get("exp_zip"):
        st.download_button("Baixar resultados.zip", st.session_state.exp_zip,
                           file_name=f"wiebepy_{fonte}.zip",
                           mime="application/zip", icon=":material/download:")

modelo = MultiStageWiebe(stages=stages, angle_unit=st.session_state.angle_unit)
st.download_button("Baixar só o model.json", json.dumps(modelo.to_dict(), indent=2),
                   file_name="model.json", mime="application/json",
                   icon=":material/download:")
st.caption("O model.json pode ser reaberto na CLI: `wiebepy --model model.json "
           "--plot`, ou em Python: `MultiStageWiebe.load('model.json')`.")
