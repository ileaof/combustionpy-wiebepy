# -*- coding: utf-8 -*-
"""
compare.py — Comparação objetiva entre modelos de 1 a 5 estágios.

Para cada N ajusta o modelo (com ``runs`` runs) e reporta RMSE, MAE, SEE,
R², AIC, BIC, número de parâmetros, tempo e diagnóstico dos resíduos.

AIC/BIC supõem resíduos independentes; em curvas de fração queimada os
resíduos são fortemente autocorrelacionados (Durbin-Watson << 2) e a
penalidade k·ln(n) fica pequena perante n·ln(SSE/n) — AIC/BIC tendem a
favorecer mais estágios. Por isso a recomendação usa principalmente a
VALIDAÇÃO CRUZADA POR BLOCOS INTERCALADOS: θ é dividido em muitos blocos
contíguos curtos (~2 % dos pontos, mais longos que a correlação típica dos
resíduos), distribuídos ciclicamente entre ``cv_folds`` folds; cada fold é
previsto por um ajuste feito sem ele. Blocos grandes únicos obrigariam o
modelo a EXTRAPOLAR (ex.: remover o início da combustão apaga a informação
sobre θ0) e dominariam o erro. Os ajustes de CV partem do ótimo dos dados
completos, com 1/4 das iterações, para medir generalização e não a sorte
do otimizador.

Refinamento aninhado: os modelos são aninhados (N estágios ⊂ N+1 com um
β = 0), mas o PSO de um N isolado pode cair numa bacia falsa (ex.: dois
estágios com o mesmo θ0). Depois de ajustar todos os N, de cima para baixo,
cada estágio do ótimo de N+1 é removido (β renormalizados) e o resultado é
refinado localmente como candidato para N; se melhorar o objetivo de N, o
candidato entra como um run extra ("nested"). Isso torna a comparação
robusta a falhas pontuais do otimizador.

Regra de recomendação (documentada no README):
    1. N_cv = argmin do erro de validação cruzada;
    2. escolhe-se o MENOR N cujo erro de CV fica a até ``cv_tol`` (5 %) do
       de N_cv e cujo ajuste não tem estágios desprezíveis/coincidentes;
    3. sem CV (cv_folds = 0), usa-se o menor BIC com a mesma ressalva.
O menor RMSE de treino nunca é, sozinho, critério de escolha.
"""
from __future__ import annotations

import logging
import time
from dataclasses import replace
from typing import Dict, List, Optional, Sequence

import numpy as np

from ..core.core import multistage_wiebe
from ..core.derivatives import multistage_wiebe_derivative
from .fit import (FitResult, FitSettings, RunResult, build_problem, fit,
                  refine, single_run, summarize)
from .objective import FitData

log = logging.getLogger("wiebepy")

_ESTRUTURAIS = ("contributes less than", "nearly identical")


def _serie_principal(data: FitData, target: str) -> str:
    return "xb" if (data.xb is not None and target in ("xb", "both")) else "dxb"


def block_folds(n: int, k: int, block_frac: float = 0.02) -> List[np.ndarray]:
    """Máscaras de teste de k folds formados por blocos contíguos curtos
    (block_frac·n pontos, ao menos 3) atribuídos ciclicamente aos folds.
    Sem embaralhar pontos; todo ponto cai em exatamente um fold."""
    tam = max(3, int(round(block_frac * n)))
    bloco = np.arange(n) // tam
    return [(bloco % k) == i for i in range(k)]


def block_cv(data: FitData, s: FitSettings, x_full: np.ndarray,
             folds: int) -> Dict:
    """RMSE de previsão por blocos (série principal)."""
    from ..parallel.backend import make_objective
    serie = _serie_principal(data, s.fit_target or data.default_target())
    erros = []
    s1 = replace(s, runs=1, parallel_runs="no",
                 iterations=max(100, s.iterations // 4),
                 patience=max(50, s.patience // 4))
    for i, teste in enumerate(block_folds(data.n, folds)):
        treino = data.subset(~teste)
        param, spec = build_problem(treino, s1)
        obj = make_objective(s1.backend, treino, param, spec, s1.precision,
                             s1.workers, s1.particles)
        try:
            r = single_run(obj, param, s1, 0,
                           None if s.seed is None else s.seed + 1000 + i,
                           data=treino, spec=spec, x0=x_full)
        finally:
            obj.close()
        st = param.to_stages(r.x)
        th = data.theta[teste]
        prev = (multistage_wiebe(th, st) if serie == "xb"
                else multistage_wiebe_derivative(th, st))
        y = (data.xb if serie == "xb" else data.dxb)[teste]
        erros.append(float(np.sqrt(np.mean((prev - y) ** 2))))
    e = np.asarray(erros)
    return {"cv_rmse": float(e.mean()), "cv_std": float(e.std(ddof=1))
            if e.size > 1 else 0.0, "cv_folds": folds,
            "cv_fold_rmse": erros, "series": serie}


def nested_candidate(maior: FitResult, N: int, data: FitData,
                     s: FitSettings) -> RunResult:
    """Melhor candidato de N estágios obtido removendo um estágio do ótimo
    de N+1 (β renormalizados) seguido de refinamento local."""
    from ..core.parameters import Stage
    from ..parallel.backend import make_objective
    param, spec = build_problem(data, s)
    inicios = []
    for j in range(len(maior.stages)):
        resto = [st for i, st in enumerate(maior.stages) if i != j]
        soma = sum(st.beta for st in resto)
        if soma <= 0:
            continue
        resto = [Stage(st.beta / soma, st.theta0, st.duration, st.m, st.a)
                 for st in resto]
        inicios.append(np.clip(param.encode(resto), param.lower, param.upper))
    obj = make_objective("numpy", data, param, spec, s.precision)
    t0 = time.perf_counter()
    x, f = refine(obj, inicios, param, data, spec)
    obj.close()
    return RunResult(run=len(inicios), seed=None, x=x, objective=f,
                     objective_pso=float("nan"), history=[], iterations=0,
                     stopped_by="nested", elapsed_s=time.perf_counter() - t0,
                     n_evals=0)


def compare_stages(data: FitData, ns: Sequence[int], base: FitSettings,
                   cv_folds: int = 5, cv_tol: float = 0.05,
                   nested: bool = True) -> Dict:
    """Ajusta cada N e devolve tabela, resultados e recomendação."""
    ns = sorted(set(int(n) for n in ns))
    resultados: Dict[int, FitResult] = {}
    tempos: Dict[int, float] = {}
    for N in ns:
        log.info("=== Modelo %d-Wiebe ===", N)
        t0 = time.perf_counter()
        resultados[N] = fit(data, replace(base, n_stages=N))
        tempos[N] = time.perf_counter() - t0
    if nested:
        for N in sorted(ns, reverse=True):
            if N + 1 not in resultados:
                continue
            s = replace(base, n_stages=N)
            cand = nested_candidate(resultados[N + 1], N, data, s)
            r = resultados[N]
            if cand.objective < r.best.objective * (1 - 1e-9):
                log.info("N=%d: candidato aninhado (de N=%d) melhora o "
                         "objetivo %.6e -> %.6e", N, N + 1, r.best.objective,
                         cand.objective)
                cand.run = len(r.runs)
                resultados[N] = summarize(data, s, r.param, r.spec,
                                          r.runs + [cand], r.backend,
                                          r.elapsed_s + cand.elapsed_s)
            tempos[N] += cand.elapsed_s
    linhas: List[Dict] = []
    for N in ns:
        t0 = time.perf_counter()
        s = replace(base, n_stages=N)
        r = resultados[N]
        cv = block_cv(data, s, r.best.x, cv_folds) if cv_folds >= 2 else {}
        serie = _serie_principal(data, r.spec.fit_target)
        m = r.metrics[serie]
        estruturais = [w for w in r.warnings
                       if any(t in w for t in _ESTRUTURAIS)]
        linhas.append({
            "n_stages": N, "k": r.param.size, "series": serie,
            "objective": r.objective_stats["best"],
            "rmse": m["rmse"], "mae": m["mae"], "see": m["see"],
            "r2": m["r2"], "aic": m["aic"], "bic": m["bic"],
            "durbin_watson": m["durbin_watson"],
            "lag1_autocorr": m["lag1_autocorr"],
            "cv_rmse": cv.get("cv_rmse", float("nan")),
            "cv_std": cv.get("cv_std", float("nan")),
            "objective_run_std": r.objective_stats["std"],
            "n_warnings": len(r.warnings),
            "structural_warnings": len(estruturais),
            "nested_improved": any(x.stopped_by == "nested" and x is r.best
                                   for x in r.runs),
            "time_s": tempos[N] + time.perf_counter() - t0,
        })
    aic_min = min(l["aic"] for l in linhas)
    bic_min = min(l["bic"] for l in linhas)
    for l in linhas:
        l["delta_aic"] = l["aic"] - aic_min
        l["delta_bic"] = l["bic"] - bic_min
    rec, motivo = recommend(linhas, cv_tol)
    return {"table": linhas, "results": resultados, "recommended": rec,
            "reason": motivo, "cv_folds": cv_folds, "cv_tol": cv_tol}


def recommend(linhas: List[Dict], cv_tol: float = 0.05):
    """Aplica a regra de parcimônia descrita no cabeçalho do módulo."""
    usa_cv = all(np.isfinite(l["cv_rmse"]) for l in linhas)
    chave = "cv_rmse" if usa_cv else "bic"
    ref = min(linhas, key=lambda l: l[chave])
    limiar = (ref["cv_rmse"] * (1 + cv_tol) if usa_cv else ref["bic"] + 2.0)
    for l in sorted(linhas, key=lambda l: l["n_stages"]):
        if l[chave] <= limiar and l["structural_warnings"] == 0:
            n = l["n_stages"]
            break
    else:
        n = ref["n_stages"]
    if usa_cv:
        motivo = (f"menor N com erro de validação cruzada a até "
                  f"{cv_tol * 100:.0f}% do melhor (N={ref['n_stages']}, "
                  f"CV RMSE={ref['cv_rmse']:.4g}) e sem estágios "
                  f"desprezíveis/coincidentes")
    else:
        motivo = (f"menor N com BIC a até 2 unidades do mínimo "
                  f"(N={ref['n_stages']}) e sem estágios desprezíveis/"
                  f"coincidentes — validação cruzada desativada")
    return n, motivo
