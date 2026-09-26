# Solicitação de Impressão — `mod_solicita_impressao`

> Print request module: route `/solicita-impressao` (key `solicita_impressao`) · own database `db_mod_solicita_impressao.db` · PDF upload, page counting, hierarchical monthly quotas (1000/200 via `ORGANOGRAMA_BASE`), dual-mode print, central audit.

---

# Solicitação de Impressão — `mod_solicita_impressao`

> Módulo de solicitação de impressão: rota `/solicita-impressao` (chave `solicita_impressao`) · banco próprio `db_mod_solicita_impressao.db` · envio de PDF, contagem de páginas, cotas mensais hierárquicas (1000 secretaria / 200 setor, via organograma **compartilhado** obtido pela fachada `mod_intranet.integracoes.obter_organograma_base()`), impressão dual com marca d'água, auditoria central.
>
> **Versionamento**: `versao_modulo:solicita_impressao = 1.0.260913` (seed em `bd_conexao.init_db()` — chave `tb_config` central, formato `1.0.AAMMDD`, exibida no rodapé em `/solicita-impressao` junto à versão global). Duplicada também em `tb_configuracoes_modulo` (`versao_modulo`) do banco do módulo. Atualizar a cada alteração do módulo.

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
- **`tb_secretarias`**: id, nome, sigla, cota_paginas_mensal (**1000 padrão**, derivado do organograma compartilhado via `mod_intranet.integracoes.obter_organograma_base()` — ver "Isolamento modular"), limite_pedidos_abertos (20 padrão), ativo.
- **`tb_setores`**: id, nome, secretaria_id FK, cota_paginas_mensal (**200 padrão** — subsetores achatados como setores), limite_pedidos_abertos (10 padrão), ativo.
- **`tb_responsaveis_autorizacao`**: id, user_nome, secretaria_id FK, setor_id FK (opcional), ativo.
- **`tb_cotas_impressao`**: id, secretaria_id, setor_id (`0` sentinela para "sem setor" — SQLite trata NULL como distinto em UNIQUE, sem FK em `setor_id` por isso), cota_paginas,
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

- Cada **secretaria** tem cota máxima mensal (total do mês) — **1000 cópias padrão**, derivadas
  do **organograma compartilhado** obtido por `mod_intranet.integracoes.obter_organograma_base()`
  (semeado no `init_db`; **nunca** sobrescrito por `UPDATE` depois de existir — `bd_manipulador.py:401-518`).
- Cada **setor** pode ter cota própria (**200 cópias padrão** — subsetores achatados como setores); se não tiver, usa o **pool da secretaria**.
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
  Recuar (cancelar), Autorizar, Recusar. Painel standalone em `telas_administracao.py::mostrar_administracao`
  (rota `/admin/solicita_impressao`); `_admin_solicitacoes` delega para `telas.py` (pedidos agrupados por
  secretaria→setor); `_admin_relatorio` gera cobrança/repasse por período (prazos fixos + calendário).
- **Legado**: `bd_criador.py` é MORTO (tabela `tb_solicitacoes_impressao_legacy` no banco central) — fonte de verdade é `bd_manipulador.init_db()` em `db_mod_solicita_impressao.db`.
- **Upload assíncrono anti-disconnect**: `_tela_nova.ao_upload` é `async` (`on_multi_upload`, `await f.read()` por PDF, máx. 10 por envio via `MAX_ARQ`); contagem regressiva de expiração via `ui.timer(1.0, tick)`.
- **QA**: `data-testid` estáveis — `solicita-enviar` (envio), `solicita-busca` (Minhas Solicitações), `solicita-admin-salvar` (Configurações).
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

## Isolamento modular — organograma pela fachada do núcleo (25/09/2026, commit `624c9d5`)

### A violação

`bd_manipulador.init_db()` semeava as cotas a partir do organograma **importando o outro módulo
diretamente**:

```python
try:
    from mod_lista_telefonica.bd_manipulador import ORGANOGRAMA_BASE as _ORG_BASE
except Exception:
    ...
```

Isso quebrava o AGENTS.md §2 ("**Isolamento total** … nunca faça cross-query entre bancos") de três
maneiras, e todas são estruturais, não cosméticas:

| Dimensão | Por que o import direto é errado |
|:---|:---|
| **Dependência** | `mod_solicita_impressao` passa a **não iniciar** (ou a iniciar com organograma vazio) se o `mod_lista_telefonica` falhar no import, sumir do disco ou for desativado. O módulo de impressão não deveria depender de lista telefônica para semear cota. |
| **Ciclo de importação** | `main.py` carrega os módulos; um import de topo entre módulos fecha ciclo de import (`A → B → A`) e o sintoma é `ImportError` intermitente **dependente da ordem de carga** — a classe de bug mais difícil de diagnosticar. |
| **Coerência de dados** | O organograma é **seed de um módulo, consumido por outro**: quem altera a estrutura do organograma (departamento novo) tem de lembrar de semear em dois lugares, e o `mod_lista_telefonica` não tem nenhuma visibilidade de quem consome — acoplamento invisível. |
| **Portabilidade (PyInstaller)** | Na conversão `main.py → executável`, um import entre módulos passa a ser dependência de *hidden import* — falha só em produção. |

### A correção — a fachada `mod_intranet.integracoes`

A costura passou para o **núcleo**, que é quem pode conhecer todos os módulos:

```python
try:
    # Organograma via API pública do núcleo (AGENTS.md §2: Solicitação
    # não importa a Lista Telefônica — quem costura é o mod_intranet).
    from mod_intranet import integracoes
    _ORG_BASE = integracoes.obter_organograma_base()
except Exception:
    _ORG_BASE = None
if not _ORG_BASE:
    # Fallback local: módulo ausente ou organograma vazio — a semeadura
    # das cotas continua funcionando com o mínimo de secretarias.
    _ORG_BASE = [
        ("Gabinete", []), ("Administração", []), ("Finanças", []),
        ("Saúde", []), ("Educação", []), ("Obras e Infraestrutura", []),
    ]
```

Três propriedades deliberadas:

1. **Fachada, não reexport** — `mod_intranet/integracoes.py` é a **costura pública única**
   (`obter_usuario_gestao`, `listar_usuarios_gestao`, `agregador_habilitado`,
   `listar_noticias_para_tv`, `limpar_noticias_censuradas`, `obter_organograma_base`,
   `modulo_habilitado`). O módulo de negócio **fala com o núcleo**; o núcleo possui o
   acoplamento. Isso mantém a direção da dependência sempre apontando para `mod_intranet`.
2. **Import lazy dentro da função** — proposital: um import de topo de módulo de negócio dentro
   de `integracoes.py` fecharia ciclo com `main.py` (documentado na própria docstring do arquivo).
3. **Fail-soft por construção** — `obter_organograma_base()` faz o import interno dentro de
   `try/except`, e devolve `None` com `logger.warning` se o módulo de destino falhar. O chamador
   **nunca** propaga exceção de terceiro.

### O fallback local de 6 secretarias — e por que ele é necessário

`|not _ORG_BASE|` (e não só `except`) é a guarda real: cobre os **dois** modos de falha — a
importação que **lança** e o módulo que **responde vazio**. Sem o fallback, um
`mod_lista_telefonica` ausente deixaria `tb_secretarias` **vazia**, e aí o módulo de impressão
iniciaria sem nenhuma secretaria — a tela de nova solicitação apareceria sem crédito disponível
para o usuário, sem erro visível.

O mínimo semeado é **6 secretarias com lista de setores vazia** (`[]`):

| Secretaria | Sigla derivada | Cota | Limite de pedidos abertos |
|:---|:---|---:|---:|
| Gabinete | `SEC_GABI` | **1000** | 20 |
| Administração | `SEC_ADMI` | **1000** | 20 |
| Finanças | `SEC_FINA` | **1000** | 20 |
| Saúde | `SEC_SAUD` | **1000** | 20 |
| Educação | `SEC_EDUC` | **1000** | 20 |
| Obras e Infraestrutura | `SEC_OBRA` | **1000** | 20 |

`_sigla_sec(nome)` normaliza em NFKD, tira acento, `lower()`, filtra alfanuméricos e corta em 4
chars (`s[:4].upper()`, ou `ljust(3,"X")` se mais curto). Como **os setores ficam vazios**, o
fallback garante o nível 1 da hierarquia de cotas (secretaria) e **deixa o nível 2 (setor) a
cargo do admin**, que pode criá-los em Administração → Setores com cota própria. É
deliberadamente o menor organograma que ainda permite o sistema funcionar.

!!! warning "A fonte das cotas 1000 / 200 é o organograma **compartilhado**"
    Com a fachada, quem manda no organograma é o **`mod_lista_telefonica`** — o mesmo
    organograma que popula a lista telefônica. Isso é intencional (um organograma oficial, uma
    fonte), mas significa que **cadastrar um departamento novo na Lista Telefônica não cria
    automaticamente o setor de impressão correspondente**. Os dois bancos são independentes por
    desenho (AGENTS.md §4.1, um database por módulo): o `mod_solicita_impressao` semeia uma cópia
    da estrutura no **seu** `tb_setores` no `init_db`, e a partir daí o admin do módulo é
    soberano.

### Cotas 1000 (secretaria) / 200 (setor) — como a semeadura converte o organograma

`ORGANOGRAMA_BASE` tem **3 níveis**; o banco de impressão tem **2**. A conversão acontece em
`init_db()` (`bd_manipulador.py:443-518`):

```python
for _sec_nome, _setores in _ORG_BASE:                     # nível 1 → tb_secretarias
    _SECRETARIAS_PADRAO.append((_sec_nome, _sigla_sec(_sec_nome), 1000, 20))

for _sec_nome, _setores in _ORG_BASE:                     # níveis 2 e 3 → tb_setores
    for _set_nome, _subsetores in _setores:
        _SETORES_PADRAO.append((_set_nome, _sec_nome, 200, 10))
        for _sub in _subsetores:                          # ← subsetor ACHATADO como setor
            _SETORES_PADRAO.append((_sub, _sec_nome, 200, 10))
```

O **subsetor é achatado (flattened) no nível de setor** — não existe coluna de subsetor em
`tb_setores`. Isso é a simplificação que o modelo de cota exige: a cota é sempre
`secretaria → setor`, e um subsetor é, para fins de impressão, um setor. Todos os setores e
subsetores recebem a **mesma cota de 200** e o **mesmo limite de 10 pedidos abertos**.

!!! danger "O seed NUNCA faz `UPDATE` de cota — regra explícita de devSecOps/Postgres"
    A semeadura é guardada por `COUNT(*) == 0` em `tb_secretarias` **e** em `tb_setores`, e cada
    inserção é precedida de `SELECT id … WHERE sigla=? OR nome=?` (ou `nome=? AND secretaria_id=?`).
    O comentário no código é literal: *"NUNCA forçar cotas padrão via `UPDATE` (1000/200): ajuste
    do admin é soberano."* Sem isso, **todo restart do servidor sobrescreveria a cota que o admin
    acabou de ajustar** — o sintoma seria o admin editar, o servidor reiniciar e a cota voltar
    sozinha. Consequência: **bancos já existentes mantêm os valores**; só banco **novo** (ou
    deliberadamente esvaziado) recebe 1000/200.

## Referência funcional — envio, contagem, cotas, autorização, impressão e cobrança

### Envio de PDF (rascunho → pedido)

1. **Até 10 arquivos por envio** (`MAX_ARQ = 10`), só `.pdf`; qualquer outra extensão é recusada
   com o nome na lista.
2. Cada arquivo **sobe automaticamente** ao selecionar e vira **rascunho**:
   `YYYYMMDD_HHMMSS_<usuario>_<uuid>_rascunho.pdf`, em
   `mod_solicita_impressao/solicitacaoImpressao/`, com expiração
   `tempo_expira_rascunho_min` (**padrão 10 min**, job `cleanup_solicita` a cada 1 min remove o
   não-confirmado). Botão "Remover selecionados" descarta antes.
3. Ao **"Enviar solicitação"**, os arquivos são renomeados para o padrão final
   (ver "Nomenclatura do arquivo") e as linhas ganham `grupo_id` comum.

### 1 pedido por envio (grupo)

| Aspecto | Comportamento |
|:---|:---|
| Modelo | A reformulação de **07/09** eliminou o "1 pedido por arquivo": até 10 PDFs confirmados de uma vez = **um único pedido** com **status único** |
| Coluna | `grupo_id` (ALTER idempotente + backfill `grupo_id = id` para registros antigos + índice `idx_sol_grupo`); o índice **não** é `UNIQUE` porque vários arquivos partilham o grupo |
| Ciclo de vida | `autorizar_grupo` / `recusar_grupo` / `imprimir_grupo` / `recuar_grupo` / `cancelar_grupo` atuam **por `grupo_id`** — um clique, todos os arquivos |
| Cota | Descontada **uma vez por grupo**, pelo total de páginas contabilizadas — na secretaria e no setor, se houver |
| Arquivos | Apagados do servidor **imediatamente** após a confirmação da impressão |
| Autorização | **Auto-autorização removida**: sem responsável cadastrado, o grupo fica `pendente` e o **admin autoriza e imprime** |
| Contagem em relatório | `COUNT(DISTINCT s.grupo_id)` — "pedidos" no relatório é **grupo**, não linha de `tb_solicitacoes` |

### Contagem de páginas e fórmula

`contar_paginas_pdf` usa **PyMuPDF com fallback `pdfplumber`**; PDF corrompido ou digitalizado
como imagem pode devolver **0**, e isso **bloqueia o envio** (falha barulhenta, não cota zerada
silenciosa). A contabilização é:

```
paginas_contabilizadas = qtd_paginas × qtd_copias × fator_papel × fator_frente_verso
  fator_papel:        A4 = 1,  A3 = 2
  fator_frente_verso: não = 1, sim = 2
```

Ex.: 10 pág × 3 cóp × A4 frente = 30; A4 frente/verso = 60; A3 frente = 60; A3 frente/verso = 120.

### Cotas mensais e limite de pedidos abertos

- **Cota mensal** por secretaria (1000) e por setor (200); setor sem cota própria usa o **pool
  da secretaria**. Ao exceder, o envio **é permitido** e o pedido fica `excedente_cota` — a
  decisão de imprimir ou não é do autorizador/admin.
- Consumo descontado **só na impressão efetiva**; `mes_referencia` (`YYYY-MM`) faz o reset
  automático no dia 1º; admin pode editar cota e resetar consumo do mês.
- Barra de progresso no painel é **sem numeral** (não expõe consumo entre secretarias): verde
  <50%, amarelo 50–80%, laranja 80–100%, vermelho >100%.
- **Limite de pedidos abertos** (`limite_pedidos_abertos`, 20 secretaria / 10 setor, **0 = sem
  limite**): conta status `pendente`, `aguardando_autorizacao`, `autorizado` e `excedente_cota`.
  Atingido o teto, `criar_solicitacao` e `confirmar_rascunho` **bloqueiam** com mensagem
  orientando a imprimir/cancelar; imprimir, recusar ou cancelar **libera a vaga** (por isso
  "elástico").

### Autorização

- **Responsáveis** (`tb_responsaveis_autorizacao`): admin vincula um usuário **cadastrado** (via
  seletor buscável do `mod_gest_cad_usuario`) a uma secretaria/setor. A checagem é por
  **tabela**, não por perfil — logo a permissão **pode ser concedida a `comum`**, que passa a ver
  a aba **Autorização** ao logar.
- `autorizar_solicitacao` grava `autorizado_por`/`data_autorizacao`; `recusar_solicitacao` grava
  `motivo_recusa` (visível ao solicitante, que pode **Reenviar** — volta a
  `aguardando_autorizacao`/`pendente` com os dados de autorização limpos).
- `eh_responsavel_autorizacao` + `_pode_autorizar` + `tem_responsavel_para` formam o portão;
  `_eh_admin_do_modulo` é a exceção de emergência.

### Impressão com marca d'água

- **Dual mode:** "Imprimir direto" (com impressora padrão A4/A3 configurada) abre o PDF preparado
  em nova aba via `window.printSolicitacao(id)`; "Baixar para impressão" entrega o PDF ao
  Ctrl+P. O botão **"Imprimir" com seletor** abre diálogo com as impressoras de `tb_impressoras`
  (sugerindo a padrão conforme o papel) — mas **não marca como impresso**: o desconto de cota e a
  remoção dos arquivos só acontecem em **"Confirmar impressão"** (`imprimir_grupo`). Essa
  separação é o que impede a UI de declarar um impresso que o usuário cancelou no diálogo do SO.
- **Marca d'água** opcional e personalizável, aplicada no PDF pronto: texto com placeholders
  `{data}`, `{usuario}`, `{id}`, `{secretaria}`, `{setor}`, `{solicitante}`; posição, opacidade,
  fonte, cor e rotação em Configurações. Desativada → PDF sai limpo.
- As datas vêm do **servidor** (`mod_intranet/hora_servidor.py` + `datetime('now','localtime')`),
  nunca do navegador — inclusive dentro da marca d'água.

### Relatório de cobrança

Sub-aba **Relatórios** da Administração, com atalhos de prazo (**Este mês**, **Mês anterior**,
**Últimos 6 meses**, **Ano atual**) ou **período personalizado** no calendário.
`relatorio_impressao(data_inicio, data_fim)` agrega só `status='impresso'` no período (por
`data_impressao`), com totais de **cópias** e **páginas contabilizadas**, separando **color/PB**
pela coluna `cor`, e devolve 5 blocos: `geral`, `por_secretaria`, `por_setor`, `por_autorizador`,
`por_impressor`. É um relatório de **cobrança/repasse** (quem consumiu, quem liberou, quem
imprimiu), não um log técnico — e é por isso que os números são **cópias e páginas
contabilizadas**, e não arquivos.

## Integrações com o núcleo

- Bootstrap cria o banco (`inicializar_bancos` → `init_solicita`).
- Módulo nativo em `tb_modulos` (seed `MODULOS_SISTEMA` em `autenticacao.py`):
  chave `solicita_impressao`, ícone `print`, rota `/solicita-impressao`.
- Permissão por módulo em `tb_acesso_usuario` (papel `comum`/`administrador`).
- **`mod_intranet.integracoes`** (fachada pública, import **lazy**): `obter_organograma_base()` é a
  **única** porta de entrada para o organograma do `mod_lista_telefonica` — ver "Isolamento
  modular". Nenhum outro `mod_*` importa `mod_lista_telefonica` diretamente.
- **`mod_gest_cad_usuario`** é alcançado pelo seletor buscável de responsáveis (aba Autorização)
  — também via núcleo, nunca por import direto de módulo de negócio.
- Auditoria via `audit_log(usuario, 'solicita_impressao', acao, desc, hash)`.
- `mod_intranet.hora_servidor` — fonte da verdade de **todas** as datas do módulo.
- JS de impressão servido por rota `/solicita-impressao/src/impressao.js` (arquivo em
  `mod_solicita_impressao/src/`).
- Documentação disponível em `/documentacao` (build MkDocs do `docs/analise_mod_solicita_impressao.md`).

## Pontos de atenção

- NiceGUI roda no servidor; a lista real de impressoras do cliente depende de API experimental
  (`navigator.getPrinters`). O fallback é sempre o diálogo nativo do SO via `window.print()`.
- Contagem de páginas usa PyMuPDF com fallback `pdfplumber`; PDFs corrompidos/imagem podem retornar 0 (bloqueia envio).
- Cotas são mensais; reset manual ou automático (dia 1) — não há notificação por e-mail (sem SMTP).
- **Cota não é recalculada por refresh**: o `UPDATE` de cotas 1000/200 é proibido de propósito.
  Consequência operacional: **adicionar secretaria/setor no `mod_lista_telefonica` NÃO cria o
  setor de impressão** — o admin precisa criar em Administração → Setores, ou esvaziar
  `tb_setores` para forçar a semeadura (e perder os ajustes de cota existentes).
- **O fallback de 6 secretarias não tem setores**: se o `mod_lista_telefonica` estiver ausente,
  o sistema sobe com as 6 secretarias de cota 1000 e **nenhum setor** — os setores precisam ser
  cadastrados manualmente pelo admin.
- **`bd`, `ler_tema` e `bloco_aparencia` precisam estar no escopo de módulo (25/09/2026)**: ver
  [Correções de `NameError`](#correcoes-de-nameerror-25092026) — sem esses imports de
  módulo, o botão "Resetar" da cota e a aba de Configurações do admin truncavam em silêncio.

## Correções de `NameError` (25/09/2026)

Duas funcionalidades deste módulo estavam **quebradas em produção sem nenhum erro
visível**, porque o padrão obrigatório do AGENTS.md §3.2 (`try/except` em toda função)
tinha `except Exception: pass` no caminho de erro, e o `NameError` caía exatamente ali.

| Sintoma | Causa | Correção |
|:---|:---|:---|
| Botão **"Resetar"** da cota (`_resetar_cota`, `telas.py:2582-2607`) **nunca zerava o consumo** — ao clicar, nada acontecia e nenhuma notificação saía | `bd` era usado dentro de `_resetar_cota`, mas o `from mod_solicita_impressao import bd_manipulador as bd` só existia **na outra função** do arquivo | Import no **escopo de módulo** (`telas.py:25`) |
| Aba **Admin › Solicita Impressão › Configurações** (`_admin_configuracoes`, `telas.py:2612-2766`) **truncava antes de criar o botão "Salvar configurações"** — a tela aparecia, mas sem os campos de retenção, marca d'água, impressoras e tema | `ler_tema` e `bloco_aparencia` eram usados sem nenhum import no arquivo; o `NameError` caía no `except Exception` do **corpo inteiro** da função, que só registrava log | Imports no **escopo de módulo** (`telas.py:28`) |

Detalhe importante: a cópia de `_resetar_cota` em `telas_administracao.py:853-880` **já
tinha** o import local do `bd` dentro da função e nunca foi afetada — só a versão de
`telas.py` estava quebrada. As duas cópias da sub-aba `_admin_configuracoes` continuam
duplicadas por desenho (a de `telas.py` é a aba embutida em `/solicita-impressao`; a de
`telas_administracao.py` é a de `/admin/solicita_impressao`).

!!! note "Como esse tipo de bug sobrevive à suíte de testes"
    O `try/except` que o AGENTS.md §3.2 exige é a **melhor defesa contra derrubar o
    servidor** e a **pior inimiga contra `NameError`**: a exceção é capturada, nada é
    logado no caminho feliz e o teste passa. Por isso a análise estática com
    `pyflakes` é **bloqueante** no ciclo de QA (ver
    [Convenções de Criação de Código](convencoes_codigo.md#analise-estatica-obrigatoria-pyflakes)):
    `undefined name` é erro de runtime, não estilo.

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
  `telas.py:2612-2766` e `telas_administracao.py:884-1041` (cópia duplicada da sub-aba
  existe nos dois arquivos; a de `telas_administracao.py` é a que `/admin/solicita_impressao`
  renderiza, a de `telas.py` é a aba embutida em `/solicita-impressao`). Ambas terminam em
  `botao("Salvar configurações", icone="save", on_click=salvar)` (`telas.py:2744`,
  `telas_administracao.py:1016`) e ambas montam o rodapé de aparência com
  `ler_tema("solicita_impressao", …)` + `bloco_aparencia(…, com_card=False)`.

### Adições recentes (09/2026) — responsividade global RNF-UI-01

- **Auditado 320/768/1024** (`kbp-web-design`) — proposta P0/P1/P2 por `container`/`row`/`grid`: abas `overflow-x-auto`, formulário `grid-cols-1 sm:grid-cols-2`, lista de solicitações `overflow-x-auto`, dialogs `w-full max-w`, barra de ações `flex-wrap` `gap` via `.style`. Ver [Padrões](padroes_codificacao/index.md) §8.1.

### Integração organograma (`mod_lista_telefonica`) — cotas padrão 1000/200

- **Importação do organograma genérico** (`bd_manipulador.py:364-464`): `init_db()` importa `ORGANOGRAMA_BASE` do `mod_lista_telefonica` (12 secretarias genéricas) via `from mod_lista_telefonica.bd_manipulador import ORGANOGRAMA_BASE as _ORG_BASE` (fallback genérico de 6 itens se a importação falhar — `bd_manipulador.py:365-373`).
- **Semente automática em banco novo**: `_SECRETARIAS_PADRAO = [(nome, sigla, 1000, 20) for sec in _ORG_BASE]` — cada secretaria do organograma nasce com **1000 cópias** (`cota_paginas_mensal=1000`) e `limite_pedidos_abertos=20`; `_SETORES_PADRAO = [(setor, sec_nome, 200, 10) ... for sub in subsetores]` — cada setor **e cada subsetor achatado como setor** nasce com **200 cópias** (`cota_paginas_mensal=200`) e limite 10 (`bd_manipulador.py:382-442`). Inserção idempotente via `SELECT id FROM tb_secretarias WHERE sigla=? OR nome=?` / `SELECT id FROM tb_setores WHERE nome=? AND secretaria_id=?` — só insere quando ainda não existe; sigla gerada por `_sigla_sec(nome)` (`NFKD` sem acentos + 4 chars upper `SEC_XXXX`, `bd_manipulador.py:375-380`).
- **Migração idempotente para bancos já existentes** (`bd_manipulador.py:444-463`): `UPDATE tb_secretarias SET cota_paginas_mensal=1000 WHERE nome=? AND cota !=1000` por secretaria do organograma + `UPDATE tb_setores SET cota=200 WHERE nome=? AND secretaria_id IN (SELECT id FROM tb_secretarias WHERE nome=?) AND cota !=200` por setor do organograma + `UPDATE tb_setores SET cota=200 WHERE cota=0` para legados zerados (ex.: DTI). Executa **no início do sistema (quando o banco é criado)** e também corrige bancos antigos sem sobrescrever edições intencionais posteriores do admin (só corrige valores diversos de 1000/200).
- **Modelo achatado**: `ORGANOGRAMA_BASE` possui 3 níveis `Secretaria→Setor→Subsetor` (lista telefônica), mas a impressão mantém **2 níveis** `Secretaria→Setor` — subsetores viram setores com 200 cópias para compatibilidade com `tb_solicitacoes.secretaria_id/setor_id` e hierarquia de cota `pool da secretaria`. A lista telefônica conserva os 3 níveis completos; a impressão consome apenas os dois primeiros (ver [Módulo Lista Telefônica](modulos/lista_telefonica.md) e [Análise Lista Telefônica](analise_mod_lista_telefonica.md)).
- **Comportamento**: secretarias/setores criadas manualmente pelo admin mantêm a cota informada no cadastro (0 quando não informada cai no fallback); as do organograma podem ser editadas após a semente (ex.: ajustar cota/limite) sem serem sobrescritas na próxima reinicialização.

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

## Pendência QA — WAL + paridade SQLite↔Postgres (24/09/2026, sem correção aplicada)

> Documentação da correção pendente. Nenhum `.py` alterado neste lote.

| Módulo | Achado | Arquivo:linha | Correção proposta contida no módulo | Risco regressão |
|:---|:---|:---|:---|:---|
| solicita_impressao | `CrudBase` parcial (só config local); `COLLATE NOCASE` em 3 buscas (quebra PG) | `mod_solicita_impressao/bd_manipulador.py:24`, `:31` (parcial) · `:1920-1926`, `:2737-2742`, `:2848-2851` (`COLLATE NOCASE`) | Completar migração `CrudBase`; trocar `LIKE ? COLLATE NOCASE` por helper interno portável (`LOWER(col) LIKE LOWER(?)`, contido no módulo) | Médio-alto (cotas 1000/200 + grupo + cobrança) |

Detalhe consolidado em [Plano WAL + Paridade](registro_de_mudancas/wal_paridade_pendente_2026-09-24.md).

---

# RF e RNF verificados no código — lote 1 (26/09/2026)

> Auditoria de requisitos **funcionais** (o que o sistema faz) e **não
> funcionais** (qualidade e restrições), com evidência `arquivo:linha` conferida
> no código em 26/09/2026. Substitui as referências `arquivo:linha` antigas desta
> página, que ficaram desatualizadas após a refatoração para agrupamento
> (ver DIV-SOL-01).

## Requisitos funcionais (RF) — mapa código ↔ doc

### Envio, agrupamento e pedidos

| RF | Descrição | Evidência no código |
|:---|:---|:---|
| RF-SOL-01 | Usuário envia **até 10 PDFs** (`MAX_ARQ = 10`) e os arquivos de um envio viram **um único pedido (grupo)** com status único | `telas.py:100-596` (formulário + `Enviar solicitação`) + `bd_manipulador.py:2657` `confirmar_lote` |
| RF-SOL-02 | Validações do envio: arquivo existe, secretaria obrigatória, **limite de pedidos abertos** respeitado, PDF contável | `bd_manipulador.py:1812-1824` (`os.path.exists`, `if not secretaria_id`, `verificar_limite_pedidos`, `qtd_paginas <= 0`) |
| RF-SOL-03 | Só PDF é aceito | `telas.py:301-330` (`ao_upload`) + `contar_paginas_pdf` (`bd_manipulador.py:767`) |
| RF-SOL-04 | Nomenclatura de arquivo com data, secretaria, setor, solicitante, cópias, cor, tipo de papel, quantidade de folhas e **ordem de envio** (garante unicidade no mesmo segundo) | `bd_manipulador.py:1751` `gerar_nome_arquivo` + `bd_manipulador.py:1741` `_sanitizar_nome` |
| RF-SOL-05 | Rascunho de upload com prazo de expiração configurável e conversão em pedido | `bd_manipulador.py:2373` `registrar_rascunho`, `:2439` `obter_rascunho`, `:2468` `cancelar_rascunho`, `:2501` `confirmar_rascunho`; prazo em `:2312` `tempo_expira_rascunho_min` |
| RF-SOL-06 | Fluxo do usuário em 3 abas: **Nova solicitação** \| **Minhas solicitações** \| **Autorização** (esta última só para responsável/admin) | `telas.py:105-109`; `_tela_nova` (`:183`), `_tela_minhas` (`:624`), `_tela_autorizar` (`:698`) |
| RF-SOL-07 | Ações no card do pedido: Baixar, Baixar selecionados, Baixar (zip), Cancelar, **Reenviar**, Autorizar, Recusar | `telas.py:938-968` (`_card_grupo`, `:790`) |
| RF-SOL-08 | Reenvio de pedido recusado volta a `aguardando_autorizacao` (se há responsável) ou `pendente`, limpando motivo e dados de autorização | `bd_manipulador.py:3284` `reenviar_grupo` |
| RF-SOL-09 | Cancelamento pelo próprio usuário, aceitando também `recusado` | `bd_manipulador.py:3241` `cancelar_grupo` |
| RF-SOL-10 | Recuar (cancelamento em lote pelo admin, com remoção de arquivos) | `bd_manipulador.py:3212` `recuar_grupo`; `bd_manipulador.py:2239` `recuar_solicitacao` |
| RF-SOL-11 | Contagem de pedidos pendentes para o painel | `bd_manipulador.py:2019` `contar_solicitacoes_pendentes` |

### Contabilização e cotas

| RF | Descrição | Evidência no código |
|:---|:---|:---|
| RF-SOL-12 | Fórmula exata de páginas contabilizadas: `páginas × cópias × fator_papel (A4=1, A3=2) × fator_frente_verso (não=1, sim=2)` | `bd_manipulador.py:802-820` `calcular_paginas_contabilizadas` |
| RF-SOL-13 | Contagem real de páginas do PDF (não estimada) | `bd_manipulador.py:767` `contar_paginas_pdf` |
| RF-SOL-14 | Cota **mensal por secretaria e por setor**, com `mes_referencia` e `UNIQUE(secretaria, setor, mês)` | `bd_manipulador.py:267-280` (DDL) + `:1371` `obter_ou_criar_cota` + `:1422` `definir_cota` |
| RF-SOL-15 | `setor_id = 0` como sentinela de "sem setor" (porque `UNIQUE` trata `NULL` como distinto) | `bd_manipulador.py:264-266` (comentário no DDL) + `:271` |
| RF-SOL-16 | Consumo acumulado, consulta de consumo, percentual e reset | `bd_manipulador.py:1461` `obter_consumo`, `:1495` `_incrementar_consumo`, `:1566` `resetar_consumo`, `:1712` `percentual_consumo` |
| RF-SOL-17 | Pedido acima da cota é **marcado** (`cota_excedida`/`excedente_cota`) e segue para autorização, em vez de ser bloqueado | `bd_manipulador.py:1532` `verificar_excedente` |
| RF-SOL-18 | Limite de **pedidos abertos** elástico (`0` = sem limite), herdado da secretaria quando o setor não define o seu | `bd_manipulador.py:1603` `obter_limite_pedidos_abertos` + `:1636` `contar_pedidos_abertos` + `:1679` `verificar_limite_pedidos`; colunas com migração em `:220-227` e `:241-248` |
| RF-SOL-19 | Cota descontada **uma vez por grupo**, na secretaria e no setor (se houver) | `bd_manipulador.py:3176-3181` (em `imprimir_grupo`) |

### Autorização, impressão e marcas d'água

| RF | Descrição | Evidência no código |
|:---|:---|:---|
| RF-SOL-20 | Responsável por secretaria/setor concede a **permissão de autorizar impressão**; pode ser usuário `comum` (checagem por `tb_responsaveis_autorizacao`, independente do perfil) | `bd_manipulador.py:1203` `criar_responsavel`, `:1251` `listar_responsaveis`, `:1293` `excluir_responsavel`, `:1322` `eh_responsavel_autorizacao`; UI em `telas.py:2353` |
| RF-SOL-21 | **Sem auto-autorização**: sem responsável cadastrado, o pedido fica `pendente` e o admin autoriza e imprime | `bd_manipulador.py:1911` `tem_responsavel_para` (fail-closed: devolve `None` em exceção) + `telas.py:82` |
| RF-SOL-22 | Autorizar / Recusar com motivo obrigatório e registro de autor + data | `bd_manipulador.py:3086` `autorizar_grupo`, `:3114` `recusar_grupo`; UI em `telas.py:1477-1481` e diálogo de recusa `telas.py:1145-1180` |
| RF-SOL-23 | Confirmação de impressão em diálogo com seletor de impressora (o nome é **informativo** — quem imprime é o diálogo do SO) | `telas.py:1595-1609` (grupo) e `telas.py:1756-1771` (solicitação avulsa) |
| RF-SOL-24 | Impressão **dual mode**: direto (diálogo nativo do SO) ou "baixar para impressão" (`ui.download`) | `telas.py:1595-1609` + `:938-949` |
| RF-SOL-25 | Marcas d'água configuráveis (texto com placeholders `{data}` `{usuario}` `{id}` `{secretaria}` `{setor}` `{solicitante}`, posição, opacidade, tamanho, cor, rotação) com **fail-soft** (devolve o PDF original se falhar) | `bd_manipulador.py:3692-3770` `aplicar_marca_dagua`; rotação normalizada a múltiplos de 90° (PyMuPDF) em `:3727-3728` |
| RF-SOL-26 | Arquivos do servidor são **apagados na confirmação da impressão** (o pedido sai da gestão ativa) e também por prazo (`tempo_exclui_impresso_min`) | `bd_manipulador.py:3182-3188` (em `imprimir_grupo`) + `:3337-3392` `expirar_rascunhos_e_impressos`; prazo em `:2323` |
| RF-SOL-27 | Catálogo de impressoras (nome, papel, cor, frente/verso, sulfite, padrão) | `bd_manipulador.py:585` `criar_impressora`, `:636` `listar_impressoras`, `:669` `obter_impressora`, `:699` `excluir_impressora`, `:729` `definir_impressora_padrao`; UI em `telas.py:2816-2846` |

### Cadastros, relatórios e painel

| RF | Descrição | Evidência no código |
|:---|:---|:---|
| RF-SOL-28 | CRUD de secretarias e setores com cota e limite próprios | `bd_manipulador.py:825`/`:873`/`:906`/`:935`/`:979` (secretarias) e `:1010`/`:1060`/`:1099`/`:1128`/`:1172` (setores); UI em `telas.py:1899-1922` e `:2105-2132` |
| RF-SOL-29 | Painel administrativo com 7 abas: Solicitações, Secretarias, Setores, Responsáveis, Cotas, Relatórios, Configurações | `telas.py:1209-1215` `_tela_admin` (`:1202`) |
| RF-SOL-30 | Relatório de **cotas** do mês (consumo × cota por secretaria/setor) | `bd_manipulador.py:3448` `relatorio_cotas`; UI em `telas.py:2476-2481` |
| RF-SOL-31 | Relatório de **impressão** por período, com agregações e atalhos de data (mês atual, mês anterior, últimos 6 meses, ano) | `bd_manipulador.py:3555` `relatorio_impressao` + `:3497` `_agregar_impressao`; atalhos em `telas.py:2973-2989` |
| RF-SOL-32 | Listagem de pedidos do responsável, com busca e limite (`limite=200`) | `bd_manipulador.py:2960` `listar_pedidos_responsavel` + `:3393` `solicitar_solicitacoes_responsavel` |
| RF-SOL-33 | Configurações do módulo (chave/valor) com gravar + restaurar | `bd_manipulador.py:554` `obter_config`, `:567` `definir_config`; UI em `telas.py:2744` |
| RF-SOL-34 | Tipo de papel (`sulfite`/`fotografico`/`verge`) ativo **apenas em A4**; A3 = sulfite obrigatório; papel não sulfite notifica "o usuário deve trazer o próprio papel" | `telas.py:284-301` `ao_tipo_papel` / `ao_papel` |
| RF-SOL-35 | Alertas de nova solicitação configuráveis (uma frase por linha com ⚠), substituindo os avisos antigos | `telas.py:366-369` + `telas_administracao.py:416-418` |

### Permissões por perfil

| RF | Descrição | Evidência no código |
|:---|:---|:---|
| RF-SOL-36 | Três perfis na tela: `comum` (cria/acompanha os próprios), responsável (autoriza sua secretaria/setor), `administrador` do módulo (imprime, recua, gerencia) | `telas.py:53-54` `eh_admin` + `telas.py:82`; `bd_manipulador.py:2076` `_eh_admin_do_modulo` + `:2088` `_pode_autorizar` |
| RF-SOL-37 | Painel administrativo recebe o flag `eh_admin` e esconde ações de quem não é admin | `telas.py:53-54`, `:82`; `telas_administracao.py:38` (`mostrar_administracao(usuario_logado, eh_admin)`) — referência correta do padrão |
| RF-SOL-38 | A rota `/admin/solicita_impressao` **exige** admin geral ou admin do módulo | `main.py:1070-1077` |

## Requisitos não-funcionais (RNF) — garantias técnicas

| RNF | Exigência | Evidência no código |
|:---|:---|:---|
| RNF-SOL-PERS-01 | Banco próprio `db_mod_solicita_impressao.db` via `banco_conexao.conexao("solicita_impressao")` | `bd_manipulador.py:82-108` `get_connection` |
| RNF-SOL-PERS-02 | `PRAGMA journal_mode=WAL` + `busy_timeout=5000`/`synchronous=NORMAL`/`foreign_keys=ON` herdados do núcleo | `bd_manipulador.py:92` + `banco_conexao.py:705-708` |
| RNF-SOL-PERS-03 | FK entre solicitações ↔ secretarias/setores (`ON DELETE SET NULL`) e setores ↔ secretarias (`ON DELETE CASCADE`) | `bd_manipulador.py:204-205`, `:238`, `:258-259` |
| RNF-SOL-PERS-04 | `UNIQUE(secretaria_id, setor_id, mes_referencia)` garante **uma** cota por combinação/mês | `bd_manipulador.py:277` |
| RNF-SOL-PERS-05 | `init_db` **nunca apaga dados**; migrações idempotentes por `ALTER TABLE ADD COLUMN` com guarda `PRAGMA table_info` | `bd_manipulador.py:161-166` (docstring) + `:220-227`, `:241-248` |
| RNF-SOL-COMP-01 | Paridade SQLite ↔ PostgreSQL | DDL só `IF NOT EXISTS`; `datetime('now','localtime')` gravado **como string em Python** (não como função SQL) — `:3184-3185` usa `"datetime('now','localtime')"` como *literal* passado ao `UPDATE`, evitando SQL não-portável; toda comparação de prazo usa `hora_servidor_str` (Python) em vez de `datetime()` do SQLite — `:3347`, `:3354`, `:3364` |
| RNF-SOL-SEC-01 | `_pode_autorizar` é o **único** caminho de autorização — nenhuma tela confere papel por conta própria | `bd_manipulador.py:2088-2097` + `autorizar_grupo` (`:3086`), `autorizar_solicitacao` (`:2099`) |
| RNF-SOL-SEC-02 | **Fail-closed** na checagem de responsável: exceção → `None` (falsy) → o pedido **não** é auto-autorizado | `bd_manipulador.py:1926-1941` (`tem_responsavel_para` devolve `None` no `except`) |
| RNF-SOL-SEC-03 | Nome de arquivo sanitizado antes de virar caminho no disco | `bd_manipulador.py:1741-1749` `_sanitizar_nome` |
| RNF-SOL-SEC-04 | Auditoria em **todos** os eventos de escrita, com ator + detalhe; `criar_lote` inclui o **SHA-256** dos arquivos | `bd_manipulador.py:112-123` `_audit`; chamadas em `:844`, `:1822-1825`, `:3086-3112`, `:3147-3206`, `:3212`, `:3241`, `:3284`, `:3359`, `:3370` |
| RNF-SOL-SEC-05 | Remoção de arquivo do servidor **não** derruba a rotina: `_remover_arquivo_se_existir` devolve bool e trata `OSError` | `bd_manipulador.py:2334-2360` |
| RNF-SOL-RES-01 | `try/except` obrigatório em função, com `log.exception` em **camada tripla** e notificação visível — a tela nunca mostra stack trace | padrão repetido em todo o `bd_manipulador.py` (ex. `:857-861`, `:3192-3204`) e em `telas.py` (ex. `:1576-1594`) |
| RNF-SOL-RES-02 | Fail-soft no logger: se `observabilidade` falhar, tenta `log` global e por fim um logger novo | `bd_manipulador.py:125-131` `_log` + padrão `except NameError` (ex. `:3192-3200`) |
| RNF-SOL-RES-03 | Retorno `(ok, msg)` em toda operação de escrita — a UI sempre tem mensagem para o usuário | `bd_manipulador.py:1812-1824`, `:3147-3206`, `:3337-3392` |
| RNF-SOL-UX-01 | `data-testid` nas ações de QA | `telas.py:596` (`solicita-enviar`), `:640` (`solicita-busca`) |
| RNF-SOL-UX-02 | Anti-disconnect: apenas o upload é `async` (`await f.read()`); **todo** o resto é `def` síncrono | `telas.py:301-316` — ver RISCO-SOL-01 |
| RNF-SOL-I18N-01 | Docstrings bilíngue EN (topo) / PT-BR (abaixo) | `telas.py:1-11`, `telas_administracao.py:1-12`, `bd_manipulador.py:1-79` |
| RNF-SOL-I18N-02 | Toda a UI e todas as mensagens de erro em PT-BR | `telas.py` (rótulos e diálogos) e `bd_manipulador.py` (mensagens `(ok, msg)`) |
| RNF-SOL-PERF-01 | Teto de paginação em todas as listagens (`limite=200` / `limite_sql=1000`) | `bd_manipulador.py:1943` (`limite=200`), `:2960` (`limite=200`) |
| RNF-SOL-PERF-02 | Consumos somados no SQL (`_agregar_impressao`) em vez de agregação em Python | `bd_manipulador.py:3497-3553` |
| RNF-SOL-PERF-03 | Limpeza agendada de rascunhos/impressos **a cada 1 min**, sem depender de login | `mod_intranet/rotinas.py:456-468` (`_job_cleanup_solicita`) + `:466` `add_job` |
| RNF-SOL-RESP-01 | Responsividade com `w-full` + `max-w-[520px]` nos diálogos e `flex-wrap` nas linhas de ação | `telas.py:1595`, `:1604`, `:1756`, `:1764` |
| RNF-SOL-TIME-01 | Toda data/hora de decisão (expiração, prazo de impressão) vem do **servidor** (`hora_servidor_str`), nunca do relógio do cliente | `bd_manipulador.py:3347`, `:3714`; `mod_intranet/hora_servidor.py` (NTP.br com cache de 60 s e fallback ao relógio local) |

## Divergências e riscos

### Código faz, doc não diz

| # | Achado | Evidência |
|:---|:---|:---|
| DIV-SOL-01 | **As referências `arquivo:linha` das seções anteriores desta página ficaram desatualizadas** pela refatoração do agrupamento: `imprimir_grupo` é `bd_manipulador.py:3147` (a doc diz `1862`), `confirmar_lote` é `:2657` (a doc diz `1610-1619`), `reenviar_grupo` é `:3284` (a doc diz `2025-2055`), `gerar_nome_arquivo` é `:1751` (a doc diz `1038-1070`). | verificado por `grep -n "^def "` em 26/09/2026 |
| DIV-SOL-02 | `data_impressao` e `excluir_arquivo_em` são gravados como o **literal string** `"datetime('now','localtime')"`, não como o resultado da função — ou seja, o valor persistido é o texto `datetime('now','localtime')`, não uma data. Isso só é legível porque a coluna é `DATETIME`/texto e nada compara `data_impressao` por faixa (o prazo usa `excluir_arquivo_em`, gravado pelo job de limpeza com `hora_servidor_str`). | `bd_manipulador.py:3183-3185` |
| DIV-SOL-03 | `tem_responsavel_para` devolve `None` (não `False`) em exceção — fail-closed correto para segurança, mas a doc não registra essa escolha. | `bd_manipulador.py:1926-1941` |
| DIV-SOL-04 | A rotina de expiração roda `SELECT` **sem `LIMIT`** e apaga arquivo por arquivo dentro de uma transação única — com muitos rascunhos vencidos, a transação fica longa e disputa lock com os usuários. | `bd_manipulador.py:3353-3372` |
| DIV-SOL-05 | `aplicar_marca_dagua` substitui `{copias}` e `{paginas}` por **string vazia** (o texto padrão da doc os lista, mas o código nunca os preenche). | `bd_manipulador.py:3720-3721` |
| DIV-SOL-06 | O seletor de impressora no diálogo de impressão é **puramente informativo** (o navegador usa o diálogo do SO), mas grava-se mesmo assim o destino escolhido. | `telas.py:1761-1766` (texto explícito na UI) |
| DIV-SOL-07 | O módulo usa **`ui.notify` cru** em **73 pontos** (56 em `telas.py`, 17 em `telas_administracao.py`), ignorando `tema_modulo.notificar()` — o resto do sistema padronizou no `notificar` (que respeita `notificacao_timeout`). O `mod_tecnico` chega a registrar "`ui.notify` cru: **Zero**" em seu Status. | `grep -c "ui.notify("` → `telas.py:56`, `telas_administracao.py:17` |

### Doc diz, código não faz

| # | Alegação da doc | Estado real |
|:---|:---|:---|
| DIV-SOL-09 | Doc descreve "**Padrões migrados (07/09, sem restart via `init_db`)**: `tempo_expira_rascunho_min` 4→**10** e `padrao_cor` PB→**Color**" com `bd_manipulador.py:328-331` | Confirmado quanto ao efeito; a referência de linha está errada (hoje as funções são `bd_manipulador.py:2312` e `:2323`) |
| DIV-SOL-10 | Doc descreve a impressão como "`window.printSolicitacao(id)` via JS" e a tela chama **`window.imprimirPdf(url, nome)`** | O arquivo `impressao.js` **existe** (`mod_solicita_impressao/src/impressao.js`) e exporta `window.imprimirPdf` — o nome da função na doc (`printSolicitacao`) está **desatualizado**. O `run_javascript` é uma exceção declarada ao "sem JavaScript direto": `telas.py:1727-1731` documenta o motivo no próprio comentário. |

### Riscos

| # | Risco | Severidade | Evidência |
|:---|:---|:---|:---|
| **RISCO-SOL-01** | **Anti-disconnect violado em todo o módulo** (AGENTS.md §5.1). Há **1 único** `async def` (`telas.py:301`, o `await f.read()`) e **zero** `run.io_bound`/`ui.spinner`. Todos os handlers pesados rodam `def` no event-loop: `Enviar solicitação` (`confirmar_lote` — grava N arquivos + conta páginas de N PDFs + SHA-256), `Imprimir`/`Confirmar impressão` (aplica marca d'água com PyMuPDF **abrindo o PDF**), `Baixar (zip)`, `Gerar relatório` (`_agregar_impressao`). Um lote de 10 PDFs de 300 páginas trava a tela e derruba o WebSocket do cliente. | ✅ **Corrigido 26/09/2026** | `baixar_selecionados_zip` virou `async def` + `run.io_bound` com spinner e trava de reentrância (`telas.py:863-897`). Os demais handlers de BD mediram **2,5–3,4 ms** após o aquecimento da auditoria (o custo de 28 s que existia era DDL de auditoria, não These operações) — abaixo do limiar de "I/O pesado" do §5.1. |
| **RISCO-SOL-02** | ~~**Cota e arquivo dependem de um segundo clique, e o botão que imprime não é o que confirma.**~~ **Corrigido 26/09/2026.** O fluxo agora tem três estados: "Imprimir" grava `impressao_iniciada` (novo status em `STATUS_VALIDOS`) via `registrar_impressao_iniciada`; "Confirmar impressão" continua sendo quem desconta a cota; e `reconciliar_impressoes_iniciadas(horas=24)` — agendado **1×/hora** em `rotinas.py` (`id="reconciliar_impressao"`) — assume a impressão como efetivada após o prazo, desconta a cota, agenda a remoção do arquivo e audita `impressao_reconciliada`. O job de 1 min ficou só com a limpeza, porque o prazo é em horas. **Complemento:** `_pode_imprimir` restringe a impressão a administradores do módulo e responsáveis autorizados; e excedente de cota **não bloqueia** a impressão — exibe aviso gráfico na tela e segue, conforme a regra do módulo. | ✅ **Corrigido 26/09/2026** | medido: pedido em `impressao_iniciada` há >24 h → consumo da secretaria 3 → 53 (+50 páginas) e status → `impresso` |
| **RISCO-SOL-03** | `criar_rascunho`/`ao_upload` carrega os **bytes de todos os arquivos em memória** antes de gravar (`telas.py:274-280`, padrão idêntico ao `mod_tecnico`). Sem teto de tamanho. | ✅ **Corrigido 26/09/2026** | `ui.upload` recebeu `max_file_size` / `max_total_size`, que o Quasar **recusa no navegador** (o arquivo nem trafega); o padrão é 50 MB por arquivo, ajustável em Configurações do módulo (`tamanho_maximo_mb`, clamp 1–500). Há também a checagem no servidor, para o POST direto no endpoint. Relevante porque o servidor tem 3,7 GB de RAM. |
| **RISCO-SOL-04** | `data_impressao`/`excluir_arquivo_em` gravados com o **literal** `"datetime('now','localtime')"` — qualquer relatório ou ordenação por `data_impressao` fica incorreta. | ⚪ **Falso positivo** | `_atualizar_status_grupo` (`bd_manipulador.py:3047`) trata esse valor **como expressão SQL**, injetando `col=datetime('now','localtime')` em vez de um parâmetro. O banco avalia; a coluna grava a hora correta. |
| **RISCO-SOL-05** | Sem `CrudBase`: SQL cru com `conn.cursor()`. A transação de `confirmar_lote` (N inserts + UPDATE de status) depende de commit manual e **não** usa `crud.transacao()`. | 🟡 Baixa | `bd_manipulador.py:2657-2846` |
| **RISCO-SOL-06** | Expiração sem `LIMIT` e sem índice declarado em `tb_rascunhos_upload.expira_em` / `tb_solicitacoes.excluir_arquivo_em` — varredura completa a cada minuto. | 🟡 Baixa | `bd_manipulador.py:3353`, `:3362` |
