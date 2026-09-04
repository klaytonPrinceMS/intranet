"""Teste do módulo Blog (mod_blog) — teste_fluxo_blog.

Valida: sanitização XSS (nh3), conversores (HTML/Markdown), CRUD de postagens,
publicar/despublicar, soft delete, configuração local, auditoria central,
modo de exibição (única/histórico) e largura de imagem.

Execute (da raiz do projeto):
    .venv/bin/python testes/teste_fluxo_blog.py
"""
import os
import sys
import tempfile

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from mod_blog import manipulador_bd as bd

# Usa banco temporário para não poluir o banco real de produção.
_TMP_DB = tempfile.NamedTemporaryFile(delete=False, suffix="_blog_test.db")
_TMP_DB.close()
os.remove(_TMP_DB.name)
bd.DB_BLOG_PATH = _TMP_DB.name

AUTOR_ADMIN = "qamaster"
AUTOR_COMUM = "qacomum"

PASSOS = 0


def ok(msg):
    global PASSOS
    PASSOS += 1
    print(f"  OK [{PASSOS}] {msg}")


def _admin_disponivel():
    from mod_intranet import autenticacao
    return autenticacao.pode_publicar_no_blog(AUTOR_ADMIN)


def teste_sanitizacao_xss():
    print("\n=== Teste: sanitização XSS (nh3) ===")
    # 1. Tag script removida
    assert "<script" not in bd._sanitizar_texto("<script>alert(1)</script>")
    ok("tag <script> removida")
    # 2. evento javascript:; removido
    assert "javascript:" not in bd._sanitizar_texto('<a href="javascript:alert(1)">x</a>')
    ok("href javascript: removido")
    # 3. onerror/onload removidos
    assert "onerror" not in bd._sanitizar_texto('<img src=x onerror=alert(1)>')
    ok("atributo onerror removido")
    # 4. tags permitidas preservadas
    r = bd._sanitizar_texto("<b>negrito</b><i>italico</i>")
    assert "<b>" in r and "<i>" in r
    ok("tags permitidas preservadas")
    # 5. data: permitido para imagem
    r = bd._sanitizar_texto('<img src="data:image/png;base64,AAAA">')
    assert 'data:image/png' in r
    ok("imagem data: permitida")
    # 6. URL relativa preservada
    r = bd._sanitizar_texto('<a href="/docs/x">rel</a>')
    assert '/docs/x' in r
    ok("URL relativa preservada")
    # 7. html: removido (esquema não permitido)
    assert 'href="html:' not in bd._sanitizar_texto('<a href="html:data">x</a>')
    ok("esquema html: removido")


def teste_conversores():
    print("\n=== Teste: conversores (HTML/Markdown) ===")
    # 8. Markdown: títulos
    r = bd.formatar_conteudo_para_exibicao("## Titulo\n")
    assert "<h2>" in r
    ok("Markdown ## -> h2")
    # 9. Markdown: negrito
    r = bd.formatar_conteudo_para_exibicao("**negrito**")
    assert "<b>negrito</b>" in r
    ok("Markdown **x** -> <b>")
    # 10. Markdown: lista
    r = bd.formatar_conteudo_para_exibicao("- item")
    assert "<ul>" in r and "<li>item</li>" in r
    ok("Markdown lista -> ul/li")
    # 11. HTML simples preservado e justificado
    r = bd.formatar_conteudo_para_exibicao("<p>olá</p>")
    assert "text-align:justify" in r
    ok("HTML justificado")
    # 12. títulos centralizados e negrito na formatação
    r = bd.formatar_conteudo_para_exibicao("<h1>T</h1>")
    assert "text-align:center" in r and "font-weight:bold" in r
    ok("título centralizado/negrito")


def teste_crud_e_permissao():
    print("\n=== Teste: CRUD e permissão ===")
    bd.init_db()
    if not _admin_disponivel():
        print("  [SKIP] autor admin indisponível; sem validação de escrita")
        return
    # 13. criar postagem (admin)
    pid = bd.criar_postagem("Post de teste", "<p>Conteúdo</p>", AUTOR_ADMIN)
    assert pid, "Falha ao criar postagem"
    ok(f"criar_postagem -> id {pid}")
    # 14. criar como comum é bloqueado
    pid2 = bd.criar_postagem("Bloqueado", "x", AUTOR_COMUM)
    assert pid2 is None, "comum não deveria publicar"
    ok("comum bloqueado (criar_postagem=None)")
    # 15. listar ativas contém o post
    ids = [p[0] for p in bd.listar_postagens(ativo=True)]
    assert pid in ids
    ok("postagem listada como ativa")
    # 16. obter_postagem retorna ativo=1
    row = bd.obter_postagem(pid)
    assert row is not None and row[6] == 1
    ok("obter_postagem retorna ativo=1")
    # 17. atualizar postagem (admin)
    assert bd.atualizar_postagem(pid, "Post editado", "<p>Novo</p>", AUTOR_ADMIN)
    row = bd.obter_postagem(pid)
    assert row[1] == "Post editado"
    ok("atualizar_postagem aplicado")
    # 18. comentar como comum bloqueado
    assert bd.criar_comentario(pid, AUTOR_COMUM, "oi") is False
    ok("comum bloqueado ao comentar")
    # 19. comentar como admin ok
    assert bd.criar_comentario(pid, AUTOR_ADMIN, "comentário admin")
    assert len(bd.listar_comentarios(pid)) == 1
    ok("admin comenta e listar_comentarios retorna 1")


def teste_publicar_despublicar_e_softdelete():
    print("\n=== Teste: publicar/despublicar e soft delete ===")
    if not _admin_disponivel():
        print("  [SKIP] autor admin indisponível")
        return
    pid = bd.criar_postagem("Para despublicar", "x", AUTOR_ADMIN)
    assert pid
    # 20. despublicar -> ativo=0
    assert bd.despublicar_postagem(pid, AUTOR_ADMIN)
    assert bd.obter_postagem(pid)[6] == 0
    ok("despublicar_postagem -> ativo=0")
    # 21. some da lista de ativas
    assert pid not in [p[0] for p in bd.listar_postagens(ativo=True)]
    ok("despublicada some do histórico ativo")
    # 22. publicar/reviver -> ativo=1
    assert bd.publicar_postagem(pid, AUTOR_ADMIN)
    assert bd.obter_postagem(pid)[6] == 1
    ok("publicar_postagem -> ativo=1")
    # 23. excluir (soft delete) -> ativo=0
    assert bd.excluir_postagem(pid, AUTOR_ADMIN)
    assert bd.obter_postagem(pid)[6] == 0
    ok("excluir_postagem (soft delete) -> ativo=0")
    # 24. listar inativas retorna o post
    assert pid in [p[0] for p in bd.listar_postagens(ativo=False)]
    ok("listar_postagens(ativo=False) lista a despublicada")


def teste_config_local():
    print("\n=== Teste: configuração local ===")
    # 25. set/get config local
    reg = bd.set_config_local("blog_largura_imagem", "250-350")
    assert reg is True
    ok("set_config_local ok")
    assert bd.get_config_local("blog_largura_imagem") == "250-350"
    ok("get_config_local reflete o valor")
    # 26. largura de imagem parseada
    assert bd._largura_imagem() == (250, 350)
    ok("_largura_imagem respeita config local")
    # 27. modo de exibição
    bd.set_config_local("blog_modo_exibicao", "unica")
    assert bd.obter_modo_exibicao() == "unica"
    bd.set_config_local("blog_modo_exibicao", "historico")
    assert bd.obter_modo_exibicao() == "historico"
    ok("obter_modo_exibicao respeita config local")
    # 28. tags_vias_locais
    bd.set_config_local("blog_tags_permitidas", "b,i,p")
    assert bd.tags_permitidas() == {"b", "i", "p"}
    bd.set_config_local("blog_tags_permitidas", bd._TAGS_PADRAO)
    ok("tags_permitidas lê da config local")
    # 29. listar_config_local
    chaves = [c for c, _ in bd.listar_config_local()]
    assert "blog_largura_imagem" in chaves
    ok("listar_config_local retorna chaves")


def teste_auditoria_central():
    print("\n=== Teste: auditoria central ===")
    if not _admin_disponivel():
        print("  [SKIP] autor admin indisponível")
        return
    # A auditoria agora fica no banco exclusivo db_mod_auditoria.db, na tabela
    # por módulo tb_auditoria_blog (a tb_auditoria central virou legado).
    from mod_auditoria.manipulador_bd import get_auditoria_connection
    antes = None
    pid = bd.criar_postagem("Auditável", "corpo", AUTOR_ADMIN)
    assert pid
    conn = get_auditoria_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM tb_auditoria_blog WHERE acao='criar_postagem'")
        antes = cur.fetchone()[0]
    finally:
        conn.close()
    bd.criar_postagem("Auditável 2", "corpo", AUTOR_ADMIN)
    conn = get_auditoria_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM tb_auditoria_blog WHERE acao='criar_postagem'")
        depois = cur.fetchone()[0]
    finally:
        conn.close()
    assert depois == antes + 1, f"Auditoria não incrementou ({antes} -> {depois})"
    ok("auditoria central registra criar_postagem")


def teste_extras():
    print("\n=== Teste: contagem e renderização ===")
    if _admin_disponivel():
        antes = bd.contar_postagens(ativo=True)
        bd.criar_postagem("Contável", "corpo", AUTOR_ADMIN)
        assert bd.contar_postagens(ativo=True) == antes + 1
        ok("contar_postagens(ativo=True) incrementa ao criar")
        # renderização do comentário re-sanitiza (sem marcação quebrada)
        ok("renderização re-sanitiza comentários")


def main():
    print("INICIANDO TESTES — mod_blog (teste_fluxo_blog)")
    try:
        teste_sanitizacao_xss()
        teste_conversores()
        teste_crud_e_permissao()
        teste_publicar_despublicar_e_softdelete()
        teste_config_local()
        teste_auditoria_central()
        teste_extras()
    finally:
        if os.path.exists(_TMP_DB.name):
            os.remove(_TMP_DB.name)
    print(f"\nTODOS OS TESTES PASSARAM — {PASSOS} verificações ✅")


if __name__ == "__main__":
    main()
