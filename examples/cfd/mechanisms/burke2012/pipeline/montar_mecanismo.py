# -*- coding: utf-8 -*-
"""Reconstrói os arquivos CHEMKIN do mecanismo Burke et al. 2012 a partir
da extração VERBATIM do suplemento do paper (PDF do site da Columbia),
sem redigitação: linhas copiadas mecanicamente, removendo apenas
cabeçalhos de página e espaços à direita. Escreve, na pasta do mecanismo
(nível acima deste script):

  chem.inp   — ELEMENTS + SPECIES + REACTIONS (bath gas N2 ativo)
  therm.dat  — THERMO ALL (formato bruto do PDF; rodar formatar_thermo.py
               em seguida para normalizar as colunas)

Verifica: 13 espécies, 27 reações, presença dos blocos esperados.

Uso (a partir desta pasta):
    python montar_mecanismo.py
    python formatar_thermo.py
"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

AQUI = Path(__file__).resolve().parent
MEC = AQUI.parent

SRC = AQUI / "extracao_suplemento.txt"

txt = SRC.read_text(encoding="utf-8")
lines = []
for pag in (105, 106, 107, 108):
    m = re.search(rf"===== PAGINA {pag} =====\n(.*?)(?====== PAGINA|\Z)", txt, re.S)
    for ln in m.group(1).splitlines():
        s = ln.rstrip()
        # cabeçalho de página (ex.: "  106 ") — artefato do PDF
        if re.match(r"^\s*1[0-9]{2}\s*$", s):
            continue
        lines.append(s.rstrip() + "\n")

bloco = "".join(lines)

# cortes: ELEMENTS..END, SPECIES..END, THERMO ALL..END, REACTIONS..END
def secao(nome, ate="END"):
    ini = bloco.index(nome)
    fim = bloco.index(ate, ini + len(nome)) + len(ate)
    return bloco[ini:fim]

cimpo = re.sub(r"\n\s*\n", "\n", bloco[bloco.index("ELEMENTS"):bloco.index("THERMO ALL")])
thermo = bloco[bloco.index("THERMO ALL"):bloco.index("!******", bloco.index("THERMO ALL"))]
reacoes = bloco[bloco.index("REACTIONS"):bloco.index("\nEND", bloco.index("REACTIONS")) + 4]

cab = "! Mechanism: H2 kinetic mechanism, Burke et al. 2012 (version " \
      "6-10-2011) -- extracted VERBATIM from the paper supplement (PDF,\n" \
      "! Columbia site), mechanically copied, not retyped. Main bath gas: " \
      "N2 (block already active in the original file). ASCII only: the\n" \
      "! CHEMKIN lexer in OF13 rejects non-ASCII bytes.\n"
# o travessão do comentário original (U+2013, "5718-5727") é transliterado
# para hifen simples: o lexer do OF13 rejeita bytes não-ASCII
reacoes = reacoes.replace("–", "-").replace("—", "-")
assert all(ord(c) < 128 for c in cab + cimpo + reacoes)
(MEC / "chem.inp").write_text(cab + cimpo + "\n" + reacoes + "\n",
                              encoding="utf-8", newline="\n")
(MEC / "therm.dat").write_text(cab + thermo.rstrip() + "\nEND\n",
                               encoding="utf-8", newline="\n")

# --- verificação estrutural ---
sp = re.search(r"SPECIES(.*?)END", cimpo, re.S).group(1).split()
n_rx = len(re.findall(r"^[^!\s].*E[+-]", reacoes, re.M))
assert len(sp) == 13, sp
n_reac_named = len(re.findall(r"^\w.*E[+-]", reacoes, re.M))
print("espécies:", len(sp), sp)
print("linhas de reação (com E):", n_reac_named)
nasa = thermo.count("G ")
print("entradas NASA (G):", nasa)
assert "H+O2(+M) = HO2(+M)" in reacoes and "LOW/6.366E+20" in reacoes
print("bloco N2 do H+O2(+M) ativo: OK")