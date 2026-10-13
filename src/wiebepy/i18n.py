# -*- coding: utf-8 -*-
"""
i18n.py — Idioma do que o wiebepy mostra: interface gráfica e
relatórios HTML (português e inglês).

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

import contextlib
import json
import threading
from pathlib import Path
from typing import Dict, Iterator, List, Optional

from .lang_en import EN

IDIOMAS: Dict[str, str] = {"pt": "Português", "en": "English"}
PADRAO = "pt"
CHAVE_ESTADO = "gui_lang"
ARQUIVO = Path.home() / ".wiebepy" / "gui.json"

_atual: Optional[str] = None          # idioma fora do Streamlit (testes, CLI)
_faltando: set = set()                # textos pedidos sem tradução em inglês
_local = threading.local()            # idioma fixado por bloco (relatórios)


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
        if get_script_run_ctx(suppress_warning=True) is None:
            return None     # fora de uma execução de script: sem aviso
        import streamlit as st
        return st.session_state
    except Exception:                                       # noqa: BLE001
        return None


def idioma() -> str:
    """Idioma corrente: bloco fixado → sessão → URL → arquivo → padrão."""
    forcado = getattr(_local, "lang", None)
    if forcado in IDIOMAS:
        return forcado
    ss = _sessao()
    if ss is not None:
        lang = ss.get(CHAVE_ESTADO)
        if lang in IDIOMAS:
            _lembrar(lang)          # threads de fundo (relatórios) herdam
            return lang
        try:
            import streamlit as st
            da_url = st.query_params.get("lang")
        except Exception:                                   # noqa: BLE001
            da_url = None
        lang = da_url if da_url in IDIOMAS else _ler_arquivo()
        lang = lang or _atual or PADRAO
        ss[CHAVE_ESTADO] = lang
        _lembrar(lang)
        return lang
    return _atual or _ler_arquivo() or PADRAO


def _lembrar(lang: str) -> None:
    """Guarda o idioma da sessão no processo.

    A GUI gera relatório numa thread de fundo, onde não há sessão
    Streamlit; sem isto o relatório sairia no idioma do arquivo (ou no
    padrão) em vez do que está na tela.
    """
    global _atual
    _atual = lang


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


@contextlib.contextmanager
def idioma_fixo(lang: Optional[str]) -> Iterator[str]:
    """Fixa o idioma dentro do bloco, sem gravar a escolha.

    É como os relatórios recebem ``lang=``: ``lang=None`` mantém o idioma
    corrente (o da interface, quando gerados por ela). O valor é
    thread-local porque a GUI gera relatório numa thread de fundo enquanto
    a tela continua desenhando na principal.
    """
    if lang is not None and lang not in IDIOMAS:
        raise ValueError(f"idioma desconhecido: {lang!r}")
    anterior = getattr(_local, "lang", None)
    if lang is not None:
        _local.lang = lang
    try:
        yield idioma()
    finally:
        _local.lang = anterior


def consumir_lang(args: List[str]) -> List[str]:
    """Tira ``--lang pt|en`` da linha de comando e fixa o idioma.

    A escolha vale só para esta execução (não grava o arquivo), e alcança
    tudo que a execução imprimir ou gerar — inclusive os relatórios HTML.
    """
    saida, i = [], 0
    while i < len(args):
        a = args[i]
        if a == "--lang" and i + 1 < len(args):
            definir_idioma(args[i + 1], gravar=False)
            i += 2
            continue
        if a.startswith("--lang="):
            definir_idioma(a.split("=", 1)[1], gravar=False)
            i += 1
            continue
        saida.append(a)
        i += 1
    return saida


def em_ingles() -> bool:
    return idioma() == "en"


# =============================================================================
# Tradução
# =============================================================================
class Texto(str):
    """``str`` que JÁ passou pela tradução.

    Os relatórios montam tabelas em que a coluna de rótulos mistura texto
    literal e rótulo já formatado por :func:`tf`; a marca evita traduzir
    duas vezes (o que, em inglês, procuraria a tradução de uma frase
    inglesa e a contaria como pendente).
    """

    __slots__ = ()


def t(texto: str, registrar: bool = True) -> str:
    """Texto no idioma corrente (chave = texto em português)."""
    if isinstance(texto, Texto) or idioma() == "pt":
        return texto
    traduzido = EN.get(texto)
    if traduzido is None:
        if registrar:
            _faltando.add(texto)
        return Texto(texto)
    return Texto(traduzido)


def ts(texto) -> str:
    """Tradução branda, para células de tabela que podem ser DADOS.

    Nos relatórios a mesma coluna mistura rótulo e valor (um caminho de
    arquivo, "DOP853", o nome do combustível). Traduz quando existe
    entrada e devolve o original sem registrar falta quando não existe —
    senão todo dado do caso entraria na lista de pendências.
    """
    if isinstance(texto, str):
        return t(texto, registrar=False)
    if isinstance(texto, dict):          # células que mostram um dict inteiro
        return {k: ts(v) for k, v in texto.items()}   # (ex. "modelo de gás")
    if isinstance(texto, (list, tuple)):
        return type(texto)(ts(v) for v in texto)
    return texto


def rotulo(v):
    """Tradução de uma CÉLULA DE RÓTULO de relatório.

    Traduz (registrando falta) só o que ainda não passou pela tradução e é
    texto; números e valores já traduzidos passam intactos.
    """
    if isinstance(v, Texto) or not isinstance(v, str):
        return v
    return t(v)


def tf(texto: str, **campos) -> str:
    """Como :func:`t`, aplicando ``format`` — para rótulos com valores.

    ``tf("Resultado {n}-Wiebe", n=3)`` traduz o molde e só então formata, de
    modo que a tradução pode reordenar os campos.
    """
    return Texto(t(texto).format(**campos))


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
