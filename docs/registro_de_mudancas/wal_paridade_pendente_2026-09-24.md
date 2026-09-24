# WAL + Parity Plan (pending, no code changed)

> Pending QA plan for WAL + SQLite↔PostgreSQL parity across 9 audited modules (intranet, gest_cad_usuario, auditoria, blog, edit_pdf, renomear_empenho, solicita_impressao, tecnico, filas). Central findings: hot-path WAL present (`banco_conexao.py:620`), 3 raw connects without WAL (`banco_conexao.py:74,90`, `ativacao.py:502`), zero `busy_timeout` in repo, no full `CrudBase` in 8/9, PG breaks (`sqlite_master`, `strftime`, `GROUP BY`, `COLLATE NOCASE`, FTS5, removed FK). NO code fix applied — documentation only, contained per-module proposals. `lista_telefonica` + `agregador_noticias` QA still pending.

---

# Plano WAL + Paridade (pendente, sem alteração de código)

> Plano QA pendente de WAL + paridade SQLite↔PostgreSQL nos 9 módulos auditados (intranet, gest_cad_usuario, auditoria, blog, edit_pdf, renomear_empenho, solicita_impressao, tecnico, filas). Achados centrais: WAL presente no quente (`banco_conexao.py:620`), 3 connects crus sem WAL (`banco_conexao.py:74,90`, `ativacao.py:502`), zero `busy_timeout` no repo, sem `CrudBase` completo em 8/9, quebras PG (`sqlite_master`, `strftime`, `GROUP BY`, `COLLATE NOCASE`, FTS5, FK removida). NENHUMA correção de código aplicada — só documentação, com propostas contidas por módulo. QA de `lista_telefonica` + `agregador_noticias` ainda pendente.

## Escopo e regras

- **Só documentação:** nenhum `.py` foi alterado; nada em `db_*.db`, `backup/`, `logs/`, `site/`.
- **Regra de ouro (AGENTS.md §1-2):** toda correção futura DEVE viver contida no próprio `mod_*` (conexão via `mod_intranet/banco_conexao.conexao(chave)` ou `CrudBase`, sem cross-query entre bancos).
- **Fontes lidas:** `docs/arquitetura.md`, `docs/visao_geral.md`, `docs/convencoes_codigo.md` + `docs/analise_mod_*.md` dos 9 módulos + verificação pontual no código (arquivo:linha abaixo).
- **Faltam auditar:** `lista_telefonica` + `agregador_noticias` (fora deste lote; sem linha proposta aqui).

## Tabela consolidada — módulo | achado | arquivo:linha | correção proposta contida no módulo | risco regressão

| Módulo | Achado | Arquivo:linha | Correção proposta contida no módulo | Risco regressão |
|:---|:---|:---|:---|:---|
| intranet (núcleo) | 3 connects crus sem WAL; zero `busy_timeout` no repo; WAL OK no quente | `mod_intranet/banco_conexao.py:74`, `:90` (sem WAL) · `mod_intranet/ativacao.py:502` (sem WAL) · `mod_intranet/banco_conexao.py:619-620` (quente COM WAL) · `mod_intranet/crud_base.py:112,124-125` (padrão WAL) | Criar helper interno `_conectar_wal()` em `banco_conexao.py` + reutilizar em `ativacao.py:502`; aplicar `PRAGMA journal_mode=WAL` + `synchronous=NORMAL` + `busy_timeout=5000` só nesses 3 pontos, sem mudar assinatura pública | Baixo-médio (boot/assistente; validar fresh-install + `garantir_bancos`) |
| gest_cad_usuario | ~~Sem `CrudBase` completo; `sqlite_master` em migração/seed; `GROUP_CONCAT` agregado~~ → **CORRIGIDO 24/09/2026 (ver § Correção aplicada — gest_cad_usuario abaixo)** | `mod_gest_cad_usuario/bd_manipulador.py:47` (`_eh_violacao_unicidade`), `:71` (`_eh_bloqueio_banco`), `:79` (`_rollback_seguro`), `:91` (`_commit_com_retry`), `:238-264` (FK por `sgbd_ativo`), `:455` + `:464-466` (`GROUP_CONCAT` + GROUP BY completo), `:723` (limpeza órfãos), `:23` + `:353-411` (seeds preservados) | Helpers unicidade/retry + GROUP BY completo + FK por SGBD + limpeza órfãos, tudo contido no módulo (sem `CrudBase`; `GROUP_CONCAT` mantido — proxy traduz p/ `STRING_AGG`) | Superada (testes 19/19, 13/13, 20/20) |
| auditoria | ~~Sem `CrudBase`; `sqlite_master` em 3 pontos; `strftime` em SQL (sem tradução no proxy)~~ → **CORRIGIDO 24/09/2026 (ver § Correção aplicada — auditoria abaixo)** | `mod_auditoria/bd_manipulador.py:27` (`_sgbd`), `:37` (`_commit_com_retry`), `:72` (`_tabela_existe`), `:99` (`_sql_hora`), `:110` (`_sql_data_formatada`), `:245` (meta primária) + `:260-269` (fallback `information_schema`/`sqlite_master`), `:352-354` (cache escrita) + `:367-375` (invalidação), `:637` (migração portável) · `mod_auditoria/check_auditoria.py:31` (`conexao("intranet")`) | Meta primária + `information_schema` no PG; `to_char` vs `strftime` em helpers do módulo; cache `_TABELAS_GARANTIDAS` + retry 3x; migração e `check` portáveis, tudo contido no módulo (sem `CrudBase`) | Superada (testes 12/12) |
| blog | Referência `CrudBase` 100% — sem migração; validar paridade de datas/`GROUP BY` | `mod_blog/bd_manipulador.py:24`, `:104` (`CrudBase` piloto) | Nenhuma migração; só bateria paridade SQLite↔PG (datas como string via `_normalizar_valor`, `banco_conexao.py:516`; `GROUP_CONCAT`→`STRING_AGG` se usado) | Baixo (módulo piloto; rodar `teste_fluxo_blog.py`) |
| edit_pdf | Sem `CrudBase`; `strftime` só em Python (OK); auditar `GROUP BY`/`COLLATE` | `mod_edit_pdf/bd_manipulador.py:215`, `:423` (`strftime` Python — sem quebra) | Migrar `bd_manipulador.py` para `CrudBase` + `conexao("editar_pdf")`; varredura interna de `GROUP BY`/`COLLATE` antes de fechar | Médio (cotas 1 GB/10 GB + expiração 10 min + ZIP) |
| renomear_empenho | Sem `CrudBase`; FTS5 `VIRTUAL TABLE` + `sqlite_master` (degrada no PG por desenho) | `mod_renomear_empenho/bd_manipulador.py:687`, `:786` (`VIRTUAL TABLE fts5`) · `:773` (`sqlite_master`) · `:660` (fallback LIKE documentado) | Manter fallback LIKE no PG; isolar FTS5 em ramo SQLite; migrar CRUD comum para `CrudBase`; helper `_tabela_existe()` interno | Médio (monitor 60 s + quarentena + organizador) |
| solicita_impressao | `CrudBase` parcial (só config local); `COLLATE NOCASE` em 3 buscas (quebra PG) | `mod_solicita_impressao/bd_manipulador.py:24`, `:31` (parcial) · `:1920-1926`, `:2737-2742`, `:2848-2851` (`COLLATE NOCASE`) | Completar migração `CrudBase`; trocar `LIKE ? COLLATE NOCASE` por helper interno portável (`LOWER(col) LIKE LOWER(?)` ou `ILIKE` no ramo PG, contido no módulo) | Médio-alto (cotas 1000/200 + autorização grupo + relatório cobrança) |
| tecnico | Sem `CrudBase`; sem quebra PG localizada (varredura pendente fina) | `mod_tecnico/bd_manipulador.py` (sem `CrudBase` — verificado por busca) | Migrar para `CrudBase` + `conexao("tecnico")`; varredura `GROUP BY`/`COLLATE`/`strftime` SQL dentro do módulo | Baixo-médio (software ZIP + backup `YYYYMMDD_HHMM_nomePc_ip`) |
| filas | Sem `CrudBase`; `sqlite_master` em migração de `tb_midia` | `mod_filas/bd_manipulador.py:75` (`sqlite_master`) · sem `CrudBase` (verificado por busca) | Migrar para `CrudBase`; trocar `sqlite_master` por `_tabela_existe()` interno; testar TV `/tv`, `/tv/{id}`, `/tv?grupo=` nos dois backends | Médio (voz claim + ducking + `/midia_filas`) |
| lista_telefonica | QA WAL+paridade **pendente** (fora do lote de 9) | — | Aguardar auditoria `kbp-qa` antes de propor | A definir |
| agregador_noticias | QA WAL+paridade **pendente** (fora do lote de 9) | — | Aguardar auditoria `kbp-qa` antes de propor (atenção: sem backup, `reiniciar_banco` diário) | A definir |

## Achados transversais (valem para todos)

- **WAL quente OK:** `banco_conexao.py:619-620` aplica `PRAGMA journal_mode=WAL`; `crud_base.py:112,125` e `repositorio.py:164` também.
- **Crus sem WAL:** `banco_conexao.py:74,90` + `ativacao.py:502` usam `sqlite3.connect` sem pragmas — corrigir só ali.
- **`busy_timeout` zero:** nenhuma ocorrência no repo (busca sem retorno); incluir `PRAGMA busy_timeout=5000` (ou `timeout=` no connect) junto da correção WAL.
- **Tradução PG existente (não reinventar):** `_CursorPostgres` (`banco_conexao.py:390-545`) já cobre `?`→`%s`, `GROUP_CONCAT`→`STRING_AGG` (`:435-437`), `INSERT OR IGNORE/REPLACE`→`ON CONFLICT`, `PRAGMA`/`sqlite_master`/FTS5 degradados (`:462-467`), `PRAGMA table_info`→`information_schema`, `lastrowid` via `RETURNING`, datas→string (`:545`). Correções devem **usar** essa camada, não duplicá-la.
- **FK removida:** `_ddl_postgres` (`banco_conexao.py:358`) remove `FOREIGN KEY` — módulos não devem confiar em cascata no PG; integridade em código onde houver `CASCADE` (ex. `tb_comentarios` no blog).

## Próximos passos (quando houver pedido de código)

1. Auditar `lista_telefonica` + `agregador_noticias` (lote faltante).
2. Aplicar correções **uma por módulo**, na ordem: intranet (base) → auditoria → gest → solicita → renomear → filas → tecnico → edit_pdf → blog (só testes).
3. Validar cada módulo com `.venv/bin/pytest` + boot SQLite e boot Postgres (`banco_tipo=postgres`).
4. Extração semântica LLM (`/graphify --update`) pendente se esta doc for considerada relevante para o grafo.

> **NÃO commitar** este arquivo (regra `kbp-doc`). Sem `commit`/`push` pelo documentador.

## Correção aplicada 24/09/2026 — gest_cad_usuario (código já corrigido, lote só-documentação)

> EN: Fix applied 24/09/2026 in `mod_gest_cad_usuario/bd_manipulador.py` (no .py touched in this batch): uniqueness/retry helpers, full GROUP BY, FK per active SGBD, orphan cleanup, preserved seeds; tests 19/19 + 13/13 + 20/20, verdict PASS. Other modules in the table above remain pending.

> Correção aplicada em 24/09/2026 em `mod_gest_cad_usuario/bd_manipulador.py` (nenhum `.py` tocado neste lote): helpers de unicidade/retry, GROUP BY completo, FK por SGBD ativo, limpeza de órfãos, seeds preservados; testes 19/19 + 13/13 + 20/20, veredito APROVADO. Demais módulos da tabela acima seguem pendentes.

| Tema | Antes | Depois — arquivo:linha |
|:---|:---|:---|
| Helpers unicidade/retry | `IntegrityError` genérico; sem retry em `database is locked` | `_eh_violacao_unicidade` (`mod_gest_cad_usuario/bd_manipulador.py:47`); `_eh_bloqueio_banco` (`:71`); `_rollback_seguro` (`:79`); `_commit_com_retry` (`:91`); `_conexao_segura` (`:121`) |
| GROUP BY completo | `GROUP_CONCAT` sem GROUP BY total (quebra PG) | `listar_usuarios` (`:438`); `GROUP_CONCAT` (`:455` → `STRING_AGG` via proxy); `GROUP BY` completo (`:464-466`); `_normalizar_data` (`:425`) |
| FK por `sgbd_ativo` | `sqlite_master` + `ON UPDATE CASCADE` nos dois backends | `sgbd_ativo()` (`:238-264`): rebuild CASCADE só no SQLite; no PG integridade na aplicação (`renomear_usuario` `:718-719`); `flags` check-then-add (`:268-272`) |
| Limpeza de órfãos | Sem cobertura PG (FK removida no `_ddl_postgres`) | `DELETE ... NOT IN (SELECT ...)` (`:723`, best-effort); upsert `ON CONFLICT` (`:1037-1044`) |
| Seeds preservados | Risco em `master`/`qacomum`/`qamaster` | `ACESSO_PADRAO_NOVO_USUARIO` (`:23`); auto-cura `master` (`:343-350`); seeds (`:353-373`, `:382-411`); troca forçada mantida (AGENTS §8.2) |

### Testes e veredito

| Suíte | Resultado |
|:---|:---|
| `assets/test/teste_fluxo_autenticacao.py` | 19/19 OK |
| `assets/test/teste_fluxo_permissoes.py` | 13/13 OK |
| `assets/test/teste_flags_permissao.py` | 20/20 OK |

**Veredito: APROVADO — sem regressão.** Linha `gest_cad_usuario` da tabela consolidada marcada como superada; escopo/navegação MkDocs (`readthedocs`) inalterados.

## Correção aplicada 24/09/2026 — auditoria (código já corrigido, lote só-documentação)

> EN: Fix applied 24/09/2026 in `mod_auditoria/bd_manipulador.py` (no .py touched in this batch): meta-first discovery + `information_schema` fallback, `to_char` vs `strftime` helpers, write cache + 3x commit retry, portable migration, portable check; tests 12/12 in `assets/test/test_auditoria.py`, verdict PASS. Other pending modules in the table above remain unchanged.

> Correção aplicada em 24/09/2026 em `mod_auditoria/bd_manipulador.py` (nenhum `.py` tocado neste lote): descoberta via meta + fallback `information_schema`, helpers `to_char` vs `strftime`, cache de escrita + retry 3x, migração portável, `check` portável; testes 12/12 em `assets/test/test_auditoria.py`, veredito APROVADO. Demais módulos pendentes da tabela acima seguem inalterados.

| Tema | Antes | Depois — arquivo:linha |
|:---|:---|:---|
| Descoberta via meta + `information_schema` | `sqlite_master` em 3 pontos, sem ramo PG | Fonte primária `tb_auditoria_meta` (`mod_auditoria/bd_manipulador.py:245`); fallback por backend (`:256-269`): `information_schema.tables` no PG (`:260-267`), `sqlite_master` só no SQLite (`:268`); `_tabela_existe()` portável (`:72-96`) com `_sgbd()` (`:27-34`) |
| Filtros hora/data `to_char` | `strftime` em SQL sem tradução no proxy | `_sql_hora()` (`:99-107`, `to_char(col,'HH24:MI')` vs `strftime('%H:%M')`) usado em (`:515`, `:548`); `_sql_data_formatada()` (`:110-118`, `to_char(col,'DD/MM/YYYY HH24:MI:SS')` vs `strftime('%d/%m/%Y %H:%M:%S')`) usado em (`:528`, `:564`) |
| Cache de escrita + retry | DDL+commit por escrita; `database is locked` sem retry | `_TABELAS_GARANTIDAS` (`:21`) + `_TENTATIVAS_COMMIT = 3` (`:24`); `registrar_auditoria` (`:352-354` cache, `:367-375` invalidação/regarante em `no such table`/`undefined_table`); `_commit_com_retry()` (`:37-69`); `get_auditoria_connection()` via `conexao("auditoria")` + `PRAGMA journal_mode=WAL`/`synchronous=NORMAL` (`:130-146`) |
| Migração portável | `sqlite_master` no legado central | `_migrar_dados_existentes_seguro()` (`:623`): `_tabela_existe(central_conn, "tb_auditoria")` (`:637`); garante meta (`:665-666`); `_commit_com_retry` (`:679`); marca `auditoria_migracao_concluida=1` + remove legado (`:696-697`) |
| `check` portável | Risco de `sqlite3` cru | `check_auditoria.py` via `conexao("intranet")` (`:31-33`), `SELECT ... WHERE chave LIKE 'auditoria%'` (`:35`), log `logs/auditoria_*.log` — ferramenta dev-only, sem uso pela aplicação |

### Testes e veredito

| Suíte | Resultado |
|:---|:---|
| `assets/test/test_auditoria.py` (3 índices + 4 `audit_log` + 2 poda + 2 acesso + 1 prefs) | 12/12 OK |

**Veredito: APROVADO — sem regressão.** Linha `auditoria` da tabela consolidada marcada como superada; escopo/navegação MkDocs (`readthedocs`) inalterados.
