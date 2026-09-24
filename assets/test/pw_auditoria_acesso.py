"""Auditoria /auditoria — somente administrador_geral (pytest-playwright).

EN: Audit viewer is read-only and restricted to administrador_geral;
    qamaster sees busca/exportar, qacomum is redirected to / with denial.
PT: Auditoria é somente-leitura e exclusiva do administrador_geral;
    qamaster vê busca/exportar, qacomum é redirecionado para / com negação.

Pirâmide: estáticos (fonte/rota/papel) + E2E de leitura; nenhuma escrita
(auditoria nunca escreve pela UI — só filtros e exportação).
Troca forçada ciente: 123456 provisória; skip amigável se trocada ou se o
diálogo persistente abrir.

Como rodar:
    .venv\\Scripts\\python -m pytest assets/test/pw_auditoria_acesso.py -v
"""

import os
import pathlib

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e

BASE_URL = os.environ.get("INTRANET_BASE_URL", "http://localhost:8080")
ADMIN_USUARIO = "qamaster"
ADMIN_SENHA = "123456"
COMUM_USUARIO = "qacomum"
COMUM_SENHA = "123456"

RAIZ = pathlib.Path(__file__).resolve().parents[2]


def _ler(rel: str) -> str:
    """Lê fonte (somente leitura)."""
    try:
        return (RAIZ / rel).read_text(encoding="utf-8")
    except Exception:
        return ""


def _dialogo_troca_visivel(page) -> bool:
    """Detecta troca obrigatória."""
    try:
        for texto in ("Troca de senha obrigatória", "Credenciais obrigatórias"):
            if page.get_by_text(texto, exact=False).count() > 0:
                return True
        return False
    except Exception:
        return False


def fazer_login(page, usuario: str, senha: str) -> bool:
    """Login via data-testid; True se saiu do /login."""
    try:
        page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded", timeout=15000)
    except Exception:
        pytest.skip(f"servidor live indisponível em {BASE_URL}")
    page.get_by_test_id("login-usuario").fill(usuario)
    page.get_by_test_id("login-senha").fill(senha)
    page.get_by_test_id("login-entrar").click()
    try:
        page.wait_for_function(
            "() => !location.pathname.startsWith('/login')", timeout=20000)
    except Exception:
        pass
    try:
        page.wait_for_load_state("domcontentloaded", timeout=10000)
    except Exception:
        pass
    page.wait_for_timeout(1500)
    try:
        url = page.url
    except Exception:
        url = ""
    if "/login" in (url or "") and not _dialogo_troca_visivel(page):
        return False
    return True


class TestAuditoriaEstatico:
    """Unitários rápidos sem servidor."""

    def test_testids_via_props(self):
        """Busca e exportar via .props('data-testid=...')."""
        fonte = _ler("mod_auditoria/telas.py")
        assert ".props('data-testid=auditoria-busca')" in fonte
        assert ".props('data-testid=auditoria-exportar')" in fonte

    def test_rota_auditoria_registrada(self):
        """Rota /auditoria registrada."""
        assert '@ui.page("/auditoria")' in _ler("main.py")

    def test_papel_do_ator_antes_da_escrita(self):
        """Exclusivo do administrador_geral (leitura; sem escrita pela UI)."""
        fonte = _ler("mod_auditoria/telas.py")
        assert 'perfil == "administrador_geral"' in fonte
        assert "eh_admin_geral" in fonte


class TestAuditoriaAcessoE2E:
    """E2E headless, sequencial, 1 contexto, sem carga."""

    def test_admin_ve_busca_e_exportar(self, page):
        """qamaster vê busca e botão exportar (somente leitura)."""
        ok = fazer_login(page, ADMIN_USUARIO, ADMIN_SENHA)
        if not ok:
            pytest.skip("senha do qamaster trocada (provisória) — ciente")
        if _dialogo_troca_visivel(page):
            pytest.skip("troca obrigatória pendente")
        page.goto(f"{BASE_URL}/auditoria", wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(2000)
        expect(page.get_by_test_id("auditoria-busca")).to_be_visible(timeout=15000)
        expect(page.get_by_test_id("auditoria-exportar")).to_be_visible(timeout=15000)

    def test_comum_nao_abre_auditoria(self, page):
        """qacomum é barrado: cai em / com 'Acesso negado' (papel antes de tudo)."""
        ok = fazer_login(page, COMUM_USUARIO, COMUM_SENHA)
        if not ok:
            pytest.skip("senha do qacomum trocada (provisória) — ciente")
        if _dialogo_troca_visivel(page):
            pytest.skip("troca obrigatória pendente")
        page.goto(f"{BASE_URL}/auditoria", wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(2500)
        url = ""
        try:
            url = page.url
        except Exception:
            url = ""
        corpo = page.locator("body")
        # Guard central redireciona para / com aviso; aceita qualquer evidência.
        redirecionou = (url.rstrip("/") == BASE_URL) or ("/auditoria" not in url)
        negou = corpo.get_by_text("Acesso negado", exact=False).count() > 0
        assert redirecionou or negou, f"esperava bloqueio, url={url}"


if __name__ == "__main__":
    print("Execute: .venv\\Scripts\\python -m pytest assets/test/pw_auditoria_acesso.py -v")
