import sys
import os

# Garante que o pacote do projeto seja importavel a partir desta pasta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
from mod_intranet.mod_intranet_inicializacao_bd import inicializar_bancos
from mod_intranet import autenticacao as auth
from mod_intranet.conexao_bd import get_connection


def test_login_e_sessao_em_banco():
    """Fase 1: autenticacao master/master, gravacao de sessao em tb_sessoes
    (cookie HTTP-Only amarrado ao hash) e troca obrigatoria no 1o logon."""
    # Ordem correta de bootstrap (central antes do modulo de usuarios)
    inicializar_bancos()

    # 1) Autenticacao master/master
    ok, perfil = auth.autenticar("master", "master")
    assert ok, "autenticar master/master deveria passar"
    assert perfil == "administrador_geral", f"perfil esperado admin_geral, veio {perfil}"

    # 2) Senha errada deve falhar
    ok2, _ = auth.autenticar("master", "senha_errada")
    assert not ok2, "senha errada nao deveria autenticar"

    # 3) Registro de sessao em tb_sessoes
    h = auth.registrar_login("master", "sistema")
    assert h, "registrar_login deveria retornar cookie_hash"
    conn = get_connection()
    cur = conn.cursor()
    row = cur.execute(
        "SELECT usuario, modulo, cookie_hash, logout_timestamp "
        "FROM tb_sessoes WHERE cookie_hash=?",
        (h,),
    ).fetchone()
    conn.close()
    assert row, "sessao nao foi gravada em tb_sessoes"
    assert row[0] == "master" and row[2] == h and row[3] is None, \
        f"sessao incompleta: {row}"

    # 4) sessao_ativa reconhece a sessao aberta
    assert auth.sessao_ativa("master", h) is True, \
        "sessao_ativa deveria ser True"

    # 5) Troca obrigatoria no 1o logon (flag do seed)
    assert auth.precisa_trocar_senha("master") is True, \
        "master deveria exigir troca no 1o logon"

    # Limpeza da sessao de teste
    conn = get_connection()
    conn.execute(
        "UPDATE tb_sessoes SET logout_timestamp=datetime('now','localtime') "
        "WHERE cookie_hash=?",
        (h,),
    )
    conn.commit()
    conn.close()

    print("OK: Fase 1 (Login + sessao em banco) validada com sucesso.")


if __name__ == "__main__":
    test_login_e_sessao_em_banco()
