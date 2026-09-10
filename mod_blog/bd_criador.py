"""Legacy database creator — mod_blog (kept only for compatibility).

Criador de BD LEGADO do módulo Blog, mantido apenas por compatibilidade
histórica. O criador VIGENTE do esquema é `init_db()` em
`mod_blog/db_manipulador.py` (banco próprio `db_mod_blog.db`, com `tb_config`
local e seeds). Este arquivo conecta no banco CENTRAL, duplica os CRUDs com
comportamento divergente (sanitização sem whitelist, ordenação sem efeito) e
NÃO é importado por ninguém — não usar como fonte de verdade.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

import sqlite3
import os

from mod_intranet.bd_conexao import get_connection, DB_PATH
from mod_intranet.bd_manipulador import audit_log

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_BLOG_PATH = os.path.join(BASE_DIR, "db_mod_blog.db")


def init_db():
    """Creates the legacy post/comment tables in the CENTRAL database.

    Cria `tb_postagens` e `tb_comentarios` no banco central
    (`db_mod_intranet.db`) — comportamento legado. O esquema real do módulo
    vive em `manipulador_bd.init_db()` (banco próprio). Idempotente."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_postagens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            conteudo TEXT NOT NULL,
            autor TEXT NOT NULL,
            data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP,
            data_atualizacao DATETIME DEFAULT CURRENT_TIMESTAMP,
            ativo INTEGER NOT NULL DEFAULT 1
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_comentarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            postagem_id INTEGER NOT NULL,
            autor TEXT NOT NULL,
            conteudo TEXT NOT NULL,
            data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (postagem_id) REFERENCES tb_postagens(id) ON DELETE CASCADE
        )
    """)

    conn.commit()
    conn.close()


def listar_postagens(ativo=True, ordem="DESC"):
    """Legacy listing of posts in the CENTRAL database (do not use).

    Lista postagens do banco central (legado). A versão vigente, com ordem
    validada e banco próprio, é `mod_blog.manipulador_bd.listar_postagens`."""
    conn = get_connection()
    cur = conn.cursor()
    sql = "SELECT id, titulo, autor, data_criacao, ativo FROM tb_postagens WHERE ativo=? ORDER BY data_criacao ?"
    cur.execute(sql, (1 if ativo else 0, ordem))
    rows = cur.fetchall()
    conn.close()
    return rows


def obter_postagem(id_post):
    """Legacy single-post lookup in the CENTRAL database (do not use)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, titulo, conteudo, autor, data_criacao, data_atualizacao, ativo FROM tb_postagens WHERE id=?", (id_post,))
    row = cur.fetchone()
    conn.close()
    return row


def criar_postagem(titulo, conteudo, autor):
    """Legacy post creation in the CENTRAL database (do not use).

    Sanitiza apenas o conteúdo com `nh3.clean` padrão (sem whitelist de tags)
    e grava no banco central. Retorna o id criado ou None em falha."""
    from nh3 import clean
    conn = get_connection()
    cur = conn.cursor()
    try:
        conteudo_sanitizado = clean(conteudo)
        cur.execute(
            "INSERT INTO tb_postagens (titulo, conteudo, autor) VALUES (?, ?, ?)",
            (titulo, conteudo_sanitizado, autor),
        )
        post_id = cur.lastrowid
        conn.commit()
        return post_id
    except Exception as e:
        print(f"Erro ao criar postagem: {e}")
        return None
    finally:
        conn.close()


def atualizar_postagem(id_post, titulo, conteudo, autor):
    """Legacy post update in the CENTRAL database (do not use)."""
    from nh3 import clean
    conn = get_connection()
    cur = conn.cursor()
    try:
        conteudo_sanitizado = clean(conteudo)
        cur.execute(
            "UPDATE tb_postagens SET titulo=?, conteudo=?, data_atualizacao=datetime('now') WHERE id=?",
            (titulo, conteudo_sanitizado, id_post),
        )
        conn.commit()
        return cur.rowcount > 0
    except Exception as e:
        print(f"Erro ao atualizar postagem: {e}")
        return False
    finally:
        conn.close()


def excluir_postagem(id_post, autor):
    """Legacy soft delete (ativo=0) in the CENTRAL database (do not use)."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE tb_postagens SET ativo=0 WHERE id=?", (id_post,))
        conn.commit()
        return cur.rowcount > 0
    except Exception:
        return False
    finally:
        conn.close()


def listar_comentarios(postagem_id):
    """Legacy comment listing in the CENTRAL database (do not use)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, autor, conteudo, data_criacao FROM tb_comentarios WHERE postagem_id=? ORDER BY data_criacao", (postagem_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


def criar_comentario(postagem_id, autor, conteudo):
    """Legacy comment creation in the CENTRAL database (do not use)."""
    from nh3 import clean
    conn = get_connection()
    cur = conn.cursor()
    try:
        conteudo_sanitizado = clean(conteudo)
        cur.execute(
            "INSERT INTO tb_comentarios (postagem_id, autor, conteudo) VALUES (?, ?, ?)",
            (postagem_id, autor, conteudo_sanitizado),
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"Erro ao criar comentario: {e}")
        return False
    finally:
        conn.close()