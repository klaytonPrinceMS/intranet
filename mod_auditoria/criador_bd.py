import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_AUDITORIA_PATH = os.path.join(BASE_DIR, "db_mod_auditoria.db")


def init_db():
    conn = sqlite3.connect(DB_AUDITORIA_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tb_auditoria_meta (
                modulo TEXT PRIMARY KEY,
                nome TEXT NOT NULL,
                criada_em TEXT DEFAULT (datetime('now','localtime'))
            )
        """)
        conn.commit()
    finally:
        conn.close()