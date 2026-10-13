# -*- coding: utf-8 -*-
"""Textos de ajuda da CLI (--help, --help-model, --help-examples)."""

DESCRIPTION = """\
wiebepy — funções Wiebe de 1 a 5 estágios (single, double, triple, 4- e
5-stage): avaliação da fração de massa queimada x_b(θ) e da taxa de queima
dx_b/dθ, ajuste a dados experimentais (PSO + refinamento local), múltiplos
runs com estatística, comparação objetiva entre números de estágios e
execução serial, paralela (CPU) ou em GPU NVIDIA.

O que é uma função Wiebe
  Uma curva em S que descreve a fração da massa de combustível já queimada
  em função do ângulo do virabrequim θ. Cada estágio j começa em θ0_j, dura
  Δθ_j, tem forma m_j e eficiência a_j; o estágio contribui com a fração
  β_j da massa total (Σβ_j = 1). Vários estágios representam fases
  distintas da combustão (ex.: pré-misturada + difusão + queima tardia).

Parâmetros de cada estágio (unidades)
  beta      fração da massa do estágio [-], 0 ≤ β ≤ 1, Σβ = 1
  theta0    início da combustão do estágio [°] (ou rad com --angle-unit rad)
  duration  duração Δθ [mesma unidade de θ], > 0
  m         fator de forma [-], > 0 (m pequeno: início abrupto)
  a         eficiência [-]; a = 6.908 ⇒ 99.9 % queimado ao fim de Δθ
  x_b é adimensional; dx_b/dθ tem unidade 1/° (ou 1/rad).

Modos de execução
  (padrão)            avalia um modelo numa grade θ (--theta-min/max/step)
  --optimize          ajusta N estágios aos dados de --input
  --compare-stages    ajusta vários N e compara (RMSE, MAE, SEE, R², AIC,
                      BIC, validação cruzada por blocos, tempo)
  --benchmark         mede os backends nesta máquina
  --devices           mostra o hardware detectado
  wiebepy cfd …       subcomando CFD OPCIONAL (OpenFOAM 13 via WSL2):
                      doctor/prepare/validate/run/status/cancel/report —
                      liberação de calor PRESCRITA pela Wiebe calibrada;
                      não prevê cinética química, frente de chama ou
                      emissões (ver README, seção CFD)

Backends (--backend)
  auto             mede os disponíveis com o tamanho real do problema e
                   escolhe o mais rápido (padrão)
  numpy            enxame vetorizado (S candidatos × n pontos), 1 núcleo
  numba            kernel compilado, --workers threads (requer numba)
  multiprocessing  enxame dividido entre --workers processos (NumPy)
  cupy             GPU NVIDIA (requer cupy-cuda12x); --gpu é atalho
  Backend indisponível ⇒ WARNING e fallback (cupy → numba → numpy).
  Runs independentes (--runs) rodam em processos paralelos com o backend
  numpy; com numba/cupy rodam em sequência (já paralelos por dentro).

Formatos de entrada (--input)
  .csv/.txt/.dat com cabeçalho: theta,xb  |  theta,dxb_dtheta  |
  theta,xb,dxb_dtheta  (+ weight ou sigma opcionais); sem cabeçalho:
  2 colunas = theta,xb e 3 colunas = theta,xb,dxb_dtheta.
  .json: {"theta": [...], "xb": [...], "dxb_dtheta": [...]}.
  Configuração (--config): .json, .yaml ou .toml (ver README).
"""

EPILOG = """\
exemplos:
  wiebepy --stages 3 --plot
  wiebepy --stages 2 --optimize --input data.csv --runs 10 --save-plots
  wiebepy --compare-stages 1 2 3 4 5 --input data.csv --backend auto
  wiebepy --benchmark --workers 8
  wiebepy --help-model      (formulação matemática)
  wiebepy --help-examples   (comandos prontos para cada caso)
"""

HELP_MODEL = r"""
FORMULAÇÃO MATEMÁTICA — Wiebe de N estágios (N = 1..5)
======================================================

Para cada estágio j = 1..N:

    z_j(θ) = (θ − θ0_j) / Δθ_j

    x_j(θ) = 0                                  se θ < θ0_j
    x_j(θ) = 1 − exp[ −a_j · z_j^(m_j+1) ]      se θ ≥ θ0_j

    dx_j/dθ = a_j (m_j + 1) / Δθ_j · z_j^m_j · exp[ −a_j · z_j^(m_j+1) ]

Fração de massa queimada e taxa de queima:

    x_b(θ)    = Σ_j β_j · x_j(θ)
    dx_b/dθ   = Σ_j β_j · dx_j/dθ

Restrições: 0 ≤ β_j ≤ 1, Σ β_j = 1, Δθ_j > 0, m_j > 0, a_j > 0.
Com elas cada x_j é monotônica em [0, 1), logo 0 ≤ x_b ≤ 1 (o código
recorta ruído de ponto flutuante). a = 6.908 = ln(1000) faz o estágio
atingir 99.9 % em θ0 + Δθ. N = 1 é a Wiebe simples; N = 2 com β_1 = α é o
double-Wiebe clássico.

PARAMETRIZAÇÃO USADA NO AJUSTE (vetor de busca em caixa)
  inícios   θ0_1 e incrementos δθ_j ≥ 0:  θ0_j = θ0_1 + Σ_{k≤j} δθ_k
            (impõe θ0_1 ≤ … ≤ θ0_N e elimina permutações de estágios);
            θ0_N ≤ θ0_max (padrão θ_max dos dados) com penalidade suave
  pesos     --beta-param stick (padrão): s_1..s_{N−1} ∈ [0, 1]
                β_1 = s_1, β_j = s_j Π_{k<j}(1 − s_k), β_N = Π_{k<N}(1 − s_k)
            --beta-param softmax: z_1..z_{N−1}, z_N = 0,  β = softmax(z)
            --beta-param explicit: β_1..β_{N−1} livres, β_N = 1 − Σ
                (soma > 1 penalizada) — modo tradicional, para comparação
  a_j       fixo em --a-fixed (6.908) ou ajustado com --fit-a
  k (nº de parâmetros livres) = 4N − 1, ou 5N − 1 com --fit-a.

FUNÇÃO OBJETIVO (r = simulado − experimental)
  rmse  √(Σr²/n)   mse  Σr²/n   mae  Σ|r|/n   see  √(Σr²/(n−k))
  wrmse √(Σw r²/Σw)  (w do arquivo, ou w = 1/σ²)
  --fit-target xb | dxb | both;  both: J = w_x·J(x_b)/s_x + w_d·J(dx_b)/s_d,
  com s_x, s_d = desvio-padrão das séries experimentais.

COMPARAÇÃO DE MODELOS
  AIC = n ln(SSE/n) + 2k      BIC = n ln(SSE/n) + k ln(n)
  Supõem resíduos independentes; em curvas de x_b os resíduos são
  autocorrelacionados (Durbin-Watson reportado), o que favorece modelos
  maiores. A recomendação usa validação cruzada por blocos contíguos curtos
  de θ intercalados entre os folds (sem extrapolação) e a regra: menor N
  com erro de CV a até 5 % do melhor e sem estágios desprezíveis
  (β < 0.5 %) ou coincidentes. Antes, cada N é refinado a partir do ótimo
  de N+1 sem um estágio (modelos aninhados), o que corrige falhas pontuais
  do otimizador.
"""

HELP_EXAMPLES = """
EXEMPLOS PRONTOS
================
(use `python main.py` no lugar de `wiebepy` se não instalou o pacote)

# Avaliar modelos (sem dados) numa grade de -20° a 100°, passo 0.1°
wiebepy --stages 1 --theta-min -20 --theta-max 100 --theta-step 0.1 --plot   # single-Wiebe
wiebepy --stages 2 --save-plots --output results/double                      # double-Wiebe
wiebepy --stages 3 --plot                                                    # triple-Wiebe
wiebepy --stages 4 --save-plots --output results/four                        # 4-stage
wiebepy --stages 5 --save-plots --output results/five                        # 5-stage

# Avaliar um modelo salvo (model.json de um ajuste anterior)
wiebepy --model results/fit/model.json --theta-min -30 --theta-max 120 --plot

# Ajuste experimental (x_b), 10 runs, gráficos salvos
wiebepy --stages 3 --optimize --input examples/data/synthetic_3stage.csv \\
        --population 60 --iterations 500 --runs 10 --save-plots --output results/fit3

# Ajuste usando x_b e dx_b/dθ juntos, com a_j ajustado
wiebepy --stages 2 --optimize --input dados.csv --fit-target both --fit-a

# Execução paralela em CPU
wiebepy --stages 4 --optimize --input dados.csv --runs 16 --backend numba --workers 8
        # enxame em Numba com 8 threads (runs em sequência) — o mais rápido
        # em CPU nas medições deste projeto
wiebepy --stages 4 --optimize --input dados.csv --runs 16 --backend numpy --workers 8
        # 16 runs distribuídos em 8 processos (NumPy em cada um)

# GPU NVIDIA (CuPy). Só compensa em problemas grandes (enxame × pontos
# ≳ 1e6); float32 acelera ainda mais, mas a busca fica menos precisa
wiebepy --stages 5 --optimize --input dados_grandes.csv --gpu --population 1000

# Comparar 1 a 5 estágios (AIC/BIC + validação cruzada por blocos)
wiebepy --compare-stages 1 2 3 4 5 --input examples/data/synthetic_3stage.csv \\
        --optimize --population 100 --iterations 1000 --runs 20 \\
        --backend auto --workers 8 --save-plots

# Curva de PRESSÃO do ensaio (θ em rad, P em bar): modelo 0-D do Double
# Wiebe com N estágios de liberação de calor; Rc ajustado
wiebepy --stages 2 --optimize --input examples/data/ensaio_P_exp_carga3_45.txt \\
        --input-type pressure --pressure-unit bar --runs 5 --save-plots
wiebepy --compare-stages 1 2 3 --input ensaio.txt --input-type pressure

# Usar um arquivo de configuração (CLI sobrescreve o arquivo)
wiebepy --config examples/config_example.yaml --input dados.csv --optimize

# CFD opcional (requer OpenFOAM 13 no WSL2): o fluxo completo
wiebepy cfd doctor                                        # ambiente WSL2/OpenFOAM
wiebepy cfd prepare  --config examples/config_cfd.yaml    # gera o caso, sem rodar
wiebepy cfd validate --case results/cfd/case_001          # valida antes de rodar
wiebepy cfd run      --case results/cfd/case_001 --follow # executa com log ao vivo
wiebepy cfd status   --case results/cfd/case_001          # estado do caso
wiebepy cfd cancel   --case results/cfd/case_001          # interrompe a execução
wiebepy cfd report   --case results/cfd/case_001          # relatório HTML do caso
# Variantes de preparação: --no-heat (caso motrado, sem fonte) e
# --fixed-piston (pistão fixo). A fonte Wiebe é verificada
# energeticamente na preparação (integral Q̇dt = m_f·PCI·Δx_b em 0,1 %).

# Benchmark dos backends nesta máquina e hardware detectado
wiebepy --benchmark --workers 8 --output results/bench
wiebepy --devices
"""


# =============================================================================
# Inglês — os textos longos ficam em constantes paralelas (e não no
# dicionário de i18n): são documentos, revisados como documentos.
# =============================================================================
DESCRIPTION_EN = """\
wiebepy — Wiebe functions with 1 to 5 stages (single, double, triple, 4- and
5-stage): evaluation of the mass fraction burned x_b(θ) and of the burn rate
dx_b/dθ, fitting to experimental data (PSO + local refinement), multiple runs
with statistics, objective comparison across stage counts, and serial,
parallel (CPU) or NVIDIA GPU execution.

What a Wiebe function is
  An S-shaped curve describing the fraction of the fuel mass already burned
  as a function of the crank angle θ. Each stage j starts at θ0_j, lasts
  Δθ_j, has shape m_j and efficiency a_j; the stage contributes the fraction
  β_j of the total mass (Σβ_j = 1). Several stages represent distinct phases
  of the combustion (e.g. premixed + diffusion + late burning).

Parameters of each stage (units)
  beta      mass fraction of the stage [-], 0 ≤ β ≤ 1, Σβ = 1
  theta0    start of the stage's combustion [°] (or rad with --angle-unit rad)
  duration  duration Δθ [same unit as θ], > 0
  m         shape factor [-], > 0 (small m: abrupt start)
  a         efficiency [-]; a = 6.908 ⇒ 99.9 % burned by the end of Δθ
  x_b is dimensionless; dx_b/dθ has unit 1/° (or 1/rad).

Execution modes
  (default)           evaluates a model on a θ grid (--theta-min/max/step)
  --optimize          fits N stages to the data from --input
  --compare-stages    fits several N and compares them (RMSE, MAE, SEE, R²,
                      AIC, BIC, blocked cross-validation, time)
  --benchmark         measures the backends on this machine
  --devices           shows the detected hardware
  wiebepy cfd …       OPTIONAL CFD subcommand (OpenFOAM 13 through WSL2):
                      doctor/prepare/validate/run/status/cancel/report — the
                      heat release is PRESCRIBED by the calibrated Wiebe
                      function; it does not predict chemical kinetics, flame
                      front or emissions (see the README, CFD section)

Backends (--backend)
  auto             measures the available ones with the real problem size
                   and picks the fastest (default)
  numpy            vectorized swarm (S candidates × n points), 1 core
  numba            compiled kernel, --workers threads (requires numba)
  multiprocessing  swarm split across --workers processes (NumPy)
  cupy             NVIDIA GPU (requires cupy-cuda12x); --gpu is a shortcut
  An unavailable backend ⇒ WARNING and fallback (cupy → numba → numpy).
  Independent runs (--runs) go to parallel processes with the numpy backend;
  with numba/cupy they run in sequence (already parallel inside).

Input formats (--input)
  .csv/.txt/.dat with a header: theta,xb  |  theta,dxb_dtheta  |
  theta,xb,dxb_dtheta  (+ optional weight or sigma); without a header:
  2 columns = theta,xb and 3 columns = theta,xb,dxb_dtheta.
  .json: {"theta": [...], "xb": [...], "dxb_dtheta": [...]}.
  Configuration (--config): .json, .yaml or .toml (see the README).
"""

EPILOG_EN = """\
examples:
  wiebepy --stages 3 --plot
  wiebepy --stages 2 --optimize --input data.csv --runs 10 --save-plots
  wiebepy --compare-stages 1 2 3 4 5 --input data.csv --backend auto
  wiebepy --benchmark --workers 8
  wiebepy --help-model      (mathematical formulation)
  wiebepy --help-examples   (ready-made commands for each case)
"""

HELP_MODEL_EN = r"""
MATHEMATICAL FORMULATION — N-stage Wiebe (N = 1..5)
===================================================

For each stage j = 1..N:

    z_j(θ) = (θ − θ0_j) / Δθ_j

    x_j(θ) = 0                                  if θ < θ0_j
    x_j(θ) = 1 − exp[ −a_j · z_j^(m_j+1) ]      if θ ≥ θ0_j

    dx_j/dθ = a_j (m_j + 1) / Δθ_j · z_j^m_j · exp[ −a_j · z_j^(m_j+1) ]

Mass fraction burned and burn rate:

    x_b(θ)    = Σ_j β_j · x_j(θ)
    dx_b/dθ   = Σ_j β_j · dx_j/dθ

Constraints: 0 ≤ β_j ≤ 1, Σ β_j = 1, Δθ_j > 0, m_j > 0, a_j > 0.
With them each x_j is monotonic in [0, 1), hence 0 ≤ x_b ≤ 1 (the code clips
floating-point noise). a = 6.908 = ln(1000) makes the stage reach 99.9 % at
θ0 + Δθ. N = 1 is the plain Wiebe; N = 2 with β_1 = α is the classic
double-Wiebe.

PARAMETRIZATION USED IN THE FIT (boxed search vector)
  starts    θ0_1 and increments δθ_j ≥ 0:  θ0_j = θ0_1 + Σ_{k≤j} δθ_k
            (imposes θ0_1 ≤ … ≤ θ0_N and removes stage permutations);
            θ0_N ≤ θ0_max (default: the data's θ_max) with a soft penalty
  weights   --beta-param stick (default): s_1..s_{N−1} ∈ [0, 1]
                β_1 = s_1, β_j = s_j Π_{k<j}(1 − s_k), β_N = Π_{k<N}(1 − s_k)
            --beta-param softmax: z_1..z_{N−1}, z_N = 0,  β = softmax(z)
            --beta-param explicit: β_1..β_{N−1} free, β_N = 1 − Σ
                (a sum > 1 is penalized) — the traditional mode, for
                comparison
  a_j       fixed at --a-fixed (6.908) or fitted with --fit-a
  k (number of free parameters) = 4N − 1, or 5N − 1 with --fit-a.

OBJECTIVE FUNCTION (r = simulated − experimental)
  rmse  √(Σr²/n)   mse  Σr²/n   mae  Σ|r|/n   see  √(Σr²/(n−k))
  wrmse √(Σw r²/Σw)  (w from the file, or w = 1/σ²)
  --fit-target xb | dxb | both;  both: J = w_x·J(x_b)/s_x + w_d·J(dx_b)/s_d,
  with s_x, s_d = the standard deviation of the experimental series.

MODEL COMPARISON
  AIC = n ln(SSE/n) + 2k      BIC = n ln(SSE/n) + k ln(n)
  They assume independent residuals; in x_b curves the residuals are
  autocorrelated (Durbin-Watson is reported), which favours larger models.
  The recommendation uses cross-validation over short contiguous blocks of θ
  interleaved between the folds (no extrapolation) and the rule: the
  smallest N whose CV error stays within 5 % of the best one and that has no
  negligible (β < 0.5 %) or coincident stages. Beforehand, each N is refined
  from the optimum of N+1 with one stage removed (nested models), which
  corrects occasional failures of the optimizer.
"""

HELP_EXAMPLES_EN = """
READY-MADE EXAMPLES
===================
(use `python main.py` instead of `wiebepy` if you did not install the package)

# Evaluate models (without data) on a grid from -20° to 100°, step 0.1°
wiebepy --stages 1 --theta-min -20 --theta-max 100 --theta-step 0.1 --plot   # single-Wiebe
wiebepy --stages 2 --save-plots --output results/double                      # double-Wiebe
wiebepy --stages 3 --plot                                                    # triple-Wiebe
wiebepy --stages 4 --save-plots --output results/four                        # 4-stage
wiebepy --stages 5 --save-plots --output results/five                        # 5-stage

# Evaluate a saved model (model.json from an earlier fit)
wiebepy --model results/fit/model.json --theta-min -30 --theta-max 120 --plot

# Experimental fit (x_b), 10 runs, charts saved
wiebepy --stages 3 --optimize --input examples/data/synthetic_3stage.csv \\
        --population 60 --iterations 500 --runs 10 --save-plots --output results/fit3

# Fit using x_b and dx_b/dθ together, with a_j fitted
wiebepy --stages 2 --optimize --input data.csv --fit-target both --fit-a

# Parallel execution on the CPU
wiebepy --stages 4 --optimize --input data.csv --runs 16 --backend numba --workers 8
        # swarm in Numba with 8 threads (runs in sequence) — the fastest on
        # the CPU in this project's measurements
wiebepy --stages 4 --optimize --input data.csv --runs 16 --backend numpy --workers 8
        # 16 runs spread over 8 processes (NumPy in each one)

# NVIDIA GPU (CuPy). It only pays off on large problems (swarm × points
# ≳ 1e6); float32 is faster still, but the search becomes less precise
wiebepy --stages 5 --optimize --input large_data.csv --gpu --population 1000

# Compare 1 to 5 stages (AIC/BIC + blocked cross-validation)
wiebepy --compare-stages 1 2 3 4 5 --input examples/data/synthetic_3stage.csv \\
        --optimize --population 100 --iterations 1000 --runs 20 \\
        --backend auto --workers 8 --save-plots

# PRESSURE curve from a test (θ in rad, P in bar): the 0-D Double Wiebe
# model with N heat-release stages; Rc fitted
wiebepy --stages 2 --optimize --input examples/data/ensaio_P_exp_carga3_45.txt \\
        --input-type pressure --pressure-unit bar --runs 5 --save-plots
wiebepy --compare-stages 1 2 3 --input test.txt --input-type pressure

# Use a configuration file (the CLI overrides the file)
wiebepy --config examples/config_example.yaml --input data.csv --optimize

# Optional CFD (requires OpenFOAM 13 on WSL2): the complete flow
wiebepy cfd doctor                                        # WSL2/OpenFOAM environment
wiebepy cfd prepare  --config examples/config_cfd.yaml    # builds the case, does not run it
wiebepy cfd validate --case results/cfd/case_001          # validates before running
wiebepy cfd run      --case results/cfd/case_001 --follow # runs with a live log
wiebepy cfd status   --case results/cfd/case_001          # state of the case
wiebepy cfd cancel   --case results/cfd/case_001          # stops the run
wiebepy cfd report   --case results/cfd/case_001          # HTML report of the case
# Preparation variants: --no-heat (motored case, no source) and
# --fixed-piston (fixed piston). The Wiebe source is checked
# energetically during preparation (∫Q̇dt = m_f·LHV·Δx_b within 0.1 %).

# Benchmark of the backends on this machine, and detected hardware
wiebepy --benchmark --workers 8 --output results/bench
wiebepy --devices
"""


# =============================================================================
# Acesso pelo idioma corrente
# =============================================================================
def descricao() -> str:
    from ..i18n import em_ingles
    return DESCRIPTION_EN if em_ingles() else DESCRIPTION


def epilogo() -> str:
    from ..i18n import em_ingles
    return EPILOG_EN if em_ingles() else EPILOG


def help_model() -> str:
    from ..i18n import em_ingles
    return HELP_MODEL_EN if em_ingles() else HELP_MODEL


def help_examples() -> str:
    from ..i18n import em_ingles
    return HELP_EXAMPLES_EN if em_ingles() else HELP_EXAMPLES
