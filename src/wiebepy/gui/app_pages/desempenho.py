# -*- coding: utf-8 -*-
"""Página Desempenho: hardware detectado, backends e benchmark rápido."""
import altair as alt
import pandas as pd
import streamlit as st

from wiebepy.parallel.backend import available_backends
from wiebepy.parallel.hardware import detect_hardware

st.header("Desempenho", anchor=False)
h = detect_hardware()
nb, cp = h["numba"], h["cupy"]


def _gib(b):
    return "?" if not b else f"{b / 2**30:.1f} GiB"


with st.container(horizontal=True):
    st.metric("Núcleos lógicos", h["logical_cores"], border=True)
    st.metric("Núcleos físicos", h["physical_cores"] or "?", border=True)
    st.metric("RAM", _gib(h["ram_bytes"]), border=True)
    st.metric("Numba", nb["version"] if nb["available"] else "ausente",
              border=True)
    st.metric("GPU", cp["gpu_name"] if cp["available"] else "indisponível",
              border=True)
st.caption(f"{h['cpu']} · {h['platform']} · Python {h['python']}")
if not cp["available"]:
    st.caption(f"GPU: {cp.get('reason', '')}")
st.markdown("Backends disponíveis: " + ", ".join(f"`{b}`"
                                                 for b in available_backends()))
st.caption("Na interface os runs rodam em sequência (com progresso e "
           "cancelamento); o paralelismo vem do backend (Numba multithread ou "
           "GPU). Runs em processos paralelos estão disponíveis na linha de "
           "comando (--backend numpy --workers N).")

with st.container(border=True):
    st.markdown("**Benchmark rápido** — função objetivo em lote (S candidatos "
                "× n pontos, N = 3), como em cada iteração do PSO")
    workers = st.number_input("Threads/processos", 1, 256,
                              max(1, (h["logical_cores"] or 2) - 1))
    if st.button("Rodar benchmark", icon=":material/speed:", type="primary"):
        from wiebepy.benchmark import bench_objective
        with st.spinner("Medindo (inclui compilação Numba/CUDA no aquecimento)…"):
            linhas = bench_objective(3, S_list=(20, 100, 1000),
                                     n_list=(1_000, 10_000), reps=3,
                                     workers=int(workers), log=lambda *_: None,
                                     multiprocessing=False)
        st.session_state.bench = pd.DataFrame(linhas)

df = st.session_state.bench
if df is not None:
    df = df.assign(caso=df.candidates.astype(str) + " × " + df.n_points.astype(str),
                   ms=df.time_s * 1e3)
    st.altair_chart(alt.Chart(df).mark_bar().encode(
        x=alt.X("speedup_vs_numpy:Q", title="speedup vs NumPy (×)"),
        y=alt.Y("backend:N", title=None),
        color=alt.Color("backend:N", legend=None),
        row=alt.Row("caso:N", title="S × n"),
        tooltip=["backend", "caso", alt.Tooltip("ms:Q", format=".2f"),
                 alt.Tooltip("speedup_vs_numpy:Q", format=".2f")]
    ).properties(height=110))
    st.dataframe(df[["caso", "backend", "ms", "std_s", "speedup_vs_numpy",
                     "max_rel_err_objective_vs_numpy"]].rename(columns={
                         "ms": "tempo [ms]", "std_s": "desvio [s]",
                         "speedup_vs_numpy": "speedup",
                         "max_rel_err_objective_vs_numpy": "erro rel. máx"}),
                 hide_index=True)
