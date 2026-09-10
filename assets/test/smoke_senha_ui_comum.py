"""Real-NiceGUI smoke test for password fields via `ui_comum.campo_texto`.

Smoke com NiceGUI REAL (sem servidor) dos campos de senha: prova que
`campo_texto(senha=True)` produz o mesmo elemento `ui.input` da construção
crua (`password=True, password_toggle_button=True`) — props/classes/style/
filhos idênticos (exceto o id instância-específico `for`), botão de
exibir/ocultar presente, default sem senha intocado e `placeholder`
repassado byte-idêntico.

Execute: .venv/bin/python test/smoke_senha_ui_comum.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))))

from nicegui import ui

from mod_intranet import ui_comum

_OK = 0
_TOTAL = 0


def check(cond, msg):
    global _OK, _TOTAL
    _TOTAL += 1
    print(f"  {'OK ' if cond else 'FALHOU'} {msg}")
    if cond:
        _OK += 1


def estado(el):
    """Visual state of a real NiceGUI element (props/classes/style/children).

    Estado visual de um elemento NiceGUI real: props (sem o id instância-
    específico `for`), classes, style e tipos dos filhos (o slot append
    carrega o Icon do toggle de senha)."""
    props = {k: v for k, v in dict(el._props).items() if k != "for"}
    return (type(el).__name__, props, list(el._classes), dict(el._style),
            [type(c).__name__ for c in el])


print("== smoke NiceGUI real: campo_texto(senha=True) ==")
raw = ui.input("Senha atual", password=True, password_toggle_button=True) \
    .props("outlined dense").classes("w-full")
c1 = ui_comum.campo_texto("Senha atual", senha=True)
check(estado(raw) == estado(c1),
      "campo_texto(senha=True) == ui.input cru (props/classes/style/filhos)")
check(c1._props.get("type") == "password", "type=password (campo oculto)")
check(any(type(c).__name__ == "Icon" for c in c1),
      "botão exibir/ocultar presente (slot append com Icon)")
check(c1.value == "" and raw.value == "",
      "value inicial vazio ('' e não None, igual à construção crua)")

raw2 = ui.input("Senha atual", password=True,
                password_toggle_button=True).classes("w-full")
c2 = ui_comum.campo_texto("Senha atual", senha=True, props="")
check(estado(raw2) == estado(c2),
      "campo_texto(senha=True, props='') == troca de senha obrigatória crua")
check("outlined" not in c2._props and "dense" not in c2._props,
      "props='' não aplica outlined/dense (byte-idêntico ao original)")

c3 = ui_comum.campo_texto("Rótulo")
check(c3._props.get("type") == "text" and
      not any(type(c).__name__ == "Icon" for c in c3),
      "default sem senha: type=text, sem toggle de visibilidade")

raw4 = ui.input("Chave única *", placeholder="ex.: folha_ponto") \
    .props("outlined dense")
c4 = ui_comum.campo_texto("Chave única *", placeholder="ex.: folha_ponto",
                          props="outlined dense", largura="")
check(estado(raw4) == estado(c4),
      "campo_texto(placeholder=, largura='') == ui.input cru do novo módulo")

print(f"RESULTADO: {_OK} OK, {_TOTAL - _OK} falha(s) de {_TOTAL}")
sys.exit(0 if _OK == _TOTAL else 1)
