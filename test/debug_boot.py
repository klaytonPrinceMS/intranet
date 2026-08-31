import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mod_intranet.conexao_bd import get_connection, init_db as init_central
from mod_intranet.manipulador_bd import garantir_rastreabilidade
from mod_blog.manipulador_bd import init_db as init_blog

def mostra(l):
    c = get_connection()
    try:
        tabs = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    except Exception as e:
        tabs = f"ERRO {e}"
    c.close()
    print(l, "->", tabs)

init_central()
mostra("apos init_central")
garantir_rastreabilidade()
mostra("apos garantir")
init_blog()
mostra("apos init_blog")
print(">>> agora dispara init_db do modulo de usuarios (import) <<<")
import mod_gest_cad_usuario.manipulador_bd
mostra("apos init_users")
