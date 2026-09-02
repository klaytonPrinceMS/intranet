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
from mod_intranet.conexao_bd import get_config, set_config, get_connection
from mod_intranet.contexto import rotulo_dispositivo
from mod_intranet import observabilidade
from mod_intranet.aba_modulo import cabecalho, abas
from mod_intranet.manipulador_bd import audit_log

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
        conn = get_connection()
        try:
            cur = conn.cursor()
            where = " WHERE 1=1"
            params = []
            if filtro_usuario:
                where += " AND usuario LIKE ?"
                params.append(f"%{filtro_usuario}%")
            if filtro_modulo:
                where += " AND modulo = ?"
                params.append(filtro_modulo)
            if filtro_acao:
                where += " AND acao LIKE ?"
                params.append(f"%{filtro_acao}%")
            if filtro_hora:
                where += " AND strftime('%H:%M', timestamp) LIKE ?"
                params.append(f"%{filtro_hora}%")
            if data_inicio:
                where += " AND timestamp >= ?"
                params.append(f"{data_inicio} 00:00:00")
            if data_fim:
                where += " AND timestamp <= ?"
                params.append(f"{data_fim} 23:59:59")
            cur.execute(f"SELECT COUNT(*) FROM tb_auditoria{where}", params)
            total = cur.fetchone()[0]
            offset = max(0, (int(pagina) - 1) * limite_sql)
            sql = (f"SELECT id, usuario, modulo, acao, descricao, hash_arquivo,"
                   f" strftime('%d/%m/%Y %H:%M:%S', timestamp), ip, user_agent"
                   f" FROM tb_auditoria{where} ORDER BY id DESC LIMIT ? OFFSET ?")
            cur.execute(sql, params + [limite_sql, offset])
            return cur.fetchall(), total
        except Exception:
            log.exception("falha ao buscar logs de auditoria")
            return [], 0
        finally:
            conn.close()

    def _render_tabela():
        ativos = _campos_ativos()
        conjunto = set(ativos)
        colunas = []
        for chave, label in CAMPOS:
            if chave not in conjunto:
                continue
            col = {"name": chave, "label": label, "field": chave,
                   "align": "center" if chave == "data" else "left"}
            if chave == "acao":
                col["html"] = True
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
            filtro_modulo=filtro_modulo.value or "",
            filtro_acao=filtro_acao.value or "",
            data_inicio=data_inicio.value or "",
            data_fim=data_fim.value or "",
            filtro_hora=filtro_hora.value or "",
            pagina=pagina_atual,
        )
        total_registros = total
        total_paginas = max(1, -(-total // limite_sql)) if total else 1
        if pagina_atual > total_paginas:
            pagina_atual = total_paginas
            rows, _ = _buscar_logs(
                filtro_usuario=filtro_usuario.value or "",
                filtro_modulo=filtro_modulo.value or "",
                filtro_acao=filtro_acao.value or "",
                data_inicio=data_inicio.value or "",
                data_fim=data_fim.value or "",
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
        filtro_usuario.value = ""
        filtro_modulo.value = ""
        filtro_acao.value = ""
        filtro_hora.value = ""
        data_inicio.value = None
        data_fim.value = None
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
    tabs_el = abas("Logs", "history", admin=eh_admin_geral)
    with ui.tab_panels(tabs_el, value="principal").classes("w-full"):
        with ui.tab_panel("principal"):
            with ui.row().classes("w-full gap-3 flex-wrap mb-3 items-end"):
                filtro_usuario = ui.input("Filtrar usuário").props("outlined dense").classes("w-40")

                # Select de módulo DINÂMICO: módulos registrados (inclusive os
                # cadastrados depois) + produtores atuais da trilha (chaves reais).
                modulos_opcoes = {"": "Todos os módulos"}
                try:
                    from mod_intranet import autenticacao
                    for chave, nome, _i, _r, _a in autenticacao.modulos_registrados():
                        modulos_opcoes.setdefault(chave, nome or chave)
                except Exception:
                    pass
                for chave, nome in (
                    ("intranet", "Intranet (núcleo)"),
                    ("gest_cad_usuario", "Gestão de Usuários"),
                    ("blog", "Blog"),
                    ("edit-pdf", "Editor de PDF"),
                    ("renomear-empenho", "Renomear Empenhos"),
                    ("solicita_impressao", "Solicitação de Impressão"),
                    ("auditoria", "Auditoria"),
                ):
                    modulos_opcoes.setdefault(chave, nome)
                filtro_modulo = ui.select(modulos_opcoes, value="", label="Filtrar módulo") \
                    .props("outlined dense").classes("w-56")

                # Categorias de ação prontas (cores por tipo) + texto livre.
                opcoes_acao = {"": "Todas as ações"}
                for acao in sorted(CORES_ACAO):
                    opcoes_acao[acao] = acao
                filtro_acao = ui.select(opcoes_acao, value="", label="Filtrar ação",
                                        with_input=True, new_value_mode="add-last") \
                    .props("outlined dense").classes("w-60")

                filtro_hora = ui.input("Filtrar hora (HH:MM)").props("outlined dense").classes("w-40")
                with ui.expansion("Filtrar por data", icon="event").classes("w-auto self-end"):
                    with ui.row().classes("gap-3 items-end"):
                        with ui.column().classes("gap-0"):
                            ui.label("Data inicial").classes("text-caption text-grey-7")
                            data_inicio = ui.date(value=None).props("outlined dense")
                        with ui.column().classes("gap-0"):
                            ui.label("Data final").classes("text-caption text-grey-7")
                            data_fim = ui.date(value=None).props("outlined dense")
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
            _atualizar_tabela()
            ui.timer(30.0, _atualizar_tabela)