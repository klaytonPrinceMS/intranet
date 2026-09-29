"""EN: Administration panel of the Service Orders module — overview, access,
default columns, numbering and backup.

PT-BR: Painel de administração do módulo de Ordens de Serviço — visão geral,
acesso dos servidores, colunas padrão do sistema, padrão de numeração e backup.

O QUE ESTE PAINEL FAZ, E O QUE NÃO FAZ
    Ele administra o MÓDULO, não o trabalho. Quem opera uma secretaria cria o
    quadro dela e convida quem precisa; isto aqui é o que o DTI ajusta uma vez
    para a prefeitura inteira: o formato do número, as colunas que todo quadro
    novo nasce com, e quem tem acesso ao módulo.

    O que NÃO cabe aqui, e por quê: a lista de todos os quadros e todas as
    ordens de serviço. Um quadro é trabalho em andamento, tem dono, tem prazo;
    quando o DTI passa a listar o trabalho de todo mundo, ele deixa de ser o
    administrador do módulo e vira o fiscal do setor. A visão geral deste painel
    é NÚMERO (quantos quadros, quantas ordens em atraso, quantos convites
    esperando), e o detalhe fica com quem é dono do quadro.

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
from mod_os import bd_manipulador as os_bd

log = observabilidade.get_logger("os")

CHAVE = "os"
ROTULO = "Ordens de Serviço"
TEXTO_HEADER = ("Quadros de ordem de serviço: um por unidade, um por servidor, "
                "com linha do tempo de cada ordem.")


def _n(rotulo, valor, sufixo="", cor=None):
    """Um número grande de visão geral. `cor=None` usa a cor de texto padrão."""
    classes = "text-h5" + (f" {cor}" if cor else " text-grey-9")
    with ui.column().classes("items-start"):
        ui.label(f"{valor}{sufixo}").classes(classes)
        ui.label(rotulo).classes("text-caption text-grey-6")


def _visao_geral():
    """Os números que dizem se o módulo está sendo usado e se alguém está preso.

    "Em atraso" é o número que importa: ordem de serviço vencida e não concluída
    é trabalho que parou, e é o que o DTI precisa ver primeiro. Um painel de
    módulo que só mostra "quantos quadros existem" informa que o sistema está no
    ar, e não se ele está servindo a alguém.
    """
    try:
        conn = os_bd.get_connection()
        try:
            cur = conn.cursor()
            def _um(sql, params=()):
                try:
                    cur.execute(sql, params)
                    linha = cur.fetchone()
                    return int((linha[0] if linha else 0) or 0)
                except Exception:
                    return 0
            q_total = _um("SELECT COUNT(*) FROM tb_os_quadro WHERE arquivado=0")
            q_unidade = _um("SELECT COUNT(*) FROM tb_os_quadro "
                            "WHERE arquivado=0 AND visibilidade='unidade'")
            q_ativos = _um("SELECT COUNT(*) FROM tb_os_quadro "
                           "WHERE arquivado=0 AND ativo=1")
            o_total = _um("SELECT COUNT(*) FROM tb_os_ordem WHERE arquivada=0")
            o_concluidas = _um("SELECT COUNT(*) FROM tb_os_ordem o "
                               "JOIN tb_os_coluna c ON c.id=o.coluna_id "
                               "WHERE o.arquivada=0 AND c.conclusiva=1")
            o_vencimento = _um("SELECT COUNT(*) FROM tb_os_ordem WHERE "
                               "arquivada=0 AND data_vencimento IS NOT NULL "
                               "AND data_vencimento <> ''")
            o_atraso = _um("SELECT COUNT(*) FROM tb_os_ordem o "
                           "LEFT JOIN tb_os_coluna c ON c.id=o.coluna_id "
                           "WHERE o.arquivada=0 "
                           "AND (c.conclusiva IS NULL OR c.conclusiva=0) "
                           "AND o.data_vencimento IS NOT NULL "
                           "AND o.data_vencimento <> '' "
                           "AND o.data_vencimento < ?", ("",))
            # comparação de data feita em Python: a coluna é texto e o formato
            # varia com quem escreveu, então perguntar ao SQLite seria pedir
            # para a comparação depender do formato
            try:
                from datetime import date
                hoje = date.today().isoformat()
                o_atraso = _um("SELECT COUNT(*) FROM tb_os_ordem o "
                               "LEFT JOIN tb_os_coluna c ON c.id=o.coluna_id "
                               "WHERE o.arquivada=0 "
                               "AND (c.conclusiva IS NULL OR c.conclusiva=0) "
                               "AND o.data_vencimento IS NOT NULL "
                               "AND o.data_vencimento <> '' "
                               "AND substr(o.data_vencimento,1,10) < ?", (hoje,))
            except Exception:
                o_atraso = 0
            convites = _um("SELECT COUNT(*) FROM tb_os_convite "
                           "WHERE situacao='pendente'")
            conv_usuarios = _um("SELECT COUNT(DISTINCT quadro_id, user_nome) "
                                "FROM tb_os_convite")
            return {"quadros": q_total, "quadros_ativos": q_ativos,
                    "quadros_unidade": q_unidade, "ordens": o_total,
                    "concluidas": o_concluidas, "com_prazo": o_vencimento,
                    "atraso": o_atraso, "convites": convites,
                    "convidados": conv_usuarios}
        finally:
            conn.close()
    except Exception as e:
        log.exception(f"telas_administracao: visão geral falhou: {e}")
        return {}


def _card_visao_geral():
    with card_admin("Uso do módulo", icone="insights",
                    chave_modulo=CHAVE, grade=False):
        d = _visao_geral()
        if not d:
            ui.label("Não foi possível ler os números agora.").classes(
                "text-body2 text-negative")
            return
        with ui.row().classes("w-full items-start").style("gap: 1.5rem; flex-wrap: wrap"):
            _n("quadros de pé", d.get("quadros", 0))
            _n("deles, de unidade", d.get("quadros_unidade", 0))
            _n("ordens em aberto",
               max(0, d.get("ordens", 0) - d.get("concluidas", 0)))
            _n("em atraso",
               d.get("atraso", 0),
               cor="text-negative" if d.get("atraso") else None)
            _n("convites esperando", d.get("convites", 0))
            _n("pessoas convidadas", d.get("convidados", 0))
        if d.get("atraso"):
            ui.label(
                f"Há {d['atraso']} ordem(ns) com prazo vencido e sem conclusão. "
                f"Isso é trabalho parado — o quadro é de quem o criou, e o "
                f"painel só avisa.").classes("text-caption text-orange-8")
        else:
            ui.label("Nenhuma ordem de serviço com prazo vencido em aberto.").classes(
                "text-caption text-grey-6")


def _card_acesso():
    """Quem tem acesso ao módulo, e como dar acesso a quem não tem.

    A concessão é feita pela fachada do núcleo, nunca escrevendo no banco da
    Gestão de Usuários: o vínculo `tb_acesso_usuario` é do módulo dono, e o que
    este painel faz é pedir.
    """
    with card_admin("Servidores com acesso ao módulo",
                    icone="manage_accounts", chave_modulo=CHAVE):
        ui.label("Buscar pelo nome, pelo nome completo ou pelo login. A pessoa é "
                 "listada pelo nome de tratamento; o login fica entre parênteses "
                 "porque é com ele que ela entra.").classes(
            "text-caption text-grey-6")
        inp_busca = ui.input("Buscar servidor", placeholder="nome ou login") \
            .props("outlined dense clearable").classes("w-full") \
            .props("data-testid=os-admin-busca-acesso")
        sel_user = ui.select({}, label="Servidor encontrado") \
            .props("outlined dense clearable").classes("w-full") \
            .props("data-testid=os-admin-selecionar-acesso")
        sel_papel = ui.select({"comum": "Comum — cria e trata ordens de serviço",
                               "administrador": "Administrador do módulo — "
                                                "cria quadro de unidade e "
                                                "convida"},
                              label="Papel no módulo", value="comum") \
            .props("outlined dense").classes("w-full") \
            .props("data-testid=os-admin-papel-acesso")

        def _carregar(termo):
            from mod_intranet import integracoes
            todos = integracoes.listar_usuarios_gestao(filtro_ativo=True) or []
            return todos

        def _ao_buscar(e=None):
            try:
                import unicodedata

                def _norm(t):
                    return unicodedata.normalize(
                        "NFKD", t or "").encode("ascii", "ignore").decode().lower()

                todos = _carregar(None)
                termo = _norm(getattr(e, "value", "") or "")
                achados = [u for u in todos
                           if termo and (termo in _norm(u[1]) or termo in _norm(u[9])
                                         or termo in _norm(u[4]))]
                if not termo:
                    achados = todos[:20]
                opts = {}
                for u in achados[:30]:
                    nome = (u[9] or "").strip() or u[1]
                    opts[u[1]] = f"{nome} (@{u[1]})"
                sel_user.set_options(opts)
                sel_user.update()
            except Exception as ex:
                log.warning(f"os admin: busca de servidor falhou: {ex}")
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
                from mod_intranet import integracoes
                ok = integracoes.conceder_acesso_gestao(
                    usuario_logado_atual, sel_user.value, CHAVE,
                    papel=sel_papel.value or "comum")
                if ok:
                    notificar(f"Acesso de {sel_user.value} "
                              f"concedido como {sel_papel.value}.", type="positive")
                else:
                    notificar("Não foi possível conceder o acesso.", type="negative")
            except Exception as e:
                log.exception(f"os admin: conceder acesso falhou: {e}")
                notificar("Erro ao conceder acesso.", type="negative")

        def _restaurar():
            sel_user.set_options({})
            sel_user.value = None
            sel_papel.value = "comum"
            try:
                sel_user.update()
                sel_papel.update()
            except Exception:
                pass
            notificar("Seleção limpa.", type="warning")

        rodape_salvar_restaurar(_salvar, _restaurar, chave_modulo=CHAVE,
                                rotulo_salvar="Conceder acesso",
                                data_testid="os-admin-conceder-acesso")
        ui.label("Retirar acesso é feito na tela de Usuários, em "
                 "Liberações por módulo — de propósito: sair é tão decisão do "
                 "administrador quanto entrar, e fica no mesmo lugar onde as "
                 "outras liberações do sistema são feitas.").classes(
            "text-caption text-grey-6")


# Estado do formulário de acesso, lido pela função de salvar. Vem do chamador
# para que o log de auditoria registre QUEM concedeu, e não "sistema".
usuario_logado_atual = ""


def _card_numeracao():
    """O formato do número — o ajuste que o DTI faz uma vez para a prefeitura.

    O número é por quadro, então este é o PADRÃO, não uma imposição: quadro já
    criado mantém os números que já tem. Quem precisa de outro formato (por
    secretaria, por ano, com mais dígitos) ajusta no quadro dele.
    """
    with card_admin("Numeração das ordens de serviço",
                    icone="tag", chave_modulo=CHAVE):
        ui.label("Padrão para os quadros novos. O número é sequencial por "
                 "quadro e nunca é reaproveitado; um quadro já criado mantém os "
                 "números que já recebeu.").classes("text-caption text-grey-6")
        dig_atual = os_bd.get_config("os_digitos_padrao", str(os_bd.DIGITOS_PADRAO))
        try:
            dig_atual = os_bd.validar_digitos(int(dig_atual))
        except Exception:
            dig_atual = os_bd.DIGITOS_PADRAO
        inp_pref = ui.input("Prefixo padrão (quadros novos)",
                            value=os_bd.get_config("os_prefixo_padrao", "OS")) \
            .props("outlined dense").classes("w-full") \
            .props("data-testid=os-admin-prefixo")
        inp_dig = ui.select({str(d): f"{d} dígitos"
                             for d in range(3, int(os_bd.DIGITOS_PADRAO) + 1, 1)
                             if d >= 3},
                            label="Dígitos do número", value=str(dig_atual)) \
            .props("outlined dense").classes("w-full") \
            .props("data-testid=os-admin-digitos")
        with ui.row().classes("items-center").style("gap: 0.75rem"):
            ui.label("Fica assim:").classes("text-caption text-grey-7")
            lbl_ex = ui.label("OS-0001").classes("text-caption text-grey-6")

        def _previa():
            pref = (inp_pref.value or "OS").strip().upper() or "OS"
            try:
                d = os_bd.validar_digitos(int(inp_dig.value or dig_atual))
                lbl_ex.text = os_bd.montar_numero(pref, 1, d)
            except Exception:
                lbl_ex.text = f"{pref}-0001"

        inp_pref.on_value_change(lambda _e=None: _previa())
        inp_dig.on_value_change(lambda _e=None: _previa())
        _previa()

        def _salvar():
            try:
                dig = os_bd.validar_digitos(int(inp_dig.value or dig_atual))
                pref = (inp_pref.value or "OS").strip().upper() or "OS"
                gravou_pref = os_bd.set_config("os_prefixo_padrao", pref)
                gravou_dig = os_bd.set_config("os_digitos_padrao", str(dig))
                if not (gravou_pref and gravou_dig):
                    notificar("Não foi possível gravar o padrão de numeração.",
                              type="negative")
                    return
                notificar(f"Padrão: {pref} com {dig} dígitos. Vale para os quadros "
                          f"novos; os que já existem mantêm o formato atual.",
                          type="positive")
            except Exception as e:
                log.exception(f"os admin: gravar padrão de numeração falhou: {e}")
                notificar("Erro ao gravar o padrão de numeração.", type="negative")

        def _restaurar():
            try:
                inp_pref.value = "OS"
                inp_dig.value = str(os_bd.DIGITOS_PADRAO)
                inp_pref.update()
                inp_dig.update()
                os_bd.set_config("os_prefixo_padrao", "OS")
                os_bd.set_config("os_digitos_padrao", str(os_bd.DIGITOS_PADRAO))
                _previa()
                notificar("Padrão de numeração restaurado.", type="warning")
            except Exception as e:
                log.exception(f"os admin: restaurar numeração falhou: {e}")
                notificar("Erro ao restaurar o padrão.", type="negative")

        rodape_salvar_restaurar(_salvar, _restaurar, chave_modulo=CHAVE,
                                rotulo_salvar="Salvar padrão",
                                data_testid="os-admin-salvar-numeracao")


def _card_colunas_padrao():
    """As colunas que todo quadro novo nasce com.

    Um quadro sem colunas é um quadro vazio, e quem cria um quadro não quer
    decidir de novo o mesmo conjunto toda vez. O padrão do sistema é "Aberto, em
    andamento, aguardando, concluído" — quatro etapas, e só a última conta como
    conclusão (o que faz o número de "em atraso" da visão geral ser verdadeiro).
    """
    with card_admin("Colunas padrão dos quadros novos",
                    icone="view_column", chave_modulo=CHAVE):
        ui.label("Uma coluna por linha, na ordem em que aparecem no quadro. A "
                 "última linha é a de conclusão: é ela que fecha a ordem de "
                 "serviço e faz o número de \"em atraso\" da visão geral "
                 "querer dizer alguma coisa.").classes("text-caption text-grey-6")
        ta = ui.textarea("Colunas", value="\n".join(os_bd.colunas_padrao())) \
            .props("outlined rows=6").classes("w-full") \
            .props("data-testid=os-admin-colunas")

        def _salvar():
            try:
                ok, msg = os_bd.salvar_colunas_padrao(
                    ", ".join(l.strip() for l in (ta.value or "").splitlines()
                              if l.strip()), usuario_logado_atual)
                notificar(msg, type="positive" if ok else "negative")
            except Exception as e:
                log.exception(f"os admin: gravar colunas padrão falhou: {e}")
                notificar("Erro ao gravar as colunas padrão.", type="negative")

        def _restaurar():
            try:
                padrao = os_bd.COLUNAS_PADRAO
                ok, msg = os_bd.salvar_colunas_padrao(padrao, usuario_logado_atual)
                ta.value = "\n".join(p.strip() for p in padrao.split(","))
                ta.update()
                notificar(msg if ok else "Colunas restauradas.",
                          type="positive" if ok else "negative")
            except Exception as e:
                log.exception(f"os admin: restaurar colunas falhou: {e}")
                notificar("Erro ao restaurar as colunas.", type="negative")

        rodape_salvar_restaurar(_salvar, _restaurar, chave_modulo=CHAVE,
                                rotulo_salvar="Salvar colunas",
                                data_testid="os-admin-salvar-colunas")


def mostrar_administracao(usuario_logado: str = ""):
    """EN: Renders the module administration panel.

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
        _card_acesso()
        _card_numeracao()
        _card_colunas_padrao()
        try:
            from mod_intranet.rotinas import painel_backup
            painel_backup(usuario_logado, CHAVE)
        except Exception:
            log.exception("os admin: painel de backup não montou")
            notificar("Erro ao carregar o painel de backup.", type="negative")
    except Exception as e:
        log.exception(f"os admin: painel não montou: {e}")
        try:
            notificar("Erro ao carregar a administração das Ordens de Serviço.",
                      type="negative")
        except Exception:
            pass
