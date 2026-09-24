# Empenho Renamer — `mod_renomear_empenho` — Module Analysis

> Empenho PDF renaming module: route `/renomear-empenho` (key `empenhos`) · own DB `db_mod_renomear_empenho.db` · text extraction with dynamic regex (incl. special types EC/EE/EG/AE), multi-folder monitor (local/UNC), queue, FTS5 search, quarantine with individual+batch reprocessing without restart, physical organizer (`capa.pdf/txt` + `matrizDeDocumentos.pdf/.txt`) and common→admin request flow.

---

# Renomear Empenhos — `mod_renomear_empenho` — Análise do Módulo

> Módulo de renomeação de empenhos: rota `/renomear-empenho` (chave `empenhos`) · banco próprio `db_mod_renomear_empenho.db` · extração de texto de PDF por regex dinâmica, tipos especiais EC/EE/EG/AE, quarentena com reprocessamento individual e em lote sem reiniciar, organizador físico com `capa.pdf/txt` e `matrizDeDocumentos.pdf/.txt` e fluxo de solicitações comum→admin.

## Propósito

Extrai o nº do empenho/parcela (ou tipo especial EC/EE/EG/AE) do texto dos PDFs, renomeia sequencialmente e move falhas para quarentena reprocessável. Inclui organizador físico em caixas/subpastas, edição e ferramentas de PDF, e o fluxo completo de solicitação de envio. O processamento é **manual** (botão "Processar pasta agora", abas Fila/Navegar) e **automático** via job `monitor_empenho` do APScheduler (**RF-40**, intervalo padrão 60 s, configurável em `empenhos_monitor_intervalo_seg` sem restart — `mod_intranet/rotinas.py:36-70,229`).

### Tela — 6 abas internas

A tela `/renomear-empenho` (`telas.py:mostrar_tela`) tem **4 abas** (admin: Navegar, Fila, Organizador, Solicitação; comum: só Navegar). A busca FTS5 vive no campo de pesquisa do Navegar e as Configurações no painel standalone (`telas_administracao.py`, `/admin/empenhos`):

| Aba | Acesso | Conteúdo |
|:---|:---|:---|
| Navegar | todos | navegação recursiva/protegida (só PDFs), breadcrumb, baixar, revisar/renomear manual (`renomear_manual` com gate + edição ficha/parcela/ano), solicitar envio, "Processar pasta agora" |
| Fila Renomeação | todos | pendentes recursivos, "Processar" individual e "Processar todos" |
| Organizador | **admin** | organizar caixas, capas/matriz (`gerar_matriz_organizador`/`validar_presenca_matriz`), inventário, ferramentas de PDF |
| Solicitação | todos (admin gerencia) | fluxo comum→admin: e-mail/ZIP/recusa, lotes, histórico |
| Configurações | **admin, painel `/admin/empenhos`** | pastas monitoradas, aparência, template, campos, quarentena (4b), regras com `valida_regex` anti-ReDoS |

Admin = `administrador_geral` ou `eh_admin_do_modulo(usuario, "empenhos")` (`telas.py:76`).

## Banco próprio

Criador vigente: `init_db_empenho()` em `bd_manipulador.py:289`.

| Tabela | Conteúdo |
|:---|:---|
| `tb_empenhos` | nome original/final, numero_empenho, parcela, **tipo_especial**, ficha, ano, usuario, data, status ('ativo'), caminho; índice por número |
| `tb_indexador_pesquisa` | fallback comum (`empenho_id`, `conteudo_texto`) |
| `tb_indexador_pesquisa_fts5` | **VIRTUAL TABLE FTS5 (59 colunas de `FTS_COLS`, RF-41)**; alimentada por `reindexar_empenho()` + trigger de exclusão + `campo_destino` nas regras |
| `tb_quarentena` | nome_arquivo, motivo, caminho_atual, data_insercao, processado |
| `tb_levantamento` | **inventário vivo** — `nome_arquivo`, `caminho_atual UNIQUE`, `presente` (1/0), `status` (detectado/renomeado), `numero_empenho`, `parcela`, `ficha`, `ano`, `tipo_especial`, **`usuario` (ator do reconhecimento, `TEXT`, CREATE + `_migrar_coluna` idempotente)**, `conteudo_texto` (≤20k), `tamanho`, `mtime`, `data_deteccao`, `data_visto` |
| `tb_regex_regras` | nome_regra UNIQUE, padrao_regra, substituicao, ativo, **campo_destino** (FTS customizado) |
| `tb_campos_busca` | regex por campo (ficha/empenho/parcela/ano...) editável sem tocar no código |
| `tb_arquivos_auditoria` | trilha por arquivo (detectado→renomeado→removido) com **SHA-256** de origem/destino |
| `tb_eventos_arquivos` | linha do tempo cronológica por arquivo (FK `tb_arquivos_auditoria`) |
| `tb_solicitacoes` | fluxo comum→admin: pendente → enviado | zip_gerado → recusado; `lote_id`, `metodo_envio`, `caminho_zip`, `motivo_recusa` |

⚠️ O `bd_criador.py` é **legado/morto** (esquema FTS5 fantasma no banco central) — não executar; o esquema real está em `bd_manipulador.py`.

## Fluxo da tela

Acesso pela chave do módulo `empenhos`; perfil define o que é visível (abas admin ocultas/restritas). Detalhes por aba em [Módulos (resumo)](modulos/renomear_empenho.md).

## RFs / RNFs do módulo

> Numeração herdada do roadmap do sistema; o código executável prevalece sobre a documentação.

### Requisitos funcionais (RF)

| RF | Descrição | Situação |
|:---|:---|:---|
| RF-001 | Parametrização do padrão/monitor no modo manutenção (`tb_campos_busca` editável) | ✅ Implementado |
| RF-002 | Consulta avançada com seleção por conteúdo (FTS5 + fallback LIKE) | ✅ Implementado (FTS5, máx. 50) |
| RF-003 | Envio/exportação de cópia em ZIP (fluxo solicitação → ZIP/e-mail) | ✅ Implementado |
| RF-004 | Gestão granular de permissão para download (`renomear_autorizar_download`) | ✅ Implementado |
| RF-005 | Índice de busca textual (FTS) e extração preditiva | ✅ Implementado (`tb_indexador_pesquisa_fts5`, 59 colunas) |
| RF-006 | Renomeação automática opcional (monitor `sistema`) | ✅ Implementado (job + manual) |
| RF-007 | Biblioteca de leitura de PDF configurável (fallback) | ✅ Implementado (pipeline de extração) |
| RF-008 | Tipos especiais de documento (EC/EE/EG/AE) | ✅ Implementado (`detectar_tipo_especial`/`extrair_dados_tipo_especial`) |
| RF-009 | Organizador de documentos físicos | ✅ Implementado (caixas/subpastas + capas/matriz) |
| RF-39 | Ações de usuário comum (e-mail/ZIP/download) | ✅ Implementado |
| RF-40 | Monitor de pasta automático | ✅ Implementado (APScheduler, intervalo 60 s) |
| RF-41 | Indexação FTS5 do cabeçalho | ✅ Implementado (59 colunas + campos customizados) |
| RF-44 | Organizador completo com capas e matriz | ✅ Implementado (`gerar_matriz_organizador`, `validar_presenca_matriz`) |
| RF-45 | Ferramentas de PDF embutidas (cortar/juntar/reduzir) | ✅ Implementado |

### Requisitos não funcionais (RNF)

| RNF | Descrição | Situação |
|:---|:---|:---|
| RNF-01 | Banco SQLite próprio em modo **WAL** | ✅ Toda conexão aplica `PRAGMA journal_mode=WAL` |
| RNF-02 | Auditoria rastreável com **hash SHA-256** | ✅ `tb_arquivos_auditoria` (origem/destino) + `audit_log` central |
| RNF-03 | Perfis/papéis por módulo (validação de acesso por aba) | ✅ `eh_admin_do_modulo`/`administrador_geral` |
| RNF-04 | Execução em intranet; sem dependência de CDN | ✅ Tailwind servido localmente |
| RNF-05 | Configuração aplicada **sem reiniciar o servidor** | ✅ `tb_config` (pastas, intervalo, template, campos) |
| RNF-06 | Tolerância a falta de rede/UNC (não derruba o monitor) | ✅ `pasta_acessivel` pula pastas inacessíveis |
| RNF-07 | Não-reprocessamento idempotente | ✅ `arquivo_ja_processado` + `_arquivo_registrado_no_bd` |
| RNF-08 | Segurança de navegação (anti-travessia de diretórios) | ✅ `raizes_navegacao`/`pasta_navegavel` |

### Adições além da referência (implementadas)

- **Monitor multi-pasta** local + **rede/UNC** (`\\servidor\...`, `E:\scan`) — uma por linha, na raiz (não recursivo); suporta vários computadores escaneando.
- **Correção de tipos especiais**: antes capturava o nº do empenho complementado (66) em vez do nº do documento (24). Agora `detectar_tipo_especial` decide AE>EC>PARCELA>Tipo>Nota de Empenho e nomeia `EC_0024.pdf`, `EE_9570.pdf`, `EG_0089.pdf`.
- **Gate de validação** (PLANO 4c): renomeação somente com nº identificado sem divergência crítica; falha → quarentena com motivo.
- **Revisão manual com normalização** (`renomear_manual`) + anti-colisão (`_v2`).
- **Trilha por arquivo** (`tb_arquivos_auditoria` + `tb_eventos_arquivos`) no banco do módulo.
- **Não-reprocessamento DB-aware** para tipos especiais (cujo nome não discrimina por contagem de dígitos).

## Regras de negócio relevantes

- **Extração** (pipeline tolerante a escaneados, `bd_manipulador.py:475`): `pymupdf → pdfplumber → OCR (pytesseract, por+eng) → pikepdf` (fallback com ordem `pymupdf` primeira; plano previa `pytesseract→pdfplumber→pikepdf→pymupdf` — libs idênticas, ordem otimizada para nativo primeiro). `cp1252`/`Latin-1` e mojibake neutralizados via normalização de texto (`?` tolerante); PDF sem texto vai à quarentena ("possivelmente escaneado").
- **Renomeação**: contador sequencial persistido em banco, único entre pastas; tipos especiais usam nome próprio. Template de nome configurável.
- **Quarentena e regras dinâmicas (4b)**: falha de extração/validação ou PDF sem texto → `mover_quarentena`/`promover_quarentena` (`bd_manipulador.py:1530`) com motivo truncado a 300 chars, cópia para `mod_renomear_empenho/quarentena/<timestamp>_<nome>` e registro em `tb_quarentena`. **Identificação manual**: diálogo "Revisar/renomear" na Navegar (`renomear_manual` com gate) normaliza o nome sem reiniciar. **Regex dinâmico**: `tb_regex_regras` (`nome_regra UNIQUE`, `padrao_regra`, `ativo`, `campo_destino` → coluna FTS) editável em Configurações/Quarentena; `salvar_regra` valida `re.compile` antes de gravar e vale **sem reiniciar** (lida a cada `processar_pdf`/`extrair_numero`). **Reprocessamento**: individual — clique na linha da quarentena → "Reprocessar com nova regex" (`reprocesse_quarentena(qid, novo_padrao)`); em lote — botão **"Reprocessar fila"** (`reprocessar_fila(usuario, novo_padrao)`, `bd_manipulador.py:1792`) itera todos `processado=0` com regras ativas e reporta `sucessos/total` sem reiniciar (aliases PLANO: `promover_quarentena`→`mover_quarentena`, `reprocessar_fila`→batch). **Múltiplos documentos**: `detectar_documentos_no_pdf`/`eh_multiplo_documento` (`bd_manipulador.py:815`) agrupa por `_inicio_documento`; quarentena com motivo "Múltiplos documentos detectados (N empenhos: ...)" oferece botão **"Separar documentos"** (`separar_documentos_quarentena`/`separar_pdf_por_documentos`) que divide em `*_parteNN_pA-B.pdf`, move para a pasta monitorada e reprocessa cada parte.
- **Organizador físico (4c)**: distribui renomeados em `mod_renomear_empenho/organizadorPasta/caixa_NN/sub_X` com **~200 páginas por subpasta e 4 pastas por caixa** (padrões configuráveis via `tb_config` `empenhos_organizador_paginas_pasta`/`empenhos_organizador_pastas_caixa`, `bd_manipulador.py:1988`). Ao final, `gerar_matriz_organizador` (`bd_manipulador.py:2090`) gera **capa por caixa** (`organizadorPasta/caixa_NN/capa.txt` **e** `capa.pdf` via pymupdf) e **matriz geral** (`organizadorPasta/matrizDeDocumentos.txt` **e** `matrizDeDocumentos.pdf`). `validar_presenca_matriz` (`bd_manipulador.py:2121`) confere que todo `.pdf` listado na matriz existe em disco; `organizar_pastas` já encadeia a geração de capas/matriz e retorna `"<N> organizado(s). Matriz gerada (TOTAL documentos)."`.
- **Solicitações**: `pendente → (email) enviado | (ZIP) zip_gerado → confirmar | recusado`; agrupadas por `lote_id`; ZIP em `mod_renomear_empenho/downloads/solic_*.zip`.
- **Auditoria**: ações `processar`, `revisao_manual`, `solicitacao*`, `configuracao`, `quarentena`, `separar_documentos` na trilha central **com hash SHA-256**; + trilha por arquivo local (`tb_arquivos_auditoria`/`tb_eventos_arquivos`).

## Integrações com o núcleo

- `mod_intranet.bd_conexao` (`get_config`/`set_config` — chaves `empenhos_*` e `renomear_autorizar_download`).
- `mod_intranet.autenticacao.eh_admin_do_modulo` (permissão por aba).
- `mod_intranet.rotinas` (job `monitor_empenho`, `intervalo_monitor_empenho`, `reagendar_monitor_empenho`).
- `mod_intranet.email_util.enviar_email` — envio de solicitações por SMTP.
- `mod_intranet.aba_modulo.cabecalho` (`campo_modulo` removido — edição do módulo é exclusiva de `/configuracoes`).
- `audit_log` (central, com hash).

## Pontos de atenção

- `bd_criador.py` **morto** com esquema FTS5 fantasma — fonte de confusão; não executar.
- Monitor automático varre **só a raiz** de cada pasta monitorada; navegação/fila manuais são **recursivas** (comportamento intencional) — não equivaler automaticidade a recursividade.
- Intervalo padrão do monitor é **600 s (10 min)**; ajustado em `mod_intranet/rotinas.py` (`intervalo_monitor_empenho`), alterável pelo usuário na tela do módulo.

## Status — Fases do PLANO (4b/4c concluídos)

**Implementado:** banco próprio em WAL; auditoria central com hash SHA-256; perfis/papéis por módulo; **quarentena com motivo + reprocessamento individual e em lote sem reiniciar** (`promover_quarentena`/`mover_quarentena`, `reprocesse_quarentena` + `reprocessar_fila` com botão "Reprocessar fila" — PLANO 4b); **regex dinâmicas persistidas** (`campo_destino` → FTS) com identificação manual (`renomear_manual`) e cadastro sem reiniciar; **separação de múltiplos documentos** (`detectar_documentos_no_pdf`/`separar_documentos_quarentena` com botão "Separar documentos"); renomeação automática sequencial; **organizador físico completo (PLANO 4c)** — ~200 páginas/subpasta, 4 subpastas/caixa (configuráveis), **capas `capa.txt` + `capa.pdf` por caixa** e `matrizDeDocumentos.txt/.pdf` geral com `validar_presenca_matriz` em `mod_renomear_empenho/organizadorPasta/`; indexação FTS5 (RF-41); ferramentas de PDF (RF-45); monitor automático multi-pasta (RF-40); ações de usuário comum (RF-39); tipos especiais EC/EE/EG/AE corrigidos; gate de validação; trilha por arquivo; solicitações comum→admin.

---

## Comparação com a documentação de referência

> Avaliação da documentação do sistema de origem (aplicativo "renomeador de empenhos" standalone) frente ao que foi portado para a intranet modular.

### O que a referência documentava — o que foi implementado

A documentação de referência (levantamento de requisitos + manual) descrevia um app **autônomo** com: monitor por regex, tipos especiais EC/EE/EG/AE/EX, renomeação automática opcional, índice FTS5 (30 campos de fábrica), busca ao vivo, organizador físico com capas, gestão de usuários CRUD, "meu perfil", editor de PDF (enviar/merge/reduzir/dividir com auditoria SHA256), solicitações em lote e auditoria em bancos separados.

Mapeamento para esta implementação:

| Referência | Nesta implementação |
|:---|:---|
| App standalone (login próprio + gestão de usuários + perfil) | Intranet modular reutiliza `mod_gest_cad_usuario`/`mod_intranet` (login, perfis, troca de senha) — **não duplicado** |
| Editor de PDF (abas ENVIAR/auditoria PDF/scanner) | Já existe como módulo próprio `/edit-pdf` — **não duplicado** |
| Auditoria em `auditoria.db`/`indice.db` separados | Banco exclusivo de auditoria (`db_mod_auditoria.db`, tabela `tb_auditoria_renomear_empenho`) + banco próprio do módulo (`tb_arquivos_auditoria`/`tb_eventos_arquivos`) |
| Índice FTS5 (30 campos) | `tb_indexador_pesquisa_fts5` com **59 colunas (`FTS_COLS`)** + campos customizados |
| Tipos EC/EE/EG/AE/EX | EC/EE/EG/AE implementados; a desambiguação pelo conteúdo foi **corrigida** (nº do documento, não do empenho complementado) |
| Monitor de pasta único (intervalo ~4 s) | Monitor **multi-pasta** (local/UNC, um por linha), intervalo padrão **60 s** |
| Renomeação mesmo sem validação total | **Gate de validação** adicionado (renomeia só com nº identificado) |
| Organizador com capas | Implementado com capas + `matrizDeDocumentos` + validação de presença |
| Solicitações em lote (comum→master) | Implementado com agrupamento por lote, e-mail (SMTP central) e ZIP |
| Ferramentas de PDF embutidas | Implementado (reusa `mod_edit_pdf`); corte/mesclar/reduzir |

### Ganhos da portabilidade para a intranet

- **Segurança/perfis** unitários: usuários, sessões revogáveis, perfil por módulo e auditoria central com SHA-256 — em vez de gestão de usuários própria do app standalone.
- **Configuração central** em `tb_config` (sem `config.json`) com efeito **sem reiniciar**.
- **Não-reprocessamento** e **gate de validação** que a referência não garantia.
- **Anti-travessia** na navegação e suporte nativo a **pasta de rede/UNC**.
- **Sem duplicação**: editor de PDF, usuários e auditoria continuam nos módulos próprios.

### Adições recentes (09/2026) — responsividade global RNF-UI-01

- **Auditado 320/768/1024** (`kbp-web-design`) — proposta P0/P1/P2 por `container`/`row`/`grid`: `menu_modulo` `overflow-x-auto`, filtros/busca `flex-wrap` `flex-1 min-w`, tabelas `overflow-x-auto`, `scroll_area` altura explícita, grids `grid-cols-1 sm:grid-cols-2 md:grid-cols-3`, dialogs `w-full max-w`; header `flex-wrap` `truncate`. Ver [Padrões](padroes_codificacao/index.md) §8.1.

### Adições recentes (14/09/2026) — levantamento grava usuário + listagem exibe empenho/parcela/usuário

- **Leitura no reconhecimento grava todos os campos + usuário:** `levantar_arquivos(usuario)` (`bd_manipulador.py:1614`) extrai nº/ficha/parcela/ano/tipo + conteúdo (≤20k) e grava o **ator no `INSERT`** de `tb_levantamento`; na **releitura** (mesmo `tamanho`/`mtime`) atualiza `presente=1`/`status`/`data_visto` e na **revisita adota o usuário logado sem que o agendador `"sistema"` sobrescreva nome real** (só adota quando o ator ≠ `"sistema"` e o dono está vazio ou é `"sistema"`).
- **Anotação para exibição:** novo `anotar_arquivos(pdfs)` (`bd_manipulador.py:2624`) anexa `numero_empenho`/`parcela`/`usuario`/`data` do levantamento a cada dict de listagem; quando o arquivo já foi processado, **sobrescreve com `tb_empenhos`** (nº/parcela/usuário de quem processou, com fallback ao nome final `doc_<cont>_<empenho>_<parcela>.pdf` / `EC|EE|EG|AE_<n>.pdf`). `listar_navegacao` e `listar_pendentes` retornam os dicts já anotados; `pesquisar_levantamento` retorna também `parcela` e `usuario`.
- **Listagem exibe nome/empenho/parcela/usuário:** abas **Navegar** e **Fila** (lista, cabeçalhos e resultados de pesquisa) exibem as colunas **Arquivo, Empenho, Parcela, Usuário, Data, Status** (+ Pasta/Ações no Navegar); valores vêm da leitura do reconhecimento/processamento, com **zeros à esquerda normalizados só na exibição**. A aba **Pesquisar** já tinha a coluna Usuário e foi mantida.
- **Validado:** `ast.parse` OK, migração aplicada (`PRAGMA table_info(tb_levantamento)` confirma `usuario`), `listar_navegacao` real retorna empenho/parcela/usuario/data, 2 restarts com `/login` 200.

### Adições recentes (14/09/2026) — botão TEMPORÁRIO de massa de teste (REMOVER em produção)

!!! warning "TEMPORARIO-25-ARQUIVOS-REMOVER-EM-PRODUCAO — remover antes de produção"
    O botão **"Gerar 25 (TEMP)"** (`mod_renomear_empenho/telas.py:153-183`) é **só para QA** e **NÃO pode ir para produção** — remover o bloco marcado + o handler `_gerar_25_temp`.

- **Onde/comportamento:** totalmente à direita do `menu_mod` (row `justify-between flex-nowrap`: `ui.tabs` `flex-1 min-w-0 overflow-x-auto` à esquerda e botão `shrink-0 ml-auto` à direita), rótulo "Gerar 25 (TEMP)" ícone `science` variante `secundario` `data-testid=empenhos-gerar-25-temp`; **cada clique = +25 PDFs fictícios** na 1ª pasta de `pastas_monitoradas()` (fallback `_PASTA_MONITORADA_PADRAO` = `mod_renomear_empenho/doc`) via `assets/test/fabrica_documentos.py:criar_lote_principal(pasta_doc, quantidade=25)`; handler async `_gerar_25_temp` com `await run.io_bound(_criar)` (anti-disconnect AGENTS.md §5.1); audita `audit_log(usuario,"empenhos","gerar_massa_temp",...)` com `notificar` positiva/negativa. Detalhe e arquivos:linhas em [Módulos (resumo)](modulos/renomear_empenho.md) ("Botão TEMPORÁRIO de massa de teste").

### Lacunas / diferenças assumidas

- **EX** (tipo especial adicional citado na referência) não foi portado — a extração cobre EC/EE/EG/AE.
- A referência tinha **pesquisa ao vivo** com yield progressivo; aqui a busca FTS5 é por atualização do campo, com limite de resultados.
- Editor de PDF e gestão **não** ficam dentro da tela dos empenhos — permanecem como módulos independentes (escopo definido na portabilidade).
- Intervalo de varredura foi elevado (60 s) para reduzir I/O em ambiente de rede; ajustável sem reiniciar.
