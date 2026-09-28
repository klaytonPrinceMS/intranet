# Auditoria — `mod_auditoria`

> Audit module: route `/auditoria` (key `auditoria`) · EXCLUSIVE database `db_mod_auditoria.db` with ONE TABLE PER PRODUCER MODULE (`tb_auditoria_<modulo>`) · single writer (`audit_log`) reached through a decoupled hook · write cache + 3× commit retry · meta-first table discovery with `information_schema`/`sqlite_master` fallback · `to_char` vs `strftime` helpers · read-only viewer with dynamic table navigation, filters by user/module/action/time/date range, server-side pagination, CSV export, per-auditor column selection/ordering, Grafana observability tab.

---

# Auditoria — `mod_auditoria`

> Módulo de auditoria: rota `/auditoria` (chave `auditoria`) · **banco EXCLUSIVO** `db_mod_auditoria.db` com **UMA TABELA POR MÓDULO PRODUTOR** (`tb_auditoria_<modulo>`) · escritor **único** (`audit_log`) alcançado por **gancho desacoplado** · cache de escrita + retry 3× no commit · descoberta de tabela pela meta com fallback `information_schema`/`sqlite_master` · helpers `to_char` vs `strftime` · visualizador somente-leitura com navegação dinâmica por tabela, filtros por usuário/módulo/ação/hora/intervalo de datas, paginação server-side, exportação CSV, seleção/ordem de campos por auditor e aba de Observabilidade (Grafana).

## Propósito

Banco e visualizador da trilha de auditoria LGPD. A **escrita** é feita pelos demais módulos via `audit_log` (núcleo) → `registrar_auditoria` (este módulo), que grava na tabela do módulo produtor (`tb_auditoria_<modulo>`, criada automaticamente). A **leitura** é feita pela tela `/auditoria` (exclusiva do `administrador_geral`), com filtros, paginação server-side e exportação CSV. As preferências de coluna e as configurações vão para `tb_config` central.

Anatomia completa da escrita (caminho do `audit_log`, gancho desacoplado, cache de escrita, retry 3× no commit, descoberta de tabela, helpers `to_char`/`strftime` e as ações em background com ator `sistema`) na seção
["Anatomia da escrita na trilha (25/09/2026)"](#anatomia-da-escrita-na-trilha-25092026).

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
- **Filtros**: Usuário (LIKE), Ação (select com **categorias prontas** coloridas `CORES_ACAO` + texto livre via `with_input`), Hora (expressão do helper `_sql_hora()` — `to_char` no PG / `strftime` no SQLite), intervalo de datas (campos com calendário em popup).
- **Paginação server-side**: `LIMIT ? OFFSET ?` (`auditoria_limite` como tamanho de página, default 1000) com contador e botões Anterior/Próxima; auto-atualização a cada 30 s.
- **Campos/ordem por auditor**: painel "Campos e ordem de exibição" com mover ↑/↓, ocultar, adicionar e "Restaurar padrão"; persistido em `tb_config` na chave `auditoria_campos:<usuario>` (JSON). Coluna "Ação" colorida por categoria.
- **Exportação CSV**: baixa o resultado filtrado da página corrente respeitando os **campos e a ordem** selecionados pelo auditor.
- **Colunas padrão**: Data/Hora, Usuário, Módulo, Ação, Descrição (truncada a 100 chars), Hash, IP e rótulo de dispositivo (`rotulo_dispositivo`).
- **Aba Observabilidade** (só quando a stack OTel está no ar — `docker_detector.otel_stack_rodando()`): cards de atalho para os dashboards Grafana (Visão Geral, Traces, Logs) com aviso LGPD sobre a senha padrão do Grafana.
- **Administração separada** (`telas_administracao.py`, rota `/admin/auditoria`): `auditoria_limite`, `auditoria_retencao_dias`, `auditoria_texto_header` + card padrão **"Configurações de cores"** (`auditoria_cor_botao`, `auditoria_cor_texto_botao`, `auditoria_cor_fundo`, `auditoria_cor_titulo`, `auditoria_btn_tamanho` — vazios usam o padrão do PRÓPRIO módulo via `PADROES_TEMA["auditoria"]` = `#000000`, sem herança do tema do sistema). Salvar também **audita a si mesmo** (`auditoria`, `configuracao`).

## Anatomia da escrita na trilha (25/09/2026)

> **EN:** Anatomy of a write into the trail — the only writer is
> `mod_intranet/bd_manipulador.py::audit_log()`, which hands the record to this
> module through a decoupled hook. Writes are cached (DDL once per session) and
> the commit is retried 3×; background actions (APScheduler) are recorded with
> `sistema` as the actor.
>
> **PT-BR:** Anatomia de uma escrita na trilha — o **único** escritor é
> `mod_intranet/bd_manipulador.py::audit_log()`, que entrega o registro a este
> módulo por um **gancho desacoplado**. As escritas são cacheadas (DDL uma vez
> por sessão) e o commit tem **retry 3×**; as ações em background (APScheduler)
> entram na trilha com `sistema` como ator.

### O caminho completo de uma escrita

```text
módulo de negócio
   └─ audit_log(usuario, modulo, acao, descricao, hash_arquivo=None,
               client_ip="__CTX__", client_user_agent="__CTX__")
        │  mod_intranet/bd_manipulador.py:74-104
        ├─ resolve IP/UA do contexto HTTP (mod_intranet/contexto.py) quando "__CTX__"
        ├─ carimbo local: datetime.now().strftime("%Y-%m-%d %H:%M:%S")   (RF-08)
        ├─ _hook_auditoria(...)            ← caminho normal (registrado no boot)
        │      └─ mod_auditoria/bd_manipulador.registrar_auditoria(...)
        └─ import lazy mod_auditoria...   ← fallback se nenhum gancho foi registrado
```

- **Único ponto de escrita.** Nenhum módulo grava em `db_mod_auditoria.db`
  diretamente: todos passam por `audit_log`. Isso mantém o carimbo de tempo, a
  rastreabilidade (IP/UA) e a decisão de destino (`tb_auditoria_<modulo>`) em um
  lugar só.
- **Gancho, não import, no caminho quente.** `registrar_hook_auditoria(fn)`
  (`mod_intranet/bd_manipulador.py:29-39`) recebe a função gravadora **quando o
  módulo carrega**, e `audit_log` só a chama. Isso **remove a dependência cíclica
  núcleo↔auditoria**: o núcleo não importa o módulo de auditoria na rotina de
  escrita. Sem gancho registrado, `audit_log` mantém o **import lazy** de
  fallback (`bd_manipulador.py:102-104`) — o módulo continua funcionando mesmo
  fora do boot completo.
- **Falha de auditoria não derruba a operação.** `registrar_auditoria` é
  fail-soft (loguru + `rollback`): se a trilha falhar, a escrita de negócio já
  foi feita e a tela não cai. O mesmo vale para `crud_base.audit_reg`.

### Descoberta de tabela: meta primária + fallback por backend

`registrar_auditoria` cria a tabela do módulo **na primeira gravação** e registra
o módulo em `tb_auditoria_meta` — um módulo novo passa a auditar **sem nenhuma
edição** neste módulo. A **leitura** (menu da tela) descobre as tabelas em duas
fontes (`get_tabelas_auditoria`, `bd_manipulador.py:230-280`):

| Ordem | Fonte | Observação |
|:--|:---|:---|
| **1ª (primária)** | `SELECT modulo FROM tb_auditoria_meta ORDER BY nome` (`:245`) | Portátil nos dois backends; devolve as tabelas já sanitizadas por `_nome_tabela(modulo)` |
| **2ª (fallback)** | `information_schema.tables` (PG, `:262-267`) · `sqlite_master` (SQLite, `:268`) | SÓ se a meta falhar/estiver vazia |

O fallback é **explícito por backend** porque `SELECT` em `sqlite_master`
**através do proxy** Postgres **devolve vazio** (não erro) — a comment no código
registra isso. O mesmo par vale no helper `_tabela_existe` (`:72-96`), usado pela
DDL e pela migração do legado. `get_modulos_com_auditoria` (`:283-318`) tem o
mesmo desenho em dois níveis: meta → `get_tabelas_auditoria()` → derivação do
módulo pelo nome da tabela (`_extrair_modulo`, inverso de `_nome_tabela`).

### Helpers de data/hora — `to_char` (PG) vs `strftime` (SQLite)

O filtro de **Hora** e o intervalo de **Datas** da tela precisavam de SQL de
formatação — SQLite e PostgreSQL não compartilham a função. Em vez de `strftime`
"solto" no SQL (que o proxy não traduz), há dois helpers que escolhem pelo SGBD
ativo (`_sgbd()`, `:27-34`):

| Helper | PostgreSQL | SQLite | Usado em |
|:---|:---|:---|:---|
| `_sql_hora(coluna)` (`:99-107`) | `to_char(col, 'HH24:MI')` | `strftime('%H:%M', col)` | filtro de hora na tabela única e no `UNION ALL` |
| `_sql_data_formatada(coluna)` (`:110-118`) | `to_char(col, 'DD/MM/YYYY HH24:MI:SS')` | `strftime('%d/%m/%Y %H:%M:%S', col)` | coluna de data/hora formatada na tabela única e no `UNION ALL` |

Ambos têm `except` com fallback para a forma SQLite e `log.exception` — nunca
levantam.

### Cache de escrita + retry 3× no commit

Duas defesas contra a **janela de lock** do SQLite (o `audit_log` é chamado em
toda ação, muitas vezes dentro de outra transação):

1. **`_TABELAS_GARANTIDAS`** (`:21`) — set de tabelas já garantidas **nesta
   sessão**: o `CREATE TABLE` + o registro em `tb_auditoria_meta` só rodam na
   **primeira** escrita do módulo (`:352-354`). Se o `INSERT` falhar com
   `no such table` / `does not exist` / `undefined_table` (tabela derrubada por
   alguém no meio do caminho), o cache é **invalidado**, a DDL é regarantada e o
   `INSERT` é refeito **uma vez** (`:363-382`) — a trilha LGPD não se perde.
2. **`_commit_com_retry(conn, contexto)`** (`:37-69`) — até **`_TENTATIVAS_COMMIT = 3`**
   tentativas; só re-tenta quando a mensagem indica contenção (`locked`, `busy`,
   `timeout`) e ainda há tentativa, com backoff `0.05s × tentativa`; ao esgotar,
   faz `rollback` seguro, registra `log.exception` e **devolve `False`** (fail-soft
   — quem chamou não propaga). O `contexto` (ex.: `registrar blog/criar_postagem`)
   identifica a ação que falhou no log.

### Aquecimento no boot: por que a 1ª gravação custava 73,9 s (26/09/2026)

O item 1 acima tem um custo escondido. A **primeira** gravação de cada módulo
roda `_garantir_tabela_auditoria` (DDL) dentro do event-loop do handler de tela.
Medido num banco recém-criado: a 1ª chamada de `audit_log` levava **73,9 s**, e as
seguintes caíam para ~145 ms. Como o handler roda no event-loop, a tela ficava
congelada por mais de um minuto e o WebSocket caía — o "servidor desconectado"
intermitente.

A causa não era a auditoria em si, e sim o preço de setup de cada tabela pago na
primeira ação de cada módulo. A correção é **`aquecer_auditoria(modulos=None)`**:
ela pré-cria as tabelas de todos os módulos registrados **antes** do servidor
aceitar requisições. O `main.py` chama isso em `_passo_auditoria`, o primeiro
passo de `ativacao.progresso_boot`.

| medição | antes | depois |
|:---|:---|:---|
| 1ª gravação de auditoria | **73,9 s** | **141 ms** |
| preço do aquecimento (1×, no boot) | — | 4,5 s |
| gravações seguintes | ~145 ms | ~122 ms |

O aquecimento é **síncrono de propósito**: roda no boot, antes de o servidor
existir, então não há event-loop a bloquear. Uma primeira tentativa usou
`run.io_bound` e emitiu `RuntimeWarning: coroutine 'io_bound' was never awaited`
— `io_bound` é `async` e não pode ser chamado de função síncrona; foi removido.

Consequência prática: depois de um boot, **nenhuma ação de usuário paga o preço de
setup**. Vale notar que isso derrubou `criar_impressora` de 28,1 s para
milissegundos — medição que mudou a prioridade das correções anti-disconnect do
Solicita Impressão (ver `analise_mod_solicita_impressao.md`, RISCO-SOL-01).

## A trilha também registra as ações em background (APScheduler)

Nem todo registro da trilha vem de um clique humano: os **jobs agendados** pelo
núcleo gravam com o ator literal **`sistema`**, o que permite distinguir ação
humana de ação automática na auditoria.

| Job (`mod_intranet/rotinas.py`) | Ator | Como entra na trilha |
|:---|:---|:---|
| `monitor_empenho` → `rodar_monitor("sistema")` (`:213-225`) | `sistema` | Varredura da pasta monitorada de empenhos grava o renomeio dos campos de cadastro com `audit_log("sistema", "renomear-empenho", "campo_cadastro", ...)` (`mod_renomear_empenho/bd_manipulador.py:2726`) |
| `agregador_coleta` → `coletar_todas(ator="sistema")` (`:228-240`) | `sistema` | Cada coleta audita com `_auditoria(ator or "sistema", ...)` (`mod_agregador_noticias/bd_manipulador.py:97`); os definidores (`definir_habilitado`, `definir_intervalo`, `definir_termo`, `definir_fontes`, `definir_temas`, `definir_hora_reinicio`, `reiniciar_banco`) também têm `ator="sistema"` como default |
| `poda_auditoria` (`:288-317`) | — | **Praticada sobre** a trilha: `podar_registros(dias)` remove registros mais antigos que `auditoria_retencao_dias` (default 90) em **todas** as tabelas; a remoção só gera `log` (`observabilidade`), não linha nova na trilha |
| `backup` / `cleanup_pdf` / `cleanup_solicita` | `sistema`/usuário | Backup manual grava `audit_log(usuario, "intranet", "backup_manual", ...)` a partir do painel (`rotinas.py:123`); o backup agendado registra hash SHA-256 dos arquivos via `hash_arquivo` |

!!! note "Consequência para o auditor"
    Filtrar por `usuario = "sistema"` separa o que o sistema fez sozinho
    (coleta de notícias, varredura de empenhos) do que uma pessoa fez. Sem isso,
    renomear um empenho automaticamente pareceria uma ação de usuário e a trilha
    perderia valor probatório. Auditoria **nunca** é apagada pela cascata LGPD de
    exclusão de usuário (ver
    [Gestão de Usuários](analise_mod_gest_cad_usuario.md#limpeza-cruzada-lgpd-a-unica-excecao-de-negocionegocio)).

## Integrações com o núcleo

- **Escrita**: `mod_intranet.bd_manipulador.audit_log` preenche IP/UA do contexto (`mod_intranet.contexto`) e chama `registrar_auditoria` — produtores: todos os módulos + o próprio núcleo (login/logout/falhas/configurações/backups) + os **jobs em background** com ator `sistema` (ver seção acima).
- **Desacoplamento**: o núcleo **não importa** este módulo no caminho quente — usa o gancho `registrar_hook_auditoria`; o import lazy de `audit_log` é só o fallback.
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

Detalhe consolidado em [Plano WAL + Paridade](registro_de_mudancas/wal_paridade_pendente_2026-09-24.md).

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

---

# RF e RNF verificados no código — lote 1 (26/09/2026)

> Auditoria de requisitos **funcionais** (o que o sistema faz) e **não
> funcionais** (qualidade e restrições), com evidência `arquivo:linha` conferida
> no código em 26/09/2026.

## Requisitos funcionais (RF) — mapa código ↔ doc

| RF | Descrição | Evidência no código |
|:---|:---|:---|
| RF-AUD-01 | **Uma tabela por módulo** (`tb_auditoria_<modulo>`) criada automaticamente: módulo novo audita sem editar o Auditoria | `bd_manipulador.py:121-127` `_nome_tabela` + `:183-227` `_garantir_tabela_auditoria` + cache de sessão `_TABELAS_GARANTIDAS` (`:21`, `:352-354`) |
| RF-AUD-02 | Hífen do módulo vira `_` no nome da tabela (`edit-pdf` → `tb_auditoria_edit_pdf`) | `bd_manipulador.py:127` |
| RF-AUD-03 | Gravar ação com 10 campos LGPD: `usuario, modulo, acao, descricao, hash_arquivo, ip, user_agent, client_hostname, timestamp` | `bd_manipulador.py:329-396` `registrar_auditoria` (INSERT em `:357-362`) |
| RF-AUD-04 | Rastreabilidade preenchida a partir do **contexto HTTP corrente** quando o chamador não informa (`__CTX__`) | `mod_intranet/bd_manipulador.py:88-95` (`contexto.contexto_atual()`) + `mod_intranet/contexto.py:71` |
| RF-AUD-05 | Timestamp em **horário local** (consistente com `tb_sessoes`) | `bd_manipulador.py:340-342` + `mod_intranet/bd_manipulador.py:96` |
| RF-AUD-06 | Tabela desaparecida no meio do caminho → recria e reinsere **uma vez**, sem perder a trilha | `bd_manipulador.py:363-382` (detecta `no such table`/`does not exist`/`undefined_table`) |
| RF-AUD-07 | Navegação **dinâmica** por tabela na tela (menu montado a partir do banco; módulo novo aparece sozinho) | `telas.py:198` `_opcoes_navegacao` (consumida em `:416-424`) + `telas.py:432-441` `nav_tabela` + `bd_manipulador.py:230` `get_tabelas_auditoria` |
| RF-AUD-08 | Busca com filtros: usuário (`LIKE`), módulo (exato), ação (`LIKE` + categorias coloridas), hora `HH:MM`, intervalo de datas | `bd_manipulador.py:483-531`; tela em `telas.py:409-503` |
| RF-AUD-09 | Sem tabela selecionada → `UNION ALL` de **todas** as tabelas por módulo (visão global) | `bd_manipulador.py:532-571` |
| RF-AUD-10 | Paginação **server-side** (`LIMIT ? OFFSET ?`) com total em `COUNT(*)` separado | `bd_manipulador.py:500`, `:525-530`; tela em `telas.py:285-318` (`total_paginas`) |
| RF-AUD-11 | Escolha de **campos visíveis e ordem** por auditor, persistida por usuário | `telas.py:150-168` `_campos_ativos` (`auditoria_campos:<usuario>`) + painel `ui.expansion` em `telas.py:504-536` |
| RF-AUD-12 | Exportar **CSV** da consulta atual (respeita os campos escolhidos) | `telas.py:321-339` `_exportar_csv` + botão `data-testid=auditoria-exportar` (`telas.py:501`) |
| RF-AUD-13 | Poda LGPD por retenção (`podar_registros(dias)`), aplicada uniformemente a todas as tabelas | `bd_manipulador.py:438-481`; agendado em `mod_intranet/rotinas.py:288` (`_job_poda_auditoria`, 24 h) + `:465` (`add_job`) |
| RF-AUD-14 | Migração única do `tb_auditoria` central legado para as tabelas por módulo, com marcador persistido; ao final **derruba** a tabela legada | `bd_manipulador.py:605-621` `migrar_dados_existentes` + `:582-602` `_remover_legado_central` |
| RF-AUD-15 | Visualizador **somente leitura** para `administrador_geral`; painel `/admin/auditoria` **não renderiza** para os demais | `telas.py:104` `eh_admin_geral`; `telas_administracao.py:66`, `:87-88` (`if not eh_admin_geral: return`) |
| RF-AUD-16 | Atualização automática da tabela a cada **30 s** | `telas.py:566` `ui.timer(30.0, _atualizar_tabela)` |
| RF-AUD-17 | Aba **Observabilidade** (dashboards Grafana) só quando a stack OTel está no ar | `telas.py:408` `obs_ligado = _dd.otel_stack_rodando()` + `abas(..., observabilidade=obs_ligado)` |
| RF-AUD-18 | Categorias de ação com **cor por tipo** (`CORES_ACAO`) na coluna Ação | `telas.py:54` `CORES_ACAO` + `telas.py:265-268` |

## Requisitos não-funcionais (RNF) — garantias técnicas

| RNF | Exigência | Evidência no código |
|:---|:---|:---|
| RNF-AUD-PERS-01 | Banco **exclusivo** da auditoria, um por módulo | `get_auditoria_connection` → `banco_conexao.conexao("auditoria")` (`bd_manipulador.py:130-146`) → `db_mod_auditoria.db` |
| RNF-AUD-PERS-02 | `PRAGMA journal_mode=WAL` + `synchronous=NORMAL` | `bd_manipulador.py:141-142` |
| RNF-AUD-PERS-03 | `busy_timeout=5000` herdado do núcleo + **retry 3× em `database is locked`** com rollback seguro | `banco_conexao.py:707` + `bd_manipulador.py:37-69` `_commit_com_retry` (`_TENTATIVAS_COMMIT = 3` em `:24`, backoff `0.05 × tentativa`) |
| RNF-AUD-PERS-04 | **Trilha nunca é perdida por contenção**: DDL só na primeira vez por sessão (fora da janela de lock) | `bd_manipulador.py:350-354` (`if tabela not in _TABELAS_GARANTIDAS`) |
| RNF-AUD-PERF-01 | 3 índices por tabela — `modulo`, `usuario`, `timestamp` | `bd_manipulador.py:207-211` |
| RNF-AUD-PERF-02 | Teto de página configurável (`auditoria_limite`, piso 10, default 1000) | `telas.py:144-146` |
| RNF-AUD-PERF-03 | Leitura **curta** (1 `COUNT` + 1 `SELECT`), sem carregar a tabela inteira | `bd_manipulador.py:525-530` |
| RNF-AUD-COMP-01 | Paridade SQLite ↔ PostgreSQL | `_sgbd()` (`:27-34`) escolhe o backend; `_tabela_existe` (`:72-96`) usa `information_schema.tables` no PG e `sqlite_master` no SQLite; `_sql_hora` (`:99-107`) → `to_char(...,'HH24:MI')` vs `strftime('%H:%M')`; `_sql_data_formatada` (`:110-118`) → `to_char(...,'DD/MM/YYYY HH24:MI:SS')`; `datetime('now','localtime')` → `LOCALTIMESTAMP` (proxy, `banco_conexao.py:471`); `cur.executescript` de 3 `CREATE INDEX` emulado no proxy (`banco_conexao.py:604-608`) |
| RNF-AUD-SEG-01 | Nome de tabela sempre derivado de `_nome_tabela()` (hífen→`_`), nunca input cru — com `# nosec B608` documentando o porquê | `bd_manipulador.py:127`, `:359`, `:206`, `:211` |
| RNF-AUD-SEG-01b | Tabelas do `UNION ALL` vêm de `get_modulos_com_auditoria()` (whitelist do próprio banco), não de string do usuário | `bd_manipulador.py:558-561`, `:562-566` (todos com `# nosec B608`) |
| RNF-AUD-SEG-02 | `Filtros parametrizados` (`?`) em toda a cláusula `WHERE`, inclusive `LIKE` e intervalo de datas | `bd_manipulador.py:505-522` |
| RNF-AUD-SEG-03 | Leitura da trilha é **read-only**: a tela não expõe escrita/edição/exclusão de registro | `telas.py:94-566` — só `buscar_logs`, `contar_registros`, `podar_registros` (esta última só via painel do admin) |
| RNF-AUD-RES-01 | `try/except` em toda função, com `log.exception` + retorno neutro (`0`, `[]`, `None`, `( [], 0 )`) — a trilha **nunca derruba** a tela nem o `try/except` do chamador | `bd_manipulador.py:29-34`, `:37-69`, `:90-96`, `:144-146`, `:157-161`, `:174-180`, `:221-227`, `:405-436`, `:494-498`, `:572-578`; `telas.py:379-389`, `:392-399`, `:283-318`, `:321-339` |
| RNF-AUD-UX-01 | `data-testid` nas ações de QA | `telas.py:411` (`auditoria-busca`), `telas.py:501` (`auditoria-exportar`) |
| RNF-AUD-UX-02 | Calendário em **popup** (abre só ao clicar) em vez de sempre aberto | `telas.py:447-483` `_campo_data` (`ui.menu` + `campo.on('click', _abrir)`) |
| RNF-AUD-UX-03 | Descrição truncada em 100 caracteres com reticências na tabela (tabela enxuta; o texto completo fica no CSV) | `telas.py:270-272` |
| RNF-AUD-I18N-01 | Docstring bilíngue EN/PT-BR nas telas; **exceção** no `bd_manipulador.py` (só PT-BR) | `telas.py:1-10` e `telas_administracao.py:1-5` são bilíngues; `bd_manipulador.py:1-8` **não** tem o bloco EN (ver DIV-AUD-01) |
| RNF-AUD-I18N-02 | Toda a UI em PT-BR; rótulos de campo derivados de `CAMPOS`/`_LABEL` | `telas.py:409-503` |

## Divergências e riscos

### Código faz, doc não diz

| # | Achado | Evidência |
|:---|:---|:---|
| DIV-AUD-01 | O docstring de módulo de `bd_manipulador.py` **não** segue o padrão bilíngue EN-topo/PT-BR-abaixo exigido pelo AGENTS.md (é PT-BR puro) | `bd_manipulador.py:1-8` |
| DIV-AUD-02 | `_TABELAS_GARANTIDAS` é um cache de sessão que só é invalidado quando o `INSERT` falha com "no such table" — se o DDL for feito por fora (restauração de backup, `psql`), a primeira escrita da sessão já cai no caminho de recuperação | `bd_manipulador.py:21`, `:352-354`, `:363-373` |
| DIV-AUD-03 | A aba Observabilidade (Grafana) é condicional à stack OTel, mas a doc da tela de auditoria não descreve o comportamento quando a stack está **fora** | `telas.py:408` |
| DIV-AUD-04 | `check_auditoria.py` (`main()`) é um verificador standalone de integridade da trilha que **não** é chamado por nenhum fluxo do sistema | `mod_auditoria/check_auditoria.py:26` — sem referência em `main.py` nem em `rotinas.py` |

### Doc diz, código não faz

| # | Alegação da doc | Estado real |
|:---|:---|:---|
| DIV-AUD-05 | Doc descreve a trilha como "somente `administrador_geral`" | A **rota** `/auditoria` só exige acesso ao módulo (`main.py:601-605` → `pagina_restrita(..., chave_modulo="auditoria")`); o `eh_admin_geral` de `telas.py:104` controla **cores/aparência e a aba de Administração**, não a leitura da trilha. Um `administrador` do módulo com papel `comum` **lê a trilha** e só não gerencia. |
| DIV-AUD-06 | Doc cita "retenção LGPD 90 dias" como padrão | Confirmado: `telas.py:147` `retencao_dias = _cfg("retencao_dias", "90")` — mas é **texto de config**, e quem efetivamente executa a poda é `_job_poda_auditoria` (`mod_intranet/rotinas.py:288`), que precisa ler essa chave. |

### Riscos

| # | Risco | Severidade | Evidência |
|:---|:---|:---|:---|
| **RISCO-AUD-01** | ~~**`v-html` sem escape na coluna "Ação"**~~ **Corrigido 26/09/2026.** A coluna montava `<span style="color:...">{raw["acao"]}</span>` e o slot `body-cell-acao` renderiza por `v-html`; `acao` é uma string livre em `_audit(usuario, acao, ...)`, então qualquer valor fora de `CORES_ACAO` caía direto no HTML. Agora `html.escape()` é aplicado ao `acao` (e só ele — `descricao` e `hash` são renderizados como texto pelo Quasar, que já escapa). | ✅ **Corrigido 26/09/2026** | `telas.py:266-276` |
| **RISCO-AUD-02** | **`contar_registros()` sem tabela faz N+1**: um `COUNT(*)` por tabela de módulo | `bd_manipulador.py:415-426` — com ~12 módulos são 12 `COUNT`s a cada montagem do dashboard |
| **RISCO-AUD-03** | **`_exportar_csv` exporta só `_ultimos_logs`** (a página atual, ≤ `auditoria_limite` = 1000), mas a dica da UI não avisa disso. Quem filtrou 50 mil registros e exportou recebe 1 000 linhas sem indicação. | 🟡 Baixa | `telas.py:323-336` |
| **RISCO-AUD-04** | **Zero `async` / `run.io_bound` / `spinner`** no módulo. `_atualizar_tabela` (chamada pelo `ui.timer(30.0)` e por cada clique em "Buscar") roda `COUNT` + `SELECT` + `UNION ALL` de N tabelas direto no event-loop. Com trilha grande, o poll de 30 s por auditoria acumulada e derruba o WebSocket — viola AGENTS.md §5.1. | 🟠 Média | `telas.py:566` + ausência de `async def` em `mod_auditoria/*.py` |
| **RISCO-AUD-05** | `buscar_logs` sem `tabela` monta o `UNION ALL` por chamada (string concatenada a partir de N tabelas) — o **plano de consulta é re-parseado a cada busca**, e `COUNT` roda sobre o mesmo `UNION` (2 varreduras). Em PostgreSQL isso é o pior caso do planejador. | 🟡 Baixa | `bd_manipulador.py:557-570` |
| **RISCO-AUD-06** | `check_auditoria.py` não é executado por nenhum job — a verificação de integridade da trilha depende de alguém rodar o script à mão. | 🟡 Baixa | `mod_auditoria/check_auditoria.py:26` |
