"""Phone helpers: DDI select + BR formatting (single standard).
EN: Canonical phone storage, BR display mask and a DDI+number field with country tooltip.
PT-BR: Armazenamento canônico, máscara BR de exibição e campo DDI+número com
tooltip do país. Todo telefone do sistema usa este módulo (cadastro de
usuário, meu perfil, troca de credenciais do master e lista telefônica).
"""
import re

try:
    _REGEX_BR = re.compile(
        r"^(?:\+?55\s?)?(?:\(?[1-9]{2}\)?\s?)?"
        r"(?:((?:9\d|[2-9])\d{3})[\s-]?(\d{4}))$"
    )
except Exception:
    _REGEX_BR = None

DDI_PADRAO = "+55"

# DDI -> país (E.164). Lista completa para o combobox; o rótulo exibido é
# "+DDI — País", de modo que o hover sobre a opção já mostra o país.
DDI_PAISES = {
    "+93": "Afeganistão", "+355": "Albânia", "+213": "Argélia",
    "+1684": "Samoa Americana", "+376": "Andorra", "+244": "Angola",
    "+1264": "Anguilla", "+672": "Antártida", "+1268": "Antígua e Barbuda",
    "+54": "Argentina", "+374": "Armênia", "+297": "Aruba",
    "+61": "Austrália", "+43": "Áustria", "+994": "Azerbaijão",
    "+1242": "Bahamas", "+973": "Bahrein", "+880": "Bangladesh",
    "+1246": "Barbados", "+375": "Bielorrússia", "+32": "Bélgica",
    "+501": "Belize", "+229": "Benim", "+1441": "Bermudas",
    "+975": "Butão", "+591": "Bolívia", "+387": "Bósnia e Herzegovina",
    "+267": "Botsuana", "+55": "Brasil", "+673": "Brunei",
    "+359": "Bulgária", "+226": "Burkina Faso", "+257": "Burundi",
    "+855": "Camboja", "+237": "Camarões", "+1": "EUA/Canadá/Caribe",
    "+238": "Cabo Verde", "+1345": "Ilhas Cayman",
    "+236": "República Centro-Africana", "+235": "Chade", "+56": "Chile",
    "+86": "China", "+57": "Colômbia", "+269": "Comores",
    "+242": "Congo", "+243": "Congo (RDC)", "+682": "Ilhas Cook",
    "+506": "Costa Rica", "+225": "Costa do Marfim", "+385": "Croácia",
    "+53": "Cuba", "+357": "Chipre", "+420": "Tchéquia",
    "+45": "Dinamarca", "+253": "Djibuti", "+1767": "Dominica",
    "+1809": "Rep. Dominicana", "+1829": "Rep. Dominicana",
    "+1849": "Rep. Dominicana", "+593": "Equador", "+20": "Egito",
    "+503": "El Salvador", "+240": "Guiné Equatorial", "+291": "Eritreia",
    "+372": "Estônia", "+251": "Etiópia", "+500": "Ilhas Malvinas",
    "+298": "Ilhas Faroe", "+679": "Fiji", "+358": "Finlândia",
    "+33": "França", "+594": "Guiana Francesa", "+241": "Gabão",
    "+220": "Gâmbia", "+995": "Geórgia", "+49": "Alemanha",
    "+233": "Gana", "+350": "Gibraltar", "+30": "Grécia",
    "+299": "Groenlândia", "+1473": "Granada", "+590": "Guadalupe",
    "+1671": "Guam", "+502": "Guatemala", "+224": "Guiné",
    "+245": "Guiné-Bissau", "+592": "Guiana", "+509": "Haiti",
    "+504": "Honduras", "+852": "Hong Kong", "+36": "Hungria",
    "+354": "Islândia", "+91": "Índia", "+62": "Indonésia",
    "+98": "Irã", "+964": "Iraque", "+353": "Irlanda",
    "+972": "Israel", "+39": "Itália", "+1876": "Jamaica",
    "+81": "Japão", "+962": "Jordânia", "+7": "Rússia/Cazaquistão",
    "+254": "Quênia", "+686": "Kiribati", "+850": "Coreia do Norte",
    "+82": "Coreia do Sul", "+965": "Kuwait", "+996": "Quirguistão",
    "+856": "Laos", "+371": "Letônia", "+961": "Líbano",
    "+266": "Lesoto", "+231": "Libéria", "+218": "Líbia",
    "+423": "Liechtenstein", "+370": "Lituânia", "+352": "Luxemburgo",
    "+853": "Macau", "+389": "Macedônia do Norte", "+261": "Madagascar",
    "+265": "Malawi", "+60": "Malásia", "+960": "Maldivas",
    "+223": "Mali", "+356": "Malta", "+692": "Ilhas Marshall",
    "+596": "Martinica", "+222": "Mauritânia", "+230": "Maurício",
    "+52": "México", "+691": "Micronésia", "+373": "Moldávia",
    "+377": "Mônaco", "+976": "Mongólia", "+382": "Montenegro",
    "+1664": "Montserrat", "+212": "Marrocos", "+258": "Moçambique",
    "+95": "Mianmar", "+264": "Namíbia", "+674": "Nauru",
    "+977": "Nepal", "+31": "Holanda", "+687": "Nova Caledônia",
    "+64": "Nova Zelândia", "+505": "Nicarágua", "+227": "Níger",
    "+234": "Nigéria", "+683": "Niue", "+672": "Ilha Norfolk",
    "+1670": "Ilhas Marianas", "+47": "Noruega", "+968": "Omã",
    "+92": "Paquistão", "+680": "Palau", "+970": "Palestina",
    "+507": "Panamá", "+675": "Papua-Nova Guiné", "+595": "Paraguai",
    "+51": "Peru", "+63": "Filipinas", "+48": "Polônia",
    "+351": "Portugal", "+1787": "Porto Rico", "+1939": "Porto Rico",
    "+974": "Catar", "+262": "Reunião", "+40": "Romênia",
    "+250": "Ruanda", "+590": "São Bartolomeu", "+290": "Santa Helena",
    "+1869": "São Cristóvão e Nevis", "+1758": "Santa Lúcia",
    "+590": "São Martinho", "+508": "São Pedro e Miquelon",
    "+1784": "São Vicente e Granadinas", "+685": "Samoa",
    "+378": "San Marino", "+239": "São Tomé e Príncipe",
    "+966": "Arábia Saudita", "+221": "Senegal", "+381": "Sérvia",
    "+248": "Seicheles", "+232": "Serra Leoa", "+65": "Singapura",
    "+421": "Eslováquia", "+386": "Eslovênia", "+677": "Ilhas Salomão",
    "+252": "Somália", "+27": "África do Sul", "+34": "Espanha",
    "+94": "Sri Lanka", "+249": "Sudão", "+597": "Suriname",
    "+268": "Essuatíni", "+46": "Suécia", "+41": "Suíça",
    "+963": "Síria", "+886": "Taiwan", "+992": "Tajiquistão",
    "+255": "Tanzânia", "+66": "Tailândia", "+670": "Timor-Leste",
    "+228": "Togo", "+690": "Tokelau", "+676": "Tonga",
    "+1868": "Trinidad e Tobago", "+216": "Tunísia", "+90": "Turquia",
    "+993": "Turcomenistão", "+1649": "Turks e Caicos", "+688": "Tuvalu",
    "+256": "Uganda", "+380": "Ucrânia", "+971": "Emirados Árabes",
    "+44": "Reino Unido", "+598": "Uruguai", "+998": "Uzbequistão",
    "+678": "Vanuatu", "+58": "Venezuela", "+84": "Vietnã",
    "+1284": "Ilhas Virgens (GB)", "+1340": "Ilhas Virgens (EUA)",
    "+681": "Wallis e Futuna", "+967": "Iêmen", "+260": "Zâmbia",
    "+263": "Zimbábue",
}


def listar_ddis():
    """EN: Sorted DDI list with default (+55) first. PT-BR: Lista de DDIs com +55 primeiro."""
    try:
        todos = sorted(DDI_PAISES.keys(), key=lambda d: (d != DDI_PADRAO, d))
        return todos
    except Exception:
        return [DDI_PADRAO]


def nome_pais(ddi):
    """EN: Country name for a DDI. PT-BR: Nome do país do DDI."""
    try:
        return DDI_PAISES.get((ddi or "").strip(), "")
    except Exception:
        return ""


def opcoes_ddi():
    """EN: Select options '+DDI — Country'. PT-BR: Opções '+DDI — País' (hover mostra o país)."""
    try:
        opcoes = {}
        for ddi in listar_ddis():
            opcoes[ddi] = f"{ddi} - {DDI_PAISES.get(ddi, '')}".strip()
        return opcoes
    except Exception:
        return {DDI_PADRAO: f"{DDI_PADRAO} - Brasil"}


def apenas_digitos(texto):
    """EN: Only digits. PT-BR: Só dígitos."""
    try:
        import re as _re
        return _re.sub(r"\D", "", texto or "")
    except Exception:
        return ""


def obter_ddi(telefone):
    """EN: Detects stored DDI or default +55. PT-BR: Detecta o DDI gravado ou usa +55."""
    try:
        txt = (telefone or "").strip()
        if not txt:
            return DDI_PADRAO
        if txt.startswith("+"):
            dig = apenas_digitos(txt)
            for ddi in sorted(DDI_PAISES.keys(), key=len, reverse=True):
                if dig.startswith(ddi.replace("+", "")):
                    return ddi
            return DDI_PADRAO
        dig = apenas_digitos(txt)
        if len(dig) > 11:
            for ddi in sorted(DDI_PAISES.keys(), key=len, reverse=True):
                if ddi in ("+1", "+7"):
                    continue
                if dig.startswith(ddi.replace("+", "")):
                    return ddi
        return DDI_PADRAO
    except Exception:
        return DDI_PADRAO


def obter_numero_nacional(telefone):
    """EN: National number without DDI. PT-BR: Número nacional sem o DDI."""
    try:
        txt = (telefone or "").strip()
        if not txt:
            return ""
        ddi = obter_ddi(txt)
        dig = apenas_digitos(txt)
        prefixo = ddi.replace("+", "")
        if dig.startswith(prefixo) and len(dig) > len(prefixo):
            resto = dig[len(prefixo):]
            # evita comer DDD nacional quando DDI=default e número já é nacional
            if ddi == DDI_PADRAO and len(dig) in (10, 11):
                return dig
            return resto
        return dig
    except Exception:
        return apenas_digitos(telefone)


def normalizar_telefone(ddi, numero):
    """EN: Canonical '+DDIdigits'. PT-BR: Canônico '+DDIdígitos' (+55 automático)."""
    try:
        ddi = (ddi or "").strip() or DDI_PADRAO
        if not ddi.startswith("+"):
            ddi = "+" + ddi
        dig = apenas_digitos(numero)
        if not dig:
            return ""
        prefixo = ddi.replace("+", "")
        if dig.startswith(prefixo) and len(dig) > 11:
            return "+" + dig
        return ddi + dig
    except Exception:
        return ""


def validar_br(telefone):
    """EN: BR validation with project regex. PT-BR: Validação BR com o regex do projeto."""
    try:
        txt = (telefone or "").strip()
        if not txt:
            return False
        if _REGEX_BR is None:
            return len(apenas_digitos(txt)) in (10, 11)
        return bool(_REGEX_BR.match(txt))
    except Exception:
        return False


def formatar_br(nacional):
    """EN: '(DD) 9XXXX-XXXX'. PT-BR: '(DDD) 9XXXX-XXXX' ou '(DDD) XXXX-XXXX'."""
    try:
        dig = apenas_digitos(nacional)
        if len(dig) == 11:
            return f"({dig[:2]}) {dig[2:7]}-{dig[7:]}"
        if len(dig) == 10:
            return f"({dig[:2]}) {dig[2:6]}-{dig[6:]}"
        return (nacional or "").strip()
    except Exception:
        return (nacional or "").strip()


def formatar_para_exibicao(telefone):
    """EN: '+55 (DD) 9XXXX-XXXX' for BR, '+DDI number' otherwise.
    PT-BR: '+55 (DDD) 9XXXX-XXXX' para BR, '+DDI número' para o resto."""
    try:
        txt = (telefone or "").strip()
        if not txt:
            return ""
        ddi = obter_ddi(txt)
        nacional = obter_numero_nacional(txt)
        if ddi == DDI_PADRAO and len(apenas_digitos(nacional)) in (10, 11):
            return f"{DDI_PADRAO} {formatar_br(nacional)}"
        if nacional:
            return f"{ddi} {nacional}".strip()
        return txt
    except Exception:
        return (telefone or "").strip()


def criar_campo_telefone(rotulo="Telefone", valor="", ddi_inicial=None,
                         placeholder="(35) 98818-3288", largura_numero="flex-1",
                         testid_ddi=None, testid_numero=None):
    """EN: DDI select + number input with country tooltip; returns dict with getter.
    PT-BR: Linha DDI (combobox com todos os países, hover mostra o país) +
    número; DDI padrão +55 automático; retorna dict com `obter()` canônico."""
    try:
        from nicegui import ui
    except Exception:
        return None
    try:
        ddi_atual = (ddi_inicial or "").strip() or obter_ddi(valor) or DDI_PADRAO
        nacional_atual = obter_numero_nacional(valor)
        with ui.row().classes("w-full gap-2 flex-nowrap items-start"):
            sel = ui.select(opcoes_ddi(), label="DDI", value=ddi_atual,
                            with_input=True).props("outlined dense").classes("w-[190px]")
            if testid_ddi:
                try:
                    sel.props(f"data-testid={testid_ddi}")
                except Exception:
                    pass
            inp = ui.input(rotulo, value=nacional_atual,
                           placeholder=placeholder).props("outlined dense").classes(
                f"{largura_numero} min-w-0")

            def _atualizar_tooltip(e=None):
                try:
                    ddi_sel = (sel.value or "").strip() or DDI_PADRAO
                    pais = nome_pais(ddi_sel) or ""
                    sel.tooltip(f"{ddi_sel} - {pais}".strip(" -"))
                except Exception:
                    pass

            try:
                sel.tooltip(f"{ddi_atual} - {nome_pais(ddi_atual)}".strip(" -"))
                sel.on_value_change(_atualizar_tooltip)
            except Exception:
                pass
            if testid_numero:
                try:
                    inp.props(f"data-testid={testid_numero}")
                except Exception:
                    pass

        def _obter():
            try:
                return normalizar_telefone(sel.value, inp.value)
            except Exception:
                return ""

        def _definir(novo_valor):
            try:
                sel.value = obter_ddi(novo_valor)
                inp.value = obter_numero_nacional(novo_valor)
                _atualizar_tooltip()
            except Exception:
                pass

        return {"ddi": sel, "numero": inp, "obter": _obter, "definir": _definir}
    except Exception:
        return None
