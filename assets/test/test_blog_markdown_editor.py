"""Markdown dentro do editor WYSIWYG do Blog.

EN: Markdown inside the WYSIWYG editor — `<p>`/`<div>` blocks, bare first
    line, lists, bold, `code`/`pre` intact, `#hashtag` and spaceless `#`
    left literal (CommonMark).
PT: Markdown digitado no editor — o QEditor gera a 1ª linha solta e as
    demais em `<div>` (o nh3 mantém `div`/`br` sem atributos); `#` exige
    espaço (`#texto` fica literal, como no GitHub).

Cobre as validações de sessão (backend + preview no navegador 14/09/2026):
- saída real do editor rende h1/h2/h3 centralizados;
- 1ª linha solta, listas vizinhas, negrito, `code`/`pre` intactos;
- sem falso positivo (`#hashtag`, `**incompleto`, `#colado`);
- texto puro inalterado.

Somente LEITURA (sem banco, sem servidor).

Execute: .venv/bin/python assets/test/test_blog_markdown_editor.py
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


print("INICIANDO TESTES — Markdown dentro do editor WYSIWYG")

from mod_blog.bd_manipulador import (  # noqa: E402
    formatar_conteudo_para_exibicao as fmt,
)

# div/br estruturais sempre permitidos mesmo se o admin remover do CSV
from mod_blog.bd_manipulador import _sanitizar_texto  # noqa: E402
check("<div>" in _sanitizar_texto("<div>x</div>") and "<br>" in _sanitizar_texto("a<br>b"),
      "div/br preservados pela sanitização (sem atributos)")

# saída real do editor: 1ª linha solta + demais em <div>
e = fmt("#Texto teste 1<div>## Texto teste2</div><div>### Texto teste 3</div>")
check("#Texto teste 1" in e, "sem espaço após # fica literal (padrão Markdown)")
check("Texto teste2</h2>" in e and "Texto teste 3</h3>" in e,
      "linhas ##/### em <div> convertem com estilo")
s = fmt("# Texto teste 1<div>## Texto teste2</div>")
check("Texto teste 1</h1>" in s and "text-align:center" in s,
      "1ª linha solta espaçada converte centralizada")

# blocos <p> (linhas com Enter simples após normalização)
p = fmt("<p># T1</p><p>- um</p><p>- dois</p><p>oi **forte**</p>")
check("<h1" in p and "<ul>" in p and "<li>um</li>" in p and "<b>forte</b>" in p,
      "títulos, listas e negrito dentro de <p>")

# preservação e falsos positivos
c = fmt("<p># T</p><pre># nao **x**</pre>")
check("<h1" in c and "# nao **x**" in c, "code/pre intactos")
m = fmt("<p>uso #hashtag e **incompleto aqui</p>")
check("#hashtag" in m and "**incompleto" in m, "sem falso positivo")
t = fmt("# Oi\n- a\n- b")
check("<h1>Oi</h1>" in t and "<ul>" in t, "texto puro inalterado")

print(f"RESULTADO: {_OK} OK, {_TOTAL - _OK} falha(s) de {_TOTAL} verificações")
sys.exit(0 if _OK == _TOTAL else 1)
