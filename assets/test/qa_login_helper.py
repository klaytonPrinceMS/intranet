"""EN: Shared login helper for the QA Playwright tests.

PT-BR: Auxiliar de login compartilhado pelos testes Playwright de QA.

Existe por um motivo concreto: os seeds `qamaster` e `qacomum` nascem com
`forcar_troca=1`, então o 1º login abre o diálogo de troca obrigatória e a
tela fica bloqueada. Os testes Historically faziam `pytest.skip` nesse
caso — ou seja, **a cobertura Playwright rodava majoritariamente pulada**
sem que ninguém visse.

Aqui a troca é FEITA no teste, com a mesma senha de origem (o usuário só
precisa trocar, não tem direito de escolher outra). Depois disso o
`forcar_troca` é zerado no banco e a troca não acontece mais — então a
suíte funciona tanto numa instalação nova quanto numa já configurada.

Por que um módulo e não uma função em cada arquivo: `pw_cobertura_extra_qa`
e `pw_click_extra_qa` precisam do MESMO comportamento, e duplicar lógica
de login foi o que deixou a divergência passar.
"""
from __future__ import annotations

import sys
from pathlib import Path

BASE_URL = "http://localhost:8080"
QA_USUARIO = "qamaster"
QA_SENHA = "123456"
# mesma senha de origem: o fluxo só exige que a troca seja feita
QA_SENHA_NOVA = QA_SENHA


def _dialogo_troca_visivel(page) -> bool:
    """Diz se o diálogo de troca de senha está aberto na tela."""
    try:
        if page.locator(".q-dialog").count() == 0:
            return False
        dlg = page.locator(".q-dialog").first
        return dlg.is_visible() and ("troca" in (dlg.inner_text() or "").lower()
                                     or "senha" in (dlg.inner_text() or "").lower())
    except Exception:
        return False


def zerar_forcar_troca(usuario: str = QA_USUARIO) -> bool:
    """Desliga a troca obrigatória de senha do usuário de QA (idempotente).

    Depois da primeira troca feita pelo teste, a flag sai do caminho para as
    execuções seguintes. Vai por `autenticacao.marcar_trocar_senha`, e NÃO por
    `sqlite3` direto: o helper tem de funcionar também com `banco_tipo=postgres`
    (AGENTS.md §4.1 — os `db_mod_*.db` são legado quando o banco é Postgres).
    Fail-soft: devolve False se não conseguir, e o teste refaz a troca.
    """
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
        from mod_intranet import autenticacao
        autenticacao.marcar_trocar_senha(usuario, forcar=False)
        return True
    except Exception:
        return False


def fazer_login_com_troca(page, usuario: str = QA_USUARIO,
                          senha: str = QA_SENHA) -> bool:
    """Loga e, se a troca obrigatória aparecer, CONCLUI a troca.

    Devolve True quando há sessão utilizável. Não levanta: qualquer falha
    de infra vira False e quem chama decide pular.
    """
    try:
        page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(600)
        _preencher(page, "login-usuario", usuario)
        _preencher(page, "login-senha", senha)
        page.get_by_test_id("login-entrar").click()
        page.wait_for_timeout(2200)
    except Exception:
        return False

    if not _dialogo_troca_visivel(page):
        return "/" not in page.url or "login" not in page.url

    # --- troca obrigatória: preenche com a MESMA senha e confirma ---
    if not concluir_troca(page, senha_atual=senha, senha_nova=QA_SENHA_NOVA):
        return False
    zerar_forcar_troca(usuario)
    return not _dialogo_troca_visivel(page)


def _preencher(page, testid: str, valor: str) -> None:
    """Preenche um campo pelo data-testid, seja ele o input ou um wrapper.

    Os testids do login ficam no PRÓPRIO `<input>`; os de outras telas
    podem estar num wrapper. `Playwright.fill()` exige o input, então
    descemos até ele quando preciso.
    """
    loc = page.get_by_test_id(testid)
    alvo = loc if loc.evaluate("e => e.tagName === 'INPUT'") else loc.locator("input")
    alvo.fill(valor)


def concluir_troca(page, senha_atual: str, senha_nova: str) -> bool:
    """EN: Completes the mandatory password-change dialog.

    PT-BR: Conclui o diálogo de troca obrigatória de senha.

    Assume que a sessão JÁ está logada e o diálogo aberto — não faz
    login. Separado de `fazer_login_com_troca` porque recarregar a página
    aqui destruiria o próprio diálogo que o teste precisa resolver.
    """
    try:
        if not _dialogo_troca_visivel(page):
            return True
        campos = page.locator(".q-dialog input[type=password]")
        if campos.count() < 3:
            return False
        campos.nth(0).fill(senha_atual)               # senha atual
        campos.nth(1).fill(senha_nova)                 # nova
        campos.nth(2).fill(senha_nova)                 # confirmar
        botao = page.get_by_role("button", name="Salvar nova senha")
        if botao.count() == 0:
            botao = page.locator(".q-dialog button").last
        botao.click()
        #aguarda a confirmação ("Senha alterada com sucesso") e o sumiço do diálogo
        try:
            page.wait_for_function(
                "() => document.querySelectorAll('.q-dialog').length === 0",
                timeout=15000)
        except Exception:
            return False
        return True
    except Exception:
        return False
