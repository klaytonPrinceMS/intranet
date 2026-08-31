"""Teste funcional do módulo Auditoria (rastreabilidade LGPD).

Roda manualmente:
    .venv/bin/python test/test_auditoria.py

Cobre: índices da tb_auditoria, audit_log com rastreabilidade, poda por
retenção configurável, permissão de acesso (exclusivo do admin geral) e a
preferência de campos/ordem persistida por usuário.
"""
import sys
import os
import json
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from mod_intranet.conexao_bd import get_config, set_config, get_connection
from mod_intranet.manipulador_bd import audit_log, garantir_rastreabilidade

PASS = []
FAIL = []


def check(nome, condicao):
    (PASS if condicao else FAIL).append(nome)
    print(f"  [{'OK' if condicao else 'FALHOU'}] {nome}")


def _testar_indices():
    print("\n== indices na tb_auditoria ==")
    garantir_rastreabilidade()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='tb_auditoria'")
        nomes = {r[0] for r in cur.fetchall()}
    finally:
        conn.close()
    for idx in ("idx_auditoria_modulo", "idx_auditoria_usuario", "idx_auditoria_timestamp"):
        check(f"indice {idx}", idx in nomes)


def _testar_audit_log():
    print("\n== audit_log com rastreabilidade ==")
    conn = get_connection()
    try:
        audit_log("zz_aud_teste", "intranet", "teste_neo",
                  "registro de verificacao rastreavel",
                  hash_arquivo=None, ip="127.0.0.1", user_agent="zz-ua")
        cur = conn.cursor()
        row = cur.execute(
            "SELECT acao, ip, user_agent, timestamp FROM tb_auditoria "
            "WHERE usuario='zz_aud_teste' ORDER BY id DESC LIMIT 1").fetchone()
        check("acao gravada", row and row[0] == "teste_neo")
        check("ip gravado", row and row[1] == "127.0.0.1")
        check("user_agent gravado", row and row[2] == "zz-ua")
        check("timestamp em formato local (HH:MM:SS)", row and row[3] and row[3].count(":") == 2)
        cur.execute("DELETE FROM tb_auditoria WHERE usuario='zz_aud_teste'")
        conn.commit()
    except Exception:
        check("audit_log sem excecao", False)
        raise
    finally:
        conn.close()


def _testar_poda():
    print("\n== poda por retencao configurável ==")
    from mod_intranet import rotinas
    retencao_prev = get_config("auditoria_retencao_dias", "")
    conn = get_connection()
    cur = conn.cursor()
    try:
        antigas = cur.execute(
            "SELECT COUNT(*) FROM tb_auditoria "
            "WHERE timestamp < datetime('now','localtime','-90 days')").fetchone()[0]
        set_config("auditoria_retencao_dias", "90")
        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur.execute(
            "INSERT INTO tb_auditoria (usuario, modulo, acao, descricao, timestamp) "
            "VALUES ('zz_poda_teste','intranet','teste_neo','registro novo', ?)", (agora,))
        cur.execute(
            "INSERT INTO tb_auditoria (usuario, modulo, acao, descricao, timestamp) "
            "VALUES ('zz_poda_teste','intranet','teste_neo','registro velho', "
            "'2000-01-01 00:00:00')")
        conn.commit()
        velho_id = cur.execute(
            "SELECT id FROM tb_auditoria WHERE descricao='registro velho' "
            "AND usuario='zz_poda_teste'").fetchone()[0]
        novo_id = cur.execute(
            "SELECT id FROM tb_auditoria WHERE descricao='registro novo' "
            "AND usuario='zz_poda_teste'").fetchone()[0]

        if antigas == 0:
            rotinas._job_poda_auditoria()
            cur.execute("SELECT COUNT(*) FROM tb_auditoria WHERE id=?", (velho_id,))
            check("poda remove registro mais antigo que a retencao", cur.fetchone()[0] == 0)
        else:
            print("  (skip destrutivo: banco ja possui registros antigos reais)")

        cur.execute("SELECT COUNT(*) FROM tb_auditoria WHERE id=?", (novo_id,))
        check("poda preserva registro dentro da retencao", cur.fetchone()[0] == 1)

        cur.execute("DELETE FROM tb_auditoria WHERE usuario='zz_poda_teste'")
        conn.commit()
    except Exception:
        check("poda sem excecao", False)
        raise
    finally:
        if retencao_prev != "":
            set_config("auditoria_retencao_dias", retencao_prev)
        conn.close()


def _testar_acesso():
    print("\n== acesso ao modulo de auditoria (exclusivo admin geral) ==")
    from mod_intranet import autenticacao
    if not (autenticacao.usuario_existe("qacomum") and autenticacao.usuario_existe("qamaster")):
        print("  (skip: usuarios de QA qacomum/qamaster ausentes)")
        return
    check("qacomum NAO tem acesso",
          autenticacao.validar_acesso_modulo("qacomum", "auditoria") is False)
    check("qamaster TEM acesso",
          autenticacao.validar_acesso_modulo("qamaster", "auditoria") is True)


def _testar_prefs_campos():
    print("\n== preferencia de campos por usuario ==")
    chave = "auditoria_campos:zz_aud_pref"
    conn = get_connection()
    try:
        set_config(chave, json.dumps(["usuario", "acao", "data"]))
        valor = None
        try:
            valor = json.loads(get_config(chave, ""))
        except Exception:
            valor = None
        check("preferencia de campos persiste por usuario",
              valor == ["usuario", "acao", "data"])
        conn.execute("DELETE FROM tb_config WHERE chave=?", (chave,))
        conn.commit()
    finally:
        conn.close()


def main():
    _testar_indices()
    _testar_audit_log()
    _testar_poda()
    _testar_acesso()
    _testar_prefs_campos()

    print(f"\n=== Auditoria: {len(PASS)} OK · {len(FAIL)} falhou ===")
    if FAIL:
        print("FALHARAM:", ", ".join(FAIL))
        sys.exit(1)


if __name__ == "__main__":
    main()