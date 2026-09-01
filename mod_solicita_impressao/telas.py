"""Tela do módulo Solicitação de Impressão — NiceGUI.

Rotas: /solicita-impressao
Áreas (por permissão):
  - Comum: Nova Solicitação, Minhas Solicitações
  - Responsável autorização: Autorização
  - Admin do módulo: Administração (todas + sub-abas de cadastro/cotas/config)
"""
import sys
import os
import time
import tempfile
import datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from nicegui import ui
from mod_intranet.aba_modulo import cabecalho
from mod_intranet.manipulador_bd import audit_log

MOD_DIR = os.path.dirname(os.path.abspath(__file__))


def mostrar_tela(usuario_logado: str, perfil: str):
    from mod_intranet import autenticacao
    from mod_solicita_impressao import manipulador_bd as bd

    # Permissões
    eh_admin = (perfil == "administrador_geral"
                or autenticacao.eh_admin_do_modulo(usuario_logado, "solicita_impressao"))
    eh_responsavel = _eh_responsavel(usuario_logado)

    # ================= TEMA (Aparência, prefixo solicita_impressao_) =================
    from mod_intranet.conexao_bd import get_config, set_config
    def _tema(chave, default):
        try:
            return (get_config(f"solicita_impressao_{chave}", default) or "").strip() or default
        except Exception:
            return default

    t_cor_botao = _tema("cor_botao", "#EF6C00")
    t_cor_txt_botao = _tema("cor_texto_botao", "#FFFFFF")
    t_cor_fundo = _tema("cor_fundo", "")
    t_cor_titulo = _tema("cor_titulo", "#212121")
    t_btn_tamanho = _tema("btn_tamanho", "medium")
    t_texto_header = _tema("texto_header",
                           "Solicite impressões, acompanhe pedidos e autorize demandas.")

    def _btn_cls():
        if t_btn_tamanho == "small":
            return "min-w-[140px] text-sm"
        if t_btn_tamanho == "large":
            return "min-w-[220px] text-lg"
        return "min-w-[180px]"

    def _btn_style():
        st = ""
        if t_cor_botao:
            st += f"background-color:{t_cor_botao};"
        if t_cor_txt_botao:
            st += f"color:{t_cor_txt_botao};"
        return st

    container = ui.column().classes("w-full gap-4")

    with container:
        cabecalho("Solicitação de Impressão",
                   t_texto_header,
                   cor_borda="#EF6C00", cor_titulo=t_cor_titulo, cor_fundo=t_cor_fundo)

        # Tabs conforme perfil
        tabs = []
        if not eh_admin:
            tabs.append(("nova", "Nova Solicitação"))
            tabs.append(("minhas", "Minhas Solicitações"))
            if eh_responsavel:
                tabs.append(("autorizar", "Autorização"))
        else:
            tabs.append(("nova", "Nova Solicitação"))
            tabs.append(("minhas", "Minhas Solicitações"))
            tabs.append(("autorizar", "Autorização"))
            tabs.append(("admin", "Administração"))

        if tabs:
            _icones = {"nova": "add_box", "minhas": "list_alt",
                       "autorizar": "approval", "admin": "admin_panel_settings"}
            with ui.tabs().classes("w-full") as tab_def:
                for key, label in tabs:
                    ui.tab(key, label, icon=_icones.get(key))
            with ui.tab_panels(tab_def, value=tabs[0][0]).classes("w-full"):
                for key, label in tabs:
                    with ui.tab_panel(key):
                        if key == "nova":
                            _tela_nova(usuario_logado, eh_admin)
                        elif key == "minhas":
                            _tela_minhas(usuario_logado, eh_admin)
                        elif key == "autorizar":
                            _tela_autorizar(usuario_logado, eh_admin)
                        elif key == "admin":
                            _tela_admin(usuario_logado, eh_admin)


# ================= HELPERS =================

def _eh_responsavel(user_nome):
    from mod_solicita_impressao import manipulador_bd as bd
    from mod_intranet import autenticacao
    # Busca vinculos onde o usuário é responsável
    try:
        vinculos = bd.listar_responsaveis(ativo=1)
        return any(v[1] == user_nome for v in vinculos)
    except Exception:
        return False


def _status_chip(status):
    mapeamento = {
        "pendente": ("Pendente", "blue"),
        "aguardando_autorizacao": ("Aguardando Autorização", "amber"),
        "autorizado": ("Autorizado", "light-blue"),
        "excedente_cota": ("Excedente de Cota", "orange"),
        "impresso": ("Impresso", "green"),
        "recusado": ("Recusado", "red"),
        "cancelado": ("Cancelado", "grey"),
    }
    label, cor = mapeamento.get(status, (status, "grey"))
    return ui.badge(label, color=cor)


def _barra_cota(percentual):
    cor = "green" if percentual < 80 else ("amber" if percentual < 100 else "red")
    ui.linear_progress(value=min(percentual, 100) / 100.0, color=cor).classes("w-32")
    ui.label(f"{percentual}%").classes("text-caption text-grey-7")


# ================= NOVA SOLICITAÇÃO =================

def _tela_nova(usuario_logado, eh_admin):
    from mod_solicita_impressao import manipulador_bd as bd

    aviso = bd.obter_config("aviso_presenca_obrigatoria", "")
    if aviso:
        ui.label("⚠ " + aviso).classes(
            "text-caption text-orange-9 bg-orange-1 rounded p-2 w-full")

    secretarias = bd.listar_secretarias(ativo=1)
    if not secretarias:
        ui.label("Nenhuma secretaria cadastrada. Procure o administrador.").classes(
            "text-orange-9")
        return

    with ui.card().classes("w-full shadow-lg"):
        with ui.card_section().classes("gap-2 w-full"):
            rascunhos = []                       # {rid, nome, paginas, expira, sel, _exp_label}
            MAX_ARQ = 10
            info_arq = ui.label("Nenhum arquivo enviado ainda.").classes(
                "text-caption text-grey-7")
            lista = ui.column().classes("w-full gap-1")

            def rebuild():
                lista.clear()
                if not rascunhos:
                    info_arq.text = "Nenhum arquivo enviado ainda."
                    return
                info_arq.text = (f"{len(rascunhos)} arquivo(s) recebido(s) — marque os que "
                                 f"deseja enviar e clique em 'Enviar solicitação'.")
                with lista:
                    for r in rascunhos:
                        with ui.row().classes("w-full items-center gap-2 flex-wrap"):
                            ui.checkbox(value=r["sel"]).on_value_change(
                                lambda v, r=r: r.__setitem__("sel", bool(v)))
                            ui.label(r["nome"]).classes("grow text-body2")
                            ui.label(f"{r['paginas']} pág.").classes("text-caption text-grey-6")
                            r["_exp_label"] = ui.label("").classes("text-caption text-orange-9")
                            ui.button(icon="delete", on_click=lambda r=r: _remover_um(r)).props(
                                "flat dense color=red").tooltip("Remover este arquivo")

            def _remover_um(r):
                bd.cancelar_rascunho(r["rid"], ator=usuario_logado)
                if r in rascunhos:
                    rascunhos.remove(r)
                rebuild()
                ui.notify("Arquivo removido do servidor", type="info")

            def _remover_selecionados():
                alvos = [r for r in rascunhos if r["sel"]]
                if not alvos:
                    ui.notify("Marque ao menos um arquivo para remover", type="warning")
                    return
                for r in alvos:
                    bd.cancelar_rascunho(r["rid"], ator=usuario_logado)
                    rascunhos.remove(r)
                rebuild()
                ui.notify(f"{len(alvos)} arquivo(s) removido(s)", type="info")

            async def ao_upload(e):
                # Fluxo funcional espelhado do Editor de PDF (on_multi_upload + FileUpload).
                pdfs = [f for f in e.files if (f.name or "").lower().endswith(".pdf")]
                if not pdfs:
                    ui.notify("Apenas arquivos PDF são aceitos", type="negative")
                    up.reset()
                    return
                if len(rascunhos) + len(pdfs) > MAX_ARQ:
                    ui.notify(f"Máximo de {MAX_ARQ} arquivos por solicitação. "
                              f"Remova algum antes de anexar mais.", type="warning")
                    pdfs = pdfs[:max(0, MAX_ARQ - len(rascunhos))]
                novos = 0
                for f in pdfs:
                    try:
                        conteudo = await f.read()
                    except Exception as ex:
                        ui.notify(f"Falha ao ler {f.name}: {ex}", type="negative")
                        continue
                    try:
                        rid, nome_servidor, n, caminho = bd.registrar_rascunho(
                            usuario_logado, conteudo, f.name)
                    except Exception as ex:
                        ui.notify(f"Falha no upload de {f.name}: {ex}", type="negative")
                        continue
                    if not rid:
                        ui.notify(f"Não foi possível ler {f.name} (PDF inválido?)",
                                  type="negative")
                        continue
                    rascunhos.append({"rid": rid, "nome": nome_servidor, "paginas": n,
                                      "expira": time.time() + bd.tempo_expira_rascunho_min() * 60,
                                      "sel": True, "_exp_label": None})
                    novos += 1
                if novos:
                    ui.notify(f"{novos} PDF(s) recebido(s). Confirme o envio abaixo.",
                              type="positive")
                rebuild()
                up.reset()

            up = ui.upload(
                label=f"Anexar PDFs (até {MAX_ARQ} por solicitação)*",
                multiple=True, max_files=MAX_ARQ, auto_upload=True,
                on_multi_upload=ao_upload).props("accept=.pdf").classes("w-full")

            ui.button("Remover selecionados", icon="delete",
                      on_click=_remover_selecionados).props("flat dense color=red")

            qtd_copias = ui.number("Quantidade de cópias*", value=1, min=1, max=9999).props(
                "outlined dense").classes("w-full")

            with ui.row().classes("w-full gap-4"):
                papel = ui.select({"A4": "A4", "A3": "A3"}, label="Tamanho do papel*",
                                   value=bd.obter_config("padrao_papel", "A4")).props(
                    "outlined dense")
                cor = ui.select({"PB": "Preto e Branco", "Color": "Colorido"},
                                label="Cor*",
                                value=bd.obter_config("padrao_cor", "PB")).props(
                    "outlined dense")
                frente_verso = ui.checkbox(
                    "Frente e verso",
                    value=bd.obter_config("padrao_frente_verso", "0") == "1")

            with ui.row().classes("w-full gap-4"):
                borda = ui.select({"curta": "Borda curta", "longa": "Borda longa"},
                                  label="Tipo de borda (se frente e verso)",
                                  value="longa").props("outlined dense")
                sulfite = ui.checkbox(
                    "Papel sulfite (trazer outro tipo)",
                    value=bd.obter_config("padrao_sulfite", "1") == "1")

                def toggle_borda():
                    borda.enabled = frente_verso.value
                frente_verso.on_value_change(toggle_borda)
                borda.enabled = frente_verso.value

            def ao_sulfite():
                if not sulfite.value:
                    ui.notify("Atenção: demais tipos de papel — o usuário deve levar o papel.",
                              type="warning")
            sulfite.on_value_change(ao_sulfite)

            obs = ui.textarea("Observações / orientações para o solicitante").props(
                "outlined dense").classes("w-full")

            with ui.row().classes("w-full gap-4"):
                sel_secretaria = ui.select(
                    {s[0]: (s[2] or s[1]) for s in secretarias},
                    label="Secretaria (crédito)*").props("outlined dense").classes("grow")
                sel_setor = ui.select({}, label="Setor / Unidade (opcional)").props(
                    "outlined dense").classes("grow")

                def ao_secretaria(e):
                    sid = e.value
                    setores = bd.listar_setores(secretaria_id=sid, ativo=1) if sid else []
                    sel_setor.options = {st[0]: st[1] for st in setores}
                    sel_setor.value = None
                    sel_setor.update()
                sel_secretaria.on_value_change(ao_secretaria)

            # Cada arquivo marcado vira uma solicitação (com as opções abaixo)
            prev_nome = ui.label(
                "Arquivos marcados serão enviados como solicitações separadas, "
                "com as opções abaixo.").classes("text-caption text-grey-6")

            def tick():
                if not rascunhos:
                    return
                agora = time.time()
                mudou = False
                for r in list(rascunhos):
                    if r["expira"] <= agora:
                        bd.cancelar_rascunho(r["rid"], ator=usuario_logado)
                        rascunhos.remove(r)
                        mudou = True
                    elif r.get("_exp_label") is not None:
                        resta = max(0, int(r["expira"] - agora))
                        mm, ss = divmod(resta, 60)
                        r["_exp_label"].text = f"⏳ descarta em {mm}:{ss:02d}"
                if mudou:
                    rebuild()

            ui.timer(1.0, tick)

            def enviar():
                if not rascunhos:
                    ui.notify("Anexe ao menos um PDF", type="warning")
                    return
                if not sel_secretaria.value:
                    ui.notify("Selecione a secretaria", type="warning")
                    return
                alvos = [r for r in rascunhos if r["sel"]]
                if not alvos:
                    ui.notify("Marque ao menos um arquivo para enviar", type="warning")
                    return
                criadas = 0
                falhas = []
                for r in alvos:
                    ok, msg, sid = bd.confirmar_rascunho(
                        r["rid"], int(qtd_copias.value or 1), papel.value, cor.value,
                        frente_verso.value, borda.value if frente_verso.value else None,
                        sulfite.value, obs.value, sel_secretaria.value, sel_setor.value,
                        ator=usuario_logado)
                    if ok:
                        if r in rascunhos:
                            rascunhos.remove(r)
                        criadas += 1
                    else:
                        falhas.append(msg)
                rebuild()
                if criadas:
                    ui.notify(f"{criadas} solicitação(ões) criada(s)!", type="positive")
                if falhas:
                    ui.notify("Falhas: " + " | ".join(falhas[:3]),
                              type="negative", multi_line=True)
                if criadas:
                    ui.timer(0.1, lambda: ui.navigate.reload(), once=True)

            btn_enviar = ui.button("Enviar solicitação", icon="send", on_click=enviar).props(
                "unelevated color=primary")


# ================= MINHAS SOLICITAÇÕES =================

def _tela_minhas(usuario_logado, eh_admin):
    from mod_solicita_impressao import manipulador_bd as bd
    wrap = ui.column().classes("w-full gap-2")

    def atualizar():
        wrap.clear()
        rows = bd.listar_solicitacoes(usuario=usuario_logado, limite=200)
        with wrap:
            if not rows:
                ui.label("Nenhuma solicitação ainda.").classes("text-grey-6")
                return
            for r in rows:
                _card_solicitacao(r, usuario_logado, eh_admin, pode_cancelar=True,
                                  atualizar=atualizar)
    atualizar()


# ================= AUTORIZAÇÃO =================

def _tela_autorizar(usuario_logado, eh_admin):
    from mod_solicita_impressao import manipulador_bd as bd
    wrap = ui.column().classes("w-full gap-2")

    def atualizar():
        wrap.clear()
        rows = bd.solicitar_solicitacoes_responsavel(usuario_logado)
        with wrap:
            if not rows:
                ui.label("Nenhuma solicitação pendente de autorização para seus vínculos.").classes(
                    "text-grey-6")
                return
            for r in rows:
                _card_solicitacao(r, usuario_logado, eh_admin, pode_autorizar=True,
                                  atualizar=atualizar)
    atualizar()


# ================= CARD DE SOLICITAÇÃO =================

def _card_solicitacao(r, usuario_logado, eh_admin, pode_cancelar=False,
                      pode_autorizar=False, atualizar=None):
    from mod_solicita_impressao import manipulador_bd as bd
    (sid, user, arq_serv, arq_orig, copias, papel, cor, fv, borda, sulf, obs,
     secr, setor, pag_arq, pag_calc, status, cota_exc, req_auth, aut_por,
     dt_aut, motivo, imp_por, dt_imp, dt_cri, sec_nome, sec_sig, st_nome) = r

    with ui.card().classes("w-full shadow-md border-l-8").style(
            "border-left-color:#EF6C00"):
        with ui.row().classes("w-full items-start justify-between flex-wrap"):
            with ui.column().classes("gap-0 grow"):
                ui.label(f"Solicitação #{sid} — {arq_orig or arq_serv}").classes(
                    "text-h6 font-bold text-grey-9")
                ui.label(
                    f"por {user} • {dt_cri[:16] if dt_cri else ''}").classes(
                    "text-caption text-grey-6")
            _status_chip(status)

        with ui.column().classes("w-full mt-1 gap-1"):
            ui.label(
                f"Copias: {copias} | Papel: {papel} | Cor: {cor} | "
                f"Frente/verso: {'Sim (' + (borda or '—') + ')' if fv else 'Não'} | "
                f"Sulfite: {'Sim' if sulf else 'NÃO (trazer papel)'}"
            ).classes("text-body2 text-grey-8")
            ui.label(
                f"Secretaria: {sec_nome or '?'} | Setor: {st_nome or '—'} | "
                f"Páginas arquivo: {pag_arq} | Páginas contabilizadas: {pag_calc}"
            ).classes("text-body2 text-grey-8")
            if obs:
                ui.label(f"Obs: {obs}").classes("text-caption text-grey-7")
            if cota_exc:
                ui.label("⚠ EXCEDENTE DE COTA — sujeito à autorização").classes(
                    "text-caption text-orange-9 font-bold")
            # Barra de cota da secretaria
            if secr:
                pct, usado, cota = bd.percentual_consumo(secr, setor)
                ui.label(f"Cota ({'setor' if setor else 'secretaria'}): {usado}/{cota} ({pct}%)").classes(
                    "text-caption text-grey-7")
                _barra_cota(pct)

        with ui.row().classes("w-full gap-2 mt-2 flex-wrap"):
            # Download sempre disponível
            sol = bd.obter_solicitacao(sid)
            if sol and sol.get("caminho_arquivo") and os.path.exists(sol["caminho_arquivo"]):
                ui.button("Baixar", icon="download",
                          on_click=lambda s=sol: _baixar(s)).props("flat dense")

            if pode_cancelar and status in ("pendente", "aguardando_autorizacao",
                                            "excedente_cota"):
                ui.button("Cancelar", icon="cancel",
                          on_click=lambda s=sid: _cancelar(s, usuario_logado, atualizar)).props(
                    "flat dense color=red")

            if pode_autorizar and status in ("aguardando_autorizacao", "excedente_cota"):
                ui.button("Autorizar", icon="check",
                          on_click=lambda s=sid: _autorizar(s, usuario_logado, atualizar)).props(
                    "flat dense color=green")
                ui.button("Recusar", icon="block",
                          on_click=lambda s=sid: _recusar(s, usuario_logado, atualizar)).props(
                    "flat dense color=red")


def _baixar(sol):
    from nicegui import ui as _ui
    caminho = sol.get("caminho_arquivo")
    if caminho and os.path.exists(caminho):
        _ui.download(caminho, filename=sol.get("arquivo_servidor") or "documento.pdf")


def _cancelar(sid, usuario, atualizar):
    from mod_solicita_impressao import manipulador_bd as bd
    ok, msg = bd.cancelar_solicitacao(sid, usuario, ator=usuario)
    ui.notify(msg, type="positive" if ok else "negative")
    if atualizar:
        atualizar()


def _autorizar(sid, usuario, atualizar):
    from mod_solicita_impressao import manipulador_bd as bd
    ok, msg = bd.autorizar_solicitacao(sid, usuario)
    ui.notify(msg, type="positive" if ok else "negative")
    if atualizar:
        atualizar()


def _recusar(sid, usuario, atualizar):
    from mod_solicita_impressao import manipulador_bd as bd
    with ui.dialog() as dlg, ui.card().classes("w-96"):
        ui.label("Motivo da recusa*").classes("text-subtitle2")
        motivo = ui.textarea("Motivo").props("outlined dense").classes("w-full")

        def confirmar():
            if not (motivo.value or "").strip():
                ui.notify("Informe o motivo", type="warning")
                return
            ok, msg = bd.recusar_solicitacao(sid, usuario, motivo.value.strip())
            ui.notify(msg, type="positive" if ok else "negative")
            dlg.close()
            if atualizar:
                atualizar()
        ui.button("Confirmar recusa", on_click=confirmar).props("unelevated color=red")
    dlg.open()


# ================= ADMINISTRAÇÃO =================

def _tela_admin(usuario_logado, eh_admin):
    from mod_solicita_impressao import manipulador_bd as bd
    with ui.tabs().classes("w-full") as subtab:
        ui.tab("solic", "Solicitações")
        ui.tab("secr", "Secretarias")
        ui.tab("setor", "Setores")
        ui.tab("resp", "Responsáveis")
        ui.tab("cotas", "Cotas")
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
        with ui.tab_panel("conf"):
            _admin_configuracoes(usuario_logado)


def _admin_solicitacoes(usuario_logado):
    from mod_solicita_impressao import manipulador_bd as bd
    wrap = ui.column().classes("w-full gap-2")

    def atualizar():
        wrap.clear()
        rows = bd.listar_solicitacoes(limite=400)
        with wrap:
            if not rows:
                ui.label("Nenhuma solicitação.").classes("text-grey-6")
                return
            for r in rows:
                _card_admin(r, usuario_logado, atualizar)
    atualizar()


def _card_admin(r, usuario_logado, atualizar):
    from mod_solicita_impressao import manipulador_bd as bd
    (sid, user, arq_serv, arq_orig, copias, papel, cor, fv, borda, sulf, obs,
     secr, setor, pag_arq, pag_calc, status, cota_exc, req_auth, aut_por,
     dt_aut, motivo, imp_por, dt_imp, dt_cri, sec_nome, sec_sig, st_nome) = r

    with ui.card().classes("w-full shadow-md border-l-8").style(
            "border-left-color:#EF6C00"):
        with ui.row().classes("w-full items-start justify-between flex-wrap"):
            with ui.column().classes("gap-0 grow"):
                ui.label(f"#{sid} — {arq_orig or arq_serv}").classes(
                    "text-h6 font-bold text-grey-9")
                ui.label(f"por {user} • {dt_cri[:16] if dt_cri else ''}").classes(
                    "text-caption text-grey-6")
            _status_chip(status)

        with ui.column().classes("w-full mt-1 gap-1"):
            ui.label(
                f"Copias:{copias} | {papel} | {cor} | FV:{'Sim' if fv else 'Não'} | "
                f"Sulfite:{'Sim' if sulf else 'NÃO'} | {sec_nome}/{st_nome} | "
                f"Calc:{pag_calc}").classes("text-body2 text-grey-8")
            if cota_exc:
                ui.label("⚠ EXCEDENTE DE COTA").classes(
                    "text-caption text-orange-9 font-bold")
            if secr:
                pct, usado, cota = bd.percentual_consumo(secr, setor)
                ui.label(f"Cota: {usado}/{cota} ({pct}%)").classes("text-caption text-grey-7")
                _barra_cota(pct)

        with ui.row().classes("w-full gap-2 mt-2 flex-wrap"):
            sol = bd.obter_solicitacao(sid)
            if sol and sol.get("caminho_arquivo") and os.path.exists(sol["caminho_arquivo"]):
                ui.button("Baixar", icon="download",
                          on_click=lambda s=sol: _baixar(s)).props("flat dense")
                if status == "autorizado":
                    ui.button("Imprimir", icon="print",
                              on_click=lambda s=sid: _imprimir(s, usuario_logado, atualizar)).props(
                        "flat dense color=primary").tooltip("Enviar à impressora / abrir o PDF")
                    ui.button("Confirmar impressão", icon="done_all",
                              on_click=lambda s=sid: _confirmar_impressao(s, usuario_logado, atualizar)).props(
                        "flat dense color=green").tooltip("Marca o arquivo como efetivamente impresso")
                    ui.button("Recuar", icon="undo",
                              on_click=lambda s=sid: _recuar(s, usuario_logado, atualizar)).props(
                        "flat dense color=red")
                elif status in ("excedente_cota",):
                    ui.button("Recuar", icon="undo",
                              on_click=lambda s=sid: _recuar(s, usuario_logado, atualizar)).props(
                        "flat dense color=red")
                elif status == "impresso":
                    ui.label("Arquivo impresso em " + (dt_imp[:16] if dt_imp else "")).classes(
                        "text-caption text-grey-7")
                    ui.button("Recuar", icon="undo",
                              on_click=lambda s=sid: _recuar(s, usuario_logado, atualizar)).props(
                        "flat dense color=red")
            if status in ("aguardando_autorizacao", "excedente_cota"):
                ui.button("Autorizar", icon="check",
                          on_click=lambda s=sid: _autorizar(s, usuario_logado, atualizar)).props(
                    "flat dense color=green")
                ui.button("Recusar", icon="block",
                          on_click=lambda s=sid: _recusar(s, usuario_logado, atualizar)).props(
                    "flat dense color=red")


def _imprimir(sid, usuario, atualizar):
    # Abre o PDF / envia à impressora via JS (NÃO marca como impresso; isso é
    # feito pelo botão "Confirmar impressão" após a impressão efetiva).
    from mod_solicita_impressao import manipulador_bd as bd
    sol = bd.obter_solicitacao(sid)
    if not sol:
        ui.notify("Não encontrada", type="negative")
        return
    if sol.get("status") != "autorizado":
        ui.notify(f"Situação '{sol.get('status')}' não permite imprimir — é necessário autorizar antes.",
                  type="negative")
        return
    imp_a4 = bd.obter_config("impressora_padrao_nome", "")
    imp_a3 = bd.obter_config("impressora_padrao_a3_nome", "")
    impressora = imp_a3 if (sol.get("tamanho_papel") == "A3" and imp_a3) else imp_a4
    if impressora:
        ui.notify(f"Enviando para impressora: {impressora}", type="info")
    ui.run_javascript(
        f"if (window.printSolicitacao) window.printSolicitacao({sid}, '/solicita-impressao/pdf/{sid}');"
    )
    ui.notify("Impressão enviada. Confirme após concluir para marcar como impresso.",
              type="info", position="bottom")


def _confirmar_impressao(sid, usuario, atualizar):
    from mod_solicita_impressao import manipulador_bd as bd
    ok, msg = bd.imprimir_solicitacao(sid, usuario, ator=usuario)
    ui.notify(msg, type="positive" if ok else "negative")
    if atualizar:
        atualizar()


def _recuar(sid, usuario, atualizar):
    from mod_solicita_impressao import manipulador_bd as bd
    ok, msg = bd.recuar_solicitacao(sid, ator=usuario)
    ui.notify(msg, type="positive" if ok else "negative")
    if atualizar:
        atualizar()


# ================= ADMIN: SECRETARIAS =================

def _admin_secretarias(usuario_logado):
    from mod_solicita_impressao import manipulador_bd as bd
    wrap = ui.column().classes("w-full gap-2")

    with ui.card().classes("w-full"):
        ui.label("Nova Secretaria").classes("text-subtitle2")
        with ui.row().classes("w-full gap-2"):
            n_nome = ui.input("Nome*").props("outlined dense")
            n_sigla = ui.input("Sigla").props("outlined dense")
            n_cota = ui.number("Cota mensal (páginas)", value=0, min=0).props("outlined dense")

            def criar():
                ok, msg = bd.criar_secretaria(n_nome.value, n_sigla.value, n_cota.value,
                                              ator=usuario_logado)
                ui.notify(msg, type="positive" if ok else "negative")
                if ok:
                    n_nome.value = n_sigla.value = ""
                    n_cota.value = 0
                    atualizar()
            ui.button("Criar", on_click=criar).props("unelevated color=primary")

    def atualizar():
        wrap.clear()
        rows = bd.listar_secretarias()
        with wrap:
            if not rows:
                ui.label("Nenhuma secretaria.").classes("text-grey-6")
                return
            for sid, nome, sigla, cota, ativo in rows:
                with ui.card().classes("w-full"):
                    with ui.row().classes("w-full items-center justify-between"):
                        ui.label(f"{nome} ({sigla or '—'}) — cota: {cota} — "
                                 f"{'ativo' if ativo else 'inativo'}").classes("text-body2")
                        with ui.row().classes("gap-1"):
                            ui.button("Editar", icon="edit",
                                      on_click=lambda s=sid, n=nome, sg=sigla, c=cota:
                                      _editar_secretaria(s, n, sg, c, usuario_logado, atualizar)
                                      ).props("flat dense")
                            ui.button("Excluir", icon="delete",
                                      on_click=lambda s=sid: _excluir_secretaria(s, usuario_logado, atualizar)
                                      ).props("flat dense color=red")
    atualizar()


def _editar_secretaria(sid, nome, sigla, cota, usuario, atualizar):
    from mod_solicita_impressao import manipulador_bd as bd
    with ui.dialog() as dlg, ui.card().classes("w-96"):
        n = ui.input("Nome", value=nome).props("outlined dense")
        sg = ui.input("Sigla", value=sigla or "").props("outlined dense")
        c = ui.number("Cota mensal", value=cota, min=0).props("outlined dense")

        def salvar():
            ok, msg = bd.editar_secretaria(sid, n.value, sg.value, c.value, ator=usuario)
            ui.notify(msg, type="positive" if ok else "negative")
            dlg.close()
            atualizar()
        ui.button("Salvar", on_click=salvar).props("unelevated color=primary")
    dlg.open()


def _excluir_secretaria(sid, usuario, atualizar):
    from mod_solicita_impressao import manipulador_bd as bd
    ok, msg = bd.excluir_secretaria(sid, ator=usuario)
    ui.notify(msg, type="positive" if ok else "negative")
    atualizar()


# ================= ADMIN: SETORES =================

def _admin_setores(usuario_logado):
    from mod_solicita_impressao import manipulador_bd as bd
    wrap = ui.column().classes("w-full gap-2")

    with ui.card().classes("w-full"):
        ui.label("Novo Setor").classes("text-subtitle2")
        secr_opts = {s[0]: (s[2] or s[1]) for s in bd.listar_secretarias(ativo=1)}
        with ui.row().classes("w-full gap-2"):
            n_nome = ui.input("Nome*").props("outlined dense").classes("grow")
            n_secr = ui.select(secr_opts, label="Secretaria*").props("outlined dense").classes("grow")
            n_cota = ui.number("Cota mensal (0=usa secretaria)", value=0, min=0).props(
                "outlined dense")

            def criar():
                if not n_secr.value:
                    ui.notify("Selecione secretaria", type="warning"); return
                ok, msg = bd.criar_setor(n_nome.value, n_secr.value, n_cota.value,
                                         ator=usuario_logado)
                ui.notify(msg, type="positive" if ok else "negative")
                if ok:
                    n_nome.value = ""
                    n_cota.value = 0
                    atualizar()
            ui.button("Criar", on_click=criar).props("unelevated color=primary")

    def atualizar():
        wrap.clear()
        rows = bd.listar_setores()
        with wrap:
            if not rows:
                ui.label("Nenhum setor.").classes("text-grey-6")
                return
            for stid, nome, secr, cota, ativo in rows:
                sec_nome = ""
                s = bd.obter_secretaria(secr)
                if s:
                    sec_nome = s[2] or s[1]
                with ui.card().classes("w-full"):
                    with ui.row().classes("w-full items-center justify-between"):
                        ui.label(f"{nome} — {sec_nome} — cota: {cota} — "
                                 f"{'ativo' if ativo else 'inativo'}").classes("text-body2")
                        with ui.row().classes("gap-1"):
                            ui.button("Editar", icon="edit",
                                      on_click=lambda st=stid, nm=nome, sc=secr, c=cota:
                                      _editar_setor(st, nm, sc, c, usuario_logado, atualizar)
                                      ).props("flat dense")
                            ui.button("Excluir", icon="delete",
                                      on_click=lambda st=stid: _excluir_setor(st, usuario_logado, atualizar)
                                      ).props("flat dense color=red")
    atualizar()


def _editar_setor(stid, nome, secr, cota, usuario, atualizar):
    from mod_solicita_impressao import manipulador_bd as bd
    with ui.dialog() as dlg, ui.card().classes("w-96"):
        n = ui.input("Nome", value=nome).props("outlined dense")
        c = ui.number("Cota mensal", value=cota, min=0).props("outlined dense")

        def salvar():
            ok, msg = bd.editar_setor(stid, n.value, None, c.value, ator=usuario)
            ui.notify(msg, type="positive" if ok else "negative")
            dlg.close()
            atualizar()
        ui.button("Salvar", on_click=salvar).props("unelevated color=primary")
    dlg.open()


def _excluir_setor(stid, usuario, atualizar):
    from mod_solicita_impressao import manipulador_bd as bd
    ok, msg = bd.excluir_setor(stid, ator=usuario)
    ui.notify(msg, type="positive" if ok else "negative")
    atualizar()


# ================= ADMIN: RESPONSÁVEIS =================

def _admin_responsaveis(usuario_logado):
    from mod_solicita_impressao import manipulador_bd as bd
    wrap = ui.column().classes("w-full gap-2")

    with ui.card().classes("w-full"):
        ui.label("Novo Responsável por Autorização").classes("text-subtitle2")
        ui.label("Localize um usuário cadastrado e conceda a ele a permissão de "
                 "autorizar impressões (funciona mesmo para usuários 'comum').").classes(
            "text-caption text-grey-6")
        secr_opts = {s[0]: (s[2] or s[1]) for s in bd.listar_secretarias(ativo=1)}
        # Lista de usuários cadastrados (do módulo de gestão de usuários) para seleção
        try:
            from mod_gest_cad_usuario import manipulador_bd as _gest
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
            ui.button("Conceder permissão de autorizar impressão", icon="assignment_ind",
                      on_click=criar).props("unelevated color=primary")

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
                        ui.button("Excluir", icon="delete",
                                  on_click=lambda r=rid: _excluir_resp(r, usuario_logado, atualizar)
                                  ).props("flat dense color=red")
    atualizar()


def _excluir_resp(rid, usuario, atualizar):
    from mod_solicita_impressao import manipulador_bd as bd
    ok, msg = bd.excluir_responsavel(rid, ator=usuario)
    ui.notify(msg, type="positive" if ok else "negative")
    atualizar()


# ================= ADMIN: COTAS =================

def _admin_cotas(usuario_logado):
    from mod_solicita_impressao import manipulador_bd as bd
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
                        ui.button("Editar cota", icon="edit",
                                  on_click=lambda sc=sid, st=stid, c=cota:
                                  _editar_cota(sc, st, c, usuario_logado, atualizar)
                                  ).props("flat dense")
                        ui.button("Resetar", icon="restart_alt",
                                  on_click=lambda sc=sid, st=stid:
                                  _resetar_cota(sc, st, usuario_logado, atualizar)
                                  ).props("flat dense color=orange")
    atualizar()


def _editar_cota(secr, setor, cota_atual, usuario, atualizar):
    from mod_solicita_impressao import manipulador_bd as bd
    with ui.dialog() as dlg, ui.card().classes("w-80"):
        ui.label("Definir cota mensal (páginas)").classes("text-subtitle2")
        c = ui.number("Cota", value=cota_atual, min=0).props("outlined dense")

        def salvar():
            ok, msg = bd.definir_cota(secr, setor, c.value, ator=usuario)
            ui.notify(msg, type="positive" if ok else "negative")
            dlg.close()
            atualizar()
        ui.button("Salvar", on_click=salvar).props("unelevated color=primary")
    dlg.open()


def _resetar_cota(secr, setor, usuario, atualizar):
    ok, msg = bd.resetar_consumo(secr, setor, ator=usuario)
    ui.notify(msg, type="positive" if ok else "negative")
    atualizar()


# ================= ADMIN: CONFIGURAÇÕES =================

def _admin_configuracoes(usuario_logado):
    from mod_solicita_impressao import manipulador_bd as bd
    with ui.card().classes("w-full"):
        ui.label("Configurações do Módulo").classes("text-h6 font-bold")

        imp_a4 = ui.input("Impressora padrão (A4)",
                          value=bd.obter_config("impressora_padrao_nome", "")).props(
            "outlined dense").classes("w-full").tooltip(
            "Nome da impressora padrão. Se preenchido, botão 'Imprimir direto' envia ao cliente.")
        imp_a3 = ui.input("Impressora padrão (A3)",
                          value=bd.obter_config("impressora_padrao_a3_nome", "")).props(
            "outlined dense").classes("w-full")
        aviso = ui.textarea("Aviso de presença obrigatória",
                            value=bd.obter_config("aviso_presenca_obrigatoria", "")).props(
            "outlined dense").classes("w-full")
        max_mb = ui.number("Tamanho máx. upload (MB)",
                           value=int(bd.obter_config("max_arquivo_mb", "10")), min=1).props(
            "outlined dense")

        ui.separator().classes("my-2")
        ui.label("Retenção de arquivos e padrões do formulário").classes("text-subtitle2")
        tempo_rasc = ui.number(
            "Minutos para confirmar o envio (depois o arquivo é descartado)*",
            value=int(bd.obter_config("tempo_expira_rascunho_min", "4")),
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
                                  value=bd.obter_config("padrao_cor", "PB")).props(
                "outlined dense")
            p_pad_fv = ui.checkbox("Frente e verso por padrão",
                                   value=bd.obter_config("padrao_frente_verso", "0") == "1")
            p_pad_sulf = ui.checkbox("Papel sulfite por padrão",
                                     value=bd.obter_config("padrao_sulfite", "1") == "1")

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
        ui.label("Aparência — temas dos botões desta tela").classes("text-subtitle2")
        with ui.grid(columns=2).classes("w-full gap-3 max-sm:grid-cols-1"):
            inp_cor_botao = ui.color_input("Cor dos botões", value=t_cor_botao) \
                .props("outlined dense").classes("w-full")
            inp_cor_txt = ui.color_input("Cor do texto dos botões", value=t_cor_txt_botao) \
                .props("outlined dense").classes("w-full")
            inp_cor_fundo = ui.color_input("Cor de fundo da página (vazio = herda)",
                                           value=t_cor_fundo) \
                .props("outlined dense").classes("w-full")
            inp_cor_titulo = ui.color_input("Cor dos títulos", value=t_cor_titulo) \
                .props("outlined dense").classes("w-full")
        sel_tamanho = ui.select({0: "Pequeno", 1: "Médio", 2: "Grande"},
                                label="Tamanho dos botões",
                                value={"small": 0, "medium": 1, "large": 2}.get(
                                    t_btn_tamanho, 1)).props("outlined dense").classes("w-full")
        inp_txt_header = ui.input("Texto do cabeçalho", value=t_texto_header) \
            .props("outlined dense").classes("w-full")
        _tamanhos = {0: "small", 1: "medium", 2: "large"}

        def salvar():
            from mod_intranet.conexao_bd import set_config as _set_cfg_central
            _set_cfg_central("solicita_impressao_cor_botao", inp_cor_botao.value or "")
            _set_cfg_central("solicita_impressao_cor_texto_botao", inp_cor_txt.value or "")
            _set_cfg_central("solicita_impressao_cor_fundo", inp_cor_fundo.value or "")
            _set_cfg_central("solicita_impressao_cor_titulo", inp_cor_titulo.value or "")
            _set_cfg_central("solicita_impressao_btn_tamanho",
                             _tamanhos[sel_tamanho.value])
            _set_cfg_central("solicita_impressao_texto_header", inp_txt_header.value or "")
            bd.definir_config("impressora_padrao_nome", imp_a4.value or "")
            bd.definir_config("impressora_padrao_a3_nome", imp_a3.value or "")
            bd.definir_config("aviso_presenca_obrigatoria", aviso.value or "")
            bd.definir_config("max_arquivo_mb", int(max_mb.value or 10))
            bd.definir_config("tempo_expira_rascunho_min", int(tempo_rasc.value or 4))
            bd.definir_config("tempo_exclui_impresso_min", int(tempo_imp.value or 10))
            bd.definir_config("padrao_papel", p_pad_papel.value or "A4")
            bd.definir_config("padrao_cor", p_pad_cor.value or "PB")
            bd.definir_config("padrao_frente_verso", "1" if p_pad_fv.value else "0")
            bd.definir_config("padrao_sulfite", "1" if p_pad_sulf.value else "0")
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
            except Exception:
                pass
            ui.notify("Configurações salvas", type="positive")
        ui.button("Salvar configurações", icon="save", on_click=salvar).props(
            "unelevated").classes(_btn_cls()).style(_btn_style())
