"""Embedded MkDocs documentation: static build + serving.

Documentação MkDocs embutida: build estático + servir. A documentação é
servida na PORTA DO MKDOCS (padrão 8000), separada da porta do site (8080)."""
import os
import subprocess
import sys
import threading

from nicegui import app
from starlette.staticfiles import StaticFiles

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE_DIR = os.path.join(BASE_DIR, "site")
ROTA = "/documentacao"
PORTA_PADRAO = 8001

_montado = False
_servidor = None
_porta_atual = None


def _build() -> tuple:
    """Gera site/ com o mkdocs do próprio venv. Retorna (ok, erro_curto)."""
    try:
        r = subprocess.run(
            [sys.executable, "-m", "mkdocs", "build"],
            cwd=BASE_DIR, capture_output=True, text=True,             timeout=120,
        )
        ok = r.returncode == 0 and os.path.exists(os.path.join(SITE_DIR, "index.html"))
        return ok, "" if ok else ((r.stderr or r.stdout or "mkdocs falhou")[-400:])
    except Exception as e:
        return False, str(e)


def montar() -> bool:
    """Serve site/ como rota estática (idempotente; arquivos novos valem sem remount)."""
    global _montado
    if _montado:
        return True
    if not os.path.exists(os.path.join(SITE_DIR, "index.html")):
        return False
    try:
        app.mount(ROTA, StaticFiles(directory=SITE_DIR, html=True), name="documentacao")
        _montado = True
        return True
    except Exception:
        return False


def iniciar_servidor(porta=PORTA_PADRAO) -> bool:
    """Serves site/ on the mkdocs port in a background thread (daemon).

    Serve a documentação gerada na PORTA DO MKDOCS (padrão 8001), separada
    da porta do site (8080). Idempotente: a primeira chamada inicia; as
    seguintes apenas confirmam. Falha NUNCA derruba o servidor. Se a porta
    pedida estiver ocupada (ex.: 8000 do snap), tenta as próximas 5."""
    global _servidor, _porta_atual
    if _servidor is not None:
        return True
    if not os.path.exists(os.path.join(SITE_DIR, "index.html")):
        return False
    # tenta a porta pedida e as próximas 5 se estiver ocupada
    for tentativa in range(6):
        try:
            from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

            class _Handler(SimpleHTTPRequestHandler):
                def __init__(self, *args, **kwargs):
                    super().__init__(*args, directory=SITE_DIR, **kwargs)

                def log_message(self, *args):  # silencia o log padrão por request
                    pass

            p = int((porta or PORTA_PADRAO) + tentativa) if tentativa else int(porta or PORTA_PADRAO)
            _servidor = ThreadingHTTPServer(("0.0.0.0", p), _Handler)
            _porta_atual = p
            threading.Thread(target=_servidor.serve_forever, daemon=True).start()
            if tentativa:
                print(f"[documentacao] porta {porta} em uso, usando {p}")
            print(f"[documentacao] OK: servindo em http://localhost:{p}")
            return True
        except Exception as e:
            if tentativa == 0:
                print(f"[documentacao] aviso: não foi possível servir na porta "
                      f"{porta}: {e}")
            _servidor = None
            continue
    return False


def porta_documentacao():
    """Returns the port where the documentation server is running (or default)."""
    return _porta_atual or PORTA_PADRAO


def construir_e_montar_documentacao(logar=True, porta=None) -> bool:
    """Build + mount + start the docs server. Falha NUNCA derruba o servidor.

    Gera o site/, monta a rota inline (compatibilidade) e inicia o servidor
    na porta da documentação (mkdocs, padrão 8000)."""
    ok, erro = _build()
    if not ok:
        if logar:
            print(f"[documentacao] FALHA no mkdocs build: {erro}")
        return False
    ok_serve = iniciar_servidor(porta or PORTA_PADRAO)
    if montar():
        if logar:
            if ok_serve:
                print(f"[documentacao] OK: servindo em http://localhost:{porta_documentacao()}")
            else:
                print(f"[documentacao] montado em /documentacao (porta {porta} ocupada, docs via rota interna)")
    elif logar:
        print("[documentacao] build OK, mas nao foi possivel montar a rota agora")
    return True


def reconstruir() -> tuple:
    """Para o botão de Configurações: rebuild + garante rota. (ok, mensagem)."""
    ok, erro = _build()
    if not ok:
        return False, f"Falha no build da documentação: {erro}"
    iniciar_servidor(porta_documentacao())
    if montar():
        return True, (f"Documentação reconstruída — disponível em "
                      f"http://localhost:{porta_documentacao()}")
    return True, ("Arquivos regenerados. A documentação será servida em "
                  f"http://localhost:{porta_documentacao()}")
