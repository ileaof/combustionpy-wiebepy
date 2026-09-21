# -*- coding: utf-8 -*-
"""
wiebepy — Funções Wiebe de 1 a 5 estágios.

Avaliação vetorizada de x_b(θ) e dx_b/dθ, ajuste a dados experimentais por
PSO (lote NumPy, Numba, multiprocessing ou GPU via CuPy), comparação entre
números de estágios (AIC/BIC + validação cruzada por blocos) e análise de
identificabilidade.

    from wiebepy import MultiStageWiebe
    model = MultiStageWiebe(n_stages=3)
    xb = model.evaluate(theta)
"""
__version__ = "1.0.0"

from .core import (A_DEFAULT, MAX_STAGES, Stage,  # noqa: F401,E402
                   multistage_wiebe, multistage_wiebe_derivative)
from .model import MultiStageWiebe  # noqa: F401,E402

__all__ = ["MultiStageWiebe", "Stage", "multistage_wiebe",
           "multistage_wiebe_derivative", "A_DEFAULT", "MAX_STAGES",
           "__version__"]
