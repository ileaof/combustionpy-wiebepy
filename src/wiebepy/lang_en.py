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

    # =====================================================================
    # Relatório HTML do modo pressão (pressure/html_report.py)
    # =====================================================================
    "wiebepy — Relatório do ajuste de pressão ({n}-Wiebe)":
        "wiebepy — Pressure fit report ({n}-Wiebe)",
    "wiebepy — Relatório de pressão ({n}-Wiebe)":
        "wiebepy — Pressure report ({n}-Wiebe)",
    "Ajuste da curva de pressão do cilindro com liberação de calor Wiebe de "
    "N estágios (modelo 0-D de zona única do Double Wiebe: geometria "
    "biela-manivela, Hohenberg, EDOs em P e T<sub>g</sub>). Extensão do "
    "modelo Single Wiebe desenvolvido na dissertação de L. Queiroz, sob "
    "orientação do Prof. I. L. Ferreira.":
        "Fit of the cylinder pressure curve with N-stage Wiebe heat release "
        "(the single-zone 0-D model of Double Wiebe: slider-crank geometry, "
        "Hohenberg, ODEs in P and T<sub>g</sub>). An extension of the "
        "Single Wiebe model developed in the dissertation of L. Queiroz, "
        "supervised by Prof. I. L. Ferreira.",
    # cabeçalhos de tabela e seções
    "Item": "Item",
    "Valor": "Value",
    "Constante": "Constant",
    "Unidade": "Unit",
    "Unidade / observação": "Unit / remark",
    "Coeficiente": "Coefficient",
    "Símbolo": "Symbol",
    "Observação": "Remark",
    "Métrica": "Metric",
    "Indicador": "Indicator",
    "Resumo": "Summary",
    "Motor e constantes": "Engine and constants",
    "Modelo ajustado": "Fitted model",
    "Coeficientes do modelo": "Model coefficients",
    "Transferência de calor — correlação de Hohenberg":
        "Heat transfer — Hohenberg correlation",
    "Balanço de energia e integração": "Energy balance and integration",
    "Coeficientes Wiebe de cada estágio": "Wiebe coefficients of each stage",
    "Vetor de parâmetros ajustados (espaço de busca)":
        "Vector of fitted parameters (search space)",
    "Configuração do ajuste": "Fit configuration",
    "Métricas de ajuste (pressão)": "Fit metrics (pressure)",
    "Indicadores termodinâmicos": "Thermodynamic indicators",
    "Avisos": "Warnings",
    "Nenhum aviso.": "No warnings.",
    "Comparação entre números de estágios": "Comparison across stage counts",
    "Recomendado: {n}-Wiebe": "Recommended: {n}-Wiebe",
    "Gráficos": "Charts",
    # identificação
    "arquivo do ensaio": "test file",
    "pontos usados": "points used",
    "janela angular [°]": "angle window [°]",
    "gerado em": "generated on",
    "wiebepy": "wiebepy",
    "Rc ajustado": "fitted Rc",
    "estágios": "stages",
    "runs": "runs",
    "tempo": "time",
    # motor e constantes
    "diâmetro (bore)": "bore",
    "curso (stroke)": "stroke",
    "comprimento da biela": "connecting rod length",
    "raio da manivela r = s/2": "crank radius r = s/2",
    "razão biela/manivela R = l/r": "rod/crank ratio R = l/r",
    "cilindrada unitária Vd": "displacement per cylinder Vd",
    "razão de compressão Rc (ajustada)": "compression ratio Rc (fitted)",
    "razão de compressão Rc (fixa)": "compression ratio Rc (fixed)",
    "volume de folga Vc = Vd/(Rc−1)": "clearance volume Vc = Vd/(Rc−1)",
    "Rc inicial/nominal do motor": "initial/nominal engine Rc",
    "rotação": "speed",
    "velocidade média do pistão Vp": "mean piston speed Vp",
    "massa de combustível por ciclo": "fuel mass per cycle",
    "poder calorífico inferior (PCI)": "lower heating value (LHV)",
    "energia do combustível Q_total": "fuel energy Q_total",
    "razão de calores específicos κ": "specific heat ratio κ",
    "temperatura inicial T1": "initial temperature T1",
    "temperatura da parede Tw": "wall temperature Tw",
    "perda de calor (Hohenberg)": "heat loss (Hohenberg)",
    "pressão inicial P1 (medida)": "initial pressure P1 (measured)",
    "Hohenberg": "Hohenberg",
    # modelo ajustado
    "β [-]": "β [-]",
    "θ0 [rad]": "θ0 [rad]",
    "Δθ [rad]": "Δθ [rad]",
    "m [-]": "m [-]",
    "a [-]": "a [-]",
    "Q do estágio [kJ]": "stage Q [kJ]",
    # coeficientes de Hohenberg
    "constante de Hohenberg": "Hohenberg constant",
    "expoente do volume": "volume exponent",
    "expoente da pressão": "pressure exponent",
    "escala da pressão (kPa → bar)": "pressure scale (kPa → bar)",
    "expoente da temperatura": "temperature exponent",
    "acréscimo à velocidade do pistão": "piston-speed increment",
    "expoente da velocidade": "speed exponent",
    "fator (Vp + b)^e_Vp calculado": "computed factor (Vp + b)^e_Vp",
    "perda de calor ativa": "heat loss active",
    "V em m³": "V in m³",            # colunas de observação (ts)
    "P em bar": "P in bar",
    "T_g em K": "T_g in K",
    # balanço de energia
    "κ (razão de calores específicos)": "κ (specific heat ratio)",
    "T1 (início da integração)": "T1 (start of the integration)",
    "Tw (parede)": "Tw (wall)",
    "P1 (primeiro ponto medido)": "P1 (first measured point)",
    "conversão J → kJ no balanço": "J → kJ conversion in the balance",
    "integrador de referência": "reference integrator",
    "rtol / atol da referência": "rtol / atol of the reference",
    "integrador da busca": "search integrator",
    "limite de sanidade das derivadas": "sanity limit of the derivatives",
    "constante no ciclo": "constant over the cycle",
    "acima disso o candidato é penalizado":
        "above this the candidate is penalized",
    # coeficientes por estágio
    "coeficiente": "coefficient",
    "valor": "value",
    "unidade": "unit",
    "β (fração de energia)": "β (energy fraction)",
    "θ0 (início)": "θ0 (start)",
    "Δθ (duração)": "Δθ (duration)",
    "m (forma)": "m (shape)",
    "a (eficiência)": "a (efficiency)",
    "fração queimada ao fim de Δθ, 1 − e^(−a)":
        "burned fraction at the end of Δθ, 1 − e^(−a)",
    # vetor de parâmetros
    "parâmetro": "parameter",
    "valor ajustado": "fitted value",
    "limite inferior": "lower bound",
    "limite superior": "upper bound",
    "na borda?": "at the bound?",
    "SIM": "YES",
    "Ângulos do vetor de busca em rad. θ0_j = θ0_1 + Σ dtheta0_k; pesos por "
    "stick-breaking: β_1 = s_1, β_j = s_j·Π(1 − s_k), β_N = Π(1 − s_k).":
        "Angles in the search vector are in rad. θ0_j = θ0_1 + Σ dtheta0_k; "
        "stick-breaking weights: β_1 = s_1, β_j = s_j·Π(1 − s_k), "
        "β_N = Π(1 − s_k).",
    # configuração do ajuste
    "otimizador": "optimizer",
    "PSO ({topo}), {p} partículas × {it} iterações, paciência {pac}":
        "PSO ({topo}), {p} particles × {it} iterations, patience {pac}",
    "runs independentes / semente": "independent runs / seed",
    "refinamento local": "local refinement",
    "mínimos quadrados (TRF), {n} inícios": "least squares (TRF), {n} starts",
    "desligado": "off",
    "RK4 em lote, {n} sub-passos, backend {be}, {prec}":
        "batched RK4, {n} substeps, {be} backend, {prec}",
    "referência (RMSE relatado)": "reference (reported RMSE)",
    "solve_ivp DOP853, rtol = atol = 1e-9":
        "solve_ivp DOP853, rtol = atol = 1e-9",
    "parametrização de β": "β parametrization",
    "ajustado em [{lo}, {hi}]": "fitted within [{lo}, {hi}]",
    "fixo = {rc}": "fixed = {rc}",
    "fixo = {a}": "fixed = {a}",
    "ajustado": "fitted",
    "limites θ0₁ [°]": "θ0₁ bounds [°]",
    "incremento entre inícios [°]": "increment between starts [°]",
    "limites Δθ [°]": "Δθ bounds [°]",
    "último início θ0_N máx [°]": "last start θ0_N max [°]",
    "limites m": "m bounds",
    "a": "a",          # rótulo do coeficiente a (não se traduz)
    # métricas
    "MAE [kPa]": "MAE [kPa]",
    "MSE [kPa²]": "MSE [kPa²]",
    "SEE [kPa]": "SEE [kPa]",
    "R² [-]": "R² [-]",
    "AIC": "AIC",
    "BIC": "BIC",
    "autocorrelação lag-1": "lag-1 autocorrelation",
    "erro absoluto máximo [kPa]": "maximum absolute error [kPa]",
    "pontos": "points",
    "parâmetros livres": "free parameters",
    "SSE [kPa²]": "SSE [kPa²]",
    # indicadores termodinâmicos
    "P_max_sim [kPa]": "P_max_sim [kPa]",
    "θ(P_max) sim [°]": "θ(P_max) sim [°]",
    "P_max_exp [kPa]": "P_max_exp [kPa]",
    "θ(P_max) exp [°]": "θ(P_max) exp [°]",
    "T_max [K]": "T_max [K]",
    "θ(T_max) [°]": "θ(T_max) [°]",
    "início da combustão θ0_1 [°]": "start of combustion θ0_1 [°]",
    "CA10 [°]": "CA10 [°]",
    "CA50 [°]": "CA50 [°]",
    "CA90 [°]": "CA90 [°]",
    "duração CA10–CA90 [°]": "CA10–CA90 duration [°]",
    "Q_total = m_comb·PCI [kJ]": "Q_total = m_fuel·LHV [kJ]",
    "Q liberado até θ_final [kJ]": "Q released up to θ_final [kJ]",
    "x_b em θ_final [-]": "x_b at θ_final [-]",
    "Q perdido às paredes [kJ]": "Q lost to the walls [kJ]",
    "trabalho indicado ∮P dV, modelo [kJ]":
        "indicated work ∮P dV, model [kJ]",
    "trabalho indicado ∮P dV, ensaio [kJ]":
        "indicated work ∮P dV, test [kJ]",
    "IMEP modelo (janela) [bar]": "IMEP model (window) [bar]",
    "IMEP ensaio (janela) [bar]": "IMEP test (window) [bar]",
    # runs
    "run": "run",
    "semente": "seed",
    "RMSE solve_ivp [kPa]": "RMSE solve_ivp [kPa]",
    "RMSE RK4 [kPa]": "RMSE RK4 [kPa]",
    "iterações": "iterations",
    "parada": "stop",
    "observação": "remark",
    "RMSE entre runs: melhor {melhor:.4f} · média {media:.4f} · desvio "
    "{desvio:.4f} · mediana {mediana:.4f} · pior {pior:.4f} kPa":
        "RMSE across runs: best {melhor:.4f} · mean {media:.4f} · std "
        "{desvio:.4f} · median {mediana:.4f} · worst {pior:.4f} kPa",
    # figuras do modo pressão (pressure/report.py)
    "simulada ({n}-Wiebe)": "simulated ({n}-Wiebe)",
    "Pressão — RMSE {rmse:.2f} kPa": "Pressure — RMSE {rmse:.2f} kPa",
    "{n}-Wiebe (ajuste, RMSE {rmse:.1f} kPa)":
        "{n}-Wiebe (fit, RMSE {rmse:.1f} kPa)",
    "{k}-Wiebe (falhou)": "{k}-Wiebe (failed)",
    "refinado": "refined",
    "truncado": "truncated",
    "{k}-Wiebe ({estado}, RMSE {rmse:.1f} kPa)":
        "{k}-Wiebe ({estado}, RMSE {rmse:.1f} kPa)",
    "Pressão × ângulo — comparação entre estágios":
        "Pressure × angle — comparison across stages",
    "{n}-Wiebe (ajuste, Rc {rc:.3f})": "{n}-Wiebe (fit, Rc {rc:.3f})",
    "{k}-Wiebe ({estado}, Rc {rc:.3f})": "{k}-Wiebe ({estado}, Rc {rc:.3f})",
    "Diagrama P–V — comparação entre estágios":
        "P–V diagram — comparison across stages",
    "modelo ({n}-Wiebe, Rc {rc:.3f})": "model ({n}-Wiebe, Rc {rc:.3f})",
    "Diagrama P–V": "P–V diagram",
    "(log-log)": "(log-log)",
    "Resíduo": "Residual",
    "dQ/dθ total": "dQ/dθ total",
    "Taxa de liberação de calor [kJ/rad]": "Heat release rate [kJ/rad]",
    "Temperatura do gás [K]": "Gas temperature [K]",
    "Calor perdido acumulado [J]": "Cumulative heat lost [J]",
    # legendas das figuras
    "Pressão medida × simulada": "Pressure: measured × simulated",
    "Pressão × ângulo — comparação entre estágios (k-Wiebe refinados)":
        "Pressure × angle — comparison across stages (refined k-Wiebe)",
    "Diagrama P–V (modelo × experimental)":
        "P–V diagram (model × experimental)",
    "Diagrama P–V — comparação entre estágios (k-Wiebe refinados)":
        "P–V diagram — comparison across stages (refined k-Wiebe)",
    "Diagrama P–V em escala log-log": "P–V diagram in log-log scale",
    "Taxa de queima normalizada": "Normalized burn rate",
    "Volume do cilindro": "Cylinder volume",

    # =====================================================================
    # Relatório HTML do CFD (cfd/reporting.py)
    # =====================================================================
    "wiebepy CFD — Relatório do caso": "wiebepy CFD — Case report",
    "wiebepy CFD — Relatório do caso ({caso})":
        "wiebepy CFD — Case report ({caso})",
    "Simulação 3D da combustão em um cilindro simplificado: a liberação de "
    "calor da combustão segue a função Wiebe calibrada no ensaio (modo "
    "{modo}), e o solver calcula o escoamento, a pressão, as temperaturas e "
    "a troca de calor nas paredes. A taxa de queima é a da Wiebe; cinética "
    "química e frente de chama não são resolvidas (ver <i>Modo físico e "
    "escopo</i>).":
        "3D simulation of combustion in a simplified cylinder: the "
        "combustion heat release follows the Wiebe function calibrated "
        "against the test ({modo} mode), and the solver computes the flow, "
        "the pressure, the temperatures and the wall heat transfer. The "
        "burn rate is the Wiebe one; chemical kinetics and the flame front "
        "are not resolved (see <i>Physical mode and scope</i>).",
    # seções
    "Identificação e proveniência": "Identification and provenance",
    "Solver e adapter": "Solver and adapter",
    "Modo físico e escopo": "Physical mode and scope",
    "Combustível e propriedades": "Fuel and properties",
    "Geometria e movimento do pistão": "Geometry and piston motion",
    "Condições iniciais e de contorno": "Initial and boundary conditions",
    "Fonte Wiebe e distribuição espacial":
        "Wiebe source and spatial distribution",
    "Configuração numérica": "Numerical setup",
    "Execução e hardware": "Run and hardware",
    "Balanços e curvas": "Balances and curves",
    "Comparação experimental": "Experimental comparison",
    "Métricas p̄ CFD × p medida": "Metrics p̄ CFD × measured p",
    "RMSE por faixa angular": "RMSE by crank-angle band",
    "n_eff politrópico por faixa (ensaio × CFD)":
        "Polytropic n_eff by band (test × CFD)",
    "Avisos e limitações científicas": "Scientific warnings and limitations",
    "Campos 3D e exportação": "3D fields and export",
    # cabeçalhos de tabela
    "Grandeza": "Quantity",
    "Condição": "Condition",
    "Verificação da fonte": "Source check",
    "Faixa [° CA]": "Band [° CA]",
    "n (exp)": "n (exp)",
    "viés [kPa]": "bias [kPa]",
    "n_eff ensaio": "n_eff test",
    "n_eff CFD": "n_eff CFD",
    "etapa": "step",
    "código de saída": "exit code",
    "log": "log",
    # identificação e proveniência
    "diretório do caso": "case directory",
    "criado em": "created on",
    "relatório gerado em": "report generated on",
    "estado do caso": "case state",
    "configuração efetiva": "effective configuration",
    "case_config.yaml (salva com o caso)":
        "case_config.yaml (saved with the case)",
    # solver
    "solver": "solver",
    "versão": "version",
    "instalação": "installation",
    "foamRun": "foamRun",
    "adapter": "adapter",
    "paralelismo do solver": "solver parallelism",
    "{n} processo(s) (MPI; distinto dos backends do wiebepy)":
        "{n} process(es) (MPI; distinct from wiebepy's backends)",
    # modo físico
    "Não são previstos: cinética química, frente de chama, emissões.":
        "Not predicted: chemical kinetics, flame front, emissions.",
    "A fonte de calor é a curva Wiebe calibrada declarada abaixo (origem "
    "experimental/documental do caso).":
        "The heat source is the calibrated Wiebe curve declared below (the "
        "case's experimental/documentary origin).",
    # combustível
    "combustível": "fuel",
    "composição/formula": "composition/formula",
    "alimentação": "feed",
    "PCI (LHV) usado na fonte": "LHV used in the source",
    "PCI de referência do registro": "reference LHV from the registry",
    "fonte do PCI": "LHV source",
    "massa por ciclo": "mass per cycle",
    "energia por ciclo (m_f·PCI do ensaio)":
        "energy per cycle (m_f·LHV of the test)",
    "mecanismo químico": "chemical mechanism",
    "— (não aplicável ao modo prescrito)":
        "— (not applicable to the prescribed mode)",
    "limitações": "limitations",
    # geometria e movimento
    "diâmetro [mm]": "bore [mm]",
    "curso [mm]": "stroke [mm]",
    "biela [mm]": "connecting rod [mm]",
    "rotação [rpm]": "speed [rpm]",
    "janela simulada [° CA]": "simulated window [° CA]",
    "volume inicial [cm³]": "initial volume [cm³]",
    "volume final [cm³]": "final volume [cm³]",
    "volume mínimo [cm³]": "minimum volume [cm³]",
    "volume máximo [cm³]": "maximum volume [cm³]",
    "malha": "mesh",
    "cilindro simplificado {nr}×{nr}×{na} células (blockMesh)":
        "simplified cylinder, {nr}×{nr}×{na} cells (blockMesh)",
    "pistão móvel": "moving piston",
    "Hipótese": "Hypothesis",
    "Qualidade da malha durante o movimento: a malha deforma-se entre "
    "pistão e cabeçote (mover multiValveEngine); avalie checkMesh em cada "
    "tempo para casos sensíveis.":
        "Mesh quality during the motion: the mesh deforms between piston "
        "and head (mover multiValveEngine); run checkMesh at each time for "
        "sensitive cases.",
    # condições iniciais
    "pressão inicial [Pa]": "initial pressure [Pa]",
    "temperatura inicial [K]": "initial temperature [K]",
    "velocidade inicial": "initial velocity",
    "repouso (0, 0, 0)": "at rest (0, 0, 0)",
    "paredes": "walls",
    "turbulência": "turbulence",
    "modelo de gás": "gas model",
    # fonte Wiebe
    "energia integrada ∫Q̇dt [J]": "integrated energy ∫Q̇dt [J]",
    "energia esperada m_f·PCI·Δx_b [J]":
        "expected energy m_f·LHV·Δx_b [J]",
    "erro relativo": "relative error",
    "distribuição espacial": "spatial distribution",
    "região (cellZone)": "region (cellZone)",
    "Na malha discreta a normalização Σᵢ q\'\'\'ᵢ·Vᵢ = Q̇ é feita pelo "
    "fvModel heatSource do solver sobre os volumes atuais (correta com "
    "malha móvel e em paralelo). A energia é aplicada UMA única vez — não "
    "há sobreposição com reações químicas neste modo.":
        "On the discrete mesh the normalization Σᵢ q\'\'\'ᵢ·Vᵢ = Q̇ is done "
        "by the solver's heatSource fvModel over the current volumes "
        "(correct with a moving mesh and in parallel). The energy is "
        "applied ONCE — there is no overlap with chemical reactions in "
        "this mode.",
    # numérica
    "tempo do solver": "solver time",
    "ângulo de manivela (userTime engine)": "crank angle (userTime engine)",
    "passo inicial Δt [° CA]": "initial step Δt [° CA]",
    "passo máximo [° CA]": "maximum step [° CA]",
    "máx. Courant": "max Courant",
    "intervalo de gravação [° CA]": "write interval [° CA]",
    "esquema temporal": "time scheme",
    "Euler (implícito)": "Euler (implicit)",
    "esquemas espaciais": "spatial schemes",
    "upwind (U, h), linear (laplacianos)":
        "upwind (U, h), linear (laplacians)",
    "Tempo total: {s} s; workers (MPI): {w}. Números de recursos aqui são "
    "os efetivamente usados nesta máquina — não são estimativas.":
        "Total time: {s} s; workers (MPI): {w}. The resource figures here "
        "are the ones actually used on this machine — they are not "
        "estimates.",
    # balanços
    "trabalho indicado na janela [J]": "indicated work in the window [J]",
    "energia perdida nas paredes [J]": "energy lost to the walls [J]",
    "energia prescrita pela Wiebe [J]":
        "energy prescribed by the Wiebe function [J]",
    "massa inicial/final [kg]": "initial/final mass [kg]",
    "Sem resultados numéricos disponíveis.": "No numerical results available.",
    "Pressão média volumétrica ≠ pressão em sonda ≠ pressão medida: esta "
    "versão reporta apenas a média volumétrica do cilindro; sondas "
    "numéricas próximas ao sensor experimental são uma extensão futura.":
        "Volume-averaged pressure ≠ probe pressure ≠ measured pressure: "
        "this version reports only the cylinder's volume average; numerical "
        "probes near the experimental sensor are a future extension.",
    # comparação experimental
    "A comparação abaixo é INDICATIVA: pressão média volumétrica (CFD) vs "
    "pressão medida no sensor. A comparação é DIAGNÓSTICA, não validação do "
    "modo prescrito: a liberação de calor foi imposta a partir da "
    "calibração que já usa estes dados.":
        "The comparison below is INDICATIVE: volume-averaged pressure (CFD) "
        "vs the pressure measured at the sensor. The comparison is "
        "DIAGNOSTIC, not validation of the prescribed mode: the heat "
        "release was imposed from a calibration that already uses this "
        "data.",
    "arquivo experimental": "experimental file",
    "unidades declaradas": "declared units",
    "θ: rad, P: kPa (padrão)": "θ: rad, P: kPa (default)",
    "alinhamento de fase declarado [°CA]": "declared phase alignment [°CA]",
    "erro": "error",
    "avisos do leitor": "reader warnings",
    "As comparações abaixo estão ausentes por causa do erro acima — nenhuma "
    "substituição silenciosa foi feita.":
        "The comparisons below are missing because of the error above — no "
        "silent substitution was made.",
    "sobreposição em CA": "overlap in CA",
    "nenhum ponto experimental dentro da janela CFD — verifique o "
    "alinhamento de fase":
        "no experimental point inside the CFD window — check the phase "
        "alignment",
    "p_max CFD [kPa]": "p_max CFD [kPa]",
    "CA de p_max CFD [°]": "CA of p_max CFD [°]",
    "p_max experimental [kPa]": "p_max experimental [kPa]",
    "CA de p_max experimental [°]": "CA of p_max experimental [°]",
    "erro de p_max (CFD − exp) [kPa]": "p_max error (CFD − exp) [kPa]",
    "erro de fase de p_max [°]": "p_max phase error [°]",
    "pontos experimentais na janela CFD":
        "experimental points inside the CFD window",
    "diferença média (viés) [kPa]": "mean difference (bias) [kPa]",
    "diferença média absoluta [kPa]": "mean absolute difference [kPa]",
    "RMSE na sobreposição [kPa]": "RMSE over the overlap [kPa]",
    "perda às paredes: total na janela [J]":
        "wall loss: total in the window [J]",
    "perda às paredes acumulada até p_max ({ca:.1f}°) [J]":
        "wall loss accumulated up to p_max ({ca:.1f}°) [J]",
    "perda às paredes acumulada até p_max ({ca:.1f}°) [W·°CA] (rpm "
    "ausente: sem conversão para J)":
        "wall loss accumulated up to p_max ({ca:.1f}°) [W·°CA] (rpm "
        "missing: no conversion to J)",
    "conferência: integral da potência na janela [J]":
        "cross-check: integral of the power over the window [J]",
    "fração da perda antes do p_max [%]":
        "fraction of the loss before p_max [%]",
    "Diferenças calculadas por interpolação linear de p̄(θ) do CFD nos "
    "pontos experimentais, somente dentro da janela simulada. Pressão "
    "média volumétrica ≠ pressão medida no sensor (posicionamento do "
    "sensor, cavitação, defasagem de aquisição).":
        "Differences computed by linear interpolation of the CFD p̄(θ) at "
        "the experimental points, only inside the simulated window. "
        "Volume-averaged pressure ≠ pressure measured at the sensor "
        "(sensor placement, cavitation, acquisition lag).",
    "Comparação DIAGNÓSTICA por faixa — nenhuma calibração silenciosa; "
    "banda sem pontos experimentais aparece com n = 0.":
        "DIAGNOSTIC comparison by band — no silent calibration; a band "
        "without experimental points shows n = 0.",
    "Dip de n_eff no meio da compressão é assinatura de crevice/blow-by "
    "(gás armazenado na folga da segmentação). O CFD com Rc geométrico "
    "constante tende a NÃO reproduzir o dip — comparação diagnóstica, "
    "nunca validação.":
        "A dip of n_eff in mid-compression is the signature of "
        "crevice/blow-by (gas stored in the ring-pack clearance). CFD with "
        "a constant geometric Rc tends NOT to reproduce the dip — a "
        "diagnostic comparison, never validation.",
    "Sem métricas: as séries não se sobrepõem em ângulo de manivela.":
        "No metrics: the series do not overlap in crank angle.",
    # limitações científicas (_LIM)
    "A pressão experimental sozinha não identifica unicamente os campos "
    "3D: diferentes distribuições espaciais de calor podem reproduzir "
    "pressões médias semelhantes.":
        "The experimental pressure alone does not uniquely identify the 3D "
        "fields: different spatial heat distributions can reproduce similar "
        "mean pressures.",
    "Ajustar a pressão não valida automaticamente temperatura local, "
    "frente de chama ou emissões.":
        "Fitting the pressure does not automatically validate local "
        "temperature, flame front or emissions.",
    "Somente o intervalo de válvulas fechadas é simulado; isso exige "
    "hipóteses sobre o estado inicial da carga (repouso, P/T uniformes).":
        "Only the closed-valve interval is simulated; that requires "
        "hypotheses about the initial state of the charge (at rest, "
        "uniform P/T).",
    "Emissões não são calculadas neste modo.":
        "Emissions are not computed in this mode.",
    "Mecanismos químicos e propriedades têm faixas de validade — no modo "
    "reativo, declare-as por combustível.":
        "Chemical mechanisms and properties have validity ranges — in "
        "reactive mode, declare them per fuel.",
    # campos 3D
    "Diretórios de tempo com campos 3D (formato nativo do solver): {lista}":
        "Time directories with 3D fields (the solver's native format): "
        "{lista}",
    "Pós-processamento externo (ParaView) pode abrir os formatos nativos "
    "diretamente; a exportação VTK opcional usa foamToVTK.":
        "External post-processing (ParaView) can open the native formats "
        "directly; the optional VTK export uses foamToVTK.",
    # figuras do CFD
    "CFD (p̄ volumétrica)": "CFD (volume-averaged p̄)",
    "ângulo de manivela [°]": "crank angle [°]",
    "pressão média volumétrica [kPa]": "volume-averaged pressure [kPa]",
    "Pressão média volumétrica × ângulo":
        "Volume-averaged pressure × angle",
    "Pressão média volumétrica × ângulo de manivela":
        "Volume-averaged pressure × crank angle",
    "volume do cilindro [cm³]": "cylinder volume [cm³]",
    "pressão [kPa]": "pressure [kPa]",
    "Diagrama P–V: CFD vs experimental": "P–V diagram: CFD vs experimental",
    "Diagrama P–V (CFD vs experimental)": "P–V diagram (CFD vs experimental)",
    "fonte Wiebe prescrita": "prescribed Wiebe source",
    "perda nas paredes (solver)": "wall loss (solver)",
    "potência [kW]": "power [kW]",
    "Liberação de calor prescrita e perda de calor":
        "Prescribed heat release and heat loss",
    "Liberação de calor prescrita × perda nas paredes":
        "Prescribed heat release × wall loss",
    "T média": "mean T",
    "T máxima": "maximum T",
    "temperatura [K]": "temperature [K]",
    "Temperatura média e máxima do gás": "Mean and maximum gas temperature",
    "Temperatura média e máxima": "Mean and maximum temperature",
    "massa no cilindro [kg]": "mass in the cylinder [kg]",
    "Balanço de massa (integral volumétrica de ρ)":
        "Mass balance (volume integral of ρ)",
    "Massa no cilindro × ângulo": "Mass in the cylinder × angle",

    # =====================================================================
    # Avisos científicos do CFD (gravados no caso em português e traduzidos
    # na exibição: o case_config.yaml guarda a proveniência como foi escrita)
    # =====================================================================
    "Calor prescrito pela função Wiebe calibrada — NÃO prevê cinética "
    "química, frente de chama ou emissões.":
        "Heat prescribed by the calibrated Wiebe function — it does NOT "
        "predict chemical kinetics, flame front or emissions.",
    "Distribuição UNIFORME de calor no volume ativo (caso de referência). "
    "Isto NÃO representa a propagação da chama: diferentes distribuições "
    "espaciais podem reproduzir pressões volumétricas médias semelhantes.":
        "UNIFORM heat distribution over the active volume (reference case). "
        "This does NOT represent flame propagation: different spatial "
        "distributions can reproduce similar volume-averaged pressures.",
    "Distribuição em região especificada (cellZone). A forma da região é "
    "uma hipótese do usuário, não uma chama resolvida; não validar "
    "temperatura local ou emissões a partir dela. LIMITAÇÃO OpenFOAM 13: "
    "neste modo a fonte usa potência total Q, dividida pelo volume da zona "
    "congelado na construção do fvModel — com pistão móvel a energia "
    "injetada deixa de ser conservativa; preferir 'uniform'.":
        "Distribution over a specified region (cellZone). The shape of the "
        "region is a user hypothesis, not a resolved flame; do not validate "
        "local temperature or emissions from it. OpenFOAM 13 LIMITATION: in "
        "this mode the source uses the total power Q, divided by the zone "
        "volume frozen when the fvModel was built — with a moving piston "
        "the injected energy stops being conservative; prefer 'uniform'.",
    # geometria e movimento (hipóteses gravadas no caso)
    "Geometria simplificada de cilindro com pistão plano (sem válvulas, sem "
    "dome de câmara): representa o intervalo de válvulas fechadas de uma "
    "câmara genérica, NÃO a geometria real do ensaio.":
        "Simplified cylinder geometry with a flat piston (no valves, no "
        "chamber dome): it represents the closed-valve interval of a "
        "generic chamber, NOT the real geometry of the test engine.",
    "Somente o intervalo simulado (válvulas fechadas) é resolvido; as "
    "trocas de carga (admissão/escape) ficam fora do domínio.":
        "Only the simulated interval (valves closed) is resolved; the gas "
        "exchange (intake/exhaust) is outside the domain.",
    "Movimento inicial da carga: fluido em repouso no instante inicial, com "
    "pressão e temperatura uniformes (hipótese declarada; swirl/tumble "
    "reais do ensaio não são impostos).":
        "Initial motion of the charge: fluid at rest at the initial instant, "
        "with uniform pressure and temperature (a declared hypothesis; the "
        "real swirl/tumble of the test engine are not imposed).",
    "Ar simplificado (propriedades constantes). O κ do modelo 0-D e a "
    "correlação de Hohenberg não são transferidos para o CFD; a troca "
    "térmica nas paredes é calculada pelo solver.":
        "Simplified air (constant properties). The κ of the 0-D model and "
        "the Hohenberg correlation are not carried over to the CFD; the "
        "wall heat transfer is computed by the solver.",
    # combustível
    "O PCI usado na fonte de calor é o do combustível DO ENSAIO "
    "({usado:.1f} kJ/kg, seção engine); a referência típica do registro é "
    "{ref:.1f} kJ/kg (substituir pela ficha/certificado do combustível "
    "real). No modo prescrito o combustível entra apenas via m_f·PCI; a "
    "composição/surrogate só é relevante no modo reativo (não "
    "implementado).":
        "The LHV used in the heat source is the one of the TEST fuel "
        "({usado:.1f} kJ/kg, engine section); the registry's typical "
        "reference is {ref:.1f} kJ/kg (replace it with the data "
        "sheet/certificate of the real fuel). In prescribed mode the fuel "
        "enters only through m_f·LHV; the composition/surrogate only "
        "matters in reactive mode (not implemented).",
    "Valor usual de diesel comercial ≈ 42,6 MJ/kg (LHV); varia com a "
    "composição — substituir pelo valor do certificado do combustível do "
    "ensaio quando disponível":
        "Usual value for commercial diesel ≈ 42.6 MJ/kg (LHV); it varies "
        "with composition — replace it with the value from the test fuel's "
        "certificate when available",
    "Diesel NÃO é uma espécie química única universal: no modo reativo "
    "exige composição substituta (surrogate, ex. n-dodecano/…, conforme a "
    "literatura escolhida) e mecanismo correspondente. No modo prescrito "
    "entra apenas como PCI e m_f.":
        "Diesel is NOT a single universal chemical species: in reactive "
        "mode it requires a surrogate composition (e.g. n-dodecane/…, "
        "according to the chosen literature) and a matching mechanism. In "
        "prescribed mode it enters only as LHV and m_f.",
    "PCI típico; confirmar com a ficha do combustível real.":
        "Typical LHV; confirm it against the data sheet of the real fuel.",
    "Metano PURO: gás natural comercial tem composição variável (outros "
    "hidrocarbonetos, inertes) — não tratar gás natural como CH4 puro sem "
    "declarar a composição.":
        "PURE methane: commercial natural gas has a variable composition "
        "(other hydrocarbons, inerts) — do not treat natural gas as pure "
        "CH4 without declaring the composition.",
    "Difusividade e difusão diferencial muito acima dos hidrocarbonetos: no "
    "modo reativo, transporte e mecanismo devem tratar difusão "
    "multicomponente. Sem emissões de carbono; emissões de NOx exigem "
    "modelo e validação próprios.":
        "Diffusivity and differential diffusion far above those of "
        "hydrocarbons: in reactive mode, transport and mechanism must "
        "handle multicomponent diffusion. No carbon emissions; NOx "
        "emissions require their own model and validation.",
    "Combustível líquido: injeção direta envolveria spray, evaporação e "
    "calor latente — NÃO modelados no modo de calor prescrito. Aqui "
    "assume-se mistura pré-vaporizada (alimentação declarada como "
    "premixed_gas).":
        "Liquid fuel: direct injection would involve spray, evaporation and "
        "latent heat — NOT modelled in the prescribed-heat mode. Here a "
        "pre-vaporized mixture is assumed (feed declared as premixed_gas).",
    "Referência de PCI a 25 °C; no modo prescrito o H2 afeta apenas Q̇(t) "
    "via m_f·PCI.":
        "LHV referenced at 25 °C; in prescribed mode H2 affects only Q̇(t) "
        "through m_f·LHV.",
    "Referência de PCI a 25 °C; no modo prescrito afeta apenas Q̇(t) via "
    "m_f·PCI.":
        "LHV referenced at 25 °C; in prescribed mode it affects only Q̇(t) "
        "through m_f·LHV.",
    "Referência de PCI a 25 °C; modo prescrito afeta apenas Q̇(t) via "
    "m_f·PCI.":
        "LHV referenced at 25 °C; prescribed mode affects only Q̇(t) "
        "through m_f·LHV.",
    "Comparação entre combustíveis sob o critério declarado "
    "('{criterio}'): no modo de calor prescrito, cada combustível usa "
    "parâmetros Wiebe pré-calibrados (origem experimental declarada em "
    "cada caso). Isto NÃO é uma previsão de troca de combustível — a "
    "combustão foi prescrita por curvas calibradas, não resolvida.":
        "Comparison between fuels under the declared criterion "
        "('{criterio}'): in the prescribed-heat mode each fuel uses "
        "pre-calibrated Wiebe parameters (with the experimental origin "
        "declared in each case). This is NOT a prediction of a fuel swap — "
        "the combustion was prescribed by calibrated curves, not resolved.",

    # =====================================================================
    # Relatório HTML da fresta (crevice_flow/report.py)
    # =====================================================================
    "wiebepy crevice_flow — Fresta top-land ({caso})":
        "wiebepy crevice_flow — Top-land crevice ({caso})",
    "wiebepy crevice_flow — relatório": "wiebepy crevice_flow — report",
    "Submodelo de escoamento na fresta entre pistão, primeiro anel e "
    "cilindro. <b>NÃO é simulação de blow-by</b>: o domínio comunica APENAS "
    "com a câmara (fundo fechado no flanco acima do 1º anel). A pressão da "
    "câmara é prescrita — o escoamento calculado <b>não modifica</b> essa "
    "pressão (não é acoplamento bidirecional).":
        "Submodel of the flow in the crevice between piston, first ring and "
        "liner. <b>This is NOT a blow-by simulation</b>: the domain "
        "communicates ONLY with the chamber (closed at the flank above the "
        "first ring). The chamber pressure is prescribed — the computed "
        "flow <b>does not modify</b> that pressure (it is not two-way "
        "coupling).",
    # seções
    "Identificação e estado": "Identification and state",
    "Grandezas: simuladas, impostas, medidas":
        "Quantities: simulated, imposed, measured",
    "Geometria, malha e regime": "Geometry, mesh and regime",
    "Condições de contorno e conversões":
        "Boundary conditions and conversions",
    "Séries temporais": "Time series",
    "Balanços quantificados": "Quantified balances",
    "Exportações": "Exports",
    "Limitações e avisos": "Limitations and warnings",
    # identificação
    "nível": "level",
    "execução": "run",
    "Concluído: o solver encerrou com 'End' e a janela simulada está "
    "coberta (verificação de resultados, não apenas o fim do processo).":
        "Completed: the solver ended with 'End' and the simulated window is "
        "covered (a check of the results, not just the end of the "
        "process).",
    "Estado {estado}: este relatório pode refletir resultados PARCIAIS ou "
    "ausentes. 'Processo terminou' não implica 'simulação concluída nem "
    "convergiu'.":
        "State {estado}: this report may reflect PARTIAL or missing "
        "results. 'The process finished' does not imply 'the simulation "
        "completed, let alone converged'.",
    # classes de grandeza
    "SIMULADO": "SIMULATED",
    "IMPOSTO": "IMPOSED",
    "MEDIDO": "MEASURED",
    "Classe": "Class",
    "Origem": "Origin",
    "resolvido pelo solver": "resolved by the solver",
    "condição declarada pelo usuário/config":
        "condition declared by the user/config",
    "dado de ensaio": "test data",
    "p, T, ρ, U na fresta e no buffer":
        "p, T, ρ, U in the crevice and in the buffer",
    "vazão mássica nas aberturas (phi)": "mass flow at the openings (phi)",
    "calor trocado com as paredes": "heat exchanged with the walls",
    "p da câmara p(θ)": "chamber pressure p(θ)",
    "{fonte} — arquivo {arquivo}": "{fonte} — file {arquivo}",
    "temperatura do gás que entra": "temperature of the incoming gas",
    "inflow_T_K = {t} (a pressão sozinha não determina o estado)":
        "inflow_T_K = {t} (pressure alone does not determine the state)",
    "temperaturas das paredes": "wall temperatures",
    "seção thermal da config": "thermal section of the config",
    "propriedades do gás (R, γ, μ, Pr)": "gas properties (R, γ, μ, Pr)",
    "rotação / conversão θ↔t": "speed / θ↔t conversion",
    "dados do ensaio": "test data",
    "nenhuma grandeza medida entra neste nível":
        "no measured quantity enters at this level",
    "A comparação deste submodelo com ensaio é sempre DIAGNÓSTICA — nunca "
    "validação. Calibrar não é validar.":
        "Comparing this submodel against a test is always DIAGNOSTIC — "
        "never validation. Calibrating is not validating.",
    # geometria
    "diâmetro do cilindro [mm]": "cylinder bore [mm]",
    "folga radial da fresta [mm]": "radial crevice gap [mm]",
    "altura do top land [mm]": "top-land height [mm]",
    "altura do buffer [mm]": "buffer height [mm]",
    "ângulo do setor [°]": "sector angle [°]",
    "volume da fresta [cm³]": "crevice volume [cm³]",
    "células": "cells",
    "Δr [m]": "Δr [m]",
    "Δz [m]": "Δz [m]",
    "razão de aspecto": "aspect ratio",
    "regime": "regime",
    "Re estimado na folga": "estimated Re in the gap",
    "O modelo turbulento NÃO foi selecionado automaticamente por se tratar "
    "de um motor — a justificativa de laminar é local (Re da folga) e fica "
    "registrada; se o Re real for muito maior, declare e habilite um "
    "modelo explicitamente.":
        "The turbulence model was NOT selected automatically just because "
        "this is an engine — the laminar justification is local (the gap's "
        "Re) and is recorded; if the real Re is much larger, declare it and "
        "enable a model explicitly.",
    "Setor periódico (wedge): válido porque geometria e BCs são uniformes "
    "na circunferência. Uma abertura LOCALIZADA do anel (gap do anel) NÃO é "
    "representada neste nível.":
        "Periodic sector (wedge): valid because geometry and BCs are "
        "uniform around the circumference. A LOCALIZED ring opening (the "
        "ring gap) is NOT represented at this level.",
    # condições de contorno
    "BC de pressão na boca": "pressure BC at the mouth",
    "pico de pressão imposto [Pa]": "imposed pressure peak [Pa]",
    "janela do arquivo [° CA]": "file window [° CA]",
    "extrapolação fora da tabela": "extrapolation outside the table",
    "dθ/dt [°/s]": "dθ/dt [°/s]",
    "dθ/dt [rad/s]": "dθ/dt [rad/s]",
    "tempo do solver [s]": "solver time [s]",
    "referencial": "reference frame",
    "Convenção de sinais: ṁ > 0 = fluxo SAINDO do domínio (fresta→câmara); "
    "q̇ > 0 = gás PERDE calor para a parede. Massas acumuladas de entrada e "
    "de saída são integradas separadamente a partir do sinal de ṁ.":
        "Sign convention: ṁ > 0 = flow LEAVING the domain (crevice→"
        "chamber); q̇ > 0 = the gas LOSES heat to the wall. The accumulated "
        "inflow and outflow masses are integrated separately from the sign "
        "of ṁ.",
    "Sem séries em postProcessing — prepare e execute o caso antes de gerar "
    "o relatório definitivo.":
        "No series under postProcessing — prepare and run the case before "
        "generating the final report.",
    # figuras
    "p câmara (imposta/verificada)": "chamber p (imposed/verified)",
    "Pressão na boca da fresta": "Pressure at the crevice mouth",
    "ṁ (sinal OF)": "ṁ (OpenFOAM sign)",
    "entrada (≥0)": "inflow (≥0)",
    "saída (≥0)": "outflow (≥0)",
    "Vazão mássica na boca (ṁ>0 sai do domínio)":
        "Mass flow at the mouth (ṁ>0 leaves the domain)",
    "entrada acumulada": "accumulated inflow",
    "saída acumulada": "accumulated outflow",
    "Massas acumuladas (entrada e saída separadas)":
        "Accumulated masses (inflow and outflow separately)",
    "fresta": "crevice",
    "buffer": "buffer",
    "Massa armazenada por zona": "Mass stored per zone",
    "liner": "liner",
    "pistão": "piston",
    "q̇ [W] (gás→parede > 0)": "q̇ [W] (gas→wall > 0)",
    "Transferência de calor por parede": "Heat transfer per wall",
    "Energia interna (∫p dV/(γ−1))": "Internal energy (∫p dV/(γ−1))",
    # balanços
    "Balanço": "Balance",
    "Resíduo": "Residual",
    "Relativo": "Relative",
    "Tolerância": "Tolerance",
    "Estado": "State",
    "massa": "mass",
    "energia": "energy",
    "OK": "OK",
    "FALHOU": "FAILED",
    "Aproximações declaradas do balanço de energia: h ≈ cp·T (sem energia "
    "cinética), entalpia de entrada com T_inflow, termo viscoso de parede "
    "desprezado, volume constante no referencial do domínio (sem trabalho "
    "p·dV). A energia usa U = ∫p dV/(γ−1) (exato para gás perfeito).":
        "Declared approximations of the energy balance: h ≈ cp·T (no "
        "kinetic energy), inlet enthalpy at T_inflow, wall viscous term "
        "neglected, constant volume in the domain's frame (no p·dV work). "
        "The energy uses U = ∫p dV/(γ−1) (exact for a perfect gas).",
    # exportações
    "Arquivo": "File",
    "Conteúdo": "Content",
    "séries completas com convenção de sinais no cabeçalho":
        "complete series with the sign convention in the header",
    "tempos de campo (snapshots)": "field times (snapshots)",
    "{n} instantes: {lista}": "{n} instants: {lista}",
    "Os campos 3D (p, T, U, ρ) ficam no formato nativo do OpenFOAM nos "
    "diretórios de tempo do caso — abertos no paraFoam/paraview sem "
    "conversão.":
        "The 3D fields (p, T, U, ρ) stay in OpenFOAM's native format in the "
        "case's time directories — opened in paraFoam/paraview without "
        "conversion.",
    # limitações
    "Limitação": "Limitation",
    "Aviso (da config)": "Warning (from the config)",
    "Submodelo com câmara prescrita: o resultado NÃO retroage na pressão da "
    "câmara (não é acoplamento bidirecional).":
        "Submodel with a prescribed chamber: the result does NOT feed back "
        "into the chamber pressure (it is not two-way coupling).",
    "Não é blow-by: não há caminho de fuga para região de menor pressão — o "
    "domínio só comunica com a câmara.":
        "Not blow-by: there is no escape path to a lower-pressure region — "
        "the domain communicates only with the chamber.",
    "Sem anéis móveis, sem filme de óleo, sem combustão, sem transporte de "
    "combustível, sem emissões de HC.":
        "No moving rings, no oil film, no combustion, no fuel transport, no "
        "HC emissions.",
    "Efeitos do referencial acelerado (ω²r) negligenciados (hipótese "
    "declarada na config do caso).":
        "Accelerated-frame effects (ω²r) neglected (a hypothesis declared "
        "in the case config).",
    "Setor wedge só representa fresta anelar completa e uniforme.":
        "The wedge sector only represents a complete, uniform annular "
        "crevice.",

    # avisos e hipóteses gravados no caso de fresta (crevice_flow)
    "submodelo (fresta comunicando APENAS com a câmara — NÃO é simulação de "
    "blow-by)":
        "submodel (the crevice communicates ONLY with the chamber — this is "
        "NOT a blow-by simulation)",
    "Submodelo de fresta top-land: anelar (setor wedge), fundo fechado no "
    "flanco acima do 1º anel, boca na câmara através de um buffer de gás; "
    "pressão da câmara prescrita como condição de contorno — o escoamento "
    "calculado NÃO modifica essa pressão (não é acoplamento bidirecional).":
        "Top-land crevice submodel: annular (wedge sector), closed at the "
        "flank above the first ring, mouth opening into the chamber through "
        "a gas buffer; the chamber pressure is prescribed as a boundary "
        "condition — the computed flow does NOT modify that pressure (it is "
        "not two-way coupling).",
    "OpenFOAM Foundation 13, foamRun -solver fluid, transiente "
    "compressível, laminar, não reativo":
        "OpenFOAM Foundation 13, foamRun -solver fluid, transient "
        "compressible, laminar, non-reacting",
    "temperatura do gás que entra declarada pelo usuário — a pressão "
    "sozinha não determina o estado":
        "temperature of the incoming gas declared by the user — pressure "
        "alone does not determine the state",
    "pistão (geometria constante; malha estática)":
        "piston (constant geometry; static mesh)",
    "efeitos do referencial acelerado (ω²r) negligenciados — hipótese "
    "declarada: termo de corpo ordens de grandeza menor que os gradientes "
    "de pressão dirigindo o escoamento na fresta":
        "accelerated-frame effects (ω²r) neglected — a declared hypothesis: "
        "the body term is orders of magnitude smaller than the pressure "
        "gradients driving the flow in the crevice",
    "laminar — não selecionado automaticamente":
        "laminar — not selected automatically",
    "estimativa com pico de pressão, v≈50 m/s e escala = delta_r; "
    "justificativa impressa no relatório":
        "estimated with the pressure peak, v≈50 m/s and length scale = "
        "delta_r; the justification is printed in the report",
    "valores demo coerentes com o gás simplificado dos casos de câmara do "
    "wiebepy (R=287,07; γ=1,370; Cp=γR/(γ−1)=1063) — SINTÉTICO para o "
    "exemplo":
        "demo values consistent with the simplified gas of wiebepy's "
        "chamber cases (R=287.07; γ=1.370; Cp=γR/(γ−1)=1063) — SYNTHETIC, "
        "for the example",
    "phi do OpenFOAM: positivo = fluxo SAINDO do domínio; results.py separa "
    "entrada e saída pelo sinal":
        "OpenFOAM's phi: positive = flow LEAVING the domain; results.py "
        "separates inflow and outflow by the sign",
    "volume constante no referencial do domínio (sem trabalho p·dV); dU/dt "
    "= −∮h·φ + Q̇_paredes (trabalho viscoso da parede móvel desprezado, "
    "hipótese declarada)":
        "constant volume in the domain's frame (no p·dV work); dU/dt = "
        "−∮h·φ + Q̇_walls (the viscous work of the moving wall is "
        "neglected, a declared hypothesis)",
    "fresta isotérmica não é assumida: T é resolvida; paredes têm "
    "temperatura prescrita ou são adiabáticas (config)":
        "an isothermal crevice is not assumed: T is resolved; the walls "
        "have a prescribed temperature or are adiabatic (config)",
    "sem anéis móveis, sem filme de óleo, sem combustão, sem transporte de "
    "combustível":
        "no moving rings, no oil film, no combustion, no fuel transport",
    "setor periódico válido: geometria e BCs uniformes na circunferência "
    "(abertura localizada do anel NÃO representada)":
        "periodic sector valid: geometry and BCs uniform around the "
        "circumference (a localized ring opening is NOT represented)",
    # nomes dos termos dos balanços da fresta (exibição; o CSV mantém
    # as chaves originais)
    "massa_trocada_kg": "mass_exchanged_kg",
    "m_in_final_kg": "m_in_final_kg",
    "m_out_final_kg": "m_out_final_kg",
    "entalpia_liquida_J": "net_enthalpy_J",
    "Q_paredes_J": "Q_walls_J",
    "termo_bruto_J": "gross_term_J",
}
