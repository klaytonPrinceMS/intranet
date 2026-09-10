"""Verificação das classes novas do núcleo (CrudBase, ui_painel, ui_form,
ui_comum em classes, banco_conexao).

Script standalone (NÃO pytest). Cobre:
- `CrudBase`: conexão (WAL/FK/synchronous), atalhos CRUD, `executar_muitas`,
  `criar_tabela`, transação atômica com rollback em exceção;
- gancho de auditoria (`registrar_hook_auditoria` + `audit_log`) e
  `audit_reg` fail-soft;
- `banco_conexao`: SQLite default, Postgres fail-soft sem driver, DSN
  mascarado;
- classes de UI (`BotaoFabrica`, `Dialogo`, `Campo*`, `Cartao`) com
  equivalência 1:1 dos wrappers funcionais (tema fixado via monkeypatch);
- `GradeTabela`/`PainelLista`/`FormularioBuilder` (headless, stub NiceGUI).

Execute: .venv/bin/python test/teste_classes_crud.py
"""
import os
import sys
import tempfile
import types

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


# ================== STUB DE NICEGUI (registra saída visual) ==================
REG = []


class _El:
    def __init__(self, tipo, *args, **kwargs):
        self.tipo = tipo
        self.args = args
        self.kwargs = kwargs
        self.value = kwargs.get("value")
        self.props_str = ""
        self.classes_str = ""
        self.style_str = ""
        self.tooltips = []
        self.callbacks = []
        self.clears = 0

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

    def clear(self):
        self.clears += 1
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
              "switch", "number", "date"):
    setattr(_ui_mod, _nome, _fab(_nome))

_nice = types.ModuleType("nicegui")
_nice.ui = _ui_mod
_nice.app = types.SimpleNamespace(add_static_files=lambda *a, **k: None)
sys.modules["nicegui"] = _nice
sys.modules["nicegui.ui"] = _ui_mod

# ============ TEMA FIXADO (monkeypatch — não toca no banco) ============
from nicegui import ui
import mod_intranet.tema_modulo as tm

COR = "#0F62FE"
tm.ler_tema = lambda chave="intranet": {
    "cor_botao": COR, "cor_texto_botao": "#FFFFFF", "btn_tamanho": "medium",
    "cor_titulo": "#212121", "cor_fundo": "", "texto_header": ""}
tm.estilo_cartao = lambda chave="intranet": \
    "background-color:#FAFAFA;color:#111111;"
tm.btn_style = lambda c, t: f"background-color:{c};color:{t};"
tm.btn_cls = lambda s: "q-pa-sm"

from mod_intranet.ui_comum import (BotaoFabrica, Dialogo, Cartao, CampoBase,
                                   CampoCor, CampoTexto, CampoSelecao,
                                   botao, botao_icone, dialogo_card,
                                   campo_cor, campo_texto, campo_selecao,
                                   card_config)
from mod_intranet.ui_painel import GradeTabela, PainelLista
from mod_intranet.ui_form import FormularioBuilder
from mod_intranet.crud_base import CrudBase, audit_reg
from mod_intranet import banco_conexao as bc
from mod_intranet import bd_manipulador as mbd
from mod_intranet.bd_conexao import get_config


def labels():
    return [e for e in REG if e.tipo == "label"]


def buttons():
    return [e for e in REG if e.tipo == "button"]


def por_tipo(tipo):
    return [e for e in REG if e.tipo == tipo]


# ================== 1. CrudBase (SQLite real em temp) ==================
print("== CrudBase ==")
_tmp = tempfile.mkdtemp(prefix="teste_classes_crud_")
DB = os.path.join(_tmp, "t.db")
crud = CrudBase(DB, "teste", foreign_keys=True)

conn = crud._conectar()
fm = conn.execute("PRAGMA journal_mode").fetchone()[0]
sinc = conn.execute("PRAGMA synchronous").fetchone()[0]
fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
conn.close()
check(fm == "wal" and sinc == 1 and fk == 1,
      "_conectar: WAL + synchronous=NORMAL + foreign_keys=ON")

check(crud.criar_tabela(
    "CREATE TABLE IF NOT EXISTS pai (id INTEGER PRIMARY KEY, nome TEXT)"),
    "criar_tabela: DDL idempotente com commit")
check(crud.criar_tabela(
    "CREATE TABLE IF NOT EXISTS filho (id INTEGER PRIMARY KEY, "
    "pai_id INTEGER NOT NULL REFERENCES pai(id) ON DELETE CASCADE)"),
    "criar_tabela: FK CASCADE")

check(crud.criar("INSERT INTO pai (nome) VALUES (?)", ("ana",)) == 1,
      "criar: INSERT devolve lastrowid")
check(crud.criar("INSERT INTO pai (nome) VALUES (?)", ("bruno",)) == 2,
      "criar: lastrowid incremental")
check(crud.obter("SELECT nome FROM pai WHERE id=?", (1,)) == ("ana",),
      "obter: fetchone devolve a linha")
check([r[0] for r in crud.listar("SELECT nome FROM pai ORDER BY id")] ==
      ["ana", "bruno"], "listar: fetchall ordenado")
check(crud.atualizar("UPDATE pai SET nome=? WHERE id=?", ("ANA", 1)) == 1,
      "atualizar: rowcount do UPDATE")
check(crud.executar_muitas(
    "INSERT INTO pai (nome) VALUES (?)", [("carla",), ("diego",)]) == 2,
      "executar_muitas: lote gravado")

try:
    with crud.transacao() as cur:
        cur.execute("INSERT INTO pai (nome) VALUES (?)", ("eva",))
        raise RuntimeError("boom")
except RuntimeError:
    pass
check(crud.obter("SELECT COUNT(*) FROM pai WHERE nome='eva'")[0] == 0,
      "transacao: rollback em exceção (linha não persistida)")

with crud.transacao() as cur:
    cur.execute("INSERT INTO pai (nome) VALUES (?)", ("eva",))
check(crud.obter("SELECT COUNT(*) FROM pai WHERE nome='eva'")[0] == 1,
      "transacao: commit no fim do bloco (linha persistida)")

check(crud.excluir("DELETE FROM pai WHERE nome=?", ("diego",)) == 1,
      "excluir: DELETE com rowcount")
check(crud.obter("SELECT COUNT(*) FROM pai")[0] == 4,
      "estado final: 4 registros (ana/bruno/carla/eva)")

try:
    crud.obter("SELECT * FROM tabela_inexistente")
    _subiu = False
except Exception:
    _subiu = True
check(_subiu, "falha de SQL PROPAGA (fail-loud para a camada de negócio)")

# ================== 2. Gancho de auditoria + audit_reg ==================
print("== auditoria ==")
capturado = []
mbd.registrar_hook_auditoria(
    lambda *a, **k: capturado.append((a, k)))
mbd.audit_log("u1", "blog", "acao", "desc")
check(len(capturado) == 1 and capturado[0][0][:5] ==
      ("u1", "blog", "acao", "desc", None),
      "registrar_hook_auditoria: audit_log grava pelo gancho (sem import)")
mbd.registrar_hook_auditoria(None)


def _boom(*a, **k):
    raise RuntimeError("auditoria fora do ar")


_original = mbd.audit_log
mbd.audit_log = _boom
_nao_subiu = True
try:
    audit_reg("u2", "modulo", "acao", "alvo", "detalhe")
except Exception:
    _nao_subiu = False
mbd.audit_log = _original
check(_nao_subiu, "audit_reg: falha de auditoria NÃO derruba o negócio "
                  "(fail-soft, loguru registra)")

# ================== 3. banco_conexao (SQLite default, PG fail-soft) =====
print("== banco_conexao ==")
check(bc.sgbd_ativo() == "sqlite", "sgbd_ativo: default sqlite (tb_config)")
check(bc.obter_engine() is None,
      "obter_engine: None com sqlite (nada a criar)")
check(bc.engine_disponivel() is True,
      "engine_disponivel: True com sqlite")

check(bc._dsn_publico(
    "postgresql+psycopg2://intranet:senha@localhost:5432/intranet") ==
    "postgresql+psycopg2://***@localhost:5432/intranet",
      "_dsn_publico: credenciais mascaradas para log")
check(bc._dsn_publico("postgresql://localhost:5432/intranet") ==
      "postgresql://localhost:5432/intranet",
      "_dsn_publico: DSN sem credenciais volta intacto")

_sgbd_original = bc.sgbd_ativo
bc.sgbd_ativo = lambda: "postgres"
check(bc.obter_engine() is not None,
      "obter_engine: postgres com driver instalado → engine lazy (não None)")
check(bc.engine_disponivel() is True,
      "engine_disponivel: True quando a engine postgres foi criada (lazy)")
bc.sgbd_ativo = _sgbd_original

# ================== 4. BotaoFabrica (equivalência com o wrapper) =========
print("== BotaoFabrica ==")
REG.clear()
el_classe = BotaoFabrica("intranet").criar("OK", variante="primario")
REG.clear()
el_func = botao("OK", variante="primario")
check(el_classe.props_str == el_func.props_str and
      el_classe.classes_str == el_func.classes_str and
      el_classe.style_str == el_func.style_str and
      el_classe.tooltips == el_func.tooltips,
      "botao (wrapper) == BotaoFabrica.criar (props/classes/estilo/tooltip)")
check(COR in el_classe.style_str and "no-caps" in el_classe.props_str and
      "size=md" in el_classe.props_str,
      "variante primario tematizada (cor do tema fixado)")

REG.clear()
el_cor = BotaoFabrica().criar("X", variante="primario", cor="#FF0000")
check("color=#FF0000" in el_cor.props_str and el_cor.style_str == "" and
      "shadow-sm" in el_cor.classes_str,
      "cor explícita: props color= e estilo limpo (tema não lido)")

_subiu_valor = False
try:
    BotaoFabrica().criar("X", variante="zz")
except ValueError:
    _subiu_valor = True
check(_subiu_valor, "variante inválida levanta ValueError (fail-fast)")

REG.clear()
el_ic = botao_icone("delete", on_click=lambda: None)
check(el_ic is not None and "flat round dense size=sm" in el_ic.props_str,
      "botao_icone: atalho de ação de linha (icone tematizado)")

# ================== 5. Dialogo (classe) e wrapper ========================
print("== Dialogo ==")
REG.clear()
d1 = Dialogo("Título", "w-[420px]", chave_modulo="intranet")
with d1 as (dlg_a, card_a):
    check(card_a.classes_str == "w-[420px] max-h-[90vh]" and
          card_a.style_str == "background-color:#FAFAFA;color:#111111;",
          "Dialogo: largura + max-h + estilo do cartão (tema fixado)")
    rotulos = labels()
    check(any(l.args and l.args[0] == "Título" and
              "text-h6" in l.classes_str for l in rotulos),
          "Dialogo: título text-h6 criado dentro do card")
    check(len(por_tipo("separator")) == 1,
          "Dialogo: separador após o título")
d1.abrir()
d1.fechar()

REG.clear()
d2 = Dialogo(largura="", max_altura=False)
with d2 as (dlg_b, card_b):
    check(card_b.classes_str == "" and card_b.style_str ==
          "background-color:#FAFAFA;color:#111111;",
          "Dialogo(largura='', max_altura=False) == shell cru do confirmar")

REG.clear()
with dialogo_card("Título", "w-[420px]") as (dlg_c, card_c):
    check(card_c.classes_str == card_a.classes_str and
          card_c.style_str == card_a.style_str,
          "dialogo_card (wrapper) == Dialogo (classes/estilo)")

# ================== 6. Campos (classes e wrappers) =======================
print("== Campo* ==")
REG.clear()
ct = CampoTexto("Geral", chave="titulo_sistema").montar()
esperado = get_config("titulo_sistema", "")
check(ct.kwargs.get("value") == esperado,
      "CampoTexto: valor resolvido via tb_config (chave)")
REG.clear()
ctw = campo_texto("Geral", chave="titulo_sistema")
check(ctw.kwargs.get("value") == ct.kwargs.get("value") and
      ctw.props_str == "outlined dense" and ctw.classes_str == "w-full",
      "campo_texto (wrapper) == CampoTexto.montar")

REG.clear()
cs = CampoTexto("Senha", "123", senha=True).montar()
check(cs.kwargs.get("password") is True and
      cs.kwargs.get("password_toggle_button") is True,
      "CampoTexto: senha com botão exibir/ocultar")
REG.clear()
cm = CampoTexto("Texto", multiline=True, cor_texto="#111111").montar()
check(len(por_tipo("textarea")) == 1 and
      cm.style_str == "color:#111111;",
      "CampoTexto: multiline → textarea + estilo inline")
REG.clear()
csin = CampoTexto("Puro").montar()
check("value" not in csin.kwargs,
      "CampoTexto: sem valor/chave → kwarg value NÃO repassado (cru)")

REG.clear()
ct2 = CampoTexto("Com extras", "x", tooltip="tt", placeholder="ph",
                 ao_mudar=lambda e: None).montar()
check(ct2.tooltips == ["tt"] and ct2.kwargs.get("placeholder") == "ph" and
      len(ct2.callbacks) == 1,
      "CampoTexto: tooltip + placeholder + ao_mudar")

REG.clear()
cc = CampoCor("Cor", chave="cor_principal").montar()
check(cc.tipo == "color_input" and
      cc.kwargs.get("value") == get_config("cor_principal", ""),
      "CampoCor: color_input com valor de tb_config")
REG.clear()
csw = campo_selecao("Tamanho", ["small", "medium"], "medium")
check(csw.tipo == "select" and csw.kwargs.get("value") == "medium" and
      csw.kwargs.get("label") == "Tamanho",
      "campo_selecao (wrapper): ui.select com label+valor")

# ================== 7. Cartao (classe) e wrapper =========================
print("== Cartao ==")
REG.clear()
cartao = Cartao(chave_modulo="intranet", colunas="sm:grid-cols-2")
extras = {}


def _campo1():
    extras["c1"] = ui.label("campo1")
    return extras["c1"]


card1 = cartao.montar("Título", campos=(_campo1,), legenda="legenda",
                      acoes=(("Salvar", "save", lambda: None, "tt"),),
                      extras=(lambda: extras.setdefault("extra",
                                                        ui.label("extra")),))
check(card1.classes_str == "w-full" and
      card1.style_str == "background-color:#FAFAFA;color:#111111;",
      "Cartao: w-full + estilo do tema")
tit = labels()[0]
check(tit.args[0] == "Título" and "text-subtitle1 font-bold" in
      tit.classes_str and tit.style_str == "color:#212121",
      "Cartao: título bold na cor do tema")
check(any(l.args and l.args[0] == "legenda" and "text-caption" in
          l.classes_str for l in labels()),
      "Cartao: legenda caption")
check(extras.get("c1") is not None and
      extras["c1"].classes_str == "",
      "Cartao: campo criado dentro do grid (sem destaque)")
grids = por_tipo("grid")
check(grids and grids[0].kwargs.get("columns") is None and
      "w-full grid-cols-1 sm:grid-cols-2" in grids[0].classes_str and
      grids[0].style_str == "gap:1.25rem",
      "Cartao: grid com colunas e gap")
acao_btn = [b for b in buttons() if b.tooltips == ["tt"]]
check(acao_btn and acao_btn[0].args[0] == "Salvar" and
      acao_btn[0].kwargs.get("icon") == "save",
      "Cartao: ação (rotulo, icone, callback, tooltip)")
check(any(l.args and l.args[0] == "extra" for l in labels()),
      "Cartao: extra renderizado entre grid e ações")

REG.clear()
cartao_d = Cartao(chave_modulo="intranet")


def _campo_impar(i):
    def _criar():
        return ui.label(f"c{i}")
    return _criar


card2 = cartao_d.montar("Ímpar", campos=tuple(
    _campo_impar(i) for i in range(5)))
c0 = [e for e in labels() if e.args and e.args[0] == "c0"]
check(len(c0) == 1 and "col-span-full" in c0[0].classes_str,
      "Cartao: destaque_impar com 5 campos → 1º col-span-full")

REG.clear()
card3 = card_config("Título", campos=(_campo1,), chave_modulo="intranet",
                    colunas="sm:grid-cols-2")
check(card3.classes_str == card1.classes_str and
      card3.style_str == card1.style_str,
      "card_config (wrapper) == Cartao.montar")

# ================== 8. GradeTabela =======================================
print("== GradeTabela ==")
REG.clear()
g = GradeTabela([("Nome", "1fr"), ("Qtd", "")])
chamadas = []


def _cel(d):
    ui.label(d["nome"])
    ui.label(str(d["qtd"]))


def _aco(d, i):
    chamadas.append((d["nome"], i))


grid = g.montar([{"nome": "a", "qtd": 1}, {"nome": "b", "qtd": 2}],
                _cel, _aco, classes_extra="mt-2")
check(grid.kwargs.get("columns") == "1fr auto auto" and
      "w-full items-center mt-2" in grid.classes_str and
      grid.style_str == "gap:0.5rem",
      "GradeTabela: colunas + auto p/ ações + classes_extra + gap")
cabe = labels()[:3]
check([l.args[0] for l in cabe] == ["Nome", "Qtd", ""] and
      all("text-caption text-grey-7 font-bold" in l.classes_str
          for l in cabe),
      "GradeTabela: cabeçalho caption (coluna de ações vazia)")
check(chamadas == [("a", 0), ("b", 1)],
      "GradeTabela: acoes(dado, indice) por linha")


def _cel_ruim(d):
    if d["nome"] == "a":
        raise RuntimeError("célula quebrada")
    ui.label(d["nome"])


REG.clear()
chamadas.clear()
g.montar([{"nome": "a", "qtd": 1}, {"nome": "b", "qtd": 2}],
         _cel_ruim, _aco)
check(chamadas == [("a", 0), ("b", 1)] and len(labels()) >= 3,
      "GradeTabela: célula com falha não derruba a linha seguinte (soft)")

# ================== 9. PainelLista =======================================
print("== PainelLista ==")
REG.clear()
dados = [{"nome": f"u{i}"} for i in range(25)]
pl = PainelLista([("Nome", "1fr")], lambda: dados,
                 filtrar=lambda d, t: t.lower() in d["nome"].lower(),
                 por_pagina=10)
cont = pl.montar(lambda d: ui.label(d["nome"]))
check(cont.classes_str == "w-full gap-2",
      "PainelLista: container coluna w-full gap-2")
buscas = [e for e in por_tipo("input") if e.kwargs.get("placeholder") ==
          "Buscar…"]
check(len(buscas) == 1 and
      "outlined dense clearable" in buscas[0].props_str,
      "PainelLista: campo_busca padrão (outlined dense clearable)")
conto = [l for l in labels() if "registro(s)" in (l.args[0] if l.args else "")]
check(conto and conto[0].args[0] == "25 registro(s) — página 1/3",
      "PainelLista: contagem 25 registros, página 1/3")
chev = [b for b in buttons() if b.kwargs.get("icon") == "chevron_left"]
chevd = [b for b in buttons() if b.kwargs.get("icon") == "chevron_right"]
check(chev and "disable" in chev[0].props_str and chevd and
      "disable" not in chevd[0].props_str,
      "PainelLista: chevrons com bordas desabilitadas")

_linhas1 = len([l for l in labels() if l.args[0].startswith("u")])
check(_linhas1 == 10, "PainelLista: 10 linhas da página 1")

pl._proxima()
conto2 = [l for l in labels() if "registro(s)" in (l.args[0] if l.args else "")]
check(conto2[-1].args[0] == "25 registro(s) — página 2/3",
      "PainelLista: próxima página re-renderiza (2/3)")

pl._ao_buscar(type("E", (), {"value": "u2"})())
conto3 = [l for l in labels() if "registro(s)" in (l.args[0] if l.args else "")]
check(conto3[-1].args[0] == "6 registro(s) — página 1/1",
      "PainelLista: filtro por busca (u2,u20-u24 = 6 resultados, 1 página)")

paginas_antes = len(por_tipo("grid"))
pl.atualizar()
check(len(por_tipo("grid")) > paginas_antes,
      "PainelLista.atualizar(): re-render (container.clear + rebuild)")
check(cont.clears >= 3,
      "PainelLista: corpo re-renderizado via clear (busca mantém foco)")

# ================== 10. FormularioBuilder ================================
print("== FormularioBuilder ==")
REG.clear()
fb = (FormularioBuilder()
      .campo_texto("nome", "Nome *", valor="Ana")
      .campo_senha("senha", "Senha *", valor="")
      .campo_selecao("perfil", "Perfil", ["comum", "admin"], valor="comum")
      .campo_numero("idade", "Idade", valor=30, minimo=0, maximo=120)
      .campo_data("dia", "Data", valor="2026-09-06"))
fb.build()
valores = fb.valores()
check(valores.get("nome") == "Ana" and valores.get("senha") == "" and
      valores.get("perfil") == "comum" and valores.get("idade") == 30 and
      valores.get("dia") == "2026-09-06",
      "FormularioBuilder.valores(): todos os campos por nome")
check(fb.elemento("inexistente") is None and fb.valor("inexistente") is None,
      "FormularioBuilder: campo inexistente → None")
tipos_ok = {el.tipo for _, el in fb._campos}
mask_dia = fb.elemento("dia")
check(mask_dia is not None and 'mask="date"' in mask_dia.props_str,
      "campo_data: máscara Quasar 'date' (AAAA-MM-DD)")
check("number" in tipos_ok,
      "campo_numero: ui.number montado (min/max/step)")

fb2 = FormularioBuilder()
fb2._especificacoes.append(
    ("quebra", lambda: (_ for _ in ()).throw(RuntimeError("x"))))
fb2.campo_texto("ok", "OK", valor="v")
fb2.build()
check("quebra" not in fb2.valores() and fb2.valores().get("ok") == "v",
      "FormularioBuilder: campo com falha ignorado (fail-soft, sem derrubar)")

# ================== resultado ============================================
print("")
print(f"RESULTADO: {_OK} OK, {_TOTAL - _OK} falha(s) de {_TOTAL} verificações")
if _TOTAL != _OK:
    sys.exit(1)
