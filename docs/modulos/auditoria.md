# Audit Module — `mod_auditoria`

> Audit viewer module: route `/auditoria` (key `auditoria`) · no own database — reads unified `tb_auditoria` from central `db_mod_intranet.db` · read-only, filters by user/module/action/date, IP and device summary, server-side pagination, CSV export and per-auditor column selection/ordering.

---

# Módulo Auditoria — `mod_auditoria`

> Módulo visualizador de auditoria: rota `/auditoria` (chave `auditoria`) · **sem banco próprio** — lê `tb_auditoria` unificada do central `db_mod_intranet.db` · somente-leitura, filtros por usuário/módulo/ação/data/hora, IP e rótulo de dispositivo, paginação server-side, exportação CSV e seleção/ordem de campos por auditor.

## Propósito

Visualizador somente-leitura da trilha de auditoria LGPD unificada gravada pelos demais módulos via `audit_log`. Permite filtrar e inspecionar registros (data/hora, usuário, módulo, ação, descrição, IP, rótulo de dispositivo). Não escreve em nenhuma tabela (as preferências e configs vão para `tb_config` central).

## Estrutura do pacote

Contém apenas `telas.py` (com `__init__.py` vazio) e `check_auditoria.py` (script diagnóstico). **Não há `manipulador_bd`**: o único ponto de entrada é `mostrar_tela(usuario_logado, perfil)` (`telas.py:83`) e a leitura usa `get_connection()` do núcleo.

## Funcionalidades

- **Acesso exclusivo `administrador_geral`** — dupla camada: bloqueio interno + exigência da chave `auditoria` em `pagina_restrita`. Sem permissão: `acesso_negado` na trilha (choke point único).
- **Filtros**: Módulo (`ui.select` dinâmico — `tb_modulos` + produtores atuais), Ação (categorias prontas coloridas + texto livre), Usuário (LIKE), Hora (`strftime('%H:%M')`), intervalo de datas.
- **Paginação server-side**: `LIMIT ? OFFSET ?` (`auditoria_limite`, default 1000) com contador e Anterior/Próxima.
- **Campos/ordem por auditor**: painel com checkbox/↑/↓/ocultar e "Restaurar padrão", persistido em `auditoria_campos:<usuario>` (JSON).
- **Exportação CSV**: página corrente respeitando campos/ordem do auditor.
- **Colunas padrão**: Data/Hora, Usuário, Módulo, Ação (cores por tipo), Descrição (100 chars), Hash, IP, dispositivo.
- **Painel Administração**: `auditoria_limite`, `auditoria_retencao_dias`, `auditoria_texto_header`; salvar audita a si mesmo.
- **Versionamento**: `versao_modulo:auditoria = 1.0.260827`.

## Permissões

| Ação | `comum` | `administrador_modulo` | `administrador_geral` |
|:---|:---:|:---:|:---:|
| Acessar `/auditoria` | ✗ | ✗ | ✓ |
| Exportar CSV | ✗ | ✗ | ✓ |

## Rota e integrações

- Rota: `/auditoria` (chave `auditoria`) — `main.py:208`.
- Produtores da trilha: todos os módulos via `audit_log` + o núcleo (login/logout/falhas/config/backups).
- Índices (`modulo`, `usuario`, `timestamp`) criados por `garantir_rastreabilidade()`; **poda diária** de registros > `auditoria_retencao_dias` (default 90) — LGPD.

## Testes

```bash
.venv/bin/python test/test_auditoria.py
```

## Pontos de atenção

- Exportação cobre a **página corrente** (não a consulta inteira).
- Ações novas/desconhecidas podem ser filtradas por texto livre no select de Ação.

Ver [Análise do Módulo](../analise_mod_auditoria.md).