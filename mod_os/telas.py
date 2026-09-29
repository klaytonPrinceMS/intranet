"""EN: Service Orders — the business screen (route /os).
Boards list, per-board columns with cards, card detail (edit, timeline,
comments), invites, and the working views (my cards, overdue, unassigned).

PT-BR: Ordens de Serviço — tela de negócio (rota /os).
Lista de quadros, colunas com os cartões de cada quadro, detalhe da ordem de
serviço (edição, linha do tempo, comentários), convites e as visões de
trabalho (meus cartões, atrasadas, sem responsável).
"""

import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from nicegui import ui, run

from mod_intranet import autenticacao
from mod_intranet import integracoes
from mod_intranet import observabilidade
from mod_intranet.aba_modulo import cabecalho
from mod_intranet.tema_modulo import ler_tema, notificar
from mod_intranet.ui_comum import CORES, botao, botao_icone
from mod_os import bd_manipulador as os_bd

log = observabilidade.get_logger("os")

CHAVE = "os"
TEXTO_CABECALHO = ("Quadros de ordens de serviço — por servidor ou por unidade "
                   "do organograma.")

PRIORIDADES = {"baixa": "Baixa", "media": "Média", "alta": "Alta",
               "urgente": "Urgente"}
PAPEIS_ROTULO = {"leitor": "Leitor (só vê)", "editor": "Editor (cria e move)",
                 "administrador": "Administrador (gerencia o quadro)",
                 "dono": "Dono do quadro", "unidade": "Leitor da unidade"}
CORES_PRIORIDADE = {"baixa": "grey-7", "media": "teal", "alta": "orange-8",
                    "urgente": "red-8"}


def _pode_acessar(user_nome, perfil_global):
    """Acesso ao módulo: administrador geral ou vínculo liberado no cadastro."""
    if perfil_global == "administrador_geral":
        return True
    try:
        return autenticacao.validar_acesso_modulo(user_nome, CHAVE)
    except Exception:
        log.exception(f"_pode_acessar({user_nome}) falhou")
        return False


def _prazo_curto(data):
    """Data em dd/mm — é assim que o servidor lê o prazo."""
    if not data:
        return ""
    try:
        return datetime.strptime(str(data)[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return str(data)[:10]


def _para_data_bruta(valor):
    """`ui.date` devolve `date`/`datetime`; o banco guarda `YYYY-MM-DD`."""
    if not valor:
        return ""
    try:
        return valor.strftime("%Y-%m-%d")
    except (AttributeError, ValueError, TypeError):
        return str(valor)[:10]


def _data_sugerida():
    return (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")


def _copiar_texto(texto, rotulo):
    """Copia o número da ordem de serviço — é o que o servidor vai ditar."""
    try:
        ui.clipboard.write(texto)
        notificar(f"{rotulo} copiado: {texto}", type="positive")
    except Exception:
        log.exception(f"_copiar_texto({texto}) falhou")
        notificar(f"Não foi possível copiar. {rotulo}: {texto}", type="warning")


async def _gravar(botao_ui, status_ui, funcao, fechar=None, ao_sucesso=None):
    """Botão de gravação: trava reentrância, roda fora do event-loop, avisa.

    `funcao` é a escrita (chamada em `run.io_bound`, para não travar o
    event-loop do servidor). Devolve `(ok, mensagem)`. O estado do botão e
    do aviso volta SEMPRE no `finally` — erro não pode deixar a tela
    travada."""
    ocupado = {"valor": True}
    try:
        if botao_ui is not None:
            botao_ui.disable()
        if status_ui is not None:
            status_ui.set_text("Salvando…")
        try:
            retorno = await run.io_bound(funcao)
        except Exception:
            log.exception("_gravar: a escritaRaised exceção")
            notificar("Erro inesperado ao salvar.", type="negative")
            return
        ok, mensagem = (retorno if isinstance(retorno, tuple) and len(retorno) >= 2
                        else (bool(retorno), "" if retorno else "Falha ao salvar."))
        if ok:
            if ao_sucesso is not None:
                try:
                    ao_sucesso()
                except Exception:
                    log.exception("_gravar: callback de sucesso falhou")
            if fechar is not None:
                fechar()
        notificar(mensagem or ("Salvo." if ok else "Falha ao salvar."),
                  type="positive" if ok else "negative")
    except Exception:
        log.exception("_gravar falhou")
        notificar("Erro inesperado ao salvar.", type="negative")
    finally:
        ocupado["valor"] = False
        try:
            if status_ui is not None:
                status_ui.set_text("")
            if botao_ui is not None:
                botao_ui.enable()
        except Exception:
            log.exception("_gravar: falha ao restaurar o botão")


class _SessaoOs:
    """Quem está na tela e qual quadro está aberto.

    Objeto de sessão por servidor (um por chamada de `mostrar_tela`): guarda
    o login, se é administrador geral e o quadro em edição. Existe para não
    passar quatro parâmetros por toda função e para que o quadro aberto
    NUNCA vire variável global — dois servidores na mesma página não podem
    trocar o quadro um do outro."""

    def __init__(self, user_nome, perfil_global):
        self.user_nome = user_nome or ""
        self.perfil_global = perfil_global or ""
        self.admin_geral = perfil_global == "administrador_geral"
        self.quadro_aberto = None
        self.recarregar = None

    def papel(self, quadro_id):
        """Papel da pessoa no quadro."""
        try:
            return os_bd.papel_no_quadro(self.user_nome, quadro_id, self.admin_geral)
        except Exception:
            log.exception("sessao.papel falhou")
            return None

    def abrir(self, quadro_id):
        """Abre um quadro e redesenha a aba."""
        self.quadro_aberto = quadro_id
        if self.recarregar:
            self.recarregar()

    def voltar(self):
        """Volta para a lista de quadros."""
        self.quadro_aberto = None
        if self.recarregar:
            self.recarregar()


def mostrar_tela(user_nome: str, perfil_global: str = ""):
    """EN: Renders /os — the Service Orders screen for the logged user.

    PT-BR: Renderiza /os — a tela de ordens de serviço do servidor logado.

    Monta cabeçalho e abas de trabalho: quadros, convites pendentes, meus
    cartões, atrasadas e sem responsável."""
    if not _pode_acessar(user_nome, perfil_global):
        with ui.column().classes("w-full items-center p-12 gap-3"):
            ui.icon("block", size="64px").classes("text-red-8")
            ui.label("Acesso restrito").classes("text-h6")
            ui.label("Somente usuários com acesso ao módulo "
                     "Ordens de Serviço.").classes("text-body2 text-grey-7")
        return

    sessao = _SessaoOs(user_nome, perfil_global)
    tema = ler_tema(CHAVE, cor_botao="#000000", cor_texto_botao="#FFFFFF",
                    texto_header=TEXTO_CABECALHO)
    ui.colors(primary=tema["cor_botao"])

    with ui.column().classes("w-full p-6 gap-4"):
        cabecalho("Ordens de Serviço", tema["texto_header"], chave_modulo=CHAVE,
                  cor_titulo=tema["cor_titulo"], cor_fundo=tema["cor_fundo"])

        with ui.tabs().classes("w-full") as _abas:
            aba_quadros = ui.tab("Quadros")
            aba_convites = ui.tab("Convites")
            aba_minhas = ui.tab("Meus cartões")
            aba_atrasadas = ui.tab("Atrasadas")
            aba_sem_resp = ui.tab("Sem responsável")

        # O container dos painéis é `ui.tab_panels(abas)`, não `ui.stack`.
        # `ui.stack` NÃO EXISTE no NiceGUI: a tela desenhava as abas (que são
        # os `ui.tab`) e estourava AttributeError na primeira linha de painel,
        # então o módulo aparecia no menu e não renderizava nada dentro.
        with ui.tab_panels(_abas, value=aba_quadros).classes("w-full bg-transparent"):
            with ui.tab_panel(aba_quadros):

                @ui.refreshable
                def aba_quadros_painel():
                    """Desenha a lista de quadros OU o quadro aberto."""
                    if sessao.quadro_aberto:
                        _desenhar_quadro(sessao)
                    else:
                        _desenhar_lista(sessao)

                sessao.recarregar = aba_quadros_painel.refresh
                aba_quadros_painel()

            with ui.tab_panel(aba_convites):
                _desenhar_convites(sessao)
            with ui.tab_panel(aba_minhas):
                _desenhar_minhas(sessao, "meus")
            with ui.tab_panel(aba_atrasadas):
                _desenhar_minhas(sessao, "atraso")
            with ui.tab_panel(aba_sem_resp):
                _desenhar_minhas(sessao, "sem_responsavel")


# ============ lista de quadros ============

def _desenhar_lista(sessao):
    """Aba 'Quadros': o que a pessoa vê e o botão de criar."""
    try:
        quadros = os_bd.listar_quadros_visiveis(sessao.user_nome, sessao.admin_geral)
    except Exception:
        log.exception("_desenhar_lista falhou ao listar")
        notificar("Erro ao carregar os quadros.", type="negative")
        return
    with ui.row().classes("w-full items-center justify-between flex-wrap") \
            .style("gap: 0.5rem"):
        ui.label(f"{len(quadros)} quadro(s)").classes("text-body2 text-grey-7")
        botao("Novo quadro", icone="add", chave_modulo=CHAVE,
              on_click=lambda: _dialogo_novo_quadro(sessao)) \
            .props("data-testid=os-novo-quadro")

    if not quadros:
        with ui.column().classes("w-full items-center p-8 gap-2"):
            ui.icon("dashboard_customize", size="48px").classes("text-grey-5")
            ui.label("Nenhum quadro ainda.").classes("text-body1")
            ui.label("Crie o seu: ele nasce privado, com as colunas padrão e "
                     "numeração própria.").classes("text-caption text-grey-6")
        return

    with ui.grid().classes("w-full grid-cols-1 sm:grid-cols-2 lg:grid-cols-3") \
            .style("gap: 0.75rem"):
        for quadro in quadros:
            _cartao_quadro(sessao, quadro)


def _cartao_quadro(sessao, quadro):
    """Cartão-resumo de um quadro na lista."""
    try:
        colunas = os_bd.listar_colunas(quadro["id"])
        pendentes = [o for o in os_bd.listar_ordens(quadro["id"])
                     if not o["concluido_em"]]
        atrasadas = [o for o in pendentes if o.get("atrasada")]
        proximo = os_bd.proximo_numero(quadro["id"]) + 1
        with ui.card().classes("w-full").style(
                "border-left: 6px solid "
                f"{quadro.get('cor') or CORES['primaria']}") \
                .props(f"data-testid=os-quadro-{quadro['id']}"):
            with ui.column().classes("w-full gap-1").style("min-width: 0"):
                with ui.row().classes("w-full items-center justify-between flex-wrap") \
                        .style("gap: 0.5rem"):
                    ui.label(quadro["nome"]).classes("text-subtitle1 font-bold") \
                        .style("min-width: 0; word-break: break-word")
                    _rotulo_visibilidade(quadro)
                if quadro.get("descricao"):
                    ui.label(quadro["descricao"]).classes("text-caption text-grey-7") \
                        .style("word-break: break-word")
                ui.label(
                    f"{len(colunas)} coluna(s) · {len(pendentes)} em aberto"
                    + (f" · {len(atrasadas)} atrasada(s)" if atrasadas else "")
                    + " · próximo "
                    + os_bd.montar_numero(quadro["prefixo_numero"], proximo,
                                          quadro["digitos_numero"])
                ).classes("text-caption text-grey-6").style("word-break: break-word")
                if quadro.get("visibilidade") == "unidade" and quadro.get("unidade_nome"):
                    ui.label(f"Unidade: {quadro['unidade_nome']}") \
                        .classes("text-caption text-grey-6")
                with ui.row().classes("w-full justify-end").style("gap: 0.5rem"):
                    botao("Abrir", icone="open_in_new", variante="secundario",
                          chave_modulo=CHAVE,
                          on_click=lambda q=quadro: sessao.abrir(q["id"])) \
                        .props(f"data-testid=os-abrir-quadro-{quadro['id']}")
    except Exception:
        log.exception(f"_cartao_quadro({quadro.get('id')}) falhou")
        notificar("Erro ao desenhar um quadro.", type="negative")


def _rotulo_visibilidade(quadro):
    """Etiqueta 'Privado' ou 'Unidade' — o servidor precisa saber quem vê."""
    try:
        if quadro.get("visibilidade") == "unidade":
            ui.badge("Unidade", color="teal").props("rounded")
        else:
            ui.badge("Privado", color="grey-6").props("rounded")
    except Exception:
        log.exception("_rotulo_visibilidade falhou")


def _dialogo_novo_quadro(sessao):
    """Diálogo de criação de quadro — privado do dono ou da unidade."""
    try:
        with ui.dialog() as dlg, ui.card().classes("w-[600px] max-h-[90vh]"):
            ui.label("Novo quadro de ordens de serviço").classes("text-h6")
            ui.separator()
            inp_nome = ui.input("Nome do quadro",
                                placeholder="Ex.: Obras 2026, Manutenção")
            inp_nome.props("outlined dense data-testid=os-quadro-nome")
            inp_desc = ui.textarea("Descrição",
                                   placeholder="Do que trata este quadro?")
            inp_desc.props("outlined dense rows=2 "
                           "data-testid=os-quadro-descricao")

            sel_cor = ui.select(dict(os_bd._CORES_QUADRO), label="Cor do quadro",
                                value="azul")
            sel_cor.props("outlined dense data-testid=os-quadro-cor")

            inp_prefixo = ui.input("Prefixo do número",
                                   placeholder="Ex.: OBRAS (até 6 letras)")
            inp_prefixo.props("outlined dense maxlength=12 "
                              "data-testid=os-quadro-prefixo")
            inp_prefixo.tooltip("Vazio = prefixo tirado do nome do quadro. "
                                "Ex.: 'Obras 2026' vira OBRAS-0001.")

            num_digitos = ui.number("Dígitos do número",
                                    value=os_bd.DIGITOS_PADRAO,
                                    min=os_bd.DIGITOS_MINIMO,
                                    max=os_bd.DIGITOS_MAXIMO, step=1)
            num_digitos.props("outlined dense data-testid=os-quadro-digitos")
            num_digitos.tooltip("Quantos dígitos o número tem (3 a 8). "
                                "Mudar depois NÃO renumera o que já existe.")

            chk_unidade = ui.switch("Quadro da unidade (visível para o setor)",
                                    value=False)
            chk_unidade.props("data-testid=os-quadro-unidade")

            try:
                unidades = integracoes.listar_unidades_organograma(ativo=1) or []
            except Exception:
                log.exception("_dialogo_novo_quadro: organograma indisponível")
                unidades = []
            opcoes_unidade = {u["nome"]: u["id"] for u in unidades}
            sel_unidade = ui.select(opcoes_unidade,
                                    label="Unidade (secretaria, setor ou subsetor)")
            sel_unidade.props("outlined dense data-testid=os-quadro-unidade-nome")
            sel_unidade.disable()

            def _alternar(valor):
                """Libera o seletor de unidade junto com a chave."""
                try:
                    if valor:
                        sel_unidade.enable()
                    else:
                        sel_unidade.disable()
                except Exception:
                    log.exception("_alternar falhou")
                    notificar("Erro ao montar o seletor de unidade",
                              type="negative")

            chk_unidade.on_value_change(_alternar)

            lbl_status = ui.label("").classes("text-caption text-grey-6")

            def _criar():
                """Cria o quadro com os dados do formulário."""
                unidade_id = None
                unidade_nome = ""
                if chk_unidade.value:
                    unidade_nome = sel_unidade.value or ""
                    if not unidade_nome:
                        return (False, "Escolha a unidade do quadro.")
                    unidade_id = opcoes_unidade.get(unidade_nome)
                return os_bd.criar_quadro(
                    sessao.user_nome, inp_nome.value or "",
                    descricao=inp_desc.value or "",
                    cor=os_bd._CORES_QUADRO.get(sel_cor.value, CORES["primaria"]),
                    unidade_id=unidade_id, unidade_nome=unidade_nome,
                    visibilidade="unidade" if chk_unidade.value else "privado",
                    pode_criar_unidade=sessao.admin_geral,
                    prefixo_numero=inp_prefixo.value or "",
                    digitos_numero=num_digitos.value or os_bd.DIGITOS_PADRAO)

            btn = botao("Criar quadro", icone="add", chave_modulo=CHAVE) \
                .props("data-testid=os-quadro-salvar")
            with ui.row().classes("w-full justify-end items-center") \
                    .style("gap: 0.5rem"):
                ui.button("Cancelar", on_click=dlg.close).props("flat no-caps")
                btn.on("click", lambda: _gravar(btn, lbl_status, _criar,
                                                fechar=dlg.close,
                                                ao_sucesso=sessao.voltar))
        dlg.open()
    except Exception:
        log.exception("_dialogo_novo_quadro falhou")
        notificar("Erro ao abrir o formulário de novo quadro.", type="negative")


# ============ quadro aberto ============

def _desenhar_quadro(sessao):
    """Quadro aberto: colunas lado a lado, com os cartões dentro."""
    try:
        quadro_id = sessao.quadro_aberto
        quadro = os_bd.obter_quadro(quadro_id)
        if not quadro:
            sessao.quadro_aberto = None
            ui.label("Quadro não encontrado.").classes("text-body2 text-grey-7")
            return
        papel = sessao.papel(quadro_id)
        colunas = os_bd.listar_colunas(quadro_id)
        pode_editar = papel in ("dono", "administrador", "editor")
        pode_gerenciar = papel in ("dono", "administrador")

        with ui.row().classes("w-full items-center justify-between flex-wrap") \
                .style("gap: 0.5rem"):
            botao("Voltar aos quadros", icone="arrow_back", variante="secundario",
                  chave_modulo=CHAVE,
                  on_click=sessao.voltar).props("data-testid=os-voltar")
            with ui.row().classes("items-center flex-wrap").style("gap: 0.5rem"):
                ui.label(quadro["nome"]).classes("text-h6")
                _rotulo_visibilidade(quadro)
                ui.label(f"Você está como: {PAPEIS_ROTULO.get(papel, papel or '—')}") \
                    .classes("text-caption text-grey-6")
        if pode_gerenciar:
            with ui.row().classes("w-full flex-wrap").style("gap: 0.5rem"):
                botao("Colunas", icone="view_column", variante="secundario",
                      chave_modulo=CHAVE,
                      on_click=lambda: _dialogo_colunas(sessao)) \
                    .props("data-testid=os-colunas")
                botao("Convites", icone="person_add", variante="secundario",
                      chave_modulo=CHAVE,
                      on_click=lambda: _dialogo_convites(sessao)) \
                    .props("data-testid=os-convites")
                botao("Ajustes do quadro", icone="settings", variante="secundario",
                      chave_modulo=CHAVE,
                      on_click=lambda: _dialogo_ajustes(sessao)) \
                    .props("data-testid=os-ajustes")
        if not colunas:
            ui.label("Este quadro não tem colunas.").classes("text-body2 text-grey-7")
            return
        with ui.row().classes("w-full items-start").style(
                "gap: 1rem; overflow-x: auto; padding-bottom: 0.5rem"):
            for indice, coluna in enumerate(colunas):
                _coluna_ui(sessao, quadro, coluna, colunas, indice, pode_editar)
    except Exception:
        log.exception("_desenhar_quadro falhou")
        notificar("Erro ao abrir o quadro.", type="negative")


def _coluna_ui(sessao, quadro, coluna, colunas, indice, pode_editar):
    """Uma coluna do quadro com os cartões dentro."""
    try:
        cartoes = os_bd.listar_ordens(quadro["id"], coluna_id=coluna["id"])
        with ui.card().classes("w-72 min-w-72").style("min-width: 0") \
                .props(f"data-testid=os-coluna-{coluna['id']}"):
            with ui.row().classes("w-full items-center justify-between flex-wrap") \
                    .style("gap: 0.25rem"):
                ui.label(f"{coluna['nome']} ({len(cartoes)})") \
                    .classes("text-subtitle2 font-bold").style("min-width: 0")
                if coluna.get("conclusiva"):
                    ui.badge("Conclusão", color="green-7").props("rounded")
            ui.separator()
            with ui.column().classes("w-full gap-2").style("min-width: 0"):
                if not cartoes:
                    ui.label("Vazio.").classes("text-caption text-grey-5 italic")
                for cartao in cartoes:
                    _cartao_os_ui(sessao, quadro, cartao, colunas, indice,
                                  pode_editar)
            if pode_editar:
                botao("Nova ordem de serviço", icone="add", variante="secundario",
                      chave_modulo=CHAVE,
                      on_click=lambda c=coluna: _dialogo_nova_ordem(sessao, quadro, c)) \
                    .classes("w-full") \
                    .props(f"data-testid=os-nova-ordem-coluna-{coluna['id']}")
    except Exception:
        log.exception(f"_coluna_ui({coluna.get('id')}) falhou")
        notificar("Erro ao desenhar uma coluna.", type="negative")


def _cartao_os_ui(sessao, quadro, cartao, colunas, indice_coluna, pode_editar):
    """O cartão: número copiável, título, responsável, prazo e ações de mover."""
    try:
        with ui.card().classes("w-full").style("min-width: 0") \
                .props(f"data-testid=os-cartao-{cartao['numero']}"):
            with ui.column().classes("w-full gap-1").style("min-width: 0"):
                with ui.row().classes("w-full items-center justify-between flex-wrap") \
                        .style("gap: 0.5rem"):
                    # o NÚMERO é clicável: é o que o servidor dita ao chamador
                    ui.label(cartao["numero"]).classes("text-caption font-bold") \
                        .props(f"data-testid=os-numero-{cartao['numero']}") \
                        .style("cursor: pointer") \
                        .on("click", lambda _e, n=cartao["numero"]:
                             _copiar_texto(n, "Número"))
                    ui.badge(PRIORIDADES.get(cartao["prioridade"],
                                              cartao["prioridade"]),
                             color=CORES_PRIORIDADE.get(cartao["prioridade"],
                                                         "grey-7")).props("rounded")
                ui.label(cartao["titulo"]).classes("text-body2 font-medium") \
                    .style("min-width: 0; word-break: break-word")
                if cartao.get("descricao"):
                    ui.label(cartao["descricao"][:90]) \
                        .classes("text-caption text-grey-6") \
                        .style("word-break: break-word")
                if cartao.get("rotulos"):
                    ui.label(f"Rótulos: {cartao['rotulos']}") \
                        .classes("text-caption text-grey-6")
                with ui.row().classes("w-full items-center flex-wrap") \
                        .style("gap: 0.5rem; min-width: 0"):
                    resp = cartao.get("responsavel_user_nome") or "sem responsável"
                    ui.label(f"Resp.: {resp}").classes("text-caption text-grey-6") \
                        .style("min-width: 0; word-break: break-all")
                    if cartao.get("data_vencimento"):
                        estilo = "text-caption text-red-8 font-bold" \
                            if cartao.get("atrasada") else "text-caption text-grey-6"
                        ui.label(f"Prazo: {_prazo_curto(cartao['data_vencimento'])}") \
                            .classes(estilo)
                if cartao.get("concluido_em"):
                    ui.label("Concluída em "
                             + _prazo_curto(cartao["concluido_em"])) \
                        .classes("text-caption text-green-8")
                with ui.row().classes("w-full items-center justify-between flex-wrap") \
                        .style("gap: 0.25rem"):
                    botao_icone("open_in_new", chave_modulo=CHAVE,
                                tooltip="Abrir a ordem de serviço",
                                on_click=lambda c=cartao: _dialogo_detalhe(
                                    sessao, quadro, c))
                    if pode_editar:
                        with ui.row().style("gap: 0.25rem"):
                            botao_icone("arrow_upward", chave_modulo=CHAVE,
                                        tooltip="Subir na coluna",
                                        on_click=lambda c=cartao, i=indice_coluna:
                                        _mover_na_coluna(sessao, c, colunas, i, -1))
                            botao_icone("arrow_downward", chave_modulo=CHAVE,
                                        tooltip="Descer na coluna",
                                        on_click=lambda c=cartao, i=indice_coluna:
                                        _mover_na_coluna(sessao, c, colunas, i, 1))
                            if _existe_vizinha(colunas, indice_coluna - 1):
                                botao_icone("chevron_left", chave_modulo=CHAVE,
                                            tooltip="Mover para a coluna anterior",
                                            on_click=lambda c=cartao,
                                            i=indice_coluna:
                                            _mover_de_coluna(sessao, c, colunas, i, -1))
                            if _existe_vizinha(colunas, indice_coluna + 1):
                                botao_icone("chevron_right", chave_modulo=CHAVE,
                                            tooltip="Mover para a próxima coluna",
                                            on_click=lambda c=cartao,
                                            i=indice_coluna:
                                            _mover_de_coluna(sessao, c, colunas, i, 1))
    except Exception:
        log.exception(f"_cartao_os_ui({cartao.get('numero')}) falhou")
        notificar("Erro ao desenhar um cartão.", type="negative")


def _existe_vizinha(colunas, indice):
    """Verdadeiro quando o índice vizinho existe."""
    try:
        return 0 <= indice < len(colunas)
    except Exception:
        return False


def _mover_na_coluna(sessao, cartao, colunas, indice, passo):
    """Sobe ou desce o cartão dentro da MESMA coluna (troca de inteiros)."""
    try:
        alvo = indice + passo
        if not _existe_vizinha(colunas, alvo):
            return
        os_bd.mover_ordem(cartao["id"], cartao["coluna_id"], posicao=alvo + 1,
                          ator=sessao.user_nome, eh_admin_geral=sessao.admin_geral)
        sessao.recarregar()
    except Exception:
        log.exception("_mover_na_coluna falhou")
        notificar("Erro ao mover o cartão.", type="negative")


def _mover_de_coluna(sessao, cartao, colunas, indice, passo):
    """Move o cartão para a coluna vizinha (concluir é chegar na última)."""
    try:
        alvo = indice + passo
        if not _existe_vizinha(colunas, alvo):
            return
        ok, msg = os_bd.mover_ordem(cartao["id"], colunas[alvo]["id"],
                                    ator=sessao.user_nome,
                                    eh_admin_geral=sessao.admin_geral)
        notificar(msg, type="positive" if ok else "negative")
        sessao.recarregar()
    except Exception:
        log.exception("_mover_de_coluna falhou")
        notificar("Erro ao mudar o cartão de coluna.", type="negative")


# ============ criar ordem de serviço ============

def _dialogo_nova_ordem(sessao, quadro, coluna):
    """Formulário de nova ordem de serviço na coluna."""
    try:
        with ui.dialog() as dlg, ui.card().classes("w-[620px] max-h-[90vh]"):
            ui.label(f"Nova ordem de serviço — {coluna['nome']}") \
                .classes("text-h6")
            ui.separator()
            proximo = os_bd.proximo_numero(quadro["id"]) + 1
            ui.label("Número: "
                     + os_bd.montar_numero(quadro["prefixo_numero"], proximo,
                                           quadro["digitos_numero"])) \
                .classes("text-caption text-grey-6")
            inp_titulo = ui.input("Título da ordem de serviço",
                                  placeholder="Ex.: Trocar lâmpada do galpão")
            inp_titulo.props("outlined dense data-testid=os-ordem-titulo")
            inp_desc = ui.textarea("Descrição", placeholder="O que precisa ser feito")
            inp_desc.props("outlined dense rows=3 data-testid=os-ordem-descricao")
            sel_prio = ui.select(PRIORIDADES, label="Prioridade", value="media")
            sel_prio.props("outlined dense data-testid=os-ordem-prioridade")
            responsaveis = os_bd.responsaveis_do_quadro(quadro["id"],
                                                        sessao.admin_geral)
            opcoes_resp = {"(sem responsável)": ""}
            for pessoa in responsaveis:
                rotulo = pessoa.get("nome_exibicao") or pessoa.get("user_nome")
                if pessoa.get("unidade"):
                    rotulo = f"{rotulo} — {pessoa['unidade']}"
                opcoes_resp[rotulo] = pessoa["user_nome"]
            sel_resp = ui.select(opcoes_resp, label="Responsável")
            sel_resp.props("outlined dense data-testid=os-ordem-responsavel")
            inp_rotulos = ui.input("Rótulos", placeholder="Ex.: elétrica, galpão")
            inp_rotulos.props("outlined dense data-testid=os-ordem-rotulos")
            inp_prazo = ui.date("Prazo (até quando)")
            inp_prazo.props("outlined dense data-testid=os-ordem-prazo")
            inp_prazo.set_value(_data_sugerida())
            lbl_status = ui.label("").classes("text-caption text-grey-6")

            def _criar():
                """Cria o cartão e devolve o número gerado."""
                return os_bd.criar_ordem_servico(
                    quadro["id"], coluna["id"], inp_titulo.value or "",
                    descricao=inp_desc.value or "",
                    prioridade=sel_prio.value or "media",
                    responsavel_user_nome=sel_resp.value or "",
                    rotulos=inp_rotulos.value or "",
                    data_vencimento=_para_data_bruta(inp_prazo.value),
                    ator=sessao.user_nome, eh_admin_geral=sessao.admin_geral)

            btn = botao("Criar ordem de serviço", icone="add", chave_modulo=CHAVE) \
                .props("data-testid=os-ordem-salvar")
            with ui.row().classes("w-full justify-end items-center") \
                    .style("gap: 0.5rem"):
                ui.button("Cancelar", on_click=dlg.close).props("flat no-caps")
                btn.on("click", lambda: _gravar(btn, lbl_status, _criar,
                                                fechar=dlg.close,
                                                ao_sucesso=sessao.recarregar))
        dlg.open()
    except Exception:
        log.exception("_dialogo_nova_ordem falhou")
        notificar("Erro ao abrir o formulário de nova ordem de serviço.",
                  type="negative")


# ============ detalhe da ordem de serviço ============

def _dialogo_detalhe(sessao, quadro, cartao):
    """Detalhe: edição, linha do tempo e comentários da ordem de serviço."""
    try:
        admin_geral = sessao.admin_geral
        pode_editar = sessao.papel(quadro["id"]) in ("dono", "administrador", "editor")
        with ui.dialog() as dlg, ui.card().classes("w-[720px] max-h-[90vh]"):
            with ui.row().classes("w-full items-center justify-between flex-wrap") \
                    .style("gap: 0.5rem"):
                ui.label(cartao["numero"]).classes("text-h6") \
                    .props(f"data-testid=os-detalhe-numero-{cartao['numero']}")
                ui.button("Fechar", on_click=dlg.close).props("flat no-caps")
            ui.label(f"{quadro['nome']} · coluna {cartao.get('coluna_nome') or '—'}"
                     f" · criada em {_prazo_curto(cartao['criado_em'])}"
                     f" por {cartao.get('criado_por') or '—'}") \
                .classes("text-caption text-grey-6")
            ui.separator()

            if pode_editar:
                inp_titulo = ui.input("Título", value=cartao["titulo"])
                inp_titulo.props("outlined dense data-testid=os-detalhe-titulo")
                inp_desc = ui.textarea("Descrição", value=cartao["descricao"])
                inp_desc.props("outlined dense rows=3 data-testid=os-detalhe-descricao")
                sel_prio = ui.select(PRIORIDADES, label="Prioridade",
                                     value=cartao["prioridade"])
                sel_prio.props("outlined dense data-testid=os-detalhe-prioridade")
                opcoes_resp = {"(sem responsável)": ""}
                for pessoa in os_bd.responsaveis_do_quadro(quadro["id"], admin_geral):
                    rotulo = pessoa.get("nome_exibicao") or pessoa.get("user_nome")
                    opcoes_resp[rotulo] = pessoa["user_nome"]
                sel_resp = ui.select(opcoes_resp, label="Responsável",
                                     value=cartao.get("responsavel_user_nome") or "")
                sel_resp.props("outlined dense data-testid=os-detalhe-responsavel")
                inp_rotulos = ui.input("Rótulos", value=cartao.get("rotulos") or "")
                inp_rotulos.props("outlined dense data-testid=os-detalhe-rotulos")
                inp_prazo = ui.date("Prazo",
                                    value=cartao.get("data_vencimento") or None)
                inp_prazo.props("outlined dense data-testid=os-detalhe-prazo")
                lbl_status = ui.label("").classes("text-caption text-grey-6")

                def _salvar():
                    """Grava a edição (cada mudança vira evento)."""
                    return os_bd.atualizar_ordem(
                        cartao["id"],
                        {"titulo": inp_titulo.value or "",
                         "descricao": inp_desc.value or "",
                         "prioridade": sel_prio.value or "media",
                         "responsavel_user_nome": sel_resp.value or "",
                         "rotulos": inp_rotulos.value or "",
                         "data_vencimento": _para_data_bruta(inp_prazo.value)},
                        ator=sessao.user_nome, eh_admin_geral=admin_geral)

                btn_salvar = botao("Salvar", icone="save", chave_modulo=CHAVE) \
                    .props("data-testid=os-detalhe-salvar")
                with ui.row().classes("w-full justify-between items-center flex-wrap") \
                        .style("gap: 0.5rem"):
                    botao("Arquivar ordem" if not cartao.get("arquivado")
                          else "Restaurar ordem",
                          icone="inventory_2", variante="perigo", chave_modulo=CHAVE,
                          on_click=lambda: _gravar(
                              None, lbl_status,
                              lambda: os_bd.arquivar_ordem(
                                  cartao["id"],
                                  arquivar=not cartao.get("arquivado"),
                                  ator=sessao.user_nome,
                                  eh_admin_geral=admin_geral),
                              ao_sucesso=lambda: (dlg.close(), sessao.recarregar()))) \
                        .props("data-testid=os-detalhe-arquivar")
                    with ui.row().classes("items-center").style("gap: 0.5rem"):
                        lbl_status
                        btn_salvar.on("click", lambda: _gravar(
                            btn_salvar, lbl_status, _salvar,
                            ao_sucesso=sessao.recarregar))
            else:
                ui.label(cartao["titulo"]).classes("text-subtitle1 font-bold")
                if cartao.get("descricao"):
                    ui.label(cartao["descricao"]).classes("text-body2")
                ui.label("Seu papel neste quadro é de leitura.") \
                    .classes("text-caption text-grey-6")

            ui.separator()
            _desenhar_comentarios(sessao, cartao, pode_editar)
            ui.separator()
            _desenhar_linha_tempo(cartao["id"])
        dlg.open()
    except Exception:
        log.exception(f"_dialogo_detalhe({cartao.get('numero')}) falhou")
        notificar("Erro ao abrir a ordem de serviço.", type="negative")


def _desenhar_comentarios(sessao, cartao, pode_editar):
    """Comentários da ordem de serviço + campo para escrever."""
    try:
        ui.label("Comentários").classes("text-subtitle2 font-bold")
        for comentario in os_bd.listar_comentarios(cartao["id"]):
            with ui.column().classes("w-full gap-0").style("min-width: 0"):
                ui.label(f"{comentario['autor_user_nome']} · "
                         f"{_prazo_curto(comentario['criado_em'])}") \
                    .classes("text-caption text-grey-6")
                ui.label(comentario["texto"]).classes("text-body2") \
                    .style("word-break: break-word")
        if not pode_editar:
            return
        inp = ui.textarea("Escrever comentário", placeholder="O que aconteceu?")
        inp.props("outlined dense rows=2 data-testid=os-comentario")
        lbl_status = ui.label("").classes("text-caption text-grey-6")
        btn = botao("Comentar", icone="comment", chave_modulo=CHAVE) \
            .props("data-testid=os-comentario-enviar")
        with ui.row().classes("w-full justify-end items-center").style("gap: 0.5rem"):
            lbl_status
            btn.on("click", lambda: _gravar(
                btn, lbl_status,
                lambda: os_bd.comentar_ordem(cartao["id"], inp.value or "",
                                             ator=sessao.user_nome),
                ao_sucesso=lambda: inp.set_value("")))
    except Exception:
        log.exception("_desenhar_comentarios falhou")
        notificar("Erro ao carregar os comentários.", type="negative")


ROTULOS_EVENTO = {
    "criacao": "Criação", "edicao": "Edição", "movimento": "Movimento",
    "responsavel": "Responsável", "prioridade": "Prioridade",
    "comentario": "Comentário", "arquivamento": "Arquivamento",
    "conclusao": "Conclusão", "reabertura": "Reabertura",
}


def _desenhar_linha_tempo(ordem_id):
    """A linha do tempo da ordem de serviço — quem fez o quê, e quando."""
    try:
        ui.label("Linha do tempo").classes("text-subtitle2 font-bold")
        eventos = os_bd.listar_eventos(ordem_id)
        if not eventos:
            ui.label("Sem eventos ainda.").classes("text-caption text-grey-5 italic")
            return
        with ui.column().classes("w-full gap-1").style("min-width: 0"):
            for evento in eventos:
                rotulo = ROTULOS_EVENTO.get(evento["tipo"], evento["tipo"])
                with ui.row().classes("w-full items-start flex-wrap") \
                        .style("gap: 0.5rem; min-width: 0"):
                    ui.badge(rotulo, color="blue-grey-6").props("rounded")
                    ui.label(f"{_prazo_curto(evento['criado_em'])} · "
                             f"{evento['autor_user_nome'] or 'sistema'}") \
                        .classes("text-caption text-grey-6") \
                        .style("min-width: 0")
                ui.label(evento["texto"]).classes("text-body2") \
                    .style("min-width: 0; word-break: break-word")
    except Exception:
        log.exception("_desenhar_linha_tempo falhou")
        notificar("Erro ao carregar a linha do tempo.", type="negative")


# ============ colunas, convites e ajustes ============

def _dialogo_colunas(sessao):
    """Gerência das colunas: criar, renomear, reordenar e excluir."""
    try:
        with ui.dialog() as dlg, ui.card().classes("w-[640px] max-h-[90vh]"):
            ui.label("Colunas do quadro").classes("text-h6")
            ui.separator()

            @ui.refreshable
            def colunas():
                """Lista as colunas na ordem, com os botões de ação."""
                try:
                    itens = os_bd.listar_colunas(sessao.quadro_aberto)
                except Exception:
                    log.exception("lista de colunas falhou")
                    notificar("Erro ao carregar as colunas.", type="negative")
                    return
                for indice, coluna in enumerate(itens):
                    with ui.row().classes("w-full items-center flex-wrap") \
                            .style("gap: 0.5rem; min-width: 0"):
                        ui.label(f"{indice + 1}. {coluna['nome']}"
                                 + ("  (conclusão)" if coluna.get("conclusiva") else "")) \
                            .classes("text-body2").style("min-width: 0; flex: 1")
                        botao_icone("edit", chave_modulo=CHAVE,
                                    tooltip="Renomear",
                                    on_click=lambda c=coluna: _renomear_coluna(
                                        sessao, c, colunas))
                        if _existe_vizinha(itens, indice - 1):
                            botao_icone("arrow_upward", chave_modulo=CHAVE,
                                        tooltip="Mover para a esquerda",
                                        on_click=lambda c=coluna, i=indice:
                                        _reordenar_colunas(sessao, itens, i, -1,
                                                            colunas))
                        if _existe_vizinha(itens, indice + 1):
                            botao_icone("arrow_downward", chave_modulo=CHAVE,
                                        tooltip="Mover para a direita",
                                        on_click=lambda c=coluna, i=indice:
                                        _reordenar_colunas(sessao, itens, i, 1,
                                                            colunas))
                        botao_icone("delete", variante="perigo", chave_modulo=CHAVE,
                                    tooltip="Excluir coluna",
                                    on_click=lambda c=coluna: _excluir_coluna(
                                        sessao, c, colunas))

            colunas()
            ui.separator()
            inp_nova = ui.input("Nome da nova coluna",
                                placeholder="Ex.: Aguardando material")
            inp_nova.props("outlined dense data-testid=os-coluna-nova")
            lbl_status = ui.label("").classes("text-caption text-grey-6")
            btn = botao("Criar coluna", icone="add", chave_modulo=CHAVE) \
                .props("data-testid=os-coluna-criar")
            with ui.row().classes("w-full justify-end items-center") \
                    .style("gap: 0.5rem"):
                lbl_status
                btn.on("click", lambda: _gravar(
                    btn, lbl_status,
                    lambda: os_bd.criar_coluna(sessao.quadro_aberto,
                                               inp_nova.value or "",
                                               ator=sessao.user_nome,
                                               eh_admin_geral=sessao.admin_geral),
                    ao_sucesso=lambda: (inp_nova.set_value(""), colunas.refresh(),
                                        sessao.recarregar())))
            ui.button("Fechar", on_click=dlg.close).props("flat no-caps")
        dlg.open()
    except Exception:
        log.exception("_dialogo_colunas falhou")
        notificar("Erro ao abrir as colunas do quadro.", type="negative")


def _renomear_coluna(sessao, coluna, refrescar):
    """Renomeia uma coluna pelo prompt do navegador (sem diálogo aninhado)."""
    try:
        ui.dialog()  # mantém o contexto de UI estável quando o chamador usa prompt
    except Exception:
        pass
    try:
        _prompt_texto(sessao, coluna, refrescar)
    except Exception:
        log.exception("_renomear_coluna falhou")
        notificar("Erro ao renomear a coluna.", type="negative")


def _prompt_texto(sessao, coluna, refrescar):
    """Pede o novo nome da coluna em um diálogo próprio."""
    try:
        with ui.dialog() as dlg, ui.card().classes("w-[420px]"):
            ui.label("Renomear coluna").classes("text-subtitle1 font-bold")
            inp = ui.input("Novo nome", value=coluna["nome"])
            inp.props("outlined dense data-testid=os-coluna-novo-nome")
            lbl_status = ui.label("").classes("text-caption text-grey-6")
            btn = botao("Salvar", icone="save", chave_modulo=CHAVE)
            with ui.row().classes("w-full justify-end items-center") \
                    .style("gap: 0.5rem"):
                ui.button("Cancelar", on_click=dlg.close).props("flat no-caps")
                btn.on("click", lambda: _gravar(
                    btn, lbl_status,
                    lambda: os_bd.renomear_coluna(coluna["id"], inp.value or "",
                                                   ator=sessao.user_nome,
                                                   eh_admin_geral=sessao.admin_geral),
                    fechar=dlg.close,
                    ao_sucesso=lambda: (refrescar.refresh(), sessao.recarregar())))
        dlg.open()
    except Exception:
        log.exception("_prompt_texto falhou")
        notificar("Erro ao abrir a renomeação.", type="negative")


def _reordenar_colunas(sessao, colunas, indice, passo, refrescar):
    """Troca a coluna de lugar (a de conclusão sempre fica por último)."""
    try:
        alvo = indice + passo
        if not _existe_vizinha(colunas, alvo):
            return
        ordem = [c["id"] for c in colunas]
        ordem[indice], ordem[alvo] = ordem[alvo], ordem[indice]
        ok, msg = os_bd.mover_coluna(sessao.quadro_aberto, ordem,
                                    ator=sessao.user_nome,
                                    eh_admin_geral=sessao.admin_geral)
        notificar(msg, type="positive" if ok else "negative")
        refrescar.refresh()
        sessao.recarregar()
    except Exception:
        log.exception("_reordenar_colunas falhou")
        notificar("Erro ao reordenar as colunas.", type="negative")


def _excluir_coluna(sessao, coluna, refrescar):
    """Exclui a coluna (recusa se houver ordem de serviço dentro)."""
    try:
        ok, msg = os_bd.excluir_coluna(coluna["id"], ator=sessao.user_nome,
                                       eh_admin_geral=sessao.admin_geral)
        notificar(msg, type="positive" if ok else "negative")
        refrescar.refresh()
        sessao.recarregar()
    except Exception:
        log.exception("_excluir_coluna falhou")
        notificar("Erro ao excluir a coluna.", type="negative")


def _dialogo_convites(sessao):
    """Convida servidores cadastrados e mostra quem já participa."""
    try:
        with ui.dialog() as dlg, ui.card().classes("w-[680px] max-h-[90vh]"):
            ui.label("Quem participa deste quadro").classes("text-h6")
            ui.separator()
            with ui.column().classes("w-full gap-2").style("min-width: 0"):

                @ui.refreshable
                def participantes():
                    """Convites do quadro, com o estado de cada um."""
                    try:
                        itens = os_bd.listar_convites_quadro(sessao.quadro_aberto)
                    except Exception:
                        log.exception("lista de convites falhou")
                        notificar("Erro ao carregar os convites.", type="negative")
                        return
                    if not itens:
                        ui.label("Ninguém convidado ainda.") \
                            .classes("text-caption text-grey-5 italic")
                        return
                    for convite in itens:
                        with ui.row().classes(
                                "w-full items-center justify-between flex-wrap") \
                                .style("gap: 0.5rem; min-width: 0"):
                            nome = convite.get("nome_exibicao") \
                                or convite.get("convidado_user_nome")
                            if convite.get("unidade"):
                                nome = f"{nome} — {convite['unidade']}"
                            with ui.column().classes("gap-0").style("min-width: 0"):
                                ui.label(nome).classes("text-body2") \
                                    .style("word-break: break-word")
                                ui.label(f"{PAPEIS_ROTULO.get(convite['papel'], convite['papel'])}"
                                         f" · {convite['status']}") \
                                    .classes("text-caption text-grey-6")
                            if convite["status"] in ("pendente", "aceito"):
                                botao_icone("person_remove", variante="perigo",
                                            chave_modulo=CHAVE,
                                            tooltip="Cancelar a participação",
                                            on_click=lambda c=convite:
                                            _cancelar_convite(sessao, c,
                                                               participantes))

                participantes()
                ui.separator()
                inp_busca = ui.input("Buscar servidor", placeholder="Nome ou matrícula")
                inp_busca.props("outlined dense data-testid=os-convite-busca")

                @ui.refreshable
                def candidatos():
                    """Servidores do cadastro que batem com a busca."""
                    termo = (inp_busca.value or "").strip()
                    if not termo:
                        ui.label("Digite o nome do servidor para convidar.") \
                            .classes("text-caption text-grey-6")
                        return
                    try:
                        achados = integracoes.buscar_usuarios_gestao(
                            termo=termo, limite=20) or []
                    except Exception:
                        log.exception("busca de candidatos falhou")
                        notificar("Erro ao buscar servidores.", type="negative")
                        return
                    if not achados:
                        ui.label("Nenhum servidor encontrado.") \
                            .classes("text-caption text-grey-6")
                        return
                    for achado in achados:
                        with ui.row().classes("w-full items-center flex-wrap") \
                                .style("gap: 0.5rem; min-width: 0"):
                            rotulo = achado.get("nome_exibicao") \
                                or achado.get("user_nome")
                            if achado.get("unidade") or achado.get("lotacao"):
                                rotulo = f"{rotulo} — " \
                                    f"{achado.get('lotacao') or achado.get('unidade')}"
                            ui.label(rotulo).classes("text-body2").style("flex: 1")
                            sel = ui.select(PAPEIS_ROTULO, label="Papel",
                                            value="editor").classes("w-40")
                            sel.props("outlined dense data-testid=os-convite-papel")
                            botao("Convidar", icone="person_add", variante="secundario",
                                  chave_modulo=CHAVE,
                                  on_click=lambda a=achado, s=sel: _convidar(
                                      sessao, a.get("user_nome"), s.value, dlg,
                                      participantes, candidatos)) \
                                .props("data-testid=os-convite-enviar")

                inp_busca.on_value_change(lambda _v: candidatos.refresh())
                candidatos()
            ui.button("Fechar", on_click=dlg.close).props("flat no-caps")
        dlg.open()
    except Exception:
        log.exception("_dialogo_convites falhou")
        notificar("Erro ao abrir os convites do quadro.", type="negative")


def _convidar(sessao, login, papel, dlg, refrescar_convites, refrescar_candidatos):
    """Envia o convite e devolve (ok, mensagem) para o botão padrão."""
    try:
        return os_bd.convidar_usuario(sessao.quadro_aberto, login,
                                      next((p for p, r in PAPEIS_ROTULO.items()
                                            if r == papel), "editor"),
                                      ator=sessao.user_nome,
                                      eh_admin_geral=sessao.admin_geral)
    except Exception:
        log.exception("_convidar falhou")
        return (False, "Erro ao convidar o servidor.")


def _cancelar_convite(sessao, convite, refrescar):
    """Cancela o convite pendente (ou remove a participação)."""
    try:
        ok, msg = os_bd.cancelar_convite(convite["id"], ator=sessao.user_nome,
                                         eh_admin_geral=sessao.admin_geral)
        notificar(msg, type="positive" if ok else "negative")
        refrescar.refresh()
    except Exception:
        log.exception("_cancelar_convite falhou")
        notificar("Erro ao cancelar o convite.", type="negative")


def _dialogo_ajustes(sessao):
    """Nome, descrição, cor, unidade e formato do número do quadro."""
    try:
        quadro = os_bd.obter_quadro(sessao.quadro_aberto)
        if not quadro:
            notificar("Quadro não encontrado.", type="negative")
            return
        with ui.dialog() as dlg, ui.card().classes("w-[620px] max-h-[90vh]"):
            ui.label("Ajustes do quadro").classes("text-h6")
            ui.separator()
            inp_nome = ui.input("Nome do quadro", value=quadro["nome"])
            inp_nome.props("outlined dense data-testid=os-ajuste-nome")
            inp_desc = ui.textarea("Descrição", value=quadro["descricao"])
            inp_desc.props("outlined dense rows=2 data-testid=os-ajuste-descricao")
            sel_cor = ui.select(dict(os_bd._CORES_QUADRO), label="Cor",
                                value=quadro.get("cor") or CORES["primaria"])
            sel_cor.props("outlined dense data-testid=os-ajuste-cor")

            try:
                unidades = integracoes.listar_unidades_organograma(ativo=1) or []
            except Exception:
                log.exception("_dialogo_ajustes: organograma indisponível")
                unidades = []
            opcoes = {"(quadro privado)": ""}
            opcoes.update({u["nome"]: u["id"] for u in unidades})
            sel_unidade = ui.select(opcoes, label="Unidade do quadro",
                                    value=quadro.get("unidade_nome") or "")
            sel_unidade.props("outlined dense data-testid=os-ajuste-unidade")
            sel_unidade.tooltip("Escolher uma unidade torna o quadro visível "
                                "para todos os servidores dela.")

            inp_prefixo = ui.input("Prefixo do número",
                                   value=quadro.get("prefixo_numero") or "")
            inp_prefixo.props("outlined dense maxlength=12 "
                              "data-testid=os-ajuste-prefixo")
            num_digitos = ui.number("Dígitos do número",
                                    value=quadro.get("digitos_numero")
                                    or os_bd.DIGITOS_PADRAO,
                                    min=os_bd.DIGITOS_MINIMO,
                                    max=os_bd.DIGITOS_MAXIMO, step=1)
            num_digitos.props("outlined dense data-testid=os-ajuste-digitos")
            ui.label("Mudar o formato NÃO renumera as ordens de serviço já "
                     "criadas: o número guardado é o histórico.").classes(
                "text-caption text-grey-6")
            lbl_status = ui.label("").classes("text-caption text-grey-6")

            def _salvar():
                """Grava os ajustes (inclusive o formato do número)."""
                nome_unidade = sel_unidade.value or ""
                return os_bd.atualizar_quadro(
                    sessao.quadro_aberto,
                    {"nome": inp_nome.value or "",
                     "descricao": inp_desc.value or "",
                     "cor": sel_cor.value or CORES["primaria"],
                     "unidade_nome": nome_unidade,
                     "unidade_id": opcoes.get(nome_unidade),
                     "visibilidade": "unidade" if nome_unidade else "privado",
                     "prefixo_numero": inp_prefixo.value or "",
                     "digitos_numero": num_digitos.value or os_bd.DIGITOS_PADRAO},
                    ator=sessao.user_nome, eh_admin_geral=sessao.admin_geral)

            btn = botao("Salvar ajustes", icone="save", chave_modulo=CHAVE) \
                .props("data-testid=os-ajuste-salvar")
            with ui.row().classes("w-full justify-end items-center") \
                    .style("gap: 0.5rem"):
                ui.button("Cancelar", on_click=dlg.close).props("flat no-caps")
                btn.on("click", lambda: _gravar(btn, lbl_status, _salvar,
                                                fechar=dlg.close,
                                                ao_sucesso=sessao.recarregar))
        dlg.open()
    except Exception:
        log.exception("_dialogo_ajustes falhou")
        notificar("Erro ao abrir os ajustes do quadro.", type="negative")


# ============ abas de trabalho ============

def _desenhar_convites(sessao):
    """Aba 'Convites': o que está aguardando resposta de quem está logado."""
    try:
        pendentes = os_bd.listar_convites_pendentes(sessao.user_nome)
        if not pendentes:
            ui.label("Você não tem convites pendentes.").classes("text-body2 text-grey-7")
            return
        with ui.column().classes("w-full gap-2").style("min-width: 0"):
            for convite in pendentes:
                with ui.card().classes("w-full").style("min-width: 0"):
                    with ui.row().classes(
                            "w-full items-center justify-between flex-wrap") \
                            .style("gap: 0.5rem; min-width: 0"):
                        with ui.column().classes("gap-0").style("min-width: 0"):
                            ui.label(convite.get("quadro_nome") or "Quadro") \
                                .classes("text-subtitle2 font-bold")
                            ui.label(
                                f"Papel oferecido: "
                                f"{PAPEIS_ROTULO.get(convite['papel'], convite['papel'])}"
                                + (f" · {convite['recado']}" if convite.get("recado") else "")
                            ).classes("text-caption text-grey-6")
                        with ui.row().style("gap: 0.5rem"):
                            botao("Recusar", variante="perigo", chave_modulo=CHAVE,
                                  on_click=lambda c=convite: _responder_convite(
                                      sessao, c, False))
                            botao("Aceitar", icone="check", chave_modulo=CHAVE,
                                  on_click=lambda c=convite: _responder_convite(
                                      sessao, c, True))
    except Exception:
        log.exception("_desenhar_convites falhou")
        notificar("Erro ao carregar os convites.", type="negative")


def _responder_convite(sessao, convite, aceitar):
    """Aceita ou recusa o convite; se aceitar, abre o quadro."""
    try:
        ok, msg, nome_quadro = os_bd.responder_convite(
            convite["id"], sessao.user_nome, aceitar)
        notificar(msg, type="positive" if ok else "negative")
        if ok and aceitar:
            sessao.abrir(convite["quadro_id"])
    except Exception:
        log.exception("_responder_convite falhou")
        notificar("Erro ao responder o convite.", type="negative")


MODOS_MINHAS = {
    "meus": ("Meus cartões", "Nenhuma ordem de serviço sob sua responsabilidade."),
    "atraso": ("Ordens atrasadas", "Nenhuma ordem de serviço atrasada."),
    "sem_responsavel": ("Ordens sem responsável",
                        "Toda ordem de serviço em aberto tem responsável."),
}


def _desenhar_minhas(sessao, modo):
    """Visões de trabalho: meus cartões, atrasadas e sem responsável."""
    try:
        titulo, vazio = MODOS_MINHAS.get(modo, MODOS_MINHAS["meus"])
        if modo == "sem_responsavel":
            itens = []
            for quadro in os_bd.listar_quadros_visiveis(sessao.user_nome,
                                                        sessao.admin_geral):
                for ordem in os_bd.listar_ordens(quadro["id"], nao_concluidas=True):
                    if not (ordem.get("responsavel_user_nome") or ""):
                        itens.append(dict(ordem, quadro_nome=quadro["nome"]))
        else:
            itens = os_bd.listar_minhas_ordens(sessao.user_nome, sessao.admin_geral,
                                               atraso=(modo == "atraso"))
        ui.label(f"{titulo}: {len(itens)}").classes("text-body2 text-grey-7")
        if not itens:
            ui.label(vazio).classes("text-caption text-grey-6")
            return
        with ui.column().classes("w-full gap-2").style("min-width: 0"):
            for ordem in itens:
                _linha_ordem(sessao, ordem)
    except Exception:
        log.exception(f"_desenhar_minhas({modo}) falhou")
        notificar("Erro ao carregar a lista.", type="negative")


def _linha_ordem(sessao, ordem):
    """Uma linha da lista de trabalho: número, título, prazo e responsável."""
    try:
        quadro = os_bd.obter_quadro(ordem["quadro_id"])
        if not quadro:
            return
        with ui.card().classes("w-full").style("min-width: 0") \
                .props(f"data-testid=os-linha-{ordem['numero']}"):
            with ui.row().classes("w-full items-center justify-between flex-wrap") \
                    .style("gap: 0.5rem; min-width: 0"):
                with ui.column().classes("gap-0").style("min-width: 0"):
                    ui.label(ordem["numero"]).classes("text-caption font-bold") \
                        .style("cursor: pointer") \
                        .on("click", lambda _e, n=ordem["numero"]:
                             _copiar_texto(n, "Número"))
                    ui.label(ordem["titulo"]).classes("text-body2 font-medium") \
                        .style("min-width: 0; word-break: break-word")
                    ui.label(f"{quadro['nome']} · {ordem.get('coluna_nome') or '—'}"
                             f" · responsável: "
                             f"{ordem.get('responsavel_user_nome') or 'sem responsável'}") \
                        .classes("text-caption text-grey-6") \
                        .style("min-width: 0; word-break: break-word")
                with ui.row().classes("items-center").style("gap: 0.5rem"):
                    if ordem.get("data_vencimento"):
                        estilo = "text-caption text-red-8 font-bold" \
                            if ordem.get("atrasada") else "text-caption text-grey-6"
                        ui.label("Prazo: " + _prazo_curto(ordem["data_vencimento"])) \
                            .classes(estilo)
                    botao_icone("open_in_new", chave_modulo=CHAVE,
                                tooltip="Abrir a ordem de serviço",
                                on_click=lambda q=quadro, o=ordem: _dialogo_detalhe(
                                    sessao, q, o))
    except Exception:
        log.exception(f"_linha_ordem({ordem.get('numero')}) falhou")
