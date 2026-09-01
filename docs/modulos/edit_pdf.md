# PDF Editor Module — `mod_edit_pdf`

> PDF editor module: route `/edit-pdf` (key `editar_pdf`) · own database `db_mod_edit_pdf.db` · per-user temp space, quotas, SHA-256 audit, scheduled expiration.

---

# Módulo Editor de PDF — `mod_edit_pdf`

> Módulo de edição de PDF: rota `/edit-pdf` (chave `editar_pdf`) · banco próprio `db_mod_edit_pdf.db` · espaço temporário por usuário, cotas, auditoria SHA-256, expiração agendada.

## Propósito

Editor de PDFs multiusuário com espaço temporário por usuário em `editorPDF/`. O usuário envia PDFs em lote e aplica operações sobre uma seleção ordenada (reduzir, juntar, cortar, dividir, verificar, ZIP, excluir). Arquivos expiram automaticamente. Aba de Administração exclusiva do `administrador_geral` para cotas, limites e expiração — configurável sem restart.

## Banco de dados

Criador vigente: `init_db_pdf()` em `manipulador_bd.py:87-93`.

- **`tb_arquivos`**: `id`, `nome_arquivo`, `usuario`, `tamanho_bytes`, `operacao` (upload/saida/zip), `data_operacao`, `ativo`.
- **`tb_cota_disco`**: `usuario` PK, `total_usado_bytes`, `atualizado_em`.

⚠️ O `criador_bd.py` do módulo é **legado/morto** com esquema divergente — não executar (criaria tabelas erradas no banco central).

## Funcionalidades

- **Abas**: Editor (sempre) | Administração (só admin geral). Cabeçalho mostra uso da cota do usuário (global só p/ admin).
- **Upload múltiplo** com auto-upload, somente `.pdf`; recusados listados nominalmente com o motivo; "Enviar agora" para reenvio.
- **Arquivos no servidor**: seleção múltipla estável entre refreshes (timer 5 s), badges "#" com ordem de marcação (merge respeita), coluna "Expira em" com contagem regressiva colorida.
- **Operações**: Verificar integridade, Juntar, Excluir selecionados, ZIP, download individual; menu de contexto por linha.
- **Reduzir tamanho**: modo Leve (recompressão; biblioteca auto `pymupdf→pikepdf→pypdf`) ou Agressivo (rasteriza como JPEG, DPI 50–400, qualidade 10–100%).
- **Cortar** (pares/ímpares/lista "2-5,8") e **Dividir** (página-a-página, par/ímpar, cortes ou intervalos).
- **Administração**: cota global GB (default 10), máx. arquivos/lote, MB/lote, cota por usuário GB, minutos de expiração + "Expirar agora".
- **Aparência** (Administração): tema dos botões via `ui.color_input` — fundo, texto, cor da página, título, tamanho (`editpdf_*`). Este módulo é o **módulo exemplo** do padrão de exibição: área cheia (`w-full`) e cupê "Aparência" com as 6 chaves (`cor_botao`, `cor_texto_botao`, `cor_fundo`, `cor_titulo`, `btn_tamanho`, `texto_header`), replicado aos demais módulos.
- **Versionamento**: `versao_modulo:editar_pdf = 1.0.260827`.

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

- `_cfg` depende de `get_config` importado no topo de `manipulador_bd.py` (bug real já corrigido: defaults eram usados).
- Redução Agressivo transforma texto em imagem (perde seleção/busca no PDF).

Ver [Análise do Módulo](../analise_mod_edit_pdf.md).