# -*- coding: utf-8 -*-
"""
state.py — Estado da sessão, tarefas em segundo plano, gráficos e exportação
da GUI. As páginas (app_pages/) só montam a interface; a lógica vive aqui e
no pacote wiebepy.

Tarefas longas (ajuste, comparação) rodam numa thread; a thread escreve num
dict ``job`` (progresso, log, resultado) e a página o lê num fragment com
atualização periódica. Na GUI os runs são sempre sequenciais (processos
filhos não combinam com o servidor Streamlit), o que também permite
progresso por iteração e cancelamento; o paralelismo vem do backend
(Numba multithread ou GPU).
"""
from __future__ import annotations

import io
import logging
import tempfile
import threading
import time
import zipfile
from pathlib import Path
from typing import Callable, Dict, List, Optional

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

from ..core.core import multistage_wiebe, stage_contributions
from ..core.derivatives import multistage_wiebe_derivative
from ..core.parameters import A_DEFAULT, Stage, as_stages, default_stages

CORES = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#ff7f0e"]
UNIDADE = {"deg": "°", "rad": "rad"}


# =============================================================================
# Estado
# =============================================================================
def init_state() -> None:
    """Único lugar onde o estado da sessão é inicializado."""
    st.session_state.setdefault("data", None)            # FitData
    st.session_state.setdefault("data_name", "")
    st.session_state.setdefault("angle_unit", "deg")
    st.session_state.setdefault("model_stages", None)    # List[dict]
    st.session_state.setdefault("fit_result", None)      # FitResult
    st.session_state.setdefault("compare_result", None)  # dict
    st.session_state.setdefault("job", None)             # tarefa em andamento
    st.session_state.setdefault("bench", None)           # DataFrame
    # modo pressão (ajuste da curva de pressão do cilindro)
    from ..pressure.engine import EngineConfig
    st.session_state.setdefault("mode", "pressure")      # pressure | xb
    st.session_state.setdefault("pdata", None)           # PressureData
    st.session_state.setdefault("engine", EngineConfig())
    st.session_state.setdefault("pmodel", None)          # {"Rc", "stages"}
    st.session_state.setdefault("pfit_result", None)
    st.session_state.setdefault("pcompare_result", None)


def unidade() -> str:
    return UNIDADE[st.session_state.angle_unit]


def faixa_theta():
    """Faixa angular: dos dados, se houver; senão −20…100."""
    d = st.session_state.data
    if d is not None:
        return float(d.theta.min()), float(d.theta.max())
    return -20.0, 100.0


def estagios_modelo(n: int) -> List[Stage]:
    """Estágios atuais do modelo, criando padrões para N se necessário."""
    atuais = st.session_state.model_stages
    if atuais is None or len(atuais) != n:
        lo, hi = faixa_theta()
        atuais = [s.to_dict() for s in default_stages(n, lo, hi, A_DEFAULT)]
        st.session_state.model_stages = atuais
    return as_stages(atuais)


def aplicar_ao_modelo(stages) -> None:
    st.session_state.model_stages = [s.to_dict() for s in as_stages(stages)]


def tabela_estagios(stages) -> pd.DataFrame:
    u = unidade()
    return pd.DataFrame([{
        "estágio": j, "β": s.beta, f"θ0 [{u}]": s.theta0,
        f"Δθ [{u}]": s.duration, "m": s.m, "a": s.a}
        for j, s in enumerate(as_stages(stages), start=1)])


# =============================================================================
# Leitura de arquivo enviado
# =============================================================================
def ler_upload(arquivo, angle_unit: str):
    """st.file_uploader -> FitData (via arquivo temporário com a extensão)."""
    from ..io.readers import read_data
    sufixo = Path(arquivo.name).suffix.lower()
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / f"dados{sufixo}"
        p.write_bytes(arquivo.getvalue())
        dados = read_data(p, angle_unit)
    dados.source = arquivo.name
    return dados


def exemplos_disponiveis() -> Dict[str, Path]:
    """Arquivos de exemplo que acompanham o projeto (clone/instalação -e)."""
    raiz = Path(__file__).resolve().parents[3] / "examples" / "data"
    return {p.stem: p for p in sorted(raiz.glob("synthetic_*stage.csv"))}


# =============================================================================
# Tarefas em segundo plano
# =============================================================================
class _LogHandler(logging.Handler):
    """Coleta as mensagens do logger 'wiebepy' emitidas pela thread do job."""

    def __init__(self, job: Dict, thread_id: int):
        super().__init__(logging.INFO)
        self.job, self.tid = job, thread_id

    def emit(self, record):
        if record.thread == self.tid:
            self.job["log"].append(self.format(record))


def iniciar_job(tipo: str, alvo: Callable[[Dict], object], total: int) -> None:
    """Dispara ``alvo(job)`` numa thread; ``job`` é o canal de progresso."""
    job = {"tipo": tipo, "t0": time.time(), "cancel": False, "done": False,
           "result": None, "error": None, "log": [], "total": total,
           "etapa": "", "iter": 0, "best": None}

    def corpo():
        log = logging.getLogger("wiebepy")
        h = _LogHandler(job, threading.get_ident())
        h.setFormatter(logging.Formatter("%(message)s"))
        log.addHandler(h)
        nivel = log.level
        log.setLevel(logging.INFO)
        try:
            job["result"] = alvo(job)
        except Exception as e:                          # noqa: BLE001
            job["error"] = f"{type(e).__name__}: {e}"
        finally:
            log.removeHandler(h)
            log.setLevel(nivel)
            job["done"] = True

    job["thread"] = threading.Thread(target=corpo, daemon=True)
    st.session_state.job = job
    job["thread"].start()


def job_ativo(tipo: Optional[str] = None) -> Optional[Dict]:
    job = st.session_state.get("job")
    if job is None or (tipo and job["tipo"] != tipo):
        return None
    return job


# =============================================================================
# Gráficos (Altair)
# =============================================================================
def _tema(chart, titulo: str = ""):
    return chart.properties(title=titulo, height=320).interactive()


def grafico_curvas(theta, stages, dados=None, serie: str = "xb",
                   contribuicoes: bool = True):
    """x_b (ou dx_b/dθ) total, contribuições por estágio e dados."""
    u = unidade()
    st_ = as_stages(stages)
    th = np.asarray(theta, dtype=float)
    cx, cd = stage_contributions(th, st_)
    total = (multistage_wiebe(th, st_) if serie == "xb"
             else multistage_wiebe_derivative(th, st_))
    contrib = cx if serie == "xb" else cd
    linhas = [pd.DataFrame({"θ": th, "valor": total, "curva": "total"})]
    if contribuicoes and len(st_) > 1:
        for j in range(len(st_)):
            linhas.append(pd.DataFrame({"θ": th, "valor": contrib[j],
                                        "curva": f"estágio {j + 1}"}))
    df = pd.concat(linhas)
    dominio = ["total"] + [f"estágio {j + 1}" for j in range(len(st_))]
    cores = ["#1d2330"] + CORES[:len(st_)]
    eixo_y = "x_b [-]" if serie == "xb" else f"dx_b/dθ [1/{u}]"
    base = alt.Chart(df).mark_line().encode(
        x=alt.X("θ:Q", title=f"θ [{u}]"),
        y=alt.Y("valor:Q", title=eixo_y),
        color=alt.Color("curva:N", scale=alt.Scale(domain=dominio, range=cores),
                        title=None),
        strokeDash=alt.condition(alt.datum.curva == "total", alt.value([1, 0]),
                                 alt.value([5, 3])),
        tooltip=["curva:N", alt.Tooltip("θ:Q", format=".2f"),
                 alt.Tooltip("valor:Q", format=".4g")])
    camadas = [base]
    exp = None if dados is None else (dados.xb if serie == "xb" else dados.dxb)
    if exp is not None:
        pts = pd.DataFrame({"θ": dados.theta, "valor": exp})
        if len(pts) > 1500:
            pts = pts.iloc[:: int(np.ceil(len(pts) / 1500))]
        camadas.insert(0, alt.Chart(pts).mark_circle(size=12, color="#8a93a3",
                                                     opacity=0.7).encode(
            x="θ:Q", y="valor:Q",
            tooltip=[alt.Tooltip("θ:Q", format=".2f"),
                     alt.Tooltip("valor:Q", format=".4g", title="experimental")]))
    titulo = ("Fração de massa queimada" if serie == "xb" else "Taxa de queima")
    return _tema(alt.layer(*camadas), titulo)


def grafico_residuos(dados, stages, serie: str = "xb"):
    u = unidade()
    st_ = as_stages(stages)
    y = dados.xb if serie == "xb" else dados.dxb
    sim = (multistage_wiebe(dados.theta, st_) if serie == "xb"
           else multistage_wiebe_derivative(dados.theta, st_))
    df = pd.DataFrame({"θ": dados.theta, "resíduo": sim - y})
    linha = alt.Chart(df).mark_line(color=CORES[0]).encode(
        x=alt.X("θ:Q", title=f"θ [{u}]"), y=alt.Y("resíduo:Q"))
    zero = alt.Chart(pd.DataFrame({"y": [0.0]})).mark_rule(color="#1d2330").encode(y="y:Q")
    return _tema(linha + zero, f"Resíduos ({'x_b' if serie == 'xb' else 'dx_b/dθ'})")


def grafico_convergencia(fit_result):
    linhas = []
    for r in fit_result.runs:
        if not r.history:
            continue
        h = np.maximum(np.asarray(r.history, dtype=float), 1e-300)
        linhas.append(pd.DataFrame({"iteração": np.arange(h.size),
                                    "objetivo": h, "run": f"run {r.run + 1}"}))
    if not linhas:
        return None
    df = pd.concat(linhas)
    c = alt.Chart(df).mark_line().encode(
        x="iteração:Q",
        y=alt.Y("objetivo:Q", scale=alt.Scale(type="log"),
                title=f"objetivo ({fit_result.spec.metric})"),
        color=alt.Color("run:N", title=None))
    return _tema(c, "Convergência do PSO (antes do refinamento local)")


def grafico_comparacao(tabela: List[Dict]):
    df = pd.DataFrame(tabela)
    longo = pd.concat([
        pd.DataFrame({"N": df.n_stages, "RMSE": df.rmse, "série": "treino"}),
        pd.DataFrame({"N": df.n_stages, "RMSE": df.cv_rmse,
                      "série": "validação cruzada"})]).dropna()
    erro = alt.Chart(longo).mark_line(point=True).encode(
        x=alt.X("N:O", title="número de estágios"),
        y=alt.Y("RMSE:Q", scale=alt.Scale(type="log")),
        color=alt.Color("série:N", title=None))
    ic = pd.concat([
        pd.DataFrame({"N": df.n_stages, "Δ": df.delta_aic, "critério": "ΔAIC"}),
        pd.DataFrame({"N": df.n_stages, "Δ": df.delta_bic, "critério": "ΔBIC"})])
    crit = alt.Chart(ic).mark_line(point=True).encode(
        x=alt.X("N:O", title="número de estágios"), y=alt.Y("Δ:Q"),
        color=alt.Color("critério:N", title=None))
    return (_tema(erro, "Erro × complexidade"),
            _tema(crit, "ΔAIC / ΔBIC (indicativos)"))


# =============================================================================
# Exportação
# =============================================================================
def zip_resultados(stages, dados=None, fit_result=None, compare=None,
                   com_graficos: bool = True) -> bytes:
    """Mesmos arquivos da CLI, empacotados num .zip em memória."""
    from ..io import writers as W
    from ..model import MultiStageWiebe
    from ..plotting.plots import (close_all, comparison_figure, make_figures,
                                  save_figures)
    u = st.session_state.angle_unit
    st_ = as_stages(stages)
    with tempfile.TemporaryDirectory() as d:
        out = Path(d)
        if dados is not None:
            th = dados.theta
        else:
            lo, hi = faixa_theta()
            th = np.linspace(lo, hi, 1201)
        W.write_results_csv(out, th, st_, dados, u)
        W.write_parameters_csv(out, st_, fit_result.param_stats
                               if fit_result else None, u)
        MultiStageWiebe(stages=st_, angle_unit=u).save(out / "model.json")
        if fit_result is not None:
            W.write_metrics_csv(out, fit_result.metrics)
            W.write_run_statistics_csv(out, fit_result)
            W.write_warnings(out, fit_result.warnings)
            W.write_json(out, fit_result.to_dict())
        if compare is not None:
            W.write_comparison_csv(out, compare["table"])
        if com_graficos:
            grade = np.linspace(th.min(), th.max(), max(2000, th.size))
            figs = make_figures(grade, st_, dados, fit_result, u, False)
            if compare is not None:
                figs["comparison"] = comparison_figure(compare["table"], False)
            save_figures(figs, out / "plots")
            close_all(figs)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for p in sorted(out.rglob("*")):
                if p.is_file():
                    z.write(p, p.relative_to(out).as_posix())
        return buf.getvalue()


def help_html() -> Optional[str]:
    """Conteúdo do Help.html (raiz do repositório ou cópia no pacote)."""
    for p in (Path(__file__).resolve().parents[3] / "Help.html",
              Path(__file__).resolve().parent / "Help.html"):
        if p.exists():
            return p.read_text(encoding="utf-8")
    return None
