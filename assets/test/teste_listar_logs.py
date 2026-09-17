"""Listagem de logs — arquivos com tamanho e marca de uso.

EN: Log listing — files with size and in-use mark; pure size formatter.
PT: `observabilidade.listar_logs()` devolve (arquivo, tamanho_kb,
    data_hora, em_uso) do mais recente ao mais antigo, incluindo `.zip`;
    `formatar_tamanho()` rende KB/MB. Escreve APENAS arquivos próprios
    `qa_teste_*` em `logs/` (removidos no `finally`). Sem servidor.

Execute: .venv/bin/python assets/test/teste_listar_logs.py
"""
import os
import sys
import time

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


print("INICIANDO TESTES — listagem de logs")

from mod_intranet import observabilidade as obs  # noqa: E402

# ---------- formatador puro ----------
check(obs.formatar_tamanho(0) == "1 KB", "0 KB vira '1 KB'")
check(obs.formatar_tamanho(512) == "512 KB", "512 vira '512 KB'")
check(obs.formatar_tamanho(2048) == "2.0 MB", "2048 vira '2.0 MB'")
check(obs.formatar_tamanho("abc") == "1 KB", "texto inválido vira '1 KB'")

# ---------- listagem com arquivos próprios ----------
criados = []
try:
    os.makedirs(obs.LOG_DIR, exist_ok=True)
    hoje = time.strftime("%Y-%m-%d")
    nomes = [f"qa_teste_{hoje}.log", "qa_teste_antigo.log",
             "qa_teste_compacto.log.zip"]
    for nome in nomes:
        caminho = os.path.join(obs.LOG_DIR, nome)
        with open(caminho, "wb") as fh:
            fh.write(b"x" * 3000)
        criados.append(nome)
    velho = time.time() - 7200
    os.utime(os.path.join(obs.LOG_DIR, nomes[1]), (velho, velho))

    linhas = obs.listar_logs()
    check(isinstance(linhas, list) and linhas, "listagem não vazia")
    por_nome = {r[0]: r for r in linhas}
    check(all(n in por_nome for n in nomes),
          "arquivos qa_teste_* presentes")
    check(all(r[1] >= 1 for r in linhas), "tamanhos >= 1 KB")
    check(por_nome[nomes[0]][3] is True, "log com data de hoje marcado em uso")
    check(por_nome[nomes[1]][3] is False,
          "log antigo sem marca de uso")
    check(por_nome[nomes[2]][3] is False, ".zip sem marca de uso")
    idx = [r[0] for r in linhas]
    check(idx.index(nomes[0]) < idx.index(nomes[1]),
          "ordenação: mais recente primeiro")
finally:
    for nome in criados:
        try:
            os.remove(os.path.join(obs.LOG_DIR, nome))
        except Exception:
            pass
check(not any(os.path.exists(os.path.join(obs.LOG_DIR, n)) for n in criados),
      "limpeza: nenhum arquivo qa_teste_* restante")

print(f"RESULTADO: {_OK} OK, {_TOTAL - _OK} falha(s) de {_TOTAL} verificações")
sys.exit(0 if _OK == _TOTAL else 1)
