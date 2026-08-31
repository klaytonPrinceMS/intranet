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
| `tb_modulos` | id, chave UNIQUE, nome, icone, rota, ativo, nativo — semeada com os 5 módulos nativos | `autenticacao.py:28-55` |

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

`/configuracoes` (exclusiva do `administrador_geral`), gravação única "SALVAR TUDO":

1. Cores primária/fundo, ícone, título + upload de favicon `.ico` ≤1 MB → `assets/favicon_atual.ico` (arquivo vivo: troca vale no próximo F5, sem restart).
2. Textos fixos (login, home, rodapé).
3. Páginas: edita `tb_modulos` dos módulos registrados (nome, ícone, ativação).
4. Registro de novos módulos e limpeza de vínculos órfãos.

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

**Parcial/Pendente:**

- Dashboard mobile-first: grid responsivo implementado (`main.py:111-184` — `flex-wrap`, `max-w-6xl`, cards `min-w-[160px]`); as microinterações / "feedback de 2s via setTimeout" previstas na Fase 1 do PLANO **não foram evidenciadas no código**.

## Observabilidade / Logs (loguru)

Novo subsistema central em `mod_intranet/observabilidade.py` (validado com `ast.parse`), ativo no boot e configurável pela administração:

- **API**: `configurar()` (re)cria os sinks conforme `tb_config`; `limpar_todos()` remove todos os `.log`/`.log.zip`; `instalar_excepthook()` captura exceções não tratadas (thread principal e loop assíncrono); `get_logger(modulo)` retorna o logger marcado com o módulo (vai ao arquivo dedicado daquele módulo).
- **Destino**: pasta `logs/` junto ao entrypoint (mesma pasta de `main.py`; no `.exe` gerado por auto-py-to-exe usa o diretório do executável). Console (stderr) **somente** quando não está congelado (`not getattr(sys,'frozen',False)`); no executável os logs ficam apenas em arquivo.
- **Arquivos**: core `intranet_<data>.log` (logs sem módulo explícito) + um arquivo por módulo da lista `MODULOS = ["gest_cad_usuario","blog","edit_pdf","renomear_empenho","auditoria","solicita_impressao"]`.
- **Rotação/retenção**: padrão rotação `"1 month"`, retenção `"4 months"`, compactação `"zip"` (configuráveis).
- **Configurações em `tb_config`** (cartão "Observabilidade e logs" na administração): `log_ativo`, `log_nivel`, `log_rotacao`, `log_retencao`.
- **Adoção**: todos os módulos rotulam via `get_logger("<modulo>")`; falha na configuração nunca interrompe o boot (tratada em `try/except`).
