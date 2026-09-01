# Intranet Modular — Architecture

> Technical architecture of the Intranet Modular: single entry point (`main.py`), modular packages (`mod_*`), the `criador_bd.py` / `manipulador_bd.py` / `telas.py` pattern, one SQLite (WAL) database per module, centralized audit and the APScheduler jobs (per-module backups, 1-minute cleanups, folder monitor and audit pruning).

---

# Intranet Modular — Arquitetura

> Arquitetura técnica da Intranet Modular: entry point único (`main.py`), pacotes modulares (`mod_*`), padrão `criador_bd.py` / `manipulador_bd.py` / `telas.py`, banco SQLite (WAL) por módulo, auditoria centralizada e agendadores APScheduler (backups por módulo, cleanups de 1 min, monitor de pasta e poda da auditoria).

## Sumário

1. [Visão geral](#visao-geral)
2. [Entry point: `main.py`](#entry-point-mainpy)
3. [Pacotes de módulo (`mod_*`)](#pacotes-de-modulo-mod_)
4. [Padrão interno de um módulo](#padrao-interno-de-um-modulo)
5. [Bancos de dados (um por módulo, WAL)](#bancos-de-dados-um-por-modulo-wal)
6. [Autenticação e sessões](#autenticacao-e-sessoes)
7. [Guarda de página e layout](#guarda-de-pagina-e-layout)
8. [Agendadores (APScheduler)](#agendadores-apscheduler)
9. [Auditoria centralizada](#auditoria-centralizada)
10. [Observabilidade (loguru)](#observabilidade-loguru)
11. [Documentação embutida (`/documentacao`)](#documentacao-embutida-documentacao)
12. [Estrutura de diretórios (Fase 0)](#estrutura-de-diretorios-fase-0)

## Visão geral

```text
┌────────────────────────────── main.py (único entry point) ──────────────────────────────┐
│  inicializar_bancos()  →  verifica telas.py  →  iniciar_agendador()  →  ui.run(8080)     │
└───────────────┬──────────────────────────────────────────────┬──────────────────────────┘
                │                                              │
   ┌────────────▼───────────┐                     ┌────────────▼───────────┐
   │ mod_intranet (núcleo)  │                     │ Módulos de negócio      │
   │ autenticacao · layout  │◄── importa ────────►│ mod_blog, mod_gest_*,   │
   │ conexao_bd · rotinas   │                     │ mod_edit_pdf,           │
   │ observabilidade · etc. │                     │ mod_renomear_*,         │
   └────────────┬───────────┘                     │ mod_auditoria,          │
                │                                 │ mod_solicita_impressao  │
   db_mod_intranet.db (WAL)                       └─────────┬───────────────┘
   tb_auditoria · tb_config · tb_sessoes · tb_modulos        │ cada um com seu
                                                             ▼ db_mod_*.db (WAL)
```

## Entry point: `main.py`

`main.py` (raiz) é o **único ponto de entrada** — a aplicação não possui outro script de inicialização. Fluxo no boot:

1. **`inicializar_bancos()`** (`main.py:16-17`) — cria o banco central e os bancos dos módulos **antes** de qualquer import de módulo (ordem crítica; ver [Configurações](configuracoes.md#bootstrap-inicializar_bancos)).
2. **Valida `telas.py`** — aborta com `RuntimeError` se algum `mod_*` não tiver `telas.py` (`main.py:22-24`).
3. **Prepara favicon** — copia o favicon nativo para `assets/favicon_atual.ico` (arquivo vivo, troca sem restart) (`main.py:42-48`).
4. **Registra as rotas** de página NiceGUI (`@ui.page`) e rotas auxiliares FastAPI (`@app.get`) — ver [Referência de API](api_referencia.md).
5. **`iniciar_agendador()`** (`main.py:323`) — delega ao `rotinas.iniciar_agendador()`.
6. **Observabilidade** — `observabilidade.configurar()` + `instalar_excepthook()` (`main.py:319-321`).
7. **Documentação** — `construir_e_montar_documentacao()` (`main.py:330-331`): build MkDocs `docs/` → `site/` e mount em `/documentacao` (falha nunca derruba o servidor).
8. **`ui.run(...)`** (`main.py:333-339`) — `reload=False`, `show=False`, porta `8080`, `storage_secret` placeholder.

## Pacotes de módulo (`mod_*`)

Cada funcionalidade é um **pacote próprio** na raiz:

| Pacote | Banco | `telas.py` | Papel |
|:---|:---|:---|:---|
| `mod_intranet/` | `db_mod_intranet.db` | ✗ (rotas no `main.py`) | núcleo: autenticação, auditoria, config, layout, rotinas, observabilidade |
| `mod_gest_cad_usuario/` | `db_mod_gest_cad_usuario.db` | ✓ | usuários, perfis, papéis, sessões |
| `mod_blog/` | `db_mod_blog.db` | ✓ | postagens/comentários |
| `mod_edit_pdf/` | `db_mod_edit_pdf.db` | ✓ | edição de PDFs |
| `mod_renomear_empenho/` | `db_mod_renomear_empenho.db` | ✓ | empenhos/FTS5 |
| `mod_auditoria/` | — (lê o central) | ✓ | visualizador da trilha |
| `mod_solicita_impressao/` | `db_mod_solicita_impressao.db` | ✓ | solicitação de impressão |

Subpacotes/fluxos relevantes do núcleo:

- `mod_intranet/autenticacao.py` — login/sessões/permissões (bcrypt, `tb_sessoes`, `tb_modulos`).
- `mod_intranet/layout_tela.py` — guarda `pagina_restrita` + layout de 4 partes.
- `mod_intranet/conexao_bd.py` — camada mais baixa (banco central, `get_config`/`set_config`).
- `mod_intranet/manipulador_bd.py` — auditoria (`audit_log`) e rastreabilidade.
- `mod_intranet/rotinas.py` — agendadores e backups.
- `mod_intranet/observabilidade.py` — loguru por módulo.
- `mod_intranet/tela_configuracoes.py` — personalização (`/configuracoes`).
- `mod_intranet/documentacao.py` — build/mount do MkDocs.
- `mod_intranet/contexto.py` — ContextVar com IP/UA por request.
- `mod_intranet/email_util.py` — SMTP (cartão E-mail).
- `mod_intranet/dialogo_backup.py` — diálogo de backup do header.
- `mod_intranet/aba_modulo.py` — cabeçalho/abas padronizadas das telas.

## Padrão interno de um módulo

```text
mod_<nome>/
  __init__.py
  telas.py            # OBRIGATÓRIO: expõe mostrar_tela(usuario_logado, perfil)
  manipulador_bd.py   # acesso ao db_mod_<nome>.db (WAL) — criador vigente das tabelas
  criador_bd.py       # LEGADO/MORTO: aponta para o banco central — NÃO confiar nem executar
  (outros: monitor, organizador, src/...)
```

| Arquivo | Responsabilidade |
|:---|:---|
| `telas.py` | UI NiceGUI; `mostrar_tela(usuario_logado, perfil)`; revalida papel antes de qualquer escrita |
| `manipulador_bd.py` | schema (`init_db*`), queries e regras de negócio; conexão WAL; auditoria via `audit_log` |
| `criador_bd.py` | **legado/morto** em todos os módulos — usa a conexão do banco central e esquemas divergentes; nunca executar (o padrão real é `manipulador_bd.init_db*`) |

Exceção: `mod_auditoria` **não tem** `manipulador_bd.py` — lê `tb_auditoria` via `get_connection()` do núcleo (é somente-leitura).

## Bancos de dados (um por módulo, WAL)

- Cada banco é um **arquivo SQLite separado** na raiz (`db_mod_*.db`).
- Toda conexão aplica `PRAGMA journal_mode=WAL` + `synchronous=NORMAL`.
- **Convenção:** consultar um banco somente pelo `manipulador_bd` do seu próprio módulo (evitar cross-query). Exceção conhecida e documentada: a limpeza cruzada LGPD da exclusão de usuário (`mod_gest_cad_usuario` varre bancos vizinhos para anonimizar/excluir dados — ver [Módulo de Gestão de Usuários](modulos/gest_cad_usuario.md)).
- O banco **central** (`db_mod_intranet.db`) é o único compartilhado: `tb_auditoria`, `tb_config`, `tb_sessoes`, `tb_modulos`.

## Autenticação e sessões

- **bcrypt** para hash de senhas (`autenticar` — `autenticacao.py:179`).
- Login grava **sessão revogável** em `tb_sessoes` com `cookie_hash = sha256(...)[:16]` via `secrets` (`registrar_login` — `autenticacao.py:224`); cookie HTTP-Only definido no nível de framework (NiceGUI/Starlette).
- Guarda de página revalida a sessão a cada request (`sessao_ativa` — `autenticacao.py:257`); sessão encerrada pelo admin derruba o navegador na próxima interação.
- **Rastreabilidade**: ContextVar do NiceGUI captura IP (prioriza `X-Forwarded-For`), user-agent, rótulo de dispositivo e MAC best-effort (Linux) em cada request (`mod_intranet/contexto.py`).

## Guarda de página e layout

`pagina_restrita(titulo_modulo, chave_modulo)` (`layout_tela.py:29`) é usada por **todas** as rotas de módulos do `main.py`:

1. Sem usuário → redireciona `/login`.
2. Revalida existência/situação ativa do usuário no banco.
3. Revalida `sessao_ativa` (sessões antigas sem hash são adotadas).
4. Valida `validar_acesso_modulo(nome, chave)` — sem permissão: audita `acesso_negado`, notifica e redireciona `/`.
5. Monta o **layout de 4 partes**: header (hambúrguer, backup, "Meu Perfil", badge de perfil, logout), drawer lateral (módulos liberados), rodapé com versões, área principal.
6. Se `precisa_trocar_senha`, abre o diálogo persistente de troca obrigatória.

## Agendadores (APScheduler)

`rotinas.iniciar_agendador()` (`mod_intranet/rotinas.py:176-232`) — `BackgroundScheduler(daemon=True)`:

| Job | Intervalo | Descrição |
|:---|:---|:---|
| `backup:<chave>` (1 por módulo) | `backup_horas:<chave>` (default **12 h**, mín. 1 h) | copia o banco do módulo para `backup/`, retendo as **10 cópias mais recentes**; reagendável sem restart (`reagendar_backup`) |
| `cleanup_pdf` | **1 min** | expira arquivos do editor PDF (`expirar_antigos(cfg_expiracao_min())`, default 10 min); fallback `limpar_editor_pdf(minutos=10)` |
| `cleanup_solicita` | **1 min** | remove rascunhos de impressão não confirmados e impressos vencidos do servidor |
| `poda_auditoria` | **24 h** | remove registros de `tb_auditoria` mais antigos que `auditoria_retencao_dias` (default 90) |
| `monitor_empenho` | `empenhos_monitor_intervalo_seg` (default **10 s**) | varredura automática da pasta monitorada de empenhos (`rodar_monitor("sistema")`) |

> **Ajuste fino:** o `MAPA_BACKUPS` (`rotinas.py:16-22`) controla quais bancos são copiados em cada job de backup (intranet, usuarios, blog, editar_pdf, empenhos).

## Auditoria centralizada

- **`audit_log(usuario, modulo, acao, descricao, hash_arquivo, ip, user_agent)`** (`mod_intranet/manipulador_bd.py:66-95`) é a função única de escrita na `tb_auditoria`.
- Todos os módulos auditam suas ações relevantes: criação/edição/exclusão, autenticação (login/logout/falha), configurações, permissões (inclusive `acesso_negado`), operações com arquivos (com **hash SHA-256**).
- Colunas de rastreabilidade (`ip`, `user_agent`) vêm da migração `garantir_rastreabilidade()` (`manipulador_bd.py:24-63`), que também cria índices (`modulo`, `usuario`, `timestamp`).
- Visualização: módulo `mod_auditoria` (só `administrador_geral`) — ver [Módulo de Auditoria](modulos/auditoria.md).

## Observabilidade (loguru)

- `mod_intranet/observabilidade.py` configura sinks de arquivo em `logs/` com rotação/retenção/compressão e captura exceções não tratadas (`excepthook`).
- Console (stderr) **somente** quando não está congelado (`sys.frozen`); no executável, logs vão só para arquivo.
- `get_logger("<modulo>")` rotula o logger para o arquivo dedicado (`blog_<data>.log`, ...); core em `intranet_<data>.log`.
- Configurável em runtime pela administração (`log_ativo`, `log_nivel`, `log_rotacao`, `log_retencao`).

## Documentação embutida (`/documentacao`)

- `mod_intranet/documentacao.py` executa `python -m mkdocs build` (docs/ → site/) e monta `site/` como rota estática FastAPI (`app.mount("/documentacao", StaticFiles(...))`).
- O build roda no boot (`main.py:330-331`) e **falhas nunca derrubam o servidor** (apenas avisam nos logs).
- Tema do MkDocs: **`readthedocs`** (definido em `mkdocs.yml` — não alterar para `material`).

## Estrutura de diretórios (Fase 0)

Raiz do projeto (scaffold base — Fase 0 do `PLANO.md`):

| Pasta | Finalidade |
|:---|:---|
| `assets/` | recursos estáticos; `favicon_atual.ico` é o "arquivo vivo" do favicon (troca via upload sem restart, cache-busted por `favicon_versao()`) |
| `assets/css/` | estilos CSS customizados do sistema |
| `doc/` | pasta monitorada de empenhos (`_PASTA_MONITORADA_PADRAO` — `mod_renomear_empenho/manipulador_bd.py:23`) |
| `editorPDF/` | arquivos temporários do Editor de PDF (expiração automática, default 10 min) |
| `organizadorPasta/` | saída do organizador físico do renomear empenho (caixas/subpastas — `PASTA_ORGANIZADOR`) |
| `backup/` | backups dos bancos por módulo (APScheduler, retenção das 10 cópias mais recentes — `PASTA_BACKUP` em `mod_intranet/rotinas.py`) |
| `quarentena/` | PDFs com erro de leitura/corrupção na fila de quarentena (`PASTA_QUARENTENA`) |
| `logs/` | arquivos de log por módulo (loguru — rotação/retenção/compressão) |
| `site/` | build estático do MkDocs (`docs/` → `site/`), servido em `/documentacao` |
| `mod_*/` | núcleo `mod_intranet/` + módulos de negócio (`telas.py` obrigatório) |
| `main.py`, `requirements.txt`, `mkdocs.yml`, `db_mod_*.db` | entry point único, dependências, build da doc e bancos SQLite (WAL) por módulo |

> Pastas operacionais (`backup/`, `organizadorPasta/`, `quarentena/`) são criadas com `.gitkeep`
> no repositório e também garantidas em runtime pelas rotinas (`os.makedirs(..., exist_ok=True)`);
> `doc/`, `editorPDF/`, `logs/` e `site/` são criados/geridos em runtime pelo aplicativo.

> Pendências conceituais conhecidas: `criador_bd.py` legado em todos os módulos (não confiar); `manipulador_bd.py` do núcleo foi reconstruído de `*.pyc` quando ausente como fonte (ver [Análise do Núcleo](analise_mod_intranet.md)).