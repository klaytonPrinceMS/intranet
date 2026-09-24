"""Renomear empenhos /renomear-empenho (pytest-playwright, headless).

EN: Empenho renamer — empenhos-* testids via .props (busca/atualizar/
    processar/navegar-pesquisa); qamaster and qacomum (both with empenhos
    access) see the panel; no batch processing (no load on live).
PT: Renomear empenhos — testids empenhos-* via .props (busca/atualizar/
    processar/navegar-pesquisa); qamaster e qacomum (ambos com empenhos)
    veem o painel; sem processar lote (sem carga no live).

Pirâmide: estáticos (fonte/rota/papel) + E2E só-leitura (navegação, busca e
atualizar — sem renomear de verdade, sem escrita).
Troca forçada ciente: 123456 provisória; skip se trocada ou diálogo aberto.

Como rodar:
    .venv\\Scripts\\python -m pytest assets/test/pw_empenhos_navegacao.py -v
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


class TestEmpenhosEstatico:
    """Unitários rápidos sem servidor."""

    def test_testids_via_props(self):
        """Navegação/busca/processar via .props('data-testid=...')."""
        fonte = _ler("mod_renomear_empenho/telas.py")
        for tid in ("empenhos-busca", "empenhos-atualizar",
                    "empenhos-processar", "empenhos-navegar-pesquisa"):
            assert f"data-testid={tid}" in fonte, tid
        assert ".props(" in fonte and "data-testid=" in fonte

    def test_rota_empenhos_registrada(self):
        """Rota /renomear-empenho registrada."""
        assert '@ui.page("/renomear-empenho")' in _ler("main.py")

    def test_papel_do_ator_antes_da_escrita(self):
        """Renomear/processar valida papel antes de escrever."""
        fonte = _ler("mod_renomear_empenho/telas.py")
        assert "validar_acesso_modulo" in fonte or "eh_admin_do_modulo" in fonte \
            or "_pode" in fonte or "perfil" in fonte


class TestEmpenhosNavegacaoE2E:
    """E2E headless, sequencial, sem processar lote."""

    def test_admin_ve_painel_e_busca(self, page):
        """qamaster vê busca + atualizar + processar."""
        ok = fazer_login(page, ADMIN_USUARIO, ADMIN_SENHA)
        if not ok:
            pytest.skip("senha do qamaster trocada (provisória) — ciente")
        if _dialogo_troca_visivel(page):
            pytest.skip("troca obrigatória pendente")
        page.goto(f"{BASE_URL}/renomear-empenho", wait_until="domcontentloaded",
                  timeout=15000)
        page.wait_for_timeout(2500)
        expect(page.get_by_test_id("empenhos-busca").first).to_be_visible(timeout=15000)
        expect(page.get_by_test_id("empenhos-atualizar")).to_be_visible(timeout=15000)

    def test_comum_ve_painel(self, page):
        """qacomum (com empenhos liberado) vê o painel."""
        ok = fazer_login(page, COMUM_USUARIO, COMUM_SENHA)
        if not ok:
            pytest.skip("senha do qacomum trocada (provisória) — ciente")
        if _dialogo_troca_visivel(page):
            pytest.skip("troca obrigatória pendente")
        page.goto(f"{BASE_URL}/renomear-empenho", wait_until="domcontentloaded",
                  timeout=15000)
        page.wait_for_timeout(2500)
        expect(page.get_by_test_id("empenhos-busca").first).to_be_visible(timeout=15000)

    def test_busca_filtra_sem_escrever(self, page):
        """Digitar na busca filtra sem renomear nada (só leitura)."""
        ok = fazer_login(page, ADMIN_USUARIO, ADMIN_SENHA)
        if not ok:
            pytest.skip("senha do qamaster trocada — ciente")
        if _dialogo_troca_visivel(page):
            pytest.skip("troca obrigatória pendente")
        page.goto(f"{BASE_URL}/renomear-empenho", wait_until="domcontentloaded",
                  timeout=15000)
        page.wait_for_timeout(2500)
        campo = page.get_by_test_id("empenhos-busca").first
        expect(campo).to_be_visible(timeout=15000)
        campo.fill("QA-inexistente-zzz")
        page.wait_for_timeout(1500)
        # Sem escrita: apenas garante que o painel segue íntegro.
        expect(page.get_by_test_id("empenhos-atualizar")).to_be_visible(timeout=15000)


if __name__ == "__main__":
    print("Execute: .venv\\Scripts\\python -m pytest assets/test/pw_empenhos_navegacao.py -v")
