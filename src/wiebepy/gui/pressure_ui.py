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
from ..i18n import t as _, tf

G = math.pi / 180.0
EXEMPLO = "ensaio_P_exp_carga3_45"


def _exemplo_path():
    p = Path(__file__).resolve().parents[3] / "examples" / "data" / f"{EXEMPLO}.txt"
    return p if p.exists() else None


# =============================================================================
# Dados
# =============================================================================
SEPARADORES = {"auto": None, "espaços/tab": r"\s+", ",": ",", ";": ";",
               "tab": "\t"}


def _ler_tabela(conteudo: bytes, sep: str, cabecalho: str) -> pd.DataFrame:
    """Lê θ, P (e outras colunas) como o Double Wiebe: separador e cabeçalho
    configuráveis; linhas iniciadas por # são comentários."""
    texto = conteudo.decode("utf-8-sig", errors="replace")
    linhas = [l for l in texto.splitlines()
              if l.strip() and not l.lstrip().startswith("#")]
    if not linhas:
        raise ValueError(_("arquivo vazio"))
    if cabecalho == "auto":
        primeira = linhas[0].replace(",", " ").replace(";", " ").split()
        try:
            [float(v) for v in primeira]
            tem = False
        except ValueError:
            tem = True
    else:
        tem = cabecalho == "sim"
    sep_real = SEPARADORES[sep]
    if sep_real is None:                      # auto: vírgula, ; , tab ou espaços
        amostra = linhas[min(1, len(linhas) - 1)]
        sep_real = next((c for c in (";", "\t", ",") if c in amostra), r"\s+")
    df = pd.read_csv(io.StringIO("\n".join(linhas)), sep=sep_real,
                     engine="python", header=0 if tem else None)
    if not tem:
        df.columns = [tf("coluna {i}", i=i) for i in range(df.shape[1])]
    if df.shape[1] < 2:
        raise ValueError(_("são necessárias ao menos 2 colunas (ângulo e "
                           "pressão); confira o separador"))
    return df


def dados() -> None:
    st.subheader(_("Pressão × ângulo (ensaio)"), anchor=False)
    st.caption(_("Mesma entrada do Single/Double Wiebe: arquivo .txt/.csv/.tsv "
               "com o ângulo do virabrequim (θ = 0 no PMS de combustão) e a "
               "pressão do cilindro. Convertido internamente para rad e kPa."))
    c1, c2, c3 = st.columns([2, 1, 1])
    arq = c1.file_uploader(_("Arquivo de pressão"),
                           type=["txt", "csv", "tsv", "dat"], key="p_upl")
    sep = c2.selectbox(_("Separador"), list(SEPARADORES), key="p_sep",
                       format_func=_)
    cab = c3.selectbox(_("Cabeçalho"), ["auto", "sim", "não"], key="p_cab",
                       format_func=_)
    c4, c5, c6, c7 = st.columns(4)
    ang = c4.selectbox(_("Unidade do ângulo"), ["radianos", "graus"],
                       key="p_ang", format_func=_)
    pun = c5.selectbox(_("Unidade da pressão"), ["bar", "kPa", "Pa", "MPa"],
                       key="p_un")
    tmin = c6.number_input(_("θ mín [rad]"), value=-2.0, key="p_tmin")
    tmax = c7.number_input(_("θ máx [rad]"), value=2.0, key="p_tmax")
    # rotação e massa de combustível MUDAM com a carga do ensaio: ficam
    # aqui, junto do arquivo, e não escondidas no editor do motor
    e_atual = st.session_state.engine
    c8, c9 = st.columns(2)
    c8.number_input(_("Rotação [rpm]"), value=float(e_atual.rpm),
                    min_value=0.0, step=1.0, format="%.2f", key="e_rpm",
                    help=_("Rotação DESTE ensaio. O padrão é o da carga "
                         "45% (3396,20 rpm)."))
    c9.number_input(_("Massa de combustível [kg/ciclo]"),
                    value=float(e_atual.m_fuel), min_value=0.0,
                    step=1e-7, format="%.6e", key="e_mf",
                    help=_("Massa injetada por ciclo NESTE ensaio; entra "
                         "no modelo só por Q_total = m_comb·PCI. O padrão "
                         "é o da carga 45%."))
    st.caption(_("Rotação e massa de combustível mudam com a carga — "
               "troque-as ao carregar um ensaio de outra carga. O resto "
               "do motor fica em “Motor (geometria e combustível)”."))
    with st.container(horizontal=True, vertical_alignment="center"):
        exemplo = st.button(_("Carregar dados de exemplo"), key="p_exemplo",
                            icon=":material/science:",
                            disabled=_exemplo_path() is None,
                            help=_("Ensaio real P_exp-Carga-3_45% (θ em rad, P "
                                 "em bar), o mesmo do Single/Double Wiebe."))
        st.caption(_("Sem arquivo? Use o ensaio de exemplo."))

    fonte = None
    if exemplo:
        fonte = (_exemplo_path().name, _exemplo_path().read_bytes(),
                 "radianos", "bar")
    elif arq is not None:
        fonte = (arq.name, arq.getvalue(), ang, pun)

    if fonte is not None:
        nome, conteudo, u_ang, u_p = fonte
        try:
            df = _ler_tabela(conteudo, "auto" if exemplo else sep,
                             "auto" if exemplo else cab)
            n_cols = df.shape[1]
            if exemplo:
                col_a, col_p = 0, 1
            else:
                ca, cp = st.columns(2)
                col_a = ca.number_input(_("Coluna do ângulo (0 = primeira)"), 0,
                                        n_cols - 1, 0, key="p_col_a")
                col_p = cp.number_input(_("Coluna da pressão"), 0, n_cols - 1,
                                        min(1, n_cols - 1), key="p_col_p")
            bruto = df.iloc[:, [int(col_a), int(col_p)]].apply(
                pd.to_numeric, errors="coerce")
            validos = bruto.dropna()
            th = validos.iloc[:, 0].to_numpy(float)
            P = validos.iloc[:, 1].to_numpy(float)
            fator = 1.0 if u_ang == "radianos" else G
            dentro = (th * fator >= tmin) & (th * fator <= tmax)
            d = pressure_from_arrays(th, P, "rad" if u_ang == "radianos"
                                     else "deg", u_p, tmin, tmax, nome)
        except (ValueError, IndexError, KeyError) as e:
            st.error(tf("Erro nos dados: {erro}", erro=e))
        else:
            anterior = st.session_state.pdata
            nova = (anterior is None or nome != st.session_state.data_name
                    or d.n != anterior.n or not np.allclose(d.P, anterior.P))
            st.session_state.pdata = d
            # série SEM o corte θ mín/máx: o CFD tira dela o P inicial
            # (ex. -120°, fora de ±2 rad) e grava a cópia do ensaio no caso
            st.session_state.pdata_full = pressure_from_arrays(
                th, P, "rad" if u_ang == "radianos" else "deg", u_p,
                None, None, nome)
            st.session_state.mode = "pressure"
            st.session_state.data_name = nome
            st.session_state.p_resumo = {
                "descartadas": int(len(bruto) - len(validos)),
                "fora": int((~dentro).sum()), "preview": df.head(15)}
            if nova:
                st.session_state.pmodel = None
                st.session_state.pfit_result = None
                st.session_state.pcompare_result = None
            if exemplo:
                st.success(tf("Dados de exemplo carregados: {nome} "
                              "({n} observações).", nome=nome, n=d.n))

    motor()
    d = st.session_state.pdata
    if d is None:
        st.info(_("Envie um arquivo de pressão ou clique em **Carregar dados de "
                "exemplo**."), icon=":material/info:")
        return
    res = st.session_state.get("p_resumo") or {}
    st.info(tf("Dados ativos: **{nome}** — {n} observações.",
               nome=st.session_state.data_name, n=d.n))
    with st.container(horizontal=True):
        st.metric(_("Observações"), d.n, border=True)
        st.metric(_("Descartadas (inválidas)"), res.get("descartadas", 0),
                  border=True)
        st.metric(_("Fora do intervalo"), res.get("fora", 0), border=True)
        st.metric(_("P no IVC"), f"{d.P[0]:.1f} kPa", border=True)
        st.metric(_("P máx"), f"{d.P.max():.0f} kPa @ "
                           f"{math.degrees(d.theta[np.argmax(d.P)]):.1f}°",
                  border=True)
    for w in d.warnings:
        st.warning(w, icon=":material/warning:")
    if d.P[0] < 5.0:
        st.warning(tf("P no IVC = {p:.3g} kPa — muito baixa. Confira a "
                      "**Unidade da pressão**.", p=d.P[0]))
    elif d.P[0] > 20000.0:
        st.warning(tf("P no IVC = {p:.3g} kPa — muito alta. Confira a "
                      "**Unidade da pressão**.", p=d.P[0]))
    # campos SEM colchete: o parser de campos do Vega trata "[...]" como
    # acesso aninhado e o gráfico sai em branco (NaN); unidades vão no title
    df = pd.DataFrame({"θ": d.theta, "P": d.P})
    st.altair_chart(alt.Chart(df).mark_line(
        point=alt.OverlayMarkDef(size=12)).encode(
        x=alt.X("θ:Q", title="θ [rad]"), y=alt.Y("P:Q", title="P [kPa]"),
        tooltip=[alt.Tooltip("θ:Q", format=".4f", title="θ [rad]"),
                 alt.Tooltip("P:Q", format=".1f", title="P [kPa]")]
    ).properties(title=_("Prévia: pressão × ângulo (após conversão e "
                         "filtro)"), height=360).interactive())
    if res.get("preview") is not None:
        with st.expander(_("Prévia do arquivo (15 primeiras linhas)")):
            st.dataframe(res["preview"])


def motor() -> EngineConfig:
    """Editor dos dados do motor (padrões = motor do ensaio do Double Wiebe)."""
    e = st.session_state.engine
    with st.expander(_("Motor (geometria e combustível)")):
        with st.container(horizontal=True):
            bore = st.number_input(_("Diâmetro [mm]"), value=e.bore * 1e3,
                                   key="e_bore")
            stroke = st.number_input(_("Curso [mm]"), value=e.stroke * 1e3,
                                     key="e_stroke")
            rod = st.number_input(_("Biela [mm]"), value=e.rod_length * 1e3,
                                  key="e_rod")
            rc = st.number_input(_("Rc (inicial/fixo)"), value=e.Rc,
                                 key="e_rc")
        with st.container(horizontal=True):
            lhv = st.number_input(_("PCI [kJ/kg]"), value=e.LHV,
                                  key="e_lhv")
            kap = st.number_input("κ", value=e.kappa, format="%.3f",
                                  key="e_k")
            t1 = st.number_input(_("T inicial [K]"), value=e.T1, key="e_t1")
        with st.container(horizontal=True):
            tw = st.number_input(_("T parede [K]"), value=e.Tw, key="e_tw")
            ht = st.toggle(_("Perda de calor (Hohenberg)"),
                           value=e.heat_transfer, key="e_ht")
        st.caption(_("Rotação e massa de combustível ficam acima, junto "
                   "do arquivo: são o que muda de uma carga para outra."))
    # os dois campos da carga sao desenhados junto do arquivo; se a pagina
    # atual nao os desenhou, vale o que ja esta no motor da sessao
    rpm = float(st.session_state.get("e_rpm", e.rpm))
    mf = float(st.session_state.get("e_mf", e.m_fuel))
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
    n_med, n_sim = _("medida"), _("simulada")
    df = pd.concat([
        pd.DataFrame({"θ": np.degrees(d.theta), "P": d.P, "curva": n_med}),
        pd.DataFrame({"θ": np.degrees(d.theta), "P": P_sim,
                      "curva": n_sim})])
    return alt.Chart(df).mark_line().encode(
        x=alt.X("θ:Q", title="θ [°]"), y=alt.Y("P:Q", title="P [kPa]"),
        color=alt.Color("curva:N", title=None,
                        scale=alt.Scale(domain=[n_med, n_sim],
                                        range=["#8a93a3", "#d62728"])),
        strokeDash=alt.condition(alt.datum.curva == n_med, alt.value([1, 0]),
                                 alt.value([6, 3]))
    ).properties(title=_("Pressão: medida × simulada"),
                 height=340).interactive()


def grafico_pv(d, P_sim, Rc: float, engine=None, chave: str = "pv"):
    """Diagrama P–V: modelo (linha, na ordem de θ) × experimental (pontos),
    volume pela geometria do motor com o Rc do modelo."""
    from ..pressure.engine import volume
    e = engine or st.session_state.engine
    V = volume(d.theta, Rc, e)[0] * 1e6                     # cm³
    log = st.toggle(_("Escala log-log (P–V)"), value=False, key=f"{chave}_log",
                    help=_("Em log-log, compressão e expansão politrópicas "
                         "aparecem como retas (inclinação ≈ −n)."))
    esc = alt.Scale(type="log") if log else alt.Scale(zero=False)
    df_m = pd.DataFrame({"V": V, "P": P_sim, "ordem": np.arange(V.size),
                         "θ": np.degrees(d.theta)})
    df_e = pd.DataFrame({"V": V, "P": d.P, "θ": np.degrees(d.theta)})
    linha = alt.Chart(df_m).mark_line(color="#d62728", strokeWidth=1.8).encode(
        x=alt.X("V:Q", title=_("Volume [cm³]"), scale=esc),
        y=alt.Y("P:Q", title="P [kPa]", scale=esc), order="ordem:Q",
        tooltip=[alt.Tooltip("θ:Q", format=".1f", title="θ [°]"),
                 alt.Tooltip("V:Q", format=".2f"),
                 alt.Tooltip("P:Q", format=".1f", title=_("P modelo"))])
    pontos = alt.Chart(df_e).mark_point(shape="cross", size=28, color="#1d2330",
                                        opacity=0.55).encode(
        x="V:Q", y="P:Q",
        tooltip=[alt.Tooltip("θ:Q", format=".1f", title="θ [°]"),
                 alt.Tooltip("V:Q", format=".2f"),
                 alt.Tooltip("P:Q", format=".1f", title=_("P medida"))])
    return (pontos + linha).properties(
        title=_("Diagrama P–V: modelo (linha) × experimental (+)"),
        height=380).interactive()


def grafico_residuo(d, P_sim):
    df = pd.DataFrame({"θ": np.degrees(d.theta), "resíduo": P_sim - d.P})
    return (alt.Chart(df).mark_line().encode(
        x=alt.X("θ:Q", title="θ [°]"),
        y=alt.Y("resíduo:Q", title=_("P sim − P med [kPa]")))
        + alt.Chart(pd.DataFrame({"y": [0]})).mark_rule().encode(y="y:Q")
    ).properties(title=_("Resíduo de pressão"), height=260).interactive()


def _graus(stages):
    return [Stage(s.beta, math.degrees(s.theta0), math.degrees(s.duration), s.m, s.a)
            for s in as_stages(stages)]


def _linhas(df, titulo, titulo_y, cores=None, altura=300):
    enc = {"x": alt.X("θ:Q", title="θ [°]"),
           "y": alt.Y("valor:Q", title=titulo_y),
           "tooltip": [alt.Tooltip("curva:N", title=_("curva")),
                       alt.Tooltip("θ:Q", format=".1f"),
                       alt.Tooltip("valor:Q", format=".4g",
                                   title=_("valor"))]}
    if df["curva"].nunique() > 1:
        dom = list(dict.fromkeys(df["curva"]))
        enc["color"] = alt.Color("curva:N", title=None,
                                 scale=alt.Scale(domain=dom, range=cores)
                                 if cores else alt.Undefined)
    return alt.Chart(df).mark_line().encode(**enc).properties(
        title=titulo, height=altura).interactive()


def painel_termico(d, stages_rad, Rc, engine, Tg, Qw) -> None:
    """Mesmos gráficos do Single/Double Wiebe: fração queimada, taxa de
    liberação de calor por estágio [kJ/rad], calor liberado acumulado,
    temperatura do gás, calor perdido às paredes e volume."""
    from ..core.core import stage_contributions
    from ..pressure.engine import volume
    st_ = as_stages(stages_rad)
    N = len(st_)
    Qt = engine.Q_total
    th = np.linspace(d.theta[0], d.theta[-1], 1500)
    thd = np.degrees(th)
    cx, cd = stage_contributions(th, st_)
    cores = S.CORES[:N] + ["#1d2330"]
    nomes = [tf("estágio {j}", j=j + 1) for j in range(N)]

    xb = pd.concat([pd.DataFrame({"θ": thd, "valor": cx[j], "curva": nomes[j]})
                    for j in range(N)] + [pd.DataFrame(
                        {"θ": thd, "valor": cx.sum(axis=0),
                         "curva": _("total")})])
    hrr = pd.concat([pd.DataFrame({"θ": thd, "valor": Qt * cd[j],
                                   "curva": f"dQ{j + 1}/dθ"}) for j in range(N)]
                    + [pd.DataFrame({"θ": thd, "valor": Qt * cd.sum(axis=0),
                                     "curva": "dQ/dθ total"})])
    qc = pd.concat([pd.DataFrame({"θ": thd, "valor": Qt * cx[j],
                                  "curva": nomes[j]}) for j in range(N)]
                   + [pd.DataFrame({"θ": thd, "valor": Qt * cx.sum(axis=0),
                                    "curva": _("total")})])
    g1, g2 = st.columns(2)
    g1.altair_chart(_linhas(xb, _("Fração de massa queimada"), "x_b [-]",
                            cores))
    g2.altair_chart(_linhas(hrr, _("Taxa de liberação de calor por estágio "
                                   "e total"), "dQ/dθ [kJ/rad]", cores))
    tde = np.degrees(d.theta)
    g3, g4 = st.columns(2)
    if Tg is not None and np.all(np.isfinite(Tg)):
        g3.altair_chart(_linhas(pd.DataFrame({"θ": tde, "valor": Tg,
                                              "curva": _("T_gás")}),
                                _("Temperatura do gás"), "T [K]"))
    if Qw is not None and np.all(np.isfinite(Qw)):
        g4.altair_chart(_linhas(pd.DataFrame({"θ": tde, "valor": Qw,
                                              "curva": _("Q_parede")}),
                                _("Calor perdido para as paredes "
                                  "(Hohenberg)"),
                                _("calor perdido acumulado [J]")))
    g5, g6 = st.columns(2)
    g5.altair_chart(_linhas(qc, tf("Calor liberado acumulado "
                                   "(Q_total = {q:.4f} kJ)", q=Qt),
                            "Q [kJ]", cores))
    V = volume(d.theta, Rc, engine)[0] * 1e6
    g6.altair_chart(_linhas(pd.DataFrame({"θ": tde, "valor": V,
                                          "curva": "V(θ)"}),
                            tf("Volume do cilindro (Rc = {rc:.3f})", rc=Rc),
                            _("V [cm³]")))


def tabela(Rc, stages_rad):
    linhas = [{_("estágio"): j, "β": s.beta,
               _("θ0 [°]"): math.degrees(s.theta0),
               _("Δθ [°]"): math.degrees(s.duration), "m": s.m, "a": s.a}
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
    n = st.segmented_control(_("Número de estágios"), list(range(1, MAX_STAGES + 1)),
                             key="pmodelo_n", format_func=lambda k: f"{k}-Wiebe")
    n = n or n_padrao
    if atual is None or len(atual["stages"]) != n:
        padrao = [Stage(1 / n, (-10 + 12 * j) * G, (20 + 15 * j) * G,
                        2.0 if j == 0 else 1.0, 6.9078) for j in range(n)]
        atual = {"Rc": e.Rc, "stages": [s.to_dict() for s in padrao]}
        st.session_state.pmodel = atual
    with st.container(border=True):
        rc = st.number_input(_("Rc"), value=float(atual["Rc"]), format="%.4f",
                             key=f"pm_rc_{n}")
        tab = pd.DataFrame([{"beta": s.beta, "theta0": math.degrees(s.theta0),
                             "duration": math.degrees(s.duration), "m": s.m,
                             "a": s.a} for s in as_stages(atual["stages"])])
        ed = st.data_editor(tab, key=f"peditor_{n}", num_rows="fixed",
                            column_config={
                                "beta": st.column_config.NumberColumn("β", min_value=0.0, max_value=1.0, format="%.4f"),
                                "theta0": st.column_config.NumberColumn(_("θ0 [°]"), format="%.3f"),
                                "duration": st.column_config.NumberColumn(_("Δθ [°]"), min_value=0.0, format="%.3f"),
                                "m": st.column_config.NumberColumn("m", min_value=0.0, format="%.4f"),
                                "a": st.column_config.NumberColumn("a", min_value=0.0, format="%.4f")})
        stages = [Stage(float(r.beta), float(r.theta0) * G, float(r.duration) * G,
                        float(r.m), float(r.a)) for r in ed.itertuples()]
        with st.container(horizontal=True):
            if st.button(_("Normalizar β"), icon=":material/balance:"):
                soma = sum(s.beta for s in stages) or 1.0
                st.session_state.pmodel = {"Rc": rc, "stages": [
                    Stage(s.beta / soma, s.theta0, s.duration, s.m, s.a).to_dict()
                    for s in stages]}
                st.session_state.pop(f"peditor_{n}", None)
                st.rerun()
            fit = st.session_state.pfit_result
            if st.button(_("Usar o último ajuste"), icon=":material/history:",
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
        st.info(_("Carregue uma curva de pressão (página Dados) para simular."))
    else:
        try:
            P_sim, Tg_m, Qw_m = simulate(d.theta, float(d.P[0]), stages, e, rc)
        except ODEFailure as ex:
            st.error(tf("A simulação falhou com estes parâmetros: {erro}",
                        erro=ex))
        else:
            m = pressure_metrics(d.P, P_sim, 4 * n)
            with st.container(horizontal=True):
                st.metric(_("RMSE [kPa]"), f"{m['rmse']:.3f}", border=True)
                st.metric(_("R²"), f"{m['r2']:.6f}", border=True)
                st.metric(_("P máx sim/med [kPa]"),
                          f"{m['P_max_sim_kPa']:.0f} / {m['P_max_exp_kPa']:.0f}",
                          border=True)
            st.altair_chart(grafico_pressao(d, P_sim))
            st.altair_chart(grafico_pv(d, P_sim, rc, e, "pv_modelo"))
            painel_termico(d, stages, rc, e, Tg_m, Qw_m)


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
            _("Número de estágios"), range(1, MAX_STAGES + 1), index=1,
            format_func=lambda k: f"{k}-Wiebe", key=f"{chave}_n")
        runs = st.number_input(_("Runs por N") if comparacao else _("Runs"),
                               1, 50, 3, key=f"{chave}_runs")
        fit_rc = st.toggle(_("Ajustar Rc"), value=True, key=f"{chave}_rc",
                           help=_("Como no Double Wiebe; desligado, usa "
                                  "o Rc do motor."))
    with st.expander(_("Opções avançadas")):
        with st.container(horizontal=True):
            part = st.number_input(_("Partículas"), 4, 2000, 60, key=f"{chave}_p")
            it = st.number_input(_("Iterações"), 1, 20000, 400, key=f"{chave}_it")
            seed = st.number_input(_("Semente"), 0, 10**9, 42, key=f"{chave}_seed")
            sub = st.number_input(_("Sub-passos RK4"), 1, 32, 4, key=f"{chave}_sub")
        with st.container(horizontal=True):
            backend = st.selectbox(_("Backend"), backends, key=f"{chave}_be",
                                   help=_("numba (CPU) é o mais rápido na maioria "
                                        "dos casos; cupy usa a GPU"))
            prec = st.selectbox(_("Precisão"), ["float64", "float32"],
                                key=f"{chave}_pr")
            rc_lo = st.number_input(_("Rc mín"), value=14.0, key=f"{chave}_rclo")
            rc_hi = st.number_input(_("Rc máx"), value=20.0, key=f"{chave}_rchi")
        with st.container(horizontal=True):
            d_lo = st.number_input(_("Δθ mín [°]"), value=2.0, key=f"{chave}_dlo")
            d_hi = st.number_input(_("Δθ máx [°]"), value=90.0, key=f"{chave}_dhi")
            t_lo = st.number_input(_("θ0₁ mín [°]"), value=-30.0, key=f"{chave}_tlo")
            t_hi = st.number_input(_("θ0₁ máx [°]"), value=10.0, key=f"{chave}_thi")
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
        st.info(_("Carregue uma curva de pressão na página **Dados**."))
        return
    job = S.job_ativo()
    ocupado = job is not None and not job["done"]
    with st.form("form_pajuste"):
        s = _settings_form("pa")
        ok = st.form_submit_button(_("Iniciar ajuste"), type="primary",
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
    st.subheader(tf("Resultado — {n}-Wiebe (pressão)",
                    n=r.settings.n_stages), anchor=False)
    if not r.metrics:
        st.error(_("A referência solve_ivp falhou: resultado inválido."))
        return
    m = r.metrics
    with st.container(horizontal=True):
        st.metric(_("RMSE [kPa]"), f"{m['rmse']:.3f}", border=True)
        st.metric(_("R²"), f"{m['r2']:.6f}", border=True)
        st.metric(_("Rc"), f"{r.Rc:.4f}", border=True)
        st.metric(_("P máx sim/med [kPa]"),
                  f"{m['P_max_sim_kPa']:.0f} / {m['P_max_exp_kPa']:.0f}", border=True)
        st.metric(_("Tempo"), f"{r.elapsed_s:.1f} s", border=True)
    st.caption(tf("RMSE da referência solve_ivp (DOP853). Backend da "
                  "busca: {backend}. Runs: ", backend=r.backend)
               + ", ".join(f"{x.rmse:.3f}" for x in r.runs))
    df, _sb = tabela(r.Rc, r.stages)
    st.dataframe(df, hide_index=True, column_config={
        c: st.column_config.NumberColumn(format="%.5g") for c in df.columns[1:]})
    with st.container(horizontal=True):
        if st.button(_("Aplicar ao modelo"), icon=":material/check:",
                     key="pa_aplicar"):
            aplicar(r.Rc, r.stages)
            st.toast(_("Parâmetros aplicados à página Modelo."))
        botao_relatorio(r, d, None, "pa_rel")
    if r.warnings:
        with st.expander(tf("Avisos ({n})", n=len(r.warnings)),
                         icon=":material/warning:"):
            for w in r.warnings:
                st.markdown(f"- `{w}`")
    st.altair_chart(grafico_pressao(d, r.P_sim))
    g0, g00 = st.columns(2)
    with g0:
        st.altair_chart(grafico_pv(d, r.P_sim, r.Rc, r.settings.engine,
                                   "pv_ajuste"))
    g00.altair_chart(grafico_residuo(d, r.P_sim))
    painel_termico(d, r.stages, r.Rc, r.settings.engine, r.Tg, r.Q_wall)


def botao_relatorio(r, d, comp, chave: str) -> None:
    """Gera (sob demanda) e oferece o relatório HTML completo."""
    from ..pressure.html_report import report_html
    alvo = f"_rel_{chave}"
    if st.button(_("Gerar relatório HTML"), icon=":material/description:",
                 key=f"{chave}_gerar"):
        with st.spinner(_("Gerando relatório (gráficos incluídos)…")):
            st.session_state[alvo] = report_html(r, d, comp).encode("utf-8")
    if st.session_state.get(alvo):
        st.download_button(_("Baixar relatório HTML"), st.session_state[alvo],
                           file_name=f"relatorio_pressao_{r.settings.n_stages}"
                                     f"wiebe.html", mime="text/html",
                           icon=":material/download:", key=f"{chave}_baixar")


def painel(tipo: str, destino: str) -> None:
    @st.fragment(run_every=0.5)
    def _painel():
        job = S.job_ativo(tipo)
        if job is None:
            return
        if job["done"]:
            if job["error"]:
                st.error(tf("Erro: {erro}", erro=job["error"]))
            elif job["result"] is not None:
                st.session_state[destino] = job["result"]
            st.session_state.job = None
            st.rerun()
        with st.container(border=True):
            txt = (tf("{etapa} · iteração {it} · melhor {best:.4f} kPa "
                      "(RK4)", etapa=job["etapa"], it=job["iter"],
                      best=job["best"]) if job["best"] is not None
                   else _("preparando (compilação do kernel na 1ª vez)…"))
            st.progress(min(1.0, job.get("frac", 0.0)), text=txt)
            with st.container(horizontal=True, vertical_alignment="center"):
                st.caption(tf("Decorrido: {s:.0f} s",
                              s=time.time() - job["t0"]))
                if st.button(_("Cancelar"), icon=":material/stop:",
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
        st.info(_("Carregue uma curva de pressão na página **Dados**."))
        return
    job = S.job_ativo()
    ocupado = job is not None and not job["done"]
    with st.form("form_pcomp"):
        ns = st.pills(_("Números de estágios"), [1, 2, 3, 4, 5],
                      selection_mode="multi", default=[1, 2, 3],
                      key="pc_ns", format_func=lambda k: f"{k}-Wiebe")
        folds = st.number_input(_("Folds da validação cruzada"), 0, 20, 5,
                                key="pc_folds")
        s = _settings_form("pc", comparacao=True)
        ok = st.form_submit_button(_("Comparar"), type="primary",
                                   icon=":material/play_arrow:", disabled=ocupado)
    if ok:
        if not ns or len(ns) < 2:
            st.error(_("Escolha ao menos dois números de estágios."))
        else:
            lista = sorted(ns)

            def tarefa(job, d=d, s=s, lista=lista, folds=int(folds)):
                def prog(fase, k, it, best):
                    job.update(
                        etapa=(tf("ajuste {k}-Wiebe", k=k) if fase == "fit"
                               else tf("validação cruzada, fold {k}",
                                       k=k + 1)),
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
        st.warning(_("Comparação cancelada: resultados parciais."))
    st.success(tf("Modelo recomendado: **{n}-Wiebe** — {motivo}.",
                  n=res["recommended"], motivo=res["reason"]),
               icon=":material/recommend:")
    tab = pd.DataFrame(res["table"])
    cols = {"n_stages": "N", "k": "k", "rmse": "RMSE [kPa]",
            "cv_rmse": "CV RMSE [kPa]", "r2": "R²", "delta_aic": "ΔAIC",
            "delta_bic": "ΔBIC", "durbin_watson": "Durbin-Watson",
            "n_warnings": _("avisos"), "time_s": _("tempo [s]")}
    st.dataframe(tab[list(cols)].rename(columns=cols), hide_index=True,
                 column_config={c: st.column_config.NumberColumn(format="%.5g")
                                for c in list(cols.values())[2:]})
    e1, e2 = S.grafico_comparacao(res["table"])
    g1, g2 = st.columns(2)
    g1.altair_chart(e1)
    g2.altair_chart(e2)
    esc = st.segmented_control(_("Detalhe"), sorted(res["results"]),
                               default=res["recommended"], key="pc_det",
                               format_func=lambda k: f"{k}-Wiebe")
    if esc:
        r = res["results"][esc]
        df, _sb = tabela(r.Rc, r.stages)
        st.caption(f"Rc = {r.Rc:.4f}")
        st.dataframe(df, hide_index=True)
        with st.container(horizontal=True):
            if st.button(_("Aplicar ao modelo"), key="pc_aplicar",
                         icon=":material/check:"):
                aplicar(r.Rc, r.stages)
                st.toast(_("Parâmetros aplicados à página Modelo."))
            if st.button(_("Usar como resultado de ajuste"), key="pc_usar",
                         icon=":material/tune:"):
                st.session_state.pfit_result = r
                st.toast(_("Disponível na página Ajuste."))
        st.altair_chart(grafico_pressao(d, r.P_sim))
        st.altair_chart(grafico_pv(d, r.P_sim, r.Rc, r.settings.engine,
                                   "pv_comp"))
        painel_termico(d, r.stages, r.Rc, r.settings.engine, r.Tg, r.Q_wall)


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
        st.info(_("Faça um ajuste ou uma comparação de pressão para exportar."))
        return
    alvo = r if r is not None else comp["results"][comp["recommended"]]
    df, _sb = tabela(alvo.Rc, alvo.stages)
    st.caption(f"{alvo.settings.n_stages}-Wiebe · Rc = {alvo.Rc:.4f} · "
               f"RMSE = {alvo.metrics.get('rmse', float('nan')):.3f} kPa")
    st.dataframe(df, hide_index=True)
    st.caption(_("O .zip inclui report.html (relatório completo com todas as "
               "constantes e gráficos), CSVs, results.json e plots/*.png."))
    with st.container(horizontal=True):
        preparar = st.button(_("Preparar .zip"), type="primary",
                             icon=":material/folder_zip:")
        botao_relatorio(alvo, d, comp, "exp_rel")
    if preparar:
        st.session_state.exp_pzip = zip_pressao(alvo, d, comp)
    if st.session_state.get("exp_pzip"):
        st.download_button(_("Baixar resultados_pressao.zip"),
                           st.session_state.exp_pzip,
                           file_name="wiebepy_pressao.zip",
                           mime="application/zip",
                           icon=":material/download:")
