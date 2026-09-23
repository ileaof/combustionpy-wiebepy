# -*- coding: utf-8 -*-
"""
config.py — Configuração do módulo CFD (seção ``cfd`` do arquivo de
configuração) e estados do caso.

Estrutura (exemplo; a seção inteira é opcional e ``enabled: false`` é o
padrão — ver io/config.py):

    cfd:
      enabled: false
      adapter: openfoam          # único adapter implementado
      mode: prescribed_wiebe     # prescribed_wiebe | reactive (não implementado)
      case_directory: results/cfd/case_001
      workers: 4                 # processos do SOLVER (MPI), não do wiebepy
      wsl_distro: Ubuntu-22.04   # Windows: distribuição WSL2 com o solver

      geometry:
        type: simplified_cylinder
        moving_piston: true
        # bore, stroke, rod_length, Rc, rpm vêm da seção ``engine`` existente
        # (EngineConfig); podem ser sobrescritos aqui se desejado.

      interval:                  # janela simulada (válvulas fechadas)
        angle_unit: deg          # deg | rad
        start: -120
        end: 120

      initial: {P_kPa: 250, T_K: 800}
      walls: {Tw_K: 440, model: fixed_temperature}
      turbulence: {model: kEpsilon, wall_functions: true}
      numerics: {deltaT_s: 1.0e-06, max_Co: 0.25, write_interval_deg: 5}

      heat_source:
        distribution: uniform    # uniform (referência) | region
        region: null             # nome do cellZone, se distribution=region

      fuel: {name: diesel, feed: premixed_gas}   # diesel do ensaio (PCI do
                                                 # ensaio na seção engine)
      wiebe:
        source: model            # model (model.json do wiebepy) | parameters
        model: results/model.json
        # parameters: [{beta, theta0, duration, m}, …]

      comparison:
        criterion: same_rpm_same_energy   # registro do critério (doc)
        experimental: null                # CSV θ,P opcional (leitor do módulo
                                          # de pressão)
        experimental_angle_unit: rad      # rad | deg
        experimental_pressure_unit: kPa   # kPa | bar | MPa | Pa | psi
        experimental_offset_deg: 0.0      # alinhamento de fase [°CA] (0 = sem
                                          # alinhamento; PMP em θ=0 assumida)

A validação (``CfdConfig.validate``) checa campos obrigatórios ANTES de
qualquer execução. O arquivo de configuração efetivamente usado — incluindo
valores derivados e versões do solver — é gravado em <case>/case_config.yaml
pelo case_builder.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

from wiebepy.cfd.fuels import fuel_names


class CaseState(str, Enum):
    """Estados do caso CFD (§12). ``running`` ≠ convergiu: 'processo
    terminou' só vira 'completed' após a verificação de resultados."""
    NOT_CONFIGURED = "not_configured"
    PREPARED = "prepared"
    VALIDATED = "validated"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"

    @property
    def label(self) -> str:
        return {"not_configured": "Não configurado",
                "prepared": "Preparado",
                "validated": "Validado",
                "running": "Executando",
                "completed": "Concluído",
                "cancelled": "Cancelado",
                "failed": "Falhou"}[self.value]


class CfdConfigError(ValueError):
    """Configuração CFD inválida."""


ADAPTERS = ("openfoam",)
MODES = ("prescribed_wiebe", "reactive")
ANGLE_UNITS = ("deg", "rad")
FUELS = ("H2", "CH4", "ethanol", "diesel")
DISTRIBUTIONS = ("uniform", "region")


@dataclass
class CfdConfig:
    """Configuração CFD validável. Campos derivados são calculados por
    ``derived`` e gravados junto com o caso."""
    enabled: bool = False
    adapter: str = "openfoam"
    mode: str = "prescribed_wiebe"
    case_directory: str = "results/cfd/case_001"
    workers: int = 1
    wsl_distro: Optional[str] = None          # Windows: distro WSL2

    geometry_type: str = "simplified_cylinder"
    moving_piston: bool = True
    n_radial: int = 16             # células na direção radial (blockMesh)
    n_axial: int = 24              # células na direção axial (blockMesh)

    interval_angle_unit: str = "deg"
    interval_start: float = -120.0
    interval_end: float = 120.0

    P0_kPa: float = 250.0                     # pressão inicial [kPa]
    T0_K: float = 800.0                       # temperatura inicial [K]
    Tw_K: float = 440.0                       # temperatura de parede [K]
    wall_model: str = "fixed_temperature"     # fixed_temperature | adiabatic

    turbulence_model: str = "kEpsilon"
    wall_functions: bool = True

    # Propriedades do gás no physicalProperties (ar simplificado, §9).
    # Padrões = valores atuais do builder; o teste de equivalência
    # termodinâmica (γ = κ do 0-D) sobrescreve Cp explicitamente.
    gas_Cp_J_kgK: float = 1005.0              # Cp [J/kgK]
    gas_molWeight: float = 28.96              # massa molar [kg/kmol]
    gas_mu: float = 5.5e-05                   # viscosidade [Pa·s]
    gas_Pr: float = 0.7                       # Prandtl [-]

    deltaT_s: float = 1.0e-6                  # passo temporal [s]
    # 0,25 e não 0,5: com max_Co 0,5 os casos 008 (motrado) e 012 (Rc
    # efetivo) abortaram com pico de velocidade local → T negativa
    # (ver docs/cfd/verification.md §5b). Os casos 001–006 concluíram
    # em 0,5; 0,25 é o padrão robusto (sensibilidade Δt: case_011).
    max_Co: float = 0.25
    write_interval_deg: float = 5.0           # gravação por grau de manivela

    distribution: str = "uniform"             # uniform | region
    region: Optional[str] = None              # cellZone (distribution=region)

    fuel_name: str = "diesel"   # ensaio de pressão de referência: Diesel
    fuel_feed: str = "premixed_gas"   # pré-vaporizado no modo prescrito

    wiebe_source: str = "model"               # model | parameters
    wiebe_model: Optional[str] = None         # caminho de model.json
    wiebe_parameters: Optional[List[dict]] = None

    comparison_criterion: str = "same_rpm_same_energy"
    experimental: Optional[str] = None        # CSV θ,P (leitor do módulo
                                              # de pressão)
    experimental_angle_unit: str = "rad"      # rad | deg
    experimental_pressure_unit: str = "kPa"   # kPa | bar | MPa | Pa | psi
    experimental_offset_deg: float = 0.0      # alinhamento de fase [°CA]

    # ------------------------------------------------------------- leitura
    @classmethod
    def from_dict(cls, d: Optional[Dict]) -> "CfdConfig":
        """Cria a configuração a partir da seção ``cfd`` do arquivo."""
        d = dict(d or {})
        geo = d.get("geometry") or {}
        itv = d.get("interval") or {}
        ini = d.get("initial") or {}
        walls = d.get("walls") or {}
        turb = d.get("turbulence") or {}
        num = d.get("numerics") or {}
        hs = d.get("heat_source") or {}
        fuel = d.get("fuel") or {}
        wiebe = d.get("wiebe") or {}
        comp = d.get("comparison") or {}
        gas = d.get("gas") or {}
        return cls(
            enabled=bool(d.get("enabled", False)),
            adapter=d.get("adapter", "openfoam"),
            mode=d.get("mode", "prescribed_wiebe"),
            case_directory=d.get("case_directory", "results/cfd/case_001"),
            workers=int(d.get("workers") or 1),
            wsl_distro=d.get("wsl_distro"),
            geometry_type=geo.get("type", "simplified_cylinder"),
            moving_piston=bool(geo.get("moving_piston", True)),
            n_radial=int(geo.get("n_radial", 16)),
            n_axial=int(geo.get("n_axial", 24)),
            interval_angle_unit=itv.get("angle_unit", "deg"),
            interval_start=float(itv.get("start", -120.0)),
            interval_end=float(itv.get("end", 120.0)),
            P0_kPa=float(ini.get("P_kPa", 250.0)),
            T0_K=float(ini.get("T_K", 800.0)),
            Tw_K=float(walls.get("Tw_K", 440.0)),
            wall_model=walls.get("model", "fixed_temperature"),
            turbulence_model=turb.get("model", "kEpsilon"),
            wall_functions=bool(turb.get("wall_functions", True)),
            deltaT_s=float(num.get("deltaT_s", 1.0e-6)),
            max_Co=float(num.get("max_Co", 0.25)),
            write_interval_deg=float(num.get("write_interval_deg", 5.0)),
            distribution=hs.get("distribution", "uniform"),
            region=hs.get("region"),
            fuel_name=fuel.get("name", "diesel"),
            fuel_feed=fuel.get("feed", "premixed_gas"),
            gas_Cp_J_kgK=float(gas.get("Cp_J_kgK", 1005.0)),
            gas_molWeight=float(gas.get("molWeight_kg_kmol", 28.96)),
            gas_mu=float(gas.get("mu_Pa_s", 5.5e-05)),
            gas_Pr=float(gas.get("Pr", 0.7)),
            wiebe_source=wiebe.get("source", "model"),
            wiebe_model=wiebe.get("model"),
            wiebe_parameters=wiebe.get("parameters"),
            comparison_criterion=comp.get("criterion", "same_rpm_same_energy"),
            experimental=comp.get("experimental"),
            experimental_angle_unit=str(comp.get("experimental_angle_unit")
                                        or "rad"),
            experimental_pressure_unit=str(
                comp.get("experimental_pressure_unit") or "kPa"),
            experimental_offset_deg=float(
                comp.get("experimental_offset_deg", 0.0) or 0.0),
        )

    def to_dict_public(self) -> Dict:
        """A seção ``cfd`` como dict (valores padrão documentados)."""
        return {"enabled": self.enabled, "adapter": self.adapter,
                "mode": self.mode, "case_directory": self.case_directory,
                "workers": self.workers, "wsl_distro": self.wsl_distro,
                "geometry": {"type": self.geometry_type,
                             "moving_piston": self.moving_piston,
                             "n_radial": self.n_radial,
                             "n_axial": self.n_axial},
                "interval": {"angle_unit": self.interval_angle_unit,
                             "start": self.interval_start,
                             "end": self.interval_end},
                "initial": {"P_kPa": self.P0_kPa, "T_K": self.T0_K},
                "walls": {"Tw_K": self.Tw_K,
                          "model": self.wall_model},
                "turbulence": {"model": self.turbulence_model,
                               "wall_functions": self.wall_functions},
                "numerics": {"deltaT_s": self.deltaT_s, "max_Co": self.max_Co,
                             "write_interval_deg": self.write_interval_deg},
                "heat_source": {"distribution": self.distribution,
                                "region": self.region},
                "fuel": {"name": self.fuel_name, "feed": self.fuel_feed},
                "gas": {"Cp_J_kgK": self.gas_Cp_J_kgK,
                        "molWeight_kg_kmol": self.gas_molWeight,
                        "mu_Pa_s": self.gas_mu, "Pr": self.gas_Pr},
                "wiebe": {"source": self.wiebe_source,
                          "model": self.wiebe_model,
                          "parameters": self.wiebe_parameters},
                "comparison": {"criterion": self.comparison_criterion,
                               "experimental": self.experimental,
                               "experimental_angle_unit":
                                   self.experimental_angle_unit,
                               "experimental_pressure_unit":
                                   self.experimental_pressure_unit,
                               "experimental_offset_deg":
                                   self.experimental_offset_deg}}

    # ---------------------------------------------------------- derivados
    def derived(self, engine_cfg) -> Dict:
        """Valores derivados da geometria do motor (EngineConfig do modo
        pressão) e do intervalo — gravados no case_config.yaml."""
        from ..pressure.engine import volume
        import math
        unit = self.interval_angle_unit
        s, e = self.interval_start, self.interval_end
        a0, a1 = (math.radians(s), math.radians(e)) if unit == "deg" \
            else (s, e)
        V0, _, _ = volume(a0, engine_cfg.Rc, engine_cfg)
        V1, _, _ = volume(a1, engine_cfg.Rc, engine_cfg)
        th = a0
        Vmin, Vmax = V0, V0
        n = 720
        for i in range(n + 1):
            a = a0 + (a1 - a0) * i / n
            V, _, _ = volume(a, engine_cfg.Rc, engine_cfg)
            Vmin, Vmax = min(Vmin, V), max(Vmax, V)
        return {
            "interval_start_rad": a0, "interval_end_rad": a1,
            "interval_duration_s": (a1 - a0)
                                   / (2.0 * math.pi * engine_cfg.omega_rev_s),
            "V_start_m3": float(V0), "V_end_m3": float(V1),
            "V_min_m3": float(Vmin), "V_max_m3": float(Vmax),
            "Rc_geometric_check": float(engine_cfg.Rc),
            "rpm": float(engine_cfg.rpm),
        }

    # ---------------------------------------------------------- validação
    def validate(self) -> List[str]:
        """Erros bloqueantes (lista vazia = ok). Chamada antes de prepare
        e de run — nenhum campo obrigatório é inferido silenciosamente."""
        e: List[str] = []
        if self.adapter not in ADAPTERS:
            e.append(f"cfd.adapter '{self.adapter}' não implementado "
                     f"(válidos: {ADAPTERS}).")
        if self.mode not in MODES:
            e.append(f"cfd.mode '{self.mode}' inválido ({MODES}).")
        elif self.mode == "reactive":
            e.append("cfd.mode 'reactive' ainda não está implementado "
                     "(combustão reativa é uma extensão futura).")
        if not self.case_directory:
            e.append("cfd.case_directory é obrigatório.")
        if self.workers < 1:
            e.append("cfd.workers deve ser ≥ 1.")
        if self.interval_angle_unit not in ANGLE_UNITS:
            e.append("cfd.interval.angle_unit deve ser 'deg' ou 'rad'.")
        if not self.interval_end > self.interval_start:
            e.append("cfd.interval.end deve ser > start.")
        if self.geometry_type != "simplified_cylinder":
            e.append(f"cfd.geometry.type '{self.geometry_type}' não "
                     "suportado (use simplified_cylinder).")
        if self.n_radial < 4 or self.n_axial < 4:
            e.append("cfd.geometry.n_radial e n_axial devem ser ≥ 4.")
        if not self.P0_kPa > 0 or not self.T0_K > 0:
            e.append("cfd.initial.P_kPa e T_K devem ser > 0.")
        if not self.Tw_K > 0:
            e.append("cfd.walls.Tw_K deve ser > 0.")
        if self.wall_model not in ("fixed_temperature", "adiabatic"):
            e.append("cfd.walls.model deve ser fixed_temperature ou "
                     "adiabatic.")
        if self.wall_model == "adiabatic" and self.Tw_K != 440.0:
            e.append("cfd.walls.model=adiabatic não usa Tw_K (paredes sem "
                     "fluxo de calor); omita Tw_K ou use fixed_temperature.")
        if not self.gas_Cp_J_kgK > 0 or not self.gas_molWeight > 0:
            e.append("cfd.gas.Cp_J_kgK e molWeight_kg_kmol devem ser > 0.")
        if not self.gas_mu > 0 or not 0 < self.gas_Pr <= 1.0:
            e.append("cfd.gas.mu_Pa_s deve ser > 0 e Pr em (0, 1].")
        if self.turbulence_model not in ("kEpsilon", "kOmegaSST", "laminar"):
            e.append("cfd.turbulence.model deve ser kEpsilon, kOmegaSST "
                     "ou laminar.")
        if not self.deltaT_s > 0 or not self.max_Co > 0:
            e.append("cfd.numerics.deltaT_s e max_Co devem ser > 0.")
        if not self.write_interval_deg > 0:
            e.append("cfd.numerics.write_interval_deg deve ser > 0.")
        if self.distribution not in DISTRIBUTIONS:
            e.append(f"cfd.heat_source.distribution '{self.distribution}' "
                     f"inválida ({DISTRIBUTIONS}).")
        if self.distribution == "region" and not self.region:
            e.append("distribution=region exige cfd.heat_source.region "
                     "(nome do cellZone).")
        if self.fuel_name not in fuel_names():
            e.append(f"cfd.fuel.name '{self.fuel_name}' inválida "
                     f"(válidos: {fuel_names()}).")
        if self.fuel_feed not in ("premixed_gas",):
            e.append("cfd.fuel.feed: apenas 'premixed_gas' no modo de calor "
                     "prescrito (injeção líquida/spray é futura).")
        if self.experimental:
            if self.experimental_angle_unit not in ("rad", "deg"):
                e.append("cfd.comparison.experimental_angle_unit deve ser "
                         "'rad' ou 'deg'.")
            from ..pressure.fit import PRESSURE_FACTORS_KPA
            if self.experimental_pressure_unit not in PRESSURE_FACTORS_KPA:
                e.append("cfd.comparison.experimental_pressure_unit inválida "
                         f"({list(PRESSURE_FACTORS_KPA)}).")
        if self.wiebe_source not in ("model", "parameters"):
            e.append("cfd.wiebe.source deve ser 'model' (model.json) ou "
                     "'parameters' (lista inline).")
        if self.wiebe_source == "model" and not self.wiebe_model:
            e.append("cfd.wiebe.source=model exige cfd.wiebe.model "
                     "(caminho de um model.json gerado pelo wiebepy).")
        if self.wiebe_source == "parameters" and not self.wiebe_parameters:
            e.append("cfd.wiebe.source=parameters exige a lista "
                     "cfd.wiebe.parameters.")
        if self.wiebe_source == "model" and self.wiebe_model:
            if not Path(self.wiebe_model).exists():
                e.append(f"cfd.wiebe.model não encontrado: {self.wiebe_model}")
        return e

    def load_wiebe_stages(self, angle_unit_deg: bool = True):
        """Carrega os estágios Wiebe (lista de Stage/dicts) na unidade
        angular do modo pressão do wiebepy (rad).

        O model.json do wiebepy guarda θ0/Δθ em rad; parâmetros inline
        são interpretados na unidade de ``interval.angle_unit`` e
        convertidos para rad.
        """
        import math
        from ..core.parameters import as_stages
        if self.wiebe_source == "model":
            from ..model import MultiStageWiebe
            return MultiStageWiebe.load(self.wiebe_model).stages
        p = [dict(s) for s in self.wiebe_parameters]
        if self.interval_angle_unit == "deg":
            for s in p:
                s["theta0"] = math.radians(float(s["theta0"]))
                s["duration"] = math.radians(float(s["duration"]))
        return as_stages(p)


# ------------------------------------------------------------- integração
def cfd_section_defaults() -> Dict:
    """Seção ``cfd`` padrão — adicionada a io/config.DEFAULTS para que
    arquivos com ``cfd:`` sejam aceitos. Com ``enabled: false`` nada muda
    no comportamento existente."""
    return CfdConfig().to_dict_public()


def cfd_config_from_cfg(cfg: Dict) -> CfdConfig:
    """Extrai e valida a seção cfd de uma configuração resolvida."""
    return CfdConfig.from_dict((cfg or {}).get("cfd") or {})


def state_path(case_dir: Path) -> Path:
    return Path(case_dir) / "case_state.json"


def read_state(case_dir) -> CaseState:
    p = state_path(case_dir)
    if not p.exists():
        return CaseState.NOT_CONFIGURED
    try:
        return CaseState(json.loads(p.read_text(encoding="utf-8"))["state"])
    except Exception:                                   # noqa: BLE001
        return CaseState.NOT_CONFIGURED


def write_state(case_dir, state: CaseState, **extra) -> None:
    p = state_path(case_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    d = {"state": state.value, **extra}
    p.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")