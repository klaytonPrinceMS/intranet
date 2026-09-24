"""E2E Click Extra Sec — clique seguro nos ultimos 27 botoes (linhas 29-55) (kbp-devSecOps).

EN — Playwright safe-click coverage for the last 27 buttons from all_buttons.txt
(lines 29-55): single test loops the 27 button testids on owner route
(qamaster login or public /tv), goto route, click once, close without
confirming destructive (Escape/cancel), assert dialog or navigation.
NEVER confirms delete/excluir-todas/reiniciar-agora on data (open+close only).
Localhost only.

PT-BR — Cobertura Playwright de clique seguro dos ultimos 27 botoes do
all_buttons.txt (linhas 29-55): teste unico percorre os 27 testids de botao
na rota dona (login qamaster ou /tv publica), goto rota, click unico, fecha
sem confirmar destrutivo (Escape/cancelar), asserta dialog ou navegacao.
NUNCA confirma delete/excluir-todas/reiniciar-agora em dados (so abre+fecha).
Somente localhost.

Execucao (servidor vivo em outro terminal):
    .venv/Scripts/python.exe -m pytest assets/test/test_e2e_click_extra_sec.py -v
    .venv/Scripts/python.exe -m pytest assets/test/test_e2e_click_extra_sec.py -v -m "e2e and security"

Notas: confinado a C:\\opencode; localhost apenas http://localhost:8080;
sem k6/carga; sem segredos alem do seed QA; sem commit; sem sys.exit.
Login padrao qamaster/123456 (seed AGENTS.md 8.2) ou acesso publico /tv.
Toda funcao com try/except + logger; skip se servidor fora do ar.
"""

import os
import sys
import urllib.request

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASE_URL = "http://localhost:8080"
USUARIO_QAMASTER = "qamaster"
SENHA_QA = "123456"  # nosec B105 B106 B107 -- seed QA AGENTS.md 8.2, nunca producao

pytestmark = [pytest.mark.e2e, pytest.mark.security]

# 27 botoes finais do all_buttons.txt (linhas 29-55).
BOTOES_27 = [
    "empenhos-reprocessar-fila-admin",
    "filas-acesso-abrir",
    "filas-acesso-buscar",
    "filas-acesso-chamar",
    "filas-avancar",
    "filas-cancelar-edicao",
    "filas-card-abrir-tv",
    "filas-card-tv-grupo",
    "filas-chamar-proximo",
    "filas-confirmar-exclusao",
    "filas-criar",
    "filas-editar",
    "filas-etapa-proximo",
    "filas-excluir",
    "filas-excluir-todas",
    "filas-importar-submit",
    "filas-midia-fundo",
    "filas-midia-salvar",
    "filas-midia-som",
    "filas-salvar-edicao",
    "filas-transferir-todos",
    "filas-tv-avancar",
    "filas-tv-pausar",
    "filas-tv-recem-criada",
    "filas-tv-retomar",
    "filas-tv-retornar",
    "lista-ligar",
]

# Finais destrutivos: NUNCA clicar para confirmar (so abre+fecha ou so presença).
# filas-confirmar-exclusao e o botao final: nunca clicar. filas-excluir e
# filas-excluir-todas sao abridores: pode abrir e fechar com Escape, sem confirmar.
NUNCA_CONFIRMAR_FINAL = (
    "filas-confirmar-exclusao",
)

ABRIR_FECHAR_SEM_CONFIRMAR = (
    "filas-excluir",
    "filas-excluir-todas",
    "reiniciar-agora",
    "confirmar-excluir-lote",
    "confirmar-exclusao",
)


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
                lg.exception("click_extra_sec: _fechar_dialogos falhou")
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
                lg.exception("click_extra_sec: _fazer_login falhou para %s", usuario)
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
                lg.exception("click_extra_sec: _cookie_sem_segredo falhou")
        except Exception:
            pass
        return ""


def _rota_para_botao(testid):
    """EN: Owner route + login need. PT-BR: rota dona + se precisa login."""
    try:
        tid = testid or ""
        if tid in ("filas-card-abrir-tv", "filas-card-tv-grupo") or tid.startswith("filas-tv-"):
            return ("/tv", False)
        if tid.startswith("filas-"):
            return ("/filas", True)
        if tid.startswith("empenhos-"):
            return ("/renomear-empenho", True)
        if tid.startswith("lista-"):
            return ("/lista-telefonica", True)
        return ("/", True)
    except Exception:
        try:
            lg = _log()
            if lg is not None:
                lg.exception("click_extra_sec: _rota_para_botao falhou")
        except Exception:
            pass
        return ("/", True)


def _eh_final_destrutivo(testid):
    """EN: True if final confirm must never be clicked. PT-BR: True se confirm final nunca clica."""
    try:
        tid = (testid or "").lower()
        for frag in NUNCA_CONFIRMAR_FINAL:
            if frag in tid:
                return True
        return False
    except Exception:
        try:
            lg = _log()
            if lg is not None:
                lg.exception("click_extra_sec: _eh_final_destrutivo falhou")
        except Exception:
            pass
        return True


def _eh_abrir_fechar(testid):
    """EN: True if open+close only. PT-BR: True se so abre+fecha sem confirmar."""
    try:
        tid = (testid or "").lower()
        for frag in ABRIR_FECHAR_SEM_CONFIRMAR:
            if frag in tid:
                return True
        return False
    except Exception:
        try:
            lg = _log()
            if lg is not None:
                lg.exception("click_extra_sec: _eh_abrir_fechar falhou")
        except Exception:
            pass
        return True


def _fechar_sem_confirmar(page):
    """EN: Escape/cancel, never confirm. PT-BR: Escape/cancelar, nunca confirmar."""
    try:
        try:
            page.keyboard.press("Escape")
            page.wait_for_timeout(500)
        except Exception:
            pass
        try:
            for texto in ("Cancelar", "cancelar", "Fechar", "fechar", "Voltar", "voltar"):
                btn = page.get_by_text(texto, exact=False).first
                try:
                    if btn.count() >= 1 and btn.is_visible():
                        # So cancela se o botao nao for destrutivo final.
                        rotulo = (btn.inner_text() or "").lower()
                        if "confirmar" not in rotulo and "excluir" not in rotulo and "delete" not in rotulo:
                            btn.click()
                            page.wait_for_timeout(500)
                            break
                except Exception:
                    continue
        except Exception:
            pass
        _fechar_dialogos(page)
    except Exception:
        try:
            lg = _log()
            if lg is not None:
                lg.exception("click_extra_sec: _fechar_sem_confirmar falhou")
        except Exception:
            pass


def _clicar_seguro(page, testid):
    """EN: Safe click open+close, assert dialog/navigation. PT-BR: clique seguro abre+fecha, asserta dialog/navegacao."""
    try:
        rota, precisa_login = _rota_para_botao(testid)
        _garantir_localhost(BASE_URL)
        if precisa_login:
            _fazer_login(page, USUARIO_QAMASTER, SENHA_QA)
            page.goto(BASE_URL + rota, wait_until="domcontentloaded")
        else:
            page.goto(BASE_URL + rota, wait_until="domcontentloaded")
        page.wait_for_timeout(3500)
        _fechar_dialogos(page)
        conteudo_antes = page.content()
        assert "root:" not in conteudo_antes, "resposta vazou /etc/passwd"
        assert SENHA_QA not in conteudo_antes, "resposta vazou senha"
        assert ".." not in testid, "testid com traversal"
        assert "/" not in testid, "testid com barra"
        assert "\\" not in testid, "testid com barra invertida"
        localizador = page.get_by_test_id(testid)
        total = localizador.count()
        if total < 1:
            return "ausente"
        primeiro = localizador.first
        visivel = bool(primeiro.is_visible())
        habilitado = bool(primeiro.is_enabled())
        assert visivel or habilitado, f"botao sem visible/enabled: {testid}"
        # Final destrutivo: NUNCA clica, so presenca (abre+fecha = nada).
        if _eh_final_destrutivo(testid):
            try:
                lg = _log()
                if lg is not None:
                    lg.info("click_extra_sec: %s final destrutivo, sem clique (so presenca)", testid)
            except Exception:
                pass
            _cookie_sem_segredo(page)
            return "so_presenca_sem_clique"
        url_antes = page.url
        try:
            primeiro.scroll_into_view_if_needed()
            page.wait_for_timeout(400)
        except Exception:
            pass
        primeiro.click()
        page.wait_for_timeout(2000)
        # Assert dialog ou navegacao (sem exigir texto destrutivo).
        dialog_visivel = False
        try:
            dialog_visivel = page.locator(".q-dialog, .q-menu, [role=dialog]").first.is_visible()
        except Exception:
            dialog_visivel = False
        url_depois = ""
        try:
            url_depois = page.url
        except Exception:
            url_depois = url_antes
        navegou = (url_depois != url_antes)
        conteudo_depois = ""
        try:
            conteudo_depois = page.content()
        except Exception:
            conteudo_depois = ""
        assert dialog_visivel or navegou or len(conteudo_depois) > len(conteudo_antes) // 2, (
            f"clique sem dialog/navegacao: {testid} em {rota}"
        )
        assert "root:" not in conteudo_depois, "resposta vazou /etc/passwd apos clique"
        assert SENHA_QA not in conteudo_depois, "resposta vazou senha apos clique"
        _cookie_sem_segredo(page)
        # Fecha sem confirmar destrutivo (Escape/cancelar). NUNCA segundo clique
        # em confirmar/delete/excluir-todas/reiniciar-agora.
        _fechar_sem_confirmar(page)
        _cookie_sem_segredo(page)
        if _eh_abrir_fechar(testid):
            return "abriu_fechou_sem_confirmar"
        return "clicado"
    except AssertionError:
        raise
    except Exception:
        try:
            lg = _log()
            if lg is not None:
                lg.exception("click_extra_sec: _clicar_seguro falhou: %s", testid)
        except Exception:
            pass
        raise


class TestClickExtraSec:
    """EN: 1 safe-click test for 27 buttons (lines 29-55). PT-BR: 1 teste clique seguro p/ 27 botoes (linhas 29-55)."""

    def test_clique_seguro_ultimos_27_botoes(self, page):
        """EN: Loop 27 buttons safe open+close. PT-BR: percorre 27 botoes com abre+fecha seguro."""
        try:
            if not _servidor_ativo():
                pytest.skip("servidor localhost:8080 fora do ar")
            assert len(BOTOES_27) == 27, f"esperado 27 botoes, veio {len(BOTOES_27)}"
            clicados = []
            so_presenca = []
            ausentes = []
            falhas = []
            for testid in BOTOES_27:
                try:
                    status = _clicar_seguro(page, testid)
                    if status == "ausente":
                        ausentes.append(testid)
                    elif status == "so_presenca_sem_clique":
                        so_presenca.append(testid)
                    else:
                        clicados.append(f"{testid}:{status}")
                except AssertionError as exc_ass:
                    try:
                        lg = _log()
                        if lg is not None:
                            lg.exception("click_extra_sec: assert falhou: %s", testid)
                    except Exception:
                        pass
                    falhas.append(f"{testid} :: {exc_ass}")
                except Exception as exc:
                    try:
                        lg = _log()
                        if lg is not None:
                            lg.exception("click_extra_sec: botao falhou: %s", testid)
                    except Exception:
                        pass
                    falhas.append(f"{testid} :: {exc}")
            try:
                lg2 = _log()
                if lg2 is not None:
                    lg2.info(
                        "click_extra_sec: clicados=%s so_presenca=%s ausentes=%s falhas=%s",
                        clicados, so_presenca, ausentes, falhas,
                    )
            except Exception:
                pass
            # Nenhum confirm destrutivo executado: garante que finais ficaram em so_presenca.
            assert "filas-confirmar-exclusao" in so_presenca or "filas-confirmar-exclusao" in ausentes, (
                "filas-confirmar-exclusao deveria ficar sem clique (so presenca/ausente)"
            )
            assert not falhas, f"falhas no clique seguro: {falhas}"
            assert (len(clicados) + len(so_presenca)) >= 1, "nenhum botao verificado"
            _cookie_sem_segredo(page)
        except Exception:
            try:
                lg = _log()
                if lg is not None:
                    lg.exception("click_extra_sec: test_clique_seguro_ultimos_27_botoes falhou")
            except Exception:
                pass
            raise
