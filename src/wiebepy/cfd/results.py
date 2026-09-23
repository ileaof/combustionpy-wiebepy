# -*- coding: utf-8 -*-
"""
results.py — Leitura de resultados do caso OpenFOAM e curvas de
comparação (§16).

Fontes:
  • postProcessing/gasAvg/…     → médias volumétricas de p [Pa], T [K],
                                  rho [kg/m³];
  • postProcessing/gasIntegral/ → integral volumétrica de rho (massa);
  • postProcessing/gasMinMax/   → min/max de T e p;
  • postProcessing/wallHeatFlux/→ fluxo térmico integral por parede [W];
  • diretórios de tempo <case>/<time>/ → campos 3D (p, T, U, rho) para
                                  pós-processamento externo (formato
                                  nativo do solver; exportação VTK via
                                  foamToVTK, opcional).

Convenções:
  • o "tempo" do OpenFOAM é o ângulo de manivela (CA, graus) —
    userTime engine; t físico [s] = CA/(6·RPM);
  • pressão média volumétrica do cilindro ≠ pressão em sonda ≠ pressão
    medida — distinguimos explicitamente (§16);
  • volume V(CA) vem da cinemática biela-manivela (mesma equação do
    0-D), consistente com o movimento imposto ao pistão.

``check_completion`` distingue "processo terminou" de "simulação
convergiu/cobriu a janela": exige 'End' no log do foamRun E último CA
registrado ≥ fim da janela.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np


def _read_dat(path: Path) -> Tuple[np.ndarray, List[str]]:
    """Lê um .dat do postProcessing (comentários '#'): (matriz, colunas)."""
    cols: List[str] = []
    rows: List[List[float]] = []
    for line in path.read_text(encoding="utf-8", errors="replace") \
            .splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("#"):
            # o cabeçalho de colunas é o comentário que contém "Time"
            cand = [c for c in s.lstrip("#").split() if c]
            if "Time" in cand:
                cols = cand
            continue
        try:
            rows.append([float(x) for x in s.split()])
        except ValueError:
            continue
    if not rows:
        return np.empty((0, 0)), cols
    return np.array(rows), cols


def _read_wall_heat_flux(path: Path) -> Tuple[np.ndarray, List[str]]:
    """Lê o wallHeatFlux.dat (uma linha por parede e tempo):

        # Time  patch  min  max  Q [W]  q [W/m^2]

    Retorna (matriz [Time, Q_piston, Q_head, Q_liner], colunas) com a
    potência INTEGRAL por parede (Q [W]) na ordem dos patches lidos.
    """
    ordem: List[str] = []
    dados: Dict[float, Dict[str, float]] = {}
    for line in path.read_text(encoding="utf-8", errors="replace") \
            .splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        parts = s.split()
        if len(parts) < 5:
            continue
        try:
            t = float(parts[0])
            q_w = float(parts[4])          # Q [W] (integral no patch)
        except ValueError:
            continue
        patch = parts[1]
        if patch not in ordem:
            ordem.append(patch)
        dados.setdefault(t, {})[patch] = q_w
    if not dados:
        return np.empty((0, 0)), []
    tempos = sorted(dados)
    mat = np.array([[t] + [dados[t].get(p, 0.0) for p in ordem]
                    for t in tempos])
    return mat, ["Time"] + ordem


def _fo_dat(case_dir: Path, fo: str) -> Optional[Path]:
    base = Path(case_dir) / "postProcessing" / fo
    if not base.is_dir():
        return None
    # diretório de startTime mais recente
    subs = sorted([p for p in base.iterdir() if p.is_dir()],
                  key=lambda p: p.name)
    for sub in reversed(subs):
        for nome in ("volFieldValue.dat", "fieldMinMax.dat",
                     "wallHeatFlux.dat", "volFieldValue.dat"):
            f = sub / nome
            if f.exists():
                return f
        for f in sorted(sub.glob("*.dat")):
            return f
    return None


def _series(case_dir: Path, fo: str) -> Tuple[np.ndarray, List[str]]:
    f = _fo_dat(case_dir, fo)
    if f is None:
        return np.empty((0, 0)), []
    return _read_dat(f)


def physical_time_s(ca_deg: np.ndarray, rpm: float) -> np.ndarray:
    """CA [grau] → t [s]: t = CA/(6·RPM) (conversão explícita §7)."""
    return np.asarray(ca_deg, dtype=float) / (6.0 * rpm)


def read_results(case_dir, engine=None, stages=None) -> Dict:
    """Extrai as curvas do caso. ``engine`` (EngineConfig) dá rotação,
    geometria e volume; ``stages`` (opcional) permite recomputar a fonte
    Wiebe prescrita para comparação."""
    case_dir = Path(case_dir)
    out: Dict = {}

    avg, cols_avg = _series(case_dir, "gasAvg")
    integ, _ = _series(case_dir, "gasIntegral")
    mn, cols_mn = _series(case_dir, "gasMin")
    mx, cols_mx = _series(case_dir, "gasMax")
    # R1 (multicomponente): integrais volumétricas de ρ·Yi — massa de
    # cada espécie ao longo do ciclo (colunas rhoN2/rhoO2 etc.)
    spm, cols_spm = _series(case_dir, "specieMass")
    f_whf = _fo_dat(case_dir, "wallHeatFlux")
    whf, cols_whf = _read_wall_heat_flux(f_whf) if f_whf else \
        (np.empty((0, 0)), [])

    def col(mat, cols, key):
        if not cols or key not in cols or mat.size == 0:
            return np.empty(0)
        return mat[:, cols.index(key)]

    # médias volumétricas — CA é a coluna Time
    if avg.size:
        ca = avg[:, cols_avg.index("Time")]
        out["ca_deg"] = ca
        out["t_s"] = physical_time_s(ca, engine.rpm if engine else 1.0)
        for campo in ("p", "T", "rho"):
            k = f"volAverage({campo})"
            if k in cols_avg:
                out[f"{campo}_mean"] = avg[:, cols_avg.index(k)]
        out["p_mean_kPa"] = (out["p_mean"] / 1e3
                             if "p_mean" in out else np.empty(0))
    if integ.size:
        out["mass_kg"] = integ[:, -1]   # volIntegrate(rho)
    if spm.size and cols_spm:
        # R1: massa de cada espécie [kg] — colunas volIntegrate(rho<SP>)
        out["specie_mass_kg"] = {}
        for k in cols_spm:
            if k.startswith("volIntegrate(rho") and k.endswith(")"):
                sp = k[len("volIntegrate(rho"):-1]
                out["specie_mass_kg"][sp] = spm[:, cols_spm.index(k)]
    if mn.size and cols_mn and mx.size and cols_mx:
        for nome, chave, mat, cols in (
                ("T_min", "min(T)", mn, cols_mn),
                ("T_max", "max(T)", mx, cols_mx),
                ("p_min", "min(p)", mn, cols_mn),
                ("p_max", "max(p)", mx, cols_mx)):
            if chave in cols:
                out[nome] = mat[:, cols.index(chave)]
        if "Time" in cols_mn and "ca_deg" not in out:
            out["ca_deg"] = mn[:, cols_mn.index("Time")]
            out["t_s"] = physical_time_s(out["ca_deg"],
                                         engine.rpm if engine else 1.0)
    if whf.size and cols_whf:
        out["wall_heat_flux_cols"] = cols_whf
        out["wall_heat_flux_W"] = whf        # Time + potência por parede [W]
    # volume do cilindro em cada CA (cinemática do 0-D — mesma equação)
    if "ca_deg" in out and engine is not None:
        from ..pressure.engine import volume
        V, _, _ = volume(np.radians(out["ca_deg"]), engine.Rc, engine)
        out["V_m3"] = V
        # trabalho indicado na janela: ∫p dV (trapézio; p em Pa → J)
        if "p_mean" in out:
            p = out["p_mean"]
            out["indicated_work_J"] = float(np.trapezoid(p, V)) \
                if hasattr(np, "trapezoid") else float(np.trapz(p, V))

    # calor nas paredes: potência total = soma das paredes; acumulado
    if "wall_heat_flux_W" in out:
        whf = out["wall_heat_flux_W"]
        pot = whf[:, 1:].sum(axis=1)
        ca = whf[:, 0]
        out["wall_loss_W"] = pot
        out["wall_loss_ca_deg"] = ca
        dt_s = physical_time_s(np.gradient(ca), engine.rpm if engine
                               else 1.0)
        out["wall_loss_J"] = float(np.trapezoid(pot, physical_time_s(
            ca, engine.rpm if engine else 1.0))) if ca.size > 1 else 0.0

    # fonte Wiebe prescrita (para comparação no relatório)
    if engine is not None and stages is not None and out.get("ca_deg") \
            is not None and len(out.get("ca_deg", [])):
        from .sources.wiebe_heat_release import qdot_time_series
        ca = out["ca_deg"]
        th = np.linspace(math.radians(float(np.min(ca))),
                         math.radians(float(np.max(ca))), 800)
        t, q = qdot_time_series(th, stages, engine.m_fuel, engine.LHV,
                                "rad", engine.rpm)
        out["prescribed_ca_deg"] = np.degrees(th)
        out["prescribed_Q_W"] = q
        out["prescribed_Q_J"] = float(np.trapezoid(q, t)) \
            if hasattr(np, "trapezoid") else float(np.trapz(q, t))
    return out


def check_completion(case_dir, cfg) -> Tuple[bool, str]:
    """'processo terminou' ≠ 'simulação concluída': exige log 'End' e
    último CA registrado ≥ fim da janela (tolerância de gravação)."""
    case_dir = Path(case_dir)
    log = case_dir / "logs" / "foamRun.log"
    if not log.exists():
        return False, "Log do foamRun não encontrado (logs/foamRun.log)."
    texto = log.read_text(encoding="utf-8", errors="replace")
    if "End" not in texto:
        return False, ("O solver terminou sem a mensagem final 'End' — "
                       "execução provavelmente interrompida.")
    fim = float(cfg.interval_end)
    avg, cols = _series(case_dir, "gasAvg")
    if avg.size == 0:
        return False, "Sem série temporal em postProcessing (gasAvg)."
    ca = avg[:, cols.index("Time")]
    ultimo = float(ca[-1])
    if ultimo < fim - max(1.0, 0.02 * abs(fim)):
        return False, (f"Último ponto registrado (CA {ultimo:.2f}°) não "
                       f"cobre o fim da janela ({fim:.2f}°).")
    return True, "Janela simulada coberta e solver encerrado com 'End'."


def time_directories(case_dir) -> List[str]:
    """Diretórios de tempo com campos 3D (formato nativo do solver)."""
    case_dir = Path(case_dir)
    tempos = []
    for p in case_dir.iterdir():
        if p.is_dir():
            try:
                float(p.name)
                tempos.append(p.name)
            except ValueError:
                pass
    return sorted(tempos, key=lambda s: float(s))


def export_vtk(case_dir) -> Optional[Path]:
    """Exporta os campos para VTK (foamToVTK) — opcional, requer solver."""
    import subprocess
    from .wsl import detect_openfoam, list_distros, on_windows
    case_dir = Path(case_dir)
    if on_windows():
        distros = list_distros()
        insts = detect_openfoam(distros[0]) if distros else []
        if not insts or not insts[0].get("foamRun"):
            return None
        argv = ["wsl.exe", "-d", insts[0].get("distro") or distros[0],
                "--cd", str(case_dir), "--", "bash", "-lc",
                f"source {insts[0]['root']}/etc/bashrc && foamToVTK"]
        subprocess.run(argv, capture_output=True, timeout=600)
    else:
        insts = detect_openfoam(None)
        if not insts or not insts[0].get("foamRun"):
            return None
        subprocess.run(["bash", "-lc",
                        f"source {insts[0]['root']}/etc/bashrc && "
                        f"cd '{case_dir}' && foamToVTK"],
                       capture_output=True, timeout=600)
    vtk = case_dir / "VTK"
    return vtk if vtk.exists() else None


__all__ = ["read_results", "check_completion", "time_directories",
           "export_vtk", "physical_time_s"]