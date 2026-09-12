# Blog Module — `mod_blog`

> Corporate blog module: route `/blog` (key `blog`) · own database `db_mod_blog.db` (WAL) · HTML sanitized with `nh3` · read-only for `comum` · central LGPD audit.

---

# Módulo Blog — `mod_blog`

> Módulo de blog corporativo: rota `/blog` (chave `blog`) · banco próprio `db_mod_blog.db` (WAL) · HTML sanitizado com `nh3` · somente-leitura para `comum` · auditoria central LGPD.

## Propósito

Blog corporativo para publicação de avisos, novidades e orientações. O usuário `comum` tem acesso **somente leitura** — publicar, comentar, editar e excluir são restritos ao administrador geral e ao administrador do módulo `blog`, validados na UI **e** no backend.

## Banco de dados

- **`tb_postagens`**: `id` PK, `titulo`, `conteudo` (gravado sanitizado), `autor`, `data_criacao`, `data_atualizacao`, `ativo` (soft delete / publicar).
- **`tb_comentarios`**: `id` PK, `postagem_id` FK CASCADE, `autor`, `conteudo` (sanitizado), `data_criacao`.
- **`tb_config` (local do módulo)**: chave-valor com os padrões do blog (`blog_modo_exibicao`, `blog_postagem_unica_id`, `blog_largura_imagem`, `blog_tags_permitidas`, `blog_texto_header`, `blog_habilitar_mermaid`, `blog_carrossel_tempo`, `blog_carrossel_postagens_ids`).

A configuração visual (cor/tamanho dos botões, cor de fundo/título e texto do cabeçalho) permanece na `tb_config` central (prefixo `blog_*` — `blog_cor_botao`, `blog_cor_texto_botao`, `blog_cor_fundo`, `blog_cor_titulo`, `blog_btn_tamanho`, `blog_texto_header`), no card padrão **"Configurações de cores"** da Administração (via `tema_modulo.bloco_aparencia` — prévia ao vivo, sem texto do cabeçalho), seguindo o padrão do módulo Intranet. A tela ocupa a área cheia (`w-full`). O cabeçalho usa `chave_modulo="blog"` (`telas.py:246`): a borda de destaque é a **mesma cor dos botões do módulo** (`blog_cor_botao`, vazia = padrão via `PADROES_TEMA` — todos os módulos em `#000000`, a cor do intranet), título/fundo seguem o tema — sem hex hardcoded.

## Funcionalidades

- **CRUD com soft delete e publicar/despublicar**: criar, editar, despublicar, republicar e excluir (lógica) postagens.
- **Sanitização nh3** na gravação **e** na renderização, com whitelist configurável (`blog_tags_permitidas`, CSV). Aceita `http`/`https`, URLs relativas e `data:` para imagens.
- **Formatação rica**: títulos centralizados/negrito, imagens à esquerda com largura configurável (min–max em px), texto justificado.
- **Conversores**: HTML simples e Markdown leve (`#`, `**negrito**`, `- item`).
- **Diagramas Mermaid**: blocos ```mermaid ... ``` no conteúdo viram diagramas renderizados via `ui.mermaid` (bundle embutido do NiceGUI, **sem CDN**); texto ao redor preservado e diagrama inválido exibe "(diagrama inválido)". Habilitado por padrão e configurável no admin (`blog_habilitar_mermaid`, switch "Permitir diagramas Mermaid" no card "Configurações específicas").
- **Editor com pré-visualização** do conteúdo antes de publicar.
- **Modo de exibição**: histórico (lista completa DESC), **ou** publicação única, **ou** carrossel rotativo, alternável e persistido em config local. No modo única é possível **fixar qual postagem exibir** (`blog_postagem_unica_id`, config local — vazio = mais recente, automático); se a postagem fixada for despublicada/excluída, o feed volta silenciosamente para a mais recente (fallback automático). Ao criar uma nova publicação a fixação é limpa (a nova passa a ser a exibida).
- **Modo carrossel (rotação automática)**: o administrador seleciona **2 ou mais postagens** (`blog_carrossel_postagens_ids`, CSV) e define o **tempo de rotação** (`blog_carrossel_tempo`, padrão 10 s). As postagens são exibidas **uma por vez** com rotação automática (`ui.timer`), navegação manual (Anterior/Próximo) e **"Leitura completa"** que expande a postagem inteira e **pausa** a rotação. Em estado normal o card mostra um **resumo** (recorte em até 3 linhas via `_resumo_conteudo`). O bloco administrativo (`ui.select` múltiplo + `ui.number` do tempo) **reverte a seleção** se o admin tentar selecionar exatamente 1 postagem.
- **Modo carrossel — barra de ações no topo E no rodapé**: `_renderizar_carrossel` (`telas.py:239`) refatorou a barra de ações em função interna `barra_acoes()` (`telas.py:287`), renderizada **duas vezes** — no topo do card (para o usuário fixar a leitura logo no início de postagens longas) e no rodapé (para trocar de postagem sem voltar ao topo). Contém navegação (anterior/próxima), indicador "atual/total" e o botão **"Leitura completa"**/**"Voltar ao carrossel"** (que pausa/retoma a rotação automática).
- **Busca no feed (usuários e administradores)**: campo de busca por termo (título, conteúdo ou autor — case-insensitive) e campo de data (AAAA-MM-DD), filtrando em memória antes da lógica do modo de exibição; com busca ativa e sem resultados, a mensagem é "Nenhuma publicação encontrada." (sem busca: "Nenhuma publicação ainda.").
- **Fonte única de exibição — Home mostra o MESMO padrão**: a nova função **`renderizar_postagens(wrap, usuario_logado, perfil, pode_publicar, ao_atualizar, ao_editar=None, termo="", data_f="")`** (`telas.py:368`) é a **FONTE ÚNICA** do padrão de exibição (histórico/única/carrossel) — usada pela tela do Blog **e pela Home** (`main.py:216,289-302`), que exibe "Publicações recentes" no mesmo padrão configurado no módulo, com botão "Abrir Blog completo" (`main.py:296`). O `atualizar()` do Blog foi refatorado para chamar `renderizar_postagens` (`telas.py:749`); `termo`/`data_f` filtram título/conteúdo/autor e data.
- **Gestão de despublicadas**: lista de postagens inativas com botão de republicar — na aba **"Despublicadas"** da própria tela do blog (`telas.py:251,469`). O painel de administração standalone (`/admin/blog`) **não tem mais** o card "Postagens despublicadas (gestão)" (removido em 06/09) — ficou apenas com "Configurações de cores" + "Configurações específicas" + backup.
- **Somente-leitura para `comum`**: controles ocultos na UI e bloqueados no backend.
- **Auditoria** (banco exclusivo `db_mod_auditoria.db`, tabela `tb_auditoria_blog`) para criar/atualizar/despublicar/republicar/excluir postagens e comentários.
- **Responsividade (RNF-UI-01, 09/2026 — auditado 320/768/1024 `kbp-web-design`)**: filtros justificados (`flex-wrap` `gap` via `.style`), exibição centralizada (`w-full justify-center`), seleção em lote com `grid mobile-first`; dialogs `w-full max-w`; proposta P0/P1/P2 por `container`/`row`/`grid` (cards `grid-cols-1 sm:grid-cols-2`).
- **Versionamento**: `versao_modulo:blog` exibido no rodapé de `/blog`.
- **Seed de postagens "Como usar"**: script `test/criar_postagens_blog.py` insere 3 postagens de guia de uso (Editor de PDF, Solicitação de Impressão e Empenhos) no `db_mod_blog.db`, cada uma com fluxograma Mermaid e seções *Como usar*/*Dicas*. Reutiliza `criar_postagem` (sanitização nh3, permissão e auditoria) com autor `master`; `main()` é fail-soft com try/except + loguru. Execute: `source .venv/bin/activate && python test/criar_postagens_blog.py`.
- **Semeadura automática em banco novo** (`_semear_postagens_padrao`, `bd_manipulador.py:205`): renomeada de `_sembrar_postagens_padrao` (termo português correto). As 3 postagens padrão (`POSTAGENS_PADRAO`, `bd_manipulador.py:104`) tiveram o conteúdo **reordenado — texto primeiro e o fluxograma ```mermaid por último**. A semeadura agora define `data_criacao` = **momento de criação do banco** (`datetime.now` local), um único timestamp compartilhado por todas as postagens, em vez do `DEFAULT CURRENT_TIMESTAMP` por linha. Chamada por `init_db()` apenas quando a tabela está vazia (idempotente) e com try/except + loguru.

## Home (dashboard) — feed no mesmo padrão do módulo (11/09)

A página inicial (`main.py:216`, `page_dashboard`) exibe a seção **"Publicações recentes"** usando a **mesma** função de renderização da tela do Blog — `renderizar_postagens` (`mod_blog/telas.py:368`). Consequência: o que o admin configura no módulo (modo `historico`/`unica`/`carrossel`, postagem fixada, carrossel com IDs/tempo, busca) vale **igualmente para a Home** — ela respeita o padrão configurado e não tem lógica própria de exibição. O cabeçalho da seção traz o botão **"Abrir Blog completo"** (`main.py:296`), que navega para `/blog`. O feed é renderizado em `_feed_wrap` com `pode_publicar_blog` calculado a partir do perfil (`administrador_geral` ou admin do módulo blog) — `main.py:289-302`. Coberto por `test/teste_home_blog.py` (3 verificações, headless — valida carrossel/única/histórico na Home).

## Permissões

| Ação | `comum` | Admin | Observação |
|:---|:---:|:---:|:---|
| Ler postagens/comentários | ✓ | ✓ | — |
| Criar postagem | ✗ | ✓ | backend valida |
| Editar postagem | ✗ | ✓ | backend valida |
| Comentar | ✗ | ✓ | backend valida |
| Despublicar/Republicar | ✗ | ✓ | aba Administração |
| Excluir (soft delete) | ✗ | ✓ | só admin |

## Rota e integrações

- Rota: `/blog` (chave `blog`) — permissão via `validar_acesso_modulo`.
- Consumido pelo núcleo: bootstrap cria o banco, scheduler faz backup e o dashboard usa `contar_postagens(ativo=True)`.
- Testes: `test/teste_fluxo_blog.py` (37/37 OK), `test/teste_viabilidade_mermaid.py` (5/5 OK — renderização de `ui.mermaid` sem CDN e caminho real do blog) e `test/teste_carrossel_blog.py` (headless — valida o DOM do modo carrossel: indicador de posição, botão Leitura completa, select de postagens, tempo e expansão).

## Testes

```bash
.venv/bin/python test/teste_fluxo_blog.py
```

Ver [Manual do Usuário Comum](../manual_de_uso_usuario_comum/index.md), [Manual do Administrador](../manual_de_uso_administrador/index.md) e [Análise do Módulo](../analise_mod_blog.md).
