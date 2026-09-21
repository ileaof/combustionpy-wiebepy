# -*- coding: utf-8 -*-
"""
generate_synthetic.py — Gera os dados sintéticos de teste em examples/data/.

Para N = 1..5 estágios com parâmetros conhecidos (graus), grava
synthetic_<N>stage.csv com colunas theta,xb,dxb_dtheta e ruído gaussiano
(σ_x = 0.002 em x_b; σ_d = 2 % do pico em dx_b/dθ), além de
true_parameters.json com os valores verdadeiros. Semente fixa: os arquivos
são reprodutíveis.

    python examples/generate_synthetic.py
"""
import json
import sys
from pathlib import Path

import numpy as np

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent / "src"))

from wiebepy.core import (Stage, multistage_wiebe,  # noqa: E402
                          multistage_wiebe_derivative)

VERDADE = {
    1: [Stage(1.0, -10.0, 60.0, 2.0)],
    2: [Stage(0.35, -5.0, 12.0, 2.0), Stage(0.65, 2.0, 45.0, 1.3)],
    3: [Stage(0.2, -8.0, 10.0, 2.5), Stage(0.5, 0.0, 30.0, 1.2),
        Stage(0.3, 15.0, 50.0, 0.8)],
    4: [Stage(0.15, -8.0, 8.0, 3.0), Stage(0.35, -2.0, 25.0, 1.5),
        Stage(0.3, 10.0, 40.0, 1.0), Stage(0.2, 30.0, 50.0, 0.6)],
    5: [Stage(0.1, -10.0, 6.0, 3.0), Stage(0.25, -4.0, 18.0, 2.0),
        Stage(0.3, 5.0, 30.0, 1.2), Stage(0.2, 20.0, 45.0, 0.9),
        Stage(0.15, 40.0, 50.0, 0.5)],
}


def main():
    destino = AQUI / "data"
    destino.mkdir(exist_ok=True)
    theta = np.arange(-20.0, 100.0 + 1e-9, 0.2)
    rng = np.random.default_rng(2024)
    for n, st in VERDADE.items():
        xb = multistage_wiebe(theta, st)
        dxb = multistage_wiebe_derivative(theta, st)
        xb_r = xb + rng.normal(0.0, 0.002, theta.size)
        dxb_r = dxb + rng.normal(0.0, 0.02 * dxb.max(), theta.size)
        caminho = destino / f"synthetic_{n}stage.csv"
        with open(caminho, "w", encoding="utf-8") as fh:
            fh.write(f"# sintético {n}-Wiebe (graus); ver true_parameters.json\n")
            fh.write("theta,xb,dxb_dtheta\n")
            for t, x, d in zip(theta, xb_r, dxb_r):
                fh.write(f"{t:.4f},{x:.6f},{d:.8f}\n")
        print(f"gravado {caminho}")
    (destino / "true_parameters.json").write_text(json.dumps(
        {str(n): [s.to_dict() for s in st] for n, st in VERDADE.items()},
        indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
