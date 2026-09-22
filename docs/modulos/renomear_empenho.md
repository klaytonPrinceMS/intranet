# Empenho Renamer Module — `mod_renomear_empenho`

> Empenho renaming and management module: route `/renomear-empenho` (key `empenhos`) · own DB `db_mod_renomear_empenho.db` · PDF text extraction (incl. special types EC/EE/EG/AE), multi-folder monitor (local/UNC) with optional automatic renaming, FTS5 search with prefix (1 char) + LIKE fallback, live inventory `tb_levantamento`/`tb_levantamento_fts`, rename queue, quarantine with batch `run.io_bound` reprocessing without restart, physical organizer with `capa.pdf/txt` + `matrizDeDocumentos.pdf/.txt`, request flow and settings. Audit removed from admin panel — shown only in Auditoria menu via `audit_log`.

---

# Módulo Renomear Empenho — `mod_renomear_empenho`

> Módulo de renomeação e gestão de empenhos: rota `/renomear-empenho` (chave `empenhos`) · banco próprio `db_mod_renomear_empenho.db` · extração de texto de PDF (inclui tipos especiais EC/EE/EG/AE), monitor multi-pasta (local/UNC) com renomeação automática desabilitável, pesquisa FTS5 com prefixo (1 letra já filtra) + fallback LIKE, inventário vivo `tb_levantamento`/`tb_levantamento_fts`, fila de renomeação, quarentena com reprocessamento em lote assíncrono sem reiniciar, organizador físico com `capa.pdf/txt` + `matrizDeDocumentos.pdf/.txt`, fluxo de solicitações comum→admin e configurações do módulo. Auditoria removida da admin — exibida só no menu Auditoria via `audit_log`.

## Propósito

Extrai o nº do empenho/parcela (ou o tipo especial EC/EE/EG/AE) do texto dos PDFs por regex dinâmica, renomeia sequencialmente e move falhas para quarentena reprocessável. Mantém **inventário vivo** de todos os PDFs nas pastas monitoradas (`tb_levantamento`, `tb_levantamento_fts`) para busca por nome/campos/conteúdo mesmo antes da renomeação. Inclui organizador físico em caixas/subpastas, edição e ferramentas de PDF, e o fluxo completo de solicitação de envio (comum solicita; admin aprova via e-mail ou ZIP).

A tela é organizada em **6 abas internas**: **Navegar**, **Fila Renomeação**, **Pesquisar**, **Organizador** (admin), **Solicitação** e **Configurações** (admin). O menu lateral global de módulos permanece intacto. A **renomeação automática** pelo monitor pode ser desligada por switch admin sem afetar o processamento manual.

## Banco de dados

Criador vigente: `init_db_empenho()` em `bd_manipulador.py:289`.

| Tabela | Conteúdo |
|:---|:---|
| `tb_empenhos` | nome original/final, numero_empenho, parcela, **tipo_especial**, ficha, ano, usuario, data, status, caminho + 40+ colunas espelho de `CAMPOS_BUSCA_PADRAO` e `campos_json` |
| `tb_indexador_pesquisa` | fallback comum (`empenho_id`, `conteudo_texto`) |
| `tb_indexador_pesquisa_fts5` | **VIRTUAL TABLE FTS5 com 59 colunas** do cabeçalho (RF-41, `FTS_COLS` em `bd_manipulador.py:461`) + trigger de exclusão + `campo_destino` nas regras |
| `tb_levantamento` | **inventário vivo** — `nome_arquivo`, `caminho_atual UNIQUE`, `presente` (1/0), `status` (detectado/renomeado), `numero_empenho`, `parcela`, `ficha`, `ano`, `tipo_especial`, **`usuario` (`TEXT`, CREATE + `_migrar_coluna` idempotente — ator do reconhecimento)**, `conteudo_texto` (≤20k), `tamanho`, `mtime`, `data_deteccao`, `data_visto`; índices `idx_lev_nome`, `idx_lev_presente`, `idx_lev_num` (`bd_manipulador.py:630`) |
| `tb_levantamento_fts` | **VIRTUAL TABLE FTS5** `nome_arquivo, numero_empenho, ficha, ano, tipo_especial, conteudo_texto` sobre o levantamento — **só no SQLite**; no Postgres o `CREATE VIRTUAL TABLE` é ignorado pelo proxy (`_CursorPostgres`) e a busca usa **fallback `LIKE`** (`bd_manipulador.py:651`, `pesquisar_levantamento:1757`) |
| `tb_quarentena` | nome_arquivo, motivo, caminho_atual, data_insercao, processado |
| `tb_regex_regras` | nome_regra UNIQUE, padrao_regra, substituicao, ativo, **campo_destino** (FTS customizado) |
| `tb_campos_busca` | regex de identificação por campo (ficha/empenho/parcela/ano...) editáveis sem tocar no código |
| `tb_arquivos_auditoria` | trilha por arquivo (detectado→renomeado→removido) com **hash SHA-256** de origem/destino |
| `tb_eventos_arquivos` | linha do tempo cronológica por arquivo (FK para `tb_arquivos_auditoria`) |
| `tb_solicitacoes` | fluxo comum→admin: pendente → enviado/email \| zip_gerado → recusado; com `lote_id`, `metodo_envio`, `caminho_zip`, `motivo_recusa` |

⚠️ O `bd_criador.py` é **legado/morto** (esquema FTS5 fantasma no banco central) — não executar; o esquema real está em `bd_manipulador.py`.

### Levantamento — inventário pelo monitor

- **Coleta:** `levantar_arquivos(usuario)` em `bd_manipulador.py:1614` varre **todas** as pastas monitoradas com `os.walk` (recursivo só para inventário), anota todo PDF novo com **nome, campos extraídos (nº/parcela/ficha/ano/tipo), conteúdo e usuário** para busca — o **ator é gravado no `INSERT`** e na **releitura** (mesmo `tamanho`/`mtime`, só `presente=1`/`status`/`data_visto`); na **revisita adota o usuário logado sem que o agendador `"sistema"` sobrescreva nome real** (só adota quando ator ≠ `"sistema"` e dono vazio ou `"sistema"`). Arquivos sem alteração são só revisitados (`presente=1`), ausentes ficam `presente=0`. Chamada **antes** de processar em `rodar_monitor()` (`bd_manipulador.py:2305`).
- **Anotação para exibição:** `anotar_arquivos(pdfs)` (`bd_manipulador.py:2624`) anexa `numero_empenho`/`parcela`/`usuario`/`data` do levantamento a cada dict; quando processado, **sobrescreve com `tb_empenhos`** (nº/parcela/usuário de quem processou, com fallback ao nome final `doc_<cont>_<empenho>_<parcela>.pdf` / `EC|EE|EG|AE_<n>.pdf`). `listar_navegacao` e `listar_pendentes` retornam os dicts já anotados.
- **Atualização pós-renomeação:** `atualizar_levantamento_renomeado()` (`bd_manipulador.py:1736`) aponta o registro para `nome_final`/`caminho_final`/`status='renomeado'` e ressincroniza o FTS via `_levantamento_fts_sincronizar()` (`bd_manipulador.py:1593` — `DELETE+INSERT` por `rowid`; falha silenciosa no Postgres).
- **Busca no levantamento:** `pesquisar_levantamento(termo, limite=100)` (`bd_manipulador.py:1769`) tenta `MATCH` com **prefixo** via `_fts_query_prefixada()` (`bd_manipulador.py:1871` — `'"tok"*'` no último token, 1 letra já filtra) e cai em `LIKE` (`nome_arquivo`, `numero_empenho`, `ficha`, `ano`, `conteudo_texto`) quando FTS indisponível (Postgres); **retorna também `parcela` e `usuario`** — tuplas `(id, nome, caminho, presente, status, numero, parcela, ficha, ano, usuario)`.

## Funcionalidades

- **6 abas internas** (padrão `mod_solicita_impressao/telas.py`, com tabs manuais):
  - **Navegar**: navegação recursiva e protegida (anti-travessia) das pastas monitoradas + organizador, mostrando apenas PDFs; breadcrumb; baixar; revisar/renomear manual; solicitar envio. Botões "Processar pasta agora" e "Atualizar". Lista, cabeçalhos e resultados de pesquisa exibem as colunas **Arquivo, Empenho, Parcela, Usuário, Data, Status** (+ Pasta/Ações) — valores da leitura do reconhecimento/processamento via `anotar_arquivos`, com **zeros à esquerda normalizados só na exibição**. Campo **Pesquisar (conteúdo + todos os campos)** com **busca FTS5 assíncrona** — vê abaixo.
  - **Fila Renomeação**: lista recursiva de PDFs pendentes, "Processar" individual e "Processar todos". Cada linha exibe **Arquivo, Empenho, Parcela, Usuário, Data, Status** (leitura do reconhecimento via `anotar_arquivos`; zeros à esquerda normalizados só na exibição).
  - **Pesquisar**: busca FTS5 (`MATCH`, fallback `LIKE`) + tabela de empenhos renomeados (coluna **Usuário** já existente, mantida).
  - **Organizador** (admin): organizar caixas, gerar capas/matriz, validar matriz, inventário e ferramentas de PDF (cortar/mesclar/reduzir).
  - **Solicitação**: fluxo comum→admin (e-mail/ZIP/recusa) com agrupamento por lote e histórico; admin confirma/recusa.
  - **Configurações** (admin): pastas monitoradas (multi-pasta, UNC), aparência, template de nome, campos de busca, quarentena e regras regex — **sem aba de Auditoria** (removida; auditoria vive no menu Auditoria via `audit_log` central).
- **Monitor multi-pasta** (RF-40): varre a **raiz** de cada pasta monitorada (não recursivo), incluindo pastas **locais e de rede/UNC** (`\\servidor\empenhos`, `E:\scan`); pastas inacessíveis são puladas sem derrubar o monitor. Automático via job `monitor_empenho` do APScheduler (intervalo configurável, padrão 60 s) + botão manual. **Renomeação automática desabilitável** — switch admin `Renomeação automática pelo monitor` (`telas_administracao.py:150`) grava `empenhos_renomeacao_automatica` (`1`/`0`, padrão `1`) em `tb_config`; `rotinas._job_monitor_empenho()` (`mod_intranet/rotinas.py:208`) checa `renomeacao_automatica_empenho_ativa()` (`rotinas.py:194`) e retorna sem varrer quando `0` — processamento manual (botão "Processar pasta agora", fila, revisão) continua ativo.
- **Pesquisa na aba Navegar — FTS5 assíncrona com prefixo** (`telas.py:412`):
  - Handler `async _filtrar()` (`telas.py:471`) dispara a cada `update:model-value` do `ui.input` `data-testid=empenhos-navegar-pesquisa`; **1 letra já filtra** via `_fts_query_prefixada()` (`bd_manipulador.py:1871` — último token vira `'"tok"*'`).
  - **Assíncrona anti-disconnect (§5.1):** `achados = await run.io_bound(_buscar_dados, termo, raiz)` (`telas.py:487`) — evita travar o event-loop do NiceGUI; spinner `ui.spinner` com `aria-label="Pesquisando empenhos"` + label "Pesquisando (FTS5 + conteúdo)…" durante o `io_bound`.
  - **Combina duas fontes:** `pesquisar(termo, 100)` (processados, FTS5 do módulo, 59 colunas) + `pesquisar_levantamento(termo, 100)` (pendentes/detectados com nome/campos/conteúdo). Escopo confinado à **pasta atual + subpastas** (`_dentro()` checa `realpath` `== raiz` ou `startswith(raiz+sep)`).
  - **Exibição:** só **nome do arquivo** + `badge` **"na pasta"** (verde, `presente=1` e existe em disco) ou **"fora da pasta"** (cinza, `presente=0` ou removido) + `sub` relativo quando em subpasta; `visto` deduplica por `real.lower()`, ignora inexistentes; contador `data-testid=empenhos-navegar-contagem` mostra `"Pesquisa 'X': N resultado(s) nesta pasta e subpastas (nome + presença)."`; debounce por `seq`.
- **Tipos especiais** (EC/EE/EG/AE): `detectar_tipo_especial`/`extrair_dados_tipo_especial` detectam pelo conteúdo (AE>EC>PARCELA>Tipo>Nota de Empenho) e nomeiam `EC_0024.pdf`, `EE_9570.pdf`, `EG_0089.pdf`; corrige a captura que antes pegava o nº do empenho complementado (66) em vez do nº do documento (24).
- **Pesquisa FTS5** (RF-41): 59 colunas do cabeçalho; regras regex com `campo_destino` alimentam colunas customizadas; trigger de exclusão mantém o índice sincronizado; `_fts_query_prefixada` habilita prefixo incremental.
- **Gate de validação**: `renomear_manual`/`processar_pdf` só renomeiam quando o nº é identificado sem divergência crítica; caso contrário vão para a quarentena com motivo.
- **Não-reprocessamento**: `arquivo_ja_processado` (nomes DOC) + `_arquivo_registrado_no_bd` (autoritativo via `tb_empenhos`) impedem reprocessar itens já renomeados (inclusive tipos especiais, cujo nome não discrimina por contagem de dígitos).
- **Quarentena e regras dinâmicas (4b)**: falhas vão para `mod_renomear_empenho/quarentena/<timestamp>_<nome>` via `mover_quarentena`/`promover_quarentena` (aliases PLANO) com motivo em `tb_quarentena`; admin reprocessa **individualmente** (clique na linha → regex alternativa → `reprocesse_quarentena`) ou **em lote assíncrono** (botão **"Reprocessar fila"** `data-testid=empenhos-reprocessar-fila-admin` → `reprocessar_fila` itera `processado=0` com regras ativas, sem reiniciar; hardening: valida `REGEX_MAX_LEN=200` e `re.compile`, confina caminho à quarentena — `bd_manipulador.py:2091`); **identificação manual** via "Revisar/renomear" (`renomear_manual` com gate e **correção EE `str→int`** — `telas.py:222` converte `num_txt` via `re.sub`/`int` antes de montar `EC_0024` etc., evita `TypeError` quando o input vem como string do diálogo); **regex dinâmicas** em `tb_regex_regras` (`nome_regra UNIQUE`, `padrao_regra` validado por `re.compile`, `campo_destino` → FTS) e `tb_campos_busca` — cadastro/edição sem reiniciar, leitura a cada extração. **Múltiplos documentos**: `detectar_documentos_no_pdf`/`eh_multiplo_documento` detecta 2+ empenhos (critério: ≥2 `NOTA DE EMPENHO`/`EMPENHO PARCELA` com nº distintos); quarentena marca "Múltiplos documentos detectados" e expõe **"Separar documentos"** (`separar_documentos_quarentena`/`separar_pdf_por_documentos` → `*_parteNN_pA-B.pdf` na pasta monitorada + reprocesso).
- **Lote de solicitações assíncrono** (`telas.py:299`): `_enviar_lote()` em `Navegar` é `async` com `await run.io_bound(_gravar)` — grava `N×criar_solicitacao` fora do event-loop, com spinner `aria-label="Registrando lote"`, botão `Solicitar lote` desabilitado e trava `ocupado` (anti-disconnect §5.1); evita `websocket disconnect` quando o lote tem N itens (~0,35 s cada em SQLite+auditoria).
- **Organizador físico (4c / RF-44)**: distribui em `mod_renomear_empenho/organizadorPasta/caixa_NN/sub_X` com **~200 páginas por subpasta e 4 subpastas por caixa** (configuráveis via `tb_config` `empenhos_organizador_paginas_pasta`/`empenhos_organizador_pastas_caixa`, `bd_manipulador.py:1988`); `gerar_matriz_organizador` gera **capa por caixa** (`caixa_NN/capa.txt` **e** `caixa_NN/capa.pdf`) e **matriz geral** (`matrizDeDocumentos.txt` **e** `matrizDeDocumentos.pdf` na raiz do organizador); `validar_presenca_matriz` confere presença de todos os PDFs listados; `organizar_pastas` já encadeia a geração e retorna total + mensagem da matriz; estrutura visível em `mod_renomear_empenho/organizadorPasta/`.
- **Ferramentas de PDF embutidas** (RF-45): corte (pares/ímpares/intervalo), mesclagem e redução; saídas em `mod_renomear_empenho/datahora_cortePDF/`, `mod_renomear_empenho/datahora_mergePDF/`, `mod_renomear_empenho/datahora_reducaoPDF/`.
- **Solicitações de envio** (RF-39): comum registra pedido (e-mail + mensagem); admin envia por e-mail (SMTP central `mod_intranet/email_util`) ou gera ZIP (`mod_renomear_empenho/downloads/solic_*.zip`); agrupamento por lote; histórico completo.
- **Painel Administração** (`telas_administracao.py:36`): aparência (`empenhos_*` — cor do botão/texto/fundo/título, tamanho, texto do cabeçalho via `bloco_aparencia`), pastas monitoradas (multi-pasta, UNC), intervalo do monitor + **switch `empenhos_renomeacao_automatica`**, autorização de download/ZIP/e-mail para comuns, template de nome final, campos de busca e regras regex — **auditoria removida**; exibida exclusivamente no menu **Auditoria** (banco `db_mod_auditoria.db` via `audit_log`).
- **Responsividade (RNF-UI-01, 09/2026 — auditado 320/768/1024 `kbp-web-design`)**: proposta P0/P1/P2 por `container`/`row`/`grid` — `menu_modulo` `overflow-x-auto`, filtros/busca `flex-wrap` `flex-1 min-w`, tabelas `overflow-x-auto`, `scroll_area` altura explícita, grids `grid-cols-1 sm:grid-cols-2 md:grid-cols-3`, dialogs `w-full max-w`; cabeçalho `flex-wrap` `truncate`.
- **Versionamento**: `versao_modulo:empenhos = 1.0.<data>` (seed em `bd_conexao.init_db()`), exibido no rodapé.

## CSS frameworks — padrão PIC (12/09/2026)

> Standard visual **PIC** defined in `tb_config empenhos_modelo_visual=pic` — 17 CSS remain on disk for direct URL comparison (200), drawer shows only the default Empenhos.
>
> Padrão visual **PIC** definido em `tb_config empenhos_modelo_visual=pic` — 17 CSS permanecem em disco para comparação direta via URL (200), drawer exibe apenas Empenhos padrão.

O padrão do módulo é **PIC — Quasar nativo suave (sem framework)** (`mod_renomear_empenho/visual.py:MODELO_PADRAO="pic"`, `CHAVE_CONFIG="empenhos_modelo_visual"`). Antes as 12 telas por CSS (`spectre`, `chota`, `milligram`, `skeleton`, `water`, `mvp`, `tachyons`, `uikit`, `foundation`, `semantic`, `materialize`, `primer`) + os 5 legados (`bootstrap`, `bulma`, `daisyui`, `pico`, `picnic`/`hibrido`) apareciam no drawer `mod_intranet/telas.py` como `Empenhos — PIC + por CSS`. Agora o drawer contém apenas **Empenhos padrão** (`/renomear-empenho`, chave `empenhos`) e o bloco de exemplos foi removido — comentário `Padrão PIC definido — exemplos de CSS removidos do menu (mantidos em disco/docs para comparação direta via URL se necessário).` (`telas.py:289`).

Os **17 frameworks** permanecem em disco em `assets/css/frameworks/` (17 arquivos principais + `daisyui themes` auxiliar) e continuam registrados em `mod_intranet/tema_css.py:FRAMEWORKS_CSS` e servidos em `/css/frameworks/*` por `tema_css.montar_rotas_static()` (`main.py:129`). Cada um tem **tela dedicada** `/renomear-empenho-{nome}` em `main.py:572-637` via `visual.FORCAR_MODELO` + `tema_css.injetar_framework()` por página (sem CDN, sem reset global fora do escopo) — todas respondem `200` quando autenticado, permitindo **comparação direta via URL sem poluir o menu**. Ver `assets/css/frameworks/README.md` para versões, origens, licenças e avaliação de compatibilidade.

| Grupo | Frameworks | Rotas dedicadas | No menu? |
|:---|:---|:---|:---:|
| Legados mantidos em disco | `bootstrap`, `bulma`, `daisyui`, `pico`, `picnic` | `/renomear-empenho-bootstrap` (bootstrap) | Não |
| 12 novos | `spectre`, `chota`, `milligram`, `skeleton`, `water`, `mvp`, `tachyons`, `uikit`, `foundation`, `semantic`, `materialize`, `primer` | `/renomear-empenho-spectre` … `/renomear-empenho-primer` | Não — rota direta (200) |
| **Padrão** | **PIC** (sem arquivo) | `/renomear-empenho` + `/renomear-empenho-pic` | **Sim** |

`visual.FRAMEWORKS` lista apenas os 12 novos; `visual.VALIDOS=("pic",)+FRAMEWORKS` e `visual.ROTULOS` mapeiam rótulos amigáveis. A troca de modelo continua via `visual.salvar_modelo()` se necessário, mas o `tb_config` permanece `pic`.

## Botão TEMPORÁRIO de massa de teste — REMOVER em produção (14/09/2026)

> Temporary QA-only button that creates 25 fictitious PDFs per click — MUST be removed before production.
>
> Botão TEMPORÁRIO só para QA que cria 25 PDFs fictícios por clique — REMOVER obrigatoriamente antes de produção.

!!! warning "TEMPORARIO-25-ARQUIVOS-REMOVER-EM-PRODUCAO — remover antes de produção"
    O botão **"Gerar 25 (TEMP)"** (`mod_renomear_empenho/telas.py:153-183`) existe **apenas para gerar massa de teste** e **NÃO pode ir para produção**. A remoção é apagar o bloco marcado + o handler `_gerar_25_temp` (linhas 153-183).

- **Onde:** totalmente à direita do `menu_mod` (row `justify-between flex-nowrap`: `ui.tabs` `flex-1 min-w-0 overflow-x-auto` à esquerda e botão `shrink-0 ml-auto` à direita), rótulo "Gerar 25 (TEMP)" ícone `science` variante `secundario` `data-testid=empenhos-gerar-25-temp`.
- **Comportamento esperado:** cada clique cria **+25 PDFs fictícios** na 1ª pasta de `pastas_monitoradas()` (fallback `_PASTA_MONITORADA_PADRAO` = `mod_renomear_empenho/doc`) via `assets/test/fabrica_documentos.py:criar_lote_principal(pasta_doc, quantidade=25)`; handler async `_gerar_25_temp` com `await run.io_bound(_criar)` (anti-disconnect AGENTS.md §5.1 — nunca bloqueia o event-loop); audita `audit_log(usuario,"empenhos","gerar_massa_temp",...)` e exibe `notificar` positiva (`"<N> arquivos criados na pasta doc."`) ou negativa (`"Falha ao criar arquivos: ..."`) em falha.
- **Arquivos:linhas:** `mod_renomear_empenho/telas.py:153-183` (botão + handler), `assets/test/fabrica_documentos.py:53` (`criar_lote_principal`), `mod_renomear_empenho/bd_manipulador.py:30-34` (`_PASTA_MONITORADA_PADRAO`/`pastas_monitoradas`).

## Contagem de acessos — apenas logins (padronizada)

> Access counter now **login-only** (navigations/refresh never count), centralized in `mod_intranet/bd_conexao.incrementar_contador_acessos()` via `tb_config` (`contador_acessos_total` + `contador_acessos_inicio`).
>
> Contador de acessos agora **apenas logins** (navegações/refresh nunca contam), centralizado em `mod_intranet/bd_conexao.incrementar_contador_acessos()` via `tb_config` (`contador_acessos_total` + `contador_acessos_inicio`).

**Antes:** contagem inline em `main.py` (incrementava em navegações/refresh). **Agora:** padronizada e centralizada em `mod_intranet/bd_conexao.incrementar_contador_acessos()` (`bd_conexao.py:200`) — conta **apenas logins bem-sucedidos**, nunca navegações, refreshs ou trocas de aba.

| Item | Detalhe |
|:---|:---|
| Função central | `mod_intranet/bd_conexao.incrementar_contador_acessos() -> int` — docstring bilíngue EN no topo / PT-BR abaixo |
| Persistência | `tb_config contador_acessos_total` (total acumulado, default `"0"`) + `contador_acessos_inicio` (data `YYYY-MM-DD` do início da contagem) via `get_config`/`set_config` (delegam a `Repositorio`/SQLAlchemy → `banco_conexao.conexao`) |
| Seed | `bd_conexao.init_db()` semeia `contador_acessos_total="0"` e `contador_acessos_inicio=hoje` se ausentes (`bd_conexao.py:186-197`) |
| Chamada única | `main.py:tentar_login` (`page_login`, `main.py:227-231`) após `autenticacao.registrar_login(nome, "sistema")` — bloco `try` com `incrementar_contador_acessos()` fail-soft |
| Leitura | `main._orquestrar_resumo_dados()` (`main.py:248-321`) apenas lê `get_config("contador_acessos_total")` para o card **Acessos** do Resumo do sistema (exibido no dashboard para `administrador_geral`/`administrador_modulo`) — nunca incrementa |
| Dashboard | `_orquestrar_resumo_dados` coleta 9 contadores (5 base + fila impressão, quarentena, PDFs, auditoria 24h); `n_acessos` vem do contador padronizado; `_stat` exibe `>9999` com tooltip do total real |

Fluxo:

```python
# main.py:tentar_login (após validar credenciais)
sessao = autenticacao.registrar_login(nome, "sistema")
try:
    from mod_intranet.bd_conexao import incrementar_contador_acessos
    incrementar_contador_acessos()  # só logins
except Exception:
    pass
```

Antes o incremento era inline em `main`; agora a função documentada é a **única fonte da verdade** (read elsewhere, write only here).

## Regras de negócio

- Contador sequencial persistido em banco, único entre pastas; template de nome configurável (`doc_{contador:04d}_{empenho}_{parcela:03d}.pdf` — ex.: `doc_0001_345_001.pdf`).
- Tipos especiais usam nome próprio (`EC_%04d.pdf`), não o sequencial DOC; `renomear_manual` com `tipo_especial` converte `novo_numero` string→int (`re.sub`+`int`) antes de `montar_nome_tipo_especial`.
- **Gate de validação**: renomeação somente com nº identificado; falha → quarentena com motivo (PLANO 4b/4c atendidos).
- **Levantamento:** todo PDF nas pastas monitoradas é anotado no reconhecimento (nome/campos/conteúdo **+ usuário do ator**) antes do processamento; `presente` indica se ainda está em disco — a pesquisa Navegar mostra `na pasta`/`fora da pasta`; Navegar e Fila exibem **Arquivo, Empenho, Parcela, Usuário, Data, Status** via `anotar_arquivos` (sobrescrito por `tb_empenhos` quando processado).
- **Quarentena (4b)**: `promover_quarentena`/`mover_quarentena` grava motivo (300 chars) e timestamp; reprocessamento individual (`reprocesse_quarentena` com regex alternativa) e em lote (`reprocessar_fila` + botão "Reprocessar fila" sem reiniciar, `run.io_bound` no admin) sem reiniciar; múltiplos documentos detectados por `detectar_documentos_no_pdf` → botão "Separar documentos".
- **Organizador (4c)**: ~200 páginas/subpasta e 4 subpastas/caixa (configuráveis); capas `capa.txt` + `capa.pdf` por caixa e matriz `matrizDeDocumentos.txt/.pdf` geral; `validar_presenca_matriz` garante que todo PDF da matriz existe em `organizadorPasta/`.
- Não-reprocessamento: DOC por padrão de nome; tipos especiais e demais por registro no banco (`tb_empenhos`/`tb_arquivos_auditoria`).
- Anti-travessia: navegação/renomeação restritas às raízes protegidas (`pastas_monitoradas` + `mod_renomear_empenho/organizadorPasta`), com `realpath` + `startswith`.
- Auditoria: `audit_log` (central, **com hash SHA-256** em toda operação) + trilha por arquivo em `tb_arquivos_auditoria`/`tb_eventos_arquivos`; **não há seção de auditoria na admin do módulo** — consulta exclusiva no menu **Auditoria** (`/auditoria`).
- Monitor automático varre só a raiz; levantamento e navegação/fila manuais variam recursivamente; `rodar_monitor` levanta antes de processar.
- Renomeação automática pode ser desligada (`empenhos_renomeacao_automatica=0`) — `rotinas._job_monitor_empenho` vira no-op; manual permanece.

## Permissões

| Ação | `comum` | Admin módulo | `administrador_geral` |
|:---|:---:|:---:|:---:|
| Navegar / pesquisar (prefixo 1 letra, FTS5+levantamento, badge na pasta/fora) / baixar (se autorizado) / solicitar envio (lote async) | ✓ | ✓ | ✓ |
| Fila: processar / processar todos | ✓ | ✓ | ✓ |
| Organizador / ferramentas de PDF | ✗ | ✓ | ✓ |
| Solicitação: confirmar envio / gerar ZIP / recusar | ✗ | ✓ | ✓ |
| Configurações / pastas / intervalo / **renomeação automática on/off** / template / campos / regras / quarentena | ✗ | ✓ | ✓ |
| Auditoria do módulo | — | — | — (exclusivo menu **Auditoria**) |

> Detalhe: usuário `comum` só baixa/envia quando `renomear_autorizar_download = 1` (configuração do admin); mesmo autorizado, a aba **Organizador** e as **Configurações** permanecem restritas ao admin. O switch `empenhos_renomeacao_automatica` não afeta permissões — apenas o gate do job automático.

## Rota e integrações

- Rota: `/renomear-empenho` (chave `empenhos`) — `main.py`.
- Contrato obrigatório `mostrar_tela(usuario_logado, perfil)` em `telas.py` (validado pelo `main.py`).
- Job `monitor_empenho` no APScheduler (`mod_intranet/rotinas.py`) — `rodar_monitor` levanta (`levantar_arquivos`) e varre a raiz de todas as pastas; gate `renomeacao_automatica_empenho_ativa()` (`rotinas.py:194`) lê `empenhos_renomeacao_automatica`.
- Integrações: `mod_intranet.email_util.enviar_email` (SMTP central) para envio de solicitações; `mod_intranet.autenticacao.eh_admin_do_modulo`; `mod_intranet.aba_modulo.cabecalho` (o `tema_modulo.campo_modulo` foi removido — a edição do módulo é exclusiva de `/configuracoes`). O cabeçalho usa `chave_modulo="empenhos"` (`telas.py:85`): a borda de destaque é a **mesma cor dos botões do módulo** (`empenhos_cor_botao`, vazia = padrão via `PADROES_TEMA` — todos os módulos em `#000000`, a cor do intranet), título/fundo seguem o tema — sem hex hardcoded.
- Chaves de configuração em `tb_config` (preferencialmente com prefixo `empenhos_` — ver [Configurações](../configuracoes.md)): `empenhos_pastas_monitoradas` (multi-linha local/UNC), `empenhos_monitor_intervalo_seg` (60 s), **`empenhos_renomeacao_automatica` (1/0)**, `empenhos_autorizar_download` (1/0), `empenhos_template_nome`, `empenhos_organizador_paginas_pasta`/`empenhos_organizador_pastas_caixa`, `empenhos_*` de aparência.
- Pastas (dentro do módulo, criadas sob demanda): `mod_renomear_empenho/doc/` (padrão), `mod_renomear_empenho/quarentena/`, `mod_renomear_empenho/organizadorPasta/`, `mod_renomear_empenho/downloads/`, `mod_renomear_empenho/datahora_*PDF/`, `mod_renomear_empenho/tmp_ferramentas_pdf/`.
- **Anti-disconnect (§5.1):** handlers de I/O pesado (`_filtrar`, `_enviar_lote` em `telas.py`) são `async` + `await run.io_bound(...)` com spinner `aria-label` e trava `ocupado` — nunca bloqueiam o event-loop.

## Testes

- `test/teste_fluxo_renameador.py` cobre: processamento DOC e tipos especiais EC/EE/EG, gate de validação, não-reprocessamento, classificação, fluxo de solicitações e navegação. Determinístico (roda 2x); isola `pastas_monitoradas` via monkeypatch para não vazar configuração central.
- `data-testid` para QA Playwright: `empenhos-navegar-pesquisa`, `empenhos-navegar-contagem`, `empenhos-lote-*`, `empenhos-reprocessar-fila-admin`, `empenhos-revisar-*`, `empenhos-gerar-25-temp` (TEMPORÁRIO — só QA, remover em produção).

## Pontos de atenção

- `bd_criador.py` **morto** — não confiar; o esquema real está em `bd_manipulador.py`.
- **Módulo indisponível — causa e reativação (22/09/2026)**: se o menu/rota `/renomear-empenho` sumir, a causa é `tb_modulos.ativo=0` para a chave `empenhos` no banco central (`db_mod_intranet.db`) — o seed de `_garantir_tb_modulos` (`mod_intranet/autenticacao.py`) usa `INSERT OR IGNORE` e **nunca religa** um módulo já desativado. Para reativar: `/configuracoes` → aba **Módulo** → linha `empenhos` → ligar o switch **Ativo** → Aplicar; ou via SQL `UPDATE tb_modulos SET ativo=1 WHERE chave='empenhos';` (com o servidor parado). Os módulos `auditoria` e `usuarios` são indispensáveis e não podem ser desativados (tentativa recusada no backend).
- Monitor automático é **não recursivo** (apenas a raiz das pastas monitoradas); levantamento e navegação/fila manuais são recursivas; levantamento anota recursivamente mas o processamento automático continua só na raiz.
- O intervalo do monitor (padrão **600 s = 10 min**) e a lista de pastas são lidos de `tb_config` e aplicados **sem reiniciar**; o switch `empenhos_renomeacao_automatica` também vale sem reiniciar (gate no job).
- `tb_levantamento_fts` é **VIRTUAL TABLE FTS5 exclusiva do SQLite** — no Postgres o `CREATE VIRTUAL TABLE` é ignorado e `pesquisar_levantamento` usa `LIKE`; comportamento esperado via `banco_conexao`.
- Auditoria do módulo **não aparece** na admin — consulte o menu **Auditoria**.

Ver [Análise do Módulo](../analise_mod_renomear_empenho.md) e [Manual de Uso](../manual_de_uso_renomear_empenho/index.md) para RFs/RNFs e operação.
