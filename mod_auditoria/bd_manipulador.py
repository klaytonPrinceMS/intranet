"""Audit module — exclusive database (db_mod_auditoria.db) with one table per module.

Módulo Auditoria — banco exclusivo (db_mod_auditoria.db) com tabela por módulo.

Cada módulo que grava auditoria tem sua própria tabela:
  tb_auditoria_<modulo_sanitizado>
A descoberta é automática: a tela lista todas as tabelas encontradas.
"""
import os
import time

from mod_intranet import observabilidade

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_AUDITORIA_PATH = os.path.join(BASE_DIR, "db_mod_auditoria.db")

log = observabilidade.get_logger("auditoria")

# Cache de tabelas já garantidas nesta sessão: evita DDL+commit por escrita
# (janela de lock). Invalidado se o INSERT falhar com "no such table".
_TABELAS_GARANTIDAS: set = set()

# Tentativas de commit em caso de contenção SQLite ("database is locked").
_TENTATIVAS_COMMIT = 3


def _sgbd() -> str:
    """Devolve o SGBD ativo ('sqlite'|'postgres') com fallback seguro."""
    try:
        from mod_intranet.banco_conexao import sgbd_ativo
        atual = sgbd_ativo()
        return atual if atual in ("sqlite", "postgres") else "sqlite"
    except Exception:
        return "sqlite"


def _commit_com_retry(conn, contexto: str = "") -> bool:
    """Commit com retry 3x em 'database is locked'; rollback seguro."""
    try:
        ultimo_erro = None
        for tentativa in range(1, _TENTATIVAS_COMMIT + 1):
            try:
                conn.commit()
                return True
            except Exception as e:
                ultimo_erro = e
                msg = str(e).lower()
                travou = ("locked" in msg or "busy" in msg or "timeout" in msg)
                if travou and tentativa < _TENTATIVAS_COMMIT:
                    try:
                        time.sleep(0.05 * tentativa)
                    except Exception:
                        pass
                    continue
                try:
                    conn.rollback()
                except Exception:
                    pass
                log.exception(f"_commit_com_retry: falha no commit ({contexto}) | {e}")
                return False
        try:
            conn.rollback()
        except Exception:
            pass
        log.exception(f"_commit_com_retry: esgotadas tentativas ({contexto}) | {ultimo_erro}")
        return False
    except Exception as e:
        log.exception(f"_commit_com_retry: erro inesperado ({contexto}) | {e}")
        return False


def _tabela_existe(conn, nome: str) -> bool:
    """Verifica existência de tabela de forma portável SQLite↔PostgreSQL."""
    try:
        cur = conn.cursor()
        if _sgbd() == "postgres":
            cur.execute(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = current_schema() AND table_name = ?",
                (nome,),
            )
            existe = cur.fetchone() is not None
        else:
            cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (nome,),
            )
            existe = cur.fetchone() is not None
        return existe
    except Exception as e:
        log.exception(f"_tabela_existe: falha ao verificar {nome} | {e}")
        try:
            conn.rollback()
        except Exception:
            pass
        return False


def _sql_hora(coluna: str) -> str:
    """Expressão SQL portável para extrair 'HH:MI' de coluna timestamp."""
    try:
        if _sgbd() == "postgres":
            return f"to_char({coluna}, 'HH24:MI')"
        return f"strftime('%H:%M', {coluna})"
    except Exception as e:
        log.exception(f"_sql_hora: falha ao montar expressão | {e}")
        return f"strftime('%H:%M', {coluna})"


def _sql_data_formatada(coluna: str) -> str:
    """Expressão SQL portável para formatar timestamp em 'dd/mm/AAAA HH:MM:SS'."""
    try:
        if _sgbd() == "postgres":
            return f"to_char({coluna}, 'DD/MM/YYYY HH24:MI:SS')"
        return f"strftime('%d/%m/%Y %H:%M:%S', {coluna})"
    except Exception as e:
        log.exception(f"_sql_data_formatada: falha ao montar expressão | {e}")
        return f"strftime('%d/%m/%Y %H:%M:%S', {coluna})"


def _nome_tabela(modulo: str) -> str:
    """Returns the audit table name for a module (`tb_auditoria_<modulo>`).

    Sanitiza o nome do módulo substituindo hífens por sublinhado, pois o
    identificador de tabela SQLite não aceita hífen. Ex.: `edit-pdf` →
    `tb_auditoria_edit_pdf`."""
    return f"tb_auditoria_{modulo.replace('-', '_')}"


def get_auditoria_connection():
    """Opens a connection to the exclusive audit database (WAL).

    Conexão com o banco de auditoria via `banco_conexao.conexao` — SQLite
    (db_mod_auditoria.db, WAL) ou PostgreSQL (schema `auditoria`). Todas as
    leituras/escritas da auditoria passam por aqui."""
    try:
        from mod_intranet.banco_conexao import conexao
        conn = conexao("auditoria")
        if conn is None:
            raise RuntimeError("Falha ao abrir conexão do módulo Auditoria")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn
    except Exception as e:
        log.exception(f"get_auditoria_connection: falha ao abrir conexão | {e}")
        raise


def init_db_auditoria():
    """Creates the audit metadata table (idempotent bootstrap).

    Cria `tb_auditoria_meta` (módulo → nome, data de criação) e
    também garante a tabela e índices de auditoria do módulo
    `intranet` (tb_auditoria_intranet) para que os testes possam
    verificar os índices imediatamente. Executado no import do
    módulo e pelo bootstrap central; nunca apaga dados."""
    try:
        conn = get_auditoria_connection()
    except Exception:
        log.exception("init_db_auditoria: falha ao abrir conexão")
        return
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tb_auditoria_meta (
                modulo TEXT PRIMARY KEY,
                nome TEXT NOT NULL,
                criada_em TEXT DEFAULT (datetime('now','localtime'))
            )
        """)
        # Garante a tabela e índices do módulo intranet para testes
        _garantir_tabela_auditoria(conn, "tb_auditoria_intranet", "intranet")
        conn.commit()
    except Exception:
        log.exception("init_db_auditoria: falha ao criar tb_auditoria_meta")
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _garantir_tabela_auditoria(conn, tabela: str, modulo: str = ""):
    """Creates the per-module audit table and its indexes if missing.

    Garante a existência da tabela `tb_auditoria_<modulo>` (idempotente) com
    as colunas de rastreabilidade LGPD (usuario, modulo, acao, descricao,
    timestamp, hash_arquivo, ip, user_agent, client_hostname), cria os índices
    (modulo, usuario, timestamp) e registra o módulo em `tb_auditoria_meta`.
    """
    try:
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
        """)  # nosec B608 — tabela de _nome_tabela(), sanitizada
        cur.executescript(f"""
            CREATE INDEX IF NOT EXISTS idx_aud_{tabela}_modulo ON {tabela} (modulo);
            CREATE INDEX IF NOT EXISTS idx_aud_{tabela}_usuario ON {tabela} (usuario);
            CREATE INDEX IF NOT EXISTS idx_aud_{tabela}_timestamp ON {tabela} (timestamp);
        """)  # nosec B608 — tabela de _nome_tabela(), sanitizada
        if modulo:
            try:
                cur.execute(
                    "INSERT OR IGNORE INTO tb_auditoria_meta (modulo, nome) VALUES (?, ?)",
                    (modulo, modulo),
                )
            except Exception:
                log.warning(f"_garantir_tabela_auditoria: falha ao registrar meta de {modulo}")
        _commit_com_retry(conn, f"garantir {tabela}")
    except Exception as e:
        log.exception(f"_garantir_tabela_auditoria: falha ao garantir {tabela} | {e}")
        try:
            conn.rollback()
        except Exception:
            pass
        raise


def get_tabelas_auditoria():
    """Lists the per-module audit tables found in the audit database.

    Retorna os nomes de todas as tabelas `tb_auditoria_*` (exceto a de
    metadados) existentes em `db_mod_auditoria.db` — a descoberta é
    automática, então novos módulos aparecem sem edição neste módulo."""
    try:
        conn = get_auditoria_connection()
    except Exception:
        log.exception("get_tabelas_auditoria: falha ao abrir conexão")
        return []
    try:
        cur = conn.cursor()
        # Fonte primária (portável nos dois backends): tb_auditoria_meta.
        try:
            cur.execute("SELECT modulo FROM tb_auditoria_meta ORDER BY nome")
            linhas_meta = cur.fetchall()
            tabelas_meta = [_nome_tabela(r[0]) for r in linhas_meta if r and r[0]]
            if tabelas_meta:
                return tabelas_meta
        except Exception:
            log.exception("get_tabelas_auditoria: falha ao ler tb_auditoria_meta; usando fallback")
            try:
                conn.rollback()
            except Exception:
                pass
        # Fallback por backend: information_schema no PG, sqlite_master no SQLite.
        # (SELECT em sqlite_master no PG via proxy retorna vazio — por isso o
        # fallback explícito.)
        try:
            if _sgbd() == "postgres":
                cur.execute(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = current_schema() "
                    "AND table_name LIKE 'tb_auditoria_%' "
                    "AND table_name <> 'tb_auditoria_meta'"
                )
                return [row[0] for row in cur.fetchall()]
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'tb_auditoria_%' AND name != 'tb_auditoria_meta'")
            return [row[0] for row in cur.fetchall()]
        except Exception:
            log.exception("get_tabelas_auditoria: falha no fallback por backend")
            return []
    except Exception:
        log.exception("get_tabelas_auditoria: falha ao listar tabelas")
        return []
    finally:
        try:
            conn.close()
        except Exception:
            pass


def get_modulos_com_auditoria():
    """Lists modules that produce audit records: [(modulo, tabela)].

    Lê `tb_auditoria_meta` (ordem alfabética por nome). Em falha de leitura,
    faz fallback descobrindo as tabelas existentes via `get_tabelas_auditoria`
    e extraindo a chave do módulo do próprio nome da tabela."""
    try:
        conn = get_auditoria_connection()
    except Exception:
        log.exception("get_modulos_com_auditoria: falha ao abrir conexão; usando descoberta")
        try:
            tabelas = get_tabelas_auditoria()
        except Exception:
            log.exception("get_modulos_com_auditoria: falha na descoberta de tabelas")
            return []
        return [(_extrair_modulo(t), t) for t in tabelas]
    try:
        cur = conn.cursor()
        cur.execute("SELECT modulo, nome FROM tb_auditoria_meta ORDER BY nome")
        saida = [(modulo, _nome_tabela(modulo)) for modulo, nome in cur.fetchall()]
    except Exception:
        log.exception("get_modulos_com_auditoria: falha ao ler meta; usando descoberta")
        saida = None
    finally:
        try:
            conn.close()
        except Exception:
            pass
    if saida is not None:
        return saida
    try:
        tabelas = get_tabelas_auditoria()
    except Exception:
        log.exception("get_modulos_com_auditoria: falha na descoberta de tabelas")
        return []
    return [(_extrair_modulo(t), t) for t in tabelas]


def _extrair_modulo(tabela: str) -> str:
    """Extracts the module key from an audit table name (reverse of _nome_tabela).

    Extrai a chave do módulo a partir do nome da tabela de auditoria
    (inverso de `_nome_tabela`)."""
    return tabela.replace("tb_auditoria_", "").replace("_", "-")


def registrar_auditoria(usuario, modulo, acao, descricao, hash_arquivo=None,
                        ip=None, user_agent=None, client_hostname=None,
                        timestamp=None):
    """Appends one action to the module's exclusive table in db_mod_auditoria.db.

    Grava a ação na tabela exclusiva do módulo em db_mod_auditoria.db.

    A tabela é criada automaticamente (e registrada em tb_auditoria_meta)
    caso ainda não exista, de modo que novos módulos passam a auditar
    sem nenhuma edição no módulo de auditoria.
    """
    if timestamp is None:
        import datetime as _dt
        timestamp = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        conn = get_auditoria_connection()
    except Exception:
        log.exception(f"registrar_auditoria: falha ao abrir conexão ({modulo}/{acao})")
        return
    try:
        tabela = _nome_tabela(modulo)
        # DDL só quando a tabela ainda não foi garantida nesta sessão
        # (busy_timeout herdado de banco_conexao.conexao; transação curta).
        if tabela not in _TABELAS_GARANTIDAS:
            _garantir_tabela_auditoria(conn, tabela, modulo)
            _TABELAS_GARANTIDAS.add(tabela)
        cur = conn.cursor()
        try:
            cur.execute(
                f"INSERT INTO {tabela} (usuario, modulo, acao, descricao, hash_arquivo, ip, user_agent, client_hostname, timestamp)"
                f" VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",  # nosec B608 — tabela de _nome_tabela(), sanitizada
                (usuario, modulo, acao, descricao, hash_arquivo, ip, user_agent,
                 client_hostname, timestamp),
            )
        except Exception as e:
            # Se a tabela sumiu no meio do caminho, invalida o cache e
            # tenta garantir + reinserir uma vez (sem perder a trilha LGPD).
            msg = str(e).lower()
            if "no such table" in msg or "does not exist" in msg or "undefined_table" in msg:
                log.warning(f"registrar_auditoria: tabela ausente, regarantindo {tabela}")
                try:
                    conn.rollback()
                except Exception:
                    pass
                _TABELAS_GARANTIDAS.discard(tabela)
                _garantir_tabela_auditoria(conn, tabela, modulo)
                _TABELAS_GARANTIDAS.add(tabela)
                cur = conn.cursor()
                cur.execute(
                    f"INSERT INTO {tabela} (usuario, modulo, acao, descricao, hash_arquivo, ip, user_agent, client_hostname, timestamp)"
                    f" VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",  # nosec B608 — tabela de _nome_tabela(), sanitizada
                    (usuario, modulo, acao, descricao, hash_arquivo, ip, user_agent,
                     client_hostname, timestamp),
                )
            else:
                raise
        _commit_com_retry(conn, f"registrar {modulo}/{acao}")
    except Exception:
        log.exception(f"registrar_auditoria: falha ao gravar ({modulo}/{acao})")
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        try:
            conn.close()
        except Exception:
            pass


def contar_registros(tabela=None):
    """Counts audit records in one table or across all of them.

    Total de registros de auditoria: se `tabela` for informada, conta apenas
    nela; caso contrário soma o total de todas as tabelas por módulo (falhas
    individuais são ignoradas). Usada pelo resumo do dashboard."""
    try:
        conn = get_auditoria_connection()
    except Exception:
        log.exception("contar_registros: falha ao abrir conexão")
        return 0
    try:
        cur = conn.cursor()
        if tabela:
            cur.execute(f"SELECT COUNT(*) FROM {tabela}")  # nosec B608 — tabela de get_tabelas_auditoria(), whitelistada
            return cur.fetchone()[0]
        total = 0
        for tbl in get_tabelas_auditoria():
            try:
                cur.execute(f"SELECT COUNT(*) FROM {tbl}")  # nosec B608 — tabela de get_tabelas_auditoria(), whitelistada
                total += cur.fetchone()[0]
            except Exception:
                log.exception(f"contar_registros: falha ao contar {tbl}")
                try:
                    conn.rollback()
                except Exception:
                    pass
                continue
        return total
    except Exception:
        log.exception("contar_registros: falha ao contar registros")
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def podar_registros(dias):
    """Remove registros mais antigos que `dias` em todas as tabelas de auditoria.

    Aplica a política LGPD de retenção de forma uniforme a cada tabela por
    módulo. Retorna o número total de registros removidos.
    """
    import datetime as _dt
    removidos = 0
    try:
        conn = get_auditoria_connection()
    except Exception:
        log.exception("podar_registros: falha ao abrir conexão")
        return removidos
    try:
        cur = conn.cursor()
        for tbl in get_tabelas_auditoria():
            try:
                cur.execute(
                    f"DELETE FROM {tbl} "  # nosec B608 — tabela de get_tabelas_auditoria(), whitelistada
                    "WHERE timestamp < datetime('now','localtime', ?)",
                    (f"-{int(dias)} days",),
                )
                removidos += cur.rowcount
            except Exception:
                log.exception(f"podar_registros: falha ao podar {tbl}")
                try:
                    conn.rollback()
                except Exception:
                    pass
                continue
        _commit_com_retry(conn, "podar_registros")
    except Exception:
        log.exception("podar_registros: falha ao podar registros")
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return removidos


def buscar_logs(tabela=None, filtro_usuario="", filtro_modulo="",
                filtro_acao="", filtro_hora="", data_inicio="", data_fim="",
                pagina=1, limite_sql=1000):
    """Searches audit records with filters and server-side pagination.

    Consulta da trilha de auditoria com filtros (usuário LIKE, módulo exato,
    ação LIKE, hora `strftime('%H:%M')`, intervalo de datas) e paginação
    server-side (`LIMIT ? OFFSET ?`). Sem `tabela`, une TODAS as tabelas por
    módulo via `UNION ALL` (fallback quando `tb_auditoria_meta` falha).
    Retorna `(linhas, total)` — linhas com data já formatada `dd/mm/AAAA
    HH:MM:SS`."""
    try:
        conn = get_auditoria_connection()
    except Exception:
        log.exception("buscar_logs: falha ao abrir conexão")
        return [], 0
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
                where += f" AND {_sql_hora('timestamp')} LIKE ?"
                params.append(f"%{filtro_hora}%")
            if data_inicio:
                where += " AND timestamp >= ?"
                params.append(f"{data_inicio} 00:00:00")
            if data_fim:
                where += " AND timestamp <= ?"
                params.append(f"{data_fim} 23:59:59")

            cur = conn.cursor()
            cur.execute(f"SELECT COUNT(*) FROM {tabela}{where}", params)  # nosec B608 — tabela sanitizada, where com params
            total = cur.fetchone()[0]
            sql = (f"SELECT id, usuario, modulo, acao, descricao, hash_arquivo,"
                   f" {_sql_data_formatada('timestamp')}, ip, user_agent, client_hostname"
                   f" FROM {tabela}{where} ORDER BY id DESC LIMIT ? OFFSET ?")  # nosec B608 — tabela sanitizada, where com params
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
                where += f" AND {_sql_hora('sq.timestamp')} LIKE ?"
                params.append(f"%{filtro_hora}%")
            if data_inicio:
                where += " AND sq.timestamp >= ?"
                params.append(f"{data_inicio} 00:00:00")
            if data_fim:
                where += " AND sq.timestamp <= ?"
                params.append(f"{data_fim} 23:59:59")

            inner_parts = []
            for modulo, tbl in tabelas_info:
                inner_parts.append(f"SELECT id, usuario, modulo, acao, descricao, hash_arquivo, timestamp, ip, user_agent, client_hostname"  # nosec B608 — tabela de get_tabelas_auditoria(), whitelistada
                                   f" FROM {tbl}")  # nosec B608 — tabela de get_tabelas_auditoria(), whitelistada
            inner_sql = " UNION ALL ".join(inner_parts)
            count_sql = f"SELECT COUNT(*) FROM ({inner_sql}) AS sq{where}"  # nosec B608 — tabelas de get_tabelas_auditoria(), whitelistadas
            data_sql = (f"SELECT id, usuario, modulo, acao, descricao, hash_arquivo,"  # nosec B608 — tabelas de get_tabelas_auditoria(), whitelistadas
                        f" {_sql_data_formatada('sq.timestamp')}, ip, user_agent, client_hostname"
                        f" FROM ({inner_sql}) AS sq{where}"
                        f" ORDER BY sq.id DESC LIMIT ? OFFSET ?")
            cur = conn.cursor()
            cur.execute(count_sql, params)
            total = cur.fetchone()[0]
            cur.execute(data_sql, params + [limite_sql, offset])
            return cur.fetchall(), total
    except Exception:
        log.exception("buscar_logs: falha ao buscar registros")
        return [], 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _remover_legado_central():
    """Drops the legacy central tb_auditoria table after migration.

    Remove a tabela tb_auditoria legada do banco central.

    Após a auditoria migrar para o banco exclusivo (db_mod_auditoria.db, uma
    tabela por módulo), a tb_auditoria central virou resíduo e é descartada.
    """
    from mod_intranet.bd_conexao import get_connection as _get_central_conn
    try:
        conn = _get_central_conn()
        try:
            conn.execute("DROP TABLE IF EXISTS tb_auditoria")
            conn.commit()
        finally:
            try:
                conn.close()
            except Exception:
                pass
    except Exception:
        log.exception("_remover_legado_central: falha ao remover tb_auditoria legada")


def migrar_dados_existentes(forcar=False):
    """Migrates rows from the legacy central tb_auditoria to per-module tables.

    Migra dados da antiga tb_auditoria em db_mod_intranet.db para as novas
    tabelas por módulo.

    Idempotente: só roda uma única vez (marcador persistido na central,
    'auditoria_migracao_concluida' = '1'). Use forcar=True para forçar uma
    nova rodada (p.ex. em testes ou manutenção). Ao concluir, a tb_auditoria
    legada do banco central é removida.
    """
    try:
        return _migrar_dados_existentes_seguro(forcar)
    except Exception:
        log.exception("migrar_dados_existentes: falha na migração")
        return 0


def _migrar_dados_existentes_seguro(forcar=False):
    """Body of `migrar_dados_existentes`, isolated so the entry point can protect it.

    Corpo de `migrar_dados_existentes`, isolado para que o ponto de entrada
    possa protegê-lo com try/except sem derrubar o bootstrap."""
    from mod_intranet.bd_conexao import get_config, set_config
    from mod_intranet.bd_conexao import get_connection as _get_central_conn
    if not forcar and get_config("auditoria_migracao_concluida", "") == "1":
        _remover_legado_central()
        return 0
    central_conn = _get_central_conn()
    try:
        # Portável SQLite↔PG: information_schema no PG, sqlite_master no SQLite
        # (SELECT em sqlite_master no PG via proxy retorna vazio).
        if not _tabela_existe(central_conn, "tb_auditoria"):
            return 0
        cur_central = central_conn.cursor()
        try:
            cur_central.execute("SELECT COUNT(*) FROM tb_auditoria")
            total = cur_central.fetchone()[0]
        except Exception:
            log.exception("_migrar_dados_existentes_seguro: falha ao contar legado")
            try:
                central_conn.rollback()
            except Exception:
                pass
            return 0
        if total == 0:
            return 0
        cur_central.execute("SELECT usuario, modulo, acao, descricao, timestamp, hash_arquivo, ip, user_agent, client_hostname FROM tb_auditoria")
        rows = cur_central.fetchall()
    except Exception:
        log.exception("_migrar_dados_existentes_seguro: falha ao ler legado central")
        return 0
    finally:
        try:
            central_conn.close()
        except Exception:
            pass

    audit_conn = get_auditoria_connection()
    try:
        if not _tabela_existe(audit_conn, "tb_auditoria_meta"):
            init_db_auditoria()
        cur_audit = audit_conn.cursor()

        modulos_por_tabela = {}
        for usuario, modulo, acao, descricao, timestamp, hash_arquivo, ip, user_agent, client_hostname in rows:
            tabela = _nome_tabela(modulo)
            if tabela not in modulos_por_tabela:
                modulos_por_tabela[tabela] = modulo
                _garantir_tabela_auditoria(audit_conn, tabela, modulo)
            cur_audit.execute(
                 f"INSERT INTO {tabela} (usuario, modulo, acao, descricao, timestamp, hash_arquivo, ip, user_agent, client_hostname) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",  # nosec B608 — tabela de _nome_tabela(), sanitizada
                 (usuario, modulo, acao, descricao, timestamp, hash_arquivo, ip, user_agent, client_hostname),
             )
        _commit_com_retry(audit_conn, "migrar_dados_existentes")
    except Exception:
        log.exception("_migrar_dados_existentes_seguro: falha ao gravar no banco de auditoria")
        try:
            audit_conn.rollback()
        except Exception:
            pass
        try:
            audit_conn.close()
        except Exception:
            pass
        return 0
    finally:
        try:
            audit_conn.close()
        except Exception:
            pass
    set_config("auditoria_migracao_concluida", "1")
    _remover_legado_central()
    return len(rows)


def _semear_versao_modulo():
    """Seeds the module version key (`versao_modulo:auditoria`) in tb_config.

    Semeia a chave de versão do módulo (`versao_modulo:auditoria`) na tb_config."""
    try:
        from mod_intranet.bd_conexao import get_config, set_config
        set_config("versao_modulo:auditoria", "1.0.260908")
    except Exception:
        log.exception("_semear_versao_modulo: falha ao semear versão do módulo")


try:
    from mod_intranet.bd_manipulador import registrar_hook_auditoria
    registrar_hook_auditoria(registrar_auditoria)
except Exception:
    log.exception("bootstrap: falha ao registrar hook de auditoria")
try:
    init_db_auditoria()
except Exception:
    log.exception("bootstrap: falha no init_db_auditoria")
try:
    _semear_versao_modulo()
except Exception:
    log.exception("bootstrap: falha ao semear versão do módulo")