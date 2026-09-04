"""Teste do fluxo completo de autenticação — Fase 2.5.

Valida a sequência end-to-end de login e gestão de conta:
  login → senha provisória → troca obrigatória no 1º acesso →
  sessão/logout com revogação → trilha de auditoria central → soft delete.

O teste é AUTOCONTIDO: cria um usuário COM NOME ÚNICO (sufixo timestamp),
roda todo o fluxo sobre ele e o remove definitivamente ao final (LGPD) —
não altera nem depende do estado mutável do `master` real (senha/flag), para
não destruir dados do desenvolvedor. O `master` só é consultado via perfil.

Script standalone (NÃO pytest):
    .venv/bin/python test/teste_fluxo_autenticacao.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mod_intranet.mod_intranet_inicializacao_bd import inicializar_bancos  # noqa: E402
from mod_intranet import autenticacao as auth  # noqa: E402
from mod_gest_cad_usuario import manipulador_bd as gest  # noqa: E402
from mod_auditoria.manipulador_bd import get_auditoria_connection  # noqa: E402


def _conta_auditoria(tabela, acao, usuario):
    conn = get_auditoria_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) FROM {tabela} WHERE acao=? AND usuario=?",
                    (acao, usuario))
        return cur.fetchone()[0]
    finally:
        conn.close()


def ok(cond, msg):
    global _OK
    _OK += 1
    print(f"  {'OK' if cond else 'FALHOU'} [{_OK}] {msg}")
    return bool(cond)


_OK = 0
print("INICIANDO TESTES — Fluxo de autenticação (Fase 2.5)")
inicializar_bancos()

SUFIXO = f"qa{int(time.time() * 1000) % 100000}"
USUARIO = f"fluxo_{SUFIXO}"
PROVISORIA = "Provi@123"
NOVA = "Nova@4567"

# 1) conta master existe com perfil administrador_geral (consulta imutável)
linha = auth.usuario_existe("master")
ok(linha is not None and linha[1] == "administrador_geral",
   "master existe como administrador_geral")

# 2) criar usuário com senha provisória (fluxo de 1º acesso)
ok_criar, msg_criar = gest.criar_usuario(
    "master", USUARIO, PROVISORIA, email="qa@teste.local",
    perfil="comum", nome_completo="Usuário de Fluxo QA")
ok(ok_criar, f"criar_usuario com senha provisória ({msg_criar})")

# 3) novo usuário nasce com troca obrigatória de senha
ok(auth.precisa_trocar_senha(USUARIO) is True,
   "novo usuário exige troca de senha no 1º acesso")

# 4) login com a senha provisória funciona (perfil comum)
ok4, p4 = auth.autenticar(USUARIO, PROVISORIA)
ok(ok4 and p4 == "comum", "login com senha provisória → perfil comum")

# 5) senha errada é rejeitada
ok5, _ = auth.autenticar(USUARIO, "senha_errada_x")
ok(not ok5, "senha errada é rejeitada")

# 6) registrar_login cria sessão e devolve cookie_hash
ch = auth.registrar_login(USUARIO, "sistema")
ok(bool(ch) and len(ch) >= 16, "registrar_login devolve cookie_hash de sessão")

# 7) sessão fica ativa
ok(auth.sessao_ativa(USUARIO, ch) is True, "sessao_ativa reconhece sessão aberta")

# 8) auditoria central registra o login (usuário é único → esperado 1)
ok(_conta_auditoria("tb_auditoria_intranet", "login", USUARIO) >= 1,
   "auditoria central registra login")

# 9) trocar senha com atual incorreta falha
r_errada, _ = auth.trocar_senha_propria(USUARIO, "senha_absurda", NOVA)
ok(not r_errada, "trocar_senha_propria rejeita senha atual incorreta")

# 10) nova senha abaixo do mínimo é rejeitada
r_curta, _ = auth.trocar_senha_propria(USUARIO, PROVISORIA, "123")
ok(not r_curta, "nova senha abaixo do mínimo é rejeitada")

# 11) troca obrigatória de senha (1º acesso) bem-sucedida
r_ok, _ = auth.trocar_senha_propria(USUARIO, PROVISORIA, NOVA)
ok(r_ok, "troca de senha obrigatória (1º acesso) bem-sucedida")

# 12) flag de troca desarmada após a troca
ok(auth.precisa_trocar_senha(USUARIO) is False,
   "flag de troca desarmada após a troca")

# 13) login com a nova senha funciona
ok13, _ = auth.autenticar(USUARIO, NOVA)
ok(ok13, "login com a nova senha funciona")

# 14) senha provisória antiga deixa de funcionar
ok14, _ = auth.autenticar(USUARIO, PROVISORIA)
ok(not ok14, "senha provisória antiga é rejeitada")

# 15) logout encerra a sessão
auth.registrar_logout(USUARIO, ch)
ok(auth.sessao_ativa(USUARIO, ch) is False,
   "logout encerra a sessão (sessao_ativa False)")

# 16) auditoria central registra logout
ok(_conta_auditoria("tb_auditoria_intranet", "logout", USUARIO) >= 1,
   "auditoria central registra logout")

# 17) usuário inativo/soft deixa de autenticar
gest.soft_delete_usuario("master", USUARIO, motivo="limpeza de teste QA")
ok17, _ = auth.autenticar(USUARIO, NOVA)
ok(not ok17, "usuário soft-deletado não autentica")

# 18) soft delete marca user_deletado=1 e ativo=0
row = gest.obter_usuario(USUARIO)
ok(row is not None and row[8] == 1 and row[6] == 0,
   "soft_delete_usuario marca user_deletado=1 e ativo=0")

# 19) restauração do soft delete (desbloquear restaura a conta)
rr, _ = gest.bloquear_usuario("master", USUARIO, bloquear=False)
row2 = gest.obter_usuario(USUARIO)
ok(rr and row2 is not None and row2[8] == 0 and row2[6] == 1,
   "desbloquear restaura o soft delete (deletado=0, ativo=1)")

# ===== limpeza (LGPD): remove definitivamente o usuário de teste =====
try:
    gest.excluir_usuario_definitivo("master", USUARIO)
except Exception:
    pass

print(f"\nTODOS OS TESTES PASSARAM — {_OK} verificações ✅")
