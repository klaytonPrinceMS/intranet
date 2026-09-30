"""4-part system layout: header, drawer, content and footer.

Layout de 4 partes do sistema: header, drawer, conteúdo e footer.

Uso dentro de uma função @ui.page:

    from mod_intranet.telas import pagina_restrita

    @ui.page("/blog")
    def page_blog():
        usuario = pagina_restrita("Blog", chave_modulo="blog")
        if not usuario:
            return
        # ... construir conteúdo
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from nicegui import ui, app, run

from mod_intranet import autenticacao
from mod_intranet import ui_comum
from mod_intranet.bd_conexao import get_config as _obter_config
from mod_intranet.tema_modulo import botao as _botao_tema
from mod_intranet.tema_modulo import notificar

# Logger do fluxo de LOGIN/troca de credenciais. A função (e não uma
# constante) porque é resolvida no 1º uso e memorizada: os call sites já
# usavam `_login_erro_log()`, que nunca foi definida — o NameError caía no
# `except Exception: pass` e TODOS os erros de login sumiam sem log.
_login_erro_logger = None


def _login_erro_log():
    """EN: Returns the login-flow logger (loguru, fail-soft).

    PT-BR: Retorna o logger do fluxo de login (loguru, fail-soft).

    Memoriza o logger na primeira chamada. Nunca levanta: se a observabilidade
    falhar, devolve o logger padrão do loguru para o `except` do chamador
    seguir funcionando."""
    global _login_erro_logger
    if _login_erro_logger is None:
        try:
            from mod_intranet import observabilidade as _obs
            _login_erro_logger = _obs.get_logger("intranet")
        except Exception:
            try:
                from loguru import logger as _logger_padrao
                _login_erro_logger = _logger_padrao
            except Exception:
                return None
    return _login_erro_logger


def usuario_logado():
    """Returns the session user dict or None.

    Retorna o dict do usuário da sessão ou None."""
    return app.storage.user.get("usuario")


def pagina_restrita(titulo_modulo: str, chave_modulo: str = None):
    """Guard de autenticação + layout completo. Retorna dict do usuário ou None.

    Se não autenticado, redireciona para /login.
    """
    user = usuario_logado()
    if not user:
        ui.navigate.to("/login")
        return None

    # Revalida contra o BD a cada request: bloqueio/exclusão/renomeio derrubam a sessão viva
    linha_bd = autenticacao.usuario_existe(user.get("nome", ""))
    if not linha_bd or not linha_bd[2]:
        app.storage.user.clear()
        notificar("Sua sessão foi encerrada pelo administrador.", type="warning")
        ui.navigate.to("/login")
        return None

    # Sessão revogável: se o admin encerrou esta sessão no banco, o navegador cai
    hash_sessao = user.get("sessao")
    if hash_sessao:
        if not autenticacao.sessao_ativa(user["nome"], hash_sessao):
            app.storage.user.clear()
            notificar("Sua sessão foi encerrada pelo administrador.", type="warning")
            ui.navigate.to("/login")
            return None
    else:
        # Sessões anteriores à rastreabilidade não têm hash amarrado:
        # adota agora (nova linha com IP/UA deste acesso) e passa a ser revogável
        user["sessao"] = autenticacao.registrar_login(user["nome"], "sistema")
        app.storage.user["usuario"] = user

    papel_mod = autenticacao.papel_no_modulo(user["nome"], chave_modulo) if chave_modulo else None
    rotulo_perfil = f"{papel_mod.replace('_', ' ')} · neste módulo" if papel_mod \
        else user.get("perfil", "comum").replace("_", " ")

    # Bloqueio de acesso por módulo: impede navegação direta por URL de quem não
    # tem permissão (ex.: usuário comum acessando /auditoria). Check centralizado
    # aqui vale para todas as rotas que passam chave_modulo. Como passa por aqui
    # apenas usuários autenticados, o registro de 'acesso_negado' não polui com
    # bots/curl (tentativa de quem realmente tem conta).
    if chave_modulo and not autenticacao.validar_acesso_modulo(user["nome"], chave_modulo):
        try:
            from mod_intranet.bd_manipulador import audit_log
            audit_log(user["nome"], chave_modulo, "acesso_negado",
                      f"tentou abrir o módulo '{chave_modulo}' sem permissão")
        except Exception:
            pass
        notificar("Acesso negado a este módulo.", type="negative")
        ui.navigate.to("/")
        return None

    _montar_layout(user["nome"], rotulo_perfil, titulo_modulo, chave_modulo)

    try:
        # Primeiro acesso: senha -> telefones. `_primeiro_acesso` encadeia os
        # dois passos e só abre o segundo quando o primeiro foi concluído.
        _primeiro_acesso(user["nome"])
    except Exception as _e_troca:
        try:
            _login_erro_log().exception(
                f"pagina_restrita: falha ao abrir troca obrigatória de '{user.get('nome','')}': {_e_troca}")
        except Exception:
            pass
        try:
            notificar("Erro ao abrir a troca obrigatória — recarregue a página.", tipo="error")
        except Exception:
            pass

    return user


def _aplicar_tema_escuro(escuro: bool, chave_modulo: str = None):
    """Applies the user's dark-theme override (per-user, non-global).

    Aplica o tema escuro individual: ativa o dark mode do Quasar e injeta CSS
    com uma paleta em variáveis, na ordem MAIS ESCURO → MAIS CLARO (do que está
    mais ao fundo para o que está mais à frente):
      cor geral do módulo → fundo da página → fundo do card → cor do título →
      texto do módulo → texto do card. O tema claro (light) é o padrão — as
      cores escolhidas pelos administradores."""
    if not escuro:
        return
    try:
        ui.dark_mode(True)
    except Exception:
        pass
    from mod_intranet import tema_modulo
    tema = tema_modulo.ler_tema(chave_modulo or "intranet")
    p = tema_modulo.paleta_escura(tema)
    ui.query("body").classes("intranet-dark")
    ui.add_head_html(f"""<style>
body.intranet-dark {{
  --cor-geral: {p['cor_geral']};
  --fundo-pagina: {p['fundo_pagina']};
  --fundo-card: {p['fundo_card']};
  --cor-titulo: {p['cor_titulo']};
  --texto-modulo: {p['texto_modulo']};
  --texto-card: {p['texto_card']};
}}
body.intranet-dark {{ background: var(--fundo-pagina) !important; }}
body.intranet-dark .q-page {{ background-color: var(--fundo-pagina) !important; color: var(--texto-modulo); }}
body.intranet-dark .q-card,
body.intranet-dark .q-drawer,
body.intranet-dark .q-dialog,
body.intranet-dark .q-menu,
body.intranet-dark .q-expansion-item__content,
body.intranet-dark .q-table {{ background-color: var(--fundo-card) !important; color: var(--texto-card); }}
body.intranet-dark .q-footer {{ background-color: #1a1a1a !important; }}
body.intranet-dark .bg-white {{ background-color: var(--fundo-card) !important; }}
body.intranet-dark .bg-grey-1,
body.intranet-dark .bg-grey-2,
body.intranet-dark .bg-grey-3 {{ background-color: var(--fundo-pagina) !important; }}
body.intranet-dark .cabecalho-titulo {{ color: var(--cor-titulo) !important; }}
body.intranet-dark .text-grey-9,
body.intranet-dark .text-grey-8,
body.intranet-dark .text-grey-7,
body.intranet-dark .text-black {{ color: var(--texto-modulo) !important; }}
body.intranet-dark .q-card .text-grey-9,
body.intranet-dark .q-card .text-grey-8,
body.intranet-dark .q-card .text-grey-7,
body.intranet-dark .q-card .text-black {{ color: var(--texto-card) !important; }}
body.intranet-dark .text-grey-6,
body.intranet-dark .text-grey-5,
body.intranet-dark .text-grey-4,
body.intranet-dark .text-caption {{ color: var(--texto-modulo) !important; }}
body.intranet-dark .q-field--outlined .q-field__control,
body.intranet-dark .q-input,
body.intranet-dark .q-textarea,
body.intranet-dark .q-select,
body.intranet-dark .q-number {{ background-color: var(--fundo-card) !important; color: var(--texto-card); }}
body.intranet-dark input,
body.intranet-dark textarea {{ color: var(--texto-card) !important; }}
body.intranet-dark .q-field__label {{ color: var(--texto-modulo) !important; }}
body.intranet-dark .q-item,
body.intranet-dark .q-tab {{ color: var(--texto-modulo) !important; }}
body.intranet-dark .q-separator {{ background-color: #3f3f3f !important; }}
body.intranet-dark .q-chip {{ background-color: var(--fundo-card) !important; color: var(--texto-card); }}
</style>
""")


def _alternar_tema(user_nome: str):
    """Toggles the current user's dark/light theme preference (individual)."""
    novo = not autenticacao.tema_escuro(user_nome)
    autenticacao.definir_tema_escuro(user_nome, novo)
    ui.timer(0.1, lambda: ui.navigate.reload(), once=True)


def _montar_layout(nome_usuario: str, rotulo_perfil: str, titulo_modulo: str,
                    chave_modulo: str = None):
    """Builds the 4-part layout (header, drawer, content and footer).

    Monta o layout de 4 partes: header, drawer lateral, conteúdo e rodapé,
    aplicando cor principal, fundo, título do sistema e versões no rodapé.
    Espaçamentos via `.style("gap: …")` (visual 1:1, bug #2171/Ubuntu).
    """
    cores = _obter_cor_principal()
    # Estilo visual em vigor: a ESCOLHA deste navegador (cookie). Vazio
    # significa "Padrão" — e aí NENHUM estilo é imposto, para a cor que o
    # administrador deste módulo configurou aparecer como está. Precisa ser
    # resolvido e aplicado ANTES do cabeçalho: quando há estilo, ele redefine
    # `--q-primary`, que é a cor do cabeçalho e de todo elemento `bg-primary`.
    estilo_visual_usuario = ""
    try:
        from mod_intranet import preview_estilos as _pv_estilos
        estilo_visual_usuario = _pv_estilos.estilo_efetivo()
        if estilo_visual_usuario:
            _pv_estilos.aplicar(estilo_visual_usuario, cor_principal=cores)
    except Exception:
        try:
            import logging
            logging.getLogger(__name__).exception(
                "telas: falha ao aplicar o estilo visual")
        except Exception:
            pass
    ui.colors(primary=cores, secondary=ui_comum.CORES["cinza_escuro"],
              accent=cores)
    fundo = _obter_config('cor_fundo', ui_comum.CORES["fundo"]) \
        or ui_comum.CORES["fundo"]
    ui.query("body").classes("bg-grey-2")
    ui.query("body").style(f"background:{fundo}")
    try:
        # O Quasar pinta .q-page por cima do body: sem isso o cor_fundo
        # configurado nunca aparece na área do conteúdo.
        ui.query(".q-page").style(f"background-color:{fundo}")
    except Exception:
        pass
    # Tema escuro individual do usuário (não afeta os demais).
    _aplicar_tema_escuro(autenticacao.tema_escuro(nome_usuario), chave_modulo)
    titulo_sistema = _obter_config("titulo_sistema", "INTRANET") or "INTRANET"
    icone_sistema = (_obter_config("icone_sistema", "hub") or "hub").strip()
    # Título da ABA do navegador acompanha o nome configurado.
    # Exceção intencional de "sem JS direto": via `ui.run_javascript` (API
    # oficial do NiceGUI), pois `ui.page(title=...)` é fixo por rota.
    import json as _json
    ui.run_javascript(f"document.title = {_json.dumps(titulo_sistema)}")
    # favicon com cache-busting: ?v muda quando o .ico é trocado
    from mod_intranet.bd_conexao import favicon_versao
    ui.add_head_html(
        f'<link rel="icon" type="image/x-icon" href="/favicon.ico?v={favicon_versao()}">')
    # Título da página vem do cadastro de módulos (editável em Configurações)
    if chave_modulo:
        nome_cadastrado = autenticacao.nome_do_modulo(chave_modulo)
        if nome_cadastrado:
            titulo_modulo = nome_cadastrado

    # ===== HEADER (parte 1) =====
    with ui.header(elevated=True).classes("w-full bg-primary px-3 sm:px-4 py-1").style("min-width: 0"):
        with ui.row().classes("w-full items-center justify-between flex-wrap").style("gap: 0.5rem; min-width: 0"):
            with ui.row().classes("items-center flex-wrap flex-1").style("gap: 0.5rem; min-width: 0"):
                _btn_menu = ui_comum.botao_icone("menu", on_click=lambda: drawer.toggle(),
                                     variante="icone_branco",
                                     tooltip="Abrir menu de navegação")
                if _btn_menu is not None:
                    _btn_menu.props('data-testid=menu-hamburguer aria-label="Abrir menu de navegação"')
                ui.icon(icone_sistema).classes("text-white shrink-0")
                ui.label(titulo_sistema).classes("text-h6 text-white font-bold whitespace-nowrap")
                ui.separator().props("vertical")
                ui.label(titulo_modulo).classes("text-subtitle2 text-white opacity-90 flex-1").style("min-width: 8ch; overflow-wrap: anywhere")
            with ui.row().classes("items-center flex-wrap justify-end flex-1").style("gap: 0.5rem; min-width: 0"):
                # Nome de TRATAMENTO clicável -> Meu Perfil (nome completo ou social).
                # Um único botão sempre visível: ellipsis à direita + tooltip completo.
                # (Sem toggles `hidden sm:*` — o tailwind embutido resolve `hidden`
                #  acima do `sm:flex`, então o botão sumia em qualquer largura.)
                # O conteúdo interno do q-btn é centralizado (`justify-content:center`),
                # então o CSS escopado abaixo ancora o texto à esquerda com ellipsis.
                try:
                    ui.add_head_html("""
<style>
/* Header — nome do usuário ancorado à esquerda com ellipsis à direita */
[data-testid="header-nome-usuario"] .q-btn__content{justify-content:flex-start !important;overflow:hidden}
[data-testid="header-nome-usuario"] .q-btn__content>span{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
</style>
""")
                except Exception:
                    pass
                trat = autenticacao.nome_de_tratamento(nome_usuario)
                _btn_nome = ui_comum.botao(trat, variante="texto_branco",
                               on_click=lambda: _dialogo_meu_perfil(nome_usuario),
                               tooltip=trat)
                if _btn_nome is not None:
                    _btn_nome.props('data-testid=header-nome-usuario')
                    _btn_nome.classes("min-w-0 overflow-hidden whitespace-nowrap").style("min-width: 0; max-width: min(28ch, 55vw); overflow: hidden; text-overflow: ellipsis;")
                # Tema claro/escuro (preferência individual do usuário)
                escuro_atual = autenticacao.tema_escuro(nome_usuario)
                ui_comum.botao_icone(
                    "dark_mode" if escuro_atual else "light_mode",
                    on_click=lambda: _alternar_tema(nome_usuario),
                    variante="icone_branco",
                    tooltip="Tema atual: "
                            + ("escuro" if escuro_atual else "claro")
                            + " — clique para alternar (só para você)")
                ui.badge(rotulo_perfil, color="primary-4").props("outline").classes("max-w-[12ch] truncate shrink-0").style("min-width: 0")
                ui_comum.botao_icone("logout", _logout, variante="icone_branco",
                                     tooltip="Sair")

    # ===== DRAWER/SIDEBAR (parte 2) =====
    # Por padrão o drawer abre FECHADO — o usuário abre via botão hambúrguer.
    # Visual Bootstrap list-group SEM injeção global: o Bootstrap local
    # (assets/css/frameworks/bootstrap@5.3.8.min.css, servido em
    # /css/frameworks/* via tema_css.montar_rotas_static()) tem reset global
    # que quebraria o Quasar — por isso item_menu_drawer replica o visual
    # (borda arredondada, hover, ativo) via Tailwind (.classes()) + Quasar
    # (.props()). RNF-UI-01 320/768/1024: w-full + min-width: 0, sem gap-*.
    with ui.left_drawer(bordered=True, elevated=False, value=False).classes("p-2").style("min-width: 0") as drawer:
        with ui.column().classes("w-full").style("gap: 0.25rem; min-width: 0"):
            # ===== HOME: página inicial de boas-vindas =====
            ui_comum.item_menu_drawer(
                "Home", icone="home",
                on_click=lambda: ui.navigate.to("/"),
                tooltip="Ir para a página inicial",
                chave_modulo=chave_modulo or "intranet",
                testid="menu-home",
                ativo=(not chave_modulo))

            ui.separator().classes("w-full")

            # ===== ORDENAÇÃO HAMBÚRGUER (requisito 2026-09-19) =====
            # Home fica isolado acima (já renderizado). Demais módulos em ordem
            # alfabética por nome, exceto Blog/Usuários/Auditoria que são
            # agrupados após Administração e antes de Documentação/Sair.
            _CHAVES_POS_ADMIN = {"blog", "usuarios", "auditoria"}
            _ORDEM_POS_ADMIN = ["blog", "usuarios", "auditoria"]
            _todos = autenticacao.modulos_do_usuario(nome_usuario)
            _map_todos = {c: (c, n, ic, r, a) for c, n, ic, r, a in _todos}
            _outros = [t for t in _todos if t[0] not in _CHAVES_POS_ADMIN]
            _outros.sort(key=lambda t: t[1].lower())
            _pos_admin = [_map_todos[c] for c in _ORDEM_POS_ADMIN if c in _map_todos]

            def _render_lista_modulos(lista):
                """Renders a list of drawer entries (active via item_menu_drawer or orange unavailable card).

                Renderiza uma lista de entradas do drawer (ativa via item_menu_drawer ou card laranja de indisponível).
                """
                for chave, nome, icone, rota, ativa in lista:
                    if ativa:
                        ui_comum.item_menu_drawer(
                            nome, icone=icone,
                            on_click=lambda r=rota: ui.navigate.to(r),
                            tooltip=f"Abrir o módulo {nome}",
                            chave_modulo=chave_modulo or "intranet",
                            testid=f"menu-{chave}",
                            ativo=(chave == chave_modulo))
                    else:
                        with ui.item(on_click=lambda n=nome: notificar(
                                f"⚠ '{n}' está indisponível/removido. Procure o administrador.",
                                type="warning", position="top")) \
                                .classes("w-full rounded-lg my-0.5 bg-orange-2 border border-orange-6 cursor-pointer "
                                         "focus-visible:ring-2 focus-visible:outline-none") \
                                .style("min-width: 0") \
                                .props(f'data-testid=menu-{chave}-indisponivel aria-label="{nome} — módulo indisponível"') \
                                .tooltip(f"'{nome}' está indisponível — procure o administrador"):
                            with ui.item_section().props("avatar"):
                                ui.icon("report_problem").classes("text-orange-9 shrink-0").props('aria-hidden="true"')
                            with ui.item_section().style("min-width: 0"):
                                ui.item_label(nome).classes("text-orange-10 font-bold truncate max-w-full").style("min-width: 0")
                                ui.item_label("Módulo indisponível").classes("text-caption text-orange-9 truncate max-w-full").style("min-width: 0")

            _render_lista_modulos(_outros)

            # Padrão PIC definido — exemplos de CSS removidos do menu (mantidos em disco/docs para comparação direta via URL se necessário).

            # ===== SISTEMA: Administração + trio Blog/Usuários/Auditoria + Documentação =====
            _eh_admin_geral = autenticacao.perfil_global_de(nome_usuario) == "administrador_geral"
            if _eh_admin_geral:
                ui.separator().classes("w-full")
                if chave_modulo:
                    _nome_mod_atual = autenticacao.nome_do_modulo(chave_modulo) or chave_modulo
                    _admin_label = "Administração"
                    _admin_tooltip = f"Configurações de {_nome_mod_atual}"
                else:
                    _admin_label = "Administração (sistema)"
                    _admin_tooltip = "Configurações gerais do sistema"
                ui_comum.item_menu_drawer(
                    _admin_label, icone="admin_panel_settings",
                    on_click=lambda cm=chave_modulo: ui.navigate.to(
                        f"/admin/{cm}" if cm else "/configuracoes"),
                    tooltip=_admin_tooltip,
                    chave_modulo=chave_modulo or "intranet",
                    testid="menu-admin",
                    ativo=False)

            # Trio Blog/Usuários/Auditoria — sempre após Administração (se houver) e antes de Documentação/Sair
            if _pos_admin:
                if not _eh_admin_geral:
                    ui.separator().classes("w-full")
                _render_lista_modulos(_pos_admin)

            if _eh_admin_geral:
                # Documentação MkDocs servida em /documentacao (main.py monta o site/)
                ui_comum.item_menu_drawer(
                    "Documentação", icone="menu_book",
                    on_click=lambda: ui.navigate.to(
                        "/documentacao", new_tab=True),
                    tooltip="Abre a documentação técnica em nova aba",
                    chave_modulo=chave_modulo or "intranet",
                    testid="menu-docs",
                    ativo=False)

            ui.separator().classes("w-full")
            ui_comum.item_menu_drawer(
                "Sair", icone="logout", on_click=_logout,
                tooltip="Encerrar a sessão e sair do sistema",
                chave_modulo=chave_modulo or "intranet",
                testid="menu-sair",
                ativo=False)

    # ===== FOOTER (parte 4) =====
    # Rodapé ESCONDIDO durante a navegação, revelado no hover/focus (faixa de
    # 5px como pista). É onde mora a escolha de estilo visual — escondido para
    # não roubar altura da tela de quem está trabalhando, e um mouse na base da
    # janela abre. CSS escopado via [data-testid="rodape-sistema"], sem
    # vazamento global.
    try:
        ui.add_head_html("""
<style>
/* Rodape — escondido por padrão, revela no hover/focus */
[data-testid="rodape-sistema"]{opacity:0;transform:translateY(calc(100% - 5px));transition:opacity .25s ease,transform .25s ease}
[data-testid="rodape-sistema"]:hover,[data-testid="rodape-sistema"]:focus-within{opacity:1;transform:none}
</style>
""")
    except Exception:
        pass
    with ui.footer().classes("bg-grey-8 w-full").props('data-testid=rodape-sistema').style("min-width: 0"):
        with ui.row().classes("w-full items-center justify-between flex-wrap px-4 py-1").style("gap: 0.5rem; min-width: 0"):
            texto_rodape = _obter_config("texto_rodape", "uso interno") or "uso interno"
            ui.label(f"{titulo_sistema} Básica — {texto_rodape}").classes(
                "text-caption opacity-80")
            # Escolha de estilo visual: mora no COOKIE deste navegador, então
            # o padrão escolhido é só dele e não viaja com o usuário para
            # outra máquina. Fica no meio do rodapé para ser Achado sem caçar a
            # beira, e disponível em QUALQUER módulo.
            try:
                from mod_intranet import preview_estilos as _pv_estilos
                _pv_estilos.barra_alternador(estilo_visual_usuario, discreto=True)
            except Exception:
                try:
                    import logging
                    logging.getLogger(__name__).exception(
                        "telas: falha ao montar a barra de estilo no rodapé")
                except Exception:
                    pass
            # Versões (esquerda -> direita): 1ª global do sistema, seguida da
            # parte do módulo atual mesclada (ocultando AAMMDD iguais).
            # Sempre exibido num rótulo único; o detalhe completo fica no tooltip.
            with ui.row().classes("items-center flex-wrap").style("gap: 0.5rem; min-width: 0"):
                versao = _obter_versao()
                versao_mod = _obter_versao_modulo(chave_modulo) if chave_modulo else None
                resultado = _formatar_versao_rodape(versao, versao_mod)
                ui.label(resultado).classes("text-caption font-bold opacity-90").tooltip(
                    f"Sistema: v{versao}\nMódulo: v{versao_mod}" if versao_mod
                    else f"Sistema: v{versao}")


def _logout():
    user = usuario_logado()
    if user:
        autenticacao.registrar_logout(user["nome"], user.get("sessao"))
    app.storage.user.clear()
    ui.navigate.to("/login")


def _dialogo_meu_perfil(nome_usuario: str):
    """Autoatendimento: edita próprios dados pessoais e troca própria senha.

    Permissões e chaves de banco NÃO são editáveis aqui (README linha 60).
    """
    row = autenticacao._gest().obter_usuario(nome_usuario)
    email_atual = row[3] or "" if row else ""
    fone_atual = row[4] or "" if row else ""
    completo_atual = row[9] or "" if row else ""

    # Diálogo de FORMULÁRIO (dados + senha + telefones + fechar): sem teto de
    # altura, ele estourava a janela e quem rolava era a página inteira. O
    # `dialogo_formulario` dá 88vw, teto de 90vh e rolagem só no miolo.
    with ui_comum.dialogo_formulario(chave_modulo="intranet",
                                     sem_descricao=True) as (dlg, card, miolo, grade):
        ui.label("Meu Perfil").classes("text-h6 font-bold")
        ui.separator()

        ui.label("Dados pessoais").classes("text-subtitle2 text-grey-7")
        # Grade só dos três campos de dados: a ordem do DOM dos campos de SENHA
        # abaixo não pode mudar (o QA preenche por índice), e ela fica fora da
        # grade de propósito.
        with grade:
            completo = ui_comum.campo_texto(
                "Nome completo (ou social)", valor=completo_atual,
                tooltip="Nome pelo qual você será tratado no sistema. "
                        "Pode ser seu nome social (Decreto 8.727/2016)")
            email = ui_comum.campo_texto("E-mail", valor=email_atual)
            try:
                from mod_intranet import telefone as _tel_perfil
                _campo_fone_perfil = _tel_perfil.criar_campo_telefone(valor=fone_atual)
            except Exception:
                _campo_fone_perfil = None
                fone = ui_comum.campo_texto("Telefone", valor=fone_atual)

        def _fone_perfil_valor():
            try:
                if _campo_fone_perfil is not None:
                    return _campo_fone_perfil["obter"]() or ""
                return fone.value.strip()
            except Exception:
                return ""

        def salvar_dados():
            ok, msg = autenticacao.editar_meu_perfil(
                nome_usuario, email=email.value.strip(), fone=_fone_perfil_valor(),
                nome_completo=completo.value.strip())
            notificar(msg, type="positive" if ok else "negative")
            if ok:
                ui.timer(0.1, lambda: ui.navigate.reload(), once=True)

        _botao_tema("Salvar dados", on_click=salvar_dados)

        ui.separator()
        ui.label("Trocar minha senha").classes("text-subtitle2 text-grey-7")
        atual = ui_comum.campo_texto("Senha atual", senha=True)
        nova = ui_comum.campo_texto("Nova senha (mín. 6)", senha=True)
        conf = ui_comum.campo_texto("Confirmar nova senha", senha=True)

        def salvar_senha():
            if nova.value != conf.value:
                notificar("As senhas não conferem", type="negative")
                return
            ok, msg = autenticacao.trocar_senha_propria(nome_usuario, atual.value or "", nova.value or "")
            notificar(msg, type="positive" if ok else "negative")
            if ok:
                atual.value = nova.value = conf.value = ""

        _botao_tema("Alterar senha", on_click=salvar_senha)

        ui.separator()
        _bloco_telefones_meu_perfil(nome_usuario)

        ui.separator()
        with ui.row().classes("w-full justify-end"):
            _botao_tema("Fechar", variante="texto", on_click=dlg.close)
    dlg.open()


def _bloco_telefones_meu_perfil(nome_usuario: str):
    """EN: My phones — add, change and withdraw publication consent.

    PT-BR: Meus telefones — cadastrar, corrigir e RETIRAR a autorização de
    publicação.

    POR QUE ISTO EXISTE
        No primeiro acesso o servidor escolhe o que pode aparecer na lista
        telefônica. Mas escolha nenhuma é definitiva: o número de quem
        atendia a defesa civil em março pode ser de outra pessoa em setembro.
        Pedir consentimento e não dar com o que retirá-lo é a forma mais
        rápida de um cadastro público virar dato ruim — e o dono do número é
        quem tem que decidir, não o administrador.

    O QUE NÃO É NEGOCIÁVEL
        O checkbox do celular particular e o do residencial não aparecem, e o
        do fixo da prefeitura vem travado. A regra é da prefeitura
        (`telefone_e_publicavel`), não deste formulário: repetir a regra
        aqui criaria dois lugares onde ela mora, e o formulário viraria a
        fonte da verdade no primeiro dia em que alguém o copiasse.
    """
    from mod_gest_cad_usuario import bd_manipulador as _bd_usuarios

    ui.label("Meus telefones").classes("text-subtitle2 text-grey-7")
    ui.label("O fixo da prefeitura é a linha institucional e aparece na "
             "lista telefônica. Os demais só saem se você marcar aqui.") \
        .classes("text-caption text-grey-6")

    caixa = ui.column().classes("w-full gap-1")

    def _desenhar():
        caixa.clear()
        try:
            telefones = _bd_usuarios.listar_telefones(nome_usuario)
        except Exception as e:
            lg = _login_erro_log()
            if lg:
                lg.exception(f"meu_perfil: falha ao listar telefones: {e}")
            return
        if not telefones:
            ui.label("Nenhum telefone cadastrado.").classes("text-body2 text-grey-6 italic")
            return
        # t = (id, user_nome, numero, papel, tipo, principal, visivel, data_cadastro)
        for t in telefones:
            papel_txt = "da prefeitura" if t[3] == "empresa" else "particular"
            tipo_txt = "fixo" if t[4] == "fixo" else "celular"
            with ui.row().classes("w-full items-center no-wrap").style("gap: 0.5rem"):
                with ui.column().classes("grow").style("min-width: 0"):
                    ui.label(f"{t[2]}").classes("text-body2 truncate")
                    detalhe = f"{tipo_txt} {papel_txt}"
                    if t[4] == "fixo" and t[3] == "empresa":
                        detalhe += " · sempre na lista"
                    elif _bd_usuarios.telefone_e_publicavel(t[3], t[4], t[6]):
                        detalhe += " · aparece na lista"
                    else:
                        detalhe += " · só no seu cadastro"
                    ui.label(detalhe).classes("text-caption text-grey-6 truncate")
                # o particular não tem botão de publicar: não há o que
                # autorizar. O fixo da prefeitura também não.
                if t[3] == "empresa" and t[4] == "celular":
                    marcado = ui.checkbox("na lista")
                    marcado.props("dense data-testid=meu-perfil-visivel-{}".format(t[0]))
                    marcado.value = bool(t[6])

                    def _alternar(valor, tid=t[0]):
                        try:
                            _bd_usuarios.editar_telefone(nome_usuario, tid, visivel=bool(valor))
                            notificar("Lista telefônica atualizada.", tipo="positive")
                        except Exception as e:
                            lg = _login_erro_log()
                            if lg:
                                lg.exception(f"meu_perfil: falha ao alterar visivel do {tid}: {e}")
                            notificar("Não foi possível alterar.", tipo="error")

                    marcado.on("update:model-value", lambda ev, tid=t[0]: _alternar(ev.value, tid))
                with ui.button(on_click=lambda tid=t[0]: _remover(tid), icon="delete") \
                        .props("flat dense color=negative").classes("shrink-0") \
                        .tooltip("Remover este telefone"):
                    ui.props("data-testid=meu-perfil-remover-{}".format(t[0]))

    def _remover(tid):
        try:
            ok, msg = _bd_usuarios.remover_telefone(nome_usuario, tid)
            notificar(msg, tipo="positive" if ok else "negative")
            if ok:
                _desenhar()
        except Exception as e:
            lg = _login_erro_log()
            if lg:
                lg.exception(f"meu_perfil: falha ao remover telefone {tid}: {e}")
            notificar("Erro ao remover o telefone.", tipo="error")

    _desenhar()

    def _adicionar():
        with ui.dialog() as dlg_add:
            with ui.card().classes("w-[380px] gap-2"):
                ui.label("Novo telefone").classes("text-h6")
                num = ui.input("Número").props("outlined dense").classes("w-full") \
                    .props("data-testid=meu-perfil-novo-numero")
                pap = ui.select({"empresa": "da prefeitura", "pessoal": "particular"},
                                label="De quem é", value="empresa") \
                    .props("outlined dense").classes("w-full")
                tip = ui.select({"celular": "celular", "fixo": "fixo"},
                                label="Tipo", value="celular") \
                    .props("outlined dense").classes("w-full")
                vis = ui.checkbox("Pode aparecer na lista telefônica")
                vis.props("dense data-testid=meu-perfil-novo-visivel")

                def _salvar_add():
                    try:
                        ok, msg = _bd_usuarios.adicionar_telefone(
                            nome_usuario, num.value or "", papel=pap.value,
                            tipo=tip.value, visivel=bool(vis.value))
                        notificar(msg, tipo="positive" if ok else "negative")
                        if ok:
                            dlg_add.close()
                            _desenhar()
                    except Exception as e:
                        lg = _login_erro_log()
                        if lg:
                            lg.exception(f"meu_perfil: falha ao adicionar telefone: {e}")
                        notificar("Erro ao cadastrar o telefone.", tipo="error")

                with ui.row().classes("w-full justify-end"):
                    ui.button("Cancelar", on_click=dlg_add.close).props("flat")
                    _botao_tema("Salvar", on_click=_salvar_add)
        dlg_add.open()

    _botao_tema("Adicionar telefone", variante="secundario", on_click=_adicionar)


# ================ LAYOUT DO DIÁLOGO DE TROCA DE CREDENCIAIS =================
#
# O diálogo do primeiro acesso do `master` foi o PRIMEIRO a receber o layout de
# formulário largo, e é o que tem mais conteúdo: 7 campos, dois blocos
# informativos e um botão. Com `w-96` (384px) e `max_altura=False` ele virava uma
# coluna estreita que estourava a altura da janela — e quem rolava era a PÁGINA
# INTEIRA, uma barra de rolagem no meio do formulário, não o conteúdo do diálogo.
#
# A correção é de LAYOUT, não de estrutura: os campos continuam sendo os mesmos
# `ui_comum.campo_texto`, na MESMA ordem do DOM (o QA preenche os três campos
# de senha por índice: atual → nova → confirmar), e o que muda é o CSS.
#
# A largura e as grades NÃO são definidas aqui: moram em `ui_comum` e são
# compartilhadas por todos os diálogos de formulário da intranet, para que este
# diálogo e o de "Novo usuário" não cresçam em direções diferentes. O que este
# módulo acrescenta são os DOIS blocos informativos lado a lado, o que a base
# comum não faz — os campos vão na grade de `miolo`, os avisos em outra.
LARGURA_DIALOGO_TROCA = ui_comum.LARGURA_DIALOGO_FORMULARIO
CSS_GRADE_CAMPOS_TROCA = ui_comum.CSS_GRADE_CAMPOS
CSS_GRADE_AVISOS_TROCA = ui_comum.CSS_GRADE_AVISOS

# Senha que o formulário de troca obrigatória JÁ PROPOSTE (30/09/2026).
#
# Só para as contas de TESTE — `qacomum` e `qamaster`, que entregam com a
# senha `123456` e são contas de fábrica publicadas na §8.2 do AGENTS.md. Não
# vale para conta real: o campo nasce vazio e a pessoa digita a senha dela.
#
# Por que preencher: obrigar a DIGITAR uma senha que já se sabe qual é é
# trabalho sem resultado — o objetivo da troca obrigatória é a pessoa entrar,
# não decorar `123456`. Com o campo preenchido, a troca é um clique. É a mesma
# lógica do diálogo de credenciais do `master`, que nasce com o nome e a
# senha do responsável.
_SENHA_PROPOSTA_TROCA = "123456"


def _dialogo_troca_credenciais(nome_usuario: str, ao_concluir=None):
    """Opens the mandatory first-access dialog with a safe minimal fallback.

    Abre o diálogo de troca obrigatória completo (pré-preenchido); se a
    montagem falhar por qualquer motivo, abre o diálogo mínimo (campos
    simples, sem pré-preenchimento) para nunca derrubar a página. Nenhum
    caminho propaga exceção ao chamador.

    `ao_concluir` é repassado aos dois diálogos e roda só depois de uma
    troca bem-sucedida — é o que encadeia o cadastro dos telefones."""
    try:
        _dialogo_troca_credenciais_completo(nome_usuario, ao_concluir)
    except Exception as _e_full:
        try:
            _login_erro_log().exception(
                f"troca_credenciais completo falhou para '{nome_usuario}': {_e_full}")
        except Exception:
            pass
        try:
            _dialogo_troca_credenciais_minimo(nome_usuario, ao_concluir)
        except Exception as _e_min:
            try:
                _login_erro_log().exception(
                    f"troca_credenciais mínimo falhou para '{nome_usuario}': {_e_min}")
            except Exception:
                pass
            try:
                notificar("Erro ao abrir a troca de credenciais.", tipo="error")
            except Exception:
                pass


def _dialogo_troca_credenciais_minimo(nome_usuario: str, ao_concluir=None):
    """Minimal first-access dialog (plain fields, no prefill, no DDI select).

    Diálogo mínimo de primeiro acesso: campos simples vazios, sem
    pré-preenchimento e sem combobox de DDI. Fallback para garantir que o
    master sempre consiga trocar as credenciais mesmo se o diálogo completo
    falhar.

    Mesmo layout do diálogo completo (88vw, teto de 1600px, `max-h-[90vh]` com
    rolagem interna e grade auto-fit nos campos), porque um fallback que
    estoura a tela em máquina de instalação não é fallback de ninguém.

    `ao_concluir` recebe o NOVO nome de usuário, porque aqui o login muda."""
    with ui_comum.dialogo_card(largura=LARGURA_DIALOGO_TROCA,
                               max_altura=True) as (dlg, card):
        # O card vira coluna flex (`max-h-[90vh]` vem do `max_altura=True`):
        # título fica parado em cima, botão parado embaixo, e o miolo é que
        # rola. O `min-h-0` do miolo é obrigatório — sem ele o filho flex não
        # encolhe abaixo da altura do conteúdo, o `overflow-y` não pega e o
        # `max-h` do card é simplesmente ignorado.
        card.classes("flex flex-col")
        ui.label("Credenciais obrigatórias").classes("text-h6")
        ui.label("Por segurança, defina um novo nome de usuário e uma nova "
                 "senha antes de continuar.").classes("text-body2 text-grey-7")
        _miolo = ui.column().classes("w-full flex-1 min-h-0 overflow-y-auto")
        _miolo.props('role="region" tabindex="0" '
                     'aria-label="Campos da troca de credenciais"')
        with _miolo:
            # Grade responsiva: os 7 campos saem da coluna estreita e ocupam
            # várias colunas na tela larga, sem media query e sem mexer na
            # ORDEM do DOM — atual → nova → confirmar, que é o contrato do QA.
            _grade = ui.element("div").classes("w-full").style(
                CSS_GRADE_CAMPOS_TROCA)
            _grade.props('role="group" aria-label="Dados de acesso"')
            with _grade:
                novo_nome = ui_comum.campo_texto("Novo nome de usuário",
                                                 props="")
                nome_completo = ui_comum.campo_texto("Nome completo (ou social)",
                                                     props="")
                email = ui_comum.campo_texto("E-mail", props="")
                fone = ui_comum.campo_texto("Telefone", props="")
                atual = ui_comum.campo_texto("Senha atual", senha=True, props="")
                nova = ui_comum.campo_texto("Nova senha (mín. 6)", senha=True,
                                            props="")
                conf = ui_comum.campo_texto("Confirmar nova senha", senha=True,
                                            props="")

        def _v(campo):
            try:
                return getattr(campo, "value", "") or ""
            except Exception:
                return ""

        def confirmar():
            try:
                if not _v(novo_nome).strip() or _v(novo_nome).strip().lower() == "master":
                    notificar("Informe um novo nome de usuário diferente de 'master'.",
                              type="negative")
                    return
                if _v(nova) != _v(conf):
                    notificar("As senhas não conferem", type="negative")
                    return
                try:
                    ok, msg, novo = autenticacao.trocar_credenciais_master(
                        nome_usuario, _v(novo_nome), _v(atual), _v(nova),
                        nome_completo=_v(nome_completo),
                        email=_v(email), fone=_v(fone))
                except Exception as _e_cred:
                    _login_erro_log().exception(
                        f"falha ao trocar credenciais de '{nome_usuario}': {_e_cred}")
                    notificar("Erro ao trocar credenciais", type="negative")
                    return
                notificar(msg, type="positive" if ok else "negative")
                if ok:
                    try:
                        app.storage.user["usuario"]["nome"] = novo
                    except Exception:
                        pass
                    try:
                        dlg.close()
                    except Exception:
                        pass
                    ui.timer(0.2, lambda: ui.navigate.to("/"))
                    if ao_concluir:
                        try:
                            ao_concluir(novo)
                        except Exception as e:
                            _login_erro_log().exception(
                                f"troca_credenciais: callback de {novo} falhou: {e}")
            except Exception as _e_conf:
                try:
                    _login_erro_log().exception(
                        f"confirmar mínimo falhou para '{nome_usuario}': {_e_conf}")
                except Exception:
                    pass
                try:
                    notificar("Erro ao salvar credenciais.", tipo="error")
                except Exception:
                    pass

        # fora do miolo: o botão fica ancorado na base do card, sempre visível
        # mesmo com o formulário rolado até o fim
        _botao_tema("Salvar credenciais", on_click=confirmar,
                    extra_classes="w-full mt-2 shrink-0")
    dlg.props("persistent")
    dlg.open()


# Contas de teste que a semente de QA cria (AGENTS.md §8.2). São as mesmas da
# documentação — o objetivo de as listar aqui é o oposto do de documentá-las:
# aqui é onde se decide se elas ficam.
CONTAS_DE_TESTE = ("qacomum", "qamaster")


def _contas_de_teste():
    """As contas de teste que ainda existem, para a tela do primeiro acesso.

    Devolve lista de dicionários `{"login", "nome", "perfil"}`. Lista vazia
    quando não há nenhuma, ou quando o cadastro não pode ser lido — e lista
    vazia é o estado NORMAL depois que o administrador já apagou, e também o
    estado de quem não tem esse módulo. Nos dois casos a tela não mostra o
    bloco, e não é erro.
    """
    saida = []
    try:
        from mod_gest_cad_usuario import bd_manipulador as _bd
        for login in CONTAS_DE_TESTE:
            try:
                linha = _bd.listar_usuarios()
            except Exception:
                return []
            achado = next((u for u in (linha or []) if u[1] == login), None)
            if not achado:
                continue
            saida.append({
                "login": login,
                "nome": (achado[9] or "").strip() or login,
                "perfil": achado[2] or "",
            })
    except Exception as e:
        try:
            _login_erro_log().exception(
                f"contas de teste: não foi possível listar: {e}")
        except Exception:
            pass
        return []
    return saida


def _apagar_conta_teste(login: str):
    """Apaga uma conta de teste a partir da tela de primeiro acesso.

    A exclusão é a DEFINITIVA (a de LGPD, com limpeza em cascata nos outros
    módulos), não uma desativação: conta de teste que fica lá, desativada, é
    conta que alguém reativa por engano daqui a seis meses. O usuário pede
    "apagar do cadastro", e apagar de verdade é o que ele espera.

    O que este botão NÃO faz é apagar conta que não é de teste. A lista vem
    de `CONTAS_DE_TESTE`, e o nome vem do botão — não de digitação livre — então
    não há como apagar `master` por este caminho. E mesmo que houvesse,
    `excluir_usuario_definitivo` recusa `master` e recusa remover o último
    administrador geral ativo: a proteção não depende desta tela.
    """
    if login not in CONTAS_DE_TESTE:
        notificar("Esta conta não é de teste.", type="warning")
        return
    try:
        from mod_gest_cad_usuario import bd_manipulador as _bd
        ok, msg = _bd.excluir_usuario_definitivo("master", login)
        notificar(msg or ("Conta apagada." if ok else "Não foi possível apagar."),
                  type="positive" if ok else "negative")
        if ok:
            # some com a linha da lista sem recarregar a página inteira: quem
            # está no meio da troca de credenciais não pode perder o que já
            # preencheu por causa de um botão ao lado.
            _REMOVIDOS_DE_TESTE.add(login)
            ui.navigate.reload()
    except Exception as e:
        try:
            _login_erro_log().exception(f"apagar conta de teste {login}: {e}")
        except Exception:
            pass
        notificar("Erro ao apagar a conta de teste.", type="negative")


# Contas já apagadas nesta sessão. Vive no servidor (não no navegador) porque a
# tela é re-renderizada a cada dialogo e a lista de contas é lida de novo; sem
# isto, o bloco voltaria a aparecer depois do reload, com a conta que não existe
# mais — pior do que não mostrar nada.
_REMOVIDOS_DE_TESTE = set()


def _dialogo_troca_credenciais_completo(nome_usuario: str, ao_concluir=None):
    """Full first-access dialog (prefilled + DDI phone field).

    Diálogo completo do primeiro acesso do `master` nativo: vem
    pré-preenchido com os dados do responsável pelo sistema para o futuro
    administrador conferir/ajustar antes de salvar. `persistent` (não fecha
    com ESC/clique fora) e fechamento somente após a troca bem-sucedida.

    Layout: card largo (88vw, teto de 1600px) e alto no máximo 90vh, com o
    conteúdo rolando por dentro — em vez dos 384px de antes, que faziam o
    formulário estourar a janela. Os dois blocos informativos ocupam o mesmo
    grid auto-fit (lado a lado em tela larga, empilhados no celular) e os
    campos vão para um segundo grid, SEM mudar a ordem do DOM: o QA preenche
    os três campos de senha por índice (atual → nova → confirmar).

    `ao_concluir` recebe o NOVO nome de usuário, porque aqui o login muda."""
    with ui_comum.dialogo_card(largura=LARGURA_DIALOGO_TROCA,
                               max_altura=True) as (dlg, card):
        # Mesmo esqueleto do diálogo mínimo: card em coluna flex com
        # `max-h-[90vh]`, título e botão parados nas pontas e miolo rolável
        # (`flex-1 min-h-0 overflow-y-auto`) — o `min-h-0` é o que permite ao
        # filho encolher abaixo da altura do conteúdo e o `overflow-y` pegar.
        card.classes("flex flex-col")
        ui.label("Credenciais obrigatórias").classes("text-h6")
        ui.label(f"Bem-vindo(a), {autenticacao.nome_de_tratamento(nome_usuario)}. "
                 "Por segurança, defina um novo nome de usuário e uma nova "
                 "senha antes de continuar.").classes("text-body2 text-grey-7")
        _miolo = ui.column().classes("w-full flex-1 min-h-0 overflow-y-auto")
        _miolo.props('role="region" tabindex="0" '
                     'aria-label="Conteúdo da troca de credenciais"')
        with _miolo:
            _grade_avisos = ui.element("div").classes("w-full").style(
                CSS_GRADE_AVISOS_TROCA)
            _grade_avisos.props(
                'role="group" aria-label="Informações do primeiro acesso"')
            with _grade_avisos:
                try:
                    with ui.column().classes("w-full gap-1 p-2 rounded bg-blue-1"):
                        ui.label("Analista de Sistemas Atual: Klayton Prince").classes(
                            "text-caption font-bold text-blue-10")
                        ui.label("Analista de Sistemas Inicial: Klayton Prince").classes(
                            "text-caption text-blue-9")
                        ui.label("klayton.prince.ms@gmail.com").classes(
                            "text-caption text-blue-9")
                        ui.label("+55 (35) 98818-3288").classes(
                            "text-caption text-blue-9")
                except Exception:
                    pass
                # ------- Contas de teste: apagar ou manter, AQUI (28/09/2026) ---
                #
                # A prefeitura recebe o sistema com `qacomum` e `qamaster` já
                # cadastrados (a semente de QA, AGENTS.md §8.2). Quem entra pela
                # primeira vez com `master` é o administrador installing — é a
                # única pessoa no sistema cuja conta tem o perfil
                # `administrador_geral` de fábrica e senha conhecida. Se ele sai
                # da tela sem decidir o destino dessas duas contas, fica uma
                # prefeitura com dois administradores de senha `123456`
                # published.
                #
                # Por que AQUI e não em uma tela depois: este é o momento em que
                # a pessoa está trocando a senha do administrador porque entendeu
                # que conta de fábrica é perigosa. Um passo adiante, essa Timeout
                # já passou.
                _contas_teste = _contas_de_teste()
                if _contas_teste:
                    with ui.column().classes("w-full gap-1 p-2 rounded bg-orange-1"):
                        ui.label("Contas de teste que vieram com o sistema").classes(
                            "text-caption font-bold text-orange-10")
                        ui.label(
                            "O sistema é entregue com duas contas de teste, "
                            "para documentação e conferência. Elas entram com "
                            "a senha conhecida, então convém decidir agora o "
                            "que fazer com elas — apagar é o padrão de quem "
                            "vai usar o sistema de verdade, e manter é o de "
                            "quem ainda vai documentar.").classes(
                            "text-caption text-orange-9")
                        # a linha da conta continua com a mesma estrutura: o
                        # nome/login ocupa o que sobra (`flex: 1 1 0` +
                        # `min-width: 0`) e o botão "Apagar" nunca é espremido
                        # nem quebra em tela estreita
                        for _c in _contas_teste:
                            with ui.row().classes("w-full items-center").style(
                                    "gap: 0.5rem; min-width: 0"):
                                with ui.column().classes("gap-0").style(
                                        "min-width: 0; flex: 1 1 0"):
                                    ui.label(f"{_c['nome']}  (@{_c['login']})").classes(
                                        "text-caption text-grey-8 truncate")
                                    ui.label(f"perfil: {_c['perfil']}").classes(
                                        "text-caption text-grey-6")
                                _btn_excluir = ui_comum.botao(
                                    "Apagar", icone="delete",
                                    on_click=lambda l=_c["login"]: _apagar_conta_teste(l),
                                    variante="perigo", compacto=True,
                                    chave_modulo="intranet")
                                _btn_excluir.props(
                                    f'data-testid=apagar-conta-teste-{_c["login"]} '
                                    f'aria-label="Apagar a conta de teste {_c["login"]}"')
                                _btn_excluir.classes("no-print")

            _grade_campos = ui.element("div").classes("w-full").style(
                CSS_GRADE_CAMPOS_TROCA)
            _grade_campos.props('role="group" aria-label="Dados de acesso"')
            with _grade_campos:
                novo_nome = ui_comum.campo_texto("Novo nome de usuário",
                                                 valor="klayton", props="")
                nome_completo = ui_comum.campo_texto(
                    "Nome completo (ou social)", valor="PRINCE,K.B", props="",
                    tooltip="Nome pelo qual você será tratado no sistema. "
                            "Pode ser seu nome social (Decreto 8.727/2016)")
                email = ui_comum.campo_texto("E-mail",
                                             valor="klayton.prince.ms@gmail.com",
                                             props="")
                _campo_fone = None
                fone = None
                try:
                    from mod_intranet import telefone as _tel
                    _campo_fone = _tel.criar_campo_telefone(valor="+5535988183288")
                except Exception:
                    _campo_fone = None
                if _campo_fone is None:
                    try:
                        fone = ui_comum.campo_texto("Telefone", valor="35988183288",
                                                    props="")
                    except Exception:
                        fone = None
                # a ORDEM do DOM dos três campos de senha é contrato do QA
                # (`concluir_troca` preenche por índice): atual → nova →
                # confirmar. O grid CSS preenche por linha e não reordena.
                atual = ui_comum.campo_texto("Senha atual", senha=True,
                                             valor="master", props="")
                nova = ui_comum.campo_texto("Nova senha (mín. 6)", senha=True,
                                            valor="klayton", props="")
                conf = ui_comum.campo_texto("Confirmar nova senha", senha=True,
                                            valor="klayton", props="")

        def _v(campo):
            try:
                return getattr(campo, "value", "") or ""
            except Exception:
                return ""

        def _fone_valor():
            try:
                if _campo_fone is not None:
                    return _campo_fone["obter"]() or ""
                return _v(fone)
            except Exception:
                return ""

        def confirmar():
            try:
                if not _v(novo_nome).strip() or _v(novo_nome).strip().lower() == "master":
                    notificar("Informe um novo nome de usuário diferente de 'master'.",
                              type="negative")
                    return
                if _v(nova) != _v(conf):
                    notificar("As senhas não conferem", type="negative")
                    return
                try:
                    ok, msg, novo = autenticacao.trocar_credenciais_master(
                        nome_usuario, _v(novo_nome), _v(atual), _v(nova),
                        nome_completo=_v(nome_completo),
                        email=_v(email), fone=_fone_valor())
                except Exception as _e_cred:
                    _login_erro_log().exception(
                        f"falha ao trocar credenciais de '{nome_usuario}': {_e_cred}")
                    notificar("Erro ao trocar credenciais", type="negative")
                    return
                notificar(msg, type="positive" if ok else "negative")
                if ok:
                    try:
                        _login_erro_log().info(
                            f"credenciais ok: '{nome_usuario}' -> '{novo}' — "
                            "atualizando sessão")
                    except Exception:
                        pass
                    try:
                        app.storage.user["usuario"]["nome"] = novo
                    except Exception as _e_sess:
                        try:
                            _login_erro_log().exception(
                                f"falha ao atualizar sessão para '{novo}': {_e_sess}")
                        except Exception:
                            pass
                    try:
                        dlg.close()
                    except Exception as _e_close:
                        try:
                            _login_erro_log().exception(
                                f"falha ao fechar diálogo de '{novo}': {_e_close}")
                        except Exception:
                            pass
                    try:
                        _login_erro_log().info(
                            f"credenciais ok: '{novo}' — agendando navegação para /")
                    except Exception:
                        pass
                    ui.timer(0.2, lambda: ui.navigate.to("/"))
                    if ao_concluir:
                        try:
                            ao_concluir(novo)
                        except Exception as e:
                            _login_erro_log().exception(
                                f"troca_credenciais: callback de {novo} falhou: {e}")
            except Exception as _e_conf:
                try:
                    _login_erro_log().exception(
                        f"confirmar completo falhou para '{nome_usuario}': {_e_conf}")
                except Exception:
                    pass
                try:
                    notificar("Erro ao salvar credenciais.", tipo="error")
                except Exception:
                    pass

        # fora do miolo: o botão fica ancorado na base do card, sempre visível
        # mesmo com o formulário rolado até o fim
        _botao_tema("Salvar credenciais", on_click=confirmar,
                    extra_classes="w-full mt-2 shrink-0")
    # persistent: não fecha com ESC/clique fora — a troca é realmente obrigatória
    dlg.props("persistent")
    dlg.open()


def _dialogo_troca_senha(nome_usuario: str, ao_concluir=None):
    """Forces the mandatory first-login password change dialog.

    Diálogo persistente de troca obrigatória de senha no primeiro acesso:
    `persistent` (não fecha com ESC/clique fora) e fechamento somente após
    a troca bem-sucedida. Título manual (`text-h6`, sem separador) para
    manter o visual original.

    `ao_concluir` roda DEPOIS da troca bem-sucedida, e é o que abre o passo
    seguinte do primeiro acesso (o cadastro dos telefones). Se a troca
    falhar, o callback não roda — senão o servidor cadastraria o telefone
    e continuaria com a senha provisória.
    """
    # Mesmo esqueleto do diálogo de credenciais: 88vw, teto de 90vh, miolo
    # rolável e botão ancorado na base. A ORDEM do DOM dos três campos de senha
    # (atual → nova → confirmar) é preservada: o QA preenche por índice em
    # `assets/test/qa_login_helper.py::concluir_troca`.
    #
    # SENHA PROPOSTA PRÉ-PREENCHIDA (30/09/2026, decisão do responsável).
    # `qacomum` e `qamaster` são contas de teste que ENTREGAM com a senha
    # `123456` (§8.2 do AGENTS.md), e a troca obrigatória existe para quem
    # entra. Deixar o campo vazio obriga a pessoa a DIGITAR uma senha que já
    # se sabe qual é — trabalho sem resultado. O formulário nasce preenchido
    # com `123456` nos dois campos, como o diálogo de credenciais do `master`
    # nasce com o nome e a senha do responsável: a troca vira um clique.
    #
    # A senha ATUAL continua vazia de propósito: ela é o que se está
    # substituindo, e vir preenchida tiraria a prova de que a pessoa sabe a
    # senha de entrada.
    with ui_comum.dialogo_formulario(
            chave_modulo="intranet", sem_descricao=True) as (dlg, card, miolo, grade):
        # TÍTULO E BOAS-VINDAS DENTRO DO `miolo`, de propósito (30/09/2026).
        # `dialogo_formulario` fecha `miolo` e `grade` ANTES do `yield` — está
        # escrito no docstring: é o que ancora o rodapé na base do cartão. Só
        # que a consequência é que tudo que o chamador cria fora desses `with`
        # nasce no CARD, ou seja DEPOIS da coluna rolável, e o título aparecia
        # embaixo dos campos. Criando dentro de `miolo`, título e boas-vindas
        # ficam no topo do formulário.
        #
        # Em diálogo de três campos a coluna nem rola, então não há custo: é o
        # lugar certo, e não vale mexer no helper compartilhado (23 chamadas).
        with miolo:
            ui.label("Troca de senha obrigatória").classes("text-h6")
            ui.label(f"Bem-vindo(a), {autenticacao.nome_de_tratamento(nome_usuario)}. "
                     "Por segurança, defina uma nova senha antes de continuar.").classes(
                "text-body2 text-grey-7")
            with grade:
                atual = ui_comum.campo_texto("Senha atual", senha=True, props="")
                nova = ui_comum.campo_texto("Nova senha (mín. 6)", senha=True,
                                            valor=_SENHA_PROPOSTA_TROCA,
                                            props="")
                conf = ui_comum.campo_texto("Confirmar nova senha", senha=True,
                                            valor=_SENHA_PROPOSTA_TROCA, props="")
            # --- Veredito de força e de vazamento, enquanto a pessoa digita --
            # `on("update:model-value")` chega a cada tecla; o `ui.timer` de 0,8s
            # segura o que está digitando e dispara UMA vez ao parar, no mesmo
            # padrão do "Por página" do agregador.
            #
            # O requisito de rede local mora aqui: o que roda no event-loop é só
            # a troca de rótulo. A consulta sai por `run.io_bound`, porque pode
            # falar com a internet — e uma espera de socket na fila do
            # event-loop trava a tela inteira, sem internet até o fim do tempo
            # máximo. Fora da fila, o pior caso é um rótulo que não muda.
            rotulo_veredito = ui.label("").classes("text-body2")

            async def _avaliar_senha():
                """Consulta fora do event-loop. Falha aqui não trava a troca."""
                from mod_intranet.validador_senha import (
                    analisar_online, texto_para_usuario)
                senha = nova.value or ""
                if len(senha) < 4:
                    rotulo_veredito.set_text("")
                    return
                try:
                    r = await run.io_bound(analisar_online, senha, nome_usuario)
                    r = r or {}
                    texto = texto_para_usuario(r)
                    rotulo_veredito.set_text(texto)
                    rotulo_veredito.classes(
                        remove="text-grey-7 text-positive text-negative",
                        add="text-negative" if not r.get("ok") else "text-positive")
                except Exception as e:
                    # Se a avaliação falhar, a pessoa continua podendo trocar a
                    # senha — a checagem é ajuda, não portão.
                    lg = _login_erro_log()
                    if lg:
                        lg.exception(f"troca_senha: veredito falhou: {e}")
                    rotulo_veredito.set_text("")

            _pendente_veredito = {"timer": None}

            def _agendar_veredito(_=None):
                t = _pendente_veredito.get("timer")
                if t is not None:
                    try:
                        t.delete()
                    except Exception:
                        pass
                _pendente_veredito["timer"] = ui.timer(
                    0.8, _avaliar_senha, once=True)

            nova.on("update:model-value", _agendar_veredito)
            # Primeira avaliação: o formulário já nasce preenchido, e a pessoa
            # precisa do veredito sem ter que mexer em algum campo.
            _agendar_veredito()

        def confirmar():
            if nova.value != conf.value:
                notificar("As senhas não conferem", type="negative")
                return
            ok, msg = autenticacao.trocar_senha_propria(nome_usuario, atual.value or "", nova.value or "")
            notificar(msg, type="positive" if ok else "negative")
            if ok:
                dlg.close()
                if ao_concluir:
                    try:
                        ao_concluir()
                    except Exception as e:
                        lg = _login_erro_log()
                        if lg:
                            lg.exception(
                                f"troca_senha: callback de {nome_usuario} falhou: {e}")

        _botao_tema("Salvar nova senha", on_click=confirmar,
                    extra_classes="w-full mt-2")
    # persistent: não fecha com ESC/clique fora — a troca é realmente obrigatória
    dlg.props("persistent")
    dlg.open()


def _dialogo_telefones(nome_usuario: str, ao_concluir=None):
    """Força o cadastro dos telefones no primeiro acesso (persistent).

    EN: First-access phone registration. The transparency portal publishes
    name, unit and role — but no extension. So the extension only exists if
    the server types it here, which is why this dialog is mandatory.

    PT-BR: Cadastro dos telefones no primeiro acesso. O portal da
    transparência publica nome, unidade e cargo — mas não o ramal. Então o
    número só existe se o servidor o informar aqui, e é por isso que este
    diálogo é obrigatório.

    A CONSENTIMENTO — cada linha da prefeitura é escolha de quem atende:

    - **celular particular**: começa desmarcado, e é assim que o prefeito
      resolve não ter o número na lista. Ninguém precisa explicar nada a
      ninguém.
    - **celular da prefeitura**: começa desmarcado também, e é assim que o
      responsável pela defesa civil resolve aparecer para todos. Quem atende
      emergência liga de qualquer lugar; precisa ser achado.
    - **fixo da prefeitura**: a caixa vem **travada marcada**. Linha
      institucional existe para ser encontrada — é o número que a prefeitura
      divulga em visita de rotina. Guardá-lo tornaria o cadastro inútil para
      o fim a que ele serve.
    - **residencial**: não tem caixa nenhuma. Telefone de casa não entra em
      cadastro de servidor, ponto.
    """
    from mod_gest_cad_usuario import bd_manipulador as _bd_usuarios

    # Diálogo de FORMULÁRIO: 4 campos, 4 caixas de consentimento e texto longo
    # de instrução. A 620px ele virava uma coluna alta; agora tem 88vw, teto de
    # 90vh e só o miolo rola. Os `data-testid` das caixas de consentimento são
    # contrato do QA (`assets/test/test_primeiro_acesso_e2e.py`) e ficam como
    # estavam.
    with ui_comum.dialogo_formulario(
            chave_modulo="intranet", sem_descricao=True) as (dlg, card, miolo, grade):
        ui.label("Seus telefones").classes("text-h6")
        ui.label(f"{autenticacao.nome_de_tratamento(nome_usuario)}, "
                 "falta o passo que faz você aparecer na lista telefônica. "
                 "Preencha o que quiser e marque o que pode ficar público.").classes(
            "text-body2 text-grey-7")

        # Grade só dos CAMPOS. Cada par (campo + caixa) é uma célula: a caixa
        # fica logo abaixo do seu campo, e o par inteiro ocupa uma coluna —
        # juntar os quatro campos numa linha e as caixas noutra desamarraria
        # quem responde "pode aparecer?" de qual número é.
        with grade:
            with ui.column().classes("w-full gap-1"):
                # ---- celular particular ----
                cel_pessoal = ui_comum.campo_texto(
                    "Celular particular", props="outlined dense",
                    placeholder="(35) 99999-0000")
                chk_pessoal = ui.checkbox("Pode aparecer na lista telefônica")
                chk_pessoal.props("dense data-testid=primeiro-acesso-chk-pessoal") \
                    .classes("text-body2")

            with ui.column().classes("w-full gap-1"):
                # ---- celular da prefeitura ----
                cel_empresa = ui_comum.campo_texto(
                    "Celular da prefeitura", props="outlined dense",
                    placeholder="(35) 99999-0000")
                chk_empresa = ui.checkbox("Pode aparecer na lista telefônica")
                chk_empresa.props("dense data-testid=primeiro-acesso-chk-empresa") \
                    .classes("text-body2")

            with ui.column().classes("w-full gap-1"):
                # ---- fixo da prefeitura ----
                fixo_empresa = ui_comum.campo_texto(
                    "Telefone fixo da prefeitura", props="outlined dense",
                    placeholder="(00) 3591-5100")
                chk_fixo = ui.checkbox("Aparece na lista telefônica")
                # Marcada E travada. A ordem importa: `value` antes de `disable`,
                # senão o NiceGUI aplica `disable` e a atribuição seguinte é
                # ignorada — e a tela mostrava uma caixa vazia ao lado de um texto
                # que dizia que ela apareceria. A regra que manda é a de
                # `telefone_e_publicavel`, não a do formulário; aqui só se
                # mostra o que ela faz.
                chk_fixo.props("dense disable data-testid=primeiro-acesso-chk-fixo") \
                    .classes("text-body2 text-grey-6")
                chk_fixo.value = True

            with ui.column().classes("w-full gap-1"):
                # ---- telefone de recado ----
                chk_recado = ui.checkbox(
                    "Não tenho linha própria: este é o telefone do setor, para recado")
                chk_recado.props("dense data-testid=primeiro-acesso-chk-recado") \
                    .classes("text-body2")

                # ---- residencial ----
                fixo_pessoal = ui_comum.campo_texto(
                    "Telefone residencial (opcional)", props="outlined dense",
                    placeholder="(00) 3800-0000")
                ui.label("O residencial fica só no seu cadastro — nunca sai na "
                         "lista telefônica.").classes("text-caption text-grey-6")

        # fora da grade: as explicações e o aviso de faixa são texto corrido e
        # ocupam a largura toda, não uma coluna estreita da grade
        ui.label("Marque quando for o telefone do SETOR: a garagem, a "
                 "secretaria da escola, a unidade de saúde, o almoxarifado. "
                 "Quem receber a ligação anota o recado e passa adiante — "
                 "é assim que a lista telefônica funciona para quem não "
                 "atende.").classes("text-caption text-grey-6")

        # aviso de faixa, preenchido enquanto o servidor digita
        aviso_faixa = ui.label("").classes("text-caption text-orange-8")

        def _montar_contatos():
            """Os 4 campos viram a lista que o cadastro grava."""
            contatos = []
            if (cel_pessoal.value or "").strip():
                contatos.append({"numero": cel_pessoal.value, "papel": "pessoal",
                                 "tipo": "celular", "visivel": chk_pessoal.value})
            if (cel_empresa.value or "").strip():
                contatos.append({"numero": cel_empresa.value, "papel": "empresa",
                                 "tipo": "celular", "visivel": chk_empresa.value})
            if (fixo_empresa.value or "").strip():
                # visivel=1 fixo: é a regra da prefeitura
                # (telefone_e_publicavel) — o checkbox travado acima é só o
                # espelho visual dela, a decisão real fica no banco.
                contatos.append({"numero": fixo_empresa.value, "papel": "empresa",
                                 "tipo": "fixo", "visivel": True,
                                 "recado": bool(chk_recado.value)})
            if (fixo_pessoal.value or "").strip():
                contatos.append({"numero": fixo_pessoal.value, "papel": "pessoal",
                                 "tipo": "fixo", "visivel": False})
            return contatos

        def _reavaliar_faixa(_evento=None):
            """Avisa, ENQUANTO digita, se o fixo está fora das faixas.

            Mostrar o aviso depois de salvar é tarde: o servidor já salvou, já
            recebeu o "telefones registrados" e só depois descobre que o
            número estava errado. A faixa existe para pegar o erro no dedo,
            não no relatório.

            Registrado com `on_value_change`, que é o caminho do próprio
            projeto (`campo_texto(ao_mudar=...)`); `on("update:model-value")`
            também funcionaria, mas mistura duas formas de fazer a mesma
            coisa no mesmo arquivo."""
            try:
                num = (fixo_empresa.value or "").strip()
                if not num:
                    aviso_faixa.set_text("")
                    return
                avalio = _bd_usuarios.avaliar_telefones_primeiro_acesso(
                    [{"numero": num, "papel": "empresa", "tipo": "fixo"}])
                fora = avalio.get("fora_da_faixa") or []
                if not fora:
                    aviso_faixa.set_text("")
                    return
                perto = fora[0][1] if len(fora[0]) > 1 else ""
                aviso_faixa.set_text(
                    f"Atenção: {num} está fora das faixas de telefone da "
                    f"prefeitura."
                    + (f" A faixa mais próxima é a {perto} — confira o número."
                       if perto else " Confira o número."))
            except Exception as e:
                lg = _login_erro_log()
                if lg:
                    lg.exception(f"primeiro_acesso: aviso de faixa falhou: {e}")
                aviso_faixa.set_text("")

        fixo_empresa.on_value_change(_reavaliar_faixa)

        def _salvar(liberacao_provisoria=False):
            """Grava. `liberacao_provisoria` é o paliativo do servidor que não
            sabe o próprio número — só chega True depois das DUAS confirmações."""
            contatos = _montar_contatos()
            try:
                ok, msg, detalhes = _bd_usuarios.registrar_contatos_primeiro_acesso(
                    nome_usuario, nome_usuario, contatos,
                    liberacao_provisoria=liberacao_provisoria)
            except Exception as e:
                lg = _login_erro_log()
                if lg:
                    lg.exception(
                        f"primeiro_acesso: falha ao gravar telefones de {nome_usuario}: {e}")
                notificar("Erro ao salvar os telefones — tente de novo.", tipo="error")
                return
            if not ok:
                notificar(msg, tipo="negative")
                return
            notificar(msg, tipo="positive")
            fora = (detalhes or {}).get("fora_da_faixa") or []
            if fora:
                # o salvou, mas o número não é nosso: fala alto, porque o
                # próximo passo do servidor é justamente confiar no número
                notificar(
                    f"{len(fora)} telefone(s) fora das faixas da prefeitura — "
                    f"veja o aviso no formulário e ajuste depois.",
                    tipo="warning")
            if (detalhes or {}).get("provisorio"):
                dias = _bd_usuarios.DIAS_LIBERACAO_PROVISORIA
                _aviso_provisorio(nome_usuario, dias)
            dlg.close()
            if ao_concluir:
                try:
                    ao_concluir()
                except Exception as e:
                    lg = _login_erro_log()
                    if lg:
                        lg.exception(
                            f"primeiro_acesso: falha no pós-conclusão de {nome_usuario}: {e}")

        def _confirmar():
            """Primeira trava: pergunta pelo telefone da prefeitura."""
            try:
                avalio = _bd_usuarios.avaliar_telefones_primeiro_acesso(
                    _montar_contatos())
            except Exception as e:
                lg = _login_erro_log()
                if lg:
                    lg.exception(f"primeiro_acesso: avaliação falhou: {e}")
                _salvar()
                return
            if avalio.get("tem_da_prefeitura"):
                _salvar()
                return
            if not avalio.get("particulares"):
                notificar("Informe também um telefone particular de contato.",
                          tipo="negative")
                return
            _travas_falta_numero(nome_usuario, _salvar)

        _botao_tema("Salvar telefones", on_click=_confirmar,
                    extra_classes="w-full mt-2")
    dlg.props("persistent")
    dlg.open()


def _travas_falta_numero(nome_usuario, ao_confirmar):
    """As DUAS travas quando o servidor não sabe o número da prefeitura.

    A primeira pergunta se ele quer sair e descobrir o número. A segunda
    confirma que ele entendeu o preço: acesso por 4 dias, e depois a conta
    fecha até o DTI abrir.

    Duas travas em vez de uma não é desconfiança do servidor — é o contrário.
    A única falha que sobra é o clique apressado numa tela de advertência, e
    ele passa por duas. Um servidor que leu o aviso duas vezes e seguiu em
    frente é alguém que entendeu; alguém que clicou uma vez pode ter só
    lido a primeira linha."""
    with ui.dialog() as dlg_t:
        with ui.card().classes("w-[520px] gap-3"):
            ui.label("Falta um telefone da prefeitura").classes("text-h6")
            ui.label(
                "Todo servidor da prefeitura está ligado a uma secretaria ou "
                "a um setor, e todo setor tem telefone. O sistema precisa de um "
                "número institucional para você constar na lista telefônica.") \
                .classes("text-body2 text-grey-7")
            ui.label("Se você não tem linha própria, use o telefone do seu "
                     "setor e marque como telefone de recado: a garagem, a "
                     "secretaria da escola, a unidade de saúde, o "
                     "almoxarifado. Quem receber anota e passa adiante.") \
                .classes("text-body2 text-grey-7")
            with ui.row().classes("w-full justify-end").style("gap: 0.5rem"):
                ui.button("Informar o telefone do setor", on_click=dlg_t.close) \
                    .props("flat")
                _botao_tema("Não sei meu número", on_click=lambda: _travas_confirmar(
                    nome_usuario, ao_confirmar, dlg_t),
                    variante="secundario")
    dlg_t.open()


def _travas_confirmar(nome_usuario, ao_confirmar, dlg_anterior):
    """Segunda trava: o preço, escrito."""
    from mod_gest_cad_usuario import bd_manipulador as _bd

    dias = _bd.DIAS_LIBERACAO_PROVISORIA
    with ui.dialog() as dlg_c:
        with ui.card().classes("w-[520px] gap-3"):
            ui.label("Acesso temporário").classes("text-h6")
            ui.label(
                f"Sem o número, seu acesso fica liberado por {dias} dias. "
                f"Depois disso a conta é bloqueada e só o DTI consegue "
                f"reabrir.").classes("text-body2 text-grey-7")
            ui.label(
                "Use esses 4 dias para descobrir o seu número: pergunte na "
                "secretaria da sua escola, na unidade de saúde onde você "
                "trabalha, no setor de empilhadeiras, na garagem ou no "
                "almoxarifado. Depois, volte aqui pelo seu perfil e atualize "
                "o telefone — o acesso fica definitivo.").classes(
                "text-body2 text-grey-7")
            with ui.row().classes("w-full justify-end").style("gap: 0.5rem"):
                ui.button("Voltar e informar o número", on_click=dlg_c.close) \
                    .props("flat")
                _botao_tema("Entendo, liberar por enquanto",
                            on_click=lambda: (
                                dlg_c.close(), dlg_anterior.close(),
                                ao_confirmar(True)),
                            variante="primario")
    dlg_c.open()


def _aviso_provisorio(nome_usuario, dias):
    """O bilhete que fica na tela depois de entrar em liberação temporária."""
    try:
        with ui.dialog() as dlg_p:
            with ui.card().classes("w-[480px] gap-2"):
                ui.label("Acesso liberado por enquanto").classes("text-h6")
                ui.label(f"Você tem {dias} dias para descobrir o seu número de "
                         f"contato na prefeitura e atualizar o cadastro. "
                         f"Depois disso o acesso será bloqueado.").classes(
                    "text-body2 text-grey-7")
                ui.label("Enquanto o acesso é temporário, seu nome aparece na "
                         "lista telefônica, mas sem número — a prefeitura "
                         "ainda não sabe como falar com você.").classes(
                    "text-caption text-grey-6")
                _botao_tema("Entendi", on_click=dlg_p.close)
        dlg_p.open()
    except Exception as e:
        lg = _login_erro_log()
        if lg:
            lg.exception(f"aviso provisório falhou: {e}")


def _dialogo_dados_pendentes(nome_usuario: str, ao_concluir=None):
    """Avisa que a folha de pagamento trouxe dado diferente do cadastro.

    A folha é atualizada todo mês e traz secretaria, departamento e cargo. O
    sistema NÃO sobrescreve o cadastro de quem já existe: marca a pendência e
    pergunta à própria pessoa. A pergunta é o ponto — setor tem dois donos
    possíveis (a folha e a pessoa), e só a pessoa sabe qual é o certo.

    Dá para recusar ("continua como está"), e isso também é resposta: a folha
    pode estar errada, e uma pessoa que discorda de um sistema tem razão para
    discordar.
    """
    try:
        from mod_gest_cad_usuario import bd_manipulador as _bd_usuarios
        info = _bd_usuarios.informacao_pendencia(nome_usuario)
        if not info.get("tem"):
            if ao_concluir:
                ao_concluir()
            return
        descricao = info.get("descricao") or "seus dados funcionais mudaram"
        dias = int(info.get("dias") or 0)
    except Exception as e:
        lg = _login_erro_log()
        if lg:
            lg.exception(f"dialogo de pendência: leitura falhou para "
                         f"{nome_usuario}: {e}")
        if ao_concluir:
            ao_concluir()
        return

    def _salvar(novo_depto: str, novo_cargo: str, unidade: str):
        """Grava o que a pessoa confirmou. Falhou, a pendência fica."""
        try:
            ok, msg = _bd_usuarios.confirmar_pendencia_dados(
                nome_usuario, nome_usuario, unidade=unidade or None,
                lotacao=novo_depto or None, cargo=novo_cargo or None)
            notificar(msg or ("Dados atualizados." if ok
                              else "Não foi possível atualizar."),
                      type="positive" if ok else "negative")
        except Exception as e:
            lg = _login_erro_log()
            if lg:
                lg.exception(f"diálogo de pendência: gravar falhou para "
                             f"{nome_usuario}: {e}")
            notificar("Não foi possível atualizar seus dados agora.",
                      type="negative")
        finally:
            if ao_concluir:
                ao_concluir()

    try:
        with ui.dialog() as dlg_d:
            with ui.card().classes("w-[560px] gap-3"):
                ui.label("A folha de pagamento mudou o seu cadastro").classes("text-h6")
                # Só a PRIMEIRA letra desce. `descricao.lower()` inteiro
                # quebraria o nome próprio do setor — "Obras" viraria "obras" —
                # e a pessoa lê o próprio departamento com letra minúscula
                # como se fosse erro de digitação do sistema.
                meio = descricao[:1].lower() + descricao[1:]
                ui.label(f"A folha de pagamento foi atualizada e {meio} Por isso "
                         f"o cadastro só muda com a sua confirmação — o sistema "
                         f"não sobrescreve o que está gravado por causa de um "
                         f"arquivo.").classes("text-body2 text-grey-7")
                if dias > 7:
                    ui.label(f"Esta pendência está aberta há {dias} dias. Se "
                             f"estiver correta, confirme; se não estiver, "
                             f"avise o DTI para corrigir a folha.").classes(
                        "text-caption text-orange-8")
                # O que o servidor responde: como é hoje, para ele escrever.
                # Em branco = mantém o que já está gravado, sem apagar.
                inp_unidade = ui.input("Secretaria").props("outlined dense") \
                    .classes("w-full").props("data-testid=pendencia-dados-unidade")
                inp_depto = ui.input("Departamento").props("outlined dense") \
                    .classes("w-full").props("data-testid=pendencia-dados-departamento")
                inp_cargo = ui.input("Cargo").props("outlined dense") \
                    .classes("w-full").props("data-testid=pendencia-dados-cargo")

                def _confirmar():
                    _salvar((inp_depto.value or "").strip(),
                            (inp_cargo.value or "").strip(),
                            (inp_unidade.value or "").strip())
                    dlg_d.close()

                def _manter():
                    try:
                        _bd_usuarios.confirmar_pendencia_dados(
                            nome_usuario, nome_usuario)
                        notificar("Cadastro mantido como estava. Avise o DTI "
                                  "se a folha estiver errada.", type="warning")
                    except Exception as e:
                        lg = _login_erro_log()
                        if lg:
                            lg.exception(f"diálogo de pendência: manter falhou "
                                         f"para {nome_usuario}: {e}")
                    finally:
                        dlg_d.close()
                        if ao_concluir:
                            ao_concluir()

                with ui.row().classes("w-full justify-end").style("gap: 0.5rem"):
                    _botao_tema("Está certo, confirmar", on_click=_confirmar) \
                        .props("data-testid=pendencia-dados-confirmar")
                    _botao_tema("Manter como está", on_click=_manter,
                                variante="secundario") \
                        .props("data-testid=pendencia-dados-manter")
        dlg_d.open()
    except Exception as e:
        lg = _login_erro_log()
        if lg:
            lg.exception(f"diálogo de pendência: abrir falhou para "
                         f"{nome_usuario}: {e}")
        if ao_concluir:
            ao_concluir()


def _primeiro_acesso(nome_usuario: str):
    """Encadeia os passos obrigatórios do primeiro acesso.

    Ordem: senha -> telefones. Não dá para pular a senha; e não dá para
    cadastrar telefone de quem ainda entra com a senha provisória
    `123456`, que todo servidor da prefeitura conhece. Cada passo só abre
    o próximo quando o anterior foi realmente concluído — um diálogo de
    senha que fecha sem trocar deixaria o telefone para trás, e o servidor
    entraria no sistema com a pendência e sem saber por quê."""
    def abrir_telefones(novo_nome=None):
        """Abre o cadastro de telefones se ainda estiver pendente.

        `novo_nome` vem dos diálogos de credenciais, em que o login muda de
        `master` para o nome escolhido — a pendência do telefone está no
        usuário NOVO, não no `master` que já saiu de cena.

        A pendência de DADOS vem DEPOIS da do telefone, e só se o telefone
        estiver resolvido. A ordem não é estética: são duas perguntas para a
        mesma pessoa, no mesmo minuto, e quem responde a segunda já não está
        mais ledindo o formulário da primeira."""
        try:
            from mod_gest_cad_usuario import bd_manipulador as _bd_usuarios
            alvo = novo_nome or nome_usuario
            if _bd_usuarios.telefone_pendente(alvo):
                _dialogo_telefones(alvo, ao_concluir=lambda: _abrir_dados(alvo))
                return
            _abrir_dados(alvo)
        except Exception as e:
            lg = _login_erro_log()
            if lg:
                lg.exception(
                    f"primeiro_acesso: falha ao verificar telefone de "
                    f"{novo_nome or nome_usuario}: {e}")

    def _abrir_dados(alvo):
        """A pendência de dados, quando existir, com o telefone já resolvido."""
        try:
            _dialogo_dados_pendentes(alvo)
        except Exception as e:
            lg = _login_erro_log()
            if lg:
                lg.exception(f"primeiro_acesso: falha ao verificar pendência "
                             f"de dados de {alvo}: {e}")

    try:
        if autenticacao.precisa_trocar_credenciais(nome_usuario):
            _dialogo_troca_credenciais(nome_usuario, ao_concluir=abrir_telefones)
            return
        if autenticacao.precisa_trocar_senha(nome_usuario):
            _dialogo_troca_senha(nome_usuario, ao_concluir=abrir_telefones)
            return
        abrir_telefones()
    except Exception as e:
        lg = _login_erro_log()
        if lg:
            lg.exception(
                f"primeiro_acesso: falha ao montar o fluxo de {nome_usuario}: {e}")


def _obter_cor_principal():
    """Reads the system primary color from config, falling back to the palette.

    Lê a cor principal do sistema em `tb_config` (chave `cor_principal`);
    em ausência do valor ou falha de conexão usa `ui_comum.CORES["primaria"]`.
    """
    from mod_intranet.bd_conexao import get_connection
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT valor FROM tb_config WHERE chave='cor_principal'")
        row = cur.fetchone()
        conn.close()
        return row[0] if row else ui_comum.CORES["primaria"]
    except Exception:
        return ui_comum.CORES["primaria"]


def _obter_versao():
    from mod_intranet.bd_conexao import get_connection
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT valor FROM tb_config WHERE chave='versao_sistema'")
        row = cur.fetchone()
        conn.close()
        return row[0] if row else "1.0"
    except Exception:
        return "1.0"


def _obter_versao_modulo(chave_modulo):
    """Versão individual do módulo (chave 'versao_modulo:<chave>' em tb_config).

    Formato 1.0.AAMMDD, no mesmo estilo da versão do sistema. Se o módulo ainda
    não tem versão registrada, retorna a padrão '1.0'.
    """
    from mod_intranet.bd_conexao import get_connection
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT valor FROM tb_config WHERE chave=?",
                    (f"versao_modulo:{chave_modulo}",))
        row = cur.fetchone()
        conn.close()
        return row[0] if row else "1.0"
    except Exception:
        return "1.0"


def _parse_versao(v: str):
    """Parse 'X.Y.AAMMDD' ou 'X.Y' -> (major, minor, patch)."""
    parts = v.split(".")
    major = int(parts[0]) if parts else 1
    minor = int(parts[1]) if len(parts) > 1 else 0
    patch = parts[2] if len(parts) > 2 else ""
    return major, minor, patch


def _mesclar_patch(patch_sis: str, patch_mod: str) -> str:
    """Mescla patches AAMMDD conforme regras: oculta ano/mês/dia iguais."""
    if not patch_sis or not patch_mod or patch_sis == patch_mod:
        return patch_sis
    aa1, mm1, dd1 = patch_sis[:2], patch_sis[2:4], patch_sis[4:6]
    aa2, mm2, dd2 = patch_mod[:2], patch_mod[2:4], patch_mod[4:6]
    if aa1 == aa2:
        if mm1 == mm2:
            return f"{patch_sis}.{dd2}"
        return f"{patch_sis}.{mm2}{dd2}"
    return f"{patch_sis}.{patch_mod}"


def _formatar_versao_rodape(versao_sistema: str, versao_modulo: str = None):
    """Retorna sempre uma única string com a versão mesclada para exibição.

    Formato: v{major}.{minor}.{patch_sis}[.{parte_mod}]
    - Sem módulo: v{versao_sistema}
    - major.minor iguais: mescla ocultando AAMMDD iguais (v1.0.260829.28,
      v1.0.260829.0717, v1.0.260828.250412)
    - major.minor diferentes: mostra ambos separados por ' · '
    """
    if not versao_modulo:
        return f"v{versao_sistema}"

    major_sis, minor_sis, patch_sis = _parse_versao(versao_sistema)
    major_mod, minor_mod, patch_mod = _parse_versao(versao_modulo)

    if major_sis != major_mod or minor_sis != minor_mod:
        return f"v{versao_sistema} · v{versao_modulo}"

    base = f"v{major_sis}.{minor_sis}"
    if patch_sis and patch_mod:
        mesclado = _mesclar_patch(patch_sis, patch_mod)
        return f"{base}.{mesclado}"
    if patch_sis or patch_mod:
        return f"{base}.{patch_sis or patch_mod}"
    return base
