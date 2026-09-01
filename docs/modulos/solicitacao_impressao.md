# Print Request Module — `mod_solicita_impressao`

> Print request module: route `/solicita-impressao` (key `solicita_impressao`) · own database `db_mod_solicita_impressao.db` · PDF upload, page counting, hierarchical monthly quotas, dual-mode print, central audit.

---

# Módulo Solicitação de Impressão — `mod_solicita_impressao`

> Módulo de solicitação de impressão: rota `/solicita-impressao` (chave `solicita_impressao`) · banco próprio `db_mod_solicita_impressao.db` · envio de PDF, contagem de páginas, cotas mensais hierárquicas, impressão dual, auditoria central.

## Propósito

Módulo para solicitação de impressão de PDFs. Usuários **comuns** anexam um PDF por solicitação (upload automático), informam cópias, papel (A4/A3), cor (PB/Color), frente/verso, sulfite, observações e a secretaria/setor de crédito. O sistema conta as páginas, renomeia o arquivo no padrão definido, aplica regras de cota mensal hierárquica e fluxo de autorização quando exigido. Apenas administradores do módulo imprimem; responsáveis cadastrados autorizam.

**Versionamento**: `versao_modulo:solicita_impressao = 1.0.260829`.

## Banco de dados

Criador vigente: `init_db()` em `manipulador_bd.py:92` (bootstrap central). Arquivos PDF em `mod_solicita_impressao/solicitacaoImpressao/` (pasta própria).

| Tabela | Conteúdo |
|:---|:---|
| `tb_solicitacoes` | fluxo completo (solicitante, arquivos, cópias, papel, cor, frente/verso, secretaria/setor FK, páginas, status, autorização, impressão) |
| `tb_secretarias` | nome, sigla, cota mensal |
| `tb_setores` | nome, secretaria FK, cota mensal |
| `tb_responsaveis_autorizacao` | user_nome, secretaria/setor, ativo |
| `tb_cotas_impressao` | secretaria/setor, cota, `mes_referencia` (YYYY-MM único) |
| `tb_consumo_cota` | páginas usadas por mês |
| `tb_configuracoes_modulo` | chave/valor (pasta, MB, impressoras, marca d'água, prazos) |

## Funcionalidades

- **Upload automático ao selecionar o PDF** + renomeação (nome original descartado); rascunho `YYYYMMDD_HHMMSS_usuario_rascunho.pdf` com expiração (`tempo_expira_rascunho_min`, default 4 min) e botão "Remover arquivo".
- **Envio múltiplo** (até 10 PDFs): lista com checkbox, "Remover selecionados", cada arquivo vira uma solicitação; uuid evita colisão de rascunho no mesmo segundo.
- **Contabilização**: `paginas = qtd × copias × fator_papel × fator_frente_verso` (A4=1/A3=2; frente=1/verso=2).
- **Cotas hierárquicas mensais**: secretaria e setor (setor sem cota usa o pool da secretaria); excedente **permitido** e marcado; consumo descontado só na impressão; visual verde <80% / amarelo 80–99% / vermelho ≥100%; reset no dia 1º.
- **Autorização por responsável cadastrado** (pode ser usuário `comum` — a checagem usa `tb_responsaveis_autorizacao`, independente do perfil); sem responsável → autorizado direto.
- **Impressão dual**: "Imprimir direto" (`window.printSolicitacao(id)` via `impressao.js`) ou "Baixar para impressão" (Ctrl+P); decota cota ao imprimir e agenda exclusão em `tempo_exclui_impresso_min` (default 10 min); recusar/recuar/cancelar removem o arquivo na hora.
- **Marca d'água** opcional e personalizável (texto `{data}`, `{usuario}`, `{id}`, `{secretaria}`, `{setor}`, `{solicitante}`; posição, opacidade, fonte, cor, rotação).
- **Padrões pré-selecionados e editáveis** (A4, PB, somente frente, sulfite) na Administração.
- **Aparência** (cupê padronizado — módulo exemplo: Editor de PDF): `solicita_impressao_cor_botao`, `solicita_impressao_cor_texto_botao`, `solicita_impressao_cor_fundo`, `solicita_impressao_cor_titulo`, `solicita_impressao_btn_tamanho`, `solicita_impressao_texto_header` em `tb_config` central, na sub-aba Configurações da Administração; tela em área cheia (`w-full`).
- **Auditoria central** (`solicita_impressao`): quem solicitou/autorizou/imprimiu/recusou (quantidades, motivo, hash).
- **Job `cleanup_solicita`** (1 min) remove rascunhos não confirmados e impressos vencidos.

## Nomenclatura do arquivo

```
YYYYMMDD_HHMMSS_usuario_copias_paginas_secretaria_setor.pdf
```

Ex.: `20260829_143022_joao_silva_3_10_SECRETARIA_SAUDE_ATENDIMENTO.pdf` (acentos removidos, espaços→`_`).

## Permissões

| Perfil | Capacidade |
|:---|:---|
| `comum` | criar solicitações, acompanhar as próprias ("Minhas Solicitações"), cancelar pendentes |
| `comum` vinculado como responsável | ver aba **Autorização** da sua secretaria/setor (autorizar/recusar com motivo) |
| `administrador` do módulo | imprimir, recuar, gerenciar cadastros (secretarias, setores, responsáveis, cotas), configurar |
| `administrador_geral` | tudo + auditoria |

## Rota e integrações

- Rota: `/solicita-impressao` (`main.py:285`) + downloads `/solicita-impressao/pdf/{id}` (`main.py:238`) e JS `/solicita-impressao/src/impressao.js` (`main.py:297`).
- Módulo nativo em `tb_modulos` (chave `solicita_impressao`, ícone `print`).
- Auditoria via `audit_log(usuario, 'solicita_impressao', ...)`.

## Testes

```bash
.venv/bin/python test/test_solicita_impressao.py
```

## Pontos de atenção

- Lista real de impressoras depende de API experimental do navegador (`navigator.getPrinters`); fallback é o diálogo nativo do SO.
- Contagem de páginas usa PyMuPDF; PDFs corrompidos/imagem podem retornar 0 (bloqueia envio).
- Cotas são mensais; reset manual ou automático (dia 1); sem e-mail (SMTP não usado aqui).

Ver [Análise do Módulo](../analise_mod_solicita_impressao.md).