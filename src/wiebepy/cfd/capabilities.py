# -*- coding: utf-8 -*-
"""
capabilities.py — Diagnóstico do ambiente CFD (``wiebepy cfd doctor``).

Verifica, sem downloads e sem detecção pesada:
  • plataforma (Windows + WSL2 / Linux nativo);
  • distribuições WSL2 disponíveis;
  • instalações OpenFOAM (distribuição, versão, foamRun, gcc, mpirun).

Além de LOCALIZAR o solver, o doctor CONECTA: ``connect_openfoam``
verifica que o foamRun detectado executa de verdade (probe ``-help``)
e grava a conexão (distro + root + caminhos) em
``~/.wiebepy/cfd_env.json`` — é essa conexão que a GUI e a CLI usam
como padrão de distribuição, sem o usuário recopiar "Ubuntu-22.04".

O resultado orienta o usuário mas nunca impede o uso do restante do
wiebepy. Executar o doctor é seguro: roda apenas ls/source/which/-help
dentro do WSL.
"""
from __future__ import annotations

import json
import os
import platform
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .wsl import (WslError, RUN_TIMEOUT_PROBE, detect_openfoam,
                  list_distros, on_windows, run_wsl, wsl_available)

# estado da conexão persistida (máquina, não projeto); WIEBEPY_CFD_ENV
# sobrescreve o caminho (testes usam parâmetro/tmp)
ESTADO_PADRAO = Path.home() / ".wiebepy" / "cfd_env.json"


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
        conn = load_connection()
        if conn:
            L.append(f"Conexão ativa       : distro '{conn.get('distro')}' "
                     f"— OpenFOAM {conn.get('version') or '?'} em "
                     f"{conn.get('root')} (foamRun: {conn.get('foamRun')})")
        else:
            L.append("Conexão             : nenhuma — use "
                     "'Conectar OpenFOAM ao código' (GUI) ou "
                     "'wiebepy cfd doctor --connect'")
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


def estado_path(state_file: Optional[str] = None) -> Path:
    """Arquivo de estado da conexão (parâmetro > env > ~/.wiebepy)."""
    if state_file is not None:
        return Path(state_file)
    env = os.environ.get("WIEBEPY_CFD_ENV")
    if env:
        return Path(env)
    return ESTADO_PADRAO


def verify_install(inst: Dict, distro: Optional[str] = None) -> Tuple[bool, str]:
    """Verifica que o foamRun detectado EXECUTA (probe leve: ``-help``).

    A detecção por ls/source pode achar um diretório quebrado; a conexão
    só é gravada com o foamRun respondendo.
    """
    root = inst.get("root") or ""
    # ATENÇÃO: `foamRun -help` abre com uma linha VAZIA — não usar
    # `head -1` (engole o "Usage: foamRun"; registrado na 1ª conexão)
    script = (f'source "{root}/etc/bashrc" 2>/dev/null || true; '
              'command -v foamRun >/dev/null && foamRun -help 2>&1')
    try:
        code, out, err = run_wsl(distro or inst.get("distro"), script,
                                 timeout=RUN_TIMEOUT_PROBE)
    except WslError as e:
        return False, str(e)
    saida = (out + err).strip()
    if code == 0 and "Usage: foamRun" in saida:
        primeira = next(l for l in out.splitlines() if l.strip())
        return True, primeira.strip()
    return False, f"foamRun não respondeu (rc={code}): {saida[:160]}"


def connect_openfoam(distro: Optional[str] = None,
                     state_file: Optional[str] = None,
                     verify: bool = True) -> Tuple[Optional[Dict], List[str]]:
    """Detecta, verifica e PERSISTE a conexão com uma instalação OpenFOAM.

    Procura primeiro na ``distro`` pedida; sem instalação lá (ou sem
    distro pedida), usa a melhor instalação de qualquer distro. Com
    ``verify``, exige que o foamRun responda a ``-help`` antes de
    conectar. A conexão é gravada em ``estado_path(state_file)``.

    Retorna (conexao|None, mensagens) — conexao é o dict da instalação
    com ``distro`` e ``connected_at``; nunca levanta por ambiente
    ausente (isso é diagnóstico, não erro fatal).
    """
    msgs: List[str] = []
    rep = doctor()
    inst: Optional[Dict] = None
    if distro:
        for d in rep.distros:
            if d["name"] == distro and d["openfoam"]:
                inst = d["openfoam"][0]
                break
        if inst is None:
            msgs.append(f"nenhuma instalação OpenFOAM na distro "
                        f"'{distro}' — usando a melhor encontrada")
    if inst is None:
        inst = rep.best()
    if inst is None:
        return None, msgs + [
            "nenhuma instalação OpenFOAM encontrada — ver "
            "docs/cfd/install.md"]
    if verify:
        ok, detalhe = verify_install(inst)
        if not ok:
            return None, msgs + [f"instalação detectada não executa: "
                                 f"{detalhe}"]
        msgs.append(f"foamRun verificado: {detalhe}")
    conn = dict(inst)
    conn["connected_at"] = datetime.now(timezone.utc).isoformat(
        timespec="seconds")
    p = estado_path(state_file)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(conn, ensure_ascii=False, indent=2),
                     encoding="utf-8")
    except OSError as e:
        return conn, msgs + [f"AVISO: conexão detectada mas não gravada "
                             f"em {p}: {e}"]
    msgs.append(f"conexão gravada em {p}")
    return conn, msgs


def load_connection(state_file: Optional[str] = None) -> Optional[Dict]:
    """Conexão persistida (dict) ou None — leitura barata e à prova de
    arquivo corrompido; nunca lança."""
    p = estado_path(state_file)
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if isinstance(d, dict) and d.get("foamRun") and d.get("distro"):
        return d
    return None


__all__ = ["EnvironmentReport", "doctor", "connect_openfoam",
           "verify_install", "load_connection", "estado_path"]