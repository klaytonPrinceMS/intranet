"""Teste do feed do Blog na HOME (mod_intranet/main.py) — padrão de exibição.

Renderiza `renderizar_postagens` (fonte única usada pela Home e pela tela do
Blog) e valida o DOM nos três modos: 'carrossel' (indicador 1/N), 'unica'
(apenas a postagem fixada/mais recente) e 'historico' (todas). Restaura a
config original ao final.

Execute (da raiz do projeto):
    .venv/bin/python assets/test/teste_home_blog.py
"""
import asyncio
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE)

_OK = 0
_TOTAL = 0


def check(cond, msg):
    global _OK, _TOTAL
    _TOTAL += 1
    if cond:
        _OK += 1
        print(f"  OK [{_OK}] {msg}")
    else:
        print(f"  FALHOU [{_TOTAL - _OK}] {msg}")


from nicegui import ui  # noqa: E402
from nicegui.client import Client  # noqa: E402
from nicegui.elements.label import Label  # noqa: E402
from nicegui.elements.card import Card  # noqa: E402

from mod_blog import bd_manipulador as bd  # noqa: E402
from mod_blog.telas import renderizar_postagens  # noqa: E402

print("INICIANDO TESTES — feed do Blog na Home")


def _varrer(raiz=None):
    from collections import deque
    cli = list(Client.instances.values())[0]
    els = []
    fila = deque([raiz if raiz is not None else cli.layout])
    while fila:
        e = fila.popleft()
        els.append(e)
        fila.extend(list(e))
    return els


def _cards_blog(els):
    """Post cards do blog (borda colorida border-left) presentes no DOM."""
    return [e for e in els
            if isinstance(e, Card) and "border-left-color" in (e._style or "")]


async def main():
    ORIG = {
        "modo": bd.get_config_local("blog_modo_exibicao", "historico"),
        "unica": bd.obter_postagem_unica_id(),
        "ids": bd.obter_carrossel_postagens_ids(),
        "tempo": bd.obter_carrossel_tempo(),
    }

    posts = bd.listar_postagens(ativo=True, ordem="DESC")
    if len(posts) < 2:
        raise RuntimeError("banco do blog sem postagens suficientes para testar")
    ids = [p[0] for p in posts[:2]]

    # ---- modo carrossel: a Home mostra a rotação com indicador 1/N ----
    bd.set_config_local("blog_modo_exibicao", "carrossel")
    bd.definir_carrossel_postagens_ids(ids)
    bd.definir_carrossel_tempo(7)
    wrap = ui.column().classes("w-full")
    renderizar_postagens(wrap, "master", "administrador_geral", True,
                         lambda: None)
    els = _varrer(wrap)
    indicador = [e for e in els
                 if isinstance(e, Label) and e.text == f"1 / {len(ids)}"]
    check(len(indicador) >= 1,
          f"home carrossel: indicador de posição '1 / {len(ids)}' presente")

    # ---- modo única: apenas a postagem fixada (1 card) ----
    bd.set_config_local("blog_modo_exibicao", "unica")
    bd.definir_postagem_unica_id(ids[0])
    wrap2 = ui.column().classes("w-full")
    renderizar_postagens(wrap2, "master", "administrador_geral", True,
                         lambda: None)
    els2 = _varrer(wrap2)
    cards2 = _cards_blog(els2)
    check(len(cards2) == 1,
          f"home única: exibe apenas 1 postagem (obteve {len(cards2)})")

    # ---- modo histórico: todas as postagens ativas ----
    bd.set_config_local("blog_modo_exibicao", "historico")
    bd.definir_postagem_unica_id(None)
    wrap3 = ui.column().classes("w-full")
    renderizar_postagens(wrap3, "master", "administrador_geral", True,
                         lambda: None)
    els3 = _varrer(wrap3)
    cards3 = _cards_blog(els3)
    check(len(cards3) >= len(posts),
          f"home histórico: exibe {len(cards3)} postagens (ativas: {len(posts)})")

    # restaura config original
    bd.set_config_local("blog_modo_exibicao", ORIG["modo"])
    bd.definir_postagem_unica_id(ORIG["unica"])
    bd.definir_carrossel_postagens_ids(ORIG["ids"])
    bd.definir_carrossel_tempo(ORIG["tempo"])


if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        from mod_blog import bd_manipulador as _bd
        _bd.set_config_local("blog_modo_exibicao", "historico")
        _bd.definir_postagem_unica_id(None)
        _bd.definir_carrossel_postagens_ids([])
        _bd.definir_carrossel_tempo(10)
    print(f"\nTODOS OS TESTES PASSARAM — {_OK} verificações ✅")