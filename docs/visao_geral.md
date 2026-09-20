# Intranet Modular — System Overview

> High-level view of the Intranet Modular: the 11 modules (core + 10 business including the new News Aggregator `httpx+parsel` multi-source `Google/BBC/JFP/RSS` 3-column masonry + TV carousel and the Phone Directory organogram `Secretaria→Setor→Subsetor`), the main usage flow (login → dashboard → modules) and the 3 user profiles (`comum`, `administrador_modulo`, `administrador_geral`) with per-module roles, access validation and quota integration (1000/200 via `ORGANOGRAMA_BASE`).

---

# Intranet Modular — Visão Geral

> Visão de alto nível da Intranet Modular: os 11 módulos (núcleo + 10 de negócio incluindo o novo Agregador de Notícias `httpx+parsel` multi-fonte `Google/BBC/JFP/RSS` 3 colunas masonry + carrossel TV e a nova Lista Telefônica `Secretaria→Setor→Subsetor`), o fluxo principal de uso (login → dashboard → módulos) e os 3 perfis de usuário (`comum`, `administrador_modulo`, `administrador_geral`) com papéis por módulo, validação de acesso e integração de cotas (1000/200 via `ORGANOGRAMA_BASE`).

## Sumário

1. [Objetivos](#objetivos)
2. [Módulos do sistema](#modulos-do-sistema)
3. [Fluxo de alto nível](#fluxo-de-alto-nivel)
4. [Perfis de usuário](#perfis-de-usuario)
5. [Autorização por módulo](#autorizacao-por-modulo)

## Objetivos

- Centralizar serviços internos da rede em **uma única aplicação** acessível pela rede interna.
- Garantir **rastreabilidade** (auditoria central LGPD) de todas as ações relevantes.
- Permitir **evolução incremental**: cada funcionalidade é um módulo independente com banco próprio.
- Operar **sem internet**: interface com Tailwind local, bibliotecas empacotadas e documentação embutida.
- Manter **organograma único** compartilhado entre módulos (Lista Telefônica como fonte do organograma genérico e Solicitação de Impressão como consumidora das cotas 1000/200).

## Módulos do sistema

O sistema é composto por um **núcleo** (`mod_intranet`) e **10 módulos de negócio** (6 históricos + 2 em 18/09/2026 + 2 em 19/09/2026):

| Módulo | Chave | Rota | Banco | Função |
|:---|:---|:---|:---|:---|
| **Intranet (núcleo)** | `intranet` | `/`, `/login`, `/configuracoes`, `/documentacao` | `db_mod_intranet.db` | autenticação, sessões, configurações, backups, observabilidade |
| **Gestão de Usuários** | `usuarios` | `/users` | `db_mod_gest_cad_usuario.db` | CRUD soft de usuários, perfis, papéis por módulo, sessões ativas |
| **Blog** | `blog` | `/blog` | `db_mod_blog.db` | postagens/comentários HTML sanitizados (`nh3`) — **padrão `carrossel` com 3 básicas (18/09/2026)** |
| **Editor de PDF** | `editar_pdf` | `/edit-pdf` | `db_mod_edit_pdf.db` | reduzir, juntar, cortar, dividir, verificar, ZIP — com cotas e expiração |
| **Renomear Empenhos** | `empenhos` | `/renomear-empenho` | `db_mod_renomear_empenho.db` | extração de texto, regex dinâmicas, FTS5, quarentena, renomeação sequencial, organizador |
| **Auditoria** | `auditoria` | `/auditoria` | `db_mod_auditoria.db` (uma tabela por módulo) | trilha LGPD + visualização/filtro/exportação |
| **Solicitação de Impressão** | `solicita_impressao` | `/solicita-impressao` | `db_mod_solicita_impressao.db` | envio de PDF, contagem de páginas, cotas mensais (1000/200 via `ORGANOGRAMA_BASE`), autorização, impressão |
| **Técnico** | `tecnico` | `/tecnico` | `db_mod_tecnico.db` | **novo** (18/09/2026) — software (download zip multi-seleção) + backup `YYYYMMDD_HHMM_nomePc_ip` owner-isolated, `webkitdirectory` |
| **Filas (TV)** | `filas` | `/filas` + `/tv?grupo=` (compartilhada) + `/tv/{fila_id}` (isolada) | `db_mod_filas.db` | multi-filas por local (`endereco/prefixo/inicio→fim` `fim=0` infinito, `criado_por`, `tv_grupo`, `tb_fila_etapa`/`tb_midia`, isolamento por criador vs `administrador_geral`, TV `/tv/{id}` isolada vs `/tv?grupo=` compartilhada, ícone padrão intranet, bip+voz só novo id, playlist áudio elevador/vídeo `/midia_filas`, exclusão uma/todas exceto Geral, censura filtrada) |
| **Lista Telefônica** | `lista_telefonica` | `/lista-telefonica` + `/admin/lista_telefonica` | `db_mod_lista_telefonica.db` | **novo** (19/09/2026) — organograma 12 secretarias `Secretaria→Setor→Subsetor` genérico, contatos alfabéticos, busca sem acentos, `tel:` clicável no celular, admin com excluir ramo/mover/elevar/ordenar/transferir |
| **Agregador de Notícias** | `agregador_noticias` | `/agregador-noticias` + `/agregador-noticias-puro` (pura) + `/assets/noticia/*` + `/admin/agregador_noticias` | `db_mod_agregador_noticias.db` | **novo** (19/09/2026) — multi-fonte `httpx+parsel` (Google/BBC/JFP/RSS) espelhando `klaytonPrinceMS/Noticia`, termo livre + fontes configuráveis, 10–360 min, **barra filtro tema + busca lado a lado** `agregador-busca` `debounce 300` `placeholder "Buscar palavra…"` NFKD (**sem badge `Coleta:`** removido a169c9a) + `agregador-ver-puro` → `/agregador-noticias-puro`, grid responsivo **3→2→1 via `.grid-noticias {display:grid; grid-template-columns: repeat(3,1fr)}` + media queries 1024px/640px + `.card-noticia {min-height:160px; max-height:220px}` (média 91 notícias: título 79/75, descrição 34, 87.9% imagem, 24% fonte_icon)** `ui.link(target=href, new_tab=True)` + **ícone fonte 16×16 + imagem 30×30 lado a lado antes do título** (`fonte_icon_url` `faviconV2` + `imagem_url`), paginação 12 + busca 500 NFKD, **tela pura** `telas_puro.py` `intro-overlay` + `about` `info-list` (12 notícias `COALESCE DESC`, `assets/noticia/` `base.css`/`vendor.css`/`main.css`/`font-awesome`/`micons`/`js`/`images` via `main.py:818` `@app.get("/assets/noticia/{caminho:path}")`), 24h `limpar_antigas`/`reiniciar_banco` `06:00` `CronTrigger`, TV `listar_para_tv` (`fonte_icon` incluso, censura filtrada) + censura central `conteudo_palavras_bloqueadas` + `assets/noticia/` 4.9M servido via rota estática |

> O cadastro real de módulos vive em `tb_modulos` (banco central), semeado por `MODULOS_SISTEMA` em `mod_intranet/autenticacao.py:15-26`.

## Fluxo de alto nível

```mermaid
flowchart TD
    U[Usuário] -->|/login| L[Autenticação bcrypt]
    L -->|ok| S[Sessão revogável<br/>tb_sessoes + cookie_hash<br/>+ Visitas ++contador_acessos_total]
    S --> D[Dashboard /<br/>boas-vindas + Resumo dinâmico Water + feed do Blog<br/>sem botão Abrir Blog (18/09/2026)]
    D --> M[Drawer lateral<br/>módulos liberados]
    M --> R1[/blog] & R2[/users] & R3[/edit-pdf] & R4[/renomear-empenho] & R5[/solicita-impressao] & R6[/auditoria] & R7[/tecnico] & R8[/filas] & R9[/lista-telefonica] & R10[/agregador-noticias]
    R1 & R2 & R3 & R4 & R5 & R6 & R7 & R8 & R9 & R10 --> G[pagina_restrita<br/>autenticação + permissão + layout<br/>/tv sem guarda]
    G --> AC[audit_log<br/>db_mod_auditoria.db<br/>tb_auditoria_&lt;modulo&gt;]
    D -->|logout| LO[registrar_logout + /login]
    BG[APScheduler<br/>backups · cleanups · monitor · poda<br/>+ agregador_coleta/limpeza] -.->|2º plano| AC
    LT[(Lista Telefônica<br/>ORGANOGRAMA_BASE<br/>12 secretarias)] -.->|importa cotas 1000/200| R5
     AG[(Agregador<br/>tb_noticia 24h<br/>httpx+parsel<br/>censura filtrada)] -.->|listar_para_tv<br/>carrossel 7s/120s filtrado| R8
     CS[(Censura<br/>tb_config conteudo_palavras_bloqueadas<br/>lower+NFD)] -.->|titulo_bloqueado| R1 & R10 & R8
```

1. O usuário acessa `/login` e informa usuário/senha (`autenticar` → bcrypt).
2. Login bem-sucedido cria uma **sessão revogável** (`registrar_login`) amarrada a um cookie HTTP-Only (`cookie_hash`) e incrementa **uma única vez** o contador `tb_config contador_acessos_total` (`bd_conexao.incrementar_contador_acessos()` só em `main.py:tentar_login()` — nunca em navegação/refresh; `contador_acessos_inicio` em `YYYY-MM-DD` semeado em `bd_conexao.init_db()`).
3. O usuário é levado ao **Dashboard** `/` (saudação + **Resumo dinâmico sem botão Atualizar** + feed do Blog) — ver detalhe abaixo.
4. A navegação por módulos ocorre pelo **menu lateral** (drawer), que só mostra módulos liberados ao usuário.
5. Toda rota de módulo passa pela guarda `pagina_restrita` (autenticação + permissão + layout de 4 partes).
6. Ações relevantes gravam a **trilha de auditoria** (`audit_log` → banco exclusivo `db_mod_auditoria.db`, tabela por módulo) com IP/user-agent/hash quando aplicável.
7. Em segundo plano, **APScheduler** executa backups por módulo, limpezas e monitor de pasta.

### Dashboard `/` — Resumo dinâmico (redesign 09/2026, padronizado 18/09/2026)

> Home visual **Water escopado só no card** (`home_visual.injetar_water_card()` → `.home-resumo-water/.home-stat-water` border `#dfe8f0` bg `#fafcfd`, ícone 36px, `modelo="water"` fixo em `page_dashboard` — **18/09/2026**: sombra lateral direita `box-shadow:6px 0 16px rgba(0,0,0,.07)` + `border-left-color` = **cor do módulo `intranet`** via `ler_tema("intranet")["cor_botao"]` (antes `#000000`/`#EF6C00` fixos) + `classes_card_resumo` com `shadow-md`).

- **Sem botão Atualizar**: `_orquestrar_resumo_dados()` (`main.py:250`) recalcula **a cada acesso** (9 contadores: usuários `filtro_ativo=None`, sessões `WHERE logout IS NULL`, visitas `contador_acessos_total`, postagens, quarentena `processado=0`, PDFs `ativo=1`, auditoria 24h `SUM WHERE timestamp >= -1 day`, fila impressão pendente, logs totais).
- **Sem botão "Abrir Blog completo" (removido 18/09/2026)**: o header do feed em `main.py:448-453` é agora só `row items-center` com `label "Publicações recentes"` — o acesso ao Blog permanece pelo drawer (`/blog`); a Home usa `renderizar_postagens` (mesmo padrão do módulo) sem navegação dedicada.
- **2 cards, altura -50%+25% com sombra lateral direita e cor do módulo**: `gap-1 px-2 py-1`, ícone 36px `text-2xl`, número `text-h6` 4 dígitos (`>9999` com total real no tooltip único do card; `Logs>9999` com alerta `⚠️ realize backup do banco de auditoria (db_mod_auditoria.db)`), layout horizontal ícone esq + número, tooltip simples (`Usuarios/Sessões/Noticias/Logs/Visitas/Fila geral/Para autorizar/Quarentena/PDFs/Auditoria 24h`). Estilo: `.home-resumo-water` + `.home-resumo-pic` com `border-left-width:4px` + `box-shadow:6px 0 16px` + `shadow-md` em `classes_card_resumo`.
- **Visibilidade por papel**:
    - **"Resumo do sistema"** (8 métricas: Usuários, Sessões, Visitas, Postagens, Quarentena, PDFs, Logs, Logs 24h) — **só `administrador_geral`/`administrador_modulo`** (`eh_admin` `main.py:500`, `main.py:406-426` com `_cor_modulo_home` via `ler_tema("intranet")`).
    - **"Resumo do sistema — Impressão"** (Fila geral + Para autorizar) — **só autorizador** (`tb_responsaveis_autorizacao ativo=1` via `_eh_autorizador_impressao()` `main.py:446`) **ou `administrador_geral`** (`_contar_fila_para_autorizar()` `main.py:460`; admin geral = fila geral; `main.py:427-441` com `_cor_modulo_home2` idem, antes `#EF6C00` fixo).
- Comparativo `/home-*` revertido e hambúrguer sem seção comparativa; serviço `http://localhost:8080` water OK.

## Perfis de usuário

Existem **3 perfis globais** (coluna `user_perfil` de `tb_usuarios`):

| Perfil | Acesso | Exemplos de capacidades |
|:---|:---|:---|
| `comum` | módulos liberados (papel por módulo) | ler Blog, editar PDFs, renomear/consultar empenhos, solicitar impressão |
| `administrador_modulo` | admin de **módulos específicos** | gerenciar o módulo (publicar, imprimir, configurar aparência do módulo) |
| `administrador_geral` | **todos** os módulos + auditoria + configurações | ver tudo, excluir usuários (LGPD), configurar sistema, visualizar auditoria |

Além do perfil global, existe o **papel por módulo** (`tb_acesso_usuario`): vínculo `usuário × módulo × papel` (ex.: `comum` ou `administrador` dentro de `solicita_impressao`). A combinação perfil global + papel por módulo define o que aparece no menu e o que é aceito pela guarda.

### Perfis × módulos (visão resumida)

| Módulo | `comum` | `administrador_modulo` | `administrador_geral` |
|:---|:---:|:---:|:---:|
| Blog | somente leitura (censura `titulo_bloqueado` bloqueia `criar/atualizar` se palavra proibida) | criar/editar/publicar (censura bloqueia título com palavra proibida) | tudo + gerenciar censura (`blog-palavras-bloqueadas`) |
| Editor de PDF | usar editor | — | cotas/expiração (aba Administração) |
| Renomear Empenhos | processar/pesquisar/ZIP | regras/quarentena | tudo |
| Auditoria | ✗ | ✗ | somente este perfil |
| Configurações | ✗ | ✗ | somente este perfil |
| Gestão de Usuários | ✗ | admin do módulo `usuarios` | tudo |
| Solicitação de Impressão | solicitar/acompanhar | imprimir/gerenciar | tudo |
| Técnico | software/backup do próprio PC | — | tudo + ver todos os backups em `/admin/tecnico` |
| Filas (TV) | chamar próxima / ver TV isolada `/tv/{id}` ou compartilhada `/tv?grupo=` + notícias censura-filtradas + mídia | gerenciar multi-filas do próprio dono; mídia global só admin | tudo (todas as filas + mídia global) |
| Lista Telefônica | ver organograma + busca + ligar | gerenciar ramos/contatos/ordem | tudo |
| Agregador de Notícias | ver 3 colunas + **filtro tema + busca lado a lado** `agregador-busca` `debounce 300` NFKD + abrir link externo (**ícone fonte 16×16 + imagem 30×30 antes do título**, sem badge `Coleta:`, censura filtra `listar_para_tv`) | configurar habilitado/intervalo/termo/fontes/temas + censura (`agregador-palavras-bloqueadas`) + **busca NFKD** | tudo + `Coletar agora` + `Remover já censuradas` |

## Autorização por módulo

- A visibilidade no **menu lateral** usa `listar_modulos_permitidos` / `modulos_do_usuario`.
- O **gate de rota** usa `validar_acesso_modulo` (núcleo delega ao manipulador do módulo de usuários).
- Tentativa sem permissão gera `acesso_negado` na trilha de auditoria (`layout_tela.pagina_restrita` — choke point único).
- Dentro de cada módulo, a tela valida novamente o papel antes de qualquer escrita (dupla camada UI + backend).

> Usuários de teste prontos: `qacomum`/`123456` (comum) e `qamaster`/`123456` (administrador_geral) — ver [Guia de Início Rápido](inicio_rapido.md).