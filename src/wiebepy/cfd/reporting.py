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
        V, _, _ = volume(np.radians(ca_deg - offset), engine.Rc, engine)
        out["V_m3"] = np.asarray(V, float)
    return out


def _yaml_load(p: Path) -> Dict:
    import yaml
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def _metricas_experimental(res: Dict, exp: Dict) -> List[List]:
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
        return [["sobreposição em CA", "nenhum ponto experimental dentro "
                                       "da janela CFD — verifique o "
                                       "alinhamento de fase"]]
    p_cf = np.interp(cae[dentro], ca, p)
    pd_ = pe[dentro]
    dif = p_cf - pd_
    imax_c = int(np.argmax(p))
    imax_e = int(np.argmax(pe))
    return [
        ["p_max CFD [kPa]", float(p[imax_c])],
        ["CA de p_max CFD [°]", float(ca[imax_c])],
        ["p_max experimental [kPa]", float(pe[imax_e])],
        ["CA de p_max experimental [°]", float(cae[imax_e])],
        ["erro de p_max (CFD − exp) [kPa]", float(p[imax_c] - pe[imax_e])],
        ["erro de fase de p_max [°]", float(ca[imax_c] - cae[imax_e])],
        ["pontos experimentais na janela CFD", n_sobre],
        ["diferença média (viés) [kPa]", float(np.mean(dif))],
        ["diferença média absoluta [kPa]", float(np.mean(np.abs(dif)))],
        ["RMSE na sobreposição [kPa]", float(np.sqrt(np.mean(dif ** 2)))],
    ]


def _e(v) -> str:
    return html.escape(str(v))


def _fmt(v) -> str:
    if isinstance(v, (float, np.floating)):
        return "—" if not math.isfinite(v) else f"{v:.6g}"
    if isinstance(v, (bool, np.bool_)):
        return "sim" if v else "não"
    return _e(v)


def _tabela(cab: List[str], linhas) -> str:
    h = ["<table><thead><tr>"] + [f"<th>{_e(c)}</th>" for c in cab]
    h.append("</tr></thead><tbody>")
    for l in linhas:
        h.append("<tr>" + "".join(f"<td>{_fmt(v)}</td>" for v in l)
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
                    label="CFD (p̄ volumétrica)")
            if curvas.get("exp_ca_deg") is not None:
                ax.plot(curvas["exp_ca_deg"], curvas["exp_p_kPa"], ".",
                        ms=3, color="#5b6475", label="experimental")
                ax.legend(frameon=False)
            ax.set_xlabel("ângulo de manivela [°]")
            ax.set_ylabel("pressão média volumétrica [kPa]")
            ax.set_title("Pressão média volumétrica × ângulo")
        add(p_theta, "Pressão média volumétrica × ângulo de manivela")

    if ca and "V_m3" in curvas:

        def pv(fig, ax):
            ax.plot(curvas["V_m3"] * 1e6, curvas["p_mean_kPa"], lw=2,
                    color="#b4432f", label="CFD (p̄ volumétrica)")
            if curvas.get("exp_V_m3") is not None:
                ax.plot(np.asarray(curvas["exp_V_m3"], float) * 1e6,
                        curvas["exp_p_kPa"], ".", ms=3, color="#5b6475",
                        label="experimental")
                ax.legend(frameon=False)
            ax.set_xlabel("volume do cilindro [cm³]")
            ax.set_ylabel("pressão [kPa]")
            ax.set_title("Diagrama P–V: CFD vs experimental")
        add(pv, "Diagrama P–V (CFD vs experimental)")

    if "prescribed_Q_W" in curvas:

        def qdot(fig, ax):
            ax.plot(curvas["prescribed_ca_deg"],
                    curvas["prescribed_Q_W"] / 1e3, lw=2, color="#b4432f",
                    label="fonte Wiebe prescrita")
            if "wall_loss_ca_deg" in curvas:
                ax.plot(curvas["wall_loss_ca_deg"],
                        curvas["wall_loss_W"] / 1e3, lw=1.5, ls="--",
                        color="#5b6475",
                        label="perda nas paredes (solver)")
            ax.set_xlabel("ângulo de manivela [°]")
            ax.set_ylabel("potência [kW]")
            ax.legend(frameon=False)
            ax.set_title("Liberação de calor prescrita e perda de calor")
        add(qdot, "Liberação de calor prescrita × perda nas paredes")

    if "T_mean" in curvas:

        def temp(fig, ax):
            x = curvas["ca_deg"]
            ax.plot(x, curvas["T_mean"], lw=2, color="#b4432f",
                    label="T média")
            if "T_max" in curvas:
                ax.plot(x, curvas["T_max"], lw=1.2, ls="--",
                        color="#c98a2b", label="T máxima")
            ax.set_xlabel("ângulo de manivela [°]")
            ax.set_ylabel("temperatura [K]")
            ax.legend(frameon=False)
            ax.set_title("Temperatura média e máxima do gás")
        add(temp, "Temperatura média e máxima")

    if "mass_kg" in curvas and "ca_deg" in curvas:

        def massa(fig, ax):
            ax.plot(curvas["ca_deg"], curvas["mass_kg"], lw=2,
                    color="#3f6f8f")
            ax.set_xlabel("ângulo de manivela [°]")
            ax.set_ylabel("massa no cilindro [kg]")
            ax.set_title("Balanço de massa (integral volumétrica de ρ)")
        add(massa, "Massa no cilindro × ângulo")

    return figs


def report_html(case_dir, res: Dict, cfg: Optional[CfdConfig] = None,
                exp: Optional[Dict] = None,
                run_summary: Optional[Dict] = None,
                exp_data: Optional[Dict] = None,
                engine=None) -> str:
    """Relatório HTML do caso. ``res`` = read_results(...);
    ``exp_data`` = dict com ca_deg/p_kPa experimentais (opcional; quando
    ausente, tentado de comparison.experimental em case_config.yaml)."""
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
    a("<h1>wiebepy CFD — Relatório do caso "
      f"({_e(case_dir.name)})</h1>")
    a("<p class='sub'>Simulação 3D do escoamento e da energia em um "
      "cilindro simplificado com liberação de calor global prescrita pela "
      "função Wiebe calibrada (modo "
      f"{_e(info.get('mode', 'prescribed_wiebe'))}). <b>Este relatório "
      "NÃO apresenta previsões independentes de combustão</b>: a liberação "
      "de calor foi imposta; o solver responde ao escoamento, à pressão e "
      "às temperaturas.</p>")

    a("<h2>Identificação e proveniência</h2>")
    a(_tabela(["Item", "Valor"], [
        ["diretório do caso", str(case_dir.resolve())],
        ["criado em", info.get("created", "—")],
        ["relatório gerado em", datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S")],
        ["wiebepy", info.get("wiebepy_version", "—")],
        ["estado do caso", estado.label],
        ["configuração efetiva", "case_config.yaml (salva com o caso)"],
    ]))

    a("<h2>Solver e adapter</h2>")
    a(_tabela(["Item", "Valor"], [
        ["solver", "OpenFOAM Foundation"],
        ["versão", solver.get("version", "—")],
        ["instalação", solver.get("root", "—")],
        ["foamRun", solver.get("foamRun", "—")],
        ["adapter", cfgd.get("adapter", "openfoam")],
        ["paralelismo do solver",
         f"{cfgd.get('workers', 1)} processo(s) (MPI; distinto dos "
         "backends do wiebepy)"],
    ]))

    a("<h2>Modo físico e escopo</h2>")
    a("<p class='nota'>" + _e(hs.get("notice") or distribution_notice(
        cfgd.get("heat_source", {}).get("distribution", "uniform")))
      + "</p>")
    a("<ul><li>Não são previstos: cinética química, frente de chama, "
      "emissões.</li><li>A fonte de calor é a curva Wiebe calibrada "
      "declarada abaixo (origem experimental/documental do caso).</li>"
      "</ul>")

    a("<h2>Combustível e propriedades</h2>")
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
         or "— (não aplicável ao modo prescrito)"],
        ["limitações", fuel.get("validity")],
    ]))
    if fuel.get("notice"):
        a(f"<p class='nota'>{fuel['notice']}</p>")

    a("<h2>Geometria e movimento do pistão</h2>")
    a(_tabela(["Grandeza", "Valor"], [
        ["diâmetro [mm]", (info.get("engine") or {}).get("bore", 0) * 1e3],
        ["curso [mm]", (info.get("engine") or {}).get("stroke", 0) * 1e3],
        ["biela [mm]", (info.get("engine") or {}).get("rod_length", 0)
         * 1e3],
        ["rotação [rpm]", motion.get("rpm")],
        ["janela simulada [° CA]", f"{intervalo.get('start')} a "
                                   f"{intervalo.get('end')}"],
        ["volume inicial [cm³]", motion.get("V_start_m3", 0) * 1e6],
        ["volume final [cm³]", motion.get("V_end_m3", 0) * 1e6],
        ["volume mínimo [cm³]", motion.get("V_min_m3", 0) * 1e6],
        ["volume máximo [cm³]", motion.get("V_max_m3", 0) * 1e6],
        ["malha", f"cilindro simplificado "
                  f"{(cfgd.get('geometry') or {}).get('n_radial')}×"
                  f"{(cfgd.get('geometry') or {}).get('n_radial')}×"
                  f"{(cfgd.get('geometry') or {}).get('n_axial')} células "
                  "(blockMesh)"],
        ["pistão móvel", bool(motion)],
    ]))
    for h in motion.get("hypotheses", []):
        a(f"<p class='nota'>Hipótese: {_e(h)}</p>")
    a("<p class='nota'>Qualidade da malha durante o movimento: a malha "
      "deforma-se entre pistão e cabeçote (mover multiValveEngine); "
      "avalie checkMesh em cada tempo para casos sensíveis.</p>")

    a("<h2>Condições iniciais e de contorno</h2>")
    ic = info.get("initial_conditions") or {}
    a(_tabela(["Condição", "Valor"], [
        ["pressão inicial [Pa]", ic.get("P_Pa")],
        ["temperatura inicial [K]", ic.get("T_K")],
        ["velocidade inicial", "repouso (0, 0, 0)"],
        ["paredes", info.get("walls")],
        ["turbulência", turb],
        ["modelo de gás", gas],
    ]))

    a("<h2>Fonte Wiebe e distribuição espacial</h2>")
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
    a("<p class='nota'>" + _e(hs.get("notice") or "") + "</p>")
    a("<p class='nota'>Na malha discreta a normalização Σᵢ q'''ᵢ·Vᵢ = Q̇ é "
      "feita pelo fvModel heatSource do solver sobre os volumes atuais "
      "(correta com malha móvel e em paralelo). A energia é aplicada UMA "
      "única vez — não há sobreposição com reações químicas neste "
      "modo.</p>")

    a("<h2>Configuração numérica</h2>")
    a(_tabela(["Item", "Valor"], [
        ["tempo do solver", "ângulo de manivela (userTime engine)"],
        ["passo inicial Δt [° CA]", 0.01],
        ["passo máximo [° CA]", 0.5],
        ["máx. Courant", (info.get("numerics") or {}).get("max_Co")],
        ["intervalo de gravação [° CA]",
         (cfgd.get("numerics") or {}).get("write_interval_deg")],
        ["esquema temporal", "Euler (implícito)"],
        ["esquemas espaciais", "upwind (U, h), linear (laplacianos)"],
    ]))

    if run_summary:
        a("<h2>Execução e hardware</h2>")
        etapas = run_summary.get("steps") or []
        a(_tabela(["etapa", "código de saída", "tempo [s]", "log"],
                  [[s.get("step"), s.get("returncode"), s.get("elapsed_s"),
                    s.get("log")] for s in etapas]))
        a(f"<p class='nota'>Tempo total: {run_summary.get('elapsed_s')} s; "
          f"workers (MPI): {run_summary.get('workers')}. Números de "
          "recursos aqui são os efetivamente usados nesta máquina — não "
          "são estimativas.</p>")

    # --------------------------------------------- dados experimentais
    if exp_data is None and exp is None:
        exp_data = load_exp_data(case_dir, engine=engine)

    a("<h2>Balanços e curvas</h2>")
    linhas = []
    if "indicated_work_J" in res:
        linhas.append(["trabalho indicado na janela [J]",
                       res["indicated_work_J"]])
    if "wall_loss_J" in res:
        linhas.append(["energia perdida nas paredes [J]", res["wall_loss_J"]])
    if "prescribed_Q_J" in res:
        linhas.append(["energia prescrita pela Wiebe [J]",
                       res["prescribed_Q_J"]])
    if "mass_kg" in res and len(res["mass_kg"]):
        linhas.append(["massa inicial/final [kg]",
                       (float(res["mass_kg"][0]),
                        float(res["mass_kg"][-1]))])
    a(_tabela(["Grandeza", "Valor"], linhas) if linhas
      else "<p>Sem resultados numéricos disponíveis.</p>")
    a("<p class='nota'>Pressão média volumétrica ≠ pressão em sonda ≠ "
      "pressão medida: esta versão reporta apenas a média volumétrica do "
      "cilindro; sondas numéricas próximas ao sensor experimental são uma "
      "extensão futura.</p>")

    if exp_data:
        a("<h2>Comparação experimental</h2>")
        a("<p class='nota'>A comparação abaixo é INDICATIVA: pressão média "
          "volumétrica (CFD) vs pressão medida no sensor. A comparação é "
          "DIAGNÓSTICA, não validação do modo prescrito: a liberação de "
          "calor foi imposta a partir da calibração que já usa estes "
          "dados.</p>")
        pk = exp_data.get("p_kPa")
        linhas_exp = [["arquivo experimental", exp_data.get("source", "—")],
                      ["pontos", int(np.asarray(pk).size) if pk is not None
                       else 0],
                      ["unidades declaradas", _e(", ".join(
                          f"{k}: {v}" for k, v in
                          (exp_data.get("units") or {}).items()))
                          or "θ: rad, P: kPa (padrão)"],
                      ["alinhamento de fase declarado [°CA]",
                       float(exp_data.get("offset_deg") or 0.0)]]
        if exp_data.get("erro"):
            linhas_exp.append(["erro", exp_data["erro"]])
        if exp_data.get("warnings"):
            linhas_exp.append(["avisos do leitor",
                               " | ".join(exp_data["warnings"])])
        a(_tabela(["Item", "Valor"], linhas_exp))
        if exp_data.get("erro"):
            a("<p class='nota'>As comparações abaixo estão ausentes por "
              "causa do erro acima — nenhuma substituição silenciosa foi "
              "feita.</p>")
        else:
            met = _metricas_experimental(res, exp_data)
            if met:
                a("<h3>Métricas p̄ CFD × p medida</h3>")
                a(_tabela(["Métrica", "Valor"], met))
                a("<p class='nota'>Diferenças calculadas por interpolação "
                  "linear de p̄(θ) do CFD nos pontos experimentais, "
                  "somente dentro da janela simulada. Pressão média "
                  "volumétrica ≠ pressão medida no sensor (posicionamento "
                  "do sensor, cavitação, defasagem de aquisição).</p>")
            else:
                a("<p class='nota'>Sem métricas: as séries não se "
                  "sobrepõem em ângulo de manivela.</p>")

    # ------------------------------------------------- comparação exp. (fig)
    curvas = dict(res)
    if exp_data and exp_data.get("ca_deg") is not None:
        curvas["exp_ca_deg"] = exp_data["ca_deg"]
        curvas["exp_p_kPa"] = exp_data["p_kPa"]
        curvas["exp_V_m3"] = exp_data.get("V_m3")

    a("<h2>Avisos e limitações científicas</h2>")
    a("<ul class='avisos'>"
      + "".join(f"<li>{_e(w)}</li>" for w in _LIM) + "</ul>")

    # --------------------------------------- curvas p/ gráficos (com exp.)
    curvas = dict(res)
    if exp_data and exp_data.get("ca_deg") is not None:
        curvas["exp_ca_deg"] = exp_data["ca_deg"]
        curvas["exp_p_kPa"] = exp_data["p_kPa"]
        curvas["exp_V_m3"] = exp_data.get("V_m3")

    a("<h2>Gráficos</h2>")
    for titulo, b64 in _fig(curvas):
        a(f"<figure><figcaption>{_e(titulo)}</figcaption>"
          f"<img src='data:image/png;base64,{b64}' "
          f"alt='{_e(titulo)}'></figure>")

    a("<h2>Campos 3D e exportação</h2>")
    from .results import time_directories
    tempos = time_directories(case_dir)
    a(f"<p>Diretórios de tempo com campos 3D (formato nativo do solver): "
      f"{_e(', '.join(tempos[:20]) or 'nenhum')}"
      + (" …" if len(tempos) > 20 else "") + ".</p>")
    a("<p class='nota'>Pós-processamento externo (ParaView) pode abrir os "
      "formatos nativos diretamente; a exportação VTK opcional usa "
      "foamToVTK.</p>")

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
    return ("<!DOCTYPE html><html lang='pt-BR'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,"
            "initial-scale=1'><title>wiebepy CFD — Relatório do caso"
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