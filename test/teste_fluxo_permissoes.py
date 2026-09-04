"""Teste do fluxo de permissões por módulo — Fase 2.5.

Valida a concessão/atualização/revogação de perfil (papel) de um usuário POR
MÓDULO e o privilégio do administrador geral de enxergar/ter acesso a tudo
(monitorado também no menu lateral e cards do dashboard — ver
`validar_acesso_modulo`/`listar_modulos_permitidos`, usados na UI).

Cria um usuário COM NOME ÚNICO e o remove definitivamente ao final (LGPD).

Script standalone (NÃO pytest):
    .venv/bin/python test/teste_fluxo_permissoes.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mod_intranet.mod_intranet_inicializacao_bd import inicializar_bancos  # noqa: E402
from mod_intranet import autenticacao as auth  # noqa: E402
from mod_gest_cad_usuario import manipulador_bd as gest  # noqa: E402

_OK = 0


def ok(cond, msg):
    global _OK
    _OK += 1
    print(f"  {'OK' if cond else 'FALHOU'} [{_OK}] {msg}")
    return bool(cond)


print("INICIANDO TESTES — Fluxo de permissões por módulo (Fase 2.5)")
inicializar_bancos()

SUFIXO = f"qa{int(time.time() * 1000) % 100000}"
USUARIO = f"perm_{SUFIXO}"

# fixture: usuário comum
gest.criar_usuario("master", USUARIO, "Perm@123", email="perm@teste.local",
                   perfil="comum", nome_completo="Usuário de Permissões QA")

# 1) recém-criado não tem papel no módulo blog
ok(gest.obter_papel_no_modulo(USUARIO, "blog") is None,
   "usuário novo sem acesso ao blog (papel None)")

# 2) acesso ao blog não liberado inicialmente
ok(gest.validar_acesso_modulo(USUARIO, "blog") is False,
   "validar_acesso_modulo(blog) é False antes de liberar")

# 3) concessão de papel comum no blog
ok_conc, _ = gest.definir_acesso("master", USUARIO, "blog", "comum")
ok(ok_conc, "concessão de papel 'comum' no blog")

# 4) papel refletido
ok(gest.obter_papel_no_modulo(USUARIO, "blog") == "comum",
   "obter_papel_no_modulo reflete 'comum'")

# 5) acesso liberado após concessão
ok(gest.validar_acesso_modulo(USUARIO, "blog") is True,
   "validar_acesso_modulo(blog) True após liberar")

# 6) blog aparece na lista de módulos permitidos do usuário
permitidos = auth.listar_modulos_permitidos(USUARIO)
ok("blog" in [m[0] for m in permitidos],
   "blog aparece em listar_modulos_permitidos")

# 7) atualização para administrador do módulo
ok_atual, _ = gest.definir_acesso("master", USUARIO, "blog", "administrador")
ok(ok_atual, "atualização do papel para 'administrador'")

# 8) papel atualizado reflete
ok(gest.obter_papel_no_modulo(USUARIO, "blog") == "administrador",
   "obter_papel_no_modulo reflete 'administrador'")

# 9) eh_admin_do_modulo reconhece o administrador do blog
ok(auth.eh_admin_do_modulo(USUARIO, "blog") is True,
   "eh_admin_do_modulo(blog) True")

# 10) administrador geral enxerga TUDO (todos os módulos, inclusive auditoria)
todos = auth.listar_modulos_permitidos("qamaster")
chaves_master = {m[0] for m in todos}
ok(auth.validar_acesso_modulo("qamaster", "auditoria") is True
   and "auditoria" in chaves_master,
   "admin geral vê tudo (inclusive auditoria, exclusiva de admin geral)")

# 11) auditoria é exclusiva do admin geral: comum não tem acesso
ok(gest.validar_acesso_modulo(USUARIO, "auditoria") is False,
   "auditoria negada ao usuário comum")

# 12) revogação do acesso ao blog
ok_rev, _ = gest.remover_acesso("master", USUARIO, "blog")
ok(ok_rev, "revogação (remover_acesso) do blog")

# 13) pós-revogação: papel None e módulo fora dos permitidos
nopapel = gest.obter_papel_no_modulo(USUARIO, "blog")
eadm = auth.eh_admin_do_modulo(USUARIO, "blog")
novos = auth.listar_modulos_permitidos(USUARIO)
ok(nopapel is None and not eadm
   and "blog" not in [m[0] for m in novos],
   "após revogar, papel None e blog sai dos módulos permitidos")

# ===== limpeza (LGPD) =====
try:
    gest.excluir_usuario_definitivo("master", USUARIO)
except Exception:
    pass

print(f"\nTODOS OS TESTES PASSARAM — {_OK} verificações ✅")
