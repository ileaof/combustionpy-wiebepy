# -*- coding: utf-8 -*-
"""
writers.py — Arquivos de saída.

    results.csv              θ, x_b e dx_b/dθ (ajustados), dados
                             experimentais e resíduos, contribuições β_j x_j
                             e β_j dx_j/dθ de cada estágio
    parameters.csv           parâmetros do melhor ajuste + média/desvio entre
                             runs
    metrics.csv              métricas (RMSE, MAE, SEE, R², AIC, BIC, DW...)
    run_statistics.csv       objetivo de cada run + best/mean/std/median/worst
    comparison.csv           tabela da comparação 1..5 estágios
    warnings.txt             avisos de identificabilidade (lista completa)
    configuration_used.yaml  configuração efetiva da execução
    results.json             (opcional) tudo acima em JSON
    model.json               modelo reutilizável (MultiStageWiebe.load)
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import numpy as np

from ..core.core import multistage_wiebe, stage_contributions
from ..core.derivatives import multistage_wiebe_derivative
from .config import _plain, dump_yaml


def _unit_suffix(angle_unit: str) -> str:
    return "deg" if angle_unit == "deg" else "rad"


def _write_rows(path: Path, header: List[str], rows) -> Path:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        for r in rows:
            w.writerow([f"{v:.10g}" if isinstance(v, (float, np.floating))
                        else v for v in r])
    return path


def write_results_csv(outdir: Path, theta, stages, data=None,
                      angle_unit: str = "deg") -> Path:
    u = _unit_suffix(angle_unit)
    th = np.asarray(theta, dtype=float)
    xb = multistage_wiebe(th, stages)
    dxb = multistage_wiebe_derivative(th, stages)
    cx, cd = stage_contributions(th, stages)
    cols = {f"theta_{u}": th, "xb_fit": xb, f"dxb_dtheta_fit_per_{u}": dxb}
    if data is not None:
        if data.xb is not None:
            cols["xb_exp"] = data.xb
            cols["xb_residual"] = xb - data.xb
        if data.dxb is not None:
            cols[f"dxb_dtheta_exp_per_{u}"] = data.dxb
            cols["dxb_residual"] = dxb - data.dxb
    for j in range(len(stages)):
        cols[f"beta{j + 1}_xb{j + 1}"] = cx[j]
        cols[f"beta{j + 1}_dxb{j + 1}_per_{u}"] = cd[j]
    return _write_rows(outdir / "results.csv", list(cols),
                       zip(*cols.values()))


def write_parameters_csv(outdir: Path, stages, param_stats: Optional[Dict] = None,
                         angle_unit: str = "deg") -> Path:
    u = _unit_suffix(angle_unit)
    unidades = {"beta": "-", "theta0": u, "duration": u, "m": "-", "a": "-"}
    linhas = []
    for j, s in enumerate(stages, start=1):
        for k in ("beta", "theta0", "duration", "m", "a"):
            chave = f"{k}_{j}"
            st = (param_stats or {}).get(chave, {})
            linhas.append([j, k, getattr(s, k), unidades[k],
                           st.get("mean", ""), st.get("std", "")])
    return _write_rows(outdir / "parameters.csv",
                       ["stage", "parameter", "value", "unit",
                        "mean_over_runs", "std_over_runs"], linhas)


def write_metrics_csv(outdir: Path, metrics: Dict[str, Dict]) -> Path:
    linhas = [[serie, k, v] for serie, m in metrics.items()
              for k, v in m.items()]
    return _write_rows(outdir / "metrics.csv", ["series", "metric", "value"],
                       linhas)


def write_run_statistics_csv(outdir: Path, fit_result) -> Path:
    linhas = [[r.run + 1, r.seed if r.seed is not None else "", r.objective,
               r.objective_pso, r.iterations, r.stopped_by, r.n_evals,
               r.elapsed_s] for r in fit_result.runs]
    linhas.append([])
    for k, v in fit_result.objective_stats.items():
        linhas.append([k, "", v])
    return _write_rows(outdir / "run_statistics.csv",
                       ["run", "seed", "objective", "objective_pso_only",
                        "iterations", "stopped_by", "evaluations", "time_s"],
                       linhas)


def write_comparison_csv(outdir: Path, table: Sequence[Dict]) -> Path:
    cab = list(table[0])
    return _write_rows(outdir / "comparison.csv", cab,
                       ([l[c] for c in cab] for l in table))


def write_warnings(outdir: Path, warnings: Sequence[str]) -> Path:
    p = outdir / "warnings.txt"
    p.write_text("".join(f"{w}\n" for w in warnings), encoding="utf-8")
    return p


def write_json(outdir: Path, payload: Dict, name: str = "results.json") -> Path:
    p = outdir / name
    p.write_text(json.dumps(_plain(payload), indent=2, ensure_ascii=False,
                            default=str), encoding="utf-8")
    return p


def write_configuration(outdir: Path, cfg: Dict) -> Path:
    return dump_yaml(cfg, outdir / "configuration_used.yaml")


def prepare_outdir(path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p
