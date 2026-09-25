# PDF Editor Module — `mod_edit_pdf`

> PDF editor module: route `/edit-pdf` (key `editar_pdf`) · own database `db_mod_edit_pdf.db` · per-user temp space, quotas, SHA-256 audit, scheduled expiration.

---

# Módulo Editor de PDF — `mod_edit_pdf`

> Módulo de edição de PDF: rota `/edit-pdf` (chave `editar_pdf`) · banco próprio `db_mod_edit_pdf.db` · espaço temporário por usuário, cotas, auditoria SHA-256, expiração agendada.

## Propósito

Editor de PDFs multiusuário com espaço temporário por usuário em `mod_edit_pdf/editorPDF/`. O usuário envia PDFs em lote e aplica operações sobre uma seleção ordenada (reduzir, juntar, cortar, dividir, verificar, ZIP, excluir). Arquivos expiram automaticamente. Aba de Administração exclusiva do `administrador_geral` para cotas, limites e expiração — configurável sem restart.

## Banco de dados

Criador vigente: `init_db_pdf()` em `bd_manipulador.py:92-123`.

- **`tb_arquivos`**: `id`, `nome_arquivo`, `usuario`, `tamanho_bytes`, `operacao` (upload/saida/zip), `data_operacao`, `ativo`.
- **`tb_cota_disco`**: `usuario` PK, `total_usado_bytes`, `atualizado_em`.

⚠️ O `bd_criador.py` do módulo é **legado/morto** com esquema divergente — não executar (criaria tabelas erradas no banco central).

## Funcionalidades

- **Abas**: Editor (sempre) | Administração (só admin geral). Cabeçalho mostra uso da cota do usuário (global só p/ admin).
- **Upload múltiplo** com auto-upload, somente `.pdf`; recusados listados nominalmente com o motivo; "Enviar agora" para reenvio.
- **Arquivos no servidor**: seleção múltipla estável entre refreshes (timer 5 s), badges "#" com ordem de marcação (merge respeita), coluna "Expira em" com contagem regressiva colorida.
- **Operações**: Verificar integridade, Juntar, Excluir selecionados, ZIP, download individual; menu de contexto por linha.
- **Reduzir tamanho**: modo Leve (recompressão; biblioteca auto `pymupdf→pikepdf→pypdf`) ou Agressivo (rasteriza como JPEG, DPI 50–400, qualidade 10–100%).
- **Cortar** (pares/ímpares/lista "2-5,8") e **Dividir** (página-a-página, par/ímpar, cortes ou intervalos).
- **Administração** (padrão de cards dos módulos, 06/09): card **"Configurações de cores"** (prévia ao vivo), card **"Configurações específicas"** (cota global GB default 10, máx. arquivos/lote, MB/lote, cota por usuário GB, minutos de expiração e textos da tela) e card **"Manutenção"** ("Expirar agora") — todos recolhíveis (`card_admin`) com o rodapé padrão de 2 botões ("Restaurar padrão" + "Aplicar") exclusivos do card, recarregando após 1s; ao final, card padrão de backup do banco (`painel_backup`).
- **Aparência** (Administração): tema do módulo via card padrão **"Configurações de cores"** (`tema_modulo.bloco_aparencia` — `mod_edit_pdf/telas_administracao.py:175`, `com_card=True` — prévia ao vivo e rodapé 2 botões) — campos **"Cor geral do módulo"** (`editpdf_cor_botao`), "Cor do texto do módulo", fundo, título, tamanho (`editpdf_*`) montados pelas fábricas `campo_cor`/`campo_selecao`. Este módulo é o **módulo exemplo** do padrão de exibição: área cheia (`w-full`) e card "Configurações de cores" com as 6 chaves (`cor_botao`, `cor_texto_botao`, `cor_fundo`, `cor_titulo`, `btn_tamanho`, `texto_header`), replicado aos demais módulos. Com as chaves de botão `editpdf_*` **vazias** (padrão atual), os botões usam o **padrão do módulo** (`PADROES_TEMA` — todos os módulos em `#000000`, a cor do intranet — sem herança do tema do sistema); o override por módulo continua possível no card.
- **Padrões centrais de UI (06/09)**: TODOS os botões de ação usam o MESMO padrão `ui_comum.botao(..., variante="primario", chave_modulo="editar_pdf")` — sem `compacto`/`no_caps` — inclusive "Excluir selecionados" (deixou `variante="perigo"`), "Enviar agora" (deixou `variante="solido"`) e o botão "Atualizar" (deixou de ser `botao_icone`); 32 avisos via `notificar` (tempo configurável em `notificacao_timeout`); tema único via `ler_tema("editar_pdf", ...)` (helpers locais `cls_btn`/`estilo_btn` removidos de `telas.py`); borda do cabeçalho = `tema["cor_botao"]` (antes `CORES["perigo"]` fixo) e título colorido por `_app_tema` via `lbl_header_titulo`; `PADROES_CFG` corrigido para o prefixo real `editpdf_*` (antes `editar_pdf_cor_*`, nunca lidas). Detalhes em [Análise do Módulo](../analise_mod_edit_pdf.md).
- **Avisos unificados (25/09/2026, commit `624c9d5`)**: **22 chamadas de `ui.notify(...)` cru foram trocadas por `tema_modulo.notificar()`** em `telas.py` — o módulo **não usa mais aviso cru na tela** e passa a respeitar o tempo configurável `notificacao_timeout` (**1–30 s, padrão 5**) em **todos** os avisos (76 chamadas a `notificar` em `telas.py`, 7 em `telas_administracao.py`). As 22 eram o **nível 2 de defesa** dos handlers (a cadeia de três `try/except` do AGENTS.md §3.2): um `ui.notify(..., type="negative")` sem a causa e com a duração default da NiceGUI, disparado só quando o `notificar(..., tipo="error")` primário também falhava. `notificar` é **fail-soft** (nunca derruba a tela), aceita `tipo=` ou `type=`, e só usa o timeout configurado quando o ponto de chamada **não** passa `timeout=` explícito — o que não ocorre neste módulo. Lacuna conhecida: **1 `ui.notify` cru sobrou** em `telas_administracao.py:56`, fora do alcance da guarda de QA (que lê só `telas.py`).
- **Responsividade (RNF-UI-01, 09/2026 — auditado 320/768/1024 `kbp-web-design`)**: botões centralizados `w-full justify-center flex-wrap` `gap` via `.style` `min-width:0`, toggle `spread`, grids responsivos `grid-cols-1 sm:grid-cols-2 md:grid-cols-3`; `overflow-x-auto` em tabelas, `scroll_area` altura explícita; proposta P0/P1/P2 por `container`/`row`/`grid` já aplicada.
- **Versionamento**: `versao_modulo:editar_pdf = 1.0.260908`.

## Regras de negócio

- **Espaço temporário por usuário** — `mod_edit_pdf/editorPDF/<usuario>/` (pasta criada on demand por `pasta_usuario()`). O isolamento é **físico**, não só lógico: `obter_meus_arquivos(usuario)` filtra por usuário e um login nunca vê nem apaga arquivo de outro. `nome_padronizado(usuario, operacao, nome_original)` monta `dataHora_usuario_operacao_nomeArquivo` (`%Y%m%d%H%M%S` + nome sanitizado em 60 chars) — o prefixo é o que torna a expiração por `mtime` segura. A raiz `editorPDF/` nunca é servida como estático.
- **Cotas em 4 níveis** (global `cotadisco_global_gb` default **10 GB**, por usuário `editar_pdf_usuario_gb` default **1 GB**, por lote `editar_pdf_lote_arquivos` (10) / `editar_pdf_lote_mb` (1024) em janela de 60 s `JANELA_LOTE_S`, estoque via `contar_uploads_ativos()`) lidas de `tb_config` central a cada uso. Ordem de validação do upload: janela deslizante → filtro `.pdf` → **pré-checagem do lote inteiro** (antes de gravar qualquer byte) → validação por arquivo na janela + `verificar_quota()` → grava e audita o SHA-256. Se a gravação falhar, remove o arquivo do disco (nunca deixa órfão) e manda o nome para `recusados`.
- **Limite de MB é por envio, não acumulado**: `_receber_lote` faz pré-checagem do lote inteiro antes de gravar — um envio único de 350 MB com limite 200 MB é recusado de imediato.
- **Expiração — padrão 10 min**: job `cleanup_pdf` (`mod_intranet/rotinas.py`, 1 min, **sem usuário logado**) chama `expirar_antigos(minutos=cfg_expiracao_min())` — remove do disco por `mtime`, inativa registro, devolve cota (`MAX(0, …)`, nunca negativa) e audita como ator `sistema`; "Expirar agora" força a mesma limpeza. **Expirar é o que destrava a cota** — a cota é de *uso*, não de envio, então o texto de recusa orienta "aguarde expiração ou exclua".
- **Prefixo obrigatório**: `dataHora_usuario_operacao_nomeArquivo.pdf` — cada usuário vê apenas os próprios arquivos.
- **Auditoria SHA-256**: `upload_hash` no upload; `juntar`/`cortar` gravam os hashes das origens no texto e o do resultado em `hash_arquivo` (`_auditar_hash`); `reduzir` idem, com `erro_reducao` (hash do **original**) quando falha; `dividir` grava `modo/filtro/bib/arquivos/sha256_origem`; `zip` grava `arquivos=N sha256`; `deletar` (em `bd_manipulador`) com estorno de cota. **`op_verificar` não audita** — é leitura, e só notifica.
- **Motor PDF**: `mod_intranet/pdf_operacoes.py` re-exportado (`hash_sha256`, `op_reduzir`/`op_juntar`/`op_cortar`/`op_dividir`/`op_dividir_partes`/`op_verificar`); ZIP via `zip_por_ids()` (seleção) / `zip_do_usuario()` (todos); exclusão com estorno de cota; ganchos `remover_vinculos_usuario()`/`renomear_usuario()`; `contar_arquivos_ativos()` no Resumo.

## Operações e `data-testid`

| Ação | `data-testid` | Motor | Auditoria |
|:---|:---|:---|:---|
| Atualizar lista | `editar_pdf-atualizar` | — | — |
| Verificar integridade | `editar_pdf-verificar` | `op_verificar` | — (só avisa) |
| Juntar (≥ 2 PDFs) | `editar_pdf-juntar` | `op_juntar` | `juntar` |
| Excluir selecionados | `editar_pdf-excluir` | `deletar_arquivo` | `deletar` |
| Baixar ZIP | `editar_pdf-baixar-zip` | `zip_por_ids` | `zip` |
| Baixar PDFs individuais | `editar_pdf-baixar-pdfs` | — | — |
| Enviar agora (reenvio) | `editar_pdf-enviar` | — | `upload_hash` |
| Modo de redução | `editar_pdf-modo-reduzir` | — | — |
| Reduzir | `editar_pdf-reduzir` | `op_reduzir` | `reduzir` / `erro_reducao` |
| Cortar | `editar_pdf-cortar` | `op_cortar` | `cortar` |
| Dividir | `editar_pdf-dividir` | `op_dividir_partes` | `dividir` |
| *(legado)* | `editpdf-upload` (`span.hidden`) | — | — |

O **Juntar respeita a ordem de marcação** dos checkboxes (`ordem_ids` → `_alvos()`), não a
alfabética nem a de upload — a tela confirma com `Junção na ordem dos # : a → b → c`. Se o
retorno contiver `IGNORADOS`, o aviso sai em `warning`, nunca em "sucesso" escondido.


## Permissões

| Ação | `comum` | Admin módulo | `administrador_geral` |
|:---|:---:|:---:|:---:|
| Subir/editar/baixar próprios PDFs | ✓ | ✓ | ✓ |
| Aba Administração (cotas/tema) | ✗ | ✗ | ✓ |

## Rota e integrações

- Rota: `/edit-pdf` (chave `editar_pdf`) — `main.py:218`.
- Integra com o núcleo via `get_connection`/`get_config`/`set_config`/`audit_log`; scheduler central (`mod_intranet/rotinas.py`, job `cleanup_pdf` 1 min) chama `expirar_antigos()`.
- Configs: `cotadisco_global_gb`, `editar_pdf_lote_arquivos`, `editar_pdf_lote_mb`, `editar_pdf_usuario_gb`, `editar_pdf_expiracao_min` (+ textos `editar_pdf_texto_*`); tema usa prefixo distinto `editpdf_*`.
- Reutilizado pelo módulo Renomear Empenho: `op_cortar`/`op_juntar`/`op_reduzir` (RF-45).

## Testes

```bash
.venv/bin/python assets/test/test_editor_pdf.py      # 32 OK, 0 falha(s)
.venv/bin/python assets/test/verifica_ui_comum.py    # 190 OK, 0 falha(s) de 190
```

- `test_editor_pdf.py` — 32 verificações cobrindo banco próprio, cotas, auditoria com hash e
  `expirar_antigos` (o README antigo dizia "20": número defasado).
- `verifica_ui_comum.py`, seção **"16. edit_pdf migrado (fonte)"** (9 checks) — garante
  `EPDF.count("ui.notify(") == 0`, `botao(` ≥ 5, ausência dos helpers locais de tema e de
  `cfg_tema`, ausência de `CORES[…]` fixas, borda do cabeçalho = `tema["cor_botao"]`, hexes fora
  dos defaults de reset e ausência das exceções de botão cruas. **Lê só `telas.py`** — o painel
  `telas_administracao.py` não é verificado por esse check.

`data-testid` (QA/playwright): `editar_pdf-atualizar`, `editar_pdf-verificar`, `editar_pdf-juntar`, `editar_pdf-excluir`, `editar_pdf-baixar-zip`, `editar_pdf-baixar-pdfs`, `editar_pdf-enviar`, `editar_pdf-modo-reduzir`, `editar_pdf-reduzir`, `editar_pdf-cortar`, `editar_pdf-dividir` (+ `editpdf-upload` legada, `span.hidden`).

## Pontos de atenção

- `_cfg` depende de `get_config` importado no topo de `bd_manipulador.py` (bug real já corrigido: defaults eram usados).
- Redução Agressivo transforma texto em imagem (perde seleção/busca no PDF).
- **1 `ui.notify` cru remanescente** em `telas_administracao.py:56` (nível 2 de `_fmt_bytes`) — fora do alcance do check de QA. Correção de 1 linha: `notificar(..., type="negative")` + ampliar a guarda de `verifica_ui_comum.py` para o arquivo de Administração.
- `cfg_tema` em `bd_manipulador.py` ficou sem uso após a migração para `ler_tema` — código morto candidato a remoção.
- `bd_criador.py` é legado/morto com esquema divergente — **não executar**.

Ver [Análise do Módulo](../analise_mod_edit_pdf.md).