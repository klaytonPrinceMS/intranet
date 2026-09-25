"""Ordem do menu hambúrguer — padrão + persistência após reorder + restart.

EN: Sidebar order — desired default seed and user order surviving reorder
    and reboot (regression: 0-based write wiped customization on boot).
PT: Ordem dos módulos — padrão (Editor PDF, Empenhos, Solicitação,
    Blog, Usuários, Auditoria) e personalização do usuário preservada após
    reordenar (↑/↓ + Aplicar) e reiniciar. Regressão corrigida: o
    `reordenar` 0-based gravava `ordem=0` e o boot reescrevia tudo para
    `MODULOS_SISTEMA`; `_garantir_tb_modulos` agora só numera linhas zeradas.
    Migração 260918 renumera para o novo padrão SOMENTE se a ordem vigente
    for exatamente a antiga (sem personalização).

Cobre as validações de sessão (backend + 2 restarts 14/09/2026):
- `reordenar` grava 1-based (nenhum `ordem=0`);
- simulação de boot (`_modulos_ok=False` + `_garantir_tb_modulos()`)
  preserva a ordem personalizada;
- ordem padrão vigente é a desejada.

Faz snapshot de `tb_modulos` e RESTAURA no `finally` (não altera a ordem
do usuário). Sem servidor (o restart real foi validado manualmente).

Execute: .venv/bin/python assets/test/test_ordem_modulos.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))))

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


print("INICIANDO TESTES — ordem do menu (padrão + persistência)")

from mod_intranet import autenticacao  # noqa: E402
from mod_intranet.repositorio import Repositorio  # noqa: E402

DESEJADA = ["editar_pdf", "empenhos", "solicita_impressao", "blog", "usuarios",
            "auditoria", "tecnico", "filas", "lista_telefonica",
            "agregador_noticias"]

conn = autenticacao.get_connection()
try:
    snap = conn.execute(
        "SELECT chave, nome, icone, rota, ativo, nativo, ordem FROM tb_modulos").fetchall()
finally:
    conn.close()

try:
    # ---------- padrão desejado ----------
    atual = [c for c, _n, _i, _r, _a in autenticacao.modulos_registrados()]
    check(atual == DESEJADA, f"ordem padrão vigente é a desejada (obteve {atual})")

    # ---------- reorder é 1-based (sem ordem=0) ----------
    # cobre TODOS os módulos: `reordenar_modulos` só numera as chaves enviadas,
    # então uma lista parcial deixaria os demais com a ordem anterior e a
    # comparação com `ordens` (10 linhas) nunca casaria.
    prova = ["blog", "usuarios", "auditoria", "editar_pdf", "empenhos",
             "solicita_impressao", "tecnico", "filas", "lista_telefonica",
             "agregador_noticias"]
    with Repositorio() as repo:
        check(repo.reordenar_modulos(prova), "reordenar persiste a ordem de prova")
    conn = autenticacao.get_connection()
    try:
        ordens = conn.execute("SELECT chave, ordem FROM tb_modulos ORDER BY ordem").fetchall()
    finally:
        conn.close()
    check([c for c, _o in ordens] == prova, "ordem de prova gravada")
    check(all(o > 0 for _c, o in ordens), "nenhuma linha com ordem=0 (causa da regressão)")

    # ---------- boot simulado preserva ----------
    autenticacao._modulos_ok = False
    autenticacao._garantir_tb_modulos()
    depois = [c for c, _n, _i, _r, _a in autenticacao.modulos_registrados()]
    check(depois == prova, "boot simulado preserva a personalização (não reseta)")
finally:
    conn = autenticacao.get_connection()
    try:
        for chave, nome, icone, rota, ativo, nativo, ordem in snap:
            conn.execute("UPDATE tb_modulos SET nome=?, icone=?, rota=?, ativo=?,"
                         " nativo=?, ordem=? WHERE chave=?",
                         (nome, icone, rota, ativo, nativo, ordem, chave))
        conn.commit()
    finally:
        conn.close()

conn = autenticacao.get_connection()
try:
    restaurada = [c for c, _o in conn.execute(
        "SELECT chave, ordem FROM tb_modulos ORDER BY ordem").fetchall()]
finally:
    conn.close()
check(restaurada == [c for c, _n, _i, _r, _a, _na, _o in
                     sorted(snap, key=lambda r: r[6])],
      "limpeza: ordem anterior restaurada")

print(f"RESULTADO: {_OK} OK, {_TOTAL - _OK} falha(s) de {_TOTAL} verificações")
sys.exit(0 if _OK == _TOTAL else 1)
