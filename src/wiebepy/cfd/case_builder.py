# -*- coding: utf-8 -*-
"""
case_builder.py — Gera o caso OpenFOAM a partir da configuração CFD
(``CfdConfig``), da geometria do motor (EngineConfig existente) e dos
estágios Wiebe carregados do núcleo (sem duplicar a formulação).

O caso usa o OpenFOAM Foundation 13 (adapter openfoam):
  • solver ``fluid`` (foamRun) — transiente compressível, energia;
  • userTime ``engine`` (o tempo do solver é o ângulo de manivela em
    graus — CA);
  • malha blockMesh de cilindro paramétrico (pistão plano);
  • mover ``multiValveEngine`` (só pistão) com
    ``crankConnectingRodMotion`` quando moving_piston;
  • fvModel ``heatSource`` (cellZone all/região) com q''' prescrito
    diretamente como ``table`` (CA [°], Q̇/V₀(CA) [W/m³]) gerado a partir
    da Wiebe — conservativo com malha móvel;
  • functionObjects: médias/integrais volumétricas (p, T, rho), min/max
    de T, fluxo térmico nas paredes.

Propriedades do gás: ar simplificado (perfectGas, Cp e mu constantes) —
hipótese declarada; o κ do 0-D e a correlação de Hohenberg NÃO são
transferidos para o CFD (o solver calcula a troca térmica nas paredes).
"""
from __future__ import annotations

import math
import shutil
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from .config import CfdConfig
from .fuels import fuel_summary
from .geometry import PistonKinematics, motion_report
from .sources.wiebe_heat_release import (distribution_notice, energy_check,
                                         table_text, table_text_density)

FOAMFILE = """/*--------------------------------*- C++ -*------------------*\\
  =========                 |
  \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\\\    /   O peration     | Website:  https://openfoam.org
    \\\\  /   A nd           | Version:  13
     \\/     M anipulation  |
\\*---------------------------------------------------------------------------*/
FoamFile
{{
    format      ascii;
    class       {cls};
    location    "{loc}";
    object      {obj};
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

{body}
// ************************************************************************* //
"""


def _dict_file(cls: str, loc: str, obj: str, body: str) -> str:
    return FOAMFILE.format(cls=cls, loc=loc, obj=obj, body=body.rstrip()
                           + "\n")


def _fmt(x: float, nd: int = 9) -> str:
    """Número para dicionário OpenFOAM (ponto decimal sempre)."""
    s = f"{x:.{nd}g}"
    if "e" not in s and "." not in s:
        s += ".0"
    return s


def _timename(x: float) -> str:
    """Nome do diretório de tempo no formato do OpenFOAM (timeFormat
    general, timePrecision 6): -120.0 → "-120" (sem zeros à direita)."""
    return f"{x:.6g}"


class CaseBuilder:
    """Constrói o caso OpenFOAM no diretório dado."""

    def __init__(self, cfg: CfdConfig, engine, solver_info: Optional[Dict] = None,
                 heat_enabled: bool = True, moving_override: Optional[bool] = None):
        self.cfg = cfg
        self.engine = engine          # pressure.engine.EngineConfig
        self.solver_info = solver_info or {}
        self.heat_enabled = heat_enabled
        self.moving = (cfg.moving_piston if moving_override is None
                       else moving_override)
        self.kin = PistonKinematics(bore=engine.bore, stroke=engine.stroke,
                                    rod_length=engine.rod_length,
                                    Rc=engine.Rc, rpm=engine.rpm)
        a0 = self.theta_start_rad
        self.fuel = fuel_summary(cfg.fuel_name, engine.m_fuel)
        # os estágios Wiebe são carregados em RAD (config.load_wiebe_stages
        # converte deg→rad) e theta_grid() retorna rad — a unidade angular
        # passada às funções da fonte deve ser a DO ARRAY θ, não a da
        # configuração do intervalo
        self.energy_check = energy_check(
            self.theta_grid(), self.load_stages(), engine.m_fuel,
            engine.LHV, "rad", engine.rpm)
        self.motion = motion_report(self.kin, a0, self.theta_end_rad)

    # ------------------------------------------------------------ utilidades
    def load_stages(self):
        return self.cfg.load_wiebe_stages()

    @property
    def theta_start_rad(self) -> float:
        return (math.radians(self.cfg.interval_start)
                if self.cfg.interval_angle_unit == "deg"
                else self.cfg.interval_start)

    @property
    def theta_end_rad(self) -> float:
        return (math.radians(self.cfg.interval_end)
                if self.cfg.interval_angle_unit == "deg"
                else self.cfg.interval_end)

    def theta_grid(self, step_deg: float = 0.1) -> np.ndarray:
        a0, a1 = self.theta_start_rad, self.theta_end_rad
        step = math.radians(step_deg)
        n = max(2, int(math.ceil((a1 - a0) / step)) + 1)
        return np.linspace(a0, a1, n)

    # ------------------------------------------------------------ geometria
    def chamber_height_at(self, theta_rad: float) -> float:
        """Altura da câmara em θ: V(θ)/A (A = área do pistão)."""
        A = math.pi * (self.engine.bore / 2.0) ** 2
        V = self.kin.volume(theta_rad)
        return V / A

    # ------------------------------------------------------------ arquivos
    def build(self, case_dir) -> Path:
        """Gera o caso completo. Retorna o diretório do caso."""
        case_dir = Path(case_dir)
        if case_dir.exists():
            shutil.rmtree(case_dir)
        # Os campos iniciais vão no diretório nomeado pelo TEMPO INICIAL:
        # com userTime engine, o tempo do solver é o CA (graus) e o
        # OpenFOAM procura os campos no diretório do startTime (ex. -120).
        t0 = _timename(math.degrees(self.theta_start_rad))
        for sub in (t0, "constant", "system"):
            (case_dir / sub).mkdir(parents=True)
        self._write_fields(case_dir / t0)
        self._write_constant(case_dir / "constant")
        self._write_system(case_dir / "system")
        self._write_case_docs(case_dir)
        _normalize_lf(case_dir)
        return case_dir

    # ------------------------------------------------------------------ 0/
    def _write_fields(self, d: Path) -> None:
        P0 = self.cfg.P0_kPa * 1e3           # kPa → Pa (conversão explícita)
        T0 = self.cfg.T0_K
        turb = self.cfg.turbulence_model != "laminar"
        Tw = self.cfg.Tw_K

        d.joinpath("p").write_text(_dict_file("volScalarField", "", "p", f"""
dimensions      [1 -1 -2 0 0 0 0];

internalField   uniform {_fmt(P0)};

boundaryField
{{
    piston
    {{
        type            zeroGradient;
    }}
    liner
    {{
        type            zeroGradient;
    }}
    head
    {{
        type            zeroGradient;
    }}
}}"""), encoding="utf-8")

        d.joinpath("T").write_text(_dict_file("volScalarField", "", "T", f"""
dimensions      [0 0 0 1 0 0 0];

internalField   uniform {_fmt(T0)};

boundaryField
{{
    piston
    {{
        type            fixedValue;
        value            uniform {_fmt(Tw)};
    }}
    liner
    {{
        type            fixedValue;
        value            uniform {_fmt(Tw)};
    }}
    head
    {{
        type            fixedValue;
        value            uniform {_fmt(Tw)};
    }}
}}"""), encoding="utf-8")

        d.joinpath("U").write_text(_dict_file("volVectorField", "", "U", f"""
dimensions      [0 1 -1 0 0 0 0];

internalField   uniform (0 0 0);

boundaryField
{{
    piston
    {{
        type            {('movingWallVelocity', 'noSlip')[not self.moving]};
        value           uniform (0 0 0);
    }}
    liner
    {{
        type            noSlip;
    }}
    head
    {{
        type            noSlip;
    }}
}}"""), encoding="utf-8")

        if turb:
            d.joinpath("k").write_text(_dict_file("volScalarField", "", "k", """
dimensions      [0 2 -2 0 0 0 0];

internalField   uniform 1.0;

boundaryField
{
    piston { type kqRWallFunction; value uniform 1.0; }
    liner  { type kqRWallFunction; value uniform 1.0; }
    head   { type kqRWallFunction; value uniform 1.0; }
}"""), encoding="utf-8")
            d.joinpath("epsilon").write_text(_dict_file("volScalarField", "",
                                                        "epsilon", """
dimensions      [0 2 -3 0 0 0 0];

internalField   uniform 100.0;

boundaryField
{
    piston { type epsilonWallFunction; value uniform 100.0; }
    liner  { type epsilonWallFunction; value uniform 100.0; }
    head   { type epsilonWallFunction; value uniform 100.0; }
}"""), encoding="utf-8")
            d.joinpath("nut").write_text(_dict_file("volScalarField", "",
                                                    "nut", """
dimensions      [0 2 -1 0 0 0 0];

internalField   uniform 0;

boundaryField
{
    piston { type nutkWallFunction; value uniform 0; }
    liner  { type nutkWallFunction; value uniform 0; }
    head   { type nutkWallFunction; value uniform 0; }
}"""), encoding="utf-8")
            d.joinpath("alphat").write_text(_dict_file("volScalarField", "",
                                                       "alphat", """
dimensions      [1 -1 -1 0 0 0 0];

internalField   uniform 0;

boundaryField
{
    piston { type compressible::alphatWallFunction; Prt 0.85; value uniform 0; }
    liner  { type compressible::alphatWallFunction; Prt 0.85; value uniform 0; }
    head   { type compressible::alphatWallFunction; Prt 0.85; value uniform 0; }
}"""), encoding="utf-8")

    # ------------------------------------------------------------ constant/
    def _write_constant(self, d: Path) -> None:
        # Propriedades do ar — VALORES SIMPLIFICADOS declarados (§9). Não
        # são os κ/Hohenberg do 0-D: o CFD resolve a energia e a troca
        # térmica nas paredes por si.
        d.joinpath("physicalProperties").write_text(_dict_file("dictionary",
                                                               "constant",
                                                               "physicalProperties", """
thermoType
{
    type            heRhoThermo;
    mixture         pureMixture;
    transport       const;
    thermo          hConst;
    equationOfState perfectGas;
    specie          specie;
    energy          sensibleEnthalpy;
}

mixture
{
    specie
    {
        molWeight       28.96;
    }
    thermodynamics
    {
        Cp              1005;
        hf              0;
    }
    transport
    {
        mu              5.5e-05;
        Pr              0.7;
    }
}"""), encoding="utf-8")

        if self.cfg.turbulence_model == "laminar":
            d.joinpath("momentumTransport").write_text(_dict_file(
                "dictionary", "constant", "momentumTransport",
                "simulationType  laminar;\n"), encoding="utf-8")
        else:
            d.joinpath("momentumTransport").write_text(_dict_file(
                "dictionary", "constant", "momentumTransport", f"""
simulationType  RAS;

RAS
{{
    model           {self.cfg.turbulence_model};
    turbulence      on;
    printCoeffs     on;
}}"""), encoding="utf-8")

        # mover do pistão (malha móvel)
        if self.moving:
            l_m = self.engine.rod_length
            s_m = self.engine.stroke
            d.joinpath("dynamicMeshDict").write_text(_dict_file(
                "dictionary", "constant", "dynamicMeshDict", f"""
mover
{{
    type            multiValveEngine;

    libs            ("libfvMeshMoversMultiValveEngine.so");

    slidingPatches  (liner);

    linerPatches    (liner);

    piston
    {{
        patches         (piston);

        axis            (0 0 1);

        motion
        {{
            type            crankConnectingRodMotion;
            conRodLength    {_fmt(l_m)};
            stroke          {_fmt(s_m)};
        }}
    }}
}}"""), encoding="utf-8")

        # fonte de calor Wiebe (fvModel nativo, conservativo)
        # OpenFOAM 13: o modo ``Q`` (potência total) do heatSource divide a
        # potência pelo volume da cellZone CONGELADO na construção — com
        # malha móvel (pistão) a fonte deixa de ser conservativa. Por isso
        # prescrevemos a densidade q'''(CA) = Q̇(CA)/V₀(CA) diretamente
        # (distribuição uniforme, Σᵢ q'''ᵢ·Vᵢᵃᵗᵘᵃˡ = Q̇ sobre os volumes
        # atuais). No modo ``region`` o volume da zona não é conhecido na
        # geração do caso: mantém-se Q com a limitação registrada.
        if self.heat_enabled:
            th = self.theta_grid()
            zona = ("all" if self.cfg.distribution == "uniform"
                    else self.cfg.region)
            if self.cfg.distribution == "uniform":
                campo = "q"          # q''' [W/m³]
                comentario = ("q''' [W/m³] = Q̇(CA)/V₀(CA) — conservativo "
                              "com malha móvel (Σᵢ q'''ᵢ·Vᵢ = Q̇)")
                tabela = table_text_density(
                    th, self.load_stages(), self.engine.m_fuel,
                    self.engine.LHV, "rad", self.engine.rpm,
                    self.kin.volume(th))
            else:                    # region: limitação documentada abaixo
                campo = "Q"          # Q̇ [W] (não conservativo c/ malha móvel)
                comentario = ("Q̇ [W] — NÃO conservativo com malha móvel "
                              "no OF13 (limitação em case_config.yaml)")
                tabela = table_text(th, self.load_stages(),
                                    self.engine.m_fuel, self.engine.LHV,
                                    "rad", self.engine.rpm)
            d.joinpath("fvModels").write_text(_dict_file(
                "dictionary", "constant", "fvModels", f"""
wiebeHeatSource
{{
    type            heatSource;

    cellZone        {zona};

    {campo}
    {{
        type            table;
        // tempo do solver = CA [graus] (userTime engine); {comentario}
        values
{tabela}
    }}
}}"""), encoding="utf-8")

        # topoSet: geração da região (distribution=region) — caixa axial
        if self.heat_enabled and self.cfg.distribution == "region" \
                and self.cfg.region:
            h0 = self.chamber_height_at(self.theta_start_rad)
            r = self.engine.bore / 2.0
            zmax = h0 * 0.5   # metade inferior: hipótese declarada do usuário
            d.joinpath("system").joinpath("topoSetDict").write_text(
                _dict_file("dictionary", "system", "topoSetDict", f"""
actions
(
    {{
        name    {self.cfg.region};
        type    cellZoneSet;
        action  new;
        source  boxToCell;
        box     (-{_fmt(r)} -{_fmt(r)} -0.01) ({_fmt(r)} {_fmt(r)} {_fmt(zmax)});
    }}
);"""), encoding="utf-8")

    # -------------------------------------------------------------- system/
    def _write_system(self, d: Path) -> None:
        c = self.cfg
        a0 = self.theta_start_rad
        a1 = self.theta_end_rad
        turb = c.turbulence_model != "laminar"

        d.joinpath("controlDict").write_text(_dict_file(
            "dictionary", "system", "controlDict", f"""
solver          fluid;

userTime
{{
    type            engine;
    omega           {_fmt(self.engine.rpm)} [rpm];
}}

startFrom       startTime;

// mesmo formato do nome do diretório de tempo (_timename): o OpenFOAM
// procura os campos iniciais no diretório startTime (ex. "-120", não "-120.0")
startTime       {_timename(math.degrees(a0))};

stopAt          endTime;

endTime         {_fmt(math.degrees(a1))};

deltaT          0.01;

adjustTimeStep  yes;

maxCo           {_fmt(c.max_Co)};

maxDeltaT       0.5;

writeControl    adjustableRunTime;

writeInterval   {_fmt(c.write_interval_deg)};

purgeWrite      0;

writeFormat     binary;

writePrecision  8;

writeCompression off;

timeFormat      general;

timePrecision   6;

runTimeModifiable true;

functions
{{
    gasAvg
    {{
        type            volFieldValue;
        libs            ("libfieldFunctionObjects.so");
        cellZone        all;
        operation       volAverage;
        writeFields     no;
        fields          (p T rho);
    }}
    gasIntegral
    {{
        type            volFieldValue;
        libs            ("libfieldFunctionObjects.so");
        cellZone        all;
        operation       volIntegrate;
        writeFields     no;
        fields          (rho);
    }}
    gasMin
    {{
        type            volFieldValue;
        libs            ("libfieldFunctionObjects.so");
        cellZone        all;
        operation       min;
        writeFields     no;
        fields          (T p);
    }}
    gasMax
    {{
        type            volFieldValue;
        libs            ("libfieldFunctionObjects.so");
        cellZone        all;
        operation       max;
        writeFields     no;
        fields          (T p);
    }}
    wallHeatFlux
    {{
        type            wallHeatFlux;
        libs            ("libfieldFunctionObjects.so");
        patches         (piston liner head);
    }}
}}"""), encoding="utf-8")

        d.joinpath("fvSchemes").write_text(_dict_file(
            "dictionary", "system", "fvSchemes", """
ddtSchemes
{
    default         Euler;
}

gradSchemes
{
    default         Gauss linear;
}

divSchemes
{
    default         none;
    div(phi,U)      Gauss upwind;
    div(phi,h)      Gauss upwind;
    div(phi,e)      Gauss upwind;
    div(phi,(p|rho)) Gauss upwind;
    div(phi,k)      Gauss upwind;
    div(phi,epsilon) Gauss upwind;
    div(phi,R)      Gauss upwind;
    div(phi,K)      Gauss linear;
    div(phi,Ekp)    Gauss linear;
    div(R)          Gauss linear;
    div(((rho*nuEff)*dev2(T(grad(U))))) Gauss linear;
}

laplacianSchemes
{
    default         Gauss linear corrected;
}

interpolationSchemes
{
    default         linear;
}

snGradSchemes
{
    default         corrected;
}"""), encoding="utf-8")

        d.joinpath("fvSolution").write_text(_dict_file(
            "dictionary", "system", "fvSolution", f"""
solvers
{{
    "rho.*"
    {{
        solver          PCG;
        preconditioner  DIC;
        tolerance       0;
        relTol          0;
    }}

    p
    {{
        solver          PCG;
        preconditioner  DIC;
        tolerance       1e-08;
        relTol          0.01;
    }}

    pFinal
    {{
        $p;
        relTol          0;
    }}

    pcorr
    {{
        solver          PCG;
        preconditioner  DIC;
        tolerance       1e-05;
        relTol          0;
    }}

    "(U|h|e|k|epsilon|R)"
    {{
        solver          PBiCGStab;
        preconditioner  DILU;
        tolerance       1e-06;
        relTol          0.1;
    }}

    "(U|h|e|k|epsilon|R)Final"
    {{
        $U;
        relTol          0;
    }}
}}

PIMPLE
{{
    momentumPredictor yes;
    nOuterCorrectors 2;
    nCorrectors     2;
    nNonOrthogonalCorrectors 0;
}}"""), encoding="utf-8")

        d.joinpath("blockMeshDict").write_text(
            self._blockmesh_dict(), encoding="utf-8")

        if self.cfg.workers > 1:
            n = self.cfg.workers
            d.joinpath("decomposeParDict").write_text(_dict_file(
                "dictionary", "system", "decomposeParDict", f"""
numberOfSubdomains  {n};

method              scotch;"""), encoding="utf-8")

    def _blockmesh_dict(self) -> str:
        """Cilindro paramétrico: pistão em z=0, cabeçote em z=h(θ_ini).

        A seção circular é obtida com um único bloco hexaedral cujos 4
        vértices estão no círculo (a 45°, 135°, 225°, 315°) e cujas 8
        arestas laterais são ``arc`` — a fronteira é exatamente o
        cilindro de raio ``r`` (volume π r² h = V(θ), consistente com a
        cinemática do 0-D). A malha é gerada NA geometria do instante
        inicial; com o pistão móvel, o mover desloca o patch ``piston``.
        """
        r = self.engine.bore / 2.0
        h = self.chamber_height_at(self.theta_start_rad)
        nr = self.cfg.n_radial
        nz = self.cfg.n_axial
        d = r * math.sqrt(2.0) / 2.0    # vértices no círculo, a 45°
        return _dict_file("dictionary", "system", "blockMeshDict", f"""
convertToMeters 1;

vertices
(
    ({_fmt(d)} {_fmt(-d)} 0)
    ({_fmt(d)} {_fmt(d)} 0)
    ({_fmt(-d)} {_fmt(d)} 0)
    ({_fmt(-d)} {_fmt(-d)} 0)
    ({_fmt(d)} {_fmt(-d)} {_fmt(h)})
    ({_fmt(d)} {_fmt(d)} {_fmt(h)})
    ({_fmt(-d)} {_fmt(d)} {_fmt(h)})
    ({_fmt(-d)} {_fmt(-d)} {_fmt(h)})
);

blocks
(
    hex (0 1 2 3 4 5 6 7) ({nr} {nr} {nz}) simpleGrading (1 1 1)
);

edges
(
    arc 0 1 ({_fmt(r)} 0 0)
    arc 1 2 (0 {_fmt(r)} 0)
    arc 2 3 ({_fmt(-r)} 0 0)
    arc 3 0 (0 {_fmt(-r)} 0)
    arc 4 5 ({_fmt(r)} 0 {_fmt(h)})
    arc 5 6 (0 {_fmt(r)} {_fmt(h)})
    arc 6 7 ({_fmt(-r)} 0 {_fmt(h)})
    arc 7 4 (0 {_fmt(-r)} {_fmt(h)})
);

boundary
(
    piston
    {{
        type wall;
        faces
        (
            (0 3 2 1)
        );
    }}
    head
    {{
        type wall;
        faces
        (
            (4 5 6 7)
        );
    }}
    liner
    {{
        type wall;
        faces
        (
            (0 1 5 4)
            (1 2 6 5)
            (2 3 7 6)
            (3 0 4 7)
        );
    }}
);

mergePatchPairs
(
);""")

    # ------------------------------------------------------- docs do caso
    def _write_case_docs(self, case_dir: Path) -> None:
        import yaml
        deriv = self.cfg.derived(self.engine)
        info = {
            "created": datetime.now().isoformat(timespec="seconds"),
            "wiebepy_version": _version(),
            "solver": self.solver_info,
            "mode": self.cfg.mode,
            "adapter": self.cfg.adapter,
            "features": {"moving_piston": self.moving,
                         "heat_source": self.heat_enabled},
            "physics_scope": (
                "Calor prescrito pela função Wiebe calibrada — NÃO prevê "
                "cinética química, frente de chama ou emissões."),
            "fuel": self.fuel,
            "engine": asdict(self.engine),
            "wiebe_stages": [s.to_dict() for s in self.load_stages()],
            "heat_source": {
                "distribution": self.cfg.distribution,
                "region": self.cfg.region,
                "table_form": ("q_density_W_per_m3"
                               if self.cfg.distribution == "uniform"
                               else "total_power_W"),
                "notice": distribution_notice(self.cfg.distribution),
                "energy_check": self.energy_check},
            "motion": self.motion,
            "numerics": {"deltaT_CA_deg": 0.01, "max_Co": self.cfg.max_Co,
                         "time_is_crank_angle_deg": True},
            "initial_conditions": {"P_Pa": self.cfg.P0_kPa * 1e3,
                                   "T_K": self.cfg.T0_K},
            "walls": {"model": "fixed_temperature", "Tw_K": self.cfg.Tw_K},
            "turbulence": {"model": self.cfg.turbulence_model,
                           "wall_functions": self.cfg.wall_functions},
            "gas_model": {
                "eos": "perfectGas", "Cp_J_kgK": 1005.0,
                "mu_Pa_s": 5.5e-5, "Pr": 0.7,
                "notice": "Ar simplificado (propriedades constantes). O κ "
                          "do modelo 0-D e a correlação de Hohenberg não "
                          "são transferidos para o CFD; a troca térmica "
                          "nas paredes é calculada pelo solver."},
            "interval": {"angle_unit": "CA_deg", "start": self.cfg.interval_start,
                         "end": self.cfg.interval_end, **deriv},
            "configuration": self.cfg.to_dict_public(),
        }
        p = case_dir / "case_config.yaml"
        p.write_text(yaml.safe_dump(_plain(info), sort_keys=False,
                                    allow_unicode=True), encoding="utf-8")
        (case_dir / "README.md").write_text(
            f"# Caso CFD gerado pelo wiebepy ({self.cfg.mode})\n\n"
            f"- Caso: {case_dir.name} — criado em {info['created']}\n"
            f"- Solver: OpenFOAM {self.solver_info.get('version', '?')} "
            f"(adapter openfoam)\n"
            f"- Janela simulada: CA {self.cfg.interval_start}° a "
            f"{self.cfg.interval_end}° (válvulas fechadas)\n"
            f"- Energia da fonte Wiebe: {self.energy_check['integral_J']:.1f} J "
            f"(erro {self.energy_check['rel_error']:.2e})\n\n"
            f"## Execução\n\n    wiebepy cfd run --case \"{case_dir}\"\n\n"
            "## Limitações\n\n"
            "- A combustão é prescrita (curva Wiebe); não há previsão de "
            "chama, cinética ou emissões.\n"
            "- Geometria simplificada de cilindro (sem válvulas/dome).\n\n"
            "Detalhes completos em case_config.yaml.\n", encoding="utf-8")


def _normalize_lf(case_dir: Path) -> None:
    """Converte CRLF→LF em todos os arquivos do caso: no Windows,
    ``write_text`` traduz \\n para \\r\\n e o parser de listas do
    OpenFOAM não tolera \\r (erro "ill defined primitiveEntry")."""
    for p in case_dir.rglob("*"):
        if p.is_file():
            b = p.read_bytes()
            if b"\r\n" in b:
                p.write_bytes(b.replace(b"\r\n", b"\n"))


def _version() -> str:
    from .. import __version__
    return __version__


def _plain(o):
    import numpy as np
    if isinstance(o, dict):
        return {str(k): _plain(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_plain(v) for v in o]
    if isinstance(o, np.generic):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    return o


__all__ = ["CaseBuilder"]