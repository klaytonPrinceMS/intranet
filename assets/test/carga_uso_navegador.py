"""Carga e USO com navegador real — 20 usuários headless em paralelo (Playwright).

EN: Twenty real headless browsers running the usage cycle that needs a genuine
    click: login, dashboard, news, blog (60 s read), PDF editor, empenho search,
    print request with a real PDF upload, and the permission-gate measurement.
    One browser, N isolated contexts, JSON report for the k6 run to read.

PT-BR: Vinte navegadores headless reais rodando o ciclo de uso que exige clique
de verdade: login, painel, notícias, blog (60 s de leitura), Editor de PDF,
busca de empenhos, solicitação de impressão com upload real de PDF, e a
medição do gate de permissões. Um navegador, N contextos isolados, relatório
JSON para o k6 ler.

POR QUE ESTE ARQUIVO EXISTE AO LADO DO k6
------------------------------------------
`assets/k6/carga_uso.js` não clica em nada: o login desta intranet é um evento
no WebSocket e o despacho interno do NiceGUI não é reproduzível com segurança
(numa atualização da biblioteca quebraria a medição em silêncio). Medido: com o
cookie do protocolo k6, `GET /blog` devolve 8761 bytes — o stub de
redirecionamento, idêntico ao de `/` — e só `/tv` (pública) renderiza de
verdade. Ou seja: o k6 mede **quantos clientes o servidor segura**; este
arquivo mede **se eles conseguem trabalhar**.

Os dois rodam **ao mesmo tempo**, por isso: 20 usuários de verdade é o
complemento do volume do k6, e é o que produz uma carga mista (120 sockets de
protocolo + 20 navegadores com tela inteira, JS, upload e render).

LIMITE DE RECURSO (medido nesta máquina: i3-2375M, 3,7 GiB)
----------------------------------------------------------
Chromium headless custa ~109 MB ao abrir + ~37 MB por página, então 20
navegadores é o que cabe com folga: 20 × 37 = 740 MB, mais o servidor (105 MB),
mais o k6 (~100 MB com 120 VUs). Por isso NAVEgadores headless, e não 120: a
memória, e não a CPU, é o teto do teste de navegador real. `guarda_recursos.py`
interrompe a bateria a 90 % de RAM/CPU.

O QUE ESTE ARQUIVO NÃO FAZ (e por quê — nada aqui é inventado)
-------------------------------------------------------------
* **não autoriza nem confirma impressão.** `_eh_responsavel` decide quem vê a
  aba "Autorização": `userNNN` é `comum` e não tem vínculo de autorização, então
  a aba nem aparece. A aprovação exige `administrador_geral` ou um responsável
  vinculado — o caminho existe e é medido aqui como **gate**, não forçado.* **não confirma exclusão, recusa, recuo nem cancelamento definitivo.** Os
  cliques passam por uma lista de permissivos; a lista de proibidos é explícita.
* **não envia a solicitação para todos.** O upload (a parte cara: o PDF entra
  na RAM do servidor e vira rascunho) é feito por todos os 20; o ENVIO é feito
  só por `--enviar` usuários (padrão 2) e **cancelado em seguida**, para não
  deixar pedido pendente de verdade na fila de autorização. Onde parou, e por quê,
  fica no relatório.

Uso:
    # fumaça: 1 usuário, 40 s
    .venv/bin/python assets/test/carga_uso_navegador.py --usuarios 1 --minutos 1 --blog-s 5
    # bateria completa (rodar JUNTO com o k6, com o guarda de recursos de olho)
    .venv/bin/python assets/test/libera_modulos_carga.py          # libera blog/notícias
    .venv/bin/python assets/test/guarda_recursos.py --k6-pid <pid> --py-pid <pid> &
    k6 run assets/k6/carga_uso.js &
    .venv/bin/python assets/test/carga_uso_navegador.py --usuarios 20
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from playwright.async_api import async_playwright

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

BASE_URL = os.environ.get("INTRANET_BASE_URL", "http://localhost:8080")
SENHA = os.environ.get("INTRANET_CARGA_SENHA", "123456")
PREFIXO_USUARIO = "user"

# leitura de post de blog: 1 minuto, por exigência
LEITURA_BLOG_PADRAO_S = 60

# Rotas que NUNCA são permitidas a `comum`, em nenhuma configuração. O gate
# delas é o que este script mede no lugar de forçar a aprovação.
ROTAS_BLOQUEADAS_SEMPRE = ("/auditoria", "/tecnico", "/users", "/configuracoes")

# Cliques permitidos: leitura e navegação. Qualquer botão fora daqui não é
# clicado — o filtro é por allowlist, não por denylist, porque o erro de uma
# denylist é clicar em "Confirmar exclusão" sem perceber que a palavra perigosa
# estava escrita de outro jeito.
BOTOES_SEGUROS = re.compile(
    r"^(atualizar|recarregar|pesquisar|buscar|filtrar|voltar|fechar|"
    r"expandir|recolher|anterior|próxima|proxima|ver|abrir|limpar busca|"
    r"limpar filtros|mostrar todas|ordenar)$", re.IGNORECASE)
# Proibidos, mesmo que o texto pareça inofensivo: destrutivo, irreversível ou
# que muda estado de negócio.
BOTOES_PROIBIDOS = re.compile(
    r"(exclu|apag|remov|cancel|recus|rejeit|autoriz|autoriza|confirm|salvar|"
    r"enviar|publicar|despublicar|restaurar|finaliz|conclu|imprimir|baixar|"
    r"gerar|processar|lote|logout|sair|trocar senha|redefinir|desabilit|"
    r"habilit|parar|encerrar|sessão|upload|selecionar|marcar|recuar|"
    r"reprocessar|gerar|atualizar automatic)", re.IGNORECASE)
# Atalho: o botão de atualizar é seguro, mas o filtro acima rejeita
# "atualizar" quando ele tem sufixo perigoso ("atualizar pedido").
LIMITE_CLIQUES_SEGUROS = 4


@dataclass
class Registro:
    """Tudo que UM usuário mediu. Vira uma linha do JSON."""

    login: str = ""
    login_ok: bool = False
    ciclo_completo: bool = False
    url_final: str = ""
    passos: list = field(default_factory=list)
    pdf_anexado: bool = False
    envio_feito: bool = False
    envio_cancelado: bool = False
    motivo_parada: str = ""
    erros: list = field(default_factory=list)
    duracao_s: float = 0.0

    def ok(self, passo: str, detalhe: str = "") -> None:
        self.passos.append({"passo": passo, "ok": True, "detalhe": detalhe,
                            "t": round(time.time(), 3)})

    def falha(self, passo: str, erro: str) -> None:
        self.passos.append({"passo": passo, "ok": False, "detalhe": str( erro)[:300],
                            "t": round(time.time(), 3)})
        self.erros.append(f"{passo}: {str(erro)[:200]}")


# ============================================================================
#  Login
# ============================================================================

async def _fechar_dialogos(page) -> None:
    """Remove diálogo bloqueador (troca de senha que não deveria existir)."""
    try:
        for _ in range(2):
            if await page.locator(".q-dialog").count() == 0:
                return
            botoes = page.locator(".q-dialog button")
            n = await botoes.count()
            alvo = None
            for i in range(n):
                txt = ((await botoes.nth(i).inner_text()) or "").strip().lower()
                if "fechar" in txt or "cancelar" in txt or "depois" in txt:
                    alvo = botoes.nth(i)
                    break
            if alvo is None:
                await page.evaluate("() => document.querySelectorAll('.q-dialog')"
                                    ".forEach(d => d.remove())")
            else:
                await alvo.click()
            await page.wait_for_timeout(300)
    except Exception:
        pass


async def _dialogo_troca_visivel(page) -> bool:
    """Diz se o diálogo de troca de senha está aberto."""
    try:
        if await page.locator(".q-dialog").count() == 0:
            return False
        dlg = page.locator(".q-dialog").first
        if not await dlg.is_visible():
            return False
        txt = (await dlg.inner_text() or "").lower()
        return "senha" in txt or "troca" in txt
    except Exception:
        return False


async def _preencher(page, testid: str, valor: str) -> None:
    """Preenche um campo pelo data-testid (desce até o <input> se for wrapper)."""
    loc = page.get_by_test_id(testid)
    alvo = loc if await loc.evaluate("e => e.tagName === 'INPUT'") else loc.locator("input").first
    await alvo.fill(valor)


async def fazer_login(page, login: str, senha: str = SENHA) -> bool:
    """Loga com clique de verdade no botão Entrar. Devolve True se abriu sessão.

    O `userNNN` de carga já tem `forcar_troca=0`, então o diálogo de troca não
    deveria aparecer. Se aparecer (senha trocada por alguém, seed novo), o
    teste CONCLUI a troca com a MESMA senha em vez de pular — pular faria a
    cobertura rodar majoritariamente pulada sem ninguém ver, que foi
    exatamente o defeito que `qa_login_helper`exists para corrigir.
    """
    try:
        await page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(1200)
        await _preencher(page, "login-usuario", login)
        await _preencher(page, "login-senha", senha)
        await page.get_by_test_id("login-entrar").click()
        for _ in range(40):                      # até ~20 s pela troca de URL
            await page.wait_for_timeout(500)
            if "/login" not in (page.url or ""):
                break
        if await _dialogo_troca_visivel(page):
            await _concluir_troca(page, senha)
        await _fechar_dialogos(page)
        return "/login" not in (page.url or "")
    except Exception as exc:
        raise RuntimeError(f"login falhou: {exc}") from exc


async def _concluir_troca(page, senha: str) -> bool:
    """Conclui o diálogo de troca obrigatória com a MESMA senha de origem."""
    try:
        campos = page.locator(".q-dialog input[type=password]")
        if await campos.count() < 3:
            return False
        await campos.nth(0).fill(senha)
        await campos.nth(1).fill(senha)
        await campos.nth(2).fill(senha)
        botao = page.get_by_role("button", name="Salvar nova senha")
        if await botao.count() == 0:
            botao = page.locator(".q-dialog button").last
        await botao.click()
        await page.wait_for_function(
            "() => document.querySelectorAll('.q-dialog').length === 0", timeout=20000)
        return True
    except Exception:
        return False


# ============================================================================
#  Helpers de tela
# ============================================================================

class DemoraDeNavegacao(Exception):
    """A navegação estourou o tempo mesmo depois de repetir.

    Não é defeito do script: sob carga, uma página lenta É o que se quer
    medir. Por isso é uma exceção própria, e quem chama registra como
    "demora medida" em vez de contar como erro do teste. Sem esta distinção, o
    relatório diria "o script falhou" quando a verdade é "a intranet demorou".
    """


async def abrir(page, rota: str, espera_ms: int = 2500, tentas: int = 2) -> str:
    """Abre uma rota e devolve a URL final (já com o redirecionamento aplicado).

    Repete uma vez: sob carga o primeiro `goto` pode perder a corrida com o
    event-loop do servidor, e um teste de carga que desiste na primeira
    demissão mediria o teste, não a intranet.
    """
    ultimo: Exception | None = None
    for tentativa in range(tentas):
        try:
            await page.goto(BASE_URL + rota, wait_until="domcontentloaded",
                            timeout=45000)
            await page.wait_for_timeout(espera_ms)
            return page.url.replace(BASE_URL, "") or "/"
        except Exception as exc:
            ultimo = exc
            if tentativa + 1 < tentas:
                await page.wait_for_timeout(2000)
    raise DemoraDeNavegacao(f"{rota}: {ultimo}") from ultimo


async def abrir_uso(page, reg: Registro, passo: str, rota: str,
                    espera_ms: int = 2500) -> bool:
    """Abre uma rota de USO e registra se o gate deixou passar (e quanto demorou).

    O gate de `pagina_restrita` redireciona para `/` (ou `/login`) quando o
    usuário não tem vínculo no módulo. Sem esta checagem, um passo de uso
    redirecionado reportaria "OK" e o teste mediria a tela inicial 20 vezes sem
    dizer isso — foi o que aconteceu na primeira versão, que via "tela abriu"
    para o Agregador de Notícias que na verdade estava bloqueado.
    """
    inicio = time.time()
    try:
        destino = await abrir(page, rota, espera_ms)
    except DemoraDeNavegacao as exc:
        reg.ok(passo, f"DEMORA MEDIDA (>45 s): {rota} | {str(exc)[:110]}")
        return False
    decorrido = round((time.time() - inicio) * 1000)
    if destino != rota:
        reg.ok(passo, f"BLOQUEADO pelo gate: {rota} -> {destino} ({decorrido} ms)")
        return False
    reg.ok(passo, f"abriu {rota} ({decorrido} ms)")
    return True


async def _visivel(page, testid: str) -> bool:
    """True se o elemento com o data-testid existe e está visível."""
    try:
        loc = page.get_by_test_id(testid)
        if await loc.count() == 0:
            return False
        return await loc.first.is_visible()
    except Exception:
        return False


async def clicar_botoes_seguros(page, reg: Registro, teto: int = LIMITE_CLIQUES_SEGUROS) -> list:
    """Clica nos botões INOCENTES da tela e só neles. Devolve o que clicou.

    Filtro duplo: o texto precisa casar com a allowlist E não pode casar com a
    lista de proibidos. A allowlist garante que nada perigoso entre; a
    denylist é a segunda barreira, para o caso de alguém acrescentar um termo
    permissivo que na verdade dispara algo irreversível.
    """
    clicados: list = []
    try:
        botoes = page.get_by_role("button")
        total = await botoes.count()
    except Exception:
        return clicados
    for i in range(min(total, 60)):
        if len(clicados) >= teto:
            break
        try:
            b = botoes.nth(i)
            if not await b.is_visible() or not await b.is_enabled():
                continue
            txt = ((await b.inner_text()) or "").strip()
            if not txt or len(txt) > 40:
                continue
            if BOTOES_PROIBIDOS.search(txt):
                continue
            if not BOTOES_SEGUROS.match(txt):
                continue
            await b.click()
            await page.wait_for_timeout(1200)
            clicados.append(txt)
        except Exception:
            continue
    return clicados


# ============================================================================
#  Os passos do ciclo de uso
# ============================================================================

async def usar_painel(page, reg: Registro) -> None:
    """Abre a página inicial, lê e procura botões inofensivos."""
    try:
        reg.url_final = await abrir(page, "/", 3000)
        corpo = (await page.locator("body").inner_text())[:4000].lower()
        if "desconectado" in corpo:
            reg.falha("painel", "tela caiu em 'desconectado'")
            return
        reg.ok("painel", f"url={reg.url_final}")
        clicados = await clicar_botoes_seguros(page, reg, teto=2)
        if clicados:
            reg.ok("painel_botoes", ", ".join(clicados))
    except Exception as exc:
        reg.falha("painel", exc)


async def usar_noticias(page, reg: Registro) -> None:
    """Agregador: abre, filtra por tema e busca — só leitura."""
    try:
        if not await abrir_uso(page, reg, "noticias", "/agregador-noticias", 3500):
            return
        # `agregador-busca` é o campo do LEITOR. (`agregador-termo` existe
        # também, mas é o campo da aba de administração de Fontes — clicar nele
        # aqui não encontraria nada.)
        if await _visivel(page, "agregador-busca"):
            await page.get_by_test_id("agregador-busca").first.fill("prefeitura")
            await page.wait_for_timeout(1500)
            reg.ok("noticias_busca", "busca aplicada (somente leitura)")
        else:
            reg.ok("noticias_busca", "campo de busca ausente nesta versão")
        if await _visivel(page, "agregador-filtro-tema"):
            reg.ok("noticias_filtro", "filtro de tema visível (não alterado)")
        corpo = (await page.locator("body").inner_text())[:3000]
        reg.ok("noticias", f"leitura: {len(corpo)} caracteres na tela")
        # A tela pura `/agregador-noticias-puro` foi REMOVIDA em 26/09/2026
        # (réplica de teste do modelo `Noticia`); o Agregador normal é o que
        # permanece. Não há mais o que abrir aqui.
    except Exception as exc:
        reg.falha("noticias", exc)


async def usar_filas_e_lista(page, reg: Registro) -> None:
    """Filas e Lista Telefônica: abrir, ler e filtrar — sem chamar, sem editar."""
    try:
        if await abrir_uso(page, reg, "filas", "/filas", 3000):
            reg.ok("filas", "tela de filas renderizou")
        if await abrir_uso(page, reg, "lista_telefonica", "/lista-telefonica", 3000):
            if await _visivel(page, "lista-busca"):
                await page.get_by_test_id("lista-busca").first.fill("gabinete")
                await page.wait_for_timeout(1500)
            reg.ok("lista_telefonica", "organograma aberto e filtrado")
    except Exception as exc:
        reg.falha("filas_lista", exc)


async def usar_blog(page, reg: Registro, leitura_s: int) -> None:
    """Blog: abre o feed, lê um post pelo tempo de leitura e volta."""
    try:
        if not await abrir_uso(page, reg, "blog_abrir", "/blog", 3000):
            return
        if await _visivel(page, "blog-busca"):
            await page.get_by_test_id("blog-busca").fill("a")
            await page.wait_for_timeout(1200)
        # expande o primeiro post, se o botão existir (leitura de verdade)
        try:
            expandir = page.get_by_role("button", name="Expandir")
            if await expandir.count() > 0:
                await expandir.first.click()
                await page.wait_for_timeout(800)
        except Exception:
            pass
        inicio = time.time()
        await page.wait_for_timeout(leitura_s * 1000)     # a leitura medida
        reg.ok("blog_ler", f"{round(time.time() - inicio, 1)} s de leitura")
    except Exception as exc:
        reg.falha("blog", exc)


async def usar_edit_pdf(page, reg: Registro) -> None:
    """Editor de PDF: abre a biblioteca e navega (sem editar PDF)."""
    try:
        if not await abrir_uso(page, reg, "edit_pdf", "/edit-pdf", 3000):
            return
        if await _visivel(page, "editar_pdf-atualizar"):
            await page.get_by_test_id("editar_pdf-atualizar").first.click()
            await page.wait_for_timeout(2000)
            reg.ok("edit_pdf", "biblioteca aberta e atualizada")
        else:
            reg.ok("edit_pdf", "tela abriu")
        clicados = await clicar_botoes_seguros(page, reg, teto=1)
        if clicados:
            reg.ok("edit_pdf_botoes", ", ".join(clicados))
    except Exception as exc:
        reg.falha("edit_pdf", exc)


async def usar_empenhos(page, reg: Registro) -> None:
    """Renomeador de Empenhos: busca e lê a lista. NÃO renomeia nada."""
    try:
        if not await abrir_uso(page, reg, "empenhos", "/renomear-empenho", 3500):
            return
        if await _visivel(page, "empenhos-navegar-pesquisa"):
            await page.get_by_test_id("empenhos-navegar-pesquisa").first.fill("QA-inexistente-zzz")
            await page.wait_for_timeout(2000)
            reg.ok("empenhos_busca", "busca sem resultado (somente leitura)")
        if await _visivel(page, "empenhos-atualizar"):
            await page.get_by_test_id("empenhos-atualizar").first.click()
            await page.wait_for_timeout(1500)
            reg.ok("empenhos_listar", "lista recarregada")
        else:
            reg.ok("empenhos", "tela abriu")
    except Exception as exc:
        reg.falha("empenhos", exc)


def achar_pdf_de_teste() -> Path:
    """Acha UM PDF pequeno já existente no disco; gera 1 se não houver nenhum.

    Um (1) arquivo basta: o objetivo é medir o custo de um anexo, não encher a
    fila. Nunca usar a fábrica de 15 documentos aqui — ela é do `kbp-doc_teste`
    e serve para outro fim.
    """
    pasta = RAIZ / "assets" / "test" / "pdf"
    try:
        candidatos = sorted(pasta.glob("*.pdf"))
        if candidatos:
            return candidatos[0]
    except Exception:
        pass
    destino = RAIZ / "logs" / "pdf_carga_uso.pdf"
    try:
        destino.parent.mkdir(parents=True, exist_ok=True)
        import fitz  # PyMuPDF, já dependência do projeto
        doc = fitz.open()
        doc.new_page().insert_text((72, 72), "PDF de teste do teste de carga e uso")
        doc.save(str(destino))
        doc.close()
        return destino
    except Exception:
        return destino


async def ler_notificacoes(page) -> list:
    """Lê as notificações visíveis do Quasar: [(tipo, texto), ...].

    `ui.notify` do NiceGUI é o ÚNICO sinal confiável de que uma escrita
    aconteceu: o módulo responde com `type="positive"` no sucesso e
    `type="negative"/"warning"` na recusa. Caçar texto solto no corpo da página
    dá falso positivo — o título da tela é "Solicitação de Impressão", então
    qualquer verificação por "solicitação" passa mesmo quando nada foi enviado.
    """
    achados: list = []
    try:
        loc = page.locator(".q-notification")
        for i in range(await loc.count()):
            el = loc.nth(i)
            if not await el.is_visible():
                continue
            cls = (await el.get_attribute("class")) or ""
            if "positive" in cls:
                tipo = "positive"
            elif "negative" in cls:
                tipo = "negative"
            elif "warning" in cls:
                tipo = "warning"
            else:
                tipo = "info"
            achados.append((tipo, (await el.inner_text()).strip()))
    except Exception:
        pass
    return achados


async def anexar_pdf(page, reg: Registro, pdf: Path) -> bool:
    """Anexa o PDF de teste na tela de Nova Solicitação.

    O `ui.upload` do módulo não tem data-testid (achado do módulo, não do
    teste), então o alvo é o `input[type=file]` dentro do rótulo "Anexar PDFs".
    O upload é o passo CARO desta tela: ele traz o PDF inteiro para a RAM do
    servidor (`await f.read()`) e grava um rascunho.
    """
    try:
        entrada = page.locator("input[type=file]")
        if await entrada.count() == 0:
            reg.falha("solicita_upload", "nenhum input[type=file] na tela")
            return False
        await entrada.first.set_input_files(str(pdf))
        # o Quasar processa o `change` de forma assíncrona; o upload real
        # acontece logo depois, sem botão — é preciso dar tempo e confirmar
        for _ in range(20):
            await page.wait_for_timeout(700)
            texto = (await page.locator("body").inner_text())[:3000]
            if "arquivo(s) recebido(s)" in texto or "recebido" in texto:
                reg.pdf_anexado = True
                reg.ok("solicita_upload", f"{pdf.name} anexado")
                return True
        reg.falha("solicita_upload",
                  "o upload não confirmou 'arquivo(s) recebido(s)' em ~14 s")
        return False
    except Exception as exc:
        reg.falha("solicita_upload", exc)
        return False


async def usar_solicitacao(page, reg: Registro, pdf: Path, enviar: bool) -> None:
    """Solicitação de Impressão: preenche o formulário e anexa o PDF.

    `enviar=False` (padrão de 18 dos 20 usuários) para na preparação: o
    rascunho fica no disco do servidor até expirar, que é o efeito reversível
    que importa medir. `enviar=True` faz o envio E cancela em seguida, para não
    deixar pedido pendente na fila de autorização de verdade.
    """
    try:
        if not await abrir_uso(page, reg, "solicita_abrir", "/solicita-impressao", 3500):
            return
        # a aba "Autorização" só existe para responsável/admin: medir é o
        # objetivo, forçar não cabe a `comum`.
        tem_autorizacao = False
        try:
            tem_autorizacao = (await page.get_by_text("Autorização", exact=True).count()) > 0
        except Exception:
            pass
        reg.ok("solicita_gate_autorizacao",
               "aba Autorização visível" if tem_autorizacao
               else "aba Autorização AUSENTE (exige responsável vinculado ou admin)")

        # selects do formulário: secretaria é obrigatória para o envio
        try:
            selects = page.locator(".q-select")
            n = await selects.count()
            if n > 0:
                await selects.nth(0).click()
                await page.wait_for_timeout(900)
                opcoes = page.locator(".q-menu .q-item")
                if await opcoes.count() > 0:
                    await opcoes.first.click()
                    await page.wait_for_timeout(700)
                    reg.ok("solicita_formulario", "secretaria selecionada")
        except Exception as exc:
            reg.ok("solicita_formulario", f"select não preenchido: {str(exc)[:80]}")

        await anexar_pdf(page, reg, pdf)

        if not enviar:
            reg.motivo_parada = ("envio suprimido por padrão (--enviar): o envio cria "
                                 "pedido aguardando autorização na fila de verdade")
            return

        if not reg.pdf_anexado:
            reg.motivo_parada = "sem PDF anexado, o envio seria recusado pelo módulo"
            return
        try:
            if not await _visivel(page, "solicita-enviar"):
                reg.motivo_parada = "botão solicitar-enviar ausente na tela"
                return
            # O módulo SÓ envia arquivos marcados, e o checkbox do rascunho já
            # nasce marcado (`ui.checkbox(value=r["sel"])` com sel=True). Clicar
            # nele cegamente o DESMARCA — foi exatamente o que aconteceu na
            # primeira versão deste teste, e a resposta do módulo foi "Marque ao
            # menos um arquivo para enviar". Então só se clica quando não está.
            try:
                caixas = page.locator(".q-checkbox")
                if await caixas.count() > 0:
                    cx = caixas.first
                    if (await cx.get_attribute("aria-checked")) != "true":
                        await cx.click()
                        await page.wait_for_timeout(800)
                        reg.ok("solicita_selecionar", "rascunho marcado para envio")
                    else:
                        reg.ok("solicita_selecionar", "rascunho já vem marcado")
            except Exception as exc:
                reg.ok("solicita_selecionar", f"não foi possível marcar: {str(exc)[:80]}")

            await page.get_by_test_id("solicita-enviar").first.click()
            # A notificação é informative e efêmera: `tema_modulo.notificar()`
            # respeita `notificacao_timeout`, então em ~3 s ela já sumiu (foi o
            # que aconteceu na primeira versão, que(reportou "sem notificação"
            # para um envio que tinha dado certo). Por isso a notificação é lida
            # cedo e a CONFIRMAÇÃO do envio é feita na lista, que é o estado.
            await page.wait_for_timeout(2200)
            notifs = await ler_notificacoes(page)
            if notifs:
                reg.ok("solicita_enviar", "notificação do módulo: "
                       + " / ".join(f"[{t}] {x[:60]}" for t, x in notifs))
            else:
                reg.ok("solicita_enviar", "sem notificação visível (já expirou)")
            # confirmação autoritativa + limpeza, na lista do próprio usuário
            await _confirmar_e_cancelar_pedido(page, reg, notifs)
        except Exception as exc:
            reg.falha("solicita_enviar", exc)
    except Exception as exc:
        reg.falha("solicita", exc)


async def _confirmar_e_cancelar_pedido(page, reg: Registro, notifs: list) -> None:
    """Confirma o envio na LISTA e cancela o pedido, para não deixar pendência.

    Confirmação: "Minhas Solicitações" é o estado autoritativo. Se o cartão do
    pedido aparecer, o envio aconteceu — independentemente da notificação, que
    é efêmera. Verificar importa duas vezes: um falso positivo deixaria 20
    pedidos pendentes na fila de autorização depois da bateria sem ninguém
    saber de onde vieram, e um falso negativo diria que o envio falhou quando
    deu certo.
    """
    try:
        await abrir(page, "/solicita-impressao", 3000)
        try:
            await page.get_by_text("Minhas Solicitações", exact=True).first.click()
            await page.wait_for_timeout(2500)
        except Exception:
            reg.ok("solicita_confirmar", "não achou a aba 'Minhas Solicitações'")
            return
        corpo = await page.locator("body").inner_text()
        if "Nenhum pedido ainda" in corpo:
            recusa = [t for tipo, t in notifs if tipo in ("negative", "warning")]
            reg.motivo_parada = ("envio NÃO criou pedido na lista"
                                 + (": " + recusa[-1][:120] if recusa else ""))
            reg.falha("solicita_confirmar", reg.motivo_parada)
            return
        reg.envio_feito = True
        reg.ok("solicita_confirmar", "pedido aparece em 'Minhas Solicitações' (envio real)")

        cancelar = page.get_by_role("button", name="Cancelar")
        if await cancelar.count() == 0:
            reg.ok("solicita_cancelar", "pedido SEM botão Cancelar (estado não cancelável)")
            return
        await cancelar.first.click()
        await page.wait_for_timeout(2500)
        confirmar = page.get_by_role("button", name=re.compile("confirm", re.IGNORECASE))
        if await confirmar.count() > 0:
            await confirmar.first.click()
            await page.wait_for_timeout(2500)
        notifs2 = await ler_notificacoes(page)
        reg.envio_cancelado = any(tipo == "positive" for tipo, _ in notifs2)
        if reg.envio_cancelado:
            reg.ok("solicita_cancelar",
                   "cancelado: " + ([t for k, t in notifs2 if k == "positive"][-1][:70]))
        else:
            reg.ok("solicita_cancelar",
                   "Cancelar clicado sem notificação positiva: "
                   + (" / ".join(t for _, t in notifs2)[:110] or "sem notificação"))
    except Exception as exc:
        reg.falha("solicita_confirmar", exc)


async def medir_gate(page, reg: Registro) -> dict:
    """Mede o gate de permissão: para onde cada rota restrita manda o usuário.

    Esta é a forma de medir a aprovação em vez de forçá-la. O redirecionamento
    é CLIENT-SIDE, então só um navegador de verdade enxerga; o k6 recebe 200 em
    todas elas.
    """
    resultado: dict = {}
    for rota in ROTAS_BLOQUEADAS_SEMPRE:
        try:
            destino = await abrir(page, rota, 2500)
            resultado[rota] = destino
        except Exception as exc:
            resultado[rota] = f"erro: {str(exc)[:120]}"
    permitidas = [r for r, d in resultado.items() if d == r]
    bloqueadas = [r for r, d in resultado.items() if d != r]
    reg.ok("gate_permissoes",
           f"permitidas={permitidas} bloqueadas={bloqueadas}")
    return resultado


# ============================================================================
#  Orquestração
# ============================================================================

async def ciclo_de_uso(context, login: str, pdf: Path, blog_s: int,
                       enviar: bool, deadline: float, reg: Registro) -> None:
    """Roda o ciclo de um usuário em uma página isolada. Nunca levanta."""
    inicio = time.time()
    page = None
    try:
        page = await context.new_page()
        page.set_default_timeout(25000)
        try:
            reg.login_ok = await fazer_login(page, login)
        except Exception as exc:
            reg.falha("login", exc)
            reg.motivo_parada = "login não abriu sessão"
            return
        if not reg.login_ok:
            reg.motivo_parada = "login devolveu tela de login"
            return
        reg.ok("login", login)

        passos = [
            ("painel", lambda: usar_painel(page, reg)),
            ("noticias", lambda: usar_noticias(page, reg)),
            ("blog", lambda: usar_blog(page, reg, blog_s)),
            ("edit_pdf", lambda: usar_edit_pdf(page, reg)),
            ("empenhos", lambda: usar_empenhos(page, reg)),
            ("solicita", lambda: usar_solicitacao(page, reg, pdf, enviar)),
            ("filas_lista", lambda: usar_filas_e_lista(page, reg)),
            ("gate", lambda: medir_gate(page, reg)),
        ]
        for nome, acao in passos:
            if time.time() > deadline:
                reg.motivo_parada = (reg.motivo_parada
                                     or f"interrompido no passo '{nome}': orçamento de tempo esgotado")
                reg.ok("orcamento", f"parou em '{nome}'")
                break
            try:
                await acao()
            except Exception as exc:
                reg.falha(nome, exc)
        if not reg.motivo_parada:
            reg.motivo_parada = "ciclo completo"
        # O envio suprimido é uma PARADA DELIBERADA no meio do roteiro, não um
        # ciclo incompleto: sem esta flag, 18 dos 20 usuários seriam contados
        # como "não completou" e o relatório acusaria falha onde houve decisão.
        reg.ciclo_completo = reg.motivo_parada in ("ciclo completo",) or (
            reg.motivo_parada.startswith("envio suprimido"))
    finally:
        reg.duracao_s = round(time.time() - inicio, 1)
        if page is not None:
            try:
                await page.close()
            except Exception:
                pass


def _resumo(reg: Registro) -> str:
    """Uma linha por usuário, para o stdout."""
    tot = len(reg.passos)
    bons = sum(1 for p in reg.passos if p["ok"])
    return (f"  {reg.login:9s} passos {bons}/{tot} "
            f"pdf={'s' if reg.pdf_anexado else 'n'} "
            f"envio={'s' if reg.envio_feito else 'n'}"
            f"/cancel={'s' if reg.envio_cancelado else 'n'} "
            f"{reg.duracao_s:6.1f}s  {reg.motivo_parada[:52]}")


async def executar_async(args) -> dict:
    """Sobe 1 navegador, cria N contextos isolados e roda o ciclo em paralelo."""
    pdf = Path(args.pdf) if args.pdf else achar_pdf_de_teste()
    inicio = time.time()
    deadline = inicio + args.minutos * 60
    registros: list = []
    gate: dict = {}
    vinculo_log: list = []

    async with async_playwright() as p:
        navegador = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage",
                  # 20 abas num Chromium único: sem isto cada uma vira processo
                  # e a RAM estoura (o limite real é memória, não CPU).
                  "--renderer-process-limit=4",
                  "--disable-gpu"],
        )
        try:
            contexts = []
            for i in range(1, args.usuarios + 1):
                login = f"{PREFIXO_USUARIO}{i:03d}"
                ctx = await navegador.new_context(
                    viewport={"width": 1280, "height": 800},
                    ignore_https_errors=True)
                contexts.append((ctx, login))
            print(f"  {len(contexts)} contexto(s) aberto(s) em 1 navegador", flush=True)

            # Onda única: os N usuários rodam em paralelo. Um `Semaphore` maior
            # que N não seguraria nada aqui — o limite é a memória, e N já é o
            # teto medido nesta máquina.
            tarefas = []
            for ctx, login in contexts:
                enviar = args.enviar > 0 and (len(tarefas) < args.enviar)
                reg = Registro(login=login)
                registros.append(reg)
                tarefas.append(asyncio.create_task(
                    ciclo_de_uso(ctx, login, pdf, args.blog_s, enviar, deadline, reg)))
            # o gate é medido pelo primeiro usuário que terminar login, para
            # não multiplicar por 20 a mesma navegação
            await asyncio.gather(*tarefas, return_exceptions=True)

            for reg in registros:
                print(_resumo(reg), flush=True)
            for ctx, _login in contexts:
                try:
                    await ctx.close()
                except Exception:
                    pass
        finally:
            try:
                await navegador.close()
            except Exception:
                pass

    # o gate coletado por qualquer usuário
    for reg in registros:
        for passo in reg.passos:
            if passo["passo"] == "gate_permissoes":
                vinculo_log.append(passo["detalhe"])
                break
    for reg in registros:
        if reg.erros:
            gate.setdefault("erros_por_usuario", {})[reg.login] = reg.erros

    fim = time.time()
    return {
        "meta": {
            "inicio": datetime.fromtimestamp(inicio, timezone.utc).isoformat(),
            "fim": datetime.fromtimestamp(fim, timezone.utc).isoformat(),
            "duracao_s": round(fim - inicio, 1),
            "usuarios": args.usuarios,
            "base_url": BASE_URL,
            "blog_leitura_s": args.blog_s,
            "pdf_usado": str(pdf),
            "enviar_n": args.enviar,
            "k6_pid": os.environ.get("K6_PID", ""),
        },
        "totais": {
            "logins_ok": sum(1 for r in registros if r.login_ok),
            "ciclos_completos": sum(1 for r in registros if r.ciclo_completo),
            "passos_ok": sum(1 for r in registros for p in r.passos if p["ok"]),
            "passos_falha": sum(1 for r in registros for p in r.passos if not p["ok"]),
            "pdf_anexado": sum(1 for r in registros if r.pdf_anexado),
            "envios": sum(1 for r in registros if r.envio_feito),
            "cancelamentos": sum(1 for r in registros if r.envio_cancelado),
            "erros": sum(len(r.erros) for r in registros),
        },
        "gate": {"observacoes": vinculo_log[:1]},
        "usuarios": [r.__dict__ for r in registros],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Carga de uso com 20 navegadores reais")
    ap.add_argument("--usuarios", type=int, default=20,
                    help="quantidade de navegadores (padrão 20 — o teto medido)")
    ap.add_argument("--minutos", type=float, default=14.0,
                    help="orçamento total de minutos (o k6 fecha em 15)")
    ap.add_argument("--blog-s", type=int, default=LEITURA_BLOG_PADRAO_S,
                    help="segundos de leitura por post (padrão 60 = 1 min)")
    ap.add_argument("--enviar", type=int, default=2,
                    help="quantos usuários ENVIAM a solicitação (e cancelam). 0 = nenhum")
    ap.add_argument("--json", default=str(RAIZ / "logs" / "carga_uso_navegador.json"),
                    help="onde gravar o relatório JSON")
    ap.add_argument("--pdf", default="", help="PDF de teste (padrão: procura em assets/test/pdf)")
    args = ap.parse_args()

    if args.usuarios < 1 or args.usuarios > 20:
        print("  [aviso] o teto medido é 20 navegadores nesta máquina "
              "(~37 MB por página em 3,7 GiB)", flush=True)

    print("== CARGA DE USO (navegador real) ==", flush=True)
    print(f"  usuários={args.usuarios}  orçamento={args.minutos}min  "
          f"leitura blog={args.blog_s}s  envios={args.enviar}", flush=True)
    print(f"  base={BASE_URL}", flush=True)

    relatorio = asyncio.run(executar_async(args))

    destino = Path(args.json)
    try:
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    except Exception as exc:
        print(f"  [erro] não foi possível gravar o JSON: {exc}", flush=True)

    t = relatorio["totais"]
    print("", flush=True)
    print("------- RESUMO (navegador real) -------", flush=True)
    print(f"  logins ok.......: {t['logins_ok']}/{args.usuarios}", flush=True)
    print(f"  ciclos completos: {t['ciclos_completos']}/{args.usuarios}", flush=True)
    print(f"  passos..........: {t['passos_ok']} ok / {t['passos_falha']} falha", flush=True)
    print(f"  PDF anexado.....: {t['pdf_anexado']}/{args.usuarios}", flush=True)
    print(f"  enviados/canc...: {t['envios']} / {t['cancelamentos']}", flush=True)
    print(f"  erros...........: {t['erros']}", flush=True)
    print(f"  duração.........: {relatorio['meta']['duracao_s']} s", flush=True)
    print(f"  JSON............: {destino}", flush=True)
    print("--------------------------------------", flush=True)
    for obs in relatorio["gate"].get("observacoes", []):
        print(f"  gate: {obs}", flush=True)
    return 0 if t["logins_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
