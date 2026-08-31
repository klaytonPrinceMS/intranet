"""Configurações DO MÓDULO INTRANET (módulo principal) — admin_geral.

Escopo exclusivo deste módulo:
· Cores: primária e de fundo do sistema
· Ícones: ícone principal do cabeçalho/login
· Textos fixos: login (título/subtítulo/ajuda), rodapé, saudação da home
· Páginas do sistema: nome exibido e ícone de cada página/módulo no menu e no título
"""
import sys, os, shutil
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from nicegui import ui

from mod_intranet.conexao_bd import get_config, set_config, PADRAO_CONFIG
from mod_intranet.manipulador_bd import audit_log
from mod_intranet import autenticacao, documentacao

CORES_PRESET = ["#1565C0", "#00838F", "#2E7D32", "#6A1B9A", "#C62828", "#EF6C00", "#37474F"]

BASE_DIR_MOD = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # raiz do projeto


def mostrar_tela(user_nome: str, perfil_global: str = ""):
    if perfil_global != "administrador_geral" and \
            autenticacao.perfil_global_de(user_nome) != "administrador_geral":
        ui.label("Área de configuração restrita ao administrador geral.") \
            .classes("text-h6 text-negative q-pa-xl")
        return

    def confirmar(rotulo, acao):
        """Diálogo de confirmação para restaurações (ação destrutiva local)."""
        with ui.dialog() as dlg, ui.card():
            ui.label(f"Restaurar padrão — {rotulo}?").classes("text-subtitle1 font-bold")
            ui.label("Os valores codificados originalmente serão reaplicados e as "
                     "alterações salvas neste item serão perdidas.").classes(
                "text-caption text-grey-7")
            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Cancelar", on_click=dlg.close).props("flat no-caps")
                ui.button("Restaurar", on_click=lambda: (dlg.close(), acao())) \
                    .props("unelevated no-caps color=warning icon=restore")
        dlg.open()

    def restaurar_padroes(chaves, rotulo):
        for k in chaves:
            if k in PADRAO_CONFIG:
                set_config(k, PADRAO_CONFIG[k])
        audit_log(user_nome, "intranet", "config_restaurada",
                  f"padrões restaurados: {rotulo}")
        ui.notify(f"Padrão restaurado ({rotulo}) — recarregue com F5",
                  type="positive")

    ui.colors(primary=get_config("cor_principal", "#1565C0"))
    ui.label("Configurações do módulo Intranet").classes(
        "text-h5 font-bold text-grey-9 q-mb-sm")

    # ---- barra única de salvamento: um clique grava TODOS os cartões ----
    estado_campos = {}

    def salvar_tudo():
        c = estado_campos
        # Cartão 1
        set_config("cor_principal", ((c.get("cor") or "").strip()) or PADRAO_CONFIG["cor_principal"])
        set_config("cor_fundo", ((c.get("fundo") or "").strip()) or PADRAO_CONFIG["cor_fundo"])
        set_config("icone_sistema", ((c.get("icone") or "").strip()) or PADRAO_CONFIG["icone_sistema"])
        set_config("titulo_sistema", ((c.get("titulo") or "").strip()) or PADRAO_CONFIG["titulo_sistema"])
        # Cartão 2
        for k in ("texto_login_titulo", "texto_login_subtitulo", "texto_login_hint",
                  "texto_home_saudacao", "texto_home_subtitulo", "texto_rodape"):
            set_config(k, c.get(k) or "")
        # Cartão SMTP (RF-58)
        for k in ("smtp_servidor", "smtp_porta", "smtp_usuario", "smtp_senha", "smtp_de"):
            set_config(k, c.get(k) or "")
        set_config("smtp_tls", "1" if c.get("smtp_tls") else "0")
        # Cartão Configurações gerais (RF-57)
        set_config("backup_interval_hours", (c.get("backup_interval_hours") or "12").strip() or "12")
        set_config("sessao_retencao", (c.get("sessao_retencao") or "50").strip() or "50")
        # Cartão 3
        n = 0
        for chave, (inp_n, inp_i, sw_a) in c.get("paginas", {}).items():
            conn = autenticacao.get_connection()
            try:
                conn.execute(
                    "UPDATE tb_modulos SET nome=?, icone=?, ativo=? WHERE chave=?",
                    ((inp_n.value or "").strip() or chave,
                     (inp_i.value or "").strip() or "extension",
                     1 if sw_a.value else 0, chave))
                conn.commit()
            finally:
                conn.close()
            n += 1
        # Cartão Observabilidade (logs)
        from mod_intranet import observabilidade
        set_config("log_ativo", "1" if c.get("log_ativo") else "0")
        set_config("log_nivel", (c.get("log_nivel") or "INFO").upper())
        set_config("log_rotacao", (c.get("log_rotacao") or "1 month").strip())
        set_config("log_retencao", (c.get("log_retencao") or "4 months").strip())
        observabilidade.configurar()
        audit_log(user_nome, "intranet", "config_alterada",
                  f"salvamento completo ({n} páginas) + observabilidade")
        ui.notify(f"Tudo salvo — cabeçalho agora: "
                  f"'{(c.get('titulo') or '').strip() or PADRAO_CONFIG['titulo_sistema']}'. "
                  "Recarregue com F5 para ver em todas as páginas.", type="positive")

    with ui.row().classes("w-full justify-end -mt-2 mb-2"):
        ui.button("SALVAR TUDO", on_click=salvar_tudo) \
            .props("unelevated no-caps icon=save size=md color=primary") \
            .tooltip("Grava de uma vez cores, ícone, nome do sistema, textos e páginas")

    # ==================== CARTÃO 1: CORES E ÍCONE ====================
    with ui.card().classes("w-full"):
        ui.label("Cores e ícone").classes("text-subtitle1 font-bold")
        # color_input = campo para digitar o código + PALETA visual clicável
        f_cor = ui.color_input(label="Cor primária (menus, botões, destaques)",
                               value=get_config("cor_principal", "#1565C0")) \
            .props("outlined dense default-view=palette").classes("w-72") \
            .on_value_change(lambda e: estado_campos.update(cor=e.value))
        f_fundo = ui.color_input(label="Cor de fundo das páginas",
                                 value=get_config("cor_fundo", "#EEEEEE")) \
            .props("outlined dense default-view=palette").classes("w-72") \
            .on_value_change(lambda e: estado_campos.update(fundo=e.value))

        with ui.grid(columns="1fr 1fr").classes("w-full gap-3 mt-2"):
            f_icone = ui.input("Ícone do sistema (nome Material)",
                               value=get_config("icone_sistema", "hub"),
                               placeholder="ex.: hub, apartment, domain") \
                .props("outlined dense") \
                .on_value_change(lambda e: estado_campos.update(icone=e.value))
            f_titulo = ui.input("Nome do sistema no cabeçalho",
                                value=get_config("titulo_sistema", "INTRANET")) \
                .props("outlined dense") \
                .on_value_change(lambda e: estado_campos.update(titulo=e.value))

        @ui.refreshable
        def previa():
            cor = (f_cor.value or "#1565C0").strip()
            fundo = (f_fundo.value or "#EEEEEE").strip()
            ico = (f_icone.value or "hub").strip() or "hub"
            nom = (f_titulo.value or "INTRANET").strip() or "INTRANET"
            with ui.element("div").classes("rounded-lg w-full max-w-xl overflow-hidden") \
                    .style(f"background:{fundo}"):
                with ui.row().classes("items-center gap-2 px-4 py-2 w-full") \
                        .style(f"background:{cor}"):
                    ui.icon(ico).classes("text-white")
                    ui.label(nom).classes("text-white font-bold")
                with ui.column().classes("px-4 py-3 gap-1"):
                    ui.label("Exemplo de página").classes("font-medium text-grey-9")
                    ui.button("Botão exemplo", icon="info") \
                        .props("unelevated dense no-caps color=primary")

        previa()
        for campo in (f_cor, f_fundo, f_icone, f_titulo):
            campo.on_value_change(lambda _: previa.refresh())

        def salvar_cores():
            salvar_tudo()

        ui.button("Salvar cores e ícone", on_click=salvar_cores) \
            .props("unelevated no-caps icon=palette color=primary")
        ui.button("Restaurar padrão", icon="restore",
                  on_click=lambda: confirmar(
                      "cores, ícone e nome do sistema",
                      lambda: restaurar_padroes(
                          ["cor_principal", "cor_fundo", "icone_sistema",
                           "titulo_sistema"], "cores/ícone"))) \
            .props("outline no-caps color=warning")

        # ---- favicon do navegador (upload de .ico) ----
        ui.separator()
        import nicegui as _nicegui_pkg
        fav_path = os.path.join(BASE_DIR_MOD, "assets", "favicon_atual.ico")
        fav_padrao = os.path.join(os.path.dirname(_nicegui_pkg.__file__),
                                  "static", "favicon.ico")

        def _linha_fav():
            with ui.row().classes("items-center gap-4 flex-wrap"):
                ui.label("Ícone da aba do navegador:").classes("text-body2 text-grey-8")
                if get_config("favicon_custom") == "1":
                    ui.badge("personalizado ativo", color="green-2") \
                        .props("outline dense text-color=green-9")
                    import base64 as _b64
                    with open(fav_path, "rb") as fh:
                        _dados = _b64.b64encode(fh.read()).decode()
                    ui.image(f"data:image/x-icon;base64,{_dados}") \
                        .classes("w-8 h-8").props("fit=contain")
                else:
                    ui.badge("padrão NiceGUI", color="grey-3") \
                        .props("outline dense text-color=grey-8")
        _linha_fav()

        async def receber_ico(e):
            nome = (e.file.name or "").lower()
            if not nome.endswith(".ico"):
                ui.notify("Envie um arquivo .ico", type="negative")
                return
            conteudo = await e.file.read()
            if not conteudo or len(conteudo) > 1 * 1024 * 1024:
                ui.notify("Arquivo vazio ou maior que 1 MB", type="negative")
                return
            with open(fav_path, "wb") as fh:
                fh.write(conteudo)
            set_config("favicon_custom", "1")
            audit_log(user_nome, "intranet", "config_alterada",
                      f"favicon enviado ({nome}, {len(conteudo)} bytes)")
            ui.notify("Favicon aplicado — recarregue a aba com Ctrl+F5",
                      type="positive")

        def remover_fav():
            shutil.copy2(fav_padrao, fav_path)
            set_config("favicon_custom", "0")
            audit_log(user_nome, "intranet", "config_restaurada",
                      "favicon voltou ao padrão NiceGUI")
            ui.notify("Ícone padrão restaurado — Ctrl+F5 na aba", type="positive")

        ui.upload(on_upload=receber_ico, auto_upload=True) \
            .props('accept=".ico,image/x-icon" label="Enviar .ico" '
                   'flat dense color=primary') \
            .classes("max-w-[240px]").tooltip("Substitui o ícone da aba do navegador")
        ui.button(icon="restart_alt", on_click=lambda: confirmar(
            "ícone do navegador", remover_fav)) \
            .props("flat round dense color=warning") \
            .tooltip("Voltar ao ícone padrão do NiceGUI")

    # ==================== CARTÃO 2: TEXTOS FIXOS ====================
    with ui.card().classes("w-full"):
        ui.label("Textos fixos exibidos aos usuários").classes("text-subtitle1 font-bold")
        with ui.grid(columns="1fr 1fr").classes("w-full gap-3"):
            t_login = ui.input("Título da tela de login",
                               value=get_config("texto_login_titulo", "INTRANET Básica")) \
                .props("outlined dense") \
                .on_value_change(lambda e: estado_campos.update(texto_login_titulo=e.value))
            t_sub = ui.input("Subtítulo da tela de login",
                             value=get_config("texto_login_subtitulo")) \
                .props("outlined dense") \
                .on_value_change(lambda e: estado_campos.update(texto_login_subtitulo=e.value))
        t_hint = ui.input("Ajuda abaixo do botão Entrar (login)",
                          value=get_config("texto_login_hint")) \
            .props("outlined dense").classes("w-full") \
            .on_value_change(lambda e: estado_campos.update(texto_login_hint=e.value))
        with ui.grid(columns="1fr 2fr").classes("w-full gap-3"):
            t_saud = ui.input("Saudação da página inicial",
                              value=get_config("texto_home_saudacao", "Olá")) \
                .props("outlined dense") \
                .on_value_change(lambda e: estado_campos.update(texto_home_saudacao=e.value))
            t_homesub = ui.input("Frase abaixo da saudação (página inicial)",
                                 value=get_config("texto_home_subtitulo")) \
                .props("outlined dense") \
                .on_value_change(lambda e: estado_campos.update(texto_home_subtitulo=e.value))
        t_rodape = ui.input("Texto do rodapé (a versão é anexada automaticamente)",
                            value=get_config("texto_rodape", "uso interno")) \
            .props("outlined dense").classes("w-full") \
            .on_value_change(lambda e: estado_campos.update(texto_rodape=e.value))

        def salvar_textos():
            salvar_tudo()

        ui.button("Salvar textos", on_click=salvar_textos) \
            .props("unelevated no-caps icon=text_fields color=primary")
        ui.button("Restaurar padrão", icon="restore",
                  on_click=lambda: confirmar(
                      "textos fixos",
                      lambda: restaurar_padroes(
                          ["texto_login_titulo", "texto_login_subtitulo",
                           "texto_login_hint", "texto_home_saudacao",
                           "texto_home_subtitulo", "texto_rodape"], "textos"))) \
            .props("outline no-caps color=warning")

    # ==================== CARTÃO 3: PÁGINAS (NOME E ÍCONE) ====================
    with ui.card().classes("w-full"):
        ui.label("Páginas do sistema — nome exibido e ícone").classes(
            "text-subtitle1 font-bold")
        ui.label("O nome é usado no menu lateral e no título exibido no cabeçalho "
                 "ao entrar na página. O ícone aparece no menu.").classes(
            "text-caption text-grey-7 -mt-2")

        modulos = autenticacao.modulos_registrados()
        campos = {}
        estado_campos["paginas"] = campos  # lido pelo SALVAR TUDO
        with ui.grid(columns="0.8fr 1fr 1fr auto").classes(
                "w-full bg-grey-1 rounded px-3 py-1.5 text-caption font-bold text-grey-8"):
            for c in ("Página", "Nome exibido", "Ícone", "Ativa"):
                ui.label(c)
        for chave, nome, icone, rota, ativo in modulos:
            inp_n = ui.input(value=nome).props("dense outlined").classes("w-full")
            inp_i = ui.input(value=icone).props("dense outlined").classes("w-full")
            sw = ui.switch(value=bool(ativo)).props("dense")
            campos[chave] = (inp_n, inp_i, sw)

        def salvar_paginas():
            salvar_tudo()

        def restaurar_paginas_padrao():
            """Páginas NATIVAS voltam ao nome/ícone codificados e reativadas;
            módulos criados pelo administrador permanecem intocados."""
            for chave, nome, icone, _rota in autenticacao.MODULOS_SISTEMA:
                conn = autenticacao.get_connection()
                try:
                    conn.execute(
                        "UPDATE tb_modulos SET nome=?, icone=?, ativo=1 WHERE chave=? AND nativo=1",
                        (nome, icone, chave))
                    conn.commit()
                finally:
                    conn.close()
            audit_log(user_nome, "intranet", "config_restaurada",
                      "páginas nativas restauradas")
            ui.notify("Páginas nativas restauradas ao padrão — recarregue com F5",
                      type="positive")

        ui.button("Salvar páginas", on_click=salvar_paginas) \
            .props("unelevated no-caps icon=view_list color=primary")
        ui.button("Restaurar padrão", icon="restore",
                  on_click=lambda: confirmar(
                      "nomes e ícones das páginas",
                      restaurar_paginas_padrao)) \
            .props("outline no-caps color=warning")

        for chave, nome, icone, rota, ativo in modulos:
            inp_n, inp_i, sw = campos[chave]
            with ui.grid(columns="0.8fr 1fr 1fr auto").classes(
                    "w-full border-b border-grey-2 px-3 py-1 items-center"):
                with ui.row().classes("items-center gap-2 flex-nowrap"):
                    ui.icon(icone).classes("text-primary")
                    ui.label(chave).classes("text-caption text-grey-6")
                inp_n
                inp_i
                sw

    # ==================== CARTÃO 4: REGISTRAR MÓDULOS E ÓRFÃOS ====================
    # (configuração DO SISTEMA intranet — movida da gestão de usuários)
    from mod_gest_cad_usuario import manipulador_bd as gest_usuarios

    with ui.card().classes("w-full"):
        ui.label("Registro de módulos e vínculos órfãos").classes(
            "text-subtitle1 font-bold")
        ui.label("Todo módulo registrado aqui passa a aparecer automaticamente nas telas "
                 "de criação/edição de usuários e nos menus — inclusive módulos futuros. "
                 "Vínculos apontando para módulos inexistentes ficam destacados abaixo "
                 "para manutenção ou exclusão.").classes(
            "text-caption text-grey-7 max-w-3xl -mt-2")

        box_orfaos = ui.column().classes("w-full gap-4 -mt-2")

        def refresh_orfaos():
            box_orfaos.clear()
            registrados = autenticacao.modulos_registrados()
            orfaos = gest_usuarios.listar_vinculos_orfaos(autenticacao.chaves_ativas())
            with box_orfaos:
                # --- registrar novo módulo ---
                with ui.expansion("Registrar novo módulo (futuro)",
                                  icon="add_circle_outline").classes("w-full"):
                    n_ativo = {"valor": False}
                    with ui.row().classes("w-full flex-wrap items-end gap-2"):
                        n_chave = ui.input("Chave única *",
                                           placeholder="ex.: folha_ponto").props("outlined dense")
                        n_nome = ui.input("Nome exibido *",
                                          placeholder="ex.: Folha de Ponto").props("outlined dense")
                        n_icone = ui.input("Ícone Material", value="extension") \
                            .props("outlined dense").classes("max-w-[140px]")
                        n_rota = ui.input("Rota",
                                          placeholder="# ou /rota-futura") \
                            .props("outlined dense").classes("max-w-[180px]")
                        ui.switch("Já em funcionamento",
                                  on_change=lambda e: n_ativo.update(valor=bool(e.value))) \
                            .tooltip("Marque só se a rota/página já existe no main.py")

                        def registrar():
                            ok, msg = autenticacao.registrar_modulo(
                                user_nome, n_chave.value, n_nome.value,
                                n_icone.value or "extension", n_rota.value or "#",
                                ativo=n_ativo["valor"])
                            ui.notify(msg, type="positive" if ok else "negative")
                            if ok:
                                n_chave.value = n_nome.value = ""
                                n_rota.value = "#"

                        ui.button("Registrar", on_click=registrar) \
                            .props("unelevated color=primary no-caps icon=add_circle")

                ui.separator()
                # --- vínculos órfãos ---
                ui.label(f"Vínculos sem módulo correspondente ({len(orfaos)})").classes(
                    "text-subtitle1 font-bold")
                if not orfaos:
                    ui.label("Nenhum vínculo órfão — base consistente.").classes("text-green-8")
                else:
                    with ui.grid(columns="1fr 1fr 0.8fr auto").classes(
                            "w-full bg-orange-1 rounded-lg px-3 py-2 text-caption "
                            "font-bold text-orange-10 border border-orange-6"):
                        for c in ("Usuário", "Módulo inexistente", "Papel", ""):
                            ui.label(c)
                    for u, m, p in orfaos:
                        with ui.grid(columns="1fr 1fr 0.8fr auto").classes(
                                "w-full border-b border-orange-3 bg-orange-1/60 px-3 py-1.5 items-center"):
                            ui.label(u)
                            ui.badge(m, color="orange-2").props("text-color=orange-10 outline dense")
                            ui.label(p).classes("text-caption")
                            ui.button(icon="link_off",
                                      on_click=lambda _, uu=u, mm=m: (
                                          gest_usuarios.remover_acesso(user_nome, uu, mm),
                                          refresh_orfaos())) \
                                .props("flat round dense color=red-8 size=sm") \
                                 .tooltip("Excluir permissão órfã")

        refresh_orfaos()

    # ==================== CARTÃO 5: DOCUMENTAÇÃO (MKDOCS) ====================
    with ui.card().classes("w-full"):
        ui.label("Documentação técnica").classes("text-subtitle1 font-bold")
        ui.label("Reconstrói a documentação MkDocs do projeto e a publica em "
                 "/documentacao (mesmo endereço/porta do sistema, nova aba). "
                 "Edições em docs/*.md valem após reconstruir.") \
            .classes("text-caption text-grey-7")

        def reconstruir_docs():
            ok, msg = documentacao.reconstruir()
            if ok:
                audit_log(user_nome, "intranet", "documentacao_reconstruida",
                          msg[:200])
            ui.notify(msg, type="positive" if ok else "negative",
                      multi_line=True, close_button="Fechar")

        with ui.row().classes("gap-2 mt-1 items-center"):
            ui.button("Reconstruir documentação", on_click=reconstruir_docs) \
                .props("unelevated no-caps icon=menu_book color=primary")
            ui.button(icon="open_in_new", on_click=lambda: ui.navigate.to(
                          "/documentacao", new_tab=True)) \
                .props("flat no-caps color=primary") \
                .tooltip("Abrir a documentação em nova aba")

    # ==================== CARTÃO 6: OBSERVABILIDADE / LOGS ====================
    with ui.card().classes("w-full"):
        ui.label("Observabilidade e logs (loguru)").classes("text-subtitle1 font-bold")
        ui.label("Logs de erro/debug/info em arquivo, com rotação (tempo ou tamanho) e "
                 "retenção configurável. Arquivos rotacionados são compactados em .zip e "
                 "mantidos até o prazo de retenção. Exceções não tratadas são capturadas "
                 "automaticamente.").classes("text-caption text-grey-7 max-w-3xl -mt-2")

        sw_ativo = ui.switch("Logs ativos",
                             value=get_config("log_ativo", "1") == "1").props("dense")
        sel_nivel = ui.select({"DEBUG": "DEBUG", "INFO": "INFO",
                               "WARNING": "WARNING", "ERROR": "ERROR"},
                              label="Nível mínimo",
                              value=get_config("log_nivel", "INFO")).props("outlined dense")
        inp_rot = ui.input("Rotação (tempo ou tamanho)",
                          value=get_config("log_rotacao", "1 month")) \
            .props("outlined dense").classes("w-full") \
            .tooltip("Ex.: '1 month' (tempo) ou '50 MB' (tamanho). Padrão '1 month'.")
        inp_ret = ui.input("Retenção dos arquivos compactados (.zip)",
                          value=get_config("log_retencao", "4 months")) \
            .props("outlined dense").classes("w-full") \
            .tooltip("Ex.: '4 months' (padrão). Arquivos .zip mantidos até o prazo.")

        # Garante que os valores já entrem no estado mesmo sem o usuário mexer
        estado_campos["log_ativo"] = sw_ativo.value
        estado_campos["log_nivel"] = sel_nivel.value
        estado_campos["log_rotacao"] = inp_rot.value
        estado_campos["log_retencao"] = inp_ret.value
        sw_ativo.on_value_change(lambda e: estado_campos.update(log_ativo=e.value))
        sel_nivel.on_value_change(lambda e: estado_campos.update(log_nivel=e.value))
        inp_rot.on_value_change(lambda e: estado_campos.update(log_rotacao=e.value))
        inp_ret.on_value_change(lambda e: estado_campos.update(log_retencao=e.value))

        def salvar_logs():
            salvar_tudo()

        def limpar_logs():
            from mod_intranet import observabilidade as _obs
            ok, msg = _obs.limpar_todos()
            ui.notify(msg, type="positive" if ok else "negative")
            audit_log(user_nome, "intranet", "logs_limpos", msg)
            _obs.get_logger().warning(f"logs limpos manualmente por {user_nome}: {msg}")

        with ui.row().classes("w-full gap-2 items-center"):
            ui.button("Salvar logs", on_click=salvar_logs) \
                .props("unelevated no-caps icon=save color=primary")
            ui.button("Limpar TODOS os logs", icon="delete_forever",
                      on_click=lambda: confirmar("LIMPEZA TOTAL dos logs", limpar_logs)) \
                .props("outline no-caps color=red")

    # ==================== CARTÃO 7: E-MAIL / SMTP (RF-58) ====================
    from mod_intranet import email_util

    with ui.card().classes("w-full"):
        ui.label("E-mail / SMTP (envio de documentos)").classes(
            "text-subtitle1 font-bold")
        ui.label("Credenciais do servidor de saída usadas para enviar empenhos "
                 "renomeados por e-mail. Salve com 'SALVAR TUDO' acima; use o "
                 "botão abaixo para testar a conexão sem sair da tela.").classes(
            "text-caption text-grey-7 max-w-3xl -mt-2")

        with ui.grid(columns="1fr 1fr").classes("w-full gap-3"):
            sm_serv = ui.input("Servidor SMTP",
                               value=get_config("smtp_servidor", "")) \
                .props("outlined dense").classes("w-full") \
                .on_value_change(lambda e: estado_campos.update(smtp_servidor=e.value))
            sm_port = ui.input("Porta",
                               value=get_config("smtp_porta", "587")) \
                .props("outlined dense").classes("max-w-[120px]") \
                .on_value_change(lambda e: estado_campos.update(smtp_porta=e.value))
        with ui.grid(columns="1fr 1fr").classes("w-full gap-3"):
            sm_user = ui.input("Usuário / login",
                               value=get_config("smtp_usuario", "")) \
                .props("outlined dense").classes("w-full") \
                .on_value_change(lambda e: estado_campos.update(smtp_usuario=e.value))
            sm_de = ui.input("Remetente (De)",
                             value=get_config("smtp_de", "")) \
                .props("outlined dense").classes("w-full") \
                .on_value_change(lambda e: estado_campos.update(smtp_de=e.value))
        sm_senha = ui.input("Senha", password=True, password_toggle_button=True,
                            value=get_config("smtp_senha", "")) \
            .props("outlined dense").classes("w-full") \
            .on_value_change(lambda e: estado_campos.update(smtp_senha=e.value))
        sm_tls = ui.switch("Usar TLS (STARTTLS)", value=get_config("smtp_tls", "1") == "1") \
            .props("dense") \
            .on_value_change(lambda e: estado_campos.update(smtp_tls=e.value))

        def testar_smtp():
            set_config("smtp_servidor", sm_serv.value or "")
            set_config("smtp_porta", sm_port.value or "587")
            set_config("smtp_usuario", sm_user.value or "")
            set_config("smtp_senha", sm_senha.value or "")
            set_config("smtp_de", sm_de.value or "")
            set_config("smtp_tls", "1" if sm_tls.value else "0")
            ok, msg = email_util.testar_conexao()
            ui.notify(msg, type="positive" if ok else "negative",
                      multi_line=True, close_button="Fechar")

        ui.button("Testar conexão SMTP", on_click=testar_smtp) \
            .props("unelevated no-caps icon=mail color=primary")

    # ==================== CARTÃO 8: CONFIGURAÇÕES GERAIS (RF-57) ====================
    from mod_intranet import rotinas as _rotinas

    with ui.card().classes("w-full"):
        ui.label("Configurações gerais do sistema").classes("text-subtitle1 font-bold")
        ui.label("Intervalo de backup, retenção de sessão e pasta raiz dos arquivos. "
                 "Salve com 'SALVAR TUDO' acima.").classes(
            "text-caption text-grey-7 max-w-3xl -mt-2")

        inp_backup = ui.input("Intervalo de backup (horas)",
                              value=get_config("backup_interval_hours", "12")) \
            .props("outlined dense").classes("max-w-[160px]") \
            .on_value_change(lambda e: estado_campos.update(backup_interval_hours=e.value))
        inp_sessao = ui.input("Retenção de sessão (dias)",
                              value=get_config("sessao_retencao", "50")) \
            .props("outlined dense").classes("max-w-[160px]") \
            .on_value_change(lambda e: estado_campos.update(sessao_retencao=e.value))
        inp_raiz = ui.input("Pasta raiz dos arquivos (BASE_DIR)",
                            value=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) \
            .props("outlined dense readonly").classes("w-full") \
            .tooltip("Diretório raiz do sistema (somente leitura)")

        def aplicar_gerais():
            try:
                horas = max(1, int((inp_backup.value or "12").strip() or 12))
                set_config("backup_interval_hours", str(horas))
                set_config("sessao_retencao", str(max(1, int((inp_sessao.value or "50").strip() or 50))))
                for chave in _rotinas.MAPA_BACKUPS:
                    try:
                        _rotinas.reagendar_backup(chave, horas)
                    except Exception:
                        pass
                ui.notify(f"Backup global = {horas}h aplicado a todos os módulos; "
                          f"retenção de sessão = {get_config('sessao_retencao')}d",
                          type="positive")
            except Exception as ex:
                ui.notify(f"Erro ao aplicar configurações gerais: {ex}", type="negative")

        ui.button("Aplicar configurações gerais", on_click=aplicar_gerais) \
            .props("unelevated no-caps icon=settings_applications color=primary")
