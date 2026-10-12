# -*- coding: utf-8 -*-
"""Idioma da GUI (português/inglês).

Os testes de cobertura (dicionário completo, campos de ``format`` iguais,
nenhuma chave morta) não precisam do Streamlit; os dois últimos abrem a
interface com AppTest e conferem que a troca de idioma chega à tela.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from wiebepy.gui import i18n
from wiebepy.gui.lang_en import EN

RAIZ = Path(__file__).resolve().parents[1] / "src" / "wiebepy"
GUI = RAIZ / "gui"
EMBRULHOS = ("_", "t", "tf")
CAMPO = re.compile(r"\{(\w+)")


def _textos_do_codigo() -> dict:
    """{texto: [arquivo:linha]} de cada _( "..." ) / tf( "..." ) da GUI."""
    achados: dict = {}
    for p in sorted(GUI.rglob("*.py")):
        if p.name in ("i18n.py", "lang_en.py"):
            continue
        for n in ast.walk(ast.parse(p.read_text(encoding="utf-8-sig"))):
            if not isinstance(n, ast.Call) or not n.args:
                continue
            f = n.func
            nome = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
            a = n.args[0]
            if nome in EMBRULHOS and isinstance(a, ast.Constant) \
                    and isinstance(a.value, str):
                achados.setdefault(a.value, []).append(f"{p.name}:{a.lineno}")
    return achados


TEXTOS = _textos_do_codigo()


def test_ha_textos_embrulhados():
    assert len(TEXTOS) > 300, "o varredor de textos da GUI parou de funcionar"


def test_toda_mensagem_tem_traducao():
    falta = {k: v[0] for k, v in TEXTOS.items() if k not in EN}
    assert not falta, f"sem tradução em lang_en.EN: {falta}"


def test_nenhuma_traducao_vazia():
    vazias = [k for k, v in EN.items() if not isinstance(v, str) or not v.strip()]
    assert not vazias, vazias


def _literais_do_pacote() -> set:
    """Toda string literal do pacote, já com as concatenações implícitas
    juntadas pelo parser (no código as frases longas são quebradas em
    várias linhas)."""
    todas = set()
    for p in sorted(RAIZ.rglob("*.py")):
        if p.name == "lang_en.py":
            continue
        for n in ast.walk(ast.parse(p.read_text(encoding="utf-8-sig"))):
            if isinstance(n, ast.Constant) and isinstance(n.value, str):
                todas.add(n.value)
    return todas


def test_nenhuma_chave_morta():
    """Toda chave do dicionário tem de aparecer no código.

    Inclui as indiretas: valores de ``format_func``, nomes de tarefa e os
    rótulos de ``CaseState.label`` (em cfd/config.py).
    """
    mortas = sorted(set(EN) - _literais_do_pacote())
    assert not mortas, f"chaves que não existem mais no código: {mortas}"


def test_campos_de_format_preservados():
    """{n}, {u}, {erro}… têm de existir, com o mesmo nome, nos dois idiomas."""
    erros = []
    for pt, en in EN.items():
        if set(CAMPO.findall(pt)) != set(CAMPO.findall(en)):
            erros.append((pt, en))
    assert not erros, erros


def test_markdown_equilibrado():
    """Negrito e crase do português se mantêm na tradução."""
    erros = [(pt, en) for pt, en in EN.items()
             if pt.count("**") != en.count("**") or pt.count("`") != en.count("`")]
    assert not erros, erros


# ------------------------------------------------------------------ runtime
def test_t_devolve_portugues_e_ingles():
    i18n.definir_idioma("pt", gravar=False)
    assert i18n.t("Dados") == "Dados"
    i18n.definir_idioma("en", gravar=False)
    assert i18n.t("Dados") == "Data"
    assert i18n.tf("Versão {v}", v="1.0") == "Version 1.0"
    i18n.definir_idioma("pt", gravar=False)


def test_texto_sem_traducao_cai_para_portugues():
    i18n.limpar_faltantes()
    i18n.definir_idioma("en", gravar=False)
    assert i18n.t("texto inexistente no dicionário") == \
        "texto inexistente no dicionário"
    assert "texto inexistente no dicionário" in i18n.faltantes()
    i18n.limpar_faltantes()
    i18n.definir_idioma("pt", gravar=False)


def test_idioma_desconhecido_recusado():
    with pytest.raises(ValueError):
        i18n.definir_idioma("fr")


def test_escolha_e_gravada_e_relida(tmp_path, monkeypatch):
    monkeypatch.setattr(i18n, "ARQUIVO", tmp_path / "gui.json")
    monkeypatch.setattr(i18n, "_atual", None)
    i18n.definir_idioma("en")
    monkeypatch.setattr(i18n, "_atual", None)        # como numa sessão nova
    assert i18n.idioma() == "en"
    i18n.definir_idioma("pt")
    monkeypatch.setattr(i18n, "_atual", None)
    assert i18n.idioma() == "pt"


def test_disco_somente_leitura_nao_impede_a_troca(tmp_path, monkeypatch):
    monkeypatch.setattr(i18n, "ARQUIVO", tmp_path / "sem" / "permissao"
                        / "gui.json")

    def _explode(*a, **k):
        raise OSError("somente leitura")

    monkeypatch.setattr(Path, "mkdir", _explode)
    i18n.definir_idioma("en")                        # não levanta
    assert i18n.idioma() == "en"
    i18n.definir_idioma("pt", gravar=False)


# --------------------------------------------------------------- na interface
APP = str(GUI / "app.py")


def test_interface_em_ingles(monkeypatch):
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest
    # o AppTest chama os format_func FORA da execução do script (onde não há
    # sessão); sem isto, ele formataria as opções em português e não as
    # acharia na lista já traduzida da tela
    monkeypatch.setattr(i18n, "_atual", "en")
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["gui_lang"] = "en"
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert any("Wiebe functions with 1 to 5 stages" in t.value for t in at.title)
    assert [b for b in at.button if b.label == "Help"]
    for pagina in ("app_pages/dados.py", "app_pages/modelo.py",
                   "app_pages/ajuste.py", "app_pages/comparacao.py",
                   "app_pages/exportar.py", "app_pages/desempenho.py",
                   "app_pages/cfd.py", "app_pages/combustiveis.py"):
        at.switch_page(pagina).run()
        assert not at.exception, (pagina, [e.value for e in at.exception])
    assert any("Fuels — permanent registry" in h.value for h in at.header)
    at.switch_page("app_pages/dados.py").run()
    assert any("Experimental data" in h.value for h in at.header)
    assert not i18n.faltantes(), i18n.faltantes()


def test_modo_pressao_em_ingles(monkeypatch):
    """O modo pressão (maior parte da interface) com o ensaio de exemplo."""
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest
    monkeypatch.setattr(i18n, "_atual", "en")
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["gui_lang"] = "en"
    at.run()
    at.switch_page("app_pages/dados.py").run()
    exemplo = [b for b in at.button if b.key == "p_exemplo"]
    if not exemplo:                 # sem o arquivo de ensaio no clone
        pytest.skip("ensaio de exemplo ausente")
    exemplo[0].click().run()
    assert not at.exception, [e.value for e in at.exception]
    rotulos = [m.label for m in at.get("metric")]
    assert "P at IVC" in rotulos and "Observations" in rotulos
    assert not i18n.faltantes(), i18n.faltantes()


def test_interface_em_portugues_por_padrao():
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception, [e.value for e in at.exception]
    assert any("funções Wiebe de 1 a 5 estágios" in t.value for t in at.title)
    assert [b for b in at.button if b.label == "Ajuda"]
