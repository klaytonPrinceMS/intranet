import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
# Garante a ordem correta de bootstrap (central antes do módulo de usuários)
from mod_intranet.mod_intranet_inicializacao_bd import inicializar_bancos
inicializar_bancos()
from mod_intranet import autenticacao as auth
from mod_intranet.conexao_bd import get_connection

print("== Validacao Fase 1: Login + Sessao em Banco ==")

# 1) Autenticacao master/master
ok, perfil = auth.autenticar("master", "master")
assert ok, "autenticar master/master deveria passar"
assert perfil == "administrador_geral", f"perfil esperado admin_geral, veio {perfil}"
print("[OK] autenticar('master','master') -> perfil", perfil)

# 2) Senha errada deve falhar
ok2, _ = auth.autenticar("master", "senha_errada")
assert not ok2, "senha errada nao deveria autenticar"
print("[OK] autenticar com senha errada e bloqueado")

# 3) Registro de sessao em tb_sessoes
h = auth.registrar_login("master", "sistema")
assert h, "registrar_login deveria retornar cookie_hash"
conn = get_connection(); cur = conn.cursor()
row = cur.execute(
    "SELECT usuario, modulo, cookie_hash, logout_timestamp FROM tb_sessoes WHERE cookie_hash=?",
    (h,)).fetchone()
conn.close()
assert row, "sessao nao foi gravada em tb_sessoes"
assert row[0] == "master" and row[2] == h and row[3] is None, f"sessao incompleta: {row}"
print("[OK] sessao gravada em tb_sessoes (usuario, cookie_hash, aberta)")

# 4) sessao_ativa reconhece a sessao aberta
assert auth.sessao_ativa("master", h) is True, "sessao_ativa deveria ser True"
print("[OK] sessao_ativa() confirma a sessao aberta")

# 5) Troca obrigatoria no 1o logon (flag default do seed)
assert auth.precisa_trocar_senha("master") is True, "master deveria exigir troca no 1o logon"
print("[OK] precisa_trocar_senha('master') == True (troca obrigatoria no 1o logon)")

# Limpeza da sessao de teste (mantem o BD limpo)
conn = get_connection(); cur = conn.cursor()
cur.execute("UPDATE tb_sessoes SET logout_timestamp=datetime('now','localtime') WHERE cookie_hash=?", (h,))
conn.commit(); conn.close()
print("[OK] sessao de teste encerrada (limpeza)")

print("\nRESULTADO: item Fase 1 (Login + sessao em banco) VALIDADO com sucesso.")
