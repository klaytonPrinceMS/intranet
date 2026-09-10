"""Teste do módulo Solicitação de Impressão (mod_solicita_impressao).

Valida: banco, contagem de páginas, fórmula, cotas, fluxo de solicitação,
autorização, impressão, recuo e marca d'água.

Execute: .venv/bin/python test/test_solicita_impressao.py
"""
import sys
import os
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from mod_solicita_impressao import bd_manipulador as bd


def criar_pdf_teste(caminho, n_paginas=3):
    """Gera um PDF simples de n_paginas para teste (PyMuPDF)."""
    try:
        import fitz
        doc = fitz.open()
        for i in range(n_paginas):
            page = doc.new_page()
            page.insert_text((72, 72), f"Pagina de teste {i+1}")
        doc.save(caminho)
        doc.close()
        return True
    except Exception as e:
        print(f"  [WARN] nao foi possivel gerar PDF: {e}")
        return False


def teste_contagem_e_formula():
    print("\n=== Teste: contagem de páginas e fórmula ===")
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    tmp.close()
    assert criar_pdf_teste(tmp.name, 10), "Falha ao criar PDF"
    n = bd.contar_paginas_pdf(tmp.name)
    assert n == 10, f"Contagem esperada 10, recebida {n}"
    print(f"  OK contagem = {n}")

    casos = [
        ("A4 frente 3cop", 10, 3, "A4", False, 30),
        ("A4 fv 3cop", 10, 3, "A4", True, 60),
        ("A3 frente 3cop", 10, 3, "A3", False, 60),
        ("A3 fv 3cop", 10, 3, "A3", True, 120),
    ]
    for nome, pag, cop, papel, fv, esp in casos:
        calc = bd.calcular_paginas_contabilizadas(pag, cop, papel, fv)
        assert calc == esp, f"{nome}: esperado {esp}, recebido {calc}"
        print(f"  OK {nome} = {calc}")
    os.remove(tmp.name)


def teste_cadastros_e_cotas():
    print("\n=== Teste: cadastros e cotas ===")
    bd.init_db()
    # Secretaria
    ok, msg = bd.criar_secretaria("Saúde", "SMS", 100, ator="teste")
    print(f"  criar_secretaria: {ok} {msg}")
    secrs = bd.listar_secretarias(ativo=1)
    assert secrs, "Nenhuma secretaria"
    sid = secrs[0][0]
    # Setor com cota própria
    ok, msg = bd.criar_setor("Atendimento", sid, 50, ator="teste")
    print(f"  criar_setor: {ok} {msg}")
    setores = bd.listar_setores(secretaria_id=sid, ativo=1)
    assert setores, "Nenhum setor"
    stid = setores[0][0]
    # Responsável (a nível de secretaria: cobre a secretaria inteira, inclusive
    # solicitações sem setor — escopo estrito de autorização)
    ok, msg = bd.criar_responsavel("resp_saude", sid, None, ator="teste")
    print(f"  criar_responsavel: {ok} {msg}")
    assert bd.eh_responsavel_autorizacao("resp_saude", sid, stid), "Responsavel nao reconhecido"
    print("  OK responsavel reconhecido")
    # Cota
    ok, msg = bd.definir_cota(sid, None, 100, ator="teste")
    ok2, msg2 = bd.definir_cota(sid, stid, 50, ator="teste")
    print(f"  definir_cota secr: {ok} {msg} | setor: {ok2} {msg2}")
    cota, existe = bd.obter_ou_criar_cota(sid, None)
    assert cota == 100, f"Cota secretaria esperada 100, {cota}"
    cota_s, _ = bd.obter_ou_criar_cota(sid, stid)
    assert cota_s == 50, f"Cota setor esperada 50, {cota_s}"
    print("  OK cotas definidas")
    return sid, stid


def teste_fluxo(sid, stid):
    print("\n=== Teste: fluxo de solicitação ===")
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    tmp.close()
    assert criar_pdf_teste(tmp.name, 5), "Falha PDF"
    # Secretaria tem responsável -> requer autorização (aguardando_autorizacao)
    ok, msg = bd.criar_solicitacao(
        "qacomum", tmp.name, "doc_teste.pdf", 2, "A4", "PB", False, None, True,
        "obs teste", sid, None, ator="qacomum")
    print(f"  criar_solicitacao (com responsavel): {ok} {msg}")
    assert ok, msg
    rows = bd.listar_solicitacoes(usuario="qacomum", status="aguardando_autorizacao")
    assert rows, "Solicitacao deveria aguardar autorizacao"
    sol_id = rows[0][0]
    print(f"  OK solicitacao #{sol_id} aguardando autorizacao")

    # Responsável autoriza
    ok, msg = bd.autorizar_solicitacao(sol_id, "resp_saude")
    print(f"  autorizar (resp_saude): {ok} {msg}")
    assert ok, msg
    rows = bd.listar_solicitacoes(usuario="qacomum", status="autorizado")
    assert rows, "Solicitacao nao autorizada apos responsavel"
    print(f"  OK solicitacao #{sol_id} autorizada pelo responsavel")

    # Imprimir (desconta cota)
    pct0, usado0, cota0 = bd.percentual_consumo(sid, None)
    ok, msg = bd.imprimir_solicitacao(sol_id, "admin_impressao", ator="admin_impressao")
    print(f"  imprimir_solicitacao: {ok} {msg}")
    assert ok, msg
    pct, usado, cota = bd.percentual_consumo(sid, None)
    print(f"  consumo secretaria: {usado}/{cota} ({pct}%)")
    assert usado - usado0 == 10, f"Consumo esperado +10 (5 pag x2 cop), recebido +{usado - usado0}"

    # Recuar
    ok, msg = bd.recuar_solicitacao(sol_id, ator="admin_impressao")
    print(f"  recuar_solicitacao: {ok} {msg}")
    assert ok, msg
    os.remove(tmp.name)


def teste_excedente(sid, stid):
    print("\n=== Teste: excedente de cota ===")
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    tmp.close()
    assert criar_pdf_teste(tmp.name, 5), "Falha PDF"
    # Define cota baixa para forçar excedente
    bd.definir_cota(sid, None, 5, ator="teste")  # 5 < 10 (5 pag x 2 cop)
    ok, msg = bd.criar_solicitacao(
        "qacomum", tmp.name, "doc_exc.pdf", 2, "A4", "PB", False, None, True,
        "teste excedente", sid, None, ator="qacomum")
    print(f"  criar_solicitacao (excedente): {ok} {msg}")
    assert ok, msg
    rows = bd.listar_solicitacoes(usuario="qacomum", apenas_excedentes=True)
    assert rows, "Excedente nao marcado"
    print(f"  OK solicitacao excedente #{rows[0][0]} marcada")
    os.remove(tmp.name)
    # Restaura cota
    bd.definir_cota(sid, None, 100, ator="teste")


def teste_marca_dagua():
    print("\n=== Teste: marca d'água (opcional) ===")
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    tmp.close()
    assert criar_pdf_teste(tmp.name, 1), "Falha PDF"
    bd.definir_config("marca_dagua_ativa", "1")
    saida = bd.aplicar_marca_dagua(tmp.name, 999, "admin_impressao", "Saude", "Atend",
                                    "qacomum")
    print(f"  marca d'agua aplicada: {saida != tmp.name} (saida={saida})")
    if saida != tmp.name and os.path.exists(saida):
        os.remove(saida)
    bd.definir_config("marca_dagua_ativa", "0")
    saida2 = bd.aplicar_marca_dagua(tmp.name, 999, "admin", "Saude", "Atend", "qacomum")
    assert saida2 == tmp.name, "Marca d'agua deveria estar desativada"
    print("  OK marca d'agua desativada nao altera arquivo")
    os.remove(tmp.name)


def teste_rascunho(sid, stid):
    print("\n=== Teste: rascunho de upload + confirmação + expiração ===")
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    tmp.close()
    assert criar_pdf_teste(tmp.name, 4), "Falha PDF"
    with open(tmp.name, "rb") as f:
        conteudo = f.read()
    # Upload -> rascunho no servidor (nome original descartado)
    rid, nome_servidor, paginas, caminho = bd.registrar_rascunho(
        "qacomum", conteudo, "meu_doc_pessoal.pdf")
    print(f"  registrar_rascunho: rid={rid} nome={nome_servidor} paginas={paginas}")
    assert rid, "Rascunho nao criado"
    assert "meu_doc_pessoal" not in nome_servidor, "Nome original nao deveria ser usado"
    assert os.path.exists(caminho), "Arquivo nao foi para o servidor"
    r = bd.obter_rascunho(rid)
    assert r and r["qtd_paginas_arquivo"] == 4, "Paginas do rascunho incorretas"

    # Cancelar remove arquivo e registro
    ok, msg = bd.cancelar_rascunho(rid)
    print(f"  cancelar_rascunho: {ok} {msg}")
    assert ok, msg
    assert not os.path.exists(caminho), "Arquivo do rascunho nao foi removido"
    assert bd.obter_rascunho(rid) is None, "Rascunho deveria sumir"

    # Novo rascunho e confirmar (vira solicitação com nome final)
    rid, nome_servidor, paginas, caminho = bd.registrar_rascunho(
        "qacomum", conteudo, "outro.pdf")
    ok, msg, sol_id = bd.confirmar_rascunho(
        rid, 2, "A4", "PB", False, None, True, "obs", sid, None, ator="qacomum")
    print(f"  confirmar_rascunho: {ok} {msg}")
    assert ok, msg
    assert bd.obter_rascunho(rid) is None, "Rascunho deveria ser consumido"
    sol = bd.obter_solicitacao(sol_id)
    assert sol and os.path.exists(sol["caminho_arquivo"]), "Solicitacao sem arquivo"
    # Expiração de impressos: autoriza, imprime e força prazo vencido
    bd.autorizar_solicitacao(sol_id, "resp_saude")
    bd.definir_config("tempo_exclui_impresso_min", 1)
    bd.imprimir_solicitacao(sol_id, "admin_impressao")
    # Força expira_em no passado
    import sqlite3
    c = sqlite3.connect(bd.DB_PATH)
    c.execute("UPDATE tb_solicitacoes SET excluir_arquivo_em='2000-01-01 00:00:00' WHERE id=?",
              (sol_id,))
    c.commit(); c.close()
    removidos = bd.expirar_rascunhos_e_impressos()
    print(f"  expirar_rascunhos_e_impressos: {removidos} removidos")
    assert removidos >= 1, "Arquivo impresso nao foi excluido"
    assert not os.path.exists(sol["caminho_arquivo"]), "Arquivo deveria ser excluido"
    os.remove(tmp.name)


def teste_multiplos_arquivos(sid, stid):
    print("\n=== Teste: multiplos arquivos (padrao 10) por solicitacao ===")
    # Simula a tela Nova Solicitacao: cada PDF marcado vira uma solicitacao.
    rids = []
    originais = []
    for i in range(3):
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        tmp.close()
        assert criar_pdf_teste(tmp.name, 2 + i), "Falha PDF"
        with open(tmp.name, "rb") as f:
            conteudo = f.read()
        rid, nome_servidor, paginas, caminho = bd.registrar_rascunho(
            "qacomum", conteudo, f"doc_{i}.pdf")
        assert rid, f"Rascunho {i} nao criado"
        rids.append(rid)
        originais.append(tmp.name)
    antes = len(bd.listar_solicitacoes(usuario="qacomum"))
    for rid in rids:
        ok, msg, sol_id = bd.confirmar_rascunho(
            rid, 1, "A4", "PB", False, None, True, "lote multi", sid, None,
            ator="qacomum")
        assert ok, msg
    depois = len(bd.listar_solicitacoes(usuario="qacomum"))
    assert depois == antes + 3, f"Esperado +3 solicitacoes (antes={antes}, depois={depois})"
    print(f"  OK 3 solicitacoes criadas a partir de multiplos rascunhos")
    for o in originais:
        if os.path.exists(o):
            os.remove(o)


def teste_impressoras_e_busca(sid, stid):
    print("\n=== Teste: impressoras cadastradas e busca ===")
    # Impressoras
    ok, _ = bd.criar_impressora("HP LaserJet PCL6", "A4", "Color", False, True, "PCL6",
                                ator="qamaster")
    assert ok, "Falha ao cadastrar impressora 1"
    ok, _ = bd.criar_impressora("Epson A3", "A3", "PB", True, True, "PCL6",
                                ator="qamaster")
    assert ok, "Falha ao cadastrar impressora 2"
    imps = bd.listar_impressoras(ativo=1)
    assert len(imps) == 2, f"Esperado 2 impressoras, recebido {len(imps)}"
    hp = next((i for i in imps if i[1] == "HP LaserJet PCL6"), None)
    assert hp and hp[6] == "PCL6", "Driver PCL6 não persistido"
    ok, msg = bd.definir_impressora_padrao(hp[0], ator="qamaster")
    assert ok and bd.obter_config("impressora_padrao_nome") == "HP LaserJet PCL6", msg
    ok, _ = bd.excluir_impressora(imps[1][0], ator="qamaster")
    assert ok and len(bd.listar_impressoras()) == 1, "Falha ao excluir impressora"
    print("  OK CRUD de impressoras (driver PCL6, padrão, exclusão)")

    # Nome do arquivo novo (com cor)
    nome = bd.gerar_nome_arquivo("20260907_120000", "joao_silva", 3, 10, sid, None, "Color")
    assert "colorido" in nome, f"Nome de arquivo não traz cor: {nome}"
    nome_pb = bd.gerar_nome_arquivo("20260907_120000", "joao_silva", 3, 10, sid, None, "PB")
    assert "pretoebranco" in nome_pb, f"Nome PB não traz pretoebranco: {nome_pb}"
    print(f"  OK novo padrão de nome com cor: {nome}")

    # Busca por observação e solicitante
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    tmp.close()
    assert criar_pdf_teste(tmp.name, 2), "Falha PDF"
    with open(tmp.name, "rb") as f:
        conteudo = f.read()
    rid, _, _, _ = bd.registrar_rascunho("qacomum", conteudo, "busca.pdf")
    ok, _, sol_id = bd.confirmar_rascunho(rid, 1, "A4", "Color", False, None, True,
                                          "observacao unicateste xyz", sid, None,
                                          ator="qacomum")
    assert ok, "Falha ao criar solicitação para busca"
    rows = bd.listar_solicitacoes(busca="unicateste xyz")
    assert any(r[0] == sol_id for r in rows), "Busca por observação não encontrou"
    rows2 = bd.listar_solicitacoes(busca="qacomum")
    assert any(r[0] == sol_id for r in rows2), "Busca por solicitante não encontrou"
    rows3 = bd.listar_solicitacoes(busca="SECRETARIA_INEXISTENTE_XYZ")
    assert not any(r[0] == sol_id for r in rows3), "Busca retornou resultado incorreto"
    print("  OK busca por observação/solicitante (com filtros negativos)")

    # Migração dos padrões
    bd.definir_config("tempo_expira_rascunho_min", "4")
    bd.definir_config("padrao_cor", "PB")
    bd.init_db()
    assert bd.tempo_expira_rascunho_min() == 10, "Rascunho não migrado para 10"
    assert bd.obter_config("padrao_cor") == "Color", "Cor não migrada para Colorido"
    print("  OK migração de padrões (rascunho 10 min, cor Colorido)")


def teste_relatorio_impressao(sid, stid):
    print("\n=== Teste: relatório de impressões por período ===")
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    tmp.close()
    assert criar_pdf_teste(tmp.name, 3), "Falha PDF"
    # Duas impressões: uma colorida, uma PB
    ids = []
    for cor, copias in (("Color", 2), ("PB", 1)):
        rid, _, _, _ = bd.registrar_rascunho("qacomum", open(tmp.name, "rb").read(), "rel.pdf")
        ok, _, sid_ = bd.confirmar_rascunho(rid, copias, "A4", cor, False, None, True,
                                            "obs rel", sid, None, ator="qacomum")
        assert ok, "Falha criar solicitação para relatório"
        ids.append(sid_)
    # Autoriza e imprime (desconta cota) para entrar no relatório
    for s_ in ids:
        ok, _ = bd.autorizar_solicitacao(s_, "resp_saude")
        assert ok, "Falha autorizar para relatório"
        ok, _ = bd.imprimir_solicitacao(s_, "admin_impressao", ator="admin_impressao")
        assert ok, "Falha imprimir para relatório"

    hoje = bd.datetime.date.today().strftime("%Y-%m-%d")
    antes = bd.relatorio_impressao(hoje, hoje)["geral"]
    # Cria 2 impressões novas (uma color, uma PB) e mede o delta
    ids = []
    for cor, copias in (("Color", 2), ("PB", 1)):
        rid, _, _, _ = bd.registrar_rascunho("qacomum", open(tmp.name, "rb").read(), "rel.pdf")
        ok, _, sid_ = bd.confirmar_rascunho(rid, copias, "A4", cor, False, None, True,
                                            "obs rel", sid, None, ator="qacomum")
        assert ok, "Falha criar solicitação para relatório"
        ids.append(sid_)
    for s_ in ids:
        ok, _ = bd.autorizar_solicitacao(s_, "resp_saude")
        assert ok, "Falha autorizar para relatório"
        ok, _ = bd.imprimir_solicitacao(s_, "admin_impressao", ator="admin_impressao")
        assert ok, "Falha imprimir para relatório"

    rel = bd.relatorio_impressao(hoje, hoje)
    geral = rel["geral"]
    delta = [geral[i] - antes[i] for i in range(len(geral))]
    # delta: num_pedidos, copias_total, copias_color, copias_pb, paginas_total, paginas_color, paginas_pb
    assert delta[0] == 2, f"Esperado +2 pedidos, {delta[0]}"
    assert delta[1] == 3, f"Esperado +3 cópias total (2 color + 1 PB), {delta[1]}"
    assert delta[2] == 2, f"Esperado +2 cópias color, {delta[2]}"
    assert delta[3] == 1, f"Esperado +1 cópia PB, {delta[3]}"
    assert rel["por_secretaria"], "Sem total por secretaria"
    assert rel["por_setor"], "Sem total por setor"
    assert any(r[0] == "resp_saude" for r in rel["por_autorizador"]), "Falta autorizador"
    assert any(r[0] == "admin_impressao" for r in rel["por_impressor"]), "Falta impressor"
    print(f"  OK relatório (delta): {delta}")
    os.remove(tmp.name)


def teste_limite_pedidos_abertos(sid, stid):
    print("\n=== Teste: limite elástico de pedidos abertos ===")
    abertos_antes = bd.contar_pedidos_abertos(sid, None)[0]
    # Define limite = atuais + 2 pedidos abertos para a secretaria
    limite = abertos_antes + 2
    bd.editar_secretaria(sid, limite_pedidos_abertos=limite, ator="teste")
    # Cria 2 pedidos (ficam abertos; agora igual ao limite)
    rids = []
    for i in range(2):
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        tmp.close()
        assert criar_pdf_teste(tmp.name, 2), "Falha PDF"
        rid, _, _, _ = bd.registrar_rascunho("qacomum", open(tmp.name, "rb").read(), f"lim{i}.pdf")
        ok, _, _ = bd.confirmar_rascunho(rid, 1, "A4", "Color", False, None, True,
                                         "obs lim", sid, None, ator="qacomum")
        assert ok, "Falha criar pedido limite"
        rids.append(tmp.name)
    # Terceiro deve ser bloqueado (atingiu o limite)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    tmp.close()
    assert criar_pdf_teste(tmp.name, 2), "Falha PDF"
    rid, _, _, _ = bd.registrar_rascunho("qacomum", open(tmp.name, "rb").read(), "lim3.pdf")
    ok, msg, _ = bd.confirmar_rascunho(rid, 1, "A4", "Color", False, None, True,
                                       "obs lim3", sid, None, ator="qacomum")
    assert not ok, "Terceiro pedido deveria ser bloqueado pelo limite"
    assert "atingido" in msg, f"Mensagem de limite ausente: {msg}"
    print(f"  OK limite {limite} bloqueia pedido além do teto (msg: {msg})")

    # Ao imprimir 1, libera vaga (elástica)
    alvo = None
    for r in bd.listar_solicitacoes(usuario="qacomum", limite=400):
        if r[16] in ("aguardando_autorizacao", "autorizado"):
            alvo = r[0]; break
    if alvo:
        bd.autorizar_solicitacao(alvo, "resp_saude")
        ok, _ = bd.imprimir_solicitacao(alvo, "admin_impressao", ator="admin_impressao")
        assert ok, "Falha imprimir para liberar vaga"
    contagem = bd.contar_pedidos_abertos(sid, None)
    assert contagem[0] <= limite, f"Contagem de abertos {contagem} excedeu limite após impressão"
    print(f"  OK contagem de abertos após impressão: {contagem}")
    bd.editar_secretaria(sid, limite_pedidos_abertos=0, ator="teste")
    for o in rids:
        if os.path.exists(o):
            os.remove(o)


def teste_fluxo_grupo(sid, stid):
    print("\n=== Teste: 1 pedido por envio (grupo) — autorização/impressão em conjunto ===")
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    tmp.close()
    assert criar_pdf_teste(tmp.name, 3), "Falha PDF"
    # 3 arquivos no mesmo envio -> 1 grupo
    rids = []
    for i in range(3):
        rid, _, _, _ = bd.registrar_rascunho("qacomum", open(tmp.name, "rb").read(), f"g{i}.pdf")
        assert rid, f"Rascunho {i} não criado"
        rids.append(rid)
    ok, msg, grupo_id = bd.confirmar_lote(
        "qacomum", rids, 1, "A4", "Color", False, None, True, "grupo teste", sid, stid,
        ator="qacomum")
    assert ok, f"Falha confirmar_lote: {msg}"
    arquivos = bd.listar_arquivos_grupo(grupo_id)
    assert len(arquivos) == 3, f"Esperado 3 arquivos no grupo, {len(arquivos)}"
    # Com responsável -> aguardando autorização
    assert arquivos[0] is not None
    pedidos = bd.listar_pedidos(usuario="qacomum")
    grupo = next((p for p in pedidos if p[0] == grupo_id), None)
    assert grupo, "Grupo não listado"
    assert grupo[12] == "aguardando_autorizacao", f"Status esperado aguardando, {grupo[12]}"
    assert grupo[24] == 3, f"num_arquivos esperado 3, {grupo[24]}"
    print(f"  OK confirmar_lote criou 1 pedido #{grupo_id} com 3 arquivos")

    # Autoriza o grupo -> TODOS autorizados
    ok, _ = bd.autorizar_grupo(grupo_id, "resp_saude")
    assert ok, "Falha autorizar_grupo"
    statuses = {bd.obter_solicitacao(a[0])["status"] for a in bd.listar_arquivos_grupo(grupo_id)}
    assert statuses == {"autorizado"}, f"Status não uniforme após autorizar: {statuses}"
    print("  OK autorizar_grupo autorizou todos os arquivos")

    # Imprime o grupo -> desconta cota uma vez + apaga arquivos
    antes = bd.obter_consumo(sid, stid)
    ok, _ = bd.imprimir_grupo(grupo_id, "admin_impressao", ator="admin_impressao")
    assert ok, "Falha imprimir_grupo"
    depois = bd.obter_consumo(sid, stid)
    assert depois - antes == 9, f"Cota deveria +9 (3 pág x3 arquivos), +{depois - antes}"
    for a in bd.listar_arquivos_grupo(grupo_id):
        assert not os.path.exists(a[6]), f"Arquivo do grupo não apagado: {a[6]}"
    print(f"  OK imprimir_grupo descontou {depois - antes} pág e apagou arquivos")
    os.remove(tmp.name)


def main():
    print("INICIANDO TESTES — mod_solicita_impressao")
    # Banco temporário isolado (determinístico): evita acúmulo de estado do
    # banco persistente em execuções repetidas (teste deve ser idempotente).
    tmpdir = tempfile.mkdtemp(prefix="sol_imp_test_")
    bd.DB_PATH = os.path.join(tmpdir, "db_mod_solicita_impressao.db")
    import mod_intranet.repositorio as _repo
    _repo.MODULOS_BD["solicita_impressao"] = bd.DB_PATH  # conexão via caminho_db
    bd.PASTA_SOLICITACOES = os.path.join(tmpdir, "solicitacaoImpressao")
    bd.init_db()
    teste_contagem_e_formula()
    sid, stid = teste_cadastros_e_cotas()
    teste_fluxo(sid, stid)
    teste_excedente(sid, stid)
    teste_marca_dagua()
    teste_rascunho(sid, stid)
    teste_multiplos_arquivos(sid, stid)
    teste_impressoras_e_busca(sid, stid)
    teste_relatorio_impressao(sid, stid)
    teste_limite_pedidos_abertos(sid, stid)
    teste_fluxo_grupo(sid, stid)
    print("\nTODOS OS TESTES PASSARAM ✅")


if __name__ == "__main__":
    main()
