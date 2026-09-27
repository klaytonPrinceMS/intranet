# Agregador de Notícias — `mod_agregador_noticias`

> News aggregator: route `/agregador-noticias` only (key `agregador_noticias`) — the pure screen
> `/agregador-noticias-puro` was **REMOVED on 26/09/2026** (file `telas_puro.py` and the 4.9 MB
> `assets/noticia/` theme are gone; only `assets/noticia/favicon.png` survives, used as the
> fallback image by `/api/attachments/`) · own database `db_mod_agregador_noticias.db` · table `tb_noticia` (title/source/theme/url/image/fonte_icon/description/dates, `fonte_icon_url` 16×16 faviconV2 + `imagem_url` 30×30, **daily recycle at 09:00 configurable `hora_reinicio` via `reiniciar_banco` DELETE + `CronTrigger`**, **no backup** `MAPA_BACKUPS` without `agregador_noticias`) · scrapy-like `httpx+parsel` mirroring `klaytonPrinceMS/Noticia` (Sites gn_brasil/gn_saude + Noticias get_noticiasGN/BBC/JFP/RSS) · interval 60–9360 min + habilitado flag + free term via RSS (`/rss/search` — HTML `/search` gives 429/captcha) + configurable sources (24 default in `FONTES_PADRAO`; 3 legacy + 11 RSS V1 + 15 V2 kept only for migration) + polite collection (`UA_COLETA`, `CORTEZIA_SEG` 1.5s+jitter, 30min 429 cooldown) · deduplication by URL (`SELECT url`) + normalized title (`_norm_tit` NFKD lower) before `INSERT OR IGNORE` · real post time via `_parse_data_pub` (`email.utils.parsedate_to_datetime` + ISO/RSS fallback) ordered by `COALESCE(data_publicacao, data_coleta) DESC` · **bar tema filter + busca input side-by-side** (`agregador-filtro-tema` + `agregador-busca` `debounce 300` NFKD, `placeholder "Buscar palavra…"`, `clearable`, tooltip, no Coleta badge) · **pagination 12 + busca** (`pagina` state `por_pagina=12` `total_pag` `offset`, `busca` global in-memory 500 NFKD title/desc/fonte/tema (ignores tema filter), `ORDER BY COALESCE(...) DESC` newest→oldest, buttons `Primeira/Anterior/Próxima/Última` with `data-testid=agregador-primeira/anterior/proxima/ultima`) · grid responsivo **3 colunas desktop → 2 tablet (max-width 1024px) → 1 celular (max-width 640px) via `.grid-noticias {display:grid; grid-template-columns: repeat(3,1fr)}` + media queries, cards **`height: 250px` FIXED** (220px mobile — never `min/max-height`, so every card of the row is identical)** · cards **redesigned 25/09/2026 (fixed-height card): thumbnail `120×120` `cover` (was `30×30`) whose click/ENTER/SPACE opens an ENLARGEMENT in the standard `dialogo_card` with the image at 60vw×60vh `object-fit: contain` (closes via ESC/click-outside/"Fechar", dialog memoized per card and mounted only on the 1st click) + the source logo as a `32×32` WATERMARK in the image footer (bottom-right, `opacity .65`, `pointer-events: none`, dark+light `drop-shadow`; falls back to a 16×16 icon next to the badge only when the news has no image) + badge theme + title as `ui.link(new_tab=True)` + FULL description in a fixed-height box with `overflow-y: auto` (no longer truncated as `desc[:180] + "…"`) + relative time `_tempo_relativo` using real `data_publicacao`, no button — title click suffices, no TV card, absolute date replaced, busca NFKD; the thumbnail frame is a SIBLING of the title link and the click uses the native `.stop` modifier, so enlarging never navigates to the original site; the grid `<style>` moved out of `@ui.refreshable` (it was duplicated on every search/pagination)** · **seed `Folha de S.Paulo` URL repaired (`https:/s.folha...` → `https://s.folha...`, one slash only caused `Request URL is missing an 'http://' or 'https://' protocol`) + idempotent migration in `init_db` that rewrites any malformed-scheme URL already persisted in `tb_config` without touching user-customized sources** · **pure screen — REMOVED 26/09/2026** (was `telas_puro.py:mostrar_tela_pura` on `/agregador-noticias-puro`, a copy of `klaytonPrinceMS/Noticia` `intro-overlay` + `about` `info-list`; the button `Ver puro Noticia` `data-testid=agregador-ver-puro` is also gone) · admin: habilitado, intervalo, termo, fontes, temas, **hora_reinicio `09:00` + reinício diário `reiniciar_banco`** · TV filas `listar_para_tv` carousel (7s rotate, 120s reload, `fonte_icon` included) · `assets/noticia/` reduced to `favicon.png` (4.9 MB theme removed 26/09/2026) · `mod_filas/midia/` (`PASTA_MIDIA` `/midia_filas`) · audit only **who changed what** (`definir_*` + `reiniciar_banco`, no audit for localized posts).

---

# Agregador de Notícias — `mod_agregador_noticias`

> Agregador de notícias: rota `/agregador-noticias` (chave `agregador_noticias`) · **a tela pura `/agregador-noticias-puro` foi REMOVIDA em 26/09/2026** — era réplica de teste do modelo `Noticia` (`telas_puro.py` + `assets/noticia/` de 4,9 MB); sobrou só o `assets/noticia/favicon.png`, que o fallback de `/api/attachments/` usa como imagem de substituição na TV e no Blog · **atualizado 25/09/2026**: censura compartilhada orquestrada pelo núcleo via `integracoes.limpar_noticias_censuradas()` · banco próprio `db_mod_agregador_noticias.db` · tabela `tb_noticia` (título/fonte/tema/url/imagem/ícone_fonte/descrição/datas, `fonte_icon_url` 16×16 faviconV2 + `imagem_url` 30×30, **banco reciclado diariamente às `09:00` configurável `hora_reinicio` via `reiniciar_banco` `DELETE` + `CronTrigger`, sem backup** `MAPA_BACKUPS` sem `agregador_noticias`) · scrapy-like `httpx+parsel` espelhando `klaytonPrinceMS/Noticia` (Sites gn_brasil/gn_saude + Noticias get_noticiasGN/BBC/JFP/RSS) · intervalo 60–9360 min + flag habilitado + termo livre via RSS (`/rss/search` — HTML `/search` dá 429/captcha) + fontes configuráveis (24 no `FONTES_PADRAO`; 3 legadas + 11 RSS V1 + 15 V2 preservadas só para migração) + coleta educada (`UA_COLETA`, `CORTEZIA_SEG` 1.5s+jitter, cooldown 30 min) · deduplicação por URL (`SELECT url`) + título normalizado (`_norm_tit` NFKD lower) antes de `INSERT OR IGNORE` · tempo real da postagem via `_parse_data_pub` (`email.utils.parsedate_to_datetime` + fallback ISO/RSS) ordenado por `COALESCE(data_publicacao, data_coleta) DESC` · **barra filtro tema + busca lado a lado** (`agregador-filtro-tema` + `agregador-busca` `debounce 300` NFKD, `placeholder "Buscar palavra…"`, `clearable`, tooltip, sem badge `Coleta:`) · **paginação 12 + busca** (`pagina` `por_pagina=12` `total_pag` `offset`, busca **global** em memória 500 NFKD título/descrição/fonte/tema (ignora filtro de tema), ordenação `COALESCE(...) DESC` mais atual→mais antiga, botões `Primeira/Anterior/Próxima/Última` `data-testid=agregador-primeira/anterior/proxima/ultima`) · grid responsivo **3 colunas desktop → 2 tablet (max-width 1024px) → 1 celular (max-width 640px) via `.grid-noticias {display:grid; grid-template-columns: repeat(3,1fr)}` + media queries, cards **`height: 250px` FIXO** (220px no celular — nunca `min/max-height`, para todos os cards da linha ficarem idênticos)** · cards **redesenho 25/09/2026 (card de altura fixa): miniatura `120×120` `cover` (era `30×30`) cujo clique/ENTER/ESPAÇO abre a AMPLIAÇÃO no `dialogo_card` padronizado com a imagem em 60vw×60vh `object-fit: contain` (fecha por ESC/clique fora/botão "Fechar"; diálogo memoizado por card e montado só no 1º clique) + o logo da fonte como MARCA D'ÁGUA de `32×32` no rodapé da imagem (inferior direito, `opacity .65`, `pointer-events: none`, `drop-shadow` claro+escuro; só vira ícone `16×16` ao lado do badge quando a notícia não tem imagem) + badge tema + título como `ui.link(new_tab=True)` + descrição COMPLETA em caixa de altura fixa com `overflow-y: auto` (não é mais truncada como `desc[:180] + "…"`) + tempo relativo `_tempo_relativo` usando `data_publicacao` real, sem botão — título clicável basta, sem card TV, data absoluta substituída, busca NFKD; a moldura da miniatura é IRMÃ do link do título e o clique usa o modificador nativo `.stop`, então ampliar nunca navega para o site original; o `<style>` do grid saiu de dentro do `@ui.refreshable` (era duplicado a cada busca/paginação)** · **URL do seed `Folha de S.Paulo` reparada (`https:/s.folha...` → `https://s.folha...`, uma barra só causava `Request URL is missing an 'http://' or 'https://' protocol`) + migração idempotente no `init_db` que reescreve qualquer URL com esquema malformado já persistida em `tb_config` sem tocar nas fontes customizadas do usuário** · **tela pura — REMOVIDA 26/09/2026** (era `telas_puro.py:mostrar_tela_pura` em `/agregador-noticias-puro`, copiando padrão `klaytonPrinceMS/Noticia` `intro-overlay` + `about` `info-list` com cards atuais (3 colunas, `fonte_icon 16×16` + `imagem 30×30`, tempo relativo) + originais `assets/noticia/` (`base.css`, `vendor.css`, `main.css`, `font-awesome`, `micons`, `fonts/lora/poppins`, `images/bg/intro`, `js/modernizr/pace/jquery/plugins/main.js`, `favicon.png`) servidos via `main.py` `@app.get("/assets/noticia/{caminho:path}")` + botão `Ver puro Noticia` `data-testid=agregador-ver-puro` · admin: habilitado, intervalo, termo, fontes, temas, **hora `09:00` + reinício `reiniciar_banco`** · TV filas `listar_para_tv` carrossel (7s rotação, 120s recarrega, `fonte_icon` incluso) · `assets/noticia/` 4.9M servido via rota estática · `mod_filas/midia/` (`PASTA_MIDIA` `mod_filas/midia` → `/midia_filas`) · auditoria só **quem alterou o quê** (`definir_*` + `reiniciar_banco`, sem postagens).

## Propósito

Módulo que **agrega notícias multi-fonte** para a rede interna, com **conteúdo de pesquisa configurável pelo admin** (termo livre) e **previsão de não apenas Google News, mas outras fontes** (`BBC`, `JFP`, `RSS`). Coleta **scrapy-like** (`httpx` + `parsel`) espelhando `https://github.com/klaytonPrinceMS/Noticia` — `Sites` (`gn_brasil`, `gn_saude` etc) + `Noticias.get_noticiasGN/BBC/JFP/RSS` — investigando a cada **10 min–6 h** (clamp) quando **habilitado**. Banco **reciclado diariamente às horas da manhã** (padrão `09:00` configurável `obter_hora_reinicio`/`definir_hora_reinicio`, `reiniciar_banco` `DELETE` + `CronTrigger` em `rotinas.py`, **sem backup** `MAPA_BACKUPS` sem `agregador_noticias`; `telas_administracao` sem `painel_backup`, card `Reinício diário — banco reciclado` com `Zerar agora`). **Deduplicação** por URL e por título normalizado (`_norm_tit` NFKD lower, `join`) impede notícia já incluída com mesmo título (case-insensitive, sem acentos) ou mesma URL antes de `INSERT OR IGNORE`. **Timer com tempo real**: `data_publicacao` extraída da postagem (`time[datetime]`, `pubDate`/`dc:date`) via `_parse_data_pub` (`email.utils.parsedate_to_datetime` + fallback ISO/RSS) e ordenação por `COALESCE(data_publicacao, data_coleta) DESC`; `_tempo_relativo` usa `data_pub` real ou `data_coleta` fallback. Visual em **grid responsivo 3→2→1 colunas (desktop 3, tablet 2 max-width 1024px, celular 1 max-width 640px) paginado 12** com card **sem fonte textual e sem botão** — **miniatura `120×120` (`object-fit: cover`, era `30×30`) CLICÁVEL que abre a ampliação em diálogo (60vw×60vh `object-fit: contain`) + logo da fonte como marca d'água `32×32` no rodapé da imagem + badge tema + título como `ui.link(target=href, new_tab=True)` + descrição COMPLETA com scroll + tempo relativo** (`_tempo_relativo` → `agora`/`X minuto(s)/hora(s)/dia(s) atrás`, data absoluta substituída — as faixas de **semana/mês/ano foram removidas** em 26/09/2026, porque no Agregador a notícia vive 24 h) e **título clicável basta — botão "Abrir notícia" removido 19/09/2026**, **paginação `12` com botões `Primeira/Anterior/Próxima/Última` (`data-testid=agregador-primeira/anterior/proxima/ultima`) mais atual→mais antiga `COALESCE DESC` + grid `.grid-noticias` + cards `.card-noticia` de ALTURA FIXA `height 250px` (`220px` no celular em `@media max-width:640px` — nunca `min/max-height`, para todos os cards da linha ficarem idênticos; `telas.py:411` e `:469`)**. **Card "Integração TV — Filas" removido da tela agregador**. Integra a **TV do `mod_filas`** (`/tv`) com **carrossel título+descrição** via `listar_para_tv` (`timer 7s` rotação + `120s` recarrega). **Auditoria só quem alterou o quê** (`definir_habilitado/intervalo/termo/fontes/temas/hora_reinicio/reiniciar_banco` com `_audit`), **sem auditar postagens localizadas** (removido `_audit` de `coletar_todas`, `limpar_antigas`, `limpar_censuradas`).

## Banco próprio

Conexão WAL + `foreign_keys=ON` via `mod_intranet/banco_conexao.conexao("agregador_noticias")` (backend duplo SQLite/PostgreSQL). Criador vigente: `init_db()` em `bd_manipulador.py:209-250`, executado no import (`bd_manipulador.py:705` `init_db()`) e pelo bootstrap central (`mod_intranet/bd_criador.py:67` `init_agregador`).

**`tb_noticia`**:

| Coluna | Observação |
|:---|:---|
| `id` | PK AUTOINCREMENT |
| `titulo` | TEXT NOT NULL (`[:500]` em `inserir_noticia`, dedup via `_norm_tit` NFKD lower) |
| `fonte` | TEXT NOT NULL (`[:100]` — ex.: `Google News - Brasil`, `BBC`, `JFP Notícias`, `RSS`) |
| `tema` | TEXT NOT NULL DEFAULT `Geral` (`[:50]` — ex.: `Brasil`, `Saúde`, `Economia`) |
| `url` | TEXT NOT NULL UNIQUE (`[:2000]`, normalizada `/`→ `https://news.google.com` + `/`) — `SELECT url` + `INSERT OR IGNORE` deduplica |
| `imagem_url` | TEXT DEFAULT `''` (`[:2000]` — `img::attr(src)`/`data-src`/`media:content`/`lh3.googleusercontent` — **`"/api/attachments"` filtrado para `""` em `inserir_noticia` (`bd_manipulador.py:481-493` só relativo/localhost → `""`; absoluto preservado), evita URL quebrada Trello/Notion; fallback `main.py:820` `/api/attachments` → `favicon.png` se `-w280-h168-p-df/.png/.jpg` senão `404` silencioso**, miniatura `120×120` `cover` clicável com ampliação em diálogo) |
| `fonte_icon_url` | TEXT DEFAULT `''` (`[:2000]` — `faviconV2` extraído via `//img[contains(@src,'faviconV2')]/@src` ancestral `div[1..3]`, `try` fail-soft, migração idempotente `ALTER TABLE ADD COLUMN` — **`"/api/attachments"` relativo/localhost também filtrado para `""` (absoluto `news.google.com/api/attachments` preservado)**; na tela principal vira **marca d'água `32×32` no rodapé da miniatura** (opacidade `.65`, `pointer-events: none`) e só aparece como ícone `16×16` `contain` ao lado do badge quando a notícia **não tem** imagem) |
| `descricao` | TEXT DEFAULT `''` (`[:1000]` — `description::text` RSS ou `txt` Google/BBC/JFP) |
| `data_publicacao` | DATETIME (`COALESCE(?, datetime('now'))` — preenchido via `_parse_data_pub` com tempo real da postagem ou `now` fallback, ordenação `COALESCE(data_publicacao, data_coleta) DESC`) |
| `data_coleta` | DATETIME DEFAULT `CURRENT_TIMESTAMP` (`ORDER BY COALESCE(data_publicacao, data_coleta) DESC, data_coleta DESC`) |

Índices `idx_noticia_tema(tema)`, `idx_noticia_fonte(fonte)`, `idx_noticia_data(data_coleta)`.

**Temas padrão** (`TEMAS_PADRAO` — len conferido em 27/09/2026): `["Brasil","Internacional","Economia","Saúde","Ciência e Tecnologia","Entretenimento","Esporte","Monte Santo","Geral","Tribunais de Contas"]` — **10 temas**, semente `temas_json` em `tb_config` central (`json.dumps`). A doc anterior listava 9 e usava `"Monte Santo de Minas"`; o código tem `"Monte Santo"` e ganhou `"Tribunais de Contas"`.

**Fontes padrão — 15** (`FONTES_PADRAO` — `bd_manipulador.py:35-59`: `_FONTES_PADRAO_LEGADO` 3 + `_FONTES_PADRAO_V1` 8 RSS + 4 cobertura V2 20/09/2026; espelho `Sites` `gn_brasil`/`gn_saude` + RSS oficiais verificados 20/09/2026; migração `init_db` promove LEGADO/V1 → atual quem nunca customizou):

| `tipo` | `nome` | `url` | `tema` |
|:---|:---|:---|:---|
| `google` | Google News - Brasil | `https://news.google.com/topics/CAAqJQgKIh9DQkFTRVFvSUwyMHZNREUxWm5JU0JYQjBMVUpTS0FBUAE?hl=pt-BR&gl=BR&ceid=BR%3Apt-419` | `Brasil` |
| `bbc` | BBC - Brasil | `https://www.bbc.com/portuguese/topics/cz74k717pw5t` | `Brasil` |
| `google` | Google News - Saúde | `https://news.google.com/topics/CAAqJQgKIh9DQkFTRVFvSUwyMHZNR3QwTlRFU0JYQjBMVUpTS0FBUAE?hl=pt-BR&gl=BR&ceid=BR%3Apt-419` | `Saúde` |
| `rss` | Agência Brasil | `https://agenciabrasil.ebc.com.br/rss/ultimasnoticias.xml` | `Brasil` |
| `rss` | Senado Federal | `https://www12.senado.leg.br/noticias/rss` | `Brasil` |
| `rss` | G1 - Últimas | `https://g1.globo.com/rss/g1/` | `Geral` |
| `rss` | G1 - Economia | `https://g1.globo.com/rss/g1/economia/` | `Economia` |
| `rss` | G1 - Saúde | `https://g1.globo.com/rss/g1/saude/` | `Saúde` |
| `rss` | G1 - Tecnologia | `https://g1.globo.com/rss/g1/tecnologia/` | `Ciência e Tecnologia` |
| `rss` | Poder9360 | `https://www.poder9360.com.br/` | `Brasil` |
| `rss` | Folha de S.Paulo | `https://s.folha.uol.com.br/emcimadahora/rss091.xml` (**URL corrigida 25/09/2026** — o seed tinha `https:/s.folha...`, com uma barra só) | `Brasil` |
| `rss` | G1 - Mundo | `https://g1.globo.com/rss/g1/mundo/` | `Internacional` |
| `rss` | G1 - Pop e Arte | `https://g1.globo.com/rss/g1/pop-arte/` | `Entretenimento` |
| `rss` | GE - Esporte | `https://ge.globo.com/rss/ge/` | `Esporte` |
| `rss` | JFP - Monte Santo de Minas | `https://jfpnoticias.com.br` (**sem `/feed/`** — o caminho do feed não existe no site; o coletor cai no `except` e a fonte não traz notícia) | `Monte Santo de Minas` |

Seeds `tb_config` central incluem `agregador_noticias_hora_reinicio` `09:00` (`HH:MM` validado `re.match`).

⚠️ `bd_criador.py` legado/morto.

## Fluxo da tela

- Gate `_pode_ver` (`telas.py:37-44`): `administrador_geral` ou `validar_acesso_modulo(user,"agregador_noticias")`; sem acesso → `block` 64px + "Acesso restrito".
- `mostrar_tela(user_nome, perfil_global)` (`telas.py:46-437`, 392 linhas): `ler_tema("agregador_noticias", cor_botao="#000000", texto_header="Notícias agregadas de múltiplas fontes — 3 colunas, clique abre no site original. Para TV do Filas, carrossel título+descrição.")` + `ui.colors(primary)` + `cabecalho(... chave_modulo="agregador_noticias")` + `estado={"tema":"","busca":"","pagina":1}` + `temas=temas_config()` + helper **`_tempo_relativo(data_str)` (`telas.py:65-107`)** — converte ISO flexível (`YYYY-MM-DD HH:MM:SS`/`YYYY-MM-DD HH:MM`/`YYYY-MM-DD`, normaliza `T`/`Z`/fração `.\d+`, `re.split`, `strptime` por formato, `now - dt` → `total_seconds` → `agora` (<60 s) / `X minuto(s) atrás` (<3600) / `X hora(s) atrás` (<86400) / `X dia(s) atrás` (<604800) / `X semana(s) atrás` (<2592000) / `X mês(es) atrás` (<31536000) / `X ano(s) atrás`, `delta<0→0`, fallback `[:16]`), **usa `data_publicacao` real da postagem (extraída via `_parse_data_pub` de `time[datetime]`/`pubDate`) com fallback `data_coleta`, ordenação `COALESCE(data_publicacao, data_coleta) DESC` garante "3 minutos atrás, 25 minutos atrás, 2 semanas..." com tempo real**.
  - **Barra** (`telas.py:119-148`): `newspaper` icon + `sel_tema` (`data-testid=agregador-filtro-tema`, `Todos os temas` + `temas`, `min-w-[200px]`) **+ `inp_busca` (`data-testid=agregador-busca`, `Buscar palavra…` `debounce 300` `min-w-[220px] flex-1`, `placeholder "Buscar palavra…"` `outlined dense clearable debounce='300'`, `tooltip "Pesquisar em todos os temas por palavra no título/descrição/fonte" (busca global — ignora filtro de tema)`, `on_value_change→estado["busca"]=val, pagina=1, grid.refresh()`) lado a lado (`flex-wrap` `gap-3` `bg-white rounded-lg shadow-sm px-3 py-2`)** — **badge `Coleta: ativa/desabilitada` removido a169c9a** + `botao Atualizar` (`data-testid=agregador-atualizar`, `texto`, `grid.refresh()`) + `botao Coletar agora` (`data-testid=agregador-coletar`, `primario`, só `administrador_geral`/`eh_admin_do_modulo` → **`async _coletar` com `run.io_bound(lambda: ag.coletar_todas(ator=user_nome, forcar=True))`, spinner `aria-label=Coletando notícias`, trava `ocupado`, `notificar` + `grid.refresh()` — anti-disconnect**) (**botão Ver puro Noticia `agregador-ver-puro` removido de `telas.py` 20/09/2026 — `/agregador-noticias-puro` por URL direta**).
  - **Redesenho do card 25/09/2026 — altura fixa, miniatura `120×120` ampliável, marca d'água da fonte e resumo com scroll.** O card deixou de usar `min-height`/`max-height` (que produziam alturas diferentes entre linhas) e passou a ter **`height` FIXA**; a miniatura deixou de ser um elemento de `30×30` ao lado do título e virou um **elemento clicável de `120×120`**; a descrição deixou de ser truncada (`desc[:180] + "…"`) e passou a ser **o texto completo numa caixa de altura fixa com scroll**; e o logo da fonte deixou de ser um ícone decorativo ao lado do título e virou **marca d'água sobre a própria imagem**. Os helpers novos são:
    - **`_desempacotar_noticia(n)`** (`telas.py:109-129`) — substitui o `if/elif` de compat por posição dentro de `_noticia_card`. Normaliza a linha do `bd_manipulador` numa tupla de **sempre 10 campos** (`id, titulo, fonte, tema, url, imagem_url, fonte_icon_url, descricao, data_publicacao, data_coleta`): `>=10` → `tuple(campos[:10])`; `==9` (registro antigo sem `fonte_icon_url`) → insere `""` na posição 6; menor/maior → completa com `""`. Linha ilegível vira registro vazio, com `log.warning` (**fail-soft**, nunca levanta).
    - **`_criar_dialogo_noticia(img, titulo, fonte)`** (`telas.py:131-162`) — **cria (sem abrir)** o diálogo de ampliação e devolve o `ui.dialog` (ou `None`). Usa o `dialogo_card` padronizado do projeto (`mod_intranet/ui_comum.py:294` — cartão com o estilo do módulo, **fecha por ESC e por clique fora**), com `titulo` truncado em 90 chars, `largura="w-full max-w-[94vw] mx-4"` e `max_altura=False` (a imagem define a altura). Dentro: `ui.image(img).classes("dlg-noticia__img").props("fit=contain")` → **60vw × 60vh** (`88vw × 58vh` no celular), `alt`/`aria-label` descritivos passados pelo **dicionário de props** (o texto pode conter aspas, e o dicionário dispensa escape), rótulo da fonte com `aria-label` e botão "Fechar" (`icone="close"`, `primario`, `compacto`) sempre visível. Falha ao montar → `log.exception` + `notificar(... type="negative")` + devolve `None` (**nunca derruba o cliente**, AGENTS.md §3.2).
    - **`_abrir_dialogo_noticia(cache, img, titulo, fonte)`** (`telas.py:164-180`) — **abre** a ampliação **memoizando o diálogo no `cache` do card**: o `ui.image` grande só é baixado/montado no **PRIMEIRO clique** (evita puxar 12 imagens grandes por página) e o mesmo `dlg` é reaberto nos cliques seguintes, sem acumular diálogos no DOM. Falha → `log.exception` + `notificar`.
    - **`_midia_noticia(img, fonte_icon, titulo, fonte, testeid="")`** (`telas.py:182-226`) — monta a **moldura clicável** da miniatura: `ui.element("div").classes("card-noticia__midia").style("cursor: zoom-in")` com `role="button"`, `tabindex="0"`, `aria-label="Ampliar imagem da notícia: <título>"` e `data-testid` estável (`agregador-ampliar-<id>`, ou `agregador-ampliar` quando o id não é alfanumérico). Dentro: `ui.image(img).classes("card-noticia__foto").props("fit=cover")` (**120×120**, `object-fit: cover`; se a miniatura for inválida, cai num `🖼` com `log.warning`) e o **logo da fonte como marca d'água** `ui.image(fonte_icon).classes("card-noticia__marca")` — **32×32, canto inferior direito (`right:4px; bottom:4px`), `opacity: .65`, `pointer-events: none` (não rouba o clique), `z-index: 2` e `drop-shadow` claro+escuro** para destacar sobre qualquer foto (auditoria de direitos). Eventos: `on("click.stop", _ampliar)`, `on("keydown.enter", _ampliar)`, `on("keydown.space", _ampliar)` + `tooltip("Ampliar imagem")`. Os modificadores **`.stop`/`.enter`/`.space` são os nativos do NiceGUI** (`Vue.withModifiers`/`withKeys` — **nada de JavaScript escrito à mão**).
    - **`_noticia_card(n)`** (`telas.py:228-292`) — monta o card com `ui.card().classes("w-full hover:shadow-lg transition-shadow card-noticia")` (sem `cursor-pointer` no card inteiro, sem `break-inside:avoid` de masonry). Duas `card_section`: **topo** (`card-noticia__topo`, `flex 0 0 auto`) com o **badge do tema** (`badge(tema_n or "Geral", "blue-grey-2") outline dense`) + o **ícone `16×16` da fonte SÓ quando a notícia não tem imagem** (`fonte_icon and not img` — com imagem o logo vira marca d'água) e o **tempo relativo** `ui.label(_tempo_relativo(data_pub or data_col)).classes("text-caption text-grey-5")`; **corpo** (`card-noticia__corpo`, `flex 1 1 auto`, `row`) com a **miniatura `120×120` ampliável** (via `_midia_noticia`, só quando há `imagem_url`) ao lado da coluna de texto (`card-noticia__texto`) com o **título** `ui.link(texto, target=href, new_tab=True).classes("card-noticia__titulo hover:text-primary")` (`try` → `ui.label` fallback) e o **resumo**: `ui.label(str(desc)).classes("card-noticia__resumo")` com o **texto completo** quando há descrição distinta do título, senão `"Sem resumo disponível."` em `text-grey-5`. `texto` nunca fica vazio (`"Notícia sem título"`); título vazio cai no `try`/`label`. `href = url or "#"`. Todo o corpo está em `try/except` → `log.exception` + `notificar("Não foi possível montar o card desta notícia.", type="negative")`.
    - **Dois detalhes que impedem o clique na imagem de disparar a navegação**: (a) a moldura da miniatura é **IRMÃ** do link do título, nunca ancestral dele; (b) o `click` usa o modificador **`.stop`**, que interrompe a propagação. Antes o clique na miniatura era absorvido pelo `<a>` do título.
    - **Sem botão "Abrir notícia"** (removido 19/09/2026) — o **título** é o link externo (`new_tab=True`) e o **clique na imagem** é a ampliação; são dois alvos, não um só.
    - ⚠️ **Divergência conhecida (25/09/2026)**: os cinco helpers acima
      (`_desempacotar_noticia`, `_criar_dialogo_noticia`, `_abrir_dialogo_noticia`,
      `_midia_noticia`, `_noticia_card`) foram escritos com docstring **só em PT-BR**,
      contrariando o padrão do repositório (**EN no topo, PT-BR abaixo**). O **docstring
      de módulo** de `telas.py` está correto e bilíngue (`EN:` no topo, `PT-BR:` abaixo).
      A correção é em `mod_*/`, fora do escopo deste lote de documentação.
      `_tempo_relativo` (pré-existente, `telas.py:65-107`) está na mesma condição.
      O padrão correto pode ser visto nas duas formas aceitas no repositório:
      **rótulos explícitos** — `bloco_nomes_fila` (`mod_filas/telas.py:267-269`) — e
      **frase EN → linha em branco → parágrafo PT-BR** — `_resetar_cota`
      (`mod_solicita_impressao/telas.py:2583-2585`).
  - **`grid()`** (`@ui.refreshable`, `telas.py:357-436`): `estado {"tema":"","busca":"","pagina":1}` → `tema_f=estado["tema"] or None`, `busca=(estado["busca"] or "").strip()` → se `busca`: `todas=ag.listar_noticias(tema=None, limite=500) (busca global — ignora filtro de tema, termo livre cai em "Geral")` → `filtradas=[n for n in todas if busca_n in titulo[1]/descricao[7]/fonte[2]/tema[3]]` via `_norm` `NFKD lower` `ascii ignore` (`_camp` helper, `busca_n=_norm(busca)`) → `total=len(filtradas)` senão `total=contar_noticias(tema_f)` → `por_pagina=12` → `total_pag = max(1, (total+12-1)//12)` → clamp `pagina` `1..total_pag` → `offset=(pagina-1)*12` → **se busca: `noticias=filtradas[offset:offset+12]` senão `ag.listar_noticias(tema_f, limite=12, offset=offset)` `ORDER BY COALESCE(data_publicacao, data_coleta) DESC`** → ``.grid-noticias` `display:grid` responsivo 3→2→1 com `gap:1rem` + `.card-noticia` `height 250px`; vazio → `article 48px` + `"Nenhuma notícia ainda. Ative a coleta nas Configurações."` + tema se filtrado. **Paginação rodapé** `row w-full items-center justify-between mt-3 flex-wrap gap-2` com `ui.button icon=first_page` `data-testid=agregador-primeira` → `pagina=1` + `chevron_left` `agregador-anterior` → `max(1,pagina-1)` + `label Página X de Y • N notícias` + `chevron_right` `agregador-proxima` → `min(total_pag,pagina+1)` + `last_page` `agregador-ultima` → `total_pag` + `label Exibindo len de total` + `ui.label Exibindo len de total`. **Sem busca:** `contar_noticias` direto; **com busca:** em memória 500 NFKD. **Card "Integração TV — Filas" removido (antes `telas.py:184-187` `card bg-blue-50` — grid agora termina com paginação + busca).** `on_tema` + `on_busca` (`inp_busca.on_value_change`) ambos resetam `pagina=1` e `grid.refresh()` (**sem badge `Coleta:`**).
  - **CSS do grid injetado FORA do `@ui.refreshable`** (`telas.py:320-354`, `ui.add_head_html`): o bloco `<style>` ficava dentro de `grid()` e era **duplicado a cada busca e a cada paginação**, acumulando cópias da folha de estilo no `<head>`. Agora é emitido **uma única vez por página**, logo acima da definição de `grid()`.
  - **Sem card TV nesta tela** — integração TV permanece via `mod_filas/tv` + `listar_para_tv`.
  - **Tela pura Noticia — REMOVIDA em 26/09/2026.** O que segue é o registro do que ela fazia;
    `mod_agregador_noticias/telas_puro.py` **não existe mais** e a rota `/agregador-noticias-puro`
    foi retirada de `main.py` (restou só o comentário, em `main.py:955`). Para o estado atual da tela,
    ver as seções acima. Histórico: (`telas_puro.py:mostrar_tela_pura`, `telas_puro.py:48-145`): gate `validar_acesso_modulo(user, "agregador_noticias")` + `ui.add_head_html` `base.css`/`vendor.css`/`main.css`/`font-awesome`/`micons` + `favicon.png` + `modernizr.js`/`pace.min.js` via `main.py:818` `@app.get("/assets/noticia/{caminho:path}")` (`normpath` + `startswith(base)` anti-traversal + `mimetypes.guess_type` → `FileResponse`, `404` se fora) + `ler_tema("agregador_noticias")` + `section intro-overlay` (`background:#111417`) + `intro-content` `PRINCE. K,B.` + `DTI - Notícias` + `Pref. Municipal — Agregador puro` + `Início` (`/agregador-noticias`) / `Fim` (`window.scrollTo`) + `section about` `Principais notícias` + `row about-content` `col-six tab-full` `ul.info-list` com **12 notícias `listar_noticias(limite=12)` `COALESCE DESC`** `li.border-b py-3` (`fonte_icon 16×16` + `badge tema` + `tempo _tempo_relativo` + `fonte ml-auto` + `imagem 30×30` + `ui.link titulo new_tab` + `descricao[:160]` + `href[:60] font-mono` + `<a>Abrir no site original →</a>`) + `footer bg-grey-900` `© Copyright DTI` + `js/jquery-2.1.3/plugins/main`; helper `_tempo_relativo(s)` `T/Z/fração` `strptime` → `agora`/minutos/horas/dias/semanas, acesso por URL direta `/agregador-noticias-puro` (botão `agregador-ver-puro` removido 20/09/2026).
- Responsividade: `w-full p-6 gap-4`, `flex-wrap`, `.grid-noticias {display:grid; grid-template-columns: repeat(3,1fr); gap:1rem}` desktop 3 → tablet 2 `max-width 1024px` → celular 1 `max-width 640px` + **`.card-noticia {height: 250px}` (celular `220px`) — altura FIXA, nunca `min/max-height`**, `.dlg-noticia__img {width: 60vw; height: 60vh}` (celular `88vw × 58vh`) + `min-width: 0` em `.card-noticia__texto` / `.card-noticia__titulo`. O prefixo `.card-noticia` nos seletores das seções vence o `.column` do Quasar (mesma especificidade) sem depender da ordem de injeção dos `<style>`.
- **Admin** (`telas_administracao.py:15-241`): `bloco_aparencia` + `card "Coleta"` (switch `data-testid=agregador-habilitado` + select `agregador-intervalo` 10/30/60/120/180/360 + input `agregador-termo` + **input `agregador-hora-reinicio` `09:00` + `rodape data-testid=agregador-salvar-coleta` + `Coletar agora` + `Limpar antigas`**) + `card "Fontes"` (`data-testid agregador-fonte-tipo/nome/tema/url`, `estado_fontes` + `render_fontes` + `Adicionar fonte` `data-testid=agregador-add-fonte` + `rodape data-testid=agregador-salvar-fontes`) + `card "Temas"` (`data-testid=agregador-temas`, `rodape data-testid=agregador-salvar-temas`) + **`card "Censura"` + `card "Reinício diário — banco reciclado"` (substitui `painel_backup`, `data-testid=agregador-reiniciar-agora` `Zerar agora`)**.

## Regras de negócio relevantes

- **Habilitado** (`habilitado()`/`definir_habilitado(bool,ator)` — `bd_manipulador.py:77-85`): `get_config("agregador_noticias_habilitado","0")=="1"`; `set_config` + `audit configurar habilitado`; `init_db` semente `0` (desabilitado).
- **Intervalo** (`intervalo_min()`/`definir_intervalo(min,ator)` — `bd_manipulador.py:88-101`): `int(get_config("agregador_noticias_intervalo_min","60"))` com `try` fallback `60` + `clamp 60–9360 (min(360,v))`; `definir_intervalo` `clamp 60–9360` + `audit` + `return ok,v` (`v` clampado).
- **Termo** (`termo_pesquisa()`/`definir_termo(termo,ator)` — `bd_manipulador.py:104-112`): `get_config("agregador_noticias_termo_pesquisa","").strip()`; `definir_termo` `strip` + `audit`.
- **Fontes** (`fontes_config()`/`definir_fontes(list,ator)` — `bd_manipulador.py:115-138`): `json.loads(get_config("agregador_noticias_fontes_json",""))` → `list` se `isinstance(list) and dados` senão `FONTES_PADRAO`; `definir_fontes` `json.dumps(ensure_ascii=False)` + `set_config` + `audit configurar fontes_json N fontes`.
- **Temas** (`temas_config()`/`definir_temas(list, ator)` (dedupe `vistos`/`unicos` 20/09/2026) — `bd_manipulador.py:140-157`): `json.loads(temas_json)` → dedupe preservando ordem (`vistos`/`unicos`, `strip`) senão `TEMAS_PADRAO`; `definir_temas` dedupe (`vistos`/`unicos` `strip`) + `audit`.
- **Hora reinício** (`obter_hora_reinicio()`/`definir_hora_reinicio(hora_str,ator)` — `bd_manipulador.py:160-186`): `get_config("agregador_noticias_hora_reinicio","09:00")` validado `re.match HH:MM` `00–23:00–59` → `f"{h:02d}:{mi:02d}"` ou `09:00` fallback; `definir` valida `HH:MM`, normaliza, `audit configurar hora_reinicio`, `return False+msg` se inválido.
- **Reiniciar banco** (`reiniciar_banco(ator)` — `bd_manipulador.py:189-204`): `SELECT COUNT(*)` + `DELETE FROM tb_noticia` + `commit` + `log info` + **`audit reiniciar_banco N notícias + hora`**; job diário `agregador_reinicio` `CronTrigger` às `hora_reinicio`.
- **Tempo real da postagem** (`_parse_data_pub(raw)` — `bd_manipulador.py:267-311`): tenta `email.utils.parsedate_to_datetime` (robusto RFC822 `Tue, 19 Sep 2026 12:34:56 GMT`) → `astimezone().replace(tzinfo=None)` → `YYYY-MM-DD HH:MM:SS`; fallback ISO/RSS (`%Y-%m-%dT%H:%M:%S%z`, `%Y-%m-%dT%H:%M:%S.%f%z`, `%Y-%m-%dT%H:%M:%S`, `%Y-%m-%d %H:%M:%S`, `%a, %d %b %Y %H:%M:%S %z/%Z`, `%d/%m/%Y %H:%M`, normaliza `Z`→`+00:00`, `+00:00`→`+0000`, regex `YYYY-MM-DD[ T]HH:MM:SS`) → `None` se falhar; usado em `_coletar_google/bbc/jfp/rss` para extrair `time[datetime]`/`pubDate`/`dc:date` real e passar para `inserir_noticia`.
- **Relativo** (`_parse_relativo_para_absoluto(texto)` — `bd_manipulador.py:523-551`): `"Ontem"`, `"3 horas atrás"` → `now - delta` → `YYYY-MM-DD HH:MM:SS` usado em `_coletar_google` fallback.
- **Inserir** (`inserir_noticia` — `bd_manipulador.py:399-443`): `titulo[:500]`, `url[:2000]`, `url "/"→"https://news.google.com"+url` (relativa Google), `fonte[:100]`, `tema[:50] or Geral`, `imagem[:2000]`, `desc[:1000]`, **deduplicação: `SELECT 1 WHERE url=?` (UNIQUE) + loop `SELECT titulo` com `_norm_tit` (`unicodedata.normalize NFKD → ascii ignore → lower → " ".join(split)`) — evita notícia já incluída com mesmo título case-insensitive sem acentos ou mesma URL antes de `INSERT OR IGNORE` + `COALESCE(data_pub, datetime('now'))`**, censura `titulo_bloqueado` descarta → `return rowcount>0`.
- **Listar** (`listar_noticias(tema,limite,offset)` — `bd_manipulador.py:314-325`): `SELECT ... WHERE tema=? ORDER BY COALESCE(data_publicacao, data_coleta) DESC, data_coleta DESC LIMIT ? OFFSET ?` / `ORDER BY COALESCE(...) DESC LIMIT/OFFSET` sem tema; **paginação 12** `por_pagina=12` `total_pag` `offset` com botões `Primeira/Anterior/Próxima/Última` `data-testid=agregador-*` no `grid()`; `contar_noticias(tema?)` (`bd_manipulador.py:254-264`); `listar_para_tv(limite=10)` (`bd_manipulador.py:330-352` `SELECT titulo,descricao,url,imagem_url,fonte,tema ORDER BY COALESCE(data_publicacao, data_coleta) DESC, data_coleta DESC LIMIT ?*3` filtrando censuradas via `titulo_bloqueado` → `[{"titulo","descricao":desc or titulo,"url","imagem","fonte","tema"}]`).
- **Limpar** (`limpar_antigas(horas=24)` — `bd_manipulador.py:384-397`): `DELETE WHERE data_coleta < datetime('now','-N hours')` (portável: `banco_conexao` traduz `datetime('now','-24 hours')` → `LOCALTIMESTAMP`/`CURRENT_TIMESTAMP` no Postgres proxy) + `rowcount n` + `log info` **sem `audit`** (postagens não auditadas); chamada ao fim de `coletar_todas`.
- **Limpar censuradas** (`limpar_censuradas()` — `bd_manipulador.py:354-381`): `SELECT id,titulo` → `titulo_bloqueado` → `DELETE WHERE id=?` + `log info` **sem audit**; chamada ao salvar censura.
- **Reiniciar** (`reiniciar_banco(ator)` — `bd_manipulador.py:189-204`): `DELETE FROM tb_noticia` (zera todas) + **`audit reiniciar_banco`** (quem alterou); usado pelo `CronTrigger` diário `09:00` + botão `Zerar agora`.
- **Coleta** (`coletar_todas(ator, forcar=False)` — `bd_manipulador.py:910-946`): `if not forcar and not habilitado(): 0` + `fontes_config()` + `termo_pesquisa()` → `total=0` + loop `for f in fontes: tipo=(tipo or google).lower(), url, tema or Geral, nome or url[:30]; tipo google→_coletar_google, bbc→_coletar_bbc, jfp→_coletar_jfp, rss→_coletar_rss, else→_coletar_google` (fail-soft `warning`) + `termo → _coletar_pesquisa_google(termo,Geral)` (via **RSS** `/rss/search`, HTML `/search` dá 429/captcha) + `limpar_antigas(24)` (`try` **sem audit**) + `log info` **sem `_audit coletar`** (auditoria só quem alterou config).
- **`_get_html(url,timeout=12)`** (`bd_manipulador.py:447-455`): `httpx.get(url, timeout, follow_redirects=True, headers={"User-Agent": `UA_COLETA` (`Mozilla/5.0 Chrome/126` comum, `bd_manipulador.py:531`)})` → `r.text` se `200` senão `""` (`warning` em exceção; `429` em HTML `news.google.com` não-RSS arma cooldown 30 min `COOLDOWN_429_SEG` e `_coletar_google` pula). **Coleta educada 20/09/2026**: `_aguardar_cortezia()` (`CORTEZIA_SEG=1.5s` + jitter 0–1s, nunca rajada) antes de cada requisição, `_url_ja_coletada(url)` evita `og:image` de repetida, sem retry agressivo (Google 429/captcha por IP — RSS oficial é a via).
- **Parsers** (`parsel.Selector`): Google `".gPFEn, .JtKRv, .a7P8L, article"` + `a::text`/`href` (`.`/`/`→ `https://news.google.com`) + `img::attr(src/data-src)` + **normalização `_normalizar_imagem_url` (`//`→`https:`, `/`→`base news.google.com`, `srcset`→1ª URL, 20/09/2026)** + `time[datetime]`→`_parse_data_pub` (20, cooldown 429 pula coleta); BBC `".bbc-uk8dsi, .bbc-19j92fr, article, a[href*='/portuguese/articles']"` (`/`→ `https://www.bbc.com`) + `time[datetime]` (15); JFP `".td-module-title"` + `time[datetime]`/`.td-post-date` (15); RSS `type="xml"` `item` → `title` + `link` + `description ::text` todos os nós (CDATA/HTML) + fallback `content:encoded` + limpeza HTML (`unescape`+strip tags) + supressão de resumo redundante (NFKD `desc==titulo`/prefixo→`""`) + `pubDate`/`dc:date`/`published`→`_parse_data_pub` + `media:content` + `media:thumbnail` (BBC) + `enclosure` + fonte real `<source>` + favicon `s2` + pré-checagem `_url_ja_coletada` + `_og_image` fail-soft 6s (20/09/2026) (15); pesquisa Google via RSS `https://news.google.com/rss/search?q={quote(termo)}&hl=pt-BR&gl=BR&ceid=BR:pt-419` → `_coletar_rss` (HTML `/search` dá 429/captcha).
- **LGPD**: notícias públicas sem vínculo por usuário; sem `remover_vinculos` ainda (futuro se necessário).
- **Censura**: `inserir_noticia` descarta bloqueadas, `listar_para_tv` filtra `LIMIT*3` com `titulo_bloqueado`, `limpar_censuradas` remove já coletadas (`bd_manipulador.py:306-396`).

## Censura de conteúdo — palavras bloqueadas (central `mod_intranet/censura.py`)

Funcionalidade compartilhada Blog ↔ Agregador (chave única `conteudo_palavras_bloqueadas` em `tb_config` central):

- **Núcleo** (`censura.py:1-95`): `CHAVE_CONFIG="conteudo_palavras_bloqueadas"` · `obter_palavras_bloqueadas()` (split `,;\n` + JSON fallback, `lower`) · `definir_palavras_bloqueadas(lista, ator)` (normaliza `lower` dedup, grava CSV via `set_config`, `audit_log` `censura/palavras_bloqueadas`) · `titulo_bloqueado(titulo, palavras=None)` / `filtrar_titulo` → `(bloqueado, palavra)` com `_normalizar` `lower+NFD` sem acentos (`suicidio` bloqueia `suicídio`, substring insensível) — docstring bilíngue EN/PT-BR.
- **Agregador** (`bd_manipulador.py:399-443` `inserir_noticia` descarta censurada; `328-352` `listar_para_tv` filtra `LIMIT*3` → `titulo_bloqueado`; `354-381` `limpar_censuradas()` remove já coletadas censuradas).
- **Blog** (`bd_manipulador.py:646-703`): `criar/atualizar` bloqueiam título censurado.
- **Admin Agregador** (`telas_administracao.py:187-241`): card `Censura de conteúdo — palavras bloqueadas` (`block`, `data-testid=agregador-palavras-bloqueadas`, `textarea` CSV/;/linha, `Salvar censura` `data-testid=agregador-salvar-censura` + `Restaurar`, ao salvar `definir_palavras_bloqueadas` + `limpar_censuradas`) + botão `Remover já censuradas agora` (`data-testid=agregador-limpar-censuradas`).
- **Admin Blog** (`mod_blog/telas_administracao.py:72-106`): mesmo card (`data-testid=blog-palavras-bloqueadas`); ao salvar dispara a purga via **`integracoes.limpar_noticias_censuradas()`** (25/09/2026) — o Blog **não** importa `mod_agregador_noticias` direto (AGENTS.md §2). Ver *Atualização 25/09/2026 — censura compartilhada orquestrada pelo núcleo* abaixo.
- **Normalização**: `lower` + `NFD` remove `Mn` → `suicidio` bloqueia `suicídio`; substring (não exige palavra inteira).
- **RNF**: persistência `banco_conexao` WAL por módulo, auditoria `censura/palavras_bloqueadas`, segurança `lower+NFD` substring, performance `limpar_censuradas` sem travar TV (TV filtra em `LIMIT*3`), usabilidade textarea CSV/;/linha.

## Integrações com o núcleo

Importa `autenticacao.validar_acesso_modulo`/`perfil_global_de`/`eh_admin_do_modulo`, `banco_conexao.conexao`/`get_config`/`set_config`, `tema_modulo.ler_tema`/`notificar`/`bloco_aparencia`, `ui_comum.botao`/`card_admin`/`rodape_salvar_restaurar`, `observabilidade.get_logger`. Grava via `audit_log` → `tb_auditoria_agregador_noticias` (**só quem alterou o quê**: `definir_habilitado/intervalo/termo/fontes/temas/hora_reinicio/reiniciar_banco` auditam `configurar`/`reiniciar_banco`; `coletar_todas`/`limpar_antigas`/`limpar_censuradas` **sem audit**). Agendadores `rotinas._job_agregador_coleta` (`interval minutes` + `CronTrigger` hora) + `_job_agregador_reinicio` (`CronTrigger hora_reinicio` `09:00` default → `reiniciar_banco` `DELETE`) + `reconfigurar_agregador_noticias()` (`pause/resume`+`reschedule minutes`+`reschedule CronTrigger`). **Sem backup**: `MAPA_BACKUPS` sem `agregador_noticias`, `painel_backup` removido, card `Reinício diário — banco reciclado` com `Zerar agora` `data-testid=agregador-reiniciar-agora`. `PREFIXO_POR_CHAVE`/`PADROES_TEMA`/`MODULOS_SISTEMA`/`MODULOS_BD` com `agregador_noticias`. `bd_criador.py` init_agregador no `mod_intranet/bd_criador.py`. TV `mod_filas` consome `listar_para_tv`.

## Atualização 25/09/2026 — censura compartilhada orquestrada pelo núcleo

> A lista de **palavras bloqueadas** é a **mesma** para o Blog, o Agregador e a
> TV de Filas (uma chave só). Em 25/09/2026, o `telas_administracao.py` do
> **Blog** deixou de importar `mod_agregador_noticias` para fazer a purga e
> passou a chamá-la pela fachada `mod_intranet.integracoes`
> (AGENTS.md §2). Commit `624c9d5`.

### Quem orquestra a purga — e por que o Blog

O **Blog** é o módulo que tem a tela de **administração da lista de censura** com
o card "Censura de conteúdo — palavras bloqueadas" (`mod_blog/telas_administracao.py:72-106`,
`data-testid=blog-palavras-bloqueadas`). Ao salvar a lista, ele dispara a purga
das notícias **já coletadas** cujo título passou a estar bloqueado:

```python
# ANTES — Blog importava o Agregador diretamente (violava AGENTS.md §2)
from mod_agregador_noticias.bd_manipulador import limpar_censuradas
n = limpar_censuradas()

# DEPOIS — quem costura é o núcleo
from mod_intranet import integracoes
n = integracoes.limpar_noticias_censuradas()
if n:
    notificar(f"{n} notícias censuradas removidas do agregador", type="info")
```

!!! note "O Agregador também tem o seu próprio botão de purga"
    `mod_agregador_noticias/telas_administracao.py:226` e `:246` chamam
    `limpar_censuradas()` **de dentro do próprio módulo** (intracomponente, o que
    é permitido). São **dois pontos de entrada** para a mesma rotina — o botão
    "Remover já censuradas agora" (`data-testid=agregador-limpar-censuradas`) no
    Agregador e o disparo automático ao salvar a censura no Blog.

### `mod_intranet/censura.py` — o núcleo compartilhado

Chave **única** em `tb_config` **central**: `conteudo_palavras_bloqueadas`.

| Função | Comportamento |
|:---|:---|
| `obter_palavras_bloqueadas()` | Lê a chave, faz `split` por `,` / `;` / `\n`, com **fallback para JSON**, e normaliza em `lower` |
| `definir_palavras_bloqueadas(lista, ator)` | Normaliza (`lower`), **deduplica**, grava o CSV via `set_config` e audita (`audit_log` → `censura/palavras_bloqueadas`) |
| `titulo_bloqueado(titulo, palavras=None)` | Devolve `(bloqueado, palavra)` — tupla, para o chamador **saber qual** palavra bloqueou |
| `filtrar_titulo(...)` | Variante de filtragem direta |

**Normalização (o ponto que importa)** — `_normalizar` aplica **`lower` + NFD
removendo os diacríticos (`Mn`)**:

| Entrada gravada | Título testado | Bloqueia? |
|:---|:---|:---:|
| `suicidio` | `suicídio` | ✔ (o acento é ignorado) |
| `SAÚDE` | `saúde pública` | ✔ (case-insensitive) |
| `violencia` | `violência no trânsito` | ✔ (**substring** — não exige palavra inteira) |

!!! warning "A comparação é por **substring**, não por palavra inteira"
    Bloquear `vaca` também bloquearia `vacinação`. A lista de censura precisa ser
    montada com termos **longos e específicos** para não produzir falsos
    positivos.

### Os três consumidores

| Consumidor | Ponto de aplicação | Comportamento |
|:---|:---|:---|
| **Blog** | `bd_manipulador.py:criar_postagem` / `atualizar_postagem` | `titulo_bloqueado(titulo)` **antes** do `nh3`. Se bloqueado → retorno `None`/`False` + `warning` no log + `notificar("Título contém palavra bloqueada: ...")` — **não sanitiza e não grava** |
| **Agregador** | `bd_manipulador.py:inserir_noticia` | Descarta a notícia na **coleta** — o banco nunca chega a receber o título censurado |
| **Agregador → TV** | `bd_manipulador.py:listar_para_tv` | Filtra **na origem da TV**: busca `LIMIT × 3` e descarta as censuradas, devolvendo até `limite` itens válidos (assim a TV nunca fica sem notícia por causa de censura) |
| **Agregador (pago)** | `bd_manipulador.py:limpar_censuradas` | Remove as **já coletadas** que ficaram censuradas depois da alteração da lista; retorna `n` |

### Diagrama da censura compartilhada

```mermaid
graph TD
  CFG["tb_config central<br/>conteudo_palavras_bloqueadas<br/>(CSV)"]
  CENS["mod_intranet/censura.py<br/>obter / definir / titulo_bloqueado<br/>lower + NFD sem acento, substring"]
  CFG --> CENS

  CENS --> BLOGDB["mod_blog<br/>criar/atualizar_postagem<br/>bloqueia ANTES do nh3"]
  CENS --> AGDB["mod_agregador_noticias<br/>inserir_noticia descarta"]
  CENS --> TV["mod_filas (TV)<br/>listar_para_tv filtra"]

  BLOGADM["Admin Blog<br/>blog-salvar-censura"] --> CENS
  BLOGADM -.->|integracoes.limpar_<br/>noticias_censuradas| PURGA["Agregador<br/>limpar_censuradas"]
  AGADM["Admin Agregador<br/>agregador-limpar-censuradas"] --> PURGA
```

### Complemento — coleta multi-fonte, grid e limpeza 24 h

#### Coleta multi-fonte (`httpx` + `parsel`)

O coletor é **scrapy-like** e espelha o repositório `klaytonPrinceMS/Noticia`
(`Sites` + `Noticias.get_noticiasGN/BBC/JFP/RSS`). Quatro despachantes, escolhidos
pelo campo `tipo` de cada fonte:

| `tipo` | Despachante | Alvo |
|:---|:---|:---|
| `google` | `_coletar_google` | Google News por tema (`gn_brasil`, `gn_saude`, …) |
| `bbc` | `_coletar_bbc` | BBC Português |
| `jfp` | `_coletar_jfp` | JFP Notícias (Monte Santo de Minas) |
| `rss` | `_coletar_rss` | RSS oficial (a maioria das 24 fontes padrão) |
| *(outro)* | `_coletar_google` | Fallback |

**24 fontes padrão** (`FONTES_PADRAO`, len()==24 conferido em 27/09/2026): 3 legadas (Google Brasil, Google Saúde,
BBC) + 8 RSS V1 (Agência Brasil, Senado, G1 Últimas/Economia/Saúde/Tecnologia,
Poder360, Folha) + 4 de cobertura V2 (G1 Mundo→`Internacional`, G1 Pop e
Arte→`Entretenimento`, GE Esporte, JFP→`Monte Santo de Minas`). O `init_db`
promove LEGADO/V1 → atual **apenas** para quem nunca customizou.

**Coleta educada (anti-ban)** — o Google bloqueia por IP e por padrão
robotizado (429/captcha comprovado com `httpx` **e** Chromium real):

| Mecanismo | Valor |
|:---|:---|
| `UA_COLETA` | `Mozilla/5.0 … Chrome/126` (User-Agent comum) |
| `_aguardar_cortezia()` | `CORTEZIA_SEG = 1.5` s + jitter de 0–1 s **antes de cada** requisição — nunca rajada |
| Cooldown de 429 | `COOLDOWN_429_SEG = 1800` (30 min); `_GOOGLE_HTML_BLOQUEADO_ATE` faz `_coletar_google` pular |
| Sem retry agressivo | RSS oficial é a via viável; `Scrapy`/`Playwright`/`Selenium` não burlam o bloqueio |
| Termo livre | `_coletar_pesquisa_google` usa `news.google.com/**rss/search**` (o HTML `/search` dá 429/captcha) |
| Pré-checagem | `_url_ja_coletada(url)` evita re-buscar `og:image` de URL já coletada |
| Timeout | 12 s no HTML, 6 s no `og:image` (fail-soft) |

**Deduplicação em duas camadas** (`inserir_noticia`): `SELECT 1 WHERE url=?`
(`url` é `UNIQUE`) **e** um laço `SELECT titulo` com `_norm_tit`
(`NFKD` → ascii → `lower` → `join`) — evita duplicata com **mesmo título**,
case-insensitive e sem acento, antes do `INSERT` (que vira
`ON CONFLICT DO NOTHING` no Postgres pelo proxy de `banco_conexao`).

#### Grid responsivo 3 → 2 → 1, card de altura fixa e paginação 12

| Elemento | Implementação |
|:---|:---|
| **Colunas** | `.grid-noticias { display:grid; grid-template-columns: repeat(3,1fr); gap:1rem }` + media queries `max-width:1024px → 2`, `max-width:640px → 1` |
| **Altura do card** | `.card-noticia { height: 250px }` (celular `220px`) — **altura FIXA, nunca `min/max-height`**: é isso que garante que todos os cards de uma linha fiquem idênticos. Antes, `min-height:160px; max-height:220px` deixava a altura depender do conteúdo, e a página ficava irregular. O valor é uma escolha de layout, não um número derivado da média de notícias |
| **Miniatura** | `120×120` (`flex: 0 0 120px`, `align-self: flex-start`, `border-radius: 8px`, `box-shadow: inset 0 0 0 1px rgba(0,0,0,.10)`) com `object-fit: cover` (era `30×30`); moldura com `cursor: zoom-in`, `role="button"`, `tabindex="0"`, `aria-label`, `data-testid=agregador-ampliar-<id>` e `tooltip("Ampliar imagem")` |
| **Ampliação** | `dialogo_card` (`ui_comum.py:294`, fecha por ESC/clique fora) com `ui.image` em **60vw × 60vh** (`88vw × 58vh` no celular), `object-fit: contain` (**não distorce nem corta**), `alt` descritivo e botão "Fechar". Diálogo **memoizado por card** e montado **só no 1º clique** |
| **Marca d'água** | Logo da fonte (`fonte_icon_url`) em `32×32` no rodapé direito da miniatura (`right:4px; bottom:4px`), `opacity: .65`, `pointer-events: none`, `z-index: 2` e `drop-shadow` claro+escuro. Sem imagem, o mesmo logo vira ícone `16×16` `contain` ao lado do badge do tema |
| **Resumo** | Texto **completo** (nunca `desc[:180] + "…"`): `flex: 1 1 auto; min-height: 0; overflow-y: auto; overflow-x: hidden` + `scrollbar-width: thin` e `::-webkit-scrollbar` de 5px. Sem descrição (ou igual ao título) → `"Sem resumo disponível."` em `text-grey-5` |
| **Título** | `ui.link(texto, target=href, new_tab=True)` em `card-noticia__titulo` — `font-weight:700`, `line-height:1.25`, `word-break: break-word` e `-webkit-line-clamp: 3` (no máximo 3 linhas; o **resumo** é que rola) |
| **Paginação** | `por_pagina = 12`; `total_pag = max(1, (total+11)//12)`; `offset = (pagina-1)*12`; botões `Primeira` / `Anterior` / `Próxima` / `Última` (`data-testid=agregador-primeira` / `-anterior` / `-proxima` / `-ultima`) + rótulo `Página X de Y • N notícias` |
| **Ordenação** | `ORDER BY COALESCE(data_publicacao, data_coleta) DESC, data_coleta DESC` — **mais atual → mais antiga**, com o tempo real da postagem (`_parse_data_pub`, RFC822/ISO) e não o horário da coleta |
| **Busca** | **Global** (ignora o filtro de tema): `listar_noticias(tema=None, limite=500)` filtrado em memória com `NFKD` sobre título/descrição/fonte/tema; `debounce 300`; digitar **reseta** para a página 1 |
| **Injeção do CSS** | `ui.add_head_html` **fora** do `@ui.refreshable` (`telas.py:320-354`): dentro, o `<style>` era reemitido a cada busca/paginação |

!!! warning "Acessibilidade do clique na miniatura"
    O clique na imagem **não** pode Herdar a navegação do link do título. A solução
    adotada tem **duas** camadas: a moldura da miniatura é **irmã** do link do título
    (nunca é filho nem ancestral dele), e o `click.stop` usa o **modificador nativo** do NiceGUI
    (`Vue.withModifiers`, sem JavaScript à mão). O `role="button"` + `tabindex="0"` +
    `keydown.enter`/`keydown.space` + `aria-label` + `focus-visible` com outline fazem o
    alvo operável por teclado; `pointer-events: none` na marca d'água garante que ela não
    roube o clique.

#### Tela pura (`telas_puro.py`) — REMOVIDA em 26/09/2026

Rota `/agregador-noticias-puro` — 145 linhas, **sem paginação** (12 fixas), sem
filtro/busca, com o layout do modelo `Noticia` (`intro-overlay` + `about` +
`info-list`) e o CSS/JS original servido por `main.py:818`
`@app.get("/assets/noticia/{caminho:path}")` (anti path-traversal com `normpath` +
`startswith(base)`). Acesso **por URL direta** — o botão `agregador-ver-puro` foi
removido de `/agregador-noticias` em 20/09/2026.

**Saiu em 26/09/2026**: a tela era réplica de teste do modelo `Noticia`, sem
funcionalidade própria. Com ela foram removidos `mod_agregador_noticias/telas_puro.py`
e os 4,9 MB de `assets/noticia/{css,fonts,images,js}`. **Preservado**:
`assets/noticia/favicon.png`, porque o fallback de `/api/attachments/` o usa como
imagem de substituição quando a TV ou o Blog apontam para anexo externo quebrado
— a rota `/assets/noticia/{caminho:path}` continua, servindo **só** esse arquivo
e devolvendo `404` para qualquer outro nome. A análise dedicada ficou registrada
em `docs/registro_de_mudancas/` na sessão de 26/09/2026.

#### `listar_para_tv` — o carrossel da TV de Filas

```python
# mod_agregador_noticias/bd_manipulador.py
SELECT titulo, descricao, url, imagem_url, fonte, tema
  FROM tb_noticia
 ORDER BY COALESCE(data_publicacao, data_coleta) DESC, data_coleta DESC
 LIMIT ? * 3          # pede 3x e filtra a censura no Python
```

| Garantia | Detalhe |
|:---|:---|
| **Censura já aplicada** | Busca `LIMIT × 3` e descarta censuradas com `titulo_bloqueado` — a TV **nunca** exibe título bloqueado e **nunca** fica sem notícia por causa da censura |
| **`descricao or titulo`** | A TV nunca mostra um card vazio |
| **Desabilitado** | `integracoes.agregador_habilitado()` falso → a TV cai num *placeholder* de pausa, não em erro |
| **Consumo na TV** | `mod_filas/telas.py`: `carregar_noticias(limite=200)` + `_mostrar_noticia` com `ui.timer 15.0` (rotação) e `ui.timer 120.0` (recarga) no rodapé escuro |

#### Limpeza 24 h e reciclagem diária

| Mecanismo | Gatilho | O que faz |
|:---|:---|:---|
| `limpar_antigas(horas=24)` | Fim de **cada** `coletar_todas` | `DELETE WHERE data_coleta < datetime('now','-24 hours')` — portável: o proxy de `banco_conexao` traduz para `LOCALTIMESTAMP`/`CURRENT_TIMESTAMP` no Postgres. Log `info` + **`sem audit`** (postagens não são auditadas) |
| `rotinas._job_agregador_coleta` | `interval minutes` (60–9360, clamp) | `coletar_todas()` quando habilitado; `pause`/`resume` + `reschedule` por `reconfigurar_agregador_noticias()` sem reiniciar o sistema |
| `rotinas._job_agregador_reinicio` | **`CronTrigger` diário** na `hora_reinicio` (padrão `09:00`, `HH:MM` validado) | `reiniciar_banco(ator)` → `DELETE FROM tb_noticia` + `audit reiniciar_banco N notícias + hora` |
| **Sem backup** | — | `MAPA_BACKUPS` **não** tem `agregador_noticias` e o admin **não** tem `painel_backup`: o banco é **reciclado**, não preservado. No admin, o card "Reinício diário — banco reciclado" com `Zerar agora` (`agregador-reiniciar-agora`) substitui o card de backup |

!!! note "Por que reciclar em vez de fazer backup"
    Notícias são **efêmeras** por natureza: a tela mostra as 12 mais recentes e o
    carrossel da TV renova a cada 15 s. Guardar cópias não agrega valor e só
    consome espaço — recriar a base às 09:00 garante o mesmo resultado com
    I/O zero.

## Pontos de atenção

- **RESOLVIDO (era PENDÊNCIA de 22/09/2026) — `models/__init__.py` não é mais stub**: o arquivo agora compila e traz o `dataclass Noticia` **completo** (10 campos: `id, titulo, fonte, tema, url, imagem_url, fonte_icon_url, descricao, data_publicacao, data_coleta`) com docstring bilíngue. Ele continua sendo **espelho de leitura, sem acesso a banco** (docstring do módulo: "NÃO é importado em runtime e NÃO abre conexão" — evita cross-query entre bancos, AGENTS.md §2). **Resta** a propagação do padrão imperativo do AGENTS.md §3.1: os outros `models/` (`mod_filas`, `mod_lista_telefonica`, `mod_tecnico`) já usam `Table` + `dataclass` + `map_imperatively()`, e o do agregador ainda **não** — só a dataclass, sem `map_imperatively()`. Como ele não é importado em runtime, isso não é bug; é dívida de padrão.
- Habilitado default `0` — sem coleta até admin habilitar; `reconfigurar_agregador_noticias()` (`rotinas.py:256`) `pause` quando desabilitado, `resume+reschedule` quando habilitado + `CronTrigger` hora (sem restart).
- Intervalo `clamp 60–9360` — `intervalo_min()` e `definir_intervalo` garantem faixa; admin select limita a 6 opções, API aceita qualquer `60–9360`.
- **Hora `09:00` configurável + reinício diário `CronTrigger` + sem backup**: `obter_hora_reinicio()`/`definir_hora_reinicio(HH:MM)` validam `00–23:00–59`, normalizam `09:00`, auditam, `reconfigurar_agregador_noticias()` reaplica `CronTrigger(hour=H, minute=M)` sem restart; `reiniciar_banco(ator)` `DELETE` + `audit` + `Zerar agora` `data-testid=agregador-reiniciar-agora`; `MAPA_BACKUPS` sem `agregador_noticias`, `telas_administracao` sem `painel_backup` — banco reciclado.
- **Auditoria só quem alterou o quê**: `definir_*` + `reiniciar_banco` auditam; `coletar_todas`/`limpar_*` **sem audit** (postagens não auditadas).
- **Paginação 12 + grid responsivo 3→2→1 + card de ALTURA FIXA — mais atual → mais antiga**: `estado pagina=1` `por_pagina=12` `total_pag=max(1,(total+12-1)//12)` `offset=(pagina-1)*12` `listar_noticias(tema_f, limite=12, offset=offset)` `ORDER BY COALESCE(data_publicacao, data_coleta) DESC`; botões `agregador-primeira/anterior/proxima/ultima` + label `Página X de Y • N notícias` + `Exibindo len de total`; `.grid-noticias {display:grid; grid-template-columns: repeat(3,1fr)}` + `@media 1024px→2 640px→1` + **`.card-noticia {height: 250px}` (celular `220px`) — altura FIXA, nunca `min/max-height`**, miniatura `120×120` ampliável antes do título, sem fonte textual/botão/card-TV.
- **Deduplicação por URL + título normalizado** (`inserir_noticia` + `_norm_tit` NFKD lower): `SELECT 1 WHERE url=?` (UNIQUE) + `SELECT titulo` loop com `_norm_tit` (`NFKD → ascii ignore → lower → join`) — evita duplicata com mesmo título case-insensitive sem acentos ou mesma URL; `INSERT OR IGNORE` vira `ON CONFLICT DO NOTHING` no Postgres via `_CursorPostgres`.
- **Timer com tempo real** (`_parse_data_pub` + `COALESCE(data_publicacao, data_coleta) DESC` + `_tempo_relativo`): `_parse_data_pub` reescrito via `email.utils.parsedate_to_datetime` + fallback ISO/RSS → `YYYY-MM-DD HH:MM:SS` usado em todos os coletores (`time[datetime]`, `pubDate`) para `data_publicacao` real; `listar_noticias`/`listar_para_tv` ordenam por `COALESCE(data_publicacao, data_coleta) DESC`; `telas.py _tempo_relativo` usa `data_pub` real ou `data_col` fallback (`agora`/<60s, minutos/<60m, horas/<24h, dias/<7d, semanas/<30d, meses/<365d, anos, `delta<0→0`, `T`/`Z`/fração, fallback `[:16]`).
- `datetime('now','-N hours')` portável — `banco_conexao` traduz para `LOCALTIMESTAMP` no Postgres (`_CursorPostgres._preparar` + `_ddl_postgres`).
- `httpx`+`parsel` (`requirements.txt`); sem internet coleta `0` (fail-soft); `User-Agent` comum `UA_COLETA` Chrome/126; timeout `12s` HTML / `6s` `og:image`; `try/except` com `warning` em cada coletor; `CORTEZIA_SEG=1.5s`+jitter, cooldown 30 min após 429, `_url_ja_coletada` pré-checagem (20/09/2026).
- `url` relativa Google normalizada em `inserir_noticia` + `_coletar_google` (`./`/`/`→`https://news.google.com`).
- `listar_para_tv` `descricao or titulo` — TV nunca mostra vazio; `habilitado()==False` → placeholder desabilitado; vazio → placeholder aguarde.
- **Card sem fonte textual e sem botão, com tempo relativo + miniatura `120×120` ampliável + marca d'água da fonte + resumo com scroll, grid responsivo 3→2→1 + paginação 12 + card de ALTURA FIXA, sem card TV** (`telas.py:65-107` `_tempo_relativo` + `telas.py:109-226` `_desempacotar_noticia`/`_criar_dialogo_noticia`/`_abrir_dialogo_noticia`/`_midia_noticia` + `telas.py:228-292` `_noticia_card` + `357-436` `grid()`): `tb_noticia.fonte` continua gravada (útil para `listar_para_tv` e auditoria) mas **não é renderizada como texto no card** — vira **marca d'água `32×32`** sobre a miniatura; `data_pub` real via `_parse_data_pub` ou `data_col` fallback com `[:16]` absoluto substituído por relativo `agora`/minutos/horas/dias/semanas/meses/anos (parse flexível `T`/`Z`/fração, `delta<0→agora`); **miniatura `120×120` (`120px object-cover` `fit=cover`) clicável que abre a ampliação em `dialogo_card` (60vw×60vh `contain`, ESC/botão "Fechar") + `badge tema` + `titulo` `ui.link(target=href, new_tab=True)` + `descricao` COMPLETA com `overflow-y: auto`** (antes `descricao[:180]…`); **botão "Abrir notícia" removido 19/09/2026 + card TV `bg-blue-50` removido, substituído por paginação 12 com 4 botões**, mantém **grid responsivo `.grid-noticias` 3→2→1 + `.card-noticia {height: 250px}` + paginação `Página X de Y`**.

- **Coleta educada anti-ban + termo via RSS (20/09/2026)**: `UA_COLETA` `Mozilla/5.0 Chrome/126` comum + `_aguardar_cortezia()` (`CORTEZIA_SEG=1.5s` + jitter 0–1s, nunca rajada) antes de cada `_get_html`/`_og_image` + sem retry agressivo + `429` em HTML `news.google.com` (não-RSS) arma `_GOOGLE_HTML_BLOQUEADO_ATE` = now + `COOLDOWN_429_SEG=1800` (30 min) e `_coletar_google` pula com `warning`; `_url_ja_coletada(url)` (`SELECT 1 WHERE url`) evita `og:image` de repetida. Motivo: Google bloqueia por IP + padrão robotizado (429/captcha no `/search` comprovado com httpx E Chromium real; Scrapy/Playwright/Selenium não burlam — via viável é RSS oficial + tráfego "regular"). Termo livre via `_coletar_pesquisa_google` → `https://news.google.com/rss/search?q=...` → `_coletar_rss` (nunca HTML `/search`).
- **Enriquecimento RSS (20/09/2026)**: `description ::text` todos os nós (CDATA/HTML) + fallback `content:encoded` + limpeza HTML do Google RSS (`unescape` + strip tags) + supressão de resumo redundante (NFKD `desc==titulo`/prefixo → `""`, card oculta `desc` vazia) + `media:content` + `media:thumbnail` (BBC) + `enclosure` (jpg/png/webp) + fonte real `<source>` + favicon `s2` (`google.com/s2/favicons?domain=<dom>&sz=32`, domínio de `source@url` ou do link) + `_og_image` (`og:image`/`twitter:image`, timeout 6s, fail-soft) quando sem imagem. Imagem relativa normalizada via `_normalizar_imagem_url` (`//`→`https:`, `/api/attachments` relativo→absoluto `news.google.com`, `srcset`→1ª URL); `inserir_noticia` só zera `/api/attachments` relativo/localhost — absoluto `news.google.com/api/attachments` é thumbnail real e é preservado.
- **15 fontes + migração V1/V2 + busca global + temas dedupe + sem botão puro (20/09/2026)**: `FONTES_PADRAO` 15 (`_FONTES_PADRAO_LEGADO` 3 + `_FONTES_PADRAO_V1` 8 RSS: Agência Brasil, Senado, G1 Últimas/Economia/Saúde/Tecnologia, Poder360, Folha + 4 V2: G1 Mundo→`Internacional`, G1 Pop→`Entretenimento`, GE→`Esporte`, JFP→`Monte Santo de Minas`); `init_db` promove LEGADO/V1 → atual quem nunca customizou (`json == LEGADO ou == V1`); busca global ignora filtro de tema (`listar_noticias(tema=None, limite=500)` — termo livre cai em `Geral`); `temas_config`/`definir_temas` dedupem preservando ordem (`vistos`/`unicos`); botão `Ver puro Noticia` (`agregador-ver-puro`) removido de `telas.py` — `/agregador-noticias-puro` por URL direta (mesmo gate).
- **URL com esquema malformado no seed (25/09/2026) — `Folha de S.Paulo`**: o seed tinha `https:/s.folha.uol.com.br/...` (**uma barra só**), e a coleta morria com `Request URL is missing an 'http://' or 'https://' protocol`. O `try/except Exception` do coletor engolia o erro, então o sintoma era apenas *"aquela fonte nunca traz notícia"* — sem rastro. Duas correções: (a) o seed foi corrigido; (b) o `init_db` ganhou uma **migração idempotente** que lê `agregador_noticias_fontes_json`, aplica `re.sub(r"^(https?:)/(?!/)", r"\1//", url, count=1)` em cada fonte e regrava a config **só se algo mudou** (com `log.warning` por fonte reparada). O regex é ancorado e tem lookahead `(?!/)`, então **URLs válidas não são tocadas** e **fontes customizadas do usuário nunca são sobrescritas** — a migração só repara o que está de fato quebrado.

## Status

| Item | Situação |
|:---|:---|
| Banco WAL `tb_noticia` + `fonte_icon_url` `16×16` + `TEMAS/FONTES_PADRAO` + seeds `tb_config` + deduplicação `_norm_tit` NFKD + `COALESCE(data_publicacao, data_coleta)` + **`hora_reinicio 09:00` + `reiniciar_banco` + sem backup** | Implementado (`init_db()` CREATE TABLE fonte_icon_url + ALTER TABLE ADD COLUMN migração + `inserir_noticia` SELECT url + SELECT titulo _norm_tit + _parse_data_pub + fonte_icon/imagem extração faviconV2/api-attachments + obter_hora_reinicio/definir_hora_reinicio/reiniciar_banco + MAPA_BACKUPS sem agregador_noticias) |
| Coleta scrapy-like `httpx+parsel` Google/BBC/JFP/RSS + pesquisa termo + tempo real `_parse_data_pub` (`time[datetime]`/`pubDate`→`data_publicacao`) | Implementado (`_coletar_google/bbc/jfp/rss/pesquisa` + `coletar_todas` + `_parse_data_pub` RFC822/ISO) |
| Habilitado flag + intervalo **60–9360** clamp (piso 1 h desde 26/09/2026) + termo livre + fontes/temas `json` + **hora `09:00` + reinício diário** | Implementado (`habilitado/definir_habilitado`, `intervalo_min/definir_intervalo`, `termo/definir_termo`, `fontes/temas_config`, `obter_hora_reinicio`/`definir_hora_reinicio` + audit, `reiniciar_banco` + audit) |
| **Sem backup — banco reciclado** `MAPA_BACKUPS` sem `agregador_noticias` + card `Reinício diário` + `Zerar agora` | Implementado (`rotinas.py:19-30` MAPA sem agregador, `telas_administracao.py:235-241` card `restart_alt` com `reiniciar_banco`) |
| **Paginação 12 + busca + grid responsivo 3→2→1 + card de ALTURA FIXA** `pagina` `por_pagina=12` `total_pag` `offset` `COALESCE DESC` + **busca lado a lado `agregador-busca` `debounce 300` NFKD 500 + remoção badge `Coleta:` + marca d'água da fonte `32×32` + miniatura `120×120` ampliável + grid `.grid-noticias` 3→2→1 (`1024px`/`640px`) + `.card-noticia {height: 250px}` (celular `220px`)** + botões `Primeira/Anterior/Próxima/Última` `data-testid=agregador-primeira/anterior/proxima/ultima` + mais atual→mais antiga | Implementado (`telas.py:357-436` estado tema/busca/pagina + `por_pagina=12` + total com busca filtradas 500 NFKD vs `contar_noticias` + 4 botões + `inp_busca` `agregador-busca` `debounce 300` lado a lado `sel_tema` + `grid-noticias` `display:grid 3→2→1` + `card-noticia` `height 250px` + `fonte_icon` como marca d'água `32×32` + `imagem` `120×120` ampliável antes do título) |
| **Redesenho do card (25/09/2026)** card de **altura fixa** (250px/220px, nunca `min/max-height`) + **miniatura `120×120`** (era `30×30`) com **ampliação em diálogo** (`dialogo_card`, 60vw×60vh `contain`, ESC/"Fechar", diálogo memoizado por card e montado só no 1º clique, `data-testid=agregador-ampliar-<id>`, `.stop`/`.enter`/`.space` nativos) + **logo da fonte como marca d'água** `32×32` no rodapé direito da imagem (`opacity .65`, `pointer-events: none`, `drop-shadow`; ícone `16×16` ao lado do badge só quando não há imagem) + **descrição completa com scroll** (`overflow-y: auto` em caixa de altura fixa; antes `desc[:180] + "…"`) + `<style>` do grid **fora** do `@ui.refreshable` | Implementado (`telas.py:109-129` `_desempacotar_noticia` + `131-162` `_criar_dialogo_noticia` + `164-180` `_abrir_dialogo_noticia` + `182-226` `_midia_noticia` + `228-292` `_noticia_card` + `320-354` `add_head_html` CSS) |
| **Seed `Folha de S.Paulo` com URL reparada + migração idempotente (25/09/2026)** `https:/s.folha.uol.com.br/...` → `https://s.folha.uol.com.br/...` (uma barra só fazia a coleta falhar com `Request URL is missing an 'http://' or 'https://' protocol`); `init_db` reescreve **apenas** URL com esquema malformado já persistida em `tb_config`, sem tocar em fontes customizadas, e só chama `set_config` se algo mudou | Implementado (`bd_manipulador.py:48` seed corrigido + bloco de migração no fim de `init_db()` com `re.sub(r"^(https?:)/(?!/)", r"\1//", ...)` + `log.warning` por fonte reparada) |
| Grid responsivo `display:grid` 3→2→1 (`grid-noticias` 1024px/640px) + card de altura fixa com **miniatura `120×120` ampliável + marca d'água `32×32` da fonte + resumo com scroll** + badge tema + título `ui.link(new_tab=True)` + tempo relativo `_tempo_relativo` (`agora`/`X atrás`, `data_publicacao` real + `COALESCE` fallback, **busca NFKD**) **sem botão — título clicável basta + sem card TV + paginação 12 + busca + `.card-noticia {height: 250px}`** (**sem fonte textual**, data `[:16]` substituída, `gap:1rem` + `hover:shadow-lg`, **sem badge `Coleta:`**) | Implementado (`telas.py _tempo_relativo` real + `_noticia_card` `card-noticia` + `_midia_noticia` miniatura 120×120/marca d'água + `_criar_dialogo_noticia`/`_abrir_dialogo_noticia` ampliação + `ui.link` + grid `grid-noticias` 3→2→1 paginado 12 + altura fixa 250px + busca `agregador-busca` debounce 300 lado a lado `sel_tema`, botão removido 19/09/2026, card TV removido 19/09/2026, paginação 12 20/09/2026, grid responsivo 20/09/2026, **redesenho do card 25/09/2026**) |
| Filtro tema + **busca `agregador-busca` `debounce 300` NFKD lado a lado + sem badge `Coleta:`** + `Coletar agora` async | Implementado (`sel_tema` + `inp_busca` `agregador-busca` `debounce 300` NFKD lado a lado, `on_busca` pagina=1 + `grid.refresh` com `pagina=1` + `async _coletar` `run.io_bound` + `spinner` `ocupado` + `forcar=True`, badge `Coleta:` removido a169c9a) |
| Admin: switch habilitado + select intervalo + input termo + **input hora `09:00`** + card fontes + card temas + **censura + reinício diário** (5 cards, sem `painel_backup`) | Implementado (`telas_administracao.py` 241 linhas, `data-testid` QA incluindo `agregador-hora-reinicio` + `agregador-reiniciar-agora`) |
| `listar_para_tv` + TV `mod_filas` carrossel 15s/120s até 200 (ordena `COALESCE` + filtra censuradas) | Implementado (`listar_para_tv(limite=200)` + `titulo_bloqueado` + `mod_filas/telas.py mostrar_tv` `carregar_noticias` + `_mostrar_noticia` `15.0` + `120.0`, fallback elegante nunca vazio) |
| `MODULOS_SISTEMA`/`MODULOS_BD`/`PADROES_TEMA`/`PREFIXO_POR_CHAVE` **+ `MAPA_BACKUPS` sem agregador** | Implementado (`autenticacao.py:25`, `repositorio.py:68`, `tema_modulo.py:82`, `rotinas.py:19-30` sem `agregador_noticias`) |
| Agendadores `agregador_coleta` (`interval minutes`) + **`agregador_reinicio` (`CronTrigger 09:00` + `reiniciar_banco` `DELETE`)** + `reconfigurar_agregador_noticias()` (`pause/resume`+`reschedule`+`CronTrigger`) | Implementado (`rotinas.py:228-285` + `483` `CronTrigger` + `reconfigurar` com `CronTrigger` hora) |
| `main.py` `/agregador-noticias` + `/admin/agregador_noticias` + `bd_criador init_agregador` | Implementado (`main.py:766-777`, `896-906`, `bd_criador.py:67`) |
| Auditoria só **quem alterou o quê** (`configurar` `habilitado`/`intervalo_min`/`termo_pesquisa`/`fontes_json`/`temas_json`/`hora_reinicio`/`reiniciar_banco`) **sem postagens** | Implementado (`bd_manipulador.py:77-204` `definir_*` + `reiniciar_banco` com `_audit`; `coletar_todas`/`limpar_*` sem `_audit`) |
| **15 fontes + migração V1/V2 (20/09/2026)** `_FONTES_PADRAO_LEGADO` 3 + `_FONTES_PADRAO_V1` 8 RSS (Agência Brasil, Senado, G1 ×4, Poder360, Folha) + 4 cobertura (G1 Mundo→`Internacional`, G1 Pop→`Entretenimento`, GE→`Esporte`, JFP→`Monte Santo de Minas`); `init_db` promove LEGADO/V1 → atual quem nunca customizou | Implementado (`bd_manipulador.py:35-59` + migração `init_db` `json == LEGADO ou == V1` → `set_config` atual) |
| **Termo livre via RSS + coleta educada anti-ban (20/09/2026)** `_coletar_pesquisa_google` → `/rss/search` → `_coletar_rss` (HTML `/search` dá 429/captcha); `UA_COLETA` Chrome/126 + `CORTEZIA_SEG=1.5s`+jitter + cooldown 30 min após 429 (`_GOOGLE_HTML_BLOQUEADO_ATE`) + `_url_ja_coletada` pré-checagem | Implementado (`bd_manipulador.py:524-576` cortezia + `_get_html` UA/cooldown + `897-907` pesquisa RSS) |
| **Enriquecimento RSS + `inserir_noticia` preserva thumbnail absoluto (20/09/2026)** `description ::text`+`content:encoded`+limpeza HTML+supressão redundante+`media:thumbnail`+fonte `<source>`+favicon `s2`+`_og_image` fail-soft; `_normalizar_imagem_url` (`//`, `/`, `srcset`); `/api/attachments` relativo/localhost→`""`, absoluto `news.google.com` preservado | Implementado (`bd_manipulador.py:580-594` normaliza + `785-894` RSS/`_og_image` + `481-493` filtro relativo) |
| **Busca global + dedupe temas + botão puro removido (20/09/2026)** busca ignora filtro de tema (`tema=None`, termo livre cai em `Geral`); `temas_config`/`definir_temas` dedupe `vistos`/`unicos`; `agregador-ver-puro` removido de `telas.py` (`/agregador-noticias-puro` por URL direta) | Implementado (`telas.py:157` tooltip global + `195` `tema=None` + `bd_manipulador.py:168-199` dedupe; botão removido) |

---

# Atualização 26/09/2026 — público restrito, tempo relativo e modo escuro

> Lote de mudanças **ainda não documentadas** nesta página. Tudo abaixo foi
> conferido no código (arquivo:linha) em 26/09/2026.

## 1. Público restrito — `_TEMAS_RESTRITOS`

O tema **"Tribunais de Contas"** (criado em 26/09/2026, `bd_manipulador.py:30-32`
em `TEMAS_PADRAO`) tem **duas** regras de exclusão, e elas são **diferentes**:

| Constante | Arquivo:linha | O que faz | Onde age |
|:---|:---|:---|:---|
| `_TEMAS_SEM_TV` | `bd_manipulador.py:720` | Exclui o tema **de vez** do carrossel de notícias da TV do `mod_filas` | `listar_para_tv` (`bd_manipulador.py:731`, filtro `AND tema NOT IN (...)` em `:812` e `:817`) |
| `_TEMAS_RESTRITOS` | `bd_manipulador.py:728` | Esconde o tema da **listagem padrão**, mas **mantém acessível sob demanda** | `contar_noticias` (`:497`), `listar_novas` (`:547`), `listar_noticias` (`:645`) |

!!! warning "As duas regras valem — não confundir"
    `_TEMAS_SEM_TV` é **definitivo** (a TV do `mod_filas` nunca mostra notícia de
    tribunal: a TV é painel de atendimento, não de controle).
    `_TEMAS_RESTRITOS` é **condicional** (some da listagem geral do Agregador, mas
    volta quando o usuário **escolhe o tema** ou **acha por pesquisa**).

### RF-AGR-xx — caminhos de leitura

O tema restrito aparece em **exatamente 2 casos deliberados** do usuário:

| # | Caminho | Evidência |
|:---|:---|:---|
| 1 | **Selecionar o tema na barra de temas** (`tema=` explícito) | `listar_noticias(tema=...)` (`bd_manipulador.py:664-666`) — o filtro de restrito **não se aplica** nesse caminho (`bd_manipulador.py:665`); `contar_noticias(tema=...)` (`:503-504`) |
| 2 | **Achá-lo pela pesquisa** | `telas.py:481-482` — `ag.listar_noticias(tema=None, limite=500, offset=0, excluir_restritos=False)` |

E **nunca** sai por estes caminhos automáticos:

| # | Caminho automático | Evidência |
|:---|:---|:---|
| 1 | **Listagem geral** ("Todos os temas") | `listar_noticias(tema=None)` com `excluir_restritos=True` (default) → `WHERE tema NOT IN (...)` (`bd_manipulador.py:667-670`); `contar_noticias` com `tema=None` (`:505-508`) |
| 2 | **Atualização automática do `ui.timer`** ⚠️ | `listar_novas(apos_id, limite=12, tema=None)` (`bd_manipulador.py:547-580`) — a docstring é explícita: *"com `tema=None`, os temas em `_TEMAS_RESTRITOS` não entram — senão a atualização automática (que roda sem o usuário pedir nada) injetaria notícia de tribunal na tela de quem não pediu"* (`:555-558`). `listar_novas` é o caminho mais fácil de vazar, e está protegido |

`listar_novas` é chamada pelo polling `telas.py:636-637`
(`await run.io_bound(lambda: ag.listar_novas(apos_id=estado["max_id"], limite=12))`),
disparado por `ui.timer(_intervalo_refresh(), _checar_novidades)` (`telas.py:655`).
A atualização é **parcial**: só o card novo é *prependado* (`telas.py:602-617`),
sem redesenhar a grade.

## 2. Tempo relativo — `_tempo_relativo`

`telas.py:78-128` (função aninhada em `mostrar_tela`). As faixas de **semana, mês
e ano foram REMOVIDAS** — no Agregador a notícia vive 24 h, então granularidade
maior só poluiria o rótulo.

| Faixa | Rótulo | Exemplo | Evidência |
|:---|:---|:---|:---|
| `< 15 min` (`seg < 900`) | `agora` | `agora` | `telas.py:113-114` |
| `15 min` – `59 min` (`seg < 3600`) | `N min atrás` | `20 min atrás` | `telas.py:115-117` |
| `1 h` – `24 h` (`seg < 86400`) | `Nh atrás` (minuto exato) | `1h atrás` | `telas.py:121-123` |
| `1 h` – `24 h` (com resto) | `NhMm atrás` | `1h40 atrás` | `telas.py:120-122` |
| `> 24 h` | `1 dia atrás` / `N dias atrás` | `5 dias atrás` | `telas.py:124-126` |

Regras de borda:

- `delta < 0` (data futura, fuso do feed) → `seg = 0` → **`agora`** (`telas.py:110-111`).
- Parse flexível: `T` e `Z` removidos, fração de segundo descartada
  (`telas.py:96-98`), três formatos aceitos `%Y-%m-%d %H:%M:%S` /
  `%Y-%m-%d %H:%M` / `%Y-%m-%d` (`telas.py:99`).
- Falha de parse devolve o bruto truncado (`telas.py:106`, `:127-128`) — fail-soft.
- Fonte do dado: `data_publicacao` real, com fallback para `data_coleta`
  (`telas.py:327` — `_tempo_relativo(data_pub or data_col)`).

## 3. Modo escuro do card de notícia

Bloco CSS `body.intranet-dark .card-noticia` (`telas.py:400-414`), usando
**apenas variáveis do núcleo** — sem cor fixa fora do `var()`:

| Seletor | Variável do núcleo | Fallback | Evidência |
|:---|:---|:---|:---|
| fundo do card | `--fundo-card` | `#1e1e1e` | `telas.py:406` |
| título | `--cor-titulo` | `#ffffff` | `telas.py:407` |
| resumo (+ `a`/`span`) | `--texto-modulo` | `#c9c9c9` | `telas.py:408-410` |
| título em hover | (fixo, destaque) | `#90caf9` | `telas.py:411` |
| scrollbar | — | `#6a6a6a` | `telas.py:412` |
| borda da foto | — | `inset 0 0 0 1px rgba(255,255,255,0.18)` | `telas.py:413` |
| placeholder sem foto | — | `opacity: .5` | `telas.py:414` |

**Contraste medido 9.28:1** no par título/fundo — WCAG AA exige 4.5:1 para texto
normal, então há folga de ~2×. A borda `rgba(255,255,255,0.10)` separa o card do
fundo da página sem usar cor sólida (some no tema claro, onde não se aplica).

## Divergências detectadas nesta atualização

| # | Onde | O que a doc diz | O que o código faz | Ação sugerida |
|:---|:---|:---|:---|:---|
| DIV-AGR-01 | "Tempo relativo … `agora`/minutos/horas/dias/**semanas/meses/anos**" (seção Status, 2ª linha do bloco redesenho) | Faixas de semana/mês/ano existem | Foram **removidas** em 26/09/2026; só `agora`/min/h/dias | **Corrigir a doc** (feita nesta atualização) |
| DIV-AGR-02 | "`.card-noticia {height: 250px}` (celular `220px`)" (seção Status) | `300px` / `260px` | `250px` (`telas.py:392`) e `220px` no mobile (`telas.py:450`) | **Corrigir a doc** |
| DIV-AGR-03 | Seção Status, linha "Habilitado flag + intervalo **60–9360** clamp" | piso de 10 min | `intervalo_min` agora clampa **60–9360** (`bd_manipulador.py:187-206`) — piso de 1 h desde 26/09/2026 | **Corrigir a doc** |
| DIV-AGR-04 | Seção Status, "**15 fontes**" (×3 ocorrências) | 15 fontes | **24 fontes** em `FONTES_PADRAO` (len()==24 em 27/09/2026); 3 legadas + 11 V1 + 15 V2 ficam congeladas só para migração. A própria linha-divergência dizia 19 — também errado | **Corrigir a doc** |
| DIV-AGR-05 | Seção "Regras de negócio" | — | `TEMAS_PADRAO` ganhou `"Tribunais de Contas"` (`:30-32`) e `FONTES_PADRAO` foi **congelado** (`_FONTES_PADRAO_V1`/`_FONTES_PADRAO_V2` mantidos só para migração) | Documentado acima |
| DIV-AGR-06 | Seção Status, "Botão `Atualizar`" | Botão Atualizar na grade | **Removido** em 26/09/2026 — a grade se atualiza sozinha via `ui.timer`; só o admin vê `Coletar agora` (`telas.py:359-380`) | **Corrigir a doc** |

---

# RF e RNF verificados no código (27/09/2026)

> Auditoria de requisitos **funcionais** (o que o módulo faz) e **não
> funcionais** (qualidade e restrições), com evidência `arquivo:linha` conferida
> no código em 27/09/2026. Formato idêntico ao dos módulos auditados antes
> (`intranet`, `gest_cad_usuario`, `auditoria`, `solicita_impressao`,
> `tecnico`, `filas`).

## Requisitos funcionais (RF) — mapa código ↔ doc

| RF | Descrição | Evidência no código |
|:---|:---|:---|
| RF-AGR-01 | Acesso à tela só para `administrador_geral` **ou** usuário com liberação no módulo `agregador_noticias`; negação mostra "Acesso restrito" | `telas.py:56-62` `_pode_ver` (admin geral retorna `True`; senão `autenticacao.validar_acesso_modulo`); negação visual em `telas.py:65-70` |
| RF-AGR-02 | Coleta multi-fonte espelhando `klaytonPrinceMS/Noticia` (Google RSS, BBC, JFP, TCEMG, RSS genérico) | `bd_manipulador.py:1207` `_coletar_google_rss`, `:1256` `_coletar_google`, `:1387` `_coletar_bbc`, `:1421` `_coletar_jfp`, `:1447` `_coletar_tcemg`, `:1548` `_coletar_rss`, `:1641` `_coletar_pesquisa_google`, orquestradas por `coletar_todas` (`:1654`) |
| RF-AGR-03 | Coleta só quando `habilitado`, no `intervalo_min` configurado, com termo livre opcional | `habilitado`/`definir_habilitado` (`:193-202`); `intervalo_min`/`definir_intervalo` (`:204-225`); `termo_pesquisa`/`definir_termo` (`:254-263`); agendamento em `mod_intranet/rotinas.py:261` (`_job_agregador_coleta`) |
| RF-AGR-04 | Fontes e temas **configuráveis** pelo admin, sem seed fixo; dedupe de temas preservando ordem | `fontes_config`/`definir_fontes` (`:265-288`); `temas_config`/`definir_temas` (`:290-322`) com `vistos`/`unicos`; painel em `telas_administracao.py` (`agregador-add-fonte`, `agregador-fonte-nome/url/tema/tipo`, `agregador-temas`) |
| RF-AGR-05 | Padrão atual: **24 fontes** e **10 temas** | `FONTES_PADRAO` len 24 e `TEMAS_PADRAO` len 10 (conferido em 27/09/2026); legadas `_FONTES_PADRAO_LEGADO` (3) / `_V1` (11) / `_V2` (15) preservadas **só** para migração em `init_db` |
| RF-AGR-06 | Banco reciclado diariamente na hora configurada (`DELETE`), com botão "Zerar agora" | `obter_hora_reinicio`/`definir_hora_reinicio` (`:324-350`, padrão **`09:00`**, valida `HH:MM`); `reiniciar_banco` (`:353-371`); `rotinas.py:494` `_job_agregador_reinicio` com `CronTrigger`; painel `agregador-reiniciar-agora` |
| RF-AGR-07 | Deduplicação por **URL** e por **título normalizado** (`NFKD` + lower) antes de gravar | `inserir_noticia` (`:935`) consulta `SELECT url` e `titulo_norm`; `_normalizar_titulo` (`:880`); índice `idx_noticia_titulo_norm` |
| RF-AGR-08 | Tempo real de publicação (`pubDate`/`dc:date`/`time[datetime]`), com fallback para a data de coleta, ordenando do mais novo ao mais antigo | `_parse_data_pub` (`:613-658`, via `email.utils.parsedate_to_datetime` + fallback ISO/RSS); `listar_noticias` (`:660`) com `ORDER BY COALESCE(data_publicacao, data_coleta) DESC`; índice `idx_noticia_data` |
| RF-AGR-09 | Filtro por tema **e** busca por palavra lado a lado; a busca é **global** e ignora o filtro de tema | `telas.py:372` `agregador-busca` (`debounce 300`); `telas.py:119-148` `sel_tema` `agregador-filtro-tema`; `listar_noticias(tema=None, limite=500)` para a busca |
| RF-AGR-10 | Paginação de 12 com `Primeira/Anterior/Próxima/Última` | `telas.py:525-543` (`por_pagina = 12`, `total_pag`, `offset`); `data-testid` `agregador-primeira`/`-anterior`/`-proxima`/`-ultima` |
| RF-AGR-11 | Card de altura fixa com miniatura ampliada em diálogo, marca d'água da fonte, badge de tema, título que abre o original em nova aba e descrição completa com scroll | `telas.py:246-262` miniatura `card-noticia__midia`/`__foto`/`__marca`; `dialogo_card`; `ui.link(..., new_tab=True)`; `.card-noticia__resumo` com `overflow-y: auto` |
| RF-AGR-12 | "Coletar agora" só para administrador, com spinner, trava de reentrância e I/O fora do event-loop | `telas.py:359-395` (`eh_admin_do_modulo`, `async`, `run.io_bound(lambda: ag.coletar_todas(...))`, `notificar`, `ocupado`) |
| RF-AGR-13 | "Limpar antigas (24 h)" e "Limpar censuradas" no painel | `limpar_antigas(horas=24)` (`:890`); `limpar_censuradas` (`:850`); `data-testid` `agregador-limpar-censuradas`; orquestração cruzada via `mod_intranet/integracoes.limpar_noticias_censuradas()` (não importa o outro módulo — AGENTS.md §2) |
| RF-AGR-14 | Alimenta a **TV das filas** com notícias censuradas e corte por horas | `listar_para_tv(limite=10, por_tema, horas)` (`:735-849`) + `_corte_horas` (`:695`) + `_filtrar_censura_tv` (`:708`); consumido por `mod_filas/telas.py` |
| RF-AGR-15 | Auditoria registra **quem alterou o quê** na configuração — não as postagens coletadas | `_audit` (`:167`); auditam `definir_habilitado/intervalo/refresh_seg/termo/fontes/temas/hora_reinicio` e `reiniciar_banco`; `coletar_todas`/`limpar_antigas`/`limpar_censuradas` **sem** `_audit` |
| RF-AGR-16 | `Coletar agora` é admin-only na tela; o botão `Atualizar` da grade foi removido (a grade se atualiza sozinha) | `telas.py:359-380`; ver `DIV-AGR-06` na tabela de divergências |

## Requisitos não-funcionais (RNF) — garantias técnicas

| RNF | Exigência | Evidência no código |
|:---|:---|:---|
| RNF-AGR-PERS-01 | Banco próprio `db_mod_agregador_noticias.db`, um por módulo | `get_connection` (`:137`) → `banco_conexao.conexao("agregador_noticias")`; sem *cross-query* entre bancos |
| RNF-AGR-PERS-02 | `PRAGMA journal_mode=WAL` e DDL idempotente | `init_db` (`:373-511`) com `CREATE TABLE IF NOT EXISTS` + `ALTER TABLE ... ADD COLUMN`migration idempotente |
| RNF-AGR-PERS-03 | Reinício é `DELETE`, não recria o banco — e por isso **sem backup** no `MAPA_BACKUPS` | `reiniciar_banco` (`:353`); `telas_administracao.py` sem `painel_backup`, card "Reinício diário" no lugar |
| RNF-AGR-SEG-01 | Coleta **educada**: `User-Agent` de navegador, 1,5 s entre requisições + jitter, cooldown de 30 min após HTTP 429 do Google | `bd_manipulador.py:1140-1142` `UA_COLETA`/`CORTEZIA_SEG = 1.5`/`COOLDOWN_429_SEG = 1800`; `_aguardar_cortezia` (`:1147`); `/rss/search` em vez de `/search`, que dá 429/captcha |
| RNF-AGR-SEG-02 | Sem *retry* agressivo e sem seguir redirecionamento externo | `_get_html` (`:1172`) com `follow_redirects=False`; comentário em `:1134-1139` registra o porquê |
| RNF-AGR-SEG-03 | Pré-checagem de URL antes de baixar, para não gastar cota com repetida | `_url_ja_coletada` (`:1158`) |
| RNF-AGR-SEG-04 | URLs de fonte com esquema malformado são reparadas por migração idempotente, sem tocar nas fontes customizadas | `init_db` reescreve `tb_config` quando o esquema está quebrado; seed `Folha de S.Paulo` (`https:/…` → `https://…`) |
| RNF-AGR-SEG-05 | **Censura** por palavra bloqueada antes de exibir, com normalização sem acento e comparação por substring | `_filtrar_censura_tv` (`:708`) chama `titulo_bloqueado`/`conteudo_palavras_bloqueadas` de `mod_intranet/censura.py` |
| RNF-AGR-RES-01 | `try/except` obrigatório em função, com `notificar` + log (AGENTS.md §3.2) | Todo `bd_manipulador` protegido; falhas de UI passam por `tema_modulo.notificar` (`telas.py:205`, `:226`, `:362`, `:393`) — **zero** `ui.notify` cru |
| RNF-AGR-RES-02 | Falha de coleta **não** derruba a tela: devolve contagem e segue | `coletar_todas` (`:1654`) e `_get_html` (`:1172`) com retorno `""`/0 no erro |
| RNF-AGR-UX-01 | Anti-disconnect: I/O pesado em `async` + `run.io_bound` + spinner + trava (§5.1) | `telas.py:382-393` (`Coletar agora`); `telas.py:645` (`marca_ultimo_coletado` em `run.io_bound`) |
| RNF-AGR-UX-02 | `data-testid` via `.props('data-testid=...')` em todas as ações | `telas.py`: `agregador-busca`, `agregador-filtro-tema`, `agregador-coletar`, `agregador-primeira`, `agregador-anterior`, `agregador-proxima`, `agregador-ultima`; painel: 13 `data-testid` (`agregador-habilitado`, `-intervalo`, `-termo`, `-hora-reinicio`, `-temas`, `-add-fonte`, `-fonte-*`, `-coletar-agora`, `-reiniciar-agora`, `-limpar-censuradas`, `-palavras-bloqueadas`, `-refresh-seg`) |
| RNF-AGR-UX-03 | Rótulos PT-BR e docstrings bilíngue EN (topo) / PT-BR (abaixo) | `bd_manipulador.py:1-30`, `telas.py:1-40`, `telas_administracao.py:1-18` |
| RNF-AGR-PERF-01 | Busca global em memória (500 itens) em vez de `LIKE` no banco, para não varrer a tabela | `telas.py:525-543` carrega o recorte e filtra em Python; índice `idx_noticia_tema` cobre o filtro de tema |
| RNF-AGR-PERF-02 | `<style>` do grid injetado **uma vez** por página, fora do `@ui.refreshable` | `telas.py:405-469` (`ui.add_head_html` fora do refreshable — antes era duplicado a cada busca/paginação) |
| RNF-AGR-PERF-03 | Sem N+1 na listagem: contagem e recorte em 2 consultas | `contar_noticias` (`:512`) + `listar_noticias` (`:660`) |
| RNF-AGR-RESP-01 | Grid 3 → 2 → 1 colunas e card de altura fixa, com contraste invertido no tema escuro | `telas.py:409` `repeat(3, 1fr)`, `:468` `max-width:1024px` → 2 col., `:469` `max-width:640px` → 1 col. e `height:220px`; bloco `body.intranet-dark .card-noticia*` (`:425-433`) |
| RNF-AGR-CFG-01 | Configuração com fonte única de verdade (central) e fallback local | `_get_config`/`_set_config` (`:175-191`) delegam a `banco_conexao`, com `default` no chamador |
| RNF-AGR-COMP-01 | Compatibilidade SQLite ↔ PostgreSQL | `banco_conexao.conexao(chave)` roteia; DDL só `IF NOT EXISTS`; sem SQL SQLite-only no módulo |
| RNF-AGR-DISC-01 | O módulo não é backup nem fonte de verdade de nada: o dado é descartável por definição | `MAPA_BACKUPS` sem `agregador_noticias`; `reiniciar_banco` pode zerar tudo sem perda auditável |
