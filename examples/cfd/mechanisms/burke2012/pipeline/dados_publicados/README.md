# dados_publicados/ — pontos experimentais para o portão R2(a)

Diretório para os datasets de atraso de ignição publicados, citados na
referência do mecanismo (Burke et al. 2012, Int. J. Chem. Kinet. 44:444,
DOI 10.1002/kin.20630; preprint do laboratório Burke, ~135 p.). Regra do
projeto: **nenhum número é inventado** — cada ponto tem fonte e, quando
digitado de figura, a figura é citada com a incerteza de leitura declarada.

## Datasets identificados no paper (seção "Ignition delay times", figs. 16–18)

| Fig. | Dataset | Mistura | P | Citação |
|------|---------|---------|---|---------|
| 16 (A-16) | Pang et al. | H₂ 4 % / O₂ 2 % / Ar bal. | 3,5 atm | Pang, Davidson, Hansen, Proc. Combust. Inst. 32 (2009) 181–188 |
| 17 (A-17) | Slack 1977 (2 atm); Bhaskaran et al. 1973 (2,5 atm) | H₂ 29,6 % / O₂ 14,8 % / N₂ bal. | 2 / 2,5 atm | Slack, Combust. Flame 28 (1977) 241; Bhaskaran, Gupta, Just, Combust. Flame 21 (1973) 45 |
| 18 (A-18) | Skinner & Ringrose | H₂ 8 % / O₂ 2 % / Ar | 5 atm | J. Chem. Phys. 42 (1965) 2190 |
| 18 (A-18) | Schott & Kinsey | H₂ 1 % / O₂ 2 % (Ar bal.) | 1 atm | J. Chem. Phys. 29 (1958) 1177 |
| 18 (A-18) | Petersen et al. | H₂ 2 % / O₂ 1 % / Ar | 33/57/64/87 atm | AIAA Paper 95-3113, 31st JPC, San Diego, 1995 |

Definição do atraso por dataset (caption da fig. 18): Pang — aumento
rápido da pressão; Skinner & Ringrose — máximo de [OH]; Schott & Kinsey —
[OH] = 1×10⁻⁶ mol/L; Petersen — máximo de d[OH]/dt; Slack/Bhaskaran
(fig. 17) — aumento rápido da pressão.

**Ressalva do próprio paper** (seção 8, p. 38): atrasos de ignição em
shock tube são sensíveis a impurezas de hidrocarboneto em nível ~1 ppb
(efeito demonstrado em Hong et al.); os autores "advise modelers to
exercise caution in using ignition delay times for validation purposes".
Consequência para o portão R2a: o propósito aqui é VERIFICAÇÃO do código
(0-D do Cantera e CFD do OF13 se reproduzem mutuamente e ficam dentro do
mesmo envelope publicado), NÃO validação do mecanismo — a tolerância do
portão é declarada em verificação (típicamente dentro do mesmo envelope
que o paper mostra, ~fator 1,5–2 na banda de dados) e cada ponto carrega
a incerteza de digitação da figura.

## Protocolo de digitação

1. As páginas das figuras do apêndice (A-16..A-18) são renderizadas em
   `figs/page*.png` (pymupdf, 220 dpi) a partir do preprint do PDF.
2. Os pontos são lidos visualmente da figura publicada (cruzamentos dos
   símbolos experimentais), NÃO dos traços do modelo.
3. Cada dataset entra como um YAML `nome_dataset.yaml`:

```yaml
# exemplo de estrutura (preencher com valores lidos)
dataset: pang2009_3p5atm
fonte: >
  Pang, G. A.; Davidson, D. F.; Hansen, R. K. Proc. Combust. Inst. 32
  (2009) 181–188. Pontos digitados visualmente da Fig. A-16 do preprint
  de Burke et al. 2012 (arquivo local figs/page115.png); incerteza de
  leitura declarada ~±10 % em τ (escala log).
condicoes: {mistura: "H2 4% / O2 2% / Ar bal.", P_atm: 3.5, criterio: "aumento rápido da pressão"}
pontos:
  - {T_K: 1100.0, tau_us: 0.0, phi: 0.5}   # substituir pelos valores lidos
diluente: {AR: 47.0}   # razão diluente/O2 (Ar/O2 = 47 para Ar bal. de 4%+2%)
```

4. `verificar_0d_ignicao.py` consome apenas estes YAMLs; sem arquivo, o
   script falha com instrução explícita (nenhum dado de memória).

## Cuidado com φ e diluente

`mistura_por_phi` do script monta a composição a partir de φ e da razão
diluente/O2 publicada — os % da tabela acima já fixam ambos; conferir a
coerência (ex.: fig. 18 de Schott & Kinsey: H₂ 1 %, O₂ 2 % ⇒ φ = 0,5).