# -*- coding: utf-8 -*-
"""
config.py — Configuração do módulo crevice_flow, com unidades explícitas.

Toda dimensão carrega a unidade no nome do campo (_mm, _K, _Pa…) e toda
conversão para SI é centralizada em ``to_si()``. Conversões de ângulo e
tempo usam as relações testadas (§6 do escopo):

    dθ/dt = 6·RPM  [°/s]
    dθ/dt = 2π·RPM/60  [rad/s]
    t [s] = θ [°] / (6·RPM)

Nada é inventado: pressão da câmara vem de arquivo (ensaio, modelo 0-D ou
CFD prévio) com unidades declaradas; o estado do gás que ENTRA no domínio
é exigido explicitamente (a pressão sozinha não determina o estado);
sem extrapolação fora da janela do arquivo, a menos que ``extrapolate``
seja marcado explicitamente — e o fato vira aviso no relatório.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml


class CreviceConfigError(ValueError):
    """Erro de configuração do crevice_flow (uso/configuração: exit 2)."""


# ------------------------------------------------------------------ geometria
@dataclass
class CreviceGeometry:
    """Geometria parametrizada da fresta (§4), todas as dimensões em mm.

    O domínio do submodelo (referencial solidário ao pistão) tem
    geometria CONSTANTE: a superfície do liner desliza sobre si mesma
    ao longo do eixo, então a folga pistão-cilindro não muda de forma —
    o movimento entra como velocidade de parede axial na condição de
    contorno (``motion.liner_wall_velocity``).

        bore_diameter   diâmetro do cilindro
        radial_gap      folga radial pistão–cilindro no top land
        top_land_height altura do top land (da coroa do pistão ao topo
                        do 1º anel) — é a extensão axial da fresta
        buffer_height   coluna de gás da câmara acima da boca da fresta
                        (região de entrada; a BC da câmara fica no topo)
        sector_angle    ângulo do setor periódico (wedge) em graus. Só é
                        permitido porque a geometria e as condições de
                        contorno são uniformes na circunferência; uma
                        abertura localizada do anel NÃO pode ser
                        representada como vazamento uniforme (regra §4)
        ring_grooves    cavidades/passagens adicionais incluídas (fase
                        1: lista vazia — fundo fechado)
    """
    bore_diameter_mm: float
    radial_gap_mm: float
    top_land_height_mm: float
    buffer_height_mm: float = 2.0
    sector_angle_deg: float = 2.0
    ring_grooves: List[Dict] = field(default_factory=list)

    @property
    def crevice_volume_m3(self) -> float:
        """Volume da fresta anelar (aproximação de anel fino, g ≪ D,
        declarada): V ≈ π·D_médio·g·h. Com cavidades, soma cada uma."""
        d_med = (self.bore_diameter_mm - self.radial_gap_mm) * 1e-3
        v = math.pi * d_med * (self.radial_gap_mm * 1e-3)
        v *= self.top_land_height_mm * 1e-3
        for g in self.ring_grooves:      # cavidades: prisma anelar próprio
            d_g = (self.bore_diameter_mm - g["radial_depth_mm"]) * 1e-3
            v += math.pi * d_g * (g["radial_depth_mm"] * 1e-3) \
                * (g["axial_height_mm"] * 1e-3)
        return v


# ------------------------------------------------------------------- térmica
@dataclass
class CreviceThermal:
    """Paredes: temperatura prescrita [K] ou 'adiabatic' (§7).

    Pistão (coroa/land e flanco do anel) e cilindro (liner) podem ter
    temperaturas distintas; não há temperatura única implícita.
    """
    piston_wall: object = 400.0        # K ou "adiabatic"
    liner_wall: object = 440.0         # K ou "adiabatic"

    def _valida(self, nome, v):
        if isinstance(v, str):
            if v != "adiabatic":
                raise CreviceConfigError(
                    f"crevice.thermal.{nome}: só 'adiabatic' ou número (K); "
                    f"recebido {v!r}")
        elif not (isinstance(v, (int, float)) and 200 < float(v) < 1500):
            raise CreviceConfigError(
                f"crevice.thermal.{nome}: temperatura em K deve estar em "
                f"(200, 1500); recebido {v!r}")

    def validate(self) -> None:
        self._valida("piston_wall", self.piston_wall)
        self._valida("liner_wall", self.liner_wall)


# --------------------------------------------------------- pressão da câmara
@dataclass
class ChamberBC:
    """Condição de contorno da câmara no topo do buffer (§5).

    source        'experiment' | 'zero_d' | 'cfd' — proveniência
                  obrigatória (vai para o relatório tal como vem)
    file          CSV/TSV com colunas de ângulo e pressão
    theta_unit    'deg' | 'rad'
    p_unit        'Pa' | 'kPa' | 'bar'
    columns       {'theta': nome, 'p': nome} (cabeçalho do arquivo)
    extrapolate   False (padrão) — a janela da simulação deve estar
                  contida na do arquivo; True exige registro explícito e
                  vira AVISO no relatório
    inflow_T_K    temperatura do gás que ENTRA no domínio [K]. OBRIGATÓRIA:
                  a pressão experimental sozinha não determina o estado do
                  gás que entra (hipótese declarada, não medida)
    bc_type       'totalPressure' (padrão) | 'staticPressure' — a escolha
                  distingue grandezas estáticas e totais; com Mach baixo na
                  seção da câmara a diferença é pequena e fica declarada
    blowby        None (fase 1: fundo fechado — NÃO chamar de blow-by) ou
                  dict {'downstream_p_Pa': float, …}: caminho de vazamento
                  até região de menor pressão, com a pressão do destino
                  EXIGIDA (extensão planejada; validada quando implementada)
    """
    source: str
    file: Path
    theta_unit: str = "deg"
    p_unit: str = "kPa"
    columns: Dict[str, str] = field(default_factory=lambda:
                                    {"theta": "theta", "p": "P"})
    extrapolate: bool = False
    inflow_T_K: float = 600.0
    bc_type: str = "totalPressure"
    blowby: Optional[Dict] = None


# ------------------------------------------------------------------ motion
@dataclass
class CreviceMotion:
    """Rotação e referencial (§6).

    frame 'piston': geometria constante (o liner desliza sobre si mesmo).
    Os efeitos do referencial acelerado (ω²r da biela-manivela) são
    NEGLIGENCIADOS nesta versão — justificativa registrada: o termo de
    corpo (∼ρ·ω²·r, com ω = 2π·RPM/60) é ordens de grandeza menor que os
    gradientes de pressão que dirigem o escoamento na fresta; o fato vira
    hipótese declarada no relatório.
    liner_wall_velocity: aplica na parede do liner a velocidade axial
    relativa ao pistão (v_p = ω·r_manivela·sin… via cinemática do wiebepy)
    — escoamento de Couette na folga, em geral pequeno perto do dirigido
    por pressão, mas representado por fidelidade.
    """
    rpm: float = 1500.0
    frame: str = "piston"
    liner_wall_velocity: bool = True
    stroke_mm: Optional[float] = None          # p/ v_p (biela-manivela)
    rod_length_mm: Optional[float] = None

    def validate(self) -> None:
        if not (isinstance(self.rpm, (int, float)) and 0 < float(self.rpm) < 100000):
            raise CreviceConfigError(
                f"crevice.motion.rpm deve ser positivo; recebido "
                f"{self.rpm!r}")
        if self.frame != "piston":
            raise CreviceConfigError(
                "crevice.motion.frame: só 'piston' nesta versão")
        if self.liner_wall_velocity and not (self.stroke_mm
                                             and self.rod_length_mm):
            raise CreviceConfigError(
                "crevice.motion: liner_wall_velocity exige stroke_mm e "
                "rod_length_mm (cinemática biela-manivela)")


# ------------------------------------------------------------------- malha
@dataclass
class CreviceMesh:
    """Malha do setor (r–z), refinada transversalmente à folga (§8)."""
    n_gap: int = 6                 # células transversais à folga (≥ 3)
    n_crevice_axial: int = 10      # células axiais na fresta
    n_buffer_axial: int = 8        # células axiais no buffer de entrada
    gap_grading: float = 1.0       # 1 = uniforme; >1 refina no lado da parede
    max_growth: float = 1.3        # limite de crescimento declarado
    sector_cells: int = 1          # wedge: 1 célula na direção tangencial

    def validate(self) -> None:
        if self.n_gap < 3:
            raise CreviceConfigError(
                "crevice.mesh.n_gap ≥ 3: a folga precisa de resolução "
                "transversal mínima")
        for nome, v in (("n_crevice_axial", self.n_crevice_axial),
                        ("n_buffer_axial", self.n_buffer_axial),
                        ("sector_cells", self.sector_cells)):
            if not (isinstance(v, int) and v >= 1):
                raise CreviceConfigError(
                    f"crevice.mesh.{nome} deve ser inteiro ≥ 1; recebido "
                    f"{v!r}")
        if not (0.2 <= self.gap_grading <= 5.0):
            raise CreviceConfigError(
                "crevice.mesh.gap_grading deve estar em [0.2, 5.0]")


# ---------------------------------------------------------------- numéricos
@dataclass
class CreviceNumerics:
    max_Co: float = 0.5
    max_delta_t_s: float = 1e-7
    write_every_deg: float = 5.0
    tolerance_residuals: float = 1e-6

    def validate(self) -> None:
        if not (0 < self.max_Co <= 1.0):
            raise CreviceConfigError("crevice.numerics.max_Co em (0, 1]")
        if self.max_delta_t_s <= 0 or self.write_every_deg <= 0:
            raise CreviceConfigError(
                "crevice.numerics: passos e intervalo de escrita > 0")


# ------------------------------------------------------------------- config
@dataclass
class CreviceConfig:
    """Configuração completa de um caso crevice_flow."""
    geometry: CreviceGeometry
    chamber: ChamberBC
    thermal: CreviceThermal = field(default_factory=CreviceThermal)
    motion: CreviceMotion = field(default_factory=CreviceMotion)
    mesh: CreviceMesh = field(default_factory=CreviceMesh)
    numerics: CreviceNumerics = field(default_factory=CreviceNumerics)
    theta_unit: str = "deg"            # unidade da JANELA simulada
    window: Tuple[float, float] = (-180.0, 180.0)
    # Propriedades do gás — declaradas e rastreáveis (§7): nenhuma padrão
    # escondido; cada campo exige proveniência no YAML.
    gas: Dict[str, float] = field(default_factory=lambda: {
        "R_specific_J_kgK": 287.07, "gamma": 1.370,
        "dynamic_viscosity_Pa_s": 5.5e-5, "Pr": 0.7})
    gas_provenance: str = ""
    case_directory: Path = Path("results/crevice_case")
    notes: List[str] = field(default_factory=list)

    # ------------------------------------------------------------ conversões
    @property
    def dtheta_dt_deg_s(self) -> float:
        """dθ/dt = 6·RPM  [°/s]."""
        return 6.0 * self.motion.rpm

    @property
    def dtheta_dt_rad_s(self) -> float:
        """dθ/dt = 2π·RPM/60  [rad/s]."""
        return 2.0 * math.pi * self.motion.rpm / 60.0

    def theta_to_t(self, theta_deg: float) -> float:
        """θ [°] → t [s] (tabelas Function1 em tempo do solver)."""
        return theta_deg / self.dtheta_dt_deg_s

    def t_to_theta(self, t_s: float) -> float:
        return t_s * self.dtheta_dt_deg_s

    # ------------------------------------------------------------------ SI
    def to_si(self) -> Dict[str, float]:
        """Dimensões em SI (m) — tudo que o gerador de malha precisa."""
        g = self.geometry
        return {"bore": g.bore_diameter_mm * 1e-3,
                "gap": g.radial_gap_mm * 1e-3,
                "top_land_height": g.top_land_height_mm * 1e-3,
                "buffer_height": g.buffer_height_mm * 1e-3,
                "sector_angle": math.radians(g.sector_angle_deg)}

    # ------------------------------------------------------------- validação
    def validate(self) -> List[str]:
        """Validações do §4. Retorna avisos (não fatais); erros fatais
        levantam CreviceConfigError."""
        g, av = self.geometry, []
        for nome, v in (("bore_diameter_mm", g.bore_diameter_mm),
                        ("radial_gap_mm", g.radial_gap_mm),
                        ("top_land_height_mm", g.top_land_height_mm),
                        ("buffer_height_mm", g.buffer_height_mm)):
            if not (isinstance(v, (int, float)) and v > 0):
                raise CreviceConfigError(
                    f"crevice.geometry.{nome} deve ser positivo (mm); "
                    f"recebido {v!r}")
        if g.radial_gap_mm >= 0.5 * g.bore_diameter_mm:
            raise CreviceConfigError(
                "conectividade: radial_gap_mm deve ser ≪ raio do cilindro "
                "(folga anelar fina, g ≪ D)")
        if g.sector_angle_deg <= 0 or g.sector_angle_deg > 5.0:
            raise CreviceConfigError(
                "crevice.geometry.sector_angle_deg deve estar em (0, 5] "
                "(condição wedge do OpenFOAM)")
        if self.gas_provenance == "":
            raise CreviceConfigError(
                "crevice.gas_provenance: propriedades termodinâmicas e de "
                "transporte exigem proveniência declarada (§7) — informe "
                "de onde vêm R, γ, µ e Pr")
        for k in ("R_specific_J_kgK", "gamma", "dynamic_viscosity_Pa_s",
                  "Pr"):
            if k not in self.gas or not self.gas[k] > 0:
                raise CreviceConfigError(
                    f"crevice.gas.{k} ausente ou não positivo")
        self.thermal.validate()
        self.motion.validate()
        self.mesh.validate()
        self.numerics.validate()

        if self.theta_unit not in ("deg", "rad"):
            raise CreviceConfigError(
                f"crevice.theta_unit: 'deg' ou 'rad'; recebido "
                f"{self.theta_unit!r}")
        j = self.window
        if not (j[1] > j[0]):
            raise CreviceConfigError(
                f"crevice.window: janela invertida {j}")
        if self.theta_unit == "rad":   # normaliza para graus internamente
            self.window = (math.degrees(j[0]), math.degrees(j[1]))

        if self.chamber.bc_type not in ("totalPressure", "staticPressure"):
            raise CreviceConfigError(
                f"crevice.chamber.bc_type inválido: "
                f"{self.chamber.bc_type!r}")
        if not (isinstance(self.chamber.inflow_T_K, (int, float))
                and 100 < float(self.chamber.inflow_T_K) < 3000):
            raise CreviceConfigError(
                "crevice.chamber.inflow_T_K: estado do gás que entra "
                "exigido explicitamente (temperatura em K em (100, 3000))")
        if self.chamber.source not in ("experiment", "zero_d", "cfd"):
            raise CreviceConfigError(
                "crevice.chamber.source: 'experiment' | 'zero_d' | 'cfd' "
                "(proveniência obrigatória)")
        if self.chamber.blowby is not None:
            bb = self.chamber.blowby
            if "downstream_p_Pa" not in bb:
                raise CreviceConfigError(
                    "crevice.chamber.blowby: blow-by exige a pressão do "
                    "destino (downstream_p_Pa) declarada")
            raise CreviceConfigError(
                "blow-by (caminho de vazamento) ainda não implementado — "
                "fase 1: fresta comunicando apenas com a câmara; não "
                "declare blowby nesta versão")

        # cobertura da janela pelo arquivo de pressão (sem extrapolar)
        if not self.chamber.file.exists():
            raise CreviceConfigError(
                f"crevice.chamber.file não encontrado: {self.chamber.file}")
        th, p = read_pressure_table(self.chamber.file, self.chamber)
        th_lo, th_hi = th.min(), th.max()
        j = self.window
        if j[0] < th_lo - 1e-9 or j[1] > th_hi + 1e-9:
            msg = (f"janela {j} excede a cobertura do arquivo de pressão "
                   f"[{th_lo:.3f}, {th_hi:.3f}]")
            if self.chamber.extrapolate:
                self.notes.append("AVISO: extrapolação da pressão da "
                                  "câmara fora da janela do arquivo "
                                  f"({msg}) — opção marcada "
                                  "explicitamente em crevice.chamber."
                                  "extrapolate")
            else:
                raise CreviceConfigError(msg + "; reduza a janela ou "
                                              "marque extrapolate "
                                              "explicitamente")
        if self.numerics.max_delta_t_s > self.theta_to_t(0.1):
            self.notes.append(
                "AVISO: max_delta_t_s excede o passo equivalente a 0,1° "
                "de manivela — verifique a resolução temporal")
        return self.notes

    def resumo(self) -> Dict:
        return {"V_fresta_cm3": self.geometry.crevice_volume_m3 * 1e6,
                "dtheta_dt_deg_s": self.dtheta_dt_deg_s,
                "dtheta_dt_rad_s": self.dtheta_dt_rad_s,
                "janela_deg": list(self.window),
                "fonte_pressao": self.chamber.source,
                "bc_câmara": self.chamber.bc_type}


# --------------------------------------------------------- leitura do YAML
def read_pressure_table(path: Path, bc: ChamberBC) -> "tuple":
    """Lê a tabela p(θ) do arquivo declarado em ``bc`` (colunas nomeadas).
    Retorna (theta_deg, p_Pa). Conversão de unidades explícita e testada."""
    import csv
    sep = ";" if path.suffix.lower() in (".csv",) and \
        b";" in path.read_bytes()[:4096] else None
    with open(path, encoding="utf-8", newline="") as fh:
        rdr = csv.reader(fh, delimiter=sep or ",")
        cab = None
        for ln in rdr:                      # pula comentários/branqueadas;
            if not ln or all(not c.strip() for c in ln):
                continue                    # o cabeçalho é a 1ª linha com
            if ln[0].lstrip().startswith("#"):
                continue                    # as duas colunas declaradas
            if bc.columns["theta"] in ln and bc.columns["p"] in ln:
                cab = ln
                break
            raise CreviceConfigError(
                f"colunas {bc.columns} não encontradas em {path.name} "
                f"(linha: {ln}); ajuste crevice.chamber.columns")
        if cab is None:
            raise CreviceConfigError(
                f"{path}: cabeçalho com colunas {bc.columns} não "
                "encontrado")
        i_th = cab.index(bc.columns["theta"])
        i_p = cab.index(bc.columns["p"])
        th, p = [], []
        for ln in rdr:
            if not ln or all(not c.strip() for c in ln):
                continue
            if ln[0].lstrip().startswith("#"):
                continue
            th.append(float(ln[i_th]))
            p.append(float(ln[i_p]))
    if len(th) < 2:
        raise CreviceConfigError(
            f"{path.name}: menos de 2 pontos de pressão")
    th = [math.degrees(x) for x in th] if bc.theta_unit == "rad" else th
    f = {"Pa": 1.0, "kPa": 1e3, "bar": 1e5}[bc.p_unit]
    p = [x * f for x in p]
    ordem = sorted(range(len(th)), key=lambda i: th[i])
    import numpy as np
    return (np.array([th[i] for i in ordem]),
            np.array([p[i] for i in ordem]))


def read_crevice_config(path) -> CreviceConfig:
    """Lê o YAML do crevice_flow (seção ``crevice:``) e valida."""
    path = Path(path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or "crevice" not in raw:
        raise CreviceConfigError(
            f"{path}: YAML sem a seção 'crevice:'")
    c = raw["crevice"]
    try:
        geo = CreviceGeometry(
            bore_diameter_mm=float(c["geometry"]["bore_diameter_mm"]),
            radial_gap_mm=float(c["geometry"]["radial_gap_mm"]),
            top_land_height_mm=float(c["geometry"]["top_land_height_mm"]),
            buffer_height_mm=float(c["geometry"].get("buffer_height_mm",
                                                     2.0)),
            sector_angle_deg=float(c["geometry"].get("sector_angle_deg",
                                                     2.0)),
            ring_grooves=list(c["geometry"].get("ring_grooves", [])))
        ch = c["chamber"]
        base = Path(ch["file"])
        if not base.is_absolute():
            base = (path.parent / base).resolve()
        chamber = ChamberBC(
            source=ch["source"], file=base,
            theta_unit=ch.get("theta_unit", "deg"),
            p_unit=ch.get("p_unit", "kPa"),
            columns=ch.get("columns",
                           {"theta": "theta", "p": "P"}),
            extrapolate=bool(ch.get("extrapolate", False)),
            inflow_T_K=float(ch["inflow_T_K"]),
            bc_type=ch.get("bc_type", "totalPressure"),
            blowby=ch.get("blowby"))
        mov = c.get("motion", {})
        motion = CreviceMotion(
            rpm=float(mov.get("rpm", 1500.0)),
            liner_wall_velocity=bool(mov.get("liner_wall_velocity", True)),
            stroke_mm=mov.get("stroke_mm"),
            rod_length_mm=mov.get("rod_length_mm"))
        msh = c.get("mesh", {})
        mesh = CreviceMesh(n_gap=int(msh.get("n_gap", 6)),
                           n_crevice_axial=int(msh.get("n_crevice_axial",
                                                       10)),
                           n_buffer_axial=int(msh.get("n_buffer_axial", 8)),
                           gap_grading=float(msh.get("gap_grading", 1.0)))
        num = c.get("numerics", {})
        numerics = CreviceNumerics(
            max_Co=float(num.get("max_Co", 0.5)),
            max_delta_t_s=float(num.get("max_delta_t_s", 1e-7)),
            write_every_deg=float(num.get("write_every_deg", 5.0)))
        j = c.get("window", [-180.0, 180.0])
        cfg = CreviceConfig(
            geometry=geo, chamber=chamber, motion=motion, mesh=mesh,
            numerics=numerics,
            theta_unit=c.get("theta_unit", "deg"),
            window=(float(j[0]), float(j[1])),
            gas=dict(c.get("gas", {"R_specific_J_kgK": 287.07,
                                   "gamma": 1.370,
                                   "dynamic_viscosity_Pa_s": 5.5e-5,
                                   "Pr": 0.7})),
            gas_provenance=c.get("gas_provenance", ""),
            case_directory=Path(c.get("case_directory",
                                      "results/crevice_case")),
            notes=list(c.get("notes", [])))
    except KeyError as e:
        raise CreviceConfigError(
            f"{path}: campo obrigatório ausente em crevice: {e}") from None
    # A validação completa (§4) roda em cfg.validate() — chamada pelo CLI/
    # prepare, para que erros de uso venham com contexto do comando.
    return cfg