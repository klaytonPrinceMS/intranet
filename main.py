"""Intranet Modular — NiceGUI entrypoint (boot, routes and module wiring).

Ponto de entrada da aplicação: inicializa os bancos (SQLite), a telemetria
OTel e o build da documentação MkDocs; define as rotas centrais (login,
dashboard `/`, configurações `/configuracoes`, administração por módulo
`/admin/{chave_modulo}` e documentação). A rota `/admin/{chave_modulo}`
aplica o tema de cada módulo via `tema_modulo.ler_tema` antes de renderizar
o `mostrar_administracao` dedicado de cada `mod_<nome>/telas_administracao.py`."""
import sys
import os
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from nicegui import ui, app
from fastapi.responses import FileResponse, Response, RedirectResponse

# Patches no NiceGUI: timers cujo slot da página foi deletado param em silêncio
# (evita "The parent slot of Timer has been deleted" ao navegar/fechar página).
from mod_intranet.nicegui_patch import aplicar as _aplicar_nicegui_patch
_aplicar_nicegui_patch()

from mod_intranet.bd_conexao import (
    get_config
)
from mod_intranet import autenticacao
from mod_intranet.tema_modulo import notificar

# ================== ASSISTENTE DE ATIVAÇÃO (terminal) ==================
# Sem argumentos: sobe direto com a configuração persistida (modo padrão).
# --config: assistente interativo (ENTER = básico SQLite; 1 = configurar
#           otel, postgres e portas). --help mostra a ajuda.
# Com outros argumentos (Typer): configura direto, ex.:
#   python main.py --postgres --portapostgres 5444 --otel \
#       --portatelemetria 3000 --portadocumentacao 8081
#   python main.py --help
from mod_intranet import ativacao
_cfg = None
_args = sys.argv[1:]
# print(f"[debug] _args={_args} _cfg_before={_cfg}", file=sys.stderr)
if not _args:
    # modo padrão: sem perguntas, usa o que já está persistido
    _cfg = ativacao.config_persistida()
elif any(a in ("--config", "-c") for a in _args):
    # --config/-c: força o wizard interativo (pode vir com outras flags, mas prioriza wizard)
    _cfg = ativacao.iniciar(cli_cfg=None)
elif any(a.startswith("-") for a in _args):
    # deixa o Typer cuidar de --help/--scan-ports/--postgres/--otel
    _cli_opts = ativacao.cli_opcoes(_args)
    if _cli_opts.get("config"):
        _cfg = ativacao.iniciar(cli_cfg=None)
    else:
        _cli_opts.pop("config", None)
        _cli_cfg = ativacao.config_do_cli(**_cli_opts)
        _cfg = ativacao.iniciar(cli_cfg=_cli_cfg)
else:
    _cfg = ativacao.config_persistida()
ativacao.aplicar_banco(_cfg)

# ================== OBSERVABILIDADE (console colorido) ==================
# Configura o loguru ANTES de criar os bancos para manter as cores do console
# consistentes (a criação dos bancos também fica colorida).
from mod_intranet import observabilidade
observabilidade.configurar()

# ================== INICIALIZAÇÃO DOS BANCOS ==================
from mod_intranet.bd_criador import inicializar_bancos
inicializar_bancos()

# ================== INICIALIZAÇÃO OTEL (observabilidade) ==================
# `otel_ativo=0` desliga a telemetria; `otel_auto_start_stack=0` usa stack
# remota/dedicada (pula o `compose up` local e as checagens de Docker).
try:
    _otel_ativo = _cfg.get("otel_ativo", True) and \
        get_config("otel_ativo", "1") == "1"
    _otel_auto_stack = get_config("otel_auto_start_stack", "1") == "1"
    if not _otel_ativo:
        print("[otel] Telemetria OTel desativada (otel_ativo=0)")
    else:
        from mod_intranet.docker_detector import auto_iniciar_otel
        from mod_intranet.otel_integracao import inicializar_otel, finalizar_otel
        _stack_ok = auto_iniciar_otel() if _otel_auto_stack else True
        if _stack_ok and inicializar_otel(auto_stack=_otel_auto_stack):
            # Registra shutdown hook para finalizar OTel ao encerrar
            import atexit
            atexit.register(finalizar_otel)

            # Instrumenta a aplicação: métricas + spans por requisição HTTP
            from mod_intranet.instrumentacao_app import instrumentar_aplicacao
            instrumentar_aplicacao(app)

            # Sincroniza credenciais do Grafana com o usuário master
            # (só com stack local — via `docker exec`; remota usa token — Fase 3)
            if _otel_auto_stack:
                try:
                    from mod_intranet.grafana_sync import sincronizar_credenciais
                    sucesso, msg = sincronizar_credenciais()
                    if sucesso:
                        print(f"[grafana] {msg}")
                    else:
                        print(f"[grafana] {msg}")
                except Exception as e:
                    print(f"[grafana] Aviso: não foi possível sincronizar credenciais: {e}")
            else:
                print("[otel] Stack remota: sync de credenciais Grafana ignorado "
                      "(use token/API)")
        else:
            print("[otel] O sistema funcionará sem telemetria OTel")
except Exception as e:
    print(f"[otel] Aviso: não foi possível inicializar OTel: {e}")
    print("[otel] O sistema funcionará sem telemetria OTel")

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


# ================== CSS FRAMEWORKS EMBARCADOS (assets/css/frameworks) ==================
# Estilos opcionais (Bulma/DaisyUI/Pico/Picnic) servidos localmente em /css/frameworks/*.
# A injeção em páginas é feita sob demanda via tema_css.injetar_framework().
try:
    from mod_intranet import tema_css
    tema_css.montar_rotas_static()
except Exception:
    print("[css] Aviso: não foi possível montar as rotas de /css/frameworks")

# ================== ROTAS DINÂMICAS DE MÓDULOS (slugs customizados) ==================
# Permite que a URL de cada página (tb_modulos.rota) seja editada em
# /configuracoes e re-registrada no servidor sem restart. Os decorators fixos
# abaixo continuam registrando as rotas padrão; montar_rotas_ativas() re-registra
# os slugs customizados persistidos no banco.
try:
    from mod_intranet import rotas_modulos
except Exception:
    print("[rotas] Aviso: não foi possível importar rotas_modulos")
    rotas_modulos = None


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
    from mod_intranet.bd_conexao import get_config
    cor = get_config("cor_principal", "#000000") or "#000000"
    icone = (get_config("icone_sistema", "hub") or "hub").strip()
    titulo_login = get_config("texto_login_titulo", "INTRANET Básica") or "INTRANET Básica"
    subtitulo = get_config("texto_login_subtitulo", "Acesso restrito a usuários autorizados")
    hint = get_config("texto_login_hint",
                      "Novos usuários? Procure o DTI para realizar o seu cadastro.")
    ui.colors(primary=cor)
    fundo_login = get_config("cor_fundo", "#EEEEEE") or "#EEEEEE"
    ui.query("body").style(f"background:{fundo_login}")
    try:
        ui.query(".q-page").style(f"background-color:{fundo_login}")
    except Exception:
        pass
    import json as _json
    ui.run_javascript(f"document.title = {_json.dumps(titulo_login)}")
    # favicon com cache-busting: ?v muda quando o .ico é trocado
    from mod_intranet.bd_conexao import favicon_versao
    ui.add_head_html(
        f'<link rel="icon" type="image/x-icon" href="/favicon.ico?v={favicon_versao()}">')

    # Se já logado, vai direto pro dashboard
    if app.storage.user.get("usuario"):
        ui.navigate.to("/")
        return

    with ui.row().classes("w-full h-screen items-center justify-center p-4").style("min-width: 0"):
        from mod_intranet.tema_modulo import estilo_cartao as _estilo_cartao_fn
        with ui.card().classes("w-full max-w-[420px] p-6 sm:p-10 shadow-2xl mx-4").style(f"{_estilo_cartao_fn()}; min-width: 0"):
            with ui.column().classes("items-center w-full gap-1"):
                ui.icon(icone, size="64px").classes("text-primary")
                ui.label(titulo_login).classes("text-h5 font-bold text-primary")
            if subtitulo:
                ui.label(subtitulo).classes("text-caption text-grey-6 mb-4")

            usuario = ui.input("Usuário", placeholder="master").props("outlined dense").classes("w-full") \
                .props('data-testid=login-usuario')
            senha = ui.input("Senha", password=True, password_toggle_button=True,
                             placeholder="master").props(
                "outlined dense"
            ).classes("w-full") \
                .props('data-testid=login-senha')

            def tentar_login():
                ok, msg = autenticacao.autenticar(usuario.value or "", senha.value or "")
                # Observabilidade: registra a tentativa de login (métrica OTel)
                try:
                    from mod_intranet.otel_integracao import registrar_login_observabilidade
                    registrar_login_observabilidade(usuario.value or "", ok)
                except Exception:
                    pass
                if not ok:
                    notificar(msg, type="negative", position="top")
                    return
                nome = (usuario.value or "").strip()
                perfil = msg  # autenticar retorna o perfil na msg quando ok
                # hash amarra o cookie do navegador à linha da sessão no banco:
                # encerrar a sessão pelo admin derruba este navegador no próximo request
                sessao = autenticacao.registrar_login(nome, "sistema")
                app.storage.user["usuario"] = {"nome": nome, "perfil": perfil, "sessao": sessao}
                notificar(f"Bem-vindo(a), {nome}!", type="positive")
                ui.navigate.to("/")

            with ui.column().classes("w-full gap-2 mt-4"):
                from mod_intranet.tema_modulo import botao as _botao_tema
                _botao_tema("Entrar", on_click=tentar_login, extra_classes="w-full") \
                    .props('data-testid=login-entrar')
            ui.label(hint).classes(
                "text-caption text-grey-6 text-center mt-3"
            )

            senha.on("keydown.enter", tentar_login)



# ================== DASHBOARD ==================
@ui.page("/")
def page_dashboard():
    from mod_intranet.telas import pagina_restrita
    user = pagina_restrita("Início")
    if not user:
        return

    nome = user["nome"]
    eh_admin = user.get("perfil") in ("administrador_geral", "administrador_modulo")

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
        ui.timer(0.1, lambda: notificar(f"Bem-vindo(a), {nome}!",
                                        type="positive", position="top", timeout=2),
                 once=True)

        # ---- Resumo do sistema (somente administradores: geral e de módulos) ----
        # Fica logo abaixo das boas-vindas e acima das postagens do blog.
        if eh_admin:
            def orquestrar_resumo():
                from mod_gest_cad_usuario import bd_manipulador as gest
                n_users = len(gest.listar_usuarios(filtro_ativo=True))
                from mod_blog import bd_manipulador as blog
                n_posts = blog.contar_postagens(ativo=True)
                from mod_auditoria.db_manipulador import contar_registros
                n_logs = contar_registros()
                return n_users, n_posts, n_logs

            from mod_intranet.tema_modulo import estilo_cartao as _estilo_cartao_fn2
            with ui.card().classes("w-full border-l-4").style(
                    f"border-left-color:#000000;{_estilo_cartao_fn2()}"):
                with ui.card_section().classes("gap-4 w-full"):
                    with ui.row().classes("w-full items-center justify-between flex-wrap gap-2"):
                        ui.label("Resumo do sistema").classes("text-h6 font-bold text-grey-9")
                        with ui.row().classes("items-center gap-2"):
                            lbl_fb_resumo = ui.label("").classes("text-caption text-green-8")
                            from mod_intranet.tema_modulo import botao as _botao_tema
                            _botao_tema("Atualizar", icone="refresh",
                                        variante="contorno",
                                        on_click=lambda: atualizar_resumo())

                    resumo_wrap = ui.row().classes("w-full justify-center gap-4")

                    def render_resumo():
                        resumo_wrap.clear()
                        n_users, n_posts, n_logs = orquestrar_resumo()
                        with resumo_wrap:
                            _stat("Usuários ativos", n_users, "people")
                            _stat("Postagens", n_posts, "article")
                            _stat("Registros de auditoria", n_logs, "history")

                    def atualizar_resumo():
                        render_resumo()
                        lbl_fb_resumo.set_text("Atualizado ✓")
                        # feedback de 2s: reverte o rótulo via timer
                        ui.timer(2.0, lambda: lbl_fb_resumo.set_text(""), once=True)

                    render_resumo()

        # ---- Feed do Blog (RF-09) — respeita o padrão de exibição ----
        # A Home mostra as postagens no MESMO padrão configurado no Blog
        # (histórico/única/carrossel): a fonte única é
        # `mod_blog.telas.renderizar_postagens`, também usada pela tela do Blog.
        from mod_blog.telas import renderizar_postagens
        pode_publicar_blog = (user.get("perfil") == "administrador_geral"
                              or autenticacao.eh_admin_do_modulo(nome, "blog"))
        with ui.column().classes("w-full gap-4"):
            with ui.row().classes("w-full items-center justify-between"):
                ui.label("Publicações recentes").classes("text-h6 font-bold text-grey-9")
                from mod_intranet.tema_modulo import botao as _botao_tema
                _botao_tema("Abrir Blog completo", icone="article",
                            variante="contorno",
                            on_click=lambda: ui.navigate.to("/blog"))
            _feed_wrap = ui.column().classes("w-full gap-4")
            renderizar_postagens(_feed_wrap, nome, user.get("perfil", ""),
                                 pode_publicar_blog,
                                 lambda: ui.navigate.reload())


def _stat(rotulo, valor, icone):
    from mod_intranet.tema_modulo import estilo_cartao as _estilo_cartao_fn3
    with ui.card().classes("flex-1 min-w-[140px] max-w-[240px] bg-grey-1 "
                           "transition-transform hover:-translate-y-0.5 hover:shadow-lg") \
            .style(_estilo_cartao_fn3()):
        with ui.column().classes("items-center justify-center gap-1 px-2 py-3"):
            ui.icon(icone).classes("text-primary text-3xl")
            ui.label(str(valor)).classes("text-h5 font-bold text-grey-9")
            ui.label(rotulo).classes("text-caption text-grey-6 text-center")


# ================== MÓDULOS ==================
@ui.page("/blog")
def page_blog():
    from mod_intranet.telas import pagina_restrita
    user = pagina_restrita("Blog Corporativo", chave_modulo="blog")
    if not user:
        return
    from mod_blog.telas import mostrar_tela
    mostrar_tela(user["nome"], user.get("perfil", ""))


if rotas_modulos is not None:
    rotas_modulos.REGISTRO_MODULOS["blog"] = page_blog


@ui.page("/users")
def page_users():
    from mod_intranet.telas import pagina_restrita
    user = pagina_restrita("Gestão de Usuários", chave_modulo="usuarios")
    if not user:
        return
    from mod_gest_cad_usuario.telas import mostrar_tela
    mostrar_tela(user["nome"], user.get("perfil", ""))


if rotas_modulos is not None:
    rotas_modulos.REGISTRO_MODULOS["usuarios"] = page_users


@ui.page("/auditoria")
def page_auditoria():
    from mod_intranet.telas import pagina_restrita
    user = pagina_restrita("Auditoria", chave_modulo="auditoria")
    if not user:
        return
    from mod_auditoria.telas import mostrar_tela
    mostrar_tela(user["nome"], user.get("perfil", ""))


if rotas_modulos is not None:
    rotas_modulos.REGISTRO_MODULOS["auditoria"] = page_auditoria


@ui.page("/edit-pdf")
def page_edit_pdf():
    from mod_intranet.telas import pagina_restrita
    user = pagina_restrita("Editor de PDF", chave_modulo="editar_pdf")
    if not user:
        return
    from mod_edit_pdf.telas import mostrar_tela
    mostrar_tela(user["nome"], user.get("perfil", ""))


if rotas_modulos is not None:
    rotas_modulos.REGISTRO_MODULOS["editar_pdf"] = page_edit_pdf


@ui.page("/renomear-empenho")
def page_renomear_empenho():
    from mod_intranet.telas import pagina_restrita
    user = pagina_restrita("Renomear Empenhos", chave_modulo="empenhos")
    if not user:
        return
    from mod_renomear_empenho.telas import mostrar_tela
    mostrar_tela(user["nome"], user.get("perfil", ""))


if rotas_modulos is not None:
    rotas_modulos.REGISTRO_MODULOS["empenhos"] = page_renomear_empenho


@app.get("/solicita-impressao/pdf/{solicitacao_id}")
def baixar_pdf_impressao(solicitacao_id: int):
    """Rota de download do PDF da solicitação (com marca d'água se ativa).

    Protegida: exige autenticação e permissão sobre a solicitação (solicitante,
    responsável pelo vínculo da secretaria/setor ou administrador do módulo).
    """
    from mod_solicita_impressao import bd_manipulador as bd
    from mod_intranet.telas import usuario_logado

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
    from mod_intranet.telas import pagina_restrita
    user = pagina_restrita("Solicitação de Impressão", chave_modulo="solicita_impressao")
    if not user:
        return
    from mod_solicita_impressao.telas import mostrar_tela
    mostrar_tela(user["nome"], user.get("perfil", ""))
    # Carrega o JS de impressão (listar/imprimir via cliente)
    ui.add_head_html('<script src="/solicita-impressao/src/impressao.js"></script>')


if rotas_modulos is not None:
    rotas_modulos.REGISTRO_MODULOS["solicita_impressao"] = page_solicita_impressao


@app.get("/solicita-impressao/src/impressao.js")
def servir_js_impressao():
    caminho = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "mod_solicita_impressao", "src", "impressao.js")
    with open(caminho, "r", encoding="utf-8") as f:
        conteudo = f.read()
    return Response(content=conteudo, media_type="application/javascript")


@ui.page("/admin/{chave_modulo}")
def page_admin_modulo(chave_modulo: str):
    """Renders the standalone administration panel for a given module.

    Rota dedicada para a administração de cada módulo: quando o usuário
    clica em 'Administração' no menu hambúrguer, é direcionado para
    `/admin/{chave_modulo}` que mostra apenas a tela de configuração
    daquele módulo, sem as abas de navegação normais."""
    from mod_intranet.telas import pagina_restrita
    from mod_intranet import autenticacao

    nome_modulo = autenticacao.nome_do_modulo(chave_modulo) or "Administração"
    user = pagina_restrita(nome_modulo, chave_modulo=chave_modulo)
    if not user:
        return

    perfil = user.get("perfil", "")
    nome = user["nome"]

    if chave_modulo == "blog":
        pode_pub = (perfil == "administrador_geral"
                    or autenticacao.eh_admin_do_modulo(nome, "blog"))
        from mod_blog.telas_administracao import mostrar_administracao
        from mod_intranet.tema_modulo import ler_tema
        tema = ler_tema("blog", cor_botao="#000000", cor_texto_botao="#FFFFFF",
                        texto_header="Comunique novidades para toda a equipe.")
        ui.colors(primary=tema["cor_botao"])
        mostrar_administracao(nome, pode_pub)

    elif chave_modulo == "usuarios":
        from mod_gest_cad_usuario.telas_administracao import mostrar_administracao
        from mod_intranet.tema_modulo import ler_tema
        tema = ler_tema("usuarios", cor_botao="#000000", cor_texto_botao="#FFFFFF")
        ui.colors(primary=tema["cor_botao"])
        with ui.column().classes("w-full p-6"):
            mostrar_administracao(nome)

    elif chave_modulo == "auditoria":
        eh_admin = perfil == "administrador_geral"
        from mod_auditoria.telas_administracao import mostrar_administracao
        from mod_intranet.tema_modulo import ler_tema
        ui.colors(primary=ler_tema("auditoria", cor_botao="#000000")["cor_botao"])
        mostrar_administracao(nome, eh_admin_geral=eh_admin)

    elif chave_modulo == "editar_pdf":
        eh_admin = perfil == "administrador_geral"
        from mod_edit_pdf.telas_administracao import mostrar_administracao
        from mod_intranet.tema_modulo import ler_tema
        ui.colors(primary=ler_tema("editar_pdf", cor_botao="#000000")["cor_botao"])
        mostrar_administracao(nome, eh_admin)

    elif chave_modulo == "empenhos":
        eh_admin = perfil == "administrador_geral"
        from mod_renomear_empenho.telas_administracao import mostrar_administracao
        from mod_intranet.bd_conexao import get_config, set_config
        t_cor_botao = get_config("empenhos_cor_botao", "#000000") or "#000000"
        ui.colors(primary=t_cor_botao)
        t_cor_txt_botao = get_config("empenhos_cor_texto_botao", "#FFFFFF") or "#FFFFFF"
        t_cor_fundo = get_config("empenhos_cor_fundo", "") or ""
        t_cor_titulo = get_config("empenhos_cor_titulo", "#212121") or "#212121"
        t_tamanho = get_config("empenhos_btn_tamanho", "medium") or "medium"
        texto_header = get_config("empenhos_texto_header",
                                  "Monitora pastas, extrai nº de empenho e renomeia.") or ""
        def _btn_cls(): return "text-white"
        def _btn_style(): return f"background:{t_cor_botao};color:{t_cor_txt_botao};"
        mostrar_administracao(nome, eh_admin, t_cor_botao, t_cor_txt_botao,
                              t_cor_fundo, t_cor_titulo, t_tamanho, texto_header,
                              _btn_cls, _btn_style, get_config, set_config)

    elif chave_modulo == "solicita_impressao":
        eh_admin = (perfil == "administrador_geral"
                    or autenticacao.eh_admin_do_modulo(nome, "solicita_impressao"))
        from mod_solicita_impressao.telas_administracao import mostrar_administracao
        from mod_intranet.tema_modulo import ler_tema
        ui.colors(primary=ler_tema("solicita_impressao",
                                   cor_botao="#000000")["cor_botao"])
        mostrar_administracao(nome, eh_admin)

    else:
        ui.navigate.to("/configuracoes")


@ui.page("/configuracoes")
def page_configuracoes():
    from mod_intranet.telas import pagina_restrita
    user = pagina_restrita("Administração")
    if not user:
        return
    from mod_intranet.tela_configuracoes import mostrar_tela
    mostrar_tela(user["nome"], user.get("perfil", ""))


# ================== START ==================
# Re-registra slugs customizados persistidos em tb_modulos (idempotente):
# as rotas padrão já foram registradas pelos decorators fixos acima.
if rotas_modulos is not None:
    rotas_modulos.montar_rotas_ativas()

if __name__ in ("__main__", "__mp_main__"):
    # Observabilidade (loguru): configura sink de arquivo + captura de exceções
    from mod_intranet import observabilidade
    observabilidade.configurar()
    observabilidade.instalar_excepthook()

    # Passos de boot com barra de progresso no terminal
    def _passo_agendador():
        return iniciar_agendador()

    def _passo_docs():
        from mod_intranet.documentacao import (
            construir_e_montar_documentacao,
            iniciar_servidor,
        )
        construir_e_montar_documentacao(
            porta=_cfg.get("porta_documentacao", 8000))
        iniciar_servidor(_cfg.get("porta_documentacao", 8000))

    ativacao.progresso_boot([
        ("Agendadores (backup/limpeza/monitor)", _passo_agendador),
        (f"Documentação MkDocs (http://localhost:"
         f"{_cfg.get('porta_documentacao', 8000)})", _passo_docs),
    ])

    observabilidade.get_logger().info("Intranet iniciada (boot concluído)")

    ui.run(
        title=get_config("texto_login_titulo", "INTRANET Básica") or "INTRANET Básica",
        favicon="assets/favicon_atual.ico",  # arquivo vivo: upload troca sem restart
        storage_secret=os.environ.get("INTRANET_STORAGE_SECRET")
        or "intranet-secret-2026-mude-isto",  # trocar via env em produção
        reload=False,
        port=_cfg.get("porta_site", 8080),
        show=False,
    )
