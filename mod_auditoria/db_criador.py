"""Legacy database creator — mod_auditoria (kept only for compatibility).

Criador de BD LEGADO do módulo Auditoria, mantido apenas por compatibilidade
histórica. O criador VIGENTE do esquema é `init_db_auditoria()` em
`mod_auditoria/db_manipulador.py`, que cria `tb_auditoria_meta` e as tabelas
por módulo (`tb_auditoria_<modulo>`). Este arquivo cria apenas a tabela de
metadados e não deve ser usado como fonte de verdade.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_AUDITORIA_PATH = os.path.join(BASE_DIR, "db_mod_auditoria.db")


def init_db():
    """Creates the audit metadata table in the module's own database (legacy).

    Cria `tb_auditoria_meta` em `db_mod_auditoria.db` (WAL). Idempotente.
    O criador vigente do esquema é `manipulador_bd.init_db_auditoria()`.
    """
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