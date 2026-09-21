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

Backends (--backend)
  auto             mede os disponíveis com o tamanho real do problema e
                   escolhe o mais rápido (padrão)
  numpy            enxame vetorizado (S candidatos × n pontos), 1 núcleo
  numba            kernel compilado, --workers threads (requer numba)
  multiprocessing  enxame dividido entre --workers processos (NumPy)
  cupy             GPU NVIDIA (requer cupy-cuda12x); --gpu é atalho
  Backend indisponível ⇒ WARNING e fallback (cupy → numba → numpy).
  Runs independentes (--runs) rodam em processos paralelos nos backends
  de CPU.

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
  maiores. A recomendação usa validação cruzada por blocos contíguos de θ
  e a regra: menor N com erro de CV a até 5 % do melhor e sem estágios
  desprezíveis (β < 0.5 %) ou coincidentes.
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

# Execução paralela em CPU (runs em 8 processos; enxame em Numba)
wiebepy --stages 4 --optimize --input dados.csv --runs 16 --backend numba --workers 8

# GPU NVIDIA (CuPy); float32 é muito mais rápido em GPUs de consumo
wiebepy --stages 5 --optimize --input dados.csv --gpu --precision float32

# Comparar 1 a 5 estágios (AIC/BIC + validação cruzada por blocos)
wiebepy --compare-stages 1 2 3 4 5 --input examples/data/synthetic_3stage.csv \\
        --optimize --population 100 --iterations 1000 --runs 20 \\
        --backend auto --workers 8 --save-plots

# Usar um arquivo de configuração (CLI sobrescreve o arquivo)
wiebepy --config examples/config_example.yaml --input dados.csv --optimize

# Benchmark dos backends nesta máquina e hardware detectado
wiebepy --benchmark --workers 8 --output results/bench
wiebepy --devices
"""
