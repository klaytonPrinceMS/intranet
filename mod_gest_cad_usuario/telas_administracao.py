"""User management — administration tab (admin geral only).

Aba Administração do módulo `gest_cad_usuario`: card padrão
"Configurações de cores" (via `bloco_aparencia` — prévia ao vivo e campos
de cores no padrão do intranet; "Restaurar padrão" usa `tema["_defaults"]`
e grava "" nos campos de botão = usar o padrão do próprio módulo em
`PADROES_TEMA`) e card de configurações específicas (tamanho mínimo da
senha). A edição de nome/ícone/ativo do módulo NÃO existe aqui — é
exclusiva do painel central /configuracoes (aba Módulo).

EN: Administration tab for `gest_cad_usuario`. Exposes the standard
"Configurações de cores" cupê (theme overrides saved under the `usuarios`
module key) and module-specific knobs such as the minimum password length.
Reserved for the global admin — module-level admins don't see this tab.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from nicegui import ui

from mod_intranet import observabilidade
from mod_intranet.bd_manipulador import audit_log
from mod_intranet.tema_modulo import bloco_aparencia, ler_tema, notificar
from mod_intranet.ui_comum import card_admin, rodape_salvar_restaurar
from mod_gest_cad_usuario import bd_manipulador as gest

log = observabilidade.get_logger("gest_cad_usuario")


def mostrar_administracao(ator: str):
    """Render the administration tab content for the global admin.

    Renders the full administration panel: card with the standard
    appearance cupê (`bloco_aparencia`) + a module-specific card with the
    minimum password length. Relies on `ler_tema("usuarios", ...)` and
    `gest.senha_minima()` — no external state needed (the parent `mostrar_tela`
    simply calls this when the global admin selects the Administração tab).

    PT-BR: Renderiza todo o conteúdo do painel "Administração" (exclusivo do
    admin geral): card de aparência (6 campos de tema) + card de
    configurações específicas (tamanho mínimo da senha). Botões vazios
    herdam o tema do sistema (`intranet_*`). Use `ui.navigate.reload()` nos
    callbacks de salvar/restaurar para que o novo tema entre em vigor sem
    reiniciar o servidor — todo o ajuste é live.
    """
    from mod_intranet.bd_conexao import set_config

    tema = ler_tema("usuarios", cor_botao="#000000", cor_texto_botao="#FFFFFF",
                    texto_header="Cadastro de usuários, papéis e acessos por módulo (soft CRUD · LGPD).")
    tema["_defaults"] = {
        "cor_botao": "",
        "cor_texto_botao": "",
        "cor_fundo": "",
        "cor_titulo": "#212121",
        "btn_tamanho": "",
        "texto_header": "Cadastro de usuários, papéis e acessos por módulo (soft CRUD · LGPD).",
    }

    ui.colors(primary=tema["cor_botao"], accent=tema["cor_botao"])

    bloco_aparencia(ator, "usuarios", tema,
                    ao_salvar_descricao="configurações de cores salvas",
                    prefixo_auditoria="gest_cad_usuario")

    with card_admin("Configurações específicas", icone="tune",
                    chave_modulo="usuarios", grade=False, aberto=False):
        ui.label("Aplicado ao criar, duplicar e redefinir senha de usuário. "
                 "Valem sem restart.").classes("text-caption text-grey-6")
        inp_senha = ui.number(
            "Tamanho mínimo da senha (caracteres)",
            value=gest.senha_minima(), min=4, max=32, precision=0,
        ).props("outlined dense").classes("w-64") \
            .tooltip("Aplicado ao criar usuário e redefinir senha.")

        def salvar():
            """Applies the minimum-password-length setting and reloads.

            Grava `usuarios_senha_min` (clamp 4–32), audita, notifica e
            recarrega após 1 segundo — aplicação sem restart."""
            set_config("usuarios_senha_min",
                       max(4, int(inp_senha.value or gest.senha_minima())))
            try:
                audit_log(ator, "gest_cad_usuario", "configuracao",
                          "tamanho mínimo de senha alterado")
            except Exception as e:
                log.warning(f"audit_log falhou em gest_cad_usuario config: {e}")
            notificar("Configuração aplicada (vale sem reiniciar)",
                      type="positive")
            ui.timer(1.0, lambda: ui.navigate.reload(), once=True)

        def resetar():
            """Restores the default minimum password length (6) and reloads.

            Restaura `usuarios_senha_min` para 6, audita, notifica e
            recarrega após 1 segundo."""
            set_config("usuarios_senha_min", 6)
            try:
                audit_log(ator, "gest_cad_usuario", "configuracao",
                          "tamanho mínimo de senha restaurado ao padrão")
            except Exception as e:
                log.warning(f"audit_log falhou em gest_cad_usuario reset: {e}")
            notificar("Padrões restaurados", type="positive")
            ui.timer(1.0, lambda: ui.navigate.reload(), once=True)

        rodape_salvar_restaurar(salvar, restaurar=resetar, chave_modulo="usuarios")

    from mod_intranet.rotinas import painel_backup
    painel_backup(ator, "usuarios")