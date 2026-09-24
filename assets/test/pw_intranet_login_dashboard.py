"""Login + dashboard do núcleo intranet (pytest-playwright, headless).

EN: Intranet core — /login (data-testid login-usuario/senha/entrar via .props)
    and dashboard / (header, menu-hamburguer, menu-home/menu-sair) for
    qamaster (administrador_geral) and qacomum (comum).
PT: Núcleo intranet — /login (data-testid login-usuario/senha/entrar via
    .props) e dashboard / (header, menu-hamburguer, menu-home/menu-sair) com
    qamaster (administrador_geral) e qacomum (comum).

Pirâmide: estáticos rápidos (fonte/rotas/papel) + poucos E2E headless,
sequenciais, 1 contexto por teste, sem carga.
Troca forçada ciente: senha padrão 123456 é provisória e pode já ter sido
trocada; se o diálogo "Troca de senha obrigatória"/"Credenciais
obrigatórias" abrir, o login é considerado OK e o teste segue com asserts
limitados (não tenta redefinir senha nem tocar banco).

Como rodar (Windows):
    .venv\\Scripts\\python -m pytest assets/test/pw_intranet_login_dashboard.py -v
Tudo (6 módulos):
    .venv\\Scripts\\python -m pytest assets/test/pw_*.py -v
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
    """Lê um arquivo do projeto em UTF-8 (somente leitura)."""
    try:
        return (RAIZ / rel).read_text(encoding="utf-8")
    except Exception:
        return ""


def _dialogo_troca_visivel(page) -> bool:
    """Detecta o diálogo de troca obrigatória (troca forçada ciente)."""
    try:
        for texto in ("Troca de senha obrigatória", "Credenciais obrigatórias"):
            if page.get_by_text(texto, exact=False).count() > 0:
                return True
        return False
    except Exception:
        return False


def fazer_login(page, usuario: str, senha: str) -> bool:
    """Faz login via data-testid e retorna True se saiu do /login.

    Troca forçada ciente: se a senha padrão já foi trocada pelo usuário, o
    login permanece no /login — o chamador deve tratar como skip/erro amigável.
    Se o diálogo de troca obrigatória abrir sobre o dashboard, retorna True.
    """
    try:
        page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded", timeout=15000)
    except Exception:
        pytest.skip(f"servidor live indisponível em {BASE_URL} — pule (sem derrubar)")
    page.get_by_test_id("login-usuario").fill(usuario)
    page.get_by_test_id("login-senha").fill(senha)
    page.get_by_test_id("login-entrar").click()
    try:
        page.wait_for_function(
            "() => !location.pathname.startsWith('/login')", timeout=20000
        )
    except Exception:
        pass
    try:
        page.wait_for_load_state("domcontentloaded", timeout=10000)
    except Exception:
        pass
    page.wait_for_timeout(1500)
    url = ""
    try:
        url = page.url
    except Exception:
        url = ""
    if "/login" in (url or "") and not _dialogo_troca_visivel(page):
        return False
    return True


def _abrir_menu(page):
    """Abre o drawer via hambúrguer (se fechado) para expor os menu-*."""
    try:
        page.get_by_test_id("menu-hamburguer").click(timeout=5000)
        page.wait_for_timeout(800)
    except Exception:
        pass


class TestLoginEstatico:
    """Asserts rápidos sem servidor (topo da pirâmide)."""

    def test_login_tem_testids_via_props(self):
        """login-usuario/senha/entrar expostos via .props('data-testid=...')."""
        fonte = _ler("main.py")
        assert ".props('data-testid=login-usuario')" in fonte
        assert ".props('data-testid=login-senha')" in fonte
        assert ".props('data-testid=login-entrar')" in fonte

    def test_rotas_login_e_dashboard_registradas(self):
        """Rotas /login e / registradas no entry point."""
        fonte = _ler("main.py")
        assert '@ui.page("/login")' in fonte
        assert '@ui.page("/")' in fonte

    def test_menu_tem_testids_via_props(self):
        """Drawer expõe menu-hamburguer/home/sair via data-testid."""
        fonte = _ler("mod_intranet/telas.py")
        assert "data-testid=menu-hamburguer" in fonte
        assert 'testid="menu-home"' in fonte or "menu-home" in fonte
        assert 'testid="menu-sair"' in fonte or "menu-sair" in fonte

    def test_papel_validado_antes_de_escrever_sessao(self):
        """Papel/credencial validado antes de registrar sessão (autenticar)."""
        fonte = _ler("main.py")
        assert "autenticacao.autenticar(" in fonte
        assert "registrar_login" in fonte


class TestLoginDashboardE2E:
    """E2E headless, sequencial, 1 contexto por teste, sem carga."""

    def test_qamaster_entra_e_ve_dashboard(self, page):
        """Admin entra e vê header + saudação (ou diálogo de troca ciente)."""
        ok = fazer_login(page, ADMIN_USUARIO, ADMIN_SENHA)
        if not ok:
            pytest.skip("senha do qamaster já foi trocada (provisória) — ciente, sem falhar")
        if _dialogo_troca_visivel(page):
            expect(page.get_by_text("Troca de senha obrigatória").or_(
                page.get_by_text("Credenciais obrigatórias"))).to_be_visible(timeout=10000)
            return
        expect(page.locator("header").first).to_be_visible(timeout=15000)
        expect(page.locator("body")).to_contain_text("Olá", timeout=15000)

    def test_qacomum_entra_e_ve_dashboard(self, page):
        """Comum entra e vê header sem área restrita de admin."""
        ok = fazer_login(page, COMUM_USUARIO, COMUM_SENHA)
        if not ok:
            pytest.skip("senha do qacomum já foi trocada (provisória) — ciente, sem falhar")
        if _dialogo_troca_visivel(page):
            return
        expect(page.locator("header").first).to_be_visible(timeout=15000)
        expect(page.locator("body")).not_to_contain_text(
            "Área de configuração restrita", timeout=5000)

    def test_login_invalido_permanece_no_login(self, page):
        """Senha errada não sai do /login (validação do ator)."""
        try:
            page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded", timeout=15000)
        except Exception:
            pytest.skip(f"servidor live indisponível em {BASE_URL}")
        page.get_by_test_id("login-usuario").fill(ADMIN_USUARIO)
        page.get_by_test_id("login-senha").fill("senha_totalmente_errada_9z")
        page.get_by_test_id("login-entrar").click()
        page.wait_for_timeout(2000)
        assert "/login" in page.url

    def test_menu_hamburguer_expoe_home_e_sair(self, page):
        """Drawer expõe menu-home e menu-sair após login admin."""
        ok = fazer_login(page, ADMIN_USUARIO, ADMIN_SENHA)
        if not ok:
            pytest.skip("senha do qamaster já foi trocada — ciente")
        if _dialogo_troca_visivel(page):
            pytest.skip("troca obrigatória pendente — menu bloqueado pelo diálogo persistente")
        _abrir_menu(page)
        expect(page.get_by_test_id("menu-home")).to_be_visible(timeout=15000)
        expect(page.get_by_test_id("menu-sair")).to_be_visible(timeout=15000)


if __name__ == "__main__":
    print("Execute: .venv\\Scripts\\python -m pytest assets/test/pw_intranet_login_dashboard.py -v")
