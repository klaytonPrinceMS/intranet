"""Painel de administração do Agregador de Notícias (rota /admin/agregador_noticias)."""

import sys, os, json, re
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from nicegui import ui
from mod_intranet.ui_comum import card_admin, rodape_salvar_restaurar, botao
from mod_intranet.tema_modulo import ler_tema, notificar, bloco_aparencia
from mod_intranet import observabilidade
from mod_agregador_noticias import bd_manipulador as ag

log = observabilidade.get_logger("agregador_noticias")


def mostrar_administracao(usuario_logado: str = ""):
    tema = ler_tema("agregador_noticias", cor_botao="#000000", cor_texto_botao="#FFFFFF",
                    texto_header="Fontes, tema de pesquisa e intervalo de coleta.")
    tema["_defaults"] = {
        "cor_botao": "", "cor_texto_botao": "", "cor_fundo": "",
        "cor_titulo": "#212121", "btn_tamanho": "medium",
        "texto_header": "Fontes, tema de pesquisa e intervalo de coleta.",
        "cor_fundo_card": "#FFFFFF", "cor_texto_card": "",
    }
    ui.colors(primary=tema["cor_botao"])
    bloco_aparencia(usuario_logado, "agregador_noticias", tema, prefixo_auditoria="agregador_noticias", com_texto_header=True)

    # === Card Coleta ===
    with card_admin("Coleta — habilitação e intervalo", icone="sync", chave_modulo="agregador_noticias", grade=False):
        ui.label("O sistema investiga fontes com scrapy-like (httpx+parsel). Banco reiniciado 24/24h (limpeza automática).").classes("text-caption text-grey-6")
        sw_hab = ui.switch("Módulo habilitado — coletar notícias automaticamente", value=ag.habilitado()).props("color=primary").classes("mt-1").props('data-testid=agregador-habilitado')
        sw_hab.tooltip("Se desabilitado, nenhuma coleta automática ocorre (só manual via Coletar agora)")

        # Intervalo 10 min – 6h
        val_intervalo = ag.intervalo_min()
        sel_intervalo = ui.select({10: "10 min", 30: "30 min", 60: "1 hora", 120: "2 horas", 180: "3 horas", 360: "6 horas"}, value=val_intervalo, label="Intervalo de coleta").props("outlined dense").classes("w-full sm:w-64").props('data-testid=agregador-intervalo')
        sel_intervalo.tooltip("Mínimo 10 minutos, máximo 6 horas (360 min)")

        inp_termo = ui.input("Conteúdo da pesquisa (termo livre, ex.: Brasil, Monte Santo, economia)", value=ag.termo_pesquisa()).props("outlined dense clearable").classes("w-full").props('data-testid=agregador-termo')
        inp_termo.tooltip("Termo usado na pesquisa Google News (search?q=termo). Deixe vazio para não pesquisar termo livre.")

        # Hora do reinício diário (padrão 06:00 manhã, zera tudo)
        val_hora = ag.obter_hora_reinicio()
        inp_hora = ui.input("Hora do reinício diário (HH:MM, padrão 06:00 manhã)", value=val_hora, placeholder="06:00").props("outlined dense").classes("w-full sm:w-64").props('data-testid=agregador-hora-reinicio')
        inp_hora.tooltip("Banco reciclado diariamente — zera todas as notícias na hora definida. Ex: 06:00")

        def salvar_coleta():
            ag.definir_habilitado(bool(sw_hab.value), ator=usuario_logado)
            ok, v = ag.definir_intervalo(int(sel_intervalo.value or 60), ator=usuario_logado)
            ag.definir_termo(inp_termo.value or "", ator=usuario_logado)
            ok_h, msg_h = ag.definir_hora_reinicio(inp_hora.value or "06:00", ator=usuario_logado)
            if not ok_h:
                notificar(msg_h, type="negative")
                return
            hora_atual = ag.obter_hora_reinicio()
            try:
                from mod_intranet.rotinas import reconfigurar_agregador_noticias
                reconfigurar_agregador_noticias()
            except Exception:
                pass
            notificar(f"Coleta {'habilitada' if sw_hab.value else 'desabilitada'} • intervalo {v} min • reinício {hora_atual}", type="positive")
            ui.timer(1.0, lambda: ui.navigate.reload(), once=True)

        def restaurar_coleta():
            ag.definir_habilitado(False, ator=usuario_logado)
            ag.definir_intervalo(60, ator=usuario_logado)
            ag.definir_termo("", ator=usuario_logado)
            ag.definir_hora_reinicio("06:00", ator=usuario_logado)
            try:
                from mod_intranet.rotinas import reconfigurar_agregador_noticias
                reconfigurar_agregador_noticias()
            except Exception:
                pass
            ui.timer(1.0, lambda: ui.navigate.reload(), once=True)

        rodape_salvar_restaurar(salvar_coleta, restaurar_coleta, chave_modulo="agregador_noticias", rotulo_salvar="Salvar coleta", data_testid="agregador-salvar-coleta")

        with ui.row().classes("w-full gap-2 mt-2 flex-wrap"):
            _estado_adm = {"ocupado": False}
            async def _coletar_agora():
                if _estado_adm["ocupado"]:
                    notificar("Coleta em andamento…", type="warning")
                    return
                _estado_adm["ocupado"] = True
                spinner = ui.spinner(size="lg").props("aria-label=Coletando notícias")
                try:
                    from nicegui import run as _run
                    n = await _run.io_bound(lambda: ag.coletar_todas(ator=usuario_logado, forcar=True))
                    notificar(f"Coleta manual: {n} novas", type="positive" if n else "info")
                    # limpa antigas também
                    try:
                        ag.limpar_antigas(24)
                    except Exception:
                        pass
                except Exception as e:
                    notificar(f"Falha na coleta: {e}", type="negative")
                finally:
                    try:
                        spinner.delete()
                    except Exception:
                        pass
                    _estado_adm["ocupado"] = False
            botao("Coletar agora", icone="cloud_download", on_click=_coletar_agora, variante="contorno", chave_modulo="agregador_noticias").props('data-testid=agregador-coletar-agora')
            def _limpar():
                n = ag.limpar_antigas(24)
                notificar(f"Limpeza 24h: {n} removidas", type="info")
            botao("Limpar antigas (24h)", icone="delete_sweep", on_click=_limpar, variante="texto", chave_modulo="agregador_noticias")

    # === Card Fontes ===
    with card_admin("Fontes de notícias — Google News, RSS e outras", icone="rss_feed", chave_modulo="agregador_noticias", grade=False):
        ui.label("Preveja não apenas Google News, mas outras fontes (BBC, JFP, RSS genérico). Adicione/edite abaixo.").classes("text-caption text-grey-6")
        fontes = ag.fontes_config()
        # tabela editável
        box = ui.column().classes("w-full gap-2")
        # estado mutável para edição
        estado_fontes = {"lista": list(fontes)}

        @ui.refreshable
        def render_fontes():
            box.clear()
            with box:
                if not estado_fontes["lista"]:
                    ui.label("Nenhuma fonte. Adicione abaixo.").classes("text-grey-6 italic")
                    return
                for idx, f in enumerate(estado_fontes["lista"]):
                    with ui.row().classes("w-full items-center gap-2 border rounded px-2 py-1"):
                        ui.label(f"{f.get('tipo','')}").classes("text-caption font-bold w-16")
                        ui.label(f.get("nome","")[:30]).classes("text-body2 flex-1")
                        ui.label(f.get("tema","")).classes("text-caption text-grey-6 w-24")
                        ui.label(f.get("url","")[:40] + "…").classes("text-caption text-grey-5 flex-1 hidden sm:flex")
                        def _rem(i=idx):
                            estado_fontes["lista"].pop(i)
                            render_fontes.refresh()
                        ui.button(icon="delete", on_click=_rem).props("flat dense color=negative").tooltip("Remover")

        render_fontes()

        with ui.row().classes("w-full gap-2 flex-wrap mt-2"):
            sel_tipo = ui.select({"google": "Google News", "bbc": "BBC", "jfp": "JFP Notícias", "rss": "RSS genérico"}, value="google", label="Tipo").props("outlined dense").classes("w-[180px]").props('data-testid=agregador-fonte-tipo')
            inp_nome = ui.input("Nome da fonte", placeholder="ex.: Google Brasil").props("outlined dense").classes("flex-1 min-w-[180px]").props('data-testid=agregador-fonte-nome')
            inp_tema = ui.input("Tema", placeholder="ex.: Brasil, Economia").props("outlined dense").classes("w-[160px]").props('data-testid=agregador-fonte-tema')
        inp_url = ui.input("URL da fonte", placeholder="https://news.google.com/... ou https://.../rss.xml").props("outlined dense").classes("w-full").props('data-testid=agregador-fonte-url')

        def adicionar():
            if not (inp_url.value or "").strip():
                notificar("Informe a URL", type="warning")
                return
            nova = {"tipo": sel_tipo.value or "google", "nome": (inp_nome.value or "").strip() or inp_url.value.strip()[:30], "url": inp_url.value.strip(), "tema": (inp_tema.value or "Geral").strip() or "Geral"}
            estado_fontes["lista"].append(nova)
            inp_url.value = ""; inp_nome.value = ""; inp_tema.value = ""
            inp_url.update(); inp_nome.update(); inp_tema.update()
            render_fontes.refresh()
        botao("Adicionar fonte", icone="add", on_click=adicionar, variante="texto", chave_modulo="agregador_noticias").props('data-testid=agregador-add-fonte')

        def salvar_fontes():
            ok, msg = ag.definir_fontes(estado_fontes["lista"], ator=usuario_logado)
            notificar(msg, type="positive" if ok else "negative")
            if ok:
                ui.timer(0.5, lambda: ui.navigate.reload(), once=True)
        def restaurar_fontes():
            from mod_agregador_noticias.bd_manipulador import FONTES_PADRAO
            estado_fontes["lista"] = list(FONTES_PADRAO)
            render_fontes.refresh()
            ag.definir_fontes(FONTES_PADRAO, ator=usuario_logado)
            ui.timer(0.5, lambda: ui.navigate.reload(), once=True)

        rodape_salvar_restaurar(salvar_fontes, restaurar_fontes, chave_modulo="agregador_noticias", rotulo_salvar="Salvar fontes", data_testid="agregador-salvar-fontes")

    # === Card Temas ===
    with card_admin("Temas — separar notícias por temas", icone="category", chave_modulo="agregador_noticias", grade=False):
        temas = ag.temas_config()
        inp_temas = ui.input("Temas (separados por vírgula)", value=", ".join(temas)).props("outlined dense").classes("w-full").props('data-testid=agregador-temas')
        inp_temas.tooltip("Ex.: Brasil, Internacional, Economia, Saúde, Geral")
        def salvar_temas():
            lista = [t.strip() for t in (inp_temas.value or "").split(",") if t.strip()]
            if not lista:
                notificar("Informe ao menos um tema", type="warning")
                return
            ag.definir_temas(lista, ator=usuario_logado)
            notificar(f"{len(lista)} temas salvos", type="positive")
            ui.timer(1.0, lambda: ui.navigate.reload(), once=True)
        def restaurar_temas():
            from mod_agregador_noticias.bd_manipulador import TEMAS_PADRAO
            ag.definir_temas(TEMAS_PADRAO, ator=usuario_logado)
            ui.timer(1.0, lambda: ui.navigate.reload(), once=True)
        rodape_salvar_restaurar(salvar_temas, restaurar_temas, chave_modulo="agregador_noticias", rotulo_salvar="Salvar temas", data_testid="agregador-salvar-temas")

    # === Card Censura — palavras bloqueadas ===
    with card_admin("Censura de conteúdo — palavras bloqueadas", icone="lock", chave_modulo="agregador_noticias", grade=False):
        ui.label("Títulos com estas palavras são descartados na coleta e ocultados na TV (ex: tinder, suicídio). Separe por vírgula, ponto e vírgula ou linha. Vale para Blog e Agregador.").classes("text-caption text-grey-6")
        from mod_intranet.censura import obter_palavras_bloqueadas, definir_palavras_bloqueadas
        palavras_atuais = ", ".join(obter_palavras_bloqueadas())
        inp_censura_ag = ui.textarea("Palavras bloqueadas", value=palavras_atuais, placeholder="ex: tinder, suicidio, aposta").props("outlined dense").classes("w-full").props('data-testid=agregador-palavras-bloqueadas')
        inp_censura_ag.tooltip("Insensível a maiúscula/acentos; 'suicidio' bloqueia 'suicídio'")

        def salvar_censura_ag():
            lista = []
            raw = (inp_censura_ag.value or "")
            import re as _re
            for p in _re.split(r"[,\n;]+", raw):
                pp = p.strip()
                if pp:
                    lista.append(pp)
            ok = definir_palavras_bloqueadas(lista, ator=usuario_logado)
            notificar("Censura salva" if ok else "Falha ao salvar", type="positive" if ok else "negative")
            if ok:
                try:
                    from mod_agregador_noticias.bd_manipulador import limpar_censuradas
                    n = limpar_censuradas()
                    if n:
                        notificar(f"{n} notícias censuradas removidas", type="info")
                except Exception:
                    pass
                ui.timer(0.5, lambda: ui.navigate.reload(), once=True)

        def restaurar_censura_ag():
            definir_palavras_bloqueadas([], ator=usuario_logado)
            inp_censura_ag.value = ""
            inp_censura_ag.update()
            notificar("Censura removida", type="positive")
            ui.timer(0.5, lambda: ui.navigate.reload(), once=True)

        rodape_salvar_restaurar(salvar_censura_ag, restaurar=restaurar_censura_ag, chave_modulo="agregador_noticias", rotulo_salvar="Salvar censura", data_testid="agregador-salvar-censura")

        with ui.row().classes("w-full gap-2 mt-2"):
            def _limpar_agora():
                try:
                    from mod_agregador_noticias.bd_manipulador import limpar_censuradas
                    n = limpar_censuradas()
                    notificar(f"{n} notícias removidas" if n else "Nenhuma notícia censurada", type="info" if n else "positive")
                except Exception as e:
                    notificar(f"Falha: {e}", type="negative")
            botao("Remover já censuradas agora", icone="delete_sweep", on_click=_limpar_agora, variante="contorno", chave_modulo="agregador_noticias").props('data-testid=agregador-limpar-censuradas')

    # Backup removido — banco reciclado diariamente (reinício às horas da manhã, zera tudo)
    with card_admin("Reinício diário — banco reciclado", icone="restart_alt", chave_modulo="agregador_noticias", grade=False):
        ui.label("Banco de notícias é reciclado diariamente às horas da manhã (padrão 06:00), zerando todas as notícias. Configure a hora acima em Coleta. Auditoria apenas de quem alterou o quê no módulo.").classes("text-caption text-grey-6")
        with ui.row().classes("w-full gap-2 mt-2"):
            def _reiniciar_agora():
                n = ag.reiniciar_banco(ator=usuario_logado)
                notificar(f"Banco reiniciado: {n} notícias apagadas", type="positive" if n else "info")
            botao("Zerar agora (reinício manual)", icone="delete_forever", on_click=_reiniciar_agora, variante="texto", chave_modulo="agregador_noticias").props('data-testid=agregador-reiniciar-agora')
