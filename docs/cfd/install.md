# Instalação do módulo CFD (opcional) — Windows (WSL2) e Linux

O módulo CFD é **opcional e independente**: sem ele (e sem as etapas
abaixo), o wiebepy inteiro funciona — ajuste, comparação, GUI, CLI,
relatórios. O CFD só é exigido pelos comandos `wiebepy cfd …` e pela
página CFD da GUI.

O **solver não é instalado pelo pip**: `pip install -e ".[cfd]"` instala
apenas dependências Python já presentes no projeto (PyYAML). O OpenFOAM
vem da instalação oficial, conforme a seção abaixo.

## 1. Python

    pip install -e .            # base (CFD desabilitado por padrão)
    pip install -e ".[cfd]"     # marca o extra CFD (não instala solver)
    pip install -e ".[gui]"     # se for usar a GUI

`cfd.enabled: false` (padrão) em qualquer configuração: nenhum import
nem subprocesso CFD acontece.

## 2. OpenFOAM 13

Documentação oficial da versão: <https://openfoam.org/version/13/>
(e <https://openfoam.org/download/>).

### 2a. Windows 11 — WSL2 (caminho recomendado)

1. Instale o WSL2 com Ubuntu 22.04 (PowerShell como administrador):

       wsl --install -d Ubuntu-22.04

2. Dentro do Ubuntu, siga o guia oficial do OpenFOAM 13 para Ubuntu:

       sudo sh -c "wget -O - https://dl.openfoam.org/gpg.key | apt-key add -"
       sudo add-apt-repository http://dl.openfoam.org/ubuntu
       sudo apt update && sudo apt install openfoam13

3. Verificação (de fora do WSL):

       wiebepy cfd doctor

   O diagnóstico lista as distribuições WSL2 e, para cada uma, se o
   OpenFOAM foi encontrado e a versão.

Notas:

- A execução lê/escreve o caso direto no diretório do projeto via
  `/mnt/c/...` — não é preciso copiar casos.
- Casos no Windows usam `wsl.exe -d <distro>`; a GUI e a CLI do wiebepy
  funcionam normalmente **sem** WSL2 — só os comandos de execução CFD
  falham (com diagnóstico do `doctor`, nunca com fallback silencioso).

### 2b. Linux

Siga o guia oficial da sua distribuição em <https://openfoam.org/download/linux>.
Depois verifique:

    wiebepy cfd doctor

## 3. Configuração mínima de um caso

Use `examples/config_cfd.yaml` como gabarito (campos obrigatórios
validados: intervalo, condições iniciais, paredes, combustível, Wiebe e
a seção `engine` reutilizada dos modos 0-D). Fluxo completo:

    wiebepy cfd prepare  --config examples/config_cfd.yaml
    wiebepy cfd validate --case results/cfd/case_001
    wiebepy cfd run      --case results/cfd/case_001 --follow
    wiebepy cfd status   --case results/cfd/case_001
    wiebepy cfd report   --case results/cfd/case_001

`prepare` é o modo de preparação **sem execução**: gera o caso para
inspeção. `run` exige estado *Validado*; "processo terminou" não
significa "convergiu" — o relatório separa as duas coisas. Cancelamento
explícito: `wiebepy cfd cancel --case …` (mata também os processos MPI;
logs e parciais preservados).

Na GUI, a mesma sequência está na página **CFD** (preparar → validar →
executar → relatório, com cancelamento e log visíveis).

## 4. Verificação da instalação (recomendado)

    pytest tests/test_cfd.py          # não exige OpenFOAM
    wiebepy cfd doctor                # exige WSL2/solver
    # caso de referência já executado: results/cfd/case_001
    # escada de V&V e números medidos: docs/cfd/verification.md