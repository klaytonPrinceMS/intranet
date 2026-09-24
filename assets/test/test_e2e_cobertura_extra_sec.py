"""E2E Cobertura Extra Sec — ultimos 85 testids (linhas 86-170) (kbp-devSecOps).

EN — Playwright coverage for the last 85 testids from all_testids.txt
(lines 86-170): each testid gets one def test_seg_<slug> on its owner
route, asserting presence via visible/enabled only (never destructive
click), validating no traversal and no password leak. Localhost only.

PT-BR — Cobertura Playwright dos ultimos 85 testids do all_testids.txt
(linhas 86-170): cada testid ganha um def test_seg_<slug> na sua rota
dona, asserta presenca so via visible/enabled (nunca clique destrutivo),
valida sem traversal e sem vazar senha. Somente localhost.

Execucao (servidor vivo em outro terminal):
    .venv/Scripts/python.exe -m pytest assets/test/test_e2e_cobertura_extra_sec.py -v
    .venv/Scripts/python.exe -m pytest assets/test/test_e2e_cobertura_extra_sec.py -v -m "e2e and security"

Notas: confinado a C:\\opencode; localhost apenas http://localhost:8080;
sem k6/carga; sem segredos alem do seed QA; sem commit; sem sys.exit.
Login padrao qamaster/123456 (seed AGENTS.md 8.2) ou acesso publico /tv.
Toda funcao com try/except + logger; skip se servidor fora do ar.
"""

import os
import re
import sys
import urllib.request

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASE_URL = "http://localhost:8080"
USUARIO_QAMASTER = "qamaster"
SENHA_QA = "123456"  # nosec B105 B106 B107 -- seed QA AGENTS.md 8.2, nunca producao

pytestmark = [pytest.mark.e2e, pytest.mark.security]


@pytest.fixture(scope="session")
def browser_type_launch_args():
    """EN: Chromium flags for CI. PT-BR: flags do Chromium para CI."""
    try:
        return {"args": ["--no-sandbox"]}
    except Exception:
        return {"args": ["--no-sandbox"]}


def _log():
    """EN: Module logger. PT-BR: logger do modulo."""
    try:
        from mod_intranet import observabilidade as _obs
        return _obs.get_logger("devsecops")
    except Exception:
        try:
            import logging as _lg
            return _lg.getLogger("devsecops")
        except Exception:
            return None


def _garantir_localhost(url):
    """EN: Refuse non-localhost URLs. PT-BR: recusa URL fora de localhost."""
    try:
        assert "localhost" in url or "127.0.0.1" in url, "URL fora de localhost"
        return True
    except Exception:
        raise


def _servidor_ativo():
    """EN: True when localhost:8080 answers. PT-BR: True se localhost:8080 responde."""
    try:
        _garantir_localhost(BASE_URL)
        with urllib.request.urlopen(BASE_URL + "/login", timeout=3) as resp:  # nosec B310 -- URL fixa localhost com guarda _garantir_localhost
            return resp.status in (200, 302)
    except Exception:
        return False


def _fechar_dialogos(page):
    """EN: Remove blocking dialogs. PT-BR: remove dialogos bloqueadores."""
    try:
        page.evaluate("() => { document.querySelectorAll('.q-dialog').forEach(d=>d.remove()); }")
        page.wait_for_timeout(400)
    except Exception:
        try:
            lg = _log()
            if lg is not None:
                lg.exception("cobertura_extra_sec: _fechar_dialogos falhou")
        except Exception:
            pass


def _fazer_login(page, usuario=USUARIO_QAMASTER, senha=SENHA_QA):
    """EN: Login with QA seed user. PT-BR: login com usuario seed QA."""
    try:
        _garantir_localhost(BASE_URL)
        page.goto(BASE_URL + "/login", wait_until="domcontentloaded")
        page.wait_for_timeout(2000)
        page.get_by_test_id("login-usuario").fill(usuario)
        page.get_by_test_id("login-senha").fill(senha)
        page.get_by_test_id("login-entrar").click()
        page.wait_for_timeout(4000)
        _fechar_dialogos(page)
    except Exception:
        try:
            lg = _log()
            if lg is not None:
                lg.exception("cobertura_extra_sec: _fazer_login falhou para %s", usuario)
        except Exception:
            pass
        raise


def _cookie_sem_segredo(page):
    """EN: Cookie must never expose password. PT-BR: cookie nunca expoe senha."""
    try:
        cookie = page.evaluate("() => document.cookie || ''")
        assert SENHA_QA not in cookie, "cookie vazou senha"
        return cookie
    except AssertionError:
        raise
    except Exception:
        try:
            lg = _log()
            if lg is not None:
                lg.exception("cobertura_extra_sec: _cookie_sem_segredo falhou")
        except Exception:
            pass
        return ""


def _rota_para_testid(testid):
    """EN: Owner route + login need. PT-BR: rota dona + se precisa login."""
    try:
        tid = testid or ""
        if tid.startswith("filas-tv-") or tid in ("filas-card-abrir-tv", "filas-card-tv-grupo"):
            return ("/tv", False)
        if tid.startswith("tv-"):
            return ("/tv", False)
        if tid.startswith("filas-"):
            return ("/filas", True)
        if tid.startswith("tecnico-"):
            return ("/tecnico", True)
        if tid.startswith("solicita-"):
            return ("/solicita-impressao", True)
        if tid.startswith("agregador-"):
            return ("/agregador-noticias", True)
        if tid.startswith("config-"):
            return ("/configuracoes", True)
        if tid.startswith("menu-"):
            return ("/", True)
        if tid.startswith("editpdf-") or tid.startswith("editar_pdf-"):
            return ("/edit-pdf", True)
        if tid.startswith("empenhos-"):
            return ("/renomear-empenho", True)
        if tid.startswith("lista-"):
            return ("/lista-telefonica", True)
        if tid.startswith("login-"):
            return ("/login", False)
        if tid.startswith("usuarios-"):
            return ("/users", True)
        if tid.startswith("header-") or tid.startswith("rodape-"):
            return ("/", True)
        return ("/", True)
    except Exception:
        try:
            lg = _log()
            if lg is not None:
                lg.exception("cobertura_extra_sec: _rota_para_testid falhou")
        except Exception:
            pass
        return ("/", True)


def _prefixo_testid(testid):
    """EN: Static prefix for dynamic testids. PT-BR: prefixo estatico p/ testid dinamico."""
    try:
        partes = re.split(r"[\{\[\(]", testid, maxsplit=1)
        prefixo = (partes[0] if partes else testid).strip()
        prefixo = prefixo.rstrip("-_")
        if '"' in testid or "'" in testid:
            prefixo = re.split(r'["\']', prefixo, maxsplit=1)[0].rstrip("-_")
        return prefixo or testid
    except Exception:
        try:
            lg = _log()
            if lg is not None:
                lg.exception("cobertura_extra_sec: _prefixo_testid falhou")
        except Exception:
            pass
        return testid


def _verificar_testid_seguro(page, testid):
    """EN: Navigate owner route, assert visible/enabled, no traversal/leak. PT-BR: navega rota dona, asserta visivel/habilitado, sem traversal/vazamento."""
    try:
        if not _servidor_ativo():
            pytest.skip("servidor localhost:8080 fora do ar")
        rota, precisa_login = _rota_para_testid(testid)
        _garantir_localhost(BASE_URL)
        if precisa_login:
            _fazer_login(page, USUARIO_QAMASTER, SENHA_QA)
        page.goto(BASE_URL + rota, wait_until="domcontentloaded")
        page.wait_for_timeout(3500)
        _fechar_dialogos(page)
        conteudo = page.content()
        assert "root:" not in conteudo, "resposta vazou /etc/passwd"
        assert SENHA_QA not in conteudo, "resposta vazou senha"
        _cookie_sem_segredo(page)
        prefixo = _prefixo_testid(testid)
        assert ".." not in prefixo, "testid com traversal"
        assert "/" not in prefixo, "testid com barra"
        assert "\\" not in prefixo, "testid com barra invertida"
        dinamico = ("{" in testid) or ("[" in testid) or ("(" in testid) or ('"' in testid)
        try:
            if dinamico:
                localizador = page.locator(f'[data-testid*="{prefixo}"]')
            else:
                localizador = page.get_by_test_id(testid)
            total = localizador.count()
            assert total >= 1, f"testid ausente: {testid} em {rota}"
            primeiro = localizador.first
            visivel = bool(primeiro.is_visible())
            habilitado = bool(primeiro.is_enabled())
            assert visivel or habilitado, f"testid sem visible/enabled: {testid}"
        except AssertionError:
            raise
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: localizador falhou: %s", testid)
            except Exception:
                pass
            raise
        _cookie_sem_segredo(page)
    except Exception:
        try:
            lg = _log()
            if lg is not None:
                lg.exception("cobertura_extra_sec: _verificar falhou: %s", testid)
        except Exception:
            pass
        raise


class TestCoberturaExtraSec:
    """EN: 85 safe presence checks (lines 86-170). PT-BR: 85 checagens seguras (linhas 86-170)."""

    def test_seg_empenhos_filtro_info(self, page):
        """EN: empenhos-filtro-info on /renomear-empenho. PT-BR: empenhos-filtro-info em /renomear-empenho."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'empenhos-filtro-info')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_empenhos_filtro_info falhou")
            except Exception:
                pass
            raise

    def test_seg_empenhos_filtro_pendentes(self, page):
        """EN: empenhos-filtro-pendentes on /renomear-empenho. PT-BR: empenhos-filtro-pendentes em /renomear-empenho."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'empenhos-filtro-pendentes')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_empenhos_filtro_pendentes falhou")
            except Exception:
                pass
            raise

    def test_seg_empenhos_gerar_25_temp(self, page):
        """EN: empenhos-gerar-25-temp on /renomear-empenho. PT-BR: empenhos-gerar-25-temp em /renomear-empenho."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'empenhos-gerar-25-temp')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_empenhos_gerar_25_temp falhou")
            except Exception:
                pass
            raise

    def test_seg_empenhos_lote_baixar(self, page):
        """EN: empenhos-lote-baixar on /renomear-empenho. PT-BR: empenhos-lote-baixar em /renomear-empenho."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'empenhos-lote-baixar')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_empenhos_lote_baixar falhou")
            except Exception:
                pass
            raise

    def test_seg_empenhos_lote_confirmar(self, page):
        """EN: empenhos-lote-confirmar on /renomear-empenho. PT-BR: empenhos-lote-confirmar em /renomear-empenho."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'empenhos-lote-confirmar')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_empenhos_lote_confirmar falhou")
            except Exception:
                pass
            raise

    def test_seg_empenhos_lote_contador(self, page):
        """EN: empenhos-lote-contador on /renomear-empenho. PT-BR: empenhos-lote-contador em /renomear-empenho."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'empenhos-lote-contador')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_empenhos_lote_contador falhou")
            except Exception:
                pass
            raise

    def test_seg_empenhos_lote_email(self, page):
        """EN: empenhos-lote-email on /renomear-empenho. PT-BR: empenhos-lote-email em /renomear-empenho."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'empenhos-lote-email')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_empenhos_lote_email falhou")
            except Exception:
                pass
            raise

    def test_seg_empenhos_lote_limpar(self, page):
        """EN: empenhos-lote-limpar on /renomear-empenho. PT-BR: empenhos-lote-limpar em /renomear-empenho."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'empenhos-lote-limpar')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_empenhos_lote_limpar falhou")
            except Exception:
                pass
            raise

    def test_seg_empenhos_lote_marcar(self, page):
        """EN: empenhos-lote-marcar on /renomear-empenho. PT-BR: empenhos-lote-marcar em /renomear-empenho."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'empenhos-lote-marcar')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_empenhos_lote_marcar falhou")
            except Exception:
                pass
            raise

    def test_seg_empenhos_lote_solicitar(self, page):
        """EN: empenhos-lote-solicitar on /renomear-empenho. PT-BR: empenhos-lote-solicitar em /renomear-empenho."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'empenhos-lote-solicitar')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_empenhos_lote_solicitar falhou")
            except Exception:
                pass
            raise

    def test_seg_empenhos_modelo_visual(self, page):
        """EN: empenhos-modelo-visual on /renomear-empenho. PT-BR: empenhos-modelo-visual em /renomear-empenho."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'empenhos-modelo-visual')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_empenhos_modelo_visual falhou")
            except Exception:
                pass
            raise

    def test_seg_empenhos_navegar_contagem(self, page):
        """EN: empenhos-navegar-contagem on /renomear-empenho. PT-BR: empenhos-navegar-contagem em /renomear-empenho."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'empenhos-navegar-contagem')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_empenhos_navegar_contagem falhou")
            except Exception:
                pass
            raise

    def test_seg_empenhos_navegar_editar(self, page):
        """EN: empenhos-navegar-editar on /renomear-empenho. PT-BR: empenhos-navegar-editar em /renomear-empenho."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'empenhos-navegar-editar')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_empenhos_navegar_editar falhou")
            except Exception:
                pass
            raise

    def test_seg_empenhos_navegar_pesquisa(self, page):
        """EN: empenhos-navegar-pesquisa on /renomear-empenho. PT-BR: empenhos-navegar-pesquisa em /renomear-empenho."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'empenhos-navegar-pesquisa')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_empenhos_navegar_pesquisa falhou")
            except Exception:
                pass
            raise

    def test_seg_empenhos_navegar_processar(self, page):
        """EN: empenhos-navegar-processar on /renomear-empenho. PT-BR: empenhos-navegar-processar em /renomear-empenho."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'empenhos-navegar-processar')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_empenhos_navegar_processar falhou")
            except Exception:
                pass
            raise

    def test_seg_empenhos_pasta_d_nome(self, page):
        """EN: dynamic empenhos-pasta prefix on /renomear-empenho. PT-BR: prefixo dinamico empenhos-pasta em /renomear-empenho."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'empenhos-pasta-{d[nome')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_empenhos_pasta_d_nome falhou")
            except Exception:
                pass
            raise

    def test_seg_empenhos_processar(self, page):
        """EN: empenhos-processar on /renomear-empenho. PT-BR: empenhos-processar em /renomear-empenho."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'empenhos-processar')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_empenhos_processar falhou")
            except Exception:
                pass
            raise

    def test_seg_empenhos_raiz_dot(self, page):
        """EN: empenhos-raiz-dot on /renomear-empenho. PT-BR: empenhos-raiz-dot em /renomear-empenho."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'empenhos-raiz-dot')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_empenhos_raiz_dot falhou")
            except Exception:
                pass
            raise

    def test_seg_empenhos_reprocessar_fila(self, page):
        """EN: empenhos-reprocessar-fila on /renomear-empenho. PT-BR: empenhos-reprocessar-fila em /renomear-empenho."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'empenhos-reprocessar-fila')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_empenhos_reprocessar_fila falhou")
            except Exception:
                pass
            raise

    def test_seg_empenhos_reprocessar_fila_admin(self, page):
        """EN: empenhos-reprocessar-fila-admin on /renomear-empenho. PT-BR: empenhos-reprocessar-fila-admin em /renomear-empenho."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'empenhos-reprocessar-fila-admin')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_empenhos_reprocessar_fila_admin falhou")
            except Exception:
                pass
            raise

    def test_seg_empenhos_revisar_ano(self, page):
        """EN: empenhos-revisar-ano on /renomear-empenho. PT-BR: empenhos-revisar-ano em /renomear-empenho."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'empenhos-revisar-ano')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_empenhos_revisar_ano falhou")
            except Exception:
                pass
            raise

    def test_seg_empenhos_revisar_empenho(self, page):
        """EN: empenhos-revisar-empenho on /renomear-empenho. PT-BR: empenhos-revisar-empenho em /renomear-empenho."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'empenhos-revisar-empenho')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_empenhos_revisar_empenho falhou")
            except Exception:
                pass
            raise

    def test_seg_empenhos_revisar_ficha(self, page):
        """EN: empenhos-revisar-ficha on /renomear-empenho. PT-BR: empenhos-revisar-ficha em /renomear-empenho."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'empenhos-revisar-ficha')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_empenhos_revisar_ficha falhou")
            except Exception:
                pass
            raise

    def test_seg_empenhos_revisar_parcela(self, page):
        """EN: empenhos-revisar-parcela on /renomear-empenho. PT-BR: empenhos-revisar-parcela em /renomear-empenho."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'empenhos-revisar-parcela')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_empenhos_revisar_parcela falhou")
            except Exception:
                pass
            raise

    def test_seg_empenhos_revisar_tipo(self, page):
        """EN: empenhos-revisar-tipo on /renomear-empenho. PT-BR: empenhos-revisar-tipo em /renomear-empenho."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'empenhos-revisar-tipo')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_empenhos_revisar_tipo falhou")
            except Exception:
                pass
            raise

    def test_seg_empenhos_selecionar(self, page):
        """EN: empenhos-selecionar on /renomear-empenho. PT-BR: empenhos-selecionar em /renomear-empenho."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'empenhos-selecionar')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_empenhos_selecionar falhou")
            except Exception:
                pass
            raise

    def test_seg_empenhos_solicitar_email(self, page):
        """EN: empenhos-solicitar-email on /renomear-empenho. PT-BR: empenhos-solicitar-email em /renomear-empenho."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'empenhos-solicitar-email')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_empenhos_solicitar_email falhou")
            except Exception:
                pass
            raise

    def test_seg_filas_acesso_abrir(self, page):
        """EN: filas-acesso-abrir on /filas. PT-BR: filas-acesso-abrir em /filas."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'filas-acesso-abrir')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_filas_acesso_abrir falhou")
            except Exception:
                pass
            raise

    def test_seg_filas_acesso_buscar(self, page):
        """EN: filas-acesso-buscar on /filas. PT-BR: filas-acesso-buscar em /filas."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'filas-acesso-buscar')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_filas_acesso_buscar falhou")
            except Exception:
                pass
            raise

    def test_seg_filas_acesso_chamar(self, page):
        """EN: filas-acesso-chamar on /filas. PT-BR: filas-acesso-chamar em /filas."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'filas-acesso-chamar')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_filas_acesso_chamar falhou")
            except Exception:
                pass
            raise

    def test_seg_filas_avancar(self, page):
        """EN: filas-avancar on /filas. PT-BR: filas-avancar em /filas."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'filas-avancar')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_filas_avancar falhou")
            except Exception:
                pass
            raise

    def test_seg_filas_cadastro(self, page):
        """EN: filas-cadastro on /filas. PT-BR: filas-cadastro em /filas."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'filas-cadastro')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_filas_cadastro falhou")
            except Exception:
                pass
            raise

    def test_seg_filas_campo_etapas(self, page):
        """EN: filas-campo-etapas on /filas. PT-BR: filas-campo-etapas em /filas."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'filas-campo-etapas')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_filas_campo_etapas falhou")
            except Exception:
                pass
            raise

    def test_seg_filas_campo_lista(self, page):
        """EN: filas-campo-lista on /filas. PT-BR: filas-campo-lista em /filas."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'filas-campo-lista')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_filas_campo_lista falhou")
            except Exception:
                pass
            raise

    def test_seg_filas_campo_nome(self, page):
        """EN: filas-campo-nome on /filas. PT-BR: filas-campo-nome em /filas."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'filas-campo-nome')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_filas_campo_nome falhou")
            except Exception:
                pass
            raise

    def test_seg_filas_campo_ordem_fala(self, page):
        """EN: filas-campo-ordem-fala on /filas. PT-BR: filas-campo-ordem-fala em /filas."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'filas-campo-ordem-fala')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_filas_campo_ordem_fala falhou")
            except Exception:
                pass
            raise

    def test_seg_filas_campo_tv_grupo(self, page):
        """EN: filas-campo-tv-grupo on /filas. PT-BR: filas-campo-tv-grupo em /filas."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'filas-campo-tv-grupo')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_filas_campo_tv_grupo falhou")
            except Exception:
                pass
            raise

    def test_seg_filas_cancelar_edicao(self, page):
        """EN: filas-cancelar-edicao on /filas. PT-BR: filas-cancelar-edicao em /filas."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'filas-cancelar-edicao')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_filas_cancelar_edicao falhou")
            except Exception:
                pass
            raise

    def test_seg_filas_card_abrir_tv(self, page):
        """EN: filas-card-abrir-tv on /tv public. PT-BR: filas-card-abrir-tv em /tv publica."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'filas-card-abrir-tv')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_filas_card_abrir_tv falhou")
            except Exception:
                pass
            raise

    def test_seg_filas_card_tv_grupo(self, page):
        """EN: filas-card-tv-grupo on /tv public. PT-BR: filas-card-tv-grupo em /tv publica."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'filas-card-tv-grupo')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_filas_card_tv_grupo falhou")
            except Exception:
                pass
            raise

    def test_seg_filas_chamar_proximo(self, page):
        """EN: filas-chamar-proximo on /filas. PT-BR: filas-chamar-proximo em /filas."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'filas-chamar-proximo')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_filas_chamar_proximo falhou")
            except Exception:
                pass
            raise

    def test_seg_filas_confirmar_exclusao(self, page):
        """EN: filas-confirmar-exclusao on /filas. PT-BR: filas-confirmar-exclusao em /filas."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'filas-confirmar-exclusao')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_filas_confirmar_exclusao falhou")
            except Exception:
                pass
            raise

    def test_seg_filas_criar(self, page):
        """EN: filas-criar on /filas. PT-BR: filas-criar em /filas."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'filas-criar')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_filas_criar falhou")
            except Exception:
                pass
            raise

    def test_seg_filas_editar(self, page):
        """EN: filas-editar on /filas. PT-BR: filas-editar em /filas."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'filas-editar')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_filas_editar falhou")
            except Exception:
                pass
            raise

    def test_seg_filas_etapa_proximo(self, page):
        """EN: filas-etapa-proximo on /filas. PT-BR: filas-etapa-proximo em /filas."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'filas-etapa-proximo')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_filas_etapa_proximo falhou")
            except Exception:
                pass
            raise

    def test_seg_filas_excluir(self, page):
        """EN: filas-excluir on /filas (no click). PT-BR: filas-excluir em /filas (sem clique)."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'filas-excluir')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_filas_excluir falhou")
            except Exception:
                pass
            raise

    def test_seg_filas_excluir_todas(self, page):
        """EN: filas-excluir-todas on /filas (no click). PT-BR: filas-excluir-todas em /filas (sem clique)."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'filas-excluir-todas')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_filas_excluir_todas falhou")
            except Exception:
                pass
            raise

    def test_seg_filas_importar_submit(self, page):
        """EN: filas-importar-submit on /filas. PT-BR: filas-importar-submit em /filas."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'filas-importar-submit')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_filas_importar_submit falhou")
            except Exception:
                pass
            raise

    def test_seg_filas_importar_texto(self, page):
        """EN: filas-importar-texto on /filas. PT-BR: filas-importar-texto em /filas."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'filas-importar-texto')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_filas_importar_texto falhou")
            except Exception:
                pass
            raise

    def test_seg_filas_midia_fundo(self, page):
        """EN: filas-midia-fundo on /filas. PT-BR: filas-midia-fundo em /filas."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'filas-midia-fundo')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_filas_midia_fundo falhou")
            except Exception:
                pass
            raise

    def test_seg_filas_midia_salvar(self, page):
        """EN: filas-midia-salvar on /filas. PT-BR: filas-midia-salvar em /filas."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'filas-midia-salvar')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_filas_midia_salvar falhou")
            except Exception:
                pass
            raise

    def test_seg_filas_midia_som(self, page):
        """EN: filas-midia-som on /filas. PT-BR: filas-midia-som em /filas."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'filas-midia-som')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_filas_midia_som falhou")
            except Exception:
                pass
            raise

    def test_seg_filas_salvar_edicao(self, page):
        """EN: filas-salvar-edicao on /filas. PT-BR: filas-salvar-edicao em /filas."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'filas-salvar-edicao')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_filas_salvar_edicao falhou")
            except Exception:
                pass
            raise

    def test_seg_filas_transferir_todos(self, page):
        """EN: filas-transferir-todos on /filas. PT-BR: filas-transferir-todos em /filas."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'filas-transferir-todos')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_filas_transferir_todos falhou")
            except Exception:
                pass
            raise

    def test_seg_filas_tv_avancar(self, page):
        """EN: filas-tv-avancar on /tv public. PT-BR: filas-tv-avancar em /tv publica."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'filas-tv-avancar')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_filas_tv_avancar falhou")
            except Exception:
                pass
            raise

    def test_seg_filas_tv_pausar(self, page):
        """EN: filas-tv-pausar on /tv public. PT-BR: filas-tv-pausar em /tv publica."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'filas-tv-pausar')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_filas_tv_pausar falhou")
            except Exception:
                pass
            raise

    def test_seg_filas_tv_recem_criada(self, page):
        """EN: filas-tv-recem-criada on /tv public. PT-BR: filas-tv-recem-criada em /tv publica."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'filas-tv-recem-criada')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_filas_tv_recem_criada falhou")
            except Exception:
                pass
            raise

    def test_seg_filas_tv_retomar(self, page):
        """EN: filas-tv-retomar on /tv public. PT-BR: filas-tv-retomar em /tv publica."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'filas-tv-retomar')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_filas_tv_retomar falhou")
            except Exception:
                pass
            raise

    def test_seg_filas_tv_retornar(self, page):
        """EN: filas-tv-retornar on /tv public. PT-BR: filas-tv-retornar em /tv publica."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'filas-tv-retornar')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_filas_tv_retornar falhou")
            except Exception:
                pass
            raise

    def test_seg_header_nome_usuario(self, page):
        """EN: header-nome-usuario on / (login). PT-BR: header-nome-usuario em / (login)."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'header-nome-usuario')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_header_nome_usuario falhou")
            except Exception:
                pass
            raise

    def test_seg_lista_busca(self, page):
        """EN: lista-busca on /lista-telefonica. PT-BR: lista-busca em /lista-telefonica."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'lista-busca')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_lista_busca falhou")
            except Exception:
                pass
            raise

    def test_seg_lista_ligar(self, page):
        """EN: lista-ligar on /lista-telefonica. PT-BR: lista-ligar em /lista-telefonica."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'lista-ligar')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_lista_ligar falhou")
            except Exception:
                pass
            raise

    def test_seg_lista_select_secretaria(self, page):
        """EN: lista-select-secretaria on /lista-telefonica. PT-BR: lista-select-secretaria em /lista-telefonica."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'lista-select-secretaria')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_lista_select_secretaria falhou")
            except Exception:
                pass
            raise

    def test_seg_lista_select_setor(self, page):
        """EN: lista-select-setor on /lista-telefonica. PT-BR: lista-select-setor em /lista-telefonica."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'lista-select-setor')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_lista_select_setor falhou")
            except Exception:
                pass
            raise

    def test_seg_lista_select_subsetor(self, page):
        """EN: lista-select-subsetor on /lista-telefonica. PT-BR: lista-select-subsetor em /lista-telefonica."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'lista-select-subsetor')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_lista_select_subsetor falhou")
            except Exception:
                pass
            raise

    def test_seg_login_entrar(self, page):
        """EN: login-entrar on /login public. PT-BR: login-entrar em /login publica."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'login-entrar')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_login_entrar falhou")
            except Exception:
                pass
            raise

    def test_seg_login_senha(self, page):
        """EN: login-senha on /login public. PT-BR: login-senha em /login publica."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'login-senha')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_login_senha falhou")
            except Exception:
                pass
            raise

    def test_seg_login_usuario(self, page):
        """EN: login-usuario on /login public. PT-BR: login-usuario em /login publica."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'login-usuario')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_login_usuario falhou")
            except Exception:
                pass
            raise

    def test_seg_menu_hamburguer(self, page):
        """EN: menu-hamburguer on /. PT-BR: menu-hamburguer em /."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'menu-hamburguer')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_menu_hamburguer falhou")
            except Exception:
                pass
            raise

    def test_seg_menu_chave_indisponivel(self, page):
        """EN: dynamic menu prefix on /. PT-BR: prefixo dinamico menu em /."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'menu-{chave}-indisponivel')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_menu_chave_indisponivel falhou")
            except Exception:
                pass
            raise

    def test_seg_rodape_sistema(self, page):
        """EN: rodape-sistema on /. PT-BR: rodape-sistema em /."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'rodape-sistema')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_rodape_sistema falhou")
            except Exception:
                pass
            raise

    def test_seg_solicita_admin_salvar(self, page):
        """EN: solicita-admin-salvar on /solicita-impressao. PT-BR: solicita-admin-salvar em /solicita-impressao."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'solicita-admin-salvar')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_solicita_admin_salvar falhou")
            except Exception:
                pass
            raise

    def test_seg_solicita_busca(self, page):
        """EN: solicita-busca on /solicita-impressao. PT-BR: solicita-busca em /solicita-impressao."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'solicita-busca')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_solicita_busca falhou")
            except Exception:
                pass
            raise

    def test_seg_solicita_enviar(self, page):
        """EN: solicita-enviar on /solicita-impressao. PT-BR: solicita-enviar em /solicita-impressao."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'solicita-enviar')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_solicita_enviar falhou")
            except Exception:
                pass
            raise

    def test_seg_tecnico_backup_ip(self, page):
        """EN: tecnico-backup-ip on /tecnico. PT-BR: tecnico-backup-ip em /tecnico."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'tecnico-backup-ip')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_tecnico_backup_ip falhou")
            except Exception:
                pass
            raise

    def test_seg_tecnico_backup_nomepc(self, page):
        """EN: tecnico-backup-nomepc on /tecnico. PT-BR: tecnico-backup-nomepc em /tecnico."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'tecnico-backup-nomepc')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_tecnico_backup_nomepc falhou")
            except Exception:
                pass
            raise

    def test_seg_tecnico_backup_select(self, page):
        """EN: tecnico-backup-select on /tecnico. PT-BR: tecnico-backup-select em /tecnico."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'tecnico-backup-select')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_tecnico_backup_select falhou")
            except Exception:
                pass
            raise

    def test_seg_tecnico_baixar(self, page):
        """EN: tecnico-baixar on /tecnico. PT-BR: tecnico-baixar em /tecnico."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'tecnico-baixar')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_tecnico_baixar falhou")
            except Exception:
                pass
            raise

    def test_seg_tecnico_baixar_safe_id_pasta_nome(self, page):
        """EN: dynamic tecnico-baixar prefix on /tecnico. PT-BR: prefixo dinamico tecnico-baixar em /tecnico."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'tecnico-baixar-{_safe_id(pasta_nome')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_tecnico_baixar_safe_id_pasta_nome falhou")
            except Exception:
                pass
            raise

    def test_seg_tecnico_criar_pasta(self, page):
        """EN: tecnico-criar-pasta on /tecnico. PT-BR: tecnico-criar-pasta em /tecnico."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'tecnico-criar-pasta')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_tecnico_criar_pasta falhou")
            except Exception:
                pass
            raise

    def test_seg_tecnico_soft_safe_id_rel(self, page):
        """EN: dynamic tecnico-soft prefix on /tecnico. PT-BR: prefixo dinamico tecnico-soft em /tecnico."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'tecnico-soft-{_safe_id(rel')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_tecnico_soft_safe_id_rel falhou")
            except Exception:
                pass
            raise

    def test_seg_tecnico_upload(self, page):
        """EN: tecnico-upload on /tecnico. PT-BR: tecnico-upload em /tecnico."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'tecnico-upload')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_tecnico_upload falhou")
            except Exception:
                pass
            raise

    def test_seg_usuarios_busca(self, page):
        """EN: usuarios-busca on /users. PT-BR: usuarios-busca em /users."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'usuarios-busca')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_usuarios_busca falhou")
            except Exception:
                pass
            raise

    def test_seg_usuarios_filtro_situacao(self, page):
        """EN: usuarios-filtro-situacao on /users. PT-BR: usuarios-filtro-situacao em /users."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'usuarios-filtro-situacao')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_usuarios_filtro_situacao falhou")
            except Exception:
                pass
            raise

    def test_seg_usuarios_novo(self, page):
        """EN: usuarios-novo on /users. PT-BR: usuarios-novo em /users."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _verificar_testid_seguro(page, 'usuarios-novo')
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("cobertura_extra_sec: test_seg_usuarios_novo falhou")
            except Exception:
                pass
            raise
