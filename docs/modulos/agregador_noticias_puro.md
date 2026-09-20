# Pure News Screen — `mod_agregador_noticias/telas_puro.py` (`/agregador-noticias-puro`)

> Pure display screen: route `/agregador-noticias-puro` (key `agregador_noticias`, same gate as `/agregador-noticias`) · reuses `db_mod_agregador_noticias.db` `tb_noticia` (`fonte_icon_url` 16×16 + `imagem_url` 30×30) via `listar_noticias(limite=12)` `ORDER BY COALESCE(data_publicacao, data_coleta) DESC` · copies display pattern from `https://github.com/klaytonPrinceMS/Noticia` (`intro-overlay` + `about` section with `tema` + `info-list` `ul`) but with current cards (3-column, `fonte_icon 16×16` `contain` + `imagem 30×30` `cover` before title, `badge tema` + `title ui.link(new_tab=True)` + `descricao[:160]` + `tempo relativo` + external link) · original `assets/noticia/` (`base.css`, `vendor.css`, `main.css`, `font-awesome/css/font-awesome.min.css`, `micons/micons.css`, `fonts/lora/poppins`, `images/bg.jpg/intro-bg.jpg`, `js/modernizr.js/pace.min.js/jquery-2.1.3.min.js/plugins.js/main.js`, `favicon.png` 4.9M) served via `main.py:818` `@app.get("/assets/noticia/{caminho:path}")` (path-traversal safe `normpath` + `startswith(base)` + `mimetypes.guess_type` → `FileResponse`, `404` if outside base) · access via button `Ver puro Noticia` `data-testid=agregador-ver-puro` (`ui.navigate.to("/agregador-noticias-puro")`) on `/agregador-noticias` · `intro-content` `PRINCE. K,B.` + `DTI - Notícias` + buttons `Início` (`/agregador-noticias`) / `Fim` (`window.scrollTo(0, document.body.scrollHeight)`) · `about-content` `info-list` with `12` most recent news (`COALESCE DESC`) · footer `© Copyright DTI`.

---

# Tela Pura de Notícias — `mod_agregador_noticias/telas_puro.py` (`/agregador-noticias-puro`)

> Tela pura de notícias: rota `/agregador-noticias-puro` (chave `agregador_noticias`, mesmo gate de `/agregador-noticias`) · reutiliza `db_mod_agregador_noticias.db` `tb_noticia` (`fonte_icon_url` 16×16 + `imagem_url` 30×30) via `listar_noticias(limite=12)` `ORDER BY COALESCE(data_publicacao, data_coleta) DESC` · copia padrão de exibição do repositório `https://github.com/klaytonPrinceMS/Noticia` (`intro-overlay` + `about` com `tema` + `info-list` `ul`) porém com cards atuais (3 colunas, `fonte_icon 16×16` `contain` + `imagem 30×30` `cover` antes do título, `badge tema` + `título ui.link(new_tab=True)` + `descrição[:160]` + `tempo relativo` + link externo) · originais `assets/noticia/` (`base.css`, `vendor.css`, `main.css`, `font-awesome/css/font-awesome.min.css`, `micons/micons.css`, `fonts/lora/poppins`, `images/bg.jpg/intro-bg.jpg`, `js/modernizr.js/pace.min.js/jquery-2.1.3.min.js/plugins.js/main.js`, `favicon.png` 4.9M) servidos via `main.py:818` `@app.get("/assets/noticia/{caminho:path}")` (seguro path-traversal `normpath` + `startswith(base)` + `mimetypes.guess_type` → `FileResponse`, `404` se fora da base) · acesso via botão `Ver puro Noticia` `data-testid=agregador-ver-puro` (`ui.navigate.to("/agregador-noticias-puro")`) em `/agregador-noticias` · `intro-content` `PRINCE. K,B.` + `DTI - Notícias` + botões `Início` (`/agregador-noticias`) / `Fim` (`window.scrollTo(0, document.body.scrollHeight)`) · `about-content` `info-list` com `12` mais recentes (`COALESCE DESC`) · rodapé `© Copyright DTI`.

## Propósito

Tela **pura** que replica fielmente o **modelo visual do repositório `Noticia`** (`https://github.com/klaytonPrinceMS/Noticia` — `gerarSite` com `intro overlay`, `about section` com `tema`, `info-list` `ul`), mas **reutiliza os cards atuais do Agregador** (3 colunas, `fonte_icon_url` `faviconV2` `16×16` `contain` + `imagem_url` `/api/attachments` `30×30` `cover` lado a lado antes do título, `badge tema`, `ui.link(target=href, new_tab=True)`, `descrição`, `tempo relativo` `_tempo_relativo` via `data_publicacao` real ou `data_coleta` fallback). O **CSS/JS original** do Noticia foi **copiado para `assets/noticia/`** e é **servido via rota estática `main.py:818` `@app.get("/assets/noticia/{caminho:path}")`** — `base.css`/`vendor.css`/`main.css`/`font-awesome`/`micons`/`fonts`/`js`/`images`/`favicon.png` 4.9M. O acesso à tela pura é via **botão `Ver puro Noticia`** (`visibility` `contorno` `data-testid=agregador-ver-puro` → `ui.navigate.to("/agregador-noticias-puro")`) na barra de `/agregador-noticias` (mesmo gate `validar_acesso_modulo(user, "agregador_noticias")`).

> Status: **ativa** (rota `/agregador-noticias-puro` `page_agregador_noticias_puro` + `assets/noticia/` servido via `servir_assets_noticia` + `telas_puro.py:mostrar_tela_pura` com `intro` + `about` + `info-list` + footer Noticia, cards atuais 3 colunas).

## Banco de dados (reuso)

Reusa o mesmo `db_mod_agregador_noticias.db` / `tb_noticia` de `/agregador-noticias` — ver [Agregador de Notícias](./agregador_noticias.md#banco-de-dados) (`fonte_icon_url` `faviconV2` `16×16` + `imagem_url` `30×30`, `COALESCE(data_publicacao, data_coleta) DESC`). A tela pura chama `ag.listar_noticias(limite=12)` (ordenação `COALESCE DESC`, 12 mais recentes, sem paginação) e exibe `fonte_icon` + `imagem` + `tempo relativo` com o mesmo `listar_noticias` do agregador principal.

## Funcionalidades — `telas_puro.py:mostrar_tela_pura`

### Docstring bilíngue (`telas_puro.py:1-8`)

```python
"""Tela pura do Agregador — estilo original Noticia (gerarSite) com cards atuais.

EN: Pure display — original Noticia style with current cards.
Copia o padrão de exibição do repositório https://github.com/klaytonPrinceMS/Noticia
(intro overlay, about section com tema, info-list) porém com os cards em uso
(tema badge + tempo relativo, título link, descrição, miniatura 30×30 + ícone fonte 16×16).
CSS/JS originais em assets/noticia/ são servidos via rota estática /assets/noticia/*.
"""
```

### `mostrar_tela_pura(user_nome, perfil_global)` (`telas_puro.py:48-145`)

| Passo | Código | Detalhe |
|:---|:---|:---|
| **Gate** | `telas_puro.py:48-58` | `administrador_geral` ou `validar_acesso_modulo(user, "agregador_noticias")` — sem acesso → `block` 64px + "Acesso restrito" (mesmo gate de `telas.py:_pode_ver`). |
| **Injeção CSS/JS head** | `telas_puro.py:60-71` | `ui.add_head_html` com 5 `<link rel="stylesheet" href="/assets/noticia/css/base.css">`, `vendor.css`, `main.css`, `font-awesome/css/font-awesome.min.css`, `micons/micons.css`, `<link rel="icon" href="/assets/noticia/favicon.png">`, `<script src="/assets/noticia/js/modernizr.js">`, `pace.min.js` — servidos via `main.py:818` `servir_assets_noticia`. |
| **Tema** | `telas_puro.py:73-75` | `ler_tema("agregador_noticias", cor_botao="#000000", texto_header="Exibição pura do modelo Noticia — intro + lista info-list, com cards atuais")` + `ui.colors(primary=tema["cor_botao"])`. |
| **Dados** | `telas_puro.py:78` | `noticias = ag.listar_noticias(limite=12)` `ORDER BY COALESCE(data_publicacao, data_coleta) DESC` — 12 mais recentes (sem filtro tema/busca, sem paginação). |
| **Intro overlay puro Noticia** | `telas_puro.py:81-92` | `section.w-full` `background:#111417;color:#fff;padding:2rem 0;` + `div.intro-overlay` + `div.intro-content` `row` `col-twelve` com `label PRINCE. K,B.` `text-caption tracking-widest` + `label DTI - Notícias` `text-h2 font-bold` + `label Pref. Municipal — Agregador puro` `text-subtitle2 opacity-80` + `row gap-2 mt-4` com `ui.button "Início"` (`ui.navigate.to("/agregador-noticias")`, `outline color=white`) + `ui.button "Fim"` (`ui.run_javascript("window.scrollTo(0, document.body.scrollHeight)")`). |
| **About section + info-list com cards atuais** | `telas_puro.py:94-131` | `section.w-full bg-white py-8` + `div.row section-intro` `col-twelve` com `Principais notícias` `text-h6 tracking-widest text-grey-6` + `Tema: Todos • N notícias (3 colunas atuais dentro do modelo puro)` `text-h5 font-bold` + `div.row about-content` `col-six tab-full` + `ul.info-list` com `for nid,titulo,fonte,tema_n,url,img,fonte_icon,desc,data_pub,data_col in noticias` por `li.border-b py-3` com **linha `fonte_icon 16×16` + `badge tema` + `tempo _tempo_relativo(data_pub or data_col)` + `fonte ml-auto` + `row` `imagem 30×30` + `ui.link(titulo, target=href, new_tab=True)`** + `descricao[:160]…` `text-caption text-grey-7` + `href[:60]…` `font-mono` + `ui.html('<span><a href="{href}" target="_blank" style="color:#0066cc;">Abrir no site original →</a></span>')`. |
| **Footer puro Noticia** | `telas_puro.py:133-139` | `footer.w-full bg-grey-900 text-white py-6 mt-8` `row` `col-six tab-full` `copyright` `© Copyright DTI — Agregador puro (Noticia) — Design by Klayton` + `col-six tab-full text-right` `ui.link("Voltar ao topo", target="#top")`. |
| **JS rodapé** | `telas_puro.py:141-145` | `ui.add_head_html` com `<script src="/assets/noticia/js/jquery-2.1.3.min.js">`, `plugins.js`, `main.js`. |
| **Helper `_tempo_relativo(s)`** | `telas_puro.py:19-45` | Normaliza `T`/`Z`/fração (`re.split(r"\.\d+", t)`), `for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d")` `strptime`, `delta = agora - dt` → `agora` (<60 s) / `X minutos atrás` (<3600) / `X horas atrás` (<86400) / `X dias atrás` (<604800) / `X semanas atrás` else fallback `[:16]` (versão simplificada de `telas.py:_tempo_relativo` sem meses/anos). |

### Rota estática `assets/noticia/` (`main.py:818-831`)

```python
@app.get("/assets/noticia/{caminho:path}")
def servir_assets_noticia(caminho: str):
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "noticia")
    caminho_abs = os.path.normpath(os.path.join(base, caminho))
    if not caminho_abs.startswith(os.path.abspath(base)):
        return Response(status_code=404)
    if not os.path.isfile(caminho_abs):
        return Response(status_code=404)
    import mimetypes
    mime, _ = mimetypes.guess_type(caminho_abs)
    mime = mime or "application/octet-stream"
    return FileResponse(caminho_abs, media_type=mime)
```

- **Segurança**: `os.path.normpath` + `startswith(os.path.abspath(base))` bloqueia `../` (path-traversal) → `404`; arquivo inexistente → `404`.
- **MIME**: `mimetypes.guess_type` (`text/css` para `.css`, `application/javascript` para `.js`, `font/woff2` etc).
- **Conteúdo** (`assets/noticia/` 4.9M): `css/base.css`, `vendor.css`, `main.css`, `font-awesome/css/font-awesome.min.css` + `fonts/FontAwesome.*`, `micons/micons.css` + `fonts/icomoon.*`, `fonts.css`, `fonts/lora/poppins` `woff/ttf/eot/svg` `stylesheet.css`, `images/bg.jpg` `intro-bg.jpg`, `js/jquery-2.1.3.min.js` `modernizr.js` `pace.min.js` `plugins.js` `main.js`, `favicon.png` — **originais do Noticia**, copiados verbatim por `kbp-web-design` (não entram no `mkdocs.yml` nav, mas são servidos em runtime).

## Permissões

| Ação | `comum` com `agregador_noticias` | `administrador_modulo`/`administrador_geral` | Sem acesso |
|:---|:---:|:---:|:---:|
| Ver `/agregador-noticias-puro` (intro Noticia + about `info-list` + 12 cards atuais) | ✓ | ✓ | ✗ ("Acesso restrito") |
| Acesso via botão `Ver puro Noticia` em `/agregador-noticias` (`data-testid=agregador-ver-puro`) | ✓ | ✓ | — |
| Rota estática `/assets/noticia/*` (CSS/JS/fonts/images) | público (sem gate, mas arquivos só acessíveis se souber o caminho) | — | — |

Gate `/agregador-noticias-puro`: mesmo de `/agregador-noticias` — `validar_acesso_modulo(user, "agregador_noticias")` ou `administrador_geral`.

## Rota e integrações

- **Rotas**: `/agregador-noticias-puro` (`main.py:808-815` `page_agregador_noticias_puro` `pagina_restrita("Agregador de Notícias — Puro", chave_modulo="agregador_noticias")` + `mostrar_tela_pura(...)` `telas_puro.py:48-145`); `/assets/noticia/{caminho:path}` (`main.py:818-831` `servir_assets_noticia`); `/agregador-noticias` com botão `Ver puro Noticia` (`telas.py:184` `data-testid=agregador-ver-puro` → `/agregador-noticias-puro`).
- **Integração com `/agregador-noticias`**: botão `Ver puro Noticia` (`visibility`, `contorno`, `data-testid=agregador-ver-puro`, `ui.navigate.to("/agregador-noticias-puro")`) na barra de filtro+busca de `telas.py:184` — visível a todos com acesso ao Agregador.
- **Auditoria**: nenhuma específica da tela pura (mesma regra do Agregador — só `quem alterou o quê` em `bd_manipulador.py` `definir_*`/`reiniciar_banco`, sem audit de visualização).
- **TV Filas**: `listar_para_tv` continua fornecendo dados à TV (a tela pura não afeta o carrossel).

Ver [Agregador de Notícias](./agregador_noticias.md) (tela principal 3 colunas + busca) e [Análise do Agregador](../analise_mod_agregador_noticias.md).

## Testes

```bash
# Smoke do módulo puro (import + listar_noticias + assets)
.venv/bin/python -c "from mod_agregador_noticias.telas_puro import mostrar_tela_pura; print(mostrar_tela_pura.__doc__[:80])"
.venv/bin/python -c "from mod_agregador_noticias.bd_manipulador import listar_noticias; print(len(listar_noticias(limite=12)))"
# assets/noticia — verificar arquivos copiados
ls assets/noticia/css/base.css assets/noticia/css/vendor.css assets/noticia/css/main.css assets/noticia/js/jquery-2.1.3.min.js assets/noticia/js/modernizr.js assets/noticia/js/pace.min.js assets/noticia/js/plugins.js assets/noticia/js/main.js assets/noticia/favicon.png
# Rota estática — iniciar servidor e curl
curl -I http://localhost:8080/assets/noticia/css/base.css  # 200 text/css
curl -I http://localhost:8080/assets/noticia/js/jquery-2.1.3.min.js  # 200 application/javascript
# Playwright — botão Ver puro Noticia
.venv/bin/pytest assets/test/teste_agregador_noticias.py -k "puro or busca or pure"  # cobre agregador-ver-puro
```

## Pontos de atenção

- **Não é página MkDocs**: `assets/noticia/` é **asset de runtime** (CSS/JS/fonts/images originais `klaytonPrinceMS/Noticia` 4.9M) servido via `main.py:818` `@app.get("/assets/noticia/{caminho:path}")` — **não entra no `mkdocs.yml` nav** como doc, mas é servido em runtime; `mkdocs build --strict` continua 0 warnings.
- **Segurança da rota estática**: `servir_assets_noticia` normaliza com `os.path.normpath(os.path.join(base, caminho))` e verifica `startswith(os.path.abspath(base))` — bloqueia `../` (ex.: `/assets/noticia/../../etc/passwd` → `404`); `mimetypes.guess_type` define `media_type` correto.
- **Gate igual ao Agregador**: a tela pura reutiliza `validar_acesso_modulo(user, "agregador_noticias")` — usuário sem acesso ao Agregador não vê nem a principal nem a pura.
- **12 notícias sem paginação**: a tela pura exibe `listar_noticias(limite=12)` `COALESCE DESC` (12 mais recentes, sem filtro tema/busca, sem paginação `Primeira/Anterior/Próxima/Última`); a busca/filtro permanece só em `/agregador-noticias`.
- **Cards com `fonte_icon 16×16` + `imagem 30×30` + tempo relativo**: mesmos `fonte_icon_url` `faviconV2` `16×16` `contain` + `imagem_url` `30×30` `cover` do `tb_noticia` (extraídos via `//img[contains(@src,'faviconV2')]` vs `/api/attachments` ancestral `div[1..3]`), `badge tema` + `ui.link(new_tab=True)` + `descricao[:160]` + `tempo relativo` `_tempo_relativo` (`agora`/minutos/horas/dias/semanas).
- **`bd_criador.py` morto**: schema real `bd_manipulador.py:209-250` `init_db()` (`fonte_icon_url` `faviconV2`).
- **Dependências**: `httpx` + `parsel` (`requirements.txt`); `assets/noticia/` 4.9M não adiciona dependência Python.
