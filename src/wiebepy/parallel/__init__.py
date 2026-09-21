# -*- coding: utf-8 -*-
"""Backends de avaliação: NumPy, Numba, multiprocessing e CuPy (GPU)."""
from .backend import (BACKENDS, available_backends, choose_auto,  # noqa: F401
                      make_objective)
from .hardware import detect_hardware, hardware_report  # noqa: F401
