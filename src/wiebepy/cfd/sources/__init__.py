# -*- coding: utf-8 -*-
"""Fonte de calor do módulo CFD (import sob demanda — nunca com CFD off)."""
from .wiebe_heat_release import (DEG_PER_S_PER_RPM, RAD_PER_S_PER_RPM,
                                 dtheta_dt, distribution_notice,
                                 energy_check, function1_table, qdot_power,
                                 qdot_time_series, table_text)

__all__ = ["DEG_PER_S_PER_RPM", "RAD_PER_S_PER_RPM", "dtheta_dt",
           "distribution_notice", "energy_check", "function1_table",
           "qdot_power", "qdot_time_series", "table_text"]