"""EN: Phone Directory administration panel (route /admin/lista_telefonica).
Manage units (create/move/elevate/reorder/delete branch) and contacts
(create/edit/transfer/delete) plus appearance and backup.

PT-BR: Painel de administração da Lista Telefônica (rota /admin/lista_telefonica).
Gerencia unidades (criar/mover/elevar/reordenar/excluir ramo) e contatos
(criar/editar/transferir/excluir), além de aparência e backup.
"""

import sys, os, re
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from nicegui import ui
from mod_intranet.ui_comum import card_admin, rodape_salvar_restaurar, botao, botao_icone, dialogo_card
from mod_intranet.tema_modulo import ler_tema, notificar, bloco_aparencia
from mod_intranet import observabilidade
from mod_lista_telefonica import bd_manipulador as lista

log = observabilidade.get_logger("lista_telefonica")


def mostrar_administracao(usuario_logado: str = ""):
    try:
        tema = ler_tema("lista_telefonica", cor_botao="#000000", cor_texto_botao="#FFFFFF",
                        texto_header="Organograma — administrar ramos, mover e ordenar.")
        tema["_defaults"] = {
            "cor_botao": "", "cor_texto_botao": "", "cor_fundo": "",
            "cor_titulo": "#212121", "btn_tamanho": "medium",
            "texto_header": "Organograma — administrar ramos, mover e ordenar.",
            "cor_fundo_card": "#FFFFFF", "cor_texto_card": "",
        }
        ui.colors(primary=tema["cor_botao"])
        bloco_aparencia(usuario_logado, "lista_telefonica", tema, prefixo_auditoria="lista_telefonica", com_texto_header=True)

        # === Card Unidades ===
        with card_admin("Unidades — criar, mover, elevar/rebaixar, excluir ramo", icone="account_tree", chave_modulo="lista_telefonica", grade=False):
            ui.label("Crie Secretaria (raiz), Setor (sob secretaria) ou Subsetor (sob setor). Use Mover para transferir e Elevar para promover setor→secretaria. Excluir ramo remove a unidade e todo o descendente (cascata).").classes("text-caption text-grey-6")

            # Criar
            with ui.row().classes("w-full gap-3 flex-wrap"):
                inp_nome = ui.input("Nome da unidade *").props("outlined dense").classes("flex-1 min-w-[220px]").props('data-testid=admin-unidade-nome')
                sel_tipo = ui.select({"secretaria": "Secretaria", "setor": "Setor", "subsetor": "Subsetor"}, value="secretaria", label="Tipo").props("outlined dense").classes("w-[180px]").props('data-testid=admin-unidade-tipo')
                sel_pai = ui.select({}, label="Unidade pai (quando setor/subsetor)").props("outlined dense clearable").classes("flex-1 min-w-[220px]").props('data-testid=admin-unidade-pai')
                try:
                    from mod_intranet import telefone as _tel_un
                    _campo_tel_un = _tel_un.criar_campo_telefone(
                        valor="", testid_ddi="admin-unidade-ddi",
                        testid_numero="admin-unidade-tel")
                except Exception:
                    _campo_tel_un = None
                    inp_tel = ui.input("Telefone").props("outlined dense").classes("flex-1 min-w-[180px]").props('data-testid=admin-unidade-tel')

            # Popular pai conforme tipo
            def refresh_pai():
                try:
                    t = sel_tipo.value
                    if t == "secretaria":
                        sel_pai.set_options({})
                        sel_pai.disable()
                    elif t == "setor":
                        secs = lista.listar_unidades(parent_id=None, tipo="secretaria")
                        sel_pai.set_options({r[0]: r[1] for r in secs})
                        sel_pai.enable()
                    else:  # subsetor
                        # todos setores
                        opts = {}
                        for sec in lista.listar_unidades(parent_id=None, tipo="secretaria"):
                            for setor in lista.listar_unidades(parent_id=sec[0], tipo="setor"):
                                opts[setor[0]] = f"{sec[1]} > {setor[1]}"
                        sel_pai.set_options(opts)
                        sel_pai.enable()
                    sel_pai.update()
                except Exception:
                    try:
                        try:
                            _log().exception("refresh_pai falhou")
                        except NameError:
                            try:
                                log.exception("refresh_pai falhou")
                            except NameError:
                                from mod_intranet import observabilidade as _obs_fail
                                _obs_fail.get_logger("lista_telefonica").exception("refresh_pai falhou")
                    except Exception:
                        pass
                    try:
                        from mod_intranet.tema_modulo import notificar as _notificar_fail
                        _notificar_fail("Erro interno. Tente novamente.", tipo="error")
                    except Exception:
                        pass
                    return None
            sel_tipo.on_value_change(lambda e: refresh_pai())
            refresh_pai()

            def _tel_un_valor():
                try:
                    if _campo_tel_un is not None:
                        return _campo_tel_un["obter"]() or ""
                    return inp_tel.value or ""
                except Exception:
                    return ""

            def criar():
                try:
                    ok, msg = lista.criar_unidade(inp_nome.value or "", sel_tipo.value, sel_pai.value, _tel_un_valor(), ator=usuario_logado)
                    notificar(msg, type="positive" if ok else "negative")
                    if ok:
                        refresh_pai()
                        render_unidades.refresh()
                except Exception:
                    try:
                        try:
                            _log().exception("criar falhou")
                        except NameError:
                            try:
                                log.exception("criar falhou")
                            except NameError:
                                from mod_intranet import observabilidade as _obs_fail
                                _obs_fail.get_logger("lista_telefonica").exception("criar falhou")
                    except Exception:
                        pass
                    try:
                        from mod_intranet.tema_modulo import notificar as _notificar_fail
                        _notificar_fail("Erro interno. Tente novamente.", tipo="error")
                    except Exception:
                        pass
                    return None
            botao("Criar unidade", icone="add", on_click=criar, variante="primario", chave_modulo="lista_telefonica").props('data-testid=admin-criar-unidade')

            # Listagem expansível para gerenciar
            @ui.refreshable
            def render_unidades():
                # mostra 3 níveis em expansão
                try:
                    secs = lista.listar_unidades(parent_id=None, tipo="secretaria")
                    if not secs:
                        ui.label("Nenhuma secretaria.").classes("text-grey-6 italic")
                        return
                    for sec in secs:
                        sec_id, sec_nome, sec_tipo, sec_pai, sec_ord, sec_tel, sec_ativo = sec
                        with ui.expansion(f"{sec_nome} ({sec_tel or 'sem tel'})", icon="apartment").classes("w-full border rounded"):
                            with ui.row().classes("w-full gap-2 flex-wrap p-2"):
                                botao_icone("edit", on_click=lambda _, sid=sec_id: _dlg_editar(sid), tooltip="Editar nome/telefone", chave_modulo="lista_telefonica")
                                botao_icone("delete_forever", on_click=lambda _, sid=sec_id: _dlg_excluir_ramo(sid), tooltip="Excluir ramo (cascata)", chave_modulo="lista_telefonica", extra_classes="text-red-8")
                                botao_icone("drive_file_move", on_click=lambda _, sid=sec_id: _dlg_mover(sid), tooltip="Mover para outro pai", chave_modulo="lista_telefonica")
                                botao_icone("vertical_align_top", on_click=lambda _, sid=sec_id: _dlg_elevar(sid), tooltip="Elevar/rebaixar tipo", chave_modulo="lista_telefonica")
                                botao_icone("swap_vert", on_click=lambda _, pid=None, sid=sec_id: _dlg_reordenar(pid, "secretaria"), tooltip="Reordenar secretarias", chave_modulo="lista_telefonica")
                            # setores
                            setores = lista.listar_unidades(parent_id=sec_id, tipo="setor")
                            for setor in setores:
                                set_id, set_nome, set_tipo, set_pai, set_ord, set_tel, set_ativo = setor
                                with ui.expansion(f"  {set_nome} ({set_tel or 'sem tel'})", icon="business").classes("w-full ml-4 border rounded"):
                                    with ui.row().classes("w-full gap-2 flex-wrap p-2"):
                                        botao_icone("edit", on_click=lambda _, sid=set_id: _dlg_editar(sid), tooltip="Editar", chave_modulo="lista_telefonica")
                                        botao_icone("delete", on_click=lambda _, sid=set_id: _dlg_excluir_ramo(sid), tooltip="Excluir ramo", chave_modulo="lista_telefonica")
                                        botao_icone("drive_file_move", on_click=lambda _, sid=set_id: _dlg_mover(sid), tooltip="Mover", chave_modulo="lista_telefonica")
                                        botao_icone("vertical_align_top", on_click=lambda _, sid=set_id: _dlg_elevar(sid), tooltip="Elevar", chave_modulo="lista_telefonica")
                                    # subsetores
                                    subs = lista.listar_unidades(parent_id=set_id, tipo="subsetor")
                                    for sub in subs:
                                        sub_id, sub_nome, sub_tipo, sub_pai, sub_ord, sub_tel, sub_ativo = sub
                                        with ui.row().classes("w-full items-center gap-2 ml-8 border-b py-1"):
                                            ui.icon("subdirectory_arrow_right").classes("text-grey-5")
                                            ui.label(f"{sub_nome} ({sub_tel or 'sem tel'})").classes("text-body2 flex-1")
                                            botao_icone("edit", on_click=lambda _, sid=sub_id: _dlg_editar(sid), tooltip="Editar", chave_modulo="lista_telefonica")
                                            botao_icone("delete", on_click=lambda _, sid=sub_id: _dlg_excluir_ramo(sid), tooltip="Excluir", chave_modulo="lista_telefonica")
                                            botao_icone("drive_file_move", on_click=lambda _, sid=sub_id: _dlg_mover(sid), tooltip="Mover", chave_modulo="lista_telefonica")
                except Exception:
                    try:
                        try:
                            _log().exception("render_unidades falhou")
                        except NameError:
                            try:
                                log.exception("render_unidades falhou")
                            except NameError:
                                from mod_intranet import observabilidade as _obs_fail
                                _obs_fail.get_logger("lista_telefonica").exception("render_unidades falhou")
                    except Exception:
                        pass
                    try:
                        from mod_intranet.tema_modulo import notificar as _notificar_fail
                        _notificar_fail("Erro interno. Tente novamente.", tipo="error")
                    except Exception:
                        pass
                    return None

            render_unidades()

            def _dlg_editar(uid):
                try:
                    uni = lista.obter_unidade(uid)
                    if not uni:
                        notificar("Unidade não encontrada", type="negative")
                        return
                    with dialogo_card(titulo=f"Editar — {uni[1]}", largura="w-[420px]", chave_modulo="lista_telefonica") as (dlg, card):
                        inp_n = ui.input("Nome", value=uni[1]).props("outlined dense").classes("w-full")
                        try:
                            from mod_intranet import telefone as _tel_une
                            _campo_t_une = _tel_une.criar_campo_telefone(valor=uni[5] or "")
                        except Exception:
                            _campo_t_une = None
                            inp_t = ui.input("Telefone", value=uni[5] or "").props("outlined dense").classes("w-full")
                        def _tel_une_valor():
                            try:
                                if _campo_t_une is not None:
                                    return _campo_t_une["obter"]() or ""
                                return inp_t.value
                            except Exception:
                                return ""
                        def salvar():
                            try:
                                ok, msg = lista.editar_unidade(uid, nome=inp_n.value, telefone=_tel_une_valor(), ator=usuario_logado)
                                notificar(msg, type="positive" if ok else "negative")
                                if ok:
                                    dlg.close()
                                    render_unidades.refresh()
                            except Exception:
                                try:
                                    try:
                                        _log().exception("salvar falhou")
                                    except NameError:
                                        try:
                                            log.exception("salvar falhou")
                                        except NameError:
                                            from mod_intranet import observabilidade as _obs_fail
                                            _obs_fail.get_logger("lista_telefonica").exception("salvar falhou")
                                except Exception:
                                    pass
                                try:
                                    from mod_intranet.tema_modulo import notificar as _notificar_fail
                                    _notificar_fail("Erro interno. Tente novamente.", tipo="error")
                                except Exception:
                                    pass
                                return None
                        with ui.row().classes("w-full justify-end gap-2 mt-3"):
                            ui.button("Cancelar", on_click=dlg.close).props("flat")
                            botao("Salvar", icone="save", on_click=salvar, variante="primario", chave_modulo="lista_telefonica")
                    dlg.open()
                except Exception:
                    try:
                        try:
                            _log().exception("_dlg_editar falhou")
                        except NameError:
                            try:
                                log.exception("_dlg_editar falhou")
                            except NameError:
                                from mod_intranet import observabilidade as _obs_fail
                                _obs_fail.get_logger("lista_telefonica").exception("_dlg_editar falhou")
                    except Exception:
                        pass
                    try:
                        from mod_intranet.tema_modulo import notificar as _notificar_fail
                        _notificar_fail("Erro interno. Tente novamente.", tipo="error")
                    except Exception:
                        pass
                    return None

            def _dlg_excluir_ramo(uid):
                try:
                    uni = lista.obter_unidade(uid)
                    if not uni:
                        return
                    with dialogo_card(titulo="Excluir ramo", largura="w-[420px]", chave_modulo="lista_telefonica", max_altura=False) as (dlg, card):
                        card.classes("border-2 border-red-6")
                        ui.label(f"Excluir '{uni[1]}' e TODOS os filhos/contatos? Esta ação não pode ser desfeita.").classes("text-body2")
                        def confirmar():
                            try:
                                ok, msg = lista.excluir_ramo(uid, ator=usuario_logado)
                                notificar(msg, type="positive" if ok else "negative")
                                if ok:
                                    dlg.close()
                                    render_unidades.refresh()
                            except Exception:
                                try:
                                    try:
                                        _log().exception("confirmar falhou")
                                    except NameError:
                                        try:
                                            log.exception("confirmar falhou")
                                        except NameError:
                                            from mod_intranet import observabilidade as _obs_fail
                                            _obs_fail.get_logger("lista_telefonica").exception("confirmar falhou")
                                except Exception:
                                    pass
                                try:
                                    from mod_intranet.tema_modulo import notificar as _notificar_fail
                                    _notificar_fail("Erro interno. Tente novamente.", tipo="error")
                                except Exception:
                                    pass
                                return None
                        with ui.row().classes("w-full justify-between mt-3"):
                            ui.button("Cancelar", on_click=dlg.close).props("flat")
                            botao("Excluir ramo", icone="warning", on_click=confirmar, variante="primario", cor="negative", chave_modulo="lista_telefonica")
                    dlg.open()
                except Exception:
                    try:
                        try:
                            _log().exception("_dlg_excluir_ramo falhou")
                        except NameError:
                            try:
                                log.exception("_dlg_excluir_ramo falhou")
                            except NameError:
                                from mod_intranet import observabilidade as _obs_fail
                                _obs_fail.get_logger("lista_telefonica").exception("_dlg_excluir_ramo falhou")
                    except Exception:
                        pass
                    try:
                        from mod_intranet.tema_modulo import notificar as _notificar_fail
                        _notificar_fail("Erro interno. Tente novamente.", tipo="error")
                    except Exception:
                        pass
                    return None

            def _dlg_mover(uid):
                try:
                    uni = lista.obter_unidade(uid)
                    if not uni:
                        return
                    with dialogo_card(titulo=f"Mover — {uni[1]} ({uni[2]})", largura="w-[420px]", chave_modulo="lista_telefonica") as (dlg, card):
                        ui.label("Escolha o novo pai (ou vazio para raiz, só secretaria).").classes("text-caption")
                        # opções conforme tipo
                        if uni[2] == "secretaria":
                            ui.label("Secretaria não pode ser movida para dentro (ficará na raiz).").classes("text-caption text-grey-6")
                            novo_pai = None
                            def confirmar():
                                try:
                                    ok, msg = lista.mover_unidade(uid, None, ator=usuario_logado)
                                    notificar(msg, type="positive" if ok else "negative")
                                    if ok:
                                        dlg.close()
                                        render_unidades.refresh()
                                except Exception:
                                    try:
                                        try:
                                            _log().exception("confirmar falhou")
                                        except NameError:
                                            try:
                                                log.exception("confirmar falhou")
                                            except NameError:
                                                from mod_intranet import observabilidade as _obs_fail
                                                _obs_fail.get_logger("lista_telefonica").exception("confirmar falhou")
                                    except Exception:
                                        pass
                                    try:
                                        from mod_intranet.tema_modulo import notificar as _notificar_fail
                                        _notificar_fail("Erro interno. Tente novamente.", tipo="error")
                                    except Exception:
                                        pass
                                    return None
                        elif uni[2] == "setor":
                            secs = lista.listar_unidades(parent_id=None, tipo="secretaria")
                            opts = {r[0]: r[1] for r in secs}
                            sel = ui.select(opts, label="Nova secretaria pai *").props("outlined dense").classes("w-full")
                            def confirmar():
                                try:
                                    if not sel.value:
                                        notificar("Escolha a secretaria", type="warning")
                                        return
                                    ok, msg = lista.mover_unidade(uid, sel.value, ator=usuario_logado)
                                    notificar(msg, type="positive" if ok else "negative")
                                    if ok:
                                        dlg.close()
                                        render_unidades.refresh()
                                except Exception:
                                    try:
                                        try:
                                            _log().exception("confirmar falhou")
                                        except NameError:
                                            try:
                                                log.exception("confirmar falhou")
                                            except NameError:
                                                from mod_intranet import observabilidade as _obs_fail
                                                _obs_fail.get_logger("lista_telefonica").exception("confirmar falhou")
                                    except Exception:
                                        pass
                                    try:
                                        from mod_intranet.tema_modulo import notificar as _notificar_fail
                                        _notificar_fail("Erro interno. Tente novamente.", tipo="error")
                                    except Exception:
                                        pass
                                    return None
                        else:  # subsetor
                            opts = {}
                            for sec in lista.listar_unidades(parent_id=None, tipo="secretaria"):
                                for setor in lista.listar_unidades(parent_id=sec[0], tipo="setor"):
                                    opts[setor[0]] = f"{sec[1]} > {setor[1]}"
                            sel = ui.select(opts, label="Novo setor pai *").props("outlined dense").classes("w-full")
                            def confirmar():
                                try:
                                    if not sel.value:
                                        notificar("Escolha o setor", type="warning")
                                        return
                                    ok, msg = lista.mover_unidade(uid, sel.value, ator=usuario_logado)
                                    notificar(msg, type="positive" if ok else "negative")
                                    if ok:
                                        dlg.close()
                                        render_unidades.refresh()
                                except Exception:
                                    try:
                                        try:
                                            _log().exception("confirmar falhou")
                                        except NameError:
                                            try:
                                                log.exception("confirmar falhou")
                                            except NameError:
                                                from mod_intranet import observabilidade as _obs_fail
                                                _obs_fail.get_logger("lista_telefonica").exception("confirmar falhou")
                                    except Exception:
                                        pass
                                    try:
                                        from mod_intranet.tema_modulo import notificar as _notificar_fail
                                        _notificar_fail("Erro interno. Tente novamente.", tipo="error")
                                    except Exception:
                                        pass
                                    return None
                        with ui.row().classes("w-full justify-end gap-2 mt-3"):
                            ui.button("Cancelar", on_click=dlg.close).props("flat")
                            botao("Mover", icone="drive_file_move", on_click=confirmar, variante="primario", chave_modulo="lista_telefonica")
                    dlg.open()
                except Exception:
                    try:
                        try:
                            _log().exception("_dlg_mover falhou")
                        except NameError:
                            try:
                                log.exception("_dlg_mover falhou")
                            except NameError:
                                from mod_intranet import observabilidade as _obs_fail
                                _obs_fail.get_logger("lista_telefonica").exception("_dlg_mover falhou")
                    except Exception:
                        pass
                    try:
                        from mod_intranet.tema_modulo import notificar as _notificar_fail
                        _notificar_fail("Erro interno. Tente novamente.", tipo="error")
                    except Exception:
                        pass
                    return None

            def _dlg_elevar(uid):
                try:
                    uni = lista.obter_unidade(uid)
                    if not uni:
                        return
                    with dialogo_card(titulo=f"Elevar/Rebaixar — {uni[1]}", largura="w-[420px]", chave_modulo="lista_telefonica") as (dlg, card):
                        ui.label(f"Tipo atual: {uni[2]}").classes("text-caption")
                        if uni[2] == "setor":
                            sel = ui.select({"secretaria": "Secretaria (elevar)"}, value="secretaria", label="Novo tipo").props("outlined dense").classes("w-full")
                        elif uni[2] == "subsetor":
                            sel = ui.select({"setor": "Setor (elevar)"}, value="setor", label="Novo tipo").props("outlined dense").classes("w-full")
                        else:
                            ui.label("Para rebaixar secretaria, use Mover e escolha a secretaria de destino.").classes("text-caption text-grey-6")
                            sel = None
                        def confirmar():
                            try:
                                if not sel or not sel.value:
                                    dlg.close()
                                    return
                                ok, msg = lista.elevar_rebaixar(uid, sel.value, ator=usuario_logado)
                                notificar(msg, type="positive" if ok else "negative")
                                if ok:
                                    dlg.close()
                                    render_unidades.refresh()
                            except Exception:
                                try:
                                    try:
                                        _log().exception("confirmar falhou")
                                    except NameError:
                                        try:
                                            log.exception("confirmar falhou")
                                        except NameError:
                                            from mod_intranet import observabilidade as _obs_fail
                                            _obs_fail.get_logger("lista_telefonica").exception("confirmar falhou")
                                except Exception:
                                    pass
                                try:
                                    from mod_intranet.tema_modulo import notificar as _notificar_fail
                                    _notificar_fail("Erro interno. Tente novamente.", tipo="error")
                                except Exception:
                                    pass
                                return None
                        with ui.row().classes("w-full justify-end gap-2 mt-3"):
                            ui.button("Cancelar", on_click=dlg.close).props("flat")
                            if sel:
                                botao("Aplicar", icone="vertical_align_top", on_click=confirmar, variante="primario", chave_modulo="lista_telefonica")
                    dlg.open()
                except Exception:
                    try:
                        try:
                            _log().exception("_dlg_elevar falhou")
                        except NameError:
                            try:
                                log.exception("_dlg_elevar falhou")
                            except NameError:
                                from mod_intranet import observabilidade as _obs_fail
                                _obs_fail.get_logger("lista_telefonica").exception("_dlg_elevar falhou")
                    except Exception:
                        pass
                    try:
                        from mod_intranet.tema_modulo import notificar as _notificar_fail
                        _notificar_fail("Erro interno. Tente novamente.", tipo="error")
                    except Exception:
                        pass
                    return None

            def _dlg_reordenar(parent_id, tipo):
                # lista irmãs
                try:
                    irmas = lista.listar_unidades(parent_id=parent_id, tipo=tipo)
                    if len(irmas) < 2:
                        notificar("Nada a reordenar", type="warning")
                        return
                    with dialogo_card(titulo="Reordenar (comutar)", largura="w-[500px]", chave_modulo="lista_telefonica") as (dlg, card):
                        ui.label("Arraste mentalmente: use ↑/↓ para comutar ordem.").classes("text-caption")
                        ordem = [r[0] for r in irmas]
                        # render lista com botões ↑/↓
                        col = ui.column().classes("w-full gap-1")
                        def render_ord():
                            try:
                                col.clear()
                                with col:
                                    for idx, uid in enumerate(ordem):
                                        nome = next((r[1] for r in irmas if r[0]==uid), str(uid))
                                        with ui.row().classes("w-full items-center gap-2 border rounded px-2 py-1"):
                                            ui.label(f"{idx+1}. {nome}").classes("flex-1")
                                            def _up(i=idx):
                                                try:
                                                    if i>0:
                                                        ordem[i-1], ordem[i] = ordem[i], ordem[i-1]
                                                        render_ord()
                                                except Exception:
                                                    try:
                                                        try:
                                                            _log().exception("_up falhou")
                                                        except NameError:
                                                            try:
                                                                log.exception("_up falhou")
                                                            except NameError:
                                                                from mod_intranet import observabilidade as _obs_fail
                                                                _obs_fail.get_logger("lista_telefonica").exception("_up falhou")
                                                    except Exception:
                                                        pass
                                                    try:
                                                        from mod_intranet.tema_modulo import notificar as _notificar_fail
                                                        _notificar_fail("Erro interno. Tente novamente.", tipo="error")
                                                    except Exception:
                                                        pass
                                                    return None
                                            def _down(i=idx):
                                                try:
                                                    if i < len(ordem)-1:
                                                        ordem[i], ordem[i+1] = ordem[i+1], ordem[i]
                                                        render_ord()
                                                except Exception:
                                                    try:
                                                        try:
                                                            _log().exception("_down falhou")
                                                        except NameError:
                                                            try:
                                                                log.exception("_down falhou")
                                                            except NameError:
                                                                from mod_intranet import observabilidade as _obs_fail
                                                                _obs_fail.get_logger("lista_telefonica").exception("_down falhou")
                                                    except Exception:
                                                        pass
                                                    try:
                                                        from mod_intranet.tema_modulo import notificar as _notificar_fail
                                                        _notificar_fail("Erro interno. Tente novamente.", tipo="error")
                                                    except Exception:
                                                        pass
                                                    return None
                                            botao_icone("arrow_upward", on_click=_up, tooltip="Mover para cima", chave_modulo="lista_telefonica")
                                            botao_icone("arrow_downward", on_click=_down, tooltip="Mover para baixo", chave_modulo="lista_telefonica")
                            except Exception:
                                try:
                                    try:
                                        _log().exception("render_ord falhou")
                                    except NameError:
                                        try:
                                            log.exception("render_ord falhou")
                                        except NameError:
                                            from mod_intranet import observabilidade as _obs_fail
                                            _obs_fail.get_logger("lista_telefonica").exception("render_ord falhou")
                                except Exception:
                                    pass
                                try:
                                    from mod_intranet.tema_modulo import notificar as _notificar_fail
                                    _notificar_fail("Erro interno. Tente novamente.", tipo="error")
                                except Exception:
                                    pass
                                return None
                        render_ord()
                        def salvar():
                            try:
                                ok, msg = lista.reordenar_unidades(parent_id, ordem, ator=usuario_logado)
                                notificar(msg, type="positive" if ok else "negative")
                                if ok:
                                    dlg.close()
                                    render_unidades.refresh()
                            except Exception:
                                try:
                                    try:
                                        _log().exception("salvar falhou")
                                    except NameError:
                                        try:
                                            log.exception("salvar falhou")
                                        except NameError:
                                            from mod_intranet import observabilidade as _obs_fail
                                            _obs_fail.get_logger("lista_telefonica").exception("salvar falhou")
                                except Exception:
                                    pass
                                try:
                                    from mod_intranet.tema_modulo import notificar as _notificar_fail
                                    _notificar_fail("Erro interno. Tente novamente.", tipo="error")
                                except Exception:
                                    pass
                                return None
                        with ui.row().classes("w-full justify-end gap-2 mt-3"):
                            ui.button("Cancelar", on_click=dlg.close).props("flat")
                            botao("Salvar ordem", icone="swap_vert", on_click=salvar, variante="primario", chave_modulo="lista_telefonica")
                    dlg.open()
                except Exception:
                    try:
                        try:
                            _log().exception("_dlg_reordenar falhou")
                        except NameError:
                            try:
                                log.exception("_dlg_reordenar falhou")
                            except NameError:
                                from mod_intranet import observabilidade as _obs_fail
                                _obs_fail.get_logger("lista_telefonica").exception("_dlg_reordenar falhou")
                    except Exception:
                        pass
                    try:
                        from mod_intranet.tema_modulo import notificar as _notificar_fail
                        _notificar_fail("Erro interno. Tente novamente.", tipo="error")
                    except Exception:
                        pass
                    return None

        # === Card Contatos ===
        with card_admin("Contatos — incluir via usuários ou externo, telefone, transferir", icone="contacts", chave_modulo="lista_telefonica", grade=False):
            ui.label("Contatos são sempre exibidos em ordem alfabética dentro da unidade.").classes("text-caption text-grey-6")

            # Seletor de unidade destino para criação
            todas = lista.listar_todas_unidades()
            # mapa id->caminho
            def _caminho(uid):
                uni = lista.obter_unidade(uid)
                if not uni:
                    return ""
                partes=[uni[1]]
                pid=uni[3]
                while pid:
                    p=lista.obter_unidade(pid)
                    if not p: break
                    partes.append(p[1])
                    pid=p[3]
                return " > ".join(reversed(partes))
            opts_unidade = {r[0]: f"{_caminho(r[0])} ({r[2]})" for r in todas}
            sel_unidade = ui.select(opts_unidade, label="Unidade * (onde incluir)").props("outlined dense").classes("w-full").props('data-testid=admin-contato-unidade')

            with ui.row().classes("w-full gap-3 flex-wrap"):
                inp_nome = ui.input("Nome *").props("outlined dense").classes("flex-1 min-w-[220px]").props('data-testid=admin-contato-nome')
                try:
                    from mod_intranet import telefone as _tel_ct
                    _campo_tel_ct = _tel_ct.criar_campo_telefone(
                        valor="", testid_ddi="admin-contato-ddi",
                        testid_numero="admin-contato-tel")
                except Exception:
                    _campo_tel_ct = None
                    inp_tel = ui.input("Telefone *", placeholder="(38) 99999-9999").props("outlined dense").classes("flex-1 min-w-[180px]").props('data-testid=admin-contato-tel')

            def _tel_ct_valor():
                try:
                    if _campo_tel_ct is not None:
                        return _campo_tel_ct["obter"]() or ""
                    return inp_tel.value or ""
                except Exception:
                    return ""
            # Busca usuário — campo de pesquisa + select de resultados (corrige listagem do mod_gest_cad_usuario)
            with ui.row().classes("w-full gap-2 flex-wrap items-end"):
                inp_busca_user = ui.input("Buscar usuário na base", placeholder="digite nome, login ou e-mail").props("outlined dense clearable").classes("flex-1 min-w-[260px]").props('data-testid=admin-contato-busca')
                sel_user = ui.select({}, label="Usuário encontrado (opcional)").props("outlined dense clearable").classes("flex-1 min-w-[260px]").props('data-testid=admin-contato-user')
                def ao_buscar_user(e):
                    try:
                        termo = (e.value or "").strip() if hasattr(e, 'value') else str(e or "").strip()
                        try:
                            # Cadastro via API pública do núcleo (AGENTS.md §2: a
                            # Lista Telefônica não importa a Gestão de Usuários).
                            from mod_intranet import integracoes
                            todos = integracoes.listar_usuarios_gestao()
                            # filtra por nome, login, e-mail, completo (sem acentos, case-insensitive)
                            import unicodedata, re
                            def _norm(s):
                                s = unicodedata.normalize("NFKD", s or "").encode("ascii","ignore").decode().lower()
                                return s
                            termo_n = _norm(termo)
                            if termo_n:
                                filtrados = [r for r in todos if termo_n in _norm(r[1]) or termo_n in _norm(r[9] or "") or termo_n in _norm(r[4] or "")]
                            else:
                                filtrados = todos[:20]
                            # exclui deletados
                            filtrados = [r for r in filtrados if not r[8]]
                            opts = {}
                            for r in filtrados[:30]:
                                nome_trat = (r[9] or r[1]).strip() or r[1]
                                # mostra perfil para distinguir
                                opts[r[1]] = f"{nome_trat} (@{r[1]} • {r[2]})"
                            sel_user.set_options(opts)
                            sel_user.update()
                        except Exception as ex:
                            try:
                                from mod_intranet import observabilidade
                                observabilidade.get_logger("lista_telefonica").warning(f"busca usuario falhou: {ex}")
                            except Exception:
                                pass
                    except Exception:
                        try:
                            try:
                                _log().exception("ao_buscar_user falhou")
                            except NameError:
                                try:
                                    log.exception("ao_buscar_user falhou")
                                except NameError:
                                    from mod_intranet import observabilidade as _obs_fail
                                    _obs_fail.get_logger("lista_telefonica").exception("ao_buscar_user falhou")
                        except Exception:
                            pass
                        try:
                            from mod_intranet.tema_modulo import notificar as _notificar_fail
                            _notificar_fail("Erro interno. Tente novamente.", tipo="error")
                        except Exception:
                            pass
                        return None
                inp_busca_user.on_value_change(ao_buscar_user)
                # carrega lista inicial (20 primeiros ativos)
                ao_buscar_user(type("E", (), {"value": ""})())
                # botão preencher nome via usuário
                def _preencher():
                    try:
                        if sel_user.value:
                            # busca nome completo
                            try:
                                # Cadastro via API pública do núcleo (AGENTS.md §2:
                                # a Lista Telefônica não importa a Gestão de Usuários).
                                from mod_intranet import integracoes
                                row = integracoes.obter_usuario_gestao(sel_user.value)
                                if row:
                                    # row[9] é nome completo, row[4] é o telefone
                                    inp_nome.value = row[9] or sel_user.value
                                    try:
                                        inp_nome.update()
                                    except Exception:
                                        pass
                                    if row[4]:
                                        try:
                                            if _campo_tel_ct is not None:
                                                _campo_tel_ct["definir"](row[4])
                                            elif not inp_tel.value:
                                                inp_tel.value = row[4]
                                                inp_tel.update()
                                        except Exception:
                                            pass
                            except Exception:
                                pass
                    except Exception:
                        try:
                            try:
                                _log().exception("_preencher falhou")
                            except NameError:
                                try:
                                    log.exception("_preencher falhou")
                                except NameError:
                                    from mod_intranet import observabilidade as _obs_fail
                                    _obs_fail.get_logger("lista_telefonica").exception("_preencher falhou")
                        except Exception:
                            pass
                        try:
                            from mod_intranet.tema_modulo import notificar as _notificar_fail
                            _notificar_fail("Erro interno. Tente novamente.", tipo="error")
                        except Exception:
                            pass
                        return None
                botao("Usar usuário", icone="person_search", on_click=_preencher, variante="texto", chave_modulo="lista_telefonica")

            def criar_contato():
                try:
                    if not sel_unidade.value:
                        notificar("Escolha a unidade", type="warning")
                        return
                    ok, msg = lista.criar_contato(sel_unidade.value, inp_nome.value or "", _tel_ct_valor(), user_nome=sel_user.value, ator=usuario_logado)
                    notificar(msg, type="positive" if ok else "negative")
                    if ok:
                        render_contatos.refresh()
                except Exception:
                    try:
                        try:
                            _log().exception("criar_contato falhou")
                        except NameError:
                            try:
                                log.exception("criar_contato falhou")
                            except NameError:
                                from mod_intranet import observabilidade as _obs_fail
                                _obs_fail.get_logger("lista_telefonica").exception("criar_contato falhou")
                    except Exception:
                        pass
                    try:
                        from mod_intranet.tema_modulo import notificar as _notificar_fail
                        _notificar_fail("Erro interno. Tente novamente.", tipo="error")
                    except Exception:
                        pass
                    return None
            botao("Incluir contato", icone="person_add", on_click=criar_contato, variante="primario", chave_modulo="lista_telefonica").props('data-testid=admin-criar-contato')

            # Lista de contatos por unidade selecionada + ações transferir/ordenar (alfabética é automática, mas permite transferir)
            @ui.refreshable
            def render_contatos():
                try:
                    uid = sel_unidade.value
                    if not uid:
                        return
                    contatos = lista.listar_contatos(uid)
                    with ui.column().classes("w-full gap-1 mt-3"):
                        ui.label(f"Contatos em {lista.obter_unidade(uid)[1] if lista.obter_unidade(uid) else ''} — {len(contatos)} (alfabético)").classes("text-caption font-bold")
                        if not contatos:
                            ui.label("Nenhum contato.").classes("text-grey-6 italic")
                            return
                        for cid, uid_c, nome, tel, user_n, tipo, data in contatos:
                            try:
                                from mod_intranet import telefone as _tel_fmt_adm
                                _tel_exib_adm = _tel_fmt_adm.formatar_para_exibicao(tel) or "—"
                            except Exception:
                                _tel_exib_adm = tel or "—"
                            with ui.row().classes("w-full items-center gap-2 border rounded px-2 py-1"):
                                ui.label(nome).classes("font-medium flex-1")
                                ui.label(_tel_exib_adm).classes("text-caption font-mono")
                                if user_n:
                                    ui.badge(f"@{user_n}", color="blue-grey-2").props("outline dense")
                                def _editar(cid=cid, n=nome, t=tel):
                                    try:
                                        with dialogo_card(titulo=f"Editar — {n}", largura="w-[380px]", chave_modulo="lista_telefonica") as (dlg, card):
                                            inp_n2 = ui.input("Nome", value=n).props("outlined dense").classes("w-full")
                                            try:
                                                from mod_intranet import telefone as _tel_ce
                                                _campo_t_ce = _tel_ce.criar_campo_telefone(valor=t or "")
                                            except Exception:
                                                _campo_t_ce = None
                                                inp_t2 = ui.input("Telefone", value=t).props("outlined dense").classes("w-full")
                                            def _tel_ce_valor():
                                                try:
                                                    if _campo_t_ce is not None:
                                                        return _campo_t_ce["obter"]() or ""
                                                    return inp_t2.value
                                                except Exception:
                                                    return ""
                                            def salvar():
                                                try:
                                                    ok, msg = lista.editar_contato(cid, nome=inp_n2.value, telefone=_tel_ce_valor(), ator=usuario_logado)
                                                    notificar(msg, type="positive" if ok else "negative")
                                                    if ok:
                                                        dlg.close()
                                                        render_contatos.refresh()
                                                except Exception:
                                                    try:
                                                        try:
                                                            _log().exception("salvar falhou")
                                                        except NameError:
                                                            try:
                                                                log.exception("salvar falhou")
                                                            except NameError:
                                                                from mod_intranet import observabilidade as _obs_fail
                                                                _obs_fail.get_logger("lista_telefonica").exception("salvar falhou")
                                                    except Exception:
                                                        pass
                                                    try:
                                                        from mod_intranet.tema_modulo import notificar as _notificar_fail
                                                        _notificar_fail("Erro interno. Tente novamente.", tipo="error")
                                                    except Exception:
                                                        pass
                                                    return None
                                            with ui.row().classes("w-full justify-end gap-2 mt-3"):
                                                ui.button("Cancelar", on_click=dlg.close).props("flat")
                                                botao("Salvar", icone="save", on_click=salvar, variante="primario", chave_modulo="lista_telefonica")
                                        dlg.open()
                                    except Exception:
                                        try:
                                            try:
                                                _log().exception("_editar falhou")
                                            except NameError:
                                                try:
                                                    log.exception("_editar falhou")
                                                except NameError:
                                                    from mod_intranet import observabilidade as _obs_fail
                                                    _obs_fail.get_logger("lista_telefonica").exception("_editar falhou")
                                        except Exception:
                                            pass
                                        try:
                                            from mod_intranet.tema_modulo import notificar as _notificar_fail
                                            _notificar_fail("Erro interno. Tente novamente.", tipo="error")
                                        except Exception:
                                            pass
                                        return None
                                def _transferir(cid=cid, nome=nome):
                                    try:
                                        with dialogo_card(titulo=f"Transferir — {nome}", largura="w-[420px]", chave_modulo="lista_telefonica") as (dlg, card):
                                            # todas unidades como destino
                                            opts = {r[0]: f"{_caminho(r[0])}" for r in lista.listar_todas_unidades()}
                                            sel_dest = ui.select(opts, label="Unidade destino *").props("outlined dense").classes("w-full")
                                            def confirmar():
                                                try:
                                                    if not sel_dest.value:
                                                        notificar("Escolha destino", type="warning")
                                                        return
                                                    ok, msg = lista.transferir_contato(cid, sel_dest.value, ator=usuario_logado)
                                                    notificar(msg, type="positive" if ok else "negative")
                                                    if ok:
                                                        dlg.close()
                                                        render_contatos.refresh()
                                                except Exception:
                                                    try:
                                                        try:
                                                            _log().exception("confirmar falhou")
                                                        except NameError:
                                                            try:
                                                                log.exception("confirmar falhou")
                                                            except NameError:
                                                                from mod_intranet import observabilidade as _obs_fail
                                                                _obs_fail.get_logger("lista_telefonica").exception("confirmar falhou")
                                                    except Exception:
                                                        pass
                                                    try:
                                                        from mod_intranet.tema_modulo import notificar as _notificar_fail
                                                        _notificar_fail("Erro interno. Tente novamente.", tipo="error")
                                                    except Exception:
                                                        pass
                                                    return None
                                            with ui.row().classes("w-full justify-end gap-2 mt-3"):
                                                ui.button("Cancelar", on_click=dlg.close).props("flat")
                                                botao("Transferir", icone="swap_horiz", on_click=confirmar, variante="primario", chave_modulo="lista_telefonica")
                                        dlg.open()
                                    except Exception:
                                        try:
                                            try:
                                                _log().exception("_transferir falhou")
                                            except NameError:
                                                try:
                                                    log.exception("_transferir falhou")
                                                except NameError:
                                                    from mod_intranet import observabilidade as _obs_fail
                                                    _obs_fail.get_logger("lista_telefonica").exception("_transferir falhou")
                                        except Exception:
                                            pass
                                        try:
                                            from mod_intranet.tema_modulo import notificar as _notificar_fail
                                            _notificar_fail("Erro interno. Tente novamente.", tipo="error")
                                        except Exception:
                                            pass
                                        return None
                                botao_icone("edit", on_click=_editar, tooltip="Editar", chave_modulo="lista_telefonica")
                                botao_icone("swap_horiz", on_click=_transferir, tooltip="Transferir para outro ponto", chave_modulo="lista_telefonica")
                                botao_icone("delete", on_click=lambda _, cid=cid: (lista.excluir_contato(cid, ator=usuario_logado), render_contatos.refresh(), notificar("Excluído", type="positive")), tooltip="Excluir", chave_modulo="lista_telefonica")
                except Exception:
                    try:
                        try:
                            _log().exception("render_contatos falhou")
                        except NameError:
                            try:
                                log.exception("render_contatos falhou")
                            except NameError:
                                from mod_intranet import observabilidade as _obs_fail
                                _obs_fail.get_logger("lista_telefonica").exception("render_contatos falhou")
                    except Exception:
                        pass
                    try:
                        from mod_intranet.tema_modulo import notificar as _notificar_fail
                        _notificar_fail("Erro interno. Tente novamente.", tipo="error")
                    except Exception:
                        pass
                    return None

            sel_unidade.on_value_change(lambda e: render_contatos.refresh())
            render_contatos()

        from mod_intranet.rotinas import painel_backup
        painel_backup(usuario_logado, "lista_telefonica")
    except Exception:
        try:
            try:
                _log().exception("mostrar_administracao falhou")
            except NameError:
                try:
                    log.exception("mostrar_administracao falhou")
                except NameError:
                    from mod_intranet import observabilidade as _obs_fail
                    _obs_fail.get_logger("lista_telefonica").exception("mostrar_administracao falhou")
        except Exception:
            pass
        try:
            from mod_intranet.tema_modulo import notificar as _notificar_fail
            _notificar_fail("Erro interno. Tente novamente.", tipo="error")
        except Exception:
            pass
        return None
