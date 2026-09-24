# -*- coding: utf-8 -*-
"""Ajusta coeficientes de Sutherland (As, Ts) à viscosidade Chapman-Enskog
(Lennard-Jones) das 13 espécies do mecanismo Burke 2012. Salva o resultado
em sutherland_fit.json (nesta pasta); os valores vão para o dict
transportProperties na pasta do mecanismo (nível acima).

Dados LJ: Burke2012.yaml (SDToolbox, Caltech) — valores da base de dados
de transporte GRI-Mech 3.0 (Kee et al.).
Validação do procedimento: o ajuste de N2 e O2 deve reproduzir os valores
publicados no tutorial OF13 counterFlowFlame2D (N2: 1.401e-6/107;
O2: 1.753e-6/139) dentro de ~5%. As diferenças (N2 +27% em As, +75% em Ts)
vêm de bases LJ publicadas distintas (GRI-3.0 vs CHEMKIN TRANSPORT
clássico) — ver README.md.
"""
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

AQUI = Path(__file__).resolve().parent

# LJ: (diametro sigma [Angstrom], profundidade eps/kB [K], molWeight)
# do Burke2012.yaml (transporte GRI) + M do mecanismo
LJ = {
    "H":    (2.05,  145.0, 1.008),
    "H2":   (2.92,  38.0,  2.0156),
    "O":    (2.75,  80.0,  15.999),
    "OH":   (2.75,  80.0,  17.0068),
    "H2O":  (2.605, 572.4, 18.0153),
    "O2":   (3.458, 107.4, 31.9988),
    "HO2":  (3.458, 107.4, 33.0068),
    "H2O2": (3.458, 107.4, 34.0147),
    "N2":   (3.621, 97.53, 28.0134),
    "AR":   (3.33,  136.5, 39.948),
    "HE":   (2.576, 10.2,  4.0026),
    "CO":   (3.65,  98.1,  28.0104),
    "CO2":  (3.763, 244.0, 44.0098),
}
# valores publicados no OF13 (tutorial counterFlowFlame2D) para validação
REF = {"N2": (1.401e-6, 107.0), "O2": (1.753e-6, 139.0)}

T = np.geomspace(300.0, 3500.0, 80)


def omega_neufeld(Tstar):
    """Integral de colisão Omega(1,1) — correlação de Neufeld et al. (1972)."""
    A, B, C, D = 1.06036, 0.15610, 0.19300, 0.47635
    E, F, G, H = 1.03587, 1.52996, 1.76474, 3.89411
    return A / Tstar**B + C / np.exp(D * Tstar) \
        + E / np.exp(F * Tstar) + G / np.exp(H * Tstar)


def mu_ce(sig, eps, M, T):
    """Viscosidade Chapman-Enskog [Pa·s]; sig [Å], M [g/mol]."""
    Tstar = T / eps
    Om = omega_neufeld(Tstar)
    return 2.6693e-6 * np.sqrt(M * T) / (sig**2 * Om)


def mu_suth(As, Ts, T):
    return As * np.sqrt(T) / (1.0 + Ts / T)


out = {}
for sp, (sig, eps, M) in LJ.items():
    mu = mu_ce(sig, eps, M, T)

    def resid(p):
        return np.log(mu_suth(p[0], p[1], T)) - np.log(mu)

    r = least_squares(resid, [1.5e-6, 150.0])
    As, Ts = r.x
    err = np.max(np.abs(np.exp(resid(r.x)) - 1.0))
    out[sp] = (As, Ts)
    linha = f"{sp:5s} As={As:.6g} Ts={Ts:.4g} (erro máx do ajuste {err:.2%})"
    if sp in REF:
        a0, t0 = REF[sp]
        linha += f"  | OF13: {a0:.4g}/{t0:.0f} → dif As={100*(As-a0)/a0:+.1f}% " \
                 f"Ts={100*(Ts-t0)/t0:+.1f}%"
    print(linha)

import json
json.dump({k: list(v) for k, v in out.items()},
          open(AQUI / "sutherland_fit.json", "w"), indent=1)
print("\nsalvo em sutherland_fit.json")