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


def cabecalho(titulo: str, subtitulo: str = "", cor_borda: str = "#1565C0"):
    """Card de cabeçalho do módulo (título + subtítulo opcional)."""
    with ui.card().classes("w-full border-l-8").style(f"border-left-color:{cor_borda}"):
        with ui.row().classes("w-full items-center justify-between flex-wrap gap-3"):
            with ui.column().classes("gap-0"):
                ui.label(titulo).classes("text-h5 font-bold text-grey-9")
                if subtitulo:
                    ui.label(subtitulo).classes("text-caption text-grey-6")


def abas(titulo_principal: str, icone_principal: str, admin: bool = False,
         valor: str = "principal"):
    """Cria a barra de abas: aba principal + aba 'Administração' (se admin).

    Retorna o elemento `ui.tabs` para ser usado em `ui.tab_panels`.
    """
    tabs_el = ui.tabs(value=valor)
    with tabs_el:
        ui.tab("principal", label=titulo_principal, icon=icone_principal)
        if admin:
            ui.tab("adm", label="Administração", icon="admin_panel_settings")
    return tabs_el
