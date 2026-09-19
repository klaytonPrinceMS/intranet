"""Tela do módulo Técnico — software e backup (rota /tecnico).

EN: Technical screen — software download + PC backup (route /tecnico).
"""

import os
import sys
import re

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from nicegui import ui

from mod_intranet import autenticacao
from mod_intranet import observabilidade
from mod_intranet.aba_modulo import cabecalho
from mod_intranet.tema_modulo import ler_tema, notificar
from mod_intranet.ui_comum import botao, botao_icone
from mod_tecnico import bd_manipulador as tec

log = observabilidade.get_logger("tecnico")


def _pode_acessar(user_nome: str, perfil_global: str) -> bool:
    if perfil_global == "administrador_geral":
        return True
    try:
        return autenticacao.validar_acesso_modulo(user_nome, "tecnico")
    except Exception:
        return False


def mostrar_tela(user_nome: str, perfil_global: str = ""):
    """Renderiza a tela do Técnico (acesso por módulo).

    Monta: cabeçalho + abas Software | Backup + listagens.
    """
    if not _pode_acessar(user_nome, perfil_global):
        with ui.column().classes("w-full items-center p-12 gap-3"):
            ui.icon("block", size="64px").classes("text-red-8")
            ui.label("Acesso restrito").classes("text-h6")
            ui.label("Somente usuários com acesso ao módulo Técnico.").classes("text-body2 text-grey-7")
        return

    tema = ler_tema("tecnico", cor_botao="#000000", cor_texto_botao="#FFFFFF",
                    texto_header="Ferramentas padrão e backup para manutenção de PCs.")
    ui.colors(primary=tema["cor_botao"])
    t_cor_titulo = tema["cor_titulo"]
    t_cor_fundo = tema["cor_fundo"]
    t_texto_header = tema["texto_header"]

    with ui.column().classes("w-full p-6 gap-4"):
        cabecalho("Técnico", t_texto_header, chave_modulo="tecnico",
                  cor_titulo=t_cor_titulo, cor_fundo=t_cor_fundo)

        with ui.tabs().props("dense inline-label").classes("w-full") as tabs:
            tab_soft = ui.tab("Software", icon="apps")
            tab_backup = ui.tab("Backup", icon="backup")

        with ui.tab_panels(tabs, value=tab_soft).classes("w-full bg-transparent"):
            with ui.tab_panel(tab_soft):
                _painel_software(user_nome)
            with ui.tab_panel(tab_backup):
                _painel_backup(user_nome)


# ==================== ABA SOFTWARE ====================

def _painel_software(user_nome: str):
    """Lista recursiva de software/ com checkbox + download zip."""
    wrap = ui.column().classes("w-full gap-3")

    def render():
        wrap.clear()
        with wrap:
            ui.label("Arquivos e executáveis em software/").classes("text-subtitle2 font-bold text-grey-8")
            ui.label("Marque arquivos e/ou pastas (pasta marcada baixa tudo dentro) e clique em Baixar selecionados.").classes("text-caption text-grey-6")

            itens = tec.listar_software()
            if not itens and not tec.listar_software_recursivo():
                ui.label("Nenhum arquivo em software/. Peça ao administrador para disponibilizar.").classes("text-grey-6 italic p-2")
                with ui.row().classes("w-full justify-center mt-2"):
                    botao("Atualizar", icone="refresh", on_click=render, variante="texto", chave_modulo="tecnico")
                return

            # Estado de seleção por relativo
            selecionados = {}

            # Lista hierárquica simples (1 nível + expansão sob demanda)
            with ui.column().classes("w-full border rounded-lg bg-white p-2 gap-1"):
                # Mostrar todos recursivamente como lista plana com checkbox (pasta indica diretório)
                todos_rels = tec.listar_software_recursivo()
                # Também listar pastas vazias
                pastas = set()
                for rel in todos_rels:
                    partes = rel.split("/")
                    for i in range(1, len(partes)):
                        pastas.add("/".join(partes[:i]))
                # Combina pastas + arquivos
                todos_itens = sorted(pastas) + todos_rels
                # Deduplica mantendo ordem
                vistos = set()
                ordem = []
                for r in todos_itens:
                    if r not in vistos:
                        vistos.add(r)
                        ordem.append(r)

                if not ordem:
                    ui.label("Pasta software vazia.").classes("text-grey-6")
                for rel in ordem:
                    eh_pasta = rel in pastas
                    # tamanho apenas para arquivos
                    tam_str = ""
                    if not eh_pasta:
                        try:
                            p = os.path.join(tec.PASTA_SOFTWARE, rel.replace("/", os.sep))
                            s = os.path.getsize(p)
                            tam_str = _fmt_bytes(s)
                        except Exception:
                            tam_str = ""
                    with ui.row().classes("w-full items-center gap-2 py-1 px-2 hover:bg-blue-50/50 rounded"):
                        cb = ui.checkbox(value=False).on_value_change(
                            lambda e, r=rel: selecionados.__setitem__(r, bool(e.value))
                        ).props(f'data-testid=tecnico-soft-{_safe_id(rel)}')
                        selecionados[rel] = False
                        ui.icon("folder" if eh_pasta else "description").classes("text-grey-6")
                        ui.label(rel).classes("grow text-body2" + (" font-medium" if eh_pasta else ""))
                        if tam_str:
                            ui.label(tam_str).classes("text-caption text-grey-5")

            def baixar():
                alvos = [r for r, v in selecionados.items() if v]
                if not alvos:
                    notificar("Selecione ao menos um arquivo/pasta", type="warning")
                    return
                try:
                    zip_path = tec.criar_zip_selecionados(alvos, owner=user_nome)
                    ui.download(zip_path, filename="software_selecionados.zip")
                    notificar(f"Download iniciado ({len(alvos)} item(ns))", type="positive")
                except Exception as e:
                    log.exception(f"download software falhou: {e}")
                    notificar(f"Falha ao gerar zip: {e}", type="negative")

            with ui.row().classes("w-full justify-center gap-2 mt-2 flex-wrap"):
                botao("Baixar selecionados", icone="download", on_click=baixar,
                      variante="primario", chave_modulo="tecnico",
                      extra_classes="min-w-[220px]").props('data-testid=tecnico-baixar')
                botao("Atualizar", icone="refresh", on_click=render, variante="texto", chave_modulo="tecnico")

    render()


def _fmt_bytes(n: int) -> str:
    try:
        n = int(n)
    except Exception:
        return ""
    for uni in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n} {uni}" if uni == "B" else f"{n:.1f} {uni}"
        n /= 1024
    return f"{n:.1f} TB"


def _safe_id(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", s)[:40]


# ==================== ABA BACKUP ====================

def _painel_backup(user_nome: str):
    """Fluxo: Criar pasta YYYYMMDD_HHMM_nomePc_ip + upload (webkitdirectory) + lista por owner."""
    wrap = ui.column().classes("w-full gap-3")

    # Sugerir IP do cliente via header (fail-soft)
    ip_sugerido = ""
    try:
        from nicegui.client import Client
        # Não há acesso síncrono ao request aqui; usaremos placeholder
        ip_sugerido = ""
    except Exception:
        pass

    def render():
        wrap.clear()
        with wrap:
            ui.label("Backup do PC a formatar").classes("text-subtitle2 font-bold text-grey-8")
            ui.label("1) Crie a pasta no servidor (nome automático). 2) Envie os arquivos do usuário. 3) Só você (dono) poderá baixar depois para restaurar.").classes("text-caption text-grey-6")

            with ui.card().classes("w-full p-4 gap-3"):
                ui.label("Criar pasta de backup no servidor").classes("text-subtitle2 font-bold")
                ui.label("Nome automático: YYYYMMDD_HHMM_nomePc_ip (ex.: 20260918_1430_NOTE07_192_168_1_10)").classes("text-caption text-grey-6")
                with ui.row().classes("w-full gap-3 flex-wrap"):
                    inp_pc = ui.input("Nome do PC *", placeholder="ex.: NOTE07, PC-DA-RECEPCAO").props("outlined dense").classes("flex-1 min-w-[220px]") \
                        .props('data-testid=tecnico-backup-nomepc')
                    inp_ip = ui.input("IP do PC *", placeholder="ex.: 192.168.1.50", value=ip_sugerido).props("outlined dense").classes("flex-1 min-w-[220px]") \
                        .props('data-testid=tecnico-backup-ip')
                # Preview do nome
                lbl_prev = ui.label("Prévia: —").classes("text-caption text-grey-7")

                def atualiza_prev():
                    try:
                        prev = tec.nome_pasta_backup(inp_pc.value or "pc", inp_ip.value or "sem_ip")
                        lbl_prev.text = f"Prévia: {prev}/"
                    except Exception:
                        pass
                inp_pc.on_value_change(lambda e: atualiza_prev())
                inp_ip.on_value_change(lambda e: atualiza_prev())
                atualiza_prev()

                pasta_criada = {"nome": ""}

                def criar():
                    ok, msg = tec.criar_pasta_backup(user_nome, inp_pc.value or "", inp_ip.value or "")
                    notificar(msg, type="positive" if ok else "negative")
                    if ok:
                        pasta_criada["nome"] = msg  # msg é pasta_nome quando ok
                        render()  # re-render para mostrar área de upload

                botao("Criar pasta no servidor", icone="create_new_folder", on_click=criar,
                      variante="primario", chave_modulo="tecnico").props('data-testid=tecnico-criar-pasta')

            # Se já há backups do owner, mostrar área de upload + lista
            backups = tec.listar_backups(owner=user_nome, apenas_owner=True)
            if not backups:
                ui.label("Nenhum backup seu ainda. Crie a pasta acima para começar.").classes("text-grey-6 italic")
                return

            ui.separator()
            ui.label("Meus backups (somente você vê)").classes("text-subtitle2 font-bold text-grey-8")

            # Seletor da pasta alvo para upload
            opcoes = {b[1]: f"{b[1]} — {b[7][:16] if b[7] else ''} ({b[5]} bytes)" for b in backups}
            sel_pasta = ui.select(opcoes, label="Pasta destino do upload").props("outlined dense").classes("w-full") \
                .props('data-testid=tecnico-backup-select')
            if backups:
                sel_pasta.value = backups[0][1]

            # Upload: múltiplos arquivos + webkitdirectory (quando técnico está no PC alvo)
            ui.label("Envio: selecione os arquivos das pastas do usuário (Documentos, Imagens, Vídeos etc.). Dica: arraste a pasta ou use Ctrl para múltiplos. Navegadores modernos permitem selecionar pasta inteira via 'webkitdirectory'.").classes("text-caption text-grey-6")

            # Mensagem de ajuda para 1-clique
            with ui.card().classes("w-full bg-blue-50 border border-blue-200 p-3"):
                ui.label("Backup 1-clique (quando no PC a formatar)").classes("text-caption font-bold text-blue-9")
                ui.label("No PC que vai formatar, abra esta página (/tecnico → Backup), crie a pasta e, no campo de envio abaixo, selecione a pasta do usuário (ex.: C:\\Users\\Joao\\Documents) — o navegador enviará todo o conteúdo com a estrutura de subpastas preservada. Se não aparecer a opção de pasta, selecione múltiplos arquivos com Ctrl+A.").classes("text-caption text-blue-8")

            async def ao_upload(e):
                pasta = sel_pasta.value
                if not pasta:
                    notificar("Selecione a pasta de destino", type="warning")
                    return
                # e.files pode ser lista de UploadedFile com .name e .read()
                arquivos = []
                for f in e.files or []:
                    try:
                        conteudo = await f.read()
                        # f.name pode conter caminho relativo quando webkitdirectory (ex.: Documents/foto.jpg)
                        nome = getattr(f, "name", "arquivo") or "arquivo"
                        arquivos.append((nome, conteudo))
                    except Exception as ex:
                        log.warning(f"upload read falhou {f}: {ex}")
                if not arquivos:
                    notificar("Nenhum arquivo recebido", type="warning")
                    return
                ok, msg = tec.salvar_arquivos_backup(pasta, arquivos, owner=user_nome)
                notificar(msg, type="positive" if ok else "negative")
                if ok:
                    render()

            up = ui.upload(label="Selecionar arquivos/pasta do usuário (arraste aqui)", multiple=True, auto_upload=True, on_multi_upload=ao_upload).props("accept=*/*").classes("w-full") \
                .props('data-testid=tecnico-upload')
            # Tenta habilitar webkitdirectory via JS (fail-soft)
            try:
                ui.run_javascript("""
                    setTimeout(() => {
                        const inp = document.querySelector('[data-testid=tecnico-upload] input[type=file]');
                        if (inp) { inp.setAttribute('webkitdirectory',''); inp.setAttribute('directory',''); }
                    }, 800);
                """)
            except Exception:
                pass

            # Lista de backups com ações
            with ui.column().classes("w-full gap-2 mt-2"):
                for bid, pasta_nome, owner, ip, host, tam, status, data in backups:
                    with ui.card().classes("w-full p-3 gap-2"):
                        with ui.row().classes("w-full items-center justify-between flex-wrap"):
                            with ui.column().classes("gap-0"):
                                ui.label(pasta_nome).classes("font-bold text-grey-9")
                                ui.label(f"Dono: {owner} • IP: {ip} • Host: {host} • {data[:16] if data else ''} • {tam} bytes • {status}").classes("text-caption text-grey-6")
                            with ui.row().classes("gap-2"):
                                def _baixar(p=pasta_nome):
                                    try:
                                        zp = tec.criar_zip_backup(p, owner=user_nome)
                                        ui.download(zp, filename=f"{p}.zip")
                                        notificar(f"Download de {p} iniciado", type="positive")
                                    except Exception as ex:
                                        notificar(str(ex), type="negative")
                                botao("Baixar pasta (zip)", icone="folder_zip", on_click=_baixar, variante="secundario", chave_modulo="tecnico",
                                      extra_classes="shrink-0").props(f'data-testid=tecnico-baixar-{_safe_id(pasta_nome)}')
                                # Listar arquivos da pasta (preview)
                                def _listar(p=pasta_nome):
                                    _dlg_listar(p, user_nome)
                                botao_icone("visibility", on_click=_listar, tooltip="Ver arquivos", chave_modulo="tecnico")

            with ui.row().classes("w-full justify-center mt-2"):
                botao("Atualizar", icone="refresh", on_click=render, variante="texto", chave_modulo="tecnico")

    render()


def _dlg_listar(pasta_nome: str, user_nome: str):
    from nicegui import ui as _ui
    from mod_intranet.ui_comum import dialogo_card
    row = tec.obter_backup(pasta_nome)
    if not row:
        notificar("Backup não encontrado", type="negative")
        return
    caminho = tec._pasta_backup_path(pasta_nome)
    if not os.path.isdir(caminho):
        notificar("Pasta física vazia ou removida", type="warning")
        return
    arquivos = []
    for root, _, files in os.walk(caminho):
        for f in files:
            rel = os.path.relpath(os.path.join(root, f), caminho).replace(os.sep, "/")
            arquivos.append(rel)
    with dialogo_card(titulo=f"Arquivos — {pasta_nome}", largura="w-full max-w-[640px] mx-4", chave_modulo="tecnico") as (dlg, card):
        with ui.column().classes("w-full gap-1 max-h-[60vh] overflow-auto"):
            if not arquivos:
                ui.label("Pasta vazia.").classes("text-grey-6 italic")
            for a in sorted(arquivos)[:200]:
                ui.label(a).classes("text-caption font-mono")
            if len(arquivos) > 200:
                ui.label(f"... e mais {len(arquivos)-200} arquivo(s)").classes("text-caption text-grey-5")
        with ui.row().classes("w-full justify-end mt-3"):
            ui.button("Fechar", on_click=dlg.close).props("flat")
    dlg.open()
