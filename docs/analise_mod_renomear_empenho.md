# Renomear Empenhos — `mod_renomear_empenho`

> Módulo de renomeação de empenhos: rota `/renomear-empenho` (chave `empenhos`) · banco próprio `db_mod_renomear_empenho.db` · extração de texto de PDF (excl. tipos EC/EE/EG/AE), monitor multi-pasta (local/UNC), fila, pesquisa FTS5, organizador físico, solicitações comum→admin e configurações.

---

# Renomear Empenhos — `mod_renomear_empenho`

> Módulo de renomeação de empenhos: rota `/renomear-empenho` (chave `empenhos`) · banco próprio `db_mod_renomear_empenho.db` · extração de texto de PDF por regex dinâmica, tipos especiais EC/EE/EG/AE, quarentena, renomeação sequencial, organizador físico e fluxo de solicitações.

## Propósito

Extrai o nº do empenho/parcela (ou tipo especial EC/EE/EG/AE) do texto dos PDFs, renomeia sequencialmente e move falhas para quarentena reprocessável. Inclui organizador físico em caixas/subpastas, edição e ferramentas de PDF, e o fluxo completo de solicitação de envio. O processamento é **manual** (botão "Processar pasta agora", abas Fila/Navegar) e **automático** via job `monitor_empenho` do APScheduler (**RF-40**, intervalo padrão 60 s, configurável em `empenhos_monitor_intervalo_seg` sem restart — `mod_intranet/rotinas.py:36-70,229`).

### Tela — 6 abas internas

A tela `/renomear-empenho` é organizada em abas manuais (padrão `mod_solicita_impressao/telas.py`), sem alterar o menu lateral global:

| Aba | Acesso | Conteúdo |
|:---|:---|:---|
| Navegar | todos | navegação recursiva/protegida (só PDFs), breadcrumb, baixar, revisar/renomear manual, solicitar envio, "Processar pasta agora" |
| Fila Renomeação | todos | pendentes recursivos, "Processar" individual e "Processar todos" |
| Pesquisar | todos | busca FTS5 + tabela de empenhos renomeados |
| Organizador | **admin** | organizar caixas, capas/matriz, validar matriz, inventário, ferramentas de PDF |
| Solicitação | todos (admin gerencia) | fluxo comum→admin: e-mail/ZIP/recusa, lotes, histórico |
| Configurações | **admin** | pastas monitoradas, aparência, template, campos, auditoria, quarentena, regras |

Admin = `administrador_geral` ou `eh_admin_do_modulo(usuario, "empenhos")` (`telas.py:76`).

## Banco próprio

Criador vigente: `init_db_empenho()` em `manipulador_bd.py:289`.

| Tabela | Conteúdo |
|:---|:---|
| `tb_empenhos` | nome original/final, numero_empenho, parcela, **tipo_especial**, ficha, ano, usuario, data, status ('ativo'), caminho; índice por número |
| `tb_indexador_pesquisa` | fallback comum (`empenho_id`, `conteudo_texto`) |
| `tb_indexador_pesquisa_fts5` | **VIRTUAL TABLE FTS5 com 32 colunas** do cabeçalho (RF-41); alimentada por trigger de exclusão + `reindexar_empenho()` |
| `tb_quarentena` | nome_arquivo, motivo, caminho_atual, data_insercao, processado |
| `tb_regex_regras` | nome_regra UNIQUE, padrao_regra, substituicao, ativo, **campo_destino** (FTS customizado) |
| `tb_campos_busca` | regex por campo (ficha/empenho/parcela/ano...) editável sem tocar no código |
| `tb_arquivos_auditoria` | trilha por arquivo (detectado→renomeado→removido) com **SHA-256** de origem/destino |
| `tb_eventos_arquivos` | linha do tempo cronológica por arquivo (FK `tb_arquivos_auditoria`) |
| `tb_solicitacoes` | fluxo comum→admin: pendente → enviado | zip_gerado → recusado; `lote_id`, `metodo_envio`, `caminho_zip`, `motivo_recusa` |

⚠️ O `criador_bd.py` é **legado/morto** (esquema FTS5 fantasma no banco central) — não executar; o esquema real está em `manipulador_bd.py`.

## Fluxo da tela

Acesso pela chave do módulo `empenhos`; perfil define o que é visível (abas admin ocultas/restritas). Detalhes por aba em [Módulos (resumo)](../modulos/renomear_empenho.md).

## RFs / RNFs do módulo

> Numeração herdada do roadmap do sistema; o código executável prevalece sobre a documentação.

### Requisitos funcionais (RF)

| RF | Descrição | Situação |
|:---|:---|:---|
| RF-001 | Parametrização do padrão/monitor no modo manutenção (`tb_campos_busca` editável) | ✅ Implementado |
| RF-002 | Consulta avançada com seleção por conteúdo (FTS5 + fallback LIKE) | ✅ Implementado (FTS5, máx. 50) |
| RF-003 | Envio/exportação de cópia em ZIP (fluxo solicitação → ZIP/e-mail) | ✅ Implementado |
| RF-004 | Gestão granular de permissão para download (`renomear_autorizar_download`) | ✅ Implementado |
| RF-005 | Índice de busca textual (FTS) e extração preditiva | ✅ Implementado (`tb_indexador_pesquisa_fts5`, 32 colunas) |
| RF-006 | Renomeação automática opcional (monitor `sistema`) | ✅ Implementado (job + manual) |
| RF-007 | Biblioteca de leitura de PDF configurável (fallback) | ✅ Implementado (pipeline de extração) |
| RF-008 | Tipos especiais de documento (EC/EE/EG/AE) | ✅ Implementado (`detectar_tipo_especial`/`extrair_dados_tipo_especial`) |
| RF-009 | Organizador de documentos físicos | ✅ Implementado (caixas/subpastas + capas/matriz) |
| RF-39 | Ações de usuário comum (e-mail/ZIP/download) | ✅ Implementado |
| RF-40 | Monitor de pasta automático | ✅ Implementado (APScheduler, intervalo 60 s) |
| RF-41 | Indexação FTS5 do cabeçalho | ✅ Implementado (32 colunas + campos customizados) |
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

- **Extração** (pipeline tolerante a escaneados, `manipulador_bd.py:466`): `pymupdf → pdfplumber → OCR (pytesseract, por+eng) → pikepdf`. PDF sem texto vai à quarentena ("possivelmente escaneado").
- **Renomeação**: contador sequencial persistido em banco, único entre pastas; tipos especiais usam nome próprio. Template de nome configurável.
- **Organizador**: distribui renomeados em `organizadorPasta/caixa_NN/sub_X` (~200 páginas/pasta, 4 pastas/caixa, configuráveis); gera `capa.txt`/`matrizDeDocumentos.txt/.pdf` e valida presença.
- **Solicitações**: `pendente → (email) enviado | (ZIP) zip_gerado → confirmar | recusado`; agrupadas por `lote_id`; ZIP em `downloads/solic_*.zip`.
- **Auditoria**: ações `processar`, `revisao_manual`, `solicitacao*`, `configuracao`, `quarentena` na trilha central **com hash SHA-256**; + trilha por arquivo local.

## Integrações com o núcleo

- `mod_intranet.conexao_bd` (`get_config`/`set_config` — chaves `empenhos_*` e `renomear_autorizar_download`).
- `mod_intranet.autenticacao.eh_admin_do_modulo` (permissão por aba).
- `mod_intranet.rotinas` (job `monitor_empenho`, `intervalo_monitor_empenho`, `reagendar_monitor_empenho`).
- `mod_intranet.email_util.enviar_email` — envio de solicitações por SMTP.
- `mod_intranet.aba_modulo.cabecalho` e `mod_intranet.tema_modulo.campo_modulo`.
- `audit_log` (central, com hash).

## Pontos de atenção

- `criador_bd.py` **morto** com esquema FTS5 fantasma — fonte de confusão; não executar.
- Monitor automático varre **só a raiz** de cada pasta monitorada; navegação/fila manuais são **recursivas** (comportamento intencional) — não equivaler automaticidade a recursividade.
- Intervalo padrão do monitor é **60 s** (não 10 s); ajustado em `mod_intranet/rotinas.py:36`.

## Status — Fases do PLANO

**Implementado:** banco próprio em WAL; auditoria central com hash SHA-256; perfis/papéis por módulo; fila de quarentena com motivo e reprocessamento (regex aplicada na hora); regex dinâmicas persistidas (com `campo_destino` para FTS); renomeação automática sequencial; organizador físico completo (capas/matriz); indexação FTS5 (RF-41); ferramentas de PDF (RF-45); monitor automático multi-pasta (RF-40); ações de usuário comum (RF-39); tipos especiais EC/EE/EG/AE corrigidos; gate de validação; trilha por arquivo; solicitações comum→admin.

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
| Auditoria em `auditoria.db`/`indice.db` separados | `tb_auditoria` central + banco próprio do módulo (`tb_arquivos_auditoria`/`tb_eventos_arquivos`) |
| Índice FTS5 (30 campos) | `tb_indexador_pesquisa_fts5` com **32 colunas** + campos customizados |
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

### Lacunas / diferenças assumidas

- **EX** (tipo especial adicional citado na referência) não foi portado — a extração cobre EC/EE/EG/AE.
- A referência tinha **pesquisa ao vivo** com yield progressivo; aqui a busca FTS5 é por atualização do campo, com limite de resultados.
- Editor de PDF e gestão **não** ficam dentro da tela dos empenhos — permanecem como módulos independentes (escopo definido na portabilidade).
- Intervalo de varredura foi elevado (60 s) para reduzir I/O em ambiente de rede; ajustável sem reiniciar.
