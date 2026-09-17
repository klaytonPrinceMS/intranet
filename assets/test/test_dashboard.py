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


MAIN = ler("main.py")
ABAS = ler("mod_intranet/aba_modulo.py")
HV = ler("mod_intranet/home_visual.py")

MODULOS = {
    "mod_blog/telas.py": "blog_",
    "mod_gest_cad_usuario/telas.py": "usuarios_",
    "mod_auditoria/telas.py": "auditoria_",
    "mod_renomear_empenho/telas.py": "empenhos_",
    "mod_solicita_impressao/telas.py": "solicita_impressao_",
    "mod_edit_pdf/telas.py": "editar_pdf_",
}

print("INICIANDO TESTES — Dashboard mobile-first + padrão de exibição (Fase 1)")

# ---------- Dashboard ----------
# Produção atual (main.py:507-509): perfil extraído antes e `eh_admin = perfil
# in (...)` — semanticamente idêntico ao `user.get("perfil") in (...)` antigo.
check('eh_admin = perfil in ("administrador_geral", "administrador_modulo")' in MAIN
      and 'perfil = user.get("perfil"' in MAIN,
      "resumo restrito a admins (geral e de módulos)")
check("if eh_admin:" in MAIN, "resumo do sistema exibido somente para admins")
check("Resumo do sistema" in MAIN and "Publicações recentes" in MAIN
      and MAIN.index("Resumo do sistema") < MAIN.index("Publicações recentes"),
      "resumo fica acima das postagens do blog")
# Produção atual: wrap centralizado em home_visual.classes_wrap_resumo
# ("w-full justify-center gap-4 flex-wrap") usado via
# `ui.row().classes(_hv2.classes_wrap_resumo(modelo))` (main.py:415,433).
check("def classes_wrap_resumo" in HV
      and "w-full justify-center gap-4 flex-wrap" in HV
      and "classes_wrap_resumo" in MAIN,
      "cards do resumo lado a lado e centralizados (via classes_wrap_resumo)")
# Microinterações migradas para o CSS centralizado (home_visual.py):
# .home-stat-pic/.home-stat-water com `transition:` e
# `:hover{...transform:translateY(-2px)}` + sombra — mesmo efeito do
# Tailwind antigo (transition-transform/hover:-translate-y/hover:shadow-lg).
check("transition:" in HV,
      "microinteração transition nos cards de estatística (CSS centralizado)")
check("translateY(-2px)" in HV, "microinteração hover -translate-y (CSS centralizado)")
check(":hover" in HV and "box-shadow" in HV,
      "microinteração hover:shadow (CSS centralizado)")
check('notificar(f"Bem-vindo(a), {nome}!' in MAIN
      and "timeout=2" in MAIN,
      "feedback de 2s: toast de boas-vindas com timeout=2 (via notificar)")
# Produção atual (main.py:398-400): botão "Atualizar" manual REMOVIDO de
# propósito — dados calculados automaticamente a cada acesso; o feedback é
# só o toast auto (ui.timer(0.1, ..., timeout=2), once=True).
check('"Atualizado ✓" not in MAIN',
      "feedback de 2s: sem botão 'Atualizar' manual (dados automáticos)")
check("lbl_fb_resumo" not in MAIN and "ui.timer(0.1" in MAIN,
      "feedback de 2s: reversão manual removida (toast auto com timeout=2)")
# Dashboard deve ocupar a largura inteira (sem container max-w centralizador)
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
# Vale literal (`<prefixo>_<chave>`) OU padrão centralizado (ler_tema + bloco_aparencia,
# que compõe as chaves dinamicamente — ex.: mod_solicita_impressao via _tema()).
CHAVES = ["cor_botao", "cor_texto_botao", "cor_fundo",
          "cor_titulo", "btn_tamanho", "texto_header"]
ADM_POSSUI = {
    "mod_blog/telas_administracao.py": "blog_",
    "mod_gest_cad_usuario/telas_administracao.py": "usuarios_",
    "mod_auditoria/telas_administracao.py": "auditoria_",
    "mod_edit_pdf/telas_administracao.py": "editar_pdf_",
    "mod_renomear_empenho/telas_administracao.py": "empenhos_",
    "mod_solicita_impressao/telas_administracao.py": "solicita_impressao_",
}
for rel, prefixo in MODULOS.items():
    src = ler(rel)
    nome = rel.split("/")[0]
    faltam = [c for c in CHAVES if f"{prefixo}{c}" not in src]
    centralizado = (f'ler_tema("{prefixo.rstrip("_")}"' in src
                    and "bloco_aparencia" in src)
    adm_src = ""
    adm_rel = rel.replace("/telas.py", "/telas_administracao.py")
    if os.path.exists(os.path.join(RAIZ, adm_rel)):
        adm_src = ler(adm_rel)
    adm_tem_keys = adm_src and all(f"{prefixo}{c}" in adm_src for c in CHAVES)
    adm_bloco = adm_src and "bloco_aparencia" in adm_src
    check(not faltam or centralizado or adm_tem_keys or adm_bloco,
          f"{nome} tem as 6 chaves de aparência ({prefixo}*)"
          + (f" — faltam: {faltam}" if faltam and not centralizado and not adm_tem_keys and not adm_bloco else "")
          + (" (via telas_administracao.py + bloco_aparencia)" if adm_bloco else
             " (via telas_administracao.py)" if adm_tem_keys else
             " (via helpers centralizados)" if centralizado else ""))

# ---------- abas_modulo.cabecalho aceita cor_titulo/cor_fundo ----------
check("cor_titulo: str = None" in ABAS and 'ui_comum.CORES["titulo"]' in ABAS,
      "cabecalho aceita cor_titulo")
check("cor_fundo: str = None" in ABAS and "if cor_fundo:" in ABAS,
      "cabecalho aceita cor_fundo")

# ---------- Consistência: nenhum módulo com max-w antigo + w-full presente ----
for rel, _ in MODULOS.items():
    src = ler(rel)
    check("w-full" in src, f"{rel.split('/')[0]} usa w-full")

print(f"RESULTADO: {_OK} OK, {_TOTAL - _OK} falha(s) "
      f"de {_TOTAL} verificações")
sys.exit(0 if _OK == _TOTAL else 1)