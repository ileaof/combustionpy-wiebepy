# -*- coding: utf-8 -*-
"""
capabilities.py — Diagnóstico do ambiente CFD (``wiebepy cfd doctor``).

Verifica, sem downloads e sem detecção pesada:
  • plataforma (Windows + WSL2 / Linux nativo);
  • distribuições WSL2 disponíveis;
  • instalações OpenFOAM (distribuição, versão, foamRun, gcc, mpirun).

O resultado orienta o usuário mas nunca impede o uso do restante do
wiebepy. Executar o doctor é seguro: roda apenas ls/source/which dentro
do WSL.
"""
from __future__ import annotations

import platform
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .wsl import (WslError, detect_openfoam, list_distros, on_windows,
                  wsl_available)


@dataclass
class EnvironmentReport:
    platform: str
    windows: bool
    wsl_ok: bool
    distros: List[Dict] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @property
    def installations(self) -> List[Dict]:
        return [inst for d in self.distros for inst in d["openfoam"]]

    def best(self) -> Optional[Dict]:
        """Instalação preferida: primeiro foamRun encontrado."""
        return self.installations[0] if self.installations else None

    def to_dict(self) -> Dict:
        return {"platform": self.platform, "windows": self.windows,
                "wsl_ok": self.wsl_ok, "distros": self.distros,
                "errors": self.errors,
                "n_installations": len(self.installations)}

    def format(self) -> str:
        L = [f"Plataforma          : {self.platform}"]
        if self.windows:
            L.append(f"WSL2                : {'disponível' if self.wsl_ok else 'NÃO disponível'}")
        for d in self.distros:
            L.append(f"Distribuição WSL    : {d['name']} — "
                     f"{len(d['openfoam'])} instalação(ões) OpenFOAM")
            for inst in d["openfoam"]:
                L.append(f"  OpenFOAM          : versão {inst['version'] or '?'} "
                         f"em {inst['root']}")
                L.append(f"    foamRun         : {inst['foamRun'] or 'não encontrado'}")
                L.append(f"    gcc             : {inst['gcc'] or 'não encontrado'}")
                L.append(f"    mpirun          : {inst['mpirun'] or 'não encontrado'}")
        if not self.installations:
            L.append("OpenFOAM            : nenhuma instalação encontrada "
                     "— ver docs/cfd/install.md")
        for e in self.errors:
            L.append(f"AVISO: {e}")
        L.append("")
        L.append("Nota: este diagnóstico apenas localiza o solver; a "
                 "validação do caso (wiebepy cfd validate) verifica o "
                 "caso em si antes da execução.")
        return "\n".join(L)


def doctor() -> EnvironmentReport:
    """Sonda o ambiente (seguro: apenas ls/source/which no WSL)."""
    rep = EnvironmentReport(platform=platform.platform(),
                            windows=on_windows(),
                            wsl_ok=wsl_available())
    if on_windows():
        if not rep.wsl_ok:
            rep.errors.append("wsl.exe não encontrado — instale WSL2 com "
                              "uma distribuição Ubuntu e o OpenFOAM "
                              "(docs/cfd/install.md).")
            return rep
        for name in list_distros():
            try:
                insts = detect_openfoam(name)
            except WslError as e:
                rep.errors.append(f"distro {name}: {e}")
                insts = []
            rep.distros.append({"name": name, "openfoam": insts})
    else:
        # Linux nativo: mesma sonda, sem wsl
        try:
            insts = detect_openfoam(None)
        except WslError as e:
            rep.errors.append(str(e))
            insts = []
        rep.distros.append({"name": "linux-nativo", "openfoam": insts})
    return rep


__all__ = ["EnvironmentReport", "doctor"]