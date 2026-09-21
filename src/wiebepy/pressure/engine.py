# -*- coding: utf-8 -*-
"""
engine.py — Motor do modelo 0-D (mesmas equações e padrões do Double Wiebe).

Geometria biela-manivela (θ em rad, θ = 0 no PMS de combustão):

    r = s/2,  R = l/r,  Vd = π(d/2)²·s,  Vc = Vd/(Rc − 1)
    V(θ)   = Vc + Vd/2·[R + 1 − cos θ − √(R² − sin²θ)]
    dV/dθ  = Vd·sin θ/2·[1 + cos θ/√(R² − sin²θ)]
    y(θ)   = l + r − r cos θ − √(l² − r² sin²θ)
    A_s(θ) = 2π(d/2)² + π d y(θ) + π d s/(Rc − 1)

Q_total = m_comb · PCI [kJ/ciclo]; Vp = 2 s (rpm/60).
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Dict, List


@dataclass
class EngineConfig:
    bore: float = 0.086              # diâmetro [m]
    stroke: float = 0.070            # curso [m]
    rod_length: float = 0.1175       # biela [m]
    rpm: float = 3396.20             # rotação [rpm]
    Rc: float = 17.0                 # razão de compressão [-]
    m_fuel: float = 9.42754647351e-6 # massa de combustível [kg/ciclo]
    LHV: float = 39191.3             # PCI [kJ/kg]
    kappa: float = 1.37              # razão de calores específicos [-]
    T1: float = 308.15               # temperatura no início da integração [K]
    Tw: float = 440.0                # temperatura da parede [K]
    heat_transfer: bool = True       # perda de calor por Hohenberg

    @property
    def r_crank(self) -> float:
        return self.stroke / 2.0

    @property
    def R(self) -> float:
        return self.rod_length / self.r_crank

    @property
    def Vd(self) -> float:
        return math.pi * (self.bore / 2.0) ** 2 * self.stroke

    @property
    def omega_rev_s(self) -> float:
        return self.rpm / 60.0

    @property
    def Vp(self) -> float:
        return 2.0 * self.stroke * self.omega_rev_s

    @property
    def Q_total(self) -> float:
        return self.m_fuel * self.LHV

    def validate(self) -> List[str]:
        e = []
        for nome in ("bore", "stroke", "rod_length", "rpm", "m_fuel", "LHV",
                     "T1", "Tw"):
            if not getattr(self, nome) > 0:
                e.append(f"{nome} deve ser > 0.")
        if not self.Rc > 1:
            e.append("Rc deve ser > 1.")
        if not 1.0 < self.kappa < 2.0:
            e.append("kappa deve estar entre 1 e 2.")
        if self.rod_length <= self.r_crank:
            e.append("A biela deve ser maior que o raio da manivela.")
        return e

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict) -> "EngineConfig":
        """Aceita as chaves desta classe ou as do YAML do Double Wiebe
        (bore_mm, stroke_mm, rod_length_mm, m_fuel_kg_per_cycle, …)."""
        mapa = {"bore_mm": ("bore", 1e-3), "stroke_mm": ("stroke", 1e-3),
                "rod_length_mm": ("rod_length", 1e-3),
                "m_fuel_kg_per_cycle": ("m_fuel", 1.0),
                "LHV_kJ_per_kg": ("LHV", 1.0), "T1_K": ("T1", 1.0),
                "Tw_K": ("Tw", 1.0)}
        kw = {}
        for k, v in (d or {}).items():
            if k in mapa:
                kw[mapa[k][0]] = float(v) * mapa[k][1]
            elif k in cls.__dataclass_fields__:
                kw[k] = v
        return cls(**kw)

    def constants(self) -> Dict[str, float]:
        """Constantes usadas pelos kernels (tudo em SI/kPa/kJ)."""
        return {"Vd": self.Vd, "R": self.R, "bore": self.bore,
                "stroke": self.stroke, "rod": self.rod_length,
                "kappa": self.kappa, "T1": self.T1, "Tw": self.Tw,
                "Qtot": self.Q_total, "Vp_fac": (self.Vp + 1.4) ** 0.8,
                "om2pi": 2.0 * math.pi * self.omega_rev_s,
                "heat": 1 if self.heat_transfer else 0}


def volume(theta, Rc, e: EngineConfig, xp=None):
    """(V, dV/dθ, A_s) para θ (array) e Rc (escalar ou broadcastável)."""
    import numpy as np
    xp = xp or np
    s, c = xp.sin(theta), xp.cos(theta)
    raiz = xp.sqrt(e.R ** 2 - s * s)
    Vc = e.Vd / (Rc - 1.0)
    V = Vc + e.Vd / 2.0 * (e.R + 1.0 - c - raiz)
    dV = e.Vd * s / 2.0 * (1.0 + c / raiz)
    r = e.r_crank
    y = e.rod_length + r - r * c - xp.sqrt(e.rod_length ** 2 - r * r * s * s)
    As = (2.0 * math.pi * (e.bore / 2.0) ** 2 + math.pi * e.bore * y
          + math.pi * e.bore * e.stroke / (Rc - 1.0))
    return V, dV, As
