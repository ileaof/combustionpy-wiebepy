# -*- coding: utf-8 -*-
"""
reporting.py — Relatório HTML autocontido do caso CFD.

Mesmo padrão do relatório de pressão (CSS inline, figuras PNG em base64):
identificação do caso, solver/adapter, modo físico, combustível,
geometria e movimento, condições iniciais/de contorno, modelos, fonte
Wiebe e distribuição, configuração numérica, hardware/paralelismo,
balanços, comparação experimental (quando fornecida), gráficos, avisos e
limitações, proveniência.

Nenhum resultado prescrito é apresentado como previsão independente: o
relatório carrega os avisos do modo (distribution_notice etc.) e as
limitações científicas (§19) em toda versão.
"""
from __future__ import annotations

import base64
import html
import io
import math
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

# np.trapz saiu do NumPy 2 (virou np.trapezoid) e o pacote declara
# numpy>=1.24: a integral precisa dos dois nomes. O resto do módulo
# CFD já fazia isso; faltava aqui, e era o que derrubava o relatório
# em instalação nova (NumPy ≥ 2.2 não tem mais np.trapz).
_integra = getattr(np, "trapezoid", None) or np.trapz

from ..i18n import idioma, idioma_fixo, rotulo, t as _, tf, ts
from .config import CfdConfig, CaseState, read_state
from .fuels import comparison_notice
from .sources.wiebe_heat_release import distribution_notice

_LIM = [
    "A pressão experimental sozinha não identifica unicamente os campos "
    "3D: diferentes distribuições espaciais de calor podem reproduzir "
    "pressões médias semelhantes.",
    "Ajustar a pressão não valida automaticamente temperatura local, "
    "frente de chama ou emissões.",
    "Somente o intervalo de válvulas fechadas é simulado; isso exige "
    "hipóteses sobre o estado inicial da carga (repouso, P/T uniformes).",
    "Emissões não são calculadas neste modo.",
    "Mecanismos químicos e propriedades têm faixas de validade — no modo "
    "reativo, declare-as por combustível.",
]


def write_exp_csv(path, theta_rad, p_kPa, origem: str = "") -> Path:
    """Grava um ensaio θ [rad], P [kPa] no formato que ``load_exp_data``
    lê: SEM cabeçalho (o leitor descarta colunas de nome desconhecido,
    como "P"), só linhas ``#`` com a origem."""
    linhas = [f"# ensaio: {origem}", "# theta [rad], P [kPa]"]
    linhas += [f"{t:.10g},{p:.10g}" for t, p in zip(theta_rad, p_kPa)]
    path = Path(path)
    path.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return path


def load_exp_data(case_dir, cfg=None, engine=None) -> Optional[Dict]:
    """Dados experimentais para a comparação do relatório.

    Fonte: ``cfd.comparison.experimental`` (CSV θ,P — leitor do módulo de
    pressão, unidade angular rad e pressão kPa por documentação) +
    ``experimental_offset_deg`` (alinhamento de fase declarado; 0 = sem
    alinhamento). Retorna dict com ca_deg/p_kPa (pós-offset), volume
    V(θ) pela cinemática do motor e avisos; None se não configurado.
    """
    import yaml as _yaml
    from ..pressure.fit import read_pressure
    case_dir = Path(case_dir)
    fonte, offset, extra = None, 0.0, []
    au, pu = "rad", "kPa"
    if cfg is not None and getattr(cfg, "experimental", None):
        fonte = cfg.experimental
        offset = float(cfg.experimental_offset_deg or 0.0)
        au = cfg.experimental_angle_unit or "rad"
        pu = cfg.experimental_pressure_unit or "kPa"
    else:
        yml = case_dir / "case_config.yaml"
        if yml.exists():
            try:
                info = _yaml_load(yml)
            except OSError:
                info = {}
            comp = (info.get("comparison")
                    or (info.get("configuration") or {}).get("comparison")
                    or {})
            fonte = comp.get("experimental")
            offset = float(comp.get("experimental_offset_deg") or 0.0)
            au = str(comp.get("experimental_angle_unit") or "rad")
            pu = str(comp.get("experimental_pressure_unit") or "kPa")
    if not fonte:
        return None
    p = Path(fonte)
    if not p.exists() and not p.is_absolute():
        alt = case_dir / fonte
        if alt.exists():
            p = alt
    if not p.exists():
        return {"source": fonte, "erro": "arquivo experimental não "
                                         "encontrado (relatório gerado "
                                         "sem as comparações)."}
    try:
        d = read_pressure(p, angle_unit=au, pressure_unit=pu,
                          theta_min=None, theta_max=None)
    except ValueError as e:
        return {"source": fonte, "erro": f"leitura do CSV experimental "
                                         f"falhou: {e}"}
    if d.warnings:
        extra = d.warnings
    ca_deg = np.degrees(d.theta) + offset
    out = {"source": str(p), "ca_deg": ca_deg, "p_kPa": d.P,
           "offset_deg": offset,
           "units": {"angle": au, "pressure": pu},
           "warnings": extra}
    if engine is not None and len(ca_deg):
        from ..pressure.engine import volume
        V, _dV, _dA = volume(np.radians(ca_deg - offset), engine.Rc,
                             engine)
        out["V_m3"] = np.asarray(V, float)
    return out


def _yaml_load(p: Path) -> Dict:
    import yaml
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def _metricas_experimental(res: Dict, exp: Dict,
                           rpm: Optional[float] = None) -> List[List]:
    """Métricas p̄ CFD × p medida no ponto experimental (seleção
    documentada; sem calibração silenciosa)."""
    ca = np.asarray(res.get("ca_deg") if res.get("ca_deg") is not None
                    else [], float)
    p = np.asarray(res.get("p_mean_kPa") if res.get("p_mean_kPa")
                   is not None else [], float)
    cae = np.asarray(exp.get("ca_deg") if exp.get("ca_deg") is not None
                     else [], float)
    pe = np.asarray(exp.get("p_kPa") if exp.get("p_kPa") is not None
                    else [], float)
    if not len(ca) or not len(cae):
        return []
    dentro = (cae >= ca.min()) & (cae <= ca.max())
    n_sobre = int(dentro.sum())
    if not n_sobre:
        return [[_("sobreposição em CA"),
                 _("nenhum ponto experimental dentro da janela CFD — "
                   "verifique o alinhamento de fase")]]
    p_cf = np.interp(cae[dentro], ca, p)
    pd_ = pe[dentro]
    dif = p_cf - pd_
    imax_c = int(np.argmax(p))
    imax_e = int(np.argmax(pe))
    extra: List[List] = []
    wl_ca = res.get("wall_loss_ca_deg")
    wl_W = res.get("wall_loss_W")
    if wl_ca is not None and wl_W is not None and len(wl_ca) > 1 \
            and "wall_loss_J" in res:
        # perda às paredes acumulada ATÉ O PICO: calor perdido depois do
        # pico não corrige a pressão máxima anterior (escada de V&V).
        # wall_loss_W é potência [W] e wl_ca é ângulo [°CA]: a integral sai
        # em W·°CA e só vira joule dividindo pela velocidade angular
        # ω = 6·rpm [°/s] (6 = 360°/60 s).
        wl_ca = np.asarray(wl_ca, float)
        wl_W = np.asarray(wl_W, float)
        m_ate = wl_ca <= ca[imax_c]
        if wl_ca.size > 1 and m_ate.sum() > 1:
            l_tot = float(_integra(wl_W, wl_ca))          # W·°CA
            l_ate = float(_integra(wl_W[m_ate], wl_ca[m_ate]))
            omega = 6.0 * float(rpm) if rpm else 0.0          # °/s
            extra = [
                [_("perda às paredes: total na janela [J]"),
                 float(res["wall_loss_J"])],
            ]
            if omega > 0:
                extra.append(
                    [tf("perda às paredes acumulada até p_max "
                        "({ca:.1f}°) [J]", ca=ca[imax_c]), l_ate / omega])
                # conferência: a integral da potência deve reproduzir o
                # total do solver (mesma grandeza, caminhos diferentes)
                extra.append(
                    [_("conferência: integral da potência na janela [J]"),
                     l_tot / omega])
            else:
                extra.append(
                    [tf("perda às paredes acumulada até p_max ({ca:.1f}°) "
                        "[W·°CA] (rpm ausente: sem conversão para J)",
                        ca=ca[imax_c]), l_ate])
            extra.append([_("fração da perda antes do p_max [%]"),
                          float(100.0 * l_ate / l_tot) if l_tot
                          else float("nan")])
    return [
        [_("p_max CFD [kPa]"), float(p[imax_c])],
        [_("CA de p_max CFD [°]"), float(ca[imax_c])],
        [_("p_max experimental [kPa]"), float(pe[imax_e])],
        [_("CA de p_max experimental [°]"), float(cae[imax_e])],
        [_("erro de p_max (CFD − exp) [kPa]"),
         float(p[imax_c] - pe[imax_e])],
        [_("erro de fase de p_max [°]"),
         float(ca[imax_c] - cae[imax_e])],
        [_("pontos experimentais na janela CFD"), n_sobre],
        [_("diferença média (viés) [kPa]"), float(np.mean(dif))],
        [_("diferença média absoluta [kPa]"),
         float(np.mean(np.abs(dif)))],
        [_("RMSE na sobreposição [kPa]"),
         float(np.sqrt(np.mean(dif ** 2)))],
    ] + extra


# ------------------------------------------------------------- faixas (§6)
BANDAS_PADRAO = ((-120.0, -80.0), (-80.0, -40.0), (-40.0, -20.0),
                 (-20.0, -5.0), (-5.0, 0.0), (0.0, 5.0), (5.0, 20.0),
                 (20.0, 120.0))


def band_metrics(ca_cfd, p_cfd, ca_exp, p_exp,
                 bandas=BANDAS_PADRAO) -> List[Dict]:
    """RMSE/viés de p̄ CFD × p medida POR FAIXA ANGULAR (método do §6 —
    a análise antes existia só como narrativa no verification.md).

    Cada banda usa os pontos EXPERIMENTAIS dentro de [a, b] com p̄ do
    CFD interpolado nesses CA; CFD sem sobreposição numa banda aparece
    com n = 0 (nunca silencioso). Diagnóstico — não validação."""
    ca = np.asarray(ca_cfd, float)
    p = np.asarray(p_cfd, float)
    cae = np.asarray(ca_exp, float)
    pe = np.asarray(p_exp, float)
    ok = len(ca) and len(cae)
    saida = []
    # faixas meio-abertas [a, b), última inclusiva — cada ponto conta em
    # exatamente UMA banda (a soma dos n é a sobreposição total)
    for i, (a, b) in enumerate(bandas):
        linha = {"banda_deg": (a, b), "n": 0, "rmse_kPa": float("nan"),
                 "bias_kPa": float("nan"), "mae_kPa": float("nan")}
        if ok:
            m = (cae >= min(a, b)) & \
                ((cae < max(a, b)) if i < len(bandas) - 1
                 else (cae <= max(a, b)))
            linha["n"] = int(m.sum())
            if linha["n"]:
                pcf = np.interp(cae[m], ca, p)
                dif = pcf - pe[m]
                linha["rmse_kPa"] = float(np.sqrt(np.mean(dif ** 2)))
                linha["bias_kPa"] = float(np.mean(dif))
                linha["mae_kPa"] = float(np.mean(np.abs(dif)))
        saida.append(linha)
    return saida


def polytropic_bands(ca, p, V, bandas=BANDAS_PADRAO) -> List[Dict]:
    """n_eff por faixa: ajuste ln p = c − n·ln V (mínimos quadrados) nos
    pontos dentro de cada banda. Um DIP de n_eff no meio da compressão é
    a assinatura de crevice/blow-by (verification.md §3c item 7) — o
    ensaio mostra 1,324 → 1,284 → 1,366; o CFD com Rc geométrico
    constante não reproduz o dip."""
    ca = np.asarray(ca, float)
    p = np.asarray(p, float)
    V = np.asarray(V, float)
    ok = len(ca) == len(p) == len(V) and len(ca) > 2
    saida = []
    for a, b in bandas:
        linha = {"banda_deg": (a, b), "n_eff": float("nan"), "n_pts": 0}
        if ok:
            m = (ca >= min(a, b)) & (ca <= max(a, b)) & (p > 0) & (V > 0)
            linha["n_pts"] = int(m.sum())
            if linha["n_pts"] >= 3:
                x = np.log(V[m])
                y = np.log(p[m])
                if x.std() > 0:
                    linha["n_eff"] = float(-np.polyfit(x, y, 1)[0])
        saida.append(linha)
    return saida


def _tabela_bandas(bandas_res: List[Dict], col_metricas: bool) -> List[List]:
    linhas = []
    for b in bandas_res:
        a, bb = b["banda_deg"]
        if col_metricas:
            linhas.append([f"{a:g}…{bb:g}", b["n"], b["rmse_kPa"],
                           b["bias_kPa"], b["mae_kPa"]])
        else:
            linhas.append([f"{a:g}…{bb:g}", b["n_pts"], b["n_eff"]])
    return linhas


def _e(v) -> str:
    return html.escape(str(v))


def _fmt(v) -> str:
    if isinstance(v, (float, np.floating)):
        return "—" if not math.isfinite(v) else f"{v:.6g}"
    if isinstance(v, (bool, np.bool_)):
        return _("sim") if v else _("não")
    return _e(v)


def _tabela(cab: List[str], linhas, rotulos: bool = True) -> str:
    """Tabela traduzida: cabeçalho e PRIMEIRA coluna (os rótulos) com
    tradução registrada; as demais colunas trazem dados do caso, então
    usam a tradução branda (ts). ``rotulos=False`` para tabelas cuja
    primeira coluna também é dado (faixas angulares, etapas)."""
    h = ["<table><thead><tr>"] + [f"<th>{_e(_(c))}</th>" for c in cab]
    h.append("</tr></thead><tbody>")
    for l in linhas:
        celulas = [_fmt(rotulo(v) if rotulos and i == 0 else ts(v))
                   for i, v in enumerate(l)]
        h.append("<tr>" + "".join(f"<td>{c}</td>" for c in celulas)
                 + "</tr>")
    h.append("</tbody></table>")
    return "".join(h)


def _fig(curvas: List[Dict]) -> List[tuple]:
    """Gera figuras matplotlib → (título, base64). Sem seaborn, cores
    suaves; cada figura fecha ao sair."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    figs = []

    def add(fn, titulo):
        fig, ax = plt.subplots(figsize=(7.2, 4.0), dpi=110)
        fn(fig, ax)
        ax.set_facecolor("#fafbfd")
        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png")
        plt.close(fig)
        figs.append((titulo, base64.b64encode(buf.getvalue()).decode()))

    ca = bool(curvas.get("ca_deg") is not None
              and len(np.atleast_1d(curvas["ca_deg"])))

    if ca:
        x = curvas["ca_deg"]

        def p_theta(fig, ax):
            ax.plot(x, curvas["p_mean_kPa"], lw=2, color="#b4432f",
                    label=_("CFD (p̄ volumétrica)"))
            if curvas.get("exp_ca_deg") is not None:
                ax.plot(curvas["exp_ca_deg"], curvas["exp_p_kPa"], ".",
                        ms=3, color="#5b6475", label=_("experimental"))
                ax.legend(frameon=False)
            ax.set_xlabel(_("ângulo de manivela [°]"))
            ax.set_ylabel(_("pressão média volumétrica [kPa]"))
            ax.set_title(_("Pressão média volumétrica × ângulo"))
        add(p_theta, _("Pressão média volumétrica × ângulo de manivela"))

    if ca and "V_m3" in curvas:

        def pv(fig, ax):
            ax.plot(curvas["V_m3"] * 1e6, curvas["p_mean_kPa"], lw=2,
                    color="#b4432f", label=_("CFD (p̄ volumétrica)"))
            if curvas.get("exp_V_m3") is not None:
                ax.plot(np.asarray(curvas["exp_V_m3"], float) * 1e6,
                        curvas["exp_p_kPa"], ".", ms=3, color="#5b6475",
                        label=_("experimental"))
                ax.legend(frameon=False)
            ax.set_xlabel(_("volume do cilindro [cm³]"))
            ax.set_ylabel(_("pressão [kPa]"))
            ax.set_title(_("Diagrama P–V: CFD vs experimental"))
        add(pv, _("Diagrama P–V (CFD vs experimental)"))

    if "prescribed_Q_W" in curvas:

        def qdot(fig, ax):
            ax.plot(curvas["prescribed_ca_deg"],
                    curvas["prescribed_Q_W"] / 1e3, lw=2, color="#b4432f",
                    label=_("fonte Wiebe prescrita"))
            if "wall_loss_ca_deg" in curvas:
                ax.plot(curvas["wall_loss_ca_deg"],
                        curvas["wall_loss_W"] / 1e3, lw=1.5, ls="--",
                        color="#5b6475",
                        label=_("perda nas paredes (solver)"))
            ax.set_xlabel(_("ângulo de manivela [°]"))
            ax.set_ylabel(_("potência [kW]"))
            ax.legend(frameon=False)
            ax.set_title(_("Liberação de calor prescrita e perda de "
                           "calor"))
        add(qdot, _("Liberação de calor prescrita × perda nas paredes"))

    if "T_mean" in curvas:

        def temp(fig, ax):
            x = curvas["ca_deg"]
            ax.plot(x, curvas["T_mean"], lw=2, color="#b4432f",
                    label=_("T média"))
            if "T_max" in curvas:
                ax.plot(x, curvas["T_max"], lw=1.2, ls="--",
                        color="#c98a2b", label=_("T máxima"))
            ax.set_xlabel(_("ângulo de manivela [°]"))
            ax.set_ylabel(_("temperatura [K]"))
            ax.legend(frameon=False)
            ax.set_title(_("Temperatura média e máxima do gás"))
        add(temp, _("Temperatura média e máxima"))

    if "mass_kg" in curvas and "ca_deg" in curvas:

        def massa(fig, ax):
            ax.plot(curvas["ca_deg"], curvas["mass_kg"], lw=2,
                    color="#3f6f8f")
            ax.set_xlabel(_("ângulo de manivela [°]"))
            ax.set_ylabel(_("massa no cilindro [kg]"))
            ax.set_title(_("Balanço de massa (integral volumétrica de ρ)"))
        add(massa, _("Massa no cilindro × ângulo"))

    return figs


def report_html(case_dir, res: Dict, cfg: Optional[CfdConfig] = None,
                exp: Optional[Dict] = None,
                run_summary: Optional[Dict] = None,
                exp_data: Optional[Dict] = None,
                engine=None, lang: Optional[str] = None) -> str:
    """Relatório HTML do caso. ``res`` = read_results(...);
    ``exp_data`` = dict com ca_deg/p_kPa experimentais (opcional; quando
    ausente, tentado de comparison.experimental em case_config.yaml).
    ``lang`` fixa o idioma; ``None`` usa o corrente (o da interface,
    quando gerado por ela)."""
    with idioma_fixo(lang):
        return _corpo(case_dir, res, cfg, exp, run_summary, exp_data,
                      engine)


def _corpo(case_dir, res: Dict, cfg: Optional[CfdConfig] = None,
           exp: Optional[Dict] = None,
           run_summary: Optional[Dict] = None,
           exp_data: Optional[Dict] = None, engine=None) -> str:
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
    solver = info.get("solver") or {}
    fuel = info.get("fuel") or {}
    hs = info.get("heat_source") or {}
    motion = info.get("motion") or {}
    intervalo = info.get("interval") or {}
    cfgd = info.get("configuration") or {}
    turb = info.get("turbulence") or {}
    gas = info.get("gas_model") or {}

    partes: List[str] = []
    a = partes.append
    a("<h1>" + tf("wiebepy CFD — Relatório do caso ({caso})",
                  caso=_e(case_dir.name)) + "</h1>")
    a("<p class='sub'>"
      + tf("Simulação 3D da combustão em um cilindro simplificado: a "
           "liberação de calor da combustão segue a função Wiebe "
           "calibrada no ensaio (modo {modo}), e o solver calcula o "
           "escoamento, a pressão, as temperaturas e a troca de calor "
           "nas paredes. A taxa de queima é a da Wiebe; cinética "
           "química e frente de chama não são resolvidas (ver <i>Modo "
           "físico e escopo</i>).",
           modo=_e(info.get("mode", "prescribed_wiebe"))) + "</p>")

    a("<h2>" + _("Identificação e proveniência") + "</h2>")
    a(_tabela(["Item", "Valor"], [
        ["diretório do caso", str(case_dir.resolve())],
        ["criado em", info.get("created", "—")],
        ["relatório gerado em", datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S")],
        ["wiebepy", info.get("wiebepy_version", "—")],
        ["estado do caso", _(estado.label)],
        ["configuração efetiva",
         _("case_config.yaml (salva com o caso)")],
    ]))

    a("<h2>" + _("Solver e adapter") + "</h2>")
    a(_tabela(["Item", "Valor"], [
        ["solver", "OpenFOAM Foundation"],
        ["versão", solver.get("version", "—")],
        ["instalação", solver.get("root", "—")],
        ["foamRun", solver.get("foamRun", "—")],
        ["adapter", cfgd.get("adapter", "openfoam")],
        ["paralelismo do solver",
         tf("{n} processo(s) (MPI; distinto dos backends do wiebepy)",
            n=cfgd.get("workers", 1))],
    ]))

    a("<h2>" + _("Modo físico e escopo") + "</h2>")
    a("<p class='nota'>" + _e(ts(hs.get("notice") or distribution_notice(
        cfgd.get("heat_source", {}).get("distribution", "uniform"))))
      + "</p>")
    a("<ul><li>"
      + _("Não são previstos: cinética química, frente de chama, "
          "emissões.") + "</li><li>"
      + _("A fonte de calor é a curva Wiebe calibrada declarada abaixo "
          "(origem experimental/documental do caso).") + "</li></ul>")

    a("<h2>" + _("Combustível e propriedades") + "</h2>")
    a(_tabela(["Item", "Valor"], [
        ["combustível", fuel.get("display")],
        ["composição/formula", fuel.get("formula")],
        ["fase", fuel.get("phase")],
        ["alimentação", fuel.get("feed")],
        ["PCI (LHV) usado na fonte",
         f"{fuel.get('LHV_kJ_per_kg_engine', fuel.get('LHV_kJ_per_kg'))}"
         " kJ/kg"],
        ["PCI de referência do registro", f"{fuel.get('LHV_kJ_per_kg')} kJ/kg"],
        ["fonte do PCI", fuel.get("LHV_source")],
        ["massa por ciclo", f"{fuel.get('m_fuel_kg_per_cycle')} kg"],
        ["energia por ciclo (m_f·PCI do ensaio)",
         f"{fuel.get('m_fuel_kg_per_cycle', 0) * 1e3 * fuel.get('LHV_kJ_per_kg_engine', fuel.get('LHV_kJ_per_kg', 0)):.1f} J"],
        ["mecanismo químico", fuel.get("mechanism")
         or _("— (não aplicável ao modo prescrito)")],
        ["limitações", fuel.get("validity")],
    ]))
    if fuel.get("notice"):
        # o aviso do PCI traz números: refaz a frase a partir dos valores
        # gravados, para sair no idioma do relatório (e não no do preparo)
        if fuel.get("LHV_kJ_per_kg_engine") is not None:
            aviso = tf(
                "O PCI usado na fonte de calor é o do combustível DO ENSAIO "
                "({usado:.1f} kJ/kg, seção engine); a referência típica do "
                "registro é {ref:.1f} kJ/kg (substituir pela "
                "ficha/certificado do combustível real). No modo prescrito o "
                "combustível entra apenas via m_f·PCI; a "
                "composição/surrogate só é relevante no modo reativo (não "
                "implementado).",
                usado=float(fuel["LHV_kJ_per_kg_engine"]),
                ref=float(fuel.get("LHV_kJ_per_kg", float("nan"))))
        else:
            aviso = ts(fuel["notice"])
        a("<p class='nota'>" + _e(aviso) + "</p>")

    a("<h2>" + _("Geometria e movimento do pistão") + "</h2>")
    a(_tabela(["Grandeza", "Valor"], [
        ["diâmetro [mm]", (info.get("engine") or {}).get("bore", 0) * 1e3],
        ["curso [mm]", (info.get("engine") or {}).get("stroke", 0) * 1e3],
        ["biela [mm]", (info.get("engine") or {}).get("rod_length", 0)
         * 1e3],
        ["rotação [rpm]", motion.get("rpm")],
        ["janela simulada [° CA]", f"{intervalo.get('start')} … "
                                   f"{intervalo.get('end')}"],
        ["volume inicial [cm³]", motion.get("V_start_m3", 0) * 1e6],
        ["volume final [cm³]", motion.get("V_end_m3", 0) * 1e6],
        ["volume mínimo [cm³]", motion.get("V_min_m3", 0) * 1e6],
        ["volume máximo [cm³]", motion.get("V_max_m3", 0) * 1e6],
        ["malha",
         tf("cilindro simplificado {nr}×{nr}×{na} células (blockMesh)",
            nr=(cfgd.get("geometry") or {}).get("n_radial"),
            na=(cfgd.get("geometry") or {}).get("n_axial"))],
        ["pistão móvel", bool(motion)],
    ]))
    for h in motion.get("hypotheses", []):
        a("<p class='nota'>" + _("Hipótese") + f": {_e(ts(h))}</p>")
    a("<p class='nota'>"
      + _("Qualidade da malha durante o movimento: a malha deforma-se "
          "entre pistão e cabeçote (mover multiValveEngine); avalie "
          "checkMesh em cada tempo para casos sensíveis.") + "</p>")

    a("<h2>" + _("Condições iniciais e de contorno") + "</h2>")
    ic = info.get("initial_conditions") or {}
    a(_tabela(["Condição", "Valor"], [
        ["pressão inicial [Pa]", ic.get("P_Pa")],
        ["temperatura inicial [K]", ic.get("T_K")],
        ["velocidade inicial", _("repouso (0, 0, 0)")],
        ["paredes", info.get("walls")],
        ["turbulência", turb],
        ["modelo de gás", gas],
    ]))

    a("<h2>" + _("Fonte Wiebe e distribuição espacial") + "</h2>")
    a(_tabela(["estágio", "β [-]", "θ0 [°]", "Δθ [°]", "m [-]", "a [-]"],
              [[j, st.get("beta"), math.degrees(st.get("theta0", 0.0)),
                math.degrees(st.get("duration", 0.0)), st.get("m"),
                st.get("a")]
               for j, st in enumerate(info.get("wiebe_stages") or [],
                                     start=1)]))
    chk = hs.get("energy_check") or {}
    a(_tabela(["Verificação da fonte", "Valor"], [
        ["energia integrada ∫Q̇dt [J]", hs.get("energy_check", {})
         .get("integral_J")],
        ["energia esperada m_f·PCI·Δx_b [J]",
         (hs.get("energy_check") or {}).get("integral_J")
         and (hs.get("energy_check") or {}).get("integral_J")],
        ["erro relativo", (hs.get("energy_check") or {}).get("rel_error")],
        ["distribuição espacial", hs.get("distribution")],
        ["região (cellZone)", hs.get("region") or "—"],
    ]))
    a("<p class='nota'>" + _e(ts(hs.get("notice") or "")) + "</p>")
    a("<p class='nota'>"
      + _("Na malha discreta a normalização Σᵢ q'''ᵢ·Vᵢ = Q̇ é feita "
          "pelo fvModel heatSource do solver sobre os volumes atuais "
          "(correta com malha móvel e em paralelo). A energia é aplicada "
          "UMA única vez — não há sobreposição com reações químicas "
          "neste modo.") + "</p>")

    a("<h2>" + _("Configuração numérica") + "</h2>")
    a(_tabela(["Item", "Valor"], [
        ["tempo do solver", _("ângulo de manivela (userTime engine)")],
        ["passo inicial Δt [° CA]", 0.01],
        ["passo máximo [° CA]", 0.5],
        ["máx. Courant", (info.get("numerics") or {}).get("max_Co")],
        ["intervalo de gravação [° CA]",
         (cfgd.get("numerics") or {}).get("write_interval_deg")],
        ["esquema temporal", _("Euler (implícito)")],
        ["esquemas espaciais",
         _("upwind (U, h), linear (laplacianos)")],
    ]))

    if run_summary:
        a("<h2>" + _("Execução e hardware") + "</h2>")
        etapas = run_summary.get("steps") or []
        a(_tabela(["etapa", "código de saída", "tempo [s]", "log"],
                  [[s.get("step"), s.get("returncode"), s.get("elapsed_s"),
                    s.get("log")] for s in etapas], rotulos=False))
        a("<p class='nota'>"
          + tf("Tempo total: {s} s; workers (MPI): {w}. Números de "
               "recursos aqui são os efetivamente usados nesta máquina — "
               "não são estimativas.", s=run_summary.get("elapsed_s"),
               w=run_summary.get("workers")) + "</p>")

    # --------------------------------------------- dados experimentais
    if exp_data is None and exp is None:
        exp_data = load_exp_data(case_dir, engine=engine)

    a("<h2>" + _("Balanços e curvas") + "</h2>")
    linhas = []
    if "indicated_work_J" in res:
        linhas.append([_("trabalho indicado na janela [J]"),
                       res["indicated_work_J"]])
    if "wall_loss_J" in res:
        linhas.append([_("energia perdida nas paredes [J]"),
                       res["wall_loss_J"]])
    if "prescribed_Q_J" in res:
        linhas.append([_("energia prescrita pela Wiebe [J]"),
                       res["prescribed_Q_J"]])
    if "mass_kg" in res and len(res["mass_kg"]):
        linhas.append([_("massa inicial/final [kg]"),
                       (float(res["mass_kg"][0]),
                        float(res["mass_kg"][-1]))])
    a(_tabela(["Grandeza", "Valor"], linhas) if linhas
      else "<p>" + _("Sem resultados numéricos disponíveis.") + "</p>")
    a("<p class='nota'>"
      + _("Pressão média volumétrica ≠ pressão em sonda ≠ pressão "
          "medida: esta versão reporta apenas a média volumétrica do "
          "cilindro; sondas numéricas próximas ao sensor experimental "
          "são uma extensão futura.") + "</p>")

    if exp_data:
        a("<h2>" + _("Comparação experimental") + "</h2>")
        a("<p class='nota'>"
          + _("A comparação abaixo é INDICATIVA: pressão média "
              "volumétrica (CFD) vs pressão medida no sensor. A "
              "comparação é DIAGNÓSTICA, não validação do modo "
              "prescrito: a liberação de calor foi imposta a partir da "
              "calibração que já usa estes dados.") + "</p>")
        pk = exp_data.get("p_kPa")
        linhas_exp = [[_("arquivo experimental"),
                       exp_data.get("source", "—")],
                      [_("pontos"), int(np.asarray(pk).size)
                       if pk is not None else 0],
                      [_("unidades declaradas"), _e(", ".join(
                          f"{k}: {v}" for k, v in
                          (exp_data.get("units") or {}).items()))
                          or _("θ: rad, P: kPa (padrão)")],
                      [_("alinhamento de fase declarado [°CA]"),
                       float(exp_data.get("offset_deg") or 0.0)]]
        if exp_data.get("erro"):
            linhas_exp.append([_("erro"), ts(exp_data["erro"])])
        if exp_data.get("warnings"):
            linhas_exp.append([_("avisos do leitor"),
                               " | ".join(exp_data["warnings"])])
        a(_tabela(["Item", "Valor"], linhas_exp))
        if exp_data.get("erro"):
            a("<p class='nota'>"
              + _("As comparações abaixo estão ausentes por causa do erro "
                  "acima — nenhuma substituição silenciosa foi feita.")
              + "</p>")
        else:
            met = _metricas_experimental(res, exp_data,
                                         (motion or {}).get("rpm"))
            if met:
                a("<h3>" + _("Métricas p̄ CFD × p medida") + "</h3>")
                a(_tabela(["Métrica", "Valor"], met))
                a("<p class='nota'>"
                  + _("Diferenças calculadas por interpolação linear de "
                      "p̄(θ) do CFD nos pontos experimentais, somente "
                      "dentro da janela simulada. Pressão média "
                      "volumétrica ≠ pressão medida no sensor "
                      "(posicionamento do sensor, cavitação, defasagem "
                      "de aquisição).") + "</p>")
            # faixas angulares (§6): RMSE por banda + n_eff politrópico
            def _serie(k):
                v = res.get(k)
                return v if v is not None and len(v) else []

            def _serie_exp(k):
                v = exp_data.get(k)
                return v if v is not None and len(v) else []
            bm_ = band_metrics(_serie("ca_deg"), _serie("p_mean_kPa"),
                               _serie_exp("ca_deg"), _serie_exp("p_kPa"))
            a("<h3>" + _("RMSE por faixa angular") + "</h3>")
            a(_tabela(["Faixa [° CA]", "n (exp)", "RMSE [kPa]",
                       "viés [kPa]", "MAE [kPa]"],
                      _tabela_bandas(bm_, col_metricas=True),
                      rotulos=False))
            a("<p class='nota'>"
              + _("Comparação DIAGNÓSTICA por faixa — nenhuma calibração "
                  "silenciosa; banda sem pontos experimentais aparece "
                  "com n = 0.") + "</p>")
            if exp_data.get("V_m3") is not None \
                    and res.get("V_m3") is not None:
                n_exp = polytropic_bands(exp_data["ca_deg"],
                                         exp_data["p_kPa"],
                                         exp_data["V_m3"])
                n_cfd = polytropic_bands(res["ca_deg"], res["p_mean_kPa"],
                                         res["V_m3"])
                a("<h3>" + _("n_eff politrópico por faixa (ensaio × CFD)")
                  + "</h3>")
                lin_n = []
                for be, bc in zip(n_exp, n_cfd):
                    lin_n.append([f"{be['banda_deg'][0]:g}…"
                                  f"{be['banda_deg'][1]:g}",
                                  be["n_eff"], bc["n_eff"]])
                a(_tabela(["Faixa [° CA]", "n_eff ensaio", "n_eff CFD"],
                          lin_n, rotulos=False))
                a("<p class='nota'>"
                  + _("Dip de n_eff no meio da compressão é assinatura de "
                      "crevice/blow-by (gás armazenado na folga da "
                      "segmentação). O CFD com Rc geométrico constante "
                      "tende a NÃO reproduzir o dip — comparação "
                      "diagnóstica, nunca validação.") + "</p>")
            else:
                a("<p class='nota'>"
                  + _("Sem métricas: as séries não se sobrepõem em "
                      "ângulo de manivela.") + "</p>")

    # ------------------------------------------------- comparação exp. (fig)
    curvas = dict(res)
    if exp_data and exp_data.get("ca_deg") is not None:
        curvas["exp_ca_deg"] = exp_data["ca_deg"]
        curvas["exp_p_kPa"] = exp_data["p_kPa"]
        curvas["exp_V_m3"] = exp_data.get("V_m3")

    a("<h2>" + _("Avisos e limitações científicas") + "</h2>")
    a("<ul class='avisos'>"
      + "".join(f"<li>{_e(_(w))}</li>" for w in _LIM) + "</ul>")

    # --------------------------------------- curvas p/ gráficos (com exp.)
    curvas = dict(res)
    if exp_data and exp_data.get("ca_deg") is not None:
        curvas["exp_ca_deg"] = exp_data["ca_deg"]
        curvas["exp_p_kPa"] = exp_data["p_kPa"]
        curvas["exp_V_m3"] = exp_data.get("V_m3")

    a("<h2>" + _("Gráficos") + "</h2>")
    for titulo, b64 in _fig(curvas):
        a(f"<figure><figcaption>{_e(titulo)}</figcaption>"
          f"<img src='data:image/png;base64,{b64}' "
          f"alt='{_e(titulo)}'></figure>")

    a("<h2>" + _("Campos 3D e exportação") + "</h2>")
    from .results import time_directories
    tempos = time_directories(case_dir)
    a("<p>" + tf("Diretórios de tempo com campos 3D (formato nativo do "
                 "solver): {lista}",
                 lista=_e(", ".join(tempos[:20]) or _("nenhum")))
      + (" …" if len(tempos) > 20 else "") + ".</p>")
    a("<p class='nota'>"
      + _("Pós-processamento externo (ParaView) pode abrir os formatos "
          "nativos diretamente; a exportação VTK opcional usa "
          "foamToVTK.") + "</p>")

    css = (
        "body{font-family:'Segoe UI',Arial,sans-serif;margin:24px auto;"
        "max-width:1000px;padding:0 16px;color:#1d2330;background:#fff}"
        "h1{font-size:24px;margin-bottom:4px}h2{font-size:18px;"
        "margin-top:28px;border-bottom:2px solid #b4432f;padding-bottom:3px}"
        ".sub{color:#5b6475;font-style:italic}.nota{color:#5b6475;"
        "font-size:13px}"
        "table{border-collapse:collapse;font-size:13px;margin:8px 0;"
        "width:100%}th,td{border:1px solid #e3e6ee;padding:4px 8px;"
        "text-align:left}th{background:#f1f3f8}"
        "tr:nth-child(even) td{background:#fafbfd}"
        ".avisos li{color:#9a6500}figure{margin:18px 0}"
        "figcaption{font-weight:600;margin-bottom:6px}img{max-width:100%;"
        "border:1px solid #e3e6ee;border-radius:6px}"
        "@media print{h2{page-break-after:avoid}"
        "figure{page-break-inside:avoid}}")
    lang_html = "pt-BR" if idioma() == "pt" else "en"
    titulo = _("wiebepy CFD — Relatório do caso")
    return (f"<!DOCTYPE html><html lang='{lang_html}'>"
            "<head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,"
            f"initial-scale=1'><title>{_e(titulo)}"
            f"</title><style>{css}</style></head><body>"
            + "".join(partes) + "</body></html>")


def write_report(case_dir, res: Dict, cfg: Optional[CfdConfig] = None,
                 **kw) -> Path:
    """Gera e grava <case>/report.html."""
    h = report_html(case_dir, res, cfg=cfg, **kw)
    p = Path(case_dir) / "report.html"
    p.write_text(h, encoding="utf-8")
    return p


__all__ = ["report_html", "write_report"]