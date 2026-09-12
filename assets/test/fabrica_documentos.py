"""Fábrica de documentos fictícios do módulo Renomear Empenhos.

Factory of fictitious Empenho PDFs covering every monitored field
(CAMPOS_BUSCA_PADRAO / FTS_COLS): identification, budget structure,
payee, financial, banking, authorizers and dates — for DOC/EC/EE/EG/AE.

Fábrica determinística (por semente) de PDFs fictícios cobrindo TODOS os
campos que o módulo monitora e armazena. Uso:
  - gerar massa demo em `mod_renomear_empenho/doc/<secretaria>/` via
    `criar_lote_demo()` (NOME_FINAL_PADRAO novo: `doc_0001_345_001.pdf`
    após processar; tipos especiais `EC_0001.pdf` etc.);
  - gerar massa de teste no pytest (ver `test_fabrica_documentos.py`).

Cada linha do texto segue o fraseado das regex de `tb_campos_busca`
(CAMPOS_BUSCA_PADRAO), então `extrair_dados_empenho()` recupera os campos.
"""

import os
import random
import re

from faker import Faker

TIPOS_DOC = ("DOC", "EC", "EE", "EG", "AE")

PASTAS_DEMO = ["saude", "educacao", "financas", "social", "obras"]

# Famílias de nomes cuspidos por scanner/impressora (padrão de entrada:
# tudo que NÃO é nome renomeado é pendente para o monitor da raiz).
FAMILIAS_IMPRESSORA = ("doc_simples", "doc_lote_data", "scan", "data_hora")


def nome_impressora(rnd, seq=0):
    """Generates a random printer/scanner-style file name (pending pattern).

    Gera nome aleatório padrão de impressora/scanner (sempre pendente,
    nunca casa com `arquivo_ja_processado`).
    """
    familia = rnd.choice(FAMILIAS_IMPRESSORA)
    if familia == "doc_simples":
        return f"DOC_{rnd.randint(1, 9999):04d}.pdf"
    if familia == "doc_lote_data":
        return (f"DOC_{rnd.randint(1, 9999):04d}_"
                f"{rnd.randint(1, 28):02d}-{rnd.randint(1, 12):02d}-"
                f"{rnd.randint(2024, 2026)}{rnd.randint(100000000, 999999999)}.pdf")
    if familia == "scan":
        return f"SCAN_{rnd.randint(1, 999):03d}.pdf"
    return (f"{rnd.randint(2024, 2026)}{rnd.randint(1, 12):02d}"
            f"{rnd.randint(1, 28):02d}_{rnd.randint(0, 23):02d}"
            f"{rnd.randint(0, 59):02d}{rnd.randint(0, 59):02d}.pdf")


def criar_lote_principal(pasta_doc, quantidade=12, semente_base=9000,
                         tipos=("DOC", "EC", "EE", "EG", "AE")):
    """Creates printer-named PDFs with ALL fields in the MAIN monitored folder.

    Cria na pasta principal monitorada (raiz, onde o `rodar_monitor` varre)
    PDFs com nomes aleatórios padrão de impressora e todos os campos.
    Retorna a lista de (caminho, dados).
    """
    os.makedirs(pasta_doc, exist_ok=True)
    criados = []
    usados = set()
    for j in range(quantidade):
        semente = semente_base + j
        rnd = random.Random(semente + 999)
        nome = nome_impressora(rnd, j)
        while nome in usados or os.path.exists(os.path.join(pasta_doc, nome)):
            nome = nome_impressora(random.Random(semente + len(usados) + 1), j)
            usados.add(nome)
        usados.add(nome)
        tipo = "DOC" if j % 4 else tipos[(j // 4 + 1) % len(tipos)]
        dados = gerar_dados_empenho(semente=semente, secretaria="GERAL", tipo=tipo)
        caminho = os.path.join(pasta_doc, nome)
        criar_pdf_empenho(caminho, dados)
        criados.append((caminho, dados))
    return criados


def _so_letras_maiusculas(texto):
    """Uppercase letters/spaces only (safe for Favorecido/Recebedor regex)."""
    limpo = re.sub(r"[^A-Za-zÁÂÃÉÊÍÓÔÕÚÇáâãéêíóôõúç ]", " ", texto or "")
    limpo = re.sub(r"\s+", " ", limpo).strip().upper()
    return limpo


def _nome_empresa(rnd, fake):
    for _ in range(20):
        nome = _so_letras_maiusculas(fake.company())
        if len(nome) >= 6:
            return nome[:60]
    return "EMPRESA EXEMPLO LTDA"


def _nome_pessoa(rnd, fake):
    for _ in range(20):
        nome = _so_letras_maiusculas(fake.name())
        if len(nome) >= 8 and " " in nome:
            return nome[:60]
    return "JOAO DA SILVA PEREIRA"


def _valor_br(valor):
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def gerar_dados_empenho(semente=0, secretaria="SAUDE", tipo="DOC"):
    """Generates one deterministic fictitious record with ALL monitored fields.

    Gera um registro fictício determinístico com todos os campos.
    """
    rnd = random.Random(semente)
    fake = Faker("pt_BR")
    Faker.seed(semente)

    ano = 2026
    empenho = rnd.randint(1, 5999)
    parcela = rnd.randint(1, 12)
    ficha = f"{rnd.randint(1, 9999999):07d}"
    numero_esp = rnd.randint(1, 9999)

    favorecido = _nome_empresa(rnd, fake)
    recebedor = _nome_pessoa(rnd, fake)
    autorizador = _nome_pessoa(rnd, fake)
    tipo_emp = rnd.choice(["Ordinario", "Estimativo", "Global"])
    modalidade = rnd.choice(["PREGAO ELETRONICO", "DISPENSA DE LICITACAO",
                             "INEXIGIBILIDADE", "CONCORRENCIA PUBLICA"])
    orgao = f"{rnd.randint(1, 9):02d} - PREFEITURA MUNICIPAL"
    unidade = f"02{rnd.randint(0, 9):02d} - {secretaria.upper()}"
    banco = rnd.choice(["001", "104", "341", "033"])
    valor_bruto = round(rnd.uniform(500, 250000), 2)
    valor_liquido = round(valor_bruto * rnd.uniform(0.85, 0.99), 2)

    return {
        "tipo": tipo if tipo in TIPOS_DOC else "DOC",
        "secretaria": secretaria.upper(),
        "ficha": ficha,
        "empenho": str(empenho),
        "empenho_formatado": f"{empenho:07d}",
        "parcela": str(parcela),
        "ano": str(ano),
        "exercicio": str(ano),
        "numero_especial": numero_esp,
        "processo": f"{rnd.randint(1, 999)}/{ano}",
        "tipo_empenho": tipo_emp,
        "modalidade": modalidade,
        "contrato_numero": f"{rnd.randint(1, 200)}/{ano}",
        "orgao": orgao,
        "unidade": unidade,
        "sub_unidade": f"001 - {secretaria.upper()} EXECUTIVO",
        "funcao": f"{rnd.randint(1, 28):02d} - ADMINISTRACAO",
        "subfuncao": f"{rnd.randint(100, 999)} - ADMINISTRACAO GERAL",
        "programa": "GESTAO ADMINISTRATIVA EFICIENTE",
        "projeto_atividade": f"MANUTENCAO DAS ATIVIDADES DA {secretaria.upper()}",
        "elemento_despesa": f"{rnd.choice(['3390', '4490', '3190'])} - MATERIAL DE CONSUMO",
        "subelemento": f"{rnd.randint(10, 99)} - MATERIAL DE EXPEDIENTE",
        "fonte_recurso": f"{rnd.choice(['1500', '1501', '1576'])} - RECURSOS PROPRIOS",
        "subfonte": f"{rnd.choice(['1500', '1501'])}000000 - TESOURO MUNICIPAL",
        "dotacao": (f"02.{rnd.randint(100, 999):03d}."
                    f"{rnd.randint(10, 99):02d}."
                    f"{rnd.randint(100, 999)}.{rnd.randint(1000, 9999)}"),
        "favorecido_codigo": str(rnd.randint(100, 9999)),
        "favorecido_nome": favorecido,
        "favorecido_cpf": fake.cnpj(),
        "favorecido_endereco": _so_letras_maiusculas(fake.street_address())[:60] or "RUA CENTRAL",
        "favorecido_bairro": _so_letras_maiusculas(fake.neighborhood())[:30] or "CENTRO",
        "favorecido_cidade": _so_letras_maiusculas(fake.city())[:40] or "MONTE SANTO DE MINAS",
        "favorecido_uf": "MG",
        "recebedor_nome": recebedor,
        "valor_bruto": _valor_br(valor_bruto),
        "valor_liquido": _valor_br(valor_liquido),
        "especificacao": (f"AQUISICAO DE MATERIAL E SERVICOS PARA ATENDIMENTO DAS "
                          f"ATIVIDADES DA {secretaria.upper()} CONFORME PROCESSO"),
        "saldo_anterior": _valor_br(round(valor_bruto * 2, 2)),
        "saldo_disponivel": _valor_br(round(valor_bruto * 0.5, 2)),
        "diarias_numero": str(rnd.randint(1, 30)),
        "banco": banco,
        "agencia": f"{rnd.randint(1000, 9999)}-{rnd.randint(0, 9)}",
        "conta": f"{rnd.randint(10000, 99999)}-{rnd.randint(0, 9)}",
        "pix": fake.email(),
        "conta_pagamento": f"{rnd.randint(10000, 99999)}-{rnd.randint(0, 9)}",
        "autorizador_nome": autorizador,
        "autorizador_cargo": f"Secretaria de {secretaria.capitalize()}",
        "contador_cpf": fake.cpf(),
        "data_emissao": fake.date_between(start_date="-60d", end_date="today").strftime("%d/%m/%Y"),
        "data_vencimento": fake.date_between(start_date="today", end_date="+60d").strftime("%d/%m/%Y"),
        "data_quitacao": "",
        "decreto": f"{rnd.randint(1, 5000)}/{ano}",
    }


def texto_empenho(dados):
    """Renders the PDF text lines matching every tb_campos_busca regex."""
    d = dados
    linhas = [
        "PREFEITURA MUNICIPAL DE MONTE SANTO DE MINAS",
        f"Secretaria: {d['secretaria']}",
        f"Exercicio: {d['ano']}",
        f"Processo n° {d['processo']}",
        f"Tipo de Empenho: {d['tipo_empenho']}",
        f"Modalidade: {d['modalidade']}",
        f"Contrato N° {d['contrato_numero']}",
    ]
    if d["tipo"] == "DOC":
        linhas += [
            f"DOCUMENTO DE ORDEM DE CREDITO - DOC_{d['empenho']}",
            f"EMPENHO PARCELA: {d['empenho']}-{d['parcela']}",
            f"N° da Ficha: {d['ficha']}/{d['ano']}",
            f"N° do Empenho: {d['empenho_formatado']}/{d['ano']}",
        ]
    elif d["tipo"] == "EC":
        linhas += [
            f"COMPLEMENTACAO DE EMPENHO N° {d['numero_especial']}/{d['ano']}",
            f"Tipo: {d['tipo_empenho']}",
            f"Ficha: {d['ficha']}",
            f"Empenho: {d['empenho_formatado']}",
        ]
    elif d["tipo"] == "EE":
        linhas += [
            f"NOTA DE EMPENHO N° {d['numero_especial']}/{d['ano']}",
            "Tipo: Estimativo",
            f"Ficha: {d['ficha']}",
        ]
    elif d["tipo"] == "EG":
        linhas += [
            f"NOTA DE EMPENHO N° {d['numero_especial']}/{d['ano']}",
            "Tipo: Global",
            f"Ficha: {d['ficha']}",
        ]
    else:  # AE
        linhas += [
            f"ANULACAO DE EMPENHO N° {d['numero_especial']}/{d['ano']}",
            f"Tipo: {d['tipo_empenho']}",
            f"Ficha: {d['ficha']}",
            f"Empenho: {d['empenho_formatado']}",
        ]
    linhas += [
        f"Orgao: {d['orgao']}",
        f"Unidade: {d['unidade']}",
        f"Sub Unidade: {d['sub_unidade']}",
        f"Funcao: {d['funcao']}",
        f"SubFuncao: {d['subfuncao']}",
        f"Programa: {d['programa']}",
        f"Projeto/Atividade: {d['projeto_atividade']}",
        f"Elemento de Despesa: {d['elemento_despesa']}",
        f"SubElemento: {d['subelemento']}",
        f"Fonte de Recurso: {d['fonte_recurso']}",
        f"SubFonte: {d['subfonte']}",
        f"Dotacao: {d['dotacao']}",
        f"Favorecido: {d['favorecido_codigo']} - {d['favorecido_nome']}",
        f"CNPJ/CPF: {d['favorecido_cpf']}",
        f"Endereco: {d['favorecido_endereco']}",
        f"Bairro: {d['favorecido_bairro']}",
        f"Cidade: {d['favorecido_cidade']}",
        "UF: MG",
        f"Recebedor: {d['recebedor_nome']}",
        f"Valor Bruto: {d['valor_bruto']}",
        f"VALOR LIQUIDO: {d['valor_liquido']}",
        f"Especificacao: {d['especificacao']}",
        f"Saldo Anterior: {d['saldo_anterior']}",
        f"Saldo Disponivel: {d['saldo_disponivel']}",
        f"Diaria N° {d['diarias_numero']}",
        f"Banco: {d['banco']}",
        f"Agencia: {d['agencia']}",
        f"Conta: {d['conta']}",
        f"PIX: {d['pix']}",
        f"CONTA: {d['conta_pagamento']}",
        f"Ordenador da Despesa: {d['autorizador_nome']}",
        f"Secretaria de {d['secretaria'].capitalize()}",
        f"CPF: {d['contador_cpf']}",
        f"Data do Empenho: {d['data_emissao']}",
        f"Data Vencimento: {d['data_vencimento']}",
        f"Decreto N° {d['decreto']}",
    ]
    return "\n".join(linhas) + "\n"


def criar_pdf_empenho(caminho, dados):
    """Writes the fictitious record as a real PDF file."""
    import pymupdf
    os.makedirs(os.path.dirname(os.path.abspath(caminho)), exist_ok=True)
    doc = pymupdf.open()
    pagina = doc.new_page()
    retangulo = pymupdf.Rect(56, 56, 539, 786)
    pagina.insert_textbox(retangulo, texto_empenho(dados), fontsize=10)
    doc.save(caminho)
    doc.close()
    return caminho


def criar_lote_demo(pasta_doc, pastas=None, por_pasta=5, semente_base=7000,
                    tipos=("DOC", "EC", "EE", "EG", "AE")):
    """Recreates the demo mass: <pasta>/<DOC_*.pdf> with ALL fields.

    Recria a massa demo nas subpastas (remove os PDFs anteriores e gera
    novos com todos os campos). Nomes pendentes `DOC_<n>.pdf`; o 5º de
    cada pasta varia o tipo especial para exercitar EC/EE/EG/AE.
    Retorna a lista de (caminho, dados).
    """
    pastas = pastas or PASTAS_DEMO
    criados = []
    for i, pasta in enumerate(pastas):
        destino = os.path.join(pasta_doc, pasta)
        os.makedirs(destino, exist_ok=True)
        for antigo in [a for a in os.listdir(destino) if a.lower().endswith(".pdf")]:
            os.remove(os.path.join(destino, antigo))
        for j in range(por_pasta):
            semente = semente_base + i * 100 + j
            tipo = "DOC" if j < por_pasta - 1 else tipos[(i + 1) % len(tipos)]
            dados = gerar_dados_empenho(semente=semente, secretaria=pasta, tipo=tipo)
            caminho = os.path.join(destino, f"DOC_{3001 + i * 10 + j}.pdf")
            criar_pdf_empenho(caminho, dados)
            criados.append((caminho, dados))
    return criados
