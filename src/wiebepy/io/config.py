# -*- coding: utf-8 -*-
"""
config.py — Arquivos de configuração (JSON, YAML, TOML) e mesclagem com a CLI.

Estrutura (todas as seções e chaves são opcionais):

    model:
      stages: 3                 # número de estágios (1..5)
      a_fixed: 6.908
      fit_a: false
      beta_mode: stick          # stick | softmax | explicit
      angle_unit: deg
      parameters:               # estágios para avaliação sem ajuste
        - {beta: 0.3, theta0: -5, duration: 12, m: 2.0}
    grid: {theta_min: -20, theta_max: 100, theta_step: 0.1}
    optimization:
      method: pso
      particles: 100
      iterations: 1000
      patience: 200
      topology: ring            # ring | global
      runs: 10
      seed: 42
      objective: rmse           # rmse | mse | mae | see | wrmse
      fit_target: xb            # xb | dxb | both
      w_x: 1.0
      w_d: 1.0
      polish: true
      polish_starts: 5
    bounds:                     # sobrescritas dos limites (ver bounds.py)
      duration: [2, 90]
      m: [0.1, 4]
    comparison: {stages: [1, 2, 3, 4, 5], cv_folds: 5, cv_tol: 0.05}
    parallel: {backend: auto, workers: 8, precision: float64}
    output: {directory: results, save_plots: true, json: false}

Precedência: valores padrão < arquivo de configuração < opções da CLI.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict

import yaml

DEFAULTS: Dict[str, Any] = {
    "model": {"stages": 2, "a_fixed": 6.908, "fit_a": False,
              "beta_mode": "stick", "angle_unit": "deg", "parameters": None},
    "grid": {"theta_min": -20.0, "theta_max": 100.0, "theta_step": 0.1},
    "optimization": {"method": "pso", "particles": 100, "iterations": 1000,
                     "patience": 200, "topology": "ring", "runs": 5, "seed": 42,
                     "objective": "rmse", "fit_target": None, "w_x": 1.0,
                     "w_d": 1.0, "polish": True, "polish_starts": 5},
    "bounds": {},
    "comparison": {"stages": [1, 2, 3, 4, 5], "cv_folds": 5, "cv_tol": 0.05},
    "parallel": {"backend": "auto", "workers": None, "precision": "float64"},
    "output": {"directory": "results", "save_plots": False, "json": False},
    # modo pressão (--input-type pressure)
    "pressure": {"input_type": None, "angle_unit": "rad", "pressure_unit": "bar",
                 "theta_min_rad": -2.0, "theta_max_rad": 2.0,
                 "particles": 60, "iterations": 400},
    "engine": {},     # motor (chaves do Double Wiebe ou de EngineConfig)
    # módulo CFD opcional (sempre presente e DESLIGADO por padrão; com
    # enabled: false nada é importado/executado — ver wiebepy/cfd)
    "cfd": None,
}

SECOES = tuple(DEFAULTS)


class ConfigError(ValueError):
    """Arquivo de configuração inválido."""


def load_config(path) -> Dict[str, Any]:
    """Lê JSON/YAML/TOML e devolve o dict (sem mesclar com os padrões)."""
    p = Path(path)
    if not p.exists():
        raise ConfigError(f"Arquivo de configuração não encontrado: {p}")
    texto = p.read_text(encoding="utf-8")
    ext = p.suffix.lower()
    try:
        if ext == ".json":
            d = json.loads(texto)
        elif ext in (".yaml", ".yml"):
            d = yaml.safe_load(texto) or {}
        elif ext == ".toml":
            import tomllib
            d = tomllib.loads(texto)
        else:
            raise ConfigError(f"Formato '{ext}' não suportado (.json, .yaml, "
                              ".yml, .toml).")
    except (json.JSONDecodeError, yaml.YAMLError, ValueError) as e:
        if isinstance(e, ConfigError):
            raise
        raise ConfigError(f"{p.name}: erro de sintaxe ({e}).") from None
    if not isinstance(d, dict):
        raise ConfigError(f"{p.name}: o conteúdo deve ser um mapeamento.")
    desconhecidas = set(d) - set(SECOES)
    if desconhecidas:
        raise ConfigError(f"{p.name}: seções desconhecidas "
                          f"{sorted(desconhecidas)}; válidas: {list(SECOES)}.")
    return d


def merge(base: Dict, extra: Dict) -> Dict:
    """Mescla recursiva (extra prevalece); None em extra não sobrescreve."""
    out = copy.deepcopy(base)
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict) and k != "bounds":
            out[k] = merge(out[k], v)
        elif v is not None:
            out[k] = copy.deepcopy(v)
    return out


def resolve(config_path=None, cli: Dict = None) -> Dict[str, Any]:
    """Padrões < arquivo < CLI."""
    cfg = copy.deepcopy(DEFAULTS)
    if config_path:
        cfg = merge(cfg, load_config(config_path))
    return merge(cfg, cli or {})


def dump_yaml(cfg: Dict, path) -> Path:
    p = Path(path)
    p.write_text(yaml.safe_dump(_plain(cfg), sort_keys=False,
                                allow_unicode=True), encoding="utf-8")
    return p


def _plain(o):
    """Converte numpy/tuplas em tipos YAML simples."""
    import numpy as np
    if isinstance(o, dict):
        return {str(k): _plain(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_plain(v) for v in o]
    if isinstance(o, np.generic):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    return o
