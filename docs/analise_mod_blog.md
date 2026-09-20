# Blog — `mod_blog`

> Corporate blog module: route `/blog` (key `blog`) · own database `db_mod_blog.db` · HTML sanitized with nh3 · read-only for common users · central LGPD audit.

---

# Blog — `mod_blog`

> Módulo de blog corporativo: rota `/blog` (chave `blog`) · banco próprio `db_mod_blog.db` · HTML sanitizado com nh3 · somente-leitura para usuário comum · auditoria central LGPD.

## Propósito

Blog corporativo com postagens e comentários em HTML sanitizado por `nh3`. Regra central: usuário `comum` tem acesso **somente leitura** — publicar, comentar e excluir são restritos ao administrador geral e ao administrador do módulo `blog`, validados na UI **e** no backend. Exclusão de postagem é lógica (`ativo=0`).

## Banco próprio

Criador vigente: `init_db()` em `bd_manipulador.py:96-143` (bootstrap central).

- **`tb_postagens`**: id PK, titulo, conteudo (gravado sanitizado), autor, data_criacao, data_atualizacao, `ativo` (soft delete / publicar-despublicar).
- **`tb_comentarios`**: id PK, postagem_id FK CASCADE → tb_postagens, autor, conteudo (sanitizado), data_criacao.
- **`tb_config` (local do módulo)**: `blog_modo_exibicao`, `blog_postagem_unica_id`, `blog_largura_imagem`, `blog_tags_permitidas`, `blog_texto_header`, `blog_habilitar_mermaid`, `blog_carrossel_tempo` (segundos por slide, padrão 10), `blog_carrossel_postagens_ids` (CSV de ids exibidos no modo carrossel).

⚠️ O `bd_criador.py` do blog é **legado/morto**: conecta no banco **central**, duplica os CRUDs com bugs próprios (sanitização sem whitelist, ordenação sem efeito) e importa `audit_log` sem chamar.

## Fluxo da tela

- Editor "Nova publicação/Edition" (Título*, Conteúdo* — HTML simples/Markdown aceito e sanitizado) com **pré-visualização** e botão Publicar/Salvar: **somente admins**. Permite criar e **editar** postagem existente.
- Todos veem lista de postagens ativas em ordem cronológica DESC (modo **histórico**), **ou** apenas uma postagem (modo **única** — a fixada via seletor "Postagem exibida", ou a mais recente quando nada está fixado), **ou** um **carrossel** rotativo (modo **carrossel** — postagens selecionadas pelo admin, exibidas uma por vez com rotação automática, resumo e leitura completa), alternável na tela e persistido em config local.
- Cada card: título, autor, data, conteúdo injetado via `ui.html` **re-sanitizado**, comentários em `ui.expansion` com contador.
- Campo de comentário apenas para admins; comum lê "Somente administradores podem comentar." Exclusão de postagem só por admin; botões de **editar**, **despublicar** e **excluir** via `ui_comum.botao_icone` com `chave_modulo="blog"` (rodapé do card, row `w-full justify-end` com `gap: 0.25rem`).
- **Busca no feed (visível a usuários e administradores)**: `campo_busca` ("Buscar por título, conteúdo ou autor...") + `campo_texto` "Data (AAAA-MM-DD)" (`w-44`) + seletor de modo, numa `ui.row` `.style("gap: 0.5rem; margin-top: 0.5rem")` FORA do `if pode_publicar:` (`telas.py:353-402`); `atualizar()` filtra em memória por termo (título/conteúdo/autor, case-insensitive) e por data (`data_criacao` startswith) antes da lógica do modo única (`telas.py:427-447`); mensagem vazia distingue "Nenhuma publicação encontrada." (busca ativa) de "Nenhuma publicação ainda." (`telas.py:450-457`).

## Regras de negócio relevantes

- **Dupla camada de permissão**: UI esconde controles e backend valida em toda escrita (`criar/atualizar/excluir_postagem`, `criar_comentario` → `autenticacao.pode_publicar_no_blog`).
- **Sanitização nh3 na gravação E na renderização** — whitelists **alinhadas**: ambas usam `tags_permitidas()` (CSV de `blog_tags_permitidas`, config local com fallback na central). Atributos essenciais permitidos (`a[href]`, `img[src/alt/title/width/height]`, `class` em code/pre/blockquote); esquemas `http`/`https`/`data`/`mailto` + URLs relativas (`url_relative="pass_through"`) e `link_rel="noopener noreferrer"` (RF-32 **REALIZADO**). `div`/`br` (estrutura de linhas do QEditor) são **sempre** permitidas em `_sanitizar_texto()` (`bd_manipulador.py:499` — `tags_permitidas() | {"div", "br"}`, sem atributos), valendo também para bancos existentes cujo CSV ainda não lista `div`/`br`; o padrão `_TAGS_PADRAO` (`bd_manipulador.py:35`) já inclui `div,br` para instalações novas.
- **Formatos**: HTML simples **e** Markdown leve — `_markdown_leve()` (`bd_manipulador.py:720`) converte `#`/`##`/`###` → h1/h2/h3, `- `/`* ` → listas e `**negrito**` → `<b>` (sobre texto já escapado). **Markdown dentro do WYSIWYG**: o editor (`ui.editor`/QEditor) gera a **1ª linha solta** e as demais envoltas em **`<div>`** (não em `<p>`), mas `div`/`br` não eram tags permitidas — o nh3 arrancava as divs e colava todas as linhas, matando o Markdown. Correção: `_TAGS_PADRAO` += `div,br` (`bd_manipulador.py:35`) e `_sanitizar_texto()` garante `tags_permitidas() | {"div", "br"}` (`bd_manipulador.py:499`, sem atributos, vale p/ bancos existentes); o novo `_markdown_em_html()` (`bd_manipulador.py:790`) normaliza `<div>`→`<p>` e converte também a 1ª linha solta (`#`/`-` no início) antes dos estilos: `<p>#..</p>` → `<h1..3>`, `<p>- ..</p>` vizinhos → `<ul><li>`, `**x**` → `<b>` só em texto (nunca em atributos de tag), conteúdo de `code`/`pre` preservado intacto, sem falso positivo em `#hashtag`. **Regra mantida: `#` exige espaço** — `#texto` fica literal (padrão CommonMark, como no GitHub). Aplicado no ramo HTML de `formatar_conteudo_para_exibicao()` (`bd_manipulador.py:782`); a pré-visualização confirma o resultado.
- **Formatação rica** (RF-32): `formatar_conteudo_para_exibicao()` aplica estilos sobre o HTML sanitizado — h1/h2/h3 centralizados e em negrito, `<img>` flutuando à esquerda com limites min/max configuráveis (`blog_largura_imagem`, padrão 200–400 px, `loading=lazy`), texto justificado; texto puro/Markdown também é justificado. **`_FormatadorBlog` respeita o autor** (`bd_manipulador.py:653`): `float` ou margens `auto` do autor vencem o `float:left` padrão; `max-width` do autor dispensa os limites padrão (inclusive o `min-width`, que estouraria larguras em % pequenas); sem estilo do autor, o padrão 200–400 px à esquerda é mantido.
- **Modo de exibição**: histórico completo **ou** publicação única — `obter_modo_exibicao()` lê `blog_modo_exibicao` da config local; alternável na tela (persistido + auditado). No modo única, a postagem exibida pode ser **fixada** por id (`blog_postagem_unica_id`, config local): `obter_postagem_unica_id()` (`bd_manipulador.py:559`) devolve o id ou `None` (ausente/inválido = mais recente, fallback automático); `definir_postagem_unica_id(pid)` (`bd_manipulador.py:573`) fixa/limpa (`None`/`""` limpa). O seletor "Postagem exibida (modo única)" (`telas.py:395`) só aparece no modo única, lista as postagens ativas (`""` = "Mais recente (automática)") e, se a fixada sair da lista (despublicada/excluída), o feed volta silenciosamente para a mais recente (`telas.py:440-447`). Ao **criar** nova publicação a fixação é limpa (`telas.py:310`) — a nova passa a ser a exibida. Trocas de modo/fixação auditadas (`audit_reg`) e com reload.
- **Gestão de despublicadas**: aba Administração lista postagens inativas (`listar_postagens(ativo=False)`) com botão **Republicar** (`publicar_postagem`).
- Soft delete: postagens inativas saem da lista pública; comentários só são removidos fisicamente por cascade quando a postagem é deletada fisicamente (fluxo da limpeza cruzada do módulo de usuários).

## Censura de conteúdo — palavras bloqueadas (central `mod_intranet/censura.py`)

Funcionalidade compartilhada Blog ↔ Agregador (chave única `conteudo_palavras_bloqueadas` em `tb_config` central):

- **Núcleo** (`censura.py:1-95`): `CHAVE_CONFIG="conteudo_palavras_bloqueadas"` · `obter_palavras_bloqueadas()` (split `,;\n` + JSON fallback, `lower`) · `definir_palavras_bloqueadas(lista, ator)` (normaliza `lower` dedup, grava CSV via `set_config`, `audit_log` `censura/palavras_bloqueadas`) · `titulo_bloqueado(titulo, palavras=None)` / `filtrar_titulo` → `(bloqueado, palavra)` com `_normalizar` `lower+NFD` semacentos (`suicidio` bloqueia `suicídio`, substring insensível) — docstring bilíngue EN/PT-BR.
- **Blog** (`bd_manipulador.py:646-703`): `criar_postagem` e `atualizar_postagem` verificam `titulo_bloqueado(titulo)` **antes** de `nh3`; se bloqueado retornam `None`/`False` com `warning` + `notificar("Título contém palavra bloqueada: '...'")` e não sanitizam/gravam.
- **Agregador** (`bd_manipulador.py:353-396` `inserir_noticia` descarta se bloqueado; `280-303` `listar_para_tv` filtra `LIMIT*3` → `titulo_bloqueado`; `306-334` `limpar_censuradas()` remove já coletadas censuradas).
- **Admin Blog** (`telas_administracao.py:72-106`): card `Censura de conteúdo — palavras bloqueadas` (`block`, `data-testid=blog-palavras-bloqueadas`, `textarea` CSV/;/linha, `Salvar censura` `data-testid=blog-salvar-censura` + `Restaurar`, ao salvar `definir_palavras_bloqueadas` + `limpar_censuradas` do agregador).
- **Admin Agregador** (`mod_agregador_noticias/telas_administracao.py:177-223`): mesmo card (`data-testid=agregador-palavras-bloqueadas`) + botão `Remover já censuradas agora` (`data-testid=agregador-limpar-censuradas`, `limpar_censuradas()`).
- **Normalização**: `lower` + `NFD` remove `Mn` → `suicidio` bloqueia `suicídio`; substring (não exige palavra inteira).

## Integrações com o núcleo

Importa `autenticacao.pode_publicar_no_blog` e `eh_admin_do_modulo`. Grava na trilha via `audit_log` (banco exclusivo `db_mod_auditoria.db`, tabela `tb_auditoria_blog`) para criar/alterar/despublicar/republicar/excluir postagens e comentários. Config de aparência na `tb_config` central (prefixo `blog_*`); config de comportamento na `tb_config` LOCAL do módulo. Consumido pelo núcleo: bootstrap cria o banco, scheduler faz backup e o dashboard usa `contar_postagens(ativo=True)`. Censura via `mod_intranet/censura.titulo_bloqueado` + chave central `conteudo_palavras_bloqueadas`.

## Pontos de atenção

- O `bd_criador.py` do blog é **legado/morto**: conecta no banco central e duplica os CRUDs com sanitização sem whitelist — não executar.
- Comentários só são removidos fisicamente por cascade quando a postagem é deletada fisicamente (fluxo da limpeza cruzada do módulo de usuários).

## Status — Fase 3 do PLANO.md

| Item | Situação |
|:---|:---|
| Banco WAL + CRUD com soft delete | Implementado |
| Sanitização nh3 (gravação + renderização) | Implementado (whitelists alinhadas via `tags_permitidas()`; aceita `data:`/relativas p/ imagens) |
| Somente-leitura para `comum` (UI + backend) | Implementado |
| Exibição de postagens/comentários | Implementado |
| Auditoria (banco exclusivo `db_mod_auditoria.db`, tabela `tb_auditoria_blog`) | Implementado |
| `tb_config` local (modo/largura de imagem) | **Implementado** (tabela `tb_config` do módulo) |
| Permitir `data:`/URLs relativas para imagens | **Implementado** (`url_schemes`/`url_relative`) |
| Formatação rica (títulos negrito/centralizados, imagens configuraveis) + Markdown | **REALIZADO (RF-32)** — `formatar_conteudo_para_exibicao()` aplica estilos; largura de imagem configurável |
| Exibição única OU histórico alternável | **Implementado** (`blog_modo_exibicao` local) + **fixação da postagem exibida** no modo única (`blog_postagem_unica_id` local, fallback automático p/ mais recente) |
| Editor com pré-visualização | **Implementado** (editor com preview, criar/editar) |
| Publicar/Despublicar + restauração de inativas | **Implementado** (aba "Despublicadas" da tela do blog — `telas.py:251,469`; o admin standalone `/admin/blog` não lista mais inativas desde 06/09) |
| `assets/test/teste_fluxo_blog.py` (46) | **Implementado** (em `assets/test/` — 46 verificações ✅) |

> Fase 3 **REALIZADO** e validado. O teste `assets/test/teste_fluxo_blog.py` (**46 verificações** ✅)
> cobre sanitização XSS (nh3), conversores HTML/Markdown, CRUD, publicar/
> despublicar, soft delete, config local, modo única/histórico, largura de
> imagem, modo carrossel e auditoria central. A checagem de auditoria foi atualizada para o
> banco exclusivo `db_mod_auditoria.db` (tabela `tb_auditoria_blog` — a
> `tb_auditoria` central virou legado, migrada via `migrar_dados_existentes`).

### Adições recentes (26/08)

- **Painel "Administração"** (exclusivo do admin do blog): bloco **Aparência** (prefixo blog_* — cor do botão/texto, tamanho via ui.color_input) e **config específica**: blog_tags_permitidas (CSV das tags HTML aceitas na sanitização NH3, aplicada via tags_permitidas()), blog_texto_header. Salvo via set_config, vale sem reiniciar.
- **Versionamento**: versao_modulo:blog = 1.0.260908 (seed em bd_conexao.init_db()), exibido no rodapé em /blog.
- **Edição do módulo** (`campo_modulo` do helper `mod_intranet/tema_modulo.py`) — **REMOVIDO (06/09)**: editar **nome de exibição, ícone e status (ativo/inativo)** do blog é agora **exclusivo do painel central `/configuracoes`** (aba Módulo, admin geral).

### Adições recentes (06/09) — admin dividido em "Configurações de cores" + "Configurações específicas"

- **`../mod_blog/telas_administracao.py` reescrito** no padrão dos demais módulos: o card "Configurações do Blog" foi dividido em **"Configurações de cores"** (via `tema_modulo.bloco_aparencia` — card padrão com prévia ao vivo, `com_texto_header=False` — `telas_administracao.py:69`) + **"Configurações específicas"** (tags HTML permitidas, largura de imagem, texto do cabeçalho e o switch de diagramas Mermaid — `telas_administracao.py:73-167`), cada um com rodapé padrão de 2 botões ("Restaurar padrão" + "Aplicar") exclusivos do card e recarga após 1 s.
- **Removido o card "Postagens despublicadas (gestão)"** da aba de administração — a gestão de despublicadas continua na aba **"Despublicadas"** da própria tela do blog (`telas.py:251,469` → `_painel_despublicadas`, `telas.py:173-209`).
- **`mostrar_administracao` retorna cedo** se `pode_publicar` for falso (`telas_administracao.py:51-52`) — sem renderizar nada para não-admin.
- Mantidos: card padrão de backup (`painel_backup`, `telas_administracao.py:171-172`) e o card "Configurações de cores".

### Adições recentes (06/09) — fixação da postagem no modo única

- **Escolher qual postagem exibir no modo "Publicação única"**: antes o modo `unica` exibia sempre a mais recente; agora é possível **fixar o id** da postagem exibida.
  - Nova chave local `blog_postagem_unica_id` (seed idempotente em `bd_manipulador.py:138`, default `""` = mais recente).
  - Helpers `obter_postagem_unica_id()` (`bd_manipulador.py:559` — retorna `int` ou `None`; valor inválido = fallback automático para a mais recente) e `definir_postagem_unica_id(pid)` (`bd_manipulador.py:573` — `None`/`""` limpa).
  - Seletor do modo migrado de `ui.select` cru para `ui_comum.campo_selecao` (`telas.py:369-377`); novo `campo_selecao` **"Postagem exibida (modo única)"** (`telas.py:395-402`), visível só no modo `unica`, com opção `""` = "Mais recente (automática)" ou `#id — título` (truncado em 60 caracteres + reticências) de cada postagem ativa.
  - Feed (`atualizar()`, `telas.py:442-447`): no modo única filtra pelo id fixado; se a fixada não estiver entre as ativas (despublicada/excluída), exibe a mais recente silenciosamente.
  - Ao **criar** nova publicação a fixação é limpa (`telas.py:310`) — a nova passa a ser a exibida.
  - Trocas de modo/fixação auditadas (`audit_reg`) e com reload (padrão da tela); row dos seletores usa `.style("gap: 0.5rem")` (`telas.py:351-352`) — regra bug #2171 (sem `gap-2` Tailwind em `ui.row`).
  - "Restaurar padrão" da Administração também limpa `blog_postagem_unica_id` (`telas_administracao.py:153`), além de `blog_modo_exibicao=historico`.
  - Testes: 4 novos asserts em `assets/test/teste_fluxo_blog.py` (#30–33: default `None`, fixar/obter, limpar, seed da chave) — agora **46 verificações** ✅.

### Adições recentes (06/09) — busca no feed e correções de bugs

- **Despublicar/excluir corrigidos**: `_despublicar`/`_excluir` (`telas.py:132,146`) passavam autor `""` ao banco → `_pode_publicar("")` = False → ação silenciosa (sem notificação). Agora recebem `usuario_logado` e notificam **negativo** quando a operação retorna False (`telas.py:139,153`) — com try/except + loguru.
- **Editar corrigido**: `ao_editar` (`telas.py:331-338`) chamava `ui.scroll_to(selector=None)` — API inexistente no NiceGUI 3.15 → AttributeError no handler (o formulário não era preenchido de forma confiável). Substituído por `ui.run_javascript("window.scrollTo({top:0, behavior:'smooth'})")` (`telas.py:336-337`).
- **Botões de ação → `ui_comum.botao_icone`** (padrão Gestão de Usuários): editar (`edit`), despublicar (`visibility_off`) e excluir (`delete`), todos com tooltip e `chave_modulo="blog"`, em row `w-full justify-end` `.style("gap: 0.25rem; margin-top: 0.25rem")` no rodapé do card (`telas.py:79-94`).
- **Busca no feed**: ver bullet acima (Fluxo da tela) — `telas.py:353-402` (barra) e `telas.py:427-457` (filtro + mensagem vazia).
- Removidos `if pode_publicar or True:` e imports não usados (`set_config`, `get_config_local`).
- Testes: `teste_fluxo_blog` **46 ✅**, `verifica_ui_comum` **188/188**, `test_dashboard` **31/31**; verificação headless confirmou que o clique em Editar preenche o formulário (título no input `Título*`) e que despublicar/excluir zeram o `ativo`.

### Adições recentes (06/09) — suporte a diagramas Mermaid nas postagens

- **Diagramas Mermaid nas postagens**: blocos ```mermaid ... ``` no conteúdo viram diagramas renderizados via `ui.mermaid` (bundle embutido do NiceGUI 3.15, **sem CDN**). O texto ao redor continua formatado normalmente; um diagrama inválido exibe o rótulo "(diagrama inválido)" sem derrubar a tela.
  - **`../mod_blog/bd_manipulador.py`**: nova constante `_FENCE_MERMAID` (regex ```mermaid ... ```, `bd_manipulador.py:52`), `obter_habilitar_mermaid()` (`bd_manipulador.py:55` — lê `blog_habilitar_mermaid` da config local, default `'1'`; valores `'0'`/`'false'`/`'off'` desabilitam; falha de leitura cai em habilitado com warning no loguru) e `extrair_segmentos_mermaid(conteudo)` (`bd_manipulador.py:68` — divide o conteúdo sanitizado em tuplas `('texto'|'mermaid', trecho)`, revertendo entidades HTML via `html.unescape`). Import `re` adicionado no topo.
  - **`mod_blog/telas.py`**: nova `_renderizar_conteudo_postagem(conteudo)` (`telas.py:17`) — texto via `formatar_conteudo_para_exibicao`/`ui.html`, mermaid via `ui.mermaid(...).classes("w-full my-2").style("overflow-x: auto")`; fallback para texto quando o recurso está desabilitado e label "(diagrama inválido)" em falha de renderização (try/except + loguru). `_card_postagem` (`telas.py:50`) e `atualizar_preview` (`telas.py:272`) passaram a usá-la; o placeholder do textarea cita ```mermaid (`telas.py:265-267`).
  - **`../mod_blog/telas_administracao.py`**: novo `ui.switch` **"Permitir diagramas Mermaid (```mermaid) nas postagens"** no card "Configurações específicas" (`telas_administracao.py:106-112`); salvar/restaurar persistem `blog_habilitar_mermaid` (`'1'`/`'0'` — `telas_administracao.py:126-127,153`).
  - **Config**: nova chave local `blog_habilitar_mermaid` (seed idempotente `'1'` em `bd_manipulador.py:140`).
  - **Teste**: novo `test/teste_viabilidade_mermaid.py` — script standalone (Playwright headless) que valida a renderização de `ui.mermaid` (NiceGUI 3.15, bundle embutido sem CDN) e o caminho real do blog (postagem com bloco mermaid): **5/5 verificações OK**. Execute: `.venv/bin/python test/teste_viabilidade_mermaid.py`.

### Adições recentes (07/09) — seed de postagens "Como usar"

- **Novo script de seed `test/criar_postagens_blog.py`**: insere **3 postagens de guia de uso** voltadas ao usuário comum — *Editor de PDF — Como usar*, *Solicitação de Impressão — Como usar* e *Empenhos — Como usar* — no banco `db_mod_blog.db`. Cada postagem inicia com um **fluxograma Mermaid** (```mermaid) e traz seções *Como usar*, *Dicas* e *Limites/Status*.
- **Reutiliza `criar_postagem`** (`bd_manipulador.py:271`) com autor `master` — herda sanitização nh3, validação de permissão e auditoria do módulo (sem duplicar lógica de escrita).
- **Robustez**: `main()` (`criar_postagens_blog.py:120`) com docstring EN+PT-BR e **try/except + loguru** — cada postagem é tratada isoladamente (falha em uma não interrompe as demais, fail-soft) e registrada no arquivo dedicado `logs/blog_<data>.log` via `_log()` (`criar_postagens_blog.py:20`).
- **Execução**: `source .venv/bin/activate && python test/criar_postagens_blog.py` (idempotente por natureza — cada execução cria novas postagens; não há deduplicação por título).

### Adições recentes (07/09) — semeadura automática + barra de ações do carrossel

- **Semeadura automática em banco novo** (`bd_manipulador.py`): a função `_sembrar_postagens_padrao` foi **renomeada para `_semear_postagens_padrao`** (`bd_manipulador.py:205` — termo português correto). As 3 postagens padrão (`POSTAGENS_PADRAO`, `bd_manipulador.py:104`) tiveram o conteúdo **reordenado**: o **texto vem primeiro** e o **fluxograma ```mermaid por último** (antes o diagrama abria a postagem). A semeadura agora define `data_criacao` = **momento de criação do banco** (`datetime.now` local, `bd_manipulador.py:217`), um **único timestamp compartilhado** por todas as postagens, em vez do `DEFAULT CURRENT_TIMESTAMP` por linha. Chamada por `init_db` (`bd_manipulador.py:290`) apenas quando a tabela está vazia (idempotente).
- **Barra de ações do carrossel no topo E no rodapé** (`mod_blog/telas.py`): `_renderizar_carrossel` (`telas.py:239`) refatorou a barra de ações em função interna **`barra_acoes()`** (`telas.py:287`), renderizada **duas vezes** — no topo do card (`telas.py:330`) e no rodapé (`telas.py:337`). Contém navegação (anterior/próxima via `botao_icone`), indicador **"atual/total"** e o botão **"Leitura completa"**/**"Voltar ao carrossel"** (que pausa/retoma a rotação automática). Motivo: fixar a leitura cedo em postagens longas (topo) e trocar de postagem sem voltar ao topo (rodapé).

### Adições recentes (07/09) — modo de exibição "carrossel"

- **Novo modo de exibição "carrossel"** (além de `historico` e `unica`): o administrador seleciona **2 ou mais postagens** e define o **tempo de rotação** (padrão 10 s, configurável). As postagens são exibidas **uma por vez** com rotação automática, navegação manual (Anterior/Próximo) e expansão para leitura completa (que **pausa** a rotação). Em estado normal o card mostra um **resumo** (recorte em até 3 linhas) e o botão **"Leitura completa"** expande a postagem inteira.
- **`../mod_blog/bd_manipulador.py`**:
  - Constantes `AUTOR_PADRAO` (`"master"`, `bd_manipulador.py:99`) e `POSTAGENS_PADRAO` (`bd_manipulador.py:104`) — as 3 postagens de guia "Como usar" (Editor de PDF, Solicitação de Impressão, Empenhos), cada uma com fluxograma Mermaid no início.
  - `_semear_postagens_padrao(cur)` (`bd_manipulador.py:205`) — insere as postagens padrão **apenas em banco recém-criado** (tabela vazia), chamada por `init_db()` (`bd_manipulador.py:290`); idempotente e com try/except + loguru.
  - Novas configs locais semeadas no `init_db`: `blog_carrossel_tempo` (`"10"`) e `blog_carrossel_postagens_ids` (`""`) (`bd_manipulador.py:277-278`).
  - Novas funções: `obter_carrossel_tempo` (`bd_manipulador.py:729`), `definir_carrossel_tempo` (`bd_manipulador.py:741`), `obter_carrossel_postagens_ids` (`bd_manipulador.py:753`), `definir_carrossel_postagens_ids` (`bd_manipulador.py:774`) e `listar_postagens_por_ids` (`bd_manipulador.py:795` — ordena pela seleção, imune a injeção via placeholders `?`).
  - `obter_modo_exibicao()` agora aceita `'carrossel'` (`bd_manipulador.py:692`).
- **`mod_blog/telas.py`**:
  - `_resumo_conteudo(conteudo, limite=220)` (`telas.py:215`) — extrai resumo em texto puro (remove HTML/Markdown/Mermaid, substitui ```mermaid por "[diagrama]", trunca com reticências); try/except + loguru.
  - `_renderizar_carrossel(...)` (`telas.py:239`) — monta o carrossel: `ui.timer` com rotação, barra de ações no topo e rodapé, card resumido quando não expandido e `_card_postagem` completo quando expandido; navegação com `aria-label` e guarda de estado expandido no timer; try/except + loguru.
  - Bloco administrativo no modo carrossel (`telas.py:546-596`): `ui.select` múltiplo das postagens + `ui.number` do tempo, com auditoria; **reverte a seleção** se o admin tentar selecionar exatamente 1 postagem (aviso "Selecione ao menos 2 postagens para o carrossel.").
  - `atualizar()` trata o modo carrossel (`telas.py:684-694`) — lista apenas as postagens selecionadas via `listar_postagens_por_ids`.
- **Testes**:
  - `assets/test/teste_fluxo_blog.py`: isolamento do banco (reatribuição de `bd._crud` para banco temporário) + nova função `teste_carrossel` (7 verificações) validando o modo carrossel.
   - `assets/test/teste_carrossel_blog.py`: teste headless que renderiza a tela em modo carrossel e valida o DOM (indicador de posição, botão Leitura completa, select de postagens, tempo, expansão).

### Adições recentes (09/2026) — responsividade global RNF-UI-01

- **Já responsivo** — filtros justificados (`flex-wrap` `gap` via `.style`), exibição centralizada (`w-full justify-center`), seleção em lote com `grid mobile-first`; dialogs `w-full max-w`. Auditado 320/768/1024 (`kbp-web-design`) com checklist P0/P1/P2 e proposta por `container`/`row`/`grid` (cards `grid-cols-1 sm:grid-cols-2`). Ver [Padrões](padroes_codificacao/index.md) §8.1.

### Adições recentes (14/09/2026) — correção Markdown no editor WYSIWYG (`div`/`br` + 1ª linha solta)

- **Causa raiz**: o QEditor gera a **1ª linha solta** e as demais em `<div>`, mas `div`/`br` não eram tags permitidas — o nh3 arrancava as divs e colava todas as linhas, matando o Markdown (a saída real do editor nunca rendia `h1`/`h2`/`h3`).
- **Mudanças em `mod_blog/bd_manipulador.py`**: `_TAGS_PADRAO` += `div,br` (`:35`); `_sanitizar_texto()` garante `tags_permitidas() | {"div", "br"}` (`:499`, sem atributos — vale p/ bancos existentes); `_markdown_em_html()` (`:790`) normaliza `<div>`→`<p>` e converte a 1ª linha solta (`#`/`-` no início).
- **Regra mantida: `#` exige espaço** (`#texto` fica literal, padrão CommonMark como no GitHub).
- **Validação (sistema reiniciado, Playwright real — `/login` 200, preview com `h1`/`h2`/`h3`)**: saída real do editor rende `h1`/`h2`/`h3` centralizados; suíte `assets/test/teste_fluxo_blog.py` **46/46**.

### Adições recentes (14/09/2026) — Markdown no WYSIWYG + controles da imagem

- **Markdown dentro do WYSIWYG (`mod_blog/bd_manipulador.py`)**: o editor envolve tudo em `<p>`, então `#`/`-`/`**` digitados nunca caíam no `_markdown_leve` (só texto puro) e apareciam literais no feed. Novo `_markdown_em_html()` (`bd_manipulador.py:786`) converte dentro dos blocos HTML antes dos estilos: `<p># Título</p>` → `<h1..3>`, `<p>- item</p>` vizinhos → `<ul><li>`, `**x**` → `<b>` só em texto (nunca em atributos de tag), conteúdo de `code`/`pre` preservado intacto, sem falso positivo em `#hashtag`. Aplicado no ramo HTML de `formatar_conteudo_para_exibicao()` (`bd_manipulador.py:778`). O placeholder do editor continua citando Markdown (agora verdadeiro) e a pré-visualização confirma o resultado antes de publicar.
- **Controles da imagem (`mod_blog/telas.py`, card "Nova publicação")**: o `ui.editor` (QEditor) **não** tem redimensionar/alinhar imagem nativo — nova linha **"Imagem:"** (`telas.py:629`) com 3 botões (`blog-img-esq`/`blog-img-centro`/`blog-img-dir`, `format_align_left/center/right`) + seletor **"Largura da imagem"** (`blog-img-largura`: 25%/50%/75%/100%/Original 200–400px, default `100%`). Aplicados por `_ajustar_imagem(alinhamento, largura)` (`telas.py:564`) à **ÚLTIMA `<img>`** do texto: reescreve só as props de layout do `style` (`float`, `margin`, `display`, `max/min-width`), preserva o restante do CSS do autor e o outro eixo quando só um muda (alinhamento atual via `float`/`margin auto`, largura atual via `max-width`); avisa (`warning`) se não há imagem no texto. `_FormatadorBlog` respeita o autor (ver bullet Formatação rica acima).
- **Validação (sistema reiniciado, Playwright real + `/login` 200)**: upload → centro → 50% → publicar rendeu no feed `float:right`/`max-width:50%` **sem** `float:left` (caso direita) e centro rende `display:block;margin:auto`; suíte `assets/test/teste_fluxo_blog.py` **46/46**; posts de QA excluídos (soft, `ativo=0`).

### Adições recentes (14/09/2026) — editor WYSIWYG + imagens nas postagens

- **Card "Nova publicação": `ui.textarea` trocado por `ui.editor` (WYSIWYG Quasar)** (`mod_blog/telas.py:519`) — barra de ferramentas de formatação nativa; `placeholder` de boas-vindas com o nome de tratamento (`Olá, <nome>! ...`, via `autenticacao.nome_de_tratamento` com fallback para o login — `telas.py:515-523`); `data-testid=blog-conteudo` mantido. Fluxos **publicar/cancelar/editar/pré-visualizar inalterados**.
- **Linha de upload de imagem** (`telas.py:551-562`): `ui.upload` ("Selecionar imagem (JPG/PNG, até 5 MB)", `auto_upload=False`, `max_file_size=5 MB`, `accept=.jpg,.jpeg,.png`, `data-testid=blog-imagem-selecionar`) + botão **Enviar** (`run_method("upload")`, `variante="secundario"`, `data-testid=blog-imagem-enviar`). Ao receber (`_receber_imagem`, `telas.py:527`), salva via `salvar_imagem_postagem` e insere no editor a tag `<img src="/img_postagens/<nome>" style="max-width:100%;height:auto;">`; falha de validação vira `notify` negativa sem derrubar a tela.
- **`mod_blog/bd_manipulador.py`**: `PASTA_IMAGENS = mod_blog/img_postagens/` (`:397`, dentro do módulo — regra de ouro); `salvar_imagem_postagem(nome_original, conteudo, usuario)` (`:410`) — só `.jpg`/`.jpeg`/`.png`, máx 5 MB, valida **assinatura do arquivo** (JPEG `FFD8`, PNG `89504E47`), nome padrão `dataHora_usuario` = `AAMMDDHHMM_login` (login normalizado para `[a-z0-9_-]`, máx 40 chars) + sufixo `_N` em colisão; retorna `(True, nome)` ou `(False, motivo)`. `expirar_imagens_orfas(minutos=5)` (`:446`) — remove arquivos com `mtime` > 5 min **não referenciados** em nenhum `conteudo` de `tb_postagens` (órfãs de uploads não concretizados). `_ATTRS["img"]` (`:388`) passa a aceitar `class` (CSS online/frameworks) + `style` (CSS local, sanitizado pelo nh3).
- **Serviço estático + limpeza**: `mod_blog/__init__.py:montar_rotas_static()` serve `img_postagens/` em `/img_postagens/*` (mesmo padrão de `tema_css.montar_rotas_static`), montada no boot pelo `main.py:138-144`; `mod_intranet/rotinas.py:353-406` — job `cleanup_blog_imagens` a cada **1 min** chama `expirar_imagens_orfas()`.
- **Validação (sistema reiniciado, Playwright real + backend `/login` 200)**: upload real via navegador gerou `2609141308_qamaster.png` + tag inserida no editor; post publicado **manteve `src`/`style`/`class` após o nh3** e renderizou no feed; `GET /img_postagens` **200 `image/png`**; órfã com `mtime` retroativo **removida** e imagem referenciada **preservada**; post de teste excluído (soft, `ativo=0`).

### Adições recentes (14/09/2026) — adequação das postagens-guia à auditoria (números reais)

- **Motivo**: auditoria das 3 postagens-guia apontou rótulos genéricos e fluxos divergentes das telas reais. `mod_blog/bd_manipulador.py:POSTAGENS_PADRAO` (`:113-208`) foi **reescrito** mantendo o PADRÃO ÚNICO (`# **Título**`, `### subtítulo`, seções em **negrito** com listas, ```mermaid ao fim).
- **Editor de PDF**: números reais — até **10 arquivos / 1024 MB por vez**, expiração automática em **10 min** (ajustável pelo admin), cota de **1 GB** (**10 GB** global); cita **Verificar integridade**, coluna **Expira em** (contagem regressiva), badges `#` de ordem do Juntar, recusas nominais do lote e modos **Reduzir** (Leve/Agressivo, qualidade/DPI) e **Dividir** (4 modos). Mermaid com rótulos reais e sem nó duplicado.
- **Solicitação de Impressão**: **Pedido único (grupo)** com N arquivos e status único (não mais "solicitação separada"); status **Pendente** incluído (sem responsável vinculado); **marca d'água só na impressão** (opcional, configurada pelo admin); tipo de papel via select + aviso **"(trazer)"** (Fotográfico/Vergê); campos **cópias, papel, cor, frente e verso, borda, observações**; **limite de pedidos abertos** e **cota em páginas**; fluxo **Autorização → Reenviar → Admin (imprime e confirma)**. Mermaid com ramo pendente e "admin imprime e confirma".
- **Empenhos**: sem "aba Pesquisar" (busca **integrada no Navegar**); inversão corrigida — **solicitar envio livre × baixar com liberação do admin**; gating comum/admin; nomes reais dos botões (**Processar pasta agora**, **Processar (auto)**, **Marcar visíveis**, **Só pendentes**); **Fila/Organizador/Quarentena**, envio em lote, tipos **DOC/EC/EE/EG/AE**, pastas locais/UNC. Mermaid reordenado (Navegar → buscar → pendente/processado → solicitar/baixar → Solicitação).
- **Posts #1/#2/#3 atualizados via `atualizar_postagem`** (autor `master`) — bancos existentes normalizados por edição (a semeadura só roda com tabela vazia).
- **`assets/test/criar_postagens_blog.py` sem duplicação**: agora importa o `POSTAGENS_PADRAO` oficial de `mod_blog/bd_manipulador` (docstring atualizada) — o seed nunca mais diverge do padrão.
- **Higiene (fora do escopo)**: a suíte completa deixa posts de teste ("Carrossel A/B/C" etc.) na base real — higiene preexistente dos testes de carrossel.
- **Validação (sistema reiniciado, Playwright real — `/login` 200, screenshot das 3 guias uniformes com diagramas centralizados)**: `assets/test/test_blog_mermaid_fim.py` **7/7** + suíte `assets/test/teste_fluxo_blog.py` **46/46**.

### Adições recentes (14/09/2026) — padronização das postagens-guia + Mermaid ao fim e centralizado

- **Diagrama centralizado e estreito (`mod_blog/telas.py:_renderizar_conteudo_postagem`, `telas.py:26-61`)**: o bloco ```mermaid deixou de ocupar a largura cheia — agora renderiza dentro de coluna `max-width:680px` com `justify-center` (`telas.py:46-52`, `ui.mermaid(...).classes("w-full my-2").style("overflow-x: auto")`). Texto ao redor continua via `formatar_conteudo_para_exibicao`/`ui.html`; diagrama inválido exibe "(diagrama inválido)" sem derrubar a tela; recurso desabilitado (`blog_habilitar_mermaid`) cai no ramo texto puro.
- **PADRÃO ÚNICO nas 3 seeds (`mod_blog/bd_manipulador.py:POSTAGENS_PADRAO`, `:113-217`)** — espelho da postagem "Editor de PDF — Como usar": `# **Título**` (faixa gigante centralizada), `### subtítulo`, parágrafo de apresentação, seções em **negrito** com listas (`**Como usar**`, `**Dicas**`, `**Limites**`/`**Status possíveis**`) e ```mermaid ao fim (fluxos inalterados). Vale para bancos novos — a semeadura (`_semear_postagens_padrao`, `:220`) só roda com a tabela vazia.
- **Postagens atuais #1/#2/#3 atualizadas via `atualizar_postagem`** (autor `master`) para o mesmo padrão — bancos existentes não são re-semeados, só normalizados por edição.
- **REGRA — `mover_mermaid_para_fim()` (`bd_manipulador.py:531-544`)**: ao salvar (criar em `:550-563` e editar em `:569-582`), blocos ```mermaid vão para o fim na ordem original (idempotente; sem fence completo o conteúdo segue intacto).
- **Teste novo `assets/test/test_blog_mermaid_fim.py` (7 checks)** — meio→fim com ordem, sem fence/incompleto intacto, entradas vazias, seeds conformes + idempotência, 3 postagens, contrato do render (`justify-center` + `max-width: 680px`); linha correspondente no `assets/test/README.md`.
- **Validação (sistema reiniciado, Playwright real — `/login` 200, screenshot das 3 postagens uniformes com diagramas estreitos centralizados)**: backend (move/ordem/idempotência/seeds), screenshot e suíte `assets/test/teste_fluxo_blog.py` **46/46**.
