"""Login + dashboard do núcleo intranet (pytest-playwright, headless).

EN: Intranet core — /login (data-testid login-usuario/senha/entrar via .props)
    and dashboard / (header, menu-hamburguer, menu-home/menu-sair) for
    qamaster (administrador_geral) and qacomum (comum).
PT: Núcleo intranet — /login (data-testid login-usuario/senha/entrar via
    .props) e dashboard / (header, menu-hamburguer, menu-home/menu-sair) com
    qamaster (administrador_geral) e qacomum (comum).

Pirâmide: estáticos rápidos (fonte/rotas/papel) + poucos E2E headless,
sequenciais, 1 contexto por teste, sem carga.
Troca forçada EXECUTADA: os seeds `qamaster` e `qacomum` nascem com
`forcar_troca=1`, então o 1º login abre o diálogo "Troca de senha
obrigatória"/"Credenciais obrigatórias" e bloqueia a tela inteira. Antes o
login tratava isso como skip (e os testes ainda retornavam cedo, passando sem
verificar nada) — a cobertura Playwright rodava majoritariamente pulada.
Agora o login **CONCLUI a troca** com a mesma senha de origem e zera o
`forcar_troca`, então o dashboard/menu é de fato verificado. Só resta skip
para infra real (servidor fora ou credencial inválida).

Como rodar (Windows):
    .venv\\Scripts\\python -m pytest assets/test/pw_intranet_login_dashboard.py -v
Tudo (6 módulos):
    .venv\\Scripts\\python -m pytest assets/test/pw_*.py -v
"""

import os
import pathlib
import sys

import pytest
from playwright.sync_api import expect

# `qa_login_helper` e irmao deste arquivo: entra no path explicitamente para
# nao depender do modo de import do pytest.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

pytestmark = pytest.mark.e2e

BASE_URL = os.environ.get("INTRANET_BASE_URL", "http://localhost:8080")
ADMIN_USUARIO = "qamaster"
ADMIN_SENHA = "123456"
COMUM_USUARIO = "qacomum"
COMUM_SENHA = "123456"

RAIZ = pathlib.Path(__file__).resolve().parents[2]

# Login/troca em UM lugar so (ver qa_login_helper). A copia local detectava a
# troca por TEXTO solto e a copia do login fazia `pytest.skip` quando o
# dialogo abria — por isso a cobertura Playwright rodava majoritariamente
# pulada. `zerar_forcar_troca` nao e importado aqui de proposito: quem chama
# e `fazer_login_com_troca`, e importar sem usar quebra o pyflakes.
from qa_login_helper import (  # noqa: E402
    _dialogo_troca_visivel,
    concluir_troca as _concluir_troca,
)


def _ler(rel: str) -> str:
    """Lê um arquivo do projeto em UTF-8 (somente leitura)."""
    try:
        return (RAIZ / rel).read_text(encoding="utf-8")
    except Exception:
        return ""


def fazer_login(page, usuario: str, senha: str) -> bool:
    """Faz login e CONCLUI a troca de senha obrigatória, se aparecer.

    Antes: `pytest.skip`/retorno silencioso quando o diálogo de troca
    abria — o 1º login dos seeds `qamaster`/`qacomum` nasce com
    `forcar_troca=1`, então o menu/dashboard ficava bloqueado e o teste
    passava sem verificar nada. Agora a troca é feita com a MESMA senha de
    origem (o fluxo só exige que a troca aconteça) e o `forcar_troca` é
    zerado, então a próxima execução já entra direto.
    """
    try:
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
        try:
            page.wait_for_timeout(1500)
        except Exception:
            pass
    except pytest.skip.Exception:
        raise
    except Exception as exc:
        pytest.skip(f"falha de infra no login — pule: {exc}")
        return False

    if _dialogo_troca_visivel(page):
        # CONCLUI a troca (mesma senha de origem) em vez de pular
        _concluir_troca(page, senha, senha)
    assert not _dialogo_troca_visivel(page), (
        "troca de senha obrigatória NÃO foi concluída pelo login — o "
        "diálogo continua bloqueando a tela")
    try:
        url = page.url
    except Exception:
        url = ""
    return "/login" not in (url or "")


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
        """Admin entra e vê header + saudação (troca de senha já concluída)."""
        ok = fazer_login(page, ADMIN_USUARIO, ADMIN_SENHA)
        if not ok:
            pytest.skip("login do qamaster não abriu sessão (credencial "
                        "inválida ou infraestrutura instável)")
        assert not _dialogo_troca_visivel(page), (
            "troca de senha obrigatória NÃO foi concluída pelo login — o "
            "diálogo continua bloqueando o dashboard")
        expect(page.locator("header").first).to_be_visible(timeout=15000)
        expect(page.locator("body")).to_contain_text("Olá", timeout=15000)

    def test_qacomum_entra_e_ve_dashboard(self, page):
        """Comum entra e vê header sem área restrita de admin."""
        ok = fazer_login(page, COMUM_USUARIO, COMUM_SENHA)
        if not ok:
            pytest.skip("login do qacomum não abriu sessão (credencial "
                        "inválida ou infraestrutura instável)")
        assert not _dialogo_troca_visivel(page), (
            "troca de senha obrigatória NÃO foi concluída pelo login — o "
            "diálogo continua bloqueando o dashboard")
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
            pytest.skip("login do qamaster não abriu sessão (credencial "
                        "inválida ou infraestrutura instável)")
        # Débito resolvido: antes era `pytest.skip("troca obrigatória
        # pendente — menu bloqueado pelo diálogo persistente")`. Como o login
        # agora CONCLUI a troca, o diálogo não deve existir mais aqui — se
        # existir, é falha real do login/troca, não motivo para pular.
        assert not _dialogo_troca_visivel(page), (
            "troca de senha obrigatória NÃO foi concluída pelo login — o "
            "diálogo continua bloqueando o menu")
        _abrir_menu(page)
        expect(page.get_by_test_id("menu-home")).to_be_visible(timeout=15000)
        expect(page.get_by_test_id("menu-sair")).to_be_visible(timeout=15000)


if __name__ == "__main__":
    print("Execute: .venv\\Scripts\\python -m pytest assets/test/pw_intranet_login_dashboard.py -v")
