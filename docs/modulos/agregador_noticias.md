# News Aggregator Module — `mod_agregador_noticias`

> News aggregator module: route `/agregador-noticias` (key `agregador_noticias`) · own database `db_mod_agregador_noticias.db` (WAL) · table `tb_noticia` (title/source/theme/url/image/description/dates) · 24h retention via `limpar_antigas` · scrapy-like collection `httpx+parsel` mirroring `klaytonPrinceMS/Noticia` (`Sites` + `Noticias.get_noticiasGN/BBC/JFP/RSS`) · interval 10–360 min + `habilitado` flag + free term + configurable sources · 3-column masonry (image+title+source → `window.open`) · TV integration via `listar_para_tv` carousel.

---

# Módulo Agregador de Notícias — `mod_agregador_noticias`

> Módulo agregador de notícias: rota `/agregador-noticias` (chave `agregador_noticias`) · banco próprio `db_mod_agregador_noticias.db` (WAL) · tabela `tb_noticia` (título/fonte/tema/url/imagem/descrição/datas) · retenção 24h via `limpar_antigas` · coleta scrapy-like `httpx+parsel` espelhando `klaytonPrinceMS/Noticia` (`Sites` gn_brasil/gn_saude + `Noticias.get_noticiasGN/BBC/JFP/RSS`) · intervalo 10–360 min + flag `habilitado` + termo livre + fontes configuráveis · 3 colunas masonry (imagem+título+fonte → `window.open`) · integração TV via `listar_para_tv` carrossel.

## Propósito

Agregador **multi-fonte** de notícias para a rede interna. O administrador especifica o **conteúdo da pesquisa** (termo livre, ex.: `Brasil`, `Monte Santo`, `economia`) e **prevê não apenas Google News, mas outras fontes** (`BBC`, `JFP`, `RSS` genérico), todas configuráveis sem restart. O sistema investiga periodicamente as fontes via **scrapy-like** (`httpx` + `parsel`, espelho de `https://github.com/klaytonPrinceMS/Noticia` — classe `Sites` com `gn_brasil`, `gn_saude` etc + `Noticias` com `get_noticiasGN/BBC/JFP/RSS`), armazena por **24 h** (banco reiniciado 24/24h) e exibe em **3 colunas masonry** com card de imagem + título + fonte. Clique no card abre o **link externo original** (`window.open`). Enquanto aguardam na TV do módulo **Filas** (`/tv`), os usuários veem **carrossel título+descrição** das últimas notícias (`listar_para_tv`).

> Status: **ativo** (coleta habilitável por flag; intervalo 10 min–6 h; sem impacto no core).

## Banco de dados

Criador vigente: `init_db()` em `bd_manipulador.py:162-201` (bootstrap central `mod_intranet/bd_criador.py:67-68` `init_agregador` + chamada no import `bd_manipulador.py:463` `init_db()`).

Conexão via `mod_intranet/banco_conexao.conexao("agregador_noticias")` (backend duplo SQLite/PostgreSQL, `PRAGMA journal_mode=WAL` + `foreign_keys=ON`). Índices `idx_noticia_tema`, `idx_noticia_fonte`, `idx_noticia_data`.

| Tabela | Conteúdo |
|:---|:---|
| `tb_noticia` | `id` PK, `titulo` TEXT (`500`), `fonte` TEXT (`100`), `tema` TEXT (`50`, default `Geral`), `url` TEXT UNIQUE (`2000`, normalizada `https://news.google.com` se `/`), `imagem_url` TEXT (`2000`, `img::attr(src)` + `data-src`/`media:content`), `descricao` TEXT (`1000`), `data_publicacao` DATETIME (`COALESCE(?, datetime('now'))`), `data_coleta` DATETIME `DEFAULT CURRENT_TIMESTAMP` |

Seeds de `tb_config` central (idempotentes, `bd_manipulador.py:182-199` — `SELECT valor` → `INSERT` só se ausente):

| Chave | Default | Descrição |
|:---|:---|:---|
| `agregador_noticias_habilitado` | `0` | coleta desabilitada por padrão |
| `agregador_noticias_intervalo_min` | `60` | 1 h (clamp 10–360) |
| `agregador_noticias_termo_pesquisa` | `""` | termo livre (vazio = sem pesquisa `search?q=`) |
| `agregador_noticias_temas_json` | `TEMAS_PADRAO` `["Brasil","Internacional","Economia","Saúde","Ciência e Tecnologia","Entretenimento","Esporte","Monte Santo de Minas","Geral"]` | temas para filtro |
| `agregador_noticias_fontes_json` | `FONTES_PADRAO` (3, `bd_manipulador.py:27-31`) | Google Brasil/Saúde (`google`, `tema Brasil/Saúde`) + BBC Brasil (`bbc`) — espelho `Sites` `gn_brasil`/`gn_saude` |

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

### Tela `/agregador-noticias` — 3 colunas masonry

- **Gate** (`_pode_ver` — `telas.py:19-25`): `administrador_geral` sempre; senão `validar_acesso_modulo(user, "agregador_noticias")` — sem acesso → "Acesso restrito".
- **Cabeçalho temático** (`telas.py:36-42`): `ler_tema("agregador_noticias", cor_botao="#000000", texto_header="Notícias agregadas de múltiplas fontes — 3 colunas, clique abre no site original. Para TV do Filas, carrossel título+descrição.")` + `ui.colors(primary=tema["cor_botao"])` + `cabecalho("Agregador de Notícias", ..., chave_modulo="agregador_noticias")` (borda = `cor_botao` via `PADROES_TEMA["agregador_noticias"]` → `#000000`).
- **Barra de filtro** (`telas.py:87-104`): `ui.select` `Filtrar por tema` (`data-testid=agregador-filtro-tema`, `{"": "Todos os temas"} | {t:t}`, `estado["tema"]`) + badge `"Coleta: ativa/desabilitada • intervalo X min • N notícias (24h)"` (`contar_noticias()`, `habilitado()`, `intervalo_min()`) + `botao "Atualizar"` (`refresh`, `texto`, `data-testid=agregador-atualizar`, `grid.refresh()`) + `botao "Coletar agora"` (`sync`, `primario`, `data-testid=agregador-coletar`, só `administrador_geral` ou `eh_admin_do_modulo`) → `ag.coletar_todas(ator=user_nome)` + `notificar` + `grid.refresh()`.
- **Grid masonry 3 colunas** (`@ui.refreshable grid()` — `telas.py:106-125`, `limite=45`, `ORDER BY data_coleta DESC`): `column-count: 3; column-gap: 1rem;` + por notícia `break-inside: avoid; margin-bottom: 1rem;` + `_noticia_card(n)` (`telas.py:47-81`): `ui.card` `w-full overflow-hidden hover:shadow-lg cursor-pointer` + imagem `ui.image(img).classes("w-full h-40 object-cover")` (`try` fail-soft) + `card_section` com `ui.badge(tema)`, `ui.link(titulo, target=href, new_tab=True)` (`font-bold`, `word-break`), `descricao[:180]` (`text-caption`), `row` fonte + data `[:16]`, `ui.run_javascript("window.open('href','_blank')")` no card + botão `Abrir notícia` `flat dense` fallback. Sem notícia → card `"Nenhuma notícia ainda. Ative a coleta nas Configurações."` + tema.
- **Info TV** (`telas.py:127-130`): `card bg-blue-50 border-blue-200` com `"Integração TV — Filas"` + `"Enquanto aguardam, a TV (/tv) exibe carrossel com título+descrição das últimas notícias via ag.listar_para_tv() (3 colunas aqui, carrossel lá)."`.
- **Helpers**: `_noticia_card` normaliza `href` (`#` fallback), sanitiza `titulo[:500]`/`url[:2000]` (`inserir_noticia`), `data-testid` para QA, `notificar` com `timeout` configurável, `ui.colors` do módulo.

#### Coleta scrapy-like (espelho `klaytonPrinceMS/Noticia`)

| Função | Fonte | Seletores | Limite |
|:---|:---|:---|:---:|
| `_coletar_google(url, fonte_nome, tema)` (`bd_manipulador.py:298-324`) | Google News (`Sites.gn_*`) | `.gPFEn, .JtKRv, .a7P8L, article` → `a::text` + `a::attr(href)` + `img::attr(src/data-src)`; `href ./`→ `https://news.google.com/` | 20 |
| `_coletar_bbc(url, tema)` (`bd_manipulador.py:327-350`) | BBC (`get_noticiasBBC`) | `.bbc-uk8dsi, .bbc-19j92fr, article` → `a::text` + `href` (`/`→ `https://www.bbc.com`) + `img::attr(src)` | 15 |
| `_coletar_jfp(url, tema)` (`bd_manipulador.py:353-374`) | JFP Notícias (`get_noticiasJFP`) | `.td-module-title a` → `::text` + `::attr(href)` + `img::attr(src)` | 15 |
| `_coletar_rss(url, fonte_nome, tema)` (`bd_manipulador.py:377-403`) | RSS genérico (`get_noticiasRSS`) | `parsel.Selector(xml, type="xml")` `item` → `title::text` + `link::text/attr(href)` + `description::text` + `media:content::attr(url)` | 15 |
| `_coletar_pesquisa_google(termo)` (`bd_manipulador.py:406-415`) | Pesquisa termo livre (`Noticia` termo) | `https://news.google.com/search?q={quote(termo)}&hl=pt-BR&gl=BR&ceid=BR%3Apt-419` → `_coletar_google(..., "Pesquisa:termo")` | 20 |

**Orquestração** (`coletar_todas(ator)` — `bd_manipulador.py:418-455`): `if not habilitado(): 0` + `fontes_config()` (`FONTES_PADRAO` ou `fontes_json`) + `termo_pesquisa()` → loop por fonte (`tipo` → dispatch acima; `google/bbc/jfp/rss`/default) + `termo → _coletar_pesquisa_google(termo, "Geral")` → `limpar_antigas(24)` (reiniciado 24/24h) → `_audit("coletar", "N novas", "fontes/N termo")` + log `info`. `httpx.get(url, timeout=12, follow_redirects=True, headers={"User-Agent":"Mozilla/5.0 (IntrAnEt; AgregadorNoticias)"})` (`_get_html` `:287-295`, `warning` em falha).

**Helpers de config** (`bd_manipulador.py:77-158`): `habilitado()` (`agregador_noticias_habilitado=="1"`), `definir_habilitado(bool, ator)` + `audit configurar`, `intervalo_min()` (`int(get_config("intervalo_min",60))` `clamp 10–360`), `definir_intervalo(min, ator)` (`clamp + audit + return ok,v`), `termo_pesquisa()`/`definir_termo(termo, ator)`, `fontes_config()` (`json.loads(fontes_json)` → `FONTES_PADRAO` em falha), `definir_fontes(list, ator)` (`json.dumps` + `audit`), `temas_config()`/`definir_temas(list, ator)` (`json.dumps` + `audit`), `intervalo_criar_job()` `return habilitado(), intervalo_min()` para `rotinas`.

**CRUD** (`bd_manipulador.py:206-282`): `contar_noticias(tema?)` (`COUNT`), `listar_noticias(tema, limite=30, offset=0)` (`SELECT ... ORDER BY data_coleta DESC LIMIT/OFFSET`), `listar_para_tv(limite=10)` (`SELECT titulo,descricao,url,imagem_url,fonte,tema ORDER BY data_coleta DESC LIMIT ?` → `[{"titulo","descricao": desc or titulo,"url","imagem","fonte","tema"}]`), `limpar_antigas(horas=24)` (`DELETE WHERE data_coleta < datetime('now', '-N hours')` + `log info` + `audit` se `n`), `inserir_noticia(titulo,fonte,tema,url,imagem,descricao,data_pub)` (`titulo[:500]`, `url[:2000]`, `url "/"→"https://news.google.com"+url`, `fonte[:100]`, `tema[:50] or Geral`, `imagem[:2000]`, `desc[:1000]`, `INSERT OR IGNORE` + `COALESCE(data_pub, datetime('now'))`).

### Administração (`/admin/agregador_noticias`)

`telas_administracao.py:15-157` — gate `eh_admin` (`main.py:896-906` `administrador_geral` ou `eh_admin_do_modulo`) + `bloco_aparencia` (cupê "Aparência" `agregador_noticias_*`, `com_texto_header=True`, defaults `cor_botao=""` → `PADROES_TEMA["agregador_noticias"]` `#000000`) + 3 cards + `painel_backup`.

**Card "Coleta — habilitação e intervalo"** (`card_admin`, `sync`, `grade=False`, `telas_administracao.py:28-76`):

| Campo | Tipo | Chave | Detalhe |
|:---|:---|:---|:---|
| `Módulo habilitado — coletar notícias automaticamente` | `ui.switch` | `agregador_noticias_habilitado` | `data-testid=agregador-habilitado`, `color=primary`, tooltip `Se desabilitado, nenhuma coleta automática ocorre` |
| `Intervalo de coleta` | `ui.select` | `agregador_noticias_intervalo_min` | `data-testid=agregador-intervalo`, opções `10:10 min, 30:30 min, 60:1 hora, 120:2h, 180:3h, 360:6h`, tooltip `Mínimo 10 min, máximo 6h` |
| `Conteúdo da pesquisa (termo livre)` | `ui.input` | `agregador_noticias_termo_pesquisa` | `data-testid=agregador-termo`, `outlined dense clearable w-full`, placeholder `Brasil, Monte Santo, economia`, tooltip `Termo usado na pesquisa Google News (search?q=termo). Vazio = sem pesquisa.` |

Rodapé `rodape_salvar_restaurar` (`salvar_coleta`, `restaurar_coleta`, `data_testid=agregador-salvar-coleta`, `rotulo_salvar="Salvar coleta"`): `salvar_coleta` → `definir_habilitado(sw)` + `definir_intervalo(sel)` (clamp) + `definir_termo(inp)` + `reconfigurar_agregador_noticias()` (`rotinas.py:256`, `pause/resume` + `reschedule minutes`) + `notificar` + `ui.timer(1.0, reload)`; `restaurar_coleta` → `False,60,""` + `reconfigurar`. Buttons extra: `Coletar agora` (`cloud_download`, `contorno`, `data-testid=agregador-coletar-agora`, `coletar_todas(ator)`) + `Limpar antigas (24h)` (`delete_sweep`, `texto`, `limpar_antigas(24)`).

**Card "Fontes de notícias — Google News, RSS e outras"** (`rss_feed`, `grade=False`, `telas_administracao.py:78-135`):

- Legenda `"Preveja não apenas Google News, mas outras fontes (BBC, JFP, RSS genérico). Adicione/edite abaixo."` (`text-caption`).
- Estado `estado_fontes={"lista": fontes_config()}` + `@ui.refreshable render_fontes()` (`box column w-full gap-2`): `row border rounded px-2 py-1` por fonte com `tipo` (`w-16 bold`), `nome[:30]` (`flex-1`), `tema` (`w-24`), `url[:40]+"…"` (`flex-1 hidden sm:flex`), `ui.button delete flat dense negative` `_rem(i)` + `refresh()`. Vazio → `"Nenhuma fonte. Adicione abaixo."`.
- Inputs de adição: `sel_tipo` (`data-testid=agregador-fonte-tipo`, `google/bbc/jfp/rss`, `google` default, `w-[180px]`), `inp_nome` (`data-testid=agregador-fonte-nome`, `flex-1 min-w-[180px]`, `placeholder Google Brasil`), `inp_tema` (`data-testid=agregador-fonte-tema`, `w-[160px]`, `placeholder Brasil, Economia`), `inp_url` (`data-testid=agregador-fonte-url`, `w-full`, `placeholder https://news.google.com/... ou .../rss.xml`). `adicionar()` (`botao "Adicionar fonte"`, `add`, `texto`, `data-testid=agregador-add-fonte`): valida `url` não vazio senão `warning`; `nova={"tipo": sel or google, "nome": nome or url[:30], "url": url, "tema": tema or Geral}` + `append` + `clear + update()` + `refresh()`.
- Rodapé `rodape_salvar_restaurar` (`salvar_fontes`, `restaurar_fontes`, `data_testid=agregador-salvar-fontes`, `rotulo_salvar="Salvar fontes"`): `salvar_fontes` → `definir_fontes(lista, ator)` + `notificar` + `reload 0.5s`; `restaurar_fontes` → `FONTES_PADRAO` + `definir_fontes(FONTES_PADRAO)` + `reload`.

**Card "Temas — separar notícias por temas"** (`category`, `grade=False`, `telas_administracao.py:138-154`):

- `inp_temas` (`data-testid=agregador-temas`, `ui.input "Temas (separados por vírgula)"`, `", ".join(temas_config())`, `tooltip "Ex.: Brasil, Internacional, Economia, Saúde, Geral"`).
- Rodapé `rodape_salvar_restaurar` (`salvar_temas`, `restaurar_temas`, `data_testid=agregador-salvar-temas`, `rotulo_salvar="Salvar temas"`): `salvar_temas` → `split(",")` `strip` `if t` → `definir_temas(lista, ator)` + `notificar` + `reload 1s`; vazio → `warning "Informe ao menos um tema"`; `restaurar_temas` → `TEMAS_PADRAO` + `definir_temas(TEMAS_PADRAO)` + `reload`.

**Backup**: `painel_backup(usuario, "agregador_noticias")` (job `backup:agregador_noticias` 12h, `MAPA_BACKUPS` `agregador_noticias: db_mod_agregador_noticias.db`).

- **Versionamento**: `versao_modulo:agregador_noticias` no rodapé de `/agregador-noticias`.

## Permissões

| Ação | `comum` com `agregador_noticias` | `administrador_modulo`/`administrador_geral` | Sem acesso |
|:---|:---:|:---:|:---:|
| Ver `/agregador-noticias` (3 colunas + filtro) | ✓ | ✓ | ✗ ("Acesso restrito") |
| `Atualizar` (grid refresh) | ✓ | ✓ | — |
| `Coletar agora` (na tela) | ✗ (só admin) | ✓ | — |
| Ver `/admin/agregador_noticias` (switch + intervalo + termo + fontes + temas) | ✗ | ✓ | ✗ (redirect `/agregador-noticias` + `ui.notify` "Acesso restrito a administradores") |
| `Salvar coleta/fontes/temas` | ✗ | ✓ | — |
| `Coletar agora` / `Limpar antigas` (no admin) | ✗ | ✓ | — |

Gate `/agregador-noticias`: `_pode_ver` (admin geral ou `validar_acesso_modulo(user,"agregador_noticias")`). Admin: `_pode_ver` + `eh_admin_do_modulo` (`main.py:896-906`).

LGPD: ainda sem `remover_vinculos_usuario` (notícias são públicas agregadas, sem vínculo por usuário); futuro: anonimizar se necessário.

## Rota e integrações

- Rotas: `/agregador-noticias` (chave `agregador_noticias`, ícone `newspaper`) — `main.py:766-777` (`pagina_restrita("Agregador de Notícias", chave_modulo="agregador_noticias")` + `REGISTRO_MODULOS["agregador_noticias"] = page_agregador_noticias`); `/admin/agregador_noticias` — `main.py:896-906` (`eh_admin` + `ui.colors(primary=ler_tema("agregador_noticias"))` + `mostrar_administracao(nome)`; não-admin → `/agregador-noticias`). Slugs customizáveis via `/configuracoes` → aba Módulo (`rotas_modulos.montar_rotas_ativas()`).
- Auditoria: `audit_log` (núcleo) → `mod_auditoria` banco exclusivo `db_mod_auditoria.db`, tabela `tb_auditoria_agregador_noticias` (`configurar` `habilitado`/`intervalo_min`/`termo_pesquisa`/`fontes_json`/`temas_json`, `coletar` `N novas`, `limpar_antigas` `N removidas`).
- Backup do banco: job `backup:agregador_noticias` (`backup_horas:agregador_noticias` default 12h, `MAPA_BACKUPS` inclui `agregador_noticias: db_mod_agregador_noticias.db`).
- **Agendadores** (`mod_intranet/rotinas.py`): `agregador_coleta` (`rotinas.py:228-240` `BackgroundScheduler` `interval minutes=intervalo_min()` — `coletar_todas` se `habilitado()`, senão skip; `reconfigurar_agregador_noticias()` `:256-277` `pause/resume` + `reschedule minutes` sem restart) + `agregador_limpeza` (`rotinas.py:243-253` `interval hours=24` `limpar_antigas(24)`).
- Cadastro central: `MODULOS_SISTEMA` (`autenticacao.py:25` → `("agregador_noticias","Agregador de Notícias","newspaper","/agregador-noticias")`), `MODULOS_BD` (`repositorio.py:68` → `agregador_noticias: db_mod_agregador_noticias.db`), `PADROES_TEMA["agregador_noticias"]` (`tema_modulo.py:82` → `#000000`), `PREFIXO_POR_CHAVE["agregador_noticias"]` → `agregador_noticias`.
- **Integração TV — Filas** (`mod_filas/telas.py:72-137` `mostrar_tv`): `carregar_noticias()` (`telas.py:103-119`) chama `listar_para_tv(limite=10)` (`agregador_noticias.bd_manipulador:232-242` `SELECT titulo,descricao,url,imagem_url,fonte,tema ORDER BY data_coleta DESC LIMIT ?` → `[{"titulo","descricao":desc or titulo,"url","imagem","fonte","tema"}]`) e exibe carrossel no rodapé da TV (`card bg-grey-900` `min-height:18vh` com `lbl_n_titulo` `text-[1.6vw]`, `lbl_n_desc` `text-[1vw]`, `lbl_n_fonte` `text-caption`) com `ui.timer(7.0, _mostrar_noticia)` (rotaciona `idx % len`) + `ui.timer(120.0, carregar_noticias)` (recarrega lista a cada 2 min); `habilitado()==False` → `"Agregador desabilitado — ative em /admin/agregador_noticias"`; vazio → `"Nenhuma notícia ainda — aguarde coleta"`. `refresh_chamada()` (senha/guichê) segue em `ui.timer(3.0)`.

## Testes

```bash
# Smoke do módulo (import + init_db + CRUD + coleta desabilitada)
.venv/bin/python -c "from mod_agregador_noticias.bd_manipulador import init_db, contar_noticias, listar_noticias, habilitado, intervalo_min; init_db(); print(habilitado(), intervalo_min(), contar_noticias()); print(listar_noticias()[:1])"
# Coleta manual (requer habilitado + internet)
.venv/bin/python -c "from mod_agregador_noticias.bd_manipulador import definir_habilitado, definir_intervalo, coletar_todas; definir_habilitado(True, ator='master'); print(coletar_todas(ator='master'))"
# TV
.venv/bin/python -c "from mod_agregador_noticias.bd_manipulador import listar_para_tv; print(listar_para_tv(3))"
# Playwright (quando coberto)
.venv/bin/pytest assets/test/teste_agregador_noticias.py -k agregador
```

Ver [Análise do Módulo](../analise_mod_agregador_noticias.md) e [Arquitetura](../arquitetura.md).

## Pontos de atenção

- **Habilitado por padrão `0`**: instalação limpa não coleta até o admin habilitar em `/admin/agregador_noticias` (switch + `reconfigurar_agregador_noticias` sem restart; `agregador_coleta` é `pause` quando desabilitado).
- **Intervalo clamp 10–360**: `intervalo_min()`/`definir_intervalo` garantem mín. 10 min / máx. 6 h (`360`); admin select limita a `10/30/60/120/180/360` mas API aceita qualquer `10–360`.
- **Fontes ao vivo**: `fontes_json` é editável sem restart; `adicionar` valida `url` não vazia e gera `nome` fallback `url[:30]`; `remover` é por índice com `refresh`.
- **Limpeza 24/24h**: `limpar_antigas(24)` roda **duas vezes** — ao fim de `coletar_todas` + job diário `agregador_limpeza` (`interval hours=24`); `DELETE WHERE data_coleta < datetime('now','-24 hours')` é portável (traduzido para `LOCALTIMESTAMP` no `banco_conexao` Postgres proxy).
- **Deduplicação**: `url UNIQUE` + `INSERT OR IGNORE` — segunda coleta da mesma URL não duplica; `INSERT OR IGNORE` vira `ON CONFLICT DO NOTHING` no Postgres.
- **`bd_criador.py` morto** — nunca executar; schema real é `init_db()` do `bd_manipulador`.
- **Dependências**: `httpx` + `parsel` (`requirements.txt`); sem internet `_get_html` retorna `""` e coleta resulta `0` (fail-soft com `warning` loguru).
