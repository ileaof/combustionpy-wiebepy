# -*- coding: utf-8 -*-
"""
fuels — Configuração de combustíveis do módulo CFD: H2, CH4 (metano),
etanol e diesel.

No modo de calor prescrito (``prescribed_wiebe``) o combustível entra na
simulação 3D por meio de:
  • m_f · PCI → série temporal Q̇(t) aplicada como fonte de energia;
  • (opcional) composição da mistura inicial nos campos 0/ (specie).

Propriedades aqui são VALORES DE REFERÊNCIA com fonte declarada — cada
uma tem unidade e referência. No modo reativo (futuro) cada combustível
exigirá mecanismo químico e propriedades de transporte específicos,
declarados no campo ``mechanism`` (ainda não preenchido: o modo reativo
não é apresentado como funcional).

Misturas (blends): um combustível pode ser declarado como MISTURA de
combustíveis já cadastrados, por percentual em base de ENERGIA, MASSA ou
VOLUME (ver ``compute_blend``). A mistura vira um combustível equivalente
(PCI, A/F estequiométrica e massa molar pelas regras de mistura em base
mássica) e entra em todo o programa como qualquer outro — no 0-D e no CFD
prescrito apenas via m_f·PCI. Cada componente é marcado como injetado
(mesmo bico) ou admitido com o ar (ex.: CH4 em dual-fuel); a energia é a
mesma, mas o relatório separa as massas.

Comparações entre combustíveis devem registrar o critério (§11) — mesma
massa NÃO equivale à mesma energia.

Padrão das cargas de 45 % e 60 % do ensaio: ``B10_ensaio`` (propriedades
medidas, Tab. 2 do manuscrito do grupo), ver ``ENSAIO_PADRAO``.
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields as _dc_fields
from pathlib import Path
from typing import Dict, List, Optional, Sequence
import yaml


@dataclass(frozen=True)
class FuelSpec:
    """Especificação de um combustível (valores de referência, SI)."""
    name: str                  # identificador (H2 | CH4 | ethanol | diesel)
    display: str
    formula: str               # composição (substância pura ou surrogato)
    phase: str                 # gas | liquid
    feed: str                  # alimentação assumida no modo prescrito
    LHV_kJ_per_kg: float       # PCI (poder calorífico inferior) [kJ/kg]
    LHV_source: str            # fonte do valor de PCI
    stoich_AFR: float          # razão ar/combustível estequiométrica [kg/kg]
    molar_mass_kg_per_kmol: float
    remarks: str = ""          # considerações científicas (§10)
    mechanism: Optional[str] = None  # reservado ao modo reativo (não usado)
    validity: str = ""         # faixa de validade / limitações
    density_kg_per_m3: Optional[float] = None   # massa específica (líquido)
    density_source: str = ""   # fonte + temperatura da massa específica
    # mistura: {"basis": energy|mass|volume, "components": [{"fuel", "percent",
    # "feed": injected|intake}, ...]}; None = combustível simples
    blend: Optional[dict] = field(default=None, compare=False, hash=False)

    @property
    def is_blend(self) -> bool:
        return bool(self.blend)


FUELS: Dict[str, FuelSpec] = {
    "H2": FuelSpec(
        name="H2", display="Hidrogênio", formula="H2", phase="gas",
        feed="premixed_gas", LHV_kJ_per_kg=119_960.0,
        LHV_source="NIST WebBook / JANAF: Δh°comb, H2O(l) − H2O(g); "
                   "valor usual 119,96 MJ/kg (LHV, 25 °C, 1 atm)",
        stoich_AFR=34.3, molar_mass_kg_per_kmol=2.016,
        remarks="Difusividade e difusão diferencial muito acima dos "
                "hidrocarbonetos: no modo reativo, transporte e mecanismo "
                "devem tratar difusão multicomponente. Sem emissões de "
                "carbono; emissões de NOx exigem modelo e validação "
                "próprios.",
        validity="Referência de PCI a 25 °C; no modo prescrito o H2 afeta "
                 "apenas Q̇(t) via m_f·PCI."),
    "CH4": FuelSpec(
        name="CH4", display="Metano", formula="CH4", phase="gas",
        feed="premixed_gas", LHV_kJ_per_kg=50_010.0,
        LHV_source="NIST WebBook / valor usual 50,0 MJ/kg (LHV, 25 °C)",
        stoich_AFR=17.2, molar_mass_kg_per_kmol=16.043,
        remarks="Metano PURO: gás natural comercial tem composição variável "
                "(outros hidrocarbonetos, inertes) — não tratar gás natural "
                "como CH4 puro sem declarar a composição.",
        validity="Referência de PCI a 25 °C; no modo prescrito afeta "
                 "apenas Q̇(t) via m_f·PCI."),
    "ethanol": FuelSpec(
        name="ethanol", display="Etanol", formula="C2H5OH", phase="liquid",
        feed="premixed_gas (vaporizado)", LHV_kJ_per_kg=26_840.0,
        LHV_source="NIST WebBook / valor usual 26,8 MJ/kg (LHV, 25 °C)",
        stoich_AFR=9.0, molar_mass_kg_per_kmol=46.069,
        density_kg_per_m3=789.3,
        density_source="CRC Handbook of Chemistry and Physics: etanol "
                       "anidro 0,7893 g/cm³ a 20 °C",
        remarks="Combustível líquido: injeção direta envolveria spray, "
                "evaporação e calor latente — NÃO modelados no modo de "
                "calor prescrito. Aqui assume-se mistura pré-vaporizada "
                "(alimentação declarada como premixed_gas).",
        validity="Referência de PCI a 25 °C; modo prescrito afeta apenas "
                 "Q̇(t) via m_f·PCI."),
    "diesel": FuelSpec(
        name="diesel", display="Diesel (surrogate)", formula="surrogate",
        phase="liquid",
        feed="premixed_gas (vaporizado)", LHV_kJ_per_kg=42_600.0,
        LHV_source="Valor usual de diesel comercial ≈ 42,6 MJ/kg (LHV); "
                   "varia com a composição — substituir pelo valor do "
                   "certificado do combustível do ensaio quando disponível",
        stoich_AFR=14.5, molar_mass_kg_per_kmol=200.0,
        remarks="Diesel NÃO é uma espécie química única universal: no modo "
                "reativo exige composição substituta (surrogate, ex. "
                "n-dodecano/…, conforme a literatura escolhida) e "
                "mecanismo correspondente. No modo prescrito entra apenas "
                "como PCI e m_f.",
        validity="PCI típico; confirmar com a ficha do combustível real."),
    "B10_ensaio": FuelSpec(
        name="B10_ensaio", display="B10 do ensaio (BD-6500)",
        formula="≈ C7.13H15.62O0.07 (B10 comercial: 90 % diesel + 10 % "
                "biodiesel em volume)",
        phase="liquid", feed="premixed_gas (vaporizado)",
        LHV_kJ_per_kg=39_191.3,
        LHV_source="Queiroz, Ferreira, Rocha, Mattos, Rodrigues (UFPA/LABMO), "
                   "manuscrito submetido — Tab. 2: PCS (43 133 kJ/kg) e "
                   "análise elementar medidos; PCI = PCS − calor de "
                   "vaporização da água formada",
        stoich_AFR=14.74, molar_mass_kg_per_kmol=102.50,
        density_kg_per_m3=816.36,
        density_source="Queiroz et al. (submetido), Tab. 2: 816,36 kg/m³ "
                       "a 24,4 °C",
        remarks="Combustível DO ENSAIO do BD-6500 (cargas de 45 % e 60 %): "
                "propriedades medidas pelo grupo. A massa molar é a da "
                "fórmula empírica normalizada (C7.13H15.62O0.07), não a da "
                "molécula média. A/F estequiométrica com ar seco 21 % O2.",
        validity="Lote do ensaio; citar o manuscrito como 'submitted' até "
                 "a publicação."),
}

# Padrão do ensaio do BD-6500: combustível e dados de cada carga. rpm e m_f
# são PROVISÓRIOS (ajuste da bancada AVL ainda não fechado — 07/11/2026).
ENSAIO_PADRAO: Dict = {
    "fuel": "B10_ensaio",
    "cargas": {
        "45%": {"rpm": 3396.2, "m_fuel_kg_per_cycle": 9.42754647351e-06,
                "arquivo": "P_exp-Carga-3_45%.txt"},
        "60%": {"rpm": 3311.0, "m_fuel_kg_per_cycle": 1.15832980973e-05,
                "arquivo": "P_exp-Carga-5_60%.txt"},
    },
}


def get_fuel(name: str) -> FuelSpec:
    f = all_fuel_specs().get(name)
    if f is None:
        raise ValueError(f"Combustível '{name}' não configurado "
                         f"(válidos: {sorted(all_fuel_specs())}).")
    return f


# ---------------------------------------------------- cadastro permanente
# Combustíveis cadastrados pelo usuário (aba "Combustíveis" da GUI) são
# gravados em data/fuels_custom.yaml (relativo ao diretório de trabalho —
# raiz do projeto) e passam a valer como os embutidos. Os embutidos (FUELS)
# NUNCA são alterados no código; um cadastro com o mesmo nome sobrepõe o
# embutido apenas em memória, com o registro marcando a substituição.
_CUSTOM_CAMPOS = ("name", "display", "formula", "phase", "feed",
                  "LHV_kJ_per_kg", "LHV_source", "stoich_AFR",
                  "molar_mass_kg_per_kmol", "remarks", "validity",
                  "mechanism", "density_kg_per_m3", "density_source")


def custom_fuels_path() -> Path:
    return Path("data") / "fuels_custom.yaml"


def load_custom_fuels(path: Optional[Path] = None) -> Dict[str, dict]:
    """Combustíveis cadastrados pelo usuário (dicts brutos do YAML)."""
    p = Path(path) if path else custom_fuels_path()
    if not p.exists():
        return {}
    try:
        d = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    fuels = d.get("fuels")
    return fuels if isinstance(fuels, dict) else {}


def all_fuel_specs(path_yaml: Optional[Path] = None) -> Dict[str, FuelSpec]:
    """Registro combinado: embutidos + cadastrados (cadastro sobrepõe)."""
    merged: Dict[str, FuelSpec] = dict(FUELS)
    validos = {f.name for f in _dc_fields(FuelSpec)}
    misturas = []
    for name, d in load_custom_fuels(path_yaml).items():
        if not isinstance(d, dict):
            continue
        if d.get("blend"):
            misturas.append((name, d))
            continue
        kwargs = {k: v for k, v in d.items() if k in validos}
        try:
            merged[name] = FuelSpec(**kwargs)
        except TypeError:
            continue           # entrada inválida é ignorada, não derruba o app
    # misturas depois dos simples: as propriedades são RECALCULADAS a partir
    # dos componentes atuais (o YAML guarda só a receita e um retrato)
    for name, d in misturas:
        b = d["blend"]
        try:
            merged[name] = blend_spec(
                name, str(d.get("display") or name), b.get("components", []),
                str(b.get("basis", "")), merged,
                remarks=str(d.get("remarks") or ""))
        except ValueError:
            continue
    return merged


def fuel_names(path_yaml: Optional[Path] = None) -> List[str]:
    """Nomes disponíveis: embutidos (ordem do registro) + cadastrados."""
    return list(FUELS) + [n for n in load_custom_fuels(path_yaml)
                          if n not in FUELS]


def validate_fuel_entry(d: Dict, existing: Dict[str, dict]) -> List[str]:
    """Validação do formulário/CSV (sem propriedade inventada: o PCI
    exige fonte declarada)."""
    e: List[str] = []
    name = str(d.get("name") or "").strip()
    if not name:
        e.append("nome (identificador) é obrigatório")
    elif " " in name:
        e.append("nome não pode conter espaços (use '-', '_' ou CamelCase)")
    if not str(d.get("display") or "").strip():
        e.append("nome de exibição é obrigatório")
    if not str(d.get("formula") or "").strip():
        e.append("composição/fórmula é obrigatória")
    if str(d.get("phase") or "") not in ("gas", "liquid"):
        e.append("fase deve ser 'gas' ou 'liquid'")
    try:
        if not float(d.get("LHV_kJ_per_kg") or 0) > 0:
            e.append("PCI (LHV) deve ser > 0")
    except (TypeError, ValueError):
        e.append("PCI (LHV) deve ser numérico")
    if not str(d.get("LHV_source") or "").strip():
        e.append("fonte do PCI é OBRIGATÓRIA (não inventar propriedade)")
    for campo in ("stoich_AFR", "molar_mass_kg_per_kmol"):
        try:
            if not float(d.get(campo) or 0) > 0:
                e.append(f"{campo} deve ser > 0")
        except (TypeError, ValueError):
            e.append(f"{campo} deve ser numérico")
    dens = d.get("density_kg_per_m3")
    if dens not in (None, ""):
        try:
            if float(dens) < 0:
                e.append("massa específica deve ser ≥ 0")
            elif float(dens) > 0 and not str(d.get("density_source")
                                             or "").strip():
                e.append("fonte da massa específica é OBRIGATÓRIA quando "
                         "ela é informada")
        except (TypeError, ValueError):
            e.append("massa específica deve ser numérica")
    if str(d.get("mechanism") or "").strip():
        e.append("mecanismo químico só é válido no modo reativo (não "
                 "implementado) — deixe em branco")
    return e


def save_custom_fuel(d: Dict, path: Optional[Path] = None) -> List[str]:
    """Valida e grava (permanente) um combustível em
    data/fuels_custom.yaml. Retorna lista de erros (vazia = gravado)."""
    existing = load_custom_fuels(path)
    erros = validate_fuel_entry(d, existing)
    if erros:
        return erros
    name = str(d["name"]).strip()
    registro = {
        "name": name,
        "display": str(d["display"]).strip(),
        "formula": str(d["formula"]).strip(),
        "phase": str(d["phase"]),
        "feed": str(d.get("feed") or "premixed_gas (vaporizado)").strip(),
        "LHV_kJ_per_kg": float(d["LHV_kJ_per_kg"]),
        "LHV_source": str(d["LHV_source"]).strip(),
        "stoich_AFR": float(d["stoich_AFR"]),
        "molar_mass_kg_per_kmol": float(d["molar_mass_kg_per_kmol"]),
        "remarks": str(d.get("remarks") or "").strip(),
        "validity": str(d.get("validity") or "").strip(),
        "mechanism": None,
    }
    dens = d.get("density_kg_per_m3")
    if dens not in (None, "") and float(dens) > 0:
        registro["density_kg_per_m3"] = float(dens)
        registro["density_source"] = str(d.get("density_source")
                                         or "").strip()
    if name in FUELS:
        registro["remarks"] = (registro["remarks"]
                               + f" [sobrepõe o embutido '{name}']").strip()
    existing[name] = registro
    _write_custom(existing, path)
    return []


def delete_custom_fuel(name: str, path: Optional[Path] = None) -> bool:
    """Remove um CADASTRO (o embutido, se existir, volta a valer)."""
    existing = load_custom_fuels(path)
    if name not in existing:
        return False
    del existing[name]
    _write_custom(existing, path)
    return True


def _write_custom(existing: Dict[str, dict],
                  path: Optional[Path] = None) -> None:
    p = Path(path) if path else custom_fuels_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.safe_dump({"fuels": existing}, sort_keys=False,
                                allow_unicode=True), encoding="utf-8")


# ================================================================ misturas
BLEND_BASES = ("energy", "mass", "volume")   # base do percentual
BLEND_FEEDS = ("injected", "intake")          # bico | admissão (com o ar)
BLEND_BASIS_LABEL = {"energy": "energia", "mass": "massa",
                     "volume": "volume"}
BLEND_FEED_LABEL = {"injected": "injetado (bico)",
                    "intake": "admissão (com o ar)"}


def _componentes(components: Sequence) -> List[dict]:
    out = []
    for c in components:
        if isinstance(c, dict):
            out.append({"fuel": str(c.get("fuel", "")).strip(),
                        "percent": c.get("percent"),
                        "feed": str(c.get("feed") or "injected")})
        else:                                  # (fuel, percent[, feed])
            c = list(c)
            out.append({"fuel": str(c[0]).strip(), "percent": c[1],
                        "feed": str(c[2]) if len(c) > 2 else "injected"})
    return out


def validate_blend(components: Sequence, basis: str,
                   specs: Optional[Dict[str, FuelSpec]] = None) -> List[str]:
    """Erros da receita de uma mistura (lista vazia = válida)."""
    specs = all_fuel_specs() if specs is None else specs
    e: List[str] = []
    if basis not in BLEND_BASES:
        e.append(f"base do percentual deve ser uma de {BLEND_BASES}")
    comps = _componentes(components)
    if len(comps) < 2:
        e.append("a mistura precisa de pelo menos 2 componentes")
    nomes = [c["fuel"] for c in comps]
    if len(set(nomes)) != len(nomes):
        e.append("componente repetido na mistura")
    soma = 0.0
    for c in comps:
        f = specs.get(c["fuel"])
        if f is None:
            e.append(f"componente '{c['fuel']}' não está cadastrado")
            continue
        if f.is_blend:
            e.append(f"'{c['fuel']}' já é uma mistura (não aninhar; "
                     "declare os componentes simples)")
        try:
            pct = float(c["percent"])
        except (TypeError, ValueError):
            e.append(f"percentual de '{c['fuel']}' deve ser numérico")
            continue
        if not pct > 0:
            e.append(f"percentual de '{c['fuel']}' deve ser > 0")
        soma += pct
        if c["feed"] not in BLEND_FEEDS:
            e.append(f"alimentação de '{c['fuel']}' deve ser uma de "
                     f"{BLEND_FEEDS}")
        if basis == "volume":
            if f.phase != "liquid":
                e.append(f"base volume só vale para líquidos: '{c['fuel']}' "
                         "é gás (use energia ou massa)")
            elif not f.density_kg_per_m3:
                e.append(f"base volume exige a massa específica de "
                         f"'{c['fuel']}' (cadastre-a com fonte)")
    if comps and abs(soma - 100.0) > 1e-6:
        e.append(f"os percentuais somam {soma:g} %, devem somar 100 %")
    return e


def compute_blend(components: Sequence, basis: str,
                  specs: Optional[Dict[str, FuelSpec]] = None) -> Dict:
    """Propriedades da mistura a partir dos percentuais.

    Conversão para fração MÁSSICA y_i:
      massa:   y_i = x_i
      volume:  y_i = x_i ρ_i / Σ x_j ρ_j           (líquidos, ρ com fonte)
      energia: y_i = (e_i / PCI_i) / Σ (e_j / PCI_j)
    Regras de mistura (mistura ideal, base mássica — exatas para PCI e
    A/F estequiométrica, pois a demanda de O2 é aditiva):
      PCI = Σ y_i PCI_i ;  A/F_est = Σ y_i A/F_i ;  1/M = Σ y_i / M_i
    """
    specs = all_fuel_specs() if specs is None else specs
    erros = validate_blend(components, basis, specs)
    if erros:
        raise ValueError("; ".join(erros))
    comps = _componentes(components)
    fs = [specs[c["fuel"]] for c in comps]
    x = [float(c["percent"]) / 100.0 for c in comps]
    if basis == "mass":
        w = x
    elif basis == "volume":
        w = [xi * f.density_kg_per_m3 for xi, f in zip(x, fs)]
    else:
        w = [xi / f.LHV_kJ_per_kg for xi, f in zip(x, fs)]
    y = [wi / sum(w) for wi in w]
    lhv = sum(yi * f.LHV_kJ_per_kg for yi, f in zip(y, fs))
    afr = sum(yi * f.stoich_AFR for yi, f in zip(y, fs))
    mm = 1.0 / sum(yi / f.molar_mass_kg_per_kmol for yi, f in zip(y, fs))
    rho = None
    if all(f.phase == "liquid" and f.density_kg_per_m3 for f in fs):
        rho = 1.0 / sum(yi / f.density_kg_per_m3 for yi, f in zip(y, fs))
    linhas = []
    for c, f, yi in zip(comps, fs, y):
        linhas.append({
            "fuel": f.name, "display": f.display, "feed": c["feed"],
            "percent_declared": float(c["percent"]),
            "mass_fraction": yi,
            "energy_fraction": yi * f.LHV_kJ_per_kg / lhv,
            "volume_fraction": (yi / f.density_kg_per_m3 * rho
                                if rho else None),
            "LHV_kJ_per_kg": f.LHV_kJ_per_kg})
    return {"basis": basis, "components": linhas, "LHV_kJ_per_kg": lhv,
            "stoich_AFR": afr, "molar_mass_kg_per_kmol": mm,
            "density_kg_per_m3": rho,
            "phase": "liquid" if all(f.phase == "liquid" for f in fs)
            else "gas+liquid" if any(f.phase == "liquid" for f in fs)
            else "gas"}


def blend_spec(name: str, display: str, components: Sequence, basis: str,
               specs: Optional[Dict[str, FuelSpec]] = None,
               remarks: str = "") -> FuelSpec:
    """FuelSpec equivalente da mistura (entra no programa como qualquer
    combustível)."""
    specs = all_fuel_specs() if specs is None else specs
    r = compute_blend(components, basis, specs)
    base = BLEND_BASIS_LABEL[basis]
    partes = [f"{c['percent_declared']:g} % {c['fuel']}"
              + (" [admissão]" if c["feed"] == "intake" else "")
              for c in r["components"]]
    fontes = "; ".join(f"{c['fuel']}: {specs[c['fuel']].LHV_source}"
                       for c in r["components"])
    feeds = {c["feed"] for c in r["components"]}
    feed = ("injetado (mesmo bico)" if feeds == {"injected"}
            else "admissão (com o ar)" if feeds == {"intake"}
            else "dual: parte injetada + parte pela admissão")
    dens_src = ""
    if r["density_kg_per_m3"]:
        dens_src = "calculada (volumes aditivos) a partir de: " + "; ".join(
            f"{c['fuel']}: {specs[c['fuel']].density_source}"
            for c in r["components"])
    return FuelSpec(
        name=name, display=display,
        formula=f"mistura ({base}): " + " + ".join(partes),
        phase="liquid" if r["phase"] == "liquid" else "gas"
        if r["phase"] == "gas" else "liquid",
        feed=feed, LHV_kJ_per_kg=r["LHV_kJ_per_kg"],
        LHV_source="calculado pela regra de mistura em base mássica "
                   "(PCI = Σ y_i·PCI_i) a partir de: " + fontes,
        stoich_AFR=r["stoich_AFR"],
        molar_mass_kg_per_kmol=r["molar_mass_kg_per_kmol"],
        remarks=remarks,
        validity="Mistura ideal (sem calor de mistura). No 0-D e no CFD "
                 "prescrito entra só via m_f·PCI; no modo reativo cada "
                 "componente precisa estar no mecanismo e ter campo inicial.",
        density_kg_per_m3=r["density_kg_per_m3"],
        density_source=dens_src,
        blend={"basis": basis,
               "components": [{"fuel": c["fuel"],
                               "percent": c["percent_declared"],
                               "feed": c["feed"]}
                              for c in r["components"]]})


def blend_breakdown(fuel, m_fuel_kg: float,
                    specs: Optional[Dict[str, FuelSpec]] = None) -> Dict:
    """Massa e energia por componente para uma massa TOTAL de mistura por
    ciclo (kg). Para combustível simples devolve um único componente."""
    f = get_fuel(fuel) if isinstance(fuel, str) else fuel
    if not f.is_blend:
        q = m_fuel_kg * f.LHV_kJ_per_kg * 1e3
        return {"components": [{"fuel": f.name, "feed": "injected",
                                "mass_kg": m_fuel_kg, "energy_J": q,
                                "mass_fraction": 1.0,
                                "energy_fraction": 1.0}],
                "m_injected_kg": m_fuel_kg, "m_intake_kg": 0.0,
                "Q_cycle_J": q}
    specs = all_fuel_specs() if specs is None else specs
    r = compute_blend(f.blend["components"], f.blend["basis"], specs)
    linhas = []
    for c in r["components"]:
        m = m_fuel_kg * c["mass_fraction"]
        linhas.append({"fuel": c["fuel"], "feed": c["feed"], "mass_kg": m,
                       "energy_J": m * c["LHV_kJ_per_kg"] * 1e3,
                       "mass_fraction": c["mass_fraction"],
                       "energy_fraction": c["energy_fraction"]})
    return {"components": linhas,
            "m_injected_kg": sum(c["mass_kg"] for c in linhas
                                 if c["feed"] == "injected"),
            "m_intake_kg": sum(c["mass_kg"] for c in linhas
                               if c["feed"] == "intake"),
            "Q_cycle_J": sum(c["energy_J"] for c in linhas)}


def blend_total_from_injected(fuel, m_injected_kg: float,
                              specs: Optional[Dict[str, FuelSpec]] = None
                              ) -> float:
    """Massa TOTAL da mistura quando só a parte injetada é conhecida
    (dual-fuel: a balança mede o diesel, o gás vem pela admissão)."""
    f = get_fuel(fuel) if isinstance(fuel, str) else fuel
    if not f.is_blend:
        return m_injected_kg
    b = blend_breakdown(f, 1.0, specs)
    if not b["m_injected_kg"] > 0:
        raise ValueError("mistura sem componente injetado")
    return m_injected_kg / b["m_injected_kg"]


def save_custom_blend(name: str, display: str, components: Sequence,
                      basis: str, remarks: str = "",
                      path: Optional[Path] = None) -> List[str]:
    """Valida e grava (permanente) uma MISTURA em data/fuels_custom.yaml.
    O YAML guarda a receita (base + componentes) e um retrato das
    propriedades calculadas; ao ler, as propriedades são recalculadas."""
    name = str(name or "").strip()
    e: List[str] = []
    if not name:
        e.append("nome (identificador) é obrigatório")
    elif " " in name:
        e.append("nome não pode conter espaços (use '-', '_' ou CamelCase)")
    elif name in FUELS:
        e.append("nome reservado a um combustível embutido")
    if not str(display or "").strip():
        e.append("nome de exibição é obrigatório")
    specs = all_fuel_specs(path)
    e += validate_blend(components, basis, specs)
    if e:
        return e
    f = blend_spec(name, str(display).strip(), components, basis, specs,
                   remarks=str(remarks or "").strip())
    existing = load_custom_fuels(path)
    registro = {k: getattr(f, k) for k in _CUSTOM_CAMPOS}
    for k in ("LHV_kJ_per_kg", "stoich_AFR", "molar_mass_kg_per_kmol"):
        registro[k] = round(float(registro[k]), 4)
    if registro.get("density_kg_per_m3"):
        registro["density_kg_per_m3"] = round(registro["density_kg_per_m3"], 3)
    registro["blend"] = f.blend
    existing[name] = registro
    _write_custom(existing, path)
    return []


def blend_from_text(texto: str) -> Dict:
    """Receita em texto (coluna 'blend' do CSV):
    'energy | B10_ensaio:70:injected ; CH4:30:intake'."""
    base, _, resto = str(texto).partition("|")
    comps = []
    for item in resto.split(";"):
        if not item.strip():
            continue
        partes = [p.strip() for p in item.split(":")]
        if len(partes) < 2:
            raise ValueError(f"componente mal formado: '{item.strip()}'")
        comps.append({"fuel": partes[0], "percent": float(partes[1]),
                      "feed": partes[2] if len(partes) > 2 else "injected"})
    return {"basis": base.strip(), "components": comps}


def blend_to_text(blend: Optional[dict]) -> str:
    if not blend:
        return ""
    return blend["basis"] + " | " + " ; ".join(
        f"{c['fuel']}:{c['percent']:g}:{c['feed']}"
        for c in blend["components"])


# ------------------------------------------------------ exportar/ler CSV
_CAMPOS_CSV = list(_CUSTOM_CAMPOS) + ["blend"]


def _valor_csv(s: FuelSpec, c: str):
    if c == "blend":
        return blend_to_text(s.blend)
    v = getattr(s, c)
    return v if v is not None else ""


def export_fuels_csv(path, names: Optional[List[str]] = None,
                     path_yaml: Optional[Path] = None) -> List[str]:
    """Exporta combustíveis para CSV (UTF-8, ';'-separado — abre direto
    no Excel em pt-BR). Padrão: TODOS (embutidos + cadastrados).
    Retorna a lista de nomes gravados."""
    import csv
    specs = all_fuel_specs(path_yaml)
    if names is None:
        nomes = list(FUELS) + [n for n in load_custom_fuels(path_yaml)
                               if n not in FUELS]
    else:
        nomes = list(names)
    faltam = [n for n in nomes if n not in specs]
    if faltam:
        raise ValueError(f"Combustível não encontrado: {faltam}")
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(_CAMPOS_CSV)
        for n in nomes:
            w.writerow([_valor_csv(specs[n], c) for c in _CAMPOS_CSV])
    return nomes


def import_fuels_csv(path, path_yaml: Optional[Path] = None) -> Dict:
    """Lê um CSV exportado (ou preenchido manualmente) e grava cada linha
    como cadastro permanente. Retorna {"gravados": [...], "erros": [...]}.
    Linhas inválidas NÃO abortam o lote (cada linha é validada; erros
    identificam a linha pelo nome)."""
    import csv
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(str(p))
    with p.open("r", newline="", encoding="utf-8-sig") as fh:
        amostra = fh.read(4096)
        fh.seek(0)
        delim = ";" if amostra.count(";") >= amostra.count(",") else ","
        leitor = csv.DictReader(fh, delimiter=delim)
        if not leitor.fieldnames or "name" not in [c.strip() for c in
                                                   leitor.fieldnames]:
            raise ValueError("CSV sem coluna 'name'; colunas esperadas: "
                             + ", ".join(_CAMPOS_CSV))
        gravados: List[str] = []
        erros: List[str] = []
        for i, linha in enumerate(leitor, start=2):
            d = {k.strip(): (v if v is not None else "") for k, v
                 in linha.items() if k}
            if not str(d.get("name") or "").strip():
                continue                      # linha em branco/comentário
            if str(d.get("blend") or "").strip():
                try:
                    b = blend_from_text(d["blend"])
                    errs = save_custom_blend(
                        str(d.get("name")), str(d.get("display") or ""),
                        b["components"], b["basis"],
                        str(d.get("remarks") or ""), path_yaml)
                except ValueError as exc:
                    errs = [str(exc)]
            else:
                errs = save_custom_fuel(d, path_yaml)
            if errs:
                erros.append(f"linha {i} ('{d.get('name')}'): "
                             + "; ".join(errs))
            else:
                gravados.append(str(d["name"]).strip())
    return {"gravados": gravados, "erros": erros}


def fuel_summary(name: str, m_fuel_kg: float) -> Dict:
    """Resumo para validação e relatório (energia por ciclo em J)."""
    f = get_fuel(name)
    return {"name": f.name, "display": f.display, "formula": f.formula,
            "phase": f.phase, "feed": f.feed,
            "LHV_kJ_per_kg": f.LHV_kJ_per_kg, "LHV_source": f.LHV_source,
            "stoich_AFR": f.stoich_AFR,
            "m_fuel_kg_per_cycle": m_fuel_kg,
            "Q_cycle_J": m_fuel_kg * f.LHV_kJ_per_kg * 1e3,
            "mechanism": f.mechanism, "remarks": f.remarks,
            "validity": f.validity,
            **({"blend": f.blend,
                "blend_breakdown": blend_breakdown(f, m_fuel_kg)}
               if f.is_blend else {})}


def comparison_notice(fuels: list, criterion: str) -> str:
    """Aviso sobre comparação entre combustíveis (§11)."""
    from ...i18n import tf
    return tf(
        "Comparação entre combustíveis sob o critério declarado "
        "('{criterio}'): no modo de calor prescrito, cada combustível usa "
        "parâmetros Wiebe pré-calibrados (origem experimental declarada em "
        "cada caso). Isto NÃO é uma previsão de troca de combustível — a "
        "combustão foi prescrita por curvas calibradas, não resolvida.",
        criterio=criterion)


__all__ = ["FuelSpec", "FUELS", "get_fuel", "fuel_summary",
           "comparison_notice", "custom_fuels_path", "load_custom_fuels",
           "all_fuel_specs", "fuel_names", "validate_fuel_entry",
           "save_custom_fuel", "delete_custom_fuel",
           "export_fuels_csv", "import_fuels_csv", "ENSAIO_PADRAO",
           "BLEND_BASES", "BLEND_FEEDS", "BLEND_BASIS_LABEL",
           "BLEND_FEED_LABEL", "validate_blend", "compute_blend",
           "blend_spec", "blend_breakdown", "blend_total_from_injected",
           "save_custom_blend", "blend_from_text", "blend_to_text"]