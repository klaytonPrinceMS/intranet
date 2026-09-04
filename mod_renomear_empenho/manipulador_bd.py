"""Módulo Renomear Empenhos — monitor de pasta, regex dinâmicas, quarentena,
renomeação sequencial e organizador físico (~200 págs/pasta, 4 pastas/caixa)."""
import sys, os, re, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

import sqlite3
import shutil
import io
from datetime import datetime

from mod_intranet.conexao_bd import get_connection, get_config
from mod_intranet.manipulador_bd import audit_log, hash_arquivo

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _log():
    from mod_intranet import observabilidade
    return observabilidade.get_logger("renomear_empenho")
DB_EMPENHO_PATH = os.path.join(BASE_DIR, "db_mod_renomear_empenho.db")
PASTA_ORGANIZADOR = os.path.join(BASE_DIR, "organizadorPasta")
PASTA_QUARENTENA = os.path.join(BASE_DIR, "quarentena")
_PASTA_MONITORADA_PADRAO = os.path.join(BASE_DIR, "doc")
PASTA_MONITORADA = _PASTA_MONITORADA_PADRAO


def pastas_monitoradas():
    """Lista de pastas monitoradas pelo módulo (rede/UNC ou local), editável em
    tb_config na chave 'empenhos_pastas_monitoradas' sem reiniciar.

    O valor é uma lista com UMA PASTA POR LINHA. Cada pasta pode ser:
      - local absoluta (C:\\empenhos, /dados/empenhos);
      - local relativa à raiz do projeto (ex.: doc);
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
            v = (get_config("empenhos_pasta_monitorada", "") or "").strip()
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
    return os.path.normpath(os.path.join(BASE_DIR, v))


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
    from mod_intranet.conexao_bd import set_config
    limpos = []
    for v in (lista or []):
        v = _normalizar_pasta(v)
        if v not in limpos:
            limpos.append(v)
    set_config("empenhos_pastas_monitoradas", "\n".join(limpos))
    return limpos

REGEX_PADRAO = r"(?:empenho|emp|ne)[\s\.: nº]*(\d{4,10})(?:[-/](\d{1,3}))?"
NOME_FINAL_PADRAO = "doc_{contador:04d}_numEmpenho_{empenho}_p{parcela:03d}.pdf"
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
    # padrão DOC: doc_0001_numEmpenho_345_p001.pdf
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
TEMPLATE_NOME_PADRAO = NOME_FINAL_PADRAO
CAMPOS_BUSCA_PADRAO = {
    "ficha": (
        "Ficha",
        r"N['°o]?\s*da\s*Ficha[\s\S]{0,40}?(\d{1,10})\s*/\s*(\d{4})",
    ),
    "empenho": (
        "Empenho",
        r"N['°o]?\s*do\s*Empenho[\s\S]{0,40}?(\d{1,10})\s*/\s*(\d{4})",
    ),
    "parcela": (
        "Parcela",
        r"EMPENHO\s*PARCELA\s*[:\s]+(\d{1,10})\s*[-–]\s*(\d{1,3})",
    ),
    "ano": (
        "Ano",
        r"(?:EMPENHO\s*PARCELA|Exerc[íi]cio)[^\d]{0,30}?/\s*(\d{4})",
    ),
}

# Colunas do índice FTS5 (RF-41) — cabeçalho do empenho (>=30 campos) + campos
# customizados extraídos por regex dinâmico (via tb_regex_regras.campo_destino).
FTS_COLS = [
    "nome_arquivo_original", "nome_arquivo_final", "numero_empenho", "parcela",
    "usuario", "data_criacao", "status", "caminho_arquivo",
    "pagador", "cpf_cnpj", "orgao", "valor", "data_emissao", "data_vencimento",
    "modalidade", "processo", "dotacao", "favorecido", "cnpj_favorecido",
    "endereco", "municipio", "uf", "cep", "telefone", "email", "observacao",
    "texto_extraido", "campos_regex", "hash_arquivo", "tags", "conteudo_texto", "nota_interna",
]


def _conn():
    conn = sqlite3.connect(DB_EMPENHO_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _migrar_coluna(conn, tabela, coluna, tipo):
    """Adiciona coluna a tabela se ela ainda não existir (migração p/ bancos
    antigos criados antes da coluna existir). Não falha se já existir."""
    try:
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({tabela})").fetchall()]
        if coluna not in cols:
            conn.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo}")
    except Exception as e:
        _log().warning(f"_migrar_coluna: falha ao adicionar {tabela}.{coluna}: {e}")


def init_db_empenho():
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

    # FTS5 — índice de busca full-text (RF-41): cabeçalho do empenho (>=30 campos).
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


def extrair_numero(texto):
    """Aplica regras regex ativas. Retorna (numero, parcela) — (None,1) se não achar."""
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
            out[campo] = m.group(1) if m.group(1) else None
            # captura o ano do 2º grupo quando presente (ex.: X/2026) e ainda não definido
            if campo != "ano" and (m.lastindex or 0) >= 2 and m.group(2):
                if out.get("ano") is None:
                    out["ano"] = m.group(2)
    return out


def template_nome_atual():
    """Template de nome final configurado (empenhos_template_nome) ou o padrão."""
    from mod_intranet.conexao_bd import get_config
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

    conn = _conn()
    try:
        cur = conn.cursor()
        if dados.get("tipo_especial"):
            cur.execute(
                """INSERT INTO tb_empenhos
                   (nome_arquivo_original, nome_arquivo_final, tipo_especial, numero_empenho,
                    ficha, ano, usuario, caminho_arquivo)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (nome_original, nome_final, dados["tipo_especial"], numero,
                 dados.get("ficha"), dados.get("ano"), usuario, destino),
            )
        else:
            cur.execute(
                """INSERT INTO tb_empenhos
                   (nome_arquivo_original, nome_arquivo_final, numero_empenho, parcela, usuario, caminho_arquivo)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (nome_original, nome_final, numero, parcela, usuario, destino),
            )
        eid = cur.lastrowid
        cur.execute(
            "INSERT OR REPLACE INTO tb_indexador_pesquisa (empenho_id, conteudo_texto) VALUES (?, ?)",
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
    texto indexado + campos extraídos por regex dinâmico."""
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, nome_arquivo_original, nome_arquivo_final, numero_empenho, "
            "parcela, usuario, data_criacao, status, caminho_arquivo "
            "FROM tb_empenhos WHERE id=?", (eid,))
        row = cur.fetchone()
        if not row:
            return
        cur.execute("SELECT conteudo_texto FROM tb_indexador_pesquisa WHERE empenho_id=?", (eid,))
        idx = cur.fetchone()
        texto = idx[0] if idx else ""
        campos = extrair_campos_regex(texto)
        campos_json = json.dumps(campos, ensure_ascii=False)
        valores = {
            "nome_arquivo_original": row[1] or "",
            "nome_arquivo_final": row[2] or "",
            "numero_empenho": str(row[3] or ""),
            "parcela": str(row[4] or ""),
            "usuario": row[5] or "",
            "data_criacao": (row[6] or "")[:19],
            "status": row[7] or "",
            "caminho_arquivo": row[8] or "",
            "texto_extraido": texto,
            "campos_regex": campos_json,
            "conteudo_texto": f"{texto} " + " ".join(f"{k}:{v}" for k, v in campos.items()),
        }
        vals = [valores.get(c, "") for c in FTS_COLS]
        cur.execute("DELETE FROM tb_indexador_pesquisa_fts5 WHERE rowid=?", (eid,))
        cur.execute(_fts_insert_sql(), [eid] + vals)
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
        cur.execute("SELECT COUNT(*) FROM tb_indexador_pesquisa_fts5")
        if cur.fetchone()[0] == 0:
            rebuild_fts()
        query = " AND ".join(f'"{_fts_escape(t)}"' for t in tokens)
        try:
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
            _log().warning(f"pesquisar FTS5 falhou, fallback LIKE: {e}")
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
    """Reprocessa item da quarentena aplicando a regex informada (ou as regras ativas)."""
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT nome_arquivo, caminho_atual FROM tb_quarentena WHERE id=?", (qid,))
        row = cur.fetchone()
        if not row or not row[1] or not os.path.exists(row[1]):
            _log().warning(f"reprocesse_quarentena: item {qid} indisponível")
            return False, "Arquivo indisponível"
    finally:
        conn.close()

    res = processar_pdf(usuario, row[1], regex_custom=novo_padrao)
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


# ================= REGRAS =================

def salvar_regra(nome, padrao, ativo=True, campo_destino=None):
    try:
        re.compile(padrao)  # valida antes de salvar
    except re.error as e:
        return False, f"Regex inválida: {e}"
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
    """Cria/atualiza um campo de busca com sua regex. Valida a regex antes."""
    if not campo or not campo.strip() or not padrao or not padrao.strip():
        return False, "Informe campo e padrão (regex)"
    try:
        re.compile(padrao)
    except re.error as e:
        return False, f"Regex inválida: {e}"
    campo_n = campo.strip().lower()
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
        return True, "Campo de busca salvo (aplicado imediatamente)"
    finally:
        conn.close()


def excluir_campo_busca(cid):
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM tb_campos_busca WHERE id=?", (cid,))
        conn.commit()
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
    """Lista por caixa as subpastas e seus documentos PDF."""
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
        try:
            with open(os.path.join(PASTA_ORGANIZADOR, caixa, "capa.txt"), "w", encoding="utf-8") as f:
                f.write(f"CAPA DA CAIXA {caixa}\n" + "\n".join(capa_caixa) + "\n")
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
PASTA_MERGE = os.path.join(BASE_DIR, "datahora_mergePDF")
PASTA_CORTE = os.path.join(BASE_DIR, "datahora_cortePDF")
PASTA_REDUCAO = os.path.join(BASE_DIR, "datahora_reducaoPDF")
PASTA_TEMP_FERR = os.path.join(BASE_DIR, "tmp_ferramentas_pdf")


def _ferramenta_nome(base, sufixo):
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
        from mod_edit_pdf.manipulador_bd import op_cortar
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
        from mod_edit_pdf.manipulador_bd import op_juntar
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
        from mod_edit_pdf.manipulador_bd import op_reduzir
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
    """Caminho absoluto normalizado (sem '..', resolve '~' e '.')."""
    try:
        return os.path.realpath(os.path.abspath(os.path.expanduser(path or "")))
    except Exception:
        return os.path.abspath(path or "")


def raizes_navegacao():
    """Raízes protegidas de navegação: pastas monitoradas + organizador."""
    raizes = [os.path.realpath(os.path.abspath(p)) for p in pastas_monitoradas()]
    if os.path.isdir(PASTA_ORGANIZADOR):
        raizes.append(os.path.realpath(os.path.abspath(PASTA_ORGANIZADOR)))
    return raizes


def pasta_navegavel(pasta):
    """True se `pasta` está dentro de uma das raízes protegidas (anti-travessia)."""
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
    return os.path.splitext(os.path.basename(path))[0]


def renomear_manual(usuario, caminho_arquivo, novo_numero=None, novoTemplate=None,
                    novo_parcela=None, tipo_especial=None):
    """Renomeia manualmente um PDF na pasta monitorada.

    - novo_numero define o nº (se dor tipo especial, usa EC_xxxx etc.)
    - caso contrário, usa novoTemplate (padrão doc_{contador}...).
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
    pasta_zip = pasta_zip or os.path.join(BASE_DIR, "downloads")
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
