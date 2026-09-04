"""Padrão visual comum de cabeçalho + abas dos módulos.

Segue o exemplo do módulo Editor de PDF: um card de cabeçalho (título +
subtítulo) seguido de uma barra de abas contendo a(s) aba(s) do próprio
módulo e a aba "Administração" (ícone `admin_panel_settings`), exibida
apenas para administradores.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from nicegui import ui


def cabecalho(titulo: str, subtitulo: str = "", cor_borda: str = "#1565C0",
              cor_titulo: str = "#212121", cor_fundo: str = ""):
    """Card de cabeçalho do módulo (título + subtítulo opcional).

    `cor_titulo`/`cor_fundo` seguem o padrão de aparência do módulo exemplo
    (Editor de PDF): cor dos títulos e cor de fundo da tela, aplicados sem restart.
    """
    with ui.card().classes("w-full border-l-8").style(f"border-left-color:{cor_borda}"):
        with ui.row().classes("w-full items-center justify-between flex-wrap gap-3"):
            with ui.column().classes("gap-0"):
                ui.label(titulo).classes("text-h5 font-bold").style(f"color:{cor_titulo}")
                if subtitulo:
                    ui.label(subtitulo).classes("text-caption text-grey-6")
    if cor_fundo:
        try:
            ui.query(".q-page").style(f"background-color:{cor_fundo}")
        except Exception:
            pass


def abas(titulo_principal: str, icone_principal: str, admin: bool = False,
         valor: str = "principal", observabilidade: bool = False):
    """Cria a barra de abas: aba principal + 'Administração' (se admin) +
    'Observabilidade' (se o serviço OTel/Grafana estiver rodando).

    Retorna o elemento `ui.tabs` para ser usado em `ui.tab_panels`.
    """
    tabs_el = ui.tabs(value=valor)
    with tabs_el:
        ui.tab("principal", label=titulo_principal, icon=icone_principal)
        if admin:
            ui.tab("adm", label="Administração", icon="admin_panel_settings")
        if observabilidade:
            ui.tab("obs", label="Observabilidade", icon="query_stats")
    return tabs_el
