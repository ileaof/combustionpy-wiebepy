# -*- coding: utf-8 -*-
"""
crevice_flow — módulo OPCIONAL do wiebepy para CFD localizado da fresta
entre pistão, anéis e cilindro (top-land crevice).

Integra-se sem alterar os modelos single/double/multi-Wiebe nem os casos
CFD de câmara existentes: nada do wiebepy importa este pacote por padrão.
O primeiro nível implementado é o SUBMODELO de fresta — um domínio
localizado (fresta + coluna de gás de entrada) alimentado pela pressão da
câmara prescrita como condição de contorno:

    • escoamento compressível transiente (solver ``fluid`` do OpenFOAM
      Foundation), NÃO reativo;
    • entrada e saída de gás da fresta durante o ciclo (inversão de fluxo
      suportada);
    • armazenamento de massa e energia na fresta;
    • transferência de calor com paredes (temperatura prescrita ou
      parede adiabática).

Delimitação explícita da primeira versão:

    • a fresta comunicando APENAS com a câmara (fundo fechado) — este
      modo NÃO é simulação de blow-by: blow-by exige caminho de vazamento
      até uma região de menor pressão, com a pressão do destino declarada;
    • sem movimento dos anéis, sem filme de óleo, sem combustão e sem
      transporte de combustível;
    • no submodelo, o escoamento calculado NÃO modifica a pressão da
      câmara prescrita — não é acoplamento bidirecional. O domínio
      integrado câmara–fresta é uma extensão planejada, não esta versão.
"""
from __future__ import annotations

from .config import (CreviceConfig, CreviceConfigError, ChamberBC,
                     CreviceGeometry, CreviceThermal, read_crevice_config)

__all__ = ["CreviceConfig", "CreviceConfigError", "ChamberBC",
           "CreviceGeometry", "CreviceThermal", "read_crevice_config"]