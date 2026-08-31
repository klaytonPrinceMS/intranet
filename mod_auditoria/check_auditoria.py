import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _log():
    from mod_intranet import observabilidade
    return observabilidade.get_logger("auditoria")


conn = sqlite3.connect(os.path.join(BASE_DIR, 'db_mod_intranet.db'))
cur = conn.cursor()
try:
    cur.execute("SELECT * FROM tb_config WHERE chave LIKE 'auditoria%'")
    for r in cur.fetchall():
        print(r)
    _log().info("leitura das configs de auditoria concluida")
except Exception:
    _log().exception("falha ao ler configs de auditoria")
finally:
    conn.close()
