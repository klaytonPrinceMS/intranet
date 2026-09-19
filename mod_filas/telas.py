"""Tela do módulo Filas — esqueleto (gestor de chamadas + TV).

EN: Queue screen skeleton — call manager + TV display.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from nicegui import ui
from mod_intranet import autenticacao
from mod_intranet.aba_modulo import cabecalho
from mod_intranet.tema_modulo import ler_tema
from mod_intranet.ui_comum import botao
from mod_filas import bd_manipulador as filas

def _pode_acessar(user_nome: str, perfil: str) -> bool:
    if perfil == "administrador_geral":
        return True
    try:
        return autenticacao.validar_acesso_modulo(user_nome, "filas")
    except Exception:
        return False

def mostrar_tela(user_nome: str, perfil_global: str = ""):
    if not _pode_acessar(user_nome, perfil_global):
        with ui.column().classes("w-full items-center p-12 gap-3"):
            ui.icon("block", size="64px").classes("text-red-8")
            ui.label("Acesso restrito").classes("text-h6")
            ui.label("Somente usuários com acesso ao módulo Filas.").classes("text-body2 text-grey-7")
        return
    tema = ler_tema("filas", cor_botao="#000000", cor_texto_botao="#FFFFFF",
                    texto_header="Gestor de chamadas para atendimento (TV). Esqueleto a título de conhecimento.")
    ui.colors(primary=tema["cor_botao"])
    with ui.column().classes("w-full p-6 gap-4"):
        cabecalho("Filas — Chamadas", tema["texto_header"], chave_modulo="filas",
                  cor_titulo=tema["cor_titulo"], cor_fundo=tema["cor_fundo"])
        with ui.row().classes("w-full gap-4 flex-wrap"):
            with ui.card().classes("flex-1 min-w-[320px] p-4 gap-3"):
                ui.label("Filas (esqueleto)").classes("text-h6 font-bold")
                ui.label("Este é o esqueleto do gestor de chamadas. A TV exibirá a última senha chamada.").classes("text-caption text-grey-6")
                box = ui.column().classes("w-full gap-2")
                def render():
                    box.clear()
                    with box:
                        for fid, nome, senha, status, guiche, data in filas.listar_filas():
                            with ui.row().classes("w-full items-center justify-between border rounded p-2"):
                                with ui.column().classes("gap-0"):
                                    ui.label(nome).classes("font-bold")
                                    ui.label(f"Senha atual: {senha} • Guichê: {guiche} • {status}").classes("text-caption text-grey-6")
                                def _chamar(fid=fid):
                                    ok, msg = filas.gerar_senha(fid, ator=user_nome)
                                    ui.notify(msg, type="positive" if ok else "negative")
                                    render()
                                botao("Chamar próximo", icone="campaign", on_click=_chamar, variante="primario", chave_modulo="filas")
                render()
                with ui.row().classes("w-full justify-center mt-2"):
                    botao("Abrir TV", icone="tv", on_click=lambda: ui.navigate.to("/tv"), variante="contorno", chave_modulo="filas").props('data-testid=filas-abrir-tv')
            with ui.card().classes("flex-1 min-w-[320px] p-4 gap-3"):
                ui.label("Última chamada (preview TV)").classes("text-h6 font-bold")
                ult = filas.ultima_chamada()
                if ult:
                    senha, guiche, data = ult
                    ui.label(f"Senha: {senha}").classes("text-h4 font-extrabold text-primary")
                    ui.label(f"Guichê: {guiche} • {data[:16] if data else ''}").classes("text-subtitle1")
                else:
                    ui.label("Nenhuma chamada ainda.").classes("text-grey-6 italic")
                ui.separator()
                ui.label("Histórico (5 últimas)").classes("text-caption font-bold")
                for _, _, senha, guiche, data, por in filas.listar_chamadas(5):
                    ui.label(f"{senha} — guichê {guiche} — {por} — {data[:16] if data else ''}").classes("text-caption")

def mostrar_tv():
    """Tela da TV — full-screen, auto-refresh a cada 3s + carrossel de notícias."""
    from mod_intranet.tema_modulo import ler_tema as _ler
    tema = _ler("filas")
    ui.colors(primary=tema.get("cor_botao", "#000000"))
    with ui.column().classes("w-full h-screen bg-black text-white gap-4 p-4").style("min-height: 100vh"):
        # Topo: chamada
        with ui.column().classes("w-full items-center justify-center gap-4 flex-1"):
            lbl_topo = ui.label("FILA — AGUARDE CHAMADA").classes("text-[2vw] tracking-widest text-grey-4")
            lbl_senha = ui.label("—").classes("text-[10vw] font-extrabold leading-none")
            lbl_guiche = ui.label("").classes("text-[4vw] font-bold")
        # Rodapé: carrossel de notícias (título + descrição) do agregador
        with ui.card().classes("w-full bg-grey-900 text-white p-4 gap-2").style("min-height: 18vh"):
            ui.label("Notícias — agregador").classes("text-caption tracking-widest text-grey-4")
            lbl_n_titulo = ui.label("Aguardando notícias...").classes("text-[1.6vw] font-bold leading-tight")
            lbl_n_desc = ui.label("").classes("text-[1vw] text-grey-3 leading-tight")
            lbl_n_fonte = ui.label("").classes("text-caption text-grey-5")

        noticias_tv = {"lista": [], "idx": 0}

        def refresh_chamada():
            ult = filas.ultima_chamada()
            if ult:
                senha, guiche, data = ult
                lbl_senha.text = str(senha)
                lbl_guiche.text = f"Guichê {guiche}"
            try:
                ui.run_javascript("try{const a=new AudioContext();const o=a.createOscillator();o.connect(a.destination);o.start();o.stop(a.currentTime+0.2);}catch(e){}")
            except Exception:
                pass

        def carregar_noticias():
            try:
                from mod_agregador_noticias.bd_manipulador import listar_para_tv, habilitado
                if not habilitado():
                    lbl_n_titulo.text = "Agregador desabilitado — ative em /admin/agregador_noticias"
                    lbl_n_desc.text = ""
                    lbl_n_fonte.text = ""
                    return
                lst = listar_para_tv(limite=10)
                if lst:
                    noticias_tv["lista"] = lst
                    noticias_tv["idx"] = 0
                    _mostrar_noticia()
                else:
                    lbl_n_titulo.text = "Nenhuma notícia ainda — aguarde coleta"
            except Exception:
                pass

        def _mostrar_noticia():
            lst = noticias_tv["lista"]
            if not lst:
                return
            idx = noticias_tv["idx"] % len(lst)
            item = lst[idx]
            lbl_n_titulo.text = item.get("titulo", "")[:120]
            lbl_n_desc.text = (item.get("descricao", "") or "")[:180]
            lbl_n_fonte.text = f"{item.get('fonte','')} • {item.get('tema','')}"
            noticias_tv["idx"] = (idx + 1) % len(lst)

        ui.timer(3.0, refresh_chamada)
        ui.timer(7.0, _mostrar_noticia)
        refresh_chamada()
        carregar_noticias()
        # recarrega lista a cada 2 minutos
        ui.timer(120.0, carregar_noticias)
