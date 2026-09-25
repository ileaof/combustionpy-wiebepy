# crevice_flow — submodelo de fresta top-land (documentação)

Módulo **opcional** do wiebepy: gera, executa e analisa casos CFD do
escoamento compressível transiente na fresta entre pistão, primeiro anel
e cilindro. **Nenhum arquivo do wiebepy existente é alterado pelos casos
de fresta** — os modelos single/double/multi Wiebe (0-D) e os casos de
câmara seguem intocados; sem `crevice:` na config, o programa inteiro se
comporta exatamente como antes.

## 1. Delimitação (o que este nível É e NÃO É)

| É | NÃO É |
|---|---|
| Fresta top-land localizada: folga radial pistão–liner + buffer de gás da câmara | Simulação de blow-by — o domínio comunica **apenas** com a câmara (fundo fechado no flanco acima do 1º anel); caminho de vazamento para região de menor pressão é fase futura |
| Preenchimento e ventagem da fresta ao longo do ciclo | Anéis móveis, filme de óleo, combustão, transporte de combustível, emissões de HC |
| Câmara prescrita: p(θ) imposta como BC | Acoplamento bidirecional — o escoamento calculado **não modifica** a pressão imposta |
| Setor periódico (wedge) anelar completo | Abertura localizada do anel (gap do segmento) — geometria/BCs não são uniformes na circunferência |

Nível 2 (planejado, não implementado): domínio integrado câmara–fresta.

## 2. Arquitetura

```
src/wiebepy/crevice_flow/
  config.py      config com unidades explícitas + validação (erro duro,
                 nunca silencioso) + leitura da tabela p(θ)
  geometry.py    domínio anelar, blockMeshDict (convenção de vértices
                 verificada), topoSet (zonas crevice/buffer), cinemática
  case.py        caso OpenFOAM 13 completo: campos 0/, constant/,
                 system/ (controlDict + 9 functionObjects, fvSchemes,
                 fvSolution), case_config.yaml de proveniência
  runner.py      prepare/validate/run/cancel reutilizando RunLock,
                 CaseState e adapter do wiebepy.cfd; "processo terminou"
                 ≠ "concluído" (check_completion próprio)
  validation.py  validação estrutural (sem fvModels/química — fonte de
                 calor prescrita e reativa nunca coexistem aqui)
  results.py     séries + balanços de massa e energia com convenção de
                 sinais declarada
  report.py      relatório HTML autônomo (simulado/imposto/medido)
  cli.py         wiebepy cfd crevice doctor|prepare|validate|run|status|
                 cancel|report
```

## 3. Condições de contorno (§5 do requisito)

- **totalPressure** (padrão): `uniformTotalPressure` com `p0` como
  Function1 tabela de tempo; `psi` ativo com γ do gás.
- **staticPressure**: `uniformFixedValue` com `uniformValue` tabela.
- **U na boca**: `pressureInletOutletVelocity` (suporta inversão de
  fluxo); **T na boca**: `inletOutlet` com `inletValue = inflow_T_K`.
- O gás que ENTRA precisa de estado explícito: **a pressão sozinha não
  determina o estado** — `inflow_T_K` é obrigatório e aparece como
  hipótese no `case_config.yaml` e no relatório.
- Sem extrapolação da tabela fora da janela (padrão `false`; erro duro
  se a janela não for coberta).
- Paredes: temperaturas distintas prescritas (pistão/liner) ou
  `adiabatic`; liner com velocidade axial (Couette) no referencial do
  pistão — hipótese de referencial acelerado negligenciado declarada.

## 4. Conversões dθ/dt (§6 — testadas em `tests/test_crevice_flow.py`)

- dθ/dt = **6·RPM** [°/s] e **2π·RPM/60** [rad/s] — propriedades da
  config, nunca re-derivadas dos dados.
- O tempo do SOLVER inicia em 0 no início da janela:
  `t(θ) = (θ − θ0)/(6·RPM)` (tabelas Function1 não aceitam t<0).

## 5. Malha e numeria (§8)

- Refinamento controlado na folga (`n_gap ≥ 3`), relatório informa
  contagem de células, Δr, Δz e razão de aspecto (exemplo: 108 células,
  aspecto ≈ 5,3, não-ortogonalidade 0 no checkMesh).
- Δt adaptativo com `maxCo` e teto `max_delta_t_s` — no exemplo,
  CFL acústico na folga (a·Δt/Δr ≈ 1 → Δt ~1e-7 s) justifica o teto.
- Estudos de sensibilidade de malha/Δt: **uma execução nunca estabelece
  independência** — o relatório registra apenas o que foi medido.

## 6. Resultados exportados (§10)

`results_series.csv` (convenção de sinais no cabeçalho) + campos 3D no
formato nativo OpenFOAM (p, T, U, ρ por tempo gravado):

- p e T na fresta (boca, área-média) vs ângulo;
- massa armazenada total e por zona (fresta/buffer);
- vazão mássica assinada na boca (ṁ > 0 = **sai** do domínio);
- massas acumuladas de entrada e de saída **separadamente**;
- transferência de calor por parede (q̇ > 0 = **gás perde** calor);
- energia interna U = ∫p dV/(γ−1) (exato para gás perfeito);
- **balanços**: massa (tol 0,5 %) e energia (tol 2 %) com números no
  relatório — nunca silenciosos.

## 7. Verificação progressiva (escada N1–N9)

| Nível | Teste | Evidência |
|---|---|---|
| N1 | validação da config + conversões dθ/dt | `tests/test_crevice_flow.py` (automatizado) |
| N1b | geometria: convenção blockMesh, volumes, regras | idem (bug "inside-out" fixado) |
| N2 | conservação de massa em cavidade fechada (ṁ=0) | sintético automatizado + caso real |
| N3 | equilíbrio sem fluxo | coberto por N2 (p interna = BC) |
| N5 | enchimento/ventagem com inversão (sinais separados) | sintético automatizado + caso real |
| N6 | balanço de energia com troca de calor | **caso real**: massa 0,019 %, energia 0,61 % (mini-janela 2e-5 s); **janela completa (caso fino, §7b)**: massa 0,0007 % (ok), energia 2,42 % (residual = aproximação declarada h_out = T_camara) |
| N7 | sensibilidade de amostragem do fluxo | **evidência real (§7b)**: resíduo de massa 2,13e-9 kg a 1° vs 1,0e-13 kg a 2e-6 s na mesma janela — aliasing do transiente acústico; FOs fixados em 20 passos no gerador |
| N7 | sensibilidade de malha/Δt | procedimento documentado (§5); não reivindicado |
| N8 | serial vs MPI | `--workers N` disponível; comparação a registrar |
| N9 | não-interferência no wiebepy | 382 testes existentes + teste de identidade automatizado |

Mocks não substituem o caso real: o caso demo
`examples/crevice/crevice_exemplo.yaml` é **executado no OpenFOAM 13
real** (foamRun, solver `fluid`, laminar, heRhoThermo/perfectGas).

## 7b. Janela completa (caso real de 360°, 2026-09-25)

Dois casos reais executados até o fim (foamRun rc=0, 'End' no log,
janela 0→0,04 s = 360° a 1500 rpm, serial, /mnt/c):

| Caso | Amostragem dos FOs | Balanço de massa | Balanço de energia |
|---|---|---|---|
| `results/crevice_exemplo` (demo, 1°) | a 1° (writeTime) | resíduo 3,04e-9 kg = **0,88 %** da massa trocada (3,44e-7 kg) — FALHA (tol 0,5 %) | **4,01 %** dos termos brutos (0,264 J) — FALHA (tol 2 %) |
| `results/crevice_exemplo_fino` (final) | a 20 passos (~2e-6 s) | 2,5e-12 kg = **0,0007 %** — OK | **2,42 %** — FALHA marginal (tol 2 %) |

**Diagnóstico do resíduo de massa (probe `results/_crevice_probe_ams`)**
— mesma janela [0, 0,002 s], mesma malha/solver, só a amostragem muda:
resíduo **2,13e-9 kg a 1°** vs **1,0e-13 kg a 2e-6 s** (≈ exato). O ṁ
real oscila até |ṁ| = 2,1e-5 kg/s DENTRO de um único intervalo de 1°
(ringing acústico da folga, Δt ≈ 1e-7 s); a amostra de 1° cai perto do
cruzamento por zero (−3,4e-8 no 1º intervalo). O gerador passou a
gravar os FOs a cada 20 passos (`writeControl timeStep`); campos 3D
continuam a 1°. Correção de escala em `balanco_massa`/`balanco_energia`:
a referência agora é a massa/termos trocados, não m₀ nem o resíduo
líquido (troca de 46× m₀ fazia o resíduo parecer 82 %).

**Residual de energia (2,42 %, acima da tol)**: causa declarada, não
numérica — `h_out = cp·T_camara` usa a temperatura PRESCRITA da câmara
enquanto o gás que sai carrega a temperatura da fresta (junto às
paredes), e `h_in` usa o `inflow_T_K` fixo da BC `inletOutlet`. Com a
troca de massa gigante (1,7e-7 kg, 46× m₀), o erro dessa aproximação
supera a tolerância. Caminho declarado para fechar: FO adicional
`volAverage(T)` na célula-zone da fresta e `h_out` medido (fica para o
nível 2). Relatórios de ambos os casos: `report.html` em cada diretório
(o do demo mostra as FALHAS com a nova escala — nunca silencioso).

**Bug corrigido durante a fase**: `check_completion` usava
`glob("*.dat")` e não via as subpastas por startTime que o RESTART do
OF13 cria (`postProcessing/<startTime>/*.dat`) — marcava caso completo
como FAILED ("Sem série temporal"); corrigido para `glob("*/*.dat")`
com teste de regressão.

## 8. Como reproduzir o caso demo

```bash
# 1. gerar a pressão SINTÉTICA de demo (motored politrópica; NÃO é ensaio)
cd examples/crevice
python gera_pressao_sintetica.py pressao_sintetica.csv 1500 55

# 2. preparar e validar
python -m wiebepy.cfd.cli crevice prepare \
    --config examples/crevice/crevice_exemplo.yaml \
    --output results/crevice_exemplo
python -m wiebepy.cfd.cli crevice validate \
    --case results/crevice_exemplo

# 3. executar (WSL2 + OpenFOAM Foundation 13; serial)
python -m wiebepy.cfd.cli crevice run --case results/crevice_exemplo --follow

# 4. relatório HTML autônomo
python -m wiebepy.cfd.cli crevice report --case results/crevice_exemplo
```

Tempo esperado: ~80 min serial em /mnt/c (WSL) para a janela completa
de 360° a 1500 rpm (~4e5 passos de Δt ≤ 1e-7 s; filesystem nativo do
WSL reduz o custo de I/O — o wall-clock foi ~7× o CPU nos testes).
Paralelo: `--workers N` (decomposePar + mpirun + reconstructPar).

## 9. Limitações declaradas (repetidas no relatório)

1. Câmara prescrita — resultado não retroage na pressão.
2. Não é blow-by (sem caminho de fuga).
3. Sem anéis móveis, óleo, combustão, transporte de combustível, HC.
4. Efeitos do referencial acelerado (ω²r) negligenciados.
5. Setor wedge válido somente para fresta anelar uniforme.
6. Turbulência: `laminar` justificado localmente pelo Re da folga
   (estimativa impressa no relatório); nunca auto-selecionado.
7. Entalpia das fronteiras aproximada por `h ≈ cp·T`: `h_out` usa a
   T_camara prescrita (não a T da fresta) e `h_in` o `inflow_T_K` fixo
   da BC — na janela completa com troca de massa 46× m₀, o residual do
   balanço de energia fica em ~2,4 % dos termos brutos (§7b).
8. Amostragem dos functionObjects: a 1° o balanço de massa não fecha
   (aliasing do ringing acústico, resíduo 0,88 % da massa trocada); o
   gerador agora grava a cada 20 passos (~2e-6 s) e fecha a 0,0007 %
   (§7b). Casos antigos com FOs a 1° devem ser reavaliados com essa
   limitação em mente.

## 10. Dados necessários para um caso REAL (não demo)

- p(θ) da câmara real (ensaio, 0-D ou CFD anterior) cobrindo a janela;
- estado do gás que entra: **T de entrada** (e origem/proveniência);
- dimensões reais: diâmetro, folga radial (top land), altura do top
  land, RPM, curso e biela (para a velocidade do liner);
- temperaturas de parede por componente (ou `adiabatic`);
- propriedades do gás com proveniência (R, γ, μ, Pr).

Valores demo existem APENAS nos arquivos de `examples/crevice/`,
identificados como sintéticos no arquivo e no relatório.