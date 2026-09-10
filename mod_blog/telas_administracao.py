"""Administration panel for the Blog module.

Painel de administração do módulo Blog, seguindo o padrão de exibição dos
    demais módulos: card PADRÃO "Configurações de cores" (prévia ao vivo, no
    exemplo do Intranet /configuracoes) via `tema_modulo.bloco_aparencia`, um
    card "Configurações específicas" (tags HTML permitidas, limites de largura
    de imagem, texto do cabeçalho e o switch de diagramas Mermaid) e o card
dados (`painel_backup`). Cada card é recolhível (`card_admin`) com o rodapé
padrão de 2 botões: "Restaurar padrão" + "Aplicar" (exclusivos do card).

EN: Blog admin panel. Standard 'Configurações de cores' card (live preview,
following the Intranet example) + 'Configurações específicas' card + the
standard database backup card. Every card is collapsible with the standard
Restore/Apply footer.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from nicegui import ui
from mod_intranet import observabilidade
from mod_intranet.ui_comum import (campo_texto,
                                   card_admin, rodape_salvar_restaurar)
from mod_intranet.tema_modulo import (
    bloco_aparencia, ler_tema, salvar_tema, notificar)
from mod_blog.bd_manipulador import (
    audit_reg,
    set_config_local,
    tags_permitidas,
    _TAGS_PADRAO,
    _largura_imagem,
)


def mostrar_administracao(usuario_logado: str, pode_publicar: bool):
    """Renders the full blog administration panel (colors + specific config).

    Monta o painel de administração do Blog — visível apenas para
    administradores (`pode_publicar=True`):
      - "Configurações de cores": card PADRÃO (prévia ao vivo no exemplo do
        Intranet) com os campos de cores do padrão do intranet (cor geral do
        módulo, texto do módulo, fundo da página, títulos, fundo/texto dos
        cards e tamanho dos botões) — via `bloco_aparencia`;
      - "Configurações específicas": tags HTML permitidas, largura de
        imagem, texto do cabeçalho e o switch "Permitir diagramas Mermaid";
      - "Backup do banco de dados": card padrão (`painel_backup`).

    Cada card é recolhível (`card_admin`) com o rodapé padrão de 2 botões
    ("Restaurar padrão" + "Aplicar") exclusivos do card. A edição de
    nome/ícone/ativo do módulo NÃO existe aqui — é exclusiva do painel
    central /configuracoes (aba Módulo)."""
    if not pode_publicar:
        return
    tema = ler_tema("blog", cor_botao="#000000", cor_texto_botao="#FFFFFF",
                    texto_header="Comunique novidades para toda a equipe.")
    tema["_defaults"] = {
        "cor_botao": "",
        "cor_texto_botao": "",
        "cor_fundo": "",
        "cor_titulo": "#212121",
        "btn_tamanho": "medium",
        "texto_header": "Comunique novidades para toda a equipe.",
        "cor_fundo_card": "#FFFFFF",
        "cor_texto_card": "",
    }

    ui.colors(primary=tema["cor_botao"], accent=tema["cor_botao"])

    # ---- Card padrão "Configurações de cores" (prévia ao vivo) ----
    bloco_aparencia(usuario_logado, "blog", tema,
                    prefixo_auditoria="blog", com_texto_header=False)

    # ---- Configurações específicas ----
    with card_admin("Configurações específicas", icone="tune",
                    chave_modulo="blog", extra_classes="mt-2", grade=False):
        ui.label("Valem para todos os usuários imediatamente, sem restart.") \
            .classes("text-caption text-grey-6")
        inp_tags = campo_texto(
            "Tags HTML permitidas (separadas por vírgula)",
            valor=",".join(sorted(tags_permitidas())) or _TAGS_PADRAO,
            chave=None,
            props="outlined dense",
        )
        inp_tags.tooltip(
            "Lista das tags aceitas na sanitização NH3. "
            "Remover tags reduz riscos de XSS.")

        _img_min, _img_max = _largura_imagem()
        inp_largura = campo_texto(
            "Largura de imagem (min-max, ex. 200-400)",
            valor=f"{_img_min}-{_img_max}",
            chave=None,
            props="outlined dense",
        )
        inp_largura.tooltip(
            "Limites mínimo/máximo de largura, em px, "
            "para imagens nas postagens.")

        inp_texto = campo_texto(
            "Texto do cabeçalho",
            valor=tema["texto_header"],
            chave="blog_texto_header",
            props="outlined dense",
        )

        from mod_blog.bd_manipulador import obter_habilitar_mermaid
        sw_mermaid = ui.switch(
            "Permitir diagramas Mermaid (```mermaid) nas postagens",
            value=obter_habilitar_mermaid(),
        ).props("color=primary").classes("mt-1")
        sw_mermaid.tooltip(
            "Quando habilitado, blocos ```mermaid ... ``` nas postagens "
            "viram diagramas (flowchart, caso de uso etc.).")

        def salvar_especificas():
            """Saves the blog-specific settings and reloads after 1s.

            Grava tags HTML permitidas, largura de imagem, texto do
            cabeçalho e o estado do switch Mermaid; audita, notifica o
            resultado e recarrega a página
            após 1 segundo (aplicação sem restart). Falha notifica negativo."""
            try:
                set_config_local("blog_tags_permitidas",
                                 (inp_tags.value or "").strip())
                set_config_local("blog_largura_imagem",
                                 (inp_largura.value or "200-400").strip())
                set_config_local("blog_habilitar_mermaid",
                                 "1" if sw_mermaid.value else "0")
                salvar_tema("blog",
                            {"texto_header": (inp_texto.value or "").strip()})
                try:
                    audit_reg(usuario_logado, "blog", "configuracao",
                              "configurações específicas do blog salvas")
                except Exception:
                    pass
                notificar("Configurações específicas aplicadas — recarregando…",
                          type="positive")
                ui.timer(1.0, lambda: ui.navigate.reload(), once=True)
            except Exception:
                observabilidade.get_logger("blog").exception(
                    "Erro ao salvar configurações específicas do blog")
                notificar("Erro ao salvar configurações específicas",
                          type="negative")

        def restaurar_especificas():
            """Restores the blog-specific settings to the coded defaults.

            Restaura tags, largura de imagem, texto do cabeçalho e o switch
            Mermaid (`blog_habilitar_mermaid='1'`) para os padrões
            codificados; audita, notifica e recarrega após 1s."""
            try:
                set_config_local("blog_tags_permitidas", _TAGS_PADRAO)
                set_config_local("blog_largura_imagem", "200-400")
                set_config_local("blog_habilitar_mermaid", "1")
                salvar_tema("blog", {"texto_header": tema["_defaults"]["texto_header"]})
                try:
                    audit_reg(usuario_logado, "blog", "configuracao",
                              "configurações específicas do blog restauradas ao padrão")
                except Exception:
                    pass
                notificar("Padrões restaurados — recarregando…", type="positive")
                ui.timer(1.0, lambda: ui.navigate.reload(), once=True)
            except Exception:
                observabilidade.get_logger("blog").exception(
                    "Erro ao restaurar padrões específicos do blog")
                notificar("Erro ao restaurar padrões", type="negative")

        rodape_salvar_restaurar(salvar_especificas,
                                restaurar=restaurar_especificas,
                                chave_modulo="blog")

    from mod_intranet.rotinas import painel_backup
    painel_backup(usuario_logado, "blog")