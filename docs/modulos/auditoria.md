# Audit Module — `mod_auditoria`

> Audit module: route `/auditoria` (key `auditoria`) · EXCLUSIVE database `db_mod_auditoria.db` with ONE TABLE PER PRODUCER MODULE (`tb_auditoria_<modulo>`) · read-only viewer with dynamic table navigation, filters, server-side pagination, CSV export and per-auditor column selection/ordering.

---

# Módulo Auditoria — `mod_auditoria`

> Módulo de auditoria: rota `/auditoria` (chave `auditoria`) · **banco EXCLUSIVO** `db_mod_auditoria.db` com **UMA TABELA POR MÓDULO PRODUTOR** (`tb_auditoria_<modulo>`) · visualizador somente-leitura com navegação dinâmica por tabela, filtros, paginação server-side, exportação CSV e seleção/ordem de campos por auditor.

## Propósito

Banco e visualizador da trilha de auditoria LGPD. A **escrita** é feita pelos demais módulos via `audit_log` (núcleo) → `registrar_auditoria` (este módulo), que grava na tabela do módulo produtor — criada automaticamente. A **leitura** é feita pela tela `/auditoria` (exclusiva do `administrador_geral`).

## Banco de dados

Criador vigente: `init_db_auditoria()` em `manipulador_bd.py:25-38` (executado no import e pelo bootstrap central).

| Tabela | Conteúdo |
|:---|:---|
| `tb_auditoria_<modulo>` | UMA POR MÓDULO produtor: `usuario`, `modulo`, `acao`, `descricao`, `timestamp` (local — RF-08), `hash_arquivo`, `ip`, `user_agent`, `client_hostname`; índices por módulo/usuário/timestamp |
| `tb_auditoria_meta` | registro dos módulos produtores (`modulo` PK, `nome`, `criada_em`) |

- **Migração idempotente** do legado central (`migrar_dados_existentes`) + remoção da antiga `tb_auditoria` do banco central.
- **Poda LGPD** diária (`podar_registros`, `auditoria_retencao_dias` default 90 — job `poda_auditoria`).

## Funcionalidades

- **Acesso exclusivo `administrador_geral`** — dupla camada: bloqueio interno + exigência da chave `auditoria` em `pagina_restrita`. Sem permissão: `acesso_negado` na trilha (choke point único).
- **Navegação dinâmica por tabela**: select "Visualizar auditoria de" montado do banco ("Todas as auditorias" = UNION ALL, ou a tabela de um módulo).
- **Filtros**: Usuário (LIKE), Ação (categorias prontas coloridas + texto livre), Hora (`strftime('%H:%M')`), intervalo de datas (calendário em popup).
- **Paginação server-side**: `LIMIT ? OFFSET ?` (`auditoria_limite`, default 1000) com contador e Anterior/Próxima; auto-atualização a cada 30 s.
- **Campos/ordem por auditor**: painel com mover ↑/↓, ocultar, adicionar e "Restaurar padrão", persistido em `auditoria_campos:<usuario>` (JSON).
- **Exportação CSV**: página corrente respeitando campos/ordem do auditor.
- **Colunas padrão**: Data/Hora, Usuário, Módulo, Ação (cores por tipo — `CORES_ACAO`), Descrição (100 chars), Hash, IP, dispositivo.
- **Aba Observabilidade** (quando a stack OTel está no ar): atalhos para os dashboards Grafana (Visão Geral, Traces, Logs) + aviso LGPD sobre a senha do Grafana.
- **Painel Administração**: `auditoria_limite`, `auditoria_retencao_dias`, `auditoria_texto_header` + card padrão **"Configurações de cores"** (`auditoria_*` — vazios usam o padrão do PRÓPRIO módulo via `PADROES_TEMA["auditoria"]` = `#000000`, sem herança do tema do sistema); salvar audita a si mesmo. O cabeçalho usa `chave_modulo="auditoria"` (`telas.py:345`): a borda de destaque é a **mesma cor dos botões do módulo**.
- **Versionamento**: `versao_modulo:auditoria = 1.0.260908`.

## Permissões

| Ação | `comum` | `administrador_modulo` | `administrador_geral` |
|:---|:---:|:---:|:---:|
| Acessar `/auditoria` | ✗ | ✗ | ✓ |
| Exportar CSV | ✗ | ✗ | ✓ |

## Rota e integrações

- Rota: `/auditoria` (chave `auditoria`) — `main.py:325`.
- **Escrita**: `audit_log` (núcleo) → `registrar_auditoria` — produtores: todos os módulos + o núcleo (login/logout/falhas/config/backups).
- **Leitura**: `buscar_logs`/`get_modulos_com_auditoria`/`contar_registros` (usado pelo resumo do dashboard).
- **Poda**: job diário `poda_auditoria` (`mod_intranet/rotinas.py:74-103`).

## Testes

```bash
.venv/bin/python test/test_auditoria.py
```

## Pontos de atenção

- Exportação cobre a **página corrente** (não a consulta inteira).
- Ações novas/desconhecidas podem ser filtradas por texto livre no select de Ação.
- `db_criador.py` é legado — o esquema real vive em `db_manipulador.py`.

Ver [Análise do Módulo](../analise_mod_auditoria.md).
