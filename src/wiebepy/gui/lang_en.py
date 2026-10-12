# -*- coding: utf-8 -*-
"""
lang_en.py — Tradução da interface para o inglês.

A chave é o texto em português exatamente como está no código (ver
``i18n.t``). Texto sem entrada aqui aparece em português; o teste
``test_gui_i18n`` lista o que falta e o que sobrou.

Os campos entre chaves ({n}, {u}, {erro}, …) têm de aparecer na tradução
com o MESMO nome — o teste confere isso. Símbolos (θ, Δθ, β, x_b, RMSE,
nomes de arquivo e de opção da CLI) não se traduzem.
"""

EN = {
    # ------------------------------------------------------------- app.py
    "Ajuda — wiebepy": "Help — wiebepy",
    "Baixar Help.html (abrir no navegador)":
        "Download Help.html (open in the browser)",
    "wiebepy — funções Wiebe de 1 a 5 estágios":
        "wiebepy — Wiebe functions with 1 to 5 stages",
    "Ajuda": "Help",
    "Versão {v}": "Version {v}",
    "Abre o guia passo a passo (Help.html)":
        "Opens the step-by-step guide (Help.html)",
    ":orange[Tarefa em andamento: {tipo}]": ":orange[Task running: {tipo}]",
    "Dados": "Data",
    "Modelo": "Model",
    "Ajuste": "Fit",
    "Comparação": "Comparison",
    "Exportar": "Export",
    "Desempenho": "Performance",
    "CFD": "CFD",
    "Combustíveis": "Fuels",
    "Help.html não encontrado (ele fica na raiz do repositório).":
        "Help.html not found (it lives in the repository root).",
    "Modo pressão · **{nome}** ({n} pontos)":
        "Pressure mode · **{nome}** ({n} points)",
    "Modo pressão · nenhuma curva carregada":
        "Pressure mode · no curve loaded",
    "Dados: **{nome}** ({n} pontos)": "Data: **{nome}** ({n} points)",
    "Dados: nenhum carregado": "Data: none loaded",
    # ------------------------------------------------- comum às páginas
    "Modo pressão: ajuste da curva de pressão do cilindro (modelo 0-D do "
    "Double Wiebe com N estágios de liberação de calor).":
        "Pressure mode: fitting of the cylinder pressure curve (the 0-D "
        "Double Wiebe model with N heat-release stages).",
    "Número de estágios": "Number of stages",
    "Série ajustada": "Fitted series",
    "x_b e dx_b/dθ": "x_b and dx_b/dθ",
    "Opções avançadas": "Advanced options",
    "Partículas": "Particles",
    "Iterações": "Iterations",
    "Paciência": "Patience",
    "Semente": "Seed",
    "Backend": "Backend",
    "Cancelar": "Cancel",
    "Decorrido: {s:.0f} s": "Elapsed: {s:.0f} s",
    "Aplicar ao modelo": "Apply to model",
    "Parâmetros aplicados à página Modelo.":
        "Parameters applied to the Model page.",
    # ------------------------------------------------------ dados.py
    "Dados experimentais": "Experimental data",
    "Tipo de dado": "Data type",
    "Arquivo .csv, .txt, .dat ou .json com θ e x_b e/ou dx_b/dθ (colunas "
    "theta, xb, dxb_dtheta; weight ou sigma opcionais). Para ajustar a "
    "curva de pressão, escolha “Pressão do cilindro”.":
        "A .csv, .txt, .dat or .json file with θ and x_b and/or dx_b/dθ "
        "(columns theta, xb, dxb_dtheta; weight or sigma optional). To fit "
        "the pressure curve, choose “Cylinder pressure”.",
    "Unidade angular dos dados": "Angle unit of the data",
    "Nenhum dado carregado. O restante da interface funciona sem dados "
    "(página Modelo), mas ajuste e comparação precisam deles.":
        "No data loaded. The rest of the interface works without data "
        "(Model page), but fitting and comparison need it.",
    "Pontos": "Points",
    "θ mín [{u}]": "θ min [{u}]",
    "θ máx [{u}]": "θ max [{u}]",
    "Séries": "Series",
    "Pesos": "Weights",
    "Tabela de dados": "Data table",
    "Arquivo de dados": "Data file",
    "Carregar arquivo": "Load file",
    "sim": "yes",
    "não": "no",
    "peso": "weight",
    "Exemplos não encontrados (ficam em examples/data no clone do "
    "repositório).":
        "Examples not found (they live in examples/data in the repository "
        "clone).",
    "Exemplo": "Example",
    "Dados gerados com parâmetros conhecidos e ruído (ver "
    "examples/data/true_parameters.json).":
        "Data generated with known parameters plus noise (see "
        "examples/data/true_parameters.json).",
    "Carregar exemplo": "Load example",
    "Não foi possível ler os dados: {erro}": "Could not read the data: {erro}",
    "graus": "degrees",
    "radianos": "radians",
    "Origem": "Source",
    "Arquivo": "File",
    "Exemplo sintético": "Synthetic example",
    "Pressão × ângulo (ensaio)": "Pressure × angle (test)",
    "Fração queimada x_b(θ)": "Burned fraction x_b(θ)",
    "Fração de massa queimada": "Mass fraction burned",
    "Taxa de queima": "Burn rate",
    # ----------------------------------------------------- modelo.py
    "Mostrar contribuição de cada estágio": "Show each stage's contribution",
    "Baixar model.json": "Download model.json",
    "**Parâmetros dos estágios**": "**Stage parameters**",
    "Grade angular": "Angle grid",
    "Grade muito fina para os gráficos; usando 200 000 pontos.":
        "Grid too fine for the charts; using 200,000 points.",
    "**Modelo atual × dados carregados**": "**Current model × loaded data**",
    "Normalizar β (Σβ = 1)": "Normalize β (Σβ = 1)",
    "Usar o último ajuste": "Use the latest fit",
    "Restaurar padrão": "Restore defaults",
    "θ mínimo [{u}]": "θ minimum [{u}]",
    "θ máximo [{u}]": "θ maximum [{u}]",
    "Passo [{u}]": "Step [{u}]",
    "θ0 [{u}]": "θ0 [{u}]",
    "Δθ [{u}]": "Δθ [{u}]",
    "série": "series",
    "fração da massa do estágio": "mass fraction of the stage",
    "início do estágio": "start of the stage",
    "duração (> 0)": "duration (> 0)",
    "fator de forma (> 0)": "shape factor (> 0)",
    "eficiência (6.908 ⇒ 99.9 %)": "efficiency (6.908 ⇒ 99.9 %)",
    # ----------------------------------------------------- ajuste.py
    "Resultado — {n}-Wiebe": "Result — {n}-Wiebe",
    "Backend: {backend}": "Backend: {backend}",
    "Carregue dados na página **Dados** para ajustar.":
        "Load data on the **Data** page to fit.",
    "Iniciar ajuste": "Start fit",
    "Ajuste cancelado: resultado parcial.": "Fit cancelled: partial result.",
    "RMSE ({serie})": "RMSE ({serie})",
    "R²": "R²",
    "Durbin-Watson": "Durbin-Watson",
    "Runs": "Runs",
    "Tempo": "Time",
    "**Parâmetros do melhor run**": "**Parameters of the best run**",
    "**Objetivo entre runs ({metrica})**":
        "**Objective across runs ({metrica})**",
    "Nenhum aviso de identificabilidade.": "No identifiability warnings.",
    "Métricas completas": "Full metrics",
    "Média e desvio dos parâmetros entre runs":
        "Mean and standard deviation of the parameters across runs",
    "Função objetivo": "Objective function",
    "Runs independentes": "Independent runs",
    "{etapa} · iteração {it} · melhor {best:.4e}":
        "{etapa} · iteration {it} · best {best:.4e}",
    "preparando (escolha do backend e compilação)…":
        "preparing (backend choice and compilation)…",
    "preparando (escolha do backend)…": "preparing (backend choice)…",
    "≈ 2: resíduo sem estrutura; ≪ 2: falta estrutura no modelo":
        "≈ 2: residual without structure; ≪ 2: structure missing from the "
        "model",
    "Avisos de identificabilidade ({n})": "Identifiability warnings ({n})",
    "Sementes seed, seed+1, …; para N ≥ 3 prefira 10 ou mais.":
        "Seeds seed, seed+1, …; for N ≥ 3 prefer 10 or more.",
    "Parametrização de β": "β parametrization",
    "Topologia do PSO": "PSO topology",
    "Ajustar a_j": "Fit a_j",
    "Refinamento local": "Local refinement",
    "Threads (numba)": "Threads (numba)",
    "Precisão": "Precision",
    "Erro no ajuste: {erro}": "Error in the fit: {erro}",
    "iterações sem melhora antes de parar":
        "iterations without improvement before stopping",
    "auto mede os disponíveis com o seu problema e usa o mais rápido":
        "auto measures the available ones on your problem and uses the "
        "fastest",
    "0 = automático": "0 = automatic",
    "float32 acelera a GPU, mas a busca fica menos precisa":
        "float32 speeds up the GPU, but the search becomes less precise",
    # -------------------------------------------------- comparacao.py
    "Comparação entre números de estágios": "Comparison across stage counts",
    "Mais estágios sempre reduzem o erro de treino. A recomendação usa o "
    "menor N cujo erro de validação cruzada fica a até 5 % do melhor e que "
    "não tem estágios desprezíveis ou coincidentes; AIC/BIC são "
    "indicativos (supõem resíduos independentes).":
        "More stages always reduce the training error. The recommendation "
        "uses the smallest N whose cross-validation error stays within 5 % "
        "of the best one and that has no negligible or coincident stages; "
        "AIC/BIC are indicative (they assume independent residuals).",
    "Modelo recomendado: **{n}-Wiebe** — {motivo}.":
        "Recommended model: **{n}-Wiebe** — {motivo}.",
    "avisos": "warnings",
    "tempo [s]": "time [s]",
    "Detalhe de um modelo": "Detail of one model",
    "Carregue dados na página **Dados** para comparar modelos.":
        "Load data on the **Data** page to compare models.",
    "Números de estágios": "Stage counts",
    "Comparar": "Compare",
    "Comparação cancelada: resultados parciais, não use a recomendação.":
        "Comparison cancelled: partial results, do not use the "
        "recommendation.",
    "Runs por N": "Runs per N",
    "Folds da validação cruzada": "Cross-validation folds",
    "Escolha ao menos dois números de estágios.":
        "Choose at least two stage counts.",
    "Usar como resultado de ajuste": "Use as the fit result",
    "0 desliga a validação cruzada (usa BIC)":
        "0 turns cross-validation off (uses BIC)",
    "Erro na comparação: {erro}": "Error in the comparison: {erro}",
    "{etapa} · iteração {it}": "{etapa} · iteration {it}",
    "Disponível na página Ajuste.": "Available on the Fit page.",
    "Avisos ({n})": "Warnings ({n})",
    "ajuste {k}-Wiebe": "fitting {k}-Wiebe",
    "validação cruzada, fold {k}/{n}": "cross-validation, fold {k}/{n}",
    "preparando…": "preparing…",
    # ---------------------------------------------------- exportar.py
    "Modelo atual (página Modelo)": "Current model (Model page)",
    "Último ajuste ({n}-Wiebe)": "Latest fit ({n}-Wiebe)",
    "Comparação (recomendado {n}-Wiebe)":
        "Comparison (recommended {n}-Wiebe)",
    "O que exportar": "What to export",
    "Incluir gráficos PNG no .zip": "Include PNG charts in the .zip",
    "Baixar só o model.json": "Download model.json only",
    "O model.json pode ser reaberto na CLI: `wiebepy --model model.json "
    "--plot`, ou em Python: `MultiStageWiebe.load('model.json')`.":
        "model.json can be reopened from the CLI: `wiebepy --model "
        "model.json --plot`, or in Python: "
        "`MultiStageWiebe.load('model.json')`.",
    "**Pacote completo**": "**Full package**",
    "Preparar .zip": "Prepare .zip",
    "Baixar resultados.zip": "Download results.zip",
    " e plots/*.png": " and plots/*.png",
    "Gerando arquivos…": "Generating files…",
    # -------------------------------------------------- desempenho.py
    "Na interface os runs rodam em sequência (com progresso e "
    "cancelamento); o paralelismo vem do backend (Numba multithread ou "
    "GPU). Runs em processos paralelos estão disponíveis na linha de "
    "comando (--backend numpy --workers N).":
        "In the interface the runs are sequential (with progress and "
        "cancellation); parallelism comes from the backend (multithreaded "
        "Numba or GPU). Runs in parallel processes are available on the "
        "command line (--backend numpy --workers N).",
    "Núcleos lógicos": "Logical cores",
    "Núcleos físicos": "Physical cores",
    "RAM": "RAM",
    "Numba": "Numba",
    "GPU": "GPU",
    "GPU: {motivo}": "GPU: {motivo}",
    "Backends disponíveis: ": "Available backends: ",
    "**Benchmark rápido** — função objetivo em lote (S candidatos × n "
    "pontos, N = 3), como em cada iteração do PSO":
        "**Quick benchmark** — batched objective function (S candidates × n "
        "points, N = 3), as in each PSO iteration",
    "Threads/processos": "Threads/processes",
    "Rodar benchmark": "Run benchmark",
    "ausente": "absent",
    "indisponível": "unavailable",
    "Medindo (inclui compilação Numba/CUDA no aquecimento)…":
        "Measuring (includes Numba/CUDA compilation in the warm-up)…",
    "tempo [ms]": "time [ms]",
    "desvio [s]": "std [s]",
    "speedup": "speedup",
    "erro rel. máx": "max rel. error",
    "speedup vs NumPy (×)": "speedup vs NumPy (×)",
    # ------------------------------------------------ combustiveis.py
    "Combustíveis — cadastro permanente": "Fuels — permanent registry",
    "Cadastre combustíveis próprios para uso no CFD (e nos campos de "
    "combustível do wiebepy). O cadastro é gravado em `{arquivo}` e "
    "permanece entre sessões. Nenhuma propriedade é inventada: o PCI (LHV) "
    "só é aceito COM a fonte declarada "
    "(ficha técnica/certificado/literatura).":
        "Register your own fuels for use in the CFD module (and in "
        "wiebepy's fuel fields). The registry is written to `{arquivo}` and "
        "persists across sessions. No property is invented: the LHV is only "
        "accepted WITH its source declared (data sheet/certificate/"
        "literature).",
    "Cadastrar": "Register",
    "Combustíveis cadastrados": "Registered fuels",
    "Exportar / ler CSV": "Export / read CSV",
    "Campos com * são obrigatórios. A composição (fórmula/surrogate) só é "
    "usada no modo reativo (não implementado); no modo prescrito o "
    "combustível entra apenas via m_f·PCI.":
        "Fields marked * are required. The composition (formula/surrogate) "
        "is only used in reactive mode (not implemented); in prescribed "
        "mode the fuel enters only through m_f·LHV.",
    "Cada embutido tem fonte do PCI declarada; observações científicas "
    "completas (ex.: CH4 puro ≠ gás natural, diesel exige surrogate) "
    "aparecem no relatório CFD.":
        "Every built-in fuel has its LHV source declared; the full "
        "scientific remarks (e.g. pure CH4 ≠ natural gas, diesel requires a "
        "surrogate) appear in the CFD report.",
    "O CSV tem as colunas completas do cadastro (name, display, formula, "
    "phase, feed, LHV_kJ_per_kg, LHV_source, stoich_AFR, "
    "molar_mass_kg_per_kmol, remarks, validity, mechanism) — serve como "
    "biblioteca portátil de combustíveis: exporte, edite no Excel e leia "
    "de volta.":
        "The CSV holds the registry's full set of columns (name, display, "
        "formula, phase, feed, LHV_kJ_per_kg, LHV_source, stoich_AFR, "
        "molar_mass_kg_per_kmol, remarks, validity, mechanism) — it works "
        "as a portable fuel library: export it, edit it in Excel and read "
        "it back.",
    "Nome (identificador) *": "Name (identifier) *",
    "Nome de exibição *": "Display name *",
    "Composição (fórmula ou surrogate) *":
        "Composition (formula or surrogate) *",
    "Fase": "Phase",
    "Alimentação assumida (modo prescrito)":
        "Assumed feed (prescribed mode)",
    "PCI (LHV) [kJ/kg] *": "LHV [kJ/kg] *",
    "A/F estequiométrica [kg/kg] *": "Stoichiometric A/F [kg/kg] *",
    "Fonte do PCI * (obrigatório)": "LHV source * (required)",
    "Massa molar [kg/kmol] *": "Molar mass [kg/kmol] *",
    "Observações científicas": "Scientific remarks",
    "Faixa de validade / limitações": "Validity range / limitations",
    "Gravar cadastro": "Save entry",
    "##### Remover cadastro": "##### Remove an entry",
    "Combustível cadastrado": "Registered fuel",
    "Remover cadastro": "Remove entry",
    "##### Exportar CSV": "##### Export CSV",
    "Arquivo de saída": "Output file",
    "Exportar todos para CSV": "Export all to CSV",
    "Baixar CSV (todos)": "Download CSV (all)",
    "##### Ler CSV (importar e gravar)": "##### Read CSV (import and save)",
    "Cada linha válida é gravada no cadastro permanente; linhas com "
    "problema são reportadas sem abortar o lote. O PCI sem fonte é "
    "rejeitado.":
        "Every valid row is written to the permanent registry; rows with a "
        "problem are reported without aborting the batch. An LHV without a "
        "source is rejected.",
    "Arquivo CSV": "CSV file",
    "Sem espaços — ex.: C3H8, E85, my_diesel":
        "No spaces — e.g. C3H8, E85, my_diesel",
    "Substância pura (ex.: CH4) ou descrição do surrogate":
        "Pure substance (e.g. CH4) or description of the surrogate",
    "No modo prescrito apenas 'premixed_gas (vaporizado)' é válida":
        "In prescribed mode only 'premixed_gas (vaporizado)' is valid",
    "Poder calorífico INFERIOR, 25 °C": "LOWER heating value, 25 °C",
    "Ex.: 'NIST WebBook', 'certificado do combustível do ensaio', "
    "referência com ano":
        "E.g. 'NIST WebBook', 'certificate of the test fuel', a reference "
        "with its year",
    "Combustível “{nome}” gravado em `{arquivo}` (permanente).":
        "Fuel “{nome}” saved to `{arquivo}` (permanent).",
    "Cadastrados: ": "Registered: ",
    "— nenhum ainda —": "— none yet —",
    "nome": "name",
    "tipo": "type",
    "exibição": "display",
    "composição": "composition",
    "fase": "phase",
    "PCI [kJ/kg]": "LHV [kJ/kg]",
    "A/F estq.": "stoich. A/F",
    "fonte do PCI": "LHV source",
    "Importar CSV": "Import CSV",
    "Embutidos: {lista} (somente leitura).":
        "Built-in: {lista} (read-only).",
    "embutido": "built-in",
    "cadastrado": "registered",
    "Cadastro “{nome}” removido.": "Entry “{nome}” removed.",
    "Não foi possível remover (embutidos não são removíveis).":
        "Could not remove it (built-in fuels cannot be removed).",
    "{n} combustíveis gravados em `{arquivo}`.":
        "{n} fuels written to `{arquivo}`.",
    "Cadastro NÃO gravado:": "Entry NOT saved:",
    "Falha ao exportar: {erro}": "Export failed: {erro}",
    "Nenhuma linha com 'name' encontrada.": "No row with 'name' found.",
    "Falha ao importar: {erro}": "Import failed: {erro}",
    "Gravados: ": "Saved: ",
    "Linhas rejeitadas:": "Rejected rows:",
    # ------------------------------------------------------- state.py
    "total": "total",
    "estágio {j}": "stage {j}",
    "Resíduos ({serie})": "Residuals ({serie})",
    "Convergência do PSO (antes do refinamento local)":
        "PSO convergence (before the local refinement)",
    "Erro × complexidade": "Error × complexity",
    "ΔAIC / ΔBIC (indicativos)": "ΔAIC / ΔBIC (indicative)",
    "estágio": "stage",
    "resíduo": "residual",
    "iteração": "iteration",
    "objetivo ({metrica})": "objective ({metrica})",
    "número de estágios": "number of stages",
    "curva": "curve",
    "valor": "value",
    "treino": "training",
    "validação cruzada": "cross-validation",
    "experimental": "experimental",
    # --------------------------------------------------------- i18n.py
    "Idioma": "Language",
    "Idioma da interface (o guia de ajuda tem o seu próprio botão)":
        "Interface language (the help guide has its own button)",
    # --------------------------------------------- nomes de tarefa (job)
    "ajuste": "fit",
    "comparação": "comparison",
    "ajuste de pressão": "pressure fit",
    "comparação de pressão": "pressure comparison",
    "preparação do caso": "case preparation",
    "validação do caso": "case validation",
    "execução CFD": "CFD run",
    "geração do relatório": "report generation",
    "preparação do caso de fresta": "crevice case preparation",
    "validação do caso de fresta": "crevice case validation",
    "execução do caso de fresta": "crevice case run",
    "relatório da fresta": "crevice report",
    # ---------------------------------- estado do caso CFD (CaseState)
    "Não configurado": "Not configured",
    "Preparado": "Prepared",
    "Validado": "Validated",
    "Executando": "Running",
    "Concluído": "Completed",
    "Cancelado": "Cancelled",
    "Falhou": "Failed",
    # ----------------------------------------------- pressure_ui.py
    "Mesma entrada do Single/Double Wiebe: arquivo .txt/.csv/.tsv com o "
    "ângulo do virabrequim (θ = 0 no PMS de combustão) e a pressão do "
    "cilindro. Convertido internamente para rad e kPa.":
        "The same input as Single/Double Wiebe: a .txt/.csv/.tsv file with "
        "the crank angle (θ = 0 at combustion TDC) and the cylinder "
        "pressure. Converted internally to rad and kPa.",
    "Arquivo de pressão": "Pressure file",
    "Separador": "Separator",
    "espaços/tab": "spaces/tab",
    "auto": "auto",
    "tab": "tab",
    ",": ",",            # símbolos de separador: iguais nos dois idiomas,
    ";": ";",            # mas precisam de entrada (passam por format_func)
    "Cabeçalho": "Header",
    "θ mín [rad]": "θ min [rad]",
    "θ máx [rad]": "θ max [rad]",
    "Coluna do ângulo (0 = primeira)": "Angle column (0 = first)",
    "Coluna da pressão": "Pressure column",
    "Carregar dados de exemplo": "Load example data",
    "Ensaio real P_exp-Carga-3_45% (θ em rad, P em bar), o mesmo do "
    "Single/Double Wiebe.":
        "Real test P_exp-Carga-3_45% (θ in rad, P in bar), the same one as "
        "Single/Double Wiebe.",
    "Sem arquivo? Use o ensaio de exemplo.":
        "No file? Use the example test.",
    "Envie um arquivo de pressão ou clique em **Carregar dados de "
    "exemplo**.":
        "Upload a pressure file or click **Load example data**.",
    "Dados ativos: **{nome}** — {n} observações.":
        "Active data: **{nome}** — {n} observations.",
    "Dados de exemplo carregados: {nome} ({n} observações).":
        "Example data loaded: {nome} ({n} observations).",
    "Observações": "Observations",
    "Descartadas (inválidas)": "Discarded (invalid)",
    "Fora do intervalo": "Outside the range",
    "P no IVC": "P at IVC",
    "P máx": "P max",
    "P no IVC = {p:.3g} kPa — muito baixa. Confira a **Unidade da "
    "pressão**.":
        "P at IVC = {p:.3g} kPa — too low. Check the **Pressure unit**.",
    "P no IVC = {p:.3g} kPa — muito alta. Confira a **Unidade da "
    "pressão**.":
        "P at IVC = {p:.3g} kPa — too high. Check the **Pressure unit**.",
    "Prévia: pressão × ângulo (após conversão e filtro)":
        "Preview: pressure × angle (after conversion and filtering)",
    "Prévia do arquivo (15 primeiras linhas)":
        "File preview (first 15 rows)",
    "Erro nos dados: {erro}": "Error in the data: {erro}",
    "arquivo vazio": "empty file",
    "coluna {i}": "column {i}",
    "são necessárias ao menos 2 colunas (ângulo e pressão); confira o "
    "separador":
        "at least 2 columns are required (angle and pressure); check the "
        "separator",
    "Motor (geometria e combustível)": "Engine (geometry and fuel)",
    "Rc (inicial/fixo)": "Rc (initial/fixed)",
    "Massa de comb. [kg/ciclo]": "Fuel mass [kg/cycle]",
    "T parede [K]": "Wall T [K]",
    "Perda de calor (Hohenberg)": "Heat loss (Hohenberg)",
    "medida": "measured",
    "simulada": "simulated",
    "Pressão: medida × simulada": "Pressure: measured × simulated",
    "Escala log-log (P–V)": "Log-log scale (P–V)",
    "Em log-log, compressão e expansão politrópicas aparecem como retas "
    "(inclinação ≈ −n).":
        "In log-log, polytropic compression and expansion show up as "
        "straight lines (slope ≈ −n).",
    "Volume [cm³]": "Volume [cm³]",
    "P modelo": "P model",
    "P medida": "P measured",
    "Diagrama P–V: modelo (linha) × experimental (+)":
        "P–V diagram: model (line) × experimental (+)",
    "P sim − P med [kPa]": "P sim − P meas [kPa]",
    "Resíduo de pressão": "Pressure residual",
    "Taxa de liberação de calor por estágio e total":
        "Heat release rate per stage and total",
    "Temperatura do gás": "Gas temperature",
    "Calor perdido para as paredes (Hohenberg)":
        "Heat lost to the walls (Hohenberg)",
    "calor perdido acumulado [J]": "cumulative heat lost [J]",
    "Calor liberado acumulado (Q_total = {q:.4f} kJ)":
        "Cumulative heat released (Q_total = {q:.4f} kJ)",
    "Volume do cilindro (Rc = {rc:.3f})": "Cylinder volume (Rc = {rc:.3f})",
    "V [cm³]": "V [cm³]",
    "T_gás": "T_gas",
    "Q_parede": "Q_wall",
    "θ0 [°]": "θ0 [°]",
    "Δθ [°]": "Δθ [°]",
    "Rc": "Rc",
    "Normalizar β": "Normalize β",
    "Carregue uma curva de pressão (página Dados) para simular.":
        "Load a pressure curve (Data page) to simulate.",
    "Carregue uma curva de pressão na página **Dados**.":
        "Load a pressure curve on the **Data** page.",
    "A simulação falhou com estes parâmetros: {erro}":
        "The simulation failed with these parameters: {erro}",
    "Ajustar Rc": "Fit Rc",
    "Como no Double Wiebe; desligado, usa o Rc do motor.":
        "As in Double Wiebe; when off, the engine's Rc is used.",
    "Sub-passos RK4": "RK4 substeps",
    "Rc mín": "Rc min",
    "Rc máx": "Rc max",
    "Δθ mín [°]": "Δθ min [°]",
    "Δθ máx [°]": "Δθ max [°]",
    "θ0₁ mín [°]": "θ0₁ min [°]",
    "θ0₁ máx [°]": "θ0₁ max [°]",
    "Runs por N": "Runs per N",
    "numba (CPU) é o mais rápido na maioria dos casos; cupy usa a GPU":
        "numba (CPU) is the fastest in most cases; cupy uses the GPU",
    "Resultado — {n}-Wiebe (pressão)": "Result — {n}-Wiebe (pressure)",
    "A referência solve_ivp falhou: resultado inválido.":
        "The solve_ivp reference failed: invalid result.",
    "RMSE [kPa]": "RMSE [kPa]",
    "P máx sim/med [kPa]": "P max sim/meas [kPa]",
    "RMSE da referência solve_ivp (DOP853). Backend da busca: {backend}. "
    "Runs: ":
        "RMSE of the solve_ivp reference (DOP853). Search backend: "
        "{backend}. Runs: ",
    "Gerar relatório HTML": "Generate HTML report",
    "Gerando relatório (gráficos incluídos)…":
        "Generating the report (charts included)…",
    "Baixar relatório HTML": "Download HTML report",
    "{etapa} · iteração {it} · melhor {best:.4f} kPa (RK4)":
        "{etapa} · iteration {it} · best {best:.4f} kPa (RK4)",
    "preparando (compilação do kernel na 1ª vez)…":
        "preparing (kernel compilation on the first run)…",
    "Erro: {erro}": "Error: {erro}",
    "validação cruzada, fold {k}": "cross-validation, fold {k}",
    "Comparação cancelada: resultados parciais.":
        "Comparison cancelled: partial results.",
    "Detalhe": "Detail",
    "Faça um ajuste ou uma comparação de pressão para exportar.":
        "Run a pressure fit or comparison to export.",
    "O .zip inclui report.html (relatório completo com todas as constantes "
    "e gráficos), CSVs, results.json e plots/*.png.":
        "The .zip includes report.html (the full report with every constant "
        "and chart), the CSVs, results.json and plots/*.png.",
    "Baixar resultados_pressao.zip": "Download pressure_results.zip",
    # ----------------------------------------------------- cfd.py
    "CFD — escoamento 3D no cilindro (opcional)":
        "CFD — 3D flow in the cylinder (optional)",
    "Casos OpenFOAM 13 (WSL2 no Windows) com liberação de calor GLOBAL "
    "prescrita pela Wiebe calibrada (modo 4.1). NÃO prevê cinética "
    "química, frente de chama ou emissões. O restante do wiebepy não "
    "depende desta página; desabilitar o CFD não apaga resultados.":
        "OpenFOAM 13 cases (WSL2 on Windows) with GLOBAL heat release "
        "prescribed by the calibrated Wiebe function (mode 4.1). It does "
        "NOT predict chemical kinetics, flame front or emissions. The rest "
        "of wiebepy does not depend on this page; disabling CFD does not "
        "erase results.",
    "Configuração do caso": "Case configuration",
    "Diretório do caso": "Case directory",
    "Diretório do caso:": "Case directory:",
    "Distribuição WSL2 (Windows)": "WSL2 distribution (Windows)",
    "Processos MPI do SOLVER": "SOLVER MPI processes",
    "Paralelismo do SOLVER (decomposePar/mpirun), distinto dos backends "
    "CPU/GPU do wiebepy.":
        "SOLVER parallelism (decomposePar/mpirun), distinct from wiebepy's "
        "CPU/GPU backends.",
    "Início [°CA]": "Start [°CA]",
    "Fim [°CA]": "End [°CA]",
    "P inicial [kPa]": "Initial P [kPa]",
    "T inicial [K]": "Initial T [K]",
    "Paredes [K]": "Walls [K]",
    "Turbulência": "Turbulence",
    "Pistão móvel": "Moving piston",
    "Células radiais": "Radial cells",
    "Células axiais": "Axial cells",
    "Distribuição da fonte": "Source distribution",
    "uniform = referência (§7); region usa potência total Q e herda uma "
    "limitação do OF13 com pistão móvel.":
        "uniform = reference (§7); region uses the total power Q and "
        "inherits an OF13 limitation with a moving piston.",
    "Combustível": "Fuel",
    "Inclui combustíveis cadastrados na aba 'Combustíveis'.":
        "Includes the fuels registered on the 'Fuels' tab.",
    "**Motor** (mesmos parâmetros dos modos 0-D)":
        "**Engine** (the same parameters as the 0-D modes)",
    "Diâmetro [mm]": "Bore [mm]",
    "Curso [mm]": "Stroke [mm]",
    "Biela [mm]": "Connecting rod [mm]",
    "Rc [-]": "Rc [-]",
    "Rotação [rpm]": "Speed [rpm]",
    "m combustível [kg/ciclo]": "Fuel mass [kg/cycle]",
    "T1 [K]": "T1 [K]",
    "**Estágios Wiebe (1–5)** — fonte do calor prescrito":
        "**Wiebe stages (1–5)** — source of the prescribed heat",
    "Modelo atual = estágios do modelo 0-D (modo pressão: parâmetros da "
    "aba Modelo), editáveis AQUI. Os parâmetros prescritos definem a "
    "liberação de calor; o CFD não recalibra o Wiebe. A edição nesta "
    "página não altera o modelo 0-D.":
        "Current model = the stages of the 0-D model (pressure mode: the "
        "parameters from the Model tab), editable HERE. The prescribed "
        "parameters set the heat release; CFD does not recalibrate the "
        "Wiebe function. Editing on this page does not change the 0-D "
        "model.",
    "Arquivo model.json": "model.json file",
    "modelo atual": "current model",     # opções do st.radio "Origem"
    "model.json": "model.json",
    "Mudar o número re-cria a tabela (estágios extras entram com padrões); "
    "use os botões abaixo para re-sincronizar com o modelo atual.":
        "Changing the count rebuilds the table (extra stages come in with "
        "defaults); use the buttons below to re-sync with the current "
        "model.",
    "Usar estágios do modelo atual": "Use the current model's stages",
    "Descarta as edições desta página e volta aos estágios do modelo 0-D "
    "atual.":
        "Discards the edits made on this page and returns to the current "
        "0-D model's stages.",
    "início do estágio [°CA]": "start of the stage [°CA]",
    "duração (> 0) [°CA]": "duration (> 0) [°CA]",
    "eficiência (6.908 ⇒ 99,9 %)": "efficiency (6.908 ⇒ 99.9 %)",
    "**Gás, numérica e comparação** (equivalência GUI↔CLI)":
        "**Gas, numerics and comparison** (GUI↔CLI equivalence)",
    "Modelo do gás": "Gas model",
    "simple = Cp/γ constantes (referência case_006); "
    "multicomponent_inert = N₂+O₂ com NASA janaf (degrau R1 do roadmap "
    "reativo; sem reação).":
        "simple = constant Cp/γ (case_006 reference); "
        "multicomponent_inert = N₂+O₂ with NASA janaf (step R1 of the "
        "reactive roadmap; no reaction).",
    "Cp do gás [J/(kg·K)]": "Gas Cp [J/(kg·K)]",
    "1063,0 ⇒ γ=1,370 (κ do 0-D; case_006). Ignorado no modo "
    "multicomponente.":
        "1063.0 ⇒ γ=1.370 (the κ of the 0-D model; case_006). Ignored in "
        "multicomponent mode.",
    "Massa molar [kg/kmol]": "Molar mass [kg/kmol]",
    "28,96 = ar seco. Ignorado no modo multicomponente (N₂+O₂ definidos "
    "pela mistura).":
        "28.96 = dry air. Ignored in multicomponent mode (N₂+O₂ are set by "
        "the mixture).",
    "Viscosidade [Pa·s]": "Viscosity [Pa·s]",
    "Ignorado no modo multicomponente (sutherland do GRI).":
        "Ignored in multicomponent mode (GRI's sutherland).",
    "Pr [-]": "Pr [-]",
    "Ignorado no modo multicomponente.": "Ignored in multicomponent mode.",
    "Δt [s]": "Δt [s]",
    "Passo de tempo do solver.": "Solver time step.",
    "max_Co [-]": "max_Co [-]",
    "0,5 ABORTOU neste motor (T negativo perto do PMS — verification.md "
    "§5b); 0,25 é o padrão seguro.":
        "0.5 ABORTED on this engine (negative T near TDC — "
        "verification.md §5b); 0.25 is the safe default.",
    "Escrita a cada [°CA]": "Write every [°CA]",
    "Intervalo entre tempos salvos (writeInterval em °CA).":
        "Interval between saved times (writeInterval in °CA).",
    "Comparação com o ensaio (diagnóstica)":
        "Comparison against the test (diagnostic)",
    "Sobreposição da pressão medida no relatório HTML. Comparação "
    "DIAGNÓSTICA — nunca validação (calibrar ≠ validar). Deixe o caminho "
    "vazio para desativar.":
        "Overlay of the measured pressure in the HTML report. A DIAGNOSTIC "
        "comparison — never validation (calibrating ≠ validating). Leave "
        "the path empty to turn it off.",
    "Arquivo do ensaio (θ,P)": "Test file (θ,P)",
    "Unidade do ângulo": "Angle unit",
    "Unidade da pressão": "Pressure unit",
    "Deslocamento [°CA]": "Offset [°CA]",
    "Offset angular aplicado ao ensaio (sincronismo do encoder).":
        "Angular offset applied to the test data (encoder synchronization).",
    "Ensaio carregado: **{nome}**. Motor, P inicial ({p:.1f} kPa, "
    "{origem}), comparação":
        "Test loaded: **{nome}**. Engine, initial P ({p:.1f} kPa, "
        "{origem}), comparison",
    " e Wiebe/Rc do modelo ajustado":
        " and the Wiebe/Rc of the fitted model",
    " (ajuste o modelo 0-D para trazer a Wiebe e o Rc)":
        " (fit the 0-D model to bring in the Wiebe function and Rc)",
    " vêm deste ensaio; o caso grava uma cópia dele.":
        " come from this test; the case stores a copy of it.",
    "interpolada no ensaio": "interpolated in the test data",
    "extrapolada de {ca:.1f}° (politrópica, κ = {k:g})":
        "extrapolated from {ca:.1f}° (polytropic, κ = {k:g})",
    "Geometria do cilindro (esquema)": "Cylinder geometry (schematic)",
    "Corte lateral com DIÂMETRO e ALTURA da câmara rotulados — valores "
    "direto do formulário. Altura instantânea h(θ) = folga + deslocamento "
    "do pistão (PMS no topo).":
        "Side section with the chamber's BORE and HEIGHT labelled — values "
        "straight from the form. Instantaneous height h(θ) = clearance + "
        "piston displacement (TDC at the top).",
    "Posição do pistão θ [°CA]": "Piston position θ [°CA]",
    "altura h(θ) = {h:.1f} mm": "height h(θ) = {h:.1f} mm",
    "diâmetro = {d:.1f} mm  |  curso = {s:.1f} mm  |  Rc = {rc:.2f}":
        "bore = {d:.1f} mm  |  stroke = {s:.1f} mm  |  Rc = {rc:.2f}",
    "diâmetro = {d:.1f} mm": "bore = {d:.1f} mm",
    "z abaixo do cabeçote [m]": "z below the cylinder head [m]",
    "h(θ = {ca:.0f}°) = {h:.2f} mm · V(θ) = π·(D/2)²·h = {v:.2f} cm³":
        "h(θ = {ca:.0f}°) = {h:.2f} mm · V(θ) = π·(D/2)²·h = {v:.2f} cm³",
    "Exportar CSV de geometria": "Export geometry CSV",
    "Baixar geometria.csv": "Download geometry.csv",
    "Exportar PNG do esquema": "Export schematic PNG",
    "Baixar esquema.png": "Download schematic.png",
    "Estado do caso": "Case state",
    "Solver": "Solver",
    "não verificado": "not checked",
    "Ação": "Action",
    "Preparar caso": "Prepare case",
    "Gera o caso OpenFOAM para inspeção (modo preparação sem execução).":
        "Builds the OpenFOAM case for inspection (preparation mode, no "
        "run).",
    "Validar": "Validate",
    "Executar": "Run",
    "Cancelar execução": "Cancel run",
    "Interrompe o solver ativo (incluindo processos MPI); logs e parciais "
    "preservados.":
        "Stops the active solver (including MPI processes); logs and "
        "partial results are preserved.",
    "Relatório HTML": "HTML report",
    "Configuração inválida: {erro}": "Invalid configuration: {erro}",
    "Caso não validado: ": "Case not validated: ",
    "Cancelamento solicitado — o executor vai interromper o solver.":
        "Cancellation requested — the runner will stop the solver.",
    "Nenhuma execução ativa neste caso.": "No active run in this case.",
    "O ensaio carregado ({carregado}) não é o deste caso; o relatório usa "
    "o ensaio gravado no caso ({do_caso}).":
        "The loaded test ({carregado}) is not this case's; the report uses "
        "the test stored in the case ({do_caso}).",
    "nenhum": "none",
    "Fresta top-land (crevice_flow — opcional)":
        "Top-land crevice (crevice_flow — optional)",
    "Módulo crevice_flow não instalado — os demais modos funcionam "
    "normalmente.":
        "The crevice_flow module is not installed — the other modes work "
        "normally.",
    "Submodelo: pressão da câmara **prescrita** (o escoamento não a "
    "modifica) e fresta comunicando **apenas** com a câmara — **não é "
    "blow-by**. Sem anéis móveis, óleo, combustão ou emissões.":
        "Submodel: the chamber pressure is **prescribed** (the flow does "
        "not modify it) and the crevice communicates **only** with the "
        "chamber — **this is not blow-by**. No moving rings, oil, "
        "combustion or emissions.",
    "Config do caso de fresta (seção crevice:)":
        "Crevice case config (crevice: section)",
    "Preparar": "Prepare",
    "Estado do caso de fresta": "Crevice case state",
    "Logs e resultados do caso de fresta":
        "Crevice case logs and results",
    "Baixar relatório HTML do caso": "Download the case's HTML report",
    "Nenhuma execução ativa no caso de fresta.":
        "No active run in the crevice case.",
    "{tipo} em andamento ({s:.0f} s)… o log do solver aparece abaixo.":
        "{tipo} running ({s:.0f} s)… the solver log appears below.",
    "Erro em {tipo}: {erro}": "Error in {tipo}: {erro}",
    "{tipo}: concluído.": "{tipo}: done.",
    "Processo do solver terminou sem erro. **Processo terminou ≠ "
    "convergiu**: verifique o fechamento de energia no relatório.":
        "The solver process finished without error. **Process finished ≠ "
        "converged**: check the energy closure in the report.",
    "Processo terminou com status “{status}”.":
        "The process finished with status “{status}”.",
    "Diagnóstico do ambiente (doctor)": "Environment diagnosis (doctor)",
    "Conectado: OpenFOAM {versao} na distro “{distro}” ({raiz})":
        "Connected: OpenFOAM {versao} on distro “{distro}” ({raiz})",
    "Nenhuma conexão gravada — detectar e conectar preenche a distro usada "
    "pelos casos.":
        "No connection stored — detecting and connecting fills in the "
        "distro the cases use.",
    "Executar diagnóstico": "Run diagnosis",
    "Conectar OpenFOAM ao código": "Connect OpenFOAM to the code",
    "Detecta a instalação, VERIFICA que o foamRun executa (probe -help), "
    "grava a conexão e ajusta a distro do formulário. Procura primeiro na "
    "distro configurada; sem instalação lá, usa a melhor de qualquer "
    "distro.":
        "Detects the installation, VERIFIES that foamRun executes (a -help "
        "probe), stores the connection and adjusts the form's distro. It "
        "looks first in the configured distro; with nothing installed "
        "there, it takes the best one from any distro.",
    "Não foi possível conectar:": "Could not connect:",
    "Instale o OpenFOAM no WSL2 seguindo docs/cfd/install.md e conecte "
    "novamente.":
        "Install OpenFOAM on WSL2 following docs/cfd/install.md and connect "
        "again.",
    "Resultados (0-D extraídos do caso 3D)":
        "Results (0-D extracted from the 3D case)",
    "Estado do caso: {estado} — resultados parciais podem estar "
    "disponíveis nos diretórios de tempo gravados.":
        "Case state: {estado} — partial results may be available in the "
        "saved time directories.",
    "Resultados ainda não legíveis: {erro}":
        "Results not readable yet: {erro}",
    "p̄ máx": "p̄ max",
    "T̄ máx": "T̄ max",
    "Trabalho indicado": "Indicated work",
    "Perda nas paredes": "Wall loss",
    "Energia prescrita pela Wiebe: {q:.1f} J (erro {erro:.1e}). Média de "
    "volume do solver (não confundir com sonda nem com pressão medida).":
        "Energy prescribed by the Wiebe function: {q:.1f} J (error "
        "{erro:.1e}). Volume average from the solver (not to be confused "
        "with a probe or with the measured pressure).",
    "Relatório completo (proveniência, balanços, limites): `{arquivo}` — "
    "gere/atualize com o botão **Relatório HTML**.":
        "Full report (provenance, balances, limits): `{arquivo}` — generate "
        "or update it with the **HTML report** button.",
}
