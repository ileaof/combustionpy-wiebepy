# -*- coding: utf-8 -*-
"""Transporte macOS (VM Multipass) e Linux nativo do módulo CFD.

Sem Multipass/VM reais: o subprocess é substituído por fakes, então os
testes rodam em qualquer plataforma (Windows, Linux, macOS Intel/Silicon).
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from wiebepy.cfd import multipass as mp
from wiebepy.cfd import wsl


class _P:
    def __init__(self, rc=0, out=b"", err=b""):
        self.returncode, self.stdout, self.stderr = rc, out, err


def _fake_macos(monkeypatch, vms=("openfoam",), mounts=None, chamadas=None):
    """macOS com multipass falso; registra (argv, stdin) em ``chamadas``."""
    mounts = mounts or {}
    real_run = subprocess.run
    monkeypatch.setattr(mp, "on_macos", lambda: True)
    monkeypatch.setattr(mp, "multipass_exe", lambda: "/usr/local/bin/multipass")

    def run(argv, input=None, **kw):
        if argv[0] != "/usr/local/bin/multipass":   # ex.: uname do platform
            return real_run(argv, input=input, **kw)
        if chamadas is not None:
            chamadas.append((argv, input))
        if argv[1:2] == ["list"]:
            return _P(out=json.dumps({"list": [
                {"name": n, "state": "Running"} for n in vms] + [
                {"name": "parada", "state": "Stopped"}]}).encode())
        if argv[1:2] == ["info"]:
            vm = argv[2]
            return _P(out=json.dumps({"info": {vm: {"mounts": {
                alvo: {"source_path": src} for src, alvo in mounts.items()
            }}}}).encode())
        if argv[1:2] == ["exec"]:
            return _P(out=b"OF|/home/u/dev/OpenFOAM-14|14|/x/foamRun|"
                          b"/usr/bin/gcc|/usr/bin/mpirun\n")
        raise AssertionError(argv)
    monkeypatch.setattr(mp.subprocess, "run", run)


def test_map_path_montagem_mais_especifica(tmp_path):
    proj = tmp_path / "Projects"
    caso = proj / "wiebepy" / "results" / "cfd" / "c1"
    caso.mkdir(parents=True)
    # alvos são caminhos POSIX da VM (o teste roda também no Windows)
    pares = [(str(proj), "/mnt/proj"),
             (str(proj / "wiebepy"), "/vm/wiebepy")]
    assert mp.map_path(caso, pares) == "/vm/wiebepy/results/cfd/c1"
    assert mp.map_path(proj / "x", pares) == "/mnt/proj/x"
    assert mp.map_path(tmp_path / "fora", pares) is None


def test_list_vms_so_em_execucao(monkeypatch):
    _fake_macos(monkeypatch, vms=("openfoam", "outra"))
    assert mp.list_vms() == ["openfoam", "outra"]
    assert wsl.list_distros() == ["openfoam", "outra"]


def test_vm_path_sem_montagem_explica_como_montar(monkeypatch, tmp_path):
    _fake_macos(monkeypatch, mounts={})
    with pytest.raises(mp.MultipassError, match="multipass mount"):
        mp.vm_path("openfoam", tmp_path)


def test_run_wsl_no_macos_usa_multipass_e_entra_no_caso(monkeypatch, tmp_path):
    chamadas = []
    _fake_macos(monkeypatch, mounts={str(tmp_path): "/mnt/casos"},
                chamadas=chamadas)
    code, out, _ = wsl.run_wsl("openfoam", "echo oi", cwd_win=tmp_path / "c")
    argv, stdin = chamadas[-1]
    assert argv == ["/usr/local/bin/multipass", "exec", "openfoam", "--",
                    "bash", "-l"]
    assert stdin.decode().startswith("cd /mnt/casos/c || exit 97\n")
    assert stdin.decode().rstrip().endswith("echo oi")
    assert code == 0


def test_detect_openfoam_no_macos(monkeypatch):
    _fake_macos(monkeypatch)
    insts = wsl.detect_openfoam("openfoam")
    assert insts == [{"root": "/home/u/dev/OpenFOAM-14", "version": "14",
                      "foamRun": "/x/foamRun", "gcc": "/usr/bin/gcc",
                      "mpirun": "/usr/bin/mpirun", "distro": "openfoam"}]


def test_multipass_ausente_vira_wslerror(monkeypatch):
    monkeypatch.setattr(mp, "on_macos", lambda: True)
    monkeypatch.setattr(mp, "multipass_exe", lambda: None)
    with pytest.raises(wsl.WslError, match="Multipass"):
        wsl.run_wsl("openfoam", "true")


def test_doctor_no_macos(monkeypatch):
    from wiebepy.cfd import capabilities as cap
    _fake_macos(monkeypatch)
    monkeypatch.setattr(cap, "on_macos", lambda: True)
    monkeypatch.setattr(cap, "on_windows", lambda: False)
    monkeypatch.setattr(cap, "multipass_available", lambda: True)
    rep = cap.doctor()
    assert rep.macos and rep.multipass_ok
    assert [d["name"] for d in rep.distros] == ["openfoam"]
    assert rep.best()["version"] == "14"
    assert "VM Multipass" in rep.format()


def test_linux_nativo_roda_bash_local(monkeypatch, tmp_path):
    """Linux: run_wsl não exige wsl.exe — executa bash -l local."""
    monkeypatch.setattr(mp, "on_macos", lambda: False)
    monkeypatch.setattr(wsl, "on_windows", lambda: False)
    visto = {}

    def run(argv, input=None, cwd=None, **kw):
        visto.update(argv=argv, cwd=cwd, input=input)
        return _P(out=b"ok\n")
    monkeypatch.setattr(wsl.subprocess, "run", run)
    code, out, _ = wsl.run_wsl(None, "echo ok", cwd_win=tmp_path)
    assert (code, out) == (0, "ok\n")
    assert visto["argv"] == ["bash", "-l"] and visto["cwd"] == str(tmp_path)


def test_cancelamento_so_mata_o_caso():
    """O cancelamento não pode derrubar outras simulações da VM."""
    from wiebepy.cfd.adapters.openfoam import _kill_case_script
    s = _kill_case_script("/casos/meu caso").decode()
    assert "pkill" not in s
    assert "'/casos/meu caso'" in s and "/proc/$p/cwd" in s
