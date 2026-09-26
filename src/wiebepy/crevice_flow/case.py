# -*- coding: utf-8 -*-
"""
case.py — Geração do caso OpenFOAM do submodelo de fresta (crevice_flow).

Solver: ``fluid`` (compressível transiente, OpenFOAM Foundation 13), NÃO
reativo, laminar (justificativa: Re na folga é tipicamente ~10²–10³ para
folgas de 0,1–1 mm e velocidades de dezenas de m/s — estimativa impressa
no relatório; um modelo de turbulência não é ativado por se tratar de um
motor). Condição de contorno da câmara com inversão de fluxo:

    totalPressure  → uniformTotalPressure (p0 = Function1 tabela de tempo;
                     ψ ativado com γ do gás)
    staticPressure → uniformFixedValue (valor estático p(t))

Convenção de sinais (declarada no relatório): a vazão de ``phi`` no
OpenFOAM é positiva para fluxo SAINDO do domínio; massa acumulada de
entrada e saída é separada em results.py por sinal.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from .config import (CreviceConfig, ChamberBC, read_pressure_table)
from .geometry import CreviceDomain, piston_speed_table, DESCRICAO_DOMINIO


def _dict_file(kind, location, obj, body) -> str:
    """Mesmo cabeçalho FoamFile usado nos casos de câmara do wiebepy."""
    return f"""/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\\\  /  F ield         | OpenFOAM: The Open Source CFD Toolbox            |
|  \\\\  /  O peration     | Website:  https://openfoam.org                   |
|   \\\\  /    A nd         | Version:  13                                     |
|    \\\\/   M anipulation  | gerado por wiebepy.crevice_flow                  |
\\*---------------------------------------------------------------------------*/
FoamFile
{{
    format          ascii;
    class           {kind};
    location        "{location}";
    object          {obj};
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

{body}"""


def _fmt(x) -> str:
    return f"{float(x):.8g}"


class CreviceCaseBuilder:
    """Escreve o caso completo a partir da CreviceConfig."""

    def __init__(self, cfg: CreviceConfig,
                 solver_info: Optional[Dict] = None):
        self.cfg = cfg
        self.solver_info = dict(solver_info or {})
        self.dom = CreviceDomain(cfg)
        self.dom.validate()
        # tabela p(θ) → p(t) em Pa, conversão explícita (§5/§6); o tempo
        # do SOLVER começa em 0 no início da janela (θ não pode gerar t<0
        # para as Function1 do OpenFOAM)
        th, p = read_pressure_table(cfg.chamber.file, cfg.chamber)
        self._interp = (np.array(th), np.array(p))
        self.t_end = cfg.theta_to_t(cfg.window[1] - cfg.window[0])
        self.t_start = 0.0

    # ------------------------------------------------------------ tabelas
    def t_de_theta(self, theta_deg: float) -> float:
        """θ [°] absoluto → t [s] do solver (0 no início da janela)."""
        return self.cfg.theta_to_t(theta_deg - self.cfg.window[0])
    def _p_em(self, th_deg) -> np.ndarray:
        th, p = self._interp
        return np.interp(th_deg, th, p)

    def _pressure_table_pairs(self, n: int = 721) -> str:
        """(t [s], p [Pa]) da janela, amostrada em n pontos."""
        ths = np.linspace(self.cfg.window[0], self.cfg.window[1], n)
        ps = self._p_em(ths)
        return "\n".join(
            f"    ({self.t_de_theta(t):.8g} {_fmt(pv)})"
            for t, pv in zip(ths, ps))

    # -------------------------------------------------------------- 0/
    def _tw_bc(self, v) -> str:
        """BC térmica de parede: temperatura prescrita ou adiabática."""
        if v == "adiabatic":
            return "type            zeroGradient;"
        return ("type            fixedValue;\n        value"
                f"            uniform {_fmt(v)};")

    def _write_fields(self, d: Path) -> None:
        cfg = self.cfg
        f0 = d / "0"
        f0.mkdir(parents=True, exist_ok=True)
        p0 = float(self._p_em(cfg.window[0]))
        t_in = cfg.chamber.inflow_T_K

        def Tw(v, nome):
            return ("zeroGradient" if v == "adiabatic"
                    else f"type            fixedValue;\n            value"
                         f"            uniform {_fmt(v)};"), (
                    "zeroGradient;" if v == "adiabatic"
                    else f"fixedValue {_fmt(v)}")

        # ------------------------------------------------------------- U
        vz_parede = ""
        if cfg.motion.liner_wall_velocity:
            th_v, vz = piston_speed_table(cfg)
            pares = "\n".join(
                f"    ({self.t_de_theta(t):.8g} (0 0 {-v:.8g}))"
                for t, v in zip(th_v, vz))
            vz_parede = f"""
            type            uniformFixedValue;
            uniformValue    table
            (
{pares}
            );
"""
        else:
            vz_parede = """
            type            noSlip;
"""
        (f0 / "U").write_text(_dict_file("volVectorField", "0", "U", f"""
dimensions      [0 1 -1 0 0 0 0];

internalField   uniform (0 0 0);

boundaryField
{{
    chamber
    {{
        type            pressureInletOutletVelocity;
        value           uniform (0 0 0);
    }}
    liner
    {{{vz_parede}    }}
    piston
    {{
        type            noSlip;
    }}
    front
    {{
        type            wedge;
    }}
    back
    {{
        type            wedge;
    }}
}}"""), encoding="utf-8")

        # ------------------------------------------------------------- p
        if cfg.chamber.bc_type == "totalPressure":
            p_bc = f"""
        type            uniformTotalPressure;
        p0              table
        (
{self._pressure_table_pairs()}
        );
        psi             psi;
        gamma           {_fmt(cfg.gas['gamma'])};
"""
        else:
            p_bc = f"""
        type            uniformFixedValue;
        uniformValue    table
        (
{self._pressure_table_pairs()}
        );
"""
        (f0 / "p").write_text(_dict_file("volScalarField", "0", "p", f"""
dimensions      [1 -1 -2 0 0 0 0];

internalField   uniform {_fmt(p0)};

boundaryField
{{
    chamber
    {{{p_bc}    }}
    liner
    {{
        type            zeroGradient;
    }}
    piston
    {{
        type            zeroGradient;
    }}
    front
    {{
        type            wedge;
    }}
    back
    {{
        type            wedge;
    }}
}}"""), encoding="utf-8")

        # ------------------------------------------------------------- T
        (f0 / "T").write_text(_dict_file("volScalarField", "0", "T", f"""
dimensions      [0 0 0 1 0 0 0];

internalField   uniform {_fmt(t_in)};

boundaryField
{{
    chamber
    {{
        type            inletOutlet;
        inletValue      uniform {_fmt(t_in)};
        value           uniform {_fmt(t_in)};
    }}
    liner
    {{
        {self._tw_bc(cfg.thermal.liner_wall)}
    }}
    piston
    {{
        {self._tw_bc(cfg.thermal.piston_wall)}
    }}
    front
    {{
        type            wedge;
    }}
    back
    {{
        type            wedge;
    }}
}}"""), encoding="utf-8")

    # --------------------------------------------------------- constant/
    def _write_constant(self, d: Path) -> None:
        c = d / "constant"
        c.mkdir(parents=True, exist_ok=True)
        g = self.cfg.gas
        r_spec = g["R_specific_J_kgK"]
        gam = g["gamma"]
        # Cp coerente com (γ, R): Cp = γR/(γ−1) — a mesma constatação que
        # liga 287,07 e 1,370 ao Cp 1063 dos casos de câmara (§3d)
        cp = gam * r_spec / (gam - 1.0)
        mol_weight = 8314.47 / r_spec
        c.joinpath("physicalProperties").write_text(_dict_file(
            "dictionary", "constant", "physicalProperties", f"""
thermoType
{{
    type            heRhoThermo;
    mixture         pureMixture;
    transport       const;
    thermo          hConst;
    equationOfState perfectGas;
    specie          specie;
    energy          sensibleEnthalpy;
}}

mixture
{{
    specie
    {{
        molWeight       {_fmt(mol_weight)};
    }}
    thermodynamics
    {{
        Cp              {_fmt(cp)};
        hf              0;
    }}
    transport
    {{
        mu              {_fmt(g['dynamic_viscosity_Pa_s'])};
        Pr              {_fmt(g['Pr'])};
    }}
}}"""), encoding="utf-8")
        c.joinpath("momentumTransport").write_text(_dict_file(
            "dictionary", "constant", "momentumTransport",
            "simulationType  laminar;\n"), encoding="utf-8")

    # ------------------------------------------------------------ system/
    def _write_system(self, d: Path) -> None:
        s = d / "system"
        s.mkdir(parents=True, exist_ok=True)
        cfg = self.cfg
        dom = self.dom
        s.joinpath("blockMeshDict").write_text(dom.blockmesh_dict(),
                                               encoding="utf-8")
        s.joinpath("topoSetDict").write_text(dom.topo_set_dict(),
                                             encoding="utf-8")
        w_int = cfg.theta_to_t(cfg.numerics.write_every_deg)
        (s / "controlDict").write_text(_dict_file(
            "dictionary", "system", "controlDict", f"""
application     foamRun;

solver          fluid;

startFrom       latestTime;
startTime       0;
endTime         {self.t_end:.8g};

deltaT          {cfg.numerics.max_delta_t_s:.8g};

writeControl    adjustableRunTime;
writeInterval   {w_int:.8g};

purgeWrite      0;
writeFormat     binary;
writePrecision  8;
writeCompression off;
timeFormat      general;
timePrecision   6;
runTimeModifiable true;

adjustTimeStep  yes;
maxCo           {cfg.numerics.max_Co:.8g};
maxDeltaT       {cfg.numerics.max_delta_t_s:.8g};

functions
{{
    fluxoMassaCamara
    {{
        type            surfaceFieldValue;
        libs            ("libfieldFunctionObjects.so");
        select          patch;
        patch           chamber;
        operation       sum;
        writeFields     no;
        fields          (phi);
        writeControl    timeStep;
        writeInterval   20;   // ~2e-6 s: resolve o transiente acustico (aliasing a 1 grau: residuo de massa 2.1e-9 kg na demo; fino: 1e-13)
    }}
    pT_camara
    {{
        type            surfaceFieldValue;
        libs            ("libfieldFunctionObjects.so");
        select          patch;
        patch           chamber;
        operation       areaAverage;
        writeFields     no;
        fields          (p T);
        writeControl    timeStep;
        writeInterval   20;   // ~2e-6 s: resolve o transiente acustico (aliasing a 1 grau: residuo de massa 2.1e-9 kg na demo; fino: 1e-13)
    }}
    massaTotal
    {{
        type            volFieldValue;
        libs            ("libfieldFunctionObjects.so");
        select          cellZone;
        cellZone        all;
        operation       volIntegrate;
        writeFields     no;
        fields          (rho);
        writeControl    timeStep;
        writeInterval   20;   // ~2e-6 s: resolve o transiente acustico (aliasing a 1 grau: residuo de massa 2.1e-9 kg na demo; fino: 1e-13)
    }}
    massaFresta
    {{
        type            volFieldValue;
        libs            ("libfieldFunctionObjects.so");
        select          cellZone;
        cellZone        crevice;
        operation       volIntegrate;
        writeFields     no;
        fields          (rho);
        writeControl    timeStep;
        writeInterval   20;   // ~2e-6 s: resolve o transiente acustico (aliasing a 1 grau: residuo de massa 2.1e-9 kg na demo; fino: 1e-13)
    }}
    massaBuffer
    {{
        type            volFieldValue;
        libs            ("libfieldFunctionObjects.so");
        select          cellZone;
        cellZone        buffer;
        operation       volIntegrate;
        writeFields     no;
        fields          (rho);
        writeControl    timeStep;
        writeInterval   20;   // ~2e-6 s: resolve o transiente acustico (aliasing a 1 grau: residuo de massa 2.1e-9 kg na demo; fino: 1e-13)
    }}
    // energia interna por zona: para gás perfeito U = ∫p dV/(γ−1) —
    // o volIntegrate de p dá o balanço de energia sem aproximar T̄
    energiaFresta
    {{
        type            volFieldValue;
        libs            ("libfieldFunctionObjects.so");
        select          cellZone;
        cellZone        crevice;
        operation       volIntegrate;
        writeFields     no;
        fields          (p);
        writeControl    timeStep;
        writeInterval   20;   // ~2e-6 s: resolve o transiente acustico (aliasing a 1 grau: residuo de massa 2.1e-9 kg na demo; fino: 1e-13)
    }}
    energiaBuffer
    {{
        type            volFieldValue;
        libs            ("libfieldFunctionObjects.so");
        select          cellZone;
        cellZone        buffer;
        operation       volIntegrate;
        writeFields     no;
        fields          (p);
        writeControl    timeStep;
        writeInterval   20;   // ~2e-6 s: resolve o transiente acustico (aliasing a 1 grau: residuo de massa 2.1e-9 kg na demo; fino: 1e-13)
    }}
    T_fresta
    {{
        type            volFieldValue;
        libs            ("libfieldFunctionObjects.so");
        select          cellZone;
        cellZone        crevice;
        operation       volAverage;
        writeFields     no;
        fields          (T);
        writeControl    timeStep;
        writeInterval   20;   // T MEDIDA da fresta: h_out = cp*T_fresta no balanco de energia (h_out = T_camara prescrita era a limitacao 7 de crevice.md)
    }}
    fluxoCalorParedes
    {{
        type            wallHeatFlux;
        libs            ("libfieldFunctionObjects.so");
        patches         (liner piston);
        writeControl    timeStep;
        writeInterval   20;   // ~2e-6 s: resolve o transiente acustico (aliasing a 1 grau: residuo de massa 2.1e-9 kg na demo; fino: 1e-13)
    }}
    calorLiner
    {{
        type            surfaceFieldValue;
        libs            ("libfieldFunctionObjects.so");
        select          patch;
        patch           liner;
        operation       areaIntegrate;
        writeFields     no;
        fields          (wallHeatFlux);
        writeControl    timeStep;
        writeInterval   20;   // ~2e-6 s: resolve o transiente acustico (aliasing a 1 grau: residuo de massa 2.1e-9 kg na demo; fino: 1e-13)
    }}
    calorPistao
    {{
        type            surfaceFieldValue;
        libs            ("libfieldFunctionObjects.so");
        select          patch;
        patch           piston;
        operation       areaIntegrate;
        writeFields     no;
        fields          (wallHeatFlux);
        writeControl    timeStep;
        writeInterval   20;   // ~2e-6 s: resolve o transiente acustico (aliasing a 1 grau: residuo de massa 2.1e-9 kg na demo; fino: 1e-13)
    }}
}}"""), encoding="utf-8")

        (s / "fvSchemes").write_text(_dict_file(
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
    div(phi,K)      Gauss linear;
    div(phi,Ekp)    Gauss linear;
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

        (s / "fvSolution").write_text(_dict_file(
            "dictionary", "system", "fvSolution", """
solvers
{
    "rho.*"
    {
        solver          PCG;
        preconditioner  DIC;
        tolerance       0;
        relTol          0;
    }

    p
    {
        solver          PCG;
        preconditioner  DIC;
        tolerance       1e-08;
        relTol          0.01;
    }

    pFinal
    {
        $p;
        relTol          0;
    }

    pcorr
    {
        solver          PCG;
        preconditioner  DIC;
        tolerance       1e-05;
        relTol          0;
    }

    "(U|h|e)"
    {
        solver          PBiCGStab;
        preconditioner  DILU;
        tolerance       1e-06;
        relTol          0.1;
    }

    "(U|h|e)Final"
    {
        $U;
        relTol          0;
    }
}

PIMPLE
{
    momentumPredictor yes;
    nOuterCorrectors 2;
    nCorrectors     2;
    nNonOrthogonalCorrectors 0;
}"""), encoding="utf-8")

    # ---------------------------------------------------------------- build
    def build(self, case_dir) -> Path:
        d = Path(case_dir)
        d.mkdir(parents=True, exist_ok=True)
        self._write_fields(d)
        self._write_constant(d)
        self._write_system(d)
        self.write_case_config(d)
        return d

    def write_case_config(self, d: Path) -> None:
        """case_config.yaml — proveniência completa (hipóteses, origem dos
        dados, hipótese do referencial, convenção de sinais)."""
        import yaml
        cfg = self.cfg
        dom = self.dom
        cd = dom.cell_dims()
        th, p = self._interp
        pico = float(p.max())
        re_est = (pico / (cfg.gas["R_specific_J_kgK"] * cfg.chamber.inflow_T_K)
                  * 50.0 * cd["delta_r_m"]
                  / cfg.gas["dynamic_viscosity_Pa_s"])
        doc = {
            "modulo": "wiebepy.crevice_flow",
            "nivel": "submodelo (fresta comunicando APENAS com a câmara — "
                     "NÃO é simulação de blow-by)",
            "descricao_dominio": DESCRICAO_DOMINIO,
            "solver": "OpenFOAM Foundation 13, foamRun -solver fluid, "
                      "transiente compressível, laminar, não reativo",
            "solver_info": self.solver_info,
            "geometria_mm": {
                "bore_diameter": cfg.geometry.bore_diameter_mm,
                "radial_gap": cfg.geometry.radial_gap_mm,
                "top_land_height": cfg.geometry.top_land_height_mm,
                "buffer_height": cfg.geometry.buffer_height_mm,
                "sector_angle": cfg.geometry.sector_angle_deg},
            "volume_fresta_m3": cfg.geometry.crevice_volume_m3,
            "malha": {"n_cells": cd["n_cells"],
                      "delta_r_m": cd["delta_r_m"],
                      "delta_z_m": cd["delta_z_m"],
                      "aspect_ratio": cd["aspect_ratio"]},
            "condicao_camara": {
                "fonte": cfg.chamber.source,
                "arquivo": str(cfg.chamber.file),
                "p_unit": cfg.chamber.p_unit,
                "theta_unit": cfg.chamber.theta_unit,
                "bc": cfg.chamber.bc_type,
                "pico_Pa": pico,
                "janela_arquivo_deg": [float(th[0]), float(th[-1])],
                "extrapolate": cfg.chamber.extrapolate,
                "inflow_T_K": cfg.chamber.inflow_T_K,
                "inflow_hipotese": "temperatura do gás que entra declarada "
                                   "pelo usuário — a pressão sozinha não "
                                   "determina o estado"},
            "janela_deg": list(cfg.window),
            "tempo_s": [self.t_start, self.t_end],
            "rotacao": {"rpm": cfg.motion.rpm,
                        "dtheta_dt_deg_s": cfg.dtheta_dt_deg_s,
                        "dtheta_dt_rad_s": cfg.dtheta_dt_rad_s},
            "referencial": {
                "frame": "pistão (geometria constante; malha estática)",
                "aceleracao_referencial": "efeitos do referencial "
                    "acelerado (ω²r) negligenciados — hipótese declarada: "
                    "termo de corpo ordens de grandeza menor que os "
                    "gradientes de pressão dirigindo o escoamento na "
                    "fresta",
                "liner_wall_velocity": cfg.motion.liner_wall_velocity},
            "regime": {
                "turbulencia": "laminar — não selecionado automaticamente",
                "Re_estimativa_folga": float(re_est),
                "nota": "estimativa com pico de pressão, v≈50 m/s e escala "
                        "= delta_r; justificativa impressa no relatório"},
            "gas": dict(cfg.gas),
            "gas_provenance": cfg.gas_provenance,
            "convencao_sinais": "phi do OpenFOAM: positivo = fluxo SAINDO "
                                "do domínio; results.py separa entrada e "
                                "saída pelo sinal",
            "balanco_energia": "volume constante no referencial do "
                "domínio (sem trabalho p·dV); dU/dt = −∮h·φ + Q̇_paredes "
                "(trabalho viscoso da parede móvel desprezado, hipótese "
                "declarada)",
            "hipoteses": [
                "fresta isotérmica não é assumida: T é resolvida; paredes "
                "têm temperatura prescrita ou são adiabáticas (config)",
                "sem anéis móveis, sem filme de óleo, sem combustão, sem "
                "transporte de combustível",
                "setor periódico válido: geometria e BCs uniformes na "
                "circunferência (abertura localizada do anel NÃO "
                "representada)"],
            "avisos": list(cfg.notes),
        }
        (d / "case_config.yaml").write_text(
            yaml.safe_dump(doc, allow_unicode=True, sort_keys=False),
            encoding="utf-8")