"""Banco central do Intranet — conexão e auditoria (rastreabilidade LGPD).

Centraliza get_intranet_conn, migração de rastreabilidade, audit_log e hash.
"""
import os
import hashlib
import sqlite3

from mod_intranet.conexao_bd import get_connection, DB_PATH

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_CAD_PATH = os.path.join(BASE_DIR, "db_mod_gest_cad_usuario.db")
DB_EDIT_PATH = os.path.join(BASE_DIR, "db_mod_edit_pdf.db")
DB_BLOG_PATH = os.path.join(BASE_DIR, "db_mod_blog.db")
DB_RENOMEAR_PATH = os.path.join(BASE_DIR, "db_mod_renomear_empenho.db")

_migracao_rastreio_feita = False


def get_intranet_conn():
    return get_connection()


def garantir_rastreabilidade():
    """Migração idempotente das colunas de rastreabilidade LGPD em tb_sessoes
    (ip, user_agent, dispositivo, mac). Registros anteriores permanecem NULL.

    Obs.: a trilha de auditoria deixou de morar no banco central (valor
    removido — agora vive em db_mod_auditoria.db, com uma tabela por módulo).
    """
    global _migracao_rastreio_feita
    if _migracao_rastreio_feita:
        return
    conn = get_connection()
    try:
        cur = conn.cursor()
        planos = {
            "tb_sessoes": [("ip", "TEXT"), ("user_agent", "TEXT"),
                           ("dispositivo", "TEXT"), ("mac", "TEXT")],
        }
        for tabela, colunas in planos.items():
            cur.execute(f"PRAGMA table_info({tabela})")
            existentes = {r[1] for r in cur.fetchall()}
            for coluna, tipo in colunas:
                if coluna not in existentes:
                    cur.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo}")
        cur.execute("SELECT valor FROM tb_config WHERE chave='sessao_retencao'")
        if not cur.fetchone():
            cur.execute("INSERT INTO tb_config (chave, valor) VALUES ('sessao_retencao', '50')")
        conn.commit()
        _migracao_rastreio_feita = True
    except Exception:
        pass
    finally:
        conn.close()


def audit_log(usuario, modulo, acao, descricao, hash_arquivo=None,
              client_ip="__CTX__", client_user_agent="__CTX__", client_hostname=None):
    """Registra ação na auditoria com rastreabilidade.

    A gravação ocorre no banco exclusivo de auditoria
    (db_mod_auditoria.db), na tabela do próprio módulo
    (tb_auditoria_<modulo>), criada automaticamente se necessário —
    assim novos módulos passam a auditar sem alterar o módulo de
    auditoria. client_ip/client_user_agent em '__CTX__' (default) são
    preenchidos do contexto HTTP corrente quando disponível. O carimbo de
    tempo é gravado em horário local (RF-08) para consistência com os
    registros de sessão.
    """
    import datetime as _dt
    from mod_intranet import contexto
    contexto_atual = contexto.contexto_atual
    if client_ip == "__CTX__" or client_user_agent == "__CTX__":
        ctx = contexto_atual()
        if client_ip == "__CTX__":
            client_ip = ctx.get('ip')
        if client_user_agent == "__CTX__":
            client_user_agent = ctx.get('ua')
    timestamp = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    from mod_auditoria.manipulador_bd import registrar_auditoria
    registrar_auditoria(usuario, modulo, acao, descricao, hash_arquivo,
                        client_ip, client_user_agent, client_hostname, timestamp)


def hash_arquivo(caminho):
    """Retorna hash SHA-256 de um arquivo."""
    h = hashlib.sha256()
    try:
        with open(caminho, 'rb') as f:
            bloco = f.read(8192)
            while bloco:
                h.update(bloco)
                bloco = f.read(8192)
    except Exception:
        return None
    return h.hexdigest()
