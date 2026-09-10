"""Administration panel for the Empenho Renamer module.

Panel de administrao do Renomeador de Empenhos: pastas monitoradas,
aparência, template de nome, campos de busca, auditoria, quarentena e
regras regex dinâmicas.
"""
from nicegui import ui

from mod_intranet import observabilidade
_log = observabilidade.get_logger("renomear_empenho")

from mod_intranet.ui_comum import card_admin, botao, botao_icone, \
    rodape_salvar_restaurar
from mod_intranet.tema_modulo import bloco_aparencia, ler_tema, notificar
from mod_renomear_empenho.bd_manipulador import (
    pastas_monitoradas, salvar_pastas_monitoradas,
    template_nome_atual, montar_nome_final, NOME_FINAL_PADRAO,
    listar_campos_busca, salvar_campo_busca, excluir_campo_busca,
    restaurar_campos_busca_padrao,
    listar_arquivos_auditoria, listar_quarentena, reprocesse_quarentena,
    listar_regras, salvar_regra, alternar_regra,
)
from mod_intranet import rotinas as _rotinas
from mod_intranet.bd_manipulador import audit_log


def _tema(chave, default, get_config):
    try:
        return (get_config(f"empenhos_{chave}", default) or "").strip() or default
    except Exception:
        return default


def mostrar_administracao(
    usuario_logado: str,
    eh_admin: bool,
    t_cor_botao: str,
    t_cor_txt_botao: str,
    t_cor_fundo: str,
    t_cor_titulo: str,
    t_tamanho: str,
    texto_header: str,
    _btn_cls,
    _btn_style,
    get_config,
    set_config,
):
    """Renders the full administration panel for the Empenho Renamer.

    Monta todas as abas de administração: pastas monitoradas, aparência,
    template do nome final, campos de busca, auditoria, Quarentena e regras
    regex. Recebe os parâmetros de tema já resolvidos; usa get_config /
    set_config do módulo de conexão para ler/gravar em tb_config.

    Args:
        usuario_logado: Nome do usuário autenticado.
        eh_admin: Indica se o usuário tem privilégios de administrador.
        t_cor_botao: Cor de fundo dos botões (hex).
        t_cor_txt_botao: Cor do texto do módulo (hex).
        t_cor_fundo: Cor de fundo da página (hex ou vazio).
        t_cor_titulo: Cor dos títulos (hex).
        t_tamanho: Tamanho dos botões ("small", "medium" ou "large").
        texto_header: Texto do cabeçalho da página.
        _btn_cls: Callable que retorna as classes CSS dos botões.
        _btn_style: Callable que retorna o estilo inline dos botões.
        get_config: Função get_config(chave, default) do módulo de conexão.
        set_config: Função set_config(chave, valor) do módulo de conexão.
    """
    try:
        from mod_renomear_empenho.bd_manipulador import _PASTA_MONITORADA_PADRAO
    except Exception:
        _PASTA_MONITORADA_PADRAO = ""

    # ================= Pastas monitoradas =================
    with card_admin("Pastas monitoradas (inclui rede/UNC)", icone="folder_open",
                    chave_modulo="empenhos", extra_classes="mt-4", grade=False):
        ui.label(
            "Uma pasta por linha. Caminhos locais ou de rede/UNC "
            "(ex.: \\\\servidor\\empenhos ou E:\\scan). Cada linha é monitorada "
            "na raiz (não recursivo), permitindo vários computadores/scaners."
        ).classes("text-caption text-grey-6")
        inp_pastas = ui.textarea(
            "Pastas monitoradas (uma por linha)",
            value="\n".join(pastas_monitoradas())
        ).props("outlined dense").classes("w-full")

        def salvar_pastas():
            """Saves the monitored folders and reloads after 1s.

            Grava as pastas monitoradas (uma por linha, local/UNC) e
            recarrega após 1 segundo — aplicação sem restart."""
            linhas = [l.strip() for l in (inp_pastas.value or "").splitlines() if l.strip()]
            salvar_pastas_monitoradas(linhas)
            notificar("Pastas monitoradas aplicadas — recarregando…", type="positive")
            ui.timer(1.0, lambda: ui.navigate.reload(), once=True)

        def restaurar_pastas():
            """Restores the default monitored folders and reloads after 1s.

            Restaura as pastas monitoradas para o padrão codificado
            (`_PASTA_MONITORADA_PADRAO`) e recarrega após 1 segundo."""
            try:
                salvar_pastas_monitoradas(
                    [p for p in (_PASTA_MONITORADA_PADRAO or "").splitlines() if p.strip()])
            except Exception:
                pass
            notificar("Pastas monitoradas restauradas ao padrão — recarregando…",
                      type="positive")
            ui.timer(1.0, lambda: ui.navigate.reload(), once=True)

        rodape_salvar_restaurar(salvar_pastas, restaurar=restaurar_pastas,
                                chave_modulo="empenhos")

    # ================= Configurações de cores (padrão) =================
    _tema_emp = ler_tema("empenhos", cor_botao=t_cor_botao,
                         cor_texto_botao=t_cor_txt_botao, cor_fundo=t_cor_fundo,
                         cor_titulo=t_cor_titulo, btn_tamanho=t_tamanho,
                         texto_header=texto_header)
    _tema_emp["_defaults"] = {
        "cor_botao": "",
        "cor_texto_botao": "",
        "cor_fundo": "",
        "cor_titulo": "#212121",
        "btn_tamanho": "medium",
        "texto_header": "",
        "cor_fundo_card": "#FFFFFF",
        "cor_texto_card": "",
    }
    bloco_aparencia(usuario_logado, "empenhos", _tema_emp,
                    prefixo_auditoria="renomear-empenho", com_texto_header=False)

    # ================= Configurações específicas =================
    with card_admin("Configurações específicas", icone="tune",
                    chave_modulo="empenhos", extra_classes="mt-2", grade=False):
        ui.label("Texto do cabeçalho, intervalo do monitor e permissão de "
                 "download para usuários comuns.").classes("text-subtitle2 text-grey-7")
        inp_texto = ui.input("Texto do cabeçalho", value=texto_header).props("outlined dense").classes("w-full")
        inp_intervalo = ui.input(
            "Intervalo do monitor automático (segundos — recomendado 60)",
            value=str(_rotinas.intervalo_monitor_empenho())
        ).props("outlined dense").classes("w-full")             .tooltip("Varredura automática das pastas monitoradas (RF-40). Aplicado sem reiniciar.")

        sw_autorizar = ui.switch(
            "Autorizar download/ZIP/e-mail para usuários comuns",
            value=get_config("empenhos_autorizar_download", "0") == "1"
        ).props("dense")             .tooltip("Quando ativo, usuários comuns podem baixar/enviar os empenhos (RF-39).")

        def salvar():
            """Applies the module-specific settings and reloads after 1s.

            Grava texto do cabeçalho, intervalo do monitor (reagendado ao
            vivo) e permissão de download para usuários comuns; audita,
            notifica e recarrega após 1 segundo. Falha registra loguru."""
            try:
                set_config("empenhos_texto_header", (inp_texto.value or "").strip())
                set_config("empenhos_autorizar_download", "1" if sw_autorizar.value else "0")
                try:
                    iv = max(1, int((inp_intervalo.value or "60").strip() or 60))
                    set_config("empenhos_monitor_intervalo_seg", str(iv))
                    _rotinas.reagendar_monitor_empenho(iv)
                except Exception as ex:
                    _log.warning(f"intervalo monitor não aplicado: {ex}")
                try:
                    audit_log(usuario_logado, "renomear-empenho", "configuracao",
                              "configurações específicas do módulo salvas")
                except Exception:
                    pass
                _log.info(f"configurações específicas salvas por {usuario_logado}")
                notificar("Configurações específicas aplicadas — recarregando…",
                          type="positive")
                ui.timer(1.0, lambda: ui.navigate.reload(), once=True)
            except Exception:
                _log.exception("erro ao salvar configurações específicas de empenhos")

        def restaurar():
            """Restores the module-specific defaults and reloads after 1s.

            Restaura texto do cabeçalho vazio, download desautorizado e
            intervalo do monitor 60 s (reagendado ao vivo); audita, notifica
            e recarrega após 1 segundo. Falha registra loguru."""
            try:
                set_config("empenhos_texto_header", "")
                set_config("empenhos_autorizar_download", "0")
                set_config("empenhos_monitor_intervalo_seg", "60")
                try:
                    _rotinas.reagendar_monitor_empenho(60)
                except Exception as ex:
                    _log.warning(f"intervalo monitor não reagendado: {ex}")
                try:
                    audit_log(usuario_logado, "renomear-empenho", "configuracao",
                              "configurações específicas restauradas ao padrão")
                except Exception:
                    pass
                notificar("Padrões restaurados — recarregando…", type="positive")
                ui.timer(1.0, lambda: ui.navigate.reload(), once=True)
            except Exception:
                _log.exception("erro ao restaurar padrões de empenhos")

        rodape_salvar_restaurar(salvar, restaurar=restaurar,
                                chave_modulo="empenhos")

    # ================= Template de nome final =================
    with card_admin(
        "Nome final do arquivo (template configurável)",
        icone="drive_file_rename_outline",
        chave_modulo="empenhos", extra_classes="mt-2", grade=False,
    ):
        ui.label(
            "Formato do nome atribuído aos PDFs renomeados. Variáveis: "
            "{contador}, {empenho}, {empenho_cru}, {parcela}, {ficha}, {ano}. "
            "Suporta formatação de largura, ex.: {contador:04d}, {parcela:03d}."
        ).classes("text-caption text-grey-6")
        ui.label(
            "Tipos especiais (EC/EE/EG/AE) usam nome próprio: EC_0024.pdf, "
            "EE_9570.pdf, EG_0089.pdf."
        ).classes("text-caption text-grey-6")
        inp_template = ui.input(
            "Template do nome final", value=template_nome_atual()
        ).props("outlined dense").classes("w-full") \
            .tooltip(f"Padrão: {NOME_FINAL_PADRAO}")

        def _preview_template():
            try:
                preview_nome = montar_nome_final(
                    inp_template.value or NOME_FINAL_PADRAO, 7,
                    {"empenho": "0000345", "ficha": "0000331", "ano": "2026"}
                )
            except Exception as e:
                preview_nome = f"(erro: {e})"
            lbl_preview.set_text(f"Nome de exemplo: {preview_nome}")

        lbl_preview = ui.label("")
        inp_template.on("update:model-value", lambda e: _preview_template())
        _preview_template()

        def salvar_template():
            t = (inp_template.value or "").strip()
            if not t:
                set_config("empenhos_template_nome", "")
                ui.notify("Template vazio — usando o padrão do módulo", type="info")
            else:
                try:
                    montar_nome_final(t, 1, {"empenho": "1", "ficha": "1", "ano": "2026"})
                except Exception as e:
                    ui.notify(f"Template inválido: {e}", type="negative")
                    return
                set_config("empenhos_template_nome", t)
            try:
                audit_log(usuario_logado, "renomear-empenho", "configuracao",
                          "template de nome atualizado")
            except Exception:
                pass
            ui.notify("Template de nome salvo (vale sem reiniciar)", type="positive")

        def restaurar_template():
            set_config("empenhos_template_nome", "")
            ui.timer(0.1, lambda: ui.navigate.reload(), once=True)

        with ui.row().classes("w-full justify-end gap-2 mt-2"):
            botao("Usar padrão", on_click=restaurar_template,
                  variante="texto", chave_modulo="empenhos")
            botao("Salvar template", icone="save", on_click=salvar_template,
                  variante="solido", chave_modulo="empenhos")

    # ================= Campos de busca (regex) =================
    with card_admin("Campos de busca (regex de identificação)",
                    icone="manage_search", chave_modulo="empenhos",
                    extra_classes="mt-2", grade=False):
        ui.label(
            "Regex usadas para identificar cada campo. O 1º grupo é o valor; "
            "o 2º, se houver, é o ano. Edite sem reiniciar."
        ).classes("text-caption text-grey-6")
        lista_campos = ui.column().classes("w-full mt-1")

        def _refresh_campos():
            lista_campos.clear()
            if not listar_campos_busca():
                with lista_campos:
                    ui.label("Sem campos cadastrados — clique em 'Restaurar padrão'.") \
                        .classes("text-caption text-grey-5")
                return
            with lista_campos:
                for cid, campo, rotulo, padrao, ativo in listar_campos_busca():
                    with ui.row().classes("w-full items-center gap-2 py-1"):
                        ui.icon("bolt" if ativo else "block").classes(
                            "text-green-7" if ativo else "text-grey-5")
                        ui.label(f"{rotulo}").classes("font-medium w-28")
                        ui.code(padrao).style("flex:1; overflow-x:auto")
                        if not ativo:
                            ui.badge("inativa", color="grey")
                        botao_icone("delete", on_click=lambda c=cid: _del_campo(c),
                                        chave_modulo="empenhos").tooltip("Excluir campo")

        def _del_campo(cid):
            excluir_campo_busca(cid)
            _refresh_campos()

        _refresh_campos()

        with ui.row().classes("w-full items-end gap-2 flex-wrap mt-2"):
            f_campo = ui.input("Campo (chave)").props("outlined dense").classes("w-36")
            f_rotulo = ui.input("Rótulo").props("outlined dense").classes("w-40")
            f_padrao = ui.input(
                "Regex (o 1º grupo é o valor)", placeholder=r"...(\d+)..."
            ).props("outlined dense").classes("grow min-w-[240px]")
            f_ativo = ui.switch("Ativa", value=True).props("dense")

            def salvar_campo():
                ok, msg = salvar_campo_busca(
                    f_campo.value or "", f_rotulo.value or "",
                    f_padrao.value or "", bool(f_ativo.value)
                )
                ui.notify(msg, type="positive" if ok else "negative")
                if ok:
                    f_campo.set_value(None)
                    f_rotulo.set_value(None)
                    f_padrao.set_value(None)
                    _refresh_campos()

            botao("Salvar campo", icone="save", on_click=salvar_campo,
                  variante="solido", chave_modulo="empenhos")

        with ui.row().classes("w-full justify-end gap-2 mt-2"):
            def restaurar_campos():
                restaurar_campos_busca_padrao()
                _refresh_campos()
                ui.notify("Campos de busca restaurados ao padrão", type="positive")

            botao("Restaurar padrão", icone="restore", on_click=restaurar_campos,
                  variante="restaurar", chave_modulo="empenhos")

    # ================= Auditoria =================
    with card_admin(
        "Auditoria dos arquivos escaneados / renomeados",
        icone="history",
        chave_modulo="empenhos", extra_classes="mt-2", grade=False,
    ):
        colunas_aud = [
            {"name": "nome_orig", "label": "Origem", "field": "nome_orig", "align": "left"},
            {"name": "nome_final", "label": "Nome final", "field": "nome_final", "align": "left"},
            {"name": "num", "label": "Empenho", "field": "num", "align": "left"},
            {"name": "parc", "label": "Parc", "field": "parc"},
            {"name": "ficha", "label": "Ficha", "field": "ficha"},
            {"name": "ano", "label": "Ano", "field": "ano"},
            {"name": "status", "label": "Status", "field": "status"},
            {"name": "usr", "label": "Usuário", "field": "usr"},
            {"name": "dt", "label": "Renomeado em", "field": "dt"},
        ]
        filtro_status = ui.select(
            {
                "": "Todos",
                "renomeado": "Renomeado",
                "detectado": "Detectado",
                "erro": "Erro",
                "removido": "Removido",
            },
            label="Status", value=""
        ).props("outlined dense").classes("w-56")
        tabela_aud = ui.table(
            columns=colunas_aud, rows=[], row_key="id"
        ).props("flat bordered dense").classes("w-full")

        def _refresh_aud():
            sel = filtro_status.value or None
            tabela_aud.rows = [
                {
                    "id": r[0], "nome_orig": r[1] or "—", "nome_final": r[2] or "—",
                    "num": r[3] or "—", "parc": r[4] or "—", "ficha": r[5] or "—",
                    "ano": r[6] or "—", "status": r[7] or "—",
                    "usr": (r[8] or "—")[:12], "dt": (r[10] or "")[:16]
                }
                for r in listar_arquivos_auditoria(status=sel)
            ]
            tabela_aud.update()

        filtro_status.on("update:model-value", lambda e: _refresh_aud())
        _refresh_aud()

    # ================= Quarentena =================
    with card_admin("Quarentena", icone="block", chave_modulo="empenhos",
                    extra_classes="mt-2", grade=False):
        colunas_q = [
            {"name": "arquivo", "label": "Arquivo", "field": "arquivo", "align": "left"},
            {"name": "motivo", "label": "Motivo", "field": "motivo", "align": "left"},
            {"name": "data", "label": "Recebido em", "field": "data"},
            {"name": "qid", "label": "", "field": "qid"},
        ]
        tabela_q = ui.table(
            columns=colunas_q, rows=[], row_key="qid"
        ).props("flat bordered dense").classes("w-full")

        def _refresh_q():
            tabela_q.rows = [
                {"qid": r[0], "arquivo": r[1], "motivo": (r[2] or "")[:80], "data": (r[3] or "")[:16]}
                for r in listar_quarentena() if not r[4]
            ]
            tabela_q.update()

        def on_q_click(e):
            linha = e.args[1]
            with ui.dialog() as dlg, ui.card().classes("w-[480px]"):
                ui.label("Reprocessar com nova regex").classes("text-h6")
                ui.label(linha["arquivo"]).classes("text-caption text-grey-6")
                padrao = ui.input("Regex alternativa (opcional)").props("outlined dense").classes("w-full")

                def tentar():
                    try:
                        ok, msg = reprocesse_quarentena(linha["qid"], padrao.value or None, usuario_logado)
                        ui.notify(("Sucesso: " + msg) if ok else ("Falha: " + msg),
                                  type="positive" if ok else "warning")
                        dlg.close()
                        _refresh_q()
                    except Exception:
                        _log.exception(f"erro ao reprocessar Quarentena qid={linha['qid']}")

                with ui.row().classes("w-full justify-end gap-2 mt-2"):
                    botao("Cancelar", on_click=dlg.close,
                        variante="texto", chave_modulo="empenhos")
                    botao("Reprocessar", on_click=tentar,
                        variante="solido", chave_modulo="empenhos")
            dlg.open()

        tabela_q.on("row-click", on_q_click)
        _refresh_q()

    # ================= Regras regex dinâmicas =================
    with card_admin("Regras de extração (regex dinâmicas)", icone="rule",
                    chave_modulo="empenhos", extra_classes="mt-2", grade=False):
        lista_regras = ui.column().classes("w-full")

        def _refresh_regras():
            lista_regras.clear()
            with lista_regras:
                for rid, nome, padrao, ativo, destino in listar_regras():
                    with ui.row().classes("w-full items-center gap-2 py-1"):
                        ui.icon("bolt" if ativo else "block").classes(
                            "text-orange-7" if ativo else "text-grey-5")
                        ui.label(nome).classes("font-medium w-40")
                        ui.code(padrao).style("flex:1; overflow-x:auto")
                        if destino:
                            ui.badge(f"→ {destino}", color="purple").props("outline")
                        if not ativo:
                            ui.badge("inativa", color="grey")

                    def _toggle(r=rid, a=ativo):
                        ok, msg = alternar_regra(r, not a)
                        ui.notify(msg, type="positive" if ok else "negative")
                        _refresh_regras()

                    botao("Inativar" if ativo else "Ativar", on_click=_toggle,
                          variante="texto", compacto=True, chave_modulo="empenhos")

        _refresh_regras()

        with ui.row().classes("w-full items-end gap-2 flex-wrap mt-2"):
            n_nome = ui.input("Nome da regra").props("outlined dense").classes("w-44")
            n_padrao = ui.input(
                "Padrão (regex)", placeholder=r"empenho\s*n[ºo]?\s*(\d+)"
            ).props("outlined dense").classes("grow min-w-[240px]")
            n_destino = ui.input("Campo FTS destino (opcional)") \
                .props("outlined dense").classes("w-56")

            def salvar_regra_handler():
                if not n_nome.value or not n_padrao.value:
                    ui.notify("Informe nome e padrão", type="warning")
                    return
                ok, msg = salvar_regra(
                    n_nome.value.strip(), n_padrao.value.strip(),
                    campo_destino=(n_destino.value or "").strip() or None
                )
                ui.notify(msg, type="positive" if ok else "negative")
                if ok:
                    n_nome.set_value(None)
                    n_padrao.set_value(None)
                    n_destino.set_value(None)
                    _refresh_regras()

            botao("Salvar regra", icone="save", on_click=salvar_regra_handler,
                  variante="solido", chave_modulo="empenhos")

    from mod_intranet.rotinas import painel_backup
    painel_backup(usuario_logado, "empenhos")
