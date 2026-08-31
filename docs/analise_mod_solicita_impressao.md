# Solicitação de Impressão — `mod_solicita_impressao`

> Print request module: route `/solicita-impressao` (key `solicita_impressao`) · own database `db_mod_solicita_impressao.db` · PDF upload, page counting, hierarchical monthly quotas, dual-mode print, central audit.

---

# Solicitação de Impressão — `mod_solicita_impressao`

> Módulo de solicitação de impressão: rota `/solicita-impressao` (chave `solicita_impressao`) · banco próprio `db_mod_solicita_impressao.db` · envio de PDF, contagem de páginas, cotas mensais hierárquicas, impressão dual, auditoria central.
>
> **Versionamento**: `versao_modulo:solicita_impressao = 1.0.260829` (seed em `conexao_bd.init_db()` — chave `tb_config` central, formato `1.0.AAMMDD`, exibida no rodapé em `/solicita-impressao` junto à versão global). Duplicada também em `tb_configuracoes_modulo` (`versao_modulo`) do banco do módulo. Atualizar a cada alteração do módulo.

## Propósito

Módulo para solicitação de impressão de arquivos PDF. Usuários **comuns** anexam um PDF por
solicitação, informam cópias, papel (A4/A3), cor (PB/Color), frente e verso (borda curta/longa),
se o papel é sulfite, observações e a secretaria/setor de crédito. O sistema conta as páginas,
renomeia o arquivo no padrão definido, aplica regras de cota mensal (hierárquica) e fluxo de
autorização quando exigido. Apenas administradores do módulo imprimem; responsáveis cadastrados
autorizam quando a secretaria/setor exige.

## Banco próprio

Criador vigente: `init_db()` em `manipulador_bd.py` (bootstrap central
`mod_intranet_inicializacao_bd.inicializar_bancos`).

Todas as tabelas vivem em `db_mod_solicita_impressao.db` (WAL). Arquivos PDF enviados são salvos
em `mod_solicita_impressao/solicitacaoImpressao/` (pasta própria do módulo — nada é misturado
com outros módulos).

### Tabelas

- **`tb_solicitacoes`**: id, usuario_solicitante, arquivo_original, arquivo_servidor,
  caminho_arquivo, hash_arquivo, qtd_copias, tamanho_papel (A4/A3), cor (PB/Color),
  frente_verso (0/1), tipo_borda (curta/longa/NULL), papel_sulfite (0/1), observacoes,
  secretaria_id FK, setor_id FK, qtd_paginas_arquivo, paginas_contabilizadas, status,
  cota_excedida (0/1), requer_autorizacao (0/1), autorizado_por, data_autorizacao,
  motivo_recusa, impresso_por, data_impressao, data_criacao, data_atualizacao.
- **`tb_secretarias`**: id, nome, sigla, cota_paginas_mensal, ativo.
- **`tb_setores`**: id, nome, secretaria_id FK, cota_paginas_mensal, ativo.
- **`tb_responsaveis_autorizacao`**: id, user_nome, secretaria_id FK, setor_id FK (opcional), ativo.
- **`tb_cotas_impressao`**: id, secretaria_id, setor_id (NULL=secretaria), cota_paginas,
  mes_referencia (YYYY-MM, único por vínculo), ativo.
- **`tb_consumo_cota`**: id, secretaria_id, setor_id, mes_referencia, paginas_usadas, atualizado_em.
- **`tb_configuracoes_modulo`**: chave/valor (pasta, max MB, aviso presença, impressoras padrão,
  marca d'água opcional e personalizável).

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
- Visual no painel: barra de progresso — verde <80%, amarelo 80–99%, vermelho ≥100%.
- Admin pode **editar cota** e **resetar consumo** do mês. Sem notificações (por design).
- Reset automático todo dia 1º (novo `mes_referencia`).

## Fluxo de tela

- **Nova Solicitação** (comum): ao **selecionar o PDF** ele sobe **automaticamente para o servidor**
  e já é **renomeado** (o nome original é descartado — não influencia o sistema). O arquivo fica
  como **rascunho** com nome `YYYYMMDD_HHMMSS_usuario_rascunho.pdf` e expiração de
  `tempo_expira_rascunho_min` (padrão 4 min): se o usuário não confirmar ("Enviar solicitação")
  nesse prazo, o arquivo é **removido do servidor automaticamente** (job `cleanup_solicita`, 1 min).
  Há botão "Remover arquivo" para descartar antes. Após confirmar, o arquivo é renomeado para o
  padrão final `dataHora_usuario_copias_paginas_secretaria_setor.pdf` e vira solicitação.
- Valores **padrão pré-selecionados** (editáveis pelo admin): papel `padrao_papel` (A4),
  cor `padrao_cor` (PB), `padrao_frente_verso` (somente frente) e `padrao_sulfite` (sim).
- Campos: cópias, papel, cor, frente/verso + borda, sulfite com aviso, observações, secretaria→setor;
  aviso fixo de presença obrigatória; pré-visualização do nome do arquivo.
- **Impressão** (admin): ao marcar "impresso", a cota é descontada e o arquivo é agendado para
  **exclusão automática** após `tempo_exclui_impresso_min` (padrão 10 min). Recusar / recuar /
  cancelar **removem o arquivo do servidor** imediatamente.
- **Auditoria** (`tb_auditoria` central, módulo `solicita_impressao`): registra quem **solicitou**
  (cópias, páginas, secretaria, setor, status, excedente), quem **autorizou**, quem **imprimiu**
  (com total de páginas e prazo de exclusão) e quem **recusou** (com motivo).
- **Minhas Solicitações** (comum): lista própria com status (chip colorido), barra de cota,
  botão Baixar e Cancelar (se pendente/aguardando/excedente).
- **Autorização** (responsável): lista pendentes de sua secretaria/setor, Autorizar / Recusar
  (motivo obrigatório).
- **Administração** (admin do módulo): tabela mestra + sub-abas Secretarias, Setores,
  Responsáveis, Cotas, Configurações. Ações: Imprimir direto (se impressora configurada),
  Baixar (sempre), Recuar (cancelar), Autorizar, Recusar.

## Impressão (dual mode)

- Se **impressora padrão** configurada (A4/A3): botão "Imprimir direto" dispara
  `window.printSolicitacao(id)` via JS (`impressao.js` em `src/`) — abre o PDF preparado numa
  nova aba e usa o diálogo nativo do SO.
- Sempre disponível: **Baixar para impressão** (`ui.download` do PDF, com marca d'água se ativa) →
  usuário imprime via Ctrl+P no navegador/SO.
- **Marca d'água** (opcional, personalizável): texto com placeholders `{data}`, `{usuario}`,
  `{id}`, `{secretaria}`, `{setor}`, `{solicitante}`; posição, opacidade, fonte, cor, rotação —
  tudo configurável em Configurações. Se desativada, PDF sai sem marca.

## Nomenclatura do arquivo

```
YYYYMMDD_HHMMSS_usuario_copias_paginas_secretaria_setor.pdf
```

Ex.: `20260829_143022_joao_silva_3_10_SECRETARIA_SAUDE_ATENDIMENTO.pdf`
(acentos removidos, espaços→`_`, nomes sanitizados).

## Regras de negócio

- **Somente PDF**: upload recusa extensões não-`.pdf`.
- **1 arquivo por solicitação**: `max_files=1`.
- **Aviso papel não sulfite**: se desmarcado, notifica "usuário deve levar o papel".
- **Aviso presença**: fixo no formulário ("documentos só impressos com presença para retirada").
- **Permissões**: `comum` cria/acompanha próprias; responsável autoriza sua secretaria/setor;
  `administrador` do módulo imprime/recua/gerencia. Admin geral vê tudo + auditoria.
- **Concessão da permissão de autorizar impressão**: em *Administração → Responsáveis* o admin
  localiza um **usuário cadastrado** via seletor buscável (do módulo de Gestão de Usuários) e o
  vincula a uma secretaria/setor como responsável. A permissão **pode ser concedida a usuários
  `comum`** — ao logar, mesmo sendo `comum`, o usuário passa a ver a aba **Autorização** e a
  área de autorizar impressões (a checagem usa `tb_responsaveis_autorizacao`, independente do perfil).
- **Auditoria central** (`tb_auditoria`): `criar_solicitacao`, `autorizar_solicitacao`,
  `recusar_solicitacao`, `imprimir_solicitacao`, `recuar_solicitacao`, `cancelar_solicitacao`,
  `criar/editar/excluir_secretaria/setor/responsavel`, `definir_cota`, `resetar_consumo`.

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

## Status

| Item | Situação |
|:---|:---|
| Banco + 7 tabelas + cotas | Implementado |
| Contagem páginas + fórmula exata | Implementado |
| Fluxo comum (criar/acompanhar) | Implementado |
| Autorização por responsável | Implementado |
| Admin (imprimir/recuar/cadastros/cotas/config) | Implementado |
| Impressão dual (direto + download) + marca d'água | Implementado |
| Auditoria central | Implementado |
| Documentação MkDocs | Implementado |
| Testes manuais (qacomum/qamaster) | Pendente |
