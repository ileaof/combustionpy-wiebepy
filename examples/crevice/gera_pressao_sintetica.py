# -*- coding: utf-8 -*-
"""
gera_pressao_sintetica.py — DEMO: gera uma tabela de pressão da câmara
SINTÉTICA (compressão/expansão politrópica com pico em torno do PMS) para
os exemplos do crevice_flow.

ATENÇÃO: os números são DEMONSTRATIVOS e claramente identificados como
sintéticos — NÃO representam o ensaio P_exp-Carga-3_45% nem nenhum motor
real. Para um caso real, use o arquivo do ensaio (crevice.chamber.source:
"experiment") ou a saída do modelo 0-D (source: "zero_d").

Uso:  python gera_pressao_sintetica.py [arquivo.csv] [rpm] [pico_bar]
"""
import math
import sys

import numpy as np

COLUNAS = "theta_deg,P_bar"


def gera(rpm: float = 1500.0, pico_bar: float = 55.0,
         p1_bar: float = 1.0, n: float = 1.35):
    """Curva MOTOREDA sintética: p = p1·(V(θ)/V_PMI)^(−n) — pico no PMS
    dado pela razão de compressão demonstrativa. Sem combustão (demo)."""
    stroke, rod, rc = 70e-3, 130e-3, 16.5      # demo: Rc 16,5
    r, l = stroke / 2, rod
    th = np.linspace(-180.0, 180.0, 721)
    s, c = np.sin(np.radians(th)), np.cos(np.radians(th))
    y = l + r - r * c - np.sqrt(l * l - r * r * s * s)      # deslocamento
    A = math.pi * (43e-3) ** 2
    folga = stroke / (rc - 1.0)              # altura de folga do Rc demo
    V = A * (y + folga)
    V_pmi = V.max()
    p = p1_bar * (V / V_pmi) ** (-n)
    if pico_bar > 0:
        p = p * (pico_bar / p.max())
    return th, p


def main() -> int:
    arq = sys.argv[1] if len(sys.argv) > 1 else "pressao_sintetica.csv"
    rpm = float(sys.argv[2]) if len(sys.argv) > 2 else 1500.0
    pico = float(sys.argv[3]) if len(sys.argv) > 3 else 55.0
    th, p = gera(rpm=rpm, pico_bar=pico)
    with open(arq, "w", encoding="utf-8") as fh:
        fh.write("# SINTÉTICO — demo crevice_flow (não é dado de ensaio)\n")
        fh.write(COLUNAS + "\n")
        for t, pv in zip(th, p):
            fh.write(f"{t:.3f},{pv:.6f}\n")
    print(f"escrito {arq}: {len(th)} pontos, pico {p.max():.2f} bar "
          f"({rpm:.0f} rpm) — DADOS SINTÉTICOS DEMO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())