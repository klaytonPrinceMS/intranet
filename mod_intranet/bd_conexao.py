"""Central database connection and configuration layer. Internally delegates
to `Repositorio` (SQLAlchemy ORM) while keeping raw sqlite3 `get_connection`
for backward compatibility.

Conexão e configurações centrais do Intranet (banco central db_mod_intranet.db).

Camada mais baixa: sem imports circulares — só os outros módulos dependem daqui.
Usa `Repositorio` (SQLAlchemy ORM) internamente para `get_config`/`set_config`;
mantém `get_connection` (sqlite3 raw) para compatibilidade com código
legado que ainda não foi migrado. Notificações pós-gravação (ex.: limpar
caches `lru_cache` de outros módulos) usam `registrar_hook_config` —
nunca import direto (nem lazy) de outro módulo aqui dentro.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

import sqlite3
from functools import lru_cache

_HOOKS_CONFIG = []  # lista de (fn, chaves_ou_None)


def registrar_hook_config(fn, apenas_chaves=None):
    """Registra fn() para rodar após cada gravação de config bem-sucedida.

    Usado por módulos com caches derivados de `tb_config` (ex.: tema,
    template de empenhos): em vez de `bd_conexao` importar o módulo
    (ciclo núcleo→módulo), o módulo se registra aqui no próprio import.
    `apenas_chaves` restringe o disparo (ex.: "empenhos_template_nome").
    Hooks nunca derrubam o `set_config` (cada um roda em try/except).
    """
    if isinstance(apenas_chaves, str):
        chaves = {apenas_chaves}
    elif apenas_chaves:
        chaves = set(apenas_chaves)
    else:
        chaves = None
    def _mesmo(a, b):
        return (getattr(a, "__func__", a) is getattr(b, "__func__", b)
                and getattr(a, "__self__", None) is getattr(b, "__self__", None))
    if callable(fn) and all(not _mesmo(f, fn) for f, _ in _HOOKS_CONFIG):
        _HOOKS_CONFIG.append((fn, chaves))

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
    # Documentação MkDocs — sobe no boot salvo docs_ativo=0 (admin religa sob demanda)
    "docs_ativo": "1",
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
    # Avisos do sistema (toasts): tempo de exibição em segundos (1-30, padrão 5)
    "notificacao_timeout": "5",
    # Card "Configurações gerais": intervalo do backup em horas e retenção de
    # sessão em dias. Viviam SÓ como literais espalhados (INSERT de banco novo
    # + `padrao=` da tela + dicionário do "Restaurar padrão"), então o card não
    # tinha fonte única de verdade e um padrão divergente quebrava a tela
    # quando a chave faltava no tb_config. Aqui ficam canônicos.
    "backup_interval_hours": "12",
    "sessao_retencao": "50",
    # Contador de acessos ao sistema (incrementado a cada login bem-sucedido)
    "contador_acessos_total": "0",
    "contador_acessos_inicio": "",
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
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES ('versao_sistema', '1.0.260913')")
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES ('cotadisco_global_gb', '10')")
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES ('backup_interval_hours', '12')")
    for _chave_mod, _ver in (
        ("usuarios", "1.0.260918"),
        ("auditoria", "1.0.260908"),
        ("editar_pdf", "1.0.260908"),
        ("empenhos", "1.0.260913"),
        ("blog", "1.0.260908"),
        ("solicita_impressao", "1.0.260913"),
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
    # Migração 260913 — solicita_impressao: seeds iniciais + bump de versão (sem reexecutar 260908)
    cur.execute("UPDATE tb_config SET valor='1.0.260913' "
                "WHERE chave='versao_modulo:solicita_impressao' AND valor != '1.0.260913'")
    # Migração 13/09/2026 — bump versão do módulo empenhos (padrão PIC + contagem padronizada + CSS docs)
    cur.execute("SELECT COUNT(*) FROM tb_config WHERE chave='migracao_versao_empenhos_260913'")
    if (cur.fetchone()[0] or 0) == 0:
        cur.execute("UPDATE tb_config SET valor='1.0.260913' WHERE chave='versao_modulo:empenhos'")
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES ('migracao_versao_empenhos_260913', '1') ON CONFLICT DO NOTHING")
    # Migração 13/09/2026 — bump versão intranet/sistema (contagem padronizada + PIC + CSS docs)
    cur.execute("SELECT COUNT(*) FROM tb_config WHERE chave='migracao_versao_intranet_260913'")
    if (cur.fetchone()[0] or 0) == 0:
        cur.execute("UPDATE tb_config SET valor='1.0.260913' WHERE chave='versao_sistema'")
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES ('versao_sistema', '1.0.260913') ON CONFLICT DO NOTHING")
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES ('versao_modulo:intranet', '1.0.260913') ON CONFLICT DO NOTHING")
        cur.execute("UPDATE tb_config SET valor='1.0.260913' WHERE chave='versao_modulo:intranet'")
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES ('migracao_versao_intranet_260913', '1') ON CONFLICT DO NOTHING")
    # Migração 18/09/2026 — bump versão do módulo usuarios (acesso padrão
    # comum em editar_pdf/empenhos/solicita_impressao, nova ordem dos
    # módulos, blog indesativável, senha provisória 123456 no cadastro)
    cur.execute("SELECT COUNT(*) FROM tb_config WHERE chave='migracao_versao_usuarios_260918'")
    if (cur.fetchone()[0] or 0) == 0:
        cur.execute("UPDATE tb_config SET valor='1.0.260918' WHERE chave='versao_modulo:usuarios'")
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES ('migracao_versao_usuarios_260918', '1') ON CONFLICT DO NOTHING")
    # Seed do contador de acessos (se ainda não existir) + data inicial da contagem
    try:
        cur.execute("SELECT valor FROM tb_config WHERE chave='contador_acessos_inicio'")
        row = cur.fetchone()
        if not row or not (row[0] or "").strip():
            import datetime as _dt
            hoje = _dt.datetime.now().strftime("%Y-%m-%d")
            cur.execute("INSERT INTO tb_config (chave, valor) VALUES ('contador_acessos_inicio', ?) ON CONFLICT DO NOTHING", (hoje,))
            cur.execute("UPDATE tb_config SET valor=? WHERE chave='contador_acessos_inicio' AND (valor IS NULL OR valor='')", (hoje,))
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES ('contador_acessos_total', '0') ON CONFLICT DO NOTHING")
    except Exception:
        pass
    conn.commit()
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()


def incrementar_contador_acessos() -> int:
    """Increments the global access counter — login-only, never navigation/refresh.

    EN: Centralized counter for **successful logins only** (not page navigations,
    refreshes or tab switches). Called exclusively in `main.tentar_login`
    after `autenticacao.registrar_login` validates credentials. Persists in
    `tb_config` (`contador_acessos_total` + `contador_acessos_inicio`) via
    `get_config`/`set_config` (which delegate to `Repositorio`/SQLAlchemy and
    then to `banco_conexao.conexao`). `main._orquestrar_resumo_dados` only
    reads (`get_config`). Previously incremented inline in `main`; now this
    function is the single source of truth. Fail-soft — returns `0` on error.
    Returns the new total.

    PT-BR: Incrementa o contador global de acessos — **apenas logins**, nunca
    navegações, refreshes ou trocas de aba. Chamado somente em
    `main.tentar_login` após `autenticacao.registrar_login` validar as
    credenciais. Persiste em `tb_config` (`contador_acessos_total` +
    `contador_acessos_inicio`) via `get_config`/`set_config` (que delegam ao
    `Repositorio`/SQLAlchemy e então a `banco_conexao.conexao`).
    `main._orquestrar_resumo_dados` apenas lê (`get_config`). Antes contava
    inline em `main`; agora esta função é a única fonte da verdade. Fail-soft
    — retorna `0` em erro. Retorna o novo total.
    """
    import datetime as _dt
    try:
        total = get_config("contador_acessos_total", "0") or "0"
        try:
            novo = int(str(total).strip() or 0) + 1
        except Exception:
            novo = 1
        set_config("contador_acessos_total", str(novo))
        inicio = (get_config("contador_acessos_inicio", "") or "").strip()
        if not inicio:
            set_config("contador_acessos_inicio", _dt.datetime.now().strftime("%Y-%m-%d"))
        return novo
    except Exception:
        return 0


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
                for _fn, _chaves in list(_HOOKS_CONFIG):
                    if _chaves is not None and chave not in _chaves:
                        continue
                    try:
                        _fn()
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
