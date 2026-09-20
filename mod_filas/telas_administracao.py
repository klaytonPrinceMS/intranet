"""Filas admin panel — multi-queues, steps and TV media.

EN: Administration panel for Filas module — multi-queues per local, sequential
    steps and global TV media playlist.

Painel de administração do módulo Filas — multi-filas, etapas e mídia TV."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from nicegui import ui, app
from mod_intranet.ui_comum import card_admin, rodape_salvar_restaurar
from mod_intranet.tema_modulo import ler_tema, notificar, bloco_aparencia
from mod_intranet import observabilidade
from mod_filas import bd_manipulador as filas
from mod_filas.telas import bloco_midia_fila, bloco_nomes_fila, bloco_controle_tv

log = observabilidade.get_logger("filas")
PASTA_MIDIA = filas.PASTA_MIDIA


def mostrar_administracao(usuario_logado: str = ""):
    tema = ler_tema("filas", cor_botao="#000000", cor_texto_botao="#FFFFFF",
                    texto_header="Gestor de filas — multi-filas por local, fluxo sequencial e mídia da TV.")
    tema["_defaults"] = {
        "cor_botao": "", "cor_texto_botao": "", "cor_fundo": "",
        "cor_titulo": "#212121", "btn_tamanho": "medium",
        "texto_header": "Gestor de filas — multi-filas por local, fluxo sequencial e mídia da TV.",
        "cor_fundo_card": "#FFFFFF", "cor_texto_card": "",
    }
    ui.colors(primary=tema["cor_botao"])
    bloco_aparencia(usuario_logado, "filas", tema, prefixo_auditoria="filas", com_texto_header=True)

    # ===== Filas por local =====
    with card_admin("Filas — por local/endereço (isoladas por criador, TV por fila ou grupo)", icone="queue", chave_modulo="filas", grade=False):
        ui.label("Cada fila é isolada (não interfere em outra). Por padrão, cada fila tem TV isolada /tv/<id>. Para compartilhar a mesma TV entre várias filas, defina o mesmo 'TV grupo' (ex: recepcao) — todas com mesmo grupo aparecem na mesma TV (/tv?grupo=recepcao). Numeração com início/fim e infinita quando fim=0.").classes("text-caption text-grey-6")
        ui.label("Apenas o criador vê/gerencia suas filas; administrador geral vê todas.").classes("text-caption text-grey-6")
        box_filas = ui.column().classes("w-full gap-3")

        def render_filas():
            box_filas.clear()
            with box_filas:
                # admin vê todas
                for fid, nome, senha, status, guiche, data, endereco, descricao, prefixo, criado_por, senha_inicio, senha_fim, tv_grupo in filas.listar_filas():
                    etapas = filas.listar_etapas(fid)
                    tv_link = f"/tv?grupo={tv_grupo}" if tv_grupo else f"/tv/{fid}"
                    with ui.card().classes("w-full p-3 gap-2"):
                        with ui.row().classes("w-full items-center justify-between flex-wrap gap-2"):
                            with ui.column().classes("gap-0 flex-1"):
                                ui.label(f"{nome} ({prefixo}{senha})").classes("font-bold")
                                ui.label(f"{endereco or 'sem endereço'} • {descricao or ''} • Guichê base {guiche} • TV: {tv_grupo or 'isolada'} • {senha_inicio}→{senha_fim if senha_fim else '∞'} • Dono: {criado_por or '—'} • {status}").classes("text-caption text-grey-6")
                                ui.label(f"Link TV: {tv_link}").classes("text-caption text-primary")
                            with ui.row().classes("gap-1 flex-wrap"):
                                ui.button("Abrir TV", icon="tv", on_click=lambda u=tv_link: ui.navigate.to(u, new_tab=True)).props("outline dense").tooltip(f"TV {'grupo '+tv_grupo if tv_grupo else 'isolada'}")
                                def _excluir(fid=fid, nome=nome):
                                    ok, msg = filas.excluir_fila(fid, ator=usuario_logado)
                                    notificar(msg, type="positive" if ok else "negative")
                                    render_filas()
                                ui.button("Excluir", icon="delete", on_click=_excluir).props("outline dense color=negative").tooltip(f"Excluir fila {nome}")
                        # editar inline
                        with ui.row().classes("w-full gap-2 flex-wrap"):
                            inp_nome = ui.input("Nome", value=nome).props("outlined dense").classes("flex-1 min-w-[120px]")
                            inp_end = ui.input("Endereço", value=endereco or "").props("outlined dense").classes("flex-1 min-w-[120px]")
                            inp_desc = ui.input("Descrição", value=descricao or "").props("outlined dense").classes("flex-1 min-w-[120px]")
                        with ui.row().classes("w-full gap-2 flex-wrap"):
                            inp_pref = ui.input("Prefixo", value=prefixo or "A").props("outlined dense").classes("w-[70px]")
                            inp_inicio = ui.input("Início", value=str(senha_inicio or 1)).props("outlined dense type=number").classes("w-[80px]")
                            inp_fim = ui.input("Fim (0=∞)", value=str(senha_fim or 0)).props("outlined dense type=number").classes("w-[80px]")
                            inp_guiche = ui.input("Guichê base", value=guiche or "01").props("outlined dense").classes("w-[80px]")
                        with ui.row().classes("w-full gap-2 flex-wrap items-end"):
                            try:
                                _grupos = filas.listar_grupos_tv()
                            except Exception:
                                _grupos = []
                            _ops = ["(manter/isolada)"] + [g for g in _grupos if g != (tv_grupo or "")]
                            if tv_grupo:
                                _ops = [tv_grupo] + [g for g in _grupos if g != tv_grupo] + ["(nova abaixo)"]
                            sel_grupo = ui.select(_ops, label="TV grupo em uso").props("outlined dense").classes("flex-1 min-w-[160px]")
                            inp_grupo = ui.input("Nova TV grupo (slug)", placeholder="ex: recepcao-2 — vazio=isolada").props("outlined dense").classes("flex-1 min-w-[140px]")

                            def _grupo_final(sel=sel_grupo, novo=inp_grupo):
                                digitado = (novo.value or "").strip()
                                if digitado:
                                    return digitado
                                s = sel.value or ""
                                if s in ("(manter/isolada)", "(nova abaixo)"):
                                    return ""
                                return s

                            def _salvar(fid=fid, a=inp_nome, b=inp_end, c=inp_desc, d=inp_pref, e=inp_guiche, si=inp_inicio, sf=inp_fim, gf=_grupo_final):
                                ok, msg = filas.atualizar_fila(fid, nome=a.value, endereco=b.value, descricao=c.value, prefixo=d.value, guiche=e.value, senha_inicio=si.value, senha_fim=sf.value, tv_grupo=gf(), ator=usuario_logado)
                                notificar(msg, type="positive" if ok else "negative")
                                render_filas()
                            ui.button("Salvar", icon="save", on_click=_salvar).props("dense color=primary")
                        ui.label("Lista = grupos em uso (selecione p/ compartilhar a TV) ou digite um novo slug. Vazio = TV isolada.").classes("text-caption text-grey-6")

                        # etapas
                        ui.separator()
                        ui.label(f"Etapas sequenciais — {nome} (isoladas)").classes("text-caption font-bold")
                        with ui.column().classes("w-full gap-1"):
                            for eid, efid, ordem, enome, eguiche, eativo in etapas:
                                with ui.row().classes("w-full items-center gap-2"):
                                    ui.label(f"{ordem}.").classes("w-[24px] text-caption")
                                    inp_enome = ui.input(value=enome).props("outlined dense").classes("flex-1")
                                    inp_eguiche = ui.input(value=eguiche or "").props("outlined dense").classes("w-[100px]")
                                    def _upd_et(eid=eid, a=inp_enome, b=inp_eguiche):
                                        ok, msg = filas.atualizar_etapa(eid, nome=a.value, guiche=b.value, ator=usuario_logado)
                                        notificar(msg, type="positive" if ok else "negative")
                                    def _del_et(eid=eid):
                                        ok, msg = filas.excluir_etapa(eid, ator=usuario_logado)
                                        notificar(msg, type="positive" if ok else "negative")
                                        render_filas()
                                    ui.button(icon="save", on_click=_upd_et).props("dense flat").tooltip("Salvar etapa")
                                    ui.button(icon="delete", on_click=_del_et).props("dense flat color=negative").tooltip("Excluir etapa")

                        with ui.row().classes("w-full gap-2"):
                            inp_nova_etapa = ui.input("Nova etapa", placeholder="Ex: Consultório 3").props("outlined dense").classes("flex-1")
                            inp_nova_guiche = ui.input("Guichê/Sala", placeholder="03").props("outlined dense").classes("w-[100px]")

                            def _add_etapa(fid=fid, a=inp_nova_etapa, b=inp_nova_guiche):
                                ok, msg = filas.criar_etapa(fid, a.value or "", guiche=b.value or "", ator=usuario_logado)
                                notificar(msg, type="positive" if ok else "negative")
                                if ok:
                                    a.value = ""; b.value = ""
                                    render_filas()
                            ui.button("Adicionar etapa", icon="add", on_click=_add_etapa).props("dense color=primary")

                        # voz + repetição + textos da TV
                        try:
                            _cfg = filas.obter_extras_fila(fid)
                        except Exception:
                            _cfg = {}
                        with ui.expansion("Voz e textos da TV", icon="record_voice_over").classes("w-full"):
                            with ui.row().classes("w-full gap-2 flex-wrap items-center"):
                                ui.label("Falar:").classes("text-caption font-bold")
                                v_nome = ui.checkbox("Nome", value=bool(_cfg.get("voz_nome", 1)))
                                v_senha = ui.checkbox("Senha", value=bool(_cfg.get("voz_senha", 1)))
                                v_dest = ui.checkbox("Destino", value=bool(_cfg.get("voz_destino", 1)))
                                v_guiche = ui.checkbox("Guichê", value=bool(_cfg.get("voz_guiche", 1)))
                                v_fila = ui.checkbox("Fila", value=bool(_cfg.get("voz_fila", 1)))
                                v_hora = ui.checkbox("Hora cheia/meia", value=bool(_cfg.get("voz_hora", 1)))
                                v_rep = ui.number("Repetir", value=_cfg.get("voz_repetir", 0), min=0, max=10, step=1).props("outlined dense").classes("w-[90px]")
                                v_int = ui.number("Intervalo(s)", value=_cfg.get("voz_intervalo", 2), min=1, max=60, step=1).props("outlined dense").classes("w-[100px]")
                            t_tit = ui.input("Título da TV", value=_cfg.get("tv_titulo") or "").props("outlined dense").classes("w-full")
                            t_sub = ui.input("Subtítulo da TV", value=_cfg.get("tv_subtitulo") or "").props("outlined dense").classes("w-full")
                            t_ag = ui.input("Texto quando ociosa", value=_cfg.get("tv_aguardando") or "AGUARDE CHAMADA").props("outlined dense").classes("w-full")
                            t_leg = ui.input("Legenda da mídia", value=_cfg.get("tv_midia_legenda") or "").props("outlined dense").classes("w-full")
                            t_not = ui.input("Título das notícias", value=_cfg.get("tv_noticias_titulo") or "Notícias").props("outlined dense").classes("w-full")

                            def _salvar_voz(fid=fid, a=v_nome, b=v_senha, c=v_dest, d=v_guiche, vf=v_fila, vh=v_hora, e=v_rep, f2=v_int, g=t_tit, h=t_sub, i=t_ag, j=t_leg, k=t_not):
                                try:
                                    rep = int(float(e.value or 0))
                                except Exception:
                                    rep = 0
                                try:
                                    interv = int(float(f2.value or 2))
                                except Exception:
                                    interv = 2
                                ok, msg = filas.atualizar_fila(fid, ator=usuario_logado, voz_nome=a.value, voz_senha=b.value, voz_destino=c.value, voz_guiche=d.value, voz_fila=vf.value, voz_hora=vh.value, voz_repetir=rep, voz_intervalo=interv, tv_titulo=g.value, tv_subtitulo=h.value, tv_aguardando=i.value, tv_midia_legenda=j.value, tv_noticias_titulo=k.value)
                                notificar(msg, type="positive" if ok else "negative")
                                render_filas()
                            ui.button("Salvar voz e textos", icon="save", on_click=_salvar_voz).props("dense color=primary")

                        bloco_nomes_fila(fid, usuario_logado, render_filas)
                        bloco_midia_fila(fid, usuario_logado, render_filas)
                        try:
                            _ids_tv = filas.ids_do_grupo(tv_grupo) if tv_grupo else [fid]
                        except Exception:
                            _ids_tv = [fid]
                        bloco_controle_tv(filas.chave_tv(tv_grupo=tv_grupo) if tv_grupo else filas.chave_tv(fila_id=fid), tv_grupo or nome, fila_ids=_ids_tv)

        render_filas()

        with ui.row().classes("w-full gap-2 flex-wrap mt-2"):
            ui.button("Recarregar", icon="refresh", on_click=render_filas).props("outline dense")
            ui.button("Abrir TV geral", icon="tv", on_click=lambda: ui.navigate.to("/tv", new_tab=True)).props("outline dense")
            def _confirmar_todas_admin():
                with ui.dialog() as dlg, ui.card():
                    ui.label("Excluir todas as filas").classes("font-bold")
                    ui.label("Todas as filas serão apagadas com chamadas, etapas, mídias e nomes. Confirmar?").classes("text-caption text-grey-7")
                    with ui.row().classes("w-full justify-end gap-2"):
                        ui.button("Cancelar", on_click=dlg.close).props("flat")
                        def _exec():
                            ok, msg = filas.excluir_todas_filas(ator=usuario_logado, eh_admin=True)
                            notificar(msg, type="positive" if ok else "negative")
                            dlg.close()
                            render_filas()
                        ui.button("Confirmar", on_click=_exec).props("color=negative")
                dlg.open()
            ui.button("Excluir todas as filas", icon="delete_forever", on_click=_confirmar_todas_admin).props("outline dense color=negative").tooltip("Exclui todas as filas")

    # ===== Áudio ambiente global — toca em TODAS as TVs (menu hambúrguer → Administração) =====
    with card_admin("Áudio ambiente global — toca em todas as filas", icone="queue_music", chave_modulo="filas", grade=False):
        ui.label("Áudios aqui tocam em TODAS as TVs (isoladas, grupos e geral), após as mídias de cada fila. Gerencie a altura do som (volume) por áudio. Vídeos/fotos globais ficam só na TV geral (/tv).").classes("text-caption text-grey-6")
        ui.label("Formatos: .mp3, .wav, .ogg (áudio), .mp4, .webm (vídeo) e .jpg, .png, .webp (foto). Arquivos ficam em mod_filas/midia/ e são servidos em /midia_filas/*.").classes("text-caption text-grey-6")

        box_midia = ui.column().classes("w-full gap-2")

        def render_midia():
            box_midia.clear()
            with box_midia:
                midias = [m for m in filas.listar_midias() if not m[8]]
                if not midias:
                    ui.label("Nenhuma mídia global. Faça upload abaixo ou envie por fila.").classes("text-caption text-grey-6 italic")
                for mid, nome, tipo, caminho, orig, ordem, ativo, criado, f_id, volume, duracao, slot, real in midias:
                    src = f"/midia_filas/{os.path.basename(caminho)}"
                    _onde = "todas as TVs" if tipo == "audio" else "só TV geral"
                    with ui.card().classes("w-full p-3 gap-2"):
                        with ui.row().classes("w-full items-center justify-between gap-2 flex-wrap"):
                            with ui.column().classes("gap-0 flex-1"):
                                ui.label(f"Exibição {slot} • [{tipo}] {nome} • vol {volume} • {_onde}").classes("font-bold text-caption")
                                ui.label(f"{orig or os.path.basename(caminho)} • {src} • {'ativo' if ativo else 'inativo'} • {criado[:16] if criado else ''}").classes("text-caption text-grey-6")
                                if tipo == "audio":
                                    ui.html(f"<audio controls style='width:100%;max-width:400px'><source src='{src}' type='audio/mpeg'></audio>", sanitize=False)
                                elif tipo == "video":
                                    ui.html(f"<video controls style='width:100%;max-width:400px;max-height:180px;background:#111'><source src='{src}' type='video/mp4'></video>", sanitize=False)
                                else:
                                    ui.image(src).classes("w-full max-w-[400px]")
                            with ui.row().classes("gap-1 flex-wrap items-end"):
                                inp_vol_g = ui.number("Volume", value=volume, min=0, max=100, step=1).props("outlined dense").classes("w-[90px]")
                                def _salvar_vol(mid=mid, v=inp_vol_g):
                                    ok, msg = filas.atualizar_midia(mid, volume=v.value)
                                    notificar(msg, type="positive" if ok else "negative")
                                    if ok:
                                        render_midia()
                                ui.button("Salvar vol", icon="save", on_click=_salvar_vol).props("dense color=primary").tooltip("Altura do som desta reprodução")
                                def _toggle(mid=mid, ativo=ativo):
                                    filas.set_midia_ativa(mid, not ativo)
                                    notificar("Mídia " + ("ativada" if not ativo else "desativada"), type="positive")
                                    render_midia()
                                def _excluir(mid=mid):
                                    ok, msg = filas.excluir_midia(mid, ator=usuario_logado)
                                    notificar(msg, type="positive" if ok else "negative")
                                    render_midia()
                                ui.button("Ativar" if not ativo else "Desativar", on_click=_toggle).props("dense outline")
                                ui.button("Excluir", icon="delete", on_click=_excluir).props("dense outline color=negative")
                        with ui.row().classes("gap-1"):
                            def _subir(mid=mid):
                                mids = [m[0] for m in filas.listar_midias() if not m[8]]
                                if mid in mids:
                                    idx = mids.index(mid)
                                    if idx > 0:
                                        mids[idx], mids[idx-1] = mids[idx-1], mids[idx]
                                        filas.reordenar_midias(mids)
                                        render_midia()
                            def _descer(mid=mid):
                                mids = [m[0] for m in filas.listar_midias() if not m[8]]
                                if mid in mids:
                                    idx = mids.index(mid)
                                    if idx < len(mids)-1:
                                        mids[idx], mids[idx+1] = mids[idx+1], mids[idx]
                                        filas.reordenar_midias(mids)
                                        render_midia()
                            ui.button(icon="arrow_upward", on_click=_subir).props("dense flat").tooltip("Mover para cima")
                            ui.button(icon="arrow_downward", on_click=_descer).props("dense flat").tooltip("Mover para baixo")

        render_midia()

        async def _on_upload(e):
            from mod_filas.telas import _ler_upload
            try:
                nome_arq, conteudo = await _ler_upload(e)
                if not conteudo:
                    notificar("Falha ao ler arquivo", type="negative")
                    return
                ext = os.path.splitext(nome_arq)[1].lower()
                tipo = filas.tipo_por_extensao(nome_arq)
                if not tipo:
                    notificar(f"Formato não suportado: {ext} (use mp3/wav/ogg/mp4/webm/jpg/png/webp)", type="negative")
                    return
                # sobe automaticamente e renomeia no servidor: datahora_global.ext
                nome_seguro = filas.nome_arquivo_midia(None, nome_arq)
                dest = os.path.join(PASTA_MIDIA, nome_seguro)
                os.makedirs(PASTA_MIDIA, exist_ok=True)
                with open(dest, "wb") as f:
                    f.write(conteudo)
                caminho = f"/midia_filas/{nome_seguro}"
                ok, msg = filas.adicionar_midia(nome_arq, tipo, caminho, arquivo_original=nome_arq, ator=usuario_logado)
                notificar(msg, type="positive" if ok else "negative")
                if ok:
                    render_midia()
            except Exception as ex:
                notificar(f"Erro no upload: {ex}", type="negative")

        from mod_filas.telas import _rejeitado
        ui.upload(label="Selecionar MP3/MP4/fotos — envia sozinho (global, só TV geral)", auto_upload=True, on_upload=_on_upload, on_rejected=_rejeitado, multiple=True).props("accept='.mp3,.wav,.ogg,.m4a,.mp4,.webm,.jpg,.jpeg,.png,.webp'").classes("w-full")

        with ui.row().classes("w-full gap-2 mt-2"):
            ui.button("Recarregar mídia", icon="refresh", on_click=render_midia).props("outline dense")
            ui.button("Preview TV", icon="tv", on_click=lambda: ui.navigate.to("/tv", new_tab=True)).props("outline dense color=primary")

    from mod_intranet.rotinas import painel_backup
    painel_backup(usuario_logado, "filas")
