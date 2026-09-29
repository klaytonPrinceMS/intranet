"""EN: Aggregator screen — fixed-height 3-column grid, ONE scroll per card, TV integration.

PT-BR: Tela do Agregador de Notícias — grid de 3 colunas, card de altura
fixa com UM scroll só, integração TV.

Barra com filtro de tema, busca e o controle "Por página" (escolha de quem
lê, guardada em cookie do navegador) e grid responsivo 3 colunas
(≤1024px: 2; ≤640px: 1).

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

"Todos os temas" mostra UMA notícia por tema na PRIMEIRA página, para a
grade não virar um bloco só de Esporte/Economia. As páginas seguintes
mostram o RESTO da lista, no tamanho configurado, sem repetir a amostra.
Paginação com busca em memória (500 limite, NFKD lower).

PAGINAÇÃO (29/09/2026): o tamanho da página é ESCOLHA DE QUEM LÊ, não
configuração do sistema. Fica em cookie do navegador (`noticias_por_pagina`),
mesmo padrão do `estilo_visual`, e cada pessoa ajusta o seu na barra de cima
desta tela — inclusive quem é `comum`. Quem não mexer usa o padrão do
módulo, `ag.por_pagina()`. O intervalo de coleta NÃO é escolha do leitor: a
coleta é automática e quem só pode disparar coleta manual é o administrador
("Coletar agora", que fica restrito a ele).

A CONTAGÊNCIA e a FATIA saem da MESMA lista, então "Exibindo X de Y" nunca
anuncia página que não existe. Antes a contagem vinha do total cru e a
fatia da amostra por tema: 30 páginas anunciadas, 29 vazias.

TEXTOS CONFIGURÁVEIS: o subtítulo do cabeçalho
(`agregador_noticias_texto_header`) e o aviso de "sem novidade"
(`agregador_noticias_texto_sem_novidade`, que aceita `{seg}`) saem da
configuração e NASCEM VAZIOS — vazio significa nenhuma label na tela, não
label em branco. Quem escreve é o administrador.
"""

import sys, os, re
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from nicegui import ui, run
from mod_intranet import autenticacao
from mod_intranet.aba_modulo import cabecalho

# ============ QUANTAS NOTÍCIAS EU VOU LER (cookie do navegador) ============
#
# Preferência de QUEM LÊ, não configuração do sistema. Fica no navegador pelo
# mesmo motivo e no mesmo formato do `estilo_visual` (`preview_estilos.py`):
# é escolha de leitura de uma pessoa, e um navegador é o lugar onde essa
# escolha vive sem virar dado do banco. Quem não mexe usa o padrão do módulo.
#
# O COOKIE e não um evento de WebSocket porque só uma RESPOSTA HTTP consegue
# mandar `Set-Cookie`; num evento de socket não há resposta para anexar o
# cabeçalho. Daí a rota + 303 de volta, o mesmo desenho de `trocar_estilo`.
COOKIE_POR_PAGINA = "noticias_por_pagina"
ROTA_POR_PAGINA = "/agregador-noticias/por-pagina"


def por_pagina_da_sessao():
    """EN: Page size chosen by this browser, falling back to the module default.

    PT-BR: Tamanho de página escolhido neste navegador; sem cookie, o padrão
    do módulo. O valor do cookie passa pelo mesmo clamp do backend
    (`ag._ajustar_por_pagina`), porque cookie é entrada de usuário e não pode
    serTrusted — alguém pode gravar `por_pagina=99999` no navegador à mão.
    """
    try:
        bruto = ""
        # `ui.context.client` LEVANTA RuntimeError quando não há requisição em
        # curso (import, teste, script) — e "não há requisição" aqui é o caso
        # NORMAL de quem cai no padrão, não uma falha. Por isso o acesso ao
        # contexto fica num try próprio, sem log; só o resto é erro de verdade.
        try:
            req = ui.context.client.request
        except Exception:
            req = None
        if req is not None:
            bruto = (getattr(req, "cookies", {}) or {}).get(
                COOKIE_POR_PAGINA) or ""
            bruto = bruto.strip()
        if bruto:
            from mod_agregador_noticias import bd_manipulador as _ag
            return _ag._ajustar_por_pagina(bruto)
    except Exception as e:
        try:
            log.exception(f"por_pagina_da_sessao: cookie ilegível | {e}")
        except Exception:
            pass
    try:
        return ag.por_pagina()
    except Exception:
        return 12


def url_por_pagina(valor, volta="/agregador-noticias"):
    """EN: URL that saves the page size in the cookie and returns to `volta`.

    PT-BR: URL que grava o tamanho de página no cookie e volta para `volta`.
    Só caminho interno — um `volta` externo viraria redirecionamento aberto.
    """
    try:
        from urllib.parse import quote
        alvo = volta or "/agregador-noticias"
        if not alvo.startswith("/"):
            alvo = "/agregador-noticias"
        return (f"{ROTA_POR_PAGINA}/{int(valor)}"
                f"?volta={quote(alvo, safe='')}")
    except Exception:
        return f"{ROTA_POR_PAGINA}/12"


def montar_rota_por_pagina() -> bool:
    """Registra a rota que grava o cookie do tamanho de página e volta.

    Mesma razão de `preview_estilos.montar_rota_troca`: só uma resposta HTTP
    manda `Set-Cookie`. O 303 evita repetir o GET no destino, e o valor vem
    pelo clamp do backend — o cookie é entrada de usuário, não é confiável.
    """
    try:
        from urllib.parse import urlparse
        from fastapi.responses import RedirectResponse
        from nicegui import app

        @app.get(ROTA_POR_PAGINA + "/{valor}")
        def _trocar_por_pagina(valor: str, volta: str = "/agregador-noticias"):
            """Grava o tamanho de página escolhido e devolve o usuário à tela."""
            destino = urlparse(volta).path if str(volta).startswith("/") else \
                "/agregador-noticias"
            try:
                # clamp do backend: quem grava o cookie é o navegador
                numero = ag._ajustar_por_pagina(valor)
            except Exception:
                numero = ag.POR_PAGINA_PADRAO
            resp = RedirectResponse(url=destino or "/agregador-noticias",
                                    status_code=303)
            resp.set_cookie(COOKIE_POR_PAGINA, str(numero),
                            max_age=60 * 60 * 24 * 365,
                            httponly=False, samesite="lax", path="/")
            return resp

        return True
    except Exception:
        try:
            log.exception("montar_rota_por_pagina: rota não foi registrada")
        except Exception:
            pass
        return False
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

    # O subtítulo do cabeçalho NÃO é mais texto fixo do código: vem da
    # configuração `agregador_noticias_texto_header` (padrão VAZIO) e,
    # vazio, o `cabecalho` não renderiza nenhuma label. Quem escreve é o
    # administrador, em /admin/agregador_noticias.
    tema = ler_tema("agregador_noticias", cor_botao="#000000", cor_texto_botao="#FFFFFF")
    ui.colors(primary=tema["cor_botao"])
    t_cor_titulo = tema["cor_titulo"]
    t_cor_fundo = tema["cor_fundo"]
    t_texto_header = tema["texto_header"]

    # Filtro por tema + busca
    temas = ag.temas_config()
    # `por_pagina` é lido do cookie **UMA VEZ**, aqui no corpo da página, e
    # guardado no `estado` — e não relido a cada redesenho da grade.
    #
    # POR QUÊ UMA VEZ SÓ: a grade é redesenhada por `ui.timer` (atualização
    # parcial a cada `refresh_seg`), e um timer roda num contexto em que
    # `ui.context.client` não existe. Relindo ali, `por_pagina_da_sessao()`
    # caía no padrão do MÓDULO e a página voltava a 12 por página por baixo,
    # com o slider ainda marcando o que a pessoa escolheu. Ler uma vez no
    # contexto de página — onde o request existe — elimina essa diferença,
    # e é o certo: a escolha não muda enquanto a pessoa está lendo.
    estado = {"tema": "", "busca": "", "pagina": 1, "max_id": 0,
              "por_pagina": por_pagina_da_sessao()}

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

    # Teto de linhas lidas em memória para a página de "Todos os temas" (a
    # amostra por tema e o resto saem daqui). Maior que a contagem real do
    # banco hoje (349 linhas com 24h de recycle), então o normal é não
    # truncar nada — mas se truncar, o rodapé avisa em vez de anunciar
    # páginas que não existem.
    _LIMITE_LISTAGEM = 600

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

            # ---- Quantas notícias EU vou ler (escolha de quem lê) ----
            # Fica aqui, na barra de cima, e NÃO no painel admin: escolher
            # quanto ler é preferência de leitura, e o usuário comum tem o
            # mesmo direito que o administrador. O padrão do módulo continua
            # valendo para quem não mexer.
            #
            # Grava em cookie por NAVEGAÇÃO (rota + 303), pelo mesmo motivo do
            # `estilo_visual`: só uma resposta HTTP manda `Set-Cookie`, e um
            # evento de WebSocket não tem resposta para anexar o cabeçalho.
            # Por isso o `change` (soltar o cursor), e não o
            # `on_value_change` — que dispara a cada movimento do trilho e
            # recarregaria a página dezenas de vezes.
            _pp_atual = estado["por_pagina"]
            with ui.row().classes("items-center gap-2 w-full sm:w-auto"):
                ui.label("Por página").classes(
                    "text-caption text-grey-6 whitespace-nowrap")
                _sl_pp = ui.slider(min=ag.POR_PAGINA_MINIMO,
                                   max=ag.POR_PAGINA_MAXIMO - 1, step=3,
                                   value=_pp_atual) \
                    .props("outlined dense label label-always") \
                    .classes("w-full sm:w-56") \
                    .props('data-testid=agregador-por-pagina')
                _sl_pp.tooltip("Quantas notícias por página")
                _sl_pp.on("change", lambda e: ui.navigate.to(
                    url_por_pagina(int(e.value or _pp_atual)), force_load=True))

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
            """Desenha a página de notícias e a paginação.

            PAGINAÇÃO (corrigida em 29/09/2026). Antes a contagem vinha do
            TOTAL CRU (349 linhas) e a fatia vinha da AMOSTRA por tema (9
            linhas): as páginas 2..30 anunciavam 30 páginas e saíam vazias —
            e a página vazia caía no cartão "Nenhuma notícia ainda", que é a
            mensagem de BANCO VAZIO. Agora contagem e fatia saem da MESMA
            lista:

            • tamanho da página = `estado["por_pagina"]` (múltiplo de 3,
              mínimo 9) — escolha de QUEM LÊ, no controle "Por página" da
              barra desta tela, gravada em cookie do navegador; sem cookie,
              o padrão do módulo (`ag.por_pagina()`). Lido do cookie UMA
              VEZ no corpo da página, e não a cada redesenho: o timer roda
              sem request e releria o padrão do módulo por baixo. Clamp no
              BACKEND;
            • "Todos os temas": a AMOSTRA por tema entra no TOPO da lista
              (uma notícia de cada tema distinto) e o RESTO vem logo depois.
              Ela é ordem de PRIORIDADE, não o conteúdo inteiro da página 1:
              o tamanho escolhido vale para TODAS as páginas, inclusive a
              primeira. Antes a página 1 era só a amostra, e o controle
              mentia — a pessoa punha 63 no trilho e via 8;
            • a última página pode vir incompleta.

            AMOSTRA e RESTO particionam a lista inteira, uma vez cada, então
            o total anunciado é exatamente o alcance da paginação: somar os
            "Exibindo X" de todas as páginas dá o total da última, sem
            sobra e sem buraco.
            """
            tema_f = estado["tema"] or None
            busca = (estado.get("busca") or "").strip()
            # TAMANHO DA PÁGINA — configurável (múltiplo de 3, mínimo 9),
            # com o clamp feito no BACKEND (`ag.por_pagina`), não aqui: é a
            # mesma variável que fatia e que anuncia o total.
            por_pagina = estado["por_pagina"]
            truncado = False
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
                total_pag = max(1, (total + por_pagina - 1) // por_pagina)
                if estado["pagina"] > total_pag:
                    estado["pagina"] = total_pag
                if estado["pagina"] < 1:
                    estado["pagina"] = 1
                offset = (estado["pagina"] - 1) * por_pagina
                noticias = filtradas[offset:offset + por_pagina]
            elif tema_f:
                # Tema escolhido: paginação direta, sem amostra — o filtro
                # JÁ é a seleção do usuário.
                total = ag.contar_noticias(tema=tema_f)
                total_pag = max(1, (total + por_pagina - 1) // por_pagina)
                if estado["pagina"] > total_pag:
                    estado["pagina"] = total_pag
                if estado["pagina"] < 1:
                    estado["pagina"] = 1
                offset = (estado["pagina"] - 1) * por_pagina
                noticias = ag.listar_noticias(tema=tema_f, limite=por_pagina,
                                              offset=offset)
            else:
                # TODOS OS TEMAS: a página 1 é a amostra por tema e o resto
                # vem depois. Amostra e resto não se repetem.
                _linhas = ag.listar_noticias(tema=None, limite=_LIMITE_LISTAGEM,
                                             offset=0)
                # A amostra é a ORDEM DE PRIORIDADE, não o conteúdo da página.
                # Ela nasce de uma notícia por tema para o dia em que 160 das
                # 351 eram do mesmo tema e o topo da página virava quase tudo
                # igual — mas ela é só a CABEÇA da lista: o que vem depois
                # completa a página até o tamanho que a pessoa escolheu.
                #
                # Antes a página 1 era SÓ a amostra, e aí o controle "Por
                # página" mentia: a pessoa punha 63 no trilho e via 8, porque
                # o tamanho não valia para a primeira página. Agora a
                # amostra ocupa o topo e o resto vem logo em seguida, então o
                # número que a pessoa escolheu é o número que ela vê.
                _vistos, _amostra = set(), []
                for _n in _linhas:
                    _t = _n[3]
                    if _t in _vistos:
                        continue
                    _vistos.add(_t)
                    _amostra.append(_n)
                    if len(_amostra) >= por_pagina:
                        break
                _ids_amostra = {_n[0] for _n in _amostra}
                _n_amostra = len(_amostra)
                _resto = [_n for _n in _linhas if _n[0] not in _ids_amostra]
                # A lista INTEIRA na ordem escolhida: amostra primeiro, resto
                # depois, sem repetir. A partir daqui a paginação é a simples
                # fatia por `por_pagina` — não há mais contagem separada para
                # a amostra, que era a origem do desencontro.
                _ordenada = _amostra + _resto
                # O total anunciado é o que a paginação ALCANÇA de fato: a
                # lista carregada, não a contagem bruta de uma tabela que
                # pode ser maior que o limite de leitura. Havendo linhas
                # além do limite, o rodapé avisa em vez de prometer páginas
                # que não existem.
                total = len(_ordenada)
                truncado = (ag.contar_noticias(tema=None) or 0) > total
                total_pag = max(1, (total + por_pagina - 1) // por_pagina)
                if estado["pagina"] > total_pag:
                    estado["pagina"] = total_pag
                if estado["pagina"] < 1:
                    estado["pagina"] = 1
                offset = (estado["pagina"] - 1) * por_pagina
                noticias = _ordenada[offset:offset + por_pagina]
            if not noticias:
                with vazio_box:
                    vazio_box.clear()
                    with ui.card().classes("w-full p-8 items-center"):
                        ui.icon("article", size="48px").classes("text-grey-4")
                        if busca:
                            # busca sem resultado: não é banco vazio, é filtro
                            ui.label(f'Nenhuma notícia para "{busca}" (busca em todos os temas).').classes("text-grey-6")
                        elif tema_f and total <= 0:
                            # o tema escolhido ainda não tem notícia: o banco
                            # tem, a coleta é que não trouxe desse tema
                            ui.label(f'Nenhuma notícia do tema "{tema_f}" no momento.').classes("text-grey-6")
                            ui.label(f"Coleta a cada {ag.intervalo_min()} min.").classes("text-caption text-grey-5")
                        elif total <= 0:
                            # BANCO REALMENTE VAZIO
                            ui.label("Nenhuma notícia ainda. A coleta é automática — aguarde o primeiro ciclo ou peça ao administrador.").classes("text-grey-6")
                            ui.label(f"Coleta a cada {ag.intervalo_min()} min.").classes("text-caption text-grey-5")
                        else:
                            # PÁGINA VAZIA dentro de um banco com notícias:
                            # só ocorre em página além do fim (proteção contra
                            # estado inconsistente). Aqui a notícia não é a
                            # coleta — é voltar.
                            ui.label("Nenhuma notícia nesta página.").classes("text-grey-6")
                            try:
                                _btn = botao(
                                    "Voltar para a primeira página", icone="first_page",
                                    on_click=lambda: (estado.__setitem__("pagina", 1), _reforcar_grid()),
                                    variante="primario", compacto=True,
                                    chave_modulo="agregador_noticias")
                                if _btn is not None:
                                    _btn.props('data-testid=agregador-voltar-primeira')
                            except Exception:
                                log.exception("grid: falha ao montar o botão de voltar")
                # a paginação some junto com a grade: botão apontando para
                # uma página que não existe é pior do que nenhum botão
                with pag_box:
                    pag_box.clear()
                return
            # a página anterior estava vazia: o cartão de estado não pode
            # sobrar na tela ao lado da grade
            with vazio_box:
                vazio_box.clear()
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
                    with ui.column().classes("items-end").style("gap: 0.15rem"):
                        # `len(noticias)` é o que está DE FATO na tela e
                        # `total` é o alcance da paginação — os dois saem
                        # da mesma lista, então nunca mentem juntos.
                        ui.label(f"Exibindo {len(noticias)} de {total}").classes("text-caption text-grey-5")
                        if truncado:
                            ui.label(f"Mostrando as {total} mais recentes — a lista é maior que o limite de leitura.").classes("text-caption text-grey-5")
                        elif not tema_f and not busca and estado["pagina"] == 1 \
                                and _n_amostra:
                            # a amostra é o TOPO da lista, não a página inteira
                            ui.label(f"As {_n_amostra} primeiras são uma de cada tema.").classes("text-caption text-grey-5")

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
            """Escreve (ou apaga) o rótulo da barra de atualização automática.

            Texto VAZIO = rótulo apagado, sem resíduo na tela: o
            administrador configurou em `/admin/agregador_noticias` e não
            preencheu nada, então nada aparece (nem uma label em branco).
            """
            try:
                lbl_auto.set_text(texto or "")
            except Exception:
                pass

        def _texto_sem_novidade() -> str:
            """Texto de 'sem novidade' — vem da configuração; vazio = nada.

            Aceita o marcador `{seg}`, trocado pelo intervalo real de
            checagem (ex.: `Sem novidade • próxima checagem em {seg}s`).
            O PADRÃO é vazio: nada aparece até o administrador preencher.
            """
            try:
                texto = ag.texto_sem_novidade() or ""
                if not texto:
                    return ""
                return texto.replace("{seg}", str(_intervalo_refresh()))
            except Exception:
                log.exception("_texto_sem_novidade: falha ao montar o rótulo")
                return ""

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
                # Texto CONFIGURÁVEL (`agregador_noticias_texto_sem_novidade`,
                # padrão VAZIO): com a configuração vazia, nada aparece.
                _rotulo_auto(_texto_sem_novidade())
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

        # Rótulo inicial da barra: é o MESMO estado do "sem novidade"
        # (ainda não chegou nada da checagem automática), então usa o texto
        # configurado — e nasce vazio quando o admin não preencheu nada.
        # Assim o rótulo não "acende" com um texto fixo e apaga no primeiro
        # polling.
        _rotulo_auto(_texto_sem_novidade())
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
