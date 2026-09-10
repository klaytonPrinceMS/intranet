"""Audit module administration panel.

Painel de administração do módulo Auditoria — configurações de retenção,
aparência (cores, tamanho de botões). Acesso restrito a `administrador_geral`.
A edição de nome/ícone/ativo do módulo NÃO existe aqui — é exclusiva do
painel central /configuracoes (aba Módulo).
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from nicegui import ui
from mod_intranet.bd_conexao import get_config, set_config
from mod_intranet.bd_manipulador import audit_log
from mod_intranet.ui_comum import card_admin, botao, campo_cor, campo_selecao
from mod_intranet import observabilidade

log = observabilidade.get_logger("auditoria")


def _cfg(chave, default):
    """Fetch an auditoria config value, returning default on failure."""
    try:
        return get_config(f"auditoria_{chave}", str(default))
    except Exception:
        log.error(f"falha ao ler config auditoria_{chave}")
        return str(default)


def _tema(chave, default):
    """Fetch a theme config value, returning default on failure."""
    try:
        return (get_config(f"auditoria_{chave}", default) or "").strip() or default
    except Exception:
        return default


def _btn_cls(tamanho):
    """Return CSS classes for button size."""
    if tamanho == "small":
        return "min-w-[140px] text-sm"
    if tamanho == "large":
        return "min-w-[220px] text-lg"
    return "min-w-[180px]"


def _btn_style(cor_botao, cor_txt_botao):
    """Build inline style dict for button colour."""
    st = ""
    if cor_botao:
        st += f"background-color:{cor_botao};"
    if cor_txt_botao:
        st += f"color:{cor_txt_botao};"
    return st


def mostrar_administracao(
    usuario_logado: str,
    eh_admin_geral: bool = True,
    on_save_callback=None,
) -> None:
    """Render the audit administration panel (colors + specific settings).

    Monta o painel "Administração" do módulo de Auditoria seguindo o padrão
    de exibição dos demais módulos: card PADRÃO "Configurações de cores"
    (prévia ao vivo, exemplo do Intranet) via `bloco_aparencia` + card
    "Configurações específicas" (limite de linhas, retenção LGPD e texto do
    cabeçalho) + card padrão de backup (`painel_backup`). Renderizado
    SOMENTE quando `eh_admin_geral` é verdadeiro. Recebe `on_save_callback`
    opcional — função sem argumentos chamada após salvar com sucesso.

    Cada card é recolhível (`card_admin`) com o rodapé padrão de 2 botões
    ("Restaurar padrão" + "Aplicar") exclusivos do card.

    Args:
        usuario_logado: Nome do usuário administrador.
        eh_admin_geral: Se falso, o painel não é renderizado.
        on_save_callback: Função opcional chamada após salvar com sucesso.
    """
    if not eh_admin_geral:
        return

    try:
        limite_sql = max(10, int(_cfg("limite", "1000")))
    except (TypeError, ValueError):
        limite_sql = 1000
    retencao_dias = _cfg("retencao_dias", "90")
    texto_header = _cfg("texto_header", "Rastreamento de ações no sistema (LGPD).")

    from mod_intranet.tema_modulo import ler_tema, bloco_aparencia
    from mod_intranet.ui_comum import card_admin, rodape_salvar_restaurar
    from mod_intranet.tema_modulo import notificar

    tema = ler_tema("auditoria", cor_botao="#000000", cor_texto_botao="#FFFFFF",
                    cor_titulo="#212121", btn_tamanho="medium")
    tema["_defaults"] = {
        "cor_botao": "",
        "cor_texto_botao": "",
        "cor_fundo": "",
        "cor_titulo": "#212121",
        "btn_tamanho": "medium",
        "cor_fundo_card": "#FFFFFF",
        "cor_texto_card": "",
    }

    # ---- Card padrão "Configurações de cores" (prévia ao vivo) ----
    bloco_aparencia(usuario_logado, "auditoria", tema,
                    prefixo_auditoria="auditoria", com_texto_header=False)

    # ---- Configurações específicas (LGPD) ----
    with card_admin("Configurações específicas", icone="tune",
                    chave_modulo="auditoria", grade=False, aberto=False):
        ui.label("Retenção LGPD (limite de linhas por página e dias) e texto "
                 "do cabeçalho. Valem sem restart.").classes(
            "text-caption text-grey-6")
        inp_limite = ui.number(
            "Limite de linhas por página (LIMIT SQL)",
            value=int(limite_sql), min=10, max=10000,
        ).props("outlined dense")
        inp_retencao = ui.number(
            "Retenção (dias)", value=int(retencao_dias),
            min=1, max=3650,
        ).props("outlined dense")
        inp_header = ui.input(
            "Texto do cabeçalho", value=texto_header,
        ).props("outlined dense").classes("w-full")

        def _salvar():
            """Applies the audit-specific settings and reloads after 1s.

            Grava limite de linhas, retenção (dias) e texto do cabeçalho;
            audita, notifica e recarrega após 1 segundo. Falha registra
            loguru e notifica negativo (fail-soft)."""
            try:
                set_config("auditoria_limite", inp_limite.value)
                set_config("auditoria_retencao_dias", inp_retencao.value)
                set_config("auditoria_texto_header", inp_header.value)
                audit_log(
                    usuario_logado, "auditoria", "configuracao",
                    "configurações específicas da auditoria alteradas: "
                    "limite, retenção e cabeçalho",
                )
                notificar("Configurações específicas aplicadas — recarregando…",
                          type="positive")
                log.info("configurações específicas da auditoria salvas")
                if on_save_callback is not None:
                    try:
                        on_save_callback()
                    except Exception:
                        log.exception("erro no callback de salvamento da auditoria")
                ui.timer(1.0, lambda: ui.navigate.reload(), once=True)
            except Exception:
                log.exception("falha ao salvar configurações da auditoria")
                notificar("Erro ao salvar configurações", type="negative")

        def _resetar():
            """Restores the audit defaults (1000 lines / 90 days) and reloads.

            Restaura limite=1000, retenção=90 dias e o texto padrão do
            cabeçalho; audita, notifica e recarrega após 1 segundo. Falha
            registra loguru e notifica negativo (fail-soft)."""
            try:
                set_config("auditoria_limite", 1000)
                set_config("auditoria_retencao_dias", 90)
                set_config("auditoria_texto_header",
                           "Rastreamento de ações no sistema (LGPD).")
                audit_log(
                    usuario_logado, "auditoria", "configuracao",
                    "configurações específicas da auditoria restauradas ao padrão",
                )
                notificar("Padrões restaurados — recarregando…", type="positive")
                ui.timer(1.0, lambda: ui.navigate.reload(), once=True)
            except Exception:
                log.exception("erro ao restaurar padrões da auditoria")
                notificar("Erro ao restaurar padrões", type="negative")

        rodape_salvar_restaurar(_salvar, restaurar=_resetar,
                                chave_modulo="auditoria")

    from mod_intranet.rotinas import painel_backup
    painel_backup(usuario_logado, "auditoria")
