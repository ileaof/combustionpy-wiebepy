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
| 8 | R1 — gás inerte multicomponente NASA (`case_014`) | Massa conservada (drift 0); fechamento motorado equivalente ao simple (residuo +1,1 J); custo +33 % (seção 3f) |
| 9 | R2 — H₂ autoignição, câmara fechada adiabática (`r2_verificacao`) | 4 portões confrontados: 0-D vs dados publicados (razões 0,38–5,98, assinatura documentada no próprio artigo); τ_CFD/τ_0D = 0,991; fechamento Q̇/(−ΔH_quím) = 1,0017; p̄ sem oscilação (1,0e-5 da variação) (seção 3g) |

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

**11b. Confirmação de malha no par (case_017_malha_fina, 36×54 vs 012,
24×36).** Fecha a limitação registrada em §3d/§7: o case_012 (par
calibrado, Rc 15,635 + fonte duo) foi reexecutado na malha 36×54
(69.984 células, 2,25× do 24×36, mesma config `examples/
config_cfd_rc_efetivo_malha_fina.yaml`, serial, 493 s). A diferença
entre as duas malhas no par é rms 4,25 kPa e a estrutura por faixa
confirma que ela se concentra onde os gradientes são maiores:
−5…0° rms 7,6 kPa (viés −7,5), 0…5° rms 11,1 kPa (viés −11,0),
5…20° rms 8,1 kPa; fora do entorno do PMS as faixas ficam ≤ 3 kPa
(−120…−80°: 0,18 kPa). Mesma magnitude da confirmação no caso base
(4,4 kPa, item 11) — a independência de malha vale também para o par
calibrado, e a Rc 15,635 configurada permanece **diagnóstica** (§3d:
adotá-la como geometria do projeto é proibido).

**9. Sensibilidade ao passo temporal / Courant (case_011 vs 006).**
case_011 repete o case_006 com `max_Co 0,25` (em vez de 0,5):
p_max 5487,6 @ 12,08° (006: 5489,6 @ 12,02°), RMSE vs ensaio 92,5
(006: 91,5). A diferença entre as duas soluções CFD é rms 3,6 kPa e
máx 10,0 kPa (0,065 % do p_max) — o resultado é insensível ao passo
temporal nesta faixa, e a queda de max_Co de 0,5 para 0,25 não altera
as conclusões. (Os casos 001–006 rodaram a 0,5; 007/008/011/012 a 0,25;
o padrão do construtor passou a ser 0,25.)

**Restauração do case_006 (2026-09-23).** O diretório arquivado
`results/cfd/case_006/` foi acidentalmente regenerado durante um teste
E2E da GUI (clique em Preparar caso com o padrão do formulário). O caso
foi re-executado de ponta a ponta pela receita documentada
(`config_cfd_equivalencia.yaml`), com max_Co 0,25 (o padrão atual do
construtor — ver item 9): p_max 5487,6 kPa @ 12,08°, T̄ máx 1305,2 K,
trabalho indicado 193,6 J, ∫Q prescrito 369,4 J (erro 1,0e-4),
perda às paredes 34,8 J. Os
números coincidem com o case_011 (rms documentado 3,6 kPa entre as
duas soluções; 0,04 % no p_max vs o 006 original a 0,5). O report.html
foi regenerado. As MÉTRICAS citadas nos itens anteriores permanecem as
da corrida original; a corrida restaurada confirma-as dentro da banda
de insensibilidade numérica documentada.

## 3d. Rastreabilidade do case_012 (caso diagnóstico)

**O que mudou do case_006 para o case_012** (única origem:
`config_cfd_rc_efetivo.yaml`):

| Item | case_006 (base) | case_012 (diagnóstico) | Origem |
|---|---|---|---|
| `engine.Rc` | 17,0 | **15,63540583** | CALIBRADO (ajuste PSO+RK4 com Rc livre, 2 estágios) |
| `wiebe.model` | model_cfd_calibrated.json (1 estágio) | **model_cfd_duo_rc15635.json** (2 estágios) | CALIBRADO |
| `numerics.max_Co` | 0,5 | 0,25 | numérico (crash §5b; sem efeito medido: item 9) |
| diretorio | results/cfd/case_006 | results/cfd/case_012 | – |
| Todos os demais | idênticos | idênticos | – |

**Intactos entre os dois casos**: bore 86 mm, curso 70 mm, biela
117,5 mm, rpm 3396,20, m_f 9,42754647351e-6 kg/ciclo, PCI
39 191,3 kJ/kg (diesel do ensaio), T1 308,15 K, Tw 440 K
(fixed_temperature), kEpsilon + wall functions, janela −120°…+120°,
inicial 127,6 kPa / 308,15 K, malha 24×36, Δt 1e-6 s, `distribution:
uniform`, fuel diesel (premixed_gas), comparação ensaio (rad/bar,
offset 0).

**Propriedades termodinâmicas (declaradas, não ajustadas)**:
Cp = 1063 J/kgK, M = 28,96 kg/kmol → R = 287,07 J/kgK,
γ = Cp/(Cp−R) = **1,370** — teste de equivalência com o κ = 1,37 do
0-D (mesmo valor dos casos 005/006/009/010/011); μ = 5,5e-5 Pa·s,
Pr = 0,7. Cv = Cp − R = 775,93 J/kgK.

**Origem da fonte Wiebe (CALIBRADA no ensaio, não prevista)**:
`--compare-stages` PSO+RK4, seed 42, 2 runs, 459 pontos do ensaio,
janela ±2 rad, com Rc livre e N = 2 (artefatos em
`results/calib_wiebe_stages123_freerc/`):

| Estágio | β_j | θ0_j | Δθ_j | m_j | a_j |
|---|---|---|---|---|---|
| 1 | 0,65653322 | −14,4527° | 49,4203° | 2,87177 | 6,9078 |
| 2 | 0,34346678 | +5,5369° | 12,1768° | 0,56855 | 6,9078 |

Métricas do ajuste: RMSE 44,60 kPa, R² 0,99919, CV 50,8; verificação
0-D independente (P1 = 127,6 kPa @ −120°): RMSE 57,9 kPa. O Rc
15,63540583 é o MESMO parâmetro calibrado em par com estes estágios.
A tabela da fonte é verificada na preparação:
∫Q̇dt = 369,40 J vs m_f·PCI = 369,48 J (erro −0,02 %).

**Balanço de energia do case_012** (janela −120°…+120°; ΔU na forma
exata U = (cv/R)·p̄·V — p uniforme no campo, hConst/perfectGas;
U inicial confere com m·cv·T₀ = 122,6 J):

| Grandeza | Valor |
|---|---|
| Energia prescrita (fonte, tabela) | 369,40 J |
| ΔU (U_final 261,24 − U_inicial 122,71) | +138,53 J |
| Trabalho indicado ∮p̄ dV | +195,99 J |
| Perda às paredes ∫q_wall dt | 35,13 J (13,90 J até o pico) |
| **Fechamento (ΔU + W + perda)** | **369,65 J (+0,07 % vs prescrito)** |
| T̄ mássica final (p̄·V/m·R) | 656,5 K |
| Massa | 0,512867 g, variação 0,00e+00 |

(o mesmo fechamento para o case_006 dá 139,89 + 192,53 + 36,99 =
369,41 J vs 366,86 J prescritos na janela — +0,7 %.)

**Janela do RMSE**: sobreposição completa ensaio ∩ CFD = **459 pontos**
do ensaio (−114,5°…+114,5°), p̄ do CFD interpolada nos ângulos do
ensaio; sem offset. As mesmas métricas (RMSE, viés, erro de pico,
R²) são calculadas nesta janela para todos os casos da seção 3a/3c.

**Verificações de malha e passo temporal**: medidas na configuração
BASE (case_006): malha 24×36 → 36×54 (case_010) muda p̄(θ) em 4,4 kPa
rms; max_Co 0,5 → 0,25 (case_011) muda 3,6 kPa rms — ambas
desprezíveis frente aos efeitos investigados. O case_012 herda a
mesma malha/numérica (com Co 0,25). A sensibilidade NÃO foi repetida
na geometria Rc 15,635 (mesmo gerador de malha e mesma equação de
volume; registrada como limitação, não como resultado estimado).

**Calibrado vs previsto — separação explícita**:

| Categoria | Grandezas |
|---|---|
| CALIBRADAS (ajustadas ao ensaio; não são previsões) | θ0_j, Δθ_j, m_j, β_j das 2 estágios; Rc efetivo 15,635 |
| FIXADAS (entrada, do ensaio/documentação) | m_f, PCI, T1, P1 127,6 kPa, rpm, geometria bore/curso/biela, Tw 440 K, γ = 1,37 (equivalência) |
| PREVISTAS pelo CFD (nenhum dado de saída usado no ajuste) | p̄(θ) completa, T̄(θ), campos 3D de U/T/p/k/ε, perda às paredes (35,13 J), trabalho indicado (195,99 J), fase do pico |
| PRESCRIÇÃO (não é previsão de queima) | A FORMA da liberação de calor é a Wiebe calibrada — o CFD transporta a energia prescrita; a sobreposição final de curvas é em parte esperada por construção |

**Leitura correta**: o case_012 mostra (a) que a cadeia numérica CFD é
conservativa e malha/Δt-independente, (b) que o resíduo do case_006
era o Rc efetivo, e (c) que a curva calibrada reproduz o ensaio — NÃO
mostra que o modelo prevê a combustão (fonte prescrita; Rc efetivo
contradiz a geometria documentada e não serve de projeto).

## 3e. Conservação da fonte `region` com malha móvel (case_013)

Caso controlado pedido antes de recomendar a distribuição `region`:
**case_013 = case_006 com `heat_source: {distribution: region, region:
zonaInferior}`** (única diferença; config em
`examples/config_cfd_region.yaml`). A zona é uma caixa axial
(boxToCell, seção plena do bore, z ∈ [−10 mm; h₀/2] com h₀ = altura da
câmara em −120° = 60,85 mm → metade axial da câmara), criada UMA vez
por `topoSet` (`cellZoneSet` estático, 10 368 de 20 736 células —
malha 24×24×36). Rodou completo (foamRun rc=0, 140,7 s).

**Resultado — SUBENTREGA forte, como previsto em §4:**

| Grandeza | case_013 (region) | case_006 (uniform) |
|---|---|---|
| Entrega efetiva (ΔU + W + perda, U = (cv/R)·p̄·V) | **39,40 J = 10,7 %** do prescrito (369,4 J) | 369,41 J (+0,7 %) |
| p_max | 4593,8 kPa @ −0,35° (igual ao motorado case_008 no pico) | ~5530 kPa |
| Divergência vs motorado | começa em 5,44° CA (início da queima); máx. +205 kPa @ 18,57° | – |
| Perda às paredes | 15,28 J | 36,99 J |
| Massa | exatamente constante (0,512867 g) | idem |

**Mecanismo confirmado no fonte do OF13** (`/opt/openfoam13/src/`):

- `src/fvModels/general/heatSource/heatSource.C:85-96` — no modo `Q`,
  a densidade é construída como
  `Function1s::Scale(Constant("1/V", 1/zone_.V()), Constant("1", 1), Q(t))`:
  o fator **1/zone_.V() é um `Constant`**, avaliado UMA vez na
  construção do fvModel (t = −120° CAD), nunca atualizado.
- `src/finiteVolume/fvMesh/fvCellZone/fvCellZone.C:38-43` +
  `fvCellZoneI.H:34-37` — `zone_.V()` = Σ `mesh_.V()` das células da
  zona, no instante da construção.
- `heatSource.C:149-153` — a fonte é aplicada como
  `eqnSource[cells[i]] -= mesh().V()[cells[i]]·q`, com os volumes
  CELULARES CORRENTES.

**Consistência quantitativa**: como a cellZone é estática (mesmos
rótulos de células) e a compressão do gás é uniforme, o volume da zona
escala com o volume total — V_zona(θ)/V_zona(−120°) = V(θ)/V(−120°) —
e a entrega prevista com o fator congelado é
∫Q̇(θ)·(V(θ)/V(−120°))·dθ = **38,36 J (10,4 %)**, fechando com os
39,40 J medidos (Δ 2,6 %, interpolacão + perda às paredes). Perto do
PMS o fator V(θ)/V(−120°) chega a 0,072: quase toda a queima é
suprimida. A densidade local efetiva também fica errada
(Q̇/V_zona(−120°) em vez de Q̇/V_zona(θ)) — o erro não é só de total,
é espacial/temporal.

**Veredito**: **NÃO usar `distribution: region` com malha móvel** — a
limitação é do fvModel `heatSource` do OF13 (volume congelado na
construção no modo `Q`), não do builder. A distribuição `uniform`
(q''' = Q̇/V₀(θ), prescrita densidade por densidade) é conservativa com
malha móvel — fechamento +0,7 % (case_006) e +0,07 % (case_012, §3d) —
e permanece a única recomendada. `region` só voltaria a ser candidata
com correção upstream (reavaliar 1/V a cada passo) ou com um fvModel
próprio; o aviso de distribuição no builder já reflete isso.

**Registro adicional**: o modo `region` estava inexecutável até esta
verificação — o `topoSetDict` era gravado em `constant/system/` em vez
de `system/` (bug do builder corrigido; teste de regressão adicionado
à suíte). Sem a correção, o case_013 abortava na validação com
"no such file: constant/system/topoSetDict".

## 3f. R1 — gás inerte multicomponente (case_014)

Primeiro degrau do roadmap reativo (`reactive_roadmap.md` §2, R1):
gás **N2+O2 com polinômios NASA** (janaf) e transporte sutherland, SEM
reação. Config `examples/config_cfd_multicomponent.yaml` = config do
case_008 (motored, paredes 440 K, janela −120..120 CA, malha 24×24×36,
pistão móvel) com `gas.model: multicomponent_inert` e
`case_directory: results/cfd/case_014`.

**Implementação** (suíte: 56 testes CFD, todos passando):

- `cfd/config.py` — novo campo `gas.model` com valores `simple`
  (padrão; comportamento idêntico ao atual) e `multicomponent_inert`;
  validação rejeita valores desconhecidos. Com `multicomponent_inert`,
  `gas.Cp/molWeight/mu/Pr` são **IGNORADOS** (aviso registrado no
  `case_config.yaml` de cada caso gerado).
- `cfd/case_builder.py` — com `multicomponent_inert`:
  `system/controlDict` usa `solver multicomponentFluid;`;
  `constant/physicalProperties` no formato do tutorial OF13
  `multicomponentFluid/counterFlowFlame2D` (`hePsiThermo` +
  `coefficientWilkeMulticomponentMixture` + sutherland + janaf +
  sensibleEnthalpy + perfectGas, `defaultSpecie N2`, lista
  `species ( N2 O2 );`); campos `N2`/`O2` em 0/ (frações mássicas do
  ar seco, razão molar 3,76:1 → Y_N2 = 0,766992, Y_O2 = 0,233008);
  `div(phi,Yi_h)  Gauss limitedLinear 1;` em fvSchemes; entradas
  `"Yi"`/`"YiFinal"` em fvSolution. **NÃO é escrito
  `constant/combustionProperties`** — o `combustionModel::New` do OF13
  cai em `noCombustion` (R = 0, Qdot = 0), confirmado no log:
  *"Combustion model not active: combustionProperties not found" →
  "Selecting combustion model none"*.
- **Proveniência dos coeficientes**: NASA + sutherland de N2 e O2
  copiados mecanicamente de
  `/opt/openfoam13/tutorials/multicomponentFluid/counterFlowFlame2D/constant/thermo.compressibleGas`
  (termoquímica GRI-Mech distribuída com o OF13) — não digitados de
  memória; a origem está citada no comentário do gerador e no
  `case_config.yaml`.
- `cfd/results.py` — novo campo `specie_mass_kg` (massa de cada
  espécie ∫ρ·Yi dV ao longo do ciclo), via functionObjects `multiply`
  (rhoN2 = ρ·N2, rhoO2 = ρ·O2) + `volFieldValue volIntegrate`
  (`specieMass`) no controlDict, no padrão gasAvg/gasIntegral.
- `tests/test_cfd.py` — 4 testes novos: physicalProperties
  multicomponente (janaf/sutherland/defaultSpecie/molWeight/NASA, sem
  combustionProperties, com dynamicMeshDict) + regressão do caso
  simple; solver/campos/functionObjects/case_config; validação de
  `gas.model`.

**Correção durante a implementação** (registrada como os demais):
a 1ª tentativa de execução abortou com *"keyword species is undefined
in dictionary .../physicalProperties"* — o tutorial define a lista de
espécies via `#include "thermo.compressibleGas"` e a lista
`species ( ... );` é OBRIGATÓRIA no nível superior do
physicalProperties. Corrigido no builder (lista explícita
`species ( N2 O2 );`) com asserção no teste. Corrigido também um
early-return no `_write_constant` que pulava
momentumTransport/dynamicMeshDict/fvModels no ramo multicomponente
(o dynamicMeshDict é obrigatório para o pistão móvel).

### Resultados (case_014 vs case_008)

**(a) Sem reação — confirmado.** O caso completa a janela
−120..120 CA (log com `End`; `check_completion` OK). Não há
combustionProperties → modelo `none` → **nenhuma fonte de calor**:
a única física é compressão/expansão + troca térmica com paredes.

**(b) p×θ vs case_008** (grades adaptativas diferentes — 684 vs 708
pontos, porque as propriedades dependem de T — interpoladas em grade
comum de 700 pontos; ambos os casos com max_Co 0,25):

| Grandeza | case_008 (Cp/mu constantes) | case_014 (NASA/sutherland) | Δ |
|---|---|---|---|
| rms(p̄) | – | – | **50,5 kPa** (≈ 1,1 % do pico) |
| máx |Δp̄| | – | – | **+129 kPa @ ≈ PMS** (≈ 2,8 %) |
| p̄_max | 4593,8 kPa @ −0,35° | **4721,3 kPa @ −0,33°** | +2,8 % |
| T̄_max | 798,4 K | 820,4 K | +22,0 K (+2,8 %) |
| perda às paredes | 13,6 J | 13,2 J | ≈ igual |

**Explicação (efeito registrado, não corrigido)**: o caso simple usa
Cp = 1063 J/kgK constante, calibrado para γ = 1,37 (equivalência com o
0-D). Com NASA, o γ real do ar seco varia de ≈ 1,40 (300 K) a ≈ 1,37
(800 K) — acima de 1,37 em quase toda a compressão — o que eleva p̄ e
T̄ no pico (+2,8 %, coerente entre p e T). O transporte sutherland dá
mu ≈ 1,8–4×10⁻⁵ Pa·s (T-dependente) contra 5,5×10⁻⁵ constante —
camada limite mais fina; a perda total às paredes quase não muda
(13,2 vs 13,6 J), mas a distribuição temporal de p muda o suficiente
para o rms de 50,5 kPa. Diferença é efeito físico esperado da
substituição do gás, não erro numérico.

**(c) Conservação de massa — gate cumprido.** Integrando ρ (gasIntegral)
e ρ·Yi (specieMass, nova cadeia multiply → volIntegrate):

| Grandeza | inicial | final | drift relativo |
|---|---|---|---|
| massa total | 5,075287×10⁻⁴ kg | 5,075287×10⁻⁴ kg | **0,0** |
| massa N2 | 3,892704×10⁻⁴ kg | 3,892704×10⁻⁴ kg | **0,0** |
| massa O2 | 1,182582×10⁻⁴ kg | 1,182582×10⁻⁴ kg | **0,0** |

Drift ZERO ao longo de TODO o ciclo (mín = máx = inicial), no limite
da precisão de escrita dos .dat (~10⁻⁷ relativo). Y_N2/Y_O2 médios
coincidem com os teóricos do ar seco (0,766992/0,233008) — composição
permanece uniforme, como esperado sem reação.

**(d) Fechamento de energia motorado** (1ª lei: ΔU + W_by + |Qw| ≈ 0,
W_by = ∫p̄ dV, |Qw| = perda às paredes integrada):

- **Método (diferente do simple — registrado honestamente)**: com gás
  multicomponente, **U = (cv/R)·p̄·V NÃO é mais válido** (pressupunha
  cv e R constantes de uma única constituição). Método usado: com
  composição uniforme (confirmada em (c)), U = m·ū(T̄_m), com ū da
  mistura avaliada pelos MESMOS polinômios NASA
  (u_i = h_i − R_s,i·T) e **T̄_mássica exata do gás ideal**
  T̄_m = p̄·V/(m·R_mix), R_mix = ΣYi·R_s,i = 288,19 J/(kg·K). Erro da
  aproximação u(T̄_m) em vez de ∫ρu(T)dV é de 1ª ordem em Var(T) via
  du/dT = cv(T) (≈ 3×10⁻⁴ J/(kg·K²) na faixa) — ≈ milésimos de J,
  desprezível frente ao residuo.
- **case_014**: ΔU = −4,3 J (T̄_m: 308,4 → 296,6 K), W_by = −7,8 J,
  |Qw| = 13,2 J → **residuo = +1,1 J (8,1 % da maior parcela)**.
- **case_008** (referência, método antigo U = (cv/R)·p̄·V): residuo
  +1,1 J (8,2 % da maior parcela). O fechamento do caso
  multicomponente é equivalente ao do caso simple.

**(e) Custo**: foamRun 183 s de clock (case_014) vs 137 s (case_008) —
**+33 %** (186,9 s no runner). Custo adicional = equações de transporte
das espécies + viscosidade Wilke avaliada por célula a cada passo.
Aceitável para o degrau; mecanismos reativos (R2+) custarão bem mais.

**Veredito**: R1 cumprido — o caminho reativo do OF13
(`multicomponentFluid` + fallback `noCombustion`) está operacional,
com termoquímica real (Cp(T), mu(T), composição) e gates de massa e
energia fechados. Próximo degrau (R2, H₂ autoignição) destravado.

## 3g. R2 — H₂ autoignição em câmara fechada (case `r2_verificacao`)

Segundo degrau do roadmap reativo (`reactive_roadmap.md` §2, R2):
mistura H₂/ar estequiométrica **homogênea**, câmara de volume FIXO
(malha fixa 24×36, 20 736 células), paredes adiabáticas, ignição
espontânea pela cinética — mecanismo **Burke et al. 2012** (13
espécies, 27 reações; conversão `chemkinToFoam` documentada em
`examples/cfd/mechanisms/burke2012/README.md`). Condição inicial
T₀ = 1050 K, p₀ = 202,65 kPa (2 atm), φ = 1 (mistura Slack: X_H2 0,296
/ X_O2 0,148 / X_N2 0,556 = ar estequiométrico, razão N₂/O₂ = 3,757).
Config `examples/config_cfd_r2_verificacao.yaml`; caso
`results/cfd/r2_verificacao` (gitignored; janela 0–3 ms). **Escopo
diagnóstico: verificação do CÓDIGO, nunca validação do mecanismo.**

### Portões confrontados (2026-09-24)

**(a) Atraso de ignição 0-D vs dados publicados.** Reator Cantera 0-D
de volume constante (mesma conversão ck2yaml `Burke2012.yaml` dos
arquivos Chemkin do suplemento; critério dT/dt máx, grade uniforme
1 µs; rtol 1e-10/atol 1e-18) confrontado com **9 pontos digitalizados
da Fig. A-17** do preprint de Burke et al. 2012 (p. 116): Slack,
Combust. Flame 28 (1977) 241 (2 atm) + Bhaskaran/Gupta/Just, Combust.
Flame 21 (1973) 45 (2,5 atm); banho N₂, φ=1 — os blocos de taxa
associados ao banho N₂ do mecanismo são exatamente os ativados
(`pipeline/dados_publicados/slack1977_bhaskaran_figA17.yaml`,
proveniência e incertezas declaradas: ±0,005 em 1000/T ≈ ±15 K;
±0,15–0,2 década em τ; leitura de gráfico, NÃO dado medido por nós).

| T (K) | p (atm) | τ_0D (µs) | τ_medido (µs) | razão |
|---|---|---|---|---|
| 990 | 2,0 | 2537,5 | 424,0 | 5,98 |
| 1037 | 2,0 | 86,5 | 67,0 | 1,29 |
| 1099 | 2,0 | 26,5 | 54,0 | 0,49 |
| 1120 | 2,0 | 21,5 | 44,0 | 0,49 |
| 1164 | 2,0 | 14,5 | 27,0 | 0,54 |
| 1182 | 2,0 | 12,5 | 22,0 | 0,57 |
| 1203 | 2,0 | 11,5 | 17,0 | 0,68 |
| 1244 | 2,0 | 8,5 | 12,2 | 0,70 |
| 1323 | 2,5 | 4,5 | 11,7 | 0,38 |

τ(dT/dt) e τ(d[OH]/dt) concordam dentro de 5% (critério do dado
original: aumento rápido da pressão). Os desvios coincidem com os
**documentados no próprio artigo**: impurezas de hidrocarbonetos ~1
ppb sensíveis no atraso e "at baixas T os atrasos experimentais são
várias vezes MENORES que as predições" (efeitos de facilidade, §8
p. 38 do preprint — o ponto 990 K reproduz exatamente essa assinatura,
5,98×). Tolerância declarada do portão: fator ~2 entre 1037 e 1244 K
(1,29→0,70, monotônica em direção à igualdade — comportamento do
modelo do próprio artigo, não do nosso conversor).

**(b) Atraso de ignição CFD vs 0-D.** Mesmas condições iniciais:
**τ_CFD = 100,6 µs** (dT̄/dt máx = 3,62e8 K/s; pico de ∫Q̇dV em
103,1 µs) vs **τ_0D = 101,5 µs** (dT/dt; 100,5 µs por d[OH]/dt) —
**razão 0,991 (~1 %)**, dentro da tolerância declarada (20 %).

**(c) Fechamento de energia** (volume fixo, adiabático —
`cfd.walls.model=adiabatic` obrigatório no modo reativo): com h do
Cantera INCLUINDO a entalpia de formação,

- ∫∫Q̇ dV dt (série `QdotIntegral`) = **31,141 J**
- −ΔH_química = −Δ(Σᵢ mᵢ·h_i°(298,15)) das MASSAS medidas
  (`specieMass`, 13 espécies) = **31,088 J**
- **Q̇/(−ΔH_quím) = 1,0017 (DENTRO da tolerância ±2 %)** — o Q̇ do
  OF13 é consistente com a variação real de composição;
- diagnóstico adiabático: ΔE_tot = +0,15 J em base |E_tot| = 8,59 J
  (E_tot = Σᵢ mᵢhᵢ(T̄) − p̄V; com volume fixo e paredes adiabáticas
  dE_tot/dt = 0 — T̄ final 2982,7 K é a temperatura adiabática de
  chama a volume constante; Δp̄·V = +7,87 J vai para ΔH_total).

Nota honesta: a energia total do combustível (m_H2 = 3,516e-7 kg ×
LHV ≈ 42 J) NÃO é toda liberada — a composição final em 2983 K fica em
equilíbrio com H₂ residual (4,5e-8 kg), OH (2,8e-7 kg) e O₂ residual;
o −ΔH_quím medido (31,1 J) é a energia realmente convertida, e é com
ela que o fechamento é avaliado.

**(d) Estabilidade do passo químico.** Máximo reverso de p̄(t) fora da
janela de ignição: **3,12 Pa = 1,0e-5 da variação total** (309 kPa) —
sem oscilação não física. Homogeneidade final (uniformidade da câmara,
pré-requisito do fechamento): T ∈ [2969,0; 2982,7] K (dispersão 0,46 %),
p ∈ [510697; 512802] Pa (0,41 %).

### Custo e limitações registradas

- **Colapso do passo pós-ignição**: `adjustTimeStepToChemistry` segue
  as escalas químicas do gás queimado — dt colapsou de ~2 µs (pré-
  ignição) para ~2 ns logo após o pico (t ≈ 102 µs), recuperando
  gradualmente até ~7 µs e completando os 3 ms (t ~ 200 µs → 3 ms em
  ritmo acelerado). Custo total: ~2 h de clock (1 worker). Para janelas
  de motor (graus CA), o pós-queima em T alta dominará o custo —
  reescopo do endTime por caso, nunca endereço automático de 3 ms.
- **Série FO**: 2554 amostras (uma por passo; `volFieldValue` escreve
  a série .dat a cada passo — desejado para resolução de dT̄/dt; os
  CAMPOS só em writeTime, ver seção 5b).
- Sem malha móvel, sem geometria de motor, sem comparação com ensaio
  (DIAGNÓSTICO). O degrau R2 não valida o mecanismo Burke 2012 —
  verifica que o caminho CFD reproduz o mesmo 0-D e fecha energia.

**Veredito**: R2 cumprido — os 4 portões confrontados com números
(a: razões 0,38–5,98 com assinatura documentada no próprio artigo;
b: 100,6 vs 101,5 µs, 1 %; c: 1,0017 vs 1,000 ± 0,02; d: 1,0e-5 de
reversos). Próximo degrau (R3, malha móvel + reação) destravado
**após a verificação de compatibilidade exigida** (§ R3 — não
afirmada: reativo + `dynamicMeshDict` no OF13 é pendência registrada).

## 5b. Impedimentos registrados (nenhum resultado estimado como simulado)

* **PRÉ-EXISTENTE (fora do escopo R1, verificado por stash)** —
  `tests/test_gui.py::test_cfd_muda_numero_de_estagios` falha
  (`TypeError: object of type 'NoneType' has no len()` em
  `session_state["cfd_form"]["wiebe_stages"]`) TAMBÉM sem as mudanças
  R1 (confirmado com `git stash` dos arquivos alterados) — introduzida
  pelo commit 3bc1cfd (GUI CFD, caso padrão case_006). Não é da etapa
  R1; restante da suíte: 368 testes passando (364 existentes + 4 novos
  de R1).
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

* **RESOLVIDO — FO `Qdot` congelava o campo entre writeTimes (R2,
  2026-09-24)**: no OF13 o functionObject do tipo `Qdot` é quem
  RECALCULA o campo `Qdot`; com `executeControl writeTime` no
  controlDict o campo só era atualizado nos writeTimes (1e-4 s, 2e-4 s,
  ...) e o FO `QdotIntegral` integrava valor BIT-A-BIT constante
  (2,65274987e+06 W ao longo de ~2000 passos) — a 1ª execução do caso
  R2 somou 256 J "liberados" com 42 J de combustível disponível.
  Detectado pelo portão R2c (∫∫Q̇dVdt vs −ΔH_química = 1707 — FORA);
  as MASSAS medidas provavam que o combustível real queimado era
  ~3,07e-7 kg (~37 J LHV). Correção no builder:
  `executeControl timeStep;` (campo vivo a cada passo) +
  `writeControl writeTime;` (sem dump do campo a cada passo); caso
  regenerado e reexecutado — fechamento 1,0017 (seção 3g). Registrado
  como impedimento 9 no roadmap reativo. Todos os números do portão
  citados vêm da REEXECUÇÃO; a dinâmica de ignição reproduziu-se
  identicamente entre as duas execuções (τ_CFD 100,6 µs e reversos de
  p̄ 3,12 Pa nos dois casos — mesma malha, mesmas condições, mesmo
  mecanismo).

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
- Modo `region` mantém Q (volume da zona desconhecido na geração); a
  subentrega prevista foi **medida no case_013: 39,40 J entregues dos
  369,4 J prescritos (10,7 %)** — mecanismo confirmado no fonte
  (1/V congelado em `Function1s::Constant`, `heatSource.C:89`) e
  veredito de não recomendação com malha móvel em **§3e**.

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
  3,6 kPa rms). **Confirmação no par calibrado** (case_017_malha_fina,
  36×54 vs case_012 24×36): 4,25 kPa rms, mesma estrutura por faixa —
  item 11b; a limitação "não repetida no par" está fechada.
- kOmegaSST executado e documentado (33,7 J — abaixo do kEpsilon
  neste caso); sem varredura exaustiva de constantes dos modelos.
- A comparação experimental é **diagnóstica**: a p̄ volumétrica de um
  cilindro simplificado não é a pressão no sensor, e a fonte prescrita
  já usa estes dados na calibração — não é validação (ver seção 3a e
  architecture.md §9).
- A pressão volumétrica média não identifica os campos 3D.
## 3h. Módulo opcional crevice_flow (submodelo de fresta, 2026-09-25)

Escopo e arquitetura: `docs/cfd/crevice.md`. Nível submodelo: câmara
prescrita (o escoamento não modifica p(θ)), domínio anelar wedge
(fresta top-land + buffer), fundo fechado — NÃO é blow-by. Modelos
Wiebe 0-D e casos de câmara intocados (teste de identidade +
suíte completa: 400 passed após as mudanças, 2026-09-25).

### Sondas e prova real (OpenFOAM Foundation 13, WSL Ubuntu-22.04)

- `uniformTotalPressure` (p0 Function1 tabela de tempo, ψ/γ), 
  `uniformFixedValue` (estático), `pressureInletOutletVelocity`
  (reversão), `inletOutlet` (T com inversão), patches `wedge`,
  `wallHeatFlux` + `areaIntegrate`/`volIntegrate` com cellZone —
  todos aceitos pelo solver `fluid` em execução real.
- Formatos de postProcessing capturados de caso real (headers acima).
- Mini-caso real (2e-5 s, 108 células, Δt ≤ 1e-7, laminar):
  **balanço de massa 0,019 %** (tol 0,5 %) e **balanço de energia
  0,61 %** (tol 2 %) — U = ∫p dV/(γ−1), h ≈ cp·T declarado.
  ṁ < 0 na subida de pressão (enchendo), física coerente.
- blockMesh/checkMesh limpos (não-ortogonalidade 0; aspecto 5,3).

### Janela completa 360° (2026-09-25, §7b de crevice.md)

Dois casos REAIS completos (0→0,04 s, 360° @ 1500 rpm, serial):
`results/crevice_exemplo` (FOs a 1°: massa **0,88 %** da massa trocada
3,44e-7 kg — FALHA; energia 4,01 % — FALHA) e
`results/crevice_exemplo_fino` (FOs a 20 passos ≈ 2e-6 s: massa
**0,0007 %** — OK, 2,5e-12 kg; energia **2,42 %** — FALHA marginal
pela aproximação declarada h_out = T_camara prescrita). O probe
`results/_crevice_probe_ams` (janela 0,002 s) provou a causa:
resíduo 2,13e-9 kg a 1° vs 1,0e-13 kg a 2e-6 s — aliasing do ringing
acústico na folga (|ṁ| até 2,1e-5 kg/s dentro de um intervalo de 1°).
Escalas dos balanços corrigidas: referência = massa/termos trocados.
Bug corrigido: `check_completion` não via subpastas de restart do
OF13 (glob `*.dat` → `*/*.dat`, com teste de regressão). Suíte:
401 passed (15 de crevice_flow) após as mudanças.

### Escada de verificação (N1–N9)

N1/N1b automatizados (`tests/test_crevice_flow.py`: conversões
dθ/dt = 6·rpm, convenção de vértices do blockMesh — bug "inside-out"
fixado —, regras de geometria, erro duro de blowby/extrapolação/
proveniência). N2/N5/N6 sintéticos automatizados + caso real acima (janela completa
na seção anterior). N7 (sensibilidade): amostragem do fluxo MEDIDA
(1° vs 2e-6 s: 0,88 % → 0,0007 % do fluxo trocado); malha/Δt com
procedimento documentado, não reivindicado — uma execução nunca
estabelece independência.
N8 (serial vs MPI): `--workers N` disponível (decomposePar + mpirun +
reconstructPar no adapter reutilizado). N9: 400 testes do wiebepy
passam com o módulo presente; CLI/GUI degradam graciosamente sem ele.

### Custo medido

Δt limitado pelo CFL acústico na folga (a·Δt/Δr ≈ 1 → Δt ~1e-7 s);
janela de 360° a 1500 rpm ≈ 4e5 passos; /mnt/c (WSL) faz wall-clock
~5–7× o CPU — considerar filesystem nativo do WSL para casos de
fresta. GPU: interface preparada (workers do SOLVER separados dos
backends do wiebepy), sem conversão OpenFOAM→CUDA e sem promessa de
aceleração.
