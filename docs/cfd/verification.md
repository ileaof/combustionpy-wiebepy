# Relatório de verificação — módulo CFD (wiebepy)

Data: 2026-09-23 · Ambiente: Windows 11 + WSL2 Ubuntu-22.04, OpenFOAM 13
(build linux64GccDPInt32Opt, /opt/openfoam13) · Malha: cilindro
paramétrico 6144 células (16×24×16, axissimétrico circular)

## 1. Escada de verificação executada

| # | Caso | Resultado |
|---|------|-----------|
| 1 | Volume fixo, frio (V1, `results/cfd/v1_fixed_cold`) | Concluído; massa conservada; p(t) consistente com pV = mRT |
| 2 | Volume fixo + fonte Wiebe (sonda, malha fixa) | Entrega integral: T 800→2140 K, 369 J injetados |
| 3 | Pistão móvel frio | p×V segue p₀(V₀/V)^γ; massa conservada |
| 4 | Pistão móvel + fonte Wiebe (referência, `results/cfd/case_001`) | Concluído (59,6 s); **balanço de energia fecha** (seção 2) |
| 5 | Comparação 0-D (caso 4) | p̄×θ CFD dentro de ±2,7 % do 0-D com a mesma fonte e a mesma perda calculada pelo CFD (seção 3) |
| 6 | Comparação experimental | Não realizado (futuro) |

## 2. Caso de referência case_001 — balanço de energia

Motor: bore 86 mm, curso 70 mm, biela 117,5 mm, Rc 17, 3396,2 rpm,
m_f = 9,4275 µg/ciclo, PCI 39 191,3 kJ/kg (CH₄), janela −120°…+120°,
início 250 kPa / 800 K, paredes 440 K.

| Grandeza | Valor |
|----------|-------|
| Energia prescrita (m_f·PCI) | 369,5 J |
| ΔU exato (∫ρ·Cv·T dV, campos inicial/final) | +119,3 J |
| Trabalho indicado ∮p̄ dV | +206,8 J |
| Perda às paredes ∫q_wall dt | −49,8 J |
| **Fechamento (ΔU + W + perda)** | **375,9 J (+1,7 % vs prescrito)** |
| p̄ máx | 10,31 MPa @ 5,0° CA (motored adiabático: 9,97 MPa) |
| T̄ máx | 2838 K @ 18° CA (T_max celular 2960 K) |
| Massa inicial/final | 0,38413 g / 0,38413 g (conservada exatamente) |

O ΔU exato foi calculado lendo os campos p e T gravados nos diretórios
inicial/final com um functionObject `coded` (∫ρ·Cv·T·dV, ρ = p/RT por
célula): U_inicial = 220,67 J, U_final = 339,93 J.

O resíduo de +1,7 % é compatível com a razão de volumes malha-móvel vs
volume cinemático 0-D que multiplica a fonte aplicada (Σᵢ q'''ᵢ·Vᵢᵃᵗᵘᵃˡ
= Q̇·Vᵐᵉˢʰ/V₀) — verificado: V_start concorda com V₀ a 0,02 %, com
desvio maior perto do PMP onde V é pequeno. Não é perda de fonte
(bug corrigido — seção 4).

## 3. Comparação 0-D (degrau 5)

Modelo 0-D fechado com a MESMA fonte Wiebe calibrada e a MESMA perda à
parede calculada pelo CFD (não Hohenberg):

- p̄_máx: CFD 10,31 MPa vs 0-D 10,05 MPa (+2,6 %)
- T̄_máx: CFD 2838 K vs 0-D 2766 K (+2,6 %)
- Diferença p̄(θ) no intervalo [−40°, 60°]: +0,7 % a +2,7 % (média
  +1,7 %) — offset sistemático consistente com o resíduo do balanço
  (+1,7 %), não com desuniformidade espacial.
- Fechamento da própria integração 0-D: resíduo +9,2 J (2,5 % —
  trapezoidal/amostragem), confirmando que a comparação é
  autoconsistente.

## 4. Bug descoberto e corrigido (fonte de calor do OF13)

Durante a verificação do degrau 4 descobriu-se que o modo `Q` (potência
total) do fvModel `heatSource` do OpenFOAM 13 **não é conservativo com
malha móvel**: o volume da zona é capturado uma única vez na construção
do fvModel (`Function1s::Scale(Constant("1/V", 1/zone_.V()), …)` —
`heatSource.C`/`fvCellZoneI.H`), enquanto o volume real varia ~15×.

- Sintoma original: o caso com pistão móvel entregava ~15 J dos 369,5 J
  prescritos (T final 854,6 K; p̄ colada na curva motored).
- Diagnóstico (bisseção, 4 sondas em /tmp no WSL): malha fixa + tabela ⇒
  369 J entregues; malha móvel + mesma tabela ⇒ ~15 J; leitura do código
  do OF13 confirmou o mecanismo.
- **Correção**: prescrever a densidade diretamente —
  `q'''(CA) = Q̇(CA)/V₀(CA)` [W/m³] (distribuição uniforme, f = 1/V₀,
  exatamente o formalismo §7), no lugar do campo Q. Implementada em
  `case_builder.py` + `sources/wiebe_heat_release.py`
  (`table_text_density`), com verificação automática de fechamento.
- Modo `region` mantém Q (volume da zona desconhecido na geração) com a
  limitação registrada no aviso de distribuição.

## 5. Cobertura de testes automatizados

- Suíte CFD: `pytest tests/test_cfd.py` → **33 passed**
  (config/estados, fonte Wiebe N=1..5 em deg/rad, identidade
  q'''·V₀ = Q̇ ponto a ponto, tabelas Function1, geometria/cinemática,
  combustíveis com fontes citadas, case builder — incl. teste que
  garante que o caso com pistão móvel usa q''' e não Q).
- **Regressão completa com CFD off: `pytest` → 343 passed**
  (310 pré-existentes + 33 CFD; nenhuma alteração de comportamento no
  núcleo).
- GUI: página CFD renderiza (Streamlit AppTest, sem exceções) com o
  caso real concluído — estados, ações e métricas corretos.

## 6. Pendências de verificação (a fazer na entrega final)

Nenhuma — suíte completa executada (343 passed) e caso de referência
re-executado após a correção (seção 4).

## 7. Limites da verificação

- Um único caso real executado (referência); sensibilidade de malha e
  timestep não varrida — responsabilidade do usuário por enquanto.
- Sem comparação experimental (degrau 6 — futuro).
- A pressão volumétrica média não identifica os campos 3D
  (ver architecture.md §9).