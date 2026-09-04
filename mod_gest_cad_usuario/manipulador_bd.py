"""Módulo Gestão de Cadastro de Usuários — soft CRUD completo.

BD próprio: db_mod_gest_cad_usuario.db (WAL).
Tabelas: tb_usuarios, tb_acesso_usuario (perfis POR módulo), tb_modulo_perfil.
Auditoria central com ATOR (quem fez) conforme LGPD.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_CAD_PATH = os.path.join(BASE_DIR, "db_mod_gest_cad_usuario.db")

PERFIS_GLOBAIS = ["comum", "administrador_modulo", "administrador_geral"]
PAPEIS_MODULO = ["comum", "administrador"]


def get_connection():
    conn = sqlite3.connect(DB_CAD_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _central():
    from mod_intranet.conexao_bd import get_connection as gc
    return gc()


def _audit(ator, acao, alvo, detalhe=""):
    from mod_intranet.manipulador_bd import audit_log
    audit_log(ator or "sistema", "gest_cad_usuario", acao,
              f"Alvo: {alvo}" + (f" | {detalhe}" if detalhe else ""))


def _log():
    """Logger central (loguru) — arquivo dedicado logs/gest_cad_usuario_<data>.log."""
    from mod_intranet import observabilidade
    return observabilidade.get_logger("gest_cad_usuario")


def senha_minima():
    """Política de senha mínima (em caracteres) do módulo, editável em
    tb_config central na chave 'usuarios_senha_min' (painel Administração)."""
    try:
        from mod_intranet.conexao_bd import get_config
        return max(4, int(get_config("usuarios_senha_min", "6")))
    except Exception as e:
        _log().warning(f"senha_minima: falha ao ler config; usando padrão 6 | {e}")
        return 6


def init_db():
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
    # depois que ele trocar, a flag nunca mais é rearmada.
    try:
        from mod_intranet import autenticacao as _auth
        linha = _auth.usuario_existe("master")
        if linha and _auth.verificar_senha("master", linha[0]):
            _auth.marcar_trocar_senha("master", True)
    except Exception as e:
        _log().exception(f"init_db: falha ao verificar senha padrão do master | {e}")

    # Garante master
    if not obter_usuario("master"):
        from mod_intranet.autenticacao import gerar_hash_senha, marcar_trocar_senha
        conn = get_connection(); cur = conn.cursor()
        cur.execute(
            "INSERT INTO tb_usuarios (user_nome, user_senha, user_perfil, user_ativo) VALUES (?, ?, 'administrador_geral', 1)",
            ("master", gerar_hash_senha("master")),
        )
        conn.commit(); conn.close()
        marcar_trocar_senha("master", True)

    # Garante usuários de teste de QA (docs) — qacomum (comum) e qamaster (administrador_geral)
    from mod_intranet.autenticacao import gerar_hash_senha, marcar_trocar_senha
    conn = get_connection(); cur = conn.cursor()
    if not obter_usuario("qacomum"):
        cur.execute(
            "INSERT INTO tb_usuarios (user_nome, user_senha, user_perfil, user_ativo, user_nome_completo) VALUES (?, ?, 'comum', 1, ?)",
            ("qacomum", gerar_hash_senha("123456"), "Usuário de Teste QA Comum"),
        )
        for chave in ("blog", "editar_pdf", "empenhos"):
            cur.execute(
                "INSERT OR IGNORE INTO tb_acesso_usuario (user_nome, modulo_chave, papel, liberado_por) VALUES (?, ?, 'comum', 'sistema')",
                ("qacomum", chave),
            )
        conn.commit()
        marcar_trocar_senha("qacomum", True)
    if not obter_usuario("qamaster"):
        cur.execute(
            "INSERT INTO tb_usuarios (user_nome, user_senha, user_perfil, user_ativo, user_nome_completo) VALUES (?, ?, 'administrador_geral', 1, ?)",
            ("qamaster", gerar_hash_senha("123456"), "Usuário de Teste QA Master"),
        )
        conn.commit()
        marcar_trocar_senha("qamaster", True)
    conn.close()


# ================= CONSULTAS =================

def listar_usuarios(filtro_ativo=None):
    conn = get_connection()
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
        return cur.fetchall()
    finally:
        conn.close()


def obter_usuario(user_nome):
    conn = get_connection()
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
    finally:
        conn.close()


def nome_de_tratamento(user_nome):
    """Nome usado para tratamento nas telas — nome completo ou social.
    Cai para o login se o campo ainda não foi preenchido."""
    row = obter_usuario(user_nome)
    return (row[9] or "").strip() if row and row[9] else user_nome


def listar_acessos(user_nome):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT modulo_chave, papel, liberado_por, data_liberacao
               FROM tb_acesso_usuario WHERE user_nome=? ORDER BY modulo_chave""",
            (user_nome,),
        )
        return cur.fetchall()
    finally:
        conn.close()


# ================= CRUD =================

def _validar_nome_completo(nome_completo, user_nome):
    nc = (nome_completo or "").strip()
    if len(nc) < 3:
        return None, "Nome completo/social é obrigatório (mín. 3 caracteres)"
    if nc.lower() == (user_nome or "").strip().lower():
        return None, "O nome de exibição deve ser diferente do nome de login"
    return nc, None


def criar_usuario(ator, user_nome, senha, email=None, fone=None, perfil="comum",
                  nome_completo=""):
    from mod_intranet.autenticacao import gerar_hash_senha, marcar_trocar_senha
    if not user_nome or not user_nome.strip():
        return False, "Nome de usuário é obrigatório"
    if len(senha or "") < senha_minima():
        return False, f"Senha provisória deve ter no mínimo {senha_minima()} caracteres"
    if perfil not in PERFIS_GLOBAIS:
        return False, f"Perfil inválido: {perfil}"
    nome_c, erro = _validar_nome_completo(nome_completo, user_nome)
    if erro:
        return False, erro
    conn = get_connection()
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
        conn.commit()
        marcar_trocar_senha(user_nome.strip(), True)
        _audit(ator, "criar_usuario", user_nome.strip(), f"perfil={perfil} | exibição: {nome_c}")
        _log().info(f"usuário criado: {user_nome.strip()} perfil={perfil} por {ator}")
        return True, "Usuário criado (senha provisória — troca obrigatória no 1º acesso)"
    except sqlite3.IntegrityError:
        _log().warning(f"criar_usuario: nome já existe: {user_nome}")
        return False, "Nome de usuário já existe"
    finally:
        conn.close()


def editar_usuario(ator, user_nome, email="__NULO__", fone="__NULO__",
                   perfil=None, ativo=None, deletado=None, nome_completo="__NULO__",
                   auditar=True):
    """Edita dados pessoais/perfil global. Use '__NULO__' p/ manter campo."""
    conn = get_connection()
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
        cur.execute(f"UPDATE tb_usuarios SET {', '.join(sets)} WHERE user_nome=?", tuple(params))
        conn.commit()
        if auditar:
            _audit(ator, "editar_usuario", user_nome, ", ".join(mudancas))
        _log().info(f"usuário editado: {user_nome} | {', '.join(mudancas)} por {ator}")
        return True, "Usuário atualizado"
    finally:
        conn.close()


def renomear_usuario(ator, nome_atual, novo_nome):
    """Renomeia mantendo o ID (chave primária), replicando nas tabelas dependentes."""
    novo_nome = (novo_nome or "").strip()
    if not novo_nome:
        return False, "Novo nome vazio"
    if nome_atual == "master":
        return False, "A conta master nativa não pode ser renomeada"
    conn = get_connection()
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
    finally:
        conn.close()


def alterar_senha_admin(ator, user_nome, nova_senha):
    """Troca administrativa de senha (reenvio provisório)."""
    if len(nova_senha or "") < senha_minima():
        return False, f"Mínimo {senha_minima()} caracteres"
    from mod_intranet.autenticacao import gerar_hash_senha, marcar_trocar_senha
    conn = get_connection()
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
    finally:
        conn.close()


def bloquear_usuario(ator, user_nome, bloquear=True):
    """Bloqueia (ativo=0). Desbloquear também restaura soft-delete."""
    if ator == user_nome and bloquear:
        return False, "Você não pode bloquear a si mesmo"
    kw = {"deletado": False} if not bloquear else {}
    # 'auditar=False': a ação ganha trilha DEDICADA abaixo (bloquear_usuario ou
    # desbloquear_usuario) em vez de um 'editar_usuario' genérico.
    ok, msg = editar_usuario(ator, user_nome, ativo=(not bloquear), auditar=False, **kw)
    if ok:
        if not bloquear:  # restauração limpa o motivo da exclusão lógica
            conn = get_connection()
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
    ok, msg = editar_usuario(ator, user_nome, ativo=False, deletado=True)
    if not ok:
        return ok, msg
    conn = get_connection()
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


def _vinculos_cruzados_excluir(user_nome):
    """Remove/anonimiza referências do usuário nos demais módulos (LGPD).
    Blog: postagens e comentários apagados. EditorPDF: arquivos físicos,
    registros e cota apagados. Empenhos: registros públicos preservados
    com autoria anonimizada."""
    det = []
    try:
        # Blog tem banco próprio (db_mod_blog.db); o central guarda cópia legada
        blog_db = os.path.join(BASE_DIR, "db_mod_blog.db")
        if os.path.exists(blog_db):
            c = sqlite3.connect(blog_db)
            cc = c.cursor()
            cc.execute("PRAGMA foreign_keys=ON")
            cc.execute("SELECT id FROM tb_postagens WHERE autor=?", (user_nome,))
            ids = [r[0] for r in cc.fetchall()]
            if ids:
                q = ",".join("?" * len(ids))
                cc.execute(f"DELETE FROM tb_comentarios WHERE postagem_id IN ({q})", ids)
                det.append(f"{len(ids)} postagem(ns)")
            cc.execute("DELETE FROM tb_comentarios WHERE autor=?", (user_nome,))
            cc.execute("DELETE FROM tb_postagens WHERE autor=?", (user_nome,))
            c.commit(); c.close()
        else:  # instalação sem banco do blog ainda: limpa a cópia legada do central
            c = _central(); cc = c.cursor()
            cc.execute("SELECT id FROM tb_postagens WHERE autor=?", (user_nome,))
            ids = [r[0] for r in cc.fetchall()]
            if ids:
                q = ",".join("?" * len(ids))
                cc.execute(f"DELETE FROM tb_comentarios WHERE postagem_id IN ({q})", ids)
                det.append(f"{len(ids)} postagem(ns) (legado)")
            cc.execute("DELETE FROM tb_comentarios WHERE autor=?", (user_nome,))
            cc.execute("DELETE FROM tb_postagens WHERE autor=?", (user_nome,))
            c.commit(); c.close()
    except Exception as e:
        det.append("blog: falhou")
        _log().exception(f"_vinculos_cruzados_excluir: blog falhou para {user_nome} | {e}")
    try:
        pdf_db = os.path.join(BASE_DIR, "db_mod_edit_pdf.db")
        if os.path.exists(pdf_db):
            c = sqlite3.connect(pdf_db); cc = c.cursor()
            cc.execute("SELECT nome_arquivo FROM tb_arquivos WHERE usuario=?", (user_nome,))
            nomes = [r[0] for r in cc.fetchall()]
            pasta = os.path.join(BASE_DIR, "editorPDF")
            removidos = 0
            for nome in nomes:
                fpath = os.path.join(pasta, nome)
                if os.path.exists(fpath):
                    try:
                        os.remove(fpath)
                        removidos += 1
                    except OSError:
                        pass
                cc.execute("DELETE FROM tb_arquivos WHERE usuario=? AND nome_arquivo=?",
                           (user_nome, nome))
            cc.execute("DELETE FROM tb_cota_disco WHERE usuario=?", (user_nome,))
            c.commit(); c.close()
            if removidos or nomes:
                det.append(f"{removidos} arquivo(s) PDF")
    except Exception as e:
        det.append("pdf: falhou")
        _log().exception(f"_vinculos_cruzados_excluir: pdf falhou para {user_nome} | {e}")
    try:
        emp_db = os.path.join(BASE_DIR, "db_mod_renomear_empenho.db")
        if os.path.exists(emp_db):
            c = sqlite3.connect(emp_db); cc = c.cursor()
            cc.execute("UPDATE tb_empenhos SET usuario='(usuário excluído)' WHERE usuario=?",
                       (user_nome,))
            n = cc.rowcount
            c.commit(); c.close()
            if n:
                det.append(f"{n} empenho(s) anonimizado(s)")
    except Exception as e:
        det.append("empenhos: falhou")
        _log().exception(f"_vinculos_cruzados_excluir: empenhos falhou para {user_nome} | {e}")
    return det


def _vinculos_cruzados_renomear(nome_atual, novo_nome):
    """Propaga o renomeio para colunas de autoria nos demais módulos."""
    planos = []
    blog_db = os.path.join(BASE_DIR, "db_mod_blog.db")
    if os.path.exists(blog_db):
        planos.append((sqlite3.connect(blog_db),
                       [("tb_postagens", "autor"), ("tb_comentarios", "autor")]))
    else:
        planos.append((_central(),
                       [("tb_postagens", "autor"), ("tb_comentarios", "autor")]))
    pdf_db = os.path.join(BASE_DIR, "db_mod_edit_pdf.db")
    if os.path.exists(pdf_db):
        planos.append((sqlite3.connect(pdf_db),
                       [("tb_arquivos", "usuario"), ("tb_cota_disco", "usuario")]))
    emp_db = os.path.join(BASE_DIR, "db_mod_renomear_empenho.db")
    if os.path.exists(emp_db):
        planos.append((sqlite3.connect(emp_db), [("tb_empenhos", "usuario")]))
    for conn, tabelas in planos:
        try:
            cc = conn.cursor()
            for tbl, col in tabelas:
                cc.execute(f"UPDATE {tbl} SET {col}=? WHERE {col}=?", (novo_nome, nome_atual))
            conn.commit()
        except Exception as e:
            _log().warning(f"_vinculos_cruzados_renomear: falha ao propagar {nome_atual}->{novo_nome} | {e}")
        finally:
            try:
                conn.close()
            except Exception:
                pass


def excluir_usuario_definitivo(ator, user_nome):
    from mod_intranet import autenticacao  # import tardio: evita ciclo de imports
    if autenticacao.perfil_global_de(ator) != "administrador_geral":
        return False, "Apenas o administrador geral do sistema pode excluir definitivamente (LGPD)"
    if user_nome == "master":
        return False, "A conta master nativa não pode ser excluída"
    if ator == user_nome:
        return False, "Você não pode excluir a própria conta"
    conn = get_connection()
    try:
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
    finally:
        conn.close()


def duplicar_usuario(ator, usuario_origem, novo_nome, senha, email=None,
                     fone=None, nome_completo=""):
    """Duplica um usuário existente e todas as suas configurações de acesso.

    Copia o perfil global e o papel do usuário origem em cada módulo
    (tb_acesso_usuario). O novo usuário é criado exigindo apenas os dados
    essenciais (login, nome, senha e email) — as permissões vêm da origem.
    """
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
    _audit(ator, "duplicar_usuario", novo_nome,
           f"origem={usuario_origem} | perfil={perfil_origem}")
    _log().info(f"usuário duplicado: {novo_nome} a partir de {usuario_origem} por {ator}")
    return True, "Usuário duplicado com as permissões da origem"

# ================= PERFIS POR MÓDULO =================

def definir_acesso(ator, user_nome, modulo_chave, papel):
    """Atribui papel do usuário num módulo ('comum'|'administrador'). None remove."""
    if papel is None:
        return remover_acesso(ator, user_nome, modulo_chave)
    if papel not in PAPEIS_MODULO:
        return False, f"Papel inválido: {papel}"
    conn = get_connection()
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
    finally:
        conn.close()


def remover_acesso(ator, user_nome, modulo_chave):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM tb_acesso_usuario WHERE user_nome=? AND modulo_chave=?",
                    (user_nome, modulo_chave))
        conn.commit()
        _audit(ator, "remover_acesso", user_nome, f"módulo {modulo_chave}")
        _log().info(f"acesso removido: {user_nome} módulo {modulo_chave} por {ator}")
        return True, f"Acesso a '{modulo_chave}' removido"
    finally:
        conn.close()


def obter_papel_no_modulo(user_nome, modulo_chave):
    """Retorna 'administrador', 'comum' ou None."""
    conn = get_connection()
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
    finally:
        conn.close()


def validar_acesso_modulo(user_nome, modulo_chave):
    # RF-35: o módulo de Auditoria é exclusivo do administrador geral do sistema.
    if modulo_chave == "auditoria":
        from mod_intranet import autenticacao
        return autenticacao.perfil_global_de(user_nome) == "administrador_geral"
    return obter_papel_no_modulo(user_nome, modulo_chave) is not None


# ================= SESSÕES ATIVAS =================

def _fechar_sessoes_central(user_nome):
    try:
        c = _central(); cc = c.cursor()
        cc.execute("UPDATE tb_sessoes SET logout_timestamp=datetime('now','localtime') WHERE usuario=? AND logout_timestamp IS NULL",
                   (user_nome,))
        c.commit(); c.close()
    except Exception as e:
        _log().warning(f"_fechar_sessoes_central: falha ao encerrar sessões de {user_nome} | {e}")


def listar_sessoes_ativas(usuario=None):
    """Sessões abertas (sem logout), agora com rastreabilidade IP/dispositivo/MAC."""
    c = _central()
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
    finally:
        c.close()


def contar_sessoes_ativas(usuario):
    c = _central()
    try:
        cur = c.cursor()
        cur.execute("SELECT COUNT(*) FROM tb_sessoes WHERE usuario=? AND logout_timestamp IS NULL",
                    (usuario,))
        return cur.fetchone()[0]
    finally:
        c.close()


def sessoes_ativas_por_usuario():
    """{usuario: qtd_ativas} — uma única consulta para a tabela inteira."""
    c = _central()
    try:
        cur = c.cursor()
        cur.execute("""SELECT usuario, COUNT(*) FROM tb_sessoes
                       WHERE logout_timestamp IS NULL GROUP BY usuario""")
        return dict(cur.fetchall())
    finally:
        c.close()


def listar_historico_sessoes(usuario, limite=10):
    """Últimas sessões ENCERRADAS do usuário (rastreabilidade LGPD)."""
    c = _central()
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
    finally:
        c.close()


def encerrar_sessao(ator, sessao_id):
    c = _central()
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
    finally:
        c.close()


def encerrar_todas_sessoes(ator, user_nome):
    _fechar_sessoes_central(user_nome)
    _audit(ator, "encerrar_todas_sessoes", user_nome)
    return True, f"Sessões de {user_nome} encerradas"


# ================= VÍNCULOS ÓRFÃOS =================

def listar_vinculos_orfaos(chaves_ativas):
    """Acessos apontando para módulos que não existem mais no sistema."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT user_nome, modulo_chave, papel FROM tb_acesso_usuario")
        return [(u, m, p) for u, m, p in cur.fetchall() if m not in chaves_ativas]
    finally:
        conn.close()


# ================= COMPATIBILIDADE =================

PERFIS_VALIDOS = PERFIS_GLOBAIS
DB_PATH = DB_CAD_PATH


def validar_acesso_modulo_compat(user_nome, modulo_chave):
    return validar_acesso_modulo(user_nome, modulo_chave)


init_db()
