# -*- coding: utf-8 -*-
"""
heat_release.py — Fração de massa queimada a partir da pressão medida.

Liberação de calor APARENTE (1ª lei, zona única, sem perdas explícitas):

    dQ/dθ = κ/(κ−1) · p · dV/dθ + 1/(κ−1) · V · dp/dθ          [kJ/rad]

com p em kPa e V em m³ (geometria biela-manivela, a mesma do Double
Wiebe):

    V(θ)  = Vc + Vd/2 · [R + 1 − cos θ − √(R² − sin²θ)],   R = 2L/S
    Vd    = π D² S / 4,   Vc = Vd / (Rc − 1)

Q(θ) = ∫ dQ/dθ dθ. O início da combustão (SOC) é o mínimo de Q antes do
pico de pressão (a compressão sem perdas modeladas faz Q aparente cair
levemente); o fim (EOC) é o máximo de Q depois do SOC. Então

    x_b = (Q − Q_SOC) / (Q_EOC − Q_SOC)      (0 antes do SOC, 1 após o EOC)
    dx_b/dθ = (dQ/dθ) / (Q_EOC − Q_SOC)      (0 fora da janela)

Limitações: é a queima *aparente* — perdas de calor, blow-by e variação
de κ não são modeladas; o resultado depende de Rc e κ (informe os do
motor). dp/dθ é calculado com filtro Savitzky-Golay (grade uniforme) para
não amplificar o ruído da medição.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional

import numpy as np

PRESSURE_FACTORS_KPA = {"bar": 100.0, "kPa": 1.0, "MPa": 1000.0, "Pa": 1e-3}


@dataclass
class EngineGeometry:
    """Geometria do motor (padrões = motor do ensaio do Double Wiebe)."""
    bore_mm: float = 86.0
    stroke_mm: float = 70.0
    rod_mm: float = 117.5
    rc: float = 17.0

    def check(self) -> "EngineGeometry":
        if min(self.bore_mm, self.stroke_mm, self.rod_mm) <= 0:
            raise ValueError("Diâmetro, curso e biela devem ser > 0.")
        if self.rod_mm <= self.stroke_mm / 2:
            raise ValueError("A biela deve ser maior que o raio da manivela.")
        if not self.rc > 1:
            raise ValueError("A razão de compressão deve ser > 1.")
        return self

    def to_dict(self):
        return asdict(self)


def cylinder_volume(theta_rad, g: EngineGeometry):
    """(V [m³], dV/dθ [m³/rad]) na convenção θ = 0 no PMS de combustão."""
    D, S = g.bore_mm / 1000.0, g.stroke_mm / 1000.0
    R = 2.0 * g.rod_mm / g.stroke_mm
    Vd = np.pi * D * D * S / 4.0
    Vc = Vd / (g.rc - 1.0)
    s, c = np.sin(theta_rad), np.cos(theta_rad)
    raiz = np.sqrt(R * R - s * s)
    V = Vc + Vd / 2.0 * (R + 1.0 - c - raiz)
    dV = Vd / 2.0 * s * (1.0 + c / raiz)
    return V, dV


@dataclass
class HeatReleaseResult:
    theta: np.ndarray          # unidade de entrada
    p_kPa: np.ndarray
    V: np.ndarray
    hrr: np.ndarray            # dQ/dθ [kJ/rad]
    q_cum: np.ndarray          # Q [kJ]
    xb: np.ndarray
    dxb: np.ndarray            # 1/(unidade angular)
    theta_soc: float
    theta_eoc: float
    q_total_kJ: float
    kappa: float
    geometry: EngineGeometry

    def summary(self) -> dict:
        return {"theta_soc": self.theta_soc, "theta_eoc": self.theta_eoc,
                "q_total_kJ": self.q_total_kJ, "kappa": self.kappa,
                **self.geometry.to_dict()}


def _derivada(theta, y, janela: int):
    """dy/dθ: Savitzky-Golay (grade uniforme) ou gradiente (não uniforme)."""
    passos = np.diff(theta)
    uniforme = np.allclose(passos, passos.mean(), rtol=1e-3)
    if uniforme and janela >= 5 and theta.size > janela:
        from scipy.signal import savgol_filter
        w = janela if janela % 2 else janela + 1
        return savgol_filter(y, w, 3, deriv=1, delta=float(passos.mean()))
    return np.gradient(y, theta)


def apparent_heat_release(theta, p_kPa, geometry: Optional[EngineGeometry] = None,
                          kappa: float = 1.37, angle_unit: str = "rad",
                          smooth: int = 11) -> HeatReleaseResult:
    """Liberação de calor aparente e x_b a partir de p(θ).

    theta      : ângulos (rad ou graus, conforme ``angle_unit``), θ = 0 no
                 PMS de combustão, crescentes
    p_kPa      : pressão do cilindro [kPa]
    smooth     : janela (pontos) do filtro Savitzky-Golay de dp/dθ; 0 desliga
    """
    g = (geometry or EngineGeometry()).check()
    if not 1.0 < kappa < 2.0:
        raise ValueError("κ deve estar entre 1 e 2.")
    theta = np.asarray(theta, dtype=float)
    p = np.asarray(p_kPa, dtype=float)
    if theta.size < 20 or np.any(np.diff(theta) <= 0):
        raise ValueError("São necessários ≥ 20 ângulos estritamente crescentes.")
    fator = 1.0 if angle_unit == "rad" else np.pi / 180.0
    th = theta * fator
    V, dV = cylinder_volume(th, g)
    dp = _derivada(th, p, smooth)
    hrr = kappa / (kappa - 1.0) * p * dV + V * dp / (kappa - 1.0)   # kJ/rad
    q = np.concatenate([[0.0], np.cumsum(0.5 * (hrr[1:] + hrr[:-1])
                                         * np.diff(th))])
    i_pico = int(np.argmax(p))
    i_soc = int(np.argmin(q[:i_pico + 1]))
    i_eoc = i_soc + int(np.argmax(q[i_soc:]))
    q_total = float(q[i_eoc] - q[i_soc])
    if not q_total > 0:
        raise ValueError("Não foi encontrada liberação de calor positiva: "
                         "confira a unidade da pressão, a do ângulo e a "
                         "convenção θ = 0 no PMS de combustão.")
    xb = np.clip((q - q[i_soc]) / q_total, 0.0, 1.0)
    xb[:i_soc] = 0.0
    xb[i_eoc:] = 1.0
    dxb = hrr / q_total * fator                    # por unidade de entrada
    dxb[:i_soc] = 0.0
    dxb[i_eoc + 1:] = 0.0
    return HeatReleaseResult(theta=theta, p_kPa=p, V=V, hrr=hrr, q_cum=q,
                             xb=xb, dxb=dxb, theta_soc=float(theta[i_soc]),
                             theta_eoc=float(theta[i_eoc]),
                             q_total_kJ=q_total, kappa=kappa, geometry=g)


def pressure_to_fitdata(theta, p, angle_unit: str = "rad",
                        pressure_unit: str = "bar",
                        geometry: Optional[EngineGeometry] = None,
                        kappa: float = 1.37, smooth: int = 11,
                        theta_min: Optional[float] = None,
                        theta_max: Optional[float] = None, source: str = ""):
    """Pressão medida -> (FitData com x_b e dx_b/dθ, HeatReleaseResult)."""
    from ..optimization.objective import FitData
    if pressure_unit not in PRESSURE_FACTORS_KPA:
        raise ValueError(f"Unidade de pressão deve ser uma de "
                         f"{list(PRESSURE_FACTORS_KPA)}.")
    theta = np.asarray(theta, dtype=float)
    p = np.asarray(p, dtype=float) * PRESSURE_FACTORS_KPA[pressure_unit]
    m = np.ones(theta.size, dtype=bool)
    if theta_min is not None:
        m &= theta >= theta_min
    if theta_max is not None:
        m &= theta <= theta_max
    hr = apparent_heat_release(theta[m], p[m], geometry, kappa, angle_unit,
                               smooth)
    dados = FitData(hr.theta, hr.xb, hr.dxb, angle_unit=angle_unit,
                    source=source)
    return dados, hr
