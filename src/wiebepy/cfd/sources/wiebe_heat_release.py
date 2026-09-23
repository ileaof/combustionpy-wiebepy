# -*- coding: utf-8 -*-
"""
wiebe_heat_release.py — Fonte de calor global conservativa a partir da
função Wiebe existente do wiebepy (N = 1..5).

A liberação de calor GLOBAL por unidade de tempo é

    Q̇(t) = m_f · PCI · (dx_b/dθ) · (dθ/dt)

com conversões explícitas de unidade (§7):

    θ em graus : dθ/dt = 6 · RPM           [grau/s]
    θ em rad   : dθ/dt = 2π · RPM/60       [rad/s]
    m_f  [kg], PCI [kJ/kg], dx_b/dθ [1/unidade angular]
    ⇒ Q̇ [kJ/s] = [kW]; converte-se para W ao escrever a tabela do solver.

O módulo NÃO re-deriva a Wiebe: usa ``multistage_wiebe_derivative`` do
núcleo (uma única implementação — sem duplicação da formulação para
N = 1..5).

Distribuição espacial (uniforme, referência): o caso OpenFOAM gerado
usa o fvModel nativo ``heatSource`` com a densidade prescrita
diretamente,

    q'''(CA) = Q̇(CA) / V₀(CA)   [W/m³]

onde V₀(CA) é o volume cinemático 0-D. O solver aplica
Σᵢ q'''ᵢ·Vᵢᵃᵗᵘᵃˡ ≈ Q̇ sobre os volumes ATUAIS da malha — conservativo
a cada instante, inclusive com malha móvel e execução paralela.
(No OpenFOAM 13 o modo ``Q`` — potência total — divide pelo volume da
cellZone congelado na construção do fvModel e NÃO é conservativo com
malha móvel; por isso prescrevemos q'''.) Aqui geramos e verificamos
apenas a série temporal Q̇(t): a verificação de fechamento é

    ∫ Q̇ dt  =  m_f · PCI · [x_b(θ_fim) − x_b(θ_ini)]

Distribuição ``region``: restringe o cellZone. Como o volume da zona
não é conhecido na geração do caso, este modo mantém o campo Q
(potência total) e herda a limitação do OF13 com malha móvel —
documentada no aviso de distribuição; preferir ``uniform``.

Este módulo nunca é importado com CFD desabilitado.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np

from ...core.core import multistage_wiebe
from ...core.derivatives import multistage_wiebe_derivative

# ---------------------------------------------------------------- unidades
DEG_PER_S_PER_RPM = 6.0            # dθ/dt [grau/s] = 6 · RPM
RAD_PER_S_PER_RPM = 2.0 * math.pi / 60.0   # dθ/dt [rad/s] = 2π · RPM/60


def dtheta_dt(angle_unit: str, rpm: float) -> float:
    """dθ/dt na unidade angular dada (deg: 6·RPM; rad: 2π·RPM/60)."""
    if angle_unit == "deg":
        return DEG_PER_S_PER_RPM * rpm
    if angle_unit == "rad":
        return RAD_PER_S_PER_RPM * rpm
    raise ValueError(f"angle_unit '{angle_unit}' inválida (deg | rad).")


def qdot_power(theta, stages, m_fuel_kg: float, LHV_kJ_per_kg: float,
               angle_unit: str, rpm: float) -> np.ndarray:
    """Q̇(θ) em W (J/s), com o mesmo suporte e unidade angular de θ.

    m_fuel_kg [kg] · LHV_kJ_per_kg [kJ/kg] · dx_b/dθ [1/unid. angular]
    · dθ/dt [unid. angular/s] = kJ/s = kW → ×1e3 ⇒ W.
    """
    dxb = np.asarray(multistage_wiebe_derivative(theta, stages), dtype=float)
    return (dxb * m_fuel_kg * LHV_kJ_per_kg
            * dtheta_dt(angle_unit, rpm)) * 1.0e3


def qdot_time_series(theta, stages, m_fuel_kg: float, LHV_kJ_per_kg: float,
                     angle_unit: str, rpm: float) -> Tuple[np.ndarray,
                                                           np.ndarray]:
    """Série temporal (t [s], Q̇ [W]) na grade θ dada (crescente).

    t(θ) = (θ − θ[0]) / (dθ/dt).
    """
    theta = np.asarray(theta, dtype=float)
    w = dtheta_dt(angle_unit, rpm)
    t = (theta - theta[0]) / w
    q = qdot_power(theta, stages, m_fuel_kg, LHV_kJ_per_kg, angle_unit, rpm)
    return t, q


def energy_check(theta, stages, m_fuel_kg: float, LHV_kJ_per_kg: float,
                 angle_unit: str, rpm: float,
                 rtol: float = 1e-3) -> Dict:
    """Fechamento temporal: ∫Q̇dt (trapezoidal) vs m_f·PCI·Δx_b.

    O erro é dominado pela resolução da grade em torno do pico de dx_b/dθ;
    a grade recomendada (0,1° ou equivalente) dá erro ≪ 0,1 %.
    """
    theta = np.asarray(theta, dtype=float)
    t, q = qdot_time_series(theta, stages, m_fuel_kg, LHV_kJ_per_kg,
                            angle_unit, rpm)
    integral_J = float(np.trapezoid(q, t)) if hasattr(np, "trapezoid") \
        else float(np.trapz(q, t))
    x = np.asarray(multistage_wiebe(theta, stages), dtype=float)
    esperado_J = m_fuel_kg * LHV_kJ_per_kg * 1e3 * float(x[-1] - x[0])
    rel = (abs(integral_J - esperado_J) / esperado_J) if esperado_J > 0 \
        else 0.0
    return {"integral_J": integral_J, "expected_J": esperado_J,
            "rel_error": rel, "ok": bool(rel <= rtol)}


def _pairs_text(pares) -> str:
    linhas = ["                ("]
    for ci, qi in pares:
        linhas.append(f"                    ({ci:.9f} {qi:.9e})")
    linhas.append("                );")
    return "\n".join(linhas)


def function1_table(theta, stages, m_fuel_kg: float, LHV_kJ_per_kg: float,
                    angle_unit: str, rpm: float, n_min: int = 400,
                    step_deg: float = 0.1) -> List[Tuple[float, float]]:
    """Tabela (CA [graus], Q̇ [W]) para o campo Function1 ``Q`` do fvModel
    ``heatSource`` do OpenFOAM (tipo ``table``).

    Com ``userTime type engine`` o tempo do solver É o ângulo de manivela
    em GRAUS — a 1ª coluna da tabela é o CA (ex. −120 … 120), não o tempo
    físico. A verificação de fechamento converte de volta para segundos
    (∫Q̇ dCA/(6·RPM) = ∫Q̇dt [s]) e confere contra a energia do ciclo; um
    erro relativo > 0,5 % levanta ValueError.
    """
    theta = np.asarray(theta, dtype=float)
    ca_deg = np.degrees(theta)
    q = qdot_power(theta, stages, m_fuel_kg, LHV_kJ_per_kg, angle_unit, rpm)
    # reamostragem uniforme em CA (mín. n_min pontos) para que o
    # interpolador linear do solver reproduza o pico de Q̇. O passo
    # padrão de 0,1° subintegra estágios com m pequeno (energia
    # concentrada numa faixa fina); o case_builder passa o passo
    # convergido da verificação de conservação.
    n = max(n_min, int(math.ceil(np.ptp(ca_deg) / step_deg)) + 1)
    cu = np.linspace(ca_deg[0], ca_deg[-1], n)
    qu = np.interp(cu, ca_deg, q)
    # fechamento da tabela (o solver integra exatamente esta série)
    E_table_deg = float(np.trapezoid(qu, cu)) if hasattr(np, "trapezoid") \
        else float(np.trapz(qu, cu))
    E_s = E_table_deg / (DEG_PER_S_PER_RPM * rpm)   # CA [°]/s → tempo físico
    chk = energy_check(theta, stages, m_fuel_kg, LHV_kJ_per_kg,
                       angle_unit, rpm)
    if chk["integral_J"] > 0 and abs(E_s - chk["integral_J"]) \
            / chk["integral_J"] > 0.005:
        raise ValueError("Tabela Q(CA) não conserva a energia do ciclo "
                         f"({E_s:.1f} J vs {chk['integral_J']:.1f} J) — "
                         "aumente a resolução da grade angular.")
    return list(zip(cu.tolist(), qu.tolist()))


def table_text(theta, stages, m_fuel_kg: float, LHV_kJ_per_kg: float,
               angle_unit: str, rpm: float, step_deg: float = 0.1) -> str:
    """Tabela (CA [graus], Q̇ [W]) no formato do Function1 ``table`` do
    OpenFOAM Foundation 13 (forma de dicionário — ver tutorials, ex.
    engine2Valve2D):

        values ( (CA0 Q0) (CA1 Q1) … )

    ATENÇÃO (OpenFOAM 13): no fvModel ``heatSource``, o campo ``Q``
    (potência total) é dividido pelo volume da cellZone **congelado na
    construção do fvModel** — com malha móvel (pistão) isso torna a
    fonte NÃO conservativa. Para casos com pistão móvel use
    ``table_text_density``, que prescreve q''' diretamente.
    """
    pares = function1_table(theta, stages, m_fuel_kg, LHV_kJ_per_kg,
                            angle_unit, rpm, step_deg=step_deg)
    return _pairs_text(pares)


def function1_table_density(theta, stages, m_fuel_kg: float,
                            LHV_kJ_per_kg: float, angle_unit: str, rpm: float,
                            volume_of_theta, n_min: int = 400,
                            step_deg: float = 0.1
                            ) -> List[Tuple[float, float]]:
    """Tabela (CA [graus], q''' [W/m³]) da distribuição UNIFORME (§7):

        q'''(CA) = Q̇(CA) / V₀(CA)

    com V₀(CA) o volume cinemático 0-D (o mesmo que define a malha).
    Prescrevendo a densidade diretamente, o fvModel ``heatSource``
    aplica Σᵢ q'''ᵢ·Vᵢ = Q̇·(ΣᵢVᵢ/V₀) ≈ Q̇ sobre os volumes ATUAIS da
    malha — conservativo a cada instante, inclusive com pistão em
    movimento (o modo ``Q`` do OpenFOAM 13 congela 1/V(zone) na
    construção e não é conservativo com malha móvel).

    ``volume_of_theta`` é o volume 0-D [m³] em cada θ (array) ou um
    escalar (pistão fixo). A verificação de fechamento integra
    q'''·V₀ no tempo e confere contra a energia do ciclo (>0,5 % de
    erro levanta ValueError).
    """
    theta = np.asarray(theta, dtype=float)
    ca_deg = np.degrees(theta)
    q = qdot_power(theta, stages, m_fuel_kg, LHV_kJ_per_kg, angle_unit, rpm)
    V = np.asarray(volume_of_theta, dtype=float)
    if V.ndim == 0:
        V = np.full_like(theta, float(V))
    # reamostragem uniforme em CA (mín. n_min pontos), como em function1_table
    n = max(n_min, int(math.ceil(np.ptp(ca_deg) / step_deg)) + 1)
    cu = np.linspace(ca_deg[0], ca_deg[-1], n)
    qu = np.interp(cu, ca_deg, q)
    Vu = np.interp(cu, ca_deg, V)
    q3 = qu / Vu
    # fechamento: ∫ q'''·V₀ dCA/(6·RPM) = ∫ Q̇dt [J]
    E_s = (float(np.trapezoid(q3 * Vu, cu)) if hasattr(np, "trapezoid")
           else float(np.trapz(q3 * Vu, cu))) / (DEG_PER_S_PER_RPM * rpm)
    chk = energy_check(theta, stages, m_fuel_kg, LHV_kJ_per_kg,
                       angle_unit, rpm)
    if chk["integral_J"] > 0 and abs(E_s - chk["integral_J"]) \
            / chk["integral_J"] > 0.005:
        raise ValueError("Tabela q'''(CA) não conserva a energia do ciclo "
                         f"({E_s:.1f} J vs {chk['integral_J']:.1f} J) — "
                         "aumente a resolução da grade angular.")
    return list(zip(cu.tolist(), q3.tolist()))


def table_text_density(theta, stages, m_fuel_kg: float, LHV_kJ_per_kg: float,
                       angle_unit: str, rpm: float, volume_of_theta,
                       step_deg: float = 0.1) -> str:
    """Tabela (CA [°], q''' [W/m³]) no formato do Function1 ``table``
    do OpenFOAM 13 — ver ``function1_table_density``."""
    pares = function1_table_density(theta, stages, m_fuel_kg, LHV_kJ_per_kg,
                                    angle_unit, rpm, volume_of_theta,
                                    step_deg=step_deg)
    return _pairs_text(pares)


def distribution_notice(distribution: str) -> str:
    """Aviso científico associado à distribuição espacial escolhida."""
    if distribution == "uniform":
        return (
            "Distribuição UNIFORME de calor no volume ativo (caso de "
            "referência). Isto NÃO representa a propagação da chama: "
            "diferentes distribuições espaciais podem reproduzir pressões "
            "volumétricas médias semelhantes.")
    return (
        "Distribuição em região especificada (cellZone). A forma da região "
        "é uma hipótese do usuário, não uma chama resolvida; não validar "
        "temperatura local ou emissões a partir dela. LIMITAÇÃO OpenFOAM 13: "
        "neste modo a fonte usa potência total Q, dividida pelo volume da "
        "zona congelado na construção do fvModel — com pistão móvel a "
        "energia injetada deixa de ser conservativa; preferir 'uniform'.")


__all__ = ["dtheta_dt", "qdot_power", "qdot_time_series", "energy_check",
           "function1_table", "table_text", "function1_table_density",
           "table_text_density", "distribution_notice",
           "DEG_PER_S_PER_RPM", "RAD_PER_S_PER_RPM"]