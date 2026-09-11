"""Database backend selection: SQLite (default) or PostgreSQL (optional).

Camada de seleção de SGBD pensada para o usuário final: servidores simples
seguem com SQLite (padrão, zero dependências extras — os módulos já operam
via `CrudBase`/sqlite3); demandas maiores ativam PostgreSQL em container
(`docker/postgres/docker-compose.yml`). Configuração em `tb_config` central
(ajustável pelo admin, vale para engines criadas depois — sem restart para
trocar de URL):

- `banco_tipo`: `'sqlite'` (padrão) ou `'postgres'`
- `postgres_url`: DSN SQLAlchemy (default `postgresql+psycopg2://
  intranet:intranet@localhost:5432/intranet`)

`obter_engine()` cria a engine SQLAlchemy sob demanda (singleton por DSN,
import lazy — sem `sqlalchemy`/driver instalado o sistema segue de pé em
SQLite com exception registrada no loguru, fail-soft). O DSN nunca é
logado com credenciais (`_dsn_publico` mascara usuário/senha). Os esquemas
dos módulos continuam sendo criados por DDL próprio — a migração de dados
SQLite→PostgreSQL é fase futura documentada.
"""
import sys
import os
import re
import threading
from datetime import datetime, date

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def _log():
    """Returns the loguru logger bound to the core module ("intranet").

    Logger loguru vinculado ao módulo núcleo (`intranet`), no padrão
    `observabilidade._FMT`. Usado para registrar a criação/falha da engine
    sem expor credenciais e sem derrubar a aplicação (fail-soft).
    """
    from mod_intranet import observabilidade
    return observabilidade.get_logger("intranet")


def _dsn_publico(url):
    """Masks credentials in the DSN before logging (never log secrets).

    Remove usuário/senha do DSN para uso seguro em logs: mantém o esquema
    e o host (`postgresql+psycopg2://***@localhost:5432/intranet`); DSN
    sem credenciais volta intacto; qualquer falha devolve `'<dsn>'`.
    """
    try:
        esquema, _, resto = url.partition("://")
        if "@" in resto:
            host = resto.rpartition("@")[2]
            return f"{esquema}://***@{host}"
        return url
    except Exception:
        return "<dsn>"


def _ler_config_sqlite(chave, default=""):
    """Reads a selector config key straight from the central SQLite file.

    Lê `banco_tipo`/`postgres_url` DIRETO do `db_mod_intranet.db` (sqlite),
    sem passar pelo `Repositorio`/engine — evita a recursão
    `sgbd_ativo → get_config → engine → sgbd_ativo`. Essas chaves são o
    "seletor de backend" e vivem no arquivo SQLite central (autoritativo
    no boot). Fail-soft: devolve `default` em qualquer falha.
    """
    try:
        from mod_intranet.repositorio import DB_PATH
        import sqlite3
        conn = sqlite3.connect(DB_PATH)
        try:
            row = conn.execute(
                "SELECT valor FROM tb_config WHERE chave=?", (chave,)).fetchone()
            return (row[0] if row else default) or default
        finally:
            conn.close()
    except Exception:
        return default


def _gravar_config_sqlite(chave, valor):
    """Upserts a selector config key directly in the central SQLite file."""
    try:
        from mod_intranet.repositorio import DB_PATH
        import sqlite3
        conn = sqlite3.connect(DB_PATH)
        try:
            conn.execute(
                "INSERT INTO tb_config (chave, valor) VALUES (?, ?) "
                "ON CONFLICT (chave) DO UPDATE SET valor = EXCLUDED.valor",
                (chave, str(valor)))
            conn.commit()
        finally:
            conn.close()
        return True
    except Exception as e:
        _log().warning(f"_gravar_config_sqlite('{chave}'): {e}")
        return False


def definir_banco_tipo(valor):
    """Sets `banco_tipo` ('sqlite'|'postgres') in the central SQLite file.

    Grava o seletor de backend no arquivo SQLite central (persistente e
    lido no boot). Aplica após reiniciar o servidor."""
    tipo = (valor or "sqlite").strip().lower()
    return _gravar_config_sqlite("banco_tipo",
                                 tipo if tipo in ("sqlite", "postgres") else "sqlite")


def definir_postgres_url(url):
    """Sets `postgres_url` (DSN) in the central SQLite file."""
    return _gravar_config_sqlite("postgres_url", (url or "").strip())


def config_backend() -> dict:
    """Returns the backend selector as a dict (`banco_tipo`, `postgres_url`).

    Usado pela aba de administração (/configuracoes) para exibir e editar o
    seletor de banco (lido do arquivo SQLite central — autoritativo no boot)."""
    return {
        "banco_tipo": sgbd_ativo(),
        "postgres_url": _ler_config_sqlite(
            "postgres_url",
            "postgresql+psycopg2://intranet:intranet@localhost:5432/intranet"),
    }


def salvar_backend(banco_tipo, postgres_url) -> bool:
    """Persists the backend selector (`banco_tipo`, `postgres_url`).

    Grava no arquivo SQLite central. Aplica ao REINICIAR o servidor
    (as conexões ativas seguem no backend anterior)."""
    ok1 = definir_banco_tipo(banco_tipo)
    ok2 = definir_postgres_url(postgres_url)
    return ok1 and ok2


def sgbd_ativo():
    """Returns the active SGBD ('sqlite' or 'postgres') from the central file.

    Lê `banco_tipo` direto do arquivo SQLite central (seletor de backend,
    autoritativo no boot). Valores distintos de 'sqlite'/'postgres' caem
    em 'sqlite'.
    """
    tipo = _ler_config_sqlite("banco_tipo", "sqlite").strip().lower()
    return tipo if tipo in ("sqlite", "postgres") else "sqlite"


def postgres_url(como_admin=False):
    """Returns the configured PostgreSQL DSN (SQLAlchemy format).

    Lê `postgres_url` da `tb_config` central; sem chave/valor devolve o
    DSN default do container (`docker/postgres/docker-compose.yml`).
    Se `como_admin=True`, usa `banco_admin_usuario`/`banco_admin_senha`
    (padrão master/master) para operações administrativas (criação de banco,
    migrations). Caso contrário usa `banco_usuario`/`banco_senha`
    (padrão klayton/klayton) para operações normais.
    """
    try:
        base = _ler_config_sqlite(
            "postgres_url",
            "postgresql+psycopg2://intranet:intranet@localhost:5432/intranet")
        esquema, _, resto = base.partition("://")
        # Se a URL já traz credenciais e não é operação admin, usa-as como está
        # (ex.: container com intranet:intranet) — não sobrescreve com seeds
        # antigos de banco_usuario/banco_senha.
        if not como_admin and "@" in resto:
            return base
        if como_admin:
            user = _ler_config_sqlite("banco_admin_usuario", "master")
            senha = _ler_config_sqlite("banco_admin_senha", "master")
        else:
            user = _ler_config_sqlite("banco_usuario", "intranet")
            senha = _ler_config_sqlite("banco_senha", "intranet")
        if "@" in resto:
            host = resto.rpartition("@")[2]
            return f"{esquema}://{user}:{senha}@{host}"
        return base
    except Exception as e:
        _log().warning(f"banco_conexao: falha ao ler postgres_url, usando default: {e}")
        if como_admin:
            return "postgresql+psycopg2://master:master@localhost:5432/intranet"
        return "postgresql+psycopg2://intranet:intranet@localhost:5432/intranet"


_engine = None
_engine_url = ""
_engine_lock = threading.Lock()


def obter_engine():
    """Returns the SQLAlchemy engine (lazy singleton) or `None` (fail-soft).

    Com `banco_tipo='sqlite'` devolve `None` (o CrudBase/sqlite3 já cobre
    — nada a fazer). Com `'postgres'`, cria `create_engine(url,
    pool_pre_ping=True)` na primeira chamada e reusa nas seguintes;
    DSN alterado na configuração descarta a engine antiga (`dispose`) e
    cria outra — troca vale sem restart. Sem `sqlalchemy`/driver
    instalado, registra exception no loguru e devolve `None` (a
    aplicação segue operando em SQLite).
    """
    global _engine, _engine_url
    if sgbd_ativo() != "postgres":
        return None
    url = postgres_url()
    with _engine_lock:
        if _engine is not None and _engine_url == url:
            return _engine
        try:
            from sqlalchemy import create_engine
            nova = create_engine(url, pool_pre_ping=True, future=True)
            antiga, _engine, _engine_url = _engine, nova, url
            if antiga is not None:
                try:
                    antiga.dispose()
                except Exception:
                    pass
            _log().info(f"banco_conexao: engine PostgreSQL criada "
                        f"({_dsn_publico(url)})")
            return _engine
        except Exception as e:
            _log().exception(f"banco_conexao: falha ao criar engine "
                             f"PostgreSQL ({e}); seguindo em SQLite")
            return None


def engine_disponivel():
    """Returns `True` when the active SGBD has a working engine.

    Verificação rápida para bootstrap/telas de administração: 'sqlite'
    sempre disponível; 'postgres' exige `obter_engine()` sem falha (ou
    engine já criada e válida).
    """
    if sgbd_ativo() == "sqlite":
        return True
    return obter_engine() is not None


# =============================================================================
# PostgreSQL: engine POR MÓDULO (schema próprio) + conexão compatível
# =============================================================================
# Cada módulo usa o SEU schema dentro do banco `intranet` (espelha o modelo
# "um SQLite por módulo"): as tabelas `tb_*` ficam isoladas por schema e as
# colisões de nome (ex.: tb_solicitacoes) desaparecem. A conexão define
# `search_path` para o schema do módulo, então o SQL não qualificado funciona
# igual no SQLite (um arquivo por módulo) e no Postgres (schema por módulo).

SCHEMAS = {
    "intranet": "intranet",
    "blog": "blog",
    "usuarios": "usuarios",
    "auditoria": "auditoria",
    "editar_pdf": "editar_pdf",
    "empenhos": "empenhos",
    "solicita_impressao": "solicita_impressao",
}

_engines_modulo: dict[str, object] = {}
_lock_modulo = threading.Lock()


def schema_modulo(chave: str = "intranet") -> str:
    """PostgreSQL schema name for a module key (fallback: 'intranet')."""
    return SCHEMAS.get(chave, SCHEMAS["intranet"])


def obter_engine_modulo(chave: str = "intranet"):
    """SQLAlchemy engine for a module on the ACTIVE backend.

    postgres: engine para o banco `intranet` com `search_path` = schema do
    módulo (cria o schema na primeira conexão); reutilizado (cache por chave).
    sqlite: devolve `None` — o `repositorio.engine(chave)` cuida dos engines
    SQLite por arquivo.
    """
    if sgbd_ativo() != "postgres":
        return None
    if chave not in SCHEMAS:
        chave = "intranet"
    with _lock_modulo:
        if chave in _engines_modulo:
            return _engines_modulo[chave]
        try:
            from sqlalchemy import create_engine, event
            url = postgres_url()
            eng = create_engine(url, pool_pre_ping=True, future=True)
            schema = schema_modulo(chave)

            @event.listens_for(eng, "connect")
            def _preparar(dbapi_conn, _connection_record):
                cur = dbapi_conn.cursor()
                cur.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
                cur.execute(f'SET search_path TO "{schema}"')
                cur.close()
                # COMMIT: sem isso o `rollback` do pool ao devolver a conexão
                # desfaz o `SET search_path` (é transacional no Postgres).
                dbapi_conn.commit()

            _engines_modulo[chave] = eng
            _log().info(f"banco_conexao: engine Postgres para o módulo "
                        f"'{chave}' (schema '{schema}')")
            return eng
        except Exception as e:
            _log().exception(f"obter_engine_modulo('{chave}'): {e}")
            return None


def _ddl_postgres(ddl: str) -> str:
    """Translates SQLite CREATE TABLE DDL into PostgreSQL-compatible DDL.

    Lida com os padrões usados pelos `init_db` dos módulos: `AUTOINCREMENT`,
    `INTEGER PRIMARY KEY` → `SERIAL PRIMARY KEY`, `BLOB` → `BYTEA`,
    `DATETIME` → `TIMESTAMP` e remove `FOREIGN KEY ... REFERENCES ...`
    (o Postgres exige a tabela referenciada pré-existente; os módulos criam
    na ordem do SQLite — a integridade é gerida no aplicativo). `IF NOT
    EXISTS` é válido em ambos.
    """
    d = (ddl or "").strip()
    if not (d.upper().startswith("CREATE TABLE")
            or d.upper().startswith("ALTER TABLE")):
        return d
    d = re.sub(r"\bAUTOINCREMENT\b", "", d, flags=re.I)
    d = re.sub(r"\bINTEGER\s+PRIMARY\s+KEY\b", "SERIAL PRIMARY KEY", d, flags=re.I)
    d = re.sub(r"\bBLOB\b", "BYTEA", d, flags=re.I)
    d = re.sub(r"\bDATETIME\b", "TIMESTAMP", d, flags=re.I)
    if d.upper().startswith("ALTER TABLE"):
        return d
    # Colunas TEXT com DEFAULT de timestamp recebem cast ::text (Postgres não
    # converte implicitamente no DEFAULT).
    d = re.sub(r"(\bTEXT\b[^,()]*?DEFAULT\s*\((LOCALTIMESTAMP|CURRENT_TIMESTAMP)\))",
               r"\1::text", d, flags=re.I)
    # Remove REFERENCES (inline e de tabela) + cláusulas ON DELETE/UPDATE.
    ref = (r"\s+REFERENCES\s+[`\"]?[\w.]+[`\"]?\s*\([^)]*\)"
           r"(?:\s+ON\s+(?:DELETE|UPDATE)\s+\w+(?:\s+\w+)?)*")
    d = re.sub(ref, "", d, flags=re.I)
    d = re.sub(r",\s*FOREIGN\s+KEY\s*\([^)]*\)", "", d, flags=re.I)
    return d


class _CursorPostgres:
    """psycopg2 cursor proxy: translates `?`→`%s`, SQLite DDL/PRAGMA and
    captures `lastrowid` for plain INSERTs (RETURNING id). Datetime values
    from Postgres are normalized to strings so the app treats dates the same
    way it does in SQLite (backend-agnostic)."""

    def __init__(self, cur):
        self._cur = cur
        self._lastrowid = None

    @staticmethod
    def _preparar(sql, params):
        import re
        s = sql or ""
        # Funções/DDL específicos do SQLite → portáveis para o Postgres.
        s = s.replace("datetime('now','localtime', ?)",
                      "(LOCALTIMESTAMP + cast(? as interval))")
        s = s.replace("datetime('now','localtime')", "LOCALTIMESTAMP")
        s = s.replace("datetime('now')", "CURRENT_TIMESTAMP")
        # GROUP_CONCAT é SQLite-only; no Postgres o equivalente é STRING_AGG
        # (mesma sintaxe/semântica para os usos `GROUP_CONCAT(x, ', ')`).
        s = s.replace("GROUP_CONCAT(", "STRING_AGG(")
        # INSERT OR IGNORE → ON CONFLICT DO NOTHING (válido em SQLite e Postgres).
        if re.match(r"(?is)^\s*INSERT\s+OR\s+IGNORE\s+INTO", s):
            s = re.sub(r"(?is)^\s*INSERT\s+OR\s+IGNORE\s+INTO", "INSERT INTO", s, count=1)
            s = s.rstrip(";") + " ON CONFLICT DO NOTHING"
        if params is None:
            return s, None
        if isinstance(params, (list, tuple)):
            return s.replace("?", "%s"), params
        return s, params

    def execute(self, sql, params=None):
        s = (sql or "").strip()
        if not s:
            return self._cur.execute(s)
        if s.upper().startswith("PRAGMA"):
            m = re.match(r"(?is)^\s*PRAGMA\s+TABLE_INFO\(\s*['\"]?([a-zA-Z_0-9]+)['\"]?\s*\)", s)
            if m:
                s = (f"SELECT 0, column_name FROM information_schema.columns "
                     f"WHERE table_schema = current_schema() "
                     f"AND table_name = '{m.group(1)}'")
            else:
                self._cur.execute("SELECT NULL WHERE 1=0")
                return self._cur  # PRAGMA (journal_mode, etc.) sem efeito/resultado
        if "CREATE VIRTUAL TABLE" in s.upper():
            return self._cur  # FTS5 é SQLite — módulo usa tabela de fallback
        if "CREATE TRIGGER" in s.upper():
            return self._cur  # trigger FTS5 (tr_fts_del_empenho) é SQLite-only
        # sqlite_master é sistema do SQLite: no Postgres devolve SEM resultados
        # (as migrações guardadas por ele são para bancos SQLite existentes).
        if "sqlite_master" in s.lower():
            self._cur.execute("SELECT NULL WHERE 1=0")
            return self._cur
        s, params = self._preparar(s, params)  # datetime(), OR IGNORE, ?→%s
        s = _ddl_postgres(s)                    # tipos SQLite → Postgres
        upper = s.upper()
        if upper.startswith("INSERT INTO") and "RETURNING" not in upper \
                and "ON CONFLICT" not in upper:
            # Captura lastrowid via RETURNING id, com SAVEPOINT para não abortar
            # a transação se a tabela não tiver coluna `id` (ex.: tb_config,
            # cuja PK é `chave`) nem em outros erros pontuais.
            tentativa = s.rstrip(";") + " RETURNING id"
            try:
                self._cur.execute("SAVEPOINT ng_sp")
                if params is None:
                    self._cur.execute(tentativa)
                else:
                    self._cur.execute(tentativa, params)
                row = self._cur.fetchone()
                self._cur.execute("RELEASE SAVEPOINT ng_sp")
                self._lastrowid = row[0] if row else None
                return self._cur
            except Exception:
                try:
                    self._cur.execute("ROLLBACK TO SAVEPOINT ng_sp")
                except Exception:
                    pass
                self._lastrowid = None
        if s.upper().startswith("SELECT"):
            if params is None:
                self._cur.execute(s)
            else:
                self._cur.execute(s, params)
            self._lastrowid = None
            return self._cur
        self._cur.execute("SAVEPOINT ng_stmt")
        try:
            if params is None:
                self._cur.execute(s)
            else:
                self._cur.execute(s, params)
            self._cur.execute("RELEASE SAVEPOINT ng_stmt")
        except Exception:
            try:
                self._cur.execute("ROLLBACK TO SAVEPOINT ng_stmt")
                self._cur.execute("RELEASE SAVEPOINT ng_stmt")
            except Exception:
                pass
            raise
        self._lastrowid = None
        return self._cur

    def executemany(self, sql, seq):
        s = _ddl_postgres((sql or "").strip())
        s, _ = self._preparar(s, None)
        return self._cur.executemany(s, seq)

    def executescript(self, script):
        """Splits a script on ';' and runs each statement (SQLite emulation)."""
        for stmt in (script or "").split(";"):
            if stmt.strip():
                self.execute(stmt)

    @property
    def lastrowid(self):
        return self._lastrowid

    @property
    def rowcount(self):
        return self._cur.rowcount

    @property
    def description(self):
        return self._cur.description

    def _normalizar_valor(self, v):
        """Converts Postgres datetime/date to string (SQLite-compatible)."""
        if isinstance(v, datetime):
            return v.strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(v, date):
            return v.isoformat()
        return v

    def _normalizar_linha(self, linha):
        if linha is None:
            return None
        if isinstance(linha, dict):
            return {k: self._normalizar_valor(v) for k, v in linha.items()}
        if isinstance(linha, (list, tuple)):
            return tuple(self._normalizar_valor(v) for v in linha)
        return self._normalizar_valor(linha)

    def fetchone(self):
        return self._normalizar_linha(self._cur.fetchone())

    def fetchall(self):
        return [self._normalizar_linha(r) for r in self._cur.fetchall()]

    def fetchmany(self, size=None):
        return [self._normalizar_linha(r) for r in self._cur.fetchmany(size)]

    def __getattr__(self, item):
        return getattr(self._cur, item)


class _ConexaoPostgres:
    """psycopg2 connection proxy exposing the DBAPI used by the modules."""

    def __init__(self, raw):
        self._raw = raw

    def cursor(self):
        return _CursorPostgres(self._raw.cursor())

    def execute(self, sql, params=None):
        cur = self.cursor()
        cur.execute(sql, params)
        return cur

    def commit(self):
        return self._raw.commit()

    def rollback(self):
        return self._raw.rollback()

    def close(self):
        return self._raw.close()


def conexao(chave: str = "intranet"):
    """DBAPI-level connection for a module on the ACTIVE backend.

    sqlite: conexão sqlite3 (WAL) para o arquivo do módulo. postgres:
    conexão psycopg2 (via SQLAlchemy) com `search_path` no schema do módulo,
    envolvida num proxy que traduz `?`→`%s`, DDL SQLite e PRAGMA, e captura
    `lastrowid`. Devolve `None` em falha (fail-soft).
    """
    if sgbd_ativo() == "postgres":
        eng = obter_engine_modulo(chave)
        if eng is None:
            return None
        try:
            return _ConexaoPostgres(eng.raw_connection())
        except Exception as e:
            _log().exception(f"conexao('{chave}'): falha ao obter conexão "
                             f"PostgreSQL: {e}")
            return None
    # SQLite
    try:
        from mod_intranet.repositorio import caminho_db
        import sqlite3
        conn = sqlite3.connect(caminho_db(chave))
        conn.execute("PRAGMA journal_mode=WAL")
        return conn
    except Exception as e:
        _log().exception(f"conexao('{chave}'): falha ao abrir SQLite: {e}")
        return None


def conexao_central():
    """Shortcut: `conexao('intranet')` for the central module."""
    return conexao("intranet")
