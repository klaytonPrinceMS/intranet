"""Testes da fábrica de documentos fictícios (faker + pytest).

Validam: determinismo por semente, cobertura dos campos monitorados
(extração via regex do módulo) e processamento ponta a ponta de um PDF
gerado (novo padrão `doc_0001_345_001.pdf`).
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from assets.test import fabrica_documentos as fab
from mod_renomear_empenho import bd_manipulador as bd


class TestFabricaDeterministica:
    def test_mesma_semente_mesmos_dados(self):
        a = fab.gerar_dados_empenho(semente=42, secretaria="saude")
        b = fab.gerar_dados_empenho(semente=42, secretaria="saude")
        assert a == b

    def test_sementes_diferentes_divergem(self):
        a = fab.gerar_dados_empenho(semente=1, secretaria="saude")
        b = fab.gerar_dados_empenho(semente=2, secretaria="saude")
        assert a["empenho"] != b["empenho"] or a["ficha"] != b["ficha"]

    def test_tipos_especiais_geram(self):
        for tipo in ("EC", "EE", "EG", "AE"):
            d = fab.gerar_dados_empenho(semente=7, secretaria="obras", tipo=tipo)
            texto = fab.texto_empenho(d)
            assert bd.detectar_tipo_especial(texto) == tipo, tipo


class TestFabricaCoberturaCampos:
    def test_identificacao_recuperada(self):
        d = fab.gerar_dados_empenho(semente=11, secretaria="financas", tipo="DOC")
        extraidos = bd.extrair_dados_empenho(fab.texto_empenho(d))
        assert int(re.sub(r"\D", "", extraidos["empenho"])) == int(d["empenho"])
        assert int(re.sub(r"\D", "", extraidos["ficha"])) == int(d["ficha"])
        assert str(extraidos["parcela"]).strip() == str(int(d["parcela"]))
        assert extraidos["ano"] == d["ano"]

    def test_estrutura_orcamentaria_presente(self):
        d = fab.gerar_dados_empenho(semente=12, secretaria="educacao", tipo="DOC")
        texto = fab.texto_empenho(d)
        for chave in ("orgao", "unidade", "funcao", "programa",
                      "elemento_despesa", "fonte_recurso", "dotacao"):
            rotulo, padrao = bd.CAMPOS_BUSCA_PADRAO[chave]
            assert re.search(padrao, texto, re.IGNORECASE), chave

    def test_favorecido_financeiro_bancario_presente(self):
        d = fab.gerar_dados_empenho(semente=13, secretaria="social", tipo="DOC")
        texto = fab.texto_empenho(d)
        for chave in ("favorecido_nome", "favorecido_cpf", "favorecido_cidade",
                      "valor_bruto", "valor_liquido", "especificacao",
                      "banco", "agencia", "conta", "pix",
                      "autorizador_nome", "data_emissao", "decreto",
                      "processo", "modalidade", "exercicio"):
            rotulo, padrao = bd.CAMPOS_BUSCA_PADRAO[chave]
            assert re.search(padrao, texto, re.IGNORECASE), chave


class TestFabricaNomesImpressora:
    def test_nomes_sao_pendentes(self):
        import random
        rnd = random.Random(5)
        nomes = {fab.nome_impressora(random.Random(s)) for s in range(30)}
        assert len(nomes) >= 4
        for nome in nomes:
            assert nome.lower().endswith(".pdf")
            assert bd.arquivo_ja_processado(nome) is False, nome

    def test_lote_principal_todos_pendentes(self, tmp_path):
        criados = fab.criar_lote_principal(str(tmp_path), quantidade=8)
        assert len(criados) == 8
        tipos = {d["tipo"] for _, d in criados}
        assert "DOC" in tipos
        for caminho, dados in criados:
            assert os.path.exists(caminho)
            assert bd.extrair_texto_pdf(caminho).strip()
            assert bd.detectar_tipo_especial(
                bd.extrair_texto_pdf(caminho)) == (
                dados["tipo"] if dados["tipo"] != "DOC" else None)


class TestFabricaPontaAPonta:
    def test_pdf_processa_no_padrao_novo(self, tmp_path, monkeypatch):
        destino = tmp_path / "empenhos"
        destino.mkdir()
        caminho = str(destino / "DOC_9001.pdf")
        fab.criar_pdf_empenho(
            caminho, fab.gerar_dados_empenho(semente=99, secretaria="saude"))
        assert bd.extrair_texto_pdf(caminho).strip()

        banco_tmp = str(tmp_path / "db_mod_renomear_empenho.db")
        monkeypatch.setattr(bd, "DB_EMPENHO_PATH", banco_tmp)
        import mod_intranet.repositorio as _repo
        monkeypatch.setitem(_repo.MODULOS_BD, "empenhos", banco_tmp)
        monkeypatch.setattr(bd, "PASTA_MONITORADA", str(destino))
        monkeypatch.setattr(bd, "_PASTA_MONITORADA_PADRAO", str(destino))
        monkeypatch.setattr(bd, "pastas_monitoradas", lambda: [str(destino)])
        bd.init_db_empenho()

        res = bd.processar_pdf("qa_fabrica", caminho)
        assert res.get("ok"), res
        assert re.match(r"^doc_\d+_\d+_\d+\.pdf$", res["nome"]), res["nome"]
        assert bd.arquivo_ja_processado(res["nome"]) is True
