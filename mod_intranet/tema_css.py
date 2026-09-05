"""Serves the embedded CSS frameworks (Bootstrap, Bulma, DaisyUI, Pico, Picnic) locally, no CDN needed.

Serva do disco os frameworks CSS baixados em assets/css/frameworks para toda a
aplicação, com injeção por página via injetar_framework().
"""
import os

from nicegui import app, ui

_BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "css", "frameworks")

# (arquivo, descrição curta, aviso de compatibilidade)
FRAMEWORKS_CSS = {
    "bootstrap": {
        "arquivo": "bootstrap@5.3.8.min.css",
        "descricao": "Bootstrap 5.3.8 — grid `.row`/`.col`, utilitários e componentes "
                     "(`.btn`, `.card`, `.badge`, `.table`).",
        "aviso": "Reset global (box-sizing, body, headings) pode afetar o Quasar. Injeção "
                 "por página; use em telas de marca própria ou escopado. JS do Bootstrap "
                 "(dropdowns/toasts/offcanvas) não é servido — SÓ o CSS funciona.",
    },
    "bulma": {
        "arquivo": "bulma@1.0.2.min.css",
        "descricao": "Bulma 1.0.2 — utilitários/componentes flexbox (classes .columns, .box, .button).",
        "aviso": "Classe .button e resets do layout podem chocar com o Quasar. Use em páginas "
                 "com componentes próprios, não nos módulos padronizados.",
    },
    "daisyui": {
        "arquivo": "daisyui@5.6.8.min.css",
        "descricao": "DaisyUI 5.6.8 — componentes .btn/.card/.badge sobre Tailwind (precisa do "
                     "runtime do Tailwind do NiceGUI).",
        "aviso": "Depende do Tailwind v4 para utilitários de cor; o NiceGUI embute Tailwind v3 "
                 "(parcial). Classes .btn/.card/.badge podem conflitar com o Quasar. Uso por página.",
    },
    "pico": {
        "arquivo": "pico@2.min.css",
        "descricao": "Pico CSS 2 — reset + tipografia minimalista (classes .container).",
        "aviso": "É um 'reset sem classes': estiliza <body>/<h1>/<button> globais e pode quebrar o "
                 "Quasar se injeção for global. Use escopado ou em telas de marca própria.",
    },
    "picnic": {
        "arquivo": "picnic@7.1.0.min.css",
        "descricao": "Picnic CSS 7.1.0 — leve, estilo 'demo site' (classes .button, .card, .modal).",
        "aviso": "Projeto em manutenção reduzida; Sirva para páginas independentes, evite em "
                 "componentes Quasar padronizados.",
    },
}


def montar_rotas_static():
    """Makes /css/frameworks/* serve the local CSS files for the whole app.

    Registra a rota estática que serve os frameworks CSS baixados em
    assets/css/frameworks para qualquer página da aplicação (sem CDN).
    Falhas silenciosas não derrubam o boot do servidor."""
    if not os.path.isdir(_BASE):
        return
    try:
        app.add_static_files("/css/frameworks", _BASE)
    except Exception as e:
        _log().warning(f"tema_css: não foi possível montar /css/frameworks: {e}")


def caminho_css(nome=None):
    """Return HTTP URL of the CSS file (None lists the available frameworks).

    Devolve a URL HTTP do arquivo CSS de um framework cadastrado, ou a lista de
    frameworks disponíveis quando `nome` é None (ou None para nome desconhecido)."""
    try:
        if not nome:
            return sorted(FRAMEWORKS_CSS)
        dados = FRAMEWORKS_CSS.get(nome)
        return f"/css/frameworks/{dados['arquivo']}" if dados else None
    except Exception as e:
        _log().exception(f"tema_css:caminho_css falha ao resolver {nome}: {e}")
        return None


def injetar_framework(nome):
    """Adds the framework <link> to the current page <head> (per-page usage).

    Adiciona o <link> do framework ao <head> da página atual. Importante: os
    frameworks têm resets/classes próprios que podem conflitar com o Quasar do
    NiceGUI — a injeção é POR PÁGINA, nunca global. Retorna True/False."""
    try:
        url = caminho_css(nome)
        if not url:
            return False
        ui.add_head_html(f'<link rel="stylesheet" href="{url}">')
        return True
    except Exception as e:
        _log().exception(f"tema_css:injetar_framework falha ao injetar {nome}: {e}")
        return False


def _log():
    from mod_intranet import observabilidade
    return observabilidade.get_logger("intranet")