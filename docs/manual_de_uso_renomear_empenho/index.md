# Manual de Uso — Renomeador de Empenho — Intranet Modular

> Guia operacional do módulo Renomeador de Empenho (`/renomear-empenho`), que indexa, renomeia e organiza documentos de empenho. Este manual cobre o fluxo de almoxarifado — **o sistema não possui perfil "almoxarife"**; o fluxo é atendido ao usuário `comum` quando autorizado pelo administrador do módulo.

## Contexto

O sistema não possui um perfil denominado "almoxarife"; a função de almoxarifado é atendida pelo **Renomeador de Empenho** (`mod_renomear_empenho`), liberado para o usuário comum quando autorizado pelo administrador do módulo.

## Fluxos do almoxarifado

- **Monitor de pastas:** varredura de PDFs (live ou intervalo configurável, padrão 10 s).
- **Extração:** fallback `pytesseract` → `pdfplumber` → `pikepdf` → `pymupdf` (trata OCR e encoding).
- **Indexação FTS5:** busca por pagador, CPF, valor, órgão, SISBB etc. (`tb_indexador_pesquisa_fts5`).
- **Quarentena:** PDFs com erro de leitura/Regex não reconhecido vão para fila; o admin identifica manualmente ou cadastra Regex dinâmico (reprocessa sem reiniciar).
- **Renomeação:** automática quando campos validados; ou sequencial (`doc_0032_numEmpenho_numParcela.pdf`).
- **Organizador físico:** subpastas ~200 páginas, 4 pastas/caixa, capas PDF/TXT; validação via `matrizDeDocumentos.pdf`.
- **Edição embutida:** corte, merge, redução de tamanho (saídas em `datahora_*PDF/`).

## Permissões

- `comum` liberado: pesquisa, solicitar envio/ZIP, visualizar/baixar conforme autorização do admin do módulo.
- Auditoria com hash SHA-256 em toda operação (`tb_auditoria`, módulo `empenhos`).

Veja [Manual do Usuário Comum](../manual_de_uso_usuario_comum/index.md) e [Levantamento de Requisitos](../2_levantamento_requisitos/index.md).
