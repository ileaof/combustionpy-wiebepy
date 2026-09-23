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

from dataclasses import dataclass, field
from typing import Dict, Optional


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
    f = FUELS.get(name)
    if f is None:
        raise ValueError(f"Combustível '{name}' não configurado "
                         f"(válidos: {sorted(FUELS)}).")
    return f


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
           "comparison_notice"]