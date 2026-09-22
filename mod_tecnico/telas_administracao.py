"""Painel de administração do módulo Técnico (rota /admin/tecnico)."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from nicegui import ui
from mod_intranet.ui_comum import card_admin, rodape_salvar_restaurar
from mod_intranet.tema_modulo import ler_tema, notificar, bloco_aparencia
from mod_intranet import observabilidade

log = observabilidade.get_logger("tecnico")


def mostrar_administracao(usuario_logado: str = ""):
    try:
        tema = ler_tema("tecnico", cor_botao="#000000", cor_texto_botao="#FFFFFF",
                        texto_header="Ferramentas e backup (admin).")
        tema["_defaults"] = {
            "cor_botao": "",
            "cor_texto_botao": "",
            "cor_fundo": "",
            "cor_titulo": "#212121",
            "btn_tamanho": "medium",
            "texto_header": "Ferramentas e backup (admin).",
            "cor_fundo_card": "#FFFFFF",
            "cor_texto_card": "",
        }
        ui.colors(primary=tema["cor_botao"])
        bloco_aparencia(usuario_logado, "tecnico", tema, prefixo_auditoria="tecnico", com_texto_header=True)

        from mod_tecnico import bd_manipulador as tec
        from mod_intranet.bd_conexao import get_config, set_config

        with card_admin("Configurações do Técnico", icone="build", chave_modulo="tecnico", grade=False):
            ui.label("Pastas físicas dentro do módulo (não use caminho fora de mod_tecnico/).").classes("text-caption text-grey-6")
            inp_soft = ui.input("Pasta software", value=tec.PASTA_SOFTWARE).props("outlined dense").classes("w-full")
            inp_soft.disable()
            inp_soft.tooltip("Fixo: mod_tecnico/software (versionável, .gitkeep)")

            inp_back = ui.input("Pasta backup", value=tec.PASTA_BACKUP).props("outlined dense").classes("w-full")
            inp_back.disable()
            inp_back.tooltip("Fixo: mod_tecnico/backup (padrão YYYYMMDD_HHMM_nomePc_ip)")

            max_zip = ui.number("Limite zip software (MB)", value=int((get_config("tecnico_max_zip_mb", "1024") or "1024")), min=10, max=10000).props("outlined dense").classes("w-full")

            def salvar():
                try:
                    set_config("tecnico_max_zip_mb", str(int(max_zip.value or 1024)))
                    notificar("Configurações do Técnico salvas", type="positive")
                    ui.timer(1.0, lambda: ui.navigate.reload(), once=True)
                except Exception:
                    log.exception("salvar config técnico falhou")
                    notificar("Erro ao salvar configurações", type="negative")

            def restaurar():
                try:
                    set_config("tecnico_max_zip_mb", "1024")
                    ui.timer(1.0, lambda: ui.navigate.reload(), once=True)
                except Exception:
                    log.exception("restaurar config técnico falhou")
                    notificar("Erro ao restaurar configurações", type="negative")

            rodape_salvar_restaurar(salvar, restaurar, chave_modulo="tecnico")

        with card_admin("Backups recentes (todos os usuários)", icone="storage", chave_modulo="tecnico", grade=False):
            box = ui.column().classes("w-full gap-2")

            def render():
                try:
                    box.clear()
                    with box:
                        rows = tec.listar_backups(owner=None, apenas_owner=False)
                        if not rows:
                            ui.label("Nenhum backup ainda.").classes("text-grey-6 italic")
                            return
                        for bid, pasta, owner, ip, host, tam, status, data in rows[:30]:
                            with ui.row().classes("w-full items-center justify-between border-b py-1"):
                                ui.label(f"{pasta} — {owner} ({tam} bytes)").classes("text-caption")
                                ui.label(str(data)[:16] if data else "").classes("text-caption text-grey-5")
                except Exception:
                    log.exception("render backups admin técnico falhou")
                    notificar("Erro ao listar backups", type="negative")

            render()
            ui.button("Atualizar", on_click=render).props("flat").classes("mt-2")

        from mod_intranet.rotinas import painel_backup
        painel_backup(usuario_logado, "tecnico")
    except Exception:
        log.exception("mostrar_administracao falhou")
        notificar("Erro ao exibir administração do Técnico", type="negative")
