import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

import sqlite3
import os

from mod_intranet.conexao_bd import get_connection, DB_PATH

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_EDIT_PATH = os.path.join(BASE_DIR, "db_mod_edit_pdf.db")


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_arquivos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_arquivo TEXT NOT NULL,
            usuario TEXT NOT NULL,
            data_upload DATETIME DEFAULT CURRENT_TIMESTAMP,
            caminho_arquivo TEXT NOT NULL,
            tamanho_bytes INTEGER,
            hash_sha256 TEXT NOT NULL,
            ativo INTEGER NOT NULL DEFAULT 1
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_cota_disco (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT NOT NULL,
            total_bytes INTEGER NOT NULL DEFAULT 0,
            ultimo_acesso DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Inserir configuração de cota global se não existir
    cur.execute("SELECT COUNT(*) FROM tb_config")
    if cur.fetchone()[0] == 0:
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES ('versao_sistema', '1.0.260827')")
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES ('cotadisco_global_gb', '10')")

    conn.commit()
    conn.close()