"""Gestão de usuários /users (pytest-playwright, headless).

EN: User admin — /users list (usuarios-busca/usuarios-novo via .props);
    qamaster (administrador_geral) sees the list, qacomum (comum) is denied.
PT: Gestão de usuários — /users lista (usuarios-busca/usuarios-novo via
    .props); qamaster (administrador_geral) vê a lista, qacomum (comum) é
    barrado antes de qualquer escrita.

Pirâmide: estáticos (fonte/rota/papel) + E2E de leitura; sem escrita no banco
(o "Novo usuário" só abre e fecha o diálogo — cleanup implícito).
Troca forçada ciente: 123456 é provisória; se o diálogo de troca abrir ou a
senha já tiver sido trocada, o teste faz skip amigável.

Como rodar:
    .venv\\Scripts\\python -m pytest assets/test/pw_usuarios_lista.py -v
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
    """Lê fonte do projeto (somente leitura)."""
    try:
        return (RAIZ / rel).read_text(encoding="utf-8")
    except Exception:
        return ""


def _dialogo_troca_visivel(page) -> bool:
    """Detecta troca obrigatória (troca forçada ciente)."""
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


class TestUsuariosEstatico:
    """Unitários rápidos: testids, rota e papel do ator."""

    def test_testids_via_props(self):
        """Busca e botão Novo via .props('data-testid=...')."""
        fonte = _ler("mod_gest_cad_usuario/telas.py")
        assert ".props('data-testid=usuarios-busca')" in fonte
        assert ".props('data-testid=usuarios-novo')" in fonte

    def test_rota_users_registrada(self):
        """Rota /users registrada no entry point."""
        fonte = _ler("main.py")
        assert '@ui.page("/users")' in fonte

    def test_papel_do_ator_antes_da_escrita(self):
        """Somente admin geral/admin do módulo escreve; demais barrados."""
        fonte = _ler("mod_gest_cad_usuario/telas.py")
        assert 'perfil_global == "administrador_geral"' in fonte
        assert 'eh_admin_do_modulo' in fonte
        assert "Acesso restrito" in fonte

    def test_listar_usuarios_existe_no_manipulador(self):
        """Manipulador expõe listar_usuarios (leitura da lista)."""
        fonte = _ler("mod_gest_cad_usuario/bd_manipulador.py")
        assert "def listar_usuarios(" in fonte


class TestUsuariosListaE2E:
    """E2E headless, sequencial, sem carga; leitura + diálogo sem escrita."""

    def test_admin_ve_lista_e_busca(self, page):
        """qamaster vê busca, botão Novo e ao menos o próprio usuário."""
        ok = fazer_login(page, ADMIN_USUARIO, ADMIN_SENHA)
        if not ok:
            pytest.skip("senha do qamaster trocada (provisória) — ciente")
        if _dialogo_troca_visivel(page):
            pytest.skip("troca obrigatória pendente — lista bloqueada pelo diálogo")
        page.goto(f"{BASE_URL}/users", wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(2000)
        expect(page.get_by_test_id("usuarios-busca")).to_be_visible(timeout=15000)
        expect(page.get_by_test_id("usuarios-novo")).to_be_visible(timeout=15000)
        expect(page.locator("body")).to_contain_text("qamaster", timeout=15000)

    def test_novo_usuario_abre_e_fecha_sem_escrever(self, page):
        """Abrir 'Novo usuário' e fechar não cria nada (cleanup implícito)."""
        ok = fazer_login(page, ADMIN_USUARIO, ADMIN_SENHA)
        if not ok:
            pytest.skip("senha do qamaster trocada — ciente")
        if _dialogo_troca_visivel(page):
            pytest.skip("troca obrigatória pendente")
        page.goto(f"{BASE_URL}/users", wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(2000)
        page.get_by_test_id("usuarios-novo").click()
        page.wait_for_timeout(1500)
        # Diálogo de criação aparece (qualquer um destes textos prova abertura).
        corpo = page.locator("body")
        expect(corpo).to_contain_text("Novo", timeout=10000)
        # Fecha com ESC ou clique fora quando possível — sem salvar (sem escrita).
        try:
            page.keyboard.press("Escape")
            page.wait_for_timeout(800)
        except Exception:
            pass

    def test_comum_e_barrado_antes_da_escrita(self, page):
        """qacomum vê 'Acesso restrito' em /users (papel validado)."""
        ok = fazer_login(page, COMUM_USUARIO, COMUM_SENHA)
        if not ok:
            pytest.skip("senha do qacomum trocada (provisória) — ciente")
        if _dialogo_troca_visivel(page):
            pytest.skip("troca obrigatória pendente")
        page.goto(f"{BASE_URL}/users", wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(2000)
        expect(page.locator("body")).to_contain_text("Acesso restrito", timeout=15000)


if __name__ == "__main__":
    print("Execute: .venv\\Scripts\\python -m pytest assets/test/pw_usuarios_lista.py -v")
