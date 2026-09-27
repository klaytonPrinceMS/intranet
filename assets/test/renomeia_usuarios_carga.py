"""EN: Renames the load-test users (perfNNN -> userNNN).

PT-BR: Renomeia os usuários de carga (perfNNN -> userNNN).

Por que pela API e não por SQL: `renomear_usuario` mantém o `id`, propaga
para `tb_acesso_usuario`, encerra as sessões do login antigo e atualiza as
colunas de autoria nos demais módulos — cada um pelo seu PRÓPRIO `bd_manipulador`
e pela sua API pública, sem cross-query entre bancos (AGENTS.md §4).

Um `UPDATE` direto deixaria para trás: linhas de acesso com o login velho,
sessões apontando para um usuário inexistente e autorias de Blog/Empenhos/Editor
órfãs. Idempotente: pula quem já está no nome novo.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

DE = "perf"
PARA = "user"


def _existe(login: str) -> bool:
    """Diz se o login existe na lista de usuários (leitura, sem escrita)."""
    try:
        from mod_gest_cad_usuario import bd_manipulador as bd
        for linha in bd.listar_usuarios(ativo=None) or []:
            if linha[1] == login:
                return True
        return False
    except Exception:
        return False


def renomear(qtd: int = 120) -> dict:
    """Renomeia perf001..perfNNN para user001..userNNN. Idempotente."""
    from mod_gest_cad_usuario import bd_manipulador as bd

    renomeados, ja_ok, falhas = 0, 0, []
    for i in range(1, qtd + 1):
        antigo = f"{DE}{i:03d}"
        novo = f"{PARA}{i:03d}"
        try:
            ok, msg = bd.renomear_usuario("sistema", antigo, novo)
        except Exception as exc:
            falhas.append((antigo, str(exc)))
            continue
        if ok:
            renomeados += 1
        elif "já existe" in (msg or "").lower() or "ja existe" in (msg or "").lower():
            # o login novo já está ocupado: num re-run é porque JÁ foi
            # renomeado antes (o `perfNNN` não existe mais). Só conta como
            # "já pronto" se o nome antigo realmente não existir mais.
            if not _existe(antigo):
                ja_ok += 1
            else:
                falhas.append((antigo, f"{msg} — e o nome antigo ainda existe"))
        else:
            falhas.append((antigo, msg))

    print(f"  renomeados agora : {renomeados}")
    print(f"  ja no nome novo  : {ja_ok}")
    if falhas:
        print(f"  FALHAS ({len(falhas)}):")
        for login, msg in falhas[:10]:
            print(f"    {login}: {msg}")
    return {"renomeados": renomeados, "ja_ok": ja_ok, "falhas": len(falhas)}


def _migrar_flags_de_troca(qtd: int = 120) -> int:
    """Move a flag `forcar_troca:perfNNN` para `forcar_troca:userNNN`.

    A flag mora no banco do NÚCLEO (outro módulo), então vai pela API do
    núcleo — `autenticacao.marcar_trocar_senha` — e não por SQL.

    `renomear_usuario` não conhece essa flag: ela fica órfã com o login
    antigo. Não existe API pública para APAGAR uma chave de configuração, e o
    código do projeto nunca apaga — zera (`marcar_trocar_senha(..., forcar=False)`
    grava "0"). Então o órfão é neutralizado do mesmo jeito, ficando inerte
    (nenhum login `perfNNN` existe mais para consultá-lo).
    """
    from mod_intranet import autenticacao
    movidas = 0
    for i in range(1, qtd + 1):
        try:
            # forcar=False: o usuário de carga entra direto, sem diálogo
            autenticacao.marcar_trocar_senha(f"{PARA}{i:03d}", forcar=False)
            autenticacao.marcar_trocar_senha(f"{DE}{i:03d}", forcar=False)
            movidas += 1
        except Exception:
            continue
    return movidas


def main() -> int:
    qtd = int(sys.argv[1]) if len(sys.argv) > 1 else 120
    print(f"  renomeando {DE}NNN -> {PARA}NNN ({qtd} usuarios)")
    resultado = renomear(qtd)
    movidas = _migrar_flags_de_troca(qtd)
    print(f"  flags de troca migradas: {movidas}")
    return 1 if resultado["falhas"] else 0


if __name__ == "__main__":
    sys.exit(main())
