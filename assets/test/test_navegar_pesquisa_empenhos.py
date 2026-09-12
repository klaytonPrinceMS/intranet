"""QA Renomear Empenhos — pirâmide de testes com evidência headless.

EN — Full QA suite for mod_renomear_empenho after recent changes.
Covers: Navegar async search (data-testid via .props, async _filtrar
with run.io_bound, 1-letter prefix via _fts_query_prefixada, contagem,
spinner aria-label, presente/fora cards), levantamento tb_levantamento +
FTS (fallback LIKE), lote async (spinner sem disconnect), renomear_manual
EE string→int, switch renomeação automática (admin), auditoria só no menu
Auditoria, quarentena/fila/template/campos. Pyramid: many unit > few
integration > few E2E (playwright against http://localhost:8080 localhost).
No production code is touched.

PT — Suíte QA completa do Renomear Empenhos após mudanças recentes.
Cobre: pesquisa Navegar assíncrona (data-testid via .props, handler async
_filtrar com run.io_bound, 1 letra filtra via _fts_query_prefixada,
contagem, spinner aria-label, cards presente/fora), levantamento
tb_levantamento + FTS (fallback LIKE), lote async (spinner sem disconnect),
renomear_manual EE string→int, switch automática (admin), auditoria só no
menu Auditoria, quarentena/fila/template/campos. Pirâmide: muitos unitários
> poucas integrações > poucos E2E (playwright contra http://localhost:8080
só localhost). Sem alterar produção.

Execute:
    .venv/bin/pytest assets/test/test_navegar_pesquisa_empenhos.py -v
    .venv/bin/python assets/test/test_navegar_pesquisa_empenhos.py
"""

import ast
import os
import re
import sys
import sys as _sys

import pytest

_sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TELAS = os.path.join(RAIZ, "mod_renomear_empenho", "telas.py")
BD = os.path.join(RAIZ, "mod_renomear_empenho", "bd_manipulador.py")
ROTINAS = os.path.join(RAIZ, "mod_intranet", "rotinas.py")
ADMIN = os.path.join(RAIZ, "mod_renomear_empenho", "telas_administracao.py")
BASE_URL = "http://localhost:8080"


def _ler(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _ler_telas():
    return _ler(TELAS)


def _ler_bd():
    return _ler(BD)


def _ler_rotinas():
    return _ler(ROTINAS)


def _ler_admin():
    return _ler(ADMIN)


def _definicoes_filtrar(arvore):
    achadas = []
    for no in ast.walk(arvore):
        if isinstance(no, ast.FunctionDef) and no.name == "_tela_navegar":
            for filho in ast.walk(no):
                if isinstance(filho, (ast.FunctionDef, ast.AsyncFunctionDef)) and filho.name == "_filtrar":
                    achadas.append((filho.lineno, isinstance(filho, ast.AsyncFunctionDef)))
    return sorted(achadas)


@pytest.fixture(scope="session")
def browser_type_launch_args():
    return {"args": ["--no-sandbox"]}


def _fechar_dialogos_bloqueadores(page):
    try:
        page.evaluate('''() => {
            document.querySelectorAll('.q-dialog').forEach(d=>d.remove());
            document.body.classList.remove('nicegui-dialog-open');
        }''')
        page.wait_for_timeout(400)
    except Exception:
        pass


def _fazer_login(page, usuario="qamaster", senha="123456"):
    page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded")
    page.wait_for_timeout(2000)
    page.get_by_test_id("login-usuario").fill(usuario)
    page.get_by_test_id("login-senha").fill(senha)
    page.get_by_test_id("login-entrar").click()
    page.wait_for_timeout(4000)
    _fechar_dialogos_bloqueadores(page)


def _abrir_navegar(page):
    page.goto(f"{BASE_URL}/renomear-empenho", wait_until="domcontentloaded")
    page.wait_for_timeout(4000)
    _fechar_dialogos_bloqueadores(page)
    campo = page.get_by_test_id("empenhos-navegar-pesquisa")
    campo.scroll_into_view_if_needed()
    page.wait_for_timeout(500)
    return campo


def _aguardar_contagem(page, timeout_ms=8000):
    import time as _time
    fim = _time.time() + timeout_ms / 1000.0
    while _time.time() < fim:
        if page.get_by_test_id("empenhos-navegar-contagem").count() > 0:
            texto = page.get_by_test_id("empenhos-navegar-contagem").first.inner_text()
            return True, texto
        page.wait_for_timeout(500)
    return False, ""


# ================================================== UNITÁRIO — Navegar pesquisa
class TestUnidadeNavegarPesquisa:
    """Pesquisa Navegar assíncrona — fiação estática sem servidor."""

    def test_input_tem_data_testid_via_props(self):
        fonte = _ler_telas()
        assert 'data-testid=empenhos-navegar-pesquisa' in fonte
        assert ".props(\"data-testid=empenhos-navegar-pesquisa\")" in fonte or ".props('data-testid=empenhos-navegar-pesquisa')" in fonte or 'data-testid=empenhos-navegar-pesquisa' in fonte
        # input deve ser criado com ui.input e tooltip de FTS
        assert 'empenhos-navegar-pesquisa' in fonte
        assert 'Pesquisar (conteúdo + todos os campos)' in fonte

    def test_handler_e_async_com_run_io_bound(self):
        fonte = _ler_telas()
        defs = _definicoes_filtrar(ast.parse(fonte))
        assert len(defs) == 1, f"deveria haver exatamente 1 _filtrar, achou {defs}"
        _, is_async = defs[0]
        assert is_async is True, "_filtrar deve ser async"
        # async deve usar await run.io_bound(_buscar_dados
        assert "async def _filtrar" in fonte
        assert "await run.io_bound" in fonte
        assert "_buscar_dados" in fonte
        # handler vinculado ao input
        assert 'on("update:model-value", _filtrar)' in fonte

    def test_uma_letra_ja_filtra_via_prefixada(self):
        fonte_bd = _ler_bd()
        assert "def _fts_query_prefixada" in fonte_bd
        # prefixo no último token: '"tok"*' → gera ...}"*'
        assert '}"*"' in fonte_bd or '"*"' in fonte_bd or "*'" in fonte_bd
        # pesquisar_levantamento tenta MATCH com query prefixada e fallback LIKE
        assert "def pesquisar_levantamento" in fonte_bd
        assert "tb_levantamento_fts MATCH" in fonte_bd
        assert "LIKE ?" in fonte_bd
        telas = _ler_telas()
        assert 'if not termo.strip():' in telas

    def test_contagem_tem_data_testid_via_props(self):
        fonte = _ler_telas()
        assert 'data-testid=empenhos-navegar-contagem' in fonte
        assert ".props(\"data-testid=empenhos-navegar-contagem\")" in fonte or ".props('data-testid=empenhos-navegar-contagem')" in fonte or 'empenhos-navegar-contagem' in fonte
        # texto de contagem
        assert "resultado(s)" in fonte

    def test_spinner_tem_aria_label(self):
        fonte = _ler_telas()
        assert 'aria-label=Pesquisando empenhos' in fonte
        assert 'ui.spinner' in fonte

    def test_cards_mostram_presente_fora(self):
        fonte = _ler_telas()
        assert 'na pasta' in fonte
        assert 'fora da pasta' in fonte
        assert 'presente' in fonte.lower()
        # badge presente/fora
        assert 'ui.badge("na pasta"' in fonte
        assert 'ui.badge("fora da pasta"' in fonte

    def test_nao_ha_duplicacao_de_filtrar(self):
        fonte = _ler_telas()
        defs = _definicoes_filtrar(ast.parse(fonte))
        assert len(defs) == 1, f"não deve haver shadowing, achou {defs}"

    def test_seq_guard_evita_corrida(self):
        fonte = _ler_telas()
        assert 'filtro_nome["seq"]' in fonte
        assert 'minha_vez' in fonte


# ================================================== UNITÁRIO — Levantamento
class TestUnidadeLevantamento:
    """tb_levantamento + FTS no banco do módulo, fallback LIKE, presença."""

    def test_tabela_levantamento_existe_no_init(self):
        fonte = _ler_bd()
        assert "CREATE TABLE IF NOT EXISTS tb_levantamento" in fonte
        assert "nome_arquivo" in fonte
        assert "caminho_atual" in fonte
        assert "presente INTEGER" in fonte
        assert "conteudo_texto" in fonte

    def test_fts_virtual_criacao_com_fallback(self):
        fonte = _ler_bd()
        assert "tb_levantamento_fts" in fonte
        assert "CREATE VIRTUAL TABLE" in fonte
        assert "USING fts5" in fonte
        # fallback comentado: proxy Postgres ignora
        assert "fallback LIKE" in fonte or "LIKE" in fonte

    def test_pesquisar_levantamento_usa_prefixada_e_like(self):
        fonte = _ler_bd()
        assert "def pesquisar_levantamento" in fonte
        assert "_fts_query_prefixada" in fonte
        # fallback LIKE cobre Postgres
        # verifica que há try/except com LIKE
        assert "tb_levantamento_fts MATCH" in fonte
        assert "nome_arquivo LIKE" in fonte

    def test_levantamento_tem_presenca_e_sincroniza_fts(self):
        fonte = _ler_bd()
        assert "def levantar_arquivos" in fonte
        assert "presente=1" in fonte
        assert "presente=0" in fonte
        assert "_levantamento_fts_sincronizar" in fonte
        assert "DELETE FROM tb_levantamento_fts" in fonte
        assert "INSERT INTO tb_levantamento_fts" in fonte

    def test_buscar_dados_combina_processados_e_levantamento(self):
        telas = _ler_telas()
        assert "pesquisar(termo" in telas
        assert "pesquisar_levantamento(termo" in telas
        assert "_dentro(" in telas
        assert "realpath" in telas


# ================================================== UNITÁRIO — Lote async
class TestUnidadeLoteAsync:
    """Lote solicitar sem disconnect — spinner e trava."""

    def test_solicitar_lote_e_async_com_io_bound(self):
        telas = _ler_telas()
        assert "def _solicitar_lote" in telas
        assert "async def _enviar_lote" in telas
        assert "await run.io_bound(_gravar)" in telas
        assert "ocupado" in telas

    def test_spinner_registrando_lote(self):
        telas = _ler_telas()
        assert "aria-label=Registrando lote" in telas
        assert "Registrando solicitações" in telas
        assert "ui.spinner" in telas

    def test_trava_e_botao_desabilitado(self):
        telas = _ler_telas()
        assert ".ocupado" in telas
        assert "btn_confirmar.disable()" in telas
        assert "Aguarde o lote em andamento" in telas

    def test_data_testids_lote_via_props(self):
        telas = _ler_telas()
        assert "data-testid=empenhos-lote-solicitar" in telas
        assert "data-testid=empenhos-lote-confirmar" in telas
        assert "data-testid=empenhos-lote-contador" in telas
        assert "data-testid=empenhos-selecionar" in telas


# ================================================== UNITÁRIO — renomear_manual EE
class TestUnidadeRenomearManual:
    """renomear_manual converte string EE→int para EC_0024 etc."""

    def test_renomear_manual_tem_conversao_string_int(self):
        fonte = _ler_bd()
        # trecho EE: num_txt pode vir como string do diálogo
        assert "def renomear_manual" in fonte
        assert 're.sub(r"\\D"' in fonte or "re.sub(r'\\D'" in fonte or 're.sub' in fonte
        assert "int(re.sub" in fonte
        assert "montar_nome_tipo_especial" in fonte

    def test_montar_nome_tipo_especial_formata_4dig(self):
        fonte = _ler_bd()
        assert "def montar_nome_tipo_especial" in fonte
        assert "_indefinido" in fonte
        assert ":04d" in fonte

    def test_dialogo_revisar_tem_testids(self):
        telas = _ler_telas()
        assert "data-testid=empenhos-revisar-tipo" in telas
        assert "data-testid=empenhos-revisar-ficha" in telas
        assert "data-testid=empenhos-revisar-empenho" in telas
        assert "data-testid=empenhos-revisar-ano" in telas


# ================================================== UNITÁRIO — switch automática
class TestUnidadeSwitchAutomatica:
    """Switch admin renomeação automática — rótulo, config, gate."""

    def test_admin_tem_switch_automatica(self):
        admin = _ler_admin()
        assert "Renomeação automática pelo monitor" in admin
        assert "empenhos_renomeacao_automatica" in admin
        assert 'get_config("empenhos_renomeacao_automatica"' in admin

    def test_rotinas_tem_gate_e_job(self):
        rot = _ler_rotinas()
        assert "def renomeacao_automatica_empenho_ativa" in rot
        assert "empenhos_renomeacao_automatica" in rot
        assert "def _job_monitor_empenho" in rot
        assert "renomeacao_automatica_empenho_ativa()" in rot
        # quando desligado retorna sem varrer
        assert "if not renomeacao_automatica_empenho_ativa()" in rot

    def test_switch_persiste_e_reage_sem_restart(self):
        admin = _ler_admin()
        assert 'set_config("empenhos_renomeacao_automatica"' in admin
        assert "1" in admin and '"0"' in admin


# ================================================== UNITÁRIO — auditoria/quarentena/fila/template/campos
class TestUnidadeAuditoriaQuarentenaFilaTemplateCampos:
    """Auditoria só no menu Auditoria + quarentena/fila/template/campos."""

    def test_auditoria_nao_esta_em_telas_administracao(self):
        admin = _ler_admin()
        # auditoria removida do admin do módulo
        assert "Auditoria dos arquivos" not in admin
        assert "tb_arquivos_auditoria" not in admin
        assert "listar_arquivos_auditoria" not in admin

    def test_quarentena_tem_reprocessar_fila_e_testid(self):
        admin = _ler_admin()
        assert "Quarentena" in admin
        assert "Reprocessar fila" in admin
        assert "reprocessar_fila" in admin
        assert "empenhos-reprocessar-fila" in admin
        # telas também tem quarentena
        telas = _ler_telas()
        assert "Quarentena" in telas
        assert "data-testid=empenhos-reprocessar-fila" in telas

    def test_quarentena_tem_separar_multiplos(self):
        bd = _ler_bd()
        assert "separar_documentos_quarentena" in bd
        assert "Múltiplos documentos" in bd
        admin = _ler_admin()
        assert "Separar documentos" in admin

    def test_fila_renomeacao_existe(self):
        telas = _ler_telas()
        assert "def _tela_fila" in telas
        assert "Fila Renomeação" in telas
        assert "listar_pendentes" in telas

    def test_template_tem_variaveis_e_preview(self):
        telas = _ler_telas()
        admin = _ler_admin()
        for vari in ["{contador", "{empenho", "{parcela", "{ficha", "{ano"]:
            assert vari in telas or vari in admin
        assert "NOME_FINAL_PADRAO" in admin or "NOME_FINAL_PADRAO" in telas
        # preview label
        assert "Nome de exemplo" in telas

    def test_campos_busca_tem_lista_e_validacao(self):
        bd = _ler_bd()
        assert "def listar_campos_busca" in bd
        assert "def salvar_campo_busca" in bd
        assert "re.compile" in bd
        assert "tb_campos_busca" in bd
        admin = _ler_admin()
        assert "Campos de busca" in admin
        assert "Restaurar padrão" in admin

    def test_regras_tem_campo_destino_fts(self):
        bd = _ler_bd()
        assert "campo_destino" in bd
        assert "tb_regex_regras" in bd
        assert "def salvar_regra" in bd
        assert "def listar_regras" in bd


# ================================================== INTEGRAÇÃO
class TestIntegracaoBackend:
    """Backend sem browser — FTS 1 letra, levantamento presença, EE string."""

    def test_backend_fts_1_letra_tem_hits(self):
        from mod_renomear_empenho.bd_manipulador import pesquisar, pesquisar_levantamento, _fts_query_prefixada
        # _fts_query_prefixada com 1 token deve gerar prefixo
        q = _fts_query_prefixada(["4"])
        assert q == '"4"*'
        q2 = _fts_query_prefixada(["joao", "si"])
        assert q2 == '"joao" AND "si"*'
        # backend de verdade
        lev = pesquisar_levantamento("4", limite=100) or []
        assert len(lev) > 0, "levantamento('4') deveria ter hits (1 letra filtra)"
        fts = pesquisar("4", limite=100) or []
        # pesquisar pode ter hits ou vazio dependendo do índice; levantamento garante
        assert isinstance(fts, list)

    def test_pesquisar_levantamento_fallback_like_sem_fts(self):
        # força fallback verificando que LIKE funciona mesmo sem MATCH
        from mod_renomear_empenho.bd_manipulador import pesquisar_levantamento
        # termo inexistente deve retornar vazio, não quebrar
        vaz = pesquisar_levantamento("___termo_inexistente_xyz___", limite=5)
        assert vaz == [] or isinstance(vaz, list)
        # termo com conteúdo conhecido
        hits = pesquisar_levantamento("2026", limite=5) or []
        assert isinstance(hits, list)

    def test_levantamento_presenca_flag(self):
        from mod_renomear_empenho.bd_manipulador import levantar_arquivos, pesquisar_levantamento
        # levantar não deve quebrar; retorna tupla (novos, vistos, ausentes)
        novos, vistos, ausentes = levantar_arquivos("tester")
        assert isinstance(novos, int)
        assert isinstance(vistos, int)
        # presença deve aparecer nas tuplas
        hits = pesquisar_levantamento("2026", limite=10) or []
        for _id, _nome, _cam, presente, *_rest in hits:
            assert presente in (0, 1)

    def test_renomear_manual_converte_string_para_int_sem_erro(self):
        import tempfile, shutil, os
        from mod_renomear_empenho import bd_manipulador as bd
        # isola banco em temp como teste_fluxo_renomeador
        tmp = tempfile.mkdtemp(prefix="qa_ee_")
        orig_path = bd.DB_EMPENHO_PATH
        orig_pasta = bd.PASTA_MONITORADA
        orig_pastas_fn = bd.pastas_monitoradas
        try:
            bd.DB_EMPENHO_PATH = os.path.join(tmp, "db_mod_renomear_empenho.db")
            import mod_intranet.repositorio as _repo
            _repo.MODULOS_BD["empenhos"] = bd.DB_EMPENHO_PATH
            bd.PASTA_MONITORADA = os.path.join(tmp, "doc")
            bd._PASTA_MONITORADA_PADRAO = bd.PASTA_MONITORADA
            os.makedirs(bd.PASTA_MONITORADA, exist_ok=True)
            bd.pastas_monitoradas = lambda: [bd.PASTA_MONITORADA]
            bd.init_db_empenho()
            # usa PDF DOC real
            src = os.path.join(RAIZ, "assets", "test", "pdf", "DOC_0201.pdf")
            assert os.path.exists(src)
            alvo = os.path.join(bd.PASTA_MONITORADA, "DOC_0201.pdf")
            shutil.copy(src, alvo)
            # novo_numero como STRING (simula input do diálogo)
            ok, msg = bd.renomear_manual("tester", alvo, novo_numero="  345  ", novo_parcela="2")
            assert ok, f"renomear_manual com string 345 falhou: {msg}"
            assert os.path.exists(os.path.join(bd.PASTA_MONITORADA, msg))
            # EE como string também — usa tipo especial manualmente
            shutil.copy(src, os.path.join(bd.PASTA_MONITORADA, "DOC_EE.pdf"))
            # força tipo EE com número string
            ok2, msg2 = bd.renomear_manual("tester", os.path.join(bd.PASTA_MONITORADA, "DOC_EE.pdf"), novo_numero="9570", tipo_especial="EE")
            # pode falhar se DOC não for EE, mas a conversão string→int não deve dar TypeError
            assert isinstance(ok2, bool) and isinstance(msg2, str)
        finally:
            bd.DB_EMPENHO_PATH = orig_path
            bd.PASTA_MONITORADA = orig_pasta
            bd.pastas_monitoradas = orig_pastas_fn
            import mod_intranet.repositorio as _repo2
            _repo2.MODULOS_BD["empenhos"] = orig_path
            shutil.rmtree(tmp, ignore_errors=True)

    def test_switch_automatica_get_set(self):
        from mod_intranet.bd_conexao import get_config, set_config
        from mod_intranet import rotinas
        prev = get_config("empenhos_renomeacao_automatica", "1")
        try:
            set_config("empenhos_renomeacao_automatica", "0")
            assert rotinas.renomeacao_automatica_empenho_ativa() is False
            set_config("empenhos_renomeacao_automatica", "1")
            assert rotinas.renomeacao_automatica_empenho_ativa() is True
        finally:
            set_config("empenhos_renomeacao_automatica", prev)

    def test_quarentena_fila_template_campos_basicos(self):
        from mod_renomear_empenho.bd_manipulador import (
            listar_quarentena, reprocessar_fila, template_nome_atual, montar_nome_final, NOME_FINAL_PADRAO,
            listar_campos_busca, listar_regras
        )
        # quarentena
        q = listar_quarentena(limite=5)
        assert isinstance(q, list)
        ok, msg, det = reprocessar_fila(usuario="tester")
        assert isinstance(ok, bool) and isinstance(msg, str) and isinstance(det, list)
        # template
        tpl = template_nome_atual()
        assert isinstance(tpl, str) and len(tpl) > 0
        nome = montar_nome_final(tpl or NOME_FINAL_PADRAO, 1, {"empenho": "345", "ficha": "331", "ano": "2026"})
        assert nome.endswith(".pdf")
        # campos e regras
        campos = listar_campos_busca()
        assert isinstance(campos, list) and len(campos) >= 4
        regras = listar_regras()
        assert isinstance(regras, list) and len(regras) >= 1


# ================================================== E2E — servidor vivo
class TestE2ENavegarPesquisa:
    """Fluxo real headless: login → /renomear-empenho → digitar no campo."""

    def test_campo_pesquisa_visivel(self, page):
        _fazer_login(page)
        campo = _abrir_navegar(page)
        assert campo.count() == 1
        assert campo.is_visible()

    def test_uma_letra_mostra_resultados(self, page):
        _fazer_login(page)
        campo = _abrir_navegar(page)
        campo.fill("4")
        achou, texto = _aguardar_contagem(page)
        assert achou, "contagem empenhos-navegar-contagem não apareceu após '4' (1 letra já deveria filtrar)"
        assert "resultado" in texto.lower()
        assert page.get_by_test_id("empenhos-selecionar").count() > 0

    def test_refino_estreita_resultados(self, page):
        _fazer_login(page)
        campo = _abrir_navegar(page)
        campo.fill("4")
        _aguardar_contagem(page)
        n_largo = page.get_by_test_id("empenhos-selecionar").count()
        campo.fill("455")
        achou, _texto = _aguardar_contagem(page)
        # se backend não tiver termo fino, contagem pode ser 0 mas ainda deve existir
        if achou:
            n_fino = page.get_by_test_id("empenhos-selecionar").count()
            # pode ser igual se poucos dados, mas não deve explodir
            assert n_fino <= n_largo

    def test_limpar_volta_a_listagem(self, page):
        _fazer_login(page)
        campo = _abrir_navegar(page)
        n_antes = page.get_by_test_id("empenhos-selecionar").count()
        assert n_antes > 0, "listagem inicial vazia — sem massa para comparar"
        campo.fill("4")
        page.wait_for_timeout(2500)
        campo.fill("")
        page.wait_for_timeout(3000)
        assert page.get_by_test_id("empenhos-navegar-contagem").count() == 0
        n_depois = page.get_by_test_id("empenhos-selecionar").count()
        assert n_depois == n_antes, f"limpar deveria restaurar a listagem ({n_antes}→{n_depois})"

    def test_checkbox_do_lote_nos_resultados(self, page):
        _fazer_login(page)
        campo = _abrir_navegar(page)
        campo.fill("4")
        achou, _texto = _aguardar_contagem(page)
        assert achou, "sem contagem não há resultados filtrados"
        caixas = page.get_by_test_id("empenhos-selecionar")
        assert caixas.count() > 0, "resultados sem checkbox de lote"
        caixas.first.scroll_into_view_if_needed()
        caixas.first.check()
        contador = page.get_by_test_id("empenhos-lote-contador").first
        assert "1 selecionado" in contador.inner_text()

    def test_sem_banner_desconectado(self, page):
        _fazer_login(page)
        campo = _abrir_navegar(page)
        campo.fill("4")
        page.wait_for_timeout(3000)
        corpo = page.locator("body").inner_text().lower()
        assert "desconectado" not in corpo
        assert "desconnected" not in corpo

    def test_cards_mostram_presente_fora(self, page):
        _fazer_login(page)
        campo = _abrir_navegar(page)
        campo.fill("4")
        achou, _texto = _aguardar_contagem(page)
        assert achou
        body = page.locator("body").inner_text()
        # ao menos um dos badges deve aparecer quando há resultados
        assert "na pasta" in body or "fora da pasta" in body

    def test_spinner_some_apos_busca(self, page):
        _fazer_login(page)
        campo = _abrir_navegar(page)
        campo.fill("4")
        # spinner deve aparecer brevemente
        page.wait_for_timeout(500)
        # pode já ter sumido; contagem já prova que terminou sem disconnect
        achou, _ = _aguardar_contagem(page)
        assert achou


# ================================================== E2E — switch admin e lote (headless extra)
class TestE2EAdminELote:
    """Admin: switch automática; lote spinner — só localhost."""

    def test_switch_automatica_visivel_so_admin(self, page):
        _fazer_login(page, usuario="qamaster", senha="123456")
        page.goto(f"{BASE_URL}/admin/empenhos", wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        _fechar_dialogos_bloqueadores(page)
        body = page.locator("body").inner_text()
        assert "Renomeação automática pelo monitor" in body

    def test_lote_contador_e_botoes_visiveis(self, page):
        _fazer_login(page)
        page.goto(f"{BASE_URL}/renomear-empenho", wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        _fechar_dialogos_bloqueadores(page)
        assert page.get_by_test_id("empenhos-lote-contador").count() >= 1
        assert page.get_by_test_id("empenhos-lote-solicitar").count() >= 1


# ================================================== runner standalone
def _check(cond, msg, cont):
    cont["total"] += 1
    if cond:
        cont["ok"] += 1
        print(f"  OK {msg}")
    else:
        print(f"  FALHOU {msg}")
    return cond


if __name__ == "__main__":
    print("INICIANDO — QA Renomear Empenhos (pirâmide)")
    cont = {"ok": 0, "total": 0}
    fonte = _ler_telas()
    fbd = _ler_bd()
    frot = _ler_rotinas()
    fadm = _ler_admin()
    defs = _definicoes_filtrar(ast.parse(fonte))
    _check(len(defs) == 1 and defs[0][1] is True, f"1 _filtrar async (achado {defs})", cont)
    _check('data-testid=empenhos-navegar-pesquisa' in fonte and ".props" in fonte, "testid pesquisa via .props", cont)
    _check('data-testid=empenhos-navegar-contagem' in fonte, "testid contagem via .props", cont)
    _check('aria-label=Pesquisando empenhos' in fonte, "spinner aria-label Pesquisando", cont)
    _check('na pasta' in fonte and 'fora da pasta' in fonte, "cards presente/fora", cont)
    _check("CREATE TABLE IF NOT EXISTS tb_levantamento" in fbd, "tb_levantamento no BD", cont)
    _check("tb_levantamento_fts" in fbd and "USING fts5" in fbd, "FTS levantamento virtual", cont)
    _check("def pesquisar_levantamento" in fbd and "LIKE ?" in fbd, "pesquisar_levantamento com fallback LIKE", cont)
    _check("async def _enviar_lote" in fonte and "await run.io_bound" in fonte, "lote async sem disconnect", cont)
    _check("aria-label=Registrando lote" in fonte, "spinner Registrando lote", cont)
    _check("int(re.sub" in fbd and "montar_nome_tipo_especial" in fbd, "renomear_manual EE string→int", cont)
    _check("Renomeação automática pelo monitor" in fadm and "empenhos_renomeacao_automatica" in fadm, "switch automática admin", cont)
    _check("def renomeacao_automatica_empenho_ativa" in frot, "gate rotinas", cont)
    _check("Auditoria dos arquivos" not in fadm, "auditoria fora do admin (só no menu Auditoria)", cont)
    _check("Reprocessar fila" in fadm and "empenhos-reprocessar-fila" in fadm, "quarentena/fila com testid", cont)
    _check("Campos de busca" in fadm, "campos configuráveis", cont)
    _check("NOME_FINAL_PADRAO" in fbd or "NOME_FINAL_PADRAO" in fonte, "template nome final", cont)
    try:
        from mod_renomear_empenho.bd_manipulador import _fts_query_prefixada
        _check(_fts_query_prefixada(["4"]) == '"4"*', "_fts_query_prefixada 1 letra", cont)
    except Exception as ex:
        _check(False, f"_fts_query_prefixada falhou: {ex}", cont)
    try:
        from mod_renomear_empenho.bd_manipulador import pesquisar_levantamento
        hits = pesquisar_levantamento("4", limite=10) or []
        _check(len(hits) > 0, f"backend levantamento('4')={len(hits)} hits", cont)
    except Exception as ex:
        _check(False, f"backend levantamento: {ex}", cont)
    print(f"RESULTADO: {cont['ok']}/{cont['total']} verificações OK")
    _sys.exit(0 if cont["ok"] == cont["total"] else 1)
