# Manual de Uso — Renomeador de Empenho — Intranet Modular

> Guia operacional do módulo Renomeador de Empenho (`/renomear-empenho`), que monitora pastas, extrai, renomeia, indexa e organiza documentos de empenho, e atende ao fluxo de solicitação de cópia (comum → administrador). A tela é dividida em **6 abas**: Navegar, Fila Renomeação, Pesquisar, Organizador (admin), Solicitação e Configurações (admin).

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

### 4. Organizador *(admin)*

- **Organizar caixas**: distribui os renomeados em `organizadorPasta/caixa_NN/sub_X` (~200 páginas/pasta, 4 pastas/caixa).
- **Gerar capas/matriz** e **Validar matriz** (`matrizDeDocumentos`).
- **Inventário** de caixas e subpastas.
- **Ferramentas de PDF** (corte, mescla, redução) sobre empenhos processados ou PDFs enviados; saídas em `datahora_cortePDF/`, `datahora_mergePDF/`, `datahora_reducaoPDF/`.

### 5. Solicitação *(todos; admin gerencia)*

- **Usuário comum**: solicita o envio de um documento informando seu e-mail (e mensagem opcional). A solicitação entra como `pendente`.
- **Administrador**: para cada solicitação (agrupada por lote) pode **Enviar por e-mail** (via SMTP central), **Gerar ZIP** (pega para envio manual e baixa o arquivo) ou **Recusar** (com motivo). ZIP gerado pode ser **Confirmar envio manual** ou **Cancelar ZIP** (volta a pendente).
- Expansão **Histórico completo**: todas as solicitações, com status e método de envio.

### 6. Configurações *(admin)*

- **Pastas monitoradas** (uma por linha, local ou rede/UNC, ex.: `\\servidor\empenhos` ou `E:\scan`) — aplicado sem reiniciar.
- **Aparência**: cor dos botões, texto, fundo, título e tamanho.
- **Configurações específicas**: texto do cabeçalho, **intervalo do monitor automático** (recomendado 60 s) e autorização de download/ZIP/e-mail para comuns.
- **Nome final do arquivo**: template configurável com as variáveis `{contador}`, `{empenho}`, `{empenho_cru}`, `{parcela}`, `{ficha}`, `{ano}` e formatação de largura (ex.: `{contador:04d}`). Tipos especiais usam nome próprio (`EC_0024.pdf`).
- **Campos de busca (regex)**: identificar/cadastrar/editar as regex de cada campo (ficha/empenho/parcela/ano...) sem reiniciar.
- **Auditoria dos arquivos**: consulta da trilha detectado→renomeado→removido por status.
- **Quarentena**: itens com erro de leitura/regex; clique para **Reprocessar com nova regex**.
- **Regras de extração**: regex dinâmicas, com ativação/inativação e campo FTS de destino.

## Fluxos principais

- **Monitor de pastas:** varre a raiz de cada pasta monitorada (local/UNC), processando PDFs novos e registrando os removidos; em rede, pastas inacessíveis são puladas.
- **Extração:** fallback `pytesseract` → `pdfplumber` → `pikepdf` → `pymupdf` (trata OCR e encoding).
- **Tipos especiais:** EC (complementação), EE (estimativo), EG (global) e AE (anulação) são detectados pelo conteúdo e renomeados com nome próprio.
- **Indexação FTS5:** busca por pagador, CPF, valor, órgão etc. (`tb_indexador_pesquisa_fts5`).
- **Quarentena:** PDFs com erro de leitura/regex vão para a fila; o admin reprocessa individualmente (regex alternativa na hora).
- **Renomeação:** automática (monitor/botão) ou manual (filas/revisão), com **gate de validação** — só renomeia com nº identificado; anti-colisão (`_v2`) evita sobrescrever.
- **Organizador físico:** subpastas ~200 páginas, 4 pastas/caixa, capas e `matrizDeDocumentos`.
- **Solicitações:** comum pede cópia; admin envia por e-mail ou ZIP; tudo fica no histórico.

## Permissões

- `comum`: Navegar, Fila, Pesquisar, Solicitar; **baixar/enviar somente se** `renomear_autorizar_download = 1` (admin).
- Admin do módulo / `administrador_geral`: tudo acima + Organizador, ferramentas de PDF, gerenciamento de solicitações e Configurações.

## Auditoria e segurança

- Toda operação relevante é registrada na auditoria central com **hash SHA-256** (módulo `empenhos`) e na trilha por arquivo do próprio módulo.
- Autenticação e perfis pelo núcleo (`mod_intranet`); não há gestão própria de usuários neste módulo.

Veja [Manual do Usuário Comum](../manual_de_uso_usuario_comum/index.md) e [Análise do Módulo](../analise_mod_renomear_empenho.md).
