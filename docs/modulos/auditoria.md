# Audit Module — `mod_auditoria`

> Audit module: route `/auditoria` (key `auditoria`) · EXCLUSIVE database `db_mod_auditoria.db` with ONE TABLE PER PRODUCER MODULE (`tb_auditoria_<modulo>`) · single writer (`audit_log`) reached through a decoupled hook · write cache + 3× commit retry · meta-first table discovery with `information_schema`/`sqlite_master` fallback · `to_char` vs `strftime` helpers · read-only viewer with dynamic table navigation, filters, server-side pagination, CSV export and per-auditor column selection/ordering.

---

# Módulo Auditoria — `mod_auditoria`

> Módulo de auditoria: rota `/auditoria` (chave `auditoria`) · **banco EXCLUSIVO** `db_mod_auditoria.db` com **UMA TABELA POR MÓDULO PRODUTOR** (`tb_auditoria_<modulo>`) · escritor **único** (`audit_log`) por **gancho desacoplado** · cache de escrita + retry 3× no commit · descoberta de tabela pela meta com fallback `information_schema`/`sqlite_master` · helpers `to_char` vs `strftime` · visualizador somente-leitura com navegação dinâmica por tabela, filtros, paginação server-side, exportação CSV e seleção/ordem de campos por auditor.

## Propósito

Banco e visualizador da trilha de auditoria LGPD. A **escrita** é feita pelos demais módulos via `audit_log` (núcleo) → `registrar_auditoria` (este módulo), que grava na tabela do módulo produtor — criada automaticamente. A **leitura** é feita pela tela `/auditoria` (exclusiva do `administrador_geral`).

## Banco de dados

Criador vigente: `init_db_auditoria()` em `bd_manipulador.py` (executado no import e pelo bootstrap central).

| Tabela | Conteúdo |
|:---|:---|
| `tb_auditoria_<modulo>` | UMA POR MÓDULO produtor: `usuario`, `modulo`, `acao`, `descricao`, `timestamp` (local — RF-08), `hash_arquivo`, `ip`, `user_agent`, `client_hostname`; índices por módulo/usuário/timestamp. O `hash_arquivo` é opaco: o cálculo (ex. SHA-256) é feito pelo módulo produtor e repassado via `audit_log` → `registrar_auditoria` |
| `tb_auditoria_meta` | registro dos módulos produtores (`modulo` PK, `nome`, `criada_em`) |

- **Migração idempotente** do legado central (`migrar_dados_existentes`) + remoção da antiga `tb_auditoria` do banco central.
- **Poda LGPD** diária (`podar_registros`, `auditoria_retencao_dias` default 90 — job `poda_auditoria`).
- **Descoberta de tabela em 2 fontes**: primária `tb_auditoria_meta` (portátil); fallback por backend — `information_schema.tables` no PostgreSQL, `sqlite_master` **só** no SQLite (via proxy, `SELECT` em `sqlite_master` no PG devolveria vazio sem erro).
- **Helpers de data/hora portables**: `_sql_hora()` e `_sql_data_formatada()` escolhem `to_char(...)` no PG e `strftime(...)` no SQLite — o filtro de hora e o intervalo de datas funcionam nos dois backends.
- **Cache de escrita** (`_TABELAS_GARANTIDAS`): o `CREATE TABLE` + registro na meta só rodam na **primeira** gravação do módulo na sessão; se o `INSERT` falhar com `no such table`/`undefined_table`, o cache é invalidado, a DDL é regarantada e o `INSERT` refeito uma vez (a trilha não se perde).
- **Retry 3× no commit** (`_commit_com_retry`, backoff `0.05s × tentativa`): re-tenta só em contenção (`locked`/`busy`/`timeout`), faz `rollback` seguro, registra `log.exception` e devolve `False` — **falha de auditoria nunca derruba a operação de negócio**.

## Funcionalidades

- **Acesso exclusivo `administrador_geral`** — dupla camada: bloqueio interno + exigência da chave `auditoria` em `pagina_restrita`. Sem permissão: `acesso_negado` na trilha (choke point único).
- **Navegação dinâmica por tabela**: select "Visualizar auditoria de" montado do banco ("Todas as auditorias" = UNION ALL, ou a tabela de um módulo).
- **Filtros**: Usuário (LIKE), Ação (categorias prontas coloridas + texto livre), Hora (`_sql_hora()`: `to_char` no PG / `strftime` no SQLite), intervalo de datas (calendário em popup).
- **Paginação server-side**: `LIMIT ? OFFSET ?` (`auditoria_limite`, default 1000) com contador e Anterior/Próxima; auto-atualização a cada 30 s.
- **Campos/ordem por auditor**: painel com mover ↑/↓, ocultar, adicionar e "Restaurar padrão", persistido em `auditoria_campos:<usuario>` (JSON).
- **Exportação CSV**: página corrente respeitando campos/ordem do auditor.
- **Colunas padrão**: Data/Hora, Usuário, Módulo, Ação (cores por tipo — `CORES_ACAO`), Descrição (100 chars), Hash, IP, dispositivo.
- **Aba Observabilidade** (quando a stack OTel está no ar): atalhos para os dashboards Grafana (Visão Geral, Traces, Logs) + aviso LGPD sobre a senha do Grafana.
- **Painel Administração standalone** (`telas_administracao.py`, rota `/admin/auditoria`): `auditoria_limite`, `auditoria_retencao_dias`, `auditoria_texto_header` + card padrão **"Configurações de cores"** (`auditoria_*` — vazios usam o padrão do PRÓPRIO módulo via `PADROES_TEMA["auditoria"]` = `#000000`, sem herança do tema do sistema); salvar audita a si mesmo. O cabeçalho usa `chave_modulo="auditoria"` (`telas.py:345`): a borda de destaque é a **mesma cor dos botões do módulo**.
- **Responsividade (RNF-UI-01, 09/2026 — auditado 320/768/1024 `kbp-web-design`)**: `overflow-x-auto` em tabs/filtros/tabela, barra de filtros `flex-wrap` `gap` via `.style`, `truncate` em colunas longas, dialogs `w-full max-w`; proposta P0/P1/P2 por `container`/`row`/`grid` (header `flex-wrap` `min-width:0`).
- **Versionamento**: `versao_modulo:auditoria = 1.0.260908`.

## Permissões

| Ação | `comum` | `administrador_modulo` | `administrador_geral` |
|:---|:---:|:---:|:---:|
| Acessar `/auditoria` | ✗ | ✗ | ✓ |
| Exportar CSV | ✗ | ✗ | ✓ |

## Rota e integrações

- Rota: `/auditoria` (chave `auditoria`) — `main.py`. Administração: `/admin/auditoria` (`telas_administracao.mostrar_administracao`).
- **Escrita — escritor único**: `mod_intranet/bd_manipulador.py::audit_log()` (resolve IP/UA do contexto HTTP + carimbo local RF-08) → **gancho** `registrar_hook_auditoria` → `registrar_auditoria`. O gancho **remove a dependência cíclica núcleo↔auditoria** (o núcleo não importa este módulo no caminho quente; o import lazy é só o fallback). Produtores: todos os módulos, o próprio núcleo (login/logout/falhas/config/backups) e os **jobs APScheduler com ator `sistema`** (coleta do agregador, varredura de empenhos).
- **Leitura**: `buscar_logs`/`get_modulos_com_auditoria`/`contar_registros` (usado pelo resumo do dashboard).
- **Poda**: job diário `poda_auditoria` (`mod_intranet/rotinas.py:74-103`).
- Auditoria é **preservada** pela cascata LGPD de exclusão de usuário (só as autorias nos bancos de negócio são removidas/anonimizadas).

## Testes

```bash
.venv/bin/python assets/test/test_auditoria.py   # 12/12 (índices, audit_log rastreável, poda LGPD, acesso exclusivo, prefs por usuário)
.venv/bin/python mod_auditoria/check_auditoria.py  # diagnóstico standalone (portátil SQLite↔PG, só log)
```

## Pontos de atenção

- Exportação cobre a **página corrente** (não a consulta inteira).
- Ações novas/desconhecidas podem ser filtradas por texto livre no select de Ação.
- `bd_criador.py` é legado — o esquema real vive em `bd_manipulador.py`.
- `sqlite_master` só é consultado no **ramo SQLite**; no PostgreSQL a consulta equivalente é `information_schema.tables` (via proxy, `sqlite_master` devolveria vazio silenciosamente).

Ver [Análise do Módulo](../analise_mod_auditoria.md).
