"""Verificação da fábrica central de UI (`ui_comum` + helpers de tela).

Script standalone (NÃO pytest). Prova byte-a-byte que os componentes
padronizados (`botao`/`botao_icone`/`dialogo_card`/`rodape_dialogo`/
`rodape_salvar_restaurar`, `menu_modulo`/`campo_busca`/`barra_acoes`) e as
delegações (`tema_modulo.botao`, `tela_configuracoes._botao_padrao`) produzem
props/classes/estilo/tooltip IDÊNTICOS às construções cruas de referência
(tema fixado sem tocar no banco, via monkeypatch de `ler_tema`/`estilo_cartao`),
além das equivalências do header branco, dos pilotos (renomear empenho,
gestão de usuários), da migração completa do gest_cad (cor= sem leitura de
tema, `classes_extra` no rodapé, `dialogo_card` por módulo e checagens de
fonte da tela migrada) e do cupê 'Edição do módulo' (`campo_modulo`
restaurado, com campos via `campo_texto`).

Execute: .venv/bin/python test/verifica_ui_comum.py
"""
import hashlib
import os
import re
import sys
import types

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))))

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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


def ler(rel):
    with open(os.path.join(RAIZ, rel), encoding="utf-8") as f:
        return f.read()


# ================== STUB DE NICEGUI (registra saída visual) ==================
REG = []


class _El:
    def __init__(self, tipo, *args, **kwargs):
        self.tipo = tipo
        self.args = args
        self.kwargs = kwargs
        self.props_str = ""
        self.classes_str = ""
        self.style_str = ""
        self.tooltips = []
        self.callbacks = []

    def props(self, s):
        self.props_str = (self.props_str + " " + s).strip()
        return self

    def classes(self, s):
        self.classes_str = (self.classes_str + " " + s).strip()
        return self

    def style(self, s):
        self.style_str = (self.style_str + " " + s).strip()
        return self

    def tooltip(self, t):
        self.tooltips.append(t)
        return self

    def on_value_change(self, cb):
        self.callbacks.append(cb)
        return self

    def open(self):
        return self

    def close(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _fab(tipo):
    def _cria(*args, **kwargs):
        el = _El(tipo, *args, **kwargs)
        REG.append(el)
        return el
    return _cria


_ui_mod = types.ModuleType("nicegui.ui")
for _nome in ("button", "row", "column", "card", "card_section", "tabs",
              "tab", "tab_panels", "tab_panel", "input", "label", "separator",
              "dialog", "icon", "badge", "menu", "grid", "timer", "element",
              "color_input", "select", "textarea", "query", "expansion",
              "switch"):
    setattr(_ui_mod, _nome, _fab(_nome))

_nice = types.ModuleType("nicegui")
_nice.ui = _ui_mod
_nice.app = types.SimpleNamespace(add_static_files=lambda *a, **k: None)
sys.modules["nicegui"] = _nice
sys.modules["nicegui.ui"] = _ui_mod

# ============ TEMA FIXADO (monkeypatch — não toca no banco) ============
import mod_intranet.tema_modulo as tm

COR = "#0F62FE"
TXT = "#FFF8E1"
TAM = "large"
_LEITURAS = {"n": 0}


def _ler_tema(chave="intranet", *a, **k):
    _LEITURAS["n"] += 1
    return {"cor_botao": COR, "cor_texto_botao": TXT, "btn_tamanho": TAM}


def _estilo_cartao(chave="intranet"):
    return "background-color:#FAFAFA;color:#111111;"


_LER_TEMA_REAL = tm.ler_tema
tm.ler_tema = _ler_tema
tm.estilo_cartao = _estilo_cartao

from mod_intranet import ui_comum
from mod_intranet import aba_modulo
from mod_intranet import tema_modulo
from mod_intranet import tela_configuracoes

_CEI = tema_modulo.btn_cls(TAM)  # "min-w-[220px] text-lg"
_CES = f"background-color:{COR};color:{TXT};"


def ult(n=1):
    return REG[-n] if n == 1 else REG[-n:]


def novo(reg=True):
    REG.clear()
    return reg


# ================== 1. CORES ==================
print("== CORES ==")
novo()
_ESPERADO_CORES = {
    "primaria": "#1565C0", "sucesso": "#2E7D32", "alerta": "#EF6C00",
    "perigo": "#C62828", "info": "#00838F", "neutro": "#455A64",
    "destaque": "#6A1B9A", "cinza_escuro": "#37474F", "titulo": "#212121",
    "branco": "#FFFFFF", "fundo": "#EEEEEE",
}
check(ui_comum.CORES == _ESPERADO_CORES, "CORES com 11 chaves e valores padrão")
check(tela_configuracoes.CORES_PRESET == [
    "#1565C0", "#00838F", "#2E7D32", "#6A1B9A", "#C62828", "#EF6C00",
    "#37474F"], "CORES_PRESET derivada com valores históricos preservados")

# ================== 2. botao() — variantes byte-exatas ==================
print("== botao: variantes ==")
novo(); ui_comum.botao("X", variante="primario")
b = ult()
check(b.props_str == "unelevated no-caps size=md" and
      b.classes_str == f"shadow-sm {_CEI}" and b.style_str == _CES,
      "primario: props+btn_cls+btn_style do tema")
novo(); ui_comum.botao("X", variante="primario", compacto=True)
b = ult()
check(b.props_str == "unelevated no-caps" and b.classes_str == "" and
      b.style_str == _CES, "primario compacto: sem size/btn_cls/sombra")
novo(); ui_comum.botao("X", variante="solido")
b = ult()
check(b.props_str == "unelevated no-caps size=md" and
      b.classes_str == f"shadow-sm {_CEI}", "alias solido == primario")
novo(); ui_comum.botao("X", variante="secundario")
b = ult()
check(b.props_str == "outline no-caps" and b.classes_str == "" and
      b.style_str == f"color:{COR};border-color:{COR};", "secundario outline")
novo(); ui_comum.botao("X", variante="contorno")
check(ult().props_str == "outline no-caps" and
      ult().style_str == f"color:{COR};border-color:{COR};",
      "alias contorno == secundario")
novo(); ui_comum.botao("X", variante="texto")
b = ult()
check(b.props_str == "flat no-caps" and b.classes_str == "" and
      b.style_str == f"color:{COR};", "texto flat na cor do tema")
novo(); ui_comum.botao("X", variante="neutro")
b = ult()
check(b.props_str == "flat no-caps size=md text-color=grey-8" and
      b.style_str == "" and b.classes_str == "", "neutro flat cinza")
novo(); ui_comum.botao("X", variante="restaurar")
check(ult().props_str == "outline no-caps size=md color=warning "
      "text-color=amber-10", "restaurar outline warning")
novo(); ui_comum.botao("X", variante="restaurar_fill")
b = ult()
check(b.props_str == "unelevated no-caps size=md color=warning "
      "text-color=white" and b.classes_str == "shadow-sm",
      "restaurar_fill warning preenchido")
novo(); ui_comum.botao("X", variante="perigo")
check(ult().props_str == "outline no-caps size=md color=negative "
      "text-color=negative", "perigo outline negative")
novo(); ui_comum.botao(None, variante="icone")
b = ult()
check(b.props_str == "flat round dense size=sm" and
      b.style_str == f"color:{COR};", "icone compacto na cor do tema")
novo(); ui_comum.botao(None, variante="icone_branco")
b = ult()
check(b.props_str == "flat round color=white" and b.style_str == "",
      "icone_branco = header cru (flat round color=white)")
novo(); ui_comum.botao("trat", variante="texto_branco")
b = ult()
check(b.props_str == "flat dense color=white no-caps",
      "texto_branco = perfil cru (flat dense color=white no-caps)")

# ================== 2b. botao(no_caps=...) — token no-caps ==================
print("== botao: no_caps ==")
novo(); ui_comum.botao("X", variante="primario", compacto=True, no_caps=False)
check(ult().props_str == "unelevated",
      "no_caps=False primario compacto: props sem no-caps")
novo(); ui_comum.botao("X", variante="primario", no_caps=False)
check(ult().props_str == "unelevated size=md",
      "no_caps=False primario: props sem no-caps")
novo(); ui_comum.botao("X", variante="texto", no_caps=False)
check(ult().props_str == "flat", "no_caps=False texto: props sem no-caps")
novo(); ui_comum.botao("X", variante="primario", compacto=True, no_caps=True)
check(ult().props_str == "unelevated no-caps",
      "no_caps=True explícito == default (compacto)")
novo(); ui_comum.botao("X", variante="primario", no_caps=True)
check(ult().props_str == "unelevated no-caps size=md",
      "no_caps=True explícito == default (não-compacto)")
novo(); ui_comum.botao("X", variante="texto", no_caps=True)
check(ult().props_str == "flat no-caps", "no_caps=True explícito == default (texto)")

# ================== 3. cor / extra_classes / tooltip / falhas ==================
print("== botao: cor, extras, tooltip, falha-soft ==")
novo(); ui_comum.botao("X", variante="primario", cor="red-8")
b = ult()
check(b.props_str == "unelevated no-caps size=md color=red-8" and
      b.classes_str == "shadow-sm" and b.style_str == "",
      "cor sobrescreve primario (sem btn_cls, estilo limpo)")
novo(); ui_comum.botao(None, variante="icone", cor="red-8")
b = ult()
check(b.props_str == "flat round dense size=sm color=red-8" and
      b.style_str == "", "cor sobrescreve icone mantendo formato")
novo(); ui_comum.botao("X", variante="primario", extra_classes="w-full")
check(ult().classes_str == f"shadow-sm {_CEI} w-full",
      "extra_classes somadas")
novo(); ui_comum.botao("X", variante="primario", tooltip="dica")
check(ult().tooltips == ["dica"], "tooltip aplicado quando informado")
novo()
_antigo = _ui_mod.button
_ui_mod.button = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
try:
    check(ui_comum.botao("X") is None, "falha de montagem retorna None")
finally:
    _ui_mod.button = _antigo
try:
    ui_comum.botao("X", variante="inexistente")
    check(False, "variante inválida levanta ValueError")
except ValueError:
    check(True, "variante inválida levanta ValueError")

# ================== 4. leitura de tema (economia de consultas) ==================
print("== botao: leitura de tema ==")
novo(); _LEITURAS["n"] = 0
ui_comum.botao("X", variante="primario")
check(_LEITURAS["n"] == 1, "variante com tema lê o tema 1x")
novo(); _LEITURAS["n"] = 0
for v in ("neutro", "restaurar", "restaurar_fill", "perigo",
          "icone_branco", "texto_branco"):
    ui_comum.botao("X", variante=v)
check(_LEITURAS["n"] == 0, "variantes fixas NÃO leem o tema (0 consultas)")

# ================== 4b. cor= evita leitura de tema (variantes tematizadas) ======
print("== botao: cor evita leitura de tema ==")
novo(); _LEITURAS["n"] = 0
for v in ("primario", "secundario", "texto", "icone"):
    ui_comum.botao(None if v == "icone" else "X", variante=v, cor="teal-8")
check(_LEITURAS["n"] == 0,
      "variantes tematizadas com cor NÃO leem o tema (0 consultas)")
novo(); ui_comum.botao("X", variante="secundario", cor="teal-8")
b = ult()
check(b.props_str == "outline no-caps color=teal-8" and b.classes_str == "" and
      b.style_str == "", "cor em secundario: color= anexado, estilo limpo")
novo(); ui_comum.botao("X", variante="texto", cor="teal-8")
b = ult()
check(b.props_str == "flat no-caps color=teal-8" and b.style_str == "",
      "cor em texto: color= anexado, estilo limpo")

# ================== 5. botao_icone ==================
print("== botao_icone ==")
novo(); ui_comum.botao_icone("delete", on_click=None)
check(ult().props_str == "flat round dense size=sm",
      "default = variante icone (linha de tabela)")
novo(); ui_comum.botao_icone("menu", variante="icone_branco")
check(ult().props_str == "flat round color=white",
      "variante icone_branco (header)")

# ================== 6. delegações ==================
print("== delegações (tema_modulo / _botao_padrao) ==")
novo(); tema_modulo.botao("Salvar", variante="solido")
b = ult()
check(b.props_str == "unelevated no-caps" and b.classes_str == _CEI and
      b.style_str == _CES, "tema_modulo.botao(solido) == tema cru antigo")
novo(); tema_modulo.botao("X", variante="contorno")
b = ult()
check(b.props_str == "outline no-caps" and b.classes_str == _CEI and
      b.style_str == f"color:{COR};border-color:{COR};",
      "tema_modulo.botao(contorno) == tema cru antigo")
novo(); tema_modulo.botao("X", variante="texto")
b = ult()
check(b.props_str == "flat no-caps" and b.classes_str == "" and
      b.style_str == f"color:{COR};", "tema_modulo.botao(texto) == antigo")
for tipo, var in (("primario", "primario"), ("neutro", "neutro"),
                  ("perigo", "perigo"), ("icone", "icone")):
    novo()
    tela_configuracoes._botao_padrao("X", tipo=tipo)
    b1 = ult()
    novo()
    ui_comum.botao("X", variante=var)
    b2 = ult()
    check((b1.props_str, b1.classes_str, b1.style_str) ==
          (b2.props_str, b2.classes_str, b2.style_str),
          f"_botao_padrao(tipo={tipo}) == ui_comum.botao({var})")
novo(); tela_configuracoes._botao_padrao(None, tipo="icone", color="red-8")
b1 = ult()
check(b1.props_str == "flat round dense size=sm color=red-8",
      "_botao_padrao color= sobrescreve como ui_comum.cor=")

# ================== 7. rodape_dialogo ==================
print("== rodape_dialogo ==")
novo()
dlg = _El("dialog")
rodape_dialogo_ok = True
try:
    ui_comum.rodape_dialogo(
        dlg, acoes=[("Salvar", lambda: None),
                    ("Salvar2", lambda: None, {"extra_classes": "w-full"})])
except Exception:
    rodape_dialogo_ok = False
check(rodape_dialogo_ok, "rodapé com ações válidas não levanta exceção")
b = REG[0]
check(b.tipo == "row" and b.classes_str == "w-full justify-end" and
      b.style_str == "gap: 0.5rem", "row do rodapé: justify-end + gap 0.5rem")
btns = [e for e in REG if e.tipo == "button"]
check(len(btns) == 3 and btns[0].args[0] == "Cancelar" and
      btns[0].kwargs.get("on_click") == dlg.close and
      btns[0].props_str == "flat no-caps", "Cancelar fecha o diálogo (flat)")
check(btns[1].props_str == "unelevated no-caps" and
      btns[1].style_str == _CES and btns[1].classes_str == "",
      "ação primária compacta do tema")
check(btns[2].classes_str == "w-full" and btns[2].style_str == _CES,
      "kwargs da ação repassados (extra_classes)")
novo()
try:
    ui_comum.rodape_dialogo(dlg, acoes=[("só-rotulo",)])
    check(True, "item malformado ignorado sem exceção")
except Exception:
    check(False, "item malformado ignorado sem exceção")
novo()
ui_comum.rodape_dialogo(dlg, acoes=[("Criar", lambda: None)], classes_extra="mt-3")
row = REG[0]
btns = [e for e in REG if e.tipo == "button"]
check(row.classes_str == "w-full justify-end mt-3" and
      row.style_str == "gap: 0.5rem" and len(btns) == 2 and
      btns[1].props_str == "unelevated no-caps" and btns[1].style_str == _CES,
      "classes_extra somadas à row do rodapé (ações primárias intactas)")

# ================== 8. rodape_salvar_restaurar ==================
print("== rodape_salvar_restaurar ==")
novo()
ui_comum.rodape_salvar_restaurar(lambda: None, lambda: None)
btns = [e for e in REG if e.tipo == "button"]
check(len(btns) == 2 and btns[0].args[0] == "Restaurar padrão" and
      "color=warning" in btns[0].props_str, "restaurar presente (variante restaurar)")
check(btns[1].args[0] == "Aplicar" and btns[1].kwargs.get("icon") == "save" and
      btns[1].props_str == "unelevated no-caps size=md" and
      btns[1].classes_str == f"shadow-sm {_CEI}" and
      btns[1].style_str == _CES,
      "aplicar = botao(variante solido) com tema (ícone save)")
novo()
ui_comum.rodape_salvar_restaurar(lambda: None)
btns = [e for e in REG if e.tipo == "button"]
check(len(btns) == 1, "restaurar=None omite o botão de restaurar")
novo()
ui_comum.rodape_salvar_restaurar(lambda: None, rotulo_salvar="Salvar módulo")
btns = [e for e in REG if e.tipo == "button"]
check(btns[0].args[0] == "Salvar módulo", "rótulo de salvar customizado")

# ================== 9. dialogo_card ==================
print("== dialogo_card ==")
novo()
with ui_comum.dialogo_card(largura="w-[560px]") as (dlg, card):
    pass
check(card.classes_str == "w-[560px] max-h-[90vh]" and
      card.style_str == "background-color:#FAFAFA;color:#111111;",
      "card padrão: largura + max-h 90vh + estilo do cartão")
novo()
with ui_comum.dialogo_card(largura="w-[420px]", max_altura=False) as (dlg, card):
    pass
check(card.classes_str == "w-[420px]", "max_altura=False omite max-h")
novo()
with ui_comum.dialogo_card(titulo="Título") as (dlg, card):
    pass
labs = [e for e in REG if e.tipo == "label"]
seps = [e for e in REG if e.tipo == "separator"]
check(labs and labs[0].args[0] == "Título" and
      labs[0].classes_str == "text-h6" and seps,
      "titulo cria label text-h6 + separator")
tm_estilo_real = tm.estilo_cartao
tm.estilo_cartao = lambda chave="intranet": (_ for _ in ()).throw(
    RuntimeError("boom"))
novo()
try:
    with ui_comum.dialogo_card() as (dlg, card):
        pass
    ok = card.style_str == ""
except Exception:
    ok = False
tm.estilo_cartao = tm_estilo_real
check(ok, "estilo de cartão indisponível não derruba o diálogo")
novo()
with ui_comum.dialogo_card(largura="w-[440px]", chave_modulo="usuarios",
                           max_altura=False) as (dlg_u, card_u):
    card_u.classes("border-2 border-orange-5")
check(card_u.classes_str == "w-[440px] border-2 border-orange-5" and
      card_u.style_str == "background-color:#FAFAFA;color:#111111;",
      "dialogo_card(chave_modulo='usuarios'): estilo do tema + classes extras")
novo()
with ui_comum.dialogo_card(largura="", max_altura=False) as (dlg_c, card_c):
    pass
check(card_c.classes_str == "" and
      card_c.style_str == "background-color:#FAFAFA;color:#111111;",
      "dialogo_card(largura='', max_altura=False) == shell cru do confirmar")

# ================== 10. menu_modulo ==================
print("== menu_modulo ==")
ITENS = (("navegar", "Navegar", "folder_open"),
         ("fila", "Fila Renomeação", "move_to_inbox"),
         ("pesquisa", "Pesquisar", "search"),
         ("organizador", "Organizador", "inventory_2"),
         ("solicitacao", "Solicitação", "mail"),
         ("config", "Administração", "admin_panel_settings"))
novo()
tabs_el = aba_modulo.menu_modulo(ITENS)
check(tabs_el.classes_str == "w-full" and tabs_el.kwargs.get("value") ==
      "navegar", "tabs w-full com 1º item ativo por padrão")
tabs_criados = [e for e in REG if e.tipo == "tab"]
check(len(tabs_criados) == 6 and
      all(t.args[:2] == (c, r) and t.kwargs.get("icon") == i
          for t, (c, r, i) in zip(tabs_criados, ITENS)),
      "6 ui.tab posicionais com ícone (padrão renomear empenho)")
novo()
aba_modulo.menu_modulo(ITENS, valor="pesquisa")
check(REG[0].kwargs.get("value") == "pesquisa", "valor explícito respeitado")
novo()
try:
    aba_modulo.menu_modulo([])
    check(True, "itens vazio não levanta exceção")
except Exception:
    check(False, "itens vazio não levanta exceção")

# ================== 11. campo_busca ==================
print("== campo_busca ==")
novo()
aba_modulo.campo_busca("🔍  Buscar…", on_change=lambda e: None,
                       tooltip="dica da busca")
c = ult()
check(c.tipo == "input" and c.kwargs.get("placeholder") == "🔍  Buscar…" and
      c.props_str == "outlined dense clearable debounce='150'",
      "props do campo de busca (gest_cad)")
check(c.classes_str == "w-full grow min-w-[220px]",
      "classes do campo de busca")
check(c.tooltips == ["dica da busca"], "tooltip aplicado quando informado")
novo()
aba_modulo.campo_busca("Busca")
check(ult().tooltips == [], "sem tooltip quando não informado")

# ================== 12. barra_acoes ==================
print("== barra_acoes ==")
novo()
barra = aba_modulo.barra_acoes(busca={"placeholder": "🔍  Buscar…"},
                               acoes=[("Novo item", "add", lambda: None,
                                       "tooltip t")])
check(barra.classes_str == "w-full items-center justify-between gap-4 "
      "flex-nowrap bg-white rounded-lg shadow-sm px-3 py-1",
      "classes da barra branca (padrão gest_cad)")
rows = [e for e in REG if e.tipo == "row"]
check(len(rows) == 2 and rows[1].classes_str ==
      "items-center gap-2 flex-nowrap shrink-0" and
      rows[1].style_str == "width:min(46%, 620px)",
      "row interna com busca: largura min(46%, 620px)")
novo()
botao_direto = ui_comum.botao("Novo item", icone="add", on_click=lambda: None,
                              tooltip="tooltip t", extra_classes="shrink-0")
b_direto = (botao_direto.props_str, botao_direto.classes_str,
            botao_direto.style_str, botao_direto.tooltips)
novo()
barra = aba_modulo.barra_acoes(busca={"placeholder": "B"},
                               acoes=[("Novo item", "add", lambda: None,
                                       "tooltip t")])
btns = [e for e in REG if e.tipo == "button"]
b_barra = (btns[0].props_str, btns[0].classes_str, btns[0].style_str,
           btns[0].tooltips)
check(b_barra == b_direto, "botão da barra == ui_comum.botao primario")
novo()
barra = aba_modulo.barra_acoes(acoes=[("Só botões", "save", lambda: None)])
rows = [e for e in REG if e.tipo == "row"]
check(rows[1].classes_str == "w-full items-center justify-end flex-nowrap"
      and rows[1].style_str == "gap: 0.5rem",
      "sem busca: botões alinhados à direita")
novo()
try:
    aba_modulo.barra_acoes(acoes=[("incompleto",)])
    check(True, "ação malformada ignorada sem exceção")
except Exception:
    check(False, "ação malformada ignorada sem exceção")

# ================== 13. pilotos no fonte ==================
print("== pilotos (fonte) ==")
REN = ler("mod_renomear_empenho/telas.py")
check("menu_modulo(" in REN and "ui.tabs()" not in REN and
      "ui.tab(" not in REN and "_icones" not in REN,
      "renomear empenho usa menu_modulo (tabs crus removidos)")
GEST = ler("mod_gest_cad_usuario/telas.py")
check("campo_busca(" in GEST and "debounce='150'" not in GEST and
      "ui.input(placeholder" not in GEST,
      "gest_cad usa campo_busca (input cru removido)")
check('ui.button("Novo usuário"' not in GEST and
      'botao("Novo usuário"' in GEST and 'chave_modulo="usuarios"' in GEST,
      "gest_cad: Novo usuário via ui_comum.botao (tema do módulo)")
check("abas(" in ler("mod_blog/telas.py") and
      "abas(" in ler("mod_auditoria/telas.py"),
      "blog/auditoria preservados usando abas() (compatibilidade)")

# ================== 14. gest_cad migrado (fonte) ==================
print("== gest_cad migrado (fonte) ==")
GEST2 = ler("mod_gest_cad_usuario/telas.py")
check("ui.notify(" not in GEST2 and "notificar(" in GEST2,
      "gest_cad: ui.notify substituído por notificar (timeout configurável)")
check('botao_icone("edit"' in GEST2 and 'chave_modulo="usuarios"' in GEST2,
      "gest_cad: ações de linha via botao_icone(chave_modulo='usuarios')")
check("dialogo_card(" in GEST2 and "max_altura=False" in GEST2,
      "gest_cad: shells de diálogo via dialogo_card (max-h só onde existia)")
check("rodape_dialogo(" in GEST2 and 'classes_extra="mt-3"' in GEST2,
      "gest_cad: rodapés padrão via rodape_dialogo com classes_extra")
check("def _tema(" not in GEST2 and "def _tema_cab(" not in GEST2 and
      "def _btn_style(" not in GEST2,
      "gest_cad: helpers locais de tema removidos (ler_tema central)")
check('ui.colors(primary="#00838F")' not in GEST2 and
      'ui.colors(primary=tema["cor_botao"])' in GEST2,
      "gest_cad: cor primária fixa removida (usuarios_cor_botao configurável)")

# ================== 15. ler_tema real: padrão próprio do módulo ==================
print("== ler_tema: chave vazia usa o padrão do PRÓPRIO módulo (não herda o sistema) ==")
_BD = {}


def _cfg_fake(chave, default=""):
    v = _BD.get(chave, default)
    return (v or "").strip() or default


_CFG_REAL = tm._cfg
tm._cfg = _cfg_fake
_LER_TEMA_REAL.cache_clear()
try:
    _BD.update({
        "usuarios_cor_botao": "#00838F", "usuarios_cor_texto_botao": "#FFFFFF",
        "usuarios_btn_tamanho": "medium", "intranet_cor_botao": "#00FF00",
        "intranet_cor_texto_botao": "#FF0000", "intranet_btn_tamanho": "large"})
    t = _LER_TEMA_REAL("usuarios", cor_botao="#1565C0",
                       cor_texto_botao="#FFFFFF", btn_tamanho="medium")
    check((t["cor_botao"], t["cor_texto_botao"], t["btn_tamanho"]) ==
          ("#00838F", "#FFFFFF", "medium"),
          "(a) valor não vazio do módulo vence o tema do sistema")

    _BD.clear()
    _LER_TEMA_REAL.cache_clear()
    _BD.update({"intranet_cor_botao": "#00FF00",
                "intranet_cor_texto_botao": "#FF0000",
                "intranet_btn_tamanho": "large"})
    t = _LER_TEMA_REAL("usuarios", cor_botao="#1565C0",
                       cor_texto_botao="#FFFFFF", btn_tamanho="medium")
    check((t["cor_botao"], t["cor_texto_botao"], t["btn_tamanho"]) ==
          ("#1565C0", "#FFFFFF", "medium"),
          "(b) módulo vazio NÃO herda do sistema — usa o default do parâmetro")

    _BD.clear()
    _LER_TEMA_REAL.cache_clear()
    t = _LER_TEMA_REAL("usuarios")
    check((t["cor_botao"], t["cor_texto_botao"], t["btn_tamanho"]) ==
          ("#000000", "#FFFFFF", "medium"),
          "(b2) módulo vazio sem default: usa o padrão do PRÓPRIO módulo (PADROES_TEMA)")

    _BD.clear()
    _LER_TEMA_REAL.cache_clear()
    t = _LER_TEMA_REAL("usuarios", cor_botao="#1565C0",
                       cor_texto_botao="#FFFFFF", btn_tamanho="medium")
    check((t["cor_botao"], t["cor_texto_botao"], t["btn_tamanho"]) ==
          ("#1565C0", "#FFFFFF", "medium"),
          "(c) ambos vazios: default do parâmetro")

    _BD.update({"intranet_cor_fundo": "#123456", "intranet_cor_titulo": "#654321",
                "intranet_texto_header": "cab do sistema"})
    t = _LER_TEMA_REAL("usuarios", cor_fundo="", cor_titulo="#212121",
                       texto_header="cab do módulo")
    check((t["cor_fundo"], t["cor_titulo"], t["texto_header"]) ==
          ("", "#212121", "cab do módulo"),
          "(d) cor_fundo/cor_titulo/texto_header NÃO herdam do sistema")

    _BD.clear()
    _LER_TEMA_REAL.cache_clear()
    _BD.update({"intranet_cor_botao": ""})
    t = _LER_TEMA_REAL("intranet", cor_botao="#1565C0")
    check(t["cor_botao"] == "#1565C0",
          "(e) ler_tema('intranet') vazio usa o default (não auto-herda)")
    _BD.update({"intranet_cor_botao": "#00FF00"})
    _LER_TEMA_REAL.cache_clear()
    t = _LER_TEMA_REAL("intranet", cor_botao="#1565C0")
    check(t["cor_botao"] == "#00FF00",
          "(e) ler_tema('intranet') lê as próprias chaves intranet_*")
finally:
    tm._cfg = _CFG_REAL
    _LER_TEMA_REAL.cache_clear()
    _BD.clear()

# ================== 16. edit_pdf migrado (fonte) ==================
print("== edit_pdf migrado (fonte) ==")
EPDF = ler("mod_edit_pdf/telas.py")
check(EPDF.count("ui.notify(") == 0,
      "edit_pdf: ui.notify substituído por notificar (timeout configurável)")
check(EPDF.count("botao(") >= 5,
      "edit_pdf: botões de ação via ui_comum.botao (>=5, admin em telas_administracao.py)")
check(not re.search(r"_btn_cls\b", EPDF) and not re.search(r"_btn_style\b", EPDF)
      and "cfg_tema" not in EPDF,
      "edit_pdf: helpers locais de tema removidos (ler_tema central)")
check('CORES["perigo"]' not in EPDF and 'CORES["primaria"]' not in EPDF and
      'CORES["destaque"]' not in EPDF and 'CORES["alerta"]' not in EPDF,
      "edit_pdf: sem CORES fixas em telas.py (borda do cabeçalho usa o tema do módulo)")
check('border-left-color:{tema["cor_botao"]}' in EPDF,
      "edit_pdf: borda do cabeçalho = cor_botao do tema do módulo (mesma cor dos botões)")
_EPDF_CFG = re.sub(r"PADROES_CFG = \{.*?\n    \}", "", EPDF, flags=re.S)
for _hex in ("#C62828", "#EF6C00", "#6A1B9A"):
    check(_hex not in _EPDF_CFG,
          f"edit_pdf: {_hex} ausente do fonte (fora dos defaults de reset)")
check('ui.button("Excluir selecionados"' not in EPDF and
      'variante="primario"' in EPDF and 'variante="perigo"' not in EPDF,
      "edit_pdf: Excluir selecionados via botao (primario igual aos demais, sem cru)")
check('ui.button("Enviar agora"' not in EPDF and 'variante="primario"' in EPDF,
      "edit_pdf: Enviar agora via botao (primario, sem cru)")
check('ui.button(icon="refresh"' not in EPDF and
      'botao("Atualizar", icone="refresh"' in EPDF,
      "edit_pdf: atualizar via botao padrão (mesmo visual dos demais, sem cru)")

# ================== 17. campo_cor ==================
print("== campo_cor ==")
import mod_intranet.bd_conexao as _cbd
_BD_CFG = {}
_CFG_GET_REAL = _cbd.get_config
_cbd.get_config = lambda chave, default="": _BD_CFG.get(chave, default)
_CB = lambda e: None


def _bruto(el):
    """Visual state tuple of a stub element (props/classes/style/tooltip/cb).

    Tupla de estado visual do elemento stub (props/classes/style/tooltips/
    callbacks + args/kwargs de criação) — base das comparações byte-idênticas.
    """
    return (el.tipo, el.args, dict(el.kwargs), el.props_str, el.classes_str,
            el.style_str, el.tooltips, el.callbacks)


novo()
_BD_CFG.clear(); _BD_CFG.update({"k_cor": "#ABCDEF"})
c1 = ui_comum.campo_cor("Rótulo", chave="k_cor", padrao="#000000",
                        ao_mudar=_CB, tooltip="dica")
novo()
c2 = _ui_mod.color_input("Rótulo", value="#ABCDEF") \
    .props("outlined dense").classes("w-full").tooltip("dica") \
    .on_value_change(_CB)
check(_bruto(c1) == _bruto(c2),
      "campo_cor(chave=) byte-idêntico à construção crua (valor resolvido)")
novo()
c1 = ui_comum.campo_cor("R", valor="#123456")
novo()
c2 = _ui_mod.color_input("R", value="#123456") \
    .props("outlined dense").classes("w-full")
check(_bruto(c1) == _bruto(c2),
      "campo_cor(valor=) byte-idêntico (sem chave, sem tooltip, sem cb)")
_BD_CFG.clear()
novo()
check(ui_comum.campo_cor("R", chave="falta", padrao="P") \
      .kwargs.get("value") == "P",
      "campo_cor: chave ausente no banco usa o padrao")
_cbd.get_config = lambda chave, default="": (_ for _ in ()).throw(
    RuntimeError("boom"))
try:
    novo()
    check(ui_comum.campo_cor("R", chave="k", padrao="P") \
          .kwargs.get("value") == "P",
          "campo_cor: falha de leitura usa padrao (fail-soft, sem exceção)")
finally:
    _cbd.get_config = lambda chave, default="": _BD_CFG.get(chave, default)
novo()
c1 = ui_comum.campo_cor("R", valor="v", props="dense outlined", largura="w-64")
novo()
c2 = _ui_mod.color_input("R", value="v").props("dense outlined") \
    .classes("w-64")
check(_bruto(c1) == _bruto(c2), "campo_cor: props/largura customizados")
novo()
c1 = ui_comum.campo_cor("R", valor="v", props="", largura="")
novo()
c2 = _ui_mod.color_input("R", value="v")
check(_bruto(c1) == _bruto(c2),
      "campo_cor: props/largura vazios não aplicam nada (réplica crua gest)")

# ================== 18. campo_texto ==================
print("== campo_texto ==")
novo()
_BD_CFG.clear(); _BD_CFG.update({"k_txt": "valor salvo"})
c1 = ui_comum.campo_texto("Rótulo", chave="k_txt", padrao="pad",
                          ao_mudar=_CB, tooltip="dica")
novo()
c2 = _ui_mod.input("Rótulo", value="valor salvo") \
    .props("outlined dense").classes("w-full").tooltip("dica") \
    .on_value_change(_CB)
check(_bruto(c1) == _bruto(c2),
      "campo_texto(chave=) byte-idêntico ao ui.input cru")
novo()
c1 = ui_comum.campo_texto("Rótulo", valor="v", multiline=True)
novo()
c2 = _ui_mod.textarea("Rótulo", value="v").props("outlined dense") \
    .classes("w-full")
check(_bruto(c1) == _bruto(c2) and c1.tipo == "textarea",
      "campo_texto(multiline=True) vira ui.textarea byte-idêntico")
novo()
c1 = ui_comum.campo_texto("R", valor="v", cor_texto="#FF0000",
                          cor_fundo="#EEEEEE")
check(c1.tipo == "input" and
      c1.style_str == "color:#FF0000;background-color:#EEEEEE;",
      "campo_texto: cores custom via style (color + background-color)")
novo()
check(ui_comum.campo_texto("R", valor="v").style_str == "",
      "campo_texto: sem style quando nenhuma cor informada")
_BD_CFG.clear()
novo()
check(ui_comum.campo_texto("R", chave="falta", padrao="P") \
      .kwargs.get("value") == "P",
      "campo_texto: chave ausente no banco usa o padrao")
_cbd.get_config = lambda chave, default="": (_ for _ in ()).throw(
    RuntimeError("boom"))
try:
    novo()
    check(ui_comum.campo_texto("R", chave="k", padrao="P") \
          .kwargs.get("value") == "P",
          "campo_texto: falha de leitura usa padrao (fail-soft)")
finally:
    _cbd.get_config = lambda chave, default="": _BD_CFG.get(chave, default)
novo()
c1 = ui_comum.campo_texto("Senha atual", senha=True)
novo()
c2 = _ui_mod.input("Senha atual", password=True,
                   password_toggle_button=True) \
    .props("outlined dense").classes("w-full")
check(_bruto(c1) == _bruto(c2) and
      c1.kwargs.get("password") is True and
      c1.kwargs.get("password_toggle_button") is True and
      "value" not in c1.kwargs,
      "campo_texto(senha=True) byte-idêntico à senha crua (kwargs password)")
novo()
c1 = ui_comum.campo_texto("Senha atual", senha=True, props="")
novo()
c2 = _ui_mod.input("Senha atual", password=True,
                   password_toggle_button=True).classes("w-full")
check(_bruto(c1) == _bruto(c2),
      "campo_texto(senha=True, props='') == troca_senha obrigatória crua")
novo()
c1 = ui_comum.campo_texto("R", valor="v", senha=True)
novo()
c2 = _ui_mod.input("R", value="v", password=True,
                   password_toggle_button=True) \
    .props("outlined dense").classes("w-full")
check(_bruto(c1) == _bruto(c2),
      "campo_texto(senha=True, valor=) repassa value + password juntos")
novo()
c1 = ui_comum.campo_texto("R")
novo()
c2 = _ui_mod.input("R").props("outlined dense").classes("w-full")
check(_bruto(c1) == _bruto(c2) and "password" not in c1.kwargs,
      "campo_texto default (sem senha) não injeta kwargs de password")
novo()
c1 = ui_comum.campo_texto("Chave única *", placeholder="ex.: folha_ponto",
                          props="outlined dense", largura="")
novo()
c2 = _ui_mod.input("Chave única *", placeholder="ex.: folha_ponto") \
    .props("outlined dense")
check(_bruto(c1) == _bruto(c2),
      "campo_texto(placeholder=, largura='') byte-idêntico (novo módulo)")

# ================== 19. campo_selecao ==================
print("== campo_selecao ==")
novo()
_BD_CFG.clear(); _BD_CFG.update({"k_sel": "medium"})
OPS = {"small": "Pequeno", "medium": "Médio", "large": "Grande"}
c1 = ui_comum.campo_selecao("Tamanho", OPS, chave="k_sel", padrao="medium",
                            ao_mudar=_CB)
novo()
c2 = _ui_mod.select(OPS, label="Tamanho", value="medium") \
    .props("outlined dense").classes("w-full").on_value_change(_CB)
check(_bruto(c1) == _bruto(c2),
      "campo_selecao(chave=) byte-idêntico ao ui.select cru")
novo()
c1 = ui_comum.campo_selecao("Tamanho", OPS, valor=1, props="dense outlined",
                            largura="")
novo()
c2 = _ui_mod.select(OPS, label="Tamanho", value=1).props("dense outlined")
check(_bruto(c1) == _bruto(c2),
      "campo_selecao: props custom + largura vazia (réplica crua gest)")
_BD_CFG.clear()
novo()
check(ui_comum.campo_selecao("T", OPS, chave="falta", padrao=1) \
      .kwargs.get("value") == 1,
      "campo_selecao: chave ausente no banco usa o padrao")
_cbd.get_config = lambda chave, default="": (_ for _ in ()).throw(
    RuntimeError("boom"))
try:
    novo()
    check(ui_comum.campo_selecao("T", OPS, chave="k", padrao=2) \
          .kwargs.get("value") == 2,
          "campo_selecao: falha de leitura usa padrao (fail-soft)")
finally:
    _cbd.get_config = lambda chave, default="": _BD_CFG.get(chave, default)
novo()
OPS_OBS = {"DEBUG": "DEBUG", "INFO": "INFO", "WARNING": "WARNING",
           "ERROR": "ERROR"}
c1 = ui_comum.campo_selecao("Nível mínimo", OPS_OBS, valor="INFO",
                            props="dense outlined",
                            tooltip="DEBUG, INFO, WARNING ou ERROR")
novo()
c2 = _ui_mod.select(OPS_OBS, label="Nível mínimo", value="INFO") \
    .props("dense outlined").classes("w-full") \
    .tooltip("DEBUG, INFO, WARNING ou ERROR")
check(_bruto(c1) == _bruto(c2),
      "campo_selecao(tooltip=, props 'dense outlined') byte-idêntico (Observabilidade)")
_cbd.get_config = _CFG_GET_REAL

# ================== 20. card_config ==================
print("== card_config ==")
novo()
_ORDEM = []


def _campo_ordem(i):
    def _criar():
        _ORDEM.append(i)
        return _ui_mod.input(f"campo {i}")
    return _criar


card = ui_comum.card_config(
    "Título", campos=tuple(_campo_ordem(i) for i in range(3)),
    legenda="legenda do card",
    colunas="sm:grid-cols-2 md:grid-cols-4")
check(card.tipo == "card" and card.classes_str == "w-full" and
      card.style_str == "background-color:#FAFAFA;color:#111111;",
      "card_config: card w-full com estilo do cartão do tema")
labs = [e for e in REG if e.tipo == "label"]
check(labs[0].args[0] == "Título" and
      labs[0].classes_str == "text-subtitle1 font-bold" and
      labs[0].style_str == "color:#212121",
      "card_config: título text-subtitle1 font-bold na cor do tema")
check(labs[1].args[0] == "legenda do card" and
      labs[1].classes_str == "text-caption text-grey-7 max-w-3xl -mt-2",
      "card_config: legenda com as classes do padrão atual")
grids = [e for e in REG if e.tipo == "grid"]
check(grids[0].classes_str == "w-full grid-cols-1 sm:grid-cols-2 md:grid-cols-4"
      and grids[0].style_str == "gap:1.25rem",
      "card_config: grid responsivo com colunas e gap 1.25rem")
check(_ORDEM == [0, 1, 2], "card_config: callables de campos na ordem")
check(all("col-span-full" not in e.classes_str for e in REG
          if e.tipo == "input"),
      "card_config: 3 campos (ímpar <= 3) sem col-span-full")
novo(); _ORDEM.clear()
ui_comum.card_config("T", campos=tuple(_campo_ordem(i) for i in range(4)))
check(all("col-span-full" not in e.classes_str for e in REG
          if e.tipo == "input"),
      "card_config: 4 campos (par) sem col-span-full")
novo(); _ORDEM.clear()
ui_comum.card_config("T", campos=tuple(_campo_ordem(i) for i in range(5)))
primeiros = [e for e in REG if e.tipo == "input"]
check(primeiros and "col-span-full" in primeiros[0].classes_str and
      all("col-span-full" not in c.classes_str for c in primeiros[1:]),
      "card_config: 5 campos (ímpar > 3) → primeiro col-span-full")
novo(); _ORDEM.clear()
ui_comum.card_config("T", campos=tuple(_campo_ordem(i) for i in range(3)),
                     destaque_impar=False, colunas="sm:grid-cols-2",
                     gap="0.75rem")
grids = [e for e in REG if e.tipo == "grid"]
check(grids[0].classes_str == "w-full grid-cols-1 sm:grid-cols-2" and
      grids[0].style_str == "gap:0.75rem",
      "card_config: colunas/gap customizados")
novo()
ui_comum.card_config("T", acoes=[("Salvar", "save", lambda: None, "dica")])
rows = [e for e in REG if e.tipo == "row"]
btns = [e for e in REG if e.tipo == "button"]
check(rows and rows[-1].classes_str == "w-full justify-center" and
      rows[-1].style_str == "gap: 0.5rem",
      "card_config: acoes em row centralizada (gap 0.5rem)")
check(len(btns) == 1 and btns[0].args[0] == "Salvar" and
      btns[0].kwargs.get("icon") == "save" and
      btns[0].props_str == "unelevated no-caps size=md" and
      btns[0].classes_str == f"shadow-sm {_CEI}" and
      btns[0].style_str == _CES and btns[0].tooltips == ["dica"],
      "card_config: ação via ui_comum.botao (tema do módulo)")
novo()
card = ui_comum.card_config("T", cor_fundo="#123456", cor_texto="#654321",
                            cor_titulo="#ABCDEF")
labs = [e for e in REG if e.tipo == "label"]
check(card.style_str == "background-color:#123456;color:#654321;" and
      labs[0].style_str == "color:#ABCDEF",
      "card_config: cor_fundo/cor_texto/cor_titulo customizados")
novo(); _ORDEM.clear()


def _campo_boom():
    _ORDEM.append("boom")
    raise RuntimeError("campo quebrado")


card = ui_comum.card_config(
    "T", campos=(_campo_boom, _campo_ordem(1)))
check(card is not None and _ORDEM == ["boom", 1],
      "card_config: campo que falha é ignorado (fail-soft) e os demais seguem")
novo()
try:
    ui_comum.card_config("T", acoes=[("incompleto",)])
    check(True, "card_config: ação malformada ignorada sem exceção")
except Exception:
    check(False, "card_config: ação malformada ignorada sem exceção")

# ============ 20b. card_config(extras=) — conteúdo entre grid e ações ============
print("== card_config: extras ==")
novo(); _ORDEM.clear()
_EXTRAS_MARCAS = []


def _extra_ok():
    _EXTRAS_MARCAS.append("extra")
    return _ui_mod.label("conteúdo extra")


def _extra_boom():
    raise RuntimeError("boom extra")


card_x = ui_comum.card_config(
    "T", campos=(_campo_ordem(0),),
    extras=[_extra_ok, _extra_boom],
    acoes=[("Salvar", "save", lambda: None)])
tipos_card = [e.tipo for e in REG]
check(card_x is not None and _EXTRAS_MARCAS == ["extra"],
      "card_config(extras): extra válido executado e extra quebrado ignorado "
      "(fail-soft, card montado)")
check(tipos_card == ["card", "label", "grid", "input", "label", "row",
                     "button"],
      "card_config(extras): conteúdo criado ENTRE o grid e a row de ações")
novo()
ui_comum.card_config("T")
labs_dflt = [e for e in REG if e.tipo == "label"]
check(len(labs_dflt) == 1,
      "card_config(extras=() default): nenhum elemento extra (byte-idêntico)")

# ================== 21. campos de configuração migrados (fonte) ==================
print("== campos de configuração (fonte) ==")
TELA = ler("mod_intranet/tela_configuracoes.py")
check(TELA.count("ui.color_input(") == 0,
      "tela_configuracoes: ui.color_input removido (7 → 0)")
check(TELA.count("ui.select(") == 0,
      "tela_configuracoes: ui.select removido (3 → 0, selects de Observabilidade migrados)")
check(TELA.count("ui.dialog(") == 0,
      "tela_configuracoes: ui.dialog removido (1 → 0, confirmar via dialogo_card)")
check(TELA.count("ui.input(") == 2,
      "tela_configuracoes: ui.input só em _campo_empilhado/_campo_icone (7 → 2)")
check(TELA.count("ui_comum.campo_cor(") == 7,
      "tela_configuracoes: 7 campos de cor via ui_comum.campo_cor")
check(TELA.count("ui_comum.campo_selecao(") == 5,
      "tela_configuracoes: 5 selects via campo_selecao (botões + 3 Observabilidade + banco de dados)")
check(TELA.count("ui_comum.campo_texto(") == 16,
      "tela_configuracoes: 16 textos via campo_texto (3 gerais + 7 fixos "
      "+ ícone/raiz + novo módulo + DSN postgres)")
check(TELA.count("_campo_empilhado(") == 13,
      "tela_configuracoes: _campo_empilhado reduzido em 3 (16 → 13, "
      "card gerais migrado)")
check(TELA.count("ui_comum.card_config(") == 0 and
      'card_admin("Configurações gerais do sistema"' in TELA and
      "Intervalo de backup (horas)" in TELA,
      "tela_configuracoes: card 'Configurações gerais' via card_admin + rodapé")
GERAIS = TELA[TELA.index("# ---- Configurações gerais (RF-57) ----"):
              TELA.index("# ---- Ícones: aba do navegador")]
check(GERAIS.count("campo_texto(") == 4,
      "tela_configuracoes: 3 campos + pasta raiz do card gerais via campo_texto")
TMF = ler("mod_intranet/tema_modulo.py")
check(TMF.count("ui.color_input(") == 0 and TMF.count("ui.select(") == 0,
      "bloco_aparencia: color_input/select crus removidos (4+1 → 0)")
check(TMF.count("ui_comum.campo_cor(") == 6 and
      TMF.count("ui_comum.campo_selecao(") == 1 and
      TMF.count("ui_comum.campo_texto(") == 3,
      "bloco_aparencia + campo_modulo: campos via ui_comum (6 cor + 1 seleção + 3 texto)")
GEST3 = ler("mod_gest_cad_usuario/telas.py")
check(GEST3.count("ui.color_input(") == 0,
      "gest_cad: ui.color_input removido (4 → 0)")
check(GEST3.count("ui.select(") == 7,
      "gest_cad: select do crud migrated (8 → 7, admin via /admin/usuarios)")
check(GEST3.count("ui.input(") == 16,
      "gest_cad: input do crud migrated (17 → 16)")
check(GEST3.count("ui.number(") == 0,
      "gest_cad: ui.number removido (admin via /admin/usuarios)")
GEST_ADM = ler("mod_gest_cad_usuario/telas_administracao.py")
check("bloco_aparencia(" in GEST_ADM and "rodape_salvar_restaurar(" in GEST_ADM,
      "gest_cad: painel admin em telas_administracao.py via bloco_aparencia + rodapé")
check("_painel_administracao" not in GEST3,
      "gest_cad/telas.py: _painel_administracao removido (admin via /admin/usuarios)")
LAYOUT = ler("mod_intranet/telas.py")
check(LAYOUT.count("ui.input(") == 0,
      "layout_tela: ui.input removido (9 → 0, perfil + senhas via campo_texto)")
check(LAYOUT.count("ui_comum.campo_texto(") == 16,
      "layout_tela: 16 campos via campo_texto (3 perfil + 3 senha perfil + 4 credenciais + 1 novo nome + 3 dados master)")
check(LAYOUT.count("senha=True") == 9,
      "layout_tela: 9 campos de senha via campo_texto(senha=True)")
TMF2 = ler("mod_intranet/tema_modulo.py")
check(TMF2.count("ui.input(") == 0 and "def campo_modulo" in TMF2,
      "tema_modulo: sem ui.input cru e campo_modulo restaurado (campos via campo_texto)")
check("_campo_empilhado" in TELA and "_campo_icone" in TELA and
      'ui.button("Botão exemplo"' in TELA and 'ui.button("Contorno"' in TELA,
      "tela_configuracoes: exceções preservadas (_campo_empilhado/_campo_icone/botões da prévia)")
check("receber_ico" in TELA and "remover_fav" in TELA,
      "tela_configuracoes: callbacks do card 'Ícones' presentes")
_ini_ico = "# ---- Ícones: aba do navegador + identidade do sistema ----"
_regiao_ico = TELA[TELA.index(_ini_ico):TELA.index("# ABA: E-MAIL / SMTP")]
check('card_admin("Ícones"' in _regiao_ico
      and 'rodape_salvar_restaurar(' in _regiao_ico
      and "receber_ico" in _regiao_ico and "remover_fav" in _regiao_ico
      and 'label="Enviar arquivo .ico"' in _regiao_ico,
      "tela_configuracoes: card 'Ícones' recolhível com rodapé Restaurar/Aplicar")
BK = ler("mod_intranet/dialogo_backup.py")
check(BK.count("ui.number(") == 1,
      "dialogo_backup: ui.number permanece cru (candidato futuro a campo_numero)")

# ================== 22. cabecalho (tema do módulo) ==================
print("== cabecalho: tema do módulo ==")
novo()
aba_modulo.cabecalho("Título", "sub <code>x</code>")
cards_h = [e for e in REG if e.tipo == "card"]
labs_h = [e for e in REG if e.tipo == "label"]
check(cards_h and cards_h[0].classes_str == "w-full border-l-8" and
      cards_h[0].style_str == "border-left-color:#1565C0" and
      labs_h[0].classes_str == "text-h5 font-bold whitespace-nowrap cabecalho-titulo" and
      labs_h[0].style_str == "color:#212121" and
      labs_h[1].classes_str == "text-caption text-grey-6" and
      not [e for e in REG if e.tipo == "query"],
      "cabecalho sem chave: borda/título CORES e .q-page intocado (byte-idêntico)")
_LER_CAB = tm.ler_tema


def _tema_cab(chave, *a, **k):
    return {"cor_botao": "#AA0000", "cor_texto_botao": "#FFFFFF",
            "cor_fundo": "#0000CC", "cor_titulo": "#00BB00",
            "btn_tamanho": "medium", "texto_header": "cab"}


def _tema_cab_boom(chave, *a, **k):
    raise RuntimeError("boom")


try:
    tm.ler_tema = _tema_cab
    novo()
    aba_modulo.cabecalho("T", "sub", chave_modulo="empenhos")
    cards_h = [e for e in REG if e.tipo == "card"]
    labs_h = [e for e in REG if e.tipo == "label"]
    queries_h = [e for e in REG if e.tipo == "query"]
    check(cards_h[0].style_str == "border-left-color:#AA0000" and
          labs_h[0].style_str == "color:#00BB00" and queries_h and
          queries_h[0].args == (".q-page",) and
          queries_h[0].style_str == "background-color:#0000CC",
          "cabecalho(chave_modulo): borda=cor_botao, título=cor_titulo, fundo pinta .q-page")
    tm.ler_tema = lambda chave, *a, **k: dict(_tema_cab(chave), cor_fundo="")
    novo()
    aba_modulo.cabecalho("T", chave_modulo="blog")
    check([e for e in REG if e.tipo == "card"][0].style_str ==
          "border-left-color:#AA0000" and
          not [e for e in REG if e.tipo == "query"],
          "cabecalho(chave_modulo): cor_fundo vazio do tema = herda (.q-page intocado)")
    novo()
    aba_modulo.cabecalho("T", chave_modulo="empenhos", cor_borda="#111111",
                         cor_titulo="#222222", cor_fundo="#333333")
    cards_h = [e for e in REG if e.tipo == "card"]
    labs_h = [e for e in REG if e.tipo == "label"]
    queries_h = [e for e in REG if e.tipo == "query"]
    check(cards_h[0].style_str == "border-left-color:#111111" and
          labs_h[0].style_str == "color:#222222" and queries_h and
          queries_h[0].style_str == "background-color:#333333",
          "cabecalho: parâmetros explícitos vencem o tema")
    novo()
    aba_modulo.cabecalho("T", chave_modulo="empenhos", cor_fundo="")
    check([e for e in REG if e.tipo == "card"][0].style_str ==
          "border-left-color:#AA0000" and
          not [e for e in REG if e.tipo == "query"],
          "cabecalho: cor_fundo='' explícito herda mesmo com tema pintado")
    tm.ler_tema = _tema_cab_boom
    novo()
    aba_modulo.cabecalho("T", "sub", chave_modulo="empenhos")
    cards_h = [e for e in REG if e.tipo == "card"]
    labs_h = [e for e in REG if e.tipo == "label"]
    check(cards_h[0].style_str == "border-left-color:#1565C0" and
          labs_h[0].style_str == "color:#212121" and
          not [e for e in REG if e.tipo == "query"],
          "cabecalho: falha ao ler tema → defaults + sem crash (fail-soft)")
finally:
    tm.ler_tema = _LER_CAB

print("== cabecalho: migração dos módulos (fonte) ==")
for _rel, _chave, _antigo in (
        ("mod_renomear_empenho/telas.py", "empenhos", 'cor_borda="#2E7D32"'),
        ("mod_auditoria/telas.py", "auditoria", 'cor_borda="#C62828"'),
        ("mod_blog/telas.py", "blog", 'cor_borda="#7B1FA2"'),
        ("mod_solicita_impressao/telas.py", "solicita_impressao",
         'cor_borda="#EF6C00"'),
        ("mod_gest_cad_usuario/telas.py", "usuarios", "cor_borda=t_cor_botao")):
    F = ler(_rel)
    check(_antigo not in F and f'chave_modulo="{_chave}"' in F and
          'cor_borda="#' not in F,
          f"{_rel}: cabeçalho via chave_modulo='{_chave}' (borda hardcoded removida)")

print("== campo_modulo: restaurado (fonte) ==")
TMF3 = ler("mod_intranet/tema_modulo.py")
_CM = TMF3[TMF3.index("def campo_modulo"):]
check("def campo_modulo" in TMF3,
      "tema_modulo: def campo_modulo presente (cupê 'Edição do módulo')")
check(_CM.count("campo_texto(") == 2,
      "campo_modulo: 2 campos de texto via ui_comum.campo_texto (nome + ícone)")
check('ui.expansion("Edição do módulo", icon="settings_applications")' in _CM
      and 'rodape_salvar_restaurar(salvar, chave_modulo=chave_modulo' in _CM
      and 'rotulo_salvar="Salvar módulo"' in _CM,
      "campo_modulo: expansion padronizada + rodapé com rotulo_salvar='Salvar módulo'")
check(
    'campo_modulo(usuario_logado, "auditoria")' not in ler("mod_auditoria/telas.py"),
    "mod_auditoria/telas.py: campo_modulo removido (admin via /admin/auditoria)")
check(
    'campo_modulo(usuario_logado, "blog")' not in ler("mod_blog/telas.py"),
    "mod_blog/telas.py: campo_modulo removido (admin via /admin/blog)")
check(
    'campo_modulo(usuario_logado, "editar_pdf")' not in ler("mod_edit_pdf/telas.py"),
    "mod_edit_pdf/telas.py: campo_modulo removido (admin via /admin/editar_pdf)")
check(
    'campo_modulo(ator, "usuarios")' not in ler("mod_gest_cad_usuario/telas.py"),
    "mod_gest_cad_usuario/telas.py: campo_modulo removido (admin via /admin/usuarios)")
check(
    'campo_modulo(usuario_logado, "empenhos")' not in ler("mod_renomear_empenho/telas.py"),
    "mod_renomear_empenho/telas.py: campo_modulo removido (admin via /admin/empenhos)")
check(
    'campo_modulo(usuario_logado, "solicita_impressao")' not in ler("mod_solicita_impressao/telas.py"),
    "mod_solicita_impressao/telas.py: campo_modulo removido (admin via /admin/solicita_impressao)")

print("== campo_modulo: stub byte-idêntico ==")
novo()
_retorno_cm = tema_modulo.campo_modulo("admin", "blog",
                                       nome_atual="Blog Corporativo",
                                       icone_atual="article", ativo_atual=True)
exp_cm = [e for e in REG if e.tipo == "expansion"]
check(callable(_retorno_cm) and len(exp_cm) == 1 and
      exp_cm[0].args == ("Edição do módulo",) and
      exp_cm[0].kwargs.get("icon") == "settings_applications" and
      exp_cm[0].classes_str == "w-full",
      "campo_modulo: expansion 'Edição do módulo' (icon=settings_applications, w-full) e retorna salvar")
ins_cm = [e for e in REG if e.tipo == "input"]
check(len(ins_cm) == 2 and
      ins_cm[0].args == ("Nome de exibição do módulo",) and
      ins_cm[0].kwargs.get("value") == "Blog Corporativo" and
      ins_cm[0].props_str == "outlined dense" and
      ins_cm[0].classes_str == "w-full" and not ins_cm[0].tooltips,
      "campo_modulo: campo nome byte-idêntico (outlined dense, w-full, sem tooltip)")
check(ins_cm[1].args == ("Ícone (Material Icons)",) and
      ins_cm[1].kwargs.get("value") == "article" and
      ins_cm[1].props_str == "outlined dense" and
      ins_cm[1].classes_str == "w-full" and
      ins_cm[1].tooltips == ["Nome do ícone Material, ex.: article, folder_open, print"],
      "campo_modulo: campo ícone byte-idêntico (props/classes + tooltip Material)")
sw_cm = [e for e in REG if e.tipo == "switch"]
check(len(sw_cm) == 1 and
      sw_cm[0].args == ("Módulo ativo (visível para os usuários)",) and
      sw_cm[0].kwargs.get("value") is True,
      "campo_modulo: switch cru 'Módulo ativo' com valor do banco")
rows_cm = [e for e in REG if e.tipo == "row"]
btns_cm = [e for e in REG if e.tipo == "button"]
check(len(rows_cm) == 1 and rows_cm[0].classes_str == "w-full justify-end mt-2 flex-wrap"
      and rows_cm[0].style_str == "gap: 0.5rem" and len(btns_cm) == 1 and
      btns_cm[0].args == ("Salvar módulo",) and
      btns_cm[0].kwargs.get("icon") == "save" and
      btns_cm[0].props_str == "unelevated no-caps size=md" and
      btns_cm[0].classes_str == f"shadow-sm {_CEI}" and
      btns_cm[0].style_str == _CES,
      "campo_modulo: rodapé via rodape_salvar_restaurar (fábrica botao, tema do módulo)")

print()
print(f"RESULTADO: {_OK} OK, {_TOTAL - _OK} falha(s) de {_TOTAL} verificações")
sys.exit(0 if _OK == _TOTAL else 1)
