"""Diagnostic script — prints audit-related keys from the central tb_config.

Script de diagnóstico standalone: conecta no banco central
(`db_mod_intranet.db`), lista as chaves de configuração `auditoria%` da
`tb_config` e registra o resultado no log do módulo (`logs/auditoria_*.log`).
Não é usado pela aplicação — ferramenta de apoio ao desenvolvedor.
"""
import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _log():
    """Logger do módulo (loguru) — arquivo dedicado logs/auditoria_<data>.log."""
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
