# Integration Facade — `mod_intranet/integracoes.py`

> Public seam that lets a business module reach another module WITHOUT importing it: lazy imports, fail-soft, core-owned coupling. Validated by `assets/test/check_integridade.py` (5 failures/17 → 13/13 on 25/09/2026).

---

# Fachada de Integração — `mod_intranet/integracoes.py`

> Costura pública que permite a um módulo de negócio alcançar outro **sem importá-lo**: imports lazy, fail-soft e acoplamento pertencente ao núcleo. Validada por `assets/test/check_integridade.py` (5 falhas/17 → 13/13 em 25/09/2026).

## O problema que a fachada resolve

O `AGENTS.md` §2 (raiz do repositório, fonte única de verdade para agentes) impõe
duas regras que, lidas ao pé da letra, parecem incompatíveis:

1. **Cada módulo tem o seu banco** e **nunca faz cross-query** entre bancos.
2. Mas a intranet tem telas que precisam de dados de **outros** módulos: a TV de
   Filas mostra notícias do Agregador; o admin do Blog purga notícias censuradas
   do Agregador; a Lista Telefônica busca o cadastro de usuários; a Solicitação
   de Impressão semeia cotas a partir do organograma da Lista Telefônica.

Sem uma costura, esses cenários violavam a regra: o módulo de negócio importava
o outro módulo direto (`from mod_agregador_noticias.bd_manipulador import ...`),
criando **dependência de topo entre módulos de negócio** e uma aresta que
`check_integridade.py` acusava como falha estrutural.

## A regra adotada (25/09/2026)

> **Módulo de negócio fala com o núcleo. O núcleo possui o acoplamento.**

- O **módulo de negócio** nunca importa outro módulo de negócio. Quando precisa
  de dado alheio, chama a **API pública do núcleo**.
- O **núcleo** (`mod_intranet/integracoes.py`) é o único dono do conhecimento de
  *qual* módulo serve *o quê* — e faz o `import` sob demanda.
- O **banco continua isolado**: a função do núcleo abre a conexão do módulo de
  destino pelo `bd_manipulador` **dele**. Não existe SQL cruzando bancos, nem
  `sqlite3.connect` em banco alheio. O que se atravessa é uma **fronteira de
  código**, não de dados.

```text
mod_filas  ──►  mod_intranet.integracoes  ──►  mod_agregador_noticias.bd_manipulador
   (fila)          (fachada, sem SQL)              (dono do seu banco)
```

## As duas regras de implementação

### 1. Imports **lazy** (dentro da função)

Nenhum `import` de módulo de negócio no topo de `integracoes.py`. O import
acontece **dentro** do corpo de cada função:

```python
def listar_noticias_para_tv(limite: int = 200) -> list:
    try:
        from mod_agregador_noticias.bd_manipulador import listar_para_tv
        return list(listar_para_tv(limite=limite) or [])
    except Exception as exc:
        logger.warning(...)
        return []
```

**Por quê:** um `import` de topo de um módulo de negócio aqui **fecharia um
ciclo de import de topo** com `main.py` (que importa todos os módulos para
registrar as rotas). Com o import dentro da função, a dependência só se resolve
quando alguém realmente chama a fachada — em runtime, já com o grafo de
imports pronto. `check_integridade.py` distingue os dois casos: ciclo
**top-level** é **falha**; ciclo **apenas-lazy** é **AVISO** (runtime ok).

### 2. Contrato **fail-soft** (valor neutro + `logger.warning`)

Toda função da fachada tem o mesmo esqueleto — `try/except Exception`, devolve um
**valor neutro** e registra `logger.warning` com o nome da função e a falha:

| Situação | Valor neutro devolvido |
|:---|:---|
| Módulo ausente / não importável | `None` / `[]` / `0` / `False` |
| Banco do módulo fechado/locked | idem (o `except` da fachada absorve) |
| Entrada vazia (`""`, `None`) | idem, sem chegar ao banco |
| Função de destino com assinatura mudada | idem + warning com o nome da função |

**Regra dura (AGENTS.md §3.2):** a fachada **nunca derruba a tela de quem
chama**. Um `audit_log`, uma busca de usuário ou uma notícia de TV que falham
não podem derrubar a página — o chamador decide o que fazer com o vazio (o
padrão adotado é aviso amigável, não erro).

## As 7 funções e onde cada uma é usada

> O arquivo expõe **7 funções públicas** (`integracoes.py:32-145`), agrupadas em
> 4 blocos com separadores de seção: Gestão de usuários, Agregador de notícias,
> Lista telefônica e Módulos do sistema.

| # | Função | Destino | Consumidores |
|:--|:---|:---|:---|
| 1 | `obter_usuario_gestao(user_nome)` (`:32`) | `mod_gest_cad_usuario.bd_manipulador.obter_usuario` | `mod_filas/bd_manipulador.py:454` (reconhecer `administrador_geral` ao autorizar) · `mod_filas/bd_manipulador.py:483` (`liberar_acesso` exige usuário cadastrado) · `mod_lista_telefonica/telas_administracao.py:745` (preencher nome/telefone do contato) |
| 2 | `listar_usuarios_gestao(filtro_ativo=None)` (`:49`) | `listar_usuarios` | `mod_filas/telas.py:631` (busca "liberar fila para usuário") · `mod_lista_telefonica/telas_administracao.py:689` (busca de contato por nome/login/e-mail) |
| 3 | `agregador_habilitado()` (`:66`) | `mod_agregador_noticias.bd_manipulador.habilitado` | `mod_filas/telas.py:1739` (TV: agregador desligado → aviso "Notícias pausadas") |
| 4 | `listar_noticias_para_tv(limite=200)` (`:79`) | `listar_para_tv` (censura já filtrada na origem) | `mod_filas/telas.py:1747` (carrossel de manchetes da TV de Filas) |
| 5 | `limpar_noticias_censuradas()` (`:93`) | `limpar_censuradas` | `mod_blog/telas_administracao.py:105` (após salvar a lista de censura: purga as já coletadas) |
| 6 | `obter_organograma_base()` (`:110`) | `mod_lista_telefonica.bd_manipulador.ORGANOGRAMA_BASE` | `mod_solicita_impressao/bd_manipulador.py:407` (semeadura das cotas: 1000 por secretaria, 200 por setor/subsetor) |
| 7 | `modulo_habilitado(chave)` (`:127`) | `mod_intranet.autenticacao.modulos_registrados` (`tb_modulos.ativo`) | chamador genérico — módulo desconhecido conta como **desligado** |

!!! warning "`obter_organograma_base()` devolve `None` de propósito"
    A Lista Telefônica é a fonte única do organograma, mas a Solicitação de
    Impressão **mantém seu próprio fallback local**: se a fachada devolver
    `None` (módulo ausente, import quebrado, organograma vazio), a semeadura
    continua com um conjunto mínimo de secretarias (`mod_solicita_impressao/bd_manipulador.py:411-421`).
    Fallback **no chamador**, nunca um valor "inventado" devolvido pela fachada —
    a fachada informa ausência, ela não simula presença.

## Precedente: `mod_intranet/censura.py`

`censura.py` (chave `conteudo_palavras_bloqueadas` em `tb_config`) já resolvia o
mesmo problema **antes** da fachada: o Blog e o Agregador precisam da **mesma**
lista de palavras bloqueadas, e o dado mora no **núcleo** (`tb_config`), não no
módulo. Os dois módulos consomem `obter_palavras_bloqueadas()` /
`titulo_bloqueado()` do núcleo — sem se conhecerem.

`integracoes.py` generaliza esse padrão: **antes** o dado era uma chave de
configuração compartilhada; **agora** a fachada cobre dado que mora no **outro
módulo**. Mesma filosofia — o núcleo como dono da costura, imports lazy, cada
lado fail-soft. Ver
[Censura de conteúdo](../analise_mod_intranet.md#censura-de-conteudo-palavras-bloqueadas-central-mod_intranetcensurapy).

## Exceção documentada: cascata LGPD

`check_integridade.py` mantém uma allowlist (`CASCATA_LGPD`) com os **únicos**
pares de negócio→negócio permitidos:

```python
CASCATA_LGPD = {("mod_gest_cad_usuario", "mod_blog"),
                ("mod_gest_cad_usuario", "mod_edit_pdf"),
                ("mod_gest_cad_usuario", "mod_renomear_empenho")}
```

Justificativa: quando um usuário é **excluído** ou **renomeado**, a Gestão de
Usuários chama a API **pública** de limpeza do próprio banco de cada módulo
afetado (remover/anonimizar/renomear). Cada módulo **toca só o seu banco** — não
há cross-query; o que existe é uma operação de negócio que **precisa** ser
transacional na frente do usuário. Qualquer outro par negócio→negócio é
violação. Ver
[Gestão de Usuários](../analise_mod_gest_cad_usuario.md#limpeza-cruzada-lgpd-a-unica-excecao-de-negocionegocio).

## Validação estrutural — `assets/test/check_integridade.py`

Guarda **estática** (AST via stdlib `ast`, sem importar nada, sem banco, sem
rede) com 3 blocos e 13 verificações:

| Bloco | Regra | Severidade |
|:---|:---|:---|
| **A** | Nenhum módulo de negócio importa outro (`mod_a → mod_b`, A≠B≠`mod_intranet`); cada módulo só acessa o **próprio** banco | **falha** (exceto `CASCATA_LGPD`) |
| **B** | Sem ciclo de import **top-level** entre `mod_*` e `main.py` | **falha**; ciclo **apenas-lazy** → **AVISO** (runtime ok) |
| **C** | Todo `mod_*` tem `bd_manipulador.py` (nunca `db_manipulador.py`) | **falha** |

```bash
.venv/bin/python assets/test/check_integridade.py
```

**Antes/depois de 25/09/2026:** **5 falhas em 17 verificações** → **13/13
verificações OK**, e 2 ciclos apenas-lazy desapareceram.

O contador do bloco A é por **par de módulos** (não por ponto de chamada), e as
5 violações fechadas foram exatamente estes 5 pares:

| # | Par de módulos | Fachada que substituiu o import direto |
|:--|:---|:---|
| 1 | `mod_blog` → `mod_agregador_noticias` | `limpar_noticias_censuradas` |
| 2 | `mod_filas` → `mod_agregador_noticias` | `agregador_habilitado`, `listar_noticias_para_tv` |
| 3 | `mod_filas` → `mod_gest_cad_usuario` | `obter_usuario_gestao`, `listar_usuarios_gestao` |
| 4 | `mod_lista_telefonica` → `mod_gest_cad_usuario` | `obter_usuario_gestao`, `listar_usuarios_gestao` |
| 5 | `mod_solicita_impressao` → `mod_lista_telefonica` | `obter_organograma_base` |

!!! note "Os AVISOs de ciclo apenas-lazy que continuam são esperados"
    Ex.: `mod_agregador_noticias -> mod_intranet -> mod_agregador_noticias`.
    São ciclos que **só se fecham em runtime**, quando alguém chama a fachada —
    resolvidos em tempo de execução e inofensivos. O que é **proibido** é o
    ciclo em nível de **topo** (bloco B), que quebraria o boot.

## Como adicionar uma função nova na fachada

1. **Verifique se o dado é mesmo de outro módulo.** Se o dado pode viver no
   núcleo (`tb_config`), prefira `get_config`/`set_config` (precedente
   `censura.py`) — é mais simples que abrir a fachada.
2. **Nomeie pela INTENÇÃO, não pelo destino** (`listar_usuarios_gestao` e não
   `chamar_gest_cad_usuario`): quem consome precisa saber o que recebe, não quem
   tem o dado.
3. **`import` dentro da função** e **só** do `bd_manipulador` do destino.
4. **Envolva em `try/except Exception`**, devolva o **valor neutro** e registre
   `logger.warning` com o nome da função + a causa.
5. **Docstring bilíngue** (EN no topo, PT-BR abaixo) e **tipo de retorno
   declarado** quando a resposta for sempre o mesmo tipo.
6. **Rode `check_integridade.py`** — o passo novo não pode criar aresta de
   negócio→negócio nem ciclo top-level.
7. **Documente**: linha na tabela acima + seção "Integrações" na
   [Análise do módulo consumidor](../modulos/gest_cad_usuario.md) e no resumo em
   `modulos/`.

!!! danger "O que a fachada NÃO é"
    - **Não é** um `SELECT` cross-database. Cada função executa SQL apenas no
      banco do módulo de destino, via o `bd_manipulador` dele.
    - **Não é** um barramento de eventos. É uma chamada síncrona best-effort; não
      há fila, retry ou transação distribuída.
    - **Não substitui** `get_config`/`set_config` para o que é configuração global.
    - **Não garante** consistência entre módulos: quem chama decide se o vazio
      é aceitável (um aviso na TV) ou exige tratamento (falha de cadastro).

Ver também: [Análise do Núcleo `mod_intranet`](../analise_mod_intranet.md) ·
[Arquitetura de Software (DAS)](index.md) · [Convenções de Código](../convencoes_codigo.md)
