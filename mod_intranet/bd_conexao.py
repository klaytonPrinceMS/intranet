"""Central database connection and configuration layer. Internally delegates
to `Repositorio` (SQLAlchemy ORM) while keeping raw sqlite3 `get_connection`
for backward compatibility.

Conexão e configurações centrais do Intranet (banco central db_mod_intranet.db).

Camada mais baixa: sem imports circulares — só os outros módulos dependem daqui.
Usa `Repositorio` (SQLAlchemy ORM) internamente para `get_config`/`set_config`;
mantém `get_connection` (sqlite3 raw) para compatibilidade com código
legado que ainda não foi migrado.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

import sqlite3
from functools import lru_cache

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "db_mod_intranet.db")

PADRAO_CONFIG = {
    "titulo_sistema": "INTRANET",
    "icone_sistema": "hub",
    "cor_principal": "#000000",
    "cor_fundo": "#EEEEEE",
    "texto_login_titulo": "INTRANET Básica",
    "texto_login_subtitulo": "Acesso restrito a usuários autorizados",
    "texto_login_hint": "Novos usuários? Procure o DTI para realizar o seu cadastro.",
    "texto_home_saudacao": "Olá",
    "texto_home_subtitulo": "Sua intranet corporativa é tudo em um só lugar.",
    "texto_rodape": "uso interno",
    # Observabilidade — loguru (aba Observabilidade)
    "log_ativo": "1",
    "log_nivel": "INFO",
    "log_rotacao": "1 month",
    "log_retencao": "4 months",
    "log_console": "auto",
    "log_otel_envio": "1",
    "log_otel_nivel": "DEBUG",
    # Observabilidade — telemetria OTel / stack remota
    "otel_ativo": "1",
    "otel_endpoint": "localhost:4317",
    "otel_auto_start_stack": "1",
    # Observabilidade — Grafana
    "grafana_url": "http://localhost:3000",
    # SGBD — SQLite (padrão universal) ou PostgreSQL opcional em container
    # (docker/postgres/docker-compose.yml; engine via banco_conexao.py)
    "banco_tipo": "sqlite",
    "postgres_url": "postgresql+psycopg2://intranet:intranet@localhost:5432/intranet",
    # Usuário de operações normais (criado no banco PostgreSQL)
    "banco_usuario": "klayton",
    "banco_senha": "klayton",
    # Usuário de operações administrativas (criação de banco, migrations)
    "banco_admin_usuario": "master",
    "banco_admin_senha": "master",
    # Aparência do módulo Intranet (botões do sistema — mesmo contrato
    # de 6 chaves dos demais módulos, prefixo "intranet")
    "intranet_cor_botao": "#000000",
    "intranet_cor_texto_botao": "#FFFFFF",
    "intranet_cor_fundo": "",
    "intranet_cor_titulo": "#212121",
    "intranet_btn_tamanho": "medium",
    "intranet_texto_header": "",
    # Aparência dos cards do módulo Intranet (fundo + texto base)
    "intranet_cor_fundo_card": "#FFFFFF",
    "intranet_cor_texto_card": "",
    # Avisos do sistema (toasts): tempo de exibição em segundos (1-30)
    "notificacao_timeout": "10",
}


def get_connection():
    """Legacy raw DBAPI connection (WAL + synchronous=NORMAL).

    Prefer `Repositorio` from `repositorio.py` for new code.
    EN: Returns a DBAPI connection (SQLite or PostgreSQL) for legacy callers.
    PT: Devolve conexão DBAPI (SQLite ou PostgreSQL) para código legado.
    """
    from mod_intranet.banco_conexao import conexao
    conn = conexao("intranet")
    if conn is None:
        raise RuntimeError("Falha ao abrir conexão do banco central")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_db():
    """Bootstrap do banco central: cria tabelas e semeia padrões (idempotente).

    Usa `conexao("intranet")` (SQLite ou PostgreSQL) — o sistema controla o
    backend. `INSERT OR IGNORE` virou `ON CONFLICT DO NOTHING` (portável).
    """
    from mod_intranet.banco_conexao import conexao

    conn = conexao("intranet")
    if conn is None:
        raise RuntimeError("Falha ao abrir conexão do banco central")
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_config (
            chave TEXT PRIMARY KEY,
            valor TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_sessoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT NOT NULL,
            modulo TEXT,
            login_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            logout_timestamp DATETIME,
            cookie_hash TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_modulos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chave TEXT NOT NULL UNIQUE,
            nome TEXT NOT NULL,
            icone TEXT,
            rota TEXT NOT NULL,
            ativo INTEGER NOT NULL DEFAULT 1,
            nativo INTEGER NOT NULL DEFAULT 0,
            ordem INTEGER NOT NULL DEFAULT 0
        )
    """)
    cur.execute("SELECT COUNT(*) FROM tb_config")
    if (cur.fetchone()[0] or 0) == 0:
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES ('versao_sistema', '1.0.260908')")
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES ('cotadisco_global_gb', '10')")
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES ('backup_interval_hours', '12')")
    for _chave_mod, _ver in (
        ("usuarios", "1.0.260908"),
        ("auditoria", "1.0.260908"),
        ("editar_pdf", "1.0.260908"),
        ("empenhos", "1.0.260908"),
        ("blog", "1.0.260908"),
        ("solicita_impressao", "1.0.260908"),
    ):
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES (?, ?) "
                    "ON CONFLICT DO NOTHING",
                    (f"versao_modulo:{_chave_mod}", _ver))
    for chave, valor in PADRAO_CONFIG.items():
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES (?, ?) "
                    "ON CONFLICT DO NOTHING", (chave, valor))
    # Migração ÚNICA (06/09): cores padrão por módulo. O banco existente guardou
    # valores antigos/customizados semeados (intranet/`cor_principal` = #1565C0,
    # blog/editpdf/empenhos/solicita com cores soltas) que sobrescrevem os
    # padrões do PRÓPRIO módulo. Zeramos as chaves `<prefixo>_cor_botao` para que
    # cada módulo caia no `PADROES_TEMA` (blog #000000, empenhos #000000,
    # editar_pdf #000000, solicita_impressao #000000, demais #000000). Guardado
    # pelo marcador `migracao_cores_padrao` — roda UMA vez para não apagar
    # futuras personalizações do admin.
    cur.execute("SELECT COUNT(*) FROM tb_config WHERE chave='migracao_cores_padrao'")
    migrado = (cur.fetchone()[0] or 0) > 0
    if not migrado:
        cur.execute("UPDATE tb_config SET valor='#000000' "
                    "WHERE chave='cor_principal' AND valor='#1565C0'")
        for _chave in ("intranet", "usuarios", "auditoria", "blog",
                       "editpdf", "empenhos", "solicita_impressao"):
            cur.execute("UPDATE tb_config SET valor='' WHERE chave=?",
                        (f"{_chave}_cor_botao",))
        cur.execute("INSERT INTO tb_config (chave, valor) "
                    "VALUES ('migracao_cores_padrao', '1') ON CONFLICT DO NOTHING")
    # Migração ÚNICA (08/09): padronização geral — TODOS os módulos na cor do
    # intranet (PRETO #000000, via `PADROES_TEMA`) e versão sistema+módulos em
    # 1.0.260908. Zera as chaves de cor de botão dos módulos (caem no padrão do
    # próprio módulo, agora #000000) e atualiza as versões. Guardado pelo
    # marcador `migracao_padronizacao_260908` — roda UMA vez.
    cur.execute("SELECT COUNT(*) FROM tb_config WHERE chave='migracao_padronizacao_260908'")
    if (cur.fetchone()[0] or 0) == 0:
        for _chave in ("intranet", "usuarios", "auditoria", "blog",
                       "editpdf", "empenhos", "solicita_impressao"):
            cur.execute("UPDATE tb_config SET valor='' WHERE chave=?",
                        (f"{_chave}_cor_botao",))
        cur.execute("UPDATE tb_config SET valor='1.0.260908' "
                    "WHERE chave='versao_sistema'")
        cur.execute("UPDATE tb_config SET valor='1.0.260908' "
                    "WHERE chave LIKE 'versao_modulo:%'")
        cur.execute("INSERT INTO tb_config (chave, valor) "
                    "VALUES ('migracao_padronizacao_260908', '1') ON CONFLICT DO NOTHING")
    conn.commit()
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()


def get_config(chave, default=""):
    """Leitura pontual de configuração via Repositorio (SQLAlchemy ORM).

    Camada mais baixa: sem imports circulares. Delega para `Repositorio.obter_config`.
    """
    try:
        from mod_intranet.repositorio import Repositorio
        with Repositorio() as repo:
            return repo.obter_config(chave, default)
    except Exception:
        pass
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT valor FROM tb_config WHERE chave=?", (chave,))
        row = cur.fetchone()
        return row[0] if row else default
    finally:
        conn.close()


def set_config(chave, valor):
    """Gravação de configuração via Repositorio (SQLAlchemy ORM).

    Delega para `Repositorio.definir_config`.
    """
    try:
        from mod_intranet.repositorio import Repositorio
        with Repositorio() as repo:
            ok = repo.definir_config(chave, valor)
            if ok:
                try:
                    favicon_versao.cache_clear()
                except Exception:
                    pass
                try:
                    from mod_intranet import tema_modulo as _tm
                    _tm._cfg.cache_clear()
                    _tm.ler_tema.cache_clear()
                except Exception:
                    pass
                if chave == "empenhos_template_nome":
                    try:
                        from mod_renomear_empenho.bd_manipulador import template_nome_atual as _tn
                        _tn.cache_clear()
                    except Exception:
                        pass
            return ok
    except Exception:
        pass
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO tb_config (chave, valor) VALUES (?, ?) "
            "ON CONFLICT (chave) DO UPDATE SET valor = EXCLUDED.valor",
            (chave, str(valor)))
        conn.commit()
    finally:
        conn.close()


@lru_cache(maxsize=1)
def favicon_versao():
    """mtime do favicon atual — muda quando o .ico é trocado (cache-busting da aba)."""
    try:
        return int(os.path.getmtime(os.path.join(BASE_DIR, "assets", "favicon_atual.ico")))
    except OSError:
        return 0
