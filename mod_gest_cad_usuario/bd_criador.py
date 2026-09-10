"""Legacy database creator — mod_gest_cad_usuario (kept only for compatibility).

Criador de BD LEGADO do módulo de Gestão de Usuários, mantido apenas por
compatibilidade histórica. O criador VIGENTE do esquema é `init_db()` em
`mod_gest_cad_usuario/db_manipulador.py` (banco próprio
`db_mod_gest_cad_usuario.db`, com migrações e seeds). Este arquivo conecta no
banco CENTRAL e cria um esquema divergente (inclui `tb_modulo_perfil`, que
não existe no esquema real) — não usar como fonte de verdade.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

import sqlite3
import os

from mod_intranet.bd_conexao import get_connection, DB_PATH
from mod_intranet.bd_manipulador import audit_log

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_CAD_PATH = os.path.join(BASE_DIR, "db_mod_gest_cad_usuario.db")


def _log():
    """Logger do módulo (loguru) — arquivo dedicado logs/gest_cad_usuario_<data>.log."""
    from mod_intranet import observabilidade
    return observabilidade.get_logger("gest_cad_usuario")


def init_db():
    """Creates the LEGACY divergent schema in the CENTRAL database (do not use).

    Cria `tb_usuarios` e `tb_modulo_perfil` no banco central, semeia o
    usuário `master`/`master` e permissões padrão — comportamento legado.
    O esquema real (com `tb_acesso_usuario`, soft delete e migrações) vive em
    `manipulador_bd.init_db()`."""
    _log().info("criador_bd: (legado) inicializando esquema de gest_cad_usuario")
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_nome TEXT NOT NULL UNIQUE,
            user_senha TEXT NOT NULL,
            user_email TEXT,
            user_fone TEXT,
            user_perfil TEXT NOT NULL DEFAULT 'comum',
            user_ativo INTEGER NOT NULL DEFAULT 1,
            data_cadastro DATETIME DEFAULT CURRENT_TIMESTAMP,
            modulo_acesso TEXT DEFAULT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_modulo_perfil (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            modulo_nome TEXT NOT NULL,
            perfil_nome TEXT NOT NULL,
            permissao_escrita INTEGER NOT NULL DEFAULT 0,
            UNIQUE (modulo_nome, perfil_nome)
        )
    """)

    # Inserir usuário master se não existir
    cur.execute("SELECT COUNT(*) FROM tb_usuarios WHERE user_nome='master'")
    if cur.fetchone()[0] == 0:
        from mod_intranet.autenticacao import gerar_hash_senha
        hash_s = gerar_hash_senha("master")
        cur.execute(
            "INSERT INTO tb_usuarios (user_nome, user_senha, user_perfil, user_ativo) VALUES (?, ?, ?, ?)",
            ("master", hash_s, "administrador_geral", True),
        )

    # Permissões padrões
    cur.execute("INSERT OR IGNORE INTO tb_modulo_perfil (modulo_nome, perfil_nome, permissao_escrita) VALUES (?, ?, 1)",
                ("intranet", "administrador_geral"))
    cur.execute("INSERT OR IGNORE INTO tb_modulo_perfil (modulo_nome, perfil_nome, permissao_escrita) VALUES (?, ?, 1)",
                ("intranet", "administrador_modulo"))

    conn.commit()
    conn.close()