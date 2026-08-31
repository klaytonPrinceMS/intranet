# Empenho Rename Module — `mod_renomear_empenho`

> Empenho rename module: route `/renomear-empenho` (key `empenhos`) · own database `db_mod_renomear_empenho.db` · PDF text extraction, dynamic regex, quarantine, sequential rename, physical organizer.

---

# Módulo Renomear Empenho — `mod_renomear_empenho`

> Módulo de renomeação de empenhos: rota `/renomear-empenho` (chave `empenhos`) · banco próprio `db_mod_renomear_empenho.db` · extração de texto de PDF, regex dinâmica, quarentena, renomeação sequencial, organizador físico.

## Propósito

Extrai nº do empenho/parcela do texto dos PDFs por regex dinâmica, renomeia sequencialmente (`doc_%04d_numEmpenho_%d_p%03d.pdf`) e move falhas para quarentena reprocessável. Inclui organizador físico em caixas/subpastas. O processamento pode ser **manual** (botão "Processar pasta agora") ou **automático** via job `monitor_empenho` (RF-40, default 10 s).

## Banco de dados

Criador vigente: `init_db_empenho()` em `manipulador_bd.py:60-83`.

| Tabela | Conteúdo |
|:---|:---|
| `tb_empenhos` | nome original/final, numero_empenho, parcela, usuario, data, status, caminho |
| `tb_indexador_pesquisa` | fallback comum (`empenho_id`, `conteudo_texto`) |
| `tb_indexador_pesquisa_fts5` | **VIRTUAL TABLE FTS5 com 32 colunas** do cabeçalho (RF-41) |
| `tb_quarentena` | nome_arquivo, motivo, caminho_atual, data_insercao, processado |
| `tb_regex_regras` | nome_regra UNIQUE, padrao_regra, substituicao, ativo, **campo_destino** (FTS customizado) |

⚠️ O `criador_bd.py` é **legado/morto** (esquema FTS5 fantasma no banco central) — não executar.

## Funcionalidades

- **Ações rápidas**: "Processar pasta agora" (varredura de `doc/` com resumo ok/total) e "Organizar caixas".
- **Pesquisa FTS5** (`MATCH`, máx. 50 resultados, fallback `LIKE`): nome final, empenho, parcela, usuário e qualquer campo do cabeçalho indexado.
- **Quarentena**: itens pendentes com diálogo "Reprocessar com nova regex" (aplicada na hora).
- **Regras de extração**: lista ativas/inativas, formulário para salvar nova regra (valida `re.compile`; vale imediatamente).
- **Extração de texto**: pipeline tolerante a escaneados (`manipulador_bd.py:139-198`): `pymupdf → pdfplumber → OCR (pytesseract, por+eng, dpi 200) → pikepdf`. PDF sem texto vai à quarentena ("possivelmente escaneado").
- **Organizador**: distribui renomeados em `organizadorPasta/caixa_NN/sub_X`; `gerar_matriz_organizador` gera `capa.txt` por caixa + `matrizDeDocumentos.txt`/`.pdf`; `validar_presenca_matriz` confere presença (RF-44).
- **Ferramentas de PDF embutidas** (RF-45): corte/merge/redução reutilizando `op_*` do `mod_edit_pdf`; saídas em `datahora_cortePDF/`, `datahora_mergePDF/`, `datahora_reducaoPDF/`.
- **Ações de usuário comum** (RF-39): ZIP/e-mail.
- **Painel Administração**: aparência (`empenhos_*`) + `empenhos_pasta_monitorada`, `empenhos_texto_header`.
- **Versionamento**: `versao_modulo:empenhos = 1.0.260827`.

## Regras de negócio

- Contador sequencial persistido em banco; **renomeia mesmo sem validação completa** (regex falhou ⇒ empenho=0 — gap do PLANO 4c).
- Auditoria: ações `processar` e `quarentena` na trilha central **com hash SHA-256**.
- Monitor automático configurável em `empenhos_monitor_intervalo_seg` sem restart.

## Permissões

| Ação | `comum` | Admin módulo | `administrador_geral` |
|:---|:---:|:---:|:---:|
| Processar pasta / pesquisar / ZIP / e-mail | ✓ | ✓ | ✓ |
| Regras de extração / quarentena reprocessar | ✗ | ✓ | ✓ |
| Organizar caixas | ✗ | ✓ | ✓ |
| Painel Administração | ✗ | ✓ | ✓ |

## Rota e integrações

- Rota: `/renomear-empenho` (chave `empenhos`) — `main.py:228`.
- Job `monitor_empenho` no APScheduler (`rotinas.py`); reutiliza `mod_edit_pdf` para ferramentas.
- Pastas fixas relativas à raiz: `doc/`, `quarentena/`, `organizadorPasta/` (criadas sob demanda).

## Testes

Sem teste automatizado em `test/` para este módulo (pendência). Testes manuais com `qacomum`/`qamaster` recomendados.

## Pontos de atenção

- Gate de validação (renomear somente campos validados sem divergência) **não implementado**.
- Tratamento de encoding cp1252/Latin-1 **em aberto** (PDFs escaneados via OCR já cobertos).

Ver [Análise do Módulo](../analise_mod_renomear_empenho.md).