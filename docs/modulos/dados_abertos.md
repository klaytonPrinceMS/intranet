# Dados Abertos — `mod_dados_abertos`

> Módulo de dados abertos públicos da prefeitura. Tela principal em
> `/dados-abertos`: uma grade de CARDS, um por conjunto de dados público.
> Hoje existe **um** card — **Servidores Públicos** —, que lê o arquivo de
> origem da folha (Portal da Transparência) e mostra o **perfil da folha**:
> quantos servidores, em qual situação, em qual vínculo, em qual secretaria, em
> qual cargo, e os números da remuneração.
>
> **O card NÃO mostra a tabela linha a linha com a remuneração de cada
> servidor.** A folha é pública, mas o painel serve para ler a *forma* da força
> de trabalho; o detalhe nominal fica no link da fonte, que é onde a lei
> determina que o dado aberto mora. Ver
> [Por que não há tabela nominal](#por-que-não-há-tabela-nominal).

---

## O que o módulo é

| Item | Valor |
|:---|:---|
| Banco | `db_mod_dados_abertos.db` (WAL) — um DATABASE `db_mod_dados_abertos` no Postgres |
| Tela | `/dados-abertos` → `telas.mostrar_tela(nome, perfil)` |
| Administração | `/admin/dados_abertos` → `telas_administracao.mostrar_administracao(nome)` |
| Acesso | **NÃO** está em `ACESSO_PADRAO_NOVO_USUARIO` — só quem o administrador liberar |
| Leitura da folha | `mod_intranet/integracoes.folha_de_servidores_publica()` (10ª função da fachada) |

## Estrutura

```text
mod_dados_abertos/
  __init__.py              # exposição pública e a regra de acesso
  bd_manipulador.py        # ÚNICO acesso ao banco: tb_fontes, tb_consultas, resumo da folha
  telas.py                 # grade de cards + painel de agregados da folha
  telas_administracao.py   # /admin/dados_abertos: aparência + registro de fontes
```

### As duas tabelas

| Tabela | Para que serve |
|:---|:---|
| `tb_fontes` | O **REGISTRO** de conjuntos de dados: `chave`, `nome`, `descricao`, `icone`, `ordem`, `ativo`. É o que dirige a grade de cards. |
| `tb_consultas` | Quem abriu qual conjunto, e quando. Dado aberto é público, mas **quem pediu** é informação que a LGPD exige guardar — e é o que permite responder depois "quem viu a folha de remuneração e quando". |

A folha **não** é guardada aqui. Ela é pública, é de outro módulo (a coleta mora
em `mod_gest_cad_usuario/dados/`) e é lida pela fachada. Copiá-la para este
banco envelheceria sem nunca ser corrigido — quem atualiza é o portal.

## A tela principal

A tela **não conhece nenhum conjunto pelo nome**: pede o registro ao
`bd_manipulador` e desenha um card por fonte. Os próximos conjuntos entram por
`/admin/dados_abertos` (ou por `init_db`) sem que a tela mude.

Um card mostra nome, descrição e ícone; ao clicar abre o diálogo com a leitura
da fonte. Fonte registrada e sem leitor mostra *"leitura ainda não
implementada"* — honestidade em vez de uma tela vazia ou de zeros que parecem
dado.

## O card "Servidores Públicos"

Reproduz o painel da folha, **sem** a tabela nominal:

1. **Cabeçalho** — competência, origem, quando foi coletado, link da fonte e o
   aviso legal dela.
2. **Aviso** — por que não há tabela nominal, e onde achá-la.
3. **Indicadores** — Servidores · Ativos · Secretarias · Cargos distintos ·
   Remuneração mediana · Remuneração total.
4. **Distribuições** — Situação (verde) · Vínculo (roxo) · Secretaria (ciano) ·
   Cargos top 12 (laranja) · Lotação top 12 (petróleo).

As barras são `ui.element` com largura **em porcentagem** do trilho, e não
`ui.linear_progress` — que é uma régua arredondada e animada e ficaria
diferente da leitura da folha.

### Por que não há tabela nominal

A folha é pública por lei (12.527), e este módulo mostra o agregado dela. A
tabela com a remuneração de cada servidor, pessoa a pessoa, fica no **link da
fonte** — o portal que a publicou. Motivo: o painel existe para responder "quantas
pessoas, em qual posto, em qual situação", e é onde o olhar de quem lê está. A
lista ordenada por salário é um **ranking de pessoas**, que é outra coisa, e é a
fonte que a publica, não a intranet.

## A folha é relida em TODO boot

`mod_intranet/bd_criador.py` chama `carga_automatica()` em **todo** boot (não só
no primeiro). O que segura o custo é a trava do arquivo dentro de
`carga_automatica`: folha inalterada sai em menos de 1 s, sem tocar em linha
nenhuma; folha mudada roda a sincronização inteira — medido em 01/10/2026,
**~450 ms por servidor** (~5 min para ~650 servidores).

Antes (30/09/2026) isso rodava só quando o cadastro não tinha nenhum servidor
com vínculo. Resolvia o primeiro boot e abria um buraco depois dele: servidor
novo, mudança de vínculo, férias, licença-maternidade, demissão e salário novo
entravam no arquivo e **não chegavam ao banco**, sem nenhuma diferença visível
para o administrador.

O log do boot agora diz **o que mudou**:

```text
[carga_folha] folha sincronizada: 650 servidor(es) lido(s), competencia 08/2026
  — 3 criado(s), 12 bloqueado(s) (ferias/licenca/demissao), 2 desbloqueado(s),
  1 nome(s) corrigido(s), 0 com pendencia de setor/cargo, 640 sem mudanca.
```

## A fachada: `folha_de_servidores_publica()`

**10ª função** de `mod_intranet/integracoes.py`. Existe porque o arquivo mora em
`mod_gest_cad_usuario/dados/`, e este módulo não pode abrir a pasta de outro
módulo (AGENTS.md §2). Quem sabe o caminho e o formato é o módulo que o
coletou — por isso o `import` é de `mod_gest_cad_usuario.carga_folha`, lazy, e
não do `bd_manipulador`: a folha é um **arquivo**, não uma tabela do banco de
usuários.

| | |
|:---|:---|
| Devolve | o dicionário cru: `origem`, `url`, `competencia`, `coletado_em`, `total`, `aviso`, `servidores` |
| Não faz | não grava, não audita, não calcula média — o dado aberto mostra o que a fonte publica, não o que o sistema gravou depois |
| Em falha | `{"erro": "...", "servidores": []}` — a tela mostra "fonte indisponível", não um zero |

O leitor no módulo dono é `carga_folha.folha_arquivo_atual()`: lê o
`funcionarios.json` quando existe e, senão, o CSV configurado em
`fonte_folha.json`.

## Registro de fontes

Em `/admin/dados_abertos`:

- **Aparência** — as 6 chaves de tema, pelo bloco padrão do sistema.
- **Conjuntos de dados** — listar, registrar e ligar/desligar.

Desligar esconde o card e **não apaga** o registro: o conjunto volta, e apagar
perderia a descrição e a ordem que o administrador ajustou.

---

## O organograma: a lista telefônica é a dona

Este módulo não guarda nem decide secretaria/setor. Quem tem isso é a
**Lista Telefônica**, e qualquer módulo que precise de unidade tira a
hierarquia de lá, pela fachada (`integracoes.listar_unidades_organograma`).

A **origem** das unidades:

| Origem | Quem manda | Efeito |
|:---|:---|:---|
| `folha` | A folha de servidores | Se sumiu da folha, a unidade é **desativada** (nunca apagada) |
| `manual` | O administrador | A folha **não** desliga. Secretaria ou setor que o portal ainda não publica sobrevive à carga |

A marca passou a existir em 01/10/2026 porque "não está na folha" e "não deveria
existir" eram a mesma condição: um setor criado pelo administrador era desligado
na carga seguinte. É a mesma razão pela qual o desativamento nunca apaga — some da
tela é pior do que sobrar uma pasta vazia.