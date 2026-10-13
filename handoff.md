# Handoff — alterações no wiebepy

Registro das alterações feitas no código, para quem continuar o trabalho.
A mais recente fica no topo.

## 2026-10-13 — README em ingles (README.en.md)

Traducao completa do README (944 linhas, ~49 KB) em `README.en.md`, com o
seletor no topo dos dois arquivos: `**Portugues** · [English](README.en.md)`
e o espelho. Nao e dicionario de i18n — e um documento, revisado como
documento, igual ao que foi feito com `--help-model`/`--help-examples`.

Quem editar o README em portugues precisa espelhar em `README.en.md`
(nao ha teste que amarre os dois; o que existe e o indice de secoes, que
e igual nos dois).

Corrigido de passagem no README em portugues: o bloco de identificabilidade
ainda dizia "avisos em ingles" e mostrava as mensagens antigas — agora os
avisos saem no idioma em uso, e os exemplos estao em portugues.

## 2026-10-13 — A CLI tambem em ingles (`--lang en`)

`cli/parser.py`, `cli/helptext.py`, `cfd/cli.py`, `crevice_flow/cli.py`,
`parallel/hardware.py`, `optimization/{fit,compare,identifiability}.py`,
`parallel/backend.py` e `pressure/fit.py`.

`wiebepy --lang en …` traduz `--help` (46 opcoes e os grupos),
`--help-model`, `--help-examples`, `--devices` e as mensagens de execucao
(cabecalho, escolha de backend, progresso do PSO, resultado, metricas,
avisos). A opcao e consumida ANTES do dispatch (`i18n.consumir_lang`), por
isso vale tambem para `wiebepy cfd …` e `wiebepy cfd crevice …`, e usa
`gravar=False`: nao mexe na preferencia que a interface grava.

Dois textos longos (`--help-model`, `--help-examples`) e a descricao/epilogo
do `--help` NAO foram para o dicionario: sao documentos, e ficam em
constantes paralelas no `cli/helptext.py` (`DESCRIPTION_EN`, `EPILOG_EN`,
`HELP_MODEL_EN`, `HELP_EXAMPLES_EN`) com os acessores `descricao()`,
`epilogo()`, `help_model()`, `help_examples()`.

O que mudou de comportamento, e merece atencao:

- a saida da CLI era MISTURADA (cabecalho e progresso em ingles, resto em
  portugues). Agora a chave e sempre o portugues: em pt a saida saiu toda
  em portugues pela primeira vez, e os avisos de identificabilidade — que
  estavam so em ingles — viraram moldes em portugues com traducao. Testes
  que fixavam o texto ingles foram atualizados (test_optimization,
  test_io_cli) e passaram a conferir os DOIS idiomas.
- moldes de alinhamento (`"%3d %4d %11.4e …"`, `"%-16s: %s"`) ficam FORA da
  traducao de proposito: nao sao texto.
- `_` como variavel descartavel apagava a funcao de traducao tambem aqui
  (backend.py, pressure/fit.py, cfd/cli.py, crevice_flow/cli.py,
  cfd/reporting.py, pressure/report.py) — renomeados.

Cuidado ao testar a GUI FORA do pytest: o seletor grava
`~/.wiebepy/gui.json`, entao uma varredura manual em ingles deixa a
preferencia do usuario em ingles (aconteceu duas vezes aqui). No pytest o
`conftest` ja isola o arquivo.

Pendencia: mensagens de erro de leitura/validacao de dados
(`core/validation.py`, `io/readers.py`, `pressure/engine.py`,
`cfd/validation.py`) seguem em portugues.

## 2026-10-13 — Os tres relatorios HTML tambem em ingles

`src/wiebepy/i18n.py` + `lang_en.py` (saidos de `gui/` para a raiz do
pacote: o CFD nao deve depender da interface) e os tres geradores de
relatorio: `pressure/html_report.py`, `cfd/reporting.py` e
`crevice_flow/report.py`, mais as figuras em `pressure/report.py`.

Como o idioma chega ao relatorio: `report_html(..., lang=None)` embrulha o
corpo em `i18n.idioma_fixo(lang)`; `lang=None` usa o idioma corrente. O
override e THREAD-LOCAL porque a GUI gera relatorio numa thread de fundo
enquanto a tela continua desenhando. E, como nessa thread nao ha sessao
Streamlit, `idioma()` passou a LEMBRAR no processo (`_lembrar`) o idioma
que a sessao resolveu — sem isso o relatorio saia em portugues com a tela
em ingles. Na CLI, `--lang pt|en` e consumido antes do dispatch, entao vale
tambem para `wiebepy cfd report` e `wiebepy cfd crevice report`.

Padrao das tabelas: `_tabela` traduz o cabecalho e a PRIMEIRA coluna
(rotulo) com traducao registrada, e as demais colunas com `ts()` (traducao
branda, que nao registra falta) porque ali ha dado do caso — caminho de
arquivo, "DOP853", nome do combustivel. Tabelas cuja 1a coluna tambem e
dado (faixas angulares, etapas, vetor de parametros) passam
`rotulos=False`. `ts` desce por dict/list, senao o valor da linha "modelo
de gas" (um dict inteiro) sairia em portugues.

Duas armadilhas resolvidas, uteis para quem continuar:

- traducao DUPLA: um rotulo ja formatado por `tf` voltava para `t()` dentro
  de `_tabela`, procurava a traducao de uma frase inglesa e a contava como
  pendente. Resolvido com `i18n.Texto` (um `str` marcado) e `rotulo()`.
- avisos cientificos: ficam GRAVADOS no case_config.yaml em portugues (sao
  proveniencia). Sao traduzidos na EXIBICAO via `ts`, com as frases no
  dicionario — vale tambem para casos antigos. O unico aviso com numeros (o
  do PCI do ensaio) e refeito no relatorio a partir dos valores gravados,
  em vez de reusar o texto. O `comparison_notice` virou molde `tf`.

Pendencias registradas: as mensagens de erro de leitura/validacao de dados
(`core/validation.py`, `io/readers.py`, `pressure/engine.py`,
`cfd/validation.py`) seguem em portugues e aparecem em ingles na GUI; e os
avisos de identificabilidade (`optimization/identifiability.py`) estao em
INGLES desde sempre, entao hoje destoam no relatorio em portugues.
`tests/test_gui_i18n.py` cobre: dicionario completo nos tres relatorios,
relatorio da GUI no idioma da tela, e PT intacto.

## 2026-10-12 — GUI bilingue (portugues/ingles)

`src/wiebepy/gui/i18n.py` (novo), `src/wiebepy/gui/lang_en.py` (novo) e todos
os arquivos da GUI. A interface inteira passou a ter idioma: seletor
**Portugues / English** no cabecalho, ao lado do botao Ajuda.

Como funciona: a chave de traducao e o PROPRIO texto em portugues (padrao
gettext), ou seja o codigo escreve `_("Fracao de massa queimada")` e
`lang_en.EN` traz a versao inglesa; texto sem entrada cai de volta para o
portugues e fica registrado em `i18n.faltantes()`. Para rotulos com valores
existe `tf("Resultado {n}-Wiebe", n=3)`, que traduz o molde antes de formatar
(a traducao pode reordenar os campos). O idioma vive em
`st.session_state["gui_lang"]`, e gravado em `~/.wiebepy/gui.json` (mesmo
padrao do `cfd_env.json`) e tambem pode vir da URL (`?lang=en`); o padrao e
portugues.

Cobertura: 456 textos distintos (548 ocorrencias, ~15 mil caracteres), em
app.py, state.py (titulos de grafico, rotulos de eixo, nomes de coluna),
as oito paginas, pressure_ui.py e cfd.py. Os NOMES DE CAMPO dos DataFrames
continuam em portugues de proposito: as strings de encode do Altair
("valor:Q") precisam casar com eles — o que se traduz e o titulo exibido.
Opcoes cujo valor e usado na logica (ex. "Arquivo"/"Exemplo sintetico",
separadores, "sim"/"nao") sao traduzidas por `format_func=_`, mantendo o
valor em portugues.

Tres armadilhas que apareceram e estao resolvidas:

- `_` como variavel descartavel (`for _, r in df.iterrows()`) APAGAVA a funcao
  de traducao do modulo. Renomeados em modelo.py, cfd.py, pressure_ui.py e
  desempenho.py; o teste `test_gui_i18n` nao cobre isso, mas um `ast` scan
  acha em segundos (procure Name id="_" em ctx Store).
- Fora de uma execucao de script o Streamlit devolve um `session_state`
  "bare" que persiste no processo; `i18n._sessao()` por isso exige o
  `ScriptRunContext` — sem isso o idioma de uma sessao vazava para outra (e
  os testes do AppTest formatavam opcoes no idioma errado).
- `col_offset` do `ast` conta BYTES utf-8: a ferramenta que embrulhou os 309
  rotulos automaticamente teve de cortar o arquivo em bytes, nao em
  caracteres, senao as linhas acentuadas saem deslocadas.

Quem for traduzir mais: `wiebepy/tests/test_gui_i18n.py` falha apontando
texto sem traducao, chave morta, campo `{...}` perdido na traducao e
`**`/crase desequilibrados; os dois ultimos testes abrem a GUI em ingles
(AppTest) e varrem as oito paginas. As mensagens do NUCLEO (134 raises e
avisos em validation.py, identificabilidade, CFD) e os 46 textos de `--help`
da CLI continuam em portugues — pendencia registrada, aparecem dentro da GUI
em ingles.

## 2026-10-12 — Help.html bilingue (Portugues/Ingles)

`Help.html`. O guia passou a conter as duas versoes no mesmo arquivo, que
continua autocontido (a exibicao no GUI usa `st.iframe` com srcdoc). O texto em
portugues ficou dentro de `<div id="doc-pt">`, sem alteracao; a traducao
completa das 15 secoes e do indice ficou em `<div id="doc-en">`, com ancoras de
sufixo `-en` para nao duplicar ids. Dois botoes no cabecalho (`.lang`) alternam
os blocos, o `<title>`, o atributo `lang` e o proprio cabecalho; a escolha vai
para `localStorage` dentro de try/catch, porque o iframe do Streamlit pode
bloquear o acesso — nesse caso o guia simplesmente abre em portugues, que e o
padrao. Quem editar o guia precisa mexer nos dois blocos.

## Planejado — CFD em Apple Silicon (macOS)

Ainda sem código; registro do plano. O CFD do wiebepy chama o OpenFOAM 13 pelo
`wsl.exe` (adapter `openfoam`, `src/wiebepy/cfd/`), o que só existe no Windows. Em
Apple Silicon (máquina M5 prevista), o OpenFOAM vai rodar numa VM Linux ARM
(OrbStack, Lima ou UTM). Será preciso um segundo caminho de execução que chame o
`foamRun` dentro da VM, escolhido pelo sistema operacional, mantendo o `doctor`,
a validação e o relatório iguais. As partes 0-D, ajuste e GUI são Python puro e
devem rodar sem mudança.

## 2026-10-10 — Relatório CFD: perda às paredes até o p_max estava em W·°CA

`src/wiebepy/cfd/reporting.py`, `_metricas_experimental`. A integral
`np.trapz(wall_loss_W, wall_loss_ca_deg)` sai em **W·°CA** e era
publicada como joule: o case_006 mostrava −278.868 J de perda acumulada
até o pico contra −35,9 J de total na janela (fator 6·rpm = 20.377 °/s).
Agora a conversão divide por ω = 6·rpm e o relatório traz também
**"conferência: integral da potência na janela"**, que reproduz o
`wall_loss_J` do solver (−35,902 J) por caminho independente. Sem rpm, o
rótulo diz W·°CA em vez de converter errado. Regressão em
`tests/test_cfd.py::test_perda_as_paredes_em_joules`; `report.html` do
case_006 regerado (−13,685 J, 38,1 % do total). Suíte: 405 passed.

## 2026-10-10 — Relatório CFD: texto de abertura fala em combustão

`src/wiebepy/cfd/reporting.py`, subtítulo do `report.html`. O texto antigo
dizia que o relatório "NÃO apresenta previsões independentes de
combustão". O novo apresenta o caso como **simulação 3D da combustão**: a
liberação de calor segue a Wiebe calibrada no ensaio, e o solver calcula
escoamento, pressão, temperaturas e troca de calor nas paredes. A
limitação continua declarada (taxa de queima da Wiebe; cinética e frente
de chama não resolvidas) e remete à seção *Modo físico e escopo*, que não
mudou. O `report.html` do case_006 foi regerado (Rc 15,624, 2-Wiebe,
RMSE 42,6 kPa). `tests/test_cfd.py`: 72 passed.

## 2026-10-10 — CFD (GUI): a carga carregada é a mesma do caso CFD

### Problema

- O `results/cfd/case_006/report.html` comparava o caso da **carga 3/45 %**
  (m_f, P1 127,6 kPa e Wiebe calibrados nela) com a medição da **carga
  5/60 %** (`data/P_exp-Carga-5_60%.txt`). O RMSE de 168 kPa daquele
  relatório mistura duas cargas e não mede o modelo. O `case_config.yaml`
  do caso aponta corretamente para a carga 3.
- **Causa 1.** O botão *Relatório HTML* dava prioridade ao ensaio
  carregado na aba Dados sobre o ensaio gravado no caso. Os dados do
  motor do relatório também vinham do formulário atual, não do caso.
- **Causa 2 (bug).** A página CFD montava o motor com
  `EngineConfig.from_dict({"engine": {...}})`, mas `from_dict` espera o
  dicionário **plano**. Toda edição de motor na página CFD (Rc, m_f, rpm,
  geometria, PCI, T1, Tw) era ignorada em silêncio, e os casos saíam com
  os padrões de `EngineConfig` (carga 3, Rc 17). Casos gerados pela CLI
  (ex. case_012, Rc 15,635) não foram afetados.
- **Causa 3.** O formulário CFD tinha a carga 3 fixa no código (P0, m_f,
  arquivo de comparação) e não acompanhava o ensaio carregado.

### O que mudou

| Arquivo | Mudança |
|---|---|
| `src/wiebepy/gui/app_pages/cfd.py` | `_sincronizar_ensaio`: o ensaio carregado define o motor, o P inicial, a T inicial e a comparação. Com o modelo 0-D ajustado, define também a Wiebe e o **Rc do mesmo ajuste**. Só sobrescreve quando o ensaio ou o modelo mudam. |
| idem | *Preparar caso* grava `ensaio_<nome>.csv` (θ rad, P kPa, cabeçalho `#` com a origem) no caso, e a comparação aponta para ele. |
| idem | *Relatório HTML* e *Resultados* usam o `engine` e a `comparison` do `case_config.yaml` do caso. Se o ensaio carregado for outro (curvas diferem > 1 %), aparece um aviso. |
| idem | `_engine_cfg(f)` passa o dicionário plano para `EngineConfig.from_dict` em `_runner`, e usa o snapshot `f` na thread em vez do `session_state`. |
| `src/wiebepy/gui/pressure_ui.py` | Ao carregar o ensaio, guarda também `pdata_full`, a série sem o corte θ mín/máx. O ensaio de exemplo cortado em ±2 rad começa em −114,5°; a janela CFD começa em −120°. |
| `src/wiebepy/gui/state.py` | Padrão `pdata_full = None`. |
| `tests/test_gui.py` | `test_cfd_segue_o_ensaio_carregado`: confere que o motor vem da sessão, que P0 = 127,6 kPa (interpolado em −120° na série completa), que a comparação vem da cópia, e que Wiebe + Rc vêm do modelo ajustado. |
| `README.md` | Passos 3, 4 e 7 da seção *Rodando um exemplo na interface gráfica*. |
| `src/wiebepy/cfd/reporting.py` | `write_exp_csv`: grava a cópia do ensaio **sem cabeçalho**. A primeira versão escrevia `theta,P`, o leitor (`_parse_table`) descartava a coluna de nome desconhecido `P`, e o relatório saía com **0 pontos** na comparação. A GUI passou a usar esta função. |
| `tests/test_cfd.py` | `test_copia_do_ensaio_no_caso_e_lida_pelo_relatorio`: grava, lê de volta por `load_exp_data` e confere os 503 pontos. |

Verificação: `python -m pytest tests -q` → **404 passed**.

**case_006**, rodado de novo pela GUI com a carga 3 e o 2-Wiebe ajustado
(Rc 15,624). A cópia `ensaio_P_exp-Carga-3_45_.csv` do caso foi regravada
no formato correto e o relatório foi regerado: **503 pontos**, p_max CFD
5554,6 kPa @ 11,44° contra 5602,3 kPa medidos, **RMSE 42,6 kPa** (0-D:
44,5 kPa).

### Pendências

- **Carga 5/60 %.** O arquivo de pressão existe (`data/`), mas **não há
  m_f nem T1 dessa carga** no repositório nem no material da dissertação
  (os notebooks e PDFs do Single/Double Wiebe só têm a carga 3). Sem m_f
  correto, a energia da fonte do CFD fica errada.
- O motor da sessão (aba Dados → *Motor*) continua com os padrões da
  carga 3. Ao carregar outra carga, confira m_f, T1 e PCI ali **antes**
  de abrir a página CFD.
