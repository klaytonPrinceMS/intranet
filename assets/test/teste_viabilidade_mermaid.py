"""Teste de viabilidade: ui.mermaid no NiceGUI 3.15 (renderização em navegador).

Script standalone (NÃO pytest). Sobe o app NiceGUI numa porta livre, monta uma
página com `ui.mermaid` (diagrama flowchart e diagrama de caso de uso) e usa o
Playwright (driver do Python) para confirmar que o componente renderiza um SVG
de verdade no navegador — sem CDN, via bundle embutido do NiceGUI. Também
exercita o caminho real do módulo Blog: uma postagem com bloco ```mermaid
renderizada via `_renderizar_conteudo_postagem`.

Execute: .venv/bin/python test/teste_viabilidade_mermaid.py
"""
import os
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))))

from nicegui import ui, app  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

PORT = 8099

flowchart = """flowchart LR
    A[Início] --> B{Sessão válida?}
    B -- Sim --> C[Painel]
    B -- Nao --> D[Login]
"""

caso_uso = """flowchart LR
    Actor[Usuario] -->|publica| Blog
    Actor -->|le| Blog
    Actor -->|comenta| Blog
"""


@ui.page("/")
def montar_pagina():
    with ui.row().classes("w-full gap-4"):
        with ui.column().classes("w-full"):
            ui.label("Diagrama flowchart").classes("text-h6")
            ui.mermaid(flowchart)
        with ui.column().classes("w-full"):
            ui.label("Diagrama caso de uso").classes("text-h6")
            ui.mermaid(caso_uso)

    # Caminho real do Blog: postagem com bloco mermaid
    from mod_blog.bd_manipulador import _sanitizar_texto
    from mod_blog.telas import _renderizar_conteudo_postagem
    conteudo = _sanitizar_texto(
        "Texto do post.\n\n"
        "```mermaid\nflowchart TD\n    A[Pedido] --> B{Aprovado?}\n"
        "    B -- Sim --> C[Imprimir]\n    B -- Nao --> D[Devolver]\n```\n\n"
        "Fim do post.")
    with ui.card().classes("w-full"):
        ui.label("Postagem do Blog (mermaid)").classes("text-h6")
        with ui.column().classes("w-full"):
            _renderizar_conteudo_postagem(conteudo)


def main():
    ui.run(
        port=PORT,
        host="127.0.0.1",
        show=False,
        reload=False,
        title="Mermaid Viabilidade",
        favicon=None,
    )


def iniciar_servidor():
    t = threading.Thread(target=main, daemon=True)
    t.start()
    time.sleep(6)


if __name__ == "__main__":
    print("INICIANDO — viabilidade do ui.mermaid (NiceGUI 3.15)")
    iniciar_servidor()
    _cont = {"ok": 0, "total": 0}

    def check(cond, msg):
        _cont["total"] += 1
        if cond:
            _cont["ok"] += 1
        print(("  OK " if cond else "  FALHOU ") + msg)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(f"http://127.0.0.1:{PORT}/", wait_until="networkidle")
            page.wait_for_timeout(2500)

            svgs = page.locator("svg")
            n_svg = svgs.count()
            print(f"SVGs encontrados: {n_svg}")
            check(n_svg >= 2, "ui.mermaid renderizou 2+ diagramas (SVG)")

            # título dos diagramas
            check(page.get_by_text("Diagrama flowchart").count() > 0,
                  "labels dos diagramas presentes")

            # caminho real do blog: postagem com mermaid
            check(page.get_by_text("Postagem do Blog (mermaid)").count() > 0,
                  "postagem do blog presente")
            svgs_blog = page.locator("svg").count()
            check(svgs_blog >= 3,
                  f"renderizou diagrama do blog (total {svgs_blog} SVGs)")
            # texto puro do post preservado ao redor do diagrama
            check(page.get_by_text("Texto do post.").count() > 0
                  and page.get_by_text("Fim do post.").count() > 0,
                  "texto ao redor do diagrama preservado")

            browser.close()
    except Exception as e:
        _cont["total"] += 1
        print(f"  FALHOU exceção ao renderizar: {e}")

    print(f"\nRESULTADO: {_cont['ok']}/{_cont['total']} verificações OK")
    sys.exit(0 if _cont["ok"] == _cont["total"] and _cont["ok"] > 0 else 1)