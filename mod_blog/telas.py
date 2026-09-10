"""Blog module screen — posts and comments with NH3 sanitization.

Tela do módulo Blog — postagens e comentários com sanitização NH3.

Inclui: criação/edição com pré-visualização, modos de exibição
única/histórico/carrossel (rotação automática com resumo e leitura
completa). Administração via menu hambúrguer (rota /admin/blog).
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from nicegui import ui
from mod_intranet import observabilidade
from mod_intranet.aba_modulo import cabecalho, abas, campo_busca
from mod_intranet.tema_modulo import ler_tema
from mod_intranet.ui_comum import (campo_selecao, campo_texto, botao,
                                   botao_icone)


def _renderizar_conteudo_postagem(conteudo):
    """Renders post content supporting Mermaid diagrams (ui.mermaid).

    Divide o conteúdo sanitizado em segmentos via
    `extrair_segmentos_mermaid`; texto é renderizado com
    `formatar_conteudo_para_exibicao` (ui.html) e blocos ```mermaid via
    `ui.mermaid` (bundle embutido do NiceGUI, sem CDN). Quando o recurso
    está desabilitado, renderiza todo o conteúdo como texto."""
    from mod_blog.bd_manipulador import (
        extrair_segmentos_mermaid, formatar_conteudo_para_exibicao,
        obter_habilitar_mermaid,
    )
    if not obter_habilitar_mermaid():
        html_seguro = formatar_conteudo_para_exibicao(conteudo or "")
        if html_seguro:
            ui.html(html_seguro).classes("text-body2 text-grey-8")
        return
    for tipo, trecho in extrair_segmentos_mermaid(conteudo or ""):
        if tipo == "mermaid":
            try:
                ui.mermaid(trecho).classes("w-full my-2") \
                    .style("overflow-x: auto")
            except Exception:
                observabilidade.get_logger("blog").exception(
                    "mermaid: falha ao renderizar diagrama")
                ui.label("(diagrama inválido)").classes(
                    "text-caption text-grey-5 italic")
        else:
            html_seguro = formatar_conteudo_para_exibicao(trecho or "")
            if html_seguro:
                ui.html(html_seguro).classes("text-body2 text-grey-8")


def _card_postagem(post, usuario_logado, perfil, ao_atualizar, pode_publicar=False,
                   ao_editar=None):
    """Renders one post card with comments and admin actions.

    Card de postagem: título, autor/data, conteúdo renderizado via
    `_renderizar_conteudo_postagem` (texto formatado por
    `formatar_conteudo_para_exibicao` + diagramas ```mermaid via `ui.mermaid`),
    comentários em expansão com contador
    e campo de comentário (só para quem pode publicar). Ações de admin:
    editar (via `ao_editar`), despublicar e excluir (soft delete) — todas com
    try/except + loguru e notificação do resultado."""
    from mod_blog.bd_manipulador import (
        listar_comentarios, excluir_postagem, despublicar_postagem,
    )

    pid, titulo, conteudo, autor, data = post[0], post[1], post[2], post[3], (post[4] or "")[:16]

    from mod_intranet.tema_modulo import ler_tema
    tema = ler_tema("blog", cor_botao="#000000", cor_texto_botao="#FFFFFF")
    cor_borda = tema["cor_botao"] or "#000000"

    with ui.card().classes("w-full shadow-md border-l-8").style(
            f"border-left-color:{cor_borda}"):
        with ui.row().classes("w-full items-start justify-between flex-wrap"):
            with ui.column().classes("gap-0 grow"):
                ui.label(titulo or "(sem título)").classes("text-h6 font-bold text-grey-9")
                ui.label(f"por {autor} • {data}").classes("text-caption text-grey-6")
        with ui.column().classes("w-full mt-1"):
            _renderizar_conteudo_postagem(conteudo or "")
            if not (conteudo or "").strip():
                ui.label("(sem conteúdo)").classes("text-body2 italic text-grey-5")
        if pode_publicar:
            with ui.row().classes("w-full justify-end items-center") \
                    .style("gap: 0.25rem; margin-top: 0.25rem"):
                if ao_editar is not None:
                    botao_icone("edit",
                                on_click=lambda: ao_editar(
                                    pid, titulo, conteudo),
                                tooltip="Editar", chave_modulo="blog") \
                        .props('data-testid=blog-editar')
                botao_icone("visibility_off",
                            on_click=lambda: _despublicar(
                                pid, usuario_logado, ao_atualizar),
                            tooltip="Despublicar", chave_modulo="blog") \
                    .props('data-testid=blog-despublicar')
                botao_icone("delete",
                            on_click=lambda: _excluir(
                                pid, usuario_logado, ao_atualizar),
                            tooltip="Excluir", chave_modulo="blog") \
                    .props('data-testid=blog-excluir')
        comentarios = listar_comentarios(pid)
        with ui.expansion(f"Comentários ({len(comentarios)})").classes("w-full"):
            for cid, cautor, ctexto, cdata in comentarios:
                with ui.row().classes("w-full items-start gap-2 py-1 border-b"):
                    ui.icon("chat_bubble_outline").classes("text-grey-5")
                    ui.html(f"<b>{_esc(cautor)}</b> "
                            f"<span class='text-grey-6 text-xs'>{(cdata or '')[:16]}</span>"
                            f"<br>{_sanitizar(ctexto or '')}")
            if pode_publicar:
                novo = ui.input(placeholder="Escreva um comentário...").props(
                    "outlined dense").classes("w-full")

                def enviar(pid=pid, novo=novo):
                    from mod_blog.bd_manipulador import criar_comentario
                    if not (novo.value or "").strip():
                        return
                    try:
                        ok = criar_comentario(pid, usuario_logado, novo.value.strip())
                    except Exception:
                        observabilidade.get_logger("blog").exception(
                            f"Erro ao comentar na postagem #{pid}")
                        ok = False
                    if ok:
                        novo.set_value(None)
                        ui.notify("Comentário publicado", type="positive")
                        ao_atualizar()
                    else:
                        ui.notify("Erro ao comentar", type="negative")

                novo.on("keydown.enter", enviar)
            else:
                ui.label("Somente administradores podem comentar.").classes(
                    "text-caption text-grey-5 italic")


def _despublicar(pid, usuario_logado, ao_atualizar):
    from mod_blog.bd_manipulador import despublicar_postagem
    try:
        if despublicar_postagem(pid, usuario_logado):
            ui.notify("Postagem despublicada", type="info")
            ao_atualizar()
        else:
            ui.notify("Não foi possível despublicar (permissão?)",
                      type="negative")
    except Exception:
        observabilidade.get_logger("blog").exception(f"Erro ao despublicar #{pid}")
        ui.notify("Erro ao despublicar postagem", type="negative")


def _excluir(pid, usuario_logado, ao_atualizar):
    from mod_blog.bd_manipulador import excluir_postagem
    try:
        if excluir_postagem(pid, usuario_logado):
            ui.notify("Postagem removida", type="info")
            ao_atualizar()
        else:
            ui.notify("Não foi possível excluir (permissão?)", type="negative")
    except Exception:
        observabilidade.get_logger("blog").exception(f"Erro ao excluir #{pid}")
        ui.notify("Erro ao excluir postagem", type="negative")


def _esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _sanitizar(texto):
    from mod_blog.bd_manipulador import tags_permitidas, _URL_SCHEMES, _ATTRS
    from nh3 import clean
    try:
        return clean(texto, tags=tags_permitidas(), attributes=_ATTRS,
                     url_schemes=_URL_SCHEMES, url_relative="pass_through")
    except Exception:
        return _esc(texto)


def _painel_despublicadas(usuario_logado):
    """Admin-only panel listing unpublished posts with a 'Republicar' action.

    Painel da aba "Despublicadas" (exclusivo do administrador do blog):
    lista as postagens com `ativo=0` e oferece o botão Republicar
    (`publicar_postagem` com auditoria) por linha. Recarrega a lista após
    republicar (a postagem volta ao feed público)."""
    from mod_blog.bd_manipulador import listar_postagens, publicar_postagem
    wrap = ui.column().classes("w-full gap-2")

    def carregar():
        wrap.clear()
        inativos = listar_postagens(ativo=False, ordem="DESC")
        with wrap:
            if not inativos:
                ui.label("Nenhuma postagem despublicada.").classes(
                    "text-caption text-grey-5 italic")
            for ipost in inativos:
                iid, itit, _, iautor, idata = ipost[:5]
                with ui.row().classes(
                        "w-full items-center justify-between border-b py-1"):
                    ui.label(
                        f"#{iid} — {itit or '(sem título)'} "
                        f"({iautor}, {(idata or '')[:10]})").classes(
                        "text-body2 text-grey-8")

                    def republicar(iid=iid):
                        if publicar_postagem(iid, usuario_logado):
                            ui.notify(f"Postagem #{iid} republicada",
                                      type="positive")
                            carregar()
                        else:
                            ui.notify("Erro ao republicar", type="negative")

                    botao("Republicar", icone="visibility",
                          on_click=republicar, variante="texto",
                          chave_modulo="blog")

    carregar()


def _resumo_conteudo(conteudo, limite=220):
    """Extracts a plain-text summary (no HTML/Markdown/Mermaid).

    Remove blocos ```mermaid (substitui por "[diagrama]"), tags HTML e
    caracteres de Markdown, colapsa espaços e trunca em `limite` caracteres
    (com reticências). Usado no preview do modo carrossel. Falha na limpeza
    registra warning e devolve o texto original (fail-soft)."""
    try:
        import re as _re
        texto = conteudo or ""
        texto = _re.sub(r"```mermaid.*?```", " [diagrama] ",
                        texto, flags=_re.DOTALL)
        texto = _re.sub(r"<[^>]+>", " ", texto)
        texto = _re.sub(r"[#*`_\[\]]", " ", texto)
        texto = _re.sub(r"\s+", " ", texto).strip()
        if len(texto) > limite:
            texto = texto[:limite].rstrip() + "…"
        return texto
    except Exception:
        observabilidade.get_logger("blog").exception(
            "resumo de conteúdo falhou; devolvendo texto original")
        return conteudo or ""


def _renderizar_carrossel(wrap, posts, tempo_seg, usuario_logado, perfil,
                          pode_publicar, ao_editar, ao_atualizar):
    """Renders a rotating carousel of selected posts (no min, auto slide).

    Exibe as postagens selecionadas uma por vez, avançando automaticamente a
    cada `tempo_seg` (configurável pelo admin). Em estado normal mostra um
    **resumo** de cada postagem (recorte em até 3 linhas via `_resumo_conteudo`);
    o botão "Leitura completa" pausa a rotação e expande a postagem inteira
    (`_card_postagem`). A barra de ações (Anterior, indicador "atual/total",
    Próxima e o botão de expandir/voltar) aparece no topo e no rodapé. Ao
    voltar ao carrossel, a rotação retoma. Falha na montagem registra
    exception no loguru e exibe aviso (fail-soft, sem crash da tela).

    NOTA (timer único): o `ui.timer` é criado UMA vez, FORA do `with wrap:` —
    recriá-lo a cada `montar()` acumulava timers no cliente e acelerava a
    rotação (ex.: configurado 10 s, girava em <2 s)."""
    idx = {"v": 0}
    expandido = {"v": False}
    from mod_intranet.tema_modulo import ler_tema as _ler_tema
    cor_borda = (_ler_tema("blog", cor_botao="#000000")["cor_botao"]
                 or "#000000")
    n = len(posts or [])

    def montar():
        wrap.clear()
        if n == 0:
            with wrap:
                ui.label("Nenhuma postagem selecionada para o carrossel. "
                         "Selecione ao menos 2 acima.").classes(
                    "text-body2 text-grey-6 italic")
            return
        i = idx["v"] % n
        post = posts[i]

        def anterior(i=i):
            idx["v"] = (i - 1) % n
            expandido["v"] = False
            montar()

        def proximo(i=i):
            idx["v"] = (i + 1) % n
            expandido["v"] = False
            montar()

        def expandir():
            expandido["v"] = True
            montar()

        def voltar():
            expandido["v"] = False
            montar()

        def barra_acoes():
            with ui.row().classes("w-full justify-center items-center"
                                  " flex-wrap").style("gap: 0.5rem"):
                botao_icone("chevron_left", on_click=anterior,
                            tooltip="Postagem anterior",
                            chave_modulo="blog") \
                    .props('aria-label="Postagem anterior"')
                ui.label(f"{i + 1} / {n}").classes(
                    "text-body2 text-grey-7 font-bold")
                botao_icone("chevron_right", on_click=proximo,
                            tooltip="Próxima postagem",
                            chave_modulo="blog") \
                    .props('aria-label="Próxima postagem"')
                if not expandido["v"]:
                    botao("Leitura completa", icone="fullscreen",
                          on_click=expandir, variante="contorno",
                          chave_modulo="blog")
                else:
                    botao("Voltar ao carrossel", icone="close_fullscreen",
                          on_click=voltar, variante="contorno",
                          chave_modulo="blog")

        def card_resumo():
            _tit, _conteudo, _autor, _data = (
                post[1], post[2], post[3], (post[4] or "")[:16])
            with ui.card().classes("w-full shadow-md border-l-8").style(
                    f"border-left-color:{cor_borda}"):
                ui.label(_tit or "(sem título)").classes(
                    "text-h6 font-bold text-grey-9")
                ui.label(f"por {_autor} • {_data}").classes(
                    "text-caption text-grey-6")
                resumo = _resumo_conteudo(_conteudo)
                if resumo:
                    ui.label(resumo).classes("text-body2 text-grey-8") \
                        .style("display:-webkit-box;"
                               "-webkit-line-clamp:3;"
                               "-webkit-box-orient:vertical;"
                               "overflow:hidden;")
                else:
                    ui.label("(sem conteúdo)").classes(
                        "text-body2 italic text-grey-5")

        with wrap:
            barra_acoes()
            if expandido["v"]:
                _card_postagem(post, usuario_logado, perfil, ao_atualizar,
                               pode_publicar=pode_publicar,
                               ao_editar=ao_editar if pode_publicar else None)
            else:
                card_resumo()
            barra_acoes()

    def avancar():
        if not expandido["v"] and n:
            idx["v"] = (idx["v"] + 1) % n
            montar()

    try:
        montar()
    except Exception:
        observabilidade.get_logger("blog").exception(
            "falha ao montar o carrossel de postagens")
        wrap.clear()
        with wrap:
            ui.label("Não foi possível exibir o carrossel.").classes(
                "text-body2 text-grey-6 italic")
        return
    # Timer ÚNICO da rotação — criado fora do `with wrap:` para não ser
    # destruído/recriado a cada `montar()` (evita aceleração).
    ui.timer(tempo_seg, avancar)


def mostrar_tela(usuario_logado: str, perfil: str):
    """Renders the blog screen (editor + feed + administration tab).

    Monta a tela do Blog: regra de permissão (`pode_publicar` — comum só
    lê), tema/aparência via `ler_tema("blog")`, editor com
    pré-visualização (criar/editar), alternância de modo de exibição
    (histórico/única/carrossel, persistida na config local), feed de
    postagens."""
    from mod_intranet import autenticacao
    from mod_intranet.crud_base import audit_reg
    from mod_blog.bd_manipulador import (
        set_config_local, tags_permitidas,
        obter_modo_exibicao, obter_postagem_unica_id,
        definir_postagem_unica_id, criar_postagem, atualizar_postagem,
    )

    pode_publicar = (perfil == "administrador_geral"
                     or autenticacao.eh_admin_do_modulo(usuario_logado, "blog"))

    tema = ler_tema("blog", cor_botao="#000000", cor_texto_botao="#FFFFFF",
                    texto_header="Comunique novidades para toda a equipe.")
    tema["_defaults"] = {
        "cor_botao": "#000000",
        "cor_texto_botao": "#FFFFFF",
        "cor_fundo": "",
        "cor_titulo": "#212121",
        "btn_tamanho": "medium",
        "texto_header": "Comunique novidades para toda a equipe.",
    }

    ui.colors(primary=tema["cor_botao"], accent=tema["cor_botao"])
    modo_atual = obter_modo_exibicao()

    cabecalho("Blog", tema["texto_header"], chave_modulo="blog",
              cor_titulo=tema["cor_titulo"], cor_fundo=tema["cor_fundo"])
    tabs_el = abas("Publicações", "article")
    if pode_publicar:
        with tabs_el:
            ui.tab("admin_blog", label="Despublicadas",
                   icon="inventory_2")
    with ui.tab_panels(tabs_el, value="principal").classes("w-full"):
        with ui.tab_panel("principal"):
            container = ui.column().classes("w-full gap-4")

            if pode_publicar:
                _edit_id = {"id": None}
                with ui.card().classes("w-full shadow-lg"):
                    with ui.card_section().classes("gap-2 w-full"):
                        titulo_edit = ui.label("Nova publicação").classes(
                            "text-h6 font-bold text-grey-9")
                        inp_titulo = ui.input("Título*").props(
                            "outlined dense").classes("w-full") \
                            .props('data-testid=blog-titulo')
                        inp_conteudo = ui.textarea(
                            "Conteúdo*", placeholder="Use <b>, <i>, <p>, HTML simples, "
                            "Markdown (#, **negrito**, - item), URLs de imagem "
                            "(data:/relativas aceitas) ou ```mermaid para diagramas"
                        ).props("outlined dense").classes("w-full") \
                            .props('data-testid=blog-conteudo')
                        preview_wrap = ui.column().classes("w-full hidden")

                        def atualizar_preview():
                            preview_wrap.clear()
                            if not (inp_conteudo.value or "").strip():
                                preview_wrap.classes(replace="w-full hidden")
                                return
                            preview_wrap.classes(replace="w-full")
                            preview_wrap.clear()
                            with preview_wrap:
                                ui.label("Pré-visualização").classes(
                                    "text-subtitle2 text-grey-7")
                                with ui.card().classes("w-full bg-grey-2 p-3"):
                                    _renderizar_conteudo_postagem(inp_conteudo.value)

                        def mostrar_preview():
                            atualizar_preview()

                        def publicar():
                            if not (inp_titulo.value or "").strip() or \
                               not (inp_conteudo.value or "").strip():
                                ui.notify("Preencha título e conteúdo", type="warning")
                                return
                            try:
                                if _edit_id["id"] is not None:
                                    ok = atualizar_postagem(
                                        _edit_id["id"], inp_titulo.value.strip(),
                                        inp_conteudo.value.strip(), usuario_logado)
                                    if ok:
                                        ui.notify(f"Publicação #{_edit_id['id']} atualizada",
                                                  type="positive")
                                else:
                                    pid = criar_postagem(inp_titulo.value.strip(),
                                                         inp_conteudo.value.strip(),
                                                         usuario_logado)
                                    if pid:
                                        ui.notify(f"Publicação #{pid} criada!",
                                                  type="positive")
                                        # modo 'unica': nova publicação volta a
                                        # ser a exibida (limpa fixação antiga)
                                        definir_postagem_unica_id(None)
                            except Exception:
                                observabilidade.get_logger("blog").exception(
                                    "Erro ao salvar postagem")
                                ui.notify("Erro ao salvar", type="negative")
                                return
                            _edit_id["id"] = None
                            titulo_edit.set_text("Nova publicação")
                            inp_titulo.set_value(None)
                            inp_conteudo.set_value(None)
                            preview_wrap.classes(replace="w-full hidden")
                            atualizar()

                        def cancelar_edicao():
                            _edit_id["id"] = None
                            titulo_edit.set_text("Nova publicação")
                            inp_titulo.set_value(None)
                            inp_conteudo.set_value(None)
                            preview_wrap.classes(replace="w-full hidden")
                            ui.notify("Edição cancelada", type="info")

                        def ao_editar(pid, titulo, conteudo):
                            _edit_id["id"] = pid
                            titulo_edit.set_text(f"Editar publicação #{pid}")
                            inp_titulo.set_value(titulo)
                            inp_conteudo.set_value(conteudo)
                            # Exceção intencional de "sem JS direto": scroll via
                            # `ui.run_javascript` (API oficial) — `ui.scroll_to`
                            # com selector=None falha no NiceGUI 3.15.
                            ui.run_javascript(
                                "window.scrollTo({top:0, behavior:'smooth'})")
                            atualizar_preview()

                        with ui.row().classes(
                                "w-full items-center flex-wrap") \
                                .style("gap: 0.5rem"):
                            botao("Pré-visualizar", icone="preview",
                                  on_click=mostrar_preview, variante="contorno",
                                  chave_modulo="blog")
                            botao("Publicar", icone="send",
                                  on_click=publicar, variante="solido",
                                  chave_modulo="blog") \
                                .props('data-testid=blog-publicar')
                            botao("Cancelar edição", icone="cancel",
                                  on_click=cancelar_edicao, variante="texto",
                                  chave_modulo="blog")

            with ui.row().classes("w-full items-center flex-wrap") \
            .style("gap: 0.5rem; margin-top: 0.5rem"):
                busca_termo = campo_busca(
                    "Buscar por título, conteúdo ou autor...",
                    on_change=lambda e: atualizar(),
                    tooltip="Filtra as publicações pelo termo digitado "
                            "(título, conteúdo ou autor).",
                ).props('data-testid=blog-busca')
                busca_data = campo_texto(
                    "Data (AAAA-MM-DD)",
                    placeholder="ex.: 2026-09-06",
                    ao_mudar=lambda e: atualizar(),
                    largura="w-44",
                    tooltip="Filtra pela data de publicação "
                            "(formato AAAA-MM-DD).",
                )

            # ---- Configurações de exibição (aplicadas SOMENTE em "Aplicar") ----
            from mod_blog.bd_manipulador import (
                listar_postagens, obter_modo_exibicao,
                obter_postagem_unica_id, obter_carrossel_postagens_ids,
                obter_carrossel_tempo, definir_carrossel_postagens_ids,
                definir_carrossel_tempo, definir_postagem_unica_id,
            )
            _admin = {
                "modo": obter_modo_exibicao(),
                "unica": obter_postagem_unica_id() or "",
                "sel": [str(i) for i in obter_carrossel_postagens_ids()],
                "tempo": obter_carrossel_tempo(),
            }
            admin_wrap = ui.column().classes("w-full gap-1")

            def render_admin():
                """Re-renders the blog display-config controls from `_admin`.

                Reconstrói os controles de exibição (modo, postagem única e
                carrossel) a partir do estado pendente `_admin`. NADA é
                persistido até o botão "Aplicar configurações" — mudanças de
                campo não são automáticas."""
                admin_wrap.clear()
                with admin_wrap:
                    with ui.row().classes(
                            "w-full items-center flex-wrap") \
                            .style("gap: 0.5rem; margin-top: 0.5rem"):
                        campo_selecao(
                            "Modo de exibição",
                            {"historico": "Histórico (lista completa)",
                             "unica": "Publicação única",
                             "carrossel": "Carrossel (rotação automática)"},
                            valor=_admin["modo"],
                            ao_mudar=lambda e: (_admin.update(modo=e.value),
                                                render_admin()),
                            largura="w-64",
                            tooltip="Exibir todas as postagens (histórico), "
                                    "apenas uma (única) ou um carrossel "
                                    "rotativo com as postagens selecionadas "
                                    "abaixo.",
                        )
                    if _admin["modo"] == "unica":
                        posts_ativos = listar_postagens(ativo=True,
                                                        ordem="DESC")
                        opcoes_post = {"": "Mais recente (automática)"}
                        for pp in posts_ativos:
                            _titulo = (pp[1] or "(sem título)")
                            opcoes_post[str(pp[0])] = (
                                f"#{pp[0]} — {_titulo[:60]}"
                                + ("…" if len(_titulo) > 60 else ""))
                        if str(_admin["unica"]) not in opcoes_post:
                            _admin["unica"] = ""
                        with admin_wrap:
                            campo_selecao(
                                "Postagem exibida (modo única)",
                                opcoes_post,
                                valor=str(_admin["unica"]),
                                ao_mudar=lambda e: _admin.update(unica=e.value),
                                largura="w-full max-w-xl",
                                tooltip="Qual postagem exibir no modo única. "
                                        "'Mais recente' mostra a última "
                                        "publicada (automático).",
                            )
                    if _admin["modo"] == "carrossel" and pode_publicar:
                        posts_car = listar_postagens(ativo=True, ordem="DESC")
                        opcoes_car = {str(pp[0]): (
                            f"#{pp[0]} — {(pp[1] or '(sem título)')[:60]}"
                            + ("…" if len(pp[1] or "") > 60 else ""))
                            for pp in posts_car}
                        _admin["sel"] = [v for v in _admin["sel"]
                                         if v in opcoes_car]
                        with admin_wrap:
                            select_car = ui.select(opcoes_car,
                                      label="Postagens do carrossel "
                                      "(selecione 2 ou mais)",
                                      value=_admin["sel"], multiple=True) \
                                .classes("w-full max-w-xl") \
                                .props("outlined dense chips") \
                                .tooltip("Quais postagens entram no carrossel. "
                                         "Somente as selecionadas aparecem, "
                                         "na ordem de exibição.") \
                                .on_value_change(
                                    lambda e: _admin.update(
                                        sel=[str(v) for v in (e.value or [])]))
                            ui.number("Tempo de exibição (segundos)",
                                      value=_admin["tempo"], min=1, step=1) \
                                .classes("w-56") \
                                .props("outlined dense") \
                                .tooltip("Intervalo entre as postagens no "
                                         "carrossel. Padrão: 10 segundos.") \
                                .on_value_change(
                                    lambda e: _admin.update(
                                        tempo=int(e.value or 1)))
                    with admin_wrap:
                        with ui.row().classes("w-full items-center") \
                                .style("gap: 0.5rem"):
                            botao("Aplicar configurações", icone="check",
                                  on_click=_aplicar_admin,
                                  chave_modulo="blog")
                            botao("Restaurar padrão", icone="restore",
                                  on_click=_restaurar_admin,
                                  variante="restaurar",
                                  chave_modulo="blog")

            def _aplicar_admin():
                """Persists modo + postagem única + carrossel on 'Aplicar'.

                Grava as configurações de exibição (modo, postagem fixada no
                modo única, ids e tempo do carrossel) SOMENTE quando o admin
                clica em "Aplicar configurações" — mudanças nos campos não
                são automáticas. Exige 2+ postagens no carrossel."""
                try:
                    set_config_local("blog_modo_exibicao", _admin["modo"])
                    definir_postagem_unica_id(_admin["unica"] or None)
                    ids = [int(v) for v in _admin["sel"]]
                    if _admin["modo"] == "carrossel" and len(ids) == 1:
                        ui.notify("Selecione ao menos 2 postagens para o "
                                  "carrossel.", type="warning")
                        return
                    definir_carrossel_postagens_ids(ids)
                    definir_carrossel_tempo(int(_admin["tempo"] or 1))
                    try:
                        audit_reg(usuario_logado, "blog", "configuracao",
                                  f"exibição: modo={_admin['modo']} "
                                  f"única={_admin['unica'] or '—'} "
                                  f"carrossel={ids} tempo={_admin['tempo']}s")
                    except Exception:
                        pass
                    ui.notify("Configurações de exibição aplicadas",
                              type="positive")
                    ui.timer(0.1, lambda: ui.navigate.reload(), once=True)
                except Exception:
                    observabilidade.get_logger("blog").exception(
                        "falha ao aplicar configurações de exibição")
                    ui.notify("Erro ao aplicar configurações", type="negative")

            def _restaurar_admin():
                """Restores display config (modo/única/carrossel) to defaults."""
                try:
                    set_config_local("blog_modo_exibicao", "historico")
                    definir_postagem_unica_id(None)
                    definir_carrossel_postagens_ids([])
                    definir_carrossel_tempo(10)
                    try:
                        audit_reg(usuario_logado, "blog", "configuracao",
                                  "exibição: padrões restaurados")
                    except Exception:
                        pass
                    ui.notify("Configurações de exibição restauradas ao padrão",
                              type="positive")
                    ui.timer(0.1, lambda: ui.navigate.reload(), once=True)
                except Exception:
                    observabilidade.get_logger("blog").exception(
                        "falha ao restaurar configurações de exibição")
                    ui.notify("Erro ao restaurar configurações",
                              type="negative")

            render_admin()

            posts_wrap = ui.column().classes("w-full gap-4")

            def atualizar():
                from mod_blog.bd_manipulador import listar_postagens
                posts_wrap.clear()
                modo = obter_modo_exibicao()
                posts = listar_postagens(ativo=True, ordem="DESC")
                termo = (busca_termo.value or "").strip().lower()
                data_f = (busca_data.value or "").strip()
                if termo:
                    posts = [p for p in posts if
                             termo in ((p[1] or "").lower())
                             or termo in ((p[2] or "").lower())
                             or termo in ((p[3] or "").lower())]
                if data_f:
                    posts = [p for p in posts
                             if (p[4] or "").startswith(data_f)]
                if modo == "unica":
                    fixada = obter_postagem_unica_id()
                    if fixada is not None:
                        fixadas = [p for p in posts
                                   if str(p[0]) == str(fixada)]
                        if fixadas:
                            posts = fixadas
                    posts = posts[:1]
                if modo == "carrossel":
                    from mod_blog.bd_manipulador import (
                        listar_postagens_por_ids, obter_carrossel_postagens_ids,
                    )
                    posts = listar_postagens_por_ids(
                        obter_carrossel_postagens_ids(), ativo=True)
                    _renderizar_carrossel(
                        posts_wrap, posts, obter_carrossel_tempo(),
                        usuario_logado, perfil, pode_publicar, ao_editar,
                        atualizar)
                    return
                with posts_wrap:
                    if not posts:
                        with ui.card().classes("w-full items-center p-8"):
                            ui.icon("article", size="48px").classes("text-grey-4")
                            if termo or data_f:
                                msg = "Nenhuma publicação encontrada."
                            else:
                                msg = "Nenhuma publicação ainda." + (
                                    " Crie a primeira!" if pode_publicar else "")
                            ui.label(msg).classes("text-grey-6")
                    for post in posts:
                        _card_postagem(
                            post, usuario_logado, perfil, atualizar,
                            pode_publicar=pode_publicar,
                            ao_editar=ao_editar if pode_publicar else None)

            atualizar()

        if pode_publicar:
            with ui.tab_panel("admin_blog"):
                _painel_despublicadas(usuario_logado)
