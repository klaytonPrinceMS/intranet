# Auditoria — `mod_auditoria`

> Audit viewer module: route `/auditoria` (key `auditoria`) · no own database — reads unified `tb_auditoria` from central `db_mod_intranet.db` · read-only, filters by user/module/action/date, IP and device summary, server-side pagination, CSV export and per-auditor column selection/ordering.

---

# Auditoria — `mod_auditoria`

> Módulo visualizador de auditoria: rota `/auditoria` (chave `auditoria`) · **sem banco próprio** — lê `tb_auditoria` unificada do central `db_mod_intranet.db` · somente-leitura, filtros por usuário/módulo/ação/data/hora, IP e **rótulo de dispositivo** (`rotulo_dispositivo`), paginação server-side, exportação CSV e seleção/ordem de campos por auditor.

## Propósito

Visualizador somente-leitura da trilha de auditoria LGPD unificada gravada pelos demais módulos via `audit_log`. Permite filtrar e inspecionar registros (data/hora, usuário, módulo, ação, descrição, IP, rótulo de dispositivo). Não escreve em nenhuma tabela (as preferências de coluna e as configs vão para `tb_config` central).

## Estrutura do pacote

Contém apenas `telas.py` (com `__init__.py` vazio) e `check_auditoria.py` (script diagnóstico). Não há `manipulador_bd`: o único ponto de entrada é `mostrar_tela(usuario_logado, perfil)` e a leitura usa `get_connection()` do núcleo importada dentro da função.

## Fluxo da tela

- **Acesso exclusivo ao `administrador_geral`** — dupla camada: bloqueio interno ("Acesso restrito") + exigência da chave `auditoria` em `pagina_restrita`. Usuário logado sem permissão que tenta abrir a rota gera `acesso_negado` em `tb_auditoria` (choke point único em `layout_tela.pagina_restrita`).
- **Filtros**: Módulo (`ui.select` **dinâmico** — módulos registrados em `tb_modulos` + produtores atuais da trilha), Ação (select com **categorias prontas** coloridas, com texto livre via `with_input`), Usuário (LIKE), Hora (`strftime('%H:%M')`), intervalo de datas (inicial/final).
- **Paginação server-side**: parâmetro `LIMIT ? OFFSET ?` (`auditoria_limite` como tamanho de página, default 1000) com contador e botões Anterior/Próxima; `auditoria_limite` ajusta o tamanho da página.
- **Campos/ordem por auditor**: painel "Campos e ordem de exibição" com checkbox/botões ↑/↓/ocultar e "Restaurar padrão"; persistido em `tb_config` na chave `auditoria_campos:<usuario>` (JSON com as chaves na ordem de exibição). Colunas coloridas na coluna `Ação` conforme `CORES_ACAO` (por tipo de ação).
- **Exportação CSV**: baixa o resultado filtrado da página corrente respeitando os **campos e a ordem** selecionados pelo auditor.
- **Colunas padrão**: Data/Hora, Usuário, Módulo, Ação, Descrição (truncada a 100 chars), Hash, IP e resumo do User-Agent via rótulo de dispositivo.

## Integrações com o núcleo

Importa `mod_intranet.conexao_bd.get_connection`/`get_config`/`set_config` e `mod_intranet.manipulador_bd.audit_log`. Os produtores da trilha são os outros módulos (via `audit_log`) e o próprio núcleo (login/logout/falhas/configurações/backups).

- **Índices** na `tb_auditoria` (`modulo`, `usuario`, `timestamp`) criados em `garantir_rastreabilidade()` (`mod_intranet/manipulador_bd.py`) — idempotente, via `CREATE INDEX IF NOT EXISTS`.
- **Poda automática**: job diário `poda_auditoria` (`mod_intranet/rotinas.py`) remove registros mais antigos que `auditoria_retencao_dias` (default 90) para conformidade LGPD.
- **Ações registradas**: as quatro telas de configuração que antes só logavam em arquivo agora também gravam `configuracao` na trilha central (Blog, Renomear Empenhos, Gestão de Usuários — inclui `usuarios_senha_min` — e Solicitação de Impressão); bloqueio/desbloqueio de usuário ganharam ações dedicadas (`bloquear_usuario`/`desbloquear_usuario`).
- Painel **Administração** (expansão, exclusivo do admin geral): `auditoria_limite` (LIMIT/tamanho de página), `auditoria_retencao_dias`, `auditoria_texto_header`. Salvar também **audita a si mesmo** (`auditoria`, `configuracao`). No rodapé, exibe `v{versao_sistema}` + `v{versao_modulo:auditoria}=1.0.260827` (seed em `conexao_bd.init_db()`).

## Pontos de atenção

- Consulta forense além de `auditoria_limite` numa página usa os botões de paginação; a exportação CSV cobre a página corrente (na ordem do auditor).
- Ações desconhecidas/novas ainda podem ser filtradas por texto livre no select de Ação.
- A preferência de colunas é por usuário (`auditoria_campos:<usuario>`); como o módulo é exclusivo do admin geral, na prática vale para qualquer auditor.

## Status — Fases 6/9 do PLANO.md

**Implementado:** leitura/filtro unificada da `tb_auditoria` central por data, **hora** (`strftime('%H:%M')`), usuário (LIKE), módulo e **categorias de ação**; colunas com IP e **rótulo de dispositivo**; **paginação server-side**; **exportação CSV**; **campos e ordem configuráveis por auditor**; cores por tipo de ação; módulo dinâmico; **auto-auditoria** das configs; **índices** na `tb_auditoria`; **poda diária** por `auditoria_retencao_dias`; acesso **exclusivo do `administrador_geral`** com registro de `acesso_negado` (backend + UI, RF-35) — **REALIZADO**.