# Pasta de testes — `assets/test/`

> Toda validação do sistema vive aqui como arquivo executável: nenhum teste
> existe só em conversa, comando avulso ou linha inline — tudo é roteiro
> versionado nesta pasta (scripts standalone `*.py` + specs E2E `e2e/*.spec.js`).

## Como rodar

```bash
.venv/bin/python assets/test/<arquivo>.py   # um teste isolado
.venv/bin/python assets/test/test_suite.py  # suíte direta, com progresso
.venv/bin/pytest                            # via pytest.ini → test_suite.py
cd assets/test && npm install && npm run test:e2e   # navegador (requer servidor :8080)
```

`test_suite.py` executa todo `*.py` em subprocesso (timeout 240s, `INTRANET_FORCE_SQLITE=1`)
e falha se algum sair ≠ 0. Exceções em `EXCLUIR` (`test_suite.py:23-32`): helpers
(`debug_boot`, `step_boot`, `diag_*`, `wtest`), geradores (`criar_postagens_blog`,
`fabrica_documentos`), destrutivos/ambiente (`test_fresh_install*`, `test_fase1_login`,
`validar_fase1_login`, `test_server`, `test_otel`).

## Convenções obrigatórias (todo teste novo)

1. **Standalone**: roda com `.venv/bin/python <arquivo>.py`, sem servidor, sem argumentos.
2. **Veredito por exit code**: `check(cond, msg)` conta OK/falha; `sys.exit(0 se tudo OK)`.
3. **Docstring bilíngue** EN no topo / PT-BR abaixo + linha `Execute:`.
4. **Sem destruição**: só escreve dados próprios (`qa_*`) ou faz snapshot/restore
   (`tb_config`, `tb_modulos`, uploads) com limpeza em `finally`.
5. **Seletores E2E** sempre por `data-testid` (nunca CSS/XPath); `clicar()` aguarda
   handlers `async` (`inspect.isawaitable`).
6. **Evidência de navegador** vira spec em `e2e/0N_*.spec.js` (helpers `login`,
   `coletarErros`, `errosFatais`); credenciais QA via `_garantir_credenciais.py`.

## Catálogo — validações das sessões de 14/09/2026

| Arquivo | O que cobre | Origem |
|---|---|---|
| `test_header_nome.py` (9) | Nome no header: tratamento `qacomum`/`qamaster`, botão único `header-nome-usuario`, sem `hidden sm:*`, CSS escopado, tooltip | Sessão: nome truncado `io de Teste QA C` |
| `e2e/04_header_nome.spec.js` | Render real: visível desktop/mobile, clique abre Meu Perfil | idem (evidência Playwright) |
| `test_rodape_hover.py` (7) | Rodapé: testid, CSS `opacity:0`→hover, faixa 5px, textos preservados | Sessão: rodapé auto-hide |
| `e2e/05_rodape_hover.spec.js` | opacity 0 → 1 no hover | idem |
| `test_blog_editor_imagens.py` (17) | Upload JPG/PNG (aceite/recusa 5MB/assinatura), nome `dataHora_usuario`, tag nh3, rota `/img_postagens`, job, expiração órfãs | Sessão: editor WYSIWYG + imagens |
| `test_blog_markdown_editor.py` (8) | Markdown em `<p>`/`<div>`/1ª solta, listas, negrito, `code/pre`, `#hashtag`, `div/br` | Sessões: Markdown não rendia |
| `test_blog_imagem_controles.py` (12) | `ajustar_imagem_html` (eixos, CSS autor, última img, sem-img) + feed respeita autor/padrão | Sessão: redimensionar/alinhar |
| `test_blog_mermaid_fim.py` (7) | Mermaid ao fim (`mover_mermaid_para_fim`), seeds conformes, centralização no render | Sessão: mermaid centralizado ao fim |
| `test_empenho_anotar.py` (7) | `anotar_arquivos`: levantamento, override `tb_empenhos`, fallbacks de nome | Sessão: Empenho/Parcela/Usuário |
| `test_ordem_modulos.py` (6) | Ordem padrão + `reordenar` 1-based + boot simulado preserva | Sessão: ordem resetava no restart |
| `e2e/06_blog_editor.spec.js` | Controles visíveis, preview Markdown, upload→centro+50%→publicar sem `float:left` | idem |

## Falhas preexistentes conhecidas (não causadas por esta sessão)

Verificadas em 14/09/2026 — os checks referenciam código anterior à sessão.
**Atualização 25/09/2026: ambas foram RESOLVIDAS nesta sessão.**

- ~~`test_dashboard.py` (7 checks)~~ — **resolvido em 25/09/2026** (7/7 OK):
  esperava o layout antigo do Resumo (`"Atualizado ✓"`, `ui.timer(2.0)`,
  microinterações `transition`/`hover`); o teste foi alinhado ao dashboard
  redesenhado (toast via `notificar`, timer 0.1).
- ~~`verifica_ui_comum.py` (1 check em 190)~~ — **resolvido em 25/09/2026**
  (**190/190 OK**): exigia `ui.tabs()` ausente em `mod_renomear_empenho/telas.py`;
  a barra do menu foi migrada para o helper padrão `aba_modulo.menu_modulo`
  (importado e sem uso até então), e os demais checks obsoletos foram reparados
  (`campo_texto` com contagem `>=`, `ui.notify` cru em `mod_edit_pdf`,
  organização de `notificacao_timeout`).

Além disso, em 25/09/2026 a suíte foi reparada de **10 scripts falhando → 0**:
bugs reais de `mod_filas` (predicado invertido em `contar_nomes_pendentes`,
`ORDER BY` invertido em `listar_nomes`), busca de 1 letra em
`mod_renomear_empenho` (FTS prefixo sem fallback substring), `ui.notify` cru em
`main.py` (guarda de admin), botão sem `data-testid` em `mod_filas`, e testes
obsoletos em `test_ordem_modulos` (6 → 10 módulos),
`test_tema_cache_trava`/`teste_config_intranet` (timeout padrão contraditório:
4 e 10 → 5, o valor do código), `test_filas_testids`
(`filas-midia-mutar` → `filas-midia-som`), `test_seg_novos_modulos` (gitleaks
por `shutil.which`) e `teste_carrossel_blog` (carrossel migrou de select
dedicado para seleção em lote por checkbox + campo `Tempo (s)`).

## Demais arquivos

- `fabrica_documentos.py` — fábrica de PDFs fictícios de empenho (massa de teste).
- `test_fabrica_documentos.py`, `teste_fluxo_*.py`, `test_*.py` — suítes por módulo/fluxo.
- `verifica_ui_comum.py` — checks byte-a-byte da fábrica de UI (190 verificações).
- `playwright.config.js`, `e2e/helpers.js`, `e2e/_global_setup.js` — infra E2E.
- `package.json` — deps Node do E2E (`@playwright/test`).
- `pdf/` — fixtures PDF para o editor de PDF.
