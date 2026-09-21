# -*- coding: utf-8 -*-
"""
hardware.py — Detecção de CPU, memória, Numba, CUDA/CuPy e GPU.

Nunca lança exceção: bibliotecas ausentes aparecem como indisponíveis.
psutil é usado se instalado; sem ele, núcleos físicos e RAM vêm de APIs
do sistema (Windows: GlobalMemoryStatusEx/wmic; Linux: /proc).
"""
from __future__ import annotations

import os
import platform
from functools import lru_cache
from typing import Dict, Optional


def _ram_bytes() -> Optional[int]:
    try:
        import psutil
        return int(psutil.virtual_memory().total)
    except ImportError:
        pass
    try:
        if os.name == "nt":
            import ctypes

            class _MS(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong),
                            ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong),
                            ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong),
                            ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong),
                            ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            ms = _MS()
            ms.dwLength = ctypes.sizeof(_MS)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms))
            return int(ms.ullTotalPhys)
        with open("/proc/meminfo") as fh:
            for linha in fh:
                if linha.startswith("MemTotal:"):
                    return int(linha.split()[1]) * 1024
    except Exception:
        pass
    return None


def _physical_cores() -> Optional[int]:
    try:
        import psutil
        return psutil.cpu_count(logical=False)
    except ImportError:
        pass
    try:
        if os.name == "nt":
            import subprocess
            out = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "(Get-CimInstance Win32_Processor | Measure-Object "
                 "-Property NumberOfCores -Sum).Sum"],
                capture_output=True, text=True, timeout=10)
            return int(out.stdout.strip())
        with open("/proc/cpuinfo") as fh:
            ids = {linha.split(":")[1].strip() for linha in fh
                   if linha.startswith("core id")}
        return len(ids) or None
    except Exception:
        return None


def numba_info() -> Dict:
    try:
        import numba
        return {"available": True, "version": numba.__version__,
                "threads": int(numba.config.NUMBA_NUM_THREADS)}
    except Exception:
        return {"available": False, "version": None, "threads": 0}


def cupy_info() -> Dict:
    """CuPy + GPU NVIDIA. 'available' exige ao menos uma GPU utilizável."""
    try:
        import cupy
    except Exception as e:
        return {"available": False, "reason": f"CuPy não instalado ({e.__class__.__name__})"}
    try:
        n = int(cupy.cuda.runtime.getDeviceCount())
        if n < 1:
            return {"available": False, "reason": "nenhuma GPU CUDA"}
        props = cupy.cuda.runtime.getDeviceProperties(0)
        nome = props["name"]
        nome = nome.decode("utf-8", "replace") if isinstance(nome, bytes) else str(nome)
        return {"available": True, "version": cupy.__version__,
                "gpu_name": nome, "gpu_count": n,
                "gpu_memory_bytes": int(props["totalGlobalMem"]),
                "cuda_runtime": int(cupy.cuda.runtime.runtimeGetVersion()),
                "cuda_driver": int(cupy.cuda.runtime.driverGetVersion())}
    except Exception as e:
        return {"available": False, "reason": f"{e.__class__.__name__}: {e}"}


@lru_cache(maxsize=1)
def detect_hardware() -> Dict:
    """Retrato do hardware (em cache por processo)."""
    return {
        "cpu": platform.processor() or platform.machine(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "logical_cores": os.cpu_count() or 1,
        "physical_cores": _physical_cores(),
        "ram_bytes": _ram_bytes(),
        "numba": numba_info(),
        "cupy": cupy_info(),
    }


def _gib(b: Optional[int]) -> str:
    return "?" if not b else f"{b / 2**30:.1f} GiB"


def hardware_report() -> str:
    h = detect_hardware()
    nb, cp = h["numba"], h["cupy"]
    linhas = [
        f"CPU               : {h['cpu']}",
        f"Logical cores     : {h['logical_cores']}",
        f"Physical cores    : {h['physical_cores'] or '?'}",
        f"RAM               : {_gib(h['ram_bytes'])}",
        f"Platform          : {h['platform']}",
        f"Python            : {h['python']}",
        f"Numba             : {nb['version'] if nb['available'] else 'não disponível'}",
    ]
    if cp["available"]:
        linhas += [f"CuPy              : {cp['version']}",
                   f"GPU               : {cp['gpu_name']} "
                   f"({_gib(cp['gpu_memory_bytes'])})",
                   f"CUDA (runtime)    : {cp['cuda_runtime']}"]
    else:
        linhas.append(f"CuPy / GPU        : indisponível ({cp['reason']})")
    return "\n".join(linhas)
