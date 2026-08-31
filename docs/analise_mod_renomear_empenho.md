# Renomear Empenhos — `mod_renomear_empenho`

> Empenho rename module: route `/renomear-empenho` (key `empenhos`) · own database `db_mod_renomear_empenho.db` · PDF text extraction, dynamic regex, quarantine, sequential rename, partial physical organizer.

---

# Renomear Empenhos — `mod_renomear_empenho`

> Módulo de renomeação de empenhos: rota `/renomear-empenho` (chave `empenhos`) · banco próprio `db_mod_renomear_empenho.db` · extração de texto de PDF, regex dinâmica, quarentena, renomeação sequencial, organizador físico parcial.

## Propósito

Extrai nº do empenho/parcela do texto dos PDFs por regex dinâmica, renomeia sequencialmente (`doc_%04d_numEmpenho_%d_p%03d.pdf`) e move falhas para quarentena reprocessável. Inclui organizador físico em caixas/subpastas. **O processamento pode ser manual (botão "Processar pasta agora") ou automático** via job `monitor_empenho` do APScheduler (RF-40, intervalo padrão 10 s, configurável em `empenhos_monitor_intervalo_seg` sem restart — `mod_intranet/rotinas.py:36-67,192-193`).

## Banco próprio

Criador vigente: `init_db_empenho()` em `manipulador_bd.py:29-83`.

| Tabela | Conteúdo |
|:---|:---|
| `tb_empenhos` | nome original/final, numero_empenho, parcela, usuario, data, status ('ativo'), caminho; índice por número |
| `tb_indexador_pesquisa` | empenho_id PK, conteudo_texto (original + final + primeiros 4000 chars) — tabela **comum, mantida como fallback** |
| `tb_indexador_pesquisa_fts5` | **VIRTUAL TABLE FTS5** com 32 colunas do cabeçalho do empenho (RF-41) — índice real de busca; alimentada por trigger de exclusão + `reindexar_empenho()` |
| `tb_quarentena` | nome_arquivo, motivo, caminho_atual, data_insercao, processado |
| `tb_regex_regras` | nome_regra UNIQUE, padrao_regra, substituicao, ativo, **campo_destino** (FTS customizado); seeds "Padrão Empenho" e "Só números" |

⚠️ O `criador_bd.py` deste pacote é **legado/morto** e diverge totalmente: define um `tb_indexador_pesquisa_fts5` virtual (6 colunas) conectado no banco **central**. Nunca foi executado; o esquema real (FTS5 com 32 colunas em `db_mod_renomear_empenho.db`) está em `manipulador_bd.py`.

## Fluxo da tela

Sem abas e sem controle fino de perfil (parâmetro `perfil` não é usado — acesso pela chave do módulo apenas):

- Ações rápidas: **"Processar pasta agora"** (varredura pontual de `doc/` com resumo ok/total) e **"Organizar caixas"**.
- Pesquisa textual instantânea via **FTS5** (`MATCH`, máx. 50 resultados, fallback `LIKE`): nome final, empenho, parcela, usuário e qualquer campo do cabeçalho indexado.
- Tabela de Empenhos (últimos registros por status).
- Seção Quarentena: itens pendentes; clique abre diálogo **"Reprocessar com nova regex"** (regex opcional aplicada na hora).
- Expansion "Regras de extração": lista regras ativas/inativas com o padrão e formulário para salvar nova regra (valida `re.compile`; vale imediatamente).

## Regras de negócio relevantes — o que existe hoje

- Extração: pipeline tolerante a escaneados em `manipulador_bd.py:139-198` nas `PAGINAS_EXTRACAO` primeiras páginas: `pymupdf → pdfplumber → OCR (pytesseract, `por+eng`, dpi 200) → pikepdf (metadados)`. **Sem tratamento explícito de encoding cp1252/Latin-1** — PDF sem texto (nem mesmo via OCR) vai à quarentena ("possivelmente escaneado").
- Renomeação: contador sequencial persistido em banco; **renomeia mesmo sem validação completa** (regex falhou ⇒ empenho=0), contrariando o PLANO 4c ("somente campos validados sem divergência").
- Organizador: distribui renomeados em `organizadorPasta/caixa_NN/sub_X` por fórmula de páginas. **Não gera capas PDF/TXT nem valida `matrizDeDocumentos.pdf`**.
- Auditoria: ações `processar` e `quarentena` na trilha central **com hash SHA-256** (exigência do PLANO 4d atendida).

## Integrações com o núcleo

Importa `audit_log` (usado) e `get_connection` central (importado sem uso — conexões são locais via sqlite3). Nenhuma chave `tb_config`. Pastas fixas relativas à raiz: `doc/`, `quarentena/`, `organizadorPasta/` — criadas sob demanda; **nenhuma delas existe hoje na raiz** até o primeiro uso.

## Pontos de atenção

- `criador_bd.py` morto com esquema FTS5 fantasma no banco central — fonte de confusão ao ler o código; não executar.
- Gap conhecido: **gate de validação** (renomear somente campos validados sem divergência, PLANO 4c) ainda não implementado — renomeia mesmo quando a regex falha (empenho=0).
- Sem nenhum teste automatizado em `test/` para este módulo.

## Status — Fases 4a–4d do PLANO.md

**Implementado:** banco próprio em WAL; auditoria central com **hash SHA-256**; perfis/papéis por módulo (validação de acesso); fila de quarentena com motivo e reprocessamento individual (regex aplicada na hora); regex dinâmicas persistidas aplicadas sem restart (com `campo_destino` para campos FTS customizados); renomeação automática sequencial com contador em banco; organizador físico básico em caixas/subpastas; **indexação FTS5 (RF-41)** com 32 colunas do cabeçalho e busca via `MATCH` (fallback `LIKE`); processamento sob demanda de `doc/`.

**Parcial/Pendente (RF-41/45/39/40/44 finalizados e documentados; abaixo os gaps reais):**

- **Indexação FTS5** (RF-41) — **REALIZADO** (32 colunas + campos regex customizados; busca na tela usa FTS5).
- **Ferramentas de PDF embutidas** (corte/juntar/reduzir) DENTRO do módulo (RF-45) — **REALIZADO** (reutiliza `op_cortar`/`op_juntar`/`op_reduzir` do `mod_edit_pdf`; saídas em `datahora_cortePDF/`, `datahora_mergePDF/`, `datahora_reducaoPDF/`).
- **Ações de usuário comum** (e-mail/ZIP/download) (RF-39) — **REALIZADO** (card "Ações de usuário comum" com ZIP/e-mail, liberado por `renomear_autorizar_download`).
- **Monitor de pasta automático** (scheduler ~10 s) em vez de execução manual (RF-40) — **REALIZADO** (job `monitor_empenho` no APScheduler; intervalo em `empenhos_monitor_intervalo_seg`).
- **Capas PDF/TXT e validação `matrizDeDocumentos.pdf`** no organizador (RF-44) — **REALIZADO** (`gerar_matriz_organizador` gera `capa.txt` por caixa + `matrizDeDocumentos.txt`/`.pdf`; `validar_presenca_matriz` confere presença; `organizar_pastas` gera a matriz ao final).
- Reprocessamento em lote ("Reprocessar fila") — não há botão; é item a item.
- Tratamento de encoding cp1252/Latin-1 na extração — **Em aberto** (OCR `pytesseract`/`pikepdf` já implementado em `manipulador_bd.py:139-198`).
- Renomeação condicionada a validação sem divergência — **Em aberto**.
- Teste `testes/teste_fluxo_renameador.py` (31/31) citado no PLANO — não existe.

### Adições recentes (26/08)

- **Painel "Administração"** (expansão, exclusivo do admin geral/admin do módulo): bloco **Aparência** (prefixo empenhos_* — cor do botão/texto, tamanho via ui.color_input) e **config específica**: empenhos_pasta_monitorada (pasta monitorada, aplicada via pasta_monitorada() sem reiniciar), empenhos_texto_header. Salvo via set_config.
- **Versionamento**: versao_modulo:empenhos = 1.0.260827 (seed em conexao_bd.init_db()), exibido no rodapé em /renomear-empenho (rota → chave empenhos).
