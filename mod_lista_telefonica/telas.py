"""Lista Telefônica — organograma expansível (rota /lista-telefonica).

EN: Phone directory with expandable Secretary→Sector→Subsetor + search + mobile tel.
"""

import sys, os, re
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from nicegui import ui
from mod_intranet import autenticacao
from mod_intranet.aba_modulo import cabecalho, campo_busca
from mod_intranet.tema_modulo import ler_tema, notificar
from mod_intranet.ui_comum import botao, botao_icone
from mod_lista_telefonica import bd_manipulador as lista

log = __import__("mod_intranet.observabilidade", fromlist=["get_logger"]).get_logger("lista_telefonica")


def _pode_ver(user_nome, perfil):
    if perfil == "administrador_geral":
        return True
    try:
        return autenticacao.validar_acesso_modulo(user_nome, "lista_telefonica")
    except Exception:
        return False


def _eh_admin(user_nome, perfil):
    return perfil == "administrador_geral" or autenticacao.eh_admin_do_modulo(user_nome, "lista_telefonica")


def mostrar_tela(user_nome: str, perfil_global: str = ""):
    try:
        if not _pode_ver(user_nome, perfil_global):
            with ui.column().classes("w-full items-center p-12 gap-3"):
                ui.icon("block", size="64px").classes("text-red-8")
                ui.label("Acesso restrito").classes("text-h6")
                ui.label("Somente usuários com acesso à Lista Telefônica.").classes("text-body2 text-grey-7")
            return

        tema = ler_tema("lista_telefonica", cor_botao="#000000", cor_texto_botao="#FFFFFF",
                        texto_header="Organograma expansível — navegue por Secretaria, Setor e Subsetor. Contatos em ordem alfabética.")
        ui.colors(primary=tema["cor_botao"])
        t_cor_titulo = tema["cor_titulo"]
        t_cor_fundo = tema["cor_fundo"]
        t_texto_header = tema["texto_header"]

        estado = {"secretaria": None, "setor": None, "subsetor": None, "busca": ""}

        # Busca global
        def ao_buscar(e):
            try:
                estado["busca"] = (e.value or "").strip()
                render_busca.refresh()
            except Exception:
                try:
                    try:
                        _log().exception("ao_buscar falhou")
                    except NameError:
                        try:
                            log.exception("ao_buscar falhou")
                        except NameError:
                            from mod_intranet import observabilidade as _obs_fail
                            _obs_fail.get_logger("lista_telefonica").exception("ao_buscar falhou")
                except Exception:
                    pass
                try:
                    from mod_intranet.tema_modulo import notificar as _notificar_fail
                    _notificar_fail("Erro interno. Tente novamente.", tipo="error")
                except Exception:
                    pass
                return None

        with ui.column().classes("w-full p-6 gap-4"):
            cabecalho("Lista Telefônica", t_texto_header, chave_modulo="lista_telefonica",
                      cor_titulo=t_cor_titulo, cor_fundo=t_cor_fundo)

            # Barra superior: busca + navegação expansível
            with ui.row().classes("w-full items-center gap-4 flex-nowrap bg-white rounded-lg shadow-sm px-3 py-2").style("min-width:0"):
                with ui.row().classes("items-center gap-2 flex-nowrap shrink-0").style("width:min(46%, 620px)"):
                    campo_busca("🔍 Buscar — nome, telefone, unidade", ao_buscar,
                                tooltip="Pesquisa em unidades e contatos (sem acentos)").props('data-testid=lista-busca')

            # Navegação expansível: 3 selects em cascata
            with ui.card().classes("w-full p-4 gap-3"):
                ui.label("Navegue pelo organograma").classes("text-subtitle2 font-bold text-grey-8")
                ui.label("Selecione a Secretaria para abrir os Setores; selecione o Setor para abrir os Subsetores.").classes("text-caption text-grey-6 -mt-2")

                # Carrega secretarias
                secretarias = lista.listar_unidades(parent_id=None, tipo="secretaria")
                opts_sec = {r[0]: r[1] for r in secretarias}
                sel_sec = ui.select(opts_sec, label="Secretaria *", with_input=True).props("outlined dense clearable").classes("w-full").props('data-testid=lista-select-secretaria')
                sel_set = ui.select({}, label="Setor").props("outlined dense clearable").classes("w-full").props('data-testid=lista-select-setor')
                sel_sub = ui.select({}, label="Subsetor").props("outlined dense clearable").classes("w-full").props('data-testid=lista-select-subsetor')
                sel_set.disable()
                sel_sub.disable()

                wrap_contatos = ui.column().classes("w-full gap-2 mt-2")

                def unidade_selecionada():
                    try:
                        if sel_sub.value:
                            return sel_sub.value
                        if sel_set.value:
                            return sel_set.value
                        if sel_sec.value:
                            return sel_sec.value
                        return None
                    except Exception:
                        try:
                            try:
                                _log().exception("unidade_selecionada falhou")
                            except NameError:
                                try:
                                    log.exception("unidade_selecionada falhou")
                                except NameError:
                                    from mod_intranet import observabilidade as _obs_fail
                                    _obs_fail.get_logger("lista_telefonica").exception("unidade_selecionada falhou")
                        except Exception:
                            pass
                        try:
                            from mod_intranet.tema_modulo import notificar as _notificar_fail
                            _notificar_fail("Erro interno. Tente novamente.", tipo="error")
                        except Exception:
                            pass
                        return None

                def render_contatos():
                    try:
                        wrap_contatos.clear()
                        uid = unidade_selecionada()
                        if not uid:
                            with wrap_contatos:
                                ui.label("Selecione uma unidade para ver os contatos.").classes("text-grey-6 italic")
                            return
                        uni = lista.obter_unidade(uid)
                        contatos = lista.listar_contatos(uid)
                        with wrap_contatos:
                            ui.label(f"Contatos — {uni[1]} ({uni[2]})" if uni else "Contatos").classes("text-subtitle2 font-bold")
                            if uni and uni[5]:
                                ui.label(f"Telefone da unidade: {uni[5]}").classes("text-caption text-grey-7")
                            if not contatos:
                                ui.label("Nenhum contato nesta unidade.").classes("text-grey-6 italic")
                                return
                            ui.label(f"{len(contatos)} contato(s) — ordem alfabética").classes("text-caption text-grey-5")
                            # Lista alfabética já vem ordenada
                            with ui.column().classes("w-full gap-1"):
                                for cid, uid_c, nome, tel, user_n, tipo, data in contatos:
                                    with ui.row().classes("w-full items-center justify-between border rounded-lg px-3 py-2 hover:bg-blue-50/50"):
                                        with ui.row().classes("items-center gap-2"):
                                            ui.icon("person" if tipo == "vinculado" else "badge").classes("text-grey-6")
                                            # Nome clicável para ligar no celular
                                            # Usa link tel: + tooltip
                                            # Detecta mobile via CSS, mas sempre oferece ação
                                            with ui.element("div").classes("flex flex-col"):
                                                # Nome como link tel
                                                tel_limpo = re.sub(r"[^0-9+]", "", tel or "")
                                                if tel_limpo:
                                                    # NiceGUI link com href tel:
                                                    ui.link(nome, target=f"tel:{tel_limpo}").classes("font-medium text-primary").tooltip("Toque para ligar (celular)")
                                                    ui.label(tel).classes("text-caption text-grey-6 font-mono")
                                                else:
                                                    ui.label(nome).classes("font-medium")
                                                    ui.label(tel or "—").classes("text-caption text-grey-6")
                                                if user_n:
                                                    ui.label(f"@{user_n}").classes("text-caption text-grey-5")
                                        # Botão alternativo para mobile: oferece escolha ligar
                                        def _acao_tel(n=nome, t=tel):
                                            try:
                                                _dlg_ligar(n, t)
                                            except Exception:
                                                try:
                                                    try:
                                                        _log().exception("_acao_tel falhou")
                                                    except NameError:
                                                        try:
                                                            log.exception("_acao_tel falhou")
                                                        except NameError:
                                                            from mod_intranet import observabilidade as _obs_fail
                                                            _obs_fail.get_logger("lista_telefonica").exception("_acao_tel falhou")
                                                except Exception:
                                                    pass
                                                try:
                                                    from mod_intranet.tema_modulo import notificar as _notificar_fail
                                                    _notificar_fail("Erro interno. Tente novamente.", tipo="error")
                                                except Exception:
                                                    pass
                                                return None
                                        botao_icone("phone", on_click=_acao_tel, tooltip="Ligar / opções", chave_modulo="lista_telefonica").props('data-testid=lista-ligar')
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

                def _dlg_ligar(nome, telefone):
                    try:
                        from mod_intranet.ui_comum import dialogo_card
                        tel = re.sub(r"[^0-9+]", "", telefone or "")
                        with dialogo_card(titulo=f"Contato — {nome}", largura="w-[380px]", chave_modulo="lista_telefonica", max_altura=False) as (dlg, card):
                            ui.label(f"Telefone: {telefone or '—'}").classes("text-body1 font-mono")
                            ui.label("No celular, escolha Ligar. No desktop, o discador pode não estar configurado.").classes("text-caption text-grey-6")
                            with ui.row().classes("w-full justify-between mt-2"):
                                ui.button("Fechar", on_click=dlg.close).props("flat")
                                if tel:
                                    # Botão que tenta tel:
                                    def _ir_tel():
                                        try:
                                            try:
                                                ui.run_javascript(f"window.location.href='tel:{tel}'")
                                            except Exception:
                                                pass
                                            dlg.close()
                                        except Exception:
                                            try:
                                                try:
                                                    _log().exception("_ir_tel falhou")
                                                except NameError:
                                                    try:
                                                        log.exception("_ir_tel falhou")
                                                    except NameError:
                                                        from mod_intranet import observabilidade as _obs_fail
                                                        _obs_fail.get_logger("lista_telefonica").exception("_ir_tel falhou")
                                            except Exception:
                                                pass
                                            try:
                                                from mod_intranet.tema_modulo import notificar as _notificar_fail
                                                _notificar_fail("Erro interno. Tente novamente.", tipo="error")
                                            except Exception:
                                                pass
                                            return None
                                    botao("Ligar agora", icone="call", on_click=_ir_tel, variante="primario", chave_modulo="lista_telefonica")
                        dlg.open()
                    except Exception:
                        try:
                            try:
                                _log().exception("_dlg_ligar falhou")
                            except NameError:
                                try:
                                    log.exception("_dlg_ligar falhou")
                                except NameError:
                                    from mod_intranet import observabilidade as _obs_fail
                                    _obs_fail.get_logger("lista_telefonica").exception("_dlg_ligar falhou")
                        except Exception:
                            pass
                        try:
                            from mod_intranet.tema_modulo import notificar as _notificar_fail
                            _notificar_fail("Erro interno. Tente novamente.", tipo="error")
                        except Exception:
                            pass
                        return None

                def ao_sec(e):
                    try:
                        sel_set.value = None
                        sel_sub.value = None
                        sel_sub.set_options({})
                        sel_sub.disable()
                        sel_sub.update()
                        if e.value:
                            setores = lista.listar_unidades(parent_id=e.value, tipo="setor")
                            opts = {r[0]: r[1] for r in setores}
                            sel_set.set_options(opts)
                            sel_set.enable()
                        else:
                            sel_set.set_options({})
                            sel_set.disable()
                        sel_set.update()
                        render_contatos()
                    except Exception:
                        try:
                            try:
                                _log().exception("ao_sec falhou")
                            except NameError:
                                try:
                                    log.exception("ao_sec falhou")
                                except NameError:
                                    from mod_intranet import observabilidade as _obs_fail
                                    _obs_fail.get_logger("lista_telefonica").exception("ao_sec falhou")
                        except Exception:
                            pass
                        try:
                            from mod_intranet.tema_modulo import notificar as _notificar_fail
                            _notificar_fail("Erro interno. Tente novamente.", tipo="error")
                        except Exception:
                            pass
                        return None

                def ao_set(e):
                    try:
                        sel_sub.value = None
                        if e.value:
                            subs = lista.listar_unidades(parent_id=e.value, tipo="subsetor")
                            opts = {r[0]: r[1] for r in subs}
                            sel_sub.set_options(opts)
                            sel_sub.enable()
                        else:
                            sel_sub.set_options({})
                            sel_sub.disable()
                        sel_sub.update()
                        render_contatos()
                    except Exception:
                        try:
                            try:
                                _log().exception("ao_set falhou")
                            except NameError:
                                try:
                                    log.exception("ao_set falhou")
                                except NameError:
                                    from mod_intranet import observabilidade as _obs_fail
                                    _obs_fail.get_logger("lista_telefonica").exception("ao_set falhou")
                        except Exception:
                            pass
                        try:
                            from mod_intranet.tema_modulo import notificar as _notificar_fail
                            _notificar_fail("Erro interno. Tente novamente.", tipo="error")
                        except Exception:
                            pass
                        return None

                def ao_sub(e):
                    try:
                        render_contatos()
                    except Exception:
                        try:
                            try:
                                _log().exception("ao_sub falhou")
                            except NameError:
                                try:
                                    log.exception("ao_sub falhou")
                                except NameError:
                                    from mod_intranet import observabilidade as _obs_fail
                                    _obs_fail.get_logger("lista_telefonica").exception("ao_sub falhou")
                        except Exception:
                            pass
                        try:
                            from mod_intranet.tema_modulo import notificar as _notificar_fail
                            _notificar_fail("Erro interno. Tente novamente.", tipo="error")
                        except Exception:
                            pass
                        return None

                sel_sec.on_value_change(ao_sec)
                sel_set.on_value_change(ao_set)
                sel_sub.on_value_change(ao_sub)

                # Inicial
                render_contatos()

            # Resultado da busca (quando há termo)
            @ui.refreshable
            def render_busca():
                try:
                    termo = estado["busca"]
                    if not termo:
                        return
                    with ui.card().classes("w-full p-4 gap-2"):
                        ui.label(f"Resultados da busca — “{termo}”").classes("text-subtitle2 font-bold")
                        unidades = lista.buscar_unidades(termo)
                        contatos = lista.buscar_contatos(termo)
                        if not unidades and not contatos:
                            ui.label("Nenhum resultado.").classes("text-grey-6 italic")
                            return
                        if unidades:
                            ui.label(f"Unidades ({len(unidades)})").classes("text-caption font-bold text-grey-7")
                            for uid, nome, tipo, pid, ordem, tel, ativo in unidades[:10]:
                                caminho = _caminho_unidade(uid)
                                with ui.row().classes("w-full items-center gap-2 border-b py-1"):
                                    ui.icon("account_tree").classes("text-grey-5")
                                    ui.label(f"{nome} ({tipo})").classes("text-body2 flex-1")
                                    ui.label(tel or "").classes("text-caption text-grey-5")
                                    ui.label(caminho).classes("text-caption text-grey-4")
                        if contatos:
                            ui.label(f"Contatos ({len(contatos)})").classes("text-caption font-bold text-grey-7 mt-2")
                            for cid, uid_c, nome, tel, user_n, tipo, data in contatos[:20]:
                                with ui.row().classes("w-full items-center gap-2 border-b py-1"):
                                    ui.label(nome).classes("font-medium flex-1")
                                    ui.label(tel).classes("text-caption font-mono")
                                    # tel link
                                    tel_limpo = re.sub(r"[^0-9+]", "", tel or "")
                                    if tel_limpo:
                                        ui.link("Ligar", target=f"tel:{tel_limpo}").classes("text-caption text-primary")
                except Exception:
                    try:
                        try:
                            _log().exception("render_busca falhou")
                        except NameError:
                            try:
                                log.exception("render_busca falhou")
                            except NameError:
                                from mod_intranet import observabilidade as _obs_fail
                                _obs_fail.get_logger("lista_telefonica").exception("render_busca falhou")
                    except Exception:
                        pass
                    try:
                        from mod_intranet.tema_modulo import notificar as _notificar_fail
                        _notificar_fail("Erro interno. Tente novamente.", tipo="error")
                    except Exception:
                        pass
                    return None

            render_busca()
    except Exception:
        try:
            try:
                _log().exception("mostrar_tela falhou")
            except NameError:
                try:
                    log.exception("mostrar_tela falhou")
                except NameError:
                    from mod_intranet import observabilidade as _obs_fail
                    _obs_fail.get_logger("lista_telefonica").exception("mostrar_tela falhou")
        except Exception:
            pass
        try:
            from mod_intranet.tema_modulo import notificar as _notificar_fail
            _notificar_fail("Erro interno. Tente novamente.", tipo="error")
        except Exception:
            pass
        return None


def _caminho_unidade(uid):
    """Retorna caminho hierárquico Secretaria > Setor > Subsetor."""
    try:
        uni = lista.obter_unidade(uid)
        if not uni:
            return ""
        partes = [uni[1]]
        pid = uni[3]
        while pid:
            p = lista.obter_unidade(pid)
            if not p:
                break
            partes.append(p[1])
            pid = p[3]
        return " > ".join(reversed(partes))
    except Exception:
        return ""
