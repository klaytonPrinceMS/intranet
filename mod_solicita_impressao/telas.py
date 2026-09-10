"""Print request module screen — NiceGUI.

Tela do módulo Solicitação de Impressão — NiceGUI.

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
from mod_intranet.bd_manipulador import audit_log
from mod_intranet.ui_comum import botao, botao_icone
from mod_intranet import observabilidade

MOD_DIR = os.path.dirname(os.path.abspath(__file__))


def _log():
    from mod_intranet import observabilidade
    return observabilidade.get_logger("solicita_impressao")


def mostrar_tela(usuario_logado: str, perfil: str):
    """Renders the print-request screen with permission-based tabs.

    Monta a tela: abas conforme o perfil — Nova Solicitação e Minhas
    Solicitações para todos; Autorização para responsáveis vinculados
    (mesmo sendo `comum`); Administração (Solicitações, Secretarias,
    Setores, Responsáveis, Cotas, Configurações) para admins do módulo."""
    from mod_intranet import autenticacao
    from mod_solicita_impressao import bd_manipulador as bd

    # Permissões
    eh_admin = (perfil == "administrador_geral"
                or autenticacao.eh_admin_do_modulo(usuario_logado, "solicita_impressao"))
    eh_responsavel = _eh_responsavel(usuario_logado)

    # ================= TEMA (cabeçalho) =================
    from mod_intranet.bd_conexao import get_config
    def _tema(chave, default):
        try:
            return (get_config(f"solicita_impressao_{chave}", default) or "").strip() or default
        except Exception as e:
            _log().warning(f"_tema: falha ao ler 'solicita_impressao_{chave}' | {e}")
            return default

    t_cor_botao = _tema("cor_botao", "#000000")
    t_cor_fundo = _tema("cor_fundo", "")
    t_cor_titulo = _tema("cor_titulo", "#212121")
    t_texto_header = _tema("texto_header",
                           "Solicite impressões, acompanhe pedidos e autorize demandas.")
    ui.colors(primary=t_cor_botao)

    container = ui.column().classes("w-full gap-4")

    with container:
        cabecalho("Solicitação de Impressão",
                   t_texto_header,
                   chave_modulo="solicita_impressao", cor_titulo=t_cor_titulo, cor_fundo=t_cor_fundo)

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

        if tabs:
            _icones = {"nova": "add_box", "minhas": "list_alt",
                       "autorizar": "approval"}
            with ui.row().classes("w-full items-center justify-between gap-4 flex-nowrap "
                                  "bg-white rounded-lg shadow-sm px-3 py-1"):
                with ui.tabs().props("dense inline-label").classes(
                        "min-w-0 overflow-x-auto") as tab_def:
                    for key, label in tabs:
                        ui.tab(key, label, icon=_icones.get(key))
            with ui.tab_panels(tab_def, value=tabs[0][0]).classes("w-full bg-transparent"):
                for key, label in tabs:
                    with ui.tab_panel(key):
                        if key == "nova":
                            _tela_nova(usuario_logado, eh_admin)
                        elif key == "minhas":
                            _tela_minhas(usuario_logado, eh_admin)
                        elif key == "autorizar":
                            _tela_autorizar(usuario_logado, eh_admin)


# ================= HELPERS =================

def _eh_responsavel(user_nome):
    """True if the user has any active authorization grant (any department/unit).

    Verdadeiro se o usuário tem algum vínculo ativo de autorização (qualquer secretaria/setor)."""
    from mod_solicita_impressao import bd_manipulador as bd
    from mod_intranet import autenticacao
    # Busca vinculos onde o usuário é responsável
    try:
        vinculos = bd.listar_responsaveis(ativo=1)
        return any(v[1] == user_nome for v in vinculos)
    except Exception:
        return False


def _status_chip(status):
    """Renders the colored status badge of a request.

    Renderiza o chip colorido de status de uma solicitação."""
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
    """Renders the quota usage bar WITHOUT the numeric value (green <50%,
    yellow 50–80%, orange 80–100%, red >100%).

    Barra de uso da cota SEM o numeral (para não expor o consumo entre
    secretarias): verde quando abaixo de 50%, amarelo de 50% a 80%, laranja
    acima de 80% (até 100%) e vermelho acima de 100%."""
    if percentual > 100:
        cor = "red"
    elif percentual > 80:
        cor = "orange"
    elif percentual >= 50:
        cor = "yellow"
    else:
        cor = "green"
    ui.linear_progress(value=min(percentual, 100) / 100.0, color=cor).classes("w-32")


# ================= NOVA SOLICITAÇÃO =================

def _tela_nova(usuario_logado, eh_admin):
    """New-request tab: multi-PDF drafts with countdown + form + submission.

    Upload automático ao selecionar (rascunhos com expiração visível e
    removíveis), valores padrão pré-selecionados (papel/cor/frente-verso/
    sulfite), secretaria→setor de crédito e envio: cada arquivo marcado vira
    uma solicitação separada com as opções do formulário."""
    from mod_solicita_impressao import bd_manipulador as bd

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
                                lambda e, r=r: r.__setitem__("sel", bool(e.value)))
                            ui.label(r["nome"]).classes("grow text-body2")
                            ui.label(f"{r['paginas']} pág.").classes("text-caption text-grey-6")
                            r["_exp_label"] = ui.label("").classes("text-caption text-orange-9")
                            botao_icone("delete", on_click=lambda r=r: _remover_um(r),
                                         cor="negative",
                                         chave_modulo="solicita_impressao").tooltip("Remover este arquivo")

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

            with ui.row().classes("w-full gap-2 flex-wrap items-end"):
                sel_secretaria = ui.select(
                    {s[0]: (s[2] or s[1]) for s in secretarias},
                    label="Secretaria (crédito)*").props("outlined dense").classes(
                    "flex-1 min-w-[25ch]")
                sel_setor = ui.select({}, label="Setor / Unidade (opcional)").props(
                    "outlined dense").classes("flex-1 min-w-[25ch]")
                qtd_copias = ui.number("Quantidade de cópias*", value=1, min=1, max=9999).props(
                    "outlined dense").classes("flex-1 min-w-[15ch]")
                papel = ui.select({"A4": "A4", "A3": "A3"}, label="Tamanho do papel*",
                                   value=bd.obter_config("padrao_papel", "A4")).props(
                    "outlined dense").classes("flex-1 min-w-[15ch]")
                cor = ui.select({"PB": "Preto e Branco", "Color": "Colorido"},
                                label="Cor*",
                                value=bd.obter_config("padrao_cor", "Color")).props(
                    "outlined dense").classes("flex-1 min-w-[15ch]")
                tipo_papel = ui.select(
                    {"sulfite": "Sulfite", "fotografico": "Fotográfico", "verge": "Vergê"},
                    label="Tipo de papel",
                    value=bd.obter_config("padrao_tipo_papel", "sulfite")).props(
                    "outlined dense").classes("flex-1 min-w-[15ch]")
                frente_verso = ui.checkbox(
                    "Frente e verso",
                    value=bd.obter_config("padrao_frente_verso", "0") == "1").classes(
                    "flex-none sm:flex-1 sm:min-w-[15ch] lg:pb-2")
                borda = ui.select({"curta": "Borda curta", "longa": "Borda longa"},
                                  label="Tipo de borda (se frente e verso)",
                                  value="longa").props("outlined dense").classes(
                    "flex-1 min-w-[15ch]")

                def ao_secretaria(e):
                    sid = e.value
                    setores = bd.listar_setores(secretaria_id=sid, ativo=1) if sid else []
                    sel_setor.options = {st[0]: st[1] for st in setores}
                    sel_setor.value = None
                    sel_setor.update()
                sel_secretaria.on_value_change(ao_secretaria)

                def ao_tipo_papel():
                    if tipo_papel.value not in (None, "sulfite"):
                        ui.notify("Atenção: papel fotográfico/vergê — o usuário deve "
                                  "trazer o próprio papel.", type="warning")
                tipo_papel.on_value_change(ao_tipo_papel)

                def ao_papel():
                    if (papel.value or "A4").upper() == "A3":
                        tipo_papel.value = "sulfite"
                        tipo_papel.enabled = False
                        tipo_papel.update()
                    else:
                        tipo_papel.enabled = True
                        if tipo_papel.value is None:
                            tipo_papel.value = bd.obter_config("padrao_tipo_papel", "sulfite")
                        tipo_papel.update()
                papel.on_value_change(ao_papel)
                ao_papel()

                def toggle_borda():
                    borda.enabled = frente_verso.value
                frente_verso.on_value_change(toggle_borda)
                borda.enabled = frente_verso.value

            obs = ui.textarea("Observações / orientações para o solicitante").props(
                "outlined dense").classes("w-full")

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
                rids = [r["rid"] for r in alvos]
                ok, msg, grupo_id = bd.confirmar_lote(
                    usuario_logado, rids, int(qtd_copias.value or 1), papel.value, cor.value,
                    frente_verso.value, borda.value if frente_verso.value else None,
                    (tipo_papel.value or "sulfite") == "sulfite",
                    obs.value, sel_secretaria.value, sel_setor.value,
                    ator=usuario_logado, tipo_papel=tipo_papel.value or "sulfite")
                if ok:
                    for r in alvos:
                        if r in rascunhos:
                            rascunhos.remove(r)
                    rebuild()
                    ui.notify(msg, type="positive")
                    ui.timer(0.1, lambda: ui.navigate.reload(), once=True)
                else:
                    ui.notify(msg, type="negative")

            with ui.row().classes("w-full justify-center gap-2"):
                botao("Remover selecionados", icone="delete",
                      on_click=_remover_selecionados, variante="solido",
                      chave_modulo="solicita_impressao", extra_classes="w-56")
                btn_enviar = botao("Enviar solicitação", icone="send", on_click=enviar,
                                   variante="solido", chave_modulo="solicita_impressao",
                                   extra_classes="w-56") \
                    .props('data-testid=solicita-enviar')

        alertas = bd.obter_config("alertas_nova_solicitacao", "")
        for alerta in [a.strip() for a in (alertas or "").split("\n") if a.strip()]:
            ui.label("⚠ " + alerta).classes(
                "text-white font-bold bg-orange-9 rounded p-3 w-full")


# ================= MINHAS SOLICITAÇÕES =================

def _tela_minhas(usuario_logado, eh_admin):
    """My-requests tab: the user's own PEDIDOS (one card per submission/group),
    tracking status (pending authorization / authorized / ready to accompany print).

    Aba "Minhas solicitações": lista os pedidos do usuário (um card por envio/
    grupo) com o status de acompanhamento (aguardando autorização / autorizado /
    pronto para acompanhar a impressão), com pesquisa por texto e remoção da
    lista dos pedidos cancelados."""
    from mod_solicita_impressao import bd_manipulador as bd
    wrap = ui.column().classes("w-full gap-2")

    with ui.card().classes("w-full"):
        with ui.row().classes("w-full items-center gap-2 flex-wrap"):
            inp_busca = ui.input("Buscar", placeholder="solicitante, observação, arquivo…").props(
                "outlined dense clearable").classes("grow") \
                .props('data-testid=solicita-busca')
            botao("Filtrar", icone="search", on_click=lambda: atualizar(), variante="solido",
                  chave_modulo="solicita_impressao")

    def atualizar():
        wrap.clear()
        rows = bd.listar_pedidos(usuario=usuario_logado, limite=200,
                                 busca=inp_busca.value or None)
        rows = [r for r in rows if r[12] != "cancelado"]
        with wrap:
            if not rows:
                ui.label("Nenhum pedido ainda.").classes("text-grey-6")
                return
            for g in rows:
                _card_grupo(g, usuario_logado, eh_admin, pode_cancelar=True,
                            permite_selecao=True, atualizar=atualizar)
    atualizar()


# ================= AUTORIZAÇÃO =================

def _tela_autorizar(usuario_logado, eh_admin):
    """Authorization tab "Solicitação pendente": the authorizer sees only pedidos
    of the secretarias/setores they authorize, split into "aguardando autorização"
    and "já autorizados", with search (date, who requested, content).

    Aba "Solicitação pendente" do autorizador: mostra apenas os pedidos das
    secretarias/setores que ele autoriza, divididos em "AGUARDANDO AUTORIZAÇÃO"
    e "JÁ AUTORIZADOS", com busca por texto e data."""
    from mod_solicita_impressao import bd_manipulador as bd

    with ui.row().classes("w-full items-center gap-2 flex-wrap pt-2"):
        inp_busca = ui.input("Buscar", placeholder="solicitante, observação, arquivo…").props(
            "outlined dense clearable").classes("grow")
        inp_dt_ini = ui.input("Data inicial").props("outlined dense type=date").classes("w-40")
        inp_dt_fim = ui.input("Data final").props("outlined dense type=date").classes("w-40")
        botao("Filtrar", icone="search", on_click=lambda: atualizar(), variante="solido",
              chave_modulo="solicita_impressao")

    wrap = ui.column().classes("w-full gap-2")

    def atualizar():
        busca = inp_busca.value or None
        di = inp_dt_ini.value or None
        df = inp_dt_fim.value or None
        wrap.clear()
        pend = bd.listar_pedidos_responsavel(
            usuario_logado, status="aguardando_autorizacao", busca=busca,
            data_inicio=di, data_fim=df)
        exced = bd.listar_pedidos_responsavel(
            usuario_logado, status="excedente_cota", busca=busca, data_inicio=di, data_fim=df)
        autorizados = bd.listar_pedidos_responsavel(
            usuario_logado, status="autorizado", busca=busca, data_inicio=di, data_fim=df)
        aguardando = pend + [e for e in exced if e[0] not in [p[0] for p in pend]]
        with wrap:
            ui.label(f"AGUARDANDO AUTORIZAÇÃO ({len(aguardando)})").classes(
                "text-subtitle2 text-amber-8")
            if not aguardando:
                ui.label("Nenhum pedido aguardando autorização para seus vínculos.").classes(
                    "text-grey-6")
            for g in aguardando:
                _card_grupo(g, usuario_logado, eh_admin, pode_autorizar=True,
                            atualizar=atualizar)
            ui.separator().classes("my-2")
            ui.label(f"JÁ AUTORIZADOS ({len(autorizados)})").classes(
                "text-subtitle2 text-green-8")
            if not autorizados:
                ui.label("Nenhum pedido autorizado para seus vínculos.").classes("text-grey-6")
            for g in autorizados:
                _card_grupo(g, usuario_logado, eh_admin, atualizar=atualizar)
    atualizar()


# ================= CARD DE SOLICITAÇÃO =================

def _card_grupo(g, usuario_logado, eh_admin, pode_cancelar=False,
                pode_autorizar=False, permite_selecao=False, atualizar=None):
    """Renders one PEDIDO card (all files of the submission) with actions.

    O pedido é o grupo: um card mostra todos os arquivos do envio com o mesmo
    status. Ações dependem do perfil/estado (autorizar/recusar/baixar/imprimir/
    confirmar/recuar/cancelar). Com `permite_selecao=True`, cada arquivo ganha
    um checkbox e os botões "Baixar selecionados" (avulso) e "Baixar
    selecionados (zip)" ficam disponíveis na linha de ações."""
    from mod_solicita_impressao import bd_manipulador as bd
    (grupo_id, user, copias, papel, cor, fv, borda, sulf, tipo_papel, obs, secr, setor,
     status, cota_exc, req_auth, aut_por, dt_aut, motivo, imp_por, dt_imp,
     dt_cri, sec_nome, sec_sig, st_nome, num_arq, pag_calc_total, pag_arq_total) = g
    arquivos = bd.listar_arquivos_grupo(grupo_id)
    selecionados = {}   # fid -> bool

    def _selecionados_fisicos():
        alvos = []
        for fid, arq_serv, arq_orig, pag_arq, pag_calc, hash_arq, caminho in arquivos:
            if selecionados.get(fid) and caminho and os.path.exists(caminho):
                alvos.append((fid, caminho, arq_serv or arq_orig))
        return alvos

    def baixar_selecionados():
        alvos = _selecionados_fisicos()
        if not alvos:
            ui.notify("Selecione ao menos um arquivo para baixar", type="warning")
            return
        for fid, caminho, nome in alvos:
            _baixar_arquivo(caminho, nome)

    def baixar_selecionados_zip():
        alvos = _selecionados_fisicos()
        if not alvos:
            ui.notify("Selecione ao menos um arquivo para baixar", type="warning")
            return
        import zipfile
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
            with zipfile.ZipFile(tmp.name, "w", zipfile.ZIP_DEFLATED) as zf:
                for fid, caminho, nome in alvos:
                    zf.write(caminho, arcname=nome)
            ui.download(tmp.name, filename=f"pedido_{grupo_id}.zip")

    with ui.card().classes("w-full shadow-md border-l-8").style(
            "border-left-color:#000000"):
        with ui.row().classes("w-full items-start justify-between flex-wrap"):
            with ui.column().classes("gap-0 grow"):
                ui.label(f"Pedido #{grupo_id} — {num_arq} arquivo(s)").classes(
                    "text-h6 font-bold text-grey-9")
                ui.label(f"por {user} • {dt_cri[:16] if dt_cri else ''}").classes(
                    "text-caption text-grey-6")
            _status_chip(status)

        with ui.column().classes("w-full mt-1 gap-1"):
            ui.label(
                f"Secretaria: {sec_nome or '?'} | Setor: {st_nome or '—'}"
            ).classes("text-body2 text-grey-9 font-bold")
            ui.label(
                f"Cópias: {copias} | Papel: {papel} | Cor: {cor} | "
                f"Frente/verso: {'Sim (' + (borda or '—') + ')' if fv else 'Não'} | "
                f"Tipo: {tipo_papel or 'sulfite'}"
                + (" (trazer)" if (tipo_papel or 'sulfite') != 'sulfite' else "")
            ).classes("text-body2 text-grey-8")
            if obs:
                ui.label(f"Obs: {obs}").classes("text-caption text-grey-7")
            if motivo:
                ui.label(f"Motivo: {motivo}").classes("text-caption text-red-8")
            if cota_exc:
                ui.label("⚠ EXCEDENTE DE COTA — sujeito à autorização").classes(
                    "text-caption text-orange-9 font-bold")

            with ui.row().classes("w-full items-center gap-2 flex-wrap"):
                ui.label(f"Páginas: {pag_arq_total} (contab.: {pag_calc_total})").classes(
                    "text-body2 text-grey-8")
                if secr:
                    pct, usado, cota = bd.percentual_consumo(secr, setor)
                    _barra_cota(pct)

            # Lista de arquivos do pedido
            with ui.column().classes("w-full gap-1 mt-1"):
                for fid, arq_serv, arq_orig, pag_arq, pag_calc, hash_arq, caminho in arquivos:
                    with ui.row().classes("w-full items-center gap-2"):
                        if permite_selecao:
                            selecionados[fid] = False
                            ui.checkbox(value=False).on_value_change(
                                lambda e, f=fid: selecionados.__setitem__(f, bool(e.value)))
                        ui.label(f"📄 {arq_orig or arq_serv} ({pag_arq} pág.)").classes(
                            "grow text-caption text-grey-8")
                        if caminho and os.path.exists(caminho):
                            botao("Baixar", icone="download",
                                  on_click=lambda c=caminho, a=arq_serv: _baixar_arquivo(c, a),
                                  variante="texto", compacto=True,
                                  chave_modulo="solicita_impressao")

        with ui.row().classes("w-full gap-2 mt-2 flex-wrap"):
            if permite_selecao:
                botao("Baixar selecionados", icone="file_download",
                      on_click=baixar_selecionados, variante="solido",
                      chave_modulo="solicita_impressao")
                botao("Baixar selecionados (zip)", icone="folder_zip",
                      on_click=baixar_selecionados_zip, variante="solido",
                      chave_modulo="solicita_impressao")
            if pode_cancelar and status in ("pendente", "aguardando_autorizacao",
                                            "excedente_cota", "recusado"):
                botao("Cancelar", icone="cancel",
                          on_click=lambda gr=grupo_id: _cancelar_grupo(gr, usuario_logado, atualizar),
                          variante="texto", compacto=True, cor="negative",
                          chave_modulo="solicita_impressao")
            if pode_cancelar and status == "recusado":
                botao("Reenviar", icone="replay",
                          on_click=lambda gr=grupo_id: _reenviar_grupo(gr, usuario_logado, atualizar),
                          variante="texto", compacto=True, cor="primary",
                          chave_modulo="solicita_impressao")
            if pode_autorizar and status in ("aguardando_autorizacao", "excedente_cota",
                                             "pendente"):
                botao("Autorizar", icone="check",
                          on_click=lambda gr=grupo_id: _autorizar_grupo(gr, usuario_logado, atualizar),
                          variante="texto", compacto=True, cor="green-8",
                          chave_modulo="solicita_impressao")
                botao("Recusar", icone="block",
                          on_click=lambda gr=grupo_id: _recusar_grupo(gr, usuario_logado, atualizar),
                          variante="perigo", compacto=True,
                          chave_modulo="solicita_impressao")


def _baixar_arquivo(caminho, nome):
    """Downloads one file of a pedido (with watermark applied at download time).

    Baixa um arquivo de um pedido (com marca d'água aplicada no momento do download)."""
    from nicegui import ui as _ui
    if caminho and os.path.exists(caminho):
        _ui.download(caminho, filename=nome or "documento.pdf")


def _baixar(sol):
    """Downloads the request PDF (with watermark applied at download time).

    Baixa o PDF da solicitação (com marca d'água aplicada no momento do download)."""
    from nicegui import ui as _ui
    caminho = sol.get("caminho_arquivo")
    if caminho and os.path.exists(caminho):
        _ui.download(caminho, filename=sol.get("arquivo_servidor") or "documento.pdf")


def _cancelar_grupo(grupo_id, usuario, atualizar):
    """Cancels the user's own pending PEDIDO (all files removed from server).

    Cancela o pedido pendente do próprio usuário (todos os arquivos removidos do servidor)."""
    from mod_solicita_impressao import bd_manipulador as bd
    ok, msg = bd.cancelar_grupo(grupo_id, usuario, ator=usuario)
    ui.notify(msg, type="positive" if ok else "negative")
    if atualizar:
        atualizar()


def _reenviar_grupo(grupo_id, usuario, atualizar):
    """Re-opens a refused PEDIDO for a new authorization round (own request).

    Reabre um pedido recusado para nova rodada de autorização (pedido do próprio usuário)."""
    from mod_solicita_impressao import bd_manipulador as bd
    ok, msg = bd.reenviar_grupo(grupo_id, usuario, ator=usuario)
    ui.notify(msg, type="positive" if ok else "negative")
    if atualizar:
        atualizar()


def _autorizar_grupo(grupo_id, usuario, atualizar):
    """Authorizes a PEDIDO (all files) — responsável or module admin.

    Autoriza um pedido (todos os arquivos) — responsável ou admin do módulo."""
    from mod_solicita_impressao import bd_manipulador as bd
    ok, msg = bd.autorizar_grupo(grupo_id, usuario)
    ui.notify(msg, type="positive" if ok else "negative")
    if atualizar:
        atualizar()


def _recusar_grupo(grupo_id, usuario, atualizar):
    """Refuses a PEDIDO (all files) with a mandatory reason (dialog).

    Recusa um pedido (todos os arquivos) com motivo obrigatório (diálogo)."""
    from mod_solicita_impressao import bd_manipulador as bd
    with ui.dialog() as dlg, ui.card().classes("w-96"):
        ui.label("Motivo da recusa*").classes("text-subtitle2")
        motivo = ui.textarea("Motivo").props("outlined dense").classes("w-full")

        def confirmar():
            if not (motivo.value or "").strip():
                ui.notify("Informe o motivo", type="warning")
                return
            ok, msg = bd.recusar_grupo(grupo_id, usuario, motivo.value.strip())
            ui.notify(msg, type="positive" if ok else "negative")
            dlg.close()
            if atualizar:
                atualizar()
        botao("Confirmar recusa", on_click=confirmar, variante="primario",
                       cor="negative", chave_modulo="solicita_impressao")
    dlg.open()


# ================= ADMINISTRAÇÃO =================

def _tela_admin(usuario_logado, eh_admin):
    """Administration tab with 7 sub-tabs (requests + master data + report + config).

    Aba de Administração com 7 sub-abas (solicitações + cadastros + relatórios + configurações)."""
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
    """Admin sub-tab: PEDIDOS grouped by secretaria -> setor, with status tabs
    and search. Once printed the pedido leaves the active management.

    Sub-aba de administração: lista os pedidos agrupados por secretaria→setor,
    com abas de status (Ativos/Impressos/Recusados/Todos) e busca. Ao ser
    impresso, o pedido sai da gestão ativa do admin."""
    from mod_solicita_impressao import bd_manipulador as bd
    ABAS = [("ativos", "Ativos"), ("impressos", "Impressos"),
            ("recusados", "Recusados"), ("todos", "Todos")]
    filtro_por_aba = {"ativos": None, "impressos": "impresso",
                      "recusados": "recusado", "todos": None}
    excluir_aba = {"ativos": ("impresso", "recusado", "cancelado"),
                   "impressos": (), "recusados": (), "todos": ()}

    with ui.tabs().classes("w-full") as stat:
        for key, lab in ABAS:
            ui.tab(key, lab)
    wrap = ui.column().classes("w-full gap-2 mt-1")

    with ui.card().classes("w-full"):
        with ui.row().classes("w-full items-center gap-2 flex-wrap"):
            inp_busca = ui.input("Buscar", placeholder="solicitante, observação, arquivo…").props(
                "outlined dense clearable").classes("grow")
            inp_secretaria = ui.select(
                {s[0]: (s[2] or s[1]) for s in bd.listar_secretarias()},
                label="Secretaria").props("outlined dense clearable").classes("w-48")
            inp_setor = ui.select({}, label="Setor").props(
                "outlined dense clearable").classes("w-48")
            inp_dt_ini = ui.input("Data inicial").props(
                "outlined dense type=date").classes("w-40")
            inp_dt_fim = ui.input("Data final").props(
                "outlined dense type=date").classes("w-40")
            botao("Buscar", icone="search", on_click=lambda: atualizar(), variante="solido",
                  chave_modulo="solicita_impressao")

        def ao_secretaria(e):
            sid = e.value
            sts = bd.listar_setores(secretaria_id=sid) if sid else []
            inp_setor.options = {st[0]: st[1] for st in sts}
            inp_setor.value = None
            inp_setor.update()
        inp_secretaria.on_value_change(ao_secretaria)

    estado = {"aba": "ativos"}

    def atualizar():
        wrap.clear()
        status = filtro_por_aba.get(estado["aba"])
        rows = bd.listar_pedidos(
            status=status,
            secretaria_id=inp_secretaria.value,
            setor_id=inp_setor.value,
            busca=inp_busca.value or None,
            data_inicio=inp_dt_ini.value or None,
            data_fim=inp_dt_fim.value or None,
            limite=400)
        excl = excluir_aba.get(estado["aba"])
        if excl:
            rows = [r for r in rows if r[12] not in excl]
        with wrap:
            if not rows:
                ui.label("Nenhum pedido para estes filtros.").classes("text-grey-6")
                return
            ui.label(f"{len(rows)} pedido(s)").classes("text-caption text-grey-6")
            rows.sort(key=lambda r: ((r[21] or ''), (r[23] or '')))
            sec_atual = None
            for g in rows:
                sec_chave = (g[21] or '?')
                if sec_chave != sec_atual:
                    sec_atual = sec_chave
                    ui.label(f"\u25b8 {sec_chave}").classes(
                        "text-subtitle1 font-bold text-grey-8 mt-1")
                _card_admin_grupo(g, usuario_logado, atualizar)
    atualizar()

    def ao_aba(e):
        estado["aba"] = e.value
        atualizar()
    stat.on_value_change(ao_aba)


def _card_admin_grupo(g, usuario_logado, atualizar):
    """Renders the admin variant of a PEDIDO card (full action set).

    For authorized/pending-authorizable pedidos: Imprimir, Baixar (each file),
    Confirmar impressão and Recusar (motivo). When marked printed, the files
    are removed from the server and the pedido leaves the active management."""
    from mod_solicita_impressao import bd_manipulador as bd
    (grupo_id, user, copias, papel, cor, fv, borda, sulf, tipo_papel, obs, secr, setor,
     status, cota_exc, req_auth, aut_por, dt_aut, motivo, imp_por, dt_imp,
     dt_cri, sec_nome, sec_sig, st_nome, num_arq, pag_calc_total, pag_arq_total) = g
    arquivos = bd.listar_arquivos_grupo(grupo_id)

    with ui.card().classes("w-full shadow-md border-l-8").style(
            "border-left-color:#000000"):
        with ui.row().classes("w-full items-start justify-between flex-wrap"):
            with ui.column().classes("gap-0 grow"):
                ui.label(f"Pedido #{grupo_id} — {num_arq} arquivo(s)").classes(
                    "text-h6 font-bold text-grey-9")
                ui.label(f"por {user} • {dt_cri[:16] if dt_cri else ''}").classes(
                    "text-caption text-grey-6")
            _status_chip(status)

        with ui.column().classes("w-full mt-1 gap-1"):
            ui.label(
                f"Secretaria: {sec_nome or '?'} | Setor: {st_nome or '—'}"
            ).classes("text-body2 text-grey-9 font-bold")
            ui.label(
                f"Cópias: {copias} | Papel: {papel} | Cor: {cor} | "
                f"Frente/verso: {'Sim (' + (borda or '—') + ')' if fv else 'Não'} | "
                f"Tipo: {tipo_papel or 'sulfite'}"
                + (" (trazer)" if (tipo_papel or 'sulfite') != 'sulfite' else "")
            ).classes("text-body2 text-grey-8")
            if obs:
                ui.label(f"Obs: {obs}").classes("text-caption text-grey-7")
            if motivo:
                ui.label(f"Motivo: {motivo}").classes("text-caption text-red-8")
            if cota_exc:
                ui.label("⚠ EXCEDENTE DE COTA").classes("text-caption text-orange-9 font-bold")

            with ui.row().classes("w-full items-center gap-2 flex-wrap"):
                ui.label(f"Páginas: {pag_arq_total} (contab.: {pag_calc_total})").classes(
                    "text-body2 text-grey-8")
                if secr:
                    pct, usado, cota = bd.percentual_consumo(secr, setor)
                    _barra_cota(pct)
            if aut_por:
                ui.label(f"Autorizado por {aut_por} • {dt_aut[:16] if dt_aut else ''}").classes(
                    "text-caption text-green-8")
            if imp_por:
                ui.label(f"Impresso por {imp_por} • {dt_imp[:16] if dt_imp else ''}").classes(
                    "text-caption text-green-8")

            for fid, arq_serv, arq_orig, pag_arq, pag_calc, hash_arq, caminho in arquivos:
                with ui.row().classes("w-full items-center gap-2"):
                    ui.label(f"\U0001F4C4 {arq_orig or arq_serv} ({pag_arq} pág.)").classes(
                        "grow text-caption text-grey-8")
                    if caminho and os.path.exists(caminho):
                        botao("Baixar", icone="download",
                              on_click=lambda c=caminho, a=arq_serv: _baixar_arquivo(c, a),
                              variante="texto", compacto=True,
                              chave_modulo="solicita_impressao")
                    else:
                        ui.label("(arquivo já removido)").classes(
                            "text-caption text-grey-5 italic")

        with ui.row().classes("w-full gap-2 mt-2 flex-wrap"):
            if status in ("pendente", "aguardando_autorizacao", "excedente_cota"):
                botao("Autorizar", icone="check",
                      on_click=lambda gr=grupo_id: _autorizar_grupo(gr, usuario_logado, atualizar),
                      variante="texto", compacto=True, cor="green-8",
                      chave_modulo="solicita_impressao")
                botao("Recusar", icone="block",
                      on_click=lambda gr=grupo_id: _recusar_grupo(gr, usuario_logado, atualizar),
                      variante="perigo", compacto=True,
                      chave_modulo="solicita_impressao")
            elif status == "autorizado":
                botao("Imprimir", icone="print",
                      on_click=lambda gr=grupo_id: _imprimir_grupo(gr, usuario_logado, atualizar),
                      variante="texto", compacto=True,
                      chave_modulo="solicita_impressao").tooltip("Enviar à impressora / abrir o PDF")
                botao("Confirmar impressão", icone="done_all",
                      on_click=lambda gr=grupo_id: _confirmar_impressao_grupo(gr, usuario_logado, atualizar),
                      variante="texto", compacto=True, cor="green-8",
                      chave_modulo="solicita_impressao").tooltip("Marca impresso e apaga arquivos do servidor")
                botao("Recusar", icone="block",
                      on_click=lambda gr=grupo_id: _recusar_grupo(gr, usuario_logado, atualizar),
                      variante="perigo", compacto=True,
                      chave_modulo="solicita_impressao")
                botao("Recuar", icone="undo",
                      on_click=lambda gr=grupo_id: _recuar_grupo(gr, usuario_logado, atualizar),
                      variante="texto", compacto=True, cor="negative",
                      chave_modulo="solicita_impressao")
            elif status == "impresso":
                ui.label("Arquivos impressos em " + (dt_imp[:16] if dt_imp else "") +
                         " e removidos do servidor.").classes("text-caption text-grey-7")
                botao("Recuar", icone="undo",
                      on_click=lambda gr=grupo_id: _recuar_grupo(gr, usuario_logado, atualizar),
                      variante="texto", compacto=True, cor="negative",
                      chave_modulo="solicita_impressao")


def _imprimir_grupo(grupo_id, usuario, atualizar):
    """Opens the printer picker for a PEDIDO, then sends each file to print.

    Mantém o JS nativo (diálogo do SO). NÃO marca como impresso — o desconto
    de cota e a remoção dos arquivos ocorrem em 'Confirmar impressão'."""
    from mod_solicita_impressao import bd_manipulador as bd
    arquivos = bd.listar_arquivos_grupo(grupo_id)
    if not arquivos:
        ui.notify("Pedido não encontrado", type="negative")
        return
    status_atual = None
    for p in bd.listar_pedidos(limite=1000):
        if p[0] == grupo_id:
            status_atual = p[12]
            break
    if status_atual not in ("autorizado", "pendente", "excedente_cota"):
        ui.notify("Situação não permite imprimir — é necessário autorizar antes.",
                  type="negative")
        return
    existentes = [a for a in arquivos if a[6] and os.path.exists(a[6])]
    if not existentes:
        ui.notify("Arquivos já foram removidos do servidor.", type="warning")
        return
    impressoras = bd.listar_impressoras(ativo=1)
    if not impressoras:
        ui.notify("Nenhuma impressora cadastrada. Cadastre em Administração → Configurações.",
                  type="warning")
        return
    padrao_nome = bd.obter_config("impressora_padrao_nome", "")
    opcoes = {i[0]: f"{i[1]}  —  {i[2]} · {i[3]} · driver {i[6]}" for i in impressoras}
    valor_padrao = next((i[0] for i in impressoras if i[1] == padrao_nome), None)

    def disparar():
        escolhida = bd.obter_impressora(sel_imp.value)
        if not escolhida:
            ui.notify("Selecione uma impressora", type="warning")
            return
        dlg.close()
        ui.notify(f"Enviando para impressora: {escolhida[1]}", type="info")
        # Exceção intencional de "sem JS direto": impressão via diálogo nativo do SO
        # (`window.imprimirPdf` injetado por /solicita-impressao/src/impressao.js).
        for a in existentes:
            ui.run_javascript(
                f"if (window.imprimirPdf) window.imprimirPdf('/solicita-impressao/pdf/{a[0]}',"
                f" {escolhida[1]!r});")
        ui.notify("Impressão enviada. Confirme após concluir para marcar como impresso.",
                  type="info", position="bottom")

    with ui.dialog() as dlg, ui.card().classes("w-[520px]"):
        ui.label(f"Impressão — Pedido #{grupo_id} ({len(existentes)} arquivo(s))").classes(
            "text-h6 font-bold")
        sel_imp = ui.select(opcoes, label="Impressora*", value=valor_padrao).props(
            "outlined dense clearable").classes("w-full")
        ui.label("Dica: o navegador usa o diálogo de impressão do sistema.").classes(
            "text-caption text-grey-6")
        with ui.row().classes("w-full justify-end gap-2 mt-2"):
            botao("Cancelar", on_click=dlg.close, variante="texto",
                  chave_modulo="solicita_impressao")
            botao("Imprimir", icone="print", on_click=disparar, variante="solido",
                  chave_modulo="solicita_impressao")
    dlg.open()


def _confirmar_impressao_grupo(grupo_id, usuario, atualizar):
    """Confirms the effective print of a PEDIDO (status=impresso + quota
    deduction + immediate removal of files from the server)."""
    from mod_solicita_impressao import bd_manipulador as bd
    ok, msg = bd.imprimir_grupo(grupo_id, usuario, ator=usuario)
    ui.notify(msg, type="positive" if ok else "negative")
    if atualizar:
        atualizar()


def _recuar_grupo(grupo_id, usuario, atualizar):
    """Recalls a PEDIDO (status=cancelado, files removed).

    Recua um pedido (status=cancelado, arquivos removidos)."""
    from mod_solicita_impressao import bd_manipulador as bd
    ok, msg = bd.recuar_grupo(grupo_id, ator=usuario)
    ui.notify(msg, type="positive" if ok else "negative")
    if atualizar:
        atualizar()


def _imprimir(sid, usuario, atualizar):
    """Opens the printer picker for an authorized request, then sends to print.

    Abre um diálogo com as impressoras cadastradas (tb_impressoras); ao
    confirmar, dispara `window.imprimirPdf` via JS (diálogo nativo do SO).
    NÃO marca como impresso — o desconto de cota é feito no botão
    'Confirmar impressão' após a impressão efetiva."""
    from mod_solicita_impressao import bd_manipulador as bd
    sol = bd.obter_solicitacao(sid)
    if not sol:
        ui.notify("Não encontrada", type="negative")
        return
    if sol.get("status") != "autorizado":
        ui.notify(f"Situação '{sol.get('status')}' não permite imprimir — é necessário autorizar antes.",
                  type="negative")
        return

    impressoras = bd.listar_impressoras(ativo=1)
    if not impressoras:
        ui.notify("Nenhuma impressora cadastrada. Cadastre em Administração → Configurações.",
                  type="warning")
        return

    # Impressora padrão sugerida (A4/A3) conforme o papel da solicitação
    papel_sol = (sol.get("tamanho_papel") or "A4").upper()
    padrao_nome = (bd.obter_config("impressora_padrao_a3_nome" if papel_sol == "A3"
                                   else "impressora_padrao_nome", ""))
    opcoes = {i[0]: f"{i[1]}  —  {i[2]} · {i[3]} · {'frente/verso' if i[4] else 'somente frente'} · driver {i[6]}"
              for i in impressoras}
    valor_padrao = next((i[0] for i in impressoras if i[1] == padrao_nome), None)

    def disparar():
        escolhida = bd.obter_impressora(sel_imp.value)
        if not escolhida:
            ui.notify("Selecione uma impressora", type="warning")
            return
        dlg.close()
        ui.notify(f"Enviando para impressora: {escolhida[1]}", type="info")
        # Exceção intencional de "sem JS direto": impressão via diálogo nativo do SO
        # (`window.imprimirPdf` injetado por /solicita-impressao/src/impressao.js).
        ui.run_javascript(
            f"if (window.imprimirPdf) window.imprimirPdf('/solicita-impressao/pdf/{sid}',"
            f" {escolhida[1]!r});"
        )
        ui.notify("Impressão enviada. Confirme após concluir para marcar como impresso.",
                  type="info", position="bottom")

    with ui.dialog() as dlg, ui.card().classes("w-[520px]"):
        ui.label(f"Impressão — Solicitação #{sid}").classes("text-h6 font-bold")
        ui.label(f"Papel: {sol.get('tamanho_papel')} · Cor: {sol.get('cor')} · "
                 f"Cópias: {sol.get('qtd_copias')} · Páginas: {sol.get('qtd_paginas_arquivo')}"
                 ).classes("text-caption text-grey-7")
        sel_imp = ui.select(opcoes, label="Impressora*", value=valor_padrao).props(
            "outlined dense clearable").classes("w-full").tooltip(
            "O diálogo nativo do SO decide a fila; a escolha aqui registra o destino.")
        ui.label("Dica: o navegador usa o diálogo de impressão do sistema. "
                 "O nome acima é apenas informativo.").classes("text-caption text-grey-6")
        with ui.row().classes("w-full justify-end gap-2 mt-2"):
            botao("Cancelar", on_click=dlg.close, variante="texto",
                  chave_modulo="solicita_impressao")
            botao("Imprimir", icone="print", on_click=disparar, variante="solido",
                  chave_modulo="solicita_impressao")
    dlg.open()


def _confirmar_impressao(sid, usuario, atualizar):
    """Confirms the effective print (status=impresso + quota deduction).

    Confirma a impressão efetiva (status=impresso + desconto de cota)."""
    from mod_solicita_impressao import bd_manipulador as bd
    ok, msg = bd.imprimir_solicitacao(sid, usuario, ator=usuario)
    ui.notify(msg, type="positive" if ok else "negative")
    if atualizar:
        atualizar()


def _recuar(sid, usuario, atualizar):
    """Recalls an authorized/printed request (status=cancelado, file removed).

    Recua uma solicitação autorizada/impressa (status=cancelado, arquivo removido)."""
    from mod_solicita_impressao import bd_manipulador as bd
    ok, msg = bd.recuar_solicitacao(sid, ator=usuario)
    ui.notify(msg, type="positive" if ok else "negative")
    if atualizar:
        atualizar()


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
        # Lista de usuários cadastrados (do módulo de gestão de usuários) para seleção
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
                _log().warning(f"salvar: falha ao auditar configurações | {e}")
            ui.notify("Configurações salvas", type="positive")
        botao("Salvar configurações", icone="save", on_click=salvar,
            variante="solido", chave_modulo="solicita_impressao",
            extra_classes="min-w-[180px]")


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

    Renderiza uma tabela pequena de relatório com cabeçalho + linhas (ou aviso de vazio)."""
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
    range. Totals come ready (overall, color, B&W, by secretaria, setor,
    authorizer, printer).

    Sub-aba Relatórios: prazos fixos mensais (este mês, mês anterior, últimos
    6 meses, ano atual) ou período personalizado no calendário. Ao escolher um
    prazo fixo, as datas são preenchidas e o relatório é gerado na hora."""
    from mod_solicita_impressao import bd_manipulador as bd
    import datetime as _dt
    wrap = ui.column().classes("w-full gap-2")

    with ui.card().classes("w-full"):
        ui.label("Relatório de impressões").classes("text-subtitle2")
        with ui.row().classes("w-full items-center gap-2 flex-wrap"):
            btn_mes_atual = botao("Este mês", icone="calendar_month",
                                  on_click=lambda: _prazo_fixo("mes_atual"),
                                  variante="contorno", chave_modulo="solicita_impressao")
            btn_mes_ant = botao("Mês anterior", icone="calendar_month",
                                on_click=lambda: _prazo_fixo("mes_anterior"),
                                variante="contorno", chave_modulo="solicita_impressao")
            btn_6m = botao("Últimos 6 meses", icone="date_range",
                           on_click=lambda: _prazo_fixo("6_meses"),
                           variante="contorno", chave_modulo="solicita_impressao")
            btn_ano = botao("Ano atual", icone="event",
                            on_click=lambda: _prazo_fixo("ano_atual"),
                            variante="contorno", chave_modulo="solicita_impressao")
        ui.separator().classes("my-1")
        with ui.row().classes("w-full items-center gap-2 flex-wrap"):
            inp_dt_ini = ui.input("Data inicial").props("outlined dense type=date").classes("w-44")
            inp_dt_fim = ui.input("Data final").props("outlined dense type=date").classes("w-44")
            botao("Gerar relatório", icone="assessment", on_click=lambda: gerar(),
                  variante="solido", chave_modulo="solicita_impressao")

    with wrap:
        ui.label("Escolha um prazo fixo mensal acima ou informe um período "
                 "no calendário para gerar o relatório.").classes("text-grey-6")

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
