# Auditoria — `mod_auditoria`

> Audit module: route `/auditoria` (key `auditoria`) · EXCLUSIVE database `db_mod_auditoria.db` with ONE TABLE PER PRODUCER MODULE (`tb_auditoria_<modulo>`) · read-only viewer with dynamic table navigation, filters by user/module/action/time/date range, server-side pagination, CSV export, per-auditor column selection/ordering, Grafana observability tab.

---

# Auditoria — `mod_auditoria`

> Módulo de auditoria: rota `/auditoria` (chave `auditoria`) · **banco EXCLUSIVO** `db_mod_auditoria.db` com **UMA TABELA POR MÓDULO PRODUTOR** (`tb_auditoria_<modulo>`) · visualizador somente-leitura com navegação dinâmica por tabela, filtros por usuário/módulo/ação/hora/intervalo de datas, paginação server-side, exportação CSV, seleção/ordem de campos por auditor e aba de Observabilidade (Grafana).

## Propósito

Banco e visualizador da trilha de auditoria LGPD. A **escrita** é feita pelos demais módulos via `audit_log` (núcleo) → `registrar_auditoria` (este módulo), que grava na tabela do módulo produtor (`tb_auditoria_<modulo>`, criada automaticamente). A **leitura** é feita pela tela `/auditoria` (exclusiva do `administrador_geral`), com filtros, paginação server-side e exportação CSV. As preferências de coluna e as configurações vão para `tb_config` central.

## Banco exclusivo (`db_mod_auditoria.db`, WAL)

Criador vigente: `init_db_auditoria()` em `db_manipulador.py:25-38` (executado no import e pelo bootstrap central).

- **`tb_auditoria_<modulo>`** — UMA TABELA POR MÓDULO (nome sanitizado: hífen vira `_`, ex. `edit-pdf` → `tb_auditoria_edit_pdf`). Colunas: `id`, `usuario`, `modulo`, `acao`, `descricao`, `timestamp` (horário local — RF-08), `hash_arquivo`, `ip`, `user_agent`, `client_hostname`; índices por `modulo`, `usuario` e `timestamp`.
- **`tb_auditoria_meta`** — registro dos módulos produtores (`modulo` PK, `nome`, `criada_em`).
- **Migração idempotente** do legado: `migrar_dados_existentes()` (`db_manipulador.py:273-324`) copia a antiga `tb_auditoria` do banco central para as tabelas por módulo, marca `auditoria_migracao_concluida=1` na `tb_config` e **remove a tabela legada** do central.
- **Poda LGPD**: `podar_registros(dias)` (`db_manipulador.py:147-171`) remove registros mais antigos que o prazo em TODAS as tabelas — chamada diariamente pelo job `poda_auditoria` (`mod_intranet/rotinas.py:74-103`, `auditoria_retencao_dias`, default 90).

!!! note "Escrita automática por novos módulos"
    `registrar_auditoria` (`db_manipulador.py:99-124`) cria a tabela do módulo e o registro em `tb_auditoria_meta` na primeira gravação — um módulo novo passa a auditar **sem nenhuma edição** neste módulo.

## Estrutura do pacote

- `db_manipulador.py` — conexão WAL, criação/garantia de tabelas, `registrar_auditoria`, `contar_registros`, `podar_registros`, `buscar_logs` (filtros + paginação), descoberta de módulos (`get_modulos_com_auditoria`/`get_tabelas_auditoria`) e migração do legado.
- `telas.py` — visualizador (`mostrar_tela(usuario_logado, perfil)`).
- `db_criador.py` — **legado** (cria apenas `tb_auditoria_meta`; o esquema real é o de `db_manipulador.py`).
- `check_auditoria.py` — script diagnóstico standalone (lista chaves `auditoria%` da `tb_config` central).

## Fluxo da tela

- **Acesso exclusivo ao `administrador_geral`** — dupla camada: bloqueio interno + exigência da chave `auditoria` em `pagina_restrita`. Tentativa sem permissão gera `acesso_negado` na trilha (choke point único em `layout_tela.pagina_restrita`).
- **Navegação dinâmica por tabela**: select "Visualizar auditoria de" montado a partir do banco (`get_modulos_com_auditoria`) — "Todas as auditorias" (UNION ALL) ou a tabela de um módulo específico; rótulos amigáveis por chave (`DEFS_NAV`).
- **Filtros**: Usuário (LIKE), Ação (select com **categorias prontas** coloridas `CORES_ACAO` + texto livre via `with_input`), Hora (`strftime('%H:%M')`), intervalo de datas (campos com calendário em popup).
- **Paginação server-side**: `LIMIT ? OFFSET ?` (`auditoria_limite` como tamanho de página, default 1000) com contador e botões Anterior/Próxima; auto-atualização a cada 30 s.
- **Campos/ordem por auditor**: painel "Campos e ordem de exibição" com mover ↑/↓, ocultar, adicionar e "Restaurar padrão"; persistido em `tb_config` na chave `auditoria_campos:<usuario>` (JSON). Coluna "Ação" colorida por categoria.
- **Exportação CSV**: baixa o resultado filtrado da página corrente respeitando os **campos e a ordem** selecionados pelo auditor.
- **Colunas padrão**: Data/Hora, Usuário, Módulo, Ação, Descrição (truncada a 100 chars), Hash, IP e rótulo de dispositivo (`rotulo_dispositivo`).
- **Aba Observabilidade** (só quando a stack OTel está no ar — `docker_detector.otel_stack_rodando()`): cards de atalho para os dashboards Grafana (Visão Geral, Traces, Logs) com aviso LGPD sobre a senha padrão do Grafana.
- **Aba Administração** (expansão, exclusiva do admin geral): `auditoria_limite`, `auditoria_retencao_dias`, `auditoria_texto_header` + card padrão **"Configurações de cores"** (`auditoria_cor_botao`, `auditoria_cor_texto_botao`, `auditoria_cor_fundo`, `auditoria_cor_titulo`, `auditoria_btn_tamanho` — vazios usam o padrão do PRÓPRIO módulo via `PADROES_TEMA["auditoria"]` = `#000000`, sem herança do tema do sistema). Salvar também **audita a si mesmo** (`auditoria`, `configuracao`).

## Integrações com o núcleo

- **Escrita**: `mod_intranet.bd_manipulador.audit_log` preenche IP/UA do contexto (`mod_intranet.contexto`) e chama `registrar_auditoria` — produtores: todos os módulos + o próprio núcleo (login/logout/falhas/configurações/backups).
- **Leitura**: `buscar_logs` (UNION ALL entre tabelas ou tabela única), `get_modulos_com_auditoria` (menu dinâmico), `contar_registros` (resumo do dashboard).
- **Config**: `get_config`/`set_config` centrais (`auditoria_limite`, `auditoria_retencao_dias`, `auditoria_texto_header`, `auditoria_campos:<usuario>`, tema `auditoria_*`).
- **Poda**: job diário `poda_auditoria` do APScheduler central.
- **Versionamento**: `versao_modulo:auditoria = 1.0.260908` (seed em `db_manipulador._semear_versao_modulo` e `conexao_bd.init_db()`), exibido no rodapé de `/auditoria`.

## Pontos de atenção

- Consulta além de `auditoria_limite` numa página usa os botões de paginação; a exportação CSV cobre a página corrente (na ordem do auditor).
- Ações desconhecidas/novas podem ser filtradas por texto livre no select de Ação.
- A preferência de colunas é por usuário (`auditoria_campos:<usuario>`); como o módulo é exclusivo do admin geral, na prática vale para qualquer auditor.
- `db_criador.py` é legado — não executar como fonte de verdade.

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
