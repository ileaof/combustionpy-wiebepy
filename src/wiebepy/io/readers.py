# -*- coding: utf-8 -*-
"""
readers.py — Leitura de dados experimentais (CSV, TXT, DAT, JSON).

Tabelas (.csv/.txt/.dat): separador detectado (vírgula, ponto e vírgula,
tabulação ou espaços); linhas iniciadas por # são comentários. Colunas
reconhecidas pelo cabeçalho (maiúsculas/minúsculas indiferentes):

    theta | angle | ca | crank_angle                 ângulo
    xb | mfb | x_b | burned_fraction                 fração queimada [-]
    dxb_dtheta | dxb | burn_rate | rohr_norm         taxa de queima
    weight | w                                       peso do ponto
    sigma | uncertainty | std                        incerteza (w = 1/σ²)

Sem cabeçalho: 2 colunas = theta, xb; 3 colunas = theta, xb, dxb_dtheta.

JSON: {"theta": [...], "xb": [...], "dxb_dtheta": [...], "weight": [...]}
(mesmos aliases).

Os dados são ordenados por θ; ângulos repetidos geram erro claro.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from ..core.validation import DataError
from ..optimization.objective import FitData

ALIASES = {
    "theta": ("theta", "angle", "ca", "crank_angle", "crankangle", "θ"),
    "xb": ("xb", "mfb", "x_b", "burned_fraction", "mass_fraction_burned"),
    "dxb": ("dxb_dtheta", "dxb", "burn_rate", "dxbdtheta", "rohr_norm",
            "dx_b/dtheta"),
    "weight": ("weight", "weights", "w"),
    "sigma": ("sigma", "uncertainty", "std", "stdev"),
}
EXTENSOES = (".csv", ".txt", ".dat", ".json", ".tsv")


def _canon(nome: str) -> Optional[str]:
    n = nome.strip().lower().replace(" ", "_")
    for k, als in ALIASES.items():
        if n in als:
            return k
    return None


def _from_columns(cols: Dict[str, np.ndarray], fonte: str,
                  angle_unit: str) -> FitData:
    if "theta" not in cols:
        raise DataError(f"{fonte}: coluna de ângulo (theta) não encontrada.")
    if "xb" not in cols and "dxb" not in cols:
        raise DataError(f"{fonte}: é preciso a coluna xb e/ou dxb_dtheta.")
    w = cols.get("weight")
    if w is None and "sigma" in cols:
        s = cols["sigma"]
        if np.any(s <= 0):
            raise DataError(f"{fonte}: sigma deve ser positivo.")
        w = 1.0 / s ** 2
    ordem = np.argsort(cols["theta"], kind="stable")
    th = cols["theta"][ordem]
    if np.any(np.diff(th) == 0):
        raise DataError(f"{fonte}: ângulos θ repetidos.")
    pega = lambda k: None if cols.get(k) is None else cols[k][ordem]  # noqa: E731
    d = FitData(th, pega("xb"), pega("dxb"),
                None if w is None else np.asarray(w)[ordem],
                angle_unit=angle_unit, source=fonte)
    return d


def _parse_table(texto: str, fonte: str) -> Dict[str, np.ndarray]:
    linhas = [l for l in texto.splitlines()
              if l.strip() and not l.lstrip().startswith("#")]
    if not linhas:
        raise DataError(f"{fonte}: arquivo vazio.")
    amostra = "\n".join(linhas[:20])
    try:
        dialeto = csv.Sniffer().sniff(amostra, delimiters=",;\t ")
        sep = dialeto.delimiter
    except csv.Error:
        sep = None
    def dividir(l):
        partes = l.split(sep) if sep not in (None, " ") else l.split()
        return [p.strip() for p in partes if p.strip() != ""]
    cab = dividir(linhas[0])
    try:
        [float(c) for c in cab]
        tem_cab = False
    except ValueError:
        tem_cab = True
    corpo = linhas[1:] if tem_cab else linhas
    try:
        M = np.array([[float(v) for v in dividir(l)] for l in corpo])
    except ValueError as e:
        raise DataError(f"{fonte}: valor não numérico ({e}).") from None
    if M.ndim != 2 or M.shape[1] < 2:
        raise DataError(f"{fonte}: são necessárias ao menos 2 colunas.")
    if tem_cab:
        if len(cab) != M.shape[1]:
            raise DataError(f"{fonte}: cabeçalho com {len(cab)} colunas e "
                            f"dados com {M.shape[1]}.")
        cols = {}
        for i, nome in enumerate(cab):
            k = _canon(nome)
            if k is not None:
                cols[k] = M[:, i]
        return cols
    nomes = ["theta", "xb", "dxb"][:M.shape[1]]
    return {k: M[:, i] for i, k in enumerate(nomes)}


def read_data(path, angle_unit: str = "deg") -> FitData:
    """Lê um arquivo de dados experimentais e devolve FitData."""
    p = Path(path)
    if not p.exists():
        raise DataError(f"Arquivo não encontrado: {p}")
    ext = p.suffix.lower()
    if ext not in EXTENSOES:
        raise DataError(f"Extensão '{ext}' não suportada ({', '.join(EXTENSOES)}).")
    texto = p.read_text(encoding="utf-8-sig")
    if ext == ".json":
        try:
            bruto = json.loads(texto)
        except json.JSONDecodeError as e:
            raise DataError(f"{p.name}: JSON inválido ({e}).") from None
        if isinstance(bruto, dict) and "data" in bruto:
            bruto = bruto["data"]
        cols = {}
        for nome, v in bruto.items():
            k = _canon(nome)
            if k is not None and v is not None:
                cols[k] = np.asarray(v, dtype=float)
    else:
        cols = _parse_table(texto, p.name)
    return _from_columns(cols, p.name, angle_unit)


def theta_grid(theta_min: float, theta_max: float, step: float) -> np.ndarray:
    """Grade θ_min..θ_max (inclusive) com passo ``step``."""
    if not step > 0 or not theta_max > theta_min:
        raise ValueError("Use theta_max > theta_min e theta_step > 0.")
    n = int(np.floor((theta_max - theta_min) / step + 1e-9)) + 1
    return theta_min + step * np.arange(n)
