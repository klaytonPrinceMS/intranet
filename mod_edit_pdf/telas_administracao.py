"""PDF Editor administration tab — extracted from `telas.py`.

Aba de Administração do Editor de PDF — extraída de `telas.py`.
Segue o padrão de exibição dos demais módulos: card PADRÃO
"Configurações de cores" (prévia ao vivo, exemplo do Intranet) via
`tema_modulo.bloco_aparencia`, card "Configurações específicas" (cotas,
limites de lote, expiração e textos da tela) e card de backup do banco
(`painel_backup`). Cada card é recolhível (`card_admin`) com o rodapé
padrão de 2 botões — "Restaurar padrão" + "Aplicar" — exclusivos do card.
Cada alteração é registrada na auditoria central (`audit_log`).

This module exposes `mostrar_administracao(usuario_logado, eh_admin)`,
which renders the admin panel as a self-contained block that recomputes
the configuration values it needs via the `cfg_*` helpers in
`mod_edit_pdf.manipulador_bd`.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from nicegui import ui

from mod_intranet.bd_conexao import get_config, set_config
from mod_intranet.bd_manipulador import audit_log
from mod_intranet.tema_modulo import bloco_aparencia, ler_tema, notificar
from mod_intranet.ui_comum import card_admin, rodape_salvar_restaurar, botao
from mod_intranet import observabilidade

from mod_edit_pdf.bd_manipulador import (
    cfg_lote_arquivos, cfg_lote_mb, cfg_usuario_gb, cfg_expiracao_min,
    uso_global_bytes, expirar_antigos,
)

log = observabilidade.get_logger("edit_pdf.administracao")

CHAVE_MODULO = "editar_pdf"
PREFIXO_AUDITORIA = "edit-pdf"


def _fmt_bytes(n):
    """Formats a byte count as KB/MB/GB for display."""
    if n >= 1024**3:
        return f"{n/1024**3:.1f} GB"
    if n >= 1024**2:
        return f"{n/1024**2:.1f} MB"
    return f"{n/1024:.0f} KB"


def mostrar_administracao(usuario_logado: str, eh_admin: bool):
    """Renders the PDF Editor administration tab (standard card pattern).

    Renderiza a aba de Administração do Editor de PDF seguindo o padrão
    de exibição dos demais módulos:

    * "Configurações de cores": card PADRÃO (prévia ao vivo, exemplo do
      Intranet) via `tema_modulo.bloco_aparencia` — card recolhível
      `card_admin` com rodapé Restaurar padrão + Aplicar.
    * "Configurações específicas": cota global do servidor (GB), cota por
      usuário (GB), limites de lote (arquivos e MB), tempo de expiração
      dos PDFs e textos customizados da tela de upload/cabeçalho — card
      recolhível com o rodapé padrão de 2 botões.
    * "Manutenção": ação "Expirar agora".
    * "Backup do banco de dados": card padrão (`painel_backup`).

    Todas as configurações são aplicadas sem restart e cada salvamento
    gera um registro de auditoria (`edit-pdf` / `configuracao`).

    Parameters
    ----------
    usuario_logado : str
        Login do usuário que abriu a tela; usado apenas para registrar as
        alterações no log de auditoria.
    eh_admin : bool
        Deve ser ``True`` para que o painel seja renderizado. Caso
        contrário, nada é exibido (defesa em profundidade — a aba já é
        oculta no `tabs_el` quando o usuário não é admin geral).

    Returns
    -------
    None
        O conteúdo é renderizado diretamente na árvore de elementos
        corrente do NiceGUI.
    """
    if not eh_admin:
        log.debug("mostrar_administracao chamado sem privilégios de admin")
        return

    try:
        tema = ler_tema(CHAVE_MODULO)
    except Exception as ex:
        log.debug("falha ao ler tema do módulo: %s", ex)
        tema = None

    # ---- Card padrão "Configurações de cores" (prévia ao vivo) ----
    bloco_aparencia(usuario_logado, CHAVE_MODULO, tema,
                    prefixo_auditoria=PREFIXO_AUDITORIA)

    # ---- Configurações específicas (cotas, limites, textos) ----
    with card_admin("Configurações específicas", icone="tune",
                    chave_modulo=CHAVE_MODULO, grade=False, aberto=False):
        ui.label("Valem para todos os usuários imediatamente, sem restart. "
                 "Cada alteração é registrada na auditoria.").classes(
            "text-caption text-grey-6")
        with ui.grid().classes(
                "w-full grid-cols-1 sm:grid-cols-2 md:grid-cols-4") \
                .style("gap: 1.25rem"):
            inp_cota_global = ui.number(
                "Cota global do servidor (GB)",
                value=int(get_config("cotadisco_global_gb", "10") or 10),
                min=1, max=1024, precision=0).props("outlined dense")
            inp_lote_arq = ui.number(
                "Máx. arquivos por lote",
                value=cfg_lote_arquivos(), min=1, max=100,
                precision=0).props("outlined dense")
            inp_lote_mb = ui.number(
                "Máx. MB por lote",
                value=cfg_lote_mb(), min=1, max=10240,
                precision=0).props("outlined dense")
            inp_usuario_gb = ui.number(
                "Cota por usuário (GB)",
                value=cfg_usuario_gb(), min=1, max=100,
                precision=0).props("outlined dense")
            inp_expira_min = ui.number(
                "Minutos até expiração dos arquivos",
                value=cfg_expiracao_min(), min=1, max=1440,
                precision=0).props("outlined dense")

        ui.separator().classes("my-2")
        ui.label("Textos da tela").classes("font-bold")
        ui.label("Personalize as frases exibidas aos usuários. "
                 "Deixe vazio para usar o padrão.").classes(
            "text-caption text-grey-6")
        with ui.grid().classes(
                "w-full grid-cols-1 sm:grid-cols-2").style("gap: 1.25rem"):
            inp_txt_header = ui.input(
                "Subtítulo do cabeçalho (abaixo de 'Editor de PDF')",
                value=get_config(
                    "editar_pdf_texto_header_sub",
                    "Reduza, junte, corte, divida e verifique seus documentos."),
            ).props("outlined dense").classes("w-full")
            inp_txt_titulo = ui.input(
                "Título da seção de upload",
                value=get_config("editar_pdf_texto_upload_titulo",
                                 "Envie um ou mais PDFs"),
            ).props("outlined dense").classes("w-full")
            inp_txt_hint = ui.input(
                "Texto de ajuda abaixo do título (vazio = padrão dinâmico com limites)",
                value=get_config("editar_pdf_texto_upload_hint", ""),
            ).props("outlined dense").classes("w-full")
            inp_txt_label = ui.input(
                "Rótulo do botão de upload",
                value=get_config("editar_pdf_texto_upload_label",
                                 "Clique ou arraste PDFs aqui"),
            ).props("outlined dense").classes("w-full")

        rodape_salvar_restaurar(
            salvar=lambda: _salvar_configs(
                usuario_logado,
                inp_cota_global, inp_lote_arq, inp_lote_mb,
                inp_usuario_gb, inp_expira_min,
                inp_txt_header, inp_txt_titulo,
                inp_txt_hint, inp_txt_label,
            ),
            restaurar=lambda: _resetar_configs(
                usuario_logado,
                inp_cota_global, inp_lote_arq, inp_lote_mb,
                inp_usuario_gb, inp_expira_min,
                inp_txt_header, inp_txt_titulo,
                inp_txt_hint, inp_txt_label,
            ),
            chave_modulo=CHAVE_MODULO)

    # ---- Manutenção ----
    with card_admin("Manutenção", icone="cleaning_services",
                    chave_modulo=CHAVE_MODULO, grade=False, aberto=False):
        ui.label(f"Em disco agora: {_fmt_bytes(uso_global_bytes())}. "
                 "A expiração automática roda a cada 1 min usando os minutos "
                 "configurados acima.").classes("text-caption text-grey-6")
        botao("Expirar agora (força limpeza)",
              icone="cleaning_services", on_click=_expirar_agora,
              variante="primario", chave_modulo=CHAVE_MODULO)

    from mod_intranet.rotinas import painel_backup
    painel_backup(usuario_logado, "editar_pdf")


def _salvar_configs(usuario_logado,
                    inp_cota_global, inp_lote_arq, inp_lote_mb,
                    inp_usuario_gb, inp_expira_min,
                    inp_txt_header, inp_txt_titulo,
                    inp_txt_hint, inp_txt_label):
    """Persiste as alterações do card 'Configurações específicas' e recarrega.

    Grava cotas, limites de lote, expiração e textos; registra auditoria
    (`edit-pdf` / `configuracao`), notifica o RESULTADO e recarrega após
    1 segundo (padrão "Aplicar" de card). Falha notifica negativo."""
    try:
        gb_g = max(1, int(inp_cota_global.value or 10))
        lot_a = max(1, int(inp_lote_arq.value or 10))
        lot_mb = max(1, int(inp_lote_mb.value or 1024))
        usr_g = max(1, int(inp_usuario_gb.value or 1))
        exp_m = max(1, int(inp_expira_min.value or 10))
        set_config("cotadisco_global_gb", gb_g)
        set_config("editar_pdf_lote_arquivos", lot_a)
        set_config("editar_pdf_lote_mb", lot_mb)
        set_config("editar_pdf_usuario_gb", usr_g)
        set_config("editar_pdf_expiracao_min", exp_m)
        titulo = (inp_txt_titulo.value or "").strip() or "Envie um ou mais PDFs"
        hint = (inp_txt_hint.value or "").strip()
        label = (inp_txt_label.value or "").strip() or "Clique ou arraste PDFs aqui"
        header = (inp_txt_header.value or "").strip() \
            or "Reduza, junte, corte, divida e verifique seus documentos."
        set_config("editar_pdf_texto_upload_titulo", titulo)
        set_config("editar_pdf_texto_upload_hint", hint)
        set_config("editar_pdf_texto_upload_label", label)
        set_config("editar_pdf_texto_header_sub", header)
    except Exception as ex:
        log.exception("erro ao salvar configurações do editor PDF")
        notificar(f"Erro ao salvar configurações: {ex}", type="negative")
        return
    try:
        audit_log(usuario_logado, PREFIXO_AUDITORIA, "configuracao",
                  f"cota_global={gb_g}GB lote={lot_a}arq/{lot_mb}MB "
                  f"cota_usuario={usr_g}GB expiracao={exp_m}min")
    except Exception:
        log.debug("falha ao registrar auditoria de configuração")
    notificar("Configurações específicas aplicadas — recarregando…",
              type="positive")
    ui.timer(1.0, lambda: ui.navigate.reload(), once=True)


def _resetar_configs(usuario_logado,
                     inp_cota_global, inp_lote_arq, inp_lote_mb,
                     inp_usuario_gb, inp_expira_min,
                     inp_txt_header, inp_txt_titulo,
                     inp_txt_hint, inp_txt_label):
    """Restaura os valores padrão do card 'Configurações específicas'.

    Grava os padrões codificados (cotas/limites/expiração/textos), atualiza
    os campos em tela, registra auditoria e recarrega após 1 segundo. Falha
    notifica negativo."""
    try:
        set_config("cotadisco_global_gb", 10)
        set_config("editar_pdf_lote_arquivos", 10)
        set_config("editar_pdf_lote_mb", 1024)
        set_config("editar_pdf_usuario_gb", 1)
        set_config("editar_pdf_expiracao_min", 10)
        set_config("editar_pdf_texto_upload_titulo", "Envie um ou mais PDFs")
        set_config("editar_pdf_texto_upload_hint", "")
        set_config("editar_pdf_texto_upload_label", "Clique ou arraste PDFs aqui")
        set_config("editar_pdf_texto_header_sub",
                   "Reduza, junte, corte, divida e verifique seus documentos.")
        inp_cota_global.value = 10
        inp_lote_arq.value = 10
        inp_lote_mb.value = 1024
        inp_usuario_gb.value = 1
        inp_expira_min.value = 10
        inp_txt_titulo.value = "Envie um ou mais PDFs"
        inp_txt_hint.value = ""
        inp_txt_label.value = "Clique ou arraste PDFs aqui"
        inp_txt_header.value = ("Reduza, junte, corte, divida e verifique "
                                "seus documentos.")
        try:
            audit_log(usuario_logado, PREFIXO_AUDITORIA, "configuracao",
                      "configurações específicas restauradas ao padrão")
        except Exception:
            log.debug("falha ao registrar auditoria de restore")
        notificar("Padrões restaurados — recarregando…", type="positive")
        ui.timer(1.0, lambda: ui.navigate.reload(), once=True)
    except Exception as ex:
        log.exception("erro ao restaurar padrões do editor PDF")
        notificar(f"Erro ao restaurar padrões: {ex}", type="negative")


def _expirar_agora():
    """Força a limpeza imediata dos arquivos expirados."""
    try:
        n = expirar_antigos(minutos=cfg_expiracao_min())
        notificar(f"{n} arquivo(s) removido(s) pela expiração manual",
                  type="info")
    except Exception as ex:
        log.exception("erro ao expirar arquivos manualmente")
        notificar(f"Erro ao expirar arquivos: {ex}", type="negative")