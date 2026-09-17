"""Shutdown gracioso — agendador e servidor de documentação.

EN: Graceful shutdown — idempotent start/stop of the APScheduler and the
    MkDocs docs server; double-stop never raises; restart works after stop.
PT: Desligamento ordenado — iniciar/parar idempotentes do agendador
    (`rotinas.iniciar_agendador`/`encerrar_agendador`) e do servidor de
    docs (`documentacao.parar_servidor`); parar duas vezes nunca levanta e
    dá para recriar após parar. Sem servidor NiceGUI, sem escrita em banco
    (só leitura de config para os intervalos).

Execute: .venv/bin/python assets/test/teste_shutdown_gracioso.py
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


print("INICIANDO TESTES — shutdown gracioso")

from mod_intranet import rotinas  # noqa: E402
from mod_intranet import documentacao  # noqa: E402

# ---------- agendador: início idempotente ----------
s1 = rotinas.iniciar_agendador()
check(s1 is not None, "iniciar_agendador devolve o scheduler")
s2 = rotinas.iniciar_agendador()
check(s2 is s1, "segundo iniciar devolve a MESMA instância (sem duplicar)")
try:
    n_jobs = len(s1.get_jobs())
except Exception:
    n_jobs = 0
check(n_jobs > 0, f"scheduler com jobs registrados ({n_jobs})")
try:
    estado = s1.state
except Exception:
    estado = None
check(estado == 1, "scheduler em execução (state==RUNNING)")

# ---------- agendador: parada idempotente ----------
check(rotinas.encerrar_agendador() is True, "encerrar devolve True")
check(rotinas._agendador is None, "referência global limpa")
try:
    estado_apos = s1.state
except Exception:
    estado_apos = 1
check(estado_apos != 1, "scheduler fora de execução após encerrar")
check(rotinas.encerrar_agendador() is False, "encerrar de novo devolve False")

# ---------- agendador: recria após parar ----------
s3 = rotinas.iniciar_agendador()
check(s3 is not None and s3 is not s1, "recria nova instância após parar")
try:
    n_jobs3 = len(s3.get_jobs())
except Exception:
    n_jobs3 = 0
check(n_jobs3 > 0, f"nova instância com jobs ({n_jobs3})")
rotinas.encerrar_agendador()
check(rotinas._agendador is None, "limpeza final do agendador")

# ---------- docs: parar sem servidor ----------
check(documentacao.parar_servidor() is False,
      "parar docs sem servidor devolve False")

# ---------- docs: para servidor simulado (sem porta real) ----------


class _SrvFalso:
    def __init__(self):
        self.chamadas = []

    def shutdown(self):
        self.chamadas.append("shutdown")

    def server_close(self):
        self.chamadas.append("server_close")


_falso = _SrvFalso()
documentacao._servidor = _falso
documentacao._porta_atual = 19999
check(documentacao.parar_servidor() is True,
      "parar docs com servidor devolve True")
check(_falso.chamadas == ["shutdown", "server_close"],
      "servidor recebeu shutdown + server_close nesta ordem")
check(documentacao._servidor is None
      and documentacao._porta_atual is None,
      "referências de docs limpas")
check(documentacao.parar_servidor() is False,
      "parar docs de novo devolve False")

print(f"RESULTADO: {_OK} OK, {_TOTAL - _OK} falha(s) de {_TOTAL} verificações")
sys.exit(0 if _OK == _TOTAL else 1)
