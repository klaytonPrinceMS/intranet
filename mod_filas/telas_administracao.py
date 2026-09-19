"""Painel de administração do módulo Filas — esqueleto (rota /admin/filas)."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from nicegui import ui
from mod_intranet.ui_comum import card_admin, rodape_salvar_restaurar
from mod_intranet.tema_modulo import ler_tema, notificar, bloco_aparencia
from mod_intranet import observabilidade

log = observabilidade.get_logger("filas")

def mostrar_administracao(usuario_logado: str = ""):
    tema = ler_tema("filas", cor_botao="#000000", cor_texto_botao="#FFFFFF",
                    texto_header="Gestor de filas — esqueleto (TV).")
    tema["_defaults"] = {
        "cor_botao": "", "cor_texto_botao": "", "cor_fundo": "",
        "cor_titulo": "#212121", "btn_tamanho": "medium",
        "texto_header": "Gestor de filas — esqueleto (TV).",
        "cor_fundo_card": "#FFFFFF", "cor_texto_card": "",
    }
    ui.colors(primary=tema["cor_botao"])
    bloco_aparencia(usuario_logado, "filas", tema, prefixo_auditoria="filas", com_texto_header=True)

    with card_admin("Fila — Esqueleto", icone="queue", chave_modulo="filas", grade=False):
        ui.label("Esqueleto a título de conhecimento — será expandido para gestão completa de chamadas com TV na rede.").classes("text-caption text-grey-6")
        ui.label("Tabela tb_fila (Geral) já semeada; use a tela do módulo para chamar próxima senha.").classes("text-caption")

    from mod_intranet.rotinas import painel_backup
    painel_backup(usuario_logado, "filas")
