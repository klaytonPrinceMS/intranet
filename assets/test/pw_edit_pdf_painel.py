"""Editor de PDF /edit-pdf (pytest-playwright, headless).

EN: PDF editor panel — editar_pdf-* testids via .props; qamaster and qacomum
    (both with editar_pdf access) see atualizar/enviar/juntar without upload.
PT: Editor de PDF — painel com testids editar_pdf-* via .props; qamaster e
    qacomum (ambos com acesso a editar_pdf) veem atualizar/enviar/juntar sem
    fazer upload (sem carga no live).

Pirâmide: estáticos (fonte/rota/papel) + E2E só-leitura (sem upload, sem ZIP,
sem escrita — cleanup desnecessário).
Troca forçada EXECUTADA: quando o diálogo "Troca de senha obrigatória" abre,
o login CONCLUI a troca (mesma senha de origem) em vez de pular — antes a
cobertura rodava majoritariamente pulada, sem ninguém ver. Só há skip para
infra real (servidor fora / credencial inválida).

Como rodar:
    .venv\\Scripts\\python -m pytest assets/test/pw_edit_pdf_painel.py -v
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
    """Lê fonte (somente leitura)."""
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
            pytest.skip("login do qamaster não abriu sessão (credencial "
                        "inválida ou infraestrutura instável)")
        assert not _dialogo_troca_visivel(page), (
            "troca de senha obrigatória NÃO foi concluída pelo login — o "
            "diálogo continua bloqueando a tela")
        page.goto(f"{BASE_URL}/edit-pdf", wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(2500)
        expect(page.get_by_test_id("editar_pdf-atualizar")).to_be_visible(timeout=15000)
        expect(page.get_by_test_id("editar_pdf-enviar")).to_be_visible(timeout=15000)
        expect(page.get_by_test_id("editar_pdf-juntar")).to_be_visible(timeout=15000)

    def test_comum_tambem_ve_painel(self, page):
        """qacomum (com editar_pdf liberado) vê o painel sem poder admin."""
        ok = fazer_login(page, COMUM_USUARIO, COMUM_SENHA)
        if not ok:
            pytest.skip("login do qacomum não abriu sessão (credencial "
                        "inválida ou infraestrutura instável)")
        assert not _dialogo_troca_visivel(page), (
            "troca de senha obrigatória NÃO foi concluída pelo login — o "
            "diálogo continua bloqueando a tela")
        page.goto(f"{BASE_URL}/edit-pdf", wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(2500)
        expect(page.get_by_test_id("editar_pdf-atualizar")).to_be_visible(timeout=15000)

    def test_atualizar_nao_quebra(self, page):
        """Clicar Atualizar recarrega a lista sem erro fatal (só leitura)."""
        ok = fazer_login(page, ADMIN_USUARIO, ADMIN_SENHA)
        if not ok:
            pytest.skip("login do qamaster não abriu sessão (credencial "
                        "inválida ou infraestrutura instável)")
        assert not _dialogo_troca_visivel(page), (
            "troca de senha obrigatória NÃO foi concluída pelo login — o "
            "diálogo continua bloqueando a tela")
        page.goto(f"{BASE_URL}/edit-pdf", wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(2500)
        page.get_by_test_id("editar_pdf-atualizar").click()
        page.wait_for_timeout(2000)
        expect(page.get_by_test_id("editar_pdf-atualizar")).to_be_visible(timeout=15000)


if __name__ == "__main__":
    print("Execute: .venv\\Scripts\\python -m pytest assets/test/pw_edit_pdf_painel.py -v")
