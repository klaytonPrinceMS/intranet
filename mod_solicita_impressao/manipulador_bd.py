"""Módulo Solicitação de Impressão — manipulador de banco de dados.

BD próprio: db_mod_solicita_impressao.db (SQLite WAL).
Todas as tabelas do módulo vivem aqui; nada é misturado com outros módulos.
Arquivos PDF enviados ficam em mod_solicita_impressao/solicitacaoImpressao/.

Regras de cota (mensal, hierárquica):
  - Secretaria tem cota máxima (total do mês).
  - Setor pode ter cota própria; se não tiver, usa o pool da secretaria.
  - Ao exceder: envio É permitido, mas a solicitação fica marcada como excedente
    e a critério do autorizador/admin imprimir ou não.
  - Consumo descontado SOMENTE na impressão efetiva (admin confirma).
"""
import sys
import os
import sqlite3
import datetime
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD_DIR = os.path.join(BASE_DIR, "mod_solicita_impressao")
PASTA_SOLICITACOES = os.path.join(MOD_DIR, "solicitacaoImpressao")
DB_PATH = os.path.join(BASE_DIR, "db_mod_solicita_impressao.db")

# Configurações padrão do módulo (seed em tb_configuracoes_modulo)
CONFIG_PADRAO = {
    "pasta_arquivos": "solicitacaoImpressao",
    "max_arquivo_mb": "10",
    "aviso_presenca_obrigatoria": (
        "Documentos só serão impressos com a presença de alguém no local "
        "para retirar as impressões."
    ),
    "impressora_padrao_nome": "",
    "impressora_padrao_a3_nome": "",
    "marca_dagua_ativa": "1",
    "marca_dagua_texto": (
        "IMPRESSO EM {data} POR {usuario} - SOLIC. #{id} - {secretaria}/{setor}"
    ),
    "marca_dagua_posicao": "centro",
    "marca_dagua_opacidade": "30",
    "marca_dagua_fonte_tamanho": "24",
    "marca_dagua_cor": "#CCCCCC",
    "marca_dagua_rotacao": "45",
    # Tempo de vida do rascunho (upload feito, ainda não confirmado) em minutos.
    # Passado esse prazo o arquivo é removido do servidor automaticamente.
    "tempo_expira_rascunho_min": "4",
    # Tempo para exclusão do arquivo após a impressão ser confirmada (minutos).
    "tempo_exclui_impresso_min": "10",
    # Valores padrão pré-selecionados no formulário de nova solicitação.
    "padrao_papel": "A4",
    "padrao_cor": "PB",
    "padrao_frente_verso": "0",   # 0 = somente frente, 1 = frente e verso
    "padrao_sulfite": "1",        # 1 = papel sulfite (trazer outro tipo se 0)
}

STATUS_VALIDOS = (
    "pendente", "aguardando_autorizacao", "autorizado",
    "excedente_cota", "impresso", "recusado", "cancelado",
)


# ================= CONEXÃO =================

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ================= AUDITORIA =================

def _audit(usuario, acao, descricao, hash_arquivo=None):
    """Registra na auditoria (db_mod_auditoria.db, tabela por módulo — LGPD)."""
    try:
        from mod_intranet.manipulador_bd import audit_log
        audit_log(usuario or "sistema", "solicita_impressao", acao, descricao, hash_arquivo)
    except Exception:
        pass


def _log():
    """Logger central (loguru) para observabilidade de execução."""
    from mod_intranet import observabilidade
    return observabilidade.get_logger("solicita_impressao")


# ================= INIT DB =================

def init_db():
    """Cria tabelas e seeds idempotentes. NUNCA apaga dados."""
    os.makedirs(PASTA_SOLICITACOES, exist_ok=True)

    conn = get_connection()
    cur = conn.cursor()

    # ----- Solicitações -----
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_solicitacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_solicitante TEXT NOT NULL,
            arquivo_original TEXT,
            arquivo_servidor TEXT,
            caminho_arquivo TEXT,
            hash_arquivo TEXT,
            qtd_copias INTEGER NOT NULL DEFAULT 1,
            tamanho_papel TEXT NOT NULL DEFAULT 'A4',
            cor TEXT NOT NULL DEFAULT 'PB',
            frente_verso INTEGER NOT NULL DEFAULT 0,
            tipo_borda TEXT,
            papel_sulfite INTEGER NOT NULL DEFAULT 1,
            observacoes TEXT,
            secretaria_id INTEGER,
            setor_id INTEGER,
            qtd_paginas_arquivo INTEGER NOT NULL DEFAULT 0,
            paginas_contabilizadas INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'pendente',
            cota_excedida INTEGER NOT NULL DEFAULT 0,
            requer_autorizacao INTEGER NOT NULL DEFAULT 0,
            autorizado_por TEXT,
            data_autorizacao DATETIME,
            motivo_recusa TEXT,
            impresso_por TEXT,
            data_impressao DATETIME,
            data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP,
            data_atualizacao DATETIME,
            FOREIGN KEY (secretaria_id) REFERENCES tb_secretarias(id) ON DELETE SET NULL,
            FOREIGN KEY (setor_id) REFERENCES tb_setores(id) ON DELETE SET NULL
        )
    """)

    # ----- Secretarias -----
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_secretarias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            sigla TEXT,
            cota_paginas_mensal INTEGER NOT NULL DEFAULT 0,
            ativo INTEGER NOT NULL DEFAULT 1
        )
    """)

    # ----- Setores -----
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_setores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            secretaria_id INTEGER NOT NULL,
            cota_paginas_mensal INTEGER NOT NULL DEFAULT 0,
            ativo INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (secretaria_id) REFERENCES tb_secretarias(id) ON DELETE CASCADE
        )
    """)

    # ----- Responsáveis por autorização -----
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_responsaveis_autorizacao (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_nome TEXT NOT NULL,
            secretaria_id INTEGER NOT NULL,
            setor_id INTEGER,
            ativo INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (secretaria_id) REFERENCES tb_secretarias(id) ON DELETE CASCADE,
            FOREIGN KEY (setor_id) REFERENCES tb_setores(id) ON DELETE CASCADE
        )
    """)

    # ----- Cotas (mensal) -----
    # OBS: setor_id usa 0 como sentinela para "sem setor" (SQLite trata NULL como
    # distinto em UNIQUE, o que quebraria o único por (secretaria, setor, mês).
    # Sem FK em setor_id para permitir o valor 0.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_cotas_impressao (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            secretaria_id INTEGER NOT NULL,
            setor_id INTEGER NOT NULL DEFAULT 0,
            cota_paginas INTEGER NOT NULL DEFAULT 0,
            mes_referencia TEXT NOT NULL,
            ativo INTEGER NOT NULL DEFAULT 1,
            criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
            atualizado_em DATETIME,
            UNIQUE(secretaria_id, setor_id, mes_referencia),
            FOREIGN KEY (secretaria_id) REFERENCES tb_secretarias(id) ON DELETE CASCADE
        )
    """)

    # ----- Consumo de cota -----
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_consumo_cota (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            secretaria_id INTEGER NOT NULL,
            setor_id INTEGER NOT NULL DEFAULT 0,
            mes_referencia TEXT NOT NULL,
            paginas_usadas INTEGER NOT NULL DEFAULT 0,
            atualizado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(secretaria_id, setor_id, mes_referencia)
        )
    """)

    # ----- Configurações do módulo -----
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_configuracoes_modulo (
            chave TEXT PRIMARY KEY,
            valor TEXT NOT NULL
        )
    """)

    # ----- Rascunhos de upload (arquivo no servidor, ainda não confirmado) -----
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_rascunhos_upload (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_solicitante TEXT NOT NULL,
            caminho_arquivo TEXT NOT NULL,
            nome_original TEXT,
            nome_servidor TEXT NOT NULL,
            hash_arquivo TEXT,
            qtd_paginas_arquivo INTEGER NOT NULL DEFAULT 0,
            criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
            expira_em DATETIME NOT NULL
        )
    """)

    # Coluna de agendamento de exclusão do arquivo (após impressão)
    try:
        cols = [c[1] for c in cur.execute("PRAGMA table_info(tb_solicitacoes)").fetchall()]
        if "excluir_arquivo_em" not in cols:
            cur.execute("ALTER TABLE tb_solicitacoes ADD COLUMN excluir_arquivo_em DATETIME")
    except Exception:
        pass

    # Seeds de configuração
    for chave, valor in CONFIG_PADRAO.items():
        cur.execute(
            "INSERT OR IGNORE INTO tb_configuracoes_modulo (chave, valor) VALUES (?, ?)",
            (chave, valor),
        )

    # Seed de versão do módulo
    cur.execute("SELECT COUNT(*) FROM tb_configuracoes_modulo WHERE chave='versao_modulo'")
    if not cur.fetchone()[0]:
        cur.execute(
            "INSERT INTO tb_configuracoes_modulo (chave, valor) VALUES ('versao_modulo', '1.0.260829')"
        )

    # Índices
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sol_usuario ON tb_solicitacoes(usuario_solicitante)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sol_status ON tb_solicitacoes(status)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sol_secretaria ON tb_solicitacoes(secretaria_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sol_data ON tb_solicitacoes(data_criacao)")

    conn.commit()
    conn.close()


# ================= CONFIGURAÇÕES =================

def obter_config(chave, default=""):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT valor FROM tb_configuracoes_modulo WHERE chave=?", (chave,))
        row = cur.fetchone()
        return row[0] if row else default
    finally:
        conn.close()


def definir_config(chave, valor):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO tb_configuracoes_modulo (chave, valor) VALUES (?, ?)",
            (chave, str(valor)),
        )
        conn.commit()
    finally:
        conn.close()


# ================= CONTAGEM DE PÁGINAS =================

def contar_paginas_pdf(caminho):
    """Conta páginas do PDF usando PyMuPDF; fallback pdfplumber."""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(caminho)
        n = doc.page_count
        doc.close()
        return n
    except Exception:
        pass
    try:
        import pdfplumber
        with pdfplumber.open(caminho) as pdf:
            return len(pdf.pages) if pdf.pages else 0
    except Exception:
        return 0


def calcular_paginas_contabilizadas(qtd_paginas, qtd_copias, tamanho_papel, frente_verso):
    """Fórmula exata (regra do projeto):
    paginas = qtd_paginas * qtd_copias * fator_papel * fator_frente_verso
      fator_papel: A4=1, A3=2
      fator_frente_verso: não=1, sim=2
    """
    fator_papel = 2 if (tamanho_papel or "A4").upper() == "A3" else 1
    fator_fv = 2 if frente_verso else 1
    try:
        qtd_paginas = int(qtd_paginas)
        qtd_copias = int(qtd_copias)
    except (TypeError, ValueError):
        return 0
    return max(0, qtd_paginas) * max(0, qtd_copias) * fator_papel * fator_fv


# ================= SECRETARIAS =================

def criar_secretaria(nome, sigla="", cota_paginas_mensal=0, ator="sistema"):
    if not (nome or "").strip():
        return False, "Nome da secretaria é obrigatório"
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO tb_secretarias (nome, sigla, cota_paginas_mensal) VALUES (?, ?, ?)",
            (nome.strip(), (sigla or "").strip(), int(cota_paginas_mensal or 0)),
        )
        sid = cur.lastrowid
        conn.commit()
        _audit(ator, "criar_secretaria", f"Secretaria: {nome} (cota={cota_paginas_mensal})")
        return True, f"Secretaria '{nome}' criada (ID #{sid})"
    except sqlite3.IntegrityError:
        return False, "Secretaria já existe"
    finally:
        conn.close()


def listar_secretarias(ativo=None):
    conn = get_connection()
    try:
        cur = conn.cursor()
        sql = "SELECT id, nome, sigla, cota_paginas_mensal, ativo FROM tb_secretarias"
        if ativo is not None:
            sql += " WHERE ativo=?"
            cur.execute(sql, (1 if ativo else 0,))
        else:
            cur.execute(sql)
        return cur.fetchall()
    finally:
        conn.close()


def obter_secretaria(secretaria_id):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, nome, sigla, cota_paginas_mensal, ativo FROM tb_secretarias WHERE id=?",
            (secretaria_id,),
        )
        return cur.fetchone()
    finally:
        conn.close()


def editar_secretaria(secretaria_id, nome=None, sigla=None, cota_paginas_mensal=None,
                       ativo=None, ator="sistema"):
    conn = get_connection()
    try:
        cur = conn.cursor()
        sets, params = [], []
        if nome is not None:
            sets.append("nome=?"); params.append(nome.strip())
        if sigla is not None:
            sets.append("sigla=?"); params.append((sigla or "").strip())
        if cota_paginas_mensal is not None:
            sets.append("cota_paginas_mensal=?"); params.append(int(cota_paginas_mensal or 0))
        if ativo is not None:
            sets.append("ativo=?"); params.append(1 if ativo else 0)
        if not sets:
            return True, "Nada a alterar"
        params.append(secretaria_id)
        cur.execute(f"UPDATE tb_secretarias SET {', '.join(sets)} WHERE id=?", tuple(params))
        conn.commit()
        _audit(ator, "editar_secretaria", f"ID {secretaria_id}")
        return True, "Secretaria atualizada"
    finally:
        conn.close()


def excluir_secretaria(secretaria_id, ator="sistema"):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM tb_secretarias WHERE id=?", (secretaria_id,))
        conn.commit()
        _audit(ator, "excluir_secretaria", f"ID {secretaria_id}")
        return True, "Secretaria excluída"
    finally:
        conn.close()


# ================= SETORES =================

def criar_setor(nome, secretaria_id, cota_paginas_mensal=0, ator="sistema"):
    if not (nome or "").strip():
        return False, "Nome do setor é obrigatório"
    if not secretaria_id:
        return False, "Secretaria é obrigatória"
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO tb_setores (nome, secretaria_id, cota_paginas_mensal) VALUES (?, ?, ?)",
            (nome.strip(), int(secretaria_id), int(cota_paginas_mensal or 0)),
        )
        sid = cur.lastrowid
        conn.commit()
        _audit(ator, "criar_setor", f"Setor: {nome} (secretaria={secretaria_id})")
        return True, f"Setor '{nome}' criado (ID #{sid})"
    except sqlite3.IntegrityError:
        return False, "Setor já existe nesta secretaria"
    finally:
        conn.close()


def listar_setores(secretaria_id=None, ativo=None):
    conn = get_connection()
    try:
        cur = conn.cursor()
        sql = "SELECT id, nome, secretaria_id, cota_paginas_mensal, ativo FROM tb_setores"
        params = []
        where = []
        if secretaria_id is not None:
            where.append("secretaria_id=?")
            params.append(int(secretaria_id))
        if ativo is not None:
            where.append("ativo=?")
            params.append(1 if ativo else 0)
        if where:
            sql += " WHERE " + " AND ".join(where)
        cur.execute(sql, params)
        return cur.fetchall()
    finally:
        conn.close()


def obter_setor(setor_id):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, nome, secretaria_id, cota_paginas_mensal, ativo FROM tb_setores WHERE id=?",
            (setor_id,),
        )
        return cur.fetchone()
    finally:
        conn.close()


def editar_setor(setor_id, nome=None, secretaria_id=None, cota_paginas_mensal=None,
                 ativo=None, ator="sistema"):
    conn = get_connection()
    try:
        cur = conn.cursor()
        sets, params = [], []
        if nome is not None:
            sets.append("nome=?"); params.append(nome.strip())
        if secretaria_id is not None:
            sets.append("secretaria_id=?"); params.append(int(secretaria_id))
        if cota_paginas_mensal is not None:
            sets.append("cota_paginas_mensal=?"); params.append(int(cota_paginas_mensal or 0))
        if ativo is not None:
            sets.append("ativo=?"); params.append(1 if ativo else 0)
        if not sets:
            return True, "Nada a alterar"
        params.append(setor_id)
        cur.execute(f"UPDATE tb_setores SET {', '.join(sets)} WHERE id=?", tuple(params))
        conn.commit()
        _audit(ator, "editar_setor", f"ID {setor_id}")
        return True, "Setor atualizado"
    finally:
        conn.close()


def excluir_setor(setor_id, ator="sistema"):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM tb_setores WHERE id=?", (setor_id,))
        conn.commit()
        _audit(ator, "excluir_setor", f"ID {setor_id}")
        return True, "Setor excluído"
    finally:
        conn.close()


# ================= RESPONSÁVEIS POR AUTORIZAÇÃO =================

def criar_responsavel(user_nome, secretaria_id, setor_id=None, ator="sistema"):
    if not (user_nome or "").strip():
        return False, "Usuário é obrigatório"
    if not secretaria_id:
        return False, "Secretaria é obrigatória"
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO tb_responsaveis_autorizacao (user_nome, secretaria_id, setor_id) "
            "VALUES (?, ?, ?)",
            (user_nome.strip(), int(secretaria_id), setor_id),
        )
        rid = cur.lastrowid
        conn.commit()
        _audit(ator, "criar_responsavel", f"{user_nome} (secr={secretaria_id}, setor={setor_id})")
        return True, f"Responsável '{user_nome}' cadastrado (ID #{rid})"
    except sqlite3.IntegrityError:
        return False, "Responsável já cadastrado para este vínculo"
    finally:
        conn.close()


def listar_responsaveis(secretaria_id=None, setor_id=None, ativo=None):
    conn = get_connection()
    try:
        cur = conn.cursor()
        sql = ("SELECT id, user_nome, secretaria_id, setor_id, ativo "
               "FROM tb_responsaveis_autorizacao")
        params = []
        where = []
        if secretaria_id is not None:
            where.append("secretaria_id=?")
            params.append(int(secretaria_id))
        if setor_id is not None:
            where.append("setor_id=?")
            params.append(setor_id)
        if ativo is not None:
            where.append("ativo=?")
            params.append(1 if ativo else 0)
        if where:
            sql += " WHERE " + " AND ".join(where)
        cur.execute(sql, params)
        return cur.fetchall()
    finally:
        conn.close()


def excluir_responsavel(responsavel_id, ator="sistema"):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM tb_responsaveis_autorizacao WHERE id=?", (responsavel_id,))
        conn.commit()
        _audit(ator, "excluir_responsavel", f"ID {responsavel_id}")
        return True, "Responsável removido"
    finally:
        conn.close()


def eh_responsavel_autorizacao(user_nome, secretaria_id, setor_id=None):
    """Verifica se user_nome é responsável por autorizar para a secretaria/setor."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        if setor_id:
            cur.execute(
                "SELECT 1 FROM tb_responsaveis_autorizacao "
                "WHERE user_nome=? AND secretaria_id=? AND setor_id=? AND ativo=1 LIMIT 1",
                (user_nome, int(secretaria_id), setor_id),
            )
            if cur.fetchone():
                return True
        cur.execute(
            "SELECT 1 FROM tb_responsaveis_autorizacao "
            "WHERE user_nome=? AND secretaria_id=? AND (setor_id IS NULL OR setor_id=?) AND ativo=1 LIMIT 1",
            (user_nome, int(secretaria_id), setor_id),
        )
        return cur.fetchone() is not None
    finally:
        conn.close()


# ================= COTAS (MENSAL) =================

def mes_atual():
    return datetime.date.today().strftime("%Y-%m")


def obter_ou_criar_cota(secretaria_id, setor_id, mes=None):
    """Retorna (cota_paginas, existe). Cria registro se não existir.
    setor_id=None (sem setor) é normalizado para 0 (sentinelas)."""
    setor_id = int(setor_id or 0)
    mes = mes or mes_atual()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT cota_paginas FROM tb_cotas_impressao "
            "WHERE secretaria_id=? AND setor_id=? AND mes_referencia=?",
            (int(secretaria_id), setor_id, mes),
        )
        row = cur.fetchone()
        if row:
            return row[0], True
        # Cria com cota da secretaria/setor (do cadastro)
        sec = obter_secretaria(secretaria_id)
        cota_base = sec[3] if sec else 0
        if setor_id:
            st = obter_setor(setor_id)
            if st and st[3]:
                cota_base = st[3]
        cur.execute(
            "INSERT OR IGNORE INTO tb_cotas_impressao "
            "(secretaria_id, setor_id, cota_paginas, mes_referencia) VALUES (?, ?, ?, ?)",
            (int(secretaria_id), setor_id, int(cota_base or 0), mes),
        )
        conn.commit()
        return int(cota_base or 0), False
    finally:
        conn.close()


def definir_cota(secretaria_id, setor_id, cota_paginas, mes=None, ator="sistema"):
    setor_id = int(setor_id or 0)
    mes = mes or mes_atual()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO tb_cotas_impressao (secretaria_id, setor_id, cota_paginas, mes_referencia, atualizado_em) "
            "VALUES (?, ?, ?, ?, datetime('now')) "
            "ON CONFLICT(secretaria_id, setor_id, mes_referencia) DO UPDATE SET "
            "cota_paginas=excluded.cota_paginas, atualizado_em=datetime('now')",
            (int(secretaria_id), setor_id, int(cota_paginas or 0), mes),
        )
        conn.commit()
        _audit(ator, "definir_cota",
               f"secr={secretaria_id} setor={setor_id} cota={cota_paginas} mes={mes}")
        return True, "Cota definida"
    finally:
        conn.close()


def obter_consumo(secretaria_id, setor_id, mes=None):
    setor_id = int(setor_id or 0)
    mes = mes or mes_atual()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT paginas_usadas FROM tb_consumo_cota "
            "WHERE secretaria_id=? AND setor_id=? AND mes_referencia=?",
            (int(secretaria_id), setor_id, mes),
        )
        row = cur.fetchone()
        return row[0] if row else 0
    finally:
        conn.close()


def _incrementar_consumo(secretaria_id, setor_id, paginas, mes=None):
    setor_id = int(setor_id or 0)
    mes = mes or mes_atual()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO tb_consumo_cota (secretaria_id, setor_id, mes_referencia, paginas_usadas) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(secretaria_id, setor_id, mes_referencia) DO UPDATE SET "
            "paginas_usadas = paginas_usadas + excluded.paginas_usadas, "
            "atualizado_em = datetime('now')",
            (int(secretaria_id), setor_id, mes, int(paginas or 0)),
        )
        conn.commit()
    finally:
        conn.close()


def verificar_excedente(secretaria_id, setor_id, paginas_contabilizadas):
    """Verifica se a impressão excederá alguma cota (secretaria OU setor).
    Retorna (excedente: bool, detalhe: str)."""
    setor_id = int(setor_id or 0)
    # Cota da secretaria
    cota_secr, _ = obter_ou_criar_cota(secretaria_id, 0)
    usado_secr = obter_consumo(secretaria_id, 0)
    if cota_secr > 0 and (usado_secr + paginas_contabilizadas) > cota_secr:
        return True, f"Excede cota da secretaria ({usado_secr + paginas_contabilizadas}/{cota_secr})"
    # Cota do setor (se houver)
    if setor_id:
        cota_setor, _ = obter_ou_criar_cota(secretaria_id, setor_id)
        usado_setor = obter_consumo(secretaria_id, setor_id)
        if cota_setor > 0 and (usado_setor + paginas_contabilizadas) > cota_setor:
            return True, f"Excede cota do setor ({usado_setor + paginas_contabilizadas}/{cota_setor})"
    return False, ""


def resetar_consumo(secretaria_id, setor_id, mes=None, ator="sistema"):
    """Zera o consumo do mês (manual)."""
    setor_id = int(setor_id or 0)
    mes = mes or mes_atual()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE tb_consumo_cota SET paginas_usadas=0, atualizado_em=datetime('now') "
            "WHERE secretaria_id=? AND setor_id=? AND mes_referencia=?",
            (int(secretaria_id), setor_id, mes),
        )
        conn.commit()
        _audit(ator, "resetar_consumo",
               f"secr={secretaria_id} setor={setor_id} mes={mes}")
        return True, "Consumo do mês resetado"
    finally:
        conn.close()


def percentual_consumo(secretaria_id, setor_id, mes=None):
    """Retorna (percentual 0-100+, usado, cota)."""
    setor_id = int(setor_id or 0)
    mes = mes or mes_atual()
    cota, _ = obter_ou_criar_cota(secretaria_id, setor_id)
    usado = obter_consumo(secretaria_id, setor_id)
    if cota <= 0:
        return 0, usado, cota
    return round((usado / cota) * 100, 1), usado, cota


# ================= SOLICITAÇÕES =================

def _sanitizar_nome(s):
    import unicodedata
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode("ascii")
    s = "".join(c if c.isalnum() else "_" for c in s)
    return s.strip("_") or "x"


def gerar_nome_arquivo(data_hora, usuario, qtd_copias, qtd_paginas, secretaria_id, setor_id):
    sec = obter_secretaria(secretaria_id)
    sec_nome = _sanitizar_nome(sec[2] or sec[1]) if sec else "secretaria"
    set_nome = "sem_setor"
    if setor_id:
        st = obter_setor(setor_id)
        if st:
            set_nome = _sanitizar_nome(st[1])
    usuario_san = _sanitizar_nome(usuario)
    return (f"{data_hora}_{usuario_san}_{qtd_copias}_{qtd_paginas}_{sec_nome}_{set_nome}.pdf")


def criar_solicitacao(usuario, caminho_tmp, arquivo_original, qtd_copias, tamanho_papel,
                      cor, frente_verso, tipo_borda, papel_sulfite, observacoes,
                      secretaria_id, setor_id, ator="sistema"):
    """Cria solicitação: salva PDF na pasta do módulo, conta páginas, calcula
    contabilização e marca excedente se necessário."""
    if not caminho_tmp or not os.path.exists(caminho_tmp):
        return False, "Arquivo PDF não encontrado"
    if not secretaria_id:
        return False, "Secretaria é obrigatória"

    qtd_paginas = contar_paginas_pdf(caminho_tmp)
    if qtd_paginas <= 0:
        return False, "Não foi possível contar as páginas do PDF (arquivo inválido?)"

    paginas_calc = calcular_paginas_contabilizadas(
        qtd_paginas, qtd_copias, tamanho_papel, frente_verso)

    # Nome e destino
    agora = datetime.datetime.now()
    data_hora = agora.strftime("%Y%m%d_%H%M%S")
    nome_servidor = gerar_nome_arquivo(
        data_hora, usuario, qtd_copias, qtd_paginas, secretaria_id, setor_id)
    os.makedirs(PASTA_SOLICITACOES, exist_ok=True)
    destino = os.path.join(PASTA_SOLICITACOES, nome_servidor)
    import shutil
    shutil.copy2(caminho_tmp, destino)

    hash_arq = None
    try:
        from mod_intranet.manipulador_bd import hash_arquivo
        hash_arq = hash_arquivo(destino)
    except Exception:
        pass

    # Excedente de cota
    excedente, detalhe = verificar_excedente(secretaria_id, setor_id, paginas_calc)
    cota_excedida = 1 if excedente else 0

    # Requer autorização? (se há responsável cadastrado para secretaria/setor)
    requer_auth = 1 if tem_responsavel_para(secretaria_id, setor_id) else 0

    if excedente:
        status = "excedente_cota"
    elif requer_auth:
        status = "aguardando_autorizacao"
    else:
        status = "autorizado"

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO tb_solicitacoes
               (usuario_solicitante, arquivo_original, arquivo_servidor, caminho_arquivo,
                hash_arquivo, qtd_copias, tamanho_papel, cor, frente_verso, tipo_borda,
                papel_sulfite, observacoes, secretaria_id, setor_id, qtd_paginas_arquivo,
                paginas_contabilizadas, status, cota_excedida, requer_autorizacao,
                data_atualizacao)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
            (usuario, arquivo_original, nome_servidor, destino, hash_arq,
             int(qtd_copias), tamanho_papel, cor, 1 if frente_verso else 0, tipo_borda,
             1 if papel_sulfite else 0, observacoes, int(secretaria_id), setor_id,
             qtd_paginas, paginas_calc, status, cota_excedida, requer_auth),
        )
        sid = cur.lastrowid
        conn.commit()
        _audit(ator, "criar_solicitacao",
               f"#{sid} {nome_servidor} | paginas_calc={paginas_calc} | {status}"
               + (" | EXCEDENTE" if excedente else ""),
               hash_arq)
        msg = f"Solicitação #{sid} criada"
        if excedente:
            msg += " — ATENÇÃO: excedente de cota (sujeita à autorização)"
        elif requer_auth:
            msg += " — aguardando autorização"
        else:
            msg += " — autorizada, pronta para impressão"
        return True, msg
    except Exception as e:
        return False, f"Erro ao criar solicitação: {e}"
    finally:
        conn.close()


def tem_responsavel_para(secretaria_id, setor_id):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM tb_responsaveis_autorizacao "
            "WHERE secretaria_id=? AND ativo=1 "
            "AND (setor_id IS NULL OR setor_id=?) LIMIT 1",
            (int(secretaria_id), setor_id),
        )
        return cur.fetchone() is not None
    finally:
        conn.close()


def listar_solicitacoes(usuario=None, status=None, secretaria_id=None, setor_id=None,
                        apenas_excedentes=False, limite=200):
    conn = get_connection()
    try:
        cur = conn.cursor()
        sql = ("SELECT s.id, s.usuario_solicitante, s.arquivo_servidor, s.arquivo_original, "
               "s.qtd_copias, s.tamanho_papel, s.cor, s.frente_verso, s.tipo_borda, "
               "s.papel_sulfite, s.observacoes, s.secretaria_id, s.setor_id, "
               "s.qtd_paginas_arquivo, s.paginas_contabilizadas, s.status, s.cota_excedida, "
               "s.requer_autorizacao, s.autorizado_por, s.data_autorizacao, s.motivo_recusa, "
               "s.impresso_por, s.data_impressao, s.data_criacao, "
               "sec.nome, sec.sigla, st.nome "
               "FROM tb_solicitacoes s "
               "LEFT JOIN tb_secretarias sec ON sec.id = s.secretaria_id "
               "LEFT JOIN tb_setores st ON st.id = s.setor_id "
               "WHERE 1=1")
        params = []
        if usuario:
            sql += " AND s.usuario_solicitante=?"
            params.append(usuario)
        if status:
            sql += " AND s.status=?"
            params.append(status)
        if secretaria_id is not None:
            sql += " AND s.secretaria_id=?"
            params.append(int(secretaria_id))
        if setor_id is not None:
            sql += " AND s.setor_id=?"
            params.append(setor_id)
        if apenas_excedentes:
            sql += " AND s.cota_excedida=1"
        sql += " ORDER BY s.data_criacao DESC LIMIT ?"
        params.append(int(limite))
        cur.execute(sql, params)
        return cur.fetchall()
    finally:
        conn.close()


def obter_solicitacao(solicitacao_id):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM tb_solicitacoes WHERE id=?", (solicitacao_id,))
        cols = [d[0] for d in cur.description]
        row = cur.fetchone()
        return dict(zip(cols, row)) if row else None
    finally:
        conn.close()


def _eh_admin_do_modulo(user):
    """Admin geral do sistema OU administrador do módulo de impressão."""
    try:
        from mod_intranet import autenticacao
        return (autenticacao.perfil_global_de(user) == "administrador_geral"
                or autenticacao.eh_admin_do_modulo(user, "solicita_impressao"))
    except Exception:
        return False


def _pode_autorizar(user, secretaria_id, setor_id):
    """Só autoriza quem é responsável pelo vínculo OU administrador do módulo."""
    if _eh_admin_do_modulo(user):
        return True
    if not secretaria_id:
        return False
    return eh_responsavel_autorizacao(user, int(secretaria_id), setor_id)


def autorizar_solicitacao(solicitacao_id, autor, motivo=None):
    sol = obter_solicitacao(solicitacao_id)
    if not sol:
        return False, "Solicitação não encontrada"
    if sol["status"] not in ("aguardando_autorizacao", "excedente_cota"):
        return False, "Não autorizável neste estado"
    if not _pode_autorizar(autor, sol.get("secretaria_id"), sol.get("setor_id")):
        return False, "Usuário sem permissão de autorização para este vínculo"
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE tb_solicitacoes SET status='autorizado', autorizado_por=?, "
            "data_autorizacao=datetime('now'), data_atualizacao=datetime('now') "
            "WHERE id=? AND status IN ('aguardando_autorizacao', 'excedente_cota')",
            (autor, solicitacao_id),
        )
        ok = cur.rowcount > 0
        conn.commit()
        if ok:
            _audit(autor, "autorizar_solicitacao", f"#{solicitacao_id}", None)
        return ok, "Solicitação autorizada" if ok else "Não autorizável neste estado"
    finally:
        conn.close()


def recusar_solicitacao(solicitacao_id, autor, motivo):
    if not (motivo or "").strip():
        return False, "Motivo da recusa é obrigatório"
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE tb_solicitacoes SET status='recusado', motivo_recusa=?, "
            "data_atualizacao=datetime('now') WHERE id=? "
            "AND status IN ('aguardando_autorizacao', 'excedente_cota', 'autorizado')",
            (motivo.strip(), solicitacao_id),
        )
        ok = cur.rowcount > 0
        conn.commit()
        if ok:
            _remover_arquivo_solicitacao(solicitacao_id)
            _audit(autor, "recusar_solicitacao", f"#{solicitacao_id} motivo={motivo}", None)
        return ok, "Solicitação recusada" if ok else "Não recusável"
    finally:
        conn.close()


def imprimir_solicitacao(solicitacao_id, admin_user, ator="sistema"):
    """Marca como impresso e desconta cota (secretaria + setor se houver)."""
    sol = obter_solicitacao(solicitacao_id)
    if not sol:
        return False, "Solicitação não encontrada"
    if sol["status"] != "autorizado":
        return False, f"Status '{sol['status']}' não permite impressão (é necessário autorizar antes)"
    if not sol.get("autorizado_por"):
        return False, "Solicitação ainda não foi autorizada — liberada só após autorização"
    secr = sol["secretaria_id"]
    setor = sol["setor_id"]
    paginas = sol["paginas_contabilizadas"]
    # Desconta da secretaria (sempre)
    _incrementar_consumo(secr, 0, paginas)
    # Desconta do setor apenas se houver setor próprio (evita duplo desconto
    # na mesma linha secretaria/0 quando setor é None)
    if setor:
        _incrementar_consumo(secr, setor, paginas)
    conn = get_connection()
    try:
        cur = conn.cursor()
        minutos = tempo_exclui_impresso_min()
        exclui_em = (datetime.datetime.now() + datetime.timedelta(minutes=minutos)).strftime(
            "%Y-%m-%d %H:%M:%S")
        cur.execute(
            "UPDATE tb_solicitacoes SET status='impresso', impresso_por=?, "
            "data_impressao=datetime('now'), excluir_arquivo_em=?, "
            "data_atualizacao=datetime('now') WHERE id=?",
            (admin_user, exclui_em, solicitacao_id),
        )
        conn.commit()
        _audit(ator, "imprimir_solicitacao",
               f"#{solicitacao_id} paginas={paginas} arquivo_exclui_em={exclui_em}", None)
        _log().info(f"impressao #{solicitacao_id} por {admin_user} | paginas={paginas} "
                    f"arquivo_exclui_em={exclui_em}")
        return True, f"Solicitação #{solicitacao_id} marcada como impressa"
    finally:
        conn.close()


def recuar_solicitacao(solicitacao_id, ator="sistema"):
    """Cancela solicitação já autorizada/impressa (status=cancelado)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE tb_solicitacoes SET status='cancelado', data_atualizacao=datetime('now') "
            "WHERE id=? AND status IN ('autorizado', 'excedente_cota', 'impresso')",
            (solicitacao_id,),
        )
        ok = cur.rowcount > 0
        conn.commit()
        if ok:
            _remover_arquivo_solicitacao(solicitacao_id)
            _audit(ator, "recuar_solicitacao", f"#{solicitacao_id}", None)
        return ok, "Solicitação cancelada" if ok else "Não cancelável"
    finally:
        conn.close()


def cancelar_solicitacao(solicitacao_id, usuario, ator="sistema"):
    """Usuário cancela própria solicitação se ainda pendente/aguardando/excedente."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE tb_solicitacoes SET status='cancelado', data_atualizacao=datetime('now') "
            "WHERE id=? AND usuario_solicitante=? AND status IN "
            "('pendente', 'aguardando_autorizacao', 'excedente_cota')",
            (solicitacao_id, usuario),
        )
        ok = cur.rowcount > 0
        conn.commit()
        if ok:
            _remover_arquivo_solicitacao(solicitacao_id)
            _audit(ator, "cancelar_solicitacao", f"#{solicitacao_id}", None)
        return ok, "Solicitação cancelada" if ok else "Não cancelável pelo usuário"
    finally:
        conn.close()


def tempo_expira_rascunho_min():
    try:
        return max(1, int(obter_config("tempo_expira_rascunho_min", "4")))
    except (TypeError, ValueError):
        return 4


def tempo_exclui_impresso_min():
    try:
        return max(1, int(obter_config("tempo_exclui_impresso_min", "10")))
    except (TypeError, ValueError):
        return 10


def _remover_arquivo_se_existir(caminho):
    try:
        if caminho and os.path.exists(caminho):
            os.remove(caminho)
            return True
    except OSError:
        pass
    return False


def _remover_arquivo_solicitacao(solicitacao_id):
    """Remove o arquivo físico de uma solicitação (ao recusar/recuar/cancelar)."""
    try:
        sol = obter_solicitacao(solicitacao_id)
        if sol and sol.get("caminho_arquivo"):
            _remover_arquivo_se_existir(sol["caminho_arquivo"])
    except Exception:
        pass


def registrar_rascunho(usuario, conteudo_bytes, nome_original):
    """Recebe o PDF (bytes) do upload, salva NO SERVIDOR já com nome do sistema
    (sem usar o nome original), conta páginas e registra rascunho com expiração.
    Retorna (rascunho_id, nome_servidor, qtd_paginas, caminho)."""
    os.makedirs(PASTA_SOLICITACOES, exist_ok=True)
    agora = datetime.datetime.now()
    data_hora = agora.strftime("%Y%m%d_%H%M%S")
    usuario_san = _sanitizar_nome(usuario)
    # Nome único por rascunho (evita colisão no mesmo segundo ao anexar vários PDFs)
    destino = os.path.join(PASTA_SOLICITACOES,
                           f"{data_hora}_{usuario_san}_{uuid.uuid4().hex[:8]}_rascunho.pdf")
    with open(destino, "wb") as f:
        f.write(conteudo_bytes)
    qtd_paginas = contar_paginas_pdf(destino)
    if qtd_paginas <= 0:
        _remover_arquivo_se_existir(destino)
        _log().warning(f"rascunho de {usuario}: PDF inválido/sem páginas (nome original="
                        f"{nome_original})")
        return None, "", 0, None
    hash_arq = None
    try:
        from mod_intranet.manipulador_bd import hash_arquivo
        hash_arq = hash_arquivo(destino)
    except Exception:
        pass
    minutos = tempo_expira_rascunho_min()
    expira_dt = (agora + datetime.timedelta(minutes=minutos)).strftime("%Y-%m-%d %H:%M:%S")
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO tb_rascunhos_upload "
            "(usuario_solicitante, caminho_arquivo, nome_original, nome_servidor, "
            "hash_arquivo, qtd_paginas_arquivo, criado_em, expira_em) "
            "VALUES (?, ?, ?, ?, ?, ?, datetime('now'), ?)",
            (usuario, destino, nome_original or "", os.path.basename(destino),
             hash_arq, qtd_paginas, expira_dt))
        rid = cur.lastrowid
        conn.commit()
        _audit(usuario, "rascunho_upload",
               f"#{rid} {os.path.basename(destino)} paginas={qtd_paginas} expira_em={expira_dt}",
               hash_arq)
        return rid, os.path.basename(destino), qtd_paginas, destino
    finally:
        conn.close()


def obter_rascunho(rascunho_id):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM tb_rascunhos_upload WHERE id=?", (rascunho_id,))
        cols = [d[0] for d in cur.description]
        row = cur.fetchone()
        return dict(zip(cols, row)) if row else None
    finally:
        conn.close()


def cancelar_rascunho(rascunho_id, ator="sistema"):
    """Remove o rascunho e o arquivo do servidor (usuário desistiu antes de confirmar)."""
    r = obter_rascunho(rascunho_id)
    if not r:
        return False, "Rascunho não encontrado"
    _remover_arquivo_se_existir(r["caminho_arquivo"])
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM tb_rascunhos_upload WHERE id=?", (rascunho_id,))
        conn.commit()
        _audit(ator, "rascunho_cancelado", f"#{rascunho_id} {r['nome_servidor']}", None)
        return True, "Rascunho removido"
    finally:
        conn.close()


def confirmar_rascunho(rascunho_id, qtd_copias, tamanho_papel, cor, frente_verso,
                       tipo_borda, papel_sulfite, observacoes, secretaria_id, setor_id,
                       ator="sistema"):
    """Converte um rascunho em solicitação: renomeia o arquivo para o padrão final,
    cria o registro em tb_solicitacoes e remove o rascunho."""
    r = obter_rascunho(rascunho_id)
    if not r:
        return False, "Rascunho não encontrado (expirado?)", None
    if not os.path.exists(r["caminho_arquivo"]):
        conn = get_connection()
        try:
            conn.execute("DELETE FROM tb_rascunhos_upload WHERE id=?", (rascunho_id,))
            conn.commit()
        finally:
            conn.close()
        return False, "Arquivo do rascunho sumiu do servidor", None
    if not secretaria_id:
        return False, "Secretaria é obrigatória", None

    usuario = r["usuario_solicitante"]
    qtd_paginas = r["qtd_paginas_arquivo"] or contar_paginas_pdf(r["caminho_arquivo"])
    paginas_calc = calcular_paginas_contabilizadas(
        qtd_paginas, qtd_copias, tamanho_papel, frente_verso)

    # Nome final (padrão do projeto) — dataHora da confirmação
    agora = datetime.datetime.now()
    data_hora = agora.strftime("%Y%m%d_%H%M%S")
    nome_servidor = gerar_nome_arquivo(
        data_hora, usuario, qtd_copias, qtd_paginas, secretaria_id, setor_id)
    os.makedirs(PASTA_SOLICITACOES, exist_ok=True)
    destino = os.path.join(PASTA_SOLICITACOES, nome_servidor)
    import shutil
    shutil.move(r["caminho_arquivo"], destino)

    hash_arq = r["hash_arquivo"]
    excedente, detalhe = verificar_excedente(secretaria_id, setor_id, paginas_calc)
    cota_excedida = 1 if excedente else 0
    requer_auth = 1 if tem_responsavel_para(secretaria_id, setor_id) else 0
    if excedente:
        status = "excedente_cota"
    elif requer_auth:
        status = "aguardando_autorizacao"
    else:
        status = "autorizado"

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO tb_solicitacoes
               (usuario_solicitante, arquivo_original, arquivo_servidor, caminho_arquivo,
                hash_arquivo, qtd_copias, tamanho_papel, cor, frente_verso, tipo_borda,
                papel_sulfite, observacoes, secretaria_id, setor_id, qtd_paginas_arquivo,
                paginas_contabilizadas, status, cota_excedida, requer_autorizacao,
                data_atualizacao)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
            (usuario, r["nome_original"], nome_servidor, destino, hash_arq,
             int(qtd_copias), tamanho_papel, cor, 1 if frente_verso else 0, tipo_borda,
             1 if papel_sulfite else 0, observacoes, int(secretaria_id), setor_id,
             qtd_paginas, paginas_calc, status, cota_excedida, requer_auth),
        )
        sid = cur.lastrowid
        cur.execute("DELETE FROM tb_rascunhos_upload WHERE id=?", (rascunho_id,))
        conn.commit()
        _audit(ator, "criar_solicitacao",
               f"#{sid} {nome_servidor} | copias={qtd_copias} paginas_arq={qtd_paginas} "
               f"paginas_calc={paginas_calc} secr={secretaria_id} setor={setor_id} | {status}"
               + (" | EXCEDENTE" if excedente else ""),
               hash_arq)
        _log().info(f"solicitacao criada #{sid} por {usuario} | copias={qtd_copias} "
                    f"paginas_calc={paginas_calc} secr={secretaria_id} setor={setor_id} "
                    f"status={status}")
        msg = f"Solicitação #{sid} criada"
        if excedente:
            msg += " — ATENÇÃO: excedente de cota (sujeita à autorização)"
        elif requer_auth:
            msg += " — aguardando autorização"
        else:
            msg += " — autorizada, pronta para impressão"
        return True, msg, sid
    except Exception as e:
        return False, f"Erro ao criar solicitação: {e}", None
    finally:
        conn.close()


def expirar_rascunhos_e_impressos():
    """Limpeza agendada (a cada 1 min):
    - rascunhos cujo expira_em passou -> remove arquivo + registro;
    - solicitações impressas cujo excluir_arquivo_em passou -> remove arquivo do servidor."""
    agora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    removidos = 0
    # Rascunhos expirados
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, caminho_arquivo, nome_servidor FROM tb_rascunhos_upload "
                    "WHERE expira_em < ?", (agora,))
        for rid, caminho, nome in cur.fetchall():
            _remover_arquivo_se_existir(caminho)
            cur.execute("DELETE FROM tb_rascunhos_upload WHERE id=?", (rid,))
            removidos += 1
            _audit("sistema", "rascunho_expirado",
                   f"#{rid} {nome} removido automaticamente (não confirmado)", None)
        # Arquivos de solicitações impressas vencidos
        cur.execute("SELECT id, caminho_arquivo FROM tb_solicitacoes "
                    "WHERE status='impresso' AND excluir_arquivo_em IS NOT NULL "
                    "AND excluir_arquivo_em < ?", (agora,))
        for sid, caminho in cur.fetchall():
            if _remover_arquivo_se_existir(caminho):
                removidos += 1
            cur.execute("UPDATE tb_solicitacoes SET excluir_arquivo_em=NULL "
                        "WHERE id=?", (sid,))
            _audit("sistema", "arquivo_impresso_excluido",
                   f"#{sid} arquivo removido após prazo de retenção", None)
        conn.commit()
    finally:
        conn.close()
    if removidos:
        _log().info(f"limpeza de rascunhos/impressos: {removidos} arquivo(s) removido(s)")
    return removidos


def solicitar_solicitacoes_responsavel(user_nome, limite=200):
    """Retorna solicitações pendentes das secretarias/setores onde o user é responsável.

    Escopo: um responsável vinculado à secretaria inteira (setor_id IS NULL) vê
    todas as solicitações da secretaria; um responsável vinculado a um setor vê
    apenas as daquele setor (não sobre-expoe outros setores)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT DISTINCT secretaria_id, setor_id FROM tb_responsaveis_autorizacao "
            "WHERE user_nome = ? AND ativo = 1",
            (user_nome,),
        )
        vinculos = cur.fetchall()
        if not vinculos:
            return []
        vistos = set()
        resultados = []
        for secr, setor in vinculos:
            for row in listar_solicitacoes(
                    secretaria_id=secr, setor_id=setor,
                    status="aguardando_autorizacao", limite=limite):
                if row[0] not in vistos:
                    resultados.append(row)
                    vistos.add(row[0])
            for row in listar_solicitacoes(
                    secretaria_id=secr, setor_id=setor,
                    status="excedente_cota", limite=limite):
                if row[0] not in vistos:
                    resultados.append(row)
                    vistos.add(row[0])
        return resultados
    finally:
        conn.close()


# ================= RELATÓRIO DE COTAS =================

def relatorio_cotas(mes=None):
    """Retorna lista de (secretaria_id, secretaria_nome, setor_id, setor_nome,
    cota, usado, percentual) para todas as secretarias/setores ativas."""
    mes = mes or mes_atual()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, nome, sigla, cota_paginas_mensal FROM tb_secretarias WHERE ativo=1"
        )
        secrs = cur.fetchall()
        rel = []
        for sid, nome, sigla, cota_secr in secrs:
            cota, _ = obter_ou_criar_cota(sid, 0, mes)
            usado = obter_consumo(sid, 0, mes)
            pct = round((usado / cota) * 100, 1) if cota > 0 else 0
            rel.append((sid, nome, None, "—", cota, usado, pct))
            # Setores
            cur.execute(
                "SELECT id, nome, cota_paginas_mensal FROM tb_setores "
                "WHERE secretaria_id=? AND ativo=1", (sid,))
            for stid, stnome, cota_st in cur.fetchall():
                c, _ = obter_ou_criar_cota(sid, stid, mes)
                u = obter_consumo(sid, stid, mes)
                p = round((u / c) * 100, 1) if c > 0 else 0
                rel.append((sid, nome, stid, stnome, c, u, p))
        return rel
    finally:
        conn.close()


# ================= MARCAS D'ÁGUA (PDF) =================

def aplicar_marca_dagua(caminho_pdf, solicitacao_id, usuario, secretaria_nome,
                        setor_nome, solicitante):
    """Gera um novo PDF (cópia) com marca d'água se ativa. Retorna caminho do PDF final."""
    if obter_config("marca_dagua_ativa", "1") != "1":
        return caminho_pdf  # sem marca d'água
    try:
        import pymupdf as fitz
        ativa = obter_config("marca_dagua_ativa", "1") == "1"
        if not ativa:
            return caminho_pdf
        texto = obter_config("marca_dagua_texto",
                             "IMPRESSO EM {data} POR {usuario} - SOLIC. #{id} - {secretaria}/{setor}")
        pos = obter_config("marca_dagua_posicao", "centro")
        opac = int(obter_config("marca_dagua_opacidade", "30")) / 100.0
        fs = int(obter_config("marca_dagua_fonte_tamanho", "24"))
        cor = obter_config("marca_dagua_cor", "#CCCCCC")
        rot = int(obter_config("marca_dagua_rotacao", "45"))
        if rot not in (0, 90, 180, 270):
            rot = 0  # PyMuPDF só aceita múltiplos de 90°
        agora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
        texto = (texto.replace("{data}", agora).replace("{usuario}", usuario or "")
                 .replace("{id}", str(solicitacao_id)).replace("{secretaria}", secretaria_nome or "")
                 .replace("{setor}", setor_nome or "—").replace("{solicitante}", solicitante or "")
                 .replace("{copias}", "").replace("{paginas}", ""))

        doc = fitz.open(caminho_pdf)
        try:
            rgb = fitz.utils.hex_to_rgb(cor)
        except Exception:
            rgb = (0.8, 0.8, 0.8)
        for page in doc:
            w, h = page.rect.width, page.rect.height
            if pos == "centro":
                x, y = w / 2, h / 2
            elif pos == "rodape":
                x, y = w / 2, h - 40
            elif pos == "canto_superior":
                x, y = 60, 40
            else:  # canto_inferior
                x, y = 60, h - 40
            page.insert_text(
                (x, y), texto,
                fontsize=fs, color=rgb, fill_opacity=opac,
                rotate=rot,
            )
        saida = caminho_pdf.replace(".pdf", f"_wm_{solicitacao_id}.pdf")
        doc.save(saida)
        doc.close()
        return saida
    except Exception as e:
        print(f"Marca d'água falhou: {e}")
        return caminho_pdf


# Inicialização ao importar
init_db()
