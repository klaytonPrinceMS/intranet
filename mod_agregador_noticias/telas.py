"""EN: Aggregator screen — fixed-height 3-column grid, tema filter + busca, 120x120 thumbnail, TV integration.

PT-BR: Tela do Agregador de Notícias — grid de 3 colunas com card de altura fixa, filtro tema + busca, miniatura 120×120, integração TV.

Barra com filtro tema e busca lado a lado (sem badge Coleta) e grid
responsivo 3→2→1 colunas com card de ALTURA FIXA (300px desktop/260px
celular — `height`, nunca `min/max-height`, para todos os cards ficarem
uniformes). Cada card traz: badge do tema + tempo relativo no topo;
miniatura da notícia em 120×120 px (`object-fit: cover`) que, ao clicar
(ou ENTER), abre a AMPLIAÇÃO em diálogo `dialogo_card` com a imagem em
60vw×60vh (`object-fit: contain`, fecha por ESC); o logo da fonte
(`fonte_icon_url` faviconV2) aparece como MARCA D'ÁGUA no rodapé da
imagem (inferior direito, 32×32, opacidade 0.65, `pointer-events: none`
e `drop-shadow` para destacar sobre qualquer foto) — sem imagem, cai
como ícone 16×16 ao lado do badge; título em link externo; e o resumo
(descrição) em caixa de altura fixa com `overflow-y: auto`, ou seja, o
texto NÃO é mais truncado com reticências. A moldura da imagem é irmã
do link do título (nunca ancestral) e o clique usa o modificador nativo
`.stop` (Vue.withModifiers), logo ampliar nunca navega para o site
original. Paginação 12 por página com busca em memória (500 limite,
NFKD lower).
"""

import sys, os, re
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from nicegui import ui
from mod_intranet import autenticacao
from mod_intranet.aba_modulo import cabecalho
from mod_intranet.tema_modulo import ler_tema, notificar
from mod_intranet.ui_comum import botao, dialogo_card
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

    def _desempacotar_noticia(n):
        """Normaliza o registro da notícia nos 10 campos de `tb_noticia`.

        Recebe a linha desempacotada do `bd_manipulador` (id, titulo,
        fonte, tema, url, imagem_url, fonte_icon_url, descricao,
        data_publicacao, data_coleta) e devolve SEMPRE a mesma tupla de 10
        posições, aceitando registros antigos de 9 colunas (sem
        `fonte_icon_url`) ou linhas curtas/incompletas. Nunca levanta
        exceção: linha ilegível vira registro vazio (fail-soft).
        """
        try:
            campos = list(n) if n is not None else []
        except Exception as e:
            log.warning(f"_desempacotar_noticia: registro ilegível, usando vazio ({e})")
            campos = []
        if len(campos) >= 10:
            return tuple(campos[:10])
        if len(campos) == 9:
            return (campos[0], campos[1], campos[2], campos[3], campos[4],
                    campos[5], "", campos[6], campos[7], campos[8])
        return tuple((campos + [""] * 10)[:10])

    def _criar_dialogo_noticia(img, titulo, fonte):
        """Cria (sem abrir) o diálogo de ampliação; devolve o `ui.dialog` ou `None`.

        Diálogo padronizado do projeto (`dialogo_card`: cartão com o estilo
        do módulo, fecha por ESC e por clique fora) contendo a imagem em
        60vw×60vh com `object-fit: contain` (não distorce nem corta), `alt`
        descritivo para acessibilidade e botão "Fechar" sempre visível.
        Falha ao montar avisa via `notificar` e registra no log — nunca
        derruba o cliente (AGENTS.md §3.2).
        """
        try:
            with dialogo_card(titulo=(titulo or "Notícia")[:90],
                              largura="w-full max-w-[94vw] mx-4",
                              chave_modulo="agregador_noticias",
                              max_altura=False) as (dlg, card):
                with ui.column().classes("w-full items-center").style("gap: 0.5rem"):
                    ampliada = ui.image(img).classes("dlg-noticia__img").props("fit=contain")
                    # alt/aria-label descritivos (o texto pode ter aspas: vai
                    # pelo dicionário de props, que não precisa de escape)
                    ampliada.props["alt"] = f"Imagem ampliada da notícia: {titulo or 'sem título'}"
                    if fonte:
                        lbl_fonte = ui.label(fonte).classes("text-caption text-grey-6")
                        lbl_fonte.props["aria-label"] = f"Fonte: {fonte}"
                    with ui.row().classes("w-full justify-end"):
                        botao("Fechar", icone="close", on_click=dlg.close,
                              variante="primario", compacto=True,
                              chave_modulo="agregador_noticias")
            return dlg
        except Exception:
            log.exception(f"_criar_dialogo_noticia: falha ao criar ampliação da notícia {titulo!r}")
            notificar("Não foi possível ampliar a imagem da notícia.", type="negative")
            return None

    def _abrir_dialogo_noticia(cache, img, titulo, fonte):
        """Abre a ampliação da notícia, memoizando o diálogo no `cache` do card.

        O diálogo só é montado no PRIMEIRO clique (evita baixar a imagem
        grande para as 12 notícias da página) e reaproveitado nos cliques
        seguintes, para não acumular diálogos/imagens no DOM. Falha avisa
        via `notificar` e registra no log (fail-soft, AGENTS.md §3.2).
        """
        try:
            if cache.get("dlg") is None:
                cache["dlg"] = _criar_dialogo_noticia(img, titulo, fonte)
            dlg = cache.get("dlg")
            if dlg is not None:
                dlg.open()
        except Exception:
            log.exception(f"_abrir_dialogo_noticia: falha ao ampliar imagem da notícia {titulo!r}")
            notificar("Não foi possível ampliar a imagem da notícia.", type="negative")

    def _midia_noticia(img, fonte_icon, titulo, fonte, testeid=""):
        """Moldura 120×120 da miniatura + marca d'água da fonte (clique amplia).

        A miniatura (`imagem_url`) ocupa 120×120 px com `object-fit: cover`
        e o logo da fonte (`fonte_icon_url`) fica como marca d'água no
        rodapé da imagem — inferior direito, 32×32, opacidade 0.65,
        `pointer-events: none` e `drop-shadow` (claro + escuro) para
        destacar sobre qualquer foto sem atrapalhar a leitura. O clique,
        assim como ENTER/ESPAÇO no teclado, abre o diálogo de
        ampliação (montado só no 1º clique e reaproveitado depois); a
        dica é "Ampliar imagem". A moldura é IRMÃ do link do título
        (nunca ancestral dele) e o clique usa o modificador nativo
        `.stop`, então ampliar nunca navega para o site original.
        """
        alvo = None
        cache = {"dlg": None}  # diálogo de ampliação memoizado por card
        with ui.element("div").classes("card-noticia__midia").style("cursor: zoom-in") as alvo:
            alvo.props["role"] = "button"
            alvo.props["tabindex"] = "0"
            alvo.props["aria-label"] = f"Ampliar imagem da notícia: {titulo or 'sem título'}"
            if testeid:
                alvo.props["data-testid"] = testeid
            try:
                ui.image(img).classes("card-noticia__foto").props("fit=cover")
            except Exception:
                log.warning(f"_midia_noticia: miniatura inválida para {titulo!r}")
                ui.label("🖼").classes("card-noticia__sem-foto")
            if fonte_icon:
                try:
                    ui.image(fonte_icon).classes("card-noticia__marca").props("fit=contain")
                except Exception:
                    log.warning(f"_midia_noticia: marca d'água da fonte inválida para {titulo!r}")

        def _ampliar(_=None):
            _abrir_dialogo_noticia(cache, img, titulo, fonte)

        # `.stop` e `.enter`/`.space` são os MODIFICADORES NATIVOS do NiceGUI
        # (Vue.withModifiers/withKeys — nada de JavaScript escrito à mão):
        # o `.stop` impede a propagação do clique, então ampliar NUNCA aciona
        # a navegação do link do título nem um handler de clique do card.
        alvo.on("click.stop", _ampliar)
        alvo.on("keydown.enter", _ampliar)
        alvo.on("keydown.space", _ampliar)
        alvo.tooltip("Ampliar imagem")
        return alvo

    def _noticia_card(n):
        """Monta o card da notícia: altura fixa, miniatura 120×120 e resumo com scroll.

        Card de ALTURA FIXA (300px desktop / 260px celular, via CSS
        `.card-noticia`), para que todos os cards da linha fiquem
        idênticos: topo com badge do tema + tempo relativo, corpo com a
        miniatura 120×120 (marca d'água da fonte, clique amplia em
        diálogo) ao lado da coluna de texto com o título em link externo
        e o RESUMO completo em caixa de altura fixa com `overflow-y: auto`
        — a descrição nunca mais é truncada com reticências. A moldura da
        imagem é irmã do link (nunca o contém) e o clique usa o
        modificador nativo `.stop`, então o clique na imagem só abre a
        ampliação. Falha ao montar registra no log e avisa via
        `notificar` (fail-soft).
        """
        try:
            nid, titulo, fonte, tema_n, url, img, fonte_icon, desc, data_pub, data_col = _desempacotar_noticia(n)
            href = url or "#"
            texto = str(titulo or "").strip() or "Notícia sem título"
            # data-testid estável por notícia (QA/kbp-qa)
            tid = f"agregador-ampliar-{nid}" if str(nid).strip().isalnum() else "agregador-ampliar"
            with ui.card().classes("w-full hover:shadow-lg transition-shadow card-noticia"):
                # ---- topo: tema + tempo relativo (ícone da fonte só quando não há imagem) ----
                with ui.card_section().classes("card-noticia__topo"):
                    with ui.row().classes("w-full items-center justify-between").style("gap: 0.5rem"):
                        with ui.row().classes("items-center").style("gap: 0.375rem"):
                            if fonte_icon and not img:
                                try:
                                    ui.image(fonte_icon).classes("card-noticia__fonte").props("fit=contain")
                                except Exception:
                                    pass
                            ui.badge(tema_n or "Geral", color="blue-grey-2").props("outline dense")
                        ui.label(_tempo_relativo(data_pub or data_col)).classes("text-caption text-grey-5")
                # ---- corpo: miniatura 120×120 (ampliável) + título + resumo com scroll ----
                with ui.card_section().classes("card-noticia__corpo"):
                    if img:
                        _midia_noticia(img, fonte_icon, texto, fonte, testeid=tid)
                    with ui.column().classes("card-noticia__texto"):
                        try:
                            ui.link(texto, target=href, new_tab=True).classes(
                                "card-noticia__titulo hover:text-primary")
                        except Exception:
                            ui.label(texto).classes("card-noticia__titulo")
                        # resumo: texto COMPLETO com scroll — nunca truncado
                        if desc and str(desc).strip() and str(desc).strip() != texto:
                            ui.label(str(desc)).classes("card-noticia__resumo")
                        else:
                            ui.label("Sem resumo disponível.").classes("card-noticia__resumo text-grey-5")
        except Exception:
            log.exception(f"_noticia_card: falha ao montar card da notícia {n!r}")
            notificar("Não foi possível montar o card desta notícia.", type="negative")

    with ui.column().classes("w-full p-6 gap-4"):
        cabecalho("Agregador de Notícias", t_texto_header, chave_modulo="agregador_noticias",
                  cor_titulo=t_cor_titulo, cor_fundo=t_cor_fundo)

        with ui.row().classes("w-full items-center gap-3 flex-wrap bg-white rounded-lg shadow-sm px-3 py-2"):
            ui.icon("newspaper").classes("text-grey-6")
            sel_tema = ui.select({"": "Todos os temas"} | {t: t for t in temas}, value="", label="Filtrar por tema").props("outlined dense").classes("min-w-[200px]").props('data-testid=agregador-filtro-tema')
            inp_busca = ui.input(placeholder="Buscar palavra…", value="").props("outlined dense clearable debounce='300'").classes("min-w-[220px] flex-1").props('data-testid=agregador-busca')
            inp_busca.tooltip("Pesquisar em todos os temas por palavra no título/descrição/fonte")
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

        # Paginação 10 por página, mais atual → mais antiga (ORDER BY data_publicacao DESC)
        # estado já contém pagina e busca

        # CSS do grid injetado UMA vez por página (fora do @ui.refreshable, para
        # não duplicar o <style> a cada refresh da busca/paginação).
        ui.add_head_html("""
        <style>
        .grid-noticias { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; }
        /* card de ALTURA FIXA: todos os cards da linha idênticos (nunca min/max) */
        .card-noticia { height: 300px; display: flex; flex-direction: column; }
        .card-noticia .q-card__section { min-height: 0; padding: 0; }
        /* prefixo `.card-noticia` para vencer o `.column` do Quasar (mesma
           especificidade) sem depender da ordem de injeção dos <style> */
        .card-noticia .card-noticia__topo { flex: 0 0 auto; display: flex; flex-direction: column; padding: 12px 16px 6px; }
        .card-noticia .card-noticia__corpo { flex: 1 1 auto; display: flex; flex-direction: row; align-items: stretch; padding: 0 16px 14px; gap: 0.75rem; }
        .card-noticia .card-noticia__texto { flex: 1 1 auto; min-width: 0; min-height: 0; display: flex; flex-direction: column; gap: 0.375rem; }
        .card-noticia .card-noticia__titulo { font-weight: 700; color: #212121; line-height: 1.25; word-break: break-word; min-width: 0; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
        /* resumo: caixa de ALTURA FIXA com scroll — o texto nunca é cortado */
        .card-noticia .card-noticia__resumo { flex: 1 1 auto; min-height: 0; overflow-y: auto; overflow-x: hidden; padding-right: 4px; font-size: 0.75rem; line-height: 1.35; color: #616161; white-space: pre-wrap; scrollbar-width: thin; }
        .card-noticia .card-noticia__resumo::-webkit-scrollbar { width: 5px; }
        .card-noticia .card-noticia__resumo::-webkit-scrollbar-thumb { background: #bdbdbd; border-radius: 4px; }
        .card-noticia .card-noticia__resumo::-webkit-scrollbar-track { background: transparent; }
        /* miniatura 120x120 */
        .card-noticia .card-noticia__midia { position: relative; flex: 0 0 120px; width: 120px; height: 120px; align-self: flex-start; }
        .card-noticia .card-noticia__midia:focus-visible { outline: 2px solid #1565C0; outline-offset: 2px; border-radius: 8px; }
        .card-noticia .card-noticia__foto { display: block; width: 100%; height: 100%; border-radius: 8px; box-shadow: inset 0 0 0 1px rgba(0,0,0,0.10); }
        .card-noticia .card-noticia__foto .q-img__image img { object-fit: cover; }
        .card-noticia .card-noticia__sem-foto { font-size: 32px; opacity: .35; }
        .card-noticia .card-noticia__fonte { width: 16px; height: 16px; flex: 0 0 16px; }
        .card-noticia .card-noticia__fonte .q-img__image img { object-fit: contain; }
        /* marca d'água: logo da fonte no rodapé da imagem (inferior direito) */
        .card-noticia .card-noticia__marca { position: absolute; right: 4px; bottom: 4px; width: 32px; height: 32px; opacity: .65; pointer-events: none; z-index: 2; }
        .card-noticia .card-noticia__marca .q-img__image img { object-fit: contain; filter: drop-shadow(0 1px 3px rgba(0,0,0,0.95)) drop-shadow(0 0 1px rgba(255,255,255,0.85)); }
        /* diálogo de ampliação: imagem em ~60% da tela */
        .dlg-noticia__img { display: block; width: 60vw; height: 60vh; max-width: 94vw; border-radius: 8px; }
        .dlg-noticia__img .q-img__image img { object-fit: contain; }
        @media (max-width: 1024px) { .grid-noticias { grid-template-columns: repeat(2, 1fr); } }
        @media (max-width: 640px) { .grid-noticias { grid-template-columns: 1fr; } .card-noticia { height: 260px; } .dlg-noticia__img { width: 88vw; height: 58vh; } }
        </style>
        """)

        @ui.refreshable
        def grid():
            tema_f = estado["tema"] or None
            busca = (estado.get("busca") or "").strip()
            # total para paginação (com busca)
            if busca:
                # busca global: ignora o filtro de tema (vale para todos os temas,
                # pois notícias de termo livre caem em "Geral" e sumiriam do resultado)
                todas = ag.listar_noticias(tema=None, limite=500, offset=0)
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
            total_pag = max(1, (total + por_pagina) // por_pagina)
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
                    if busca:
                        ui.label(f'Nenhuma notícia para "{busca}" (busca em todos os temas).').classes("text-grey-6")
                    else:
                        ui.label("Nenhuma notícia ainda. Ative a coleta nas Configurações.").classes("text-grey-6")
                    if tema_f and not busca:
                        ui.label(f"Tema: {tema_f}").classes("text-caption text-grey-5")
                return
            # 3 colunas desktop / 2 tablet / 1 celular — responsivo + card de ALTURA FIXA
            # (o CSS é injetado uma única vez, fora do @ui.refreshable, logo abaixo)
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
