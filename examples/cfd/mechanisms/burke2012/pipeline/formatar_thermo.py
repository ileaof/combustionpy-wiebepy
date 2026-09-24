# -*- coding: utf-8 -*-
r"""Reformata o bloco THERMO do therm.dat (extraído verbatim do PDF do
paper Burke 2012) para o formato CHEMKIN clássico de colunas fixas — o
mesmo aceito pelo thermo30.dat do OF13. Números copiados MECANICAMENTE;
só as colunas são normalizadas (a extração do PDF perdeu espaços à
esquerda, ex.: "0300.00" em vez de " 300.000").

Detalhes:
  - Linha 1 extraída por COLUNAS: data (cols 19-24) e elementos (cols
    25-44) copiados verbatim. Um regex "\s+" entre nome e data engoliria
    o espaço à esquerda de campos de data com 5 dígitos (ex.: H2O,
    data " 20387") e deslocaria o bloco de elementos uma coluna — erro
    que fez o chemkinToFoam morrer com SIGFPE.
  - A coluna Tint (5º campo opcional da linha 4 — extensão CHEMKIN; o
    GRI thermo30.dat não a usa) é descartada: os polinômios NASA-7 são
    definidos por Tlow/Tcommon/Thigh.
  - A linha de temperaturas (formato clássico 3F10.0) é recolocada após
    "THERMO ALL" — exigida pelo lexer do OF13.

Rodar logo após montar_mecanismo.py (este script sobrescreve therm.dat).
"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

AQUI = Path(__file__).resolve().parent
MEC = AQUI.parent

src = (MEC / "therm.dat").read_text(encoding="utf-8")
linhas = src.splitlines()

# localiza o início das entradas (após a linha de temperaturas)
i0 = next(i for i, ln in enumerate(linhas) if ln.startswith("0300"))
# recoloca a linha de temperaturas (formato clássico 3F10.0) após
# "THERMO ALL" — exigida pelo lexer do OF13
cab = "\n".join(linhas[:i0]) + "\n   300.000  1000.000  5000.000\n"

# junta entradas: grupos de 4 linhas iniciando com nome + "G"
entradas, i = [], i0 + 1
while i < len(linhas):
    ln = linhas[i]
    if not ln.strip() or ln.startswith("!"):
        i += 1
        continue
    if ln.strip() == "END":
        break
    # extração por COLUNAS (ver docstring)
    assert len(ln) >= 45 and ln[44] == "G", f"linha 1 fora de colunas: {ln!r}"
    nome = ln[:18].strip()
    meio = ln[18:44]                      # data (6) + elementos (20), verbatim
    tl, th, tc = [float(x) for x in ln[45:75].split()]
    cont = ln.rstrip()[-1]
    l2 = linhas[i + 1]
    l3 = linhas[i + 2]
    l4 = linhas[i + 3]
    pat = re.compile(r"[+-]?\d*\.\d+E[+-]\d+")
    coefs = ([float(x) for x in pat.findall(l2)]         # 5 high
             + [float(x) for x in pat.findall(l3)]       # 2 high + 3 low
             + [float(x) for x in pat.findall(l4)])      # 4 low (+Tint?)
    assert len(coefs) in (14, 15), (nome, coefs)
    if len(coefs) == 15:
        coefs = coefs[:14]        # Tint descartado (documentado)
    hi, lo = coefs[:7], coefs[7:]

    def f(x):                     # campo de coeficiente: 15 colunas, 8 dec.
        return f"{x:15.8E}"

    linha1 = f"{nome:<18}{meio}G{tl:10.3f}{th:10.3f}{tc:10.3f}    {cont}"
    l2n = "".join(f"{x:15.8E}" for x in hi[:5]) + "    2"
    l3n = "".join(f"{x:15.8E}" for x in hi[5:]) + "".join(
        f"{x:15.8E}" for x in lo[:3]) + "    3"
    l4n = "".join(f"{x:15.8E}" for x in lo[3:7]) + " " * 19 + "4"
    entradas.append("\n".join([linha1, l2n, l3n, l4n]))
    i += 4

out = cab + "\n".join(entradas) + "\nEND\n"
(MEC / "therm.dat").write_text(out, encoding="utf-8", newline="\n")
print("entradas:", len(entradas))
print(out[:400])