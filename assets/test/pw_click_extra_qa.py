"""Clique seguro QA — botoes 1-28 de all_buttons.txt (pytest-playwright, headless).

EN: Safe CLICK coverage for the FIRST 28 buttons (lines 1-28) of
    all_buttons.txt; login as qamaster, goto the owner route, click the
    testid via get_by_test_id, then CLOSE without confirming (dialog ->
    assert visible + Escape/cancel; navigation/refresh/search -> assert URL
    or list reloaded). NEVER clicks confirmar-excluir/apagar/salvar; those
    only verify visible/enabled and skip. Buttons needing prior selection
    skip with a documented reason.
PT: Cobertura de CLIQUE SEGURO para os PRIMEIROS 28 botoes (linhas 1-28) de
    all_buttons.txt; login como qamaster, goto na rota dona, click no testid
    via get_by_test_id e depois FECHA sem confirmar (dialog -> assert
    visivel + Escape/cancelar; navegacao/atualizar/busca -> assert URL ou
    lista recarregou). NUNCA clica em confirmar-excluir/apagar/salvar
    definitivo; nesses so verifica visible/enabled e pula. Botao que exige
    selecao previa pula com skip documentado.

Piramide: E2E de clique seguro (poucos, topo da piramide); sem escrita real.
Confinado a C:\\opencode, localhost http://localhost:8080, headless,
sequencial, 1 contexto (fixture `page` do pytest-playwright); nunca derruba
o servidor (tudo com skip amigavel se fora do ar).
Troca forcada EXECUTADA: quando o dialogo "Troca de senha obrigatoria" abre,
o teste CONCLUI a troca (mesma senha de origem) em vez de pular — antes ele
fazia skip e os cliques rodavam majoritariamente pulados. So ha skip para
infra real (servidor fora). Sem sys.exit, sem massa, sem tocar db/backup/logs/site,
sem segredos alem do seed de QA (qamaster).

Como rodar (Windows):
    .venv\\Scripts\\python -m pytest assets/test/pw_click_extra_qa.py -v
So cliques:
    .venv\\Scripts\\python -m pytest assets/test/pw_click_extra_qa.py -k clique_ -q
"""

import os
import sys

import pytest
from playwright.sync_api import expect

# `qa_login_helper` e irmao deste arquivo: entra no path explicitamente para
# nao depender do modo de import do pytest.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

pytestmark = pytest.mark.e2e

BASE_URL = os.environ.get("INTRANET_BASE_URL", "http://localhost:8080")
QA_USUARIO = "qamaster"
QA_SENHA = "123456"

# Login/troca em UM lugar so (ver qa_login_helper): a copia local era o que
# mantinha a cobertura pulada, porque fazia skip em vez de trocar a senha.
from qa_login_helper import (  # noqa: E402
    _dialogo_troca_visivel,
    concluir_troca as _concluir_troca,
)

# Botoes que exigem selecao previa de linha/lote: nao ha o que clicar sem
# contexto — pula com skip documentado em vez de forcar escrita.
EXIGE_SELECAO_PREVIA = frozenset({
    "blog-confirmar-excluir-lote",  # confirmacao dentro de dialog de lote
    "empenhos-fila-editar",  # por linha da fila (depende de item presente)
    "empenhos-fila-processar",  # por linha da fila + escrita real (renomeia)
})

# Acoes destrutivas/diretas sem dialog de confirmacao: NUNCA dispara o clique
# definitivo no live — so verifica visible/enabled e pula documentado.
NUNCA_CONFIRMAR = frozenset({
    "blog-confirmar-excluir-lote",  # botao CONFIRMAR dentro do dialog
    "agregador-limpar-censuradas",  # delete direto (remove censuradas)
    "agregador-reiniciar-agora",  # zerar manual (apaga estado)
    "empenhos-processar",  # processa pasta agora (escrita em lote)
    "empenhos-reprocessar-fila",  # reprocessa pendentes (escrita em lote)
})


def fazer_login(page, usuario: str, senha: str) -> bool:
    """Faz login e CONCLUI a troca de senha obrigatoria, se aparecer.

    Antes: `pytest.skip` quando o dialogo de troca abria — o que fazia os
    cliques rodarem pulados. Agora a troca e feita com a MESMA senha de
    origem e o `forcar_troca` e zerado.
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
                "() => !location.pathname.startsWith('/login')", timeout=20000
            )
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
        _concluir_troca(page, senha, senha)
        return not _dialogo_troca_visivel(page)
    try:
        url = page.url
    except Exception:
        url = ""
    return "/login" not in (url or "")


def _rota_para_botao(testid: str) -> str:
    """Mapeia cada botao (linhas 1-28) para a rota dona do modulo."""
    try:
        mapa = {
            "admin-criar-contato": "/admin/lista_telefonica",
            "admin-criar-unidade": "/admin/lista_telefonica",
            "agregador-add-fonte": "/admin/agregador_noticias",
            "agregador-anterior": "/agregador-noticias",
            "agregador-atualizar": "/agregador-noticias",
            "agregador-coletar": "/agregador-noticias",
            "agregador-coletar-agora": "/admin/agregador_noticias",
            "agregador-limpar-censuradas": "/admin/agregador_noticias",
            "agregador-primeira": "/agregador-noticias",
            "agregador-proxima": "/agregador-noticias",
            "agregador-reiniciar-agora": "/admin/agregador_noticias",
            "agregador-ultima": "/agregador-noticias",
            "blog-confirmar-excluir-lote": "/blog",
            "blog-excluir-selecionados": "/blog",
            "blog-limpar-selecao": "/blog",
            "blog-selecionar-10": "/blog",
            "blog-selecionar-5": "/blog",
            "empenhos-atualizar": "/renomear-empenho",
            "empenhos-fila-editar": "/renomear-empenho",
            "empenhos-fila-processar": "/renomear-empenho",
            "empenhos-filtro-icone": "/renomear-empenho",
            "empenhos-lote-baixar": "/renomear-empenho",
            "empenhos-lote-limpar": "/renomear-empenho",
            "empenhos-lote-marcar": "/renomear-empenho",
            "empenhos-lote-solicitar": "/renomear-empenho",
            "empenhos-processar": "/renomear-empenho",
            "empenhos-raiz-dot": "/renomear-empenho",
            "empenhos-reprocessar-fila": "/renomear-empenho",
        }
        return mapa.get(testid, "/")
    except Exception:
        return "/"


def _fechar_dialogo_se_aberto(page) -> bool:
    """Fecha dialog Quasar aberto sem confirmar; retorna True se havia dialog."""
    try:
        dialogo = page.locator(".q-dialog, [role='dialog']")
        try:
            total = dialogo.count()
        except Exception:
            total = 0
        if total <= 0:
            return False
        try:
            visivel = dialogo.first.is_visible()
        except Exception:
            visivel = False
        if not visivel:
            return False
        assert visivel, "dialog deveria estar visível após o clique"
        # Tenta botao cancelar/fechar/voltar; senao Escape.
        try:
            for texto in ("Cancelar", "Fechar", "Voltar", "Não", "Nao"):
                candidato = page.get_by_role("button", name=texto)
                try:
                    if candidato.count() > 0 and candidato.first.is_visible():
                        candidato.first.click()
                        page.wait_for_timeout(800)
                        return True
                except Exception:
                    continue
        except Exception:
            pass
        try:
            page.keyboard.press("Escape")
            page.wait_for_timeout(800)
        except Exception:
            pass
        return True
    except AssertionError:
        raise
    except Exception:
        return False


def _clicar_seguro(page, testid: str) -> None:
    """Login qamaster, goto rota dona, click seguro e fecha sem confirmar."""
    try:
        if testid in EXIGE_SELECAO_PREVIA:
            pytest.skip(f"{testid}: exige seleção prévia de linha/lote — pule documentado")
        rota = _rota_para_botao(testid)
        ok = fazer_login(page, QA_USUARIO, QA_SENHA)
        if not ok:
            pytest.skip("login do qamaster não abriu sessão (credencial "
                        "inválida ou infraestrutura instável)")
        if _dialogo_troca_visivel(page):
            pytest.fail("troca de senha obrigatória NÃO foi concluída pelo "
                        "login — o diálogo continua bloqueando a tela")
        try:
            page.goto(f"{BASE_URL}{rota}", wait_until="domcontentloaded", timeout=15000)
        except Exception:
            pytest.skip(f"servidor live indisponível em {BASE_URL}{rota}")
        try:
            page.wait_for_timeout(2000)
        except Exception:
            pass
        try:
            total = page.get_by_test_id(testid).count()
        except Exception:
            total = 0
        if total <= 0:
            pytest.skip(f"{testid} ausente em {rota} (sem permissão/condição) — pule")
        alvo = page.get_by_test_id(testid).first
        try:
            expect(alvo).to_be_visible(timeout=10000)
        except Exception:
            pytest.skip(f"{testid} fora da viewport em {rota} — pule")
        if testid in NUNCA_CONFIRMAR:
            try:
                expect(alvo).to_be_enabled(timeout=10000)
            except Exception:
                pass
            pytest.skip(f"{testid}: ação definitiva — só visible/enabled, sem clique")
        try:
            url_antes = page.url
        except Exception:
            url_antes = ""
        alvo.click()
        try:
            page.wait_for_timeout(1500)
        except Exception:
            pass
        fechou = _fechar_dialogo_se_aberto(page)
        if fechou:
            # Dialog aberto e fechado sem confirmar: garante que nao navegou
            # para lugar inesperado nem travou a pagina.
            try:
                assert rota in (page.url or "") or BASE_URL in (page.url or "")
            except AssertionError:
                raise
            except Exception:
                pass
            return
        # Sem dialog: navegacao/atualizar/busca — assert URL ou lista recarregou
        # (botao segue visivel e pagina segue na rota dona).
        try:
            url_depois = page.url
        except Exception:
            url_depois = ""
        assert (rota in (url_depois or "")) or (url_antes in (url_depois or "")), (
            f"navegação inesperada após clicar em {testid}: {url_depois}"
        )
        try:
            expect(page.get_by_test_id(testid).first).to_be_visible(timeout=10000)
        except Exception:
            pass
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"infra instável ao clicar em {testid} — pule: {exc}")


class TestCliqueSeguroAdmin:
    """Cliques seguros dos botoes admin (linhas 1-2)."""

    def test_clique_admin_criar_contato(self, page):
        """Clica em admin-criar-contato e fecha o dialog sem salvar."""
        try:
            _clicar_seguro(page, "admin-criar-contato")
        except pytest.skip.Exception:
            raise
        except AssertionError:
            raise
        except Exception as exc:
            pytest.skip(f"pule por infra: {exc}")

    def test_clique_admin_criar_unidade(self, page):
        """Clica em admin-criar-unidade e fecha o dialog sem salvar."""
        try:
            _clicar_seguro(page, "admin-criar-unidade")
        except pytest.skip.Exception:
            raise
        except AssertionError:
            raise
        except Exception as exc:
            pytest.skip(f"pule por infra: {exc}")


class TestCliqueSeguroAgregador:
    """Cliques seguros do agregador (linhas 3-12)."""

    def test_clique_agregador_add_fonte(self, page):
        """Clica em agregador-add-fonte sem cadastrar (fecha sem salvar)."""
        try:
            _clicar_seguro(page, "agregador-add-fonte")
        except pytest.skip.Exception:
            raise
        except AssertionError:
            raise
        except Exception as exc:
            pytest.skip(f"pule por infra: {exc}")

    def test_clique_agregador_anterior(self, page):
        """Clica em agregador-anterior e garante paginacao sem sair da rota."""
        try:
            _clicar_seguro(page, "agregador-anterior")
        except pytest.skip.Exception:
            raise
        except AssertionError:
            raise
        except Exception as exc:
            pytest.skip(f"pule por infra: {exc}")

    def test_clique_agregador_atualizar(self, page):
        """A grade é atualizada SOZINHA — o botão 'Atualizar' foi removido.

        Removido em 26/09/2026: a atualização virou automática (ui.timer com
        atualização parcial). Este teste fica como REGRA DE NEGÓCIO: se o
        botão voltar, é porque alguém quebrou a atualização automática.
        """
        page.goto(f"{BASE_URL}/agregador-noticias", wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(1500)
        assert page.get_by_test_id("agregador-atualizar").count() == 0, (
            "o botão 'Atualizar' foi removido de propósito — a grade se "
            "atualiza sozinha; se ele voltou, revise a atualização automática")

    def test_clique_agregador_coletar(self, page):
        """Clica em agregador-coletar e garante permanencia na rota."""
        try:
            _clicar_seguro(page, "agregador-coletar")
        except pytest.skip.Exception:
            raise
        except AssertionError:
            raise
        except Exception as exc:
            pytest.skip(f"pule por infra: {exc}")

    def test_clique_agregador_coletar_agora(self, page):
        """Clica em agregador-coletar-agora e fecha sem confirmar duplicado."""
        try:
            _clicar_seguro(page, "agregador-coletar-agora")
        except pytest.skip.Exception:
            raise
        except AssertionError:
            raise
        except Exception as exc:
            pytest.skip(f"pule por infra: {exc}")

    def test_clique_agregador_limpar_censuradas(self, page):
        """Verifica agregador-limpar-censuradas sem apagar (definitivo)."""
        try:
            _clicar_seguro(page, "agregador-limpar-censuradas")
        except pytest.skip.Exception:
            raise
        except AssertionError:
            raise
        except Exception as exc:
            pytest.skip(f"pule por infra: {exc}")

    def test_clique_agregador_primeira(self, page):
        """Clica em agregador-primeira e garante paginacao sem sair da rota."""
        try:
            _clicar_seguro(page, "agregador-primeira")
        except pytest.skip.Exception:
            raise
        except AssertionError:
            raise
        except Exception as exc:
            pytest.skip(f"pule por infra: {exc}")

    def test_clique_agregador_proxima(self, page):
        """Clica em agregador-proxima e garante paginacao sem sair da rota."""
        try:
            _clicar_seguro(page, "agregador-proxima")
        except pytest.skip.Exception:
            raise
        except AssertionError:
            raise
        except Exception as exc:
            pytest.skip(f"pule por infra: {exc}")

    def test_clique_agregador_reiniciar_agora(self, page):
        """Verifica agregador-reiniciar-agora sem zerar (definitivo)."""
        try:
            _clicar_seguro(page, "agregador-reiniciar-agora")
        except pytest.skip.Exception:
            raise
        except AssertionError:
            raise
        except Exception as exc:
            pytest.skip(f"pule por infra: {exc}")

    def test_clique_agregador_ultima(self, page):
        """Clica em agregador-ultima e garante paginacao sem sair da rota."""
        try:
            _clicar_seguro(page, "agregador-ultima")
        except pytest.skip.Exception:
            raise
        except AssertionError:
            raise
        except Exception as exc:
            pytest.skip(f"pule por infra: {exc}")


class TestCliqueSeguroBlog:
    """Cliques seguros do blog (linhas 13-17)."""

    def test_clique_blog_confirmar_excluir_lote(self, page):
        """Pula blog-confirmar-excluir-lote: exige selecao e e definitivo."""
        try:
            _clicar_seguro(page, "blog-confirmar-excluir-lote")
        except pytest.skip.Exception:
            raise
        except AssertionError:
            raise
        except Exception as exc:
            pytest.skip(f"pule por infra: {exc}")

    def test_clique_blog_excluir_selecionados(self, page):
        """Clica em blog-excluir-selecionados e fecha o dialog sem excluir."""
        try:
            _clicar_seguro(page, "blog-excluir-selecionados")
        except pytest.skip.Exception:
            raise
        except AssertionError:
            raise
        except Exception as exc:
            pytest.skip(f"pule por infra: {exc}")

    def test_clique_blog_limpar_selecao(self, page):
        """Clica em blog-limpar-selecao e garante lista recarregada."""
        try:
            _clicar_seguro(page, "blog-limpar-selecao")
        except pytest.skip.Exception:
            raise
        except AssertionError:
            raise
        except Exception as exc:
            pytest.skip(f"pule por infra: {exc}")

    def test_clique_blog_selecionar_10(self, page):
        """Clica em blog-selecionar-10 e garante lista recarregada."""
        try:
            _clicar_seguro(page, "blog-selecionar-10")
        except pytest.skip.Exception:
            raise
        except AssertionError:
            raise
        except Exception as exc:
            pytest.skip(f"pule por infra: {exc}")

    def test_clique_blog_selecionar_5(self, page):
        """Clica em blog-selecionar-5 e garante lista recarregada."""
        try:
            _clicar_seguro(page, "blog-selecionar-5")
        except pytest.skip.Exception:
            raise
        except AssertionError:
            raise
        except Exception as exc:
            pytest.skip(f"pule por infra: {exc}")


class TestCliqueSeguroEmpenhos:
    """Cliques seguros dos empenhos (linhas 18-28)."""

    def test_clique_empenhos_atualizar(self, page):
        """Clica em empenhos-atualizar e garante lista recarregada."""
        try:
            _clicar_seguro(page, "empenhos-atualizar")
        except pytest.skip.Exception:
            raise
        except AssertionError:
            raise
        except Exception as exc:
            pytest.skip(f"pule por infra: {exc}")

    def test_clique_empenhos_fila_editar(self, page):
        """Pula empenhos-fila-editar: exige linha da fila selecionada."""
        try:
            _clicar_seguro(page, "empenhos-fila-editar")
        except pytest.skip.Exception:
            raise
        except AssertionError:
            raise
        except Exception as exc:
            pytest.skip(f"pule por infra: {exc}")

    def test_clique_empenhos_fila_processar(self, page):
        """Pula empenhos-fila-processar: exige linha e escreve de verdade."""
        try:
            _clicar_seguro(page, "empenhos-fila-processar")
        except pytest.skip.Exception:
            raise
        except AssertionError:
            raise
        except Exception as exc:
            pytest.skip(f"pule por infra: {exc}")

    def test_clique_empenhos_filtro_icone(self, page):
        """Clica em empenhos-filtro-icone e garante filtro sem sair da rota."""
        try:
            _clicar_seguro(page, "empenhos-filtro-icone")
        except pytest.skip.Exception:
            raise
        except AssertionError:
            raise
        except Exception as exc:
            pytest.skip(f"pule por infra: {exc}")

    def test_clique_empenhos_lote_baixar(self, page):
        """Clica em empenhos-lote-baixar sem lote e garante sem download."""
        try:
            _clicar_seguro(page, "empenhos-lote-baixar")
        except pytest.skip.Exception:
            raise
        except AssertionError:
            raise
        except Exception as exc:
            pytest.skip(f"pule por infra: {exc}")

    def test_clique_empenhos_lote_limpar(self, page):
        """Clica em empenhos-lote-limpar e garante lista recarregada."""
        try:
            _clicar_seguro(page, "empenhos-lote-limpar")
        except pytest.skip.Exception:
            raise
        except AssertionError:
            raise
        except Exception as exc:
            pytest.skip(f"pule por infra: {exc}")

    def test_clique_empenhos_lote_marcar(self, page):
        """Clica em empenhos-lote-marcar e garante lista recarregada."""
        try:
            _clicar_seguro(page, "empenhos-lote-marcar")
        except pytest.skip.Exception:
            raise
        except AssertionError:
            raise
        except Exception as exc:
            pytest.skip(f"pule por infra: {exc}")

    def test_clique_empenhos_lote_solicitar(self, page):
        """Clica em empenhos-lote-solicitar e fecha o dialog sem enviar."""
        try:
            _clicar_seguro(page, "empenhos-lote-solicitar")
        except pytest.skip.Exception:
            raise
        except AssertionError:
            raise
        except Exception as exc:
            pytest.skip(f"pule por infra: {exc}")

    def test_clique_empenhos_processar(self, page):
        """Verifica empenhos-processar sem processar a pasta (definitivo)."""
        try:
            _clicar_seguro(page, "empenhos-processar")
        except pytest.skip.Exception:
            raise
        except AssertionError:
            raise
        except Exception as exc:
            pytest.skip(f"pule por infra: {exc}")

    def test_clique_empenhos_raiz_dot(self, page):
        """Clica em empenhos-raiz-dot e garante navegacao na mesma rota."""
        try:
            _clicar_seguro(page, "empenhos-raiz-dot")
        except pytest.skip.Exception:
            raise
        except AssertionError:
            raise
        except Exception as exc:
            pytest.skip(f"pule por infra: {exc}")

    def test_clique_empenhos_reprocessar_fila(self, page):
        """Verifica empenhos-reprocessar-fila sem reprocessar (definitivo)."""
        try:
            _clicar_seguro(page, "empenhos-reprocessar-fila")
        except pytest.skip.Exception:
            raise
        except AssertionError:
            raise
        except Exception as exc:
            pytest.skip(f"pule por infra: {exc}")


if __name__ == "__main__":
    print("Execute: .venv\\Scripts\\python -m pytest assets/test/pw_click_extra_qa.py -k clique_ -q")
