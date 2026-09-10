# Intranet Modular — System Requirements

> Requirements audit of the Intranet Modular: technical requirements to run the system (Linux/Windows host, Python 3.12, NiceGUI 3.15 with local Tailwind, SQLite WAL, APScheduler, nh3, PDF libraries, bcrypt, loguru, MkDocs `readthedocs`) PLUS the functional requirements per module and the non-functional requirements (security, persistence, local CSS frameworks, loguru, try/except, configurability without restart, responsiveness) — each one with its REAL status verified against the executable code (implemented / partial / not implemented). Nothing aspirational.

---

# Intranet Modular — Requisitos do Sistema

> Auditoria de requisitos da Intranet Modular: requisitos técnicos para rodar o sistema (hospedeiro Linux/Windows, Python 3.12, NiceGUI 3.15 com Tailwind local, SQLite WAL, APScheduler, nh3, bibliotecas de PDF, bcrypt, loguru, MkDocs `readthedocs`) MAIS os requisitos funcionais por módulo e os não funcionais (segurança, persistência, frameworks CSS locais, loguru, try/except, configurabilidade sem restart, responsividade) — cada um com o status REAL verificado no código executável (implementado/parcial/não implementado). Nada aspiracional.

## Sumário

1. [Requisitos técnicos (ambiente)](#requisitos-tecnicos-ambiente)
2. [Requisitos funcionais por módulo (status real)](#requisitos-funcionais-por-modulo-status-real)
3. [Requisitos não funcionais (status real)](#requisitos-nao-funcionais-status-real)
4. [Diagramas](#diagramas)
   - [Fluxo de uso (login → navegação → ações)](#fluxo-de-uso)
   - [Modelo de dados (erDiagram)](#modelo-de-dados)
   - [Estrutura de classes dos módulos (classDiagram)](#estrutura-de-classes)

> Em conflito entre documentação e código, prevalece o **código executável** (`requirements.txt`, `mkdocs.yml`, `main.py`, `mod_*/`). Status verificados por leitura do código em 06/09/2026.

## Requisitos técnicos (ambiente)

| Categoria | Exigência | Status |
|:---|:---|:---:|
| SO | Linux (recomendado) ou Windows | ✅ Implementado |
| Python | **3.12** | ✅ Implementado |
| Framework | **NiceGUI 3.15** (`ui.run` com `reload=False`, `show=False`, porta `8080` — `main.py:471-478`) | ✅ Implementado |
| Banco | SQLite (stdlib) em **modo WAL** (`PRAGMA journal_mode=WAL` em toda conexão) | ✅ Implementado |
| UI | Tailwind CSS servido localmente pelo NiceGUI (**sem CDN**) | ✅ Implementado |
| Internet | necessária apenas na instalação das dependências; em operação, o sistema roda **sem internet** (rede interna) | ✅ Implementado |
| OCR (opcional) | binário **Tesseract** no SO (`apt install tesseract-ocr`, `por+eng`) — usado no fallback de extração de empenhos escaneados | ⚠️ Opcional (degrada para quarentena sem ele) |

### Dependências Python

Fonte: `requirements.txt` (raiz).

| Dependência | Versão mínima | Uso |
|:---|:---|:---|
| `nicegui` | `3.15.0` | framework web (páginas, componentes, Tailwind local) |
| `apscheduler` | `>=3.10,<4` | agendadores (backups, cleanups, monitor de pasta, poda) |
| `nh3` | `>=0.2` | sanitização HTML do Blog (gravação e renderização) |
| `pdfplumber` | `>=0.11` | extração de texto de PDF (fallback) |
| `pikepdf` | `>=9.0` | manipulação PDF (metadados, redução leve) |
| `pymupdf` | `>=1.24` | extração de texto, contagem de páginas, rasterização |
| `pytesseract` | `>=0.3` | OCR de PDFs escaneados (requer binário `tesseract` no SO) |
| `pypdf` | `>=5.0` | manipulação PDF (redução leve/fallback) |
| `bcrypt` | `>=5.0.0` | hash de senhas |
| `loguru` | `>=0.7.3` | observabilidade/logs por módulo |
| `mkdocs` | `>=1.6.1` | build da documentação embutida |
| `mkdocs-material` | `>=9.7.7` | presente no requirements; **o tema ativo é `readthedocs`** (ver `mkdocs.yml`) |

### Armazenamento

- **SQLite** (módulo `sqlite3` da stdlib) — sem servidor externo de banco.
- **Modo WAL obrigatório**: cada conexão executa `PRAGMA journal_mode=WAL` (+ `synchronous=NORMAL` no central/auditoria).
- **Um banco por módulo** na raiz do projeto: `db_mod_intranet.db`, `db_mod_gest_cad_usuario.db`, `db_mod_blog.db`, `db_mod_edit_pdf.db`, `db_mod_renomear_empenho.db`, `db_mod_auditoria.db`, `db_mod_solicita_impressao.db`.
- Pastas de arquivos: na raiz — `assets/` (+ `assets/css/frameworks/`), `backup/`, `logs/` (loguru), `site/` (docs compiladas); **dentro dos módulos** — `mod_edit_pdf/editorPDF/`, `mod_renomear_empenho/doc/` (empenhos), `mod_renomear_empenho/quarentena/`, `mod_renomear_empenho/organizadorPasta/`, `mod_renomear_empenho/downloads/`, `mod_renomear_empenho/datahora_*PDF/`, `mod_renomear_empenho/tmp_ferramentas_pdf/`, `mod_solicita_impressao/solicitacaoImpressao/`.

### Rede e interface

- **Tailwind CSS local**: o NiceGUI embute/serve o `tailwindcss.min.js` localmente — exigência para rede interna.
- **Frameworks CSS embarcados**: Bulma, DaisyUI, Pico e Picnic em `assets/css/frameworks/`, servidos localmente em `/css/frameworks/*` (sem CDN) via `tema_css.montar_rotas_static()` (`main.py:81-85`); injeção **por página** via `tema_css.injetar_framework()` — nunca global.
- **Porta**: `8080` (`main.py:476`).
- **Documentação**: servida na mesma porta em `/documentacao` (build MkDocs `docs/` → `site/`, montado pela própria aplicação — `mod_intranet/documentacao.py`).

## Requisitos funcionais por módulo (status real)

> Numeração herdada do roadmap (`analise.md`/`PLANO.md`); o código executável prevalece. Status verificados no código em 06/09/2026.

### Núcleo (`mod_intranet`) — resumo (detalhe em `analise_mod_intranet.md`)

| Requisito | Situação |
|:---|:---:|
| Login bcrypt + sessão revogável amarrada a cookie (`tb_sessoes` com IP/UA/dispositivo/MAC) | ✅ Implementado |
| Guarda de página `pagina_restrita` (revalida usuário, sessão e permissão a cada request) | ✅ Implementado |
| Troca obrigatória de senha no 1º acesso (diálogo persistente) + "Meu Perfil" (dados + senha) | ✅ Implementado |
| Cadastro de módulos em `tb_modulos` (nome/ícone/rota/ordem/ativo; indispensáveis não desativáveis) | ✅ Implementado |
| URL (slug) de página editável com re-registro ao vivo (`rotas_modulos`) — sem restart | ✅ Implementado |
| Painel central `/configuracoes` (aparência, textos, e-mail/SMTP, módulos, observabilidade, documentação) | ✅ Implementado |
| Backups por módulo (APScheduler, intervalo individual, retenção 10 cópias) | ✅ Implementado |
| Observabilidade loguru (arquivo por módulo, rotação/retenção, console `auto/sempre/nunca`, bridge OTel→Loki) | ✅ Implementado |
| Telemetria OTel (stack local via Docker ou remota; Grafana com sync de credenciais) | ✅ Implementado |
| Documentação embutida `/documentacao` (build MkDocs no boot; falha nunca derruba o servidor) | ✅ Implementado |
| Favicon customizável por upload (arquivo vivo, cache-busting, sem restart) | ✅ Implementado |
| CSS frameworks embarcados locais (`/css/frameworks/*`, injeção por página) | ✅ Implementado |

### Gestão de Usuários (`mod_gest_cad_usuario`)

| Requisito | Situação |
|:---|:---:|
| Soft CRUD completo (criar, editar, renomear, bloquear/restaurar, excluir lógico com motivo, excluir definitivo LGPD) | ✅ Implementado |
| Perfis globais (`comum`, `administrador_modulo`, `administrador_geral`) + papéis por módulo (`tb_acesso_usuario`) | ✅ Implementado |
| Senha provisória com troca obrigatória; política de tamanho mínimo configurável (`usuarios_senha_min`) | ✅ Implementado |
| Nome de exibição/social (Decreto 8.727/2016) usado como tratamento | ✅ Implementado |
| Busca instantânea em todos os campos + palavras-chave de estado (provisório/bloqueado/sessão/excluído) | ✅ Implementado |
| Lista paginada (10/20/50/100), filtros situação/perfil, ordenação A→Z/numérica, exibição compacta com tooltip | ✅ Implementado |
| Duplicar usuário (herda perfil global + acessos por módulo) | ✅ Implementado |
| Sessões ativas: visualização (IP/dispositivo/MAC), encerramento individual/em massa, histórico por usuário | ✅ Implementado |
| Limpeza cruzada LGPD na exclusão definitiva (Blog, editorPDF, empenhos anonimizados; auditoria preservada) | ✅ Implementado |
| Proteções: vedado agir sobre a própria conta; `master` não renomeável/excluível; último admin geral protegido (RF-26) | ✅ Implementado |
| Aba Administração: aparência (`usuarios_*` com padrão próprio do módulo) + `usuarios_senha_min` | ✅ Implementado |
| Geração ALEATÓRIA de senha provisória pelo sistema | ❌ Não implementado (admin digita a senha) |

### Blog (`mod_blog`)

| Requisito | Situação |
|:---|:---:|
| CRUD de postagens com soft delete + publicar/despublicar/republicar | ✅ Implementado |
| Sanitização nh3 na gravação E na renderização, com whitelist configurável (`blog_tags_permitidas`) | ✅ Implementado |
| Aceita `http`/`https`, URLs relativas e `data:` para imagens (`url_schemes`/`url_relative`) | ✅ Implementado |
| Formatação rica: títulos centralizados/negrito, imagens à esquerda com largura configurável, texto justificado | ✅ Implementado |
| Markdown leve (`#`, `**negrito**`, `- item`) convertido para HTML | ✅ Implementado |
| Editor com pré-visualização (criar e editar) | ✅ Implementado |
| Modo de exibição histórico OU publicação única (config local `blog_modo_exibicao`) | ✅ Implementado |
| Gestão de postagens despublicadas com republicar (aba Administração) | ✅ Implementado |
| Somente-leitura para `comum` (UI esconde + backend valida em toda escrita) | ✅ Implementado |
| Comentários (só admins escrevem; leitura para todos) | ✅ Implementado |
| Feed do Blog no dashboard `/` (RF-09) | ✅ Implementado |

### Editor de PDF (`mod_edit_pdf`)

| Requisito | Situação |
|:---|:---:|
| Upload múltiplo com pré-checagem do lote e recusas nominais com motivo | ✅ Implementado |
| Operações: reduzir (leve/agressivo), juntar, cortar, dividir (4 modos), verificar, ZIP, excluir | ✅ Implementado |
| Seleção ordenada (badges "#") respeitada pelo Juntar/Reduzir/Cortar | ✅ Implementado |
| Cotas em 4 níveis (global, por usuário, por lote, estoque de uploads) — todas configuráveis sem restart | ✅ Implementado |
| Expiração automática (job 1 min, critério mtime; devolve cota e audita) + "Expirar agora" | ✅ Implementado |
| Auditoria com SHA-256 (upload e operações; hashes de origem/destino) | ✅ Implementado |
| Menu de contexto por linha (Baixar/Excluir) + downloads individuais | ✅ Implementado |
| Aba Administração (cotas, limites, textos da tela, aparência, manutenção) — só admin geral | ✅ Implementado |

### Renomear Empenhos (`mod_renomear_empenho`)

| Requisito | Situação |
|:---|:---:|
| Extração de texto tolerante a escaneados (`pymupdf → pdfplumber → OCR → pikepdf`) | ✅ Implementado |
| Regex dinâmicas persistidas (`tb_regex_regras`, com `campo_destino` para FTS) — sem restart | ✅ Implementado |
| Campos de busca configuráveis por regex (`tb_campos_busca`: ficha/empenho/parcela/ano…) | ✅ Implementado |
| Tipos especiais EC/EE/EG/AE detectados pelo conteúdo e nomeados (`EC_0024.pdf`…) | ✅ Implementado |
| Renomeação sequencial com template configurável (`{contador}`, `{empenho}`, `{parcela}`…) | ✅ Implementado |
| Monitor multi-pasta (local + rede/UNC), automático (RF-40, intervalo configurável) + manual | ✅ Implementado |
| Quarentena com motivo e reprocessamento (regex aplicada na hora) | ✅ Implementado |
| Pesquisa FTS5 (32 colunas, RF-41) com fallback LIKE | ✅ Implementado |
| Organizador físico (~200 pág/pasta, 4 pastas/caixa configuráveis) + capas/matriz + validação (RF-44) | ✅ Implementado |
| Ferramentas de PDF embutidas: cortar/mesclar/reduzir (RF-45, reusa `mod_edit_pdf`) | ✅ Implementado |
| Solicitações comum→admin (e-mail SMTP central ou ZIP; lotes; recusa com motivo) (RF-39/RF-003) | ✅ Implementado |
| Navegação protegida anti-travessia (só PDFs, raízes monitoradas + organizador) | ✅ Implementado |
| Trilha por arquivo (`tb_arquivos_auditoria` + `tb_eventos_arquivos`) com SHA-256 | ✅ Implementado |
| Tipo especial "EX" (citado na referência standalone) | ❌ Não portado |

### Auditoria (`mod_auditoria`)

| Requisito | Situação |
|:---|:---:|
| Banco exclusivo `db_mod_auditoria.db` com UMA TABELA POR MÓDULO (`tb_auditoria_<modulo>`) | ✅ Implementado |
| Descoberta automática de módulos produtores (navegação dinâmica por tabela) | ✅ Implementado |
| Filtros: usuário (LIKE), módulo/tabela, ação (categorias coloridas + texto livre), hora, intervalo de datas | ✅ Implementado |
| Paginação server-side (`LIMIT ? OFFSET ?`, `auditoria_limite`) | ✅ Implementado |
| Exportação CSV da página corrente (respeita campos/ordem do auditor) | ✅ Implementado |
| Campos/ordem de exibição por auditor (persistido em `auditoria_campos:<usuario>`) | ✅ Implementado |
| Cores por categoria de ação (`CORES_ACAO`) | ✅ Implementado |
| Poda automática diária (`auditoria_retencao_dias`, default 90 — LGPD) | ✅ Implementado |
| Migração idempotente do legado central (`migrar_dados_existentes`) | ✅ Implementado |
| Aba Observabilidade (dashboards Grafana) quando a stack OTel está no ar | ✅ Implementado |
| Acesso exclusivo do `administrador_geral` (RF-35) com `acesso_negado` | ✅ Implementado |

### Solicitação de Impressão (`mod_solicita_impressao`)

| Requisito | Situação |
|:---|:---:|
| Upload múltiplo (até 10 PDFs) com rascunhos expiráveis e contagem regressiva | ✅ Implementado |
| Contagem de páginas (PyMuPDF, fallback pdfplumber) + fórmula de contabilização exata | ✅ Implementado |
| Cotas mensais hierárquicas (secretaria → setor; excedente permitido e marcado) | ✅ Implementado |
| Consumo descontado somente na impressão confirmada; reset manual (e virada de mês por `mes_referencia`) | ✅ Implementado |
| Autorização por responsável vinculado (pode ser usuário `comum`) ou admin do módulo | ✅ Implementado |
| Fluxo de status completo (pendente → aguardando → autorizado → impresso; recusado/cancelado) | ✅ Implementado |
| Impressão dual: JS `printSolicitacao` (impressora padrão A4/A3) ou download com marca d'água | ✅ Implementado |
| Marca d'água configurável (texto com placeholders, posição, opacidade, fonte, cor, rotação) | ✅ Implementado |
| Cadastros: secretarias, setores, responsáveis, cotas (relatório mensal com barras) | ✅ Implementado |
| Configurações: impressoras padrão, aviso de presença, prazos de rascunho/exclusão, padrões do formulário | ✅ Implementado |
| Limpeza automática (job 1 min): rascunhos vencidos + arquivos de impressos vencidos | ✅ Implementado |
| Notificação por e-mail de eventos de cota | ❌ Não implementado (por design — sem SMTP neste fluxo) |

## Requisitos não funcionais (status real)

| Requisito | Evidência no código | Status |
|:---|:---|:---:|
| **Segurança — autenticação** | bcrypt (`autenticacao.py:294-299`); falha de login audita `login_falha`; usuário bloqueado não entra | ✅ |
| **Segurança — sessões revogáveis** | `cookie_hash` sha256+secrets por sessão (`registrar_login`); guarda revalida `sessao_ativa` a cada request; bloqueio/exclusão/redefinição derrubam sessões vivas | ✅ |
| **Segurança — permissões** | `validar_acesso_modulo` no choke point `pagina_restrita` + revalidação do papel dentro de cada tela (dupla camada); `acesso_negado` auditado | ✅ |
| **Segurança — XSS** | nh3 na gravação e renderização do Blog (whitelist configurável); escape em comentários | ✅ |
| **Segurança — anti-travessia** | `pasta_navegavel`/`raizes_navegacao` no renomeador; `_path_real` resolve `..`/`~` | ✅ |
| **Segurança — storage_secret** | placeholder `intranet-secret-2026-mude-isto` em `main.py:474` — **precisa ser trocado em produção** | ⚠️ Parcial (placeholder) |
| **Persistência SQLite/WAL** | `PRAGMA journal_mode=WAL` em todos os bancos; `synchronous=NORMAL` no central/auditoria; um banco por módulo | ✅ |
| **Postgres** | Não há suporte — SQLite apenas (decisão de arquitetura do projeto) | ❌ Não aplicável |
| **Frameworks CSS locais** | `assets/css/frameworks/` servido em `/css/frameworks/*` (Bulma, DaisyUI, Pico, Picnic — sem CDN); injeção por página via `tema_css.injetar_framework()` | ✅ |
| **Loguru padronizado** | `_FMT` com `{module}:{function}:{line}`; arquivo por módulo (`logs/<modulo>_<data>.log`); rotação/retenção/compressão; excepthook global | ✅ |
| **try/except (fail-soft)** | Handlers de UI e acessos a BD protegidos nos módulos; falhas registradas com loguru; renderização nunca derruba a tela | ⚠️ Parcial (pontos legados restantes, ex.: `print` em fallbacks) |
| **Configurabilidade sem restart** | Chaves em `tb_config` (central) e `tb_configuracoes_modulo`/`tb_config` locais; temas, cotas, prazos, pastas, textos e intervalos aplicados a cada leitura; jobs reagendáveis ao vivo | ✅ |
| **Responsividade** | Grids Tailwind fluidos (`grid-cols-1 sm:grid-cols-2 …`), telas em área cheia (`w-full`), cards com `flex-wrap`/`min-w` — 360–1440 px | ✅ |
| **Desempenho — paginação** | Lista de usuários paginada client-side; auditoria com paginação server-side (`LIMIT/OFFSET` + índices); FTS5 para busca textual | ✅ |
| **Desempenho — timers** | Editor PDF atualiza a cada 5 s; auditoria a cada 30 s; limpezas a cada 1 min; monitor de empenhos configurável (padrão 60 s) | ✅ |
| **Retenção LGPD** | Poda diária da auditoria (`auditoria_retencao_dias`); poda de sessões (`sessao_retencao`, padrão 50); exclusão definitiva com limpeza cruzada | ✅ |
| **Backups** | 1 job por módulo (intervalo individual `backup_horas:<chave>`, padrão 12 h), retenção das 10 cópias mais recentes | ✅ |
| **Operação sem internet** | Tailwind/frameworks locais; sem CDN; documentação embutida | ✅ |
| **Auditoria com hash** | SHA-256 em operações com arquivos (editor PDF, empenhos, impressão) | ✅ |

## Diagramas

### Fluxo de uso

```mermaid
flowchart TD
    A[Navegador] -->|GET /login| B[Página de Login]
    B -->|usuário + senha| C[autenticar<br/>bcrypt + usuário ativo?]
    C -->|falha| B
    C -->|ok| D[registrar_login<br/>tb_sessoes + cookie_hash]
    D --> E[Dashboard /<br/>boas-vindas + resumo admin + feed do Blog]
    E --> F{Menu lateral<br/>módulos liberados}
    F --> G[/blog]
    F --> H[/users]
    F --> I[/edit-pdf]
    F --> J[/renomear-empenho]
    F --> K[/solicita-impressao]
    F --> L[/auditoria<br/>só admin geral]
    G & H & I & J & K & L --> M[pagina_restrita<br/>revalida usuário + sessão + permissão]
    M -->|sem permissão| N[acesso_negado + volta ao /]
    M -->|ok| O[Ações do módulo<br/>CRUD · operações · configurações]
    O --> P[audit_log<br/>db_mod_auditoria.db<br/>tb_auditoria_&lt;modulo&gt;]
    O --> Q[notificar<br/>toast com notificacao_timeout]
    E -->|logout| R[registrar_logout + /login]
```

### Modelo de dados

```mermaid
erDiagram
    tb_config {
        TEXT chave PK
        TEXT valor
    }
    tb_sessoes {
        INTEGER id PK
        TEXT usuario
        TEXT modulo
        DATETIME login_timestamp
        DATETIME logout_timestamp
        TEXT cookie_hash
        TEXT ip
        TEXT user_agent
        TEXT dispositivo
        TEXT mac
    }
    tb_modulos {
        INTEGER id PK
        TEXT chave UK
        TEXT nome
        TEXT icone
        TEXT rota
        INTEGER ativo
        INTEGER nativo
        INTEGER ordem
    }
    tb_usuarios {
        INTEGER id PK
        TEXT user_nome UK
        TEXT user_senha
        TEXT user_email
        TEXT user_fone
        TEXT user_perfil
        INTEGER user_ativo
        DATETIME data_cadastro
        INTEGER user_deletado
        TEXT user_nome_completo
        TEXT user_motivo_exclusao
    }
    tb_acesso_usuario {
        INTEGER id PK
        TEXT user_nome FK
        TEXT modulo_chave
        TEXT papel
        TEXT liberado_por
        DATETIME data_liberacao
    }
    tb_postagens {
        INTEGER id PK
        TEXT titulo
        TEXT conteudo
        TEXT autor
        DATETIME data_criacao
        DATETIME data_atualizacao
        INTEGER ativo
    }
    tb_comentarios {
        INTEGER id PK
        INTEGER postagem_id FK
        TEXT autor
        TEXT conteudo
        DATETIME data_criacao
    }
    tb_arquivos {
        INTEGER id PK
        TEXT nome_arquivo
        TEXT usuario
        INTEGER tamanho_bytes
        TEXT operacao
        DATETIME data_operacao
        INTEGER ativo
    }
    tb_cota_disco {
        TEXT usuario PK
        INTEGER total_usado_bytes
        DATETIME atualizado_em
    }
    tb_empenhos {
        INTEGER id PK
        TEXT nome_arquivo_original
        TEXT nome_arquivo_final
        INTEGER numero_empenho
        INTEGER parcela
        TEXT tipo_especial
        TEXT ficha
        TEXT ano
        TEXT usuario
        TEXT status
        TEXT caminho_arquivo
    }
    tb_quarentena {
        INTEGER id PK
        TEXT nome_arquivo
        TEXT motivo
        TEXT caminho_atual
        INTEGER processado
    }
    tb_regex_regras {
        INTEGER id PK
        TEXT nome_regra UK
        TEXT padrao_regra
        TEXT campo_destino
        INTEGER ativo
    }
    tb_campos_busca {
        INTEGER id PK
        TEXT campo UK
        TEXT rotulo
        TEXT padrao_regra
        INTEGER ativo
    }
    tb_arquivos_auditoria {
        INTEGER id PK
        TEXT nome_original
        TEXT nome_renomeado
        TEXT numero_empenho
        TEXT status
        TEXT hash_sha256_origem
        TEXT hash_sha256_destino
        TEXT usuario
    }
    tb_eventos_arquivos {
        INTEGER id PK
        INTEGER arquivo_id FK
        TEXT tipo
        TEXT detalhe
        TEXT usuario
        DATETIME timestamp
    }
    tb_solicitacoes_emp {
        INTEGER id PK
        INTEGER empenho_id FK
        TEXT arquivo_caminho
        TEXT solicitante_email
        TEXT status
        TEXT lote_id
        TEXT metodo_envio
        TEXT caminho_zip
        TEXT motivo_recusa
    }
    tb_solicitacoes_imp {
        INTEGER id PK
        TEXT usuario_solicitante
        TEXT arquivo_servidor
        TEXT hash_arquivo
        INTEGER qtd_copias
        TEXT tamanho_papel
        TEXT cor
        INTEGER frente_verso
        INTEGER secretaria_id FK
        INTEGER setor_id FK
        INTEGER paginas_contabilizadas
        TEXT status
        INTEGER cota_excedida
        TEXT autorizado_por
        TEXT impresso_por
        DATETIME excluir_arquivo_em
    }
    tb_secretarias {
        INTEGER id PK
        TEXT nome
        TEXT sigla
        INTEGER cota_paginas_mensal
        INTEGER ativo
    }
    tb_setores {
        INTEGER id PK
        TEXT nome
        INTEGER secretaria_id FK
        INTEGER cota_paginas_mensal
        INTEGER ativo
    }
    tb_responsaveis_autorizacao {
        INTEGER id PK
        TEXT user_nome
        INTEGER secretaria_id FK
        INTEGER setor_id FK
        INTEGER ativo
    }
    tb_cotas_impressao {
        INTEGER id PK
        INTEGER secretaria_id FK
        INTEGER setor_id
        INTEGER cota_paginas
        TEXT mes_referencia
    }
    tb_consumo_cota {
        INTEGER id PK
        INTEGER secretaria_id FK
        INTEGER setor_id
        TEXT mes_referencia
        INTEGER paginas_usadas
    }
    tb_auditoria_modulo {
        INTEGER id PK
        TEXT usuario
        TEXT modulo
        TEXT acao
        TEXT descricao
        TEXT hash_arquivo
        TEXT ip
        TEXT user_agent
        TEXT client_hostname
        DATETIME timestamp
    }
    tb_auditoria_meta {
        TEXT modulo PK
        TEXT nome
        TEXT criada_em
    }

    tb_usuarios ||--o{ tb_acesso_usuario : "user_nome"
    tb_postagens ||--o{ tb_comentarios : "postagem_id (CASCADE)"
    tb_empenhos ||--o{ tb_eventos_arquivos : "arquivo_id (via auditoria)"
    tb_arquivos_auditoria ||--o{ tb_eventos_arquivos : "arquivo_id (CASCADE)"
    tb_empenhos |o--o| tb_solicitacoes_emp : "empenho_id"
    tb_secretarias ||--o{ tb_setores : "secretaria_id (CASCADE)"
    tb_secretarias ||--o{ tb_responsaveis_autorizacao : "secretaria_id (CASCADE)"
    tb_setores ||--o{ tb_responsaveis_autorizacao : "setor_id (CASCADE)"
    tb_secretarias ||--o{ tb_solicitacoes_imp : "secretaria_id (SET NULL)"
    tb_setores |o--o{ tb_solicitacoes_imp : "setor_id (SET NULL)"
    tb_secretarias ||--o{ tb_cotas_impressao : "secretaria_id (CASCADE)"
    tb_secretarias ||--o{ tb_consumo_cota : "secretaria_id"
    tb_auditoria_meta ||--|| tb_auditoria_modulo : "uma tabela por módulo"
```

> Notas: `tb_config` (central) e as `tb_config` locais (blog) / `tb_configuracoes_modulo` (impressão) são tabelas chave-valor sem FK. `tb_auditoria_modulo` representa o padrão `tb_auditoria_<modulo>` (uma tabela física por módulo produtor, em `db_mod_auditoria.db`). `tb_indexador_pesquisa_fts5` (32 colunas) é uma virtual table FTS5 alimentada por `reindexar_empenho()` — omitida do diagrama por ser derivada de `tb_empenhos` + texto extraído.

### Estrutura de classes

O projeto é **funcional/procedural** — não há classes de domínio. O "modelo de classes" real é o padrão de pacote por módulo, mais as duas únicas classes do código:

```mermaid
classDiagram
    class main_py["main.py (entry point)"] {
        +page_login()
        +page_dashboard()
        +page_blog() / page_users() / page_auditoria()
        +page_edit_pdf() / page_renomear_empenho()
        +page_solicita_impressao() / page_configuracoes()
        +baixar_pdf_impressao(solicitacao_id) FileResponse
        +iniciar_agendador()
    }
    class ModuloNegocio["mod_<nome> (padrão de pacote)"] {
        +telas.py : mostrar_tela(usuario_logado, perfil)
        +manipulador_bd.py : init_db*() / queries / regras
        +criador_bd.py : LEGADO (não usar)
    }
    class ManipuladorBD["db_manipulador.py"] {
        +get_connection() Connection
        +init_db*() void
        +listar*/criar*/editar*/excluir*()
        -_log() Logger
        -_audit(ator, acao, alvo)
    }
    class Telas["telas.py"] {
        +mostrar_tela(usuario_logado, perfil)
        -_dlg_*() Dialog
        -_painel_*() Panel
    }
    class FormatadorBlog {
        +parts list
        +img_min int
        +img_max int
        +feed(html)
        +getvalue() str
    }
    class HTMLParser {
        <<stdlib>>
    }
    class Observabilidade["mod_intranet.observabilidade"] {
        +configurar()
        +get_logger(modulo) Logger
        +instalar_excepthook()
    }
    class Autenticacao["mod_intranet.autenticacao"] {
        +autenticar(user, senha)
        +registrar_login(user, modulo)
        +sessao_ativa(user, hash)
        +validar_acesso_modulo(user, chave)
        +modulos_do_usuario(user)
    }
    class AuditLog["mod_intranet.manipulador_bd.audit_log"] {
        +audit_log(usuario, modulo, acao, descricao, hash_arquivo)
    }
    class RegistrarAuditoria["mod_auditoria.manipulador_bd.registrar_auditoria"] {
        +registrar_auditoria(usuario, modulo, acao, ...)
    }

    main_py --> ModuloNegocio : importa e registra rotas
    ModuloNegocio *-- ManipuladorBD
    ModuloNegocio *-- Telas
    HTMLParser <|-- FormatadorBlog : única herança do código
    Telas ..> Observabilidade : get_logger("modulo")
    ManipuladorBD ..> Observabilidade : get_logger("modulo")
    ManipuladorBD ..> AuditLog : audita ações
    AuditLog ..> RegistrarAuditoria : grava em db_mod_auditoria.db
    main_py ..> Autenticacao : login/guarda/permissões
```

> `db_criador.py` é legado/morto em todos os módulos (aponta para o banco central com esquemas divergentes) — o padrão real é `manipulador_bd.init_db*()`. Detalhes em [Arquitetura](arquitetura.md#padrao-interno-de-um-modulo).
