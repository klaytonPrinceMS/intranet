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
- **Versionamento**: `versao_modulo:editar_pdf = 1.0.260908`.

## Regras de negócio

- **Cotas em 4 níveis** (global, por usuário, por lote, estoque) lidas de `tb_config` central a cada uso.
- **Limite de MB é por envio, não acumulado**: `_receber_lote` faz pré-checagem do lote inteiro antes de gravar.
- **Expiração**: job `cleanup_pdf` (1 min) remove do disco, inativa registro, devolve cota e audita como ator `sistema`.
- **Prefixo obrigatório**: `dataHora_usuario_operacao_nomeArquivo.pdf` — cada usuário vê apenas os próprios arquivos.
- **Auditoria SHA-256**: `upload_hash` no upload; hashes das origens/resposta nas operações.

## Permissões

| Ação | `comum` | Admin módulo | `administrador_geral` |
|:---|:---:|:---:|:---:|
| Subir/editar/baixar próprios PDFs | ✓ | ✓ | ✓ |
| Aba Administração (cotas/tema) | ✗ | ✗ | ✓ |

## Rota e integrações

- Rota: `/edit-pdf` (chave `editar_pdf`) — `main.py:218`.
- Integra com o núcleo via `get_connection`/`get_config`/`set_config`/`audit_log`; scheduler central chama `expirar_antigos()`.
- Reutilizado pelo módulo Renomear Empenho: `op_cortar`/`op_juntar`/`op_reduzir` (RF-45).

## Testes

```bash
.venv/bin/python test/test_editor_pdf.py
```

## Pontos de atenção

- `_cfg` depende de `get_config` importado no topo de `bd_manipulador.py` (bug real já corrigido: defaults eram usados).
- Redução Agressivo transforma texto em imagem (perde seleção/busca no PDF).

Ver [Análise do Módulo](../analise_mod_edit_pdf.md).