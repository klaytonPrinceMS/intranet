"""E2E Filas — /filas + /tv publica sem login (kbp-devSecOps).

EN — Playwright checks for mod_filas on localhost only: /filas (login),
/tv public without login, critical filas-* testids, shared TV ?grupo=,
traversal blocked, no cookie leak. Read-preferred.

PT-BR — Verificacoes Playwright do mod_filas só em localhost: /filas (com
login), /tv pública sem login, testids filas-* criticos, TV compartilhada
?grupo=, traversal bloqueado, sem vazar cookie. Leitura preferencial.

Execucao (servidor vivo em outro terminal):
    .venv/Scripts/python.exe -m pytest assets/test/test_e2e_filas.py -v
    .venv/Scripts/python.exe -m pytest assets/test/test_e2e_filas.py -v -m "unit"

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
                lg.exception("filas: _fechar_dialogos falhou")
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
                lg.exception("filas: _fazer_login falhou para %s", usuario)
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
                lg.exception("filas: _cookie_sem_segredo falhou")
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
                lg.exception("filas: _ler falhou: %s", rel)
        except Exception:
            pass
        return ""


class TestUnidadeFilas:
    """EN: Static + backend checks (no server). PT-BR: checagens estaticas (sem servidor)."""

    @pytest.mark.unit
    def test_testids_criticos_via_props(self):
        """EN: Critical filas-* testids exist. PT-BR: testids filas-* criticos existem."""
        try:
            fonte = _ler("mod_filas/telas.py")
            for tid in ("filas-cadastro", "filas-criar", "filas-chamar-proximo",
                        "filas-avancar", "filas-excluir-todas", "filas-tv-pausar",
                        "filas-acesso-buscar", "filas-midia-salvar"):
                assert f"data-testid={tid}" in fonte, f"testid ausente: {tid}"
            assert ".props('data-testid=" in fonte
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("filas: testids falhou")
            except Exception:
                pass
            raise

    @pytest.mark.unit
    def test_tv_grupo_slug_e_traversal_bloqueado(self):
        """EN: tv_grupo slug rejects traversal. PT-BR: tv_grupo rejeita traversal."""
        try:
            from mod_filas import bd_manipulador as filas
            ok, slug = filas.normalizar_tv_grupo("Ambulatório Geral")
            assert ok and slug == "ambulatorio-geral"
            ok2, slug2 = filas.normalizar_tv_grupo("../../etc")
            assert ".." not in slug2 and "/" not in slug2, f"slug deveria neutralizar: {slug2!r}"
            assert slug2 == "etc", f"traversal neutralizado para slug seguro: {slug2!r}"
            ok3, _ = filas.normalizar_tv_grupo("!!!")
            assert not ok3
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("filas: tv_grupo falhou")
            except Exception:
                pass
            raise

    @pytest.mark.unit
    def test_csv_para_tags_nao_executa_traversal(self):
        """EN: csv_para_tags stays data-only. PT-BR: csv_para_tags só dados."""
        try:
            from mod_filas import bd_manipulador as filas
            assert filas.csv_para_tags("Maria\nJoão") is None
            saida = filas.csv_para_tags("nome;grupo\nMaria;gestante")
            assert saida == "Maria #gestante", f"conversao inesperada: {saida!r}"
            assert ".." not in (saida or "")
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("filas: csv tags falhou")
            except Exception:
                pass
            raise


class TestE2EFilas:
    """EN: Live headless flow on localhost. PT-BR: fluxo real headless em localhost."""

    def test_filas_carrega_qacomum(self, page):
        """EN: /filas renders for qacomum. PT-BR: /filas abre para qacomum."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _fazer_login(page, USUARIO_LEITURA, SENHA_QA)
            _garantir_localhost(BASE_URL)
            page.goto(BASE_URL + "/filas", wait_until="domcontentloaded")
            page.wait_for_timeout(4000)
            _fechar_dialogos(page)
            corpo = page.locator("body").inner_text()
            assert "Fila" in corpo or "fila" in corpo
            _cookie_sem_segredo(page)
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("filas E2E: /filas falhou")
            except Exception:
                pass
            raise

    def test_tv_publica_sem_login(self, page):
        """EN: /tv renders without login. PT-BR: /tv abre sem login (publica)."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _garantir_localhost(BASE_URL)
            page.goto(BASE_URL + "/tv", wait_until="domcontentloaded")
            page.wait_for_timeout(4000)
            url = page.url
            assert "/login" not in url, f"/tv nao deveria exigir login, foi para {url}"
            corpo = page.content()
            assert "root:" not in corpo
            assert SENHA_QA not in corpo
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("filas E2E: /tv publica falhou")
            except Exception:
                pass
            raise

    def test_tv_grupo_traversal_bloqueado(self, page):
        """EN: /tv?grupo= traversal is contained. PT-BR: /tv?grupo= traversal contido."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _garantir_localhost(BASE_URL)
            page.goto(BASE_URL + "/tv?grupo=..%2F..%2Fetc", wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
            corpo = page.content()
            assert "root:" not in corpo, "traversal vazou /etc/passwd"
            assert SENHA_QA not in corpo
            _cookie_sem_segredo(page)
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("filas E2E: traversal falhou")
            except Exception:
                pass
            raise
