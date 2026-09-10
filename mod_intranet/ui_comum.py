"""Central factory for shared UI components (buttons, dialogs, footers).

Fábrica central de componentes de UI compartilhados por todas as telas:
paleta semântica de cores (`CORES`), fábrica de botões (`BotaoFabrica` +
`botao`/`botao_icone`), moldura de diálogo (`Dialogo` + `dialogo_card`),
rodapés (`rodape_dialogo`, `rodape_salvar_restaurar`), campos de
configuração (`CampoBase`/`CampoCor`/`CampoTexto`/`CampoSelecao` +
`campo_cor`/`campo_texto`/`campo_selecao`) e card de configuração
(`Cartao` + `card_config`). As FUNÇÕES são wrappers finos que delegam às
CLASSES correspondentes — assinaturas e saída preservadas byte-identicamente
para as centenas de chamadas existentes; código novo pode usar as classes
diretamente. Unifica `tema_modulo.botao` (variantes de tema) com as
variantes fixas do painel de configurações, para que o mesmo dado tenha a
mesma aparência em qualquer lugar.

É o padrão oficial de componentes para os módulos `mod_*`: importe de
`mod_intranet.ui_comum` em vez de criar `ui.button` crus ou repetir hexes
soltos (`#C62828`, `#EF6C00`, `#2E7D32`…) nas telas.
"""
import sys
import os
from contextlib import contextmanager, ExitStack

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from mod_intranet.tema_modulo import notificar


def _log():
    """Returns the loguru logger bound to the core module ("intranet").

    Logger loguru vinculado ao módulo núcleo (`intranet`), no padrão
    `observabilidade._FMT` (`{module}:{function}:{line}`). Usado nos blocos
    `except` das fábricas de UI para registrar falhas sem derrubar a
    renderização da tela (fail-soft).
    """
    from mod_intranet import observabilidade
    return observabilidade.get_logger("intranet")


# Paleta semântica única do sistema: use `CORES["perigo"]`, `CORES["alerta"]`
# etc. em vez de hexes soltos repetidos nas telas (ver docs/convencoes_codigo).
CORES = {
    "primaria": "#1565C0",
    "sucesso": "#2E7D32",
    "alerta": "#EF6C00",
    "perigo": "#C62828",
    "info": "#00838F",
    "neutro": "#455A64",
    "destaque": "#6A1B9A",
    "cinza_escuro": "#37474F",
    "titulo": "#212121",
    "branco": "#FFFFFF",
    "fundo": "#EEEEEE",
}


class BotaoFabrica:
    """Factory of standardized buttons (module theme or fixed variant).

    Fábrica de botões padronizados: encapsula a leitura do tema do módulo
    (`tema_modulo.ler_tema`) e a montagem de props/classes/estilo por
    variante — `primario` (alias `solido`), `secundario` (alias
    `contorno`), `texto` e `icone` usam o tema; `neutro`, `restaurar`,
    `restaurar_fill`, `perigo`, `icone_branco` e `texto_branco` são 100%
    props fixas (o tema NÃO é lido para elas — economia de consultas por
    render). Com `cor` informado, o tema também NÃO é lido nem para as
    variantes tematizadas (nenhuma saída o utiliza: estilo limpo, sem
    `btn_cls`, cor via props `color=`). `cor` sobrescreve a cor da
    variante mantendo formato/tamanho; `extra_classes` soma classes;
    `compacto=True` remove `size=md`, `btn_cls` e sombra (visual de rodapé
    de diálogo). `no_caps=False` remove o token `no-caps` (para módulos
    com botões UPPERCASE herdados do Quasar). Variante
    inválida levanta `ValueError` (erro de programação — falha rápida
    intencional). Falha ao ler o tema registra warning no loguru e usa os
    padrões; falha ao montar o elemento registra exception e retorna
    `None` (fail-soft).
    """

    ALIAS = {"solido": "primario", "contorno": "secundario"}
    TEMATIZADAS = ("primario", "secundario", "texto", "icone")

    def __init__(self, chave_modulo="intranet"):
        self.chave_modulo = chave_modulo

    def criar(self, rotulo=None, *, variante="primario", icone=None,
              on_click=None, tooltip=None, cor=None, extra_classes="",
              compacto=False, no_caps=True):
        """Builds one standardized button; returns the `ui.button` (or `None`).

        Aplica a sequência fixa de montagem: props da variante → estilo do
        tema (quando aplicável) → classes (`size`, sombra,
        `extra_classes`) → tooltip. Com `cor`, sobrescreve `color=`/
        `text-color=` nas props e zera o estilo. Retorna o `ui.button`
        criado ou `None` em falha de montagem (fail-soft).
        """
        from nicegui import ui
        from mod_intranet import tema_modulo
        v = self.ALIAS.get(variante, variante)
        if v in self.TEMATIZADAS and not cor:
            try:
                tema = tema_modulo.ler_tema(self.chave_modulo)
            except Exception as e:
                _log().warning(f"botao: tema indisponível para "
                               f"'{self.chave_modulo}', usando padrões: {e}")
                tema = {}
            cor_tema = tema.get("cor_botao", "#1565C0") or "#1565C0"
            txt_tema = tema.get("cor_texto_botao", "#FFFFFF") or "#FFFFFF"
            tamanho = tema.get("btn_tamanho", "medium") or "medium"
        else:
            tema, cor_tema, txt_tema, tamanho = {}, "", "", "medium"
        if v == "primario":
            if compacto:
                props, classes = "unelevated no-caps", ""
            else:
                props, classes = "unelevated no-caps size=md", "shadow-sm"
            estilo = tema_modulo.btn_style(cor_tema, txt_tema)
            if not compacto and not cor:
                classes = f"{classes} {tema_modulo.btn_cls(tamanho)}"
        elif v == "secundario":
            props, classes = "outline no-caps", ""
            estilo = f"color:{cor_tema};border-color:{cor_tema};"
        elif v == "texto":
            props, classes = "flat no-caps", ""
            estilo = f"color:{cor_tema};"
        elif v == "neutro":
            props, classes, estilo = \
                "flat no-caps size=md text-color=grey-8", "", ""
        elif v == "restaurar":
            props, classes, estilo = (
                "outline no-caps size=md color=warning text-color=amber-10",
                "", "")
        elif v == "restaurar_fill":
            props, classes, estilo = (
                "unelevated no-caps size=md color=warning text-color=white",
                "shadow-sm", "")
        elif v == "perigo":
            props, classes, estilo = (
                "outline no-caps size=md color=negative text-color=negative",
                "", "")
        elif v == "icone":
            props, classes = "flat round dense size=sm", ""
            estilo = f"color:{cor_tema};"
        elif v == "icone_branco":
            props, classes, estilo = "flat round color=white", "", ""
        elif v == "texto_branco":
            props, classes, estilo = "flat dense color=white no-caps", "", ""
        else:
            raise ValueError(f"variante de botão inválida: {variante!r}")
        if not no_caps:
            props = " ".join(p for p in props.split() if p != "no-caps")
        classes = f"{classes} {extra_classes}".strip()
        if cor:
            partes = props.split()
            props = " ".join(
                f"color={cor}" if p.startswith("color=") else
                f"text-color={cor}" if p.startswith("text-color=") else p
                for p in partes)
            if not any(p.startswith("color=") for p in partes):
                props += f" color={cor}"
            estilo = ""
        try:
            btn = ui.button(rotulo, icon=icone, on_click=on_click).props(props)
            if estilo:
                btn.style(estilo)
            if classes:
                btn.classes(classes)
            if tooltip:
                btn.tooltip(tooltip)
            return btn
        except Exception as e:
            _log().exception(f"botao: falha ao montar botão {rotulo!r} "
                             f"(variante={variante!r}): {e}")
            return None


def botao(rotulo=None, *, variante="primario", icone=None, on_click=None,
          tooltip=None, cor=None, chave_modulo="intranet", extra_classes="",
          compacto=False, no_caps=True):
    """Builds the single standardized button (delegates to `BotaoFabrica`).

    Wrapper fino da classe `BotaoFabrica` — assinatura e saída idênticas à
    original. Fábrica única de botões: lê o tema do módulo
    (`tema_modulo.ler_tema`) e aplica props/classes/estilo por variante
    (`primario`/`secundario`/`texto`/`icone` tematizadas; `neutro`,
    `restaurar`, `restaurar_fill`, `perigo`, `icone_branco` e
    `texto_branco` com props fixas). Com `cor` informado, o tema não é
    lido e `cor` sobrescreve a variante mantendo formato/tamanho;
    `extra_classes` soma classes; `compacto=True` produz o visual de
    rodapé de diálogo; `no_caps=False` remove o token `no-caps` (módulos
    UPPERCASE, ex. edit_pdf). Variante inválida levanta `ValueError`;
    falha de tema registra warning e usa os padrões; falha de montagem
    registra exception e retorna `None` (fail-soft). Retorna o `ui.button`
    criado.
    """
    return BotaoFabrica(chave_modulo).criar(
        rotulo, variante=variante, icone=icone, on_click=on_click,
        tooltip=tooltip, cor=cor, extra_classes=extra_classes,
        compacto=compacto, no_caps=no_caps)


def botao_icone(icone, on_click=None, *, variante="icone", cor=None,
                tooltip=None, chave_modulo="intranet", extra_classes=""):
    """Icon-only row-action button (themed or white header variants).

    Atalho para `botao(icone=..., variante=variante, ...)`: o padrão
    `variante="icone"` (`flat round dense size=sm` na cor do tema) serve às
    ações de linha de tabela (mover, excluir, abrir); `variante="icone_branco"`
    (`flat round color=white`) serve aos botões do header sobre fundo
    primário. `cor` sobrescreve a cor do tema mantendo o formato. Falhas são
    registradas no loguru e retornam `None` (fail-soft); retorna o
    `ui.button` criado.
    """
    try:
        return botao(None, variante=variante, icone=icone, on_click=on_click,
                     cor=cor, tooltip=tooltip, chave_modulo=chave_modulo,
                     extra_classes=extra_classes)
    except Exception as e:
        _log().exception(f"botao_icone: falha ao criar ação de linha "
                         f"(ícone={icone!r}): {e}")
        return None


class Dialogo:
    """Standard dialog + themed card as a context-manager class.

    Classe gerenciadora de contexto que replica `dialogo_card`: abre
    `ui.dialog` + `ui.card` via `ExitStack` (o escopo do card permanece
    aberto até `__exit__` — o conteúdo criado após o `__enter__` nasce
    dentro do card), aplica largura `largura`, altura máxima 90vh quando
    `max_altura` e o estilo de cartão do módulo
    (`tema_modulo.estilo_cartao`, fail-soft); com `titulo`, cria o rótulo
    `text-h6` e um separador. Expõe ainda `abrir()`/`fechar()`. O contexto
    devolve `(dlg, card)`, como o wrapper funcional.
    """

    def __init__(self, titulo="", largura="w-[560px]", *,
                 chave_modulo="intranet", max_altura=True):
        self.titulo = titulo
        self.largura = largura
        self.chave_modulo = chave_modulo
        self.max_altura = max_altura
        self.dlg = None
        self.card = None
        self._stack = None

    def __enter__(self):
        """Enters dialog + card contexts; returns `(dlg, card)`.

        Sequência de criação idêntica à de `dialogo_card`: dialog → card →
        classes (largura + `max-h-[90vh]`) → estilo do tema (fail-soft) →
        título/separador. Mantém os contextos abertos via `ExitStack`
        até `__exit__`.
        """
        from nicegui import ui
        from mod_intranet import tema_modulo
        self._stack = ExitStack()
        dlg = self._stack.enter_context(ui.dialog())
        card = self._stack.enter_context(ui.card())
        card.classes(f"{self.largura}{' max-h-[90vh]' if self.max_altura else ''}")
        try:
            estilo = tema_modulo.estilo_cartao(self.chave_modulo)
        except Exception as e:
            _log().warning(f"dialogo_card: estilo de cartão indisponível "
                           f"para '{self.chave_modulo}': {e}")
            estilo = ""
        if estilo:
            card.style(estilo)
        if self.titulo:
            ui.label(self.titulo).classes("text-h6")
            ui.separator()
        self.dlg, self.card = dlg, card
        return dlg, card

    def __exit__(self, *exc):
        """Closes the card and dialog contexts (reverse order)."""
        stack, self._stack = self._stack, None
        if stack:
            stack.close()
        return False

    def abrir(self):
        """Opens the dialog (no-op quando o contexto ainda não entrou)."""
        if self.dlg is not None:
            self.dlg.open()

    def fechar(self):
        """Closes the dialog (no-op quando o contexto ainda não entrou)."""
        if self.dlg is not None:
            self.dlg.close()


@contextmanager
def dialogo_card(titulo="", largura="w-[560px]", *, chave_modulo="intranet",
                 max_altura=True):
    """Opens a standard dialog + themed card (delegates to `Dialogo`).

    Wrapper fino da classe `Dialogo` — assinatura e saída idênticas à
    original. Abre `ui.dialog` + `ui.card` padronizados: largura `largura`,
    altura máxima de 90vh quando `max_altura` e estilo de cartão do módulo
    (`tema_modulo.estilo_cartao`). Com `titulo`, cria o rótulo `text-h6` e
    um separador. Falha ao ler o estilo do cartão registra warning no loguru
    e segue sem estilo (fail-soft). Faz `yield (dlg, card)`.
    """
    dialogo = Dialogo(titulo, largura, chave_modulo=chave_modulo,
                      max_altura=max_altura)
    with dialogo as (dlg, card):
        yield dlg, card


def rodape_dialogo(dlg, acoes=(), *, chave_modulo="intranet", classes_extra=""):
    """Renders the standard right-aligned dialog footer (Cancel + actions).

    Rodapé de diálogo com ações primárias sempre visíveis: linha
    `w-full justify-end` (gap 0.5rem) com o botão "Cancelar"
    (`flat no-caps`, fecha o diálogo) e, para cada item de `acoes` — tupla
    `(rotulo, on_click)` ou `(rotulo, on_click, kwargs)` — um botão
    primário compacto do tema do módulo. `classes_extra` soma classes à
    row (ex.: `mt-3`); default "" mantém a saída atual byte-idêntica.
    Itens malformados são ignorados com registro de erro no loguru
    (fail-soft, sem derrubar o diálogo).
    """
    from nicegui import ui
    classes = "w-full justify-end" + (f" {classes_extra}" if classes_extra else "")
    with ui.row().classes(classes).style("gap: 0.5rem"):
        ui.button("Cancelar", on_click=dlg.close).props("flat no-caps")
        for item in acoes:
            try:
                rotulo, on_click, *resto = item
                kwargs = resto[0] if resto else {}
                botao(rotulo, variante="primario", compacto=True,
                      on_click=on_click, chave_modulo=chave_modulo, **kwargs)
            except Exception as e:
                _log().error(f"rodape_dialogo: ação de rodapé inválida "
                             f"ignorada ({item!r}): {e}")


def rodape_salvar_restaurar(salvar, restaurar=None, *, chave_modulo="intranet",
                            rotulo_salvar="Aplicar", icone_salvar="save",
                            rotulo_restaurar="Restaurar padrão",
                            acoes_extra=(), data_testid=None):
    """Renders the standard per-card footer: restore + apply (+ extra actions).

    Rodapé PADRÃO dos cards de configuração (padrão de 2 botões por card):
    linha `w-full justify-end mt-2 flex-wrap` (gap 0.5rem) com, em ordem, as
    ações extras de `acoes_extra` — tuplas `(rotulo, icone, on_click[,
    tooltip[, variante]])`, variante default `solido` —, "Restaurar padrão"
    (variante `restaurar` — contorno âmbar; somente se `restaurar` for
    callable) e o botão "Aplicar" (variante `solido` do tema do módulo via
    `botao`) — ambos pela fábrica central, garantindo cor/tamanho idênticos
    em todo o módulo. "Aplicar" grava EXCLUSIVAMENTE o card em questão.
    `data_testid` (opcional) aplica `data-testid=<valor>` ao botão "Aplicar"
    (default `None` preserva a saída byte-idêntica das chamadas existentes).
    Falha de montagem registra exception e omite o botão (fail-soft); ações
    extras malformadas são ignoradas com registro.
    """
    from nicegui import ui
    with ui.row().classes("w-full justify-end mt-2 flex-wrap") \
            .style("gap: 0.5rem"):
        for item in acoes_extra:
            try:
                rotulo, icone, on_click, *resto = item
                tooltip = resto[0] if len(resto) > 0 else None
                variante = resto[1] if len(resto) > 1 else "solido"
                botao(rotulo, icone=icone, on_click=on_click, tooltip=tooltip,
                      variante=variante, chave_modulo=chave_modulo)
            except Exception as e:
                _log().error(f"rodape_salvar_restaurar: ação extra inválida "
                             f"ignorada ({item!r}): {e}")
        if callable(restaurar):
            botao(rotulo_restaurar, on_click=restaurar, variante="restaurar",
                  chave_modulo=chave_modulo)
        _btn_aplicar = botao(rotulo_salvar, icone=icone_salvar, on_click=salvar,
                             variante="solido", chave_modulo=chave_modulo)
        if _btn_aplicar is not None and data_testid:
            _btn_aplicar.props(f'data-testid={data_testid}')


def _valor_config(chave, padrao, origem):
    """Resolves one `tb_config` value for the field factories (fail-soft).

    Resolve o valor inicial de um campo de configuração via `get_config`
    (import lazy de `conexao_bd`); falha de leitura registra warning no
    loguru e devolve o `padrao` (fail-soft, sem derrubar a renderização).
    """
    try:
        from mod_intranet.bd_conexao import get_config
        return get_config(chave, padrao)
    except Exception as e:
        _log().warning(f"{origem}: falha ao ler '{chave}', usando "
                       f"valor/padrão: {e}")
        return padrao


class CampoBase:
    """Base class for config fields (`tb_config` resolution + finishing).

    Base dos campos de configuração: com `chave` informada e `valor=None`,
    o valor inicial vem de `get_config(chave, padrao)` (tb_config central,
    fail-soft via `_valor_config`); caso contrário, usa `valor`.
    `_finalizar` aplica a sequência fixa de acabamento — props, classes
    (`largura`), estilo inline (opcional), tooltip e `ao_mudar` repassado
    a `.on_value_change` — sobre o campo criado pela subclasse em
    `montar`. Falha de montagem registra exception e devolve `None`
    (fail-soft).
    """

    origem = "campo"

    def __init__(self, rotulo, valor=None, *, chave=None, padrao="",
                 ao_mudar=None, tooltip=None, largura="w-full",
                 props="outlined dense"):
        self.rotulo = rotulo
        self.valor = valor
        self.chave = chave
        self.padrao = padrao
        self.ao_mudar = ao_mudar
        self.tooltip = tooltip
        self.largura = largura
        self.props = props

    def _valor_resolvido(self):
        """Resolves the initial value (`tb_config` via `chave` or `valor`)."""
        if self.valor is None and self.chave:
            return _valor_config(self.chave, self.padrao,
                                 type(self).origem)
        return self.valor

    def _finalizar(self, campo, estilo=""):
        """Applies props/classes/style/tooltip/`ao_mudar` to the element.

        Sequência fixa de acabamento, na mesma ordem das funções
        originais: props → classes (`largura`) → style (`estilo`, quando
        não vazio) → tooltip → `ao_mudar`. Retorna o próprio campo.
        """
        if self.props:
            campo.props(self.props)
        if self.largura:
            campo.classes(self.largura)
        if estilo:
            campo.style(estilo)
        if self.tooltip:
            campo.tooltip(self.tooltip)
        if self.ao_mudar:
            campo.on_value_change(self.ao_mudar)
        return campo

    def montar(self):
        """Creates and finishes the field element (subclass hook)."""
        raise NotImplementedError


class CampoCor(CampoBase):
    """Standard color field (`ui.color_input`) with optional config lookup.

    Campo de cor padronizado: `ui.color_input(rotulo,
    value=valor_resolvido)` com props `props` (default `outlined dense`),
    classes `largura` (default `w-full`), tooltip opcional e `ao_mudar`
    repassado a `.on_value_change`. `props`/`largura` vazios não são
    aplicados (permite réplica crua, ex. painel de aparência sem props).
    Retorna o elemento criado (ou `None` em falha de montagem).
    """

    origem = "campo_cor"

    def montar(self):
        """Creates the `ui.color_input` with the resolved value."""
        from nicegui import ui
        try:
            return self._finalizar(ui.color_input(
                self.rotulo, value=self._valor_resolvido()))
        except Exception as e:
            _log().exception(f"campo_cor: falha ao montar campo "
                             f"{self.rotulo!r}: {e}")
            return None


class CampoTexto(CampoBase):
    """Standard text field (`ui.input`/`ui.textarea`) with config lookup.

    Campo de texto padronizado: `ui.textarea` quando `multiline`, senão
    `ui.input` (mesma assinatura posicional rótulo+valor). `cor_texto`/
    `cor_fundo` geram style inline (`color:`/`background-color:`)
    somente quando informados. `senha=True` cria o `ui.input` com
    `password=True, password_toggle_button=True` (botão exibir/ocultar,
    byte-idêntico aos campos de senha existentes; sem efeito com
    `multiline`). `placeholder` é repassado ao construtor quando
    informado. Sem valor resolvido (`valor=None` sem `chave`), o kwarg
    `value` NÃO é repassado — réplica crua byte-idêntica (`ui.input` sem
    `value` usa `''`, não `None`). Retorna o elemento criado (ou `None`
    em falha de montagem).
    """

    origem = "campo_texto"

    def __init__(self, rotulo, valor=None, *, chave=None, padrao="",
                 ao_mudar=None, tooltip=None, cor_texto=None, cor_fundo=None,
                 largura="w-full", multiline=False, props="outlined dense",
                 senha=False, placeholder=None):
        super().__init__(rotulo, valor, chave=chave, padrao=padrao,
                         ao_mudar=ao_mudar, tooltip=tooltip, largura=largura,
                         props=props)
        self.cor_texto = cor_texto
        self.cor_fundo = cor_fundo
        self.multiline = multiline
        self.senha = senha
        self.placeholder = placeholder

    def _estilo(self):
        """Builds the inline style from `cor_texto`/`cor_fundo` (or empty)."""
        estilo = ""
        if self.cor_texto:
            estilo += f"color:{self.cor_texto};"
        if self.cor_fundo:
            estilo += f"background-color:{self.cor_fundo};"
        return estilo

    def montar(self):
        """Creates the `ui.input`/`ui.textarea` and finishes it."""
        from nicegui import ui
        try:
            fabrica = ui.textarea if self.multiline else ui.input
            kwargs = {}
            valor_resolvido = self._valor_resolvido()
            if valor_resolvido is not None:
                kwargs["value"] = valor_resolvido
            if self.senha and not self.multiline:
                kwargs["password"] = True
                kwargs["password_toggle_button"] = True
            if self.placeholder is not None:
                kwargs["placeholder"] = self.placeholder
            campo = fabrica(self.rotulo, **kwargs)
            return self._finalizar(campo, estilo=self._estilo())
        except Exception as e:
            _log().exception(f"campo_texto: falha ao montar campo "
                             f"{self.rotulo!r}: {e}")
            return None


class CampoSelecao(CampoBase):
    """Standard select field (`ui.select`) with optional config lookup.

    Campo de seleção padronizado: `ui.select(opcoes, label=rotulo,
    value=valor_resolvido)` com props `props` (default `outlined dense`),
    classes `largura` (default `w-full`) e tooltip opcional. Com `chave`
    informada e `valor=None`, o valor inicial vem de `get_config(chave,
    padrao)`. `ao_mudar` é repassado a `.on_value_change`. Retorna o
    elemento criado (ou `None` em falha de montagem).
    """

    origem = "campo_selecao"

    def __init__(self, rotulo, opcoes, valor=None, *, chave=None,
                 padrao=None, ao_mudar=None, largura="w-full",
                 props="outlined dense", tooltip=None):
        super().__init__(rotulo, valor, chave=chave, padrao=padrao,
                         ao_mudar=ao_mudar, tooltip=tooltip, largura=largura,
                         props=props)
        self.opcoes = opcoes

    def montar(self):
        """Creates the `ui.select` with the resolved value."""
        from nicegui import ui
        try:
            return self._finalizar(ui.select(self.opcoes, label=self.rotulo,
                                             value=self._valor_resolvido()))
        except Exception as e:
            _log().exception(f"campo_selecao: falha ao montar campo "
                             f"{self.rotulo!r}: {e}")
            return None


def campo_cor(rotulo, valor=None, *, chave=None, padrao="", ao_mudar=None,
              tooltip=None, largura="w-full", props="outlined dense"):
    """Standard color field (delegates to `CampoCor`).

    Wrapper fino da classe `CampoCor` — assinatura e saída idênticas à
    original. Campo de cor padronizado: `ui.color_input(rotulo,
    value=valor_resolvido)` com props `props` (default `outlined dense`),
    classes `largura` (default `w-full`), tooltip opcional e `ao_mudar`
    repassado a `.on_value_change` (recebe o evento, igual ao padrão
    atual). Com `chave` informada e `valor=None`, o valor inicial vem de
    `get_config(chave, padrao)` (tb_config central); falha de leitura
    registra warning no loguru e usa `valor`/`padrao` (fail-soft).
    `props`/`largura` vazios não são aplicados. Retorna o elemento criado
    (ou `None` em falha de montagem).
    """
    return CampoCor(rotulo, valor, chave=chave, padrao=padrao,
                    ao_mudar=ao_mudar, tooltip=tooltip, largura=largura,
                    props=props).montar()


def campo_texto(rotulo, valor=None, *, chave=None, padrao="", ao_mudar=None,
                tooltip=None, cor_texto=None, cor_fundo=None,
                largura="w-full", multiline=False, props="outlined dense",
                senha=False, placeholder=None):
    """Standard text field (delegates to `CampoTexto`).

    Wrapper fino da classe `CampoTexto` — assinatura e saída idênticas à
    original. Campo de texto padronizado: `ui.textarea` quando `multiline`,
    senão `ui.input` (mesma assinatura posicional rótulo+valor), props
    `props` (default `outlined dense`), classes `largura` (default
    `w-full`), tooltip opcional e `ao_mudar` repassado a
    `.on_value_change`. Com `chave` informada e `valor=None`, o valor
    inicial vem de `get_config(chave, padrao)`; falha de leitura registra
    warning no loguru e usa `valor`/`padrao` (fail-soft). `cor_texto`/
    `cor_fundo` geram style inline somente quando informados.
    `senha=True` cria o campo com botão exibir/ocultar; `placeholder` é
    repassado quando informado; sem valor resolvido o kwarg `value` não é
    repassado (réplica crua byte-idêntica). Retorna o elemento criado (ou
    `None` em falha de montagem).
    """
    return CampoTexto(rotulo, valor, chave=chave, padrao=padrao,
                      ao_mudar=ao_mudar, tooltip=tooltip,
                      cor_texto=cor_texto, cor_fundo=cor_fundo,
                      largura=largura, multiline=multiline, props=props,
                      senha=senha, placeholder=placeholder).montar()


def campo_selecao(rotulo, opcoes, valor=None, *, chave=None, padrao=None,
                  ao_mudar=None, largura="w-full", props="outlined dense",
                  tooltip=None):
    """Standard select field (delegates to `CampoSelecao`).

    Wrapper fino da classe `CampoSelecao` — assinatura e saída idênticas à
    original. Campo de seleção padronizado: `ui.select(opcoes,
    label=rotulo, value=valor_resolvido)` com props `props` (default
    `outlined dense`), classes `largura` (default `w-full`) e tooltip
    opcional. Com `chave` informada e `valor=None`, o valor inicial vem de
    `get_config(chave, padrao)`; falha de leitura registra warning no
    loguru e usa `valor`/`padrao` (fail-soft). Retorna o elemento criado
    (ou `None` em falha de montagem).
    """
    return CampoSelecao(rotulo, opcoes, valor, chave=chave, padrao=padrao,
                        ao_mudar=ao_mudar, largura=largura, props=props,
                        tooltip=tooltip).montar()


class Cartao:
    """Configuration card class (themed title/caption/grid/actions/extras).

    Encapsula a montagem do card de configuração: estilo `cor_fundo`
    informado ou `tema_modulo.estilo_cartao(chave_modulo)` (fail-soft),
    mais `color:{cor_texto}` quando informado; cor de título do tema
    quando `cor_titulo=None`; grid `w-full grid-cols-1` + `colunas` com
    `gap:{gap}` para os CALLABLES de `campos` (cada um cria seu campo
    dentro do grid); `destaque_impar=True` com quantidade ímpar > 3
    aplica `col-span-full` ao primeiro campo; `extras` — CALLABLES
    renderizados ENTRE o grid e a row de ações; `acoes` — tuplas
    `(rotulo, icone, on_click[, tooltip])` — vira row `w-full
    justify-center` com botões `ui_comum.botao` do tema do módulo.
    Falhas por campo/ação/extra são registradas no loguru sem derrubar o
    card (fail-soft). `card_config` é o wrapper fino.
    """

    def __init__(self, *, chave_modulo="intranet", cor_titulo=None,
                 cor_fundo=None, cor_texto=None, colunas="", gap="1.25rem",
                 destaque_impar=True):
        self.chave_modulo = chave_modulo
        self.cor_titulo = cor_titulo
        self.cor_fundo = cor_fundo
        self.cor_texto = cor_texto
        self.colunas = colunas
        self.gap = gap
        self.destaque_impar = destaque_impar

    def _estilo(self):
        """Builds the card inline style (explicit `cor_fundo` or theme)."""
        from mod_intranet import tema_modulo
        if self.cor_fundo:
            estilo = f"background-color:{self.cor_fundo};"
        else:
            try:
                estilo = tema_modulo.estilo_cartao(self.chave_modulo)
            except Exception as e:
                _log().warning(f"card_config: estilo de cartão indisponível "
                               f"para '{self.chave_modulo}': {e}")
                estilo = ""
        if self.cor_texto:
            estilo = f"{estilo}color:{self.cor_texto};"
        return estilo

    def _cor_titulo_resolvida(self):
        """Resolves the title color (`cor_titulo` explicit or theme value)."""
        if self.cor_titulo is not None:
            return self.cor_titulo
        from mod_intranet import tema_modulo
        try:
            return tema_modulo.ler_tema(self.chave_modulo).get(
                "cor_titulo", "#212121") or "#212121"
        except Exception as e:
            _log().warning(f"card_config: cor de título indisponível para "
                           f"'{self.chave_modulo}': {e}")
            return "#212121"

    def montar(self, titulo, campos=(), legenda="", acoes=(), extras=()):
        """Builds the full card; returns the element (or `None` on failure).

        Ordem fixa de criação: card (`w-full`) + estilo → título
        (`text-subtitle1 font-bold` na cor resolvida) → legenda
        (`text-caption text-grey-7 max-w-3xl -mt-2`) → grid de campos →
        extras → row de ações. Falha geral de montagem registra exception
        e retorna `None` (fail-soft).
        """
        from nicegui import ui
        estilo = self._estilo()
        cor_titulo = self._cor_titulo_resolvida()
        try:
            card = ui.card().classes("w-full")
            if estilo:
                card.style(estilo)
            with card:
                ui.label(titulo).classes("text-subtitle1 font-bold") \
                    .style(f"color:{cor_titulo}")
                if legenda:
                    ui.label(legenda).classes(
                        "text-caption text-grey-7 max-w-3xl -mt-2")
                classes_grid = "w-full grid-cols-1" + \
                    (f" {self.colunas}" if self.colunas else "")
                with ui.grid().classes(classes_grid).style(f"gap:{self.gap}"):
                    destacar = (self.destaque_impar and len(campos) > 3
                                and len(campos) % 2 == 1)
                    for i, criar in enumerate(campos):
                        try:
                            el = criar()
                            if destacar and i == 0 and el is not None:
                                el.classes("col-span-full")
                        except Exception as e:
                            _log().error(f"card_config: campo {i} ignorado "
                                         f"({criar!r}): {e}")
                for j, criar_extra in enumerate(extras):
                    try:
                        criar_extra()
                    except Exception as e:
                        _log().error(f"card_config: extra {j} ignorado "
                                     f"({criar_extra!r}): {e}")
                if acoes:
                    with ui.row().classes("w-full justify-center") \
                            .style("gap: 0.5rem"):
                        for item in acoes:
                            try:
                                rotulo, icone, on_click, *resto = item
                                tooltip = resto[0] if resto else None
                                botao(rotulo, icone=icone,
                                      on_click=on_click, tooltip=tooltip,
                                      chave_modulo=self.chave_modulo)
                            except Exception as e:
                                _log().error(f"card_config: ação inválida "
                                             f"ignorada ({item!r}): {e}")
            return card
        except Exception as e:
            _log().exception(f"card_config: falha ao montar card "
                             f"{titulo!r}: {e}")
            return None


def card_config(titulo, campos=(), *, legenda="", acoes=(),
                chave_modulo="intranet", cor_titulo=None, cor_fundo=None,
                cor_texto=None, colunas="", gap="1.25rem",
                destaque_impar=True, extras=()):
    """Configuration card (delegates to `Cartao`).

    Wrapper fino da classe `Cartao` — assinatura e saída idênticas à
    original. Card de configuração padronizado: `ui.card().classes("w-full")`
    com estilo `cor_fundo` informado ou `tema_modulo.estilo_cartao`
    (fail-soft), mais `color:{cor_texto}` quando informado. Título em
    label `text-subtitle1 font-bold` na cor `cor_titulo` — quando `None`,
    usa a cor de título do tema. `legenda` vira label `text-caption
    text-grey-7 max-w-3xl -mt-2`. O grid recebe os CALLABLES de `campos`
    (o caller captura o elemento via closure); `destaque_impar=True` com
    quantidade ímpar > 3 aplica `col-span-full` ao primeiro campo.
    `extras` — CALLABLES renderizados ENTRE o grid e a row de ações;
    `acoes` — tuplas `(rotulo, icone, on_click[, tooltip])` — vira row
    `w-full justify-center` com botões do tema do módulo. Falhas por
    campo/ação são registradas no loguru sem derrubar o card (fail-soft).
    Retorna o card criado (ou `None` em falha de montagem).
    """
    cartao = Cartao(chave_modulo=chave_modulo, cor_titulo=cor_titulo,
                    cor_fundo=cor_fundo, cor_texto=cor_texto,
                    colunas=colunas, gap=gap, destaque_impar=destaque_impar)
    return cartao.montar(titulo, campos=campos, legenda=legenda,
                         acoes=acoes, extras=extras)


def card_admin(titulo, *, icone="settings", chave_modulo="intranet",
               aberto=True, cor_borda=None, cor_fundo=None, extra_classes="",
               grade=True, gap="0.5rem"):
    """Standard admin card: essential card shell + collapsible header inside.

    Padrão dos painéis de administração (card ESSENCIAL): `ui.card` w-full
    com borda esquerda temática — `cor_borda` explícita vence; senão a
    `<prefixo>_cor_botao` do tema (ler_tema, fail-soft); senão cinza
    `#607D8B` — e fundo por `estilo_cartao(chave_modulo)` (fail-soft),
    salvo `cor_fundo` explícito. Dentro do card fica `ui.expansion(titulo,
    icon=icone)` — o cabeçalho retrátil; o card permanece visível mesmo
    com o conteúdo retraído (o retrátil é apenas o cabeçalho, nunca o
    card). O retorno é o alvo do `with` do chamador:

    - `grade=True` (padrão): dentro da expansion é criada a GRADE
      responsiva do projeto — `ui.grid().classes("w-full grid-cols-1
      sm:grid-cols-2 md:grid-cols-3")` com `gap:{gap}` — 1 campo por linha
      em tela pequena, 2 em média e 3 em grande; o retorno é a grade e o
      conteúdo do `with` flui nela (campos em células; rótulos/rodapés
      full-width usam `col-span-full`).
    - `grade=False`: o retorno é a própria expansion — conteúdo livre
      (tabelas, textareas, seções mistas).

    `extra_classes` soma classes no card (ex.: espaçamento `mt-2`);
    `aberto=True` inicia com o conteúdo expandido. O título (cabeçalho
    retrátil) é colorido com a cor de título do módulo
    (`<prefixo>_cor_titulo` via `ler_tema`, fail-soft → `#212121`), seguindo
    o padrão "cor dos títulos dos cards". Falha ao ler o tema registra
    warning e usa os padrões (fail-soft).
    """
    from nicegui import ui
    from mod_intranet import tema_modulo
    try:
        tema = tema_modulo.ler_tema(chave_modulo)
        cor_tema = tema.get("cor_botao", "") or ""
        cor_titulo = tema.get("cor_titulo", "#212121") or "#212121"
    except Exception as e:
        _log().warning(f"card_admin: tema indisponível para "
                       f"'{chave_modulo}', usando borda padrão: {e}")
        cor_tema = ""
        cor_titulo = "#212121"
    borda = cor_borda or cor_tema or "#607D8B"
    estilo = f"border-left-color:{borda};"
    if cor_fundo:
        estilo += f"background-color:{cor_fundo};"
    else:
        try:
            estilo += tema_modulo.estilo_cartao(chave_modulo)
        except Exception:
            pass
    with ui.card().classes(
            f"w-full border-l-8 {extra_classes}".strip()).style(estilo):
        exp = ui.expansion(titulo, icon=icone, value=aberto).classes("w-full")
        if cor_titulo:
            exp.props(f"header-style='color:{cor_titulo}'")
        alvo = exp
        if grade:
            with exp:
                alvo = ui.grid().classes(
                    "w-full grid-cols-1 sm:grid-cols-2 md:grid-cols-3"
                ).style(f"gap:{gap}")
    return alvo
