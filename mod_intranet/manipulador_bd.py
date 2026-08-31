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
    """Migração idempotente: colunas de rastreabilidade LGPD.

    tb_sessoes: ip, user_agent, dispositivo, mac
    tb_auditoria: ip, user_agent
    Registros anteriores permanecem NULL (exibidos como '—').
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
            "tb_auditoria": [("ip", "TEXT"), ("user_agent", "TEXT"), ("client_hostname", "TEXT")],
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
        # Índices de consulta da trilha de auditoria (idempotente).
        # Sem eles, os filtros do módulo de auditoria degradam com volume.
        cur.executescript("""
            CREATE INDEX IF NOT EXISTS idx_auditoria_modulo ON tb_auditoria (modulo);
            CREATE INDEX IF NOT EXISTS idx_auditoria_usuario ON tb_auditoria (usuario);
            CREATE INDEX IF NOT EXISTS idx_auditoria_timestamp ON tb_auditoria (timestamp);
        """)
        conn.commit()
        _migracao_rastreio_feita = True
    except Exception:
        pass
    finally:
        conn.close()


def audit_log(usuario, modulo, acao, descricao, hash_arquivo=None,
              client_ip="__CTX__", client_user_agent="__CTX__", client_hostname=None):
    """Registra ação na tabela central de auditoria com rastreabilidade.

    client_ip/client_user_agent em '__CTX__' (default) são preenchidos do contexto HTTP
    corrente quando disponível. O carimbo de tempo é gravado em horário
    local (RF-08) para consistência com os registros de sessão.
    """
    import datetime as _dt
    garantir_rastreabilidade()
    from mod_intranet import contexto
    contexto_atual = contexto.contexto_atual
    if client_ip == "__CTX__" or client_user_agent == "__CTX__":
        ctx = contexto_atual()
        if client_ip == "__CTX__":
            client_ip = ctx.get('ip')
        if client_user_agent == "__CTX__":
            client_user_agent = ctx.get('ua')
    timestamp = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO tb_auditoria (usuario, modulo, acao, descricao, hash_arquivo, ip, user_agent, client_hostname, timestamp)\n"
            "               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (usuario, modulo, acao, descricao, hash_arquivo, client_ip, client_user_agent, client_hostname, timestamp),
        )
        conn.commit()
    finally:
        conn.close()


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
