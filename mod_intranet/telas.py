"""4-part system layout: header, drawer, content and footer.

Layout de 4 partes do sistema: header, drawer, conteúdo e footer.

Uso dentro de uma função @ui.page:

    from mod_intranet.layout_tela import pagina_restrita

    @ui.page("/blog")
    def page_blog():
        usuario = pagina_restrita("Blog", chave_modulo="blog")
        if not usuario:
            return
        # ... construir conteúdo
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from nicegui import ui, app

from mod_intranet import autenticacao
from mod_intranet import ui_comum
from mod_intranet.bd_conexao import get_config as _obter_config
from mod_intranet.tema_modulo import botao as _botao_tema
from mod_intranet.tema_modulo import notificar


def usuario_logado():
    """Retorna dict do usuário da sessão ou None."""
    return app.storage.user.get("usuario")


def pagina_restrita(titulo_modulo: str, chave_modulo: str = None):
    """Guard de autenticação + layout completo. Retorna dict do usuário ou None.

    Se não autenticado, redireciona para /login.
    """
    user = usuario_logado()
    if not user:
        ui.navigate.to("/login")
        return None

    # Revalida contra o BD a cada request: bloqueio/exclusão/renomeio derrubam a sessão viva
    linha_bd = autenticacao.usuario_existe(user.get("nome", ""))
    if not linha_bd or not linha_bd[2]:
        app.storage.user.clear()
        notificar("Sua sessão foi encerrada pelo administrador.", type="warning")
        ui.navigate.to("/login")
        return None

    # Sessão revogável: se o admin encerrou esta sessão no banco, o navegador cai
    hash_sessao = user.get("sessao")
    if hash_sessao:
        if not autenticacao.sessao_ativa(user["nome"], hash_sessao):
            app.storage.user.clear()
            notificar("Sua sessão foi encerrada pelo administrador.", type="warning")
            ui.navigate.to("/login")
            return None
    else:
        # Sessões anteriores à rastreabilidade não têm hash amarrado:
        # adota agora (nova linha com IP/UA deste acesso) e passa a ser revogável
        user["sessao"] = autenticacao.registrar_login(user["nome"], "sistema")
        app.storage.user["usuario"] = user

    papel_mod = autenticacao.papel_no_modulo(user["nome"], chave_modulo) if chave_modulo else None
    rotulo_perfil = f"{papel_mod.replace('_', ' ')} · neste módulo" if papel_mod \
        else user.get("perfil", "comum").replace("_", " ")

    # Bloqueio de acesso por módulo: impede navegação direta por URL de quem não
    # tem permissão (ex.: usuário comum acessando /auditoria). Check centralizado
    # aqui vale para todas as rotas que passam chave_modulo. Como passa por aqui
    # apenas usuários autenticados, o registro de 'acesso_negado' não polui com
    # bots/curl (tentativa de quem realmente tem conta).
    if chave_modulo and not autenticacao.validar_acesso_modulo(user["nome"], chave_modulo):
        try:
            from mod_intranet.bd_manipulador import audit_log
            audit_log(user["nome"], chave_modulo, "acesso_negado",
                      f"tentou abrir o módulo '{chave_modulo}' sem permissão")
        except Exception:
            pass
        notificar("Acesso negado a este módulo.", type="negative")
        ui.navigate.to("/")
        return None

    _montar_layout(user["nome"], rotulo_perfil, titulo_modulo, chave_modulo)

    if autenticacao.precisa_trocar_credenciais(user["nome"]):
        _dialogo_troca_credenciais(user["nome"])
    elif autenticacao.precisa_trocar_senha(user["nome"]):
        _dialogo_troca_senha(user["nome"])

    return user


def _montar_layout(nome_usuario: str, rotulo_perfil: str, titulo_modulo: str,
                    chave_modulo: str = None):
    """Builds the 4-part layout (header, drawer, content and footer).

    Monta o layout de 4 partes: header, drawer lateral, conteúdo e rodapé,
    aplicando cor principal, fundo, título do sistema e versões no rodapé.
    Espaçamentos via `.style("gap: …")` (visual 1:1, bug #2171/Ubuntu).
    """
    cores = _obter_cor_principal()
    ui.colors(primary=cores, secondary=ui_comum.CORES["cinza_escuro"],
              accent=cores)
    fundo = _obter_config('cor_fundo', ui_comum.CORES["fundo"]) \
        or ui_comum.CORES["fundo"]
    ui.query("body").classes("bg-grey-2")
    ui.query("body").style(f"background:{fundo}")
    try:
        # O Quasar pinta .q-page por cima do body: sem isso o cor_fundo
        # configurado nunca aparece na área do conteúdo.
        ui.query(".q-page").style(f"background-color:{fundo}")
    except Exception:
        pass
    titulo_sistema = _obter_config("titulo_sistema", "INTRANET") or "INTRANET"
    icone_sistema = (_obter_config("icone_sistema", "hub") or "hub").strip()
    # Título da ABA do navegador acompanha o nome configurado.
    # Exceção intencional de "sem JS direto": via `ui.run_javascript` (API
    # oficial do NiceGUI), pois `ui.page(title=...)` é fixo por rota.
    import json as _json
    ui.run_javascript(f"document.title = {_json.dumps(titulo_sistema)}")
    # favicon com cache-busting: ?v muda quando o .ico é trocado
    from mod_intranet.bd_conexao import favicon_versao
    ui.add_head_html(
        f'<link rel="icon" type="image/x-icon" href="/favicon.ico?v={favicon_versao()}">')
    # Título da página vem do cadastro de módulos (editável em Configurações)
    if chave_modulo:
        nome_cadastrado = autenticacao.nome_do_modulo(chave_modulo)
        if nome_cadastrado:
            titulo_modulo = nome_cadastrado

    # ===== HEADER (parte 1) =====
    with ui.header(elevated=True).classes("items-center justify-between bg-primary px-4"):
        with ui.row().classes("items-center").style("gap: 0.5rem"):
            ui_comum.botao_icone("menu", on_click=lambda: drawer.toggle(),
                                 variante="icone_branco")
            ui.icon(icone_sistema).classes("text-white")
            ui.label(titulo_sistema).classes("text-h6 text-white font-bold")
            ui.separator().props("vertical")
            ui.label(titulo_modulo).classes("text-subtitle1 text-white opacity-90")
        with ui.row().classes("items-center").style("gap: 0.5rem"):
            # Nome de TRATAMENTO clicável -> Meu Perfil (nome completo ou social)
            trat = autenticacao.nome_de_tratamento(nome_usuario)
            ui_comum.botao(trat, variante="texto_branco",
                           on_click=lambda: _dialogo_meu_perfil(nome_usuario),
                           tooltip="Meu Perfil — editar meus dados e senha")
            ui.badge(rotulo_perfil, color="primary-4").props("outline")
            ui_comum.botao_icone("logout", _logout, variante="icone_branco",
                                 tooltip="Sair")

    # ===== DRAWER/SIDEBAR (parte 2) =====
    # Por padrão o drawer abre FECHADO — o usuário abre via botão hambúrguer.
    with ui.left_drawer(bordered=True, elevated=False, value=False) as drawer:
        # ===== HOME: página inicial de boas-vindas =====
        with ui.item(on_click=lambda: ui.navigate.to("/")).classes(
                "rounded-lg mx-2 my-0.5 mt-2 hover:bg-blue-50 cursor-pointer"):
            with ui.item_section().props("avatar"):
                ui.icon("home").classes("text-primary")
            ui.item_label("Home")

        ui.separator()
        for chave, nome, icone, rota, ativa in autenticacao.modulos_do_usuario(nome_usuario):
            if ativa:
                with ui.item(on_click=lambda r=rota: ui.navigate.to(r)).classes(
                        "rounded-lg mx-2 my-0.5 hover:bg-blue-50 cursor-pointer"):
                    with ui.item_section().props("avatar"):
                        ui.icon(icone).classes("text-primary")
                    ui.item_label(nome)
            else:
                # Módulo removido/desativado com vínculo remanescente: alerta chamativo
                with ui.item(on_click=lambda n=nome: notificar(
                        f"⚠ '{n}' está indisponível/removido. Procure o administrador.",
                        type="warning", position="top")) \
                        .classes("rounded-lg mx-2 my-0.5 bg-orange-2 border border-orange-6 cursor-pointer"):
                    with ui.item_section().props("avatar"):
                        ui.icon("report_problem").classes("text-orange-9")
                    with ui.item_section():
                        ui.item_label(nome).classes("text-orange-10 font-bold")
                        ui.item_label("Módulo indisponível").classes("text-caption text-orange-9")

        # ===== SISTEMA: menu de Administração — exclusivo do administrador geral =====
        if autenticacao.perfil_global_de(nome_usuario) == "administrador_geral":
            ui.separator()
            if chave_modulo:
                _nome_mod_atual = autenticacao.nome_do_modulo(chave_modulo) or chave_modulo
                _admin_label = "Administração"
                _admin_tooltip = f"Configurações de {_nome_mod_atual}"
            else:
                _admin_label = "Administração (sistema)"
                _admin_tooltip = "Configurações gerais do sistema"
            with ui.item(on_click=lambda cm=chave_modulo: ui.navigate.to(
                    f"/admin/{cm}" if cm else "/configuracoes")).classes(
                    "rounded-lg mx-2 my-0.5 hover:bg-blue-50 cursor-pointer") \
                    .tooltip(_admin_tooltip):
                with ui.item_section().props("avatar"):
                    ui.icon("admin_panel_settings").classes("text-primary")
                ui.item_label(_admin_label)

            # Documentação MkDocs servida em /documentacao (main.py monta o site/)
            with ui.item(on_click=lambda: ui.navigate.to(
                    "/documentacao", new_tab=True)).classes(
                    "rounded-lg mx-2 my-0.5 hover:bg-blue-50 cursor-pointer") \
                    .tooltip("Abre a documentação técnica em nova aba"):
                with ui.item_section().props("avatar"):
                    ui.icon("menu_book").classes("text-primary")
                ui.item_label("Documentação")

    # ===== FOOTER (parte 4) =====
    with ui.footer().classes("bg-grey-8"):
        with ui.row().classes("w-full items-center justify-between px-4 py-1.5"):
            texto_rodape = _obter_config("texto_rodape", "uso interno") or "uso interno"
            ui.label(f"{titulo_sistema} Básica — {texto_rodape}").classes(
                "text-caption opacity-80")
            # Versões (esquerda -> direita): 1ª global do sistema, seguida da
            # parte do módulo atual mesclada (ocultando AAMMDD iguais).
            # Sempre exibido num rótulo único; o detalhe completo fica no tooltip.
            with ui.row().classes("items-center").style("gap: 0.5rem"):
                versao = _obter_versao()
                versao_mod = _obter_versao_modulo(chave_modulo) if chave_modulo else None
                resultado = _formatar_versao_rodape(versao, versao_mod)
                ui.label(resultado).classes("text-caption font-bold opacity-90").tooltip(
                    f"Sistema: v{versao}\nMódulo: v{versao_mod}" if versao_mod
                    else f"Sistema: v{versao}")


def _logout():
    user = usuario_logado()
    if user:
        autenticacao.registrar_logout(user["nome"], user.get("sessao"))
    app.storage.user.clear()
    ui.navigate.to("/login")


def _dialogo_meu_perfil(nome_usuario: str):
    """Autoatendimento: edita próprios dados pessoais e troca própria senha.

    Permissões e chaves de banco NÃO são editáveis aqui (README linha 60).
    """
    row = autenticacao._gest().obter_usuario(nome_usuario)
    email_atual = row[3] or "" if row else ""
    fone_atual = row[4] or "" if row else ""
    completo_atual = row[9] or "" if row else ""

    with ui_comum.dialogo_card(largura="w-[420px]", max_altura=False) as (dlg, card):
        ui.label("Meu Perfil").classes("text-h6 font-bold")
        ui.separator()

        ui.label("Dados pessoais").classes("text-subtitle2 text-grey-7")
        completo = ui_comum.campo_texto(
            "Nome completo (ou social)", valor=completo_atual,
            tooltip="Nome pelo qual você será tratado no sistema. "
                    "Pode ser seu nome social (Decreto 8.727/2016)")
        email = ui_comum.campo_texto("E-mail", valor=email_atual)
        fone = ui_comum.campo_texto("Telefone", valor=fone_atual)

        def salvar_dados():
            ok, msg = autenticacao.editar_meu_perfil(
                nome_usuario, email=email.value.strip(), fone=fone.value.strip(),
                nome_completo=completo.value.strip())
            notificar(msg, type="positive" if ok else "negative")
            if ok:
                ui.timer(0.1, lambda: ui.navigate.reload(), once=True)

        _botao_tema("Salvar dados", on_click=salvar_dados)

        ui.separator()
        ui.label("Trocar minha senha").classes("text-subtitle2 text-grey-7")
        atual = ui_comum.campo_texto("Senha atual", senha=True)
        nova = ui_comum.campo_texto("Nova senha (mín. 6)", senha=True)
        conf = ui_comum.campo_texto("Confirmar nova senha", senha=True)

        def salvar_senha():
            if nova.value != conf.value:
                notificar("As senhas não conferem", type="negative")
                return
            ok, msg = autenticacao.trocar_senha_propria(nome_usuario, atual.value or "", nova.value or "")
            notificar(msg, type="positive" if ok else "negative")
            if ok:
                atual.value = nova.value = conf.value = ""

        _botao_tema("Alterar senha", on_click=salvar_senha)

        ui.separator()
        with ui.row().classes("w-full justify-end"):
            _botao_tema("Fechar", variante="texto", on_click=dlg.close)
    dlg.open()


def _dialogo_troca_credenciais(nome_usuario: str):
    """Forces master's first-access combined change (username + password).

    Diálogo persistente do primeiro acesso do `master` nativo: exige definir
    um NOVO nome de usuário E uma nova senha. `persistent` (não fecha com
    ESC/clique fora) e fechamento somente após a troca bem-sucedida."""
    with ui_comum.dialogo_card(largura="w-96", max_altura=False) as (dlg, card):
        ui.label("Credenciais obrigatórias").classes("text-h6")
        ui.label(f"Bem-vindo(a), {autenticacao.nome_de_tratamento(nome_usuario)}. "
                 "Por segurança, defina um novo nome de usuário e uma nova "
                 "senha antes de continuar.").classes("text-body2 text-grey-7")
        novo_nome = ui_comum.campo_texto("Novo nome de usuário", props="")
        atual = ui_comum.campo_texto("Senha atual", senha=True, props="")
        nova = ui_comum.campo_texto("Nova senha (mín. 6)", senha=True, props="")
        conf = ui_comum.campo_texto("Confirmar nova senha", senha=True, props="")

        def confirmar():
            if (novo_nome.value or "").strip().lower() == "master":
                notificar("O novo nome de usuário deve ser diferente de 'master'.",
                          type="negative")
                return
            if nova.value != conf.value:
                notificar("As senhas não conferem", type="negative")
                return
            ok, msg, novo = autenticacao.trocar_credenciais_master(
                nome_usuario, novo_nome.value or "", atual.value or "", nova.value or "")
            notificar(msg, type="positive" if ok else "negative")
            if ok:
                app.storage.user["usuario"]["nome"] = novo
                dlg.close()
                ui.timer(0.2, lambda: ui.navigate.to("/"))

        _botao_tema("Salvar credenciais", on_click=confirmar,
                    extra_classes="w-full mt-2")
    # persistent: não fecha com ESC/clique fora — a troca é realmente obrigatória
    dlg.props("persistent")
    dlg.open()


def _dialogo_troca_senha(nome_usuario: str):
    """Forces the mandatory first-login password change dialog.

    Diálogo persistente de troca obrigatória de senha no primeiro acesso:
    `persistent` (não fecha com ESC/clique fora) e fechamento somente após
    a troca bem-sucedida. Título manual (`text-h6`, sem separador) para
    manter o visual original.
    """
    with ui_comum.dialogo_card(largura="w-96", max_altura=False) as (dlg, card):
        ui.label("Troca de senha obrigatória").classes("text-h6")
        ui.label(f"Bem-vindo(a), {autenticacao.nome_de_tratamento(nome_usuario)}. "
                 "Por segurança, defina uma nova senha antes de continuar.").classes(
            "text-body2 text-grey-7")
        atual = ui_comum.campo_texto("Senha atual", senha=True, props="")
        nova = ui_comum.campo_texto("Nova senha (mín. 6)", senha=True, props="")
        conf = ui_comum.campo_texto("Confirmar nova senha", senha=True, props="")

        def confirmar():
            if nova.value != conf.value:
                notificar("As senhas não conferem", type="negative")
                return
            ok, msg = autenticacao.trocar_senha_propria(nome_usuario, atual.value or "", nova.value or "")
            notificar(msg, type="positive" if ok else "negative")
            if ok:
                dlg.close()

        _botao_tema("Salvar nova senha", on_click=confirmar,
                    extra_classes="w-full mt-2")
    # persistent: não fecha com ESC/clique fora — a troca é realmente obrigatória
    dlg.props("persistent")
    dlg.open()


def _obter_cor_principal():
    """Reads the system primary color from config, falling back to the palette.

    Lê a cor principal do sistema em `tb_config` (chave `cor_principal`);
    em ausência do valor ou falha de conexão usa `ui_comum.CORES["primaria"]`.
    """
    from mod_intranet.bd_conexao import get_connection
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT valor FROM tb_config WHERE chave='cor_principal'")
        row = cur.fetchone()
        conn.close()
        return row[0] if row else ui_comum.CORES["primaria"]
    except Exception:
        return ui_comum.CORES["primaria"]


def _obter_versao():
    from mod_intranet.bd_conexao import get_connection
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT valor FROM tb_config WHERE chave='versao_sistema'")
        row = cur.fetchone()
        conn.close()
        return row[0] if row else "1.0"
    except Exception:
        return "1.0"


def _obter_versao_modulo(chave_modulo):
    """Versão individual do módulo (chave 'versao_modulo:<chave>' em tb_config).

    Formato 1.0.AAMMDD, no mesmo estilo da versão do sistema. Se o módulo ainda
    não tem versão registrada, retorna a padrão '1.0'.
    """
    from mod_intranet.bd_conexao import get_connection
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT valor FROM tb_config WHERE chave=?",
                    (f"versao_modulo:{chave_modulo}",))
        row = cur.fetchone()
        conn.close()
        return row[0] if row else "1.0"
    except Exception:
        return "1.0"


def _parse_versao(v: str):
    """Parse 'X.Y.AAMMDD' ou 'X.Y' -> (major, minor, patch)."""
    parts = v.split(".")
    major = int(parts[0]) if parts else 1
    minor = int(parts[1]) if len(parts) > 1 else 0
    patch = parts[2] if len(parts) > 2 else ""
    return major, minor, patch


def _mesclar_patch(patch_sis: str, patch_mod: str) -> str:
    """Mescla patches AAMMDD conforme regras: oculta ano/mês/dia iguais."""
    if not patch_sis or not patch_mod or patch_sis == patch_mod:
        return patch_sis
    aa1, mm1, dd1 = patch_sis[:2], patch_sis[2:4], patch_sis[4:6]
    aa2, mm2, dd2 = patch_mod[:2], patch_mod[2:4], patch_mod[4:6]
    if aa1 == aa2:
        if mm1 == mm2:
            return f"{patch_sis}.{dd2}"
        return f"{patch_sis}.{mm2}{dd2}"
    return f"{patch_sis}.{patch_mod}"


def _formatar_versao_rodape(versao_sistema: str, versao_modulo: str = None):
    """Retorna sempre uma única string com a versão mesclada para exibição.

    Formato: v{major}.{minor}.{patch_sis}[.{parte_mod}]
    - Sem módulo: v{versao_sistema}
    - major.minor iguais: mescla ocultando AAMMDD iguais (v1.0.260829.28,
      v1.0.260829.0717, v1.0.260828.250412)
    - major.minor diferentes: mostra ambos separados por ' · '
    """
    if not versao_modulo:
        return f"v{versao_sistema}"

    major_sis, minor_sis, patch_sis = _parse_versao(versao_sistema)
    major_mod, minor_mod, patch_mod = _parse_versao(versao_modulo)

    if major_sis != major_mod or minor_sis != minor_mod:
        return f"v{versao_sistema} · v{versao_modulo}"

    base = f"v{major_sis}.{minor_sis}"
    if patch_sis and patch_mod:
        mesclado = _mesclar_patch(patch_sis, patch_mod)
        return f"{base}.{mesclado}"
    if patch_sis or patch_mod:
        return f"{base}.{patch_sis or patch_mod}"
    return base
