# Tela Pura de Notícias — `mod_agregador_noticias/telas_puro.py` (`/agregador-noticias-puro`)

> Deep analysis of the pure screen: route `/agregador-noticias-puro` (key `agregador_noticias`, same gate as `/agregador-noticias`) · reuses `db_mod_agregador_noticias.db` `tb_noticia` via `listar_noticias(limite=12)` `ORDER BY COALESCE(data_publicacao, data_coleta) DESC` · replicates the visual model of `klaytonPrinceMS/Noticia` (`intro-overlay` + `about` section with `tema` + `info-list` `ul`) with the current cards · original CSS/JS/images in `assets/noticia/` served by `main.py:818` `@app.get("/assets/noticia/{caminho:path}")` (path-traversal safe) · 145 lines, no pagination, no own database.

---

# Tela Pura de Notícias — `mod_agregador_noticias/telas_puro.py` (`/agregador-noticias-puro`)

> Análise profunda da tela pura: rota `/agregador-noticias-puro` (chave `agregador_noticias`, mesmo gate de `/agregador-noticias`) · reutiliza `db_mod_agregador_noticias.db` `tb_noticia` via `listar_noticias(limite=12)` `ORDER BY COALESCE(data_publicacao, data_coleta) DESC` · replica o modelo visual do repositório `klaytonPrinceMS/Noticia` (`intro-overlay` + seção `about` com `tema` + `info-list` `ul`) com os cards atuais · CSS/JS/imagens originais em `assets/noticia/` servidos por `main.py:818` `@app.get("/assets/noticia/{caminho:path}")` (seguro contra path-traversal) · 145 linhas, sem paginação, sem banco próprio.

## Propósito

Segunda porta de entrada do **Agregador de Notícias**, com o **layout do modelo
`Noticia`** (`https://github.com/klaytonPrinceMS/Noticia`, `gerarSite`): um
**overlay de abertura** (`intro-overlay`, fundo escuro, chamada `PRINCE. K,B.`) e
uma **seção `about`** com `info-list` em `ul`. O diferencial é que a "casca" é a
do `Noticia`, mas o **conteúdo dos cards é o atual do Agregador** (ícone da fonte,
miniatura, badge de tema, título clicável, descrição e tempo relativo) — não
há replicação do *fetch* do repositório original.

O módulo entrega **duas telas complementares**:

| Tela | Rota | Arquivo | Papel |
|:---|:---|:---|:---|
| Principal | `/agregador-noticias` | `mod_agregador_noticias/telas.py` | Grid paginado 3→2→1, busca global, filtro de tema, "Coletar agora" |
| **Pura** | `/agregador-noticias-puro` | `mod_agregador_noticias/telas_puro.py` | Apresentação/TV, sem filtros, 12 notícias fixas, CSS `Noticia` |

!!! info "Acesso por URL direta"
    O botão *"Ver puro Noticia"* (`agregador-ver-puro`) foi **removido** de
    `/agregador-noticias` em 20/09/2026. A tela pura é acessada **digitando a URL
    `/agregador-noticias-puro`** — útil para TVs, vídeos de apresentação e
    Tablets fixos.

## Banco de dados (reuso — nenhum banco novo)

A tela pura **não tem `bd_manipulador.py` próprio nem banco próprio**: reusa o
`db_mod_agregador_noticias.db` do módulo, lendo pela **mesma** função da tela
principal.

| Item | Valor |
|:---|:---|
| Banco | `db_mod_agregador_noticias.db` (chave `agregador_noticias`) |
| Tabela | `tb_noticia` |
| Função | `ag.listar_noticias(limite=12)` — `mod_agregador_noticias/bd_manipulador.py:314-325` |
| Ordenação | `ORDER BY COALESCE(data_publicacao, data_coleta) DESC, data_coleta DESC` |
| Colunas consumidas | `fonte_icon_url` (16×16 `contain`), `imagem_url` (30×30 `cover`), `tema`, `titulo`, `url`, `descricao`, `data_publicacao`, `data_coleta`, `fonte` |
| Escrita | **nenhuma** — a tela pura é read-only |

!!! note "O redesenho do card (25/09/2026) NÃO atingiu esta tela"
    O redesenho do card de `/agregador-noticias` (miniatura `30×30` → **`120×120`
    ampliável em diálogo**, descrição truncada `desc[:160]…` → **texto completo**,
    card de **altura fixa** `300px`, logo da fonte como **marca d'água `32×32`**)
    foi feito **apenas em `mod_agregador_noticias/telas.py`**. O
    `mod_agregador_noticias/telas_puro.py` **não foi alterado** e **continua
    exatamente como está documentado aqui**: miniatura `30×30` `cover`, ícone de
    fonte `16×16` `contain` e `desc[:160] + "…"`.

    Isso é deliberado: a tela pura é uma **réplica fiel do modelo visual
    `klaytonPrinceMS/Noticia`**, e o CSS original (`base.css`/`vendor.css`/`main.css`)
    define o tamanho dos itens da `info-list`. Alterar o tamanho da miniatura ali
    quebraria a fidelidade ao modelo de referência. Se a tela pura for
    reprojetada no futuro, esta página precisa ser atualizada **junto** — não
    assuma que ela acompanha o card da tela principal. Detalhes do redesenho em
    [Agregador de Notícias — Fluxo da tela](analise_mod_agregador_noticias.md#fluxo-da-tela).

Detalhe completo do schema em
[Agregador de Notícias — Banco próprio](analise_mod_agregador_noticias.md#banco-proprio)
e em [Resumo do módulo](modulos/agregador_noticias.md).

## Funcionalidades — `telas_puro.py:mostrar_tela_pura`

### Docstring bilíngue (`telas_puro.py:1-8`)

```python
"""EN: Pure Aggregator display — original Noticia style (gerarSite) with current cards.

PT-BR: Tela pura do Agregador — estilo original Noticia (gerarSite) com cards atuais.
Copia o padrão de exibição do repositório https://github.com/klaytonPrinceMS/Noticia
(intro overlay, about section com tema, info-list) porém com os cards em uso
(tema badge + tempo relativo, título link, descrição, miniatura 30×30 + ícone fonte 16×16).
CSS/JS originais em assets/noticia/ são servidos via rota estática /assets/noticia/*.
"""
```

### Anatomia da função (`telas_puro.py:48-145`)

| Passo | Linhas | O que faz |
|:---|:---|:---|
| **Gate de acesso** | `48-58` | `perfil_global == "administrador_geral"` **ou** `autenticacao.validar_acesso_modulo(user_nome, "agregador_noticias")`. Sem acesso → `ui.icon("block", size="64px")` + `ui.label("Acesso restrito")` e `return` — **mesmo gate** de `telas.py:_pode_ver` |
| **CSS/JS no `<head>`** | `60-71` | `ui.add_head_html` com 5 `<link rel="stylesheet">` (`base.css`, `vendor.css`, `main.css`, `font-awesome`, `micons`) + `<link rel="icon" href="/assets/noticia/favicon.png">` + 2 `<script>` (`modernizr.js`, `pace.min.js`) |
| **Tema** | `73-75` | `ler_tema("agregador_noticias", cor_botao="#000000", cor_texto_botao="#FFFFFF", texto_header="Exibição pura do modelo Noticia — intro + lista info-list, com cards atuais")` + `ui.colors(primary=tema["cor_botao"])` |
| **Dados** | `78` | `noticias = ag.listar_noticias(limite=12)` — **12 mais recentes**, sem filtro de tema, sem busca, sem paginação |
| **`intro-overlay`** | `81-92` | `section` `w-full` com `style("background:#111417;color:#fff;padding:2rem 0;")` + `div.intro-overlay` (vazio — o fundo é do `Noticia`) + `div.intro-content` (`row` / `col-twelve`) com `PRINCE. K,B.` (`text-caption tracking-widest`), `DTI - Notícias` (`text-h2 font-bold`), `Pref. Municipal — Agregador puro` (`text-subtitle2 opacity-80`) e dois botões `outline color=white`: **`Início`** (`ui.navigate.to("/agregador-noticias")`) e **`Fim`** (`window.scrollTo(0, document.body.scrollHeight)`) |
| **`about` + `info-list`** | `95-131` | `section` `w-full bg-white py-8` + `div.row section-intro` (`col-twelve`) com `Principais notícias` (`text-h6 tracking-widest text-grey-6`) + `Tema: Todos • N notícias (3 colunas atuais dentro do modelo puro)` (`text-h5 font-bold`) + `div.row about-content` (`col-six tab-full`) + `ul.info-list` com um `li.border-b py-3` por notícia |
| **Rodapé `Noticia`** | `133-139` | `footer` `w-full bg-grey-900 text-white py-6 mt-8` + `row` com `copyright` `© Copyright DTI — Agregador puro (Noticia) — Design by Klayton` e, à direita, `ui.link("Voltar ao topo", target="#top")` |
| **JS no rodapé da função** | `141-145` | `ui.add_head_html` com `jquery-2.1.3.min.js`, `plugins.js`, `main.js` |

### Anatomia do card (`li` do `info-list`)

Cada notícia vira um `li.border-b py-3` com **duas linhas** — a primeira é a
"linha de metadados", a segunda a "linha de conteúdo":

```text
[fonte_icon 16×16] [badge tema] [tempo relativo]            [fonte]  ← ml-auto
[imagem 30×30] [título (ui.link, new_tab)]                          ← flex-1
[descrição[:160]…]
[href[:60]…  (font-mono)]
[Abrir no site original →]
```

| Elemento | Detalhe |
|:---|:---|
| `fonte_icon` | `ui.image(fonte_icon)` `16×16` `object-fit:contain` + `shrink-0 rounded`; dentro de `try/except` (fail-soft) |
| `badge tema` | `ui.label(tema_n or "Geral")` `text-caption font-bold bg-grey-2 px-2 py-0.5 rounded` |
| Tempo relativo | `_tempo_relativo(data_pub or data_col)` `text-caption text-grey-5` |
| Fonte | `ui.label(fonte or "")` `ml-auto` — **aqui a fonte textual aparece**, ao contrário do card da tela principal (que a removeu) |
| `imagem` | `ui.image(img)` `30×30` `object-fit:cover` + `shrink-0 rounded`; `try/except` |
| Título | `ui.link(titulo, target=href, new_tab=True)` `font-bold text-grey-9 hover:text-primary flex-1` com `word-break: break-word` |
| Descrição | `desc[:160] + "…"` quando maior — renderizada **só se** `desc` existir **e** for diferente do `titulo` |
| URL crua | `href[:60] + "…"` em `font-mono text-grey-5` (reconhecível para o usuário) |
| Link de saída | `ui.html('<span><a href="{href}" target="_blank" ...>Abrir no site original →</a></span>')` — único `ui.html` cru da tela |

!!! warning "`ui.html` cru é a exceção consciente"
    A tela pura injeta a âncora "Abrir no site original" via `ui.html` com
    interpolação de `href`. O `href` vem de `tb_noticia.url` — que é
    **normalizada** em `inserir_noticia` (`[:2000]`, `/` relativo → base
    `https://news.google.com`, valores `/api/attachments` relativos → `""`).
    Ainda assim, é o **único ponto** do módulo onde um valor de banco entra em
    HTML sem passar por `nh3`/escape. Ao adicionar novos campos interpolados
    neste bloco, use escape ou componente do NiceGUI.

### Helper `_tempo_relativo(s)` (`telas_puro.py:19-45`)

Versão **simplificada** do helper homônimo de `telas.py:47-89`:

```python
t = str(s).strip().replace("T", " ").replace("Z", "")   # normaliza ISO
t = re.split(r"\.\d+", t)[0]                              # corta fração de segundo
for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
    dt = datetime.strptime(t[:19], fmt); break
```

| `delta` | Texto |
|:---|:---|
| `< 60` s | `agora` |
| `< 3600` s | `X minutos atrás` |
| `< 86400` s | `X horas atrás` |
| `< 604800` s | `X dias atrás` |
| `>= 604800` s | `X semanas atrás` |
| Formato não reconhecido | `t[:16]` (fallback) |

Toda a função é `try/except` e devolve `(s or "")[:16]` em falha.
**Diferença em relação a `telas.py`**: aqui **não existem** os patamares de
*mês* e *ano* (2.592.000 s / 31.536.000 s) — notícias com mais de 7 dias caem
em "semanas atrás" (ou no fallback de 16 caracteres).

## Rotas e assets servidos

### `main.py` — rota da tela

```python
@app.get("/agregador-noticias-puro")
def page_agregador_noticias_puro():
    """EN: Pure news screen (Noticia layout). PT-BR: Tela pura de notícias (layout Noticia)."""
    from mod_intranet.ui_comum import pagina_restrita
    pagina_restrita("Agregador de Notícias — Puro", chave_modulo="agregador_noticias")
    ...
    mostrar_tela_pura(nome, perfil)
```

O gate real está **duas camadas**: `pagina_restrita(...)` (autenticação + perfil)
e, dentro de `mostrar_tela_pura`, a checagem de **acesso ao módulo**
(`validar_acesso_modulo(..., "agregador_noticias")`).

### `main.py:818-831` — rota estática dos assets do `Noticia`

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

**Três garantias**:

1. **Anti path-traversal** — `os.path.normpath` resolve `..` e o
   `startswith(os.path.abspath(base))` rejeita qualquer caminho que escape da
   base. `/assets/noticia/../../etc/passwd` → **404**.
2. **Existência** — `os.path.isfile` antes de servir; diretório ou ausente → **404**.
3. **MIME correto** — `mimetypes.guess_type` (`text/css`, `application/javascript`,
   `font/woff2`, `image/png`…), com fallback `application/octet-stream`.

### Conteúdo de `assets/noticia/` (4,9 MB, originais do `Noticia`)

| Grupo | Arquivos |
|:---|:---|
| CSS | `css/base.css`, `css/vendor.css`, `css/main.css`, `css/fonts.css` |
| Ícones | `css/font-awesome/css/font-awesome.min.css` + `fonts/FontAwesome.*`, `css/micons/micons.css` + `fonts/icomoon.*` |
| Fontes | `css/fonts/lora/…`, `css/fonts/poppins/…` (`woff`/`ttf`/`eot`/`svg`) |
| Imagens | `images/bg.jpg`, `images/intro-bg.jpg` |
| JS | `js/jquery-2.1.3.min.js`, `js/modernizr.js`, `js/pace.min.js`, `js/plugins.js`, `js/main.js` |
| Ícone do site | `favicon.png` |

!!! note "`assets/noticia/` não é documentação"
    É **asset de runtime**: é servido pela rota acima em runtime e **não entra no
    `nav` do `mkdocs.yml`** como página. `mkdocs build --strict` continua com
    **0 warnings** por causa dele.

## Permissões

| Ação | `comum` com `agregador_noticias` | `administrador_modulo` / `administrador_geral` | Sem acesso |
|:---|:---:|:---:|:---:|
| Ver `/agregador-noticias-puro` (intro + `info-list` com 12 cards) | ✓ | ✓ | ✗ — `block` 64px + "Acesso restrito" |
| Coletar / configurar / censurar | ✗ | ✓ (só no admin `/admin/agregador_noticias`) | ✗ |
| `GET /assets/noticia/*` | público (rota **sem** gate; os arquivos só carregam se o caminho for conhecido) | — | — |

!!! danger "`/assets/noticia/*` é público"
    A rota estática **não** valida sessão. Como o conteúdo é apenas CSS/JS/
    fontes/imagens do projeto de código aberto `klaytonPrinceMS/Noticia`, não há
    vazamento de dados — mas **qualquer arquivo** colocado em `assets/noticia/`
    passa a ser servido sem autenticação. Nunca coloque lá segredos, dumps ou
    arquivos de módulo.

## Integrações

- **Dados** — `mod_agregador_noticias.bd_manipulador.listar_noticias(limite=12)`
  (mesmo caminho da tela principal; **nenhuma** query própria).
- **Autenticação** — `mod_intranet.autenticacao.validar_acesso_modulo` +
  `mod_intranet.tema_modulo.ler_tema` (`ler_tema` também lê a cor do botão do
  tema do Agregador, então a personalização do admin **vale** aqui).
- **Assets** — `main.py:818` `servir_assets_noticia` (rota estática do núcleo).
- **NÃO** usa `mod_intranet.integracoes` (a tela pura é intra-módulo) e **NÃO**
  escreve nada — `audit_log` não registra visualizações.
- **TV Filas** — não tem relação direta: a TV consome
  `listar_para_tv(limite=200)` pelo `integracoes.listar_noticias_para_tv()`.
  A tela pura **não** interfere no carrossel.
- **Censura** — a filtragem de palavras bloqueadas acontece na **origem**
  (`inserir_noticia` descarta título censurado) e em `listar_para_tv`; a tela pura
  lê `listar_noticias`, que já não recebe conteúdo censurado. Detalhes em
  [Censura compartilhada](analise_mod_agregador_noticias.md#censura-de-conteudo-palavras-bloqueadas-central-mod_intranetcensurapy).

## Diferenças em relação à tela principal

| Aspecto | `/agregador-noticias` | `/agregador-noticias-puro` |
|:---|:---|:---|
| Layout | Grid CSS próprio, 3→2→1 colunas | `intro-overlay` + `about`/`info-list` do `Noticia` |
| CSS | Tailwind/Quasar do NiceGUI | `assets/noticia/*` (originais) via `add_head_html` |
| Notícias por página | **12** com **paginação** (4 botões) | **12 fixas**, sem paginação |
| Filtro de tema | `agregador-filtro-tema` | Não (rótulo fixo `Tema: Todos`) |
| Busca | `agregador-busca` (`debounce 300`, global) | Não |
| Fonte textual no card | **Removida** | **Presente** (`ml-auto`) |
| Botão "Coletar agora" | Sim (admin, `run.io_bound`) | Não |
| Botão "Abrir notícia" | Removido (título `ui.link` basta) | Link de texto `Abrir no site original →` |
| Botão de entrada | — | `Início` (volta à principal) / `Fim` (rola ao fim) |
| Escrita / auditoria | Nenhuma na tela | Nenhuma |

## Pontos de atenção

- **Sem paginação** — `listar_noticias(limite=12)` fixo. Para uma TV de saguão
  com rolagem contínua, as 12 notícias trocam de ordem conforme a coleta
  recicla o banco (reinício diário).
- **Rota de assets pública** — ver a caixa de atenção acima.
- **`ui.html` com `href` interpolado** — único HTML cru da tela (ver a caixa de
  warning acima).
- **`_tempo_relativo` simplificado** — sem meses/anos (ao contrário de `telas.py`).
  Duas implementações do mesmo conceito em arquivos diferentes: qualquer regra
  nova precisa ser aplicada **nas duas**.
- **`sys.path.insert` no topo do arquivo** (`telas_puro.py:10-11`) — o arquivo
  se auto-localiza para import direto em script; dentro da aplicação NiceGUI
  (importada por `main.py`) é redundante, mas inofensivo.
- **Docstring e o resto do código divergem do padrão do resto do projeto**:
  imports em linha (`import sys, os, re`), `__import__("datetime")` dentro da
  função em vez de import no topo, e ausência de `try/except` em
  `mostrar_tela_pura` (apenas o gate e as imagens têm proteção). Não é uma
  violação do AGENTS.md §3.2 no caminho exercitado, mas **é** a tela com menor
  defesa do módulo — qualquer `ag.listar_noticias`/`ler_tema` que estoure cai no
  topo.
- **Sem `bd_criador.py` próprio** — usa o do módulo
  (`mod_agregador_noticias/bd_criador.py`, legado/morto; o schema real é
  `bd_manipulador.py:init_db()`).
- **Dependências** — `httpx` + `parsel` (coleta, não a tela); a tela pura não
  adiciona dependência Python alguma.

## Testes

```bash
# Import + contrato da função
.venv/bin/python -c "from mod_agregador_noticias.telas_puro import mostrar_tela_pura; print(mostrar_tela_pura.__doc__[:80])"

# Leitura dos 12 cards a partir do banco real
.venv/bin/python -c "from mod_agregador_noticias import bd_manipulador as ag; print(len(ag.listar_noticias(limite=12)))"

# Assets do Noticia presentes
ls assets/noticia/css/base.css assets/noticia/css/vendor.css assets/noticia/css/main.css \
   assets/noticia/js/jquery-2.1.3.min.js assets/noticia/js/modernizr.js \
   assets/noticia/js/pace.min.js assets/noticia/js/plugins.js assets/noticia/js/main.js \
   assets/noticia/favicon.png

# Rota estática (com o sistema no ar)
curl -I http://localhost:8080/assets/noticia/css/base.css           # 200 text/css
curl -I http://localhost:8080/assets/noticia/js/jquery-2.1.3.min.js # 200 application/javascript
curl -I http://localhost:8080/assets/noticia/../../etc/passwd        # 404 (anti-traversal)

# Playwright — tela pura por URL direta (botão agregador-ver-puro removido 20/09/2026)
.venv/bin/pytest assets/test/test_e2e_agregador_noticias.py
```

## Status

| Item | Situação |
|:---|:---|
| Rota `/agregador-noticias-puro` com `pagina_restrita` + gate de módulo | Implementado (`main.py` + `telas_puro.py:48-58`) |
| `intro-overlay` + `about`/`info-list` do modelo `Noticia` com cards atuais | Implementado (`telas_puro.py:81-131`) |
| Reuso do banco do módulo (`listar_noticias(limite=12)`, sem banco novo) | Implementado |
| CSS/JS/imagens originais servidos por `main.py:818` (anti-traversal) | Implementado |
| Rodapé `Noticia` + `Voltar ao topo` + botões `Início`/`Fim` | Implementado (`telas_puro.py:133-139`) |
| Acesso por URL direta (botão `agregador-ver-puro` removido 20/09/2026) | Implementado |
| Filtro de tema / busca / paginação na tela pura | **Fora de escopo por decisão** (existem só na tela principal) |
| Escrita / auditoria na tela pura | **Não aplicável** (read-only) |

## Referências

- [Agregador de Notícias — análise](analise_mod_agregador_noticias.md) · [Resumo](modulos/agregador_noticias.md)
- [Tela Pura — resumo do módulo](modulos/agregador_noticias_puro.md)
- [Filas (TV) — carrossel de notícias](analise_mod_filas.md) · [Resumo](modulos/filas.md)
- [Censura de conteúdo compartilhada](analise_mod_agregador_noticias.md#censura-de-conteudo-palavras-bloqueadas-central-mod_intranetcensurapy)
