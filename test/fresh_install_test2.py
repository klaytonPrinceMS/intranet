import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mod_intranet.conexao_bd import get_connection

# Conexao previa "vazia" ao banco central (como o mostra() do step_boot)
c = get_connection()
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
c.close()

from mod_intranet.mod_intranet_inicializacao_bd import inicializar_bancos
inicializar_bancos()
import sqlite3
c = sqlite3.connect('db_mod_intranet.db')
print('central tabelas:', [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")])
c.close()
c2 = sqlite3.connect('db_mod_gest_cad_usuario.db')
m = c2.execute("SELECT user_nome,user_perfil FROM tb_usuarios WHERE user_nome='master'").fetchone()
print('master:', m)
c2.close()
print('FRESH INSTALL OK')
