# Roadmap do modo reativo (modo 4.2) — proposta incremental

Status: **proposta (não implementada)** · Modo 4.2 reativo: **adiado para
etapa posterior (não proibido permanentemente)** · Última revisão:
2026-09-23 · Complementa `docs/cfd/architecture.md` (seção 9) e
`docs/cfd/verification.md`.

Este documento é uma **proposta**. Nada aqui foi executado; cada etapa
tem critérios de verificação que devem ser cumpridos ANTES de subir o
degrau seguinte. Onde há afirmação não confirmada, ela é marcada como
**VERIFICAÇÃO PENDENTE**. Onde há custo computacional esperado, ele é
marcado como **a medir** — nenhum número de custo é prometido sem
medição (protocolo na seção 6).

## 1. Objetivo e princípios

O modo reativo permite estudar a liberação de calor **calculada pela
cinética química** (mecanismos publicados) em vez de prescrita pela
Wiebe, mantendo tudo o que existe hoje intacto.

Princípios invioláveis (herdados da arquitetura, seção 9):

- **Uma única fonte de calor por caso.** No modo prescrito
  (`prescribed_wiebe`) a Wiebe fornece o calor. No modo reativo a
  **química fornece o calor** e a Wiebe serve APENAS para comparação e
  ajuste posterior (pós-processo, seção 7). As duas fontes **nunca
  coexistem** no mesmo caso — nunca duplicar a fonte energética. A
  troca de modo é explícita na configuração; nunca substituir
  silenciosamente uma fonte pela outra.
- **Opcional e independente.** O modo reativo não pode quebrar o
  `prescribed_wiebe`: CFD permanece desabilitado por padrão
  (`cfd.enabled: false`), o núcleo 0-D não importa nada de CFD, e a
  suíte de testes do wiebepy (365 testes) continua passando sem o
  módulo CFD.
- **Preservar os modelos atuais de 1 a 5 estágios.** As Wiebes 1–5
  estágios do núcleo não são modificadas; no modo reativo elas existem
  apenas como referência comparativa.
- **Comparação com ensaio é DIAGNÓSTICO, nunca validação** (mesma
  convenção do modo prescrito). O modo reativo nascente seria
  **verificado** contra resultados 0-D e contra dados publicados de
  autoignição, e **diagnosticado** contra o ensaio (seção 5).
- **Nada é apresentado como funcional antes de existir.** Enquanto o
  modo 4.2 não estiver implementado e verificado, ele não aparece como
  opção executável na GUI/CLI — apenas esta proposta.

## 2. Arquitetura incremental (degraus R1..R7)

Cada degrau adiciona UMA capacidade nova. Subir um degrau exige cumprir
os critérios de gate do degrau anterior. Cada degrau declara
explicitamente o que fica FORA de escopo — o que não está listado como
entrega não é prometido.

### R1 — Gás inerte multicomponente (sem reação) — **IMPLEMENTADO E VERIFICADO** (ref. §3f do verification.md)

- **O que adiciona**: substituir o gás simplificado (perfectGas, Cp/mu
  constantes) por termoquímica multicomponente — polinômios NASA
  (janaf) com transporte sutherland e mistura
  `coefficientWilkeMulticomponentMixture` — sem nenhuma reação. O caso
  é inerte: a composição não muda, só as propriedades passam a
  depender de T e da composição. Config `gas.model:
  multicomponent_inert`; sem `constant/combustionProperties` (o OF13
  cai em `noCombustion`, R = 0).
- **Gate antes de subir para R2** (cumprido — números em §3f):
  - p×V motored com Cp constante reproduz o caso atual (regressão;
    suíte de testes, caso simple intacto);
  - p×V motored com NASA converge e a diferença vs Cp constante é
    quantificada e explicada (rms 50,5 kPa, máx +129 kPa no pico,
    +2,8 % — Cp/γ deixam de ser constantes — efeito registrado, não
    corrigido);
  - massa de cada espécie conservada ao longo do ciclo (drift 0 no
    limite da precisão de escrita, total e N2/O2);
  - fechamento de energia no padrão do `verification.md` (residuo
    +1,1 J = 8,1 % da maior parcela; U via NASA — método registrado).
- **Fora de escopo**: qualquer espécie combustível, reação, ignição.

### R2 — H₂ autoignição, câmara fechada homogênea — **IMPLEMENTADO, portões CONFRONTADOS (2026-09-24)**

- **O que adiciona**: primeira reação — mistura H₂/ar definida
  homogênea, câmara de volume FIXO (malha fixa), ignição espontânea
  pela cinética (sem fonte, sem faísca, sem malha adaptativa).
  Mecanismo: **Burke et al. 2012** (núcleo ~19 reações derivado de Li
  et al. 2004; arquivo CHEMKIN com 13 espécies, incluindo gases de
  banho N₂/Ar/He/CO/CO₂; blocos de taxa específicos por gás de banho —
  N₂ vs Ar/He; validado para chamas diluídas de alta pressão).
  Candidato alternativo: Ó Conaire et al. 2004 (Combustion and Flame),
  mecanismo H₂/O₂ amplamente usado em motores — citado como candidato,
  sem números não confirmados.
- **Estado (2026-09-24)**: modo `reactive` implementado no case_builder/
  config (câmara fixa em Vc, sem fvModels, sem dynamicMeshDict,
  `reactions`/`speciesThermo` copiados byte a byte do mecanismo
  convertido — ver `examples/cfd/mechanisms/burke2012/README.md`).
  Caso gerado e executado no OF13/WSL2 (`foamRun -solver
  multicomponentFluid`, "End" limpo, `adjustTimeStepToChemistry`
  ativo). **Portões R2a/R2b/R2c/R2d CONFRONTADOS (2026-09-24, ver
  lista abaixo e `docs/cfd/verification.md` §3g).** Dois bugs de
  infraestrutura de FO corrigidos durante a verificação (impedimentos
  8 e 9 — gravação do campo a cada passo; campo Qdot congelado).
  - **R2a (0-D vs dados publicados)**: reator Cantera 0-D (volume
    constante, critério dT/dt máx) contra 9 pontos digitalizados da
    Fig. A-17 do preprint de Burke et al. 2012 (Slack 1977, 2 atm +
    Bhaskaran 1973, 2,5 atm; banho N₂, φ=1 — razões τ_0D/τ_medido:
    5,98 @990 K, 1,29 @1037 K, 0,49–0,70 @1099–1244 K, 0,38 @1323 K).
    Os desvios coincidem com os DOCUMENTADOS no próprio artigo
    (impurezas ~1 ppb / efeitos de facilidade em baixa T: "experimental
    ignition delay times are several times smaller than predictions" —
    §8 p. 38). Proveniência em
    `pipeline/dados_publicados/slack1977_bhaskaran_figA17.yaml`;
    comparação é verificação do CÓDIGO (tolerância fator ~2), nunca
    validação do mecanismo.
  - **R2b (0-D vs CFD, 1ª execução)**: τ_CFD = 100,6 µs (dT̄/dt máx) e
    100,0 µs (pico de ∫Q̇dV) vs τ_0D = 101,5 µs (dT/dt máx; 101,0 µs
    por d[OH]/dt) em T₀=1050 K, p₀=202,65 kPa, φ=1 — coerência de ~1 %.
    Confirmado na reexecução com o FO Qdot corrigido (impedimento 9).
  Reforços da fase de verificação (mesma data):
  - paredes **adiabáticas obrigatórias** no modo reativo
    (`cfd.walls.model=adiabatic` bloqueante em config.validate) — o
    portão R2c só fecha sem troca de calor com as paredes;
  - `specieMass` agora rastreia **todas as espécies do mecanismo** (o
    ΔU precisa da composição completa; intermediários têm massa no pico
    de ignição);
  - scripts de verificação em
    `examples/cfd/mechanisms/burke2012/pipeline/`:
    `verificar_0d_ignicao.py` (portão R2a — reator 0-D Cantera, volume
    constante, lê a conversão ck2yaml `Burke2012.yaml` dos MESMOS arquivos
    Chemkin do suplemento; os pontos experimentais entram SOMENTE de
    `dados_publicados/*.yaml` citados — nenhum dado é inventado) e
    `verificar_cfd_r2.py` (portões R2b/R2c/R2d — lê as séries de
    postProcessing do caso, ΔU via entalpias Cantera e massa medida
    `gasIntegral`, `U = Σᵢ mᵢhᵢ(T̄) − p̄V`).
- **Gate antes de subir para R3** (CONFRONTADOS 2026-09-24 —
  `docs/cfd/verification.md` §3g):
  - ~~atraso de ignição (0-D, integrador homogêneo) reproduz dados~~
    **CUMPRIDO**: 9 pontos da Fig. A-17 (Slack 1977 2 atm +
    Bhaskaran 1973 2,5 atm, banho N₂, φ=1) digitalizados com
    incertezas declaradas; razões τ_0D/τ_medido 0,38–5,98, com os
    desvios coincidindo com os documentados no próprio artigo Burke
    (impurezas ~1 ppb; baixa T: dados de facilidade MENORES que a
    predição — 5,98× @990 K). Verificação do CÓDIGO (fator ~2), não
    validação do mecanismo;
  - ~~o mesmo atraso no CFD (malha fixa, homogênea) é consistente com o
    0-D~~ **CUMPRIDO**: τ_CFD = 100,6 µs (dT̄/dt máx) / 103,1 µs (pico
    ∫Q̇dV) vs τ_0D = 101,5 µs — razão 0,991 (tolerância declarada 20 %);
  - ~~fechamento de energia: energia liberada pela química = ΔU~~
    **CUMPRIDO (reformulado honestamente)**: com câmara adiabática
    fechada e rígida, ΔE_tot = 0 por construção física — o confronto
    correto é ∫∫Q̇dVdt vs −ΔH_química (entalpia de formação consumida,
    das massas medidas de TODAS as 13 espécies): **1,0017 vs 1,000
    (tolerância ±2 %)**; ΔE_tot = +0,15 J em base 8,59 J (diagnóstico
    adiabático);
  - ~~passo de integração química estabilizado (sem oscilação não
    física em p̄(t))~~ **CUMPRIDO**: reversos máximos de p̄ = 3,12 Pa =
    1,0e-5 da variação total; homogeneidade final T 0,46 % / p 0,41 %.
- **Fora de escopo**: malha móvel, geometria de motor, CH₄/etanol/
  diesel, emissões.

### R3 — Geometria de motor (malha móvel + reação)

- **O que adiciona**: juntar o pistão móvel (já verificado no modo
  prescrito) com a reação do R2 — o primeiro caso reativo no motor
  (ainda H₂, premistura homogênea).
- **VERIFICAÇÃO PENDENTE — não afirmar compatibilidade**: é preciso
  confirmar ANTES de começar R3 que o caminho reativo do OF13 aceita
  malha móvel (fvModels + movers `multiValveEngine`/
  `crankConnectingRodMotion` combinados com química), e como o solver
  reativo candidato se comporta com remeshing. A compatibilidade
  reactingFoam + malha móvel no OF13 NÃO está afirmada neste documento
  — é uma pendência registrada (seção 8) e critério de gate.
- **Gate antes de subir para R4**:
  - compatibilidade solver+malha móvel confirmada em caso real (ou o
    degrau é redefinido/adiado com o impedimento registrado);
  - compressão motored reativa (sem combustível, inerte) = caso R1
    (a reação não contamina o motored);
  - fechamento de energia reativo na malha móvel no padrão
    `verification.md` (inclui trabalho ∮p̄ dV);
  - conservação de massa de cada espécie.
- **Fora de escopo**: válvulas, injeção, chama de difusão.

### R4 — CH₄ (premistura gasosa homogênea)

- **O que adiciona**: trocar o combustível para CH₄, mesmo arcabouço do
  R3. Mecanismo recomendado: **GRI-Mech 3.0** (Smith et al. 1999,
  Berkeley) — 53 espécies / 325 reações, validado 1000–2500 K,
  10 Torr–10 atm, φ 0,1–5. Candidato leve: **DRM19** (redução do
  GRI-Mech, 19 espécies) — citado como candidato sem afirmar
  desempenho; a escolha entre GRI-Mech e DRM19 é feita com critério
  documentado (custo medido vs faixa de validade do caso, seção 6).
- **Gate antes de subir para R5**:
  - verificação do mecanismo contra dados publicados citados na
    referência (ignition delay/chamas);
  - custo por passo medido e registrado (a medir — seção 6);
  - se DRM19: divergência vs GRI-Mech no caso de referência
    quantificada antes de adotá-lo.
- **Fora de escopo**: gás natural (CH₄ puro ≠ gás natural — mesma
  observação do modo prescrito), NOₓ, emissões.

### R5 — Etanol (premistura gasosa homogênea)

- **O que adiciona**: etanol gasoso premisturado, mesmo arcabouço.
  Mecanismo: **a escolher entre candidatos** — Marinov 1999 (mecanismo
  etanol clássico) e versões do AramcoMech — apresentados como
  candidatos A CONFIRMAR; a contagem de espécies/reações de cada um só
  entra neste documento após verificação da fonte. Critério de escolha
  documentado (faixa de validade vs condições do motor, licença,
  disponibilidade do arquivo) é prerequisito do degrau.
- **Gate antes de subir para R6**: igual ao padrão (verificação contra
  dados publicados citados; custo medido).
- **Fora de escopo**: etanol/gasolina, emissões.

### R6 — Diesel PREMISTURADO (surrogate n-dodecano, Yao 2017)

- **O que adiciona**: diesel representado pelo surrogate **n-dodecano**
  — **Yao et al. 2017**, Fuel 191:339–349 — 54 espécies / 269 reações,
  química de alta e baixa temperatura (NTC), otimizado contra ECN
  Spray A; manuscrito aberto no UCL Discovery
  (discovery.ucl.ac.uk/id/eprint/1532208/). Alimentação ainda
  **premisturada homogênea** (o combustível entra gasoso, distribuído
  — NÃO é injeção). Candidatos alternativos registrados: Narayanaswamy
  et al. 2014 (255 espécies, CNF); Chishty et al. 2018 (usou Yao como
  referência; observou atividade de baixa temperatura possivelmente
  excessiva); Wehrfritz et al. 2018 (extensão 76 espécies / 423
  reações com NO e precursores de fuligem).
- **Gate antes de encerrar o escopo inicial**:
  - verificação do surrogate contra dados publicados (ECN Spray A =
    fonte de dados de referência para diesel, Sandia);
  - comportamento NTC reproduzido no 0-D antes de ir ao 3D;
  - custo por passo medido (54 espécies é muito acima das 13 do H₂ —
    número EXATO a medir, seção 6).
- **Fora de escopo**: injeção real (R7), emissões, fuligem (a extensão
  de Wehrfritz é candidata, não compromisso).

### R7 — Injeção DI / spray — FORA DO ESCOPO INICIAL

- **O que seria**: injeção direta de diesel (spray, queima não
  premisturada).
- **Por que fica fora**: exige dados que NÃO temos do ensaio — taxa de
  injeção, momento de injeção, geometria do injetor, temperatura de
  parede/injetor, composição detalhada do surrogate para fase
  líquida/vapor. Inventar esses dados é proibido pela mesma regra do
  resto do projeto. O degrau só é reaberto se esses dados forem
  obtidos de fonte citada.

## 3. Combustíveis e mecanismos

Mecanismos usados SOMENTE como publicados — nenhuma constante é
editada. As propriedades termoquímicas (polinômios NASA de Cp/h/s)
vêm **dos próprios arquivos dos mecanismos** — nada é inventado; com
isso Cp/γ deixam de ser constantes (efeito separado no R1).

| Combustível | Mecanismo recomendado | Espécies/reações | Referência | Alimentação | Status dos dados |
|---|---|---|---|---|---|
| H₂ | Burke et al. 2012 (núcleo ~19 reações, de Li et al. 2004) | 13 espécies (arquivo CHEMKIN, incl. banho N₂/Ar/He/CO/CO₂) | Burke, M. P. et al., *Int. J. Chem. Kinet.* 44 (2012) 444–474, DOI 10.1002/kin.20603 | premistura gasosa homogênea; Φ computável da configuração atual (m_fuel, ar, T1, P1) | alimentação computável hoje; verificação vs dados publicados do próprio artigo |
| H₂ (alternativo) | Ó Conaire et al. 2004 | não confirmado aqui | Ó Conaire, M. et al., *Combustion and Flame* (2004) — mecanismo H₂/O₂ amplamente usado em motores | idem | candidato; números a confirmar antes de uso |
| CH₄ | GRI-Mech 3.0 | 53 / 325 | Smith, G. P. et al., GRI-Mech 3.0, Berkeley, 1999, http://combustion.berkeley.edu/gri-mech/ | premistura gasosa homogênea; Φ computável (m_fuel, ar, T1, P1) | alimentação computável hoje; validade declarada 1000–2500 K, 10 Torr–10 atm, φ 0,1–5 |
| CH₄ (leve) | DRM19 (redução do GRI-Mech) | 19 / não confirmado aqui | citado como candidato | idem | candidato; desempenho NÃO afirmado sem medir |
| Etanol | Marinov 1999 ou AramcoMech | não confirmado aqui | Marinov, N. M. (1999), mecanismo etanol clássico; versões do AramcoMech | premistura gasosa homogênea; Φ computável | candidatos A CONFIRMAR; contagem de espécies só entra após verificação da fonte |
| Diesel (premisturado) | surrogate n-dodecano, Yao et al. 2017 | 54 / 269 (NTC; otimizado contra ECN Spray A) | Yao, T. et al., *Fuel* 191 (2017) 339–349, DOI 10.1016/j.fuel.2016.11.083; manuscrito aberto: discovery.ucl.ac.uk/id/eprint/1532208/ | premistura homogênea (R6) | alimentação premistura computável; DI = dados FALTANTES (abaixo) |
| Diesel (alternativos) | Narayanaswamy et al. 2014 (255 esp., CNF); Chishty et al. 2018 (usou Yao como referência; observou atividade de baixa T possivelmente excessiva); Wehrfritz et al. 2018 (extensão 76/423, NO + precursores de fuligem) | como indicado | como citado | idem | candidatos; a escolha definitiva é feita com critério documentado no degrau |

**Condições de alimentação — o que é computável hoje vs faltante:**

- **H₂, CH₄, etanol (premistura gasosa)**: Φ é computável da
  configuração atual do wiebepy — m_fuel, massa de ar, T1, P1. Nenhum
  dado novo é necessário para os degraus R2–R5 (e R6 no modo
  premisturado). A stoichiometria vem do próprio mecanismo.
- **Diesel DI (R7) — dados FALTANTES, listados explicitamente**:
  taxa de injeção (perfil de razão de injeção), momento (SOI),
  geometria do injetor, temperatura de parede e do injetor,
  composição do surrogate para o modelo de spray, e qualquer dado de
  ROHR/emissões (o ensaio não os fornece — seção 5). Enquanto não
  houver fonte citada para esses dados, R7 não sai do papel.

## 4. Solver e compatibilidade — VERIFICADO NO FONTE DO OF13 (2026-09-23)

Caminho reativo do OF13 confirmado por inspeção direta do fonte
instalado (`/opt/openfoam13/`, Ubuntu-22.04 WSL2) e dos tutoriais:

- **(a) Solver — CONFIRMADO**: no OF13 não há `reactingFoam` próprio; o
  executável `/opt/openfoam13/bin/reactingFoam` é um script que informa
  que foi substituído e executa **`foamRun -solver multicomponentFluid`**.
  O módulo `applications/modules/multicomponentFluid/` existe e seu
  cabeçalho declara *"multicomponent fluids with optional mesh motion
  and change"* (`multicomponentFluid.H:29`) — malha móvel suportada pelo
  mesmo framework `fvModels`/`fvConstraints` usado no modo prescrito
  (ex.: `fvModels().source(rho, Yi)` em `thermophysicalPredictor.C`).
- **(b) Combustion models — CONFIRMADO**: `src/combustionModels/` com
  `laminar` (cinética finita — caminho do R2/R4-R6), `PaSR`, `EDC`,
  `noCombustion` (transporte de espécies SEM reação — caminho do R1),
  `infinitelyFastChemistry`, `singleStepCombustion`, entre outros.
- **(c) Química — CONFIRMADO**: `src/thermophysicalModels/chemistryModel/`
  com `odeChemistryModel`, solvers `ode`, `EulerImplicit` e
  `noChemistrySolver`, tabulação ISAT e redução (DRGEP/DRG); métodos do
  `odeSolver` do OF13: Euler, EulerSI, RKCK45, RKDP45, RKF45,
  Rosenbrock12/23/34, SIBS, Trapezoid, rodas23, rodas34, seulex
  (`ODESolverNew.C`) — o padrão do wiebepy é `seulex` (o OF13 NÃO tem
  Rosenbrock43; correção registrada ao executar o caso R2);
  functionObject `adjustTimeStepToChemistry` para passo controlado pela
  química (seção 4c antiga — controles existem; custo continua a medir,
  seção 6).
- **(d) Formato de mecanismo — CONFIRMADO, com ressalva**: o leitor do
  OF13 NÃO lê CHEMKIN; os mecanismos entram em dicionário OpenFOAM
  (reactions `reversibleArrhenius`/`irreversibleArrhenius` + thermo por
  espécie com polinômios NASA low/high Cp — formato do tutorial
  `tutorials/multicomponentFluid/counterFlowFlame2D_GRI_TDAC`, que já
  traz o GRI-Mech 3.0 pré-convertido). A conversão CHEMKIN → OpenFOAM é
  feita pelo utilitário **`chemkinToFoam`**
  (`platforms/linux64GccDPInt32Opt/bin/chemkinToFoam`, incluído no OF13)
  — mecanismos publicados (Burke, GRI, Yao) precisam desse passo de
  conversão antes do uso.
- **(e) Reação + malha móvel — PLAUSÍVEL, A TESTAR (R3)**: o módulo
  declara suporte a movimento de malha e reusa o framework de fvModels
  do modo prescrito, mas não há tutorial de motor com `multicomponentFluid`
  no OF13 — a combinação com `dynamicMotionSolverList` +
  `crankConnectingRodMotion` (nossa infraestrutura) continua sendo gate
  de verificação prática do R3, não mais uma dúvida de existência.

Impedimentos 1–3 da seção 8 ficam resolvidos nesta inspeção (com a
ressalva (e)); a lista da seção 8 é atualizada em consequência.

## 5. Verificação e diagnóstico (o que é honesto prometer)

Os dados experimentais disponíveis são APENAS p×θ do ensaio
P_exp-Carga-3_45% (diesel; rpm 3396,2; Rc 17; P1 127,6 kPa @ −120°;
T1 308,15 K; Tw 440 K). NÃO há ROHR, emissões, taxa de injeção nem
composição do surrogate. Conclusão honesta:

- **O modo reativo nascente NÃO pode ser validado contra o ensaio** —
  não há dado de combustão independente (a pressão do ensaio já foi
  usada para calibrar a Wiebe; usá-la também para "validar" a química
  repetiria o mesmo problema do modo prescrito, agravado).
- **Verificação**: casos 0-D/autoignição — ignition delay de shock tube
  da LITERATURA (dados publicados e citados das próprias referências
  dos mecanismos, ex. as chamas diluídas de alta pressão do Burke
  2012, a faixa 1000–2500 K do GRI-Mech, o ECN Spray A do Yao 2017) —
  comparação com dados PUBLICADOS, citados; e consistência interna
  (fechamento de energia, conservação de massa/elementos) no padrão
  do `verification.md`.
- **Diagnóstico contra o ensaio**: p×θ do caso reativo sobreposto ao
  ensaio com as MESMAS ressalvas do modo prescrito (p̄ volumétrica ≠
  pressão no sensor; surrogate ≠ diesel real; premistura ≠ DI) —
  leitura diagnóstica, nunca "o modelo previu o ensaio".
- Nenhum resultado de emissão, knock ou eficiência é reportado no modo
  reativo nascente — não há dado para confrontar.

## 6. Custo computacional — A MEDIR (protocolo)

Nenhum número de custo do modo reativo é prometido. Referência única
existente: o caso prescrito de referência (malha 24×36, janela
−120°…+120°) leva **~150 s** (wall-clock, WSL2, registrado no
`verification.md`).

Protocolo de medição (executar ANTES de qualquer promessa):

1. **Mesma malha 24×36** e mesma janela para todos os casos medidos.
2. **Mesma janela angular** (−120°…+120°) e mesmo critério de passo
   onde aplicável.
3. Medir **s/°CA** (tempo total / graus percorridos) de:
   a. `prescribed_wiebe` (baseline ~150 s re-medido na mesma sessão);
   b. reativo H₂ (R2, malha fixa) e (R3, malha móvel);
   c. reativo CH₄ (GRI-Mech e DRM19, se ambos medidos);
   d. reativo diesel premisturado (Yao 2017).
4. Registrar separadamente: custo de montagem química por passo,
   número de subpassos de integração química, e custo de I/O — para
   separar custo da química do custo do solver.
5. Publicar os números na tabela de verificação do degrau (com
   máquina/versão), não neste roadmap; este documento lista "a medir"
   até a medição existir.
6. Regra: se o custo medido inviabilizar um degrau, o degrau é
   reescopo (malha menor, mecanismo mais leve, janela reduzida) com a
   decisão registrada — nunca um número otimista no lugar da medição.

## 7. Wiebe no modo reativo — comparação, nunca fonte

No modo reativo a Wiebe não entra na física do caso. Ela reaparece
APENAS no pós-processo comparativo:

- **p×θ**: sobreposição do caso reativo vs caso prescrito vs ensaio,
  com RMSE p×θ contra o ensaio nas mesmas métricas do
  `verification.md` (p_max/erro, fase, viés, RMSE) — leitura
  DIAGNÓSTICA.
- **x(θ)**: fração queimada da Wiebe calibrada vs fração de calor
  liberado integrada da química — comparar forma/fase/liberação
  acumulada; usar para diagnosticar onde a química antecipa/atrasa em
  relação à Wiebe calibrada.
- O relatório do caso reativo declara explicitamente:
  `source = chemistry` (nunca Wiebe), o mecanismo e sua referência, e
  que a Wiebe exibida é comparação. Nenhum ajuste da Wiebe a partir do
  caso reativo é feito automaticamente (ajuste posterior, se houver,
  é decisão registrada do usuário).

## 8. Impedimentos registrados

Lista viva — cada item é resolvido (ou reescopado) antes do degrau que
depende dele:

1. **~~Compatibilidade do solver reativo no OF13~~ — RESOLVIDO
   (seção 4a-d)**: caminho reativo = `foamRun -solver multicomponentFluid`;
   combustion models `laminar`/`PaSR`/`noCombustion` confirmados no
   fonte; `chemkinToFoam` disponível para conversão de mecanismos.
   Restante: teste prático de reação + malha móvel (item 2).
2. **~~Termoquímica × química~~ — RESOLVIDO (seção 4d)**: a termoquímica
   multicomponente do OF13 usa polinômios NASA low/high Cp por espécie
   (formato dos tutoriais `multicomponentFluid`), o mesmo formalismo dos
   arquivos dos mecanismos publicados — compatível por construção com
   `chemkinToFoam`. A verificação numérica (fechamento com NASA vs Cp
   constante) permanece gate do R1.
3. **~~Integração química e passo~~ — CONTROLES CONFIRMADOS
   (seção 4c)**: solvers `ode` (métodos do `ODESolverNew.C` — padrão
   do wiebepy: `seulex`), `EulerImplicit`, `initialChemicalTimeStep` e
   functionObject `adjustTimeStepToChemistry` existem no OF13; o CUSTO
   multiplicado continua a medir (item 7).
4. **Mecanismo de etanol a escolher** (R5): Marinov 1999 vs AramcoMech
   — critério de escolha documentado (faixa de validade vs condições
   do motor, disponibilidade do arquivo, licença) é prerequisito;
   contagens de espécies só após verificação da fonte.
5. **Dados DI faltantes** (R7): taxa de injeção, SOI, T de parede/
   injetor, composição do surrogate para spray — sem fonte citada, R7
   permanece fora do escopo.
6. **Licenças dos mecanismos**: GRI-Mech e AramcoMech têm termos
   próprios de uso/redistribuição — verificar antes de embutir
   qualquer arquivo no repositório; H₂ (Burke) e o surrogate (Yao,
   UCL Discovery) igualmente, conforme a fonte do arquivo usado.
7. **Custo computacional não medido**: todos os números de custo do
   modo reativo estão "a medir" até o protocolo da seção 6 ser
   executado.
8. **~~functionObjects gravam campo TODO passo~~ — RESOLVIDO
   (2026-09-24)**: no OF13 os FOs `multiply` (ρ·Yᵢ, R1/R2) e
   `wallHeatFlux` usam `writeControl timeStep` por padrão e gravam o
   campo resultante a CADA passo (um diretório de tempo por passo —
   milhares de diretórios até o fim da janela; registrado no primeiro
   caso de verificação R2). Correção: `writeControl writeTime;`
   explícito nesses FOs no case_builder (testes de regressão em
   tests/test_cfd.py).
9. **~~FO `Qdot` com `executeControl writeTime` congela o campo~~ —
   RESOLVIDO (2026-09-24)**: no OF13 o FO do tipo `Qdot` é quem
   RECALCULA o campo `Qdot` — com `executeControl writeTime` o campo só
   era atualizado nos writeTimes e o `QdotIntegral` integrava valor
   parado entre eles (segundo caso R2: 256 J "liberados" com 42 J de
   combustível — série bit-a-bit constante, 2,65274987e+06 W, ao longo
   de ~2000 passos). Correção: `executeControl timeStep;` (campo vivo)
   + `writeControl writeTime;` (sem dump do campo a cada passo) no
   case_builder. Verificação numérica do fechamento reexecutada no caso
   regenerado.