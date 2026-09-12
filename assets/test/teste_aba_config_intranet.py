"""Teste da aba CONFIG do menu_mod em /configuracoes (módulo Intranet).

Script standalone (NÃO pytest). Renderiza a tela REAL `mostrar_tela`
(NiceGUI headless, sem servidor) e verifica, campo por campo da aba
Config (Cores, Textos fixos, Gerais e Ícones):

  1. ATIVAÇÃO — todo campo existe, está habilitado (enabled) e editável
     (exceto BASE_DIR, que é somente leitura por design);
  2. CONFIGURAÇÃO INICIAL — todo campo nasce com o valor vigente do
     `tb_config` (padrão quando ausente);
  3. APLICAÇÃO sem editar nada — grava de volta o que já estava
     (contrato anti-zeramento) e reconfigura observabilidade + backups;
  4. APLICAÇÃO com edição — cada campo propagado ao estado e gravado na
     chave CORRETA do `tb_config` (inclui limpeza intencional com "");
  5. VALIDAÇÕES — entradas inválidas/fora de faixa são saneadas sem
     derrubar o APLICÁR (backup/sessão/aviso, tamanho e cor vazia);
  6. RESTAURAR PADRÃO — os 4 cards da aba restauram os padrões
     codificados no banco e nos campos (Ícones também o favicon);
  7. FAVICON — upload .ico válido aplica, extensão errada e arquivo
     vazio são recusados;
  8. ACESSO — usuário sem perfil administrador_geral recebe a mensagem
     de restrição (a tela não renderiza os campos).

O teste é AUTOCONTIDO: faz snapshot das chaves do `tb_config` e do
favicon atual, roda tudo e restaura ao final.

Execute: .venv/bin/python test/teste_aba_config_intranet.py
"""
import asyncio
import os
import shutil
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))))

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_OK = 0
_TOTAL = 0


def check(cond, msg):
    global _OK, _TOTAL
    _TOTAL += 1
    if cond:
        _OK += 1
        print(f"  OK [{_OK}] {msg}")
    else:
        print(f"  FALHOU [{_TOTAL - _OK}] {msg}")


print("INICIANDO TESTES — Aba Config do menu_mod (/configuracoes)")

from nicegui import ui  # noqa: E402
from nicegui.client import Client  # noqa: E402
from nicegui.elements.button import Button  # noqa: E402
from nicegui.elements.color_input import ColorInput  # noqa: E402
from nicegui.elements.input import Input  # noqa: E402
from nicegui.elements.label import Label  # noqa: E402
from nicegui.elements.select import Select  # noqa: E402
from nicegui.elements.upload import Upload  # noqa: E402
from nicegui.elements.mixins.value_element import ValueElement  # noqa: E402

from mod_intranet.bd_conexao import (  # noqa: E402
    init_db, get_config, set_config, PADRAO_CONFIG)
from mod_intranet import observabilidade  # noqa: E402
from mod_intranet import rotinas as _rotinas  # noqa: E402

init_db()

# ------------------------------------------------------------------
# Chaves tocadas pela aba Config (snapshot/restore no fim do teste)
# ------------------------------------------------------------------
CHAVES = [
    "cor_principal", "cor_fundo", "intranet_cor_botao",
    "intranet_cor_texto_botao", "intranet_cor_titulo",
    "intranet_cor_fundo_card", "intranet_cor_texto_card",
    "intranet_btn_tamanho", "titulo_sistema", "texto_login_titulo",
    "texto_login_subtitulo", "texto_login_hint", "texto_home_saudacao",
    "texto_home_subtitulo", "texto_rodape", "backup_interval_hours",
    "sessao_retencao", "notificacao_timeout", "icone_sistema",
    "favicon_custom",
]
ORIG = {k: get_config(k, None) for k in CHAVES}
mod_snapshot = []  # preenchido no main() (tb_modulos antes dos restores)

FAV = os.path.join(RAIZ, "assets", "favicon_atual.ico")
FAV_BKP = FAV + ".teste_bkp"
FAV_TINHA = os.path.exists(FAV)
if FAV_TINHA:
    shutil.copy2(FAV, FAV_BKP)

# ------------------------------------------------------------------
# Monkeypatches headless: observabilidade/backups/timer sob controle
# ------------------------------------------------------------------
_obs_calls = []
observabilidade.configurar = lambda: _obs_calls.append(True)

_rb_calls = []
_rotinas.reagendar_backup = lambda chave, horas: _rb_calls.append((chave, horas))

_timer_calls = []
ui.timer = lambda *a, **k: _timer_calls.append(a)


# ------------------------------------------------------------------
# Campos da aba Config: rótulo → chave do tb_config (readonly quando só leitura)
# ------------------------------------------------------------------
CAMPOS_CONFIG = {
    # Card Cores
    "Cor primária (menus e destaques)": ("cor_principal", False),
    "Cor de fundo das páginas": ("cor_fundo", False),
    "Cor geral do módulo": ("intranet_cor_botao", False),
    "Cor do texto do módulo": ("intranet_cor_texto_botao", False),
    "Tamanho dos botões": ("intranet_btn_tamanho", False),
    "Cor dos títulos dos cards": ("intranet_cor_titulo", False),
    "Cor de fundo dos cards": ("intranet_cor_fundo_card", False),
    "Cor do texto dos cards (vazio = herda)": ("intranet_cor_texto_card", False),
    # Card Textos fixos
    "Nome do sistema no cabeçalho": ("titulo_sistema", False),
    "Título da tela de login": ("texto_login_titulo", False),
    "Subtítulo da tela de login": ("texto_login_subtitulo", False),
    "Ajuda abaixo do botão Entrar (login)": ("texto_login_hint", False),
    "Saudação da página inicial": ("texto_home_saudacao", False),
    "Frase abaixo da saudação (página inicial)": ("texto_home_subtitulo", False),
    "Texto do rodapé (versão anexada automaticamente)": ("texto_rodape", False),
    # Card Configurações gerais
    "Intervalo de backup (horas)": ("backup_interval_hours", False),
    "Retenção de sessão (dias)": ("sessao_retencao", False),
    "Tempo de exibição dos avisos (segundos)": ("notificacao_timeout", False),
    "Pasta raiz dos arquivos (BASE_DIR)": (None, True),
    # Card Ícones
    "Ícone do sistema (nome Material)": ("icone_sistema", False),
}


def _varrer():
    """Elementos da tela em ORDEM do DOM (BFS — índices = ordem de render)."""
    from collections import deque
    cli = list(Client.instances.values())[0]
    els = []
    fila = deque([cli.layout])
    while fila:
        e = fila.popleft()
        els.append(e)
        fila.extend(list(e))
    return els


def achar_campos(rotulo):
    return [e for e in _varrer()
            if isinstance(e, ValueElement) and e._props.get("label") == rotulo]


def achar_botoes(texto):
    return [e for e in _varrer()
            if isinstance(e, Button) and e.text == texto]


async def clicar(botao_el):
    """Dispara os handlers de clique do botão (fluxo real do NiceGUI).

    Suporta handlers síncronos e assíncronos (Aplicar via io_bound):
    se o handler devolver awaitable, aguarda a conclusão.
    """
    import inspect as _inspect
    for lst in list(botao_el._event_listeners.values()):
        if lst.type == "click" and lst.handler:
            ret = lst.handler(None)
            if _inspect.isawaitable(ret):
                await ret


async def clicar_seguro(botao_el):
    """clicar() capturando exceção — devolve None ou o erro."""
    try:
        await clicar(botao_el)
        return None
    except Exception as ex:
        return ex


def valor_padrao(chave):
    return PADRAO_CONFIG.get(chave, "") if chave else ""


class _ArquivoFake(Upload.FileUpload):
    """Upload.FileUpload em memória para simular o upload do favicon."""

    def __init__(self, nome, conteudo):
        super().__init__(name=nome, content_type="image/x-icon")
        self._conteudo = conteudo

    async def read(self):
        return self._conteudo

    async def text(self, encoding="utf-8"):
        return self._conteudo.decode(encoding, errors="replace")

    def iterate(self, *, chunk_size=1024 * 1024):
        async def _it():
            yield self._conteudo
        return _it()

    async def save(self, path):
        with open(path, "wb") as fh:
            fh.write(self._conteudo)

    def size(self):
        return len(self._conteudo)


async def main():
    global _OK, _TOTAL, mod_snapshot

    # ================== render da tela real (admin) ==================
    from mod_intranet import tela_configuracoes
    tela_configuracoes.mostrar_tela("master", "administrador_geral")

    # snapshot de tb_modulos (o teste restaura no fim)
    import mod_intranet.autenticacao as auth
    conn = auth.get_connection()
    try:
        mod_snapshot = list(conn.execute(
            "SELECT chave, nome, icone, rota, ativo, nativo, ordem FROM tb_modulos"))
    finally:
        conn.close()

    aplicar = achar_botoes("Aplicar")
    check(len(achar_botoes("APLICAR")) == 0,
          "sem botão APLICAR geral na barra do menu_mod")
    check(len(aplicar) == 9,
          "um botão 'Aplicar' por card (Cores, Textos, Gerais, Ícones, "
          "E-mail, Páginas, Obs, OTel, Banco)")

    # ================== 1) ATIVAÇÃO ==================
    print("-- ATIVAÇÃO (campo existe, habilitado e editável) --")
    for rotulo, (_chave, somente_leitura) in CAMPOS_CONFIG.items():
        achados = achar_campos(rotulo)
        ok_existe = len(achados) == 1
        check(ok_existe, f"campo '{rotulo}' existe (único)")
        if not ok_existe:
            continue
        el = achados[0]
        check(el.enabled is True, f"campo '{rotulo}' habilitado")
        eh_readonly = bool(el._props.get("readonly"))
        if somente_leitura:
            check(eh_readonly, f"campo '{rotulo}' é somente leitura (BASE_DIR)")
        else:
            check(not eh_readonly, f"campo '{rotulo}' é editável (não readonly)")
    achar_campos("Tamanho dos botões")
    ups = [e for e in _varrer() if isinstance(e, Upload)]
    check(len(ups) == 1, "campo de upload do favicon existe (único)")
    if ups:
        check(ups[0]._props.get("auto-upload") is True,
              "upload do favicon com auto-upload ativo")
    restaurar = achar_botoes("Restaurar padrão")
    check(len(restaurar) == 8,
          "8 botões 'Restaurar padrão' (um por card com rodapé padrão)")

    # ================== 2) VALOR INICIAL VEM DO BANCO ==================
    print("-- CONFIGURAÇÃO INICIAL (valor vigente do tb_config) --")
    for rotulo, (chave, _somente_leitura) in CAMPOS_CONFIG.items():
        if chave is None:
            continue
        achados = achar_campos(rotulo)
        if not achados:
            continue
        esperado = get_config(chave, valor_padrao(chave))
        check(achados[0].value == esperado,
              f"'{rotulo}' nasce com o valor do banco ({chave})")

    # ================== 3) APLICAR POR CARD SEM EDITAR (anti-zeramento) ==================
    print("-- Aplicar por card sem editar (grava de volta, não zera) --")
    _obs_calls.clear()
    _timer_calls.clear()
    _rb_calls.clear()
    horas_vigentes = get_config("backup_interval_hours", "12")
    erros = [(await clicar_seguro(b)) for b in aplicar]
    check(all(e is None for e in erros),
          "Aplicar de todos os cards sem edição roda sem crash")
    for k, v in ORIG.items():
        if v is None:
            continue
        check(get_config(k, None) == v,
              f"Aplicar sem editar preserva '{k}' (anti-zeramento)")
    check(len(_obs_calls) == 1,
          "Aplicar (Obs) reconfigura a observabilidade (1 chamada)")
    check(len(_timer_calls) == len(aplicar) - 1,
          "cada Aplicar agenda o recarregamento da página (ui.timer) — exceto Banco (exige restart)")
    check(all(a[0] == 1.0 for a in _timer_calls),
          "todos os Aplicar recarregam após 1 segundo")
    chaves_rb = {c for c, _h in _rb_calls}
    check(chaves_rb == set(_rotinas.MAPA_BACKUPS),
          "Aplicar (Gerais) reagenda o backup de todos os módulos")
    if _rb_calls:
        check(all(h == int(horas_vigentes or 12) for _c, h in _rb_calls),
              "reagendamento usa o intervalo vigente em horas")

    # ================== 4) EDIÇÃO DE TODOS OS CAMPOS → APLICAR POR CARD ==================
    print("-- EDIÇÃO de todos os campos → Aplicar por card grava na chave certa --")
    EDITAS = {
        "Cor primária (menus e destaques)": "#010203",
        "Cor de fundo das páginas": "#040506",
        "Cor geral do módulo": "#070809",
        "Cor do texto do módulo": "#0A0B0C",
        "Cor dos títulos dos cards": "#0D0E0F",
        "Cor de fundo dos cards": "#101112",
        "Tamanho dos botões": "large",
        "Cor do texto dos cards (vazio = herda)": "#131415",
        "Nome do sistema no cabeçalho": "TESTE APLICAR",
        "Título da tela de login": "LOGIN TÍTULO",
        "Subtítulo da tela de login": "LOGIN SUBTÍTULO",
        "Ajuda abaixo do botão Entrar (login)": "",
        "Saudação da página inicial": "Oi",
        "Frase abaixo da saudação (página inicial)": "FRASE HOME",
        "Texto do rodapé (versão anexada automaticamente)": "RODAPÉ QA",
        "Intervalo de backup (horas)": "24",
        "Retenção de sessão (dias)": "30",
        "Tempo de exibição dos avisos (segundos)": "5",
        "Ícone do sistema (nome Material)": "apartment",
    }
    for rotulo, novo in EDITAS.items():
        achados = achar_campos(rotulo)
        if achados:
            achados[0].set_value(novo)
    _obs_calls.clear()
    erros = [(await clicar_seguro(b)) for b in aplicar]
    check(all(e is None for e in erros),
          "Aplicar de todos os cards após editar roda sem crash")
    esperados = {
        "cor_principal": "#010203", "cor_fundo": "#040506",
        "intranet_cor_botao": "#070809",
        "intranet_cor_texto_botao": "#0A0B0C",
        "intranet_cor_titulo": "#0D0E0F",
        "intranet_cor_fundo_card": "#101112",
        "intranet_cor_texto_card": "#131415",
        "intranet_btn_tamanho": "large", "titulo_sistema": "TESTE APLICAR",
        "texto_login_titulo": "LOGIN TÍTULO",
        "texto_login_subtitulo": "LOGIN SUBTÍTULO",
        "texto_login_hint": "", "texto_home_saudacao": "Oi",
        "texto_home_subtitulo": "FRASE HOME", "texto_rodape": "RODAPÉ QA",
        "backup_interval_hours": "24", "sessao_retencao": "30",
        "notificacao_timeout": "5", "icone_sistema": "apartment",
    }
    for k, esperado in esperados.items():
        check(get_config(k, None) == esperado,
              f"Aplicar gravou '{k}' = {esperado!r}")
    check(len(_obs_calls) == 1, "Aplicar (Obs) também reconfigura observabilidade")

    # ================== 5) VALIDAÇÕES / SANEAMENTO ==================
    print("-- VALIDAÇÕES (entrada inválida saneada, sem crash) --")
    CLAMPS = {
        "Intervalo de backup (horas)": ("backup_interval_hours", "0", "1"),
        "Retenção de sessão (dias)": ("sessao_retencao", "-3", "1"),
        "Tempo de exibição dos avisos (segundos)": ("notificacao_timeout",
                                                    "99", "30"),
    }
    for rotulo, (_k, invalido, _e) in CLAMPS.items():
        achar_campos(rotulo)[0].set_value(invalido)
    erro = await clicar_seguro(aplicar[2])  # Aplicar do card Gerais
    check(erro is None, "Aplicar (Gerais) com limites estourados (0 / -3 / 99) sem crash")
    for rotulo, (k, _i, esperado) in CLAMPS.items():
        check(get_config(k, None) == esperado,
              f"'{rotulo}' com {CLAMPS[rotulo][1]!r} grava {esperado!r}")

    CLAMPS2 = {
        "Intervalo de backup (horas)": ("backup_interval_hours", "abc", "12"),
        "Retenção de sessão (dias)": ("sessao_retencao", "abc", "50"),
        "Tempo de exibição dos avisos (segundos)": ("notificacao_timeout",
                                                    "abc", "10"),
    }
    for rotulo, (_k, invalido, _e) in CLAMPS2.items():
        achar_campos(rotulo)[0].set_value(invalido)
    achar_campos("Tamanho dos botões")[0].set_value("gigante")
    achar_campos("Cor primária (menus e destaques)")[0].set_value("")
    erros = [(await clicar_seguro(aplicar[0])), (await clicar_seguro(aplicar[2]))]
    check(all(e is None for e in erros),
          "Aplicar (Cores/Gerais) com entrada não numérica ('abc') não derruba")
    for rotulo, (k, _i, esperado) in CLAMPS2.items():
        check(get_config(k, None) == esperado,
              f"'{rotulo}' com 'abc' grava o padrão {esperado!r}")
    check(get_config("intranet_btn_tamanho", None) == "medium",
          "tamanho inválido ('gigante') grava 'medium'")
    check(get_config("cor_principal", None) == PADRAO_CONFIG["cor_principal"],
          "cor primária vazia grava o padrão do sistema")

    # ================== 6) RESTAURAR PADRÃO (4 cards + Módulo) ==================
    print("-- RESTAURAR PADRÃO (Cores, Textos, Gerais, Ícones, Módulo) --")
    # Valores esperados após o restore: os codificados em cada card
    # (PADRAO_CONFIG; os do card Gerais são literais "12"/"50"/"10" na tela).
    GRUPOS = [
        ("Cores", {k: PADRAO_CONFIG[k] for k in (
            "cor_principal", "cor_fundo", "intranet_cor_botao",
            "intranet_cor_texto_botao", "intranet_btn_tamanho",
            "intranet_cor_titulo", "intranet_cor_fundo_card",
            "intranet_cor_texto_card")}),
        ("Textos fixos", {k: PADRAO_CONFIG[k] for k in (
            "titulo_sistema", "texto_login_titulo", "texto_login_subtitulo",
            "texto_login_hint", "texto_home_saudacao",
            "texto_home_subtitulo", "texto_rodape")}),
        ("Gerais", {"backup_interval_hours": "12", "sessao_retencao": "50",
                    "notificacao_timeout": "10"}),
        ("Ícones", {"icone_sistema": PADRAO_CONFIG["icone_sistema"]}),
    ]
    restaurar = achar_botoes("Restaurar padrão")
    set_config("favicon_custom", "1")
    for i, (nome_grupo, esperados) in enumerate(GRUPOS):
        _rb_calls.clear()
        antes = len(achar_botoes("Restaurar"))
        await clicar(restaurar[i])
        dialogo = achar_botoes("Restaurar")
        if len(dialogo) <= antes:
            check(False, f"'{nome_grupo}': diálogo de confirmação abre")
            continue
        check(achar_botoes("Cancelar") and len(dialogo) == antes + 1,
              f"'{nome_grupo}': diálogo com Cancelar + Restaurar")
        await clicar(dialogo[antes])
        falta = [k for k, v in esperados.items() if get_config(k, None) != v]
        check(not falta, f"'{nome_grupo}': banco volta ao padrão codificado"
                         + (f" — faltam {falta}" if falta else ""))
        campos_ok = True
        for rotulo, (k, _r) in CAMPOS_CONFIG.items():
            if k in esperados:
                el = achar_campos(rotulo)
                if not el or el[0].value != esperados[k]:
                    campos_ok = False
        check(campos_ok, f"'{nome_grupo}': campos voltam ao padrão na tela")
        if nome_grupo == "Gerais":
            check(all(h == 12 for _c, h in _rb_calls) and _rb_calls,
                  f"'{nome_grupo}': restore reagenda backups com 12h")
        if nome_grupo == "Ícones":
            check(get_config("favicon_custom", None) == "0",
                  f"'{nome_grupo}': favicon volta ao padrão (favicon_custom=0)")

    # ---- 6b) Módulo: páginas nativas voltam ao padrão (sem crash) ----
    print("-- MÓDULO: 'Restaurar padrão' das páginas nativas --")
    check(len(restaurar) == 8,
          "8 botões 'Restaurar padrão' (4 Config + E-mail + Páginas + "
          "Observabilidade + Telemetria)")
    antes = len(achar_botoes("Restaurar"))
    erro = await clicar_seguro(restaurar[5])  # Páginas do sistema (aba Módulo)
    check(erro is None, f"MÓDULO: abrir diálogo do restore sem crash"
          + (f" — erro: {erro}" if erro else ""))
    dialogo = achar_botoes("Restaurar")
    if len(dialogo) > antes:
        erro = await clicar_seguro(dialogo[antes])
        check(erro is None, f"MÓDULO: confirmar restore sem crash"
              + (f" — erro: {erro}" if erro else ""))
        conn = auth.get_connection()
        try:
            nativos = list(conn.execute(
                "SELECT chave, ativo, ordem FROM tb_modulos WHERE nativo=1 "
                "ORDER BY ordem"))
            ordens = [o for _c, _a, o in nativos]
            check(len(nativos) == len(auth.MODULOS_SISTEMA)
                  and all(a == 1 for _c, a, _o in nativos)
                  and ordens == list(range(1, len(nativos) + 1)),
                  "MÓDULO: nativos reativados e renumerados 1..N na ordem original")
        finally:
            conn.close()

    # ================== 7) FAVICON (upload) ==================
    print("-- FAVICON via upload (.ico válido / rejeições) --")
    from nicegui.events import UploadEventArguments
    upl = [e for e in _varrer() if isinstance(e, Upload)][0]
    handler = upl._upload_handlers[0]
    check(callable(handler), "handler on_upload do favicon registrado")

    erro_up = None
    try:
        await handler(UploadEventArguments(sender=upl, client=upl.client,
                                           file=_ArquivoFake("novo.ico", b"ICO-TESTE-123")))
    except Exception as ex:
        erro_up = ex
    check(erro_up is None, f"upload .ico válido sem crash"
          + (f" — erro: {erro_up}" if erro_up else ""))
    check(os.path.exists(FAV) and open(FAV, "rb").read() == b"ICO-TESTE-123",
          "upload .ico válido grava assets/favicon_atual.ico")
    check(get_config("favicon_custom", None) == "1",
          "upload .ico válido marca favicon_custom=1")
    try:
        await handler(UploadEventArguments(sender=upl, client=upl.client,
                                           file=_ArquivoFake("errado.png", b"PNG-FALSO")))
    except Exception:
        pass
    check(open(FAV, "rb").read() == b"ICO-TESTE-123",
          "extensão não .ico é recusada (arquivo intacto)")
    try:
        await handler(UploadEventArguments(sender=upl, client=upl.client,
                                           file=_ArquivoFake("vazio.ico", b"")))
    except Exception:
        pass
    check(open(FAV, "rb").read() == b"ICO-TESTE-123",
          "arquivo .ico vazio é recusado (arquivo intacto)")

    # ================== 8) ACESSO RESTRITO ==================
    print("-- ACESSO (não administrador_geral) --")
    tela_configuracoes.mostrar_tela("qa_usuario_inexistente", "comum")
    restricao = [e for e in _varrer()
                 if isinstance(e, Label)
                 and e.text == "Área de configuração restrita ao administrador geral."]
    check(len(restricao) >= 1,
          "usuário comum recebe a mensagem de restrição (sem campos)")


try:
    asyncio.run(main())
finally:
    # ---------- restauração do estado (banco + favicon + tb_modulos) ----------
    from mod_intranet.bd_conexao import get_connection
    from mod_intranet import autenticacao as _auth
    for k, v in ORIG.items():
        try:
            if v is None:
                conn = get_connection()
                try:
                    conn.execute("DELETE FROM tb_config WHERE chave=?", (k,))
                    conn.commit()
                finally:
                    conn.close()
            else:
                set_config(k, v)
        except Exception:
            pass
    try:
        conn = _auth.get_connection()
        try:
            for chave, nome, icone, rota, ativo, nativo, ordem in mod_snapshot:
                conn.execute(
                    "UPDATE tb_modulos SET nome=?, icone=?, rota=?, ativo=?, "
                    "nativo=?, ordem=? WHERE chave=?",
                    (nome, icone, rota, ativo, nativo, ordem, chave))
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass
    try:
        if FAV_TINHA:
            shutil.copy2(FAV_BKP, FAV)
            os.remove(FAV_BKP)
    except Exception:
        pass

print(f"RESULTADO: {_OK} OK, {_TOTAL - _OK} falha(s) "
      f"de {_TOTAL} verificações")
sys.exit(0 if _OK == _TOTAL else 1)
