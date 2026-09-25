# Print Request Module — `mod_solicita_impressao`

> Print request module: route `/solicita-impressao` (key `solicita_impressao`) · own database `db_mod_solicita_impressao.db` · PDF upload, page counting, hierarchical monthly quotas, dual-mode print, central audit · **shared organogram obtained through the core facade (`mod_intranet.integracoes.obter_organograma_base()`, with a 6-secretariat local fallback) drives the default quotas 1000/200**.

---

# Módulo Solicitação de Impressão — `mod_solicita_impressao`

> Módulo de solicitação de impressão: rota `/solicita-impressao` (chave `solicita_impressao`) · banco próprio `db_mod_solicita_impressao.db` · envio de PDF, contagem de páginas, cotas mensais hierárquicas, impressão dual, auditoria central · **organograma compartilhado obtido pela fachada do núcleo (`mod_intranet.integracoes.obter_organograma_base()`, com fallback local de 6 secretarias) é a fonte das cotas padrão 1000/200**.

## Propósito

Módulo para solicitação de impressão de PDFs. Usuários **comuns** anexam até 10 PDFs por envio (upload automático assíncrono `on_multi_upload`, um único pedido/grupo), informam cópias, papel (A4/A3), cor (PB/Color), frente/verso, sulfite, observações e a secretaria/setor de crédito. O sistema conta as páginas (PyMuPDF com fallback `pdfplumber`), renomeia o arquivo no padrão definido, aplica regras de cota mensal hierárquica e fluxo de autorização quando exigido. Apenas administradores do módulo imprimem; responsáveis cadastrados autorizam. Rascunhos têm contagem regressiva visível (`ui.timer` 1 s) e expiram em `tempo_expira_rascunho_min` (padrão 10 min).

**Versionamento**: `versao_modulo:solicita_impressao = 1.0.260913`.

**Integração organograma**: no primeiro boot o `init_db()` obtém o organograma compartilhado pela **fachada pública do núcleo** (`integracoes.obter_organograma_base()` — o módulo **não** importa `mod_lista_telefonica` diretamente, AGENTS.md §2) e **popula automaticamente** `tb_secretarias` com **1000 cópias** e `tb_setores` com **200 cópias** (subsetores achatados como setores). Quando o módulo de destino não responde, cai num **fallback local de 6 secretarias sem setores** (Gabinete, Administração, Finanças, Saúde, Educação, Obras e Infraestrutura). O seed é guardado por `COUNT(*) == 0` e **nunca faz `UPDATE`** de cota — bancos já existentes mantêm os valores e o ajuste do admin é soberano. Ver [Organograma compartilhado e cotas padrão](#organograma-compartilhado-e-cotas-padrao-1000200) e [Isolamento modular](../analise_mod_solicita_impressao.md).

## Banco de dados

Criador vigente: `init_db()` em `bd_manipulador.py:121-472` (bootstrap central). Arquivos PDF em `mod_solicita_impressao/solicitacaoImpressao/` (pasta própria).

| Tabela | Conteúdo |
|:---|:---|
| `tb_solicitacoes` | fluxo completo (solicitante, arquivos, cópias, papel, cor, frente/verso, **tipo de papel**, secretaria/setor FK, páginas, status, autorização, impressão) |
| `tb_secretarias` | nome, sigla, cota mensal (**1000 padrão do organograma**), limite de pedidos abertos (20 padrão) |
| `tb_setores` | nome, secretaria FK, cota mensal (**200 padrão do organograma**, subsetores achatados), limite de pedidos abertos (10 padrão) |
| `tb_responsaveis_autorizacao` | user_nome, secretaria/setor, ativo |
| `tb_cotas_impressao` | secretaria/setor (`setor_id=0` sentinela para "sem setor", pois SQLite trata NULL como distinto em UNIQUE), cota, `mes_referencia` (YYYY-MM único) |
| `tb_consumo_cota` | páginas usadas por mês |
| `tb_configuracoes_modulo` | chave/valor (pasta, MB, alertas, impressoras, tipo de papel padrão, marca d'água, prazos) |
| `tb_impressoras` | nome (UNIQUE), papel, cor, frente/verso, sulfite, driver (PCL6), ativo |

> **Cotas padrão do organograma**: `tb_secretarias.cota_paginas_mensal = 1000` e `tb_setores.cota_paginas_mensal = 200` vêm do organograma **compartilhado**, obtido pela fachada `mod_intranet.integracoes.obter_organograma_base()` (nível 1 → secretaria; níveis 2 e 3 → setor, com subsetor achatado). Semeado **somente quando a tabela está vazia** — **nunca** por `UPDATE` (o ajuste do admin é soberano).

## Funcionalidades

- **Upload automático ao selecionar o PDF** + renomeação (nome original descartado); rascunho `YYYYMMDD_HHMMSS_usuario_rascunho.pdf` com expiração (`tempo_expira_rascunho_min`, default 10 min) e botão "Remover arquivo".
- **Envio múltiplo** (até 10 PDFs): lista com checkbox, "Remover selecionados", todos os arquivos viram **um único pedido (grupo)** com status único; uuid evita colisão de rascunho no mesmo segundo.
- **Contabilização**: `paginas = qtd × copias × fator_papel × fator_frente_verso` (A4=1/A3=2; frente=1/verso=2).
- **Cotas hierárquicas mensais**: secretaria **1000 cópias padrão** e setor **200 cópias padrão** (semeadas do organograma compartilhado via `integracoes.obter_organograma_base()`, com fallback de 6 secretarias sem setores); setor sem cota usa o pool da secretaria; excedente **permitido** e marcado; consumo descontado só na impressão; visual **sem numeral** — verde <50% / amarelo 50–80% / laranja 80–100% / vermelho >100%; reset no dia 1º.
- **Limite de pedidos abertos** (elástico): secretaria 20 / setor 10 (0 = sem limite) sobre os status `pendente`, `aguardando_autorizacao`, `autorizado` e `excedente_cota`; ao atingir o teto, `criar_solicitacao` e `confirmar_rascunho` **bloqueiam** o envio orientando a imprimir/cancelar; imprimir, recusar ou cancelar **libera a vaga**.
- **Tipo de papel** (sulfite/fotográfico/vergê): selecionável no formulário, **ativo apenas em A4** (A3 = sulfite obrigatório); não sulfite avisa "traga o próprio papel"; padrão configurável (`padrao_tipo_papel`).
- **Alertas da nova solicitação** (`alertas_nova_solicitacao`): frases configuráveis (uma por linha) exibidas abaixo do card de envio — substitui os antigos avisos fixos de presença/páginas múltiplas.
- **Autorização por responsável cadastrado** (pode ser usuário `comum` — a checagem usa `tb_responsaveis_autorizacao`, independente do perfil); sem responsável → pedido fica `pendente` e o **admin autoriza e imprime**.
- **Reenvio de pedido recusado**: botão "Reenviar" reabre o pedido para nova autorização (limpa motivo e dados de autorização); "Cancelar" também vale para recusados.
- **Impressão dual**: "Imprimir" abre o seletor de impressoras (`tb_impressoras`) e dispara `window.imprimirPdf(url, nome)` via `src/impressao.js` (diálogo nativo do SO; `window.printSolicitacao(id)` é apenas atalho que monta `/solicita-impressao/pdf/{id}`) ou "Baixar para impressão" (Ctrl+P); decota cota ao imprimir e agenda exclusão em `tempo_exclui_impresso_min` (default 10 min); recusar/recuar/cancelar removem o arquivo na hora.
- **Marca d'água** opcional e personalizável (texto `{data}`, `{usuario}`, `{id}`, `{secretaria}`, `{setor}`, `{solicitante}`; posição, opacidade, fonte, cor, rotação).
- **Padrões pré-selecionados e editáveis** (A4, Colorido, somente frente, sulfite, tipo de papel) na Administração.
- **Datas do servidor**: todas as datas (criação, autorização, impressão, expiração) usam `hora_servidor()`/`datetime('now','localtime')` — fonte da verdade é o servidor (NTP.br opcional via `hora_ntp_ativa`).
- **Aparência** (card padrão "Configurações de cores" — `bloco_aparencia` com `com_card=False`, card próprio do módulo, prévia ao vivo e rodapé 2 botões): `solicita_impressao_cor_botao`, `solicita_impressao_cor_texto_botao`, `solicita_impressao_cor_fundo`, `solicita_impressao_cor_titulo`, `solicita_impressao_btn_tamanho`, `solicita_impressao_texto_header` em `tb_config` central, na sub-aba Configurações da Administração; tela em área cheia (`w-full`). O cabeçalho usa `chave_modulo="solicita_impressao"` (`telas.py:49`): a borda de destaque é a **mesma cor dos botões do módulo** (`solicita_impressao_cor_botao`, vazia = padrão via `PADROES_TEMA` — todos os módulos em `#000000`, a cor do intranet), título/fundo seguem o tema — sem hex hardcoded.
- **Auditoria central** (`solicita_impressao`): quem solicitou/autorizou/imprimiu/recusou (quantidades, motivo, hash).
- **Responsividade (RNF-UI-01, 09/2026 — auditado 320/768/1024 `kbp-web-design`)**: proposta P0/P1/P2 por `container`/`row`/`grid` — abas `overflow-x-auto`, formulário `grid-cols-1 sm:grid-cols-2`, lista de solicitações `overflow-x-auto`, dialogs `w-full max-w`, barra de ações `flex-wrap` `gap` via `.style`.
- **Job `cleanup_solicita`** (1 min) remove rascunhos não confirmados e impressos vencidos (`expirar_rascunhos_e_impressos` em `bd_manipulador.py`).
- **Administração standalone** (`telas_administracao.py::mostrar_administracao`, rota `/admin/solicita_impressao`): 7 sub-abas (Solicitações, Secretarias, Setores, Responsáveis, Cotas, Relatórios, Configurações) — `_admin_solicitacoes` delega para `telas.py` (pedidos agrupados por secretaria→setor); `_admin_relatorio` gera cobrança/repasse por período.
- **Relatório de cobrança/repasse** (sub-aba Relatórios): atalhos de prazo (Este mês, Mês anterior, Últimos 6 meses, Ano atual) ou período personalizado no calendário; `relatorio_impressao(data_inicio, data_fim)` agrega só `status='impresso'` no período, com totais de **cópias** e **páginas contabilizadas** separados por color/PB, e devolve 5 blocos — `geral`, `por_secretaria`, `por_setor`, `por_autorizador`, `por_impressor`. A contagem de pedidos usa `COUNT(DISTINCT s.grupo_id)` (1 pedido por envio).
- **Legado**: `bd_criador.py` é MORTO (criador antigo no banco central, tabela `tb_solicitacoes_impressao_legacy`) — fonte de verdade é `bd_manipulador.init_db()` em `db_mod_solicita_impressao.db`.
- **QA**: `data-testid` estáveis — `solicita-enviar`, `solicita-busca`, `solicita-admin-salvar`.

### Organograma compartilhado e cotas padrão (1000/200)

No `init_db()` (`bd_manipulador.py:401-518`), o organograma **não é importado do outro módulo
diretamente** — vem pela **fachada pública do núcleo** (25/09/2026, ver "Isolamento modular"):

- `from mod_intranet import integracoes` → `integracoes.obter_organograma_base()` — costura
  pública única; **nenhum módulo de negócio importa `mod_lista_telefonica` diretamente**
  (AGENTS.md §2). A função é fail-soft e devolve `None` com `logger.warning` se o módulo de
  destino falhar.
- `if not _ORG_BASE:` guarda os **dois** modos de falha (import que lança **e** resposta vazia) e
  cai num **fallback local de 6 secretarias sem setores**: Gabinete, Administração, Finanças,
  Saúde, Educação e Obras e Infraestrutura.
- `_sigla_sec(nome)`: `NFKD` sem acentos + 4 chars upper → `SEC_XXXX` (`ljust(3,"X")` se curto).
- **Secretarias** — nível 1 do organograma: `[(nome, sigla, 1000, 20) for sec in _ORG_BASE]`,
  cada uma com **1000 cópias/mes** e limite de **20 pedidos abertos**.
- **Setores** — níveis 2 **e** 3 (subsetor **achatado** como setor, pois a hierarquia de cota é
  só secretaria → setor): `200 cópias/mes` e limite de **10 pedidos abertos** cada. O
  `secretaria_id` é resolvido por `_mapa_nome_id` → `_mapa_sigla_id` → `SELECT … WHERE nome=?`.
- Idempotência: `INSERT` só quando não existe (`SELECT … WHERE sigla=? OR nome=?` /
  `WHERE nome=? AND secretaria_id=?`), sob a guarda `COUNT(*) == 0` em `tb_secretarias` **e**
  `tb_setores`.
- ⚠️ **O seed NUNCA faz `UPDATE` de cota** (regra devSecOps/PostgreSQL): *"NUNCA forçar cotas
  padrão via `UPDATE` (1000/200): ajuste do admin é soberano."* Bancos já existentes **mantêm**
  os valores; só banco **novo** recebe o seed. Sem essa guarda, todo restart sobrescreveria a
  cota que o admin acabou de ajustar. (Documentação anterior afirmava uma migração `UPDATE …
  SET cota=1000/200` para bancos existentes — **desatualizada**, removida pelo guard de COUNT.)
- Secretarias/setores criados manualmente pelo admin mantêm a cota informada no cadastro.

!!! warning "Adicionar departamento na Lista Telefônica NÃO cria setor de impressão"
    Os bancos são independentes por módulo (AGENTS.md §4.1). O `init_db` semeia uma **cópia** da
    estrutura no `tb_setores` **só na primeira criação**. Depois disso, o admin do módulo de
    impressão é soberano: departamento novo no organograma precisa ser cadastrado em
    Administração → Setores (ou `tb_setores` precisa ser esvaziada, o que descarta os ajustes
    de cota).

## Nomenclatura do arquivo

```
AAMMDDHHMMSS_secretaria_setor_solicitante_copias_cor_tipoPapel_folhas_ordemEnvio.pdf
```

Ex.: `260907143022_SAUDE_ATENDIMENTO_joao_silva_3_colorido_sulfite_10_1.pdf` (acentos removidos,
espaços→`_`; `ordemEnvio` diferencia arquivos do mesmo envio no mesmo segundo).

## Permissões

| Perfil | Capacidade |
|:---|:---|
| `comum` | criar solicitações, acompanhar as próprias ("Minhas Solicitações"), cancelar pendentes |
| `comum` vinculado como responsável | ver aba **Autorização** da sua secretaria/setor (autorizar/recusar com motivo) |
| `administrador` do módulo | imprimir, recuar, gerenciar cadastros (secretarias, setores, responsáveis, cotas), configurar |
| `administrador_geral` | tudo + auditoria |

## Rota e integrações

- Rota: `/solicita-impressao` (`main.py:701`) + downloads `/solicita-impressao/pdf/{id}` (`main.py:654`) e JS `/solicita-impressao/src/impressao.js` (`main.py:766`).
- Módulo nativo em `tb_modulos` (chave `solicita_impressao`, ícone `print`).
- Auditoria via `audit_log(usuario, 'solicita_impressao', ...)`.
- **Organograma**: obtido pela fachada `mod_intranet.integracoes.obter_organograma_base()` (lazy, fail-soft, devolve `None` se o módulo não responder) com **fallback local de 6 secretarias sem setores** — ver [Organograma compartilhado e cotas padrão](#organograma-compartilhado-e-cotas-padrao-1000200), [Isolamento modular](../analise_mod_solicita_impressao.md#isolamento-modular-organograma-pela-fachada-do-nucleo-25092026-commit-624c9d5) e [Integração Lista Telefônica](../analise_mod_lista_telefonica.md).
- **Usuários**: o seletor buscável de responsáveis (aba Autorização) é alimentado pelo módulo de Gestão de Usuários, também **via núcleo** (`integracoes.listar_usuarios_gestao`) — nunca por import direto de módulo de negócio.

## Testes

```bash
.venv/bin/python test/test_solicita_impressao.py
# Smoke cotas padrão
.venv/bin/python -c "from mod_solicita_impressao.bd_manipulador import init_db, listar_secretarias, listar_setores; init_db(); print([(s[1],s[3]) for s in listar_secretarias()[:3]]); print([(s[1],s[3]) for s in listar_setores()[:5]])"
```

## Pontos de atenção

- Lista real de impressoras depende de API experimental do navegador (`navigator.getPrinters`); fallback é o diálogo nativo do SO.
- Contagem de páginas usa PyMuPDF; PDFs corrompidos/imagem podem retornar 0 (bloqueia envio).
- Cotas são mensais; reset manual ou automático (dia 1); sem e-mail (SMTP não usado aqui).
- **Organograma achatado**: o organograma compartilhado tem 3 níveis (Secretaria→Setor→Subsetor), mas a impressão mantém **2 níveis** (Secretaria→Setor) — subsetores viram setores com 200 cópias para compatibilidade com o modelo hierárquico da impressão.
- **O seed NUNCA corrige cota por `UPDATE`** (regra devSecOps/PostgreSQL). A documentação anterior descrevia uma migração `UPDATE … WHERE cota != 1000/200` — **desatualizada**: hoje só se semeia com `COUNT(*) == 0`, e qualquer valor existente é preservado. Consequência: um setor legado com cota 0 **não** é mais corrigido automaticamente no boot; o admin precisa ajustá-lo, ou `tb_setores` precisa ser esvaziada (o que descarta os ajustes).
- **Bancos independentes**: adicionar departamento no `mod_lista_telefonica` **não** cria o setor de impressão correspondente — o admin precisa cadastrar em Administração → Setores.
- **Fallback de 6 secretarias não tem setores**: se o `mod_lista_telefonica` estiver ausente ou vazio, o sistema sobe com as 6 secretarias de cota 1000 e **nenhum setor** cadastrado.

```bash
# Verificação rápida do isolamento (não deve haver import direto de mod_lista_telefonica)
grep -n "mod_lista_telefonica" mod_solicita_impressao/*.py   # esperado: NENHUMA ocorrência
```

Ver [Análise do Módulo](../analise_mod_solicita_impressao.md).
