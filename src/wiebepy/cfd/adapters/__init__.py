# -*- coding: utf-8 -*-
"""adapters — Integração com solvers CFD (import sob demanda)."""
from .base import AdapterError, CfdAdapter, get_adapter

__all__ = ["AdapterError", "CfdAdapter", "get_adapter"]