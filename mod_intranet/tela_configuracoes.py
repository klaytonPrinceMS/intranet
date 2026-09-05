"""Intranet module settings screen (main module) — admin_geral only.

Tela de configurações do módulo Intranet, organizada no padrão menu_mod
(abas, como na Gestão de Usuários):

| Aba             | Conteúdo                                              |
|-----------------|-------------------------------------------------------|
| Config          | Texto e cor: cores/ícone, textos fixos, gerais (RF-57)|
| E-mail          | SMTP (RF-58)                                          |
| Módulo          | Páginas (nome/ícone/ativa) + registro de módulos      |
| Observabilidade | Logs loguru (ativo/nível/rotação/retenção)            |
| Documentação    | Rebuild MkDocs /documentacao                          |

Um ÚNICO botão "SALVAR TUDO" na barra do menu_mod grava todas as abas de
uma vez (RF-57/RF-58/páginas/logs); cada card possui seu botão
"Restaurar padrão" para voltar aos valores padrão/iniciais do sistema.
"""
import sys, os, shutil
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from nicegui import ui

from mod_intranet.conexao_bd import get_config, set_config, PADRAO_CONFIG
from mod_intranet.manipulador_bd import audit_log
from mod_intranet import autenticacao, documentacao

CORES_PRESET = ["#1565C0", "#00838F", "#2E7D32", "#6A1B9A", "#C62828", "#EF6C00", "#37474F"]

# Módulos indispensáveis ao funcionamento do sistema: permitem renomear/ícone,
# mas NUNCA podem ser desativados (relevant para a navegação/segurança).
MODULOS_INDISPENSAVEIS = {"auditoria", "usuarios"}

# Ícones Material comuns oferecidos no seletor visual de ícones de módulos.
ICONES_COMUNS = [
    "article", "people", "manage_accounts", "history", "folder_open", "print",
    "picture_as_pdf", "extension", "home", "settings", "menu_book", "dashboard",
    "description", "list", "tune", "mail", "query_stats", "hub", "apartment",
    "domain", "blog", "edit", "lock", "save", "restore", "add_circle",
    "link_off", "delete_forever", "open_in_new", "info", "settings_applications",
]

# Colunas do grid de módulos — compartilhadas entre cabeçalho e linhas.
# Em desktop (lg:) 6 colunas explícitas; em sm/md, 2 colunas empilhadas
# (cada _campo_empilhado já coloca label acima do input).
COLUNAS_MODULOS = (
    "grid-cols-1 sm:grid-cols-2 lg:grid-cols-[56px_minmax(12ch,1fr)"
    "_minmax(22ch,1fr)_minmax(22ch,1fr)_minmax(20ch,1fr)_150px]"
)

BASE_DIR_MOD = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # raiz do projeto


# ------------------------------------------------------------------
# Helpers de campo empilhado — usados em TODAS as abas (Config, E-mail,
# Observabilidade, Módulo) para manter consistência visual.
# ------------------------------------------------------------------
def _campo_empilhado(label, valor, readonly=False, tooltip=None):
    """Label stacked above an input that fills its grid column.

    Rótulo acima do input (empilhado); o input ocupa a largura da
    coluna do grid até o máximo de ~30ch (encolhe em telas menores).
    label em `text-caption text-grey-7`. Retorna o `ui.input` criado."""
    with ui.column().classes("min-w-0").style("gap: 0.25rem"):
        ui.label(label).classes("text-caption text-grey-7")
        inp = ui.input(value=valor) \
            .props("dense outlined" + (" readonly" if readonly else "")) \
            .classes("w-full max-w-[30ch]")
        if tooltip:
            inp.tooltip(tooltip)
        return inp


def _botao_padrao(rotulo=None, *, tipo="primario", icone=None, tooltip=None,
                  on_click=None, color=None):
    """Standardized button with a fixed variant (single source of truth).

    Botão padronizado do módulo: cada variante define props/classes/text-color
    fixos (cor de botão + cor de texto + tamanho idênticos por tipo). O
    parâmetro `color` (opcional) sobrescreve a cor da variante mantendo o
    tamanho/formato — usado para dar semântica (ex.: perigo/aviso) a botões
    de ícone sem quebrar a padronização. Retorna o `ui.button` criado.

    Variantes:
      primario       fill primary (unelevated, texto branco, shadow-sm)
      secundario     outline primary
      restaurar      outline warning (texto amber-9)
      restaurar_fill fill warning (texto branco) — confirmação de diálogo
      perigo         outline negative
      icone          flat round dense size=sm (compacto)
      neutro         flat no-caps (texto grey-8)
    """
    VARIANTES = {
        "primario":       ("unelevated no-caps size=md color=primary text-color=white", "shadow-sm"),
        "secundario":     ("outline no-caps size=md color=primary text-color=primary", ""),
        "restaurar":      ("outline no-caps size=md color=warning text-color=amber-9", ""),
        "restaurar_fill": ("unelevated no-caps size=md color=warning text-color=white", "shadow-sm"),
        "perigo":         ("outline no-caps size=md color=negative text-color=negative", ""),
        "icone":          ("flat round dense size=sm color=primary text-color=primary", ""),
        "neutro":         ("flat no-caps size=md text-color=grey-8", ""),
    }
    props, classes = VARIANTES[tipo]
    if color:
        props = " ".join(
            f"color={color}" if p.startswith("color=") else
            f"text-color={color}" if p.startswith("text-color=") else p
            for p in props.split())
    btn = ui.button(rotulo, icon=icone, on_click=on_click).props(props)
    if classes:
        btn.classes(classes)
    if tooltip:
        btn.tooltip(tooltip)
    return btn


def _campo_icone(valor_inicial):
    """Material icon free-text input (fills column) with a picker above.

    Campo livre de ícone Material Icons que preenche a coluna do
    grid (máx. ~30ch) com pré-visualização viva. O seletor visual
    (botão `grid_view` + menu com `ICONES_COMUNS`) fica empilhado
    ACIMA do input. Retorna o `ui.input` cujo `.value` é o nome
    do ícone."""
    with ui.column().classes("min-w-0").style("gap: 0.25rem"):
        with ui.row().classes("items-center").style("gap: 0.25rem"):
            with ui.menu() as menu:
                with ui.grid(columns="repeat(6, 1fr)").classes("p-1").style("gap: 0.25rem"):
                    for nome_icone in ICONES_COMUNS:
                        _botao_padrao(icone=nome_icone, tipo="icone",
                                      tooltip=nome_icone,
                                      on_click=lambda _, n=nome_icone: (
                                          inp.set_value(n), menu.close()))
            _botao_padrao(icone="grid_view", tipo="icone",
                          tooltip="Escolher ícone de uma lista",
                          on_click=menu.open)
            prev = ui.icon(valor_inicial or "extension").classes(
                "text-primary text-2xl shrink-0")
        inp = ui.input(value=valor_inicial) \
            .props("dense outlined").classes("w-full max-w-[30ch]") \
            .tooltip("Nome do ícone Material Icons — aparece no menu")
        inp.on_value_change(
            lambda e: prev.set_text((e.value or "extension").strip() or "extension"))
    return inp


def mostrar_tela(user_nome: str, perfil_global: str = ""):
    """Renders the /configuracoes screen (5 tabs + SALVAR TUDO) for the general admin.

    Renderiza a tela de configurações do módulo Intranet, restrita ao
    administrador geral. Monta a barra de abas (Config, E-mail, Módulo,
    Observabilidade e Documentação) com o botão SALVAR TUDO
    (grava todas as abas via `salvar_tudo`) e, em cada card, um botão
    "Restaurar padrão" para voltar aos valores padrão do sistema."""
    if perfil_global != "administrador_geral" and \
            autenticacao.perfil_global_de(user_nome) != "administrador_geral":
        ui.label("Área de configuração restrita ao administrador geral.") \
            .classes("text-h6 text-negative q-pa-xl")
        return

    def confirmar(rotulo, acao):
        """Confirmation dialog for destructive local restores.

        Diálogo de confirmação para restaurações (ação destrutiva local)."""
        with ui.dialog() as dlg, ui.card():
            ui.label(f"Restaurar padrão — {rotulo}?").classes("text-subtitle1 font-bold")
            ui.label("Os valores codificados originalmente serão reaplicados e as "
                     "alterações salvas neste item serão perdidas.").classes(
                "text-caption text-grey-7")
            with ui.row().classes("w-full justify-end items-center").style("gap: 0.5rem"):
                _botao_padrao("Cancelar", tipo="neutro", on_click=dlg.close)
                _botao_padrao("Restaurar", tipo="restaurar_fill", icone="restore",
                              on_click=lambda: (dlg.close(), acao()))
        dlg.open()

    def restaurar_grupo(defaults, rotulo, campos=None, pos_acao=None):
        """Restores a config group to its coded defaults and audits.

        Restaura as chaves de um grupo de `tb_config` para os padrões
        codificados (PADRAO_CONFIG ou valores fixos do sistema), registra
        auditoria e notifica. `campos` (opcional) é uma lista de
        (input, chave_estado, valor) cujos `.value` e `estado_campos`
        são atualizados; `pos_acao` (opcional) roda após a gravação
        (ex.: reagendar backups, reconfigurar observabilidade)."""
        for k, v in defaults.items():
            set_config(k, v)
        if campos:
            for inp, chave_estado, valor in campos:
                inp.set_value(valor)
                estado_campos[chave_estado] = valor
        audit_log(user_nome, "intranet", "config_restaurada",
                  f"padrões restaurados: {rotulo}")
        if pos_acao:
            pos_acao()
        ui.notify(f"Padrão restaurado ({rotulo})", type="positive")

    def _reagendar_backups(horas):
        """Reapplies the backup interval to every live module job.

        Reagenda o job vivo de backup de cada módulo com o novo
        intervalo (falhas individuais são ignoradas)."""
        from mod_intranet import rotinas as _rot
        for chave in _rot.MAPA_BACKUPS:
            try:
                _rot.reagendar_backup(chave, horas)
            except Exception:
                pass

    ui.colors(primary=get_config("cor_principal", "#1565C0"))

    # ---- barra única de salvamento: um clique grava TODAS as abas ----
    estado_campos = {}

    def salvar_tudo():
        """Saves every tab at once (config, texts, SMTP, modules, logs).

        Grava todas as abas de uma vez: cores/ícone/textos/gerais (aba
        Config), `smtp_*` (E-mail), nome/ícone/ativo/rota em `tb_modulos`
        (aba Módulo — forçando `ativo=1` para `MODULOS_INDISPENSAVEIS`;
        URLs alteradas são re-registradas ao vivo via
        `autenticacao.alterar_rota_modulo`) e `log_*` com reconfiguração
        da observabilidade."""
        c = estado_campos
        # Aba Config — cores/ícone
        set_config("cor_principal", ((c.get("cor") or "").strip()) or PADRAO_CONFIG["cor_principal"])
        set_config("cor_fundo", ((c.get("fundo") or "").strip()) or PADRAO_CONFIG["cor_fundo"])
        set_config("icone_sistema", ((c.get("icone") or "").strip()) or PADRAO_CONFIG["icone_sistema"])
        set_config("titulo_sistema", ((c.get("titulo") or "").strip()) or PADRAO_CONFIG["titulo_sistema"])
        # Aba Config — textos fixos
        for k in ("texto_login_titulo", "texto_login_subtitulo", "texto_login_hint",
                  "texto_home_saudacao", "texto_home_subtitulo", "texto_rodape"):
            set_config(k, c.get(k) or "")
        # Aba Config — gerais (RF-57): valida e reagenda os backups
        horas = max(1, int((c.get("backup_interval_hours") or "12").strip() or 12))
        set_config("backup_interval_hours", str(horas))
        set_config("sessao_retencao", str(
            max(1, int((c.get("sessao_retencao") or "50").strip() or 50))))
        _reagendar_backups(horas)
        # Aba E-mail (RF-58)
        for k in ("smtp_servidor", "smtp_porta", "smtp_usuario", "smtp_senha", "smtp_de"):
            set_config(k, c.get(k) or "")
        set_config("smtp_tls", "1" if c.get("smtp_tls") else "0")
        # Aba Módulo — páginas
        n = 0
        for chave, (inp_n, inp_i, sw_a) in c.get("paginas", {}).items():
            conn = autenticacao.get_connection()
            try:
                ativo = 1 if chave in MODULOS_INDISPENSAVEIS else (1 if sw_a.value else 0)
                conn.execute(
                    "UPDATE tb_modulos SET nome=?, icone=?, ativo=? WHERE chave=?",
                    ((inp_n.value or "").strip() or chave,
                     (inp_i.value or "").strip() or "extension",
                     ativo, chave))
                conn.commit()
            finally:
                conn.close()
            n += 1
        # Aba Módulo — URLs alteradas
        avisos = []
        urls_alteradas = 0
        for chave, inp_url in c.get("urls", {}).items():
            nova_rota = (inp_url.value or "").strip()
            if not nova_rota:
                continue
            conn = autenticacao.get_connection()
            try:
                row = conn.execute(
                    "SELECT rota FROM tb_modulos WHERE chave=?", (chave,)).fetchone()
                rota_vigente = row[0] if row else None
            finally:
                conn.close()
            if rota_vigente and nova_rota != rota_vigente:
                ok, msg = autenticacao.alterar_rota_modulo(user_nome, chave, nova_rota)
                if ok:
                    urls_alteradas += 1
                else:
                    avisos.append(msg)
        # Aba Observabilidade (logs)
        from mod_intranet import observabilidade
        set_config("log_ativo", "1" if c.get("log_ativo") else "0")
        set_config("log_nivel", (c.get("log_nivel") or "INFO").upper())
        set_config("log_rotacao", (c.get("log_rotacao") or "1 month").strip())
        set_config("log_retencao", (c.get("log_retencao") or "4 months").strip())
        observabilidade.configurar()
        audit_log(user_nome, "intranet", "config_alterada",
                  f"salvamento completo ({n} páginas) + observabilidade")
        msg_final = (f"Tudo salvo — cabeçalho agora: "
                     f"'{(c.get('titulo') or '').strip() or PADRAO_CONFIG['titulo_sistema']}'.")
        if urls_alteradas:
            msg_final += f" {urls_alteradas} URL(s) alterada(s) — recarregue com F5."
        if avisos:
            msg_final += " Avisos: " + " | ".join(avisos)
        ui.notify(msg_final, type="positive" if not avisos else "warning",
                  multi_line=bool(avisos), close_button="Fechar" if avisos else False)

    with ui.column().classes("w-full p-6").style("gap: 1rem"):
        with ui.row().classes("w-full items-center justify-between flex-nowrap "
                              "bg-white rounded-lg shadow-sm px-3 py-1").style("gap: 1rem"):
            with ui.tabs().props("dense inline-label").classes("min-w-0 overflow-x-auto") as tabs:
                tab_geral = ui.tab("Config", icon="tune")
                tab_email = ui.tab("E-mail", icon="mail")
                tab_mod = ui.tab("Módulo", icon="extension")
                tab_obs = ui.tab("Observabilidade", icon="query_stats")
                tab_docs = ui.tab("Documentação", icon="menu_book")
            with ui.row().classes("items-center shrink-0").style("gap: 0.5rem"):
                _botao_padrao("SALVAR TUDO", tipo="primario", icone="save",
                              tooltip="Grava de uma vez todas as abas",
                              on_click=salvar_tudo)

        with ui.tab_panels(tabs, value=tab_geral).classes("w-full bg-transparent"):

            # ============================================================
            # ABA: CONFIG — texto e cor
            # ============================================================
            with ui.tab_panel(tab_geral):
                # ---- Cores e ícone ----
                with ui.card().classes("w-full"):
                    ui.label("Cores e ícone").classes("text-subtitle1 font-bold")
                    ui.label("Defina a cor principal do sistema, cor de fundo, "
                             "ícone do cabeçalho e nome exibido no topo de cada página.").classes(
                        "text-caption text-grey-7 max-w-3xl -mt-2")

                    with ui.grid(columns="grid-cols-1 sm:grid-cols-2 lg:grid-cols-4") \
                            .classes("w-full").style("gap: 1.25rem"):
                        with ui.column().classes("min-w-0").style("gap: 0.25rem"):
                            ui.label("Cor primária (menus, botões, destaques)") \
                                .classes("text-caption text-grey-7")
                            f_cor = ui.color_input(
                                value=get_config("cor_principal", "#1565C0")) \
                                .props("outlined dense default-view=palette") \
                                .classes("w-full max-w-[288px]") \
                                .on_value_change(lambda e: estado_campos.update(cor=e.value))
                        with ui.column().classes("min-w-0").style("gap: 0.25rem"):
                            ui.label("Cor de fundo das páginas") \
                                .classes("text-caption text-grey-7")
                            f_fundo = ui.color_input(
                                value=get_config("cor_fundo", "#EEEEEE")) \
                                .props("outlined dense default-view=palette") \
                                .classes("w-full max-w-[288px]") \
                                .on_value_change(lambda e: estado_campos.update(fundo=e.value))
                        f_icone = _campo_empilhado(
                            "Ícone do sistema (nome Material)",
                            get_config("icone_sistema", "hub"),
                            tooltip="ex.: hub, apartment, domain") \
                            .on_value_change(lambda e: estado_campos.update(icone=e.value))
                        f_titulo = _campo_empilhado(
                            "Nome do sistema no cabeçalho",
                            get_config("titulo_sistema", "INTRANET"),
                            tooltip="Texto que aparece no topo de cada página") \
                            .on_value_change(lambda e: estado_campos.update(titulo=e.value))

                    # Pré-visualização
                    @ui.refreshable
                    def previa():
                        cor = (f_cor.value or "#1565C0").strip()
                        fundo = (f_fundo.value or "#EEEEEE").strip()
                        ico = (f_icone.value or "hub").strip() or "hub"
                        nom = (f_titulo.value or "INTRANET").strip() or "INTRANET"
                        with ui.element("div").classes("rounded-lg w-full max-w-xl overflow-hidden") \
                                .style(f"background:{fundo}"):
                            with ui.row().classes("items-center px-4 py-2 w-full") \
                                    .style(f"background:{cor}; gap: 0.5rem"):
                                ui.icon(ico).classes("text-white")
                                ui.label(nom).classes("text-white font-bold")
                            with ui.column().classes("px-4 py-3").style("gap: 0.25rem"):
                                ui.label("Exemplo de página").classes("font-medium text-grey-9")
                                _botao_padrao("Botão exemplo", tipo="primario",
                                              icone="info")

                    previa()
                    for campo in (f_cor, f_fundo, f_icone, f_titulo):
                        campo.on_value_change(lambda _: previa.refresh())

                    # Garante que os valores atuais já entrem no estado sem o usuário mexer
                    estado_campos["cor"] = f_cor.value
                    estado_campos["fundo"] = f_fundo.value
                    estado_campos["icone"] = f_icone.value
                    estado_campos["titulo"] = f_titulo.value

                    with ui.row().classes("w-full items-center flex-wrap") \
                            .style("gap: 0.5rem"):
                        _botao_padrao(
                            "Restaurar padrão", tipo="restaurar", icone="restore",
                            on_click=lambda: confirmar(
                                "cores, ícone e nome do sistema",
                                lambda: restaurar_grupo(
                                    {"cor_principal": PADRAO_CONFIG["cor_principal"],
                                     "cor_fundo": PADRAO_CONFIG["cor_fundo"],
                                     "icone_sistema": PADRAO_CONFIG["icone_sistema"],
                                     "titulo_sistema": PADRAO_CONFIG["titulo_sistema"]},
                                    "cores/ícone",
                                    campos=[(f_cor, "cor", PADRAO_CONFIG["cor_principal"]),
                                            (f_fundo, "fundo", PADRAO_CONFIG["cor_fundo"]),
                                            (f_icone, "icone", PADRAO_CONFIG["icone_sistema"]),
                                            (f_titulo, "titulo", PADRAO_CONFIG["titulo_sistema"])])))

                    # ---- favicon do navegador (upload de .ico) ----
                    ui.separator()
                    import nicegui as _nicegui_pkg
                    fav_path = os.path.join(BASE_DIR_MOD, "assets", "favicon_atual.ico")
                    fav_padrao = os.path.join(os.path.dirname(_nicegui_pkg.__file__),
                                              "static", "favicon.ico")

                    def _linha_fav():
                        with ui.row().classes("items-center flex-wrap").style("gap: 1rem"):
                            ui.label("Ícone da aba do navegador:").classes(
                                "text-body2 text-grey-8")
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

                    with ui.row().classes("items-center flex-wrap").style("gap: 0.5rem"):
                        ui.upload(on_upload=receber_ico, auto_upload=True) \
                            .props('accept=".ico,image/x-icon" label="Enviar .ico" '
                                   'flat dense color=primary') \
                            .classes("max-w-[240px]") \
                            .tooltip("Substitui o ícone da aba do navegador")
                        _botao_padrao(icone="restart_alt", tipo="icone", color="warning",
                          tooltip="Voltar ao ícone padrão do NiceGUI",
                          on_click=lambda: confirmar(
                              "ícone do navegador", remover_fav))

                # ---- Textos fixos ----
                with ui.card().classes("w-full"):
                    ui.label("Textos fixos exibidos aos usuários").classes(
                        "text-subtitle1 font-bold")
                    ui.label("Personalize as mensagens da tela de login, da página inicial "
                             "e do rodapé.").classes(
                        "text-caption text-grey-7 max-w-3xl -mt-2")

                    with ui.grid(columns="grid-cols-1 sm:grid-cols-2") \
                            .classes("w-full").style("gap: 1.25rem"):
                        t_login = _campo_empilhado(
                            "Título da tela de login",
                            get_config("texto_login_titulo", "INTRANET Básica")) \
                            .on_value_change(lambda e: estado_campos.update(
                                texto_login_titulo=e.value))
                        t_sub = _campo_empilhado(
                            "Subtítulo da tela de login",
                            get_config("texto_login_subtitulo")) \
                            .on_value_change(lambda e: estado_campos.update(
                                texto_login_subtitulo=e.value))
                        t_hint = _campo_empilhado(
                            "Ajuda abaixo do botão Entrar (login)",
                            get_config("texto_login_hint")) \
                            .on_value_change(lambda e: estado_campos.update(
                                texto_login_hint=e.value))
                        t_saud = _campo_empilhado(
                            "Saudação da página inicial",
                            get_config("texto_home_saudacao", "Olá")) \
                            .on_value_change(lambda e: estado_campos.update(
                                texto_home_saudacao=e.value))
                        t_homesub = _campo_empilhado(
                            "Frase abaixo da saudação (página inicial)",
                            get_config("texto_home_subtitulo")) \
                            .on_value_change(lambda e: estado_campos.update(
                                texto_home_subtitulo=e.value))
                        t_rodape = _campo_empilhado(
                            "Texto do rodapé (versão é anexada automaticamente)",
                            get_config("texto_rodape", "uso interno")) \
                            .on_value_change(lambda e: estado_campos.update(
                                texto_rodape=e.value))

                    # Garante que os valores atuais já entrem no estado sem o usuário mexer
                    estado_campos["texto_login_titulo"] = t_login.value
                    estado_campos["texto_login_subtitulo"] = t_sub.value
                    estado_campos["texto_login_hint"] = t_hint.value
                    estado_campos["texto_home_saudacao"] = t_saud.value
                    estado_campos["texto_home_subtitulo"] = t_homesub.value
                    estado_campos["texto_rodape"] = t_rodape.value

                    with ui.row().classes("w-full items-center flex-wrap") \
                            .style("gap: 0.5rem"):
                        _botao_padrao("Restaurar padrão", tipo="restaurar", icone="restore",
                            on_click=lambda: confirmar(
                                "textos fixos",
                                lambda: restaurargrupo(
                                    {"texto_login_título": "INTRANET Básica",
                                     "texto_login_subtítulo": "Acesso restrito a usuários autorizados",
                                     "texto_login_hint": "Primeiro acesso? Use master / master e troque a senha.",
                                     "texto_home_saudacao": "Olá",
                                     "texto_home_subtítulo": "Sua intranet corporativa é tudo em um só lugar.",
                                     "texto_rodape": "uso interno"},
                                    "textos",
                                    campos=[(t_login, "texto_login_título", "INTRANET Básica"),
                                            (t_sub, "texto_login_subtítulo", "Acesso restrito a usuários autorizados"),
                                            (t_hint, "texto_login_hint", "Primeiro acesso? Use master / master e troque a senha."),
                                            (t_saud, "texto_home_saudacao", "Olá"),
                                            (t_homesub, "texto_home_subtítulo", "Sua intranet corporativa é tudo em um só lugar."),
                                            (t_rodape, "texto_rodape", "uso interno")])))

                # ---- Configurações gerais (RF-57) ----
                with ui.card().classes("w-full"):
                    ui.label("Configurações gerais do sistema").classes(
                        "text-subtitle1 font-bold")
                    ui.label("Intervalo de backup, retenção de sessão e pasta raiz dos arquivos.") \
                        .classes("text-caption text-grey-7 max-w-3xl -mt-2")

                    with ui.grid(columns="grid-cols-1 sm:grid-cols-2") \
                            .classes("w-full").style("gap: 1.25rem"):
                        inp_backup = _campo_empilhado(
                            "Intervalo de backup (horas)",
                            get_config("backup_interval_hours", "12")) \
                            .on_value_change(lambda e: estado_campos.update(
                                backup_interval_hours=e.value))
                        inp_sessao = _campo_empilhado(
                            "Retenção de sessão (dias)",
                            get_config("sessao_retencao", "50")) \
                            .on_value_change(lambda e: estado_campos.update(
                                sessao_retencao=e.value))

                    # Garante que os valores atuais já entrem no estado sem o usuário mexer
                    estado_campos["backup_interval_hours"] = inp_backup.value
                    estado_campos["sessao_retencao"] = inp_sessao.value

                    inp_raiz = ui.input(
                        "Pasta raiz dos arquivos (BASE_DIR)",
                        value=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) \
                        .props("outlined dense readonly").classes("w-full") \
                        .tooltip("Diretório raiz do sistema (somente leitura)")

                    with ui.row().classes("w-full items-center flex-wrap") \
                            .style("gap: 0.5rem"):
                        _botao_padrao("Restaurar padrão", tipo="restaurar", icone="restore",
                          on_click=lambda: confirmar(
                              "configurações gerais",
                              lambda: restaurar_grupo(
                                  {"backup_interval_hours": "12",
                                   "sessao_retencao": "50"},
                                  "configurações gerais",
                                  campos=[(inp_backup, "backup_interval_hours", "12"),
                                          (inp_sessao, "sessao_retencao", "50")],
                                  pos_acao=lambda: _reagendar_backups(12)))

            # ============================================================
            # ABA: E-MAIL / SMTP
            # ============================================================
            with ui.tab_panel(tab_email):
                from mod_intranet import email_util

                with ui.card().classes("w-full"):
                    ui.label("E-mail / SMTP (envio de documentos)").classes(
                        "text-subtitle1 font-bold")
                    ui.label("Credenciais do servidor de saída usadas para enviar empenhos "
                             "renomeados por e-mail.").classes(
                        "text-caption text-grey-7 max-w-3xl -mt-2")

                    with ui.grid(columns="grid-cols-1 sm:grid-cols-2") \
                            .classes("w-full").style("gap: 1.25rem"):
                        sm_serv = _campo_empilhado(
                            "Servidor SMTP", get_config("smtp_servidor", "")) \
                            .on_value_change(lambda e: estado_campos.update(
                                smtp_servidor=e.value))
                        sm_port = _campo_empilhado(
                            "Porta", get_config("smtp_porta", "587")) \
                            .on_value_change(lambda e: estado_campos.update(
                                smtp_porta=e.value))
                        sm_user = _campo_empilhado(
                            "Usuário / login", get_config("smtp_usuario", "")) \
                            .on_value_change(lambda e: estado_campos.update(
                                smtp_usuario=e.value))
                        sm_de = _campo_empilhado(
                            "Remetente (De)", get_config("smtp_de", "")) \
                            .on_value_change(lambda e: estado_campos.update(
                                smtp_de=e.value))
                        sm_senha = _campo_empilhado(
                            "Senha", get_config("smtp_senha", ""),
                            tooltip="Senha do servidor SMTP") \
                            .props("password password_toggle_button") \
                            .on_value_change(lambda e: estado_campos.update(
                                smtp_senha=e.value))
                        with ui.column().classes("min-w-0").style("gap: 0.25rem"):
                            ui.label("Criptografia").classes("text-caption text-grey-7")
                            sm_tls = ui.switch(
                                "Usar TLS (STARTTLS)",
                                value=get_config("smtp_tls", "1") == "1") \
                                .props("dense") \
                                .on_value_change(
                                    lambda e: estado_campos.update(smtp_tls=e.value))

                    # Garante que os valores atuais já entrem no estado sem o usuário mexer
                    estado_campos["smtp_servidor"] = sm_serv.value
                    estado_campos["smtp_porta"] = sm_port.value
                    estado_campos["smtp_usuario"] = sm_user.value
                    estado_campos["smtp_senha"] = sm_senha.value
                    estado_campos["smtp_de"] = sm_de.value
                    estado_campos["smtp_tls"] = sm_tls.value

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

                    with ui.row().classes("w-full items-center flex-wrap") \
                            .style("gap: 0.5rem"):
                        _botao_padrao("Restaurar padrão", tipo="restaurar", icone="restore",
                          on_click=lambda: confirmar(
                              "e-mail / SMTP",
                              lambda: restaurar_grupo(
                                  {"smtp_servidor": "", "smtp_porta": "587",
                                   "smtp_usuario": "", "smtp_senha": "",
                                   "smtp_de": "", "smtp_tls": "1"},
                                  "e-mail / SMTP",
                                  campos=[(sm_serv, "smtp_servidor", ""),
                                          (sm_port, "smtp_porta", "587"),
                                          (sm_user, "smtp_usuario", ""),
                                          (sm_senha, "smtp_senha", ""),
                                          (sm_de, "smtp_de", "")],
                                  pos_acao=lambda: (
                                      sm_tls.set_value(True),
                                      estado_campos.update(smtp_tls=True))))
                        _botao_padrao("Testar conexão SMTP", tipo="secundario",
                                      icone="mail", on_click=testar_smtp)

            # ============================================================
            # ABA: OBSERVABILIDADE / LOGS
            # ============================================================
            with ui.tab_panel(tab_obs):
                with ui.card().classes("w-full"):
                    ui.label("Observabilidade e logs (loguru)").classes(
                        "text-subtitle1 font-bold")
                    ui.label("Logs de erro/debug/info em arquivo, com rotação (tempo ou "
                             "tamanho) e retenção configurável. Arquivos rotacionados são "
                             "compactados em .zip e mantidos até o prazo de retenção.").classes(
                        "text-caption text-grey-7 max-w-3xl -mt-2")

                    with ui.grid(columns="grid-cols-1 sm:grid-cols-2") \
                            .classes("w-full").style("gap: 1.25rem"):
                        with ui.column().classes("min-w-0").style("gap: 0.25rem"):
                            ui.label("Ativação").classes("text-caption text-grey-7")
                            sw_ativo = ui.switch(
                                "Logs ativos",
                                value=get_config("log_ativo", "1") == "1") \
                                .props("dense")
                        with ui.column().classes("min-w-0").style("gap: 0.25rem"):
                            ui.label("Nível mínimo").classes("text-caption text-grey-7")
                            sel_nivel = ui.select(
                                {"DEBUG": "DEBUG", "INFO": "INFO",
                                 "WARNING": "WARNING", "ERROR": "ERROR"},
                                value=get_config("log_nivel", "INFO")) \
                                .props("dense outlined").classes("w-full max-w-[30ch]") \
                                .tooltip("DEBUG, INFO, WARNING ou ERROR")
                        inp_rot = _campo_empilhado(
                            "Rotação (tempo ou tamanho)",
                            get_config("log_rotacao", "1 month"),
                            tooltip="Ex.: '1 month' (tempo) ou '50 MB' (tamanho). "
                                    "Padrão '1 month'.")
                        inp_ret = _campo_empilhado(
                            "Retenção dos arquivos compactados (.zip)",
                            get_config("log_retencao", "4 months"),
                            tooltip="Ex.: '4 months' (padrão). Arquivos .zip "
                                    "mantidos até o prazo.")

                    # Garante que os valores já entrem no estado mesmo sem o usuário mexer
                    estado_campos["log_ativo"] = sw_ativo.value
                    estado_campos["log_nivel"] = sel_nivel.value
                    estado_campos["log_rotacao"] = inp_rot.value
                    estado_campos["log_retencao"] = inp_ret.value
                    sw_ativo.on_value_change(
                        lambda e: estado_campos.update(log_ativo=e.value))
                    sel_nivel.on_value_change(
                        lambda e: estado_campos.update(log_nivel=e.value))
                    inp_rot.on_value_change(
                        lambda e: estado_campos.update(log_rotacao=e.value))
                    inp_ret.on_value_change(
                        lambda e: estado_campos.update(log_retencao=e.value))

                    def limpar_logs():
                        from mod_intranet import observabilidade as _obs
                        ok, msg = _obs.limpar_todos()
                        ui.notify(msg, type="positive" if ok else "negative")
                        audit_log(user_nome, "intranet", "logs_limpos", msg)
                        _obs.get_logger().warning(
                            f"logs limpos manualmente por {user_nome}: {msg}")

                    def _reconfigurar_obs():
                        """Reapplies the observability config after a restore.

                        Reaplica a configuração da observabilidade (ativação,
                        nível, rotação e retenção) após restaurar os padrões."""
                        from mod_intranet import observabilidade as _obs
                        _obs.configurar()

                    with ui.row().classes("w-full items-center flex-wrap") \
                            .style("gap: 0.5rem"):
                        _botao_padrao("Restaurar padrão", tipo="restaurar", icone="restore",
                          on_click=lambda: confirmar(
                              "observabilidade / logs",
                              lambda: restaurar_grupo(
                                  {"log_ativo": "1", "log_nivel": "INFO",
                                   "log_rotacao": "1 month", "log_retencao": "4 months"},
                                  "observabilidade / logs",
                                  campos=[(sw_ativo, "log_ativo", True),
                                          (sel_nivel, "log_nivel", "INFO"),
                                          (inp_rot, "log_rotacao", "1 month"),
                                          (inp_ret, "log_retencao", "4 months")],
                                  pos_acao=lambda: _reconfigurar_obs())))
                        _botao_padrao("Limpar TODOS os logs", tipo="perigo",
                                      icone="delete_forever",
                                      on_click=lambda: confirmar(
                                          "LIMPEZA TOTAL dos logs", limpar_logs))

            # ============================================================
            # ABA: DOCUMENTAÇÃO
            # ============================================================
            with ui.tab_panel(tab_docs):
                with ui.card().classes("w-full"):
                    ui.label("Documentação").classes("text-subtitle1 font-bold")
                    ui.label("Reconstrói a documentação MkDocs do projeto e a publica em "
                             "/documentacao (mesmo endereço/porta do sistema, nova aba). "
                             "Edições em docs/*.md valem após reconstruir.") \
                        .classes("text-caption text-grey-7 max-w-3xl -mt-2")

                    def reconstruir_docs():
                        ok, msg = documentacao.reconstruir()
                        if ok:
                            audit_log(user_nome, "intranet", "documentacao_reconstruida",
                                      msg[:200])
                        ui.notify(msg, type="positive" if ok else "negative",
                                  multi_line=True, close_button="Fechar")

                    with ui.row().classes("w-full items-center flex-wrap") \
                            .style("gap: 0.5rem"):
                        _botao_padrao("Reconstruir documentação", tipo="primario",
                              icone="menu_book", on_click=reconstruir_docs)
                        _botao_padrao(icone="open_in_new", tipo="icone",
                                      tooltip="Abrir a documentação em nova aba",
                                      on_click=lambda: ui.navigate.to(
                                          "/documentacao", new_tab=True))

            # ============================================================
            # ABA: MÓDULO
            # ============================================================
            with ui.tab_panel(tab_mod):
                # ---- Páginas do sistema (nome e ícone) ----
                with ui.card().classes("w-full"):
                    ui.label("Páginas do sistema — como aparecem no menu").classes(
                        "text-subtitle1 font-bold")
                    ui.label("Edite o nome exibido (menu lateral e título do cabeçalho), a URL "
                             "da página (slug), o ícone (Material Icons) e a ORDEM de cada "
                             "página usando as setas ↑/↓ (a ordem é salva imediatamente). "
                             "Auditoria e Usuários são INDISPENSÁVEIS ao funcionamento do "
                             "sistema: podem ser reordenados, mas não desativados.").classes(
                        "text-caption text-grey-7 max-w-3xl -mt-2")

                    modulos_ordenados = list(autenticacao.modulos_registrados())
                    campos = {}
                    estado_campos["paginas"] = campos  # lido pelo SALVAR TUDO
                    campos_url = {}
                    estado_campos["urls"] = campos_url  # lido pelo SALVAR TUDO (URLs)

                    container_modulos = ui.column().classes("w-full")

                    def refresh_modulos():
                        """Rebuilds the ordered module list (after a reorder).

                        Remonta a lista ÚNICA de módulos na ordem vigente de
                        `tb_modulos.ordem`, recriando os campos de edição e os
                        botões ↑/↓. Mantém `estado_campos["paginas"]` e
                        `estado_campos["urls"]` apontando para os mesmos dicts
                        `campos`/`campos_url` (contrato do SALVAR TUDO).
                        Em falha, registra loguru e notifica o usuário."""
                        nonlocal modulos_ordenados
                        try:
                            container_modulos.clear()
                            modulos_ordenados = list(autenticacao.modulos_registrados())
                            campos.clear()
                            campos_url.clear()
                            with container_modulos:
                                # Cabeçalho de colunas — oculto em sm/md (cada célula
                                # já tem label via _campo_empilhado)
                                with ui.grid().classes(
                                        COLUNAS_MODULOS + " w-full bg-grey-1 rounded-lg "
                                        "px-3 py-2 text-caption font-bold text-grey-8 "
                                        "items-start hidden lg:grid"
                                ).style("gap: 0.75rem"):
                                    ui.label("#").classes("text-center").tooltip(
                                        "Posição no menu — use ↑/↓ para reordenar")
                                    ui.label("Página (chave)").tooltip(
                                        "Identificador interno do módulo")
                                    ui.label("Nome exibido (menu e título)").tooltip(
                                        "Texto que aparece no menu lateral e no título do cabeçalho")
                                    ui.label("URL da página").tooltip(
                                        "Slug da rota — ex.: /renomear-empenho → /renomeador")
                                    ui.label("Ícone (Material Icons)").tooltip(
                                        "Nome do ícone Material. Digite ou escolha na lista "
                                        "(ex.: people, article, history)")
                                    ui.label("Situação")

                                for idx, (chave, nome, icone, rota, ativo) in enumerate(modulos_ordenados):
                                    is_indisp = chave in MODULOS_INDISPENSAVEIS
                                    with ui.grid().classes(
                                            COLUNAS_MODULOS + " w-full bg-white border "
                                            "border-grey-2 rounded-lg px-3 py-2 items-center "
                                            "hover:shadow-sm"
                                            + (" border-amber-200 bg-amber-50/40"
                                               if is_indisp else "")
                                    ).style("gap: 0.75rem"):
                                        # Coluna de ordem: posição + setas ↑/↓
                                        with ui.column().classes("items-center").style("gap: 0.1rem"):
                                            ui.label(str(idx + 1)).classes(
                                                "text-caption font-bold text-grey-8")
                                            with ui.row().classes("items-center").style("gap: 0.1rem"):
                                                _botao_padrao(icone="arrow_upward",
                                                              tipo="icone",
                                                              tooltip="Mover para cima",
                                                              on_click=lambda _, i=idx: _mover(i, -1))
                                                _botao_padrao(icone="arrow_downward",
                                                              tipo="icone",
                                                              tooltip="Mover para baixo",
                                                              on_click=lambda _, i=idx: _mover(i, 1))
                                        _campo_empilhado("Página (chave)", chave, readonly=True)
                                        inp_n = _campo_empilhado(
                                            "Nome exibido", nome,
                                            tooltip="Usado no menu lateral e no cabeçalho ao entrar na página")
                                        inp_url = _campo_empilhado(
                                            "URL da página", rota,
                                            tooltip="Slug da rota — ex.: /renomear-empenho → /renomeador")
                                        inp_i = _campo_icone(icone)
                                        if is_indisp:
                                            with ui.row().classes("items-center").style("gap: 0.25rem"):
                                                ui.icon("lock", size="sm").classes("text-amber-7").tooltip(
                                                    "Sempre ativo — não pode ser desativado")
                                            sw = ui.switch(value=True).props("dense disabled").classes("hidden")
                                        else:
                                            with ui.column().classes("items-start").style("gap: 0.25rem"):
                                                ui.label("Ativo").classes("text-caption text-grey-7")
                                                sw = ui.switch(value=bool(ativo)).props("dense color=primary")
                                        campos[chave] = (inp_n, inp_i, sw)
                                        campos_url[chave] = inp_url
                        except Exception:
                            from mod_intranet import observabilidade
                            observabilidade.get_logger("intranet").exception(
                                "falha ao remontar a lista de módulos")
                            ui.notify("Erro ao recarregar a lista de módulos.",
                                      type="negative")

                    def _mover(idx, direcao):
                        """Moves a module up/down in the display order and persists.

                        Troca o módulo da posição `idx` com o vizinho na direção
                        `direcao` (-1 sobe, +1 desce), grava a nova ordem via
                        `autenticacao.reordenar_modulos` e remonta a lista.
                        Edições ainda não salvas (nome/ícone/ativo/url) são
                        preservadas entre a remontagem. Em falha, registra
                        loguru e notifica o usuário."""
                        try:
                            novo_idx = idx + direcao
                            if novo_idx < 0 or novo_idx >= len(modulos_ordenados):
                                return
                            # Preserva edições pendentes antes de remontar a lista
                            pendentes = {chave: (inp_n.value, inp_i.value, sw.value)
                                         for chave, (inp_n, inp_i, sw) in campos.items()}
                            pendentes_url = {chave: inp_u.value
                                             for chave, inp_u in campos_url.items()}
                            modulos_ordenados[idx], modulos_ordenados[novo_idx] = \
                                modulos_ordenados[novo_idx], modulos_ordenados[idx]
                            chaves = [m[0] for m in modulos_ordenados]
                            ok, msg = autenticacao.reordenar_modulos(user_nome, chaves)
                            ui.notify(msg, type="positive" if ok else "negative")
                            refresh_modulos()
                            for chave, (nome_val, icone_val, ativo_val) in pendentes.items():
                                if chave in campos:
                                    campos[chave][0].value = nome_val
                                    campos[chave][1].value = icone_val
                                    campos[chave][2].value = ativo_val
                            for chave, url_val in pendentes_url.items():
                                if chave in campos_url:
                                    campos_url[chave].value = url_val
                        except Exception:
                            from mod_intranet import observabilidade
                            observabilidade.get_logger("intranet").exception(
                                "falha ao mover módulo na lista de páginas")
                            ui.notify("Erro ao reordenar módulos.", type="negative")

                    refresh_modulos()

                    def restaurar_paginas_padrao():
                        """Native pages return to coded name/icon/route, are
                        reactivated and reordered to the MODULOS_SISTEMA sequence.

                        Páginas NATIVAS voltam ao nome/ícone/rota codificados,
                        reativadas e na ordem original de `MODULOS_SISTEMA`;
                        módulos criados pelo administrador permanecem intocados
                        (renumerados após os nativos, em ordem alfabética). Em
                        falha, registra loguru e notifica o usuário."""
                        try:
                            from mod_intranet import rotas_modulos
                            for chave, nome, icone, rota in autenticacao.MODULOS_SISTEMA:
                                conn = autenticacao.get_connection()
                                try:
                                    conn.execute(
                                        "UPDATE tb_modulos SET nome=?, icone=?, rota=?, ativo=1 "
                                        "WHERE chave=? AND nativo=1",
                                        (nome, icone, rota, chave))
                                    conn.commit()
                                finally:
                                    conn.close()
                                # Re-registra a rota nativa ao vivo (idempotente)
                                rotas_modulos.registrar_modulo(chave, rota)
                            # Restaura a ordem nativa e renumera os não-nativos depois
                            conn = autenticacao.get_connection()
                            try:
                                for idx, (chave, _, _, _) in enumerate(
                                        autenticacao.MODULOS_SISTEMA, start=1):
                                    conn.execute(
                                        "UPDATE tb_modulos SET ordem=? WHERE chave=? AND nativo=1",
                                        (idx, chave))
                                conn.execute(
                                    "SELECT COALESCE(MAX(ordem), 0) FROM tb_modulos WHERE nativo=1")
                                max_nativo = conn.fetchone()[0]
                                conn.execute(
                                    "SELECT chave FROM tb_modulos WHERE nativo=0 ORDER BY nome")
                                for i, (chave,) in enumerate(conn.fetchall()):
                                    conn.execute(
                                        "UPDATE tb_modulos SET ordem=? WHERE chave=?",
                                        (max_nativo + i + 1, chave))
                                conn.commit()
                            finally:
                                conn.close()
                            audit_log(user_nome, "intranet", "config_restaurada",
                                      "páginas nativas restauradas")
                            ui.notify("Páginas nativas restauradas ao padrão — recarregue com F5",
                                      type="positive")
                        except Exception:
                            from mod_intranet import observabilidade
                            observabilidade.get_logger("intranet").exception(
                                "falha ao restaurar páginas nativas ao padrão")
                            ui.notify("Erro ao restaurar páginas nativas.", type="negative")

                    with ui.row().classes("w-full items-center").style("gap: 0.5rem"):
                        _botao_padrao("Restaurar padrão", tipo="restaurar",
                                      icone="restore",
                                      on_click=lambda: confirmar(
                                          "nomes, URLs, ícones e ordem das páginas",
                                          restaurar_paginas_padrao))

                # ---- Registro de módulos e vínculos órfãos ----
                from mod_gest_cad_usuario import manipulador_bd as gest_usuarios

                with ui.card().classes("w-full"):
                    ui.label("Registro de módulos e vínculos órfãos").classes(
                        "text-subtitle1 font-bold")
                    ui.label("Todo módulo registrado aqui passa a aparecer automaticamente nas telas "
                             "de criação/edição de usuários e nos menus — inclusive módulos futuros. "
                             "Vínculos apontando para módulos inexistentes ficam destacados abaixo "
                             "para manutenção ou exclusão.").classes(
                        "text-caption text-grey-7 max-w-3xl -mt-2")

                    box_orfaos = ui.column().classes("w-full -mt-2").style("gap: 1rem")

                    def refresh_orfaos():
                        """Rebuilds the orphan-links panel (register new module + orphans).

                        Recarrega o painel de vínculos órfãos: re-lista os órfãos e
                        remonta a expansão "Registrar novo módulo (futuro)" e a lista
                        de vínculos sem módulo correspondente."""
                        box_orfaos.clear()
                        orfaos = gest_usuarios.listar_vinculos_orfaos(autenticacao.chaves_ativas())
                        with box_orfaos:
                            # --- registrar novo módulo ---
                            with ui.expansion("Registrar novo módulo (futuro)",
                                              icon="add_circle_outline").classes("w-full"):
                                n_ativo = {"valor": False}
                                with ui.row().classes("w-full flex-wrap items-end").style("gap: 0.5rem"):
                                    n_chave = ui.input("Chave única *",
                                                       placeholder="ex.: folha_ponto").props("outlined dense")
                                    n_nome = ui.input("Nome exibido *",
                                                      placeholder="ex.: Folha de Ponto").props("outlined dense")
                                    n_icone = _campo_icone("extension")
                                    n_rota = ui.input("Rota",
                                                      placeholder="# ou /rota-futura") \
                                        .props("outlined dense").classes("max-w-[180px]")
                                    ui.switch("Já em funcionamento",
                                              on_change=lambda e: n_ativo.update(valor=bool(e.value))) \
                                        .tooltip("Marque só se a rota/página já existe no main.py")

                                    def registrar():
                                        """Registers a new (future) module via autenticacao.registrar_modulo.

                                        Cadastra um módulo novo com chave/nome/ícone/rota e notifica o
                                        resultado; em sucesso limpa os campos do formulário."""
                                        ok, msg = autenticacao.registrar_modulo(
                                            user_nome, n_chave.value, n_nome.value,
                                            n_icone.value or "extension", n_rota.value or "#",
                                            ativo=n_ativo["valor"])
                                        ui.notify(msg, type="positive" if ok else "negative")
                                        if ok:
                                            n_chave.value = n_nome.value = ""
                                            n_rota.value = "#"

                                    _botao_padrao("Registrar", tipo="primario", icone="add_circle",
                                              on_click=registrar)

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
                                        _botao_padrao(icone="link_off", tipo="icone", color="red-8",
                                                  tooltip="Excluir permissão órfã",
                                                  on_click=lambda _, uu=u, mm=m: (
                                                      gest_usuarios.remover_acesso(user_nome, uu, mm),
                                                      refresh_orfaos()))

                    refresh_orfaos()
