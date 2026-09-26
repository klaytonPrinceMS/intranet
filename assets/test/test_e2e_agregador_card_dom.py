"""EN: DOM regression tests for the mod_agregador_noticias card (Playwright).

Teste de REGRESSÃO de DOM do card do Agregador de Notícias (kbp-qa, 26/09/2026).

Valida no DOM o que o teste baseado em código NÃO pegava: quando `with ui.card()`
virou `_card = ui.card()`, as `card_section` passaram a ser IRMÃS do card, o CSS
descendente `.card-noticia .card-noticia__*` deixou de casar e o card renderizou
quebrado (miniatura estourando, texto preto sobre preto). Aqui a hierarquia é
verificada no DOM REAL, com JavaScript.

Verificações:
  1. `.card-noticia` EXISTE e tem FILHOS (não é casca vazia).
  2. `.card-noticia__rolagem` é DESCENDENTE de `.card-noticia` (hierarquia real).
  3. Altura computada = 250px (220px em viewport móvel).
  4. Miniatura 60x60.
  5. Marca d'água: `position: absolute`, `opacity: 0.5`, 20x20.
  6. Título e resumo NUNCA truncados (sem `-webkit-line-clamp`).
  7. UM ÚNICO container de scroll (`.card-noticia__rolagem`).
  8. Grade responsiva 3 → 2 → 1 colunas.

SOMENTE LEITURA: nenhum clique de escrita, nenhuma alteração no banco.

Execução (servidor vivo em localhost:8080):
    .venv/bin/python -m pytest assets/test/test_e2e_agregador_card_dom.py -v -m e2e
    .venv/bin/python assets/test/test_e2e_agregador_card_dom.py    # runner standalone

O bloco `__main__` existe de propósito: `test_suite.py` roda cada `*.py` de
`assets/test/` como SUBPROCESSO, e um arquivo só-de-pytest coletaria 0 testes e
sairia com 0 (falso positivo silencioso). O runner standalone dá sinal real.
"""

import os
import sys
import urllib.request

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

BASE_URL = "http://localhost:8080"
# Usuário de seed AGENTS.md §8.2 — `qamaster` é administrador_geral e tem
# acesso ao agregador_noticias. A senha do seed é 123456 e a troca ainda está
# PENDENTE (verificado no banco em 26/09/2026): por isso o diálogo de troca
# obrigatória aparece. Ele é `persistent` e não atrapalha — estes testes só
# MEDEM o DOM, nunca clicam na grade.
USUARIO_QA = "qamaster"
SENHA_QA = "123456"  # nosec B105 -- seed QA AGENTS.md §8.2, nunca produção

pytestmark = [pytest.mark.e2e]


# ================== JS: MÉTRICAS DO 1º CARD (espelha o CSS do módulo) ==================

JS_METRICAS_CARD = r"""
() => {
  const card = document.querySelector('.card-noticia');
  if (!card) return {achou: false};
  const rol = card.querySelector('.card-noticia__rolagem');
  const cs = (el) => el ? getComputedStyle(el) : null;
  const cardCs = cs(card);
  const titulo = card.querySelector('.card-noticia__titulo');
  const resumo = card.querySelector('.card-noticia__resumo');
  const titCs = cs(titulo);
  const resCs = cs(resumo);
  const marca = card.querySelector('.card-noticia__marca');
  const marcaCs = cs(marca);
  const midia = card.querySelector('.card-noticia__midia');
  const foto = card.querySelector('.card-noticia__foto');
  return {
    achou: true,
    filhosDiretos: card.children.length,
    rolDescendente: !!rol && card.contains(rol),
    alturaCard: card.getBoundingClientRect().height,
    alturaCardCss: cardCs ? cardCs.height : '',
    rolTemOverflowY: rol ? cs(rol).overflowY : null,
    containersScroll: card.querySelectorAll('.card-noticia__rolagem').length,
    midiaW: midia ? midia.getBoundingClientRect().width : 0,
    midiaH: midia ? midia.getBoundingClientRect().height : 0,
    fotoW: foto ? foto.getBoundingClientRect().width : 0,
    fotoH: foto ? foto.getBoundingClientRect().height : 0,
    marcaPosicao: marcaCs ? marcaCs.position : null,
    marcaOpacidade: marcaCs ? marcaCs.opacity : null,
    marcaW: marca ? marca.getBoundingClientRect().width : 0,
    marcaH: marca ? marca.getBoundingClientRect().height : 0,
    tituloLineClamp: titCs ? (titCs.webkitLineClamp || '') : null,
    resumoLineClamp: resCs ? (resCs.webkitLineClamp || '') : null,
    resumoTextAlign: resCs ? resCs.textAlign : null,
    temTituloNaRolagem: !!(rol && titulo && rol.contains(titulo)),
    temResumoNaRolagem: !!(rol && resumo && rol.contains(resumo)),
  };
}
"""


# ================== HELPERS ==================

def _servidor_ativo():
    """EN: True when localhost:8080 answers. PT-BR: True se localhost:8080 responde."""
    try:
        assert "localhost" in BASE_URL, "URL fora de localhost"
        with urllib.request.urlopen(BASE_URL + "/login", timeout=5) as resp:  # nosec B310 -- localhost fixo
            return resp.status in (200, 302)
    except Exception:
        return False


def _fazer_login(page):
    """EN: Login as the QA admin seed user. PT-BR: login com o usuário seed de QA."""
    page.goto(BASE_URL + "/login", wait_until="domcontentloaded")
    page.wait_for_timeout(1500)
    page.get_by_test_id("login-usuario").fill(USUARIO_QA)
    page.get_by_test_id("login-senha").fill(SENHA_QA)
    page.get_by_test_id("login-entrar").click()
    page.wait_for_timeout(3500)


def _abrir_agregador(page):
    """EN: Open the news screen and wait for cards. PT-BR: abre a tela e espera os cards."""
    page.goto(BASE_URL + "/agregador-noticias", wait_until="domcontentloaded")
    page.wait_for_selector(".card-noticia", timeout=30000)
    page.wait_for_timeout(1200)


def _m(page):
    """EN: Card metrics from the DOM. PT-BR: métricas do card vindas do DOM."""
    return page.evaluate(JS_METRICAS_CARD)


def _n_colunas(page):
    """EN: Number of grid columns. PT-BR: número de colunas da grade."""
    cols = page.evaluate(
        "() => getComputedStyle(document.querySelector('.grid-noticias')).gridTemplateColumns"
    )
    return len(str(cols).split())


# ================== CHECKS (uma função por regra; reusadas por pytest e __main__) ==================

def checar_card_tem_filhos(m):
    """EN: .card-noticia has children. PT-BR: .card-noticia tem FILHOS."""
    assert m.get("achou"), "nenhum .card-noticia encontrado na grade"
    assert m["filhosDiretos"] > 0, (
        ".card-noticia está VAZIO (0 filhos) — as seções saíram do card; "
        "hierarquia quebrada (regressão de `_card = ui.card()`)"
    )


def checar_rolagem_descendente(m):
    """EN: rolagem is a descendant of card. PT-BR: rolagem é descendente do card."""
    assert m.get("achou"), "nenhum .card-noticia encontrado"
    assert m["rolDescendente"], (
        ".card-noticia__rolagem NÃO é descendente de .card-noticia — "
        "hierarquia quebrada (o CSS descendente não casa)"
    )


def checar_altura_250(m):
    """EN: computed height 250px. PT-BR: altura computada 250px."""
    assert m.get("achou"), "nenhum .card-noticia encontrado"
    assert abs(m["alturaCard"] - 250) <= 2, (
        f"altura do card deveria ser 250px, veio {m['alturaCard']}px "
        f"(css height={m['alturaCardCss']!r})"
    )


def checar_altura_220_celular(m):
    """EN: computed height 220px on mobile. PT-BR: altura 220px no celular."""
    assert m.get("achou"), "nenhum .card-noticia encontrado no celular"
    assert abs(m["alturaCard"] - 220) <= 2, (
        f"altura no celular deveria ser 220px, veio {m['alturaCard']}px"
    )


def checar_miniatura_60(m):
    """EN: thumbnail frame/image 60x60. PT-BR: moldura e foto 60x60."""
    assert m.get("achou"), "nenhum .card-noticia encontrado"
    assert abs(m["midiaW"] - 60) <= 1, f"moldura da miniatura deveria ser 60px, veio {m['midiaW']}"
    assert abs(m["midiaH"] - 60) <= 1, f"altura da miniatura deveria ser 60px, veio {m['midiaH']}"
    assert abs(m["fotoW"] - 60) <= 2, f"foto deveria ser 60px, veio {m['fotoW']} (estourou?)"
    assert abs(m["fotoH"] - 60) <= 2, f"foto deveria ser 60px, veio {m['fotoH']} (estourou?)"


def checar_marca_agua(m):
    """EN: watermark absolute, opacity .5, 20x20. PT-BR: marca d'água absolute, .5, 20x20."""
    assert m.get("achou"), "nenhum .card-noticia encontrado"
    assert m["marcaPosicao"] == "absolute", (
        f"marca d'água deveria ser position:absolute, veio {m['marcaPosicao']!r}"
    )
    assert abs(float(m["marcaOpacidade"]) - 0.5) < 0.02, (
        f"marca d'água deveria ter opacity 0.5, veio {m['marcaOpacidade']}"
    )
    assert abs(m["marcaW"] - 20) <= 1, f"marca d'água deveria ser 20px, veio {m['marcaW']}"
    assert abs(m["marcaH"] - 20) <= 1, f"marca d'água deveria ser 20px, veio {m['marcaH']}"


def checar_nao_truncado(m):
    """EN: title/summary never clamped. PT-BR: título/resumo nunca truncados."""
    assert m.get("achou"), "nenhum .card-noticia encontrado"
    for campo in ("tituloLineClamp", "resumoLineClamp"):
        valor = m.get(campo)
        assert valor in (None, "", "none"), (
            f"{campo} está TRUNCADO por -webkit-line-clamp={valor!r} "
            f"(título/resumo não podem ser cortados)"
        )


def checar_resumo_justificado(m):
    """EN: summary text-align justify. PT-BR: resumo com text-align justify."""
    assert m.get("achou"), "nenhum .card-noticia encontrado"
    assert m.get("resumoTextAlign") == "justify", (
        f"resumo deveria ter text-align: justify, veio {m.get('resumoTextAlign')!r}"
    )


def checar_um_scroll(m):
    """EN: exactly one scroll container per card. PT-BR: UM container de scroll por card."""
    assert m.get("achou"), "nenhum .card-noticia encontrado"
    assert m["containersScroll"] == 1, (
        f"deveria haver EXATAMENTE 1 container de scroll, veio {m['containersScroll']}"
    )
    assert m["rolTemOverflowY"] == "auto", (
        f".card-noticia__rolagem deveria ter overflow-y:auto, veio {m['rolTemOverflowY']!r}"
    )


def checar_texto_dentro_da_rolagem(m):
    """EN: title and summary inside the scroll container. PT-BR: título/resumo dentro da rolagem."""
    assert m.get("achou"), "nenhum .card-noticia encontrado"
    assert m["temTituloNaRolagem"], "título fora do container de rolagem"
    assert m["temResumoNaRolagem"], "resumo fora do container de rolagem"


# ================== FIXTURES PYTEST ==================

@pytest.fixture(scope="session")
def browser_type_launch_args():
    """EN: Chromium flags for CI. PT-BR: flags do Chromium para CI."""
    return {"args": ["--no-sandbox"]}


@pytest.fixture(scope="session")
def card_logado(browser):
    """EN: Session-scoped logged-in page on /agregador-noticias.

    PT-BR: página logada (sessão) em /agregador-noticias.

    Escopo de SESSÃO de propósito: o login é caro (~5 s) e repeti-lo por teste
    deixava a auditoria lenta e frágil. Os testes são somente-leitura, então
    compartilhar a página é seguro.
    """
    if not _servidor_ativo():
        pytest.skip("servidor localhost:8080 fora do ar")
    contexto = browser.new_context(viewport={"width": 1440, "height": 1000})
    page = contexto.new_page()
    try:
        _fazer_login(page)
        _abrir_agregador(page)
        yield page
    finally:
        try:
            contexto.close()
        except Exception:
            pass


# ================== TESTES ==================

def test_card_tem_filhos_nao_e_casca_vazia(card_logado):
    """EN: .card-noticia has children — not an empty shell.

    PT-BR: .card-noticia tem FILHOS — não é casca vazia.

    Este é o teste que teria pegado a regressão de hierarquia: com
    `_card = ui.card()` as seções saíram IRMÃS do card, o card ficava
    sem conteúdo e o CSS descendente parava de casar.
    """
    checar_card_tem_filhos(_m(card_logado))


def test_rolagem_e_descendente_do_card(card_logado):
    """EN: .card-noticia__rolagem is a descendant of .card-noticia.

    PT-BR: .card-noticia__rolagem é DESCENDENTE de .card-noticia.
    """
    checar_rolagem_descendente(_m(card_logado))


def test_altura_computada_250px(card_logado):
    """EN: Card computed height is 250px on desktop. PT-BR: altura computada 250px."""
    checar_altura_250(_m(card_logado))


def test_miniatura_60x60(card_logado):
    """EN: Thumbnail frame and image are 60x60. PT-BR: moldura e imagem 60x60."""
    checar_miniatura_60(_m(card_logado))


def test_marca_agua_absolute_opacidade_050(card_logado):
    """EN: Source watermark position:absolute, opacity 0.5, 20x20.

    PT-BR: marca d'água position:absolute, opacity 0.5, 20x20.
    """
    checar_marca_agua(_m(card_logado))


def test_titulo_e_resumo_nao_truncados(card_logado):
    """EN: Title and summary are never clamped. PT-BR: nunca truncados."""
    checar_nao_truncado(_m(card_logado))


def test_resumo_justificado(card_logado):
    """EN: Summary uses text-align: justify. PT-BR: resumo com text-align justify."""
    checar_resumo_justificado(_m(card_logado))


def test_um_unico_container_de_scroll(card_logado):
    """EN: Exactly one scroll container per card. PT-BR: UM container de scroll por card."""
    checar_um_scroll(_m(card_logado))


def test_titulo_e_resumo_dentro_da_rolagem(card_logado):
    """EN: Title and summary live inside the scroll container.

    PT-BR: título e resumo ficam DENTRO do container de rolagem.
    """
    checar_texto_dentro_da_rolagem(_m(card_logado))


def test_grade_3_colunas_desktop(card_logado):
    """EN: Grid is 3 columns on desktop. PT-BR: grade com 3 colunas no desktop."""
    n = _n_colunas(card_logado)
    assert n == 3, f"grade deveria ter 3 colunas no desktop, veio {n}"


def test_grade_2_colunas_tablet(card_logado):
    """EN: Grid is 2 columns at <=1024px. PT-BR: grade com 2 colunas no tablet."""
    page = card_logado
    try:
        page.set_viewport_size({"width": 900, "height": 1000})
        page.wait_for_timeout(600)
        n = _n_colunas(page)
        assert n == 2, f"grade deveria ter 2 colunas no tablet, veio {n}"
    finally:
        page.set_viewport_size({"width": 1440, "height": 1000})
        page.wait_for_timeout(300)


def test_grade_1_coluna_e_altura_220_celular(card_logado):
    """EN: Grid is 1 column and card is 220px at <=640px.

    PT-BR: grade com 1 coluna e card com 220px no celular.
    """
    page = card_logado
    try:
        page.set_viewport_size({"width": 420, "height": 900})
        page.wait_for_timeout(600)
        n = _n_colunas(page)
        assert n == 1, f"grade deveria ter 1 coluna no celular, veio {n}"
        checar_altura_220_celular(_m(page))
    finally:
        page.set_viewport_size({"width": 1440, "height": 1000})
        page.wait_for_timeout(300)


# ================== RUNNER STANDALONE (sinal real na suíte por subprocesso) ==================

# Checks de viewport FIXA: todos medidos com a grade em 1440px.
_CHECKS_DESKTOP = (
    ("card tem filhos", checar_card_tem_filhos),
    ("rolagem descendente do card", checar_rolagem_descendente),
    ("altura 250px", checar_altura_250),
    ("miniatura 60x60", checar_miniatura_60),
    ("marca d'agua absolute/.5/20px", checar_marca_agua),
    ("titulo e resumo nao truncados", checar_nao_truncado),
    ("resumo justificado", checar_resumo_justificado),
    ("um unico container de scroll", checar_um_scroll),
    ("texto dentro da rolagem", checar_texto_dentro_da_rolagem),
)


def _rodar_standalone():
    """EN: Run every DOM check headless, exit non-zero on failure.

    PT-BR: roda todos os checks de DOM headless e sai com erro se algum falhar.
    """
    from playwright.sync_api import sync_playwright

    if not _servidor_ativo():
        print("SKIP: servidor localhost:8080 fora do ar")
        return 0
    print("INICIANDO TESTES - card do Agregador (DOM/Playwright, somente leitura)")
    nav = None
    ok = 0
    falhas = []
    try:
        with sync_playwright() as p:
            nav = p.chromium.launch(args=["--no-sandbox"])
            ctx = nav.new_context(viewport={"width": 1440, "height": 1000})
            page = ctx.new_page()
            try:
                _fazer_login(page)
                _abrir_agregador(page)

                # --- desktop ---
                m = _m(page)
                print(f"  DOM: filhos={m['filhosDiretos']} altura={m['alturaCard']}px "
                      f"rolagem_descendente={m['rolDescendente']} "
                      f"miniatura={m['fotoW']}x{m['fotoH']} "
                      f"marca={m['marcaPosicao']}/op={m['marcaOpacidade']}")
                for nome, fn in _CHECKS_DESKTOP:
                    try:
                        fn(m)
                        ok += 1
                        print(f"  OK [{ok}] {nome}")
                    except AssertionError as e:
                        falhas.append(f"{nome}: {e}")
                        print(f"  FALHOU {nome}: {e}")
                try:
                    n = _n_colunas(page)
                    assert n == 3, f"grade com 3 colunas no desktop, veio {n}"
                    ok += 1
                    print(f"  OK [{ok}] grade 3 colunas desktop")
                except AssertionError as e:
                    falhas.append(str(e))
                    print(f"  FALHOU grade 3 colunas desktop: {e}")

                # --- tablet (900px -> 2 colunas) ---
                page.set_viewport_size({"width": 900, "height": 1000})
                page.wait_for_timeout(600)
                try:
                    n = _n_colunas(page)
                    assert n == 2, f"grade com 2 colunas no tablet, veio {n}"
                    ok += 1
                    print(f"  OK [{ok}] grade 2 colunas tablet")
                except AssertionError as e:
                    falhas.append(str(e))
                    print(f"  FALHOU grade 2 colunas tablet: {e}")

                # --- celular (420px -> 1 coluna + card 220px) ---
                page.set_viewport_size({"width": 420, "height": 900})
                page.wait_for_timeout(600)
                try:
                    n = _n_colunas(page)
                    assert n == 1, f"grade com 1 coluna no celular, veio {n}"
                    checar_altura_220_celular(_m(page))
                    ok += 1
                    print(f"  OK [{ok}] grade 1 coluna + card 220px no celular")
                except AssertionError as e:
                    falhas.append(str(e))
                    print(f"  FALHOU grade 1 coluna + card 220px no celular: {e}")
            finally:
                try:
                    ctx.close()
                except Exception:
                    pass
    except Exception as e:  # noqa: BLE001
        falhas.append(f"erro geral do runner: {type(e).__name__}: {e}")
        print(f"  FALHOU erro geral do runner: {type(e).__name__}: {e}")
    finally:
        try:
            if nav is not None:
                nav.close()
        except Exception:
            pass

    total = ok + len(falhas)
    print(f"RESULTADO: {ok} OK, {len(falhas)} falha(s) de {total} verificações")
    if falhas:
        print("\nFALHAS:")
        for f in falhas:
            print(f"  - {f}")
    return 0 if not falhas else 1


if __name__ == "__main__":
    sys.exit(_rodar_standalone())
