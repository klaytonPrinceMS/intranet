"""Módulo Auditoria — banco exclusivo (db_mod_auditoria.db) com tabela por módulo.

Cada módulo que grava auditoria tem sua própria tabela:
  tb_auditoria_<modulo_sanitizado>
A descoberta é automática: a tela lista todas as tabelas encontradas.
"""
import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_AUDITORIA_PATH = os.path.join(BASE_DIR, "db_mod_auditoria.db")


def _nome_tabela(modulo: str) -> str:
    return f"tb_auditoria_{modulo.replace('-', '_')}"


def get_auditoria_connection():
    conn = sqlite3.connect(DB_AUDITORIA_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_db_auditoria():
    conn = get_auditoria_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tb_auditoria_meta (
                modulo TEXT PRIMARY KEY,
                nome TEXT NOT NULL,
                criada_em TEXT DEFAULT (datetime('now','localtime'))
            )
        """)
        conn.commit()
    finally:
        conn.close()


def _garantir_tabela_auditoria(conn, tabela: str, modulo: str = ""):
    cur = conn.cursor()
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {tabela} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT NOT NULL,
            modulo TEXT NOT NULL,
            acao TEXT NOT NULL,
            descricao TEXT,
            timestamp DATETIME DEFAULT (datetime('now','localtime')),
            hash_arquivo TEXT,
            ip TEXT,
            user_agent TEXT,
            client_hostname TEXT
        )
    """)
    cur.executescript(f"""
        CREATE INDEX IF NOT EXISTS idx_aud_{tabela}_modulo ON {tabela} (modulo);
        CREATE INDEX IF NOT EXISTS idx_aud_{tabela}_usuario ON {tabela} (usuario);
        CREATE INDEX IF NOT EXISTS idx_aud_{tabela}_timestamp ON {tabela} (timestamp);
    """)
    if modulo:
        try:
            cur.execute(
                "INSERT OR IGNORE INTO tb_auditoria_meta (modulo, nome) VALUES (?, ?)",
                (modulo, modulo),
            )
        except Exception:
            pass
    conn.commit()


def get_tabelas_auditoria():
    conn = get_auditoria_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'tb_auditoria_%' AND name != 'tb_auditoria_meta'")
        return [row[0] for row in cur.fetchall()]
    finally:
        conn.close()


def get_modulos_com_auditoria():
    conn = get_auditoria_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT modulo, nome FROM tb_auditoria_meta ORDER BY nome")
        return [(modulo, _nome_tabela(modulo)) for modulo, nome in cur.fetchall()]
    except Exception:
        conn.close()
        tabelas = get_tabelas_auditoria()
        return [(_extrair_modulo(t), t) for t in tabelas]


def _extrair_modulo(tabela: str) -> str:
    return tabela.replace("tb_auditoria_", "").replace("_", "-")


def registrar_auditoria(usuario, modulo, acao, descricao, hash_arquivo=None,
                        ip=None, user_agent=None, client_hostname=None,
                        timestamp=None):
    """Grava a ação na tabela exclusiva do módulo em db_mod_auditoria.db.

    A tabela é criada automaticamente (e registrada em tb_auditoria_meta)
    caso ainda não exista, de modo que novos módulos passam a auditar
    sem nenhuma edição no módulo de auditoria.
    """
    if timestamp is None:
        import datetime as _dt
        timestamp = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_auditoria_connection()
    try:
        tabela = _nome_tabela(modulo)
        _garantir_tabela_auditoria(conn, tabela, modulo)
        cur = conn.cursor()
        cur.execute(
            f"INSERT INTO {tabela} (usuario, modulo, acao, descricao, hash_arquivo, ip, user_agent, client_hostname, timestamp)"
            f" VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (usuario, modulo, acao, descricao, hash_arquivo, ip, user_agent,
             client_hostname, timestamp),
        )
        conn.commit()
    finally:
        conn.close()


def contar_registros(tabela=None):
    """Total de registros no banco de auditoria (uma tabela ou todas)."""
    conn = get_auditoria_connection()
    try:
        cur = conn.cursor()
        if tabela:
            cur.execute(f"SELECT COUNT(*) FROM {tabela}")
            return cur.fetchone()[0]
        total = 0
        for tbl in get_tabelas_auditoria():
            try:
                cur.execute(f"SELECT COUNT(*) FROM {tbl}")
                total += cur.fetchone()[0]
            except Exception:
                continue
        return total
    finally:
        conn.close()


def podar_registros(dias):
    """Remove registros mais antigos que `dias` em todas as tabelas de auditoria.

    Aplica a política LGPD de retenção de forma uniforme a cada tabela por
    módulo. Retorna o número total de registros removidos.
    """
    import datetime as _dt
    removidos = 0
    conn = get_auditoria_connection()
    try:
        cur = conn.cursor()
        for tbl in get_tabelas_auditoria():
            try:
                cur.execute(
                    f"DELETE FROM {tbl} "
                    "WHERE timestamp < datetime('now','localtime', ?)",
                    (f"-{int(dias)} days",),
                )
                removidos += cur.rowcount
            except Exception:
                continue
        conn.commit()
    finally:
        conn.close()
    return removidos


def buscar_logs(tabela=None, filtro_usuario="", filtro_modulo="",
                filtro_acao="", filtro_hora="", data_inicio="", data_fim="",
                pagina=1, limite_sql=1000):
    conn = get_auditoria_connection()
    try:
        offset = max(0, (int(pagina) - 1) * limite_sql)

        if tabela:
            where = " WHERE 1=1"
            params = []
            if filtro_usuario:
                where += " AND usuario LIKE ?"
                params.append(f"%{filtro_usuario}%")
            if filtro_modulo:
                where += " AND modulo = ?"
                params.append(filtro_modulo)
            if filtro_acao:
                where += " AND acao LIKE ?"
                params.append(f"%{filtro_acao}%")
            if filtro_hora:
                where += " AND strftime('%H:%M', timestamp) LIKE ?"
                params.append(f"%{filtro_hora}%")
            if data_inicio:
                where += " AND timestamp >= ?"
                params.append(f"{data_inicio} 00:00:00")
            if data_fim:
                where += " AND timestamp <= ?"
                params.append(f"{data_fim} 23:59:59")

            cur = conn.cursor()
            cur.execute(f"SELECT COUNT(*) FROM {tabela}{where}", params)
            total = cur.fetchone()[0]
            sql = (f"SELECT id, usuario, modulo, acao, descricao, hash_arquivo,"
                   f" strftime('%d/%m/%Y %H:%M:%S', timestamp), ip, user_agent, client_hostname"
                   f" FROM {tabela}{where} ORDER BY id DESC LIMIT ? OFFSET ?")
            cur.execute(sql, params + [limite_sql, offset])
            return cur.fetchall(), total
        else:
            tabelas_info = get_modulos_com_auditoria()
            if not tabelas_info:
                return [], 0
            where = " WHERE 1=1"
            params = []
            if filtro_usuario:
                where += " AND sq.usuario LIKE ?"
                params.append(f"%{filtro_usuario}%")
            if filtro_modulo:
                where += " AND sq.modulo = ?"
                params.append(filtro_modulo)
            if filtro_acao:
                where += " AND sq.acao LIKE ?"
                params.append(f"%{filtro_acao}%")
            if filtro_hora:
                where += " AND strftime('%H:%M', sq.timestamp) LIKE ?"
                params.append(f"%{filtro_hora}%")
            if data_inicio:
                where += " AND sq.timestamp >= ?"
                params.append(f"{data_inicio} 00:00:00")
            if data_fim:
                where += " AND sq.timestamp <= ?"
                params.append(f"{data_fim} 23:59:59")

            inner_parts = []
            for modulo, tbl in tabelas_info:
                inner_parts.append(f"SELECT id, usuario, modulo, acao, descricao, hash_arquivo, timestamp, ip, user_agent, client_hostname"
                                   f" FROM {tbl}")
            inner_sql = " UNION ALL ".join(inner_parts)
            count_sql = f"SELECT COUNT(*) FROM ({inner_sql}) AS sq{where}"
            data_sql = (f"SELECT id, usuario, modulo, acao, descricao, hash_arquivo,"
                        f" strftime('%d/%m/%Y %H:%M:%S', sq.timestamp), ip, user_agent, client_hostname"
                        f" FROM ({inner_sql}) AS sq{where}"
                        f" ORDER BY sq.id DESC LIMIT ? OFFSET ?")
            cur = conn.cursor()
            cur.execute(count_sql, params)
            total = cur.fetchone()[0]
            cur.execute(data_sql, params + [limite_sql, offset])
            return cur.fetchall(), total
    finally:
        conn.close()


def _remover_legado_central():
    """Remove a tabela tb_auditoria legada do banco central.

    Após a auditoria migrar para o banco exclusivo (db_mod_auditoria.db, uma
    tabela por módulo), a tb_auditoria central virou resíduo e é descartada.
    """
    from mod_intranet.conexao_bd import get_connection as _get_central_conn
    try:
        conn = _get_central_conn()
        try:
            conn.execute("DROP TABLE IF EXISTS tb_auditoria")
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass


def migrar_dados_existentes(forcar=False):
    """Migra dados da antiga tb_auditoria em db_mod_intranet.db para as novas
    tabelas por módulo.

    Idempotente: só roda uma única vez (marcador persistido na central,
    'auditoria_migracao_concluida' = '1'). Use forcar=True para forçar uma
    nova rodada (p.ex. em testes ou manutenção). Ao concluir, a tb_auditoria
    legada do banco central é removida.
    """
    from mod_intranet.conexao_bd import get_config, set_config
    from mod_intranet.conexao_bd import get_connection as _get_central_conn
    if not forcar and get_config("auditoria_migracao_concluida", "") == "1":
        _remover_legado_central()
        return 0
    central_conn = _get_central_conn()
    try:
        cur_central = central_conn.cursor()
        cur_central.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tb_auditoria'")
        if not cur_central.fetchone():
            return 0
        cur_central.execute("SELECT COUNT(*) FROM tb_auditoria")
        total = cur_central.fetchone()[0]
        if total == 0:
            return 0
        cur_central.execute("SELECT usuario, modulo, acao, descricao, timestamp, hash_arquivo, ip, user_agent, client_hostname FROM tb_auditoria")
        rows = cur_central.fetchall()
    finally:
        central_conn.close()

    audit_conn = get_auditoria_connection()
    try:
        cur_audit = audit_conn.cursor()
        cur_audit.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='tb_auditoria_meta'")
        if not cur_audit.fetchone():
            init_db_auditoria()

        modulos_por_tabela = {}
        for usuario, modulo, acao, descricao, timestamp, hash_arquivo, ip, user_agent, client_hostname in rows:
            tabela = _nome_tabela(modulo)
            if tabela not in modulos_por_tabela:
                modulos_por_tabela[tabela] = modulo
                _garantir_tabela_auditoria(audit_conn, tabela, modulo)
            cur_audit.execute(
                f"INSERT INTO {tabela} (usuario, modulo, acao, descricao, timestamp, hash_arquivo, ip, user_agent, client_hostname) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (usuario, modulo, acao, descricao, timestamp, hash_arquivo, ip, user_agent, client_hostname),
            )
        audit_conn.commit()
    finally:
        audit_conn.close()
    set_config("auditoria_migracao_concluida", "1")
    _remover_legado_central()
    return len(rows)


def _semear_versao_modulo():
    from mod_intranet.conexao_bd import get_config, set_config
    set_config("versao_modulo:auditoria", "1.0.260901")


init_db_auditoria()
_semear_versao_modulo()