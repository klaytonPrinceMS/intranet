"""Criador de BD LEGADO — mod_solicita_impressao.

ATENÇÃO: Este arquivo é mantido apenas por compatibilidade histórica.
O banco REAL do módulo é db_mod_solicita_impressao.db (SQLite WAL),
criado e gerenciado por manipulador_bd.py via init_db().

Este criador_bd.py aponta para o banco CENTRAL (db_mod_intranet.db)
e NÃO deve ser usado como fonte de verdade para o módulo.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

import sqlite3

from mod_intranet.conexao_bd import get_connection, DB_PATH


def init_db():
    """Cria tabelas legadas no banco CENTRAL (apenas para compatibilidade).
    
    NÃO USA ESTE BANCO PARA DADOS DO MÓDULO.
    O módulo usa db_mod_solicita_impressao.db (ver manipulador_bd.py).
    """
    conn = get_connection()
    cur = conn.cursor()
    
    # Tabela legada de solicitações (apenas referência)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_solicitacoes_impressao_legacy (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT NOT NULL,
            arquivo TEXT,
            qtd_copias INTEGER DEFAULT 1,
            papel TEXT DEFAULT 'A4',
            cor TEXT DEFAULT 'PB',
            frente_verso INTEGER DEFAULT 0,
            tipo_borda TEXT,
            observacoes TEXT,
            secretaria TEXT,
            setor TEXT,
            status TEXT DEFAULT 'pendente',
            data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print("Banco legado (central) inicializado para mod_solicita_impressao")