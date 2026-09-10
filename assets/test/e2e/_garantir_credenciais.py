"""Garante as credenciais dos usuários QA usados nos testes E2E.

EN: Ensures the QA credentials used by the Playwright E2E suite
    (qacomum/qamaster = 123456), resets the forced password-change flag and
    fixes the global profile. Idempotent — safe to run on every run.
PT: Garante as credenciais dos usuários QA usados na suíte E2E do
    Playwright (qacomum/qamaster = 123456), limpa a flag de troca obrigatória
    de senha e reafirma o perfil global. Idempotente — seguro executar a cada
    execução.

Executado automaticamente pelo global setup (`_global_setup.js`).
"""
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, RAIZ)
os.chdir(RAIZ)

from mod_intranet import autenticacao  # noqa: E402

# (usuário, senha) — perfil: qacomum=comum, qamaster=administrador_geral
USUARIOS = [("qacomum", "123456"), ("qamaster", "123456")]


def garantir():
    """Idempotently fixes QA users' passwords, profiles and change flag."""
    from mod_gest_cad_usuario import bd_manipulador as gest
    conn = gest.get_connection()
    try:
        cur = conn.cursor()
        for user, senha in USUARIOS:
            perfil = "comum" if user == "qacomum" else "administrador_geral"
            cur.execute(
                "UPDATE tb_usuarios SET user_senha=?, user_perfil=? "
                "WHERE user_nome=?",
                (autenticacao.gerar_hash_senha(senha), perfil, user))
        conn.commit()
    finally:
        conn.close()
    for user, _ in USUARIOS:
        autenticacao.marcar_trocar_senha(user, forcar=False)
    print(f"credenciais QA garantidas: {USUARIOS}")


if __name__ == "__main__":
    try:
        garantir()
    except Exception as exc:  # fail-soft: testes seguem, login pode falhar
        print(f"[aviso] falha ao garantir credenciais QA: {exc}")