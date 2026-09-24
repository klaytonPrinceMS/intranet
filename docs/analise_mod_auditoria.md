# Auditoria — `mod_auditoria`

> Audit module: route `/auditoria` (key `auditoria`) · EXCLUSIVE database `db_mod_auditoria.db` with ONE TABLE PER PRODUCER MODULE (`tb_auditoria_<modulo>`) · read-only viewer with dynamic table navigation, filters by user/module/action/time/date range, server-side pagination, CSV export, per-auditor column selection/ordering, Grafana observability tab.

---

# Auditoria — `mod_auditoria`

> Módulo de auditoria: rota `/auditoria` (chave `auditoria`) · **banco EXCLUSIVO** `db_mod_auditoria.db` com **UMA TABELA POR MÓDULO PRODUTOR** (`tb_auditoria_<modulo>`) · visualizador somente-leitura com navegação dinâmica por tabela, filtros por usuário/módulo/ação/hora/intervalo de datas, paginação server-side, exportação CSV, seleção/ordem de campos por auditor e aba de Observabilidade (Grafana).

## Propósito

Banco e visualizador da trilha de auditoria LGPD. A **escrita** é feita pelos demais módulos via `audit_log` (núcleo) → `registrar_auditoria` (este módulo), que grava na tabela do módulo produtor (`tb_auditoria_<modulo>`, criada automaticamente). A **leitura** é feita pela tela `/auditoria` (exclusiva do `administrador_geral`), com filtros, paginação server-side e exportação CSV. As preferências de coluna e as configurações vão para `tb_config` central.

## Banco exclusivo (`db_mod_auditoria.db`, WAL)

Criador vigente: `init_db_auditoria()` em `bd_manipulador.py` (executado no import e pelo bootstrap central).

- **`tb_auditoria_<modulo>`** — UMA TABELA POR MÓDULO (nome sanitizado: hífen vira `_`, ex. `edit-pdf` → `tb_auditoria_edit_pdf`). Colunas: `id`, `usuario`, `modulo`, `acao`, `descricao`, `timestamp` (horário local — RF-08), `hash_arquivo`, `ip`, `user_agent`, `client_hostname`; índices por `modulo`, `usuario` e `timestamp`. O `hash_arquivo` é opaco para este módulo: quem calcula (ex. SHA-256 no Editor de PDF) é o produtor, que repassa via `audit_log` → `registrar_auditoria`.
- **`tb_auditoria_meta`** — registro dos módulos produtores (`modulo` PK, `nome`, `criada_em`).
- **Migração idempotente** do legado: `migrar_dados_existentes()` (`bd_manipulador.py`) copia a antiga `tb_auditoria` do banco central para as tabelas por módulo, marca `auditoria_migracao_concluida=1` na `tb_config` e **remove a tabela legada** do central.
- **Poda LGPD**: `podar_registros(dias)` (`bd_manipulador.py`) remove registros mais antigos que o prazo em TODAS as tabelas — chamada diariamente pelo job `poda_auditoria` (`mod_intranet/rotinas.py`, `auditoria_retencao_dias`, default 90).

!!! note "Escrita automática por novos módulos"
    `registrar_auditoria` (`bd_manipulador.py`) cria a tabela do módulo e o registro em `tb_auditoria_meta` na primeira gravação — um módulo novo passa a auditar **sem nenhuma edição** neste módulo.

## Estrutura do pacote

- `bd_manipulador.py` — conexão WAL, criação/garantia de tabelas, `registrar_auditoria`, `contar_registros`, `podar_registros`, `buscar_logs` (filtros + paginação), descoberta de módulos (`get_modulos_com_auditoria`/`get_tabelas_auditoria`) e migração do legado.
- `telas.py` — visualizador somente-leitura (`mostrar_tela(usuario_logado, perfil)`): abas Logs + Observabilidade (sem aba de administração interna).
- `telas_administracao.py` — painel standalone `mostrar_administracao` (rota `/admin/auditoria`): cores + configurações específicas (limite, retenção, cabeçalho) + backup; exclusivo do `administrador_geral`.
- `bd_criador.py` — **legado** (cria apenas `tb_auditoria_meta`; o esquema real é o de `bd_manipulador.py`).
- `check_auditoria.py` — script diagnóstico standalone (lista chaves `auditoria%` da `tb_config` central).

## Fluxo da tela

- **Acesso exclusivo ao `administrador_geral`** — dupla camada: bloqueio interno + exigência da chave `auditoria` em `pagina_restrita`. Tentativa sem permissão gera `acesso_negado` na trilha (choke point único em `telas.pagina_restrita`).
- **Navegação dinâmica por tabela**: select "Visualizar auditoria de" montado a partir do banco (`get_modulos_com_auditoria`) — "Todas as auditorias" (UNION ALL) ou a tabela de um módulo específico; rótulos amigáveis por chave (`DEFS_NAV`).
- **Filtros**: Usuário (LIKE), Ação (select com **categorias prontas** coloridas `CORES_ACAO` + texto livre via `with_input`), Hora (`strftime('%H:%M')`), intervalo de datas (campos com calendário em popup).
- **Paginação server-side**: `LIMIT ? OFFSET ?` (`auditoria_limite` como tamanho de página, default 1000) com contador e botões Anterior/Próxima; auto-atualização a cada 30 s.
- **Campos/ordem por auditor**: painel "Campos e ordem de exibição" com mover ↑/↓, ocultar, adicionar e "Restaurar padrão"; persistido em `tb_config` na chave `auditoria_campos:<usuario>` (JSON). Coluna "Ação" colorida por categoria.
- **Exportação CSV**: baixa o resultado filtrado da página corrente respeitando os **campos e a ordem** selecionados pelo auditor.
- **Colunas padrão**: Data/Hora, Usuário, Módulo, Ação, Descrição (truncada a 100 chars), Hash, IP e rótulo de dispositivo (`rotulo_dispositivo`).
- **Aba Observabilidade** (só quando a stack OTel está no ar — `docker_detector.otel_stack_rodando()`): cards de atalho para os dashboards Grafana (Visão Geral, Traces, Logs) com aviso LGPD sobre a senha padrão do Grafana.
- **Administração separada** (`telas_administracao.py`, rota `/admin/auditoria`): `auditoria_limite`, `auditoria_retencao_dias`, `auditoria_texto_header` + card padrão **"Configurações de cores"** (`auditoria_cor_botao`, `auditoria_cor_texto_botao`, `auditoria_cor_fundo`, `auditoria_cor_titulo`, `auditoria_btn_tamanho` — vazios usam o padrão do PRÓPRIO módulo via `PADROES_TEMA["auditoria"]` = `#000000`, sem herança do tema do sistema). Salvar também **audita a si mesmo** (`auditoria`, `configuracao`).

## Integrações com o núcleo

- **Escrita**: `mod_intranet.bd_manipulador.audit_log` preenche IP/UA do contexto (`mod_intranet.contexto`) e chama `registrar_auditoria` — produtores: todos os módulos + o próprio núcleo (login/logout/falhas/configurações/backups).
- **Leitura**: `buscar_logs` (UNION ALL entre tabelas ou tabela única), `get_modulos_com_auditoria` (menu dinâmico), `contar_registros` (resumo do dashboard).
- **Config**: `get_config`/`set_config` centrais (`auditoria_limite`, `auditoria_retencao_dias`, `auditoria_texto_header`, `auditoria_campos:<usuario>`, tema `auditoria_*`).
- **Poda**: job diário `poda_auditoria` do APScheduler central.
- **Versionamento**: `versao_modulo:auditoria = 1.0.260908` (seed em `bd_manipulador._semear_versao_modulo` e `conexao_bd.init_db()`), exibido no rodapé de `/auditoria`.

## Pontos de atenção

- Consulta além de `auditoria_limite` numa página usa os botões de paginação; a exportação CSV cobre a página corrente (na ordem do auditor).
- Ações desconhecidas/novas podem ser filtradas por texto livre no select de Ação.
- A preferência de colunas é por usuário (`auditoria_campos:<usuario>`); como o módulo é exclusivo do admin geral, na prática vale para qualquer auditor.
- `bd_criador.py` é legado — não executar como fonte de verdade.

### Adições recentes (09/2026) — responsividade global RNF-UI-01

- **Auditado 320/768/1024** (`kbp-web-design`) com checklist P0/P1/P2 por `container`/`row`/`grid`: tabs/filtros/tabela `overflow-x-auto`, barra de filtros `flex-wrap` `gap` via `.style`, `truncate` em colunas longas, dialogs `w-full max-w`. Proposta por `container`/`row`/`grid` (header `flex-wrap` `min-width:0`) registrada na auditoria; ver [Padrões](padroes_codificacao/index.md) §8.1.

## Status

| Item | Situação |
|:---|:---:|
| Banco exclusivo com tabela por módulo + metadados | ✅ Implementado |
| Escrita automática (`registrar_auditoria` cria tabela/meta) | ✅ Implementado |
| Migração idempotente do legado central (+ remoção da tabela legada) | ✅ Implementado |
| Navegação dinâmica por tabela de módulo | ✅ Implementado |
| Filtros (usuário/módulo/ação/hora/datas) + categorias coloridas | ✅ Implementado |
| Paginação server-side + índices | ✅ Implementado |
| Exportação CSV (página corrente, campos/ordem do auditor) | ✅ Implementado |
| Campos/ordem por auditor (`auditoria_campos:<usuario>`) | ✅ Implementado |
| Poda diária LGPD (`auditoria_retencao_dias`) | ✅ Implementado |
| Acesso exclusivo do `administrador_geral` + `acesso_negado` (RF-35) | ✅ Implementado |
| Aba Observabilidade (Grafana) condicionada à stack OTel | ✅ Implementado |
| Cupê Aparência + auto-auditoria das configs | ✅ Implementado |

## Pendência QA — WAL + paridade SQLite↔Postgres (24/09/2026, sem correção aplicada)

> Documentação da correção pendente. Nenhum `.py` alterado neste lote.

| Módulo | Achado | Arquivo:linha | Correção proposta contida no módulo | Risco regressão |
|:---|:---|:---|:---|:---|
| auditoria | Sem `CrudBase`; `sqlite_master` em 3 pontos; `strftime` em SQL sem tradução PG | `mod_auditoria/bd_manipulador.py:138`, `:460`, `:475` (`sqlite_master`) · `:339`, `:352`, `:372`, `:388` (`strftime`) | Migrar para `CrudBase` + `conexao("auditoria")`; helper `_tabela_existe()` interno; reescrever filtro hora/datas sem `strftime` SQL (Python ou `EXTRACT`/`TO_CHAR` isolado) | Médio-alto (LGPD/poda + UNION ALL + CSV) |

Detalhe consolidado em [Plano WAL + Paridade](../registro_de_mudancas/wal_paridade_pendente_2026-09-24.md).

## Correção aplicada 24/09/2026 — WAL + paridade SQLite↔PostgreSQL

> EN: Fix applied 24/09/2026 in `mod_auditoria/bd_manipulador.py` (code already patched, docs-only batch): meta-first discovery + `information_schema` fallback, `to_char` vs `strftime` helpers, write cache + 3x commit retry, portable migration, portable `check_auditoria.py`; tests 12/12 in `assets/test/test_auditoria.py`, verdict PASS.

> Correção aplicada em 24/09/2026 em `mod_auditoria/bd_manipulador.py` (código já corrigido, lote só-documentação): descoberta via meta + fallback `information_schema`, helpers `to_char` vs `strftime`, cache de escrita + retry 3x, migração portável, `check_auditoria.py` portável; testes 12/12 em `assets/test/test_auditoria.py`, veredito APROVADO.

| Tema | Antes (pendência 24/09) | Depois (correção aplicada) — arquivo:linha |
|:---|:---|:---|
| Descoberta via meta + `information_schema` | `sqlite_master` em 3 pontos, sem ramo PG | Fonte primária `tb_auditoria_meta` (`bd_manipulador.py:245`); fallback por backend (`:256-269`): `information_schema.tables` no PG (`:260-267`), `sqlite_master` só no SQLite (`:268`); `_tabela_existe()` portável (`:72-96`) com `_sgbd()` (`:27-34`) |
| Filtros hora/data `to_char` | `strftime('%H:%M'/'%d/%m/%Y')` em SQL sem tradução no proxy (`:339`, `:352`, `:372`, `:388`) | `_sql_hora()` (`:99-107`): `to_char(col, 'HH24:MI')` no PG, `strftime('%H:%M')` no SQLite — usado em `buscar_logs` tabela única (`:515`) e `UNION ALL` (`:548`); `_sql_data_formatada()` (`:110-118`): `to_char(col, 'DD/MM/YYYY HH24:MI:SS')` vs `strftime('%d/%m/%Y %H:%M:%S')` — usado em (`:528`) e (`:564`) |
| Cache de escrita + retry | DDL+commit por escrita (janela de lock); `database is locked` sem retry | `_TABELAS_GARANTIDAS` (`:21`) + `_TENTATIVAS_COMMIT = 3` (`:24`); `registrar_auditoria` só garante DDL se fora do cache (`:352-354`), invalida e regarante em `no such table`/`undefined_table` (`:367-375`); `_commit_com_retry()` (`:37-69`, backoff `0.05s × tentativa`, rollback seguro, fail-soft AGENTS §3.2); conexão via `conexao("auditoria")` + `PRAGMA journal_mode=WAL`/`synchronous=NORMAL` (`:130-146`) |
| Migração portável | `sqlite_master` no legado central, sem ramo PG | `_migrar_dados_existentes_seguro()` (`:623`) usa `_tabela_existe(central_conn, "tb_auditoria")` (`:637`, `information_schema` no PG); garante `tb_auditoria_meta` (`:665-666`); grava por módulo + `_commit_com_retry` (`:679`); marca `auditoria_migracao_concluida=1` e remove legado (`:696-697`) |
| `check` portável | Risco de `sqlite3` cru no diagnóstico | `check_auditoria.py` via `banco_conexao.conexao("intranet")` (`:31-33`), `SELECT chave, valor FROM tb_config WHERE chave LIKE 'auditoria%'` (`:35`) portável nos dois backends, log dedicado `logs/auditoria_*.log` — sem uso pela aplicação |

### Testes e veredito

| Suíte | Resultado |
|:---|:---|
| `assets/test/test_auditoria.py` — índices (3: `modulo`/`usuario`/`timestamp` em `tb_auditoria_intranet`) + `audit_log` rastreável (4: ação/IP/UA/timestamp local) + poda LGPD (2: remove velho/preserva novo) + acesso exclusivo (2: `qacomum` nega/`qamaster` permite) + prefs por usuário (1) | 12/12 OK |

**Veredito: APROVADO — sem regressão.** Pendência WAL+paridade do `mod_auditoria` (linha da tabela acima) considerada **superada**; demais módulos do plano permanecem pendentes conforme o arquivo consolidado.
