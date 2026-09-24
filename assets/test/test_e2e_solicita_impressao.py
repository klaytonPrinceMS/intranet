"""E2E Solicita Impressao — leitura + rascunho com limpeza (kbp-devSecOps).

EN — Playwright checks for mod_solicita_impressao on localhost only
(route /solicita-impressao): testids, reading flow without disconnect,
traversal blocked on /solicita-impressao/pdf/{id}, no cookie leak.
Writes are limited to a draft (rascunho) that is always cancelled.

PT-BR — Verificacoes Playwright do mod_solicita_impressao só em localhost
(rota /solicita-impressao): testids, fluxo de leitura sem disconnect,
traversal bloqueado em /solicita-impressao/pdf/{id}, sem vazar cookie.
Escrita limitada a rascunho sempre cancelado depois (com logger).

Execucao (servidor vivo em outro terminal):
    .venv/Scripts/python.exe -m pytest assets/test/test_e2e_solicita_impressao.py -v
    .venv/Scripts/python.exe -m pytest assets/test/test_e2e_solicita_impressao.py -v -m "unit"
    .venv/Scripts/python.exe -m pytest assets/test/test_e2e_solicita_impressao.py -v -m "e2e"

Notas: headless sequencial (fixture `page` = 1 contexto, workers=1);
localhost apenas, nunca producao; sem k6/carga; sem commit.
"""

import os
import re
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
                lg.exception("solicita: _fechar_dialogos falhou")
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
                lg.exception("solicita: _fazer_login falhou para %s", usuario)
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
                lg.exception("solicita: _cookie_sem_segredo falhou")
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
                lg.exception("solicita: _ler falhou: %s", rel)
        except Exception:
            pass
        return ""


class TestUnidadeSolicita:
    """EN: Static + backend checks (no server). PT-BR: checagens estaticas (sem servidor)."""

    @pytest.mark.unit
    def test_testids_enviar_e_busca_via_props(self):
        """EN: Key testids exist. PT-BR: testids principais existem."""
        try:
            fonte = _ler("mod_solicita_impressao/telas.py")
            assert "data-testid=solicita-enviar" in fonte
            assert "data-testid=solicita-busca" in fonte
            assert ".props('data-testid=" in fonte or '.props("data-testid=' in fonte
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("solicita: testids falhou")
            except Exception:
                pass
            raise

    @pytest.mark.unit
    def test_sanitizar_nome_bloqueia_traversal(self):
        """EN: _sanitizar_nome blocks ../... PT-BR: _sanitizar_nome bloqueia ../.."""
        try:
            from mod_solicita_impressao import bd_manipulador as bd
            assert callable(getattr(bd, "_sanitizar_nome", None))
            limpo = bd._sanitizar_nome("../../etc/passwd")
            assert ".." not in limpo and "/" not in limpo
            limpo2 = bd._sanitizar_nome("meu_doc.pdf")
            assert limpo2 and ".." not in limpo2
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("solicita: sanitizar falhou")
            except Exception:
                pass
            raise

    @pytest.mark.unit
    def test_rascunho_cria_e_limpa_com_logger(self):
        """EN: Draft is created then cancelled (cleanup). PT-BR: rascunho criado e cancelado."""
        rid = None
        caminho = ""
        try:
            from mod_solicita_impressao import bd_manipulador as bd
            lg = _log()
            try:
                import fitz as _fitz
                _doc = _fitz.open()
                _pg = _doc.new_page()
                _pg.insert_text((72, 72), "rascunho QA devsecops")
                pdf = _doc.tobytes()
                _doc.close()
            except Exception:
                pdf = None
            assert pdf, "PyMuPDF indisponivel para gerar PDF de teste"
            rid, nome_serv, _pags, caminho = bd.registrar_rascunho("qacomum", pdf, "doc_teste.pdf")
            try:
                if lg is not None:
                    lg.info("solicita: rascunho QA criado rid=%s", rid)
            except Exception:
                pass
            assert rid, "rascunho nao criado"
            assert os.path.exists(caminho), "arquivo do rascunho nao existe"
            assert "doc_teste" not in (nome_serv or ""), "nome original nao deveria ser reusado"
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("solicita: rascunho falhou")
            except Exception:
                pass
            raise
        finally:
            try:
                if rid:
                    from mod_solicita_impressao import bd_manipulador as bd2
                    bd2.cancelar_rascunho(rid)
                    lg2 = _log()
                    try:
                        if lg2 is not None:
                            lg2.info("solicita: rascunho QA rid=%s cancelado (limpeza)", rid)
                    except Exception:
                        pass
                    assert not os.path.exists(caminho), "arquivo do rascunho deveria ser removido"
            except Exception:
                try:
                    lg3 = _log()
                    if lg3 is not None:
                        lg3.exception("solicita: limpeza do rascunho falhou")
                except Exception:
                    pass
                raise


class TestE2ESolicita:
    """EN: Live headless flow on localhost. PT-BR: fluxo real headless em localhost."""

    def test_pagina_carrega_leitura_qacomum(self, page):
        """EN: /solicita-impressao renders for qacomum. PT-BR: /solicita-impressao abre para qacomum."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _fazer_login(page, USUARIO_LEITURA, SENHA_QA)
            _garantir_localhost(BASE_URL)
            page.goto(BASE_URL + "/solicita-impressao", wait_until="domcontentloaded")
            page.wait_for_timeout(4000)
            _fechar_dialogos(page)
            assert page.get_by_test_id("solicita-busca").count() >= 1
            _cookie_sem_segredo(page)
        except Exception as exc:
            if isinstance(exc, pytest.skip.Exception if hasattr(pytest, "skip") else Exception):
                raise
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("solicita E2E: pagina falhou")
            except Exception:
                pass
            raise

    def test_busca_nao_desconecta(self, page):
        """EN: Search keeps session alive. PT-BR: busca mantem sessao sem disconnect."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _fazer_login(page, USUARIO_LEITURA, SENHA_QA)
            page.goto(BASE_URL + "/solicita-impressao", wait_until="domcontentloaded")
            page.wait_for_timeout(4000)
            _fechar_dialogos(page)
            campo = page.get_by_test_id("solicita-busca").first
            campo.fill("qacomum")
            page.wait_for_timeout(2500)
            corpo = page.locator("body").inner_text().lower()
            assert "desconectado" not in corpo
            _cookie_sem_segredo(page)
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("solicita E2E: busca falhou")
            except Exception:
                pass
            raise

    def test_traversal_pdf_bloqueado_sem_vazar_cookie(self, page):
        """EN: Traversal on pdf route is blocked. PT-BR: traversal no pdf e bloqueado."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _fazer_login(page, USUARIO_LEITURA, SENHA_QA)
            _garantir_localhost(BASE_URL)
            page.goto(BASE_URL + "/solicita-impressao/pdf/..%2F..%2Fetc%2Fpasswd", wait_until="domcontentloaded")
            page.wait_for_timeout(2500)
            corpo = page.content()
            assert "root:" not in corpo, "traversal vazou /etc/passwd"
            _cookie_sem_segredo(page)
            assert SENHA_QA not in corpo, "resposta vazou senha"
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("solicita E2E: traversal falhou")
            except Exception:
                pass
            raise
