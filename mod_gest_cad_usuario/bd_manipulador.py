"""User registration management module — full soft CRUD.

Módulo Gestão de Cadastro de Usuários — soft CRUD completo.

BD próprio: db_mod_gest_cad_usuario.db (WAL).
Tabelas: tb_usuarios, tb_acesso_usuario (perfis POR módulo), tb_modulo_perfil.
Auditoria central com ATOR (quem fez) conforme LGPD.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

import sqlite3
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_CAD_PATH = os.path.join(BASE_DIR, "db_mod_gest_cad_usuario.db")

PERFIS_GLOBAIS = ["comum", "administrador_modulo", "administrador_geral"]
PAPEIS_MODULO = ["comum", "administrador"]
# Módulos com acesso 'comum' liberado por padrão a todo usuário novo.
# usuarios/auditoria/blog são restritos (sem vínculo inicial): o acesso a
# eles é concedido manualmente pelo administrador na tela de usuários.
ACESSO_PADRAO_NOVO_USUARIO = ("editar_pdf", "empenhos", "solicita_impressao")


def get_connection():
    """Opens a connection to the module's own database (FKs enabled).

    Conexão via `banco_conexao.conexao` — SQLite (db_mod_gest_cad_usuario.db,
    WAL) ou PostgreSQL (DATABASE `db_mod_gest_cad_usuario`)."""
    try:
        from mod_intranet.banco_conexao import conexao
        conn = conexao("usuarios")
        if conn is None:
            raise RuntimeError("Falha ao abrir conexão do módulo Gestão de Usuários")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn
    except Exception as e:
        _log().exception(f"get_connection: falha ao abrir conexão | {e}")
        raise


def _conexao_segura():
    """Opens the module connection logging the failure (returns None on error).

    Versão fail-soft de `get_connection`: em falha loga a causa e devolve
    None — os chamadores tratam None como estado de erro sem derrubar."""
    try:
        return get_connection()
    except Exception as e:
        _log().exception(f"_conexao_segura: falha ao abrir conexão | {e}")
        return None


def _central():
    """Opens a connection to the CENTRAL database (sessions/config only)."""
    try:
        from mod_intranet.bd_conexao import get_connection as gc
        return gc()
    except Exception as e:
        _log().exception(f"_central: falha ao abrir conexão central | {e}")
        raise


def _audit(ator, acao, alvo, detalhe=""):
    """Writes a central audit record for this module (LGPD trail)."""
    try:
        from mod_intranet.bd_manipulador import audit_log
        audit_log(ator or "sistema", "gest_cad_usuario", acao,
                  f"Alvo: {alvo}" + (f" | {detalhe}" if detalhe else ""))
    except Exception as e:
        _log().exception(f"_audit: falha ao registrar auditoria | {e}")


def _log():
    """Logger central (loguru) — arquivo dedicado logs/gest_cad_usuario_<data>.log."""
    from mod_intranet import observabilidade
    return observabilidade.get_logger("gest_cad_usuario")


def senha_minima():
    """Minimum password length (characters) configured for the module.

    Política de senha mínima (em caracteres) do módulo, editável em
    tb_config central na chave `usuarios_senha_min` (painel Administração
    da Gestão de Usuários, 4–32, padrão 6). Fail-soft: em falha de leitura
    registra warning no loguru e retorna 6."""
    try:
        from mod_intranet.bd_conexao import get_config
        return max(4, int(get_config("usuarios_senha_min", "6")))
    except Exception as e:
        _log().warning(f"senha_minima: falha ao ler config; usando padrão 6 | {e}")
        return 6


def init_db():
    """Creates/migrates the schema and seeds (idempotent bootstrap).

    Cria `tb_usuarios` e `tb_acesso_usuario` (FK CASCADE/UPDATE CASCADE),
    aplica migrações idempotentes (soft delete `user_deletado`,
    `user_nome_completo`, `user_motivo_exclusao`), migra legados (usuários do
    banco central, CSV de módulos), semeia `master`/`master` com troca
    obrigatória (auto-cura enquanto a senha padrão existir) e os usuários de
    teste QA (`qacomum`/`qamaster`). Executado no import e pelo bootstrap."""
    try:
        _init_db_seguro()
    except Exception as e:
        _log().exception(f"init_db: falha no bootstrap | {e}")


def _init_db_seguro():
    """Runs the real init_db bootstrap inside a protected wrapper.

    Executa o bootstrap de init_db isolado para receber o try/except do
    entry point — falha nunca deve derrubar o import do módulo."""
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
        CREATE TABLE IF NOT EXISTS tb_acesso_usuario (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_nome TEXT NOT NULL REFERENCES tb_usuarios(user_nome) ON DELETE CASCADE,
            modulo_chave TEXT NOT NULL,
            papel TEXT NOT NULL DEFAULT 'comum',
            liberado_por TEXT,
            data_liberacao DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_nome, modulo_chave)
        )
    """)
    conn.commit()

    # Migração de esquema: garante FK com ON UPDATE CASCADE (renomeio de user_nome)
    cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='tb_acesso_usuario'")
    sql_row = cur.fetchone()
    if sql_row and "ON UPDATE" not in (sql_row[0] or "").upper():
        cur.executescript("""
            ALTER TABLE tb_acesso_usuario RENAME TO tb_acesso_usuario_old;
            CREATE TABLE tb_acesso_usuario (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_nome TEXT NOT NULL REFERENCES tb_usuarios(user_nome) ON DELETE CASCADE ON UPDATE CASCADE,
                modulo_chave TEXT NOT NULL,
                papel TEXT NOT NULL DEFAULT 'comum',
                liberado_por TEXT,
                data_liberacao DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_nome, modulo_chave)
            );
            INSERT INTO tb_acesso_usuario SELECT * FROM tb_acesso_usuario_old;
            DROP TABLE tb_acesso_usuario_old;
        """)
        conn.commit()

    # Migração: flags finas de permissão por módulo (JSON em tb_acesso_usuario).
    cur.execute("PRAGMA table_info(tb_acesso_usuario)")
    cols_acesso = {r[1] for r in cur.fetchall()}
    if "flags" not in cols_acesso:
        cur.execute("ALTER TABLE tb_acesso_usuario ADD COLUMN flags TEXT NOT NULL DEFAULT '{}'")
        conn.commit()

    # Migração única: usuários do BD central -> BD do módulo (legado).
    # Só roda se o BD central AINDA tiver tb_usuarios; em instalação nova
    # essa tabela não existe mais, então a migração é pulada com segurança
    # (evita quebrar o bootstrap "criar do zero" do PLANO.md).
    cur.execute("SELECT COUNT(*) FROM tb_usuarios")
    if cur.fetchone()[0] == 0:
        c = _central()
        try:
            cc = c.cursor()
            cc.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tb_usuarios'")
            if cc.fetchone():
                cc.execute("SELECT user_nome, user_senha, user_email, user_fone, user_perfil, user_ativo, data_cadastro, modulo_acesso FROM tb_usuarios")
                for r in cc.fetchall():
                    cur.execute(
                        """INSERT INTO tb_usuarios
                           (user_nome, user_senha, user_email, user_fone, user_perfil, user_ativo, data_cadastro, modulo_acesso)
                           VALUES (?, ?, ?, ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP), ?)""",
                        r,
                    )
                    # converte legado CSV -> linhas de acesso com papel 'comum'
                    for chave in [x.strip() for x in (r[7] or "").split(",") if x.strip()]:
                        cur.execute(
                            "INSERT OR IGNORE INTO tb_acesso_usuario (user_nome, modulo_chave, papel, liberado_por) VALUES (?, ?, 'comum', 'migracao')",
                            (r[0], chave),
                        )
                conn.commit()
        finally:
            c.close()

    # Migração: coluna de soft-delete explícita (distingue bloqueado de excluído)
    cur.execute("PRAGMA table_info(tb_usuarios)")
    cols = [r[1] for r in cur.fetchall()]
    if "user_deletado" not in cols:
        cur.execute("ALTER TABLE tb_usuarios ADD COLUMN user_deletado INTEGER NOT NULL DEFAULT 0")
        conn.commit()
    # Migração: nome de exibição/tratamento (pode ser o nome social — Decreto 8.727/2016)
    cur.execute("PRAGMA table_info(tb_usuarios)")
    cols = [r[1] for r in cur.fetchall()]
    if "user_nome_completo" not in cols:
        cur.execute("ALTER TABLE tb_usuarios ADD COLUMN user_nome_completo TEXT")
        cur.execute("UPDATE tb_usuarios SET user_nome_completo='Usuário Master' WHERE user_nome='master'")
        conn.commit()
    # Migração: motivo registrado no momento da exclusão lógica
    cur.execute("PRAGMA table_info(tb_usuarios)")
    cols = [r[1] for r in cur.fetchall()]
    if "user_motivo_exclusao" not in cols:
        cur.execute("ALTER TABLE tb_usuarios ADD COLUMN user_motivo_exclusao TEXT")
        conn.commit()
    conn.close()

    # Segurança: se o master AINDA usa a senha padrão 'master' (instalação nova
    # ou legado), força a troca no primeiro logon — idempotente e auto-cura:
    # depois que ele trocar, a flag nunca mais é rearmada. No primeiro acesso,
    # além da senha, o master nativo deve renomear o usuário (credenciais).
    try:
        from mod_intranet import autenticacao as _auth
        linha = _auth.usuario_existe("master")
        if linha and _auth.verificar_senha("master", linha[0]):
            _auth.marcar_trocar_senha("master", True)
            _auth.marcar_trocar_credenciais("master", True)
    except Exception as e:
        _log().exception(f"init_db: falha ao verificar senha padrão do master | {e}")

    # Garante master
    if not obter_usuario("master"):
        from mod_intranet.autenticacao import gerar_hash_senha, marcar_trocar_senha, marcar_trocar_credenciais
        conn = get_connection(); cur = conn.cursor()
        cur.execute(
            "INSERT INTO tb_usuarios (user_nome, user_senha, user_perfil, user_ativo) VALUES (?, ?, 'administrador_geral', 1)",
            ("master", gerar_hash_senha("master")),
        )
        conn.commit(); conn.close()
        marcar_trocar_senha("master", True)
        marcar_trocar_credenciais("master", True)

    # Garante usuários de teste de QA (docs) — qacomum (comum) e qamaster (administrador_geral).
    # qacomum segue o padrão de criação vigente (comum em editar_pdf,
    # empenhos e solicita_impressao; SEM acesso a blog/usuarios/auditoria).
    from mod_intranet.autenticacao import gerar_hash_senha, marcar_trocar_senha
    conn = get_connection(); cur = conn.cursor()
    if not obter_usuario("qacomum"):
        cur.execute(
            "INSERT INTO tb_usuarios (user_nome, user_senha, user_perfil, user_ativo, user_nome_completo) VALUES (?, ?, 'comum', 1, ?)",
            ("qacomum", gerar_hash_senha("123456"), "Usuário de Teste QA Comum"),
        )
        for chave in ACESSO_PADRAO_NOVO_USUARIO:
            cur.execute(
                "INSERT OR IGNORE INTO tb_acesso_usuario (user_nome, modulo_chave, papel, liberado_por) VALUES (?, ?, 'comum', 'sistema')",
                ("qacomum", chave),
            )
        conn.commit()
        marcar_trocar_senha("qacomum", True)
    else:
        # Reconcilia o qacomum existente com o padrão vigente (idempotente):
        # garante os 3 acessos comuns e remove o legado 'blog' concedido
        # pelo seed ('sistema') — concessões manuais do admin são mantidas.
        for chave in ACESSO_PADRAO_NOVO_USUARIO:
            cur.execute(
                "INSERT OR IGNORE INTO tb_acesso_usuario (user_nome, modulo_chave, papel, liberado_por) VALUES (?, ?, 'comum', 'sistema')",
                ("qacomum", chave),
            )
        cur.execute("DELETE FROM tb_acesso_usuario WHERE user_nome='qacomum' AND modulo_chave='blog' AND liberado_por='sistema'")
        conn.commit()
    if not obter_usuario("qamaster"):
        cur.execute(
            "INSERT INTO tb_usuarios (user_nome, user_senha, user_perfil, user_ativo, user_nome_completo) VALUES (?, ?, 'administrador_geral', 1, ?)",
            ("qamaster", gerar_hash_senha("123456"), "Usuário de Teste QA Master"),
        )
        conn.commit()
        marcar_trocar_senha("qamaster", True)
    conn.close()


# ================= CONSULTAS =================

def _normalizar_data(valor):
    """Normalizes a date value to 'YYYY-MM-DD HH:MM:SS' string.

    No SQLite `data_cadastro`/`data_liberacao` já vêm como string; no
    PostgreSQL o driver retorna `datetime.datetime`. Padroniza para string
    para que o consumo (telas) não precise saber o backend."""
    if valor is None:
        return None
    if isinstance(valor, (datetime,)):
        return valor.strftime("%Y-%m-%d %H:%M:%S")
    return str(valor)


def listar_usuarios(filtro_ativo=None):
    """Lists users with per-module access aggregated (GROUP_CONCAT).

    Retorna tuplas (id, user_nome, user_perfil, user_ativo, user_email,
    user_fone, data_cadastro, acessos 'modulo:papel, …', user_deletado,
    user_nome_completo, user_motivo_exclusao). `filtro_ativo` filtra por
    `user_ativo` quando informado; ordenado por login. `data_cadastro` é
    normalizada para string (backend-agnóstico)."""
    conn = _conexao_segura()
    if conn is None:
        return []
    try:
        cur = conn.cursor()
        sql = """SELECT u.id, u.user_nome, u.user_perfil, u.user_ativo,
                        u.user_email, u.user_fone, u.data_cadastro,
                        GROUP_CONCAT(a.modulo_chave || ':' || a.papel, ', '),
                        u.user_deletado, u.user_nome_completo, u.user_motivo_exclusao
                 FROM tb_usuarios u
                 LEFT JOIN tb_acesso_usuario a ON a.user_nome = u.user_nome
                 WHERE 1=1"""
        params = []
        if filtro_ativo is not None:
            sql += " AND u.user_ativo=?"
            params.append(1 if filtro_ativo else 0)
        sql += " GROUP BY u.id ORDER BY u.user_nome"
        cur.execute(sql, params)
        linhas = []
        for r in cur.fetchall():
            linha = list(r)
            linha[6] = _normalizar_data(linha[6])
            linhas.append(tuple(linha))
        return linhas
    except Exception as e:
        _log().exception(f"listar_usuarios: falha ao listar usuários | {e}")
        return []
    finally:
        conn.close()


def obter_usuario(user_nome):
    """Fetches one user row (incl. senha/perfil/ativo/deletado/nome_completo).

    Retorna a tupla completa do usuário ou None. Usada pelo núcleo
    (`autenticacao.usuario_existe`) para validar login/sessão a cada request."""
    conn = _conexao_segura()
    if conn is None:
        return None
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT id, user_nome, user_senha, user_email, user_fone,
                      user_perfil, user_ativo, data_cadastro,
                      user_deletado, user_nome_completo
               FROM tb_usuarios WHERE user_nome=?""",
            (user_nome,),
        )
        return cur.fetchone()
    except Exception as e:
        _log().exception(f"obter_usuario: falha ao obter usuário {user_nome} | {e}")
        return None
    finally:
        conn.close()


def nome_de_tratamento(user_nome):
    """Nome usado para tratamento nas telas — nome completo ou social.
    Cai para o login se o campo ainda não foi preenchido."""
    try:
        row = obter_usuario(user_nome)
        return (row[9] or "").strip() if row and row[9] else user_nome
    except Exception as e:
        _log().exception(f"nome_de_tratamento: falha para {user_nome} | {e}")
        return user_nome


def listar_acessos(user_nome):
    """Lists the user's per-module grants (modulo_chave, papel, liberado_por, data)."""
    conn = _conexao_segura()
    if conn is None:
        return []
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT modulo_chave, papel, liberado_por, data_liberacao
               FROM tb_acesso_usuario WHERE user_nome=? ORDER BY modulo_chave""",
            (user_nome,),
        )
        linhas = []
        for r in cur.fetchall():
            linha = list(r)
            linha[3] = _normalizar_data(linha[3])
            linhas.append(tuple(linha))
        return linhas
    except Exception as e:
        _log().exception(f"listar_acessos: falha ao listar acessos de {user_nome} | {e}")
        return []
    finally:
        conn.close()


# ================= CRUD =================

def _validar_nome_completo(nome_completo, user_nome):
    """Validates the display/social name (min 3 chars, different from login)."""
    nc = (nome_completo or "").strip()
    if len(nc) < 3:
        return None, "Nome completo/social é obrigatório (mín. 3 caracteres)"
    if nc.lower() == (user_nome or "").strip().lower():
        return None, "O nome de exibição deve ser diferente do nome de login"
    return nc, None


def criar_usuario(ator, user_nome, senha, email=None, fone=None, perfil="comum",
                   nome_completo=""):
    """Creates a user with a provisional password (mandatory first-login change).

    Valida login, senha mínima (`senha_minima`), perfil global e nome de
    exibição; grava hash bcrypt, libera o acesso padrão 'comum'
    (`ACESSO_PADRAO_NOVO_USUARIO`), marca `forcar_troca` e audita
    `criar_usuario`. Senha vazia/None cai no padrão inicial ``123456``.
    Retorna `(ok, msg)`."""
    from mod_intranet.autenticacao import gerar_hash_senha, marcar_trocar_senha
    senha = (senha or "").strip() or "123456"
    if not user_nome or not user_nome.strip():
        return False, "Nome de usuário é obrigatório"
    if len(senha or "") < senha_minima():
        return False, f"Senha provisória deve ter no mínimo {senha_minima()} caracteres"
    if perfil not in PERFIS_GLOBAIS:
        return False, f"Perfil inválido: {perfil}"
    nome_c, erro = _validar_nome_completo(nome_completo, user_nome)
    if erro:
        return False, erro
    conn = _conexao_segura()
    if conn is None:
        return False, "Falha ao conectar no banco de usuários"
    try:
        cur = conn.cursor()
        hash_s = gerar_hash_senha(senha)
        cur.execute(
            """INSERT INTO tb_usuarios
               (user_nome, user_senha, user_email, user_fone, user_perfil, user_ativo,
                user_nome_completo)
               VALUES (?, ?, ?, ?, ?, 1, ?)""",
            (user_nome.strip(), hash_s, email, fone, perfil, nome_c),
        )
        for chave in ACESSO_PADRAO_NOVO_USUARIO:
            cur.execute(
                "INSERT INTO tb_acesso_usuario (user_nome, modulo_chave, papel, liberado_por) VALUES (?, ?, 'comum', ?)",
                (user_nome.strip(), chave, ator),
            )
        conn.commit()
        marcar_trocar_senha(user_nome.strip(), True)
        _audit(ator, "criar_usuario", user_nome.strip(), f"perfil={perfil} | exibição: {nome_c}")
        _log().info(f"usuário criado: {user_nome.strip()} perfil={perfil} por {ator}")
        return True, "Usuário criado (senha provisória — troca obrigatória no 1º acesso)"
    except sqlite3.IntegrityError:
        _log().warning(f"criar_usuario: nome já existe: {user_nome}")
        return False, "Nome de usuário já existe"
    except Exception as e:
        _log().exception(f"criar_usuario: falha ao criar usuário {user_nome} | {e}")
        return False, "Erro inesperado ao criar usuário"
    finally:
        conn.close()


def editar_usuario(ator, user_nome, email="__NULO__", fone="__NULO__",
                   perfil=None, ativo=None, deletado=None, nome_completo="__NULO__",
                   auditar=True):
    """Edita dados pessoais/perfil global. Use '__NULO__' p/ manter campo."""
    conn = _conexao_segura()
    if conn is None:
        return False, "Falha ao conectar no banco de usuários"
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM tb_usuarios WHERE user_nome=?", (user_nome,))
        if not cur.fetchone():
            return False, "Usuário não existe"
        # RF-26: outro administrador não pode rebaixar nem bloquear o último
        # administrador_geral ativo do sistema.
        if ator != user_nome:
            cur.execute("SELECT user_perfil, user_ativo FROM tb_usuarios WHERE user_nome=?", (user_nome,))
            linha = cur.fetchone()
            if linha and linha[0] == "administrador_geral" and linha[1] == 1:
                vai_rebaixar = perfil is not None and perfil != "administrador_geral"
                vai_bloquear = ativo is not None and not ativo
                if vai_rebaixar or vai_bloquear:
                    cur.execute(
                        "SELECT COUNT(*) FROM tb_usuarios "
                        "WHERE user_perfil='administrador_geral' AND user_ativo=1")
                    if cur.fetchone()[0] <= 1:
                        return False, "Não é possível rebaixar/bloquear o último administrador geral ativo"
        sets, params, mudancas = [], [], []
        if nome_completo != "__NULO__":
            nc, erro = _validar_nome_completo(nome_completo, user_nome)
            if erro:
                return False, erro
            sets.append("user_nome_completo=?"); params.append(nc)
            mudancas.append(f"nome de exibição: {nc}")
        if email != "__NULO__":
            sets.append("user_email=?"); params.append(email or None); mudancas.append("email")
        if fone != "__NULO__":
            sets.append("user_fone=?"); params.append(fone or None); mudancas.append("telefone")
        if perfil:
            if perfil not in PERFIS_GLOBAIS:
                return False, f"Perfil inválido: {perfil}"
            if ator == user_nome:
                cur.execute("SELECT user_perfil FROM tb_usuarios WHERE user_nome=?", (user_nome,))
                atual = cur.fetchone()
                if atual and atual[0] == "administrador_geral" and perfil != "administrador_geral":
                    return False, "Você não pode remover o próprio perfil de administrador geral"
            sets.append("user_perfil=?"); params.append(perfil); mudancas.append(f"perfil={perfil}")
        if ativo is not None:
            if ator == user_nome and not ativo:
                return False, "Você não pode desativar a própria conta"
            sets.append("user_ativo=?"); params.append(1 if ativo else 0)
            mudancas.append("ativo" if ativo else "inativo")
        if deletado is not None:
            if ator == user_nome and deletado:
                return False, "Você não pode excluir a própria conta"
            sets.append("user_deletado=?"); params.append(1 if deletado else 0)
            mudancas.append("restaurado" if not deletado else "soft")
        if not sets:
            return True, "Nada a alterar"
        params.append(user_nome)
        cur.execute(f"UPDATE tb_usuarios SET {', '.join(sets)} WHERE user_nome=?", tuple(params))  # nosec B608 — sets só literais fixos "col=?"; valores via ?
        conn.commit()
        if auditar:
            _audit(ator, "editar_usuario", user_nome, ", ".join(mudancas))
        _log().info(f"usuário editado: {user_nome} | {', '.join(mudancas)} por {ator}")
        return True, "Usuário atualizado"
    except Exception as e:
        _log().exception(f"editar_usuario: falha ao editar {user_nome} | {e}")
        return False, "Erro inesperado ao editar usuário"
    finally:
        conn.close()


def renomear_usuario(ator, nome_atual, novo_nome, permitir_master=False):
    """Renomeia mantendo o ID (chave primária), replicando nas tabelas dependentes.

    `permitir_master=True` libera a renomeação do `master` nativo — usado
    EXCLUSIVAMENTE no primeiro acesso (troca de credenciais obrigatória)."""
    novo_nome = (novo_nome or "").strip()
    if not novo_nome:
        return False, "Novo nome vazio"
    if nome_atual == "master" and not permitir_master:
        return False, "A conta master nativa não pode ser renomeada"
    conn = _conexao_segura()
    if conn is None:
        return False, "Falha ao conectar no banco de usuários"
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM tb_usuarios WHERE user_nome=?", (novo_nome,))
        if cur.fetchone():
            return False, f"'{novo_nome}' já existe"
        cur.execute("SELECT id FROM tb_usuarios WHERE user_nome=?", (nome_atual,))
        if not cur.fetchone():
            return False, "Usuário não existe"
        cur.execute("UPDATE tb_usuarios SET user_nome=? WHERE user_nome=?", (novo_nome, nome_atual))
        cur.execute("UPDATE tb_acesso_usuario SET user_nome=? WHERE user_nome=?", (novo_nome, nome_atual))
        conn.commit()
        _audit(ator, "renomear_usuario", nome_atual, f"→ {novo_nome} (ID preservado)")
        # reflete também nas sessões do banco central
        try:
            c = _central(); cc = c.cursor()
            cc.execute("UPDATE tb_sessoes SET usuario=? WHERE usuario=? AND logout_timestamp IS NULL",
                       (novo_nome, nome_atual))
            c.commit(); c.close()
        except Exception as e:
            _log().warning(f"renomear_usuario: falha ao refletir em sessões centrais | {e}")
        _vinculos_cruzados_renomear(nome_atual, novo_nome)
        _log().info(f"usuário renomeado: {nome_atual} -> {novo_nome} por {ator}")
        return True, f"Renomeado para '{novo_nome}'"
    except sqlite3.IntegrityError:
        _log().warning(f"renomear_usuario: conflito de unicidade para '{novo_nome}'")
        return False, "Conflito de unicidade"
    except Exception as e:
        _log().exception(f"renomear_usuario: falha ao renomear {nome_atual} | {e}")
        return False, "Erro inesperado ao renomear usuário"
    finally:
        conn.close()


def alterar_senha_admin(ator, user_nome, nova_senha):
    """Troca administrativa de senha (reenvio provisório)."""
    if len(nova_senha or "") < senha_minima():
        return False, f"Mínimo {senha_minima()} caracteres"
    from mod_intranet.autenticacao import gerar_hash_senha, marcar_trocar_senha
    conn = _conexao_segura()
    if conn is None:
        return False, "Falha ao conectar no banco de usuários"
    try:
        cur = conn.cursor()
        cur.execute("UPDATE tb_usuarios SET user_senha=? WHERE user_nome=?",
                    (gerar_hash_senha(nova_senha), user_nome))
        if cur.rowcount == 0:
            return False, "Usuário não existe"
        conn.commit()
        marcar_trocar_senha(user_nome, True)
        _fechar_sessoes_central(user_nome)  # senha redefinida -> todas as sessões caem
        _audit(ator, "alterar_senha", user_nome, "senha provisória definida pelo admin; sessões encerradas")
        _log().info(f"senha redefinida (admin): {user_nome} por {ator}")
        return True, "Senha redefinida — sessões encerradas e troca obrigatória no próximo acesso"
    except Exception as e:
        _log().exception(f"alterar_senha_admin: falha ao redefinir senha de {user_nome} | {e}")
        return False, "Erro inesperado ao redefinir senha"
    finally:
        conn.close()


def bloquear_usuario(ator, user_nome, bloquear=True):
    """Bloqueia (ativo=0). Desbloquear também restaura soft-delete."""
    if ator == user_nome and bloquear:
        return False, "Você não pode bloquear a si mesmo"
    try:
        kw = {"deletado": False} if not bloquear else {}
        # 'auditar=False': a ação ganha trilha DEDICADA abaixo (bloquear_usuario ou
        # desbloquear_usuario) em vez de um 'editar_usuario' genérico.
        ok, msg = editar_usuario(ator, user_nome, ativo=(not bloquear), auditar=False, **kw)
        if ok:
            if not bloquear:  # restauração limpa o motivo da exclusão lógica
                conn = _conexao_segura()
                if conn is not None:
                    try:
                        conn.execute("UPDATE tb_usuarios SET user_motivo_exclusao=NULL WHERE user_nome=?",
                                     (user_nome,))
                        conn.commit()
                    finally:
                        conn.close()
            if bloquear:
                _fechar_sessoes_central(user_nome)
            _audit(ator, "bloquear_usuario" if bloquear else "desbloquear_usuario",
                   user_nome, "conta bloqueada" if bloquear else "conta restaurada (inclui soft delete)")
            _log().info(f"usuário {'bloqueado' if bloquear else 'restaurado'}: {user_nome} por {ator}")
        return ok, msg
    except Exception as e:
        _log().exception(f"bloquear_usuario: falha para {user_nome} | {e}")
        return False, "Erro inesperado ao bloquear/restaurar conta"


def soft_delete_usuario(ator, user_nome, motivo=None):
    """Exclusão LÓGICA com motivo obrigatório — vai para a lista de excluídos.

    Não apaga nada: reversível via 'Restaurar'. A exclusão permanente
    (LGPD) é ação separada, disponível apenas na lista de excluídos."""
    if user_nome == "master":
        return False, "A conta master nativa não pode ser excluída"
    if ator == user_nome:
        return False, "Você não pode excluir a própria conta"
    motivo = (motivo or "").strip()
    if len(motivo) < 3:
        return False, "Informe o motivo da exclusão (mín. 3 caracteres)"
    try:
        ok, msg = editar_usuario(ator, user_nome, ativo=False, deletado=True)
        if not ok:
            return ok, msg
        conn = _conexao_segura()
        if conn is not None:
            try:
                conn.execute("UPDATE tb_usuarios SET user_motivo_exclusao=? WHERE user_nome=?",
                             (motivo, user_nome))
                conn.commit()
            finally:
                conn.close()
        _fechar_sessoes_central(user_nome)
        _audit(ator, "soft_delete", user_nome, f"motivo: {motivo}")
        _log().info(f"exclusão lógica: {user_nome} por {ator} | motivo: {motivo}")
        return True, f"'{user_nome}' movido para a lista de excluídos"
    except Exception as e:
        _log().exception(f"soft_delete_usuario: falha para {user_nome} | {e}")
        return False, "Erro inesperado ao excluir usuário"


def _vinculos_cruzados_excluir(user_nome):
    """Remove/anonimiza referências do usuário nos demais módulos (LGPD).
    Blog: postagens e comentários apagados. EditorPDF: arquivos físicos,
    registros e cota apagados. Empenhos: registros públicos preservados
    com autoria anonimizada.

    Isolamento total: cada módulo limpa o PRÓPRIO banco através de sua
    API pública — nunca há cross-query entre bancos."""
    det = []
    try:
        from mod_blog import bd_manipulador as _blog
        n = _blog.remover_vinculos_usuario(user_nome)
        if n:
            det.append(f"{n} postagem(ns)")
    except Exception as e:
        det.append("blog: falhou")
        _log().exception(f"_vinculos_cruzados_excluir: blog falhou para {user_nome} | {e}")
    try:
        from mod_edit_pdf import bd_manipulador as _pdf
        removidos, nomes = _pdf.remover_vinculos_usuario(user_nome)
        if removidos or nomes:
            det.append(f"{removidos} arquivo(s) PDF")
    except Exception as e:
        det.append("pdf: falhou")
        _log().exception(f"_vinculos_cruzados_excluir: pdf falhou para {user_nome} | {e}")
    try:
        from mod_renomear_empenho import bd_manipulador as _emp
        n = _emp.anonimizar_usuario(user_nome)
        if n:
            det.append(f"{n} empenho(s) anonimizado(s)")
    except Exception as e:
        det.append("empenhos: falhou")
        _log().exception(f"_vinculos_cruzados_excluir: empenhos falhou para {user_nome} | {e}")
    return det


def _vinculos_cruzados_renomear(nome_atual, novo_nome):
    """Propaga o renomeio para colunas de autoria nos demais módulos.

    Isolamento total: cada módulo atualiza o PRÓPRIO banco através de
    sua API pública — nunca há cross-query entre bancos."""
    try:
        from mod_blog import bd_manipulador as _blog
        _blog.renomear_autor(nome_atual, novo_nome)
    except Exception as e:
        _log().warning(f"_vinculos_cruzados_renomear: falha ao propagar {nome_atual}->{novo_nome} | {e}")
    try:
        from mod_edit_pdf import bd_manipulador as _pdf
        _pdf.renomear_usuario(nome_atual, novo_nome)
    except Exception as e:
        _log().warning(f"_vinculos_cruzados_renomear: falha ao propagar {nome_atual}->{novo_nome} | {e}")
    try:
        from mod_renomear_empenho import bd_manipulador as _emp
        _emp.renomear_usuario(nome_atual, novo_nome)
    except Exception as e:
        _log().warning(f"_vinculos_cruzados_renomear: falha ao propagar {nome_atual}->{novo_nome} | {e}")


def excluir_usuario_definitivo(ator, user_nome):
    """Permanently deletes a user (LGPD) with cross-module cleanup.

    Exclusivo do `administrador_geral` (revalidado no backend). Remove
    postagens/comentários do Blog, arquivos/cota do editorPDF e anonimiza
    autoria de empenhos (`_vinculos_cruzados_excluir`), apaga acessos e o
    usuário, encerra sessões e audita `excluir_definitivo`. `master` e a
    própria conta do ator são protegidos; o último admin geral ativo também.
    Retorna `(ok, msg)`."""
    try:
        from mod_intranet import autenticacao  # import tardio: evita ciclo de imports
        if autenticacao.perfil_global_de(ator) != "administrador_geral":
            return False, "Apenas o administrador geral do sistema pode excluir definitivamente (LGPD)"
        if user_nome == "master":
            return False, "A conta master nativa não pode ser excluída"
        if ator == user_nome:
            return False, "Você não pode excluir a própria conta"
        conn = _conexao_segura()
        if conn is None:
            return False, "Falha ao conectar no banco de usuários"
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM tb_usuarios WHERE user_perfil='administrador_geral' AND user_ativo=1 AND user_nome=?",
            (user_nome,),
        )
        if cur.fetchone()[0] > 0:
            cur.execute("SELECT COUNT(*) FROM tb_usuarios WHERE user_perfil='administrador_geral' AND user_ativo=1")
            if cur.fetchone()[0] <= 1:
                return False, "Não é possível excluir o último administrador ativo"
        detalhes = _vinculos_cruzados_excluir(user_nome)
        cur.execute("DELETE FROM tb_acesso_usuario WHERE user_nome=?", (user_nome,))
        cur.execute("DELETE FROM tb_usuarios WHERE user_nome=?", (user_nome,))
        conn.commit()
        _fechar_sessoes_central(user_nome)
        extra = f" | {', '.join(detalhes)}" if detalhes else ""
        _audit(ator, "excluir_definitivo", user_nome, f"DELETE físico (LGPD){extra}")
        _log().info(f"exclusão definitiva (LGPD): {user_nome} por {ator}{extra}")
        msg = "Usuário excluído definitivamente"
        if detalhes:
            msg += f" ({', '.join(detalhes)})"
        return True, msg
    except Exception as e:
        _log().exception(f"excluir_usuario_definitivo: falha ao excluir {user_nome} | {e}")
        return False, "Erro inesperado ao excluir definitivamente"


def duplicar_usuario(ator, usuario_origem, novo_nome, senha, email=None,
                     fone=None, nome_completo=""):
    """Duplica um usuário existente e todas as suas configurações de acesso.

    Copia o perfil global e o papel do usuário origem em cada módulo
    (tb_acesso_usuario). O novo usuário é criado exigindo apenas os dados
    essenciais (login, nome, senha e email) — as permissões vêm da origem.
    Senha vazia/None cai no padrão inicial ``123456``.
    """
    try:
        senha = (senha or "").strip() or "123456"
        origem = obter_usuario(usuario_origem)
        if not origem:
            return False, "Usuário origem não encontrado"
        perfil_origem = origem[5]
        ok, msg = criar_usuario(ator, novo_nome, senha,
                                email=email, fone=fone, perfil=perfil_origem,
                                nome_completo=nome_completo)
        if not ok:
            return False, msg
        # replica acessos por módulo (perfil) da origem
        for chave, papel, _liberado, _data in listar_acessos(usuario_origem):
            gest_sys = definir_acesso(ator, novo_nome, chave, papel)
            if not gest_sys[0]:
                _log().warning(f"duplicar_usuario: falha ao replicar acesso {chave} "
                               f"para {novo_nome} | {gest_sys[1]}")
            else:
                _flags_origem = obter_flags(usuario_origem, chave)
                if _flags_origem:
                    ok_f, msg_f = definir_flags(ator, novo_nome, chave, _flags_origem)
                    if not ok_f:
                        _log().warning(f"duplicar_usuario: falha ao replicar flags {chave} "
                                       f"para {novo_nome} | {msg_f}")
        _audit(ator, "duplicar_usuario", novo_nome,
               f"origem={usuario_origem} | perfil={perfil_origem}")
        _log().info(f"usuário duplicado: {novo_nome} a partir de {usuario_origem} por {ator}")
        return True, "Usuário duplicado com as permissões da origem"
    except Exception as e:
        _log().exception(f"duplicar_usuario: falha ao duplicar {novo_nome} a partir de {usuario_origem} | {e}")
        return False, "Erro inesperado ao duplicar usuário"

# ================= PERFIS POR MÓDULO =================

def definir_acesso(ator, user_nome, modulo_chave, papel):
    """Atribui papel do usuário num módulo ('comum'|'administrador'). None remove."""
    if papel is None:
        return remover_acesso(ator, user_nome, modulo_chave)
    if papel not in PAPEIS_MODULO:
        return False, f"Papel inválido: {papel}"
    conn = _conexao_segura()
    if conn is None:
        return False, "Falha ao conectar no banco de usuários"
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO tb_acesso_usuario (user_nome, modulo_chave, papel, liberado_por, data_liberacao)
               VALUES (?, ?, ?, ?, datetime('now','localtime'))
               ON CONFLICT(user_nome, modulo_chave) DO UPDATE SET
                   papel=excluded.papel, liberado_por=excluded.liberado_por,
                   data_liberacao=excluded.data_liberacao""",
            (user_nome, modulo_chave, papel, ator),
        )
        conn.commit()
        _audit(ator, "definir_acesso", user_nome, f"{modulo_chave}={papel}")
        _log().info(f"acesso definido: {user_nome} {modulo_chave}={papel} por {ator}")
        return True, f"{modulo_chave}: {papel}"
    except Exception as e:
        _log().exception(f"definir_acesso: falha ao definir acesso {user_nome}@{modulo_chave} | {e}")
        return False, "Erro inesperado ao definir acesso"
    finally:
        conn.close()


def remover_acesso(ator, user_nome, modulo_chave):
    """Removes the user's grant on a module and audits it. Returns (ok, msg)."""
    conn = _conexao_segura()
    if conn is None:
        return False, "Falha ao conectar no banco de usuários"
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM tb_acesso_usuario WHERE user_nome=? AND modulo_chave=?",
                    (user_nome, modulo_chave))
        conn.commit()
        _audit(ator, "remover_acesso", user_nome, f"módulo {modulo_chave}")
        _log().info(f"acesso removido: {user_nome} módulo {modulo_chave} por {ator}")
        return True, f"Acesso a '{modulo_chave}' removido"
    except Exception as e:
        _log().exception(f"remover_acesso: falha ao remover acesso {user_nome}@{modulo_chave} | {e}")
        return False, "Erro inesperado ao remover acesso"
    finally:
        conn.close()


def obter_papel_no_modulo(user_nome, modulo_chave):
    """Retorna 'administrador', 'comum' ou None."""
    conn = _conexao_segura()
    if conn is None:
        return None
    try:
        cur = conn.cursor()
        cur.execute("SELECT user_perfil FROM tb_usuarios WHERE user_nome=? AND user_ativo=1",
                    (user_nome,))
        row = cur.fetchone()
        if row and row[0] == "administrador_geral":
            return "administrador"
        cur.execute("SELECT papel FROM tb_acesso_usuario WHERE user_nome=? AND modulo_chave=?",
                    (user_nome, modulo_chave))
        row = cur.fetchone()
        return row[0] if row else None
    except Exception as e:
        _log().exception(f"obter_papel_no_modulo: falha para {user_nome}@{modulo_chave} | {e}")
        return None
    finally:
        conn.close()


def validar_acesso_modulo(user_nome, modulo_chave):
    """True if the user may access the module (used by the core page guard).

    RF-35: o módulo de Auditoria é exclusivo do `administrador_geral`.
    Demais módulos: basta existir vínculo em `tb_acesso_usuario` (o papel
    `administrador` em qualquer módulo é concedido ao admin geral)."""
    try:
        # RF-35: o módulo de Auditoria é exclusivo do administrador geral do sistema.
        if modulo_chave == "auditoria":
            from mod_intranet import autenticacao
            return autenticacao.perfil_global_de(user_nome) == "administrador_geral"
        return obter_papel_no_modulo(user_nome, modulo_chave) is not None
    except Exception as e:
        _log().exception(f"validar_acesso_modulo: falha para {user_nome}@{modulo_chave} | {e}")
        return False


# ================= FLAGS FINAS DE PERMISSÃO (JSON) =================

FLAGS_PERMISSAO = {
    "blog.publicar": "Publicar e editar postagens do blog",
    "blog.comentar": "Comentar nas postagens do blog",
    "blog.configurar": "Configurar exibição e aparência do blog",
}


def _flags_validas(flags):
    """Valida o dicionário de flags contra o catálogo (allowlist)."""
    if not isinstance(flags, dict):
        return False, "flags deve ser um dicionário {flag: bool}"
    desconhecidas = [k for k in flags if k not in FLAGS_PERMISSAO]
    if desconhecidas:
        return False, f"flags desconhecidas: {', '.join(desconhecidas)}"
    if any(not isinstance(v, bool) for v in flags.values()):
        return False, "valores das flags devem ser booleanos"
    return True, ""


def obter_flags(user_nome, modulo_chave):
    """Lê as flags finas do vínculo (dict). Fail-soft: ausente/erro/JSON inválido = {}."""
    try:
        conn = get_connection()
    except Exception as e:
        _log().exception(f"obter_flags: falha ao conectar para {user_nome}@{modulo_chave} | {e}")
        return {}
    try:
        cur = conn.cursor()
        cur.execute("SELECT flags FROM tb_acesso_usuario WHERE user_nome=? AND modulo_chave=?",
                    (user_nome, modulo_chave))
        row = cur.fetchone()
        if not row or not row[0]:
            return {}
        try:
            import json
            dados = json.loads(row[0])
        except (ValueError, TypeError):
            return {}
        return dados if isinstance(dados, dict) else {}
    except Exception as e:
        _log().exception(f"obter_flags: falha ao ler flags de {user_nome}@{modulo_chave} | {e}")
        return {}
    finally:
        conn.close()


def definir_flags(ator, user_nome, modulo_chave, flags):
    """Substitui as flags finas do vínculo (validadas pelo catálogo)."""
    ok, msg = _flags_validas(flags)
    if not ok:
        return False, msg
    conn = _conexao_segura()
    if conn is None:
        return False, "Falha ao conectar no banco de usuários"
    try:
        import json
        cur = conn.cursor()
        cur.execute("SELECT id FROM tb_acesso_usuario WHERE user_nome=? AND modulo_chave=?",
                    (user_nome, modulo_chave))
        if not cur.fetchone():
            return False, f"sem vínculo {user_nome}@{modulo_chave} (libere o acesso primeiro)"
        cur.execute("UPDATE tb_acesso_usuario SET flags=? WHERE user_nome=? AND modulo_chave=?",
                    (json.dumps(flags, sort_keys=True), user_nome, modulo_chave))
        conn.commit()
        _audit(ator, "definir_flags", user_nome, f"{modulo_chave}={sorted(flags)}")
        _log().info(f"flags definidas: {user_nome} {modulo_chave}={sorted(flags)} por {ator}")
        return True, f"{modulo_chave}: {len(flags)} flag(s)"
    except Exception as e:
        _log().exception(f"definir_flags: falha para {user_nome}@{modulo_chave} | {e}")
        return False, "Erro inesperado ao definir flags"
    finally:
        conn.close()


def tem_flag(user_nome, modulo_chave, flag):
    """True se o usuário tem a flag (admin global/modular passam pelo papel)."""
    try:
        if obter_papel_no_modulo(user_nome, modulo_chave) == "administrador":
            return True
        return bool(obter_flags(user_nome, modulo_chave).get(flag))
    except Exception:
        return False


# ================= SESSÕES ATIVAS =================

def _fechar_sessoes_central(user_nome):
    """Closes ALL open central sessions of the user (block/delete/password reset)."""
    try:
        c = _central(); cc = c.cursor()
        cc.execute("UPDATE tb_sessoes SET logout_timestamp=datetime('now','localtime') WHERE usuario=? AND logout_timestamp IS NULL",
                   (user_nome,))
        c.commit(); c.close()
    except Exception as e:
        _log().warning(f"_fechar_sessoes_central: falha ao encerrar sessões de {user_nome} | {e}")


def listar_sessoes_ativas(usuario=None):
    """Sessões abertas (sem logout), agora com rastreabilidade IP/dispositivo/MAC."""
    try:
        c = _central()
    except Exception as e:
        _log().exception(f"listar_sessoes_ativas: falha ao abrir conexão central | {e}")
        return []
    try:
        cur = c.cursor()
        sql = """SELECT id, usuario, modulo, login_timestamp, cookie_hash,
                        COALESCE(ip,'—'), COALESCE(dispositivo,'—'), COALESCE(mac,'—')
                 FROM tb_sessoes WHERE logout_timestamp IS NULL"""
        params = []
        if usuario:
            sql += " AND usuario=?"
            params.append(usuario)
        sql += " ORDER BY login_timestamp DESC"
        cur.execute(sql, params)
        return cur.fetchall()
    except Exception as e:
        _log().exception(f"listar_sessoes_ativas: falha ao listar sessões | {e}")
        return []
    finally:
        c.close()


def contar_sessoes_ativas(usuario):
    """Counts the user's open sessions (logout_timestamp IS NULL)."""
    try:
        c = _central()
    except Exception as e:
        _log().exception(f"contar_sessoes_ativas: falha ao abrir conexão central | {e}")
        return 0
    try:
        cur = c.cursor()
        cur.execute("SELECT COUNT(*) FROM tb_sessoes WHERE usuario=? AND logout_timestamp IS NULL",
                    (usuario,))
        return cur.fetchone()[0]
    except Exception as e:
        _log().exception(f"contar_sessoes_ativas: falha para {usuario} | {e}")
        return 0
    finally:
        c.close()


def sessoes_ativas_por_usuario():
    """{usuario: qtd_ativas} — uma única consulta para a tabela inteira."""
    try:
        c = _central()
    except Exception as e:
        _log().exception(f"sessoes_ativas_por_usuario: falha ao abrir conexão central | {e}")
        return {}
    try:
        cur = c.cursor()
        cur.execute("""SELECT usuario, COUNT(*) FROM tb_sessoes
                       WHERE logout_timestamp IS NULL GROUP BY usuario""")
        return dict(cur.fetchall())
    except Exception as e:
        _log().exception(f"sessoes_ativas_por_usuario: falha ao agrupar sessões | {e}")
        return {}
    finally:
        c.close()


def listar_historico_sessoes(usuario, limite=10):
    """Últimas sessões ENCERRADAS do usuário (rastreabilidade LGPD)."""
    try:
        c = _central()
    except Exception as e:
        _log().exception(f"listar_historico_sessoes: falha ao abrir conexão central | {e}")
        return []
    try:
        cur = c.cursor()
        cur.execute(
            """SELECT id, modulo, login_timestamp, logout_timestamp,
                      COALESCE(ip,'—'), COALESCE(dispositivo,'—'), COALESCE(mac,'—')
               FROM tb_sessoes
               WHERE usuario=? AND logout_timestamp IS NOT NULL
               ORDER BY id DESC LIMIT ?""",
            (usuario, int(limite)),
        )
        return cur.fetchall()
    except Exception as e:
        _log().exception(f"listar_historico_sessoes: falha para {usuario} | {e}")
        return []
    finally:
        c.close()


def encerrar_sessao(ator, sessao_id):
    """Closes ONE open session by id and audits it. Returns (ok, msg)."""
    try:
        c = _central()
    except Exception as e:
        _log().exception(f"encerrar_sessao: falha ao abrir conexão central | {e}")
        return False, "Falha ao conectar no banco central"
    try:
        cur = c.cursor()
        cur.execute("SELECT usuario FROM tb_sessoes WHERE id=? AND logout_timestamp IS NULL", (sessao_id,))
        row = cur.fetchone()
        if not row:
            return False, "Sessão já encerrada"
        cur.execute("UPDATE tb_sessoes SET logout_timestamp=datetime('now','localtime') WHERE id=?", (sessao_id,))
        c.commit()
        _audit(ator, "encerrar_sessao", row[0], f"sessão #{sessao_id}")
        _log().info(f"sessão encerrada: #{sessao_id} de {row[0]} por {ator}")
        return True, "Sessão encerrada"
    except Exception as e:
        _log().exception(f"encerrar_sessao: falha ao encerrar sessão #{sessao_id} | {e}")
        return False, "Erro inesperado ao encerrar sessão"
    finally:
        c.close()


def encerrar_todas_sessoes(ator, user_nome):
    """Closes ALL open sessions of the user and audits the bulk action."""
    try:
        _fechar_sessoes_central(user_nome)
        _audit(ator, "encerrar_todas_sessoes", user_nome)
        return True, f"Sessões de {user_nome} encerradas"
    except Exception as e:
        _log().exception(f"encerrar_todas_sessoes: falha para {user_nome} | {e}")
        return False, "Erro inesperado ao encerrar sessões"


# ================= VÍNCULOS ÓRFÃOS =================

def listar_vinculos_orfaos(chaves_ativas):
    """Acessos apontando para módulos que não existem mais no sistema."""
    conn = _conexao_segura()
    if conn is None:
        return []
    try:
        cur = conn.cursor()
        cur.execute("SELECT user_nome, modulo_chave, papel FROM tb_acesso_usuario")
        return [(u, m, p) for u, m, p in cur.fetchall() if m not in chaves_ativas]
    except Exception as e:
        _log().exception(f"listar_vinculos_orfaos: falha ao listar vínculos | {e}")
        return []
    finally:
        conn.close()


# ================= COMPATIBILIDADE =================

PERFIS_VALIDOS = PERFIS_GLOBAIS
DB_PATH = DB_CAD_PATH


def validar_acesso_modulo_compat(user_nome, modulo_chave):
    """Backward-compatible alias of `validar_acesso_modulo`."""
    return validar_acesso_modulo(user_nome, modulo_chave)


init_db()
