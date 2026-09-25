# -*- coding: utf-8 -*-
"""
report.py — Relatório HTML autônomo do caso de fresta.

Mesmo padrão dos relatórios do wiebepy (CSS inline, figuras PNG em
base64 — matplotlib, sem seaborn). Distinção EXPLÍCITA entre grandezas
SIMULADAS (resolvidas pelo solver), IMPOSTAS (condições de contorno e
propriedades declaradas pelo usuário) e MEDIDAS (nenhuma neste nível —
a comparação com ensaio é diagnóstico, não validação). O estado de
conclusão distingue "processo terminou" de "janela coberta".
"""
from __future__ import annotations

import base64
import io
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from ..cfd.config import read_state
from .results import CreviceResults


def _e(v) -> str:
    import html
    return html.escape(str(v))


def _fmt(v, nd: int = 4) -> str:
    if v is None:
        return "—"
    try:
        fv = float(v)
    except (TypeError, ValueError):
        return _e(v)
    if fv == 0.0:
        return "0"
    return f"{fv:.{nd}g}"


def _tabela(cab: List[str], linhas) -> str:
    th = "".join(f"<th>{_e(c)}</th>" for c in cab)
    trs = "".join(
        "<tr>" + "".join(f"<td>{_e(c) if not isinstance(c, float) else _fmt(c)}"
                         f"</td>" for c in linha) + "</tr>"
        for linha in linhas)
    return (f"<table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody>"
            "</table>")


def _fig(curvas: List[Dict], xlab: str, ylab: str,
         titulo: str) -> Tuple[str, str]:
    """Figura matplotlib → (título, base64)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(6.4, 3.4), dpi=110)
    for c in curvas:
        ax.plot(c["x"], c["y"], label=c.get("label", ""), lw=1.4,
                color=c.get("color"))
    ax.set_xlabel(xlab)
    ax.set_ylabel(ylab)
    ax.set_title(titulo, fontsize=10)
    ax.grid(alpha=0.3)
    if any(c.get("label") for c in curvas):
        ax.legend(fontsize=8)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return (titulo, base64.b64encode(buf.getvalue()).decode())


CSS = """
body { font-family: 'Segoe UI', system-ui, sans-serif; margin: 2em auto;
       max-width: 900px; padding: 0 1em; color: #1c2430;
       background: #fbfbf9; line-height: 1.5; }
h1 { font-size: 1.5em; border-bottom: 2px solid #264653; padding-bottom:.3em; }
h2 { font-size: 1.15em; color: #264653; margin-top: 1.6em;
     border-bottom: 1px solid #d8dde3; padding-bottom: .2em; }
table { border-collapse: collapse; width: 100%; margin: .6em 0;
        font-size: .88em; }
th { background: #264653; color: #fff; text-align: left; padding: .35em .6em; }
td { border-bottom: 1px solid #e2e6ea; padding: .3em .6em;
     font-variant-numeric: tabular-nums; }
tr:nth-child(even) td { background: #f2f4f6; }
.nota { background: #f4f1e8; border-left: 3px solid #b08930;
        padding: .5em .9em; font-size: .88em; margin: .6em 0; }
.alerta { background: #fbeaea; border-left: 3px solid #b3402e;
          padding: .5em .9em; font-size: .88em; margin: .6em 0; }
.ok { background: #eaf4ea; border-left: 3px solid #3c7a3c;
      padding: .5em .9em; font-size: .88em; margin: .6em 0; }
.sub { color: #5a6472; font-size: .92em; }
img { max-width: 100%; margin: .4em 0; }
.badge { display: inline-block; padding: .1em .6em; border-radius: 3px;
         font-size: .78em; font-weight: 600; color: #fff; }
.sim { background: #2a6f97; } .imp { background: #b08930; }
.med { background: #3c7a3c; }
"""


def report_html(case_dir, run_summary: Optional[Dict] = None) -> str:
    """Monta o HTML completo do caso de fresta."""
    case_dir = Path(case_dir)
    import yaml
    info: Dict = {}
    yml = case_dir / "case_config.yaml"
    if yml.exists():
        try:
            info = yaml.safe_load(yml.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            pass
    estado = read_state(case_dir)
    res = CreviceResults.load(case_dir, cfg=None)
    tem_campos = bool(res.t.size)

    partes: List[str] = []
    a = partes.append
    a(f"<h1>wiebepy crevice_flow — Fresta top-land ({_e(case_dir.name)})</h1>")
    a("<p class='sub'>Submodelo de escoamento na fresta entre pistão, "
      "primeiro anel e cilindro. <b>NÃO é simulação de blow-by</b>: o "
      "domínio comunica APENAS com a câmara (fundo fechado no flanco "
      "acima do 1º anel). A pressão da câmara é prescrita — o escoamento "
      "calculado <b>não modifica</b> essa pressão (não é acoplamento "
      "bidirecional).</p>")

    # ------------------------------------------------------ identificação
    a("<h2>Identificação e estado</h2>")
    si = info.get("solver_info") or {}
    a(_tabela(["Item", "Valor"], [
        ["diretório do caso", str(case_dir.resolve())],
        ["relatório gerado em", datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
        ["nível", info.get("nivel", "—")],
        ["estado do caso", estado.label],
        ["solver", f"OpenFOAM Foundation {si.get('version', '—')} "
                   f"({si.get('root', '—')})"],
        ["execução", (run_summary or {}).get("elapsed_s", "—")],
    ]))
    if estado.value == "completed":
        a("<p class='ok'>Concluído: o solver encerrou com 'End' e a "
          "janela simulada está coberta (verificação de resultados, não "
          "apenas o fim do processo).</p>")
    elif estado.value in ("running", "failed", "cancelled", "prepared",
                          "validated"):
        a("<p class='alerta'>Estado "
          f"{estado.label.lower()}: este relatório pode refletir "
          "resultados PARCIAIS ou ausentes. 'Processo terminou' não "
          "implica 'simulação concluída nem convergiu'.</p>")

    # --------------------------------------------------- grandezas e origem
    a("<h2>Grandezas: simuladas, impostas, medidas</h2>")
    a("<p><span class='badge sim'>SIMULADO</span> resolvido pelo solver &nbsp;"
      "<span class='badge imp'>IMPOSTO</span> condição declarada pelo "
      "usuário/config &nbsp;<span class='badge med'>MEDIDO</span> dado de "
      "ensaio</p>")
    a(_tabela(["Grandeza", "Classe", "Origem"], [
        ["p, T, ρ, U na fresta e no buffer", "SIMULADO",
         "foamRun (fluid, laminar)"],
        ["vazão mássica nas aberturas (phi)", "SIMULADO",
         "functionObject surfaceFieldValue"],
        ["calor trocado com as paredes", "SIMULADO",
         "wallHeatFlux + areaIntegrate"],
        ["p da câmara p(θ)", "IMPOSTO",
         f"{info.get('condicao_camara', {}).get('fonte', '—')} — arquivo "
         f"{info.get('condicao_camara', {}).get('arquivo', '—')}"],
        ["temperatura do gás que entra", "IMPOSTO",
         f"inflow_T_K = {info.get('condicao_camara', {}).get('inflow_T_K', '—')} "
         "(a pressão sozinha não determina o estado)"],
        ["temperaturas das paredes", "IMPOSTO", "seção thermal da config"],
        ["propriedades do gás (R, γ, μ, Pr)", "IMPOSTO",
         info.get("gas_provenance", "—")],
        ["rotação / conversão θ↔t", "IMPOSTO",
         f"{info.get('rotacao', {}).get('rpm', '—')} rpm"],
        ["dados do ensaio", "MEDIDO",
         "nenhuma grandeza medida entra neste nível"],
    ]))
    a("<p class='nota'>A comparação deste submodelo com ensaio é sempre "
      "DIAGNÓSTICA — nunca validação. Calibrar não é validar.</p>")

    # ------------------------------------------------------------- geometria
    a("<h2>Geometria, malha e regime</h2>")
    geo = info.get("geometria_mm") or {}
    mal = info.get("malha") or {}
    reg = info.get("regime") or {}
    a(_tabela(["Grandeza", "Valor"], [
        ["diâmetro do cilindro [mm]", geo.get("bore_diameter")],
        ["folga radial da fresta [mm]", geo.get("radial_gap")],
        ["altura do top land [mm]", geo.get("top_land_height")],
        ["altura do buffer [mm]", geo.get("buffer_height")],
        ["ângulo do setor [°]", geo.get("sector_angle")],
        ["volume da fresta [cm³]",
         f"{float(info.get('volume_fresta_m3', 0) or 0) * 1e6:.4g}"],
        ["células", mal.get("n_cells")],
        ["Δr [m]", mal.get("delta_r_m")],
        ["Δz [m]", mal.get("delta_z_m")],
        ["razão de aspecto", _fmt(mal.get("aspect_ratio"), 3)],
        ["regime", reg.get("turbulencia", "—")],
        ["Re estimado na folga", _fmt(reg.get("Re_estimativa_folga"), 4)],
    ]))
    a("<p class='nota'>" + _e(reg.get("nota", "")) + " O modelo "
      "turbulento NÃO foi selecionado automaticamente por se tratar de um "
      "motor — a justificativa de laminar é local (Re da folga) e fica "
      "registrada; se o Re real for muito maior, declare e habilite um "
      "modelo explicitamente.</p>")
    a("<p class='nota'>Setor periódico (wedge): válido porque geometria e "
      "BCs são uniformes na circunferência. Uma abertura LOCALIZADA do "
      "anel (gap do anel) NÃO é representada neste nível.</p>")

    # --------------------------------------------------------------- BCs
    a("<h2>Condições de contorno e conversões</h2>")
    cc = info.get("condicao_camara") or {}
    rot = info.get("rotacao") or {}
    a(_tabela(["Item", "Valor"], [
        ["BC de pressão na boca", cc.get("bc")],
        ["pico de pressão imposto [Pa]", _fmt(cc.get("pico_Pa"))],
        ["janela do arquivo [° CA]",
         f"{(cc.get('janela_arquivo_deg') or ['—', '—'])[0]} a "
         f"{(cc.get('janela_arquivo_deg') or ['—', '—'])[-1]}"],
        ["extrapolação fora da tabela", cc.get("extrapolate")],
        ["rotação", f"{rot.get('rpm')} rpm"],
        ["dθ/dt [°/s]", _fmt(rot.get("dtheta_dt_deg_s"), 6)],
        ["dθ/dt [rad/s]", _fmt(rot.get("dtheta_dt_rad_s"), 6)],
        ["janela simulada [° CA]",
         f"{(info.get('janela_deg') or ['—'])[0]} a "
         f"{(info.get('janela_deg') or ['—', '—'])[1]}"],
        ["tempo do solver [s]",
         f"{(info.get('tempo_s') or ['—', '—'])[0]} a "
         f"{(info.get('tempo_s') or ['—', '—'])[1]}"],
        ["referencial", (info.get("referencial") or {}).get("frame")],
    ]))
    for h in info.get("hipoteses") or []:
        a(f"<p class='nota'>Hipótese: {_e(h)}</p>")
    a("<p class='nota'>Convenção de sinais: ṁ > 0 = fluxo SAINDO do "
      "domínio (fresta→câmara); q̇ > 0 = gás PERDE calor para a parede. "
      "Massas acumuladas de entrada e de saída são integradas "
      "separadamente a partir do sinal de ṁ.</p>")
    a("<p class='nota'>" + _e(info.get("balanco_energia", "")) + "</p>")

    if not tem_campos:
        a("<h2>Séries temporais</h2>")
        a("<p class='alerta'>Sem séries em postProcessing — prepare e "
          "execute o caso antes de gerar o relatório definitivo.</p>")
    else:
        # ------------------------------------------------------- séries
        a("<h2>Séries temporais</h2>")
        th = res.theta_deg
        figs = [
            _fig([{"x": th, "y": res.p_camara / 1e5,
                   "label": "p câmara (imposta/verificada)", "color": "#b3402a"}],
                 "θ [° CA]", "p [bar]", "Pressão na boca da fresta"),
            _fig([{"x": th, "y": res.mdot, "label": "ṁ (sinal OF)", "color": "#2a6f97"},
                  {"x": th, "y": res.mdot_in, "label": "entrada (≥0)",
                   "color": "#3c7a3c", "ls": "--"},
                  {"x": th, "y": res.mdot_out, "label": "saída (≥0)",
                   "color": "#b08930", "ls": "--"}],
                 "θ [° CA]", "ṁ [kg/s]",
                 "Vazão mássica na boca (ṁ>0 sai do domínio)"),
            _fig([{"x": th, "y": res.m_in_cum() * 1e9,
                   "label": "entrada acumulada", "color": "#3c7a3c"},
                  {"x": th, "y": res.m_out_cum() * 1e9,
                   "label": "saída acumulada", "color": "#b08930"}],
                 "θ [° CA]", "m [mg·10⁻³ = kg·10⁻⁹]",
                 "Massas acumuladas (entrada e saída separadas)"),
            _fig([{"x": th, "y": res.m_fresta * 1e9, "label": "fresta",
                   "color": "#2a6f97"},
                  {"x": th, "y": res.m_buffer * 1e9, "label": "buffer",
                   "color": "#b08930"}],
                 "θ [° CA]", "m [kg·10⁻⁹]", "Massa armazenada por zona"),
            _fig([{"x": th, "y": res.q_liner, "label": "liner",
                   "color": "#2a6f97"},
                  {"x": th, "y": res.q_pistao, "label": "pistão",
                   "color": "#b3402a"}],
                 "θ [° CA]", "q̇ [W] (gás→parede > 0)",
                 "Transferência de calor por parede"),
            _fig([{"x": th, "y": res.u_total * 1e3, "label": "U",
                   "color": "#5a4e8a"}],
                 "θ [° CA]", "U [mJ]", "Energia interna (∫p dV/(γ−1))"),
        ]
        for titulo, b64 in figs:
            a(f"<h3>{_e(titulo)}</h3>")
            a(f"<img src='data:image/png;base64,{b64}' alt='{_e(titulo)}'>")

        # ------------------------------------------------------ balanços
        a("<h2>Balanços quantificados</h2>")
        bm = res.balanco_massa()
        be = res.balanco_energia()
        a(_tabela(["Balanço", "Resíduo", "Relativo", "Tolerância",
                   "Estado"], [
            ["massa", _fmt(bm.valor, 3) + " kg",
             f"{bm.rel_pct:.4g} %", f"{bm.tolerancia_pct} %",
             "OK" if bm.ok else "FALHOU"],
            ["energia", _fmt(be.valor, 4) + " J",
             f"{be.rel_pct:.4g} %", f"{be.tolerancia_pct} %",
             "FALHOU" if not be.ok else "OK"],
        ]))
        for b in (bm, be):
            det = "; ".join(f"{k} = {_fmt(v, 5)}" for k, v in
                            b.detalhe.items() if k != "aproximacao")
            cls = "ok" if b.ok else "alerta"
            a(f"<p class='{cls}'><b>{_e(b.nome)}:</b> {det}</p>")
        a("<p class='nota'>Aproximações declaradas do balanço de energia: "
          "h ≈ cp·T (sem energia cinética), entalpia de entrada com "
          "T_inflow, termo viscoso de parede desprezado, volume constante "
          "no referencial do domínio (sem trabalho p·dV). A energia usa "
          "U = ∫p dV/(γ−1) (exato para gás perfeito).</p>")

        # -------------------------------------------------------- export
        csv = case_dir / "results_series.csv"
        if not csv.exists():
            res.export_serie(case_dir)
        tempos = res.tempos_de_campo(case_dir)
        a("<h2>Exportações</h2>")
        a(_tabela(["Arquivo", "Conteúdo"], [
            ["results_series.csv", "séries completas com convenção de "
                                   "sinais no cabeçalho"],
            ["tempos de campo (snapshots)",
             f"{len(tempos)} instantes: {', '.join(_fmt(t, 5) for t in tempos[:8])}"
             + ("…" if len(tempos) > 8 else "")],
        ]))
        a("<p class='nota'>Os campos 3D (p, T, U, ρ) ficam no formato "
          "nativo do OpenFOAM nos diretórios de tempo do caso — abertos "
          "no paraFoam/paraview sem conversão.</p>")

    # ---------------------------------------------------------- limitações
    a("<h2>Limitações e avisos</h2>")
    for h in info.get("hipoteses") or []:
        pass
    limite = [
        "Submodelo com câmara prescrita: o resultado NÃO retroage na "
        "pressão da câmara (não é acoplamento bidirecional).",
        "Não é blow-by: não há caminho de fuga para região de menor "
        "pressão — o domínio só comunica com a câmara.",
        "Sem anéis móveis, sem filme de óleo, sem combustão, sem "
        "transporte de combustível, sem emissões de HC.",
        "Efeitos do referencial acelerado (ω²r) negligenciados (hipótese "
        "declarada na config do caso).",
        "Setor wedge só representa fresta anelar completa e uniforme.",
    ]
    for l in limite:
        a(f"<p class='nota'>Limitação: {_e(l)}</p>")
    for av in info.get("avisos") or []:
        a(f"<p class='alerta'>Aviso (da config): {_e(av)}</p>")

    return (f"<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'>"
            f"<title>wiebepy crevice_flow — relatório</title>"
            f"<style>{CSS}</style></head><body>"
            + "".join(partes) + "</body></html>")


def write_report(case_dir, run_summary: Optional[Dict] = None) -> Path:
    """Gera report.html no diretório do caso."""
    case_dir = Path(case_dir)
    html = report_html(case_dir, run_summary)
    saida = case_dir / "report.html"
    saida.write_text(html, encoding="utf-8")
    return saida


__all__ = ["report_html", "write_report"]