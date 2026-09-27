"""Libera (ou restringe) os módulos de leitura dos usuários de carga.

EN: Grants the read-only modules to the load-test users (user001..user120) so
    the usage test covers news, blog, queues and the phone list; reversible
    with --restaurar.

PT-BR: Libera (ou restringe) os módulos de leitura dos usuários de carga
(user001…user120) para que o teste de uso cubra notícias, blog, filas e lista
telefônica; reversível com `--restaurar`.

POR QUE ESTE SCRIPT EXISTE (achado de medição, não de suposição)
---------------------------------------------------------------
`criar_usuario` libera por padrão apenas três vínculos: `editar_pdf`,
`empenhos` e `solicita_impressao`. O gate de `pagina_restrita` exige vínculo
para TODO módulo, então `userNNN`:

    /edit-pdf             -> abre
    /renomear-empenho     -> abre
    /solicita-impressao   -> abre
    /tv                   -> abre (pública por projeto, sem login)
    /configuracoes        -> abre (não tem chave_modulo, só exige sessão)
    /blog                 -> REDIRECIONA para /
    /agregador-noticias  -> REDIRECIONA para /
    tela pura /agregador-noticias-puro -> REMOVIDA em 26/09/2026 (404)
    /filas                -> REDIRECIONA para /
    /lista-telefonica     -> REDIRECIONA para /
    /auditoria            -> REDIRECIONA para /
    /tecnico              -> REDIRECIONA para /
    /users                -> REDIRECIONA para /

Medido com navegador real (Playwright), porque o redirecionamento é
CLIENT-SIDE: o HTTP responde 200 e o `ui.navigate.to('/')` acontece no
navegador. Um `curl` não veria nada disso — o k6 também não.

Sem este script, metade do roteiro de uso (`carga_uso.js`) e a maior parte do
roteiro de navegador (`carga_uso_navegador.py`) mediriam a tela inicial em vez
de notícias e blog. O acesso é `comum` (leitura), nunca `administrador`: a
exigência é medir uso, não administração.

Todos entram pelo módulo (`definir_acesso`), nunca por `sqlite3` direto: é a
única porta de entrada, propaga para `tb_acesso_usuario` e audita. E o mesmo
vale para Postgres (AGENTS.md §4.1).

Uso:
    INTRANET_FORCE_SQLITE=1 .venv/bin/python assets/test/libera_modulos_carga.py
    INTRANET_FORCE_SQLITE=1 .venv/bin/python assets/test/libera_modulos_carga.py --listar
    INTRANET_FORCE_SQLITE=1 .venv/bin/python assets/test/libera_modulos_carga.py --restaurar
"""
from __future__ import annotations

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

PREFIXO = "user"
# `definir_acesso` revalida o papel no backend; o ator precisa ser
# `administrador_geral` (o próprio `master` do seed serve).
ATOR_ADMIN = "master"

# módulos de LEITURA que o roteiro de uso percorre. `comum` em todos.
MODULOS_LEITURA = ("blog", "agregador_noticias", "filas", "lista_telefonica")
# o que `criar_usuario` libera por padrão — é o estado ao qual `--restaurar`
# volta, e o que o teste finds sem este script.
MODULOS_PADRAO = ("editar_pdf", "empenhos", "solicita_impressao")


def _log(msg: str) -> None:
    """Imprime progresso, tolerando stdout fechado (pipe fechado no `head`)."""
    try:
        print(msg, flush=True)
    except Exception:
        pass


def _bd():
    """Importa o bd_manipulador do módulo de usuários (falha explícita)."""
    try:
        from mod_gest_cad_usuario import bd_manipulador
        return bd_manipulador
    except Exception as exc:
        _log(f"  [erro] módulo de usuários indisponível: {exc}")
        return None


def listar_carga() -> list:
    """Logins `userNNN` já cadastrados, ordenados."""
    bd = _bd()
    if bd is None:
        return []
    try:
        linhas = bd.listar_usuarios() or []
        return sorted({str(linha[1]) for linha in linhas
                       if len(linha) > 1 and str(linha[1]).startswith(PREFIXO)})
    except Exception as exc:
        _log(f"  [aviso] não foi possível listar: {exc}")
        return []


def mostrar_situacao() -> None:
    """Imprime a matriz de acesso atual (diagnóstico, não altera nada)."""
    bd = _bd()
    if bd is None:
        return
    logins = listar_carga()
    if not logins:
        _log("  nenhum usuário de carga encontrado (rode popula_usuarios_carga.py)")
        return
    _log(f"  {len(logins)} usuário(s) de carga; módulos de {logins[0]}:")
    from mod_intranet import autenticacao
    chaves = list(MODULOS_PADRAO) + [m for m in MODULOS_LEITURA if m not in MODULOS_PADRAO]
    for chave in chaves:
        papel = None
        try:
            papel = autenticacao.papel_no_modulo(logins[0], chave)
        except Exception as exc:
            _log(f"  [aviso] papel_no_modulo({chave}) falhou: {exc}")
        marca = "acessa" if papel else "BLOQUEADO"
        _log(f"    {chave:24s} {marca:10s} papel={papel or '-'}")


def aplicar(qtd: int = 120, restaurar: bool = False) -> int:
    """Aplica (ou remove) os vínculos de leitura. Devolve quantos usuários mudaram.

    `restaurar=True` remove os vínculos de leitura, devolvendo os usuários ao
    estado de `criar_usuario`. Idempotente nos dois sentidos.
    """
    bd = _bd()
    if bd is None:
        return 0
    logins = [l for l in listar_carga()][:qtd] if qtd else listar_carga()
    if not logins:
        _log("  nenhum usuário de carga encontrado — nada a fazer")
        return 0

    inicio = time.perf_counter()
    alterados, falhas = 0, 0
    verbos = "restaurar" if restaurar else "liberar"
    _log(f"  {verbos} módulos de leitura para {len(logins)} usuário(s): "
         f"{', '.join(MODULOS_LEITURA)}")

    for login in logins:
        mudou = False
        for chave in MODULOS_LEITURA:
            try:
                if restaurar:
                    ok, _msg = bd.remover_acesso(ATOR_ADMIN, login, chave)
                else:
                    ok, _msg = bd.definir_acesso(ATOR_ADMIN, login, chave, "comum")
                if ok:
                    mudou = True
                else:
                    falhas += 1
            except Exception:
                falhas += 1
        if mudou:
            alterados += 1
        if alterados and alterados % 25 == 0 and login != logins[-1]:
            _log(f"    ... {alterados}/{len(logins)}")

    decorrido = time.perf_counter() - inicio
    _log(f"  usuários alterados : {alterados}/{len(logins)}")
    _log(f"  falhas (vínculo)    : {falhas}")
    _log(f"  tempo              : {decorrido:.1f}s")
    return alterados


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Libera módulos de leitura dos usuários de carga")
    ap.add_argument("--qtd", type=int, default=120,
                    help="quantos usuários de carga (padrão 120)")
    ap.add_argument("--restaurar", action="store_true",
                    help="remove os vínculos de leitura (volta ao padrão)")
    ap.add_argument("--listar", action="store_true",
                    help="só mostra a matriz de acesso atual e sai")
    args = ap.parse_args()

    if args.listar:
        mostrar_situacao()
        return 0
    n = aplicar(qtd=args.qtd, restaurar=args.restaurar)
    return 1 if n == 0 else 0


if __name__ == "__main__":
    sys.exit(main())
