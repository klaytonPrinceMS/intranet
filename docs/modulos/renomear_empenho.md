# Módulo Renomear Empenho — `mod_renomear_empenho`

> Módulo de renomeação e gestão de empenhos: rota `/renomear-empenho` (chave `empenhos`) · banco próprio `db_mod_renomear_empenho.db` · extração de texto de PDF (inclui tipos especiais EC/EE/EG/AE), monitor multi-pasta (local/UNC), fila de renomeação, pesquisa FTS5, organizador físico, fluxo de solicitações comum→admin e configurações do módulo.

## Propósito

Extrai o nº do empenho/parcela (ou o tipo especial EC/EE/EG/AE) do texto dos PDFs por regex dinâmica, renomeia sequencialmente e move falhas para quarentena reprocessável. Inclui organizador físico em caixas/subpastas, edição e ferramentas de PDF, e o fluxo completo de solicitação de envio (comum solicita; admin aprova via e-mail ou ZIP).

A tela é organizada em **6 abas internas**: **Navegar**, **Fila Renomeação**, **Pesquisar**, **Organizador** (admin), **Solicitação** e **Configurações** (admin). O menu lateral global de módulos permanece intacto.

## Banco de dados

Criador vigente: `init_db_empenho()` em `manipulador_bd.py:289`.

| Tabela | Conteúdo |
|:---|:---|
| `tb_empenhos` | nome original/final, numero_empenho, parcela, **tipo_especial**, ficha, ano, usuario, data, status, caminho |
| `tb_indexador_pesquisa` | fallback comum (`empenho_id`, `conteudo_texto`) |
| `tb_indexador_pesquisa_fts5` | **VIRTUAL TABLE FTS5 com 32 colunas** do cabeçalho (RF-41) |
| `tb_quarentena` | nome_arquivo, motivo, caminho_atual, data_insercao, processado |
| `tb_regex_regras` | nome_regra UNIQUE, padrao_regra, substituicao, ativo, **campo_destino** (FTS customizado) |
| `tb_campos_busca` | regex de identificação por campo (ficha/empenho/parcela/ano...) editáveis sem tocar no código |
| `tb_arquivos_auditoria` | trilha por arquivo (detectado→renomeado→removido) com **hash SHA-256** de origem/destino |
| `tb_eventos_arquivos` | linha do tempo cronológica por arquivo (FK para `tb_arquivos_auditoria`) |
| `tb_solicitacoes` | fluxo comum→admin: pendente → enviado/email | zip_gerado → recusado; com `lote_id`, `metodo_envio`, `caminho_zip`, `motivo_recusa` |

⚠️ O `criador_bd.py` é **legado/morto** (esquema FTS5 fantasma no banco central) — não executar; o esquema real está em `manipulador_bd.py`.

## Funcionalidades

- **6 abas internas** (padrão `mod_solicita_impressao/telas.py`, com tabs manuais):
  - **Navegar**: navegação recursiva e protegida (anti-travessia) das pastas monitoradas + organizador, mostrando apenas PDFs; breadcrumb; baixar; revisar/renomear manual; solicitar envio. Botões "Processar pasta agora" e "Atualizar".
  - **Fila Renomeação**: lista recursiva de PDFs pendentes, "Processar" individual e "Processar todos".
  - **Pesquisar**: busca FTS5 (`MATCH`, fallback `LIKE`) + tabela de empenhos renomeados.
  - **Organizador** (admin): organizar caixas, gerar capas/matriz, validar matriz, inventário e ferramentas de PDF (cortar/mesclar/reduzir).
  - **Solicitação**: fluxo comum→admin (e-mail/ZIP/recusa) com agrupamento por lote e histórico; admin confirma/recusa.
  - **Configurações** (admin): pastas monitoradas (multi-pasta, UNC), aparência, template de nome, campos de busca, auditoria, quarentena e regras regex.
- **Monitor multi-pasta** (RF-40): varre a **raiz** de cada pasta monitorada (não recursivo), incluindo pastas **locais e de rede/UNC** (`\\servidor\empenhos`, `E:\scan`); pastas inacessíveis são puladas sem derrubar o monitor. Automático via job `monitor_empenho` do APScheduler (intervalo configurável, padrão 60 s) + botão manual.
- **Tipos especiais** (EC/EE/EG/AE): `detectar_tipo_especial`/`extrair_dados_tipo_especial` detectam pelo conteúdo (AE>EC>PARCELA>Tipo>Nota de Empenho) e nomeiam `EC_0024.pdf`, `EE_9570.pdf`, `EG_0089.pdf`; corrige a captura que antes pegava o nº do empenho complementado (66) em vez do nº do documento (24).
- **Pesquisa FTS5** (RF-41): 32 colunas do cabeçalho; regras regex com `campo_destino` alimentam colunas customizadas; trigger de exclusão mantém o índice sincronizado.
- **Gate de validação**: `renomear_manual`/`processar_pdf` só renomeiam quando o nº é identificado sem divergência crítica; caso contrário vão para a quarentena com motivo.
- **Não-reprocessamento**: `arquivo_ja_processado` (nomes DOC) + `_arquivo_registrado_no_bd` (autoritativo via `tb_empenhos`) impedem reprocessar itens já renomeados (inclusive tipos especiais, cujo nome não discrimina por contagem de dígitos).
- **Organizador completo** (RF-44): distribui em `organizadorPasta/caixa_NN/sub_X` (~200 páginas/pasta, 4 pastas/caixa — configuráveis); gera `capa.txt` por caixa e `matrizDeDocumentos.txt/.pdf`; `validar_presenca_matriz` confere presença.
- **Ferramentas de PDF embutidas** (RF-45): corte (pares/ímpares/intervalo), mesclagem e redução; saídas em `datahora_cortePDF/`, `datahora_mergePDF/`, `datahora_reducaoPDF/`.
- **Solicitações de envio** (RF-39): comum registra pedido (e-mail + mensagem); admin envia por e-mail (SMTP central `mod_intranet/email_util`) ou gera ZIP (`downloads/solic_*.zip`); agrupamento por lote; histórico completo.
- **Painel Administração**: aparência (`empenhos_*` — cor do botão/texto/fundo/título, tamanho, texto do cabeçalho), pastas monitoradas, intervalo do monitor, autorização de download/ZIP/e-mail para comuns, template de nome final, campos de busca e regras regex.
- **Versionamento**: `versao_modulo:empenhos = 1.0.<data>` (seed em `conexao_bd.init_db()`), exibido no rodapé.

## Regras de negócio

- Contador sequencial persistido em banco, único entre pastas; template de nome configurável (`doc_{contador:04d}_numEmpenho_{empenho}_p{parcela:03d}.pdf`).
- Tipos especiais usam nome próprio (`EC_%04d.pdf`), não o sequencial DOC.
- **Gate de validação**: renomeação somente com nº identificado; falha → quarentena com motivo (PLANO 4c atendido).
- Não-reprocessamento: DOC por padrão de nome; tipos especiais e demais por registro no banco (`tb_empenhos`/`tb_arquivos_auditoria`).
- Anti-travessia: navegação/renomeação restritas às raízes protegidas (`pastas_monitoradas` + `organizadorPasta`).
- Auditoria: `audit_log` (central) **com hash SHA-256** em toda operação + trilha por arquivo em `tb_arquivos_auditoria`/`tb_eventos_arquivos`.
- Monitor automático varre só a raiz; navegação/fila manual variam recursivamente.

## Permissões

| Ação | `comum` | Admin módulo | `administrador_geral` |
|:---|:---:|:---:|:---:|
| Navegar / pesquisar / baixar (se autorizado) / solicitar envio | ✓ | ✓ | ✓ |
| Fila: processar / processar todos | ✓ | ✓ | ✓ |
| Organizador / ferramentas de PDF | ✗ | ✓ | ✓ |
| Solicitação: confirmar envio / gerar ZIP / recusar | ✗ | ✓ | ✓ |
| Configurações / pastas / template / campos / regras / quarentena | ✗ | ✓ | ✓ |

> Detalhe: usuário `comum` só baixa/envia quando `renomear_autorizar_download = 1` (configuração do admin); mesmo autorizado, a aba **Organizador** e as **Configurações** permanecem restritas ao admin.

## Rota e integrações

- Rota: `/renomear-empenho` (chave `empenhos`) — `main.py`.
- Contrato obrigatório `mostrar_tela(usuario_logado, perfil)` em `telas.py` (validado pelo `main.py`).
- Job `monitor_empenho` no APScheduler (`mod_intranet/rotinas.py`) — `rodar_monitor` varre a raiz de todas as pastas.
- Integrações: `mod_intranet.email_util.enviar_email` (SMTP central) para envio de solicitações; `mod_intranet.autenticacao.eh_admin_do_modulo`; `mod_intranet.aba_modulo.cabecalho`; `mod_intranet.tema_modulo.campo_modulo`.
- Chaves de configuração em `tb_config` (preferencialmente com prefixo `empenhos_` — ver [Configurações](../configuracoes.md)).
- Pastas: `doc/` (padrão), `quarentena/`, `organizadorPasta/`, `downloads/`, `datahora_*PDF/`, `tmp_ferramentas_pdf/` (criadas sob demanda).

## Testes

- `test/teste_fluxo_renameador.py` cobre: processamento DOC e tipos especiais EC/EE/EG, gate de validação, não-reprocessamento, classificação, fluxo de solicitações e navegação. Determinístico (roda 2x); isola `pastas_monitoradas` via monkeypatch para não vazar configuração central.

## Pontos de atenção

- `criador_bd.py` **morto** — não confiar; o esquema real está em `manipulador_bd.py`.
- Monitor automático é **não recursivo** (apenas a raiz das pastas monitoradas); a navegação/fila manuais são recursivas.
- O intervalo do monitor (padrão **60 s**) e a lista de pastas são lidos de `tb_config` e aplicados **sem reiniciar**.

Ver [Análise do Módulo](../analise_mod_renomear_empenho.md) e [Manual de Uso](../manual_de_uso_renomear_empenho/index.md) para RFs/RNFs e operação.
