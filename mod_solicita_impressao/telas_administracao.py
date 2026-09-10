"""Administration panel for the print-request module.

EN — NiceGUI rendering of the print module admin tab (requests, departments,
units, authorization grants, quotas, and module configuration). Exposes
`mostrar_administracao(usuario_logado, eh_admin)` so the main screen can
delegate this entire panel to a dedicated module.

PT — Renderização NiceGUI da aba Administração do módulo de impressão
(solicitações, secretarias, setores, responsáveis, cotas e configurações).
Expõe `mostrar_administracao(usuario_logado, eh_admin)` para que a tela
principal delegue todo este painel a um módulo dedicado.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from nicegui import ui
from mod_intranet.bd_manipulador import audit_log
from mod_intranet.ui_comum import botao
from mod_intranet import observabilidade

from mod_solicita_impressao.telas import (
    _status_chip,
    _barra_cota,
    _admin_solicitacoes,
    _card_admin_grupo,
    _imprimir_grupo,
    _confirmar_impressao_grupo,
    _recuar_grupo,
    _autorizar_grupo,
    _recusar_grupo,
)


# ================= ADMINISTRAÇÃO =================

def mostrar_administracao(usuario_logado: str, eh_admin: bool):
    """Renders the full administration panel for the print module.

    EN — Builds six sub-tabs (Solicitações, Secretarias, Setores,
    Responsáveis, Cotas, Configurações) covering every master-data and
    configuration surface an administrator needs. `eh_admin` is accepted
    for symmetry with other tabs and to allow future role checks.

    PT — Monta as seis sub-abas (Solicitações, Secretarias, Setores,
    Responsáveis, Cotas, Configurações) cobrindo todos os cadastros e
    configurações que o administrador do módulo precisa. `eh_admin` é
    aceito por simetria com as demais abas e para permitir checagens
    futuras de papel.
    """
    from mod_solicita_impressao import bd_manipulador as bd
    with ui.tabs().classes("w-full") as subtab:
        ui.tab("solic", "Solicitações")
        ui.tab("secr", "Secretarias")
        ui.tab("setor", "Setores")
        ui.tab("resp", "Responsáveis")
        ui.tab("cotas", "Cotas")
        ui.tab("rel", "Relatórios")
        ui.tab("conf", "Configurações")
    with ui.tab_panels(subtab, value="solic").classes("w-full"):
        with ui.tab_panel("solic"):
            _admin_solicitacoes(usuario_logado)
        with ui.tab_panel("secr"):
            _admin_secretarias(usuario_logado)
        with ui.tab_panel("setor"):
            _admin_setores(usuario_logado)
        with ui.tab_panel("resp"):
            _admin_responsaveis(usuario_logado)
        with ui.tab_panel("cotas"):
            _admin_cotas(usuario_logado)
        with ui.tab_panel("rel"):
            _admin_relatorio(usuario_logado)
        with ui.tab_panel("conf"):
            _admin_configuracoes(usuario_logado)


def _admin_solicitacoes(usuario_logado):
    """Admin sub-tab: PEDIDOS grouped by secretaria -> setor (delegates to telas).

    Sub-aba de administração: pedidos agrupados por secretaria → setor (delega para telas)."""
    from mod_solicita_impressao.telas import _admin_solicitacoes as _impl
    _impl(usuario_logado)


# ================= ADMIN: SECRETARIAS =================

def _admin_secretarias(usuario_logado):
    """Admin sub-tab: department CRUD (create/edit/delete with quota).

    Sub-aba de administração: CRUD de secretarias (criar/editar/excluir com cota)."""
    from mod_solicita_impressao import bd_manipulador as bd
    wrap = ui.column().classes("w-full gap-2")

    with ui.card().classes("w-full"):
        ui.label("Nova Secretaria").classes("text-subtitle2")
        with ui.row().classes("w-full gap-2 flex-wrap"):
            n_nome = ui.input("Nome*").props("outlined dense")
            n_sigla = ui.input("Sigla").props("outlined dense")
            n_cota = ui.number("Cota mensal (páginas)", value=0, min=0).props("outlined dense")
            n_lim = ui.number("Limite pedidos abertos (0=ilimitado)", value=0, min=0).props(
                "outlined dense")

            def criar():
                ok, msg = bd.criar_secretaria(n_nome.value, n_sigla.value, n_cota.value,
                                              n_lim.value, ator=usuario_logado)
                ui.notify(msg, type="positive" if ok else "negative")
                if ok:
                    n_nome.value = n_sigla.value = ""
                    n_cota.value = 0
                    n_lim.value = 0
                    atualizar()
            botao("Criar", on_click=criar, variante="solido",
                   chave_modulo="solicita_impressao")

    def atualizar():
        wrap.clear()
        rows = bd.listar_secretarias()
        with wrap:
            if not rows:
                ui.label("Nenhuma secretaria.").classes("text-grey-6")
                return
            for sid, nome, sigla, cota, lim, ativo in rows:
                with ui.card().classes("w-full"):
                    with ui.row().classes("w-full items-center justify-between"):
                        ui.label(f"{nome} ({sigla or '—'}) — cota: {cota} — "
                                 f"lim. pedidos: {lim or 'ilimitado'} — "
                                 f"{'ativo' if ativo else 'inativo'}").classes("text-body2")
                        with ui.row().classes("gap-1"):
                            botao("Editar", icone="edit",
                                      on_click=lambda s=sid, n=nome, sg=sigla, c=cota, l=lim:
                                      _editar_secretaria(s, n, sg, c, l, usuario_logado, atualizar),
                                      variante="texto", compacto=True,
                                      chave_modulo="solicita_impressao")
                            botao("Excluir", icone="delete",
                                      on_click=lambda s=sid: _excluir_secretaria(s, usuario_logado, atualizar),
                                      variante="perigo", compacto=True,
                                      chave_modulo="solicita_impressao")
    atualizar()


def _editar_secretaria(sid, nome, sigla, cota, lim, usuario, atualizar):
    """Edit-department dialog (name, sigla, monthly quota, open-request limit).

    Diálogo de edição de secretaria (nome, sigla, cota mensal, limite de pedidos abertos)."""
    from mod_solicita_impressao import bd_manipulador as bd
    with ui.dialog() as dlg, ui.card().classes("w-96"):
        n = ui.input("Nome", value=nome).props("outlined dense")
        sg = ui.input("Sigla", value=sigla or "").props("outlined dense")
        c = ui.number("Cota mensal", value=cota, min=0).props("outlined dense")
        l = ui.number("Limite pedidos abertos (0=ilimitado)", value=lim, min=0).props(
            "outlined dense")

        def salvar():
            ok, msg = bd.editar_secretaria(sid, n.value, sg.value, c.value, l.value, ator=usuario)
            ui.notify(msg, type="positive" if ok else "negative")
            dlg.close()
            atualizar()
        botao("Salvar", on_click=salvar, variante="solido",
                   chave_modulo="solicita_impressao")
    dlg.open()


def _excluir_secretaria(sid, usuario, atualizar):
    """Deletes a department (with confirmation-free immediate action).

    Exclui uma secretaria (ação imediata, sem confirmação)."""
    from mod_solicita_impressao import bd_manipulador as bd
    ok, msg = bd.excluir_secretaria(sid, ator=usuario)
    ui.notify(msg, type="positive" if ok else "negative")
    atualizar()


# ================= ADMIN: SETORES =================

def _admin_setores(usuario_logado):
    """Admin sub-tab: unit CRUD under departments (optional own quota).

    Sub-aba de administração: CRUD de setores sob secretarias (cota própria opcional)."""
    from mod_solicita_impressao import bd_manipulador as bd
    wrap = ui.column().classes("w-full gap-2")

    with ui.card().classes("w-full"):
        ui.label("Novo Setor").classes("text-subtitle2")
        secr_opts = {s[0]: (s[2] or s[1]) for s in bd.listar_secretarias(ativo=1)}
        with ui.row().classes("w-full gap-2 flex-wrap"):
            n_nome = ui.input("Nome*").props("outlined dense").classes("grow")
            n_secr = ui.select(secr_opts, label="Secretaria*").props("outlined dense").classes("grow")
            n_cota = ui.number("Cota mensal (0=usa secretaria)", value=0, min=0).props(
                "outlined dense")
            n_lim = ui.number("Limite pedidos abertos (0=ilimitado)", value=0, min=0).props(
                "outlined dense")

            def criar():
                if not n_secr.value:
                    ui.notify("Selecione secretaria", type="warning"); return
                ok, msg = bd.criar_setor(n_nome.value, n_secr.value, n_cota.value,
                                         n_lim.value, ator=usuario_logado)
                ui.notify(msg, type="positive" if ok else "negative")
                if ok:
                    n_nome.value = ""
                    n_cota.value = 0
                    n_lim.value = 0
                    atualizar()
            botao("Criar", on_click=criar, variante="solido",
                   chave_modulo="solicita_impressao")

    def atualizar():
        wrap.clear()
        rows = bd.listar_setores()
        with wrap:
            if not rows:
                ui.label("Nenhum setor.").classes("text-grey-6")
                return
            for stid, nome, secr, cota, lim, ativo in rows:
                sec_nome = ""
                s = bd.obter_secretaria(secr)
                if s:
                    sec_nome = s[2] or s[1]
                with ui.card().classes("w-full"):
                    with ui.row().classes("w-full items-center justify-between"):
                        ui.label(f"{nome} — {sec_nome} — cota: {cota} — "
                                 f"lim. pedidos: {lim or 'ilimitado'} — "
                                 f"{'ativo' if ativo else 'inativo'}").classes("text-body2")
                        with ui.row().classes("gap-1"):
                            botao("Editar", icone="edit",
                                      on_click=lambda st=stid, nm=nome, sc=secr, c=cota, l=lim:
                                      _editar_setor(st, nm, sc, c, l, usuario_logado, atualizar),
                                      variante="texto", compacto=True,
                                      chave_modulo="solicita_impressao")
                            botao("Excluir", icone="delete",
                                      on_click=lambda st=stid: _excluir_setor(st, usuario_logado, atualizar),
                                      variante="perigo", compacto=True,
                                      chave_modulo="solicita_impressao")
    atualizar()


def _editar_setor(stid, nome, secr, cota, lim, usuario, atualizar):
    """Edit-unit dialog (name, monthly quota, open-request limit; department kept).

    Diálogo de edição de setor (nome, cota mensal, limite de pedidos; secretaria mantida)."""
    from mod_solicita_impressao import bd_manipulador as bd
    with ui.dialog() as dlg, ui.card().classes("w-96"):
        n = ui.input("Nome", value=nome).props("outlined dense")
        c = ui.number("Cota mensal", value=cota, min=0).props("outlined dense")
        l = ui.number("Limite pedidos abertos (0=ilimitado)", value=lim, min=0).props(
            "outlined dense")

        def salvar():
            ok, msg = bd.editar_setor(stid, n.value, None, c.value, l.value, ator=usuario)
            ui.notify(msg, type="positive" if ok else "negative")
            dlg.close()
            atualizar()
        botao("Salvar", on_click=salvar, variante="solido",
                   chave_modulo="solicita_impressao")
    dlg.open()


def _excluir_setor(stid, usuario, atualizar):
    """Deletes a unit.

    Exclui um setor."""
    from mod_solicita_impressao import bd_manipulador as bd
    ok, msg = bd.excluir_setor(stid, ator=usuario)
    ui.notify(msg, type="positive" if ok else "negative")
    atualizar()


# ================= ADMIN: RESPONSÁVEIS =================

def _admin_responsaveis(usuario_logado):
    """Admin sub-tab: grants authorization power to registered users.

    Sub-aba de administração: concede permissão de autorizar a usuários cadastrados."""
    from mod_solicita_impressao import bd_manipulador as bd
    wrap = ui.column().classes("w-full gap-2")

    with ui.card().classes("w-full"):
        ui.label("Novo Responsável por Autorização").classes("text-subtitle2")
        ui.label("Localize um usuário cadastrado e conceda a ele a permissão de "
                 "autorizar impressões (funciona mesmo para usuários 'comum').").classes(
            "text-caption text-grey-6")
        secr_opts = {s[0]: (s[2] or s[1]) for s in bd.listar_secretarias(ativo=1)}
        try:
            from mod_gest_cad_usuario import bd_manipulador as _gest
            _usuarios = _gest.listar_usuarios(filtro_ativo=True)
            user_opts = {u[1]: f"{u[1]} ({u[2]})" for u in _usuarios}
        except Exception:
            user_opts = {}
        with ui.row().classes("w-full gap-2"):
            n_user = ui.select(user_opts, label="Usuário*", with_input=True).props(
                "outlined dense clearable").classes("grow")
            n_secr = ui.select(secr_opts, label="Secretaria*").props("outlined dense").classes("grow")
            n_setor = ui.select({}, label="Setor (opcional)").props("outlined dense").classes("grow")

            def ao_secr(e):
                sid = e.value
                setores = bd.listar_setores(secretaria_id=sid, ativo=1) if sid else []
                n_setor.options = {st[0]: st[1] for st in setores}
                n_setor.value = None
                n_setor.update()
            n_secr.on_value_change(ao_secr)

            def criar():
                if not n_user.value:
                    ui.notify("Selecione um usuário", type="warning"); return
                if not n_secr.value:
                    ui.notify("Selecione secretaria", type="warning"); return
                ok, msg = bd.criar_responsavel(n_user.value, n_secr.value,
                                              n_setor.value, ator=usuario_logado)
                ui.notify(msg, type="positive" if ok else "negative")
                if ok:
                    n_user.value = None
                    n_secr.value = None
                    n_setor.value = None
                    n_setor.options = {}
                    n_setor.update()
                    atualizar()
            botao("Conceder permissão de autorizar impressão", icone="assignment_ind",
                      on_click=criar, variante="solido",
                      chave_modulo="solicita_impressao")

    def atualizar():
        wrap.clear()
        rows = bd.listar_responsaveis()
        with wrap:
            if not rows:
                ui.label("Nenhum responsável cadastrado.").classes("text-grey-6")
                return
            for rid, uname, secr, setor, ativo in rows:
                sec_nome = ""
                s = bd.obter_secretaria(secr)
                if s:
                    sec_nome = s[2] or s[1]
                st_nome = "—"
                if setor:
                    st = bd.obter_setor(setor)
                    if st:
                        st_nome = st[1]
                with ui.card().classes("w-full"):
                    with ui.row().classes("w-full items-center justify-between"):
                        ui.label(f"{uname} — {sec_nome} / {st_nome} — "
                                 f"{'ativo' if ativo else 'inativo'}").classes("text-body2")
                        botao("Excluir", icone="delete",
                                  on_click=lambda r=rid: _excluir_resp(r, usuario_logado, atualizar),
                                  variante="perigo", compacto=True,
                                  chave_modulo="solicita_impressao")
    atualizar()


def _excluir_resp(rid, usuario, atualizar):
    """Removes an authorization grant.

    Remove um vínculo de autorização."""
    from mod_solicita_impressao import bd_manipulador as bd
    ok, msg = bd.excluir_responsavel(rid, ator=usuario)
    ui.notify(msg, type="positive" if ok else "negative")
    atualizar()


# ================= ADMIN: COTAS =================

def _admin_cotas(usuario_logado):
    """Admin sub-tab: monthly quota report with edit/reset per department/unit.

    Sub-aba de administração: relatório mensal de cotas com editar/resetar por secretaria/setor."""
    from mod_solicita_impressao import bd_manipulador as bd
    wrap = ui.column().classes("w-full gap-2")

    def atualizar():
        wrap.clear()
        rel = bd.relatorio_cotas()
        with wrap:
            ui.label("Consumo de cotas — mês atual").classes("text-subtitle2")
            if not rel:
                ui.label("Cadastre secretarias para ver cotas.").classes("text-grey-6")
                return
            for sid, sec_nome, stid, st_nome, cota, usado, pct in rel:
                with ui.card().classes("w-full"):
                    with ui.row().classes("w-full items-center justify-between gap-2 flex-wrap"):
                        ui.label(f"{sec_nome} / {st_nome}").classes("text-body2 grow")
                        ui.label(f"{usado}/{cota} ({pct}%)").classes("text-caption text-grey-7")
                        _barra_cota(pct)
                        botao("Editar cota", icone="edit",
                                  on_click=lambda sc=sid, st=stid, c=cota:
                                  _editar_cota(sc, st, c, usuario_logado, atualizar),
                                  variante="texto", compacto=True,
                                  chave_modulo="solicita_impressao")
                        botao("Resetar", icone="restart_alt",
                                  on_click=lambda sc=sid, st=stid:
                                  _resetar_cota(sc, st, usuario_logado, atualizar),
                                  variante="restaurar_fill",
                                  chave_modulo="solicita_impressao")
    atualizar()


def _editar_cota(secr, setor, cota_atual, usuario, atualizar):
    """Edit-quota dialog for the month (department or unit).

    Diálogo de edição de cota do mês (secretaria ou setor)."""
    from mod_solicita_impressao import bd_manipulador as bd
    with ui.dialog() as dlg, ui.card().classes("w-80"):
        ui.label("Definir cota mensal (páginas)").classes("text-subtitle2")
        c = ui.number("Cota", value=cota_atual, min=0).props("outlined dense")

        def salvar():
            ok, msg = bd.definir_cota(secr, setor, c.value, ator=usuario)
            ui.notify(msg, type="positive" if ok else "negative")
            dlg.close()
            atualizar()
        botao("Salvar", on_click=salvar, variante="solido",
                   chave_modulo="solicita_impressao")
    dlg.open()


def _resetar_cota(secr, setor, usuario, atualizar):
    """Zeros the month's consumption for the department/unit.

    Zera o consumo do mês para a secretaria/setor."""
    from mod_solicita_impressao import bd_manipulador as bd
    ok, msg = bd.resetar_consumo(secr, setor, ator=usuario)
    ui.notify(msg, type="positive" if ok else "negative")
    atualizar()


# ================= ADMIN: CONFIGURAÇÕES =================

def _admin_configuracoes(usuario_logado):
    """Admin sub-tab: printers, retention times, form defaults, watermark, theme.

    Sub-aba de administração: impressoras, tempos de retenção, padrões do formulário,
    marca d'água e tema."""
    from mod_solicita_impressao import bd_manipulador as bd
    with ui.card().classes("w-full"):
        ui.label("Configurações do Módulo").classes("text-h6 font-bold")

        imp_a4 = ui.input("Impressora padrão (A4)",
                          value=bd.obter_config("impressora_padrao_nome", "")).props(
            "outlined dense").classes("w-full").tooltip(
            "Nome da impressora padrão. Se preenchido, botão 'Imprimir direto' envia ao cliente.")
        imp_a3 = ui.input("Impressora padrão (A3)",
                          value=bd.obter_config("impressora_padrao_a3_nome", "")).props(
            "outlined dense").classes("w-full")
        alertas = ui.textarea("Alertas da nova solicitação (uma frase por linha)",
                            value=bd.obter_config("alertas_nova_solicitacao", "")).props(
            "outlined dense").classes("w-full")
        max_mb = ui.number("Tamanho máx. upload (MB)",
                           value=int(bd.obter_config("max_arquivo_mb", "10")), min=1).props(
            "outlined dense")

        ui.separator().classes("my-2")
        ui.label("Retenção de arquivos e padrões do formulário").classes("text-subtitle2")
        tempo_rasc = ui.number(
            "Minutos para confirmar o envio (depois o arquivo é descartado)*",
            value=int(bd.obter_config("tempo_expira_rascunho_min", "10")),
            min=1, max=120).props("outlined dense").classes("w-full")
        tempo_imp = ui.number(
            "Minutos para excluir o arquivo após a impressão*",
            value=int(bd.obter_config("tempo_exclui_impresso_min", "10")),
            min=1, max=120).props("outlined dense").classes("w-full")
        with ui.row().classes("w-full gap-4"):
            p_pad_papel = ui.select({"A4": "A4", "A3": "A3"}, label="Papel padrão",
                                    value=bd.obter_config("padrao_papel", "A4")).props(
                "outlined dense")
            p_pad_cor = ui.select({"PB": "Preto e Branco", "Color": "Colorido"},
                                  label="Cor padrão",
                                  value=bd.obter_config("padrao_cor", "Color")).props(
                "outlined dense")
            p_pad_fv = ui.checkbox("Frente e verso por padrão",
                                   value=bd.obter_config("padrao_frente_verso", "0") == "1")
            p_pad_tipo = ui.select({"sulfite": "Sulfite", "fotografico": "Fotográfico",
                                    "verge": "Vergê"},
                                   label="Tipo de papel padrão",
                                   value=bd.obter_config("padrao_tipo_papel", "sulfite")).props(
                "outlined dense")

        ui.separator().classes("my-2")
        ui.label("Marca d'água (opcional)").classes("text-subtitle2")
        md_ativa = ui.checkbox("Ativar marca d'água",
                               value=bd.obter_config("marca_dagua_ativa", "1") == "1")
        md_texto = ui.input("Texto (placeholders: {data} {usuario} {id} {secretaria} {setor} {solicitante})",
                            value=bd.obter_config("marca_dagua_texto", "")).props(
            "outlined dense").classes("w-full")
        md_pos = ui.select({"centro": "Centro", "rodape": "Rodapé",
                            "canto_superior": "Canto superior",
                            "canto_inferior": "Canto inferior"},
                           label="Posição",
                           value=bd.obter_config("marca_dagua_posicao", "centro")).props(
            "outlined dense")
        with ui.row().classes("w-full gap-4"):
            md_op = ui.number("Opacidade (0-100)",
                             value=int(bd.obter_config("marca_dagua_opacidade", "30")),
                             min=0, max=100).props("outlined dense")
            md_fs = ui.number("Tamanho fonte",
                             value=int(bd.obter_config("marca_dagua_fonte_tamanho", "24")),
                             min=6, max=200).props("outlined dense")
            md_rot = ui.number("Rotação (graus)",
                              value=int(bd.obter_config("marca_dagua_rotacao", "45")),
                              min=0, max=360).props("outlined dense")
            md_cor = ui.color_input("Cor",
                                   value=bd.obter_config("marca_dagua_cor", "#CCCCCC"))

        ui.separator().classes("my-2")
        _painel_impressoras(usuario_logado)

        ui.separator().classes("my-2")
        from mod_intranet.tema_modulo import ler_tema, bloco_aparencia
        _tema_sol = ler_tema("solicita_impressao", cor_botao="#000000",
                             cor_titulo="#212121", btn_tamanho="medium")
        bloco_aparencia(usuario_logado, "solicita_impressao", _tema_sol,
                        prefixo_auditoria="solicita_impressao",
                        com_card=False)

        def salvar():
            bd.definir_config("impressora_padrao_nome", imp_a4.value or "")
            bd.definir_config("impressora_padrao_a3_nome", imp_a3.value or "")
            bd.definir_config("alertas_nova_solicitacao", alertas.value or "")
            bd.definir_config("max_arquivo_mb", int(max_mb.value or 10))
            bd.definir_config("tempo_expira_rascunho_min", int(tempo_rasc.value or 10))
            bd.definir_config("tempo_exclui_impresso_min", int(tempo_imp.value or 10))
            bd.definir_config("padrao_papel", p_pad_papel.value or "A4")
            bd.definir_config("padrao_cor", p_pad_cor.value or "PB")
            bd.definir_config("padrao_frente_verso", "1" if p_pad_fv.value else "0")
            bd.definir_config("padrao_tipo_papel", p_pad_tipo.value or "sulfite")
            bd.definir_config("marca_dagua_ativa", "1" if md_ativa.value else "0")
            bd.definir_config("marca_dagua_texto", md_texto.value or "")
            bd.definir_config("marca_dagua_posicao", md_pos.value or "centro")
            bd.definir_config("marca_dagua_opacidade", int(md_op.value or 30))
            bd.definir_config("marca_dagua_fonte_tamanho", int(md_fs.value or 24))
            bd.definir_config("marca_dagua_rotacao", int(md_rot.value or 45))
            bd.definir_config("marca_dagua_cor", md_cor.value or "#CCCCCC")
            try:
                audit_log(usuario_logado, "solicita_impressao", "configuracao",
                          "configurações do módulo salvas (impressoras, tempos, "
                          "padrões e marca d'água)")
            except Exception as e:
                observabilidade.get_logger("solicita_impressao").warning(
                    f"salvar: falha ao auditar configurações | {e}")
            ui.notify("Configurações salvas", type="positive")
        botao("Salvar configurações", icone="save", on_click=salvar,
            variante="solido", chave_modulo="solicita_impressao",
            extra_classes="min-w-[180px]") \
            .props('data-testid=solicita-admin-salvar')

    from mod_intranet.rotinas import painel_backup
    painel_backup(usuario_logado, "solicita_impressao")

def _painel_impressoras(usuario_logado):
    """Admin block: register/list/set-default printers used by the print selector.

    Cadastro de impressoras (nome, papel, cor, frente/verso, sulfite, driver PCL6)
    usadas no seletor do botão 'Imprimir'; também permite marcar a padrão A4/A3."""
    from mod_solicita_impressao import bd_manipulador as bd
    with ui.column().classes("w-full gap-2"):
        ui.label("Impressoras cadastradas (seletor de impressão)").classes("text-subtitle2")

        with ui.card().classes("w-full"):
            ui.label("Cadastrar impressora").classes("text-caption text-grey-7")
            with ui.row().classes("w-full items-center gap-2 flex-wrap"):
                n_nome = ui.input("Nome*").props("outlined dense clearable").classes("grow")
                n_papel = ui.select({"A4": "A4", "A3": "A3"}, label="Papel",
                                    value="A4").props("outlined dense").classes("w-28")
                n_cor = ui.select({"Color": "Colorido", "PB": "Preto e Branco"},
                                  label="Cor", value="Color").props("outlined dense").classes("w-36")
                n_fv = ui.checkbox("Frente/verso", value=False)
                n_sulf = ui.checkbox("Sulfite", value=True)
                n_drv = ui.input("Driver", value="PCL6").props("outlined dense").classes("w-36")

                def criar():
                    ok, msg = bd.criar_impressora(
                        n_nome.value, n_papel.value, n_cor.value, n_fv.value, n_sulf.value,
                        n_drv.value, ator=usuario_logado)
                    ui.notify(msg, type="positive" if ok else "negative")
                    if ok:
                        n_nome.value = ""
                        atualizar()
                botao("Cadastrar", icone="add", on_click=criar, variante="solido",
                      chave_modulo="solicita_impressao")

        lista = ui.column().classes("w-full gap-1")

        def atualizar():
            lista.clear()
            imps = bd.listar_impressoras()
            pad_a4 = bd.obter_config("impressora_padrao_nome", "")
            pad_a3 = bd.obter_config("impressora_padrao_a3_nome", "")
            if not imps:
                ui.label("Nenhuma impressora cadastrada ainda.").classes(
                    "text-caption text-grey-6")
                return
            with lista:
                for i in imps:
                    pid, nome, papel, cor, fv, sulf, drv, ativo = i
                    eh_pad = nome in (pad_a4, pad_a3)
                    with ui.row().classes("w-full items-center gap-2"):
                        ui.label(f"{nome} — {papel} · {cor} · "
                                 f"{'frente/verso' if fv else 'somente frente'} · "
                                 f"driver {drv or 'PCL6'}"
                                 + (" ⭐ padrão" if eh_pad else "")).classes(
                            "grow text-body2")
                        if not eh_pad:
                            botao("Definir padrão", icone="star",
                                  on_click=lambda p=pid: _def_padrao(p, atualizar),
                                  variante="texto", compacto=True,
                                  chave_modulo="solicita_impressao")
                        botao("Excluir", icone="delete",
                              on_click=lambda p=pid: _excluir_imp(p, atualizar),
                              variante="perigo", compacto=True,
                              chave_modulo="solicita_impressao")

        def _def_padrao(pid, atualizar):
            ok, msg = bd.definir_impressora_padrao(pid, ator=usuario_logado)
            ui.notify(msg, type="positive" if ok else "negative")
            atualizar()

        def _excluir_imp(pid, atualizar):
            ok, msg = bd.excluir_impressora(pid, ator=usuario_logado)
            ui.notify(msg, type="positive" if ok else "negative")
            atualizar()

        atualizar()


# ================= ADMIN: RELATÓRIOS =================

def _tabela_relatorio(titulo, linhas, colunas):
    """Renders a small report table with header + rows (or an empty note).

    Monta um card com `ui.table` a partir do título, das linhas (listas de
    valores) e das colunas (rótulos). Se `linhas` estiver vazio, exibe apenas
    um aviso "sem impressões no período"."""
    if not linhas:
        ui.label(f"{titulo}: sem impressões no período.").classes("text-caption text-grey-6")
        return
    with ui.card().classes("w-full"):
        ui.label(titulo).classes("text-subtitle2")
        with ui.table({
            "columns": [{"name": f"c{i}", "label": c, "align": "left"}
                        for i, c in enumerate(colunas)],
            "rows": [dict((f"c{i}", v) for i, v in enumerate(r)) for r in linhas],
        }).classes("w-full").style("overflow-x:auto"):
            pass


def _admin_relatorio(usuario_logado):
    """Admin sub-tab: print report by fixed monthly periods or custom calendar
    range, focused on cost reimbursement — who printed, how many pages (color
    and B&W) and the consumption per secretaria/setor to charge the transfer.

    Sub-aba Relatórios: prazos fixos mensais (este mês, mês anterior, últimos
    6 meses, ano atual) ou período personalizado no calendário, gerando o
    relatório na hora. O objetivo é gerenciar quem imprimiu e quantas páginas,
    para cobrar das secretarias/setores o repasse dos custos de impressão."""
    from mod_solicita_impressao import bd_manipulador as bd
    import datetime as _dt
    wrap = ui.column().classes("w-full gap-2")

    with ui.card().classes("w-full"):
        ui.label("Relatório de impressões (repasse de custos)").classes("text-subtitle2")
        with ui.row().classes("w-full items-center gap-2 flex-wrap"):
            botao("Este mês", icone="calendar_month",
                  on_click=lambda: _prazo_fixo("mes_atual"),
                  variante="contorno", chave_modulo="solicita_impressao")
            botao("Mês anterior", icone="calendar_month",
                  on_click=lambda: _prazo_fixo("mes_anterior"),
                  variante="contorno", chave_modulo="solicita_impressao")
            botao("Últimos 6 meses", icone="date_range",
                  on_click=lambda: _prazo_fixo("6_meses"),
                  variante="contorno", chave_modulo="solicita_impressao")
            botao("Ano atual", icone="event",
                  on_click=lambda: _prazo_fixo("ano_atual"),
                  variante="contorno", chave_modulo="solicita_impressao")
        ui.separator().classes("my-1")
        with ui.row().classes("w-full items-center gap-2 flex-wrap"):
            inp_dt_ini = ui.input("Data inicial").props("outlined dense type=date").classes("w-44")
            inp_dt_fim = ui.input("Data final").props("outlined dense type=date").classes("w-44")
            botao("Gerar relatório", icone="assessment", on_click=lambda: gerar(),
                  variante="solido", chave_modulo="solicita_impressao")

    def atualizar():
        wrap.clear()
        with wrap:
            ui.label("Escolha um prazo fixo mensal acima ou informe um período "
                     "no calendário para gerar o relatório.").classes("text-grey-6")
    atualizar()

    def _prazo_fixo(tipo):
        hoje = _dt.date.today()
        if tipo == "mes_atual":
            ini = hoje.replace(day=1)
            fim = hoje
        elif tipo == "mes_anterior":
            ultimo = hoje.replace(day=1) - _dt.timedelta(days=1)
            ini = ultimo.replace(day=1)
            fim = ultimo
        elif tipo == "6_meses":
            ini = (hoje.replace(day=1) - _dt.timedelta(days=183))
            fim = hoje
        else:  # ano_atual
            ini = hoje.replace(month=1, day=1)
            fim = hoje
        inp_dt_ini.value = ini.strftime("%Y-%m-%d")
        inp_dt_fim.value = fim.strftime("%Y-%m-%d")
        gerar()

    def gerar():
        rel = bd.relatorio_impressao(inp_dt_ini.value or None, inp_dt_fim.value or None)
        geral = rel["geral"]
        wrap.clear()
        with wrap:
            if not any(geral):
                ui.label("Nenhuma impressão registrada no período.").classes("text-grey-6")
                return
            ui.label(f"Período: {inp_dt_ini.value or 'início'} a {inp_dt_fim.value or 'hoje'}").classes(
                "text-caption text-grey-6")
            _tabela_relatorio(
                "Cobrança por secretaria (repasse)",
                rel["por_secretaria"],
                ["Secretaria", "Pedidos", "Cópias total", "Cópias color", "Cópias PB",
                 "Págs. total", "Págs. color", "Págs. PB"])
            _tabela_relatorio(
                "Cobrança por setor (repasse)",
                rel["por_setor"],
                ["Secretaria", "Setor", "Pedidos", "Cópias total", "Cópias color", "Cópias PB",
                 "Págs. total", "Págs. color", "Págs. PB"])
            _tabela_relatorio(
                "Quem imprimiu",
                rel["por_impressor"],
                ["Quem imprimiu", "Pedidos", "Cópias total", "Cópias color", "Cópias PB",
                 "Págs. total", "Págs. color", "Págs. PB"])
            _tabela_relatorio(
                "Quem autorizou",
                rel["por_autorizador"],
                ["Autorizador", "Pedidos", "Cópias total", "Cópias color", "Cópias PB",
                 "Págs. total", "Págs. color", "Págs. PB"])
            _tabela_relatorio(
                "Total geral",
                [list(geral)],
                ["Pedidos", "Cópias total", "Cópias color", "Cópias PB",
                 "Págs. total", "Págs. color", "Págs. PB"])

    inp_dt_ini.on_value_change(lambda: gerar())
    inp_dt_fim.on_value_change(lambda: gerar())
