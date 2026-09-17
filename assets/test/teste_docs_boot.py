"""Documentação sob demanda — trava de boot e subida manual.

EN: Docs on demand — boot gate flag and manual server start/stop.
PT: `documentacao.habilitada_no_boot()` lê `docs_ativo` (padrão ligada);
    `iniciar_servidor()` sobe numa porta de teste e `parar_servidor()`
    desliga. Restaura `docs_ativo` original no `finally`. Sem NiceGUI.

Execute: .venv/bin/python assets/test/teste_docs_boot.py
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


print("INICIANDO TESTES — documentação sob demanda")

from mod_intranet import documentacao  # noqa: E402
from mod_intranet.bd_conexao import get_config, set_config  # noqa: E402

# ---------- trava de boot (restaura original) ----------
original = get_config("docs_ativo", "1")
try:
    check(documentacao.habilitada_no_boot() in (True, False),
          "habilitada_no_boot devolve bool")
    set_config("docs_ativo", "0")
    check(documentacao.habilitada_no_boot() is False,
          "docs_ativo=0 desliga no boot")
    set_config("docs_ativo", "1")
    check(documentacao.habilitada_no_boot() is True,
          "docs_ativo=1 liga no boot")
finally:
    set_config("docs_ativo", original)
check(get_config("docs_ativo", "1") == original, "docs_ativo restaurado")

# ---------- subida/parada manual em porta de teste ----------
_PORTA_TESTE = 18231
try:
    check(documentacao.iniciar_servidor(_PORTA_TESTE) is True,
          "iniciar_servidor sobe na porta de teste")
    check(documentacao.porta_documentacao() == _PORTA_TESTE,
          "porta_documentacao reflete a porta de teste")
finally:
    parado = documentacao.parar_servidor()
check(parado is True, "parar_servidor desliga após subida")

print(f"RESULTADO: {_OK} OK, {_TOTAL - _OK} falha(s) de {_TOTAL} verificações")
sys.exit(0 if _OK == _TOTAL else 1)
