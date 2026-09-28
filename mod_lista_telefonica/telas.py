"""EN: Phone directory — single search field, cascading unit selects, 3-column grid,
admin CRUD and printing (PDF download + browser print). Route /lista-telefonica.

PT-BR: Tela da Lista Telefônica — busca em UM campo (nome, telefone ou unidade),
três selects de unidade em cascata, grade de 3+ colunas, CRUD do administrador na
própria navegação e impressão (PDF para baixar + impressão do navegador).
Rota /lista-telefonica.
"""

import sys, os, re
from urllib.parse import urlencode

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from nicegui import ui, run
from mod_intranet import autenticacao
from mod_intranet.aba_modulo import cabecalho, campo_busca
from mod_intranet.tema_modulo import ler_tema, notificar
from mod_intranet.ui_comum import botao, botao_icone, dialogo_card
from mod_lista_telefonica import bd_manipulador as lista
from mod_lista_telefonica import impressao

log = __import__("mod_intranet.observabilidade", fromlist=["get_logger"]).get_logger("lista_telefonica")

CHAVE = "lista_telefonica"

# Quem tem telefone de RECADO, por matrícula. É preenchido por
# `_carregar_arvore` a cada desenho da tela e consultado por cartão.
# Começa VAZIO, e não `None`: `_contato_e_recado` é chamado durante o desenho
# dos cartões, e um nome não definido ali viraria `NameError` — a dependência
# "a árvore vem antes dos cartões" é real, mas implícita, e implícita é a
# forma de defeito que só aparece depois, em outra tela.
_cache_recado = {}
TEXTO_HEADER = ("Navegue por secretaria, setor e subsetor; busque por nome, telefone ou "
                "unidade. Contatos em ordem alfabética.")

# Grade de contatos. O pedido é "no mínimo 3 colunas", então o `minmax` tem de
# caber três vezes no contentor mais estreito do desktop. A conta:
#   3 colunas × 200px + 2 vãos × 12px = 624px
# Com 260px eram necessárias 804px e, num contentor de 673px (janela de 800px
# menos a margem da página), a grade caía em DUAS colunas — o mínimo pedido não
# era cumprido. 200px resolve e ainda dá 1 coluna no celular (mobile-first).
# `ui.row()` não serve aqui: é flex e nunca quebra em colunas.
# `align-items: stretch` (o padrão do grid) e a ALTURA FIXA do cartão são o que
# fazem todos os cartões terem o MESMO tamanho. Com `align-items: start` cada
# cartão media o próprio conteúdo e a coluna fica com o topo alinhado mas
# alturas diferentes — que é o oposto de "padrão em tamanho igual para todos".
CSS_GRADE = ("display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); "
             "gap: 0.75rem; align-items: stretch;")
ALTURA_CARTAO = "6.9rem"   # 4 linhas: nome+ações, telefone, "deixe recado"
                          # (só nos de recado) e matrícula/unidade. Antes eram
                          # 5.9rem com 3 linhas; o "deixe recado" cabe na MESMA
                          # linha visual do telefone quando não há recado, e
                          # quem tem recado ganha a 4ª linha. A altura cobre as
                          # duas situações para os cartões continuarem iguais —
                          # é a regra de "3 colunas de tamanho igual" que
                          # vale mais do que poupar 1rem.

# Folha de impressão: esconde cabeçalho, menu, busca, navegação e botões e deixa
# só a lista, em 3 colunas. Sem JavaScript — só CSS `@media print`.
CSS_IMPRESSAO = """<style>
@media print {
  header, footer, .q-drawer, .q-menu, .q-dialog, .no-print,
  [data-testid^="lista-nav"], [data-testid^="lista-busca"], [data-testid^="lista-limpar"],
  [data-testid^="lista-admin"], [data-testid^="lista-ligar"], [data-testid^="lista-imprimir"],
  [data-testid^="lista-pdf"] { display: none !important; }
  /* `body[class]` (e não só `body`) porque a classe de fundo do Quasar/Tailwind
     (`bg-grey-2`) é `!important` e tem especificidade maior que `body`. */
  body, body[class], .q-page, .q-page-container, .nicegui-content { background: #fff !important; }
  .lista-cabecalho .text-caption { display: none !important; }
  .lista-cabecalho .q-card { box-shadow: none !important; border-left-width: 2px !important; }
  .lista-impressao { box-shadow: none !important; border: 0 !important; padding: 0 !important; }
  .lista-impressao .lista-grade {
    grid-template-columns: repeat(3, 1fr) !important; gap: 0.25rem !important;
  }
  .lista-impressao .lista-cartao-contato {
    break-inside: avoid; border-color: #bbb !important;
    padding: 2px 6px !important;
  }
  /* O nome continua na 1ª linha e o telefone na 2ª (é o que o cartão já é na
     tela); na folha o cartão só encolhe, para caber mais por página. */
  .lista-impressao a { color: #000 !important; text-decoration: none !important; }
  .lista-impressao a[href^="tel:"]::after { content: "" !important; }
  @page { size: A4; margin: 10mm; }
}
</style>"""


def _pode_ver(user_nome, perfil):
    """EN: Access gate for the screen. PT-BR: Porta de acesso da tela."""
    if perfil == "administrador_geral":
        return True
    try:
        return autenticacao.validar_acesso_modulo(user_nome, "lista_telefonica")
    except Exception:
        _falha("pode_ver", f"falha ao validar acesso de {user_nome}")
        return False


def _eh_admin(user_nome, perfil):
    """EN: Admin gate — re-checked inside every write handler. PT-BR: Porta de administrador.

    Fecha (devolve `False`) quando a consulta falha: em dúvida, nega.
    """
    try:
        return perfil == "administrador_geral" or autenticacao.eh_admin_do_modulo(
            user_nome, "lista_telefonica")
    except Exception:
        _falha("eh_admin", f"falha ao checar administrador de {user_nome}")
        return False


def _falha(funcao, detalhe=""):
    """EN: Logs a failure in the module's cascading-fallback pattern.

    PT-BR: Registra uma falha no padrão em cascata do módulo
    (`_log()` -> `log` -> `observabilidade.get_logger`), sem derrubar a tela.
    """
    try:
        try:
            _log().exception("%s falhou: %s", funcao, detalhe)
        except NameError:
            try:
                log.exception("%s falhou: %s", funcao, detalhe)
            except NameError:
                from mod_intranet import observabilidade as _obs_fail
                _obs_fail.get_logger("lista_telefonica").exception(
                    "%s falhou: %s", funcao, detalhe)
    except Exception:
        pass


def _falhar(funcao, detalhe=""):
    """EN: Logs AND notifies — the pair every except block of this screen uses.

    PT-BR: Registra E avisa — o par usado por todo `except` desta tela: o erro
    nunca some só no log, o usuário sempre fica sabendo.
    """
    _falha(funcao, detalhe)
    try:
        from mod_intranet.tema_modulo import notificar as _notificar_fail
        _notificar_fail("Erro interno. Tente novamente.", tipo="error")
    except Exception:
        pass


def _testid(elemento, props=""):
    """EN: Applies props/testid to an element, tolerating `None` (fail-soft).

    PT-BR: Aplica props/testid num elemento tolerando `None` (fail-soft) — as
    fábricas de botão devolvem `None` quando o tema falha.
    """
    try:
        if elemento is not None and props:
            elemento.props(props)
    except Exception:
        _falha("aplicar props", props)
    return elemento


def _texto_curto(texto, tamanho=60):
    """EN: Safe text for an attribute (quotes/angle brackets out).

    PT-BR: Texto seguro para atributo (tira aspas e sinais de maior/menor).
    """
    try:
        limpo = str(texto or "").replace('"', "'").replace("<", "").replace(">", "")
        return limpo[:tamanho]
    except Exception:
        return ""


# Rota de download do PDF, registrada uma única vez na importação da tela (o
# `main.py` importa este módulo dentro da página, então a rota existe antes de
# qualquer clique do usuário).
try:
    impressao.registrar_rota_pdf()
except Exception:
    _falha("registrar_rota_pdf", "rota de download do PDF indisponível")


def _contato_e_recado(user_nome):
    """EN: Is this contact's number the SECTOR's line (message phone)?

    PT-BR: O telefone deste contato é o do SETOR (a pessoa deixa recado)?

    O nome do servidor já é a **matrícula** no contato vinculado, e é por
    isso que a consulta bate em cheio: um contato digitado à mão não tem
    `user_nome` e cai em `False` sem tocar o banco. Um cache no escopo do
    desenho evita repetir a consulta para cada cartão da grade — que com
    mais de mil servidores seria mil idas ao cadastro de usuários.

    EN: the cache is a module-level dict filled by `_carregar_arvore`; it
    starts EMPTY (not `None`), so a contact drawn before the first tree load
    answers False instead of raising `NameError`.
    PT-BR: o cache é um dicionário de módulo preenchido por `_carregar_arvore`;
    começa VAZIO (não `None`), para que um contato desenhado antes da primeira
    carga da árvore responda False em vez de levantar `NameError`."""
    if not user_nome:
        return False
    return bool(_cache_recado.get(user_nome))


def _tel_limpo(telefone):
    """EN: Phone reduced to digits and '+' for the `tel:` link.

    PT-BR: Telefone só com dígito e `+` para montar o link `tel:`.
    """
    try:
        from mod_intranet import telefone as _tel
        limpo = _tel.normalizar_telefone(_tel.obter_ddi(telefone), telefone)
        if not limpo:
            limpo = re.sub(r"[^0-9+]", "", telefone or "")
        return limpo
    except Exception:
        return re.sub(r"[^0-9+]", "", telefone or "")


def _tel_exibicao(telefone):
    """EN: Phone for reading, in the shape a Brazilian reads it.

    PT-BR: Telefone como leitura, no formato que se lê no Brasil.

    O "+55" (código do país) é TIRADO de propósito. Quem liga do mesmo
    município não precisa dele, e no cartão de ~216px da grade de 3 colunas o
    prefixo empurrava o telefone para duas linhas e cortava o nome do contato
    ("Gabriela Teixe…"). O número que o `tel:` usa é o completo e não muda —
    o que muda é só o texto exibido.

    A formatação é feita aqui, pelos dígitos, em vez de chamar
    `telefone.formatar_para_exibicao`: aquela função devolve o que já está
    gravado e, num número parcial, devolve sem os separadores — daí o resultado
    inconsistente entre "(35) 3591-5101" e "35915104" lado a lado.
    """
    try:
        digitos = "".join(c for c in str(telefone or "") if c.isdigit())
        if digitos.startswith("55") and len(digitos) > 10:
            digitos = digitos[2:]
        if len(digitos) == 11:
            # celular com 9 dígitos: (DD) 9XXXX-XXXX
            return f"({digitos[:2]}) {digitos[2:7]}-{digitos[7:]}"
        if len(digitos) == 10:
            return f"({digitos[:2]}) {digitos[2:6]}-{digitos[6:]}"
        return str(telefone or "").strip() or "—"
    except Exception:
        return str(telefone or "").strip() or "—"


def _caminho_unidade(uid):
    """EN: Hierarchical path Secretaria > Setor > Subsetor.

    PT-BR: Caminho hierárquico Secretaria > Setor > Subsetor.
    """
    try:
        uni = lista.obter_unidade(uid)
        if not uni:
            return ""
        partes = [uni[1]]
        pid = uni[3]
        while pid:
            p = lista.obter_unidade(pid)
            if not p:
                break
            partes.append(p[1])
            pid = p[3]
        return " > ".join(reversed(partes))
    except Exception:
        _falha("caminho_unidade", f"unidade {uid}")
        return ""


def _no_por_id(arvore, uid):
    """EN: Finds a unit node by id in the tree. PT-BR: Acha o nó de uma unidade pelo id."""
    try:
        for no in arvore or []:
            if no.get("id") == uid:
                return no
            achado = _no_por_id(no.get("filhos") or [], uid)
            if achado:
                return achado
    except Exception:
        _falha("no por id", f"unidade {uid}")
    return None


def _recortar(arvore, uid):
    """EN: Returns the subtree of `uid` — the organogram slice of the list.

    PT-BR: Devolve a subárvore de `uid` (o recorte do organograma na lista). Com
    filtro ligado o nó só existe se sobrou contato, daí o `[]` e a tela avisar
    que o recorte ficou vazio.
    """
    if uid is None:
        return arvore or []
    try:
        achado = _no_por_id(arvore, uid)
        return [achado] if achado else []
    except Exception:
        _falha("recortar arvore", f"unidade {uid}")
        return []


def _unidades_para_selecao(arvore):
    """EN: Flat list (id, "path (type)") for the unit pickers of the dialogs.

    PT-BR: Lista plana (id, "caminho (tipo)") para os seletores de unidade dos
    diálogos. Sai da árvore, que já vem alfabética do banco.
    """
    opcoes = []
    try:
        def andar(nos, prefixo):
            """EN: Walks one level. PT-BR: Percorre um nível."""
            for no in nos or []:
                nome = no.get("nome") or ""
                caminho = f"{prefixo} > {nome}" if prefixo else nome
                opcoes.append((no.get("id"), f"{caminho} ({no.get('tipo') or ''})"))
                andar(no.get("filhos") or [], caminho)
        andar(arvore, "")
    except Exception:
        _falha("unidades para selecao", "opcoes de unidade")
    return opcoes


def _opcoes_pai(arvore, tipo):
    """EN: Parent options per unit type (secretaria has none).

    PT-BR: Opções de pai por tipo de unidade (secretaria não tem pai).
    """
    try:
        if tipo == "secretaria":
            return {}
        if tipo == "subsetor":
            opcoes = {}
            for raiz in arvore or []:
                for filho in raiz.get("filhos") or []:
                    opcoes[filho.get("id")] = f"{raiz.get('nome')} > {filho.get('nome')}"
            return opcoes
        return {raiz.get("id"): (raiz.get("nome") or "") for raiz in arvore or []}
    except Exception:
        _falha("opcoes de pai", str(tipo))
        return {}


def _campo_telefone(rotulo, prefixo_testid, valor=""):
    """EN: DDI + number row (falls back to a plain input).

    PT-BR: Linha DDI + número (cai para `ui.input` simples se o helper falhar).
    """
    try:
        from mod_intranet import telefone as _tel
        campo = _tel.criar_campo_telefone(rotulo=rotulo, valor=valor,
                                          testid_ddi=f"{prefixo_testid}-ddi",
                                          testid_numero=f"{prefixo_testid}-numero")
        if campo:
            return campo
    except Exception:
        _falha("campo de telefone", prefixo_testid)
    try:
        entrada = ui.input(rotulo, value=valor or "").props("outlined dense").classes("w-full")
        _testid(entrada, f'data-testid={prefixo_testid}-numero')
        return {"obter": lambda: entrada.value or "", "definir": lambda v: setattr(entrada, "value", v)}
    except Exception:
        _falha("campo de telefone simples", prefixo_testid)
        return None


def _url_pdf(recorte, termo="", nome="", telefone="", unidade=""):
    """EN: Download URL of the current slice. PT-BR: URL de download do recorte atual.

    `termo` e o filtro UNICO da tela (nome, telefone ou unidade). Os campos
    separados continuam aceitos para quem chama por recorte de impressao.
    """
    try:
        params = {}
        if recorte:
            params["recorte"] = recorte
        for chave, valor in (("termo", termo), ("nome", nome),
                             ("telefone", telefone), ("unidade", unidade)):
            if (valor or "").strip():
                params[chave] = valor.strip()
        if not params:
            return impressao.ROTA_PDF
        return f"{impressao.ROTA_PDF}?{urlencode(params)}"
    except Exception:
        _falha("url do pdf", "query string")
        return impressao.ROTA_PDF


def mostrar_tela(user_nome: str, perfil_global: str = ""):
    try:
        if not _pode_ver(user_nome, perfil_global):
            with ui.column().classes("w-full items-center p-12 gap-3"):
                ui.icon("block", size="64px").classes("text-red-8")
                ui.label("Acesso restrito").classes("text-h6")
                ui.label("Somente usuários com acesso à Lista Telefônica.").classes("text-body2 text-grey-7")
            return

        tema = ler_tema("lista_telefonica", cor_botao="#000000", cor_texto_botao="#FFFFFF",
                        texto_header=TEXTO_HEADER)
        ui.colors(primary=tema["cor_botao"])
        t_cor_titulo = tema["cor_titulo"]
        t_cor_fundo = tema["cor_fundo"]
        t_texto_header = tema["texto_header"]
        cor_botao = tema["cor_botao"]
        cor_texto_botao = tema["cor_texto_botao"]

        # A folha de impressão precisa existir antes de qualquer elemento da
        # lista (é ela que esconde cabeçalho, busca e botões no papel).
        try:
            ui.add_head_html(CSS_IMPRESSAO)
        except Exception:
            _falha("add_head_html", "folha de impressao")

        # UM termo de busca (pesquisa nome, telefone e unidade de uma vez) e
        # TRÊS níveis de unidade em cascata. Antes eram três campos de busca e
        # botões de navegação: o pedido é um campo só, que pesquisa tudo, e o
        # recorte por unidade em selects que se alimentam.
        estado = {"unidade": None, "busca": "",
                  "nivel_1": None, "nivel_2": None, "nivel_3": None}
        campos_busca = []
        campos_cascata = []
        eh_admin = bool(_eh_admin(user_nome, perfil_global))
        # Trava de reentrância da sincronização com o cadastro: dois cliques
        # em "Sincronizar cadastro" disparariam duas leituras de mil usuários
        # ao mesmo tempo, e a segunda criaria contato duplicado.
        _sincronizando = False

        # =================== funções internas ===================
        # Todas são declaradas ANTES da construção da UI: `render_organograma` é
        # chamado no fim e depende delas estar prontas.

        def _ao_filtrar(campo, evento):
            """EN: The single search field changed — re-filter the list.

            PT-BR: O único campo de busca mudou — refiltra a lista.
            """
            try:
                estado[campo] = (getattr(evento, "value", "") or "").strip()
                render_organograma.refresh()
            except Exception:
                _falhar("ao_filtrar", f"campo {campo}")

        def _limpar_busca():
            """EN: Clears the search field, the three selects and the filter state.

            PT-BR: Limpa o campo de busca, os três selects e o estado do filtro.
            """
            try:
                estado["busca"] = ""
                for campo in campos_busca:
                    campo.value = ""
                for chave in ("nivel_1", "nivel_2", "nivel_3"):
                    estado[chave] = None
                for sel in campos_cascata:
                    sel.set_options({})
                if campos_cascata:
                    # NÍVEL 0, e não 1: a raiz do organograma é o nível 0, e o
                    # 1º select é o de "Unidade" (as secretarias). Com o 1 aqui,
                    # limpar a busca trocava as secretarias pelos setores.
                    campos_cascata[0].set_options(
                        _opcoes_nivel(0, _carregar_arvore()))
                    campos_cascata[0].update()
                render_organograma.refresh()
            except Exception:
                _falhar("limpar_busca", "limpeza dos campos")

        def _tem_filtro():
            """EN: True when any of the three filters has text.

            PT-BR: Verdadeiro quando algum dos três filtros tem texto.
            """
            try:
                return bool(estado["busca"].strip()
                            or estado["nivel_1"] or estado["nivel_2"]
                            or estado["nivel_3"])
            except Exception:
                _falha("tem_filtro", "estado dos filtros")
                return False

        def _niveis_da_arvore(arvore):
            """Achata a árvore em uma lista por nível de profundidade.

            Devolve `[{id, nome, nivel, parent_id}]`, um dicionário por nível, do
            raiz para o mais fundo. Como a estrutura é `parent_id`, o número de
            níveis não é fixo: quem decide são os selects, que recebem o nível
            seguinte a partir do que foi escolhido.
            """
            niveis = {}

            def descer(nos, profundidade):
                for no in nos or []:
                    niveis.setdefault(profundidade, []).append({
                        "id": no.get("id"), "nome": no.get("nome") or "",
                        "nivel": profundidade, "parent_id": no.get("pai_id"),
                    })
                    descer(no.get("filhos") or [], profundidade + 1)
            descer(arvore, 0)
            return niveis

        def _opcoes_nivel(nivel, arvore=None):
            """Opções do select de um nível, por nível e não por caminho.

            Cada select mostra só o NOME da unidade daquele nível — é o que o
            usuário espera de uma cascata, e o select ao lado já dá o contexto.
            (Um rótulo com o caminho inteiro "Administração > Patrimônio >
            Compras" foi considerado e descartado: com 12 secretarias e 29
            setores, o rótulo vira uma frase que não cabe no campo.)
            """
            try:
                arv = arvore if arvore is not None else _carregar_arvore()
                niveis = _niveis_da_arvore(arv)
                return {n["id"]: n["nome"] for n in niveis.get(nivel, [])}
            except Exception:
                _falha("opcoes_nivel", f"nivel {nivel}")
                return {}

        def _caminho_do_id(uid, arvore=None):
            """Nome do caminho de uma unidade, para achar as filhas dela."""
            try:
                arv = arvore if arvore is not None else _carregar_arvore()

                def achar(nos):
                    for no in nos or []:
                        if no.get("id") == uid:
                            return no
                        achado = achar(no.get("filhos") or [])
                        if achado:
                            return achado
                    return None
                alvo = achar(arv)
                return alvo or None
            except Exception:
                _falha("caminho_do_id", str(uid))
                return None

        def _preencher_cascata(nivel_escolhido):
            """Repopula os selects a partir do que foi escolhido no nível acima.

            Escolher "Administração" no 1º select traz os setores dela no 2º;
            escolher "Compras" traz o que existe abaixo de Compras no 3º — e o
            que não existir fica vazio e desabilitado, que é a informação
            honesta ("aqui embaixo não tem mais nada").
            """
            try:
                for i in (1, 2, 3):
                    if campos_cascata[i - 1] is None:
                        continue
                    estado[f"nivel_{i + 1}"] = None
                arv = _carregar_arvore()
                alvo = _caminho_do_id(nivel_escolhido, arv) if nivel_escolhido else None
                for i, sel in enumerate(campos_cascata):
                    if sel is None:
                        continue
                    if i == 0:
                        opcoes = _opcoes_nivel(0, arv)
                    else:
                        opcoes = {f["id"]: f["nome"]
                                  for f in (alvo.get("filhos") or [])} if alvo else {}
                    sel.set_options(opcoes)
                    sel.update()
                    if opcoes:
                        sel.enable()
                    else:
                        sel.disable()
            except Exception:
                _falha("preencher_cascata", str(nivel_escolhido))

        def _ao_mudar_nivel(nivel, evento):
            """Um select do organograma mudou — recorta e redesenha."""
            try:
                estado[f"nivel_{nivel}"] = getattr(evento, "value", None)
                if nivel == 1:
                    _preencher_cascata(estado["nivel_1"])
                render_organograma.refresh()
            except Exception:
                _falhar("ao_mudar_nivel", f"nivel {nivel}")

        def _carregar_arvore():
            """EN: Full organogram (already alphabetical from the DB).

            PT-BR: Organograma completo (já alfabético, veio do banco). Os botões
            de navegação usam a árvore SEM filtro — senão o usuário perderia o
            botão da secretaria assim que digitasse uma letra.
            """
            global _cache_recado
            try:
                arvore = lista.listar_arvore_contatos(raiz_id=None)
            except Exception:
                _falha("carregar arvore", "listar_arvore_contatos")
                return []
            # Quem tem telefone de recado. Uma consulta por desenho da tela,
            # e NÃO uma por cartão: a grade desenha mais de mil cartões de
            # uma vez, e perguntar ao cadastro de usuários por cada um
            # transformava a tela em uma espera.
            try:
                from mod_intranet import integracoes as _int_rec
                _cache_recado = _int_rec.telefones_de_recado_para_lista()
            except Exception as e:
                _cache_recado = {}
                log.warning(f"lista: cache de recado não carregou ({e})")
            return arvore

        def _escolher(uid):
            """EN: Organogram button — sets the slice (click again to go back).

            PT-BR: Botão do organograma — fixa o recorte (clicar de novo volta).
            """
            try:
                estado["unidade"] = None if uid == estado["unidade"] else uid
                render_organograma.refresh()
            except Exception:
                _falhar("escolher unidade", str(uid))

        def _cabecalho_recorte(recorte):
            """EN: Slice title, count and print actions (plus admin actions).

            PT-BR: Título do recorte, contagem e ações de impressão (mais as
            ações do administrador).
            """
            try:
                uni = lista.obter_unidade(estado["unidade"]) if estado["unidade"] else None
                nome_unidade = uni[1] if uni else ""
                with ui.row().classes("w-full items-center justify-between flex-wrap").style(
                        "gap: 0.5rem; min-width: 0"):
                    with ui.column().classes("gap-0").style("min-width: 0"):
                        ui.label(nome_unidade or "Todas as unidades").classes("text-subtitle1 font-bold")
                        caminho = _caminho_unidade(estado["unidade"]) if uni else ""
                        if caminho and caminho != nome_unidade:
                            ui.label(caminho).classes("text-caption text-grey-6")
                        if uni and uni[5]:
                            ui.label(f"Telefone da unidade: {_tel_exibicao(uni[5])}") \
                                .classes("text-caption text-grey-7")
                        ui.label(f"{impressao.contar(recorte)} contato(s) — ordem alfabética") \
                            .classes("text-caption text-grey-5")
                    with ui.row().classes("items-center flex-wrap shrink-0").style("gap: 0.4rem"):
                        _botao_pdf()
                        _testid(botao("Imprimir", icone="print", on_click=_imprimir,
                                      variante="secundario", chave_modulo=CHAVE,
                                      extra_classes="no-print shrink-0"),
                                'data-testid=lista-imprimir aria-label="Imprimir a lista"')
                        if eh_admin:
                            _testid(botao("Novo contato", icone="person_add",
                                          on_click=_dlg_novo_contato, variante="primario",
                                          chave_modulo=CHAVE, extra_classes="no-print shrink-0"),
                                    'data-testid=lista-admin-novo-contato')
                            _testid(botao("Nova unidade", icone="add_business",
                                          on_click=_dlg_nova_unidade, variante="secundario",
                                          chave_modulo=CHAVE, extra_classes="no-print shrink-0"),
                                    'data-testid=lista-admin-nova-unidade')
                            _testid(botao("Editar unidade", icone="edit",
                                          on_click=_dlg_editar_unidade, variante="secundario",
                                          chave_modulo=CHAVE, extra_classes="no-print shrink-0"),
                                    'data-testid=lista-admin-editar-unidade')
                            _testid(botao("Sincronizar cadastro", icone="sync",
                                          on_click=_sincronizar_cadastro, variante="secundario",
                                          chave_modulo=CHAVE, extra_classes="no-print shrink-0"),
                                    'data-testid=lista-admin-sincronizar')
            except Exception:
                _falhar("cabecalho do recorte", "titulo e acoes")

        async def _sincronizar_cadastro():
            """EN: Mirror registered servers into the directory (admin only).

            PT-BR: Espelha no diretório os servidores do cadastro (só admin).

            `async` + `run.io_bound` porque a sincronização lê mais de mil
            usuários e escreve contatos: um handler `sync` travaria o
            event-loop por segundos e derrubaria a conexão de quem Admin e de
            quem está na mesma tela. O botão fica desabilitado durante a
            operação para não haver dois cliques pedindo a mesma coisa.
            """
            nonlocal _sincronizando
            try:
                if _sincronizando:
                    return
                _sincronizando = True
                from mod_intranet import integracoes as _int
                with ui.linear_progress(value=0).props("rounded") as barra:
                    ui.tooltip("Lendo o cadastro de servidores...")
                    # pelo NÚCLEO, nunca direto no módulo de cadastro: os dois
                    # têm banco próprio e o AGENTS.md §2 proíbe a consulta
                    # cruzada. `integracoes` é a costura pública autorizada.
                    resumo = await run.io_bound(
                        _int.espelhar_cadastro_na_lista_telefonica, user_nome)
                    barra.value = 1.0
                if resumo.get("erro"):
                    notificar("Falha ao sincronizar com o cadastro.", tipo="negative")
                    return
                partes = []
                if resumo["criados"]:
                    partes.append(f"{resumo['criados']} contato(s) criado(s)")
                if resumo["atualizados"]:
                    partes.append(f"{resumo['atualizados']} telefone(s) atualizado(s)")
                if resumo["sem_telefone"]:
                    partes.append(f"{resumo['sem_telefone']} sem telefone liberado")
                if resumo["sem_unidade"]:
                    partes.append(f"{resumo['sem_unidade']} sem unidade correspondente")
                notificar("Sincronizado: " + (", ".join(partes) if partes
                                              else "nada mudou."),
                          tipo="positive")
                # repopula a cascata e redesenha: a sincronização pode ter
                # criado unidades novas, e um select com as opções antigas
                # esconderia o resultado do clique que o usuário acabou de dar
                _preencher_cascata(None)
                render_organograma.refresh()
            except Exception as e:
                _falhar("sincronizar cadastro", str(e))
            finally:
                _sincronizando = False

        async def _auto_sincronizar():
            """Reespelha o cadastro sozinho quando o diretório está velho.

            Silencioso de propósito: quem abriu a tela não pediu nada e não
            precisa de um aviso de "3 contatos sincronizados". A diferença
            entre o diretário velho e o novo é que o contato simplesmente
            passa a estar lá. Um aviso barulhento a cada 15 minutos seria
            treinar o usuário a ignorar os avisos — e o dia em que aparecer
            um importante, ele também ignoraria."""
            nonlocal _sincronizando
            try:
                if _sincronizando:
                    return
                _sincronizando = True
                from mod_intranet import integracoes as _int
                resumo = await run.io_bound(
                    _int.espelhar_cadastro_na_lista_telefonica, "sistema")
                if resumo.get("erro"):
                    return
                if resumo["criados"] or resumo["atualizados"]:
                    log.info(
                        "lista: diretário atualizado sozinho — "
                        f"criados={resumo['criados']} "
                        f"atualizados={resumo['atualizados']}")
                    _preencher_cascata(None)
                    render_organograma.refresh()
            except Exception:
                log.exception("falha na sincronização automática do diretório")
            finally:
                _sincronizando = False

        def _botao_pdf():
            """EN: Download link to the PDF of the current slice.
            PT-BR: Link de download do PDF do recorte atual. É um `<a>` de
            verdade (e não botão + JS): só uma requisição HTTP traz o arquivo
            para o disco do usuário, então não há JavaScript aqui.
            """
            try:
                # O recorte do PDF e o MESMO da tela: o nivel mais fundo da
                # cascata e o termo unico. Ler o estado antigo aqui gerava um
                # PDF diferente do que a tela mostra.
                nivel = (estado.get("nivel_3") or estado.get("nivel_2")
                         or estado.get("nivel_1"))
                alvo = _url_pdf(nivel, estado.get("busca", ""))
                with ui.link(target=alvo) as link:
                    link.classes("no-underline rounded-lg px-4 py-2 shadow-sm no-print shrink-0 "
                                 "cursor-pointer inline-flex items-center")
                    link.style(f"background:{cor_botao};color:{cor_texto_botao};gap:0.35rem;")
                    _testid(link, 'data-testid=lista-pdf-baixar '
                                  'aria-label="Baixar a lista em PDF"')
                    ui.icon("download", size="18px")
                    ui.label("Baixar PDF").classes("text-body2")
            except Exception:
                _falhar("botao de pdf", "link de download")

        def _imprimir():
            """EN: Opens the browser print dialog (the print sheet does the rest).

            PT-BR: Abre a impressão do navegador (a folha de impressão faz o
            resto). Exceção intencional de "sem JS direto": via
            `ui.run_javascript` (API oficial do NiceGUI), porque não existe
            elemento NiceGUI para `window.print()` — mesmo motivo já registrado
            em `mod_intranet/telas.py` (título da aba) e nesta tela (diálogo
            "Ligar agora").
            """
            try:
                ui.run_javascript("window.print()")
            except Exception:
                _falhar("imprimir", "window.print()")

        def _desenhar_blocos(nos, nivel, prefixo):
            """EN: One continuous contact grid, grouped by the organogram.

            PT-BR: UMA grade contínua de contatos, agrupada pelo organograma.

            Antes cada unidade abria a SUA grade, e como quase toda unidade tem
            um contato só, a grade de 3 colunas nunca aparecia — o resultado era
            uma coluna de cartões, um por unidade, que é o oposto do pedido.
            Aqui a grade é uma só: os cartões fluem em 3+ colunas e cada um
            carrega o caminho da sua unidade (secretaria > setor > subsetor).
            A hierarquia continua legível de dois jeitos, porque a ordem do
            banco já é alfabética por nível e o cartão diz a que unidade ele
            pertence.

            Unidades sem contato não viram cartão: viram uma linha de
            "seção" ocupando a largura toda da grade, que é o que dá a leitura
            de "aonde eu estou" sem custar uma coluna.
            """
            try:
                with ui.element("div").classes("w-full lista-grade").style(CSS_GRADE) \
                        .props('data-testid=lista-grade role="list"'):
                    _preencher_grade(nos, nivel, prefixo)
            except Exception:
                _falhar("desenhar blocos", "grade de contatos")

        def _preencher_grade(nos, nivel, prefixo):
            """EN: Fills the grid in place, in alphabetical hierarchy order.

            PT-BR: Preenche a grade no lugar, na ordem alfabética da
            hierarquia. A profundidade do organograma não é fixa: entra
            quantos níveis existirem (`nivel` do banco).
            """
            try:
                for no in nos or []:
                    nome = no.get("nome") or ""
                    tipo = no.get("tipo") or ""
                    caminho = f"{prefixo} > {nome}" if prefixo else nome
                    contatos = no.get("contatos") or []
                    if contatos:
                        for contato in contatos:
                            _cartao_contato(contato, caminho)
                    elif not _tem_filtro():
                        # Unidade sem contato vira uma faixa de seção, que
                        # ocupa a linha toda: na tela informa que a unidade
                        # existe; no papel (`no-print`) some, porque um título
                        # sozinho na folha impressa é só ruído.
                        with ui.element("div").classes(
                                "lista-secao no-print").style(
                                "grid-column: 1 / -1; display: flex; align-items: center; gap: 0.4rem; min-width: 0; padding: 0.5rem 0 0.15rem; border-top: 1px solid rgba(0,0,0,.12)"):
                            ui.icon({"secretaria": "account_balance", "setor": "business",
                                     "subsetor": "folder"}.get(tipo, "folder"),
                                    size="16px").classes("text-grey-6 shrink-0")
                            ui.label(nome).classes(
                                "text-subtitle2 font-bold text-grey-9" if nivel == 0
                                else "text-body2 font-medium text-grey-8")
                            if no.get("telefone"):
                                ui.label(_tel_exibicao(no.get("telefone"))) \
                                    .classes("text-caption text-grey-6 font-mono")
                    _preencher_grade(no.get("filhos") or [], nivel + 1, caminho)
            except Exception:
                _falhar("desenhar blocos", "grade de contatos")

        def _cartao_contato(contato, caminho):
            """EN: Contact card — name (tel: link), phone, matricula, unit, actions.

            PT-BR: Cartão de contato — nome (link tel:), telefone, matrícula,
            unidade e ações do administrador.

            A ESTRUTURA é coluna, com os botões só na PRIMEIRA linha. Com os
            botões como irmãos de uma coluna de texto (o desenho anterior), eles
            espremiam a largura em TODAS as linhas: num cartão de ~216px da
            grade de 3 colunas, o telefone "(35) 3591-5101" quebrava no meio
            ("3591-" / "5101") e o nome ficava cortado. Com os botões apenas na
            linha do nome, telefone e unidade ganham a largura inteira.
            """
            try:
                cid, _uid, nome, telefone, user_nome, tipo = contato[:6]
                with ui.element("div").classes(
                        "lista-cartao-contato border rounded-lg px-3 py-2 flex flex-col "
                        "justify-between overflow-hidden hover:bg-blue-50/50") \
                        .style(f"min-width: 0; max-width: 100%; gap: 0.1rem; "
                               f"height: {ALTURA_CARTAO}; box-sizing: border-box") \
                        .props(f'data-testid=lista-contato-{cid} role="listitem" '
                               f'aria-label="{_texto_curto(nome)} {caminho}"'):
                    # Linha 1: nome (trunca) + ações. `flex: 1 1 0` + `min-width: 0`
                    # para o nome encolher no que sobra sem esticar o cartão.
                    with ui.row().classes("items-center").style(
                            "gap: 0.4rem; min-width: 0; width: 100%"):
                        ui.icon("person" if tipo == "vinculado" else "badge") \
                            .classes("text-grey-6 shrink-0")
                        limpo = _tel_limpo(telefone)
                        with ui.column().classes("gap-0") \
                                .style("min-width: 0; flex: 1 1 0; overflow: hidden"):
                            if limpo:
                                ui.link(nome, target=f"tel:{limpo}") \
                                    .classes("font-medium text-primary truncate") \
                                    .tooltip("Toque para ligar (celular)")
                            else:
                                ui.label(nome).classes("font-medium truncate")
                        with ui.row().classes("items-center shrink-0").style("gap: 0.15rem"):
                            _testid(botao_icone("phone",
                                                on_click=lambda: _dlg_ligar(nome, telefone),
                                                tooltip="Ligar / opções",
                                                chave_modulo=CHAVE,
                                                extra_classes="no-print"),
                                    'data-testid=lista-ligar aria-label="Ligar"')
                            if eh_admin:
                                _testid(botao_icone("edit",
                                                    on_click=lambda: _dlg_editar_contato(
                                                        cid, nome, telefone),
                                                    tooltip="Editar contato",
                                                    chave_modulo=CHAVE,
                                                    extra_classes="no-print"),
                                        f'data-testid=lista-contato-editar-{cid} '
                                        f'aria-label="Editar {_texto_curto(nome)}"')
                                _testid(botao_icone("delete",
                                                    on_click=lambda: _dlg_remover_contato(
                                                        cid, nome),
                                                    tooltip="Remover contato",
                                                    chave_modulo=CHAVE,
                                                    extra_classes="no-print"),
                                        f'data-testid=lista-contato-remover-{cid} '
                                        f'aria-label="Remover {_texto_curto(nome)}"')
                    # Linha 2: telefone, com a largura inteira do cartão. O
                    # "deixe recado" vem logo abaixo, e não como sufixo do
                    # número: o número é o do SETOR, e quem liga precisa saber
                    # que não vai falar com a pessoa. Escrever "(35) 3591-5150
                    # (deixe recado)" faria o texto não caber na coluna de
                    # ~216px e empurraria o nome.
                    with ui.column().classes("gap-0").style("min-width: 0; width: 100%"):
                        ui.label(_tel_exibicao(telefone)).classes(
                            "text-caption text-grey-6 font-mono truncate")
                        if _contato_e_recado(user_nome):
                            ui.label("deixe recado").classes(
                                "text-caption text-grey-5 italic truncate") \
                                .props('data-testid=lista-contato-recado')
                    # Linha 3: matrícula e unidade. A unidade é o que diz a que
                    # secretaria/setor/subsetor o contato pertence — como a grade
                    # é uma só e os cartões fluem em 3+ colunas, sem este rótulo
                    # o diretório perderia a hierarquia do organograma.
                    with ui.row().classes("items-center").style(
                            "gap: 0.35rem; min-width: 0; width: 100%"):
                        if user_nome:
                            ui.label(f"@{user_nome}").classes(
                                "text-caption text-grey-5 shrink-0")
                        if caminho:
                            ui.label(caminho).classes(
                                "text-caption text-grey-5 truncate").style(
                                "min-width: 0").tooltip(caminho)
            except Exception:
                _falhar("cartao de contato", str(caminho))

        def _dlg_ligar(nome, telefone):
            """EN: Call dialog with the `tel:` handoff. PT-BR: Diálogo de ligação com o `tel:`."""
            try:
                tel = _tel_limpo(telefone)
                with dialogo_card(titulo=f"Contato — {nome}", largura="w-[380px]",
                                  chave_modulo=CHAVE, max_altura=False) as (dlg, card):
                    ui.label(f"Telefone: {_tel_exibicao(telefone)}").classes("text-body1 font-mono")
                    ui.label("No celular, escolha Ligar. No desktop, o discador pode não estar configurado.") \
                        .classes("text-caption text-grey-6")
                    with ui.row().classes("w-full justify-between mt-2"):
                        ui.button("Fechar", on_click=dlg.close).props("flat")
                        if tel:
                            def _ir_tel():
                                try:
                                    # Exceção intencional de "sem JS direto": o
                                    # NiceGUI não expõe `tel:` — `window.location`
                                    # é a via oficial (`ui.run_javascript`).
                                    ui.run_javascript(f"window.location.href='tel:{tel}'")
                                except Exception:
                                    pass
                                dlg.close()
                            botao("Ligar agora", icone="call", on_click=_ir_tel,
                                  variante="primario", chave_modulo=CHAVE)
                dlg.open()
            except Exception:
                _falhar("dlg_ligar", nome)

        def _guarda_admin(acao):
            """EN: Server-side admin check inside every write handler.

            PT-BR: Guarda de administrador NO SERVIDOR, dentro de cada handler de
            escrita — esconder o botão não é proteção: o evento chega pelo
            socket e o cliente manda o que quiser.
            """
            try:
                if _eh_admin(user_nome, perfil_global):
                    return True
                notificar(f"Apenas administradores podem {acao}.", tipo="warning")
            except Exception:
                _falha("guarda de administrador", acao)
            return False

        def _dlg_novo_contato():
            """EN: New contact — unit, name, phone. PT-BR: Novo contato — unidade, nome, telefone."""
            if not _guarda_admin("criar contatos"):
                return
            try:
                opcoes = dict(_unidades_para_selecao(_carregar_arvore()))
                inicial = estado["unidade"] if estado["unidade"] in opcoes else None
                with dialogo_card(titulo="Novo contato", largura="w-[420px]",
                                  chave_modulo=CHAVE) as (dlg, card):
                    sel_unidade = ui.select(opcoes, label="Unidade *", value=inicial) \
                        .props("outlined dense clearable").classes("w-full") \
                        .props('data-testid=lista-novo-contato-unidade')
                    inp_nome = ui.input("Nome *").props("outlined dense").classes("w-full") \
                        .props('data-testid=lista-novo-contato-nome')
                    campo_tel = _campo_telefone("Telefone *", "lista-novo-contato")

                    def _salvar():
                        try:
                            if not _guarda_admin("criar contatos"):
                                return
                            if not sel_unidade.value:
                                notificar("Escolha a unidade.", tipo="warning")
                                return
                            ok, msg = lista.criar_contato(
                                sel_unidade.value, inp_nome.value or "",
                                campo_tel["obter"]() if campo_tel else "", ator=user_nome)
                            notificar(msg, tipo="positive" if ok else "negative")
                            if ok:
                                dlg.close()
                                estado["unidade"] = sel_unidade.value
                                render_organograma.refresh()
                        except Exception:
                            _falhar("salvar novo contato", str(inp_nome.value))

                    with ui.row().classes("w-full justify-end mt-2").style("gap: 0.5rem"):
                        ui.button("Cancelar", on_click=dlg.close).props("flat")
                        _testid(botao("Salvar", icone="save", on_click=_salvar, variante="primario",
                                      chave_modulo=CHAVE),
                                'data-testid=lista-novo-contato-salvar')
                dlg.open()
            except Exception:
                _falhar("dlg_novo_contato", "dialogo")

        def _dlg_editar_contato(cid, nome, telefone):
            """EN: Edit contact — name and phone. PT-BR: Editar contato — nome e telefone."""
            if not _guarda_admin("editar contatos"):
                return
            try:
                with dialogo_card(titulo=f"Editar — {nome}", largura="w-[380px]",
                                  chave_modulo=CHAVE) as (dlg, card):
                    inp_nome = ui.input("Nome", value=nome).props("outlined dense") \
                        .classes("w-full").props('data-testid=lista-editar-contato-nome')
                    campo_tel = _campo_telefone("Telefone", "lista-editar-contato", telefone)

                    def _salvar():
                        try:
                            if not _guarda_admin("editar contatos"):
                                return
                            ok, msg = lista.editar_contato(
                                cid, nome=inp_nome.value or "",
                                telefone=campo_tel["obter"]() if campo_tel else None,
                                ator=user_nome)
                            notificar(msg, tipo="positive" if ok else "negative")
                            if ok:
                                dlg.close()
                                render_organograma.refresh()
                        except Exception:
                            _falhar("salvar edicao de contato", str(cid))

                    with ui.row().classes("w-full justify-end mt-2").style("gap: 0.5rem"):
                        ui.button("Cancelar", on_click=dlg.close).props("flat")
                        _testid(botao("Salvar", icone="save", on_click=_salvar, variante="primario",
                                      chave_modulo=CHAVE),
                                'data-testid=lista-editar-contato-salvar')
                dlg.open()
            except Exception:
                _falhar("dlg_editar_contato", str(cid))

        def _dlg_remover_contato(cid, nome):
            """EN: Remove contact, with confirmation. PT-BR: Remover contato, com confirmação."""
            if not _guarda_admin("remover contatos"):
                return
            try:
                with dialogo_card(titulo="Remover contato", largura="w-[380px]",
                                  chave_modulo=CHAVE, max_altura=False) as (dlg, card):
                    ui.label(f"Remover “{nome}” da lista telefônica?").classes("text-body1")
                    ui.label("A remoção não pode ser desfeita.").classes("text-caption text-grey-6")

                    def _confirmar():
                        try:
                            if not _guarda_admin("remover contatos"):
                                return
                            ok, msg = lista.excluir_contato(cid, ator=user_nome)
                            notificar(msg, tipo="positive" if ok else "negative")
                            if ok:
                                dlg.close()
                                render_organograma.refresh()
                        except Exception:
                            _falhar("confirmar remocao de contato", str(cid))

                    with ui.row().classes("w-full justify-end mt-2").style("gap: 0.5rem"):
                        ui.button("Cancelar", on_click=dlg.close).props("flat")
                        _testid(botao("Remover", icone="delete", on_click=_confirmar,
                                      variante="perigo", chave_modulo=CHAVE),
                                'data-testid=lista-remover-contato-confirmar')
                dlg.open()
            except Exception:
                _falhar("dlg_remover_contato", str(cid))

        def _dlg_nova_unidade():
            """EN: New unit — name, type, parent, phone. PT-BR: Nova unidade — nome, tipo, pai, telefone."""
            if not _guarda_admin("criar unidades"):
                return
            try:
                arvore = _carregar_arvore()
                sel_pai = {"elemento": None}
                with dialogo_card(titulo="Nova unidade", largura="w-[420px]",
                                  chave_modulo=CHAVE) as (dlg, card):
                    inp_nome = ui.input("Nome *").props("outlined dense").classes("w-full") \
                        .props('data-testid=lista-nova-unidade-nome')
                    sel_tipo = ui.select({"secretaria": "Secretaria", "setor": "Setor",
                                          "subsetor": "Subsetor"}, value="secretaria",
                                         label="Tipo").props("outlined dense").classes("w-full") \
                        .props('data-testid=lista-nova-unidade-tipo')
                    pai_holder = ui.column().classes("w-full gap-1")
                    campo_tel = _campo_telefone("Telefone", "lista-nova-unidade")

                    def _montar_pai():
                        """EN: Parent picker follows the chosen type.

                        PT-BR: O seletor de pai acompanha o tipo escolhido.
                        """
                        try:
                            sel_pai["elemento"] = None
                            pai_holder.clear()
                            with pai_holder:
                                sel_pai["elemento"] = ui.select(
                                    _opcoes_pai(arvore, sel_tipo.value), label="Unidade pai *") \
                                    .props("outlined dense clearable").classes("w-full") \
                                    .props('data-testid=lista-nova-unidade-pai')
                        except Exception:
                            _falha("seletor de pai", str(sel_tipo.value))

                    def _salvar():
                        try:
                            if not _guarda_admin("criar unidades"):
                                return
                            pai = sel_pai["elemento"].value if sel_pai["elemento"] else None
                            ok, msg = lista.criar_unidade(
                                inp_nome.value or "", sel_tipo.value, pai,
                                campo_tel["obter"]() if campo_tel else "", ator=user_nome)
                            notificar(msg, tipo="positive" if ok else "negative")
                            if ok:
                                dlg.close()
                                render_organograma.refresh()
                        except Exception:
                            _falhar("salvar nova unidade", str(sel_tipo.value))

                    with ui.row().classes("w-full justify-end mt-2").style("gap: 0.5rem"):
                        ui.button("Cancelar", on_click=dlg.close).props("flat")
                        _testid(botao("Salvar", icone="save", on_click=_salvar, variante="primario",
                                      chave_modulo=CHAVE),
                                'data-testid=lista-nova-unidade-salvar')

                sel_tipo.on_value_change(lambda e: _montar_pai())
                _montar_pai()
                dlg.open()
            except Exception:
                _falhar("dlg_nova_unidade", "dialogo")

        def _dlg_editar_unidade():
            """EN: Edit the unit of the current slice. PT-BR: Editar a unidade do recorte atual."""
            if not _guarda_admin("editar unidades"):
                return
            if not estado["unidade"]:
                notificar("Escolha uma secretaria, setor ou subsetor para editar.", tipo="warning")
                return
            try:
                uni = lista.obter_unidade(estado["unidade"])
                if not uni:
                    notificar("Unidade não encontrada.", tipo="negative")
                    return
                with dialogo_card(titulo=f"Editar — {uni[1]}", largura="w-[420px]",
                                  chave_modulo=CHAVE) as (dlg, card):
                    inp_nome = ui.input("Nome", value=uni[1]).props("outlined dense") \
                        .classes("w-full").props('data-testid=lista-editar-unidade-nome')
                    campo_tel = _campo_telefone("Telefone", "lista-editar-unidade", uni[5] or "")

                    def _salvar():
                        try:
                            if not _guarda_admin("editar unidades"):
                                return
                            ok, msg = lista.editar_unidade(
                                uni[0], nome=inp_nome.value or "",
                                telefone=campo_tel["obter"]() if campo_tel else None,
                                ator=user_nome)
                            notificar(msg, tipo="positive" if ok else "negative")
                            if ok:
                                dlg.close()
                                render_organograma.refresh()
                        except Exception:
                            _falhar("salvar edicao de unidade", str(uni[0]))

                    with ui.row().classes("w-full justify-end mt-2").style("gap: 0.5rem"):
                        ui.button("Cancelar", on_click=dlg.close).props("flat")
                        _testid(botao("Salvar", icone="save", on_click=_salvar, variante="primario",
                                      chave_modulo=CHAVE),
                                'data-testid=lista-editar-unidade-salvar')
                dlg.open()
            except Exception:
                _falhar("dlg_editar_unidade", "dialogo")

        @ui.refreshable
        def render_organograma():
            """EN: Nav buttons + slice + contact grid. PT-BR: Botões + recorte + grade."""
            try:
                arvore = _carregar_arvore()
                # O termo é UNICO: `filtrar_arvore` procura nome, telefone e
                # unidade com o mesmo texto, sem acento.
                filtrada = impressao.filtrar_arvore(arvore, termo=estado["busca"])
                # O recorte vem da CASCATA: o nível mais fundo escolhido
                # manda, e a árvore já traz os descendentes dele.
                recorte = filtrada
                for chave in ("nivel_3", "nivel_2", "nivel_1"):
                    if estado.get(chave) is not None:
                        recorte = _recortar(recorte, estado[chave])
                        break
                with ui.card().classes("w-full p-4 gap-3 lista-impressao"):
                    _cabecalho_recorte(recorte)
                    if not recorte:
                        if _tem_filtro():
                            ui.label("Nenhum contato neste recorte com os filtros atuais.") \
                                .classes("text-grey-6 italic")
                            ui.label("Ajuste a busca ou escolha outro nível do organograma.") \
                                .classes("text-caption text-grey-6")
                        else:
                            ui.label("Nenhum contato encontrado.").classes("text-grey-6 italic")
                        return
                    _desenhar_blocos(recorte, nivel=0, prefixo="")
            except Exception:
                _falhar("render_organograma", "desenho da navegacao")

        # =================== construção da tela ===================
        with ui.column().classes("w-full p-6 gap-4"):
            with ui.element("div").classes("w-full lista-cabecalho"):
                cabecalho("Lista Telefônica", t_texto_header, chave_modulo=CHAVE,
                          cor_titulo=t_cor_titulo, cor_fundo=t_cor_fundo)

            # UM campo de busca + TRÊS selects de unidade em cascata, no mesmo
            # card. A busca é uma só e pesquisa nome, telefone e unidade de uma
            # vez; o recorte por unidade é pelos selects, que se alimentam
            # (escolheu a secretaria, o select seguinte traz os setores dela).
            # Fica FORA do refreshable de propósito: os campos precisam manter
            # foco e valor enquanto a lista é redesenhada a cada tecla.
            with ui.card().classes("w-full p-3 shadow-sm no-print") \
                    .props('data-testid=lista-busca role="search" '
                           'aria-label="Busca e filtro da lista telefônica"'):
                with ui.row().classes("w-full items-center flex-wrap").style(
                        "gap: 0.75rem; min-width: 0"):
                    with ui.element("div").classes(
                            "w-full sm:w-[320px] shrink-0 no-print").style("min-width: 0"):
                        campo = campo_busca(
                            "🔍 Buscar — nome, telefone ou unidade",
                            lambda e: _ao_filtrar("busca", e),
                            tooltip="Um único campo: pesquisa nome, telefone e "
                                    "unidade ao mesmo tempo (sem acentos)")
                        campo.props('data-testid=lista-busca-termo '
                                    'aria-label="Buscar por nome, telefone ou unidade"')
                        campos_busca.append(campo)
                    # Três selects: unidade, subunidade e sub-subunidade.
                    for i, (rotulo, dica) in enumerate((
                            ("Unidade", "Todas as unidades do organograma"),
                            ("Subunidade", "Abre depois de escolher a unidade"),
                            ("Sub-subunidade", "Abre depois de escolher a subunidade"))):
                        with ui.element("div").classes(
                                "w-full sm:w-[210px] shrink-0 no-print").style("min-width: 0"):
                            sel = ui.select({}, label=rotulo, with_input=True) \
                                .props("outlined dense clearable") \
                                .classes("w-full") \
                                .props(f'data-testid="lista-cascata-{i + 1}" '
                                       f'aria-label="{rotulo}"')
                            sel.disable()
                            sel.on("update:model-value",
                                   lambda e, n=i + 1: _ao_mudar_nivel(n, e))
                            campos_cascata.append(sel)
                    _testid(botao("Limpar", icone="clear", on_click=_limpar_busca,
                                  variante="texto", chave_modulo=CHAVE,
                                  extra_classes="shrink-0 no-print"),
                            'data-testid=lista-limpar-busca aria-label="Limpar a busca"')
                # Popula a cascata ANTES do primeiro desenho: sem isto o
                # primeiro select nascia vazio e desligado, e só ganhava as
                # unidades depois que o usuário mexesse em algum campo.
                _preencher_cascata(None)

                # Diretário velho: reespelha o cadastro sozinho. Quem acabou
                # de cadastrar o telefone no primeiro acesso precisa
                # encontrar-se na lista sem depender de alguém lembrar de
                # apertar o botão. Fora do event-loop, e o desenho inicial
                # acontece de qualquer forma — se a sincronização demorar,
                # quem está vendo é a tela vazia por instantes, não a página
                # pendurada.
                try:
                    if lista.sincronizacao_desatualizada():
                        ui.timer(0.4, _auto_sincronizar)
                except Exception:
                    log.warning("não foi possível checar a desatualização "
                                "do diretório")
            render_organograma()
    except Exception:
        _falhar("mostrar_tela", "renderizacao da lista telefonica")
        return None
