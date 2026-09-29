"""EN: Administration panel of the Stock module — overview, who operates the
module, the "standing still" threshold and backup.

PT-BR: Painel de administração do módulo de Estoque — visão geral, quem opera
o módulo, o prazo de item parado e backup.

O QUE ESTE PAINEL FAZ, E O QUE NÃO FAZ
    Ele administra o MÓDULO, não o material. Quem opera a secretaria cadastra o
    almoxarifado dela, move o estoque e pede o recolhimento; isto aqui é o que o
    DTI ajusta uma vez para a prefeitura inteira: quem tem acesso, quem
    movimenta, em quantos dias um material parado vira pedido de recolhimento,
    e o backup do banco.

    O que NÃO cabe aqui, e por quê: a lista de todos os itens e de todas as
    transferências de todos os almoxarifados. Um almoxarifado é trabalho em
    andamento, tem responsável, tem saldo; quando o DTI passa a listar o
    material de todo mundo, ele deixa de ser o administrador do módulo e vira o
    fiscal do setor. A visão geral deste painel é NÚMERO (quantos almoxarifados,
    quanto parado, quantos pedidos esperando), e o detalhe fica com quem opera
    o almoxarifado.

USUÁRIOS E UNIDADES
    Servidores e secretarias vêm SEMPRE pela fachada do núcleo
    (`mod_intranet.integracoes`): este módulo não importa a Gestão de Usuários
    nem a Lista Telefônica, e `check_integridade.py` reprova a aresta se ele
    tentar. O nome que aparece para o administrador é o nome de tratamento
    (primeiro + último) com o login entre parênteses — nunca a matrícula sozinha,
    que é o que o técnico precisa para logar, não o que a pessoa precisa ler.
"""

from __future__ import annotations

from nicegui import ui
from mod_intranet import observabilidade
from mod_intranet.tema_modulo import bloco_aparencia, ler_tema, notificar
from mod_intranet.ui_comum import card_admin, rodape_salvar_restaurar
from mod_estoque import bd_manipulador as est_bd

log = observabilidade.get_logger("estoque")

CHAVE = "estoque"
ROTULO = "Estoque"
TEXTO_HEADER = ("Estoque central e almoxarifados das secretarias — entrada, "
                "distribuição, o que está em uso e o que volta.")

# Estado do painel, lido pelas funções de salvar. Vem do chamador para que o log
# de auditoria registre QUEM concedeu, e não "sistema".
usuario_logado_atual = ""

PAPEIS_ROTULO = {
    est_bd.PAPEL_CONSULTA: "Consulta — só vê o estoque",
    est_bd.PAPEL_OPERADOR: "Operador — entrada, transferência, entrega e baixa",
    est_bd.PAPEL_ADMINISTRADOR: "Administrador — cria almoxarifado, item e "
                                "servidor",
}


def _n(rotulo, valor, sufixo="", cor=None):
    """Um número grande de visão geral. `cor=None` usa a cor de texto padrão."""
    classes = "text-h5" + (f" {cor}" if cor else " text-grey-9")
    with ui.column().classes("items-start").style("min-width: 0"):
        ui.label(f"{valor:g}{sufixo}" if isinstance(valor, float) else f"{valor}{sufixo}") \
            .classes(classes)
        ui.label(rotulo).classes("text-caption text-grey-6")


def _card_visao_geral():
    """Os números que dizem se o módulo está servindo a alguém.

    "Parado" é o número que importa: material em uso sem baixa há mais de N
    dias é o que se perde se ninguém recolher. Um painel de módulo que só mostra
    "quantos almoxarifados existem" informa que o sistema está no ar, e não se
    ele está evitando desperdício."""
    try:
        d = est_bd.visao_geral()
        with card_admin("Uso do módulo", icone="insights", chave_modulo=CHAVE,
                        grade=False):
            with ui.row().classes("w-full items-start flex-wrap") \
                    .style("gap: 1.5rem"):
                _n("almoxarifados de secretaria", d.get("almoxarifados", 0))
                _n("itens no catálogo", d.get("itens", 0))
                _n("disponível", d.get("disponivel", 0))
                _n("em uso", d.get("em_uso", 0))
                _n(f"parado ({d.get('dias_parado', 0)}d)", d.get("parado", 0),
                   cor="text-negative" if d.get("parado") else None)
                _n("pedidos de recolhimento", d.get("pedidos", 0),
                   cor="text-orange-8" if d.get("pedidos") else None)
            if d.get("parado"):
                ui.label(
                    f"Há {d['parado']:g} unidade(s) fora do almoxarifado há mais "
                    f"de {d.get('dias_parado', 0)} dias sem baixa. Isso é "
                    f"material que pode se perder — o painel só avisa; quem "
                    f"recolhe é o almoxarifado da secretaria, com o central.").classes(
                    "text-caption text-orange-8")
            else:
                ui.label("Nenhum material parado fora do prazo definido.") \
                    .classes("text-caption text-grey-6")

            por_almoxarifado = d.get("por_almoxarifado") or []
            if por_almoxarifado:
                ui.separator()
                ui.label("Por almoxarifado").classes("text-subtitle2 font-bold")
                with ui.column().classes("w-full gap-1").style("min-width: 0"):
                    for linha in por_almoxarifado:
                        with ui.row().classes("w-full items-center flex-wrap") \
                                .style("gap: 0.75rem; min-width: 0") \
                                .props(f"data-testid=estoque-admin-visao-"
                                       f"{linha['id']}"):
                            ui.label(linha["nome"]).classes(
                                "text-caption font-medium").style(
                                "min-width: 0; word-break: break-word")
                            ui.label(f"recebido {linha['recebido']:g}").classes(
                                "text-caption text-grey-6")
                            ui.label(f"disponível {linha['disponivel']:g}").classes(
                                "text-caption text-grey-6")
                            ui.label(f"em uso {linha['em_uso']:g}").classes(
                                "text-caption text-grey-6")
                            if linha["parado"]:
                                ui.label(f"parado {linha['parado']:g}").classes(
                                    "text-caption text-orange-8 font-bold")
    except Exception as e:
        log.exception(f"estoque admin: visão geral falhou: {e}")
        notificar("Não foi possível ler os números agora.", type="negative")


def _card_servidores():
    """Quem opera o módulo, e com que papel — o vínculo com o cadastro.

    Este módulo NÃO cria usuário: a lista é um vínculo com o login de quem já
    existe. A concessão de acesso ao módulo em si é feita pela fachada do
    núcleo, que é quem escreve no banco do cadastro de usuários."""
    with card_admin("Servidores que operam o módulo",
                    icone="manage_accounts", chave_modulo=CHAVE):
        ui.label("Vincule servidores já cadastrados e escolha o papel de cada "
                 "um. Quem só consulta enxerga o estoque e não movimenta nada; "
                 "quem opera entra, transfere, entrega e dá baixa; quem "
                 "administra cria almoxarifado e item.").classes(
            "text-caption text-grey-6")
        with ui.column().classes("w-full gap-2").style("min-width: 0"):
            inp_busca = ui.input("Buscar servidor", placeholder="nome, nome completo ou login") \
                .props("outlined dense clearable") \
                .props("data-testid=estoque-admin-busca-servidor")
            sel_user = ui.select({}, label="Servidor encontrado") \
                .props("outlined dense clearable") \
                .props("data-testid=estoque-admin-selecionar-servidor")
            sel_papel = ui.select(dict(PAPEIS_ROTULO), label="Papel no módulo",
                                  value=est_bd.PAPEL_CONSULTA) \
                .props("outlined dense") \
                .props("data-testid=estoque-admin-papel")

            def _carregar(termo):
                """Servidores do cadastro, filtrados pelo termo."""
                from mod_intranet import integracoes
                todos = integracoes.listar_usuarios_gestao(filtro_ativo=True) or []
                if not termo:
                    return todos[:20]
                alvo = (termo or "").strip().lower()
                achados = [u for u in todos
                           if alvo in (u[1] or "").lower()
                           or alvo in (u[9] or "").lower()
                           or alvo in (u[4] or "").lower()]
                return achados[:30]

            def _ao_buscar(e=None):
                try:
                    import unicodedata

                    def _norm(t):
                        return unicodedata.normalize(
                            "NFKD", t or "").encode("ascii", "ignore").decode().lower()

                    termo = _norm(getattr(e, "value", "") or "")
                    achados = _carregar(termo)
                    opts = {}
                    for u in achados:
                        nome = (u[9] or "").strip() or u[1]
                        opts[u[1]] = f"{nome} (@{u[1]})"
                    sel_user.set_options(opts)
                    sel_user.update()
                except Exception as ex:
                    log.warning(f"estoque admin: busca de servidor falhou: {ex}")
                    notificar("Não foi possível buscar servidores.", type="negative")

            inp_busca.on_value_change(_ao_buscar)
            try:
                _ao_buscar()
            except Exception:
                pass

            def _salvar():
                try:
                    if not sel_user.value:
                        notificar("Escolha um servidor primeiro.", type="warning")
                        return
                    ok, msg = est_bd.vincular_usuario(
                        sel_user.value, papel=sel_papel.value or est_bd.PAPEL_CONSULTA,
                        ator=usuario_logado_atual)
                    notificar(msg, type="positive" if ok else "negative")
                    if ok:
                        ui.navigate.reload()
                except Exception as e:
                    log.exception(f"estoque admin: vincular servidor falhou: {e}")
                    notificar("Erro ao vincular o servidor.", type="negative")

            def _restaurar():
                try:
                    sel_user.set_options({})
                    sel_user.value = None
                    sel_user.update()
                    sel_papel.value = est_bd.PAPEL_CONSULTA
                    sel_papel.update()
                    notificar("Seleção limpa.", type="warning")
                except Exception as e:
                    log.exception(f"estoque admin: restaurar seleção falhou: {e}")
                    notificar("Erro ao limpar a seleção.", type="negative")

            rodape_salvar_restaurar(_salvar, _restaurar, chave_modulo=CHAVE,
                                    rotulo_salvar="Vincular servidor",
                                    data_testid="estoque-admin-vincular-servidor")

            vinculados = est_bd.listar_usuarios_vinculados()
            ui.separator()
            if not vinculados:
                ui.label("Ninguém vinculado ainda. Sem vínculo, quem tem acesso "
                         "ao módulo por padrão entra como CONSULTA.").classes(
                    "text-caption text-grey-6")
            else:
                with ui.column().classes("w-full gap-1").style("min-width: 0"):
                    for vinculado in vinculados:
                        with ui.row().classes("w-full items-center justify-between flex-wrap") \
                                .style("gap: 0.5rem; min-width: 0") \
                                .props(f"data-testid=estoque-admin-vinculado-"
                                       f"{vinculado['user_nome']}"):
                            with ui.column().classes("gap-0").style("min-width: 0"):
                                ui.label(f"{vinculado['nome_exibicao'] or vinculado['user_nome']} "
                                         f"(@{vinculado['user_nome']})").classes(
                                    "text-caption font-medium").style(
                                    "min-width: 0; word-break: break-word")
                                if vinculado.get("unidade"):
                                    ui.label(vinculado["unidade"]).classes(
                                        "text-caption text-grey-6")
                            with ui.row().classes("items-center flex-wrap") \
                                    .style("gap: 0.5rem"):
                                ui.badge(PAPEIS_ROTULO.get(vinculado["papel"],
                                                           vinculado["papel"]),
                                         color={"administrador": "blue-7",
                                                "operador": "green-7"}.get(
                                                    vinculado["papel"], "grey-6")) \
                                    .props("rounded")
                                ui.button("Retirar", on_click=lambda v=vinculado:
                                          _retirar_vinculo(v)) \
                                    .props("flat no-caps dense") \
                                    .props(f"data-testid=estoque-admin-retirar-"
                                           f"{vinculado['user_nome']}")
            ui.label("O acesso ao MÓDULO (entrar na tela) é concedido em Usuários, "
                     "em Liberações por módulo — de propósito: sair é tão decisão "
                     "do administrador quanto entrar, e fica no mesmo lugar onde as "
                     "outras liberações do sistema são feitas.").classes(
                "text-caption text-grey-6")


def _retirar_vinculo(vinculado):
    """Tira o servidor da lista de quem opera o módulo."""
    try:
        ok, msg = est_bd.remover_vinculo(vinculado["user_nome"],
                                         ator=usuario_logado_atual)
        notificar(msg, type="positive" if ok else "negative")
        if ok:
            ui.navigate.reload()
    except Exception as e:
        log.exception(f"estoque admin: retirar vínculo falhou: {e}")
        notificar("Erro ao retirar o servidor do módulo.", type="negative")


def _card_dias_parado():
    """O PRAZO DO ITEM PARADO — o número que decide o que vira pedido.

    Material entregue a uma sala e sem baixa há mais de N dias aparece como
    "parado" no painel da secretaria. O padrão é 30 dias; quem administra o
    módulo ajusta, e o ajuste vale para todo mundo na hora."""
    with card_admin("Prazo do item parado", icone="hourglass_bottom",
                    chave_modulo=CHAVE):
        ui.label("Material entregue a uma sala e sem baixa há mais de N dias "
                 "conta como PARADO. É esse número que indica desperdício e que "
                 "abre o pedido de recolhimento. Menor prazo = o alerta aparece "
                 "antes; maior prazo = menos falsos positivos.") \
            .classes("text-caption text-grey-6")
        atual = est_bd.dias_parado()
        opcoes = {str(d): f"{d} dias" for d in (7, 15, 20, 30, 45, 60, 90, 120)}
        sel_dias = ui.select(opcoes, label="Dias sem baixa para contar como parado",
                             value=str(atual)) \
            .props("outlined dense") \
            .props("data-testid=estoque-admin-dias-parado")

        def _salvar():
            try:
                ok, msg = est_bd.salvar_dias_parado(sel_dias.value or atual,
                                                    ator=usuario_logado_atual)
                notificar(msg, type="positive" if ok else "negative")
                if ok:
                    ui.navigate.reload()
            except Exception as e:
                log.exception(f"estoque admin: gravar dias parado falhou: {e}")
                notificar("Erro ao gravar o prazo de item parado.", type="negative")

        def _restaurar():
            try:
                sel_dias.value = str(est_bd.DIAS_PARADO_PADRAO)
                sel_dias.update()
                notificar("Voltou ao prazo padrão do módulo. Clique em Salvar "
                          "para gravar no banco.", type="warning")
            except Exception as e:
                log.exception(f"estoque admin: restaurar dias parado falhou: {e}")
                notificar("Erro ao restaurar o prazo.", type="negative")

        rodape_salvar_restaurar(_salvar, _restaurar, chave_modulo=CHAVE,
                                rotulo_salvar="Salvar prazo",
                                data_testid="estoque-admin-salvar-dias-parado")


def _card_numeracao():
    """O formato do número do CENTRAL — o ajuste que o DTI faz uma vez.

    O número é por almoxarifado, então este é o PADRÃO para almoxarifados novos.
    Almoxarifado já criado mantém os números que já recebeu; quem precisa de
    outro formato ajusta no almoxarifado dele (Ajustes)."""
    with card_admin("Numeração do almoxarifado novo", icone="tag",
                    chave_modulo=CHAVE):
        ui.label("Padrão para almoxarifados novos. O número do ITEM e o número "
                 "do DOCUMENTO são contagens separadas, e nenhum dos dois é "
                 "reaproveitado. Almoxarifado já criado mantém os números que "
                 "já recebeu.").classes("text-caption text-grey-6")
        inp_pref_item = ui.input("Prefixo do número do item",
                                 value=est_bd.get_config("estoque_prefixo_item", "IT")) \
            .props("outlined dense") \
            .props("data-testid=estoque-admin-prefixo-item")
        inp_pref_doc = ui.input("Prefixo do número do documento",
                                value=est_bd.get_config("estoque_prefixo_documento", "DOC")) \
            .props("outlined dense") \
            .props("data-testid=estoque-admin-prefixo-documento")
        try:
            dig_atual = est_bd.validar_digitos(
                int(est_bd.get_config("estoque_digitos_padrao",
                                      str(est_bd.DIGITOS_PADRAO))))
        except (TypeError, ValueError):
            dig_atual = est_bd.DIGITOS_PADRAO
        sel_dig = ui.select({str(d): f"{d} dígitos" for d in range(
            est_bd.DIGITOS_MINIMO, est_bd.DIGITOS_MAXIMO + 1)},
            label="Dígitos do número", value=str(dig_atual)) \
            .props("outlined dense") \
            .props("data-testid=estoque-admin-digitos")
        with ui.row().classes("items-center").style("gap: 0.75rem"):
            ui.label("Fica assim:").classes("text-caption text-grey-7")
            lbl_ex = ui.label("IT-0001 / DOC-0001").classes("text-caption text-grey-6")

        def _previa():
            try:
                d = est_bd.validar_digitos(sel_dig.value or dig_atual)
                pi = (inp_pref_item.value or "IT").strip().upper() or "IT"
                pd_ = (inp_pref_doc.value or "DOC").strip().upper() or "DOC"
                lbl_ex.text = f"{pi}-{'0' * d} / {pd_}-{'0' * d}"
            except Exception:
                log.exception("_previa falhou")

        inp_pref_item.on_value_change(lambda _e=None: _previa())
        inp_pref_doc.on_value_change(lambda _e=None: _previa())
        sel_dig.on_value_change(lambda _e=None: _previa())
        _previa()

        def _salvar():
            try:
                pi = (inp_pref_item.value or "IT").strip().upper() or "IT"
                pd_ = (inp_pref_doc.value or "DOC").strip().upper() or "DOC"
                d = est_bd.validar_digitos(sel_dig.value or dig_atual)
                gravou = (est_bd.set_config("estoque_prefixo_item", pi)
                          and est_bd.set_config("estoque_prefixo_documento", pd_)
                          and est_bd.set_config("estoque_digitos_padrao", str(d)))
                if not gravou:
                    notificar("Não foi possível gravar o padrão de numeração.",
                              type="negative")
                    return
                notificar(f"Padrão: item {pi} e documento {pd_} com {d} dígitos. "
                          f"Vale para almoxarifados novos; os que já existem "
                          f"mantêm o formato atual.", type="positive")
            except Exception as e:
                log.exception(f"estoque admin: gravar numeração falhou: {e}")
                notificar("Erro ao gravar o padrão de numeração.", type="negative")

        def _restaurar():
            try:
                inp_pref_item.value = "IT"
                inp_pref_doc.value = "DOC"
                sel_dig.value = str(est_bd.DIGITOS_PADRAO)
                inp_pref_item.update()
                inp_pref_doc.update()
                sel_dig.update()
                est_bd.set_config("estoque_prefixo_item", "IT")
                est_bd.set_config("estoque_prefixo_documento", "DOC")
                est_bd.set_config("estoque_digitos_padrao", str(est_bd.DIGITOS_PADRAO))
                _previa()
                notificar("Padrão de numeração restaurado.", type="warning")
            except Exception as e:
                log.exception(f"estoque admin: restaurar numeração falhou: {e}")
                notificar("Erro ao restaurar o padrão.", type="negative")

        rodape_salvar_restaurar(_salvar, _restaurar, chave_modulo=CHAVE,
                                rotulo_salvar="Salvar padrão",
                                data_testid="estoque-admin-salvar-numeracao")


def mostrar_administracao(usuario_logado: str = ""):
    """EN: Renders the Stock module administration panel.

    PT-BR: Monta o painel de administração do módulo. O gate de quem é
    administrador fica em `main.py`; aqui só se monta a tela."""
    global usuario_logado_atual
    usuario_logado_atual = usuario_logado or ""
    try:
        tema = ler_tema(CHAVE, cor_botao="#000000", cor_texto_botao="#FFFFFF",
                        texto_header=TEXTO_HEADER)
        ui.colors(primary=tema["cor_botao"])
        bloco_aparencia(usuario_logado, CHAVE, tema, prefixo_auditoria=CHAVE,
                        com_texto_header=True)
        _card_visao_geral()
        _card_servidores()
        _card_dias_parado()
        _card_numeracao()
        try:
            from mod_intranet.rotinas import painel_backup
            painel_backup(usuario_logado, CHAVE)
        except Exception:
            log.exception("estoque admin: painel de backup não montou")
            notificar("Erro ao carregar o painel de backup.", type="negative")
    except Exception as e:
        log.exception(f"estoque admin: painel não montou: {e}")
        try:
            notificar("Erro ao carregar a administração do Estoque.", type="negative")
        except Exception:
            pass
