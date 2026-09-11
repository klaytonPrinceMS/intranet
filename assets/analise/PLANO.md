# PLANO DE IMPLEMENTAÇÃO

> Checklist rastreável por fase. **Marcar `[x]` cada item concluído** para permitir retomada após interrupção. Versionamento: `1.0.AAMMDD`. Não executar `git commit` (responsabilidade do autor).
> Antes de Qualquer fase, obrigatorio, garantir que caso os bancos de dados db_mod_blog, db_mod_edit_pdf, db_modgest_cad_usuario, db_mod_intranet, db_mod_nomear_empenho, ou qualquer outro banco de dados nao exista na rais do sistema onde o script ou o exetuvel gerado no futuro estiver rodanto tiver os bancos de dados deve ser criado os bancos de dados do zero, e para o usuario deve ser inserio sempre o usuario master senha master inicialmente com permissao de administrador geral 

> **Itens concluídos e documentados foram removidos deste plano** (Fases 0–3, 5–9 integralmente
> verificadas em 11/09; restam apenas itens pendentes/parciais abaixo). Documentação de referência:
> `docs/` (`analise_mod_*.md`, `modulos/*.md`, `arquitetura.md`, `requisitos.md`, `plano_de_projeto/index.md`).

## Fase 4 — mod_renomear_empenho

### 4a. Monitor, extração e indexação

- [ ] Extração com fallback automático `pytesseract` → `pdfplumber` → `pikepdf` → `pymupdf` (tratar encoding cp1252/Latin-1 e OCR em páginas-imagem) — mojibake neutralizado via texto tolerante (`?`)

### 4b. Quarentena e regras dinâmicas

- [ ] Interface do administrador: identificação manual + cadastro de Regex dinâmico com reprocessamento sem reiniciar (`promover_quarentena`/`reprocessar_fila`, botão "Reprocessar fila")

### 4c. Renomeação e organizador físico

- [ ] Organizador: subpastas ~200 páginas, 4 pastas/caixa, capas PDF/TXT em `organizadorPasta/` (`mod_renomear_empenho_organizador.py`, 16/16 OK)

