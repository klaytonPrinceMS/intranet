"""Conexão e configurações centrais do Intranet (banco central db_mod_intranet.db).

Camada mais baixa: sem imports circulares — só os outros módulos dependem daqui.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "db_mod_intranet.db")

PADRAO_CONFIG = {
    "titulo_sistema": "INTRANET",
    "icone_sistema": "hub",
    "cor_principal": "#1565C0",
    "cor_fundo": "#EEEEEE",
    "texto_login_titulo": "INTRANET Básica",
    "texto_login_subtitulo": "Acesso restrito a usuários autorizados",
    "texto_login_hint": "Primeiro acesso? Use master / master e troque a senha.",
    "texto_home_saudacao": "Olá",
    "texto_home_subtitulo": "Sua intranet corporativa é tudo em um só lugar.",
    "texto_rodape": "uso interno",
}


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_auditoria (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT NOT NULL,
            modulo TEXT NOT NULL,
            acao TEXT NOT NULL,
            descricao TEXT,
            timestamp DATETIME DEFAULT (datetime('now','localtime')),
            hash_arquivo TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_config (
            chave TEXT PRIMARY KEY,
            valor TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_sessoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT NOT NULL,
            modulo TEXT,
            login_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            logout_timestamp DATETIME,
            cookie_hash TEXT NOT NULL
        )
    """)
    cur.execute("SELECT COUNT(*) FROM tb_config")
    if (cur.fetchone()[0] or 0) == 0:
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES ('versao_sistema', '1.0.260827')")
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES ('cotadisco_global_gb', '10')")
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES ('backup_interval_hours', '12')")
    # Versão individual de cada módulo (1.0.AAMMDD) — idempotente, não sobrescreve edição manual
    for _chave_mod, _ver in (
        ("usuarios", "1.0.260901"),
        ("auditoria", "1.0.260901"),
        ("editar_pdf", "1.0.260827"),
        ("empenhos", "1.0.260901"),
        ("blog", "1.0.260901"),
        ("solicita_impressao", "1.0.260901"),
    ):
        cur.execute("INSERT OR IGNORE INTO tb_config (chave, valor) VALUES (?, ?)",
                    (f"versao_modulo:{_chave_mod}", _ver))
    for chave, valor in PADRAO_CONFIG.items():
        cur.execute("INSERT OR IGNORE INTO tb_config (chave, valor) VALUES (?, ?)", (chave, valor))
    conn.commit()
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()


def get_config(chave, default=""):
    """Leitura pontual de configuração (camada mais baixa — sem imports circulares)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT valor FROM tb_config WHERE chave=?", (chave,))
        row = cur.fetchone()
        return row[0] if row else default
    finally:
        conn.close()


def set_config(chave, valor):
    """Gravação de configuração."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("INSERT OR REPLACE INTO tb_config (chave, valor) VALUES (?, ?)", (chave, str(valor)))
        conn.commit()
    finally:
        conn.close()


def favicon_versao():
    """mtime do favicon atual — muda quando o .ico é trocado (cache-busting da aba)."""
    try:
        return int(os.path.getmtime(os.path.join(BASE_DIR, "assets", "favicon_atual.ico")))
    except OSError:
        return 0
