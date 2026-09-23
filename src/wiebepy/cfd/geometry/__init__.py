# -*- coding: utf-8 -*-
"""
geometry — Geometria paramétrica simplificada (cilindro + pistão) e
cinemática biela-manivela.

Reutiliza ``EngineConfig`` e ``volume()`` do modelo 0-D existente
(``wiebepy.pressure.engine``) — diâmetro, curso, biela, Rc, rotação e
referência angular do PMS são os MESMOS parâmetros usados nos modos de
fração queimada e pressão (§8). Nenhuma nova fórmula de cinemática é
introduzida aqui.

A geometria 3D gerada é uma câmara simplificada (cilindro + pistão
plano). Ela NÃO representa automaticamente a geometria real do ensaio —
diferenças de câmara, válvulas e dome mudam o escoamento.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict

# Hipóteses documentadas da geometria simplificada (registradas no
# relatório do caso):
SIMPLIFIED_GEOMETRY_HYPOTHESES = (
    "Geometria simplificada de cilindro com pistão plano (sem válvulas, "
    "sem dome de câmara): representa o intervalo de válvulas fechadas de "
    "uma câmara genérica, NÃO a geometria real do ensaio.",
    "Somente o intervalo simulado (válvulas fechadas) é resolvido; as "
    "trocas de carga (admissão/escape) ficam fora do domínio.",
    "Movimento inicial da carga: fluido em repouso no instante inicial, "
    "com pressão e temperatura uniformes (hipótese declarada; swirl/tumble "
    "reais do ensaio não são impostos).",
)


@dataclass
class PistonKinematics:
    """Posição do pistão e volume instantâneos (reutiliza o 0-D)."""
    bore: float            # [m]
    stroke: float          # [m]
    rod_length: float      # [m]
    Rc: float              # [-]
    rpm: float

    @property
    def r_crank(self) -> float:
        return self.stroke / 2.0

    @property
    def Vd(self) -> float:
        return math.pi * (self.bore / 2.0) ** 2 * self.stroke

    def volume(self, theta_rad: float) -> float:
        """Volume da câmara em θ (rad, 0 = PMS de combustão)."""
        from ...pressure.engine import EngineConfig, volume
        e = EngineConfig(bore=self.bore, stroke=self.stroke,
                         rod_length=self.rod_length, Rc=self.Rc,
                         rpm=self.rpm)
        V, _, _ = volume(theta_rad, self.Rc, e)
        return V

    def piston_displacement(self, theta_rad: float) -> float:
        """Deslocamento axial do pistão desde o PMS [m] (para baixo, +z):

        y(θ) = l + r − r·cos θ − √(l² − r²·sin²θ)   (mesma fórmula do 0-D)
        """
        r, l = self.r_crank, self.rod_length
        s, c = math.sin(theta_rad), math.cos(theta_rad)
        return l + r - r * c - math.sqrt(l * l - r * r * s * s)

    def omega(self) -> float:
        """Velocidade angular [rad/s]."""
        return 2.0 * math.pi * self.rpm / 60.0

    def consistency_errors(self) -> list:
        """Consistência geométrica (Rc × volume de folga — §8)."""
        e = []
        Vc = self.Vd / (self.Rc - 1.0)
        if Vc <= 0:
            e.append("Volume de folga não positivo para o Rc dado.")
        if self.rod_length <= self.r_crank:
            e.append("A biela deve ser maior que o raio da manivela.")
        return e


def motion_report(k: PistonKinematics, theta0_rad: float,
                  theta1_rad: float) -> Dict:
    """Resumo do movimento do pistão no intervalo simulado (para docs e
    relatório): deslocamentos, volumes e hipóteses."""
    V0 = k.volume(theta0_rad)
    V1 = k.volume(theta1_rad)
    n = 720
    Vmin = Vmax = V0
    y_min = y_max = 0.0
    for i in range(n + 1):
        a = theta0_rad + (theta1_rad - theta0_rad) * i / n
        V = k.volume(a)
        Vmin, Vmax = min(Vmin, V), max(Vmax, V)
        y = k.piston_displacement(a)
        y_min, y_max = min(y_min, y), max(y_max, y)
    return {"theta_start_deg": math.degrees(theta0_rad),
            "theta_end_deg": math.degrees(theta1_rad),
            "piston_displacement_start_m": 0.0,
            "piston_displacement_end_m": k.piston_displacement(theta1_rad),
            "piston_displacement_range_m": (y_min, y_max),
            "V_start_m3": V0, "V_end_m3": V1,
            "V_min_m3": Vmin, "V_max_m3": Vmax,
            "instantaneous_Rc_range": (Vmax / Vmin,) if Vmin > 0 else (),
            "rpm": k.rpm, "omega_rad_s": k.omega(),
            "Vd_m3": k.Vd,
            "hypotheses": list(SIMPLIFIED_GEOMETRY_HYPOTHESES)}


__all__ = ["PistonKinematics", "motion_report",
           "SIMPLIFIED_GEOMETRY_HYPOTHESES"]