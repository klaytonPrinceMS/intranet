import bcrypt
import os
import hashlib

import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from mod_intranet.conexao_bd import get_connection
from mod_intranet.manipulador_bd import audit_log

SESSION_COOKIE_NAME = "intranet_session"

# (chave, nome_exibicao, icone, rota) — SEMENTE: módulos nativos do código.
# O cadastro REAL vive em tb_modulos (BD central) e pode crescer via administração.
MODULOS_SISTEMA = [
    ("blog", "Blog", "article", "/blog"),
    ("usuarios", "Usuários", "manage_accounts", "/users"),
    ("auditoria", "Auditoria", "history", "/auditoria"),
    ("editar_pdf", "Editor PDF", "picture_as_pdf", "/edit-pdf"),
    ("empenhos", "Empenhos", "folder_open", "/renomear-empenho"),
    ("solicita_impressao", "Solicitação de Impressão", "print", "/solicita-impressao"),
]

CHAVE_POR_ROTA = {rota.strip("/"): chave for chave, _, _, rota in MODULOS_SISTEMA}

_modulos_ok = False


def _garantir_tb_modulos():
    """Cria/popula tb_modulos uma única vez por processo."""
    global _modulos_ok
    if _modulos_ok:
        return
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tb_modulos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chave TEXT NOT NULL UNIQUE,
                nome TEXT NOT NULL,
                icone TEXT DEFAULT 'extension',
                rota TEXT NOT NULL,
                ativo INTEGER NOT NULL DEFAULT 1,
                nativo INTEGER NOT NULL DEFAULT 0
            )
        """)
        for chave, nome, icone, rota in MODULOS_SISTEMA:
            cur.execute(
                "INSERT OR IGNORE INTO tb_modulos (chave, nome, icone, rota, nativo) VALUES (?, ?, ?, ?, 1)",
                (chave, nome, icone, rota),
            )
        conn.commit()
        _modulos_ok = True
    finally:
        conn.close()


def nome_do_modulo(chave):
    """Nome de exibição cadastrado para a página (editável em Configurações)."""
    _garantir_tb_modulos()
    conn = get_connection()
    try:
        row = conn.execute("SELECT nome FROM tb_modulos WHERE chave=?", (chave,)).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def modulos_registrados(somente_ativos=False):
    """[(chave, nome, icone, rota, ativo)] — TODOS os módulos cadastrados,
    incluindo os registrados depois (nativos ou criados pelo administrador)."""
    _garantir_tb_modulos()
    conn = get_connection()
    try:
        cur = conn.cursor()
        sql = "SELECT chave, nome, icone, rota, ativo FROM tb_modulos"
        if somente_ativos:
            sql += " WHERE ativo=1"
        sql += " ORDER BY nativo DESC, nome"
        cur.execute(sql)
        return cur.fetchall()
    finally:
        conn.close()


def registrar_modulo(ator, chave, nome, icone="extension", rota="#", ativo=False):
    """Cadastra um módulo NOVO (futuro). Por padrão nasce INDISPONÍVEL até que
    o administrador o ative (quando a rota/página passar a existir).
    Aparece imediatamente nas liberações de usuário."""
    chave = (chave or "").strip().lower().replace(" ", "_")
    if not chave or not nome:
        return False, "Chave e nome são obrigatórios"
    _garantir_tb_modulos()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO tb_modulos (chave, nome, icone, rota, ativo, nativo) VALUES (?, ?, ?, ?, ?, 0)",
            (chave, nome.strip(), icone.strip() or "extension", rota.strip() or "#",
             1 if ativo else 0),
        )
        conn.commit()
        audit_log(ator, "intranet", "registrar_modulo",
                  f"{chave} ({nome}) rota={rota} {'ativo' if ativo else 'indisponível'}")
        return True, f"Módulo '{nome}' registrado — já disponível nas liberações"
    except Exception:
        return False, f"Chave '{chave}' já existe"
    finally:
        conn.close()


def excluir_modulo(ator, chave):
    """Remove módulo NÃO-nativo do cadastro."""
    _garantir_tb_modulos()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT nativo FROM tb_modulos WHERE chave=?", (chave,))
        row = cur.fetchone()
        if not row:
            return False, "Módulo não encontrado"
        if row[0]:
            return False, "Módulos nativos do código não podem ser excluídos"
        cur.execute("DELETE FROM tb_modulos WHERE chave=?", (chave,))
        conn.commit()
        audit_log(ator, "intranet", "excluir_modulo", chave)
        return True, f"Módulo '{chave}' removido do cadastro"
    finally:
        conn.close()


def set_modulo_ativo(ator, chave, ativo=True):
    _garantir_tb_modulos()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE tb_modulos SET ativo=? WHERE chave=?", (1 if ativo else 0, chave))
        conn.commit()
        audit_log(ator, "intranet", "modulo_desativado" if not ativo else "moduloreativado", chave)
    finally:
        conn.close()


def chaves_nativas():
    """Chaves dos módulos nativos do código (não excluíveis via interface)."""
    _garantir_tb_modulos()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT chave FROM tb_modulos WHERE nativo=1")
        return {r[0] for r in cur.fetchall()}
    finally:
        conn.close()


def verificar_senha(texto_plano, hash_senha):
    return bcrypt.checkpw(texto_plano.encode("utf-8"), hash_senha.encode("utf-8"))


def gerar_hash_senha(senha_plana):
    return bcrypt.hashpw(senha_plana.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _gest():
    from mod_gest_cad_usuario import manipulador_bd as g
    return g


def usuario_existe(user_nome):
    """Retorna (senha_hash, perfil, ativo) ou None — lê o BD do módulo de usuários."""
    row = _gest().obter_usuario(user_nome)
    if not row:
        return None
    # obter_usuario: id, nome, senha, email, fone, perfil, ativo, data
    return (row[2], row[5], row[6])


def autenticar(user_nome, senha):
    """Retorna (ok: bool, msg: str). Em caso de sucesso msg é o perfil."""
    if not user_nome or not senha:
        return False, "Informe usuário e senha"
    row = usuario_existe(user_nome.strip())
    if not row:
        return False, "Usuário ou senha inválidos"
    senha_bd, perfil, ativo = row
    try:
        if not verificar_senha(senha, senha_bd):
            audit_log(user_nome, "intranet", "login_falha", f"Tentativa de login inválida para {user_nome}")
            return False, "Usuário ou senha inválidos"
    except Exception:
        return False, "Erro interno ao validar credenciais"
    if not ativo:
        return False, "Usuário bloqueado. Procure o administrador."
    return True, perfil


def _podar_sessoes(user_nome):
    """Retenção LGPD: mantém as N sessões mais recentes por usuário.

    Configuração 'sessao_retencao' na tb_config central (padrão 50;
    valor 0 = manter para sempre — para uso futuro numa tela de opções)."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT valor FROM tb_config WHERE chave='sessao_retencao'")
        row = cur.fetchone()
        limite = int(row[0]) if row and str(row[0]).strip().lstrip("-").isdigit() else 50
        if limite <= 0:
            conn.close()
            return
        cur.execute(
            """DELETE FROM tb_sessoes WHERE usuario=? AND id NOT IN (
                   SELECT id FROM tb_sessoes WHERE usuario=?
                   ORDER BY id DESC LIMIT ?)""",
            (user_nome, user_nome, limite),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def registrar_login(user_nome, modulo=""):
    from .manipulador_bd import garantir_rastreabilidade
    from .contexto import contexto_atual, rotulo_dispositivo, mac_best_effort
    garantir_rastreabilidade()
    ctx = contexto_atual()
    ip = ctx.get("ip")
    ua = ctx.get("ua")
    dispositivo = rotulo_dispositivo(ua) if ua else None
    mac = mac_best_effort(ip)
    conn = get_connection()
    try:
        cur = conn.cursor()
        timestamp = __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # segredo por sessão: timestamp tem 1s de resolução e colidia entre navegadores
        cookie_hash = hashlib.sha256(
            f"{user_nome}|{timestamp}|{__import__('secrets').token_hex(16)}".encode()
        ).hexdigest()[:16]
        cur.execute(
            """INSERT INTO tb_sessoes
               (usuario, modulo, login_timestamp, cookie_hash, ip, user_agent, dispositivo, mac)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_nome, modulo, timestamp, cookie_hash, ip, ua, dispositivo, mac),
        )
        conn.commit()
        audit_log(user_nome, "intranet", "login",
                  f"Login realizado ({modulo or 'sistema'})"
                  + (f" de {ip}" if ip else ""))
        return cookie_hash
    finally:
        conn.close()
        _podar_sessoes(user_nome)


def sessao_ativa(user_nome, cookie_hash):
    """True se existe linha de sessão ABERTA com esse hash no banco central.
    Usado pelo guard para revogar navegadores vivos quando o admin encerra
    a sessão (individual ou 'todas')."""
    if not cookie_hash:
        return False
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT 1 FROM tb_sessoes
               WHERE usuario=? AND cookie_hash=? AND logout_timestamp IS NULL LIMIT 1""",
            (user_nome, cookie_hash),
        )
        return cur.fetchone() is not None
    finally:
        conn.close()


def registrar_logout(user_nome, cookie_hash=None):
    """Fecha a sessão deste navegador; sem hash, fecha todas (comportamento antigo)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        if cookie_hash:
            cur.execute(
                "UPDATE tb_sessoes SET logout_timestamp=datetime('now','localtime') "
                "WHERE usuario=? AND cookie_hash=? AND logout_timestamp IS NULL",
                (user_nome, cookie_hash),
            )
        else:
            cur.execute(
                "UPDATE tb_sessoes SET logout_timestamp=datetime('now','localtime') "
                "WHERE usuario=? AND logout_timestamp IS NULL",
                (user_nome,),
            )
        conn.commit()
        audit_log(user_nome, "intranet", "logout", "Logout realizado")
    finally:
        conn.close()


def precisa_trocar_senha(user_nome):
    """Verifica flag de troca obrigatória de senha (primeiro acesso)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT valor FROM tb_config WHERE chave=?", (f"forcar_troca:{user_nome}",))
        row = cur.fetchone()
        return bool(row and row[0] == "1")
    finally:
        conn.close()


def usuarios_com_troca_pendente():
    """Conjunto de usuários com senha provisória ainda não trocada."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT chave FROM tb_config WHERE valor='1' AND chave LIKE 'forcar\\_troca:%' ESCAPE '\\'")
        return {r[0].split(":", 1)[1] for r in cur.fetchall()}
    finally:
        conn.close()


def marcar_trocar_senha(user_nome, forcar=True):
    conn = get_connection()
    try:
        cur = conn.cursor()
        valor = "1" if forcar else "0"
        cur.execute(
            "INSERT OR REPLACE INTO tb_config (chave, valor) VALUES (?, ?)",
            (f"forcar_troca:{user_nome}", valor),
        )
        conn.commit()
    finally:
        conn.close()


def trocar_senha_propria(user_nome, senha_atual, nova_senha):
    ok, msg = autenticar(user_nome, senha_atual)
    if not ok:
        return False, "Senha atual incorreta"
    if len(nova_senha) < 6:
        return False, "Nova senha deve ter no mínimo 6 caracteres"
    gest = _gest()
    conn = gest.get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE tb_usuarios SET user_senha=? WHERE user_nome=?",
            (gerar_hash_senha(nova_senha), user_nome),
        )
        conn.commit()
    finally:
        conn.close()
    marcar_trocar_senha(user_nome, False)
    audit_log(user_nome, "gest_cad_usuario", "trocar_senha", "Usuário alterou a própria senha")
    return True, "Senha alterada com sucesso"


def editar_meu_perfil(user_nome, email="__NULO__", fone="__NULO__",
                      nome_completo="__NULO__"):
    """Autoatendimento: usuário edita próprios dados pessoais (nunca permissões)."""
    return _gest().editar_usuario(user_nome, user_nome, email=email, fone=fone,
                                  nome_completo=nome_completo)


def nome_de_tratamento(user_nome):
    """Nome exibido para tratamento do usuário (nome completo ou social)."""
    return _gest().nome_de_tratamento(user_nome)


# ================= MÓDULOS / ACESSOS =================

def chaves_desativadas():
    """Chaves de módulos marcados como removidos/desativados."""
    return {c for c, n, i, r, a in modulos_registrados() if not a}


def set_chaves_desativadas(ator, chaves):
    """Compatibilidade: define quais chaves ficam desativadas; demais reativadas."""
    alvo = set(chaves)
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT chave FROM tb_modulos")
        for (c,) in cur.fetchall():
            cur.execute("UPDATE tb_modulos SET ativo=? WHERE chave=?",
                        (0 if c in alvo else 1, c))
        conn.commit()
        audit_log(ator, "intranet", "modulos_desativados", ",".join(sorted(alvo)) or "(nenhum)")
    finally:
        conn.close()


def chaves_ativas():
    return [c for c, n, i, r, a in modulos_registrados(somente_ativos=True)]


def papel_no_modulo(user_nome, modulo_chave):
    """'administrador', 'comum' ou None. Delega ao módulo de usuários."""
    try:
        return _gest().obter_papel_no_modulo(user_nome, modulo_chave)
    except Exception:
        return None


def eh_admin_do_modulo(user_nome, modulo_chave):
    return papel_no_modulo(user_nome, modulo_chave) == "administrador"


def perfil_global_de(user_nome):
    """Perfil global do usuário ('comum'|'administrador_modulo'|'administrador_geral')."""
    row = usuario_existe(user_nome)
    return row[1] if row else None


def pode_publicar_no_blog(user_nome):
    """Usuário comum só lê o blog; publicar/comentar/excluir é de administradores."""
    if perfil_global_de(user_nome) == "administrador_geral":
        return True
    return eh_admin_do_modulo(user_nome, "blog")


def validar_acesso_modulo(user_nome, modulo_chave):
    try:
        return _gest().validar_acesso_modulo(user_nome, modulo_chave)
    except Exception:
        return False


def listar_modulos_permitidos(user_nome):
    """Módulos ATIVOS liberados para o usuário (chave, nome, ícone, rota)."""
    row = usuario_existe(user_nome)
    if not row or not row[2]:
        return []
    ativos = {(c, n, i, r) for c, n, i, r, a in modulos_registrados(somente_ativos=True)}
    return [m for m in sorted(ativos) if validar_acesso_modulo(user_nome, m[0])]


def modulos_do_usuario(user_nome):
    """[(chave, nome, icone, rota, ativa)] — TODOS os módulos registrados aos quais
    o usuário tem vínculo; módulos desativados vêm sinalizados (ativa=False),
    para que a interface os destaque com alerta (README linha 45)."""
    row = usuario_existe(user_nome)
    if not row or not row[2]:
        return []
    resultado = []
    for chave, nome, icone, rota, ativo in modulos_registrados():
        if validar_acesso_modulo(user_nome, chave):
            resultado.append((chave, nome, icone, rota, bool(ativo)))
    return resultado
