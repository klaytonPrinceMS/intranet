"""Legacy database creator — mod_renomear_empenho (kept only for compatibility).

Criador de BD LEGADO do módulo Renomear Empenhos, mantido apenas por
compatibilidade histórica. O criador VIGENTE do esquema é
`init_db_empenho()` em `mod_renomear_empenho/db_manipulador.py` (banco
próprio `db_mod_renomear_empenho.db`, com FTS5 real, quarentena, regras,
auditoria de arquivos e solicitações). Este arquivo conecta no banco CENTRAL
e cria um esquema FTS5 "fantasma" divergente — não usar como fonte de
verdade.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

import sqlite3
import os

from mod_intranet.bd_conexao import get_connection, DB_PATH

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_RENOMEAR_PATH = os.path.join(BASE_DIR, "db_mod_renomear_empenho.db")


def init_db():
    """Creates the LEGACY divergent schema in the CENTRAL database (do not use).

    Cria `tb_empenhos`/`tb_indexador_fts5` legados e uma FTS5 virtual com
    trigger de INSERT quebrado (referência inválida
    `tb_indexador_pesquisa_fts5fts5`) no banco central. O esquema real vive
    em `manipulador_bd.init_db_empenho()`."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_empenhos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_arquivo_origem TEXT NOT NULL,
            nome_arquivo_final TEXT,
            pagador TEXT,
            cpf_cnpj TEXT,
            orgao TEXT,
            valor TEXT,
            data_emissao TEXT,
            data_vencimento TEXT,
            hash_sha256_origem TEXT,
            hash_sha256_destino TEXT,
            modulo_acesso TEXT DEFAULT 'renomear_empenho',
            data_cadastro DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_indexador_fts5 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empenho_id INTEGER,
            campo TEXT NOT NULL,
            valor TEXT NOT NULL,
            FOREIGN KEY (empenho_id) REFERENCES tb_empenhos(id) ON DELETE CASCADE,
            UNIQUE (empenho_id, campo)
        )
    """)

    # FTS5 virtual table para busca full-text
    cur.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS tb_indexador_pesquisa_fts5 USING fts5(
            pagador, cpf_cnpj, orgao, valor, data_emissao, data_vencimento,
            content='tb_empenhos', content_rowid='id'
        )
    """)

    # Trigger para manter o FTS em sincronia
    cur.execute("""
        CREATE TRIGGER IF NOT EXISTS tr_fts_atualizacao AFTER INSERT ON tb_empenhos
        BEGIN
            INSERT INTO tb_indexador_pesquisa_fts5(tb_indexador_pesquisa_ftsfts5, pagador, cpf_cnpj, orgao, valor, data_emissao, data_vencimento)
            VALUES (new.id, new.pagador, new.cpf_cnpj, new.orgao, new.valor, new.data_emissao, new.data_vencimento);
        END
    """)

    # Trigger para exclusão
    cur.execute("""
        CREATE TRIGGER IF NOT EXISTS tr_fts_exclusao AFTER DELETE ON tb_empenhos
        BEGIN
            DELETE FROM tb_indexador_pesquisa_fts5 WHERE empenho_id = old.id;
        END
    """)

    conn.commit()
    conn.close()