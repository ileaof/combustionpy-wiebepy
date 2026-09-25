# -*- coding: utf-8 -*-
"""
results.py — Extração de resultados e balanços do caso de fresta.

Fontes (postProcessing do foamRun, formatos verificados em caso real):
  • fluxoMassaCamara   sum(phi)                  [kg/s]
  • pT_camara          areaAverage(p), (T)       [Pa, K]
  • massaTotal/Fresta/Buffer  volIntegrate(rho)  [kg]
  • energiaFresta/Buffer      volIntegrate(p)    [Pa·m³ → U = ∫p dV/(γ−1)]
  • calorLiner/Pistao  areaIntegrate(wallHeatFlux) [W]

CONVENÇÃO DE SINAIS (declarada no relatório e respeitada aqui):
  • phi do OpenFOAM: positivo = fluxo SAINDO do domínio (fresta→câmara).
    ṁ_camara = sum(phi); entrada de gás = ṁ < 0.
  • wallHeatFlux do OpenFOAM: positivo = calor PARA o gás. Aqui as séries
    q_parede são invertidas: q > 0 = gás PERDE calor para a parede.

Balanco (referencial do domínio, volume constante — sem trabalho p·dV):
  massa:   m(t) − [m0 + ∫max(−ṁ,0)dt − ∫max(ṁ,0)dt]  ≤ tolerância
  energia: ΔU = ∫ṁ_in·cp·T_in dt − ∫ṁ_out·cp·T_out dt − ∫q̇_paredes dt
           com h ≈ cp·T (aproximação declarada; sem energia cinética e
           sem termo viscoso de parede).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from ..cfd.results import _read_dat          # mesmo parser de .dat (# Time)


def _dat(case_dir: Path, fo: str, fname: Optional[str] = None) -> np.ndarray:
    """Série (Time, colunas…) do functionObject, concatenando subpastas
    de startTime em ordem."""
    base = case_dir / "postProcessing" / fo
    if not base.is_dir():
        return np.zeros((0, 0))
    partes = []
    for sub in sorted(p for p in base.iterdir() if p.is_dir()):
        for dat in sorted(sub.glob(f"{fname or fo}.dat")):
            s, _ = _read_dat(dat)
            if s.size:
                partes.append(s)
    if not partes:
        return np.zeros((0, 0))
    ncol = min(p.shape[1] for p in partes)
    return np.vstack([p[:, :ncol] for p in partes])


@dataclass
class Balanco:
    """Resultado de um balanço — número + estado explícito (nunca
    silencioso)."""

    nome: str
    valor: float            # grandeza principal (residual, na unidade)
    rel_pct: float          # resíduo relativo [%]
    tolerancia_pct: float
    ok: bool
    detalhe: Dict[str, float] = field(default_factory=dict)


@dataclass
class CreviceResults:
    """Séries temporais do caso (t do solver → θ via dθ/dt declarado)."""

    t: np.ndarray                       # [s], tempo do solver (0 na janela)
    theta_deg: np.ndarray               # [°], ângulo absoluto
    p_camara: np.ndarray                # [Pa]  (área-média, patch chamber)
    T_camara: np.ndarray                # [K]
    m_total: np.ndarray                 # [kg]  (∫ρ dV, domínio todo)
    m_fresta: np.ndarray                # [kg]  (zona crevice)
    m_buffer: np.ndarray                # [kg]  (zona buffer)
    u_total: np.ndarray                 # [J]   (∫p dV/(γ−1))
    mdot: np.ndarray                    # [kg/s] + = SAINDO (fresta→câmara)
    q_liner: np.ndarray                 # [W]  + = gás perde para a parede
    q_pistao: np.ndarray                # [W]  idem
    meta: Dict = field(default_factory=dict)

    # ----------------------------------------------------------- derivadas
    @property
    def mdot_in(self) -> np.ndarray:
        """Vazão ENTRANDO (câmara→fresta) [kg/s] ≥ 0."""
        return np.maximum(-self.mdot, 0.0)

    @property
    def mdot_out(self) -> np.ndarray:
        """Vazão SAINDO (fresta→câmara) [kg/s] ≥ 0."""
        return np.maximum(self.mdot, 0.0)

    def _cum(self, y: np.ndarray) -> np.ndarray:
        if self.t.size < 2:
            return np.zeros_like(y)
        return np.concatenate(([0.0], np.cumsum(
            0.5 * (y[1:] + y[:-1]) * np.diff(self.t))))

    def m_in_cum(self) -> np.ndarray:
        """Massa acumulada de ENTRADA [kg]."""
        return self._cum(self.mdot_in)

    def m_out_cum(self) -> np.ndarray:
        """Massa acumulada de SAÍDA [kg] (separada da entrada)."""
        return self._cum(self.mdot_out)

    def q_cum(self) -> Dict[str, np.ndarray]:
        """Calor acumulado por parede + total [J] (integrado no tempo)."""
        qw = self.q_liner + self.q_pistao
        return {"liner": self._cum(self.q_liner),
                "piston": self._cum(self.q_pistao),
                "total": self._cum(qw)}

    # ------------------------------------------------------------ balanços
    def balanco_massa(self, tolerancia_pct: float = 0.5) -> Balanco:
        """m(t) = m0 + m_in_cum − m_out_cum, ponto a ponto."""
        if self.t.size < 2:
            return Balanco("massa", 0.0, 0.0, tolerancia_pct, False,
                           {"motivo": "série vazia"})
        prev = self.m_total[0] + self.m_in_cum() - self.m_out_cum()
        res = self.m_total - prev
        m0 = float(self.m_total[0])
        denom = max(abs(m0), 1e-15)
        rel = float(np.max(np.abs(res)) / denom * 100.0)
        return Balanco("massa", float(np.max(np.abs(res))), rel,
                       tolerancia_pct, rel <= tolerancia_pct,
                       {"m0_kg": m0, "m_in_final_kg":
                        float(self.m_in_cum()[-1]),
                        "m_out_final_kg": float(self.m_out_cum()[-1]),
                        "m_final_kg": float(self.m_total[-1])})

    def balanco_energia(self, tolerancia_pct: float = 2.0) -> Balanco:
        """ΔU = ∫ṁ_in·cp·T_in − ∫ṁ_out·cp·T_out − ∫q̇_paredes."""
        if self.t.size < 2:
            return Balanco("energia", 0.0, 0.0, tolerancia_pct, False,
                           {"motivo": "série vazia"})
        g = self.meta.get("gas", {})
        gam = float(g.get("gamma", 0) or 0)
        rspec = float(g.get("R_specific_J_kgK", 0) or 0)
        cp = gam * rspec / (gam - 1.0)
        t_in = float(self.meta.get("condicao_camara", {}).get(
            "inflow_T_K", self.T_camara[0]))
        e_in = self._cum(self.mdot_in * cp * t_in)
        e_out = self._cum(self.mdot_out * cp * self.T_camara)
        q = self.q_cum()["total"]
        du = float(self.u_total[-1] - self.u_total[0])
        esperado = float((e_in - e_out - q)[-1])
        res = du - esperado
        denom = max(abs(esperado), abs(du), 1e-15)
        rel = abs(res) / denom * 100.0
        return Balanco("energia", res, rel, tolerancia_pct,
                       rel <= tolerancia_pct,
                       {"dU_J": du, "entalpia_liquida_J": esperado,
                        "Q_paredes_J": float(q[-1]),
                        "E_in_J": float(e_in[-1]),
                        "E_out_J": float(e_out[-1]),
                        "aproximacao": "h ~= cp·T; h_in = cp·T_inflow "
                                       "(BC inletOutlet)"})

    # ------------------------------------------------------------- exportar
    def export_serie(self, case_dir) -> Path:
        """CSV com todas as séries e acumulados (θ, t, p, T, massas,
        vazões, calores, U) — convenção de sinais no cabeçalho."""
        case_dir = Path(case_dir)
        q = self.q_cum()
        cols = ["theta_deg", "t_s", "p_camara_Pa", "T_camara_K",
                "m_total_kg", "m_fresta_kg", "m_buffer_kg", "U_J",
                "mdot_kg_s_positivo_saindo", "mdot_in_kg_s",
                "mdot_out_kg_s", "m_in_cum_kg", "m_out_cum_kg",
                "q_liner_W", "q_pistao_W", "Q_liner_cum_J",
                "Q_pistao_cum_J", "Q_paredes_cum_J"]
        data = [self.theta_deg, self.t, self.p_camara, self.T_camara,
                self.m_total, self.m_fresta, self.m_buffer, self.u_total,
                self.mdot, self.mdot_in, self.mdot_out, self.m_in_cum(),
                self.m_out_cum(), self.q_liner, self.q_pistao,
                q["liner"], q["piston"], q["total"]]
        saida = case_dir / "results_series.csv"
        with open(saida, "w", encoding="utf-8", newline="") as fh:
            fh.write("# crevice_flow — série temporal do submodelo\n")
            fh.write("# sinais: mdot>0 = sai do domínio (fresta→câmara); "
                     "q>0 = gás perde calor para a parede\n")
            fh.write(",".join(cols) + "\n")
            for linha in zip(*data):
                fh.write(",".join(f"{v:.8g}" for v in linha) + "\n")
        return saida

    def tempos_de_campo(self, case_dir) -> List[float]:
        """Instantes com campos 3D gravados (snapshots p/T/U/rho)."""
        case_dir = Path(case_dir)
        tempos = []
        for p in case_dir.iterdir():
            if p.is_dir():
                try:
                    tempos.append(float(p.name))
                except ValueError:
                    continue
        return sorted(tempos)

    # ---------------------------------------------------------------- load
    @classmethod
    def load(cls, case_dir, cfg=None) -> "CreviceResults":
        """Lê o postProcessing do caso + case_config.yaml (conversões
        dθ/dt declaradas na config — nunca re-derivadas do dado)."""
        import yaml
        case_dir = Path(case_dir)
        yml = case_dir / "case_config.yaml"
        meta = (yaml.safe_load(yml.read_text(encoding="utf-8"))
                if yml.exists() else {})
        janela = meta.get("janela_deg") or [0.0, 0.0]
        rot = meta.get("rotacao") or {}
        deg_s = float(rot.get("dtheta_dt_deg_s", 0) or 0)

        flux = _dat(case_dir, "fluxoMassaCamara", "surfaceFieldValue")
        pt = _dat(case_dir, "pT_camara", "surfaceFieldValue")
        m_tot = _dat(case_dir, "massaTotal", "volFieldValue")
        m_fre = _dat(case_dir, "massaFresta", "volFieldValue")
        m_buf = _dat(case_dir, "massaBuffer", "volFieldValue")
        e_fre = _dat(case_dir, "energiaFresta", "volFieldValue")
        e_buf = _dat(case_dir, "energiaBuffer", "volFieldValue")
        q_lin = _dat(case_dir, "calorLiner", "surfaceFieldValue")
        q_pis = _dat(case_dir, "calorPistao", "surfaceFieldValue")

        # grelha temporal = série do fluxo (writeControl comum)
        t = flux[:, 0].copy() if flux.size else np.zeros(0)
        g = meta.get("gas", {}) or {}
        gam = float(g.get("gamma", 1.4))
        u_tot = np.zeros_like(t)
        if t.size and e_fre.size and e_buf.size:
            # alinhar por tempo comum (as séries gravam nos mesmos steps)
            u_tot = (_zone_at(e_fre, t) + _zone_at(e_buf, t)) / (gam - 1.0)

        return cls(
            t=t,
            theta_deg=janela[0] + t * deg_s if t.size else np.zeros(0),
            p_camara=_zone_at(pt, t, col=1) if pt.size else np.zeros_like(t),
            T_camara=_zone_at(pt, t, col=2) if pt.size else np.zeros_like(t),
            m_total=_zone_at(m_tot, t) if m_tot.size else np.zeros_like(t),
            m_fresta=_zone_at(m_fre, t) if m_fre.size else np.zeros_like(t),
            m_buffer=_zone_at(m_buf, t) if m_buf.size else np.zeros_like(t),
            u_total=u_tot,
            mdot=flux[:, 1].copy() if flux.size else np.zeros(0),
            # sinal invertido: OF positivo = calor para o gás; aqui
            # q>0 = gás PERDE (convenção declarada no docstring)
            q_liner=-_zone_at(q_lin, t) if q_lin.size else np.zeros_like(t),
            q_pistao=-_zone_at(q_pis, t) if q_pis.size else np.zeros_like(t),
            meta=meta)


def _zone_at(serie: np.ndarray, t: np.ndarray, col: int = 1) -> np.ndarray:
    """Amostra a série do FO nos instantes t (interpolação; as séries
    compartilham os mesmos tempos de gravação)."""
    if serie.size == 0 or t.size == 0:
        return np.zeros_like(t)
    return np.interp(t, serie[:, 0], serie[:, col])


__all__ = ["CreviceResults", "Balanco"]