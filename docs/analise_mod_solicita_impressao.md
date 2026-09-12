# Solicitação de Impressão — `mod_solicita_impressao`

> Print request module: route `/solicita-impressao` (key `solicita_impressao`) · own database `db_mod_solicita_impressao.db` · PDF upload, page counting, hierarchical monthly quotas, dual-mode print, central audit.

---

# Solicitação de Impressão — `mod_solicita_impressao`

> Módulo de solicitação de impressão: rota `/solicita-impressao` (chave `solicita_impressao`) · banco próprio `db_mod_solicita_impressao.db` · envio de PDF, contagem de páginas, cotas mensais hierárquicas, impressão dual, auditoria central.
>
> **Versionamento**: `versao_modulo:solicita_impressao = 1.0.260908` (seed em `bd_conexao.init_db()` — chave `tb_config` central, formato `1.0.AAMMDD`, exibida no rodapé em `/solicita-impressao` junto à versão global). Duplicada também em `tb_configuracoes_modulo` (`versao_modulo`) do banco do módulo. Atualizar a cada alteração do módulo.

## Propósito

Módulo para solicitação de impressão de arquivos PDF. Usuários **comuns** anexam um ou mais PDFs
por envio, informam cópias, papel (A4/A3), cor (PB/Color), frente e verso (borda curta/longa),
se o papel é sulfite, observações e a secretaria/setor de crédito. O sistema conta as páginas,
renomeia os arquivos no padrão definido, aplica regras de cota mensal (hierárquica) e fluxo de
autorização quando exigido. Apenas administradores do módulo imprimem; responsáveis cadastrados
autorizam quando a secretaria/setor exige.

!!! note "Modelo vigente — 1 pedido por envio (grupo)"
    Desde a reformulação de **07/09** o módulo trata **1 PEDIDO POR ENVIO**: um grupo de arquivos
    (até 10 PDFs) confirmado de uma vez vira **um único pedido** com **status único** — todos os
    arquivos do grupo são autorizados/recusados/impressos/cancelados **em conjunto**. A
    **auto-autorização foi removida**: sem autorizador cadastrado para a secretaria/setor, o
    pedido fica `pendente` e o **admin autoriza e imprime**. Ao imprimir, a cota é descontada
    **uma vez por grupo** e os **arquivos são apagados do servidor imediatamente**.

## Banco próprio

Criador vigente: `init_db()` em `bd_manipulador.py:113-345` (bootstrap central
`mod_intranet_inicializacao_bd.inicializar_bancos`).

Todas as tabelas vivem em `db_mod_solicita_impressao.db` (WAL). Arquivos PDF enviados são salvos
em `mod_solicita_impressao/solicitacaoImpressao/` (pasta própria do módulo — nada é misturado
com outros módulos).

### Tabelas

- **`tb_solicitacoes`**: id, usuario_solicitante, arquivo_original, arquivo_servidor,
  caminho_arquivo, hash_arquivo, qtd_copias, tamanho_papel (A4/A3), cor (PB/Color),
  frente_verso (0/1), tipo_borda (curta/longa/NULL), papel_sulfite (0/1),
  **tipo_papel** (sulfite/fotografico/verge — coluna nova, migração idempotente
  `bd_manipulador.py:275-282`), observacoes,
  secretaria_id FK, setor_id FK, qtd_paginas_arquivo, paginas_contabilizadas, status,
  cota_excedida (0/1), requer_autorizacao (0/1), autorizado_por, data_autorizacao,
  motivo_recusa, impresso_por, data_impressao, data_criacao, data_atualizacao,
  **grupo_id** (agrupamento "1 pedido por envio"; criado via ALTER idempotente +
  backfill `grupo_id = id` para registros sem grupo + índice `idx_sol_grupo` —
  `bd_manipulador.py:278-287`).
- **`tb_secretarias`**: id, nome, sigla, cota_paginas_mensal, limite_pedidos_abertos, ativo.
- **`tb_setores`**: id, nome, secretaria_id FK, cota_paginas_mensal, limite_pedidos_abertos, ativo.
- **`tb_responsaveis_autorizacao`**: id, user_nome, secretaria_id FK, setor_id FK (opcional), ativo.
- **`tb_cotas_impressao`**: id, secretaria_id, setor_id (NULL=secretaria), cota_paginas,
  mes_referencia (YYYY-MM, único por vínculo), ativo.
- **`tb_consumo_cota`**: id, secretaria_id, setor_id, mes_referencia, paginas_usadas, atualizado_em.
- **`tb_configuracoes_modulo`**: chave/valor (pasta, max MB, **alertas da nova solicitação**,
  impressoras padrão, **tipo de papel padrão**, marca d'água opcional e personalizável).
- **`tb_impressoras`**: id, nome (UNIQUE), tamanho_papel (A4/A3), cor (Color/PB),
  frente_verso (0/1), papel_sulfite (0/1), driver (padrão `PCL6`), ativo (0/1), criado_em.
  Usada pelo seletor de impressão do botão "Imprimir". Migração idempotente adiciona a coluna
  `driver` em instalações existentes (`bd_manipulador.py:304-315`).

## Contabilização de impressões (fórmula)

```
paginas_contabilizadas = qtd_paginas × qtd_copias × fator_papel × fator_frente_verso
  fator_papel: A4 = 1, A3 = 2
  fator_frente_verso: não = 1, sim = 2
```

Exemplos: 10 pág × 3 cóp × A4 frente = 30; A4 frente/verso = 60; A3 frente = 60; A3 frente/verso = 120.

## Cotas (mensal, hierárquicas)

- Cada **secretaria** tem cota máxima mensal (total do mês).
- Cada **setor** pode ter cota própria; se não tiver, usa o **pool da secretaria**.
- Ao **exceder**: o envio é **permitido**, porém a solicitação fica marcada como
  `excedente_cota` e a critério do autorizador/admin imprimir ou não.
- Consumo descontado **somente na impressão efetiva** (admin confirma).
- Visual no painel: barra de progresso **SEM numeral** (para não expor o consumo entre
  secretarias) — verde <50%, amarelo 50–80%, laranja 80–100%, vermelho >100%
  (`_barra_cota`, `telas.py:123-138`).
- Admin pode **editar cota** e **resetar consumo** do mês. Sem notificações (por design).
- Reset automático todo dia 1º (novo `mes_referencia`).

## Limite de pedidos abertos (elástico)

Além da cota mensal de páginas, cada **secretaria** e cada **setor** pode ter um
**limite de pedidos abertos** (`limite_pedidos_abertos`, coluna nova em
`tb_secretarias` e `tb_setores` — `bd_manipulador.py:159,180`; migração idempotente
`bd_manipulador.py:160-166,181-187`). **0 = sem limite** (padrão).

Regra de bloqueio (contagem elástica):

- "Pedido aberto" = status em `pendente`, `aguardando_autorizacao`, `autorizado`
  ou `excedente_cota` — ou seja, **não** impresso/recusado/cancelado
  (`contar_pedidos_abertos`, `bd_manipulador.py:1028`).
- O **setor só pode pedir se a secretaria não atingiu o teto**; cada um tem seu
  próprio limite (`verificar_limite_pedidos`, `bd_manipulador.py:1057`).
- Ao atingir o teto, `criar_solicitacao` (`bd_manipulador.py:1136`) e
  `confirmar_rascunho` (`bd_manipulador.py:1627`) **bloqueiam** o envio com
  mensagem orientando a imprimir/cancelar pedidos pendentes para liberar vaga.
- A impressão (ou recusa/cancelamento) **libera a vaga** automaticamente —
  por isso "elástico".

## Relatório de impressões por período

Sub-aba **Relatórios** na Administração (`_admin_relatorio`, `telas.py:1553-1647` e
`telas_administracao.py:615-713` — **cópia duplicada da admin existe nos dois arquivos**): o admin
escolhe um **prazo fixo mensal** (Este mês, Mês anterior, Últimos 6 meses, Ano atual — botões que
preenchem as datas e geram na hora) ou informa um **período personalizado no calendário**
(data inicial/final) e clica em **"Gerar relatório"**, que monta as tabelas prontas via
`_tabela_relatorio` (`telas.py:1538`, `telas_administracao.py:596`). O foco é **cobrança/repasse**:
secretaria/setor primeiro, depois quem imprimiu, quem autorizou e o total geral.

Backend: `relatorio_impressao(data_inicio, data_fim)` (`bd_manipulador.py:2345`)
agrega as solicitações com `status='impresso'` no período (por `data_impressao`),
com totais de **cópias** e **páginas contabilizadas**, separando **color/PB** pela
coluna `cor`. Helper `_agregar_impressao` (`bd_manipulador.py:2301`) faz o GROUP BY
por coluna. Desde a reformulação de 07/09, a contagem de **pedidos** usa
`COUNT(DISTINCT s.grupo_id)` (1 pedido por envio) — não mais o nº de linhas de
`tb_solicitacoes`. Retorna um dict com:

- `geral` — total geral (pedidos, cópias total/color/PB, págs. total/color/PB);
- `por_secretaria` — agrupado por secretaria;
- `por_setor` — agrupado por secretaria+setor;
- `por_autorizador` — agrupado por `autorizado_por`;
- `por_impressor` — agrupado por `impresso_por`.

## Fluxo de tela

- **Nova Solicitação** (comum): ao **selecionar os PDFs** eles sobem **automaticamente para o servidor**
  e já recebem nome do sistema (o nome original é descartado — não influencia o sistema). Cada arquivo fica
  como **rascunho** com nome `YYYYMMDD_HHMMSS_usuario_<uuid>_rascunho.pdf` e expiração de
  `tempo_expira_rascunho_min` (padrão 10 min): se o usuário não confirmar ("Enviar solicitação")
  nesse prazo, o arquivo é **removido do servidor automaticamente** (job `cleanup_solicita`, 1 min).
  Há botão "Remover selecionados" (e remoção individual) para descartar antes. Ao confirmar, os
  arquivos são renomeados para o padrão final `dataHora_usuario_cor_copias_paginas_secretaria_setor.pdf`
  e **todos viram UM ÚNICO PEDIDO (grupo)** — `confirmar_lote` (`bd_manipulador.py:1740`) converte os
  N rascunhos do envio em um pedido com o mesmo `grupo_id` e **status único** (máx. 10 PDFs por envio,
  `MAX_ARQ`).
- **Status do pedido (sem auto-autorização)**: ao confirmar o envio, o status do grupo é definido por
  `confirmar_lote` (`bd_manipulador.py:1773-1782`): `excedente_cota` se exceder a cota; senão
  `aguardando_autorizacao` se houver responsável cadastrado para a secretaria/setor; senão
  **`pendente`** — sem autorizador, o pedido fica pendente e o **admin autoriza e imprime**.
- Valores **padrão pré-selecionados** (editáveis pelo admin): papel `padrao_papel` (A4),
  cor `padrao_cor` (**Color** — migrado de PB em 07/09), `padrao_frente_verso` (somente frente),
  `padrao_sulfite` (sim) e **`padrao_tipo_papel`** (sulfite).
- Campos: cópias, papel, cor, **tipo de papel** (sulfite/fotográfico/vergê — ativo apenas em A4),
  frente/verso + borda, observações, secretaria→setor — todos em **UMA linha** (`flex-wrap` +
  `flex-1 min-w-[15ch]`, secretaria/setor `min-w-[25ch]`); **alertas configuráveis**
  (`alertas_nova_solicitacao`, uma frase por linha) exibidos **abaixo do card de envio** com ⚠
  (substitui os antigos avisos fixos de presença obrigatória e de páginas múltiplas); rótulo
  informando que todos os arquivos marcados viram **um único pedido**.
- **Impressão** (admin): ao confirmar a impressão do pedido, a cota é descontada **uma vez por grupo**
  e os **arquivos são apagados do servidor imediatamente** (`imprimir_grupo`,
  `bd_manipulador.py:2053`). Recusar / recuar / cancelar **removem os arquivos do servidor** de todos
  os arquivos do grupo.
- **Auditoria** (banco exclusivo `db_mod_auditoria.db`, tabela `tb_auditoria_solicita_impressao`): registra quem **solicitou**
  (cópias, páginas, secretaria, setor, status, excedente), quem **autorizou**, quem **imprimiu**
  (com total de páginas e prazo de exclusão) e quem **recusou** (com motivo).
- **Minhas Solicitações** (comum): lista os **pedidos** do usuário (um card por envio/grupo, com
  todos os arquivos e status único — `_tela_minhas`, `telas.py:374`), com **campo de busca**,
  **filtro que remove pedidos cancelados** da lista, chip de status, barra de cota **sem numeral**,
  botão Baixar (por arquivo), **checkboxes por arquivo + "Baixar selecionados" (avulso) e
  "(zip)"**, **Reenviar** (pedido recusado) e Cancelar (pendente/aguardando/excedente/recusado).
- **Autorização** (responsável): aba **"Solicitação pendente"** (`_tela_autorizar`, `telas.py:409`)
  com **campo de busca no topo** (entre o menu de abas e os cards) e seções **"AGUARDANDO
  AUTORIZAÇÃO"** e **"JÁ AUTORIZADOS"** + busca (texto/data); lista os
  pedidos das secretarias/setores do autorizador (`listar_pedidos_responsavel`,
  `bd_manipulador.py:1923`) com Autorizar / Recusar (motivo obrigatório) — ações em **todo o grupo**.
- **Administração** (admin do módulo): tabela mestra + sub-abas Secretarias, Setores,
  Responsáveis, Cotas, Relatórios, Configurações. Ações: Imprimir (seletor de impressora), Baixar (sempre),
  Recuar (cancelar), Autorizar, Recusar.
- **Administração → Secretarias / Setores**: campo **"Limite pedidos abertos (0=ilimitado)"**
  no criar/editar e exibição do limite na listagem (`telas_administracao.py:100,150,190,245`).
- **Administração → Solicitações** (`_admin_solicitacoes`, `telas.py:700`; `telas_administracao.py:77`
  delega para `telas.py` — evita duplicação): abas **Ativos / Impressos / Recusados / Todos** +
  barra de busca com **texto livre** (solicitante, observação, arquivo, nome de secretaria/setor —
  `LIKE NOCASE`), **secretaria→setor em cascata**, **data inicial/final** e botão **Buscar**
  (`listar_pedidos`, `bd_manipulador.py:1840`). Pedidos agrupados por **secretaria→setor**; ao
  imprimir, o pedido sai da gestão ativa do admin.
- **Impressão com seletor de impressoras** (`_imprimir_grupo`, `telas.py:883`): ao clicar em "Imprimir"
  num pedido **autorizado/pendente/excedente**, abre um **diálogo com as impressoras cadastradas**
  (`tb_impressoras`), sugerindo a padrão A4/A3 conforme o papel; ao confirmar, dispara
  `window.imprimirPdf` via JS (diálogo nativo do SO). **Não marca como impresso** — o desconto de
  cota e a remoção dos arquivos ocorrem no botão **"Confirmar impressão"** (`_confirmar_impressao_grupo`,
  `telas.py:944` → `imprimir_grupo`, `bd_manipulador.py:1862`).

## Impressão (dual mode)

- Se **impressora padrão** configurada (A4/A3): botão "Imprimir direto" dispara
  `window.printSolicitacao(id)` via JS (`impressao.js` em `src/`) — abre o PDF preparado numa
  nova aba e usa o diálogo nativo do SO.
- Sempre disponível: **Baixar para impressão** (`ui.download` do PDF, com marca d'água se ativa) →
  usuário imprime via Ctrl+P no navegador/SO.
- **Marca d'água** (opcional, personalizável): texto com placeholders `{data}`, `{usuario}`,
  `{id}`, `{secretaria}`, `{setor}`, `{solicitante}`; posição, opacidade, fonte, cor, rotação —
  tudo configurável em Configurações. Se desativada, PDF sai sem marca.
- **Painel de impressoras** (`_painel_impressoras`, `telas.py:1509` e `telas_administracao.py:545`):
  bloco em **Configurações** para **cadastrar / listar / definir padrão / excluir** impressoras
  (nome, papel, cor, frente/verso, sulfite, driver **PCL6** default). A padrão A4/A3 é marcada via
  `definir_impressora_padrao` (`bd_manipulador.py:474`) e alimenta o seletor do botão "Imprimir".
- **Impressão por grupo** (`imprimir_grupo`, `bd_manipulador.py:1862`): ao confirmar a impressão de
  um pedido, a cota é descontada **uma vez por grupo** (pelo total de páginas contabilizadas, na
  secretaria e no setor se houver) e os **arquivos são apagados do servidor imediatamente** — o
  pedido impresso sai da gestão ativa do admin.
- **Padrões migrados (07/09, sem restart via `init_db`)**: `tempo_expira_rascunho_min` 4→**10** e
  `padrao_cor` PB→**Color** (`bd_manipulador.py:328-331`).

## Nomenclatura do arquivo

```
AAMMDDHHMMSS_secretaria_setor_nomeSolicitante_qtdCopias_cor_tipoPapel_quantidadeFolhas_ordemDoenvioArquivo.pdf
```

Ex.: `260907143022_SAUDE_ATENDIMENTO_joao_silva_3_colorido_sulfite_10_1.pdf`
(acentos removidos, espaços→`_`, nomes sanitizados). A cor entra entre as cópias e o tipo de
papel (`colorido` para Color, `pretoebranco` para PB); o **tipo de papel**
(`sulfite`/`fotografico`/`verge`) e a **ordem de envio do arquivo** (1, 2, 3…) garantem
unicidade mesmo quando vários arquivos chegam no mesmo segundo com a mesma quantidade de
páginas — gerada por `gerar_nome_arquivo` (`bd_manipulador.py:1038-1070`), que recebe
`cor`, `tipo_papel` e `ordem_envio`.

## Regras de negócio

- **Somente PDF**: upload recusa extensões não-`.pdf`.
- **Até 10 arquivos por envio** (`MAX_ARQ = 10`): todos os arquivos de um envio viram **um único
  pedido (grupo)** com status único.
- **Tipo de papel** (`tipo_papel`): sulfite (padrão), fotográfico ou vergê — selecionável no
  formulário e **ativo apenas em A4** (A3 = sulfite obrigatório, `ao_papel` em `telas.py:290-301`);
  papel não sulfite notifica "o usuário deve trazer o próprio papel" (`ao_tipo_papel`,
  `telas.py:284-288`). Padrão configurável (`padrao_tipo_papel`, default `sulfite`).
- **Alertas da nova solicitação** (`alertas_nova_solicitacao`, config): frases exibidas abaixo do
  card de envio (uma por linha, com ⚠) — **substitui** os antigos `aviso_presenca_obrigatoria` e
  `aviso_paginas_multiplas` (removidos). Editável em Administração → Configurações
  (`telas.py:366-369`, `telas_administracao.py:416-418`).
- **Reenvio de pedido recusado**: o usuário pode **Reenviar** o próprio pedido recusado — o status
  volta para `aguardando_autorizacao` (se há responsável) ou `pendente`, limpando motivo e dados de
  autorização (`reenviar_grupo`, `bd_manipulador.py:2025-2055`; botão em `telas.py:572-576`).
  `cancelar_grupo` também aceita o status `recusado` (`bd_manipulador.py:2001-2022`).
- **Permissões**: `comum` cria/acompanha próprios pedidos; responsável autoriza sua secretaria/setor;
  `administrador` do módulo imprime/recua/gerencia. Admin geral vê tudo + auditoria.
- **Concessão da permissão de autorizar impressão**: em *Administração → Responsáveis* o admin
  localiza um **usuário cadastrado** via seletor buscável (do módulo de Gestão de Usuários) e o
  vincula a uma secretaria/setor como responsável. A permissão **pode ser concedida a usuários
  `comum`** — ao logar, mesmo sendo `comum`, o usuário passa a ver a aba **Autorização** e a
  área de autorizar impressões (a checagem usa `tb_responsaveis_autorizacao`, independente do perfil).
- **Sem auto-autorização**: sem responsável cadastrado para a secretaria/setor, o pedido fica
  `pendente` e o **admin autoriza e imprime** (`confirmar_lote`, `bd_manipulador.py:1610-1619`).
- **Auditoria central** (banco exclusivo de auditoria, tabela `tb_auditoria_solicita_impressao`): `criar_solicitacao`, `autorizar_solicitacao`,
  `recusar_solicitacao`, `imprimir_solicitacao`, `recuar_solicitacao`, `cancelar_solicitacao`,
  `criar/editar/excluir_secretaria/setor/responsavel`, `definir_cota`, `resetar_consumo`. Na
  reformulação de 07/09, a auditoria de **`criar_grupo`** (`confirmar_lote`,
  `bd_manipulador.py:1822-1825`) inclui o **SHA256 dos arquivos** do pedido; as ações de grupo
  (`autorizar_grupo`, `recusar_grupo`, `imprimir_grupo`, `recuar_grupo`, `cancelar_grupo`) são
  auditadas por `grupo_id`.

## Integrações com o núcleo

- Bootstrap cria o banco (`inicializar_bancos` → `init_solicita`).
- Módulo nativo em `tb_modulos` (seed `MODULOS_SISTEMA` em `autenticacao.py`):
  chave `solicita_impressao`, ícone `print`, rota `/solicita-impressao`.
- Permissão por módulo em `tb_acesso_usuario` (papel `comum`/`administrador`).
- Auditoria via `audit_log(usuario, 'solicita_impressao', acao, desc, hash)`.
- JS de impressão servido por rota `/solicita-impressao/src/impressao.js` (arquivo em
  `mod_solicita_impressao/src/`).
- Documentação disponível em `/documentacao` (build MkDocs do `docs/analise_mod_solicita_impressao.md`).

## Pontos de atenção

- NiceGUI roda no servidor; a lista real de impressoras do cliente depende de API experimental
  (`navigator.getPrinters`). O fallback é sempre o diálogo nativo do SO via `window.print()`.
- Contagem de páginas usa PyMuPDF; PDFs corrompidos/imagem podem retornar 0 (bloqueia envio).
- Cotas são mensais; reset manual ou automático (dia 1) — não há notificação por e-mail (sem SMTP).

## Hora do servidor (fonte da verdade de data/hora)

Desde 07/09, **todas as datas** do módulo (criação, autorização, impressão, expiração de
rascunho, exclusão de impresso, marca d'água e chave do mês de cota) vêm do **servidor** —
nunca do navegador/cliente:

- **Python**: `hora_servidor()` / `hora_servidor_str()` do novo helper central
  `mod_intranet/hora_servidor.py` (substituiu `datetime.datetime.now()` em
  `criar_solicitacao`, `confirmar_rascunho`, `confirmar_lote`, `registrar_rascunho`,
  `imprimir_solicitacao`, `expirar_rascunhos_e_impressos`, `aplicar_marca_dagua` e
  `mes_atual`).
- **SQL**: `datetime('now','localtime')` (relógio do servidor) em todos os INSERT/UPDATE de
  data — antes alguns usavam `datetime('now')` (UTC) e outros gravavam a string literal
  `"datetime('now','localtime')"` como texto (bug do relatório).

Com internet, a hora é sincronizada com **NTP.br** (a/b/c.ntp.br, RFC 5905, socket UDP puro,
timeout 2 s, cache de 60 s, lock threading); sem internet (ou com NTP desativado) usa o relógio
local do servidor. Chave de configuração: `hora_ntp_ativa` (default `"1"`) em `tb_config`
central — ver [Análise do Núcleo](analise_mod_intranet.md#hora-do-servidor-ntp).

## Adições recentes (07/09) — tipo de papel, alertas unificados, reenvio e relatório de cobrança

### `bd_manipulador.py`

- **Config `alertas_nova_solicitacao`** (`bd_manipulador.py:34-45`): frases de alerta da nova
  solicitação (uma por linha) — **substitui** `aviso_presenca_obrigatoria` e
  `aviso_paginas_multiplas` (removidos do `CONFIG_PADRAO`).
- **Coluna `tipo_papel`** em `tb_solicitacoes` (sulfite/fotografico/verge, default `sulfite`):
  no CREATE (`bd_manipulador.py:127`) + **migração idempotente** via ALTER
  (`bd_manipulador.py:275-282`).
- **`gerar_nome_arquivo` reescrito** (`bd_manipulador.py:1038-1070`): novo formato
  `AAMMDDHHMMSS_secretaria_setor_solicitante_copias_cor_tipoPapel_folhas_ordemEnvio.pdf` com o
  parâmetro `ordem_envio` para diferenciar arquivos do mesmo envio no mesmo segundo.
- **`criar_solicitacao`** (`:1073`), **`confirmar_rascunho`** (`:1520`) e **`confirmar_lote`**
  (`:1626`) recebem `tipo_papel` (e `ordem_envio` nas duas primeiras); o INSERT grava a coluna
  `tipo_papel`.
- **`reenviar_grupo(grupo_id, usuario, ator)`** (`:2025`): reabre pedido recusado para nova
  autorização (status → `aguardando_autorizacao`/`pendente`, limpa motivo e autorização).
- **`cancelar_grupo`** (`:2001`) agora também aceita o status `recusado`.
- **`_atualizar_status_grupo` corrigido** (`:1870-1899`): o valor especial
  `"datetime('now','localtime')"` é injetado como **expressão SQL** (avaliada pelo banco), não
  como string literal — era a causa do relatório não mostrar impressões do dia.
- **Migração de datas** (`init_db`, `:321-328`): corrige registros com a string literal
  `"datetime('now')"`/`"datetime('now','localtime')"` gravada em `data_impressao`/
  `data_autorizacao` para o valor real de agora.
- **Datas do servidor**: todas as funções usam `hora_servidor()` (Python) e
  `datetime('now','localtime')` (SQL) — ver seção "Hora do servidor" acima.
- **`relatorio_impressao` mantido** (`:2211`): geral, por secretaria, setor, autorizador e
  impressor (com `COUNT(DISTINCT grupo_id)`).

### `telas.py` / `telas_administracao.py`

- **Aba Nova Solicitação** (`_tela_nova`, `telas.py:143-369`): alertas unificados da config
  `alertas_nova_solicitacao` exibidos **abaixo do card de envio** (`:366-369`); removido o texto
  "Arquivos marcados serão enviados..."; campos (Secretaria, Setor, Qtd cópias, Tamanho papel,
  Cor, Tipo papel, Frente e verso, Tipo de borda) em **UMA linha** com `flex-wrap` e
  `flex-1 min-w-[15ch]` (secretaria/setor `min-w-[25ch]`), preenchendo toda a linha em qualquer
  largura; select **Tipo de papel ativo apenas em A4** (A3 = sulfite obrigatório); botões
  "Remover selecionados" e "Enviar solicitação" com **mesmo tamanho (w-56) centralizados**.
- **Aba Minhas Solicitações** (`_tela_minhas`, `telas.py:374-404`): campo de busca; filtro que
  **remove pedidos cancelados** da lista (`:396`); checkboxes por arquivo + botões
  **"Baixar selecionados"** (avulso) e **"Baixar selecionados (zip)"** (`_card_grupo`,
  `telas.py:486-505`); botões **Reenviar** e **Cancelar** para pedido recusado (`:566-576`);
  card mostra Secretaria/Setor na 1ª linha, Cópias/Papel/Cor/FV/Tipo na 2ª, Páginas + barra de
  cota na 3ª.
- **`_barra_cota` sem numeral** (`telas.py:123-138`): verde <50%, amarelo 50–80%, laranja
  80–100%, vermelho >100%.
- **Aba Autorização** (`_tela_autorizar`, `telas.py:409-458`): campo de busca no topo (entre o
  menu de abas e os cards).
- **`_card_grupo`/`_card_admin_grupo`** (`telas.py:463,764`): unpacking com `tipo_papel`, novo
  layout e `permite_selecao`.
- **`_admin_relatorio` reescrito** (`telas.py:1553-1647` e `telas_administracao.py:615-713` — cópia
  duplicada da admin existe nos dois arquivos): **prazos fixos mensais** (Este mês, Mês anterior,
  Últimos 6 meses, Ano atual) + calendário, com foco em **cobrança/repasse** (secretaria/setor
  primeiro, depois quem imprimiu, quem autorizou e total geral).
- **Novo wrapper `_reenviar_grupo`** (`telas.py:613-619`).
- **Admin config** (`_admin_configuracoes`): campo único **"Alertas da nova solicitação (uma
  frase por linha)"** e select **"Tipo de papel padrão"** (sulfite/fotográfico/vergê) —
  `telas.py:1359-1390` e `telas_administracao.py:416-447`.

### Adições recentes (09/2026) — responsividade global RNF-UI-01

- **Auditado 320/768/1024** (`kbp-web-design`) — proposta P0/P1/P2 por `container`/`row`/`grid`: abas `overflow-x-auto`, formulário `grid-cols-1 sm:grid-cols-2`, lista de solicitações `overflow-x-auto`, dialogs `w-full max-w`, barra de ações `flex-wrap` `gap` via `.style`. Ver [Padrões](padroes_codificacao/index.md) §8.1.

## Status

| Item | Situação |
|:---|:---:|
| Banco + 7 tabelas + cotas | Implementado |
| Contagem páginas + fórmula exata | Implementado |
| Fluxo comum (criar/acompanhar) | Implementado |
| Autorização por responsável | Implementado |
| Admin (imprimir/recuar/cadastros/cotas/config) | Implementado |
| Impressão dual (direto + download) + marca d'água | Implementado |
| Auditoria (banco exclusivo, tabela por módulo) | Implementado |
| Impressoras cadastradas + seletor de impressão (driver PCL6) | Implementado |
| Abas por status + busca (texto/secretaria→setor/data) em Solicitações | Implementado |
| Nomenclatura do arquivo com cor + padrões migrados (10 min / Colorido) | Implementado |
| Limite de pedidos abertos (elástico) em secretaria/setor | Implementado |
| Relatório de impressões por período (Relatórios) | Implementado |
| **1 pedido por envio (grupo)** — status único, sem auto-autorização, admin autoriza+imprime, arquivos apagados ao imprimir | Implementado |
| Auditoria de `criar_grupo` com SHA256 + relatório conta pedidos (`COUNT(DISTINCT grupo_id)`) | Implementado |
| Tipo de papel (sulfite/fotografico/verge) + nome de arquivo com `ordem_envio` | Implementado |
| Alertas unificados `alertas_nova_solicitacao` (substitui avisos antigos) | Implementado |
| Reenvio de pedido recusado (`reenviar_grupo`) + cancelar recusado | Implementado |
| Datas do servidor (`hora_servidor()`/NTP.br) + correção do `_atualizar_status_grupo` | Implementado |
| Relatório de cobrança/repasse com prazos fixos + calendário | Implementado |
| Documentação MkDocs | Implementado |
| Testes automatizados (`test/test_solicita_impressao.py`, `test/test_solicita_ui.py`) | Implementado |
| Testes manuais com usuários QA (`qacomum`/`qamaster`) | Pendente |

## Correção registrada — tema no escopo do módulo (`NameError`)

Bug real: ao abrir `/solicita-impressao`, a tela quebrava com
`NameError: name 't_cor_botao' is not defined`. Causa: as variáveis `t_cor_botao`,
`t_cor_txt_botao`, `t_btn_tamanho` e os helpers `_btn_cls()`/`_btn_style()` foram deixados **fora**
de `mostrar_tela(usuario_logado, perfil)` (no escopo do módulo), onde não têm acesso ao
`usuario_logado` para ler o tema — e as cores residuais no banco (`editpdf_cor_botao=#e61c91`,
`editpdf_cor_texto_botao=#faf7f7`) nunca eram lidas/carregadas corretamente naquele escopo.

Corrigido tirando a leitura de aparência do escopo do módulo e delegando o cupê "Aparência" ao
**helper central** `mod_intranet/tema_modulo.py::bloco_aparencia` (que lê/grava as 6 chaves com o
prefixo `solicita_impressao_*` em `tb_config` e **possui botão Salvar próprio**). O `_admin_configuracoes`
passou a usar `bloco_aparencia` (o `campo_modulo` foi **removido em 06/09** — edição do módulo é
exclusiva de `/configuracoes`); as variáveis `t_cor_fundo`, `t_cor_titulo` e
`t_texto_header` (usadas no cabeçalho) permanecem em `mostrar_tela`. Código morto (`_btn_cls`,
`_btn_style`) removido. Regra de uniformidade e prefixos cobertos por `test/test_tema.py`.
