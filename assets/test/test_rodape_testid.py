"""Teste de integração headless do rodapé padrão (ui_comum) — delta a1b1650.

Cobre o que verifica_ui_comum.py (stub estático) não cobre com a UI real:
`rodape_salvar_restaurar` devolve (restaurar, aplicar), aplica
`data-testid` no Aplicar, omite o Restaurar quando não-callable, ignora
ação extra malformada (fail-soft) e dispara handlers sync e async
(`clicar()` aguarda awaitable — padrão teste_aba_config_intranet.py).
Inclui guardas de regressão na fonte de tela_configuracoes.py (ids
config-aplicar-*, Banco sem reload, docs/SMTP via io_bound).

Somente LEITURA de banco (ler_tema); não altera tb_config.

Execute: .venv/bin/python assets/test/test_rodape_testid.py
"""
import asyncio
import inspect
import os
import sys
from collections import deque

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))))

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


print("INICIANDO TESTES — rodape_salvar_restaurar + data-testid (headless)")

from nicegui import ui  # noqa: E402
from nicegui.client import Client  # noqa: E402
from nicegui.elements.button import Button  # noqa: E402
from mod_intranet import ui_comum  # noqa: E402


def _varrer():
    cli = list(Client.instances.values())[0]
    els = []
    fila = deque([cli.layout])
    while fila:
        e = fila.popleft()
        els.append(e)
        fila.extend(list(e))
    return els


def _botoes_testid(valor):
    return [e for e in _varrer()
            if isinstance(e, Button)
            and e._props.get("data-testid") == valor]


async def clicar(botao_el):
    import inspect as _inspect
    for lst in list(botao_el._event_listeners.values()):
        if lst.type == "click" and lst.handler:
            ret = lst.handler(None)
            if _inspect.isawaitable(ret):
                await ret


async def main():
    # Headless não há ui.run: sem loop do NiceGUI, handlers async seriam
    # adiados para o startup (create_or_defer) e nunca executariam. Apontar
    # core.loop para o loop corrente reproduz o ambiente de produção e
    # exercita o caminho async real (padrão AGENTS §5.1).
    from nicegui import core as _core
    _core.loop = asyncio.get_running_loop()

    chamadas = {"salvar": 0, "restaurar": 0, "async": 0}

    def _salvar():
        chamadas["salvar"] += 1

    def _restaurar():
        chamadas["restaurar"] += 1

    async def _salvar_async():
        chamadas["async"] += 1

    # ---------- tupla + data-testid ----------
    ret = ui_comum.rodape_salvar_restaurar(
        _salvar, _restaurar, chave_modulo="blog",
        data_testid="config-aplicar-probe-qa")
    check(isinstance(ret, tuple) and len(ret) == 2,
          "rodape_salvar_restaurar devolve (restaurar, aplicar)")
    btn_rest, btn_aplic = ret
    check(isinstance(btn_rest, Button) and isinstance(btn_aplic, Button),
          "tupla contém os dois Buttons")
    check(btn_rest.text == "Restaurar padrão" and btn_aplic.text == "Aplicar",
          "rótulos padrão (Restaurar padrão + Aplicar)")
    achados = _botoes_testid("config-aplicar-probe-qa")
    check(len(achados) == 1 and achados[0] is btn_aplic,
          "data-testid aplicado exatamente no botão Aplicar")

    # ---------- sem restaurar ----------
    ret2 = ui_comum.rodape_salvar_restaurar(
        _salvar, None, chave_modulo="blog",
        data_testid="config-aplicar-probe-sem-rest")
    check(ret2[0] is None and isinstance(ret2[1], Button),
          "restaurar=None devolve (None, aplicar) sem quebrar")

    # ---------- sem data_testid (compatível com chamadas legadas) ----------
    ret3 = ui_comum.rodape_salvar_restaurar(_salvar, _restaurar,
                                            chave_modulo="blog")
    check(ret3[1]._props.get("data-testid") is None,
          "sem data_testid não injeta prop (saída legada preservada)")

    # ---------- ação extra malformada é ignorada ----------
    try:
        ui_comum.rodape_salvar_restaurar(
            _salvar, _restaurar, chave_modulo="blog",
            acoes_extra=[("só-rotulo",)],
            data_testid="config-aplicar-probe-extra")
        check(True, "ação extra malformada ignorada sem derrubar o rodapé")
    except Exception:
        check(False, "ação extra malformada ignorada sem derrubar o rodapé")
    check(len(_botoes_testid("config-aplicar-probe-extra")) == 1,
          "rodapé com extra inválida ainda renderiza o Aplicar")

    # ---------- clique dispara handlers (sync + async) ----------
    await clicar(btn_aplic)
    check(chamadas["salvar"] == 1,
          "clique no Aplicar executa o handler de salvar")
    await clicar(btn_rest)
    check(chamadas["restaurar"] == 1,
          "clique no Restaurar executa o handler de restaurar")
    ui_comum.rodape_salvar_restaurar(
        _salvar_async, None, chave_modulo="blog",
        data_testid="config-aplicar-probe-async")
    await clicar(_botoes_testid("config-aplicar-probe-async")[0])
    await asyncio.sleep(0.5)  # background task do handler async
    check(chamadas["async"] == 1,
          "handler async do Aplicar executa até o fim (caminho io_bound)")

    # ---------- fábrica central ----------
    b = ui_comum.botao("Ir", variante="primario", chave_modulo="blog")
    check(isinstance(b, Button) and b.text == "Ir",
          "ui_comum.botao cria Button via fábrica central")
    bi = ui_comum.botao_icone("edit", on_click=lambda: None)
    check(bi is not None, "ui_comum.botao_icone cria botão de ícone")
    from mod_intranet.ui_comum import Dialogo
    from nicegui.elements.dialog import Dialog as _Dlg
    from nicegui.elements.card import Card as _Card
    pendente = Dialogo("Título QA", chave_modulo="blog")
    try:
        pendente.abrir()
        pendente.fechar()
        check(True, "Dialogo abrir/fechar antes do contexto é no-op seguro")
    except Exception:
        check(False, "Dialogo abrir/fechar antes do contexto é no-op seguro")
    try:
        with Dialogo("Título QA", chave_modulo="blog") as (dlg, card):
            check(isinstance(dlg, _Dlg) and isinstance(card, _Card),
                  "Dialogo como context manager entrega (Dialog, Card)")
    except Exception:
        check(False, "Dialogo como context manager entrega (Dialog, Card)")

    # ---------- guardas de regressão (fonte tela_configuracoes, a1b1650) ----------
    import mod_intranet.tela_configuracoes as tc
    fonte = inspect.getsource(tc)
    for tid in ("config-aplicar-banco", "config-aplicar-smtp",
                "config-reconstruir-docs", "config-aplicar-paginas"):
        check(f"data_testid=\"{tid}\"" in fonte or f"data-testid={tid}" in fonte,
              f"tela_configuracoes expõe {tid}")
    check("_aplicar_card_sem_reload" in fonte,
          "card Banco aplica sem reload (exige restart)")
    check("io_bound" in fonte,
          "operações pesadas (docs/SMTP/backup) via run.io_bound")

asyncio.run(main())

print(f"RESULTADO: {_OK} OK, {_TOTAL - _OK} falha(s) de {_TOTAL} verificações")
sys.exit(0 if _OK == _TOTAL else 1)
