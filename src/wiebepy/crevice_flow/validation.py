# -*- coding: utf-8 -*-
"""
validation.py — Validação estrutural do caso de fresta (antes de rodar).

Escopo: arquivos obrigatórios presentes, config do caso coerente com o
módulo, BCs da câmara presentes e nenhuma feature proibida no nível
submodelo (sem fvModels, sem química — o calor prescrito de câmara e o
reativo nunca se misturam com este domínio). A checagem geométrica/numérica
fina (blockMesh/checkMesh) é feita na execução, com logs no caso.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

import yaml

from ..cfd.config import CaseState, read_state, write_state

OBRIGATORIOS = (
    "system/controlDict", "system/fvSchemes", "system/fvSolution",
    "system/blockMeshDict", "system/topoSetDict",
    "constant/physicalProperties", "constant/momentumTransport",
    "case_config.yaml",
)


def validate_case(case_dir, set_validated: bool = True
                  ) -> Tuple[bool, List[str], List[str]]:
    """Valida o caso de fresta. Retorna (ok, erros, avisos); em sucesso
    e ``set_validated``, marca VALIDATED."""
    case_dir = Path(case_dir)
    erros: List[str] = []
    avisos: List[str] = []
    state = read_state(case_dir)

    if state == CaseState.NOT_CONFIGURED:
        erros.append("Caso não preparado — execute o prepare do "
                     "crevice_flow.")
        return False, erros, avisos
    if state == CaseState.RUNNING and (case_dir / ".run.lock").exists():
        erros.append("Caso em execução — cancele ou aguarde antes de "
                     "validar novamente.")
        return False, erros, avisos

    for rel in OBRIGATORIOS:
        if not (case_dir / rel).exists():
            erros.append(f"Arquivo ausente no caso: {rel}")

    cfg: dict = {}
    yml = case_dir / "case_config.yaml"
    if yml.exists():
        try:
            cfg = yaml.safe_load(yml.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as e:
            erros.append(f"case_config.yaml inválido: {e}")

    if cfg and cfg.get("modulo") != "wiebepy.crevice_flow":
        erros.append("O case_config.yaml não é de um caso crevice_flow "
                     f"(modulo = {cfg.get('modulo')!r}).")

    # nível submodelo: NENHUM fvModels/chemisty — a câmara não tem fonte
    # aqui e a fresta não queima
    for proibido in ("constant/fvModels", "constant/chemistryProperties",
                     "constant/reactions"):
        if (case_dir / proibido).exists():
            erros.append(f"Arquivo proibido no nível submodelo: {proibido} "
                         "(sem fonte de calor e sem química na fresta).")

    # campos iniciais p/T/U no diretório de tempo inicial
    if not _dir_campos(case_dir):
        erros.append("Campos iniciais p/T/U ausentes (diretório do tempo "
                     "inicial).")

    # BC da câmara deve existir em p
    pfile = _dir_campos(case_dir)
    if pfile is not None:
        texto = (case_dir / pfile / "p").read_text(
            encoding="utf-8", errors="replace")
        if "chamber" not in texto:
            erros.append("BC da câmara ausente no campo p (patch chamber).")

    if erros:
        return False, erros, avisos
    if set_validated:
        write_state(case_dir, CaseState.VALIDATED)
    return True, erros, avisos


def _dir_campos(case_dir: Path) -> Optional[str]:
    """Diretório de tempo inicial com os 3 campos (0, ou latestTime se
    startFrom latestTime após execução interrompida)."""
    for nome in ("0",):
        d = case_dir / nome
        if d.is_dir() and all((d / f).exists() for f in ("p", "T", "U")):
            return nome
    return None


__all__ = ["validate_case", "OBRIGATORIOS"]