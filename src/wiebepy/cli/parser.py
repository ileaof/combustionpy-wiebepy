# -*- coding: utf-8 -*-
"""
parser.py — Interface de linha de comando.

    python main.py --help        (ou: wiebepy --help, após pip install -e .)

Códigos de saída: 0 sucesso | 2 erro de uso/dados/configuração |
1 erro inesperado.
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from .. import __version__
from .helptext import DESCRIPTION, EPILOG, HELP_EXAMPLES, HELP_MODEL

log = logging.getLogger("wiebepy")

EXIT_OK, EXIT_ERR, EXIT_USO = 0, 1, 2


# =============================================================================
# Parser
# =============================================================================
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="wiebepy", description=DESCRIPTION, epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    a = p.add_argument

    g = p.add_argument_group("modelo")
    g.add_argument("--stages", type=int, metavar="N",
                   help="número de estágios, 1 a 5 (padrão 2)")
    g.add_argument("--compare-stages", type=int, nargs="+", metavar="N",
                   help="ajusta e compara estes números de estágios "
                        "(ex.: 1 2 3 4 5); requer --input")
    g.add_argument("--a-fixed", type=float, metavar="A",
                   help="eficiência a_j fixa (padrão 6.908 = ln 1000)")
    g.add_argument("--fit-a", action="store_true", default=None,
                   help="ajusta a_j de cada estágio em vez de fixá-lo")
    g.add_argument("--beta-param", choices=["stick", "softmax", "explicit"],
                   help="parametrização das frações β (padrão stick)")
    g.add_argument("--model", metavar="JSON",
                   help="modelo salvo (model.json) para avaliar sem ajuste")
    g.add_argument("--angle-unit", choices=["deg", "rad"],
                   help="unidade angular de θ, θ0 e Δθ (padrão deg)")

    g = p.add_argument_group("grade angular (modo de avaliação)")
    g.add_argument("--theta-min", type=float, metavar="θ",
                   help="início da grade (padrão -20)")
    g.add_argument("--theta-max", type=float, metavar="θ",
                   help="fim da grade (padrão 100)")
    g.add_argument("--theta-step", type=float, metavar="Δ",
                   help="passo da grade (padrão 0.1)")

    g = p.add_argument_group("dados e saída")
    g.add_argument("--input", metavar="ARQ",
                   help="dados experimentais (.csv .txt .dat .json)")
    g.add_argument("--output", metavar="DIR",
                   help="diretório de resultados (padrão results)")
    g.add_argument("--config", metavar="ARQ",
                   help="configuração .json/.yaml/.toml (a CLI prevalece)")
    g.add_argument("--json", action="store_true", default=None,
                   help="também grava results.json")
    g.add_argument("--plot", action="store_true",
                   help="mostra os gráficos na tela")
    g.add_argument("--save-plots", action="store_true", default=None,
                   help="grava os gráficos PNG em <output>/plots")

    g = p.add_argument_group("otimização")
    g.add_argument("--optimize", action="store_true",
                   help="ajusta os parâmetros aos dados de --input")
    g.add_argument("--optimizer", choices=["pso"], default="pso",
                   help="otimizador global (pso)")
    g.add_argument("--population", type=int, metavar="S",
                   help="partículas do PSO (padrão 100)")
    g.add_argument("--iterations", type=int, metavar="K",
                   help="iterações máximas do PSO (padrão 1000)")
    g.add_argument("--patience", type=int, metavar="K",
                   help="iterações sem melhora antes de parar (padrão 200)")
    g.add_argument("--topology", choices=["ring", "global"],
                   help="topologia do PSO (padrão ring: menos convergência "
                        "prematura)")
    g.add_argument("--runs", type=int, metavar="R",
                   help="runs independentes com sementes seed+i (padrão 5)")
    g.add_argument("--seed", type=int, help="semente base (padrão 42)")
    g.add_argument("--objective", choices=["rmse", "mse", "mae", "see",
                                           "wrmse"],
                   help="função objetivo (padrão rmse)")
    g.add_argument("--fit-target", choices=["xb", "dxb", "both"],
                   help="série ajustada (padrão: as disponíveis nos dados)")
    g.add_argument("--w-x", type=float, help="peso de x_b no alvo both")
    g.add_argument("--w-d", type=float, help="peso de dx_b/dθ no alvo both")
    g.add_argument("--no-polish", action="store_true",
                   help="desliga o refinamento local após o PSO")
    g.add_argument("--cv-folds", type=int, metavar="K",
                   help="blocos da validação cruzada em --compare-stages "
                        "(padrão 5; 0 desliga)")

    g = p.add_argument_group("paralelismo")
    g.add_argument("--backend", choices=["auto", "numpy", "numba",
                                         "multiprocessing", "cupy"],
                   help="backend de avaliação (padrão auto)")
    g.add_argument("--workers", type=int, metavar="W",
                   help="threads (numba) ou processos (multiprocessing e "
                        "runs paralelos); padrão: núcleos − 1")
    g.add_argument("--gpu", action="store_true",
                   help="atalho para --backend cupy")
    g.add_argument("--precision", choices=["float64", "float32"],
                   help="precisão (padrão float64; float32 é mais rápido "
                        "em GPU)")

    g = p.add_argument_group("utilidades")
    g.add_argument("--benchmark", action="store_true",
                   help="benchmark dos backends nesta máquina")
    g.add_argument("--benchmark-full", action="store_true",
                   help="benchmark incluindo n = 1e5 no cenário do PSO")
    g.add_argument("--devices", action="store_true",
                   help="mostra o hardware detectado e sai")
    g.add_argument("--gui", action="store_true",
                   help="abre a interface gráfica no navegador (requer "
                        "pip install -e \".[gui]\")")
    g.add_argument("--help-model", action="store_true",
                   help="mostra a formulação matemática e sai")
    g.add_argument("--help-examples", action="store_true",
                   help="mostra comandos prontos e sai")
    nivel = g.add_mutually_exclusive_group()
    nivel.add_argument("--quiet", "-q", action="store_true",
                       help="só avisos e erros")
    nivel.add_argument("--verbose", "-v", action="store_true",
                       help="hardware, backend e progresso do PSO")
    nivel.add_argument("--debug", action="store_true",
                       help="mensagens de depuração")
    a("--version", action="version", version=f"wiebepy {__version__}")
    return p


def _cli_overrides(a) -> Dict:
    """Opções da CLI no formato do arquivo de configuração (None = ausente)."""
    return {
        "model": {"stages": a.stages, "a_fixed": a.a_fixed,
                  "fit_a": a.fit_a, "beta_mode": a.beta_param,
                  "angle_unit": a.angle_unit},
        "grid": {"theta_min": a.theta_min, "theta_max": a.theta_max,
                 "theta_step": a.theta_step},
        "optimization": {"particles": a.population,
                         "iterations": a.iterations, "patience": a.patience,
                         "topology": a.topology,
                         "runs": a.runs, "seed": a.seed,
                         "objective": a.objective, "fit_target": a.fit_target,
                         "w_x": a.w_x, "w_d": a.w_d,
                         "polish": False if a.no_polish else None},
        "comparison": {"stages": a.compare_stages, "cv_folds": a.cv_folds},
        "parallel": {"backend": "cupy" if a.gpu else a.backend,
                     "workers": a.workers, "precision": a.precision},
        "output": {"directory": a.output, "save_plots": a.save_plots,
                   "json": a.json},
    }


def _setup_logging(a) -> None:
    nivel = (logging.WARNING if a.quiet else
             logging.DEBUG if a.debug else logging.INFO)
    logging.basicConfig(level=nivel, format="%(message)s", force=True)
    log.setLevel(nivel)


# =============================================================================
# Execução
# =============================================================================
def _settings(cfg: Dict, n_stages: int):
    from ..optimization.fit import FitSettings
    o, m, par = cfg["optimization"], cfg["model"], cfg["parallel"]
    return FitSettings(
        n_stages=n_stages, beta_mode=m["beta_mode"], fit_a=bool(m["fit_a"]),
        a_fixed=float(m["a_fixed"]), bounds=cfg.get("bounds") or {},
        metric=o["objective"], fit_target=o["fit_target"],
        w_x=float(o["w_x"]), w_d=float(o["w_d"]),
        particles=int(o["particles"]), iterations=int(o["iterations"]),
        patience=int(o["patience"]), topology=o.get("topology", "ring"),
        runs=int(o["runs"]),
        seed=None if o["seed"] is None else int(o["seed"]),
        backend=par["backend"], workers=par["workers"],
        precision=par["precision"], polish=bool(o["polish"]),
        polish_starts=int(o.get("polish_starts", 5)))


def _header(cfg: Dict, modo: str, n_stages) -> None:
    from ..parallel.hardware import detect_hardware
    h = detect_hardware()
    gpu = (h["cupy"]["gpu_name"] if h["cupy"]["available"] else "none")
    log.info("Mode              : %s", modo)
    log.info("Requested backend : %s", cfg["parallel"]["backend"])
    log.info("GPU               : %s", gpu)
    log.info("CPU workers       : %s", cfg["parallel"]["workers"] or
             max(1, (h["logical_cores"] or 2) - 1))
    log.info("Number of stages  : %s", n_stages)
    log.info("Optimization      : PSO (%s particles × %s iterations, %s runs)",
             cfg["optimization"]["particles"],
             cfg["optimization"]["iterations"], cfg["optimization"]["runs"])
    log.info("Precision         : %s", cfg["parallel"]["precision"])


def _progress_logger(n_stages: int, total_runs: int, iters: int):
    t0 = [time.perf_counter()]
    atual = [-1]

    def cb(run, it, best, x):
        if run != atual[0]:
            atual[0] = run
            t0[0] = time.perf_counter()
        if it % 50 == 0 or it == iters:
            log.info("Run %02d/%02d | %d-Wiebe | iteration %4d/%d | best "
                     "%.3e | %.1f s", run + 1, total_runs, n_stages, it,
                     iters, best, time.perf_counter() - t0[0])
        return False
    return cb


def _stages_para_avaliar(cfg: Dict, a):
    from ..core.parameters import as_stages, default_stages
    from ..model import MultiStageWiebe
    if a.model:
        return MultiStageWiebe.load(a.model).stages
    params = cfg["model"].get("parameters")
    if params:
        return as_stages(params)
    g = cfg["grid"]
    return default_stages(int(cfg["model"]["stages"]), float(g["theta_min"]),
                          float(g["theta_max"]), float(cfg["model"]["a_fixed"]))


def _write_fit_outputs(outdir: Path, data, fit_result, cfg, a, show) -> List[Path]:
    from ..io import writers as W
    from ..model import MultiStageWiebe
    from ..plotting.plots import close_all, make_figures, save_figures
    u = cfg["model"]["angle_unit"]
    arquivos = [
        W.write_results_csv(outdir, data.theta, fit_result.stages, data, u),
        W.write_parameters_csv(outdir, fit_result.stages,
                               fit_result.param_stats, u),
        W.write_metrics_csv(outdir, fit_result.metrics),
        W.write_run_statistics_csv(outdir, fit_result),
        W.write_warnings(outdir, fit_result.warnings),
        MultiStageWiebe(stages=fit_result.stages, a_fixed=cfg["model"]["a_fixed"],
                        angle_unit=u).save(outdir / "model.json"),
    ]
    if cfg["output"]["json"]:
        arquivos.append(W.write_json(outdir, fit_result.to_dict()))
    if cfg["output"]["save_plots"] or show:
        th = np.linspace(data.theta.min(), data.theta.max(),
                         max(2000, data.n))
        figs = make_figures(th, fit_result.stages, data, fit_result, u, show)
        if cfg["output"]["save_plots"]:
            arquivos += save_figures(figs, outdir / "plots")
        if not show:
            close_all(figs)
    return arquivos


def _print_fit(r) -> None:
    log.info("")
    log.info("Melhor ajuste (%d-Wiebe) — backend: %s — %.1f s",
             r.settings.n_stages, r.backend, r.elapsed_s)
    log.info("  %-6s %10s %10s %10s %8s %8s", "stage", "beta", "theta0",
             "duration", "m", "a")
    for j, s in enumerate(r.stages, start=1):
        log.info("  %-6d %10.4f %10.4f %10.4f %8.4f %8.4f", j, s.beta,
                 s.theta0, s.duration, s.m, s.a)
    o = r.objective_stats
    log.info("  objetivo (%s): best %.4e | mean %.4e | std %.2e | median "
             "%.4e | worst %.4e  (%d runs)", r.spec.metric, o["best"],
             o["mean"], o["std"], o["median"], o["worst"], o["runs"])
    for serie, m in r.metrics.items():
        log.info("  %s: RMSE %.4e  MAE %.4e  SEE %.4e  R² %.6f  AIC %.1f  "
                 "BIC %.1f  DW %.2f", serie, m["rmse"], m["mae"], m["see"],
                 m["r2"], m["aic"], m["bic"], m["durbin_watson"])
    _resumo_avisos(r.warnings)


def _resumo_avisos(avisos, prefixo: str = "", maximo: int = 5) -> None:
    for w in avisos[:maximo]:
        log.warning("%s%s", prefixo, w)
    if len(avisos) > maximo:
        log.warning("%s... e mais %d avisos (lista completa em warnings.txt)",
                    prefixo, len(avisos) - maximo)


def _abrir_gui() -> int:
    """Inicia `streamlit run` com o app da GUI (bloqueia até fechar)."""
    import importlib.util
    import subprocess
    if importlib.util.find_spec("streamlit") is None:
        print("ERRO: a GUI requer Streamlit: pip install -e \".[gui]\"",
              file=sys.stderr)
        return EXIT_USO
    app = Path(__file__).resolve().parents[1] / "gui" / "app.py"
    return subprocess.call([sys.executable, "-m", "streamlit", "run", str(app)])


def main(argv: Optional[List[str]] = None) -> None:
    sys.exit(_main(argv))


def _main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    a = parser.parse_args(argv)
    if a.help_model:
        print(HELP_MODEL)
        return EXIT_OK
    if a.help_examples:
        print(HELP_EXAMPLES)
        return EXIT_OK
    if a.gui:
        return _abrir_gui()
    _setup_logging(a)
    from ..core.validation import DataError
    from ..io.config import ConfigError, resolve
    try:
        cfg = resolve(a.config, _cli_overrides(a))
        return _dispatch(a, cfg)
    except (DataError, ConfigError, ValueError, FileNotFoundError) as e:
        log.error("ERRO: %s", e)
        return EXIT_USO
    except KeyboardInterrupt:
        log.error("Interrompido pelo usuário.")
        return EXIT_ERR
    except Exception as e:                              # noqa: BLE001
        if a.debug:
            raise
        log.error("ERRO inesperado (%s): %s — use --debug para detalhes.",
                  type(e).__name__, e)
        return EXIT_ERR


def _dispatch(a, cfg: Dict) -> int:
    from ..io import writers as W
    from ..io.readers import read_data, theta_grid
    from ..parallel.hardware import hardware_report

    if a.devices:
        from ..parallel.backend import available_backends
        print(hardware_report())
        print(f"Backends disponíveis: {', '.join(available_backends())}")
        return EXIT_OK

    outdir = Path(cfg["output"]["directory"])
    workers = cfg["parallel"]["workers"]

    if a.benchmark or a.benchmark_full:
        from ..benchmark import run_benchmark
        log.info(hardware_report())
        W.prepare_outdir(outdir)
        run_benchmark(int(cfg["model"]["stages"]), a.benchmark_full,
                      workers=workers or None, csv_path=outdir / "benchmark.csv",
                      log=log.info)
        log.info("Benchmark gravado em %s", outdir / "benchmark.csv")
        return EXIT_OK

    compare = cfg["comparison"]["stages"] if a.compare_stages else None
    u = cfg["model"]["angle_unit"]
    data = read_data(a.input, u) if a.input else None
    if data is not None:
        for w in data.warnings:
            log.warning("WARNING: %s", w)
    show = bool(a.plot)

    # --------------------------------------------------------- comparação
    if compare:
        from ..optimization.compare import compare_stages
        from ..plotting.plots import comparison_figure, save_figures
        if data is None:
            raise ValueError("--compare-stages requer --input.")
        if a.verbose:
            _header(cfg, "compare-stages", compare)
        W.prepare_outdir(outdir)
        base = _settings(cfg, int(compare[0]))
        res = compare_stages(data, compare, base,
                             int(cfg["comparison"]["cv_folds"]),
                             float(cfg["comparison"]["cv_tol"]))
        W.write_comparison_csv(outdir, res["table"])
        for N, r in res["results"].items():
            sub = W.prepare_outdir(outdir / f"N{N}")
            _write_fit_outputs(sub, data, r, cfg, a, False)
        W.write_configuration(outdir, cfg)
        if cfg["output"]["json"]:
            W.write_json(outdir, {
                "table": res["table"], "recommended": res["recommended"],
                "reason": res["reason"],
                "fits": {str(N): r.to_dict() for N, r in res["results"].items()}},
                "comparison.json")
        _print_comparison(res)
        if cfg["output"]["save_plots"] or show:
            f = comparison_figure(res["table"], show)
            if cfg["output"]["save_plots"]:
                save_figures({"comparison": f}, outdir / "plots")
            if show:
                import matplotlib.pyplot as plt
                plt.show()
        log.info("Resultados em %s", outdir.resolve())
        return EXIT_OK

    # --------------------------------------------------------------- ajuste
    if a.optimize:
        from ..optimization.fit import fit
        if data is None:
            raise ValueError("--optimize requer --input.")
        N = int(cfg["model"]["stages"])
        s = _settings(cfg, N)
        if a.verbose:
            _header(cfg, "optimize", N)
        prog = (_progress_logger(N, s.runs, s.iterations) if a.verbose
                else None)
        r = fit(data, s, progress=prog)
        W.prepare_outdir(outdir)
        cfg_usada = dict(cfg)
        cfg_usada["resolved"] = {"backend": r.backend,
                                 "fit_target": r.spec.fit_target,
                                 "parameter_names": r.param.names}
        W.write_configuration(outdir, cfg_usada)
        _write_fit_outputs(outdir, data, r, cfg, a, show)
        _print_fit(r)
        if show:
            import matplotlib.pyplot as plt
            plt.show()
        log.info("Resultados em %s", outdir.resolve())
        return EXIT_OK

    # ------------------------------------------------------------ avaliação
    from ..core.parameters import validate_stages
    from ..optimization.objective import fit_metrics
    from ..plotting.plots import close_all, make_figures, save_figures
    stages = _stages_para_avaliar(cfg, a)
    erros = validate_stages(stages)
    if erros:
        raise ValueError("; ".join(erros))
    g = cfg["grid"]
    th = (data.theta if data is not None else
          theta_grid(float(g["theta_min"]), float(g["theta_max"]),
                     float(g["theta_step"])))
    if a.verbose:
        _header(cfg, "evaluate", len(stages))
    W.prepare_outdir(outdir)
    W.write_results_csv(outdir, th, stages, data, u)
    W.write_parameters_csv(outdir, stages, None, u)
    if data is not None:
        from ..core.core import multistage_wiebe
        from ..core.derivatives import multistage_wiebe_derivative
        k = 4 * len(stages) - 1
        met = {}
        if data.xb is not None:
            met["xb"] = fit_metrics(data.xb, multistage_wiebe(th, stages), k)
        if data.dxb is not None:
            met["dxb"] = fit_metrics(data.dxb,
                                     multistage_wiebe_derivative(th, stages), k)
        W.write_metrics_csv(outdir, met)
    W.write_configuration(outdir, cfg)
    from ..model import MultiStageWiebe
    MultiStageWiebe(stages=stages, angle_unit=u).save(outdir / "model.json")
    log.info("Modelo %d-Wiebe avaliado em %d pontos (θ = %g … %g %s).",
             len(stages), th.size, th[0], th[-1], u)
    for j, s in enumerate(stages, start=1):
        log.info("  estágio %d: %s", j, s.to_dict())
    if cfg["output"]["save_plots"] or show:
        grade = (np.linspace(th.min(), th.max(), max(2000, th.size))
                 if data is not None else th)
        figs = make_figures(grade, stages, data, None, u, show)
        if cfg["output"]["save_plots"]:
            save_figures(figs, outdir / "plots")
        if show:
            import matplotlib.pyplot as plt
            plt.show()
        else:
            close_all(figs)
    log.info("Resultados em %s", outdir.resolve())
    return EXIT_OK


def _print_comparison(res: Dict) -> None:
    log.info("")
    log.info("%3s %4s %11s %11s %11s %9s %10s %10s %11s %6s %5s %8s", "N", "k",
             "RMSE", "MAE", "SEE", "R²", "ΔAIC", "ΔBIC", "CV RMSE", "DW",
             "warn", "tempo")
    for l in res["table"]:
        log.info("%3d %4d %11.4e %11.4e %11.4e %9.6f %10.1f %10.1f %11.4e "
                 "%6.2f %5d %7.1fs", l["n_stages"], l["k"], l["rmse"],
                 l["mae"], l["see"], l["r2"], l["delta_aic"], l["delta_bic"],
                 l["cv_rmse"], l["durbin_watson"], l["n_warnings"],
                 l["time_s"])
    log.info("")
    log.info("Modelo recomendado: %d-Wiebe — %s.", res["recommended"],
             res["reason"])
    log.info("O menor RMSE de treino NÃO é usado sozinho como critério "
             "(ver --help-model).")
    for N, r in res["results"].items():
        _resumo_avisos(r.warnings, f"[N={N}] ", 3)
