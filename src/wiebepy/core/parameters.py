# -*- coding: utf-8 -*-
"""
parameters.py — Estágios Wiebe e parametrização para o ajuste.

Um estágio j é descrito por (beta_j, theta0_j, duration_j, m_j, a_j):

    beta_j      fração da massa queimada atribuída ao estágio [-]
    theta0_j    início do estágio [unidade angular dos dados]
    duration_j  duração do estágio (Δθ_j) [mesma unidade]
    m_j         fator de forma [-]  (m_j > 0)
    a_j         eficiência [-]      (a = 6.908 => 99.9 % queimado em Δθ)

A parametrização (``Parametrization``) mapeia um vetor de busca em caixa
(adequado ao PSO) nos parâmetros físicos, para qualquer N = 1..5, sem ramos
por número de estágios:

    [theta0_1, dtheta0_2..N, duration_1..N, m_1..N, (a_1..N), pesos]

* inícios por incrementos não negativos (theta0_j = theta0_1 + Σ dtheta0_k),
  o que impõe theta0_1 <= ... <= theta0_N e elimina permutações;
* pesos em um dos modos:
    - "stick"    (padrão): frações s_1..s_{N-1} ∈ [0, 1]
                 beta_1 = s_1, beta_j = s_j Π_{k<j}(1-s_k), beta_N = Π(1-s_k)
    - "softmax": logits z_1..z_{N-1} com z_N = 0 fixo (sem grau redundante)
    - "explicit": beta_1..beta_{N-1} ∈ [0, 1], beta_N = 1 - Σ; soma > 1 é
                 penalizada (modo tradicional, para comparação).
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence

import numpy as np

A_DEFAULT = 6.908          # ln(1000): 99.9 % queimado ao fim de Δθ
MAX_STAGES = 5
BETA_MODES = ("stick", "softmax", "explicit")
PENALTY = 1.0e10           # objetivo de candidatos inválidos
PENALTY_WEIGHT = 1.0e2     # peso das violações suaves (limite cumulativo etc.)


# =============================================================================
# Estágio
# =============================================================================
@dataclass
class Stage:
    """Parâmetros físicos de um estágio Wiebe."""
    beta: float
    theta0: float
    duration: float
    m: float
    a: float = A_DEFAULT

    def to_dict(self) -> Dict[str, float]:
        return {k: float(v) for k, v in asdict(self).items()}

    @classmethod
    def from_dict(cls, d: Dict) -> "Stage":
        faltando = {"beta", "theta0", "duration", "m"} - set(d)
        if faltando:
            raise ValueError(f"Estágio sem os campos: {sorted(faltando)}")
        return cls(beta=float(d["beta"]), theta0=float(d["theta0"]),
                   duration=float(d["duration"]), m=float(d["m"]),
                   a=float(d.get("a", A_DEFAULT)))


def as_stages(stages: Iterable) -> List[Stage]:
    """Aceita lista de Stage ou de dicts e devolve lista de Stage."""
    out = []
    for s in stages:
        out.append(s if isinstance(s, Stage) else Stage.from_dict(s))
    return out


def stages_to_arrays(stages: Iterable) -> Dict[str, np.ndarray]:
    """Lista de estágios -> dict de arrays (N,) beta/theta0/duration/m/a."""
    st = as_stages(stages)
    return {k: np.array([getattr(s, k) for s in st], dtype=float)
            for k in ("beta", "theta0", "duration", "m", "a")}


def validate_stages(stages: Iterable, tol: float = 1e-9) -> List[str]:
    """Mensagens de erro para estágios fisicamente inválidos (vazia = ok)."""
    st = as_stages(stages)
    erros: List[str] = []
    if not 1 <= len(st) <= MAX_STAGES:
        erros.append(f"Número de estágios deve estar entre 1 e {MAX_STAGES} "
                     f"(recebido {len(st)}).")
    for j, s in enumerate(st, start=1):
        if not 0.0 <= s.beta <= 1.0:
            erros.append(f"beta_{j} deve estar em [0, 1] (recebido {s.beta}).")
        if not s.duration > 0.0:
            erros.append(f"duration_{j} deve ser > 0 (recebido {s.duration}).")
        if not s.m > 0.0:
            erros.append(f"m_{j} deve ser > 0 (recebido {s.m}).")
        if not s.a > 0.0:
            erros.append(f"a_{j} deve ser > 0 (recebido {s.a}).")
        if not all(math.isfinite(v) for v in
                   (s.beta, s.theta0, s.duration, s.m, s.a)):
            erros.append(f"estágio {j} contém valor não finito.")
    soma = sum(s.beta for s in st)
    if st and abs(soma - 1.0) > tol:
        erros.append(f"Σ beta deve ser 1 (recebido {soma:.12g}).")
    return erros


def sort_stages(stages: Iterable) -> List[Stage]:
    """Ordena por theta0 (a física é invariante à ordem)."""
    return sorted(as_stages(stages), key=lambda s: s.theta0)


def default_stages(n_stages: int, theta_min: float, theta_max: float,
                   a: float = A_DEFAULT) -> List[Stage]:
    """Estágios plausíveis para avaliação sem dados: inícios espaçados no
    primeiro terço do intervalo, durações crescentes, pesos iguais."""
    _check_n(n_stages)
    R = float(theta_max - theta_min)
    out = []
    for j in range(n_stages):
        out.append(Stage(
            beta=1.0 / n_stages,
            theta0=theta_min + R * (0.10 + 0.25 * j / max(n_stages, 1)),
            duration=R * (0.15 + 0.10 * j),
            m=2.0 if j == 0 else 1.0,
            a=a))
    return out


def _check_n(n: int) -> None:
    if not isinstance(n, (int, np.integer)) or not 1 <= n <= MAX_STAGES:
        raise ValueError(f"n_stages deve ser inteiro entre 1 e {MAX_STAGES} "
                         f"(recebido {n!r}).")


# =============================================================================
# Limites
# =============================================================================
@dataclass
class StageBounds:
    """Limites do espaço de busca (mesmos para todos os estágios)."""
    theta0: tuple                 # início do 1º estágio
    dtheta0: tuple                # incremento entre inícios consecutivos
    duration: tuple
    m: tuple = (0.05, 5.0)
    a: tuple = (1.0, 15.0)
    z: tuple = (-8.0, 8.0)        # logits (modo softmax)
    theta0_max: Optional[float] = None   # limite cumulativo do último início

    @classmethod
    def from_data(cls, theta_min: float, theta_max: float) -> "StageBounds":
        R = float(theta_max - theta_min)
        if not R > 0:
            raise ValueError("Intervalo angular inválido (theta_max <= theta_min).")
        return cls(theta0=(theta_min, theta_max - 0.05 * R),
                   dtheta0=(0.0, 0.5 * R),
                   duration=(0.01 * R, 1.5 * R),
                   theta0_max=theta_max)

    def to_dict(self) -> Dict:
        return {k: (list(v) if isinstance(v, tuple) else v)
                for k, v in asdict(self).items()}

    @classmethod
    def from_dict(cls, d: Dict) -> "StageBounds":
        kw = {k: (tuple(v) if isinstance(v, list) else v) for k, v in d.items()}
        return cls(**kw)


# =============================================================================
# Parametrização
# =============================================================================
@dataclass
class Parametrization:
    """Mapeia vetores de busca (S, P) em parâmetros físicos (S, N)."""
    n_stages: int
    bounds: StageBounds
    beta_mode: str = "stick"
    fit_a: bool = False
    a_fixed: float = A_DEFAULT
    names: List[str] = field(init=False)
    lower: np.ndarray = field(init=False)
    upper: np.ndarray = field(init=False)

    def __post_init__(self):
        _check_n(self.n_stages)
        if self.beta_mode not in BETA_MODES:
            raise ValueError(f"beta_mode deve ser um de {BETA_MODES}.")
        N, b = self.n_stages, self.bounds
        nomes, lo, hi = ["theta0_1"], [b.theta0[0]], [b.theta0[1]]
        for j in range(2, N + 1):
            nomes.append(f"dtheta0_{j}")
            lo.append(b.dtheta0[0]); hi.append(b.dtheta0[1])
        for rot, lim in (("duration", b.duration), ("m", b.m)) + (
                (("a", b.a),) if self.fit_a else ()):
            for j in range(1, N + 1):
                nomes.append(f"{rot}_{j}")
                lo.append(lim[0]); hi.append(lim[1])
        rot_w, lim_w = {"stick": ("s", (0.0, 1.0)),
                        "softmax": ("z", b.z),
                        "explicit": ("beta", (0.0, 1.0))}[self.beta_mode]
        for j in range(1, N):
            nomes.append(f"{rot_w}_{j}")
            lo.append(lim_w[0]); hi.append(lim_w[1])
        self.names = nomes
        self.lower = np.asarray(lo, dtype=float)
        self.upper = np.asarray(hi, dtype=float)

    @property
    def size(self) -> int:
        return len(self.names)

    # ------------------------------------------------------------ decode
    def decode(self, X, xp=np):
        """X (S, P) -> (params, penalidade) com params[k] (S, N) e
        penalidade (S,) por violação suave (limite cumulativo de theta0,
        soma de pesos > 1 no modo explícito)."""
        N = self.n_stages
        X = xp.atleast_2d(X)
        S = X.shape[0]
        c = 0
        inc = X[:, c:c + N]                       # theta0_1, dtheta0_2..N
        c += N
        theta0 = xp.cumsum(inc, axis=1)
        duration = X[:, c:c + N]; c += N
        m = X[:, c:c + N]; c += N
        if self.fit_a:
            a = X[:, c:c + N]; c += N
        else:
            a = xp.full((S, N), self.a_fixed, dtype=X.dtype)
        w = X[:, c:c + N - 1]
        pen = xp.zeros(S, dtype=X.dtype)
        if self.beta_mode == "stick":
            beta = xp.empty((S, N), dtype=X.dtype)
            resto = xp.ones(S, dtype=X.dtype)
            for j in range(N - 1):
                beta[:, j] = w[:, j] * resto
                resto = resto * (1.0 - w[:, j])
            beta[:, N - 1] = resto
        elif self.beta_mode == "softmax":
            z = xp.concatenate([w, xp.zeros((S, 1), dtype=X.dtype)], axis=1)
            z = z - z.max(axis=1, keepdims=True)
            e = xp.exp(z)
            beta = e / e.sum(axis=1, keepdims=True)
        else:                                     # explicit
            ultimo = 1.0 - w.sum(axis=1)
            pen = pen + PENALTY_WEIGHT * xp.minimum(ultimo, 0.0) ** 2
            beta = xp.concatenate(
                [w, xp.maximum(ultimo, 0.0)[:, None]], axis=1)
        if self.bounds.theta0_max is not None:
            R = self.bounds.theta0[1] - self.bounds.theta0[0] or 1.0
            excesso = xp.maximum(theta0[:, -1] - self.bounds.theta0_max, 0.0)
            pen = pen + PENALTY_WEIGHT * (excesso / R) ** 2
        return ({"beta": beta, "theta0": theta0, "duration": duration,
                 "m": m, "a": a}, pen)

    def to_stages(self, x) -> List[Stage]:
        """Vetor (P,) -> lista de Stage (numpy)."""
        p, _ = self.decode(np.asarray(x, dtype=float)[None, :])
        return [Stage(beta=float(p["beta"][0, j]),
                      theta0=float(p["theta0"][0, j]),
                      duration=float(p["duration"][0, j]),
                      m=float(p["m"][0, j]), a=float(p["a"][0, j]))
                for j in range(self.n_stages)]

    # ------------------------------------------------------------ encode
    def encode(self, stages: Sequence) -> np.ndarray:
        """Lista de estágios -> vetor (P,) (inversa de decode para estágios
        ordenados por theta0). Não recorta nos limites."""
        st = sort_stages(stages)
        if len(st) != self.n_stages:
            raise ValueError("Número de estágios diferente da parametrização.")
        N = self.n_stages
        th = [s.theta0 for s in st]
        v = [th[0]] + [th[j] - th[j - 1] for j in range(1, N)]
        v += [s.duration for s in st] + [s.m for s in st]
        if self.fit_a:
            v += [s.a for s in st]
        beta = np.array([s.beta for s in st], dtype=float)
        if self.beta_mode == "stick":
            resto = 1.0
            for j in range(N - 1):
                v.append(beta[j] / resto if resto > 0 else 0.0)
                resto -= beta[j]
        elif self.beta_mode == "softmax":
            b = np.maximum(beta, 1e-300)
            v += list(np.log(b[:-1]) - np.log(b[-1]))
        else:
            v += list(beta[:-1])
        return np.asarray(v, dtype=float)

    def to_dict(self) -> Dict:
        return {"n_stages": self.n_stages, "beta_mode": self.beta_mode,
                "fit_a": self.fit_a, "a_fixed": self.a_fixed,
                "bounds": self.bounds.to_dict()}
