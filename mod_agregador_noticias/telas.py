"""Aggregator screen — 3-column masonry, tema filter + busca, fonte_icon + 30x30 thumbnail, TV integration.

EN: Aggregator screen with 3-column masonry (column-count:3), tema select
    + busca input (debounced, NFKD normalized) side-by-side, card with
    fonte_icon (faviconV2 16×16) + imagem 30×30 thumbnail before title
    (both optional, fail-soft), badge tema + title ui.link new_tab + descricao
    + tempo relativo, pagination 10 (Primeira/Anterior/Próxima/Última),
    Coleta badge removed, async Coletar via run.io_bound, integration TV via
    listar_para_tv.

Tela do Agregador de Notícias — 3 colunas, filtro tema + busca, ícone fonte + miniatura 30×30, integração TV.

Barra com filtro tema e busca lado a lado (sem badge Coleta), card com
ícone da fonte (fonte_icon_url faviconV2 16×16) + miniatura 30×30
(imagem_url 30×30 object-cover) antes do título quando presentes, badge
tema + título link externo + descrição + tempo relativo, paginação 10
com busca em memória (500 limite, NFKD lower).
"""

import sys, os, re
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from nicegui import ui
from mod_intranet import autenticacao
from mod_intranet.aba_modulo import cabecalho
from mod_intranet.tema_modulo import ler_tema, notificar
from mod_intranet.ui_comum import botao
from mod_agregador_noticias import bd_manipulador as ag

log = __import__("mod_intranet.observabilidade", fromlist=["get_logger"]).get_logger("agregador_noticias")


def _pode_ver(user_nome, perfil):
    if perfil == "administrador_geral":
        return True
    try:
        return autenticacao.validar_acesso_modulo(user_nome, "agregador_noticias")
    except Exception:
        return False


def mostrar_tela(user_nome: str, perfil_global: str = ""):
    if not _pode_ver(user_nome, perfil_global):
        with ui.column().classes("w-full items-center p-12 gap-3"):
            ui.icon("block", size="64px").classes("text-red-8")
            ui.label("Acesso restrito").classes("text-h6")
            ui.label("Somente usuários com acesso ao Agregador de Notícias.").classes("text-body2 text-grey-7")
        return

    tema = ler_tema("agregador_noticias", cor_botao="#000000", cor_texto_botao="#FFFFFF",
                    texto_header="Notícias agregadas de múltiplas fontes — 3 colunas, clique abre no site original. Para TV do Filas, carrossel título+descrição.")
    ui.colors(primary=tema["cor_botao"])
    t_cor_titulo = tema["cor_titulo"]
    t_cor_fundo = tema["cor_fundo"]
    t_texto_header = tema["texto_header"]

    # Filtro por tema + busca
    temas = ag.temas_config()
    estado = {"tema": "", "busca": "", "pagina": 1}

    def _tempo_relativo(data_str: str) -> str:
        """Converte data ISO para texto relativo: 3 minutos atrás, 2 semanas etc."""
        if not data_str:
            return ""
        try:
            # tenta parse flexível: YYYY-MM-DD HH:MM:SS ou ISO
            s = str(data_str).strip().replace("T", " ").replace("Z", "")
            # remove fração
            s = re.split(r"\.\d+", s)[0]
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
                try:
                    dt = __import__("datetime").datetime.strptime(s[:19], fmt)
                    break
                except Exception:
                    continue
            else:
                return s[:16]
            agora = __import__("datetime").datetime.now()
            delta = agora - dt
            seg = int(delta.total_seconds())
            if seg < 0:
                seg = 0
            if seg < 60:
                return "agora"
            if seg < 3600:
                m = seg // 60
                return f"{m} minuto atrás" if m == 1 else f"{m} minutos atrás"
            if seg < 86400:
                h = seg // 3600
                return f"{h} hora atrás" if h == 1 else f"{h} horas atrás"
            if seg < 604800:
                d = seg // 86400
                return f"{d} dia atrás" if d == 1 else f"{d} dias atrás"
            if seg < 2592000:
                sem = seg // 604800
                return f"{sem} semana atrás" if sem == 1 else f"{sem} semanas atrás"
            if seg < 31536000:
                meses = seg // 2592000
                return f"{meses} mês atrás" if meses == 1 else f"{meses} meses atrás"
            anos = seg // 31536000
            return f"{anos} ano atrás" if anos == 1 else f"{anos} anos atrás"
        except Exception:
            return (data_str or "")[:16]

    def _noticia_card(n):
        # n = (id, titulo, fonte, tema, url, imagem_url, fonte_icon_url, descricao, data_pub, data_col) — 10 cols
        # compat: se ainda vier 9 cols (sem fonte_icon_url), normaliza
        if len(n) == 10:
            nid, titulo, fonte, tema_n, url, img, fonte_icon, desc, data_pub, data_col = n
        elif len(n) == 9:
            nid, titulo, fonte, tema_n, url, img, desc, data_pub, data_col = n
            fonte_icon = ""
        else:
            # fallback genérico: tenta desempacotar últimos 3 como desc/data_pub/data_col
            try:
                nid, titulo, fonte, tema_n, url = n[0], n[1], n[2], n[3], n[4]
                img = n[5] if len(n) > 5 else ""
                fonte_icon = n[6] if len(n) > 9 else ""
                desc = n[7] if len(n) == 10 else (n[6] if len(n) == 9 else "")
                data_pub = n[8] if len(n) == 10 else (n[7] if len(n) == 9 else "")
                data_col = n[9] if len(n) == 10 else (n[8] if len(n) == 9 else "")
            except Exception:
                nid, titulo, fonte, tema_n, url, img, fonte_icon, desc, data_pub, data_col = n[0], n[1] if len(n) > 1 else "", "", "", "#", "", "", "", "", ""
        href = url or "#"
        with ui.card().classes("w-full overflow-hidden hover:shadow-lg transition-shadow cursor-pointer card-noticia").style(""):
            with ui.card_section().classes("gap-2 w-full"):
                # linha 1: indicativo tema + tempo (ordem alterada)
                with ui.row().classes("w-full items-center justify-between"):
                    ui.badge(tema_n or "Geral", color="blue-grey-2").props("outline dense")
                    ui.label(_tempo_relativo(data_pub or data_col)).classes("text-caption text-grey-5")
                # linha 2: título com ícone fonte 16×16 + miniatura 30×30 antes do título
                with ui.row().classes("w-full items-start gap-2"):
                    if fonte_icon:
                        try:
                            ui.image(fonte_icon).classes("shrink-0 rounded").style("width:16px;height:16px;object-fit:contain;").props("fit=contain")
                        except Exception:
                            pass
                    if img:
                        try:
                            ui.image(img).classes("shrink-0 rounded").style("width:30px;height:30px;object-fit:cover;").props("fit=cover")
                        except Exception:
                            pass
                    try:
                        ui.link(titulo, target=href, new_tab=True).classes("font-bold text-grey-9 leading-tight hover:text-primary flex-1").style("word-break: break-word; min-width:0;")
                    except Exception:
                        ui.label(titulo).classes("font-bold text-grey-9 flex-1").style("min-width:0;")
                if desc and desc != titulo:
                    ui.label(desc[:180] + ("…" if len(desc) > 180 else "")).classes("text-caption text-grey-7")

    with ui.column().classes("w-full p-6 gap-4"):
        cabecalho("Agregador de Notícias", t_texto_header, chave_modulo="agregador_noticias",
                  cor_titulo=t_cor_titulo, cor_fundo=t_cor_fundo)

        with ui.row().classes("w-full items-center gap-3 flex-wrap bg-white rounded-lg shadow-sm px-3 py-2"):
            ui.icon("newspaper").classes("text-grey-6")
            sel_tema = ui.select({"": "Todos os temas"} | {t: t for t in temas}, value="", label="Filtrar por tema").props("outlined dense").classes("min-w-[200px]").props('data-testid=agregador-filtro-tema')
            inp_busca = ui.input(placeholder="Buscar palavra…", value="").props("outlined dense clearable debounce='300'").classes("min-w-[220px] flex-1").props('data-testid=agregador-busca')
            inp_busca.tooltip("Pesquisar entre as notícias por palavra no título/descrição")
            def _atualizar():
                grid.refresh()
            botao("Atualizar", icone="refresh", on_click=_atualizar, variante="texto", chave_modulo="agregador_noticias").props('data-testid=agregador-atualizar')
            if _pode_ver(user_nome, perfil_global) and (perfil_global == "administrador_geral" or autenticacao.eh_admin_do_modulo(user_nome, "agregador_noticias")):
                _estado_coleta = {"ocupado": False}
                async def _coletar():
                    if _estado_coleta["ocupado"]:
                        notificar("Coleta em andamento…", type="warning")
                        return
                    _estado_coleta["ocupado"] = True
                    spinner = ui.spinner(size="lg").props("aria-label=Coletando notícias")
                    try:
                        from nicegui import run as _run
                        n = await _run.io_bound(lambda: ag.coletar_todas(ator=user_nome, forcar=True))
                        notificar(f"Coleta concluída: {n} novas", type="positive" if n else "info")
                        grid.refresh()
                    except Exception as e:
                        notificar(f"Falha na coleta: {e}", type="negative")
                    finally:
                        try:
                            spinner.delete()
                        except Exception:
                            pass
                        _estado_coleta["ocupado"] = False
                botao("Coletar agora", icone="sync", on_click=_coletar, variante="primario", chave_modulo="agregador_noticias").props('data-testid=agregador-coletar')
            botao("Ver puro Noticia", icone="visibility", on_click=lambda: ui.navigate.to("/agregador-noticias-puro"), variante="contorno", chave_modulo="agregador_noticias").props('data-testid=agregador-ver-puro')

        # Paginação 10 por página, mais atual → mais antiga (ORDER BY data_publicacao DESC)
        # estado já contém pagina e busca
        @ui.refreshable
        def grid():
            tema_f = estado["tema"] or None
            busca = (estado.get("busca") or "").strip()
            # total para paginação (com busca)
            if busca:
                # busca em memória para contar filtrado (sem acentos, lower) — sobre 500 mais recentes
                todas = ag.listar_noticias(tema=tema_f, limite=500, offset=0)
                # filtra por palavra no título/descrição/fonte/tema/fonte_icon (normaliza sem acentos)
                import unicodedata
                def _norm(s):
                    s = unicodedata.normalize("NFKD", s or "").encode("ascii","ignore").decode().lower()
                    return s
                busca_n = _norm(busca)
                # índices com 10 cols: 1 titulo, 2 fonte, 3 tema, 6 fonte_icon, 7 descricao
                def _camp(n, idx):
                    try:
                        return n[idx] or ""
                    except Exception:
                        return ""
                filtradas = [
                    n for n in todas
                    if busca_n in _norm(_camp(n, 1))
                    or busca_n in _norm(_camp(n, 7) if len(n) == 10 else _camp(n, 6))
                    or busca_n in _norm(_camp(n, 2))
                    or busca_n in _norm(_camp(n, 3))
                ]
                total = len(filtradas)
            else:
                total = ag.contar_noticias(tema=tema_f)
            por_pagina = 12
            total_pag = max(1, (total + por_pagina - 1) // por_pagina)
            if estado["pagina"] > total_pag:
                estado["pagina"] = total_pag
            if estado["pagina"] < 1:
                estado["pagina"] = 1
            offset = (estado["pagina"] - 1) * por_pagina
            if busca:
                # pagina sobre filtradas
                noticias = filtradas[offset:offset+por_pagina]
            else:
                noticias = ag.listar_noticias(tema=tema_f, limite=por_pagina, offset=offset)
            if not noticias:
                with ui.card().classes("w-full p-8 items-center"):
                    ui.icon("article", size="48px").classes("text-grey-4")
                    ui.label("Nenhuma notícia ainda. Ative a coleta nas Configurações.").classes("text-grey-6")
                    if tema_f:
                        ui.label(f"Tema: {tema_f}").classes("text-caption text-grey-5")
                return
            # 3 colunas desktop / 2 tablet / 1 celular — responsivo + altura padronizada
            # CSS responsivo injetado uma vez
            ui.add_head_html("""
            <style>
            .grid-noticias { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; }
            .card-noticia { min-height: 160px; max-height: 220px; display: flex; flex-direction: column; }
            .card-noticia .q-card__section { flex: 1; display: flex; flex-direction: column; }
            @media (max-width: 1024px) { .grid-noticias { grid-template-columns: repeat(2, 1fr); } }
            @media (max-width: 640px) { .grid-noticias { grid-template-columns: 1fr; } .card-noticia { min-height: 140px; max-height: none; } }
            </style>
            """)
            with ui.element("div").classes("grid-noticias w-full"):
                for n in noticias:
                    with ui.element("div"):
                        _noticia_card(n)
            # Paginação: anterior / próxima / última
            with ui.row().classes("w-full items-center justify-between mt-3 flex-wrap gap-2"):
                with ui.row().classes("items-center gap-1"):
                    ui.button(icon="first_page", on_click=lambda: (estado.__setitem__("pagina", 1), grid.refresh())).props("flat dense").tooltip("Primeira página").props('data-testid=agregador-primeira')
                    ui.button(icon="chevron_left", on_click=lambda: (estado.__setitem__("pagina", max(1, estado["pagina"]-1)), grid.refresh())).props("flat dense").tooltip("Anterior").props('data-testid=agregador-anterior')
                    ui.label(f"Página {estado['pagina']} de {total_pag} • {total} notícias").classes("text-caption text-grey-7 mx-2")
                    ui.button(icon="chevron_right", on_click=lambda: (estado.__setitem__("pagina", min(total_pag, estado["pagina"]+1)), grid.refresh())).props("flat dense").tooltip("Próxima").props('data-testid=agregador-proxima')
                    ui.button(icon="last_page", on_click=lambda: (estado.__setitem__("pagina", total_pag), grid.refresh())).props("flat dense").tooltip("Última página").props('data-testid=agregador-ultima')
                ui.label(f"Exibindo {len(noticias)} de {total}").classes("text-caption text-grey-5")

        def _on_tema(e):
            estado["tema"] = e.value or ""
            estado["pagina"] = 1
            grid.refresh()
        sel_tema.on_value_change(_on_tema)

        def _on_busca(e):
            estado["busca"] = e.value or ""
            estado["pagina"] = 1
            grid.refresh()
        inp_busca.on_value_change(_on_busca)

        grid()
