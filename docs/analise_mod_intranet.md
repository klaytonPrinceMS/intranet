# Núcleo — `mod_intranet`

> Core module: routes `/`, `/login`, `/configuracoes` · central database `db_mod_intranet.db` (unified WAL audit, config, sessions, module registry) · revocable sessions · 4-part layout · centralized observability (loguru).

---

# Núcleo — `mod_intranet`

> Módulo central: rotas `/`, `/login`, `/configuracoes` · banco central `db_mod_intranet.db` (auditoria unificada em WAL, configurações, sessões e cadastro de módulos) · sessões revogáveis · layout de 4 partes · observabilidade centralizada (loguru).

## Propósito

Pacote núcleo que centraliza tudo o que os módulos compartilham: banco central (auditoria unificada LGPD, configurações, sessões e cadastro de módulos), autenticação com sessões revogáveis, layout padrão de 4 partes com guarda de página, rotinas agendadas (backup por módulo + expiração do editorPDF) e a tela de personalização `/configuracoes`. Não possui `telas.py` próprio — suas telas (`layout_tela`, `tela_configuracoes`, `dialogo_backup`) são montadas pelas rotas de `main.py`.

## Banco central `db_mod_intranet.db`

Toda conexão executa `PRAGMA journal_mode=WAL` + `synchronous=NORMAL` (`conexao_bd.py:29-30`). Tabelas criadas por `init_db()` (`conexao_bd.py:34-77`), chamada pelo bootstrap `inicializar_bancos()` **antes** da importação de qualquer módulo:

> ⚠️ **Reconstrução do núcleo**: `conexao_bd.py`, `manipulador_bd.py` e `dialogo_backup.py` estavam **ausentes como fonte** (restavam só `*.pyc` em `__pycache__`) e foram reconstruídos fielmente a partir do bytecode. Em caso de divergência de comportamento esperada, comparar com o `*.pyc` correspondente (ou `gh-pages`). `manipulador_bd.py` central expõe `get_intranet_conn`, `garantir_rastreabilidade`, `audit_log`, `hash_arquivo`; `conexao_bd.py` expõe `get_connection`, `get_config`, `set_config`, `init_db`, `favicon_versao`, `DB_PATH`, `PADRAO_CONFIG`.

| Tabela | Conteúdo | Criada em |
|:---|:---|:---|
| `tb_auditoria` | id, usuario, modulo, acao, descricao, timestamp, hash_arquivo + colunas `ip`/`user_agent` (migração `garantir_rastreabilidade`) | `conexao_bd.py:38-47` |
| `tb_config` | chave PK / valor — seeds: `versao_sistema=1.0.260827`, `cotadisco_global_gb=10`, `backup_interval_hours=12` (legada) e padrões de aparência | `conexao_bd.py:49-74` |
| `tb_sessoes` | id, usuario, modulo, login/logout_timestamp, cookie_hash + `ip`, `user_agent`, `dispositivo`, `mac` | `conexao_bd.py:55-63` |
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

`/configuracoes` (exclusiva do `administrador_geral`), organizada no padrão **menu_mod de abas** (mesmo padrão da Gestão de Usuários): barra com 5 abas à esquerda e botão "SALVAR TUDO" à direita (`tela_configuracoes.py:189-198`).

| Aba | Ícone | Conteúdo |
|:---|:---|:---|
| Config | `tune` | Cores e ícone (color_input, ícone Material, nome do sistema, favicon `.ico` ≤1 MB) + Textos fixos (login, home, rodapé) + Configurações gerais (backup horas, retenção de sessão, pasta raiz) |
| E-mail | `mail` | SMTP: servidor, porta, usuário, remetente, senha, TLS + "Testar conexão SMTP" |
| Módulo | `extension` | Páginas do sistema (lista ÚNICA reordenável com ↑/↓, nome/ícone/ativa por módulo; indispensáveis destacados) + registro de módulos e vínculos órfãos |
| Observabilidade | `query_stats` | Logs loguru: ativo, nível mínimo, rotação, retenção + "Limpar TODOS os logs" |
| Documentação | `menu_book` | Rebuild MkDocs para `/documentacao` + abrir em nova aba |

Cada aba tem seu próprio botão "SALVAR <aba>" (helper `botao_salvar_aba`, `tela_configuracoes.py:177-184`) que chama o **mesmo** `salvar_tudo` do botão "SALVAR TUDO" (`tela_configuracoes.py:98-175`); a aba "Documentação" não precisa salvar por ser ação única (reconstruir). A persistência grava em `tb_config` (`cor_principal`, `texto_*`, `smtp_*`, `log_*`, `backup_interval_hours`, `sessao_retencao`) e em `tb_modulos` (nome/ícone/ativo).

`dialogo_backup.abrir_dialogo()` (botão no header do módulo, para quem pode gerenciar): intervalo em horas salvo + reagendado ao vivo, "Fazer backup agora" e grade das cópias retidas.

## Versionamento no rodapé — `layout_tela._montar_layout`

O rodapé mostra as versões **da esquerda para a direita**: 1ª a versão global do sistema (`v{versao_sistema}`), e quando o usuário está dentro de um módulo (`chave_modulo`), 2ª a versão **individual do módulo atual** (`v{versao_modulo:<chave>}`). Sem módulo específico (Dashboard/Configurações) aparece só a global. A versão individual é lida de `tb_config` (chave `versao_modulo:<chave>`, mesmo estilo `1.0.AAMMDD`) com fallback `1.0` quando o módulo ainda não versionou. Ex.: `/edit-pdf` mostra `v1.0.260822` (sistema) + `v1.0.260827` (mod_edit_pdf).

**Seed centralizado**: `versao_modulo:<chave>` é semeada para os 5 módulos (`usuarios`, `auditoria`, `editar_pdf`, `empenhos`, `blog`) em `conexao_bd.init_db()` com `INSERT OR IGNORE` — idempotente, não sobrescreve edição manual. Para refletir numa base existente, chame `init_db()` novamente.

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
- **`btn_cls(tamanho)` / `btn_style(cor_botao, cor_texto)`**: funções puras de classe/estilo.
  Garantem a regra de **uniformidade** — todos os botões de uma mesma tela usam **sempre a mesma
  cor/tamanho** (por construção, via o mesmo `_btn_style`/`_btn_cls` da tela e o mesmo prefixo).
- **`bloco_aparencia(usuario_logado, chave, tema)`**: cupê "Aparência" padronizado da aba
  Administração (cor do botão, cor do texto, fundo, títulos, tamanho e texto do cabeçalho), **com
  botão Salvar próprio** e "Restaurar padrão", gravando via `salvar_tema` e audita.
- **`campo_modulo(usuario_logado, chave)`**: cupê "Edição do módulo" que permite ao
  administrador alterar **nome de exibição, ícone e status (ativo/inativo)** do módulo em
  `tb_modulos` — hoje também disponível no painel central `/configuracoes`.

**Adoção**: `edit_pdf` e `solicita_impressao` usam `bloco_aparencia` + `campo_modulo`; os demais
módulos (`blog`, `usuarios`, `auditoria`, `empenhos`) usam `campo_modulo`. A regra de
uniformidade e o helper são cobertos por `test/test_tema.py` (18 verificações standalone).

## Pontos de atenção

- Bootstrap: `inicializar_bancos()` roda antes de qualquer import de módulo (`main.py:15-16`) — ordem crítica.
- O PLANO cita `mod_intranet_criador_bd.py` e `mod_intranet_auditoria.py`: esses arquivos **não existem** — quem cria as tabelas é `conexao_bd.init_db()` e quem audita é `manipulador_bd.audit_log()`.
- `storage_secret` do `ui.run` é placeholder hardcoded ("...mude-isto") — trocar antes de produção.
- `backup_interval_hours` é semente legada; os jobs usam apenas `backup_horas:<modulo>`. `sessao_retencao` não tem campo na UI.
- MAC via ARP não funciona neste host Windows (comandos Linux) — coluna fica nula.

## Status — Fase 1 do PLANO.md

**Implementado:**

- Banco central `db_mod_intranet.db` em modo **WAL** + `tb_auditoria` unificada (rastreabilidade IP/UA/dispositivo/MAC via `garantir_rastreabilidade`).
- Auditoria centralizada: `manipulador_bd.audit_log` registra config/auth/permissões/acessos de todos os módulos.
- Visibilidade de módulos por permissão (drawer lateral com alerta de módulo inativo/removido).
- Login com sessão registrada em banco (`registrar_login`) + **sessões revogáveis**: `cookie_hash` via `secrets`, revalidação a cada request (`sessao_ativa`), logout próprio preserva as demais sessões do usuário.
- Gestão de Sessões (ativas + histórico + encerrar) no módulo de usuários; **retenção** do histórico implementada no mecanismo (poda por `sessao_retencao`, default 50/usuário).
- Layout de 4 partes (`layout_tela.pagina_restrita`) com versão no rodapé; área principal carrega o **Blog por padrão** (feed de publicações recentes) — RF-09 **REALIZADO**; a navegação por módulos permanece no drawer lateral.
- Personalização de cor primária/fundo, ícone, título, textos e favicon via `/configuracoes` (gravação única, vale sem restart).
- Edição de Perfil ("Meu Perfil") e troca obrigatória de senha do `master` no 1º login (auto-cura idempotente em boot — `mod_gest_cad_usuario/manipulador_bd.py:136-156`).
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

- **`tela_configuracoes.py:189-198`**: a tela `/configuracoes` deixou de ser um empilhamento de 8 cartões sequenciais com um único "SALVAR TUDO" no topo e passou a usar `ui.tabs` + `ui.tab_panels` (padrão menu_mod, como a Gestão de Usuários): barra com **5 abas** à esquerda e botão **"SALVAR TUDO"** à direita (`tela_configuracoes.py:195-198`).
- **`tela_configuracoes.py:190-194`**: as 5 abas são `Config` (`tune`), `E-mail` (`mail`), `Módulo` (`extension`), `Observabilidade` (`query_stats`) e `Documentação` (`menu_book`).
- **`tela_configuracoes.py:177-184`**: novo helper `botao_salvar_aba(rotulo)` gera o botão "SALVAR <rotulo>" (ex.: "SALVAR Config", "SALVAR E-mail", "SALVAR Observabilidade", "SALVAR Módulos") com o **mesmo handler `salvar_tudo`** do botão "SALVAR TUDO" — cada aba tem seu botão no rodapé dos cartões; a aba "Documentação" não tem salvar por ser ação única (reconstruir).
- **`tela_configuracoes.py:98-175`**: `salvar_tudo` mantido, agora comentado **por aba** (Config → cores/ícone/textos/gerais; E-mail → `smtp_*`; Módulo → `tb_modulos`; Observabilidade → `log_*` + `observabilidade.configurar()`).
- **Conteúdo por aba**: Config reúne Cores e ícone (`tela_configuracoes.py:206-314`, inclui upload de favicon `.ico` ≤1 MB), Textos fixos (`tela_configuracoes.py:316-355`) e Configurações gerais RF-57 (`tela_configuracoes.py:357-400`); E-mail/SMTP RF-58 (`tela_configuracoes.py:402-453`, com "Testar conexão SMTP" em `tela_configuracoes.py:438-447`); Observabilidade (`tela_configuracoes.py:457-501`, com "Limpar TODOS os logs" em `tela_configuracoes.py:490-495`); Documentação (`tela_configuracoes.py:506-528`, rebuild MkDocs + abrir `/documentacao` em nova aba); Módulo (`tela_configuracoes.py:578-865`, páginas do sistema + registro de módulos e vínculos órfãos).
- **Não mudou**: chaves em `tb_config` (`cor_principal`, `texto_*`, `smtp_*`, `log_*`, `backup_interval_hours`, `sessao_retencao`), restrição a `administrador_geral` (`tela_configuracoes.py:59-63`), autenticação e a rota `/configuracoes` em `main.py`.

#### Abas renomeadas e reordenadas (05/09) — Config, E-mail, Módulo, Observabilidade, Documentação

- **`tela_configuracoes.py:190-194`**: as 5 abas foram **renomeadas e reordenadas** — antes `[Config geral, E-mail, Observabilidade, Documentação técnica, Módulo]`, agora **`[Config, E-mail, Módulo, Observabilidade, Documentação]`** (mesmos ícones: `tune`, `mail`, `extension`, `query_stats`, `menu_book`).
- **`tela_configuracoes.py:200-865`**: os `ui.tab_panel` foram renomeados/reordenados no código; a **ordem DOM dos painéis** (Config, E-mail, Observabilidade, Documentação, Módulo) **não coincide mais com a ordem da barra de abas** — o Quasar `q-tab-panels` vincula abas a painéis pelo atributo `name`, então **não há mudança funcional**.
- **`tela_configuracoes.py:251, 347, 397`**: os 3 botões `botao_salvar_aba("Config")` da aba Config (cores/ícone, textos fixos e gerais).
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
  - **`tela_configuracoes.py:593-594`**: `campos_url[chave] = inp_url` ligado em `estado_campos["urls"]` (lido pelo SALVAR TUDO). A tupla `estado_campos["paginas"] = (inp_n, inp_i, sw_a)` é **mantida**.
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

**Parcial/Pendente:**

- Nada pendente nesta fase (Fase 1 concluída — ver item 6 → REALIZADO acima).

## Observabilidade / Logs (loguru)

Novo subsistema central em `mod_intranet/observabilidade.py` (validado com `ast.parse`), ativo no boot e configurável pela administração:

- **API**: `configurar()` (re)cria os sinks conforme `tb_config`; `limpar_todos()` remove todos os `.log`/`.log.zip`; `instalar_excepthook()` captura exceções não tratadas (thread principal e loop assíncrono); `get_logger(modulo)` retorna o logger marcado com o módulo (vai ao arquivo dedicado daquele módulo).
- **Destino**: pasta `logs/` junto ao entrypoint (mesma pasta de `main.py`; no `.exe` gerado por auto-py-to-exe usa o diretório do executável). Console (stderr) **somente** quando não está congelado (`not getattr(sys,'frozen',False)`); no executável os logs ficam apenas em arquivo.
- **Arquivos**: core `intranet_<data>.log` (logs sem módulo explícito) + um arquivo por módulo da lista `MODULOS = ["gest_cad_usuario","blog","edit_pdf","renomear_empenho","auditoria","solicita_impressao"]`.
- **Rotação/retenção**: padrão rotação `"1 month"`, retenção `"4 months"`, compactação `"zip"` (configuráveis).
- **Configurações em `tb_config`** (cartão "Observabilidade e logs" na administração): `log_ativo`, `log_nivel`, `log_rotacao`, `log_retencao`.
- **Adoção**: todos os módulos rotulam via `get_logger("<modulo>")`; falha na configuração nunca interrompe o boot (tratada em `try/except`).
