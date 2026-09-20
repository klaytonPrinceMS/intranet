"""Tela pura do Agregador — estilo original Noticia (gerarSite) com cards atuais.

EN: Pure display — original Noticia style with current cards.
Copia o padrão de exibição do repositório https://github.com/klaytonPrinceMS/Noticia
(intro overlay, about section com tema, info-list) porém com os cards em uso
(tema badge + tempo relativo, título link, descrição, miniatura 30×30 + ícone fonte 16×16).
CSS/JS originais em assets/noticia/ são servidos via rota estática /assets/noticia/*.
"""

import sys, os, re
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from nicegui import ui
from mod_intranet import autenticacao
from mod_intranet.tema_modulo import ler_tema
from mod_agregador_noticias import bd_manipulador as ag


def _tempo_relativo(s: str) -> str:
    if not s:
        return ""
    try:
        t = str(s).strip().replace("T", " ").replace("Z", "")
        t = re.split(r"\.\d+", t)[0]
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                dt = __import__("datetime").datetime.strptime(t[:19], fmt)
                break
            except Exception:
                continue
        else:
            return t[:16]
        agora = __import__("datetime").datetime.now()
        seg = int((agora - dt).total_seconds())
        if seg < 60:
            return "agora"
        if seg < 3600:
            return f"{seg//60} minutos atrás"
        if seg < 86400:
            return f"{seg//3600} horas atrás"
        if seg < 604800:
            return f"{seg//86400} dias atrás"
        return f"{seg//604800} semanas atrás"
    except Exception:
        return (s or "")[:16]


def mostrar_tela_pura(user_nome: str, perfil_global: str = ""):
    # permissão igual ao agregador normal
    if perfil_global != "administrador_geral":
        try:
            if not autenticacao.validar_acesso_modulo(user_nome, "agregador_noticias"):
                with ui.column().classes("w-full items-center p-12 gap-3"):
                    ui.icon("block", size="64px").classes("text-red-8")
                    ui.label("Acesso restrito").classes("text-h6")
                return
        except Exception:
            pass

    # Injeta CSS/JS originais do Noticia (copiados para assets/noticia/)
    # Servidos via rota /assets/noticia/* montada em main.py
    ui.add_head_html("""
    <link rel="stylesheet" href="/assets/noticia/css/base.css">
    <link rel="stylesheet" href="/assets/noticia/css/vendor.css">
    <link rel="stylesheet" href="/assets/noticia/css/main.css">
    <link rel="stylesheet" href="/assets/noticia/css/font-awesome/css/font-awesome.min.css">
    <link rel="stylesheet" href="/assets/noticia/css/micons/micons.css">
    <link rel="icon" type="image/png" href="/assets/noticia/favicon.png">
    <script src="/assets/noticia/js/modernizr.js"></script>
    <script src="/assets/noticia/js/pace.min.js"></script>
    """)

    tema = ler_tema("agregador_noticias", cor_botao="#000000", cor_texto_botao="#FFFFFF",
                    texto_header="Exibição pura do modelo Noticia — intro + lista info-list, com cards atuais")
    ui.colors(primary=tema["cor_botao"])

    # Busca notícias mais recentes (10) ordenadas por data real
    noticias = ag.listar_noticias(limite=12)

    # Intro overlay puro Noticia
    with ui.element("section").classes("w-full").style("background:#111417;color:#fff;padding:2rem 0;"):
        with ui.element("div").classes("intro-overlay"):
            pass
        with ui.element("div").classes("intro-content"):
            with ui.element("div").classes("row"):
                with ui.element("div").classes("col-twelve"):
                    ui.label("PRINCE. K,B.").classes("text-caption tracking-widest")
                    ui.label("DTI - Notícias").classes("text-h2 font-bold")
                    ui.label("Pref. Municipal — Agregador puro").classes("text-subtitle2 opacity-80")
                    with ui.row().classes("gap-2 mt-4"):
                        ui.button("Início", on_click=lambda: ui.navigate.to("/agregador-noticias")).props("outline color=white")
                        ui.button("Fim", on_click=lambda: ui.run_javascript("window.scrollTo(0, document.body.scrollHeight)")).props("outline color=white")

    # About section puro Noticia com tema e lista info-list, porém cards atuais dentro
    with ui.element("section").classes("w-full bg-white py-8"):
        with ui.element("div").classes("row section-intro"):
            with ui.element("div").classes("col-twelve"):
                ui.label("Principais notícias").classes("text-h6 tracking-widest text-grey-6")
                ui.label(f"Tema: Todos • {len(noticias)} notícias (3 colunas atuais dentro do modelo puro)").classes("text-h5 font-bold")

        with ui.element("div").classes("row about-content"):
            with ui.element("div").classes("col-six tab-full"):
                with ui.element("ul").classes("info-list"):
                    for nid, titulo, fonte, tema_n, url, img, fonte_icon, desc, data_pub, data_col in noticias:
                        href = url or "#"
                        tempo = _tempo_relativo(data_pub or data_col)
                        with ui.element("li").classes("border-b py-3"):
                            # Linha com ícone fonte + tempo + tema
                            with ui.row().classes("w-full items-center gap-2"):
                                if fonte_icon:
                                    try:
                                        ui.image(fonte_icon).classes("shrink-0 rounded").style("width:16px;height:16px;object-fit:contain;")
                                    except Exception:
                                        pass
                                ui.label(tema_n or "Geral").classes("text-caption font-bold bg-grey-2 px-2 py-0.5 rounded")
                                ui.label(tempo).classes("text-caption text-grey-5")
                                ui.label(fonte or "").classes("text-caption text-grey-5 ml-auto")
                            # Título com miniatura 30x30 antes
                            with ui.row().classes("w-full items-start gap-2 mt-1"):
                                if img:
                                    try:
                                        ui.image(img).classes("shrink-0 rounded").style("width:30px;height:30px;object-fit:cover;")
                                    except Exception:
                                        pass
                                ui.link(titulo, target=href, new_tab=True).classes("font-bold text-grey-9 hover:text-primary flex-1").style("word-break: break-word;")
                            if desc and desc != titulo:
                                ui.label(desc[:160] + ("…" if len(desc) > 160 else "")).classes("text-caption text-grey-7")
                            with ui.element("div").classes("w-full"):
                                ui.label(href[:60] + ("…" if len(href) > 60 else "")).classes("text-caption text-grey-5 font-mono")
                            ui.html(f'<span><a href="{href}" target="_blank" style="color:#0066cc; font-size:0.85rem;">Abrir no site original →</a></span>')

    # Footer puro Noticia
    with ui.element("footer").classes("w-full bg-grey-900 text-white py-6 mt-8"):
        with ui.element("div").classes("row"):
            with ui.element("div").classes("col-six tab-full"):
                with ui.element("div").classes("copyright"):
                    ui.label("© Copyright DTI — Agregador puro (Noticia) — Design by Klayton").classes("text-caption")
            with ui.element("div").classes("col-six tab-full text-right"):
                ui.link("Voltar ao topo", target="#top").classes("text-caption text-white")

    ui.add_head_html("""
    <script src="/assets/noticia/js/jquery-2.1.3.min.js"></script>
    <script src="/assets/noticia/js/plugins.js"></script>
    <script src="/assets/noticia/js/main.js"></script>
    """)
