"""Empenho renaming module — folder monitor, dynamic regex, quarantine,
sequential renaming and physical organizer (~200 pages/folder, 4 folders/box).

Módulo Renomear Empenhos — monitor de pasta, regex dinâmicas, quarentena,
renomeação sequencial e organizador físico (~200 págs/pasta, 4 pastas/caixa)."""
import sys, os, re, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

import sqlite3
import shutil
import io
from datetime import datetime
from functools import lru_cache

from mod_intranet.bd_conexao import get_connection, get_config
from mod_intranet.bd_manipulador import audit_log, hash_arquivo
from mod_intranet.decoradores import valida_regex

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD_DIR = os.path.join(BASE_DIR, "mod_renomear_empenho")


def _log():
    """Logger do módulo (loguru) — arquivo dedicado logs/renomear_empenho_<data>.log."""
    from mod_intranet import observabilidade
    return observabilidade.get_logger("renomear_empenho")
DB_EMPENHO_PATH = os.path.join(BASE_DIR, "db_mod_renomear_empenho.db")
PASTA_ORGANIZADOR = os.path.join(MOD_DIR, "organizadorPasta")
PASTA_QUARENTENA = os.path.join(MOD_DIR, "quarentena")
_PASTA_MONITORADA_PADRAO = os.path.join(MOD_DIR, "doc")
PASTA_MONITORADA = _PASTA_MONITORADA_PADRAO


def pastas_monitoradas():
    """Lista de pastas monitoradas pelo módulo (rede/UNC ou local), editável em
    tb_config na chave 'empenhos_pastas_monitoradas' sem reiniciar.

    O valor é uma lista com UMA PASTA POR LINHA. Cada pasta pode ser:
      - local absoluta (C:\\empenhos, /dados/empenhos);
      - local relativa ao módulo (ex.: doc — dentro de mod_renomear_empenho/);
      - rede/UNC (\\\\servidor\\compartilhamento\\empenhos) ou drive mapeado
        (E:\\scan), permitindo monitorar vários computadores que escaneiam.

    Pastas inacessíveis (ex.: host de rede fora do ar) são retornadas na lista —
    quem varre (rodar_monitor/navegação) trata via `pasta_acessivel`. Retorna
    sempre >= 1 pasta (fallback para doc/).
    """
    try:
        raw = (get_config("empenhos_pastas_monitoradas", "") or "").strip()
        itens = [l.strip() for l in re.split(r"[\r\n|]+", raw) if l.strip()]
    except Exception as e:
        _log().warning(f"falha ao ler pastas monitoradas de tb_config: {e}")
        itens = []
    if not itens:
        # retrocompatibilidade: chave antiga com uma única pasta
        try:
            v = (get_config("empenhos_pastas_monitoradas", "") or "").strip()
            if v:
                itens = [v]
        except Exception:
            pass
    if not itens:
        return [PASTA_MONITORADA]

    saida = []
    for v in itens:
        saida.append(_normalizar_pasta(v))
    # garante fallback se todas as pastas configuradas forem inválidas/vazias
    return saida or [PASTA_MONITORADA]


def _normalizar_pasta(v):
    """Normaliza um caminho de pasta (local ou UNC/rede) para uso com os.path."""
    v = (v or "").strip()
    if not v:
        return PASTA_MONITORADA
    # caminho UNC (\\host\share ou //host/share): preservar separadores
    if v.startswith("\\\\") or v.startswith("//"):
        return os.path.normpath(v.replace("/", "\\"))
    if os.path.isabs(v):
        return os.path.normpath(v)
    return os.path.normpath(os.path.join(MOD_DIR, v))


def pasta_monitorada():
    """Pasta monitorada principal do módulo (primeira da lista). Legado: usado
    pela tela como raiz padrão. A lista completa fica em `pastas_monitoradas()`."""
    try:
        return pastas_monitoradas()[0]
    except Exception:
        return PASTA_MONITORADA


def pasta_acessivel(pasta):
    """True se a pasta existe e é lida/escrita (tolerante a rede fora do ar)."""
    try:
        return os.path.isdir(pasta)
    except Exception:
        return False


def salvar_pastas_monitoradas(lista):
    """Grava a lista de pastas monitoradas (uma por linha) em tb_config."""
    from mod_intranet.bd_conexao import set_config
    limpos = []
    for v in (lista or []):
        v = _normalizar_pasta(v)
        if v not in limpos:
            limpos.append(v)
    set_config("empenhos_pastas_monitoradas", "\n".join(limpos))
    return limpos

REGEX_PADRAO = r"(?:empenho|emp|ne)[\s\.: nº]*(\d{4,10})(?:[-/](\d{1,3}))?"
NOME_FINAL_PADRAO = "doc_{contador:04d}_{empenho}_{parcela:03d}.pdf"
PAGINAS_EXTRACAO = 3

# ================= TIPOS ESPECIAIS (EC/EE/EG/AE) =================
# Documentos diferentes do "empenho de parcela" DOC, reconhecidos pelo conteúdo.
# Adequados aos modelos de documento: DOC_0201 (parcela), EC_24 (complementação),
# EE_9570 (nota de empenho estimativo) e EG_89 (nota de empenho global).
TIPO_EC = "EC"   # Nota de Complementação de Empenho
TIPO_EE = "EE"   # Nota de Empenho (Estimativo)
TIPO_EG = "EG"   # Nota de Empenho (Global)
TIPO_AE = "AE"   # Anulação de Empenho
PREFIXOS_ESPECIAIS = (TIPO_EC, TIPO_EE, TIPO_EG, TIPO_AE)

# Regex de detecção do tipo pelo conteúdo do texto (ordem: mais específico primeiro)
_PADRAO_TIPO_A = r"ANULA[ÇC][ÃA]O\s*DE\s*EMPENHO"
_PADRAO_TIPO_C = r"(?:NOTA\s*DE\s*)?COMPLEMENTA[ÇC][ÃA]O\s*DE\s*EMPENHO"
_PADRAO_TIPO_T = r"(?:N['°o]?\s*)?(?:TIPO|Tipo)\s*[:]?\s*(Estimativo|Global)"
_PADRAO_NOTA_EMP = r"NOTA\s*DE\s*EMPENHO"

# Extração do número/ano/pela pelos padrões de cada tipo especial (o 1º grupo
# capturado é o número do documento; quando houver, o ano vem do grupo do ano).
_PADRAO_NUM_EC = r"COMPLEMENTA[ÇC][ÃA]O\s*DE\s*EMPENHO\s*N['°o]?\s*(\d+)\s*/\s*(\d{4})"
_PADRAO_NUM_NOTAS = r"NOTA\s*DE\s*EMPENHO\s*N['°o]?\s*(\d+)\s*/\s*(\d{4})"
_PADRAO_NUM_AE = r"ANULA[ÇC][ÃA]O\s*DE\s*EMPENHO\s*N['°o]?\s*(\d+)\s*/\s*(\d{4})"

# Nome final para tipos especiais: <PREFIXO>_<numero_com_4dig>.pdf (ex.: EC_0024.pdf)
def montar_nome_tipo_especial(tipo, numero, ano=""):
    """Builds the special-type file name: <TIPO>_<numero 4 dígitos>.pdf.

    Ex.: EC_0024.pdf, EE_9570.pdf. Número inválido/ausente gera
    `<TIPO>_indefinido.pdf` (o `ano` não entra no nome)."""
    try:
        num = int(re.sub(r"\D", "", str(numero or "0")))
    except ValueError:
        num = 0
    if not num:
        return f"{tipo}_indefinido.pdf"
    return f"{tipo.upper()}_{num:04d}.pdf"


def arquivo_ja_processado(nome_arquivo):
    """True se o nome segue o padrão DOC renomeado (sequencial).

    NOTA: tipos especiais (EC/EE/EG/AE) NÃO são classificados aqui por nome,
    pois o nome de entrada (ex.: EE_9570.pdf) pode ter o mesmo nº de dígitos do
    processado (EE_9570.pdf) e zero-à-esquerda não discrimina de forma confiável.
    Para eles, use `_arquivo_registrado_no_bd` (autoritativo via tb_empenhos).
    """
    nome = (nome_arquivo or "").strip().lower()
    if not nome:
        return False
    # padrão DOC vigente: doc_0001_345_001.pdf (contador, empenho, parcela)
    if re.match(r"^doc_\d+_\d+_\d+\.pdf$", nome):
        return True
    # padrão DOC legado: doc_0001_numEmpenho_345_p001.pdf (mantido p/ retrocompatibilidade)
    if re.match(r"^doc_\d+_numempenho_\d+_p\d+\.pdf$", nome):
        return True
    # padrão DOC com ano: doc_0001_0000331_0000345_(1)_2026.pdf (projeto de origem)
    if re.match(r"^doc_\d+_\d+_\d+_(\(\d+\))?_?\d{4}\.pdf$", nome):
        return True
    return False


def arquivo_pendente(nome_arquivo, padroes=()):
    """True se o arquivo ainda aguarda processamento (bate algum padrão pendente
    e ainda não foi renomeado). `padroes` é uma lista de regex de pendência."""
    nome = (nome_arquivo or "").strip()
    if not nome:
        return False
    if arquivo_ja_processado(nome):
        return False
    for p in (padroes or ()):
        try:
            if re.search(p, nome, re.IGNORECASE):
                return True
        except re.error:
            continue
    return False


def detectar_tipo_especial(texto):
    """Identifica se o documento é um tipo especial (EC/EE/EG/AE) pelo conteúdo.

    Ordem de checagem (mais específico primeiro):
      1. Anulação de Empenho   -> AE
      2. Complementação        -> EC
      3. 'EMPENHO PARCELA'     -> None (é o DOC clássico)
      4. 'Tipo: Estimativo'    -> EE ; 'Tipo: Global' -> EG
      5. 'NOTA DE EMPENHO'     -> EE/EG conforme o campo Tipo
    Retorna a chave (EC/EE/EG/AE) ou None.
    """
    t = texto or ""
    if re.search(_PADRAO_TIPO_A, t, re.IGNORECASE | re.UNICODE):
        return TIPO_AE
    if re.search(_PADRAO_TIPO_C, t, re.IGNORECASE | re.UNICODE):
        return TIPO_EC
    if re.search(r"EMPENHO\s*PARCELA", t, re.IGNORECASE | re.UNICODE):
        return None
    m_tipo = re.search(_PADRAO_TIPO_T, t, re.IGNORECASE | re.UNICODE)
    if m_tipo:
        return TIPO_EG if m_tipo.group(1).lower() == "global" else TIPO_EE
    if re.search(_PADRAO_NOTA_EMP, t, re.IGNORECASE | re.UNICODE):
        # nota de empenho sem 'Tipo' explícito: assume Estimativo
        return TIPO_EE
    return None


def extrair_dados_tipo_especial(texto, tipo):
    """Extrai os campos relevantes de um tipo especial (EC/EE/EG/AE).

    Retorna dict com chaves: tipo, numero, ano, ficha (quando presente),
    empenho_original (a que o documento se refere), rotulos.
    """
    t = texto or ""
    dados = {"tipo": tipo}
    padrao = None
    if tipo == TIPO_EC:
        padrao = _PADRAO_NUM_EC
    elif tipo == TIPO_AE:
        padrao = _PADRAO_NUM_AE
    else:  # EE ou EG
        padrao = _PADRAO_NUM_NOTAS
    m = re.search(padrao, t, re.IGNORECASE | re.UNICODE)
    dados["numero"] = int(m.group(1)) if m and m.group(1) else None
    dados["ano"] = m.group(2) if m and m.lastindex and m.lastindex >= 2 and m.group(2) else None
    # ficha / empenho original (referenciados pelo documento)
    mf = re.search(r"Ficha\s*[:]?\s*(\d+)", t, re.IGNORECASE | re.UNICODE)
    dados["ficha"] = mf.group(1) if mf else None
    me = re.search(r"[Ee]mpenho\s*[:]?\s*(\d{4,})", t, re.IGNORECASE | re.UNICODE)
    dados["empenho_original"] = me.group(1) if me else None
    if dados.get("numero") is None:
        # fallback: qualquer número longo no texto
        mn = re.search(r"(\d{4,10})", t)
        dados["numero"] = int(mn.group(1)) if mn else None
    dados["rotulos"] = {"numero": "Nº do documento", "ano": "Exercício",
                        "ficha": "Ficha", "empenho_original": "Empenho original"}
    return dados

# Padrões padrão de extração dos campos do cabeçalho do empenho (editáveis
# via tb_campos_busca, sem tocar no código). Cada entrada: campo -> (rótulo, regex).
# Expandido para >=40 campos — cada campo pode ser adicionado/editado sem código
# pela aba Configurações (Campos de busca), que grava em tb_campos_busca.
TEMPLATE_NOME_PADRAO = NOME_FINAL_PADRAO
CAMPOS_BUSCA_PADRAO = {
    # --- identificação ---
    "ficha": (
        "Ficha",
        r"(?:N['°o]?\s*da\s*)?Ficha\s*[:\s]*(\d[\d\s]{3,10})(?:\s*/\s*(\d{4}))?",
    ),
    "empenho": (
        "Empenho",
        r"(?:N['°o]?\s*do\s*Empenho|NOTA\s*DE\s*EMPENHO\s*N['°o]?)[\s\S]{0,40}?(\d{1,10})\s*/\s*(\d{4})",
    ),
    "parcela": (
        "Parcela",
        r"EMPENHO\s*PARCELA\s*[:\s]+(\d{1,10})\s*[-–]\s*(\d{1,3})",
    ),
    "ano": (
        "Ano",
        r"(?:EMPENHO\s*PARCELA|Exerc[íi]cio)[^\d]{0,30}?/\s*(\d{4})",
    ),
    "exercicio": (
        "Exercício",
        r"Exerc[íi]cio\s*[:\s]*(\d{4})",
    ),
    "processo": (
        "Processo",
        r"Processo\s*n['°o]?\s*[:\s]*(\d+/\d{4})",
    ),
    "tipo_empenho": (
        "Tipo de Empenho",
        r"Tipo\s*de\s*Empenho\s*[:\s]*([A-Za-záâãéêíóôõúçÁÂÃÉÊÍÓÔÕÚÇ]+)",
    ),
    "modalidade": (
        "Modalidade",
        r"Modalidade\s*[:\s]*([A-ZÁÂÃÉÊÍÓÔÕÚÇ /]+?)(?:\n|$)",
    ),
    "contrato_numero": (
        "Contrato Nº",
        r"Contrato\s*N['°o]?\s*[:\s]*([^\n]{1,30})",
    ),
    # --- estrutura orçamentária ---
    "orgao": (
        "Órgão",
        r"Org[aã]o\s*[:\s]*(\d+\s*[-–]\s*[^\n]{2,60})",
    ),
    "unidade": (
        "Unidade Orçamentária",
        r"Unidade(?:\s*Or[çc]ament[áa]ria)?\s*[:\s]*(\d+\s*[-–]\s*[^\n]{2,60})",
    ),
    "sub_unidade": (
        "Sub-Unidade",
        r"Sub\s*Unidade\s*[:\s]*(\d+\s*[-–]\s*[^\n]{2,60})",
    ),
    "funcao": (
        "Função",
        r"Fun[çc][aã]o\s*[:\s]*(\d+\s*[-–]\s*[^\n]{2,60})",
    ),
    "subfuncao": (
        "Subfunção",
        r"Subfun[çc][aã]o\s*[:\s]*(\d+\s*[-–]\s*[^\n]{2,60})",
    ),
    "programa": (
        "Programa",
        r"Programa\s*[:\s]*([^\n]{2,80})",
    ),
    "projeto_atividade": (
        "Projeto/Atividade",
        r"Projeto/Atividade\s*[:\s]*([^\n]{2,80})",
    ),
    "elemento_despesa": (
        "Elemento de Despesa",
        r"Elemento(?:\s*de\s*Despesa)?\s*[:\s]*([\d\s]+[-–][^\n]{3,60})",
    ),
    "subelemento": (
        "SubElemento",
        r"SubElemento\s*[:\s]*([\d\s]+[-–][^\n]{3,60})",
    ),
    "fonte_recurso": (
        "Fonte de Recurso",
        r"Fonte\s*(?:de\s*)?Recurso\s*[:\s]*([\d\s]+[-–][^\n]{3,60})",
    ),
    "subfonte": (
        "SubFonte",
        r"SubFonte\s*[:\s]*([^\n]{3,80})",
    ),
    "dotacao": (
        "Dotação",
        r"Dota[çc][aã]o\s*[:\s]*([^\n]{3,80})",
    ),
    # --- favorecido / recebedor ---
    "favorecido_nome": (
        "Favorecido",
        r"Favorecido\s*[:\s]*(?:\d+\s*[-–]\s*)?(?!Endere[çc]o|Cidade|Bairro|CNPJ|CPF|Telefone)([A-ZÁÂÃÉÊÍÓÔÕÚÇ][A-ZÁÂÃÉÊÍÓÔÕÚÇ ]{5,80})",
    ),
    "favorecido_codigo": (
        "Código Favorecido",
        r"Favorecido\s*[:\s]*(\d+)\s*[-–]",
    ),
    "favorecido_cpf": (
        "CPF/CNPJ Favorecido",
        r"CNPJ/CPF\s*[:\s]*([\d\.\-/\s]{11,20})",
    ),
    "favorecido_endereco": (
        "Endereço Favorecido",
        r"Endere[çc]o\s*[:\s]*([^\n]{5,80})",
    ),
    "favorecido_bairro": (
        "Bairro",
        r"Bairro\s*[:\s]*([^\n]{2,40})",
    ),
    "favorecido_cidade": (
        "Cidade",
        r"Cidade\s*[:\s]*([^\n]{3,50})",
    ),
    "favorecido_uf": (
        "UF",
        r"\bUF\s*[:\s]*([A-Za-z ]{2,30})",
    ),
    "recebedor_nome": (
        "Recebedor",
        r"(?:QUITADO|Recebedor|Favorecido)\s*[:\s]*([A-ZÁÂÃÉÊÍÓÔÕÚÇ][A-ZÁÂÃÉÊÍÓÔÕÚÇ ]{4,80})",
    ),
    # --- financeiro ---
    "valor_bruto": (
        "Valor Bruto",
        r"Valor\s*Bruto\s*[:\s]*([\d\.\,\s]{2,20})",
    ),
    "valor_liquido": (
        "Valor Líquido",
        r"VALOR\s*L[ÍI]QUIDO\s*[:\s]*([\d\.\,]+)",
    ),
    "especificacao": (
        "Especificação/Histórico",
        r"(?:Especifica[çc][aã]o|Hist[óo]rico)\s*[:\s]*([^\n]{10,300})",
    ),
    "saldo_anterior": (
        "Saldo Anterior",
        r"Saldo\s*Anterior\s*[:\s]*([\d\.\,]+)",
    ),
    "saldo_disponivel": (
        "Saldo Disponível",
        r"Saldo\s*Dispon[íi]vel\s*[:\s]*([\d\.\,]+)",
    ),
    "diarias_numero": (
        "Diária Nº",
        r"Di[áa]ria\s*N['°o]?\s*[:\s]*(\d+)",
    ),
    # --- bancário ---
    "banco": (
        "Banco",
        r"Banco\s*[:\s]*(\d+)",
    ),
    "agencia": (
        "Agência",
        r"Ag[eê]ncia\s*[:\s]*([\d\-O\s]{1,10})",
    ),
    "conta": (
        "Conta",
        r"Conta\s*[:\s]*([\d\.\-]{5,20})",
    ),
    "pix": (
        "PIX",
        r"PIX\s*[:\s]*([^\n]{3,50})",
    ),
    "conta_pagamento": (
        "Conta Pagamento",
        r"CONTA\s*[:\s]*([\d\.\-\s]{5,30})",
    ),
    "conta_recebimento": (
        "Conta Recebimento",
        r"(?:SubFonte|RECURSOS\s*DISPON[ÍI]VEIS|DISPONIBILIDADE)[^\n:]*[:\s]*([^\n]{5,60})",
    ),
    # --- autorizador / responsáveis ---
    "autorizador_nome": (
        "Autorizador",
        r"Ordenador\s*da\s*Despesa\s*[^\n]{0,20}([A-ZÁÂÃÉÊÍÓÔÕÚÇ][A-Za-záâãéêíóôõúç ]{6,60})",
    ),
    "autorizador_cargo": (
        "Cargo Autorizador",
        r"Secret[áa]ri[ao]\s*de\s*([^\n]{3,50})",
    ),
    "contador_cpf": (
        "CPF Contador",
        r"CPF\s*[:\s]*([\d\.\-]{11,18})",
    ),
    # --- datas ---
    "data_emissao": (
        "Data do Empenho",
        r"Data\s*do\s*Empenho\s*[:\s]*([\d/]{8,12})",
    ),
    "data_vencimento": (
        "Data Vencimento",
        r"Data\s*Venc(?:imento|\.)\s*[:\s]*([\d/]{8,12})",
    ),
    "data_quitacao": (
        "Data Quitação",
        r"Data\s*Quita[çc][aã]o\s*[:\s]*([\d/]{8,12})",
    ),
    "decreto": (
        "Decreto",
        r"Decreto\s*N['°o]?\s*([\d/]+)",
    ),
}

# Colunas do índice FTS5 (RF-41) — cabeçalho do empenho (>=40 campos) + campos
# customizados extraídos por regex dinâmico (via tb_regex_regras.campo_destino).
FTS_COLS = [
    "nome_arquivo_original", "nome_arquivo_final", "numero_empenho", "parcela",
    "usuario", "data_criacao", "status", "caminho_arquivo",
    "orgao", "unidade", "sub_unidade", "funcao", "subfuncao", "programa",
    "projeto_atividade", "elemento_despesa", "subelemento", "fonte_recurso",
    "subfonte", "dotacao",
    "favorecido_nome", "favorecido_codigo", "favorecido_cpf", "favorecido_endereco",
    "favorecido_bairro", "favorecido_cidade", "favorecido_uf",
    "recebedor_nome", "autorizador_nome", "autorizador_cargo", "contador_cpf",
    "banco", "agencia", "conta", "conta_pagamento", "conta_recebimento", "pix",
    "valor_bruto", "valor_liquido", "especificacao", "saldo_anterior",
    "saldo_disponivel", "processo", "exercicio", "tipo_empenho", "modalidade",
    "contrato_numero", "data_emissao", "data_vencimento", "data_quitacao",
    "decreto", "diarias_numero",
    "texto_extraido", "campos_regex", "campos_json", "hash_arquivo", "tags",
    "conteudo_texto", "nota_interna",
]


def _conn():
    """Opens a connection to the module's own database (WAL).

    Conexão via `banco_conexao.conexao` — SQLite (db_mod_renomear_empenho.db,
    WAL) ou PostgreSQL (schema `empenhos`)."""
    from mod_intranet.banco_conexao import conexao
    conn = conexao("empenhos")
    if conn is None:
        raise RuntimeError("Falha ao abrir conexão do módulo Renomear Empenhos")
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _migrar_coluna(conn, tabela, coluna, tipo):
    """Adds a column to a table if it does not exist yet (idempotent migration)."""
    try:
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({tabela})").fetchall()]
        if coluna not in cols:
            conn.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo}")
    except Exception as e:
        _log().warning(f"_migrar_coluna: falha ao adicionar {tabela}.{coluna}: {e}")


def init_db_empenho():
    """Creates/migrates all module tables and seeds (idempotent bootstrap).

    Cria `tb_empenhos` (com migrações de `tipo_especial`/`ficha`/`ano`),
    `tb_indexador_pesquisa` (fallback), `tb_quarentena`, `tb_regex_regras`
    (semeada com 2 regras padrão), `tb_arquivos_auditoria` +
    `tb_eventos_arquivos` (trilha por arquivo), `tb_campos_busca` (semeada
    com ficha/empenho/parcela/ano), `tb_solicitacoes` (fluxo comum→admin) e
    a FTS5 virtual `tb_indexador_pesquisa_fts5` (32 colunas + trigger de
    exclusão + coluna `campo_destino` nas regras). Executado no import."""
    os.makedirs(_PASTA_MONITORADA_PADRAO, exist_ok=True)
    conn = _conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_empenhos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_arquivo_original TEXT,
            nome_arquivo_final TEXT NOT NULL,
            numero_empenho INTEGER,
            parcela INTEGER DEFAULT 1,
            tipo_especial TEXT,
            ficha TEXT,
            ano TEXT,
            usuario TEXT,
            data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'ativo',
            caminho_arquivo TEXT
        )
    """)
    _migrar_coluna(conn, "tb_empenhos", "tipo_especial", "TEXT")
    _migrar_coluna(conn, "tb_empenhos", "ficha", "TEXT")
    _migrar_coluna(conn, "tb_empenhos", "ano", "TEXT")
    # --- 40+ campos: colunas explicitas + JSON com todos os campos ---
    for _col in (
        "orgao", "unidade", "sub_unidade", "funcao", "subfuncao", "programa",
        "projeto_atividade", "elemento_despesa", "subelemento", "fonte_recurso",
        "subfonte", "dotacao",
        "favorecido_nome", "favorecido_codigo", "favorecido_cpf",
        "favorecido_endereco", "favorecido_bairro", "favorecido_cidade", "favorecido_uf",
        "recebedor_nome",
        "valor_bruto", "valor_liquido", "especificacao",
        "saldo_anterior", "saldo_disponivel", "diarias_numero",
        "banco", "agencia", "conta", "conta_pagamento", "conta_recebimento", "pix",
        "autorizador_nome", "autorizador_cargo", "contador_cpf",
        "processo", "exercicio", "tipo_empenho", "modalidade", "contrato_numero",
        "data_emissao", "data_vencimento", "data_quitacao", "decreto",
        "campos_json",
    ):
        _migrar_coluna(conn, "tb_empenhos", _col, "TEXT")
    # migra inclusões futuras de CAMPOS_BUSCA_PADRAO: todo campo novo vira coluna em tb_empenhos
    for _campo in CAMPOS_BUSCA_PADRAO:
        if _campo not in ("ficha", "empenho", "parcela", "ano"):
            _migrar_coluna(conn, "tb_empenhos", _campo, "TEXT")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_empenho_numero ON tb_empenhos(numero_empenho)")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_indexador_pesquisa (
            empenho_id INTEGER PRIMARY KEY,
            conteudo_texto TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_quarentena (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_arquivo TEXT NOT NULL,
            motivo TEXT,
            caminho_atual TEXT,
            data_insercao DATETIME DEFAULT CURRENT_TIMESTAMP,
            processado INTEGER DEFAULT 0
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_regex_regras (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_regra TEXT NOT NULL UNIQUE,
            padrao_regra TEXT NOT NULL,
            substituicao TEXT,
            ativo INTEGER DEFAULT 1,
            data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("SELECT COUNT(*) FROM tb_regex_regras")
    if cur.fetchone()[0] == 0:
        cur.execute(
            "INSERT INTO tb_regex_regras (nome_regra, padrao_regra) VALUES (?, ?)",
            ("Padrão Empenho", REGEX_PADRAO),
        )
        cur.execute(
            "INSERT INTO tb_regex_regras (nome_regra, padrao_regra) VALUES (?, ?)",
            ("Só números", r"(\d{6,10})"),
        )

    # ---- Auditoria dos arquivos escaneados/renomeados ----
    # Um registro por documento, rastreando o ciclo detectado -> renomeado ->
    # removido -> (re)processado. Espelha o "eventos/arquivos" do app original,
    # unificado numa trilha por arquivo no próprio banco do módulo.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_arquivos_auditoria (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_original TEXT,
            nome_renomeado TEXT,
            numero_empenho TEXT,
            parcela INTEGER DEFAULT 1,
            ficha TEXT,
            ano TEXT,
            caminho_original TEXT,
            caminho_final TEXT,
            hash_sha256_origem TEXT,
            hash_sha256_destino TEXT,
            status TEXT DEFAULT 'detectado',
            usuario TEXT,
            motivo_erro TEXT,
            data_deteccao DATETIME DEFAULT CURRENT_TIMESTAMP,
            data_renomeacao DATETIME,
            data_remocao DATETIME,
            data_ultimo_evento DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_aud_arq_status ON tb_arquivos_auditoria(status)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_aud_arq_num ON tb_arquivos_auditoria(numero_empenho)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_aud_arq_orig ON tb_arquivos_auditoria(nome_original)")

    # Linha do tempo cronológica por arquivo (detectado/renomeado/removido/erro).
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_eventos_arquivos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            arquivo_id INTEGER,
            nome_arquivo TEXT,
            tipo TEXT NOT NULL,
            detalhe TEXT,
            usuario TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (arquivo_id) REFERENCES tb_arquivos_auditoria(id) ON DELETE CASCADE
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ev_arq_id ON tb_eventos_arquivos(arquivo_id, id)")

    # ---- Campos de busca configuráveis por regex ----
    # Permite ao usuário (admin) editar a regex de identificação de cada campo
    # (ficha/empenho/parcela/ano/...), sem tocar no código. O 1º grupo capturado
    # é o valor do campo; o 2º grupo (se houver) é o ano.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_campos_busca (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campo TEXT NOT NULL UNIQUE,
            rotulo TEXT NOT NULL,
            padrao_regra TEXT NOT NULL,
            ativo INTEGER DEFAULT 1,
            data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("SELECT COUNT(*) FROM tb_campos_busca")
    if cur.fetchone()[0] == 0:
        for campo, (rotulo, padrao) in CAMPOS_BUSCA_PADRAO.items():
            cur.execute(
                "INSERT INTO tb_campos_busca (campo, rotulo, padrao_regra) VALUES (?, ?, ?)",
                (campo, rotulo, padrao),
            )

    # ---- Solicitações de envio (comum → master) ----
    # Fluxo: pendente → email (enviado) | zip_gerado → confirmar manual
    #        → recusado. `lote_id` agrupa solicitações de um mesmo pedido.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_solicitacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empenho_id INTEGER,
            arquivo_caminho TEXT NOT NULL,
            nome_arquivo TEXT NOT NULL,
            solicitante_nome TEXT,
            solicitante_email TEXT NOT NULL,
            mensagem TEXT,
            timestamp_solicitacao DATETIME DEFAULT CURRENT_TIMESTAMP,
            status TEXT NOT NULL DEFAULT 'pendente',
            timestamp_envio DATETIME,
            enviado_por TEXT,
            lote_id TEXT,
            metodo_envio TEXT,
            caminho_zip TEXT,
            motivo_recusa TEXT
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_solic_status ON tb_solicitacoes(status)")
    _migrar_coluna(conn, "tb_solicitacoes", "motivo_recusa", "TEXT")

    # FTS5 — índice de busca full-text (RF-41): cabeçalho do empenho (>=40 campos).
    # Semeia campos novos em tb_campos_busca (sem duplicar os já cadastrados).
    for _campo, (_rotulo, _padrao) in CAMPOS_BUSCA_PADRAO.items():
        try:
            cur.execute(
                "INSERT OR IGNORE INTO tb_campos_busca (campo, rotulo, padrao_regra) VALUES (?, ?, ?)",
                (_campo, _rotulo, _padrao),
            )
        except Exception:
            pass
    # Migra regex antigas para as novas mais tolerantes (aceitam variações OCR)
    try:
        for _campo, (_rotulo, _padrao) in CAMPOS_BUSCA_PADRAO.items():
            cur.execute("UPDATE tb_campos_busca SET padrao_regra=?, rotulo=? WHERE campo=?", (_padrao, _rotulo, _campo))
    except Exception:
        pass
    # Se o FTS já existe com colunas antigas (32), recria para o novo conjunto (>=42).
    try:
        cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='tb_indexador_pesquisa_fts5'")
        _fts_row = cur.fetchone()
        _fts_sql = (_fts_row[0] if _fts_row else "") or ""
        _precisa_recriar = False
        for _c in FTS_COLS:
            if _c not in _fts_sql:
                _precisa_recriar = True
                break
        if _precisa_recriar and _fts_row:
            cur.execute("DROP TABLE IF EXISTS tb_indexador_pesquisa_fts5")
    except Exception as e:
        _log().debug(f"FTS check: {e}")
    cur.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS tb_indexador_pesquisa_fts5 USING fts5("
        + ", ".join(FTS_COLS) + ")"
    )
    # Campo de destino dinâmico nas regras regex (alimenta colunas FTS customizadas).
    try:
        cur.execute("ALTER TABLE tb_regex_regras ADD COLUMN campo_destino TEXT")
    except Exception:
        pass  # coluna já existe em bancos previamente criados
    # Trigger: remove o índice FTS ao excluir o empenho.
    cur.execute("""
        CREATE TRIGGER IF NOT EXISTS tr_fts_del_empenho
        AFTER DELETE ON tb_empenhos
        BEGIN
            DELETE FROM tb_indexador_pesquisa_fts5 WHERE rowid = old.id;
        END
    """)
    conn.commit()
    conn.close()
    try:
        _campos_busca_ativos.cache_clear()
    except Exception:
        pass
    try:
        template_nome_atual.cache_clear()
    except Exception:
        pass


# ================= TEXTO / EXTRAÇÃO =================

def extrair_texto_pdf(caminho):
    """Extrai texto das primeiras páginas.

    Pipeline tolerante a PDFs escaneados:
        pymupdf → pdfplumber → OCR(pytesseract) → pikepdf(metadados) → pymupdf(imagens)
    Cada etapa só avança para a próxima se não produzir texto. PDFs escaneados
    sem camada de texto são reconhecidos via OCR (pytesseract) em vez de irem
    direto para a quarentena.
    """
    # 1) pymupdf (camada de texto nativa)
    try:
        import pymupdf
        doc = pymupdf.open(caminho)
        texto = "\n".join(doc[i].get_text() for i in range(min(PAGINAS_EXTRACAO, len(doc))))
        doc.close()
        if texto.strip():
            return texto
    except Exception as e:
        _log().debug(f"extrair_texto_pdf: pymupdf falhou para {caminho}: {e}")

    # 2) pdfplumber
    try:
        import pdfplumber
        with pdfplumber.open(caminho) as pdf:
            texto = "\n".join((p.extract_text() or "") for p in pdf.pages[:PAGINAS_EXTRACAO])
        if texto.strip():
            return texto
    except Exception as e:
        _log().debug(f"extrair_texto_pdf: pdfplumber falhou para {caminho}: {e}")

    # 3) OCR com pytesseract (PDFs escaneados)
    try:
        import pytesseract
        from PIL import Image
        import pymupdf as fitz
        doc = fitz.open(caminho)
        paginas = []
        for i in range(min(PAGINAS_EXTRACAO, len(doc))):
            pix = doc[i].get_pixmap(dpi=200)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            paginas.append(pytesseract.image_to_string(img, lang="por+eng"))
        doc.close()
        texto = "\n".join(paginas)
        if texto.strip():
            return texto
    except Exception as e:
        _log().debug(f"extrair_texto_pdf: OCR pytesseract falhou para {caminho}: {e}")

    # 4) pikepdf (metadados como último recurso)
    try:
        import pikepdf
        pdf = pikepdf.open(caminho)
        texto = " ".join(str(v) for v in pdf.docinfo.values() if v)
        pdf.close()
        if texto.strip():
            return texto
    except Exception as e:
        _log().debug(f"extrair_texto_pdf: pikepdf falhou para {caminho}: {e}")

    return ""


def _inicio_documento(texto_pagina):
    """True se a página parece início de um documento de empenho.

    Sinais fortes: NOTA DE EMPENHO/COMPLEMENTAÇÃO/ANULAÇÃO, EMPENHO PARCELA,
    PREFEITURA + CNPJ. Anexo de transferência/FROTA não é início."""
    t = texto_pagina or ""
    # TED e FROTA são anexos, não novos empenhos
    if re.search(r"COMPROVANTE\s*DE\s*TRANSFERENCIA|AGENDAMENTO\s*DE\s*VIAGENS", t, re.I):
        return False
    if re.search(r"NOTA\s*DE\s*(EMPENHO|COMPLEMENTA|ANULA)", t, re.I):
        return True
    if re.search(r"EMPENHO\s*PARCELA", t, re.I):
        return True
    # fallback: cabeçalho da prefeitura + número de ficha/empenho na mesma página
    if re.search(r"PREFEITURA\s*MUNICIPAL", t, re.I) and re.search(r"N['°o]?\s*da\s*Ficha|N['°o]?\s*do\s*Empenho", t, re.I):
        return True
    return False


def detectar_documentos_no_pdf(caminho):
    """Detecta múltiplos documentos em um único PDF escaneado.

    Varre página a página (via pymupdf) e agrupa em segmentos lógicos:
    cada vez que `_inicio_documento` é True, inicia novo segmento.
    TED/FROTA são anexos e ficam no segmento anterior.

    Retorna lista de dicts: {pag_inicio, pag_fim, empenho, tipo, texto}.
    Retorna [] se não conseguir abrir ou se PDF tem 0 páginas."""
    try:
        import pymupdf
    except Exception:
        return []
    try:
        doc = pymupdf.open(caminho)
    except Exception as e:
        _log().debug(f"detectar_documentos: falha ao abrir {caminho}: {e}")
        return []
    if len(doc) == 0:
        doc.close()
        return []
    textos_por_pagina = []
    for i in range(len(doc)):
        try:
            textos_por_pagina.append(doc[i].get_text() or "")
        except Exception:
            textos_por_pagina.append("")
    doc.close()
    # identifica páginas de início
    inicios = []
    for idx, txt in enumerate(textos_por_pagina):
        if _inicio_documento(txt):
            inicios.append(idx)
    if not inicios:
        # nenhum início detectado: trata como documento único
        texto_full = "\n".join(textos_por_pagina)
        dados = extrair_dados_empenho(texto_full)
        return [{"pag_inicio": 0, "pag_fim": len(textos_por_pagina) - 1,
                 "empenho": dados.get("empenho"), "tipo": detectar_tipo_especial(texto_full),
                 "paginas": len(textos_por_pagina)}]
    # constrói segmentos a partir dos inícios
    segmentos = []
    for s_idx, pag_ini in enumerate(inicios):
        pag_fim = (inicios[s_idx + 1] - 1) if s_idx + 1 < len(inicios) else len(textos_por_pagina) - 1
        texto_seg = "\n".join(textos_por_pagina[pag_ini:pag_fim + 1])
        dados = extrair_dados_empenho(texto_seg)
        # identificador do documento: ficha (mais estável que nº/AE) ou empenho
        ident = dados.get("ficha") or dados.get("empenho")
        segmentos.append({
            "pag_inicio": pag_ini,
            "pag_fim": pag_fim,
            "empenho": ident,
            "ficha": dados.get("ficha"),
            "tipo": detectar_tipo_especial(texto_seg),
            "paginas": pag_fim - pag_ini + 1,
        })
    return segmentos


def eh_multiplo_documento(caminho):
    """True se o PDF contém 2+ documentos distintos (empenhos diferentes).

    Critério: `detectar_documentos_no_pdf` retorna >=2 segmentos E
    os nº de empenho distintos são >=2 (evita falso-positivo de
    empenho 345 + anexos/FROTA/TED do mesmo empenho)."""
    segs = detectar_documentos_no_pdf(caminho)
    if len(segs) < 2:
        return False, segs
    nums = set()
    for s in segs:
        n = s.get("empenho")
        if n:
            # normaliza: remove zeros e não-dígitos
            nums.add(re.sub(r"\D", "", str(n)).lstrip("0") or "0")
    # também verifica nº via regex direta por segmento (fallback)
    if len(nums) < 2:
        # pode ser EC/EE/EG com números em `numero` em vez de `empenho`
        return False, segs
    return True, segs


def separar_pdf_por_documentos(caminho, destino_dir=None, usuario="sistema"):
    """Separa um PDF com múltiplos documentos em um PDF por segmento.

    Usa `detectar_documentos_no_pdf` para achar os intervalos de páginas
    e grava cada um como arquivo separado via pymupdf.

    Retorna lista de (caminho_novo, segmento) ou [] em falha."""
    try:
        import pymupdf
    except Exception as e:
        _log().warning(f"separar_pdf: pymupdf indisponível: {e}")
        return []
    segs = detectar_documentos_no_pdf(caminho)
    if len(segs) < 2:
        return []
    if destino_dir is None:
        destino_dir = os.path.dirname(caminho)
    os.makedirs(destino_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(caminho))[0]
    out = []
    try:
        src = pymupdf.open(caminho)
    except Exception as e:
        _log().warning(f"separar_pdf: falha ao abrir {caminho}: {e}")
        return []
    for seg in segs:
        ini, fim = seg["pag_inicio"], seg["pag_fim"]
        dst = pymupdf.open()
        try:
            dst.insert_pdf(src, from_page=ini, to_page=fim)
        except Exception as e:
            _log().warning(f"separar_pdf: falha ao copiar p{ini}-{fim}: {e}")
            continue
        nome_seg = f"{base}_parte{ini+1:02d}_p{ini+1}-{fim+1}.pdf"
        caminho_seg = os.path.join(destino_dir, nome_seg)
        # evita colisão
        c = 1
        while os.path.exists(caminho_seg):
            nome_seg = f"{base}_parte{ini+1:02d}_p{ini+1}-{fim+1}_{c}.pdf"
            caminho_seg = os.path.join(destino_dir, nome_seg)
            c += 1
        try:
            dst.save(caminho_seg)
            out.append((caminho_seg, seg))
        except Exception as e:
            _log().warning(f"separar_pdf: falha ao salvar {caminho_seg}: {e}")
        finally:
            dst.close()
    src.close()
    return out


def separar_documentos_quarentena(qid, usuario="sistema"):
    """Separa o PDF de um item da quarentena marcado como multi-documento.

    Remove o arquivo original da quarentena e re-injeta cada parte
    separada na pasta monitorada para reprocessamento normal.

    Retorna (ok: bool, msg: str)."""
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT nome_arquivo, caminho_atual, motivo FROM tb_quarentena WHERE id=?", (qid,))
        row = cur.fetchone()
        if not row or not row[1] or not os.path.exists(row[1]):
            return False, "Arquivo da quarentena não encontrado"
        nome, caminho_atual, motivo = row
        if "Múltiplos documentos" not in (motivo or ""):
            # tenta separar de qualquer forma se detectar multi
            eh_multi, _ = eh_multiplo_documento(caminho_atual)
            if not eh_multi:
                return False, "Arquivo não é múltiplo documento"
    finally:
        conn.close()
    partes = separar_pdf_por_documentos(caminho_atual, destino_dir=os.path.dirname(caminho_atual), usuario=usuario)
    if not partes:
        return False, "Falha ao separar — nenhuma parte gerada"
    # move cada parte para a 1ª pasta monitorada (ou mesma pasta) para reprocessamento
    pastas = pastas_monitoradas()
    destino_base = pastas[0] if pastas and pasta_acessivel(pastas[0]) else os.path.dirname(caminho_atual)
    os.makedirs(destino_base, exist_ok=True)
    movidas = []
    for caminho_seg, seg in partes:
        # se destino_dir era a quarentena, mover para a pasta monitorada
        if os.path.dirname(caminho_seg) != destino_base:
            novo = os.path.join(destino_base, os.path.basename(caminho_seg))
            try:
                shutil.move(caminho_seg, novo)
                movidas.append(novo)
            except Exception as e:
                _log().warning(f"separar quarentena: move {caminho_seg}: {e}")
                movidas.append(caminho_seg)
        else:
            movidas.append(caminho_seg)
    # remove original da quarentena; marca como processado
    try:
        os.remove(caminho_atual)
    except Exception:
        pass
    c2 = _conn()
    try:
        cc = c2.cursor()
        cc.execute("UPDATE tb_quarentena SET processado=1 WHERE id=?", (qid,))
        c2.commit()
    finally:
        c2.close()
    audit_log(usuario, "renomear-empenho", "separar_documentos",
              f"{nome}: separado em {len(movidas)} partes", hash_arquivo=None)
    # reprocessa cada parte
    sucessos = 0
    for p in movidas:
        try:
            r = processar_pdf(usuario, p)
            if r.get("ok"):
                sucessos += 1
        except Exception as e:
            _log().warning(f"separar quarentena reprocess {p}: {e}")
    return True, f"Separado em {len(movidas)} arquivos; {sucessos} processado(s)"


def extrair_numero(texto):
    """Applies active regex rules. Returns (numero, parcela) — (None,1) if not found."""
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT padrao_regra FROM tb_regex_regras WHERE ativo=1 ORDER BY id")
        for (padrao,) in cur.fetchall():
            try:
                m = re.search(padrao, texto or "", re.IGNORECASE)
            except re.error:
                continue
            if m:
                num = int(m.group(1)) if m.group(1) else None
                parc = int(m.group(2)) if (m.lastindex or 0) >= 2 and m.group(2) and m.group(2).isdigit() else 1
                return num, parc
        # fallback: qualquer número longo no texto
        m = re.search(r"(\d{6,})", texto or "")
        if m:
            return int(m.group(1)), 1
        return None, 1
    finally:
        conn.close()


def _proximo_contador():
    """Next sequential counter (max of active count and highest used number + 1)."""
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM tb_empenhos WHERE status='ativo'")
        n = cur.fetchone()[0]
        # garante unicidade mesmo após exclusões
        cur.execute("SELECT MAX(CAST(SUBSTR(nome_arquivo_final, 5, 4) AS INTEGER)) FROM tb_empenhos")
        mx = cur.fetchone()[0] or 0
        return max(n + 1, mx + 1)
    finally:
        conn.close()


@lru_cache(maxsize=1)
def _campos_busca_ativos():
    """Regex ativas de tb_campos_busca: {campo: (rotulo, padrao)}."""
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT campo, rotulo, padrao_regra FROM tb_campos_busca WHERE ativo=1")
        return {c: (r, p) for c, r, p in cur.fetchall()}
    finally:
        conn.close()


def extrair_dados_empenho(texto):
    """Identifica os campos do cabeçalho (ficha/empenho/parcela/ano) a partir do
    texto do PDF usando as regex configuráveis de tb_campos_busca.

    Retorna dict com as chaves dos campos conhecidos; cada valor é o 1º grupo
    capturado da regex (ou None se não achou). O campo 'ano' recebe o valor do
    2º grupo das regex que o carregam junto (ex.: 'N do Empenho: 0000345/2026').
    """
    texto = texto or ""
    campos = set(_campos_busca_ativos().keys()) or set(CAMPOS_BUSCA_PADRAO.keys())
    out = {c: None for c in campos}
    # backup das regex padrão caso a tabela esteja vazia
    regras = _campos_busca_ativos() or {c: v for c, v in CAMPOS_BUSCA_PADRAO.items()}
    for campo, (rotulo, padrao) in regras.items():
        try:
            m = re.search(padrao, texto, re.IGNORECASE)
        except re.error:
            continue
        if m:
            # parcela: usa o 2º grupo (nº da parcela), quando houver
            if campo == "parcela" and (m.lastindex or 0) >= 2 and m.group(2) and m.group(2).strip().isdigit():
                out[campo] = m.group(2).strip()
                # guarda também o ano se a regex de parcela o trouxer como 3º grupo
                if (m.lastindex or 0) >= 3 and m.group(3) and out.get("ano") is None:
                    out["ano"] = m.group(3).strip()
            else:
                out[campo] = m.group(1).strip() if m.group(1) else None
            # captura o ano do 2º grupo quando presente (ex.: X/2026) e ainda não definido
            if campo != "ano" and campo != "parcela" and (m.lastindex or 0) >= 2 and m.group(2):
                if out.get("ano") is None and m.group(2).strip().isdigit() and len(m.group(2).strip()) == 4:
                    out["ano"] = m.group(2).strip()
    # normaliza: limpa espaços duplos e remove quebras residuais nos valores
    _num_fields = {"ficha", "empenho", "processo", "valor_bruto", "valor_liquido",
                   "saldo_anterior", "saldo_disponivel", "banco", "agencia", "conta",
                   "conta_pagamento", "conta_recebimento", "favorecido_codigo",
                   "favorecido_cpf", "contador_cpf", "pix", "diarias_numero", "decreto"}
    for k in list(out.keys()):
        if out[k] and isinstance(out[k], str):
            out[k] = re.sub(r"\s+", " ", out[k]).strip()
            if k in _num_fields:
                # remove espaços internos em números (ex.: "1 .000,00" -> "1.000,00", "00003 17" -> "0000317")
                out[k] = re.sub(r"\s+", "", out[k])
    return out


@lru_cache(maxsize=1)
def template_nome_atual():
    """Template de nome final configurado (empenhos_template_nome) ou o padrão."""
    from mod_intranet.bd_conexao import get_config
    try:
        t = (get_config("empenhos_template_nome", "") or "").strip()
        return t if t else TEMPLATE_NOME_PADRAO
    except Exception:
        return TEMPLATE_NOME_PADRAO


def montar_nome_final(template, contador, dados):
    """Aplica o template de nome com os dados extraídos.

    Variáveis disponíveis no template:
      {contador}      contador sequencial (suporta {contador:04d})
      {empenho}       nº do empenho como inteiro (sem zeros à esquerda)
      {empenho_cru}   nº do empenho como extraído (pode ter zeros, ex: 0000345)
      {parcela}       parcela (inteiro; suporta {parcela:03d})
      {ficha}         nº da ficha (string do cabeçalho)
      {ano}           exercício/ano

    Retorna a string. Se alguma variável do template não existir nos dados,
    cai para o template padrão do módulo (robusto).
    """
    empenho_cru = str(dados.get("empenho") or "")
    try:
        empenho_num = int(re.sub(r"\D", "", empenho_cru)) if empenho_cru else 0
    except ValueError:
        empenho_num = 0
    valores = {
        "contador": int(contador or 0),
        "empenho": empenho_num,
        "empenho_cru": empenho_cru,
        "parcela": int(dados.get("parcela") or 1),
        "ficha": str(dados.get("ficha") or ""),
        "ano": str(dados.get("ano") or ""),
    }
    try:
        return template.format(**valores)
    except (KeyError, ValueError):
        # se alguma variável falhar (campo ausente), cai para o padrão robusto
        return NOME_FINAL_PADRAO.format(
            contador=int(contador or 0), empenho=empenho_num, parcela=valores["parcela"] or 1)


def processar_pdf(usuario, caminho_arquivo, numero=None, parcela=None, regex_custom=None):
    """Processa 1 PDF: extrai nº, renomeia, indexa e move. Retorna dict resultado.

    - Se `regex_custom` for informada, usa-a (case-insensitive) para capturar o nº.
    - Se `numero` for informado, pula a extração e usa o valor.
    - A identificação dos campos (ficha/empenho/parcela/ano) usa as regex
      configuráveis de tb_campos_busca; cria/atualiza o registro de auditoria
      do arquivo em tb_arquivos_auditoria.
    """
    nome_original = os.path.basename(caminho_arquivo)
    # --- detecção de múltiplos documentos em um único PDF ---
    # Se o arquivo contém 2+ empenhos distintos (ex.: lote escaneado), vai
    # para a quarentena com botão "Separar documentos" em vez de renomear.
    if numero is None and not regex_custom:
        try:
            eh_multi, segs = eh_multiplo_documento(caminho_arquivo)
            if eh_multi:
                nums = ", ".join(str(s.get("empenho") or "?") for s in segs)
                motivo = f"Múltiplos documentos detectados ({len(segs)} empenhos: {nums}) — use Separar"
                _log().warning(f"processar_pdf: {nome_original}: {motivo}")
                registrar_arquivo_detectado(nome_original, caminho_arquivo, usuario, status="erro", motivo=motivo)
                mover_quarentena(usuario, caminho_arquivo, motivo)
                return {"ok": False, "motivo": motivo, "multi": True, "segmentos": segs}
        except Exception as e:
            _log().debug(f"processar_pdf: detecção multi-doc falhou: {e}")
    texto = extrair_texto_pdf(caminho_arquivo)

    if not texto.strip():
        _log().warning(f"processar_pdf: sem texto legível em {nome_original}")
        registrar_arquivo_detectado(nome_original, caminho_arquivo, usuario, status="erro",
                                    motivo="PDF sem texto legível (possivelmente escaneado)")
        mover_quarentena(usuario, caminho_arquivo, "PDF sem texto legível (possivelmente escaneado)")
        return {"ok": False, "motivo": "sem texto"}

    dados = extrair_dados_empenho(texto)

    # Detecção de tipo especial (EC/EE/EG/AE) pelo conteúdo — feita ANTES da
    # extração genérica de "empenho", pois nesses documentos o nº do documento
    # difere do nº do empenho ao qual ele se refere (ex.: EC_24 reflete empenho
    # 66). Isso corrige a captura errada que ocorria nos modelos EC/EE/EG.
    tipo_especial = detectar_tipo_especial(texto)
    if tipo_especial and numero is None and not regex_custom:
        dados_esp = extrair_dados_tipo_especial(texto, tipo_especial)
        numero = dados_esp.get("numero")
        dados["tipo_especial"] = tipo_especial
        for k in ("ano", "ficha", "empenho_original"):
            if dados_esp.get(k) and (dados.get(k) in (None, "")):
                dados[k] = dados_esp[k]

    # prioridade: numero explícito > regex_custom > regex padrão
    if numero is None and regex_custom:
        m = None
        try:
            m = re.search(regex_custom, texto or "", re.IGNORECASE)
        except re.error:
            m = None
        if m and m.group(1):
            numero = int(m.group(1))
            parcela = int(m.group(2)) if (m.lastindex or 0) >= 2 and m.group(2) and m.group(2).isdigit() else (parcela or 1)
            dados["empenho"] = str(numero)
            if dados.get("parcela") is None:
                dados["parcela"] = parcela
        else:
            registrar_arquivo_detectado(nome_original, caminho_arquivo, usuario, status="erro",
                                        motivo="Sem correspondência (regex informada)")
            return {"ok": False, "motivo": "sem correspondência (regex informada)"}

    if numero is None:
        if dados.get("empenho"):
            numero = int(re.sub(r"\D", "", str(dados["empenho"])))
        else:
            numero = None
        if dados.get("parcela") is not None:
            parcela = int(re.sub(r"\D", "", str(dados["parcela"])))
        elif parcela is None:
            parcela = 1

    if numero is None or numero <= 0:
        _log().warning(f"processar_pdf: nº de empenho não encontrado em {nome_original}")
        registrar_arquivo_detectado(nome_original, caminho_arquivo, usuario, status="erro",
                                    motivo="Número de empenho não encontrado no conteúdo")
        mover_quarentena(usuario, caminho_arquivo, "Número de empenho não encontrado no conteúdo")
        return {"ok": False, "motivo": "sem numero"}

    contador = _proximo_contador()
    if dados.get("tipo_especial"):
        # tipos especiais usam nome próprio (EC_0024.pdf etc.), não o sequencial DOC
        nome_final = montar_nome_tipo_especial(dados["tipo_especial"], numero, dados.get("ano"))
    else:
        nome_final = montar_nome_final(template_nome_atual(), contador, dados)

    destino_dir = os.path.dirname(caminho_arquivo)
    destino = os.path.join(destino_dir, nome_final)
    try:
        os.rename(caminho_arquivo, destino)
    except OSError as e:
        _log().error(f"processar_pdf: falha ao renomear {nome_original}: {e}")
        registrar_arquivo_detectado(nome_original, caminho_arquivo, usuario, status="erro",
                                    motivo=f"Falha ao renomear: {e}")
        mover_quarentena(usuario, caminho_arquivo, f"Falha ao renomear: {e}")
        return {"ok": False, "motivo": str(e)}

    # --- grava os 40+ campos extraídos nas tabelas ---
    # Normaliza: garante que todo campo de CAMPOS_BUSCA_PADRAO exista em `dados`
    # (None se não extraído) e prepara o JSON com todos os campos para tabela/F.T.S.
    _todos_campos = set(CAMPOS_BUSCA_PADRAO.keys()) | set(dados.keys())
    # campos_json = snapshot completo dos dados extraídos (sem None vazios, para tabela)
    try:
        _campos_json = json.dumps({k: v for k, v in dados.items() if v not in (None, "")}, ensure_ascii=False)
    except Exception:
        _campos_json = "{}"
    # Colunas explicitas de tb_empenhos que espelham CAMPOS_BUSCA_PADRAO (além das 5 chaves)
    _cols_extras = [c for c in CAMPOS_BUSCA_PADRAO.keys() if c not in ("ficha", "empenho", "parcela", "ano")]
    # Linha base: sempre grava numero/parcela/ficha/ano + usuario/caminho + tipo_especial
    conn = _conn()
    try:
        cur = conn.cursor()
        # Constrói INSERT dinâmico: base + 40+ colunas extras + campos_json
        _base_cols = ["nome_arquivo_original", "nome_arquivo_final", "numero_empenho", "parcela",
                      "tipo_especial", "ficha", "ano", "usuario", "caminho_arquivo", "campos_json"]
        _base_vals = [nome_original, nome_final, numero, parcela,
                      dados.get("tipo_especial"), dados.get("ficha"), dados.get("ano"), usuario, destino, _campos_json]
        _cols = list(_base_cols)
        _vals = list(_base_vals)
        for _c in _cols_extras:
            _cols.append(_c)
            _vals.append(dados.get(_c))
        _ph = ", ".join("?" for _ in _cols)
        _col_sql = ", ".join(_cols)
        try:
            cur.execute(f"INSERT INTO tb_empenhos ({_col_sql}) VALUES ({_ph})", _vals)
        except Exception as e:
            # fallback: inserção mínima se alguma coluna ainda não existe (migração pendente)
            _log().warning(f"processar_pdf: insert dinâmico falhou ({e}), fallback mínimo")
            if dados.get("tipo_especial"):
                cur.execute(
                    """INSERT INTO tb_empenhos
                       (nome_arquivo_original, nome_arquivo_final, tipo_especial, numero_empenho,
                        ficha, ano, usuario, caminho_arquivo, campos_json)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (nome_original, nome_final, dados["tipo_especial"], numero,
                     dados.get("ficha"), dados.get("ano"), usuario, destino, _campos_json),
                )
            else:
                cur.execute(
                    """INSERT INTO tb_empenhos
                       (nome_arquivo_original, nome_arquivo_final, numero_empenho, parcela, usuario, caminho_arquivo, campos_json)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (nome_original, nome_final, numero, parcela, usuario, destino, _campos_json),
                )
        eid = cur.lastrowid
        cur.execute(
            "INSERT INTO tb_indexador_pesquisa (empenho_id, conteudo_texto) "
            "VALUES (?, ?) ON CONFLICT (empenho_id) "
            "DO UPDATE SET conteudo_texto = EXCLUDED.conteudo_texto",
            (eid, f"{nome_original} {nome_final} {texto[:4000]}"),
        )
        conn.commit()
        reindexar_empenho(eid)  # mantém o índice FTS5 em sincronia (RF-41)
        hash_src = hash_arquivo(caminho_arquivo) if os.path.exists(caminho_arquivo) else None
        hash_dst = hash_arquivo(destino)
        registrar_arquivo_renomeado(nome_original, nome_final, caminho_arquivo, destino,
                                    dados, usuario, hash_src, hash_dst)
        tipo_log = f" tipo {dados['tipo_especial']}" if dados.get("tipo_especial") else ""
        audit_log(usuario, "renomear-empenho", "processar",
                  f"{nome_original} → {nome_final}{tipo_log} (nº {numero})",
                  hash_arquivo=hash_dst)
        _log().info(f"empenho {numero}{tipo_log} processado: {nome_final}")
        return {"ok": True, "id": eid, "nome": nome_final, "numero": numero,
                "parcela": parcela, "tipo": dados.get("tipo_especial")}
    except Exception as e:
        conn.rollback()
        _log().exception(f"processar_pdf: erro ao gravar {nome_original}")
        return {"ok": False, "motivo": str(e)}
    finally:
        conn.close()


# ================= AUDITORIA DOS ARQUIVOS =================

def registrar_arquivo_detectado(nome_original, caminho_original, usuario="sistema",
                                status="detectado", motivo="", dados=None):
    """Registra (ou reativa) o arquivo em tb_arquivos_auditoria e grava o evento."""
    dados = dados or {}
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, status FROM tb_arquivos_auditoria WHERE nome_original=?", (nome_original,))
        row = cur.fetchone()
        if row:
            cur.execute(
                """UPDATE tb_arquivos_auditoria SET status=?, motivo_erro=?,
                   data_ultimo_evento=datetime('now','localtime'), data_remocao=NULL
                   WHERE id=?""",
                (status, motivo or None, row[0]))
            aid = row[0]
        else:
            cur.execute(
                """INSERT INTO tb_arquivos_auditoria
                   (nome_original, caminho_original, numero_empenho, parcela, ficha, ano,
                    status, usuario, motivo_erro)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (nome_original, caminho_original,
                 dados.get("empenho"), dados.get("parcela") or 1,
                 dados.get("ficha"), dados.get("ano"),
                 status, usuario, motivo or None))
            aid = cur.lastrowid
        cur.execute(
            """INSERT INTO tb_eventos_arquivos (arquivo_id, nome_arquivo, tipo, detalhe, usuario)
               VALUES (?, ?, ?, ?, ?)""",
            (aid, nome_original, status,
             motivo or f"Arquivo detectado na pasta ({status})", usuario))
        conn.commit()
        return aid
    finally:
        conn.close()


def registrar_arquivo_renomeado(nome_original, nome_final, caminho_original, caminho_final,
                                dados, usuario, hash_src=None, hash_dst=None):
    """Atualiza o registro de auditoria do arquivo para 'renomeado' + evento."""
    dados = dados or {}
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM tb_arquivos_auditoria WHERE nome_original=?", (nome_original,))
        row = cur.fetchone()
        if row:
            aid = row[0]
            cur.execute(
                """UPDATE tb_arquivos_auditoria SET
                     nome_renomeado=?, numero_empenho=?, parcela=?, ficha=?, ano=?,
                     caminho_original=?, caminho_final=?, hash_sha256_origem=?, hash_sha256_destino=?,
                     status='renomeado', usuario=?, motivo_erro=NULL,
                     data_renomeacao=datetime('now','localtime'),
                     data_ultimo_evento=datetime('now','localtime')
                   WHERE id=?""",
                (nome_final, dados.get("empenho"), dados.get("parcela") or 1,
                 dados.get("ficha"), dados.get("ano"),
                 caminho_original, caminho_final, hash_src, hash_dst,
                 usuario, aid))
        else:
            cur.execute(
                """INSERT INTO tb_arquivos_auditoria
                   (nome_original, nome_renomeado, numero_empenho, parcela, ficha, ano,
                    caminho_original, caminho_final, hash_sha256_origem, hash_sha256_destino,
                    status, usuario, data_renomeacao) VALUES
                   (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'renomeado', ?, datetime('now','localtime'))""",
                (nome_original, nome_final, dados.get("empenho"), dados.get("parcela") or 1,
                 dados.get("ficha"), dados.get("ano"),
                 caminho_original, caminho_final, hash_src, hash_dst, usuario))
            aid = cur.lastrowid
        cur.execute(
            """INSERT INTO tb_eventos_arquivos (arquivo_id, nome_arquivo, tipo, detalhe, usuario)
               VALUES (?, ?, 'renomeado', ?, ?)""",
            (aid, nome_final, f"{nome_original} -> {nome_final}", usuario))
        conn.commit()
        return aid
    finally:
        conn.close()


def registrar_arquivo_erro(nome_arquivo, caminho, usuario, motivo):
    """Registra falha de processamento e grava evento de erro."""
    return registrar_arquivo_detectado(nome_arquivo, caminho, usuario,
                                       status="erro", motivo=motivo)


def registrar_arquivo_removido(nome_arquivo, caminho, usuario="sistema"):
    """Marca o arquivo como removido (sumiu da pasta) + evento."""
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM tb_arquivos_auditoria WHERE nome_original=?", (nome_arquivo,))
        row = cur.fetchone()
        if row:
            aid = row[0]
            cur.execute(
                """UPDATE tb_arquivos_auditoria SET status='removido',
                   data_remocao=datetime('now','localtime'), data_ultimo_evento=datetime('now','localtime')
                   WHERE id=?""", (aid,))
        else:
            cur.execute(
                """INSERT INTO tb_arquivos_auditoria (nome_original, nome_renomeado, status, usuario)
                   VALUES (?, ?, 'removido', ?)""", (nome_arquivo, nome_arquivo, usuario))
            aid = cur.lastrowid
        cur.execute(
            """INSERT INTO tb_eventos_arquivos (arquivo_id, nome_arquivo, tipo, detalhe, usuario)
               VALUES (?, ?, 'removido', 'Arquivo deixou de existir na pasta monitorada', ?)""",
            (aid, nome_arquivo, usuario))
        conn.commit()
        return aid
    finally:
        conn.close()


def listar_arquivos_auditoria(status=None, limite=200):
    """Linha de tempo dos arquivos escaneados/renomeados."""
    conn = _conn()
    try:
        cur = conn.cursor()
        sql = ("SELECT id, nome_original, nome_renomeado, numero_empenho, parcela, ficha, ano, "
               "status, usuario, data_deteccao, data_renomeacao, data_remocao "
               "FROM tb_arquivos_auditoria")
        params = []
        if status:
            sql += " WHERE status=?"
            params.append(status)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limite)
        cur.execute(sql, params)
        return cur.fetchall()
    finally:
        conn.close()


def listar_eventos_arquivo(arquivo_id, limite=100):
    """Lists the chronological events of one file (newest first)."""
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT nome_arquivo, tipo, detalhe, usuario, timestamp
               FROM tb_eventos_arquivos WHERE arquivo_id=? ORDER BY id DESC LIMIT ?""",
            (arquivo_id, limite))
        return cur.fetchall()
    finally:
        conn.close()


def _registrar_removidos_monitor(usuario="sistema", pastas=None):
    """Marca como 'removido' os arquivos registrados como renomeados/detectados
    cujo arquivo já não existe mais em nenhuma pasta monitorada (rastreio)."""
    pastas = pastas or pastas_monitoradas()
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, nome_renomeado, nome_original FROM tb_arquivos_auditoria "
                    "WHERE status IN ('renomeado','detectado')")
        for aid, nr, no in cur.fetchall():
            alvo = nr or no
            if not alvo:
                continue
            achou = False
            for pasta in pastas:
                if not pasta_acessivel(pasta):
                    continue
                try:
                    for raiz, _dirs, arqs in os.walk(pasta):
                        if alvo in arqs:
                            achou = True
                            break
                    if achou:
                        break
                except Exception:
                    continue
            if not achou:
                _m = _conn()
                try:
                    c2 = _m.cursor()
                    c2.execute("UPDATE tb_arquivos_auditoria SET status='removido', "
                               "data_remocao=datetime('now','localtime'), "
                               "data_ultimo_evento=datetime('now','localtime') WHERE id=?", (aid,))
                    c2.execute("INSERT INTO tb_eventos_arquivos (arquivo_id, nome_arquivo, tipo, "
                               "detalhe, usuario) VALUES (?, ?, 'removido', "
                               "'Arquivo deixou de existir na pasta monitorada', ?)",
                               (aid, alvo, usuario))
                    _m.commit()
                finally:
                    _m.close()
    finally:
        conn.close()


def mover_quarentena(usuario, caminho_arquivo, motivo):
    """Moves a failed PDF to the quarantine folder and records it (LGPD audit).

    Copia o arquivo para `quarentena/` com prefixo de timestamp, grava a
        entrada em `tb_quarentena` (motivo truncado a 300 chars), audita com
        hash SHA-256 e registra o erro na trilha por arquivo."""
    os.makedirs(PASTA_QUARENTENA, exist_ok=True)
    nome = os.path.basename(caminho_arquivo)
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    destino = os.path.join(PASTA_QUARENTENA, f"{stamp}_{nome}")
    try:
        shutil.move(caminho_arquivo, destino)
        caminho_atual = destino
    except Exception as e:
        _log().error(f"mover_quarentena: falha ao mover {nome}: {e}")
        caminho_atual = ""
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO tb_quarentena (nome_arquivo, motivo, caminho_atual) VALUES (?, ?, ?)",
            (nome, motivo[:300], caminho_atual),
        )
        conn.commit()
    finally:
        conn.close()
    hash_arq = hash_arquivo(destino) if destino and os.path.exists(destino) else None
    audit_log(usuario, "renomear-empenho", "quarentena", f"{nome}: {motivo[:120]}",
              hash_arquivo=hash_arq)
    try:
        registrar_arquivo_erro(nome, destino or caminho_arquivo, usuario,
                               f"quarentena: {motivo[:200]}")
    except Exception:
        _log().exception("mover_quarentena: falha ao registrar erro na auditoria de arquivos")


# ================= CONSULTAS =================

def listar_empenhos(status="ativo", limite=200):
    """Lists processed empenhos (newest first): id, nomes, numero, parcela,
    usuario, data, caminho. `status` filtra pela coluna status ('ativo')."""
    conn = _conn()
    try:
        cur = conn.cursor()
        sql = """SELECT id, nome_arquivo_original, nome_arquivo_final, numero_empenho,
                        parcela, usuario, data_criacao, caminho_arquivo
                 FROM tb_empenhos"""
        params = []
        if status:
            sql += " WHERE status=?"
            params.append(status)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limite)
        cur.execute(sql, params)
        return cur.fetchall()
    finally:
        conn.close()


def _fts_insert_sql():
    """Builds the parameterized FTS5 INSERT for all index columns."""
    cols = ", ".join(FTS_COLS)
    placeholders = ", ".join("?" for _ in FTS_COLS)
    return f"INSERT INTO tb_indexador_pesquisa_fts5 (rowid, {cols}) VALUES (?, {placeholders})"


def _fts_escape(token):
    """Escapa aspas para uso seguro em frase FTS5 (aspas duplas duplicadas)."""
    return (token or "").replace('"', '""').strip()


def extrair_campos_regex(texto):
    """Aplica regras regex que possuem `campo_destino` definido e devolve
    dict {campo_destino: valor} — alimenta colunas FTS customizadas (RF-41)."""
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT padrao_regra, campo_destino FROM tb_regex_regras "
            "WHERE ativo=1 AND campo_destino IS NOT NULL AND campo_destino <> ''"
        )
        regras = cur.fetchall()
    finally:
        conn.close()
    out = {}
    if not texto:
        return out
    for padrao, campo in regras:
        try:
            m = re.search(padrao, texto or "", re.IGNORECASE)
        except re.error:
            continue
        if m and m.group(1):
            out[campo] = m.group(1)
    return out


def reindexar_empenho(eid):
    """Reconstrói a linha FTS5 do empenho `eid` a partir de tb_empenhos +
    texto indexado + campos extraídos por regex dinâmico (40+ cols)."""
    conn = _conn()
    try:
        cur = conn.cursor()
        # Lê registro completo de tb_empenhos, incluindo campos_json e os 40+ campos explicitos
        cur.execute("SELECT * FROM tb_empenhos WHERE id=?", (eid,))
        row = cur.fetchone()
        if not row:
            return
        # Mapeia colunas -> valores via PRAGMA
        cur.execute("PRAGMA table_info(tb_empenhos)")
        _colunas = [r[1] for r in cur.fetchall()]
        _mapa = {col: row[i] for i, col in enumerate(_colunas) if i < len(row)}
        cur.execute("SELECT conteudo_texto FROM tb_indexador_pesquisa WHERE empenho_id=?", (eid,))
        idx = cur.fetchone()
        texto = idx[0] if idx else (_mapa.get("campos_json") or "")
        # campos extraídos de forma dinâmica (tb_regex_regras) + campos do cabeçalho (tb_empenhos)
        campos_dyn = extrair_campos_regex(texto)
        try:
            _dados_json = json.loads(_mapa.get("campos_json") or "{}")
        except Exception:
            _dados_json = {}
        # mescla: dados do documento (40 campos) têm prioridade sobre dinâmicos
        _todos = {**campos_dyn, **{k: v for k, v in _dados_json.items() if v not in (None, "")}}
        # completa com colunas explicitas de tb_empenhos (expandidas)
        for _c in _colunas:
            if _c not in _todos and _c not in ("id", "nome_arquivo_original", "nome_arquivo_final",
                                                "numero_empenho", "parcela", "usuario", "data_criacao",
                                                "status", "caminho_arquivo", "campos_json", "tipo_especial"):
                v = _mapa.get(_c)
                if v not in (None, ""):
                    _todos[_c] = str(v)
        campos_json = json.dumps(_todos, ensure_ascii=False)
        valores = {
            "nome_arquivo_original": _mapa.get("nome_arquivo_original") or "",
            "nome_arquivo_final": _mapa.get("nome_arquivo_final") or "",
            "numero_empenho": str(_mapa.get("numero_empenho") or ""),
            "parcela": str(_mapa.get("parcela") or ""),
            "usuario": _mapa.get("usuario") or "",
            "data_criacao": (_mapa.get("data_criacao") or "")[:19],
            "status": _mapa.get("status") or "",
            "caminho_arquivo": _mapa.get("caminho_arquivo") or "",
            "texto_extraido": texto,
            "campos_regex": json.dumps(campos_dyn, ensure_ascii=False),
            "campos_json": campos_json,
            "conteudo_texto": f"{texto} " + " ".join(f"{k}:{v}" for k, v in _todos.items()),
        }
        # preenche automaticamente cada FTS_COL que corresponda a um campo extraído
        for _c in FTS_COLS:
            if _c not in valores:
                valores[_c] = str(_todos.get(_c, "") or _mapa.get(_c, "") or "")
        vals = [valores.get(c, "") for c in FTS_COLS]
        try:
            cur.execute("DELETE FROM tb_indexador_pesquisa_fts5 WHERE rowid=?", (eid,))
            cur.execute(_fts_insert_sql(), [eid] + vals)
        except Exception as e:
            _log().debug(f"reindexar_empenho: FTS5 indisponível ({e}) — "
                         f"mantém índice de fallback (tb_indexador_pesquisa)")
        conn.commit()
    finally:
        conn.close()


def rebuild_fts():
    """Reconstrói todo o índice FTS5 (usado na 1ª busca se estiver vazio)."""
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM tb_empenhos")
        ids = [r[0] for r in cur.fetchall()]
    finally:
        conn.close()
    for eid in ids:
        reindexar_empenho(eid)
    return len(ids)


def pesquisar(termo, limite=50):
    """Busca full-text via FTS5 (RF-41). Fallback para LIKE se o FTS falhar."""
    if not termo or not termo.strip():
        return []
    tokens = [t for t in termo.strip().split() if t]
    if not tokens:
        return []
    conn = _conn()
    try:
        cur = conn.cursor()
        try:
            cur.execute("SELECT COUNT(*) FROM tb_indexador_pesquisa_fts5")
            n = cur.fetchone()[0]
            if n == 0:
                try:
                    rebuild_fts()
                except Exception:
                    pass
            query = " AND ".join(f'"{_fts_escape(t)}"' for t in tokens)
            cur.execute(
                """SELECT e.id, e.nome_arquivo_final, e.numero_empenho, e.parcela,
                          e.usuario, e.data_criacao, e.caminho_arquivo
                   FROM tb_indexador_pesquisa_fts5 f
                   JOIN tb_empenhos e ON e.id = f.rowid
                   WHERE tb_indexador_pesquisa_fts5 MATCH ?
                   ORDER BY rank LIMIT ?""",
                (query, limite),
            )
            return cur.fetchall()
        except Exception as e:
            _log().warning(f"pesquisar FTS5 indisponível, fallback LIKE: {e}")
            like = f"%{termo.strip()}%"
            cur.execute(
                """SELECT e.id, e.nome_arquivo_final, e.numero_empenho, e.parcela,
                          e.usuario, e.data_criacao, e.caminho_arquivo
                   FROM tb_indexador_pesquisa i
                   JOIN tb_empenhos e ON e.id = i.empenho_id
                   WHERE i.conteudo_texto LIKE ?
                   ORDER BY e.id DESC LIMIT ?""",
                (like, limite),
            )
            return cur.fetchall()
    finally:
        conn.close()


def listar_quarentena(limite=100):
    """Lists quarantine entries (newest first): id, nome, motivo, data, processado, caminho."""
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT id, nome_arquivo, motivo, data_insercao, processado, caminho_atual
               FROM tb_quarentena ORDER BY id DESC LIMIT ?""",
            (limite,),
        )
        return cur.fetchall()
    finally:
        conn.close()


def reprocesse_quarentena(qid, novo_padrao=None, usuario="sistema"):
    """Reprocesses one quarantine item with an optional custom regex (or active rules).

    Reprocessa um item da quarentena aplicando a regex informada (ou as regras
    ativas quando None). Sem reiniciar — as regras são lidas do banco na hora."""
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT nome_arquivo, caminho_atual FROM tb_quarentena WHERE id=?", (qid,))
        row = cur.fetchone()
        if not row or not row[1] or not os.path.exists(row[1]):
            _log().warning(f"reprocesse_quarentena: item {qid} indisponível")
            return False, "Arquivo indisponível"
        caminho = os.path.realpath(os.path.abspath(row[1]))
        quar_real = os.path.realpath(os.path.abspath(PASTA_QUARENTENA))
        if not (caminho == quar_real or caminho.startswith(quar_real + os.sep)):
            _log().warning(f"reprocesse_quarentena: caminho fora da quarentena bloqueado: {caminho}")
            return False, "Caminho fora da quarentena"
    finally:
        conn.close()

    res = processar_pdf(usuario, caminho, regex_custom=novo_padrao)
    if res.get("ok"):
        c = _conn()
        try:
            cc = c.cursor()
            cc.execute("UPDATE tb_quarentena SET processado=1 WHERE id=?", (qid,))
            c.commit()
        finally:
            c.close()
        return True, res["nome"]
    return False, res.get("motivo", "?")


def promover_quarentena(usuario, caminho_arquivo, motivo):
    """Promotes a failed file to quarantine — alias of mover_quarentena (PLANO 4b).

    Promove um arquivo com falha para a quarentena — alias de `mover_quarentena`
    (nome previsto no PLANO 4b). Mantém compatibilidade com o roadmap sem
    duplicar lógica."""
    return mover_quarentena(usuario, caminho_arquivo, motivo)


def reprocessar_fila(usuario="sistema", novo_padrao=None):
    """Reprocesses the whole quarantine queue in batch without restarting.

    Reprocessa toda a fila da quarentena em lote, sem reiniciar o servidor.
    Itera sobre itens pendentes (`processado=0`), aplica `reprocesse_quarentena`
    em cada um (com `novo_padrao` opcional ou regras ativas) e retorna
    `(ok, mensagem, detalhes)` onde detalhes = lista de (qid, ok, msg).

    Hardening: valida tamanho de regex e confina caminho à quarentena."""
    if novo_padrao and len(novo_padrao) > REGEX_MAX_LEN:
        return False, f"Regex deve ter 1-{REGEX_MAX_LEN} caracteres", []
    if novo_padrao:
        try:
            re.compile(novo_padrao)
        except re.error as e:
            return False, f"Regex inválida: {e}", []
    pendentes = [r for r in listar_quarentena(limite=500) if not r[4]]
    if not pendentes:
        return True, "Fila vazia — nada a reprocessar", []
    detalhes = []
    sucessos = 0
    for qid, nome, motivo, data, proc, caminho in pendentes:
        try:
            ok, msg = reprocesse_quarentena(qid, novo_padrao=novo_padrao, usuario=usuario)
            detalhes.append((qid, ok, msg))
            if ok:
                sucessos += 1
        except Exception as e:
            _log().warning(f"reprocessar_fila qid={qid}: {e}")
            detalhes.append((qid, False, str(e)))
    total = len(pendentes)
    if sucessos == total:
        return True, f"Fila reprocessada: {sucessos}/{total} com sucesso", detalhes
    if sucessos > 0:
        return True, f"Fila reprocessada: {sucessos}/{total} com sucesso ({total - sucessos} falha(s) permanecem na quarentena)", detalhes
    return False, f"Nenhum item reprocessado ({total} falha(s)) — verifique as regex ativas", detalhes


# ================= REGRAS =================

REGEX_MAX_LEN = 200

@valida_regex(arg="padrao", max_len=200)
def salvar_regra(nome, padrao, ativo=True, campo_destino=None):
    """Creates/updates a regex rule (validated before saving). Returns (ok, msg).

    Valida tamanho (ReDoS), compila antes de gravar (recusa inválido);
    `campo_destino` (opcional) alimenta uma coluna FTS customizada. Aplicada
    imediatamente, sem reiniciar."""
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO tb_regex_regras (nome_regra, padrao_regra, ativo, campo_destino)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(nome_regra) DO UPDATE SET padrao_regra=?, ativo=?, campo_destino=?""",
            (nome, padrao, 1 if ativo else 0, campo_destino,
             padrao, 1 if ativo else 0, campo_destino),
        )
        conn.commit()
        return True, "Regra salva (aplicada imediatamente, sem reiniciar)"
    finally:
        conn.close()


def listar_regras():
    """Lists regex rules (id, nome, padrao, ativo, campo_destino) in creation order."""
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, nome_regra, padrao_regra, ativo, campo_destino "
            "FROM tb_regex_regras ORDER BY id")
        return cur.fetchall()
    finally:
        conn.close()


def alternar_regra(rid, ativo):
    """Ativa (1) ou inativa (0) uma regra regex. Retorna (ok, msg)."""
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE tb_regex_regras SET ativo=? WHERE id=?", (1 if ativo else 0, rid))
        conn.commit()
        return True, "Regra " + ("ativada" if ativo else "inativada")
    except Exception as e:
        _log().error(f"alternar_regra: erro ao alternar regra {rid}: {e}")
        return False, f"Erro: {e}"
    finally:
        conn.close()


def listar_regras_padrao(rid):
    """Returns the regex pattern of a rule by id (or None)."""
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT padrao_regra FROM tb_regex_regras WHERE id=?", (rid,))
        row = cur.fetchone()
        return row[0] if row else None
    finally:
        conn.close()


# ================= CAMPOS DE BUSCA CONFIGURÁVEIS (regex) =================

def listar_campos_busca():
    """Lista os campos de busca e suas regex (ficha/empenho/parcela/ano/...)."""
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, campo, rotulo, padrao_regra, ativo FROM tb_campos_busca ORDER BY id")
        return cur.fetchall()
    finally:
        conn.close()


def salvar_campo_busca(campo, rotulo, padrao, ativo=True):
    """Cria/atualiza um campo de busca com sua regex. Valida a regex antes.

    Campos novos são persistidos sem reiniciar e, na próxima captura
    (processar_pdf), passam a ser extraídos de cada PDF e gravados em
    `tb_empenhos.campos_json` + coluna dedicada (se o nome for válido
    para coluna SQLite). A inclusão futura é feita só pela UI de
    Configurações (sem tocar no código)."""
    if not campo or not campo.strip() or not padrao or not padrao.strip():
        return False, "Informe campo e padrão (regex)"
    try:
        re.compile(padrao)
    except re.error as e:
        return False, f"Regex inválida: {e}"
    campo_n = campo.strip().lower()
    if not re.match(r"^[a-z_][a-z0-9_]*$", campo_n):
        return False, "Nome do campo deve usar apenas letras minúsculas, números e _ (ex.: dotacao)"
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO tb_campos_busca (campo, rotulo, padrao_regra, ativo) VALUES (?, ?, ?, ?)
               ON CONFLICT(campo) DO UPDATE SET rotulo=?, padrao_regra=?, ativo=?""",
            (campo_n, (rotulo or "").strip() or campo_n, padrao.strip(), 1 if ativo else 0,
             (rotulo or "").strip() or campo_n, padrao.strip(), 1 if ativo else 0),
        )
        conn.commit()
        try:
            _campos_busca_ativos.cache_clear()
        except Exception:
            pass
    finally:
        conn.close()
    # inclusão futura: adiciona coluna dedicada em tb_empenhos para o novo campo
    try:
        _c = _conn()
        try:
            _migrar_coluna(_c, "tb_empenhos", campo_n, "TEXT")
            _c.commit()
        finally:
            _c.close()
    except Exception as e:
        _log().debug(f"salvar_campo_busca: migra coluna {campo_n}: {e}")
    audit_log("sistema", "renomear-empenho", "campo_cadastro",
              f"campo {campo_n} cadastrado/atualizado (regex)")
    return True, "Campo de busca salvo (aplicado imediatamente — novos PDFs já trazem o campo)"


def excluir_campo_busca(cid):
    """Deletes a search-field rule by id. Returns the number of rows removed."""
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM tb_campos_busca WHERE id=?", (cid,))
        conn.commit()
        try:
            _campos_busca_ativos.cache_clear()
        except Exception:
            pass
        return cur.rowcount
    finally:
        conn.close()


def restaurar_campos_busca_padrao():
    """Reinsere os campos padrão (ficha/empenho/parcela/ano) com regex de fábrica."""
    conn = _conn()
    try:
        cur = conn.cursor()
        for campo, (rotulo, padrao) in CAMPOS_BUSCA_PADRAO.items():
            cur.execute(
                """INSERT INTO tb_campos_busca (campo, rotulo, padrao_regra, ativo) VALUES (?, ?, ?, 1)
                   ON CONFLICT(campo) DO UPDATE SET rotulo=?, padrao_regra=?, ativo=1""",
                (campo, rotulo, padrao, rotulo, padrao),
            )
        conn.commit()
        try:
            _campos_busca_ativos.cache_clear()
        except Exception:
            pass
        return True
    finally:
        conn.close()


# ================= MONITOR E ORGANIZADOR =================

def rodar_monitor(usuario="sistema"):
    """Varre a raiz de TODAS as pastas monitoradas processando PDFs pendentes.

    Apenas a raiz de cada pasta é varrida (não recursivo). Pastas inacessíveis
    (ex.: host de rede fora do ar) são puladas com aviso, sem derrubar o monitor.
    A numeração sequencial é única entre pastas (contador global no banco).
    """
    pastas = pastas_monitoradas()
    resultados = []
    for pasta in pastas:
        if not pasta_acessivel(pasta):
            _log().warning(f"monitor: pasta inacessível, pulada: {pasta}")
            continue
        _log().info(f"monitor varrendo {pasta} (usuário {usuario})")
        for f in sorted(os.listdir(pasta)):
            if not f.lower().endswith(".pdf"):
                continue
            caminho = os.path.join(pasta, f)
            # pula arquivos já renomeados (padrão DOC) ou já registrados no banco
            if arquivo_ja_processado(f) or _arquivo_registrado_no_bd(caminho):
                continue
            try:
                resultados.append(processar_pdf(usuario, caminho))
            except Exception as e:
                _log().exception(f"rodar_monitor: erro ao processar {f}")
                try:
                    registrar_arquivo_erro(f, caminho, usuario, str(e))
                except Exception:
                    pass
                resultados.append({"ok": False, "motivo": str(e), "arquivo": f})
    # rastreia remoção (arquivos que sumiram das pastas)
    try:
        _registrar_removidos_monitor(usuario, pastas)
    except Exception as e:
        _log().debug(f"rodar_monitor: verificação de remoção falhou: {e}")
    return resultados


def organizar_pastas():
    """Organiza PDFs: ~200 páginas por subpasta, 4 subpastas por caixa.

    Estrutura: organizadorPasta/caixa_N/sub_X/doc_*.pdf
    Limites configuráveis via tb_config:
      - 'empenhos_organizador_paginas_pasta' (padrão 200)
      - 'empenhos_organizador_pastas_caixa'  (padrão 4)
    Retorna (ok, msg).
    """
    import pymupdf
    os.makedirs(PASTA_ORGANIZADOR, exist_ok=True)
    movidos, erros = 0, 0
    try:
        paginas_por_pasta = max(1, int(get_config("empenhos_organizador_paginas_pasta", "200") or 200))
    except ValueError:
        paginas_por_pasta = 200
    try:
        pastas_por_caixa = max(1, int(get_config("empenhos_organizador_pastas_caixa", "4") or 4))
    except ValueError:
        pastas_por_caixa = 4

    paginas_acum = 0
    sub_atual = 1
    caixa_atual = 1
    for row in listar_empenhos(status="ativo", limite=5000):
        _id, _orig, final, _num, _parc, _user, _dt, caminho = row
        if not caminho or not os.path.exists(caminho):
            continue
        try:
            doc = pymupdf.open(caminho)
            n_paginas = len(doc)
            doc.close()
        except Exception as e:
            _log().warning(f"organizar_pastas: não abriu {caminho}: {e}")
            n_paginas = 1

        # fecha a subpasta ao ultrapassar o limite de páginas por pasta
        if paginas_acum + n_paginas > paginas_por_pasta:
            paginas_acum = 0
            sub_atual += 1
            if sub_atual > pastas_por_caixa:
                sub_atual = 1
                caixa_atual += 1

        dir_caixa = os.path.join(PASTA_ORGANIZADOR, f"caixa_{caixa_atual:02d}")
        dir_sub = os.path.join(dir_caixa, f"sub_{sub_atual}")
        os.makedirs(dir_sub, exist_ok=True)

        destino = os.path.join(dir_sub, final)
        try:
            shutil.move(caminho, destino)
            c = _conn(); cc = c.cursor()
            cc.execute("UPDATE tb_empenhos SET caminho_arquivo=? WHERE id=?", (destino, _id))
            c.commit(); c.close()
            movidos += 1
            paginas_acum += n_paginas
        except Exception as e:
            _log().error(f"organizar_pastas: falha ao mover {final}: {e}")
            erros += 1

    _log().info(f"organizar_pastas: {movidos} organizado(s), {erros} erro(s)")
    # RF-44: gera capas por caixa + matrizDeDocumentos (txt/pdf) ao final da organização
    try:
        ok_m, msg_m = gerar_matriz_organizador()
        if ok_m:
            _log().info(f"organizar_pastas: {msg_m}")
            return True, f"{movidos} arquivo(s) organizado(s), {erros} erro(s). {msg_m}"
    except Exception:
        _log().exception("organizar_pastas: falha ao gerar matriz/capas")
    return True, f"{movidos} arquivo(s) organizado(s), {erros} erro(s)"


# ================= ORGANIZADOR FÍSICO COMPLETO (RF-44) =================
def _inventario_organizador():
    """Inventories the organizer: [(caixa, [(sub, [pdfs…])…])…] from disk."""
    itens = []
    if not os.path.isdir(PASTA_ORGANIZADOR):
        return itens
    for caixa in sorted(os.listdir(PASTA_ORGANIZADOR)):
        dir_c = os.path.join(PASTA_ORGANIZADOR, caixa)
        if not os.path.isdir(dir_c):
            continue
        subs = []
        for sub in sorted(os.listdir(dir_c)):
            dir_s = os.path.join(dir_c, sub)
            if not os.path.isdir(dir_s):
                continue
            docs = [f for f in sorted(os.listdir(dir_s)) if f.lower().endswith(".pdf")]
            subs.append((sub, docs))
        itens.append((caixa, subs))
    return itens


def _gerar_pdf_texto(conteudo, caminho):
    """Writes plain text into a single-page PDF (used by the matrix generator)."""
    import pymupdf
    doc = pymupdf.open()
    pag = doc.new_page()
    pag.insert_text((40, 40), conteudo, fontname="helv", fontsize=10)
    doc.save(caminho, garbage=4, deflate=True)
    doc.close()


def gerar_matriz_organizador():
    """Gera capa por caixa + `matrizDeDocumentos.txt`/`.pdf` (RF-44). Retorna (ok, msg)."""
    inv = _inventario_organizador()
    if not inv:
        return False, "Nada organizado ainda."
    linhas = ["MATRIZ DE DOCUMENTOS - Renomeador de Empenhos", "=" * 60]
    total = 0
    for caixa, subs in inv:
        linhas.append(f"\nCAIXA {caixa}")
        capa_caixa = []
        for sub, docs in subs:
            linhas.append(f"  {sub}: {len(docs)} doc(s)")
            capa_caixa.append(f"{sub}: {len(docs)} doc(s) -> " + ", ".join(docs))
            total += len(docs)
        # capa por caixa — gera TXT e PDF (4b/4c: capas PDF/TXT)
        conteudo_capa = f"CAPA DA CAIXA {caixa}\n" + "\n".join(capa_caixa) + "\n"
        try:
            with open(os.path.join(PASTA_ORGANIZADOR, caixa, "capa.txt"), "w", encoding="utf-8") as f:
                f.write(conteudo_capa)
            _gerar_pdf_texto(conteudo_capa, os.path.join(PASTA_ORGANIZADOR, caixa, "capa.pdf"))
        except Exception:
            _log().warning(f"gerar_matriz: falha ao gravar capa de {caixa}")
    linhas.append(f"\nTOTAL DE DOCUMENTOS: {total}")
    texto = "\n".join(linhas)
    try:
        with open(os.path.join(PASTA_ORGANIZADOR, "matrizDeDocumentos.txt"), "w", encoding="utf-8") as f:
            f.write(texto)
        _gerar_pdf_texto(texto, os.path.join(PASTA_ORGANIZADOR, "matrizDeDocumentos.pdf"))
        return True, f"Matriz gerada ({total} documentos)."
    except Exception as e:
        _log().exception("gerar_matriz: falha ao gravar matriz")
        return False, str(e)


def validar_presenca_matriz():
    """Valida que todos os PDFs listados na matriz existem no disco (RF-44).
    Retorna (ok, faltando)."""
    import re
    path = os.path.join(PASTA_ORGANIZADOR, "matrizDeDocumentos.txt")
    if not os.path.exists(path):
        return False, ["matrizDeDocumentos.txt ausente - gere a matriz primeiro"]
    with open(path, encoding="utf-8") as f:
        txt = f.read()
    faltando = []
    for m in re.findall(r"(\S+\.pdf)", txt):
        achou = False
        for raiz, _, arq in os.walk(PASTA_ORGANIZADOR):
            if m in arq:
                achou = True
                break
        if not achou:
            faltando.append(m)
    return (len(faltando) == 0), faltando


# ================= FERRAMENTAS DE PDF (RF-45) =================
# Saídas em pastas específicas, reutilizando as operações do mod_edit_pdf.
PASTA_MERGE = os.path.join(MOD_DIR, "datahora_mergePDF")
PASTA_CORTE = os.path.join(MOD_DIR, "datahora_cortePDF")
PASTA_REDUCAO = os.path.join(MOD_DIR, "datahora_reducaoPDF")
PASTA_TEMP_FERR = os.path.join(MOD_DIR, "tmp_ferramentas_pdf")


def _ferramenta_nome(base, sufixo):
    """Builds a timestamped output name for the embedded PDF tools."""
    from datetime import datetime as _dt
    return f"{_dt.now():%Y%m%d%H%M%S}_{base}{sufixo}"


def ferramenta_cortar(caminho_in, filtro, usuario="sistema"):
    """Corta um PDF (pares/ímpares/intervalo) usando o motor do mod_edit_pdf.
    Retorna (ok, caminho_ou_msg)."""
    if not caminho_in or not os.path.exists(caminho_in):
        return False, "Arquivo de entrada inexistente"
    os.makedirs(PASTA_CORTE, exist_ok=True)
    base = os.path.splitext(os.path.basename(caminho_in))[0]
    destino = os.path.join(PASTA_CORTE, _ferramenta_nome(base, "_corte.pdf"))
    try:
        from mod_edit_pdf.bd_manipulador import op_cortar
        ok, res = op_cortar(caminho_in, filtro, PASTA_CORTE,
                            os.path.basename(destino)[:-4])
        if ok:
            audit_log(usuario, "renomear-empenho", "ferramenta_corte",
                      f"{os.path.basename(caminho_in)} -> {os.path.basename(res)} (filtro={filtro})",
                      hash_arquivo=hash_arquivo(res))
            return True, res
        return False, res
    except Exception as e:
        _log().exception(f"ferramenta_cortar falhou para {caminho_in}")
        return False, str(e)


def ferramenta_juntar(caminhos_in, usuario="sistema"):
    """Mescla múltiplos PDFs em um único arquivo. Retorna (ok, caminho_ou_msg)."""
    caminhos = [c for c in (caminhos_in or []) if c and os.path.exists(c)]
    if len(caminhos) < 2:
        return False, "Selecione ao menos 2 PDFs válidos para mesclar"
    os.makedirs(PASTA_MERGE, exist_ok=True)
    destino = os.path.join(PASTA_MERGE, _ferramenta_nome("merge", ".pdf"))
    try:
        from mod_edit_pdf.bd_manipulador import op_juntar
        ok, msg = op_juntar(caminhos, destino)
        if ok and os.path.exists(destino):
            audit_log(usuario, "renomear-empenho", "ferramenta_juntar",
                      f"{len(caminhos)} arquivo(s) -> {os.path.basename(destino)}",
                      hash_arquivo=hash_arquivo(destino))
            return True, destino
        return False, msg
    except Exception as e:
        _log().exception("ferramenta_juntar falhou")
        return False, str(e)


def ferramenta_reduzir(caminho_in, usuario="sistema", qualidade=50, modo="leve", dpi=None):
    """Reduz o tamanho de um PDF. Retorna (ok, caminho_ou_msg)."""
    if not caminho_in or not os.path.exists(caminho_in):
        return False, "Arquivo de entrada inexistente"
    os.makedirs(PASTA_REDUCAO, exist_ok=True)
    base = os.path.splitext(os.path.basename(caminho_in))[0]
    destino = os.path.join(PASTA_REDUCAO, _ferramenta_nome(base, "_reducao.pdf"))
    try:
        from mod_edit_pdf.bd_manipulador import op_reduzir
        ok, msg = op_reduzir(caminho_in, destino, qualidade=qualidade, modo=modo, dpi=dpi)
        if ok and os.path.exists(destino):
            audit_log(usuario, "renomear-empenho", "ferramenta_reducao",
                      f"{os.path.basename(caminho_in)} -> {os.path.basename(destino)} "
                      f"(modo={modo} q{qualidade})",
                      hash_arquivo=hash_arquivo(destino))
            return True, destino
        return False, msg
    except Exception as e:
        _log().exception(f"ferramenta_reduzir falhou para {caminho_in}")
        return False, str(e)


def ferramenta_fontes(usuario="sistema"):
    """Lista fontes disponíveis: empenhos processados (caminho_arquivo)."""
    return [(r[0], r[2], r[7]) for r in listar_empenhos(status="ativo", limite=1000)
            if r[7] and os.path.exists(r[7])]


# ================= NAVEGAÇÃO (recursiva, só PDF, protegida) =================

def _path_real(path):
    """Absolute normalized path (resolves '~', '.' and '..' — anti-traversal)."""
    try:
        return os.path.realpath(os.path.abspath(os.path.expanduser(path or "")))
    except Exception:
        return os.path.abspath(path or "")


def raizes_navegacao():
    """Protected navigation roots: monitored folders + organizer folder."""
    raizes = [os.path.realpath(os.path.abspath(p)) for p in pastas_monitoradas()]
    if os.path.isdir(PASTA_ORGANIZADOR):
        raizes.append(os.path.realpath(os.path.abspath(PASTA_ORGANIZADOR)))
    return raizes


def pasta_navegavel(pasta):
    """True if `pasta` is inside one of the protected roots (anti-traversal)."""
    p = _path_real(pasta)
    for raiz in raizes_navegacao():
        r = _path_real(raiz)
        if p == r or p.startswith(r + os.sep):
            return True
    return False


def listar_navegacao(pasta):
    """Lista o conteúdo (só PDFs e subpastas) de um diretório para a navegação.

    Retorna {'raiz': bool, 'atual': caminho, 'dirs':[...], 'pdfs':[{nome, caminho, status}]}.
    Não escapa das raízes protegidas. Só mostra PDFs (nunca outros arquivos).
    """
    p = _path_real(pasta)
    e_raiz = p in [r for r in raizes_navegacao()]
    # se a pasta atual não é navegável, sobe até a primeira raiz navegável
    if not pasta_navegavel(p):
        for r in raizes_navegacao():
            if p == r or p.startswith(r + os.sep):
                p = r
                e_raiz = True
                break
        else:
            p = raizes_navegacao()[0] if raizes_navegacao() else PASTA_MONITORADA
            e_raiz = True
    dirs, pdfs = [], []
    try:
        for nome in sorted(os.listdir(p)):
            caminho = os.path.join(p, nome)
            if os.path.isdir(caminho):
                dirs.append({"nome": nome, "caminho": caminho})
            elif nome.lower().endswith(".pdf"):
                pdfs.append({"nome": nome, "caminho": caminho, "status": status_arquivo(caminho)})
    except Exception as e:
        _log().warning(f"listar_navegacao: erro em {p}: {e}")
    return {"raiz": e_raiz, "atual": p, "dirs": dirs, "pdfs": pdfs}


def status_arquivo(caminho):
    """Status de um PDF: 'processado' | 'pendente' (ou por conta do nome).

    Um arquivo é considerado processado se o nome segue o padrão DOC renomeado
    OU está registrado no banco como renomeado (nome_arquivo_final ou caminho).
    Para tipos especiais o critério é o banco — o nome de entrada (ex.: EE_9570)
    pode ter o mesmo número de dígitos do nome processado.
    """
    nome = os.path.basename(caminho or "")
    if arquivo_ja_processado(nome):
        return "processado"
    if _arquivo_registrado_no_bd(caminho):
        return "processado"
    if nome.lower().endswith(".pdf"):
        return "pendente"
    return "outros"


def _arquivo_registrado_no_bd(caminho):
    """True se o arquivo (por basename ou caminho completo) já foi processado conforme
    registrado em tb_empenhos ou tb_arquivos_auditoria."""
    try:
        nome = os.path.basename(caminho or "")
        conn = _conn()
        try:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM tb_empenhos WHERE nome_arquivo_final=? OR caminho_arquivo=? LIMIT 1",
                        (nome, os.path.realpath(caminho)))
            if cur.fetchone():
                return True
            cur.execute("SELECT 1 FROM tb_arquivos_auditoria WHERE nome_renomeado=? AND status='renomeado' LIMIT 1",
                        (nome,))
            return bool(cur.fetchone())
        finally:
            conn.close()
    except Exception:
        return False


def listar_pendentes(recursivo=False, limite=500):
    """Lista PDFs ainda não processados nas pastas monitoradas.

    Se `recursivo` for False (padrão do monitor automático), só a raiz de cada
    pasta é varrida; se True (navegação/fila manual), varre também subpastas.
    """
    pendentes = []
    for pasta in pastas_monitoradas():
        if not pasta_acessivel(pasta):
            continue
        if recursivo:
            for raiz, _dirs, arqs in os.walk(pasta):
                for f in sorted(arqs):
                    cam = os.path.join(raiz, f)
                    if not f.lower().endswith(".pdf"):
                        continue
                    if arquivo_ja_processado(f) or _arquivo_registrado_no_bd(cam):
                        continue
                    pendentes.append({"nome": f, "caminho": cam})
                    if len(pendentes) >= limite:
                        return pendentes
        else:
            for f in sorted(os.listdir(pasta)):
                cam = os.path.join(pasta, f)
                if not f.lower().endswith(".pdf"):
                    continue
                if arquivo_ja_processado(f) or _arquivo_registrado_no_bd(cam):
                    continue
                pendentes.append({"nome": f, "caminho": cam})
                if len(pendentes) >= limite:
                    return pendentes
    return pendentes


# ================= REVISÃO MANUAL (edição + renomeação com validação) =================

def _basename_sem_ext(path):
    """File name without extension (helper for manual rename)."""
    return os.path.splitext(os.path.basename(path))[0]


def renomear_manual(usuario, caminho_arquivo, novo_numero=None, novoTemplate=None,
                    novo_parcela=None, tipo_especial=None,
                    nova_ficha=None, novo_ano=None):
    """Renomeia manualmente um PDF na pasta monitorada.

    - novo_numero define o nº (se dor tipo especial, usa EC_xxxx etc.)
    - caso contrário, usa novoTemplate (padrão doc_{contador}...).
    - novo_parcela, nova_ficha e novo_ano sobrescrevem os campos extraídos
      (edição manual por campo — vale mesmo quando o OCR falhou num campo;
      os demais campos reconhecidos são preservados).
    Aplica o GATE de validação: só renomeia se a extração gerar resultado sem
    divergência crítica (nº identificado). Retorna (ok, msg).
    """
    caminho = _path_real(caminho_arquivo)
    if not os.path.exists(caminho):
        return False, "Arquivo não encontrado"
    if not pasta_navegavel(caminho):
        return False, "Ação fora das pastas monitoradas"
    nome_orig = os.path.basename(caminho)
    texto = extrair_texto_pdf(caminho)
    if not texto.strip():
        return False, "PDF sem texto legível; impossível validar manualmente"

    # gate: detecta tipo especial; se manual for genérico, respeita o tipo
    if tipo_especial is None:
        tipo_especial = detectar_tipo_especial(texto)

    if tipo_especial:
        de = extrair_dados_tipo_especial(texto, tipo_especial)
        num = novo_numero if novo_numero is not None else de.get("numero")
        if not num or num <= 0:
            return False, "Número do documento não identificado"
        nome_novo = montar_nome_tipo_especial(tipo_especial, num, de.get("ano"))
    else:
        contador = _proximo_contador()
        dados = extrair_dados_empenho(texto)
        if novo_numero is not None:
            dados["empenho"] = str(novo_numero)
        if novo_parcela is not None:
            dados["parcela"] = novo_parcela
        if nova_ficha is not None:
            dados["ficha"] = nova_ficha
        if novo_ano is not None:
            dados["ano"] = novo_ano
        num = int(re.sub(r"\D", "", str(dados.get("empenho") or "0")))
        if num <= 0:
            return False, "Número de empenho não identificado; informe um nº válido"
        template = novoTemplate or template_nome_atual()
        nome_novo = montar_nome_final(template, contador, dados)

    destino = os.path.join(os.path.dirname(caminho), nome_novo)
    destino = _evitar_colisao(destino)
    try:
        os.rename(caminho, destino)
    except OSError as e:
        _log().error(f"renomear_manual: falha ao renomear {nome_orig}: {e}")
        return False, f"Falha ao renomear: {e}"
    audit_log(usuario, "renomear-empenho", "revisao_manual",
              f"{nome_orig} → {os.path.basename(destino)} (manual)")
    return True, os.path.basename(destino)


def _evitar_colisao(destino):
    """Se o destino já existe, acrescenta _v2, _v3 etc. para não sobrescrever."""
    if not os.path.exists(destino):
        return destino
    base, ext = os.path.splitext(destino)
    i = 2
    while True:
        cand = f"{base}_v{i}{ext}"
        if not os.path.exists(cand):
            return cand
        i += 1


def editar_campos_empenho(empenho_id, campos):
    """Edita campos extraídos (ficha/empenho/ano/parcela) de um registro já
    processado, atualizando o índice. Retorna (ok, msg)."""
    conn = _conn()
    try:
        cur = conn.cursor()
        campos = campos or {}
        atual = {}
        cur.execute("SELECT * FROM tb_empenhos WHERE id=?", (empenho_id,))
        colunas = [d[0] for d in cur.description]
        row = cur.fetchone()
        if not row:
            return False, "Registro não encontrado"
        for c, v in zip(colunas, row):
            atual[c] = v
        nome_final = campos.get("nome_arquivo_final") or atual.get("nome_arquivo_final") or ""
        base = os.path.dirname(atual.get("caminho_arquivo") or "")
        novo_caminho = os.path.join(base, _evitar_colisao(
            os.path.join(base, nome_final))) if nome_final else atual.get("caminho_arquivo")
        if novo_caminho and nome_final and novo_caminho != atual.get("caminho_arquivo") \
           and os.path.exists(atual.get("caminho_arquivo")):
            os.rename(atual["caminho_arquivo"], novo_caminho)
        cur.execute(
            """UPDATE tb_empenhos SET
                 nome_arquivo_final=?, numero_empenho=?, parcela=?, ficha=?, ano=?, caminho_arquivo=?
               WHERE id=?""",
            (nome_final,
             campos.get("numero_empenho", atual.get("numero_empenho")),
             campos.get("parcela", atual.get("parcela")),
             campos.get("ficha", atual.get("ficha")),
             campos.get("ano", atual.get("ano")),
             novo_caminho or atual.get("caminho_arquivo"),
             empenho_id))
        conn.commit()
        reindexar_empenho(empenho_id)
        return True, "Campos atualizados"
    except Exception as e:
        conn.rollback()
        _log().exception("editar_campos_empenho falhou")
        return False, str(e)
    finally:
        conn.close()



def criar_solicitacao(arquivo_caminho, nome_arquivo, solicitante_nome, solicitante_email,
                      mensagem="", lote_id=None, empenho_id=None):
    """Registra pedido de envio de um documento. Retorna o id da solicitação."""
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO tb_solicitacoes
               (empenho_id, arquivo_caminho, nome_arquivo, solicitante_nome,
                solicitante_email, mensagem, lote_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (empenho_id, arquivo_caminho, nome_arquivo, solicitante_nome,
             solicitante_email, mensagem, lote_id or uuid4().hex),
        )
        aid = cur.lastrowid
        conn.commit()
        audit_log(solicitante_nome or "comum", "renomear-empenho", "solicitacao",
                  f"Solicitação de cópia de {nome_arquivo} por {solicitante_nome or 'usuário'} "
                  f"<{solicitante_email}>")
        return aid
    finally:
        conn.close()


def listar_solicitacoes(status=None, limite=500):
    """Lista solicitações. Sem filtro → todas; com filtro → só as de um status."""
    conn = _conn()
    try:
        cur = conn.cursor()
        if status:
            cur.execute("""SELECT * FROM tb_solicitacoes WHERE status=?
                           ORDER BY timestamp_solicitacao DESC LIMIT ?""", (status, limite))
        else:
            cur.execute("""SELECT * FROM tb_solicitacoes
                           ORDER BY timestamp_solicitacao DESC LIMIT ?""", (limite,))
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
    finally:
        conn.close()


def listar_solicitacoes_acao_pendente(limite=500):
    """Solicitações que exigem ação do master: pendente ou zip_gerado."""
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("""SELECT * FROM tb_solicitacoes WHERE status IN ('pendente','zip_gerado')
                       ORDER BY timestamp_solicitacao DESC LIMIT ?""", (limite,))
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
    finally:
        conn.close()


def obter_solicitacao(solicitacao_id):
    """Fetches one request as a dict (all columns) or None."""
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM tb_solicitacoes WHERE id=?", (solicitacao_id,))
        cols = [d[0] for d in cur.description]
        row = cur.fetchone()
        return dict(zip(cols, row)) if row else None
    finally:
        conn.close()


def marcar_solicitacao_enviada(solicitacao_id, enviado_por="master", metodo="email"):
    """Marca como enviada (email ou confirmação manual de envio de ZIP)."""
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """UPDATE tb_solicitacoes SET status='enviado', timestamp_envio=datetime('now','localtime'),
               enviado_por=?, metodo_envio=? WHERE id=?""",
            (enviado_por, metodo, solicitacao_id))
        conn.commit()
        audit_log(enviado_por, "renomear-empenho", "solicitacao_envio",
                  f"Solicitação #{solicitacao_id} marcada como enviada ({metodo})")
        return True
    finally:
        conn.close()


def marcar_solicitacoes_zip_gerado(ids_solicitacoes, caminho_zip, gerado_por="master"):
    """Marca um conjunto de solicitações como zip_gerado (aguardando confirmação)."""
    conn = _conn()
    try:
        cur = conn.cursor()
        for sid in (ids_solicitacoes or []):
            cur.execute(
                "UPDATE tb_solicitacoes SET status='zip_gerado', caminho_zip=? WHERE id=?",
                (caminho_zip, sid))
        conn.commit()
        audit_log(gerado_por, "renomear-empenho", "solicitacao_zip",
                  f"ZIP gerado para {len(ids_solicitacoes or [])} solicitações: {os.path.basename(caminho_zip)}")
        return True
    finally:
        conn.close()


def marcar_solicitacao_pendente(solicitacao_id):
    """Reverte 'zip_gerado' para 'pendente' (ZIP cancelado pelo master)."""
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE tb_solicitacoes SET status='pendente', caminho_zip=NULL WHERE id=?", (solicitacao_id,))
        conn.commit()
        return True
    finally:
        conn.close()


def marcar_solicitacao_recusada(solicitacao_id, motivo="", usuario="master"):
    """Marks a request as refused (with reason) and audits it."""
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE tb_solicitacoes SET status='recusado', motivo_recusa=? WHERE id=?", (motivo or "", solicitacao_id))
        conn.commit()
        audit_log(usuario, "renomear-empenho", "solicitacao_recusa",
                  f"Solicitação #{solicitacao_id} recusada: {motivo or 'sem motivo'}")
        return True
    finally:
        conn.close()


def agrupar_solicitacoes_em_lote(itens):
    """Agrupa solicitações (dicts) por lote_id, mantendo as avulsas. Retorna
    (lotes, avulsas): lotes = {lote_id: [sol...]}, avulsas = [sol...]."""
    lotes, avulsas = {}, []
    for s in itens or []:
        lid = s.get("lote_id")
        if lid:
            lotes.setdefault(lid, []).append(s)
        else:
            avulsas.append(s)
    return lotes, avulsas


def gerar_zip_solicitacoes(itens, pasta_zip=None):
    """Empacota os arquivos das solicitações num ZIP (para envio manual).

    Retorna (ok, caminho_zip ou mensagem)."""
    import zipfile
    pasta_zip = pasta_zip or os.path.join(MOD_DIR, "downloads")
    os.makedirs(pasta_zip, exist_ok=True)
    primeiro = itens[0] if itens else {}
    nome = primeiro.get("solicitante_nome") or "docs"
    nome = "".join(c for c in nome if c.isalnum() or c in "._- ").strip() or "docs"
    data = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_path = os.path.join(pasta_zip, f"solic_{nome}_{data}.zip")
    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            for s in itens:
                p = s.get("arquivo_caminho")
                if p and os.path.exists(p):
                    z.write(p, arcname=s.get("nome_arquivo") or os.path.basename(p))
        return True, zip_path
    except Exception as e:
        _log().exception(f"falha ao gerar ZIP de solicitações")
        return False, str(e)


def enviar_solicitacao_por_email(itens, destinatario=None):
    """Envia por e-mail os arquivos de um grupo de solicitações via SMTP central.

    Retorna (ok, msg)."""
    from mod_intranet.email_util import enviar_email as _enviar
    if not destinatario:
        destinatario = itens[0].get("solicitante_email") if itens else None
    if not destinatario:
        return False, "Solicitante sem e-mail"
    caminhos = [s.get("arquivo_caminho") for s in itens
                if s.get("arquivo_caminho") and os.path.exists(s.get("arquivo_caminho"))]
    if not caminhos:
        return False, "Nenhum arquivo existe mais"
    nome = (itens[0].get("solicitante_nome") or "").strip() or "usuário"
    ok, msg = _enviar(
        destinatario,
        f"Documentos solicitados ({len(caminhos)})",
        f"Olá {nome},\n\nSegue(m) o(s) documento(s) solicitado(s) no sistema de empenhos.\n\n"
        f"Total de arquivos: {len(caminhos)}.",
        anexos=caminhos,
    )
    return ok, msg


from uuid import uuid4


init_db_empenho()
