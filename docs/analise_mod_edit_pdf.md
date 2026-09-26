# Editor de PDF — `mod_edit_pdf`

> PDF editor module: route `/edit-pdf` (key `editar_pdf`) · own database `db_mod_edit_pdf.db` · per-user temp space, quotas, SHA-256 audit, scheduled expiration.

---

# Editor de PDF — `mod_edit_pdf`

> Módulo de edição de PDF: rota `/edit-pdf` (chave `editar_pdf`) · banco próprio `db_mod_edit_pdf.db` · espaço temporário por usuário, cotas, auditoria SHA-256, expiração agendada.

## Propósito

Editor de PDFs multiusuário com espaço temporário por usuário. O usuário envia PDFs em lote e aplica operações sobre uma seleção ordenada (reduzir, juntar, cortar, dividir, verificar, ZIP, excluir); arquivos expiram automaticamente. Aba de Administração exclusiva do `administrador_geral` para cotas/limites/expiração — tudo configurável sem restart.

## Banco próprio

Criador vigente: `init_db_pdf()` em `bd_manipulador.py:92-123` (executado no import e no bootstrap central).

- **`tb_arquivos`**: id, nome_arquivo, usuario, tamanho_bytes, `operacao` (upload/saida/zip), data_operacao, ativo.
- **`tb_cota_disco`**: usuario PK, total_usado_bytes, atualizado_em.

⚠️ O `bd_criador.py` deste módulo é **legado/morto** com esquema divergente (`caminho_arquivo`, `hash_sha256 NOT NULL`, FTS inexistente) e conecta no banco **central** — se executado criaria tabelas erradas em `db_mod_intranet.db`. É dele a semeadura da versão do sistema citada na convenção de versionamento.

## Fluxo da tela

- **Abas**: Editor (sempre) | Administração (só `administrador_geral`). Cabeçalho mostra uso da cota do usuário; uso global só ao admin geral.
- **Upload**: múltiplo com auto-upload, aceita só `.pdf`; recusados aparecem **nominalmente em vermelho** com o motivo; botão "Enviar agora" para reenvio.
- **Arquivos no servidor**: tabela com seleção múltipla estável entre refreshes (timer 5 s), badges "#" com a ordem de marcação (merge respeita essa ordem) e coluna "Expira em" com contagem regressiva colorida (verde >5 min, amarelo ≤5 min, vermelho ≤1 min).
- **Ações sobre a seleção**: Verificar integridade, Juntar, Excluir selecionados, Baixar ZIP, baixar PDFs individuais; menu de contexto por linha (Baixar/Excluir).
- **Operações**: Reduzir tamanho — modos Leve (recompressão; biblioteca auto `pymupdf→pikepdf→pypdf` ou fixa) e Agressivo (rasteriza páginas como JPEG, DPI 50–400, qualidade 10–100%) | Cortar páginas (pares/ímpares/lista "2-5,8" → um único PDF) | Dividir (página-a-página, par/ímpar, cortes ou intervalos → vários PDFs).
- **Administração** (padrão de cards dos módulos, 06/09): card **"Configurações de cores"** (prévia ao vivo), card **"Configurações específicas"** (cota global GB, máx. arquivos/lote, MB/lote, cota por usuário GB, minutos de expiração + textos da tela) e card **"Manutenção"** ("Expirar agora") — todos recolhíveis (`card_admin`) com o rodapé padrão de 2 botões ("Restaurar padrão" + "Aplicar") exclusivos do card, recarregando após 1 s; ao final, card padrão de backup do banco (`painel_backup`).

### Padrões centrais de UI aplicados (06/09)

A tela foi migrada para os padrões centrais (`mod_intranet/ui_comum.py` + `tema_modulo`), mantendo o visual byte-idêntico:

| Padrão | Antes | Depois |
|:---|:---|:---|
| Botões de ação | 10 × `ui.button(...).props("unelevated no-caps")` crus + 3 exceções (`flat`/`outline`/`refresh`) | TODOS via `ui_comum.botao(..., variante="primario", chave_modulo="editar_pdf")` — sem `compacto`/`no_caps` (`telas.py:671-756,786-841`) |
| Avisos | 32 × `ui.notify` cru | `notificar` (`tema_modulo`, tempo configurável em `notificacao_timeout`) — **zerado em `telas.py` em 25/09/2026** (ver "Avisos unificados via `notificar`") |
| Tema | helpers locais `cls_btn`/`estilo_btn` | UMA `ler_tema("editar_pdf", ...)` (`telas.py:87-88`) — tema aplicado pela fábrica `ui_comum.botao` |
| Borda do cabeçalho | `CORES["perigo"]` (vermelho fixo) | `tema["cor_botao"]` — a MESMA cor dos botões do módulo (`telas.py:621`) |
| Título do cabeçalho | `text-grey-9` fixo | colorido por `_app_tema` via `lbl_header_titulo` (`telas.py:624`, `cor_titulo` configurável) |
| Reset de aparência | `PADROES_CFG` com `editar_pdf_cor_*` (nunca lidas) | `editpdf_*` — prefixo real lido por `ler_tema` (`telas.py:572-576`) |
| Cupês de Administração | montagem própria | `bloco_aparencia` reusando o tema único (`telas_administracao.py:175-176`, `com_card=True` — card padrão "Configurações de cores") — o `campo_modulo` foi **removido (06/09)** |

### Código morto removido (25/09/2026) — `salvar_configs` / `resetar_configs`

Duas funções e uma constante foram **removidas de `mod_edit_pdf/telas.py`** por serem
resíduo de um refactor anterior:

| Removido | Motivo |
|:---|:---|
| `salvar_configs()` (~46 linhas) | **Nunca chamada** — a UI real de configuração vive em `mod_edit_pdf/telas_administracao.py`. Referenciava **10 nomes `inp_*` inexistentes** (`inp_cota_global`, `inp_lote_arq`, `inp_lote_mb`, `inp_usuario_gb`, `inp_expira_min`, `inp_txt_titulo`, `inp_txt_hint`, `inp_txt_label`, `inp_txt_header` e os rótulos `lbl_up_titulo`/`lbl_up_hint`/`lbl_header_sub`) |
| `resetar_configs()` (~52 linhas) | **Nunca chamada** — mesma origem; lia e escrevia os mesmos `inp_*` inexistentes |
| `PADROES_CFG` (14 chaves) | Só existia para alimentar `resetar_configs()`. Note que os prefixos eram `editar_pdf_*` (cota/lote/expiração/texto), enquanto as chaves de tema reales lidas por `ler_tema` são `editpdf_*` (sem "ar") — a lista nunca teve efeito sobre o tema |

Como o `try/except` do AGENTS.md §3.2 involve a função inteira, os `NameError` dos
`inp_*` ficavam **engolidos** e o código parecia inofensivo: um def que ninguém chama
não executa, e ninguém vê o erro. Remover o que não é chamado é a correção correta —
não "consertar" as referências, porque a UI que elas controlavam **não existe mais
neste arquivo**.

!!! note "Como saber se um handler está realmente morto"
    `pyflakes` **não** detecta função morta (ele aponta o oposto: nome usado sem
    definição). Para isso, o caminho é `grep` do nome no módulo inteiro: se o
    `def` existe e nenhuma chamada aparece, é código morto. No caso das
    `salvar_configs`/`resetar_configs`, a verificação cruzada de que a UI real está
    em `telas_administracao.py` veio da ausência de qualquer binding `on_click`
    apontando para elas.

**Padronização total dos botões**: "Excluir selecionados" deixou `variante="perigo"` (outline vermelho) e virou `primario` igual aos demais (`telas.py:743-744`); "Enviar agora" deixou `variante="solido"` (`telas.py:754-756`); o botão de atualizar deixou de ser `botao_icone` e virou `botao("Atualizar", ...)` (`telas.py:671-673`). Os helpers locais `cls_btn`/`estilo_btn` foram removidos — o tema é aplicado pela fábrica `ui_comum.botao(chave_modulo="editar_pdf")`. Com o padrão do módulo (chaves `editpdf_*` vazias), os botões usam `PADROES_TEMA` (todos os módulos em `#000000`, a cor do intranet) — **mudança visual intencional**: antes o azul era fixo (`#1565C0`); o override por módulo continua possível no cupê "Aparência".

**Admin padronizado** (`../mod_edit_pdf/telas_administracao.py`): `bloco_aparencia` com card padrão "Configurações de cores" (`com_card=True`); "Configurações específicas" e "Manutenção" como `card_admin` recolhíveis com o rodapé padrão de 2 botões (`rodape_salvar_restaurar` — Restaurar padrão + Aplicar, recarregando após 1 s); `painel_backup` ao final.

Coberto por `test/verifica_ui_comum.py` (190 verificações — seção "edit_pdf migrado (fonte)": `ui.notify` zerado, ≥5 `botao(`, helpers locais ausentes, sem `CORES` fixas em `telas.py`, borda do cabeçalho = `tema["cor_botao"]`, hexes fora dos defaults de reset e ausência das exceções cruas).
- **Aparência** (Administração): padronização de tema dos botões — cor de fundo, cor do texto, cor de fundo da página do editor, cor dos títulos e tamanho dos botões (`small`/`medium`/`large`). Cada cor usa `ui.color_input` (seletor de cor **e** digitação direta hex/RGB). Valem sem restart (leitura live via `ler_tema`). O cupê agora é o **padronizado pelo helper central** `mod_intranet/tema_modulo.py::bloco_aparencia` (prefixo `editpdf_*`), **com botão Salvar próprio** e "Restaurar padrão". O cupê **"Edição do módulo"** (`campo_modulo`) foi **removido (06/09)** — a edição de nome de exibição, ícone e status do módulo é **exclusiva do painel central `/configuracoes`** (aba Módulo, admin geral). Com as chaves de botão `editpdf_*` vazias (padrão), os botões usam o **padrão do módulo** (`PADROES_TEMA` — todos os módulos em `#000000`, a cor do intranet — sem herança do tema do sistema).

## Avisos unificados via `notificar` (25/09/2026 — commit `624c9d5`)

Este era o **único módulo de tela com `ui.notify` cru remanescente**, violando o AGENTS.md §5.1
("nunca `ui.notify` cru"). O commit `624c9d5` converteu **22 chamadas** em
`mod_edit_pdf/telas.py`.

### O que era o `ui.notify` cru

As 22 chamadas não eram avisos de negócio — eram o **terceiro e último nível de defesa** de
cada handler. O padrão do módulo é uma cadeia de três `try/except` aninhados (AGENTS.md §3.2):

```python
except Exception as e:                              # nível 1 — regra de negócio
    log.exception(f"erro interno em X: {e}")        #   registra a causa real
    notificar(f"Erro em X: {e}", tipo="error")      #   aviso com a causa
except Exception:                                    # nível 2 — nem o aviso funcionou
    try:
        ui.notify(f"Erro em X", type="negative")    #   ⚠️ CRU — ignorava o timeout
    except Exception:
        pass                                         # nível 3 — falha silenciosa
```

O nível 2 recebia a mensagem **sem a causa** (`f"Erro em X"`, sem `: {e}`) e usava
`ui.notify(..., type="negative")` diretamente — ou seja, o usuário via um toast com **duração
default da NiceGUI**, ignorando o `notificacao_timeout` configurado pelo administrador, e sem a
cor do tema do módulo. Foram convertidas para `notificar(f"Erro em X", type="negative")`
(`notificar` aceita `type=` e normaliza para `tipo=`), unificando o tempo e o tema.

Os 22 pontos convertidos cobrem exatamente os **callbacks e helpers que a tela executa**:
`_fmt_bytes`, `_fmt_resta`, `_cor_resta`, `_rows_do_evento`, `_ao_selecionar`, `_renumerar`,
`atualizar_tabela`, `_alvos`, `_registrar_saida`, `_op_reduzir`, `_op_juntar`, `_op_cortar_sel`,
`_op_dividir`, `_op_verificar`, `baixar_zip`, `excluir_selecionados`, `baixar_originais`,
`expirar_agora`, `_montar_hint`, `_baixar_linha`, `_excluir_linha` e o próprio `mostrar_tela`.

### Comportamento resultante

| Propriedade | Efeito no módulo |
|:---|:---|
| Tempo | **76 chamadas** a `notificar(` em `telas.py` (7 em `telas_administracao.py`) passam a respeitar `notificacao_timeout` — chave da `tb_config` central, **1–30 s, padrão 5** (`tema_modulo.notificacao_timeout()`, clamp `min(30, max(1, v))`) |
| Precedência | `notificar` faz `kwargs.setdefault("timeout", notificacao_timeout())` — um `timeout=` explícito no ponto de chamada **vence** o configurado; nenhum aviso deste módulo passa `timeout=` explícito, então todos seguem a configuração |
| Tema | o tipo é repassado ao `ui.notify` (`positive`/`negative`/`warning`); com as chaves `editpdf_*` no padrão, o toast sai na cor do módulo |
| **Fail-soft** | `notificar` **nunca derruba a tela**: `try: ui.notify(msg, type=tipo, **kwargs)` → `except: try: ui.notify(msg)` → `except: pass`. Uma notificação que falha (slot de UI já desmontado, evento após `ui.navigate.reload()`, cliente desconectado) é engolida de propósito, porque o aviso é acessório e a exceção subir derrubaria o handler |
| Formato | `multi_line=True` nos avisos de upload (lista de recusados com motivo), garantindo legibilidade sem truncamento |

!!! warning "Lacuna conhecida — `telas_administracao.py:56`"
    A conversão atingiu 100 % de `telas.py`, mas **1 `ui.notify` cru permanece** em
    `mod_edit_pdf/telas_administracao.py:56` (nível 2 de `_fmt_bytes`, mesma cadeia de três
    níveis). A guarda de QA `verifica_ui_comum.py:641-643` faz
    `EPDF = ler("mod_edit_pdf/telas.py")` — leu **só a tela**, nunca o painel de Administração —
    então `EPDF.count("ui.notify(") == 0` passa mesmo com o resíduo no arquivo irmão.
    **Correção proposta (1 linha):** `notificar(f"Erro em _fmt_bytes", type="negative")`
    (o helper já é importado no arquivo, linha 25) **e** ampliar a guarda para
    `ler("mod_edit_pdf/telas_administracao.py")` com o mesmo `count("ui.notify(") == 0`.

## Regras de negócio relevantes

- **Cotas em 4 níveis**, todas lidas de `tb_config` central a cada uso:
  - global: uso real em disco de `mod_edit_pdf/editorPDF/` ≤ `cotadisco_global_gb` (default 10 GB);
  - por usuário: `editar_pdf_usuario_gb` (default 1 GB);
  - lote: `editar_pdf_lote_arquivos` arquivos / `editar_pdf_lote_mb` MB numa janela deslizante de 60 s (`JANELA_LOTE_S` em `telas.py`, não configurável — o valor de MB é teto **por envio/lote**, não acumulado por usuário);
  - estoque: máximo simultâneo de arquivos tipo `upload` por usuário (= limite do lote, via `contar_uploads_ativos()` — conta só arquivos `upload`/`ativo=1` ainda presentes em disco).
- **Limite de MB é por ENVIO, não acumulado**: `_receber_lote` faz **pré-checagem** de `ativos_upload+len(pdfs) > lote_max` e `sum(f.size()) > lote_bytes_max` **antes** de gravar qualquer arquivo (rejeita nominalmente o lote inteiro), depois valida por-arquivo na janela de 60 s. Um envio único de 350 MB com limite 200 MB é recusado de imediato.
- **Expiração**: executada pelo scheduler do núcleo a cada 1 min (sem login), critério mtime; remove do disco, inativa registro, devolve cota e audita como ator `sistema`.
- **Prefixo obrigatório**: `dataHora_usuario_operacao_nomeArquivo.pdf` — cada usuário vê apenas os próprios arquivos.
- **Auditoria com SHA-256**: upload grava `upload_hash`; reduzir/juntar/cortar gravam hashes das origens na descrição e hash do resultado no campo `hash_arquivo`; dividir audita origens; tipos extras: `erro_reducao`, `configuracao`, `expiracao`, `deletar`.

## Referência operacional — espaço, cotas, expiração e operações

### Espaço temporário por usuário

Todo arquivo vive **dentro do módulo**, nunca fora dele (AGENTS.md §1):

```
mod_edit_pdf/editorPDF/              # PASTA_EDITOR — raiz do espaço temporário
└── <usuario>/                       # pasta_usuario(usuario) — criada on demand (makedirs exist_ok)
    ├── 20260925T153012_maria_upload_relatorio.pdf      # nome_padronizado()
    ├── 20260925T153044_maria_saida_20260925T153012_maria_upload_relatorio.pdf
    └── 20260925T153210_maria_zip_selecao.zip
```

- **Isolamento por usuário é físico**, não apenas lógico: cada login tem sua própria subpasta e
  `obter_meus_arquivos(usuario)` filtra por `usuario` — um usuário **nunca** vê nem apaga arquivo
  de outro, mesmo que manipule o id na URL.
- **`nome_padronizado(usuario, operacao, nome_original)`** monta
  `dataHora_usuario_operacao_nomeArquivo` com `dataHora` = `%Y%m%d%H%M%S` e o nome original
  **sanitizado** (só `isalnum()` e `.`, `_`, `-`, espaço; truncado em 60 caracteres). O prefixo é
  o que torna a expiração por `mtime` segura (o mtime do arquivo nunca é falsificado pelo nome).
- **Raiz `editorPDF/`** nunca é servida como estático: só é percorrida por `uso_global_bytes()`
  (cota global real em disco), por `expirar_antigos()` (job) e pelos ganchos de usuário
  (`remover_vinculos_usuario`, `renomear_usuario`).

### Cotas — 4 níveis, todos com default no código

| Nível | Chave de configuração | Default | Onde é aplicado | Semântica |
|:---|:---|:---|:---|:---|
| Global | `cotadisco_global_gb` (chave **central**, sem prefixo) | **10 GB** (`QUOTA_GLOBAL_BYTES_DEFAULT`) | `verificar_quota()` — `SUM(tamanho_bytes) WHERE ativo=1` + o arquivo entrando | uso real do banco; aviso `Cota global excedida (10 GB)` |
| Por usuário | `editar_pdf_usuario_gb` | **1 GB** (`cfg_usuario_gb`, mín. 1) | `verificar_quota()` — `tb_cota_disco.total_usado_bytes` | aviso `Sua cota de 1 GB foi excedida` |
| Por lote (arquivos) | `editar_pdf_lote_arquivos` | 10 (`cfg_lote_arquivos`, mín. 1) | pré-checagem do lote inteiro **e** janela de 60 s | teto de arquivos `upload` ativos do usuário |
| Por lote (MB) | `editar_pdf_lote_mb` | 1024 (`cfg_lote_mb`, mín. 1) | idem | teto de MB **por envio**, nunca acumulado |

!!! tip "Ordem de validação do upload (`_receber_lote`, `telas.py:161-253`)"
    1. **Janela deslizante** de `JANELA_LOTE_S = 60` s descarta envios antigos do `deque lote`.
    2. **Filtro de formato** — só `.pdf` (case-insensitive) entra; o resto vai nominalmente para
       `recusados` com o motivo `formato não-PDF`.
    3. **Pré-checagem do lote inteiro** (`ativos_upload + len(pdfs) > lote_max`, depois
       `sum(f.size()) > lote_bytes_max`) — ocorre **antes de gravar qualquer byte**, então um
       envio único de 350 MB com limite 200 MB é recusado de imediato, e não "aceito pela metade".
    4. **Validação por arquivo** na janela de 60 s, e `verificar_quota()` antes de cada `save`.
    5. Grava com `nome_padronizado`, chama `registrar_arquivo` (transação atômica
       `tb_arquivos` + `tb_cota_disco`); se a gravação falhar, **remove o arquivo do disco** e
       manda o nome para `recusados` com `falha ao registrar` — nunca deixa órfão.
    6. `audit_log(..., "upload_hash", f"{nome} sha256=...")`.
    7. Resumo: sucesso em `text-green-8`, **`NÃO ENVIADOS (n) → 'nome' (motivo)` em `text-red-8`**
       (nunca falha silencioso) + um `notificar(..., multi_line=True)` com o resumo.

### Expiração — padrão 10 min

- **Automática:** job `cleanup_pdf` do núcleo (`mod_intranet/rotinas.py`, **a cada 1 min**,
  **sem usuário logado** — basta o servidor vivo) chama
  `expirar_antigos(minutos=cfg_expiracao_min())` com `editar_pdf_expiracao_min` (default **10**).
- **Critério:** `mtime` do arquivo, não a data do banco — `agora - os.path.getmtime(caminho) > minutos*60`.
- **Efeito:** `os.remove` no disco → para os usuários tocados, `UPDATE tb_arquivos SET ativo=0`
  dos registros cujo arquivo não existe mais → devolve a cota com
  `MAX(0, total_usado_bytes - liberado)` (nunca fica negativo) → `audit_log("sistema", "edit-pdf",
  "expiracao", …)`.
- **Manual:** botão **"Expirar agora"** no card "Manutenção"
  (`telas_administracao._expirar_agora`) roda exatamente a mesma função.
- **Efeito colateral importante:** expirar é o mecanismo que **destrava a cota**. Como a cota é
  de uso, e não de envio, um usuário que lotou 1 GB tem que esperar a expiração (ou excluir) para
  voltar a enviar — por isso o texto de recusa orienta "aguarde expiração ou exclua".
- **Falha nunca derruba:** toda a função é `try/except`; erro no banco faz `rollback()` e
  retorna `0`; erro na varredura de disco só registra `debug` por arquivo e segue.

### Operações e `data-testid`

| Ação na UI | `data-testid` | Handler (`telas.py`) | Motor | Auditoria |
|:---|:---|:---|:---|:---|
| Atualizar lista | `editar_pdf-atualizar` | `atualizar_tabela` (timer 5 s) | — | — |
| Verificar integridade | `editar_pdf-verificar` | `_op_verificar` | `op_verificar` | **não audita** — só `notificar(ok/msg)` por arquivo (operação de leitura) |
| Juntar selecionados | `editar_pdf-juntar` | `_op_juntar` (exige ≥ 2 PDFs) | `op_juntar` | `juntar` — `sha256 origem=[…]` no texto + resultado em `hash_arquivo` (`_auditar_hash`) |
| Excluir selecionados | `editar_pdf-excluir` | `excluir_selecionados` | `deletar_arquivo` | `deletar` (dentro de `bd_manipulador`, com estorno de cota) |
| Baixar ZIP | `editar_pdf-baixar-zip` | `baixar_zip` | `zip_por_ids` | `zip` — `arquivos=N sha256=…` |
| Baixar PDFs individuais | `editar_pdf-baixar-pdfs` | `baixar_originais` | — | — |
| Enviar agora (reenvio) | `editar_pdf-enviar` | `up.reset()` + `_receber_lote` | — | `upload_hash` (um por arquivo) |
| Modo de redução | `editar_pdf-modo-reduzir` | toggle `Leve`/`Agressivo` | — | — |
| Reduzir | `editar_pdf-reduzir` | `_op_reduzir` | `op_reduzir` (leve/agressivo) | sucesso: `reduzir` (`_auditar_hash`); falha: `erro_reducao` com `hash_arquivo` do **original** |
| Cortar | `editar_pdf-cortar` | `_op_cortar_sel` | `op_cortar` (pares/ímpares/lista `"2-5,8"`) | `cortar` via `_auditar_hash` |
| Dividir | `editar_pdf-dividir` | `_op_dividir` | `op_dividir_partes` (`pagina`/`parimpar`/`cortes`/`intervalos`) | `dividir` — `modo=… filtro='…' bib=… arquivos=N sha256_origem=…` |
| *(legado)* upload | `editpdf-upload` | `span.hidden` de compat | — | — |

!!! note "Ordem que o Juntar respeita"
    `op_juntar(alvos, out)` recebe os caminhos **na ordem de marcação** dos checkboxes
    (`ordem_ids` → `_alvos()`), não em ordem alfabética nem de upload. A tela confirma isso com
    o aviso `Junção na ordem dos # : a → b → c` e a coluna "Expira em"/badge `#` existe
    exatamente para tornar essa ordem visível ao usuário. Se a mensagem de retorno contiver
    `IGNORADOS`, o aviso sai em `warning` em vez de `positive` (o arquivo foi gerado, mas some
    entrada foi descartada — a UI não pode dizer "sucesso" e esconder isso).

O `editpdf-upload` (sem o `_` no meio) é um `ui.element("span").classes("hidden")` mantido
**só** para não quebrar seletores Playwright antigos; o selador oficial é `editar_pdf-enviar`.
Os `data-testid` são aplicados via `.props('data-testid=…')` sobre o retorno da fábrica
`ui_comum.botao(...)` — o botão já padronizado continua sendo o alvo do teste (AGENTS.md do
`kbp-qa`: `data-testid` **sempre** por `.props()`, nunca `id`).

## Integrações com o núcleo

Usa `get_connection`/`get_config`/`set_config` centrais e `audit_log`. Chaves de configuração: `cotadisco_global_gb`, `editar_pdf_lote_arquivos`, `editar_pdf_lote_mb`, `editar_pdf_usuario_gb`, `editar_pdf_expiracao_min` (lidas via `cfg_*` em `bd_manipulador.py`); textos da tela: `editar_pdf_texto_upload_titulo`, `editar_pdf_texto_upload_hint`, `editar_pdf_texto_upload_label`, `editar_pdf_texto_header_sub`; tema: `editpdf_cor_botao`, `editpdf_cor_texto_botao`, `editpdf_cor_fundo`, `editpdf_cor_titulo`, `editpdf_btn_tamanho` (prefixo `editpdf_*` — distinto do prefixo `editar_pdf_*` das cotas). O scheduler central (`mod_intranet/rotinas.py`, job `cleanup_pdf` a cada 1 min) chama `expirar_antigos(minutos=cfg_expiracao_min())` diretamente.

**Versão individual do módulo**: `versao_modulo:editar_pdf = 1.0.260908` (em `tb_config` central — seed principal idempotente em `bd_conexao.init_db()`; o `bd_manipulador.py::_semear_versao_modulo` é duplicado inofensivo). Exibida no rodapé ao lado da versão global quando o usuário navega em `/edit-pdf`. Atualizar manualmente a cada alteração do `mod_edit_pdf` — não mexer na versão global nem na dos demais módulos.

## Pontos de atenção

- `bd_criador.py` morto/divergente — não executar.
- Motor de PDF mora em `mod_intranet/pdf_operacoes.py` (re-exportado por `bd_manipulador.py`): `hash_sha256`, `op_reduzir` (leve/agressivo), `op_juntar`, `op_cortar`, `op_dividir` (legado 1 filtro), `op_dividir_partes` (vigente: modos `pagina`/`parimpar`/`cortes`/`intervalos`), `op_verificar`, mais helpers `partes_*`. A tela usa `op_dividir_partes`.
- ZIP tem duas entradas: `zip_do_usuario()` (todos os ativos) e `zip_por_ids()` (só ids marcados — usada pela tela); `deletar_arquivo()` faz disco + soft delete + estorno de cota com auditoria `deletar`.
- Ganchos LGPD/usuário: `remover_vinculos_usuario()` (remove disco + registros + cota) e `renomear_usuario()` (propaga renomeio em `tb_arquivos`/`tb_cota_disco`); `contar_arquivos_ativos()` alimenta o Resumo do `main.py`.
- `data-testid` da tela (`telas.py`): `editar_pdf-atualizar`, `editar_pdf-verificar`, `editar_pdf-juntar`, `editar_pdf-excluir`, `editar_pdf-baixar-zip`, `editar_pdf-baixar-pdfs`, `editar_pdf-enviar`, `editar_pdf-modo-reduzir`, `editar_pdf-reduzir`, `editar_pdf-cortar`, `editar_pdf-dividir` (+ compat legada `editpdf-upload`).
- Expiração manual "Expirar agora" (`telas_administracao._expirar_agora`) chama `expirar_antigos(minutos=cfg_expiracao_min())`; a automática roda via job `cleanup_pdf` (1 min, sem login) com critério mtime, inativando registros e devolvendo cota como ator `sistema`.
- **`_cfg` depende de `get_config` importado** no topo de `bd_manipulador.py`. Se faltar `get_config` no `from mod_intranet.bd_conexao import …`, cada leitura cai em `NameError`→`except`→ retorna **sempre o default** (bug real: MB configurado em 200 e o sistema usava 1024; arquivos configurados em 100 e usava 10). Conferir o import ao mexer no topo do arquivo.
- Limite de "estoque de uploads" reaproveita o valor do limite de lote (não é configurável separadamente).
- Redução Agressivo transforma texto em imagem (perde seleção/busca no PDF).
- `cfg_tema` em `bd_manipulador.py:74` ficou **sem uso** após a migração da tela para `ler_tema` (06/09) — código morto candidato a remoção.
- **`ui.notify` cru remanescente em `telas_administracao.py:56`** (nível 2 de `_fmt_bytes`) — ver "Avisos unificados via `notificar`". A guarda de QA lê só `telas.py`; ampliar a guarda para o arquivo de Administração fecha a lacuna.

## Status — Fase 5 do PLANO.md

Fase essencialmente **concluída**: banco + cotas + limites de lote; expiração automática agendada; prefixo padronizado; todas as operações (reduzir/juntar/cortar/dividir/verificar/ZIP/excluir); auditoria com SHA-256 origem/destino; estoque de uploads; **tema padronizado** (boas práticas: botões/tamanho/cores via `ui.color_input`); testes ponta a ponta em `test/test_editor_pdf.py` (32 verificações passando — o README diz "20", número defasado). Única pendência conceitual é o legado `bd_criador.py`.

### Correção registrada — limite de MB ignorado

Bug real: limites configurados não eram aplicados porque faltava o import de `get_config` em `../mod_edit_pdf/bd_manipulador.py` — `_cfg` sempre retornava o default (`editpdf_lote_mb`=1024 em vez de 200). Corrigido restaurando o import e reforçado com a pré-checagem do lote inteiro em `_receber_lote` (`telas.py`).

### Cupê de Aparência padronizado (helper central)

O cupê "Aparência" (cor de botões, texto, fundo, títulos e tamanho) passou a usar o **helper
central** `mod_intranet/tema_modulo.py::bloco_aparencia`, que **possui botão "Salvar" próprio**
(cada cor é persistida via `salvar_tema` e a tela é recarregada) e "Restaurar padrão". Antes, os
campos de cor do cupê ficavam **sem botão salvar dedicado** (o salvamento dependia do botão
"Salvar configurações" do cartão de cotas/textos), o que dificultava aplicar a alteração. O cupê
"Edição do módulo" (`campo_modulo`), adicionado à época, foi **removido em 06/09** — a edição do
módulo ficou exclusiva do painel central `/configuracoes`.

Regra de uniformidade e mapeamento de prefixos cobertos por `test/test_tema.py` (18 verificações
standalone).

### Adições recentes (09/2026) — responsividade global RNF-UI-01

- **Já responsivo** — botões centralizados `w-full justify-center flex-wrap` `gap` via `.style` `min-width:0`, toggle `spread`, grids responsivos `grid-cols-1 sm:grid-cols-2 md:grid-cols-3`; `overflow-x-auto` em tabelas, `scroll_area` altura explícita. Auditado 320/768/1024 (`kbp-web-design`) com checklist P0/P1/P2 por `container`/`row`/`grid` (sem pendências P0).

## Pendência QA — WAL + paridade SQLite↔Postgres (24/09/2026, sem correção aplicada)

> Documentação da correção pendente. Nenhum `.py` alterado neste lote.

| Módulo | Achado | Arquivo:linha | Correção proposta contida no módulo | Risco regressão |
|:---|:---|:---|:---|:---|
| edit_pdf | Sem `CrudBase`; `strftime` só em Python (sem quebra); auditar `GROUP BY`/`COLLATE` | `mod_edit_pdf/bd_manipulador.py:215`, `:423` (`strftime` Python — OK) | Migrar para `CrudBase` + `conexao("editar_pdf")`; varredura `GROUP BY`/`COLLATE` interna | Médio (cotas 1 GB/10 GB + expiração 10 min + ZIP) |

Detalhe consolidado em [Plano WAL + Paridade](registro_de_mudancas/wal_paridade_pendente_2026-09-24.md).
