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

## 3c. Investigação dirigida (plano de 8 passos, 2026-09-23)

Revisão do usuário identificou que a tabela da seção 3a mistura
diferenças de TERMODINÂMICA com diferenças de TRANSFERÊNCIA DE
CALOR. Cada hipótese foi confirmada nos arquivos/resultados antes de
qualquer alteração:

**1. Procedência dos parâmetros Wiebe — CONFIRMADO que a fonte dos
casos 001–004 NÃO é a calibração documentada.** Reprodução da cadeia
documentada (`--input-type pressure --pressure-unit bar --optimize`,
modo pressão, PSO+RK4 sobre 459 pontos do ensaio):

| Parâmetros | θ0 | Δθ | m | Rc | RMSE (ensaio) |
|---|---|---|---|---|---|
| model_cfd.json (usado nos casos 001–004) | −10,0° | 45,0° | 2,0 | 17 (motor) | **221,4 kPa** |
| ajuste reproduzido, Rc livre | +2,79° | 38,7° | 0,459 | 15,89 (ajustado) | 62,0 kPa |
| ajuste reproduzido, Rc fixado 17 | +5,31° | 58,1° | 0,075 | 17 (motor) | 116,3 kPa |

Os números redondos do `model_cfd.json` indicam parametrização
manual; avaliado diretamente na curva do ensaio, rende RMSE 3,5×
pior que o modelo realmente calibrado. **Adoção**: os casos
controlados 005+ usam `examples/model_cfd_calibrated.json` (Rc
fixado em 17 — consistente com a geometria da malha; proveniência
dentro do arquivo; artefatos em `results/calib_wiebe_provenance`).
O modelo manual é mantido apenas para reproduzir os casos originais
002–004. A calibração é 0-D (simulado vs ensaio com κ=1,37 +
Hohenberg) — a comparação CFD–ensaio permanece diagnóstico.

**2. Duração física da janela — bug confirmado e corrigido.**
`interval_duration_s` nos metadados usava
`(Δθ_rad)·(RPM/60)/(2π)` = 37,74 s; o correto é
`Δθ_rad/(2π·RPM/60)` = 0,011776 s (240° = 2/3 de volta a
3396,2 rpm). O tempo do solver NUNCA dependeu deste campo (endTime
em graus, case_builder) — era metadado errado, não erro físico.
Teste novo: mesma janela em deg e rad dá o mesmo valor em segundos,
coerente com `dtheta_dt` da fonte.

**3. Grade da tabela/verificação convergida.** Com o modelo calibrado
(m=0,075), a grade fixa de 0,1° subintegra a derivada Wiebe em
0,29 % (~0,8 % da energia está na 1ª célula de queima). O builder
agora refina a grade até o fechamento ∫Q̇dt = m_f·PCI·Δx_b passar
(0,02° dá 1,0e-4) e grava `table_step_CA_deg`. Original: os casos
001–004 (m=2) fechavam em 0,0 % e não são alterados.

**4. Perda às paredes por ângulo e acumulada ATÉ O PICO (case_004).**

| Banda de CA | CFD case_004 | 0-D Hohenberg |
|---|---|---|
| −120°…−40° | 0,45 J | ≈0 (resfriamento) |
| −40°…−20° | 2,13 J | 2,20 J |
| −20°…0° | 8,90 J | 7,77 J |
| 0°…10° | 7,94 J | 7,83 J |
| 10°…20° | 9,85 J | 10,75 J |
| 20°…40° | 10,27 J | 14,47 J |
| 40°…120° | 5,09 J | 11,62 J |
| **acumulada até o pico** | **18,90 J** | **17,17 J** |
| total | 44,11 J | 53,67 J |

**Conclusão que corrige a interpretação anterior**: ATÉ O PICO de
pressão (10,1° vs 10,34°) as perdas CFD e Hohenberg quase coincidem
(18,9 vs 17,2 J — CFD até perde um pouco MAIS antes de 0°). Os ~10 J
que faltavam no total estão quase todos DEPOIS do pico (20°…120°),
onde não afetam p_max. Portanto o gap de p_max (+9,2 %) NÃO se
explica por déficit de perda acumulada — aponta para as propriedades
termodinâmicas (γ_CFD=1,400 vs κ_0-D=1,37) e para a fonte manual
(RMSE 221 kPa por si). O teste controlado de equivalência
(case_006, Cp=1063 → γ=1,37) separa os efeitos.

O relatório imprime a origem do arquivo, as unidades declaradas, o
offset, e — se o arquivo experimental não existir — uma linha
explícita de erro (nenhuma substituição silenciosa).

**5. Resultado da escada de equivalência (casos 005–009, 2026-09-23).**

| Caso | Fonte | γ | Paredes | p_max (erro vs ensaio) | RMSE (kPa) | viés (kPa) |
|---|---|---|---|---|---|---|
| 004 (original) | manual | 1,400 | 440 K | +9,2 % | 313,8 | — |
| 005 | calibrada (Rc 17) | 1,400 | 440 K | +4,7 % | 198,5 | +101,0 |
| 006 | calibrada (Rc 17) | 1,37 | 440 K | **−2,0 %** | **91,5** | +19,6 |
| 009 | calibrada (Rc 17) | 1,37 | adiabático | +0,7 % | 115,0 | +61,7 |

O degrau γ=1,37 (case_006, `config_cfd_equivalencia.yaml`, Cp=1063 →
γ = 1063/(1063−287,07) = 1,370) é um **teste controlado de
equivalência** com o 0-D — não ajuste arbitrário: o 0-D sempre usou
κ=1,37 e o CFD estava em 1,400 (hConst Cp=1005/M=28,96). Curvas
p×θ e p×V do case_006: `results/cfd/case_006/curvas_p_theta_pv.png`.
O degrau adiabático (case_009) isola a transferência de calor: sem
perdas o p_max vai a +0,7 %, mas o RMSE piora (91,5 → 115,0) e o viés
sobe (+19,6 → +61,7) — paredes a 440 K aproximam mais o ensaio do
que paredes adiabáticas. Curvas p×θ e p×V do case_012 (diagnóstico):
`results/cfd/case_012/curvas_p_theta_pv.png`.

Degraus motorados (completados após a correção max_Co 0,25 — §5b):

| Caso | Configuração | p_max (fase) | RMSE vs 0-D motorado | Perda às paredes |
|---|---|---|---|---|
| 007 | motorado adiabático | 4712,7 kPa @ 0,00° | 55,9 kPa (viés +29,8) | 0 J |
| 008 | motorado, paredes 440 K | 4593,8 kPa @ −0,35° | **8,2 kPa** (viés +4,7) | 13,60 J (Hohenberg 0-D: 15,95 J) |

Referência 0-D motrada (estágio inerte + Hohenberg): p_max 4580,8 kPa
@ −0,40°, perda 15,95 J. O case_008 reproduz a compressão pura com
desvio ~0,2 % do p_max — o CFD resolve corretamente a física
termofluidodinâmica sem queima; a diferença 007 vs 008 (4712,7 →
4593,8 kPa, −2,5 %) é o efeito isolado da perda às paredes.

**6. Análise por faixa angular do resíduo do case_006 — o erro do CFD
é o erro do 0-D.**

| Faixa [°] | RMSE CFD | viés CFD | RMSE 0-D | viés 0-D |
|---|---|---|---|---|
| −120…−60 | 2,8 | −2,7 | 2,4 | −2,2 |
| −60…−30 | 34,6 | +24,7 | 35,4 | +26,1 |
| −30…−10 | 216,2 | +203,9 | 215,0 | +202,8 |
| −10…0 | 276,9 | +272,5 | 274,2 | +269,7 |
| 0…5 | 88,3 | +48,1 | 85,8 | +42,3 |
| 5…10 | 90,8 | −69,8 | 116,5 | −103,1 |
| 10…15 | 96,4 | −86,5 | 124,1 | −116,3 |
| 15…25 | 28,4 | −9,5 | 45,7 | −37,3 |
| 25…40 | 52,5 | −52,2 | 75,9 | −75,7 |
| 40…70 | 28,6 | −27,2 | 47,0 | −45,6 |
| 70…120 | 12,8 | −12,7 | 23,9 | −23,8 |
| **total** | **91,5** | +19,6 | **95,0** | — |

CFD e 0-D coincidem faixa a faixa (diferença ≤ 5 kPa): o resíduo
remanescente NÃO é deficiência do CFD. ~90 % do erro quadrático está
na compressão (−60…0°), onde nenhuma queima age — nenhum re-ajuste
de Wiebe pode corrigi-lo (queima só soma pressão onde o modelo já
está alto).

A verificação **case_012** (diagnóstico) confirma a hipótese: com Rc
efetivo 15,635 + fonte 2 estágios + γ = 1,37 + paredes 440 K
(`config_cfd_rc_efetivo.yaml`), o CFD entrega **RMSE 43,6 kPa**
(R² 0,99923), p_max 5547,7 kPa @ 11,46° (−1,0% vs ensaio), viés −23,4
kPa — vs RMSE 91,5 do case_006. Por faixa: −120…−60° RMSE 4,1
(viés −4,0); −60…−30° 8,9 (+3,0); −30…−10° 35,7 (+32,8); −10…0° 104,0
(−95,5); 0…5° 84,4 (−76,3). O resíduo de compressão desaparece
(confirmando o Rc efetivo), e o erro remanescente concentra-se na
janela de queima com sinal INVERTIDO (CFD agora abaixo do ensaio
entre −10° e 70°) — coerente com a fonte 2 estágios calibrada a P1
ancorado no primeiro ponto medido (verificação 0-D independente:
RMSE 57,9 kPa na janela −120…120° com P1=127,6 @ −120°). As curvas
p×θ e p×V estão em `results/cfd/case_012/curvas_p_theta_pv.png`.
**Interpretação**: o caso é diagnóstico — demonstra QUE o resíduo
vinha do Rc, não calibra a geometria; Rc 15,635 contradiz o valor
documentado (17) e não deve ser adotado como projeto.

**7. Diagnóstico de fase e expoente politrópico efetivo.** Ajuste de
`ln p = c − n·ln V(θ−δ)` na compressão pura do ensaio (−80…−5°): o
melhor deslocamento é δ = +0,25° com ganho marginal (rms(log)
0,00637 → 0,00609) — **não há desalinhamento de PMS relevante**. O
n_eff do ENSAIO é não-monotônico (1,324 em −80…−40°; **1,284** em
−40…−20°; 1,366 em −20…−5°) — incompatível com zona única de γ
constante e perda monotônica; modelos 0-D e CFD dão 1,370/1,371,
1,358/1,361 e 1,333/1,332 nas mesmas faixas (CFD e 0-D idênticos). A
combinação "n_eff 1,284 no meio da compressão + p igual ao ensaio em
−120° e −80°" só é reproduzível com **Rc efetivo menor que o
nominal** (crevices/blow-by/medição de Vc): a calibração com Rc LIVRE
produz RMSE 62,0 kPa com UM estágio (Rc 15,89) — vs 116,3 kPa com Rc
fixado em 17.

**8. Estágios Wiebe 1/2/3 — hipótese testada objetivamente.**
`--compare-stages 1 2 3` (PSO+RK4, seed 42, 2 runs, 459 pontos):

| Estágios | Rc fixado 17: RMSE / ΔBIC | Rc livre: RMSE / R² / CV |
|---|---|---|
| 1 | 116,3 / 0 | 62,0 / 0,9984 / 79,5 |
| 2 | 115,1 / +15,0 | **44,6 / 0,9992 / 50,8** |
| 3 | 115,1 / +39,3 (pior AIC) | 42,8 / 0,9993 / 55,6 (avisos estruturais) |

Com Rc nominal 17, estágios extras NÃO melhoram (saturam em ~115 kPa
— o erro vive na compressão). Com Rc efetivo livre, o multi-estágio
entrega de verdade (62,0 → 44,6 kPa); N=2 é o ponto de equilíbrio
(N=3: θ0_2 ≈ θ0_3, CV pior). **case_012** (`config_cfd_rc_efetivo.yaml`,
fonte `model_cfd_duo_rc15635.json`): CFD com Rc 15,635 + fonte 2
estágios calibrada em par com este Rc + γ=1,37 — TESTE DIAGNÓSTICO da
hipótese de Rc efetivo. Rc 15,635 **contradiz a geometria documentada
(Rc 17)** e não deve ser adotado como geometria de projeto; a
comparação resultante é diagnostica, nunca validação. Resultado (item
6 acima): RMSE 43,6 kPa, R² 0,99923, p_max −1,0% — hipótese do Rc
efetivo CONFIRMADA como causa dominante do resíduo de compressão.

**10. Conservação de massa (todos os casos com pistão móvel).** Massa
inicial = final em TODOS os casos (leitura `mass_kg` do primeiro e do
último instante gravado; variação relativa 0,00e+00): 005/006/007/008/
009/011 = 0,509452 g; 012 = 0,512867 g (Rc menor → V mínimo maior →
mais massa a p₀/T₀ idênticos). Conservação de energia: a fonte é
verificada na preparação (∫Q̇dt = m_f·PCI·Δx_b ≤ 0,1 %, grade refinada
até fechar — §4 e caso_builder), o mecanismo q'''·V₀ = Q̇ é testado
ponto a ponto na suíte, e o fechamento ΔU + W + perda com campos
exatos foi verificado no case_001 (+0,72 %, seção 2); os casos
seguintes reutilizam o mesmo mecanismo de fonte.

**11. Sensibilidade de malha (case_010, 36×54 vs 006, 24×36).**
case_010 (2,25× células, mesmas física/fonte do 006, max_Co 0,25 —
a 0,5 abortou, §5b): p_max 5494,0 kPa @ 12,05° (006: 5489,6 @ 12,02°),
RMSE vs ensaio 91,1 (006: 91,5), viés +21,7, perda às paredes 37,25 J
(006: 36,99 J), massa conservada (0,509654 g, variação 0,00e+00). A
diferença entre as duas MALHAS é rms 4,4 kPa e máx 11,2 kPa (0,08 % do
p_max) — a solução é independente de malha nesta faixa; junto do
case_011 (passo temporal, 3,6 kPa rms), a independência numérica está
fechada e o resíduo de ~91 kPa do case_006 é físico (Rc efetivo —
item 6), não numérico.

**9. Sensibilidade ao passo temporal / Courant (case_011 vs 006).**
case_011 repete o case_006 com `max_Co 0,25` (em vez de 0,5):
p_max 5487,6 @ 12,08° (006: 5489,6 @ 12,02°), RMSE vs ensaio 92,5
(006: 91,5). A diferença entre as duas soluções CFD é rms 3,6 kPa e
máx 10,0 kPa (0,065 % do p_max) — o resultado é insensível ao passo
temporal nesta faixa, e a queda de max_Co de 0,5 para 0,25 não altera
as conclusões. (Os casos 001–006 rodaram a 0,5; 007/008/011/012 a 0,25;
o padrão do construtor passou a ser 0,25.)

## 5b. Impedimentos registrados (nenhum resultado estimado como simulado)

* **RESOLVIDO — Casos motorados 007/008 e caso 012: foamRun aborta
  (rc=134) com `FOAM FATAL ERROR: Negative initial temperature T0`
  (−42 K em 007 @ +12,3°; −921 K em 008; −2534 K em 012 @ −23,55°)**
  em `fluid::thermophysicalPredictor()`. Histórico do log: Co_max sobe
  suavemente até ~0,5 e explode em 3 passos (0,5 → 1,2 → 3,5 → 140 no
  008; 0,5 → 1,6 → 1633 no 012) com deltaT colapsando
  (1,4e-5 → 2,8e-9 s) — pico de velocidade local (Co médio ~0,006),
  seguido de divergência do campo h. Ocorre identicamente com paredes
  adiabáticas (007), a 440 K (008) e com queima (012); a ausência de
  `constant/fvModels` não é causa. **Causa raiz: max_Co 0,5 é
  marginal** para a malha/rotação deste caso. **Correção:
  `max_Co 0,25`** nos `system/controlDict` (logs de crash preservados
  como `logs/foamRun.crash_maxCo05.log`) e novo padrão do construtor
  (`CfdConfig.max_Co = 0.25`, com comentário no código citando esta
  seção). **Verificação pós-correção**: 007, 008, 011 e 012 completaram
  (rc=0; 133–160 s cada) com resultados consistentes — 008 (motorado,
  paredes 440 K) p_max 4593,8 kPa @ −0,35° vs 0-D motorado com
  Hohenberg 4580,8 @ −0,40° (RMSE 8,2 kPa, viés +4,7; perda às paredes
  CFD 13,60 J vs Hohenberg 15,95 J); 007 (motorado adiabático) p_max
  4712,7 @ 0,00° (RMSE 55,9 vs 0-D motorado; +2,9 % = efeito isolado
  da perda às paredes); 011 e 012 conforme §3c itens 6 e 9. Os degraus
  motorados da escada ficaram temporariamente sem resultado CFD entre
  as execuções abortadas e a correção; nenhum resultado foi estimado
  ou interpolado nesse período.

* **Segunda ocorrência em 0,5 — caso 010 (malha fina 36×54)**: mesma
  assinatura (Co_max 2,9e5, deltaT 6,4e-12 s, `T0: −106,8 K`) em
  −14,45° CA, durante a queima; log preservado como
  `case_010/logs/foamRun.crash_maxCo05.log`. Reexecução com max_Co
  0,25: **completou** (614,6 s) — resultado na seção 3c item 11.
  Reforça que 0,5 é marginal neste motor em qualquer malha, não apenas
  nos casos motorados.

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

- Suíte CFD: `pytest tests/test_cfd.py` → **52 passed**
  (config/estados, fonte Wiebe N=1..5 em deg/rad, identidade
  q'''·V₀ = Q̇ ponto a ponto, tabelas Function1, geometria/cinemática,
  combustíveis com fontes citadas + registro permanente em
  data/fuels_custom.yaml com portabilidade CSV, case builder — incl.
  teste que garante que o caso com pistão móvel usa q''' e não Q,
  kOmegaSST (campo omega, BCs, wallDist) e kEpsilon, gás configurável
  (Cp/M/μ/Pr) e paredes adiabáticas,
  comparação experimental: métricas de sobreposição, unidades/offset
  declarados e erro explícito sem arquivo — nenhuma substituição
  silenciosa).
- **Regressão completa com CFD off: `pytest` → 365 passed**
  (nenhuma alteração de comportamento no núcleo; inclui as páginas
  novas da GUI — CFD editável e Combustíveis — via Streamlit AppTest).
- GUI: página CFD renderiza (AppTest, sem exceções) com o caso real
  concluído — estados, ações e métricas corretos; relatório com
  comparação experimental e diagrama P–V (5 figuras).

## 6. Pendências de verificação (a fazer na entrega final)

Nenhuma — suíte completa executada (365 passed, 2026-09-23); escada
completa com casos reais 001–012 (fonte calibrada, escada de perdas,
motorados, passo temporal, malha fina, Rc efetivo) e independência
numérica fechada (malha + Δt). O balanço de energia com campos exatos
(functionObject `coded`) foi verificado nos casos de referência
001/004 (§2 e §3b) e o mecanismo de fonte é idêntico nos demais,
onde se verifica a conservação exata de massa e a verificação da
fonte na preparação (§3c item 10).

## 7. Limites da verificação

- Sensibilidade de malha varrida em TRÊS níveis (16×24, 24×36 e
  36×54 — caso 010): 24×36 → 36×54 muda p̄(θ) em 4,4 kPa rms (0,08 %
  do p_max); refinamentos adicionais têm ganho desprezível. O resíduo
  remanescente é físico (Rc efetivo, §3c item 6), não numérico —
  independência de passo temporal confirmada em separado (case_011,
  3,6 kPa rms).
- kOmegaSST executado e documentado (33,7 J — abaixo do kEpsilon
  neste caso); sem varredura exaustiva de constantes dos modelos.
- A comparação experimental é **diagnóstica**: a p̄ volumétrica de um
  cilindro simplificado não é a pressão no sensor, e a fonte prescrita
  já usa estes dados na calibração — não é validação (ver seção 3a e
  architecture.md §9).
- A pressão volumétrica média não identifica os campos 3D.