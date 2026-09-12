# Empenho Renamer — User Manual — Intranet Modular

> Operational guide for the Empenho Renamer module (`/renomear-empenho`): folder monitoring (local/UNC), text extraction with dynamic regex, sequential renaming, quarantine with batch reprocessing without restart, physical organizer with `capa.pdf/txt` and `matrizDeDocumentos.pdf/.txt`, and common→admin copy request flow. Screen split into 6 tabs: Browse, Rename Queue, Search, Organizer (admin), Request and Settings (admin).

---

# Manual de Uso — Renomeador de Empenho — Intranet Modular

> Guia operacional do módulo Renomeador de Empenho (`/renomear-empenho`), que monitora pastas, extrai, renomeia, indexa e organiza documentos de empenho, e atende ao fluxo de solicitação de cópia (comum → administrador). A tela é dividida em **6 abas**: Navegar, Fila Renomeação, Pesquisar, Organizador (admin), Solicitação e Configurações (admin). Quarentena com reprocessamento **individual e em lote sem reiniciar** (botão "Reprocessar fila") + separação de múltiplos documentos; organizador físico com **capas `capa.txt`/`capa.pdf` por caixa** e `matrizDeDocumentos.txt/.pdf`.

## Contexto

O módulo atende à função de almoxarifado/gestão de empenhos. Usuários `comum` navegam, pesquisam e (quando autorizados pelo administrador) baixam/solicitam cópias; o **Organizador** e as **Configurações** são exclusivos do administrador do módulo (ou `administrador_geral`).

## As abas

### 1. Navegar

- Navegação **recursiva** pelas pastas monitoradas e pelo organizador, mostrando apenas PDFs (com breadcrumb e botão de "pasta anterior").
- Cada PDF mostra o status (`processado` / `pendente`). Para pendentes: **baixar**, **revisar/renomear** (normaliza o nome conforme o conteúdo e o tipo — DOC, EC, EE, EG, AE) e **solicitar envio**.
- Botões: **Processar pasta agora** (varre a raiz de todas as pastas monitoradas, com resumo ok/total) e **Atualizar**.

### 2. Fila Renomeação

- Lista recursiva de PDFs ainda **pendentes** de renomeação.
- **Processar** individualmente ou **Processar todos**. Pastas inacessíveis (ex.: rede fora do ar) são puladas.

### 3. Pesquisar

- **Busca textual** via índice FTS5 (nome final, empenho, parcela, usuário e campos do cabeçalho indexado), com fallback `LIKE`.
- Tabela "Empenhos renomeados" com nome final, empenho, parcela, tipo, usuário e data.

### 4. Organizador *(admin — PLANO 4c)*

- **Organizar caixas**: distribui os renomeados em `mod_renomear_empenho/organizadorPasta/caixa_NN/sub_X` com **~200 páginas por subpasta e 4 subpastas por caixa** (padrões configuráveis em `tb_config` `empenhos_organizador_paginas_pasta`/`empenhos_organizador_pastas_caixa`; `bd_manipulador.py:1988`). O botão já encadeia a geração de capas/matriz e notifica `"<N> organizado(s). Matriz gerada (TOTAL documentos)."`.
- **Capas por caixa**: cada `caixa_NN` recebe **`capa.txt` e `capa.pdf`** (listagem de subpastas e documentos — `gerar_matriz_organizador`, `bd_manipulador.py:2090`; PDF gerado via pymupdf `_gerar_pdf_texto`). Local: `mod_renomear_empenho/organizadorPasta/caixa_NN/capa.txt` e `capa.pdf`.
- **Matriz geral**: `mod_renomear_empenho/organizadorPasta/matrizDeDocumentos.txt` **e** `matrizDeDocumentos.pdf` com cabeçalho, inventário por caixa/subpasta e `TOTAL DE DOCUMENTOS`.
- **Validar matriz** (`validar_presenca_matriz`, `bd_manipulador.py:2121`): verifica que **todo `.pdf` listado na matriz existe em disco** (`organizadorPasta/`); se `matrizDeDocumentos.txt` ausente, retorna `["matrizDeDocumentos.txt ausente - gere a matriz primeiro"]`.
- **Gerar capas/matriz**: botão independente para regenerar sem reorganizar.
- **Inventário** de caixas e subpastas (expansão com contagem por `sub_X`).
- **Ferramentas de PDF** (corte, mescla, redução) sobre empenhos processados ou PDFs enviados; saídas em `mod_renomear_empenho/datahora_cortePDF/`, `mod_renomear_empenho/datahora_mergePDF/`, `mod_renomear_empenho/datahora_reducaoPDF/`.

### 5. Solicitação *(todos; admin gerencia)*

- **Usuário comum**: solicita o envio de um documento informando seu e-mail (e mensagem opcional). A solicitação entra como `pendente`.
- **Administrador**: para cada solicitação (agrupada por lote) pode **Enviar por e-mail** (via SMTP central), **Gerar ZIP** (pega para envio manual e baixa o arquivo) ou **Recusar** (com motivo). ZIP gerado pode ser **Confirmar envio manual** ou **Cancelar ZIP** (volta a pendente).
- Expansão **Histórico completo**: todas as solicitações, com status e método de envio.

### 6. Configurações *(admin — inclui PLANO 4b)*

- **Pastas monitoradas** (uma por linha, local ou rede/UNC, ex.: `\\servidor\empenhos` ou `E:\scan`) — aplicado sem reiniciar.
- **Aparência**: cor dos botões, texto, fundo, título e tamanho.
- **Configurações específicas**: texto do cabeçalho, **intervalo do monitor automático** (recomendado 60 s) e autorização de download/ZIP/e-mail para comuns.
- **Nome final do arquivo**: template configurável com as variáveis `{contador}`, `{empenho}`, `{empenho_cru}`, `{parcela}`, `{ficha}`, `{ano}` e formatação de largura (ex.: `{contador:04d}`). Tipos especiais usam nome próprio (`EC_0024.pdf`).
- **Campos de busca (regex)**: identificar/cadastrar/editar as regex de cada campo (ficha/empenho/parcela/ano...) sem reiniciar.
- **Auditoria dos arquivos**: consulta da trilha detectado→renomeado→removido por status.
- **Quarentena (4b)**: itens com erro de leitura/regex ou **múltiplos documentos** vão para `mod_renomear_empenho/quarentena/<timestamp>_<nome>` (`mover_quarentena`/`promover_quarentena`, `bd_manipulador.py:1530`) com motivo até 300 chars. Na lista (pendentes `processado=0`): **clique na linha para reprocessar individualmente** — diálogo "Reprocessar com nova regex" (regex alternativa opcional → `reprocesse_quarentena(qid, novo_padrao)`) ou, quando o motivo contém "Múltiplos documentos detectados", botão **"Separar documentos"** (`separar_documentos_quarentena` → `detectar_documentos_no_pdf`/`separar_pdf_por_documentos` → `*_parteNN_pA-B.pdf` na pasta monitorada e reprocesso). **Botão "Reprocessar fila" (lote)** acima da tabela: `reprocessar_fila(usuario)` itera toda a fila pendente com as **regex ativas** (cadastro em "Regras de extração" vale **sem reiniciar**), marca `processado=1` nos sucessos e notifica `"Fila reprocessada: X/Y com sucesso"` — aliases PLANO `promover_quarentena`/`reprocessar_fila` mapeados no código. `data-testid="empenhos-reprocessar-fila"` para QA (Playwright).
- **Regras de extração**: regex dinâmicas (`tb_regex_regras`: `nome_regra UNIQUE`, `padrao_regra` validado por `re.compile`, `ativo`, `campo_destino` → coluna FTS), com ativação/inativação e campo FTS de destino; salvas por `salvar_regra` e aplicadas **sem reiniciar** (lidas a cada `processar_pdf`).

## Fluxos principais

- **Monitor de pastas:** varre a raiz de cada pasta monitorada (local/UNC), processando PDFs novos e registrando os removidos; em rede, pastas inacessíveis são puladas.
- **Extração:** fallback `pymupdf` → `pdfplumber` → OCR `pytesseract` → `pikepdf` (trata OCR e encoding `cp1252`/`Latin-1`, mojibake `?` tolerante).
- **Tipos especiais:** EC (complementação), EE (estimativo), EG (global) e AE (anulação) são detectados pelo conteúdo e renomeados com nome próprio.
- **Indexação FTS5:** busca por pagador, CPF, valor, órgão etc. (`tb_indexador_pesquisa_fts5`).
- **Quarentena (4b):** PDFs com erro de leitura/regex ou múltiplos documentos vão para `mod_renomear_empenho/quarentena/` com motivo; admin reprocessa **individualmente** (regex alternativa na hora via `reprocesse_quarentena`) **ou em lote sem reiniciar** (botão "Reprocessar fila" → `reprocessar_fila` com regras ativas); múltiplos documentos detectados por `_inicio_documento`/`detectar_documentos_no_pdf` trazem botão **"Separar documentos"** (`separar_documentos_quarentena` → `*_parteNN_pA-B.pdf`).
- **Identificação manual & Regex dinâmico (4b):** "Revisar/renomear" (`renomear_manual` com gate) normaliza nome sem reiniciar; cadastro de regex em `tb_regex_regras`/`tb_campos_busca` (`salvar_regra` valida `re.compile`, `campo_destino` opcional) vale imediatamente para o próximo `processar_pdf`.
- **Renomeação:** automática (monitor/botão) ou manual (filas/revisão), com **gate de validação** — só renomeia com nº identificado; anti-colisão (`_v2`) evita sobrescrever.
- **Organizador físico (4c):** subpastas **~200 páginas**, **4 pastas/caixa** (configuráveis), **capas `capa.txt` + `capa.pdf` por `caixa_NN`** e **matriz `matrizDeDocumentos.txt/.pdf`** geral em `mod_renomear_empenho/organizadorPasta/`; `validar_presenca_matriz` garante que todo PDF da matriz existe.
- **Solicitações:** comum pede cópia; admin envia por e-mail ou ZIP; tudo fica no histórico.

## Permissões

- `comum`: Navegar, Fila, Pesquisar, Solicitar; **baixar/enviar somente se** `renomear_autorizar_download = 1` (admin).
- Admin do módulo / `administrador_geral`: tudo acima + Organizador, ferramentas de PDF, gerenciamento de solicitações e Configurações.

## Auditoria e segurança

- Toda operação relevante é registrada na auditoria central com **hash SHA-256** (módulo `empenhos`) e na trilha por arquivo do próprio módulo.
- Autenticação e perfis pelo núcleo (`mod_intranet`); não há gestão própria de usuários neste módulo.

Veja [Manual do Usuário Comum](../manual_de_uso_usuario_comum/index.md) e [Análise do Módulo](../analise_mod_renomear_empenho.md).
