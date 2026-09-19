# Agregador de Notícias — `mod_agregador_noticias`

> News aggregator: route `/agregador-noticias` (key `agregador_noticias`) · own database `db_mod_agregador_noticias.db` · table `tb_noticia` (title/source/theme/url/image/description/dates, 24h retention) · scrapy-like `httpx+parsel` mirroring `klaytonPrinceMS/Noticia` (Sites gn_brasil/gn_saude + Noticias get_noticiasGN/BBC/JFP/RSS) · interval 10–360 min + habilitado flag + free term + configurable sources (google/bbc/jfp/rss) · 3-column masonry + external link · admin: habilitado, intervalo, termo, fontes, temas · TV filas `listar_para_tv` carousel (7s rotate, 120s reload).

---

# Agregador de Notícias — `mod_agregador_noticias`

> Agregador de notícias: rota `/agregador-noticias` (chave `agregador_noticias`) · banco próprio `db_mod_agregador_noticias.db` · tabela `tb_noticia` (título/fonte/tema/url/imagem/descrição/datas, retenção 24h) · scrapy-like `httpx+parsel` espelhando `klaytonPrinceMS/Noticia` (Sites gn_brasil/gn_saude + Noticias get_noticiasGN/BBC/JFP/RSS) · intervalo 10–360 min + flag habilitado + termo livre + fontes configuráveis (google/bbc/jfp/rss) · 3 colunas masonry + link externo · admin: habilitado, intervalo, termo, fontes, temas · TV filas `listar_para_tv` carrossel (7s rotação, 120s recarrega).

## Propósito

Módulo que **agrega notícias multi-fonte** para a rede interna, com **conteúdo de pesquisa configurável pelo admin** (termo livre) e **previsão de não apenas Google News, mas outras fontes** (`BBC`, `JFP`, `RSS`). Coleta **scrapy-like** (`httpx` + `parsel`) espelhando `https://github.com/klaytonPrinceMS/Noticia` — `Sites` (`gn_brasil`, `gn_saude` etc) + `Noticias.get_noticiasGN/BBC/JFP/RSS` — investigando a cada **10 min–6 h** (clamp) quando **habilitado**. Banco **reiniciado 24/24h** (`limpar_antigas` + job diário). Visual em **3 colunas masonry** com card **imagem + título + fonte** e clique que abre **link externo via `window.open`**. Integra a **TV do `mod_filas`** (`/tv`) com **carrossel título+descrição** via `listar_para_tv` (`timer 7s` rotação + `120s` recarrega).

## Banco próprio

Conexão WAL + `foreign_keys=ON` via `mod_intranet/banco_conexao.conexao("agregador_noticias")` (backend duplo SQLite/PostgreSQL). Criador vigente: `init_db()` em `bd_manipulador.py:162-201`, executado no import (`bd_manipulador.py:463` `init_db()`) e pelo bootstrap central (`mod_intranet/bd_criador.py:67` `init_agregador`).

**`tb_noticia`**:

| Coluna | Observação |
|:---|:---|
| `id` | PK AUTOINCREMENT |
| `titulo` | TEXT NOT NULL (`[:500]` em `inserir_noticia`) |
| `fonte` | TEXT NOT NULL (`[:100]` — ex.: `Google News - Brasil`, `BBC`, `JFP Notícias`, `RSS`) |
| `tema` | TEXT NOT NULL DEFAULT `Geral` (`[:50]` — ex.: `Brasil`, `Saúde`, `Economia`) |
| `url` | TEXT NOT NULL UNIQUE (`[:2000]`, normalizada `/`→ `https://news.google.com` + `/`) — `INSERT OR IGNORE` deduplica |
| `imagem_url` | TEXT DEFAULT `''` (`[:2000]` — `img::attr(src)`/`data-src`/`media:content`) |
| `descricao` | TEXT DEFAULT `''` (`[:1000]` — `description::text` RSS ou `txt` Google/BBC/JFP) |
| `data_publicacao` | DATETIME (`COALESCE(?, datetime('now'))` — `None` → `now`) |
| `data_coleta` | DATETIME DEFAULT `CURRENT_TIMESTAMP` (`ORDER BY ... DESC`) |

Índices `idx_noticia_tema(tema)`, `idx_noticia_fonte(fonte)`, `idx_noticia_data(data_coleta)`.

**Temas padrão** (`TEMAS_PADRAO` — `bd_manipulador.py:24`): `["Brasil","Internacional","Economia","Saúde","Ciência e Tecnologia","Entretenimento","Esporte","Monte Santo de Minas","Geral"]` — 9 temas, semente `temas_json` em `tb_config` central (`json.dumps`).

**Fontes padrão** (`FONTES_PADRAO` — `bd_manipulador.py:27-31`, espelho `Sites` `gn_brasil`/`gn_saude`):

| `tipo` | `nome` | `url` | `tema` |
|:---|:---|:---|:---|
| `google` | Google News - Brasil | `https://news.google.com/topics/CAAqJQgKIh9DQkFTRVFvSUwyMHZNREUxWm5JU0JYQjBMVUpTS0FBUAE?hl=pt-BR&gl=BR&ceid=BR%3Apt-419` | `Brasil` |
| `bbc` | BBC - Brasil | `https://www.bbc.com/portuguese/topics/cz74k717pw5t` | `Brasil` |
| `google` | Google News - Saúde | `https://news.google.com/topics/CAAqJQgKIh9DQkFTRVFvSUwyMHZNR3QwTlRFU0JYQjBMVUpTS0FBUAE?hl=pt-BR&gl=BR&ceid=BR%3Apt-419` | `Saúde` |

⚠️ `bd_criador.py` legado/morto.

## Fluxo da tela

- Gate `_pode_ver` (`telas.py:19-25`): `administrador_geral` ou `validar_acesso_modulo(user,"agregador_noticias")`; sem acesso → `block` 64px + "Acesso restrito".
- `mostrar_tela(user_nome, perfil_global)` (`telas.py:28-130`): `ler_tema("agregador_noticias", cor_botao="#000000", texto_header="Notícias agregadas de múltiplas fontes — 3 colunas, clique abre no site original. Para TV do Filas, carrossel título+descrição.")` + `ui.colors(primary)` + `cabecalho(... chave_modulo="agregador_noticias")` + `estado={tema:""}` + `temas=temas_config()`.
  - **Barra** (`telas.py:87-104`): `newspaper` icon + `sel_tema` (`data-testid=agregador-filtro-tema`, `Todos os temas` + `temas`, `on_value_change→estado+grid.refresh`) + badge `Coleta: ativa/desabilitada • intervalo X min • N notícias (24h)` + `botao Atualizar` (`data-testid=agregador-atualizar`, `texto`) + `botao Coletar agora` (`data-testid=agregador-coletar`, `primario`, só `administrador_geral`/`eh_admin_do_modulo` → `coletar_todas(ator) + notificar + refresh`).
  - **`_noticia_card(n)`** (`telas.py:47-81`): `n=(id,titulo,fonte,tema,url,imagem_url,descricao,data_pub,data_coleta)` → `ui.card w-full hover:shadow-lg cursor-pointer break-inside:avoid` + `ui.image(img) w-full h-40 object-cover` (`try` fail-soft) + `card_section` com `badge(tema)`, `ui.link(titulo,target=href,new_tab=True) font-bold` (`try` → `label` fallback), `descricao[:180]` (`text-caption`), `row` fonte + data `[:16]`, `ui.run_javascript("window.open('href','_blank')")` helper + botão `Abrir notícia` `flat dense` (`window.open`).
  - **`grid()`** (`@ui.refreshable`, `telas.py:106-125`): `tema_f=estado["tema"] or None` → `ag.listar_noticias(tema_f, limite=45)` → `column-count:3` masonry com `break-inside:avoid` por item; vazio → `article 48px` + `"Nenhuma notícia ainda. Ative a coleta nas Configurações."` + tema se filtrado.
  - **TV info**: `card bg-blue-50` com integração.
- Responsividade: `w-full p-6 gap-4`, `flex-wrap`, `column-count:3` desktop (masonry), `min-width:0`.
- **Admin** (`telas_administracao.py:15-157`): `bloco_aparencia` + `card "Coleta"` (switch `data-testid=agregador-habilitado` + select `agregador-intervalo` 10/30/60/120/180/360 + input `agregador-termo` + `rodape_salvar_restaurar data-testid=agregador-salvar-coleta` + `Coletar agora` `data-testid=agregador-coletar-agora` + `Limpar antigas`) + `card "Fontes"` (`data-testid agregador-fonte-tipo/nome/tema/url`, `estado_fontes` + `render_fontes` + `Adicionar fonte` `data-testid=agregador-add-fonte` + `rodape data-testid=agregador-salvar-fontes`) + `card "Temas"` (`data-testid=agregador-temas`, `rodape data-testid=agregador-salvar-temas`) + `painel_backup`.

## Regras de negócio relevantes

- **Habilitado** (`habilitado()`/`definir_habilitado(bool,ator)` — `bd_manipulador.py:77-86`): `get_config("agregador_noticias_habilitado","0")=="1"`; `set_config` + `audit configurar habilitado`; `init_db` semente `0` (desabilitado).
- **Intervalo** (`intervalo_min()`/`definir_intervalo(min,ator)` — `bd_manipulador.py:89-101`): `int(get_config("agregador_noticias_intervalo_min","60"))` com `try` fallback `60` + `clamp max(10,min(360,v))`; `definir_intervalo` `clamp 10–360` + `audit` + `return ok,v` (`v` clampado).
- **Termo** (`termo_pesquisa()`/`definir_termo(termo,ator)` — `bd_manipulador.py:104-112`): `get_config("agregador_noticias_termo_pesquisa","").strip()`; `definir_termo` `strip` + `audit`.
- **Fontes** (`fontes_config()`/`definir_fontes(list,ator)` — `bd_manipulador.py:115-138`): `json.loads(get_config("agregador_noticias_fontes_json",""))` → `list` se `isinstance(list) and dados` senão `FONTES_PADRAO`; `definir_fontes` `json.dumps(ensure_ascii=False)` + `set_config` + `audit configurar fontes_json N fontes`.
- **Temas** (`temas_config()`/`definir_temas(list,ator)` — `bd_manipulador.py:141-157`): `json.loads(temas_json)` → `[t.strip() for t in dados if strip]` senão `TEMAS_PADRAO`; `definir_temas` `json.dumps([t.strip() if strip])` + `audit`.
- **Inserir** (`inserir_noticia` — `bd_manipulador.py:261-282`): `titulo[:500]`, `url[:2000]`, `url "/"→"https://news.google.com"+url` (relativa Google), `fonte[:100]`, `tema[:50] or Geral`, `imagem[:2000]`, `desc[:1000]`, `INSERT OR IGNORE INTO tb_noticia (titulo,fonte,tema,url,imagem_url,descricao,data_publicacao) VALUES (?,?,?,?,?,?,COALESCE(?,datetime('now')))` → `return rowcount>0` (deduplicação por `url UNIQUE`).
- **Listar** (`listar_noticias(tema,limite,offset)` — `bd_manipulador.py:219-229`): `SELECT ... WHERE tema=? ORDER BY data_coleta DESC LIMIT ? OFFSET ?` / `ORDER BY ... DESC LIMIT/OFFSET` sem tema; `contar_noticias(tema?)` (`bd_manipulador.py:206-216`); `listar_para_tv(limite=10)` (`bd_manipulador.py:232-242` `SELECT titulo,descricao,url,imagem_url,fonte,tema ORDER BY data_coleta DESC LIMIT ?` → `[{"titulo","descricao":desc or titulo,"url","imagem","fonte","tema"}]`).
- **Limpar** (`limpar_antigas(horas=24)` — `bd_manipulador.py:245-258`): `DELETE WHERE data_coleta < datetime('now','-N hours')` (portável: `banco_conexao` traduz `datetime('now','-24 hours')` → `LOCALTIMESTAMP`/`CURRENT_TIMESTAMP` no Postgres proxy) + `rowcount n` + `log info` + `audit limpar_antigas N removidas`; chamada ao fim de `coletar_todas` + job diário `agregador_limpeza`.
- **Coleta** (`coletar_todas(ator)` — `bd_manipulador.py:418-455`): `if not habilitado(): 0` + `fontes_config()` + `termo_pesquisa()` → `total=0` + loop `for f in fontes: tipo=(tipo or google).lower(), url, tema or Geral, nome or url[:30]; tipo google→_coletar_google, bbc→_coletar_bbc, jfp→_coletar_jfp, rss→_coletar_rss, else→_coletar_google` (fail-soft `warning`) + `termo → _coletar_pesquisa_google(termo,Geral)` + `limpar_antigas(24)` (`try`) + `_audit coletar N novas fontes/N termo[:30]` + `log info`.
- **`_get_html(url,timeout=12)`** (`bd_manipulador.py:287-295`): `httpx.get(url, timeout, follow_redirects=True, headers={"User-Agent":"Mozilla/5.0 (IntrAnEt; AgregadorNoticias)"})` → `r.text` se `200` senão `""` (`warning` em exceção).
- **Parsers** (`parsel.Selector`): Google `".gPFEn, .JtKRv, .a7P8L, article"` + `a::text`/`href` (`.`/`/`→ `https://news.google.com`) + `img::attr(src/data-src)` (20); BBC `".bbc-uk8dsi, .bbc-19j92fr, article"` (`/`→ `https://www.bbc.com`) (15); JFP `".td-module-title a"` (15); RSS `type="xml"` `item` → `title::text` + `link::text/attr(href)` + `description::text` + `media:content::attr(url)` (15); pesquisa Google `https://news.google.com/search?q={quote(termo)}&...` → `_coletar_google`.
- **LGPD**: notícias públicas sem vínculo por usuário; sem `remover_vinculos` ainda (futuro se necessário).

## Integrações com o núcleo

Importa `autenticacao.validar_acesso_modulo`/`perfil_global_de`/`eh_admin_do_modulo`, `banco_conexao.conexao`/`get_config`/`set_config`, `tema_modulo.ler_tema`/`notificar`/`bloco_aparencia`, `ui_comum.botao`/`card_admin`/`rodape_salvar_restaurar`, `observabilidade.get_logger`. Grava via `audit_log` → `tb_auditoria_agregador_noticias`. Agendadores `rotinas._job_agregador_coleta` (`interval minutes`) + `_job_agregador_limpeza` (`interval hours=24`) + `reconfigurar_agregador_noticias()` (`pause/resume`+`reschedule`). Backup via `rotinas.painel_backup`/`MAPA_BACKUPS` (`agregador_noticias: db_mod_agregador_noticias.db`). `PREFIXO_POR_CHAVE`/`PADROES_TEMA`/`MODULOS_SISTEMA`/`MODULOS_BD` com `agregador_noticias`. `bd_criador.py` init_agregador no `mod_intranet/bd_criador.py`. TV `mod_filas` consome `listar_para_tv`.

## Pontos de atenção

- Habilitado default `0` — sem coleta até admin habilitar; `reconfigurar_agregador_noticias()` (`rotinas.py:256`) `pause` quando desabilitado, `resume+reschedule` quando habilitado (sem restart).
- Intervalo `clamp 10–360` — `intervalo_min()` e `definir_intervalo` garantem faixa; admin select limita a 6 opções, API aceita qualquer `10–360`.
- `INSERT OR IGNORE` com `url UNIQUE` — deduplicação; no Postgres `ON CONFLICT DO NOTHING` via `banco_conexao` proxy (`_CursorPostgres` `INSERT OR IGNORE`→`ON CONFLICT`).
- `datetime('now','-N hours')` portável — `banco_conexao` traduz para `LOCALTIMESTAMP` no Postgres (`_CursorPostgres._preparar` + `_ddl_postgres`).
- `httpx`+`parsel` (`requirements.txt`); sem internet coleta `0` (fail-soft); `User-Agent` custom; timeout `12s`; `try/except` com `warning` em cada coletor.
- `url` relativa Google normalizada em `inserir_noticia` + `_coletar_google` (`./`/`/`→`https://news.google.com`).
- `listar_para_tv` `descricao or titulo` — TV nunca mostra vazio; `habilitado()==False` → placeholder desabilitado; vazio → placeholder aguarde.

## Status

| Item | Situação |
|:---|:---|
| Banco WAL `tb_noticia` + `TEMAS/FONTES_PADRAO` + seeds `tb_config` | Implementado (`init_db()` + `ORGANOGRAMA_BASE` mirror `Noticia`) |
| Coleta scrapy-like `httpx+parsel` Google/BBC/JFP/RSS + pesquisa termo | Implementado (`_coletar_google/bbc/jfp/rss/pesquisa` + `coletar_todas`) |
| Habilitado flag + intervalo 10–360 clamp + termo livre + fontes/temas `json` | Implementado (`habilitado/definir_habilitado`, `intervalo_min/definir_intervalo`, `termo/definir_termo`, `fontes/temas_config`) |
| 24h retenção `limpar_antigas` + `coletar_todas` + job diário | Implementado (`DELETE ... -24 hours` + `_job_agregador_limpeza` 24h) |
| 3 colunas masonry `column-count:3` + card imagem+título+fonte + `window.open` | Implementado (`telas.py _noticia_card` + `grid()`) |
| Filtro tema + `Coletar agora` + badge status | Implementado (`sel_tema` + `grid.refresh` + `coletar_todas(ator)`) |
| Admin: switch habilitado + select intervalo + input termo + card fontes + card temas | Implementado (`telas_administracao.py` 157 linhas, `data-testid` QA) |
| `listar_para_tv` + TV `mod_filas` carrossel 7s/120s | Implementado (`listar_para_tv` + `mod_filas/telas.py mostrar_tv` `noticias_tv` `7s`+`120s`) |
| `MODULOS_SISTEMA`/`MODULOS_BD`/`PADROES_TEMA`/`PREFIXO_POR_CHAVE` | Implementado (`autenticacao.py:25`, `repositorio.py:68`, `tema_modulo.py:82`) |
| Agendadores `agregador_coleta`/`agregador_limpeza` + `reconfigurar` | Implementado (`rotinas.py:228-277` `interval minutes`/`hours 24`) |
| `main.py` `/agregador-noticias` + `/admin/agregador_noticias` + `bd_criador init_agregador` | Implementado (`main.py:766-777`, `896-906`, `bd_criador.py:67`) |
