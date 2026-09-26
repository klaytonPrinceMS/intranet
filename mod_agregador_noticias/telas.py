"""EN: Aggregator screen — fixed-height 3-column grid, ONE scroll per card, TV integration.

PT-BR: Tela do Agregador de Notícias — grid de 3 colunas, card de altura
fixa com UM scroll só, integração TV.

Barra com filtro de tema e busca (sem botão "Atualizar": a grade se
atualiza sozinha) e grid responsivo 3 colunas (≤1024px: 2; ≤640px: 1).

CARD — altura FIXA de 250px (220px no celular; `height`, nunca
`min/max-height`, para todos ficarem uniformes). Estrutura de DUAS colunas
dentro de UM ÚNICO container com scroll (`.card-noticia__rolagem`):
  · ESQUERDA, `position: sticky` (não rola): foto 60×60 (`object-fit:
    cover`) que, ao clicar (ou ENTER), abre a AMPLIAÇÃO em diálogo
    `dialogo_card` com a imagem em 60vw×60vh (`object-fit: contain`, fecha
    por ESC); o logo da fonte (`fonte_icon_url`) como MARCA D'ÁGUA no
    rodapé da foto (inferior direito, 20×20, opacidade .50,
    `pointer-events: none` e `drop-shadow` duplo) — para fins de auditoria
    de direitos; abaixo, o tema ABREVIADO e o tempo de publicação.
  · DIREITA: título em link externo e o resumo (descrição) completo.
Como foto, título e resumo estão no MESMO container de scroll, rolar leva
os três juntos e não há caixa sobrepondo outra — o título nunca é tapado.
NENHUM texto é truncado: sem `-webkit-line-clamp`, o que não couber é
rolado. Resumo com `text-align: justify` + `hyphens: auto` para leitura
comfortável. A moldura da foto é IRMÃ do link do título (nunca ancestral)
e o clique usa o modificador nativo `.stop` (Vue.withModifiers), então
ampliar nunca navega para o site original.

MODO ESCURO: bloco `body.intranet-dark .card-noticia` inverte o contraste
(fundo escuro + texto claro) usando as variáveis do núcleo —
contraste medido 9.28:1 (WCAG AA exige 4.5:1).

TEMA RESTRITO: "Tribunais de Contas" fica fora da listagem geral e só
aparece se o usuário escolher o tema ou achá-lo pela pesquisa.

TEMPO RELATIVO: <15min "agora"; 15–59min "N min atrás"; 1–24h "Nh" /
"NhMm atrás"; >24h "N dias atrás".

"Todos os temas" mostra UMA notícia por tema, para a grade não virar um
bloco só de Esporte/Economia. Paginação com busca em memória (500
limite, NFKD lower).
"""

import sys, os, re
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from nicegui import ui, run
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
    estado = {"tema": "", "busca": "", "pagina": 1, "max_id": 0}

    # `_eh_admin` decide o que só o administrador vê/usa: a coleta manual
    # ("Coletar agora"). A atualização da tela NÃO é privilégio — é automática
    # para qualquer usuário (ui.timer, atualização parcial).
    _eh_admin = bool(
        perfil_global == "administrador_geral"
        or autenticacao.eh_admin_do_modulo(user_nome, "agregador_noticias")
    )

    # Fração de segundo para a próxima checagem automática
    _REFRESCO_SEG_MIN = 15
    _REFRESCO_SEG_MAX = 600
    _REFRESCO_SEG_PADRAO = 60

    def _tempo_relativo(data_str: str) -> str:
        """EN: Publication age — "agora" / "20 min atrás" / "1h40 atrás" / "5 dias atrás".

        PT-BR: Tempo desde a publicação — "agora" / "20 min atrás" /
        "1h40 atrás" / "5 dias atrás".

        Regras (pedido do usuário, 26/09/2026):
        • < 15 min  → "agora" (só conta como "de agora" o que é bem recente)
        • 15 min–24h → contagem em minutos até 59, depois "Nh Mm atrás"
          (ex.: "20 min atrás", "30 min atrás", "1h40 atrás")
        • > 24h    → só DIAS: "1 dia atrás", "5 dias atrás" (sem horas nem
          semanas/meses — no Agregador a notícia vive 24h, então granularidade
          maior só poluiria o rótulo)
        """
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
            # até 15 min é "agora" — a partir daí já conta o tempo
            if seg < 900:
                return "agora"
            if seg < 3600:
                m = seg // 60
                return f"{m} min atrás"
            if seg < 86400:
                h = seg // 3600
                mins = (seg % 3600) // 60
                if mins:
                    return f"{h}h{mins:02d} atrás"
                return f"{h}h atrás"
            # a partir de 1 dia: só dias
            d = seg // 86400
            return f"{d} dia atrás" if d == 1 else f"{d} dias atrás"
        except Exception:
            return (data_str or "")[:16]

    def _desempacotar_noticia(n):
        """EN: Normalizes a news row into the 10 `tb_noticia` fields.

        PT-BR: Normaliza o registro da notícia nos 10 campos de `tb_noticia`.

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
        """EN: Builds (without opening) the zoom dialog; returns the `ui.dialog` or `None`.

        PT-BR: Cria (sem abrir) o diálogo de ampliação; devolve o `ui.dialog` ou `None`.

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
        """EN: Opens the news zoom, memoizing the dialog in the card's `cache`.

        PT-BR: Abre a ampliação da notícia, memoizando o diálogo no `cache` do card.

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
        """EN: 120×120 thumbnail frame + source watermark (click zooms).

        PT-BR: Moldura 120×120 da miniatura + marca d'água da fonte (clique amplia).

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

    def _tema_curto(tema):
        """Abrevia o tema para caber no badge da coluna esquerda.

        Temas compostos viram sigla ("Ciência e Tecnologia" → "C&T",
        "Tribunais de Contas" → "Trib. Contas") e o resto é cortado em 14
        caracteres. Sem isso o badge quebrava em duas linhas e empurrava
        o tempo de publicação para fora do card."""
        t = str(tema or "Geral").strip() or "Geral"
        if len(t) <= 14:
            return t
        # abrevia palavras compostas conhecidas antes de cortar no meio
        sub = {"Ciência e Tecnologia": "C&T", "Entretenimento": "Entretenim.",
               "Tribunais de Contas": "Trib. Contas",
               "Internacional": "Internac.", "Economia": "Economia"}
        if t in sub:
            return sub[t]
        return t[:13].rstrip() + "…"

    def _noticia_card(n):
        """EN: Fixed-height news card — 2 columns, ONE scroll for everything.

        PT-BR: Card de notícia de altura fixa — 2 colunas, UM scroll só.

        Estrutura: coluna ESQUERDA fixa (foto ampliável com a marca d'água
        da fonte de origem, abaixo o tema abreviado e o tempo de
        publicação) e coluna DIREITA (título em link externo + resumo
        completo). Tudo — foto, título e resumo — está dentro de UM único
        container com `overflow-y: auto`: quem rolar leva os três juntos,
        e por não haver caixas sobrepostas o título nunca é tapado.
        Nenhum texto é truncado: o que não couber é rolado.

        A moldura da foto é irmã do link do título (nunca ancestral) e o
        clique usa o modificador nativo `.stop`, então ampliar nunca
        navega para o site original. A marca d'água da fonte fica no
        rodapé direito da foto com opacidade .50 — identifica a origem
        para fins de auditoria sem atrapalhar a leitura da imagem.
        Falha ao montar registra no log e avisa via `notificar`
        (fail-soft).
        """
        try:
            nid, titulo, fonte, tema_n, url, img, fonte_icon, desc, data_pub, data_col = _desempacotar_noticia(n)
            href = url or "#"
            texto = str(titulo or "").strip() or "Notícia sem título"
            # data-testid estável por notícia (QA/kbp-qa)
            tid = f"agregador-ampliar-{nid}" if str(nid).strip().isalnum() else "agregador-ampliar"
            # O `with ui.card() as _card:` precisa ENVOLVER o corpo INTEIRO:
            # é ele que torna o card o slot pai. Se as seções forem criadas
            # DEPOIS do bloco, saem irmãs do card (fora dele) e o CSS
            # `.card-noticia .card-noticia__*` deixa de casar — aí a
            # miniatura fica com o tamanho nativo da imagem e o resumo
            # herda fundo escuro com texto escuro (ilegível).
            with ui.card() as _card:
                _card.classes("w-full hover:shadow-lg transition-shadow card-noticia")
                # ---- ÚNICO container com scroll: imagem + título + resumo rolam
                # juntos, então não há caixa sobrepondo outra (o título nunca
                # é tapado). Duas colunas: ESQUERDA fixa (foto + tema + tempo),
                # DIREITA rola (título + resumo).
                with ui.element("div").classes("card-noticia__rolagem"):
                    # ---- coluna ESQUERDA: foto (ampliável) + tema + tempo ----
                    with ui.column().classes("card-noticia__esq").style("gap: 0.25rem"):
                        if img:
                            _midia_noticia(img, fonte_icon, texto, fonte, testeid=tid)
                        elif fonte_icon:
                            # sem foto: o logo da fonte ocupa o lugar, com a
                            # marca d'água de origem preservada
                            try:
                                ui.image(fonte_icon).classes("card-noticia__fonte-slot").props("fit=contain")
                            except Exception:
                                pass
                        ui.badge(_tema_curto(tema_n), color="blue-grey-2").props("outline dense no-wrap")
                        ui.label(_tempo_relativo(data_pub or data_col)).classes("text-caption text-grey-5 no-wrap")
                    # ---- coluna DIREITA: título + resumo ----
                    with ui.column().classes("card-noticia__dir").style("gap: 0.25rem"):
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
            return _card
        except Exception:
            log.exception(f"_noticia_card: falha ao montar card da notícia {n!r}")
            notificar("Não foi possível montar o card desta notícia.", type="negative")
            return None

    with ui.column().classes("w-full p-6 gap-4"):
        cabecalho("Agregador de Notícias", t_texto_header, chave_modulo="agregador_noticias",
                  cor_titulo=t_cor_titulo, cor_fundo=t_cor_fundo)

        with ui.row().classes("w-full items-center gap-3 flex-wrap bg-white rounded-lg shadow-sm px-3 py-2"):
            ui.icon("newspaper").classes("text-grey-6")
            sel_tema = ui.select({"": "Todos os temas"} | {t: t for t in temas}, value="", label="Filtrar por tema").props("outlined dense").classes("min-w-[200px]").props('data-testid=agregador-filtro-tema')
            inp_busca = ui.input(placeholder="Buscar palavra…", value="").props("outlined dense clearable debounce='300'").classes("min-w-[220px] flex-1").props('data-testid=agregador-busca')
            inp_busca.tooltip("Pesquisar em todos os temas por palavra no título/descrição/fonte")
            # SEM botão "Atualizar": desde 26/09/2026 a grade se atualiza SOZINHA
            # (ui.timer com atualização parcial — só o card novo entra). O
            # administrador não precisa mais clicar para ver novidade.
            lbl_auto = ui.label().classes("text-caption text-grey-6")
            if _eh_admin:
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
                        _reforcar_grid()
                    except Exception as e:
                        log.exception("_coletar: falha na coleta manual")
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
        .card-noticia { height: 250px; display: flex; flex-direction: column; background: #ffffff !important; }
        .card-noticia .q-card__section { min-height: 0; padding: 0; }
        /* UM ÚNICO container de scroll: foto, título e resumo rolam juntos.
           Sem caixas sobrepostas, o título nunca é tapado (o bug anterior). */
        .card-noticia .card-noticia__rolagem { flex: 1 1 auto; min-height: 0; overflow-y: auto; overflow-x: hidden; display: flex; flex-direction: row; align-items: flex-start; gap: 0.6rem; padding: 10px 12px 12px; scrollbar-width: thin; }
        .card-noticia .card-noticia__rolagem::-webkit-scrollbar { width: 5px; }
        .card-noticia .card-noticia__rolagem::-webkit-scrollbar-thumb { background: #bdbdbd; border-radius: 4px; }
        .card-noticia .card-noticia__rolagem::-webkit-scrollbar-track { background: transparent; }
        /* ---- MODO ESCURO (body.intranet-dark) ----
           Sem isto o card ficava com `background:#ffffff !important` e texto
           #212121/#424242 (cores do tema claro) sobre fundo escuro: o título
           sumia e o resumo ficava apagado. Aqui o contraste é invertido de
           verdade — fundo escuro + texto claro, usando as variáveis que o
           núcleo (`mod_intranet/telas.py::_aplicar_tema_escuro`) publica. */
        body.intranet-dark .card-noticia { background: var(--fundo-card, #1e1e1e) !important; color: var(--texto-card, #e8e8e8); border: 1px solid rgba(255,255,255,0.10); }
        body.intranet-dark .card-noticia .card-noticia__titulo { color: var(--cor-titulo, #ffffff) !important; }
        body.intranet-dark .card-noticia .card-noticia__resumo { color: var(--texto-modulo, #c9c9c9) !important; }
        body.intranet-dark .card-noticia .card-noticia__resumo a,
        body.intranet-dark .card-noticia .card-noticia__resumo span { color: var(--texto-modulo, #c9c9c9) !important; }
        body.intranet-dark .card-noticia .card-noticia__titulo:hover { color: #90caf9 !important; }
        body.intranet-dark .card-noticia .card-noticia__rolagem::-webkit-scrollbar-thumb { background: #6a6a6a; }
        body.intranet-dark .card-noticia .card-noticia__foto { box-shadow: inset 0 0 0 1px rgba(255,255,255,0.18); }
        body.intranet-dark .card-noticia .card-noticia__sem-foto { opacity: .5; }
        /* coluna ESQUERDA: foto + tema + tempo. Fixa: NÃO rola com o texto. */
        .card-noticia .card-noticia__esq { flex: 0 0 72px; width: 72px; position: sticky; top: 0; align-items: flex-start; }
        /* coluna DIREITA: título + resumo (rolam com o container único) */
        .card-noticia .card-noticia__dir { flex: 1 1 auto; min-width: 0; display: flex; flex-direction: column; align-items: flex-start; }
        /* título: NUNCA truncado nem rolado sozinho — o scroll é do card
           inteiro, então o título sempre aparece e rola junto do resumo.
           `hyphens: auto` + entrelinha 1.3 evitam palavras quebradas. */
        .card-noticia .card-noticia__titulo { font-weight: 700; font-size: 0.9rem; color: #212121 !important; background: transparent; line-height: 1.3; word-break: normal; overflow-wrap: break-word; hyphens: auto; min-width: 0; max-width: 100%; margin: 0; }
        /* resumo: leitura confortável — fonte maior, entrelinha ampla e
           alinhamento justified (as bordas ficam retas, sem "rio de
           palavras"). `hyphens: auto` evita buracos Huge AO breakar.
           Cor explícita: o fundo do card é branco (sem isso o texto herdava
           fundo escuro do tema e ficava preto sobre preto). */
        .card-noticia .card-noticia__resumo { font-size: 0.78rem; line-height: 1.5; color: #424242 !important; background: transparent; white-space: pre-wrap; word-break: normal; overflow-wrap: break-word; hyphens: auto; text-align: justify; text-justify: inter-word; margin: 0; min-width: 0; max-width: 100%; }
        .card-noticia .card-noticia__resumo a, .card-noticia .card-noticia__resumo span { color: #424242 !important; }
        /* miniatura 60x60 na coluna esquerda */
        .card-noticia .card-noticia__midia { position: relative; flex: 0 0 60px; width: 60px; height: 60px; }
        .card-noticia .card-noticia__midia:focus-visible { outline: 2px solid #1565C0; outline-offset: 2px; border-radius: 8px; }
        .card-noticia .card-noticia__foto { display: block; width: 100%; height: 100%; border-radius: 6px; box-shadow: inset 0 0 0 1px rgba(0,0,0,0.10); }
        .card-noticia .card-noticia__foto .q-img__image img { object-fit: cover; }
        .card-noticia .card-noticia__sem-foto { font-size: 20px; opacity: .35; }
        /* logo da fonte quando a notícia não tem foto */
        .card-noticia .card-noticia__fonte-slot { width: 28px; height: 28px; opacity: .8; }
        .card-noticia .card-noticia__fonte-slot .q-img__image img { object-fit: contain; }
        /* marca d'água: logo da fonte no rodapé da foto (inferior direito).
           opacidade .50 — dá para identificar a fonte sem atrapalhar a
           leitura da imagem (o drop-shadow duplo garante contraste em
           foto clara e em foto escura). */
        .card-noticia .card-noticia__marca { position: absolute; right: 2px; bottom: 2px; width: 20px; height: 20px; opacity: .5; pointer-events: none; z-index: 2; }
        .card-noticia .card-noticia__marca .q-img__image img { object-fit: contain; filter: drop-shadow(0 1px 3px rgba(0,0,0,0.95)) drop-shadow(0 0 1px rgba(255,255,255,0.85)); }
        /* diálogo de ampliação: imagem em ~60% da tela (o tamanho grande só
           aparece aqui — no card ela é 60×60) */
        .dlg-noticia__img { display: block; width: 60vw; height: 60vh; max-width: 94vw; border-radius: 8px; }
        .dlg-noticia__img .q-img__image img { object-fit: contain; }
        @media (max-width: 1024px) { .grid-noticias { grid-template-columns: repeat(2, 1fr); } }
        @media (max-width: 640px) { .grid-noticias { grid-template-columns: 1fr; } .card-noticia { height: 220px; } .dlg-noticia__img { width: 88vw; height: 58vh; } }
        </style>
        """)

        # ================================================================
        # GRADE com containers PERSISTENTES
        # O `@ui.refreshable` é mantido só como API para busca/filtro/
        # paginação. A grade em si vive em `grid_box`, que o `ui.timer`
        # consegue PREPENDER sem redesenhar tudo (atualização parcial).
        # ================================================================
        grid_box = ui.element("div").classes("grid-noticias w-full")
        pag_box = ui.element("div").classes("w-full")
        vazio_box = ui.element("div").classes("w-full")

        def _reforcar_grid():
            """Redesenha a grade inteira (busca/filtro/paginação/coleta manual)."""
            try:
                grid.refresh()
            except Exception:
                log.exception("grid: falha ao redesenhar a grade")

        @ui.refreshable
        def grid():
            tema_f = estado["tema"] or None
            busca = (estado.get("busca") or "").strip()
            # total para paginação (com busca)
            if busca:
                # Busca do usuário: ÚNICO caso, junto com a seleção do tema,
                # em que o público restrito (Tribunais de Contas) pode
                # aparecer. A busca é deliberada — sem `excluir_restritos`
                # ela vasculha a base toda, temas restritos inclusive.
                todas = ag.listar_noticias(tema=None, limite=500, offset=0,
                                           excluir_restritos=False)
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
            if tema_f:
                por_pagina = 12
            else:
                # "Todos os temas": UMA notícia por tema, para a grade não virar
                # um bloco só de Esporte/Economia com as demais soterradas.
                # O teto de 12 dá no máximo 1 card por tema; se houver mais
                # temas que 12, a paginação leva o restante.
                por_pagina = max(12, len(temas))
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
                if tema_f:
                    noticias = ag.listar_noticias(tema=tema_f, limite=por_pagina, offset=offset)
                else:
                    # AMOSTRA POR TEMA (1 por tema): agrupa a lista geral
                    # preservando a ordem cronológica e fica só com a primeira
                    # ocorrência de cada tema. Contagem/paginação seguem pelo
                    # total real, então os próximos temas entram na página 2.
                    _vistos, _amostra = set(), []
                    for _n in ag.listar_noticias(tema=None, limite=600, offset=0):
                        _t = _n[3]
                        if _t in _vistos:
                            continue
                        _vistos.add(_t)
                        _amostra.append(_n)
                    noticias = _amostra[offset:offset + 12]
            if not noticias:
                with vazio_box:
                    vazio_box.clear()
                    with ui.card().classes("w-full p-8 items-center"):
                        ui.icon("article", size="48px").classes("text-grey-4")
                        if busca:
                            ui.label(f'Nenhuma notícia para "{busca}" (busca em todos os temas).').classes("text-grey-6")
                        else:
                            ui.label("Nenhuma notícia ainda. A coleta é automática — aguarde o primeiro ciclo ou peça ao administrador.").classes("text-grey-6")
                            ui.label(f"Coleta a cada {ag.intervalo_min()} min.").classes("text-caption text-grey-5")
                        if tema_f and not busca:
                            ui.label(f"Tema: {tema_f}").classes("text-caption text-grey-5")
                return
            # marca d'água da tela: o timer compara contra isso para saber
            # se apareceu notícia nova sem carregar linhas
            _marca = ag.marca_ultimo_coletado()
            if _marca:
                estado["max_id"] = max(estado["max_id"], _marca[1])
            # 3 colunas desktop / 2 tablet / 1 celular — responsivo + card de ALTURA FIXA
            # (o CSS é injetado uma única vez, fora do @ui.refreshable, logo abaixo)
            with grid_box:
                grid_box.clear()
                for n in noticias:
                    with ui.element("div"):
                        _noticia_card(n)
            # Paginação: anterior / próxima / última
            with pag_box:
                pag_box.clear()
                with ui.row().classes("w-full items-center justify-between mt-3 flex-wrap gap-2"):
                    with ui.row().classes("items-center gap-1"):
                        ui.button(icon="first_page", on_click=lambda: (estado.__setitem__("pagina", 1), _reforcar_grid())).props("flat dense").tooltip("Primeira página").props('data-testid=agregador-primeira')
                        ui.button(icon="chevron_left", on_click=lambda: (estado.__setitem__("pagina", max(1, estado["pagina"]-1)), _reforcar_grid())).props("flat dense").tooltip("Anterior").props('data-testid=agregador-anterior')
                        ui.label(f"Página {estado['pagina']} de {total_pag} • {total} notícias").classes("text-caption text-grey-7 mx-2")
                        ui.button(icon="chevron_right", on_click=lambda: (estado.__setitem__("pagina", min(total_pag, estado["pagina"]+1)), _reforcar_grid())).props("flat dense").tooltip("Próxima").props('data-testid=agregador-proxima')
                        ui.button(icon="last_page", on_click=lambda: (estado.__setitem__("pagina", total_pag), _reforcar_grid())).props("flat dense").tooltip("Última página").props('data-testid=agregador-ultima')
                    ui.label(f"Exibindo {len(noticias)} de {total}").classes("text-caption text-grey-5")

        def _on_tema(e):
            estado["tema"] = e.value or ""
            estado["pagina"] = 1
            _reforcar_grid()
        sel_tema.on_value_change(_on_tema)

        def _on_busca(e):
            estado["busca"] = e.value or ""
            estado["pagina"] = 1
            _reforcar_grid()
        inp_busca.on_value_change(_on_busca)

        # ================================================================
        # ATUALIZAÇÃO AUTOMÁTICA (parcial) — o usuário não clica em nada
        # ================================================================
        def _rotulo_auto(texto):
            try:
                lbl_auto.set_text(texto)
            except Exception:
                pass

        def _prepender_novas(novas):
            """Insere SÓ os cards novos no topo da grade, sem redesenhar.

            É a atualização parcial pedida: nada é recriado, o scroll e o
            foco do usuário permanecem, e o custo é proporcional ao que
            chegou — não ao tamanho da página."""
            inseridos = 0
            for n in novas:
                try:
                    _celula = ui.element("div")
                    with _celula:
                        _card = _noticia_card(n)
                    if _card is not None:
                        # nasce no slot atual; move para a PRIMEIRA posição
                        # da grade (índice 0) sem reconstruir o resto
                        _card.move(grid_box, target_index=0)
                    else:
                        _celula.delete()
                    inseridos += 1
                except Exception:
                    log.exception("_prepender_novas: falha ao inserir card novo")
            return inseridos

        async def _checar_novidades():
            """Polling barato: 1 SELECT de agregados. Se mudou, traz só as
            linhas novas e prepende. Nunca redesenha a página inteira."""
            if estado.get("busca") or estado.get("tema"):
                # com filtro/busca ativa, a ordem/quantidade muda -> redesenha
                return
            try:
                _marca = await run.io_bound(ag.marca_ultimo_coletado)
            except Exception:
                return
            if not _marca:
                return
            _total, _max_id, _coleta = _marca
            if _max_id <= estado["max_id"]:
                _rotulo_auto(f"Sem novidade • próxima checagem em {ag.refresh_seg()}s")
                return
            try:
                novas = await run.io_bound(
                    lambda: ag.listar_novas(apos_id=estado["max_id"], limite=12))
            except Exception:
                return
            if novas:
                estado["max_id"] = max(estado["max_id"], _max_id)
                _n = _prepender_novas(novas)
                _rotulo_auto(f"{_n} notícia(s) nova(s) • atualiza sozinho")
            else:
                estado["max_id"] = _max_id

        def _intervalo_refresh():
            try:
                v = int(ag.refresh_seg() or _REFRESCO_SEG_PADRAO)
            except Exception:
                v = _REFRESCO_SEG_PADRAO
            return max(_REFRESCO_SEG_MIN, min(_REFRESCO_SEG_MAX, v))

        _rotulo_auto(f"Atualização automática a cada {_intervalo_refresh()}s")
        ui.timer(_intervalo_refresh(), _checar_novidades)

        # Primeira notícia ASSÍNCRONA: se a grade nasce vazia, dispara a
        # coleta em thread e desenha assim que a primeira chegar — a tela
        # não espera o I/O de rede (nada de event-loop bloqueado).
        if not (ag.contar_noticias(tema=estado["tema"] or None) or 0):
            async def _primeira_noticia():
                _spin = ui.spinner(size="lg").props("aria-label=Buscando notícias")
                with ui.row().classes("w-full items-center justify-center gap-2"):
                    ui.label("Buscando a primeira notícia…").classes("text-caption text-grey-6")
                try:
                    from nicegui import run as _run
                    await _run.io_bound(lambda: ag.coletar_todas(ator="sistema"))
                except Exception:
                    log.exception("_primeira_noticia: falha na coleta inicial")
                finally:
                    try:
                        _spin.delete()
                    except Exception:
                        pass
                _reforcar_grid()

            ui.timer(0.6, _primeira_noticia, once=True)

        grid()
