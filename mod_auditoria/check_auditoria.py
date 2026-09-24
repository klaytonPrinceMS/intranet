"""Diagnostic script — prints audit-related keys from the central tb_config.

Script de diagnóstico standalone: conecta no banco central via
`banco_conexao.conexao("intranet")` (SQLite ou PostgreSQL, portável),
lista as chaves de configuração `auditoria%` da `tb_config` e registra
o resultado no log do módulo (`logs/auditoria_*.log`).
Não é usado pela aplicação — ferramenta de apoio ao desenvolvedor.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _log():
    """Logger do módulo (loguru) — arquivo dedicado logs/auditoria_<data>.log."""
    try:
        from mod_intranet import observabilidade
        return observabilidade.get_logger("auditoria")
    except Exception:
        import logging
        return logging.getLogger("auditoria")


def main():
    """Lê as configs de auditoria via conexão portátil (sem sqlite3 cru)."""
    conn = None
    try:
        from mod_intranet.banco_conexao import conexao
        conn = conexao("intranet")
        if conn is None:
            raise RuntimeError("Falha ao abrir conexão do módulo intranet")
        cur = conn.cursor()
        cur.execute("SELECT chave, valor FROM tb_config WHERE chave LIKE 'auditoria%'")
        for r in cur.fetchall():
            print(r)
        _log().info("leitura das configs de auditoria concluida")
    except Exception:
        try:
            _log().exception("falha ao ler configs de auditoria")
        except Exception:
            pass
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


if __name__ == "__main__":
    main()
