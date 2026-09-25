# -*- coding: utf-8 -*-
"""
geometry.py — Geometria parametrizada e malha do domínio de fresta.

Domínio do SUBMODELO (fresta + coluna de gás de entrada), em corte
r–z com setor periódico (condição wedge):

             ┌─ BC da câmara (p(θ) prescrita) ─┐   z = h_tl + h_buf
             │      buffer (gás da câmara)      │
             ├─ boca da fresta ─────────────────┤   z = h_tl
             │ fresta (folga radial g)          │
             ├─ fundo fechado (1º anel) ────────┤   z = 0
               r_i = D/2 − g          r_o = D/2

    • r_i (parede interna)  = top land do pistão → thermal.piston_wall
    • r_o (parede externa)  = liner              → thermal.liner_wall
    • fundo fechado (z = 0) = flanco acima do 1º anel → piston_wall
      (fase 1: fresta comunica APENAS com a câmara — não é blow-by)

O setor periódico (wedge) só é válido porque a geometria e as condições
de contorno são uniformes na circunferência: a pressão prescrita da
câmara é espacialmente uniforme e a fresta é anelar completa. Uma
abertura localizada do anel NÃO pode ser representada neste setor
(regra do escopo §4).

Referencial solidário ao pistão: geometria CONSTANTE (o liner desliza
sobre si mesmo) — a malha é estática; a velocidade relativa da parede
do liner entra como velocidade de parede axial (Couette).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .config import CreviceConfig, CreviceConfigError

PAREDES = ("chamber", "liner", "piston", "front", "back")

DESCRICAO_DOMINIO = (
    "Submodelo de fresta top-land: anelar (setor wedge), fundo fechado "
    "no flanco acima do 1º anel, boca na câmara através de um buffer de "
    "gás; pressão da câmara prescrita como condição de contorno — o "
    "escoamento calculado NÃO modifica essa pressão (não é acoplamento "
    "bidirecional).")


@dataclass
class CreviceDomain:
    """Dimensões do domínio em SI, derivadas da config."""

    cfg: CreviceConfig

    @property
    def bore(self) -> float:
        return self.cfg.geometry.bore_diameter_mm * 1e-3

    @property
    def gap(self) -> float:
        return self.cfg.geometry.radial_gap_mm * 1e-3

    @property
    def h_tl(self) -> float:
        return self.cfg.geometry.top_land_height_mm * 1e-3

    @property
    def h_buf(self) -> float:
        return self.cfg.geometry.buffer_height_mm * 1e-3

    @property
    def r_i(self) -> float:
        return self.bore / 2.0 - self.gap

    @property
    def r_o(self) -> float:
        return self.bore / 2.0

    @property
    def sector(self) -> float:
        """Ângulo do setor [rad]."""
        return math.radians(self.cfg.geometry.sector_angle_deg)

    @property
    def h_total(self) -> float:
        return self.h_tl + self.h_buf

    def validate(self) -> None:
        if self.gap <= 0 or self.r_i <= 0:
            raise CreviceConfigError(
                "geometria inválida: folga radial consome o raio inteiro")
        if self.gap > 0.02 * self.bore:
            raise CreviceConfigError(
                "folga radial > 2 % do diâmetro: domínio anelar fino é a "
                "premissa da malha e do volume declarado (g ≪ D)")
        if self.h_total <= 0:
            raise CreviceConfigError("altura total do domínio ≤ 0")

    # ------------------------------------------------------------- dimensões
    def cell_dims(self) -> Dict[str, float]:
        """Escala mínima e razão de aspecto das células (informadas ao
        usuário e ao relatório — §8)."""
        m = self.cfg.mesh
        dr = self.gap / m.n_gap
        dz_cr = self.h_tl / m.n_crevice_axial
        dz_bf = self.h_buf / m.n_buffer_axial
        dz = max(dz_cr, dz_bf)
        return {"delta_r_m": dr, "delta_z_m": dz,
                "delta_tang_m": self.r_med_tangential(),
                "aspect_ratio": dz / dr if dr else float("inf"),
                "n_cells": self.n_cells()}

    def r_med_tangential(self) -> float:
        """Extensão tangencial média do setor (no meio da folga)."""
        return ((self.r_i + self.r_o) / 2.0) * self.sector

    def n_cells(self) -> int:
        m = self.cfg.mesh
        return m.n_gap * (m.n_crevice_axial + m.n_buffer_axial) \
            * m.sector_cells

    # ------------------------------------------------------------- vértices
    def _vertices(self):
        """8 vértices do bloco hexa do setor na convenção do blockMesh
        (x: 0→1 = radial; y: 0→3 = tangencial; z: 0→4 = axial; faces
        0-3 e 4-7 correspondentes — o setor é simétrico em torno do
        plano y=0, condição wedge do OF)."""
        import numpy as np
        si = math.sin(self.sector / 2.0)
        ci = math.cos(self.sector / 2.0)
        r_i, r_o, h = self.r_i, self.r_o, self.h_total
        # (x, y, z); x = r·cos(∓α/2), y = r·sin(∓α/2)
        return np.array([
            [r_i * ci, -r_i * si, 0.0],      # 0
            [r_o * ci, -r_o * si, 0.0],      # 1  (+x = radial p/ fora)
            [r_o * ci, r_o * si, 0.0],       # 2  (x+y)
            [r_i * ci, r_i * si, 0.0],       # 3  (+y = tangencial)
            [r_i * ci, -r_i * si, h],        # 4  (+z = axial)
            [r_o * ci, -r_o * si, h],        # 5
            [r_o * ci, r_o * si, h],         # 6
            [r_i * ci, r_i * si, h],         # 7
        ])

    def blockmesh_dict(self) -> str:
        m = self.cfg.mesh
        v = self._vertices()
        pts = "\n".join(f"    ({v[i,0]:.8g} {v[i,1]:.8g} {v[i,2]:.8g})"
                        for i in range(8))
        gr = m.gap_grading
        # z: dois trechos (fresta + buffer) — grading único com transição
        # simples: fração axial proporcional às células
        return f"""/*--------------------------------*- C++ -*----------------------------------*\\
| blockMeshDict — gerado por wiebepy.crevice_flow (setor wedge anelar)       |
| Submodelo top-land crevice: fresta (fundo fechado) + buffer de câmara.    |
| Referencial solidário ao pistão — geometria constante, malha estática.    |
\\*---------------------------------------------------------------------------*/
FoamFile
{{
    format          ascii;
    class           dictionary;
    object          blockMeshDict;
}}

convertToMeters 1;

vertices
(
{pts}
);

blocks
(
    hex (0 1 2 3 4 5 6 7)
    ({m.n_gap} {m.sector_cells} {m.n_crevice_axial + m.n_buffer_axial})
    simpleGrading (1 1 1)
);

edges ();

boundary
(
    chamber
    {{
        type patch;
        faces
        (
            (4 5 6 7)
        );
    }}
    liner
    {{
        type wall;
        faces
        (
            (1 2 6 5)
        );
    }}
    piston
    {{
        type wall;
        faces
        (
            (0 1 2 3)
            (0 4 7 3)
        );
    }}
    front
    {{
        type wedge;
        faces
        (
            (0 1 5 4)
        );
    }}
    back
    {{
        type wedge;
        faces
        (
            (3 2 6 7)
        );
    }}
);

mergePatchPairs
(
);
"""

    def topo_set_dict(self) -> str:
        """Divide o domínio em ZONAS crevice (z < h_tl) e buffer
        (``cellZoneSet`` — os volFieldValue consomem cellZone)."""
        return f"""/* topoSet — zonas do submodelo crevice_flow */
FoamFile
{{
    format          ascii;
    class           dictionary;
    object          topoSetDict;
}}

actions
(
    {{
        name    crevice;
        type    cellZoneSet;
        action  new;
        source  boxToCell;
        box     (-1 -1 -1) (1 1 {self.h_tl:.8g});
    }}
    {{
        name    buffer;
        type    cellZoneSet;
        action  new;
        source  boxToCell;
        box     (-1 -1 {self.h_tl:.8g}) (1 1 1);
    }}
);
"""


def piston_speed_table(cfg: CreviceConfig, n: int = 361):
    """v_p(θ) [m/s] ao longo da janela (cinemática biela-manivela do
    wiebepy, mesma fórmula do 0-D). Retorna (theta_deg, v_z). Positivo
    para o pistão descendo (expansão); o liner, no referencial do
    pistão, move-se com −v_p."""
    th0, th1 = cfg.window
    step = (th1 - th0) / (n - 1)
    r = (cfg.motion.stroke_mm or 0.0) * 1e-3 / 2.0
    l = (cfg.motion.rod_length_mm or 0.0) * 1e-3
    om = 2.0 * math.pi * cfg.motion.rpm / 60.0
    th, vz = [], []
    for i in range(n):
        a = math.radians(th0 + i * step)
        s, c = math.sin(a), math.cos(a)
        dy = r * s * (1.0 + r * c / math.sqrt(l * l - r * r * s * s))
        th.append(th0 + i * step)
        vz.append(dy * om)
    return th, vz