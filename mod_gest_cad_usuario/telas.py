"""Tela de Gestão de Cadastro de Usuários — soft CRUD completo.

Barra superior fixa: abas | busca instantânea | botão Novo usuário.
Tudo no topo da página — sem precisar rolar a lista para acessar controles.
Acesso: administrador geral ou administrador do módulo 'usuarios'.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import math
import re
import unicodedata

from nicegui import ui

from mod_intranet import autenticacao
from mod_intranet import observabilidade
from mod_intranet.manipulador_bd import audit_log
from mod_intranet.aba_modulo import cabecalho
from mod_gest_cad_usuario import manipulador_bd as gest

log = observabilidade.get_logger("gest_cad_usuario")

OPCOES_PAPEL = {"": "— sem acesso —", "comum": "Comum", "administrador": "Administrador do módulo"}


def _norm(s):
    """Minúsculas, sem acentos e com pontuação vira espaço —
    buscar 'jose' acha 'José'; 'silva social' acha 'Silva-Social'."""
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return " ".join(re.findall(r"[a-z0-9]+", s))


def mostrar_tela(user_nome: str, perfil_global: str = ""):
    if not (perfil_global == "administrador_geral"
            or autenticacao.eh_admin_do_modulo(user_nome, "usuarios")):
        _acesso_negado()
        return
    # Aba "Excluídos" (com exclusão permanente LGPD): exclusiva do administrador geral
    eh_admin_geral = (perfil_global == "administrador_geral"
                      or autenticacao.perfil_global_de(user_nome) == "administrador_geral")

    ui.colors(primary="#00838F")

    # ================= TEMA (Aparência, prefixo usuarios_) =================
    from mod_intranet.conexao_bd import get_config
    def _tema_cab(chave, default):
        try:
            return (get_config(f"usuarios_{chave}", default) or "").strip() or default
        except Exception:
            return default

    t_cor_titulo = _tema_cab("cor_titulo", "#212121")
    t_cor_fundo_cab = _tema_cab("cor_fundo", "")
    t_texto_header = _tema_cab("texto_header",
                               "Cadastro de usuários, papéis e acessos por módulo (soft CRUD · LGPD).")

    estado_busca = {"valor": ""}
    refreshers = {}  # nome -> função de atualização (registrada por cada aba)

    def ao_digitar(e):
        estado_busca["valor"] = e.value or ""
        for chave in ("usuarios", "excluidos"):
            if chave in refreshers:
                try:
                    refreshers[chave]()
                except Exception as e:
                    log.exception(f"ao_digitar: falha ao atualizar aba '{chave}' | {e}")

    def novo_usuario():
        _dlg_novo(user_nome, lambda: [refreshers[k]() for k in
                                      ("usuarios", "excluidos") if k in refreshers])

    with ui.column().classes("w-full p-6 gap-4"):
        cabecalho("Gestão de Usuários",
                   t_texto_header,
                   cor_borda="#00838F", cor_titulo=t_cor_titulo, cor_fundo=t_cor_fundo_cab)

        # ===== BARRA SUPERIOR (linha única): abas à esquerda | busca larga + botão à direita =====
        with ui.row().classes("w-full items-center justify-between gap-4 flex-nowrap "
                              "bg-white rounded-lg shadow-sm px-3 py-1"):
            with ui.tabs().props("dense inline-label").classes("min-w-0 overflow-x-auto") as tabs:
                tab_users = ui.tab("Usuários", icon="people")
                tab_excluidos = ui.tab("Excluídos", icon="auto_delete") if eh_admin_geral else None
                tab_sessoes = ui.tab("Sessões Ativas", icon="wifi")
                tab_adm = ui.tab("Administração", icon="admin_panel_settings") if eh_admin_geral else None
            with ui.row().classes("items-center gap-2 flex-nowrap shrink-0").style("width:min(46%, 620px)"):
                ui.input(placeholder="🔍  Buscar usuário… (ignora acentos)", on_change=ao_digitar) \
                    .props("outlined dense clearable debounce='150'").classes("w-full grow min-w-[220px]") \
                    .tooltip("Filtra a lista de Usuários enquanto digita — sem acentos e maiúsculas")
                ui.button("Novo usuário", on_click=novo_usuario).props(
                    "unelevated color=primary no-caps icon=person_add").classes("shrink-0") \
                    .tooltip("Criar usuário definindo perfil e liberação por módulo")

        with ui.tab_panels(tabs, value=tab_users).classes("w-full bg-transparent"):
            with ui.tab_panel(tab_users):
                _painel_usuarios(user_nome, estado_busca, refreshers)
            if tab_excluidos is not None:
                with ui.tab_panel(tab_excluidos):
                    _painel_excluidos(user_nome, refreshers)
            with ui.tab_panel(tab_sessoes):
                _painel_sessoes(user_nome, refreshers)
            with ui.tab_panel(tab_adm):
                _painel_administracao(user_nome)


def _acesso_negado():
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
    local = {"pagina": 1, "por_pagina": 20, "situacao": "", "perfil": ""}
    container = ui.column().classes("w-full gap-2")

    SIT_OPCOES = {"": "Todas", "ativos": "Ativos", "bloqueados": "Bloqueados"}
    PERFIL_OPCOES = {"": "Todos"} | {p: p.replace("_", " ") for p in gest.PERFIS_GLOBAIS}

    def _filtrar():
        # excluídos (soft) vivem na aba própria; aqui só ativos/bloqueados
        linhas = [l for l in gest.listar_usuarios() if not l[8]]
        termo = _norm(estado.get("valor"))
        if termo:
            linhas = [l for l in linhas
                      if termo in _norm(l[1]) or termo in _norm(l[4])
                      or termo in _norm(l[2]) or termo in _norm(l[9])]
        sit = local["situacao"]
        if sit == "ativos":
            linhas = [l for l in linhas if l[3]]
        elif sit == "bloqueados":
            linhas = [l for l in linhas if not l[3]]
        if local["perfil"]:
            linhas = [l for l in linhas if l[2] == local["perfil"]]
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
                    ui.button(icon="restart_alt", on_click=lambda: (
                        local.update(pagina=1, situacao="", perfil=""), render())) \
                        .props("flat round dense size=sm color=grey-7") \
                        .tooltip("Limpar filtros")
                with ui.row().classes("items-center gap-1"):
                    ui.select({10: "10", 20: "20", 50: "50", 100: "100"},
                              value=por, label="Por página", on_change=lambda e: (
                                  local.update(por_pagina=int(e.value), pagina=1), render())) \
                        .props("outlined dense label").classes("min-w-[120px]")
                    ui.button(icon="chevron_left", on_click=lambda: (
                        local.update(pagina=max(1, pag - 1)), render())) \
                        .props("flat round dense").props(f"disabled={pag <= 1}")
                    ui.label(f"{ini + 1}–{ini + len(fatia)} de {total}"
                             f"  ·  pág. {pag}/{paginas} ({len(todas)} no total)") \
                        .classes("text-caption text-grey-8 min-w-[190px] text-center")
                    ui.button(icon="chevron_right", on_click=lambda: (
                        local.update(pagina=min(paginas, pag + 1)), render())) \
                        .props("flat round dense").props(f"disabled={pag >= paginas}")

            # ---- tabela ----
            cab = ("ID", "Tratamento / @login", "E-mail", "Telefone", "Perfil global",
                   "Situação", "Módulos:papel", "Ações")
            with ui.grid(columns="60px 1.1fr 1.4fr 1fr 1.2fr 0.8fr 1.6fr auto").classes(
                    "w-full bg-grey-1 rounded-t-lg px-3 py-2 text-caption font-bold text-grey-8"):
                for c in cab:
                    ui.label(c)
            if not fatia:
                ui.label("Nenhum usuário encontrado para os filtros atuais.").classes(
                    "text-grey-6 p-4")
            for row in fatia:
                uid, nome, perfil, ativo, email, fone, cadastro, acessos, deletado, completo, _motivo = row
                trat = (completo or "").strip() or nome
                with ui.grid(columns="60px 1.1fr 1.4fr 1fr 1.2fr 0.8fr 1.6fr auto").classes(
                        "w-full border-b border-grey-2 px-3 py-2 items-center hover:bg-blue-50/50"):
                    ui.label(str(uid)).classes("text-caption text-grey-6")
                    with ui.column().classes("gap-0 leading-tight"):
                        ui.label(trat).classes("font-medium")
                        ui.label("@" + nome).classes("text-caption text-grey-6")
                    ui.label(email or "—").classes("text-caption")
                    ui.label(fone or "—").classes("text-caption")
                    ui.badge(perfil.replace("_", " "), color={
                        "administrador_geral": "deep-purple-2",
                        "administrador_modulo": "blue-2",
                        "comum": "grey-3",
                    }.get(perfil, "grey-3")).props("outline dense")
                    with ui.row().classes("items-center gap-1 flex-nowrap"):
                        if deletado:
                            ui.badge("excluído (soft)", color="grey-4") \
                                .props("text-color=grey-10 outline dense") \
                                .tooltip("Exclusão lógica — pode ser restaurada")
                        elif ativo:
                            ui.badge("ativo", color="green-2").props("text-color=green-9 outline dense")
                        else:
                            ui.badge("bloqueado", color="red-2").props("text-color=red-9 outline dense")
                        if nome in pendentes and not deletado:
                            ui.badge("senha provisória", color="amber-3").props(
                                "text-color=amber-10 outline dense") \
                                .tooltip("Troca obrigatória ainda não realizada")
                    ui.label(acessos or "—").classes("text-caption text-grey-7")

                    with ui.row().classes("gap-1"):
                        ui.button(icon="edit", on_click=lambda _, n=nome: _dlg_editar(ator, n, render)) \
                            .props("flat round dense color=primary size=sm").tooltip("Editar dados e acessos")
                        ui.button(icon="devices_other",
                                  on_click=lambda _, n=nome: _dlg_sessoes(ator, n)) \
                            .props("flat round dense color=indigo-8 size=sm") \
                            .tooltip(f"Sessões: {sessoes_cnt.get(nome, 0)} ativa(s) + histórico recente")
                        if nome != ator:  # auto-ações bloqueadas no backend também
                            if not deletado and ativo:
                                ui.button(icon="vpn_key",
                                          on_click=lambda _, n=nome: _dlg_senha(ator, n)) \
                                    .props("flat round dense color=amber-8 size=sm") \
                                    .tooltip("Redefinir senha (provisória)")
                                ui.button(icon="block",
                                          on_click=lambda _, n=nome: (_gest_bloq(ator, n, True), render())) \
                                    .props("flat round dense color=orange-9 size=sm").tooltip("Bloquear")
                            else:
                                ui.button(icon="settings_backup_restore",
                                          on_click=lambda _, n=nome: (_gest_bloq(ator, n, False), render())) \
                                    .props("flat round dense color=green-8 size=sm") \
                                    .tooltip("Restaurar conta" +
                                             (" (remove exclusão lógica)" if deletado else ""))
                            ui.button(icon="delete_outline",
                                      on_click=lambda _, n=nome: _dlg_excluir(ator, n, render)) \
                                .props("flat round dense color=orange-9 size=sm") \
                                .tooltip("Excluir (lógico) — pede motivo e move para a aba Excluídos")
                        else:
                            ui.icon("person_pin").classes("text-grey-5 self-center") \
                                .tooltip("Sua própria conta — use 'Meu Perfil' (menu superior)")

    if refreshers is not None:
        refreshers["usuarios"] = render
    render()


def _gest_bloq(ator, nome, bloquear):
    ok, msg = gest.bloquear_usuario(ator, nome, bloquear)
    if not ok:
        log.error(f"_gest_bloq: falha ao {'bloquear' if bloquear else 'restaurar'} {nome} por {ator} | {msg}")
    ui.notify(msg, type="positive" if ok else "negative")


def _dlg_sessoes(ator, nome):
    """Diálogo de rastreabilidade do usuário: sessões ativas + histórico recente."""
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

    with ui.dialog() as dlg, ui.card().classes("w-[820px] max-h-[90vh]"):
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
                                ui.button(icon="logout", on_click=lambda _, i=sid: (
                                    gest.encerrar_sessao(ator, i), refresh_interno())) \
                                    .props("flat round dense color=red-8 size=sm") \
                                    .tooltip(f"Encerrar (entrada {login[:16]})")

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
                ui.button("Encerrar TODAS as sessões", on_click=lambda: (
                    gest.encerrar_todas_sessoes(ator, nome), refresh_interno())) \
                    .props("unelevated color=deep-purple-8 no-caps icon=sensors_off")
                ui.button("Fechar", on_click=dlg.close).props("flat no-caps")
    dlg.open()


def _dlg_novo(ator, refresh):
    with ui.dialog() as dlg, ui.card().classes("w-[560px] max-h-[90vh]"):
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
            senha = ui.input("Senha provisória * (mín. 6)", password=True, password_toggle_button=True) \
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
                    ui.notify(msg, type="negative")
                    return
                mudou, erros = _aplicar_acessos(ator, nome.value.strip(), selecoes)
                if erros:
                    ui.notify(f"Usuário criado, mas houve erros nos acessos: {' | '.join(erros)}",
                              type="warning")
                else:
                    ui.notify(f"Usuário '{nome.value.strip()}' criado" +
                              (f" com {mudou} acesso(s)" if mudou else ""), type="positive")
                dlg.close()
                refresh()

            with ui.row().classes("w-full justify-end gap-2 mt-3"):
                ui.button("Cancelar", on_click=dlg.close).props("flat no-caps")
                ui.button("Criar usuário", on_click=salvar).props("unelevated no-caps color=primary")
    dlg.open()


def _dlg_editar(ator, nome_atual, refresh):
    row = gest.obter_usuario(nome_atual)
    if not row:
        ui.notify("Usuário não encontrado", type="negative")
        return
    _, _, _, email, fone, perfil, _, _, _deletado, completo = row

    with ui.dialog() as dlg, ui.card().classes("w-[560px] max-h-[90vh]"):
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
                    ui.notify(" | ".join(erros), type="negative")
                else:
                    ui.notify("Usuário atualizado" +
                              (f" ({mudou} acesso(s) alterado(s))" if mudou else ""), type="positive")
                    dlg.close()
    refresh()


# ==================== ABA 3: ADMINISTRAÇÃO (exclusiva do admin geral) ====================

def _painel_administracao(ator: str):
    from mod_intranet.conexao_bd import get_config, set_config

    def _tema(chave, default):
        try:
            return (get_config(f"usuarios_{chave}", default) or "").strip() or default
        except Exception as e:
            log.warning(f"_tema: falha ao ler config '{chave}'; usando padrão | {e}")
            return default

    t_cor_botao = _tema("cor_botao", "#00838F")
    t_cor_txt_botao = _tema("cor_texto_botao", "#FFFFFF")
    t_cor_fundo = _tema("cor_fundo", "")
    t_cor_titulo = _tema("cor_titulo", "#212121")
    t_tamanho = _tema("btn_tamanho", "medium")
    t_texto_header = _tema("texto_header",
                           "Cadastro de usuários, papéis e acessos por módulo (soft CRUD · LGPD).")

    def _btn_style():
        st = ""
        if t_cor_botao:
            st += f"background-color:{t_cor_botao};"
        if t_cor_txt_botao:
            st += f"color:{t_cor_txt_botao};"
        return st

    ui.label("Administração — configurações da Gestão de Usuários").classes(
        "text-subtitle1 font-bold")
    ui.label("As cores de fundo/texto do botão também definem a cor primária desta tela.").classes(
        "text-caption text-grey-6 mb-2")

    ui.colors(primary=t_cor_botao, accent=t_cor_botao)

    with ui.card().classes("w-full max-w-3xl"):
        with ui.card_section().classes("gap-3"):
            ui.label("Aparência — temas dos botões desta tela").classes("text-subtitle2 text-grey-7")
            with ui.grid(columns=2).classes("w-full gap-3"):
                inp_cor_botao = ui.color_input(label="Cor dos botões", value=t_cor_botao)
                inp_cor_txt = ui.color_input(label="Cor do texto dos botões", value=t_cor_txt_botao)
                inp_cor_fundo = ui.color_input(label="Cor de fundo da página (vazio = herda)", value=t_cor_fundo)
                inp_cor_titulo = ui.color_input(label="Cor dos títulos", value=t_cor_titulo)

            sel_tamanho = ui.select(
                {0: "Pequeno", 1: "Médio", 2: "Grande"},
                label="Tamanho dos botões",
                value={"small": 0, "medium": 1, "large": 2}.get(t_tamanho, 1),
            ).props("outlined dense")

            with ui.separator().classes("my-2"):
                pass
            ui.label("Configurações específicas").classes("text-subtitle2 text-grey-7")
            inp_texto = ui.input("Texto do cabeçalho", value=t_texto_header) \
                .props("outlined dense").classes("w-full")
            inp_senha = ui.number(
                "Tamanho mínimo da senha (caracteres)",
                value=gest.senha_minima(), min=4, max=32, step=1,
            ).props("outlined dense").classes("w-64") \
                .tooltip("Aplicado ao criar usuário e redefinir senha.")

            _tamanhos = {0: "small", 1: "medium", 2: "large"}

            def aplicar_tema():
                try:
                    if t_cor_fundo:
                        ui.query(".q-page").style(f"background-color:{t_cor_fundo}")
                    for it in (inp_cor_titulo,):
                        if it.value:
                            it.style(f"color:{t_cor_titulo}")
                except Exception as e:
                    log.exception(f"aplicar_tema: falha ao aplicar tema | {e}")

            def salvar():
                set_config("usuarios_cor_botao", inp_cor_botao.value or "")
                set_config("usuarios_cor_texto_botao", inp_cor_txt.value or "")
                set_config("usuarios_cor_fundo", inp_cor_fundo.value or "")
                set_config("usuarios_cor_titulo", inp_cor_titulo.value or "")
                set_config("usuarios_btn_tamanho", _tamanhos[sel_tamanho.value])
                set_config("usuarios_texto_header", inp_texto.value or "")
                set_config("usuarios_senha_min", int(inp_senha.value or gest.senha_minima()))
                try:
                    audit_log(ator, "gest_cad_usuario", "configuracao",
                              "configurações do módulo salvas (inclui tamanho mínimo de senha)")
                except Exception:
                    pass
                ui.notify("Configurações salvas (valem sem reiniciar)", type="positive")
                ui.timer(0.1, lambda: ui.navigate.reload(), once=True)

            def resetar():
                for chave, valor in (("cor_botao", "#00838F"), ("cor_texto_botao", "#FFFFFF"),
                                     ("cor_fundo", ""), ("cor_titulo", "#212121"),
                                     ("btn_tamanho", "medium"),
                                     ("texto_header", "Cadastro de usuários, papéis e acessos por módulo (soft CRUD · LGPD)."),
                                     ("senha_min", 6)):
                    set_config(f"usuarios_{chave}", valor)
                try:
                    audit_log(ator, "gest_cad_usuario", "configuracao",
                              "configurações do módulo restauradas ao padrão")
                except Exception:
                    pass
                ui.notify("Padrões restaurados", type="positive")
                ui.timer(0.1, lambda: ui.navigate.reload(), once=True)

            with ui.row().classes("w-full justify-end gap-2 mt-2"):
                ui.button("Restaurar padrão", on_click=resetar).props("flat").style(_btn_style())
                ui.button("Salvar", icon="save", on_click=salvar).props("unelevated").style(_btn_style())


def _dlg_senha(ator, nome):
    with ui.dialog() as dlg, ui.card().classes("w-[380px]"):
        ui.label(f"Redefinir senha — {nome}").classes("text-h6")
        ui.label("O usuário receberá senha provisória e deverá trocá-la no próximo acesso.").classes(
            "text-caption text-orange-9 bg-orange-1 p-2 rounded")
        nova = ui.input("Nova senha provisória (mín. 6)", password=True,
                        password_toggle_button=True).props("outlined dense").classes("w-full")

        def salvar():
            ok, msg = gest.alterar_senha_admin(ator, nome, nova.value or "")
            if not ok:
                log.error(f"redefinir_senha: falha para {nome} por {ator} | {msg}")
            ui.notify(msg, type="positive" if ok else "negative")
            if ok:
                dlg.close()

        with ui.row().classes("w-full justify-end gap-2 mt-2"):
            ui.button("Cancelar", on_click=dlg.close).props("flat no-caps")
            ui.button("Redefinir", on_click=salvar).props("unelevated no-caps color=amber-8")
    dlg.open()


def _dlg_excluir(ator, nome, refresh):
    """Estágio 1: exclusão LÓGICA — pede o motivo e move para a lista de excluídos."""
    with ui.dialog() as dlg, ui.card().classes("w-[440px] border-2 border-orange-5"):
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
            ui.notify(msg, type="positive" if ok else "negative")
            if ok:
                dlg.close()
                refresh()

        with ui.row().classes("w-full justify-between mt-2"):
            ui.button("Cancelar", on_click=dlg.close).props("flat no-caps")
            ui.button("Excluir (lógico)", on_click=excluir) \
                .props("unelevated no-caps color=orange-9 icon=delete_outline")
    dlg.open()


def _dlg_excluir_definitivo(ator, nome, refresh):
    """Estágio 2 (apenas na lista de excluídos): remoção permanente LGPD."""
    with ui.dialog() as dlg, ui.card().classes("w-[440px] border-2 border-red-6"):
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
                ui.notify("Confirmação não corresponde", type="negative")
                return
            ok, msg = gest.excluir_usuario_definitivo(ator, nome)
            if not ok:
                log.error(f"excluir_definitivo: falha ao excluir {nome} por {ator} | {msg}")
            ui.notify(msg, type="positive" if ok else "negative")
            if ok:
                dlg.close()
                refresh()

        with ui.row().classes("w-full justify-between mt-2"):
            ui.button("Cancelar", on_click=dlg.close).props("flat no-caps")
            ui.button("Excluir definitivamente", on_click=excluir).props("unelevated no-caps color=negative icon=warning")
    dlg.open()


# ==================== ABA 1.5: EXCLUÍDOS (SOFT) ====================

def _painel_excluidos(ator: str, refreshers=None):
    box = ui.column().classes("w-full gap-2")

    def refresh():
        box.clear()
        linhas = [l for l in gest.listar_usuarios() if l[8]]  # deletado=1
        with box:
            with ui.row().classes("w-full justify-between items-center flex-wrap"):
                ui.label(f"{len(linhas)} usuário(s) na lista de excluídos").classes(
                    "text-subtitle1 font-bold")
                ui.button("Atualizar", on_click=refresh).props("flat no-caps icon=refresh")
            if not linhas:
                ui.label("Nenhum usuário excluído (lógico). Exclusões aparecem aqui "
                         "com o motivo registrado.").classes("text-grey-6 p-2")
                return
            with ui.grid(columns="60px 1.2fr 0.9fr 1.8fr 0.9fr auto").classes(
                    "w-full bg-grey-1 rounded-lg px-3 py-2 text-caption font-bold text-grey-8"):
                for c in ("ID", "Usuário", "Perfil", "Motivo da exclusão", "Cadastro", ""):
                    ui.label(c)
            for row in linhas:
                uid, nome, perfil, _ativo, _email, _fone, cadastro, _aces, _del, completo, motivo = row
                trat = (completo or "").strip() or nome
                with ui.grid(columns="60px 1.2fr 0.9fr 1.8fr 0.9fr auto").classes(
                        "w-full border-b border-grey-2 px-3 py-2 items-center hover:bg-red-50/40"):
                    ui.label(str(uid)).classes("text-caption text-grey-6")
                    with ui.column().classes("gap-0 leading-tight"):
                        ui.label(trat).classes("font-medium")
                        ui.label("@" + nome).classes("text-caption text-grey-6")
                    ui.badge((perfil or "comum").replace("_", " "), color="grey-3") \
                        .props("outline dense")
                    ui.label(motivo or "—").classes("text-caption text-grey-8")
                    ui.label(cadastro or "—").classes("text-caption text-grey-7")
                    with ui.row().classes("gap-1"):
                        ui.button(icon="settings_backup_restore",
                                  on_click=lambda _, n=nome: (
                                      _gest_bloq(ator, n, False), refresh())) \
                            .props("flat round dense color=green-8 size=sm") \
                            .tooltip("Restaurar conta (sai da lista de excluídos)")
                        ui.button(icon="delete_forever",
                                  on_click=lambda _, n=nome:
                                      _dlg_excluir_definitivo(ator, n, refresh)) \
                            .props("flat round dense color=red-8 size=sm") \
                            .tooltip("Excluir definitivamente (LGPD — irreversível)")

    if refreshers is not None:
        refreshers["excluidos"] = refresh
    refresh()


# ==================== ABA 2: SESSÕES ATIVAS ====================

def _painel_sessoes(ator: str, refreshers=None):
    box = ui.column().classes("w-full gap-2")

    def refresh():
        box.clear()
        sessoes = gest.listar_sessoes_ativas()
        with box:
            with ui.row().classes("w-full justify-between items-center flex-wrap"):
                ui.label(f"{len(sessoes)} sessão(ões) ativa(s)").classes("text-subtitle1 font-bold")
                ui.button("Atualizar", on_click=refresh).props("flat no-caps icon=refresh")
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
                    ui.button(icon="cancel_schedule_send", on_click=lambda _, u=usuario: (
                        gest.encerrar_todas_sessoes(ator, u), refresh())) \
                        .props("flat round dense color=deep-purple-8 size=sm") \
                        .tooltip(f"Encerrar TODAS as sessões de {usuario}")
                    ui.button(icon="logout", on_click=lambda _, i=sid: (
                        gest.encerrar_sessao(ator, i), refresh())) \
                        .props("flat round dense color=red-8 size=sm").tooltip("Encerrar esta sessão")

    refresh()
