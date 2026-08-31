"""Diálogo de gestão de backup DO MÓDULO — componente reutilizado no header.

Cada módulo gerencia o próprio banco: intervalo em horas, execução imediata
e histórico das cópias retidas. Acesso: administrador geral OU administrador
daquele módulo (validado por quem abre o diálogo).
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from nicegui import ui

from mod_intranet.conexao_bd import get_config, set_config
from mod_intranet.rotinas import (
    MAPA_BACKUPS, intervalo_backup, reagendar_backup,
    backup_modulo, listar_backups,
)
from mod_intranet.manipulador_bd import audit_log


def pode_gerenciar(usuario, chave_modulo):
    """Admin geral gerencia qualquer módulo; admin do módulo, só o seu."""
    from mod_intranet import autenticacao
    if autenticacao.perfil_global_de(usuario) == "administrador_geral":
        return True
    return autenticacao.eh_admin_do_modulo(usuario, chave_modulo)


def abrir_dialogo(usuario, chave_modulo):
    """Abre o diálogo de backup do módulo informado."""
    if chave_modulo not in MAPA_BACKUPS:
        return
    if not pode_gerenciar(usuario, chave_modulo):
        ui.notify("Sem permissão para gerir backups deste módulo", type="negative")
        return
    _arquivo, nome_amigavel = MAPA_BACKUPS[chave_modulo]

    with ui.dialog() as dlg, ui.card().classes("w-[560px]"):
        ui.label(f"Backup » {nome_amigavel}").classes("text-h6")
        ui.label(f"Banco gerenciado: {_arquivo}").classes("text-caption text-grey-7")
        with ui.row().classes("w-full items-end gap-2 flex-wrap"):
            horas = ui.number(
                "Intervalo automático (horas)",
                value=intervalo_backup(chave_modulo), min=1, max=720, precision=0,
            ).props("outlined dense").classes("w-52")
            ultima = listar_backups(chave_modulo)[None:1]
            if ultima:
                _, quando = ultima[0]
                ui.badge(f"Última cópia: {quando}",
                         color="blue-2").props("outline dense text-color=blue-9")

            def salvar_intervalo():
                set_config(f"backup_horas:{chave_modulo}",
                           int(horas.value) or 12)
                reagendar_backup(chave_modulo, int(horas.value) or 12)
                audit_log(usuario, "intranet", "config_alterada",
                          f"backup_horas:{chave_modulo}={int(horas.value) or 12}h")
                ui.notify(f"Intervalo salvo: {int(horas.value) or 12}h (aplicado sem reiniciar)",
                          type="positive")

            ui.button("Salvar intervalo", on_click=salvar_intervalo) \
                .props("unelevated no-caps dense icon=schedule")

            def rodar_agora():
                gerado = backup_modulo(chave_modulo)
                if gerado:
                    audit_log(usuario, "intranet", "backup_manual",
                              f"módulo={chave_modulo} arquivo={gerado}")
                    ui.notify(f"Cópia gerada: {gerado}", type="positive")
                    grade.refresh()
                else:
                    ui.notify("Falha ao gerar a cópia", type="negative")

            ui.button("Fazer backup agora", on_click=rodar_agora) \
                .props("unelevated no-caps dense color=primary icon=backup")

        ui.separator()
        ui.label("Cópias retidas (retenção: 10 por banco)") \
            .classes("text-subtitle2 font-bold text-grey-8")

        @ui.refreshable
        def grade():
            linhas = listar_backups(chave_modulo)
            if not linhas:
                ui.label("Nenhuma cópia retida até o momento.") \
                    .classes("text-caption text-grey-6")
                return
            with ui.grid(columns="1fr auto auto").classes(
                    "w-full bg-grey-1 rounded px-3 py-1.5 text-caption font-bold text-grey-8"):
                for c in ("Arquivo", "Tamanho", "Data/hora"):
                    ui.label(c)
            for arq, kb, quando in linhas:
                with ui.grid(columns="1fr auto auto").classes("w-full text-caption"):
                    ui.label(arq)
                    ui.label(f"{kb} KB")
                    ui.label(quando)

        grade()
        with ui.row().classes("w-full justify-end mt-2"):
            ui.button("Fechar", on_click=dlg.close).props("flat no-caps")

    dlg.open()
