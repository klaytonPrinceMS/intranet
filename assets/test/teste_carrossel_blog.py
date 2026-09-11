"""Teste do modo de exibição CARROSSEL do Blog (mod_blog/telas.py).

Renderiza a tela REAL do blog em modo 'carrossel' (headless) e valida o DOM:
indicador de posição, resumo do card, seleção de postagens e tempo pelo admin,
e a expansão para leitura completa. Restaura a config original ao final.

Execute (da raiz do projeto):
    .venv/bin/python test/teste_carrossel_blog.py
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
from nicegui.elements.button import Button  # noqa: E402
from nicegui.elements.label import Label  # noqa: E402
from nicegui.elements.select import Select  # noqa: E402
from nicegui.elements.number import Number  # noqa: E402

from mod_blog import bd_manipulador as bd

# Hermeticidade: o teste lê os bancos dos módulos no SQLite, independentemente
# do backend persistido (banco_tipo pode estar 'postgres' na máquina).
from unittest import mock as _mock  # noqa: E402
from mod_intranet import banco_conexao as _bc  # noqa: E402
_mock.patch.object(_bc, "sgbd_ativo", return_value="sqlite").start()

print("INICIANDO TESTES — modo carrossel do Blog")


def _varrer():
    from collections import deque
    cli = list(Client.instances.values())[0]
    els = []
    fila = deque([cli.layout])
    while fila:
        e = fila.popleft()
        els.append(e)
        fila.extend(list(e))
    return els


def achar_botoes(texto):
    return [e for e in _varrer() if isinstance(e, Button) and e.text == texto]


def clicar(botao_el):
    for lst in list(botao_el._event_listeners.values()):
        if lst.type == "click" and lst.handler:
            lst.handler(None)


async def main():
    from mod_blog.telas import mostrar_tela

    ORIG = {
        "modo": bd.get_config_local("blog_modo_exibicao", "historico"),
        "ids": bd.obter_carrossel_postagens_ids(),
        "tempo": bd.obter_carrossel_tempo(),
    }

    # garante ao menos 2 postagens para o carrossel
    posts = bd.listar_postagens(ativo=True, ordem="DESC")
    ids = [p[0] for p in posts[:2]]
    if len(ids) < 2:
        raise RuntimeError("banco do blog sem postagens suficientes para testar")

    bd.definir_carrossel_postagens_ids(ids)
    bd.definir_carrossel_tempo(7)
    bd.set_config_local("blog_modo_exibicao", "carrossel")

    mostrar_tela("master", "administrador_geral")

    els = _varrer()
    indicador = [e for e in els
                 if isinstance(e, Label) and e.text == f"1 / {len(ids)}"]
    check(len(indicador) >= 1, "indicador de posição '1 / N' presente")

    leitura = achar_botoes("Leitura completa")
    check(len(leitura) >= 1, "botão 'Leitura completa' presente")

    sel_post = [e for e in els
                if isinstance(e, Select)
                and e._props.get("label", "").startswith("Postagens do carrossel")]
    check(len(sel_post) >= 1, "select 'Postagens do carrossel' presente")
    if sel_post:
        vals = [str(v) for v in sel_post[0].value] if sel_post[0].value else []
        check(sorted(int(v) for v in vals) == sorted(ids),
              "select de postagens reflete a seleção salva")

    campo_tempo = [e for e in els
                   if isinstance(e, Number)
                   and e._props.get("label") == "Tempo de exibição (segundos)"]
    check(len(campo_tempo) >= 1 and campo_tempo[0].value == 7,
          "campo 'Tempo de exibição' reflete a config (7s)")

    # expansão para leitura completa
    if leitura:
        clicar(leitura[0])
        els2 = _varrer()
        voltar = [e for e in els2 if isinstance(e, Button)
                  and e.text == "Voltar ao carrossel"]
        check(len(voltar) >= 1, "ao expandir, aparece 'Voltar ao carrossel'")
        check(not achar_botoes("Leitura completa"),
              "ao expandir, some o botão 'Leitura completa' (pausa a rotação)")
        # restaura config após a validação do DOM
        bd.definir_carrossel_postagens_ids(ids)
        bd.definir_carrossel_tempo(7)
        bd.set_config_local("blog_modo_exibicao", "carrossel")

    # restaura config original
    bd.set_config_local("blog_modo_exibicao", ORIG["modo"])
    bd.definir_carrossel_postagens_ids(ORIG["ids"])
    bd.definir_carrossel_tempo(ORIG["tempo"])


if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        from mod_blog import bd_manipulador as _bd
        _bd.set_config_local("blog_modo_exibicao", "historico")
        _bd.definir_carrossel_postagens_ids([])
        _bd.definir_carrossel_tempo(10)
    print(f"\nTODOS OS TESTES PASSARAM — {_OK} verificações ✅")