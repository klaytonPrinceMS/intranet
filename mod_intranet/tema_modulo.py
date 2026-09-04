"""Helper central de tema/aparência dos módulos.

Padroniza as variáveis de configuração de aparência usadas por TODOS os
módulos, eliminando a duplicação de código e a variação de nomes entre telas.
Cada módulo lê/grava suas chaves em `tb_config` central com um PREFIXO próprio
(mapeado por `PREFIXO_POR_CHAVE`), e os 6 campos são sempre:

    <prefixo>_cor_botao        cor de fundo dos botões
    <prefixo>_cor_texto_botao  cor do texto dos botões
    <prefixo>_cor_fundo        cor de fundo da página (vazio = herda)
    <prefixo>_cor_titulo       cor dos títulos
    <prefixo>_btn_tamanho      small | medium | large
    <prefixo>_texto_header     subtítulo do cabeçalho

Todos os botões de um módulo usam SEMPRE a mesma cor (não há variação por
botão). A aplicação é imediata (sem restart), pois é lida via `get_config` a
cada renderização da tela.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


# Mapeia a CHAVE do módulo (usada em tb_modulos/rotas) para o PREFIXO de
# configuração em tb_config central. Mantém compatibilidade com o padrão
# documentado na Fase 1 do PLANO.md.
PREFIXO_POR_CHAVE = {
    "blog": "blog",
    "usuarios": "usuarios",
    "auditoria": "auditoria",
    "editar_pdf": "editpdf",
    "empenhos": "empenhos",
    "solicita_impressao": "solicita_impressao",
}


def prefixo_da_chave(chave_modulo: str) -> str:
    return PREFIXO_POR_CHAVE.get(chave_modulo, chave_modulo)


def _cfg(chave, default):
    from mod_intranet.conexao_bd import get_config
    try:
        return (get_config(chave, default) or "").strip() or default
    except Exception:
        return default


def ler_tema(chave_modulo: str, cor_botao="#1565C0", cor_texto_botao="#FFFFFF",
             cor_fundo="", cor_titulo="#212121", btn_tamanho="medium",
             texto_header=""):
    """Lê as 6 chaves de aparência do módulo em tb_config central.

    Returns dict com chaves: cor_botao, cor_texto_botao, cor_fundo,
    cor_titulo, btn_tamanho, texto_header.
    """
    p = prefixo_da_chave(chave_modulo)
    return {
        "cor_botao": _cfg(f"{p}_cor_botao", cor_botao),
        "cor_texto_botao": _cfg(f"{p}_cor_texto_botao", cor_texto_botao),
        "cor_fundo": _cfg(f"{p}_cor_fundo", cor_fundo),
        "cor_titulo": _cfg(f"{p}_cor_titulo", cor_titulo),
        "btn_tamanho": _cfg(f"{p}_btn_tamanho", btn_tamanho),
        "texto_header": _cfg(f"{p}_texto_header", texto_header),
    }


def salvar_tema(chave_modulo: str, valores: dict) -> None:
    """Grava as 6 chaves de aparência do módulo em tb_config central.

    `valores` deve conter as chaves cor_botao/cor_texto_botao/cor_fundo/
    cor_titulo/btn_tamanho/texto_header. Aplica sem restart.
    """
    from mod_intranet.conexao_bd import set_config
    p = prefixo_da_chave(chave_modulo)
    mapa = {
        "cor_botao": f"{p}_cor_botao",
        "cor_texto_botao": f"{p}_cor_texto_botao",
        "cor_fundo": f"{p}_cor_fundo",
        "cor_titulo": f"{p}_cor_titulo",
        "btn_tamanho": f"{p}_btn_tamanho",
        "texto_header": f"{p}_texto_header",
    }
    for campo, chave in mapa.items():
        if campo in valores:
            set_config(chave, valores[campo] or "")


def restaurar_tema(chave_modulo: str, defaults: dict) -> None:
    """Restaura os padrões das 6 chaves de aparência do módulo."""
    salvar_tema(chave_modulo, defaults)


def btn_cls(tamanho: str = "medium") -> str:
    """Classes CSS de largura dos botões por tamanho (padrão visual único)."""
    if tamanho == "small":
        return "min-w-[140px] text-sm"
    if tamanho == "large":
        return "min-w-[220px] text-lg"
    return "min-w-[180px]"


def btn_style(cor_botao: str = "", cor_texto_botao: str = "") -> str:
    """Estilo inline dos botões: fundo + cor do texto (sempre os mesmos)."""
    st = ""
    if cor_botao:
        st += f"background-color:{cor_botao};"
    if cor_texto_botao:
        st += f"color:{cor_texto_botao};"
    return st


def bloco_aparencia(usuario_logado, chave_modulo, tema: dict,
                    ao_salvar_descricao="configurações de aparência salvas",
                    prefixo_auditoria="intranet"):
    """Renderiza o cupê padronizado 'Aparência' na aba Administração do módulo.

    Recebe o `tema` (dict de `ler_tema`), cria os campos cor_botao,
    cor_texto_botao, cor_fundo, cor_titulo, btn_tamanho e texto_header e
    devolve um callable `salvar` que grava tudo em `tb_config` central e audita.
    """
    from nicegui import ui
    from mod_intranet.manipulador_bd import audit_log

    with ui.expansion("Aparência", icon="palette").classes("w-full"):
        with ui.grid(columns=2).classes("w-full gap-3 max-sm:grid-cols-1"):
            inp_cor_botao = ui.color_input(
                "Cor dos botões", value=tema.get("cor_botao", "")).props(
                "outlined dense").classes("w-full")
            inp_cor_txt = ui.color_input(
                "Cor do texto dos botões",
                value=tema.get("cor_texto_botao", "")).props(
                "outlined dense").classes("w-full")
            inp_cor_fundo = ui.color_input(
                "Cor de fundo da página (vazio = herda)",
                value=tema.get("cor_fundo", "")).props(
                "outlined dense").classes("w-full")
            inp_cor_titulo = ui.color_input(
                "Cor dos títulos", value=tema.get("cor_titulo", "")).props(
                "outlined dense").classes("w-full")
        sel_tamanho = ui.select(
            {0: "Pequeno", 1: "Médio", 2: "Grande"},
            label="Tamanho dos botões",
            value={"small": 0, "medium": 1, "large": 2}.get(
                tema.get("btn_tamanho", "medium"), 1)).props(
            "outlined dense").classes("w-full")
        inp_texto_header = ui.input(
            "Texto do cabeçalho", value=tema.get("texto_header", "")).props(
            "outlined dense").classes("w-full")
        _tamanhos = {0: "small", 1: "medium", 2: "large"}

        valores = {}

        def salvar():
            valores.update({
                "cor_botao": inp_cor_botao.value or "",
                "cor_texto_botao": inp_cor_txt.value or "",
                "cor_fundo": inp_cor_fundo.value or "",
                "cor_titulo": inp_cor_titulo.value or "",
                "btn_tamanho": _tamanhos[sel_tamanho.value],
                "texto_header": inp_texto_header.value or "",
            })
            salvar_tema(chave_modulo, valores)
            try:
                audit_log(usuario_logado, prefixo_auditoria, "configuracao",
                          ao_salvar_descricao)
            except Exception:
                pass
            ui.notify("Aparência salva (vale sem reiniciar)", type="positive")
            ui.timer(0.1, lambda: ui.navigate.reload(), once=True)

        with ui.row().classes("w-full justify-end gap-2 mt-2"):
            def restaurar():
                defaults = tema.get("_defaults", {})
                if defaults:
                    restaurar_tema(chave_modulo, defaults)
                ui.timer(0.1, lambda: ui.navigate.reload(), once=True)

            ui.button("Restaurar padrão", on_click=restaurar).props("flat")
            ui.button("Salvar", icon="save", on_click=salvar).props(
                "unelevated").classes(btn_cls(tema.get("btn_tamanho", "medium")))

    return salvar


def campo_modulo(usuario_logado, chave_modulo, nome_atual=None, icone_atual=None,
                 ativo_atual=None):
    """Cupê 'Edição do módulo' na aba Administração: nome, ícone e status.

    Permite ao administrador do módulo alterar nome de exibição, ícone e
    status (ativo/desativado) registrados em `tb_modulos` — hoje só disponível
    no painel central `/configuracoes`. Se os valores não forem informados,
    são carregados automaticamente de `tb_modulos`.
    """
    from nicegui import ui
    from mod_intranet import autenticacao
    from mod_intranet.manipulador_bd import audit_log
    from mod_intranet.conexao_bd import get_connection

    if nome_atual is None or icone_atual is None or ativo_atual is None:
        try:
            c = get_connection()
            row = c.execute("SELECT nome, icone, ativo FROM tb_modulos WHERE chave=?",
                            (chave_modulo,)).fetchone()
            c.close()
            if row:
                if nome_atual is None:
                    nome_atual = row[0] or chave_modulo
                if icone_atual is None:
                    icone_atual = row[1] or "extension"
                if ativo_atual is None:
                    ativo_atual = bool(row[2])
        except Exception:
            pass
    nome_atual = nome_atual or chave_modulo
    icone_atual = icone_atual or "extension"
    ativo_atual = bool(ativo_atual)

    with ui.expansion("Edição do módulo", icon="settings_applications").classes("w-full"):
        inp_nome = ui.input("Nome de exibição do módulo",
                            value=nome_atual or "").props(
            "outlined dense").classes("w-full")
        inp_icone = ui.input("Ícone (Material Icons)",
                             value=icone_atual or "extension").props(
            "outlined dense").classes("w-full") \
            .tooltip("Nome do ícone Material, ex.: article, folder_open, print")
        sw_ativo = ui.switch("Módulo ativo (visível para os usuários)",
                             value=bool(ativo_atual))

        def salvar():
            from mod_intranet.conexao_bd import get_connection
            autenticacao.set_modulo_ativo(usuario_logado, chave_modulo,
                                          bool(sw_ativo.value))
            try:
                c = get_connection()
                c.execute(
                    "UPDATE tb_modulos SET nome=?, icone=? WHERE chave=?",
                    ((inp_nome.value or "").strip() or chave_modulo,
                     (inp_icone.value or "extension").strip(), chave_modulo))
                c.commit(); c.close()
            except Exception:
                pass
            try:
                audit_log(usuario_logado, "intranet", "editar_modulo",
                          f"{chave_modulo}: nome='{inp_nome.value.strip()}' "
                          f"icone='{inp_icone.value.strip()}' "
                          f"ativo={int(bool(sw_ativo.value))}")
            except Exception:
                pass
            ui.notify("Módulo atualizado", type="positive")
            ui.timer(0.1, lambda: ui.navigate.reload(), once=True)

        with ui.row().classes("w-full justify-end mt-2"):
            ui.button("Salvar módulo", icon="save", on_click=salvar).props(
                "unelevated").classes(btn_cls())
    return salvar
