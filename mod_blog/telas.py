"""Tela do módulo Blog — postagens e comentários com sanitização NH3.

Inclui: criação/edição com pré-visualização, modo de exibição única/histórico,
publicar/despublicar e restauração de postagens inativas (aba Administração).
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from nicegui import ui
from mod_intranet import observabilidade
from mod_intranet.aba_modulo import cabecalho, abas


def _card_postagem(post, usuario_logado, perfil, ao_atualizar, pode_publicar=False,
                   ao_editar=None):
    from mod_blog.manipulador_bd import listar_comentarios, excluir_postagem, \
        despublicar_postagem, formatar_conteudo_para_exibicao

    pid, titulo, conteudo, autor, data = post[0], post[1], post[2], post[3], (post[4] or "")[:16]

    with ui.card().classes("w-full shadow-md border-l-8").style("border-left-color:#7B1FA2"):
        with ui.row().classes("w-full items-start justify-between flex-wrap"):
            with ui.column().classes("gap-0 grow"):
                ui.label(titulo or "(sem título)").classes("text-h6 font-bold text-grey-9")
                ui.label(f"por {autor} • {data}").classes("text-caption text-grey-6")
            if pode_publicar:
                with ui.row().classes("items-center gap-1"):
                    if ao_editar is not None:
                        def editar():
                            ao_editar(pid, titulo, conteudo)
                        ui.button(icon="edit", on_click=editar).props(
                            "flat round color=grey-7").tooltip("Editar")
                    def despublicar():
                        try:
                            despublicar_postagem(pid, usuario_logado)
                            ui.notify("Postagem despublicada", type="info")
                            ao_atualizar()
                        except Exception:
                            observabilidade.get_logger("blog").exception(
                                f"Erro ao despublicar postagem #{pid}")
                            ui.notify("Erro ao despublicar postagem", type="negative")
                    ui.button(icon="visibility_off", on_click=despublicar).props(
                        "flat round color=grey-7").tooltip("Despublicar")
                    def excluir():
                        try:
                            excluir_postagem(pid, usuario_logado)
                            ui.notify("Postagem removida", type="info")
                            ao_atualizar()
                        except Exception:
                            observabilidade.get_logger("blog").exception(
                                f"Erro ao excluir postagem #{pid}")
                            ui.notify("Erro ao excluir postagem", type="negative")
                    ui.button(icon="delete", on_click=excluir).props(
                        "flat round color=grey-7").tooltip("Excluir")
        with ui.column().classes("w-full mt-1"):
            # conteúdo já vem sanitizado do BD; aplica formatação padrão (títulos
            # centralizados, imagens à esquerda configuráveis, texto justificado)
            html_seguro = formatar_conteudo_para_exibicao(conteudo or "")
            if html_seguro:
                ui.html(html_seguro).classes("text-body2 text-grey-8")
            else:
                ui.label("(sem conteúdo)").classes("text-body2 italic text-grey-5")
        # comentários
        comentarios = listar_comentarios(pid)
        with ui.expansion(f"Comentários ({len(comentarios)})").classes("w-full"):
            for cid, cautor, ctexto, cdata in comentarios:
                with ui.row().classes("w-full items-start gap-2 py-1 border-b"):
                    ui.icon("chat_bubble_outline").classes("text-grey-5")
                    ui.html(f"<b>{_esc(cautor)}</b> "
                            f"<span class='text-grey-6 text-xs'>{(cdata or '')[:16]}</span>"
                            f"<br>{_sanitizar(ctexto or '')}")
            if pode_publicar:  # comum apenas lê — sem campo de comentário
                novo = ui.input(placeholder="Escreva um comentário...").props(
                    "outlined dense").classes("w-full")

                def enviar(pid=pid, novo=novo):
                    from mod_blog.manipulador_bd import criar_comentario
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


def _esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _sanitizar(texto):
    """Sanitiza mantendo apenas as tags permitidas (configuráveis em Adm),
    aceitando http/https, URLs relativas e data: para imagens."""
    from mod_blog.manipulador_bd import tags_permitidas, _URL_SCHEMES, _ATTRS
    from nh3 import clean
    try:
        return clean(texto, tags=tags_permitidas(), attributes=_ATTRS,
                     url_schemes=_URL_SCHEMES, url_relative="pass_through")
    except Exception:
        return _esc(texto)


def mostrar_tela(usuario_logado: str, perfil: str):
    from mod_intranet import autenticacao
    from mod_intranet.conexao_bd import get_config, set_config
    from mod_intranet.manipulador_bd import audit_log
    from mod_blog.manipulador_bd import (get_config_local, set_config_local,
                                         tags_permitidas, obter_modo_exibicao,
                                         criar_postagem, atualizar_postagem,
                                         _TAGS_PADRAO)
    # Regra do módulo: comum só LÊ; publicar/comentar/excluir é de administradores
    pode_publicar = (perfil == "administrador_geral"
                     or autenticacao.eh_admin_do_modulo(usuario_logado, "blog"))

    # ================= TEMA (Aparência, prefixo blog_ na config central) =================
    def _tema(chave, default):
        try:
            return (get_config(f"blog_{chave}", default) or "").strip() or default
        except Exception:
            return default

    t_cor_botao = _tema("cor_botao", "#7B1FA2")
    t_cor_txt_botao = _tema("cor_texto_botao", "#FFFFFF")
    t_tamanho = _tema("btn_tamanho", "medium")

    def _btn_cls():
        if t_tamanho == "small":
            return "min-w-[140px] text-sm"
        if t_tamanho == "large":
            return "min-w-[220px] text-lg"
        return "min-w-[180px]"

    def _btn_style():
        st = ""
        if t_cor_botao:
            st += f"background-color:{t_cor_botao};"
        if t_cor_txt_botao:
            st += f"color:{t_cor_txt_botao};"
        return st

    texto_header = _tema_s(get_config, "blog_texto_header",
                           "Comunique novidades para toda a equipe.")
    modo_atual = obter_modo_exibicao()

    cabecalho("Blog", texto_header, cor_borda="#7B1FA2")
    tabs_el = abas("Publicações", "article", admin=pode_publicar)
    with ui.tab_panels(tabs_el, value="principal").classes("w-full"):
        with ui.tab_panel("principal"):
            container = ui.column().classes("w-full max-w-4xl mx-auto gap-4")

            if pode_publicar:
                # ---- Editor (criar/editar) com pré-visualização ----
                _edit_id = {"id": None}
                with ui.card().classes("w-full shadow-lg"):
                    with ui.card_section().classes("gap-2 w-full"):
                        titulo_edit = ui.label("Nova publicação").classes(
                            "text-h6 font-bold text-grey-9")
                        inp_titulo = ui.input("Título*").props(
                            "outlined dense").classes("w-full")
                        inp_conteudo = ui.textarea(
                            "Conteúdo*", placeholder="Use <b>, <i>, <p>, HTML simples, "
                            "Markdown (#, **negrito**, - item) ou URLs de imagem "
                            "(data:/relativas aceitas)"
                        ).props("outlined dense").classes("w-full")
                        preview_wrap = ui.column().classes("w-full hidden")

                        def atualizar_preview():
                            preview_wrap.clear()
                            if not (inp_conteudo.value or "").strip():
                                preview_wrap.add_slot('default', '')
                                preview_wrap.classes(replace="w-full hidden")
                                return
                            from mod_blog.manipulador_bd import formatar_conteudo_para_exibicao
                            html_seguro = formatar_conteudo_para_exibicao(inp_conteudo.value)
                            preview_wrap.classes(replace="w-full")
                            preview_wrap.clear()
                            with preview_wrap:
                                ui.label("Pré-visualização").classes(
                                    "text-subtitle2 text-grey-7")
                                with ui.card().classes("w-full bg-grey-2"):
                                    ui.html(html_seguro or "<i>(vazio)</i>").classes(
                                        "text-body2 text-grey-8 p-3")

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
                                        ui.notify(f"Publicação #{pid} criada!", type="positive")
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
                            ui.scroll_to(selector=None)
                            atualizar_preview()

                        with ui.row().classes("w-full items-center gap-2"):
                            ui.button("Pré-visualizar", icon="preview",
                                      on_click=mostrar_preview).props("outline").classes(
                                _btn_cls()).style(_btn_style())
                            ui.button("Publicar", icon="send", on_click=publicar).props(
                                "unelevated").classes(_btn_cls()).style(_btn_style())
                            ui.button("Cancelar edição", icon="cancel",
                                      on_click=cancelar_edicao).props("flat").classes(
                                _btn_cls()).style(_btn_style())

                # ---- Alternância modo única/histórico (persistida em config local) ----
                if pode_publicar or True:
                    modo_sel = ui.select(
                        {"historico": "Histórico (lista completa)",
                         "unica": "Publicação única (mais recente)"},
                        label="Modo de exibição",
                        value=modo_atual,
                        on_change=lambda e: _mudar_modo(e.value),
                    ).props("outlined dense").classes("w-full max-w-sm mt-2")

                    def _mudar_modo(modo):
                        set_config_local("blog_modo_exibicao", modo)
                        try:
                            audit_log(usuario_logado, "blog", "configuracao",
                                      f"modo de exibição definido como '{modo}'")
                        except Exception:
                            pass
                        ui.timer(0.1, lambda: ui.navigate.reload(), once=True)

            posts_wrap = ui.column().classes("w-full gap-4")

            def atualizar():
                from mod_blog.manipulador_bd import listar_postagens
                posts_wrap.clear()
                modo = obter_modo_exibicao()
                posts = listar_postagens(ativo=True, ordem="DESC")
                if modo == "unica":
                    posts = posts[:1]
                with posts_wrap:
                    if not posts:
                        with ui.card().classes("w-full items-center p-8"):
                            ui.icon("article", size="48px").classes("text-grey-4")
                            msg = "Nenhuma publicação ainda." + (
                                " Crie a primeira!" if pode_publicar else "")
                            ui.label(msg).classes("text-grey-6")
                    for post in posts:
                        _card_postagem(
                            post, usuario_logado, perfil, atualizar,
                            pode_publicar=pode_publicar,
                            ao_editar=ao_editar if pode_publicar else None)

            atualizar()
        with ui.tab_panel("adm"):
            if pode_publicar:
                with ui.expansion("Administração — configurações do Blog",
                                  icon="settings").classes("w-full mt-4"):
                    ui.label("Aparência — temas dos botões desta tela").classes(
                        "text-subtitle2 text-grey-7")
                    inp_cor_botao = ui.color_input(label="Cor dos botões", value=t_cor_botao)
                    inp_cor_txt = ui.color_input(label="Cor do texto dos botões",
                                                 value=t_cor_txt_botao)
                    sel_tamanho = ui.select(
                        {0: "Pequeno", 1: "Médio", 2: "Grande"},
                        label="Tamanho dos botões",
                        value={"small": 0, "medium": 1, "large": 2}.get(t_tamanho, 1),
                    ).props("outlined dense")

                    with ui.separator().classes("my-3"):
                        pass
                    ui.label("Configurações específicas").classes(
                        "text-subtitle2 text-grey-7")
                    inp_tags = ui.input(
                        "Tags HTML permitidas (separadas por vírgula)",
                        value=",".join(sorted(tags_permitidas())) or _TAGS_PADRAO,
                    ).props("outlined dense").classes("w-full") \
                        .tooltip("Lista das tags aceitas na sanitização NH3. "
                                 "Remover tags reduz riscos de XSS.")
                    _img_min, _img_max = _largura_atual()
                    inp_largura = ui.input(
                        "Largura de imagem (min-max, ex. 200-400)",
                        value=f"{_img_min}-{_img_max}",
                    ).props("outlined dense").classes("w-full") \
                        .tooltip("Limites mínimo/máximo de largura, em px, "
                                 "para imagens nas postagens.")
                    inp_texto = ui.input("Texto do cabeçalho",
                                         value=texto_header).props(
                        "outlined dense").classes("w-full")

                    _tamanhos = {0: "small", 1: "medium", 2: "large"}

                    def salvar():
                        try:
                            set_config("blog_cor_botao", inp_cor_botao.value or "")
                            set_config("blog_cor_texto_botao", inp_cor_txt.value or "")
                            set_config("blog_btn_tamanho", _tamanhos[sel_tamanho.value])
                            set_config_local("blog_tags_permitidas",
                                             (inp_tags.value or "").strip())
                            set_config_local("blog_largura_imagem",
                                             (inp_largura.value or "200-400").strip())
                            set_config("blog_texto_header", (inp_texto.value or "").strip())
                            try:
                                audit_log(usuario_logado, "blog", "configuracao",
                                          "aparência e configurações do blog salvas")
                            except Exception:
                                pass
                            ui.notify("Configurações salvas (valem sem reiniciar)",
                                      type="positive")
                            ui.timer(0.1, lambda: ui.navigate.reload(), once=True)
                        except Exception:
                            observabilidade.get_logger("blog").exception(
                                "Erro ao salvar configurações do blog")
                            ui.notify("Erro ao salvar configurações", type="negative")

                    def resetar():
                        try:
                            for chave, valor in (
                                ("cor_botao", "#7B1FA2"),
                                ("cor_texto_botao", "#FFFFFF"),
                                ("btn_tamanho", "medium"),
                                ("tags_permitidas", _TAGS_PADRAO),
                                ("texto_header", "Comunique novidades para toda a equipe."),
                            ):
                                set_config(f"blog_{chave}", valor)
                            set_config_local("blog_tags_permitidas", _TAGS_PADRAO)
                            set_config_local("blog_largura_imagem", "200-400")
                            set_config_local("blog_modo_exibicao", "historico")
                            try:
                                audit_log(usuario_logado, "blog", "configuracao",
                                          "configurações do blog restauradas ao padrão")
                            except Exception:
                                pass
                            ui.notify("Padrões restaurados", type="positive")
                            ui.timer(0.1, lambda: ui.navigate.reload(), once=True)
                        except Exception:
                            observabilidade.get_logger("blog").exception(
                                "Erro ao restaurar padrões do blog")
                            ui.notify("Erro ao restaurar padrões", type="negative")

                    with ui.row().classes("w-full justify-end gap-2 mt-2"):
                        ui.button("Restaurar padrão", on_click=resetar).props("flat") \
                            .classes(_btn_cls()).style(_btn_style())
                        ui.button("Salvar", icon="save", on_click=salvar).props(
                            "unelevated").classes(_btn_cls()).style(_btn_style())

                # ---- Gestão das postagens inativas (restauração/republicar) ----
                with ui.expansion("Postagens despublicadas (gestão)",
                                  icon="inventory_2").classes("w-full mt-4"):
                    from mod_blog.manipulador_bd import listar_postagens, publicar_postagem
                    inativos_wrap = ui.column().classes("w-full gap-2")

                    def carregar_inativos():
                        inativos_wrap.clear()
                        inativos = listar_postagens(ativo=False, ordem="DESC")
                        with inativos_wrap:
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
                                        ok = publicar_postagem(iid, usuario_logado)
                                        if ok:
                                            ui.notify(f"Postagem #{iid} republicada",
                                                      type="positive")
                                        else:
                                            ui.notify("Erro ao republicar", type="negative")
                                        carregar_inativos()
                                    ui.button("Republicar", icon="visibility",
                                              on_click=republicar).props(
                                        "flat dense color=primary")

                    carregar_inativos()


def _tema_s(get_config, chave, default):
    try:
        return (get_config(chave, default) or "").strip() or default
    except Exception:
        return default


def _largura_atual():
    from mod_blog.manipulador_bd import _largura_imagem
    return _largura_imagem()
