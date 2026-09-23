# Arquitetura do módulo CFD (opcional) do wiebepy

Status: **implementado (modo 4.1 — Wiebe prescrita)** · Modo 4.2 (reativo):
**apenas arquitetura, não implementado** · Última revisão: 2026-09-23

## 1. Objetivos e limites

O módulo permite estudar o escoamento 3D compressível transiente no
cilindro com liberação de calor GLOBAL prescrita pela função Wiebe
calibrada (1–5 estágios), para os combustíveis H₂, CH₄, etanol e diesel.

**O que ele NÃO faz** (declarado em toda saída — case_config.yaml,
relatório HTML, GUI):

- **Não prevê cinética química, frente de chama, knock ou emissões.**
  A combustão é uma fonte de calor prescrita: o resultado 3D é
  condicionado à curva Wiebe de entrada.
- **Não é predição independente de combustível**: trocar o combustível
  mantendo a mesma massa não troca a energia (mesma massa ≠ mesma
  energia); o critério de comparação entre combustíveis é registrado
  explicitamente (`comparison.criterion`, padrão
  `same_rpm_same_energy`). No modo prescrito a comparação de
  combustíveis NÃO é predição de troca de combustível.
- **Não substitui o 0-D**: com `cfd.enabled: false` (padrão) o wiebepy
  funciona exatamente como antes (mfb/pressão, calibração, CPU/GPU,
  GUI, gráficos, exportações, relatório HTML). Nenhuma dependência de
  CFD é importada; não há subprocessos, downloads ou detecção pesada.
- **Não escreve um solver próprio em Python** — usa um solver
  consolidado (decisão na seção 3).

## 2. Layout do código

```
src/wiebepy/cfd/
├── __init__.py          # cfd_enabled(); fronteira de import opcional
├── config.py            # CfdConfig (validação), CaseState (máquina de estados)
├── capabilities.py      # detecção de ambiente (WSL2/solver) só sob demanda
├── validation.py        # validação de caso pré-execução (escalera V&V)
├── case_builder.py      # gera o caso OpenFOAM a partir de CfdConfig+EngineConfig
├── runner.py            # execução (blockMesh/foamRun), logs, cancelamento, lock
├── results.py           # leitura pós-execução (séries 0-D extraídas, integrais)
├── reporting.py         # relatório HTML autônomo com proveniência completa
├── geometry/            # cinemática pistão (reusa EngineConfig), relatório de hipóteses
├── fuels/               # registro H2/CH4/etanol/diesel (propriedades COM fonte)
├── sources/             # wiebe_heat_release: Q̇(t) conservativa (§7)
├── adapters/            # base.py + openfoam.py (decisão de solver, execução WSL2)
└── templates/           # trechos de dicionário OF13
```

Regras de fronteira:

- O núcleo (`wiebepy.core`, `wiebepy.pressure`, GUI, CLI principal) **não
  importa nada de `wiebepy.cfd`** a não ser `cfd_enabled()` (leitura de
  config, sem dependências de solver). Com CFD desligado, nada de CFD é
  importado.
- O pacote CFD não depende de detalhes internos do solver: só o adapter
  `openfoam` conhece dicionários/executáveis OF13.
- `single_wiebe` e `double_wiebe` do núcleo são referências independentes
  e não foram modificados; a fonte CFD consome
  `multistage_wiebe_derivative` (uma única implementação de dx_b/dθ).

## 3. Decisão de solver (registrada)

**Escolha: OpenFOAM Foundation (openfoam.org), versão 13** —
`foamRun` com o solver modular `fluid`.

Motivos: código aberto sem restrição de uso; solver compressível
transiente com energia e malha móvel prontos (fvMeshMovers
`multiValveEngine` + `crankConnectingRodMotion`); fvModels `heatSource`
para fonte volumétrica; documentação oficial da versão 13
(openfoam.org/doc/html-v13) e tutoriais de referência lidos diretamente
da instalação; execução em WSL2 no Windows e nativa no Linux.

Alternativas descartadas: escrever solver Navier–Stokes em Python
(explícitamente proibido pelo escopo), forks comerciais/derivados com
licença restritiva.

Versões e ambiente de referência (registrados no caso em
`case_config.yaml > solver`): OpenFOAM 13, build
linux64GccDPInt32Opt, WSL2 Ubuntu-22.04.

## 4. Fonte de calor conservativa (§7) — e a armadilha do OF13

Cadeia de cálculo (unidades explícitas):

1. `Q̇(θ) = m_f · PCI · (dx_b/dθ) · (dθ/dt)` com
   `dθ/dt = 6·RPM` [°/s] (graus) ou `2π·RPM/60` [rad/s];
   `m_f [kg] · PCI [kJ/kg] = kW → ×1e3 = W`.
2. Verificação de fechamento: `∫Q̇ dt = m_f·PCI·Δx_b`
   (erro relativo < 0,1 % registrado em `case_config.yaml`).
3. Distribuição espacial uniforme (referência): `q'''(x,t) = Q̇(t)·f`,
   `∫f dV = 1` ⇒ na malha discreta `Σᵢ q'''ᵢ·Vᵢ = Q̇` sobre os volumes
   **atuais**.
4. **Armadilha do OpenFOAM 13 (descoberta em verificação, 2026-09)**:
   o modo `Q` (potência total) do fvModel `heatSource` envolve a tabela
   em `Function1s::Scale` com `Constant("1/V", 1/zone_.V())` — o volume
   da zona é capturado **uma única vez, na construção do fvModel**
   (fonte: `src/fvModels/general/heatSource/heatSource.C` e
   `fvCellZoneI.H` do OF13). Com pistão móvel (V_start = 3,53e-4 m³ →
   V_TDC = 2,36e-5 m³, Rc 17) a energia realmente injetada caía para
   ~4 % da prescrita. Diagnóstico por bisseção com sondas WSL2:
   malha fixa + tabela ⇒ 369 J entregues (T 800→2140 K); malha móvel +
   a mesma tabela ⇒ ~15 J (T final 854,6 K).
5. **Correção adotada**: prescrever a densidade diretamente,
   `q'''(CA) = Q̇(CA)/V₀(CA)` [W/m³], com V₀ o volume cinemático 0-D —
   exatamente o formalismo §7 com f = 1/V₀. O fvModel aplica
   `Σᵢ q'''ᵢ·Vᵢᵃᵗᵘᵃˡ = Q̇·(ΣVᵢᵃᵗᵘᵃˡ/V₀(θ)) ≈ Q̇` a cada instante
   (a malha reproduz V₀ com erro ≤ 0,2 % — verificado no caso real).
   O modo `Q` permanece apenas para `distribution: region`, com a
   limitação registrada no aviso de distribuição (a região + pistão
   móvel não é o caminho de referência).
6. **Nunca se adiciona a mesma energia duas vezes**: o CFD calcula a
   troca térmica nas paredes; o κ 0-D e a correlação de Hohenberg NÃO
   são transferidos para o CFD (campo `gas_model.notice` no
   case_config.yaml).
7. **Grade da tabela e da verificação convergida (2026-09-23)**: a
   grade fixa de 0,1° subintegra estágios com m pequeno (queima
   concentrada numa faixa angular fina — ex. m=0,075: déficit de
   0,29 % na 1ª célula de queima). O builder refina a grade da
   verificação ∫Q̇dt = m_f·PCI·Δx_b (0,1° → 0,05° → 0,02° → 0,01° →
   0,005°) e usa a MESMA grade na tabela do fvModel, gravando o passo
   em `heat_source.table_step_CA_deg`. Se nenhum passo fecha, o erro é
   levantado — a fonte nunca é aceita com conservação falhando.

## 5. Geometria e hipóteses

- Geometria paramétrica de cilindro (blockMesh, pistão plano), reusando
  `bore/stroke/rod_length/Rc/rpm` do `EngineConfig` existente; referência
  de PMP a θ=0. Sem válvulas/câmara de topo — janela **válvulas
  fechadas** (padrão −120°…+120°).
- `geometry.motion_report` registra hipóteses, V_start/V_min/V_max e a
  verificação V(θ) contra o 0-D.
- **Sem calibração automática de Rc no CFD** (o Rc vem do motor).
- Malha cúbica-axissimétrica simples; a independência de malha é
  responsabilidade do usuário (escada de V&V na seção 7).

## 6. Combustíveis

Registro `fuels/` com composição, alimentação, PCI (unidade + **fonte
citada**), propriedades, modelo de combustão e faixa de validade —
H₂, CH₄, etanol e diesel permanecem todos configuráveis. CH₄ puro ≠
gás natural (observação explícita); diesel exige surrogate (registrado
como limitação; no modo prescrito entra apenas via PCI). **O combustível
do caso de teste/referência é DIESEL**, pois o experimento de pressão
que origina o motor calibrado (ensaio P_exp-Carga-3_45%) foi executado
com diesel — o PCI usado na fonte é o do ensaio (39 191,3 kJ/kg,
seção engine), não a referência típica do registro. No modo prescrito,
a troca de combustível só muda o PCI/m_f — não há mecanismo químico
(`mechanism is None` para todos).

**Cadastro permanente de combustíveis (aba "Combustíveis" da GUI)**:
além dos quatro embutidos, o usuário pode cadastrar combustíveis
próprios (gravados em `data/fuels_custom.yaml`, permanecem entre
sessões) e exportar/lê-los em CSV (`;`-separado, UTF-8 — biblioteca
portátil). Nenhuma propriedade é aceita sem fonte: o cadastro exige
`LHV_source` (fonte do PCI). Os embutidos nunca são alterados no
código; um cadastro com o mesmo nome sobrepõe o embutido em memória,
com o registro marcando a substituição (remover o cadastro restaura o
embutido). A validação de `cfd.fuel.name` aceita o registro combinado
(embutidos + cadastrados).

## 7. Verificação e validação (escada progressiva)

1. **Regressão com CFD off**: suíte completa do wiebepy (365 testes)
   inalterada; o módulo CFD não é importado (teste de fronteira).
2. **Testes da fonte Wiebe**: conservação ∫Q̇dt = m_f·PCI·Δx_b para
   N = 1..5 em deg e rad; identidade ponto a ponto q'''·V₀ = Q̇; tabelas
   Function1 com fechamento verificado (52 testes CFD).
3. **Escada do solver** (casos reais executados — ver
   `docs/cfd/verification.md`):
   1. volume fixo, frio (V1) — conserva massa, p(t) ideal;
   2. volume fixo + fonte (sonda) — entrega ∫Q̇dt (T→2140 K);
   3. pistão móvel frio — p(V) motored ≈ p₀(V₀/V)^γ;
   4. pistão móvel + fonte Wiebe (caso referência) — balanço de energia
      fecha: prescrito = ΔU + trabalho + perda nas paredes;
   5. comparação 0-D (p×θ CFD vs motored/0-D) — diferenças explicadas;
   6. comparação experimental (DIAGNÓSTICA, nunca validação) — ensaio
      P_exp-Carga-3_45% (diesel); escada de perdas às paredes
      (adiabático → 440 K), casos controlados: motorados 007/008,
      passo temporal 011, malha fina 010, Rc efetivo 012 (ver
      `verification.md` §3a–3c);
   7. calibração (ajuste da fonte Wiebe ao ensaio) é distinta de
      validação — a fonte prescrita usa os mesmos dados na calibração.
4. **Entrega exige pelo menos um caso real executado** —
   `results/cfd/case_001` (executado de ponta a ponta no WSL2).

## 8. Execução e paralelismo

- Paralelismo do **solver** (MPI, `workers`) é separado dos backends
  CPU/GPU do wiebepy (0-D) — nunca misturados.
- stdout/stderr capturados em `logs/`; cancelamento mata filhos/MPI;
  lock (`state.yaml` + `.run.lock`) impede execução dupla; logs e
  resultados parciais preservados no cancelamento/falha.
- **"Processo terminou" ≠ "convergiu"**: o estado Concluído significa
  processo finalizado sem erro; a qualidade (fechamento de energia,
  continuidade) é reportada separadamente.
- **Sem fallback silencioso para 0-D**: se o solver não está
  disponível, os comandos CFD falham com diagnóstico (`doctor`); os
  resultados 0-D nunca são apresentados como CFD.
- Reivindicações de GPU só existem se o adapter realmente as suportar
  e tiverem sido testadas (hoje: nenhuma).

## 9. Limites científicos (documentados também no relatório HTML)

- A pressão volumétrica média **não identifica unicamente** os campos
  3D: distribuições espaciais diferentes podem dar p̄(θ) semelhantes —
  o modo prescrito (uniforme) é o caso de referência, não a chama real.
- Pressão medida vs média de volume vs sonda: o relatório distingue as
  três.
- Ar simplificado (perfectGas, Cp/mu constantes): hipótese declarada;
  turbulência (kEpsilon e kOmegaSST, com wall functions e campo omega
  no builder) é caminho de refinamento configurável — no caso de
  referência do ensaio Diesel, kEpsilon + malha refinada eleva a
  perda às paredes de 16 J (laminar) para 44,1 J vs alvo Hohenberg
  53,7 J (verification.md §3b).
- Modo 4.2 (reativo): **apenas arquitetura** — nunca apresentado como
  funcional; nunca substituir silenciosamente a fonte Wiebe por
  combustão reativa (ou vice-versa).