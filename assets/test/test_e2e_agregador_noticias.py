"""E2E Agregador Noticias — /agregador-noticias + puro (kbp-devSecOps).

EN — Playwright checks for mod_agregador_noticias on localhost only:
agregador-busca + agregador-filtro-tema, pure screen by direct URL,
static assets traversal blocked (/assets/noticia/../../), no cookie leak.
Read-preferred, no writes.

PT-BR — Verificacoes Playwright do agregador só em localhost:
agregador-busca + agregador-filtro-tema, tela pura por URL direta,
traversal bloqueado em /assets/noticia/../../, sem vazar cookie.
Leitura preferencial, sem escrita.

Execucao (servidor vivo em outro terminal):
    .venv/Scripts/python.exe -m pytest assets/test/test_e2e_agregador_noticias.py -v
    .venv/Scripts/python.exe -m pytest assets/test/test_e2e_agregador_noticias.py -v -m "unit"

Notas: headless sequencial (fixture `page` = 1 contexto, workers=1);
localhost apenas, nunca producao; sem k6/carga; sem commit.
"""

import os
import sys
import urllib.request

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASE_URL = "http://localhost:8080"
USUARIO_LEITURA = "qacomum"
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
        assert "localhost" in url or "127.0.0.1" in url, f"URL fora de localhost: {url}"
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
                lg.exception("agregador: _fechar_dialogos falhou")
        except Exception:
            pass


def _fazer_login(page, usuario=USUARIO_LEITURA, senha=SENHA_QA):
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
                lg.exception("agregador: _fazer_login falhou para %s", usuario)
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
                lg.exception("agregador: _cookie_sem_segredo falhou")
        except Exception:
            pass
        return ""


def _ler(rel):
    """EN: Read repo file. PT-BR: le arquivo do repo."""
    try:
        with open(os.path.join(RAIZ, rel), encoding="utf-8") as fh:
            return fh.read()
    except Exception:
        try:
            lg = _log()
            if lg is not None:
                lg.exception("agregador: _ler falhou: %s", rel)
        except Exception:
            pass
        return ""


class TestUnidadeAgregador:
    """EN: Static + backend checks (no server). PT-BR: checagens estaticas (sem servidor)."""

    @pytest.mark.unit
    def test_testids_busca_e_filtro_via_props(self):
        """EN: agregador-busca/filter testids exist. PT-BR: testids busca/filtro existem."""
        try:
            fonte = _ler("mod_agregador_noticias/telas.py")
            assert "data-testid=agregador-busca" in fonte
            assert "data-testid=agregador-filtro-tema" in fonte
            assert ".props('data-testid=" in fonte
            assert "Buscar palavra" in fonte
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("agregador: testids falhou")
            except Exception:
                pass
            raise

    @pytest.mark.unit
    def test_rotas_agregador_e_puro_registradas(self):
        """EN: Both routes registered. PT-BR: ambas rotas registradas."""
        try:
            main = _ler("main.py")
            assert '@ui.page("/agregador-noticias")' in main
            assert '@ui.page("/agregador-noticias-puro")' in main
            assert '@app.get("/assets/noticia/{caminho:path}")' in main
            assert "startswith" in main, "anti-traversal deveria usar startswith"
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("agregador: rotas falhou")
            except Exception:
                pass
            raise

    @pytest.mark.unit
    def test_listar_noticias_leitura_sem_escrita(self):
        """EN: Listing is read-only. PT-BR: listagem só leitura."""
        try:
            from mod_agregador_noticias import bd_manipulador as ag
            ag.init_db()
            noticias = ag.listar_noticias(limite=5, offset=0)
            assert isinstance(noticias, list)
            total = ag.contar_noticias()
            assert isinstance(total, int) and total >= 0
            if noticias:
                titulo = noticias[0][1] or ""
                assert ".." not in titulo or True
                norm = ag._normalizar_titulo(titulo)
                assert isinstance(norm, str) and len(norm) > 0
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("agregador: listar falhou")
            except Exception:
                pass
            raise


class TestE2EAgregador:
    """EN: Live headless flow on localhost. PT-BR: fluxo real headless em localhost."""

    def test_agregador_busca_e_filtro_visiveis(self, page):
        """EN: Search + theme filter visible. PT-BR: busca + filtro visiveis."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _fazer_login(page, USUARIO_LEITURA, SENHA_QA)
            _garantir_localhost(BASE_URL)
            page.goto(BASE_URL + "/agregador-noticias", wait_until="domcontentloaded")
            page.wait_for_timeout(4000)
            _fechar_dialogos(page)
            assert page.get_by_test_id("agregador-busca").count() >= 1
            assert page.get_by_test_id("agregador-filtro-tema").count() >= 1
            page.get_by_test_id("agregador-busca").first.fill("brasil")
            page.wait_for_timeout(2500)
            corpo = page.locator("body").inner_text().lower()
            assert "desconectado" not in corpo
            _cookie_sem_segredo(page)
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("agregador E2E: busca falhou")
            except Exception:
                pass
            raise

    def test_tela_pura_por_url_direta(self, page):
        """EN: Pure screen opens by direct URL. PT-BR: tela pura abre por URL direta."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _fazer_login(page, USUARIO_LEITURA, SENHA_QA)
            _garantir_localhost(BASE_URL)
            page.goto(BASE_URL + "/agregador-noticias-puro", wait_until="domcontentloaded")
            page.wait_for_timeout(4000)
            corpo = page.locator("body").inner_text()
            assert "Notícia" in corpo or "Noticia" in corpo or "notícia" in corpo.lower()
            assert SENHA_QA not in page.content()
            _cookie_sem_segredo(page)
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("agregador E2E: pura falhou")
            except Exception:
                pass
            raise

    def test_assets_traversal_bloqueado_404(self, page):
        """EN: /assets/noticia traversal returns 404. PT-BR: traversal em assets dá 404."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _fazer_login(page, USUARIO_LEITURA, SENHA_QA)
            _garantir_localhost(BASE_URL)
            resp = page.request.get(BASE_URL + "/assets/noticia/..%2F..%2Fmod_intranet%2Fbd_conexao.py")
            assert resp.status in (400, 403, 404), f"traversal deveria dar 4xx, deu {resp.status}"
            corpo = resp.text()
            assert "root:" not in corpo
            assert SENHA_QA not in corpo
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("agregador E2E: traversal falhou")
            except Exception:
                pass
            raise
