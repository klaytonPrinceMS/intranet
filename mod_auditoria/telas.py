"""Tela do módulo Auditoria — visualização de logs centrais (tb_auditoria).

Somente-leitura: lê a trilha unificada gravada pelos demais módulos via
audit_log. Recursos: filtros (usuário/módulo/ação/hora/intervalo de datas),
paginação server-side, exportação CSV, categorias de ação com cores e escolha
do auditor sobre quais campos exibir e em que ordem (persistida por usuário).
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

import csv
import io
import json
from datetime import datetime

from nicegui import ui
from mod_intranet.conexao_bd import get_config, set_config
from mod_intranet.contexto import rotulo_dispositivo
from mod_intranet import observabilidade
from mod_intranet import docker_detector as _dd
from mod_intranet.aba_modulo import cabecalho, abas
from mod_intranet.tema_modulo import campo_modulo
from mod_intranet.manipulador_bd import audit_log
from mod_auditoria.manipulador_bd import (
    buscar_logs as buscar_logs_auditoria,
    get_modulos_com_auditoria,
)

log = observabilidade.get_logger("auditoria")

# Campos exibíveis (chave -> rótulo), na ordem padrão. A preferência do auditor
# (quais mostrar e em que ordem) fica em tb_config na chave
# 'auditoria_campos:<usuario>' — persistida POR USUÁRIO, visto que o módulo é
# exclusivo do administrador geral.
CAMPOS = [
    ("data", "Data/Hora"),
    ("usuario", "Usuário"),
    ("modulo", "Módulo"),
    ("acao", "Ação"),
    ("descricao", "Descrição"),
    ("hash", "Hash"),
    ("ip", "IP"),
    ("dispositivo", "Dispositivo"),
]
_LABEL = dict(CAMPOS)

# Cores por tipo de ação: servem ao rótulo da coluna "Ação" e ao filtro por
# categorias prontas (em vez de apenas texto livre).
CORES_ACAO = {
    # Núcleo / sessão
    "login": "#1565C0", "login_falha": "#C62828", "logout": "#1565C0",
    "trocar_senha": "#1565C0", "alterar_senha": "#1565C0",
    "registrar_modulo": "#455A64", "excluir_modulo": "#C62828",
    "modulo_desativado": "#E65100", "moduloreativado": "#2E7D32",
    "modulos_desativados": "#E65100",
    "config_alterada": "#455A64", "config_restaurada": "#455A64", "configuracao": "#455A64",
    "backup_manual": "#455A64", "documentacao_reconstruida": "#455A64", "logs_limpos": "#455A64",
    "acesso_negado": "#C62828",
    # Gestão de usuários
    "criar_usuario": "#2E7D32", "editar_usuario": "#2E7D32", "renomear_usuario": "#2E7D32",
    "soft_delete": "#6A1B9A", "excluir_definitivo": "#C62828",
    "bloquear_usuario": "#E65100", "desbloquear_usuario": "#2E7D32",
    "definir_acesso": "#2E7D32", "remover_acesso": "#E65100",
    "encerrar_sessao": "#6A1B9A", "encerrar_todas_sessoes": "#6A1B9A",
    # Blog
    "criar_postagem": "#00838F", "atualizar_postagem": "#00838F",
    "publicar_postagem": "#2E7D32", "despublicar_postagem": "#E65100",
    "excluir_postagem": "#C62828", "criar_comentario": "#00838F",
    # Editor PDF
    "upload": "#EF6C00", "upload_hash": "#EF6C00", "reduzir": "#EF6C00",
    "juntar": "#EF6C00", "cortar": "#EF6C00", "dividir": "#EF6C00",
    "deletar": "#C62828", "zip": "#EF6C00", "erro_reducao": "#C62828", "expiracao": "#455A64",
    # Renomear empenho
    "processar": "#558B2F", "quarentena": "#E65100",
    "ferramenta_corte": "#EF6C00", "ferramenta_juntar": "#EF6C00", "ferramenta_reducao": "#EF6C00",
    # Solicitação de impressão
    "rascunho_upload": "#6D4C41", "rascunho_cancelado": "#6D4C41", "rascunho_expirado": "#6D4C41",
    "criar_solicitacao": "#6D4C41", "autorizar_solicitacao": "#2E7D32",
    "recusar_solicitacao": "#C62828", "imprimir_solicitacao": "#2E7D32",
    "recuar_solicitacao": "#E65100", "cancelar_solicitacao": "#C62828",
    "arquivo_impresso_excluido": "#6D4C41",
    "criar_secretaria": "#6D4C41", "editar_secretaria": "#6D4C41", "excluir_secretaria": "#C62828",
    "criar_setor": "#6D4C41", "editar_setor": "#6D4C41", "excluir_setor": "#C62828",
    "criar_responsavel": "#6D4C41", "editar_responsavel": "#6D4C41", "excluir_responsavel": "#C62828",
    "definir_cota": "#6D4C41", "resetar_consumo": "#E65100",
}


def mostrar_tela(usuario_logado: str, perfil: str):
    eh_admin_geral = perfil == "administrador_geral"

    # ---------- Configurações (prefixo auditoria_) ----------
    def _cfg(chave, default):
        try:
            return get_config(f"auditoria_{chave}", str(default))
        except Exception:
            log.error(f"falha ao ler config auditoria_{chave}")
            return str(default)

    # ================= TEMA (Aparência, prefixo auditoria_) =================
    def _tema(chave, default):
        try:
            return (get_config(f"auditoria_{chave}", default) or "").strip() or default
        except Exception:
            return default

    t_cor_botao = _tema("cor_botao", "#C62828")
    t_cor_txt_botao = _tema("cor_texto_botao", "#FFFFFF")
    t_cor_fundo = _tema("cor_fundo", "")
    t_cor_titulo = _tema("cor_titulo", "#212121")
    t_btn_tamanho = _tema("btn_tamanho", "medium")

    def _btn_cls():
        if t_btn_tamanho == "small":
            return "min-w-[140px] text-sm"
        if t_btn_tamanho == "large":
            return "min-w-[220px] text-lg"
        return "min-w-[180px]"

    def _btn_style():
        st = ""
        if t_cor_botao:
            st += f"background-color:{t_cor_botao};"
        if t_cor_txt_botao:
            st += f"color:{t_cor_txt_botao};"
        return st

    try:
        limite_sql = max(10, int(_cfg("limite", "1000")))
    except (TypeError, ValueError):
        limite_sql = 1000
    retencao_dias = _cfg("retencao_dias", "90")
    texto_header = _cfg("texto_header", "Rastreamento de ações no sistema (LGPD).")

    # ---------- Preferência por usuário: campos visíveis e ordem ----------
    def _campos_ativos():
        chaves_validas = {c for c, _ in CAMPOS}
        lista = None
        try:
            dados = get_config(f"auditoria_campos:{usuario_logado}", "")
            lista = json.loads(dados) if dados else None
        except Exception:
            lista = None
        if not isinstance(lista, list):
            lista = [c for c, _ in CAMPOS]
        lista = [c for c in lista if c in chaves_validas]
        for c, _ in CAMPOS:
            if c not in lista:
                lista.append(c)
        return lista

    def _salvar_campos(lista):
        try:
            set_config(f"auditoria_campos:{usuario_logado}", json.dumps(lista))
        except Exception:
            log.exception("falha ao salvar preferência de colunas")

    # ---------- Estado de paginação ----------
    pagina_atual = 1
    total_registros = 0
    total_paginas = 1
    _ultimos_logs = []

    # ---------- Navegação por tabela de auditoria ----------
    # None = "todas as tabelas"; caso contrário, o nome da tabela
    # (tb_auditoria_<modulo>) selecionada no menu de navegação.
    tabela_atual = None

    # Rótulos amigáveis por chave de módulo, usados no menu de navegação.
    DEFS_NAV = {
        "intranet": "Intranet (núcleo)",
        "gest_cad_usuario": "Gestão de Usuários",
        "blog": "Blog",
        "edit-pdf": "Editor de PDF",
        "renomear-empenho": "Renomear Empenhos",
        "solicita_impressao": "Solicitação de Impressão",
        "auditoria": "Auditoria",
    }

    def _rotulo_modulo(chave):
        return DEFS_NAV.get(chave, chave.replace("_", " ").replace("-", " ").title())

    def _opcoes_navegacao():
        """Mapeia cada tabela de auditoria para um rótulo amigável."""
        opcoes = [("", "Todas as auditorias")]
        try:
            for modulo, tabela in get_modulos_com_auditoria():
                opcoes.append((tabela, _rotulo_modulo(modulo)))
        except Exception:
            log.exception("falha ao listar tabelas de auditoria")
        # Ordena por rótulo, mantendo "Todas" no topo.
        opcoes = opcoes[:1] + sorted(opcoes[1:], key=lambda o: o[1])
        return dict(opcoes)

    # ---------- Helpers ----------
    def _linha_bruta(r):
        """Dict 'chave -> valor' a partir da tupla do SELECT (antes da UI)."""
        return {
            "data": r[6],
            "usuario": r[1],
            "modulo": r[2],
            "acao": r[3],
            "descricao": r[4] or "",
            "hash": r[5] or "",
            "ip": r[7] or "",
            "dispositivo": rotulo_dispositivo(r[8]) or "",
        }

    def _buscar_logs(filtro_usuario="", filtro_modulo="", filtro_acao="",
                     data_inicio="", data_fim="", filtro_hora="", pagina=1):
        log.info(f"[DIAG] _buscar_logs chamado com tabela_atual={tabela_atual!r}")
        return buscar_logs_auditoria(
            tabela=tabela_atual,
            filtro_usuario=filtro_usuario,
            filtro_modulo=filtro_modulo,
            filtro_acao=filtro_acao,
            filtro_hora=filtro_hora,
            data_inicio=data_inicio,
            data_fim=data_fim,
            pagina=pagina,
            limite_sql=limite_sql,
        )

    def _render_tabela():
        ativos = _campos_ativos()
        conjunto = set(ativos)
        colunas = []
        for chave, label in CAMPOS:
            if chave not in conjunto:
                continue
            col = {"name": chave, "label": label, "field": chave,
                   "align": "center" if chave == "data" else "left"}
            colunas.append(col)
        tabela.columns = colunas
        linhas = []
        for r in _ultimos_logs:
            raw = _linha_bruta(r)
            linha = {k: raw[k] for k in ativos if k in raw}
            linha["id"] = r[0]
            if "acao" in conjunto:
                cor = CORES_ACAO.get(raw["acao"])
                linha["acao"] = (f'<span style="color:{cor};font-weight:600">'
                                 f'{raw["acao"]}</span>' if cor else raw["acao"])
            if "descricao" in conjunto:
                d = raw["descricao"]
                linha["descricao"] = d[:100] + ("..." if len(d) > 100 else "")
            if "hash" in conjunto:
                linha["hash"] = raw["hash"] or "-"
            linhas.append(linha)
        tabela.rows = linhas
        tabela.update()

    def _atualizar_tabela(pagina=1, reset=False):
        nonlocal pagina_atual, total_registros, total_paginas, _ultimos_logs
        if reset or not pagina:
            pagina = 1
        pagina_atual = max(1, pagina)
        rows, total = _buscar_logs(
            filtro_usuario=filtro_usuario.value or "",
            filtro_modulo="",
            filtro_acao=filtro_acao.value or "",
            data_inicio=holder_inicio["data"] or "",
            data_fim=holder_fim["data"] or "",
            filtro_hora=filtro_hora.value or "",
            pagina=pagina_atual,
        )
        total_registros = total
        total_paginas = max(1, -(-total // limite_sql)) if total else 1
        if pagina_atual > total_paginas:
            pagina_atual = total_paginas
            rows, _ = _buscar_logs(
                filtro_usuario=filtro_usuario.value or "",
                filtro_modulo="",
                filtro_acao=filtro_acao.value or "",
                data_inicio=holder_inicio["data"] or "",
                data_fim=holder_fim["data"] or "",
                filtro_hora=filtro_hora.value or "",
                pagina=pagina_atual,
            )
        _ultimos_logs = rows
        _render_tabela()
        lbl_pagina.text = (f"{total_registros} registro(s) "
                           f"· página {pagina_atual} de {total_paginas}")
        btn_prev.disabled = pagina_atual <= 1
        btn_next.disabled = pagina_atual >= total_paginas
        log.info(f"busca de logs concluida | pagina={pagina_atual} total={total_registros}")

    def _exportar_csv():
        ativos = _campos_ativos()
        if not _ultimos_logs:
            ui.notify("Nada a exportar — execute uma busca primeiro.", type="warning")
            return
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow([_LABEL[c] for c in ativos])
        for r in _ultimos_logs:
            raw = _linha_bruta(r)
            w.writerow([raw.get(c, "") for c in ativos])
        nome = f"auditoria_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        ui.download(buf.getvalue().encode("utf-8"), nome)
        log.info(f"CSV exportado por {usuario_logado} | {len(_ultimos_logs)} linha(s)")

    def _limpar_filtros():
        nonlocal tabela_atual
        filtro_usuario.value = ""
        nav_tabela.value = ""
        tabela_atual = None
        filtro_acao.value = ""
        filtro_hora.value = ""
        _limpar_inicio()
        _limpar_fim()
        _atualizar_tabela(reset=True)

    def _mover_campo(i, delta):
        ativos = _campos_ativos()
        j = i + delta
        if i < 0 or j < 0 or j >= len(ativos):
            return
        ativos[i], ativos[j] = ativos[j], ativos[i]
        _salvar_campos(ativos)
        _rebuild_painel_campos()
        _render_tabela()

    def _remover_campo(chave):
        ativos = [c for c in _campos_ativos() if c != chave]
        _salvar_campos(ativos)
        _rebuild_painel_campos()
        _render_tabela()

    def _adicionar_campo(chave):
        if not chave:
            return
        ativos = _campos_ativos()
        if chave not in ativos:
            ativos.append(chave)
            _salvar_campos(ativos)
        _rebuild_painel_campos()
        _render_tabela()

    def _restaurar_campos():
        _salvar_campos([c for c, _ in CAMPOS])
        _rebuild_painel_campos()
        _render_tabela()

    # ---------- UI ----------
    cabecalho("Auditoria", texto_header, cor_borda="#C62828",
              cor_titulo=t_cor_titulo, cor_fundo=t_cor_fundo)
    obs_ligado = _dd.otel_stack_rodando()
    tabs_el = abas("Logs", "history", admin=eh_admin_geral,
                   observabilidade=obs_ligado)
    with ui.tab_panels(tabs_el, value="principal").classes("w-full"):
        with ui.tab_panel("principal"):
            with ui.row().classes("w-full gap-3 flex-wrap mb-3 items-end"):
                filtro_usuario = ui.input("Filtrar usuário").props("outlined dense").classes("w-40")

                # Navegação DINÂMICA por tabela de auditoria: cada módulo que
                # grava auditoria tem a sua tabela (tb_auditoria_<modulo>). O
                # menu é montado automaticamente a partir do banco, então novos
                # módulos aparecem aqui sem editar o módulo de auditoria.
                nav_opcoes = _opcoes_navegacao()
                nav_tabela = ui.select(nav_opcoes, value="", label="Visualizar auditoria de") \
                    .props("outlined dense").classes("w-64")

                def _on_navegar():
                    nonlocal tabela_atual, pagina_atual
                    tabela_atual = nav_tabela.value or None
                    log.info(f"[DIAG] _on_navegar -> nav_tabela.value={nav_tabela.value!r} tabela_atual={tabela_atual!r}")
                    _atualizar_tabela(reset=True)

                nav_tabela.on_value_change(_on_navegar)

                # Categorias de ação prontas (cores por tipo) + texto livre.
                opcoes_acao = {"": "Todas as ações"}
                for acao in sorted(CORES_ACAO):
                    opcoes_acao[acao] = acao
                filtro_acao = ui.select(opcoes_acao, value="", label="Filtrar ação",
                                        with_input=True, new_value_mode="add-last") \
                    .props("outlined dense").classes("w-60")

                filtro_hora = ui.input("Filtrar hora (HH:MM)").props("outlined dense").classes("w-40")

                # Datas em modo "clicar para exibir": um campo compacto que só
                # mostra o calendário (popup) quando o usuário clica — evita o
                # calendário aberto o tempo todo e melhora a UX.
                def _fmt_data(iso):
                    if not iso:
                        return ""
                    try:
                        return datetime.strptime(iso, "%Y-%m-%d").strftime("%d/%m/%Y")
                    except (ValueError, TypeError):
                        return iso

                def _campo_data(rotulo):
                    """Campo de data com calendário em popup (abre só ao clicar)."""
                    campo = ui.input(rotulo, placeholder="dd/mm/aaaa") \
                        .props("outlined dense readonly").classes("w-40")
                    menu = ui.menu().props("no-parent-event")
                    holder = {"data": None, "cal": None}

                    def _abrir():
                        if holder["cal"] is not None:
                            holder["cal"].value = holder["data"]
                        menu.open()

                    campo.on('click', _abrir)

                    with menu:
                        cal = ui.date(value=None).props("mask YYYY-MM-DD")

                        def _ao_escolher(e):
                            holder["data"] = e.value
                            campo.value = _fmt_data(e.value)
                            menu.close()

                        cal.on_value_change(_ao_escolher)
                        holder["cal"] = cal

                    def _limpar():
                        holder["data"] = None
                        campo.value = ""

                    return campo, holder, _limpar

                data_inicio, holder_inicio, _limpar_inicio = _campo_data("Data inicial")
                data_fim, holder_fim, _limpar_fim = _campo_data("Data final")
                ui.button("Buscar", icon="search",
                      on_click=lambda: _atualizar_tabela(reset=True)) \
                    .props("unelevated").classes(_btn_cls()).style(_btn_style())
                ui.button("Limpar", icon="clear", on_click=_limpar_filtros).props("flat")
                ui.button("Exportar CSV", icon="download", on_click=_exportar_csv) \
                    .props("outline").classes(_btn_cls()).style(_btn_style())

            # ----- Painel: campos visíveis e ordem (por auditor) -----
            with ui.expansion("Campos e ordem de exibição", icon="view_column").classes("w-full mb-2"):
                painel_campos = ui.column().classes("w-full gap-1")

                def _rebuild_painel_campos():
                    painel_campos.clear()
                    ativos = _campos_ativos()
                    ocultos = [c for c, _ in CAMPOS if c not in ativos]
                    with painel_campos:
                        ui.label("Ajuste quais campos aparecem e a ordem da tabela "
                                 "(preferência salva para este auditor).") \
                            .classes("text-caption text-grey-6")
                        for i, chave in enumerate(ativos):
                            with ui.row().classes("items-center gap-1 w-full"):
                                ui.icon("drag_indicator").classes("text-grey-5")
                                ui.label(_LABEL[chave]).classes("w-40")
                                ui.button("arrow_upward",
                                          on_click=lambda i=i: _mover_campo(i, -1)) \
                                    .props("flat dense size=sm")
                                ui.button("arrow_downward",
                                          on_click=lambda i=i: _mover_campo(i, +1)) \
                                    .props("flat dense size=sm")
                                ui.button("close", on_click=lambda c=chave: _remover_campo(c)) \
                                    .props("flat dense size=sm color=negative") \
                                    .tooltip("Ocultar campo")
                        if ocultos:
                            with ui.row().classes("items-center gap-2"):
                                sel_adicionar = ui.select(
                                    {c: _LABEL[c] for c in ocultos},
                                    label="Adicionar campo", value=None) \
                                    .props("outlined dense").classes("w-56")
                                ui.button("Adicionar",
                                          on_click=lambda: _adicionar_campo(sel_adicionar.value)) \
                                    .props("unelevated dense color=primary")
                        ui.button("Restaurar padrão", icon="restore",
                                  on_click=_restaurar_campos).props("flat dense")

                _rebuild_painel_campos()

            colunas_iniciais = [{"name": c, "label": l, "field": c} for c, l in CAMPOS]
            tabela = ui.table(columns=colunas_iniciais, rows=[], row_key="id") \
                .props("flat bordered dense").classes("w-full")
            # Coluna "Ação" com cor por categoria: o Quasar (v2) não renderiza a
            # flag `html` das colunas, então injetamos um slot de corpo customizado
            # que renderiza o HTML preparado em _linha_bruta via v-html.
            tabela.add_slot("body-cell-acao", """
                <q-td :props="props"><span v-html="props.value"></span></q-td>
            """)

            with ui.row().classes("w-full items-center justify-between mt-2"):
                btn_prev = ui.button("Anterior", icon="chevron_left",
                                     on_click=lambda: _atualizar_tabela(
                                         pagina=pagina_atual - 1)).props("flat")
                lbl_pagina = ui.label("").classes("text-caption text-grey-7")
                btn_next = ui.button("Próxima", icon="chevron_right",
                                     on_click=lambda: _atualizar_tabela(
                                         pagina=pagina_atual + 1)).props("flat")

        with ui.tab_panel("adm"):
            if eh_admin_geral:
                ui.separator()
                with ui.expansion("Administração", icon="admin_panel_settings").classes("w-full mt-4"):
                    with ui.card().classes("w-full"):
                        with ui.card_section().classes("gap-3 w-full"):
                            ui.label("Configurações da Auditoria").classes("text-h6 font-bold")
                            inp_limite = ui.number("Limite de linhas por página (LIMIT SQL)",
                                                   value=int(limite_sql), min=10, max=10000) \
                                .props("outlined dense")
                            inp_retencao = ui.number("Retenção (dias)", value=int(retencao_dias),
                                                     min=1, max=3650).props("outlined dense")
                            inp_header = ui.input("Texto do cabeçalho",
                                                  value=texto_header) \
                                .props("outlined dense").classes("w-full")

                            ui.separator().classes("my-2")
                            ui.label("Aparência — temas dos botões desta tela").classes(
                                "text-subtitle2 text-grey-7")
                            with ui.grid(columns=2).classes("w-full gap-3 max-sm:grid-cols-1"):
                                inp_cor_botao = ui.color_input(label="Cor dos botões",
                                                               value=t_cor_botao) \
                                    .props("outlined dense").classes("w-full")
                                inp_cor_txt = ui.color_input(label="Cor do texto dos botões",
                                                             value=t_cor_txt_botao) \
                                    .props("outlined dense").classes("w-full")
                                inp_cor_fundo = ui.color_input(
                                    label="Cor de fundo da página (vazio = herda)",
                                    value=t_cor_fundo) \
                                    .props("outlined dense").classes("w-full")
                                inp_cor_titulo = ui.color_input(label="Cor dos títulos",
                                                                value=t_cor_titulo) \
                                    .props("outlined dense").classes("w-full")
                            sel_tamanho = ui.select(
                                {0: "Pequeno", 1: "Médio", 2: "Grande"},
                                label="Tamanho dos botões",
                                value={"small": 0, "medium": 1, "large": 2}.get(t_btn_tamanho, 1),
                            ).props("outlined dense").classes("w-full")
                            _tamanhos = {0: "small", 1: "medium", 2: "large"}

                            def _salvar():
                                try:
                                    set_config("auditoria_limite", inp_limite.value)
                                    set_config("auditoria_retencao_dias", inp_retencao.value)
                                    set_config("auditoria_texto_header", inp_header.value)
                                    set_config("auditoria_cor_botao", inp_cor_botao.value or "")
                                    set_config("auditoria_cor_texto_botao", inp_cor_txt.value or "")
                                    set_config("auditoria_cor_fundo", inp_cor_fundo.value or "")
                                    set_config("auditoria_cor_titulo", inp_cor_titulo.value or "")
                                    set_config("auditoria_btn_tamanho",
                                              _tamanhos[sel_tamanho.value])
                                    nonlocal limite_sql, retencao_dias, texto_header
                                    limite_sql = max(10, int(inp_limite.value))
                                    retencao_dias = str(inp_retencao.value)
                                    texto_header = inp_header.value
                                    audit_log(usuario_logado, "auditoria", "configuracao",
                                              "configurações do módulo de auditoria alteradas: "
                                              "limite, retenção, cabeçalho e aparência")
                                    ui.notify("Configurações salvas", type="positive")
                                    log.info("configuracoes da auditoria salvas")
                                    _atualizar_tabela(reset=True)
                                except Exception:
                                    log.exception("falha ao salvar configuracoes da auditoria")
                                    ui.notify("Erro ao salvar configurações", type="negative")

                            ui.button("Salvar", icon="save", on_click=_salvar) \
                                .props("unelevated").style(_btn_style())
                campo_modulo(usuario_logado, "auditoria")
            _atualizar_tabela()
            ui.timer(30.0, _atualizar_tabela)

        if obs_ligado:
            with ui.tab_panel("obs"):
                with ui.row().classes("w-full gap-2 items-center mb-1"):
                    ui.icon("query_stats").classes("text-primary text-2xl")
                    ui.label("Observabilidade OpenTelemetry (Grafana)").classes(
                        "text-h6 font-bold")
                ui.label("Dashboards de telemetria do sistema, servidos pelo Grafana "
                         "(LGTM: Loki, Grafana, Tempo, Mimir + OTel Collector). "
                         "Abra os links em nova aba para inspecionar métricas, "
                         "traces e logs gerados pela aplicação.").classes(
                    "text-caption text-grey-7 max-w-3xl -mt-1")

                _dashboards = [
                    ("Visão Geral (Intranet)", "intranet-visao-geral", "monitor_heart",
                     "Métricas agregadas da Intranet via Mimir"),
                    ("Traces", "intranet-traces", "timeline",
                     "Tracing distribuído via Tempo (span de requisições)"),
                    ("Logs", "intranet-logs", "subject",
                     "Logs centralizados via Loki (fluem pelo OTel Collector)"),
                ]
                with ui.row().classes("w-full flex-wrap gap-2 items-stretch mt-2"):
                    for titulo, uid, icone, desc in _dashboards:
                        _url = f"http://localhost:3000/d/{uid}/{uid}"
                        with ui.card().classes(
                                "cursor-pointer hover:shadow-lg transition-shadow "
                                "border border-grey-3 rounded-lg p-2 flex-1 "
                                "min-w-[220px]") \
                                .on("click",
                                    lambda u=_url: ui.navigate.to(u, new_tab=True)) \
                                .tooltip(desc):
                            with ui.row().classes("gap-2 items-center"):
                                ui.icon(icone).classes("text-primary text-2xl")
                                ui.label(titulo).classes("font-bold")
                            ui.label("Abrir dashboard em nova aba").classes(
                                "text-caption text-grey-6 pt-1")
                ui.html("<div class='text-caption text-grey-6 pt-2 q-px-sm'>"
                        "Grafana: <b>http://localhost:3000</b> — usuário <b>master</b> "
                        "/ senha <b>master</b></div>")
                ui.html(
                    "<div class='flex items-start gap-3 rounded-lg border-l-4 p-3' "
                    "style='background:#FFF3E0; border-left-color:#E65100'>"
                    "<span style='color:#BF360C;font-size:1.75rem;line-height:1'>⚠</span>"
                    "<div class='flex-1'>"
                    "<div class='text-body2 font-bold' style='color:#BF360C'>"
                    "Atenção (segurança de dados):</div>"
                    "<div class='text-body2 mt-1' style='color:#3E2723'>"
                    "O acesso ao Grafana é feito com a senha padrão <b>master</b>. "
                    "Por questões de segurança e de conformidade legal, cabe ao "
                    "<b>primeiro usuário administrador</b> trocar essa senha após o "
                    "primeiro acesso. Essa obrigação decorre dos princípios de "
                    "segurança previstos na <b>LGPD (Lei nº 13.709/2018)</b>, em "
                    "especial o inciso VII do art. 6º e o art. 46, bem como da "
                    "<b>Lei do Governo Digital (Lei nº 14.129/2021)</b> e do "
                    "<b>Marco Civil da Internet (Lei nº 12.965/2014)</b>. "
                    "<b>Fica registrado que não existe possibilidade de resetar a "
                    "senha do Grafana</b> caso seja perdida — guarde-a em local "
                    "seguro.</div></div></div>"
                )