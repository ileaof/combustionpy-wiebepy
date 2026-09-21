# -*- coding: utf-8 -*-
"""
model.py — API orientada a objetos.

    from wiebepy import MultiStageWiebe

    model = MultiStageWiebe(n_stages=3)
    xb = model.evaluate(theta)
    dxb = model.derivative(theta)
    result = model.fit(theta_exp, xb_exp, optimizer="pso", backend="auto")
    model.save("model.json")
    model = MultiStageWiebe.load("model.json")
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional, Sequence

import numpy as np

from . import __version__
from .core.core import multistage_wiebe, stage_contributions
from .core.derivatives import multistage_wiebe_derivative
from .core.parameters import (A_DEFAULT, MAX_STAGES, Stage, as_stages,
                              default_stages, sort_stages, validate_stages)


class MultiStageWiebe:
    """Modelo Wiebe de 1 a 5 estágios.

    n_stages   : número de estágios (1..5)
    stages     : parâmetros iniciais (lista de Stage ou dicts). Sem eles,
                 usa estágios padrão distribuídos em [theta_min, theta_max]
    a_fixed    : eficiência a_j usada quando ``fit_a=False`` (6.908)
    angle_unit : "deg" ou "rad" (apenas metadado/rotulagem: θ0 e Δθ estão
                 na mesma unidade de θ)
    """

    def __init__(self, n_stages: Optional[int] = None,
                 stages: Optional[Sequence] = None,
                 a_fixed: float = A_DEFAULT, angle_unit: str = "deg",
                 theta_min: float = -20.0, theta_max: float = 100.0):
        if stages is not None:
            self.stages: List[Stage] = sort_stages(stages)
            if n_stages is not None and n_stages != len(self.stages):
                raise ValueError("n_stages difere do número de estágios dados.")
        else:
            n = 1 if n_stages is None else int(n_stages)
            self.stages = default_stages(n, theta_min, theta_max, a_fixed)
        erros = validate_stages(self.stages)
        if erros:
            raise ValueError("; ".join(erros))
        self.a_fixed = a_fixed
        self.angle_unit = angle_unit
        self.last_fit = None

    # ------------------------------------------------------------- básico
    @property
    def n_stages(self) -> int:
        return len(self.stages)

    def evaluate(self, theta) -> np.ndarray:
        """Fração de massa queimada x_b(θ)."""
        return multistage_wiebe(np.asarray(theta, dtype=float), self.stages)

    def derivative(self, theta) -> np.ndarray:
        """Taxa de queima dx_b/dθ (analítica) [1/unidade angular]."""
        return multistage_wiebe_derivative(np.asarray(theta, dtype=float),
                                           self.stages)

    def contributions(self, theta):
        """(β_j x_j, β_j dx_j/dθ), cada um (N, n)."""
        return stage_contributions(np.asarray(theta, dtype=float),
                                   self.stages)

    # --------------------------------------------------------------- ajuste
    def fit(self, theta, xb=None, dxb=None, weights=None,
            optimizer: str = "pso", backend: str = "auto", **kwargs):
        """Ajusta os estágios aos dados. kwargs vão para FitSettings
        (runs, particles, iterations, seed, metric, fit_target, fit_a,
        beta_mode, workers, precision, bounds, polish...).

        Retorna FitResult e atualiza ``self.stages`` com o melhor ajuste.
        """
        if optimizer.lower() != "pso":
            raise ValueError("Otimizador disponível: 'pso'.")
        from .optimization.fit import FitSettings, fit
        from .optimization.objective import FitData
        data = FitData(theta, xb, dxb, weights, self.angle_unit)
        s = FitSettings(n_stages=self.n_stages, backend=backend,
                        a_fixed=self.a_fixed, **kwargs)
        r = fit(data, s)
        self.stages = r.stages
        self.last_fit = r
        return r

    # --------------------------------------------------------- persistência
    def to_dict(self) -> dict:
        return {"format": "wiebepy-model", "version": __version__,
                "n_stages": self.n_stages, "angle_unit": self.angle_unit,
                "a_fixed": self.a_fixed,
                "stages": [s.to_dict() for s in self.stages]}

    @classmethod
    def from_dict(cls, d: dict) -> "MultiStageWiebe":
        if d.get("format") not in (None, "wiebepy-model"):
            raise ValueError("Arquivo não é um modelo wiebepy.")
        st = as_stages(d["stages"])
        if not 1 <= len(st) <= MAX_STAGES:
            raise ValueError("Modelo com número de estágios inválido.")
        return cls(stages=st, a_fixed=float(d.get("a_fixed", A_DEFAULT)),
                   angle_unit=d.get("angle_unit", "deg"))

    def save(self, path) -> Path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        return p

    @classmethod
    def load(cls, path) -> "MultiStageWiebe":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    def __repr__(self) -> str:
        return (f"MultiStageWiebe(n_stages={self.n_stages}, "
                f"stages={[s.to_dict() for s in self.stages]})")
