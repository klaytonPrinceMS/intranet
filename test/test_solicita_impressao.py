"""Teste do módulo Solicitação de Impressão (mod_solicita_impressao).

Valida: banco, contagem de páginas, fórmula, cotas, fluxo de solicitação,
autorização, impressão, recuo e marca d'água.

Execute: .venv/bin/python test/test_solicita_impressao.py
"""
import sys
import os
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mod_solicita_impressao import manipulador_bd as bd


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


def main():
    print("INICIANDO TESTES — mod_solicita_impressao")
    bd.init_db()
    teste_contagem_e_formula()
    sid, stid = teste_cadastros_e_cotas()
    teste_fluxo(sid, stid)
    teste_excedente(sid, stid)
    teste_marca_dagua()
    teste_rascunho(sid, stid)
    teste_multiplos_arquivos(sid, stid)
    print("\nTODOS OS TESTES PASSARAM ✅")


if __name__ == "__main__":
    main()
