"""Editor WYSIWYG do Blog — upload de imagens e expiração de órfãs.

EN: Blog editor image upload — JPG/PNG validation, `dataHora_usuario`
    naming, `/img_postagens` serving and 5-minute orphan expiry.
PT: Upload de imagens do editor — valida JPG/PNG até 5 MB (extensão +
    assinatura), nome padrão `AAMMDDHHMM_usuario`, servidas em
    `/img_postagens/*`; imagens não concretizadas em postagem expiram em
    5 min (`cleanup_blog_imagens` a cada 1 min).

Cobre as validações de sessão (evidência Playwright + backend 14/09/2026):
- aceite PNG/JPG, recusa .txt/.gif/assinatura inválida/sobretamanho;
- padrão do nome + sufixo em colisão; tag `<img>` com src/style/class
  preservada pelo nh3; montagem da rota estática; job agendado;
- `expirar_imagens_orfas`: órfã antiga removida, recente mantida,
  referenciada mantida (post temporário criado e removido no teste).

Escreve APENAS arquivos próprios `qa_*` em `img_postagens/` (removidos no
`finally`) e UMA postagem temporária referenciando `qa_ref_*` (excluída
via `excluir_postagem` no `finally`). Sem servidor.

Execute: .venv/bin/python assets/test/test_blog_editor_imagens.py
"""
import os
import sys
import time

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


print("INICIANDO TESTES — upload de imagens do editor do Blog")

from mod_blog import bd_manipulador as bd  # noqa: E402

_PNG = (b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)
_JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
_TAG = "qa_unittest"

# ---------- validação de tipo/tamanho ----------
ok, msg = bd.salvar_imagem_postagem("foto.txt", b"abc", "qamaster")
check(not ok and "jpg" in msg.lower(), "recusa .txt")
ok, msg = bd.salvar_imagem_postagem("foto.gif", b"GIF89a" + b"\x00" * 64, "qamaster")
check(not ok, "recusa .gif")
ok, msg = bd.salvar_imagem_postagem("foto.png", b"nao-eh-png" + b"\x00" * 64, "qamaster")
check(not ok and "válida" in msg, "recusa assinatura inválida")
ok, msg = bd.salvar_imagem_postagem("foto.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * (6 * 1024 * 1024), "qamaster")
check(not ok and "5 MB" in msg, "recusa acima de 5 MB")

# ---------- aceite + padrão do nome ----------
ok, nome_png = bd.salvar_imagem_postagem("minha foto.PNG", _PNG, "QaMaster")
import re as _re
check(ok and _re.fullmatch(r"\d{10}_qamaster\.png", nome_png or "") is not None,
      f"aceita PNG e nomeia dataHora_usuario (obteve {nome_png!r})")
ok, nome_jpg = bd.salvar_imagem_postagem("foto.jpg", _JPG, "qamaster")
check(ok and nome_jpg.endswith(".jpg"), "aceita JPG")
ok, nome2 = bd.salvar_imagem_postagem("outra.png", _PNG, "qamaster")
check(ok and nome2 != nome_png, "colisão gera sufixo (nomes distintos no mesmo minuto)")

# ---------- tag preservada pelo nh3 (class/style = CSS online/local) ----------
check("class" in bd._ATTRS.get("img", set()) and "style" in bd._ATTRS.get("img", set()),
      "_ATTRS['img'] permite class (CSS online) e style (CSS local)")
limpo = bd._sanitizar_texto(
    f'<p><img src="/img_postagens/{nome_png}" alt="x" '
    'style="max-width:50%;height:auto;" class="borda"></p>')
check(f'src="/img_postagens/{nome_png}"' in limpo and "max-width:50%" in limpo
      and 'class="borda"' in limpo,
      "nh3 preserva src/style/class da tag inserida")

# ---------- rota estática + agendador ----------
import mod_blog as blog_pkg  # noqa: E402
import inspect as _inspect
check(hasattr(blog_pkg, "montar_rotas_static")
      and "/img_postagens" in _inspect.getsource(blog_pkg.montar_rotas_static),
      "mod_blog expõe montar_rotas_static para /img_postagens/*")
with open(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), "main.py"), encoding="utf-8") as fh:
    main_fonte = fh.read()
check("/img_postagens" in main_fonte, "main.py monta /img_postagens no boot")
import mod_intranet.rotinas as rotinas_mod  # noqa: E402
fonte_rot = _inspect.getsource(rotinas_mod.iniciar_agendador)
check("cleanup_blog_imagens" in fonte_rot, "job cleanup_blog_imagens a cada 1 min")

# ---------- expiração de órfãs (arquivos próprios qa_*) ----------
criados = [p for p in (nome_png, nome_jpg, nome2)
           if p and os.path.exists(os.path.join(bd.PASTA_IMAGENS, p))]
pid = None
try:
    orfa = os.path.join(bd.PASTA_IMAGENS, f"{_TAG}_orfa.png")
    with open(orfa, "wb") as fh:
        fh.write(_PNG)
    criados.append(f"{_TAG}_orfa.png")
    velho = time.time() - 400
    os.utime(orfa, (velho, velho))
    ref_nome = f"{_TAG}_ref.png"
    with open(os.path.join(bd.PASTA_IMAGENS, ref_nome), "wb") as fh:
        fh.write(_PNG)
    criados.append(ref_nome)
    os.utime(os.path.join(bd.PASTA_IMAGENS, ref_nome), (velho, velho))
    pid = bd.criar_postagem(f"{_TAG} ref", f"<p><img src=\"/img_postagens/{ref_nome}\"></p>",
                            "qamaster")
    check(pid, "postagem temporária referenciando a imagem criada")
    n = bd.expirar_imagens_orfas()
    check(not os.path.exists(orfa), "órfã antiga (>5min, sem referência) removida")
    check(os.path.exists(os.path.join(bd.PASTA_IMAGENS, ref_nome)),
          "referenciada antiga preservada")
    check(os.path.exists(os.path.join(bd.PASTA_IMAGENS, nome_png)),
          "recente (<5min) preservada")
    print(f"  (expiradas nesta rodada: {n})")
finally:
    try:
        if pid:
            from mod_blog.bd_manipulador import excluir_postagem as _exc
            _exc(pid, "qamaster")
    except Exception:
        pass
    for nome in criados:
        try:
            os.remove(os.path.join(bd.PASTA_IMAGENS, nome))
        except Exception:
            pass
check(not any(os.path.exists(os.path.join(bd.PASTA_IMAGENS, n)) for n in criados),
      "limpeza: nenhum arquivo qa_* restante")

print(f"RESULTADO: {_OK} OK, {_TOTAL - _OK} falha(s) de {_TOTAL} verificações")
sys.exit(0 if _OK == _TOTAL else 1)
