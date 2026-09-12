"""User management screen — soft CRUD with per-module access control.

Tela de Gestão de Cadastro de Usuários — soft CRUD completo. Barra superior
fixa (abas | busca instantânea | botão Novo usuário) e tudo no topo da
página — sem precisar rolar a lista para acessar controles. Componentes,
diálogos, ações de linha, rodapés, tema/aparência e notificações seguem o
padrão central: `mod_intranet.ui_comum` (`botao`, `botao_icone`,
`dialogo_card`, `rodape_dialogo`) e `mod_intranet.tema_modulo`
(`ler_tema`, `notificar` — timeout configurável em `notificacao_timeout`).
Botões seguem o tema do sistema por padrão: chaves `usuarios_cor_botao`,
`usuarios_cor_texto_botao` e `usuarios_btn_tamanho` vazias herdam as chaves
`intranet_*` ("Botões do sistema" em /configuracoes); os campos do cupê
Administração são o override do módulo. Acesso: administrador geral ou
administrador do módulo 'usuarios'.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import math
import re
import unicodedata

from nicegui import ui

from mod_intranet import autenticacao
from mod_intranet import observabilidade
from mod_intranet.bd_manipulador import audit_log
from mod_intranet.aba_modulo import cabecalho, campo_busca
from mod_intranet.tema_modulo import ler_tema, notificar
from mod_intranet.ui_comum import botao, botao_icone, dialogo_card, rodape_dialogo, \
    rodape_salvar_restaurar
from mod_gest_cad_usuario import bd_manipulador as gest

log = observabilidade.get_logger("gest_cad_usuario")

OPCOES_PAPEL = {"": "— sem acesso —", "comum": "Comum", "administrador": "Administrador do módulo"}
ROTULOS_PAPEL = {"comum": "Comum", "administrador": "Administrador"}
_MAP_MODULOS = {}  # cache lazy: {chave: (nome, icone)}


def _nomes_modulos():
    """Mapa chave → (nome, icone) dos módulos registrados — populado na primeira chamada."""
    if not _MAP_MODULOS:
        for chave, nome, icone, _rota, _ativo in autenticacao.modulos_registrados():
            _MAP_MODULOS[chave] = (nome, icone)
    return _MAP_MODULOS


def _norm(s):
    """Minúsculas, sem acentos e com pontuação vira espaço —
    buscar 'jose' acha 'José'; 'silva social' acha 'Silva-Social'."""
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return " ".join(re.findall(r"[a-z0-9]+", s))


def mostrar_tela(user_nome: str, perfil_global: str = ""):
    """Renders the user management screen (admin-only).

    Monta a tela completa: bloqueio de acesso para não administradores,
    tema/aparência do módulo `usuarios` via `ler_tema` (cor primária
    configurável em `usuarios_cor_botao`; vazia, herda o tema do sistema
    `intranet_*`, padrão #000000), cabeçalho, barra superior com
    abas/busca/botão Novo usuário e os painéis de usuários, sessões ativas
    e administração.
    """
    if not (perfil_global == "administrador_geral"
            or autenticacao.eh_admin_do_modulo(user_nome, "usuarios")):
        _acesso_negado()
        return
    eh_admin_geral = (perfil_global == "administrador_geral"
                      or autenticacao.perfil_global_de(user_nome) == "administrador_geral")

    tema = ler_tema("usuarios", cor_botao="#000000", cor_texto_botao="#FFFFFF",
                    texto_header="Cadastro de usuários, papéis e acessos por módulo (soft CRUD · LGPD).")
    ui.colors(primary=tema["cor_botao"])

    t_cor_titulo = tema["cor_titulo"]
    t_cor_fundo_cab = tema["cor_fundo"]
    t_texto_header = tema["texto_header"]

    estado_busca = {"valor": ""}
    refreshers = {}  # nome -> função de atualização (registrada por cada aba)

    def ao_digitar(e):
        estado_busca["valor"] = e.value or ""
        for chave in ("usuarios",):
            if chave in refreshers:
                try:
                    refreshers[chave]()
                except Exception as e:
                    log.exception(f"ao_digitar: falha ao atualizar aba '{chave}' | {e}")

    def novo_usuario():
        _dlg_novo(user_nome, lambda: [refreshers[k]() for k in
                                      ("usuarios",) if k in refreshers])

    with ui.column().classes("w-full p-6 gap-4"):
        cabecalho("Gestão de Usuários",
                   t_texto_header,
                   chave_modulo="usuarios", cor_titulo=t_cor_titulo, cor_fundo=t_cor_fundo_cab)

        # ===== BARRA SUPERIOR (linha única): abas à esquerda | busca larga + botão à direita =====
        with ui.row().classes("w-full items-center justify-between flex-wrap bg-white rounded-lg shadow-sm px-3 py-2").style("gap: 0.75rem; min-width: 0"):
            with ui.tabs().props("dense inline-label").classes("min-w-0 max-w-full overflow-x-auto flex-1") as tabs:
                tab_users = ui.tab("Usuários", icon="people")
                tab_sessoes = ui.tab("Sessões Ativas", icon="wifi")
            with ui.row().classes("items-center flex-wrap justify-end flex-1").style("gap: 0.5rem; min-width: 0; width: min(100%, 620px)"):
                campo_busca(
                    "🔍  Buscar… nome, e-mail, telefone, perfil, id ou estado "
                    "(provisório, bloqueado, sessão, excluído)", ao_digitar,
                    tooltip="Busca em todos os campos do usuário. Palavras-chave de estado: "
                            "'provisório' (senha a trocar), 'bloqueado', 'sessão' (com sessão ativa), "
                            "'excluído'. Sem acentos e maiúsculas.") \
                    .props('data-testid=usuarios-busca')
                botao("Novo usuário", icone="person_add", on_click=novo_usuario,
                      chave_modulo="usuarios", extra_classes="shrink-0",
                      tooltip="Criar usuário definindo perfil e liberação por módulo") \
                    .props('data-testid=usuarios-novo')

        with ui.tab_panels(tabs, value=tab_users).classes("w-full bg-transparent"):
            with ui.tab_panel(tab_users):
                _painel_usuarios(user_nome, estado_busca, refreshers)
            with ui.tab_panel(tab_sessoes):
                _painel_sessoes(user_nome, refreshers)


def _acesso_negado():
    """Renders the 'access restricted' panel for non-admin users."""
    with ui.column().classes("w-full items-center p-12 gap-3"):
        ui.icon("block", size="64px").classes("text-red-8")
        ui.label("Acesso restrito").classes("text-h6")
        ui.label("Somente administradores gerais e administradores do módulo de usuários.").classes(
            "text-body2 text-grey-7")


# ==================== COMPONENTES COMPARTILHADOS DE ACESSO ====================

def _seletores_de_acesso(container, nome_usuario=None):
    """Monta um seletor de papel por módulo dentro de `container`.
    Itera TODOS os módulos registrados no banco — existentes e futuros."""
    atual = {c: "" for c, n, i, r, a in autenticacao.modulos_registrados()}
    meta = {}
    if nome_usuario:
        for chave, papel, liberado_por, data in gest.listar_acessos(nome_usuario):
            atual[chave] = papel
            meta[chave] = f"{liberado_por} · {(data or '')[:16]}"
    desat = {c for c, n, i, r, a in autenticacao.modulos_registrados() if not a}
    selecoes = {}
    with container:
        for chave, nome, icone, rota, ativo in autenticacao.modulos_registrados():
            indisponivel = not ativo
            with ui.row().classes("w-full items-center justify-between py-0.5 flex-wrap"):
                with ui.row().classes("items-center gap-2 min-w-[190px]"):
                    ui.icon(icone).classes("text-primary" if not indisponivel else "text-orange-9")
                    ui.label(nome).classes("text-body2")
                    if indisponivel:
                        ui.badge("INDISPONÍVEL", color="orange-2").props(
                            "text-color=orange-10 outline dense").tooltip(
                            "Desativado ou ainda sem rota ativa — vínculo já pode ser definido agora")
                s = ui.select(OPCOES_PAPEL, value=atual.get(chave, ""),
                              on_change=None).props("outlined dense").classes("min-w-[220px]")
                selecoes[chave] = s
    return selecoes, meta


def _aplicar_acessos(ator, nome_usuario, selecoes):
    """Compara seletores com o estado atual e aplica só as diferenças."""
    atual_map = {c: None for c, n, i, r, a in autenticacao.modulos_registrados()}
    for chave, papel, *_ in gest.listar_acessos(nome_usuario):
        atual_map[chave] = papel
    erros, mudou = [], 0
    for chave, s in selecoes.items():
        novo = s.value or None
        if novo != atual_map.get(chave):
            ok, msg = gest.definir_acesso(ator, nome_usuario, chave, novo)
            if ok:
                mudou += 1
            else:
                erros.append(msg)
    return mudou, erros


# ==================== ABA 1: USUÁRIOS ====================

def _painel_usuarios(ator: str, termo_compartilhado=None, refreshers=None):
    """Lista paginada com filtros. Busca/botão vivem na BARRA SUPERIOR (mostrar_tela).
    Renderiza só a página visível — suporta milhares de usuários sem travar."""
    estado = termo_compartilhado if termo_compartilhado is not None else {"valor": ""}
    local = {"pagina": 1, "por_pagina": 20, "situacao": "", "perfil": "", "ordem": "nome"}
    container = ui.column().classes("w-full gap-2")

    SIT_OPCOES = {"": "Todas", "ativos": "Ativos", "bloqueados": "Bloqueados"}
    PERFIL_OPCOES = {"": "Todos"} | {p: p.replace("_", " ") for p in gest.PERFIS_GLOBAIS}
    ORDEM_OPCOES = {"nome": "A→Z (nome)", "id": "Numérica (ID)"}

    def _chave_ordenacao(linha):
        """Ordena por nome de tratamento/login (alfabética) ou por ID (numérica)."""
        if local["ordem"] == "id":
            return linha[0]
        _uid, _nome, _perfil, _ativo, _email, _fone, _cad, _aces, _del, completo, _motivo = linha
        trat = (completo or "").strip() or _nome
        return (_norm(trat), _norm(_nome))

    def _filtrar():
        termo = _norm(estado.get("valor"))
        tem_excluido = "exclu" in termo if termo else False
        todos = gest.listar_usuarios()
        # Excluídos (soft) só entram na lista quando a busca pede "excluído";
        # sem busca eles não aparecem na aba Usuários.
        linhas = todos if tem_excluido else [l for l in todos if not l[8]]
        if termo:
            # tokens de estado pesquisáveis por palavra-chave digitada
            tem_provisorio = "provisor" in termo
            tem_bloqueado = "bloque" in termo
            tem_sessao = "sess" in termo
            usa_estado = any((tem_provisorio, tem_bloqueado, tem_sessao, tem_excluido))

            pendentes = set()  # só computados se o token de estado for usado
            sessoes_cnt = {}
            if usa_estado:
                pendentes = set(autenticacao.usuarios_com_troca_pendente())
                sessoes_cnt = gest.sessoes_ativas_por_usuario()

            def _match_usuario(l):
                if tem_provisorio and l[1] in pendentes:
                    return True
                if tem_bloqueado and not l[3]:
                    return True
                if tem_sessao and sessoes_cnt.get(l[1], 0) > 0:
                    return True
                if tem_excluido and l[8]:
                    return True
                return False

            linhas = [l for l in linhas if (
                _match_usuario(l)
                or termo in _norm(str(l[0]))       # ID (numérica/alfabética)
                or termo in _norm(l[1])          # login
                or termo in _norm(l[2])          # perfil
                or termo in _norm(l[4])          # e-mail
                or termo in _norm(l[5])          # telefone
                or termo in _norm(l[7])          # módulos:papel
                or termo in _norm(l[9])          # nome completo
            )]
        sit = local["situacao"]
        if sit == "ativos":
            linhas = [l for l in linhas if l[3]]
        elif sit == "bloqueados":
            linhas = [l for l in linhas if not l[3]]
        if local["perfil"]:
            linhas = [l for l in linhas if l[2] == local["perfil"]]
        linhas.sort(key=_chave_ordenacao)
        return linhas

    def render():
        container.clear()
        pendentes = autenticacao.usuarios_com_troca_pendente()
        sessoes_cnt = gest.sessoes_ativas_por_usuario()
        todas = gest.listar_usuarios()
        linhas = _filtrar()
        total = len(linhas)
        por = local["por_pagina"]
        paginas = max(1, math.ceil(total / por))
        pag = min(local["pagina"], paginas)
        local["pagina"] = pag
        ini = (pag - 1) * por
        fatia = linhas[ini:ini + por]

        with container:
            # ---- linha de filtros + paginação ----
            with ui.row().classes("w-full items-center justify-between flex-wrap gap-2 "
                                  "bg-white rounded-lg shadow-sm px-3 py-1"):
                with ui.row().classes("items-center gap-2 flex-wrap"):
                    ui.icon("filter_alt").classes("text-grey-6 text-caption")
                    ui.select(SIT_OPCOES, value=local["situacao"], label="Situação",
                              on_change=lambda e: (local.update(situacao=e.value, pagina=1), render())) \
                        .props("outlined dense label").classes("min-w-[150px]")
                    ui.select(PERFIL_OPCOES, value=local["perfil"], label="Perfil global",
                              on_change=lambda e: (local.update(perfil=e.value, pagina=1), render())) \
                        .props("outlined dense label").classes("min-w-[170px]")
                    ui.select(ORDEM_OPCOES, value=local["ordem"], label="Ordenar por",
                              on_change=lambda e: (local.update(ordem=e.value, pagina=1), render())) \
                        .props("outlined dense label").classes("min-w-[160px]")
                    botao_icone("restart_alt", on_click=lambda: (
                        local.update(pagina=1, situacao="", perfil="", ordem="nome"), render()),
                        cor="grey-7", tooltip="Limpar filtros", chave_modulo="usuarios")
                with ui.row().classes("items-center gap-1"):
                    ui.select({10: "10", 20: "20", 50: "50", 100: "100"},
                              value=por, label="Por página", on_change=lambda e: (
                                  local.update(por_pagina=int(e.value), pagina=1), render())) \
                        .props("outlined dense label").classes("min-w-[120px]")
                    botao_icone("chevron_left", on_click=lambda: (
                        local.update(pagina=max(1, pag - 1)), render()),
                        chave_modulo="usuarios").props(f"disabled={pag <= 1}")
                    ui.label(f"{ini + 1}–{ini + len(fatia)} de {total}"
                             f"  ·  pág. {pag}/{paginas} ({len(todas)} no total)") \
                        .classes("text-caption text-grey-8 min-w-[190px] text-center")
                    botao_icone("chevron_right", on_click=lambda: (
                        local.update(pagina=min(paginas, pag + 1)), render()),
                        chave_modulo="usuarios").props(f"disabled={pag >= paginas}")

            # ---- tabela (colunas enxutas: ID | Tratamento | Ações) ----
            def _rotulo_situacao(ativo, deletado):
                if deletado:
                    return "excluído (soft)"
                return "ativo" if ativo else "bloqueado"

            cab = ("ID", "Tratamento", "Senha provisória", "Ações")
            with ui.grid(columns="60px 1fr 150px 220px").classes(
                    "w-full bg-grey-1 rounded-t-lg px-3 py-2 text-caption font-bold text-grey-8"):
                for c in cab:
                    ui.label(c)
            if not fatia:
                ui.label("Nenhum usuário encontrado para os filtros atuais.").classes(
                    "text-grey-6 p-4")
            for row in fatia:
                uid, nome, perfil, ativo, email, fone, cadastro, acessos, deletado, completo, _motivo = row
                trat = (completo or "").strip() or nome
                sit = _rotulo_situacao(ativo, deletado)
                perfil_rot = perfil.replace("_", " ")
                tem_provisoria = nome in pendentes and not deletado

                with ui.grid(columns="60px 1fr 150px 220px").classes(
                        "w-full border-b border-grey-2 px-3 py-2 items-center hover:bg-blue-50/50"):
                    ui.label(str(uid)).classes("text-caption text-grey-6")

                    # tratamento com hover -> expõe os demais campos
                    with ui.element("div").classes("cursor-help"):
                        with ui.row().classes("items-center gap-2"):
                            ui.label(trat).classes("font-medium")
                            ui.icon("info_outline").classes("text-grey-5 text-xs").tooltip(
                                "Passe o mouse para ver todos os dados")
                        with ui.tooltip().props("offset=[0,12]"):
                            with ui.column().classes("gap-1 p-1 min-w-[260px]"):
                                ui.label(f"@{nome}").classes("text-subtitle2 font-bold")
                                ui.separator()
                                ui.label(f"Perfil global: {perfil_rot}").classes("text-caption")
                                ui.label(f"Situação: {sit}").classes("text-caption")
                                ui.label(f"E-mail: {email or '—'}").classes("text-caption")
                                ui.label(f"Telefone: {fone or '—'}").classes("text-caption")
                                ui.label(f"Cadastro: {cadastro or '—'}").classes("text-caption")
                                ui.separator()
                                ui.label("Acesso aos módulos").classes("text-caption font-bold")
                                mapa_mod = _nomes_modulos()
                                if acessos:
                                    for trecho in acessos.split(","):
                                        trecho = trecho.strip()
                                        if ":" not in trecho:
                                            continue
                                        chave_mod, papel_mod = trecho.rsplit(":", 1)
                                        nome_mod, icone_mod = mapa_mod.get(chave_mod, (chave_mod, "extension"))
                                        with ui.row().classes("items-center gap-1"):
                                            ui.icon(icone_mod).classes("text-xs text-grey-6")
                                            ui.label(nome_mod).classes("text-caption font-medium")
                                            ui.badge(ROTULOS_PAPEL.get(papel_mod, papel_mod),
                                                     color="blue-grey-2").props("text-color=blue-grey-10 outline dense")
                                else:
                                    ui.label("—").classes("text-caption text-grey-6")

                    # coluna própria "Senha provisória" (tabulada à esquerda da Ações)
                    if tem_provisoria:
                        ui.badge("senha provisória", color="amber-3").props(
                            "text-color=amber-10 outline dense").tooltip(
                            "Troca obrigatória ainda não realizada")
                    else:
                        ui.label("").classes("text-caption")

                    with ui.row().style("gap: 0.25rem"):
                        botao_icone("edit", on_click=lambda _, n=nome: _dlg_editar(ator, n, render),
                                    cor="primary", tooltip="Editar dados e acessos",
                                    chave_modulo="usuarios")
                        botao_icone("content_copy",
                                    on_click=lambda _, n=nome: _dlg_duplicar(ator, n, render),
                                    cor="teal-8",
                                    tooltip="Duplicar usuário e suas configurações de acesso",
                                    chave_modulo="usuarios")
                        botao_icone("devices_other",
                                    on_click=lambda _, n=nome: _dlg_sessoes(ator, n),
                                    cor="indigo-8",
                                    tooltip=f"Sessões: {sessoes_cnt.get(nome, 0)} ativa(s) + histórico recente",
                                    chave_modulo="usuarios")
                        if nome != ator:
                            if not deletado and ativo:
                                botao_icone("vpn_key", on_click=lambda _, n=nome: _dlg_senha(ator, n),
                                            cor="amber-8", tooltip="Redefinir senha (provisória)",
                                            chave_modulo="usuarios")
                                botao_icone("block",
                                            on_click=lambda _, n=nome: (_gest_bloq(ator, n, True), render()),
                                            cor="orange-9", tooltip="Bloquear",
                                            chave_modulo="usuarios")
                            else:
                                botao_icone("settings_backup_restore",
                                            on_click=lambda _, n=nome: (_gest_bloq(ator, n, False), render()),
                                            cor="green-8",
                                            tooltip="Restaurar conta" +
                                                    (" (remove exclusão lógica)" if deletado else ""),
                                            chave_modulo="usuarios")
                            if deletado:
                                botao_icone("delete_forever",
                                            on_click=lambda _, n=nome: _dlg_excluir_definitivo(ator, n, render),
                                            cor="red-8",
                                            tooltip="Excluir definitivamente (LGPD — irreversível)",
                                            chave_modulo="usuarios")
                            else:
                                botao_icone("delete_outline",
                                            on_click=lambda _, n=nome: _dlg_excluir(ator, n, render),
                                            cor="orange-9",
                                            tooltip="Excluir (lógico) — pede motivo e move para a lista de excluídos",
                                            chave_modulo="usuarios")
                        else:
                            ui.icon("person_pin").classes("text-grey-5 self-center") \
                                .tooltip("Sua própria conta — use 'Meu Perfil' (menu superior)")

    if refreshers is not None:
        refreshers["usuarios"] = render
    render()


def _gest_bloq(ator, nome, bloquear):
    """Blocks or restores a user account and notifies the outcome.

    Bloqueia/restaura a conta via `gest.bloquear_usuario`, registra falha
    no loguru e notifica o resultado (positivo/negativo) com o timeout
    configurado (`notificacao_timeout`).
    """
    ok, msg = gest.bloquear_usuario(ator, nome, bloquear)
    if not ok:
        log.error(f"_gest_bloq: falha ao {'bloquear' if bloquear else 'restaurar'} {nome} por {ator} | {msg}")
    notificar(msg, type="positive" if ok else "negative")


def _dlg_sessoes(ator, nome):
    """User traceability dialog: active sessions + recent history.

    Diálogo de rastreabilidade do usuário: sessões ativas + histórico
    recente (IP, dispositivo e MAC), shell padronizado (`dialogo_card`) e
    ações de encerramento padronizadas (`botao_icone` na grade, `botao`
    primário compacto no rodapé às extremidades).
    """
    from datetime import datetime

    def _duracao(entrada, saida):
        try:
            fmt = "%Y-%m-%d %H:%M:%S"
            delta = datetime.strptime(saida[:19], fmt) - datetime.strptime(entrada[:19], fmt)
            mins = int(delta.total_seconds() // 60)
            return f"{mins // 60}h{mins % 60:02d}min" if mins >= 60 else f"{mins}min"
        except Exception as e:
            log.warning(f"_duracao: falha ao calcular duração de sessão | {e}")
            return "—"

    with dialogo_card(largura="w-full max-w-[820px] mx-4", chave_modulo="usuarios") as (dlg, card):
        with ui.card_section().classes("w-full gap-1"):
            ui.label(f"Sessões — {gest.nome_de_tratamento(nome)}").classes("text-h6")
            ui.label(f"@{nome} · rastreabilidade LGPD: IP, dispositivo e MAC "
                     "(quando resolvível na rede local)").classes("text-caption text-grey-7")
            if nome == ator:
                ui.badge("sua conta — encerrar a sessão atual deslogará você",
                         color="amber-3").props("text-color=amber-10 outline dense")

            # ---- ativas ----
            box_ativas = ui.column().classes("w-full mt-2")
            ui.separator()
            # ---- histórico ----
            ui.label("Histórico recente (últimas 10 encerradas)").classes(
                "text-subtitle2 font-bold mt-1")
            box_hist = ui.column().classes("w-full")

            def refresh_interno():
                box_ativas.clear()
                ativas = gest.listar_sessoes_ativas(nome)
                with box_ativas:
                    ui.label(f"Ativas agora ({len(ativas)})").classes("text-subtitle2 font-bold")
                    if not ativas:
                        ui.label("Nenhuma sessão ativa no momento.").classes(
                            "text-caption text-grey-6 italic")
                    else:
                        with ui.grid(columns="auto 0.9fr 1.4fr 0.9fr 1fr auto").classes(
                                "w-full bg-grey-1 rounded px-2 py-1 text-caption font-bold"):
                            for c in ("#", "Módulo", "Dispositivo", "IP", "MAC", ""):
                                ui.label(c)
                        for sid, _u, modulo, login, cookie, ip, disp, mac in ativas:
                            with ui.grid(columns="auto 0.9fr 1.4fr 0.9fr 1fr auto").classes(
                                    "w-full border-b border-grey-2 px-2 py-1 items-center"):
                                ui.label(str(sid)).classes("text-caption text-grey-6")
                                ui.label(modulo or "sistema").classes("text-caption")
                                ui.label(disp).classes("text-caption")
                                ui.label(ip).classes("text-caption font-mono")
                                ui.label(mac).classes("text-caption font-mono text-grey-6")
                                botao_icone("logout", on_click=lambda _, i=sid: (
                                    gest.encerrar_sessao(ator, i), refresh_interno()),
                                    cor="red-8", tooltip=f"Encerrar (entrada {login[:16]})",
                                    chave_modulo="usuarios")

                hist = gest.listar_historico_sessoes(nome, limite=10)
                box_hist.clear()
                with box_hist:
                    if not hist:
                        ui.label("Sem histórico encerrado.").classes(
                            "text-caption text-grey-6 italic")
                    else:
                        with ui.grid(columns="auto 0.9fr 1.3fr 0.9fr 0.7fr 1fr").classes(
                                "w-full bg-grey-1 rounded px-2 py-1 text-caption font-bold"):
                            for c in ("#", "Módulo", "Entrada → Saída", "Duração", "IP", "Dispositivo"):
                                ui.label(c)
                        for sid, modulo, entrada, saida, ip, disp, mac in hist:
                            with ui.grid(columns="auto 0.9fr 1.3fr 0.9fr 0.7fr 1fr").classes(
                                    "w-full border-b border-grey-2 px-2 py-1 items-center"):
                                ui.label(str(sid)).classes("text-caption text-grey-6")
                                ui.label(modulo or "sistema").classes("text-caption")
                                ui.label(f"{entrada[5:16]} → {saida[5:16]}").classes("text-caption")
                                ui.label(_duracao(entrada, saida)).classes("text-caption text-grey-7")
                                ui.label(ip).classes("text-caption font-mono")
                                ui.label(disp).classes("text-caption")

            refresh_interno()

            with ui.row().classes("w-full justify-between mt-3"):
                botao("Encerrar TODAS as sessões", variante="primario", compacto=True,
                      icone="sensors_off", cor="deep-purple-8",
                      on_click=lambda: (gest.encerrar_todas_sessoes(ator, nome),
                                        refresh_interno()),
                      chave_modulo="usuarios")
                botao("Fechar", on_click=dlg.close, variante="texto",
                      chave_modulo="usuarios")
    dlg.open()


def _dlg_novo(ator, refresh):
    """Create-user dialog: basic data, provisional password, module access.

    Diálogo de criação de usuário: dados básicos, senha provisória
    (troca obrigatória no primeiro acesso) e seletores de acesso por
    módulo; shell padronizado (`dialogo_card`), notificações via
    `notificar` e rodapé padrão (`rodape_dialogo`) com "Criar usuário"
    (primário compacto do tema).
    """
    with dialogo_card(largura="w-full max-w-[560px] mx-4", chave_modulo="usuarios") as (dlg, card):
        with ui.card_section().classes("w-full overflow-auto gap-2"):
            ui.label("Novo usuário").classes("text-h6")
            ui.label("Senha provisória — troca obrigatória no primeiro acesso.").classes(
                "text-caption text-grey-7 -mt-2")

            nome = ui.input("Nome de usuário (login) *").props("outlined dense").classes("w-full") \
                .tooltip("Usado apenas para entrar — não aparece como tratamento")
            completo = ui.input("Nome completo ou social *", placeholder="ex.: Maria Aparecida da Silva") \
                .props("outlined dense").classes("w-full") \
                .tooltip("Nome para tratamento nas telas. Pode ser o nome social "
                         "(Decreto 8.727/2016). Deve ser diferente do login")
            senha = ui.input(f"Senha provisória * (mín. {gest.senha_minima()})",
                             password=True, password_toggle_button=True) \
                .props("outlined dense").classes("w-full")
            with ui.grid(columns=2).classes("w-full gap-2"):
                email = ui.input("E-mail").props("outlined dense")
                fone = ui.input("Telefone").props("outlined dense")
            perfil = ui.select(gest.PERFIS_GLOBAIS, value="comum", label="Perfil global",
                               with_input=True).props("outlined dense").classes("w-full")

            ui.separator()
            ui.label("Acesso aos módulos (opcional — pode definir depois)").classes(
                "text-subtitle2 text-grey-8")
            box = ui.column().classes("w-full gap-0")
            selecoes, _meta = _seletores_de_acesso(box)

            def salvar():
                ok, msg = gest.criar_usuario(ator, nome.value or "", senha.value or "",
                                             email=email.value.strip() or None,
                                             fone=fone.value.strip() or None,
                                             perfil=perfil.value,
                                             nome_completo=completo.value)
                if not ok:
                    log.error(f"novo_usuario: falha ao criar '{nome.value}' por {ator} | {msg}")
                    notificar(msg, type="negative")
                    return
                mudou, erros = _aplicar_acessos(ator, nome.value.strip(), selecoes)
                if erros:
                    notificar(f"Usuário criado, mas houve erros nos acessos: {' | '.join(erros)}",
                              type="warning")
                else:
                    notificar(f"Usuário '{nome.value.strip()}' criado" +
                              (f" com {mudou} acesso(s)" if mudou else ""), type="positive")
                dlg.close()
                refresh()

            rodape_dialogo(dlg, acoes=[("Criar usuário", salvar)],
                           chave_modulo="usuarios", classes_extra="mt-3")
    dlg.open()


def _dlg_editar(ator, nome_atual, refresh):
    """Edit-user dialog: identity, global profile and per-module access.

    Diálogo de edição: renomear login, e-mail, telefone, nome de
    tratamento, perfil global e acessos por módulo. Título e separator
    permanecem manuais (vivem dentro do `card_section` — o helper
    `titulo=` os posicionaria no card, alterando o espaçamento); shell
    via `dialogo_card`, notificações via `notificar` e rodapé padrão com
    "Salvar alterações" (primário compacto do tema + ícone save).
    """
    row = gest.obter_usuario(nome_atual)
    if not row:
        notificar("Usuário não encontrado", type="negative")
        return
    _, _, _, email, fone, perfil, _, _, _deletado, completo = row

    with dialogo_card(largura="w-full max-w-[560px] mx-4", chave_modulo="usuarios") as (dlg, card):
        with ui.card_section().classes("w-full overflow-auto gap-2"):
            ui.label(f"Editar — {gest.nome_de_tratamento(nome_atual)}").classes("text-h6")
            ui.separator()

            ui.label("Identidade (chave primária ID preservada)").classes(
                "text-subtitle2 text-grey-8")
            novo_nome = ui.input("Nome de usuário (login)", value=nome_atual).props("outlined dense").classes("w-full")
            if nome_atual == "master":
                novo_nome.disable().tooltip("A conta master nativa não pode ser renomeada")

            completo_i = ui.input("Nome completo ou social *", value=completo or "",
                                  placeholder="Nome para tratamento — pode ser nome social") \
                .props("outlined dense").classes("w-full")

            with ui.grid(columns=2).classes("w-full gap-2"):
                email_i = ui.input("E-mail", value=email or "").props("outlined dense")
                fone_i = ui.input("Telefone", value=fone or "").props("outlined dense")
            perf_i = ui.select(gest.PERFIS_GLOBAIS, value=perfil, label="Perfil global",
                               with_input=True).props("outlined dense").classes("w-full")

            ui.separator()
            ui.label("Acesso aos módulos — papel em cada um").classes("text-subtitle2 text-grey-8")
            box = ui.column().classes("w-full gap-0")
            selecoes, meta = _seletores_de_acesso(box, nome_atual)

            def salvar():
                erros = []
                alvo = nome_atual
                if (novo_nome.value or "").strip() != nome_atual:
                    ok_r, msg_r = gest.renomear_usuario(ator, nome_atual, novo_nome.value.strip())
                    if not ok_r:
                        erros.append(msg_r)
                    else:
                        alvo = novo_nome.value.strip()
                ok_e, msg_e = gest.editar_usuario(ator, alvo, email=email_i.value.strip(),
                                                  fone=fone_i.value.strip(), perfil=perf_i.value,
                                                  nome_completo=completo_i.value)
                if not ok_e:
                    erros.append(msg_e)
                mudou, erros_a = _aplicar_acessos(ator, alvo, selecoes)
                erros.extend(erros_a)
                if erros:
                    log.error(f"editar_usuario: falha ao atualizar {nome_atual} por {ator} | {' | '.join(erros)}")
                    notificar(" | ".join(erros), type="negative")
                else:
                    notificar("Usuário atualizado" +
                              (f" ({mudou} acesso(s) alterado(s))" if mudou else ""), type="positive")
                    dlg.close()
                    refresh()

            rodape_dialogo(dlg, acoes=[("Salvar alterações", salvar, {"icone": "save"})],
                           chave_modulo="usuarios", classes_extra="mt-3")
    dlg.open()


# ==================== ABA 3: ADMINISTRAÇÃO (exclusiva do admin geral) ====================

def _dlg_senha(ator, nome):
    """Password reset dialog: sets a new provisional password.

    Diálogo de redefinição de senha: define nova senha provisória (troca
    obrigatória no próximo acesso); shell padronizado (`dialogo_card`) e
    rodapé padrão com "Redefinir" (cor amber-8 byte-idêntica). O label do
    campo mostra o mínimo vigente via `gest.senha_minima()` (chave
    `usuarios_senha_min`).
    """
    with dialogo_card(largura="w-[380px]", chave_modulo="usuarios",
                      max_altura=False) as (dlg, card):
        ui.label(f"Redefinir senha — {nome}").classes("text-h6")
        ui.label("O usuário receberá senha provisória e deverá trocá-la no próximo acesso.").classes(
            "text-caption text-orange-9 bg-orange-1 p-2 rounded")
        nova = ui.input(f"Nova senha provisória (mín. {gest.senha_minima()})", password=True,
                        password_toggle_button=True).props("outlined dense").classes("w-full")

        def salvar():
            ok, msg = gest.alterar_senha_admin(ator, nome, nova.value or "")
            if not ok:
                log.error(f"redefinir_senha: falha para {nome} por {ator} | {msg}")
            notificar(msg, type="positive" if ok else "negative")
            if ok:
                dlg.close()

        rodape_dialogo(dlg, acoes=[("Redefinir", salvar, {"cor": "amber-8"})],
                       chave_modulo="usuarios", classes_extra="mt-2")
    dlg.open()


def _dlg_excluir(ator, nome, refresh):
    """Stage 1: LOGICAL delete — asks for the reason and soft-deletes.

    Estágio 1: exclusão LÓGICA — pede o motivo e move o usuário para a
    lista de excluídos (reversível via 'Restaurar'); a exclusão PERMANENTE
    (LGPD) só existe dentro da lista de excluídos. Card com borda laranja
    (`dialogo_card` + classes extras); rodapé às extremidades mantido cru
    (`justify-between` não é o padrão do `rodape_dialogo`), com a ação via
    `botao` primário compacto.
    """
    with dialogo_card(largura="w-[440px]", chave_modulo="usuarios",
                      max_altura=False) as (dlg, card):
        card.classes("border-2 border-orange-5")
        ui.label("Excluir usuário").classes("text-h6 text-orange-9")
        ui.label(
            f"'{nome}' será movido para a lista de Excluídos: perde o acesso "
            "imediatamente e suas sessões são encerradas.\n"
            "Nada é apagado do banco — a exclusão é reversível via 'Restaurar'.\n"
            "A exclusão PERMANENTE (LGPD) só fica disponível dentro da lista de excluídos."
        ).classes("text-body2 whitespace-pre-line")
        motivo = ui.textarea("Motivo da exclusão *",
                             placeholder="ex.: desligamento da empresa a pedido do RH",
                             validation=lambda v: "Informe o motivo (mín. 3 caracteres)"
                             if len((v or "").strip()) < 3 else None) \
            .props("outlined dense autogrow").classes("w-full")

        def excluir():
            ok, msg = gest.soft_delete_usuario(ator, nome, motivo.value)
            if not ok:
                log.error(f"excluir_usuario: falha na exclusão lógica de {nome} por {ator} | {msg}")
            notificar(msg, type="positive" if ok else "negative")
            if ok:
                dlg.close()
                refresh()

        with ui.row().classes("w-full justify-between mt-2"):
            botao("Cancelar", on_click=dlg.close, variante="texto",
                  chave_modulo="usuarios")
            botao("Excluir (lógico)", variante="primario", compacto=True,
                  icone="delete_outline", cor="orange-9", on_click=excluir,
                  chave_modulo="usuarios")
    dlg.open()


def _dlg_excluir_definitivo(ator, nome, refresh):
    """Stage 2 (deleted list only): permanent removal (LGPD).

    Estágio 2 (apenas na lista de excluídos): remoção PERMANENTE do banco
    (LGPD — direito ao esquecimento), protegida por confirmação digitada;
    remove também postagens/comentários do Blog, arquivos PDF e cota, com
    autoria de empenhos anonimizada e auditoria preservada. Card com borda
    vermelha (`dialogo_card` + classes extras); rodapé às extremidades
    mantido cru, ação via `botao` primário compacto.
    """
    with dialogo_card(largura="w-[440px]", chave_modulo="usuarios",
                      max_altura=False) as (dlg, card):
        card.classes("border-2 border-red-6")
        ui.label("⚠ Exclusão definitiva").classes("text-h6 text-red-9")
        ui.label(
            f"Esta ação apaga PERMANENTEMENTE '{nome}' do banco de dados "
            "(conformidade LGPD — direito ao esquecimento).\n"
            "Também serão removidos: postagens e comentários do Blog, "
            "arquivos PDF do editor (físicos) e respectiva cota; registros de empenhos "
            "serão preservados com autoria anonimizada.\n"
            "Histórico de auditoria é preservado. Esta ação não pode ser desfeita."
        ).classes("text-body2 whitespace-pre-line")
        confirmacao = ui.input(f'Digite "{nome}" para confirmar').props("outlined dense").classes("w-full")

        def excluir():
            if confirmacao.value != nome:
                notificar("Confirmação não corresponde", type="negative")
                return
            ok, msg = gest.excluir_usuario_definitivo(ator, nome)
            if not ok:
                log.error(f"excluir_definitivo: falha ao excluir {nome} por {ator} | {msg}")
            notificar(msg, type="positive" if ok else "negative")
            if ok:
                dlg.close()
                refresh()

        with ui.row().classes("w-full justify-between mt-2"):
            botao("Cancelar", on_click=dlg.close, variante="texto",
                  chave_modulo="usuarios")
            botao("Excluir definitivamente", variante="primario", compacto=True,
                  icone="warning", cor="negative", on_click=excluir,
                  chave_modulo="usuarios")
    dlg.open()


# ==================== ABA 1.5: EXCLUÍDOS (SOFT) ====================

def _dlg_duplicar(ator, origem, refresh):
    """Duplicate-user dialog: clones profile and per-module access.

    Diálogo de duplicação: novo login herda o perfil global e os acessos
    por módulo do usuário origem (pré-selecionados); shell padronizado
    (`dialogo_card`), notificações via `notificar` e rodapé padrão com
    "Duplicar usuário" (teal-8 + ícone content_copy). O label do campo de
    senha mostra o mínimo vigente via `gest.senha_minima()`.
    """
    row = gest.obter_usuario(origem)
    if not row:
        notificar("Usuário origem não encontrado", type="negative")
        return
    origem_perfil = row[5]
    acessos = gest.listar_acessos(origem)

    with dialogo_card(largura="w-full max-w-[560px] mx-4", chave_modulo="usuarios") as (dlg, card):
        with ui.card_section().classes("w-full overflow-auto gap-2"):
            ui.label(f"Duplicar usuário — @{origem}").classes("text-h6")
            ui.label("O novo usuário herdará o perfil global e os acessos por módulo "
                     "do usuário origem, que já vêm pré-selecionados abaixo.").classes(
                "text-caption text-grey-7 -mt-2")
            ui.label(f"Origem: @{origem} · perfil {origem_perfil.replace('_', ' ')}"
                     f" · {len(acessos)} acesso(s) por módulo") \
                .classes("text-caption bg-teal-1 text-teal-9 px-2 py-1 rounded")

            nome = ui.input("Nome de usuário (login) *").props("outlined dense").classes("w-full") \
                .tooltip("Usado apenas para entrar — não aparece como tratamento")
            completo = ui.input("Nome completo ou social *", placeholder="ex.: Maria Aparecida da Silva") \
                .props("outlined dense").classes("w-full") \
                .tooltip("Nome para tratamento nas telas. Pode ser o nome social "
                         "(Decreto 8.727/2016). Deve ser diferente do login")
            senha = ui.input(f"Senha provisória * (mín. {gest.senha_minima()})", password=True,
                             password_toggle_button=True).props("outlined dense").classes("w-full")
            email = ui.input("E-mail *").props("outlined dense").classes("w-full")
            fone = ui.input("Telefone (opcional)").props("outlined dense").classes("w-full")

            ui.separator()
            ui.label(f"Acessos por módulo (copiados de @{origem})").classes(
                "text-subtitle2 text-grey-8")
            box = ui.column().classes("w-full gap-0")
            selecoes, _meta = _seletores_de_acesso(box, origem)

            def salvar():
                ok, msg = gest.duplicar_usuario(ator, origem, nome.value or "",
                                                senha.value or "",
                                                email=email.value.strip() or None,
                                                fone=fone.value.strip() or None,
                                                nome_completo=completo.value)
                if not ok:
                    log.error(f"duplicar_usuario: falha ao duplicar '{nome.value}' por {ator} | {msg}")
                    notificar(msg, type="negative")
                    return
                mudou, erros = _aplicar_acessos(ator, nome.value.strip(), selecoes)
                if erros:
                    notificar(f"Usuário duplicado, mas houve erros nos acessos: {' | '.join(erros)}",
                              type="warning")
                else:
                    notificar(f"Usuário '{nome.value.strip()}' duplicado de @{origem}"
                              + (f" · {mudou} acesso(s)" if mudou else ""), type="positive")
                dlg.close()
                refresh()

            rodape_dialogo(dlg, acoes=[("Duplicar usuário", salvar,
                                        {"icone": "content_copy", "cor": "teal-8"})],
                           chave_modulo="usuarios", classes_extra="mt-3")
    dlg.open()


# ==================== ABA 2: SESSÕES ATIVAS ====================

def _painel_sessoes(ator: str, refreshers=None):
    """Active sessions tab with per-row terminate actions.

    Aba Sessões Ativas: contagem, botão "Atualizar" (mantido cru — nenhuma
    variante padronizada é byte-idêntica ao `flat no-caps icon=refresh`) e
    grade de sessões com ações de encerramento padronizadas
    (`botao_icone`).
    """
    box = ui.column().classes("w-full gap-2")

    def refresh():
        box.clear()
        sessoes = gest.listar_sessoes_ativas()
        with box:
            with ui.row().classes("w-full justify-between items-center flex-wrap"):
                ui.label(f"{len(sessoes)} sessão(ões) ativa(s)").classes("text-subtitle1 font-bold")
                botao("Atualizar", icone="refresh", on_click=refresh,
                    variante="texto", chave_modulo="usuarios")
            if not sessoes:
                ui.label("Nenhuma sessão ativa no momento.").classes("text-grey-6")
            with ui.grid(columns="auto 1fr 0.9fr 1.2fr 1fr auto auto").classes(
                    "w-full bg-grey-1 rounded-lg px-3 py-2 text-caption font-bold text-grey-8"):
                for c in ("#", "Usuário", "Origem", "Login", "IP", "Dispositivo", "", ""):
                    ui.label(c)
            for sid, usuario, modulo, login, cookie, ip, disp, mac in sessoes:
                with ui.grid(columns="auto 1fr 0.9fr 1.2fr 1fr auto auto").classes(
                        "w-full border-b border-grey-2 px-3 py-1.5 items-center"):
                    with ui.column().classes("gap-0 leading-tight items-start"):
                        ui.label(str(sid)).classes("text-caption text-grey-6")
                        if mac and mac != "—":
                            ui.icon("fingerprint").classes("text-grey-5 text-xs") \
                                .tooltip(f"MAC: {mac}")
                    ui.label(usuario).classes("font-medium")
                    ui.label(modulo or "sistema").classes("text-caption")
                    ui.label((login or "").replace("T", " ")[:19]).classes("text-caption")
                    ui.label(ip).classes("text-caption font-mono")
                    ui.label(disp).classes("text-caption")
                    botao_icone("cancel_schedule_send", on_click=lambda _, u=usuario: (
                        gest.encerrar_todas_sessoes(ator, u), refresh()),
                        cor="deep-purple-8",
                        tooltip=f"Encerrar TODAS as sessões de {usuario}",
                        chave_modulo="usuarios")
                    botao_icone("logout", on_click=lambda _, i=sid: (
                        gest.encerrar_sessao(ator, i), refresh()),
                        cor="red-8", tooltip="Encerrar esta sessão",
                        chave_modulo="usuarios")

    refresh()
