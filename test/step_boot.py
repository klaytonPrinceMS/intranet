import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
from mod_intranet.conexao_bd import get_connection

def mostra(label):
    try:
        c = get_connection()
        tabs = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        c.close()
        print(f"{label}: tabelas={tabs}")
    except Exception as e:
        print(f"{label}: ERRO {e}")

print("== antes de qualquer init ==")
mostra("estado inicial")

from mod_intranet.conexao_bd import init_db as init_central
init_central()
mostra("apos init_central")

from mod_intranet.manipulador_bd import garantir_rastreabilidade
garantir_rastreabilidade()
mostra("apos garantir_rastreabilidade")

from mod_blog.manipulador_bd import init_db as init_blog
init_blog()
mostra("apos init_blog")

from mod_gest_cad_usuario.manipulador_bd import init_db as init_users
mostra("antes de init_users (import ja roda init_db no modulo)")
