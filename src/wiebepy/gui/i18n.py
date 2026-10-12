# -*- coding: utf-8 -*-
"""
i18n.py — Idioma da interface gráfica (português e inglês).

A chave de tradução é o **próprio texto em português**, como no gettext: no
código escreve-se ``_("Fração de massa queimada")`` e o dicionário
``lang_en.EN`` traz a versão inglesa. Texto sem tradução cai de volta para o
português (nunca quebra a tela) e fica registrado em :func:`faltantes`, que o
teste ``test_gui_i18n`` usa para apontar o que falta.

A escolha vive em ``st.session_state["gui_lang"]``, é gravada em
``~/.wiebepy/gui.json`` (sobrevive ao reinício do servidor, no mesmo padrão do
``cfd_env.json``) e pode vir da URL (``?lang=en``). Fora do Streamlit — nos
testes, por exemplo — valem :func:`definir_idioma` e o padrão português.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from .lang_en import EN

IDIOMAS: Dict[str, str] = {"pt": "Português", "en": "English"}
PADRAO = "pt"
CHAVE_ESTADO = "gui_lang"
ARQUIVO = Path.home() / ".wiebepy" / "gui.json"

_atual: Optional[str] = None          # idioma fora do Streamlit (testes, CLI)
_faltando: set = set()                # textos pedidos sem tradução em inglês


# =============================================================================
# Persistência
# =============================================================================
def _ler_arquivo() -> Optional[str]:
    try:
        lang = json.loads(ARQUIVO.read_text(encoding="utf-8")).get("lang")
    except Exception:                                       # noqa: BLE001
        return None
    return lang if lang in IDIOMAS else None


def _gravar_arquivo(lang: str) -> None:
    try:
        ARQUIVO.parent.mkdir(parents=True, exist_ok=True)
        dados = {}
        if ARQUIVO.exists():
            try:
                dados = json.loads(ARQUIVO.read_text(encoding="utf-8"))
            except Exception:                               # noqa: BLE001
                dados = {}
        dados["lang"] = lang
        ARQUIVO.write_text(json.dumps(dados, indent=2), encoding="utf-8")
    except Exception:                                       # noqa: BLE001
        pass            # disco somente-leitura não pode impedir a troca


# =============================================================================
# Idioma corrente
# =============================================================================
def _sessao():
    """``st.session_state`` quando há execução Streamlit de verdade.

    Fora de uma execução de script (testes, CLI, chamadas do AppTest) o
    Streamlit devolve um estado "bare" que persiste no processo e guardaria
    um idioma de outra sessão; por isso exigimos o ScriptRunContext.
    """
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        if get_script_run_ctx() is None:
            return None
        import streamlit as st
        return st.session_state
    except Exception:                                       # noqa: BLE001
        return None


def idioma() -> str:
    """Idioma corrente: sessão → URL → arquivo → padrão."""
    ss = _sessao()
    if ss is not None:
        lang = ss.get(CHAVE_ESTADO)
        if lang in IDIOMAS:
            return lang
        try:
            import streamlit as st
            da_url = st.query_params.get("lang")
        except Exception:                                   # noqa: BLE001
            da_url = None
        lang = da_url if da_url in IDIOMAS else _ler_arquivo()
        lang = lang or _atual or PADRAO
        ss[CHAVE_ESTADO] = lang
        return lang
    return _atual or _ler_arquivo() or PADRAO


def definir_idioma(lang: str, gravar: bool = True) -> None:
    """Fixa o idioma (sessão Streamlit e processo)."""
    global _atual
    if lang not in IDIOMAS:
        raise ValueError(f"idioma desconhecido: {lang!r}")
    _atual = lang
    ss = _sessao()
    if ss is not None:
        ss[CHAVE_ESTADO] = lang
    if gravar:
        _gravar_arquivo(lang)


def em_ingles() -> bool:
    return idioma() == "en"


# =============================================================================
# Tradução
# =============================================================================
def t(texto: str) -> str:
    """Texto no idioma corrente (chave = texto em português)."""
    if idioma() == "pt":
        return texto
    traduzido = EN.get(texto)
    if traduzido is None:
        _faltando.add(texto)
        return texto
    return traduzido


def tf(texto: str, **campos) -> str:
    """Como :func:`t`, aplicando ``format`` — para rótulos com valores.

    ``tf("Resultado {n}-Wiebe", n=3)`` traduz o molde e só então formata, de
    modo que a tradução pode reordenar os campos.
    """
    return t(texto).format(**campos)


def faltantes() -> List[str]:
    """Textos pedidos nesta execução que não têm tradução em inglês."""
    return sorted(_faltando)


def limpar_faltantes() -> None:
    _faltando.clear()


# =============================================================================
# Seletor (Streamlit)
# =============================================================================
def seletor(key: str = "seletor_idioma") -> str:
    """Botão de idioma; devolve o idioma escolhido e força o rerun na troca."""
    import streamlit as st

    atual = idioma()
    codigos = list(IDIOMAS)
    escolha = None
    if hasattr(st, "segmented_control"):
        escolha = st.segmented_control(
            t("Idioma"), codigos, format_func=lambda c: IDIOMAS[c],
            default=atual, key=key, label_visibility="collapsed",
            help=t("Idioma da interface (o guia de ajuda tem o seu próprio botão)"))
    else:                                                   # Streamlit antigo
        escolha = st.radio(
            t("Idioma"), codigos, format_func=lambda c: IDIOMAS[c],
            index=codigos.index(atual), key=key, horizontal=True,
            label_visibility="collapsed")
    if escolha in IDIOMAS and escolha != atual:
        definir_idioma(escolha)
        st.rerun()
    return atual
