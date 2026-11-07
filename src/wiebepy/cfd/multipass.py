# -*- coding: utf-8 -*-
"""
multipass.py — Execução do solver numa VM Multipass (macOS).

No macOS o OpenFOAM roda numa VM Ubuntu gerida pelo Multipass
(caminho recomendado pela OpenFOAM Foundation para Mac). Este módulo é o
equivalente do ``wsl.py`` do Windows:

  • ``list_vms()``      — VMs em execução (o nome da VM faz o papel da
                           "distro" do WSL na config, na GUI e na conexão);
  • ``run_vm()``        — executa um script bash na VM (via stdin de
                           ``multipass exec VM -- bash -l``);
  • ``vm_path()``       — traduz um caminho do Mac para o caminho dentro
                           da VM, pelas montagens de ``multipass info``.

Funciona igual em Apple Silicon e Intel: o binário ``multipass`` tem a
mesma interface nas duas arquiteturas.

Os casos CFD precisam estar numa pasta do Mac MONTADA na VM. O mais
simples é montar com o mesmo caminho dos dois lados, por exemplo::

    multipass mount ~/Documents/Projects openfoam:/Users/<usuario>/Documents/Projects

Nada aqui é executado no import.
"""
from __future__ import annotations

import json
import shlex
import shutil
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Dict, List, Optional, Tuple

# locais usuais do instalador oficial (pkg) e do Homebrew
_CANDIDATOS = ("/usr/local/bin/multipass", "/opt/homebrew/bin/multipass")


class MultipassError(RuntimeError):
    """Falha ao executar um comando na VM Multipass."""


def on_macos() -> bool:
    return sys.platform == "darwin"


def multipass_exe() -> Optional[str]:
    """Caminho do binário ``multipass`` (PATH primeiro, depois locais
    usuais — a GUI pode ser aberta com PATH reduzido)."""
    exe = shutil.which("multipass")
    if exe:
        return exe
    for c in _CANDIDATOS:
        if Path(c).exists():
            return c
    return None


def multipass_available() -> bool:
    return on_macos() and multipass_exe() is not None


def _exe() -> str:
    exe = multipass_exe()
    if exe is None:
        raise MultipassError(
            "Multipass não encontrado. Instale-o (https://multipass.run) e "
            "crie uma VM Ubuntu com o OpenFOAM — ver docs/cfd/install.md.")
    return exe


def _json(args: List[str], timeout: int = 60) -> Dict:
    try:
        p = subprocess.run([_exe()] + args + ["--format", "json"],
                           capture_output=True, timeout=timeout,
                           stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise MultipassError(f"Falha ao invocar multipass: {e}") from e
    if p.returncode != 0:
        raise MultipassError(
            f"multipass {' '.join(args)} falhou: "
            f"{p.stderr.decode('utf-8', errors='replace').strip()}")
    try:
        return json.loads(p.stdout.decode("utf-8", errors="replace"))
    except ValueError as e:
        raise MultipassError(f"Saída inesperada do multipass: {e}") from e


def list_vms() -> List[str]:
    """VMs Multipass em execução (estado Running)."""
    if not multipass_available():
        return []
    try:
        d = _json(["list"])
    except MultipassError:
        return []
    return [v["name"] for v in d.get("list", [])
            if str(v.get("state", "")).lower() == "running"]


def mounts(vm: str) -> List[Tuple[str, str]]:
    """Montagens da VM como pares (pasta do Mac, pasta na VM)."""
    d = _json(["info", vm])
    info = d.get("info", {}).get(vm, {})
    pares = []
    for alvo, m in (info.get("mounts") or {}).items():
        src = m.get("source_path")
        if src:
            pares.append((src, alvo))
    return pares


def map_path(host_path, pares: List[Tuple[str, str]]) -> Optional[str]:
    """Traduz ``host_path`` pela montagem mais específica; None se o
    caminho não estiver dentro de nenhuma pasta montada."""
    hp = Path(host_path).expanduser().resolve()
    melhor = None
    for src, alvo in pares:
        s = Path(src).expanduser().resolve()
        try:
            rel = hp.relative_to(s)
        except ValueError:
            continue
        if melhor is None or len(s.parts) > melhor[0]:
            melhor = (len(s.parts), str(PurePosixPath(alvo, *rel.parts)))
    return melhor[1] if melhor else None


def vm_path(vm: str, host_path) -> str:
    """Caminho dentro da VM para uma pasta do Mac (exige montagem)."""
    destino = map_path(host_path, mounts(vm))
    if destino is None:
        hp = Path(host_path).expanduser().resolve()
        raise MultipassError(
            f"A pasta {hp} não está montada na VM '{vm}'. Monte uma pasta "
            f"que a contenha, por exemplo:\n"
            f"  multipass mount \"{hp.parent}\" {vm}:\"{hp.parent}\"")
    return destino


def run_vm(vm: Optional[str], script: str, timeout: int = 600,
           cwd_host: Optional[Path] = None) -> "tuple[int, str, str]":
    """Executa ``script`` (bash -l, via stdin) na VM. Com ``cwd_host``,
    entra antes na pasta correspondente dentro da VM."""
    if not multipass_available():
        raise MultipassError("Multipass não disponível nesta máquina.")
    if not vm:
        vms = list_vms()
        if not vms:
            raise MultipassError("Nenhuma VM Multipass em execução "
                                 "(multipass start <vm>).")
        vm = vms[0]
    if cwd_host is not None:
        script = (f"cd {shlex.quote(vm_path(vm, cwd_host))} || exit 97\n"
                  + script)
    try:
        p = subprocess.run(exec_argv(vm), input=script.encode("utf-8"),
                           capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        raise MultipassError(f"Tempo esgotado ({timeout} s) executando na "
                             f"VM {vm}: {script[:120]}") from e
    except OSError as e:
        raise MultipassError(f"Falha ao invocar multipass: {e}") from e
    return (p.returncode, p.stdout.decode("utf-8", errors="replace"),
            p.stderr.decode("utf-8", errors="replace"))


def exec_argv(vm: str) -> List[str]:
    """argv para um ``bash -l`` na VM que lê o script do stdin."""
    return [_exe(), "exec", vm, "--", "bash", "-l"]


__all__ = ["MultipassError", "on_macos", "multipass_exe",
           "multipass_available", "list_vms", "mounts", "map_path",
           "vm_path", "run_vm", "exec_argv"]
