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

Não há suposição de operação dual-fuel: escolher um combustível define
uma energia por ciclo (m_f · PCI); comparações entre combustíveis devem
registrar o critério (§11) — mesma massa NÃO equivale à mesma energia.
"""
from __future__ import annotations

from dataclasses import dataclass, fields as _dc_fields
from pathlib import Path
from typing import Dict, List, Optional
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
                  "mechanism")


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
    for name, d in load_custom_fuels(path_yaml).items():
        if not isinstance(d, dict):
            continue
        kwargs = {k: v for k, v in d.items() if k in validos}
        try:
            merged[name] = FuelSpec(**kwargs)
        except TypeError:
            continue           # entrada inválida é ignorada, não derruba o app
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


# ------------------------------------------------------ exportar/ler CSV
_CAMPOS_CSV = list(_CUSTOM_CAMPOS)


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
            s = specs[n]
            w.writerow([getattr(s, c) if getattr(s, c) is not None else ""
                        for c in _CAMPOS_CSV])
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
            "validity": f.validity}


def comparison_notice(fuels: list, criterion: str) -> str:
    """Aviso sobre comparação entre combustíveis (§11)."""
    return (
        "Comparação entre combustíveis sob o critério declarado "
        f"('{criterion}'): no modo de calor prescrito, cada combustível usa "
        "parâmetros Wiebe pré-calibrados (origem experimental declarada em "
        "cada caso). Isto NÃO é uma previsão de troca de combustível — a "
        "combustão foi prescrita por curvas calibradas, não resolvida.")


__all__ = ["FuelSpec", "FUELS", "get_fuel", "fuel_summary",
           "comparison_notice", "custom_fuels_path", "load_custom_fuels",
           "all_fuel_specs", "fuel_names", "validate_fuel_entry",
           "save_custom_fuel", "delete_custom_fuel",
           "export_fuels_csv", "import_fuels_csv"]