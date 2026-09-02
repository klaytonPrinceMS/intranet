# Renomeador de Empenhos — Sistema de Gestão Documental

Sistema web de monitoramento, renomeação e gestão de documentos (empenhos e similares) da PMMSM/MG, com autenticação multiusuário, indexação de conteúdo, organizador físico de caixas/pastas e fluxo de solicitações de envio por e-mail ou ZIP.

> **DTI— Departamento de Tecnologia da Informação**
> Lei Municipal n.º 1.570/2007

**Versão ativa:** 3.0.260813 (NiceGUI) | **Limpeza técnica:** Passos 1-4 (13/05/2026) + Editor PDF consolidado (09/08/2026) + UX em diálogos (13/08/2026) + Editor PDF único com nomenclatura padrão e SHA256 na auditoria (13/08/2026, RF-020) + Redução em lote e correção pdfplumber (13/08/2026, RF-021)

---

## ⚠️ Estrutura atual pós-limpeza (35 arquivos na raiz)

| | **`main.py`** | **`/legacy/`** |
|---|---|---|
| **Status** | ✅ **Ativa / em desenvolvimento** | 📦 **Arquivado em 13/05/2026** |
| **Framework** | NiceGUI | Streamlit / Tkinter |
| **Arquitetura** | Modularizada `render_*.py` | Monolítica |
| **Papel** | Interface principal | Referência histórica apenas |

O diretório `/legacy/` contém arquivos arquivados (apenas referência histórica):
* `legacy/app.py` (72KB) - v2.0 Streamlit - usado para validar regras antes da migração
* ~~`utils_renomeador_empenhos.py` (46KB) - v1.0 desktop Tkinter~~ — **permanece ativo na raiz** (não arquivado)
* `render_configEditando.py` (18KB) - variante de Configurações — mesclada em `render_menu_master_config.py`
* `render_menu.py` (2,8KB) - versão antiga do menu — substituída pelo drawer inline de `main.py`
* `render_menupdf.py` (25B) - placeholder vazio
* `render_menu_pdf_20260812_112537.py` e `render_menu_pdf_20260813_084056.py` - backups do Editor PDF (RF-018/RF-019)
* `render_pdf.py` e `render_pdf_20260813_121336.py` - Editor PDF antigo e seu backup (substituído por `render_menu_todos_editor_pdf.py` — RF-020)

**Esses arquivos não devem receber novas funcionalidades.** Compartilham o mesmo back-end, mas a evolução acontece apenas em `main.py` + `render_*.py`.

---

## O que o sistema faz

- **Monitora pastas** por regex customizável (lista de múltiplos padrões simultâneos) e coloca em fila de revisão.
- **Extrai** Ficha, Empenho, Parcela, Ano + tipos especiais EC/EE/EG/AE/EX e renomeia automaticamente.
- **Renomeação automática opcional** quando todos os campos são reconhecidos sem divergência.
- **Indexa conteúdo** em segundo plano (FTS5 + fallback LIKE) com 30 campos de fábrica (pagador, CPF, valor bruto, órgão, banco, SISBB etc.) + campos customizáveis por prefixo/regex.
- **Pesquisa unificada** por nome, conteúdo (índice FTS ou busca ao vivo) e por campo extraído, com UM campo de termo, checkboxes de escopo (Nome / Índice rápido / Conteúdo ao vivo / Campo extraído), UM botão e UMA tabela de resultados (mesclados e de-duplicados por arquivo); busca por CPF/campos numéricos tolerante à pontuação (ex.: "083975" encontra "083.975.936-32").
- **Organizador físico**: agrupa PDFs em pastas ~200 páginas e pastas em caixas, gera capas para impressão.
- **Gestão de usuários CRUD** com bloqueio/desbloqueio e soft delete (master) + autoatendimento Meu Perfil.
- **Editor PDF**: envio de PDFs ao servidor (área `editorPDF/` única, visibilidade por usuário embutida no nome `dataHora_usuario_operacao_nome.pdf`), limites de **10 arquivos | 1 GB** e expiração automática em **10min**; seleção múltipla com download simples ou ZIP, **junção (merge)** de N PDFs, **divisão**, **redução de tamanho** com 4 ferramentas (pikepdf, pymupdf, pdfplumber, pytesseract) + **auditoria exclusiva com SHA256** (`auditoriaEditorPDF.db`).
- **Solicitações em lote**: comum solicita, master envia por email SMTP ou gera ZIP para envio manual.
- **Auditoria completa** SQLite `auditoria.db` + índice `indice.db` separado.
- **Biblioteca PDF configurável** `pdfplumber` ou `pymupdf` com fallback automático.
- **Personalização** via `config.json`: título, ícone, pasta raiz, cores do tema, senha master, SMTP.

---

## Estrutura dos arquivos (pós 09/08/2026 - 35 arquivos na raiz)

```
renomeador_empenhos/  (F:\edicaoMeta1)
├── main.py                    # ✅ 3.0.260813 - ENTRADA - 11 funcs / 17KB (render_inicio e render_auditoria ainda internos - Fase 2)
│
├── render_menu_todos_navegar.py          # ✅ Navegação: breadcrumb clicável, filtro, multiseção+lote, sortable, Voltar na raiz
├── render_menu_todos_pesquisa.py         # ✅ Pesquisa unificada (1 termo + checkboxes de escopo + 1 tabela) + CPF normalizado
├── render_menu_todos_fila_renomeacao.py             # ✅ Fila pendentes - os.walk + arquivo_bate_padrao_pendente (lista)
├── render_revisao.py          # ✅ Revisão e renomeação - extracao + tipos especiais + os.rename _v2
├── render_menu_master_organizador.py      # ✅ Organizador - Visão Geral / Organizar / Gerenciar
├── render_menu_master_solicitacoes.py     # ✅ Solicitações master - agrupa por lote_id
├── render_menu_master_usuarios.py         # ✅ CRUD usuários - soft delete, bloqueio
├── render_meu_perfil.py       # ✅ Meu Perfil - abrir_dialog(user) + hashlib.sha256
├── render_menu_master_config.py           # ✅ 3.0.260811 - 4 abas + listar_drives_windows() C:/F:/Z: + aplicar_tema() CSS
├── render_menu_todos_editor_pdf.py        # ✅ Editor PDF ATIVO 13/08/2026 (RF-019/RF-020) - abas ENVIAR (todos) + AUDITORIA PDF + SCANNER (master), nomenclatura padrão dataHora_usuario_operacao_nome.pdf
│
├── utils_operacoes_pdf.py           # ✅ Operações PDF - zipar_em_bytes() + merge_pdfs() + reduzir_pdf() (4 ferramentas)
├── utils_pdf.py           # ✅ Auditoria exclusiva Editor PDF - auditoriaEditorPDF.db + SHA256 (upload/reduzido/merge)
│
├── utils_config.py                  # CORE - carregar_config() com migração string→lista, raiz_dados(), padrao_nome_pendente() lista
├── utils_database.py                # CORE - 38 funcs - auditoria + usuarios + solicitações + arquivos - _lock RLock
├── utils_monitor.py                 # CORE - MonitorDePasta thread 4s + arquivos_pendentes_de_renomeacao() + tentar_renomear_automatica()
├── utils_indexador.py               # CORE - 28 funcs + IndexadorDePasta 8s - FTS5 + PADROES_FABRICA 30 campos + busca por campo normalizada (CPF/dígitos)
├── utils_busca.py                   # CORE - buscar_documentos_ao_vivo() yield + buscar_documentos_no_indice() FTS+LIKE (corrigido max_paginas/tamanho_trecho)
├── utils_leitor_pdf.py              # CORE - camada abstração pdfplumber/pymupdf + resolver_biblioteca()
├── utils_extracao.py                # CORE - PADROES ficha/empenho/parcela/ano + arquivo_bate_padrao_pendente() aceita LISTA
├── utils_extracao_tipos.py          # CORE - EC/EE/EG/AE + detectar_tipo_especial() ordem AE/EC primeiro
├── utils_organizador.py             # CORE - 17 funcs - calcular_divisao_pastas() + obter_caixa_com_espaco() + gerar_capa
├── utils_padroes.py                 # CORE - centralização regex + arquivo_ja_processado() + arquivo_pendente() lista
├── utils_email.py             # CORE - enviar_email_com_varios_anexos() ssl + starttls
├── utils_search.py             # CORE - busca por nome/conteúdo (wrapper de utils_busca)
├── utils_user.py               # CORE - login/CRUD usuários/perfil (fazer_login, cadastrar_usuario, is_master...)
├── utils_renomeador_empenhos.py # v1.0 desktop Tkinter - back-end de renomeação (ativo na raiz, não arquivado)
│
├── legacy/                    # 📦 Arquivado (referência histórica)
│   ├── app.py                 # v2.0 Streamlit (72KB) - referência, não rodar
│   ├── render_configEditando.py # variante Configurações - mesclada em render_menu_master_config.py
│   ├── render_menu.py         # menu antigo - substituído pelo drawer inline de main.py
│   ├── render_menupdf.py      # placeholder vazio (25B)
│   ├── render_menu_pdf_20260812_112537.py  # Backup Editor PDF (1º botão) - UX unificada (RF-018)
│   ├── render_menu_pdf_20260813_084056.py  # Backup Editor PDF (1º botão) - UX em diálogos (RF-019)
│   ├── render_pdf.py          # Editor PDF antigo (substituído - RF-020)
│   ├── render_pdf_20260813_121336.py       # Backup do Editor PDF antigo movido em 13/08/2026 (RF-020)
│   ├── config_20260813_163029.py      # backup de configurações
│   ├── main_editando.py               # rascunho de main.py
│   ├── render_config_20260813_163029.py  # backup de Configurações
│   └── render_config_bkp.py           # backup de Configurações
│
├── analise.md                # Requisitos RF-001 a RF-020 + dívida técnica + changelog limpeza
├── README.md                # Este arquivo - estrutura pós-limpeza
├── requirements.txt
├── config.json              # Gerado automaticamente - NÃO editar manualmente (use tela Configurações)
├── auditoria.db             # Gerado - banco auditoria + usuários
├── auditoriaEditorPDF.db     # Gerado - auditoria exclusiva do Editor PDF (SHA256) - tabela auditoria_editor_pdf
├── indice.db                # Gerado - índice FTS
├── assets/                  # Ícones/logos (favicon.ico, icone.ico)
├── doc/                     # Pasta dados padrão
└── editorPDF/               # Gerado - área privada do Editor PDF (visibilidade por nome do usuário)
```

**Removidos/arquivados em 13/05/2026 (Passos 1-4):**
* `render_menupdf.py` (placeholder vazio 25B) - a deleção de 13/05 não persistiu; o placeholder foi arquivado em `/legacy/`
* `render_configEditando.py` (variante não conectada 18KB) - mesclado em `render_menu_master_config.py 3.0.260811` e movido para `/legacy/`
* `render_menu.py` - substituído pelo drawer inline de `main.py` e movido para `/legacy/`
* `render_menu_todos_editor_pdf.py` (versão antiga do Editor PDF, 5 abas) - movido para `/legacy/` em 09/08/2026 e **reativado como editor ATIVO** em 12-13/08/2026 (RF-018/RF-019); ver backups `render_menu_pdf_20260812_112537.py` e `render_menu_pdf_20260813_084056.py`
* `render_pdf.py` (Editor PDF consolidado) - movido para `/legacy/` em 13/08/2026 (RF-020); ver backup `render_pdf_20260813_121336.py`

---

## Instalação

1. Python 3.10+ no computador servidor.
2. Pasta do projeto dentro da pasta monitorada ou vice-versa.
3. Terminal na pasta:
   ```bash
   pip install -r requirements.txt
   ```

## Como rodar (v3.0 NiceGUI)

```bash
python main.py
```
Porta padrão 80, acessível na rede `http://IP-DO-COMPUTADOR/`. Deixe em execução ou configure como serviço Windows.

Primeiro acesso: **master / admin**. Troque em Meu Perfil.

### Argumentos
```bash
python main.py -p 80 -H 0.0.0.0
```

## Como rodar legado (apenas referência)

```bash
# NÃO recomendado - apenas para consulta histórica
streamlit run legacy/app.py --server.address 0.0.0.0 --server.port 8501
```

---

## 📋 Editor PDF — Operações em botões e diálogos (RF-019/RF-020/RF-021)

Editor **único** no menu, implementado em `render_menu_todos_editor_pdf.py` (o antigo `render_pdf.py` foi
arquivado em `/legacy/` — RF-020). A aba **⬆️ ENVIAR** concentra o fluxo completo:

1. **Envio** — arrastar/inserir até 10 PDFs com barra de limite e lista auto-ajustável.
2. **Meus Arquivos** — checkbox + tempo de expiração colorido, selecionar todos/limpar, baixar
   ou excluir por arquivo.
3. **Operações em grade de botões**, cada um abrindo um **diálogo flutuante**:
   - **✂️ Reduzir** — **1 ou mais** arquivos selecionados; escolha da **biblioteca** (pikepdf *lossless*
     | pymupdf | pdfplumber | pytesseract *OCR*), DPI (50–400) e qualidade (10–100%) com sliders;
     reduz todos em sequência, mostrando ✅/❌ por arquivo e resumo final (arquivo com problema não
     interrompe o lote; a falha é registrada na auditoria como `erro_reducao`).
   - **🔗 Juntar (2+)** e **🔀 Dividir (1)** — diálogos com confirmação e nome do resultado.
   - **✅ Verificar integridade** — valida cada selecionado (✅/❌) com resumo.
   - **⬇ Baixar / 📦 ZIP / 🗑 Excluir** — diretos, excluir com confirmação.
4. **Auditoria PDF e Scanner** (master): auditoria com filtros por usuário/arquivo/ação/tipo e
   **SHA256** (origem/destino, para LGPD e provas jurídicas); scanner com busca por nome,
   breadcrumb e compressão para `reducao/`.

> **Nomenclatura padrão** de todos os arquivos gerados no servidor
> (RF-020): `dataHora_nomeUsuario_operacao_nomeArquivo.pdf` — ex.:
> `20260813_143000_master_reduzido_DOC_1.pdf`, `20260813_143000_master_merge_3arquivos.pdf`,
> `20260813_143000_master_dividir_DOC_1_parte1.pdf`. Antes, reduzir/dividir não gravavam o
> usuário no nome e o arquivo sumia de "Meus Arquivos" — corrigido.

> Limite: **10 arquivos | 1 GB | expiração em 10 min**.

---

## Changelog Limpeza Técnica

**13/08/2026 - Redução em lote + correção pdfplumber + robustez de erros (RF-021):**
* "Reduzir tamanho" aceita **1 ou mais** arquivos selecionados: reduz todos em sequência e mostra
  resultado por arquivo (✅/❌ com tamanho antes→depois) no próprio diálogo, que permanece aberto durante
  o lote; ao final, toast-resumo "✅ N reduzido(s)" e, se houver falhas, "❌ K não reduziram: nomes".
* Fix: `Erro na redução: cannot write mode P as JPEG` com a biblioteca **pdfplumber** — o
  `PageImage.save()` do pdfplumber faz `quantize=True` por padrão (imagem vira paleta "P", que o Pillow
  não grava como JPEG); corrigido com `quantize=False` em `utils_operacoes_pdf.py`.
* Falha em um arquivo **não interrompe o lote**: try/except por arquivo, remoção do destino parcial e
  auditoria da falha como `erro_reducao` (com motivo); sucessos seguem como `reduzido` com SHA256.
* Robustez: `_executar_reducao`, `_executar_merge` e `_executar_divisao` blindados — refresh final
  (chips/lista) em try/except individual e erros logados com traceback, para nenhuma exceção de tarefa
  de fundo derrubar o sistema.
* `VERSAO` 3.0.260813 (mantida — mesma data).

**13/08/2026 - Fix nome duplicado `.pdf.pdf` (pós-RF-021):**
* `_nome_padrao()` agora remove a extensão do `nome_base` antes de anexar o `.pdf` final — arquivos
  como `20260813_161440_pedro_reduzido_DOC_0206.pdf.pdf` não são mais gerados (upload e aba
  Scanner/Redução passavam o nome já com `.pdf`).
* Scanner/Redução também aplica `_nome_limpo()` no arquivo-fonte, evitando prefixo
  `dataHora_usuario` duplicado ao comprimir um arquivo já renomeado do servidor.
* `VERSAO` 3.0.260813 (mantida — mesma data).

**13/08/2026 - Nomenclatura padrão + SHA256 na auditoria + Editor PDF único (RF-020):**
* `render_menu_todos_editor_pdf.py`: nomenclatura padrão `dataHora_nomeUsuario_operacao_nomeArquivo.pdf` em
  **todas** as operações que geram arquivo (upload, reduzido, merge, dividir, scanner) — corrige o
  problema de o arquivo reduzido/dividido não aparecer em "Meus Arquivos" (faltava o nome do usuário).
* Auditoria: colunas `sha256_origem`/`sha256_destino` na tabela `auditoria_editor_pdf` (+ migração
  automática de `auditoriaEditorPDF.db`), hash calculado em todas as operações (inclusive `comprimido`
  do Scanner, que não registrava nada) e exibição "SHA Origem/SHA Destino" na aba Auditoria (LGPD).
* Fix: `TypeError: got an unexpected keyword argument 'icon'` no Scanner — `ui.input` do NiceGUI 3.15
  não aceita `icon=`; trocado por prop `prefix-icon` do QInput.
* Fix: botão "Confirmar envio" ficava **desabilitado permanentemente** após o primeiro lote
  (`props("disabled", False)` — `remove` é keyword-only no NiceGUI 3.15, gerava `TypeError`);
  corrigido com `props(remove="disabled")` e `try/finally` na reabilitação.
* Fix: `RuntimeError: The current slot cannot be determined` ("Task exception was never retrieved") ao
  concluir Reduzir/Juntar/Dividir/Comprimir — tarefas de background chamavam `ui.notify` após
  `await asyncio.to_thread(...)` sem contexto de slot; corrigido capturando `client = ui.context.client`
  no handler do clique e envolvendo o corpo de cada tarefa (`_executar_reducao`, `_executar_merge`,
  `_executar_divisao`, `comprimir_scanner`) em `with client:`. Bug pré-existente.
* `main.py`: botão **"📋 Editor PDF (Novo)"** removido e função `render_pdf2` eliminada — editor único
  (`render_menu_todos_editor_pdf.py`). `render_pdf.py` arquivado em `/legacy/` (backup `render_pdf_20260813_121336.py`).
* `VERSAO` 3.0.260813 (mantida).

**13/08/2026 - UX memorável do Editor PDF com operações em diálogos (RF-019):**
* `render_menu_todos_editor_pdf.py`: dropdown "Selecione ação..." substituído por grade de botões que abrem
  **diálogos flutuantes** (Verificar, Reduzir com biblioteca/DPI/qualidade, Juntar, Dividir,
  Baixar, ZIP, Excluir); cabeçalho discreto com chips; cards Enviar → Meus Arquivos → Operações.
* Fixes: auditoria corrigida (INSERT com placeholders certos), merge/divisão migrados para
  `utils_operacoes_pdf.py` (pymupdf), divisão com 2 tipos reais, limite padronizado em 1 GB.
* Abas master repaginadas (Auditoria com filtros; Scanner com busca/breadcrumb).
* `main.py`: botões do menu diferenciados — "📋 Editor PDF" e "📋 Editor PDF (Novo)".
* `VERSAO` 3.0.260813; backup em `legacy/render_menu_pdf_20260813_084056.py`.

**12/08/2026 - Unificação da UX do Editor PDF (1º botão do menu):**
* `render_menu_todos_editor_pdf.py`: abas ENVIAR + Meus Arquivos + Operações unificadas em uma única aba **⬆ ENVIAR** (seções empilhadas: envio → lista → operações). Abas restantes: Auditoria PDF e Scanner (master).
* `VERSAO` 3.0.260812; backup em `legacy/render_menu_pdf_20260812_112537.py` (RF-018).
* Os dois botões "📋 Editor PDF" foram **mantidos** (nada removido do `main.py`).

**09/08/2026 - Consolidação do Editor PDF:**
* Abas redundantes removidas (MEUS ARQUIVOS / OPERAÇÕES / SCANNER); operações integradas à aba ENVIAR
* `render_menu_todos_editor_pdf.py` (45KB) substitui o antigo `render_pdf.py` (36KB, movido para `/legacy/` em 13/08/2026 - RF-020)
* Novos módulos: `utils_operacoes_pdf.py` (zip/merge/reduzir com 4 ferramentas) e `utils_pdf.py` (SHA256)
* Órfãos identificados: `render_menupdf.py` (25B) e `projetoZero` (0B) — pendentes de remoção
* Dívida técnica "PDF mesclar/reduzir" resolvida (ver `analise.md` seção 4)

**13/05/2026 - Passos 1-4:**
* -6 arquivos na raiz (31→25), -47% tamanho, 0 quebra funcional
* `main.py`: -120 linhas (remove duplicata fila + imports mortos)
* Menu lateral centralizado e `render_menu_master_config.py` unificado com suporte multi-drive C:/F:/Z:
* `/legacy/` criado para arquivamento seguro

**15/08/2026 - Unificação da UX de Pesquisa + CPF normalizado + UX de Navegação (RF-022/RF-023/RF-024):**
* `render_menu_todos_pesquisa.py`: tela reformulada em UI única — um campo de termo, checkboxes de
  escopo (Nome / Índice rápido (conteúdo) / Conteúdo (busca ao vivo) / Campo extraído), um botão
  Pesquisar (com spinner) e uma única tabela de resultados (Arquivo | Pasta | Achado em |
  Trecho/Valor) com mesclagem e de-duplicação por arquivo; Enter dispara a busca; o dropdown de
  campo aparece só quando "Campo extraído" está marcado; dica de empty-state.
* `utils_indexador.py` (RF-023): `buscar_por_campo` normaliza termo e valor (remove espaços/`.`/`-`/`/`)
  antes do `LIKE`, e CPF/CNPJ/Processo/Documento/Empenho/Ficha são armazenados como dígitos —
  "083975" ou "083.975" encontram "083.975.936-32". Re-indexação única por processo força a
  re-extração dos documentos já indexados.
* `utils_busca.py` (RF-023): `_buscar_no_conteudo` passou a aceitar `max_paginas`/`tamanho_trecho`
  (a chamada em `buscar_documentos_ao_vivo` os passava — `TypeError` em busca ao vivo).
* `render_menu_todos_pesquisa.py` / `render_menu_todos_editor_pdf.py`: tarefas de fundo que usam
  `ui.notify`/`ui.*` capturam `client = ui.context.client` e envolvem o corpo em `with client:`
  (corrige `RuntimeError: The current slot cannot be determined` em busca ao vivo e notificações).
* `render_menu_todos_navegar.py` (RF-024): breadcrumb clicável (volta ao pai), filtro de arquivos,
  multiseção + solicitação/lote ZIP, colunas ordenáveis, botão Voltar desabilitado na raiz e
  empty-state; mantida a proteção contra traversal (`abs_raiz` check).
* Backups em `legacy/` (`render_menu_todos_pesquisa.py.bak`, `.select.bak`, `utils_indexador.py.bak`,
  `utils_busca.py.bak`, `render_menu_todos_navegar.py.bak`). `VERSAO` mantida em 3.0.260813.

Próximos passos (Fase 2): quebrar `utils_database.py`, `utils_indexador.py`, `render_menu_todos_editor_pdf.py` em módulos <10KB + extrair `render_inicio.py` e `render_auditoria.py` de `main.py`.

---

## Licença e Autoria

Desenvolvido por Systems Analyst PRINCE, K.B. - Prefeitura Municipal de Monte Santo de Minas
Versão: 3.0.260813
