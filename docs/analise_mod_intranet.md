# Núcleo — `mod_intranet`

> Core module: routes `/`, `/login`, `/configuracoes` · central database `db_mod_intranet.db` (unified WAL audit, config, sessions, module registry) · revocable sessions · 4-part layout · centralized observability (loguru).

---

# Núcleo — `mod_intranet`

> Módulo central: rotas `/`, `/login`, `/configuracoes` · banco central `db_mod_intranet.db` (auditoria unificada em WAL, configurações, sessões e cadastro de módulos) · sessões revogáveis · layout de 4 partes · observabilidade centralizada (loguru).

## Propósito

Pacote núcleo que centraliza tudo o que os módulos compartilham: banco central (auditoria unificada LGPD, configurações, sessões e cadastro de módulos), autenticação com sessões revogáveis, layout padrão de 4 partes com guarda de página, rotinas agendadas (backup por módulo + expiração do editorPDF) e a tela de personalização `/configuracoes`. Não possui `telas.py` próprio — suas telas (`layout_tela`, `tela_configuracoes`, `dialogo_backup`) são montadas pelas rotas de `main.py`.

## Banco central `db_mod_intranet.db`

Toda conexão executa `PRAGMA journal_mode=WAL` + `synchronous=NORMAL` (`bd_conexao.py:29-30`). Tabelas criadas por `init_db()` (`bd_conexao.py:34-77`), chamada pelo bootstrap `inicializar_bancos()` **antes** da importação de qualquer módulo:

> ⚠️ **Reconstrução do núcleo**: `bd_conexao.py`, `bd_manipulador.py` e `dialogo_backup.py` estavam **ausentes como fonte** (restavam só `*.pyc` em `__pycache__`) e foram reconstruídos fielmente a partir do bytecode. Em caso de divergência de comportamento esperada, comparar com o `*.pyc` correspondente (ou `gh-pages`). `bd_manipulador.py` central expõe `get_intranet_conn`, `garantir_rastreabilidade`, `audit_log`, `hash_arquivo`; `bd_conexao.py` expõe `get_connection`, `get_config`, `set_config`, `init_db`, `favicon_versao`, `DB_PATH`, `PADRAO_CONFIG`.

| Tabela | Conteúdo | Criada em |
|:---|:---|:---|
| `tb_auditoria` | id, usuario, modulo, acao, descricao, timestamp, hash_arquivo + colunas `ip`/`user_agent` (migração `garantir_rastreabilidade`) | `bd_conexao.py:38-47` |
| `tb_config` | chave PK / valor — seeds: `versao_sistema=1.0.260908`, `cotadisco_global_gb=10`, `backup_interval_hours=12` (legada) e padrões de aparência | `bd_conexao.py:49-74` |
| `tb_sessoes` | id, usuario, modulo, login/logout_timestamp, cookie_hash + `ip`, `user_agent`, `dispositivo`, `mac` | `bd_conexao.py:55-63` |
| `tb_modulos` | id, chave UNIQUE, nome, icone, rota, ativo, nativo, **ordem** — semeada com os 5 módulos nativos; `ordem` controla a exibição (migração idempotente em bancos antigos) | `autenticacao.py:29-84` |

`init_db()` encerra com `PRAGMA wal_checkpoint(TRUNCATE)` para evitar "no such table" em instalação limpa sob WAL.

## Autenticação e sessões

- `MODULOS_SISTEMA` (`autenticacao.py:15`) semeia os módulos nativos `(chave, nome, icone, rota)`; `CHAVE_POR_ROTA` (`autenticacao.py:23`) mapeia rota→chave: **rota ≠ slug** — `/users`→`usuarios`, `/edit-pdf`→`editar_pdf`, `/renomear-empenho`→`empenhos`.
- `autenticar()` (`autenticacao.py:178`): bcrypt; falha audita `login_falha`; bloqueio recusa login. Retorna `(True, perfil)`.
- `registrar_login()` (`autenticacao.py:223`): gera `cookie_hash = sha256(user|timestamp|token)[:16]` com `secrets` (sem colisão entre navegadores no mesmo segundo); grava IP/User-Agent/dispositivo/MAC em `tb_sessoes`; audita `login`; poda histórico conforme `sessao_retencao` (padrão 50 por usuário).
- Guarda revalida a cada request via `sessao_ativa()` (`autenticacao.py:256`): sessão encerrada pelo admin derruba o navegador na próxima interação.
- `validar_acesso_modulo()` (`autenticacao.py:421`) delega ao manipulador do módulo de usuários — o núcleo nunca lê `tb_usuarios` diretamente.
- Autoatendimento: flag `forcar_troca:<user>` em `tb_config` + diálogo persistent de troca obrigatória no layout.

## Guarda de página — `layout_tela.pagina_restrita()`

1. Sem usuário → redireciona `/login`.
2. Revalida existência/situação ativa contra o BD → aviso "Sua sessão foi encerrada pelo administrador."
3. Valida `sessao_ativa()`; sessões antigas sem hash são adotadas automaticamente.
4. Monta o layout de 4 partes: header (hambúrguer, botão de backup do módulo quando autorizado, "Meu Perfil", badge de perfil, logout), drawer lateral (módulos liberados; vínculo a módulo inativo vira item laranja de alerta; Configurações só ao administrador geral), rodapé com `versao_sistema`, área principal.
5. Se `precisa_trocar_senha()`, abre diálogo persistent de troca obrigatória.

## Rastreabilidade — `contexto.py`

ContextVar do NiceGUI disponibiliza IP/UA tanto na renderização quanto nos callbacks. IP prioriza `X-Forwarded-For` (proxy reverso); `rotulo_dispositivo()` produz ex.: "Chrome 126 · Windows 10/11"; `mac_best_effort()` só consulta IPs `192.168.*` via `ping -c1 -W1` + `ip neigh show` — sintaxe Linux: neste host Windows retorna `None` silenciosamente.

## Rotinas agendadas — `rotinas.iniciar_agendador()`

- Um job de backup **por módulo**: intervalo lido de `tb_config backup_horas:<modulo>` (default 12 h, mínimo 1 h), reagendável sem restart (`reagendar_backup`). Retenção das **10 cópias mais recentes por banco** em `backup/`.
- Job `cleanup_pdf` a cada **1 min**: chama `mod_edit_pdf.expirar_antigos(cfg_expiracao_min())`; em falha de import cai no fallback `limpar_editor_pdf(minutos=10)`.

## Telas de configuração

`/configuracoes` (exclusiva do `administrador_geral`), organizada no padrão **menu_mod de abas** (mesmo padrão da Gestão de Usuários): barra com 5 abas à esquerda — **sem botão "APLICAR" geral** desde 06/09 (cada card tem seu próprio rodapé "Restaurar padrão" + "Aplicar").

| Aba | Ícone | Conteúdo |
|:---|:---|:---|
| Config | `tune` | Cores e ícone (color_input, ícone Material, nome do sistema, favicon `.ico` ≤1 MB) + Textos fixos (login, home, rodapé) + Configurações gerais (backup horas, retenção de sessão, pasta raiz) |
| E-mail | `mail` | SMTP: servidor, porta, usuário, remetente, senha, TLS + "Testar conexão SMTP" |
| Módulo | `extension` | Páginas do sistema (lista ÚNICA reordenável com ↑/↓, nome/ícone/ativa por módulo; indispensáveis destacados) + registro de módulos e vínculos órfãos |
| Observabilidade | `query_stats` | Logs loguru (ativo, nível, rotação, retenção, console auto/sempre/nunca, envio ao Loki) + telemetria OTel (endpoint local/remoto, stack local) + URL Grafana + "Limpar TODOS os logs" |
| Documentação | `menu_book` | Rebuild MkDocs para `/documentacao` + abrir em nova aba |

Não há mais um botão único "APLICAR" geral: cada card é recolhível (`card_admin`, `aberto=False`) e tem o rodapé padrão de 2 botões — "Restaurar padrão" e "Aplicar" — exclusivos do card (`_aplicar_card`, `tela_configuracoes.py:284-308`): grava só os campos daquele card, aguarda 1 segundo e recarrega. A persistência grava em `tb_config` (`cor_principal`, `texto_*`, `smtp_*`, `log_*`, `backup_interval_hours`, `sessao_retencao`) e em `tb_modulos` (nome/ícone/ativo).

`dialogo_backup.abrir_dialogo()` (botão no header do módulo, para quem pode gerenciar): intervalo em horas salvo + reagendado ao vivo, "Fazer backup agora" e grade das cópias retidas.

## Versionamento no rodapé — `layout_tela._montar_layout`

O rodapé mostra as versões **da esquerda para a direita**: 1ª a versão global do sistema (`v{versao_sistema}`), e quando o usuário está dentro de um módulo (`chave_modulo`), 2ª a versão **individual do módulo atual** (`v{versao_modulo:<chave>}`). Sem módulo específico (Dashboard/Configurações) aparece só a global. A versão individual é lida de `tb_config` (chave `versao_modulo:<chave>`, mesmo estilo `1.0.AAMMDD`) com fallback `1.0` quando o módulo ainda não versionou. Ex.: `/edit-pdf` mostra `v1.0.260908` (sistema) + `v1.0.260908` (mod_edit_pdf).

**Seed centralizado**: `versao_modulo:<chave>` é semeada para os 5 módulos (`usuarios`, `auditoria`, `editar_pdf`, `empenhos`, `blog`) em `bd_conexao.init_db()` com `INSERT OR IGNORE` — idempotente, não sobrescreve edição manual. Para refletir numa base existente, chame `init_db()` novamente.

**Painel "Administração" por módulo**: cada módulo ganhou uma aba/expansão exclusiva do admin geral (ou admin do módulo) com o bloco **Aparência** (tema dos botões via `ui.color_input`, prefixo `<chave>_`) e **config específica de comportamento** salva via `set_config` do núcleo. Padrões: `usuarios_senha_min`, `auditoria_limite`/`auditoria_retencao_dias`/`auditoria_texto_header`, `empenhos_pasta_monitorada`/`empenhos_texto_header`, `blog_tags_permitidas`/`blog_texto_header`, além do `editpdf_*` já existente.

## Integrações — o que os módulos importam do núcleo

| Função | Consumidores |
|:---|:---|
| `layout_tela.pagina_restrita` | todas as rotas de `main.py` |
| `get_connection` / `DB_PATH` / `audit_log` | manipuladores de todos os módulos |
| `get_config` / `set_config` | mod_edit_pdf (cotas/expiração), telas de login/home |
| `gerar_hash_senha`, `marcar_trocar_senha` | mod_gest_cad_usuario |
| `pode_publicar_no_blog`, `eh_admin_do_modulo` | mod_blog |

## Padronização de tema e administração dos módulos — `tema_modulo.py`

Helper central em `mod_intranet/tema_modulo.py` que unifica, em TODOS os módulos, a
configuração de aparência e o gerenciamento dos próprios módulos — eliminando a duplicação de
código e a variação de nomes que existiam entre as telas.

- **`PREFIXO_POR_CHAVE` / `prefixo_da_chave(chave)`**: mapeia a chave do módulo
  (`blog`, `usuarios`, `auditoria`, `editar_pdf`, `empenhos`, `solicita_impressao`) para o
  prefixo das chaves em `tb_config` central (`blog_*`, `usuarios_*`, `auditoria_*`, `editpdf_*`,
  `empenhos_*`, `solicita_impressao_*`).
- **`ler_tema(chave, defaults...)` / `salvar_tema` / `restaurar_tema`**: as **6 chaves** de
  aparência (`cor_botao`, `cor_texto_botao`, `cor_fundo`, `cor_titulo`, `btn_tamanho`,
  `texto_header`), lidas/gravadas em `tb_config` central, com aplicação imediata (sem restart).
  **Padrão próprio do módulo (06/09)**: para `cor_botao`/`cor_texto_botao`/`btn_tamanho` a precedência
  é (1) chave do módulo (`<prefixo>_<campo>`) não vazia → (2) default do parâmetro (quando o
  chamador informa) → (3) padrão do PRÓPRIO módulo (`PADROES_TEMA`, `tema_modulo.py:53-68`); ou
  seja, **chave do módulo vazia = padrão do próprio módulo** — o tema do sistema (`intranet_*`)
  **NÃO é herdado** (`tema_modulo.py:94-126`). `cor_fundo`, `cor_titulo` e `texto_header` seguem
  a mesma regra (vazio = default do parâmetro).
- **`btn_cls(tamanho)` / `btn_style(cor_botao, cor_texto)`**: funções puras de classe/estilo.
  Garantem a regra de **uniformidade** — todos os botões de uma mesma tela usam **sempre a mesma
  cor/tamanho** (por construção, via o mesmo `_btn_style`/`_btn_cls` da tela e o mesmo prefixo).
- **`botao(rotulo, variante, ...)`**: botão padronizado do tema (`solido`/`contorno`/`texto`) —
  **delega** à fábrica central `ui_comum.botao` (ver "Fábrica central de componentes de UI" ao
  final). O rodapé do `bloco_aparencia` usa o padronizado `ui_comum.rodape_salvar_restaurar`.
- **`bloco_aparencia(usuario_logado, chave, tema)`**: cupê "Aparência" padronizado da aba
  Administração (cor do botão, cor do texto, fundo, títulos, tamanho e texto do cabeçalho), **com
  botão Salvar próprio** e "Restaurar padrão", gravando via `salvar_tema` e audita. Campos de
  botão gravados vazios usam o padrão do PRÓPRIO módulo (`PADROES_TEMA`); os inputs exibem o valor
  resolvido com os rótulos "vazio = padrão do módulo" (`tema_modulo.py:319-322`) — para voltar ao
  padrão, "Restaurar padrão" grava `""` (via `tema["_defaults"]`). Ganhou `com_card` (06/09,
  `tema_modulo.py:295`): `com_card=True` (padrão) envolve em `ui_comum.card_admin`;
  `com_card=False` renderiza só o conteúdo (callers com card próprio, ex. edit_pdf admin).
- **`campo_modulo(usuario_logado, chave_modulo, nome_atual=None, icone_atual=None, ativo_atual=None)`**
  (`tema_modulo.py:338-409`): cupê "Edição do módulo" da aba Administração — nome de exibição,
  ícone (Material) e status ativo/desativado em `tb_modulos`, com auditoria `editar_modulo` e
  rodapé padronizado `ui_comum.rodape_salvar_restaurar` ("Salvar módulo"). **Restaurado em 06/09**
  após remoção acidental (regressão — o admin do módulo perdia renomear módulo/ícone/ativo):
  byte-idêntico ao original com 2 modernizações — inputs via `ui_comum.campo_texto` e docstring
  bilíngue. Usado pelos 6 módulos de negócio (auditoria `mod_auditoria/telas.py:570`, blog
  `mod_blog/telas.py:417`, edit_pdf `mod_edit_pdf/telas.py:927`, gest `mod_gest_cad_usuario/telas.py:705`,
  renomear `mod_renomear_empenho/telas.py:951`, solicita_impressao `mod_solicita_impressao/telas.py:986`);
  a edição também permanece no painel central `/configuracoes` (aba Módulo, admin geral).

**Adoção**: `edit_pdf`, `solicita_impressao` e `usuarios` (aba Administração) usam o cupê
padronizado `bloco_aparencia`; os 6 módulos de negócio usam `campo_modulo` (restaurado em 06/09).
A regra de uniformidade e o helper são cobertos por `test/test_tema.py` (18 verificações standalone).

## Hora do servidor (NTP)

Novo helper central `mod_intranet/hora_servidor.py` (07/09) — **fonte da verdade de data/hora do
sistema**: a data atual e de gravação devem vir SEMPRE do servidor (nunca do navegador/cliente).

- **`hora_servidor()`** (`hora_servidor.py:109-114`): retorna o `datetime` atual do servidor
  corrigido pelo offset NTP quando disponível; falha cai no relógio local (fail-soft).
- **`hora_servidor_str(formato)`** (`:117-119`): mesma hora como string no formato informado.
- **`offset_ntp()`** (`:83-106`): offset NTP em segundos com **cache de 60 s** e **lock
  threading**; após falha aguarda um intervalo antes de tentar de novo (não martela a rede);
  retorna 0 quando indisponível ou NTP desativado.
- **`definir_ntp_ativa(valor)`** (`:122-125`): persiste em `tb_config` a chave `hora_ntp_ativa`
  (`1`/`0`).
- **Sincronização NTP.br** (`_obter_offset_ntp`, `:50-80`): protocolo NTP v3 (RFC 5905) via
  **socket UDP puro** (sem ntplib), servidores `a.ntp.br`/`b.ntp.br`/`c.ntp.br`, timeout 2 s,
  porta 123. Sem internet (ou NTP desativado) usa o relógio local do servidor.
- **Configuração**: chave `hora_ntp_ativa` em `tb_config` central (default `"1"` = ativa),
  lida via `get_config` — sem restart.
- **Adoção**: `mod_solicita_impressao` usa `hora_servidor()`/`hora_servidor_str()` em todas as
  datas (criação, autorização, impressão, expiração, marca d'água e mês de cota) e
  `datetime('now','localtime')` no SQL — ver [Análise do Módulo de Impressão](analise_mod_solicita_impressao.md#hora-do-servidor-fonte-da-verdade-de-datahora).
- **Robustez**: todas as funções com `try/except` + loguru (`_log()` →
  `observabilidade.get_logger("intranet")`), fail-soft (nunca derruba a hora).

## Pontos de atenção

- Bootstrap: `inicializar_bancos()` roda antes de qualquer import de módulo (`main.py:15-16`) — ordem crítica.
- O PLANO cita `mod_intranet_bd_criador.py` e `mod_intranet_auditoria.py`: esses arquivos **não existem** — quem cria as tabelas é `bd_conexao.init_db()` e quem audita é `bd_manipulador.audit_log()`.
- `storage_secret` do `ui.run` é placeholder hardcoded ("...mude-isto") — trocar antes de produção.
- `backup_interval_hours` é semente legada; os jobs usam apenas `backup_horas:<modulo>`. `sessao_retencao` não tem campo na UI.
- MAC via ARP não funciona neste host Windows (comandos Linux) — coluna fica nula.

## Status — Fase 1 do PLANO.md

**Implementado:**

- Banco central `db_mod_intranet.db` em modo **WAL** + `tb_auditoria` unificada (rastreabilidade IP/UA/dispositivo/MAC via `garantir_rastreabilidade`).
- Auditoria centralizada: `bd_manipulador.audit_log` registra config/auth/permissões/acessos de todos os módulos.
- Visibilidade de módulos por permissão (drawer lateral com alerta de módulo inativo/removido).
- Login com sessão registrada em banco (`registrar_login`) + **sessões revogáveis**: `cookie_hash` via `secrets`, revalidação a cada request (`sessao_ativa`), logout próprio preserva as demais sessões do usuário.
- Gestão de Sessões (ativas + histórico + encerrar) no módulo de usuários; **retenção** do histórico implementada no mecanismo (poda por `sessao_retencao`, default 50/usuário).
- Layout de 4 partes (`layout_tela.pagina_restrita`) com versão no rodapé; área principal carrega o **Blog por padrão** (feed de publicações recentes) — RF-09 **REALIZADO**; a navegação por módulos permanece no drawer lateral.
- Personalização de cor primária/fundo, ícone, título, textos e favicon via `/configuracoes` (gravação única, vale sem restart).
- Edição de Perfil ("Meu Perfil") e troca obrigatória de senha do `master` no 1º login (auto-cura idempotente em boot — `mod_gest_cad_usuario/bd_manipulador.py:136-156`).
- Backup automático configurável por módulo (12 h default, sem restart) + expiração do editorPDF agendada.
- **Observabilidade centralizada (loguru)** — ver seção "Observabilidade / Logs".
- Carimbos de auditoria (`tb_auditoria.timestamp`) gravados em `localtime` (RF-08) — **REALIZADO**.
- Cookie de sessão **HttpOnly** (RF-04/16) — **REALIZADO** no nível de framework: o NiceGUI/Starlette define `HttpOnly=True` no cookie `app.storage.user`.
- Tela de Configurações (RF-57) — **REALIZADO**: cartão "Configurações gerais" com `sessao_retencao`, `backup_interval_hours` (reagenda todos os backups sem restart) e exibição da pasta raiz.
- Servidor SMTP (RF-58) — **REALIZADO**: `mod_intranet/email_util.py` + cartão "E-mail / SMTP" (credenciais `smtp_*` em `tb_config` + teste de conexão).
- Dashboard mobile-first (Fase 1) — **REALIZADO**: `main.py:page_dashboard` (`main.py:147-234`) renderiza banner de boas-vindas, card "Resumo do sistema" (apenas para `administrador_geral` ou `administrador_modulo` — `main.py:155`) com métricas em `ui.row()` responsivo (`w-full gap-2 flex-wrap`) e feed do Blog em largura total (`ui.column` `w-full gap-4`). Microinterações Tailwind (`transition-transform hover:-translate-y-0.5 hover:shadow-lg`) e feedback de 2s: toast de boas-vindas (`ui.notify(... timeout=2)`) + botão "Atualizar resumo" que exibe "Atualizado ✓" e reverte em 2s (`ui.timer(2.0, once=True)`).
- CSS frameworks embarcados (Bootstrap, Bulma, DaisyUI, Pico, Picnic) servidos localmente em `/css/frameworks/*` via `tema_css.py` — **REALIZADO**: injeção por página, sem CDN, com fallback silencioso no boot.

### Adições recentes (05/09)

#### Dashboard `/` — resumo reposicionado e restrito a administradores

- **`main.py:155`**: `eh_admin` agora aceita `administrador_geral` OU `administrador_modulo` (antes era apenas `== "administrador_geral"`). Isso amplia a visibilidade do card de resumo para admin de módulos.
- **`main.py:174-211`**: O "Resumo do sistema" foi **movido de uma sidebar direita para abaixo do banner de boas-vindas** e acima do feed do blog, em largura total. O container antigo era `ui.grid(columns=3)` com `max-lg:grid-cols-2`/`max-sm:grid-cols-1` que separava feed (2/3) e resumo (1/3). Agora o bloco é sequencial: banner → resumo → feed, todos em `w-full`.
- **`main.py:190`**: As métricas passaram de `ui.column()` (`w-full gap-2`) para `ui.row()` (`w-full gap-2 flex-wrap`), exibindo os três cards lado a lado com quebra responsiva.
- **`main.py:196-198`**: Os três cards `_stat` são **sempre renderizados** dentro do bloco de admin: "Usuários ativos" (`people`), "Postagens" (`article`) e "Registros de auditoria" (`history`). Antes, o de auditoria era condicionado a `if eh_admin` — redundante agora que o bloco inteiro já é `if eh_admin`.
- **`main.py:213-234`**: O **Feed do Blog** agora ocupa largura total (`ui.column` `w-full gap-4`, sem `col-span-*`). Cabeçalho "Publicações recentes" + botão "Abrir Blog completo" inalterados; cards de postagens via `_card_postagem` e `pode_publicar_blog` permanecem iguais.

#### Menu lateral — item "Home" no topo do drawer

- **`layout_tela.py:135-144`**: Adicionado no **TOPO do drawer** (antes da seção "MÓDULOS") um item "Home" sob o rótulo de seção "PÁGINA INICIAL". O item usa ícone `home` e `ui.item_label("Home")`, navegando para `/` via `ui.navigate.to("/")`. Seguido de `ui.separator()` antes de "MÓDULOS" (`layout_tela.py:144`). Antes, o drawer começava direto com "MÓDULOS" — agora há um atalho explícito para a página inicial visível em todas as rotas.
- **Padrão de exibição** — **REALIZADO**: todos os módulos seguem o padrão do **módulo exemplo `mod_edit_pdf`** — área cheia (`w-full`, sem `max-w-*` centralizador) e cupê **"Aparência"** padronizado na aba/expansão Administração com as **6 chaves** `cor_botao`, `cor_texto_botao`, `cor_fundo`, `cor_titulo`, `btn_tamanho`, `texto_header` em `tb_config` (prefixos `blog_*`, `usuarios_*`, `auditoria_*`, `empenhos_*`, `solicita_impressao_*`; o `editar_pdf` usa `editpdf_*`). `aba_modulo.cabecalho()` passou a aceitar `cor_titulo`/`cor_fundo`, aplicando o tema sem restart. Áreas que já eram `w-full` (auditoria, empenhos) mantidas; blog/usuários/solicita tiveram o `max-w-* mx-auto` centralizador removido.

#### Tela de Configurações — reorganizada no padrão menu_mod (abas)

- **`tela_configuracoes.py:189-198`**: a tela `/configuracoes` deixou de ser um empilhamento de 8 cartões sequenciais com um único "SALVAR TUDO" no topo e passou a usar `ui.tabs` + `ui.tab_panels` (padrão menu_mod, como a Gestão de Usuários): barra com **5 abas** à esquerda e botão **"APLICAR"** à direita.
- **`tela_configuracoes.py:190-194`**: as 5 abas são `Config` (`tune`), `E-mail` (`mail`), `Módulo` (`extension`), `Observabilidade` (`query_stats`) e `Documentação` (`menu_book`).
- **Botão único "APLICAR"**: grava todas as abas via `salvar_tudo` e recarrega (`ui.navigate.reload`) para aplicar cores/botões/cards imediatamente.
- **`tela_configuracoes.py:98-175`**: `salvar_tudo` mantido, agora comentado **por aba** (Config → cores/ícone/textos/gerais; E-mail → `smtp_*`; Módulo → `tb_modulos`; Observabilidade → `log_*`/`otel_*`/`grafana_url` + `observabilidade.configurar()` (endpoint/OTel exigem restart).
- **Conteúdo por aba**: Config reúne, nesta ordem: **Ícones** (grid único responsivo com 3 itens — ícone do sistema, "Restaurar padrão" e upload do favicon `.ico`), **Cores** (8 seletores em grade 4+4 + prévia única ao vivo), **Textos fixos** (+ nome do sistema, rótulo dentro do input) e **Gerais RF-57** (padrão responsivo da aba Módulo: 1 col celular, 2 médio, linha cheia desktop) (`tela_configuracoes.py:316-355`) e Configurações gerais RF-57 (`tela_configuracoes.py:357-400`); E-mail/SMTP RF-58 (`tela_configuracoes.py:402-453`, com "Testar conexão SMTP" em `tela_configuracoes.py:438-447`); Observabilidade (`tela_configuracoes.py:656-850`, com "Limpar TODOS os logs" em `tela_configuracoes.py:844`); Documentação (`tela_configuracoes.py:506-528`, rebuild MkDocs + abrir `/documentacao` em nova aba); Módulo (`tela_configuracoes.py:578-865`, páginas do sistema + registro de módulos e vínculos órfãos).
- **Não mudou**: chaves em `tb_config` (`cor_principal`, `texto_*`, `smtp_*`, `log_*`, `backup_interval_hours`, `sessao_retencao`), restrição a `administrador_geral` (`tela_configuracoes.py:59-63`), autenticação e a rota `/configuracoes` em `main.py`.

#### Abas renomeadas e reordenadas (05/09) — Config, E-mail, Módulo, Observabilidade, Documentação

- **`tela_configuracoes.py:190-194`**: as 5 abas foram **renomeadas e reordenadas** — antes `[Config geral, E-mail, Observabilidade, Documentação técnica, Módulo]`, agora **`[Config, E-mail, Módulo, Observabilidade, Documentação]`** (mesmos ícones: `tune`, `mail`, `extension`, `query_stats`, `menu_book`).
- **`tela_configuracoes.py:200-865`**: os `ui.tab_panel` foram renomeados/reordenados no código; a **ordem DOM dos painéis** (Config, E-mail, Observabilidade, Documentação, Módulo) **não coincide mais com a ordem da barra de abas** — o Quasar `q-tab-panels` vincula abas a painéis pelo atributo `name`, então **não há mudança funcional**.
- **Prévia única ao vivo**: `previa()` (`@ui.refreshable`) mostra cabeçalho, card e botões com os valores dos campos antes de salvar; qualquer campo de aparência dispara `previa.refresh()`.
- **`tela_configuracoes.py:508`**: rótulo do painel "Documentação" (antes "Documentação técnica").
- **`tela_configuracoes.py:1-16, 53-58`**: docstring do módulo (tabela de abas) e de `mostrar_tela` atualizadas para a nova ordem; comentários internos "# Aba Config —" e "# ABA: <nome>" renomeados.

#### Aba "Módulo" — redesenho (05/09): ícone editável com seletor, alinhamento e grupos

- **`tela_configuracoes.py:165`**: a aba foi **renomeada** de "Registro/Nome de módulo" para **"Módulo"** (`tab_mod = ui.tab("Módulo", icon="extension")`); docstring do módulo, comentário do `salvar_tudo` e cabeçalho da seção atualizados.
- **`tela_configuracoes.py:33-39`**: nova constante `ICONES_COMUNS` — 31 ícones Material oferecidos no seletor visual (article, people, manage_accounts, history, folder_open, print, picture_as_pdf, extension, home, settings, menu_book, dashboard, description, list, tune, mail, query_stats, hub, apartment, domain, blog, edit, lock, save, restore, add_circle, link_off, delete_forever, open_in_new, info, settings_applications).
- **`tela_configuracoes.py:519-546`**: nova função `_campo_icone(valor_inicial)` — input livre do nome do Material Icon + **pré-visualização viva** (`prev.set_text` ligado ao `on_value_change`, com fallback `extension`) + **seletor visual** (`ui.menu` com grid de 6 colunas sobre `ICONES_COMUNS`, cada botão aplica o ícone e fecha o menu) + botão `grid_view` para abrir o seletor. Retorna o `ui.input` criado. Reutilizada no campo "Ícone Material" do registro de novo módulo (`tela_configuracoes.py:762`).
- **`tela_configuracoes.py:45`**: constante `COLUNAS_MODULOS = "56px minmax(30ch, 1fr) minmax(30ch, 1fr) minmax(30ch, 1fr) 150px"` **compartilhada entre cabeçalho e linhas** — mesmo `columns`/`gap` (0.75rem via `.style`) e mesmo padding (`px-3 py-2`). Antes o cabeçalho não tinha gap → desalinhamento com as linhas; a 1ª coluna (56px) hoje exibe posição + setas ↑/↓ (ver "Reordenação de módulos" abaixo).
- **`tela_configuracoes.py:566-636`**: a lista de módulos é **ÚNICA** (os grupos separados "Indispensáveis"/"Demais" foram substituídos pela lista reordenável — ver "Reordenação de módulos" abaixo); container `ui.column` `w-full overflow-x-auto` (responsividade) envolvendo o cabeçalho do grid com **tooltips** por coluna ("#", "Página (chave)", "Nome exibido (menu e título)", "Ícone (Material Icons)", "Situação").
- **`tela_configuracoes.py:595-630`**: módulos **indispensáveis** (auditoria, usuarios) destacados na lista única com fundo âmbar (`bg-amber-50/40 border-amber-200`) + ícone `lock` com tooltip "Sempre ativo — não pode ser desativado"; o switch fica **oculto** (`hidden`), desabilitado e com valor fixo `True`. Os demais módulos têm switch "Ativo" (`color=primary`).
- **`tela_configuracoes.py:123`**: `salvar_tudo` **força `ativo=1`** para chaves em `MODULOS_INDISPENSAVEIS` independente do switch, garantindo que nunca sejam desativados mesmo via salvamento em lote.
- **Compatibilidade mantida**: `estado_campos["paginas"]` continua com a tupla `(inp_nome, inp_icone, switch)` por chave (`tela_configuracoes.py:630`), lida por `salvar_tudo()`; a proteção de indispensáveis permanece no backend (`MODULOS_INDISPENSAVEIS` em `autenticacao.py:216`); a variável `registrados` não utilizada foi **removida** de `refresh_orfaos` (`tela_configuracoes.py:744`).
- **`tela_configuracoes.py:30`**: `MODULOS_INDISPENSAVEIS = {"auditoria", "usuarios"}` (junto de `CORES_PRESET`) — módulos essenciais que **não podem ser desativados**.

#### Backend — proteção de módulos indispensáveis em `autenticacao.py`

- **`autenticacao.py:216`**: nova constante `MODULOS_INDISPENSAVEIS = {"auditoria", "usuarios"}`.
- **`autenticacao.py:227-229`**: `set_modulo_ativo` agora **retorna `(False, msg)`** e registra auditoria `modulo_desativado_bloqueado` caso alguém tente desativar um módulo indispensável; a guarda de tempo/banco **não é executada** nesse caso. Em sucesso retorna `(True, "ok")` (contrato mudou de `None` para `(bool, str)`).
- **`autenticacao.py:481`**: `set_chaves_desativadas` filtra `set(chaves) - MODULOS_INDISPENSAVEIS` para que módulos indispensáveis **nunca** sejam desativados por essa via.

#### Reordenação de módulos — ordem editável (05/09)

- **`autenticacao.py:53`**: nova coluna `ordem INTEGER NOT NULL DEFAULT 0` na `CREATE TABLE tb_modulos` — a ordem de exibição dos módulos (menu lateral e liberações de usuário) passa a ser controlada por essa coluna.
- **Correção 07/09 — seed de `tb_modulos` em banco novo**: em instalação limpa (`metadata.create_all`) a tabela era criada SEM defaults SQL em `ativo`/`nativo`/`ordem` (defaults só do lado Python do ORM) e o `INSERT OR IGNORE` omitia `ativo`/`ordem` → cada INSERT violava NOT NULL e era silenciosamente ignorado (tabela vazia, menu sem módulos). Corrigido em duas frentes: `models/__init__.py:80-82` (colunas ganharam `server_default` — `ativo`="1", `nativo`="0", `ordem`="0") e `autenticacao.py:59-64` (INSERT agora inclui `ativo` e `ordem` explicitamente, 1 e 0). Idempotente em banco existente.
- **`autenticacao.py:61-75`**: **migração idempotente** para bancos antigos — `PRAGMA table_info(tb_modulos)` detecta a ausência da coluna e aplica `ALTER TABLE ADD COLUMN ordem INTEGER NOT NULL DEFAULT 0`; em seguida inicializa a sequência: nativos seguem `MODULOS_SISTEMA` (1..n) e não-nativos com `ordem=0` ficam após os nativos em ordem alfabética. Roda a cada boot sem efeito colateral quando já migrado.
- **`autenticacao.py:113`**: `modulos_registrados()` passou de `ORDER BY nativo DESC, nome` para **`ORDER BY ordem ASC, nome`** — as tuplas `(chave, nome, icone, rota, ativo)` permanecem intactas, então nenhum consumidor (drawer, liberações, `chaves_ativas`, `chaves_desativadas`) precisou mudar.
- **`autenticacao.py:141-148`**: `registrar_modulo()` grava `ordem = max(ordem)+1` — módulos novos nascem no fim da lista.
- **`autenticacao.py:162-192`**: nova função **`reordenar_modulos(ator, chaves_ordenadas)`** — recebe a lista COMPLETA de chaves na nova ordem, grava a posição 1-based de cada chave em `tb_modulos.ordem`, audita `modulos_reordenados` com a sequência final e retorna `(ok, msg)`. Defensivo: chaves ausentes da lista vão para o fim (ordem alfabética). `try/except` + loguru (`observabilidade.get_logger("intranet")`).
- **`tela_configuracoes.py:45`**: `COLUNAS_MODULOS` agora é `"56px minmax(30ch, 1fr) minmax(30ch, 1fr) minmax(30ch, 1fr) 150px"` — a 1ª coluna (56px) exibe a posição e os botões ↑/↓ de reordenação.
- **`tela_configuracoes.py:566-636`**: `refresh_modulos()` remonta a **lista ÚNICA de módulos** na ordem vigente de `tb_modulos.ordem` (substituiu os grupos separados "Indispensáveis"/"Demais") — todos reordenáveis; indispensáveis (auditoria, usuarios) destacados com fundo âmbar + cadeado, reordenáveis porém nunca desativáveis. Mantém `estado_campos["paginas"][chave] = (inp_nome, inp_icone, switch)` (contrato do `salvar_tudo`).
- **`tela_configuracoes.py:638-669`**: `_mover(idx, direcao)` troca o módulo com o vizinho (-1 sobe, +1 desce), **persiste de imediato** via `autenticacao.reordenar_modulos`, notifica e remonta a lista — edições pendentes (nome/ícone/ativo) são preservadas entre remontagens.
- **`tela_configuracoes.py:673-720`**: `restaurar_paginas_padrao()` agora também **restaura a ordem nativa** (nativos voltam à sequência de `MODULOS_SISTEMA`) e **renumera os não-nativos** após os nativos em ordem alfabética.
- **`layout_tela.py:147`**: sem mudança de código — o menu lateral já usa `modulos_do_usuario`, que herda a nova ordem via `modulos_registrados()`.

#### URL/slug editável dos módulos — `rotas_modulos.py` + `alterar_rota_modulo`

- **`mod_intranet/rotas_modulos.py`** (novo): registro **dinâmico** de rotas de páginas de módulos no NiceGUI, permitindo que a URL de cada página (`tb_modulos.rota`) seja editada em `/configuracoes` e re-registrada no servidor **sem restart**.
  - **`DEFAULT_ROTAS`** (`rotas_modulos.py:16-23`): espelho dos decorators fixos de `main.py` — `{"blog":"/blog","users":"/users","auditoria":"/auditoria","editar_pdf":"/edit-pdf","empenhos":"/renomear-empenho","solicita_impressao":"/solicita-impressao"}`. Usado para semear `_registradas` e como referência das rotas nativas.
  - **`REGISTRO_MODULOS: dict`** (`rotas_modulos.py:26`): chave→função de página, preenchido em `main.py` após cada decorator fixo.
  - **`_registradas: set`** (`rotas_modulos.py:30`): rotas já registradas no servidor — evita duplicidade (registrar o mesmo path duas vezes **quebraria o servidor**). Semeadas com `DEFAULT_ROTAS.values()`.
  - **`_normalizar_rota(rota)`** (`rotas_modulos.py:33-41`): garante `/` inicial, lowercase, espaço→hífen e remove `//` duplicados.
  - **`registrar_modulo(chave, rota)`** (`rotas_modulos.py:44-58`): registra via `ui.page(rota)(func)` de forma **idempotente** — se a chave não tiver página em `REGISTRO_MODULOS` (módulo futuro) ou a rota já estiver em `_registradas`, apenas retorna.
  - **`montar_rotas_ativas()`** (`rotas_modulos.py:61-69`): lê `tb_modulos` via `autenticacao.modulos_registrados()` e chama `registrar_modulo` para todos — re-registra slugs customizados persistidos após restart.
- **`main.py`**:
  - **`main.py:78-82`**: bloco "ROTAS DINÂMICAS DE MÓDULOS" — `try/except` que importa `rotas_modulos` (fallback `rotas_modulos = None`).
  - **`main.py:281, 295, 309, 323, 337, 400`**: `rotas_modulos.REGISTRO_MODULOS["chave"] = page_*` após cada decorator fixo (blog, usuarios, auditoria, editar_pdf, empenhos, solicita_impressao).
  - **`main.py:426`**: `rotas_modulos.montar_rotas_ativas()` antes do START — re-registra os slugs customizados persistidos. Os decorators fixos são **mantidos** (links antigos continuam válidos).
- **`autenticacao.py:196-232` — `alterar_rota_modulo(ator, chave, nova_rota)`**: normaliza a rota (`/` inicial, lowercase, espaço→hífen, sem `//`), valida com regex `[a-z0-9_\-/]+`, impede colisão de URL entre módulos (`SELECT ... WHERE rota=? AND chave<>?`), grava `tb_modulos.rota`, re-registra ao vivo via `rotas_modulos.registrar_modulo`, audita `modulo_rota_alterada` e usa try/except + loguru. Retorna `(ok, msg)`.
- **`tela_configuracoes.py` — campo "URL da página" e grid responsivo**:
  - **`tela_configuracoes.py:44-47`**: `COLUNAS_MODULOS` agora é **responsiva** — `"grid-cols-1 sm:grid-cols-2 lg:grid-cols-[56px_minmax(12ch,1fr)_minmax(22ch,1fr)_minmax(22ch,1fr)_minmax(20ch,1fr)_150px]"` (sem `columns=` inline). Em desktop (lg:) 6 colunas explícitas (setas, chave, nome, URL, ícone, situação); em sm/md empilha em 2 colunas (cada `_campo_empilhado` já coloca label acima do input).
  - **`tela_configuracoes.py:533-546`**: `_campo_empilhado(label, valor, readonly=False, tooltip=None)` — rótulo acima do input (empilhado), input `w-full max-w-[30ch]` que preenche a coluna do grid.
  - **`tela_configuracoes.py:660-662`**: novo campo `_campo_empilhado("URL da página", rota, ...)` em cada linha.
  - **`tela_configuracoes.py:593-594`**: `campos_url[chave] = inp_url` ligado em `estado_campos["urls"]` (lido pelo APLICAR). A tupla `estado_campos["paginas"] = (inp_n, inp_i, sw_a)` é **mantida**.
  - **`tela_configuracoes.py:139-158`**: `salvar_tudo()` — após o loop das páginas, itera `c.get("urls", {})`, compara o trim com a rota vigente no BD e chama `alterar_rota_modulo`; acumula avisos e notifica "N URL(s) alterada(s) — recarregue com F5".
  - **`tela_configuracoes.py:698-713`**: `_mover()` preserva a URL pendente entre remontagens (`pendentes_url`).
  - **`tela_configuracoes.py:737-744`**: `restaurar_paginas_padrao()` também restaura `rota` para `DEFAULT_ROTAS[chave]` dos nativos.
  - **`tela_configuracoes.py:619`**: cabeçalho do grid oculto em telas pequenas (`hidden lg:grid`); `overflow-x-auto` removido; inputs `w-full max-w-[30ch]`.
  - **`tela_configuracoes.py:816-818`**: card "Registrar novo módulo (futuro)" já tinha `n_rota` configurável (placeholder `# ou /rota-futura`) — confirmado.

#### CSS frameworks embarcados — Bootstrap/Bulma/DaisyUI/Pico/Picnic

- **`mod_intranet/tema_css.py`** (novo): módulo que serve os frameworks CSS baixados em
  `assets/css/frameworks/` localmente — **sem CDN**. A constante `FRAMEWORKS_CSS` cataloga
  cinco frameworks:

  | Chave | Arquivo | Descrição | Aviso de compatibilidade |
  |:---|:---|:---|:---|
  | `bootstrap` | `bootstrap@5.3.8.min.css` | Bootstrap 5.3.8 — grid `.row`/`.col`, utilitários e componentes (`.btn`, `.card`, `.badge`, `.table`) | Reset global (box-sizing, body, headings) pode afetar o Quasar; injeção por página em telas de marca própria ou escopado; JS do Bootstrap (dropdowns/toasts/offcanvas) não é servido — SÓ o CSS |
  | `bulma` | `bulma@1.0.2.min.css` | Flexbox utilitários/componentes | `.button` e resets podem chocar com Quasar |
  | `daisyui` | `daisyui@5.6.8.min.css` + `daisyui@5.6.8.themes.min.css` | Componentes `.btn`/`.card`/`.badge` sobre Tailwind | Depende de Tailwind v4 (NiceGUI embute v3 parcial); classes podem conflitar |
  | `pico` | `pico@2.min.css` | Reset + tipografia minimalista | Estiliza `<body>`/`<h1>`/`<button>` globais — pode quebrar Quasar |
  | `picnic` | `picnic@7.1.0.min.css` | Leve, estilo "demo site" | Projeto em manutenção reduzida; evite em módulos padronizados |

- **`tema_css.montar_rotas_static()`** (`tema_css.py:42-53`): registra `app.add_static_files("/css/frameworks", ...)` no boot. Falhas são silenciosas (não derrubam o servidor).
- **`tema_css.caminho_css(nome)`** (`tema_css.py:56-68`): devolve a URL HTTP de um framework (`/css/frameworks/<arquivo>`) ou a lista dos disponíveis quando `nome` é `None`. Retorna `None` para nome desconhecido.
- **`tema_css.injetar_framework(nome)`** (`tema_css.py:71-85`): adiciona `<link rel="stylesheet">` ao `<head>` da página atual via `ui.add_head_html()`. **Injeção POR PÁGINA, nunca global** — cada módulo/página que desejar um framework chama esta função explicitamente. Retorna `True`/`False`.
- **`tema_css._log()`** (`tema_css.py:88-90`): logger via `observabilidade.get_logger("intranet")`.
- **`main.py:64-71`**: bloco "CSS FRAMEWORKS EMBARCADOS" no boot — `try/except` que importa `tema_css` e chama `montar_rotas_static()`, com `print()` como fallback silencioso. Não há referência à palavra "cdn" no código (validado por `test/teste_boot.py`).
- **Arquivos em disco**: `assets/css/frameworks/` contém os seis arquivos `.min.css` + `README.md` com origem, licenças e instruções de uso.
- **Todos os logs** usam `loguru` via `_log()` (padrão `mod_intranet/intranet` com `try/except` em todas as funções).

#### Espaçamento `gap-*` → `style("gap: …")` e Bootstrap avaliado (05/09)

- **`mod_gest_cad_usuario/telas.py`** estudado como referência de boas práticas (sem alterações nele).
- **Bootstrap avaliado e não injetado**: o Bootstrap embarcado (`assets/css/frameworks/`, `mod_intranet/tema_css.py`) foi avaliado e **deliberadamente não injetado** em nenhuma tela — o reset global quebraria os componentes Quasar. Segue disponível para futuras páginas de marca própria via `injetar_framework()` (injeção por página, nunca global).
- **Migração `gap-*`** (bug #2171/Ubuntu, visual 1:1): `gap-*` em `.classes()` de `ui.row()`/`ui.column()` migrado para `.style("gap: …")` em 4 arquivos do núcleo:

| Arquivo | Trecho | Antes → depois |
|:---|:---|:---|
| `aba_modulo.py:25-26` | `cabecalho` | `gap-3`/`gap-0` → `style("gap: 0.75rem")` / `style("gap: 0")` |
| `layout_tela.py:122,128,205` | header (2x) + rodapé | `gap-2` → `style("gap: 0.5rem")` |
| `dialogo_backup.py:43` | linha do intervalo | `gap-2` → `style("gap: 0.5rem")` |
| `tema_modulo.py:289` | rodapé do `bloco_aparencia` | `gap-2` → `style("gap: 0.5rem")` (o `gap-3` do `ui.grid` em `tema_modulo.py:243` foi mantido — fora do escopo `row`/`column`) |

- **Docstrings** dos trechos tocados completadas no padrão EN+PT-BR (`cabecalho`, `_montar_layout`, `abrir_dialogo`, `bloco_aparencia`).

!!! note "Pendência conhecida (fora de escopo)"
    `gap-*` restante nos `telas.py` dos módulos e em `main.py` segue pendente para rodada futura — fora do escopo desta rodada (só o delta do núcleo foi migrado).

**Parcial/Pendente:**

- Nada pendente nesta fase (Fase 1 concluída — ver item 6 → REALIZADO acima).

### Adições recentes (06/09)

#### Card "Ícones" do Config — grid único responsivo (06/09)

- **`tela_configuracoes.py:433-496`**: o card **"Ícones"** da aba Config foi simplificado — removida a função `_linha_fav()` (badges "personalizado ativo"/"padrão NiceGUI" e preview base64 do favicon) e o label "Ícone da aba do navegador" acima do status. O card usa agora um **único grid inline responsivo** `grid-cols-1 sm:grid-cols-2 md:grid-cols-3` (`tela_configuracoes.py:468-470`), o mesmo padrão dos demais cards, com 3 itens:
    1. input **"Ícone do sistema (nome Material)"** (`tela_configuracoes.py:471-476`);
    2. botão **"Restaurar padrão"** — movido do rodapé centralizado para o grid, com o mesmo `on_click` (diálogo de confirmação → `restaurar_grupo` com `pos_acao=remover_fav`) (`tela_configuracoes.py:477-487`);
    3. `ui.upload` do favicon, com rótulo alterado de "Enviar .ico" para **"Enviar arquivo .ico para uso na aba do navegador"** (`tela_configuracoes.py:488-493`).
- **Não mudou**: `receber_ico` (upload/validação `.ico` ≤1 MB/auditoria `config_alterada` — `tela_configuracoes.py:444-466`) e `remover_fav` (restaura o favicon nativo do NiceGUI e audita `config_restaurada` — `tela_configuracoes.py:461-466`); chaves `tb_config` (`icone_sistema`, `favicon_custom`) e o cache-busting via `favicon_versao()` (`layout_tela.py:118-121`).
- **Docstrings**: `receber_ico` e `remover_fav` documentadas no padrão EN+PT-BR (`tela_configuracoes.py:444-452, 461-470`).
- **Teste**: `test/teste_config_intranet.py:104-105` atualizado — valida o novo label do upload e a ausência de `_linha_fav` no fonte (**50 OK, 0 falhas**).

#### Cabeçalho do módulo (`cabecalho`) resolvido pelo tema (06/09)

- **Assinatura nova** (`aba_modulo.py:33-35`): `cabecalho(titulo, subtitulo="", cor_borda=None, cor_titulo=None, cor_fundo=None, *, chave_modulo=None)`. Com `chave_modulo`, as cores vêm do **tema do módulo** via `tema_modulo.ler_tema(chave)` (`aba_modulo.py:50-59`):
    - **`cor_borda` = `tema["cor_botao"]`** — a cor de destaque da borda esquerda é a **MESMA cor geral do módulo** (chave `<prefixo>_cor_botao`; vazia = padrão do próprio módulo via `PADROES_TEMA`; editável no cupê Aparência, campo "Cor geral do módulo") — mesma fonte que colore os botões via `ui_comum.botao(chave_modulo=...)` e os menus/destaques via `ui.colors(primary=...)`;
    - `cor_titulo` = `tema["cor_titulo"]` e `cor_fundo` = `tema["cor_fundo"]`, idem;
    - **parâmetros explícitos vencem o tema** (só são substituídos quando `None`) — retrocompatibilidade total;
    - **sem chave** → defaults da paleta central `ui_comum.CORES` (`primaria`/`titulo`/`""` — `aba_modulo.py:63-68`), comportamento byte-idêntico ao anterior;
    - **fail-soft**: falha ao ler o tema → `warning` no loguru (`_log()` → `observabilidade.get_logger("intranet")`, `aba_modulo.py:60-62`) + defaults, sem derrubar a renderização;
    - `cor_fundo` vazio/`""` significa "herda" (não pinta o `.q-page` — `aba_modulo.py:75-79`).
- **Módulos migrados** (zero `cor_borda="#..."` hardcoded nas telas):

| Módulo | Chamada | Antes (borda hardcoded) | Local |
|:---|:---|:---|:---|
| Renomeador de Empenhos | `chave_modulo="empenhos"` | `cor_borda="#2E7D32"` | `mod_renomear_empenho/telas.py:85` |
| Auditoria | `chave_modulo="auditoria"` | `cor_borda="#C62828"` | `mod_auditoria/telas.py:345` |
| Blog | `chave_modulo="blog"` | `cor_borda="#7B1FA2"` | `mod_blog/telas.py:159` |
| Solicitação de Impressão | `chave_modulo="solicita_impressao"` | `cor_borda="#EF6C00"` | `mod_solicita_impressao/telas.py:49` |
| Gestão de Usuários | `chave_modulo="usuarios"` | `cor_borda=t_cor_botao` (variável) | `mod_gest_cad_usuario/telas.py:97-99` |

- **Exceção registrada**: `mod_edit_pdf` mantém **header custom** — estrutura diferente (label de admin "Uso global do servidor" + cota com `ui.linear_progress`), borda = `tema["cor_botao"]` (antes `CORES["perigo"]` fixo — `mod_edit_pdf/telas.py:621-624`).
- **Mudança visual intencional**: com as chaves de botão dos módulos vazias (padrão), a borda dos cabeçalhos segue o **padrão do módulo** (`PADROES_TEMA` — todos os módulos em `#000000`, a cor do intranet); a cor de cada módulo passa a ser **configurável por módulo** no cupê Aparência.
- **Testes**: `test/verifica_ui_comum.py` — seção 22 "cabecalho (tema do módulo)" (`test/verifica_ui_comum.py:907-991`): 6 verificações de render (sem chave byte-idêntico; borda/título/fundo do tema; `cor_fundo` vazio herda; explícitos vencem; `cor_fundo=""` explícito herda; tema indisponível → defaults sem crash) + 5 de migração dos módulos (fonte) = **139 → 150 verificações** (+11). `test/test_dashboard.py:100-105` com os 2 checks da assinatura atualizados (`cor_titulo`/`cor_fundo`).

#### Padrões `ui_comum` aplicados no núcleo (06/09)

- **`campo_texto` ampliado** (`ui_comum.py:314-317`): novos kwargs `senha=False` — cria o
  `ui.input` com `password=True, password_toggle_button=True` (campo de senha com botão
  exibir/ocultar, byte-idêntico aos campos de senha existentes; sem efeito com `multiline`) —
  e `placeholder=None` — repassado ao construtor quando informado. **Descoberta validada no
  NiceGUI real**: sem valor resolvido (`valor=None` sem `chave`) o kwarg `value` NÃO é
  repassado — réplica crua byte-idêntica (`ui.input` sem `value` usa `''`; `value=None` seria
  literal).
- **`campo_selecao` ampliado** (`ui_comum.py:374-376`): novo kwarg `tooltip=None` — aplicado
  somente quando informado.
- **Migrações byte-idênticas em `tela_configuracoes.py`**:
  - diálogo `confirmar` → `ui_comum.dialogo_card(largura="", max_altura=False)` (`tela_configuracoes.py:158`);
  - `f_icone` (`:487`), `inp_raiz` (`:783`), 3 selects de Observabilidade (`:906-932`, props
    reais `dense outlined`) e `n_chave`/`n_nome`/`n_rota` do diálogo de novo módulo
    (`:1328-1337`) → `campo_texto`/`campo_selecao`.
- **Migrações byte-idênticas em `telas.py`**: `_dialogo_meu_perfil` — 3 campos de dados
  pessoais + 3 senhas (`layout_tela.py:249-270`) e `_dialogo_troca_senha` — 3 senhas com
  `props=""` (troca obrigatória, sem `outlined dense` — `layout_tela.py:302-304`) →
  `campo_texto(senha=True)`.
- **Exceções mantidas cruas por byte-identidade**: `_campo_empilhado`/`_campo_icone` (label
  empilhada acima do input), botões da prévia (estado não salvo), cards Cores/Textos fixos e o
  `ui.number` do `dialogo_backup` (candidato a futuro `campo_numero`).
- **Contagens antes → depois**:

  | Arquivo | Métrica | Antes | Depois |
  |:---|:---|:---:|:---:|
  | `tela_configuracoes.py` | `ui.input` | 7 | 2 |
  | `tela_configuracoes.py` | `ui.select` | 3 | 0 |
  | `tela_configuracoes.py` | `ui.dialog` | 1 | 0 |
  | `tela_configuracoes.py` | `campo_texto` | 7 | 12 |
  | `tela_configuracoes.py` | `campo_selecao` | 1 | 4 |
  | `telas.py` | `ui.input` | 9 | 0 (6 senhas) |

- **Testes**: `test/verifica_ui_comum.py` — 150 → **165 verificações** (+15: seções
  `campo_texto` `:711` e `campo_selecao` `:794` ampliadas). Novo `test/smoke_senha_ui_comum.py`
  — **8 verificações com NiceGUI real** (sem stub): `campo_texto(senha=True)` byte-idêntico ao
  `ui.input` cru (props/classes/style/filhos, `type=password`, botão exibir/ocultar, `value`
  inicial `''` e não `None`, `props=''` da troca obrigatória, default sem senha e
  `placeholder`/`largura=''` do novo módulo).

#### Cupê "Edição do módulo" (`campo_modulo`) restaurado (06/09)

- **Regressão corrigida**: o cupê "Edição do módulo" havia sido **removido acidentalmente**
  (função fora de `tema_modulo.py` e chamadas/imports fora dos módulos) — o admin do módulo
  perdia renomear módulo/ícone/ativo.
- **`campo_modulo` reposto** em `tema_modulo.py:338-409` (fim do arquivo), **byte-idêntico ao
  HEAD** com 2 modernizações: inputs via `ui_comum.campo_texto` (nome sem tooltip, ícone com
  tooltip Material) e docstring bilíngue EN+PT-BR; rodapé `rodape_salvar_restaurar`
  ("Salvar módulo") mantido. Expansion `settings_applications` `w-full`, switch cru
  "Módulo ativo" com valor do banco, auditoria `editar_modulo` e reload após salvar.
- **Chamadas restauradas nos 6 módulos + imports**:

  | Módulo | Chamada | Local |
  |:---|:---|:---|
  | Auditoria | `campo_modulo(usuario_logado, "auditoria")` | `mod_auditoria/telas.py:570` |
  | Blog | `campo_modulo(usuario_logado, "blog")` | `mod_blog/telas.py:417` |
  | Editor de PDF | `campo_modulo(usuario_logado, "editar_pdf")` | `mod_edit_pdf/telas.py:927` |
  | Gestão de Usuários | `campo_modulo(ator, "usuarios")` | `mod_gest_cad_usuario/telas.py:705` |
  | Renomeador de Empenhos | `campo_modulo(usuario_logado, "empenhos")` | `mod_renomear_empenho/telas.py:951` |
  | Solicitação de Impressão | `campo_modulo(usuario_logado, "solicita_impressao")` | `mod_solicita_impressao/telas.py:986` |

- **`mod_edit_pdf/telas.py` voltou byte-idêntico ao HEAD** (a migração anterior já o havia
  padronizado; a restauração apenas recolocou a chamada).
- **Testes**: `test/verifica_ui_comum.py` — 165 → **179 verificações** (+14: seção 23
  "campo_modulo: restaurado (fonte)" `:1073` + "campo_modulo: stub byte-idêntico" `:1096`;
  corrigidas 3 checagens que afirmavam a remoção).

#### Robustez do APLICAR e restore das páginas nativas (06/09)

- **Fallback de entrada não numérica em `aplicar_gerais`** (`tela_configuracoes.py:351-368`): os campos numéricos do card "Configurações gerais do sistema" — "Intervalo de backup (horas)", "Retenção de sessão (dias)" e "Tempo de exibição dos avisos (segundos)" — envolvem o `int(...)` em `try/except (TypeError, ValueError)`: entrada não numérica (ex.: `"abc"`) cai no **padrão codificado** (12 / 50 / 10), o mesmo contrato já aplicado ao `aviso_timeout`. Antes, um `ValueError` derrubava o APLICAR no meio (sem toast nem recarregamento — salvamento parcial).
- **`restaurar_paginas_padrao` corrigido** (`tela_configuracoes.py:1360-1417`): os dois SELECTs de renumeração (`COALESCE(MAX(ordem)...)` e `SELECT chave ... nativo=0`) agora usam **cursor** (`_cur_max = conn.execute(...)` + `fetchone()`, `_cur_nativos = conn.execute(...)` + `fetchall()`). Antes chamavam `fetchone`/`fetchall` direto no `sqlite3.Connection` → `AttributeError` — o restore das páginas nativas **sempre falhava** (apenas log de erro + toast negativo).
- **Docstring de `aplicar_gerais`** no padrão EN+PT-BR, mencionando o fallback de entrada inválida (`tela_configuracoes.py:351-368`).
- **Novo teste standalone** `test/teste_aba_config_intranet.py`: renderiza a tela real `/configuracoes` headless (NiceGUI offline, `asyncio.run`) e valida a aba Config campo a campo — ativação (existe/habilitado/editável; BASE_DIR readonly), valores iniciais do `tb_config`, APLICAR sem editar (anti-zeramento + reconfigura observabilidade + reagenda backups + agenda reload), edição dos 19 campos → gravação nas chaves corretas, validações/saneamento (0 / -3 / 99 / "abc" / "gigante" / cor vazia), "Restaurar padrão" dos 4 cards da aba Config + restore das páginas nativas (aba Módulo), upload de favicon (.ico válido aplica; .png e vazio recusados) e acesso restrito para não-admin. Autocontido: snapshot/restore do `tb_config`, do favicon (`assets/favicon_atual.ico`) e de `tb_modulos`. Registrado em `../AGENTSadf.md` (lista de testes) e em [Testes — Casos](testes_casos/index.md).

#### Aplicar por card — sem botão "APLICAR" geral (06/09)

- **`salvar_tudo()` removido** — substituído por funções de Aplicar POR CARD (`tela_configuracoes.py:263-473`): `aplicar_cores` (`:310`), `aplicar_textos` (`:342`), `aplicar_gerais` (`:351`), `aplicar_icones` (`:370`), `aplicar_smtp` (`:376`), `aplicar_obs` (`:382`), `aplicar_otel` (`:404`) e `aplicar_paginas` (`:412`). Cada card é `card_admin` recolhível (`aberto=False`) com rodapé padrão de 2 botões ("Restaurar padrão" + "Aplicar") exclusivos do card.
- **Helpers do padrão**: `_v()` (`:263` — nunca zera campo fora do estado), `_reload_apos()` (`:277` — recarrega após 1 s), `_aplicar_card()` (`:284` — grava só o card, audita `config_alterada`, notifica e recarrega; falha registra loguru e notifica negativo sem recarregar) e `_aplicar_paginas()` (`:454` — wrapper do card "Páginas do sistema" com avisos de URL não alterada).
- **Card "Cores" renomeado** para **"Configurações de cores"** (`tela_configuracoes.py:492`); Observabilidade dividido em **"Observabilidade e logs (loguru)"** (`:988`) + **"Telemetria OTel — stack local ou servidor dedicado"** (`:1110`).
- **`rodape_salvar_restaurar`** (`ui_comum.py:338`): rótulo padrão do salvar agora é **"Aplicar"** (antes "Salvar"); novo parâmetro `acoes_extra` (tuplas `(rotulo, icone, on_click[, tooltip[, variante]])`, variante default `solido`); row com `flex-wrap` (responsividade mobile). **`card_admin`** (`ui_comum.py:781`) colore o título do card recolhível com a cor de título do módulo (`<prefixo>_cor_titulo` via `ler_tema`, fail-soft → `#212121`) via `header-style`.

## Observabilidade / Logs (loguru)

Novo subsistema central em `mod_intranet/observabilidade.py` (validado com `ast.parse`), ativo no boot e configurável pela administração:

- **API**: `configurar()` (re)cria os sinks conforme `tb_config`; `limpar_todos()` remove todos os `.log`/`.log.zip`; `instalar_excepthook()` captura exceções não tratadas (thread principal e loop assíncrono); `get_logger(modulo)` retorna o logger marcado com o módulo (vai ao arquivo dedicado daquele módulo).
- **Destino**: pasta `logs/` junto ao entrypoint (mesma pasta de `main.py`; no `.exe` gerado por auto-py-to-exe usa o diretório do executável). Console (stderr) conforme `log_console`: `auto` (só via python, nunca no executável), `sempre` (arquivo + terminal) ou `nunca` (só arquivo).
- **Arquivos**: core `intranet_<data>.log` (logs sem módulo explícito) + um arquivo por módulo da lista `MODULOS = ["gest_cad_usuario","blog","edit_pdf","renomear_empenho","auditoria","solicita_impressao"]`.
- **Rotação/retenção**: padrão rotação `"1 month"`, retenção `"4 months"`, compactação `"zip"` (configuráveis).
- **Configurações em `tb_config`** (cartão "Observabilidade e logs" na administração): `log_ativo`, `log_nivel`, `log_rotacao`, `log_retencao`, `log_console` (`auto`/`sempre`/`nunca`), `log_otel_envio` (`1`/`0`), `log_otel_nivel`.
- **Adoção**: todos os módulos rotulam via `get_logger("<modulo>")`; falha na configuração nunca interrompe o boot (tratada em `try/except`).

#### Observabilidade remota e destino de logs (05/09) — endpoint OTLP, stack remota, Grafana

- **Telemetria OTel configurável** (`otel_integracao.py`): `obter_endpoint()` resolve o destino OTLP com prioridade env `OTEL_ENDPOINT` > `tb_config` (`otel_endpoint`, padrão `localhost:4317`) > padrão local; `inicializar_otel(auto_stack=False)` pula Docker/`compose up` e conecta direto (modo servidor dedicado). `obter_info_otel()` reporta o endpoint resolvido.
- **Boot com gate** (`main.py`): `otel_ativo=0` desliga a telemetria; `otel_auto_start_stack=0` usa stack remota (sem gerenciar Docker local); o sync de credenciais Grafana via `docker exec` só roda com stack local (remota usa token/API — Fase 3).
- **Grafana configurável** (`grafana_sync.py`): `obter_grafana_url()` com prioridade env `GRAFANA_URL` > `tb_config` (`grafana_url`, padrão `http://localhost:3000`); health-check, API e status usam a URL resolvida.
- **Bridge loguru→Loki com filtro**: `log_otel_envio=0` mantém o log só local; `log_otel_nivel` define o nível mínimo enviado ao Loki.
- **Seed**: todas as chaves novas estão em `bd_conexao.PADRAO_CONFIG` (propagadas via `INSERT OR IGNORE`, cobrindo bancos existentes).
- **Aviso**: troca de endpoint/`otel_ativo` exige REINICIAR o sistema (endpoint lido no boot); a aba avisa isso na tela.

#### Textos fixos, fundo e padrão de edição (05/09) — exibir vigente, salvar sem zerar, aplicar

- **Restore de Textos corrigido** (`tela_configuracoes.py`): o botão "Restaurar padrão" chamava `restaurargrupo` (inexistente → `NameError`) e gravava chaves com acento (`texto_login_título`) que não existem; agora usa `restaurar_grupo` com as chaves reais via `PADRAO_CONFIG` (fonte única).
- **Salvar sem zerar**: `salvar_tudo` ganhou o helper `_v()` — campo fora do estado mantém o valor vigente do banco em vez de gravar `""` (limpeza intencional continua possível apagando o campo). Vale para textos, cores, SMTP, logs e OTel.
- **`cor_fundo` aplicado de verdade**: o Quasar pinta `.q-page` por cima do `body` e o `/login` usava `bg-blue-grey-10` fixo — por isso o preview mostrava e o módulo não mudava. Agora `layout_tela` pinta `body` + `.q-page` e o `/login` lê `cor_fundo` (teste `teste_boot.py` atualizado para o novo padrão).
- **Padrão de edição das variáveis de design**: toda chave de aparência em `tb_config` tem campo na UI mostrando o valor vigente (`get_config` + pré-carga em `estado_campos`), salva via `salvar_tudo` sem zerar e aplica sem restart (exceções avisadas na tela: endpoint/OTel exigem restart). Cromados fixos (botões brancos do header, `footer bg-grey-8`, badges semânticos) seguem fixos por padrão.

#### Aparência unificada, APLICAR e cards (05/09)

- **Card único "Cores"** com todos os seletores juntos (principal, fundo, botões, texto, tamanho, títulos, fundo/texto dos cards) + **prévia única ao vivo** (`previa()` `@ui.refreshable` lendo do estado: cabeçalho, card e botões refletem os campos antes de salvar, independente da ordem dos cards).
- **"SALVAR TUDO" → "APLICAR"**: grava e recarrega (`ui.navigate.reload`) — cores, tamanhos e botões valem na hora, sem F5 manual.
- **Cards padronizados**: chaves `intranet_cor_fundo_card`/`intranet_cor_texto_card` (+ `intranet_cor_titulo` consumida) e helpers `tema_modulo.estilo_cartao()`/`titulo_cartao()`/`ler_cartao()` aplicados aos cards do login, painel, configurações e diálogos.

#### Padrão próprio do tema de botões — vazio = padrão do módulo (06/09)

- **Regra**: a chave de tema de **botão** do módulo **VAZIA** usa o padrão do PRÓPRIO módulo —
  precedência em `ler_tema` (`tema_modulo.py:94-126`): (1) chave do módulo
  (`<prefixo>_cor_botao`/`cor_texto_botao`/`btn_tamanho`) não vazia → (2) default do parâmetro
(quando o chamador informa) → (3) `PADROES_TEMA` — mapa único com **TODOS os módulos em
   `#000000`** (blog, usuarios, auditoria, editar_pdf, empenhos, solicita_impressao, intranet — a cor
   do intranet; texto `#FFFFFF`, título `#212121`,
   tamanho `medium`). O tema do sistema (`intranet_*` / card **"Botões do sistema"** do painel
  central `/configuracoes`) **NÃO é herdado** por outros módulos; `cor_fundo`, `cor_titulo` e
  `texto_header` seguem a mesma regra (vazio = default).
- **Efeito**: todos os módulos usam a **cor do intranet (`#000000`)** por padrão (`PADROES_TEMA`);
  o override por módulo continua possível no cupê "Aparência" (`bloco_aparencia`) — os inputs
  exibem o valor **resolvido** e o "Restaurar padrão" grava `""` para voltar ao padrão do próprio
  módulo.
- **Rótulos atualizados** ("vazio = padrão do módulo"): `bloco_aparencia` compartilhado
  (`tema_modulo.py:319-322`).
- **Dados**: `PADRAO_CONFIG` não semeia chaves de botão por módulo — instalações novas já iniciam
  com o padrão do próprio módulo (sem seeds por módulo).
- **Teste**: `test/verifica_ui_comum.py` — 190 verificações (seção 15 "ler_tema real: padrão
  próprio do módulo", com os casos a–e: módulo vence o default; módulo vazio NÃO herda do sistema
  (usa default do parâmetro); módulo vazio sem default usa `PADROES_TEMA`; `cor_fundo`/
  `cor_titulo`/`texto_header` não herdam; `intranet` vazio usa o default).

#### Fábrica central de componentes de UI — `ui_comum.py` (05/09)

Novo módulo `mod_intranet/ui_comum.py` — **fábrica central de componentes de UI** que unifica
`tema_modulo.botao` (variantes de tema) com as variantes fixas do painel de configurações, para
que o mesmo dado tenha a mesma aparência em qualquer tela. `mod_intranet` é o módulo base: os
demais `mod_*` devem migrar gradualmente para importar daqui — a intenção é eliminar os hexes
soltos (`#C62828`, `#EF6C00`, `#2E7D32` — 41 ocorrências nos módulos de negócio) e os
`ui.button(...)` crus (136 ocorrências).

- **`CORES`** (`ui_comum.py:37`): paleta semântica única — `primaria` `#1565C0`, `sucesso`
  `#2E7D32`, `alerta` `#EF6C00`, `perigo` `#C62828`, `info` `#00838F`, `neutro` `#455A64`,
  `destaque` `#6A1B9A`, `cinza_escuro` `#37474F`, `titulo` `#212121`, `branco` `#FFFFFF`.
- **`botao(...)`** (`ui_comum.py:51`): fábrica única — variantes `primario` (alias `solido`),
  `secundario` (alias `contorno`), `texto`, `neutro`, `restaurar`, `restaurar_fill`, `perigo` e
  `icone`; `cor` sobrescreve a cor mantendo formato/tamanho; `compacto=True` produz o visual de
  rodapé de diálogo (sem `size=md`/`btn_cls`/sombra); `chave_modulo` seleciona o tema;
  `extra_classes` soma classes; `tooltip` adiciona dica. Variante inválida levanta `ValueError`
  (falha rápida intencional); falha de tema cai nos padrões com warning loguru; falha ao montar
  o elemento registra exception e retorna `None` (fail-soft).
- **`botao_icone(icone, on_click, ...)`** (`ui_comum.py:136`): atalho `variante="icone"` para
  ações de linha de tabela (mover, excluir, abrir).
- **`dialogo_card(titulo, largura, ...)`** (`ui_comum.py:156`): context manager `ui.dialog` +
  `ui.card` (largura `w-[560px]`, `max-h-[90vh]`, estilo `tema_modulo.estilo_cartao`); com
  `titulo` cria rótulo `text-h6` + separador; faz `yield (dlg, card)`.
- **`rodape_dialogo(dlg, acoes)`** (`ui_comum.py:184`): "Cancelar" (`flat no-caps`) + ações
  compactas `(rotulo, on_click[, kwargs])`; itens malformados são ignorados com log de erro.
- **`rodape_salvar_restaurar(salvar, restaurar=None, ...)`** (`ui_comum.py:208`): rodapé dos
  cupês de aparência/módulo ("Restaurar padrão" opcional + Salvar temático).
- **`notificar`**: reexportado de `tema_modulo` (toast com tempo configurável).
- **Delegações (sem mudança visual)**: `tema_modulo.botao()` (`tema_modulo.py:128`) delega a
  `ui_comum.botao` (`solido`→`primario`, `contorno`→`secundario`, `texto`; variante
  desconhecida cai em `primario`); o rodapé do `bloco_aparencia` (`tema_modulo.py:300`) usa
  `rodape_salvar_restaurar`; `_botao_padrao`
  (`tela_configuracoes.py:78`) delega o corpo a `ui_comum.botao` — as 20 chamadas da tela de
  configurações permanecem intactas.
- **Robustez**: `_log()` (`ui_comum.py:23`) via `observabilidade.get_logger("intranet")`; todos
  os pontos de risco (leitura de tema/estilo, montagem do elemento, itens de rodapé) em
  `try/except` com loguru — a renderização nunca derruba a tela.
- **Equivalência visual**: prova byte-a-byte (`test/verifica_ui_comum.py`, 97 verificações) +
  suítes verdes — `test_dashboard` 31/31, autenticação 19/19, tema 18/18 (`test/test_tema.py`),
  config intranet 50/50 (`test/teste_config_intranet.py`).

!!! note "Migração dos módulos (em andamento, gradual)"
    Os módulos `mod_*` ainda usam `ui.button` cru e hexes soltos; a migração para `ui_comum` é
    gradual e por tela — guia passo a passo em [Convenções de Código](convencoes_codigo.md).
    Primeiro módulo de negócio migrado: **Editor de PDF** (06/09 — 10 botões, 32 avisos e
    `CORES`; ver [Análise do Editor de PDF](analise_mod_edit_pdf.md)).

#### Helpers de tela de módulo — `aba_modulo.py` (05/09)

Três helpers novos em `mod_intranet/aba_modulo.py` padronizam os componentes de tela
repetidos entre os módulos — os pilotos foram migrados e a equivalência visual está
comprovada por `test/verifica_ui_comum.py` (97 verificações byte-a-byte):

- **`menu_modulo(itens, valor=None)`** (`aba_modulo.py:77`): barra de abas de menu no
  padrão do Renomeador de Empenhos — `ui.tabs` com classes `w-full` e, para cada item
  `(chave, rotulo, icone)`, um `ui.tab` posicional com **ícone em cima e nome embaixo**
  (sem `inline-label`). `valor=None` ativa o primeiro item; retorna o `ui.tabs` para uso
  em `ui.tab_panels`.
- **`campo_busca(placeholder, on_change=None, *, valor_inicial="", tooltip=None)`**
  (`aba_modulo.py:95`): campo de pesquisa padrão da Gestão de Usuários — `ui.input` com
  props `outlined dense clearable debounce='150'` e classes `w-full grow min-w-[220px]`;
  `tooltip` aplicado somente quando informado. Retorna o `ui.input` criado.
- **`barra_acoes(busca=None, acoes=())`** (`aba_modulo.py:112`): barra branca do padrão
  Gestão de Usuários (`bg-white rounded-lg shadow-sm px-3 py-1`) — com `busca` (dict de
  kwargs de `campo_busca`), renderiza o campo à esquerda (row `width:min(46%, 620px)`)
  seguido dos botões; sem `busca`, os botões ficam alinhados à direita. `acoes` recebe
  tuplas `(rotulo, icone, on_click[, tooltip])` e cada botão é criado por
  `ui_comum.botao` (variante `primario`, `extra_classes="shrink-0"`); itens malformados
  são ignorados com registro loguru (fail-soft — `_botoes_acoes`, `aba_modulo.py:141`).
- **`abas()`** (`aba_modulo.py:57`) permanece para os usos atuais (blog, auditoria) —
  o padrão novo para menus de módulo é `menu_modulo`.

Pilotos migrados:

| Módulo | Mudança | Local |
|:---|:---|:---|
| Renomeador de Empenhos | tabs crus (`ui.tabs()`/`ui.tab()` + dict `_icones`) removidos; usa `menu_modulo` | `mod_renomear_empenho/telas.py:32, 89-98` |
| Gestão de Usuários | input cru da busca removido; usa `campo_busca` | `mod_gest_cad_usuario/telas.py:23, 104-109` |
| Gestão de Usuários | botão "Novo usuário" agora é `ui_comum.botao` com `chave_modulo="usuarios"` — **mudança visual INTENCIONAL**: a cor passa a seguir o tema do módulo (`usuarios_cor_botao`) em vez do `color=primary` da página; ajustável pelo admin na aba Administração do módulo | `mod_gest_cad_usuario/telas.py:110-112` |

!!! note "Teste padrão em `test/`"
    A prova de render `test/prova_botao_tmp.py` foi **removida** e substituída por
    `test/verifica_ui_comum.py` (97 verificações, stub de nicegui, tema fixado via
    monkeypatch sem tocar no banco, equivalência byte-a-byte das variantes/delegações/
    helpers e checagens de fonte dos pilotos). Regra nova: **TODO código de teste fica
    em `test/`** — nunca em `/tmp` (arquivos em `/tmp` se perdem ao reiniciar a máquina).
