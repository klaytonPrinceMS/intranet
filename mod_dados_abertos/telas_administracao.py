"""EN: Open data admin panel (route /admin/dados_abertos).

PT-BR: Painel de administração do módulo Dados Abertos (rota
/admin/dados_abertos).

Duas coisas se administram aqui, e as duas são sobre a FONTE, não sobre o
módulo:

1. **Aparência** — as 6 chaves de tema, pelo bloco padrão do sistema.

2. **O registro de fontes** — quais conjuntos de dados públicos aparecem na
   tela principal (`tb_fontes`). Registrar uma fonte aqui cria o card; o
   leitor dela é que decide o que o card mostra.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from nicegui import ui

from mod_intranet import observabilidade
from mod_intranet.tema_modulo import ler_tema, notificar, bloco_aparencia
from mod_intranet.ui_comum import card_admin, botao
from mod_dados_abertos import bd_manipulador as dad

log = observabilidade.get_logger("dados_abertos")

TIPOS_UNIDADE = ("secretaria", "setor", "subsetor")


def mostrar_administracao(usuario_logado: str = ""):
    """EN: Renders /admin/dados_abertos (appearance + source register).

    PT-BR: Renderiza /admin/dados_abertos (aparência + registro de fontes).
    """
    try:
        tema = ler_tema(
            "dados_abertos", cor_botao="#000000", cor_texto_botao="#FFFFFF",
            texto_header="Dados abertos publicados pela prefeitura.")
        tema["_defaults"] = {
            "cor_botao": "",
            "cor_texto_botao": "",
            "cor_fundo": "",
            "cor_titulo": "#212121",
            "btn_tamanho": "medium",
            "texto_header": "Dados abertos publicados pela prefeitura.",
            "cor_fundo_card": "#FFFFFF",
            "cor_texto_card": "",
        }
        ui.colors(primary=tema["cor_botao"])
        bloco_aparencia(usuario_logado, "dados_abertos", tema,
                        prefixo_auditoria="dados_abertos",
                        com_texto_header=True)

        _card_fontes(usuario_logado)
    except Exception as e:
        log.exception(f"mostrar_administracao: falha no painel | {e}")
        notificar("Erro ao carregar a administração de Dados Abertos.",
                  tipo="error")


def _card_fontes(usuario_logado: str):
    """EN: The source register — list, add and toggle.

    PT-BR: O registro de fontes — listar, incluir e ligar/desligar.
    """
    with card_admin("Conjuntos de dados disponíveis", icone="public",
                    chave_modulo="dados_abertos", grade=False):
        ui.label(
            "Cada fonte registrada vira um card na tela /dados-abertos. "
            "Registrar não cria o leitor: o card mostra 'leitura ainda não "
            "implementada' até existir."
        ).classes("text-caption text-grey-6")

        lista = ui.column().classes("w-full gap-2")

        def _render():
            lista.clear()
            with lista:
                fontes = dad.listar_fontes(somente_ativas=False)
                if not fontes:
                    ui.label("Nenhuma fonte registrada.").classes(
                        "text-grey-6 italic")
                    return
                for fonte in fontes:
                    _linha_fonte(fonte, _render)

        _render()

        ui.separator().classes("my-2")
        ui.label("Incluir nova fonte").classes(
            "text-subtitle2 font-bold").style("margin-top: 8px")
        campo_nome = ui.input("Nome da fonte").props(
            "outlined dense").classes("w-full").props(
            "data-testid=dados-abertos-fonte-nome")

        def _adicionar():
            nome = (campo_nome.value or "").strip()
            if len(nome) < 3:
                notificar("Informe o nome da fonte (mínimo 3 letras).",
                          tipo="erro")
                return
            chave = _chave_de(nome)
            if _chave_existe(chave):
                notificar("Já existe uma fonte com esse nome.", tipo="erro")
                return
            if dad.registrar_fonte(usuario_logado, chave, nome):
                notificar(f"Fonte '{nome}' registrada.", tipo="positive")
                campo_nome.value = ""
                _render()
            else:
                notificar("Não foi possível registrar a fonte.", tipo="erro")

        botao("Registrar fonte", icone="add", on_click=_adicionar,
              chave_modulo="dados_abertos") \
            .props("data-testid=dados-abertos-fonte-registrar")
    return lista


def _linha_fonte(fonte: dict, ao_mudar):
    """EN: One register row — name, state and the on/off toggle.

    PT-BR: Uma linha do registro — nome, estado e o botão liga/desliga.
    """
    chave = fonte.get("chave") or ""
    with ui.row().classes("w-full items-center justify-between no-wrap").style(
            "gap: 8px; border-bottom: 1px solid #e2e8f0; padding: 6px 0"):
        with ui.column().classes("grow").style("gap: 0; min-width: 0"):
            ui.label(fonte.get("nome") or chave).classes(
                "text-body2 font-bold").style("min-width: 0")
            ui.label(f"{chave} · {fonte.get('descricao') or 'sem descrição'}").classes(
                "text-caption text-grey-6").style("min-width: 0")

        def _alternar():
            if not dad.alternar_fonte_ativa("sistema", chave,
                                             not fonte.get("ativo")):
                notificar("Não foi possível mudar o estado da fonte.",
                          tipo="erro")
            ao_mudar()

        botao("Desligar" if fonte.get("ativo") else "Ligar",
              variante="secundario", on_click=_alternar,
              chave_modulo="dados_abertos")


def _chave_de(nome: str) -> str:
    """EN: Slug of a source name ('Secretaria X' -> 'secretaria_x').

    PT-BR: Chave de uma fonte a partir do nome.
    """
    import unicodedata
    try:
        txt = unicodedata.normalize("NFKD", str(nome or "")).encode(
            "ascii", "ignore").decode().lower()
        return "_".join("".join(c if c.isalnum() else " "
                                for c in txt).split()) or "fonte"
    except Exception as e:
        log.warning(f"_chave_de: falha ({e})")
        return "fonte"


def _chave_existe(chave: str) -> bool:
    """EN: Whether the key is already registered.

    PT-BR: Se a chave já está registrada.
    """
    try:
        return any(f.get("chave") == chave
                   for f in (dad.listar_fontes(somente_ativas=False) or []))
    except Exception as e:
        log.warning(f"_chave_existe: falha ({e})")
        return False

