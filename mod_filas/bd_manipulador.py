"""Módulo Filas — esqueleto (gestor de chamadas com TV).

BD próprio: db_mod_filas.db (WAL).
Tabelas esqueleto: tb_fila, tb_chamada, tb_config_filas.
Acesso via CrudBase/banco_conexao; sem cross-query.
"""

import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_FILAS_PATH = os.path.join(BASE_DIR, "db_mod_filas.db")

def _log():
    from mod_intranet import observabilidade
    return observabilidade.get_logger("filas")

def get_connection():
    from mod_intranet.banco_conexao import conexao
    conn = conexao("filas")
    if conn is None:
        raise RuntimeError("Falha ao abrir conexão mod_filas")
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
    except Exception:
        pass
    return conn

def _audit(ator, acao, alvo, detalhe=""):
    from mod_intranet.bd_manipulador import audit_log
    audit_log(ator or "sistema", "filas", acao, f"Alvo: {alvo}" + (f" | {detalhe}" if detalhe else ""))

def init_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_fila (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL UNIQUE,
            senha_atual TEXT NOT NULL DEFAULT 'A000',
            status TEXT NOT NULL DEFAULT 'ativa',
            guiche TEXT,
            data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_chamada (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fila_id INTEGER NOT NULL REFERENCES tb_fila(id) ON DELETE CASCADE,
            senha TEXT NOT NULL,
            guiche TEXT,
            chamado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
            chamado_por TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_config_filas (
            chave TEXT PRIMARY KEY,
            valor TEXT
        )
    """)
    for k, v in (("filas_modo_tv", "1"), ("filas_senha_prefixo", "A"), ("filas_guiche_padrao", "01")):
        cur.execute("INSERT OR IGNORE INTO tb_config_filas (chave, valor) VALUES (?, ?)", (k, v))
    # seed fila Geral esqueleto
    cur.execute("INSERT OR IGNORE INTO tb_fila (nome, senha_atual, status, guiche) VALUES ('Geral', 'A000', 'ativa', '01')")
    conn.commit()
    conn.close()

def listar_filas():
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, nome, senha_atual, status, guiche, data_criacao FROM tb_fila ORDER BY nome")
        return cur.fetchall()
    finally:
        conn.close()

def gerar_senha(fila_id: int, ator: str = "") -> tuple[bool, str]:
    """Esqueleto: incrementa senha A000→A001 e registra chamada."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT senha_atual FROM tb_fila WHERE id=?", (fila_id,))
        row = cur.fetchone()
        if not row:
            return False, "Fila não encontrada"
        atual = row[0] or "A000"
        # simples incremento numérico sufixo
        import re
        m = re.match(r"([A-Za-z]*)(\d+)", atual)
        if m:
            pref, num = m.group(1) or "A", int(m.group(2))
            nova = f"{pref}{num+1:03d}"
        else:
            nova = "A001"
        cur.execute("UPDATE tb_fila SET senha_atual=? WHERE id=?", (nova, fila_id))
        cur.execute("INSERT INTO tb_chamada (fila_id, senha, guiche, chamado_por) VALUES (?, ?, (SELECT guiche FROM tb_fila WHERE id=?), ?)",
                    (fila_id, nova, fila_id, ator or "sistema"))
        conn.commit()
        _audit(ator or "sistema", "gerar_senha", nova, f"fila={fila_id}")
        return True, nova
    except Exception as e:
        _log().exception(f"gerar_senha falhou: {e}")
        return False, str(e)
    finally:
        conn.close()

def ultima_chamada():
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT senha, guiche, chamado_em FROM tb_chamada ORDER BY id DESC LIMIT 1")
        return cur.fetchone()
    finally:
        conn.close()

def listar_chamadas(limite: int = 20):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, fila_id, senha, guiche, chamado_em, chamado_por FROM tb_chamada ORDER BY id DESC LIMIT ?", (limite,))
        return cur.fetchall()
    finally:
        conn.close()

def remover_vinculos_usuario(user_nome: str) -> int:
    # esqueleto: nada vinculado ao usuário por enquanto
    return 0

def renomear_usuario(nome_atual: str, novo_nome: str):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE tb_chamada SET chamado_por=? WHERE chamado_por=?", (novo_nome, nome_atual))
        conn.commit()
    finally:
        conn.close()

init_db()
