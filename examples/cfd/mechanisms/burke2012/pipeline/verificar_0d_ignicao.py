# -*- coding: utf-8 -*-
"""Portão R2(a): atraso de ignição 0-D do mecanismo Burke 2012 vs shock tube.

Integra um reator homogêneo a volume constante (0-D, sem CFD) com o
Cantera — integrador INDEPENDENTE do OpenFOAM, que lê a conversão ck2yaml
(Burke2012.yaml nesta pasta) dos MESMOS arquivos Chemkin do suplemento
(chem.inp + therm.dat). A conversão OpenFOAM (reactions/speciesThermo) já
foi confrontada verbatim com o PDF em verificar_conversao.py; este script
não re-verifica isso.

Para cada ponto experimental do shock tube (dados_publicados/*.yaml):
  1. monta a mistura a partir de φ e do diluente publicados (nunca
     re-tipados: X_i calculado, Y_i do Cantera);
  2. integra a volume constante com U,P iniciais (o regime do shock tube
     refletido — estado (T5, P5) do experimento);
  3. define o atraso de ignição como o instante de dT/dt máximo
     (critério padrão; o Cantera também reporta via derivada de [OH]);
  4. confronta com o atraso publicado e imprime a razão modelo/medido.

Os pontos publicados entram SOMENTE de arquivo citado (dados_publicados/
com campo fonte). Nenhum número é inventado aqui: sem arquivo de dados,
o script falha com instrução explícita.

Uso:    python verificar_0d_ignicao.py
Requer: pip install cantera pyyaml
"""
import argparse
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

AQUI = Path(__file__).resolve().parent
DADOS = AQUI / "dados_publicados"

MW = {"H2": 2.01594, "O2": 31.9988, "N2": 28.0134, "AR": 39.948, "HE": 4.0026}


def mistura_por_phi(gas, phi, diluente):
    """X_i a partir de φ: H2 + 0.5 O2 (+ bath gas). Frações X fechadas na
    mão (definição de φ), massa total deixada para o Cantera normalizar."""
    x_o2 = 0.5 * phi
    partes = {"H2": phi, "O2": x_o2}
    for esp, x in (diluente or {}).items():
        # diluente citado em razão de O2 (ex.: "N2/O2 = 4") ou fração direta
        partes[esp] = partes.get(esp, 0.0) + x * x_o2
    tot = sum(partes.values())
    gas.TPX = None, None, {k: v / tot for k, v in partes.items()}


def atraso_ignicao(gas, t_max=1e-2, dt_out=1e-6):
    """Reator 0-D a volume constante; retorna (tau_dTdt, tau_OH).

    Integração adaptativa do Cantera com saída em grade uniforme
    (dt_out): o atraso por dT/dt máximo fica resolvido na própria grade.
    """
    import cantera as ct

    reac = ct.IdealGasReactor(gas, clone=False)
    rede = ct.ReactorNet([reac])
    rede.rtol = 1e-10
    rede.atol = 1e-18

    t, T = [], []
    tau_oh, dOh_max = None, 0.0
    oh_prev = 0.0
    i_oh = gas.species_index("OH") if "OH" in gas.species_names else None
    while rede.time < t_max:
        rede.advance(min(rede.time + dt_out, t_max))
        tt, TT = rede.time, reac.T
        t.append(tt)
        T.append(TT)
        oh = gas.X[i_oh] if i_oh is not None else 0.0
        if len(t) >= 2:
            dOh = (oh - oh_prev) / (tt - t[-2])
            if dOh > dOh_max:
                dOh_max, tau_oh = dOh, tt
        oh_prev = oh
    # atraso por dT/dt máximo na grade uniforme
    tau_dt, dT_max = None, 0.0
    for i in range(1, len(t)):
        d = (T[i] - T[i - 1]) / (t[i] - t[i - 1])
        if d > dT_max:
            dT_max = d
            tau_dt = 0.5 * (t[i - 1] + t[i])
    return tau_dt, tau_oh


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mecanismo", default=str(AQUI / "Burke2012.yaml"))
    ap.add_argument("--t-max", type=float, default=1e-2,
                    help="horizonte de integração (s); precisa conter a "
                         "ignição de todos os pontos")
    args = ap.parse_args()

    import yaml

    import cantera as ct

    arq_dados = sorted(DADOS.glob("*.yaml"))
    if not arq_dados:
        print("ERRO: nenhum dataset em dados_publicados/*.yaml — extrair os "
              "pontos do paper ANTES (nenhum dado é inventado aqui).")
        return 2

    gas = ct.Solution(args.mecanismo)
    print(f"mecanismo: {Path(args.mecanismo).name} "
          f"({gas.n_species} espécies, {gas.n_reactions} reações)")

    total, fora = 0, 0
    for arq in arq_dados:
        dset = yaml.safe_load(arq.read_text(encoding="utf-8"))
        fonte = dset.get("fonte") or "?"
        cond = dset.get("condicoes") or {}
        print(f"\n=== {dset.get('dataset', arq.stem)} — {fonte}")
        print(f"    condições: {cond}")
        for ponto in dset.get("pontos", []):
            T0 = float(ponto["T_K"])
            P0 = float(ponto["P_atm"]) * ct.one_atm
            phi = float(ponto.get("phi", 1.0))
            gas.TP = T0, P0
            mistura_por_phi(gas, phi, ponto.get("diluente"))
            tau_m, tau_oh = atraso_ignicao(gas, args.t_max)
            tau_e = float(ponto["tau_us"]) * 1e-6
            total += 1
            if tau_m is None:
                fora += 1
                print(f"  T={T0:7.1f} K  P={ponto['P_atm']} atm  φ={phi}: "
                      f"sem ignição em {args.t_max:g} s — aumentar --t-max")
                continue
            razao = tau_m / tau_e
            print(f"  T={T0:7.1f} K  P={ponto['P_atm']} atm  φ={phi}: "
                  f"0-D={tau_m * 1e6:8.1f} µs  medido={ponto['tau_us']:8.1f} µs  "
                  f"razão={razao:5.2f}  (dT/dt; [OH]→{tau_oh * 1e6:.1f} µs)")
    print(f"\npontos confrontados: {total} ({fora} sem ignição no horizonte)")
    return 0


if __name__ == "__main__":
    sys.exit(main())