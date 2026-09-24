# Mecanismo Burke et al. 2012 (H₂/ar) — OpenFOAM 13

Mecanismo cinético H₂/O₂ de [Burke, Chaos, Ju, Dryer & Klippenstein,
*Comprehensive H₂/O₂ Kinetic Model for High-Pressure Oxidation*,
Int. J. Chem. Kinet. **44** (2012) 444–474], convertido para os dicionários
do OpenFOAM 13 e **verificado mecanicamente** contra a fonte. Usado no
degrau **R2** do roadmap reativo (mistura homogênea H₂/ar em volume fixo,
ignição espontânea pela cinética — sem fonte de calor, sem faísca).

> **Escopo**: este mecanismo é para VERIFICAÇÃO (portões R2: atraso de
> ignição 0-D vs shock tube, fechamento de energia, estabilidade do passo
> químico). Não é validação contra dados de motor.

## Arquivos

| arquivo | papel |
|---|---|
| `chem.inp` | entrada CHEMKIN verbatim (ELEMENTS/SPECIES/REACTIONS, bath gas N₂ ativo) — proveniência; **não é lido pelo OpenFOAM** |
| `therm.dat` | entrada CHEMKIN thermo verbatim (colunas normalizadas) — proveniência |
| `transportProperties` | viscosidade Sutherland por espécie (trecho para colar no `constant/transportProperties` do caso) |
| `reactions` | saída do `chemkinToFoam` — incluir de `constant/chemistryProperties` (`#include "reactions"`) |
| `speciesThermo` | saída do `chemkinToFoam` — incluir de `constant/physicalProperties` (`#include "speciesThermo"`) |
| `pipeline/` | scripts de reconstrução + verificação e a extração bruta do PDF |

## Proveniência

- **Fonte verbatim**: suplemento do paper (PDF do site
  `burke.me.columbia.edu`), arquivo CHEMKIN versão 6-10-2011, páginas
  105–108. Extração de texto com pypdf (modo *layout*), páginas salvas em
  `pipeline/extracao_suplemento.txt`. **Nenhuma constante foi redigitada**:
  as linhas são copiadas mecanicamente pelos scripts em `pipeline/`.
- **Bath gas**: o arquivo original tem um bloco por gás de banho; o bloco
  N₂ (principal) já está ativo no original. Os blocos AR/HE estão
  comentados no original e permanecem comentados.
- **Verificação mecânica** (`pipeline/verificar_conversao.py` — 0
  divergências):
  - thermo: 13 espécies × 14 coeficientes NASA-7 idênticos ao PDF;
  - 27 reações: A (com fator de conversão de unidades — abaixo), β e Ta
    idênticos ao PDF;
  - eficiências de terceiro corpo (6 reações × 13 espécies) idênticas;
  - parâmetros TROE, k₀/kInf das reações de falloff idênticos;
  - 13 massas molares idênticas.

## Notas de conversão (chemkinToFoam, OF13)

- **Comentários ASCII**: o lexer do OF13 rejeita bytes não-ASCII; o
  travessão do comentário "Hong et al. ... 5718–5727" foi transliterado
  para hífen simples (único conteúdo alterado, em comentário).
- **therm.dat reformatado por colunas**: a extração do PDF perde espaços à
  esquerda (ex.: `0300.00` → ` 300.000`; data da H₂O ` 20387` com 5
  dígitos). A linha 1 é reconstruída por fatias de coluna fixas (data cols
  19–24, elementos cols 25–44 verbatim, G na col 45).
- **Coluna Tint descartada**: o 5º campo opcional da linha 4 (extensão
  CHEMKIN, não usado pelo GRI nem pelo formato NASA-7 do OF) é descartado;
  os polinômios são definidos por Tlow/Tcommon/Thigh.
- **Unidades de A**: o conversor aplica `Afactor = 0.001^(n_conc−1)`
  (`chemkinReader.C`), onde `n_conc` é o nº de fatores de concentração do
  reagente, **M inclusive**: reações bimoleculares ×1e-3; terceiro corpo
  (`k[A][M]`) ×1e-3; k₀ de falloff (com M extra) ×1e-6 para H+O₂(+M)
  (bimolecular) e ×1e-3 para H₂O₂(+M) (unimolecular); kInf de H₂O₂(+M)
  é s⁻¹ (×1). Verificado contra o fonte e confrontado com o PDF.
- **Constante R**: o lexer do OF13 divide Ea por `RRcal = 1.987316
  cal/(mol·K)` (`chemkinLexer.L`) — não pelo valor mais preciso 1.98720;
  os Ta do `reactions` refletem essa constante do próprio OF13.
- **TROE com 3 parâmetros**: ausência do 4º parâmetro vira o sentinela
  `Tss ≈ 2^52` no dicionário OF (contribuição `exp(−Tss/T) = 0`, correto).

## Transporte (viscosidade)

O suplemento do paper não traz transporte. Os coeficientes de Sutherland
(`transportProperties`) foram **ajustados** (não copiados) à viscosidade
Chapman-Enskog da base Lennard-Jones do GRI-Mech 3.0 (via
`pipeline/Burke2012.yaml`, SDToolbox/Caltech), correlação de Neufeld et
al. (1972), malha 300–3500 K (80 pontos, espaço log), erro máximo do
ajuste **5,9%** (`pipeline/ajustar_transporte.py`,
`pipeline/sutherland_fit.json`).

Discrepância documentada: os valores ajustados de N₂ (1.776e-6/187.4) e
O₂ (2.057e-6/193.3) diferem dos publicados nos tutoriais do OF13
(1.401e-6/107 e 1.753e-6/139) porque as bases LJ publicadas são distintas
(GRI-3.0 vs CHEMKIN TRANSPORT clássico). Ambas são fontes publicadas;
optamos pela base GRI por ser a mesma família de dados do mecanismo.

## Regeneração e verificação

```bash
cd pipeline
python montar_mecanismo.py     # extrai verbatim → chem.inp + therm.dat bruto
python formatar_thermo.py      # normaliza colunas do therm.dat
python ajustar_transporte.py   # ajuste Sutherland → sutherland_fit.json
python verificar_conversao.py  # confronta ../reactions e ../speciesThermo com o PDF
```

`verificar_conversao.py` exige que `reactions` e `speciesThermo` tenham
sido regerados com `chemkinToFoam` (OF13):

```bash
chemkinToFoam chem.inp therm.dat transportProperties reactions speciesThermo
```

## Fontes

1. Burke, M. P.; Chaos, M.; Ju, Y.; Dryer, F. L.; Klippenstein, S. J.
   *Int. J. Chem. Kinet.* 2012, 44, 444–474 + suplemento (CHEMKIN
   v6-10-2011, site burke.me.columbia.edu; acessado 2026-09-23).
2. Dados LJ de transporte: `SDToolbox` (Kéromnès et al. 2013),
   `data/Burke2012.yaml`, shepherd.caltech.edu (transporte = GRI-Mech 3.0,
   Kee et al.), salvo em `pipeline/Burke2012.yaml`.
3. Neufeld, P. D.; Janzen, A. R.; Aziz, R. A. *J. Chem. Phys.* 57 (1972)
   1100 — correlação Ω^(1,1).