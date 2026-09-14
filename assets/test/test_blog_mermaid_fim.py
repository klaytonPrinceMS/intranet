"""Mermaid sempre ao fim da postagem — padrão do Blog.

EN: Mermaid diagrams always close the post — `mover_mermaid_para_fim`
    moves ```mermaid fences to the end on create/update (order kept);
    render centers them (`_renderizar_conteudo_postagem`).
PT: PADRÃO DO MÓDULO: diagramas sempre encerram a postagem — ao salvar
    (criar/editar), os blocos ```mermaid vão para o fim na ordem original;
    sem fence completo, o conteúdo segue intacto. O render centraliza
    (`max-width:680px` com `justify-center`).

Cobre as validações de sessão (backend 14/09/2026):
- meio → fim com ordem preservada; sem fence/incompleto intacto;
- idempotente; seeds `POSTAGENS_PADRAO` conformes;
- centralização: contrato da fonte de `telas.py`.

Somente LEITURA (sem banco, sem servidor).

Execute: .venv/bin/python assets/test/test_blog_mermaid_fim.py
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


print("INICIANDO TESTES — mermaid ao fim da postagem")

from mod_blog.bd_manipulador import (  # noqa: E402
    mover_mermaid_para_fim as mv,
    POSTAGENS_PADRAO,
)

r = mv("texto\n```mermaid\ngraph A```\nmeio\n```mermaid\ngraph B```\nfim")
check(r.index("graph A") < r.index("graph B"), "ordem dos diagramas preservada")
check(r.rstrip().endswith("```") and r.startswith("texto"),
      "blocos movidos para o fim, texto preservado")
check(mv("sem nada") == "sem nada" and mv("```mermaid\nincompleto") == "```mermaid\nincompleto",
      "sem fence completo segue intacto")
check(mv(None) is None and mv("") == "", "entradas vazias intactas")
todas = True
for p in POSTAGENS_PADRAO:
    r = mv(p["conteudo"])
    ok = r.rstrip().endswith("```") and mv(r) == r
    todas = todas and ok
check(todas, "seeds conformes ao padrão + idempotente")
check(len(POSTAGENS_PADRAO) == 3, "3 postagens padrão (pdf, impressão, empenhos)")

import mod_blog.telas as telas_blog  # noqa: E402
fonte = inspect.getsource(telas_blog._renderizar_conteudo_postagem)
check("justify-center" in fonte and "max-width: 680px" in fonte,
      "render centraliza o diagrama (coluna 680px)")

print(f"RESULTADO: {_OK} OK, {_TOTAL - _OK} falha(s) de {_TOTAL} verificações")
sys.exit(0 if _OK == _TOTAL else 1)
