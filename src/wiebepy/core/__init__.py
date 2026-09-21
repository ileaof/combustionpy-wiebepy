# -*- coding: utf-8 -*-
"""Núcleo matemático: função multistage-Wiebe, derivada e parâmetros."""
from .core import (evaluate_batch, get_xp, multistage_wiebe,  # noqa: F401
                   stage_contributions, stage_terms)
from .derivatives import (finite_difference_check,  # noqa: F401
                          multistage_wiebe_derivative)
from .parameters import (A_DEFAULT, BETA_MODES, MAX_STAGES,  # noqa: F401
                         PENALTY, Parametrization, Stage, StageBounds,
                         as_stages, default_stages, sort_stages,
                         stages_to_arrays, validate_stages)
from .validation import DataError, validate_data  # noqa: F401
