"""EN: Open data screen — a grid of public-dataset cards (route /dados-abertos).

PT-BR: Tela de Dados Abertos — a grade de cards de datasets públicos (rota
/dados-abertos).

A tela não conhece nenhum conjunto de dados pelo nome: ela pede o REGISTRO ao
`bd_manipulador` (`tb_fontes`) e desenha um card por fonte. Hoje existe **um**
card — "Servidores Públicos" —, que abre a representação da folha publicada
pelo portal de transparência.

**O que NÃO está aqui, e por quê:** a tabela linha a linha dos servidores com
remuneração. A folha é pública, mas o painel mostra a **forma** da força de
trabalho (quantos servidores, em qual cargo, em qual situação, quanto paga a
mediana) e não o ordenado de cada pessoa — para o detalhe nominal, o card
publica o link da FONTE, que é onde a lei diz que o dado mora. O resto é o
mesmo que o painel da folha: cabeçalho com a origem, os indicadores e as
distribuições.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from nicegui import ui

from mod_intranet import autenticacao
from mod_intranet import observabilidade
from mod_intranet.aba_modulo import cabecalho
from mod_intranet.tema_modulo import ler_tema, notificar
from mod_intranet.ui_comum import botao
from mod_dados_abertos import bd_manipulador as dad

log = observabilidade.get_logger("dados_abertos")

# Cores das barras — as MESMAS do painel da folha. Fixa aqui, e não como
# parâmetro, porque são a identidade visual da leitura: quem viu o painel
# reconhece o mesmo gráfico na intranet.
CORES = {
    "situacao": "#16a34a",
    "vinculo": "#7c3aed",
    "unidade": "#0891b2",
    "cargo": "#ea580c",
    "lotacao": "#0f766e",
}


def _pode_acessar(user_nome: str, perfil_global: str) -> bool:
    """EN: Whether the user reaches the open-data module.

    PT-BR: Se o usuário alcança o módulo de Dados Abertos.

    `dados_abertos` **não** está em `ACESSO_PADRAO_NOVO_USUARIO`: dado ser
    público por lei não expõe a intranet por si só. Quem libera é o
    administrador, por módulo.
    """
    if perfil_global == "administrador_geral":
        return True
    try:
        return autenticacao.validar_acesso_modulo(user_nome, "dados_abertos")
    except Exception:
        return False


def _brl(valor) -> str:
    """EN: 3419.86 -> 'R$ 3.419,86'.

    PT-BR: 3419.86 -> 'R$ 3.419,86'.
    """
    try:
        return f"R$ {float(valor or 0):,.2f}".replace(",", "X").replace(
            ".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "R$ 0,00"


def _barras(itens, limite=12, cor="#1d4ed8"):
    """EN: Horizontal bar rows (label | track | count), same look as the sheet panel.

    PT-BR: Linhas de barra horizontal (rótulo | trilho | contagem), iguais ao
    painel da folha.

    A barra é um `ui.element('div')` com largura em PORCENTUAL do trilho — e
    não `ui.linear_progress`, que é uma régua arredondada com animação e
    ficaria diferente da leitura da folha. O `min-width: 0` no rótulo é o que
    impede o defeito clássico: sem ele, um nome de secretaria longo impõe a
    largura mínima e empurra a barra para fora do cartão.
    """
    itens = list(itens or [])[:limite]
    if not itens:
        ui.label("Sem dados para esta distribuição.").classes(
            "text-body2 text-grey-6 italic")
        return
    total = sum(qtd for _, qtd in itens) or 1
    with ui.column().classes("w-full").style("gap: 5px; min-width: 0"):
        for valor, qtd in itens:
            with ui.row().classes("w-full items-center no-wrap").style(
                    "gap: 8px; min-width: 0"):
                ui.label(str(valor)).classes(
                    "text-caption").style(
                    "width: 150px; min-width: 0; overflow: hidden; "
                    "text-overflow: ellipsis; white-space: nowrap"
                ).tooltip(str(valor))
                trilho = ui.element("div").classes("grow").style(
                    "background: #f1f5f9; border-radius: 4px; height: 14px; "
                    "overflow: hidden; min-width: 0")
                with trilho:
                    ui.element("div").style(
                        f"display: block; height: 100%; border-radius: 4px; "
                        f"background: {cor}; "
                        f"width: {qtd / total * 100:.2f}%")
                ui.label(str(qtd)).classes("text-caption text-grey-6").style(
                    "width: 42px; text-align: right; min-width: 0")


def _cartao_distribuicao(titulo, itens, cor, limite=12):
    """EN: Titled card holding one distribution.

    PT-BR: Cartão com título que abriga uma distribuição.
    """
    with ui.card().classes("w-full").style("padding: 16px; min-width: 0"):
        ui.label(titulo.upper()).classes(
            "text-caption font-bold text-grey-6").style("letter-spacing: .06em")
        ui.element("div").classes("w-full").style("height: 12px")
        _barras(itens, limite, cor)


def _kpi(rotulo, valor, nota=""):
    """EN: One metric card (big number, label, footnote).

    PT-BR: Um cartão de métrica (número grande, rótulo, nota).
    """
    with ui.card().classes("w-full").style("padding: 14px 16px; min-width: 0"):
        ui.label(str(valor)).classes(
            "text-h5 font-bold text-grey-9").style("line-height: 1.1")
        ui.label(rotulo.upper()).classes(
            "text-caption text-grey-6").style("letter-spacing: .05em")
        if nota:
            ui.label(nota).classes("text-caption text-grey-5")


def _painel_servidores(user_nome: str):
    """EN: The server sheet as the source publishes it (aggregates only).

    PT-BR: A folha de servidores como a FONTE a publica (só agregados).
    """
    resumo = dad.resumo_da_folha()
    if not resumo.get("disponivel"):
        with ui.card().classes("w-full").style("padding: 24px; min-width: 0"):
            with ui.column().classes("w-full items-center gap-2"):
                ui.icon("cloud_off", size="48px").classes("text-grey-5")
                ui.label("Fonte indisponível").classes("text-h6")
                ui.label(resumo.get("motivo") or
                         "O portal não devolveu a folha no momento.").classes(
                    "text-body2 text-grey-7 text-center")
        return

    # ---- Cabeçalho: origem, competência, quando foi coletado ----
    with ui.column().classes("w-full gap-1").style("min-width: 0"):
        ui.label(f"Competência {resumo.get('competencia') or '—'}").classes(
            "text-h6 font-bold")
        coletado = (resumo.get("coletado_em") or "")[:19].replace("T", " ")
        ui.label(
            f"Origem: {resumo.get('origem') or '—'} · coletado em "
            f"{coletado or '—'}").classes("text-caption text-grey-6")
        if resumo.get("aviso"):
            ui.label(resumo["aviso"]).classes("text-caption text-grey-5")
        url = resumo.get("url")
        if url:
            ui.link(url, url, target="_blank", new_tab=True).classes(
                "text-caption")

    # ---- Aviso: por que não há tabela nominal, e onde achá-la ----
    with ui.card().classes("w-full").style("padding: 12px 16px; min-width: 0"):
        with ui.row().classes("w-full items-start no-wrap").style("gap: 10px"):
            ui.icon("info", size="20px").classes("text-primary shrink-0")
            ui.label(
                "Este painel mostra a FORMA da folha — quantos servidores, em "
                "qual cargo, em qual situação e quanto paga a mediana. O "
                "detalhe nominal, pessoa a pessoa, está na fonte oficial "
                "publicada no cabeçalho: é lá que a lei determina que o dado "
                "aberto mora."
            ).classes("text-body2").style("min-width: 0")

    # ---- Indicadores ----
    total = resumo.get("total", 0)
    rem = resumo.get("remuneracao") or {}
    ativos = sum(qtd for valor, qtd in resumo.get("situacao") or []
                 if str(valor).strip().lower() == "ativo")
    with ui.grid().classes("w-full").style(
            "grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); "
            "gap: 12px"):
        _kpi("Servidores", total, "registros na folha")
        _kpi("Ativos", ativos,
             f"{ativos / total * 100:.0f}% da folha" if total else "")
        _kpi("Secretarias", len(resumo.get("unidade") or []),
             "unidades de primeira ordem")
        _kpi("Cargos distintos", len(resumo.get("cargo") or []),
             "denominações no cadastro")
        _kpi("Remuneração mediana", _brl(rem.get("mediana")),
             f"{resumo.get('total_com_remuneracao', 0)} com valor")
        _kpi("Remuneração total", _brl(rem.get("total")),
             "folha bruta do mês")

    # ---- Distribuições ----
    with ui.grid().classes("w-full").style(
            "grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); "
            "gap: 16px"):
        _cartao_distribuicao("Situação", resumo.get("situacao"),
                             CORES["situacao"], 8)
        _cartao_distribuicao("Vínculo", resumo.get("vinculo"),
                             CORES["vinculo"], 10)
        _cartao_distribuicao("Secretaria", resumo.get("unidade"),
                             CORES["unidade"], 12)
        _cartao_distribuicao("Cargos (top 12)", resumo.get("cargo"),
                             CORES["cargo"], 12)
    _cartao_distribuicao("Lotação (top 12)", resumo.get("lotacao"),
                         CORES["lotacao"], 12)


def _abrir_fonte(user_nome: str, fonte: dict):
    """EN: Opens a source in a dialog (the detail view of one dataset).

    PT-BR: Abre uma fonte em diálogo (a visão de detalhe de um conjunto).
    """
    chave = fonte.get("chave") or ""
    try:
        with ui.dialog() as dlg:
            with ui.card().classes("w-[92vw]").style(
                    "max-width: 1500px; max-height: 90vh; overflow-y: auto; "
                    "min-width: 0"):
                with ui.column().classes("w-full").style(
                        "gap: 16px; min-width: 0"):
                    ui.label(fonte.get("nome") or chave).classes(
                        "text-h6 font-bold")
                    if fonte.get("descricao"):
                        ui.label(fonte["descricao"]).classes(
                            "text-body2 text-grey-7")
                    ui.separator()
                    if chave == "servidores_publicos":
                        _painel_servidores(user_nome)
                    else:
                        # Fonte cadastrada e ainda sem leitor: honestidade em vez
                        # de tela vazia — diz o que falta, e não desenha zero.
                        with ui.column().classes("w-full items-center gap-2"):
                            ui.icon("hourglass_empty", size="40px").classes(
                                "text-grey-5")
                            ui.label("Fonte cadastrada, leitura ainda não "
                                     "implementada.").classes("text-body1")
                            ui.label(
                                "Este conjunto entrou no registro de fontes e "
                                "vai aparecer aqui quando o seu leitor existir."
                            ).classes("text-caption text-grey-6 text-center")
                    ui.separator()
                    botao("Fechar", on_click=dlg.close, variante="secundario",
                          chave_modulo="dados_abertos")
        dlg.open()
        if chave == "servidores_publicos":
            dad.registrar_consulta(user_nome, chave, "painel de agregados")
    except Exception as e:
        log.exception(f"_abrir_fonte: falha ao abrir '{chave}' | {e}")
        notificar("Erro ao abrir o conjunto de dados.", tipo="error")


def _card_fonte(fonte: dict, user_nome: str):
    """EN: One dataset card in the main grid (opens the source on click).

    PT-BR: Um card de conjunto de dados na grade principal.
    """
    with ui.card().classes("w-full cursor-pointer").style(
            "padding: 20px; min-width: 0").on(
        "click", lambda: _abrir_fonte(user_nome, fonte)):
        with ui.row().classes("w-full items-start no-wrap").style(
                "gap: 12px; min-width: 0"):
            ui.icon(fonte.get("icone") or "public", size="32px").classes(
                "text-primary shrink-0")
            with ui.column().classes("grow").style("gap: 4px; min-width: 0"):
                ui.label(fonte.get("nome") or fonte.get("chave") or "").classes(
                    "text-subtitle1 font-bold").style("min-width: 0")
                ui.label(fonte.get("descricao") or "").classes(
                    "text-body2 text-grey-7").style("min-width: 0")
        with ui.row().classes("w-full items-center no-wrap mt-2").style("gap: 6px"):
            ui.icon("open_in_new", size="16px").classes("text-grey-5")
            ui.label("Abrir").classes("text-caption text-primary")


def mostrar_tela(user_nome: str, perfil_global: str = ""):
    """EN: Renders /dados-abertos — header + the grid of dataset cards.

    PT-BR: Renderiza /dados-abertos — cabeçalho + a grade de cards.

    A grade vem do REGISTRO de fontes (`tb_fontes`), não de uma lista escrita
    aqui: os próximos conjuntos de dados entram sem que esta tela mude.
    """
    if not _pode_acessar(user_nome, perfil_global):
        with ui.column().classes("w-full items-center p-12 gap-3"):
            ui.icon("block", size="64px").classes("text-red-8")
            ui.label("Acesso restrito").classes("text-h6")
            ui.label(
                "Somente usuários com acesso ao módulo Dados Abertos."
            ).classes("text-body2 text-grey-7")
        return

    try:
        tema = ler_tema(
            "dados_abertos", cor_botao="#000000", cor_texto_botao="#FFFFFF",
            texto_header="Dados abertos publicados pela prefeitura.")
        ui.colors(primary=tema["cor_botao"])
        t_cor_titulo = tema["cor_titulo"]
        t_cor_fundo = tema["cor_fundo"]
        t_texto_header = tema["texto_header"]

        with ui.column().classes("w-full p-6 gap-4"):
            cabecalho("Dados Abertos", t_texto_header,
                      chave_modulo="dados_abertos", cor_titulo=t_cor_titulo,
                      cor_fundo=t_cor_fundo)

            fontes = dad.listar_fontes(somente_ativas=True)
            if not fontes:
                with ui.card().classes("w-full").style("padding: 24px"):
                    with ui.column().classes("w-full items-center gap-2"):
                        ui.icon("inbox", size="48px").classes("text-grey-5")
                        ui.label("Nenhum conjunto de dados disponível").classes(
                            "text-h6")
                        ui.label(
                            "Os conjuntos de dados públicos aparecem aqui "
                            "conforme são cadastrados em Configurações."
                        ).classes("text-body2 text-grey-7 text-center")
                return

            ui.label(
                f"{len(fontes)} conjunto(s) de dados público(s) disponível(is)."
            ).classes("text-caption text-grey-6")

            with ui.grid().classes("w-full").style(
                    "grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); "
                    "gap: 16px"):
                for fonte in fontes:
                    _card_fonte(fonte, user_nome)
    except Exception as e:
        log.exception(f"mostrar_tela: falha ao renderizar Dados Abertos | {e}")
        notificar("Erro ao carregar a página de Dados Abertos.", tipo="error")
