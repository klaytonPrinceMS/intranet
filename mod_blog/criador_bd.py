import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

import sqlite3
import os

from mod_intranet.conexao_bd import get_connection, DB_PATH
from mod_intranet.manipulador_bd import audit_log

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_BLOG_PATH = os.path.join(BASE_DIR, "db_mod_blog.db")


def init_db():
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
    conn = get_connection()
    cur = conn.cursor()
    sql = "SELECT id, titulo, autor, data_criacao, ativo FROM tb_postagens WHERE ativo=? ORDER BY data_criacao ?"
    cur.execute(sql, (1 if ativo else 0, ordem))
    rows = cur.fetchall()
    conn.close()
    return rows


def obter_postagem(id_post):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, titulo, conteudo, autor, data_criacao, data_atualizacao, ativo FROM tb_postagens WHERE id=?", (id_post,))
    row = cur.fetchone()
    conn.close()
    return row


def criar_postagem(titulo, conteudo, autor):
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
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, autor, conteudo, data_criacao FROM tb_comentarios WHERE postagem_id=? ORDER BY data_criacao", (postagem_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


def criar_comentario(postagem_id, autor, conteudo):
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