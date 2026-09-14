"""Nome do usuário no menu superior — botão único sempre visível.

EN: Header user-name button — single always-visible treatment-name button
    (full name + tooltip), regression guards for the `hidden sm:*` pitfall.
PT: Botão do nome no header — nome de tratamento sempre visível, com
    tooltip completo e ellipsis à direita; guardas contra o padrão quebrado
    `hidden sm:*` (o tailwind embutido resolve `hidden` acima de `sm:flex`).

Cobre as validações de sessão (evidência Playwright 14/09/2026):
- `nome_de_tratamento('qacomum')`/`('qamaster')` devolve o nome completo;
- fonte de `mod_intranet/telas.py`: UM botão `header-nome-usuario`, sem
  `hidden`, sem `header-nome-curto`, CSS escopado com ellipsis;
- badge de perfil e separador sem `hidden` (mesma armadilha).
A renderização real (visível desktop/mobile, clique abre Meu Perfil) é
coberta pelo E2E `assets/test/e2e/04_header_nome.spec.js`.

Somente LEITURA (banco + fonte). Sem servidor.

Execute: .venv/bin/python assets/test/test_header_nome.py
"""
import inspect
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


print("INICIANDO TESTES — nome do usuário no header (botão único)")

from mod_intranet import autenticacao  # noqa: E402
import mod_intranet.telas as telas_mod  # noqa: E402

# ---------- origem do nome (banco real, só leitura) ----------
check(autenticacao.nome_de_tratamento("qacomum") == "Usuário de Teste QA Comum",
      "nome_de_tratamento('qacomum') devolve o nome completo")
check(autenticacao.nome_de_tratamento("qamaster") == "Usuário de Teste QA Master",
      "nome_de_tratamento('qamaster') devolve o nome completo")

# ---------- contrato da fonte (regressão) ----------
fonte = inspect.getsource(telas_mod)
check("data-testid=header-nome-usuario" in fonte,
      "header expõe data-testid=header-nome-usuario")
check("header-nome-curto" not in fonte,
      "botão mobile duplicado header-nome-curto removido (botão único)")
check("hidden sm:flex" not in fonte and "sm:hidden" not in fonte,
      "sem toggles hidden sm:* no header (padrão quebrado neste stack)")
check("hidden md:block" not in fonte,
      "sem hidden md:* no header/badge (mesma armadilha)")
check("header-nome-usuario\"] .q-btn__content" in fonte,
      "CSS escopado ancora o conteúdo do q-btn à esquerda (ellipsis à direita)")
check("max-width: min(28ch, 55vw)" in fonte,
      "largura limitada pela viewport no mobile (sem corte à esquerda)")
check("tooltip=trat" in fonte,
      "tooltip do botão mostra o nome completo")

print(f"RESULTADO: {_OK} OK, {_TOTAL - _OK} falha(s) de {_TOTAL} verificações")
sys.exit(0 if _OK == _TOTAL else 1)
