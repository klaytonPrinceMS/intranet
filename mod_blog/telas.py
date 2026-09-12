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
from mod_intranet.decoradores import tela_modulo

# Registro dos timers do carrossel por wrap: cada re-render (atualizar/página)
# cancela o timer anterior do MESMO wrap antes de criar outro — evita acúmulo
# de timers e a corrida que gerava "The parent slot of Timer has been deleted".
_carrossel_timers = {}


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
                   ao_editar=None, selecionados=None, ao_toggle_selecao=None):
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
        # checkbox de seleção em lote (só quando admin habilitou modo seleção)
        if selecionados is not None and ao_toggle_selecao is not None:
            with ui.row().classes("w-full items-center").style("gap: 0.5rem; margin-bottom: 0.25rem"):
                ui.checkbox(value=(pid in selecionados),
                            on_change=lambda e, _pid=pid: ao_toggle_selecao(_pid, e.value)) \
                    .props(f'data-testid=blog-selecionar-{pid}') \
                    .tooltip("Selecionar para exclusão em lote")
                ui.label("Selecionar").classes("text-caption text-grey-6")
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
                          pode_publicar, ao_editar, ao_atualizar,
                          selecionados=None, ao_toggle_selecao=None):
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
                               ao_editar=ao_editar if pode_publicar else None,
                               selecionados=selecionados, ao_toggle_selecao=ao_toggle_selecao)
            else:
                if selecionados is not None and ao_toggle_selecao is not None:
                    with ui.row().classes("w-full items-center").style("gap: 0.5rem; margin-top: 0.25rem"):
                        ui.checkbox(value=(post[0] in selecionados),
                                    on_change=lambda e, _pid=post[0]: ao_toggle_selecao(_pid, e.value)) \
                            .props(f'data-testid=blog-selecionar-{post[0]}')
                        ui.label("Selecionar").classes("text-caption text-grey-6")
                card_resumo()
            barra_acoes()

    def avancar():
        try:
            if not expandido["v"] and n:
                idx["v"] = (idx["v"] + 1) % n
                montar()
        except RuntimeError:
            pass  # página navegada/fechada — timer já será encerrado

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
    # destruído/recriado a cada `montar()` (evita aceleração). Antes de criar,
    # cancela o timer anterior do MESMO wrap (evita acúmulo em re-renders).
    antigo = _carrossel_timers.pop(id(wrap), None)
    if antigo is not None:
        try:
            antigo.cancel(with_current_invocation=True)
            antigo.delete()
        except Exception:
            pass
    novo_timer = ui.timer(tempo_seg, avancar)
    _carrossel_timers[id(wrap)] = novo_timer


def renderizar_postagens(wrap, usuario_logado, perfil, pode_publicar,
                         ao_atualizar, ao_editar=None, termo="", data_f="",
                         selecionados=None, ao_toggle_selecao=None):
    """Renders the post feed honoring the configured display mode.

    Monta o feed conforme `blog_modo_exibicao` — 'historico' (lista completa),
    'unica' (postagem fixada ou a mais recente) ou 'carrossel' (rotação
    automática das selecionadas). É a FONTE ÚNICA do padrão de exibição:
    usada pela tela do Blog E pela Home, para que a página inicial mostre o
    MESMO padrão configurado no módulo. `termo` filtra título/conteúdo/autor;
    `data_f` filtra pela data (AAAA-MM-DD)."""
    from mod_blog.bd_manipulador import (
        listar_postagens, obter_modo_exibicao, obter_postagem_unica_id,
        obter_carrossel_postagens_ids, obter_carrossel_tempo,
        listar_postagens_por_ids,
    )
    wrap.clear()
    modo = obter_modo_exibicao()
    posts = listar_postagens(ativo=True, ordem="DESC")
    termo = (termo or "").strip().lower()
    data_f = (data_f or "").strip()
    if termo:
        posts = [p for p in posts if
                 termo in ((p[1] or "").lower())
                 or termo in ((p[2] or "").lower())
                 or termo in ((p[3] or "").lower())]
    if data_f:
        posts = [p for p in posts if (p[4] or "").startswith(data_f)]
    if modo == "carrossel":
        posts = listar_postagens_por_ids(
            obter_carrossel_postagens_ids(), ativo=True)
        _renderizar_carrossel(wrap, posts, obter_carrossel_tempo(),
                              usuario_logado, perfil, pode_publicar,
                              ao_editar, ao_atualizar,
                              selecionados=selecionados, ao_toggle_selecao=ao_toggle_selecao)
        return
    if modo == "unica":
        fixada = obter_postagem_unica_id()
        if fixada is not None:
            fixadas = [p for p in posts if str(p[0]) == str(fixada)]
            if fixadas:
                posts = fixadas
        posts = posts[:1]
    with wrap:
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
            _card_postagem(post, usuario_logado, perfil, ao_atualizar,
                           pode_publicar=pode_publicar, ao_editar=ao_editar,
                           selecionados=selecionados, ao_toggle_selecao=ao_toggle_selecao)


@tela_modulo(chave="blog", titulo="Blog")
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
            container = ui.column().classes("w-full gap-4").style("min-width: 0")

            if pode_publicar:
                _edit_id = {"id": None}
                with ui.card().classes("w-full shadow-lg").style("min-width: 0"):
                    with ui.card_section().classes("gap-3 w-full").style("min-width: 0"):
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
                                "w-full justify-center items-center flex-wrap") \
                                .style("gap: 0.75rem"):
                            botao("Pré-visualizar", icone="preview",
                                  on_click=mostrar_preview, variante="contorno",
                                  chave_modulo="blog")
                            botao("Publicar", icone="send",
                                  on_click=publicar, variante="solido",
                                  chave_modulo="blog") \
                                .props('data-testid=blog-publicar')
                            botao("Cancelar edição", icone="cancel",
                                  on_click=cancelar_edicao, variante="contorno",
                                  chave_modulo="blog")

            # --- estado compartilhado da seleção em lote (usado por Exibição e Seleção) ---
            selecionados = set()
            _tempo_exib = {"valor": 1}
            try:
                from mod_blog.bd_manipulador import obter_carrossel_tempo as _get_t
                _tempo_exib["valor"] = _get_t()
            except Exception:
                pass

            def _restaurar_padrao():
                try:
                    from mod_blog.bd_manipulador import set_config_local as _sc, definir_postagem_unica_id as _su, definir_carrossel_postagens_ids as _sc2, definir_carrossel_tempo as _st
                    _sc("blog_modo_exibicao", "historico")
                    _su(None)
                    _sc2([])
                    _st(10)
                    try:
                        from mod_intranet.crud_base import audit_reg as _audit
                        _audit(usuario_logado, "blog", "configuracao", "exibição: padrões restaurados")
                    except Exception:
                        pass
                    ui.notify("Configurações de exibição restauradas ao padrão", type="positive")
                    ui.timer(0.1, lambda: ui.navigate.reload(), once=True)
                except Exception:
                    observabilidade.get_logger("blog").exception("falha ao restaurar exibição")
                    ui.notify("Erro ao restaurar", type="negative")

            def _aplicar_carrossel_exib():
                if selecionados is None or len(selecionados) < 2:
                    ui.notify("Selecione ao menos 2 postagens para o carrossel", type="warning")
                    return
                from mod_blog.bd_manipulador import definir_carrossel_postagens_ids as _sc2, definir_carrossel_tempo as _st, set_config_local as _sc
                from mod_intranet.crud_base import audit_reg as _audit2
                try:
                    _sc2(sorted(selecionados))
                    _st(int(_tempo_exib.get("valor") or 10))
                    _sc("blog_modo_exibicao", "carrossel")
                    try:
                        _audit2(usuario_logado, "blog", "configuracao", f"carrossel via seleção: {sorted(selecionados)}")
                    except Exception:
                        pass
                    ui.notify(f"Carrossel definido com {len(selecionados)} postagem(ns)", type="positive")
                    ui.timer(0.1, lambda: ui.navigate.reload(), once=True)
                except Exception:
                    observabilidade.get_logger("blog").exception("Erro ao aplicar carrossel")
                    ui.notify("Erro ao aplicar ao carrossel", type="negative")

            def _aplicar_unica_exib():
                if selecionados is None or len(selecionados) != 1:
                    ui.notify("Selecione exatamente 1 postagem para 'Publicação única'", type="warning")
                    return
                from mod_blog.bd_manipulador import definir_postagem_unica_id as _su, set_config_local as _sc
                from mod_intranet.crud_base import audit_reg as _audit3
                try:
                    pid = next(iter(selecionados))
                    _su(pid)
                    _sc("blog_modo_exibicao", "unica")
                    try:
                        _audit3(usuario_logado, "blog", "configuracao", f"única via seleção: {pid}")
                    except Exception:
                        pass
                    ui.notify(f"Modo 'Publicação única' definido com #{pid}", type="positive")
                    ui.timer(0.1, lambda: ui.navigate.reload(), once=True)
                except Exception:
                    observabilidade.get_logger("blog").exception("Erro ao aplicar única")
                    ui.notify("Erro ao aplicar à única", type="negative")

            def _aplicar_historico_exib():
                from mod_blog.bd_manipulador import set_config_local as _sc
                from mod_intranet.crud_base import audit_reg as _audit4
                try:
                    _sc("blog_modo_exibicao", "historico")
                    try:
                        _audit4(usuario_logado, "blog", "configuracao", "histórico via seleção (todas)")
                    except Exception:
                        pass
                    ui.notify("Modo 'Histórico' definido — todas as postagens serão exibidas", type="positive")
                    ui.timer(0.1, lambda: ui.navigate.reload(), once=True)
                except Exception:
                    observabilidade.get_logger("blog").exception("Erro ao aplicar histórico")
                    ui.notify("Erro ao aplicar histórico", type="negative")

            # ---- Card 1 — FILTROS (busca + data, justificado, ocupa extensão) ----
            with ui.card().classes("w-full bg-white border rounded-lg shadow-sm p-4").style("min-width: 0"):
                ui.label("Filtros").classes("text-subtitle2 font-bold text-grey-8")
                ui.separator().classes("mb-2")
                with ui.row().classes("w-full items-end justify-between flex-wrap").style("gap: 1rem"):
                    with ui.row().classes("flex-1 flex-wrap items-end").style("gap: 1rem; min-width: 0"):
                        busca_termo = campo_busca(
                            "Buscar por título, conteúdo ou autor...",
                            on_change=lambda e: atualizar(),
                            tooltip="Filtra as publicações pelo termo digitado (título, conteúdo ou autor).",
                        ).classes("flex-1 min-w-[240px]").style("min-width: 0").props('data-testid=blog-busca')
                        busca_data = campo_texto(
                            "Data (AAAA-MM-DD)",
                            placeholder="ex.: 2026-09-06",
                            ao_mudar=lambda e: atualizar(),
                            largura="w-full sm:w-64",
                            tooltip="Filtra pela data de publicação (formato AAAA-MM-DD).",
                        ).style("min-width: 0")

            # ---- Card 2 — EXIBIÇÃO (centralizado, ocupa extensão, sem redundância) ----
            with ui.card().classes("w-full bg-white border rounded-lg shadow-sm p-4").style("min-width: 0"):
                ui.label("Exibição").classes("text-subtitle2 font-bold text-grey-8")
                ui.label("Defina o modo a partir da seleção em lote — ou exiba todas.").classes("text-caption text-grey-6 -mt-1")
                ui.separator().classes("mb-2")
                with ui.row().classes("w-full justify-center items-center flex-wrap").style("gap: 0.75rem"):
                    botao("Aplicar ao carrossel", icone="view_carousel", variante="solido", chave_modulo="blog",
                          on_click=_aplicar_carrossel_exib, tooltip="Define as selecionadas como carrossel (mín. 2)").props('data-testid=blog-aplicar-carrossel')
                    botao("Aplicar à única", icone="push_pin", variante="solido", chave_modulo="blog",
                          on_click=_aplicar_unica_exib, tooltip="Define a única selecionada como fixa (1)").props('data-testid=blog-aplicar-unica')
                    botao("Exibir todas", icone="view_day", variante="solido", chave_modulo="blog",
                          on_click=_aplicar_historico_exib, tooltip="Modo Histórico — lista completa").props('data-testid=blog-aplicar-historico')
                    botao("Restaurar padrão", icone="restore", on_click=_restaurar_padrao, variante="restaurar", chave_modulo="blog")
                with ui.row().classes("w-full justify-center items-center flex-wrap").style("gap: 0.75rem; margin-top: 0.5rem"):
                    ui.number("Tempo (s)", value=_tempo_exib["valor"], min=1, max=60, step=1).classes("w-36").props("outlined dense").tooltip("Intervalo do carrossel").on_value_change(lambda e: _tempo_exib.update(valor=int(e.value or 10)))
                    ui.label("segundos por slide").classes("text-caption text-grey-6")

            # ---- Card 3 — SELEÇÃO EM LOTE (box bem delimitado, agrupado por uso) ----
            # helpers da seleção — definidos ANTES da UI para evitar UnboundLocalError
            _contador_holder = {}

            def _atualizar_contador():
                lbl = _contador_holder.get("label")
                if lbl is None:
                    return
                try:
                    lbl.set_text(f"{len(selecionados)} selecionado(s)")
                except Exception:
                    pass

            def _visiveis_ids():
                from mod_blog.bd_manipulador import (
                    listar_postagens as _lst, obter_modo_exibicao as _modo,
                    obter_postagem_unica_id as _fix, obter_carrossel_postagens_ids as _car_ids,
                    listar_postagens_por_ids as _por_ids)
                modo = _modo()
                if modo == "carrossel":
                    por = _por_ids(_car_ids(), ativo=True)
                else:
                    por = _lst(ativo=True, ordem="DESC")
                    termo = (busca_termo.value or "").strip().lower()
                    dataf = (busca_data.value or "").strip()
                    if termo:
                        por = [p for p in por if termo in ((p[1] or "").lower()) or termo in ((p[2] or "").lower()) or termo in ((p[3] or "").lower())]
                    if dataf:
                        por = [p for p in por if (p[4] or "").startswith(dataf)]
                    if modo == "unica":
                        fix = _fix()
                        if fix is not None:
                            fixadas = [p for p in por if str(p[0]) == str(fix)]
                            if fixadas:
                                por = fixadas
                        por = por[:1]
                return [p[0] for p in por]

            def ao_toggle_selecao(pid, valor):
                if valor:
                    selecionados.add(pid)
                else:
                    selecionados.discard(pid)
                _atualizar_contador()

            def selecionar_todos():
                for pid in _visiveis_ids():
                    selecionados.add(pid)
                _atualizar_contador()
                atualizar()

            def selecionar_n(n):
                vis = _visiveis_ids()
                nao_sel = [pid for pid in vis if pid not in selecionados]
                for pid in nao_sel[:n]:
                    selecionados.add(pid)
                if not nao_sel:
                    for pid in vis[:n]:
                        selecionados.add(pid)
                _atualizar_contador()
                atualizar()

            def limpar_selecao():
                selecionados.clear()
                _atualizar_contador()
                atualizar()

            def excluir_selecionados():
                if not selecionados:
                    ui.notify("Nenhuma postagem selecionada", type="warning")
                    return
                ids = sorted(selecionados)
                def confirmar():
                    from mod_blog.bd_manipulador import excluir_postagens_em_lote
                    try:
                        ok, falha = excluir_postagens_em_lote(ids, usuario_logado)
                    except Exception:
                        observabilidade.get_logger("blog").exception("Erro ao excluir em lote")
                        ui.notify("Erro ao excluir selecionados", type="negative")
                        return
                    if ok:
                        ui.notify(f"{ok} postagem(ns) excluída(s)" + (f" ({falha} falha(s))" if falha else ""), type="positive" if not falha else "warning")
                        selecionados.clear()
                        _atualizar_contador()
                        atualizar()
                    else:
                        ui.notify("Nenhuma postagem excluída (permissão?)", type="negative")
                    dlg.close()
                with ui.dialog() as dlg, ui.card().classes("w-[420px]"):
                    ui.label(f"Excluir {len(ids)} postagem(ns)?").classes("text-h6")
                    ui.label("As postagens serão ocultadas (soft delete) e poderão ser restabelecidas em Despublicadas.").classes("text-caption text-grey-6")
                    with ui.row().classes("w-full justify-end").style("gap: 0.5rem"):
                        botao("Cancelar", on_click=dlg.close, variante="texto", chave_modulo="blog")
                        botao("Excluir", icone="delete", on_click=confirmar, variante="perigo", chave_modulo="blog").props('data-testid=blog-confirmar-excluir-lote')
                dlg.open()

            bulk_wrap = ui.column().classes("w-full") if pode_publicar else None
            if pode_publicar:
                with ui.card().classes("w-full bg-white border rounded-lg shadow-sm p-4").style("min-width: 0"):
                    with ui.row().classes("w-full items-center justify-between flex-wrap").style("gap: 0.75rem"):
                        ui.label("Seleção em lote").classes("text-subtitle2 font-bold text-grey-8")
                        with ui.row().classes("items-center flex-wrap").style("gap: 0.5rem"):
                            ui.checkbox("Selecionar todos", on_change=lambda e: (selecionar_todos() if e.value else limpar_selecao())).props('data-testid=blog-selecionar-todos')
                            lbl = ui.label("0 selecionado(s)").classes("text-caption text-grey-6").props('data-testid=blog-selecionados-contador')
                            _contador_holder["label"] = lbl
                    ui.separator().classes("my-2")
                    with ui.row().classes("w-full justify-center items-center flex-wrap").style("gap: 0.75rem"):
                        botao("Selecionar 10", variante="solido", chave_modulo="blog", on_click=lambda: selecionar_n(10)).props('data-testid=blog-selecionar-10')
                        botao("5 próximas", variante="solido", chave_modulo="blog", on_click=lambda: selecionar_n(5)).props('data-testid=blog-selecionar-5')
                        botao("Limpar", variante="solido", chave_modulo="blog", on_click=limpar_selecao).props('data-testid=blog-limpar-selecao')
                    with ui.row().classes("w-full justify-center items-center flex-wrap").style("gap: 0.75rem; margin-top: 0.5rem"):
                        botao("Excluir selecionados", icone="delete", variante="perigo", chave_modulo="blog", on_click=excluir_selecionados).props('data-testid=blog-excluir-selecionados')
            else:
                def ao_toggle_selecao(pid, valor):
                    pass
                selecionados = None
                def _atualizar_contador():
                    pass
                def _visiveis_ids():
                    return []

            posts_wrap = ui.column().classes("w-full gap-4")

            def atualizar():
                renderizar_postagens(
                    posts_wrap, usuario_logado, perfil, pode_publicar,
                    atualizar, ao_editar if pode_publicar else None,
                    termo=(busca_termo.value or ""),
                    data_f=(busca_data.value or ""),
                    selecionados=selecionados, ao_toggle_selecao=ao_toggle_selecao if pode_publicar else None)
                if pode_publicar:
                    try:
                        _atualizar_contador()
                    except Exception:
                        pass

            atualizar()

        if pode_publicar:
            with ui.tab_panel("admin_blog"):
                _painel_despublicadas(usuario_logado)
