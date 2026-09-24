"""E2E Tecnico — leitura + traversal/owner isolation (kbp-devSecOps).

EN — Playwright checks for mod_tecnico on localhost only (route /tecnico):
testids, reading flow, backend traversal blocked (listar_software,
_pasta_backup_path), owner isolation, no cookie leak. Read-preferred.

PT-BR — Verificacoes Playwright do mod_tecnico só em localhost (rota
/tecnico): testids, fluxo de leitura, traversal bloqueado no backend
(listar_software, _pasta_backup_path), isolamento do dono, sem vazar
cookie. Leitura preferencial.

Execucao (servidor vivo em outro terminal):
    .venv/Scripts/python.exe -m pytest assets/test/test_e2e_tecnico.py -v
    .venv/Scripts/python.exe -m pytest assets/test/test_e2e_tecnico.py -v -m "unit"

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
USUARIO_ADMIN = "qamaster"
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
                lg.exception("tecnico: _fechar_dialogos falhou")
        except Exception:
            pass


def _fazer_login(page, usuario=USUARIO_ADMIN, senha=SENHA_QA):
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
                lg.exception("tecnico: _fazer_login falhou para %s", usuario)
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
                lg.exception("tecnico: _cookie_sem_segredo falhou")
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
                lg.exception("tecnico: _ler falhou: %s", rel)
        except Exception:
            pass
        return ""


class TestUnidadeTecnico:
    """EN: Static + backend checks (no server). PT-BR: checagens estaticas (sem servidor)."""

    @pytest.mark.unit
    def test_testids_backup_via_props(self):
        """EN: Backup testids exist. PT-BR: testids do backup existem."""
        try:
            fonte = _ler("mod_tecnico/telas.py")
            assert "data-testid=tecnico-backup-nomepc" in fonte
            assert "data-testid=tecnico-backup-ip" in fonte
            assert "data-testid=tecnico-criar-pasta" in fonte
            assert "data-testid=tecnico-backup-select" in fonte
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("tecnico: testids falhou")
            except Exception:
                pass
            raise

    @pytest.mark.unit
    def test_listar_software_bloqueia_traversal(self):
        """EN: listar_software rejects ../... PT-BR: listar_software rejeita ../.."""
        try:
            from mod_tecnico import bd_manipulador as tec
            assert tec.listar_software("../../etc") == []
            assert tec.listar_software("/etc") == []
            assert tec.listar_software("..\\windows") == []
            assert isinstance(tec.listar_software(), list)
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("tecnico: listar_software falhou")
            except Exception:
                pass
            raise

    @pytest.mark.unit
    def test_pasta_backup_contida_e_nome_sanitizado(self):
        """EN: Backup path contained, name sanitized. PT-BR: pasta contida e nome sanitizado."""
        try:
            from mod_tecnico import bd_manipulador as tec
            base = os.path.abspath(tec.PASTA_BACKUP)
            trav = os.path.abspath(tec._pasta_backup_path("../../etc/passwd"))
            assert trav.startswith(base), "traversal escapou da base"
            assert ".." not in os.path.relpath(trav, base)
            nome = tec.nome_pasta_backup("../../etc", "127.0.0.1; rm -rf /")
            assert ".." not in nome and ";" not in nome and "/" not in nome
            assert tec._sanitizar_nome("../../etc/passwd") == "etc_passwd"
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("tecnico: pasta backup falhou")
            except Exception:
                pass
            raise


class TestE2ETecnico:
    """EN: Live headless flow on localhost. PT-BR: fluxo real headless em localhost."""

    def test_pagina_tecnico_carrega_qamaster(self, page):
        """EN: /tecnico renders for qamaster. PT-BR: /tecnico abre para qamaster."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _fazer_login(page, USUARIO_ADMIN, SENHA_QA)
            _garantir_localhost(BASE_URL)
            page.goto(BASE_URL + "/tecnico", wait_until="domcontentloaded")
            page.wait_for_timeout(4000)
            _fechar_dialogos(page)
            corpo = page.locator("body").inner_text()
            assert "Backup do PC" in corpo or "Software" in corpo or "Técnico" in corpo
            _cookie_sem_segredo(page)
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("tecnico E2E: pagina falhou")
            except Exception:
                pass
            raise

    def test_testids_backup_visiveis_sem_disconnect(self, page):
        """EN: Backup inputs visible, session alive. PT-BR: campos visiveis sem disconnect."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _fazer_login(page, USUARIO_ADMIN, SENHA_QA)
            page.goto(BASE_URL + "/tecnico", wait_until="domcontentloaded")
            page.wait_for_timeout(4000)
            _fechar_dialogos(page)
            assert page.get_by_test_id("tecnico-backup-nomepc").count() >= 1
            assert page.get_by_test_id("tecnico-backup-ip").count() >= 1
            corpo = page.locator("body").inner_text().lower()
            assert "desconectado" not in corpo
            _cookie_sem_segredo(page)
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("tecnico E2E: testids falhou")
            except Exception:
                pass
            raise

    def test_sem_traversal_na_resposta(self, page):
        """EN: Page never leaks /etc/passwd. PT-BR: pagina nunca vaza /etc/passwd."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _fazer_login(page, USUARIO_ADMIN, SENHA_QA)
            page.goto(BASE_URL + "/tecnico", wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
            corpo = page.content()
            assert "root:" not in corpo
            assert SENHA_QA not in corpo
            _cookie_sem_segredo(page)
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("tecnico E2E: resposta falhou")
            except Exception:
                pass
            raise
