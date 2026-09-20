# News Aggregator Module — `mod_agregador_noticias`

> News aggregator module: route `/agregador-noticias` (key `agregador_noticias`) · own database `db_mod_agregador_noticias.db` (WAL) · table `tb_noticia` (title/source/theme/url/image/description/dates) · **no backup** (`MAPA_BACKUPS` without `agregador_noticias`, daily recycle `reiniciar_banco` DELETE at configurable `hora_reinicio` default `06:00` via `CronTrigger` + `reconfigurar_agregador_noticias`) · scrapy-like collection `httpx+parsel` mirroring `klaytonPrinceMS/Noticia` (`Sites` + `Noticias.get_noticiasGN/BBC/JFP/RSS`) · interval 10–360 min + `habilitado` flag + free term + configurable sources · deduplication by URL (`SELECT url`) + normalized title (`_norm_tit` NFKD lower, `join`) before `INSERT OR IGNORE` · real post time via `_parse_data_pub` (`email.utils.parsedate_to_datetime` + ISO/RSS fallback, `time[datetime]`/`pubDate`) ordered by `COALESCE(data_publicacao, data_coleta) DESC` · **pagination 10** (`pagina` state, `por_pagina=10`, `total_pag`, `offset`, `ORDER BY COALESCE(...) DESC`, buttons `Primeira/Anterior/Próxima/Última` with `data-testid=agregador-primeira/anterior/proxima/ultima`, newest → oldest) · 3-column masonry **(thumbnail `30x30` `ui.image` before title when present `30px object-cover` `fit=cover` + badge theme + title as `ui.link(target=href, new_tab=True)` + description + relative time `_tempo_relativo` using real `data_publicacao` or `data_coleta` fallback, no button — title click suffices, no source on card, no TV card on this screen, absolute date replaced by `agora`/`X minutes/hours/days/weeks/months/years ago`)** · TV integration via `listar_para_tv` carousel · audit only **who changed what** (`definir_habilitado/intervalo/termo/fontes/temas/hora_reinicio/reiniciar_banco`, no audit for localized posts).

---

# Módulo Agregador de Notícias — `mod_agregador_noticias`

> Módulo agregador de notícias: rota `/agregador-noticias` (chave `agregador_noticias`) · banco próprio `db_mod_agregador_noticias.db` (WAL) · tabela `tb_noticia` (título/fonte/tema/url/imagem/descrição/datas) · **sem backup** (`MAPA_BACKUPS` sem `agregador_noticias`, banco reciclado diariamente via `reiniciar_banco` `DELETE` às `06:00` configurável `hora_reinicio` com `CronTrigger` + `reconfigurar_agregador_noticias`) · coleta scrapy-like `httpx+parsel` espelhando `klaytonPrinceMS/Noticia` (`Sites` gn_brasil/gn_saude + `Noticias.get_noticiasGN/BBC/JFP/RSS`) · intervalo 10–360 min + flag `habilitado` + termo livre + fontes configuráveis · deduplicação por URL (`SELECT url`) + título normalizado (`_norm_tit` NFKD lower, `join`) antes de `INSERT OR IGNORE` · tempo real da postagem via `_parse_data_pub` (`email.utils.parsedate_to_datetime` + fallback ISO/RSS, `time[datetime]`/`pubDate`) ordenado por `COALESCE(data_publicacao, data_coleta) DESC` · **paginação 10** (`pagina` `por_pagina=10` `total_pag` `offset`, mais atual → mais antiga, botões `Primeira/Anterior/Próxima/Última` `data-testid=agregador-primeira/anterior/proxima/ultima`) · 3 colunas masonry **(miniatura `30x30` `ui.image` antes do título quando há imagem `30px object-cover` `fit=cover`, `try` fail-soft + badge tema + título como `ui.link(target=href, new_tab=True)` + descrição + tempo relativo `_tempo_relativo` usando `data_publicacao` real ou `data_coleta` fallback, sem botão — título clicável basta, sem fonte no card, sem card TV nesta tela, data absoluta substituída por `agora`/`X minutos/horas/dias/semanas/meses/anos atrás`)** · integração TV via `listar_para_tv` carrossel · auditoria apenas **quem alterou o quê** (`definir_habilitado/intervalo/termo/fontes/temas/hora_reinicio/reiniciar_banco`, sem auditar postagens localizadas).

## Propósito

Agregador **multi-fonte** de notícias para a rede interna. O administrador especifica o **conteúdo da pesquisa** (termo livre, ex.: `Brasil`, `Monte Santo`, `economia`) e **prevê não apenas Google News, mas outras fontes** (`BBC`, `JFP`, `RSS` genérico), todas configuráveis sem restart. O sistema investiga periodicamente as fontes via **scrapy-like** (`httpx` + `parsel`, espelho de `https://github.com/klaytonPrinceMS/Noticia` — classe `Sites` com `gn_brasil`, `gn_saude` etc + `Noticias` com `get_noticiasGN/BBC/JFP/RSS`), armazena até o **reinício diário às horas da manhã** (padrão `06:00`, configurável, `reiniciar_banco` `DELETE FROM tb_noticia` via `CronTrigger` — banco reciclado, **sem backup**) e exibe em **3 colunas masonry paginadas 10 por página** com card **sem fonte e sem botão** — apenas **miniatura `30x30` `ui.image` antes do título quando há imagem (`30px object-cover` `fit=cover`, `try` fail-soft) + badge tema + título como `ui.link(target=href, new_tab=True)` + descrição (180c, `…`) + tempo relativo** (`_tempo_relativo` → `agora` / `X minuto(s) atrás` / `X hora(s) atrás` / `X dia(s) atrás` / `X semana(s) atrás` / `X mês(es) atrás` / `X ano(s) atrás`), **paginação `10` com `Primeira/Anterior/Próxima/Última` (`data-testid=agregador-primeira/anterior/proxima/ultima`) ordenada `COALESCE(data_publicacao, data_coleta) DESC` (mais atual → mais antiga)**. **Título clicável basta** — **botão "Abrir notícia" removido em 19/09/2026**. **Deduplicação** impede notícia já incluída com mesmo título (case-insensitive, sem acentos via `_norm_tit` NFKD) ou mesma URL (`SELECT url` + `SELECT titulo` antes de `INSERT OR IGNORE`). **Timer com tempo real**: `data_publicacao` extraída da postagem (`time[datetime]`, `pubDate`) via `_parse_data_pub` (`email.utils.parsedate_to_datetime` + fallback ISO/RSS) e ordenação por `COALESCE(data_publicacao, data_coleta) DESC`; `_tempo_relativo` usa `data_pub` real ou `data_coleta` fallback. Enquanto aguardam na TV do módulo **Filas** (`/tv`), os usuários veem **carrossel título+descrição** das últimas notícias (`listar_para_tv`). **Auditoria** registra apenas **quem alterou o quê no módulo** (`definir_habilitado/intervalo/termo/fontes/temas/hora_reinicio/reiniciar_banco`), **sem auditar postagens localizadas** (removido `_audit` de `coletar_todas`, `limpar_antigas`, `limpar_censuradas`).

> Status: **ativo** (coleta habilitável por flag; intervalo 10 min–6 h; reinício diário `06:00` configurável; paginação 10; sem backup; sem impacto no core).

## Banco de dados

Criador vigente: `init_db()` em `bd_manipulador.py:209-250` (bootstrap central `mod_intranet/bd_criador.py:67-68` `init_agregador` + chamada no import `bd_manipulador.py:705` `init_db()`).

Conexão via `mod_intranet/banco_conexao.conexao("agregador_noticias")` (backend duplo SQLite/PostgreSQL, `PRAGMA journal_mode=WAL` + `foreign_keys=ON`). Índices `idx_noticia_tema`, `idx_noticia_fonte`, `idx_noticia_data`.

| Tabela | Conteúdo |
|:---|:---|
| `tb_noticia` | `id` PK, `titulo` TEXT (`500`), `fonte` TEXT (`100`), `tema` TEXT (`50`, default `Geral`), `url` TEXT UNIQUE (`2000`, normalizada `https://news.google.com` se `/`), `imagem_url` TEXT (`2000`, `img::attr(src)` + `data-src`/`media:content`), `descricao` TEXT (`1000`), `data_publicacao` DATETIME (`COALESCE(?, datetime('now'))` — preenchido via `_parse_data_pub` com tempo real da postagem ou `now` fallback), `data_coleta` DATETIME `DEFAULT CURRENT_TIMESTAMP` |

Seeds de `tb_config` central (idempotentes, `bd_manipulador.py:229-248` — `SELECT valor` → `INSERT` só se ausente):

| Chave | Default | Descrição |
|:---|:---|:---|
| `agregador_noticias_habilitado` | `0` | coleta desabilitada por padrão |
| `agregador_noticias_intervalo_min` | `60` | 1 h (clamp 10–360) |
| `agregador_noticias_termo_pesquisa` | `""` | termo livre (vazio = sem pesquisa `search?q=`) |
| `agregador_noticias_temas_json` | `TEMAS_PADRAO` `["Brasil","Internacional","Economia","Saúde","Ciência e Tecnologia","Entretenimento","Esporte","Monte Santo de Minas","Geral"]` | temas para filtro |
| `agregador_noticias_fontes_json` | `FONTES_PADRAO` (3, `bd_manipulador.py:27-31`) | Google Brasil/Saúde (`google`, `tema Brasil/Saúde`) + BBC Brasil (`bbc`) — espelho `Sites` `gn_brasil`/`gn_saude` |
| `agregador_noticias_hora_reinicio` | `06:00` | hora do reinício diário (zerar todas, `HH:MM`, validado `re.match` `00–23:00–59`) |

Constantes (`bd_manipulador.py:24-31`):

```python
TEMAS_PADRAO = ["Brasil","Internacional","Economia","Saúde","Ciência e Tecnologia",
                "Entretenimento","Esporte","Monte Santo de Minas","Geral"]
FONTES_PADRAO = [
  {"tipo":"google","nome":"Google News - Brasil",
   "url":"https://news.google.com/topics/CAAqJQgKIh9DQkFTRVFvSUwyMHZNREUxWm5JU0JYQjBMVUpTS0FBUAE?hl=pt-BR&gl=BR&ceid=BR%3Apt-419","tema":"Brasil"},
  {"tipo":"bbc","nome":"BBC - Brasil",
   "url":"https://www.bbc.com/portuguese/topics/cz74k717pw5t","tema":"Brasil"},
  {"tipo":"google","nome":"Google News - Saúde",
   "url":"https://news.google.com/topics/CAAqJQgKIh9DQkFTRVFvSUwyMHZNR3QwTlRFU0JYQjBMVUpTS0FBUAE?hl=pt-BR&gl=BR&ceid=BR%3Apt-419","tema":"Saúde"},
]
```

⚠️ `bd_criador.py` é **legado/morto** — não executar (schema real em `bd_manipulador.py`).

Modelos tipados: ainda sem `models/__init__.py` com `map_imperatively` — acesso via `banco_conexao.conexao` direto (padrão a propagar).

## Funcionalidades

### Tela `/agregador-noticias` — 3 colunas masonry + paginação 10

- **Gate** (`_pode_ver` — `telas.py:19-25`): `administrador_geral` sempre; senão `validar_acesso_modulo(user, "agregador_noticias")` — sem acesso → "Acesso restrito".
- **Cabeçalho temático** (`telas.py:36-42`): `ler_tema("agregador_noticias", cor_botao="#000000", texto_header="Notícias agregadas de múltiplas fontes — 3 colunas, clique abre no site original. Para TV do Filas, carrossel título+descrição.")` + `ui.colors(primary=tema["cor_botao"])` + `cabecalho("Agregador de Notícias", ..., chave_modulo="agregador_noticias")` (borda = `cor_botao` via `PADROES_TEMA["agregador_noticias"]` → `#000000`).
- **Barra de filtro** (`telas.py:119-148`): `ui.select` `Filtrar por tema` (`data-testid=agregador-filtro-tema`, `{"": "Todos os temas"} | {t:t}`, `estado["tema"]`) + badge `"Coleta: ativa/desabilitada • intervalo X min • N notícias (24h)"` (`contar_noticias()`, `habilitado()`, `intervalo_min()`) + `botao "Atualizar"` (`refresh`, `texto`, `data-testid=agregador-atualizar`, `grid.refresh()`) + `botao "Coletar agora"` (`sync`, `primario`, `data-testid=agregador-coletar`, só `administrador_geral` ou `eh_admin_do_modulo`) → `async _coletar` com `run.io_bound(lambda: ag.coletar_todas(ator=user_nome, forcar=True))`, **spinner `aria-label=Coletando notícias` + trava `ocupado` + `notificar`** + `grid.refresh()` (anti-disconnect, sem bloquear event-loop).
- **Grid masonry 3 colunas + paginação 10** (`@ui.refreshable grid()` — `telas.py:149-195`, `por_pagina=10`, `ORDER BY COALESCE(data_publicacao, data_coleta) DESC`, `total_pag = max(1, (total+por_pagina-1)//por_pagina)`, `offset = (pagina-1)*por_pagina`): `column-count: 3; column-gap: 1rem;` + por notícia `break-inside: avoid; margin-bottom: 1rem;` + `_noticia_card(n)` (`telas.py:91-113` + helper `_tempo_relativo` `telas.py:47-89`): `ui.card` `w-full overflow-hidden hover:shadow-lg cursor-pointer` + **miniatura `30x30` `ui.image(img).classes("shrink-0 rounded").style("width:30px;height:30px;object-fit:cover;").props("fit=cover")` antes do título quando `imagem_url` presente** (`try` fail-soft, mantém miniatura) + `card_section` com `ui.badge(tema)` (`outline dense`), `ui.link(titulo, target=href, new_tab=True)` (`font-bold`, `word-break`, `new_tab=True` abre externo) , `descricao[:180] + …` (`text-caption text-grey-7`), **`row` apenas tempo relativo `ui.label(_tempo_relativo(data_pub or data_col)).classes("text-caption text-grey-5")` — fonte removida, data absoluta `[:16]` substituída**; `_tempo_relativo` converte `YYYY-MM-DD HH:MM:SS`/`YYYY-MM-DD HH:MM`/`YYYY-MM-DD` (normaliza `T`/`Z`/fração, `delta<0→0`) em `agora` (<60 s) / `X minuto(s) atrás` (<60 min) / `X hora(s) atrás` (<24 h) / `X dia(s) atrás` (<7 d) / `X semana(s) atrás` (<30 d) / `X mês(es) atrás` (<365 d) / `X ano(s) atrás` + fallback `[:16]`; **usa `data_publicacao` real da postagem (extraída via `_parse_data_pub` de `time[datetime]`/`pubDate`) com fallback `data_coleta`, ordenação `COALESCE(data_publicacao, data_coleta) DESC` garante "3 minutos atrás, 25 minutos atrás, 2 semanas..." com tempo real, paginação `10` garante mais atual → mais antiga**; **sem botão "Abrir notícia" — removido em 19/09/2026 (antes `flat dense` + `window.open` fallback, agora título `ui.link` clicável basta; helper `_abrir` `window.open` permanece mas sem gatilho — clique no título abre)**. **Paginação**: `estado["pagina"]=1` inicial, `@ui.refreshable grid()` computa `total=contar_noticias(tema_f)`, `total_pag`, ajusta `pagina` clamp `1..total_pag`, `offset`, `listar_noticias(tema_f, limite=por_pagina, offset=offset)` com `COALESCE` `DESC`; sem notícia → card `"Nenhuma notícia ainda. Ative a coleta nas Configurações."` + tema. Rodapé paginação `row w-full items-center justify-between mt-3 flex-wrap gap-2` com `ui.button icon=first_page` `data-testid=agregador-primeira` → `pagina=1`, `chevron_left` `agregador-anterior` → `max(1,pagina-1)`, `label Página X de Y • N notícias` + `chevron_right` `agregador-proxima` → `min(total_pag,pagina+1)`, `last_page` `agregador-ultima` → `total_pag`, + `label Exibindo len(noticias) de total`. **Card "Integração TV — Filas" removido (antes `telas.py:184-187` `card bg-blue-50 border-blue-200` com "Integração TV — FilasEnquanto aguardam..." — grid agora termina sem esse card; integração TV permanece via `/tv` + `listar_para_tv`)**.
- **Helpers**: `_tempo_relativo(data_str)` normaliza ISO flexível + delta relativo usando `data_publicacao` real ou `data_coleta` fallback; `_noticia_card` normaliza `href` (`#` fallback), sanitiza `titulo[:500]`/`url[:2000]` (`inserir_noticia` com deduplicação `_norm_tit` + `SELECT url`), `data-testid` para QA, `notificar` com `timeout` configurável, `ui.colors` do módulo, **fonte armazenada em `tb_noticia.fonte` mas não renderizada no card; imagem `30x30` antes do título; sem botão — apenas `ui.image 30x30` miniatura + `ui.link(target=href, new_tab=True)` título clicável basta; paginação 10 com 4 botões; sem card TV**.

#### Coleta scrapy-like (espelho `klaytonPrinceMS/Noticia`)

| Função | Fonte | Seletores | Limite | Tempo real |
|:---|:---|:---|:---:|:---|
| `_coletar_google(url, fonte_nome, tema)` (`bd_manipulador.py:457-521`) | Google News (`Sites.gn_*`) | `.gPFEn, .JtKRv, .a7P8L, article` → `a::text` + `a::attr(href)` + `img::attr(src/data-src)`; `href ./`→ `https://news.google.com/` | 20 | `time::attr(datetime)` / `time::text` / `[datetime]` → `_parse_data_pub` + `_parse_relativo_para_absoluto` → `inserir_noticia(..., data_pub)` |
| `_coletar_bbc(url, tema)` (`bd_manipulador.py:554-585`) | BBC (`get_noticiasBBC`) | `.bbc-uk8dsi, .bbc-19j92fr, article, a[href*='/portuguese/articles']` → `a::text` + `href` (`/`→ `https://www.bbc.com`) + `img::attr(src)` | 15 | `time::attr(datetime)` / `time::text` → `_parse_data_pub` |
| `_coletar_jfp(url, tema)` (`bd_manipulador.py:588-611`) | JFP Notícias (`get_noticiasJFP`) | `.td-module-title` → `a::text` + `::attr(href)` + `img::attr(src)` | 15 | `time::attr(datetime)` / `.td-post-date::text` → `_parse_data_pub` |
| `_coletar_rss(url, fonte_nome, tema)` (`bd_manipulador.py:614-646`) | RSS genérico (`get_noticiasRSS`) | `parsel.Selector(xml, type="xml")` `item` → `title::text` + `link::text/attr(href)` + `description::text` + `media:content::attr(url)` + `pubDate::text`/`dc:date`/`published` | 15 | `pubDate`/`dc:date`/`published` → `_parse_data_pub` |
| `_coletar_pesquisa_google(termo)` (`bd_manipulador.py:649-658`) | Pesquisa termo livre (`Noticia` termo) | `https://news.google.com/search?q={quote(termo)}&hl=pt-BR&gl=BR&ceid=BR%3Apt-419` → `_coletar_google(..., "Pesquisa:termo")` | 20 | via `_coletar_google` |

**Helper tempo real** (`_parse_data_pub(raw)` — `bd_manipulador.py:267-311`): reescrito via `email.utils.parsedate_to_datetime` (robusto para `Tue, 19 Sep 2026 12:34:56 GMT` RFC822) + `astimezone().replace(tzinfo=None)` + fallback ISO/RSS (`%Y-%m-%dT%H:%M:%S%z`, `%Y-%m-%dT%H:%M:%S.%f%z`, `%Y-%m-%dT%H:%M:%S`, `%Y-%m-%d %H:%M:%S`, `%a, %d %b %Y %H:%M:%S %z/%Z`, `%d/%m/%Y %H:%M`, normaliza `Z`→`+00:00`, `+00:00`→`+0000`, regex `YYYY-MM-DD[ T]HH:MM:SS`) → `YYYY-MM-DD HH:MM:SS` ou `None`; usado em todos os coletores acima para extrair `data_real` da postagem e passar para `inserir_noticia`. **Relativo** (`_parse_relativo_para_absoluto(texto)` — `bd_manipulador.py:523-551`): converte `"3 horas atrás"`, `"Ontem"` etc para `now - delta` → `YYYY-MM-DD HH:MM:SS`.

**Orquestração** (`coletar_todas(ator, forcar=False)` — `bd_manipulador.py:661-698`): `if not forcar and not habilitado(): 0` + `fontes_config()` (`FONTES_PADRAO` ou `fontes_json`) + `termo_pesquisa()` → loop por fonte (`tipo` → dispatch acima; `google/bbc/jfp/rss`/default) + `termo → _coletar_pesquisa_google(termo, "Geral")` → `limpar_antigas(24)` (retenção 24h, **sem auditoria de postagens**) → `log info` `Coleta agregador: N novas de M fontes (termo=...)` (**sem `_audit`**). `httpx.get(url, timeout=12, follow_redirects=True, headers={"User-Agent":"Mozilla/5.0 (IntrAnEt; AgregadorNoticias)"})` (`_get_html` `:447-455`, `warning` em falha).

**Helpers de config** (`bd_manipulador.py:77-204`): `habilitado()` (`agregador_noticias_habilitado=="1"`), `definir_habilitado(bool, ator)` + `audit configurar habilitado`, `intervalo_min()` (`int(get_config("intervalo_min",60))` `clamp 10–360`), `definir_intervalo(min, ator)` (`clamp + audit + return ok,v`), `termo_pesquisa()`/`definir_termo(termo, ator)` + audit, `fontes_config()` (`json.loads(fontes_json)` → `FONTES_PADRAO` em falha), `definir_fontes(list, ator)` (`json.dumps` + `audit`), `temas_config()`/`definir_temas(list, ator)` (`json.dumps` + `audit`), **`obter_hora_reinicio()`/`definir_hora_reinicio(hora_str, ator)` (`HH:MM` validado `re.match` `00–23:00–59`, `definir` normaliza `f"{h:02d}:{mi:02d}"` + audit)**, **`reiniciar_banco(ator)` (`DELETE FROM tb_noticia` + `COUNT` antes + `commit` + `log info` + `audit reiniciar_banco N notícias + hora`)**, `intervalo_criar_job()` `return habilitado(), intervalo_min()` para `rotinas`.

**CRUD** (`bd_manipulador.py:254-397`): `contar_noticias(tema?)` (`COUNT`), `listar_noticias(tema, limite=30, offset=0)` (`SELECT ... ORDER BY COALESCE(data_publicacao, data_coleta) DESC, data_coleta DESC LIMIT ? OFFSET ?`), `listar_para_tv(limite=10)` (`SELECT titulo,descricao,url,imagem_url,fonte,tema ORDER BY COALESCE(data_publicacao, data_coleta) DESC, data_coleta DESC LIMIT ?*3` filtrando censuradas via `titulo_bloqueado` → `[{"titulo","descricao": desc or titulo,"url","imagem","fonte","tema"}]`), `limpar_antigas(horas=24)` (`DELETE WHERE data_coleta < datetime('now', '-N hours')` + `log info` **sem audit**), `limpar_censuradas()` (`SELECT id,titulo` → `titulo_bloqueado` → `DELETE WHERE id=?` + `log info` **sem audit**), `_parse_data_pub(raw)` (RFC822 + ISO/RSS → `YYYY-MM-DD HH:MM:SS`), `inserir_noticia(titulo,fonte,tema,url,imagem,descricao,data_pub)` (`titulo[:500]`, `url[:2000]`, `url "/"→"https://news.google.com"+url`, `fonte[:100]`, `tema[:50] or Geral`, `imagem[:2000]`, `desc[:1000]`, **deduplicação: `SELECT 1 WHERE url=?` + loop `SELECT titulo` com `_norm_tit` NFKD lower `join` — evita notícia já incluída com mesmo título case-insensitive sem acentos ou mesma URL antes de `INSERT OR IGNORE` + `COALESCE(data_pub, datetime('now'))`**; censura `titulo_bloqueado` descarta).

### Censura de conteúdo — palavras bloqueadas (central `mod_intranet/censura.py`)

Funcionalidade **compartilhada Blog ↔ Agregador** (mesma chave `conteudo_palavras_bloqueadas` em `tb_config` central):

| Camada | Comportamento |
|:---|:---|
| **Núcleo `censura.py`** | `CHAVE_CONFIG="conteudo_palavras_bloqueadas"` · `obter_palavras_bloqueadas()` (split `,;\n` + JSON fallback, `lower`) · `definir_palavras_bloqueadas(lista, ator)` (normaliza `lower`, dedup, grava CSV via `set_config`, `audit_log` `censura/palavras_bloqueadas`) · `titulo_bloqueado(titulo, palavras=None)` / `filtrar_titulo(titulo)` → `(bloqueado, palavra)` com `_normalizar` `lower+NFD` sem acentos (ex.: `suicidio` bloqueia `suicídio`, substring insensível) |
| **Blog** | `criar_postagem`/`atualizar_postagem` (`bd_manipulador.py:649-703`) verificam `titulo_bloqueado` **antes** de `nh3`; se bloqueado retornam `None`/`False` com `warning` + `notificar` |
| **Agregador `inserir_noticia`** | descarta se título bloqueado (`bd_manipulador.py:399-410` `titulo_bloqueado` → `return False` + log `notícia censurada`) |
| **Agregador `listar_para_tv`** | filtra censuradas: busca `LIMIT limite*3`, itera `titulo_bloqueado(r[0])` e só retorna `limite` não bloqueadas (`bd_manipulador.py:330-352`) |
| **Agregador `limpar_censuradas()`** | remove já coletadas com palavra bloqueada: `SELECT id,titulo` → `titulo_bloqueado(tit, palavras)` → `DELETE WHERE id=?` + `log info` **sem audit** (`bd_manipulador.py:354-381`) |
| **Admin Blog** | card `Censura de conteúdo — palavras bloqueadas` (`block`, `data-testid=blog-palavras-bloqueadas`, `textarea` CSV/;/linha, `Salvar censura` `data-testid=blog-salvar-censura`) + ao salvar chama `limpar_censuradas()` |
| **Admin Agregador** | mesmo card (`data-testid=agregador-palavras-bloqueadas`, `textarea`, `Salvar censura` `data-testid=agregador-salvar-censura`) + botão **"Remover já censuradas agora"** (`data-testid=agregador-limpar-censuradas`, `bd_manipulador.limpar_censuradas()` + `notificar`) |
| **Normalização** | `lower` + `NFD` sem acentos (`unicodedata.normalize` remove `Mn`) → `suicidio` bloqueia `suicídio`; substring (não exige fronteira de palavra) |
| **Lista compartilhada** | única chave `conteudo_palavras_bloqueadas` vale para **Blog e Agregador (TV)**; separadores aceitos: `,` `;` e quebra de linha |

### Administração (`/admin/agregador_noticias`)

`telas_administracao.py:15-241` — gate `eh_admin` (`main.py:896-906` `administrador_geral` ou `eh_admin_do_modulo`) + `bloco_aparencia` (cupê "Aparência" `agregador_noticias_*`, `com_texto_header=True`, defaults `cor_botao=""` → `PADROES_TEMA["agregador_noticias"]` `#000000`) + **5 cards** (Coleta + Fontes + Temas + **Censura + Reinício diário**) + **sem `painel_backup`** (backup removido — banco reciclado).

**Card "Coleta — habilitação e intervalo"** (`card_admin`, `sync`, `grade=False`, `telas_administracao.py:28-107`):

| Campo | Tipo | Chave | Detalhe |
|:---|:---|:---|:---|
| `Módulo habilitado — coletar notícias automaticamente` | `ui.switch` | `agregador_noticias_habilitado` | `data-testid=agregador-habilitado`, `color=primary`, tooltip `Se desabilitado, nenhuma coleta automática ocorre` |
| `Intervalo de coleta` | `ui.select` | `agregador_noticias_intervalo_min` | `data-testid=agregador-intervalo`, opções `10:10 min, 30:30 min, 60:1 hora, 120:2h, 180:3h, 360:6h`, tooltip `Mínimo 10 min, máximo 6h` |
| `Conteúdo da pesquisa (termo livre)` | `ui.input` | `agregador_noticias_termo_pesquisa` | `data-testid=agregador-termo`, `outlined dense clearable w-full`, placeholder `Brasil, Monte Santo, economia`, tooltip `Termo usado na pesquisa Google News (search?q=termo). Vazio = sem pesquisa.` |
| `Hora do reinício diário (HH:MM, padrão 06:00 manhã)` | `ui.input` | `agregador_noticias_hora_reinicio` | `data-testid=agregador-hora-reinicio`, `outlined dense w-full sm:w-64`, placeholder `06:00`, tooltip `Banco reciclado diariamente — zera todas as notícias na hora definida. Ex: 06:00` |

Rodapé `rodape_salvar_restaurar` (`salvar_coleta`, `restaurar_coleta`, `data_testid=agregador-salvar-coleta`, `rotulo_salvar="Salvar coleta"`): `salvar_coleta` → `definir_habilitado(sw)` + `definir_intervalo(sel)` (clamp) + `definir_termo(inp)` + **`definir_hora_reinicio(inp_hora, ator)` (valida `HH:MM`, se inválido `notificar negative` e `return`; senão `reconfigurar_agregador_noticias()` (`rotinas.py:256` + `CronTrigger` hora) + `notificar` `Coleta habilitada/desabilitada • intervalo X min • reinício HH:MM` + `ui.timer(1.0, reload)`)**; `restaurar_coleta` → `False,60,"",06:00` + `reconfigurar`. Buttons extra: `Coletar agora` (`cloud_download`, `contorno`, `data-testid=agregador-coletar-agora`, `coletar_todas(ator, forcar=True)` async `run.io_bound` + spinner) + `Limpar antigas (24h)` (`delete_sweep`, `texto`, `limpar_antigas(24)`).

**Card "Fontes de notícias — Google News, RSS e outras"** (`rss_feed`, `grade=False`, `telas_administracao.py:109-167`):

- Legenda `"Preveja não apenas Google News, mas outras fontes (BBC, JFP, RSS genérico). Adicione/edite abaixo."` (`text-caption`).
- Estado `estado_fontes={"lista": fontes_config()}` + `@ui.refreshable render_fontes()` (`box column w-full gap-2`): `row border rounded px-2 py-1` por fonte com `tipo` (`w-16 bold`), `nome[:30]` (`flex-1`), `tema` (`w-24`), `url[:40]+"…"` (`flex-1 hidden sm:flex`), `ui.button delete flat dense negative` `_rem(i)` + `refresh()`. Vazio → `"Nenhuma fonte. Adicione abaixo."`.
- Inputs de adição: `sel_tipo` (`data-testid=agregador-fonte-tipo`, `google/bbc/jfp/rss`, `google` default, `w-[180px]`), `inp_nome` (`data-testid=agregador-fonte-nome`, `flex-1 min-w-[180px]`, `placeholder Google Brasil`), `inp_tema` (`data-testid=agregador-fonte-tema`, `w-[160px]`, `placeholder Brasil, Economia`), `inp_url` (`data-testid=agregador-fonte-url`, `w-full`, `placeholder https://news.google.com/... ou .../rss.xml`). `adicionar()` (`botao "Adicionar fonte"`, `add`, `texto`, `data-testid=agregador-add-fonte`): valida `url` não vazio senão `warning`; `nova={"tipo": sel or google, "nome": nome or url[:30], "url": url, "tema": tema or Geral}` + `append` + `clear + update()` + `refresh()`.
- Rodapé `rodape_salvar_restaurar` (`salvar_fontes`, `restaurar_fontes`, `data_testid=agregador-salvar-fontes`, `rotulo_salvar="Salvar fontes"`): `salvar_fontes` → `definir_fontes(lista, ator)` + `notificar` + `reload 0.5s`; `restaurar_fontes` → `FONTES_PADRAO` + `definir_fontes(FONTES_PADRAO)` + `reload`.

**Card "Temas — separar notícias por temas"** (`category`, `grade=False`, `telas_administracao.py:169-186`):

- `inp_temas` (`data-testid=agregador-temas`, `ui.input "Temas (separados por vírgula)"`, `", ".join(temas_config())`, `tooltip "Ex.: Brasil, Internacional, Economia, Saúde, Geral"`).
- Rodapé `rodape_salvar_restaurar` (`salvar_temas`, `restaurar_temas`, `data_testid=agregador-salvar-temas`, `rotulo_salvar="Salvar temas"`): `salvar_temas` → `split(",")` `strip` `if t` → `definir_temas(lista, ator)` + `notificar` + `reload 1s`; vazio → `warning "Informe ao menos um tema"`; `restaurar_temas` → `TEMAS_PADRAO` + `definir_temas(TEMAS_PADRAO)` + `reload`.

**Card "Censura de conteúdo — palavras bloqueadas"** (`block`, `grade=False`, `telas_administracao.py:188-233`):

- `ui.textarea "Palavras bloqueadas"` (`data-testid=agregador-palavras-bloqueadas`, `", ".join(obter_palavras_bloqueadas())`, `placeholder tinder, suicidio, aposta`, tooltip `Insensível a maiúscula/acentos; 'suicidio' bloqueia 'suicídio'`) — separadores `,` `;` `\n` via `re.split(r"[,\n;]+")`.
- Rodapé `rodape_salvar_restaurar` (`salvar_censura_ag`, `restaurar_censura_ag`, `data_testid=agregador-salvar-censura`, `rotulo_salvar="Salvar censura"`): `salvar` → `definir_palavras_bloqueadas(lista, ator)` + `limpar_censuradas()` (remove já coletadas censuradas, **sem audit**) + `notificar` + `reload 0.5s`; `restaurar` → `definir_palavras_bloqueadas([], ator)` + `reload`.
- Botão extra `Remover já censuradas agora` (`delete_sweep`, `contorno`, `data-testid=agregador-limpar-censuradas`, `limpar_censuradas()` → `notificar` `N removidas` ou `Nenhuma`).

**Card "Reinício diário — banco reciclado"** (`restart_alt`, `grade=False`, `telas_administracao.py:235-241`) — **substitui `painel_backup`**:

- Legenda `"Banco de notícias é reciclado diariamente às horas da manhã (padrão 06:00), zerando todas as notícias. Configure a hora acima em Coleta. Auditoria apenas de quem alterou o quê no módulo."` (`text-caption`).
- Botão `Zerar agora (reinício manual)` (`delete_forever`, `texto`, `data-testid=agregador-reiniciar-agora`, `reiniciar_banco(ator)` → `notificar` `Banco reiniciado: N notícias apagadas`).
- **Backup removido**: `MAPA_BACKUPS` sem `agregador_noticias` (`rotinas.py:19-30`), `telas_administracao.py` sem `painel_backup` — banco reciclado diariamente.

- **Versionamento**: `versao_modulo:agregador_noticias` no rodapé de `/agregador-noticias`.

## Permissões

| Ação | `comum` com `agregador_noticias` | `administrador_modulo`/`administrador_geral` | Sem acesso |
|:---|:---:|:---:|:---:|
| Ver `/agregador-noticias` (3 colunas + filtro + paginação 10) | ✓ | ✓ | ✗ ("Acesso restrito") |
| `Atualizar` (grid refresh) + paginação `Primeira/Anterior/Próxima/Última` | ✓ | ✓ | — |
| `Coletar agora` (na tela) | ✗ (só admin) | ✓ | — |
| Ver `/admin/agregador_noticias` (switch + intervalo + termo + hora `06:00` + fontes + temas + censura + reinício) | ✗ | ✓ | ✗ (redirect `/agregador-noticias` + `ui.notify` "Acesso restrito a administradores") |
| `Salvar coleta/fontes/temas/censura` + `Zerar agora` | ✗ | ✓ | — |
| `Coletar agora` / `Limpar antigas` / `Zerar agora` (no admin) | ✗ | ✓ | — |

Gate `/agregador-noticias`: `_pode_ver` (admin geral ou `validar_acesso_modulo(user,"agregador_noticias")`). Admin: `_pode_ver` + `eh_admin_do_modulo` (`main.py:896-906`).

LGPD: ainda sem `remover_vinculos_usuario` (notícias são públicas agregadas, sem vínculo por usuário); futuro: anonimizar se necessário.

## Rota e integrações

- Rotas: `/agregador-noticias` (chave `agregador_noticias`, ícone `newspaper`) — `main.py:766-777` (`pagina_restrita("Agregador de Notícias", chave_modulo="agregador_noticias")` + `REGISTRO_MODULOS["agregador_noticias"] = page_agregador_noticias`); `/admin/agregador_noticias` — `main.py:896-906` (`eh_admin` + `ui.colors(primary=ler_tema("agregador_noticias"))` + `mostrar_administracao(nome)`; não-admin → `/agregador-noticias`). Slugs customizáveis via `/configuracoes` → aba Módulo (`rotas_modulos.montar_rotas_ativas()`).
- Auditoria: `audit_log` (núcleo) → `mod_auditoria` banco exclusivo `db_mod_auditoria.db`, tabela `tb_auditoria_agregador_noticias` — **apenas quem alterou o quê no módulo** (`configurar` `habilitado`/`intervalo_min`/`termo_pesquisa`/`fontes_json`/`temas_json`/`hora_reinicio`/`reiniciar_banco`), **sem auditar postagens localizadas** (`coletar_todas`/`limpar_antigas`/`limpar_censuradas` sem `_audit`).
- **Sem backup**: `MAPA_BACKUPS` sem `agregador_noticias` (`rotinas.py:19-30`), `painel_backup` removido de `telas_administracao.py` — banco reciclado diariamente.
- **Agendadores** (`mod_intranet/rotinas.py`): `agregador_coleta` (`rotinas.py:228-241` `BackgroundScheduler` `interval minutes=intervalo_min()` — `coletar_todas` se `habilitado()`, senão skip; `reconfigurar_agregador_noticias()` `:256-285` `pause/resume` + `reschedule minutes` + **`CronTrigger(hour, minute)` para `agregador_reinicio` hora configurável**) + `agregador_reinicio` (`rotinas.py:243-253` `CronTrigger hour=H minute=M` de `obter_hora_reinicio()` default `06:00` → `reiniciar_banco(ator="sistema")` `DELETE FROM tb_noticia`).
- **Reinício diário**: `obter_hora_reinicio()`/`definir_hora_reinicio(HH:MM, ator)` (`bd_manipulador.py:160-186`, default `06:00`, `re.match HH:MM` `00–23:00–59`, audit) + `reiniciar_banco(ator)` (`bd_manipulador.py:189-204`, `COUNT` + `DELETE` + `commit` + `audit`) + `CronTrigger` em `rotinas.py:483` `agregador_reinicio` + `reconfigurar_agregador_noticias()` reaplica intervalo e hora sem restart.
- Cadastro central: `MODULOS_SISTEMA` (`autenticacao.py:25` → `("agregador_noticias","Agregador de Notícias","newspaper","/agregador-noticias")`), `MODULOS_BD` (`repositorio.py:68` → `agregador_noticias: db_mod_agregador_noticias.db`), `PADROES_TEMA["agregador_noticias"]` (`tema_modulo.py:82` → `#000000`), `PREFIXO_POR_CHAVE["agregador_noticias"]` → `agregador_noticias`.
- **Integração TV — Filas** (`mod_filas/telas.py:72-137` `mostrar_tv`): `carregar_noticias()` (`telas.py:103-119`) chama `listar_para_tv(limite=10)` (`agregador_noticias.bd_manipulador:330-352` `SELECT titulo,descricao,url,imagem_url,fonte,tema ORDER BY COALESCE(data_publicacao, data_coleta) DESC LIMIT ?*3` → `[{"titulo","descricao":desc or titulo,"url","imagem","fonte","tema"}]`, filtra censuradas) e exibe carrossel no rodapé da TV (`card bg-grey-900` `min-height:18vh` com `lbl_n_titulo` `text-[1.6vw]`, `lbl_n_desc` `text-[1vw]`, `lbl_n_fonte` `text-caption`) com `ui.timer(7.0, _mostrar_noticia)` (rotaciona `idx % len`) + `ui.timer(120.0, carregar_noticias)` (recarrega lista a cada 2 min); `habilitado()==False` → `"Agregador desabilitado — ative em /admin/agregador_noticias"`; vazio → `"Nenhuma notícia ainda — aguarde coleta"`. `refresh_chamada()` (senha/guichê) segue em `ui.timer(3.0)`.

## Testes

```bash
# Smoke do módulo (import + init_db + CRUD + coleta desabilitada + dedup + hora/zerar + paginação)
.venv/bin/python -c "from mod_agregador_noticias.bd_manipulador import init_db, contar_noticias, listar_noticias, habilitado, intervalo_min, inserir_noticia, _parse_data_pub, obter_hora_reinicio, definir_hora_reinicio, reiniciar_banco; init_db(); print(habilitado(), intervalo_min(), contar_noticias()); print(_parse_data_pub('Tue, 19 Sep 2026 12:34:56 GMT')); print(inserir_noticia('Teste', 'Fonte', 'Geral', 'https://example.com/a', '', 'desc', _parse_data_pub('Tue, 19 Sep 2026 12:34:56 GMT'))); print(listar_noticias(limite=10, offset=0)[:1]); print(obter_hora_reinicio()); print(definir_hora_reinicio('06:00', ator='master')); print(reiniciar_banco(ator='master'))"
# Deduplicação: segunda chamada com mesmo URL ou título normalizado deve retornar False
.venv/bin/python -c "from mod_agregador_noticias.bd_manipulador import inserir_noticia; print(inserir_noticia('Teste', 'Fonte', 'Geral', 'https://example.com/a'))  # False — URL existe
print(inserir_noticia('TESTE', 'Fonte', 'Geral', 'https://example.com/b'))  # False — título normalizado igual (case-insensitive sem acentos)
"
# Paginação 10 — mais atual → mais antiga
.venv/bin/python -c "from mod_agregador_noticias.bd_manipulador import listar_noticias, contar_noticias; total=contar_noticias(); print(total); print([(r[1][:30], r[7]) for r in listar_noticias(limite=10, offset=0)]); print([(r[1][:30], r[7]) for r in listar_noticias(limite=10, offset=10)])"
# Hora e reinício
.venv/bin/python -c "from mod_agregador_noticias.bd_manipulador import definir_hora_reinicio, obter_hora_reinicio, reiniciar_banco; print(definir_hora_reinicio('07:30', ator='master')); print(obter_hora_reinicio()); print(reiniciar_banco(ator='master'))"
# TV
.venv/bin/python -c "from mod_agregador_noticias.bd_manipulador import listar_para_tv; print(listar_para_tv(3))"
# Auditoria só config (quem alterou o quê) — sem audit de postagens
.venv/bin/python -c "from mod_auditoria.bd_manipulador import buscar_logs; print(buscar_logs('tb_auditoria_agregador_noticias', pagina=1, limite_sql=5))"
# Playwright (quando coberto) — paginação com data-testid
.venv/bin/pytest assets/test/teste_agregador_noticias.py -k agregador  # cobre agregador-primeira/anterior/proxima/ultima + hora_reinicio + reiniciar
```

Ver [Análise do Módulo](../analise_mod_agregador_noticias.md) e [Arquitetura](../arquitetura.md).

## Pontos de atenção

- **Habilitado por padrão `0`**: instalação limpa não coleta até o admin habilitar em `/admin/agregador_noticias` (switch + `reconfigurar_agregador_noticias` sem restart; `agregador_coleta` é `pause` quando desabilitado).
- **Intervalo clamp 10–360**: `intervalo_min()`/`definir_intervalo` garantem mín. 10 min / máx. 6 h (`360`); admin select limita a `10/30/60/120/180/360` mas API aceita qualquer `10–360`.
- **Hora reinício `06:00` configurável**: `obter_hora_reinicio()`/`definir_hora_reinicio(HH:MM)` validam `re.match HH:MM` `00–23:00–59`, normalizam `06:00`, `definir` audita + `reconfigurar_agregador_noticias()` reaplica `CronTrigger(hour, minute)` sem restart; `init_db` semeia `06:00` idempotente.
- **Reinício diário `DELETE` — banco reciclado, sem backup**: `reiniciar_banco(ator)` faz `COUNT` + `DELETE FROM tb_noticia` + `commit` + `audit reiniciar_banco N notícias + hora`, log `info`; job `agregador_reinicio` roda **todo dia às `06:00` (ou hora configurada) via `CronTrigger`** (`rotinas.py:243-253` + `483`); `MAPA_BACKUPS` sem `agregador_noticias`, `painel_backup` removido — banco reciclado (zerar todas). Botão `Zerar agora` manual no card Reinício.
- **Auditoria só quem alterou o quê**: `definir_habilitado/intervalo/termo/fontes/temas/hora_reinicio/reiniciar_banco` auditam `configurar`/`reiniciar_banco`; `coletar_todas`/`limpar_antigas`/`limpar_censuradas` **sem `_audit`** (postagens localizadas não auditadas).
- **Paginação 10 — mais atual → mais antiga**: `telas.py grid()` `estado pagina 1` + `por_pagina=10` + `total_pag = max(1,(total+10-1)//10)` + `offset = (pagina-1)*10` + `listar_noticias(tema_f, limite=10, offset=offset)` `ORDER BY COALESCE(data_publicacao, data_coleta) DESC`; botões `Primeira/Anterior/Próxima/Última` com `data-testid agregador-primeira/anterior/proxima/ultima` + `label Página X de Y • N notícias` + `Exibindo len de total`. Imagem `30x30` antes do título (`30px object-cover fit=cover`), sem fonte, sem botão, sem card TV.
- **Fontes ao vivo**: `fontes_json` é editável sem restart; `adicionar` valida `url` não vazia e gera `nome` fallback `url[:30]`; `remover` é por índice com `refresh`.
- **Limpeza 24/24h ainda via `limpar_antigas(24)`**: `coletar_todas` chama `limpar_antigas(24)` (sem audit) + job `agregador_reinicio` zera tudo ao amanhecer; `DELETE WHERE data_coleta < datetime('now','-24 hours')` é portável (traduzido para `LOCALTIMESTAMP` no `banco_conexao` Postgres proxy).
- **Deduplicação por URL + título normalizado** (`bd_manipulador.py:399-443` `inserir_noticia` + `_norm_tit`): `SELECT 1 WHERE url=?` (UNIQUE) + loop `SELECT titulo` com `_norm_tit` (`unicodedata.normalize NFKD → ascii ignore → lower → " ".join(split)`) — evita notícia já incluída com mesmo título case-insensitive sem acentos ou mesma URL antes de `INSERT OR IGNORE` (`ON CONFLICT DO NOTHING` no Postgres); censuradas via `titulo_bloqueado` também descartadas.
- **Timer com tempo real** (`bd_manipulador.py:267-311` `_parse_data_pub` + `457-646` coletores + `314-352` `listar_noticias`/`listar_para_tv` + `telas.py:47-89` `_tempo_relativo`): `_parse_data_pub` reescrito via `email.utils.parsedate_to_datetime` (RFC822 `Tue, 19 Sep 2026 12:34:56 GMT`) + fallback ISO/RSS (`Y-m-dTH:M:S%z`, `Y-m-d H:M:S`, `a, d b Y H:M:S %z/%Z`, `d/m/Y H:M`, normaliza `Z`→`+00:00`) → `YYYY-MM-DD HH:MM:SS` ou `None`, usado em `_coletar_google/bbc/jfp/rss` para extrair `time[datetime]`/`pubDate`/`dc:date` real da postagem e passar para `inserir_noticia`; `listar_noticias`/`listar_para_tv` ordenam por `COALESCE(data_publicacao, data_coleta) DESC`; `telas.py _tempo_relativo` usa `data_pub` real ou `data_col` fallback, mostra `agora`/`3 minutos atrás`/`25 minutos atrás`/`2 semanas...` com parsing flexível (`T`/`Z`/fração, `delta<0→0`, fallback `[:16]`).
- **Card sem fonte e sem botão, só tempo relativo + miniatura `30x30` antes do título + título link, sem card TV, com paginação 10** (`telas.py:47-89` `_tempo_relativo` + `91-113` `_noticia_card` + `149-195` `grid()`): `fonte` continua em `tb_noticia` mas **não exibida no card** — apenas **miniatura `30x30` antes do título quando `imagem_url` + `badge tema + título `ui.link(new_tab=True)` + descrição[:180]… + tempo relativo real** (`agora`/<60 s, minutos/<60 min, horas/<24 h, dias/<7 d, semanas/<30 d, meses/<365d, anos); `data_pub or data_col` com `[:16]` removida; parse flexível `T`/`Z`/fração + `delta<0→agora`; **botão "Abrir notícia" removido 19/09/2026 — título clicável basta, mantém 3 colunas masonry; card `bg-blue-50 "Integração TV — Filas...` removido — grid agora termina com paginação `Primeira/Anterior/Próxima/Última`**.
- **Anti-disconnect coleta** (`telas.py:128-147`): `async _coletar` com `run.io_bound`, `spinner aria-label=Coletando notícias`, trava `ocupado`, `forcar=True`.
- **`bd_criador.py` morto** — nunca executar; schema real é `init_db()` do `bd_manipulador`.
- **Dependências**: `httpx` + `parsel` (`requirements.txt`); sem internet `_get_html` retorna `""` e coleta resulta `0` (fail-soft com `warning` loguru).
