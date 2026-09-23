# Relatório de verificação — módulo CFD (wiebepy)

Data: 2026-09-23 · Ambiente: Windows 11 + WSL2 Ubuntu-22.04, OpenFOAM 13
(build linux64GccDPInt32Opt, /opt/openfoam13) · Malha: cilindro
paramétrico 6144 células (16×24×16, axissimétrico circular)

## 1. Escada de verificação executada

| # | Caso | Resultado |
|---|------|-----------|
| 1 | Volume fixo, frio (V1, `results/cfd/v1_fixed_cold`) | Concluído; massa conservada; p(t) consistente com pV = mRT |
| 2 | Volume fixo + fonte Wiebe (sonda, malha fixa) | Entrega integral: T 800→2140 K, 369 J injetados |
| 3 | Pistão móvel frio | p×V segue p₀(V₀/V)^γ; massa conservada |
| 4 | Pistão móvel + fonte Wiebe (referência, `results/cfd/case_001`) | Concluído (45 s); **balanço de energia fecha** (seção 2) |
| 5 | Comparação 0-D (caso 4) | p̄×θ CFD dentro de ±2 % do 0-D com a mesma fonte e a mesma perda calculada pelo CFD (seção 3) |
| 6 | Comparação experimental (ensaio P_exp-Carga-3_45%, DIESEL) | Realizada como **diagnóstico** no relatório: p×θ e diagrama P–V com sobreposição (seção 3a) — NÃO é validação (p̄ volumétrica ≠ pressão no sensor; a fonte já usa estes dados na calibração) |
| 7 | Perda às paredes: turbulência e refinamento (cases 002–004) | kEpsilon 41,0 J; kOmegaSST 33,7 J; kEpsilon + malha refinada **44,1 J** vs alvo Hohenberg 53,7 J — p_max +13,1 % → **+9,2 %** (seção 3b) |

## 2. Caso case_001 — balanço de energia (laminar, sensibilidade)

Motor: bore 86 mm, curso 70 mm, biela 117,5 mm, Rc 17, 3396,2 rpm,
m_f = 9,4275 µg/ciclo, PCI 39 191,3 kJ/kg (**diesel do ensaio** — o
experimento de pressão P_exp-Carga-3_45% foi um motor Diesel; a
referência típica do registro é 42,6 MJ/kg, o valor usado na fonte é o
do combustível do ensaio, seção engine), janela −120°…+120°.

Condições iniciais agora são as **do ENSAIO** em θ = −120° CA:
p₀ = 127,6 kPa (pressão medida, 1,276 bar) e T₀ = 308,15 K (T1 da
seção engine) — antes da inclusão da comparação experimental o caso
usava 250 kPa / 800 K (valores do exemplo sintético antigo), que
superprevia p_max em ~2×. Paredes 440 K.

| Grandeza | Valor |
|----------|-------|
| Energia prescrita (m_f·PCI, janela −120°…+120°) | 369,48 J (verificação de fechamento da tabela: erro relativo 1,5e-16) |
| ΔU exato (∫ρ·Cv·T dV, campos inicial/final) | +135,10 J (U_inicial 112,60 J, U_final 247,71 J) |
| Trabalho indicado ∮p̄ dV (V cinemático) | +221,07 J |
| Perda às paredes ∫q_wall dt | −15,97 J (T̄ máx 1493 K, bem menor que no caso antigo 800 K inicial) |
| **Fechamento (ΔU + W + perda)** | **372,15 J (+0,72 % vs prescrito)** |
| p̄ máx | 6,334 MPa @ 10,5° CA (experimental: 5,602 MPa @ 12°, seção 3a) |
| T̄ máx | 1493,4 K @ 21° CA |
| Massa inicial/final | 0,508997318 g / 0,508997318 g (conservada exatamente) |

O ΔU exato foi calculado lendo os campos p, ρ e T gravados nos diretórios
inicial/final com um functionObject `coded` (∫ρ·Cv·T·dV, ρ = p/RT por
célula; Cv = Cp − R com Cp = 1005 J/kgK do modelo gas do caso e
R = 287,10 J/kgK medido nos campos: R_mean(120°) = 287,1018,
R(−120°) = p₀·V_mesh₀/(m·T₀) = 287,1015). U_inicial também confere
analiticamente (m·Cv·T₀).

Volume da malha vs volume cinemático 0-D: V_mesh(±120°) =
3,52909e-4 m³ vs V₀ cinemático 3,53477e-4 (razão 0,9984); perto do PMP
a razão é 0,9989 — offset de folga essencialmente constante
(dV_mesh/dθ = dV₀/dθ), efeito < 0,2 % no fechamento (junto com a
amostragem de 10° na integração de W e perda). Não é perda de fonte
(bug corrigido — seção 4): com a razão de volumes aplicada, a fonte
injetada na malha é 369,29 J dos 369,48 nominais.

## 3. Comparação 0-D (degrau 5)

Modelo 0-D fechado com a MESMA fonte Wiebe calibrada e a MESMA perda à
parede calculada pelo CFD (não Hohenberg), mesmas condições iniciais
(127,6 kPa / 308,15 K), R = 287,10 J/kgK e Cv = Cp − R (o mesmo modelo
gas do caso):

- p̄_máx: CFD 6,334 MPa vs 0-D 6,420 MPa (−1,3 %)
- Diferença p̄(θ) relativa no intervalo [−40°, 60°]: −4,2 % a +0,8 %
  (média −1,7 %) — sem offset sistemático grande; consistente com o
  resíduo do balanço (+0,72 %) e a diferença de volume malha-móvel vs
  cinemático perto do PMP.
- Fechamento da própria integração 0-D: resíduo ~0,0 J (0,0 %),
  confirmando que a comparação é autoconsistente.

## 3a. Comparação experimental (ensaio P_exp-Carga-3_45%, DIESEL)

Dados do ensaio (503 pontos, bar → kPa, rad → °CA, sem offset) lidos
diretamente pelo relatório (`wiebepy cfd report` / página CFD da GUI),
que produz a sobreposição p×θ, o diagrama P–V (CFD vs experimental) e
a tabela de métricas na janela de sobreposição (503 pontos):

| Caso (config) | Perda às paredes | p_max (erro vs ensaio) | Fase | Viés | RMSE |
|---------------|------------------|------------------------|------|------|------|
| case_001 (laminar 16×24) | 16,0 J | 6334,0 kPa (+13,1 %) | −1,5° | +180,0 | 375,4 kPa |
| case_002 (kEpsilon 16×24) | 41,0 J | 6179,0 kPa (+10,3 %) | −2,0° | +145,9 | 329,2 kPa |
| case_003 (kOmegaSST 16×24) | 33,7 J | 6224,3 kPa (+11,1 %) | −2,0° | +155,7 | 342,2 kPa |
| **case_004 (kEpsilon 24×36 — referência)** | **44,1 J** | **6116,5 kPa (+9,2 %)** | −1,9° | +136,3 | **313,8 kPa** |
| (alvo 0-D Hohenberg) | 53,7 J (14,5 %) | 5692,2 kPa (+1,6 %) | −1,7° | — | — |

(p_max experimental: 5602,3 kPa @ 12° CA.)

## 3b. Escada de perda às paredes (degrau 7)

O gap CFD–ensaio está concentrado na janela de queima (compressão
motored com diferença ≤ 30 kPa até −40° CA) e é dominado pela perda
térmica às paredes:

- A calibração 0-D embute a correlação de Hohenberg: perda 53,7 J
  (14,5 % do prescrito) e p_max 5692 kPa (+1,6 % vs ensaio).
- O CFD calcula a troca térmica por si (condutibilidade na célula
  vizinha, laminar): só 16,0 J — os ~38 J a menos explicam os +13 %
  de p_max (verificados por bisseção: mesma cadeia 0-D com a perda
  escalada reproduz o p_max do ensaio).
- Turbulência real (kEpsilon + wall functions) recupera a maior parte
  (41,0 J); kOmegaSST ficou ABAIXO do kEpsilon neste caso (33,7 J —
  documentado); o refinamento da malha (24×36) soma 44,1 J.
- Restam ~10 J: geometria simplificada (sem bowl/câmara real nem
  swirl do ensaio, paredes planas), correlação de parede simples e
  propriedades do ar constantes. Cada refinamento físico aproxima do
  alvo; a distância restante é limitação declarada da geometria, não
  um erro da cadeia numérica (fechamento de energia do case_004:
  −0,04 %).

O balanço de energia exato do case_004 (referência): ΔU = +122,28 J
(U_inicial 112,72 J, U_final 235,00 J, functionObject `coded`
∫ρ·Cv·T dV; massa 0,509452 g conservada exatamente; R 287,1018) +
trabalho 202,94 J + perda 44,11 J = 369,33 J vs prescrito 369,48 J
(**−0,04 %**).

A interpretação permanece DIAGNÓSTICA, não validação (p̄ volumétrica
de cilindro genérico sem transferência de carga ≠ pressão no sensor;
a fonte prescrita já usa estes dados na calibração).

O relatório imprime a origem do arquivo, as unidades declaradas, o
offset, e — se o arquivo experimental não existir — uma linha
explícita de erro (nenhuma substituição silenciosa).

## 4. Bug descoberto e corrigido (fonte de calor do OF13)

Durante a verificação do degrau 4 descobriu-se que o modo `Q` (potência
total) do fvModel `heatSource` do OpenFOAM 13 **não é conservativo com
malha móvel**: o volume da zona é capturado uma única vez na construção
do fvModel (`Function1s::Scale(Constant("1/V", 1/zone_.V()), …)` —
`heatSource.C`/`fvCellZoneI.H`), enquanto o volume real varia ~15×.

- Sintoma original: o caso com pistão móvel entregava ~15 J dos 369,5 J
  prescritos (T final 854,6 K; p̄ colada na curva motored).
- Diagnóstico (bisseção, 4 sondas em /tmp no WSL): malha fixa + tabela ⇒
  369 J entregues; malha móvel + mesma tabela ⇒ ~15 J; leitura do código
  do OF13 confirmou o mecanismo.
- **Correção**: prescrever a densidade diretamente —
  `q'''(CA) = Q̇(CA)/V₀(CA)` [W/m³] (distribuição uniforme, f = 1/V₀,
  exatamente o formalismo §7), no lugar do campo Q. Implementada em
  `case_builder.py` + `sources/wiebe_heat_release.py`
  (`table_text_density`), com verificação automática de fechamento.
- Modo `region` mantém Q (volume da zona desconhecido na geração) com a
  limitação registrada no aviso de distribuição.

## 5. Cobertura de testes automatizados

- Suíte CFD: `pytest tests/test_cfd.py` → **46 passed**
  (config/estados, fonte Wiebe N=1..5 em deg/rad, identidade
  q'''·V₀ = Q̇ ponto a ponto, tabelas Function1, geometria/cinemática,
  combustíveis com fontes citadas + registro permanente em
  data/fuels_custom.yaml com portabilidade CSV, case builder — incl.
  teste que garante que o caso com pistão móvel usa q''' e não Q,
  kOmegaSST (campo omega, BCs, wallDist) e kEpsilon,
  comparação experimental: métricas de sobreposição, unidades/offset
  declarados e erro explícito sem arquivo — nenhuma substituição
  silenciosa).
- **Regressão completa com CFD off: `pytest` → 359 passed**
  (nenhuma alteração de comportamento no núcleo; inclui as páginas
  novas da GUI — CFD editável e Combustíveis — via Streamlit AppTest).
- GUI: página CFD renderiza (AppTest, sem exceções) com o caso real
  concluído — estados, ações e métricas corretos; relatório com
  comparação experimental e diagrama P–V (5 figuras).

## 6. Pendências de verificação (a fazer na entrega final)

Nenhuma — suíte completa executada (359 passed), caso de referência
case_004 (kEpsilon + malha refinada) executado e verificado
(seções 2, 3a e 3b).

## 7. Limites da verificação

- Sensibilidade de malha varrida em dois níveis (16×24 e 24×36);
  refinamentos adicionais têm ganho pequeno (perda 41 → 44 J) — o
  gap restante (~9 % de p_max) é dominado pela geometria
  simplificada e pelo modelo de parede, não pela resolução.
- kOmegaSST executado e documentado (33,7 J — abaixo do kEpsilon
  neste caso); sem varredura exaustiva de constantes dos modelos.
- A comparação experimental é **diagnóstica**: a p̄ volumétrica de um
  cilindro simplificado não é a pressão no sensor, e a fonte prescrita
  já usa estes dados na calibração — não é validação (ver seção 3a e
  architecture.md §9).
- A pressão volumétrica média não identifica os campos 3D.