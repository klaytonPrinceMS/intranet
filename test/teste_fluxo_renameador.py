"""Teste do fluxo do módulo Renomear Empenhos.

Valida: identificação dos campos (ficha/empenho/parcela/ano) via regex
configurável, montagem de nome (template configurável), renomeação do PDF,
auditoria dos arquivos (detectado -> renomeado), campos de busca editáveis e
template de nome padrão.

Execute: .venv/bin/python test/teste_fluxo_renameador.py
"""
import sys
import os
import shutil
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mod_renomear_empenho import manipulador_bd as bd

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC_PDF = os.path.join(RAIZ, "doc", "DOC_0201.pdf")

_bak = tempfile.mkdtemp(prefix="bkp_renom_")


def _redirecionar_para_temp():
    """Aponta o banco e a pasta monitorada do módulo para um ambiente temporário,
    preservando o ambiente de desenvolvimento."""
    bd.DB_EMPENHO_PATH = os.path.join(_bak, "db_mod_renomear_empenho.db")
    bd.PASTA_MONITORADA = os.path.join(_bak, "pasta_mon")
    bd._PASTA_MONITORADA_PADRAO = bd.PASTA_MONITORADA
    os.makedirs(bd.PASTA_MONITORADA, exist_ok=True)
    # isola a lista de pastas monitoradas (não depende de tb_config central)
    bd.pastas_monitoradas = lambda: [bd.PASTA_MONITORADA]
    return _bak


def test_extração_campos():
    print("\n=== Teste: identificação dos campos (ficha/empenho/parcela/ano) ===")
    assert os.path.exists(DOC_PDF), f"DOC_0201.pdf ausente: {DOC_PDF}"
    texto = bd.extrair_texto_pdf(DOC_PDF)
    assert texto.strip(), "Não conseguiu extrair texto do PDF"

    d = bd.extrair_dados_empenho(texto)
    print(f"  campos: {d}")
    assert d.get("empenho"), "empenho não identificado"
    assert d.get("ficha"), "ficha não identificada"
    assert d.get("ano") == "2026", f"ano esperado 2026, recebido {d.get('ano')}"
    # sem zeros à esquerda no valor numérico
    assert int(re_sub_nao_digitos(d.get("empenho"))) == 345, "empenho esperado 345"
    assert int(re_sub_nao_digitos(d.get("ficha"))) == 331, "ficha esperada 331"
    print("  OK campos identificados (empenho 345, ficha 331, ano 2026)")


def test_template_nome():
    print("\n=== Teste: template de nome configurável ===")
    d = {"empenho": "0000345", "ficha": "0000331", "ano": "2026"}
    # padrão do módulo: empenho como inteiro
    nome = bd.montar_nome_final(bd.NOME_FINAL_PADRAO, 7, d)
    print(f"  padrão -> {nome}")
    assert nome == "doc_0007_numEmpenho_345_p001.pdf", nome
    # template custom usando a string crua do cabeçalho
    custom = bd.montar_nome_final("DOC_{contador:04d}_{ficha}_{empenho_cru}_({parcela})_{ano}.pdf", 9, d)
    print(f"  custom -> {custom}")
    assert "0000331_0000345" in custom and "_2026.pdf" in custom, custom
    print("  OK template padrão + custom")


def test_fluxo_processamento():
    print("\n=== Teste: processamento e renomeação ===")
    # copia o DOC para a pasta monitorada temporária
    alvo = os.path.join(bd.PASTA_MONITORADA, "DOC_0201.pdf")
    shutil.copy(DOC_PDF, alvo)
    res = bd.processar_pdf("qamaster", alvo)
    print(f"  processar_pdf -> {res}")
    assert res.get("ok"), f"Falha no processamento: {res}"
    # o arquivo original foi renomeado
    novo = os.path.join(bd.PASTA_MONITORADA, res["nome"])
    assert os.path.exists(novo), f"Nome final não encontrado: {novo}"
    assert not os.path.exists(alvo), "Arquivo original ainda existe"
    print(f"  OK renomeado para {res['nome']} (empenho {res['numero']})")
    return res


def test_auditoria_arquivos():
    print("\n=== Teste: auditoria dos arquivos escaneados/renomeados ===")
    rows = bd.listar_arquivos_auditoria()
    assert rows, "Nenhum registro de auditoria"
    print(f"  registros: {len(rows)}")
    aid, nome_orig, nome_fin, num, parc, ficha, ano, status, *_ = rows[0]
    print(f"  [{status}] {nome_orig} -> {nome_fin} (empenho={num}, ficha={ficha}, ano={ano})")
    assert status == "renomeado", f"status esperado 'renomeado', recebido {status}"
    assert nome_orig == "DOC_0201.pdf"
    evs = bd.listar_eventos_arquivo(aid)
    tipos = {e[1] for e in evs}
    print(f"  eventos: {sorted(tipos)}")
    assert "renomeado" in tipos, "Evento 'renomeado' ausente"
    print("  OK trilha de auditoria registrada")


def test_campos_busca():
    print("\n=== Teste: campos de busca editáveis (regex) ===")
    before = {c[1] for c in bd.listar_campos_busca()}
    ok, msg = bd.salvar_campo_busca("empenho", "Empenho",
                                    r"EMPENHO\s*PARCELA[:\s]+(\d{1,10})")
    print(f"  salvar_campo_busca: {ok} {msg}")
    assert ok, msg
    after = {c[1] for c in bd.listar_campos_busca()}
    assert "empenho" in after
    # regex inválida deve ser rejeitada
    ok2, msg2 = bd.salvar_campo_busca("x", "X", r"([unclosed")
    print(f"  regex inválida: {ok2} {msg2}")
    assert not ok2, "Regex inválida deveria ser rejeitada"
    # restaura
    bd.restaurar_campos_busca_padrao()
    print("  OK campos de busca editáveis e validados")


def re_sub_nao_digitos(v):
    import re
    return re.sub(r"\D", "", v) if v else ""


def _pdf(x):
    return os.path.join(RAIZ, "doc", f"{x}.pdf")


def test_tipos_especiais():
    print("\n=== Teste: tipos especiais (EC/EE/EG) ===")
    # adequação aos 4 modelos: extração correta do nº do documento e do nome final
    casos = {
        "EC_24": ("EC", 24, "EC_0024.pdf"),
        "EE_9570": ("EE", 9570, "EE_9570.pdf"),
        "EG_89": ("EG", 89, "EG_0089.pdf"),
    }
    for nome_arquivo, (tipo, num, nome_final) in casos.items():
        path = _pdf(nome_arquivo)
        assert os.path.exists(path), f"fixture ausente: {path}"
        texto = bd.extrair_texto_pdf(path)
        t = bd.detectar_tipo_especial(texto)
        print(f"  {nome_arquivo}: tipo={t}")
        assert t == tipo, f"{nome_arquivo}: tipo esperado {tipo}, recebido {t}"
        de = bd.extrair_dados_tipo_especial(texto, t)
        print(f"    num={de.get('numero')} ano={de.get('ano')} -> {bd.montar_nome_tipo_especial(t, de.get('numero'))}")
        assert de.get("numero") == num, f"{nome_arquivo}: nº esperado {num}, recebido {de.get('numero')}"
        assert bd.montar_nome_tipo_especial(t, de.get("numero")) == nome_final
    print("  OK tipos EC/EE/EG reconhecidos corretamente")


def test_processamento_tipo_especial():
    print("\n=== Teste: processamento renomeia tipo especial ===")
    alvo = os.path.join(bd.PASTA_MONITORADA, "EC_24.pdf")
    shutil.copy(_pdf("EC_24"), alvo)
    res = bd.processar_pdf("qamaster", alvo)
    print(f"  processar_pdf EC_24 -> {res}")
    assert res.get("ok"), f"Falha EC_24: {res}"
    assert res.get("tipo") == "EC"
    novo = os.path.join(bd.PASTA_MONITORADA, res["nome"])
    assert os.path.exists(novo), f"Nome final EC não encontrado: {novo}"
    assert not os.path.exists(alvo), "EC_24 original deveria ter sido renomeado"
    assert res["nome"] == "EC_0024.pdf"
    # arquivo processado não deve ser reprocessado na fila
    assert bd.status_arquivo(novo) == "processado", "EC_0024.pdf deveria estar processado"
    pend = [p["nome"] for p in bd.listar_pendentes(recursivo=True)]
    assert "EC_0024.pdf" not in pend, "EC processado não pode aparecer como pendente"
    print("  OK tipo especial processado e marcado como processado")


def test_ja_processado_classificacao():
    print("\n=== Teste: classificação de já-processado ===")
    assert bd.arquivo_ja_processado("doc_0014_numEmpenho_345_p001.pdf") is True
    assert bd.arquivo_ja_processado("renomeador_empenhos.py") is False
    assert bd.arquivo_ja_processado("DOC_0201.pdf") is False
    # fonte EC_24 ainda é pendente (nome curto), não processado
    assert bd.arquivo_ja_processado("EC_24.pdf") is False
    # normalização de pastas local
    assert bd._normalizar_pasta("doc").endswith(os.path.join("", "doc"))
    print("  OK classificação + normalização de pastas")


def test_solicitacoes():
    print("\n=== Teste: fluxo de solicitações ===")
    # usa um arquivo já processado (o DOC do teste anterior) como alvo de cópia
    rows = bd.listar_empenhos(status="ativo", limite=1)
    assert rows, "Sem empenho base para solicitação"
    eid, _o, final, _num, _parc, _user, _dt, caminho = rows[0]
    assert caminho and os.path.exists(caminho)
    sid = bd.criar_solicitacao(caminho, final, "João Teste", "joao@teste.com", "cópia", lote_id="abc")
    print(f"  criada solicitação id={sid}")
    pend = bd.listar_solicitacoes_acao_pendente()
    assert any(s["id"] == sid for s in pend), "Solicitação não apareceu como pendente"
    # gerar zip
    ok, zip_path = bd.gerar_zip_solicitacoes([bd.obter_solicitacao(sid)])
    assert ok and os.path.exists(zip_path), f"ZIP falhou: {zip_path}"
    bd.marcar_solicitacoes_zip_gerado([sid], zip_path, "qamaster")
    assert bd.obter_solicitacao(sid)["status"] == "zip_gerado"
    bd.marcar_solicitacao_enviada(sid, "qamaster", "zip_manual")
    assert bd.obter_solicitacao(sid)["status"] == "enviado"
    # recusa
    sid2 = bd.criar_solicitacao(caminho, final, "Maria", "maria@teste.com")
    bd.marcar_solicitacao_recusada(sid2, "não autorizado", "qamaster")
    assert bd.obter_solicitacao(sid2)["status"] == "recusado"
    print("  OK fluxo de solicitações (criar→zip→enviar→recusar)")


def test_navegacao_pendas():
    print("\n=== Teste: navegação (só PDF, pendente/processado, proteção) ===")
    # cria um pendente numa subpasta para validar lista recursiva e navegação
    sub = os.path.join(bd.PASTA_MONITORADA, "subdir")
    os.makedirs(sub, exist_ok=True)
    shutil.copy(_pdf("EG_89"), os.path.join(sub, "EG_89.pdf"))
    nav = bd.listar_navegacao(bd.PASTA_MONITORADA)
    pdfs = {d["nome"]: d["status"] for d in nav["pdfs"]}
    print(f"  pdfs na raiz: {pdfs}")
    # nenhum .py aparece na navegação
    assert all(n.lower().endswith(".pdf") for n in pdfs), "Navegação deve conter só PDFs"
    # os arquivos processados estão marcados como processado
    assert "doc_0001_numEmpenho_345_p001.pdf" in pdfs
    assert pdfs["doc_0001_numEmpenho_345_p001.pdf"] == "processado"
    # dirs contém a subpasta
    assert any(d["nome"] == "subdir" for d in nav["dirs"])
    # proteção de raiz: navegar fora cai dentro
    out = bd.listar_navegacao("/etc")
    assert out["atual"].startswith(bd.PASTA_MONITORADA), f"Proteção de raiz falhou: {out['atual']}"
    # o EG_89 (pendente) aparece na lista recursiva; o EC_0024 processado não
    pend_nao_rec = [p["nome"] for p in bd.listar_pendentes(recursivo=False)]
    pend_rec = [p["nome"] for p in bd.listar_pendentes(recursivo=True)]
    print(f"  pendentes raiz: {pend_nao_rec}")
    print(f"  pendentes recursivo: {pend_rec}")
    assert "EG_89.pdf" in pend_rec, "EG_89 pendente deveria aparecer recursivo"
    assert "subdir/EG_89.pdf" not in pend_nao_rec, "recursivo=False não deve entrar em subpasta"
    assert "EC_0024.pdf" not in pend_rec, "EC processado não pode ser pendente"
    print("  OK navegação e classificação")


def main():
    print("INICIANDO TESTES — mod_renomear_empenho (fluxo)")
    _redirecionar_para_temp()
    bd.init_db_empenho()
    test_extração_campos()
    test_template_nome()
    test_fluxo_processamento()
    test_auditoria_arquivos()
    test_campos_busca()
    test_tipos_especiais()
    test_processamento_tipo_especial()
    test_ja_processado_classificacao()
    test_solicitacoes()
    test_navegacao_pendas()
    print("\nTODOS OS TESTES PASSARAM ✅")
    # limpeza
    shutil.rmtree(_bak, ignore_errors=True)


if __name__ == "__main__":
    main()
