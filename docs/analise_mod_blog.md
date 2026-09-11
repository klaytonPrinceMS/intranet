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
- **Sanitização nh3 na gravação E na renderização** — whitelists **alinhadas**: ambas usam `tags_permitidas()` (CSV de `blog_tags_permitidas`, config local com fallback na central). Atributos essenciais permitidos (`a[href]`, `img[src/alt/title/width/height]`, `class` em code/pre/blockquote); esquemas `http`/`https`/`data`/`mailto` + URLs relativas (`url_relative="pass_through"`) e `link_rel="noopener noreferrer"` (RF-32 **REALIZADO**).
- **Formatos**: HTML simples **e** Markdown leve — `_markdown_leve()` (`bd_manipulador.py:465`) converte `#`/`##`/`###` → h1/h2/h3, `- `/`* ` → listas e `**negrito**` → `<b>` (sobre texto já escapado).
- **Formatação rica** (RF-32): `formatar_conteudo_para_exibicao()` aplica estilos sobre o HTML sanitizado — h1/h2/h3 centralizados e em negrito, `<img>` flutuando à esquerda com limites min/max configuráveis (`blog_largura_imagem`, padrão 200–400 px, `loading=lazy`), texto justificado; texto puro/Markdown também é justificado.
- **Modo de exibição**: histórico completo **ou** publicação única — `obter_modo_exibicao()` lê `blog_modo_exibicao` da config local; alternável na tela (persistido + auditado). No modo única, a postagem exibida pode ser **fixada** por id (`blog_postagem_unica_id`, config local): `obter_postagem_unica_id()` (`bd_manipulador.py:559`) devolve o id ou `None` (ausente/inválido = mais recente, fallback automático); `definir_postagem_unica_id(pid)` (`bd_manipulador.py:573`) fixa/limpa (`None`/`""` limpa). O seletor "Postagem exibida (modo única)" (`telas.py:395`) só aparece no modo única, lista as postagens ativas (`""` = "Mais recente (automática)") e, se a fixada sair da lista (despublicada/excluída), o feed volta silenciosamente para a mais recente (`telas.py:440-447`). Ao **criar** nova publicação a fixação é limpa (`telas.py:310`) — a nova passa a ser a exibida. Trocas de modo/fixação auditadas (`audit_reg`) e com reload.
- **Gestão de despublicadas**: aba Administração lista postagens inativas (`listar_postagens(ativo=False)`) com botão **Republicar** (`publicar_postagem`).
- Soft delete: postagens inativas saem da lista pública; comentários só são removidos fisicamente por cascade quando a postagem é deletada fisicamente (fluxo da limpeza cruzada do módulo de usuários).

## Integrações com o núcleo

Importa `autenticacao.pode_publicar_no_blog` e `eh_admin_do_modulo`. Grava na trilha via `audit_log` (banco exclusivo `db_mod_auditoria.db`, tabela `tb_auditoria_blog`) para criar/alterar/despublicar/republicar/excluir postagens e comentários. Config de aparência na `tb_config` central (prefixo `blog_*`); config de comportamento na `tb_config` LOCAL do módulo. Consumido pelo núcleo: bootstrap cria o banco, scheduler faz backup e o dashboard usa `contar_postagens(ativo=True)`.

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
