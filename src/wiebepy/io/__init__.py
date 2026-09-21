# -*- coding: utf-8 -*-
"""Entrada/saída: leitura de dados, configuração e arquivos de resultado."""
from .config import ConfigError, load_config, resolve  # noqa: F401
from .readers import read_data, theta_grid  # noqa: F401
