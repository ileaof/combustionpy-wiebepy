# -*- coding: utf-8 -*-
"""Aba Combustíveis: cadastro PERMANENTE de combustíveis para o módulo
CFD (gravação em data/fuels_custom.yaml) e exportação/importação CSV.

Os quatro embutidos (H2, CH4, ethanol, diesel) permanecem sempre
disponíveis e nunca são alterados no código; um cadastro com o mesmo
nome sobrepõe o embutido em memória, com o registro marcando a
substituição. Nenhuma propriedade é aceita sem fonte: o PCI exige
`LHV_source` obrigatório.
"""
import io
from pathlib import Path

import streamlit as st

from wiebepy.cfd.fuels import (
    FuelSpec, FUELS, all_fuel_specs, custom_fuels_path, delete_custom_fuel,
    export_fuels_csv, fuel_names, import_fuels_csv, load_custom_fuels,
    save_custom_fuel,
)

st.header("Combustíveis — cadastro permanente", anchor=False)
st.caption(
    "Cadastre combustíveis próprios para uso no CFD (e nos campos de "
    "combustível do wiebepy). O cadastro é gravado em "
    f"`{custom_fuels_path().as_posix()}` e permanece entre sessões. "
    "Nenhuma propriedade é inventada: o PCI (LHV) só é aceito COM a "
    "fonte declarada (ficha técnica/certificado/literatura).")

_TAB_FORM, _TAB_TABELA, _TAB_CSV = st.tabs(
    ["Cadastrar", "Combustíveis cadastrados", "Exportar / ler CSV"])


def _csv_bytes(specs) -> bytes:
    """CSV completo do registro combinado (para download na GUI)."""
    import csv
    from wiebepy.cfd.fuels import _CAMPOS_CSV
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(_CAMPOS_CSV)
    for s in specs.values():
        w.writerow([getattr(s, c) if getattr(s, c) is not None else ""
                    for c in _CAMPOS_CSV])
    return buf.getvalue().encode("utf-8-sig")

# ------------------------------------------------------------------- form
with _TAB_FORM:
    st.markdown(
        "Campos com * são obrigatórios. A composição (fórmula/surrogate) "
        "só é usada no modo reativo (não implementado); no modo prescrito "
        "o combustível entra apenas via m_f·PCI.")
    with st.form("form_combustivel", clear_on_submit=False):
        c1, c2 = st.columns(2)
        nome = c1.text_input("Nome (identificador) *", key="fc_nome",
                             help="Sem espaços — ex.: C3H8, E85, my_diesel")
        display = c2.text_input("Nome de exibição *", key="fc_display")
        formula = st.text_input(
            "Composição (fórmula ou surrogate) *", key="fc_formula",
            help="Substância pura (ex.: CH4) ou descrição do surrogate")
        c3, c4 = st.columns(2)
        fase = c3.select_slider("Fase", ["gas", "liquid"], key="fc_fase")
        feed = c4.text_input("Alimentação assumida (modo prescrito)",
                             key="fc_feed",
                             help="No modo prescrito apenas "
                                  "'premixed_gas (vaporizado)' é válida")
        c5, c6 = st.columns(2)
        pci = c5.number_input("PCI (LHV) [kJ/kg] *", min_value=0.0,
                              key="fc_pci",
                              help="Poder calorífico INFERIOR, 25 °C")
        afr = c6.number_input("A/F estequiométrica [kg/kg] *",
                              min_value=0.0, key="fc_afr")
        fonte = st.text_input("Fonte do PCI * (obrigatório)",
                              key="fc_fonte",
                              help="Ex.: 'NIST WebBook', 'certificado do "
                                   "combustível do ensaio', referência "
                                   "com ano")
        mm = st.number_input("Massa molar [kg/kmol] *", min_value=0.0,
                             key="fc_mm")
        observ = st.text_area("Observações científicas", key="fc_observ",
                              height=80)
        validez = st.text_area("Faixa de validade / limitações",
                               key="fc_validez", height=60)
        submitted = st.form_submit_button("Gravar cadastro", type="primary")
    if submitted:
        registro = {
            "name": nome, "display": display, "formula": formula,
            "phase": fase, "feed": feed or "premixed_gas (vaporizado)",
            "LHV_kJ_per_kg": pci, "LHV_source": fonte,
            "stoich_AFR": afr, "molar_mass_kg_per_kmol": mm,
            "remarks": observ, "validity": validez, "mechanism": None,
        }
        erros = save_custom_fuel(registro)
        if erros:
            st.error("Cadastro NÃO gravado:\n" + "\n".join(f"• {e}"
                                                           for e in erros))
        else:
            st.success(f"Combustível '{nome.strip()}' gravado em "
                       f"`{custom_fuels_path().as_posix()}` "
                       "(permanente).")
            st.rerun()

# ------------------------------------------------------------------ table
with _TAB_TABELA:
    specs = all_fuel_specs()
    customs = load_custom_fuels()
    st.markdown(
        f"Embutidos: {', '.join(f'**{n}**' for n in FUELS)} (somente "
        "leitura).  \nCadastrados: "
        + (", ".join(f"**{n}**" for n in customs) or "— nenhum ainda —"))
    linhas = []
    for nome_f, s in specs.items():
        linhas.append({
            "nome": nome_f,
            "tipo": "embutido" if nome_f in FUELS else "cadastrado",
            "exibição": s.display, "composição": s.formula,
            "fase": s.phase, "PCI [kJ/kg]": s.LHV_kJ_per_kg,
            "A/F estq.": s.stoich_AFR,
            "fonte do PCI": s.LHV_source,
        })
    st.dataframe(linhas, use_container_width=True, hide_index=True)
    st.caption("Cada embutido tem fonte do PCI declarada; observações "
               "científicas completas (ex.: CH4 puro ≠ gás natural, "
               "diesel exige surrogate) aparecem no relatório CFD.")
    if customs:
        st.markdown("##### Remover cadastro")
        alvo = st.selectbox("Combustível cadastrado", list(customs),
                            key="fc_remover")
        if st.button("Remover cadastro", type="secondary"):
            if delete_custom_fuel(alvo):
                st.success(f"Cadastro '{alvo}' removido.")
                st.rerun()
            else:
                st.error("Não foi possível remover (embutidos não são "
                         "removíveis).")

# -------------------------------------------------------------------- CSV
with _TAB_CSV:
    st.markdown(
        "O CSV tem as colunas completas do cadastro "
        "(name, display, formula, phase, feed, LHV_kJ_per_kg, "
        "LHV_source, stoich_AFR, molar_mass_kg_per_kmol, remarks, "
        "validity, mechanism) — serve como biblioteca portátil de "
        "combustíveis: exporte, edite no Excel e leia de volta.")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("##### Exportar CSV")
        caminho = st.text_input("Arquivo de saída",
                                "data/fuels_export.csv", key="fc_csv_out")
        if st.button("Exportar todos para CSV"):
            try:
                nomes = export_fuels_csv(caminho.strip())
                st.success(f"{len(nomes)} combustíveis gravados em "
                           f"`{Path(caminho).as_posix()}`.")
            except (OSError, ValueError) as exc:
                st.error(f"Falha ao exportar: {exc}")
        linhas_csv = _csv_bytes(specs)
        st.download_button("Baixar CSV (todos)", data=linhas_csv,
                           file_name="fuels_export.csv",
                           mime="text/csv")
    with c2:
        st.markdown("##### Ler CSV (importar e gravar)")
        st.caption("Cada linha válida é gravada no cadastro permanente; "
                   "linhas com problema são reportadas sem abortar o "
                   "lote. O PCI sem fonte é rejeitado.")
        up = st.file_uploader("Arquivo CSV", type=["csv", "txt"],
                              key="fc_csv_in")
        if st.button("Importar CSV") and up is not None:
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
                    st.success("Gravados: "
                               + ", ".join(res["gravados"]))
                if res["erros"]:
                    st.warning("Linhas rejeitadas:\n"
                               + "\n".join(res["erros"]))
                if not res["gravados"] and not res["erros"]:
                    st.info("Nenhuma linha com 'name' encontrada.")
                st.rerun()
            except (OSError, ValueError) as exc:
                st.error(f"Falha ao importar: {exc}")