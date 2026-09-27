"""EN: Measures the server-side cost of a login (bcrypt), outside k6's reach.

PT-BR: Mede o custo de login (bcrypt) no servidor, fora do alcance do k6.

Por que este script existe: o teste k6 (`assets/k6/login_carga.js`) mede a
CONCORRÊNCIA de clientes, mas não mede o clique em "Entrar" — esse despacho é
um evento interno do NiceGUI, e acoplar o teste à versão da biblioteca quebraria
a medição em silêncio. O bcrypt, porém, é custo REAL de servidor por login e
precisa de número.

O que mede:
  - `autenticar()` puro: verificação de senha (o bcrypt, de propósito caro por desenho)
  - `registrar_login()`: grava a sessão
  - o ciclo completo `_audit` incluído, que é o que a tela faz de fato

Compara 1 thread (custo real de um login) com N threads simultâneas, porque o
que interessa é o quanto o event-loop para quando vários logins caem juntos —
essa é a causa raiz do "servidor desconectado".

Uso:
    INTRANET_FORCE_SQLITE=1 .venv/bin/python assets/test/mede_custo_login.py
    INTRANET_FORCE_SQLITE=1 .venv/bin/python assets/test/mede_custo_login.py --usuarios 40
"""
from __future__ import annotations

import argparse
import os
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

LOGINS = [f"user{i:03d}" for i in range(1, 121)]
SENHA = "123456"


def _um_login(i: int) -> float:
    """Um login completo: autenticar (bcrypt) + gravar sessão. Devolve ms."""
    from mod_intranet import autenticacao
    usuario = LOGINS[i % len(LOGINS)]
    inicio = time.perf_counter()
    ok, perfil = autenticacao.autenticar(usuario, SENHA)
    if ok:
        autenticacao.registrar_login(usuario, "sistema")
    return (time.perf_counter() - inicio) * 1000


def medir(n: int = 1) -> dict:
    """Executa n logins em paralelo e devolve os percentis de latência."""
    inicio = time.perf_counter()
    with ThreadPoolExecutor(max_workers=n) as pool:
        tempos = list(pool.map(_um_login, range(n)))
    parede = (time.perf_counter() - inicio) * 1000
    tempos_ordenados = sorted(tempos)
    return {
        "n": n,
        "min": min(tempos),
        "mediana": statistics.median(tempos),
        "p95": tempos_ordenados[int(len(tempos) * 0.95) - 1],
        "max": max(tempos),
        "parede_ms": parede,
        "por_segundo": (n / (parede / 1000)) if parede > 0 else 0,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Mede o custo de login (bcrypt)")
    ap.add_argument("--usuarios", type=int, default=0,
                    help="N logins simultâneos (0 = 1,10,20,40,60,80,120)")
    ap.add_argument("--sem-aquecer", action="store_true",
                    help="NÃO aquece a auditoria antes (mostra o custo de 1º acesso)")
    args = ap.parse_args()

    niveis = [args.usuarios] if args.usuarios else [1, 10, 20, 40, 60, 80, 120]

    # AQUECER A AUDITORIA antes de medir. Sem isso, a PRIMEIRA escrita do processo
    # paga o DDL de criação das tabelas — foi medido em 73,9 s. O servidor faz
    # isso no boot (`_passo_auditoria`); qualquer outro processo tem de fazer o
    # mesmo, senão a medição mistura o custo de setup com o custo do login.
    if not args.sem_aquecer:
        try:
            from mod_auditoria.bd_manipulador import aquecer_auditoria
            n = aquecer_auditoria()
            print(f"  Auditoria aquecida: {n} tabela(s) prontas "
                  f"(como o servidor faz no boot).")
        except Exception as exc:
            print(f"  [aviso] aquecimento falhou: {exc}")

    print("  Usando os usuários de carga (user001..user120), senha 123456.")
    print("  Custo por login = bcrypt (autenticar) + gravação da sessão.")
    if not args.sem_aquecer:
        print("  O servidor está no ar? NÃO — com o servidor ativo há contenção")
        print("  de escrita no SQLite entre os dois processos, e o número medido")
        print("  passa a refletir essa disputa, não o custo do login.")
    print()
    print(f"  {'simultâneos':>11} {'min':>9} {'mediana':>9} {'p95':>9} "
          f"{'max':>9} {'parede':>9} {'logins/s':>10}")
    print("  " + "-" * 72)

    falhas = 0
    for n in niveis:
        r = medir(n)
        if r["min"] <= 0:
            falhas += 1
        print(f"  {n:>11} {r['min']:>8.1f}ms {r['mediana']:>8.1f}ms "
              f"{r['p95']:>8.1f}ms {r['max']:>8.1f}ms {r['parede_ms']:>8.1f}ms "
              f"{r['por_segundo']:>10.1f}")

    print()
    print("  Leitura: 'parede' é o tempo total dos N logins juntos. Se ela")
    print("  crescer muito mais que a mediana, os logins estão se serialize")
    print("  (o bcrypt segura o event-loop) — é o risco de 'servidor")
    print("  desconectado' quando muitos usuários entram ao mesmo tempo.")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
