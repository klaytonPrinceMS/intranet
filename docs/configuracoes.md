# Intranet Modular — Configuration and Environment

> Configuration guide: the `storage_secret` placeholder (must be replaced in production), the `8080` port, the `db_mod_*` database paths, and the parameters of `main.py` and `inicializar_bancos()`. There are no `.env` variables — all settings live in the central `tb_config` table, seedable by `PADRAO_CONFIG`.

---

# Intranet Modular — Configurações e Variáveis de Ambiente

> Guia de configuração: o placeholder `storage_secret` (deve ser trocado em produção), a porta `8080`, os caminhos dos bancos `db_mod_*` e os parâmetros do `main.py` e de `inicializar_bancos()`. Não existem variáveis `.env` — as configurações vivem na tabela central `tb_config`, semeada por `PADRAO_CONFIG`.

## Sumário

1. [Visão geral](#visao-geral)
2. [`storage_secret` (curinga do NiceGUI)](#storage_secret-curinga-do-nicegui)
3. [Porta e execução](#porta-e-execucao)
4. [Caminhos de banco de dados](#caminhos-de-banco-de-dados)
5. [Parâmetros do `main.py`](#parametros-do-mainpy)
6. [Bootstrap: `inicializar_bancos()`](#bootstrap-inicializar_bancos)
7. [Chaves de configuração (`tb_config`)](#chaves-de-configuracao-tb_config)
8. [Sem variáveis de ambiente `.env`](#sem-variaveis-de-ambiente-env)

## Visão geral

A aplicação não usa arquivo `.env` nem variáveis de ambiente: a configuração é **persistida no banco central** `db_mod_intranet.db` (tabela `tb_config`, chave/valor) e lida via `get_config(chave, default)` / `set_config(chave, valor)` (`mod_intranet/bd_conexao.py:103-123`). As únicas "constantes de execução" estão hardcoded no `main.py`.

## `storage_secret` (curinga do NiceGUI)

Em `main.py:471-478`:

```python
ui.run(
    title=...,
    favicon="assets/favicon_atual.ico",
    storage_secret="intranet-secret-2026-mude-isto",  # ← placeholder
    reload=False,
    port=8080,
    show=False,
)
```

> ⚠️ **Obrigatório trocar antes de produção.** `storage_secret` é a chave usada pelo NiceGUI para assinar os dados de sessão em `app.storage.user`. O valor atual é um placeholder hardcoded. Troque por uma string longa e aleatória (ex.: gerada com `secrets.token_hex(32)`).

## Porta e execução

| Parâmetro | Valor atual | Local |
|:---|:---|:---|
| `port` | `8080` | `main.py:476` |
| `reload` | `False` | `main.py:475` |
| `show` | `False` | `main.py:477` |
| `favicon` | `assets/favicon_atual.ico` (arquivo vivo) | `main.py:473` |
| `title` | lido de `tb_config` (`texto_login_titulo`) | `main.py:472` |

## Caminhos de banco de dados

Os bancos são criados na **raiz do projeto** (mesma pasta do `main.py`):

| Banco | Módulo | Onde é declarado |
|:---|:---|:---|
| `db_mod_intranet.db` | núcleo (auditoria, config, sessões, módulos) | `mod_intranet/bd_conexao.py:11` |
| `db_mod_gest_cad_usuario.db` | gestão de usuários | `../mod_gest_cad_usuario/bd_manipulador.py` |
| `db_mod_blog.db` | blog | `mod_blog/bd_manipulador.py:41-45` |
| `db_mod_edit_pdf.db` | editor de PDF | `mod_edit_pdf/bd_manipulador.py:23` |
| `db_mod_renomear_empenho.db` | renomear empenho | `mod_renomear_empenho/bd_manipulador.py:20` |
| `db_mod_solicita_impressao.db` | solicitação de impressão | `mod_solicita_impressao/bd_manipulador.py:25` |

Todos operam em **modo WAL** (`PRAGMA journal_mode=WAL`), gerando arquivos `*.db-wal` e `*.db-shm` ao lado do `.db`.

## Parâmetros do `main.py`

| Item | Descrição | Local |
|:---|:---|:---|
| `sys.path.insert` | garante que a raiz esteja no path (imports `mod_*`) | `main.py:5` |
| `inicializar_bancos()` | cria todos os `db_mod_*` no boot **antes** de qualquer import de módulo | `main.py:17-18` |
| Telemetria OTel | auto-start da stack (Docker) ou servidor dedicado; instrumenta a app; sync Grafana | `main.py:20-60` |
| Verificação de `telas.py` | aborta com `RuntimeError` se algum `mod_*` não tiver `telas.py` | `main.py:65-67` |
| Favicon customizado | copia o favicon nativo para `assets/favicon_atual.ico` se ausente | `main.py:103-112` |
| `iniciar_agendador()` | delega ao `rotinas.iniciar_agendador()` (jobs de backup, cleanup, monitor, poda) | `main.py:71-75` e `461` |
| CSS frameworks embarcados | `tema_css.montar_rotas_static()` — serve `assets/css/frameworks/` em `/css/frameworks/*` (sem CDN), com fallback silencioso | `main.py:81-85` |
| Rotas dinâmicas | `rotas_modulos.montar_rotas_ativas()` re-registra slugs customizados de `tb_modulos` | `main.py:452-453` |
| Observabilidade | `observabilidade.configurar()` + `instalar_excepthook()` antes do `ui.run` | `main.py:457-459` |
| Documentação | `construir_e_montar_documentacao()` — build MkDocs + mount em `/documentacao` | `main.py:468-469` |
| `ui.run(...)` | sobe o NiceGUI (parâmetros da tabela acima) | `main.py:471-478` |

## Bootstrap: `inicializar_bancos()`

Definida em `mod_intranet/mod_intranet_inicializacao_bd.py:13-46`. Ordem **crítica** (o central SEMPRE primeiro):

1. `init_central()` — cria `tb_config`, `tb_sessoes` (+ seeds) no `db_mod_intranet.db` (a antiga `tb_auditoria` central não é mais criada — a trilha vive no banco exclusivo de auditoria).
2. `garantir_rastreabilidade()` — migração de colunas LGPD de `tb_sessoes` (`ip`, `user_agent`, `dispositivo`, `mac`) + seed `sessao_retencao`.
3. `init_db_auditoria()` + `migrar_dados_existentes()` — banco exclusivo `db_mod_auditoria.db` (tabela por módulo) e migração única do legado central.
4. `init_blog()` → `db_mod_blog.db`.
5. `init_users()` → `db_mod_gest_cad_usuario.db` + seed `master`/`master`.
6. `init_db_pdf()` → `db_mod_edit_pdf.db`.
7. `init_db_empenho()` → `db_mod_renomear_empenho.db`.
8. `init_solicita()` → `db_mod_solicita_impressao.db`.

O processo é **idempotente** (nunca apaga dados) e pode ser rodado novamente para aplicar seeds sem reiniciar nada.

## Chaves de configuração (`tb_config`)

As principais chaves, agrupadas por dono:

| Grupo | Chave | Default | Descrição |
|:---|:---|:---|:---|
| Sistema | `versao_sistema` | `1.0.260908` | versão global exibida no rodapé |
| Sistema | `cotadisco_global_gb` | `10` | cota global do editor PDF (GB) |
| Sistema (legada) | `backup_interval_hours` | `12` | semente legada; os jobs usam `backup_horas:<modulo>` |
| Sistema | `sessao_retencao` | `50` | histórico de sessões retido por usuário |
| Aparência | `titulo_sistema`, `icone_sistema`, `cor_principal` (`#000000`), `cor_fundo` (`#EEEEEE`) | `PADRAO_CONFIG` | personalização global |
| Botões do sistema (intranet) | `intranet_cor_botao` (`#000000`), `intranet_cor_texto_botao` (`#FFFFFF`), `intranet_btn_tamanho` (`medium`), `intranet_cor_titulo` (`#212121`) | `PADRAO_CONFIG` | **"Cor geral do módulo"** (`intranet_cor_botao`): mesma cor/tamanho em TODOS os botões do módulo (login, painel, config, diálogos) **e nos menus/destaques** (`ui.colors(primary=...)`); prévia ao vivo; APLICAR recarrega. **Vale apenas para o próprio módulo `intranet`** — os demais módulos usam o padrão do PRÓPRIO módulo (`PADROES_TEMA`), sem herança (ver seção abaixo) |
| Cards do sistema (intranet) | `intranet_cor_fundo_card` (`#FFFFFF`), `intranet_cor_texto_card` (vazio = herda) | `PADRAO_CONFIG` | fundo + texto base de todos os cards do módulo (login, config, diálogos, painel) |
| Textos | `texto_login_titulo`, `texto_login_subtitulo`, `texto_login_hint`, `texto_home_saudacao`, `texto_home_subtitulo`, `texto_rodape` | `PADRAO_CONFIG` | textos fixos |
| Versão por módulo | `versao_modulo:<chave>` | seeds em `bd_conexao.py:70-79` | versão individual no rodapé |
| Backup | `backup_horas:<modulo>` | `12` | intervalo em horas por módulo (mín. 1 h) |
| Editor PDF | `editpdf_lote_arquivos`, `editpdf_lote_mb`, `editpdf_usuario_gb`, `editpdf_expiracao_min` | — | cotas/limites/expiração |
| Editor PDF (tema) | `editpdf_cor_botao`, `editpdf_cor_texto_botao`, `editpdf_cor_fundo`, `editpdf_cor_titulo`, `editpdf_btn_tamanho` | — | aparência da tela |
| Blog | `blog_modo_exibicao`, `blog_largura_imagem`, `blog_tags_permitidas`, `blog_texto_header` + tema `blog_*` | — | comportamento/aparência |
| Usuários | `usuarios_senha_min`, tema `usuarios_*` | `6` | política de senha mínima |
| Auditoria | `auditoria_limite` (1000), `auditoria_retencao_dias` (90), `auditoria_texto_header`, `auditoria_campos:<usuario>` (JSON) | — | paginação/retirada/campos |
| Empenhos | `empenhos_pastas_monitoradas` (multi-pasta, uma por linha — local/UNC), `empenhos_pasta_monitorada` (legado, fallback de 1 pasta), `empenhos_monitor_intervalo_seg` (60), `empenhos_template_nome`, `empenhos_organizador_paginas_pasta` (200), `empenhos_organizador_pastas_caixa` (4), `renomear_autorizar_download` (0), `empenhos_texto_header`, tema `empenhos_*` | — | monitor/aparência/organizador |
| Impressão | variáveis de tempo e padrões na aba Administração → Configurações do módulo | — | ver [Módulo de Solicitação de Impressão](modulos/solicitacao_impressao.md) |
| E-mail/SMTP | `smtp_*` | — | credenciais (aba "E-mail" de Configurações) |
| Logs | `log_ativo`, `log_nivel`, `log_rotacao` (`1 month`), `log_retencao` (`4 months`), `log_console` (`auto`), `log_otel_envio` (`1`), `log_otel_nivel` (`DEBUG`) | — | observabilidade loguru (console e envio ao Loki configuráveis) |
| Telemetria OTel | `otel_ativo` (`1`), `otel_endpoint` (`localhost:4317`, env `OTEL_ENDPOINT` tem prioridade), `otel_auto_start_stack` (`1`) | — | stack local (Docker) ou servidor dedicado; troca exige restart |
| Grafana | `grafana_url` (`http://localhost:3000`, env `GRAFANA_URL` tem prioridade) | — | URL base do Grafana (health-check/API/status) |
| Avisos | `notificacao_timeout` (`10`, 1–30 s) | — | tempo de exibição dos toasts via `tema_modulo.notificar()` |
| Hora do servidor | `hora_ntp_ativa` (`1`) | — | sincronização NTP.br da hora do servidor (`mod_intranet/hora_servidor.py`): `1` = ativa (default), `0` = usa o relógio local; aplicada sem restart |
| Banco | `banco_tipo` (`sqlite`), `postgres_url` (`postgresql+psycopg2://intranet:intranet@localhost:5432/intranet`) | `PADRAO_CONFIG` (`bd_conexao.py:40-41`) | seleção do SGBD: `sqlite` (padrão, zero dependências extras) ou `postgres` (backend duplo via `banco_conexao` — conexão DBAPI por módulo, um SCHEMA por módulo no banco `intranet`); lidos no boot via `banco_conexao._ler_config_sqlite`; troca exige **reiniciar o servidor** — ver [Card "Banco de dados" (SQLite ou PostgreSQL)](#card-banco-de-dados-sqlite-ou-postgresql-0809) |

> Os padrões de aparência vivem em `PADRAO_CONFIG` (`mod_intranet/bd_conexao.py:13-24`) e são restaurados via tela de configurações (abas com "Restaurar padrão" por cartão).

### Menu "Administração" (06/09)

A tela `/configuracoes` é aberta pelo item **"Administração"** do menu lateral (antes "Configurações"), com ícone unificado `admin_panel_settings` (`layout_tela.py:184-191`) e guarda `pagina_restrita("Administração")` (`main.py:442`) — exclusivo do `administrador_geral`. O drawer **não exibe mais labels de seção** ("PÁGINA INICIAL"/"MÓDULOS"/"SISTEMA" foram removidos; restam apenas separadores entre os grupos de itens). No header das páginas de módulo, o tooltip do botão de backup passou a **"Administração do módulo (backup e agendamento)"** (`layout_tela.py:145`), alinhando a nomenclatura: toda área de gestão — central ou do módulo — chama-se **Administração**.

### Card "Banco de dados" (SQLite ou PostgreSQL) (08/09)

O padrão permanece **SQLite** (atende servidores simples, zero dependências extras — todos os módulos operam via `CrudBase`/`sqlite3`). Para demandas maiores, o **PostgreSQL é opcional e configurável pelo admin** em `/configuracoes` → aba **Documentação** → card **"Banco de dados — SQLite ou PostgreSQL"** (ícone `storage`, `tela_configuracoes.py:1226-1259`), sem tocar em código:

| Item | Detalhe |
|:---|:---|
| Card | `ui_comum.card_admin("Banco de dados — SQLite ou PostgreSQL", icone="storage")` (`tela_configuracoes.py:1227`) |
| Select `banco_tipo` | `sqlite` (padrão) \| `postgres` — lido de `config_backend()` (`banco_conexao.py:115`) |
| Campo `postgres_url` | DSN do Postgres (default do container: `postgresql+psycopg2://intranet:intranet@localhost:5432/intranet`) |
| Salvar | `banco_conexao.salvar_backend(banco_tipo, postgres_url)` grava no arquivo SQLite central |
| Aviso | **"Banco de dados atualizado — REINICIE o servidor para aplicar (as conexões ativas seguem no backend anterior)"** — a troca exige restart (o backend é resolvido no boot) |
| Auditoria | `aplicar_banco` audita `config_banco` via `_aplicar_card("Banco de dados", ...)` (`tela_configuracoes.py:1259`) |

**Backend duplo controlado pelo sistema** (`mod_intranet/banco_conexao.py`):

- `banco_tipo` em `tb_config` central (`'sqlite'` padrão | `'postgres'`): lido **DIRETO do arquivo SQLite central** (`_ler_config_sqlite`, `banco_conexao.py:57`) — seletor de backend autoritativo no boot, sem recursão.
- `postgres_url` (DSN) também no arquivo SQLite central; credenciais da URL usadas como estão (container `intranet/intranet`).
- Postgres: **um SCHEMA por módulo** dentro do banco `intranet` (`SCHEMAS`, `banco_conexao.py:248`) — `intranet`, `blog`, `usuarios`, `auditoria`, `editar_pdf`, `empenhos`, `solicita_impressao` — `search_path` setado por conexão (schema criado via `CREATE SCHEMA IF NOT EXISTS` no connect, com commit para sobreviver ao rollback do pool). Isso preserva o isolamento "um banco por módulo" e evita colisões de nome de tabela (ex.: `tb_solicitacoes`).
- `conexao(chave)` devolve uma conexão DBAPI para o backend ativo: sqlite (arquivo do módulo, WAL) ou postgres (proxy psycopg2 com tradução `?`→`%s`, DDL SQLite→Postgres, `INSERT OR IGNORE`→`ON CONFLICT DO NOTHING`, `PRAGMA`/FTS5 ignorados, `lastrowid` via `RETURNING id` com SAVEPOINT, SAVEPOINT por statement). Detalhes em [Arquitetura — Backend duplo](arquitetura.md#arquitetura-de-acesso-a-dados-do-nucleo-backend-duplo-0809).
- `repositorio.engine(chave)`/`sessaodb(chave)` roteiam para o Postgres quando `banco_tipo='postgres'` (senão mantêm SQLite por arquivo).
- Fail-soft: sem `sqlalchemy`/driver instalado, registra exception no loguru e a aplicação **segue de pé em SQLite**.
- Segurança: o DSN nunca é logado com credenciais — `_dsn_publico()` (`banco_conexao.py:40`) mascara usuário/senha (`postgresql+psycopg2://***@host/db`).

**Container Postgres opcional** (`assets/docker/postgres/docker-compose.yml`):

| Item | Detalhe |
|:---|:---|
| Imagem | `postgres:16-alpine` |
| Banco | `intranet` (via env `POSTGRES_DB`) |
| Credenciais | `intranet`/`intranet` (via env `POSTGRES_USER`/`POSTGRES_PASSWORD`) |
| Porta | `5432:5432` |
| Volume | `intranet_pgdata` (persistente) |
| Healthcheck | `pg_isready` |
| Aviso | **apenas dev/staging** — não exponha a porta `5432` em produção |

> **Nota (08/09):** o suporte ao PostgreSQL está **ativo** — não é mais fase futura. Os módulos migrados para a camada única (`banco_conexao.conexao(chave)`) operam no backend selecionado: `mod_intranet/bd_conexao.get_connection`, `mod_auditoria`, `mod_edit_pdf`, `mod_gest_cad_usuario`, `mod_renomear_empenho`, `mod_solicita_impressao`; `CrudBase._conectar` também roteia pelo backend ativo (módulo em `SCHEMAS`). A **migração de dados** SQLite→PostgreSQL permanece manual — os bancos SQLite existentes não são movidos automaticamente (o Postgres inicia com os schemas vazios, recriados pelos `init_db` dos módulos).

### Card "Cores" — ordem interna e prévia ao vivo (06/09)

O primeiro card da aba **Config** (`tela_configuracoes.py:433-582`) concentra as chaves de aparência global da tabela acima (`cor_principal`, `cor_fundo` e as `intranet_*` de botões/cards). Ordem de renderização:

| # | Bloco | Local |
|:--|:---|:---|
| 1 | Título "Cores" (`_titulo_cartao`) | `tela_configuracoes.py:434` |
| 2 | Legenda explicativa | `tela_configuracoes.py:435-438` |
| 3 | **Pré-visualização ao vivo** — barra do sistema (ícone + nome sobre a cor principal), card de exemplo (fundo/texto/título) e botões de exemplo (sólido + contorno) | `tela_configuracoes.py:440-489` |
| 4 | Campos de cores — grid responsivo com os 8 seletores (4+4 no desktop) | `tela_configuracoes.py:491-532` |
| 5 | "Restaurar padrão" (com confirmação) | `tela_configuracoes.py:546-582` |

!!! note "Prévia no topo do card (06/09)"
    A pré-visualização subiu do rodapé do card para logo abaixo da legenda: bloco de 50 linhas movido **verbatim** (antes `tela_configuracoes.py:491-540`, depois `:440-489`, antes do grid `:491`). A renderização inicial é idêntica — a prévia (`previa()`, `@ui.refreshable`) lê o estado pendente do campo com fallback ao banco (`_prev`, `tela_configuracoes.py:245-255`) e `_refresh_previa()` (`:235-243`) é independente da ordem: silenciosa se a prévia ainda não foi renderizada e acionada pelos callbacks `_mudou`/`_mudou_cor` de qualquer campo (`:223-233`), antes ou depois dela. Grid de seletores, seeds e botão "Restaurar padrão" byte-idênticos; card "Ícones" intocado. Coberto por `test/verifica_ui_comum.py` (187 verificações OK) e `test/teste_config_intranet.py` (50 OK).

### Aplicar por card — sem botão "APLICAR" geral (06/09)

O painel `/configuracoes` **não tem mais o botão "APLICAR" geral** na barra de abas. `salvar_tudo()` foi substituído por funções de Aplicar **POR CARD** (`tela_configuracoes.py:263-473`):

| Função | Card | Local |
|:---|:---|:---|
| `aplicar_cores` | Configurações de cores | `tela_configuracoes.py:310-340` |
| `aplicar_textos` | Textos fixos exibidos aos usuários | `tela_configuracoes.py:342-349` |
| `aplicar_gerais` | Configurações gerais do sistema | `tela_configuracoes.py:351-368` |
| `aplicar_icones` | Ícones | `tela_configuracoes.py:370-374` |
| `aplicar_smtp` | E-mail / SMTP | `tela_configuracoes.py:376-380` |
| `aplicar_obs` | Observabilidade e logs (loguru) | `tela_configuracoes.py:382-402` |
| `aplicar_otel` | Telemetria OTel | `tela_configuracoes.py:404-410` |
| `aplicar_paginas` | Páginas do sistema | `tela_configuracoes.py:412-452` |
| `aplicar_banco` | Banco de dados (SQLite ou PostgreSQL) — aba Documentação | `tela_configuracoes.py:1246-1257` |

Helpers do padrão:

- **`_v(chave_estado, chave_config, padrao)`** (`:263-275`): valor do campo que **nunca zera** — campo fora do estado mantém o valor vigente no banco (limpeza intencional continua possível).
- **`_reload_apos()`** (`:277-282`): recarrega a página após **1 segundo** — padrão do botão "Aplicar" de cada card.
- **`_aplicar_card(rotulo, audit_desc, salvar_fn, msg, extra_msg)`** (`:284-308`): grava EXCLUSIVAMENTE os campos do card (`salvar_fn`), audita `config_alterada`, notifica e recarrega após 1 s; falha registra loguru (`observabilidade.get_logger("intranet")`) e notifica negativo **sem recarregar**.
- **`_aplicar_paginas()`** (`:454-473`): wrapper do card "Páginas do sistema" — chama `aplicar_paginas()`, notifica com avisos de URL não alterada e recarrega.

Cada card é `card_admin` recolhível (`aberto=False`) com o rodapé padrão de 2 botões — **"Restaurar padrão" + "Aplicar"** — exclusivos do card (`rodape_salvar_restaurar`, `ui_comum.py:338`; rótulo padrão do salvar agora é **"Aplicar"**). O card "Cores" foi renomeado para **"Configurações de cores"** (`tela_configuracoes.py:492`) e o card de Observabilidade foi dividido em **"Observabilidade e logs (loguru)"** (`:988`) + **"Telemetria OTel — stack local ou servidor dedicado"** (`:1110`).

### Fallback de entrada numérica nos Gerais (06/09)

Os três campos numéricos do card **"Configurações gerais do sistema"** (aba Config) são saneados em `aplicar_gerais()` (`tela_configuracoes.py:351-368`) com `try/except (TypeError, ValueError)`:

| Campo | Chave | Entrada inválida ("abc") grava | Faixa |
|:---|:---|:---:|:---|
| Intervalo de backup (horas) | `backup_interval_hours` | `12` | mín. 1 |
| Retenção de sessão (dias) | `sessao_retencao` | `50` | mín. 1 |
| Tempo de exibição dos avisos (segundos) | `notificacao_timeout` | `10` | 1–30 |

!!! note "APLICAR nunca mais aborta por entrada inválida"
    Antes, um `ValueError` (ex.: `"abc"` no intervalo de backup) derrubava o APLICAR no meio — sem toast nem recarregamento, com salvamento parcial. Agora o valor inválido cai no **padrão codificado** (mesmo contrato já aplicado ao `aviso_timeout`) e o salvamento segue até o fim. Coberto por `test/teste_aba_config_intranet.py` (seção "VALIDAÇÕES").

### Tempo de exibição dos avisos — padrão 10 s (06/09)

O padrão do `notificacao_timeout` mudou de **2 s para 10 s** — os toasts ficam visíveis por mais tempo por padrão, sem perder a configurabilidade (1–30 s, campo "Tempo de exibição dos avisos (segundos)" do card **Gerais**):

| Ponto | Local |
|:---|:---|
| Seed em `PADRAO_CONFIG` | `mod_intranet/bd_conexao.py:67` |
| Helper `notificacao_timeout()` — default/fallback 10, clamp 1–30 | `mod_intranet/tema_modulo.py:234-243` |
| Campo do card Gerais (`padrao="10"`) | `mod_intranet/tela_configuracoes.py:713` |
| Fallback do APLICAR do card Gerais (`aplicar_gerais`) | `mod_intranet/tela_configuracoes.py:353-367` |
| "Restaurar padrão" do card Gerais grava `10` | `mod_intranet/tela_configuracoes.py:740,747` |
| Testes atualizados | `test/teste_config_intranet.py` (50 OK), `test/teste_aba_config_intranet.py` (164 OK) |

!!! note "Instalações existentes"
    O novo padrão vale para instalações novas e para o botão "Restaurar padrão". Instalações que já gravaram `notificacao_timeout` na `tb_config` central mantêm o valor atual — o admin pode ajustar em `/configuracoes` → Gerais (1–30 s), aplicado sem restart.

### Padrão próprio do tema do módulo — "Cor geral do módulo" (06/09)

As chaves de tema de **botão** dos módulos (`<prefixo>_cor_botao`, `<prefixo>_cor_texto_botao`, `<prefixo>_btn_tamanho`, lidas por `tema_modulo.ler_tema` — `mod_intranet/tema_modulo.py:94-126`) seguem precedência:

1. **Chave do módulo não vazia** (ex.: `usuarios_cor_botao`, gravada no cupê "Aparência" da Administração do módulo);
2. **Default do parâmetro** em `ler_tema` — quando o chamador informa (ex.: `ler_tema("editar_pdf", cor_botao="#000000")`);
3. **Padrão do módulo** — mapa `PADROES_TEMA` (`tema_modulo.py:53-68`), usado quando o chamador não passa default explícito.

O tema do sistema (`intranet_*` / card **"Botões do sistema"** do painel central `/configuracoes`) **NÃO é herdado** por outros módulos: **todos os módulos usam a cor do intranet (`#000000`)** por padrão, configuráveis no cupê "Aparência".

| Campo | Herda do sistema? | Comportamento com a chave vazia |
|:---|:---:|:---|
| `cor_botao` (**"Cor geral do módulo"**) | ✗ | padrão do módulo (`PADROES_TEMA` — **todos os módulos em `#000000`**, a cor do intranet) |
| `cor_texto_botao` (**"Cor do texto do módulo"**) | ✗ | `#FFFFFF` (padrão do módulo) |
| `btn_tamanho` | ✗ | `medium` (padrão do módulo) |
| `cor_fundo` | ✗ | fundo padrão da tela (default do parâmetro) |
| `cor_titulo` | ✗ | `#212121` (padrão do módulo) |
| `texto_header` | ✗ | default do parâmetro |

!!! note "Efeito prático"
    **Todos os módulos usam a cor do intranet (`#000000`)** por padrão (`PADROES_TEMA`), sem depender do tema do sistema — `PADRAO_CONFIG` não semeia chaves de botão por módulo e instalações novas já iniciam com a cor única `#000000`. O override por módulo continua disponível no cupê "Aparência" de cada módulo: os inputs exibem o valor **resolvido** (rótulo "vazio = padrão do módulo") e o "Restaurar padrão" grava `""` para voltar ao padrão do módulo. O card "Botões do sistema" (`intranet_*`) vale apenas para o próprio módulo `intranet` (`tema_modulo.py:94-126`).

!!! note "Rótulo renomeado: 'Cor geral do módulo' (06/09)"
    A chave `<prefixo>_cor_botao` agora é chamada de **"Cor geral do módulo"** (antes "Cor dos botões") e `cor_texto_botao` de **"Cor do texto do módulo"** (antes "Cor do texto dos botões") — rótulos renomeados em TODOS os painéis: cupê "Aparência" (`tema_modulo.bloco_aparencia` — `tema_modulo.py:318-323`), aba Cores do sistema (`tela_configuracoes.py:517-526`), admins de blog (`mod_blog/telas_administracao.py:56`), auditoria (`mod_auditoria/telas_administracao.py:111`) e empenhos (`mod_renomear_empenho/telas_administracao.py:99` + `telas.py:699`). O nome reflete o novo escopo: a cor define os **botões E os menus/abas/destaques** da tela do módulo — `ui.colors(primary=cor_botao)` (menus/Quasar) + `cabecalho(chave_modulo=...)` (borda de destaque) + `ui_comum.botao(chave_modulo=...)` (botões). `ui.colors(primary=...)` passou a ser aplicado em TODAS as telas (antes só blog e gest_cad): auditoria (`mod_auditoria/telas.py:126`), edit_pdf (`mod_edit_pdf/telas.py:89`), empenhos (`mod_renomear_empenho/telas.py:65`) e solicita_impressao (`mod_solicita_impressao/telas.py:53`). Nas rotas de admin (`main.py:484-523`) os hexes fixos viraram `ler_tema(<modulo>, cor_botao=<default>)["cor_botao"]`; empenhos usa `empenhos_cor_botao` com default alinhado a `#000000` (antes `#6D4C41`). `ui.color_input`/`ui.select` crus do admin de auditoria e empenhos migraram para as fábricas `campo_cor`/`campo_selecao`. Coberto por `test/teste_aba_config_intranet.py` (164 verificações — novos rótulos).

!!! tip "Botões 100% na fábrica + 'Restaurar padrão' com aparência única (06/09)"
    Com a migração de ~120 botões crus em 12 arquivos (auditoria, edit_pdf, gest_cad_usuario, renomear_empenho e solicita_impressao — telas+admin), a cor/tamanho configurados aqui (ou no cupê "Aparência" do módulo) aplicam em **TODOS os botões do módulo** — a fábrica `ui_comum.botao/botao_icone(chave_modulo=...)` lê o tema a cada render. O rodapé `rodape_salvar_restaurar` (`ui_comum.py:338`) também usa a fábrica: "Restaurar padrão" tem aparência ÚNICA no projeto (contorno âmbar, `text-color=amber-10`, contraste WCAG ~3,8:1 em card branco) e "Salvar" usa o `solido` do tema. Exceções intencionais de `ui.button` cru: a própria fábrica (`ui_comum.py:163`), o "Cancelar" de `rodape_dialogo` (`ui_comum.py:326`) e o preview ao vivo da aba Cores (`tela_configuracoes.py:493,497` — usa valores não salvos dos campos).

### Aba "Módulo" — Páginas do sistema

Na aba **Módulo → Páginas do sistema** (renomeada de "Registro/Nome de módulo" em 05/09 — `tela_configuracoes.py:165`) o administrador edita o **nome exibido** (menu lateral e título do cabeçalho), o **ícone** (Material Icons) e a **ORDEM** de cada página usando as setas ↑/↓ (a ordem é salva imediatamente). Desde 05/09:

- **Reordenação com ↑/↓** — a lista de páginas é **ÚNICA** (substituiu os grupos separados "Indispensáveis"/"Demais") e todos os módulos são reordenáveis: `refresh_modulos()` (`tela_configuracoes.py:566-636`) remonta a lista na ordem vigente de `tb_modulos.ordem` e `_mover(idx, direcao)` (`tela_configuracoes.py:638-669`) troca o vizinho, persiste de imediato via `autenticacao.reordenar_modulos` e preserva edições pendentes (nome/ícone/ativo) entre remontagens. A 1ª coluna do grid (56px) exibe a posição e os botões ↑/↓.
- **Campo de ícone editável com seletor visual** — `_campo_icone` (`tela_configuracoes.py:519-546`): input livre do nome do Material Icon + **pré-visualização viva** (o ícone é atualizado em tempo real na linha) + **seletor visual** (`ui.menu` com grid de 6 colunas sobre `ICONES_COMUNS` — 31 ícones, `tela_configuracoes.py:33-39`) + botão `grid_view`. Reutilizado no campo "Ícone Material" do registro de novo módulo (`tela_configuracoes.py:762`).
- **Alinhamento corrigido** — constante compartilhada `COLUNAS_MODULOS` (`tela_configuracoes.py:45`) entre cabeçalho e linhas (mesmo columns/gap/padding; antes o cabeçalho não tinha gap).
- **Indispensáveis destacados, porém reordenáveis** (`tela_configuracoes.py:1217-1421`): `auditoria` e `usuarios` (`MODULOS_INDISPENSAVEIS` — `tela_configuracoes.py:30` e `autenticacao.py:216`) aparecem com fundo âmbar + cadeado e **não podem ser desativados**: a tentativa é recusada no backend (`set_modulo_ativo` retorna `(False, msg)` e audita `modulo_desativado_bloqueado` — `autenticacao.py:227-229`); `set_chaves_desativadas` também os filtra (`autenticacao.py:481`); `aplicar_paginas` força `ativo=1` (`tela_configuracoes.py:420`). O switch fica oculto/disabled com valor fixo `True`.
- **"Restaurar padrão" também restaura a ordem** — `restaurar_paginas_padrao()` (`tela_configuracoes.py:1273-1324`) volta os nativos ao nome/ícone codificados, reativados e na sequência de `MODULOS_SISTEMA`, renumerando os não-nativos após os nativos em ordem alfabética. **Correção (06/09)**: os SELECTs de renumeração agora usam cursor (`conn.execute(...)` + `fetchone()`/`fetchall()` — `tela_configuracoes.py:1304-1312`); antes chamavam `fetchone`/`fetchall` direto no `sqlite3.Connection` (`AttributeError`) e o restore das páginas nativas sempre falhava.
- **Campo "URL da página" (slug editável, 05/09)** — cada linha da lista ganhou um campo **"URL da página"** editável (`_campo_empilhado("URL da página", rota, ...)` em `tela_configuracoes.py:660-662`), ligado em `campos_url[chave] = inp_url` / `estado_campos["urls"]` (`tela_configuracoes.py:593-594`). Ao aplicar, `aplicar_paginas()` (`tela_configuracoes.py:412-452`) compara o valor com a rota vigente no BD e chama `autenticacao.alterar_rota_modulo` (`autenticacao.py:196-232`), que valida a URL (regex `[a-z0-9_\-/]+`), impede colisão entre módulos, grava `tb_modulos.rota` e **re-registra a página ao vivo** via `rotas_modulos.registrar_modulo` — sem restart. A notificação informa "N URL(s) alterada(s) — recarregue com F5". O registro dinâmico de rotas vive em `mod_intranet/rotas_modulos.py` (`DEFAULT_ROTAS`, `REGISTRO_MODULOS`, `_registradas`, `_normalizar_rota`, `registrar_modulo`, `montar_rotas_ativas`), com `REGISTRO_MODULOS["chave"] = page_*` preenchido em `main.py` após cada decorator fixo e `montar_rotas_ativas()` antes do START (`main.py:426`). Os decorators fixos são mantidos — links antigos continuam válidos.
- **Grid responsivo (05/09)** — `COLUNAS_MODULOS` (`tela_configuracoes.py:44-47`) deixou de usar `columns=` inline e agora é **responsiva**: `grid-cols-1 sm:grid-cols-2 lg:grid-cols-[56px_minmax(12ch,1fr)_minmax(22ch,1fr)_minmax(22ch,1fr)_minmax(20ch,1fr)_150px]` — 6 colunas em desktop (setas, chave, nome, URL, ícone, situação), empilhando em telas pequenas. O cabeçalho é oculto em sm/md (`hidden lg:grid`, `tela_configuracoes.py:619`), o `overflow-x-auto` foi removido e os inputs usam `w-full max-w-[30ch]`.
- O grid ganhou cabeçalho com **tooltips** explicando cada coluna e colunas `56px minmax(30ch, 1fr) minmax(30ch, 1fr) minmax(30ch, 1fr) 150px` (`tela_configuracoes.py:581-593`).

## Sem variáveis de ambiente `.env`

Diferente de muitos projetos NiceGUI, a Intranet **não lê `.env` nem variáveis de ambiente**. Toda configuração operacional é:

1. **Hardcoded** no `main.py` (porta, `storage_secret`, favicon) — editar o arquivo para mudar; ou
2. **Persistida** na `tb_config` central — alterável em runtime pelas telas de administração (Configurações e abas "Administração" de cada módulo), valendo **sem reiniciar o servidor**.