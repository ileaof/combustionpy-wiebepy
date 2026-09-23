# -*- coding: utf-8 -*-
"""
validation.py — Validação do caso CFD antes da execução (§12, §14).

Verifica estaticamente:
  • estado do caso (transição prepared → validated);
  • arquivos obrigatórios do caso OpenFOAM;
  • consistência da configuração efetiva (case_config.yaml);
  • conservação da energia da fonte Wiebe registrada no caso;
  • disponibilidade do solver (adapter.check_runnable).

``validate`` NÃO executa o solver — apenas garante que o caso está
completo e consistente. A verificação física (conservação, malha,
independência) é feita depois com os resultados (results.py) e pela
escada de validação §18.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

from .adapters.base import get_adapter
from .config import CfdConfig, CaseState, read_state, write_state

OBRIGATORIOS = [
    "system/controlDict", "system/fvSchemes", "system/fvSolution",
    "system/blockMeshDict", "constant/physicalProperties",
    "constant/momentumTransport", "case_config.yaml",
]
# campos iniciais ficam no diretório do tempo inicial (userTime engine →
# o nome do diretório é o CA inicial, ex. "-120"; ver case_builder)
CAMPOS_INICIAIS = ("p", "T", "U")


def _dir_campos(case_dir: Path) -> Optional[str]:
    """Diretório de tempo que contém os campos iniciais (ex. '-120')."""
    for d in sorted(case_dir.iterdir()):
        if d.is_dir() and (d / "p").exists() and (d / "T").exists() \
                and (d / "U").exists():
            try:
                float(d.name)
                return d.name
            except ValueError:
                continue
    return None
CONDICIONAIS = {
    "constant/dynamicMeshDict": "caso com pistão móvel",
    "constant/fvModels": "caso com fonte de calor",
    "system/topoSetDict": "fonte em região (cellZone)",
    "system/decomposeParDict": "execução paralela",
}


def validate_case(case_dir, adapter_name: str = "openfoam",
                  distro: Optional[str] = None,
                  set_validated: bool = True) -> Tuple[bool, List[str],
                                                       List[str]]:
    """Valida o caso. Retorna (ok, erros, avisos). Em caso de sucesso e
    ``set_validated``, marca o estado VALIDATED."""
    case_dir = Path(case_dir)
    erros: List[str] = []
    avisos: List[str] = []
    state = read_state(case_dir)

    if state == CaseState.NOT_CONFIGURED:
        erros.append("Caso não preparado — execute `wiebepy cfd prepare`.")
        return False, erros, avisos
    if state == CaseState.RUNNING:
        if (case_dir / ".run.lock").exists():
            erros.append("Caso em execução — cancele ou aguarde antes de "
                         "validar novamente.")
            return False, erros, avisos
        # execução anterior morreu sem atualizar o estado (lock ausente):
        # recupera e segue (o runner faz o mesmo)
        write_state(case_dir, CaseState.FAILED,
                    error="Execução anterior interrompida sem atualizar o "
                          "estado (lock ausente); estado recuperado.")

    # arquivos obrigatórios
    for rel in OBRIGATORIOS:
        if not (case_dir / rel).exists():
            erros.append(f"Arquivo ausente no caso: {rel}")
    tdir = _dir_campos(case_dir)
    if tdir is None:
        erros.append("Campos iniciais p/T/U ausentes (diretório do tempo "
                     "inicial).")
    # condicionais — conforme as features declaradas do caso
    cfg_efetiva: Dict = {}
    yml = case_dir / "case_config.yaml"
    if yml.exists():
        try:
            cfg_efetiva = yaml.safe_load(yml.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as e:
            erros.append(f"case_config.yaml inválido: {e}")
    features = cfg_efetiva.get("features") or {}
    if features.get("moving_piston"):
        if not (case_dir / "constant/dynamicMeshDict").exists():
            erros.append("Caso declara pistão móvel, mas "
                         "constant/dynamicMeshDict está ausente.")
    if features.get("heat_source"):
        if not (case_dir / "constant/fvModels").exists():
            erros.append("Caso declara fonte de calor, mas "
                         "constant/fvModels está ausente.")

    # conservação da energia da fonte
    chk = cfg_efetiva.get("heat_source", {}).get("energy_check") or {}
    if chk:
        if not chk.get("ok", False):
            erros.append("A fonte Wiebe do caso não passa na verificação "
                         "de conservação (∫Q̇dt ≠ m_f·PCI·Δx_b).")
    elif features.get("heat_source"):
        avisos.append("Fonte de calor presente, mas sem verificação de "
                      "energia registrada em case_config.yaml.")

    # decomposeParDict consistente com workers declarado
    dpd = case_dir / "system/decomposeParDict"
    n_workers = cfg_efetiva.get("configuration", {}).get("workers", 1)
    if dpd.exists():
        try:
            texto = dpd.read_text(encoding="utf-8")
            n_sub = int([l.split()[1] for l in texto.splitlines()
                         if l.strip().startswith("numberOfSubdomains")][0])
            if n_sub != int(n_workers):
                erros.append(f"decomposeParDict ({n_sub} subdomínios) "
                             f"≠ workers configurado ({n_workers}).")
        except (IndexError, ValueError):
            erros.append("decomposeParDict sem numberOfSubdomains válido.")

    # solver disponível
    try:
        ad = get_adapter(adapter_name, distro=distro)
        errs = ad.check_runnable()
        erros.extend(errs)
        solver_ok = not errs
    except Exception as e:                              # noqa: BLE001
        solver_ok = False
        erros.append(f"Adapter indisponível: {e}")

    if not erros and set_validated:
        write_state(case_dir, CaseState.VALIDATED,
                    solver_version=cfg_efetiva.get("solver", {}).get("version"))
    return not erros, erros, avisos


def case_summary(case_dir) -> Dict:
    """Resumo legível do caso (para CLI/GUI)."""
    case_dir = Path(case_dir)
    state = read_state(case_dir)
    cfg: Dict = {}
    yml = case_dir / "case_config.yaml"
    if yml.exists():
        try:
            cfg = yaml.safe_load(yml.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            pass
    return {"directory": str(case_dir), "state": state.value,
            "state_label": state.label,
            "solver_version": cfg.get("solver", {}).get("version"),
            "mode": cfg.get("mode"),
            "fuel": (cfg.get("fuel") or {}).get("display"),
            "interval": cfg.get("interval"),
            "moving": bool(cfg.get("motion")),
            "has_heat": (case_dir / "constant/fvModels").exists()}


__all__ = ["validate_case", "case_summary", "CaseState"]