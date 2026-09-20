"""Tela do Agregador de Notícias — 3 colunas, link externo, integração TV.

EN: Aggregator screen — 3 columns, external link, TV integration.
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

    # Filtro por tema
    temas = ag.temas_config()
    estado = {"tema": ""}

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
        # n = (id, titulo, fonte, tema, url, imagem_url, descricao, data_pub, data_coleta)
        nid, titulo, fonte, tema_n, url, img, desc, data_pub, data_col = n
        href = url or "#"
        with ui.card().classes("w-full overflow-hidden hover:shadow-lg transition-shadow cursor-pointer").style("break-inside: avoid;"):
            if img:
                try:
                    ui.image(img).classes("w-full h-40 object-cover").props("fit=cover")
                except Exception:
                    pass
            with ui.card_section().classes("gap-1 w-full"):
                ui.badge(tema_n or "Geral", color="blue-grey-2").props("outline dense")
                try:
                    ui.link(titulo, target=href, new_tab=True).classes("font-bold text-grey-9 leading-tight hover:text-primary").style("display:block; word-break: break-word;")
                except Exception:
                    ui.label(titulo).classes("font-bold text-grey-9")
                if desc and desc != titulo:
                    ui.label(desc[:180] + ("…" if len(desc) > 180 else "")).classes("text-caption text-grey-7")
                with ui.row().classes("w-full items-center justify-between mt-1"):
                    # fonte removida conforme solicitado — apenas tempo relativo
                    ui.label(_tempo_relativo(data_pub or data_col)).classes("text-caption text-grey-5")
                # clique no card também abre
                def _abrir():
                    try:
                        ui.run_javascript(f"window.open('{href}', '_blank')")
                    except Exception:
                        pass
            # miniatura já exibida via ui.image acima quando há imagem;
            # título clicável (ui.link) abre a notícia externa — botão removido conforme solicitado
            # fallback: sem botão, clique no título basta

    with ui.column().classes("w-full p-6 gap-4"):
        cabecalho("Agregador de Notícias", t_texto_header, chave_modulo="agregador_noticias",
                  cor_titulo=t_cor_titulo, cor_fundo=t_cor_fundo)

        with ui.row().classes("w-full items-center gap-3 flex-wrap bg-white rounded-lg shadow-sm px-3 py-2"):
            ui.icon("newspaper").classes("text-grey-6")
            sel_tema = ui.select({"": "Todos os temas"} | {t: t for t in temas}, value="", label="Filtrar por tema").props("outlined dense").classes("min-w-[220px]").props('data-testid=agregador-filtro-tema')
            ui.label(f"Coleta: {'ativa' if ag.habilitado() else 'desabilitada'} • intervalo {ag.intervalo_min()} min • {ag.contar_noticias()} notícias (24h)").classes("text-caption text-grey-6")
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

            def _on_tema(e):
                estado["tema"] = e.value or ""
                grid.refresh()
            sel_tema.on_value_change(_on_tema)

        @ui.refreshable
        def grid():
            tema_f = estado["tema"] or None
            noticias = ag.listar_noticias(tema=tema_f, limite=45)
            if not noticias:
                with ui.card().classes("w-full p-8 items-center"):
                    ui.icon("article", size="48px").classes("text-grey-4")
                    ui.label("Nenhuma notícia ainda. Ative a coleta nas Configurações.").classes("text-grey-6")
                    if tema_f:
                        ui.label(f"Tema: {tema_f}").classes("text-caption text-grey-5")
                return
            # 3 colunas via CSS columns (masonry) — responsivo
            with ui.element("div").classes("w-full").style("column-count: 3; column-gap: 1rem;"):
                for n in noticias:
                    with ui.element("div").style("break-inside: avoid; margin-bottom: 1rem;"):
                        _noticia_card(n)
            # fallback grid para mobile
            # CSS já garante 3 colunas no desktop; NiceGUI will render

        grid()
