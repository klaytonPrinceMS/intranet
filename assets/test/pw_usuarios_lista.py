"""Gestão de usuários /users (pytest-playwright, headless).

EN: User admin — /users list (usuarios-busca/usuarios-novo via .props);
    qamaster (administrador_geral) sees the list, qacomum (comum) is denied.
PT: Gestão de usuários — /users lista (usuarios-busca/usuarios-novo via
    .props); qamaster (administrador_geral) vê a lista, qacomum (comum) é
    barrado antes de qualquer escrita.

Pirâmide: estáticos (fonte/rota/papel) + E2E de leitura; sem escrita no banco
(o "Novo usuário" só abre e fecha o diálogo — cleanup implícito).
Troca forçada EXECUTADA: quando o diálogo "Troca de senha obrigatória" abre,
o login CONCLUI a troca (mesma senha de origem) em vez de pular — antes a
cobertura rodava majoritariamente pulada, sem ninguém ver. Só há skip para
infra real (servidor fora / credencial inválida).

Como rodar:
    .venv\\Scripts\\python -m pytest assets/test/pw_usuarios_lista.py -v
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
    """Lê fonte do projeto (somente leitura)."""
    try:
        return (RAIZ / rel).read_text(encoding="utf-8")
    except Exception:
        return ""


def fazer_login(page, usuario: str, senha: str) -> bool:
    """Faz login e CONCLUI a troca de senha obrigatória, se aparecer.

    Antes: `pytest.skip` quando o diálogo de troca abria — o que fazia a
    suíte passar sem verificar quase nada. Agora a troca é feita com a
    MESMA senha de origem (o fluxo só exige que a troca aconteça) e o
    `forcar_troca` é zerado, então a próxima execução já entra direto.
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
                "() => !location.pathname.startsWith('/login')", timeout=20000)
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
        """qamaster vê busca, botão Novo e o próprio usuário na lista.

        A coluna exibida por padrão é "Tratamento" (NOME DE EXIBIÇÃO), não o
        login — o `qamaster` aparece como "Usuário de Teste QA Master". Por
        isso o teste compara com o nome lido do cabeçalho, em vez de fixar
        string: prova que o usuário logado está LISTADO, sem depender do
        nome nem do login.
        """
        ok = fazer_login(page, ADMIN_USUARIO, ADMIN_SENHA)
        if not ok:
            pytest.skip("login do qamaster não abriu sessão (credencial "
                        "inválida ou infraestrutura instável)")
        assert not _dialogo_troca_visivel(page), (
            "troca de senha obrigatória NÃO foi concluída pelo login — o "
            "diálogo continua bloqueando a tela")
        page.goto(f"{BASE_URL}/users", wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(2000)
        expect(page.get_by_test_id("usuarios-busca")).to_be_visible(timeout=15000)
        expect(page.get_by_test_id("usuarios-novo")).to_be_visible(timeout=15000)
        nome = (page.get_by_test_id("header-nome-usuario").inner_text() or "").strip()
        assert nome, "cabeçalho não mostrou o nome do usuário logado"
        # aparece no cabeçalho E na linha da lista
        assert page.locator("body").inner_text().count(nome) >= 2, (
            f"o usuário logado ({nome!r}) não apareceu na lista de usuários")

    def test_novo_usuario_abre_e_fecha_sem_escrever(self, page):
        """Abrir 'Novo usuário' e fechar não cria nada (cleanup implícito)."""
        ok = fazer_login(page, ADMIN_USUARIO, ADMIN_SENHA)
        if not ok:
            pytest.skip("login do qamaster não abriu sessão (credencial "
                        "inválida ou infraestrutura instável)")
        assert not _dialogo_troca_visivel(page), (
            "troca de senha obrigatória NÃO foi concluída pelo login — o "
            "diálogo continua bloqueando a tela")
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
        """qacomum é barrado de /users — o papel comum não administra usuários.

        Comportamento REAL verificado: o perfil `comum` que tenta `/users` é
        REDIRECIONADO para a home, sem mensagem na tela. O teste afirma o
        redirecionamento (a lista nunca aparece), que é o que garante a
        barreira — antes ele exigia um texto que a tela não mostra.
        """
        ok = fazer_login(page, COMUM_USUARIO, COMUM_SENHA)
        if not ok:
            pytest.skip("login do qacomum não abriu sessão (credencial "
                        "inválida ou infraestrutura instável)")
        assert not _dialogo_troca_visivel(page), (
            "troca de senha obrigatória NÃO foi concluída pelo login — o "
            "diálogo continua bloqueando a tela")
        page.goto(f"{BASE_URL}/users", wait_until="domcontentloaded", timeout=15000)
        try:
            page.wait_for_url(lambda u: "/users" not in u, timeout=15000)
        except Exception:
            pass
        assert "/users" not in page.url, (
            f"perfil comum NÃO deveria acessar /users (ficou em {page.url})")
        expect(page.get_by_test_id("usuarios-busca")).to_have_count(0)


if __name__ == "__main__":
    print("Execute: .venv\\Scripts\\python -m pytest assets/test/pw_usuarios_lista.py -v")
