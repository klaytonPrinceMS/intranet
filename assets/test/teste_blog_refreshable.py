"""Piloto @ui.refreshable no Blog — feed, carrossel, preview e despublicadas.

EN: Refreshable pilot — content renders into its own slot (no manual
    wrap.clear); public renderizar_postagens signature kept for Home.
PT: `montar` (carrossel), `_feed_blog`, `_prev` e `_lista_despublicadas`
    são `@ui.refreshable` (atualizam via `.refresh()`, sem `clear`
    manual); `renderizar_postagens(wrap, ...)` mantém a assinatura para a
    Home. Somente LEITURA (sem banco, sem servidor).

Execute: .venv/bin/python assets/test/teste_blog_refreshable.py
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


print("INICIANDO TESTES — piloto refreshable do Blog")

import mod_blog.telas as telas  # noqa: E402

# ---------- assinatura pública intacta (Home) ----------
params = list(inspect.signature(telas.renderizar_postagens).parameters)
check(params == ["wrap", "usuario_logado", "perfil", "pode_publicar",
                 "ao_atualizar", "ao_editar", "termo", "data_f",
                 "selecionados", "ao_toggle_selecao"],
      "renderizar_postagens mantém a assinatura (Home)")
check(hasattr(telas, "_renderizar_conteudo_blog"),
      "conteúdo extraído em _renderizar_conteudo_blog")

# ---------- carrossel sem clear manual ----------
fonte_car = inspect.getsource(telas._renderizar_carrossel)
check("@ui.refreshable" in fonte_car, "montar é @ui.refreshable")
check("montar.refresh()" in fonte_car, "ações/timer usam montar.refresh()")
check(fonte_car.count("        wrap.clear()") == 1
      and "Não foi possível exibir o carrossel" in fonte_car,
      "wrap.clear() só no fallback fail-soft do except")
check("_carrossel_timers" in fonte_car,
      "registro do timer único mantido (sem acúmulo)")

# ---------- feed da tela via refreshable ----------
fonte_tela = inspect.getsource(telas.mostrar_tela)
check("_feed_blog.refresh()" in fonte_tela, "atualizar usa _feed_blog.refresh()")
check("renderizar_postagens(\n                    posts_wrap" not in fonte_tela,
      "atualizar não chama mais renderizar_postagens direto")

# ---------- preview e despublicadas via refreshable ----------
check("_prev.refresh()" in fonte_tela, "atualizar_preview usa _prev.refresh()")
check("preview_wrap.clear()" not in fonte_tela, "sem preview_wrap.clear()")
fonte_des = inspect.getsource(telas._painel_despublicadas)
check("_lista_despublicadas.refresh()" in fonte_des,
      "republicar usa _lista_despublicadas.refresh()")
check("def carregar" not in fonte_des, "carregar() manual removido")

print(f"RESULTADO: {_OK} OK, {_TOTAL - _OK} falha(s) de {_TOTAL} verificações")
sys.exit(0 if _OK == _TOTAL else 1)
