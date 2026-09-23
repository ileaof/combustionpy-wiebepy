# -*- coding: utf-8 -*-
"""
cfd — Módulo CFD opcional do wiebepy.

Estuda escoamento e combustão em motores por meio de um solver externo
(OpenFOAM), com a liberação de calor global prescrita pela função Wiebe
do wiebepy (modo ``prescribed_wiebe``). O núcleo científico do wiebepy
não depende deste módulo: com ``cfd.enabled = false`` (padrão) nada daqui
é importado ou executado.

Importante — escopo do modo prescrito:
    Este modo NÃO prevê cinética química, frente de chama ou emissões.
    A combustão é prescrita pela curva Wiebe calibrada; a solução 3D
    responde a essa fonte de calor imposta. Ver docs/cfd/architecture.md.

Submódulos:
    config        configuração e validação do caso
    capabilities  diagnóstico do ambiente (WSL2, OpenFOAM)
    sources       fonte de calor conservativa a partir da Wiebe
    geometry      geometria paramétrica e cinemática do pistão
    fuels         propriedades de H2, CH4, etanol e diesel
    case_builder  geração do caso OpenFOAM a partir de templates
    adapters      integração com o solver (base abstrata + OpenFOAM)
    runner        execução, cancelamento, lock e logs
    results       leitura de resultados e curvas de comparação
    reporting     relatório HTML autocontido
    cli           subcomando ``wiebepy cfd …``

Estados do caso (CaseState): not_configured → prepared → validated →
running → completed | cancelled | failed.
"""
from __future__ import annotations

from .config import CfdConfig, CaseState, CfdConfigError, cfd_config_from_cfg

__all__ = ["CfdConfig", "CaseState", "CfdConfigError", "cfd_config_from_cfg"]


def cfd_enabled(cfg: dict) -> bool:
    """True se a seção ``cfd`` do configuration está habilitada.

    Seguro para configurações antigas sem a seção: retorna False.
    Nunca importa nada de CFD — pode ser chamado no caminho normal.
    """
    sec = (cfg or {}).get("cfd")
    return bool(isinstance(sec, dict) and sec.get("enabled", False))