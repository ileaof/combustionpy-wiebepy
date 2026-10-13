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

from wiebepy import i18n
from wiebepy.lang_en import EN

RAIZ = Path(__file__).resolve().parents[1] / "src" / "wiebepy"
GUI = RAIZ / "gui"
EMBRULHOS = ("_", "t", "tf")
CAMPO = re.compile(r"\{(\w+)")


def _textos_do_codigo() -> dict:
    """{texto: [arquivo:linha]} de cada _( "..." ) / tf( "..." ) do pacote."""
    achados: dict = {}
    for p in sorted(RAIZ.rglob("*.py")):
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


def _texto_dos_dados() -> str:
    """Arquivos de dados que acompanham o projeto (configs de exemplo,
    registros de combustível): alguns avisos moram neles, não no código."""
    partes = []
    for raiz in (RAIZ, RAIZ.parents[1] / "examples"):
        if not raiz.exists():
            continue
        for p in raiz.rglob("*"):
            if p.is_file() and p.suffix.lower() in (".yaml", ".yml",
                                                    ".json", ".csv"):
                try:
                    partes.append(p.read_text(encoding="utf-8-sig"))
                except (OSError, UnicodeDecodeError):
                    pass
    return "\n".join(partes)


def test_nenhuma_chave_morta():
    """Toda chave do dicionário tem de aparecer no código.

    Inclui as indiretas: valores de ``format_func``, nomes de tarefa e os
    rótulos de ``CaseState.label`` (em cfd/config.py).
    """
    dados = _texto_dos_dados()
    mortas = [k for k in sorted(set(EN) - _literais_do_pacote())
              if " ".join(k.split()) not in " ".join(dados.split())]
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


# --------------------------------------------------- relatórios HTML
def test_relatorios_seguem_o_idioma():
    """Os três relatórios saem no idioma pedido (e o padrão segue em pt)."""
    from wiebepy.pressure.fit import PressureSettings, fit_pressure, \
        read_pressure
    from wiebepy.pressure.html_report import report_html
    ensaio = (RAIZ.parents[1] / "examples" / "data"
              / "ensaio_P_exp_carga3_45.txt")
    if not ensaio.exists():
        pytest.skip("ensaio de exemplo ausente")
    d = read_pressure(ensaio, "rad", "bar")
    r = fit_pressure(d, PressureSettings(n_stages=2, runs=1, particles=20,
                                         iterations=40, seed=2))
    i18n.limpar_faltantes()
    en = report_html(r, d, lang="en")
    assert "<html lang='en'" in en
    assert "<h2>Engine and constants</h2>" in en
    assert "<h2>Fit configuration</h2>" in en
    assert "bore" in en and "diâmetro (bore)" not in en
    assert not i18n.faltantes(), i18n.faltantes()
    pt = report_html(r, d, lang="pt")
    assert "<html lang='pt-BR'" in pt
    assert "<h2>Motor e constantes</h2>" in pt


def test_relatorio_da_gui_usa_o_idioma_da_tela(monkeypatch):
    """O botão de relatório da GUI não recebe idioma: ele vem da tela."""
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest
    monkeypatch.setattr(i18n, "_atual", "en")
    at = AppTest.from_file(APP, default_timeout=180)
    at.session_state["gui_lang"] = "en"
    at.run()
    at.switch_page("app_pages/dados.py").run()
    exemplo = [b for b in at.button if b.key == "p_exemplo"]
    if not exemplo:
        pytest.skip("ensaio de exemplo ausente")
    exemplo[0].click().run()
    # modelo padrão + simulação: a página Modelo gera o relatório sem ajuste
    from wiebepy.pressure.fit import PressureSettings, fit_pressure
    r = fit_pressure(at.session_state["pdata"],
                     PressureSettings(n_stages=2, runs=1, particles=20,
                                      iterations=40, seed=2))
    at.session_state["pfit_result"] = r
    at.switch_page("app_pages/exportar.py").run()
    assert not at.exception, [e.value for e in at.exception]
    [b for b in at.button if b.key == "exp_rel_gerar"][0].click().run()
    html = at.session_state.get("_rel_exp_rel", b"").decode("utf-8")
    assert "<html lang='en'" in html and "Engine and constants" in html

def test_estados_de_caso_sempre_traduzidos():
    """`CaseState.label` nunca vai cru para a tela: foi assim que um
    "Validado" apareceu na interface em inglês (caso de fresta)."""
    import re
    for p in sorted((GUI).rglob("*.py")):
        texto = p.read_text(encoding="utf-8-sig")
        crus = [l.strip() for l in texto.splitlines()
                if re.search(r"(?<![\w(])\w*state\.label", l, re.I)
                and "_(" not in l]
        assert not crus, f"{p.name}: {crus}"


# ------------------------------------------------------------------- CLI
def test_cli_em_ingles(capsys):
    """--lang en alcança ajudas, hardware e mensagens de execução."""
    from wiebepy.cli.parser import _main
    assert _main(["--lang", "en", "--devices"]) == 0
    out = capsys.readouterr().out
    assert "Logical cores" in out and "Núcleos" not in out
    with pytest.raises(SystemExit):
        _main(["--lang", "en", "--help"])
    out = capsys.readouterr().out
    for termo in ("number of stages", "evaluation backend", "Input formats"):
        assert termo.lower() in out.lower(), termo
    assert _main(["--lang", "en", "--help-model"]) == 0
    assert "MATHEMATICAL FORMULATION" in capsys.readouterr().out
    assert _main(["--lang", "en", "--help-examples"]) == 0
    assert "READY-MADE EXAMPLES" in capsys.readouterr().out


def test_cli_em_portugues_por_padrao(capsys):
    from wiebepy.cli.parser import _main
    assert _main(["--devices"]) == 0
    assert "Núcleos lógicos" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        _main(["--help"])
    out = capsys.readouterr().out
    assert "número de estágios" in out.lower()
    assert _main(["--help-model"]) == 0
    assert "FORMULAÇÃO MATEMÁTICA" in capsys.readouterr().out


def test_lang_nao_grava_a_preferencia(tmp_path, monkeypatch):
    """--lang vale só para a execução: não mexe no arquivo do usuário."""
    arq = tmp_path / "gui.json"
    monkeypatch.setattr(i18n, "ARQUIVO", arq)
    from wiebepy.cli.parser import _main
    assert _main(["--lang", "en", "--devices"]) == 0
    assert not arq.exists()


def test_avisos_nunca_escapam_da_traducao():
    """Nenhum aviso visível fica fora de _()/tf().

    Foi assim que um "WARNING:" com texto em português apareceu no ajuste
    de pressão: o prefixo era inglês e a frase, portuguesa.
    """
    import ast
    fugitivos = []
    for p in sorted(RAIZ.rglob("*.py")):
        if p.name in ("i18n.py", "lang_en.py"):
            continue
        arv = ast.parse(p.read_text(encoding="utf-8-sig"))
        dentro = set()
        for n in ast.walk(arv):
            if isinstance(n, ast.Call):
                f = n.func
                nome = (f.attr if isinstance(f, ast.Attribute)
                        else getattr(f, "id", ""))
                if nome in ("_", "t", "tf", "ts"):
                    for a in ast.walk(n):
                        dentro.add(id(a))
        for n in ast.walk(arv):
            texto = None
            if isinstance(n, ast.Constant) and isinstance(n.value, str) \
                    and id(n) not in dentro:
                texto = n.value
            elif isinstance(n, ast.JoinedStr) and id(n) not in dentro:
                texto = "".join(x.value for x in n.values
                                if isinstance(x, ast.Constant))
            if texto and texto.lstrip().startswith(("WARNING:", "AVISO:")):
                fugitivos.append(f"{p.name}:{n.lineno} {texto[:60]!r}")
    assert not fugitivos, fugitivos
