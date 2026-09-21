# -*- coding: utf-8 -*-
"""Fixtures compartilhadas: estágios de referência para N = 1..5."""
from __future__ import annotations

import numpy as np
import pytest

from wiebepy.core import Stage

# Estágios de referência (graus) — inícios crescentes, pesos somando 1
REF_STAGES = {
    1: [Stage(1.0, -10.0, 60.0, 2.0)],
    2: [Stage(0.35, -5.0, 12.0, 2.0), Stage(0.65, 2.0, 45.0, 1.3)],
    3: [Stage(0.2, -8.0, 10.0, 2.5), Stage(0.5, 0.0, 30.0, 1.2),
        Stage(0.3, 15.0, 50.0, 0.8)],
    4: [Stage(0.15, -8.0, 8.0, 3.0), Stage(0.35, -2.0, 25.0, 1.5),
        Stage(0.3, 10.0, 40.0, 1.0), Stage(0.2, 30.0, 50.0, 0.6)],
    5: [Stage(0.1, -10.0, 6.0, 3.0), Stage(0.25, -4.0, 18.0, 2.0),
        Stage(0.3, 5.0, 30.0, 1.2), Stage(0.2, 20.0, 45.0, 0.9),
        Stage(0.15, 40.0, 50.0, 0.5)],
}


@pytest.fixture
def theta():
    return np.linspace(-20.0, 100.0, 1201)


@pytest.fixture(params=[1, 2, 3, 4, 5], ids=lambda n: f"N{n}")
def n_stages(request):
    return request.param


@pytest.fixture
def stages(n_stages):
    return REF_STAGES[n_stages]
