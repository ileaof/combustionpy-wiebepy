# -*- coding: utf-8 -*-
"""
html_report.py — Relatório HTML autocontido do modo pressão.

Mesmo formato do Single/Double Wiebe: um único arquivo (CSS inline, figuras
PNG embutidas em base64) com todas as constantes do motor, o modelo
ajustado, a configuração do ajuste, métricas, indicadores termodinâmicos,
estatística dos runs, avisos, a comparação entre números de estágios (se
houver) e todos os gráficos. Só valores do próprio relatório são
interpolados (escapados); nenhum HTML de usuário é inserido.
"""
from __future__ import annotations

import base64
import html
import math
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from .. import __version__
from ..core.core import multistage_wiebe
from .engine import volume

FIGURAS = [
    ("pressure.png", "Pressão medida × simulada"),
    ("pressure_stages_comparison.png",
     "Pressão × ângulo — comparação entre estágios (k-Wiebe refinados)"),
    ("pv_diagram.png", "Diagrama P–V (modelo × experimental)"),
    ("pv_diagram_stages_comparison.png",
     "Diagrama P–V — comparação entre estágios (k-Wiebe refinados)"),
    ("pv_diagram_loglog.png", "Diagrama P–V em escala log-log"),
    ("residual.png", "Resíduo de pressão"),
    ("heat_release.png", "Taxa de liberação de calor por estágio e total"),
    ("burned_fraction.png", "Fração de massa queimada"),
    ("burn_rate.png", "Taxa de queima normalizada"),
    ("temperature.png", "Temperatura do gás"),
    ("heat_loss.png", "Calor perdido para as paredes (Hohenberg)"),
    ("volume.png", "Volume do cilindro"),
]


def _e(v) -> str:
    return html.escape(str(v))


def _fmt(v) -> str:
    if isinstance(v, (bool, np.bool_)):
        return "sim" if v else "não"
    if isinstance(v, (float, np.floating)):
        return "—" if not math.isfinite(v) else f"{v:.6g}"
    return _e(v)


def _tabela(cab: List[str], linhas) -> str:
    h = ["<table><thead><tr>"] + [f"<th>{_e(c)}</th>" for c in cab]
    h.append("</tr></thead><tbody>")
    for l in linhas:
        h.append("<tr>" + "".join(f"<td>{_fmt(v)}</td>" for v in l) + "</tr>")
    h.append("</tbody></table>")
    return "".join(h)


def _ca(theta_deg, xb, frac) -> float:
    """Ângulo em que x_b atinge ``frac`` (interpolação linear)."""
    if xb[-1] < frac:
        return float("nan")
    i = int(np.argmax(xb >= frac))
    if i == 0:
        return float(theta_deg[0])
    x0, x1 = xb[i - 1], xb[i]
    return float(theta_deg[i - 1] + (frac - x0) / (x1 - x0)
                 * (theta_deg[i] - theta_deg[i - 1]))


def indicators(r, d) -> Dict[str, float]:
    """Indicadores termodinâmicos do modelo ajustado (e do ensaio)."""
    e = r.settings.engine
    th = d.theta
    thd = np.degrees(th)
    V = volume(th, r.Rc, e)[0]
    xb = multistage_wiebe(th, r.stages)
    fino = np.linspace(th[0], th[-1], 20001)
    xf = multistage_wiebe(fino, r.stages)
    fd = np.degrees(fino)
    i_ps, i_pe = int(np.argmax(r.P_sim)), int(np.argmax(d.P))
    w_sim = float(np.trapezoid(r.P_sim, V))          # kPa·m³ = kJ
    w_exp = float(np.trapezoid(d.P, V))
    out = {
        "P_max_sim [kPa]": float(r.P_sim[i_ps]),
        "θ(P_max) sim [°]": float(thd[i_ps]),
        "P_max_exp [kPa]": float(d.P[i_pe]),
        "θ(P_max) exp [°]": float(thd[i_pe]),
        "T_max [K]": float(np.nanmax(r.Tg)) if r.Tg is not None else float("nan"),
        "θ(T_max) [°]": float(thd[int(np.nanargmax(r.Tg))]) if r.Tg is not None
        else float("nan"),
        "início da combustão θ0_1 [°]": math.degrees(min(s.theta0 for s in r.stages)),
        "CA10 [°]": _ca(fd, xf, 0.10),
        "CA50 [°]": _ca(fd, xf, 0.50),
        "CA90 [°]": _ca(fd, xf, 0.90),
        "duração CA10–CA90 [°]": _ca(fd, xf, 0.90) - _ca(fd, xf, 0.10),
        "Q_total = m_comb·PCI [kJ]": e.Q_total,
        "Q liberado até θ_final [kJ]": float(e.Q_total * xb[-1]),
        "x_b em θ_final [-]": float(xb[-1]),
        "Q perdido às paredes [kJ]": float(r.Q_wall[-1] / 1000.0)
        if r.Q_wall is not None else float("nan"),
        "trabalho indicado ∮P dV, modelo [kJ]": w_sim,
        "trabalho indicado ∮P dV, ensaio [kJ]": w_exp,
        "IMEP modelo (janela) [bar]": w_sim / e.Vd / 100.0,
        "IMEP ensaio (janela) [bar]": w_exp / e.Vd / 100.0,
    }
    return out


def _figuras(pasta: Optional[Path], r, d) -> List[tuple]:
    """(título, PNG em base64) das figuras; gera-as se ``pasta`` não as tiver."""
    from .report import _graus, _plots, _stage_comparisons
    tmp = None
    if pasta is None or not (pasta / "pressure.png").exists():
        tmp = tempfile.TemporaryDirectory()
        pasta = Path(tmp.name)
        comp_est = (_stage_comparisons(r, d) if len(r.stages) > 1 else {})
        _plots(pasta, r, d, _graus(r.stages), comp_est)
    out = []
    for nome, titulo in FIGURAS:
        p = pasta / nome
        if p.exists():
            out.append((titulo, base64.b64encode(p.read_bytes()).decode("ascii")))
    if tmp is not None:
        tmp.cleanup()
    return out


def report_html(r, d, comp: Optional[Dict] = None,
                plots_dir: Optional[Path] = None) -> str:
    e = r.settings.engine
    s = r.settings
    partes: List[str] = []
    a = partes.append
    a(f"<h1>wiebepy — Relatório do ajuste de pressão ({s.n_stages}-Wiebe)</h1>")
    a("<p class='sub'>Ajuste da curva de pressão do cilindro com liberação de "
      "calor Wiebe de N estágios (modelo 0-D de zona única do Double Wiebe: "
      "geometria biela-manivela, Hohenberg, EDOs em P e T<sub>g</sub>). "
      "Extensão do modelo Single Wiebe desenvolvido na dissertação de "
      "L. Queiroz, sob orientação do Prof. I. L. Ferreira.</p>")
    a(_tabela(["Item", "Valor"], [
        ["arquivo do ensaio", d.source or "—"],
        ["pontos usados", d.n],
        ["janela angular [°]", f"{math.degrees(d.theta[0]):.2f} a "
                               f"{math.degrees(d.theta[-1]):.2f}"],
        ["gerado em", datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
        ["wiebepy", __version__],
    ]))

    m = r.metrics or {}
    a("<h2>Resumo</h2>")
    a("<div class='cards'>" + "".join(
        f"<div class='card'><div class='k'>{_e(k)}</div>"
        f"<div class='v'>{_e(v)}</div></div>" for k, v in (
            ("RMSE", f"{m.get('rmse', float('nan')):.3f} kPa"),
            ("R²", f"{m.get('r2', float('nan')):.6f}"),
            ("Rc ajustado", f"{r.Rc:.4f}"),
            ("estágios", s.n_stages),
            ("runs", len(r.runs)),
            ("tempo", f"{r.elapsed_s:.1f} s"))) + "</div>")

    a("<h2>Motor e constantes</h2>")
    a(_tabela(["Constante", "Valor", "Unidade"], [
        ["diâmetro (bore)", e.bore * 1e3, "mm"],
        ["curso (stroke)", e.stroke * 1e3, "mm"],
        ["comprimento da biela", e.rod_length * 1e3, "mm"],
        ["raio da manivela r = s/2", e.r_crank * 1e3, "mm"],
        ["razão biela/manivela R = l/r", e.R, "-"],
        ["cilindrada unitária Vd", e.Vd * 1e6, "cm³"],
        ["razão de compressão Rc (ajustada)" if s.fit_rc
         else "razão de compressão Rc (fixa)", r.Rc, "-"],
        ["volume de folga Vc = Vd/(Rc−1)", e.Vd / (r.Rc - 1) * 1e6, "cm³"],
        ["Rc inicial/nominal do motor", e.Rc, "-"],
        ["rotação", e.rpm, "rpm"],
        ["velocidade média do pistão Vp", e.Vp, "m/s"],
        ["massa de combustível por ciclo", e.m_fuel, "kg/ciclo"],
        ["poder calorífico inferior (PCI)", e.LHV, "kJ/kg"],
        ["energia do combustível Q_total", e.Q_total, "kJ/ciclo"],
        ["razão de calores específicos κ", e.kappa, "-"],
        ["temperatura inicial T1", e.T1, "K"],
        ["temperatura da parede Tw", e.Tw, "K"],
        ["perda de calor (Hohenberg)", e.heat_transfer, ""],
        ["pressão inicial P1 (medida)", float(d.P[0]), "kPa"],
    ]))
    a("<p class='nota'>Hohenberg: h = 130·V<sup>−0,06</sup>·(P·10<sup>−2</sup>)"
      "<sup>0,8</sup>·T<sub>g</sub><sup>−0,4</sup>·(Vp + 1,4)<sup>0,8</sup> "
      "[W/(m²K)]; dP/dθ = [(κ−1)(dQ/dθ − dQ<sub>w</sub>/dθ) − κP dV/dθ]/V.</p>")

    a("<h2>Modelo ajustado</h2>")
    a(_tabela(["estágio", "β [-]", "θ0 [°]", "Δθ [°]", "θ0 [rad]", "Δθ [rad]",
               "m [-]", "a [-]", "Q do estágio [kJ]"],
              [[j, st.beta, math.degrees(st.theta0), math.degrees(st.duration),
                st.theta0, st.duration, st.m, st.a, st.beta * e.Q_total]
               for j, st in enumerate(r.stages, start=1)]))
    a("<p class='nota'>x<sub>b</sub>(θ) = Σ β<sub>j</sub>[1 − exp(−a<sub>j</sub>"
      "z<sub>j</sub><sup>m<sub>j</sub>+1</sup>)], z<sub>j</sub> = (θ − θ0<sub>j"
      "</sub>)/Δθ<sub>j</sub>; dQ/dθ = Q_total · Σ β<sub>j</sub> dx<sub>j</sub>/dθ."
      "</p>")

    a("<h2>Coeficientes do modelo</h2>")
    a("<h3>Transferência de calor — correlação de Hohenberg</h3>")
    a("<p class='nota'>h = C · V<sup>e<sub>V</sub></sup> · (P·f<sub>P</sub>)"
      "<sup>e<sub>P</sub></sup> · T<sub>g</sub><sup>e<sub>T</sub></sup> · "
      "(Vp + b)<sup>e<sub>Vp</sub></sup> [W/(m²K)];  dQ<sub>w</sub>/dθ = "
      "h·A<sub>s</sub>·(T<sub>g</sub> − T<sub>w</sub>)/(2π·rpm/60) [J/rad]</p>")
    a(_tabela(["Coeficiente", "Símbolo", "Valor", "Unidade / observação"], [
        ["constante de Hohenberg", "C", 130.0, "SI"],
        ["expoente do volume", "e_V", -0.06, "V em m³"],
        ["expoente da pressão", "e_P", 0.8, "P em bar"],
        ["escala da pressão (kPa → bar)", "f_P", 1.0e-2, "-"],
        ["expoente da temperatura", "e_T", -0.4, "T_g em K"],
        ["acréscimo à velocidade do pistão", "b", 1.4, "m/s"],
        ["expoente da velocidade", "e_Vp", 0.8, "-"],
        ["fator (Vp + b)^e_Vp calculado", "", (e.Vp + 1.4) ** 0.8, "-"],
        ["perda de calor ativa", "", e.heat_transfer, ""],
    ]))
    a("<h3>Balanço de energia e integração</h3>")
    a(_tabela(["Coeficiente", "Valor", "Observação"], [
        ["κ (razão de calores específicos)", e.kappa, "constante no ciclo"],
        ["T1 (início da integração)", e.T1, "K"],
        ["Tw (parede)", e.Tw, "K"],
        ["P1 (primeiro ponto medido)", float(d.P[0]), "kPa"],
        ["conversão J → kJ no balanço", 1.0e-3, "dQ_w/1000"],
        ["integrador de referência", "DOP853", "solve_ivp"],
        ["rtol / atol da referência", "1e-9 / 1e-9", ""],
        ["integrador da busca", "RK4 passo fixo",
         f"{s.substeps} sub-passos por intervalo"],
        ["limite de sanidade das derivadas", 1.0e12,
         "acima disso o candidato é penalizado"],
    ]))
    a("<h3>Coeficientes Wiebe de cada estágio</h3>")
    linhas_w = []
    for j, st in enumerate(r.stages, start=1):
        linhas_w += [[j, "β (fração de energia)", st.beta, "-"],
                     [j, "θ0 (início)", math.degrees(st.theta0), "°"],
                     [j, "Δθ (duração)", math.degrees(st.duration), "°"],
                     [j, "m (forma)", st.m, "-"],
                     [j, "a (eficiência)", st.a, "-"],
                     [j, "fração queimada ao fim de Δθ, 1 − e^(−a)",
                      1.0 - math.exp(-st.a), "-"]]
    a(_tabela(["estágio", "coeficiente", "valor", "unidade"], linhas_w))
    a("<h3>Vetor de parâmetros ajustados (espaço de busca)</h3>")
    vivos = r.best.x
    from ..optimization.bounds import at_bounds
    borda = at_bounds(vivos, r.param.lower, r.param.upper)
    a(_tabela(["parâmetro", "valor ajustado", "limite inferior",
               "limite superior", "na borda?"],
              [[nm, float(v), float(lo), float(hi), "SIM" if bd else "não"]
               for nm, v, lo, hi, bd in zip(r.param.names, vivos, r.param.lower,
                                            r.param.upper, borda)]))
    a("<p class='nota'>Ângulos do vetor de busca em rad. θ0_j = θ0_1 + Σ "
      "dtheta0_k; pesos por stick-breaking: β_1 = s_1, β_j = s_j·Π(1 − s_k), "
      "β_N = Π(1 − s_k).</p>")

    a("<h2>Configuração do ajuste</h2>")
    b = s.bounds_deg
    a(_tabela(["Item", "Valor"], [
        ["otimizador", f"PSO ({s.topology}), {s.particles} partículas × "
                       f"{s.iterations} iterações, paciência {s.patience}"],
        ["runs independentes / semente", f"{s.runs} / {s.seed}"],
        ["refinamento local", f"mínimos quadrados (TRF), {s.polish_starts} "
                              f"inícios" if s.polish else "desligado"],
        ["integrador da busca", f"RK4 em lote, {s.substeps} sub-passos, "
                                f"backend {r.backend}, {s.precision}"],
        ["referência (RMSE relatado)", "solve_ivp DOP853, rtol = atol = 1e-9"],
        ["parametrização de β", s.beta_mode],
        ["Rc", f"ajustado em [{s.rc_bounds[0]}, {s.rc_bounds[1]}]"
               if s.fit_rc else f"fixo = {e.Rc}"],
        ["limites θ0₁ [°]", f"{b['theta0'][0]} a {b['theta0'][1]}"],
        ["incremento entre inícios [°]", f"{b['dtheta0'][0]} a {b['dtheta0'][1]}"],
        ["limites Δθ [°]", f"{b['duration'][0]} a {b['duration'][1]}"],
        ["último início θ0_N máx [°]", b.get("theta0_max", "—")],
        ["limites m", f"{s.m_bounds[0]} a {s.m_bounds[1]}"],
        ["a", "ajustado" if s.fit_a else f"fixo = {s.a_fixed}"],
    ]))

    a("<h2>Métricas de ajuste (pressão)</h2>")
    nomes = {"rmse": "RMSE [kPa]", "mae": "MAE [kPa]", "mse": "MSE [kPa²]",
             "see": "SEE [kPa]", "r2": "R² [-]", "aic": "AIC", "bic": "BIC",
             "durbin_watson": "Durbin-Watson", "lag1_autocorr":
             "autocorrelação lag-1", "max_abs_err": "erro absoluto máximo [kPa]",
             "n": "pontos", "k": "parâmetros livres", "sse": "SSE [kPa²]"}
    a(_tabela(["Métrica", "Valor"], [[nomes.get(k, k), v] for k, v in m.items()
                                     if k not in ("P_max_sim_kPa",
                                                  "P_max_exp_kPa", "wrmse")]))

    a("<h2>Indicadores termodinâmicos</h2>")
    a(_tabela(["Indicador", "Valor"], list(indicators(r, d).items())))

    a("<h2>Runs</h2>")
    a(_tabela(["run", "semente", "RMSE solve_ivp [kPa]", "RMSE RK4 [kPa]",
               "iterações", "parada", "tempo [s]", "observação"],
              [[x.run + 1, x.seed if x.seed is not None else "—", x.rmse,
                x.rmse_rk4, x.iterations, x.stopped_by, x.elapsed_s,
                x.note or ""] for x in r.runs]))
    o = r.objective_stats
    a(f"<p>RMSE entre runs: melhor {o['best']:.4f} · média {o['mean']:.4f} · "
      f"desvio {o['std']:.4f} · mediana {o['median']:.4f} · pior "
      f"{o['worst']:.4f} kPa</p>")

    a("<h2>Avisos</h2>")
    if r.warnings:
        a("<ul class='avisos'>" + "".join(f"<li>{_e(w)}</li>" for w in r.warnings)
          + "</ul>")
    else:
        a("<p>Nenhum aviso.</p>")

    if comp is not None:
        a("<h2>Comparação entre números de estágios</h2>")
        a(f"<p><b>Recomendado: {comp['recommended']}-Wiebe</b> — "
          f"{_e(comp['reason'])}.</p>")
        a(_tabela(["N", "k", "RMSE [kPa]", "CV RMSE [kPa]", "R²", "ΔAIC", "ΔBIC",
                   "Durbin-Watson", "avisos", "tempo [s]"],
                  [[l["n_stages"], l["k"], l["rmse"], l["cv_rmse"], l["r2"],
                    l["delta_aic"], l["delta_bic"], l["durbin_watson"],
                    l["n_warnings"], l["time_s"]] for l in comp["table"]]))

    a("<h2>Gráficos</h2>")
    for titulo, b64 in _figuras(plots_dir, r, d):
        a(f"<figure><figcaption>{_e(titulo)}</figcaption>"
          f"<img src='data:image/png;base64,{b64}' alt='{_e(titulo)}'></figure>")

    css = (
        "body{font-family:'Segoe UI',Arial,sans-serif;margin:24px auto;"
        "max-width:1000px;padding:0 16px;color:#1d2330;background:#fff}"
        "h1{font-size:24px;margin-bottom:4px}h2{font-size:18px;margin-top:28px;"
        "border-bottom:2px solid #b4432f;padding-bottom:3px}"
        ".sub{color:#5b6475;font-style:italic}.nota{color:#5b6475;font-size:13px}"
        "table{border-collapse:collapse;font-size:13px;margin:8px 0;width:100%}"
        "th,td{border:1px solid #e3e6ee;padding:4px 8px;text-align:left}"
        "th{background:#f1f3f8}tr:nth-child(even) td{background:#fafbfd}"
        ".cards{display:flex;flex-wrap:wrap;gap:10px}.card{border:1px solid "
        "#e3e6ee;border-radius:8px;padding:8px 14px;min-width:120px}"
        ".card .k{font-size:12px;color:#5b6475}.card .v{font-size:18px;"
        "font-weight:600}.avisos li{color:#9a6500}"
        "figure{margin:18px 0}figcaption{font-weight:600;margin-bottom:6px}"
        "img{max-width:100%;border:1px solid #e3e6ee;border-radius:6px}"
        "@media print{h2{page-break-after:avoid}figure{page-break-inside:avoid}}")
    return ("<!DOCTYPE html><html lang='pt-BR'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>wiebepy — Relatório de pressão ({s.n_stages}-Wiebe)</title>"
            f"<style>{css}</style></head><body>" + "".join(partes)
            + "</body></html>")
