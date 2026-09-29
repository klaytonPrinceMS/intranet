"""EN: Stock — the business screen (route /estoque).
The central warehouse (entry, transfer out, delivery to a room), the
per-secretariat panel (received, available, in use, standing still), what is
in use with its destination and days, the collection requests the central
answers, the deposit tasks that call other registered servers in, and the
movement history with its numbered documents.

PT-BR: Estoque — tela de negócio (rota /estoque).
O estoque central (entrada, transferência de saída, entrega para a sala), o
painel por secretaria (recebido, disponível, em uso, parado), o que está em
uso com destino e dias, os pedidos de recolhimento que o central atende, as
tarefas de depósito que chamam outros servidores cadastrados, e o histórico
de movimentação com os documentos numerados.
"""

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from nicegui import ui, run

from mod_intranet import autenticacao
from mod_intranet import integracoes
from mod_intranet import observabilidade
from mod_intranet.aba_modulo import cabecalho
from mod_intranet.tema_modulo import ler_tema, notificar
from mod_intranet.ui_comum import CORES, botao, botao_icone, dialogo_card, \
    dialogo_formulario
from mod_estoque import bd_manipulador as est_bd

log = observabilidade.get_logger("estoque")

CHAVE = "estoque"
TEXTO_CABECALHO = ("Estoque central e almoxarifados das secretarias — entrada, "
                   "distribuição, o que está em uso e o que volta.")

ORIGENS_ROTULO = {
    "nota_empenho": "Nota de empenho",
    "empenho": "Empenho",
    "compra": "Compra direta",
    "doacao": "Doação",
    "outro": "Outro",
}
TIPOS_TAREFA_ROTULO = {
    "receber": "Receber material",
    "conferir": "Conferir entrada",
    "inventariar": "Inventariar",
}
PAPEIS_ROTULO = {
    est_bd.PAPEL_CONSULTA: "Consulta (só vê)",
    est_bd.PAPEL_OPERADOR: "Operador (movimenta estoque)",
    est_bd.PAPEL_ADMINISTRADOR: "Administrador (cria almoxarifado e item)",
}
SITUACAO_RECOLHIMENTO_ROTULO = {
    "aberto": "Aberto", "atendido": "Atendido", "recusado": "Recusado",
}
SITUACAO_TAREFA_ROTULO = {
    "aberta": "Aberta", "em_andamento": "Em andamento",
    "concluida": "Concluída", "cancelada": "Cancelada",
}
UNIDADES_ROTULO = {u: u for u in est_bd.UNIDADES_MEDIDA}


# ============ ajudas de tela ============

def _pode_acessar(user_nome, perfil_global):
    """Acesso ao módulo: administrador geral ou vínculo liberado no cadastro."""
    if perfil_global == "administrador_geral":
        return True
    try:
        return autenticacao.validar_acesso_modulo(user_nome, CHAVE)
    except Exception:
        log.exception(f"_pode_acessar({user_nome}) falhou")
        return False


def _data_bruta(valor):
    """`ui.date` devolve `date`/`datetime`; o banco guarda `YYYY-MM-DD`."""
    if not valor:
        return ""
    try:
        return valor.strftime("%Y-%m-%d")
    except (AttributeError, ValueError, TypeError):
        return str(valor)[:10]


def _data_curta(data):
    """Data em dd/mm/aaaa — é assim que o servidor lê."""
    if not data:
        return "—"
    try:
        return datetime.strptime(str(data)[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return str(data)[:10]


def _hoje():
    """Data de hoje para os campos de data dos formulários."""
    return datetime.now().strftime("%Y-%m-%d")


def _qtd(valor):
    """O que o servidor digitou no campo quantidade, como texto para o banco."""
    return "" if valor is None else str(valor)


def _opcoes_almoxarifados(incluir_central=True, apenas_ativos=True):
    """`{nome: id}` dos almoxarifados para os seletores."""
    opcoes = {}
    try:
        for almoxarifado in est_bd.listar_almoxarifados():
            if not incluir_central and almoxarifado.get("central"):
                continue
            if apenas_ativos and not almoxarifado.get("ativo"):
                continue
            marca = " (central)" if almoxarifado.get("central") else ""
            if not almoxarifado.get("ativo"):
                marca += " — inativo"
            elif almoxarifado.get("bloqueado"):
                marca += " — bloqueado"
            opcoes[f"{almoxarifado['nome']}{marca}"] = almoxarifado["id"]
    except Exception:
        log.exception("_opcoes_almoxarifados falhou")
    return opcoes


def _opcoes_itens(almoxarifado_id, apenas_com_saldo=True):
    """`{número — descrição (qtd disponível): id}` dos itens."""
    opcoes = {}
    try:
        itens = est_bd.listar_itens(
            apenas_com_saldo=apenas_com_saldo, termo="")
        for item in itens:
            disponivel = est_bd.saldo_item(item["id"], almoxarifado_id) \
                if almoxarifado_id else item.get("disponivel_total", 0)
            if apenas_com_saldo and not disponivel:
                continue
            opcoes[f"{item['numero']} — {item['descricao']} "
                   f"({disponivel:g} {item['unidade_medida']})"] = item["id"]
    except Exception:
        log.exception("_opcoes_itens falhou")
    return opcoes


def _copiar_texto(texto, rotulo):
    """Copia o número do documento ou do item — é o que o servidor dita."""
    try:
        ui.clipboard.write(texto)
        notificar(f"{rotulo} copiado: {texto}", type="positive")
    except Exception:
        log.exception(f"_copiar_texto({texto}) falhou")
        notificar(f"Não foi possível copiar. {rotulo}: {texto}", type="warning")


async def _gravar(botao_ui, status_ui, funcao, fechar=None, ao_sucesso=None):
    """Botão de gravação: trava reentrância, roda fora do event-loop, avisa.

    `funcao` é a escrita, chamada em `run.io_bound` para não travar o
    event-loop do servidor (AGENTS §5.1). Devolve `(ok, mensagem)`. O estado do
    botão e do aviso volta SEMPRE no `finally` — erro não pode deixar a tela
    travada."""
    try:
        if botao_ui is not None:
            botao_ui.disable()
        if status_ui is not None:
            status_ui.set_text("Registrando…")
        try:
            retorno = await run.io_bound(funcao)
        except Exception:
            log.exception("_gravar: a escrita levantou exceção")
            notificar("Erro inesperado ao registrar.", type="negative")
            return
        if isinstance(retorno, tuple) and len(retorno) >= 2:
            ok, mensagem = retorno[0], retorno[1]
        else:
            ok, mensagem = bool(retorno), "Registrado." if retorno else "Falha ao registrar."
        if ok:
            if ao_sucesso is not None:
                try:
                    ao_sucesso()
                except Exception:
                    log.exception("_gravar: callback de sucesso falhou")
            if fechar is not None:
                fechar()
        notificar(mensagem or ("Registrado." if ok else "Falha ao registrar."),
                  type="positive" if ok else "negative")
    except Exception:
        log.exception("_gravar falhou")
        notificar("Erro inesperado ao registrar.", type="negative")
    finally:
        try:
            if status_ui is not None:
                status_ui.set_text("")
            if botao_ui is not None:
                botao_ui.enable()
        except Exception:
            log.exception("_gravar: falha ao restaurar o botão")


class _SessaoEstoque:
    """Quem está na tela e o que está selecionado.

    Objeto de sessão por servidor (um por chamada de `mostrar_tela`): guarda o
    login, se é administrador geral e o almoxarifado em foco. Existe para não
    passar quatro parâmetros por toda função e para que o almoxarifado em foco
    NUNCA vire variável global — dois servidores na mesma página não podem
    trocar o almoxarifado um do outro."""

    def __init__(self, user_nome, perfil_global):
        self.user_nome = user_nome or ""
        self.perfil_global = perfil_global or ""
        self.admin_geral = perfil_global == "administrador_geral"
        self.almoxarifado_foco = None
        self.recarregar = None

    def papel(self):
        """Papel da pessoa no módulo de estoque."""
        try:
            return est_bd.papel_no_estoque(self.user_nome, self.admin_geral)
        except Exception:
            log.exception("sessao.papel falhou")
            return None

    def movimenta(self):
        """Verdadeiro quando a pessoa pode movimentar estoque."""
        try:
            return est_bd.pode_movimentar(self.user_nome, self.admin_geral)
        except Exception:
            log.exception("sessao.movimenta falhou")
            return False

    def administra(self):
        """Verdadeiro quando a pessoa administra o módulo."""
        try:
            return est_bd.pode_administrar(self.user_nome, self.admin_geral)
        except Exception:
            log.exception("sessao.administra falhou")
            return False

    def focar(self, almoxarifado_id):
        """Troca o almoxarifado em foco e redesenha a aba."""
        self.almoxarifado_foco = almoxarifado_id
        if self.recarregar:
            self.recarregar()


def mostrar_tela(user_nome: str, perfil_global: str = ""):
    """EN: Renders /estoque — the Stock screen for the logged user.

    PT-BR: Renderiza /estoque — a tela de estoque do servidor logado.

    Monta cabeçalho e abas de trabalho: estoque central, almoxarifados das
    secretarias, o que está em uso, os pedidos de recolhimento, as tarefas de
    depósito e o histórico de movimentação."""
    if not _pode_acessar(user_nome, perfil_global):
        with ui.column().classes("w-full items-center p-12 gap-3"):
            ui.icon("block", size="64px").classes("text-red-8")
            ui.label("Acesso restrito").classes("text-h6")
            ui.label("Somente usuários com acesso ao módulo Estoque.").classes(
                "text-body2 text-grey-7")
        return

    sessao = _SessaoEstoque(user_nome, perfil_global)
    tema = ler_tema(CHAVE, cor_botao="#000000", cor_texto_botao="#FFFFFF",
                    texto_header=TEXTO_CABECALHO)
    ui.colors(primary=tema["cor_botao"])

    with ui.column().classes("w-full p-6 gap-4"):
        cabecalho("Estoque", tema["texto_header"], chave_modulo=CHAVE,
                  cor_titulo=tema["cor_titulo"], cor_fundo=tema["cor_fundo"])

        papel = sessao.papel()
        with ui.row().classes("w-full items-center flex-wrap").style("gap: 0.5rem"):
            ui.label(f"Você está como: "
                     f"{PAPEIS_ROTULO.get(papel, papel or '—')}").classes(
                "text-caption text-grey-6")
            ui.label(f"Item parado conta a partir de "
                     f"{est_bd.dias_parado()} dias sem baixa.").classes(
                "text-caption text-grey-6")

        pendentes = []
        try:
            pendentes = est_bd.listar_convites_pendentes(user_nome)
        except Exception:
            log.exception("mostrar_tela: convites pendentes falharam")
        if pendentes:
            with ui.row().classes("w-full items-center flex-wrap").style(
                    "gap: 0.5rem"):
                ui.badge(f"{len(pendentes)} convite(s) de depósito", color="orange-8") \
                    .props("rounded")
                botao("Ver convites", icone="person_add", variante="secundario",
                      chave_modulo=CHAVE,
                      on_click=lambda: _dialogo_convites_pendentes(sessao)) \
                    .props("data-testid=estoque-ver-convites")

        with ui.tabs().classes("w-full") as _abas:
            aba_central = ui.tab("Estoque central")
            aba_almox = ui.tab("Almoxarifados")
            aba_uso = ui.tab("Em uso")
            aba_recolher = ui.tab("Recolhimentos")
            aba_deposito = ui.tab("Depósito")
            aba_movimentos = ui.tab("Movimentos")

        # O container dos painéis é `ui.tab_panels(abas)`, não `ui.stack`.
        # `ui.stack` NÃO EXISTE no NiceGUI: as abas apareciam e a tela
        # estourava AttributeError na primeira linha de painel, então o módulo
        # entrava no menu e não desenhava nada. Mesmo defeito do `mod_os`.
        with ui.tab_panels(_abas, value=aba_central).classes(
                "w-full bg-transparent"):
            with ui.tab_panel(aba_central):

                @ui.refreshable
                def painel_central():
                    """Aba 'Estoque central': o que entrou e o que dá para mandar."""
                    _desenhar_central(sessao)

                sessao.recarregar = painel_central.refresh
                painel_central()

            with ui.tab_panel(aba_almox):
                _desenhar_almoxarifados(sessao)
            with ui.tab_panel(aba_uso):
                _desenhar_em_uso(sessao)
            with ui.tab_panel(aba_recolher):
                _desenhar_recolhimentos(sessao)
            with ui.tab_panel(aba_deposito):
                _desenhar_deposito(sessao)
            with ui.tab_panel(aba_movimentos):
                _desenhar_movimentos(sessao)


# ============ aba 1: estoque central ============

def _desenhar_central(sessao):
    """O estoque central: o que está disponível e o que dá para distribuir."""
    try:
        central = est_bd.garantir_estoque_central()
        if not central:
            ui.label("Estoque central indisponível.").classes(
                "text-body2 text-negative")
            return
        itens = est_bd.listar_itens(almoxarifado_id=central["id"])
        disponiveis = [i for i in itens if i["disponivel_no_almoxarifado"] > 0]
        total = sum(i["disponivel_no_almoxarifado"] for i in disponiveis)
    except Exception:
        log.exception("_desenhar_central falhou ao listar")
        notificar("Erro ao carregar o estoque central.", type="negative")
        return

    with ui.row().classes("w-full items-center justify-between flex-wrap") \
            .style("gap: 0.5rem"):
        with ui.row().classes("items-center flex-wrap").style("gap: 0.5rem"):
            ui.label(f"{len(disponiveis)} item(ns) com saldo").classes(
                "text-body2 text-grey-7")
            ui.label(f"disponível: {total:g}").classes("text-body2 font-bold")
        if sessao.movimenta():
            with ui.row().classes("items-center flex-wrap").style("gap: 0.5rem"):
                botao("Nova entrada", icone="add", chave_modulo=CHAVE,
                      on_click=lambda: _dialogo_entrada(sessao, central["id"])) \
                    .props("data-testid=estoque-nova-entrada")
                botao("Transferir", icone="swap_horiz", variante="secundario",
                      chave_modulo=CHAVE,
                      on_click=lambda: _dialogo_transferencia(sessao, central["id"])) \
                    .props("data-testid=estoque-nova-transferencia")
                botao("Entregar a sala", icone="meeting_room",
                      variante="secundario", chave_modulo=CHAVE,
                      on_click=lambda: _dialogo_entrega(sessao, central["id"])) \
                    .props("data-testid=estoque-nova-entrega")
        if sessao.administra():
            botao("Cadastrar item", icone="inventory_2", variante="secundario",
                  chave_modulo=CHAVE,
                  on_click=lambda: _dialogo_novo_item(sessao, central["id"])) \
                .props("data-testid=estoque-novo-item")

    if not disponiveis:
        with ui.column().classes("w-full items-center p-8 gap-2"):
            ui.icon("inventory", size="48px").classes("text-grey-5")
            ui.label("O estoque central está vazio.").classes("text-body1")
            ui.label("Registre a entrada do material que chegou: é por aqui que "
                     "tudo entra antes de ir para as secretarias.").classes(
                "text-caption text-grey-6")
        return

    with ui.grid().classes("w-full grid-cols-1 sm:grid-cols-2 lg:grid-cols-3") \
            .style("gap: 0.75rem"):
        for item in disponiveis:
            _cartao_item(sessao, central, item)


def _cartao_item(sessao, almoxarifado, item):
    """Cartão de um item com o que está disponível naquele almoxarifado."""
    try:
        cor = almoxarifado.get("cor") or CORES["primaria"]
        with ui.card().classes("w-full").style(
                f"border-left: 6px solid {cor}; min-width: 0") \
                .props(f"data-testid=estoque-item-{item['numero']}"):
            with ui.column().classes("w-full gap-1").style("min-width: 0"):
                with ui.row().classes("w-full items-center justify-between flex-wrap") \
                        .style("gap: 0.5rem"):
                    ui.label(item["numero"]).classes("text-caption font-bold") \
                        .style("cursor: pointer; min-width: 0") \
                        .on("click", lambda _e, n=item["numero"]:
                             _copiar_texto(n, "Número do item"))
                    ui.badge(f"{item['disponivel_no_almoxarifado']:g} "
                             f"{item['unidade_medida']}", color="green-7").props("rounded")
                ui.label(item["descricao"]).classes("text-body2 font-medium") \
                    .style("min-width: 0; word-break: break-word")
                outros = {k: v for k, v in (item.get("saldos") or {}).items()
                          if k != almoxarifado["id"] and v > 0}
                if outros:
                    nomes = est_bd._nomes_almoxarifados(list(outros))
                    resumo = ", ".join(f"{nomes.get(k, k)}: {v:g}"
                                       for k, v in sorted(outros.items()))
                    ui.label(f"Também em: {resumo}").classes(
                        "text-caption text-grey-6").style("word-break: break-word")
                if sessao.movimenta():
                    with ui.row().classes("w-full justify-end").style("gap: 0.25rem"):
                        botao_icone("meeting_room", chave_modulo=CHAVE,
                                    tooltip="Entregar este item a uma sala",
                                    on_click=lambda i=item:
                                        _dialogo_entrega(sessao, almoxarifado["id"],
                                                         item_id=i["id"])) \
                            .props(f"data-testid=estoque-entregar-{item['numero']}")
                        botao_icone("swap_horiz", chave_modulo=CHAVE,
                                    tooltip="Transferir este item para outro almoxarifado",
                                    on_click=lambda i=item:
                                        _dialogo_transferencia(
                                            sessao, almoxarifado["id"], i["id"])) \
                            .props(f"data-testid=estoque-transferir-{item['numero']}")
    except Exception:
        log.exception(f"_cartao_item({item.get('numero')}) falhou")
        notificar("Erro ao desenhar um item.", type="negative")


# ============ aba 2: almoxarifados das secretarias ============

def _desenhar_almoxarifados(sessao):
    """Painel por secretaria: recebido, disponível, em uso e PARADO."""
    try:
        almoxarifados = est_bd.listar_almoxarifados()
        if sessao.administra():
            with ui.row().classes("w-full justify-end").style("gap: 0.5rem"):
                botao("Novo almoxarifado", icone="add_business", chave_modulo=CHAVE,
                      on_click=lambda: _dialogo_novo_almoxarifado(sessao)) \
                    .props("data-testid=estoque-novo-almoxarifado")
        if not almoxarifados:
            ui.label("Nenhum almoxarifado cadastrado.").classes(
                "text-body2 text-grey-7")
            return
        with ui.grid().classes("w-full grid-cols-1 lg:grid-cols-2") \
                .style("gap: 0.75rem"):
            for almoxarifado in almoxarifados:
                _cartao_painel_almoxarifado(sessao, almoxarifado)
    except Exception:
        log.exception("_desenhar_almoxarifados falhou")
        notificar("Erro ao carregar os almoxarifados.", type="negative")


def _cartao_painel_almoxarifado(sessao, almoxarifado):
    """Os quatro números do almoxarifado + as ações que o gestor usa."""
    try:
        painel = est_bd.painel_almoxarifado(almoxarifado["id"])
        if not painel:
            return
        cor = almoxarifado.get("cor") or CORES["primaria"]
        with ui.card().classes("w-full").style(
                f"border-left: 6px solid {cor}; min-width: 0") \
                .props(f"data-testid=estoque-almoxarifado-{almoxarifado['id']}"):
            with ui.column().classes("w-full gap-2").style("min-width: 0"):
                with ui.row().classes("w-full items-center justify-between flex-wrap") \
                        .style("gap: 0.5rem"):
                    with ui.column().classes("gap-0").style("min-width: 0"):
                        ui.label(almoxarifado["nome"]).classes(
                            "text-subtitle1 font-bold").style(
                            "min-width: 0; word-break: break-word")
                        if almoxarifado.get("unidade_nome"):
                            ui.label(almoxarifado["unidade_nome"]).classes(
                                "text-caption text-grey-6").style("word-break: break-word")
                    if almoxarifado.get("central"):
                        ui.badge("Estoque central", color="blue-7").props("rounded")
                    elif not almoxarifado.get("ativo"):
                        ui.badge("Inativo", color="grey-6").props("rounded")
                    elif almoxarifado.get("bloqueado"):
                        ui.badge("Bloqueado", color="orange-8").props("rounded")
                if almoxarifado.get("responsavel_nome"):
                    ui.label(f"Responsável: {almoxarifado['responsavel_nome']}") \
                        .classes("text-caption text-grey-6").style("word-break: break-word")
                with ui.row().classes("w-full items-start flex-wrap").style("gap: 1rem"):
                    _numero("recebido", painel["recebido"])
                    _numero("disponível", painel["disponivel"])
                    _numero("em uso", painel["em_uso"])
                    _numero(f"parado ({painel['dias_limite']}d)",
                            painel["parado"],
                            alerta=painel["parado"] > 0)
                if painel["parado"] > 0:
                    ui.label(f"{painel['parado']:g} unidade(s) estão fora do "
                             f"almoxarifado há mais de {painel['dias_limite']} "
                             f"dias sem baixa. Abra um pedido de recolhimento "
                             f"para o material voltar a ficar disponível.") \
                        .classes("text-caption text-orange-8") \
                        .style("word-break: break-word")
                with ui.row().classes("w-full items-center flex-wrap") \
                        .style("gap: 0.25rem"):
                    if sessao.movimenta():
                        botao("Transferir para cá", icone="move_to_inbox",
                              variante="secundario", chave_modulo=CHAVE,
                              on_click=lambda a=almoxarifado: _dialogo_transferencia(
                                  sessao, destino_id=a["id"])) \
                            .props(f"data-testid=estoque-receber-em-"
                                   f"{almoxarifado['id']}")
                        botao("Pedido de recolhimento", icone="assignment_return",
                              variante="secundario", chave_modulo=CHAVE,
                              on_click=lambda a=almoxarifado:
                                  _dialogo_recolhimento(sessao, a["id"])) \
                            .props(f"data-testid=estoque-recolher-"
                                   f"{almoxarifado['id']}")
                    botao_icone("list", chave_modulo=CHAVE,
                                tooltip="Ver o que está em uso neste almoxarifado",
                                on_click=lambda a=almoxarifado:
                                    _dialogo_em_uso(sessao, a)) \
                        .props(f"data-testid=estoque-ver-em-uso-"
                               f"{almoxarifado['id']}")
                    if sessao.administra() and not almoxarifado.get("central"):
                        botao_icone("settings", chave_modulo=CHAVE,
                                    tooltip="Ajustar o almoxarifado",
                                    on_click=lambda a=almoxarifado:
                                        _dialogo_ajustes_almoxarifado(sessao, a)) \
                            .props(f"data-testid=estoque-ajustes-"
                                   f"{almoxarifado['id']}")
    except Exception:
        log.exception(f"_cartao_painel_almoxarifado({almoxarifado.get('id')}) falhou")
        notificar("Erro ao desenhar o painel do almoxarifado.", type="negative")


def _numero(rotulo, valor, alerta=False):
    """Um número do painel. `alerta=True` pinta de laranja (é desperdício)."""
    try:
        cor = "text-orange-8" if alerta else "text-h6"
        with ui.column().classes("gap-0").style("min-width: 0"):
            ui.label(f"{valor:g}").classes(cor).style("min-width: 0")
            ui.label(rotulo).classes("text-caption text-grey-6")
    except Exception:
        log.exception(f"_numero({rotulo}) falhou")


# ============ aba 3: o que está em uso ============

def _desenhar_em_uso(sessao):
    """Entregas em uso: destino, data, quantos dias parada."""
    try:
        entregas = est_bd.listar_entregas()
        parados = [e for e in entregas if e["parado"]]
    except Exception:
        log.exception("_desenhar_em_uso falhou")
        notificar("Erro ao carregar as entregas.", type="negative")
        return

    with ui.row().classes("w-full items-center justify-between flex-wrap") \
            .style("gap: 0.5rem"):
        with ui.row().classes("items-center flex-wrap").style("gap: 0.5rem"):
            ui.label(f"{len(entregas)} entrega(s) em uso").classes(
                "text-body2 text-grey-7")
            if parados:
                ui.badge(f"{len(parados)} parada(s)", color="orange-8").props("rounded")
        if sessao.movimenta():
            botao("Entregar a sala", icone="meeting_room", variante="secundario",
                  chave_modulo=CHAVE, on_click=lambda: _dialogo_entrega(sessao)) \
                .props("data-testid=estoque-em-uso-nova-entrega")

    if not entregas:
        with ui.column().classes("w-full items-center p-8 gap-2"):
            ui.icon("meeting_room", size="48px").classes("text-grey-5")
            ui.label("Nenhum material entregue em sala.").classes("text-body1")
            ui.label("O que está em uso precisa de sala e data — sem os dois, "
                     "'em uso' não é número.").classes("text-caption text-grey-6")
        return

    with ui.column().classes("w-full gap-2").style("min-width: 0"):
        for entrega in entregas:
            _linha_entrega(sessao, entrega)


def _linha_entrega(sessao, entrega):
    """Uma entrega: destino, responsável, data e o que dá para fazer com ela."""
    try:
        with ui.card().classes("w-full").style("min-width: 0") \
                .props(f"data-testid=estoque-entrega-{entrega['id']}"):
            with ui.column().classes("w-full gap-1").style("min-width: 0"):
                with ui.row().classes("w-full items-center justify-between flex-wrap") \
                        .style("gap: 0.5rem"):
                    ui.label(f"{entrega['item_numero']} — {entrega['descricao']}") \
                        .classes("text-body2 font-medium").style(
                        "min-width: 0; word-break: break-word")
                    if entrega["parado"]:
                        ui.badge(f"parado há {entrega['dias_parado']} dias",
                                 color="orange-8").props("rounded")
                    else:
                        ui.badge(f"{entrega['dias_parado']} dias", color="grey-6") \
                            .props("rounded")
                with ui.row().classes("w-full items-center flex-wrap") \
                        .style("gap: 0.75rem; min-width: 0"):
                    ui.label(f"{entrega['quantidade']:g} {entrega['unidade_medida']}") \
                        .classes("text-caption font-bold")
                    ui.label(f"Destino: {entrega['destino_sala']}").classes(
                        "text-caption text-grey-6").style("word-break: break-word")
                    if entrega.get("destino_departamento"):
                        ui.label(f"Departamento: {entrega['destino_departamento']}") \
                            .classes("text-caption text-grey-6") \
                            .style("word-break: break-word")
                    if entrega.get("responsavel_nome"):
                        ui.label(f"Responsável: {entrega['responsavel_nome']}") \
                            .classes("text-caption text-grey-6") \
                            .style("word-break: break-word")
                    ui.label(f"Almoxarifado: "
                             f"{entrega.get('almoxarifado_nome', '—')}") \
                        .classes("text-caption text-grey-6")
                    ui.label(f"Entregue em {_data_curta(entrega['data_entrega'])}") \
                        .classes("text-caption text-grey-6")
                if sessao.movimenta():
                    with ui.row().classes("w-full items-center flex-wrap") \
                            .style("gap: 0.25rem"):
                        botao("Dar baixa", icone="task_alt", variante="secundario",
                              chave_modulo=CHAVE,
                              on_click=lambda e=entrega: _dialogo_baixa(sessao, e)) \
                            .props(f"data-testid=estoque-baixa-{entrega['id']}")
                        botao("Pedir recolhimento", icone="assignment_return",
                              variante="secundario", chave_modulo=CHAVE,
                              on_click=lambda e=entrega:
                                  _dialogo_recolhimento(
                                      sessao, e["almoxarifado_id"],
                                      item_id=e["item_id"],
                                      sala=e["destino_sala"])) \
                            .props(f"data-testid=estoque-pedir-recolher-"
                                   f"{entrega['id']}")
    except Exception:
        log.exception(f"_linha_entrega({entrega.get('id')}) falhou")
        notificar("Erro ao desenhar uma entrega.", type="negative")


def _dialogo_em_uso(sessao, almoxarifado):
    """Diálogo com o que está em uso em UM almoxarifado."""
    try:
        entregas = est_bd.listar_entregas(almoxarifado_id=almoxarifado["id"])
        with dialogo_formulario(f"O que está em uso em {almoxarifado['nome']}",
                                chave_modulo=CHAVE) as (dlg, _card, miolo, _grade):
            with miolo:
                if not entregas:
                    ui.label("Nada entregue em sala por este almoxarifado.").classes(
                        "text-body2 text-grey-7")
                else:
                    with ui.column().classes("w-full gap-2").style("min-width: 0"):
                        for entrega in entregas:
                            with ui.row().classes("w-full items-center flex-wrap") \
                                    .style("gap: 0.5rem; min-width: 0"):
                                ui.label(
                                    f"{entrega['item_numero']} — {entrega['descricao']} "
                                    f"· {entrega['quantidade']:g} "
                                    f"{entrega['unidade_medida']} · "
                                    f"{entrega['destino_sala']} · "
                                    f"{entrega['dias_parado']} dia(s)") \
                                    .classes("text-caption").style(
                                    "min-width: 0; word-break: break-word")
                                if entrega["parado"]:
                                    ui.badge("parado", color="orange-8").props("rounded")
        dlg.open()
    except Exception:
        log.exception("_dialogo_em_uso falhou")
        notificar("Erro ao abrir a lista de entregas.", type="negative")


# ============ aba 4: pedidos de recolhimento ============

def _desenhar_recolhimentos(sessao):
    """Pedidos de recolhimento: o que o almoxarifado precisa que o central recolha."""
    try:
        abertos = est_bd.listar_pedidos_recolhimento(situacao="aberto")
        atendidos = est_bd.listar_pedidos_recolhimento(situacao="atendido")
        meus = est_bd.listar_pedidos_recolhimento(
            situacao="", solicitante=sessao.user_nome)
    except Exception:
        log.exception("_desenhar_recolhimentos falhou")
        notificar("Erro ao carregar os pedidos de recolhimento.", type="negative")
        return

    with ui.row().classes("w-full items-center justify-between flex-wrap") \
            .style("gap: 0.5rem"):
        with ui.row().classes("items-center flex-wrap").style("gap: 0.5rem"):
            ui.label(f"{len(abertos)} pedido(s) aberto(s)").classes(
                "text-body2 text-grey-7")
            if abertos:
                ui.badge("o central atende", color="blue-7").props("rounded")
        if sessao.movimenta():
            botao("Abrir pedido", icone="assignment_return", chave_modulo=CHAVE,
                  on_click=lambda: _dialogo_recolhimento(sessao)) \
                .props("data-testid=estoque-abrir-recolhimento")

    if not abertos:
        with ui.column().classes("w-full items-center p-8 gap-2"):
            ui.icon("assignment_return", size="48px").classes("text-grey-5")
            ui.label("Nenhum pedido de recolhimento aberto.").classes("text-body1")
            ui.label("Quando o almoxarifado pedir o seu material de volta — ou "
                     "quando quem está com ele quiser devolver por não uso — o "
                     "pedido aparece aqui para o central atender.").classes(
                "text-caption text-grey-6")
    else:
        with ui.column().classes("w-full gap-2").style("min-width: 0"):
            for pedido in abertos:
                _linha_recolhimento(sessao, pedido)

    if meus:
        ui.separator()
        ui.label("Meus pedidos (todos os estados)").classes(
            "text-subtitle2 font-bold")
        with ui.column().classes("w-full gap-1").style("min-width: 0"):
            for pedido in meus[:20]:
                ui.label(
                    f"{pedido['item_numero']} — {pedido['item_descricao']} · "
                    f"{pedido['quantidade']:g} {pedido['unidade_medida']} · "
                    f"{pedido['destino_sala']} · "
                    f"{SITUACAO_RECOLHIMENTO_ROTULO.get(pedido['situacao'], pedido['situacao'])}"
                ).classes("text-caption text-grey-6").style("word-break: break-word")
    if atendidos:
        ui.label(f"{len(atendidos)} pedido(s) já atendido(s) — o material "
                 f"voltou a ficar disponível.").classes("text-caption text-grey-6")


def _linha_recolhimento(sessao, pedido):
    """Um pedido de recolhimento aberto, com o botão de atender do central."""
    try:
        pode_atender = est_bd.pode_atender_recolhimento(
            sessao.user_nome, pedido["almoxarifado_id"], sessao.admin_geral)
        with ui.card().classes("w-full").style("min-width: 0") \
                .props(f"data-testid=estoque-recolhimento-{pedido['id']}"):
            with ui.column().classes("w-full gap-1").style("min-width: 0"):
                with ui.row().classes("w-full items-center justify-between flex-wrap") \
                        .style("gap: 0.5rem"):
                    ui.label(f"{pedido['item_numero']} — {pedido['item_descricao']}") \
                        .classes("text-body2 font-medium").style(
                        "min-width: 0; word-break: break-word")
                    ui.badge(pedido["tipo_pedido"], color="teal").props("rounded")
                with ui.row().classes("w-full items-center flex-wrap") \
                        .style("gap: 0.75rem; min-width: 0"):
                    ui.label(f"{pedido['quantidade']:g} "
                             f"{pedido['unidade_medida']}").classes(
                        "text-caption font-bold")
                    ui.label(f"De: {pedido['destino_sala']}").classes(
                        "text-caption text-grey-6")
                    ui.label(f"Almoxarifado: "
                             f"{pedido.get('almoxarifado_nome', '—')}") \
                        .classes("text-caption text-grey-6")
                    if pedido.get("solicitante_nome"):
                        ui.label(f"Pediu: {pedido['solicitante_nome']}").classes(
                            "text-caption text-grey-6").style("word-break: break-word")
                    ui.label(_data_curta(pedido["data_abertura"])).classes(
                        "text-caption text-grey-6")
                if pedido.get("motivo"):
                    ui.label(f"Motivo: {pedido['motivo']}").classes(
                        "text-caption text-grey-7").style("word-break: break-word")
                if not pode_atender:
                    ui.label("O atendimento é do estoque central ou de quem "
                             "administra o módulo.").classes(
                        "text-caption text-grey-6")
                elif sessao.movimenta():
                    with ui.row().classes("w-full items-center flex-wrap") \
                            .style("gap: 0.25rem"):
                        botao("Atender e devolver", icone="assignment_turned_in",
                              chave_modulo=CHAVE,
                              on_click=lambda p=pedido: _atender_recolhimento(
                                  sessao, p)) \
                            .props(f"data-testid=estoque-atender-"
                                   f"{pedido['id']}")
                        botao("Recusar", icone="close", variante="perigo",
                              chave_modulo=CHAVE,
                              on_click=lambda p=pedido: _recusar_recolhimento(
                                  sessao, p)) \
                            .props(f"data-testid=estoque-recusar-"
                                   f"{pedido['id']}")
    except Exception:
        log.exception(f"_linha_recolhimento({pedido.get('id')}) falhou")
        notificar("Erro ao desenhar um pedido de recolhimento.", type="negative")


def _atender_recolhimento(sessao, pedido):
    """Atende o pedido: o central recolhe e a quantidade volta ao DISPONÍVEL.

    Pede confirmação porque a operação MEXE no saldo: recolher é devolver
    material ao almoxarifado da secretaria, e o servidor precisa ver a sala e a
    quantidade antes de confirmar."""
    try:
        with dialogo_card("Atender pedido de recolhimento", "w-[560px]",
                          chave_modulo=CHAVE) as (dlg, _card):
            ui.label(f"{pedido['item_numero']} — {pedido['item_descricao']}") \
                .classes("text-body2 font-medium").style("word-break: break-word")
            with ui.column().classes("w-full gap-1").style("min-width: 0"):
                ui.label(f"{pedido['quantidade']:g} {pedido['unidade_medida']} "
                         f"voltam de {pedido['destino_sala']} para o disponível de "
                         f"{pedido.get('almoxarifado_nome', '—')}") \
                    .classes("text-body2")
                ui.label("O material é recolhido da sala e volta a ficar "
                         "disponível no almoxarifado da secretaria. A entrega é "
                         "encerrada e tudo fica registrado no histórico.") \
                    .classes("text-caption text-grey-6").style("word-break: break-word")
            inp_parecer = ui.textarea("Parecer (opcional)")
            inp_parecer.props("outlined rows=2 dense data-testid="
                              "estoque-parecer-atendimento")
            lbl = ui.label("").classes("text-caption text-grey-6")

            def _salvar():
                return est_bd.atender_pedido_recolhimento(
                    pedido["id"], quantidade=pedido["quantidade"],
                    parecer=inp_parecer.value or "", ator=sessao.user_nome,
                    eh_admin_geral=sessao.admin_geral)

            with ui.row().classes("w-full justify-end").style("gap: 0.5rem"):
                ui.button("Cancelar", on_click=dlg.close).props("flat no-caps")
                btn = botao("Atender e devolver", icone="assignment_turned_in",
                            chave_modulo=CHAVE) \
                    .props("data-testid=estoque-atender-confirmar")
                btn.on("click", lambda: _gravar(btn, lbl, _salvar, fechar=dlg.close,
                                                ao_sucesso=lambda: ui.navigate.reload()))
        dlg.open()
    except Exception:
        log.exception("_atender_recolhimento falhou")
        notificar("Erro ao abrir o atendimento do pedido.", type="negative")


def _recusar_recolhimento(sessao, pedido):
    """Recusa o pedido de recolhimento (o material continua em uso)."""
    try:
        with dialogo_card("Recusar pedido de recolhimento", "w-[520px]",
                          chave_modulo=CHAVE) as (dlg, _card):
            ui.label(f"{pedido['item_numero']} — {pedido['item_descricao']} · "
                     f"{pedido['quantidade']:g} {pedido['unidade_medida']}") \
                .classes("text-body2")
            inp_parecer = ui.textarea("Parecer (o material continua em uso na sala)",
                                     placeholder="Ex.: sala em reforma, material "
                                                 "será usado na semana que vem.")
            inp_parecer.props("outlined rows=2 dense data-testid="
                              "estoque-parecer-recusa")
            lbl = ui.label("").classes("text-caption text-grey-6")

            def _salvar():
                return est_bd.recusar_pedido_recolhimento(
                    pedido["id"], inp_parecer.value or "", ator=sessao.user_nome,
                    eh_admin_geral=sessao.admin_geral)

            btn = botao("Recusar pedido", icone="close", variante="perigo",
                        chave_modulo=CHAVE) \
                .props("data-testid=estoque-confirmar-recusa")
            btn.on("click", lambda: _gravar(btn, lbl, _salvar, fechar=dlg.close,
                                             ao_sucesso=lambda: ui.navigate.reload()))
        dlg.open()
    except Exception:
        log.exception("_recusar_recolhimento falhou")
        notificar("Erro ao abrir a recusa do pedido.", type="negative")


# ============ aba 5: tarefas de depósito ============

def _desenhar_deposito(sessao):
    """Tarefas de depósito: quem chamou, quem aceitou, quem está atendendo."""
    try:
        tarefas = est_bd.listar_tarefas()
    except Exception:
        log.exception("_desenhar_deposito falhou")
        notificar("Erro ao carregar as tarefas de depósito.", type="negative")
        return

    with ui.row().classes("w-full items-center justify-between flex-wrap") \
            .style("gap: 0.5rem"):
        abertas = [t for t in tarefas if t["situacao"] in ("aberta", "em_andamento")]
        ui.label(f"{len(abertas)} depósito(s) em aberto de {len(tarefas)} tarefa(s)") \
            .classes("text-body2 text-grey-7")
        if sessao.movimenta():
            botao("Abrir tarefa de depósito", icone="handyman", chave_modulo=CHAVE,
                  on_click=lambda: _dialogo_tarefa(sessao)) \
                .props("data-testid=estoque-nova-tarefa")

    if not tarefas:
        with ui.column().classes("w-full items-center p-8 gap-2"):
            ui.icon("handyman", size="48px").classes("text-grey-5")
            ui.label("Nenhuma tarefa de depósito.").classes("text-body1")
            ui.label("A tarefa é o jeito de chamar outros servidores "
                     "cadastrados para receber, conferir ou inventariar — "
                     "quem responde pela tarefa é quem chama.").classes(
                "text-caption text-grey-6")
        return

    with ui.column().classes("w-full gap-2").style("min-width: 0"):
        for tarefa in tarefas:
            _cartao_tarefa(sessao, tarefa)


def _cartao_tarefa(sessao, tarefa):
    """Uma tarefa de depósito com os convidados e o que cada um respondeu."""
    try:
        convites = est_bd.listar_convites_tarefa(tarefa["id"])
        pode_convidar = est_bd.pode_convidar_para_tarefa(
            sessao.user_nome, tarefa, sessao.admin_geral)
        with ui.card().classes("w-full").style("min-width: 0") \
                .props(f"data-testid=estoque-tarefa-{tarefa['id']}"):
            with ui.column().classes("w-full gap-1").style("min-width: 0"):
                with ui.row().classes("w-full items-center justify-between flex-wrap") \
                        .style("gap: 0.5rem"):
                    ui.label(f"{tarefa['numero']} — {tarefa['titulo']}").classes(
                        "text-body2 font-medium").style(
                        "min-width: 0; word-break: break-word")
                    ui.badge(SITUACAO_TAREFA_ROTULO.get(tarefa["situacao"],
                                                        tarefa["situacao"]),
                             color="green-7" if tarefa["situacao"] == "concluida"
                             else "blue-7").props("rounded")
                with ui.row().classes("w-full items-center flex-wrap") \
                        .style("gap: 0.75rem; min-width: 0"):
                    ui.label(TIPOS_TAREFA_ROTULO.get(tarefa["tipo"],
                                                      tarefa["tipo"])).classes(
                        "text-caption text-grey-6")
                    if tarefa.get("almoxarifado_nome"):
                        ui.label(f"Almoxarifado: {tarefa['almoxarifado_nome']}") \
                            .classes("text-caption text-grey-6")
                    if tarefa.get("responsavel_nome"):
                        ui.label(f"Responde: {tarefa['responsavel_nome']}") \
                            .classes("text-caption text-grey-6")
                    if tarefa.get("atendente_user_nome"):
                        atendente, _u = est_bd._ficha_do_servidor(
                            tarefa["atendente_user_nome"])
                        ui.label(f"Atendendo: {atendente or tarefa['atendente_user_nome']}") \
                            .classes("text-caption font-bold text-green-8")
                    ui.label(f"Aceitos: {tarefa['aceitos']} de "
                             f"{tarefa['necessarios_convidados']}").classes(
                        "text-caption text-grey-6")
                if tarefa.get("descricao"):
                    ui.label(tarefa["descricao"]).classes("text-caption text-grey-7") \
                        .style("word-break: break-word")
                if convites:
                    with ui.column().classes("w-full gap-0").style("min-width: 0"):
                        for convite in convites:
                            with ui.row().classes("w-full items-center flex-wrap") \
                                    .style("gap: 0.5rem; min-width: 0"):
                                ui.label(f"· {convite['nome_exibicao'] or convite['convidado_user_nome']}") \
                                    .classes("text-caption").style("min-width: 0")
                                cor = {"aceito": "green-7", "pendente": "orange-8",
                                       "recusado": "red-8", "cancelado": "grey-6"} \
                                    .get(convite["situacao"], "grey-6")
                                ui.badge(convite["situacao"], color=cor).props("rounded")
                                if pode_convidar and convite["situacao"] == "pendente":
                                    botao_icone("person_remove", chave_modulo=CHAVE,
                                                tooltip="Cancelar o convite",
                                                on_click=lambda c=convite:
                                                    _cancelar_convite(sessao, c)) \
                                        .props(f"data-testid=estoque-cancelar-convite-"
                                               f"{convite['id']}")
                with ui.row().classes("w-full items-center flex-wrap") \
                        .style("gap: 0.25rem"):
                    if pode_convidar and tarefa["situacao"] in ("aberta", "em_andamento"):
                        botao("Chamar servidor", icone="person_add",
                              variante="secundario", chave_modulo=CHAVE,
                              on_click=lambda t=tarefa: _dialogo_convite(sessao, t)) \
                            .props(f"data-testid=estoque-convidar-{tarefa['id']}")
                    if sessao.papel() and tarefa["situacao"] in ("aberta", "em_andamento"):
                        botao("Assumir atendimento", icone="pan_tool",
                              variante="secundario", chave_modulo=CHAVE,
                              on_click=lambda t=tarefa: _assumir(sessao, t)) \
                            .props(f"data-testid=estoque-assumir-{tarefa['id']}")
                    if sessao.movimenta() and tarefa["situacao"] in ("aberta", "em_andamento"):
                        botao("Concluir depósito", icone="task_alt", chave_modulo=CHAVE,
                              on_click=lambda t=tarefa: _concluir_tarefa(sessao, t)) \
                            .props(f"data-testid=estoque-concluir-tarefa-"
                                   f"{tarefa['id']}")
    except Exception:
        log.exception(f"_cartao_tarefa({tarefa.get('id')}) falhou")
        notificar("Erro ao desenhar uma tarefa de depósito.", type="negative")


def _assumir(sessao, tarefa):
    """Marca que quem está na tela está atendendo o depósito."""
    try:
        ok, msg = est_bd.assumir_tarefa(tarefa["id"], sessao.user_nome,
                                        sessao.admin_geral)
        notificar(msg, type="positive" if ok else "negative")
        if ok:
            ui.navigate.reload()
    except Exception:
        log.exception("_assumir falhou")
        notificar("Erro ao assumir o atendimento.", type="negative")


def _concluir_tarefa(sessao, tarefa):
    """Conclui a tarefa de depósito."""
    try:
        ok, msg = est_bd.concluir_tarefa(tarefa["id"], ator=sessao.user_nome,
                                         eh_admin_geral=sessao.admin_geral)
        notificar(msg, type="positive" if ok else "negative")
        if ok:
            ui.navigate.reload()
    except Exception:
        log.exception("_concluir_tarefa falhou")
        notificar("Erro ao concluir o depósito.", type="negative")


def _cancelar_convite(sessao, convite):
    """Cancela o convite de um servidor para o depósito."""
    try:
        ok, msg = est_bd.cancelar_convite_tarefa(convite["id"], ator=sessao.user_nome,
                                                 eh_admin_geral=sessao.admin_geral)
        notificar(msg, type="positive" if ok else "negative")
        if ok:
            ui.navigate.reload()
    except Exception:
        log.exception("_cancelar_convite falhou")
        notificar("Erro ao cancelar o convite.", type="negative")


def _dialogo_convites_pendentes(sessao):
    """Convites de depósito que aguardam resposta de quem está na tela."""
    try:
        convites = est_bd.listar_convites_pendentes(sessao.user_nome)
        with dialogo_formulario("Convites de depósito", chave_modulo=CHAVE) as (
                dlg, _card, miolo, _grade):
            with miolo:
                if not convites:
                    ui.label("Nenhum convite esperando.").classes(
                        "text-body2 text-grey-7")
                for convite in convites:
                    with ui.column().classes("w-full gap-1").style("min-width: 0"):
                        ui.label(f"{convite['tarefa_numero']} — {convite['tarefa_titulo']}") \
                            .classes("text-body2 font-medium").style(
                            "min-width: 0; word-break: break-word")
                        ui.label(f"{TIPOS_TAREFA_ROTULO.get(convite['tarefa_tipo'], '')}"
                                 f" · convidado por {convite['convidado_por']}").classes(
                            "text-caption text-grey-6")
                        inp = ui.input("Recado (opcional)").classes("w-full")
                        inp.props("outlined dense data-testid="
                                  f"estoque-recado-convite-{convite['id']}")
                        with ui.row().classes("w-full justify-end").style("gap: 0.5rem"):
                            btn_ok = botao("Aceitar", icone="check", chave_modulo=CHAVE) \
                                .props(f"data-testid=estoque-aceitar-convite-"
                                       f"{convite['id']}")
                            btn_ok.on("click", lambda c=convite, campo=inp:
                                      _responder_convite(sessao, c, True, campo, dlg,
                                                         btn_ok))
                            btn_nao = botao("Recusar", variante="perigo",
                                            chave_modulo=CHAVE) \
                                .props(f"data-testid=estoque-recusar-convite-"
                                       f"{convite['id']}")
                            btn_nao.on("click", lambda c=convite, campo=inp:
                                       _responder_convite(sessao, c, False, campo, dlg,
                                                          btn_nao))
        dlg.open()
    except Exception:
        log.exception("_dialogo_convites_pendentes falhou")
        notificar("Erro ao abrir os convites.", type="negative")


def _responder_convite(sessao, convite, aceitar, campo, dlg, btn):
    """Aceita (ou recusa) o convite de tratar o depósito."""
    def _salvar():
        return est_bd.responder_convite_tarefa(
            convite["id"], sessao.user_nome, aceitar,
            (campo.value or "") if campo is not None else "")

    try:
        _gravar(btn, None, _salvar, fechar=dlg.close,
                ao_sucesso=lambda: ui.navigate.reload())
    except Exception:
        log.exception("_responder_convite falhou")
        notificar("Erro ao responder o convite.", type="negative")


# ============ aba 6: histórico de movimentação ============

def _desenhar_movimentos(sessao):
    """Histórico: o que saiu, de onde, para onde, e com qual documento."""
    try:
        movimentos = est_bd.listar_movimentos(limite=200)
    except Exception:
        log.exception("_desenhar_movimentos falhou")
        notificar("Erro ao carregar o histórico.", type="negative")
        return

    if not movimentos:
        with ui.column().classes("w-full items-center p-8 gap-2"):
            ui.icon("receipt_long", size="48px").classes("text-grey-5")
            ui.label("Nenhuma movimentação ainda.").classes("text-body1")
        return

    with ui.column().classes("w-full gap-1").style("min-width: 0"):
        for movimento in movimentos:
            cor = {"entrada": "green-7", "saida": "orange-8",
                   "devolucao": "teal", "baixa": "grey-6"}.get(movimento["tipo"],
                                                                 "grey-6")
            with ui.row().classes("w-full items-center flex-wrap") \
                    .style("gap: 0.5rem; min-width: 0") \
                    .props(f"data-testid=estoque-movimento-{movimento['id']}"):
                ui.badge(movimento["tipo"], color=cor).props("rounded")
                ui.label(f"{movimento['item_numero']} — {movimento['descricao']}").classes(
                    "text-caption font-medium").style("min-width: 0; word-break: break-word")
                ui.label(f"{movimento['quantidade']:g} "
                         f"{movimento['unidade_medida']}").classes(
                    "text-caption font-bold")
                ui.label(f"{movimento.get('origem_nome') or '—'} → "
                         f"{movimento.get('destino_nome') or '—'}").classes(
                    "text-caption text-grey-6").style("word-break: break-word")
                if movimento.get("documento_numero"):
                    ui.label(movimento["documento_numero"]).classes(
                        "text-caption text-blue-8") \
                        .style("cursor: pointer") \
                        .on("click", lambda _e, n=movimento["documento_numero"]:
                             _copiar_texto(n, "Documento"))
                ui.label(_data_curta(movimento["data_movimento"])).classes(
                    "text-caption text-grey-6")
                if movimento.get("usuario_actor"):
                    ui.label(f"por {movimento['usuario_actor']}").classes(
                        "text-caption text-grey-6")


# ============ diálogos de movimentação ============

def _dialogo_entrada(sessao, almoxarifado_id=None):
    """Entrada de material no almoxarifado (por padrão, o central)."""
    try:
        opcoes = _opcoes_almoxarifados()
        if not opcoes:
            notificar("Nenhum almoxarifado disponível.", type="warning")
            return
        with dialogo_formulario("Entrada de material", chave_modulo=CHAVE,
                                descricao="O que entra no almoxarifado: compra, nota de empenho, "
                                          "empenho ou doação. Se o item ainda não está no catálogo, "
                                          "ele é cadastrado agora com o número do almoxarifado."
                                ) as (dlg, _card, miolo, grade):
            with grade:
                sel_alm = ui.select(opcoes, label="Almoxarifado",
                                    value=almoxarifado_id or
                                    next(iter(opcoes.values()))) \
                    .classes("w-full")
                sel_alm.props("outlined dense data-testid=estoque-entrada-almoxarifado")
                inp_desc = ui.input("Item (o que entrou)",
                                    placeholder="Ex.: Resma A4").classes("w-full")
                inp_desc.props("outlined dense data-testid=estoque-entrada-item")
                inp_qtd = ui.number("Quantidade", value=1, min=0, step=1, format="%.3f") \
                    .classes("w-full") \
                    .props("outlined dense data-testid=estoque-entrada-qtd")
                sel_un = ui.select(dict(UNIDADES_ROTULO), label="Unidade de medida",
                                   value="UN").classes("w-full")
                sel_un.props("outlined dense data-testid=estoque-entrada-unidade")
                sel_origem = ui.select(dict(ORIGENS_ROTULO), label="Origem",
                                       value="nota_empenho").classes("w-full")
                sel_origem.props("outlined dense data-testid=estoque-entrada-origem")
                inp_data = ui.date("Data da entrada", value=_hoje()).classes("w-full")
                inp_data.props("outlined dense data-testid=estoque-entrada-data")
                inp_ne = ui.input("Nota de empenho (se houver)",
                                  placeholder="Ex.: NE-2026-0145").classes("w-full")
                inp_ne.props("outlined dense data-testid=estoque-entrada-nota")
                inp_resp = ui.input("Responsável pelo recebimento").classes("w-full")
                inp_resp.props("outlined dense data-testid=estoque-entrada-responsavel")
                inp_obs = ui.textarea("Observação").classes("w-full")
                inp_obs.props("outlined rows=2 dense data-testid=estoque-entrada-obs")
            with miolo:
                lbl = ui.label("").classes("text-caption text-grey-6")

                def _salvar():
                    return est_bd.registrar_entrada(
                        inp_desc.value or "", _qtd(inp_qtd.value), sel_un.value,
                        almoxarifado_id=sel_alm.value, data_entrada=_data_bruta(inp_data.value),
                        origem=sel_origem.value, nota_empenho=inp_ne.value or "",
                        responsavel_user_nome=inp_resp.value or "",
                        observacao=inp_obs.value or "", ator=sessao.user_nome,
                        eh_admin_geral=sessao.admin_geral)

                btn = botao("Registrar entrada", icone="save", chave_modulo=CHAVE) \
                    .props("data-testid=estoque-entrada-salvar")
                btn.on("click", lambda: _gravar(btn, lbl, _salvar, fechar=dlg.close,
                                                ao_sucesso=lambda: ui.navigate.reload()))
        dlg.open()
    except Exception:
        log.exception("_dialogo_entrada falhou")
        notificar("Erro ao abrir o formulário de entrada.", type="negative")


def _dialogo_transferencia(sessao, almoxarifado_origem_id=None, item_id=None,
                           destino_id=None):
    """Transferência: escolhe a origem, o item, a quantidade e o destino."""
    try:
        opcoes = _opcoes_almoxarifados()
        if len(opcoes) < 2:
            notificar("É preciso ter um almoxarifado de destino para transferir.",
                      type="warning")
            return
        with dialogo_formulario("Transferência de material", chave_modulo=CHAVE,
                                descricao="A transferência gera DOCUMENTO DE SAÍDA e baixa a origem. "
                                          "O que passaria do disponível é recusado, e a mensagem diz "
                                          "quanto tem — o estoque nunca fica negativo."
                                ) as (dlg, _card, miolo, grade):
            with grade:
                sel_origem = ui.select(opcoes, label="Almoxarifado de origem",
                                       value=almoxarifado_origem_id or
                                       next(iter(opcoes.values()))).classes("w-full")
                sel_origem.props("outlined dense data-testid=estoque-transf-origem")
                sel_item = ui.select({}, label="Item disponível na origem").classes("w-full")
                sel_item.props("outlined dense data-testid=estoque-transf-item")

                def _recarrega_itens(e=None):
                    try:
                        sel_item.set_options(
                            _opcoes_itens(sel_origem.value, apenas_com_saldo=True))
                        sel_item.update()
                    except Exception:
                        log.exception("_recarrega_itens falhou")
                        notificar("Erro ao listar os itens da origem.",
                                  type="negative")

                sel_origem.on_value_change(_recarrega_itens)
                _recarrega_itens()
                if item_id:
                    try:
                        sel_item.value = item_id
                    except Exception:
                        log.exception("_dialogo_transferencia: preencheu item falhou")

                opcoes_destino = {k: v for k, v in opcoes.items()
                                  if v != sel_origem.value}
                sel_destino = ui.select(opcoes_destino,
                                        label="Almoxarifado de destino",
                                        value=destino_id or
                                        next(iter(opcoes_destino.values()), None)) \
                    .classes("w-full")
                sel_destino.props("outlined dense data-testid=estoque-transf-destino")
                inp_qtd = ui.number("Quantidade", value=1, min=0, step=1,
                                    format="%.3f").classes("w-full")
                inp_qtd.props("outlined dense data-testid=estoque-transf-qtd")
                inp_data = ui.date("Data", value=_hoje()).classes("w-full")
                inp_data.props("outlined dense data-testid=estoque-transf-data")
                inp_resp = ui.input("Responsável pela saída").classes("w-full")
                inp_resp.props("outlined dense data-testid=estoque-transf-responsavel")
                inp_obs = ui.textarea("Observação").classes("w-full")
                inp_obs.props("outlined rows=2 dense data-testid=estoque-transf-obs")
            with miolo:
                lbl = ui.label("").classes("text-caption text-grey-6")

                def _salvar():
                    if not sel_origem.value or not sel_destino.value \
                            or sel_origem.value == sel_destino.value:
                        return (False, "Escolha almoxarifados de origem e destino "
                                       "diferentes.")
                    if not sel_item.value:
                        return (False, "Escolha o item a transferir.")
                    return est_bd.transferir(
                        sel_item.value, _qtd(inp_qtd.value), sel_destino.value,
                        almoxarifado_origem_id=sel_origem.value,
                        data_movimento=_data_bruta(inp_data.value),
                        responsavel=inp_resp.value or "", observacao=inp_obs.value or "",
                        ator=sessao.user_nome, eh_admin_geral=sessao.admin_geral)

                btn = botao("Transferir", icone="swap_horiz", chave_modulo=CHAVE) \
                    .props("data-testid=estoque-transf-salvar")
                btn.on("click", lambda: _gravar(btn, lbl, _salvar, fechar=dlg.close,
                                                ao_sucesso=lambda: ui.navigate.reload()))
        dlg.open()
    except Exception:
        log.exception("_dialogo_transferencia falhou")
        notificar("Erro ao abrir o formulário de transferência.", type="negative")


def _dialogo_entrega(sessao, almoxarifado_id=None, item_id=None):
    """Entrega de material a uma SALA: é o que passa a contar como EM USO."""
    try:
        opcoes = _opcoes_almoxarifados()
        if not opcoes:
            notificar("Nenhum almoxarifado disponível.", type="warning")
            return
        with dialogo_formulario("Entrega para a sala", chave_modulo=CHAVE,
                                descricao="O material sai do DISPONÍVEL e entra como EM USO. A sala "
                                          "e a data são obrigatórias: sem elas não dá para dizer "
                                          "quanto tempo o material está fora."
                                ) as (dlg, _card, miolo, grade):
            with grade:
                sel_alm = ui.select(opcoes, label="Almoxarifado",
                                    value=almoxarifado_id or next(iter(opcoes.values()))) \
                    .classes("w-full")
                sel_alm.props("outlined dense data-testid=estoque-entrega-almoxarifado")
                sel_item = ui.select({}, label="Item disponível").classes("w-full")
                sel_item.props("outlined dense data-testid=estoque-entrega-item")

                def _recarrega_itens(e=None):
                    try:
                        sel_item.set_options(
                            _opcoes_itens(sel_alm.value, apenas_com_saldo=True))
                        sel_item.update()
                    except Exception:
                        log.exception("_dialogo_entrega: listar itens falhou")
                        notificar("Erro ao listar os itens.", type="negative")

                sel_alm.on_value_change(_recarrega_itens)
                _recarrega_itens()
                if item_id:
                    try:
                        sel_item.value = item_id
                    except Exception:
                        log.exception("_dialogo_entrega: preencheu item falhou")
                inp_qtd = ui.number("Quantidade", value=1, min=0, step=1,
                                    format="%.3f").classes("w-full")
                inp_qtd.props("outlined dense data-testid=estoque-entrega-qtd")
                inp_data = ui.date("Data da entrega", value=_hoje()).classes("w-full")
                inp_data.props("outlined dense data-testid=estoque-entrega-data")
                inp_sala = ui.input("Sala de destino",
                                    placeholder="Ex.: Sala 12, Protocolo Geral") \
                    .classes("w-full")
                inp_sala.props("outlined dense data-testid=estoque-entrega-sala")
                inp_dep = ui.input("Departamento / setor").classes("w-full")
                inp_dep.props("outlined dense data-testid=estoque-entrega-departamento")
                inp_resp = ui.input("Responsável pelo uso").classes("w-full")
                inp_resp.props("outlined dense data-testid=estoque-entrega-responsavel")
            with miolo:
                lbl = ui.label("").classes("text-caption text-grey-6")

                def _salvar():
                    if not sel_item.value:
                        return (False, "Escolha o item que vai para a sala.")
                    return est_bd.entregar_item(
                        _qtd(inp_qtd.value), sel_alm.value, inp_sala.value or "",
                        destino_departamento=inp_dep.value or "",
                        responsavel_user_nome=inp_resp.value or "",
                        data_entrega=_data_bruta(inp_data.value), item_id=sel_item.value,
                        ator=sessao.user_nome, eh_admin_geral=sessao.admin_geral)

                btn = botao("Entregar", icone="meeting_room", chave_modulo=CHAVE) \
                    .props("data-testid=estoque-entrega-salvar")
                btn.on("click", lambda: _gravar(btn, lbl, _salvar, fechar=dlg.close,
                                                ao_sucesso=lambda: ui.navigate.reload()))
        dlg.open()
    except Exception:
        log.exception("_dialogo_entrega falhou")
        notificar("Erro ao abrir o formulário de entrega.", type="negative")


def _dialogo_baixa(sessao, entrega):
    """Baixa da entrega: devolve ao disponível OU marca como consumido."""
    try:
        with dialogo_card("Baixa da entrega", "w-[560px]",
                          chave_modulo=CHAVE) as (dlg, _card):
            ui.label(f"{entrega['item_numero']} — {entrega['descricao']} · "
                     f"{entrega['quantidade']:g} {entrega['unidade_medida']} "
                     f"em {entrega['destino_sala']}").classes("text-body2")
            inp_qtd = ui.number("Quantidade da baixa",
                                value=entrega["quantidade"], min=0, step=1,
                                format="%.3f")
            inp_qtd.props("outlined dense data-testid=estoque-baixa-qtd")
            inp_data = ui.date("Data da baixa", value=_hoje())
            inp_data.props("outlined dense data-testid=estoque-baixa-data")
            sel_motivo = ui.select(
                {"devolver": "Voltou ao almoxarifado (fica disponível)",
                 "consumido": "Foi consumido (não volta)"},
                label="O que aconteceu com o material", value="devolver")
            sel_motivo.props("outlined dense data-testid=estoque-baixa-motivo")
            lbl = ui.label("").classes("text-caption text-grey-6")

            def _salvar():
                return est_bd.dar_baixa_entrega(
                    entrega["id"], _qtd(inp_qtd.value),
                    devolver_ao_almoxarifado=(sel_motivo.value == "devolver"),
                    data_baixa=_data_bruta(inp_data.value), ator=sessao.user_nome,
                    eh_admin_geral=sessao.admin_geral)

            btn = botao("Dar baixa", icone="task_alt", chave_modulo=CHAVE) \
                .props("data-testid=estoque-baixa-salvar")
            btn.on("click", lambda: _gravar(btn, lbl, _salvar, fechar=dlg.close,
                                            ao_sucesso=lambda: ui.navigate.reload()))
        dlg.open()
    except Exception:
        log.exception("_dialogo_baixa falhou")
        notificar("Erro ao abrir a baixa da entrega.", type="negative")


def _dialogo_recolhimento(sessao, almoxarifado_id=None, item_id=None, sala=""):
    """Pedido de recolhimento: do almoxarifado ou de quem está com o item."""
    try:
        opcoes = _opcoes_almoxarifados()
        if not opcoes:
            notificar("Nenhum almoxarifado disponível.", type="warning")
            return
        with dialogo_formulario("Pedido de recolhimento", chave_modulo=CHAVE,
                                descricao="O material entregue e não usado volta a ficar DISPONÍVEL "
                                          "quando o central atende o pedido. É o pedido que evita "
                                          "o desperdício: quem pede é o almoxarifado da secretaria "
                                          "ou quem está com o item parado."
                                ) as (dlg, _card, miolo, grade):
            with grade:
                sel_alm = ui.select(opcoes, label="Almoxarifado",
                                    value=almoxarifado_id or next(iter(opcoes.values()))) \
                    .classes("w-full")
                sel_alm.props("outlined dense data-testid=estoque-pedido-almoxarifado")
                sel_item = ui.select({}, label="Item entregue e ainda em uso").classes("w-full")
                sel_item.props("outlined dense data-testid=estoque-pedido-item")

                def _recarrega_itens(e=None):
                    try:
                        opcoes_item = {}
                        for entrega in est_bd.listar_entregas(
                                almoxarifado_id=sel_alm.value, situacao="em_uso"):
                            rotulo = (f"{entrega['item_numero']} — "
                                      f"{entrega['descricao']} em "
                                      f"{entrega['destino_sala']} "
                                      f"({entrega['quantidade']:g} "
                                      f"{entrega['unidade_medida']}, "
                                      f"{entrega['dias_parado']} dia(s))")
                            opcoes_item[rotulo] = entrega["item_id"]
                        sel_item.set_options(opcoes_item)
                        sel_item.update()
                    except Exception:
                        log.exception("_dialogo_recolhimento: listar entregas falhou")
                        notificar("Erro ao listar as entregas em uso.", type="negative")

                sel_alm.on_value_change(_recarrega_itens)
                _recarrega_itens()
                if item_id:
                    try:
                        sel_item.value = item_id
                    except Exception:
                        log.exception("_dialogo_recolhimento: preencheu item falhou")
                sel_tipo = ui.select(
                    {"recolhimento": "Almoxarifado pede para o central recolher",
                     "devolucao": "Quem está com o item devolve por não uso"},
                    label="Quem está pedindo", value="recolhimento").classes("w-full")
                sel_tipo.props("outlined dense data-testid=estoque-pedido-tipo")
                inp_qtd = ui.number("Quantidade", value=1, min=0, step=1,
                                    format="%.3f").classes("w-full")
                inp_qtd.props("outlined dense data-testid=estoque-pedido-qtd")
                inp_sala = ui.input("Sala", value=sala or "").classes("w-full")
                inp_sala.props("outlined dense data-testid=estoque-pedido-sala")
                inp_motivo = ui.textarea("Motivo (por que o material não foi usado)") \
                    .classes("w-full")
                inp_motivo.props("outlined rows=2 dense data-testid=estoque-pedido-motivo")
            with miolo:
                lbl = ui.label("").classes("text-caption text-grey-6")

                def _salvar():
                    if not sel_item.value:
                        return (False, "Escolha o item que está parado na sala.")
                    return est_bd.abrir_pedido_recolhimento(
                        sel_alm.value, sel_item.value, _qtd(inp_qtd.value),
                        tipo_pedido=sel_tipo.value, destino_sala=inp_sala.value or "",
                        motivo=inp_motivo.value or "", solicitante_user_nome=sessao.user_nome,
                        ator=sessao.user_nome, eh_admin_geral=sessao.admin_geral)

                btn = botao("Abrir pedido", icone="assignment_return",
                            chave_modulo=CHAVE) \
                    .props("data-testid=estoque-pedido-salvar")
                btn.on("click", lambda: _gravar(btn, lbl, _salvar, fechar=dlg.close,
                                                ao_sucesso=lambda: ui.navigate.reload()))
        dlg.open()
    except Exception:
        log.exception("_dialogo_recolhimento falhou")
        notificar("Erro ao abrir o pedido de recolhimento.", type="negative")


# ============ diálogos de almoxarifado e item (administrador) ============

def _dialogo_novo_almoxarifado(sessao):
    """Cria almoxarifado descentralizado para uma secretaria do organograma."""
    try:
        unidades = integracoes.listar_unidades_organograma(ativo=1) or []
        if not unidades:
            with dialogo_card("Novo almoxarifado", "w-[560px]",
                              chave_modulo=CHAVE) as (dlg, _card):
                ui.label("O organograma não respondeu, então não há secretaria "
                         "para escolher. O almoxarifado é sempre ligado a uma "
                         "secretaria — recarregue a página quando o organograma "
                         "estiver carregado.").classes("text-body2 text-grey-7")
            dlg.open()
            return
        opcoes = {u["nome"]: u["id"] for u in unidades}
        with dialogo_formulario("Novo almoxarifado", chave_modulo=CHAVE,
                                descricao="Cada secretaria do organograma pode ter o seu almoxarifado. "
                                          "Quem escolhe quais secretarias têm almoxarifado é o "
                                          "administrador do módulo — secretaria sem almoxarifado "
                                          "simplesmente não tem."
                                ) as (dlg, _card, miolo, grade):
            with grade:
                sel_unidade = ui.select(opcoes, label="Secretaria (organograma)") \
                    .classes("w-full")
                sel_unidade.props("outlined dense data-testid="
                                  "estoque-almox-secretaria")
                inp_nome = ui.input("Nome do almoxarifado",
                                    placeholder="Vazio = usa o nome da secretaria") \
                    .classes("w-full")
                inp_nome.props("outlined dense data-testid=estoque-almox-nome")
                inp_sigla = ui.input("Sigla (opcional)").classes("w-full")
                inp_sigla.props("outlined dense maxlength=6 data-testid="
                                "estoque-almox-sigla")
                inp_resp = ui.input("Responsável pelo almoxarifado").classes("w-full")
                inp_resp.props("outlined dense data-testid=estoque-almox-responsavel")
            with miolo:
                lbl_sug = ui.label("").classes("text-caption text-grey-6")

                def _sugerir(e=None):
                    """Sugere a secretaria pela lotação do servidor escolhido."""
                    try:
                        unidade_id, nome = est_bd.sugerir_secretaria(
                            (inp_resp.value or "").strip())
                        if nome:
                            lbl_sug.text = f"Lotação deste servidor: {nome}"
                            if nome in opcoes:
                                sel_unidade.value = nome
                                sel_unidade.update()
                            if not (inp_nome.value or "").strip():
                                inp_nome.value = f"Almoxarifado {nome}"
                    except Exception:
                        log.exception("_sugerir falhou")

                inp_resp.on_value_change(_sugerir)
                lbl = ui.label("").classes("text-caption text-grey-6")

                def _salvar():
                    nome = (inp_nome.value or "").strip()
                    if not nome:
                        nome = f"Almoxarifado {sel_unidade.value or ''}".strip()
                    return est_bd.criar_almoxarifado(
                        nome, unidade_id=sel_unidade.value,
                        unidade_nome=sel_unidade.value or "",
                        responsavel_user_nome=inp_resp.value or "",
                        sigla=inp_sigla.value or "", ator=sessao.user_nome,
                        eh_admin_geral=sessao.admin_geral)

                btn = botao("Criar almoxarifado", icone="add_business",
                            chave_modulo=CHAVE) \
                    .props("data-testid=estoque-almox-salvar")
                btn.on("click", lambda: _gravar(btn, lbl, _salvar, fechar=dlg.close,
                                                ao_sucesso=lambda: ui.navigate.reload()))
        dlg.open()
    except Exception:
        log.exception("_dialogo_novo_almoxarifado falhou")
        notificar("Erro ao abrir o formulário de almoxarifado.", type="negative")


def _dialogo_ajustes_almoxarifado(sessao, almoxarifado):
    """Ajustes do almoxarifado: responsável, estado e formato do número."""
    try:
        with dialogo_formulario(f"Ajustes — {almoxarifado['nome']}",
                                chave_modulo=CHAVE,
                                descricao="O estoque central é fixo e não aparece aqui: ele não se "
                                          "renomeia, não se desativa e não se exclui."
                                ) as (dlg, _card, miolo, grade):
            with grade:
                inp_nome = ui.input("Nome", value=almoxarifado["nome"]).classes("w-full")
                inp_nome.props("outlined dense data-testid=estoque-ajuste-nome")
                inp_resp = ui.input("Responsável",
                                    value=almoxarifado["responsavel_user_nome"] or "") \
                    .classes("w-full")
                inp_resp.props("outlined dense data-testid=estoque-ajuste-responsavel")
                chk_ativo = ui.switch("Ativo", value=bool(almoxarifado["ativo"]))
                chk_ativo.props("data-testid=estoque-ajuste-ativo")
                chk_bloq = ui.switch("Bloqueado para movimentação",
                                     value=bool(almoxarifado["bloqueado"]))
                chk_bloq.props("data-testid=estoque-ajuste-bloqueado")
                inp_pref_item = ui.input("Prefixo do item",
                                         value=almoxarifado["prefixo_item"] or "IT") \
                    .classes("w-full")
                inp_pref_item.props("outlined dense maxlength=12 data-testid="
                                    "estoque-ajuste-prefixo-item")
                inp_pref_doc = ui.input("Prefixo do documento",
                                        value=almoxarifado["prefixo_documento"] or "DOC") \
                    .classes("w-full")
                inp_pref_doc.props("outlined dense maxlength=12 data-testid="
                                   "estoque-ajuste-prefixo-doc")
                num_dig = ui.number("Dígitos", value=almoxarifado["digitos_numero"],
                                    min=est_bd.DIGITOS_MINIMO,
                                    max=est_bd.DIGITOS_MAXIMO, step=1).classes("w-full")
                num_dig.props("outlined dense data-testid=estoque-ajuste-digitos")
            with miolo:
                ui.separator()
                ui.label("Formato do número — NÃO renumera o que já existe.").classes(
                    "text-caption text-grey-7")
                lbl_ex = ui.label(
                    f"Fica assim: {almoxarifado['prefixo_item']}-"
                    f"{'0' * int(almoxarifado['digitos_numero'])} / "
                    f"{almoxarifado['prefixo_documento']}-"
                    f"{'0' * int(almoxarifado['digitos_numero'])}").classes(
                    "text-caption text-grey-6")

                def _previa():
                    try:
                        dig = est_bd.validar_digitos(num_dig.value)
                        lbl_ex.text = (
                            f"Fica assim: {(inp_pref_item.value or 'IT').upper()}-"
                            f"{'0' * dig} / {(inp_pref_doc.value or 'DOC').upper()}-"
                            f"{'0' * dig}")
                    except Exception:
                        log.exception("_previa falhou")

                inp_pref_item.on_value_change(lambda _e=None: _previa())
                inp_pref_doc.on_value_change(lambda _e=None: _previa())
                num_dig.on_value_change(lambda _e=None: _previa())
                lbl = ui.label("").classes("text-caption text-grey-6")

                def _salvar():
                    ok, msg = est_bd.atualizar_almoxarifado(
                        almoxarifado["id"],
                        {"nome": inp_nome.value or "",
                         "responsavel_user_nome": inp_resp.value or "",
                         "ativo": bool(chk_ativo.value),
                         "bloqueado": bool(chk_bloq.value)},
                        ator=sessao.user_nome, eh_admin_geral=sessao.admin_geral)
                    if not ok:
                        return (ok, msg)
                    ok2, msg2 = est_bd.definir_formato_numero(
                        almoxarifado["id"], prefixo_item=inp_pref_item.value or "",
                        prefixo_documento=inp_pref_doc.value or "",
                        digitos=num_dig.value, ator=sessao.user_nome,
                        eh_admin_geral=sessao.admin_geral)
                    return (ok2, msg2 if ok2 else f"{msg} {msg2}")

                btn = botao("Salvar ajustes", icone="save", chave_modulo=CHAVE) \
                    .props("data-testid=estoque-ajuste-salvar")
                btn.on("click", lambda: _gravar(btn, lbl, _salvar, fechar=dlg.close,
                                                ao_sucesso=lambda: ui.navigate.reload()))
                with ui.row().classes("w-full justify-end").style("gap: 0.5rem"):
                    btn_excluir = botao("Excluir almoxarifado", variante="perigo",
                                        chave_modulo=CHAVE) \
                        .props("data-testid=estoque-ajuste-excluir")
                    btn_excluir.on("click", lambda: _gravar(
                        btn_excluir, lbl,
                        lambda: est_bd.excluir_almoxarifado(
                            almoxarifado["id"], ator=sessao.user_nome,
                            eh_admin_geral=sessao.admin_geral),
                        fechar=dlg.close, ao_sucesso=lambda: ui.navigate.reload()))
        dlg.open()
    except Exception:
        log.exception("_dialogo_ajustes_almoxarifado falhou")
        notificar("Erro ao abrir os ajustes do almoxarifado.", type="negative")


def _dialogo_novo_item(sessao, almoxarifado_id=None):
    """Cadastra um item no catálogo, com o número do almoxarifado."""
    try:
        opcoes = _opcoes_almoxarifados()
        if not opcoes:
            notificar("Nenhum almoxarifado disponível.", type="warning")
            return
        with dialogo_formulario("Cadastrar item", chave_modulo=CHAVE,
                                descricao="O item recebe um número sequencial do almoxarifado "
                                          "escolhido, e o número nunca é reaproveitado. A quantidade "
                                          "entra depois, pelo botão de entrada."
                                ) as (dlg, _card, miolo, grade):
            with grade:
                inp_desc = ui.input("Descrição do item",
                                    placeholder="Ex.: Resma A4").classes("w-full")
                inp_desc.props("outlined dense data-testid=estoque-item-descricao")
                sel_un = ui.select(dict(UNIDADES_ROTULO),
                                   label="Unidade de medida", value="UN").classes("w-full")
                sel_un.props("outlined dense data-testid=estoque-item-unidade")
                sel_alm = ui.select(opcoes, label="Almoxarifado",
                                    value=almoxarifado_id or
                                    next(iter(opcoes.values()))).classes("w-full")
                sel_alm.props("outlined dense data-testid=estoque-item-almoxarifado")
                sel_origem = ui.select(dict(ORIGENS_ROTULO), label="Origem padrão",
                                       value="nota_empenho").classes("w-full")
                sel_origem.props("outlined dense data-testid=estoque-item-origem")
            with miolo:
                lbl = ui.label("").classes("text-caption text-grey-6")

                def _salvar():
                    return est_bd.cadastrar_item(
                        inp_desc.value or "", sel_un.value, sel_alm.value,
                        origem_padrao=sel_origem.value, ator=sessao.user_nome,
                        eh_admin_geral=sessao.admin_geral)

                btn = botao("Cadastrar item", icone="inventory_2", chave_modulo=CHAVE) \
                    .props("data-testid=estoque-item-salvar")
                btn.on("click", lambda: _gravar(btn, lbl, _salvar, fechar=dlg.close,
                                                ao_sucesso=lambda: ui.navigate.reload()))
        dlg.open()
    except Exception:
        log.exception("_dialogo_novo_item falhou")
        notificar("Erro ao abrir o cadastro de item.", type="negative")


def _dialogo_tarefa(sessao):
    """Abre uma tarefa de depósito: é o "chamar para tratar o depósito"."""
    try:
        opcoes = _opcoes_almoxarifados()
        if not opcoes:
            notificar("Nenhum almoxarifado disponível.", type="warning")
            return
        with dialogo_formulario("Nova tarefa de depósito", chave_modulo=CHAVE,
                                descricao="A tarefa é quem chama: você abre, escolhe quantos "
                                          "servidores são necessários e convida servidores já "
                                          "cadastrados. Quem aceita passa a contar como tratando "
                                          "o depósito."
                                ) as (dlg, _card, miolo, grade):
            with grade:
                inp_titulo = ui.input("Título",
                                      placeholder="Ex.: Conferência da entrada de outubro") \
                    .classes("w-full")
                inp_titulo.props("outlined dense data-testid=estoque-tarefa-titulo")
                sel_tipo = ui.select(dict(TIPOS_TAREFA_ROTULO), label="Tipo de tarefa",
                                     value="conferir").classes("w-full")
                sel_tipo.props("outlined dense data-testid=estoque-tarefa-tipo")
                sel_alm = ui.select(opcoes, label="Almoxarifado do depósito",
                                    value=next(iter(opcoes.values()))).classes("w-full")
                sel_alm.props("outlined dense data-testid=estoque-tarefa-almoxarifado")
                inp_desc = ui.textarea("O que precisa ser feito").classes("w-full")
                inp_desc.props("outlined rows=2 dense data-testid=estoque-tarefa-descricao")
                num_conv = ui.number("Servidores necessários", value=1, min=1,
                                     max=20, step=1).classes("w-full")
                num_conv.props("outlined dense data-testid=estoque-tarefa-necessarios")
            with miolo:
                lbl = ui.label("").classes("text-caption text-grey-6")

                def _salvar():
                    return est_bd.criar_tarefa_deposito(
                        inp_titulo.value or "", tipo=sel_tipo.value,
                        descricao=inp_desc.value or "", almoxarifado_id=sel_alm.value,
                        responsavel_user_nome=sessao.user_nome,
                        necessarios_convidados=num_conv.value or 1,
                        ator=sessao.user_nome, eh_admin_geral=sessao.admin_geral)

                btn = botao("Abrir tarefa", icone="handyman", chave_modulo=CHAVE) \
                    .props("data-testid=estoque-tarefa-salvar")
                btn.on("click", lambda: _gravar(btn, lbl, _salvar, fechar=dlg.close,
                                                ao_sucesso=lambda: ui.navigate.reload()))
        dlg.open()
    except Exception:
        log.exception("_dialogo_tarefa falhou")
        notificar("Erro ao abrir a tarefa de depósito.", type="negative")


def _dialogo_convite(sessao, tarefa):
    """CHAMA um servidor cadastrado para tratar o depósito."""
    try:
        with dialogo_formulario(f"Chamar servidor — {tarefa['numero']}",
                                chave_modulo=CHAVE,
                                descricao=f"Aceitos: {tarefa['aceitos']} de "
                                          f"{tarefa['necessarios_convidados']} necessários. O "
                                          f"convite fica pendente até o servidor aceitar."
                                ) as (dlg, _card, miolo, grade):
            with grade:
                inp_busca = ui.input("Buscar servidor cadastrado",
                                     placeholder="nome ou login").classes("w-full")
                inp_busca.props("outlined dense clearable data-testid="
                                "estoque-convite-busca")
                sel_conv = ui.select({}, label="Servidor encontrado").classes("w-full")
                sel_conv.props("outlined dense clearable data-testid=estoque-convite-servidor")
                inp_recado = ui.textarea("Recado (o que ele vai fazer)").classes("w-full")
                inp_recado.props("outlined rows=2 dense data-testid=estoque-convite-recado")
            with miolo:
                lbl = ui.label("").classes("text-caption text-grey-6")

            def _buscar(e=None):
                """Busca servidores pelo cadastro — o módulo nunca cria usuário."""
                try:
                    termo = (getattr(e, "value", "") or inp_busca.value or "").strip()
                    achados = integracoes.buscar_usuarios_gestao(termo=termo, limite=40) \
                        or []
                    opcoes = {}
                    for achado in achados:
                        login = achado.get("user_nome") or ""
                        if not login:
                            continue
                        nome = achado.get("nome_exibicao") or login
                        unidade = achado.get("unidade") or achado.get("lotacao") or ""
                        opcoes[f"{nome} (@{login})"
                               + (f" — {unidade}" if unidade else "")] = login
                    sel_conv.set_options(opcoes)
                    sel_conv.update()
                except Exception:
                    log.exception("_buscar servidor falhou")
                    notificar("Erro ao buscar servidores.", type="negative")

            inp_busca.on_value_change(_buscar)
            try:
                _buscar()
            except Exception:
                pass
            btn = botao("Chamar servidor", icone="person_add", chave_modulo=CHAVE) \
                .props("data-testid=estoque-convite-salvar")

            def _salvar():
                if not sel_conv.value:
                    return (False, "Escolha o servidor que vai tratar o depósito.")
                return est_bd.convidar_para_tarefa(
                    tarefa["id"], sel_conv.value, papel="participa",
                    recado=inp_recado.value or "", ator=sessao.user_nome,
                    eh_admin_geral=sessao.admin_geral)

            btn.on("click", lambda: _gravar(btn, lbl, _salvar, fechar=dlg.close,
                                            ao_sucesso=lambda: ui.navigate.reload()))
        dlg.open()
    except Exception:
        log.exception("_dialogo_convite falhou")
        notificar("Erro ao abrir o convite de depósito.", type="negative")
