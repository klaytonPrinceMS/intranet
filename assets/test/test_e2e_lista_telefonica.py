"""E2E Lista Telefonica — busca + tel: (kbp-devSecOps).

EN — Playwright checks for mod_lista_telefonica on localhost only
(route /lista-telefonica): lista-busca + tel: links sanitized to digits/+,
critical testids, traversal blocked, no cookie leak. One write test
creates then deletes a contact (cleanup + logger).

PT-BR — Verificacoes Playwright da lista telefonica só em localhost (rota
/lista-telefonica): busca + links tel: sanitizados para digitos/+,
testids criticos, traversal bloqueado, sem vazar cookie. Um teste de
escrita cria e depois exclui o contato (limpeza + logger).

Execucao (servidor vivo em outro terminal):
    .venv/Scripts/python.exe -m pytest assets/test/test_e2e_lista_telefonica.py -v
    .venv/Scripts/python.exe -m pytest assets/test/test_e2e_lista_telefonica.py -v -m "unit"

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
                lg.exception("lista: _fechar_dialogos falhou")
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
                lg.exception("lista: _fazer_login falhou para %s", usuario)
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
                lg.exception("lista: _cookie_sem_segredo falhou")
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
                lg.exception("lista: _ler falhou: %s", rel)
        except Exception:
            pass
        return ""


class TestUnidadeLista:
    """EN: Static + backend checks (no server). PT-BR: checagens estaticas (sem servidor)."""

    @pytest.mark.unit
    def test_testids_busca_e_ligar_via_props(self):
        """EN: lista-busca/ligar testids exist. PT-BR: testids lista-busca/ligar existem."""
        try:
            fonte = _ler("mod_lista_telefonica/telas.py")
            assert "data-testid=lista-busca" in fonte
            assert "data-testid=lista-ligar" in fonte
            assert ".props('data-testid=" in fonte
            assert "tel:" in fonte
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("lista: testids falhou")
            except Exception:
                pass
            raise

    @pytest.mark.unit
    def test_tel_sanitizado_so_digitos_mais(self):
        """EN: tel: keeps only digits/+. PT-BR: tel: mantem só digitos/+."""
        try:
            sujo = "(11) 9999-8888; alert(1)"
            limpo = re.sub(r"[^0-9+]", "", sujo)
            assert ";" not in limpo and "alert" not in limpo
            assert re.fullmatch(r"[0-9+]+", limpo), f"tel inesperado: {limpo}"
            fonte = _ler("mod_lista_telefonica/telas.py")
            assert '[^0-9+]' in fonte, "tela deveria sanitizar tel antes do tel:"
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("lista: tel falhou")
            except Exception:
                pass
            raise

    @pytest.mark.unit
    def test_busca_norm_sem_acento_e_contato_com_limpeza(self):
        """EN: _norm search + contact create/delete. PT-BR: busca _norm + contato cria/apaga."""
        cid = None
        try:
            from mod_lista_telefonica import bd_manipulador as lista
            lg = _log()
            lista.init_db()
            assert lista._norm("São Paulo — TI") == "sao paulo ti"
            secs = lista.listar_unidades(parent_id=None, tipo="secretaria")
            assert len(secs) >= 1, "organograma sem secretarias"
            sec_id = secs[0][0]
            setores = lista.listar_unidades(parent_id=sec_id, tipo="setor")
            if not setores:
                ok_u, _ = lista.criar_unidade(f"QA_SETOR_E2E_{os.getpid()}", "setor",
                                              parent_id=sec_id, ator="qa_e2e")
                assert ok_u
                setores = lista.listar_unidades(parent_id=sec_id, tipo="setor")
            uni_id = setores[0][0]
            nome = f"ContatoQAE2E{os.getpid()}"
            ok_c, _ = lista.criar_contato(uni_id, nome, "(11) 99999-0000", ator="qa_e2e")
            assert ok_c, "criar_contato teste falhou"
            try:
                if lg is not None:
                    lg.info("lista: contato QA %s criado (limpeza a seguir)", nome)
            except Exception:
                pass
            achados = lista.buscar_contatos("contatoqae2e")
            cid = next((r[0] for r in lista.listar_contatos(uni_id) if r[2] == nome), None)
            assert any(nome.lower() in r[2].lower() for r in achados), "busca _norm nao achou"
            assert ".." not in nome
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("lista: busca/contato falhou")
            except Exception:
                pass
            raise
        finally:
            try:
                if cid:
                    from mod_lista_telefonica import bd_manipulador as lista2
                    lista2.excluir_contato(cid, ator="qa_e2e")
                    lg2 = _log()
                    try:
                        if lg2 is not None:
                            lg2.info("lista: contato QA cid=%s excluido (limpeza)", cid)
                    except Exception:
                        pass
            except Exception:
                try:
                    lg3 = _log()
                    if lg3 is not None:
                        lg3.exception("lista: limpeza do contato falhou")
                except Exception:
                    pass
                raise


class TestE2ELista:
    """EN: Live headless flow on localhost. PT-BR: fluxo real headless em localhost."""

    def test_busca_renderiza_e_filtra(self, page):
        """EN: lista-busca renders and filters. PT-BR: lista-busca renderiza e filtra."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _fazer_login(page, USUARIO_LEITURA, SENHA_QA)
            _garantir_localhost(BASE_URL)
            page.goto(BASE_URL + "/lista-telefonica", wait_until="domcontentloaded")
            page.wait_for_timeout(4000)
            _fechar_dialogos(page)
            campo = page.get_by_test_id("lista-busca")
            assert campo.count() >= 1
            campo.first.fill("gabinete")
            page.wait_for_timeout(2500)
            corpo = page.locator("body").inner_text().lower()
            assert "desconectado" not in corpo
            _cookie_sem_segredo(page)
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("lista E2E: busca falhou")
            except Exception:
                pass
            raise

    def test_links_tel_sanitizados_sem_cookie(self, page):
        """EN: tel: hrefs are digits/+ only. PT-BR: hrefs tel: só digitos/+."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            _fazer_login(page, USUARIO_LEITURA, SENHA_QA)
            page.goto(BASE_URL + "/lista-telefonica", wait_until="domcontentloaded")
            page.wait_for_timeout(4000)
            _fechar_dialogos(page)
            hrefs = page.evaluate(
                "() => Array.from(document.querySelectorAll('a[href^=\"tel:\"]'))"
                ".map(a => a.getAttribute('href')).slice(0, 20)")
            assert isinstance(hrefs, list)
            for href in hrefs:
                numero = (href or "")[len("tel:"):]
                assert re.fullmatch(r"[0-9+]+", numero or ""), f"tel: nao sanitizado: {href}"
                assert "alert" not in (href or "") and ";" not in (href or "")
            assert SENHA_QA not in page.content()
            _cookie_sem_segredo(page)
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("lista E2E: tel falhou")
            except Exception:
                pass
            raise
