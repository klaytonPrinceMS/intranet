# Test Cases — Intranet Modular

> Test cases and scripts available under `test/`. Manual scripts executed with the venv Python (no framework).

---

# Testes — Casos — Intranet Modular

> Casos de teste e scripts disponíveis em `test/`. Scripts manuais executados com o Python do venv (sem framework).

## Scripts disponíveis

| Script | Escopo |
|:---|:---|
| `test_server.py` | Smoke test do servidor (sobe e valida) |
| `test/teste_aba_config_intranet.py` | Aba Config de `/configuracoes` campo a campo (render headless da tela real: ativação/habilitação/editabilidade — BASE_DIR readonly, valores iniciais do `tb_config`, APLICAR sem editar com anti-zeramento + reconfiguração de observabilidade + reagendamento de backups + reload, edição dos 19 campos → chaves corretas, saneamento 0/-3/99/"abc"/"gigante"/cor vazia, "Restaurar padrão" dos 4 cards + páginas nativas da aba Módulo, upload de favicon (.ico aplica; .png e vazio recusados) e acesso restrito a não-admin; autocontido — snapshot/restore de `tb_config`, favicon e `tb_modulos`) |
| `test_auditoria.py` | Auditoria (12 verificações: banco exclusivo `db_mod_auditoria.db`/tabela por módulo, rastreabilidade IP/UA, poda por retenção, acesso exclusivo do admin geral, preferência de campos/ordem por usuário) |
| `test_editor_pdf.py` | Editor PDF ponta a ponta (32 verificações: hash SHA-256, redução, união, corte, divisão, cotas, auditoria, expiração) |
| `test_solicita_impressao.py` | Solicitação de impressão (fórmula, cadastros, fluxo, cota, marca d'água, rascunho/expiração) |
| `test_fase1_login.py` / `validar_fase1_login.py` | Login (fase 1) |
| `test_fresh_install.py` / `fresh_install_test*.py` | Boot/seed (move os `.db` reais temporariamente — não interromper; desde 14/09/2026 com caminho absoluto a partir da raiz — roda de qualquer CWD sem criar `.db` de 0 bytes fora do lugar) |
| `diag_db.py` / `diag_config.py` | Diagnóstico de banco/config (`diag_db.py` desde 14/09/2026 com caminho absoluto — idem acima) |
| `step_boot.py` / `debug_boot.py` / `wtest.py` | Auxiliares de boot/depuração |

## Catálogo `data-testid` — drawer / menu hambúrguer

> EN — Drawer `data-testid` catalog (all set via `.props('data-testid=...')` in `mod_intranet/ui_comum.py:852-937` factory `ItemMenuDrawer`/`item_menu_drawer` and `mod_intranet/telas.py:218-332`): use these selectors in Playwright/pytest-playwright (`page.get_by_test_id(...)`), never CSS/XPath.

> PT — Catálogo de `data-testid` do drawer (todos aplicados via `.props('data-testid=...')` na fábrica `ItemMenuDrawer`/`item_menu_drawer` em `mod_intranet/ui_comum.py:852-937` e no drawer em `mod_intranet/telas.py:218-332`): use estes seletores no Playwright/pytest-playwright (`page.get_by_test_id(...)`), nunca CSS/XPath.

| `data-testid` | Onde | Quem vê | Ação |
|:---|:---|:---|:---|
| `menu-hamburguer` | Header (`telas.py:216-220`, `botao_icone "menu"`) — `aria-label="Abrir menu de navegação"` | todos os perfis logados | alterna (`toggle`) o `ui.left_drawer` (inicia fechado, `value=False`) |
| `menu-home` | Drawer (`telas.py:255-261`), fábrica com `ativo=(not chave_modulo)` | todos | navega para `/` |
| `menu-<chave>` | Drawer (`telas.py:266-272`), um por módulo ATIVO de `autenticacao.modulos_do_usuario()` (ex. `menu-blog`, `menu-usuarios`) — `aria-current="page"` quando `ativo` | só quem tem vínculo válido (`validar_acesso_modulo`) | navega para a rota do módulo |
| `menu-<chave>-indisponivel` | Drawer (`telas.py:274-287`), módulo com vínculo remanescente mas DESATIVADO — `aria-label="<nome> — módulo indisponível"`, visual laranja `bg-orange-2 border-orange-6` | só quem mantém o vínculo | só `notificar()` warning — NÃO navega |
| `menu-admin` | Drawer (`telas.py:299-306`), rótulo `Administração` (ou `Administração (sistema)` na Home) | só `administrador_geral` (`perfil_global_de() == "administrador_geral"`) — `comum` e `administrador_modulo` NÃO veem | navega para `/admin/<chave>` (ou `/configuracoes` na Home) |
| `menu-docs` | Drawer (`telas.py:309-316`), rótulo `Documentação` | só `administrador_geral` | abre `/documentacao` em nova aba |
| `menu-sair` | Drawer (`telas.py:319-324`), rótulo `Sair` | todos | `_logout` (encerra sessão) |

Notas de acessibilidade da fábrica (`ui_comum.py:883-918`): `ui.item` `w-full rounded-lg my-0.5` + `.style('min-width: 0')`, seção avatar com ícone `text-primary shrink-0` + `aria-hidden="true"`, rótulo `truncate max-w-full grow`, tooltip PT-BR, anel `focus-visible:ring-2`, estado ativo `bg-blue-100 font-bold` + `aria-current="page"`; item só-ícone (rótulo vazio) recebe `aria-label`. Falha de montagem = fail-soft (`None` + log exception).

## Catálogo `data-testid` — header do usuário (correção final 14/09/2026) + botão TEMP dos empenhos

> EN — Header username button (`mod_intranet/telas.py:225-260`) and temporary empenho mass-generation button (`mod_renomear_empenho/telas.py:153-183`): use `page.get_by_test_id(...)`, never CSS/XPath.

> PT — Botão de nome do usuário no header (`mod_intranet/telas.py:225-260`) e botão TEMPORÁRIO de massa dos empenhos (`mod_renomear_empenho/telas.py:153-183`): use `page.get_by_test_id(...)`, nunca CSS/XPath.

| `data-testid` | Onde | Quem vê | Esperado |
|:---|:---|:---|:---|
| `header-nome-usuario` | Header direita, **sempre visível** (`max-width: min(28ch, 55vw)` + ellipsis à direita, `tooltip` = nome completo, CSS escopado `[data-testid="header-nome-usuario"] .q-btn__content` ancora à esquerda) — origem `autenticacao.nome_de_tratamento` (nome social, fallback login) | todos os perfis logados | rótulo = nome de tratamento completo; nomes longos preservam o início com ellipsis à direita; clique abre "Meu Perfil" (`_dialogo_meu_perfil`) |
| `empenhos-gerar-25-temp` | `/renomear-empenho`, totalmente à direita do `menu_mod` — **TEMPORÁRIO QA** (`TEMPORARIO-25-ARQUIVOS-REMOVER-EM-PRODUCAO`, `telas.py:153-183`) | quem acessa empenhos (QA) | cada clique = +25 PDFs fictícios via `criar_lote_principal(..., quantidade=25)` + `audit_log(...,"gerar_massa_temp",...)`; **REMOVER antes de produção** |

!!! warning "REGRA DE PROJETO — nunca usar `hidden sm:*` / `hidden md:*` neste stack"
    O `tailwindcss.min.js` embutido no NiceGUI 3.15 resolve `hidden` acima de `sm:flex`/`md:block` mesmo a 1280 px (probe com div pura confirmou `display:none`). `header-nome-curto` foi **REMOVIDO** por esse motivo — os seletores de teste usam só `header-nome-usuario`, nunca CSS/XPath.

Roteiro manual: desktop 1280 — `header-nome-usuario` visível com nome completo + tooltip, clique abre "Meu Perfil"; mobile 360 — mesmo botão visível com início preservado + ellipsis à direita (ex. "Usuário de Teste QA C…") + tooltip completo, clique abre "Meu Perfil"; badge de perfil sempre visível. Botão TEMP: clicar 1x → `notificar` positiva `"<N> arquivos criados na pasta doc."` e +25 PDFs na pasta `doc`.

## Catálogo `data-testid` — rodapé do sistema (14/09/2026)

> EN — System footer (`mod_intranet/telas.py:346-359`, part 4 of the layout): hidden by default, reveals on hover/focus. Use `page.get_by_test_id(...)`, never CSS/XPath.

> PT — Rodapé do sistema (`mod_intranet/telas.py:346-359`, parte 4 do layout): escondido por padrão, revela no hover/foco. Use `page.get_by_test_id(...)`, nunca CSS/XPath.

| `data-testid` | Onde | Quem vê | Esperado |
|:---|:---|:---|:---|
| `rodape-sistema` | `ui.footer` (`bg-grey-8 w-full`, `telas.py:359`), CSS escopado `[data-testid="rodape-sistema"]` via `ui.add_head_html` | todos os perfis logados | escondido por padrão (`opacity:0 + translateY(calc(100% - 5px))`, faixa de 5px como pista); `:hover`/`:focus-within` → `opacity:1 + transform:none`; conteúdo inalterado (`"INTRANET Básica — uso interno"`, `v1.0.260913`); sem JS, sem `hidden` |

Roteiro manual: rodapé quase invisível no carregamento (só a faixa de 5px); passar o mouse (ou focar por teclado) sobre a faixa → rodapé aparece com texto e versão; tirar o mouse → esconde de novo. No touch, tocar na faixa revela (rodapé só informativo, sem focáveis); se o CSS falhar, degrada para sempre visível.

## Catálogo `data-testid` — editor do Blog (14/09/2026)

> EN — Blog editor (`mod_blog/telas.py:506-562`, card "Nova publicação", admin only): use `page.get_by_test_id(...)`, never CSS/XPath.
>
> PT — Editor do Blog (`mod_blog/telas.py:506-562`, card "Nova publicação", só admin): use `page.get_by_test_id(...)`, nunca CSS/XPath.

| `data-testid` | Onde | Quem vê | Esperado |
|:---|:---|:---|:---|
| `blog-titulo` | Card "Nova publicação" (`ui.input "Título*"`) | só quem `pode_publicar` (admin geral / admin do módulo `blog`) | recebe o título; vazio + Publicar → aviso "Preencha título e conteúdo" |
| `blog-conteudo` | Card "Nova publicação" (`ui.editor` WYSIWYG, placeholder `Olá, <nome>! ...`) | só quem `pode_publicar` | recebe HTML/texto; imagens entram como `<img src="/img_postagens/<nome>" style="max-width:100%;height:auto;">` |
| `blog-imagem-selecionar` | Linha de upload (`ui.upload`, `accept=.jpg,.jpeg,.png`, `auto_upload=False`, máx 5 MB) | só quem `pode_publicar` | abre o seletor de arquivo (só JPG/PNG) |
| `blog-imagem-enviar` | Botão Enviar (`run_method("upload")`) | só quem `pode_publicar` | dispara o upload → tag inserida no editor + `notify` positiva; arquivo inválido → `notify` negativa |
| `blog-img-esq` | Linha "Imagem:" (`telas.py:629`, botão `format_align_left`, `botao_icone`) | só quem `pode_publicar` | alinha a ÚLTIMA `<img>` à esquerda (`float:left`); sem imagem → `notify` warning |
| `blog-img-centro` | Linha "Imagem:" (botão `format_align_center`) | só quem `pode_publicar` | centraliza a ÚLTIMA `<img>` (`display:block;margin:auto`); sem imagem → `notify` warning |
| `blog-img-dir` | Linha "Imagem:" (botão `format_align_right`) | só quem `pode_publicar` | alinha a ÚLTIMA `<img>` à direita (`float:right`); sem imagem → `notify` warning |
| `blog-img-largura` | Linha "Imagem:" (`ui.select`, `telas.py:643` — 25%/50%/75%/100%/Original, default `100%`) | só quem `pode_publicar` | aplica `max-width` à ÚLTIMA `<img>` (`Original` = remove e volta ao padrão 200–400px); preserva o alinhamento atual |

## Roteiro manual — Markdown no WYSIWYG + controles da imagem (14/09/2026)

> EN — Manual Blog Markdown-in-WYSIWYG + image controls checklist (admin profile, real browser): `#`/`-`/`**` typed in the editor convert on preview/publish (first line loose + other lines in `<div>`, normalized to `<p>`); `#` requires a trailing space (`#text` stays literal, CommonMark as on GitHub); image buttons + width select apply to the last `<img>`; author style wins over defaults in the feed.
>
> PT — Roteiro manual do Markdown no WYSIWYG + controles da imagem (perfil admin, navegador real): `#`/`-`/`**` digitados no editor convertem na pré-visualização/publicação (1ª linha solta + demais em `<div>`, normalizadas para `<p>`); `#` exige espaço (`#texto` fica literal, CommonMark como no GitHub); botões de imagem + seletor de largura aplicam-se à última `<img>`; o estilo do autor vence o padrão no feed.

Pré-condição: sistema reiniciado, `/login` 200, logado como admin (geral ou do módulo `blog`); suíte `assets/test/teste_fluxo_blog.py` 46/46; posts de QA excluídos (soft) ao final.

| # | Passo | Esperado |
|:---|:---|:---|
| M1 | No editor, digitar `# Título`, `## Seção`, `### Sub` (cada um em uma linha, usando Enter — o QEditor gera a 1ª solta e as demais em `<div>`) + abrir **Pré-visualização** | pré-visualização mostra `<h1>`/`<h2>`/`<h3>` centralizados — nenhuma linha colada nem literal |
| M1b | Digitar `#sem-espaço` no início da linha → pré-visualizar | fica literal `#sem-espaço` (regra CommonMark: `#` exige espaço, como no GitHub) |
| M2 | Digitar `- item` (2 linhas) e `**negrito**` → pré-visualizar | lista `<ul><li>` e negrito — nada literal |
| M2b | Digitar `#hashtag` no meio de uma frase + bloco de código com `# não-título` → pré-visualizar | `#hashtag` continua texto; código intacto (sem conversão) |
| M2c | Digitar 3 linhas de texto puro com Enter (sem Markdown) → pré-visualizar | 3 parágrafos separados (as `<div>` do editor preservadas, não coladas em uma linha só) |
| M3 | Enviar imagem, clicar `blog-img-esq` → pré-visualizar | imagem à esquerda no preview |
| M4 | Clicar `blog-img-centro` + escolher `50%` em `blog-img-largura` → **Publicar** | feed rende `display:block;margin:auto` + `max-width:50%`, sem `float:left` |
| M5 | Novo post: enviar imagem, clicar `blog-img-dir` → **Publicar** | feed rende `float:right` + `max-width` escolhido, sem `float:left` |
| M6 | Clicar `blog-img-esq` com o editor sem nenhuma `<img>` | `notify` warning "Nenhuma imagem no texto — envie uma primeiro", nada muda |
| M7 | Excluir os posts de QA | soft delete (`ativo=0`, somem do feed, vão para "Despublicadas") |

## Roteiro manual — editor do Blog com imagens (14/09/2026)

> EN — Manual Blog editor checklist (admin profile, real browser): greeting placeholder, image upload, sanitized publish, static serving, orphan expiry, soft delete.
>
> PT — Roteiro manual do editor do Blog (perfil admin, navegador real): placeholder de boas-vindas, upload de imagem, publicação sanitizada, serviço estático, expiração de órfãs, soft delete.

Pré-condição: sistema reiniciado, `/login` 200, logado como admin (geral ou do módulo `blog`); `comum` NÃO vê o card "Nova publicação".

| # | Passo | Esperado |
|:---|:---|:---|
| B1 | Abrir `/blog` como admin | card "Nova publicação" visível; editor com placeholder `Olá, <nome>! ...` (nome de tratamento) |
| B2 | Selecionar JPG/PNG (≤5 MB) em `blog-imagem-selecionar` + clicar `blog-imagem-enviar` | `notify` positiva `Imagem enviada: <nome>`; tag `<img src="/img_postagens/<nome>">` inserida no editor (ex. `2609141308_qamaster.png`) |
| B3 | Tentar enviar `.gif`/`.txt` ou >5 MB | `notify` negativa, nada inserido no editor |
| B4 | Pré-visualizar → Publicar | pré-visualização mostra a imagem; post publicado **mantém `src`/`style`/`class`** (nh3) e renderiza no feed |
| B5 | `GET /img_postagens/<nome>` direto | **200 `image/png`** (ou `image/jpeg`) |
| B6 | Upload sem publicar, aguardar >5 min (ou retroagir `mtime`) + ciclo do job (1 min) | órfã **removida** de `mod_blog/img_postagens/`; imagem referenciada em postagem **preservada** |
| B7 | Excluir o post de teste | soft delete (`ativo=0`, some do feed, vai para "Despublicadas") |
| B8 | Abrir `/blog` como `comum` | **sem** card "Nova publicação", sem `blog-*`; imagens dos posts visíveis inline |

## Roteiro manual — drawer × perfis × larguras

> EN — Manual drawer checklist: 3 profiles × 3 widths (320/768/1024). Drawer starts closed, opens/closes via `menu-hamburguer`, is full-width without overflow, every visible item is keyboard-focusable with a visible ring, and ARIA states hold.

> PT — Roteiro manual do drawer: 3 perfis × 3 larguras (320/768/1024). Drawer inicia fechado, abre/fecha via `menu-hamburguer`, ocupa 100% da largura sem overflow, todo item visível recebe foco por teclado com anel visível, e os estados ARIA se mantêm.

Pré-condição: logar com cada perfil (`comum` = usuário sem admin; `administrador_modulo` = `administrador` em ≥1 módulo via gestão de usuários, sem ser geral; `administrador_geral` = `master`). Repetir cada passo em 320 px (mobile), 768 px (tablet) e 1024 px (desktop) — DevTools responsivo.

| # | Passo | Esperado |
|:---|:---|:---|
| M1 | Drawer inicia FECHADO ao abrir qualquer tela | nenhum item `menu-*` visível até clicar em `menu-hamburguer` |
| M2 | Clicar `menu-hamburguer` → clicar de novo | abre na 1ª, fecha na 2ª; foco permanece operável por teclado |
| M3 | Largura 100% (RNF-UI-01) em 320/768/1024 | drawer e itens sem overflow horizontal, sem colapso flex (`w-full` + `min-width: 0`, sem `gap-*` em `ui.row()`) |
| M4 | Teclado: `Tab` até o drawer | todos os itens visíveis recebem foco na ordem, anel `focus-visible` visível em cada um |
| M5 | ARIA: item da tela atual | tem `aria-current="page"`; ícones têm `aria-hidden="true"`; hambúrguer tem `aria-label="Abrir menu de navegação"`; só-ícone/indisponível têm `aria-label` próprio |
| M6 | `comum`: só `menu-home` + `menu-<chave>` dos módulos liberados + `menu-sair` | SEM `menu-admin`, SEM `menu-docs` |
| M7 | `administrador_modulo`: idem M6 (módulos do vínculo + `menu-sair`) | SEM `menu-admin`, SEM `menu-docs` (admin de módulo NÃO abre menu de sistema) |
| M8 | `administrador_geral`: M6 + `menu-admin` + `menu-docs` | `menu-admin` → `/admin/<chave>` (ou `/configuracoes` na Home); `menu-docs` → `/documentacao` nova aba |
| M9 | `menu-<chave>-indisponivel` (se houver módulo desativado com vínculo) | clica → `notify` warning laranja, permanece na tela (não navega) |

Automação correspondente (pirâmide): base unitária em `assets/test/verifica_ui_comum.py` (fábrica byte-a-byte, 190/190) → topo manual/E2E com este roteiro via `page.get_by_test_id(...)`.

## Validações das sessões de 14/09/2026 — scripts standalone + specs E2E

> EN — Validations from the 14/09/2026 sessions materialized as executable files in `assets/test/` (catalog in `assets/test/README.md`): 8 new standalone scripts, all green (73 checks), plus 3 new E2E specs (require `npm run test:e2e` + server on :8080 — not executed here, no Node available). Every new test follows the README conventions (standalone, exit-code verdict, bilingual docstring, no destruction, `data-testid` selectors, browser evidence as spec).
>
> PT — Validações das sessões de 14/09/2026 materializadas como arquivos executáveis em `assets/test/` (catálogo em `assets/test/README.md`): 8 scripts standalone novos, todos verdes (73 checks), + 3 specs E2E novos (requerem `npm run test:e2e` + servidor :8080 — não executados aqui por falta de Node). Todo teste novo segue as convenções do README (standalone, veredito por exit code, docstring bilíngue, sem destruição, seletores por `data-testid`, evidência de navegador como spec).

| Arquivo | O que cobre | Origem |
|:---|:---|:---|
| `assets/test/test_header_nome.py` (9) | Nome no header: tratamento `qacomum`/`qamaster`, botão único `header-nome-usuario`, sem `hidden sm:*`, CSS escopado, tooltip | Sessão: nome truncado `io de Teste QA C` |
| `assets/test/e2e/04_header_nome.spec.js` | Render real: visível desktop/mobile, clique abre Meu Perfil | idem (evidência Playwright) |
| `assets/test/test_rodape_hover.py` (7) | Rodapé: testid, CSS `opacity:0`→hover, faixa 5px, textos preservados | Sessão: rodapé auto-hide |
| `assets/test/e2e/05_rodape_hover.spec.js` | opacity 0 → 1 no hover | idem |
| `assets/test/test_blog_editor_imagens.py` (17) | Upload JPG/PNG (aceite/recusa 5MB/assinatura), nome `dataHora_usuario`, tag nh3, rota `/img_postagens`, job, expiração órfãs | Sessão: editor WYSIWYG + imagens |
| `assets/test/test_blog_markdown_editor.py` (8) | Markdown em `<p>`/`<div>`/1ª solta, listas, negrito, `code/pre`, `#hashtag`, `div/br` | Sessões: Markdown não rendia |
| `assets/test/test_blog_imagem_controles.py` (12) | `ajustar_imagem_html` (eixos, CSS autor, última img, sem-img) + feed respeita autor/padrão | Sessão: redimensionar/alinhar |
| `assets/test/test_blog_mermaid_fim.py` (7) | Mermaid ao fim (`mover_mermaid_para_fim`: meio→fim com ordem, sem fence/incompleto intacto, idempotente, seeds conformes) + render centralizado (`justify-center`, `max-width:680px`) | Sessão: padronização das postagens-guia 14/09/2026 |
| `assets/test/test_empenho_anotar.py` (7) | `anotar_arquivos`: levantamento, override `tb_empenhos`, fallbacks de nome | Sessão: Empenho/Parcela/Usuário |
| `assets/test/test_ordem_modulos.py` (6) | Ordem padrão + `reordenar` 1-based + boot simulado preserva | Sessão: ordem resetava no restart |
| `assets/test/e2e/06_blog_editor.spec.js` | Controles visíveis, preview Markdown, upload→centro+50%→publicar sem `float:left` | idem |

Convenções aplicadas (de `assets/test/README.md`): standalone (`.venv/bin/python <arquivo>.py`, sem servidor/argumentos); veredito por exit code (`check(cond, msg)`); docstring bilíngue EN no topo / PT-BR abaixo + linha `Execute:`; sem destruição (só dados `qa_*` ou snapshot/restore com limpeza em `finally`); seletores E2E por `data-testid`; evidência de navegador como spec em `e2e/0N_*.spec.js`. Refatoração associada: ajuste de imagem extraído para `bd_manipulador.ajustar_imagem_html()` pura (a tela delega); `anotar_arquivos` não normaliza zeros (só a exibição).

```bash
.venv/bin/python assets/test/test_header_nome.py
.venv/bin/python assets/test/test_rodape_hover.py
.venv/bin/python assets/test/test_blog_editor_imagens.py
.venv/bin/python assets/test/test_blog_markdown_editor.py
.venv/bin/python assets/test/test_blog_imagem_controles.py
.venv/bin/python assets/test/test_blog_mermaid_fim.py
.venv/bin/python assets/test/test_empenho_anotar.py
.venv/bin/python assets/test/test_ordem_modulos.py
```

## Roteiro manual — postagens-guia padronizadas + Mermaid ao fim e centralizado (14/09/2026)

> EN — Manual Blog guide-posts checklist (real browser, restarted system): the 3 seeds share one pattern (`# **Title**`, `### subtitle`, bold sections with lists, mermaid last, unaltered flows); diagrams render narrow and centered; saving moves ```mermaid fences to the end in order.
>
> PT — Roteiro manual das postagens-guia padronizadas (navegador real, sistema reiniciado): as 3 postagens seguem o padrão único (`# **Título**`, `### subtítulo`, seções em negrito com listas, mermaid ao fim, fluxos inalterados); diagramas rendem estreitos e centralizados; ao salvar, os fences ```mermaid vão para o fim na ordem.

Pré-condição: sistema reiniciado, `/login` 200, logado como admin (geral ou do módulo `blog`); suíte `assets/test/teste_fluxo_blog.py` 46/46; `assets/test/test_blog_mermaid_fim.py` 7/7. Nota: a suíte completa deixa posts de teste ("Carrossel A/B/C" etc.) na base real — higiene preexistente dos testes de carrossel, fora do escopo desta adequação.

| # | Passo | Esperado |
|:---|:---|:---|
| P1 | Abrir `/blog` e comparar as 3 postagens-guia (Editor de PDF, Solicitação de Impressão, Empenhos) | mesmo padrão visual: título gigante centralizado, subtítulo, intro, seções em negrito com listas, diagrama por último — com os rótulos reais: Editor de PDF (10 arquivos/1024 MB, 10 min, cota 1 GB/10 GB); Solicitação (Pedido único, Pendente, "(trazer)", borda/observações); Empenhos (busca no Navegar, Fila/Organizador/Quarentena) |
| P2 | Observar cada diagrama Mermaid | estreito e centralizado (coluna ~680px, não largura cheia), sem estouro horizontal |
| P3 | Criar postagem com ```mermaid no meio do texto → Publicar → reabrir | blocos movidos para o fim na ordem original; sem fence completo o texto segue intacto |
| P4 | Editar postagem existente inserindo ```mermaid no início → Salvar | idem P3 (vale para criar e editar) |
| P5 | `.venv/bin/python assets/test/test_blog_mermaid_fim.py` + suíte blog | **7/7 OK** (move/ordem/idempotência/seeds/render) + `teste_fluxo_blog.py` **46/46** |

## Falhas preexistentes conhecidas (não causadas pela sessão de 14/09/2026)

> EN — Known pre-existing failures (verified 14/09/2026, documented in `assets/test/README.md`): the checks reference code prior to the session — not regressions.
>
> PT — Falhas preexistentes conhecidas (verificadas em 14/09/2026, documentadas em `assets/test/README.md`): os checks referenciam código anterior à sessão — não são regressões.

- `assets/test/test_dashboard.py` (7 checks): espera o layout antigo do Resumo (`"Atualizado ✓"`, `ui.timer(2.0)`, microinterações `transition`/`hover` nos cards). O dashboard foi redesenhado (toast 2s via `notificar`, timer 0.1) sem atualizar o teste. Nenhum trecho tocado pela sessão.
- `assets/test/verifica_ui_comum.py` (1 check em 190): exige `ui.tabs()` ausente em `mod_renomear_empenho/telas.py`, mas a barra do menu usa `ui.tabs()` desde antes da sessão (`telas.py:153`, só reordenada com o botão TEMP).

Suíte completa no fechamento da sessão: 37 scripts OK; 2 falhas preexistentes acima.

## Como executar

```bash
.venv/bin/python test/test_server.py
.venv/bin/python test/test_auditoria.py
.venv/bin/python test/test_editor_pdf.py
.venv/bin/python test/teste_aba_config_intranet.py
.venv/bin/python assets/test/verifica_ui_comum.py
```

Veja [Testes — Plano](../testes_plano/index.md) e [Testes — Relatórios](../testes_relatorios/index.md).
