"""Teste de papéis/validacão de acesso do ator (mod_intranet/autenticacao.py).

Cobre a regra "validar papel do ator antes de escrita" no nível do núcleo:
- `gerar_hash_senha`/`verificar_senha` (roundtrip + recusa);
- `papel_no_modulo`, `eh_admin_do_modulo`, `validar_acesso_modulo`,
  `perfil_global_de`, `listar_modulos_permitidos`, `modulos_do_usuario`
  para o master (administrador_geral vê tudo);
- ciclo conceder -> refletir -> revogar para usuário temporário (via
  mod_gest_cad_usuario, com remoção definitiva ao final — LGPD);
- `chaves_desativadas`/`set_chaves_desativadas`/`chaves_ativas` com
  snapshot/restore de tb_modulos (como teste_aba_config_intranet.py).

AUTOCONTIDO: usuário COM NOME ÚNICO removido ao final.

Execute: .venv/bin/python assets/test/test_autenticacao_papeis.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from mod_intranet.bd_criador import inicializar_bancos  # noqa: E402
from mod_intranet import autenticacao as auth  # noqa: E402
from mod_gest_cad_usuario import bd_manipulador as gest  # noqa: E402

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


print("INICIANDO TESTES — papéis do ator (mod_intranet/autenticacao.py)")
inicializar_bancos()

conn = auth.get_connection()
try:
    MOD_SNAP = list(conn.execute(
        "SELECT chave, nome, icone, rota, ativo, nativo, ordem "
        "FROM tb_modulos"))
finally:
    conn.close()

SUFIXO = f"qa{int(time.time() * 1000) % 100000}"
USUARIO = f"papel_{SUFIXO}"

try:
    # ---------- hash/senha (puro) ----------
    print("-- senha --")
    h = auth.gerar_hash_senha("Segredo@123")
    check(auth.verificar_senha("Segredo@123", h) is True,
          "verificar_senha aprova a senha correta")
    check(auth.verificar_senha("Errada@123", h) is False,
          "verificar_senha recusa senha errada")

    # ---------- master: administrador geral vê tudo ----------
    print("-- master --")
    check(auth.perfil_global_de("master") == "administrador_geral",
          "perfil_global_de(master) é administrador_geral")
    check(auth.eh_admin_do_modulo("master", "blog") is True,
          "master é admin do blog (poder global)")
    check(auth.validar_acesso_modulo("master", "blog") is True,
          "master passa em validar_acesso_modulo")
    perms = auth.listar_modulos_permitidos("master")
    chaves_perms = {m[0] for m in perms}
    check("blog" in chaves_perms and "usuarios" in chaves_perms,
          "master tem todos os módulos permitidos")
    check(auth.papel_no_modulo("usuario_que_nao_existe", "blog") is None,
          "papel_no_modulo de desconhecido é None")

    # ---------- ciclo conceder/refletir/revogar ----------
    print("-- ciclo de papel --")
    ok_criar, _ = gest.criar_usuario(
        "master", USUARIO, "Provi@123", email="papel@teste.local",
        perfil="comum", nome_completo="Usuário Papel QA")
    check(ok_criar, "usuário temporário criado")
    check(auth.papel_no_modulo(USUARIO, "blog") is None,
          "usuário novo sem papel no blog")
    check(auth.validar_acesso_modulo(USUARIO, "blog") is False,
          "sem papel, validar_acesso_modulo é False (nega por padrão)")
    check(auth.eh_admin_do_modulo(USUARIO, "blog") is False,
          "usuário comum não é admin do módulo")
    ok_conc, _ = gest.definir_acesso("master", USUARIO, "blog", "comum")
    check(ok_conc, "concessão de papel comum no blog")
    check(auth.papel_no_modulo(USUARIO, "blog") == "comum",
          "papel_no_modulo reflete a concessão")
    check(auth.validar_acesso_modulo(USUARIO, "blog") is True,
          "com papel, validar_acesso_modulo é True")
    check("blog" in {m[0] for m in auth.modulos_do_usuario(USUARIO)},
          "modulos_do_usuario inclui o módulo concedido")
    ok_rev, _ = gest.remover_acesso("master", USUARIO, "blog")
    check(ok_rev, "revogação do acesso")
    check(auth.validar_acesso_modulo(USUARIO, "blog") is False,
          "após revogar, validar_acesso_modulo volta a False")

    # ---------- desativação de módulos ----------
    print("-- chaves ativas/desativadas --")
    auth.set_chaves_desativadas("master", [])
    check("blog" in auth.chaves_ativas(),
          "com nada desativado, blog está ativo")
    auth.set_chaves_desativadas("master", ["blog"])
    check("blog" in auth.chaves_desativadas()
          and "blog" not in auth.chaves_ativas(),
          "blog desativado sai de chaves_ativas")
    check(auth.validar_acesso_modulo(USUARIO, "blog") is False,
          "módulo desativado nega acesso mesmo sem papel")
finally:
    try:
        gest.excluir_usuario_definitivo("master", USUARIO)
    except Exception:
        pass
    try:
        conn = auth.get_connection()
        try:
            for chave, nome, icone, rota, ativo, nativo, ordem in MOD_SNAP:
                conn.execute(
                    "UPDATE tb_modulos SET nome=?, icone=?, rota=?, ativo=?, "
                    "nativo=?, ordem=? WHERE chave=?",
                    (nome, icone, rota, ativo, nativo, ordem, chave))
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass
    try:
        check(not gest.usuario_existe(USUARIO),
              "usuário temporário removido definitivamente (LGPD)")
    except Exception:
        pass

print(f"RESULTADO: {_OK} OK, {_TOTAL - _OK} falha(s) de {_TOTAL} verificações")
sys.exit(0 if _OK == _TOTAL else 1)
