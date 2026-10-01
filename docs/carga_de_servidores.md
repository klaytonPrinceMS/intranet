> **EN — Loading the staff sheet is a CSV contract, not a network feature (28/09/2026).** The system is published for any city hall or company to clone, so **no institution, host, endpoint or screen-scrape** can live in the code. The whole feature is driven by one configuration file, `mod_gest_cad_usuario/fonte_folha.json`, which ships with **`"ativo": false`**: whoever installs the system and configures nothing gets a **working system, an empty staff register, and no connection attempt to anywhere**. That is the product decision this page defends. The **CSV is the contract**: the column of the identity field can be called `matricula`, `id`, `registro`, `codigo` or `id_registro` (aliases, so an ERP export works without renaming a column), the **delimiter is detected** (`;` from pt-BR Excel, `,` from en-US, tab) and the **reference period is declared**, so a remuneration figure can say which month it belongs to. The daily load is a **scheduler routine** (`carga_folha` in `mod_intranet/rotinas.py`, 03:00) with **three interlocks**: the source is off, the sheet is empty, or the file is byte-identical to the last load. The load **never overwrites an existing record**: a server who changed department gets a **pending confirmation** answered on first sign-in, while objective data (remuneration, payslip reference, name, link and status) is written straight through. The real data lives in `mod_gest_cad_usuario/dados/`, which is **gitignored** — a name, a staff number, a post and a salary are public **by law** when published in the official channel, and public in the git history means replicated to everyone who clones and never erased. Set `tb_usuarios.vinculo` and `situacao` objectively from the sheet (28/09/2026) — same rule as the remuneration: nobody is asked anything the source already answers.

# Carga de Servidores

> !!! warning "ESTA INSTALAÇÃO ESTÁ LIGADA — e é temporário (30–31/09/2026)"
>     O padrão do produto **continua sendo desligado** (`CONFIG_PADRAO`,
>     `carga_folha.py:409`), e as seções abaixo descrevem esse padrão. Mas
>     **esta instalação foi posta em `"ativo": true` com `"origem": "portal"`**
>     por decisão do responsável, para que o cadastro de servidores **nascesse
>     junto com o banco** em vez de ficar vazio até o agendador das 03:00.
>
>     Três consequências que este documento precisa registrar, porque é o
>     contrário do que a §1 e a §2 mandam:
>
>     1. **A carga virou passo de boot**, não só agendador
>        (`mod_intranet/bd_criador.py:2.1`), logo depois do `init_users()` — a
>        folha escreve em `tb_usuarios`, que só existe depois dele.
>     2. **A primeira carga é lenta: ~25–35 minutos** para ~1.165 servidores.
>        Não é a coleta do portal (essa leva ~100 s): é a gravação, a ~1,4 s por
>        servidor, e **~60% disso é `audit_log`** (0,28 s por chamada, três por
>        servidor), porque `registrar_auditoria` abre uma conexão nova do banco
>        de auditoria a cada escrita. Correção pendente.
>     3. **A §2 (checklist antes de publicar um clone) vale para o produto, não
>        para este arquivo**: aqui `portal_url` está preenchido **de propósito**.
>
>     A remoção está combinada: voltar a `"ativo": false` e `"origem": "csv"`
>     devolve o comportamento de sistema publicado. O `_leia_me` dentro do
>     próprio `fonte_folha.json` avisa quem abrir o arquivo.

> Documenta a **carga da folha de servidores**: o
> **CSV como contrato**, a configuração em `fonte_folha.json`, as **três travas**
> da rotina agendada, a regra de **nunca sobrescrever** cadastro existente e o
> porquê de `mod_gest_cad_usuario/dados/` estar fora do git.
>
> !!! danger "Esta página descreve o FORMATO, não a origem"
>     O sistema é publicado em git para qualquer prefeitura, empresa ou
>     órgão usar. Por isso **nenhum município, empresa, URL, endpoint ou nome de
>     órgão pode aparecer nesta documentação nem no código** — o que a
>     instituição é entra no **arquivo de configuração** da instalação, nunca
>     no repositório. A página ensina a montar o arquivo, o formato da coluna e
>     o que o sistema faz com ele. Quem quiser saber de onde veio a folha
>     consulta a sua própria fonte, que é uma decisão da sua instituição, não
>     um detalhe do produto.

---

## 1. A decisão em uma frase

> **O sistema nasce desligado da folha.** Quem instala e não configura nada
> recebe um sistema **funcionando**, com o **cadastro de usuários vazio**, e
> **nada tentando se conectar a lugar nenhum**.

Não é falta de implementação, é o padrão. Um sistema que publicasse em `main`
uma carga pronta apontando para um endereço que não é seu tentaria sair para a
internet na primeira madrugada de quem clonou o repositório, em nome de uma
instituição que talvez nem exista mais. O default que evita isso é
`"ativo": false` em `mod_gest_cad_usuario/fonte_folha.json`, lido por
`carga_folha.carregar_config()`.

O resultado prático: **a carga liga quando o responsável liga**. Um município
novo não precisa reiniciar o servidor para passar a ter folha — o job já está
agendado e sai em segundos quando a fonte é desligada.

## 2. Onde a configuração mora

| Item | Valor |
|:---|:---|
| Arquivo | `mod_gest_cad_usuario/fonte_folha.json` |
| Padrão no código | `carga_folha.CONFIG_PADRAO` (usado quando o arquivo não existe) |
| Pasta dos dados | `mod_gest_cad_usuario/dados/` — **fora do git** (ver §7) |
| Agendador | `_job_carga_folha` em `mod_intranet/rotinas.py`, `id="carga_folha"` |
| Horário | `carga_folha_hora` (padrão **3**, clamp 0–23) e `carga_folha_minuto` (padrão **0**) |

O arquivo de configuração é **documentado dentro de si mesmo**: a chave
`_leia_me` traz as cinco instruções (o que `ativo` faz, o que `origem` faz, por
que `delimitador` é `auto`, como `colunas` funciona, o que `competencia`
carimba). Quem abre o arquivo no editor já entende o que preencher, sem ler
esta página.

!!! warning "O arquivo que vai para o git tem de ser o seu, com o seu default"
    O arquivo de configuração é **versionado** (é contrato, é documentação) e
    **o conteúdo é da instalação**. Antes de publicar um clone, confira se
    `fonte_folha.json` está com `"ativo": false`, `portal_url` **vazio** e
    `portal_endpoints` com as duas chaves em `""` — o padrão de
    `CONFIG_PADRAO`. Nada de endereço, nome de município, nome de órgão ou
    nome de plataforma de terceiro em um repositório público.

## 3. O CSV é o contrato

O `caminho_csv` aponta para o arquivo exportado pela sua fonte. O sistema lê o
**cabeçalho** e casa cada campo pelo que ele **precisa**, não pelo nome que o
arquivo usa.

### 3.1 Apelido de coluna

`colunas` mapeia **o que a tela precisa** para **os nomes que o seu arquivo
usa**. A lista é uma alternativa: qualquer um dos nomes serve.

```json
"colunas": {
  "matricula": ["matricula", "id", "registro", "codigo", "id_registro"],
  "nome":      ["nome", "nome_completo", "nome_funcionario"],
  "unidade":   ["unidade", "secretaria", "orgao"],
  "lotacao":   ["lotacao", "setor", "departamento"],
  "cargo":     ["cargo", "funcao", "posto"]
}
```

O motivo é concreto: **um ERP que exporta `id_registro` funciona sem ninguém
renomear coluna**. Quem mantém o sistema não obriga a instituição a mudar a
exportação, e a instituição não precisa consultar o sistema para descobrir
quais nomes o sistema aceita.

Os campos reconhecidos e o que cada um vira:

| Campo | Vira | Onde entra |
|:---|:---|:---|
| `matricula` | **o login** (`tb_usuarios.user_nome`) | obrigatório |
| `nome` | nome social (`user_nome_completo`) | obrigatório |
| `unidade` | secretaria do organograma | organograma + cadastro |
| `lotacao` | setor/subsetor | organograma + cadastro |
| `cargo` | posto | cadastro + cartão da lista telefônica |
| `vinculo` | efetivo / contrato / estágio | **cadastro, objetivo** (28/09/2026) |
| `situacao` | ativo / férias / demitido | **cadastro, objetivo** (28/09/2026) |
| `remuneracao` | histórico de remuneração, com competência | carimbado, objetivo |
| `ficha_contracheque` | identificador do documento | carimbado, objetivo |
| `regime`, `carga_horaria`, `admissao`, `exoneracao` | lidos e ignorados na gravação | — |

!!! note "A matrícula É o nome de usuário"
    A instituição já tem um identificador único e público para cada servidor,
    e ele é o login. Não há senha inventada a memorizar, não há colisão de nome
    entre homônimos (que no interior do Brasil não é comum, mas não é raro) e
    a pessoa reconhece o próprio número na tela de login. Por isso
    `user_nome` **é** a matrícula e não existe coluna `matricula` separada.

### 3.2 Delimitador detectado sozinho

`"delimitador": "auto"` detecta ponto-e-virgula, vírgula ou tabulação na
amostra inicial (`_detectar_delimitador`, `carga_folha.py:460`).

O padrão é `auto` e não um valor fixo porque **os dois existem e nenhum dos
dois é o certo**: o Excel em português grava `;`, o Excel em inglês grava `,`.
Fixar um dos dois quebra o outro, e o erro aparece como "lêu uma coluna só com
o nome inteiro do cabeçalho" — que é sintoma, não diagnóstico. Fixe
(`;`, `,` ou `\t`) **só se a detecção errar**, e registre isso como
particularidade da sua fonte.

### 3.3 Competência declarada

`"competencia"` carimba a remuneração: `"07/2026"` faz o valor de julho entrar
no histórico de julho. Sem competência, o valor é guardado **sem histórico** —
que é o mesmo defeito de contabilidade que perder a nota fiscal antiga: o
número existe, a origem dele não.

Se a folha trouxer competência por servidor, ela vale; a configuração é a
**reserva** para quando vier vazia (`COMPETENCIA_FOLHA`).

## 4. A rotina agendada e suas três travas

A carga automática é `carga_folha.carga_automatica()`, chamada por
`_job_carga_folha` às **03:00** por padrão. Ela **nunca levanta exceção** —
quem chama é um job de fundo, e job de fundo que levanta exceção some do log
do agendador sem ninguém ver — e devolve um relatório com o motivo de ter saído
cedo, se saiu.

As três travas, na ordem em que são conferidas:

| # | Trava | Mensagem que fica no log |
|---|:---|:---|
| 1 | **fonte desligada** — `ativo: false` | `fonte desativada (fonte_folha.json: ativo=false)` |
| 2 | **folha vazia ou indisponível** | `folha vazia ou indisponivel — nada foi gravado (o cadastro existente esta intacto)` |
| 3 | **arquivo inalterado** desde a última carga | `folha inalterada desde a carga de <data> — nada a fazer` |

### Por que a trava 2 é a mais importante das três

**Caminho errado é o erro mais comum**, e o sintoma sem a trava seria
catastrófico: a carga "concluiria com sucesso" e zeraria o cadastro inteiro.
Com a trava, o resultado é o oposto do desastre — **nada é gravado e o
cadastro existente fica intacto**, com o motivo escrito no log.

A trava 3 usa a **impressão digital do arquivo** (`_digitalizar`, SHA-256 dos
primeiros 16 caracteres, `carga_folha.py:614`) e não a data de modificação: a
data muda quando alguém abre e salva o arquivo sem mudar nada, e a carga
rodaria à toa. O estado da última carga fica em
`mod_gest_cad_usuario/dados/estado_carga.json` (`_registrar_carga`), **na pasta
ignorada pelo git** — é estado, não contrato.

!!! note "`MINIMO_SERVIDORES` é a rede de segurança, não a trava"
    `MINIMO_SERVIDORES = 1` (`carga_folha.py:588`) só descarta folha com menos
    de um servidor, o que cobre a folha-header sem ninguém. **A defesa de
    verdade é a trava 2**, que é a que roda antes dela e não depende de
    número mágico: folha sem servidor nenhum nunca chega à gravação.

## 5. A carga nunca sobrescreve cadastro existente

Este é o ponto onde a carga deixou de ser "sincronizar" e passou a ser
"sugerir". `carga_folha.sincronizar()` (`carga_folha.py:242`) separa o que é
**objetivo** do que é **decreto de uma pessoa**.

### 5.1 Vai direto, sem perguntar (objetivo)

| Dado | Por que não é pergunta |
|:---|:---|
| **nome** | "qual é o seu nome, o do cadastro ou o da folha?" — ninguém tem ânimo de responder isso |
| **vínculo** e **situação** | "é efetivo?", "está ativo?" saem da folha, e a folha é a fonte |
| **remuneração** e **ficha de contracheque** | valor oficial, publicado todo mês, com competência; não há o que a pessoa confirme |
| **bloqueio/desbloqueio** | quem está fora do serviço não entra; quem voltou entra (o caminho de volta é simétrico) |

**Vínculo e situação** entraram nesse grupo em 28/09/2026 (`definir_vinculo`).
Sem eles, a lista telefônica não conseguia responder "é efetivo?" e "está
ativo?" de quem não autorizou telefone — e a pessoa **sumia da busca**, que é
o contrário do que a lista precisa fazer. A regra é a mesma da remuneração:
**grava objetivo, não vira pergunta ao servidor**.

### 5.2 Vira pendência, confirmada no primeiro acesso

**Unidade, lotação e cargo** mudados na folha viram **pendência** para a
pessoa confirmar no primeiro acesso (`marcar_pendencia_dados`, que o cadastro
mostra como `telefone_pendente`-irmão no diálogo de primeiro acesso).

Por que perguntar e não escrever:

- **A transferência de setor é informação do RH.** Se o sistema troca sozinho,
  um erro de digitação na origem muda o cadastro de uma pessoa real sem
  ninguém ter visto.
- **Sobrescrever apagaria o ajuste que o administrador fez à mão** no painel do
  organograma.
- **Quem responde é quem sabe.** A folha é a fonte do setor, mas o telefone
  (e o que a pessoa acha do próprio cargo) é dela.

O resumo da carga devolve `marcados` (quantos ficaram com pendência) e
`inalterados` (quantos não divergiam em nada) — dá para ver, na primeira
carga, quantas pessoas foram de fato Foundas em posto diferente.

### 5.3 Quem nasce bloqueado, e quem volta

`VINCULOS_BLOQUEADOS = {"pensionista", "inativo", "eleito", "exonerado"}` e
`SITUACOES_BLOQUEADAS = {"demitido", "exonerado", "afastado"}` entram no
cadastro — o **registro é obrigatório** e o histórico importa — mas
**bloqueados**: não conseguem entrar. Bloquear é reversível pelo administrador;
apagar não seria.

O caminho de volta é explícito: quem é pensionista hoje e efetivo na próxima
folha é **desbloqueado** na carga seguinte (`desbloqueados` no relatório).
Bloquear sem saber desbloquear é meio caminho — a pessoa apareceria ativa na
fonte e bloqueada aqui, sem ninguém saber por quê.

!!! warning "`get_connection()` devolve a conexão; quem lê é o cursor"
    Bug de 28/09/2026, registrado porque é o tipo que se repete: o
    `try/except` por linha transformava `AttributeError: 'Connection' object
    has no attribute 'fetchone'` em **"1165 erros"** sem parar a carga, e o
    ensaio (`--so-ensaio`) retornava **antes** deste trecho — então só a
    aplicação real descobria o defeito. Escrever `conn.cursor().execute(...)`
    e ler no cursor, sempre.

## 6. Como rodar na mão

```bash
# ensaia: mostra o que faria e NÃO grava
.venv/bin/python mod_gest_cad_usuario/carga_folha.py

# grava
.venv/bin/python mod_gest_cad_usuario/carga_folha.py --aplicar

# grava com competência explícita
.venv/bin/python mod_gest_cad_usuario/carga_folha.py --aplicar --competencia 07/2026

# configuração alternativa, sem tocar na do sistema
.venv/bin/python mod_gest_cad_usuario/carga_folha.py --aplicar --config /caminho/outro.json
```

Sem `--aplicar` nada é escrito, e **sem terminal nada é gravado** mesmo com
`--aplicar` (`_tem_terminal()`): a carga por linha de comando é para pessoa,
não para o agendador. O agendador não passa `--aplicar` — ele chama
`carga_automatica()`, que aplica direto por ser o caminho já testado.

O argumento `--config` existe para os testes e para o técnico conferir uma
configuração alternativa sem mexer na do sistema.

## 7. Os dados não vão para o git, e por quê

`mod_gest_cad_usuario/dados/` está no `.gitignore`:

```gitignore
# Dados de servidores — NUNCA versionar (28/09/2026)
mod_gest_cad_usuario/dados/
```

Nele moram a folha real (`funcionarios.csv`, `funcionarios.json`) e o estado
da última carga. **As ferramentas `.py` vão para o git; os dados não.**

A justificativa é a mesma do AGENTS.md §1 e §8.3, e ela merece ser dita sem
esconder o PROVIDEDOR:

> Nome, matrícula, cargo e remuneração de servidor público são **informação
> pública por lei**. Mas **"pública" quer dizer publicada no canal oficial da
> instituição** — não publicada no histórico do git, que é **replicado para
> todo mundo que clona** e **nunca apaga**.

A diferença entre as duas coisas é a diferença entre um portal que a
instituição escolheu publicar e um repositório que o mundo inteiro recebe por
padrão, sem ter sido consultado e para sempre. Por isso:

| Vai para o git | Não vai para o git |
|:---|:---|
| `carga_folha.py`, `coleta_folha.py` (o **contrato**) | `dados/funcionarios.csv` (a folha real) |
| `fonte_folha.json` com o **padrão desligado** | `dados/funcionarios.json` |
| `dados/` no `.gitignore` com o motivo escrito | `dados/estado_carga.json` |
| Este texto, que ensina o formato | `db_mod_*.db` (o cadastro, já ignorado) |

!!! danger "A regra do AGENTS.md §8.3 vale para a documentação também"
    Exemplo de matrícula em `.md` é **sempre letra e número** (`MT-1234`),
    nunca seis dígitos: um número de seis dígitos parece real e é lido como
    real, e o histórico do git é imutável. Verificação antes de commitar em
    `docs/padroes_codificacao/index.md` § Matrícula de exemplo.

## 8. O que este documento NÃO diz, e por quê

| Não documentado | Por quê |
|:---|:---|
| Endereço, rota ou formato de resposta de qualquer origem de rede | o repositório é público; o que a instituição é, é configuração dela |
| Nome de município, empresa ou órgão | idem — e `CONFIG_PADRAO` e `fonte_folha.json`-ALVO não podem carregar isso |
| Como a coleta de rede funciona por dentro | o contrato é o CSV; a implementação de rede é interna e **não é o produto** |
| Nomes reais de servidores, matrículas e valores | §7 e AGENTS.md §8.3 |
| Senhas de desenvolvimento | AGENTS.md §8.2.1 — **no código sim, na documentação nunca** |

O que fica é o que serve a qualquer prefeitura ou empresa que clone o
repositório: **o formato do arquivo, o nome das chaves, o que cada campo vira e
por que o sistema não sobrescreve o que alguém já corrigiu à mão.**

---

## Referência rápida

| Pergunta | Onde |
|:---|:---|
| Quais nomes de coluna aceito? | §3.1 e a chave `colunas` em `fonte_folha.json` |
| O que acontece se o arquivo não existir? | §4, trava 2: nada é gravado, o cadastro fica intacto |
| Por que a carga não muda meu cargo? | §5.2: vira pendência, a pessoa confirma no primeiro acesso |
| Quais servidores entram bloqueados? | §5.3: `pensionista`, `inativo`, `eleito`, `exonerado`, `demitido`, `exonerado`, `afastado` |
| A carga roda sozinha? | §4: `_job_carga_folha`, 03:00, `id="carga_folha"` |
| Onde fica o dado real? | §7: `mod_gest_cad_usuario/dados/`, fora do git |
| Como o organograma é criado? | [Módulo Lista Telefônica](modulos/lista_telefonica.md) e `carga_folha.sincronizar_unidades` |
| E as cotas de impressão? | [Módulo Solicitação de Impressão](modulos/solicitacao_impressao.md) — vêm do organograma real |
