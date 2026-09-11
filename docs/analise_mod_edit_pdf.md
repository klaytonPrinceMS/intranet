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
| Avisos | 32 × `ui.notify` cru | `notificar` (`tema_modulo`, tempo configurável em `notificacao_timeout`) |
| Tema | helpers locais `cls_btn`/`estilo_btn` | UMA `ler_tema("editar_pdf", ...)` (`telas.py:87-88`) — tema aplicado pela fábrica `ui_comum.botao` |
| Borda do cabeçalho | `CORES["perigo"]` (vermelho fixo) | `tema["cor_botao"]` — a MESMA cor dos botões do módulo (`telas.py:621`) |
| Título do cabeçalho | `text-grey-9` fixo | colorido por `_app_tema` via `lbl_header_titulo` (`telas.py:624`, `cor_titulo` configurável) |
| Reset de aparência | `PADROES_CFG` com `editar_pdf_cor_*` (nunca lidas) | `editpdf_*` — prefixo real lido por `ler_tema` (`telas.py:572-576`) |
| Cupês de Administração | montagem própria | `bloco_aparencia` reusando o tema único (`telas_administracao.py:175-176`, `com_card=True` — card padrão "Configurações de cores") — o `campo_modulo` foi **removido (06/09)** |

**Padronização total dos botões**: "Excluir selecionados" deixou `variante="perigo"` (outline vermelho) e virou `primario` igual aos demais (`telas.py:743-744`); "Enviar agora" deixou `variante="solido"` (`telas.py:754-756`); o botão de atualizar deixou de ser `botao_icone` e virou `botao("Atualizar", ...)` (`telas.py:671-673`). Os helpers locais `cls_btn`/`estilo_btn` foram removidos — o tema é aplicado pela fábrica `ui_comum.botao(chave_modulo="editar_pdf")`. Com o padrão do módulo (chaves `editpdf_*` vazias), os botões usam `PADROES_TEMA` (todos os módulos em `#000000`, a cor do intranet) — **mudança visual intencional**: antes o azul era fixo (`#1565C0`); o override por módulo continua possível no cupê "Aparência".

**Admin padronizado** (`../mod_edit_pdf/telas_administracao.py`): `bloco_aparencia` com card padrão "Configurações de cores" (`com_card=True`); "Configurações específicas" e "Manutenção" como `card_admin` recolhíveis com o rodapé padrão de 2 botões (`rodape_salvar_restaurar` — Restaurar padrão + Aplicar, recarregando após 1 s); `painel_backup` ao final.

Coberto por `test/verifica_ui_comum.py` (190 verificações — seção "edit_pdf migrado (fonte)": `ui.notify` zerado, ≥5 `botao(`, helpers locais ausentes, sem `CORES` fixas em `telas.py`, borda do cabeçalho = `tema["cor_botao"]`, hexes fora dos defaults de reset e ausência das exceções cruas).
- **Aparência** (Administração): padronização de tema dos botões — cor de fundo, cor do texto, cor de fundo da página do editor, cor dos títulos e tamanho dos botões (`small`/`medium`/`large`). Cada cor usa `ui.color_input` (seletor de cor **e** digitação direta hex/RGB). Valem sem restart (leitura live via `ler_tema`). O cupê agora é o **padronizado pelo helper central** `mod_intranet/tema_modulo.py::bloco_aparencia` (prefixo `editpdf_*`), **com botão Salvar próprio** e "Restaurar padrão". O cupê **"Edição do módulo"** (`campo_modulo`) foi **removido (06/09)** — a edição de nome de exibição, ícone e status do módulo é **exclusiva do painel central `/configuracoes`** (aba Módulo, admin geral). Com as chaves de botão `editpdf_*` vazias (padrão), os botões usam o **padrão do módulo** (`PADROES_TEMA` — todos os módulos em `#000000`, a cor do intranet — sem herança do tema do sistema).

## Regras de negócio relevantes

- **Cotas em 4 níveis**, todas lidas de `tb_config` central a cada uso:
  - global: uso real em disco de `mod_edit_pdf/editorPDF/` ≤ `cotadisco_global_gb` (default 10 GB);
  - por usuário: `editpdf_usuario_gb` (default 1 GB);
  - lote: `editpdf_lote_arquivos` arquivos / `editpdf_lote_mb` MB numa janela deslizante de 60 s (o valor de MB é teto **por envio/lote**, não acumulado por usuário);
  - estoque: máximo simultâneo de arquivos tipo `upload` por usuário (= limite do lote).
- **Limite de MB é por ENVIO, não acumulado**: `_receber_lote` faz **pré-checagem** de `ativos_upload+len(pdfs) > lote_max` e `sum(f.size()) > lote_bytes_max` **antes** de gravar qualquer arquivo (rejeita nominalmente o lote inteiro), depois valida por-arquivo na janela de 60 s. Um envio único de 350 MB com limite 200 MB é recusado de imediato.
- **Expiração**: executada pelo scheduler do núcleo a cada 1 min (sem login), critério mtime; remove do disco, inativa registro, devolve cota e audita como ator `sistema`.
- **Prefixo obrigatório**: `dataHora_usuario_operacao_nomeArquivo.pdf` — cada usuário vê apenas os próprios arquivos.
- **Auditoria com SHA-256**: upload grava `upload_hash`; reduzir/juntar/cortar gravam hashes das origens na descrição e hash do resultado no campo `hash_arquivo`; dividir audita origens; tipos extras: `erro_reducao`, `configuracao`, `expiracao`, `deletar`.

## Integrações com o núcleo

Usa `get_connection`/`get_config`/`set_config` centrais e `audit_log`. Chaves de configuração: `cotadisco_global_gb`, `editpdf_lote_arquivos`, `editpdf_lote_mb`, `editpdf_usuario_gb`, `editpdf_expiracao_min`; tema: `editpdf_cor_botao`, `editpdf_cor_texto_botao`, `editpdf_cor_fundo`, `editpdf_cor_titulo`, `editpdf_btn_tamanho`. O scheduler central chama `expirar_antigos()` diretamente.

**Versão individual do módulo**: `versao_modulo:editar_pdf = 1.0.260908` (em `tb_config` central — seed principal idempotente em `bd_conexao.init_db()`; o `bd_manipulador.py::_semear_versao_modulo` é duplicado inofensivo). Exibida no rodapé ao lado da versão global quando o usuário navega em `/edit-pdf`. Atualizar manualmente a cada alteração do `mod_edit_pdf` — não mexer na versão global nem na dos demais módulos.

## Pontos de atenção

- `bd_criador.py` morto/divergente — não executar.
- **`_cfg` depende de `get_config` importado** no topo de `bd_manipulador.py`. Se faltar `get_config` no `from mod_intranet.bd_conexao import …`, cada leitura cai em `NameError`→`except`→ retorna **sempre o default** (bug real: MB configurado em 200 e o sistema usava 1024; arquivos configurados em 100 e usava 10). Conferir o import ao mexer no topo do arquivo.
- Limite de "estoque de uploads" reaproveita o valor do limite de lote (não é configurável separadamente).
- Redução Agressivo transforma texto em imagem (perde seleção/busca no PDF).
- `cfg_tema` em `bd_manipulador.py:74` ficou **sem uso** após a migração da tela para `ler_tema` (06/09) — código morto candidato a remoção.

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
