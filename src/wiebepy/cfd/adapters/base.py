# -*- coding: utf-8 -*-
"""
adapters.base — Interface entre o módulo CFD do wiebepy e um solver
externo.

O núcleo do wiebepy NÃO conhece detalhes do solver: toda interação
(diagnóstico, execução, cancelamento) passa por um ``CfdAdapter``. Isso
permite, no futuro, adapters para outros solvers sem alterar o resto do
módulo.

Contrato:
    diagnose()      → dict de diagnóstico (versões, caminhos)
    check_runnable()→ lista de erros BLOQUEANTES para executar um caso
    run_case(...)   → executa o caso no diretório dado; captura saída em
                      logs; respeita cancelamento; retorna resumo
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable, Dict, List, Optional

OutputCb = Optional[Callable[[str], None]]
CancelCheck = Optional[Callable[[], bool]]


class AdapterError(RuntimeError):
    """Erro do adapter/solver (mensagem voltada ao usuário)."""


class CfdAdapter(ABC):
    """Base dos adapters de solver CFD."""

    #: nome do adapter (cfd.adapter na configuração)
    name: str = "base"

    @abstractmethod
    def diagnose(self) -> Dict:
        """Diagnóstico do ambiente do solver (sem executar o caso)."""

    @abstractmethod
    def check_runnable(self) -> List[str]:
        """Erros que impedem a execução (lista vazia = pronto)."""

    @abstractmethod
    def run_case(self, case_dir: Path, workers: int = 1,
                 on_output: OutputCb = None,
                 cancel: CancelCheck = None) -> Dict:
        """Executa o caso completo (malha → solver → reconstrução).

        Retorna dict com status ('completed' | 'cancelled' | 'failed'),
        etapas, tempo e versões. Não levanta exceção por falha do solver:
        registra em ``logs`` e retorna status 'failed' — o runner decide.
        """


def get_adapter(name: str, **kw) -> CfdAdapter:
    """Fábrica de adapters (import sob demanda — nunca com CFD off)."""
    if name == "openfoam":
        from .openfoam import OpenFoamAdapter
        return OpenFoamAdapter(**kw)
    raise AdapterError(f"Adapter '{name}' não implementado.")


__all__ = ["CfdAdapter", "AdapterError", "get_adapter", "OutputCb",
           "CancelCheck"]