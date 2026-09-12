"""Teste unitário da paridade SQLite/PostgreSQL (mod_intranet/banco_conexao.py).

Cobre a REGRA de paridade do AGENTS §4 sem exigir Postgres vivo:
- `sgbd_ativo`/`config_backend` (sqlite forçado via INTRANET_FORCE_SQLITE);
- `eh_chave_modulo`, `banco_modulo`, `_url_com_banco`;
- `_CursorPostgres._preparar` (datetime→LOCALTIMESTAMP/CURRENT_TIMESTAMP,
  GROUP_CONCAT→STRING_AGG, INSERT OR IGNORE→ON CONFLICT, ?→%s);
- `_CursorPostgres._normalizar_valor/_normalizar_linha` (datetime→str);
- `_ddl_postgres` (AUTOINCREMENT, INTEGER PK→SERIAL, BLOB→BYTEA,
  DATETIME→TIMESTAMP, passthrough não-CREATE);
- `conexao('intranet')` SQLite com PRAGMA WAL (somente leitura: PRAGMA +
  SELECT 1 — não escreve no banco de produção).

Execute: .venv/bin/python assets/test/test_banco_conexao.py
"""
import os
import sys
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

os.environ["INTRANET_FORCE_SQLITE"] = "1"

from mod_intranet import banco_conexao as bc  # noqa: E402

_OK = 0
_TOTAL = 0


def check(cond, msg):
    global _OK, _TOTAL
    _TOTAL += 1
    if cond:
        _OK += 1
        print(f"  OK [{_OK}] {msg}")
    else:
        print(f"  FALHOU [{_TOTAL - _OK}] {msg}")


print("INICIANDO TESTES — banco_conexao (paridade SQLite/PostgreSQL)")
try:
    bc._sgbd_ativo_cached.cache_clear()
except Exception:
    pass

# ---------- backend ativo ----------
print("-- backend --")
check(bc.sgbd_ativo() == "sqlite",
      "sgbd_ativo é sqlite com INTRANET_FORCE_SQLITE=1")
cfg = bc.config_backend()
check(isinstance(cfg, dict) and cfg.get("banco_tipo") == "sqlite",
      "config_backend reflete o backend sqlite")
check(bc.eh_chave_modulo("blog") is True,
      "eh_chave_modulo reconhece chave de módulo")
check(bc.eh_chave_modulo("modulo_que_nao_existe") is False,
      "eh_chave_modulo rejeita chave desconhecida")
check(bc.banco_modulo("blog") == "db_mod_blog",
      "banco_modulo mapeia blog -> db_mod_blog")
check(bc._url_com_banco("postgresql://h:5432/intranet", "db_mod_blog")
      == "postgresql://h:5432/db_mod_blog",
      "_url_com_banco troca o database do módulo na URL")

# ---------- _preparar (tradução SQLite -> Postgres) ----------
print("-- _CursorPostgres._preparar --")
prep = bc._CursorPostgres._preparar
s, p = prep("SELECT datetime('now')", None)
check(s == "SELECT CURRENT_TIMESTAMP" and p is None,
      "datetime('now') vira CURRENT_TIMESTAMP")
s, p = prep("SELECT datetime('now','localtime')", None)
check(s == "SELECT LOCALTIMESTAMP",
      "datetime localtime vira LOCALTIMESTAMP")
s, p = prep("SELECT GROUP_CONCAT(nome, ', ') FROM t", None)
check(s == "SELECT STRING_AGG(nome, ', ') FROM t",
      "GROUP_CONCAT vira STRING_AGG")
s, p = prep("INSERT OR IGNORE INTO t(a) VALUES (?)", (1,))
check(s == "INSERT INTO t(a) VALUES (%s) ON CONFLICT DO NOTHING"
      and p == (1,),
      "INSERT OR IGNORE vira INSERT ... ON CONFLICT DO NOTHING + %s")
s, p = prep("SELECT * FROM t WHERE a=? AND b=?", (1, 2))
check(s == "SELECT * FROM t WHERE a=%s AND b=%s",
      "placeholders ? viram %s com params tupla")
s, p = prep("SELECT 1", None)
check(s == "SELECT 1", "SQL sem tradução passa intacto")

# ---------- normalização datetime -> str ----------
print("-- normalização de valores --")
cur = bc._CursorPostgres.__new__(bc._CursorPostgres)
check(cur._normalizar_valor(datetime(2026, 9, 12, 8, 30, 0))
      == "2026-09-12 08:30:00",
      "datetime vira string SQLite-compatível")
check(cur._normalizar_valor(date(2026, 9, 12)) == "2026-09-12",
      "date vira ISO")
check(cur._normalizar_valor(42) == 42 and cur._normalizar_valor(None) is None,
      "int/None passam intactos")
check(cur._normalizar_linha(None) is None,
      "_normalizar_linha preserva None")
ln = cur._normalizar_linha({"quando": datetime(2026, 1, 2, 3, 4, 5), "n": 1})
check(ln == {"quando": "2026-01-02 03:04:05", "n": 1},
      "_normalizar_linha normaliza dict")
check(cur._normalizar_linha((datetime(2026, 1, 2, 0, 0, 0),)) == ("2026-01-02 00:00:00",),
      "_normalizar_linha normaliza tupla")

# ---------- _ddl_postgres ----------
print("-- _ddl_postgres --")
ddl = bc._ddl_postgres(
    "CREATE TABLE IF NOT EXISTS t (id INTEGER PRIMARY KEY AUTOINCREMENT, "
    "dados BLOB, quando DATETIME)")
check("SERIAL PRIMARY KEY" in ddl and "AUTOINCREMENT" not in ddl
      and "BYTEA" in ddl and "TIMESTAMP" in ddl,
      "DDL SQLite traduzido (SERIAL/BYTEA/TIMESTAMP, sem AUTOINCREMENT)")
check(bc._ddl_postgres("SELECT 1") == "SELECT 1",
      "não-CREATE passa intacto")
check("REFERENCES" not in bc._ddl_postgres(
    "CREATE TABLE t (a INTEGER REFERENCES outra(id))"),
    "REFERENCES inline removido (integridade no aplicativo)")

# ---------- conexão SQLite real (somente leitura) ----------
print("-- conexao sqlite --")
conn = bc.conexao("intranet")
check(conn is not None, "conexao('intranet') abre no backend sqlite")
if conn is not None:
    try:
        modo = conn.execute("PRAGMA journal_mode").fetchone()[0]
        check(str(modo).lower() == "wal",
              "conexão aplica PRAGMA journal_mode=WAL")
        check(conn.execute("SELECT 1").fetchone()[0] == 1,
              "SELECT 1 responde na conexão do módulo")
    finally:
        conn.close()
check(bc.conexao_central() is not None, "conexao_central abre")
try:
    bc.conexao_central().close()
except Exception:
    pass

print(f"RESULTADO: {_OK} OK, {_TOTAL - _OK} falha(s) de {_TOTAL} verificações")
sys.exit(0 if _OK == _TOTAL else 1)
