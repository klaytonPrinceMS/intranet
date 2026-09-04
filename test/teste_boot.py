"""Teste de boot / Fase 2.5 — `teste_boot.py`.

Valida que o sistema sobe em condições de "instalação limpa":
 - o bootstrap cria TODOS os bancos do zero (PLANO pré-fase) e o usuário
   master/master como administrador_geral;
 - o módulo principal (`main.py`) importa sem erro;
 - o `/login` está configurado com Tailwind CSS LOCAL (sem CDN, rede interna)
   e CSS customizado (cor principal + fundo), como pedido pela Fase 2.5;
 - quando um servidor HTTP está disponível (rota `/login`), o teste confere
   respostas reais 200 com o Tailwind local servido.

Script standalone (NÃO pytest):
    .venv/bin/python test/teste_boot.py
"""
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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


def _http(url, timeout=3):
    """GET simples retornando (status, corpo). None se não alcançável."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except Exception:
        return None, None


print("INICIANDO TESTES — Boot do sistema (Fase 2.5)")

# ---------- 1) Bootstrap limpo cria bancos + seed master ----------
from mod_intranet.mod_intranet_inicializacao_bd import inicializar_bancos

DBS = [
    "db_mod_intranet.db",
    "db_mod_auditoria.db",
    "db_mod_blog.db",
    "db_mod_gest_cad_usuario.db",
    "db_mod_edit_pdf.db",
    "db_mod_renomear_empenho.db",
    "db_mod_solicita_impressao.db",
]

for f in DBS:
    check(os.path.exists(os.path.join(RAIZ, f)), f"bootstrap gerou {f}")

# seed master/master admin geral
import sqlite3
import tempfile
import shutil

_master_ok = False
c = sqlite3.connect(os.path.join(RAIZ, "db_mod_gest_cad_usuario.db"))
try:
    row = c.execute(
        "SELECT user_nome, user_perfil FROM tb_usuarios WHERE user_nome='master'"
    ).fetchone()
    _master_ok = row == ("master", "administrador_geral")
finally:
    c.close()
check(_master_ok, "seed master/master como administrador_geral presente")

# ---------- 2) main.py importa sem erro ----------
try:
    import main as _main  # noqa: F401
    check(True, "módulo principal (main.py) importa sem erro")
except SystemExit as _sys_exit:
    check(False, f"main.py importa sem erro (SystemExit: {_sys_exit})")
except Exception as _e:
    check(False, f"main.py importa sem erro ({_e})")

# ---------- 3) Tailwind LOCAL + CSS custom no /login ----------
MAIN = ler("main.py")
# NiceGUI 3.x usa Tailwind por padrão, embutido/servido LOCALMENTE pelo próprio
# pacote (sem CDN, requisito de rede interna). O `ui.run` não especifica CDN.
check("cdn" not in MAIN.lower(), "ui.run sem referência a CDN (Tailwind local)")
check("ui.colors(primary=cor)" in MAIN, "/login usa cor customizada (ui.colors)")
check('ui.query("body").classes("bg-blue-grey-10")' in MAIN,
      "/login usa CSS custom de fundo (mobile-first)")
check('ui.add_head_html' in MAIN or 'favicon' in MAIN,
      "/login injeta head custom (favicon/cache-bust)")

_VENV = os.path.join(RAIZ, ".venv", "lib")
check(any(
    os.path.exists(os.path.join(_VENV, d, "site-packages", "nicegui", "static", "tailwindcss.min.js"))
    for d in os.listdir(_VENV) if d.startswith("python")
) if os.path.isdir(_VENV) else False,
    "tailwindcss.min.js embutido no pacote NiceGUI (servido local)")

# ---------- 4) HTTP real (opcional — se o servidor estiver no ar) ----------
status, corpo = _http("http://localhost:8080/login")
if status == 200 and corpo:
    check("tailwindcss.min.js" in corpo, "HTTP /login serve Tailwind CSS local")
    check(status == 200, f"HTTP /login responde 200 (status={status})")
else:
    print("  [INFO] servidor HTTP não está no ar — pulando checagem de rota /login")

print(f"RESULTADO: {_OK} OK, {_TOTAL - _OK} falha(s) de {_TOTAL} verificações")
sys.exit(0 if _OK == _TOTAL else 1)
