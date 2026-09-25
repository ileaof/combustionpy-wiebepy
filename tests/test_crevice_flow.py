# -*- coding: utf-8 -*-
"""
test_crevice_flow.py — Testes progressivos do módulo crevice_flow.

Níveis cobertos AQUI (sem OpenFOAM — a execução real é verificada nos
docs/cfd e nos docs do módulo):
  • N1  validação da config e conversões dθ/dt explícitas (§6);
  • N1b geometria: convenção de vértices do blockMesh, volumes, regras;
  • N2/N5/N6 parsing de séries e balanços massa/energia com dados
    SINTÉTICOS de fixação (formato real do OF13) — os balanços sobre o
    caso REAL executado estão registrados em docs/cfd/crevice.md;
  • N9  não-interferência: com o módulo ausente/sem config, os modelos
    Wiebe e o resto do wiebepy seguem idênticos (import condicional).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wiebepy.crevice_flow.config import (CreviceConfigError, CreviceConfig,
                                         read_crevice_config)
from wiebepy.crevice_flow.geometry import CreviceDomain, piston_speed_table
from wiebepy.crevice_flow.results import CreviceResults

EXEMPLO = Path(__file__).resolve().parents[1] / "examples/crevice/crevice_exemplo.yaml"


# ==================================================================== N1
def test_n1_conversoes_angulo_tempo_explicitas():
    cfg = read_crevice_config(EXEMPLO)
    rpm = cfg.motion.rpm
    assert cfg.dtheta_dt_deg_s == pytest.approx(6.0 * rpm)
    assert cfg.dtheta_dt_rad_s == pytest.approx(2 * np.pi * rpm / 60.0)
    # t = θ / (6·rpm) — conversão declarada, idêntica à do cfd
    assert cfg.theta_to_t(6.0 * rpm) == pytest.approx(1.0)


def test_n1_config_valida_carrega():
    cfg = read_crevice_config(EXEMPLO)
    avisos = cfg.validate()
    assert isinstance(avisos, list)
    # janela coberta pelo arquivo (sem extrapolação)
    assert cfg.chamber.extrapolate is False


def test_n1_janela_fora_do_arquivo_eh_erro_duro(tmp_path):
    csv = tmp_path / "p.csv"
    csv.write_text("theta_deg,P_bar\n-10,2\n10,3\n", encoding="utf-8")
    cfg = read_crevice_config(EXEMPLO)
    cfg.chamber.file = csv
    cfg.chamber.source = "experiment"
    # janela padrão do exemplo (−180…180) não é coberta
    with pytest.raises(CreviceConfigError, match="cobert|janela|extrapol"):
        cfg.validate()


def test_n1_blowby_rejeitado_no_nivel_submodelo(tmp_path):
    csv = tmp_path / "p.csv"
    csv.write_text("theta_deg,P_bar\n-180,1\n180,1\n", encoding="utf-8")
    base = yaml.safe_load(EXEMPLO.read_text(encoding="utf-8"))
    base["crevice"]["chamber"]["file"] = str(csv)
    base["crevice"]["chamber"]["blowby"] = {"downstream_P_Pa": 1e5}
    yml = tmp_path / "c.yaml"
    yml.write_text(yaml.safe_dump(base), encoding="utf-8")
    cfg = read_crevice_config(yml)
    with pytest.raises(CreviceConfigError, match="blow-by|blowby"):
        cfg.validate()


def test_n1_sem_proveniencia_do_gas_eh_erro():
    cfg = read_crevice_config(EXEMPLO)
    cfg.gas_provenance = ""
    with pytest.raises(CreviceConfigError, match="proveniência|gas"):
        cfg.validate()


# ================================================================== N1b
def test_n1b_geometria_volume_e_regras():
    cfg = read_crevice_config(EXEMPLO)
    dom = CreviceDomain(cfg)
    dom.validate()
    # volume anelar fino: π·D_med·g·h
    d, g, h = 86e-3, 0.5e-3, 6e-3
    esperado = np.pi * (d - g) * g * h
    assert dom.cfg.geometry.crevice_volume_m3 == pytest.approx(esperado,
                                                               rel=0.02)
    # folga > 2 % do diâmetro é erro duro
    dom2 = CreviceDomain(read_crevice_config(EXEMPLO))
    dom2.cfg.geometry.radial_gap_mm = 5.0
    with pytest.raises(CreviceConfigError, match="2 %"):
        dom2.validate()


def test_n1b_vertices_na_convencao_do_blockmesh():
    """x: 0→1 radial; y: 0→3 tangencial; z: 0→4 axial (bug 'inside-out'
    já cometido e corrigido — fixado aqui)."""
    cfg = read_crevice_config(EXEMPLO)
    v = CreviceDomain(cfg)._vertices()
    assert v[1, 0] > v[0, 0]                    # 1 mais externo que 0
    assert v[3, 1] > v[0, 1]                    # 3 mais tangencial que 0
    assert v[4, 2] > v[0, 2]                    # 4 mais alto que 0
    txt = CreviceDomain(cfg).blockmesh_dict()
    assert "hex (0 1 2 3 4 5 6 7)" in txt
    assert "(4 5 6 7)" in txt                   # topo = câmara
    assert "wedge" in txt


def test_n1b_cinematica_pistao_continua():
    cfg = read_crevice_config(EXEMPLO)
    th, vz = piston_speed_table(cfg, n=181)
    assert len(th) == len(vz) == 181
    vz = np.array(vz)
    assert abs(vz).max() < 30.0                 # m/s plausível p/ 1500 rpm
    # PMS (θ=0): velocidade ~ 0
    i0 = int(np.argmin(np.abs(np.array(th))))
    assert abs(vz[i0]) < 0.05


# ============================================================ N2/N5/N6
def _escreve_dat(p: Path, cab, linhas):
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        for c in cab:
            fh.write("# " + c + "\n")
        for l in linhas:
            fh.write("\t".join(f"{x:.8e}" for x in l) + "\n")


def _caso_sintetico(tmp_path, mdot, t=None, m0=1e-9, t_in=600.0):
    """Caso com séries sintéticas no formato real do OF13: ṁ constante
    (negativo = enchendo) → balanço de massa deve fechar; calor nulo."""
    d = tmp_path / "case"
    if t is None:
        t = np.linspace(0.0, 1e-4, len(mdot))
    # massa coerente com o sinal: ṁ<0 = entrada → m(t) = m0 − ∫ṁ dt
    m = m0 - np.concatenate(([0], np.cumsum(
        0.5 * (mdot[1:] + mdot[:-1]) * np.diff(t))))
    base = {"Time": t}
    _escreve_dat(d / "postProcessing/fluxoMassaCamara/0/surfaceFieldValue.dat",
                 ["Time \tsum(phi)"], np.column_stack([t, mdot]))
    _escreve_dat(d / "postProcessing/pT_camara/0/surfaceFieldValue.dat",
                 ["Time \tareaAverage(p)\tareaAverage(T)"],
                 np.column_stack([t, np.full_like(t, 1e5),
                                  np.full_like(t, t_in)]))
    _escreve_dat(d / "postProcessing/massaTotal/0/volFieldValue.dat",
                 ["Time \tvolIntegrate(rho)"], np.column_stack([t, m]))
    _escreve_dat(d / "postProcessing/massaFresta/0/volFieldValue.dat",
                 ["Time \tvolIntegrate(rho)"],
                 np.column_stack([t, 0.7 * m]))
    _escreve_dat(d / "postProcessing/massaBuffer/0/volFieldValue.dat",
                 ["Time \tvolIntegrate(rho)"],
                 np.column_stack([t, 0.3 * m]))
    _escreve_dat(d / "postProcessing/energiaFresta/0/volFieldValue.dat",
                 ["Time \tvolIntegrate(p)"],
                 np.column_stack([t, np.full_like(t, 5e-4)]))
    _escreve_dat(d / "postProcessing/energiaBuffer/0/volFieldValue.dat",
                 ["Time \tvolIntegrate(p)"],
                 np.column_stack([t, np.full_like(t, 2e-4)]))
    _escreve_dat(d / "postProcessing/calorLiner/0/surfaceFieldValue.dat",
                 ["Time \tareaIntegrate(wallHeatFlux)"],
                 np.column_stack([t, np.zeros_like(t)]))
    _escreve_dat(d / "postProcessing/calorPistao/0/surfaceFieldValue.dat",
                 ["Time \tareaIntegrate(wallHeatFlux)"],
                 np.column_stack([t, np.zeros_like(t)]))
    meta = {
        "janela_deg": [-180.0, 180.0],
        "rotacao": {"rpm": 1500.0,
                    "dtheta_dt_deg_s": 9000.0,
                    "dtheta_dt_rad_s": 157.08},
        "gas": {"gamma": 1.370, "R_specific_J_kgK": 287.07},
        "condicao_camara": {"inflow_T_K": t_in},
    }
    (d / "case_config.yaml").write_text(yaml.safe_dump(meta),
                                        encoding="utf-8")
    return d


def test_n5_entrada_e_saida_separadas_por_sinal(tmp_path):
    """Enchendo (ṁ<0) depois esvaziando (ṁ>0): acumulados separados."""
    t = np.linspace(0.0, 2e-4, 20)              # transição entre amostras
    mdot = np.where(t < 1e-4, -2e-6, 2e-6)      # inverte no meio
    d = _caso_sintetico(tmp_path / "rev", mdot, t=t)
    r = CreviceResults.load(d)
    assert r.mdot_in[r.t < 1e-4].max() > 0
    assert r.mdot_out[r.t > 1e-4].max() > 0
    assert r.m_out_cum()[-1] > 0 and r.m_in_cum()[-1] > 0
    # metade entra, metade sai (trapezoidal nos mesmos instantes)
    assert r.m_in_cum()[-1] == pytest.approx(r.m_out_cum()[-1], rel=1e-6)
    bm = r.balanco_massa()
    assert bm.ok, bm.detalhe


def test_n2_conservacao_de_massa_fechada(tmp_path):
    """Sem fluxo (ṁ=0): massa constante — resíduo nulo."""
    t = np.linspace(0.0, 1e-4, 11)
    d = _caso_sintetico(tmp_path / "fech", np.zeros_like(t))
    r = CreviceResults.load(d)
    bm = r.balanco_massa()
    assert bm.ok and bm.rel_pct == pytest.approx(0.0, abs=1e-9)


def test_n6_balanco_de_energia_com_calor(tmp_path):
    """ΔU = entalpia líquida − calor às paredes (sintético coerente)."""
    t = np.linspace(0.0, 1e-4, 11)
    mdot = np.full_like(t, -1e-6)               # enchendo
    d = _caso_sintetico(tmp_path / "en", mdot)
    r = CreviceResults.load(d)
    # injeta calor às paredes coerente: U cai exatamente o calor integrado
    gam = 1.370
    q_w = -1e-3                                # W (OF: negativo = gás perde)
    # reescreve as séries de calor com valor constante
    _escreve_dat(
        d / "postProcessing/calorLiner/0/surfaceFieldValue.dat",
        ["Time \tareaIntegrate(wallHeatFlux)"],
        np.column_stack([t, np.full_like(t, q_w / 2)]))
    _escreve_dat(
        d / "postProcessing/calorPistao/0/surfaceFieldValue.dat",
        ["Time \tareaIntegrate(wallHeatFlux)"],
        np.column_stack([t, np.full_like(t, q_w / 2)]))
    # e U decaindo com o calor integrado (sintético)
    cp = gam * 287.07 / (gam - 1.0)
    e_in = np.concatenate(([0], np.cumsum(
        0.5 * (1e-6 * cp * 600 + 1e-6 * cp * 600) * np.diff(t))))
    u0 = 6e-4 / (gam - 1.0)
    q_cum = np.concatenate(([0], np.cumsum(
        0.5 * (q_w + q_w) * np.diff(t))))      # ∫q̇ dt com sinal OF
    # convenção: q>0 gás perde → U(t) = U0 + E_in − ∫q_paredes(gás perde)
    u = u0 + e_in + q_cum                      # q_w < 0 → U cai
    _escreve_dat(
        d / "postProcessing/energiaFresta/0/volFieldValue.dat",
        ["Time \tvolIntegrate(p)"],
        np.column_stack([t, u * (gam - 1.0) * 0.7]))
    _escreve_dat(
        d / "postProcessing/energiaBuffer/0/volFieldValue.dat",
        ["Time \tvolIntegrate(p)"],
        np.column_stack([t, u * (gam - 1.0) * 0.3]))
    r = CreviceResults.load(d)
    be = r.balanco_energia()
    assert be.ok, be.detalhe


def test_n2_balanço_falho_nunca_passa_silencioso(tmp_path):
    """Massa incoerente → ok=False explícito (nunca silencioso)."""
    t = np.linspace(0.0, 1e-4, 11)
    d = _caso_sintetico(tmp_path / "ruim", np.full_like(t, -1e-6))
    # corrompe a massa total (soma 20 %)
    p = d / "postProcessing/massaTotal/0/volFieldValue.dat"
    linhas = [l for l in p.read_text(encoding="utf-8").splitlines()
              if not l.startswith("#")]
    corromp = []
    for i, l in enumerate(linhas):
        a = l.split("\t")
        a[1] = f"{float(a[1]) * (1.2 if i else 1.0):.8e}"
        corromp.append("\t".join(a))
    _escreve_dat(p, ["Time \tvolIntegrate(rho)"],
                 [[float(x) for x in l.split("\t")] for l in corromp])
    r = CreviceResults.load(d)
    bm = r.balanco_massa()
    assert not bm.ok


# ==================================================================== N9
def test_n9_modulo_e_opcional_nao_interfere():
    """Import do módulo não altera os modelos Wiebe (0-D intactos)."""
    from wiebepy.pressure.model import simulate  # noqa: F401
    from wiebepy.crevice_flow import CreviceConfig  # noqa: F401
    from wiebepy.pressure.model import simulate as simulate_depois
    assert simulate is simulate_depois


def test_n9_cli_delega_mesmo_sem_config(tmp_path):
    from wiebepy.cfd.cli import main_cfd
    # comando crevice sem argumentos → erro de uso do SUBMÓDULO (rc 2),
    # não crash do cfd
    with pytest.raises(SystemExit) as e:
        main_cfd(["crevice"])
    assert e.value.code == 2

# ============================================== N2b: restart (subpastas)
def test_n2_check_completion_com_restart_subpastas(tmp_path):
    """Restart do OF13 cria postProcessing/<startTime>/*.dat: o
    check_completion precisa ler a ÚLTIMA subpasta (bug real do caso
    demo: _last_time com glob('*.dat') retornava None e marcava o caso
    como FAILED mesmo com janela coberta)."""
    from wiebepy.crevice_flow.runner import check_completion
    d = tmp_path / "case"
    d.mkdir()
    log = d / "logs/foamRun.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text("Time = 0.04s\nEnd\n", encoding="utf-8")
    t0 = np.array([0.0, 0.000556])
    t1 = np.array([0.013889, 0.04])
    _escreve_dat(d / "postProcessing/fluxoMassaCamara/0/"
                 "surfaceFieldValue.dat", ["Time \tsum(phi)"],
                 np.column_stack([t0, np.zeros_like(t0)]))
    _escreve_dat(d / "postProcessing/fluxoMassaCamara/0.01388889/"
                 "surfaceFieldValue.dat", ["Time \tsum(phi)"],
                 np.column_stack([t1, np.zeros_like(t1)]))
    ok, msg = check_completion(d, 0.04)
    assert ok, msg
    # sem a subpasta do restart: janela não coberta → falho, explícito
    import shutil
    shutil.rmtree(d / "postProcessing/fluxoMassaCamara/0.01388889")
    ok2, msg2 = check_completion(d, 0.04)
    assert not ok2 and "0.000556" in msg2
