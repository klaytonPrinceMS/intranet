"""Flags finas de permissão (JSON) — catálogo, grant, bypass e decorador.

EN: Fine-grained permission flags — allowlist validation, grant/revoke
    roundtrip on a real grant, admin bypass by role, fail-closed decorator.
PT: `FLAGS_PERMISSAO`/`definir_flags`/`obter_flags`/`tem_flag`
    (mod_gest_cad_usuario) + `@requer_flag` (decoradores): valida allowlist,
    roundtrip no vínculo real `qacomum@blog` (restaurado no `finally`),
    admin passa pelo papel, decorador nega/permite. Cria/duplica/exclui
    APENAS `qa_flag_tmp` (removido no `finally`). Sem servidor.

Execute: .venv/bin/python assets/test/teste_flags_permissao.py
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


print("INICIANDO TESTES — flags finas de permissão")

from mod_gest_cad_usuario import bd_manipulador as gest  # noqa: E402
from mod_intranet.decoradores import requer_flag  # noqa: E402

_ALVO = ("qacomum", "blog")
_TMP = "qa_flag_tmp"

# ---------- migração: coluna flags ----------
conn = gest.get_connection()
try:
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(tb_acesso_usuario)")
    cols = {r[1] for r in cur.fetchall()}
finally:
    conn.close()
check("flags" in cols, "migração: coluna flags existe em tb_acesso_usuario")
check(set(gest.FLAGS_PERMISSAO) >= {"blog.publicar", "blog.comentar",
                                    "blog.configurar"},
      "catálogo base presente")

# ---------- baseline: comum sem grant nega ----------
check(gest.obter_flags(*_ALVO) == {} or isinstance(gest.obter_flags(*_ALVO), dict),
      "baseline: obter_flags devolve dict")
check(gest.tem_flag(*_ALVO, "blog.comentar") is False,
      "baseline: comum sem grant nega")


@requer_flag("blog.comentar", arg_usuario="autor")
def _dummy(autor):
    return "ok"


check(_dummy("qacomum") is False, "decorador nega comum sem grant")
check(_dummy("qamaster") == "ok", "decorador permite admin pelo papel")

# ---------- validações de escrita ----------
ok, _msg = gest.definir_flags("master", *_ALVO, {"blog.inexistente": True})
check(ok is False, "flag fora do catálogo rejeitada")
ok, _msg = gest.definir_flags("master", *_ALVO, ["blog.comentar"])
check(ok is False, "flags não-dict rejeitadas")
ok, _msg = gest.definir_flags("master", "qa_sem_vinculo", "blog",
                              {"blog.comentar": True})
check(ok is False, "grant sem vínculo rejeitado")

# ---------- roundtrip com restauração ----------
original = gest.obter_flags(*_ALVO)
try:
    ok, _msg = gest.definir_flags("master", *_ALVO, {"blog.comentar": True})
    check(ok is True, "grant aplicado")
    check(gest.tem_flag(*_ALVO, "blog.comentar") is True,
          "comum com grant permite")
    check(_dummy("qacomum") == "ok", "decorador permite comum com grant")
    ok, _msg = gest.definir_flags("master", *_ALVO, {})
    check(ok is True and gest.tem_flag(*_ALVO, "blog.comentar") is False,
          "revogar ({} vazio) volta a negar")
finally:
    gest.definir_flags("master", *_ALVO, original)
check(gest.obter_flags(*_ALVO) == original, "flags originais restauradas")

# ---------- JSON malformado = {} ----------
conn = gest.get_connection()
try:
    cur = conn.cursor()
    cur.execute("UPDATE tb_acesso_usuario SET flags=? WHERE user_nome=? AND modulo_chave=?",
                ("[invalido",) + _ALVO)
    conn.commit()
    check(gest.obter_flags(*_ALVO) == {}, "JSON malformado devolve {}")
    check(gest.tem_flag(*_ALVO, "blog.comentar") is False,
          "JSON malformado nega (fail-closed)")
finally:
    cur.execute("UPDATE tb_acesso_usuario SET flags=? WHERE user_nome=? AND modulo_chave=?",
                ("{}",) + _ALVO)
    conn.commit()
    conn.close()
gest.definir_flags("master", *_ALVO, original)

# ---------- duplicar replica flags ----------
try:
    ok, _msg = gest.duplicar_usuario("master", "qacomum", _TMP, "12345678",
                                     nome_completo="Temporario Flags")
    check(ok is True, "duplicar usuário temporário")
    if ok:
        check(gest.obter_flags(_TMP, "blog") == gest.obter_flags(*_ALVO),
              "duplicar replica as flags da origem")
finally:
    gest.excluir_usuario_definitivo("master", _TMP)
check(gest.obter_flags(_TMP, "blog") == {}, "limpeza: temporário removido")

print(f"RESULTADO: {_OK} OK, {_TOTAL - _OK} falha(s) de {_TOTAL} verificações")
sys.exit(0 if _OK == _TOTAL else 1)
