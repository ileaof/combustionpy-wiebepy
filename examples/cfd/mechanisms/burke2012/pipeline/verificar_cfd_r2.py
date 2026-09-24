# -*- coding: utf-8 -*-
"""Portões R2(b), R2(c) e R2(d) — análise do CASO CFD reativo (OF13).

Lê APENAS as séries de postProcessing do caso (nenhum campo re-parseado):
  gasAvg        → p̄(t), T̄(t), ρ̄(t)        (volAverage)
  gasIntegral   → ∫ρ dV = massa total [kg] (constante — câmara fechada)
  specieMass    → m_H2, m_O2, m_N2, m_H2O  (∫ρY_i dV)
  QdotIntegral  → ∫Q̇_química dV [W]

Portões confrontados (docs/cfd/reactive_roadmap.md, seção R2):
  (b) atraso de ignição no CFD consistente com o 0-D — τ_CFD = instante de
      dT̄/dt máximo (mesmo critério do 0-D em verificar_0d_ignicao.py);
  (c) fechamento de energia (câmara fechada, rígida, ADIABÁTICA):
      ∫∫Q̇ dV dt vs −ΔH_química (entalpia de formação consumida; h do
      Cantera INCLUI h_f°, e E_tot = Σ m_i·h_i(T̄) − p̄·V com campos
      uniformes — validar com gasMin/gasMax antes de usar); o resíduo
      ΔE_tot ≈ 0 é o diagnóstico adiabático;
      h_i(T) do Cantera (Burke2012.yaml — MESMOS dados NASA do
      speciesThermo, implementação independente da janafThermo do OF13);
  (d) passo químico estável: p̄(t) sem oscilação não física fora da janela
      de ignição (residual pico-a-pico das diferenças de p̄ reportado).

Uso:    python verificar_cfd_r2.py <dir_do_caso> [--tol-closure 0.02]
Requer: pip install cantera pyyaml
"""
import argparse
import csv
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def ler_serie(case_dir: Path, fo: str):
    """Série temporal de um functionObject (.dat do postProcessing do
    OF13, separado por espaços; cabeçalho '#' contendo 'Time').

    Retorna (tempos, {coluna: [valores]})."""
    pasta = case_dir / "postProcessing" / fo
    if not pasta.is_dir():
        return None, None
    arq = None
    for sub in sorted((p for p in pasta.iterdir() if p.is_dir()),
                      key=lambda p: p.name, reverse=True):
        cand = sub / "volFieldValue.dat"
        if cand.exists():
            arq = cand
            break
        for f in sorted(sub.glob("*.dat")):
            arq = f
            break
        if arq:
            break
    if arq is None:
        return None, None
    cols, tempos, vals = [], [], {}
    for linha in arq.read_text(encoding="utf-8", errors="replace") \
            .splitlines():
        s = linha.strip()
        if not s:
            continue
        if s.startswith("#"):
            cand = [c for c in s.lstrip("#").split() if c]
            if "Time" in cand:
                cols = cand
            continue
        try:
            nums = [float(x) for x in s.split()]
        except ValueError:
            continue
        if not cols or len(nums) != len(cols):
            continue
        tempos.append(nums[0])
        for k, c in enumerate(cols[1:], start=1):
            vals.setdefault(c, []).append(nums[k])
    return tempos, vals


def atraso_por_dmax(tempo, sinal):
    """Instante da derivada máxima de `sinal` em `tempo` (grade uniforme ou
    quase) — mesmo critério do portão 0-D (dT/dt máximo)."""
    melhor_t, melhor_d = None, 0.0
    for i in range(1, len(tempo)):
        dt = tempo[i] - tempo[i - 1]
        if dt <= 0:
            continue
        d = (sinal[i] - sinal[i - 1]) / dt
        if d > melhor_d:
            melhor_d, melhor_t = d, 0.5 * (tempo[i - 1] + tempo[i])
    return melhor_t, melhor_d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("caso", help="diretório do caso CFD reativo")
    ap.add_argument("--tol-closure", type=float, default=0.02,
                    help="tolerância do fechamento ∫Q̇dVdt vs ΔU (default 2 %)")
    args = ap.parse_args()
    case = Path(args.caso)

    import yaml

    import cantera as ct

    # ——— configuração do caso (volume, mecanismo) ————————————————————
    cfg_caso = yaml.safe_load(
        (case / "case_config.yaml").read_text(encoding="utf-8"))
    V = float(cfg_caso["chamber"]["volume_m3"])
    mec = cfg_caso["reaction"]["mechanism_directory"]
    yaml_mec = Path(mec) / "pipeline" / "Burke2012.yaml"
    gas = ct.Solution(str(yaml_mec))
    print(f"caso:    {case}")
    print(f"volume:  {V:.6e} m³   mecanismo: {yaml_mec.name} "
          f"({gas.n_species} espécies, {gas.n_reactions} reações)")

    # ——— séries ————————————————————————————————————————————————————————
    t_p, p = ler_serie(case, "gasAvg")
    t_T, T = ler_serie(case, "gasAvg")
    t_m, m = ler_serie(case, "specieMass")
    t_q, q = ler_serie(case, "QdotIntegral")
    t_mm, mm = ler_serie(case, "gasMax")
    t_mn, mn = ler_serie(case, "gasMin")
    t_gi, gi = ler_serie(case, "gasIntegral")
    if not t_T or not t_p:
        print("ERRO: séries gasAvg ausentes — caso rodou? (postProcessing/)")
        return 2
    p̄, T̄ = p.get("volAverage(p)", []), T.get("volAverage(T)", [])
    print(f"séries:  {len(t_T)} amostras, t ∈ [{t_T[0]:.3e}, {t_T[-1]:.3e}] s")

    # ——— portão R2(b): atraso de ignição no CFD ———————————————————————
    tau_T, dT_max = atraso_por_dmax(t_T, T̄)
    tau_q = atraso_por_dmax(t_q, q.get("volIntegrate(Qdot)", [0.0] * len(t_q)))[0] \
        if t_q else None
    print(f"\n[portão R2b] atraso de ignição no CFD:")
    print(f"  dT̄/dt máx:      τ = {tau_T * 1e6:.1f} µs  (dT̄/dt = {dT_max:.3e} K/s)")
    if tau_q is not None:
        print(f"  pico de ∫Q̇dV:   τ = {tau_q * 1e6:.1f} µs")
    print("  → confrontar com o 0-D (verificar_0d_ignicao.py, mesmas T0/P0/φ)")

    # ——— portão R2(c): fechamento de energia ——————————————————————————
    # Câmera fechada, rígida e ADIABÁTICA ⇒ dE_tot/dt = 0, com
    #   E_tot(t) = Σ_i m_i(t)·h_i(T̄) − p̄·V   (h do Cantera INCLUI a entalpia
    #   de formação — h_i(T) = h_i^sens(T) + h_f,i°).
    # O Q̇ do OF13 é a liberação química: Q̇ = −Σ_i h_f,i°·ω_i, logo
    #   ∫∫Q̇ dV dt = −ΔH_química,  H_química(t) = Σ_i m_i(t)·h_i(298,15 K),
    # e a energia SENSÍVEL cresce exatamente de ∫Q̇ dV dt:
    #   ΔU_sens = Δ(E_tot − H_química) = ∫∫Q̇ dV dt + ΔE_tot  (ΔE_tot ≈ 0).
    # Confrontos: ∫∫Q̇dVdt vs −ΔH_química (fonte de calor), ΔE_tot ≈ 0
    # (diagnóstico adiabático — caso R2 mediu +0,15 J em 8,5 J de base).
    t_gi, gi = ler_serie(case, "gasIntegral")
    massa_serie = gi.get("volIntegrate(rho)", []) if t_gi else []
    if not t_gi:
        print("ERRO: série gasIntegral ausente (∫ρdV) — necessária para a "
              "energia interna U(t).")
        return 2

    def massa_em(tq):
        # interpolação linear na série gasIntegral
        import bisect
        i = bisect.bisect_left(t_gi, tq)
        i = min(max(i, 1), len(t_gi) - 1)
        f = (tq - t_gi[i - 1]) / (t_gi[i] - t_gi[i - 1])
        return massa_serie[i - 1] + f * (massa_serie[i] - massa_serie[i - 1])

    pref = "volIntegrate(rho"
    colunas = {c[len(pref):].rstrip(")"): c for c in m
               if c.startswith(pref) and len(c) > len(pref)}
    T_ref = 298.15

    def E_H_em(k):
        tk, Tk, Pk = t_T[k], T̄[k], p̄[k]
        tot = sum(m[c][k] for c in colunas.values())
        if tot <= 0:
            return None, None
        ys = {c: m[col][k] / tot for c, col in colunas.items()}
        gas.TPY = Tk, Pk, ys
        h_mix = gas.enthalpy_mass  # J/kg (mistura já definida pelo TPY acima)
        R_s = 8314.462618 / gas.mean_molecular_weight
        E_tot = massa_em(tk) * (h_mix - R_s * Tk)
        # entalpia de formação no estado padrão, com as MASSAS medidas
        H_quim = 0.0
        for c, col in colunas.items():
            gas.TPY = T_ref, 101325.0, {c: 1.0}
            H_quim += m[col][k] * gas.enthalpy_mass
        return E_tot, H_quim

    E0, H0 = E_H_em(0)
    E1, H1 = E_H_em(len(t_T) - 1)
    if t_q and E0 is not None and E1 is not None:
        tempo_q, val_q = t_q, q.get("volIntegrate(Qdot)", [0.0] * len(t_q))
        Q_quim = 0.0
        for i in range(1, len(tempo_q)):
            Q_quim += 0.5 * (val_q[i] + val_q[i - 1]) * (tempo_q[i] - tempo_q[i - 1])
        dH_quim = H1 - H0
        dE = E1 - E0
        fonte = -dH_quim  # energia química consumida = calor liberado
        razao = Q_quim / fonte if abs(fonte) > 1e-30 else float("nan")
        ok = abs(razao - 1.0) <= args.tol_closure
        print(f"\n[portão R2c] fechamento de energia (volume fixo, adiabático):")
        print(f"  ∫∫Q̇ dV dt            = {Q_quim:+.6e} J")
        print(f"  −ΔH_química (formação) = {fonte:+.6e} J")
        print(f"  Q̇/(−ΔH_quím) = {razao:.6f}  "
              f"({'DENTRO' if ok else 'FORA'} da tolerância ±{args.tol_closure:.0%})")
        print(f"  diagnóstico adiabático: ΔE_tot = {dE:+.3e} J "
              f"(deve ser ≈ 0; base |E_tot| = {abs(E1):.3e} J)")

    # ——— portão R2(d): estabilidade do passo químico ——————————————————
    # fora da janela de ignição, p̄ deve evoluir monotonicamente (sem
    # oscilação); reporta o maior reverso de p̄ relativo à variação total.
    reverso_max = 0.0
    for i in range(2, len(t_p)):
        if (p̄[i] - p̄[i - 1]) * (p̄[i - 1] - p̄[i - 2]) < 0:
            reverso_max = max(reverso_max, abs(p̄[i] - p̄[i - 1]))
    var_total = max(p̄) - min(p̄)
    print(f"\n[portão R2d] estabilidade de p̄(t):")
    print(f"  reversos pico-a-pico máximos: {reverso_max:.3e} Pa "
          f"({reverso_max / max(var_total, 1e-30):.3e} da variação total)")
    if t_mm and t_mn:
        print(f"  homogeneidade final: T ∈ [{mn.get('min(T)', [float('nan')])[-1]:.1f}, "
              f"{mm.get('max(T)', [float('nan')])[-1]:.1f}] K, "
              f"p ∈ [{mn.get('min(p)', [float('nan')])[-1]:.0f}, "
              f"{mm.get('max(p)', [float('nan')])[-1]:.0f}] Pa "
              "(T̄/p̄ uniformes ⇔ campos uniformes)")
    print(f"\nreferência: docs/cfd/reactive_roadmap.md (R2) e "
          f"docs/cfd/verification.md (formato do relatório).")
    return 0


if __name__ == "__main__":
    sys.exit(main())