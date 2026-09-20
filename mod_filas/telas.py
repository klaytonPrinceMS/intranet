"""Tela do módulo Filas — gestor de chamadas + TV com voz e mídia.

EN: Queue screen — multi-queue manager, sequential steps, TV with voice and media playlist.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from nicegui import ui
from mod_intranet import autenticacao
from mod_intranet.aba_modulo import cabecalho
from mod_intranet.tema_modulo import ler_tema, notificar
from mod_intranet.ui_comum import botao
from mod_filas import bd_manipulador as filas


def _pode_acessar(user_nome: str, perfil: str) -> bool:
    if perfil == "administrador_geral":
        return True
    try:
        return autenticacao.validar_acesso_modulo(user_nome, "filas")
    except Exception:
        return False


def mostrar_tela(user_nome: str, perfil_global: str = ""):
    if not _pode_acessar(user_nome, perfil_global):
        with ui.column().classes("w-full items-center p-12 gap-3"):
            ui.icon("block", size="64px").classes("text-red-8")
            ui.label("Acesso restrito").classes("text-h6")
            ui.label("Somente usuários com acesso ao módulo Filas.").classes("text-body2 text-grey-7")
        return
    tema = ler_tema("filas", cor_botao="#000000", cor_texto_botao="#FFFFFF",
                    texto_header="Gestor de filas com chamadas, etapas e TV. Crie filas por local e avance sequencialmente.")
    ui.colors(primary=tema["cor_botao"])
    eh_admin_modulo = autenticacao.eh_admin_do_modulo(user_nome, "filas")
    eh_admin = perfil_global == "administrador_geral" or eh_admin_modulo

    with ui.column().classes("w-full p-6 gap-4"):
        cabecalho("Filas — Chamadas", tema["texto_header"], chave_modulo="filas",
                  cor_titulo=tema["cor_titulo"], cor_fundo=tema["cor_fundo"])

        # Criar fila — qualquer usuário com acesso pode criar a sua; admin cria para qualquer local
        with ui.card().classes("w-full p-4 gap-3"):
            ui.label("Nova fila por local").classes("text-subtitle2 font-bold")
            ui.label("Ex: Ambulatório — xyz, Regulação de Viagem — abx, PSF AER. Cada fila tem etapas sequenciais (Atendimento → Triagem → Consultório 3). A fila criada fica visível só para você; admin geral vê todas. Numeração com início/fim e infinita quando fim=0.").classes("text-caption text-grey-6")
            with ui.row().classes("w-full gap-2 flex-wrap"):
                inp_nome = ui.input("Nome da fila *", placeholder="Ambulatório").props("outlined dense").classes("flex-1 min-w-[160px]")
                inp_end = ui.input("Endereço", placeholder="xyz — Rua ...").props("outlined dense").classes("flex-1 min-w-[160px]")
                inp_desc = ui.input("Descrição", placeholder="Atendimento geral").props("outlined dense").classes("flex-1 min-w-[160px]")
            with ui.row().classes("w-full gap-2 flex-wrap"):
                inp_pref = ui.input("Prefixo", placeholder="A").props("outlined dense").classes("w-[80px]")
                inp_inicio = ui.input("Início", placeholder="1").props("outlined dense type=number").classes("w-[90px]")
                inp_fim = ui.input("Fim (0=infinito)", placeholder="0").props("outlined dense type=number").classes("w-[110px]")
                inp_guiche = ui.input("Guichê base", placeholder="01").props("outlined dense").classes("w-[90px]")
                inp_grupo = ui.input("TV grupo (opcional)", placeholder="ex: recepcao — vazio=TV isolada").props("outlined dense").classes("flex-1 min-w-[180px]")
                inp_inicio.value = "1"
                inp_fim.value = "0"

            link_criada = ui.column().classes("w-full gap-1")

            def _criar():
                si = inp_inicio.value or "1"
                sf = inp_fim.value or "0"
                ok, res = filas.criar_fila(inp_nome.value or "", endereco=inp_end.value or "", descricao=inp_desc.value or "", prefixo=inp_pref.value or "A", guiche=inp_guiche.value or "01", ator=user_nome, senha_inicio=si, senha_fim=sf, tv_grupo=inp_grupo.value or "")
                if ok:
                    fid = res
                    # link TV isolada ou compartilhada
                    fila = filas.obter_fila(fid)
                    grupo = fila[12] if fila and len(fila) > 12 else ""
                    if grupo:
                        tv_url = f"/tv?grupo={grupo}"
                        tv_label = f"TV do grupo '{grupo}' (compartilhada)"
                    else:
                        tv_url = f"/tv/{fid}"
                        tv_label = f"TV isolada da fila '{inp_nome.value.strip()}'"
                    notificar(f"Fila '{inp_nome.value.strip()}' criada — senha {fila[2] if fila else ''} início={si} fim={sf if sf!='0' else '∞'}", type="positive")
                    link_criada.clear()
                    with link_criada:
                        with ui.row().classes("items-center gap-2"):
                            ui.icon("check_circle", size="20px").classes("text-green-7")
                            ui.label(tv_label).classes("font-bold text-caption")
                            botao("Abrir TV desta fila", icone="tv", on_click=lambda url=tv_url: ui.navigate.to(url, new_tab=True), variante="primario", chave_modulo="filas")
                            ui.label(f"Link: {tv_url}").classes("text-caption text-grey-6")
                    inp_nome.value = inp_end.value = inp_desc.value = ""
                    render_filas()
                else:
                    notificar(res, type="negative")
            botao("Criar fila", icone="add", on_click=_criar, variante="primario", chave_modulo="filas")
            with link_criada:
                pass

        box = ui.column().classes("w-full gap-4")

        def render_filas():
            box.clear()
            with box:
                filas_visiveis = filas.listar_filas_visiveis(user_nome, perfil_global, eh_admin_modulo)
                if not filas_visiveis:
                    ui.label("Nenhuma fila sua ainda. Crie acima.").classes("text-caption text-grey-6 italic")
                    return
                for fid, nome, senha, status, guiche, data, endereco, descricao, prefixo, criado_por, senha_inicio, senha_fim, tv_grupo in filas_visiveis:
                    etapas = filas.listar_etapas(fid)
                    ult = filas.ultima_chamada(fid)
                    with ui.card().classes("w-full p-4 gap-3"):
                        with ui.row().classes("w-full items-center justify-between flex-wrap gap-2"):
                            with ui.column().classes("gap-0 flex-1 min-w-[200px]"):
                                ui.label(nome).classes("font-bold text-h6")
                                ui.label(f"{endereco or 'sem endereço'} • {descricao or ''}").classes("text-caption text-grey-6")
                                ui.label(f"Senha atual: {senha} • Prefixo: {prefixo} • {senha_inicio}→{senha_fim if senha_fim else '∞'} • Guichê base: {guiche} • TV: {tv_grupo or 'isolada'} • Dono: {criado_por or '—'} • {status}").classes("text-caption text-grey-6")
                            with ui.row().classes("gap-1 flex-wrap"):
                                # link TV isolada ou compartilhada
                                if tv_grupo:
                                    tv_url = f"/tv?grupo={tv_grupo}"
                                    botao(f"TV grupo {tv_grupo}", icone="tv", on_click=lambda u=tv_url: ui.navigate.to(u, new_tab=True), variante="contorno", chave_modulo="filas").tooltip(f"TV compartilhada — grupo {tv_grupo}")
                                else:
                                    tv_url = f"/tv/{fid}"
                                    botao("Abrir TV desta fila", icone="tv", on_click=lambda u=tv_url: ui.navigate.to(u, new_tab=True), variante="contorno", chave_modulo="filas").tooltip(f"TV isolada — fila {nome}")
                                if eh_admin or criado_por == user_nome:
                                    def _excluir(fid=fid, nome=nome):
                                        ok, msg = filas.excluir_fila(fid, ator=user_nome)
                                        notificar(msg, type="positive" if ok else "negative")
                                        render_filas()
                                    botao("Excluir", icone="delete", on_click=_excluir, variante="contorno", chave_modulo="filas")
                                ui.label(f"Link: {tv_grupo and f'/tv?grupo={tv_grupo}' or f'/tv/{fid}'}").classes("text-caption text-grey-6 self-center")
                        # etapas — isoladas por fila
                        with ui.row().classes("w-full gap-2 flex-wrap"):
                            for eid, efid, ordem, enome, eguiche, eativo in etapas:
                                ui.badge(f"{ordem}. {enome} ({eguiche or guiche})", color="primary").props("outline")
                        # chamar — isolado
                        with ui.row().classes("w-full gap-2 flex-wrap items-end"):
                            inp_paciente = ui.input("Paciente (opcional p/ voz)", placeholder="Nome").props("outlined dense").classes("flex-1 min-w-[160px]")
                            sel_etapa = ui.select([e[3] for e in etapas], value=etapas[0][3] if etapas else "Atendimento", label="Etapa/Destino").props("outlined dense").classes("w-[180px]") if etapas else None

                            def _chamar(fid=fid, inp=inp_paciente, sel=sel_etapa):
                                etapa = sel.value if sel else "Atendimento"
                                paciente = inp.value.strip() if inp else ""
                                ok, msg = filas.gerar_senha(fid, ator=user_nome, paciente_nome=paciente, etapa_nome=etapa)
                                notificar(f"Senha {msg} → {etapa}" if ok else msg, type="positive" if ok else "negative")
                                if inp:
                                    inp.value = ""
                                render_filas()
                            botao("Chamar próximo", icone="campaign", on_click=_chamar, variante="primario", chave_modulo="filas")
                            if ult:
                                cid, senha_u, guiche_u, data_u, pac_u, etapa_u, fnome_u = ult
                                ui.label(f"Última: {senha_u} {pac_u or ''} → {etapa_u} ({guiche_u}) {data_u[:16] if data_u else ''}").classes("text-caption text-grey-7 self-center")

                        # histórico isolado desta fila
                        with ui.expansion("Histórico desta fila (isolado)", icon="history").classes("w-full"):
                            for cid, fid2, senha2, guiche2, data2, por2, pac2, etapa2, fn2 in filas.listar_chamadas(5, fila_id=fid):
                                with ui.row().classes("w-full items-center justify-between gap-2"):
                                    ui.label(f"{senha2} — {etapa2} — {pac2 or '—'} — guichê {guiche2} — {data2[:16] if data2 else ''}").classes("text-caption flex-1")
                                    # avançar só se não for última etapa e for dono/admin
                                    if eh_admin or criado_por == user_nome:
                                        et_nomes = [e[3] for e in etapas]
                                        if etapa2 in et_nomes and et_nomes.index(etapa2) < len(et_nomes) - 1:
                                            def _av(cid=cid):
                                                ok, m = filas.avancar_chamada(cid, ator=user_nome)
                                                notificar(m, type="positive" if ok else "warning")
                                                render_filas()
                                            botao("Avançar", icone="arrow_forward", on_click=_av, variante="texto", chave_modulo="filas")

        render_filas()

        # Excluir uma ou todas — confirmação
        with ui.row().classes("w-full justify-center mt-2 gap-2 flex-wrap"):
            def _confirmar_excluir_todas():
                titulo = "Excluir todas as filas" if eh_admin else "Excluir todas minhas filas"
                msg = "Tem certeza? Todas as filas (exceto Geral) e suas chamadas/etapas serão apagadas. Esta ação não pode ser desfeita." if eh_admin else "Excluir todas as SUAS filas (exceto Geral)?"
                with ui.dialog() as dlg, ui.card():
                    ui.label(titulo).classes("font-bold")
                    ui.label(msg).classes("text-caption text-grey-7")
                    with ui.row().classes("w-full justify-end gap-2"):
                        ui.button("Cancelar", on_click=dlg.close).props("flat")
                        def _executar():
                            ok, m = filas.excluir_todas_filas(ator=user_nome, somente_do_criador=user_nome, eh_admin=eh_admin)
                            notificar(m, type="positive" if ok else "negative")
                            dlg.close()
                            render_filas()
                        ui.button("Confirmar exclusão", on_click=_executar).props("color=negative")
                dlg.open()
            label_todas = "Excluir todas as filas" if eh_admin else "Excluir todas minhas filas"
            botao(label_todas, icone="delete_forever", on_click=_confirmar_excluir_todas, variante="contorno", chave_modulo="filas").tooltip("Exclui em lote — Geral preservada").props("color=negative")

        with ui.row().classes("w-full justify-center mt-2 gap-2"):
            botao("Administração", icone="admin_panel_settings", on_click=lambda: ui.navigate.to("/admin/filas"), variante="texto", chave_modulo="filas")


def mostrar_tv(fila_id: int = None, tv_grupo: str = None):
    """Tela da TV — chama com voz+bip só no novo id + playlist mídia quando ocioso. Suporta fila isolada ou grupo compartilhado."""
    from mod_intranet.tema_modulo import ler_tema as _ler
    from mod_intranet.bd_conexao import get_config as _get_cfg
    tema = _ler("filas")
    ui.colors(primary=tema.get("cor_botao", "#000000"))
    # ícone padrão da intranet
    try:
        icone_sistema = (_get_cfg("icone_sistema", "hub") or "hub").strip()
        titulo_sistema = (_get_cfg("titulo_sistema", "INTRANET") or "INTRANET").strip()
    except Exception:
        icone_sistema = "hub"
        titulo_sistema = "INTRANET"
    # tenta resolver grupo a partir de fila_id se tv_grupo não veio
    if fila_id and not tv_grupo:
        try:
            f = filas.obter_fila(int(fila_id))
            if f and len(f) > 12 and f[12]:
                tv_grupo = f[12]
        except Exception:
            pass
    # carrega mídias ativas
    midias = filas.listar_midias(somente_ativas=True)

    # cabeçalho com ícone padrão
    with ui.column().classes("w-full h-screen bg-black text-white gap-0 p-0").style("min-height: 100vh"):
        with ui.row().classes("w-full items-center gap-3 px-4 py-2 bg-grey-900"):
            ui.icon(icone_sistema).classes("text-white").style("font-size: 28px")
            ui.label(titulo_sistema).classes("text-white font-bold")
            ui.label("•").classes("text-grey-5")
            if tv_grupo:
                ui.label(f"TV — Grupo {tv_grupo} (compartilhada)").classes("text-white font-bold tracking-widest")
            elif fila_id:
                try:
                    f = filas.obter_fila(int(fila_id))
                    nome_f = f[1] if f else f"#{fila_id}"
                except Exception:
                    nome_f = f"#{fila_id}"
                ui.label(f"TV — Fila {nome_f} (isolada)").classes("text-white font-bold tracking-widest")
            else:
                ui.label("TV — Todas as filas").classes("text-white font-bold tracking-widest")
            ui.space()
            ui.label("Mídia: áudio elevador / vídeo propaganda").classes("text-caption text-grey-4")

        # chamada principal
        with ui.column().classes("w-full items-center justify-center gap-2 py-6 flex-1"):
            lbl_topo = ui.label("AGUARDE CHAMADA").classes("text-[1.6vw] tracking-widest text-grey-4")
            lbl_fila = ui.label("").classes("text-[1.1vw] text-grey-3")
            lbl_senha = ui.label("—").classes("text-[10vw] font-extrabold leading-none")
            lbl_paciente = ui.label("").classes("text-[2.5vw] font-bold text-yellow-3")
            lbl_destino = ui.label("").classes("text-[3vw] font-bold")
            lbl_guiche = ui.label("").classes("text-[2vw] text-grey-3")

        # área de mídia
        media_container = ui.column().classes("w-full items-center justify-center bg-grey-900 p-2 gap-2")
        with media_container:
            media_html = ui.html("", sanitize=False).classes("w-full flex justify-center")

        # rodapé notícias
        with ui.card().classes("w-full bg-grey-900 text-white p-4 gap-2 rounded-none").style("min-height: 14vh"):
            ui.label("Notícias — agregador").classes("text-caption tracking-widest text-grey-4")
            lbl_n_titulo = ui.label("Aguardando notícias...").classes("text-[1.4vw] font-bold leading-tight")
            lbl_n_desc = ui.label("").classes("text-[0.9vw] text-grey-3 leading-tight")
            lbl_n_fonte = ui.label("").classes("text-caption text-grey-5")

        noticias_tv = {"lista": [], "idx": 0}
        estado = {"ultimo_id": None, "midia_idx": 0}

        def _js_beep_e_voz(texto: str):
            texto_esc = texto.replace("'", "\\'").replace('"', '\\"').replace("\n", " ")
            js = f"""
try {{
  const ctx = new (window.AudioContext||window.webkitAudioContext)();
  const o = ctx.createOscillator(); const g = ctx.createGain();
  o.type='sine'; o.frequency.value=880; g.gain.value=0.25;
  o.connect(g); g.connect(ctx.destination); o.start(); o.stop(ctx.currentTime+0.35);
}} catch(e){{}}
try {{
  if('speechSynthesis' in window) {{
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance('{texto_esc}');
    u.lang='pt-BR'; u.rate=0.9; u.pitch=1.0; u.volume=1.0;
    window.speechSynthesis.speak(u);
  }}
}} catch(e){{}}
"""
            try:
                ui.run_javascript(js)
            except Exception:
                pass

        def _render_midia(idx: int):
            if not midias:
                media_html.content = "<div class='text-grey-5 text-caption'>Nenhuma mídia cadastrada — adicione áudios MP3 ou vídeos MP4 em Administração → Filas → Mídia</div>"
                return
            mid = midias[idx % len(midias)]
            _, nome, tipo, caminho, orig, ordem, ativo, _ = mid
            src = caminho if caminho.startswith("/") else f"/midia_filas/{os.path.basename(caminho)}"
            if not src.startswith("/midia_filas"):
                src = f"/midia_filas/{os.path.basename(src)}"
            if tipo == "audio":
                media_html.content = f"<div class='w-full max-w-[800px]'><div class='text-caption text-grey-4 mb-1'>{nome} — áudio ambiente</div><audio controls autoplay loop style='width:100%'><source src='{src}' type='audio/mpeg'></audio></div>"
            else:
                media_html.content = f"<div class='w-full max-w-[900px]'><div class='text-caption text-grey-4 mb-1'>{nome} — propaganda</div><video autoplay muted loop controls playsinline style='width:100%;max-height:32vh;background:#111'><source src='{src}' type='video/mp4'></video></div>"

        def refresh_chamada():
            # isolada vs compartilhada vs global
            if tv_grupo:
                ult = filas.ultima_chamada_tv(tv_grupo=tv_grupo)
            elif fila_id:
                ult = filas.ultima_chamada(int(fila_id))
            else:
                ult = filas.ultima_chamada()
            if not ult:
                return
            cid, senha, guiche, data, paciente, etapa, fnome = ult
            if estado["ultimo_id"] == cid:
                return
            estado["ultimo_id"] = cid
            lbl_fila.text = fnome or ""
            lbl_senha.text = str(senha)
            lbl_paciente.text = paciente or ""
            lbl_destino.text = f"{etapa}" if etapa else ""
            lbl_guiche.text = f"Guichê {guiche} • {fnome}" if guiche else (fnome or "")
            partes = []
            if paciente:
                partes.append(paciente)
            partes.append(f"senha {senha}")
            if etapa:
                partes.append(f"dirigir-se a {etapa}")
            if fnome:
                partes.append(f"fila {fnome}")
            if guiche:
                partes.append(f"guichê {guiche}")
            texto = ", ".join(partes) + "."
            _js_beep_e_voz(texto)
            media_html.content = "<div class='text-yellow-3 font-bold'>🔊 Chamada em andamento — mídia pausada</div>"
            ui.timer(12.0, lambda: _render_midia(estado["midia_idx"]), once=True)

        def carregar_noticias():
            try:
                from mod_agregador_noticias.bd_manipulador import listar_para_tv, habilitado  # type: ignore
                if not habilitado():
                    lbl_n_titulo.text = "Agregador desabilitado — ative em /admin/agregador_noticias"
                    lbl_n_desc.text = ""
                    lbl_n_fonte.text = ""
                    return
                lst = listar_para_tv(limite=10)
                if lst:
                    noticias_tv["lista"] = lst
                    noticias_tv["idx"] = 0
                    _mostrar_noticia()
                else:
                    lbl_n_titulo.text = "Nenhuma notícia ainda — aguarde coleta"
            except Exception:
                pass

        def _mostrar_noticia():
            lst = noticias_tv["lista"]
            if not lst:
                return
            idx = noticias_tv["idx"] % len(lst)
            item = lst[idx]
            lbl_n_titulo.text = item.get("titulo", "")[:120]
            lbl_n_desc.text = (item.get("descricao", "") or "")[:180]
            lbl_n_fonte.text = f"{item.get('fonte','')} • {item.get('tema','')}"
            noticias_tv["idx"] = (idx + 1) % len(lst)

        def rotacionar_midia():
            if estado["ultimo_id"] is None:
                estado["midia_idx"] = (estado["midia_idx"] + 1) % max(1, len(midias) if midias else 1)
                _render_midia(estado["midia_idx"])

        _render_midia(0)
        refresh_chamada()
        carregar_noticias()
        ui.timer(3.0, refresh_chamada)
        ui.timer(7.0, _mostrar_noticia)
        ui.timer(120.0, carregar_noticias)
        ui.timer(40.0, rotacionar_midia)
