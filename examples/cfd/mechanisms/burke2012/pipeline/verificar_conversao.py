# -*- coding: utf-8 -*-
"""Verificação mecânica da conversão chemkinToFoam do mecanismo Burke 2012.

Compara, espécie a espécie e reação a reação, os coeficientes convertidos
(../reactions e ../speciesThermo, formato OpenFOAM) contra os valores
VERBATIM do suplemento do paper (extracao_suplemento.txt nesta pasta).
Nenhuma comparação manual: tudo extraído e confrontado por código.

  - NASA-7: 14 coeficientes por espécie (5+2 alto / 2+3+4 baixo; Tint
    descartado)
  - Arrhenius: A com o fator de conversão do próprio chemkinReader
    (Afactor = 0.001^(n_conc-1), onde n_conc conta os fatores de
    concentração do lado esquerdo, M inclusive — ver chemkinReader.C),
    beta idêntico, Ta = Ea/RRcal com RRcal = 1.987316 cal/(mol K),
    constante do próprio lexer do OF13 (chemkinLexer.L)
  - Eficiências de terceiro corpo e parâmetros TROE
  - Massas molares

Uso:    python verificar_conversao.py
"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

AQUI = Path(__file__).resolve().parent
MEC = AQUI.parent

R_CAL = 1.987316  # cal/(mol K) — constante usada pelo próprio lexer do OF13
# (chemkinLexer.L: "static const scalar RRcal = 1.987316;")

txt = (AQUI / "extracao_suplemento.txt").read_text(encoding="utf-8")

# ---------- thermo: 13 entradas NASA verbatim ----------
pag = txt[txt.index("===== PAGINA 105 ====="):txt.index("===== PAGINA 109 =====")]
t0 = pag.index("THERMO ALL")
thermo_txt = pag[t0:pag.index("!******", t0)]
linhas = thermo_txt.splitlines()
pat = re.compile(r"[+-]?\d*\.\d+E[+-]\d+")
pdf_thermo = {}
for i, ln in enumerate(linhas):
    if len(ln) > 44 and ln[44] == "G" and not ln.startswith("!"):
        nome = ln[:18].strip()
        coefs = ([float(x) for x in pat.findall(linhas[i+1])]
                 + [float(x) for x in pat.findall(linhas[i+2])]
                 + [float(x) for x in pat.findall(linhas[i+3])])
        assert len(coefs) in (14, 15), (nome, coefs)
        pdf_thermo[nome] = coefs[:14]
assert len(pdf_thermo) == 13, pdf_thermo.keys()

# ---------- speciesThermo (formato OF) ----------
st = (MEC / "speciesThermo").read_text(encoding="utf-8")
of_thermo = {}
for m in re.finditer(
        r"^(\S+)\n\{\n.*?highCpCoeffs\s+\(([^)]+)\);\s*"
        r"lowCpCoeffs\s+\(([^)]+)\);", st, re.S | re.M):
    of_thermo[m.group(1)] = ([float(x) for x in m.group(2).split()],
                             [float(x) for x in m.group(3).split()])
assert len(of_thermo) == 13, of_thermo.keys()

erros = 0
for nome, coefs in sorted(pdf_thermo.items()):
    hi, lo = coefs[:7], coefs[7:]
    of_hi, of_lo = of_thermo[nome]
    for k, (a, b) in enumerate(zip(hi, of_hi)):
        if abs(a - b) > 1e-6 * max(1.0, abs(a)):
            print(f"  THERMO {nome} high[{k}]: PDF={a} OF={b}")
            erros += 1
    for k, (a, b) in enumerate(zip(lo, of_lo)):
        if abs(a - b) > 1e-6 * max(1.0, abs(a)):
            print(f"  THERMO {nome} low[{k}]: PDF={a} OF={b}")
            erros += 1
print(f"thermo: {len(pdf_thermo)} espécies x 14 coefs conferidos, {erros} divergências")

# ---------- reações ----------
sec = txt[txt.index("REACTIONS"):txt.index("\nEND", txt.index("REACTIONS")) + 4]
# remove artefatos de quebra de página do PDF
sec = "\n".join(ln for ln in sec.splitlines()
                if not re.match(r"^\s*(===== PAGINA|\s{0,3}1\d{2})\s*$", ln))
# sem linhas de comentário (o bloco AR/HE comentado tem LOW/TROE próprios)
sec_nc = "\n".join(ln for ln in sec.splitlines()
                   if not ln.lstrip().startswith("!"))
pdf_rx = []
for ln in sec_nc.splitlines():
    ln = ln.strip()
    if (not ln or ln.startswith("REACTIONS") or ln.startswith("END")
            or "LOW/" in ln or "HIGH/" in ln or "TROE/" in ln
            or re.match(r"^[A-Z0-9]{1,4}\s*/", ln) or ln.startswith("DUPLICATE")
            or re.match(r"^\s+[A-Z0-9]{1,4}/", ln)):
        continue
    m = re.match(r'^(.+?)\s+([\d.]+[Ee][+-]\d+|\d+\.)\s+([+-]?[\d.]+)\s+'
                 r'([+-]?[\d.]+[Ee][+-]\d+)?\s*$', ln)
    if m and "=" in ln:
        pdf_rx.append((m.group(1).strip(), float(m.group(2)), float(m.group(3)),
                       float(m.group(4)) if m.group(4) else None))
print(f"reações no PDF: {len(pdf_rx)}")
assert len(pdf_rx) == 27, [r[0] for r in pdf_rx]

ro = (MEC / "reactions").read_text(encoding="utf-8")
# separa os 27 blocos por tipo; Troe tem k0/kInf/F em vez de A/beta/Ta
of_troe = {}
of_rx = []
for m in re.finditer(r"un-named-reaction-(\d+)\n    \{\n(.*?)\n    \}", ro, re.S):
    idx, corpo = int(m.group(1)), m.group(2)
    tipo = re.search(r"type\s+(\S+);", corpo).group(1)
    eq = re.search(r'reaction\s+"([^"]+)"', corpo).group(1)
    if "TroeFallOff" in tipo:
        k0 = re.search(r"k0\s*\{[^}]*A\s+([^;]+);[^}]*beta\s+([^;]+);"
                       r"[^}]*Ta\s+([^;]+);", corpo)
        ki = re.search(r"kInf\s*\{[^}]*A\s+([^;]+);[^}]*beta\s+([^;]+);"
                       r"[^}]*Ta\s+([^;]+);", corpo)
        F = re.search(r"F\s*\{[^}]*alpha\s+([^;]+);[^}]*Tsss\s+([^;]+);"
                      r"[^}]*Ts\s+([^;]+);[^}]*Tss\s+([^;]+);", corpo)
        of_troe[idx] = (eq, k0.groups(), ki.groups(), F.groups())
        of_rx.append((idx, tipo, eq, None, None, None, None, corpo))
    else:
        A = re.search(r"\bA\s+([^;]+);", corpo)
        beta = re.search(r"\bbeta\s+([^;]+);", corpo)
        Ta = re.search(r"\bTa\s+([^;]+);", corpo)
        of_rx.append((idx, tipo, eq, float(A.group(1)), float(beta.group(1)),
                      float(Ta.group(1)), None, corpo))
assert len(of_rx) == 27, len(of_rx)
assert set(of_troe) == {14, 21}, sorted(of_troe)  # posições de H+O2(+M) e H2O2(+M)

# fator de conversão OF (chemkinReader.C: Afactor = 0.001^(sumExp-1),
# sumExp = nº de concentracoes no lado esquerdo; M conta como 1)
div = 0
for k, (idx, tipo, eq_of, A_of, beta_of, Ta_of, _, _c) in enumerate(of_rx):
    eq_pdf, A_pdf, beta_pdf, Ea_pdf = pdf_rx[k]
    if k in of_troe:
        continue                     # verificado à parte abaixo
    lhs = eq_pdf.split("=")[0]
    n_conc = lhs.count("+") + 1             # nº de fatores de concentração
    fator = 1e-3 ** (n_conc - 1)
    ok_eq = (eq_pdf.replace(" ", "").replace("(+M)", "").replace("+M", "")
             == eq_of.replace(" ", "").replace("+ M", ""))
    ok_A = abs(A_of - A_pdf * fator) <= 1e-6 * A_of + 1e-30
    ok_b = abs(beta_of - beta_pdf) < 1e-9
    ok_Ta = abs(Ta_of - Ea_pdf / R_CAL) <= 1e-5 * abs(Ta_of) + 1e-30
    if not (ok_eq and ok_A and ok_b and ok_Ta):
        div += 1
        print(f"  RX {k}: {eq_pdf} | tipo {tipo}")
        if not ok_eq:
            print(f"     eq: PDF={eq_pdf!r} OF={eq_of!r}")
        if not ok_A:
            print(f"     A: PDF={A_pdf}*{fator:g}={A_pdf*fator:g} OF={A_of}")
        if not ok_b:
            print(f"     beta: PDF={beta_pdf} OF={beta_of}")
        if not ok_Ta:
            print(f"     Ta: PDF Ea={Ea_pdf}/1.987={Ea_pdf/R_CAL} OF={Ta_of}")
print(f"reações confrontadas: {len(pdf_rx)}, divergências: {div}")

# ---------- eficiências de terceiro corpo (6 reações: 4 com M explícito + 2 Troe) ----------
# PDF: linhas de continuação "   SP/ef/ SP2/ef2/" após cada reação com M
tb_pdf = {}          # índice na ordem das reações -> {specie: ef}
k3 = None
for ln in sec_nc.splitlines():
    s = ln.strip()
    m = re.match(r'^(.+?)\s+[\d.]+[Ee][+-]\d+\s+[+-]?[\d.]+\s+[+-]?[\d.]+[Ee]?[+-]?\d*\s*$',
                 s)
    if m and "=" in s:
        cand = [k for k, r in enumerate(pdf_rx)
                if r[0].replace(" ", "") == m.group(1).replace(" ", "")]
        k3 = cand[0] if cand else None
    elif k3 is not None and re.match(r"^([A-Z0-9]{1,4}/[\d.]+/\s*)+$", s):
        for par in re.findall(r"([A-Z0-9]{1,4})/([\d.]+)/", s):
            tb_pdf.setdefault(k3, {})[par[0]] = float(par[1])
of_tb = {}
for k, (idx, tipo, eq_of, A_of, beta_of, Ta_of, _, corpo) in enumerate(of_rx):
    mm = re.search(r"coeffs\s*13\s*\((.*?)\)\s*;", corpo, re.S)
    if mm:
        pares = re.findall(r"\((\S+) ([\d.]+)\)", mm.group(1))
        of_tb[k] = {s: float(e) for s, e in pares}
assert len(of_tb) == 6, sorted(of_tb)  # 4 terceiro-corpo + 2 Troe
div = 0
for k, tb in sorted(tb_pdf.items()):
    for sp, ef in tb.items():
        if abs(of_tb[k].get(sp, 1.0) - ef) > 1e-9:
            print(f"  TB RX {k} ({pdf_rx[k][0]}): {sp} PDF={ef} OF={of_tb[k].get(sp)}")
            div += 1
# eficiências não listadas no PDF devem ser 1.0 no OF
for k, tb in sorted(of_tb.items()):
    for sp, ef in tb.items():
        if sp not in tb_pdf.get(k, {}) and abs(ef - 1.0) > 1e-9:
            print(f"  TB RX {k}: {sp} não listada no PDF, OF={ef}")
            div += 1
print(f"eficiências 3-corpo: {len(tb_pdf)} reações x 13 espécies, "
      f"divergências: {div}")

# ---------- massas molares ----------
mw_ref = {"H": 1.00797, "H2": 2.01594, "O": 15.9994, "OH": 17.00737,
          "H2O": 18.01534, "O2": 31.9988, "HO2": 33.00677, "H2O2": 34.01474,
          "N2": 28.0134, "AR": 39.948, "HE": 4.0026, "CO": 28.01055,
          "CO2": 44.00995}
st_mw = {m[0]: float(m[1]) for m in re.findall(
    r"^(\S+)\n\{\n\s*specie\s*\{\s*molWeight\s+([\d.]+);", st, re.M | re.S)}
assert len(st_mw) == 13, st_mw
div = sum(abs(st_mw[s] - mw_ref[s]) > 0.001 for s in mw_ref)
print(f"massas molares: {len(st_mw)}, divergências: {div}")
for s in mw_ref:
    if abs(st_mw[s] - mw_ref[s]) > 0.001:
        print(f"  MW {s}: ref={mw_ref[s]} OF={st_mw[s]}")

# ---------- k0/kInf/TROE das reações de falloff (blocos 14 e 21) ----------
pdf_low = [m.groups() for m in re.finditer(
    r"LOW/([\d.]+[Ee][+-]\d+)\s+([+-]?[\d.]+)\s+([\d.]+[Ee][+-]\d+)/", sec_nc)]
pdf_troe = [m.groups() for m in re.finditer(
    r"TROE/([\d.]+)\s+([\d.Ee+-]+)\s+([\d.Ee+-]+)/", sec_nc)]
assert len(pdf_low) == 2 and len(pdf_troe) == 2, (pdf_low, pdf_troe)
for (idx, (eq, k0, ki, F)), low, troe in zip(sorted(of_troe.items()), pdf_low,
                                             pdf_troe):
    # nº de reagentes sem M: H+O2=HO2 -> 2 ; H2O2=OH+OH -> 1.
    # Afactor = 0.001^(n-1); o k0 entra com M a mais (o lexer acrescenta
    # M ao lado esquerdo do LOW — chemkinReader.C)
    n_l = len(eq.split("=")[0].replace(" ", "").split("+"))
    f0 = 1e-3 ** n_l
    fI = 1e-3 ** (n_l - 1)
    ok0 = abs(float(k0[0]) - float(low[0]) * f0) <= 1e-5 * float(k0[0])
    okE0 = abs(float(k0[2]) - float(low[2]) / R_CAL) <= 1e-5 * abs(float(k0[2]))
    # kInf contra a linha principal do PDF (pdf_rx[idx])
    _, A_pdf, beta_pdf, Ea_pdf = pdf_rx[idx]
    okI = (abs(float(ki[0]) - A_pdf * fI) <= 1e-5 * float(ki[0])
           and abs(float(ki[1]) - beta_pdf) < 1e-9
           and abs(float(ki[2]) - Ea_pdf / R_CAL) <= 1e-5 * abs(float(ki[2])))
    okT = (abs(float(F[0]) - float(troe[0])) < 1e-9
           and abs(float(F[1]) - float(troe[1])) < 1e-9
           and abs(float(F[2]) - float(troe[2])) < 1e-9
           and float(F[3]) > 1e14)   # 4º parâmetro ausente -> sentinela 2^52
    print(f"  {eq}: k0 A={float(k0[0]):.4g} {'OK' if ok0 and okE0 else 'DIVERGE'} | "
          f"kInf A={float(ki[0]):.4g} beta={ki[1]} Ta={float(ki[2]):.6g} | "
          f"TROE {troe} {'OK' if okT else 'DIVERGE'}")