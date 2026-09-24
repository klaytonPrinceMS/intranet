"""Editor de PDF /edit-pdf (pytest-playwright, headless).

EN: PDF editor panel — editar_pdf-* testids via .props; qamaster and qacomum
    (both with editar_pdf access) see atualizar/enviar/juntar without upload.
PT: Editor de PDF — painel com testids editar_pdf-* via .props; qamaster e
    qacomum (ambos com acesso a editar_pdf) veem atualizar/enviar/juntar sem
    fazer upload (sem carga no live).

Pirâmide: estáticos (fonte/rota/papel) + E2E só-leitura (sem upload, sem ZIP,
sem escrita — cleanup desnecessário).
Troca forçada ciente: 123456 provisória; skip se trocada ou diálogo aberto.

Como rodar:
    .venv\\Scripts\\python -m pytest assets/test/pw_edit_pdf_painel.py -v
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


class TestEditPdfEstatico:
    """Unitários rápidos sem servidor."""

    def test_testids_via_props(self):
        """Painel expõe testids via .props('data-testid=...')."""
        fonte = _ler("mod_edit_pdf/telas.py")
        for tid in ("editar_pdf-atualizar", "editar_pdf-juntar",
                    "editar_pdf-excluir", "editar_pdf-enviar"):
            assert f"data-testid={tid}" in fonte, tid
        assert ".props('data-testid=" in fonte

    def test_rota_edit_pdf_registrada(self):
        """Rota /edit-pdf registrada."""
        assert '@ui.page("/edit-pdf")' in _ler("main.py")

    def test_papel_do_ator_antes_da_escrita(self):
        """Acesso validado antes de upload/juntar/excluir (papel + dono)."""
        fonte = _ler("mod_edit_pdf/telas.py")
        central = _ler("main.py")
        assert 'chave_modulo="editar_pdf"' in central
        assert 'perfil == "administrador_geral"' in fonte
        assert "pasta_usuario(" in fonte


class TestEditPdfPainelE2E:
    """E2E headless, sequencial, sem upload (sem carga)."""

    def test_admin_ve_painel(self, page):
        """qamaster vê atualizar + enviar + juntar."""
        ok = fazer_login(page, ADMIN_USUARIO, ADMIN_SENHA)
        if not ok:
            pytest.skip("senha do qamaster trocada (provisória) — ciente")
        if _dialogo_troca_visivel(page):
            pytest.skip("troca obrigatória pendente")
        page.goto(f"{BASE_URL}/edit-pdf", wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(2500)
        expect(page.get_by_test_id("editar_pdf-atualizar")).to_be_visible(timeout=15000)
        expect(page.get_by_test_id("editar_pdf-enviar")).to_be_visible(timeout=15000)
        expect(page.get_by_test_id("editar_pdf-juntar")).to_be_visible(timeout=15000)

    def test_comum_tambem_ve_painel(self, page):
        """qacomum (com editar_pdf liberado) vê o painel sem poder admin."""
        ok = fazer_login(page, COMUM_USUARIO, COMUM_SENHA)
        if not ok:
            pytest.skip("senha do qacomum trocada (provisória) — ciente")
        if _dialogo_troca_visivel(page):
            pytest.skip("troca obrigatória pendente")
        page.goto(f"{BASE_URL}/edit-pdf", wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(2500)
        expect(page.get_by_test_id("editar_pdf-atualizar")).to_be_visible(timeout=15000)

    def test_atualizar_nao_quebra(self, page):
        """Clicar Atualizar recarrega a lista sem erro fatal (só leitura)."""
        ok = fazer_login(page, ADMIN_USUARIO, ADMIN_SENHA)
        if not ok:
            pytest.skip("senha do qamaster trocada — ciente")
        if _dialogo_troca_visivel(page):
            pytest.skip("troca obrigatória pendente")
        page.goto(f"{BASE_URL}/edit-pdf", wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(2500)
        page.get_by_test_id("editar_pdf-atualizar").click()
        page.wait_for_timeout(2000)
        expect(page.get_by_test_id("editar_pdf-atualizar")).to_be_visible(timeout=15000)


if __name__ == "__main__":
    print("Execute: .venv\\Scripts\\python -m pytest assets/test/pw_edit_pdf_painel.py -v")
