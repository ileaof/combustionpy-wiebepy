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

MODO REATIVO (mode=reactive, degrau R2 do roadmap reativo):
  • a QUÍMICA fornece o calor — sem fvModels heatSource e SEM Wiebe (as
    duas fontes NUNCA coexistem; regra inviolável do roadmap);
  • mistura homogênea H₂/ar (φ), câmara de volume FIXO (malha fixa no
    volume morto, Vc na PMP, θ=0), ignição espontânea pela cinética —
    sem fonte de calor, sem faísca, sem malha adaptativa;
  • mecanismo convertido pelo chemkinToFoam (ex. Burke et al. 2012) —
    os arquivos `reactions` e `speciesThermo` do mecanismo são COPIADOS
    (nunca redigitados) para constant/ e incluídos por #include;
  • tempo do solver é FÍSICO [s] (sem userTime engine — volume fixo não
    tem manivela), com adjustTimeStepToChemistry;
  • functionObjects: Qdot (campo), ∫Q̇ dV (fechamento de energia) e
    massas por espécie (ρ·Yᵢ).

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


# Espécies do R1 (roadmap reativo, seção 2): ar seco N2 + O2, razão molar
# 3,76:1 (composição padrão do ar). Polinômios NASA (janaf, Tlow 200 /
# Thigh 5000 / Tcommon 1000) e transporte de Sutherland COPIADOS dos
# blocos N2 e O2 do arquivo do tutorial do OF13
#   /opt/openfoam13/tutorials/multicomponentFluid/counterFlowFlame2D/
#   constant/thermo.compressibleGas
# (termoquímica GRI-Mech 3.0 distribuída com o OpenFOAM 13) — extraídos
# mecanicamente, não redigitados. Nada é inventado aqui.
SPECIES_R1 = {
    "N2": {
        "molWeight": 28.0134,
        "Tlow": 200, "Thigh": 5000, "Tcommon": 1000,
        "highCpCoeffs": (2.92664, 0.00148798, -5.68476e-07, 1.0097e-10,
                         -6.75335e-15, -922.798, 5.98053),
        "lowCpCoeffs": (3.29868, 0.00140824, -3.96322e-06, 5.64152e-09,
                        -2.44486e-12, -1020.9, 3.95037),
        "As": 1.401e-6, "Ts": 107,
    },
    "O2": {
        "molWeight": 31.9988,
        "Tlow": 200, "Thigh": 5000, "Tcommon": 1000,
        "highCpCoeffs": (3.69758, 0.00061352, -1.25884e-07, 1.77528e-11,
                         -1.13644e-15, -1233.93, 3.18917),
        "lowCpCoeffs": (3.21294, 0.00112749, -5.75615e-07, 1.31388e-09,
                        -8.76855e-13, -1005.25, 6.03474),
        "As": 1.753e-6, "Ts": 139,
    },
}
# frações mássicas do ar seco (razão molar N2:O2 = 3,76:1)
_MOL_N2 = 3.76 * SPECIES_R1["N2"]["molWeight"]
_Y_N2 = _MOL_N2 / (_MOL_N2 + SPECIES_R1["O2"]["molWeight"])
_Y_O2 = 1.0 - _Y_N2


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
        # O PCI usado na fonte de calor é o do ENSAIO (engine.LHV); a
        # referência típica do registro fica registrada ao lado, com a
        # diferença explicada (ex.: diesel do ensaio ≠ diesel típico).
        if abs(float(engine.LHV) - self.fuel["LHV_kJ_per_kg"]) > 1e-9:
            self.fuel["LHV_kJ_per_kg_engine"] = float(engine.LHV)
            self.fuel["notice"] = (
                "O PCI usado na fonte de calor é o do combustível DO ENSAIO "
                f"({engine.LHV:.1f} kJ/kg, seção engine); a referência típica "
                f"do registro é {self.fuel['LHV_kJ_per_kg']:.1f} kJ/kg "
                "(substituir pela ficha/certificado do combustível real). "
                "No modo prescrito o combustível entra apenas via m_f·PCI; "
                "a composição/surrogate só é relevante no modo reativo "
                "(não implementado).")
        # os estágios Wiebe são carregados em RAD (config.load_wiebe_stages
        # converte deg→rad) e theta_grid() retorna rad — a unidade angular
        # passada às funções da fonte deve ser a DO ARRAY θ, não a da
        # configuração do intervalo
        #
        # A grade da verificação (e da tabela do fvModel) é refinada até o
        # fechamento ∫Q̇dt = m_f·PCI·Δx_b passar no gate (0,1 %): estágios
        # com m pequeno (queima muito "degrau") concentram energia numa
        # faixa angular fina e o trapezóide em grade fixa de 0,1°
        # subintegra (ex.: m=0,075 → 0,29 % de déficit na 1ª célula de
        # queima). Nenhum resultado é aceito com a verificação falhando —
        # a grade é afunilada até passar ou o erro é levantado.
        self.energy_check = None
        self.motion = None
        self._mech = None
        if self.reactive:
            # R2 — a QUÍMICA fornece o calor: sem Wiebe, sem fonte, sem
            # verificação de energia da fonte (o fechamento da energia é
            # ∫Q̇_chem dV dt = ΔU, verificado pós-execução). O intervalo
            # é TEMPO FÍSICO [s] e a composição vem de φ (ou explícita).
            self._mech = self._load_mechanism()
            self._Y0 = self._initial_composition()
        else:
            self._load_prescribed(a0)

    def _load_prescribed(self, a0: float) -> None:
        eng = self.engine
        stages = self.load_stages()
        self._grid_step_deg = 0.1
        self._theta_grid = self.theta_grid()
        for step in (0.1, 0.05, 0.02, 0.01, 0.005):
            chk = energy_check(self.theta_grid(step), stages, eng.m_fuel,
                               eng.LHV, "rad", eng.rpm)
            if chk["ok"]:
                self.energy_check = chk
                self._grid_step_deg = step
                self._theta_grid = self.theta_grid(step_deg=step)
                break
        if self.energy_check is None:
            chk = energy_check(self.theta_grid(step_deg=0.005), stages,
                               eng.m_fuel, eng.LHV, "rad", eng.rpm)
            raise ValueError(
                "A fonte Wiebe não passa na verificação de conservação "
                f"mesmo com grade de 0,005° (erro relativo "
                f"{chk['rel_error']:.2e} > 0,1 %) — revise os estágios "
                "Wiebe (m muito pequeno ou queima fora da janela).")
        self.motion = motion_report(self.kin, a0, self.theta_end_rad)

    # ------------------------------------------------------------- reativo
    @property
    def reactive(self) -> bool:
        """Modo reativo (R2): a cinética química fornece o calor."""
        return self.cfg.mode == "reactive"

    def _load_mechanism(self) -> Dict:
        """Lê os dicts convertidos do mecanismo (chemkinToFoam) e extrai a
        lista de espécies e as massas molares do próprio speciesThermo —
        nunca redigitados. Verifica a presença dos arquivos e das espécies
        necessárias à mistura H₂/ar (H2, O2, N2)."""
        import re as _re
        mech_dir = Path(self.cfg.reaction_mechanism)
        st = mech_dir / "speciesThermo"
        rx = mech_dir / "reactions"
        for f in (st, rx):
            if not f.is_file():
                raise ValueError(
                    "Mecanismo reativo incompleto: arquivo ausente no "
                    f"diretório '{mech_dir}': {f.name} (conversão do "
                    "chemkinToFoam — ver "
                    "examples/cfd/mechanisms/burke2012/README.md).")
        txt = st.read_text(encoding="utf-8", errors="replace")
        m = _re.search(r"^species\s+\d+\s*\((.*?)\);", txt, _re.S | _re.M)
        if not m:
            raise ValueError(f"speciesThermo sem linha 'species (...);': "
                             f"{st}")
        species = m.group(1).split()
        mw = {s: float(v) for s, v in _re.findall(
            r"^(\S+)\n\s*\{\s*specie\s*\{\s*molWeight\s+([\d.eE+-]+);",
            txt, _re.M | _re.S)}
        faltam = [s for s in ("H2", "O2", "N2") if s not in species]
        if faltam or set(mw) != set(species):
            raise ValueError(
                f"Mecanismo '{mech_dir.name}': espécies incompatíveis — "
                f"faltam {faltam}; speciesThermo declara {species}.")
        return {"directory": str(mech_dir), "species": species,
                "molWeight": mw}

    def _initial_composition(self) -> Dict[str, float]:
        """Frações mássicas iniciais. ``composition`` explícito (massa)
        sobrepõe; senão, φ com ar seco (O2 + 3,76 N2):
        X_H2 = 2φ/(2φ+4,76), X_O2 = 1/(2φ+4,76), X_N2 = 3,76/(2φ+4,76)."""
        mech = self._mech
        if self.cfg.composition:
            y = {str(k): float(v) for k, v in self.cfg.composition.items()}
            desconhecidas = [s for s in y if s not in mech["species"]]
            if desconhecidas:
                raise ValueError(
                    f"cfd.reaction.composition: espécies fora do mecanismo "
                    f"({desconhecidas}; mecanismo tem {mech['species']}).")
            soma = sum(y.values())
            return {s: v / soma for s, v in y.items()}
        phi = self.cfg.equivalence_ratio
        denom = 2.0 * phi + 4.76
        X = {"H2": 2.0 * phi / denom, "O2": 1.0 / denom,
             "N2": 3.76 / denom}
        mw = mech["molWeight"]
        mixm = sum(x * mw[s] for s, x in X.items())
        return {s: x * mw[s] / mixm for s, x in X.items()}

    # ------------------------------------------------------------ utilidades
    @property
    def multicomponent(self) -> bool:
        """Gás multicomponente inerte (R1): N2+O2 com NASA, sem reação."""
        return self.cfg.gas_model == "multicomponent_inert"

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

    def mesh_height(self) -> float:
        """Altura da câmara na MALHA INICIAL: no modo prescrito, a
        geometria do instante inicial θ₀; no modo reativo (R2), a câmara
        é de VOLUME FIXO no volume morto Vc (PMP, θ=0) — malha fixa,
        sem mover (ignição espontânea pela cinética)."""
        if self.reactive:
            return self.chamber_height_at(0.0)      # Vc na PMP
        return self.chamber_height_at(self.theta_start_rad)

    # ------------------------------------------------------------ arquivos
    def build(self, case_dir) -> Path:
        """Gera o caso completo. Retorna o diretório do caso."""
        case_dir = Path(case_dir)
        if case_dir.exists():
            shutil.rmtree(case_dir)
        # Os campos iniciais vão no diretório nomeado pelo TEMPO INICIAL:
        # no modo prescrito, userTime engine → o tempo do solver é o CA
        # (graus) e o OpenFOAM procura os campos no diretório do startTime
        # (ex. -120); no modo reativo o tempo é FÍSICO [s] (ex. 0).
        if self.reactive:
            t0 = _timename(float(self.cfg.interval_start))
        else:
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

        adiab = self.cfg.wall_model == "adiabatic"
        if adiab:
            t_bc = "        type            zeroGradient;\n"
        else:
            t_bc = (f"        type            fixedValue;\n"
                    f"        value            uniform {_fmt(Tw)};\n")
        d.joinpath("T").write_text(_dict_file("volScalarField", "", "T", f"""
dimensions      [0 0 0 1 0 0 0];

internalField   uniform {_fmt(T0)};

boundaryField
{{
    piston
    {{
{t_bc}    }}
    liner
    {{
{t_bc}    }}
    head
    {{
{t_bc}    }}
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
            k0, eps0 = 1.0, 100.0
            d.joinpath("k").write_text(_dict_file("volScalarField", "", "k", """
dimensions      [0 2 -2 0 0 0 0];

internalField   uniform 1.0;

boundaryField
{
    piston { type kqRWallFunction; value uniform 1.0; }
    liner  { type kqRWallFunction; value uniform 1.0; }
    head   { type kqRWallFunction; value uniform 1.0; }
}"""), encoding="utf-8")
            if self.cfg.turbulence_model == "kOmegaSST":
                # ω₀ = ε₀/(Cμ·k₀) com Cμ = 0.09 (par consistente com k/ε acima)
                omega0 = eps0 / (0.09 * k0)
                d.joinpath("omega").write_text(_dict_file("volScalarField", "",
                                                          "omega", f"""
dimensions      [0 0 -1 0 0 0 0];

internalField   uniform {_fmt(omega0)};

boundaryField
{{
    piston {{ type omegaWallFunction; value uniform {_fmt(omega0)}; }}
    liner  {{ type omegaWallFunction; value uniform {_fmt(omega0)}; }}
    head   {{ type omegaWallFunction; value uniform {_fmt(omega0)}; }}
}}"""), encoding="utf-8")
            else:
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

        # R1 (multicomponente inerte): frações mássicas iniciais do ar
        # seco (N2:O2 = 3,76:1 molar); paredes sem gradiente (sem reação
        # não há fluxo especia de parede a prescrever). N2 é a defaultSpecie
        # (Y_N2 = 1 − Y_O2); escrevemos ambas explicitamente para que o
        # estado inicial seja reprodutível sem depender da normalização.
        if self.multicomponent:
            for nome, y in (("N2", _Y_N2), ("O2", _Y_O2)):
                d.joinpath(nome).write_text(_dict_file(
                    "volScalarField", "", nome, f"""
dimensions      [0 0 0 0 0 0 0];

internalField   uniform {_fmt(y, 8)};

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

        # Modo reativo (R2): mistura homogênea H₂/ar — um arquivo por
        # espécie do mecanismo (frações mássicas de _initial_composition;
        # as demais uniform 0) + Ydefault. Paredes sem fluxo de espécies
        # prescrito (zeroGradient; a câmara é fechada, volume fixo).
        if self.reactive:
            y0 = self._Y0
            especies = self._mech["species"]
            for sp in especies:
                d.joinpath(sp).write_text(_dict_file(
                    "volScalarField", "", sp, f"""
dimensions      [0 0 0 0 0 0 0];

internalField   uniform {_fmt(y0.get(sp, 0.0), 8)};

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
            d.joinpath("Ydefault").write_text(_dict_file(
                "volScalarField", "", "Ydefault", """
dimensions      [0 0 0 0 0 0 0];

internalField   uniform 0;

boundaryField
{
    piston
    {
        type            zeroGradient;
    }
    liner
    {
        type            zeroGradient;
    }
    head
    {
        type            zeroGradient;
    }
}"""), encoding="utf-8")

    # ------------------------------------------------------------ constant/
    def _write_constant(self, d: Path) -> None:
        # Modo REATIVO (R2): a química fornece o calor — physicalProperties
        # com o mecanismo (speciesThermo copiado), combustionProperties
        # (laminar) e chemistryProperties (ode + #include "reactions").
        # SEM fvModels: as duas fontes de calor NUNCA coexistem.
        if self.reactive:
            self._write_constant_reactive(d)
        # Propriedades do gás — VALORES configuráveis, padrão ar
        # simplificado declarado (§9). Não são os κ/Hohenberg do 0-D: o
        # CFD resolve a energia e a troca térmica nas paredes por si.
        # γ_CFD = Cp/(Cp−R), R = 8314.46/molWeight — o teste de
        # equivalência termodinâmica (γ_CFD = κ do 0-D) sobrescreve Cp.
        elif self.multicomponent:
            # R1 — mistura multicomponente inerte (N2+O2), formato do
            # tutorial OF13 multicomponentFluid/counterFlowFlame2D
            # (coefficientWilkeMulticomponentMixture + janaf/sutherland).
            # SEM constant/combustionProperties: o combustionModel::New do
            # OF13 cai em noCombustion (R=0, Qdot=0) — transporte de
            # espécies sem reação (roadmap reativo §2, degrau R1).
            cp_n2 = SPECIES_R1["N2"]
            cp_o2 = SPECIES_R1["O2"]
            d.joinpath("physicalProperties").write_text(_dict_file(
                "dictionary", "constant", "physicalProperties", f"""
thermoType
{{
    type            hePsiThermo;
    mixture         coefficientWilkeMulticomponentMixture;
    transport       sutherland;
    thermo          janaf;
    energy          sensibleEnthalpy;
    equationOfState perfectGas;
    specie          specie;
}}

species          ( N2 O2 );

defaultSpecie    N2;

N2
{{
    specie
    {{
        molWeight       {_fmt(cp_n2["molWeight"], 7)};
    }}
    thermodynamics
    {{
        Tlow            {cp_n2["Tlow"]};
        Thigh           {cp_n2["Thigh"]};
        Tcommon         {cp_n2["Tcommon"]};
        highCpCoeffs    ( {cp_n2["highCpCoeffs"][0]:.6g} {cp_n2["highCpCoeffs"][1]:.6g} {cp_n2["highCpCoeffs"][2]:.6g} {cp_n2["highCpCoeffs"][3]:.6g} {cp_n2["highCpCoeffs"][4]:.6g} {cp_n2["highCpCoeffs"][5]:.6g} {cp_n2["highCpCoeffs"][6]:.6g} );
        lowCpCoeffs     ( {cp_n2["lowCpCoeffs"][0]:.6g} {cp_n2["lowCpCoeffs"][1]:.6g} {cp_n2["lowCpCoeffs"][2]:.6g} {cp_n2["lowCpCoeffs"][3]:.6g} {cp_n2["lowCpCoeffs"][4]:.6g} {cp_n2["lowCpCoeffs"][5]:.6g} {cp_n2["lowCpCoeffs"][6]:.6g} );
    }}
    transport
    {{
        As              {cp_n2["As"]:.4g};
        Ts              {cp_n2["Ts"]:.6g};
    }}
}}

O2
{{
    specie
    {{
        molWeight       {_fmt(cp_o2["molWeight"], 7)};
    }}
    thermodynamics
    {{
        Tlow            {cp_o2["Tlow"]};
        Thigh           {cp_o2["Thigh"]};
        Tcommon         {cp_o2["Tcommon"]};
        highCpCoeffs    ( {cp_o2["highCpCoeffs"][0]:.6g} {cp_o2["highCpCoeffs"][1]:.6g} {cp_o2["highCpCoeffs"][2]:.6g} {cp_o2["highCpCoeffs"][3]:.6g} {cp_o2["highCpCoeffs"][4]:.6g} {cp_o2["highCpCoeffs"][5]:.6g} {cp_o2["highCpCoeffs"][6]:.6g} );
        lowCpCoeffs     ( {cp_o2["lowCpCoeffs"][0]:.6g} {cp_o2["lowCpCoeffs"][1]:.6g} {cp_o2["lowCpCoeffs"][2]:.6g} {cp_o2["lowCpCoeffs"][3]:.6g} {cp_o2["lowCpCoeffs"][4]:.6g} {cp_o2["lowCpCoeffs"][5]:.6g} {cp_o2["lowCpCoeffs"][6]:.6g} );
    }}
    transport
    {{
        As              {cp_o2["As"]:.4g};
        Ts              {cp_o2["Ts"]:.6g};
    }}
}}"""), encoding="utf-8")
        # (o restante de constant/ — momentumTransport, dynamicMeshDict,
        # fvModels, topoSet — é comum aos dois modelos de gás e escrito
        # abaixo, sem early-return: o caso multicomponente móvel precisa
        # do dynamicMeshDict tanto quanto o simple)
        else:
            cp = self.cfg.gas_Cp_J_kgK
            mw = self.cfg.gas_molWeight
            d.joinpath("physicalProperties").write_text(_dict_file(
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
        molWeight       {_fmt(mw)};
    }}
    thermodynamics
    {{
        Cp              {_fmt(cp)};
        hf              0;
    }}
    transport
    {{
        mu              {_fmt(self.cfg.gas_mu)};
        Pr              {_fmt(self.cfg.gas_Pr)};
    }}
}}"""), encoding="utf-8")

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

        # mover do pistão (malha móvel) — inexistente no modo reativo
        # (volume fixo, R2; malha móvel com reação é o degrau R3)
        if self.moving and not self.reactive:
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

        # fonte de calor Wiebe (fvModel nativo, conservativo) — APENAS no
        # modo prescrito: no modo reativo a QUÍMICA fornece o calor e as
        # duas fontes NUNCA coexistem (regra inviolável do roadmap).
        # OpenFOAM 13: o modo ``Q`` (potência total) do heatSource divide a
        # potência pelo volume da cellZone CONGELADO na construção — com
        # malha móvel (pistão) a fonte deixa de ser conservativa. Por isso
        # prescrevemos a densidade q'''(CA) = Q̇(CA)/V₀(CA) diretamente
        # (distribuição uniforme, Σᵢ q'''ᵢ·Vᵢᵃᵗᵘᵃˡ = Q̇ sobre os volumes
        # atuais). No modo ``region`` o volume da zona não é conhecido na
        # geração do caso: mantém-se Q com a limitação registrada.
        if self.heat_enabled and not self.reactive:
            th = self._theta_grid          # MESMA grade da verificação
            zona = ("all" if self.cfg.distribution == "uniform"
                    else self.cfg.region)
            if self.cfg.distribution == "uniform":
                campo = "q"          # q''' [W/m³]
                comentario = ("q''' [W/m³] = Q̇(CA)/V₀(CA) — conservativo "
                              "com malha móvel (Σᵢ q'''ᵢ·Vᵢ = Q̇)")
                tabela = table_text_density(
                    th, self.load_stages(), self.engine.m_fuel,
                    self.engine.LHV, "rad", self.engine.rpm,
                    self.kin.volume(th),
                    step_deg=self._grid_step_deg)
            else:                    # region: limitação documentada abaixo
                campo = "Q"          # Q̇ [W] (não conservativo c/ malha móvel)
                comentario = ("Q̇ [W] — NÃO conservativo com malha móvel "
                              "no OF13 (limitação em case_config.yaml)")
                tabela = table_text(th, self.load_stages(),
                                    self.engine.m_fuel, self.engine.LHV,
                                    "rad", self.engine.rpm,
                                    step_deg=self._grid_step_deg)
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

        # topoSet: geração da região (distribution=region) — caixa axial.
        # Este bloco roda dentro de _write_constant (d = constant/) — o
        # topoSetDict pertence a system/, onde a validação e o adapter
        # o procuram (d.parent = diretório do caso). A região é criada
        # UMA vez no início da janela (cellZoneSet é estático).
        if self.heat_enabled and not self.reactive \
                and self.cfg.distribution == "region" \
                and self.cfg.region:
            h0 = self.chamber_height_at(self.theta_start_rad)
            r = self.engine.bore / 2.0
            zmax = h0 * 0.5   # metade inferior: hipótese declarada do usuário
            d.parent.joinpath("system").joinpath("topoSetDict").write_text(
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

    def _write_constant_reactive(self, d: Path) -> None:
        """Constant/ do modo reativo (R2), no formato dos tutoriais
        reativos do OF13 (multicomponentFluid/counterFlowFlame2D_GRI):
        os arquivos `reactions` e `speciesThermo` são COPIADOS do
        diretório do mecanismo (saída verificada do chemkinToFoam) —
        nenhuma constante química é redigitada aqui."""
        c = self.cfg
        mech = Path(c.reaction_mechanism)
        shutil.copy(mech / "speciesThermo", d / "speciesThermo")
        shutil.copy(mech / "reactions", d / "reactions")
        d.joinpath("physicalProperties").write_text(_dict_file(
            "dictionary", "constant", "physicalProperties", """
thermoType
{
    type            hePsiThermo;
    mixture         multicomponentMixture;
    transport       sutherland;
    thermo          janaf;
    energy          sensibleEnthalpy;
    equationOfState perfectGas;
    specie          specie;
}

defaultSpecie    N2;

#include "speciesThermo"
"""), encoding="utf-8")
        d.joinpath("combustionProperties").write_text(_dict_file(
            "dictionary", "constant", "combustionProperties", """
combustionModel  laminar;
"""), encoding="utf-8")
        d.joinpath("chemistryProperties").write_text(_dict_file(
            "dictionary", "constant", "chemistryProperties", f"""
chemistryType
{{
    solver          {c.chem_solver};
}}

chemistry           on;

initialChemicalTimeStep {_fmt(c.chem_initial_dt)};

odeCoeffs
{{
    solver          {c.chem_method};
    absTol          {_fmt(c.chem_abs_tol)};
    relTol          {_fmt(c.chem_rel_tol)};
}}

#include "reactions"
"""), encoding="utf-8")

    # -------------------------------------------------------------- system/
    def _write_system(self, d: Path) -> None:
        c = self.cfg
        a0 = self.theta_start_rad
        a1 = self.theta_end_rad
        turb = c.turbulence_model != "laminar"

        # solver do caso: ``fluid`` (ar simplificado) ou
        # ``multicomponentFluid`` (R1 — transporte de espécies; sem
        # constant/combustionProperties o OF13 usa noCombustion, R=0; R2 —
        # reação via combustionProperties/chemistryProperties)
        solver_name = "multicomponentFluid" if (self.multicomponent
                                                or self.reactive) else "fluid"
        # R1: conservação de massa por espécie (gate do degrau) — os
        # functionObjects `multiply` criam ρ·Yi ANTES do volFieldValue
        # (execução na ordem declarada); a integral volumétrica de ρ·Yi é
        # a massa da espécie (sem reação: constante ao longo do ciclo).
        species_fos = ""
        if self.multicomponent:
            species_fos = """
    massN2
    {
        type            multiply;
        libs            ("libfieldFunctionObjects.so");
        fields          (rho N2);
        result          rhoN2;
        writeControl    writeTime;
    }
    massO2
    {
        type            multiply;
        libs            ("libfieldFunctionObjects.so");
        fields          (rho O2);
        result          rhoO2;
        writeControl    writeTime;
    }
    specieMass
    {
        type            volFieldValue;
        libs            ("libfieldFunctionObjects.so");
        cellZone        all;
        operation       volIntegrate;
        writeFields     no;
        fields          (rhoN2 rhoO2);
    }"""
        elif self.reactive:
            # R2: massas de TODAS as espécies do mecanismo (o fechamento de
            # energia ∫Q̇dVdt = ΔU exige Σ_i m_i h_i com a composição
            # COMPLETA — intermediários OH/HO2/H2O2 têm massa no pico de
            # ignição; H2/O2/N2/H2O sozinhos seriam insuficientes) —
            # mesmos functionObjects `multiply` + volIntegrate do R1;
            # writeControl writeTime (sem ele o OF13 grava ρ·Yi TODO passo:
            # um diretório de tempo por passo — registrado no caso R2).
            massa = ""
            campos = []
            for sp in self._mech["species"]:
                massa += f"""
    mass{sp}
    {{
        type            multiply;
        libs            ("libfieldFunctionObjects.so");
        fields          (rho {sp});
        result          rho{sp};
        writeControl    writeTime;
    }}"""
                campos.append(f"rho{sp}")
            species_fos = massa + """
    specieMass
    {
        type            volFieldValue;
        libs            ("libfieldFunctionObjects.so");
        cellZone        all;
        operation       volIntegrate;
        writeFields     no;
        fields          (%s);
    }""" % " ".join(campos)
        # ——— tempo do solver —————————————————————————————————————————
        # prescrito: CA em graus (userTime engine); reativo: TEMPO FÍSICO
        # [s] (volume fixo não tem manivela; R2). No modo reativo o passo
        # inicial/máximo vêm da química (initial/max_chemical_time_step) e
        # `adjustTimeStepToChemistry` limita Δt às escalas de tempo
        # químicas; write_interval é interpretado em SEGUNDOS.
        if self.reactive:
            tempo_ini = _timename(float(c.interval_start))
            tempo_fim = _fmt(float(c.interval_end))
            tempo_user = ""      # sem userTime engine
            delta_t = _fmt(c.chem_initial_dt)
            max_dt = _fmt(c.chem_max_dt)
            write_int = _fmt(float(c.write_interval_deg))
        else:
            tempo_ini = _timename(math.degrees(a0))
            tempo_fim = _fmt(math.degrees(a1))
            tempo_user = f"""userTime
{{
    type            engine;
    omega           {_fmt(self.engine.rpm)} [rpm];
}}

"""
            delta_t = "0.01"
            max_dt = "0.5"
            write_int = _fmt(c.write_interval_deg)

        # R2: ajuste do passo às escalas de tempo QUÍMICAS (OF13:
        # etc/caseDicts/functions/control/adjustTimeStepToChemistry) e
        # Q̇ — campo (Qdot) e integral volumétrica ∫Q̇ dV [W] para o
        # fechamento de energia (portão R2c).
        #
        # CUIDADO (caso R2, 2026-09-24): o FO tipo Qdot é quem RECALCULA o
        # campo Qdot — com executeControl writeTime o campo ficava CONGELADO
        # entre writeTimes e o QdotIntegral integrava valor parado (256 J
        # "liberados" com 42 J de combustível no caso). executeControl
        # timeStep mantém o campo vivo; writeControl writeTime evita gravar
        # o campo TODO passo.
        reativos_fos = ""
        if self.reactive:
            reativos_fos = """
    #includeFunc adjustTimeStepToChemistry

    Qdot
    {
        type            Qdot;
        libs            ("libcombustionModels.so");
        executeControl  timeStep;
        writeControl    writeTime;
    }
    QdotIntegral
    {
        type            volFieldValue;
        libs            ("libfieldFunctionObjects.so");
        cellZone        all;
        operation       volIntegrate;
        writeFields     no;
        fields          (Qdot);
    }
"""
        d.joinpath("controlDict").write_text(_dict_file(
            "dictionary", "system", "controlDict", f"""
solver          {solver_name};

{tempo_user}startFrom       startTime;

// mesmo formato do nome do diretório de tempo (_timename): o OpenFOAM
// procura os campos iniciais no diretório startTime (ex. "-120", não "-120.0")
startTime       {tempo_ini};

stopAt          endTime;

endTime         {tempo_fim};

deltaT          {delta_t};

adjustTimeStep  yes;

maxCo           {_fmt(c.max_Co)};

maxDeltaT       {max_dt};

writeControl    adjustableRunTime;

writeInterval   {write_int};

purgeWrite      0;

writeFormat     binary;

writePrecision  8;

writeCompression off;

timeFormat      general;

timePrecision   6;

runTimeModifiable true;

functions
{{{reativos_fos}
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
    }}{species_fos}
    wallHeatFlux
    {{
        type            wallHeatFlux;
        libs            ("libfieldFunctionObjects.so");
        patches         (piston liner head);
        writeControl    writeTime;    // sem isso grava o campo TODO passo
    }}
}}"""), encoding="utf-8")

        # R1/R2: termo de transporte de espécies (formato do tutorial
        # multicomponentFluid); inócuo no caso simple
        div_yi = "    div(phi,Yi_h)   Gauss limitedLinear 1;\n" \
            if (self.multicomponent or self.reactive) else ""
        d.joinpath("fvSchemes").write_text(_dict_file(
            "dictionary", "system", "fvSchemes", f"""
ddtSchemes
{{
    default         Euler;
}}

gradSchemes
{{
    default         Gauss linear;
}}

divSchemes
{{
    default         none;
    div(phi,U)      Gauss upwind;
    div(phi,h)      Gauss upwind;
    div(phi,e)      Gauss upwind;
    div(phi,(p|rho)) Gauss upwind;
{div_yi}    div(phi,k)      Gauss upwind;
    div(phi,epsilon) Gauss upwind;
    div(phi,omega)  Gauss upwind;
    div(phi,R)      Gauss upwind;
    div(phi,K)      Gauss linear;
    div(phi,Ekp)    Gauss linear;
    div(R)          Gauss linear;
    div(((rho*nuEff)*dev2(T(grad(U))))) Gauss linear;
}}

laplacianSchemes
{{
    default         Gauss linear corrected;
}}

interpolationSchemes
{{
    default         linear;
}}

// exigido pelos modelos kOmega (distância à parede); inócuo nos demais
wallDist
{{
    method          meshWave;
}}

snGradSchemes
{{
    default         corrected;
}}"""), encoding="utf-8")

        # R1/R2: blocos do solver de espécies (Yi e YiFinal, formato do
        # tutorial multicomponentFluid); inócuo no caso simple
        sol_yi = """
    "Yi"
    {
        solver          PBiCGStab;
        preconditioner  DILU;
        tolerance       1e-06;
        relTol          0.1;
    }

    "YiFinal"
    {
        $Yi;
        relTol          0;
    }
""" if (self.multicomponent or self.reactive) else ""
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

    "(U|h|e|k|epsilon|omega|R)"
    {{
        solver          PBiCGStab;
        preconditioner  DILU;
        tolerance       1e-06;
        relTol          0.1;
    }}

    "(U|h|e|k|epsilon|omega|R)Final"
    {{
        $U;
        relTol          0;
    }}
{sol_yi}}}

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
        h = self.mesh_height()
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
        if self.reactive:
            self._write_case_docs_reactive(case_dir)
            return
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
                "energy_check": self.energy_check,
                "table_step_CA_deg": self._grid_step_deg},
            "motion": self.motion,
            "numerics": {"deltaT_CA_deg": 0.01, "max_Co": self.cfg.max_Co,
                         "time_is_crank_angle_deg": True},
            "initial_conditions": {"P_Pa": self.cfg.P0_kPa * 1e3,
                                   "T_K": self.cfg.T0_K},
            "walls": {"model": self.cfg.wall_model, "Tw_K": self.cfg.Tw_K},
            "turbulence": {"model": self.cfg.turbulence_model,
                           "wall_functions": self.cfg.wall_functions},
            "gas_model": {
                "eos": "perfectGas", "Cp_J_kgK": self.cfg.gas_Cp_J_kgK,
                "molWeight_kg_kmol": self.cfg.gas_molWeight,
                "mu_Pa_s": self.cfg.gas_mu, "Pr": self.cfg.gas_Pr,
                "gamma": self.cfg.gas_Cp_J_kgK
                         / (self.cfg.gas_Cp_J_kgK - 8314.46
                            / self.cfg.gas_molWeight),
                "notice": "Ar simplificado (propriedades constantes). O κ "
                          "do modelo 0-D e a correlação de Hohenberg não "
                          "são transferidos para o CFD; a troca térmica "
                          "nas paredes é calculada pelo solver."},
            **({"gas_thermo": {
                "model": "multicomponent_inert",
                "species": ["N2", "O2"],
                "y_N2": _Y_N2, "y_O2": _Y_O2,
                "thermo_type": ("hePsiThermo + "
                                "coefficientWilkeMulticomponentMixture + "
                                "janaf/sutherland + sensibleEnthalpy + "
                                "perfectGas"),
                "reaction": "noCombustion (sem constant/combustionProperties "
                            "— R=0, Qdot=0; transporte de espécies sem "
                            "reação)",
                "provenance": ("Polinômios NASA (janaf 200-5000 K) e "
                               "transporte de Sutherland de N2/O2 copiados "
                               "do tutorial OF13 "
                               "tutorials/multicomponentFluid/"
                               "counterFlowFlame2D/constant/"
                               "thermo.compressibleGas (termoquímica "
                               "GRI-Mech 3.0 distribuída com o OpenFOAM 13)."),
                "notice": ("Degrau R1 do roadmap reativo: Cp(T), mu(T) e "
                           "mistura N2+O2 reais (ar seco, razão molar "
                           "3,76:1); os campos Cp/molWeight/mu/Pr da seção "
                           "gas_model acima são IGNORADOS neste caso. Sem "
                           "reação — as frações mássicas só são "
                           "transportadas, nunca transformadas.")}}
              if self.multicomponent else {}),
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


    def _write_case_docs_reactive(self, case_dir: Path) -> None:
        """case_config.yaml + README do modo reativo (R2)."""
        import yaml
        c = self.cfg
        mech = self._mech
        y0 = self._Y0
        A = math.pi * (self.engine.bore / 2.0) ** 2
        Vc = self.kin.volume(0.0)
        mw_mix = sum(y0[s] * mech["molWeight"][s] for s in y0)
        m_gas = (c.P0_kPa * 1e3 * Vc) / (8314.46 / mw_mix * c.T0_K)
        # frações MOLARES iniciais (só quando a composição vem de φ)
        if c.composition:
            X0 = None
            phi_txt = "composition explícita (frações mássicas)"
        else:
            denom = 2.0 * c.equivalence_ratio + 4.76
            X0 = {"H2": 2.0 * c.equivalence_ratio / denom,
                  "O2": 1.0 / denom, "N2": 3.76 / denom}
            phi_txt = (f"φ = {c.equivalence_ratio:g} com ar seco "
                       "(O2 + 3,76 N2): X_H2 = 2φ/(2φ+4,76), "
                       "X_O2 = 1/(2φ+4,76), X_N2 = 3,76/(2φ+4,76)")
        info = {
            "created": datetime.now().isoformat(timespec="seconds"),
            "wiebepy_version": _version(),
            "solver": self.solver_info,
            "mode": c.mode,
            "adapter": c.adapter,
            "features": {"moving_piston": False,
                         "heat_source": False},
            "physics_scope": (
                "Degrau R2 do roadmap reativo: a CINÉTICA QUÍMICA fornece "
                "o calor (mistura homogênea H₂/ar, volume fixo, ignição "
                "espontânea — sem fonte de calor, sem faísca, sem malha "
                "adaptativa). VERIFICAÇÃO (portões R2), NÃO validação "
                "contra dados de motor. A Wiebe está AUSENTE: as duas "
                "fontes de calor nunca coexistem."),
            "reaction": {
                "mechanism_directory": str(Path(c.reaction_mechanism)),
                "files_copied": ["constant/reactions",
                                 "constant/speciesThermo"],
                "species": mech["species"],
                "combustion_model": c.reaction_combustion_model,
                "chemistry": {
                    "solver": c.chem_solver,
                    "method": c.chem_method,
                    "initial_chemical_time_step_s": c.chem_initial_dt,
                    "max_chemical_time_step_s": c.chem_max_dt,
                    "absolute_tolerance": c.chem_abs_tol,
                    "relative_tolerance": c.chem_rel_tol},
                "equivalence_ratio": (None if c.composition
                                      else c.equivalence_ratio),
                "initial_composition": {
                    "from": phi_txt,
                    "mole_fractions_X": X0,
                    "mass_fractions_Y": {s: y0.get(s, 0.0)
                                         for s in mech["species"]}},
                "provenance": (
                    "Mecanismo convertido pelo chemkinToFoam (OF13) e "
                    "verificado mecanicamente contra a fonte publicada — "
                    "ver README.md do diretório do mecanismo (ex.: "
                    "examples/cfd/mechanisms/burke2012). Os arquivos "
                    "reactions/speciesThermo são copiados, nunca "
                    "redigitados."),
                "notice": (
                    "No modo reativo as seções heat_source/wiebe/fuel/gas "
                    "da configuração NÃO são usadas e NÃO aparecem neste "
                    "caso (a química fornece o calor; as duas fontes "
                    "nunca coexistem). Wiebe é apenas para comparação no "
                    "modo prescrito.")},
            "chamber": {
                "model": "fixed_volume",
                "volume_m3": float(Vc),
                "cross_section_m2": float(A),
                "height_m": float(Vc / A),
                "notice": (
                    "Câmara de volume FIXO no volume morto Vc (PMP, "
                    "θ=0): malha blockMesh fixa, sem mover, sem "
                    "dynamicMeshDict. A geometria do motor (seção "
                    "engine) serve apenas para definir Vc — não há "
                    "movimento de pistão no R2.")},
            "initial_state": {
                "P_Pa": c.P0_kPa * 1e3, "T_K": c.T0_K,
                "mean_molWeight_kg_kmol": float(mw_mix),
                "gas_mass_kg_ideal_gas": float(m_gas),
                "notice": ("Massa do gás derivada do gás ideal "
                           "m = PV/(R_s·T) com a mistura inicial — "
                           "referência para os fechamentos de massa.")},
            "numerics": {
                "deltaT_initial_s": c.chem_initial_dt,
                "maxDeltaT_s": c.chem_max_dt,
                "max_Co": c.max_Co,
                "write_interval_s": float(c.write_interval_deg),
                "adjustTimeStepToChemistry": True,
                "time_is_physical_seconds": True,
                "notice": ("No modo reativo o tempo do solver é FÍSICO "
                           "[s] e cfd.numerics.write_interval_deg é "
                           "interpretado em SEGUNDOS (não há manivela em "
                           "volume fixo).")},
            "walls": {"model": c.wall_model, "Tw_K": c.Tw_K},
            "turbulence": {"model": c.turbulence_model,
                           "wall_functions": c.wall_functions},
            "interval": {"time_unit": "s", "start": c.interval_start,
                         "end": c.interval_end},
            "configuration": c.to_dict_public(),
        }
        p = case_dir / "case_config.yaml"
        p.write_text(yaml.safe_dump(_plain(info), sort_keys=False,
                                    allow_unicode=True), encoding="utf-8")
        (case_dir / "README.md").write_text(
            f"# Caso CFD reativo gerado pelo wiebepy (R2)\n\n"
            f"- Caso: {case_dir.name} — criado em {info['created']}\n"
            f"- Solver: OpenFOAM {self.solver_info.get('version', '?')} "
            f"(adapter openfoam), solver multicomponentFluid\n"
            f"- Janela simulada: {c.interval_start:g} s a "
            f"{c.interval_end:g} s (tempo FÍSICO)\n"
            f"- Mistura: {phi_txt}\n"
            f"- Câmara: volume fixo Vc = {Vc:.6e} m³ (PMP, θ=0)\n\n"
            f"## Execução\n\n    wiebepy cfd run --case \"{case_dir}\"\n\n"
            f"## Portões de verificação (R2) — antes de avançar ao R3\n\n"
            f"- (a) atraso de ignição 0-D do mecanismo vs dados de shock "
            f"tube publicados;\n"
            f"- (b) atraso de ignição do CFD consistente com o 0-D;\n"
            f"- (c) fechamento de energia ∫Q̇ dV dt = ΔU (volume fixo);\n"
            f"- (d) passo químico estável (sem oscilação em p̄(t)).\n\n"
            f"## Escopo\n\n"
            f"- A QUÍMICA fornece o calor; a Wiebe está ausente (as duas "
            f"fontes nunca coexistem).\n"
            f"- Isto é VERIFICAÇÃO do mecanismo/solver — não validação "
            f"contra dados de motor.\n"
            f"- 'Processo terminou' ≠ 'convergiu': os portões acima são "
            f"checados com os resultados (postProcessing).\n\n"
            f"Detalhes completos em case_config.yaml e no README do "
            f"mecanismo.\n", encoding="utf-8")


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