"""Teste unitário do helper de tema (mod_intranet/tema_modulo.py) — delta a1b1650.

Cobre o que test_tema.py (só leitura) não cobre: cache lru_cache em
`_cfg`/`ler_tema` com invalidação em `salvar_tema`, roundtrip
salvar/restaurar, clamp de `notificacao_timeout`, `notificar` (timeout
configurado, type explícito, fail-soft), `paleta_escura`, `ler_cartao` e a
trava de reentrância `ocupado` do bloco de aparência (guarda de regressão
via fonte).

AUTOCONTIDO: opera nas chaves blog_* do tb_config com snapshot/restore;
`ui.notify` é observado via monkeypatch (sem tela).

Execute: .venv/bin/python assets/test/test_tema_cache_trava.py
"""
import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from mod_intranet.bd_conexao import get_config, set_config, init_db  # noqa: E402
from mod_intranet import tema_modulo as tema  # noqa: E402

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


print("INICIANDO TESTES — tema_modulo (cache, trava, notificar)")
init_db()

CHAVES = ["blog_cor_botao", "blog_cor_texto_botao", "blog_cor_fundo",
          "blog_cor_titulo", "blog_btn_tamanho", "blog_texto_header",
          "blog_cor_fundo_card", "blog_cor_texto_card",
          "notificacao_timeout"]
ORIG = {k: get_config(k, None) for k in CHAVES}

try:
    # ---------- lru_cache (NOVO a1b1650) ----------
    print("-- cache --")
    check(hasattr(tema._cfg, "cache_clear"),
          "_cfg usa lru_cache (leitura sem bater no banco a cada render)")
    check(hasattr(tema.ler_tema, "cache_clear"),
          "ler_tema usa lru_cache")

    # ---------- roundtrip salvar -> ler (invalidação de cache) ----------
    print("-- salvar/restaurar --")
    tema.salvar_tema("blog", {"cor_botao": "#112233",
                              "cor_texto_botao": "#FFFFFF",
                              "btn_tamanho": "large"})
    lido = tema.ler_tema("blog")
    check(lido["cor_botao"] == "#112233",
          "salvar_tema grava e ler_tema reflete (cache invalidado)")
    check(lido["btn_tamanho"] == "large",
          "btn_tamanho persistido via salvar_tema")
    check(get_config("blog_cor_botao", "") == "#112233",
          "chave tb_config blog_cor_botao gravada")
    # salvamento parcial não apaga as demais chaves
    tema.salvar_tema("blog", {"cor_botao": "#445566"})
    check(get_config("blog_cor_texto_botao", "") == "#FFFFFF",
          "salvar parcial preserva as demais chaves do módulo")
    check(tema.ler_tema("blog")["cor_botao"] == "#445566",
          "segunda gravação reflete sem resíduo de cache")
    # valor vazio volta ao padrão do módulo (PADROES_TEMA, não herda intranet)
    tema.salvar_tema("blog", {"cor_botao": ""})
    check(tema.ler_tema("blog")["cor_botao"]
          == tema.PADROES_TEMA["blog"]["cor_botao"],
          "chave vazia usa o padrão do próprio módulo")
    tema.restaurar_tema("blog", {"cor_botao": "#AABBCC",
                                 "cor_texto_botao": "#000000",
                                 "cor_fundo": "", "cor_titulo": "",
                                 "btn_tamanho": "", "texto_header": "QA"})
    check(get_config("blog_cor_botao", "") == "#AABBCC"
          and get_config("blog_texto_header", "") == "QA",
          "restaurar_tema grava os defaults via salvar_tema")

    # ---------- notificacao_timeout (clamp 1..30, default 10) ----------
    print("-- notificacao_timeout --")
    set_config("notificacao_timeout", "7")
    tema._cfg.cache_clear()
    check(tema.notificacao_timeout() == 7,
          "timeout 7 respeitado")
    set_config("notificacao_timeout", "99")
    tema._cfg.cache_clear()
    check(tema.notificacao_timeout() == 30,
          "timeout 99 limitado a 30")
    set_config("notificacao_timeout", "0")
    tema._cfg.cache_clear()
    check(tema.notificacao_timeout() == 1,
          "timeout 0 elevado a 1")
    set_config("notificacao_timeout", "lixo")
    tema._cfg.cache_clear()
    check(tema.notificacao_timeout() == 10,
          "timeout inválido cai no padrão 10")

    # ---------- notificar (timeout configurado + fail-soft) ----------
    print("-- notificar --")
    from nicegui import ui as _ui
    chamadas = []
    _notify_orig = _ui.notify
    _ui.notify = lambda *a, **k: chamadas.append((a, k))
    try:
        set_config("notificacao_timeout", "7")
        tema._cfg.cache_clear()
        tema.notificar("Olá QA")
        check(chamadas and chamadas[-1][1].get("timeout") == 7,
              "notificar injeta timeout configurado")
        tema.notificar("Alerta", type="negative")
        check(chamadas[-1][1].get("type") == "negative",
              "notificar aceita type= explícito")
        tema.notificar("Com timeout próprio", timeout=3)
        check(chamadas[-1][1].get("timeout") == 3,
              "timeout explícito tem prioridade sobre o configurado")

        def _quebrar(*a, **k):
            raise RuntimeError("sem cliente (simulado)")

        _ui.notify = _quebrar
        try:
            tema.notificar("não pode quebrar a tela")
            check(True, "notificar com ui.notify quebrado não levanta exceção")
        except Exception:
            check(False, "notificar com ui.notify quebrado não levanta exceção")
    finally:
        _ui.notify = _notify_orig

    # ---------- puras ----------
    print("-- funções puras --")
    check(tema.btn_cls("small") == "min-w-[140px] text-sm"
          and tema.btn_cls("large") == "min-w-[220px] text-lg",
          "btn_cls por tamanho")
    st = tema.btn_style("#123456", "#FFFFFF")
    check("#123456" in st and "#FFFFFF" in st,
          "btn_style embute cor de fundo e texto")
    check(tema.prefixo_da_chave("editar_pdf") == "editpdf"
          and tema.prefixo_da_chave("mod_desconhecido") == "mod_desconhecido",
          "prefixo_da_chave (mapeado e fallback)")
    esc = tema.paleta_escura({"cor_botao": "#000000"})
    cla = tema.paleta_escura({"cor_botao": "#FFFFFF"})
    check(isinstance(esc, dict) and len(esc) == 6
          and esc["fundo_pagina"] != cla["fundo_pagina"],
          "paleta_escura varia conforme a luminância da cor geral")
    check(tema._hex_para_rgb("#FFFFFF") == (255, 255, 255),
          "_hex_para_rgb converte")
    cartao = tema.ler_cartao("blog")
    check(set(("cor_fundo_card", "cor_texto_card")) <= set(cartao),
          "ler_cartao devolve as chaves de card")

    # ---------- trava de reentrância (guarda de regressão a1b1650) ----------
    print("-- trava ocupado (regressão) --")
    fonte = inspect.getsource(tema.bloco_aparencia)
    check("ocupado" in fonte,
          "bloco_aparencia mantém a trava de reentrância (ocupado)")
finally:
    for k, v in ORIG.items():
        try:
            if v is None:
                from mod_intranet.bd_conexao import get_connection
                conn = get_connection()
                try:
                    conn.execute("DELETE FROM tb_config WHERE chave=?", (k,))
                    conn.commit()
                finally:
                    conn.close()
            else:
                set_config(k, v)
        except Exception:
            pass
    try:
        tema._cfg.cache_clear()
        tema.ler_tema.cache_clear()
    except Exception:
        pass

print(f"RESULTADO: {_OK} OK, {_TOTAL - _OK} falha(s) de {_TOTAL} verificações")
sys.exit(0 if _OK == _TOTAL else 1)
