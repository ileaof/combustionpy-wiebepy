# -*- coding: utf-8 -*-
"""Aba Combustíveis: cadastro PERMANENTE de combustíveis para o módulo
CFD (gravação em data/fuels_custom.yaml) e exportação/importação CSV.

Os embutidos (H2, CH4, ethanol, diesel, B10_ensaio) permanecem sempre
disponíveis e nunca são alterados no código; um cadastro com o mesmo
nome sobrepõe o embutido em memória, com o registro marcando a
substituição. Misturas (aba "Misturas") são declaradas por percentual em
base energia, massa ou volume sobre combustíveis já cadastrados. Nenhuma propriedade é aceita sem fonte: o PCI exige
`LHV_source` obrigatório.
"""
import io
from pathlib import Path

import streamlit as st

from wiebepy.cfd.fuels import (
    BLEND_BASES, BLEND_BASIS_LABEL, BLEND_FEED_LABEL, BLEND_FEEDS,
    ENSAIO_PADRAO, FUELS, FuelSpec, all_fuel_specs, compute_blend,
    custom_fuels_path, delete_custom_fuel, export_fuels_csv, fuel_names,
    import_fuels_csv, load_custom_fuels, save_custom_blend, save_custom_fuel,
    validate_blend,
)
from wiebepy.i18n import t as _, tf

st.header(_("Combustíveis — cadastro permanente"), anchor=False)
st.caption(tf(
    "Cadastre combustíveis próprios para uso no CFD (e nos campos de "
    "combustível do wiebepy). O cadastro é gravado em `{arquivo}` e "
    "permanece entre sessões. Nenhuma propriedade é inventada: o PCI "
    "(LHV) só é aceito COM a fonte declarada "
    "(ficha técnica/certificado/literatura).",
    arquivo=custom_fuels_path().as_posix()))

st.info(tf("**Padrão das cargas de 45 % e 60 % do ensaio:** `{nome}` — "
           "B10 comercial (90 % diesel + 10 % biodiesel em volume) com "
           "propriedades MEDIDAS: PCI 39 191,3 kJ/kg, A/F 14,74, "
           "816,36 kg/m³ a 24,4 °C (Queiroz et al., submetido, Tab. 2). "
           "Misturas com etanol, CH4 etc. partem dele.",
           nome=ENSAIO_PADRAO["fuel"]), icon=":material/local_gas_station:")

_TAB_FORM, _TAB_MIST, _TAB_TABELA, _TAB_CSV = st.tabs(
    [_("Cadastrar"), _("Misturas"), _("Combustíveis cadastrados"),
     _("Exportar / ler CSV")])


def _csv_bytes(specs) -> bytes:
    """CSV completo do registro combinado (para download na GUI)."""
    import csv
    from wiebepy.cfd.fuels import _CAMPOS_CSV
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(_CAMPOS_CSV)
    from wiebepy.cfd.fuels import _valor_csv
    for s in specs.values():
        w.writerow([_valor_csv(s, c) for c in _CAMPOS_CSV])
    return buf.getvalue().encode("utf-8-sig")

# ------------------------------------------------------------------- form
with _TAB_FORM:
    st.markdown(
        _("Campos com * são obrigatórios. A composição (fórmula/surrogate) "
        "só é usada no modo reativo (não implementado); no modo prescrito "
        "o combustível entra apenas via m_f·PCI."))
    with st.form("form_combustivel", clear_on_submit=False):
        c1, c2 = st.columns(2)
        nome = c1.text_input(_("Nome (identificador) *"), key="fc_nome",
                             help=_("Sem espaços — ex.: C3H8, E85, my_diesel"))
        display = c2.text_input(_("Nome de exibição *"), key="fc_display")
        formula = st.text_input(
            _("Composição (fórmula ou surrogate) *"), key="fc_formula",
            help=_("Substância pura (ex.: CH4) ou descrição do surrogate"))
        c3, c4 = st.columns(2)
        fase = c3.select_slider(_("Fase"), ["gas", "liquid"], key="fc_fase")
        feed = c4.text_input(_("Alimentação assumida (modo prescrito)"),
                             key="fc_feed",
                             help=_("No modo prescrito apenas "
                                  "'premixed_gas (vaporizado)' é válida"))
        c5, c6 = st.columns(2)
        pci = c5.number_input(_("PCI (LHV) [kJ/kg] *"), min_value=0.0,
                              key="fc_pci",
                              help=_("Poder calorífico INFERIOR, 25 °C"))
        afr = c6.number_input(_("A/F estequiométrica [kg/kg] *"),
                              min_value=0.0, key="fc_afr")
        fonte = st.text_input(_("Fonte do PCI * (obrigatório)"),
                              key="fc_fonte",
                              help=_("Ex.: 'NIST WebBook', 'certificado do "
                                   "combustível do ensaio', referência "
                                   "com ano"))
        mm = st.number_input(_("Massa molar [kg/kmol] *"), min_value=0.0,
                             key="fc_mm")
        c7, c8 = st.columns(2)
        dens = c7.number_input(
            _("Massa específica [kg/m³] (líquidos)"), min_value=0.0,
            key="fc_dens", help=_("Necessária para misturas em base "
                                "volume. 0 = não informada."))
        dens_src = c8.text_input(
            _("Fonte e temperatura da massa específica"), key="fc_dens_src",
            help=_("Obrigatória se a massa específica for informada"))
        observ = st.text_area(_("Observações científicas"), key="fc_observ",
                              height=80)
        validez = st.text_area(_("Faixa de validade / limitações"),
                               key="fc_validez", height=60)
        submitted = st.form_submit_button(_("Gravar cadastro"), type="primary")
    if submitted:
        registro = {
            "name": nome, "display": display, "formula": formula,
            "phase": fase, "feed": feed or "premixed_gas (vaporizado)",
            "LHV_kJ_per_kg": pci, "LHV_source": fonte,
            "stoich_AFR": afr, "molar_mass_kg_per_kmol": mm,
            "remarks": observ, "validity": validez, "mechanism": None,
            "density_kg_per_m3": dens or None, "density_source": dens_src,
        }
        erros = save_custom_fuel(registro)
        if erros:
            st.error(_("Cadastro NÃO gravado:") + "\n"
                     + "\n".join(f"• {e}" for e in erros))
        else:
            st.success(tf("Combustível “{nome}” gravado em `{arquivo}` "
                          "(permanente).", nome=nome.strip(),
                          arquivo=custom_fuels_path().as_posix()))
            st.rerun()

# --------------------------------------------------------------- misturas
with _TAB_MIST:
    st.markdown(_(
        "Uma **mistura** é declarada pelos percentuais dos combustíveis já "
        "cadastrados, injetados pelo mesmo bico ou admitidos com o ar "
        "(ex.: CH4 em dual-fuel). O programa converte para fração mássica e "
        "calcula PCI, A/F estequiométrica e massa molar pelas regras de "
        "mistura (PCI = Σ y_i·PCI_i). A mistura gravada aparece em todas as "
        "listas de combustível."))
    specs_m = {n: s_ for n, s_ in all_fuel_specs().items()
               if not s_.is_blend}
    nomes_m = list(specs_m)
    base = st.radio(
        _("Base do percentual"), list(BLEND_BASES), horizontal=True,
        key="fm_base", format_func=lambda b: _(BLEND_BASIS_LABEL[b]),
        help=_("Energia: fração da energia do ciclo (taxa de substituição, "
             "usual na literatura). Massa: fração mássica. Volume: fração "
             "volumétrica dos líquidos (ex.: B10, E10) — exige massa "
             "específica com fonte."))
    n_comp = st.number_input(_("Número de componentes"), min_value=2,
                             max_value=5, value=2, step=1, key="fm_n")
    comps = []
    padroes = [ENSAIO_PADRAO["fuel"], "ethanol", "CH4", "diesel", "H2"]
    for i in range(int(n_comp)):
        c1, c2, c3 = st.columns([2, 1, 2])
        ini = padroes[i] if padroes[i] in nomes_m else nomes_m[0]
        fuel = c1.selectbox(tf("Componente {i}", i=i + 1), nomes_m,
                            index=nomes_m.index(ini), key=f"fm_f{i}",
                            format_func=lambda n: f"{n} — {specs_m[n].display}")
        pct = c2.number_input(
            _("Percentual [%]"), min_value=0.0, max_value=100.0,
            value=(90.0, 10.0, 0.0, 0.0, 0.0)[i], step=1.0, key=f"fm_p{i}")
        feed = c3.radio(_("Alimentação"), list(BLEND_FEEDS), horizontal=True,
                        key=f"fm_a{i}",
                        index=1 if specs_m[fuel].phase == "gas" else 0,
                        format_func=lambda a: _(BLEND_FEED_LABEL[a]))
        comps.append((fuel, pct, feed))
    erros_m = validate_blend(comps, base, all_fuel_specs())
    if erros_m:
        st.warning("\n".join(f"• {e}" for e in erros_m))
    else:
        r = compute_blend(comps, base)
        k1, k2, k3, k4 = st.columns(4)
        k1.metric(_("PCI da mistura [kJ/kg]"), f"{r['LHV_kJ_per_kg']:.1f}")
        k2.metric(_("A/F estequiométrica"), f"{r['stoich_AFR']:.3f}")
        k3.metric(_("Massa molar [kg/kmol]"),
                  f"{r['molar_mass_kg_per_kmol']:.2f}")
        k4.metric(_("Massa específica [kg/m³]"),
                  f"{r['density_kg_per_m3']:.1f}"
                  if r["density_kg_per_m3"] else "—")
        st.dataframe([{
            _("componente"): c["fuel"],
            _("alimentação"): _(BLEND_FEED_LABEL[c["feed"]]),
            _("declarado [%]"): c["percent_declared"],
            _("fração mássica"): round(c["mass_fraction"], 5),
            _("fração de energia"): round(c["energy_fraction"], 5),
            _("fração volumétrica"): (round(c["volume_fraction"], 5)
                                      if c["volume_fraction"] is not None
                                      else None)}
            for c in r["components"]], hide_index=True,
            use_container_width=True)
    with st.form("form_mistura"):
        c1, c2 = st.columns(2)
        nome_m = c1.text_input(_("Nome (identificador) *"), key="fm_nome",
                               help=_("Sem espaços — ex.: B10_E10vol"))
        disp_m = c2.text_input(_("Nome de exibição *"), key="fm_display")
        obs_m = st.text_area(_("Observações científicas"), key="fm_obs",
                             height=70)
        gravar_m = st.form_submit_button(_("Gravar mistura"), type="primary")
    if gravar_m:
        erros = save_custom_blend(nome_m, disp_m, comps, base, obs_m)
        if erros:
            st.error(_("Cadastro NÃO gravado:") + "\n"
                     + "\n".join(f"• {e}" for e in erros))
        else:
            st.success(tf("Combustível “{nome}” gravado em `{arquivo}` "
                          "(permanente).", nome=nome_m.strip(),
                          arquivo=custom_fuels_path().as_posix()))
            st.rerun()

# ------------------------------------------------------------------ table
with _TAB_TABELA:
    specs = all_fuel_specs()
    customs = load_custom_fuels()
    st.markdown(
        tf("Embutidos: {lista} (somente leitura).",
           lista=", ".join(f"**{n}**" for n in FUELS))
        + "  \n" + _("Cadastrados: ")
        + (", ".join(f"**{n}**" for n in customs)
           or _("— nenhum ainda —")))
    linhas = []
    for nome_f, s in specs.items():
        linhas.append({
            _("nome"): nome_f,
            _("tipo"): _("embutido") if nome_f in FUELS
            else _("mistura") if s.is_blend else _("cadastrado"),
            _("exibição"): s.display, _("composição"): s.formula,
            _("fase"): s.phase, _("PCI [kJ/kg]"): s.LHV_kJ_per_kg,
            _("A/F estq."): s.stoich_AFR,
            _("massa esp. [kg/m³]"): s.density_kg_per_m3,
            _("fonte do PCI"): s.LHV_source,
        })
    st.dataframe(linhas, use_container_width=True, hide_index=True)
    st.caption(_("Cada embutido tem fonte do PCI declarada; observações "
               "científicas completas (ex.: CH4 puro ≠ gás natural, "
               "diesel exige surrogate) aparecem no relatório CFD."))
    if customs:
        st.markdown(_("##### Remover cadastro"))
        alvo = st.selectbox(_("Combustível cadastrado"), list(customs),
                            key="fc_remover")
        if st.button(_("Remover cadastro"), type="secondary"):
            if delete_custom_fuel(alvo):
                st.success(tf("Cadastro “{nome}” removido.", nome=alvo))
                st.rerun()
            else:
                st.error(_("Não foi possível remover (embutidos não são "
                         "removíveis)."))

# -------------------------------------------------------------------- CSV
with _TAB_CSV:
    st.markdown(
        _("O CSV tem as colunas completas do cadastro "
        "(name, display, formula, phase, feed, LHV_kJ_per_kg, "
        "LHV_source, stoich_AFR, molar_mass_kg_per_kmol, remarks, "
        "validity, mechanism, density_kg_per_m3, density_source, blend) — "
        "a coluna blend traz a receita das misturas, ex.: "
        "`energy | B10_ensaio:70:injected ; CH4:30:intake` — serve como biblioteca portátil de "
        "combustíveis: exporte, edite no Excel e leia de volta."))
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(_("##### Exportar CSV"))
        caminho = st.text_input(_("Arquivo de saída"),
                                "data/fuels_export.csv", key="fc_csv_out")
        if st.button(_("Exportar todos para CSV")):
            try:
                nomes = export_fuels_csv(caminho.strip())
                st.success(tf("{n} combustíveis gravados em `{arquivo}`.",
                              n=len(nomes),
                              arquivo=Path(caminho).as_posix()))
            except (OSError, ValueError) as exc:
                st.error(tf("Falha ao exportar: {erro}", erro=exc))
        linhas_csv = _csv_bytes(specs)
        st.download_button(_("Baixar CSV (todos)"), data=linhas_csv,
                           file_name="fuels_export.csv",
                           mime="text/csv")
    with c2:
        st.markdown(_("##### Ler CSV (importar e gravar)"))
        st.caption(_("Cada linha válida é gravada no cadastro permanente; "
                   "linhas com problema são reportadas sem abortar o "
                   "lote. O PCI sem fonte é rejeitado."))
        up = st.file_uploader(_("Arquivo CSV"), type=["csv", "txt"],
                              key="fc_csv_in")
        if st.button(_("Importar CSV")) and up is not None:
            try:
                import tempfile
                with tempfile.NamedTemporaryFile(
                        suffix=".csv", delete=False) as tmpf:
                    tmpf.write(up.getvalue())
                    tmp_path = Path(tmpf.name)
                try:
                    res = import_fuels_csv(tmp_path)
                finally:
                    tmp_path.unlink(missing_ok=True)
                if res["gravados"]:
                    st.success(_("Gravados: ")
                               + ", ".join(res["gravados"]))
                if res["erros"]:
                    st.warning(_("Linhas rejeitadas:") + "\n"
                               + "\n".join(res["erros"]))
                if not res["gravados"] and not res["erros"]:
                    st.info(_("Nenhuma linha com 'name' encontrada."))
                st.rerun()
            except (OSError, ValueError) as exc:
                st.error(tf("Falha ao importar: {erro}", erro=exc))