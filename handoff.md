# Handoff — alterações no wiebepy

Registro das alterações feitas no código, para quem continuar o trabalho.
A mais recente fica no topo.

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
