import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
from mod_intranet.conexao_bd import get_connection, DB_PATH

print("DB_PATH:", DB_PATH, "exists:", os.path.exists(DB_PATH))

# Conexao 1: cria tb_config e commita
c1 = get_connection()
c1.execute("CREATE TABLE IF NOT EXISTS tb_config (chave TEXT PRIMARY KEY, valor TEXT NOT NULL)")
c1.execute("INSERT OR IGNORE INTO tb_config (chave, valor) VALUES ('x','1')")
c1.commit()
c1.close()
print("apos c1: arquivos:", [f for f in os.listdir('.') if 'db_mod_intranet' in f])

# Conexao 2: nova conexao, consegue ver tb_config?
c2 = get_connection()
try:
    r = c2.execute("SELECT valor FROM tb_config WHERE chave='x'").fetchone()
    print("c2 enxerga tb_config:", r)
except Exception as e:
    print("c2 ERRO:", e)
c2.close()
