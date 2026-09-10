"""Automatic system routines: database backups and editorPDF cleanup.

Rotinas automáticas do sistema: backup de bancos e limpeza do editorPDF."""
import os
import shutil
import sqlite3
import time
from datetime import datetime

import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # raiz do projeto
PASTA_BACKUP = os.path.join(BASE_DIR, "backup")
PASTA_EDITOR_PDF = os.path.join(BASE_DIR, "mod_edit_pdf", "editorPDF")

# Mapeamento chave do módulo -> arquivo de banco gerenciado por ele
MAPA_BACKUPS = {
    "intranet": ("db_mod_intranet.db", "Intranet (central)"),
    "usuarios": ("db_mod_gest_cad_usuario.db", "Usuários"),
    "blog": ("db_mod_blog.db", "Blog"),
    "auditoria": ("db_mod_auditoria.db", "Auditoria"),
    "editar_pdf": ("db_mod_edit_pdf.db", "Editor PDF"),
    "empenhos": ("db_mod_renomear_empenho.db", "Empenhos"),
    "solicita_impressao": ("db_mod_solicita_impressao.db", "Solicitacao de Impressao"),
}

_agendador = None  # referência global para reagendamento em tempo de execução


def painel_backup(usuario: str, chave_modulo: str):
    """Renders the backup management panel for a module inside its administration page.

    Shows: current interval, last backup time, save interval button, run backup now
    button, and the list of retained backups. Used by all module telas_administracao.py
    files to expose backup configuration to the module admin.

    Args:
        usuario: Nome do usuário que está gerenciando (para auditoria).
        chave_modulo: Chave do módulo (ex: "blog", "auditoria", "editar_pdf").
    """
    from nicegui import ui
    from mod_intranet.bd_conexao import get_config, set_config
    from mod_intranet.tema_modulo import botao as _botao_tema, ler_tema as _ler_tema
    from mod_intranet.bd_manipulador import audit_log

    if chave_modulo not in MAPA_BACKUPS:
        return
    _arquivo, nome_amigavel = MAPA_BACKUPS[chave_modulo]

    # O "detalhe de cor" (borda lateral esquerda) acompanha a cor geral do
    # módulo (<prefixo>_cor_botao); sem tema lido, cai no cinza padrão.
    try:
        cor_borda = _ler_tema(chave_modulo).get("cor_botao", "") or ""
    except Exception:
        cor_borda = ""
    cor_borda = cor_borda or "#607D8B"

    with ui.card().classes("w-full border-l-4").style(
            f"border-left-color:{cor_borda}"):
        with ui.card_section().classes("gap-3 w-full"):
            ui.label("Backup do banco de dados").classes("text-h6 font-bold")
            with ui.row().classes("w-full items-center flex-wrap").style(
                    "gap: 0.5rem"):
                ui.label(f"Banco: {_arquivo}").classes("text-caption text-grey-7")
                ultima = listar_backups(chave_modulo)[:1]
                if ultima:
                    quando = ultima[0][2]
                    ui.badge(f"Última cópia: {quando}",
                             color="blue-2").props("outline dense text-color=blue-9")

            with ui.row().classes("w-full items-end flex-wrap").style("gap: 0.5rem"):
                inp_horas = ui.number(
                    "Intervalo automático (horas)",
                    value=intervalo_backup(chave_modulo), min=1, max=720,
                    precision=0,
                ).props("outlined dense").classes("w-40")

                def salvar_intervalo():
                    h = max(1, int(inp_horas.value or 12))
                    set_config(f"backup_horas:{chave_modulo}", h)
                    reagendar_backup(chave_modulo, h)
                    audit_log(usuario, "intranet", "config_alterada",
                              f"backup_horas:{chave_modulo}={h}h")
                    ui.notify(f"Intervalo salvo: {h}h (aplicado sem reiniciar)",
                              type="positive")

                _botao_tema("Salvar intervalo", on_click=salvar_intervalo)

                def rodar_agora():
                    gerado = backup_modulo(chave_modulo)
                    if gerado:
                        audit_log(usuario, "intranet", "backup_manual",
                                  f"módulo={chave_modulo} arquivo={gerado}")
                        ui.notify(f"Cópia gerada: {gerado}", type="positive")
                        grade.refresh()
                    else:
                        ui.notify("Falha ao gerar a cópia", type="negative")

                _botao_tema("Fazer backup agora", icone="backup",
                           on_click=rodar_agora)

            ui.separator()
            ui.label("Cópias retidas (máximo 10)").classes(
                "text-subtitle2 font-bold text-grey-8")

            @ui.refreshable
            def grade():
                linhas = listar_backups(chave_modulo)
                if not linhas:
                    ui.label("Nenhuma cópia retida até o momento.") \
                        .classes("text-caption text-grey-6")
                    return
                with ui.grid(columns="1fr auto auto").classes(
                        "w-full bg-grey-1 rounded px-3 py-1.5 "
                        "text-caption font-bold text-grey-8"):
                    for c in ("Arquivo", "Tamanho", "Data/hora"):
                        ui.label(c)
                for arq, kb, quando in linhas:
                    with ui.grid(columns="1fr auto auto") \
                            .classes("w-full text-caption"):
                        ui.label(arq)
                        ui.label(f"{kb} KB")
                        ui.label(quando)

            grade()


def intervalo_backup(chave, default="12"):
    """Intervalo em horas configurado para o módulo (tb_config)."""
    from mod_intranet.bd_conexao import get_config
    try:
        return max(1, int(get_config(f"backup_horas:{chave}", default)))
    except (TypeError, ValueError):
        return int(default)


def intervalo_monitor_empenho(default=60):
    """Intervalo (segundos) do monitor automático de empenhos (RF-40).

    Recomendado 60 s (avaliando o padrão do sistema que está sendo copiado).
    Configurável via tb_config 'empenhos_monitor_intervalo_seg' sem restart.
    """
    from mod_intranet.bd_conexao import get_config
    try:
        return max(1, int(get_config("empenhos_monitor_intervalo_seg", default)))
    except (TypeError, ValueError):
        return int(default)


def reagendar_monitor_empenho(segundos):
    """Aplica novo intervalo ao job de monitor de empenhos (sem restart)."""
    segundos = max(1, int(segundos))
    if _agendador is None:
        return False
    try:
        _agendador.reschedule_job("monitor_empenho", trigger="interval", seconds=segundos)
        return True
    except Exception:
        return False


def _job_monitor_empenho():
    """Varredura automática da pasta monitorada de empenhos (RF-40)."""
    try:
        from mod_renomear_empenho.bd_manipulador import rodar_monitor
        rodar_monitor("sistema")
    except Exception as ex:
        try:
            from mod_intranet import observabilidade
            observabilidade.get_logger("renomear_empenho").error(f"monitor_empenho falhou: {ex}")
        except Exception:
            pass


def _job_poda_auditoria():
    """Poda diária do banco exclusivo de auditoria (db_mod_auditoria.db).

    Remove das tabelas por módulo os registros mais antigos que o prazo de
    retenção configurado (auditoria_retencao_dias, default 90), para
    conformidade LGPD sem acúmulo indefinido.
    """
    removidos = 0
    try:
        from mod_intranet.bd_conexao import get_config
        from mod_auditoria.db_manipulador import podar_registros
        try:
            dias = max(1, int(get_config("auditoria_retencao_dias", "90")))
        except (TypeError, ValueError):
            dias = 90
        try:
            removidos = podar_registros(dias)
        except Exception:
            removidos = 0
        if removidos:
            from mod_intranet import observabilidade
            observabilidade.get_logger("intranet").info(
                f"poda auditoria: {removidos} registro(s) removidos | retenção {dias} dias")
    except Exception as ex:
        try:
            from mod_intranet import observabilidade
            observabilidade.get_logger().error(f"poda_auditoria falhou: {ex}")
        except Exception:
            pass
    return removidos


def backup_bancos():
    """Copia TODOS os db_*.db para /backup com timestamp."""
    os.makedirs(PASTA_BACKUP, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    copiados = []
    for f in os.listdir(BASE_DIR):
        if f.startswith("db_") and f.endswith(".db"):
            origem = os.path.join(BASE_DIR, f)
            destino = os.path.join(PASTA_BACKUP, f"{stamp}_{f}")
            try:
                shutil.copy2(origem, destino)
                copiados.append(f)
            except Exception:
                pass
    _podar_backups()
    return copiados


def backup_modulo(chave):
    """Backup SOMENTE do banco do módulo. Retorna o nome do arquivo gerado ou None."""
    info = MAPA_BACKUPS.get(chave)
    if not info:
        return None
    arquivo = info[0]
    origem = os.path.join(BASE_DIR, arquivo)
    if not os.path.exists(origem):
        return None
    os.makedirs(PASTA_BACKUP, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    destino = os.path.join(PASTA_BACKUP, f"{stamp}_{arquivo}")
    shutil.copy2(origem, destino)
    _podar_backups()
    return os.path.basename(destino)


def _podar_backups(manter=10):
    """Retém apenas os N backups mais recentes por banco de dados."""
    try:
        por_base = {}
        for f in sorted(os.listdir(PASTA_BACKUP)):
            nome_base = "_".join(f.split("_")[2:])
            por_base.setdefault(nome_base, []).append(f)
        for base, arquivos in por_base.items():
            for antigo in arquivos[:-manter]:
                os.remove(os.path.join(PASTA_BACKUP, antigo))
    except Exception:
        pass


def listar_backups(chave=None):
    """[(arquivo, tamanho_kb, data_hora)] do mais recente ao mais antigo;
    com chave, filtra pelo banco daquele módulo."""
    if not os.path.isdir(PASTA_BACKUP):
        return []
    sufixo = MAPA_BACKUPS[chave][0] if chave in MAPA_BACKUPS else None
    saida = []
    for f in sorted(os.listdir(PASTA_BACKUP), reverse=True):
        if sufixo and not f.endswith(sufixo):
            continue
        caminho = os.path.join(PASTA_BACKUP, f)
        try:
            kb = max(1, round(os.path.getsize(caminho) / 1024))
            quando = datetime.fromtimestamp(os.path.getmtime(caminho)).strftime("%d/%m %H:%M")
            saida.append((f, kb, quando))
        except OSError:
            continue
    return saida


# ================== AGENDADOR DINÂMICO ==================

def iniciar_agendador():
    """Um job de backup POR módulo (intervalo individual) + limpeza do editorPDF."""
    global _agendador
    if _agendador is not None:
        return _agendador
    from apscheduler.schedulers.background import BackgroundScheduler

    sched = BackgroundScheduler(daemon=True)

    def _job_backup(chave):
        backup_modulo(chave)

    def _job_todos():
        for chave in MAPA_BACKUPS:
            backup_modulo(chave)

    def _job_cleanup_pdfs():
        """Expiração do editorPDF a cada 1 min (sem depender de login).
        Usa a rotina do módulo dono (remove disco + inativa BD + devolve cota)
        com o tempo configurável via `editar_pdf_expiracao_min`; em caso de falha de
        import, cai no fallback que só limpa o disco."""
        try:
            from mod_edit_pdf.bd_manipulador import expirar_antigos, cfg_expiracao_min
            expirar_antigos(minutos=cfg_expiracao_min())
        except Exception as ex:
            try:
                from mod_intranet import observabilidade
                observabilidade.get_logger().error(f"cleanup_pdf falhou: {ex}")
            except Exception:
                pass
            limpar_editor_pdf(minutos=10)

    def _job_cleanup_solicita():
        """Solicitação de Impressão: a cada 1 min remove rascunhos não confirmados
        (prazo tempo_expira_rascunho_min) e arquivos de solicitações impressas já
        vencidos (prazo tempo_exclui_impresso_min)."""
        try:
            from mod_solicita_impressao.bd_manipulador import expirar_rascunhos_e_impressos
            expirar_rascunhos_e_impressos()
        except Exception as ex:
            try:
                from mod_intranet import observabilidade
                observabilidade.get_logger().error(f"cleanup_solicita falhou: {ex}")
            except Exception:
                pass

    for chave in MAPA_BACKUPS:
        sched.add_job(_job_backup, "interval", args=[chave],
                      hours=intervalo_backup(chave), id=f"backup:{chave}")
    sched.add_job(_job_cleanup_pdfs, "interval", minutes=1, id="cleanup_pdf")
    sched.add_job(_job_cleanup_solicita, "interval", minutes=1, id="cleanup_solicita")
    sched.add_job(_job_poda_auditoria, "interval", hours=24, id="poda_auditoria")
    sched.add_job(_job_monitor_empenho, "interval", seconds=intervalo_monitor_empenho(),
                  id="monitor_empenho")
    sched.start()
    _agendador = sched
    return sched


def reagendar_backup(chave, horas):
    """Aplica novo intervalo ao job vivo do módulo (sem restart)."""
    horas = max(1, int(horas))
    if _agendador is None:
        return False
    try:
        _agendador.reschedule_job(f"backup:{chave}", trigger="interval", hours=horas)
        return True
    except Exception:
        return False


def limpar_editor_pdf(minutos=10):
    """Remove arquivos do editorPDF mais antigos que N minutos."""
    removidos = 0
    agora = time.time()
    limite = minutos * 60
    if not os.path.isdir(PASTA_EDITOR_PDF):
        return 0
    for root, _dirs, files in os.walk(PASTA_EDITOR_PDF):
        for f in files:
            caminho = os.path.join(root, f)
            try:
                if agora - os.path.getmtime(caminho) > limite:
                    os.remove(caminho)
                    removidos += 1
            except Exception:
                pass
    return removidos
