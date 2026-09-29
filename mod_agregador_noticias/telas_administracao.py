"""EN: News Aggregator admin panel (route /admin/agregador_noticias) — coleta, fontes, temas, censura, reinicio.

PT-BR: Painel de administração do Agregador de Notícias (rota /admin/agregador_noticias).
Cards: Coleta (habilitado/intervalo/termo/hora reinício), Fontes, Temas,
Exibição (notícias por página + os dois textos da tela), Censura, Reinício
diário.

EXIBIÇÃO (29/09/2026): o card "Exibição" é o dono de
`agregador_noticias_por_pagina` (tamanho de página — múltiplo de 3,
mínimo 9), `agregador_noticias_texto_header` (subtítulo do cabeçalho da
tela) e `agregador_noticias_texto_sem_novidade` (aviso da barra de
atualização automática, aceita `{seg}`). Os dois textos NASCEM VAZIOS: a
tela não descreve mais a si mesma em código. O bloco de aparência entra
com `com_texto_header=False` porque a chave do cabeçalho é a mesma — dois
campos para a mesma chave fariam o "Aplicar" das cores sobrescrever o
texto digitado aqui.
"""

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
    # `texto_header` nos padrões é VAZIO de propósito: a chave
    # `agregador_noticias_texto_header` é a mesma que a TELA do Agregador lê,
    # e o "Restaurar padrão" das cores não pode gravar aqui a frase deste
    # painel — ela apareceria como cabeçalho da tela de notícias. O campo de
    # texto do cabeçalho mora no card "Exibição", mais abaixo, e é o único
    # dono da chave (daí `com_texto_header=False` no bloco de aparência).
    tema["_defaults"] = {
        "cor_botao": "", "cor_texto_botao": "", "cor_fundo": "",
        "cor_titulo": "#212121", "btn_tamanho": "medium",
        "texto_header": "",
        "cor_fundo_card": "#FFFFFF", "cor_texto_card": "",
    }
    ui.colors(primary=tema["cor_botao"])
    bloco_aparencia(usuario_logado, "agregador_noticias", tema, prefixo_auditoria="agregador_noticias", com_texto_header=False)

    # === Card Coleta ===
    with card_admin("Coleta — habilitação e intervalo", icone="sync", chave_modulo="agregador_noticias", grade=False):
        ui.label("O sistema investiga fontes com scrapy-like (httpx+parsel). Banco reiniciado 24/24h (limpeza automática).").classes("text-caption text-grey-6")
        sw_hab = ui.switch("Módulo habilitado — coletar notícias automaticamente", value=ag.habilitado()).props("color=primary").classes("mt-1").props('data-testid=agregador-habilitado')
        sw_hab.tooltip("Se desabilitado, nenhuma coleta automática ocorre (só manual via Coletar agora)")

        # Intervalo 60 min (piso 1h) – 9360 min (teto 6,5 dias, mesmo clamp da API intervalo_min())
        val_intervalo = ag.intervalo_min()
        _opcoes = {60: "1 hora (minimo)", 120: "2 horas", 180: "3 horas", 360: "6 horas", 720: "12 horas", 1440: "1 dia", 4320: "3 dias", 9360: "6,5 dias (teto)"}
        if val_intervalo not in _opcoes:
            _opcoes[val_intervalo] = f"{val_intervalo} min (atual)"
        sel_intervalo = ui.select(_opcoes, value=val_intervalo, label="Intervalo de coleta (1 hora – 6,5 dias)").props("outlined dense").classes("w-full sm:w-64").props('data-testid=agregador-intervalo')
        sel_intervalo.tooltip("Minimo 1 hora (a coleta e automatica), teto 9360 minutos (6,5 dias) — mesmo limite da API. Para buscar na hora, use a coleta manual (so admin).")

        # Intervalo de ATUALIZAÇÃO DA TELA (slider) — diferente do intervalo de
        # coleta: é de quanto em quanto a grade checa se apareceu notícia nova.
        val_refresh = ag.refresh_seg()
        lbl_refresh = ui.label(f"{val_refresh} segundos").classes("text-caption text-grey-6")
        # `ui.slider` NÃO aceita `label=` nesta versão do NiceGUI (TypeError
        # ao abrir o painel admin); o rótulo vai por `.props('label')`, como
        # em mod_filas e mod_edit_pdf.
        sl_refresh = ui.slider(min=15, max=600, step=15, value=val_refresh) \
            .props("outlined dense label label-always") \
            .classes("w-full sm:w-96").props('data-testid=agregador-refresh-seg')
        sl_refresh.tooltip("De quanto em quanto a tela checa por notícia nova (15s a 600s). "
                           "A checagem e barata (1 consulta); se houver novidade, so o card novo e "
                           "adicionado, sem recarregar a pagina.")
        sl_refresh.on_value_change(lambda e: lbl_refresh.set_text(f"{int(e.value or 0)} segundos"))

        inp_termo = ui.input("Conteúdo da pesquisa (termo livre, ex.: Brasil, Monte Santo, economia)", value=ag.termo_pesquisa()).props("outlined dense clearable").classes("w-full").props('data-testid=agregador-termo')
        inp_termo.tooltip("Termo usado na pesquisa Google News (search?q=termo). Deixe vazio para não pesquisar termo livre.")

        # Hora do reinício diário (padrão 09:00 manhã, zera tudo — mesmo default do backend obter_hora_reinicio())
        val_hora = ag.obter_hora_reinicio()
        inp_hora = ui.input("Hora do reinício diário (HH:MM, padrão 09:00 manhã)", value=val_hora, placeholder="09:00").props("outlined dense").classes("w-full sm:w-64").props('data-testid=agregador-hora-reinicio')
        inp_hora.tooltip("Banco reciclado diariamente — zera todas as notícias na hora definida. Ex: 09:00")

        def salvar_coleta():
            ag.definir_habilitado(bool(sw_hab.value), ator=usuario_logado)
            ok, v = ag.definir_intervalo(int(sel_intervalo.value or 60), ator=usuario_logado)
            ok_r, v_r = ag.definir_refresh_seg(int(sl_refresh.value or 60), ator=usuario_logado)
            ag.definir_termo(inp_termo.value or "", ator=usuario_logado)
            ok_h, msg_h = ag.definir_hora_reinicio(inp_hora.value or "09:00", ator=usuario_logado)
            if not ok_h:
                notificar(msg_h, type="negative")
                return
            hora_atual = ag.obter_hora_reinicio()
            try:
                from mod_intranet.rotinas import reconfigurar_agregador_noticias
                reconfigurar_agregador_noticias()
            except Exception:
                pass
            notificar(f"Coleta {'habilitada' if sw_hab.value else 'desabilitada'} • intervalo {v} min • "
                      f"atualização da tela {v_r}s • reinício {hora_atual}", type="positive")
            ui.timer(1.0, lambda: ui.navigate.reload(), once=True)

        def restaurar_coleta():
            ag.definir_habilitado(True, ator=usuario_logado)
            ag.definir_intervalo(60, ator=usuario_logado)
            ag.definir_refresh_seg(60, ator=usuario_logado)
            ag.definir_termo("", ator=usuario_logado)
            ag.definir_hora_reinicio("09:00", ator=usuario_logado)
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
            try:
                ok, msg = ag.definir_fontes(estado_fontes["lista"], ator=usuario_logado)
            except Exception as _e_fontes:
                log.exception(
                    f"falha ao salvar fontes do agº: {_e_fontes}")
                notificar("Erro ao salvar fontes", type="negative")
                return
            notificar(msg, type="positive" if ok else "negative")
            if ok:
                ui.timer(0.5, lambda: ui.navigate.reload(), once=True)
        def restaurar_fontes():
            from mod_agregador_noticias.bd_manipulador import FONTES_PADRAO
            estado_fontes["lista"] = list(FONTES_PADRAO)
            render_fontes.refresh()
            try:
                ag.definir_fontes(FONTES_PADRAO, ator=usuario_logado)
            except Exception as _e_rest_f:
                log.exception(
                    f"falha ao restaurar fontes do agº: {_e_rest_f}")
                notificar("Erro ao restaurar fontes", type="negative")
                return
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

    # === Card Exibição — tamanho de página e textos da tela ===
    with card_admin("Textos da tela — o que o Agregador escreve",
                    icone="view_column", chave_modulo="agregador_noticias", grade=False):
        ui.label("Estes dois textos NASCEM VAZIOS: a tela do Agregador não "
                 "escreve mais descrição de si mesma. O que ela escrever é o "
                 "administrador que decide. O tamanho de página NÃO está "
                 "aqui — quem escolhe quantas notícias vai ler é cada pessoa, "
                 "no controle “Por página” da própria tela de notícias, e a "
                 "escolha fica no navegador dela. Aqui fica só o padrão do "
                 "módulo, para quem não mexe em nada."
                 ).classes("text-caption text-grey-6")

        # Os DOIS textos nascem VAZIOS: a tela do Agregador não escreve mais
        # descrição de si mesma no código — quem escreve é o administrador.
        # (O cabeçalho é o MESMO campo que o tema do módulo usa, por isso
        # `com_texto_header=False` no bloco de aparência acima: uma chave,
        # um dono, um campo — dois campos para a mesma chave fariam o
        # "Aplicar" das cores sobrescrever o texto digitado aqui.)
        inp_header = ui.input("Texto do cabeçalho", value=ag.texto_header(),
                              placeholder="Ex.: Notícias agregadas de múltiplas fontes") \
            .props("outlined dense clearable").classes("w-full") \
            .props('data-testid=agregador-texto-header')
        inp_header.tooltip("Subtítulo abaixo do título “Agregador de Notícias”. "
                           "VAZIO = a tela não mostra cabeçalho nenhum.")

        inp_sem = ui.input("Texto de 'sem novidade'", value=ag.texto_sem_novidade(),
                           placeholder="Sem novidade • próxima checagem em {seg}s") \
            .props("outlined dense clearable").classes("w-full") \
            .props('data-testid=agregador-texto-sem-novidade')
        inp_sem.tooltip("Aviso da barra quando a checagem automática não achou "
                        "nada novo. Use {seg} para o intervalo em segundos. "
                        "VAZIO = nada aparece.")

        def salvar_exibicao():
            # Só os DOIS textos. O tamanho de página saiu daqui: é escolha de
            # quem lê, e cada pessoa ajusta o seu na tela de notícias.
            try:
                ok_h, _ = ag.definir_texto_header(inp_header.value or "", ator=usuario_logado)
                ok_s, _ = ag.definir_texto_sem_novidade(inp_sem.value or "", ator=usuario_logado)
                if not (ok_h and ok_s):
                    notificar("Falha ao salvar os textos — nada foi alterado",
                              type="negative")
                    return
                _tem_header = "sim" if (inp_header.value or "").strip() else "não"
                _tem_sem = "sim" if (inp_sem.value or "").strip() else "não"
                notificar(f"Textos salvos: cabeçalho {_tem_header} • "
                          f"'sem novidade' {_tem_sem}",
                          type="positive")
                ui.timer(1.0, lambda: ui.navigate.reload(), once=True)
            except Exception:
                log.exception("falha ao salvar os textos do agregador")
                notificar("Erro ao salvar os textos", type="negative")

        def restaurar_exibicao():
            try:
                ag.definir_texto_header("", ator=usuario_logado)
                ag.definir_texto_sem_novidade("", ator=usuario_logado)
                notificar("Textos restaurados: a tela não escreve nada",
                          type="positive")
                ui.timer(1.0, lambda: ui.navigate.reload(), once=True)
            except Exception:
                log.exception("falha ao restaurar os textos do agregador")
                notificar("Erro ao restaurar os textos", type="negative")

        rodape_salvar_restaurar(salvar_exibicao, restaurar_exibicao,
                                chave_modulo="agregador_noticias",
                                rotulo_salvar="Salvar textos",
                                data_testid="agregador-salvar-exibicao")

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
        ui.label("Banco de notícias é reciclado diariamente às horas da manhã (padrão 09:00), zerando todas as notícias. Configure a hora acima em Coleta. Auditoria apenas de quem alterou o quê no módulo.").classes("text-caption text-grey-6")
        with ui.row().classes("w-full gap-2 mt-2"):
            def _reiniciar_agora():
                n = ag.reiniciar_banco(ator=usuario_logado)
                notificar(f"Banco reiniciado: {n} notícias apagadas", type="positive" if n else "info")
            botao("Zerar agora (reinício manual)", icone="delete_forever", on_click=_reiniciar_agora, variante="texto", chave_modulo="agregador_noticias").props('data-testid=agregador-reiniciar-agora')
