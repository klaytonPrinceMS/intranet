"""Documentação MkDocs embutida: build estático + montagem em /documentacao."""
import os
import subprocess
import sys

from nicegui import app
from starlette.staticfiles import StaticFiles

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE_DIR = os.path.join(BASE_DIR, "site")
ROTA = "/documentacao"

_montado = False


def _build() -> tuple:
    """Gera site/ com o mkdocs do próprio venv. Retorna (ok, erro_curto)."""
    try:
        r = subprocess.run(
            [sys.executable, "-m", "mkdocs", "build"],
            cwd=BASE_DIR, capture_output=True, text=True, timeout=60,
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


def construir_e_montar_documentacao(logar=True) -> bool:
    """Build + mount. Falha NUNCA derruba o servidor — só avisa."""
    ok, erro = _build()
    if not ok:
        if logar:
            print(f"[documentacao] FALHA no mkdocs build: {erro}")
        return False
    if montar():
        if logar:
            print("[documentacao] OK: servindo em /documentacao")
        return True
    if logar:
        print("[documentacao] build OK, mas nao foi possivel montar a rota agora")
    return False


def reconstruir() -> tuple:
    """Para o botão de Configurações: rebuild + garante rota. (ok, mensagem)."""
    ok, erro = _build()
    if not ok:
        return False, f"Falha no build da documentação: {erro}"
    if montar():
        return True, "Documentação reconstruída — disponível em /documentacao"
    return True, ("Arquivos regenerados. A rota /documentacao será montada "
                  "no próximo reinício do servidor.")
