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

## Correções registradas (25/09/2026 — lote 1, commit `624c9d5`)

Duas falhas de produção e uma padronização de UI, todas no mesmo lote. (O `NameError` de `notificar` e os fallbacks de tema do **lote 2** estão na seção seguinte.)

### Bug 1 — a busca de 1 letra não filtrava nada

**Onde:** `bd_manipulador.pesquisar_levantamento` (`bd_manipulador.py:2180-2228`).
**Sintoma:** digitar **uma única letra** no campo de pesquisa do Navegar devolvia a lista
**vazia**, mesmo com dezenas de arquivos cujo nome contém aquela letra. A UI prometia o
comportamento oposto: o campo é `debounce='150'` (busca incremental, a cada tecla), o rótulo de
status durante a busca é literalmente `Pesquisando (FTS5 + conteúdo)…`, e a docstring de
`_fts_query_prefixada` afirma *"Permite resultado já na 1ª letra e refino a cada tecla (LIKE
cobre o fallback)"*. A promessa existia em três lugares (placeholder, spinner e docstring) e a
implementação não cumpria nenhuma para 1 caractere.

#### Por que acontecia — FTS é prefixo, `LIKE` é substring

Os dois caminhos de busca **não têm a mesma semântica de casamento**, e essa é a raiz do bug:

| Caminho | Semântica | Consulta montada | Casa com o token `24`? | Casa com `4abc`? |
|:---|:---|:---|:---:|:---:|
| **FTS5** (`MATCH`) | **prefixo de token** — só o *começo* do token | `_fts_query_prefixada(["4"])` → `"4"*` | ✗ — o token indexado é `24`, e `4` não é prefixo de `24` | ✓ |
| **`LIKE`** | **substring** — qualquer posição | `f"%{termo.strip()}%"` → `%4%` | ✓ | ✓ |

`tb_levantamento_fts` é uma `VIRTUAL TABLE ... fts5` com o tokenizer padrão (`unicode61`), que
quebra `EC_24.pdf` em tokens; o `4` de `24` é um token **isolado**, não o início de um token. Por
isso `"4"*` — apesar do `*`, que só faz *prefix matching* — não encontra `24`. Já o
`LIKE '%4%'` do fallback encontra, porque o `LIKE` do SQLite opera sobre a **string bruta**.

!!! danger "O defeito real não era o FTS — era o gatilho do fallback"
    O código só caía no `LIKE` quando o FTS **lançava exceção** (índice ausente, FTS5 não
    compilado, tabela virtual não criada — que é o caso no **PostgreSQL**, onde o proxy ignora
    `CREATE VIRTUAL TABLE`). Mas a busca de 1 letra **não levantava exceção nenhuma**: o FTS
    executava normalmente e devolvia **zero linhas**. `if not achados` nunca era Verdadeiro,
    porque o `return` ficava **fora** da checagem:

    ```python
    # ANTES — o fallback só era alcançado por exceção
    try:
        cur.execute("... WHERE tb_levantamento_fts MATCH ? ...", (query, limite))
        return cur.fetchall()          # ← retorna [] sem exceção; LIKE inalcançável
    except Exception as e:
        _log().debug("FTS indisponível, fallback LIKE")
        like = f"%{termo.strip()}%"
        cur.execute("... WHERE nome_arquivo LIKE ? OR ...", (like,)*5 + (limite,))
        return cur.fetchall()
    ```

    Ou seja: o `LIKE` existia e estava correto — ele só era um *fallback de indisponibilidade*,
    nunca um *complemento de semântica*. Um resultado vazio do FTS, que aqui significa
    "encontrado pelo índice, mas nada casa com o prefixo", era interpretado como "não há
    nada", que é a **mesma** leitura de "o índice está fora do ar".

#### Correção — FTS vazio também aciona o `LIKE`

```python
like = f"%{str(termo).strip()}%"          # ← calculado uma vez, ANTES das duas tentativas
try:
    cur.execute("... WHERE tb_levantamento_fts MATCH ? ...", (query, limite))
    achados = cur.fetchall()
    if achados:                            # ← só sai se achou; senão cai no LIKE
        return achados
except Exception as e:
    _log().debug(f"pesquisar_levantamento FTS indisponível, fallback LIKE: {e}")
# ---- 2) LIKE por substring (1 letra / termo no meio do nome) ----
cur.execute("... WHERE nome_arquivo LIKE ? OR numero_empenho LIKE ? "
            "OR ficha LIKE ? OR ano LIKE ? OR conteudo_texto LIKE ? "
            "ORDER BY id DESC LIMIT ?", (like, like, like, like, like, limite))
return cur.fetchall()
```

A correção é mínima — mover o `return` para dentro de `if achados` e **extrair o `LIKE` para fora
do `except`** — e a docstring do próprio `MATCH` foi atualizada com a semântica, para que a
dupla semântica (prefixo **ou** substring) fique escrita onde o próximo a mexer vai ler.

#### Semântica resultante

| Termo digitado | FTS (prefixo) | Se o FTS não achou → `LIKE` (substring) | Efeito percebido |
|:---|:---|:---|:---|
| `4` | `"4"*` — só tokens que **começam** com 4 | `%4%` em nome/nº/ficha/ano/conteúdo | **1ª letra já filtra** — a promessa da UI é cumprida |
| `24` | `"24"*` — casa com `24`, `2451` | `%24%` | idem |
| `2` | `"2"*` — casa com `20…`, `24`, `2º`… | `%2%` | idem |
| `EC_24` | `"EC_24"*` — casa com `EC_24`/prefixos longos | `%EC_24%` | idem |
| `jOA` (maiúsc. no meio) | case-insensitive, mas `*` no fim | `%jOA%` só se casar literal | idem |
| `silva sousa` | `"silva" AND "sousa"*` | `%silva sousa%` (a string inteira) | idem |

Trade-off consciente: o `LIKE` é **bem mais caro** que o FTS (varre `conteudo_texto`, que guarda
até 20 kB por arquivo) e **não ordena por relevância** (`ORDER BY id DESC`, contra
`ORDER BY rank` do FTS). Em compensação, só roda quando o FTS **não** achou nada, e o
`LIMIT` (padrão 100 na tela) limita o custo. O caminho quente (termo com 2+ caracteres que casa
como prefixo) continua sendo 100 % FTS5.

!!! note "Reparo do teste que provou o bug"
    `assets/test/test_navegar_pesquisa_empenhos.py` falhava por **falta de massa**, não por
    defeito de código: a pasta real `mod_renomear_empenho/doc` só tem `.gitkeep`, então
    `levantar_arquivos` não populava `tb_levantamento` e o assert `len(hits) > 0` falhava por
    tabela vazia. O teste foi reescrito para isolar banco **e** pasta monitorada em
    `tempfile.mkdtemp()`, semear 4 PDFs de `assets/test/pdf/` (`DOC_0201`, `EC_24`, `EE_9570`,
    `EG_89`), rodar `levantar_arquivos("tester")` e então exigir
    `pesquisar_levantamento("4", limite=10)` com hits — restaurando `DB_EMPENHO_PATH`,
    `PASTA_MONITORADA`, `pastas_monitoradas` e `mod_intranet.repositorio.MODULOS_BD["empenhos"]`
    no `finally`. **Resultado: 20/20 verificações OK** (`backend levantamento('4')=2 hits`).

### Padronização 1 — barra de abas no helper padrão

**Onde:** `telas.py:181-186`.
**Situação anterior:** a barra de abas do módulo era montada **à mão**, com `ui.tabs()` +
`ui.tab()` e um **dicionário de ícones paralelo e redundante**:

```python
_abas = [("navegar", "Navegar", "folder_open"), ("fila", "Fila Renomeação", "move_to_inbox"), …]
_icones = {"navegar": "folder_open", "fila": "move_to_inbox", "organizador": "inventory_2",
           "solicitacao": "mail"}                       # ← duplicata de _abas
with ui.tabs().props("dense inline-label").classes("min-w-0 flex-1 overflow-x-auto") as tabs_el:
    for key, label, _ico in _abas:
        ui.tab(key, label, icon=_icones.get(key))      # ← consome _icones, ignora _abas[2]
```

O ícone já vinha **dentro** de `_abas` (3º elemento da tupla) e era **ignorado**; a fonte de
verdade de fato era o dict `_icones`, parallelamente. Duas listas para o mesmo dado significa que
trocar `folder_open` por `folder` em `_abas` **não** mudava nada na tela — a change silenciosamente
perdida. Enquanto isso, **`menu_modulo` já estava importado** (`telas.py:40`,
`from mod_intranet.aba_modulo import cabecalho, menu_modulo`) e **sem uso** — import morto que
o `verifica_ui_comum.py` exigia ver ausente (`not re.search(r"ui\.tabs\(\)", …)`), ou seja, o
código de produção **violava a própria regra** que o teste de arquitetura cobrava.

**Correção:** `tabs_el = menu_modulo(_abas)`, e o dict `_icones` **removido** (com o comentário
explicando por quê). Uma lista, um lugar, ícone no mesmo tuple que o rótulo.

#### Efeito colateral de UI — intencional

`menu_modulo` (`mod_intranet/aba_modulo.py:102-117`) monta
`ui.tabs(value=valor).classes("w-full")` com `ui.tab(chave, rotulo, icon=icone)` **sem**
`dense inline-label` — ou seja, **ícone acima, rótulo abaixo** (é o padrão do módulo). A barra
muda de "ícone + rótulo na mesma linha" para "ícone empilhado sobre o rótulo", e perde as classes
`min-w-0 flex-1 overflow-x-auto` que a versão manual trazia. O `flex-1` era o que segurava as
abas à esquerda do botão TEMP à direita dentro do `row justify-between flex-nowrap`; com `w-full`
isso é resolvido pelo próprio `ui.tabs`. O `overflow-x-auto` (rolagem horizontal das abas em
tela estreita) **não** é reposto pelo helper — ver "Pontos de atenção".

!!! tip "Por que isso importa (e por que a suíte de QA acusou)"
    O `verifica_ui_comum.py` tem o check *"renomear_empenho: barra de abas no helper padrão
    `menu_modulo` (sem `ui.tabs()` cru)"*. Com `menu_modulo` importado e **sem uso**, o módulo
    ficava num estado incoerente: a arquitetura exigia o helper, o teste exigia o helper e o
    código não usava o helper. Além disso, a política do projeto é a de **um único lugar para o
    padrão visual** — barra de abas, cabeçalho, botão e campo de busca saem de `aba_modulo` /
    `ui_comum`, nunca de construção local.

## Correções registradas (25/09/2026 — lote 2)

### Bug 3 — `notificar` nunca importado: todo erro do Renomeador sumia

Além dos dois bugs acima, o `pyflakes` (análise estática obrigatória) revelou que
`mod_renomear_empenho/telas.py` chamava **`notificar` em cerca de 60 call sites sem
nunca ter o import no arquivo**. Cada chamada levantava `NameError` — e como quase
todas estavam dentro de um `except Exception: pass` (o caminho de erro padrão do
AGENTS.md §3.2), o efeito era:

- o usuário **não via nenhuma notificação** quando algo dava errado;
- **nada ia para o log** — o nome nem existia para o `logger.exception` chamar;
- o `try/except` do fallback mascarava tudo e a suíte de testes passava.

Correção: `from mod_intranet.tema_modulo import notificar` no **escopo de módulo**
(`telas.py:42-43`), com comentário explicando o motivo. É o mesmo padrão dos demais
casos do lote — nome usado por muitas funções vai no topo do arquivo, não repetido
dentro de cada uma.

### Fallbacks de tema que referenciavam nomes inexistentes

No mesmo arquivo, três helpers de fallback usavam nomes que **não existiam** no
escopo:

```python
# ANTES — `_bootstrap`, `_hibrido` e `_modelo` nunca foram definidos
def _eh_bootstrap():
    try:
        return _visual.eh_bootstrap(get_config)
    except Exception:
        return _bootstrap        # → NameError dentro do tratamento de erro

# DEPOIS
def _eh_bootstrap():
    try:
        return _visual.eh_bootstrap(get_config)
    except Exception:
        return False             # fallback semânticamente correto
```

| Helper | Antes | Depois | Por quê |
|:---|:---|:---|:---|
| `_eh_bootstrap` | `return _bootstrap` | `return False` | "não é Bootstrap" é o default seguro; `True` deixaria o tema errado sem nenhum sinal |
| `_eh_hibrido` | `return _hibrido` | `return False` | idem para o modo híbrido |
| `_modelo_atual` | `return _modelo` | `return _visual.MODELO_PADRAO` | aqui o fallback **tem** de ser um valor de verdade: `MODELO_PADRAO` existe em `mod_renomear_empenho/visual.py` e é o modelo documentado como padrão |

O caso de `_modelo_atual` é o mais perigoso dos três: o `except` era justamente o
caminho tomado quando a leitura da config falhava, e ali a tela ficaria sem modelo
nenhum.

!!! note "Padrão que emerge: o `except` também é código"
    Nenhum desses três `except` executava com frequência — por isso o bug passou
    despercebido. Mas o `except` é o **caminho mais crítico** do código, porque é
    onde os bugs de escopo se escondem: quando ele é executado, já há um problema em
    curso, e o `NameError` do próprio tratamento de erro transforma um incidente
    pequeno em uma tela silenciosamente quebrada. Todo `except` deve ser revisto com
    a mesma atenção que o caminho feliz.

## Referência funcional — monitor, regex, FTS5, quarentena, organizador e solicitações

### Monitor multi-pasta

- `pastas_monitoradas()` lê a lista da `tb_config` (chave `empenhos_pastas_monitoradas`), **uma
  pasta por linha**, aceitando caminho **local** (`E:\scan`) e **rede/UNC** (`\\servidor\compart`) —
  vários computadores podem escanear simultâneos. A pasta padrão é
  `_PASTA_MONITORADA_PADRAO` = `mod_renomear_empenho/doc`.
- **Automaticidade ≠ recursividade:** o job `monitor_empenho` varre **apenas a raiz** de cada
  pasta; as telas Navegar e Fila são **recursivas** (comportamento intencional, com proteção
  anti-travessia por `raizes_navegacao`/`pasta_navegavel`).
- Intervalo padrão **60 s**, chave `empenhos_monitor_intervalo_seg`, alterável **sem restart**
  (`mod_intranet/rotinas.py:intervalo_monitor_empenho` / `reagendar_monitor_empenho`).
- Falha de rede/UNC **não derruba o monitor** (RNF-06): `pasta_acessivel` pula a pasta
  inacessível e segue as demais.

### Regex dinâmica (RF-41)

- `tb_regex_regras` (`nome_regra UNIQUE`, `padrao_regra`, `substituicao`, `ativo`,
  **`campo_destino`**) é editável em Configurações **sem reiniciar**: `salvar_regra` valida
  `re.compile` **antes** de gravar e as regras são relidas a cada `processar_pdf`/`extrair_numero`.
- `extrair_campos_regex(texto)` aplica as regras com `campo_destino` definido e devolve
  `{campo_destino: valor}` — é o que alimenta as **colunas FTS customizadas** do índice.
- `validida_regex` anti-ReDoS barra padrões catastróficos na gravação.

### FTS5 — 59 colunas e as duas tabelas

| Tabela | Quando | Busca |
|:---|:---|:---|
| `tb_indexador_pesquisa_fts5` |Via `reindexar_empenho()` + trigger de exclusão | `pesquisar()` — busca os **empenhos já processados** (`tb_empenhos`) |
| `tb_levantamento_fts` | JOIN do levantamento | `pesquisar_levantamento()` — busca o **inventário vivo** (pendentes e processados) |

- **59 colunas** (`FTS_COLS`): identificação, órgão/unidade/sub-unidade, função/subfunção,
  programa, projeto/atividade, dotação, elemento/subelemento de despesa, fonte/subfonte de
  recurso, favorecido (nome/código/CPF/endereço) e **os campos livres mapeados por
  `campo_destino`** das regex dinâmicas.
- Tokenizer `unicode61` padrão; prefixo **só no último token** (`"joao" AND "si"*`) para refinar a
  cada tecla sem reprocessar os anteriores.
- `tb_indexador_pesquisa` (sem FTS) permanece como **fallback comum** (`empenho_id`,
  `conteudo_texto`).
- **Degradação no PostgreSQL:** `CREATE VIRTUAL TABLE` e `CREATE TRIGGER` são SQLite-only e o
  proxy os ignora; no PG a busca cai no `LIKE` portável (mesma degradação documentada na tabela de
  pendências de WAL/paridade). Por isso o `LIKE` **não pode ser removido** como "código morto".

### Quarentena (PLANO 4b)

- **Entrada:** falha de extração, falha do gate de validação, PDF sem texto ("possivelmente
  escaneado") ou múltiplos documentos no mesmo PDF.
- `mover_quarentena` (`bd_manipulador.py:2231`) grava o motivo **truncado a 300 caracteres**,
  copia o arquivo para `mod_renomear_empenho/quarentena/<timestamp>_<nome>` e registra em
  `tb_quarentena`.
- **Identificação manual** (sem restart): diálogo "Revisar/renomear" na aba Navegar chama
  `renomear_manual` (com gate), que normaliza o nome e resolve colisão acrescentando `_v2`.
- **Reprocessamento individual:** clique na linha da quarentena → "Reprocessar com nova regex" →
  `reprocesse_quarentena(qid, novo_padrao)`.
- **Reprocessamento em lote:** botão "Reprocessar fila" → `reprocessar_fila(usuario, novo_padrao)`
  (`bd_manipulador.py:1792`) itera todos os `processado=0` com as regras ativas e reporta
  `sucessos/total`.
- **Múltiplos documentos:** `detectar_documentos_no_pdf`/`eh_multiplo_documento`
  (`bd_manipulador.py:815`) agrupam por `_inicio_documento`; a quarentena oferece "Separar
  documentos" → `separar_documentos_quarentena`/`separar_pdf_por_documentos`, que fatia em
  `*_parteNN_pA-B.pdf`, move para a pasta monitorada e reprocessa cada parte.

### Organizador físico (PLANO 4c)

- Distribui os renomeados em `mod_renomear_empenho/organizadorPasta/caixa_NN/sub_X` com
  **~200 páginas por subpasta** e **4 subpastas por caixa** (configuráveis:
  `empenhos_organizador_paginas_pasta`, `empenhos_organizador_pastas_caixa` —
  `bd_manipulador.py:1988`).
- `gerar_matriz_organizador` (`bd_manipulador.py:2090`) gera **capa por caixa** em **dois
  formatos** — `capa.txt` **e** `capa.pdf` (via pymupdf) — e a **matriz geral**
  `matrizDeDocumentos.txt` **e** `matrizDeDocumentos.pdf`. O `.pdf` existe para quem precisa
  imprimir a matriz de conferência física.
- `validar_presenca_matriz` (`bd_manipulador.py:2121`) confere que **todo `.pdf` listado na
  matriz existe em disco** — é a rede de segurança contra documento organizado sem registro.
- `organizar_pastas` encadeia tudo e devolve `"<N> organizado(s). Matriz gerada (TOTAL documentos)."`

### Solicitações (RF-39) — fluxo comum → admin

```
   comum (aba Navegar: seleciona + "Solicitar envio")
        │  registra tb_solicitacoes(lote_id=…, status=pendente, metodo_envio=…)
        ▼
   admin (aba Solicitação)
        ├─ e-mail  → enviado        (mod_intranet.email_util.enviar_email, SMTP central)
        ├─ ZIP     → zip_gerado     (mod_renomear_empenho/downloads/solic_<lote>.zip)
        │              └─ confirmar → concluído
        └─ recusar → recusado        (grava motivo_recusa, visível ao comum)
```

- **1 pedido por envio (grupo)**: cada ação do comum cria **um** pedido com `lote_id`; vários
  arquivos do mesmo envio são **agrupados** sob o mesmo `lote_id` — é o agrupamento que permite
  ao admin tratar "12 arquivos" como uma unidade, e é o que torna o rótulo "lote" honesto.
- O histórico é exibido ao solicitante **com o estado e, no caso de recusa, o motivo**.

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
- **`overflow-x-auto` perdido na barra de abas** (25/09/2026) — a versão manual de `ui.tabs()` trazia `min-w-0 flex-1 overflow-x-auto`; `menu_modulo` devolve `w-full` sem a rolagem horizontal. Com 4 abas admin e rótulo "Fila Renomeação" o pior caso cabe em ~320 px, mas **vale reverificar no RNF-UI-01** se o menu passar a ter mais abas. Alternativa sem tocar no helper: envolver o `tabs_el` devolvido num `ui.element("div").classes("min-w-0 overflow-x-auto")`.
- **`ui.notify` cru ainda é a maioria das notificações do módulo** (25/09/2026): 117 ocorrências em `telas.py` + 23 em `telas_administracao.py`, contra a regra do AGENTS.md §5.1. O `mod_edit_pdf` foi migrado para `tema_modulo.notificar()` no mesmo dia; este módulo **ainda não**. A migração é mecânica (`notificar(msg, tipo=…)` aceita `type=`), mas é grande demais para um lote de bug-fix — deve ser tarefa própria, com guarda de QA por arquivo (o check atual de `verifica_ui_comum.py` só varre `mod_edit_pdf`).
- O `LIKE` de `pesquisar_levantamento` (`ORDER BY id DESC`, sem relevância) é **o caminho do PostgreSQL** e o **complemento de substring** do SQLite — não é fallback dispensável.

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
    ⚠️ **Correção de 25/09/2026:** o `overflow-x-auto` citado aqui era da barra de abas **manual** (`ui.tabs()` à mão). A migração para o helper `aba_modulo.menu_modulo` (ver "Padronização 1") **removeu** essa classe — o helper monta `ui.tabs().classes("w-full")`. Pendência registrada em "Pontos de atenção".

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

## Pendência QA — WAL + paridade SQLite↔Postgres (24/09/2026, sem correção aplicada)

> Documentação da correção pendente. Nenhum `.py` alterado neste lote.

| Módulo | Achado | Arquivo:linha | Correção proposta contida no módulo | Risco regressão |
|:---|:---|:---|:---|:---|
| renomear_empenho | Sem `CrudBase`; FTS5 `VIRTUAL TABLE` + `sqlite_master` (degrada no PG por desenho) | `mod_renomear_empenho/bd_manipulador.py:687`, `:786` (FTS5) · `:773` (`sqlite_master`) · `:660` (fallback LIKE) | Manter fallback LIKE no PG; isolar FTS5 em ramo SQLite; migrar CRUD para `CrudBase`; `_tabela_existe()` interno | Médio (monitor 60 s + quarentena + organizador) |

Detalhe consolidado em [Plano WAL + Paridade](registro_de_mudancas/wal_paridade_pendente_2026-09-24.md).
