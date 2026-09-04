import sys
import os
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from nicegui import ui, app
from fastapi.responses import FileResponse, Response, RedirectResponse

from mod_intranet.conexao_bd import (
    get_config
)
from mod_intranet import autenticacao

# ================== INICIALIZAÇÃO DOS BANCOS ==================
from mod_intranet.mod_intranet_inicializacao_bd import inicializar_bancos
inicializar_bancos()

# Garantir __pycache__ limpo de telas inexistentes
from pathlib import Path

for modulo in ["mod_gest_cad_usuario", "mod_auditoria", "mod_edit_pdf", "mod_renomear_empenho", "mod_blog"]:
    if not (Path(__file__).parent / modulo / "telas.py").exists():
        raise RuntimeError(f"FALTA telas.py em {modulo}")


# ================== AGENDADOR (backup por módulo / cleanup PDF 10min) ==================
def iniciar_agendador():
    """Delega ao rotinas: um job de backup POR módulo (intervalo individual
    configurável em /configuracoes, aplicável sem restart) + limpeza do editorPDF."""
    from mod_intranet import rotinas
    return rotinas.iniciar_agendador()


# ================== FAVICON CUSTOMIZADO (upload em /configuracoes) ==================
# ui.run aponta para um ARQUIVO VIVO: o NiceGUI registra /favicon.ico servindo-o
# a cada request. O upload sobrescreve o conteúdo -> troca vale no próximo F5,
# sem reiniciar o servidor. Sem customização, ele contém o ícone nativo.
import nicegui as _nicegui_pkg
import shutil

FAVICON_ATUAL = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "assets", "favicon_atual.ico")
FAVICON_PADRAO = os.path.join(os.path.dirname(_nicegui_pkg.__file__),
                              "static", "favicon.ico")
if not os.path.exists(FAVICON_ATUAL):
    os.makedirs(os.path.dirname(FAVICON_ATUAL), exist_ok=True)
    shutil.copy2(FAVICON_PADRAO, FAVICON_ATUAL)

# ================== PÁGINA DE LOGIN ==================
@ui.page("/login")
def page_login():
    from mod_intranet.conexao_bd import get_config
    cor = get_config("cor_principal", "#1565C0") or "#1565C0"
    icone = (get_config("icone_sistema", "hub") or "hub").strip()
    titulo_login = get_config("texto_login_titulo", "INTRANET Básica") or "INTRANET Básica"
    subtitulo = get_config("texto_login_subtitulo", "Acesso restrito a usuários autorizados")
    hint = get_config("texto_login_hint",
                      "Primeiro acesso? Use master / master e troque a senha.")
    ui.colors(primary=cor)
    ui.query("body").classes("bg-blue-grey-10")
    import json as _json
    ui.run_javascript(f"document.title = {_json.dumps(titulo_login)}")
    # favicon com cache-busting: ?v muda quando o .ico é trocado
    from mod_intranet.conexao_bd import favicon_versao
    ui.add_head_html(
        f'<link rel="icon" type="image/x-icon" href="/favicon.ico?v={favicon_versao()}">')

    # Se já logado, vai direto pro dashboard
    if app.storage.user.get("usuario"):
        ui.navigate.to("/")
        return

    with ui.row().classes("w-full h-screen items-center justify-center"):
        with ui.card().classes("w-[420px] p-10 shadow-2xl"):
            with ui.column().classes("items-center w-full gap-1"):
                ui.icon(icone, size="64px").classes("text-primary")
                ui.label(titulo_login).classes("text-h5 font-bold text-primary")
            if subtitulo:
                ui.label(subtitulo).classes("text-caption text-grey-6 mb-4")

            usuario = ui.input("Usuário").props("outlined dense").classes("w-full")
            senha = ui.input("Senha", password=True, password_toggle_button=True).props(
                "outlined dense"
            ).classes("w-full")

            def tentar_login():
                ok, msg = autenticacao.autenticar(usuario.value or "", senha.value or "")
                if not ok:
                    ui.notify(msg, type="negative", position="top")
                    return
                nome = (usuario.value or "").strip()
                perfil = msg  # autenticar retorna o perfil na msg quando ok
                # hash amarra o cookie do navegador à linha da sessão no banco:
                # encerrar a sessão pelo admin derruba este navegador no próximo request
                sessao = autenticacao.registrar_login(nome, "sistema")
                app.storage.user["usuario"] = {"nome": nome, "perfil": perfil, "sessao": sessao}
                ui.notify(f"Bem-vindo(a), {nome}!", type="positive")
                ui.navigate.to("/")

            with ui.column().classes("w-full gap-2 mt-4"):
                ui.button("Entrar", on_click=tentar_login).props("unelevated size=lg color=primary").classes("w-full")
            ui.label(hint).classes(
                "text-caption text-grey-6 text-center mt-3"
            )

            senha.on("keydown.enter", tentar_login)



# ================== DASHBOARD ==================
@ui.page("/")
def page_dashboard():
    from mod_intranet.layout_tela import pagina_restrita
    user = pagina_restrita("Início")
    if not user:
        return

    nome = user["nome"]
    eh_admin = user.get("perfil") == "administrador_geral"

    with ui.column().classes("w-full p-6 gap-6"):
        # Banner de boas-vindas
        with ui.card().classes("w-full bg-primary text-white shadow-lg"):
            with ui.row().classes("w-full items-center justify-between p-4 flex-wrap gap-4"):
                with ui.column().classes("gap-0"):
                    saudacao = get_config("texto_home_saudacao", "Olá") or "Olá"
                    subtitulo_home = get_config("texto_home_subtitulo",
                                                "Sua intranet corporativa — tudo em um só lugar.")
                    ui.label(f"{saudacao}, {nome}!").classes("text-h4 font-bold")
                    ui.label(subtitulo_home).classes("text-subtitle1 opacity-90")
                ui.icon("diversity_3", size="80px").classes("opacity-30")

        # Feedback de 2s no carregamento: toast de boas-vindas (desaparece sozinho)
        ui.timer(0.1, lambda: ui.notify(f"Bem-vindo(a), {nome}!",
                                        type="positive", position="top", timeout=2),
                 once=True)

        # Grid fluido 360–1440px (mobile-first): 1 col <640px, 2 cols 640–1024px,
        # 3 cols >=1024px. Feed ocupa 2/3, resumo 1/3.
        with ui.grid(columns=3).classes("w-full gap-4 max-lg:grid-cols-2 max-sm:grid-cols-1"):

            # ---- Feed do Blog por padrão (RF-09) ----
            from mod_blog.telas import _card_postagem
            from mod_blog.manipulador_bd import listar_postagens
            pode_publicar_blog = (user.get("perfil") == "administrador_geral"
                                  or autenticacao.eh_admin_do_modulo(nome, "blog"))
            with ui.column().classes("col-span-2 max-lg:col-span-2 max-sm:col-span-1 "
                                     "w-full gap-4"):
                with ui.row().classes("w-full items-center justify-between"):
                    ui.label("Publicações recentes").classes("text-h6 font-bold text-grey-9")
                    ui.button("Abrir Blog completo", icon="article",
                              on_click=lambda: ui.navigate.to("/blog")) \
                        .props("outline color=primary dense")
                posts = listar_postagens(ativo=True, ordem="DESC")
                if not posts:
                    with ui.card().classes("w-full items-center p-8"):
                        ui.icon("article", size="48px").classes("text-grey-4")
                        ui.label("Nenhuma publicação ainda."
                                 + (" Acesse o Blog para criar a primeira!"
                                    if pode_publicar_blog else "")).classes("text-grey-6")
                for post in posts:
                    _card_postagem(post, nome, user.get("perfil", ""),
                                   lambda: ui.navigate.reload(),
                                   pode_publicar=pode_publicar_blog)

            # ---- Resumo do sistema (admin vê tudo; usuário comum vê o básico) ----
            def orquestrar_resumo():
                from mod_gest_cad_usuario import manipulador_bd as gest
                n_users = len(gest.listar_usuarios(filtro_ativo=True))
                from mod_blog import manipulador_bd as blog
                n_posts = blog.contar_postagens(ativo=True)
                from mod_auditoria.manipulador_bd import contar_registros
                n_logs = contar_registros()
                return n_users, n_posts, n_logs

            with ui.column().classes("col-span-1 max-sm:col-span-1 w-full gap-4"):
                with ui.card().classes("w-full border-l-4").style(
                        "border-left-color:#1565C0"):
                    with ui.card_section().classes("gap-3 w-full"):
                        ui.label("Resumo do sistema").classes("text-h6 font-bold text-grey-9")
                        resumo_wrap = ui.column().classes("w-full gap-2")

                        def render_resumo():
                            resumo_wrap.clear()
                            n_users, n_posts, n_logs = orquestrar_resumo()
                            with resumo_wrap:
                                _stat("Usuários ativos", n_users, "people")
                                _stat("Postagens", n_posts, "article")
                                if eh_admin:
                                    _stat("Registros de auditoria", n_logs, "history")

                        render_resumo()
                        lbl_fb_resumo = ui.label("").classes("text-caption text-green-8")

                        def atualizar_resumo():
                            render_resumo()
                            lbl_fb_resumo.set_text("Atualizado ✓")
                            # feedback de 2s: reverte o rótulo via timer
                            ui.timer(2.0, lambda: lbl_fb_resumo.set_text(""), once=True)

                        ui.button("Atualizar resumo", icon="refresh",
                                  on_click=atualizar_resumo) \
                            .props("outline color=primary dense").classes("w-full")


def _stat(rotulo, valor, icone):
    with ui.card().classes("w-full min-w-[160px] bg-grey-1 "
                           "transition-transform hover:-translate-y-0.5 hover:shadow-lg"):
        with ui.row().classes("items-center gap-3"):
            ui.icon(icone).classes("text-primary text-4xl")
            with ui.column().classes("gap-0"):
                ui.label(str(valor)).classes("text-h4 font-bold text-grey-9")
                ui.label(rotulo).classes("text-caption text-grey-6")


# ================== MÓDULOS ==================
@ui.page("/blog")
def page_blog():
    from mod_intranet.layout_tela import pagina_restrita
    user = pagina_restrita("Blog Corporativo", chave_modulo="blog")
    if not user:
        return
    from mod_blog.telas import mostrar_tela
    mostrar_tela(user["nome"], user.get("perfil", ""))


@ui.page("/users")
def page_users():
    from mod_intranet.layout_tela import pagina_restrita
    user = pagina_restrita("Gestão de Usuários", chave_modulo="usuarios")
    if not user:
        return
    from mod_gest_cad_usuario.telas import mostrar_tela
    mostrar_tela(user["nome"], user.get("perfil", ""))


@ui.page("/auditoria")
def page_auditoria():
    from mod_intranet.layout_tela import pagina_restrita
    user = pagina_restrita("Auditoria", chave_modulo="auditoria")
    if not user:
        return
    from mod_auditoria.telas import mostrar_tela
    mostrar_tela(user["nome"], user.get("perfil", ""))


@ui.page("/edit-pdf")
def page_edit_pdf():
    from mod_intranet.layout_tela import pagina_restrita
    user = pagina_restrita("Editor de PDF", chave_modulo="editar_pdf")
    if not user:
        return
    from mod_edit_pdf.telas import mostrar_tela
    mostrar_tela(user["nome"], user.get("perfil", ""))


@ui.page("/renomear-empenho")
def page_renomear_empenho():
    from mod_intranet.layout_tela import pagina_restrita
    user = pagina_restrita("Renomear Empenhos", chave_modulo="empenhos")
    if not user:
        return
    from mod_renomear_empenho.telas import mostrar_tela
    mostrar_tela(user["nome"], user.get("perfil", ""))


@app.get("/solicita-impressao/pdf/{solicitacao_id}")
def baixar_pdf_impressao(solicitacao_id: int):
    """Rota de download do PDF da solicitação (com marca d'água se ativa).

    Protegida: exige autenticação e permissão sobre a solicitação (solicitante,
    responsável pelo vínculo da secretaria/setor ou administrador do módulo).
    """
    from mod_solicita_impressao import manipulador_bd as bd
    from mod_intranet.layout_tela import usuario_logado

    user = usuario_logado()
    if not user:
        return RedirectResponse("/login")
    nome = user.get("nome", "")

    # Revalida sessão ativa (bloqueio/exclusão derrubam sessões vivas)
    linha = autenticacao.usuario_existe(nome)
    if not linha or not linha[2]:
        return RedirectResponse("/login")
    if not autenticacao.validar_acesso_modulo(nome, "solicita_impressao"):
        return RedirectResponse("/solicita-impressao")

    sol = bd.obter_solicitacao(solicitacao_id)
    if not sol or not sol.get("caminho_arquivo") or not os.path.exists(sol["caminho_arquivo"]):
        return RedirectResponse("/solicita-impressao")

    eh_admin = (autenticacao.perfil_global_de(nome) == "administrador_geral"
                or autenticacao.eh_admin_do_modulo(nome, "solicita_impressao"))
    eh_solicitante = (sol.get("usuario_solicitante") == nome)
    eh_responsavel = False
    if sol.get("secretaria_id"):
        eh_responsavel = bd.eh_responsavel_autorizacao(
            nome, sol["secretaria_id"], sol.get("setor_id"))
    if not (eh_admin or eh_solicitante or eh_responsavel):
        return RedirectResponse("/solicita-impressao")

    sec = bd.obter_secretaria(sol.get("secretaria_id"))
    st = bd.obter_setor(sol.get("setor_id")) if sol.get("setor_id") else None
    sec_nome = (sec[2] or sec[1]) if sec else ""
    st_nome = st[1] if st else "—"
    caminho = bd.aplicar_marca_dagua(
        sol["caminho_arquivo"], solicitacao_id, "sistema",
        sec_nome, st_nome, sol.get("usuario_solicitante", ""))
    return FileResponse(caminho, filename=sol.get("arquivo_servidor") or "documento.pdf",
                        media_type="application/pdf")


@ui.page("/solicita-impressao")
def page_solicita_impressao():
    from mod_intranet.layout_tela import pagina_restrita
    user = pagina_restrita("Solicitação de Impressão", chave_modulo="solicita_impressao")
    if not user:
        return
    from mod_solicita_impressao.telas import mostrar_tela
    mostrar_tela(user["nome"], user.get("perfil", ""))
    # Carrega o JS de impressão (listar/imprimir via cliente)
    ui.add_head_html('<script src="/solicita-impressao/src/impressao.js"></script>')


@app.get("/solicita-impressao/src/impressao.js")
def servir_js_impressao():
    caminho = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "mod_solicita_impressao", "src", "impressao.js")
    with open(caminho, "r", encoding="utf-8") as f:
        conteudo = f.read()
    return Response(content=conteudo, media_type="application/javascript")


@ui.page("/configuracoes")
def page_configuracoes():
    from mod_intranet.layout_tela import pagina_restrita
    user = pagina_restrita("Configurações")
    if not user:
        return
    from mod_intranet.tela_configuracoes import mostrar_tela
    mostrar_tela(user["nome"], user.get("perfil", ""))


# ================== START ==================
if __name__ in ("__main__", "__mp_main__"):
    # Observabilidade (loguru): configura sink de arquivo + captura de exceções
    from mod_intranet import observabilidade
    observabilidade.configurar()
    observabilidade.instalar_excepthook()

    _agendador = iniciar_agendador()

    observabilidade.get_logger().info("Intranet iniciada (boot concluído)")

    # ================== DOCUMENTAÇÃO MKDOCS (/documentacao) ==================
    # Build estático de docs/ -> site/ e montagem como rota FastAPI da própria
    # app (mesma porta). Falha NUNCA derruba o servidor.
    from mod_intranet.documentacao import construir_e_montar_documentacao
    construir_e_montar_documentacao()

    ui.run(
        title=get_config("texto_login_titulo", "INTRANET Básica") or "INTRANET Básica",
        favicon="assets/favicon_atual.ico",  # arquivo vivo: upload troca sem restart
        storage_secret="intranet-secret-2026-mude-isto",
        reload=False,
        port=8080,
        show=False,
    )
