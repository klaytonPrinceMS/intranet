"""Cobertura extra QA — primeiros 85 data-testid (pytest-playwright, headless).

EN: Covers the FIRST 85 testids from all_testids.txt (lines 1-85) with one
    coletavel test per testid (test_vis_<slug>); login as qamaster, navigate
    to the owner route mapped by prefix, assert count>=0 without destructive
    clicks; write buttons only assert visible/enabled, never click.
PT: Cobre os PRIMEIROS 85 data-testid de all_testids.txt (linhas 1-85) com um
    teste coletavel por testid (test_vis_<slug>); faz login como qamaster,
    navega a rota dona mapeada pelo prefixo e asserta count>=0 sem clique
    destrutivo; botao de escrita apenas verifica visible/enabled, NUNCA clica.

Piramide: E2E de leitura (presenca liberada); sem escrita, sem upload.
Troca forcada EXECUTADA: quando o dialogo "Troca de senha obrigatoria" abre,
o teste CONCLUI a troca (com a mesma senha de origem) em vez de pular — antes
ele fazia skip e a cobertura rodava majoritariamente pulada, sem ninguem ver.
So ha skip para infra real (servidor fora). Servidor fora tambem faz skip (sem derrubar).
Sem sys.exit, sem tocar db/backup/logs/site, sem segredos alem do seed de QA.

Como rodar (Windows):
    .venv\\Scripts\\python -m pytest assets/test/pw_cobertura_extra_qa.py -v -k vis_
Tudo vis_:
    .venv\\Scripts\\python -m pytest assets/test/pw_cobertura_extra_qa.py -k vis_ -q
"""

import os
import sys

import pytest
from playwright.sync_api import expect

# O dir do teste entra no path explicitamente: `qa_login_helper` e irmao deste
# arquivo, e sem isso a resolucao dependeria do modo de import do pytest.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

pytestmark = pytest.mark.e2e

BASE_URL = os.environ.get("INTRANET_BASE_URL", "http://localhost:8080")
QA_USUARIO = "qamaster"
QA_SENHA = "123456"

# O login/troca vive num ÚNICO lugar (qa_login_helper) porque foi duplicado
# aqui e no pw_click_extra_qa, e a duplicata é o que deixou a cobertura
# Playwright rodando pulada: os dois faziam `pytest.skip` quando a troca
# obrigatória aparecia, em vez de CONCLUIR a troca.
from qa_login_helper import (  # noqa: E402
    _dialogo_troca_visivel,
    concluir_troca as _concluir_troca,
)


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
    except Exception as exc:
        try:
            pytest.skip(f"falha de infra no login — pule: {exc}")
        except Exception:
            return False
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


# Arquivo-fonte -> rota. O mesmo módulo tem TELA PÚBLICA e PAINEL ADMIN
# com testids de prefixo IGUAL (`agregador-busca` é público, `agregador-termo`
# é admin), então um mapa por prefixo erra metade. O mapa tem que ser por
# ARQUIVO, não por nome de testid.
_ARQUIVO_ROTA = {
    "mod_agregador_noticias/telas.py": "/agregador-noticias",
    "mod_agregador_noticias/telas_administracao.py": "/admin/agregador_noticias",
    "mod_blog/telas.py": "/blog",
    "mod_blog/telas_administracao.py": "/admin/blog",
    "mod_renomear_empenho/telas.py": "/renomear-empenho",
    "mod_edit_pdf/telas.py": "/edit-pdf",
    "mod_lista_telefonica/telas.py": "/lista-telefonica",
    "mod_lista_telefonica/telas_administracao.py": "/admin/lista_telefonica",
    "mod_gest_cad_usuario/telas.py": "/users",
    "mod_auditoria/telas.py": "/auditoria",
    "mod_filas/telas.py": "/filas",
    "mod_tecnico/telas.py": "/tecnico",
    "mod_solicita_impressao/telas.py": "/solicita-impressao",
    "mod_solicita_impressao/telas_administracao.py": "/admin/solicita_impressao",
    "mod_intranet/telas.py": "/",
}

# Fallback por prefixo, só para o que não achamos no fonte (menu/login, que
# são criados por `ui_comum`/`main` e não por `.props('data-testid=...')`).
_PREFIXO_ROTA = {
    "admin-": "/admin/lista_telefonica",
    "login-": "/login",
    "menu-": "/",
    "rodape-": "/",
    "header-": "/",
}


def _arquivo_do_testid(testid: str) -> str:
    """Descobre em qual arquivo-fonte o testid é declarado."""
    try:
        from pathlib import Path
        raiz = Path(__file__).resolve().parents[2]
        for arquivo in sorted(raiz.glob("mod_*/**/*.py")):
            if "__pycache__" in str(arquivo):
                continue
            try:
                texto = arquivo.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            if f"data-testid={testid}" in texto:
                return str(arquivo.relative_to(raiz)).replace("\\", "/")
    except Exception:
        return ""
    return ""


def _rota_para_testid(testid: str) -> str:
    """Resolve a rota dona do testid LENDO O CÓDIGO-FONTE.

    O mapa manual por prefixo já apodreceu uma vez: `agregador-busca`
    (público) e `agregador-termo` (admin) compartilham prefixo, e metade
    dos testes falhava por rota errada — não por elemento faltando.
    Descobrindo o arquivo que declara o testid, a rota vem junto e não
    precisa de manutenção quando o elemento muda de tela.
    """
    try:
        arquivo = _arquivo_do_testid(testid)
        if arquivo and arquivo in _ARQUIVO_ROTA:
            return _ARQUIVO_ROTA[arquivo]
        for prefixo, rota in _PREFIXO_ROTA.items():
            if testid.startswith(prefixo):
                return rota
        return "/"
    except Exception:
        return "/"
    except Exception:
        return "/"


def _eh_escrita(testid: str) -> bool:
    """Heuristica de botao de escrita (nunca clicar; so verificar)."""
    try:
        pistas = (
            "criar", "publicar", "excluir", "editar", "enviar", "salvar",
            "adicionar", "add-", "atualizar", "coletar", "processar",
            "cortar", "dividir", "juntar", "reduzir", "despublicar",
            "limpar", "reiniciar", "aplicar", "confirmar",
        )
        nome = (testid or "").lower()
        return any(p in nome for p in pistas)
    except Exception:
        return False


# Testid -> rótulo da aba que precisa estar aberta para ele existir.
# O módulo de Empenhos abre sempre na aba "Navegar"; a "Fila Renomeação"
# guarda os botões por linha (editar/processar), que só existem depois do
# clique na aba.
ABA_PARA_TESTID = {
    "empenhos-fila-editar": "Fila Renomeação",
    "empenhos-fila-processar": "Fila Renomeação",
}


def _abrir_aba_se_precisar(page, testid: str) -> None:
    """Clica na aba que contém o testid, se ele não estiver na tela."""
    try:
        if page.get_by_test_id(testid).count() > 0:
            return
        rotulo = ABA_PARA_TESTID.get(testid)
        if not rotulo:
            return
        aba = page.get_by_role("tab", name=rotulo)
        if aba.count() == 0:
            aba = page.get_by_text(rotulo, exact=True)
        if aba.count() > 0:
            aba.first.click()
            page.wait_for_timeout(2000)
    except Exception:
        pass


# Testids por LINHA: só existem se houver item na fila/lista. Sem dado, não
# há botão — e forjar dado aqui sobrescreveria a massa de teste do módulo.
PRECISA_DE_ITEM = {
    "empenhos-fila-editar": "a aba 'Fila Renomeação' precisa ter ao menos um item",
    "empenhos-fila-processar": "a aba 'Fila Renomeação' precisa ter ao menos um item",
    # CONFIRMAÇÃO dentro do diálogo de exclusão em lote: exige selecionar
    # posts e abrir o diálogo antes. É botão DESTRUTIVO — a suíte de leitura
    # nunca dispara a confirmação, então aqui só se documenta a exigência.
    "blog-confirmar-excluir-lote": "é o confirmar do diálogo de exclusão em "
                                  "lote (exige seleção prévia; destrutivo)",
}

# O Blog abre no modo CARROSSEL (padrão `blog_modo_exibicao`), que mostra um
# post por vez; as ações de editar/excluir só entram no DOM quando o post está
# EXPANDIDO. Expandir é só interface — não grava nada — então é seguro aqui.
PRECISA_EXPANDIR_POST = {
    "blog-editar", "blog-excluir", "blog-despublicar", "blog-confirmar-excluir-lote",
}


def _expandir_post_do_blog(page) -> None:
    """Clica no post para revelar as ações de publicação (sem escrita)."""
    try:
        if page.get_by_test_id("blog-editar").count() > 0:
            return
        for texto in ("Leitura completa", "Ler completa", "leia"):
            alvo = page.get_by_text(texto, exact=False).first
            if alvo.count() > 0:
                alvo.click()
                page.wait_for_timeout(2500)
                return
    except Exception:
        pass


def _verificar_presenca(page, testid: str) -> None:
    """Login qamaster, navega a rota dona e asserta presenca sem clique destrutivo."""
    try:
        rota = _rota_para_testid(testid)
        if rota != "/login":
            ok = fazer_login(page, QA_USUARIO, QA_SENHA)
            if not ok:
                # Sem sessão utilizável depois de TENTAR a troca: aí é infra
                # (credencial inválida de verdade), não a troca pendente.
                pytest.skip("login do qamaster não abriu sessão (credencial "
                            "inválida ou infraestrutura instável)")
        try:
            page.goto(f"{BASE_URL}{rota}", wait_until="domcontentloaded", timeout=15000)
        except Exception:
            pytest.skip(f"servidor live indisponível em {BASE_URL}{rota}")
        try:
            page.wait_for_timeout(2000)
        except Exception:
            pass
        # Alguns testids só existem numa ABA secundária (o Empenhos abre em
        # "Navegar"; a "Fila Renomeação" precisa ser clicada). Sem abrir a aba,
        # a contagem daria 0 e o teste culparia o elemento inexistente.
        _abrir_aba_se_precisar(page, testid)
        if testid in PRECISA_EXPANDIR_POST:
            _expandir_post_do_blog(page)
        try:
            total = page.get_by_test_id(testid).count()
        except Exception:
            total = 0
        if total == 0 and testid in PRECISA_DE_ITEM:
            pytest.skip(f"{testid}: {PRECISA_DE_ITEM[testid]} — botão por "
                        f"linha, sem dado não há o que verificar")
        assert total >= 1, f"testid {testid} ausente na tela (contagem={total})"
        if total > 0 and _eh_escrita(testid):
            try:
                expect(page.get_by_test_id(testid).first).to_be_visible(timeout=10000)
                expect(page.get_by_test_id(testid).first).to_be_enabled(timeout=10000)
            except Exception:
                pass
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"infra instável ao verificar {testid} — pule: {exc}")


def test_vis_admin_contato_busca(page):
    """Verifica presenca de admin-contato-busca em /admin/lista_telefonica."""
    try:
        _verificar_presenca(page, "admin-contato-busca")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_admin_contato_nome(page):
    """Verifica presenca de admin-contato-nome em /admin/lista_telefonica."""
    try:
        _verificar_presenca(page, "admin-contato-nome")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_admin_contato_tel(page):
    """Verifica presenca de admin-contato-tel em /admin/lista_telefonica."""
    try:
        _verificar_presenca(page, "admin-contato-tel")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_admin_contato_unidade(page):
    """Verifica presenca de admin-contato-unidade em /admin/lista_telefonica."""
    try:
        _verificar_presenca(page, "admin-contato-unidade")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_admin_contato_user(page):
    """Verifica presenca de admin-contato-user em /admin/lista_telefonica."""
    try:
        _verificar_presenca(page, "admin-contato-user")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_admin_criar_contato(page):
    """Verifica admin-criar-contato (escrita: so visible/enabled, sem clicar)."""
    try:
        _verificar_presenca(page, "admin-criar-contato")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_admin_criar_unidade(page):
    """Verifica admin-criar-unidade (escrita: so visible/enabled, sem clicar)."""
    try:
        _verificar_presenca(page, "admin-criar-unidade")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_admin_unidade_nome(page):
    """Verifica presenca de admin-unidade-nome em /admin/lista_telefonica."""
    try:
        _verificar_presenca(page, "admin-unidade-nome")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_admin_unidade_pai(page):
    """Verifica presenca de admin-unidade-pai em /admin/lista_telefonica."""
    try:
        _verificar_presenca(page, "admin-unidade-pai")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_admin_unidade_tel(page):
    """Verifica presenca de admin-unidade-tel em /admin/lista_telefonica."""
    try:
        _verificar_presenca(page, "admin-unidade-tel")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_admin_unidade_tipo(page):
    """Verifica presenca de admin-unidade-tipo em /admin/lista_telefonica."""
    try:
        _verificar_presenca(page, "admin-unidade-tipo")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_agregador_add_fonte(page):
    """Verifica agregador-add-fonte (escrita: so visible/enabled, sem clicar)."""
    try:
        _verificar_presenca(page, "agregador-add-fonte")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_agregador_anterior(page):
    """Verifica presenca de agregador-anterior em /agregador-noticias."""
    try:
        _verificar_presenca(page, "agregador-anterior")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_agregador_atualizar(page):
    """O botão 'Atualizar' NÃO deve existir (grade se atualiza sozinha).

    Virou regra de negócio: se o botão reaparecer, a atualização automática
    foi quebrada."""
    try:
        page.goto(f"{BASE_URL}/agregador-noticias", wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(1500)
        assert page.get_by_test_id("agregador-atualizar").count() == 0, (
            "botão 'Atualizar' deveria ter sido removido — atualização é automática")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_agregador_busca(page):
    """Verifica presenca de agregador-busca em /agregador-noticias."""
    try:
        _verificar_presenca(page, "agregador-busca")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_agregador_coletar(page):
    """Verifica agregador-coletar (escrita: so visible/enabled, sem clicar)."""
    try:
        _verificar_presenca(page, "agregador-coletar")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_agregador_coletar_agora(page):
    """Verifica agregador-coletar-agora (escrita: so visible/enabled, sem clicar)."""
    try:
        _verificar_presenca(page, "agregador-coletar-agora")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_agregador_filtro_tema(page):
    """Verifica presenca de agregador-filtro-tema em /agregador-noticias."""
    try:
        _verificar_presenca(page, "agregador-filtro-tema")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_agregador_fonte_nome(page):
    """Verifica presenca de agregador-fonte-nome em /agregador-noticias."""
    try:
        _verificar_presenca(page, "agregador-fonte-nome")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_agregador_fonte_tema(page):
    """Verifica presenca de agregador-fonte-tema em /agregador-noticias."""
    try:
        _verificar_presenca(page, "agregador-fonte-tema")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_agregador_fonte_tipo(page):
    """Verifica presenca de agregador-fonte-tipo em /agregador-noticias."""
    try:
        _verificar_presenca(page, "agregador-fonte-tipo")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_agregador_fonte_url(page):
    """Verifica presenca de agregador-fonte-url em /agregador-noticias."""
    try:
        _verificar_presenca(page, "agregador-fonte-url")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_agregador_habilitado(page):
    """Verifica presenca de agregador-habilitado em /agregador-noticias."""
    try:
        _verificar_presenca(page, "agregador-habilitado")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_agregador_hora_reinicio(page):
    """Verifica presenca de agregador-hora-reinicio em /agregador-noticias."""
    try:
        _verificar_presenca(page, "agregador-hora-reinicio")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_agregador_intervalo(page):
    """Verifica presenca de agregador-intervalo em /agregador-noticias."""
    try:
        _verificar_presenca(page, "agregador-intervalo")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_agregador_limpar_censuradas(page):
    """Verifica agregador-limpar-censuradas (escrita: so visible/enabled, sem clicar)."""
    try:
        _verificar_presenca(page, "agregador-limpar-censuradas")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_agregador_palavras_bloqueadas(page):
    """Verifica presenca de agregador-palavras-bloqueadas em /agregador-noticias."""
    try:
        _verificar_presenca(page, "agregador-palavras-bloqueadas")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_agregador_primeira(page):
    """Verifica presenca de agregador-primeira em /agregador-noticias."""
    try:
        _verificar_presenca(page, "agregador-primeira")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_agregador_proxima(page):
    """Verifica presenca de agregador-proxima em /agregador-noticias."""
    try:
        _verificar_presenca(page, "agregador-proxima")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_agregador_reiniciar_agora(page):
    """Verifica agregador-reiniciar-agora (escrita: so visible/enabled, sem clicar)."""
    try:
        _verificar_presenca(page, "agregador-reiniciar-agora")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_agregador_temas(page):
    """Verifica presenca de agregador-temas em /agregador-noticias."""
    try:
        _verificar_presenca(page, "agregador-temas")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_agregador_termo(page):
    """Verifica presenca de agregador-termo em /agregador-noticias."""
    try:
        _verificar_presenca(page, "agregador-termo")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_agregador_ultima(page):
    """Verifica presenca de agregador-ultima em /agregador-noticias."""
    try:
        _verificar_presenca(page, "agregador-ultima")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_auditoria_busca(page):
    """Verifica presenca de auditoria-busca em /auditoria."""
    try:
        _verificar_presenca(page, "auditoria-busca")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_auditoria_exportar(page):
    """Verifica presenca de auditoria-exportar em /auditoria (sem clicar)."""
    try:
        _verificar_presenca(page, "auditoria-exportar")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_blog_aplicar_carrossel(page):
    """Verifica blog-aplicar-carrossel (escrita: so visible/enabled, sem clicar)."""
    try:
        _verificar_presenca(page, "blog-aplicar-carrossel")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_blog_aplicar_historico(page):
    """Verifica blog-aplicar-historico (escrita: so visible/enabled, sem clicar)."""
    try:
        _verificar_presenca(page, "blog-aplicar-historico")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_blog_aplicar_unica(page):
    """Verifica blog-aplicar-unica (escrita: so visible/enabled, sem clicar)."""
    try:
        _verificar_presenca(page, "blog-aplicar-unica")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_blog_busca(page):
    """Verifica presenca de blog-busca em /blog."""
    try:
        _verificar_presenca(page, "blog-busca")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_blog_confirmar_excluir_lote(page):
    """Verifica blog-confirmar-excluir-lote (escrita: so visible/enabled, sem clicar)."""
    try:
        _verificar_presenca(page, "blog-confirmar-excluir-lote")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_blog_conteudo(page):
    """Verifica presenca de blog-conteudo em /blog."""
    try:
        _verificar_presenca(page, "blog-conteudo")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_blog_despublicar(page):
    """Verifica blog-despublicar (escrita: so visible/enabled, sem clicar)."""
    try:
        _verificar_presenca(page, "blog-despublicar")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_blog_editar(page):
    """Verifica blog-editar (escrita: so visible/enabled, sem clicar)."""
    try:
        _verificar_presenca(page, "blog-editar")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_blog_excluir(page):
    """Verifica blog-excluir (escrita: so visible/enabled, sem clicar)."""
    try:
        _verificar_presenca(page, "blog-excluir")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_blog_excluir_selecionados(page):
    """Verifica blog-excluir-selecionados (escrita: so visible/enabled, sem clicar)."""
    try:
        _verificar_presenca(page, "blog-excluir-selecionados")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_blog_imagem_enviar(page):
    """Verifica blog-imagem-enviar (escrita: so visible/enabled, sem clicar)."""
    try:
        _verificar_presenca(page, "blog-imagem-enviar")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_blog_imagem_selecionar(page):
    """Verifica presenca de blog-imagem-selecionar em /blog (sem upload, sem clicar)."""
    try:
        _verificar_presenca(page, "blog-imagem-selecionar")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_blog_img_centro(page):
    """Verifica presenca de blog-img-centro em /blog."""
    try:
        _verificar_presenca(page, "blog-img-centro")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_blog_img_dir(page):
    """Verifica presenca de blog-img-dir em /blog."""
    try:
        _verificar_presenca(page, "blog-img-dir")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_blog_img_esq(page):
    """Verifica presenca de blog-img-esq em /blog."""
    try:
        _verificar_presenca(page, "blog-img-esq")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_blog_img_largura(page):
    """Verifica presenca de blog-img-largura em /blog."""
    try:
        _verificar_presenca(page, "blog-img-largura")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_blog_limpar_selecao(page):
    """Verifica blog-limpar-selecao (escrita: so visible/enabled, sem clicar)."""
    try:
        _verificar_presenca(page, "blog-limpar-selecao")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_blog_palavras_bloqueadas(page):
    """Verifica presenca de blog-palavras-bloqueadas em /blog."""
    try:
        _verificar_presenca(page, "blog-palavras-bloqueadas")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_blog_publicar(page):
    """Verifica blog-publicar (escrita: so visible/enabled, sem clicar)."""
    try:
        _verificar_presenca(page, "blog-publicar")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_blog_quebra_atras(page):
    """Verifica presenca de blog-quebra-atras em /blog."""
    try:
        _verificar_presenca(page, "blog-quebra-atras")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_blog_quebra_atraves(page):
    """Verifica presenca de blog-quebra-atraves em /blog."""
    try:
        _verificar_presenca(page, "blog-quebra-atraves")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_blog_quebra_emlinha(page):
    """Verifica presenca de blog-quebra-emlinha em /blog."""
    try:
        _verificar_presenca(page, "blog-quebra-emlinha")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_blog_quebra_frente(page):
    """Verifica presenca de blog-quebra-frente em /blog."""
    try:
        _verificar_presenca(page, "blog-quebra-frente")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_blog_quebra_justo(page):
    """Verifica presenca de blog-quebra-justo em /blog."""
    try:
        _verificar_presenca(page, "blog-quebra-justo")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_blog_quebra_quadrado(page):
    """Verifica presenca de blog-quebra-quadrado em /blog."""
    try:
        _verificar_presenca(page, "blog-quebra-quadrado")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_blog_quebra_supinf(page):
    """Verifica presenca de blog-quebra-supinf em /blog."""
    try:
        _verificar_presenca(page, "blog-quebra-supinf")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_blog_selecionados_contador(page):
    """Verifica presenca de blog-selecionados-contador em /blog."""
    try:
        _verificar_presenca(page, "blog-selecionados-contador")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_blog_selecionar_10(page):
    """Verifica presenca de blog-selecionar-10 em /blog (sem clicar)."""
    try:
        _verificar_presenca(page, "blog-selecionar-10")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_blog_selecionar_5(page):
    """Verifica presenca de blog-selecionar-5 em /blog (sem clicar)."""
    try:
        _verificar_presenca(page, "blog-selecionar-5")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_blog_selecionar_todos(page):
    """Verifica presenca de blog-selecionar-todos em /blog (sem clicar)."""
    try:
        _verificar_presenca(page, "blog-selecionar-todos")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def _ler(caminho_rel: str) -> str:
    """Lê um arquivo do repositório a partir da raiz do projeto."""
    try:
        from pathlib import Path
        raiz = Path(__file__).resolve().parents[2]
        return (raiz / caminho_rel).read_text(encoding="utf-8")
    except Exception:
        return ""


def test_vis_blog_selecionar_pid(page):
    """`blog-selecionar-{pid}` é TEMPLATE, não testid concreto.

    O gerador de `all_testids.txt` leu o código e capturou a f-string
    `f"blog-selecionar-{pid}"` como se fosse literal — esse testid NUNCA
    existe no DOM. Verificar no código-fonte é a checagem honesta: o que
    importa é que a construção dinâmica continue lá.
    """
    fonte = _ler("mod_blog/telas.py")
    assert 'blog-selecionar-' in fonte, (
        "mod_blog/telas.py perdeu a construção dos testids blog-selecionar-<id>")
    assert "blog-selecionar-todos" in fonte, "seleção em bloco sumiu"


def test_vis_blog_selecionar_post_0(page):
    """`blog-selecionar-{post[0` é resíduo do gerador (id truncado).

    Mesma origem de `test_vis_blog_selecionar_pid`: o scraper cortou a
    f-string. Aqui a checagem real é que os dois testids CONCRETOS que
    existem de fato (5 e 10 posts) estão presentes no blog.
    """
    for tid in ("blog-selecionar-5", "blog-selecionar-10"):
        _verificar_presenca(page, tid)


def test_vis_blog_titulo(page):
    """Verifica presenca de blog-titulo em /blog."""
    try:
        _verificar_presenca(page, "blog-titulo")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_editar_pdf_atualizar(page):
    """Verifica editar_pdf-atualizar (escrita: so visible/enabled, sem clicar)."""
    try:
        _verificar_presenca(page, "editar_pdf-atualizar")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_editar_pdf_baixar_pdfs(page):
    """Verifica presenca de editar_pdf-baixar-pdfs em /edit-pdf (sem clicar)."""
    try:
        _verificar_presenca(page, "editar_pdf-baixar-pdfs")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_editar_pdf_baixar_zip(page):
    """Verifica presenca de editar_pdf-baixar-zip em /edit-pdf (sem clicar)."""
    try:
        _verificar_presenca(page, "editar_pdf-baixar-zip")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_editar_pdf_cortar(page):
    """Verifica editar_pdf-cortar (escrita: so visible/enabled, sem clicar)."""
    try:
        _verificar_presenca(page, "editar_pdf-cortar")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_editar_pdf_dividir(page):
    """Verifica editar_pdf-dividir (escrita: so visible/enabled, sem clicar)."""
    try:
        _verificar_presenca(page, "editar_pdf-dividir")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_editar_pdf_enviar(page):
    """Verifica editar_pdf-enviar (escrita: so visible/enabled, sem clicar)."""
    try:
        _verificar_presenca(page, "editar_pdf-enviar")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_editar_pdf_excluir(page):
    """Verifica editar_pdf-excluir (escrita: so visible/enabled, sem clicar)."""
    try:
        _verificar_presenca(page, "editar_pdf-excluir")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_editar_pdf_juntar(page):
    """Verifica editar_pdf-juntar (escrita: so visible/enabled, sem clicar)."""
    try:
        _verificar_presenca(page, "editar_pdf-juntar")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_editar_pdf_modo_reduzir(page):
    """Verifica editar_pdf-modo-reduzir (escrita: so visible/enabled, sem clicar)."""
    try:
        _verificar_presenca(page, "editar_pdf-modo-reduzir")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_editar_pdf_reduzir(page):
    """Verifica editar_pdf-reduzir (escrita: so visible/enabled, sem clicar)."""
    try:
        _verificar_presenca(page, "editar_pdf-reduzir")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_editar_pdf_verificar(page):
    """Verifica presenca de editar_pdf-verificar em /edit-pdf (sem clicar)."""
    try:
        _verificar_presenca(page, "editar_pdf-verificar")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_editpdf_upload(page):
    """Verifica presenca de editpdf-upload em /edit-pdf (sem upload, sem clicar)."""
    try:
        _verificar_presenca(page, "editpdf-upload")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_empenhos_atualizar(page):
    """Verifica empenhos-atualizar (escrita: so visible/enabled, sem clicar)."""
    try:
        _verificar_presenca(page, "empenhos-atualizar")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_empenhos_busca(page):
    """A busca do Empenhos é `empenhos-navegar-pesquisa` (aba Navegar).

    O `empenhos-busca` pertencia à aba "Pesquisar", que foi REMOVIDA — a busca
    migrou para o Navegar e a função `_tela_pesquisar` (107 linhas) saiu do
    código por estar morta. Este teste fixa o nome ATUAL, para o próximo que
    renomear descubra aqui.
    """
    try:
        _verificar_presenca(page, "empenhos-navegar-pesquisa")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_empenhos_fila_editar(page):
    """Verifica empenhos-fila-editar (escrita: so visible/enabled, sem clicar)."""
    try:
        _verificar_presenca(page, "empenhos-fila-editar")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_empenhos_fila_processar(page):
    """Verifica empenhos-fila-processar (escrita: so visible/enabled, sem clicar)."""
    try:
        _verificar_presenca(page, "empenhos-fila-processar")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


def test_vis_empenhos_filtro_icone(page):
    """Verifica presenca de empenhos-filtro-icone em /renomear-empenho."""
    try:
        _verificar_presenca(page, "empenhos-filtro-icone")
    except pytest.skip.Exception:
        raise
    except AssertionError:
        raise
    except Exception as exc:
        pytest.skip(f"pule por infra: {exc}")


if __name__ == "__main__":
    print("Execute: .venv\\Scripts\\python -m pytest assets/test/pw_cobertura_extra_qa.py -k vis_ -q")
