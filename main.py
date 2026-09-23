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
# `INTRANET_SEM_OTEL=1` força o desligamento (usada por iniciar.bat/.sh
# para subir no modo padrão, sem Docker/Postgres/Grafana).
try:
    _sem_otel_env = (os.environ.get("INTRANET_SEM_OTEL") or "").strip() == "1"
    _otel_ativo = _cfg.get("otel_ativo", True) and \
        get_config("otel_ativo", "1") == "1" and not _sem_otel_env
    if _sem_otel_env:
        print("[otel] Telemetria OTel desativada (INTRANET_SEM_OTEL=1)")
    elif not _otel_ativo:
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
    try:
        return rotinas.iniciar_agendador()
    except Exception as e:
        observabilidade.get_logger("intranet").exception(
            "iniciar_agendador: falha ao iniciar o agendador: %s", e)
        raise


# ================== CSS FRAMEWORKS EMBARCADOS (assets/css/frameworks) ==================
# Estilos opcionais (Bulma/DaisyUI/Pico/Picnic) servidos localmente em /css/frameworks/*.
# A injeção em páginas é feita sob demanda via tema_css.injetar_framework().
try:
    from mod_intranet import tema_css
    tema_css.montar_rotas_static()
except Exception:
    print("[css] Aviso: não foi possível montar as rotas de /css/frameworks")



# ================== IMAGENS DO BLOG (/img_postagens/*) ==================
# Arquivos enviados pelo editor WYSIWYG, gravados em mod_blog/img_postagens/.
try:
    from mod_blog import montar_rotas_static as _montar_img_blog
    _montar_img_blog()
except Exception:
    print("[blog] Aviso: não foi possível montar as rotas de /img_postagens")

# ================== MÍDIA DAS FILAS (/midia_filas/*) ==================
# Áudios MP3 (música elevador) e vídeos MP4 (propaganda) para a TV.
try:
    from mod_filas.bd_manipulador import montar_rotas_static as _montar_midia_filas
    _montar_midia_filas()
except Exception:
    print("[filas] Aviso: não foi possível montar as rotas de /midia_filas")

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
    try:
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
                    try:
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
                        # Contador padronizado — só logins, nunca navegações/refreshs
                        try:
                            from mod_intranet.bd_conexao import incrementar_contador_acessos
                            incrementar_contador_acessos()
                        except Exception:
                            pass
                        app.storage.user["usuario"] = {"nome": nome, "perfil": perfil, "sessao": sessao}
                        notificar(f"Bem-vindo(a), {nome}!", type="positive")
                        ui.navigate.to("/")
                    except Exception as e:
                        observabilidade.get_logger("intranet").exception(
                            "tentar_login: falha ao autenticar: %s", e)
                        notificar("Erro ao tentar entrar. Tente novamente.", tipo="error")

                with ui.column().classes("w-full gap-2 mt-4"):
                    from mod_intranet.tema_modulo import botao as _botao_tema
                    _botao_tema("Entrar", on_click=tentar_login, extra_classes="w-full") \
                        .props('data-testid=login-entrar')
                ui.label(hint).classes(
                    "text-caption text-grey-6 text-center mt-3"
                )

                senha.on("keydown.enter", tentar_login)
    except Exception as e:
        observabilidade.get_logger("intranet").exception(
            "page_login: erro ao renderizar a página de login: %s", e)
        notificar("Erro ao carregar a página de login.", tipo="error")



# ================== DASHBOARD ==================
def _orquestrar_resumo_dados():
    """Coleta os 9 contadores do Resumo — 5 base + fila impressão, quarentena, pdf uso, auditoria 24h."""
    try:
        from mod_gest_cad_usuario import bd_manipulador as gest
        try:
            n_users = len(gest.listar_usuarios(filtro_ativo=None))
        except Exception:
            n_users = len(gest.listar_usuarios(filtro_ativo=True))
        from mod_blog import bd_manipulador as blog
        n_posts = blog.contar_postagens(ativo=True)
        from mod_auditoria.bd_manipulador import contar_registros
        n_logs = contar_registros()
        # Sessões ativas
        try:
            from mod_intranet.bd_conexao import get_connection
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM tb_sessoes WHERE logout_timestamp IS NULL")
            n_sessoes = cur.fetchone()[0]
            conn.close()
        except Exception:
            n_sessoes = 0
        # Acessos (logins desde inicio)
        try:
            from mod_intranet.bd_conexao import get_config
            n_acessos = int((get_config("contador_acessos_total", "0") or "0").strip() or 0)
        except Exception:
            n_acessos = 0
        # 1) Fila impressão pendente (status aberto) — via API pública do módulo
        try:
            from mod_solicita_impressao import bd_manipulador as _bd_sol
            n_fila = _bd_sol.contar_solicitacoes_pendentes()
        except Exception:
            n_fila = 0
        # 2) Quarentena empenhos pendente — via API pública do módulo
        try:
            from mod_renomear_empenho import bd_manipulador as _bd_emp
            n_quar = _bd_emp.contar_quarentena_pendente()
        except Exception:
            n_quar = 0
        # 4) Uso PDF global — arquivos ativos — via API pública do módulo
        try:
            from mod_edit_pdf import bd_manipulador as _bd_pdf
            n_pdf = _bd_pdf.contar_arquivos_ativos()
        except Exception:
            n_pdf = 0
        # 5) Auditoria 24h
        try:
            from mod_auditoria.bd_manipulador import get_tabelas_auditoria, get_auditoria_connection
            conn_a = get_auditoria_connection()
            cur_a = conn_a.cursor()
            n_24h = 0
            for tbl in get_tabelas_auditoria():
                try:
                    # tbl vem do sqlite_master filtrado (tb_auditoria_*); revalida
                    # como identificador antes de interpolar (defesa em profundidade).
                    if not (tbl or "").startswith("tb_auditoria_"):
                        continue
                    if not tbl.replace("_", "").isalnum():
                        continue
                    cur_a.execute(f"SELECT COUNT(*) FROM {tbl} WHERE timestamp >= datetime('now','localtime','-1 day')")  # nosec B608 — tbl validado acima (prefixo + identificador); valores fixos
                    n_24h += cur_a.fetchone()[0]
                except Exception:
                    continue
            conn_a.close()
        except Exception:
            n_24h = 0
        return n_users, n_posts, n_logs, n_sessoes, n_acessos, n_fila, n_quar, n_pdf, n_24h
    except Exception as e:
        observabilidade.get_logger("intranet").exception(
            "_orquestrar_resumo_dados: falha ao coletar o resumo: %s", e)
        return 0, 0, 0, 0, 0, 0, 0, 0, 0


def _stat(rotulo, valor, icone, *, modelo="pic"):
    """Card de métrica do Resumo — ícone ampliado + número lateral (4 dígitos, >9999) — altura -25% + tooltip descritivo."""
    try:
        from mod_intranet.tema_modulo import estilo_cartao as _estilo_cartao_fn3
        from mod_intranet import home_visual as _hv
        classes = _hv.classes_stat(modelo)
        # Tooltip simples — rótulo curto
        _desc_base = {
            "Usuários ativos": "Usuarios",
            "Sessões ativas": "Sessões",
            "Postagens": "Noticias",
            "Registros de auditoria": "Logs",
            "Acessos": "Visitas",
            "Acessos ao sistema": "Visitas",
            "Fila impressão": "Fila impressão",
            "Fila geral": "Fila geral",
            "Para autorizar": "Para autorizar",
            "Quarentena": "Quarentena",
            "PDFs": "PDFs",
            "Auditoria 24h": "Auditoria 24h",
        }.get(rotulo, rotulo)
        # Formata 4 dígitos; acima de 9999 exibe ">9999" e alerta de backup da auditoria
        try:
            v = int(valor)
            texto_valor = str(v) if v <= 9999 else ">9999"
            v_int = v
        except Exception:
            texto_valor = str(valor)
            v_int = None
        _desc = _desc_base
        if v_int is not None and v_int > 9999:
            # Alerta específico para auditoria; demais >9999 mostram total real no tooltip
            if rotulo == "Registros de auditoria":
                _desc = f"{_desc_base} Total real: {v_int}. ⚠️ Alerta: volume elevado — realize backup do banco de auditoria (db_mod_auditoria.db) e avalie retenção/poda."
            else:
                _desc = f"{_desc_base} Total real: {v_int}."
        with ui.card().classes(classes).style(_estilo_cartao_fn3()).tooltip(_desc):
            # Layout horizontal: ícone à esquerda + número à direita — exibe 4 dígitos (tooltip só no card)
            with ui.row().classes("w-full items-center justify-center gap-2 px-2 py-1").style("min-width: 0"):
                with ui.element("div").classes("home-stat-icon bg-primary/10 shrink-0"):
                    ui.icon(icone).classes("text-primary text-2xl")
                ui.label(texto_valor).classes("text-h6 font-extrabold text-grey-9 leading-none min-w-[4ch] text-center").style("min-width: 0")
    except Exception as e:
        observabilidade.get_logger("intranet").exception(
            "_stat: falha ao renderizar card de métrica '%s': %s", rotulo, e)
        notificar(f"Erro ao renderizar a métrica {rotulo}.", tipo="error")


def _construir_dashboard(nome: str, perfil: str, eh_admin: bool, modelo: str = "pic"):
    """Constrói o conteúdo da Home (banner + feed + resumo dinâmico)."""
    try:
        from mod_intranet import home_visual as _hv
        _hv.aplicar_modelo(modelo)
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

            # Feedback no carregamento: toast de boas-vindas (desaparece sozinho
            # no tempo configurado pelo admin — padrão 4s, `notificacao_timeout`)
            ui.timer(0.1, lambda: notificar(f"Bem-vindo(a), {nome}!",
                                            type="positive", position="top"),
                     once=True)

            # ---- Feed do Blog (RF-09) — logo abaixo do banner, sem título ----
            from mod_blog.telas import renderizar_postagens
            pode_publicar_blog = (perfil == "administrador_geral"
                                  or autenticacao.eh_admin_do_modulo(nome, "blog"))
            _feed_wrap = ui.column().classes("w-full gap-4")
            renderizar_postagens(_feed_wrap, nome, perfil,
                                 pode_publicar_blog,
                                 lambda: ui.navigate.reload())

            # ---- Resumo do sistema (somente administradores) ----
            # Fica abaixo das postagens. Sem botão
            # Atualizar — os dados são calculados automaticamente a cada acesso
            # (dinâmico), sem ação manual.
            # Dados para os Resumos — coletados uma vez (fail-soft 0)
            n_users = n_posts = n_logs = n_sessoes = n_acessos = n_fila = n_quar = n_pdf = n_24h = 0
            if eh_admin or _eh_autorizador_impressao(nome):
                try:
                    n_users, n_posts, n_logs, n_sessoes, n_acessos, n_fila, n_quar, n_pdf, n_24h = _orquestrar_resumo_dados()
                except Exception:
                    pass
            if eh_admin:
                from mod_intranet.tema_modulo import estilo_cartao as _estilo_cartao_fn2, ler_tema as _ler_tema_home
                from mod_intranet import home_visual as _hv2
                try:
                    _cor_modulo_home = (_ler_tema_home("intranet").get("cor_botao") or "#000000").strip() or "#000000"
                except Exception:
                    _cor_modulo_home = "#000000"
                with ui.card().classes(_hv2.classes_card_resumo(modelo)).style(
                        f"border-left-color:{_cor_modulo_home};box-shadow:6px 0 16px rgba(0,0,0,0.07);{_estilo_cartao_fn2()}"):
                    with ui.card_section().classes("gap-3 w-full"):
                        ui.label("Resumo do sistema").classes("text-h6 font-bold text-grey-9")
                        with ui.row().classes(_hv2.classes_wrap_resumo(modelo)):
                            _stat("Usuários ativos", n_users, "people", modelo=modelo)
                            _stat("Sessões ativas", n_sessoes, "sensors", modelo=modelo)
                            _stat("Acessos", n_acessos, "login", modelo=modelo)
                            _stat("Postagens", n_posts, "article", modelo=modelo)
                            _stat("Quarentena", n_quar, "warning", modelo=modelo)
                            _stat("PDFs", n_pdf, "picture_as_pdf", modelo=modelo)
                            _stat("Registros de auditoria", n_logs, "history", modelo=modelo)
                            _stat("Auditoria 24h", n_24h, "schedule", modelo=modelo)
            # Somente autorizador de impressão vê este card (admin geral também é autorizador implícito via perfil) — cor padronizada do módulo + sombra lateral direita
            if _eh_autorizador_impressao(nome) or perfil == "administrador_geral":
                from mod_intranet.tema_modulo import estilo_cartao as _estilo_cartao_fn2b, ler_tema as _ler_tema_home2
                from mod_intranet import home_visual as _hv2b
                n_para_autorizar = _contar_fila_para_autorizar(nome, eh_admin_geral=(perfil == "administrador_geral"))
                try:
                    _cor_modulo_home2 = (_ler_tema_home2("intranet").get("cor_botao") or "#000000").strip() or "#000000"
                except Exception:
                    _cor_modulo_home2 = "#000000"
                with ui.card().classes(_hv2b.classes_card_resumo(modelo)).style(
                        f"border-left-color:{_cor_modulo_home2};box-shadow:6px 0 16px rgba(0,0,0,0.07);{_estilo_cartao_fn2b()}"):
                    with ui.card_section().classes("gap-3 w-full"):
                        ui.label("Resumo do sistema — Impressão").classes("text-h6 font-bold text-grey-9")
                        with ui.row().classes(_hv2b.classes_wrap_resumo(modelo)):
                            _stat("Fila geral", n_fila, "print", modelo=modelo)
                            _stat("Para autorizar", n_para_autorizar, "rule", modelo=modelo)
    except Exception as e:
        observabilidade.get_logger("intranet").exception(
            "_construir_dashboard: erro ao renderizar a Home de '%s': %s", nome, e)
        notificar("Erro ao carregar a página inicial.", tipo="error")


def _eh_autorizador_impressao(nome: str) -> bool:
    """Verifica se o usuário é responsável por autorizar impressão (qualquer secretaria/setor)."""
    try:
        from mod_solicita_impressao.bd_manipulador import get_connection as _csol
        c = _csol()
        cur = c.cursor()
        cur.execute("SELECT 1 FROM tb_responsaveis_autorizacao WHERE user_nome=? AND ativo=1 LIMIT 1", (nome,))
        ok = cur.fetchone() is not None
        c.close()
        return ok
    except Exception:
        return False


def _contar_fila_para_autorizar(nome: str, eh_admin_geral: bool = False) -> int:
    """Conta solicitações pendentes que o usuário pode autorizar (por secretaria/setor)."""
    try:
        from mod_solicita_impressao.bd_manipulador import get_connection as _csol
        c = _csol()
        cur = c.cursor()
        # Admin geral pode autorizar tudo — conta igual à fila geral
        if eh_admin_geral:
            cur.execute("SELECT COUNT(*) FROM tb_solicitacoes WHERE status NOT IN ('impresso','recusado','cancelado')")
            n = cur.fetchone()[0]
            c.close()
            return n
        # Busca vínculos ativos do usuário
        cur.execute("SELECT secretaria_id, setor_id FROM tb_responsaveis_autorizacao WHERE user_nome=? AND ativo=1", (nome,))
        vins = cur.fetchall()
        if not vins:
            c.close()
            return 0
        total = 0
        for sec_id, set_id in vins:
            if set_id is None:
                cur.execute("SELECT COUNT(*) FROM tb_solicitacoes WHERE secretaria_id=? AND status NOT IN ('impresso','recusado','cancelado')", (sec_id,))
                total += cur.fetchone()[0]
            else:
                cur.execute("SELECT COUNT(*) FROM tb_solicitacoes WHERE secretaria_id=? AND (setor_id=? OR setor_id IS NULL) AND status NOT IN ('impresso','recusado','cancelado')", (sec_id, set_id))
                total += cur.fetchone()[0]
        c.close()
        return total
    except Exception:
        return 0


@ui.page("/")
def page_dashboard():
    try:
        from mod_intranet.telas import pagina_restrita
        user = pagina_restrita("Início")
        if not user:
            return
        # Resumo do sistema: só admin geral/modulo; Impressão: só autorizador (admin geral implícito)
        perfil = user.get("perfil", "")
        nome = user["nome"]
        eh_admin = perfil in ("administrador_geral", "administrador_modulo")
        _construir_dashboard(nome, perfil, eh_admin, modelo="water")
    except Exception as e:
        observabilidade.get_logger("intranet").exception(
            "page_dashboard: erro ao renderizar o dashboard: %s", e)
        notificar("Erro ao carregar a página inicial.", tipo="error")


# ================== MÓDULOS ==================
@ui.page("/blog")
def page_blog():
    try:
        from mod_intranet.telas import pagina_restrita
        user = pagina_restrita("Blog Corporativo", chave_modulo="blog")
        if not user:
            return
        from mod_blog.telas import mostrar_tela
        mostrar_tela(user["nome"], user.get("perfil", ""))
    except Exception as e:
        observabilidade.get_logger("intranet").exception(
            "page_blog: erro ao renderizar o Blog: %s", e)
        notificar("Erro ao carregar o Blog Corporativo.", tipo="error")


if rotas_modulos is not None:
    rotas_modulos.REGISTRO_MODULOS["blog"] = page_blog


@ui.page("/users")
def page_users():
    try:
        from mod_intranet.telas import pagina_restrita
        user = pagina_restrita("Gestão de Usuários", chave_modulo="usuarios")
        if not user:
            return
        from mod_gest_cad_usuario.telas import mostrar_tela
        mostrar_tela(user["nome"], user.get("perfil", ""))
    except Exception as e:
        observabilidade.get_logger("intranet").exception(
            "page_users: erro ao renderizar a Gestão de Usuários: %s", e)
        notificar("Erro ao carregar a Gestão de Usuários.", tipo="error")


if rotas_modulos is not None:
    rotas_modulos.REGISTRO_MODULOS["usuarios"] = page_users


@ui.page("/auditoria")
def page_auditoria():
    try:
        from mod_intranet.telas import pagina_restrita
        user = pagina_restrita("Auditoria", chave_modulo="auditoria")
        if not user:
            return
        from mod_auditoria.telas import mostrar_tela
        mostrar_tela(user["nome"], user.get("perfil", ""))
    except Exception as e:
        observabilidade.get_logger("intranet").exception(
            "page_auditoria: erro ao renderizar a Auditoria: %s", e)
        notificar("Erro ao carregar a Auditoria.", tipo="error")


if rotas_modulos is not None:
    rotas_modulos.REGISTRO_MODULOS["auditoria"] = page_auditoria


@ui.page("/edit-pdf")
def page_edit_pdf():
    try:
        from mod_intranet.telas import pagina_restrita
        user = pagina_restrita("Editor de PDF", chave_modulo="editar_pdf")
        if not user:
            return
        from mod_edit_pdf.telas import mostrar_tela
        mostrar_tela(user["nome"], user.get("perfil", ""))
    except Exception as e:
        observabilidade.get_logger("intranet").exception(
            "page_edit_pdf: erro ao renderizar o Editor de PDF: %s", e)
        notificar("Erro ao carregar o Editor de PDF.", tipo="error")


if rotas_modulos is not None:
    rotas_modulos.REGISTRO_MODULOS["editar_pdf"] = page_edit_pdf


@ui.page("/renomear-empenho")
def page_renomear_empenho():
    try:
        from mod_intranet.telas import pagina_restrita
        user = pagina_restrita("Renomear Empenhos", chave_modulo="empenhos")
        if not user:
            return
        from mod_renomear_empenho.telas import mostrar_tela
        mostrar_tela(user["nome"], user.get("perfil", ""))
    except Exception as e:
        observabilidade.get_logger("intranet").exception(
            "page_renomear_empenho: erro ao renderizar Renomear Empenhos: %s", e)
        notificar("Erro ao carregar Renomear Empenhos.", tipo="error")


# Comparativo visual — pic padrão + uma tela por CSS novo (12)
def _page_empenho_forcado(modelo: str, titulo: str):
    from mod_renomear_empenho import visual as _visual_cmp
    _orig = _visual_cmp.FORCAR_MODELO
    _visual_cmp.FORCAR_MODELO = modelo
    try:
        from mod_intranet.telas import pagina_restrita
        user = pagina_restrita(titulo, chave_modulo="empenhos")
        if not user:
            return
        from mod_renomear_empenho.telas import mostrar_tela
        mostrar_tela(user["nome"], user.get("perfil", ""))
    except Exception as e:
        observabilidade.get_logger("intranet").exception(
            "_page_empenho_forcado: erro ao renderizar '%s': %s", titulo, e)
        notificar(f"Erro ao carregar {titulo}.", tipo="error")
    finally:
        _visual_cmp.FORCAR_MODELO = _orig

@ui.page("/renomear-empenho-pic")
def page_renomear_empenho_pic():
    return _page_empenho_forcado("pic", "Renomear Empenhos — PIC")

@ui.page("/renomear-empenho-spectre")
def page_renomear_empenho_spectre():
    return _page_empenho_forcado("spectre", "Renomear Empenhos — Spectre")

@ui.page("/renomear-empenho-chota")
def page_renomear_empenho_chota():
    return _page_empenho_forcado("chota", "Renomear Empenhos — Chota")

@ui.page("/renomear-empenho-milligram")
def page_renomear_empenho_milligram():
    return _page_empenho_forcado("milligram", "Renomear Empenhos — Milligram")

@ui.page("/renomear-empenho-skeleton")
def page_renomear_empenho_skeleton():
    return _page_empenho_forcado("skeleton", "Renomear Empenhos — Skeleton")

@ui.page("/renomear-empenho-water")
def page_renomear_empenho_water():
    return _page_empenho_forcado("water", "Renomear Empenhos — Water")

@ui.page("/renomear-empenho-mvp")
def page_renomear_empenho_mvp():
    return _page_empenho_forcado("mvp", "Renomear Empenhos — MVP")

@ui.page("/renomear-empenho-tachyons")
def page_renomear_empenho_tachyons():
    return _page_empenho_forcado("tachyons", "Renomear Empenhos — Tachyons")

@ui.page("/renomear-empenho-uikit")
def page_renomear_empenho_uikit():
    return _page_empenho_forcado("uikit", "Renomear Empenhos — UIkit")

@ui.page("/renomear-empenho-foundation")
def page_renomear_empenho_foundation():
    return _page_empenho_forcado("foundation", "Renomear Empenhos — Foundation")

@ui.page("/renomear-empenho-semantic")
def page_renomear_empenho_semantic():
    return _page_empenho_forcado("semantic", "Renomear Empenhos — Semantic")

@ui.page("/renomear-empenho-materialize")
def page_renomear_empenho_materialize():
    return _page_empenho_forcado("materialize", "Renomear Empenhos — Materialize")

@ui.page("/renomear-empenho-primer")
def page_renomear_empenho_primer():
    return _page_empenho_forcado("primer", "Renomear Empenhos — Primer")


if rotas_modulos is not None:
    rotas_modulos.REGISTRO_MODULOS["empenhos"] = page_renomear_empenho


@app.get("/solicita-impressao/pdf/{solicitacao_id}")
def baixar_pdf_impressao(solicitacao_id: int):
    """Rota de download do PDF da solicitação (com marca d'água se ativa).

    Protegida: exige autenticação e permissão sobre a solicitação (solicitante,
    responsável pelo vínculo da secretaria/setor ou administrador do módulo).
    """
    try:
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
    except Exception as e:
        observabilidade.get_logger("intranet").exception(
            "baixar_pdf_impressao: falha ao servir o PDF %s: %s", solicitacao_id, e)
        return Response(status_code=500)


@ui.page("/solicita-impressao")
def page_solicita_impressao():
    try:
        from mod_intranet.telas import pagina_restrita
        user = pagina_restrita("Solicitação de Impressão", chave_modulo="solicita_impressao")
        if not user:
            return
        from mod_solicita_impressao.telas import mostrar_tela
        mostrar_tela(user["nome"], user.get("perfil", ""))
        # Carrega o JS de impressão (listar/imprimir via cliente)
        ui.add_head_html('<script src="/solicita-impressao/src/impressao.js"></script>')
    except Exception as e:
        observabilidade.get_logger("intranet").exception(
            "page_solicita_impressao: erro ao renderizar a Solicitação de Impressão: %s", e)
        notificar("Erro ao carregar a Solicitação de Impressão.", tipo="error")


if rotas_modulos is not None:
    rotas_modulos.REGISTRO_MODULOS["solicita_impressao"] = page_solicita_impressao


@ui.page("/tecnico")
def page_tecnico():
    try:
        from mod_intranet.telas import pagina_restrita
        user = pagina_restrita("Técnico", chave_modulo="tecnico")
        if not user:
            return
        from mod_tecnico.telas import mostrar_tela
        mostrar_tela(user["nome"], user.get("perfil", ""))
    except Exception as e:
        observabilidade.get_logger("intranet").exception(
            "page_tecnico: erro ao renderizar o módulo Técnico: %s", e)
        notificar("Erro ao carregar o módulo Técnico.", tipo="error")


if rotas_modulos is not None:
    rotas_modulos.REGISTRO_MODULOS["tecnico"] = page_tecnico


@ui.page("/filas")
def page_filas():
    try:
        from mod_intranet.telas import pagina_restrita
        user = pagina_restrita("Filas", chave_modulo="filas")
        if not user:
            return
        from mod_filas.telas import mostrar_tela
        mostrar_tela(user["nome"], user.get("perfil", ""))
    except Exception as e:
        observabilidade.get_logger("intranet").exception(
            "page_filas: erro ao renderizar o módulo Filas: %s", e)
        notificar("Erro ao carregar o módulo Filas.", tipo="error")


if rotas_modulos is not None:
    rotas_modulos.REGISTRO_MODULOS["filas"] = page_filas


@ui.page("/tv")
def page_tv():
    # TV de chamadas — acesso livre na rede (sem login), suporta ?grupo=xxx para TV compartilhada e /tv/{id} para isolada
    try:
        from mod_filas.telas import mostrar_tv
        # query param grupo para TV compartilhada
        try:
            from nicegui import context as _ctx
            grupo = None
            etapa = None
            try:
                grupo = _ctx.client.request.query_params.get("grupo")
                etapa = _ctx.client.request.query_params.get("etapa")
            except Exception:
                grupo = None
            if grupo:
                mostrar_tv(tv_grupo=grupo, etapa=etapa)
                return
            if etapa:
                mostrar_tv(etapa=etapa)
                return
        except Exception as e:
            observabilidade.get_logger("intranet").exception(
                "page_tv: falha ao obter parâmetros da TV: %s", e)
        mostrar_tv()
    except Exception as e:
        observabilidade.get_logger("intranet").exception(
            "page_tv: erro ao renderizar a TV: %s", e)
        notificar("Erro ao carregar a TV de chamadas.", tipo="error")


@ui.page("/tv/{fila_id}")
def page_tv_fila(fila_id: int):
    # TV isolada por fila (não interfere em outra) — também resolve grupo compartilhado se fila pertence a grupo
    try:
        from mod_filas.telas import mostrar_tv
        try:
            from nicegui import context as _ctx
            etapa = _ctx.client.request.query_params.get("etapa")
        except Exception:
            etapa = None
        mostrar_tv(fila_id=fila_id, etapa=etapa)
    except Exception as e:
        observabilidade.get_logger("intranet").exception(
            "page_tv_fila: erro ao renderizar a TV da fila %s: %s", fila_id, e)
        notificar("Erro ao carregar a TV da fila.", tipo="error")


@ui.page("/lista-telefonica")
def page_lista_telefonica():
    try:
        from mod_intranet.telas import pagina_restrita
        user = pagina_restrita("Lista Telefônica", chave_modulo="lista_telefonica")
        if not user:
            return
        from mod_lista_telefonica.telas import mostrar_tela
        mostrar_tela(user["nome"], user.get("perfil", ""))
    except Exception as e:
        observabilidade.get_logger("intranet").exception(
            "page_lista_telefonica: erro ao renderizar a Lista Telefônica: %s", e)
        notificar("Erro ao carregar a Lista Telefônica.", tipo="error")


if rotas_modulos is not None:
    rotas_modulos.REGISTRO_MODULOS["lista_telefonica"] = page_lista_telefonica


@ui.page("/agregador-noticias")
def page_agregador_noticias():
    try:
        from mod_intranet.telas import pagina_restrita
        user = pagina_restrita("Agregador de Notícias", chave_modulo="agregador_noticias")
        if not user:
            return
        from mod_agregador_noticias.telas import mostrar_tela
        mostrar_tela(user["nome"], user.get("perfil", ""))
    except Exception as e:
        observabilidade.get_logger("intranet").exception(
            "page_agregador_noticias: erro ao renderizar o Agregador de Notícias: %s", e)
        notificar("Erro ao carregar o Agregador de Notícias.", tipo="error")


if rotas_modulos is not None:
    rotas_modulos.REGISTRO_MODULOS["agregador_noticias"] = page_agregador_noticias


@ui.page("/agregador-noticias-puro")
def page_agregador_noticias_puro():
    try:
        from mod_intranet.telas import pagina_restrita
        user = pagina_restrita("Agregador de Notícias — Puro", chave_modulo="agregador_noticias")
        if not user:
            return
        from mod_agregador_noticias.telas_puro import mostrar_tela_pura
        mostrar_tela_pura(user["nome"], user.get("perfil", ""))
    except Exception as e:
        observabilidade.get_logger("intranet").exception(
            "page_agregador_noticias_puro: erro ao renderizar o Agregador puro: %s", e)
        notificar("Erro ao carregar o Agregador de Notícias.", tipo="error")


@app.get("/api/attachments/{caminho:path}")
def fallback_attachments(caminho: str):
    """EN: Fallback for broken /api/attachments/* exported from Trello/Notion.
    Serves assets/noticia/favicon.png as visual placeholder when path ends with
    -w280-h168-p-df/.png/.jpg/.jpeg, otherwise 404. Inserted BEFORE
    /assets/noticia route to avoid log spam of 'http://localhost:8080/api/attachments/CC8... not found' seen on boot (NiceGUI ready). Silent fallback, TV and Blog never attempt to load broken external attachments.

    PT-BR: Fallback 404 para /api/attachments/* quebrado de export Trello/Notion no conteúdo do Blog/Agregador.
    Evita log spam de 'http://localhost:8080/api/attachments/CC8... not found' que aparecia no boot (NiceGUI ready) e serve placeholder visual favicon.png quando o caminho termina em -w280-h168-p-df/.png/.jpg/.jpeg; caso contrário 404. Inserido ANTES de /assets/noticia. Requisitos: TV e Blog não tentam carregar attachments externos quebrados; fallback silencioso, compatível, sem quebrar coleta, sem log spam, com placeholder visual."""
    try:
        # opcional: placeholder transparente 1x1
        # tenta servir assets/noticia/favicon.png como fallback visual se for imagem
        if caminho.endswith(("-w280-h168-p-df", "-w280-h168", ".png", ".jpg", ".jpeg")):
            base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "noticia")
            placeholder = os.path.join(base, "favicon.png")
            if os.path.isfile(placeholder):
                return FileResponse(placeholder, media_type="image/png")
        return Response(status_code=404)
    except Exception as e:
        observabilidade.get_logger("intranet").exception(
            "fallback_attachments: erro ao servir attachment '%s': %s", caminho, e)
        return Response(status_code=404)


@app.get("/assets/noticia/{caminho:path}")
def servir_assets_noticia(caminho: str):
    try:
        base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "noticia")
        # segurança: normaliza e garante dentro da base
        caminho_abs = os.path.normpath(os.path.join(base, caminho))
        if not caminho_abs.startswith(os.path.abspath(base)):
            return Response(status_code=404)
        if not os.path.isfile(caminho_abs):
            return Response(status_code=404)
        # tipo MIME básico
        import mimetypes
        mime, _ = mimetypes.guess_type(caminho_abs)
        mime = mime or "application/octet-stream"
        return FileResponse(caminho_abs, media_type=mime)
    except Exception as e:
        observabilidade.get_logger("intranet").exception(
            "servir_assets_noticia: erro ao servir asset '%s': %s", caminho, e)
        return Response(status_code=404)


@app.get("/solicita-impressao/src/impressao.js")
def servir_js_impressao():
    try:
        caminho = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "mod_solicita_impressao", "src", "impressao.js")
        with open(caminho, "r", encoding="utf-8") as f:
            conteudo = f.read()
        return Response(content=conteudo, media_type="application/javascript")
    except Exception as e:
        observabilidade.get_logger("intranet").exception(
            "servir_js_impressao: erro ao servir impressao.js: %s", e)
        return Response(status_code=404)


@ui.page("/admin/{chave_modulo}")
def page_admin_modulo(chave_modulo: str):
    """Renders the standalone administration panel for a given module.

    Rota dedicada para a administração de cada módulo: quando o usuário
    clica em 'Administração' no menu hambúrguer, é direcionado para
    `/admin/{chave_modulo}` que mostra apenas a tela de configuração
    daquele módulo, sem as abas de navegação normais."""
    try:
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

        elif chave_modulo == "tecnico":
            eh_admin = (perfil == "administrador_geral"
                        or autenticacao.eh_admin_do_modulo(nome, "tecnico"))
            from mod_tecnico.telas_administracao import mostrar_administracao
            from mod_intranet.tema_modulo import ler_tema
            ui.colors(primary=ler_tema("tecnico", cor_botao="#000000")["cor_botao"])
            mostrar_administracao(nome)

        elif chave_modulo == "filas":
            eh_admin = (perfil == "administrador_geral"
                        or autenticacao.eh_admin_do_modulo(nome, "filas"))
            from mod_filas.telas_administracao import mostrar_administracao
            from mod_intranet.tema_modulo import ler_tema
            ui.colors(primary=ler_tema("filas", cor_botao="#000000")["cor_botao"])
            mostrar_administracao(nome)

        elif chave_modulo == "lista_telefonica":
            eh_admin = (perfil == "administrador_geral"
                        or autenticacao.eh_admin_do_modulo(nome, "lista_telefonica"))
            from mod_lista_telefonica.telas_administracao import mostrar_administracao
            from mod_intranet.tema_modulo import ler_tema
            ui.colors(primary=ler_tema("lista_telefonica", cor_botao="#000000")["cor_botao"])
            # admin requer papel; se não for admin, mostra aviso e redireciona para visual
            if not eh_admin:
                ui.notify("Acesso restrito a administradores", type="negative")
                ui.navigate.to("/lista-telefonica")
            else:
                mostrar_administracao(nome)

        elif chave_modulo == "agregador_noticias":
            eh_admin = (perfil == "administrador_geral"
                        or autenticacao.eh_admin_do_modulo(nome, "agregador_noticias"))
            from mod_agregador_noticias.telas_administracao import mostrar_administracao
            from mod_intranet.tema_modulo import ler_tema
            ui.colors(primary=ler_tema("agregador_noticias", cor_botao="#000000")["cor_botao"])
            if not eh_admin:
                ui.notify("Acesso restrito a administradores", type="negative")
                ui.navigate.to("/agregador-noticias")
            else:
                mostrar_administracao(nome)

        else:
            ui.navigate.to("/configuracoes")
    except Exception as e:
        observabilidade.get_logger("intranet").exception(
            "page_admin_modulo: erro ao renderizar a administração de '%s': %s", chave_modulo, e)
        notificar("Erro ao carregar a administração do módulo.", tipo="error")


@ui.page("/configuracoes")
def page_configuracoes():
    try:
        from mod_intranet.telas import pagina_restrita
        user = pagina_restrita("Administração")
        if not user:
            return
        from mod_intranet.tela_configuracoes import mostrar_tela
        mostrar_tela(user["nome"], user.get("perfil", ""))
    except Exception as e:
        observabilidade.get_logger("intranet").exception(
            "page_configuracoes: erro ao renderizar as Configurações: %s", e)
        notificar("Erro ao carregar as Configurações.", tipo="error")


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
    try:
        observabilidade.registrar_excecoes_nicegui(app)
    except Exception as _e_nice:
        print(f"[observabilidade] falha ao registrar rede NiceGUI: {_e_nice}")

    # Passos de boot com barra de progresso no terminal
    def _passo_agendador():
        return iniciar_agendador()

    def _passo_docs():
        try:
            from mod_intranet.documentacao import (
                construir_e_montar_documentacao,
                iniciar_servidor, habilitada_no_boot,
            )
            if not habilitada_no_boot():
                print("[documentacao] Desativada (docs_ativo=0) — pulando build/servidor no boot")
                return True
            construir_e_montar_documentacao(
                porta=_cfg.get("porta_documentacao", 8000))
            iniciar_servidor(_cfg.get("porta_documentacao", 8000))
        except Exception as e:
            observabilidade.get_logger("intranet").exception(
                "_passo_docs: falha ao construir/iniciar a documentação: %s", e)
            raise

    ativacao.progresso_boot([
        ("Agendadores (backup/limpeza/monitor)", _passo_agendador),
        (f"Documentação MkDocs (http://localhost:"
         f"{_cfg.get('porta_documentacao', 8000)})", _passo_docs),
    ])

    observabilidade.get_logger().info("Intranet iniciada (boot concluído)")

    # ================== SHUTDOWN GRACIOSO ==================
    # Ordem: agendador (para os jobs) -> docs -> OTel. Idempotente e
    # fail-soft — falha em uma etapa nunca impede as seguintes. O caminho
    # efetivo é o `atexit` (o uvicorn substitui os handlers de sinal ao
    # subir o servidor); os handlers abaixo valem como melhor esforço.
    def _encerrar():
        try:
            print("[shutdown] atexit: encerrando processo", flush=True)
        except Exception:
            pass
        try:
            observabilidade.get_logger("intranet").info("atexit: encerrando processo")
        except Exception:
            pass
        try:
            from mod_intranet import rotinas
            if rotinas.encerrar_agendador():
                print("[shutdown] Agendador encerrado")
        except Exception as e:
            print(f"[shutdown] Aviso ao encerrar agendador: {e}")
        try:
            from mod_intranet.documentacao import parar_servidor
            if parar_servidor():
                print("[shutdown] Servidor de documentação encerrado")
        except Exception as e:
            print(f"[shutdown] Aviso ao parar documentação: {e}")
        try:
            from mod_intranet.otel_integracao import finalizar_otel
            finalizar_otel()
        except Exception:
            pass

    import atexit as _atexit
    import signal as _signal
    _atexit.register(_encerrar)

    def _ao_sinal(*_args):
        try:
            print(f"[sinal] sinal recebido ({_args[0] if _args else '?'}) — encerrando", flush=True)
        except Exception:
            pass
        try:
            observabilidade.get_logger("intranet").warning(
                f"sinal recebido ({_args[0] if _args else '?'}) — encerrando")
        except Exception:
            pass
        try:
            _encerrar()
        except Exception as e:
            observabilidade.get_logger("intranet").exception(
                "_ao_sinal: falha ao encerrar a aplicação: %s", e)
        os._exit(0)

    for _s in (_signal.SIGINT, _signal.SIGTERM):
        try:
            _signal.signal(_s, _ao_sinal)
        except Exception:
            pass

    ui.run(
        title=get_config("texto_login_titulo", "INTRANET Básica") or "INTRANET Básica",
        favicon="assets/favicon_atual.ico",  # arquivo vivo: upload troca sem restart
        storage_secret=os.environ.get("INTRANET_STORAGE_SECRET")
        or "intranet-secret-2026-mude-isto",  # trocar via env em produção
        reload=False,
        port=_cfg.get("porta_site", 8080),
        show=False,
    )
