"""Teste do Dashboard mobile-first (Fase 1, item 6) + padrão de exibição.

Script standalone (NÃO pytest). Verifica estaticamente no fonte de `main.py`
o grid fluido 360–1440px, as microinterações e o feedback de 2s; e confere que
os módulos seguem o padrão do "módulo exemplo" (Editor de PDF): área cheia
(`w-full`, sem `max-w-*` centralizador) e as 6 chaves de aparência padronizadas
no cupê Administração.

Execute: .venv/bin/python test/test_dashboard.py
"""
import os
import sys
import re

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

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


MAIN = ler("main.py")
ABAS = ler("mod_intranet/aba_modulo.py")

MODULOS = {
    "mod_blog/telas.py": "blog_",
    "mod_gest_cad_usuario/telas.py": "usuarios_",
    "mod_auditoria/telas.py": "auditoria_",
    "mod_renomear_empenho/telas.py": "empenhos_",
    "mod_solicita_impressao/telas.py": "solicita_impressao_",
    "mod_edit_pdf/telas.py": "editpdf_",
}

print("INICIANDO TESTES — Dashboard mobile-first + padrão de exibição (Fase 1)")

# ---------- Dashboard (item 6) ----------
check("ui.grid(columns=3)" in MAIN, "dashboard usa ui.grid de 3 colunas")
check("max-lg:grid-cols-2" in MAIN, "2 colunas em telas médias (max-lg)")
check("max-sm:grid-cols-1" in MAIN, "1 coluna mobile-first (max-sm)")
check("transition-transform" in MAIN,
      "microinteração transition-transform nos cards de estatística")
check("hover:-translate-y-0.5" in MAIN, "microinteração hover -translate-y")
check("hover:shadow-lg" in MAIN, "microinteração hover:shadow-lg")
check('ui.notify(f"Bem-vindo(a), {nome}!' in MAIN
      and "timeout=2" in MAIN,
      "feedback de 2s: toast de boas-vindas com timeout=2")
check('"Atualizado ✓"' in MAIN, "feedback de 2s: rótulo 'Atualizado ✓'")
check('ui.timer(2.0, lambda: lbl_fb_resumo.set_text(""), once=True)' in MAIN,
      "feedback de 2s: reversão via ui.timer(2.0, once=True)")
# Grid 360–1440px deve cobrir o intervalo com quebras responsivas (sem max-w fixo)
check("max-w-6xl mx-auto" not in MAIN.split("# ================== DASHBOARD")[1]
      [:2000], "dashboard sem container max-w centralizador")

# ---------- Padrão de exibição: área cheia sem max-w centralizador ----------
for rel, prefixo in MODULOS.items():
    src = ler(rel)
    nome = rel.split("/")[0]
    has_maxw = re.search(r'max-w-\d+xl mx-auto', src)
    check(not has_maxw,
          f"{nome} ocupa a área cheia (sem max-w-* mx-auto centralizador)")

# ---------- Padrão de exibição: 6 chaves de aparência em cada módulo ----------
CHAVES = ["cor_botao", "cor_texto_botao", "cor_fundo",
          "cor_titulo", "btn_tamanho", "texto_header"]
for rel, prefixo in MODULOS.items():
    src = ler(rel)
    nome = rel.split("/")[0]
    faltam = [c for c in CHAVES if f"{prefixo}{c}" not in src]
    check(not faltam,
          f"{nome} tem as 6 chaves de aparência ({prefixo}*)"
          + (f" — faltam: {faltam}" if faltam else ""))

# ---------- abas_modulo.cabecalho aceita cor_titulo/cor_fundo ----------
check("cor_titulo: str = \"#212121\"" in ABAS, "cabecalho aceita cor_titulo")
check("cor_fundo: str = \"\"" in ABAS, "cabecalho aceita cor_fundo")

# ---------- Consistência: nenhum módulo com max-w antigo + w-full presente ----
for rel, _ in MODULOS.items():
    src = ler(rel)
    check("w-full" in src, f"{rel.split('/')[0]} usa w-full")

print(f"RESULTADO: {_OK} OK, {_TOTAL - _OK} falha(s) "
      f"de {_TOTAL} verificações")
sys.exit(0 if _OK == _TOTAL else 1)