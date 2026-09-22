"""Tela do módulo Filas — gestor de chamadas + TV com voz e mídia.

EN: Queue screen — multi-queue manager, sequential steps, TV with voice and media playlist.
"""

import sys
import os
import re
import inspect

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from nicegui import ui
from mod_intranet import autenticacao
from mod_intranet.aba_modulo import cabecalho
from mod_intranet.tema_modulo import ler_tema, notificar
from mod_intranet.ui_comum import botao
from mod_filas import bd_manipulador as filas

PASTA_MIDIA = filas.PASTA_MIDIA


def _pode_acessar(user_nome: str, perfil: str) -> bool:
    if perfil == "administrador_geral":
        return True
    try:
        return autenticacao.validar_acesso_modulo(user_nome, "filas")
    except Exception:
        return False


async def _ler_upload(e):
    """Lê (nome, bytes) do evento de upload — NiceGUI 3.x (e.file async) e legado (e.content)."""
    f = getattr(e, "file", None)
    if f is not None:
        nome = getattr(f, "filename", None) or getattr(f, "name", None) or "arquivo"
        nome = os.path.basename(nome) or "arquivo"
        read = getattr(f, "read", None)
        if callable(read):
            conteudo = read()
            if inspect.isawaitable(conteudo):
                conteudo = await conteudo
            return nome, conteudo or b""
    nome = getattr(e, "name", "arquivo")
    c = getattr(e, "content", None)
    if c is not None and hasattr(c, "read"):
        return nome, c.read() or b""
    return nome, b""


def _rejeitado(e=None):
    notificar("Arquivo rejeitado pelo navegador", type="negative")


async def _salvar_arquivo_midia(e, fila_id, user_nome, volume, duracao, slot, recarregar):
    """Upload AUTOMÁTICO ao selecionar: salva e renomeia no servidor (datahora_nomeFila.ext), só desta fila."""
    try:
        nome_arq, conteudo = await _ler_upload(e)
        if not conteudo:
            notificar("Falha ao ler arquivo", type="negative")
            return
        tipo = filas.tipo_por_extensao(nome_arq)
        if not tipo:
            notificar("Formato não suportado (use mp3/wav/ogg/mp4/webm/jpg/png/webp)", type="negative")
            return
        # sobe automaticamente e renomeia no servidor: datahora_nomeFila.ext
        nome_seguro = filas.nome_arquivo_midia(fila_id, nome_arq)
        dest = os.path.join(PASTA_MIDIA, nome_seguro)
        os.makedirs(PASTA_MIDIA, exist_ok=True)
        with open(dest, "wb") as f:
            f.write(conteudo)
        try:
            vol = int(float(volume if volume not in (None, "") else filas.VOLUME_AMBIENTE_PADRAO))
        except Exception:
            vol = filas.VOLUME_AMBIENTE_PADRAO
        try:
            dur = int(float(duracao or 8))
        except Exception:
            dur = 8
        try:
            sl = int(float(slot or 0))
        except Exception:
            sl = 0
        ok, msg = filas.adicionar_midia(nome_arq, tipo, f"/midia_filas/{nome_seguro}", arquivo_original=nome_arq, ator=user_nome, fila_id=fila_id, volume=vol, duracao=dur, slot=sl)
        notificar(msg, type="positive" if ok else "negative")
        if ok:
            recarregar()
    except Exception as ex:
        notificar(f"Erro no upload: {ex}", type="negative")


def bloco_midia_fila(fila_id: int, user_nome: str, recarregar):
    """Mídias da fila: upload mp3/mp4/foto + sequência (exibição) + volume. Reuso em /filas e /admin/filas."""
    with ui.expansion("Mídias desta fila — áudio, foto e vídeo (sequência + volume)", icon="perm_media").classes("w-full").style("min-width: 0"):
        with ui.row().classes("w-full items-center flex-wrap").style("gap: 0.5rem; min-width: 0"):
            _info_m = ui.icon("info_outline", size="16px").classes("text-grey-5").props('aria-label="Ajuda: mídias"')
            with _info_m:
                ui.tooltip("Itens com o MESMO número tocam juntos (ex: foto + áudio). Volume 0-100 (padrão 40) p/ áudio e vídeo. Duração = tempo REAL do áudio/vídeo; fotos dividem esse tempo (áudio 40s + 4 fotos = 10s cada); foto sozinha usa a duração configurada.").props("delay=1000")
        box_lista = ui.column().classes("w-full gap-2").style("min-width: 0")

        def _render():
            box_lista.clear()
            with box_lista:
                proprias = filas.listar_midias(fila_id=fila_id)
                if not proprias:
                    ui.label("Nenhuma mídia desta fila. Selecione abaixo — sobe sozinho e fica só nesta fila.").classes("text-caption text-grey-6 italic")
                _slot_atual = None
                for mid, nome, tipo, caminho, orig, ordem, ativo, criado, f_id, volume, duracao, slot, real, fundo in proprias:
                    if slot != _slot_atual:
                        _slot_atual = slot
                        ui.label(f"— Exibição {slot} (juntos) —").classes("text-caption font-bold text-primary")
                    src = f"/midia_filas/{os.path.basename(caminho)}"
                    with ui.card().classes("w-full p-2 gap-1").style("min-width: 0"):
                        _real_txt = f" • {real}s reais" if real else ""
                        _fundo_txt = " • FUNDO" if fundo else ""
                        ui.label(f"[{tipo}] {nome} • vol {volume} • {duracao}s{_real_txt}{_fundo_txt} • {'ativo' if ativo else 'inativo'}").classes("text-caption font-bold").style("min-width: 0; overflow-wrap: break-word")
                        if tipo == "audio":
                            ui.html(f"<audio controls style='width:100%;max-width:400px'><source src='{src}'></audio>", sanitize=False)
                        elif tipo == "video":
                            ui.html(f"<video controls style='width:100%;max-width:400px;max-height:180px;background:#111'><source src='{src}'></video>", sanitize=False)
                        else:
                            ui.image(src).classes("w-full max-w-[400px]")
                        with ui.row().classes("w-full flex-wrap items-end").style("gap: 0.25rem; min-width: 0"):
                            inp_vol = ui.number("Volume", value=volume, min=0, max=100, step=1).props("outlined dense").classes("w-[90px]")
                            with inp_vol:
                                ui.tooltip("Altura do som desta reprodução (padrão 40; na chamada cai à metade).").props("delay=1000")
                            _estado_vol = {"caixa": None} if tipo in ("audio", "video") else None
                            if tipo in ("audio", "video"):
                                def _alternar_vol(_st=_estado_vol):
                                    try:
                                        cx = _st["caixa"]
                                        if cx is not None:
                                            cx.visible = not cx.visible
                                    except Exception as ex:
                                        notificar(f"Erro ao abrir volume: {ex}", type="negative")
                                ui.button(icon="volume_up", on_click=_alternar_vol).props("dense flat").tooltip("Ajustar volume (abre o controle deslizante)").props('data-testid=filas-midia-som')
                            inp_dur = ui.number("Duração(s)", value=duracao, min=3, max=120, step=1).props("outlined dense").classes("w-[100px]")
                            with inp_dur:
                                ui.tooltip("Só vale p/ foto SOZINHA (com áudio ela divide o tempo real).").props("delay=1000")
                            inp_slot = ui.number("Exibição", value=slot, min=0, max=999, step=1).props("outlined dense").classes("w-[90px]")
                            with inp_slot:
                                ui.tooltip("Posição na sequência; mesmo número = juntos.").props("delay=1000")
                            def _salvar(mid=mid, v=inp_vol, d=inp_dur, s=inp_slot):
                                ok, msg = filas.atualizar_midia(mid, volume=v.value, duracao=d.value, slot=s.value)
                                notificar(msg, type="positive" if ok else "negative")
                                if ok:
                                    recarregar()
                            ui.button("Salvar", on_click=_salvar).props("dense color=primary").props('data-testid=filas-midia-salvar')
                            if tipo == "imagem":
                                def _fundo(mid=mid, fundo=fundo):
                                    ok, msg = filas.set_midia_fundo(mid, not fundo, ator=user_nome)
                                    notificar(msg, type="positive" if ok else "negative")
                                    recarregar()
                                ui.button("Fundo" if not fundo else "Tirar fundo", icon="wallpaper", on_click=_fundo).props("dense outline color=primary" if not fundo else "dense outline").tooltip("Foto permanente atrás de tudo na TV").props('data-testid=filas-midia-fundo')
                            def _toggle(mid=mid, ativo=ativo):
                                filas.set_midia_ativa(mid, not ativo)
                                notificar("Mídia " + ("ativada" if not ativo else "desativada"), type="positive")
                                recarregar()
                            def _excluir(mid=mid):
                                ok, msg = filas.excluir_midia(mid, ator=user_nome)
                                notificar(msg, type="positive" if ok else "negative")
                                recarregar()
                            ui.button("Ativar" if not ativo else "Desativar", on_click=_toggle).props("dense outline")
                            ui.button("Excluir", on_click=_excluir).props("dense outline color=negative")
                            if tipo in ("audio", "video") and _estado_vol is not None:
                                with ui.column().classes("w-full gap-0").style("min-width: 0") as _cx_vol:
                                    _rot_vol = ui.label(f"Volume: {volume}").classes("text-caption text-grey-7")
                                    def _ao_mover_vol(e, v=inp_vol, r=_rot_vol):
                                        try:
                                            nv = int(float(e.value))
                                        except Exception:
                                            return
                                        try:
                                            v.value = nv
                                        except Exception:
                                            pass
                                        try:
                                            r.text = f"Volume: {nv}"
                                        except Exception:
                                            pass
                                    ui.slider(min=0, max=100, step=1, value=volume, on_change=_ao_mover_vol).props("label label-always").classes("w-full max-w-[300px]")
                                _cx_vol.visible = False
                                _estado_vol["caixa"] = _cx_vol
                        with ui.row().classes("w-full flex-wrap").style("gap: 0.25rem; min-width: 0"):
                            def _subir(mid=mid):
                                ids = [m[0] for m in filas.listar_midias(fila_id=fila_id) if m[8] == fila_id]
                                if mid in ids:
                                    idx = ids.index(mid)
                                    if idx > 0:
                                        ids[idx], ids[idx - 1] = ids[idx - 1], ids[idx]
                                        filas.reordenar_midias(ids)
                                        recarregar()
                            def _descer(mid=mid):
                                ids = [m[0] for m in filas.listar_midias(fila_id=fila_id) if m[8] == fila_id]
                                if mid in ids:
                                    idx = ids.index(mid)
                                    if idx < len(ids) - 1:
                                        ids[idx], ids[idx + 1] = ids[idx + 1], ids[idx]
                                        filas.reordenar_midias(ids)
                                        recarregar()
                            ui.button(icon="arrow_upward", on_click=_subir).props("dense flat").tooltip("Antecipar na sequência")
                            ui.button(icon="arrow_downward", on_click=_descer).props("dense flat").tooltip("Adiar na sequência")

        with ui.row().classes("w-full flex-wrap items-end").style("gap: 0.5rem; min-width: 0"):
            up_vol = ui.number("Volume (padrão 40)", value=filas.VOLUME_AMBIENTE_PADRAO, min=0, max=100, step=1).props("outlined dense").classes("w-[110px]")
            with up_vol:
                ui.tooltip("Altura do som (padrão 40; na chamada cai à metade).").props("delay=1000")
            up_dur = ui.number("Duração foto (s)", value=8, min=3, max=120, step=1).props("outlined dense").classes("w-[130px]")
            with up_dur:
                ui.tooltip("Só vale p/ foto SOZINHA (com áudio ela divide o tempo real).").props("delay=1000")
            up_slot = ui.number("Exibição", value=0, min=0, max=999, step=1).props("outlined dense").classes("w-[90px]")
            with up_slot:
                ui.tooltip("Posição na sequência; mesmo número = juntos.").props("delay=1000")
        ui.upload(label="Selecionar MP3 / MP4 / fotos — envia sozinho para esta fila", auto_upload=True,
                  on_upload=lambda e: _salvar_arquivo_midia(e, fila_id, user_nome, up_vol.value, up_dur.value, up_slot.value, recarregar),
                  on_rejected=lambda e: _rejeitado(e),
                  multiple=True).props("accept='.mp3,.wav,.ogg,.m4a,.mp4,.webm,.jpg,.jpeg,.png,.webp'").classes("w-full")
        _render()


PRIO_LABEL = {"comum": "Comum", "gestante": "Gestante", "idoso": "Idoso", "deficiente": "Deficiente"}
PRIO_COR = {"comum": "grey", "gestante": "pink", "idoso": "amber", "deficiente": "blue"}
MANCHESTER_LABEL = {"": "—", "vermelho": "Vermelho", "laranja": "Laranja", "amarelo": "Amarelo", "verde": "Verde", "azul": "Azul"}
# Fundo/contorno de alerta no nome (Manchester domina a demografia)
MANCHESTER_STYLE = {
    "vermelho": "background:#c62828;color:#fff;border-radius:6px;padding:2px 8px;font-weight:bold;",
    "laranja": "background:#ef6c00;color:#fff;border-radius:6px;padding:2px 8px;font-weight:bold;",
    "amarelo": "background:#fdd835;color:#212121;border-radius:6px;padding:2px 8px;font-weight:bold;",
    "verde": "background:#2e7d32;color:#fff;border-radius:6px;padding:2px 8px;font-weight:bold;",
    "azul": "background:#1565c0;color:#fff;border-radius:6px;padding:2px 8px;font-weight:bold;",
}


def _estilo_manchester(cor: str) -> str:
    return MANCHESTER_STYLE.get((cor or "").lower(), "")


def _fundo_rodape_escuro(cor_botao: str) -> str:
    """Fundo escuro do rodapé de notícias da TV a partir da cor do tema.

    EN: Dark TV news footer background derived from the module theme color.
    Usa a cor do tema quando ela já é escura (luminância < 0,45); quando o
    tema está claro, cai em #1b1b1b para manter o contraste com o texto claro.
    """
    cor = (cor_botao or "").strip() or "#000000"
    m = re.match(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$", cor)
    if not m:
        return "#1b1b1b"
    h = m.group(1)
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        r = int(h[0:2], 16) / 255
        g = int(h[2:4], 16) / 255
        b = int(h[4:6], 16) / 255
        lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
    except Exception:
        return "#1b1b1b"
    if lum < 0.45:
        return f"#{h.lower()}"
    return "#1b1b1b"


def bloco_nomes_fila(fila_id: int, user_nome: str, recarregar):
    """Lista ÚNICA da fila (só visível nela): importa, ajusta prioridade e envia p/ outra fila da mesma TV."""
    with ui.expansion("Nomes para chamar (lista única desta fila)", icon="format_list_numbered").classes("w-full").style("min-width: 0"):
        _info_n = ui.icon("info_outline", size="16px").classes("text-grey-5").props('aria-label="Ajuda: nomes"')
        with _info_n:
            ui.tooltip("Ex: maria #gestante #vermelho #recepcao. A ordem é respeitada sozinha: cor primeiro, depois grupo, depois chegada. Etapa na tag ou no seletor fixa onde o nome nasce.").props("delay=1000")
        # destinos: outras filas da MESMA tv
        try:
            _f = filas.obter_fila(fila_id)
            _grupo = _f[12] if _f and len(_f) > 12 else ""
        except Exception:
            _grupo = ""
        destinos = {}
        if _grupo:
            try:
                for _oid in filas.ids_do_grupo(_grupo):
                    if _oid == fila_id:
                        continue
                    _of = filas.obter_fila(_oid)
                    if _of:
                        destinos[f"{_of[1]}"] = _oid
            except Exception:
                pass
        box_n = ui.column().classes("w-full gap-1").style("min-width: 0")

        def _render():
            box_n.clear()
            with box_n:
                pend = filas.listar_nomes(fila_id, somente_pendentes=True)
                todos = filas.listar_nomes(fila_id)
                usados = len(todos) - len(pend)
                ui.label(f"{len(pend)} pendente(s) • {usados} já chamado(s)").classes("text-caption font-bold")
                if destinos and pend:
                    with ui.row().classes("w-full flex-wrap items-end").style("gap: 0.5rem; min-width: 0"):
                        sel_dest = ui.select(list(destinos.keys()), label="Enviar para (mesma TV)").props("outlined dense").classes("flex-1 min-w-[160px]")
                        def _todos():
                            if not sel_dest.value:
                                notificar("Escolha a fila de destino", type="warning")
                                return
                            ok, msg = filas.transferir_todos(fila_id, destinos[sel_dest.value], ator=user_nome)
                            notificar(msg, type="positive" if ok else "negative")
                            recarregar()
                        ui.button("Enviar todos", icon="forward", on_click=_todos).props("dense outline").props('data-testid=filas-transferir-todos')
                for nid, nome, ordem, usado, prio, manch, etapa_n in pend[:50]:
                    with ui.row().classes("w-full items-center flex-wrap").style("gap: 0.5rem; min-width: 0"):
                        ui.label(f"{ordem}. {nome}").classes("text-caption flex-1").style("min-width: 0; " + (_estilo_manchester(manch) or ""))
                        if etapa_n:
                            ui.label(f"→ {etapa_n}").classes("text-caption text-primary")
                        sel_p = ui.select(list(PRIO_LABEL.values()), value=PRIO_LABEL.get(prio or "comum", "Comum")).props("outlined dense").classes("w-[130px]")
                        def _trocar(nid=nid, sel=sel_p):
                            inv = {v: k for k, v in PRIO_LABEL.items()}
                            ok, msg = filas.definir_prioridade_nome(nid, inv.get(sel.value, "comum"), ator=user_nome)
                            notificar(msg, type="positive" if ok else "negative")
                            recarregar()
                        ui.button(icon="save", on_click=_trocar).props("dense flat").tooltip("Salvar grupo")
                        sel_m = ui.select(list(MANCHESTER_LABEL.values()), value=MANCHESTER_LABEL.get(manch or "", "—")).props("outlined dense").classes("w-[120px]")
                        def _trocar_m(nid=nid, sel=sel_m):
                            invm = {v: k for k, v in MANCHESTER_LABEL.items()}
                            ok, msg = filas.definir_manchester_nome(nid, invm.get(sel.value, ""), ator=user_nome)
                            notificar(msg, type="positive" if ok else "negative")
                            recarregar()
                        ui.button(icon="healing", on_click=_trocar_m).props("dense flat color=negative").tooltip("Salvar cor")
                        try:
                            _ets = [e[3] for e in filas.listar_etapas(fid)]
                        except Exception:
                            _ets = []
                        sel_e = ui.select(["(geral)"] + _ets, value=etapa_n if etapa_n in _ets else "(geral)").props("outlined dense").classes("w-[140px]")
                        def _trocar_e(nid=nid, sel=sel_e):
                            val = sel.value or ""
                            ok, msg = filas.definir_etapa_nome(nid, "" if val == "(geral)" else val, ator=user_nome)
                            notificar(msg, type="positive" if ok else "negative")
                            recarregar()
                        ui.button(icon="meeting_room", on_click=_trocar_e).props("dense flat color=primary").tooltip("Salvar etapa")
                        if destinos:
                            def _env(nid=nid, sel=sel_dest):
                                if not sel.value:
                                    notificar("Escolha a fila de destino acima", type="warning")
                                    return
                                ok, msg = filas.transferir_nome(nid, destinos[sel.value], ator=user_nome)
                                notificar(msg, type="positive" if ok else "negative")
                                recarregar()
                            ui.button(icon="forward", on_click=_env).props("dense flat color=primary").tooltip("Enviar este nome p/ fila de destino")
                        def _rm(nid=nid):
                            filas.remover_nome(nid, ator=user_nome)
                            recarregar()
                        ui.button(icon="delete", on_click=_rm).props("dense flat color=negative").tooltip("Remover nome")
                if len(pend) > 50:
                    ui.label(f"... e mais {len(pend) - 50}").classes("text-caption text-grey-6")
                if todos:
                    with ui.row().classes("w-full flex-wrap").style("gap: 0.25rem; min-width: 0"):
                        def _limpar():
                            ok, msg = filas.limpar_nomes(fila_id, ator=user_nome)
                            notificar(msg, type="positive" if ok else "negative")
                            recarregar()
                        ui.button("Apagar lista", on_click=_limpar).props("dense outline color=negative")

        with ui.row().classes("w-full flex-wrap items-end").style("gap: 0.5rem; min-width: 0"):
            txt_nomes = ui.textarea("Colar nomes (um por linha + #prioridade)", placeholder="Maria #gestante\nZé #idoso\nAna #deficiente\nBeto").props("outlined dense").classes("flex-1 min-w-[200px]").props('data-testid=filas-importar-texto')
            chk_sub = ui.checkbox("Substitui. lista atual", value=False)
            with chk_sub:
                ui.tooltip("Marcado apaga a lista atual antes de importar; desmarcado bloqueia se já houver lista.").props("delay=1000")
            def _importar_colado():
                texto_colado = txt_nomes.value or ""
                ok_s, nome_s = filas.salvar_lista_nomes(fila_id, texto_colado)
                if not ok_s:
                    notificar(nome_s, type="negative")
                    return
                ok, msg = filas.importar_nomes(fila_id, texto_colado, ator=user_nome, substituir=chk_sub.value)
                notificar(f"{msg} (lista salva como {nome_s})", type="positive" if ok else "negative")
                if ok:
                    txt_nomes.value = ""
                    recarregar()
            ui.button("Importar", on_click=_importar_colado).props("color=primary").props('data-testid=filas-importar-submit')

        async def _on_txt(e):
            nome_arq, conteudo = await _ler_upload(e)
            texto = (conteudo or b"").decode("utf-8", errors="replace")
            if not texto.strip():
                notificar("nomes.txt vazio ou ilegível", type="negative")
                return
            ok_s, nome_s = filas.salvar_lista_nomes(fila_id, conteudo)
            if not ok_s:
                notificar(nome_s, type="negative")
                return
            ok, msg = filas.importar_nomes(fila_id, texto, ator=user_nome)
            notificar(f"{msg} ({nome_arq} salvo como {nome_s})", type="positive" if ok else "negative")
            if ok:
                recarregar()

        ui.upload(label="Selecionar nomes.txt — envia sozinho", auto_upload=True, on_upload=_on_txt, on_rejected=_rejeitado, multiple=False).props("accept='.txt'").classes("w-full")
        _render()


def bloco_etapas(fid: int, nome_fila: str, tv_grupo: str, user_nome: str, recarregar):
    """Painel por etapa/sala: quem está na sala pede o próximo, vincula nome e ajusta Manchester.

    Qualquer atendente com acesso pode usar (não só dono/admin). Reuso em /filas e /admin/filas.
    """
    from urllib.parse import quote as _q
    with ui.expansion("Por etapa/sala — próximo, nome e cor (qualquer atendente)", icon="meeting_room").classes("w-full").style("min-width: 0"):
        _info_e = ui.icon("info_outline", size="16px").classes("text-grey-5").props('aria-label="Ajuda: etapas"')
        with _info_e:
            ui.tooltip("Cada etapa é uma subfila de sala. A sala pede o próximo (reanuncia o mais antigo aguardando ou chama quem está marcado para ela), vincula nome à senha do papelzinho e ajusta a cor a qualquer hora. TV replicada só da etapa.").props("delay=1000")
        try:
            etapas = filas.listar_etapas(fid)
        except Exception:
            etapas = []
        for _eid, _efid, _ordem, _enome, _eguiche, _eativo in etapas:
            try:
                espera = filas.espera_etapa(fid, _enome)
            except Exception:
                espera = []
            if tv_grupo:
                tv_url = f"/tv?grupo={tv_grupo}&etapa={_q(_enome)}"
            else:
                tv_url = f"/tv/{fid}?etapa={_q(_enome)}"
            with ui.card().classes("w-full p-3 gap-2").style("min-width: 0"):
                with ui.row().classes("w-full items-center flex-wrap").style("gap: 0.5rem; min-width: 0"):
                    ui.badge(f"{_ordem}. {_enome} ({_eguiche or '—'})", color="primary")
                    ui.label(f"{len(espera)} aguardando").classes("text-caption text-grey-6 flex-1")
                    def _prox(fn=fid, en=_enome):
                        ok, msg = filas.proximo_da_etapa(fn, en, ator=user_nome)
                        notificar(f"Chamando {msg}" if ok else msg, type="positive" if ok else "warning")
                        recarregar()
                    botao("Próximo", icone="campaign", on_click=_prox, variante="primario", chave_modulo="filas").props('data-testid=filas-etapa-proximo')
                    botao(f"TV {_enome}", icone="tv", on_click=lambda u=tv_url: ui.navigate.to(u, new_tab=True), variante="contorno", chave_modulo="filas")
                for item in espera[:10]:
                    with ui.row().classes("w-full items-center flex-wrap").style("gap: 0.5rem; min-width: 0"):
                        ui.label(f"{item['senha']}").classes("font-bold").style(_estilo_manchester(item["manchester"]) or "")
                        ui.label(item["paciente"] or "sem nome").classes("text-caption flex-1").style(_estilo_manchester(item["manchester"]) or "")
                        def _dlg_nome(senha=item["senha"], atual=item["paciente"]):
                            with ui.dialog() as dlg, ui.card():
                                ui.label(f"Nome para a senha {senha}").classes("font-bold")
                                inp = ui.input("Paciente", value=atual or "").props("outlined dense").classes("w-full")
                                with ui.row().classes("w-full justify-end flex-wrap").style("gap: 0.5rem; min-width: 0"):
                                    ui.button("Cancelar", on_click=dlg.close).props("flat")
                                    def _sv(fn=fid, s=senha, i=inp):
                                        ok, msg = filas.definir_nome_senha(fn, s, i.value, ator=user_nome)
                                        notificar(msg, type="positive" if ok else "negative")
                                        dlg.close()
                                        recarregar()
                                    ui.button("Salvar", on_click=_sv).props("color=primary")
                            dlg.open()
                        ui.button(icon="person_add", on_click=_dlg_nome).props("dense flat color=primary").tooltip("Vincular nome à senha")
                        selm = ui.select(list(MANCHESTER_LABEL.values()), value=MANCHESTER_LABEL.get(item["manchester"] or "", "—")).props("outlined dense").classes("w-[120px]")
                        def _svm(fn=fid, s=item["senha"], sel=selm):
                            invm = {v: k for k, v in MANCHESTER_LABEL.items()}
                            ok, msg = filas.definir_manchester_senha(fn, s, invm.get(sel.value, ""), ator=user_nome)
                            notificar(msg, type="positive" if ok else "negative")
                            recarregar()
                        ui.button(icon="healing", on_click=_svm).props("dense flat color=negative").tooltip("Salvar cor da senha")
                if len(espera) > 10:
                    ui.label(f"... e mais {len(espera) - 10} aguardando").classes("text-caption text-grey-6")


def dialogo_editar_fila(fid: int, user_nome: str, pode_liberar: bool, recarregar, atualizar_grupos=None):
    """Editar fila: volta e altera tudo que foi definido na criação. Reuso em /filas e /admin/filas."""
    fila = filas.obter_fila(fid)
    if not fila:
        notificar("Fila não encontrada", type="negative")
        return
    _fid, _nome, _senha, _status, _guiche, _data, _end, _desc, _pref, _dono, _si, _sf, _grupo = fila
    try:
        ex = filas.obter_extras_fila(fid)
    except Exception:
        ex = {}
    with ui.dialog() as dlg, ui.card().classes("w-full max-w-[760px] p-4 gap-3"):
        ui.label(f"Editar fila — {_nome}").classes("font-bold text-h6")
        with ui.row().classes("w-full flex-wrap").style("gap: 0.5rem; min-width: 0"):
            e_nome = ui.input("Nome da fila", value=_nome or "").props("outlined dense").classes("flex-1 min-w-[160px]")
            with e_nome:
                ui.tooltip("Nome da fila (ex: Ambulatório). Aparece na TV e nos painéis.").props("delay=1000")
        with ui.row().classes("w-full flex-wrap items-end").style("gap: 0.5rem; min-width: 0"):
            e_pref = ui.input("Prefixo", value=_pref or "A").props("outlined dense").classes("w-[80px]")
            with e_pref:
                ui.tooltip("Letras/números no início da senha (ex: A gera A001).").props("delay=1000")
            e_si = ui.input("Início", value=str(_si or 1)).props("outlined dense type=number").classes("w-[90px]")
            with e_si:
                ui.tooltip("Número da primeira senha distribuída.").props("delay=1000")
            e_sf = ui.input("Fim (0=∞)", value=str(_sf or 0)).props("outlined dense type=number").classes("w-[90px]")
            with e_sf:
                ui.tooltip("Último número da sequência (0 = infinito, nunca reinicia).").props("delay=1000")
            e_guiche = ui.input("Guichê base", value=_guiche or "01").props("outlined dense").classes("w-[90px]")
            with e_guiche:
                ui.tooltip("Guichê/sala base das chamadas desta fila.").props("delay=1000")
        with ui.row().classes("w-full flex-wrap items-end").style("gap: 0.5rem; min-width: 0"):
            try:
                _gs = filas.listar_grupos_tv()
            except Exception:
                _gs = []
            _ops = ([_grupo] if _grupo else ["(TV isolada)"]) + [g for g in _gs if g != (_grupo or "")] + ["(nova abaixo)"]
            e_sel = ui.select(_ops, label="TV grupo em uso").props("outlined dense").classes("flex-1 min-w-[180px]")
            with e_sel:
                ui.tooltip("Grupos em uso: escolha para dividir a mesma TV entre filas.").props("delay=1000")
            e_novo = ui.input("Nova TV grupo", placeholder="ex: recepcao-2").props("outlined dense").classes("flex-1 min-w-[180px]")
            with e_novo:
                ui.tooltip("Novo grupo (só letras/números/hífen). Vazio = TV isolada.").props("delay=1000")
        with ui.row().classes("w-full flex-wrap items-center").style("gap: 0.75rem; min-width: 0"):
            ui.label("Falar:").classes("text-caption font-bold")
            v_n = ui.checkbox("Nome", value=bool(ex.get("voz_nome", 1)))
            with v_n:
                ui.tooltip("Fala o nome do paciente na chamada.").props("delay=1000")
            v_s = ui.checkbox("Senha", value=bool(ex.get("voz_senha", 1)))
            with v_s:
                ui.tooltip("Fala o número da senha na chamada.").props("delay=1000")
            v_d = ui.checkbox("Destino", value=bool(ex.get("voz_destino", 1)))
            with v_d:
                ui.tooltip("Fala a sala/etapa de destino.").props("delay=1000")
            v_g = ui.checkbox("Guichê", value=bool(ex.get("voz_guiche", 1)))
            with v_g:
                ui.tooltip("Fala o gui.hê/sala da chamada.").props("delay=1000")
            v_f = ui.checkbox("Fila", value=bool(ex.get("voz_fila", 1)))
            with v_f:
                ui.tooltip("Fala o nome da fila na chamada.").props("delay=1000")
            v_h = ui.checkbox("Hora cheia/meia", value=bool(ex.get("voz_hora", 1)))
            with v_h:
                ui.tooltip("Anuncia a hora cheia e meia quando ociosa.").props("delay=1000")
            v_r = ui.number("Repetir", value=ex.get("voz_repetir", 0), min=0, max=10, step=1).props("outlined dense").classes("w-[90px]")
            with v_r:
                ui.tooltip("Quantas vezes a chamada repete sozinha (0 = fala 1x).").props("delay=1000")
            v_i = ui.number("Intervalo(s)", value=ex.get("voz_intervalo", 2), min=1, max=60, step=1).props("outlined dense").classes("w-[100px]")
            with v_i:
                ui.tooltip("Segundos entre a chamada e cada repetição.").props("delay=1000")
        e_ordem = ui.input("Ordem da fala", value=ex.get("voz_ordem") or "fila,senha,nome,destino,guiche").props("outlined dense").classes("w-full")
        with e_ordem:
            ui.tooltip("Sequência dos textos (ex: senha,nome). Campos: fila,senha,nome,destino,guiche.").props("delay=1000")
        with ui.expansion("Textos da TV", icon="tv").classes("w-full").style("min-width: 0"):
            with ui.row().classes("w-full items-center flex-wrap").style("gap: 0.5rem; min-width: 0"):
                _info_tt = ui.icon("info_outline", size="16px").classes("text-grey-5").props('aria-label="Ajuda: textos da TV"')
                with _info_tt:
                    ui.tooltip("Textos do cabeçalho e rodapé da TV. Vazio usa o padrão.").props("delay=1000")
            t_t = ui.input("Título", value=ex.get("tv_titulo") or "").props("outlined dense").classes("w-full").style("min-width: 0")
            with t_t:
                ui.tooltip("Título no topo da TV (vazio = padrão)." ).props("delay=1000")
            t_s = ui.input("Subtítulo", value=ex.get("tv_subtitulo") or "").props("outlined dense").classes("w-full").style("min-width: 0")
            with t_s:
                ui.tooltip("Linha abaixo do título (vazio = fila/grupo)." ).props("delay=1000")
            t_a = ui.input("Texto ociosa", value=ex.get("tv_aguardando") or "AGUARDE CHAMADA").props("outlined dense").classes("w-full").style("min-width: 0")
            with t_a:
                ui.tooltip("Exibido na lateral quando não há chamada.").props("delay=1000")
            t_l = ui.input("Legenda mídia", value=ex.get("tv_midia_legenda") or "").props("outlined dense").classes("w-full").style("min-width: 0")
            with t_l:
                ui.tooltip("Legenda curta ao lado do cabeçalho da TV.").props("delay=1000")
            t_n = ui.input("Título notícias", value=ex.get("tv_noticias_titulo") or "Notícias").props("outlined dense").classes("w-full").style("min-width: 0")
            with t_n:
                ui.tooltip("Título do rodapé de notícias da TV.").props("delay=1000")

        def _grupo_final():
            digitado = (e_novo.value or "").strip()
            if digitado:
                return digitado
            s = e_sel.value or ""
            if s in ("(TV isolada)", "(nova abaixo)"):
                return ""
            return s

        with ui.row().classes("w-full justify-end flex-wrap").style("gap: 0.5rem; min-width: 0"):
            ui.button("Cancelar", on_click=dlg.close).props("flat")
            def _salvar():
                try:
                    rep = int(float(v_r.value or 0))
                except Exception:
                    rep = 0
                try:
                    interv = int(float(v_i.value or 2))
                except Exception:
                    interv = 2
                ok, msg = filas.atualizar_fila(fid, nome=e_nome.value, prefixo=e_pref.value, guiche=e_guiche.value, senha_inicio=e_si.value, senha_fim=e_sf.value, tv_grupo=_grupo_final(), ator=user_nome, voz_nome=v_n.value, voz_senha=v_s.value, voz_destino=v_d.value, voz_guiche=v_g.value, voz_fila=v_f.value, voz_hora=v_h.value, voz_ordem=e_ordem.value, voz_repetir=rep, voz_intervalo=interv, tv_titulo=t_t.value, tv_subtitulo=t_s.value, tv_aguardando=t_a.value, tv_midia_legenda=t_l.value, tv_noticias_titulo=t_n.value)
                notificar(msg, type="positive" if ok else "negative")
                if ok:
                    dlg.close()
                    if atualizar_grupos:
                        try:
                            atualizar_grupos()
                        except Exception:
                            pass
                    recarregar()
            ui.button("Salvar", icon="save", on_click=_salvar).props("color=primary")

        # liberar acesso: buscar cadastrados na gestão de usuários (dono/admin)
        if pode_liberar:
            ui.separator()
            bloco_liberar_acesso(fid, user_nome, recarregar)
    dlg.open()


def bloco_liberar_acesso(fid: int, user_nome: str, recarregar):
    """Buscar usuários cadastrados (ativos) e chamá-los para a fila + lista de liberados. Reuso no Editar e no Acesso."""
    ui.label("Liberar acesso a esta fila — pesquise quem já usa o sistema e chame").classes("text-caption font-bold")
    box_lib = ui.column().classes("w-full gap-1")

    def _render_lib():
        box_lib.clear()
        with box_lib:
            atual = filas.listar_acessos(fid)
            if not atual:
                ui.label("Só você (dono) + admins.").classes("text-caption text-grey-6 italic")
            for un, dt in atual:
                with ui.row().classes("w-full items-center flex-wrap").style("gap: 0.5rem; min-width: 0"):
                    ui.label(un).classes("text-caption flex-1").style("min-width: 0")
                    def _rm(un=un):
                        ok, msg = filas.remover_acesso(fid, un, ator=user_nome)
                        notificar(msg, type="positive" if ok else "negative")
                        _render_lib()
                        recarregar()
                    ui.button(icon="delete", on_click=_rm).props("dense flat color=negative").tooltip("Remover acesso")

    with ui.row().classes("w-full flex-wrap items-end").style("gap: 0.5rem; min-width: 0"):
        inp_busca = ui.input("Buscar usuário cadastrado", placeholder="login ou nome").props("outlined dense").classes("flex-1 min-w-[180px]")
        box_res = ui.column().classes("w-full gap-1")
        def _buscar():
            box_res.clear()
            termo = (inp_busca.value or "").strip().lower()
            if len(termo) < 2:
                with box_res:
                    ui.label("Digite ao menos 2 letras.").classes("text-caption text-grey-6")
                return
            try:
                from mod_gest_cad_usuario.bd_manipulador import listar_usuarios as _lu
                users = _lu(filtro_ativo=True) or []
            except Exception:
                users = []
            cand = [u for u in users if termo in (u[1] or "").lower() or termo in (u[9] or "").lower()][:10]
            with box_res:
                if not cand:
                    ui.label("Nenhum usuário ativo encontrado.").classes("text-caption text-grey-6 italic")
                for u in cand:
                    with ui.row().classes("w-full items-center flex-wrap").style("gap: 0.5rem; min-width: 0"):
                        ui.label(f"{u[1]} — {u[9] or ''}").classes("text-caption flex-1").style("min-width: 0")
                        def _lib(un=u[1]):
                            ok, msg = filas.liberar_acesso(fid, un, ator=user_nome)
                            notificar(msg, type="positive" if ok else "negative")
                            _render_lib()
                            recarregar()
                        ui.button("Chamar", icon="person_add", on_click=_lib).props("dense color=primary").tooltip(f"Chamar {u[1]} para esta fila").props('data-testid=filas-acesso-chamar')
        ui.button("Buscar", icon="search", on_click=_buscar).props("dense outline").props('data-testid=filas-acesso-buscar')
    _render_lib()


def dialogo_acesso_fila(fid: int, user_nome: str, recarregar):
    """Diálogo focado: chamar usuários para a fila. Atalho do botão Acesso no card."""
    fila = filas.obter_fila(fid)
    with ui.dialog() as dlg, ui.card().classes("w-full max-w-[560px] p-4 gap-3"):
        ui.label(f"Acesso — {fila[1] if fila else ''}").classes("font-bold text-h6")
        bloco_liberar_acesso(fid, user_nome, recarregar)
        with ui.row().classes("w-full justify-end"):
            ui.button("Fechar", on_click=dlg.close).props("flat")
    dlg.open()


def bloco_controle_tv(chave: str, rotulo: str, fila_ids=None):
    """Edição: vê o que está reproduzindo + pausa/avança/retorna. Na TV não há controles."""
    with ui.expansion(f"Controle da TV — {rotulo} (o que está tocando + pausar/avançar/retornar)", icon="tune").classes("w-full").style("min-width: 0"):
        with ui.row().classes("w-full items-center flex-wrap").style("gap: 0.5rem; min-width: 0"):
            _info_tv = ui.icon("info_outline", size="16px").classes("text-grey-5").props('aria-label="Ajuda: controle da TV"')
            with _info_tv:
                ui.tooltip("Comandos remotos para a TV (pausar/avançar/retornar). Na TV não há botões — só aqui na edição.").props("delay=1000")
            lbl = ui.label("Lendo estado da TV...").classes("text-caption font-bold").style("min-width: 0")
        with ui.row().classes("w-full flex-wrap").style("gap: 0.25rem; min-width: 0"):
            def _cmd(c):
                filas.enviar_comando_tv(chave, c)
                notificar(f"Comando '{c}' enviado à TV", type="positive")
            ui.button("Pausar", icon="pause", on_click=lambda: _cmd("pausar")).props("dense outline").props('data-testid=filas-tv-pausar')
            ui.button("Retomar", icon="play_arrow", on_click=lambda: _cmd("retomar")).props("dense outline color=primary").props('data-testid=filas-tv-retomar')
            ui.button("Retornar", icon="skip_previous", on_click=lambda: _cmd("anterior")).props("dense outline").props('data-testid=filas-tv-retornar')
            ui.button("Avançar", icon="skip_next", on_click=lambda: _cmd("proximo")).props("dense outline").props('data-testid=filas-tv-avancar')

        def _poll():
            try:
                est = filas.obter_estado_tv(chave)
                midias = filas.listar_midias(somente_ativas=True)
                if fila_ids is not None:
                    midias = [m for m in midias if m[8] in fila_ids]
                tocando = [m for m in midias if m[11] == est["slot_atual"]]
                nomes = ", ".join(f"{m[1]} [{m[2]}]" for m in tocando[:6]) or "nenhuma mídia (só chamadas)"
                lbl.text = f"{'⏸ PAUSADA' if est['pausado'] else '▶ reproduzindo'} • exibição {est['slot_atual']}: {nomes}"
            except Exception:
                pass

        _poll()
        ui.timer(5.0, _poll)


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

        # Cadastro de fila — recolhível: uma linha; abre para criar, ou carrega fila ao Editar
        edicao = {"fid": None}
        with ui.expansion("Cadastro de fila", icon="add").classes("w-full").style("min-width: 0").props('data-testid=filas-cadastro') as exp_cad:
            with ui.row().classes("w-full items-center flex-wrap").style("gap: 0.5rem; min-width: 0"):
                _info_cad = ui.icon("info_outline", size="16px").classes("text-grey-5").props('aria-label="Ajuda: cadastro de fila"')
                with _info_cad:
                    ui.tooltip("Crie uma fila por local. Para editar, use Editar no card — o painel abre sozinho; Salvar confirma, Cancelar fecha e limpa.").props("delay=1000")
                lbl_modo = ui.label("").classes("text-caption text-primary font-bold").style("min-width: 0")
            with ui.row().classes("w-full flex-wrap items-end").style("gap: 0.5rem; min-width: 0"):
                inp_nome = ui.input("Nome da fila *", placeholder="Ambulatório").props("outlined dense").classes("flex-1 min-w-[160px]").props('data-testid=filas-campo-nome')
                with inp_nome:
                    ui.tooltip("Nome da fila (ex: Ambulatório). Aparece na TV e nos painéis.").props("delay=1000")
                inp_pref = ui.input("Prefixo", placeholder="A").props("outlined dense").classes("w-[80px]")
                with inp_pref:
                    ui.tooltip("Letras/números no início da senha (ex: A gera A001).").props("delay=1000")
                inp_inicio = ui.input("Início", placeholder="1").props("outlined dense type=number").classes("w-[90px]")
                with inp_inicio:
                    ui.tooltip("Número da primeira senha distribuída.").props("delay=1000")
                inp_fim = ui.input("Fim (0=∞)", placeholder="0").props("outlined dense type=number").classes("w-[100px]")
                with inp_fim:
                    ui.tooltip("Último número da sequência (0 = infinito, nunca reinicia).").props("delay=1000")
                inp_inicio.value = "1"
                inp_fim.value = "0"
            # TV grupo lado a lado: em uso + novo
            with ui.row().classes("w-full flex-wrap items-end").style("gap: 0.5rem; min-width: 0"):
                inp_guiche = ui.input("Guichê base", placeholder="01").props("outlined dense").classes("w-[90px]")
                with inp_guiche:
                    ui.tooltip("Guichê/sala base das chamadas desta fila.").props("delay=1000")
                sel_grupo = ui.select([], label="TV grupo em uso").props("outlined dense").classes("flex-1 min-w-[180px]")
                with sel_grupo:
                    ui.tooltip("Grupos em uso: escolha para dividir a mesma TV entre filas.").props("delay=1000")
                inp_grupo_novo = ui.input("Nova TV grupo (ou vazio=isolada)", placeholder="ex: recepcao-2").props("outlined dense").classes("flex-1 min-w-[200px]").props('data-testid=filas-campo-tv-grupo')
                with inp_grupo_novo:
                    ui.tooltip("Novo grupo (só letras/números/hífen, ex: recepcao-2). Vazio = TV isolada só desta fila.").props("delay=1000")
            # TV grupo: seletor + novo (validação de slug no backend)

            def _atualizar_grupos():
                try:
                    grupos = filas.listar_grupos_tv()
                except Exception:
                    grupos = []
                opcoes = ["(TV isolada / nova abaixo)"] + grupos
                try:
                    sel_grupo.options = opcoes
                except Exception:
                    pass
                if not sel_grupo.value:
                    sel_grupo.value = opcoes[0]
                return grupos

            _atualizar_grupos()
            # Voz inline: falar + ordem + repetir + intervalo na mesma linha
            with ui.row().classes("w-full flex-wrap items-center").style("gap: 0.75rem; min-width: 0"):
                ui.label("Falar na TV:").classes("text-caption font-bold").style("min-width: 0")
                chk_senha = ui.checkbox("Senha", value=True)
                with chk_senha:
                    ui.tooltip("Fala o número da senha na chamada.").props("delay=1000")
                chk_nome = ui.checkbox("Nome", value=True)
                with chk_nome:
                    ui.tooltip("Fala o nome do paciente na chamada.").props("delay=1000")
                chk_dest = ui.checkbox("Destino", value=True)
                with chk_dest:
                    ui.tooltip("Fala a sala/etapa de destino.").props("delay=1000")
                chk_guiche = ui.checkbox("Guichê", value=True)
                with chk_guiche:
                    ui.tooltip("Fala o gui.hê/sala da chamada.").props("delay=1000")
                chk_fila = ui.checkbox("Fila", value=True)
                with chk_fila:
                    ui.tooltip("Fala o nome da fila na chamada.").props("delay=1000")
                chk_hora = ui.checkbox("Hora cheia/meia", value=True)
                with chk_hora:
                    ui.tooltip("Anuncia a hora cheia e meia quando ociosa.").props("delay=1000")
                inp_ordem = ui.input("Ordem da fala", value="fila,senha,nome,destino,guiche").props("outlined dense").classes("flex-1 min-w-[220px]").style("min-width: 0").props('data-testid=filas-campo-ordem-fala')
                with inp_ordem:
                    ui.tooltip("Quais textos e em que sequência (ex: senha,nome para só senha+nome; nome,senha para nome primeiro). Campos: fila,senha,nome,destino,guiche.").props("delay=1000")
                num_rep = ui.number("Repetir chamada", value=0, min=0, max=10, step=1).props("outlined dense").classes("w-[130px]")
                with num_rep:
                    ui.tooltip("Quantas vezes a chamada repete sozinha após o intervalo (0 = fala 1x).").props("delay=1000")
                num_int = ui.number("Intervalo (s)", value=2, min=1, max=60, step=1).props("outlined dense").classes("w-[120px]")
                with num_int:
                    ui.tooltip("Segundos entre a chamada e cada repetição.").props("delay=1000")
            # Sequência de etapas/salas: cada etapa vira subfila com gui.hê próprio e TV replicável
            # card recolhível: sequência de etapas + lista inicial + envio txt/csv
            with ui.expansion("Etapas, lista inicial e arquivos (opcional)", icon="format_list_numbered").classes("w-full").style("min-width: 0") as exp_seq:
                with ui.row().classes("w-full items-center flex-wrap").style("gap: 0.5rem; min-width: 0"):
                    _info_seq = ui.icon("info_outline", size="16px").classes("text-grey-5").props('aria-label="Ajuda: etapas e lista"')
                    with _info_seq:
                        ui.tooltip("Etapas viram subfilas de sala; lista inicial usa um nome por linha + tags. Detalhes em cada campo.").props("delay=1000")
                with ui.row().classes("w-full flex-wrap items-start").style("gap: 0.5rem; min-width: 0"):
                    txt_etapas = ui.textarea("Sequência de etapas (uma por linha: Etapa | Guichê/Sala)", value="Recepção | 01\nTriagem | 02\nConsultório 3 | 03").props("outlined dense").classes("flex-1 min-w-[220px]").props('data-testid=filas-campo-etapas')
                    with txt_etapas:
                        ui.tooltip("Cada etapa é uma subfila (ex: Recepção → Triagem → Consultório 3 cardiologista). Cada sala/etapa tem painel próprio de 'próximo' e TV replicada só dela.").props("delay=1000")

                    txt_lista = ui.textarea("Lista inicial de usuários (opcional — um por linha + tags)", placeholder="maria #gestante #vermelho #recepcao").props("outlined dense").classes("flex-1 min-w-[220px]").props('data-testid=filas-campo-lista')
                    with txt_lista:
                        ui.tooltip("Vazio = fila só com senhas distribuídas; o nome é vinculado à senha depois, no painel. Um por linha + tags (# ou vírgula: Maria Cristina, gestante, vermelho, recepcao): grupo #gestante #idoso #deficiente, cor #vermelho #laranja #amarelo #verde #azul, etapa #recepcao.").props("delay=1000")

                async def _preencher_lista(e):
                    nome_arq, conteudo = await _ler_upload(e)
                    texto = (conteudo or b"").decode("utf-8", errors="replace")
                    if not texto.strip():
                        notificar("Arquivo vazio ou ilegível", type="negative")
                        return
                    txt_lista.value = texto
                    notificar(f"{nome_arq} carregado — confira e clique em Criar fila", type="positive")

                ui.upload(label="Ou selecione nomes.txt/.csv (preenche a lista ao lado)", auto_upload=True, on_upload=_preencher_lista, on_rejected=_rejeitado, multiple=False).props("accept='.txt,.csv'").classes("w-full")

            # card recolhível: anexo de MP4/MP3/fotos já na criação
            with ui.expansion("Anexar vídeos, áudios e fotos (opcional)", icon="attach_file").classes("w-full").style("min-width: 0") as exp_anexo:
                with ui.row().classes("w-full items-center flex-wrap").style("gap: 0.5rem; min-width: 0"):
                    _info_anex = ui.icon("info_outline", size="16px").classes("text-grey-5").props('aria-label="Ajuda: anexos"')
                    with _info_anex:
                        ui.tooltip("Anexos sobem na hora e entram na fila ao criar. Mesmo número de exibição = juntos.").props("delay=1000")
                box_stage = ui.column().classes("w-full gap-1").style("min-width: 0")
                midias_stage = []

                row_stage = ui.row().classes("w-full flex-wrap items-end").style("gap: 0.5rem; min-width: 0")
                with row_stage:
                    st_vol = ui.number("Volume", value=filas.VOLUME_AMBIENTE_PADRAO, min=0, max=100, step=1).props("outlined dense").classes("w-[90px]")
                    st_dur = ui.number("Duração foto (s)", value=8, min=3, max=120, step=1).props("outlined dense").classes("w-[130px]")
                    with st_dur:
                        ui.tooltip("Segundos de cada foto QUANDO sozinha (com áudio ela divide o tempo real).").props("delay=1000")
                    st_slot = ui.number("Exibição", value=0, min=0, max=999, step=1).props("outlined dense").classes("w-[90px]")
                    with st_slot:
                        ui.tooltip("Ordem de exibição; mesmo número = juntos (foto + áudio).").props("delay=1000")
                    st_fundo = ui.checkbox("Papel de fundo (fotos)", value=False)
                    with st_fundo:
                        ui.tooltip("Foto fixa atrás de tudo na TV (permanente).").props("delay=1000")
                with st_vol:
                    ui.tooltip("Altura do som (0-100, padrão 40) para os áudios e vídeos anexados. Duração vale só p/ foto sozinha; com áudio a foto divide o tempo real.").props("delay=1000")

                def _render_stage():
                    box_stage.clear()
                    with box_stage:
                        if not midias_stage:
                            ui.label("Nenhuma mídia anexada. Selecione MP4/MP3/fotos abaixo — sobem na hora e entram na fila ao criar.").classes("text-caption text-grey-6 italic")
                        for item in list(midias_stage):
                            with ui.row().classes("w-full items-center flex-wrap").style("gap: 0.5rem; min-width: 0"):
                                _fd = " • FUNDO" if item.get("fundo") else ""
                                ui.label(f"[{item['tipo']}] {item['original']} • vol {item['volume']} • exibição {item['slot']}{_fd}").classes("text-caption flex-1")
                                def _rm(item=item):
                                    try:
                                        os.remove(os.path.join(PASTA_MIDIA, item["temp"]))
                                    except Exception:
                                        pass
                                    midias_stage.remove(item)
                                    _render_stage()
                                ui.button(icon="delete", on_click=_rm).props("dense flat color=negative").tooltip("Remover anexo")

                async def _anexar_midia(e):
                    nome_arq, conteudo = await _ler_upload(e)
                    if not conteudo:
                        notificar("Falha ao ler arquivo", type="negative")
                        return
                    tipo = filas.tipo_por_extensao(nome_arq)
                    if not tipo:
                        notificar("Formato não suportado (mp3/wav/ogg/mp4/webm/jpg/png/webp)", type="negative")
                        return
                    import uuid as _uuid
                    base = re.sub(r"[^a-zA-Z0-9._-]", "_", os.path.splitext(nome_arq)[0])[:30]
                    temp = f"stage_{_uuid.uuid4().hex[:8]}_{base}{os.path.splitext(nome_arq)[1].lower()}"
                    try:
                        with open(os.path.join(PASTA_MIDIA, temp), "wb") as fh:
                            fh.write(conteudo)
                    except Exception as ex:
                        notificar(f"Erro ao subir: {ex}", type="negative")
                        return
                    try:
                        vol = int(float(st_vol.value if st_vol.value not in (None, "") else filas.VOLUME_AMBIENTE_PADRAO))
                    except Exception:
                        vol = filas.VOLUME_AMBIENTE_PADRAO
                    try:
                        dur = int(float(st_dur.value or 8))
                    except Exception:
                        dur = 8
                    try:
                        sl = int(float(st_slot.value or 0))
                    except Exception:
                        sl = 0
                    fundo = bool(st_fundo.value) and tipo == "imagem"
                    midias_stage.append({"original": nome_arq, "temp": temp, "tipo": tipo, "volume": vol, "duracao": dur, "slot": sl, "fundo": fundo})
                    notificar(f"{nome_arq} anexado", type="positive")
                    _render_stage()

                up_stage = ui.upload(label="Anexar vídeos MP4, áudios MP3 e fotos desta fila", auto_upload=True, on_upload=_anexar_midia, on_rejected=_rejeitado, multiple=True).props("accept='.mp3,.wav,.ogg,.m4a,.mp4,.webm,.jpg,.jpeg,.png,.webp'").classes("w-full")
                _render_stage()
            # Textos da TV editáveis pelo criador
            with ui.expansion("Personalizar textos da TV (opcional)", icon="tv").classes("w-full").style("min-width: 0") as exp_textos:
                with ui.row().classes("w-full items-center flex-wrap").style("gap: 0.5rem; min-width: 0"):
                    _info_txt = ui.icon("info_outline", size="16px").classes("text-grey-5").props('aria-label="Ajuda: textos da TV"')
                    with _info_txt:
                        ui.tooltip("Textos do cabeçalho e rodapé da TV. Vazio usa o padrão do sistema.").props("delay=1000")
                inp_tv_titulo = ui.input("Título da TV", placeholder="ex: Ambulatório — vazio=padrão do sistema").props("outlined dense").classes("w-full").style("min-width: 0")
                with inp_tv_titulo:
                    ui.tooltip("Título no topo da TV (vazio = nome do sistema).").props("delay=1000")
                inp_tv_sub = ui.input("Subtítulo da TV", placeholder="ex: Retire sua senha e aguarde").props("outlined dense").classes("w-full").style("min-width: 0")
                with inp_tv_sub:
                    ui.tooltip("Linha abaixo do título (vazio = fila/grupo).").props("delay=1000")
                inp_tv_ag = ui.input("Texto quando ociosa", value="AGUARDE CHAMADA").props("outlined dense").classes("w-full").style("min-width: 0")
                with inp_tv_ag:
                    ui.tooltip("Exibido na lateral quando não há chamada.").props("delay=1000")
                inp_tv_leg = ui.input("Legenda da mídia", placeholder="ex: Música ambiente / Propagandas").props("outlined dense").classes("w-full").style("min-width: 0")
                with inp_tv_leg:
                    ui.tooltip("Legenda curta ao lado do cabeçalho da TV.").props("delay=1000")
                inp_tv_not = ui.input("Título das notícias", value="Notícias").props("outlined dense").classes("w-full").style("min-width: 0")
                with inp_tv_not:
                    ui.tooltip("Título do rodapé de notícias da TV.").props("delay=1000")

            link_criada = ui.column().classes("w-full gap-1").style("min-width: 0")

            with ui.row().classes("w-full flex-wrap").style("gap: 0.5rem; min-width: 0"):
                btn_criar = botao("Criar fila", icone="add", on_click=lambda: _salvar_cadastro(), variante="primario", chave_modulo="filas").props('data-testid=filas-criar')
                btn_salvar = botao("Salvar alterações", icone="save", on_click=lambda: _salvar_cadastro(), variante="primario", chave_modulo="filas").props('data-testid=filas-salvar-edicao')
                btn_cancelar = botao("Cancelar", icone="close", on_click=lambda: _cancelar_edicao(), variante="contorno", chave_modulo="filas").props('data-testid=filas-cancelar-edicao')
                btn_salvar.visible = False
                btn_cancelar.visible = False

            def _limpar_form():
                inp_nome.value = ""
                inp_grupo_novo.value = ""
                txt_lista.value = ""
                for item in list(midias_stage):
                    try:
                        os.remove(os.path.join(PASTA_MIDIA, item["temp"]))
                    except Exception:
                        pass
                midias_stage.clear()
                try:
                    _render_stage()
                except Exception:
                    pass
                txt_etapas.value = "Recepção | 01\nTriagem | 02\nConsultório 3 | 03"
                inp_tv_titulo.value = ""
                inp_tv_sub.value = ""
                inp_tv_ag.value = "AGUARDE CHAMADA"
                inp_tv_leg.value = ""
                inp_tv_not.value = "Notícias"
                for c in (chk_senha, chk_nome, chk_dest, chk_guiche, chk_fila, chk_hora):
                    c.value = True
                num_rep.value = 0
                num_int.value = 2
                inp_ordem.value = "fila,senha,nome,destino,guiche"

            def _cancelar_edicao():
                edicao["fid"] = None
                lbl_modo.text = ""
                exp_seq.visible = True
                exp_anexo.visible = True
                try:
                    exp_textos.visible = True
                except Exception:
                    pass
                try:
                    exp_seq.close()
                except Exception:
                    pass
                try:
                    exp_anexo.close()
                except Exception:
                    pass
                try:
                    exp_textos.close()
                except Exception:
                    pass
                try:
                    exp_cad.close()
                except Exception:
                    pass
                link_criada.clear()
                btn_criar.visible = True
                btn_salvar.visible = False
                btn_cancelar.visible = False
                _limpar_form()

            def _carregar_edicao(fid: int):
                fila = filas.obter_fila(fid)
                if not fila:
                    notificar("Fila não encontrada", type="negative")
                    return
                _fid, _nome, _senha, _status, _guiche, _data, _end, _desc, _pref, _dono, _si, _sf, _grupo = fila
                try:
                    ex = filas.obter_extras_fila(fid)
                except Exception:
                    ex = {}
                edicao["fid"] = fid
                inp_nome.value = _nome or ""
                inp_pref.value = _pref or "A"
                inp_inicio.value = str(_si or 1)
                inp_fim.value = str(_sf or 0)
                inp_guiche.value = _guiche or "01"
                _atualizar_grupos()
                if _grupo and _grupo in (sel_grupo.options or []):
                    sel_grupo.value = _grupo
                    inp_grupo_novo.value = ""
                else:
                    sel_grupo.value = "(TV isolada / nova abaixo)"
                    inp_grupo_novo.value = _grupo or ""
                chk_nome.value = bool(ex.get("voz_nome", 1))
                chk_senha.value = bool(ex.get("voz_senha", 1))
                chk_dest.value = bool(ex.get("voz_destino", 1))
                chk_guiche.value = bool(ex.get("voz_guiche", 1))
                chk_fila.value = bool(ex.get("voz_fila", 1))
                chk_hora.value = bool(ex.get("voz_hora", 1))
                try:
                    num_rep.value = ex.get("voz_repetir", 0) or 0
                except Exception:
                    pass
                try:
                    num_int.value = ex.get("voz_intervalo", 2) or 2
                except Exception:
                    pass
                inp_ordem.value = ex.get("voz_ordem") or "fila,senha,nome,destino,guiche"
                inp_tv_titulo.value = ex.get("tv_titulo") or ""
                inp_tv_sub.value = ex.get("tv_subtitulo") or ""
                inp_tv_ag.value = ex.get("tv_aguardando") or "AGUARDE CHAMADA"
                inp_tv_leg.value = ex.get("tv_midia_legenda") or ""
                inp_tv_not.value = ex.get("tv_noticias_titulo") or "Notícias"
                exp_seq.visible = False
                exp_anexo.visible = False
                try:
                    exp_textos.visible = True
                except Exception:
                    pass
                lbl_modo.text = f"Editando: {_nome} (etapas, lista e mídias se gerenciam no card/administração)"
                btn_criar.visible = False
                btn_salvar.visible = True
                btn_cancelar.visible = True
                try:
                    exp_cad.open()
                except Exception:
                    pass

            def _editar_no_painel(fid: int):
                _carregar_edicao(fid)

            def _grupo_escolhido():
                try:
                    grupos = filas.listar_grupos_tv()
                except Exception:
                    grupos = []
                sel = sel_grupo.value or ""
                if sel in grupos:
                    return sel
                return (inp_grupo_novo.value or "").strip()

            def _salvar_cadastro():
                if edicao["fid"]:
                    return _salvar_edicao()
                si = inp_inicio.value or "1"
                sf = inp_fim.value or "0"
                try:
                    rep = int(float(num_rep.value or 0))
                except Exception:
                    rep = 0
                try:
                    interv = int(float(num_int.value or 2))
                except Exception:
                    interv = 2
                seq = []
                for lin in (txt_etapas.value or "").splitlines():
                    if "|" in lin:
                        en, eg = lin.split("|", 1)
                    else:
                        en, eg = lin, ""
                    en = en.strip()
                    if en:
                        seq.append((en, eg.strip()))
                ok, res = filas.criar_fila(inp_nome.value or "", prefixo=inp_pref.value or "A", guiche=inp_guiche.value or "01", ator=user_nome, senha_inicio=si, senha_fim=sf, tv_grupo=_grupo_escolhido(), voz_nome=chk_nome.value, voz_senha=chk_senha.value, voz_destino=chk_dest.value, voz_guiche=chk_guiche.value, voz_fila=chk_fila.value, voz_hora=chk_hora.value, voz_ordem=inp_ordem.value or "fila,senha,nome,destino,guiche", voz_repetir=rep, voz_intervalo=interv, tv_titulo=inp_tv_titulo.value or "", tv_subtitulo=inp_tv_sub.value or "", tv_aguardando=inp_tv_ag.value or "AGUARDE CHAMADA", tv_midia_legenda=inp_tv_leg.value or "", tv_noticias_titulo=inp_tv_not.value or "Notícias", etapas=seq or None)
                if ok:
                    fid = res
                    if (txt_lista.value or "").strip():
                        ok_l, msg_l = filas.importar_nomes(fid, txt_lista.value or "", ator=user_nome)
                        notificar(f"Lista inicial: {msg_l}", type="positive" if ok_l else "warning")
                        if ok_l:
                            txt_lista.value = ""
                    if midias_stage:
                        n_ok = 0
                        for item in list(midias_stage):
                            try:
                                final = filas.nome_arquivo_midia(fid, item["original"])
                                os.rename(os.path.join(PASTA_MIDIA, item["temp"]), os.path.join(PASTA_MIDIA, final))
                                ok_m, _ = filas.adicionar_midia(item["original"], item["tipo"], f"/midia_filas/{final}", arquivo_original=item["original"], ator=user_nome, fila_id=fid, volume=item["volume"], duracao=item["duracao"], slot=item["slot"])
                                if ok_m:
                                    n_ok += 1
                                    if item.get("fundo"):
                                        try:
                                            _conn_f = filas.get_connection()
                                            try:
                                                _cur_f = _conn_f.cursor()
                                                _cur_f.execute("SELECT id FROM tb_midia WHERE caminho=?", (f"/midia_filas/{final}",))
                                                _r_f = _cur_f.fetchone()
                                                if _r_f:
                                                    filas.set_midia_fundo(_r_f[0], True, ator=user_nome)
                                            finally:
                                                _conn_f.close()
                                        except Exception:
                                            pass
                            except Exception:
                                pass
                        midias_stage.clear()
                        _render_stage()
                        notificar(f"{n_ok} mídia(s) vinculada(s)", type="positive" if n_ok else "warning")
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
                        with ui.row().classes("w-full items-center flex-wrap").style("gap: 0.5rem; min-width: 0"):
                            ui.icon("check_circle", size="20px").classes("text-green-7")
                            ui.label(tv_label).classes("font-bold text-caption")
                            botao("Abrir TV desta fila", icone="tv", on_click=lambda url=tv_url: ui.navigate.to(url, new_tab=True), variante="primario", chave_modulo="filas").props('data-testid=filas-tv-recem-criada')
                            ui.label(f"Link: {tv_url}").classes("text-caption text-grey-6")
                    inp_nome.value = ""
                    inp_grupo_novo.value = ""
                    _atualizar_grupos()
                    render_filas()
                else:
                    notificar(res, type="negative")

            def _salvar_edicao():
                fid = edicao["fid"]
                try:
                    rep = int(float(num_rep.value or 0))
                except Exception:
                    rep = 0
                try:
                    interv = int(float(num_int.value or 2))
                except Exception:
                    interv = 2
                ok, msg = filas.atualizar_fila(fid, nome=inp_nome.value, prefixo=inp_pref.value, guiche=inp_guiche.value, senha_inicio=inp_inicio.value or "1", senha_fim=inp_fim.value or "0", tv_grupo=_grupo_escolhido(), ator=user_nome, voz_nome=chk_nome.value, voz_senha=chk_senha.value, voz_destino=chk_dest.value, voz_guiche=chk_guiche.value, voz_fila=chk_fila.value, voz_hora=chk_hora.value, voz_ordem=inp_ordem.value or "fila,senha,nome,destino,guiche", voz_repetir=rep, voz_intervalo=interv, tv_titulo=inp_tv_titulo.value or "", tv_subtitulo=inp_tv_sub.value or "", tv_aguardando=inp_tv_ag.value or "AGUARDE CHAMADA", tv_midia_legenda=inp_tv_leg.value or "", tv_noticias_titulo=inp_tv_not.value or "Notícias")
                notificar(msg, type="positive" if ok else "negative")
                if ok:
                    _cancelar_edicao()
                    _atualizar_grupos()
                    render_filas()
            with link_criada:
                pass

        box = ui.column().classes("w-full gap-4")

        def render_filas():
            box.clear()
            with box:
                filas_visiveis = filas.listar_filas_visiveis(user_nome, perfil_global, eh_admin_modulo)
                try:
                    liberadas = set(filas.filas_liberadas(user_nome))
                except Exception:
                    liberadas = set()
                if not filas_visiveis:
                    ui.label("Nenhuma fila sua ainda. Crie acima.").classes("text-caption text-grey-6 italic")
                    return
                for fid, nome, senha, status, guiche, data, endereco, descricao, prefixo, criado_por, senha_inicio, senha_fim, tv_grupo in filas_visiveis:
                    etapas = filas.listar_etapas(fid)
                    ult = filas.ultima_chamada(fid)
                    pode_editar = eh_admin or criado_por == user_nome or fid in liberadas
                    pode_dono = eh_admin or criado_por == user_nome
                    with ui.card().classes("w-full p-4 gap-3").style("min-width: 0"):
                        with ui.row().classes("w-full items-center justify-between flex-wrap").style("gap: 0.5rem; min-width: 0"):
                            with ui.column().classes("gap-0 flex-1 min-w-[200px]").style("min-width: 0"):
                                ui.label(nome).classes("font-bold text-h6")
                                ui.label(f"Senha atual: {senha} • Prefixo: {prefixo} • {senha_inicio}→{senha_fim if senha_fim else '∞'} • Guichê base: {guiche} • TV: {tv_grupo or 'isolada'} • Dono: {criado_por or '—'} • {status}").classes("text-caption text-grey-6")
                            with ui.row().classes("w-full flex-wrap").style("gap: 0.25rem; min-width: 0"):
                                # link TV isolada ou compartilhada
                                if tv_grupo:
                                    tv_url = f"/tv?grupo={tv_grupo}"
                                    botao(f"TV grupo {tv_grupo}", icone="tv", on_click=lambda u=tv_url: ui.navigate.to(u, new_tab=True), variante="contorno", chave_modulo="filas").tooltip(f"TV compartilhada — grupo {tv_grupo}").props('data-testid=filas-card-tv-grupo')
                                else:
                                    tv_url = f"/tv/{fid}"
                                    botao("Abrir TV desta fila", icone="tv", on_click=lambda u=tv_url: ui.navigate.to(u, new_tab=True), variante="contorno", chave_modulo="filas").tooltip(f"TV isolada — fila {nome}").props('data-testid=filas-card-abrir-tv')
                                if eh_admin or criado_por == user_nome:
                                    def _excluir(fid=fid, nome=nome):
                                        ok, msg = filas.excluir_fila(fid, ator=user_nome)
                                        notificar(msg, type="positive" if ok else "negative")
                                        render_filas()
                                    botao("Excluir", icone="delete", on_click=_excluir, variante="contorno", chave_modulo="filas").props('data-testid=filas-excluir')
                                if pode_editar:
                                    botao("Editar", icone="edit", on_click=lambda fid=fid: _editar_no_painel(fid), variante="contorno", chave_modulo="filas").props('data-testid=filas-editar')
                                if pode_dono:
                                    botao("Acesso", icone="group_add", on_click=lambda fid=fid: dialogo_acesso_fila(fid, user_nome, render_filas), variante="contorno", chave_modulo="filas").tooltip("Chamar usuários para esta fila").props('data-testid=filas-acesso-abrir')
                                ui.label(f"Link: {tv_grupo and f'/tv?grupo={tv_grupo}' or f'/tv/{fid}'}").classes("text-caption text-grey-6 self-center")
                        # etapas — isoladas por fila
                        with ui.row().classes("w-full flex-wrap").style("gap: 0.5rem; min-width: 0"):
                            for eid, efid, ordem, enome, eguiche, eativo in etapas:
                                ui.badge(f"{ordem}. {enome} ({eguiche or guiche})", color="primary").props("outline")
                        # chamar — isolado
                        with ui.row().classes("w-full flex-wrap items-end").style("gap: 0.5rem; min-width: 0"):
                            inp_paciente = ui.input("Paciente (avulso — vazio usa a lista)", placeholder="Nome").props("outlined dense").classes("flex-1 min-w-[160px]").style("min-width: 0")
                            with inp_paciente:
                                ui.tooltip("Nome avulso para esta senha; vazio consome o próximo da lista em ordem.").props("delay=1000")
                            sel_etapa = ui.select([e[3] for e in etapas], value=etapas[0][3] if etapas else "Atendimento", label="Etapa/Destino").props("outlined dense").classes("w-[180px]").style("min-width: 0") if etapas else None
                            if sel_etapa is not None:
                                with sel_etapa:
                                    ui.tooltip("Sala/etapa de destino desta chamada.").props("delay=1000")
                            sel_prio = ui.select(list(PRIO_LABEL.values()), value="Comum", label="Grupo (avulso)").props("outlined dense").classes("w-[150px]").style("min-width: 0")
                            with sel_prio:
                                ui.tooltip("Grupo do avulso (Comum, Gestante, Idoso, Deficiente).").props("delay=1000")

                            def _chamar(fid=fid, inp=inp_paciente, sel=sel_etapa, sp=sel_prio):
                                etapa = sel.value if sel else "Atendimento"
                                paciente = inp.value.strip() if inp else ""
                                inv = {v: k for k, v in PRIO_LABEL.items()}
                                ok, msg = filas.gerar_senha(fid, ator=user_nome, paciente_nome=paciente, etapa_nome=etapa, prioridade=inv.get(sp.value, "comum") if sp else "comum")
                                notificar(f"Senha {msg} → {etapa}" if ok else msg, type="positive" if ok else "negative")
                                if inp:
                                    inp.value = ""
                                render_filas()
                            botao("Chamar próximo", icone="campaign", on_click=_chamar, variante="primario", chave_modulo="filas").props('data-testid=filas-chamar-proximo')
                            if ult:
                                cid, senha_u, guiche_u, data_u, pac_u, etapa_u, fnome_u, prio_u, manch_u = ult
                                ui.label(f"Última: {senha_u} {pac_u or ''} → {etapa_u} ({guiche_u}) {data_u[:16] if data_u else ''}").classes("text-caption text-grey-7 self-center").style(_estilo_manchester(manch_u) or "")
                            try:
                                n_pend = filas.contar_nomes_pendentes(fid)
                            except Exception:
                                n_pend = 0
                            if n_pend:
                                ui.label(f"{n_pend} nome(s) na lista — o próximo chama em ordem").classes("text-caption text-primary self-center font-bold")

                        # histórico isolado desta fila
                        with ui.expansion("Histórico desta fila (isolado)", icon="history").classes("w-full").style("min-width: 0"):
                            for cid, fid2, senha2, guiche2, data2, por2, pac2, etapa2, fn2, prio2, manch2 in filas.listar_chamadas(5, fila_id=fid):
                                with ui.row().classes("w-full items-center justify-between flex-wrap").style("gap: 0.5rem; min-width: 0"):
                                    ui.label(f"{senha2} — {etapa2} — {pac2 or '—'} — gui.hê {guiche2} — {data2[:16] if data2 else ''}").classes("text-caption flex-1").style(_estilo_manchester(manch2) or "")
                                    # qualquer atendente: cor a qualquer hora
                                    selmh = ui.select(list(MANCHESTER_LABEL.values()), value=MANCHESTER_LABEL.get(manch2 or "", "—")).props("outlined dense").classes("w-[120px]")
                                    def _svmh(fn=fid, s=senha2, sel=selmh):
                                        invm = {v: k for k, v in MANCHESTER_LABEL.items()}
                                        ok, msg = filas.definir_manchester_senha(fn, s, invm.get(sel.value, ""), ator=user_nome)
                                        notificar(msg, type="positive" if ok else "negative")
                                        render_filas()
                                    ui.button(icon="healing", on_click=_svmh).props("dense flat color=negative").tooltip("Salvar cor")
                                    # avançar só se não for última etapa (quem vê a fila pode editar)
                                    if pode_editar:
                                        et_nomes = [e[3] for e in etapas]
                                        if etapa2 in et_nomes and et_nomes.index(etapa2) < len(et_nomes) - 1:
                                            def _av(cid=cid):
                                                ok, m = filas.avancar_chamada(cid, ator=user_nome)
                                                notificar(m, type="positive" if ok else "warning")
                                                render_filas()
                                            botao("Avançar", icone="arrow_forward", on_click=_av, variante="texto", chave_modulo="filas").props('data-testid=filas-avancar')

                        # por etapa/sala: próximo, nome e Manchester — qualquer atendente
                        bloco_etapas(fid, nome, tv_grupo, user_nome, render_filas)

                        # edição da fila: mídias, nomes e controle da TV (quem vê a fila pode editar)
                        if pode_editar:
                            bloco_nomes_fila(fid, user_nome, render_filas)
                            bloco_midia_fila(fid, user_nome, render_filas)
                            try:
                                _ids_tv = filas.ids_do_grupo(tv_grupo) if tv_grupo else [fid]
                            except Exception:
                                _ids_tv = [fid]
                            bloco_controle_tv(filas.chave_tv(tv_grupo=tv_grupo) if tv_grupo else filas.chave_tv(fila_id=fid), tv_grupo or nome, fila_ids=_ids_tv)

        render_filas()

        # Excluir uma ou todas — confirmação
        with ui.row().classes("w-full justify-center flex-wrap mt-2").style("gap: 0.5rem; min-width: 0"):
            def _confirmar_excluir_todas():
                titulo = "Excluir todas as filas" if eh_admin else "Excluir todas minhas filas"
                msg = "Tem certeza? Todas as filas e suas chamadas/etapas/mídias/nomes serão apagadas. Esta ação não pode ser desfeita." if eh_admin else "Excluir todas as SUAS filas?"
                with ui.dialog() as dlg, ui.card():
                    ui.label(titulo).classes("font-bold")
                    ui.label(msg).classes("text-caption text-grey-7")
                    with ui.row().classes("w-full justify-end flex-wrap").style("gap: 0.5rem; min-width: 0"):
                        ui.button("Cancelar", on_click=dlg.close).props("flat")
                        def _executar():
                            ok, m = filas.excluir_todas_filas(ator=user_nome, somente_do_criador=user_nome, eh_admin=eh_admin)
                            notificar(m, type="positive" if ok else "negative")
                            dlg.close()
                            render_filas()
                        ui.button("Confirmar exclusão", on_click=_executar).props("color=negative").props('data-testid=filas-confirmar-exclusao')
                dlg.open()
            label_todas = "Excluir todas as filas" if eh_admin else "Excluir todas minhas filas"
            botao(label_todas, icone="delete_forever", on_click=_confirmar_excluir_todas, variante="contorno", chave_modulo="filas").tooltip("Excluirem lote").props("color=negative").props('data-testid=filas-excluir-todas')
        # Administração: padrão dos módulos — menu hambúrguer → Administração (/admin/filas)


def mostrar_tv(fila_id: int = None, tv_grupo: str = None, etapa: str = None):
    """TV — mídia ocupa a tela (>90%) + faixa lateral com senhas e 3 últimos. Sem controles na TV (só na edição)."""
    from mod_intranet.tema_modulo import ler_tema as _ler
    from mod_intranet.bd_conexao import get_config as _get_cfg
    tema = _ler("filas")
    ui.colors(primary=tema.get("cor_botao", "#000000"))
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
    # valida slug do grupo (URL limpa); inválido = ignora e cai p/ isolada/geral
    if tv_grupo:
        _okg, _slug = filas.normalizar_tv_grupo(tv_grupo)
        tv_grupo = _slug if _okg else None
    # filas desta TV + config (textos/voz da 1ª fila do grupo ou da fila isolada)
    fila_ids = []
    cfg = {}
    try:
        if tv_grupo:
            todas = filas.listar_filas()
            fila_ids = [r[0] for r in todas if len(r) > 12 and r[12] == tv_grupo]
            if fila_ids:
                cfg = filas.obter_extras_fila(min(fila_ids))
        elif fila_id:
            fila_ids = [int(fila_id)]
            cfg = filas.obter_extras_fila(int(fila_id))
    except Exception:
        pass
    if not cfg:
        cfg = {"voz_nome": 1, "voz_senha": 1, "voz_destino": 1, "voz_guiche": 1,
               "voz_fila": 1, "voz_hora": 1, "voz_ordem": "fila,senha,nome,destino,guiche",
               "voz_repetir": 0, "voz_intervalo": 2, "tv_titulo": "",
               "tv_subtitulo": "", "tv_aguardando": "AGUARDE CHAMADA",
               "tv_midia_legenda": "", "tv_noticias_titulo": "Notícias"}
    etapa = (etapa or "").strip() or None
    chave = filas.chave_tv(tv_grupo=tv_grupo) if tv_grupo else (filas.chave_tv(fila_id=int(fila_id)) if fila_id else filas.chave_tv())
    # fila de voz independente por etapa/sala: um anúncio por vez, sem cortar
    try:
        chave_fala = filas.chave_tv_etapa(tv_grupo=tv_grupo, etapa=etapa) if tv_grupo else (filas.chave_tv_etapa(fila_id=int(fila_id), etapa=etapa) if fila_id else filas.chave_tv_etapa(etapa=etapa))
    except Exception:
        chave_fala = chave
    # mídias SÓ desta TV + áudio ambiente global do admin (toca em todas)
    try:
        midias = filas.midias_para_tv(fila_ids or None)
    except Exception:
        midias = []
    # slots (exibições) em ordem; mesmo slot = juntos (foto + áudio)
    slots = sorted({m[11] for m in midias}) or [0]
    try:
        _est0 = filas.obter_estado_tv(chave)
        _slot0 = _est0.get("slot_atual", 0)
    except Exception:
        _slot0 = 0
    # cabeçalho — textos editáveis pelo criador da fila
    titulo_tv = (cfg.get("tv_titulo") or titulo_sistema).strip() or titulo_sistema
    if etapa:
        base_sub = f"TV — {etapa}"
    elif cfg.get("tv_subtitulo"):
        base_sub = cfg["tv_subtitulo"]
    elif tv_grupo:
        base_sub = f"TV — Grupo {tv_grupo} (compartilhada)"
    elif fila_id:
        try:
            _f = filas.obter_fila(int(fila_id))
            _nome_f = _f[1] if _f else f"#{fila_id}"
        except Exception:
            _nome_f = f"#{fila_id}"
        base_sub = f"TV — Fila {_nome_f} (isolada)"
    else:
        base_sub = "TV — Todas as filas"
    subtitulo_tv = base_sub
    legenda_midia = (cfg.get("tv_midia_legenda") or "").strip()
    titulo_noticias = (cfg.get("tv_noticias_titulo") or "Notícias").strip() or "Notícias"
    aguardando = (cfg.get("tv_aguardando") or "AGUARDE CHAMADA").strip() or "AGUARDE CHAMADA"

    # cabeçalho com textos do criador
    with ui.column().classes("w-full h-screen bg-black text-white gap-0 p-0").style("min-height: 100vh; min-width: 0"):
        with ui.row().classes("w-full items-center flex-wrap px-4 py-2 bg-grey-900").style("gap: 0.75rem; min-width: 0"):
            ui.icon(icone_sistema).classes("text-white").style("font-size: 28px; flex-shrink: 0")
            ui.label(titulo_tv).classes("text-white font-bold").style("min-width: 0; overflow-wrap: break-word")
            ui.label("•").classes("text-grey-5").style("flex-shrink: 0")
            ui.label(subtitulo_tv).classes("text-white font-bold tracking-widest").style("min-width: 0; overflow-wrap: break-word")
            ui.space()
            if legenda_midia:
                ui.label(legenda_midia).classes("text-caption text-grey-4").style("min-width: 0")

        # corpo: mídia (flexível) + faixa lateral direita com senhas — empilha no mobile, lado a lado no desktop
        with ui.row().classes("w-full flex-1 flex-wrap md:flex-nowrap").style("min-height: 0; flex: 1 1 auto; gap: 0; min-width: 0"):
            with ui.column().classes("items-center justify-center p-2").style("flex: 1 1 320px; min-width: 0; background: #000; position: relative; overflow: hidden; gap: 0.5rem"):
                media_html = ui.html("", sanitize=False).classes("w-full flex justify-center items-center").style("pointer-events: none; min-height: 40vh; min-width: 0").props('aria-label="Mídia ambiente da TV" role=img')
                try:
                    media_html.props('id="tvmedia"')
                except Exception:
                    pass
            with ui.column().classes("p-3 bg-grey-900").style("flex: 1 1 240px; min-width: 0; max-width: 100%; overflow-y: auto; gap: 0.5rem"):
                lbl_topo = ui.label(aguardando).classes("tracking-widest text-grey-4").style("font-size: 0.85rem; min-width: 0; overflow-wrap: break-word")
                lbl_senha = ui.label("—").classes("font-extrabold leading-none text-yellow-3").style("font-size: clamp(2.4rem, 6vw, 3.2rem); min-width: 0").props('aria-live=polite role=status aria-label="Senha chamada"')
                lbl_paciente = ui.label("").classes("font-bold text-white").style("font-size: 1.15rem; min-width: 0; overflow-wrap: break-word").props('aria-live=polite aria-label="Paciente chamado"')
                lbl_destino = ui.label("").classes("font-bold text-white").style("font-size: 1rem; min-width: 0; overflow-wrap: break-word").props('aria-label="Destino da chamada"')
                lbl_guiche = ui.label("").classes("text-grey-4").style("font-size: 0.85rem; min-width: 0")
                ui.separator()
                ui.label("Últimos chamados").classes("text-caption tracking-widest text-grey-4").style("min-width: 0")
                box_ultimos = ui.column().classes("w-full").style("gap: 0.25rem; min-width: 0")
                with box_ultimos:
                    pass

        # rodapé notícias — card sempre ESCURO (cor do tema quando escura),
        # texto sempre CLARO para contraste; altura e fontes permitem ler título + descrição
        _cor_botao_tv = (tema.get("cor_botao") or "#000000").strip() or "#000000"
        _fundo_noticias = _fundo_rodape_escuro(_cor_botao_tv)
        with ui.card().classes("w-full text-white rounded-none p-5").style(
            f"background-color: {_fundo_noticias}; min-height: 22vh; flex-shrink: 0; "
            "gap: 0.5rem; border-top: 2px solid rgba(255,255,255,0.15); min-width: 0"
        ):
            with ui.row().classes("w-full items-center").style("gap: 0.75rem; min-width: 0"):
                ui.label(titulo_noticias).classes("tracking-widest").style("font-size: 0.95rem; color: #FFFFFF; font-weight: bold; min-width: 0")
                ui.space()
                lbl_n_contador = ui.label("").style("font-size: 0.95rem; color: #CCCCCC; min-width: 0").props('aria-hidden=true')
            lbl_n_titulo = ui.label("Aguardando notícias...").classes("w-full font-bold").style(
                "font-size: clamp(1.35rem, 2.4vw, 2.2rem); line-height: 1.25; color: #FFFFFF; "
                "white-space: normal; overflow-wrap: break-word; word-break: break-word; min-width: 0")
            lbl_n_desc = ui.label("").classes("w-full").style(
                "font-size: clamp(1.0rem, 1.5vw, 1.45rem); line-height: 1.4; color: #F1F1F1; "
                "white-space: normal; overflow-wrap: break-word; word-break: break-word; min-width: 0")
            lbl_n_fonte = ui.label("").classes("w-full").style("font-size: 0.95rem; color: #CCCCCC; min-width: 0")

        noticias_tv = {"lista": [], "idx": 0}
        estado = {"ultimo_id": None, "slot_pos": 0, "repeticoes": 0, "ultima_voz_fila": 0.0, "hora_falada": ""}
        if _slot0 in slots:
            estado["slot_pos"] = slots.index(_slot0)

        def _falar_fila(texto: str):
            """Voz de chamada de fila (prioridade total): registra hora p/ a hora cheia esperar."""
            import time as _t
            estado["ultima_voz_fila"] = _t.time()
            _js_duck_e_voz(texto)

        def _falar_hora_se_hora(ultimo_id_novo: bool = False):
            """Hora cheia/meia: só fala se habilitado, sem chamada de fila há 60s e ainda não falada."""
            if not cfg.get("voz_hora", 1):
                return
            import time as _t
            from datetime import datetime as _dt
            agora = _dt.now()
            if agora.minute not in (0, 30):
                return
            chave_hora = f"{agora.hour:02d}:{agora.minute:02d}"
            if estado["hora_falada"] == chave_hora:
                return
            if _t.time() - (estado["ultima_voz_fila"] or 0) < 60:
                return
            estado["hora_falada"] = chave_hora
            if agora.minute == 0:
                texto = f"É 1 hora." if agora.hour == 1 else f"São {agora.hour} horas."
            else:
                texto = f"É 1 hora e 30 minutos." if agora.hour == 1 else f"São {agora.hour} horas e 30 minutos."
            _js_duck_e_voz(texto)

        def _texto_chamada(paciente, senha, etapa, guiche, fnome):
            """Monta a fala na ORDEM definida pela fila (voz_ordem: fila,senha,nome,destino,guiche)."""
            liga = {"fila": bool(cfg.get("voz_fila", 1)), "senha": bool(cfg.get("voz_senha")),
                    "nome": bool(cfg.get("voz_nome")), "destino": bool(cfg.get("voz_destino")),
                    "guiche": bool(cfg.get("voz_guiche"))}
            frag = {}
            if fnome:
                frag["fila"] = f"fila {fnome}"
            frag["senha"] = f"senha {senha}"
            if paciente:
                frag["nome"] = paciente
            if etapa:
                frag["destino"] = f"dirigir-se a {etapa}"
            if guiche:
                g = (guiche or "").strip()
                frag["guiche"] = g if "gui.h" in g.lower() else f"gui.hê {g}"
            partes = []
            try:
                ok_o, ordem = filas.normalizar_voz_ordem(cfg.get("voz_ordem") or "")
            except Exception:
                ok_o, ordem = False, ""
            seq = ordem.split(",") if ok_o else list(filas.VOZ_CAMPOS)
            for campo in seq:
                if liga.get(campo) and campo in frag:
                    partes.append(frag[campo])
            if not partes:
                partes.append(f"senha {senha}")
            return ", ".join(partes) + "."

        def _js_duck_e_voz(texto: str):
            """Chamada com ducking: baixa a música à metade 2s antes, fala, restaura 2s depois."""
            texto_esc = texto.replace("'", "\\'").replace('"', '\\"').replace("\n", " ")
            js = f"""
try {{
  document.querySelectorAll('#tvmedia audio,#tvmedia video').forEach(el => {{
    try {{ el.volume = Math.max(0, (parseFloat(el.dataset.vol || '0.4')) * 0.5); }} catch(e){{}}
  }});
  setTimeout(() => {{
    try {{
      const ctx = new (window.AudioContext||window.webkitAudioContext)();
      const o = ctx.createOscillator(); const g = ctx.createGain();
      o.type='sine'; o.frequency.value=880; g.gain.value=0.2;
      o.connect(g); g.connect(ctx.destination); o.start(); o.stop(ctx.currentTime+0.35);
    }} catch(e){{}}
    const restaurar = () => {{
      setTimeout(() => {{
        try {{
          document.querySelectorAll('#tvmedia audio,#tvmedia video').forEach(el => {{
            const v = parseFloat(el.dataset.vol || '0.4');
            if (!isNaN(v)) el.volume = Math.max(0, Math.min(1, v));
          }});
        }} catch(e){{}}
      }}, 2000);
    }};
    try {{
      if ('speechSynthesis' in window) {{
        window.speechSynthesis.cancel();
        const u = new SpeechSynthesisUtterance('{texto_esc}');
        u.lang='pt-BR'; u.rate=0.9; u.pitch=1.0; u.volume=0.8;
        let _ok = false;
        const _uma = () => {{ if (!_ok) {{ _ok = true; restaurar(); }} }};
        u.onend = _uma;
        window.speechSynthesis.speak(u);
        setTimeout(_uma, 20000);
      }} else {{
        restaurar();
      }}
    }} catch(e){{ restaurar(); }}
  }}, 2000);
}} catch(e){{}}
"""
            try:
                ui.run_javascript(js)
            except Exception:
                pass

        def _src(caminho):
            src = caminho if caminho.startswith("/") else f"/midia_filas/{os.path.basename(caminho)}"
            if not src.startswith("/midia_filas"):
                src = f"/midia_filas/{os.path.basename(src)}"
            return src

        def _render_slot():
            """Renderiza exibição atual: imagens/vídeo ocupam a tela; áudio toca oculto. SEM controles na TV."""
            if not midias:
                media_html.content = "<div class='text-grey-5'>Nenhuma mídia — envie MP3/MP4/fotos na edição da fila</div>"
                return 8
            slot = slots[estado["slot_pos"] % len(slots)]
            itens = [m for m in midias if m[11] == slot]
            if not itens:
                return 8
            try:
                filas.definir_estado_tv(chave, slot_atual=slot)
            except Exception:
                pass
            partes = []
            html_imgs = []
            tempos_foto = []
            # papel de fundo restrito à área de mídia: absolute inset:0 dentro do wrapper relativo da mídia (não cobre a página)
            _fundos = [m for m in midias if m[2] == "imagem" and len(m) > 13 and m[13]]
            if _fundos:
                partes.append(f"<div style='position:absolute;inset:0;background:url({_src(_fundos[0][3])}) center/cover;opacity:0.22;pointer-events:none;z-index:0'></div>")
            for (_id, _nome, _tipo, _caminho, _orig, _ordem, _ativo, _criado, _fid, _vol, _dur, _slot, _real, _fundo) in itens:
                src = _src(_caminho)
                vol = max(0, min(int(_vol if _vol not in (None, "") else filas.VOLUME_AMBIENTE_PADRAO), 100)) / 100
                if _tipo == "imagem":
                    if not _fundo:
                        html_imgs.append(src)
                elif _tipo == "video":
                    if not any("data-vid" in p for p in partes):
                        partes.append(f"<video autoplay loop playsinline data-vol='{vol}' data-vid='1' style='width:100%;max-height:62vh;background:#000;pointer-events:none'><source src='{src}'></video>")
                else:
                    partes.append(f"<audio autoplay loop data-vol='{vol}' style='display:none'><source src='{src}'></audio>")
            # tempo total = real do áudio/vídeo; fotos dividem (40s + 4 fotos = 10s cada)
            total, tempos_foto = filas.calcular_passo([(_t, _d, _r) for (_, _, _t, _, _, _, _, _, _, _, _d, _, _r, *_x) in itens])
            for k, src in enumerate(html_imgs):
                vis = "block" if k == 0 else "none"
                partes.append(f"<img data-imgidx='{k}' src='{src}' style='display:{vis};max-width:100%;max-height:62vh;object-fit:contain;background:#000'>")
            media_html.content = "<div style='position:relative;z-index:1;width:100%;display:flex;flex-direction:column;align-items:center;gap:8px'>" + "".join(partes) + "</div>"
            try:
                ui.run_javascript("try{document.querySelectorAll('#tvmedia audio,#tvmedia video').forEach(el=>{const v=parseFloat(el.dataset.vol||'0.4'); if(!isNaN(v)) el.volume=Math.max(0,Math.min(1,v)); const p=el.play(); if(p&&p.catch){p.catch(()=>{if(el.tagName==='VIDEO'){el.muted=true; el.play().catch(()=>{});}});}});}catch(e){}")
                import json as _json
                ui.run_javascript("try{if(window._tvt){clearTimeout(window._tvt);window._tvt=null;}const imgs=Array.from(document.querySelectorAll('#tvmedia [data-imgidx]'));const durs=" + _json.dumps([float(x) for x in tempos_foto]) + ";if(imgs.length>1){let p=0;const show=k=>{imgs.forEach((el,j)=>{el.style.display=(j===k?'block':'none');});};const adv=()=>{p=(p+1)%imgs.length;show(p);window._tvt=setTimeout(adv,(durs[p]||8)*1000);};window._tvt=setTimeout(adv,(durs[0]||8)*1000);}}catch(e){}")
            except Exception:
                pass
            return total

        def _dur_fala(texto: str) -> float:
            return round(4.0 + len(texto or "") / 11.0, 1)

        def _rep(texto: str, restantes: int, interv: int):
            """Repetição sem cortar: só fala com voz livre, senão tenta de novo."""
            def _go():
                try:
                    if filas.tv_livre(chave_fala):
                        filas.tv_bloquear(chave_fala, _dur_fala(texto))
                        _falar_fila(texto)
                        if restantes - 1 > 0:
                            ui.timer(max(1, interv), lambda: _rep(texto, restantes - 1, interv), once=True)
                    else:
                        ui.timer(max(1, interv), lambda: _rep(texto, restantes, interv), once=True)
                except Exception:
                    pass
            _go()

        def _atualizar_lateral(ult, ultimos):
            # discrição: NENHUMA palavra de grupo/cor na tela — só o fundo colorido já orienta
            if ult:
                _cid, _senha, _guiche, _data, _pac, _etapa, _fnome, _prio, _manch = ult
                lbl_topo.text = _fnome or aguardando
                lbl_senha.text = str(_senha)
                try:
                    lbl_paciente.style(_estilo_manchester(_manch) or "")
                except Exception:
                    pass
                lbl_paciente.text = _pac or ""
                lbl_destino.text = _etapa or ""
                lbl_guiche.text = f"Guichê {_guiche}" if _guiche else ""
            box_ultimos.clear()
            with box_ultimos:
                for (_cid, _fid2, _senha2, _guiche2, _data2, _por2, _pac2, _etapa2, _fn2, _prio2, _manch2) in (ultimos or [])[:3]:
                    with ui.row().classes("w-full items-center flex-wrap").style("gap: 0.25rem; min-width: 0"):
                        ui.label(f"{_senha2} • {_pac2 or '—'}").classes("text-white font-bold").style(f"font-size: 0.95rem; min-width: 0; overflow-wrap: break-word;{_estilo_manchester(_manch2)}")
                    ui.label(f"{_etapa2 or ''} {_guiche2 and '• gui.hê ' + str(_guiche2) or ''} • {(_data2 or '')[:16]}").classes("text-grey-4").style("font-size: 0.75rem; min-width: 0; overflow-wrap: break-word")

        def refresh_chamada():
            # comando remoto da edição: pausar/retomar/próximo/anterior
            try:
                cmd = filas.consumir_comando_tv(chave)
            except Exception:
                cmd = ""
            if cmd == "pausar":
                try:
                    filas.definir_estado_tv(chave, pausado=1)
                except Exception:
                    pass
                return
            if cmd == "retomar":
                try:
                    filas.definir_estado_tv(chave, pausado=0)
                except Exception:
                    pass
            elif cmd == "proximo":
                estado["slot_pos"] = (estado["slot_pos"] + 1) % max(1, len(slots))
                _render_slot()
                return
            elif cmd == "anterior":
                estado["slot_pos"] = (estado["slot_pos"] - 1) % max(1, len(slots))
                _render_slot()
                return
            elif cmd.startswith("slot:"):
                try:
                    alvo = int(cmd.split(":", 1)[1])
                    if alvo in slots:
                        estado["slot_pos"] = slots.index(alvo)
                        _render_slot()
                except Exception:
                    pass
                return
            try:
                pausado = filas.obter_estado_tv(chave).get("pausado", 0)
            except Exception:
                pausado = 0
            if pausado:
                return
            # isolada vs compartilhada vs global — com filtro de etapa/sala
            if tv_grupo:
                ult = filas.ultima_chamada_tv(tv_grupo=tv_grupo, etapa_nome=etapa)
                ultimos = filas.listar_chamadas_tv(limite=4, tv_grupo=tv_grupo, etapa_nome=etapa)
            elif fila_id:
                ult = filas.ultima_chamada(int(fila_id), etapa_nome=etapa)
                ultimos = filas.listar_chamadas(limite=4, fila_id=int(fila_id), etapa_nome=etapa)
            else:
                ult = filas.ultima_chamada(etapa_nome=etapa)
                ultimos = filas.listar_chamadas(limite=4, etapa_nome=etapa)
            _atualizar_lateral(ult, ultimos)
            # voz em FILA: anuncia o mais antigo não falado; um por vez, sem cortar o atual
            try:
                _est_fala = filas.obter_estado_tv(chave_fala)
            except Exception:
                _est_fala = {"ultima_falada": 0}
            try:
                if tv_grupo:
                    _prox = filas.buscar_proxima_fala(tv_grupo=tv_grupo, etapa_nome=etapa, apos_id=_est_fala.get("ultima_falada", 0))
                elif fila_id:
                    _prox = filas.buscar_proxima_fala(fila_id=int(fila_id), etapa_nome=etapa, apos_id=_est_fala.get("ultima_falada", 0))
                else:
                    _prox = filas.buscar_proxima_fala(etapa_nome=etapa, apos_id=_est_fala.get("ultima_falada", 0))
            except Exception:
                _prox = None
            if _prox:
                _pcid, _psenha, _pguiche, _pdata, _ppac, _petapa, _pfnome, _pprio, _pmanch = _prox
                _texto = _texto_chamada(_ppac, _psenha, _petapa, _pguiche, _pfnome)
                try:
                    rep_total = int(cfg.get("voz_repetir") or 0)
                    interv = int(cfg.get("voz_intervalo") or 2)
                except Exception:
                    rep_total, interv = 0, 2
                if filas.tv_claim_fala(chave_fala, _pcid, _dur_fala(_texto)):
                    estado["ultimo_id"] = _pcid
                    _falar_fila(_texto)
                    if rep_total > 0:
                        ui.timer(max(1, interv), lambda t=_texto: _rep(t, rep_total, max(1, interv)), once=True)
            if not ult:
                _falar_hora_se_hora(ultimo_id_novo=False)
                return
            _falar_hora_se_hora()

        def _fallback_noticias(titulo: str, descricao: str, fonte: str = ""):
            """Fallback elegante: o rodapé nunca fica vazio (sempre há notícia/aviso)."""
            lbl_n_titulo.text = titulo
            lbl_n_desc.text = descricao
            lbl_n_fonte.text = fonte
            try:
                lbl_n_contador.text = ""
            except Exception:
                pass

        def carregar_noticias(primeira: bool = False):
            """Curadoria: até 200 notícias, mais atuais primeiro (data_publicacao,
            fallback data_coleta); recarga traz as novas para a frente sem cortar a leitura."""
            try:
                from mod_agregador_noticias.bd_manipulador import listar_para_tv, habilitado  # type: ignore
                if not habilitado():
                    noticias_tv["lista"] = []
                    noticias_tv["idx"] = 0
                    _fallback_noticias("Notícias pausadas",
                                       "Agregador desabilitado — ative em /admin/agregador_noticias para exibir manchetes aqui",
                                       "TV Filas • sem notícias")
                    return
                lst = []
                try:
                    lst = listar_para_tv(limite=200)
                except Exception:
                    lst = []
                if lst:
                    primeira_carga = not noticias_tv["lista"]
                    noticias_tv["lista"] = lst
                    noticias_tv["idx"] = noticias_tv["idx"] % len(lst)
                    if primeira_carga or primeira:
                        _mostrar_noticia()
                    # senão mantém a leitura atual; o próximo giro exibe a lista nova
                else:
                    noticias_tv["lista"] = []
                    noticias_tv["idx"] = 0
                    _fallback_noticias("Sem manchetes no momento",
                                       "Aguarde a próxima coleta do agregador — as manchetes aparecem aqui automaticamente.",
                                       "TV Filas • sem notícias")
            except Exception:
                if not noticias_tv["lista"]:
                    try:
                        _fallback_noticias("Sem manchetes no momento",
                                           "Aguarde a próxima coleta do agregador — as manchetes aparecem aqui automaticamente.",
                                           "TV Filas • sem notícias")
                    except Exception:
                        pass

        def _mostrar_noticia():
            """Carrossel automático (15s por notícia, sem controles visíveis na TV):
            congela junto com a mídia quando a TV está pausada (pausa/retoma sozinho)."""
            lst = noticias_tv["lista"]
            if not lst:
                return
            try:
                if filas.obter_estado_tv(chave).get("pausado", 0):
                    return
            except Exception:
                pass
            idx = noticias_tv["idx"] % len(lst)
            item = lst[idx]
            titulo = (item.get("titulo", "") or "")[:140]
            desc = (item.get("descricao", "") or "")[:240]
            try:
                if desc.strip() and desc.strip() == titulo.strip():
                    desc = ""
            except Exception:
                pass
            lbl_n_titulo.text = titulo
            lbl_n_desc.text = desc
            try:
                fonte_txt = f"{item.get('fonte', '')} • {item.get('tema', '')}".strip(" •")
            except Exception:
                fonte_txt = item.get("fonte", "")
            lbl_n_fonte.text = fonte_txt
            try:
                lbl_n_contador.text = f"{idx + 1} de {len(lst)}"
            except Exception:
                pass
            noticias_tv["idx"] = (idx + 1) % len(lst)

        def rotacionar_midia():
            # corrente auto-sustentada: pausado só adia (nunca morre); erro nunca quebra a cadeia
            try:
                try:
                    paus = filas.obter_estado_tv(chave).get("pausado", 0)
                except Exception:
                    paus = 0
                if paus:
                    dur = 5.0
                else:
                    estado["slot_pos"] = (estado["slot_pos"] + 1) % max(1, len(slots))
                    dur = _render_slot()
            except Exception:
                dur = 8.0
            try:
                ui.timer(float(dur or 8), rotacionar_midia, once=True)
            except Exception:
                pass

        try:
            _d0 = float(_render_slot() or 8)
        except Exception:
            _d0 = 8.0
        refresh_chamada()
        carregar_noticias(primeira=True)
        ui.timer(3.0, refresh_chamada)
        ui.timer(15.0, _mostrar_noticia)
        ui.timer(120.0, carregar_noticias)
        try:
            ui.timer(_d0, rotacionar_midia, once=True)
        except Exception:
            pass
