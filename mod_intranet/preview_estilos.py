"""Provisório — 4 padrões visuais (Login + Home) na estética de app social.

Substitui a primeira tentativa, que ficou genérica demais: eram CSS
frameworks de uso geral (Tachyons, Spectre, Foundation, Milligram), sem a
linguagem visual de rede social/mensageiro. Aqui os 4 padrões são escolhidos
dentro da estética pedida — resemble **Facebook** e **WhatsApp**: cartão
claro sobre fundo cinza, cantos generosamente arredondados, barra de topo
colorida e tipografia sans-serif limpa.

OS 4 PADRÕES
-------------
  azul       nome do produto em azul grande ACIMA do cartão branco, botão azul
             de largura toda — o login clássico do Facebook
  verde      TELA DIVIDIDA: painel verde à esquerda, formulário branco à direita
             (empilha e o painel some no celular), botão em pílula
  roxo       cartão muito arredondado (raio 22px) com faixa gradiente no topo
  preto      monocromático, aro colorido no avatar, botão preto

Nenhum framework genérico reproduz linguagem de mensageiro (painel dividido,
faixa gradiente, aro de avatar), então os quatro são **designs próprios**,
escritos para esta sessão em `assets/css/preview-estilos-v1.css`. A identidade
visual vem por custom property (`--pe-*`).

A COR DO BOTÃO SAI PELA VARIÁVEL `--q-primary`, NÃO POR CSS
----------------------------------------------------------
O Quasar declara `.bg-primary { background: var(--q-primary) !important }`
*dentro de uma cascade layer*, e em `!important` a camada vence QUALQUER
regra nossa que esteja fora de camada — por mais específica que ela seja, e
por mais `!important` que esteja. Tentamos pintar o botão "por fora" e não
funcionou: nem `!important` nosso, nem universal. A saída é a via que o próprio
Quasar usa para rebrand (`ui.colors`): mexer no TOKEN. Por isso o botão do
login e o cabeçalho da Home saem na cor do padrão sem uma única disputa de
cascata no meio. Ver `_defs_css` e o bloco do `.q-layout` na folha.

SELEÇÃO POR QUERY PARAM
-----------------------
`?estilo=<chave>`. O botão do alternador apenas navega — **sem JavaScript
direto** e **sem gravar no banco**, então a URL é compartilhável, o padrão
aparece em print/compartilhamento e não custa uma escrita por troca.

ACESSIBILIDADE
--------------
As cores de botão foram escurecidas um passo para chegar a 4,5:1 com o texto
branco (WCAG AA): o azul clássico do Facebook dá 4,23:1 e o verde vivo do
WhatsApp só 1,98:1 — os dois reprovariam. Ver o comentário em `_CORES`.

EN: TEMPORARY 4-pattern switcher for login and home, in the social-app
visual family. Chosen via `?estilo=<key>`; the switcher only navigates — no
direct JavaScript, no database writes. Button colour comes from overriding
`--q-primary` (Quasar's own rebrand hook), because Quasar's `.bg-primary` is
`!important` inside a cascade layer and cannot be outranked by a stylesheet.

>>> ESTE MÓDULO É PROVISÓRIO <<<
Para REMOVER depois de escolher o padrão definitivo:
  1. apague este arquivo e `assets/css/preview-estilos-v1.css`;
  2. em `main.py`, apague o bloco `montar_rotas_static()` do boot e os blocos
     `# ===== PROVISÓRIO: padrão visual =====` em `page_login`,
     `_construir_dashboard` e `page_dashboard` (o `modelo=` volta a ser o
     literal de antes);
  3. nada mais depende deste módulo (só `home_visual` continua valendo).
"""

import os

VERSAO_CSS = "v1"
ARQUIVO_CSS = f"preview-estilos-{VERSAO_CSS}.css"
DIRETORIO_CSS = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "assets", "css")


def _versao_arquivo() -> str:
    """Cache-buster da folha: o mtime do arquivo.

    Durante o protótipo a folha muda várias vezes por sessão; com uma versão
    fixa (`?v=1`) o navegador segura a folha antiga e a mudança "não aparece" —
    foi exatamente o que aconteceu na primeira rodada de testes. O mtime muda a
    cada edição, então o Ctrl+F5 já traz a folha nova.
    """
    try:
        return str(int(os.path.getmtime(os.path.join(DIRETORIO_CSS, ARQUIVO_CSS))))
    except Exception:
        return VERSAO_CSS

PADROES = (
    {"chave": "azul", "rotulo": "Azul",
     "descricao": "azul de marca, nome grande e cartoes brancos"},
    {"chave": "verde", "rotulo": "Verde",
     "descricao": "tela dividida, painel verde e botao em pilula"},
    {"chave": "roxo", "rotulo": "Roxo",
     "descricao": "faixa gradiente roxo para rosa, bem arredondado"},
    {"chave": "preto", "rotulo": "Preto",
     "descricao": "preto, aro colorido no avatar, bem monocromatico"},
)
CHAVES = tuple(p["chave"] for p in PADROES)
ROTULOS = {p["chave"]: p["rotulo"] for p in PADROES}
DESCRICOES = {p["chave"]: p["descricao"] for p in PADROES}

# Opção "Padrão": NÃO é um estilo, é a AUSÊNCIA de escolha pessoal. Quem clica
# nela volta a seguir a cor que o ADMINISTRADOR configurou para o módulo
# (ver `ler_estilo`): o vazio não é ausência de estilo, é ausência de imposição.
# Fica no fim da lista para os quatro estilos ficarem juntos no começo.
CHAVE_PADRAO = "padrao"
OPCAO_PADRAO = {
    "chave": CHAVE_PADRAO, "rotulo": "Padrão",
    "descricao": "segue o padrão definido pelo administrador",
}
# Padrão do LOGIN quando a URL não traz `?estilo=` — DEFINIDO PELO RESPONSÁVEL:
# o WhatsApp foi o escolhido (tela dividida, botão em pílula, painel teal).
# Trocar de padrão depois é só mudar esta linha.
PADRAO_PADRAO = "verde"

# Estilo FIXO da tela de login, por decisão do responsável: é o WhatsApp
# (`verde`) para todo mundo, independentemente da preferência que o usuário
# tenha escolhido para os módulos internos. Fica em constante própria para
# que, se um dia o login deixar de ser fixo, o padrão do sistema
# (`PADRAO_PADRAO`) possa mudar sem arrastar o login junto.
PADRAO_LOGIN = "verde"

# Padrão que absorve a cor do admin (`cor_principal`/`cor_fundo` de tb_config).
# No protótipo é `None` de propósito: a comparação só é honesta se os quatro
# aparecerem com a identidade deles — a cor da prefeitura hoje é quase preta
# e zerava justamente o azul do Facebook. Depois de escolher, basta colocar a
# chave escolhida aqui (ex.: PADRAO_ADM = "whatsapp") e a cor do admin volta a
# valer sem tocar em mais nada.
PADRAO_ADM = None

# ---------------------------------------------------------------------------
#  Paleta de cada padrão. `escuro` decide se a Home recebe as classes de tema
#  escuro do Quasar; `primaria_texto` é separado de `primaria` porque o
#  WhatsApp usa teal escuro na barra e verde claro no botão; `primaria_q` é a
#  cor que o Quasar assume como "primary" (é dela que sai a cor do botão).
_CORES = {
    "azul": {
        "escuro": False, "familia": "Feed",
        "fundo": "#f0f2f5", "superficie": "#ffffff",
        # O azul clássico do Facebook (#1877f2) dá 4,23:1 com o texto branco do
        # botão — abaixo dos 4,5:1 da WCAG AA. Este é o tom um passo mais
        # escuro: 5,24:1, e ainda lê como "azul de rede social".
        "primaria": "#1668d8", "primaria_q": "#1668d8",
        "primaria_texto": "#ffffff",
        "raio": "8px", "sombra": "0 1px 2px rgba(0,0,0,.13)",
    },
    "verde": {
        "escuro": False, "familia": "Mensageiro",
        "fundo": "#eae6df", "superficie": "#ffffff",
        "primaria": "#075e54", "primaria_q": "#0f7a6d",
        # O verde vivo do WhatsApp (#25d366) dá só 1,98:1 com branco — impossível
        # num botão de texto branco. O verde de ação do botão é o teal do
        # próprio WhatsApp, um tom mais escuro (5,22:1); o #25d366 continua
        # disponível como cor de acento.
        "primaria_acao": "#25d366",
        "primaria_texto": "#ffffff",
        "raio": "10px", "sombra": "0 1px 2px rgba(0,0,0,.10)",
    },
    "roxo": {
        "escuro": False, "familia": "Bolhas",
        "fundo": "#f4f5fb", "superficie": "#ffffff",
        "primaria": "#7c3aed", "primaria_q": "#7c3aed", "primaria_2": "#db2777",
        "primaria_texto": "#ffffff",
        "raio": "22px", "sombra": "0 2px 10px rgba(80,60,160,.14)",
    },
    "preto": {
        "escuro": False, "familia": "Monocromático",
        "fundo": "#fafafa", "superficie": "#ffffff",
        "primaria": "#111111", "primaria_q": "#111111", "primaria_2": "#e1306c",
        "primaria_texto": "#ffffff",
        "raio": "14px", "sombra": "0 1px 3px rgba(0,0,0,.10)",
    },
}


# ---------------------------------------------------------------------------
#  API
# ---------------------------------------------------------------------------
def montar_rotas_static() -> bool:
    """Monta a rota estática que serve a folha do protótipo (`/assets/css/*`).

    O projeto só tinha um mount estático (`/css/frameworks`, em `tema_css`), e
    ele aponta para `assets/css/frameworks` — por isso o `<link>` do protótipo
    devolvia 404 e NENHUMA regra de estilo era aplicada. Montando o diretório
    `assets/css` inteiro, o `<link>` passa a ser servido sem rede externa.

    Chamada uma vez no boot do `main.py`. Falha silenciosa: a página continua
    abrindo, só sem a decoração do protótipo.
    """
    destino = os.path.abspath(DIRETORIO_CSS)
    if not os.path.exists(os.path.join(destino, ARQUIVO_CSS)):
        return False
    try:
        from nicegui import app
        app.add_static_files("/assets/css", destino)
        return True
    except Exception as exc:
        try:
            import logging
            logging.getLogger(__name__).warning(
                "preview_estilos: rota estática não montada: %s", exc)
        except Exception:
            pass
        return False


def _defs_css(paleta: dict) -> str:
    """`:root` com as custom properties do padrão + o `--q-primary` da página.

    As `--pe-*` vão na raiz porque o fundo da página precisa delas FORA do
    wrapper do padrão (no `<body>`/`.q-page`).

    A `--q-primary` é a peça que mais importa e precisa de cuidado: o Quasar
    declara `.bg-primary { background: var(--q-primary) !important }` dentro de
    uma cascade layer, e em `!important` a camada ganha de QUALQUER regra nossa
    fora de camada — por mais específica que ela seja. Ou seja: não dá para
    pintar botão e cabeçalho "por fora"; tem de ser pela variável que o próprio
    Quasar lê, que é o mesmo mecanismo de `ui.colors()`.

    Ela é escrita no `.q-layout` (e não no wrapper do padrão) porque o
    cabeçalho é montado pelo layout de 4 partes, ACIMA do wrapper. O
    `!important` é o que vence a declaração inline que o `ui.colors()` deixa
    no layout. O valor vem da paleta, que continua sendo a fonte única — não
    há cor chumbada no CSS.
    """
    chaves = ("fundo", "superficie", "primaria", "primaria_acao", "primaria_2",
              "primaria_texto", "raio", "sombra")
    linhas = "\n".join(
        f"    --pe-{k}: {paleta[k]};" for k in chaves if k in paleta)
    q_primaria = paleta.get("primaria_q", paleta["primaria"])
    return (f":root {{\n{linhas}\n  }}\n"
            f"  .pe-{paleta['chave']},\n"
            f"  body:has(.pe-{paleta['chave']}) .q-layout {{\n"
            f"    --q-primary: {q_primaria} !important;\n"
            f"  }}")


def aplicar(padrao: str = "", cor_principal: str = "#000000",
            cor_fundo: str = "#EEEEEE") -> dict:
    """Aplica o padrão: injeta as custom properties e a folha de estilo.

    Devolve a paleta efetiva, para a tela usar as cores. `cor_principal`/
    `cor_fundo` do admin só entram no padrão apontado por `PADRAO_ADM` — ver o
    comentário dessa constante.
    """
    p = padrao if padrao in CHAVES else PADRAO_PADRAO
    paleta = dict(_CORES[p])
    paleta["chave"] = p
    if p == PADRAO_ADM:
        paleta["primaria"] = cor_principal or paleta["primaria"]
        paleta["fundo"] = cor_fundo or paleta["fundo"]
    try:
        from nicegui import ui
        ui.add_head_html(
            f"<style data-estilo-pe='{p}'>\n  {_defs_css(paleta)}\n</style>\n"
            f'<link rel="stylesheet" href="/assets/css/{ARQUIVO_CSS}?v={_versao_arquivo()}">')
    except Exception:
        pass
    return paleta


# ---------------------------------------------------------------------------
#  Telas
# ---------------------------------------------------------------------------
RODAPE = "Acesso restrito — uso interno da prefeitura"


def _dica(padrao: str, hint: str) -> None:
    """Bloco de dica do rodapé do formulário (tom próprio de cada app)."""
    if not hint:
        return
    try:
        from nicegui import ui
        with ui.row().classes("pe-aviso w-full items-start no-wrap").style(
                "gap: .5rem; padding: .7rem; margin-top: 1.1rem"):
            ui.icon("info", size="18px").classes("q-mt-xs")
            ui.label(hint).classes("text-caption grow min-w-0")
    except Exception:
        pass


def _campos(campos) -> None:
    """Chama o callback do `main.py` dentro de uma coluna com respiro."""
    from nicegui import ui
    with ui.column().classes("w-full min-w-0").style("gap: 1rem"):
        campos()


def _rodape() -> None:
    from nicegui import ui
    with ui.column().classes("w-full items-center").style("gap: .25rem; margin-top: 1.25rem"):
        ui.label(RODAPE).classes("text-caption text-grey-6 text-center")


# ---------------------------------------------------------------------------
#  Os 4 layouts. Cada um é uma FUNÇÃO separada de propósito: se os quatro
#  coubessem num `if/elif` só, trocar o estilo acabaria virando um galho
#  impossível de manter. Um por padrão deixa o removê-lo uma dela só.
# ---------------------------------------------------------------------------
def _login_azul(*, padrao, icone, titulo, subtitulo, hint, paleta, campos) -> None:
    """Facebook: cartão branco centralizado sobre fundo cinza, marca em cima.

    É a assinatura do login do Facebook: nome do produto grande e azul ACIMA do
    cartão, formulário dentro do cartão, botão azul de largura total.
    """
    from nicegui import ui
    with ui.element("div").classes("pe-azul w-full min-w-0").style(
            "min-height: 100vh; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 1.5rem 1rem; gap: 1.5rem"):
        with ui.column().classes("items-center").style("gap: .35rem"):
            ui.icon(icone, size="46px").classes("pe-marca")
            ui.label(titulo).classes("pe-marca").style("font-size: 2rem; line-height: 1.1")
            ui.label("entrar na sua conta").classes("text-caption text-grey-6")
        with ui.column().classes("pe-caixa-login w-full min-w-0").style(
                "padding: 1rem 1.1rem; max-width: 396px; gap: .9rem"):
            with ui.column().classes("w-full").style("gap: .85rem"):
                _campos(campos)
            _dica("azul", hint)
        _rodape()


def _login_verde(*, padrao, icone, titulo, subtitulo, hint, paleta, campos) -> None:
    """WhatsApp Web: painel colorido à esquerda, formulário branco à direita.

    A tela dividida é a assinatura do WhatsApp Web — e no telefone ela
    empilha, porque o painel some e sobra só o formulário.
    """
    from nicegui import ui
    with ui.element("div").classes("pe-verde w-full min-w-0").style(
            "min-height: 100vh; display: flex; align-items: stretch; flex-wrap: wrap"):
        # painel decorativo (some no telefone)
        with ui.column().classes("pe-painel w-full").style(
                "flex: 1 1 46%; min-width: 0; padding: 3rem 2.5rem; justify-content: center; gap: .5rem"):
            ui.icon(icone, size="54px")
            with ui.column().classes("w-full min-w-0").style("gap: .3rem; margin-top: .6rem"):
                ui.label(titulo).classes("pe-sistema")
                if subtitulo:
                    ui.label(subtitulo).classes("text-body2 opacity-90")
                if hint:
                    ui.label(hint).classes("text-caption opacity-75").style("margin-top: .8rem")
        # formulário
        with ui.column().classes("pe-caixa-login w-full min-w-0").style(
                "flex: 1 1 54%; min-width: 0; padding: 2.5rem 2rem; justify-content: center; gap: 1.1rem; max-width: 640px"):
            with ui.column().classes("w-full min-w-0").style("gap: .35rem"):
                ui.label(titulo).classes("text-h6").style("font-weight: 700")
                ui.label("Entre para continuar").classes("text-caption text-grey-6")
            _campos(campos)
            _dica("verde", hint)
            _rodape()


def _login_roxo(*, padrao, icone, titulo, subtitulo, hint, paleta, campos) -> None:
    """Messenger: cartão muito arredondado com faixa gradiente no topo."""
    from nicegui import ui
    with ui.element("div").classes("pe-roxo w-full min-w-0").style(
            "min-height: 100vh; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 1.5rem 1rem; gap: 1.25rem"):
        with ui.column().classes("pe-caixa-login w-full min-w-0").style(
                "padding: 0; max-width: 440px; overflow: hidden"):
            with ui.column().classes("pe-topo w-full items-center").style(
                    "gap: .6rem; padding: 1.4rem 1.2rem; flex-direction: column; text-align: center"):
                ui.icon(icone, size="38px")
                ui.label(titulo).classes("pe-sistema")
                if subtitulo:
                    ui.label(subtitulo).classes("text-caption opacity-90")
            with ui.column().classes("w-full").style("padding: 1.4rem 1.3rem; gap: 1rem"):
                _campos(campos)
                _dica("roxo", hint)
        _rodape()


def _login_preto(*, padrao, icone, titulo, subtitulo, hint, paleta, campos) -> None:
    """Instagram: monocromático, aro colorido no avatar, muito limpo."""
    from nicegui import ui
    with ui.element("div").classes("pe-preto w-full min-w-0").style(
            "min-height: 100vh; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 1.5rem 1rem; gap: 1.25rem"):
        with ui.column().classes("items-center").style("gap: .6rem"):
            with ui.element("div").classes("pe-aro"):
                with ui.element("span").classes("pe-aro-interna"):
                    ui.icon(icone, size="26px")
            ui.label(titulo).classes("pe-marca").style("font-size: 1.5rem")
            if subtitulo:
                ui.label(subtitulo).classes("text-caption text-grey-6 text-center").style("max-width: 300px")
        with ui.column().classes("pe-caixa-login w-full min-w-0").style(
                "padding: 1.5rem 1.2rem; max-width: 400px; gap: 1rem"):
            _campos(campos)
            _dica("preto", hint)
        _rodape()


_LAYOUTS = {
    "azul": _login_azul,
    "verde": _login_verde,
    "roxo": _login_roxo,
    "preto": _login_preto,
}


def tela_login(padrao: str, *, icone: str, titulo: str, subtitulo: str,
               hint: str, paleta: dict, campos) -> None:
    """Monta a tela de login no padrão escolhido.

    `campos` é uma CALLABLE que o `main.py` fornece: é ela quem cria os
    inputs e o botão com os `data-testid` de produção e o `tentar_login`
    real. Este módulo **não** sabe autenticar — ele só desenha o invólucro
    visual. É por isso que trocar de padrão não pode quebrar o login.

    Se o layout do padrão falhar por qualquer motivo, cai no mais simples
    possível — os campos aparecem SEM nenhum enfeite, em vez da tela ficar
    branca. O login é a única tela que não pode quebrar.
    """
    p = padrao if padrao in _LAYOUTS else PADRAO_PADRAO
    try:
        _LAYOUTS[p](padrao=p, icone=icone, titulo=titulo, subtitulo=subtitulo,
                    hint=hint, paleta=paleta, campos=campos)
    except Exception:
        try:
            import logging
            logging.getLogger(__name__).exception(
                "preview_estilos: layout '%s' falhou; usando o login mínimo", p)
        except Exception:
            pass
        try:
            from nicegui import ui
            with ui.column().classes("w-full").style("padding: 2rem; gap: 1rem"):
                campos()
        except Exception:
            pass



# ---------------------------------------------------------------------------
#  ESCOLHA DE ESTILO: COOKIE DO NAVEGADOR (não vai para o banco)
# ---------------------------------------------------------------------------
# A preferência é DO NAVEGADOR, não do banco: fica só neste computador, neste
# navegador, e não viaja com o usuário para outra máquina nem aparece para
# outra pessoa que usar o mesmo login. Por isso ela NÃO está em `tb_config`.
#
# Por que cookie e não `localStorage`: o estilo é aplicado na RENDERIZAÇÃO, no
# servidor. Com `localStorage` só existe JavaScript rodando no cliente, então o
# servidor teria de desenhar a tela no padrão padrão e o navegador trocar
# depois — um piscar de layout em toda troca de estilo, e um segundo round-trip.
# O cookie é lido no request, então a página já nasce no estilo certo. Também
# evita JavaScript direto, que o projeto proíbe.
COOKIE_ESTILO = "estilo_visual"
ROTA_TROCA = "/estilo-visual"


def _request_atual():
    """Request HTTP da renderização, ou None se não houver.

    O NiceGUI 3 expone o request em `context.client.request` e removeu o
    `context.request` que existia no 2 — por isso a cadeia: o acesso novo
    primeiro, o antigo como reserva. Sem isso o cookie chegava como vazio e o
    usuário nunca tinha sua escolha aplicada (falha silenciosa, que é a pior
    delas: a tela abre, mas no estilo errado).
    """
    try:
        from nicegui import context
        req = getattr(context, "request", None)
        if req is None:
            req = getattr(getattr(context, "client", None), "request", None)
        return req
    except Exception:
        return None


def ler_estilo() -> str:
    """Escolha pessoal neste navegador; "" quando não há escolha.

    Devolve a chave de um ESTILO (uma de `CHAVES`) ou "" — que significa
    "Padrão", isto é, NÃO impor nada e deixar a cor que o administrador do
    módulo configurou aparecer. `CHAVE_PADRAO` no cookie e qualquer valor
    desconhecido são normalizados para "", para o código ter um único jeito de
    dizer "sem escolha".
    """
    req = _request_atual()
    bruto = ""
    try:
        bruto = (req.cookies.get(COOKIE_ESTILO) or "").strip().lower() if req else ""
    except Exception:
        bruto = ""
    if bruto == CHAVE_PADRAO or bruto not in CHAVES:
        return ""
    return bruto


def estilo_efetivo() -> str:
    """Estilo que vale AGORA, ou "" quando o usuário escolheu "Padrão".

    O vazio é uma resposta válida e importante: significa que NENHUM estilo está
    sendo imposto, e quem manda na cor é o administrador do módulo (o que o
    `tema_modulo.ler_tema` do próprio módulo devolve). Por isso o padrão do
    sistema NÃO é mais um estilo: ele é a configuração de cada módulo.
    """
    return ler_estilo()


def link_troca(chave: str, volta: str = "/") -> str:
    """URL que troca o estilo e devolve o usuário para onde ele estava.

    `volta` é o caminho da tela atual. O botão navega para cá, a rota grava o
    cookie e redireciona de volta — então o usuário troca o estilo sem perder a
    página em que estava, inclusive o módulo.
    """
    from urllib.parse import quote
    destino = volta or "/"
    if not destino.startswith("/"):
        destino = "/"
    return f"{ROTA_TROCA}/{chave}?volta={quote(destino, safe='')}"


def montar_rota_troca() -> bool:
    """Registra a rota que grava o cookie do estilo e volta para a tela.

    Uma rota HTTP de verdade (e não um evento do WebSocket) porque só uma
    resposta HTTP consegue mandar `Set-Cookie` para o navegador — num evento de
    socket não há resposta para anexar o cabeçalho. O redirecionamento é 303
    para não repetir o POST no destino. Chave fora da lista é ignorada e
    devolve o padrão, sem gravar nada.
    """
    try:
        from fastapi.responses import RedirectResponse
        from nicegui import app
        from urllib.parse import urlparse

        @app.get(ROTA_TROCA + "/{chave}")
        def trocar_estilo(chave: str, volta: str = "/"):
            """Grava a escolha de estilo no cookie deste navegador e volta."""
            # `padrao` e qualquer valor desconhecido viram "sem escolha
            # pessoal": o cookie guarda a intenção, e o estilo em vigor é
            # resolvido na renderização (padrão do administrador).
            if chave not in CHAVES:
                chave = CHAVE_PADRAO
            # Só aceita caminho interno: um `volta` externo aqui viraria um
            # redirecionamento aberto (o usuário cairia numa página controlada
            # por quem montou o link).
            alvo = urlparse(volta).path if volta.startswith("/") else "/"
            resp = RedirectResponse(url=alvo or "/", status_code=303)
            resp.set_cookie(
                COOKIE_ESTILO, chave, max_age=60 * 60 * 24 * 365,
                httponly=False, samesite="lax", path="/")
            return resp

        return True
    except Exception:
        try:
            import logging
            logging.getLogger(__name__).exception(
                "preview_estilos: rota de troca de estilo não foi registrada")
        except Exception:
            pass
        return False


def _caminho_atual() -> str:
    """Caminho da tela atual (a troca de estilo devolve o usuario para aqui)."""
    req = _request_atual()
    try:
        return (req.url.path if req else "") or "/"
    except Exception:
        return "/"


def barra_alternador(padrao: str, discreto: bool = False) -> None:
    """Barra de escolha de estilo, no rodape de TODAS as telas internas.

    Clicar em um estilo navega para a rota que grava o cookie do navegador e
    volta para a tela atual — de onde o usuario nao sai. E o que faz o padrao
    escolhido continuar valendo no proximo login, neste computador.

    Os botoes sao `ui.button` crus, e nao a fabrica `ui_comum.botao`, por um
    motivo concreto: a fabrica aplica `text-primary`/`bg-primary` do Quasar,
    que sao `!important` DENTRO de uma cascade layer — nenhuma regra nossa
    fora de camada os vence. Como aqui a cor e justamente a informacao
    (ativo x inativo), o controle tem de ser nosso.

    `discreto=True` deixa a barra menor — e o modo do rodapé, que é uma faixa
    baixa e não pode crescer. A barra NUNCA é posicionada de forma fixa: ela
    fica no fluxo, entre os itens que o rodapé ja tinha, para o padrao antigo
    do rodape (titulo a esquerda, versao a direita) continuar valendo.

    Falha registrada e silenciosa: o alternador e decoracao, nunca pode
    derrubar a tela em que ele esta.
    """
    # `padrao` recebido e o que esta EFETIVO na tela; o que marca o botao ativo
    # e a ESCOLHA do usuario, que pode ser vazia (ver `ler_estilo`).
    escolhido = ler_estilo() or CHAVE_PADRAO
    try:
        from nicegui import ui
        classes = ["pe-alternador", "items-center", "justify-center", "flex-wrap",
                   "no-wrap"]
        with ui.row().classes(f"pe-{padrao} " + " ".join(classes)).style(
                "gap: .35rem" if discreto else "gap: .5rem"):
            ui.label("Estilo:").classes(
                "pe-alt-texto text-caption" if discreto else "pe-alt-texto text-body2")
            for p in tuple(PADROES) + (OPCAO_PADRAO,):
                chave = p["chave"]
                # Só o que o USUÁRIO escolheu é marcado como ativo. Quando ele
                # não escolheu, quem fica marcado é "Padrão" — mesmo que o
                # estilo em vigor por causa do administrador seja o verde, o
                # botão "Verde" não é dele, e fingir o contrário mentiria.
                ativo = chave == escolhido
                destino = link_troca(chave, _caminho_atual())
                props = "flat no-caps dense" + ("" if discreto else " size=sm")
                classes_alt = (
                    "pe-alt pe-alt--ativo"
                    if ativo else "pe-alt pe-alt--inativo"
                ) + (" text-caption" if discreto else " text-body2")
                with ui.button(
                        p["rotulo"],
                        on_click=lambda d=destino: ui.navigate.to(d),
                ).props(props).classes(classes_alt).props(
                        f'data-testid="estilo-{chave}"'):
                    ui.tooltip(
                        f"{p['rotulo']} - {p['descricao']}"
                        + (" (ativo)" if ativo else ""))
                    if not discreto and ativo:
                        ui.icon("check", size="16px").classes("q-mr-xs")
            # Rótulo do que está valendo. Sem estilo imposto não há nome de
            # estilo para mostrar, e a resposta útil é DE ONDE vem a cor: o
            # padrão é a cor que o administrador configurou no módulo.
            ui.label(ROTULOS.get(padrao) or "cor do módulo").props(
                'data-testid="estilo-atual"').classes(
                "pe-alt-texto text-caption q-px-sm")
    except Exception:
        try:
            import logging
            logging.getLogger(__name__).exception(
                "preview_estilos: alternador nao pode ser montado")
        except Exception:
            pass


def barra_home(padrao: str, url_base: str = "/", paleta: dict = None) -> None:
    """Barra de escolha de estilo na Home (assinatura antiga do prototipo)."""
    barra_alternador(padrao, discreto=False)


def resumo_padroes() -> str:
    """Uma linha com os 4 padrões — usado em relatório de QA."""
    return " | ".join(f"{p['rotulo']} ({p['chave']})" for p in PADROES)
