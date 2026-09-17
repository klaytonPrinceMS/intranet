# Graphify — guia de bordo para programadores novos (dev-only)

> EN: Knowledge-graph handbook for new developers (dev-only tooling).
> PT-BR: Guia de bordo do grafo de conhecimento para quem chega agora no
> projeto sem conhecimento prévio de Graphify.

> Ferramenta da equipe de desenvolvimento (com internet). O runtime da intranet
> segue offline/local. Graphify **nunca** entra em `requirements.txt`, nunca é
> importado por `main.py`/`mod_*/` e nunca vai no bundle PyInstaller.
> Fonte das dependências dev: `requirements-dev.txt`.
> Ver também a seção dev-only em `requisitos.md`.

## 1. O que é e por que usamos

`Graphify-Labs/graphify` (pacote PyPI `graphifyy`, comando `graphify`) transforma
o repositório em um **grafo de conhecimento consultável**: cada função, classe,
arquivo e conceito vira um nó; cada chamada, importação ou menção vira uma
aresta com procedência honesta — `EXTRACTED` (lida no código),
`INFERRED` (inferida, com confiança) ou `AMBIGUOUS` (ambígua, verificar).

Neste projeto usamos o Graphify como **mapa de navegação do código**:

- Antes de abrir dez arquivos com leitura bruta, pergunte ao grafo
  (`query`/`path`/`explain`) — a resposta vem como subgrafo pequeno, com
  `source_location` (arquivo + linha) para cada fato.
- O grafo **code-only já está gerado** em `graphify-out/`: **2841 nós,
  6925 arestas, 132 comunidades** (extração 95% `EXTRACTED`, 5% `INFERRED`,
  custo zero de LLM — só AST local). Arquivos commitáveis: `graph.json`,
  `GRAPH_REPORT.md`, `manifest.json`. Arquivos locais (não commitar):
  `cost.json`, `cache/`, `.graphify_*.json`, `.graphify_python`.
- A regra de ouro está no `AGENTS.md` (`## graphify`): **query-first** —
  se `graphify-out/graph.json` existe e a pergunta é sobre o código,
  rode `graphify query` primeiro; leia `GRAPH_REPORT.md` só para visão ampla
  de arquitetura.

!!! note "Dev-only, runtime offline"
    O Graphify roda nas máquinas da equipe (com internet para instalar o
    pacote e para a passada semântica opcional de `docs/`). O servidor da
    intranet opera sem internet. Nunca adicione `graphifyy` ao
    `requirements.txt` (só `requirements-dev.txt`, `>=0.9.0` com extras
    `[sql,postgres,pdf]`) e nunca importe `graphify` dentro de `mod_*/`.

## 2. Instalação passo a passo

Pré-requisito: `.venv` do projeto criado (ver `inicio_rapido.md`).

```bash
# 1. Instalar o pacote (dev-only, com extras de SQL/Postgres/PDF)
.venv/bin/pip install "graphifyy[sql,postgres,pdf]"

# 2. Registrar a skill no projeto (modo --project, versionado)
.venv/bin/graphify install --platform opencode --project

# 3. Instalar o plugin OpenCode no projeto
.venv/bin/graphify opencode install
```

Isso grava (tudo versionado — `.opencode/` é 100% commitado, decisão 2026-09-17):

- `.opencode/skills/graphify/SKILL.md` + `references/` (a skill `/graphify`)
- `.opencode/plugins/graphify.js` + `.opencode/opencode.json` (plugin)
- seção `## graphify` no `AGENTS.md` (gatilho `/graphify` + regra query-first)
- wrapper interno `.opencode/agent/kbp-graphify.md` (padrão `kbp-*`, `AGENTS.md` §8.1)

Para sair e recarregar agentes após mexer em `.opencode/`, **saia e reinicie o
OpenCode** (o boot carrega os agentes).

Usuários de teste/QA citados neste guia: `master` (`administrador_geral`),
`qacomum` (`comum`), `qamaster` (`administrador_geral`) — **senhas nunca
aparecem em docs públicas** (`AGENTS.md` §8.2). A fonte das senhas de seed é
`mod_gest_cad_usuario/bd_manipulador.py` (`init_db`).

## 3. Comandos essenciais (cole e use)

```bash
# Extração inicial code-only (offline, só AST, sem LLM, sem custo)
.venv/bin/graphify extract . --code-only

# Via skill (código + docs; usa Gemini se GEMINI_API_KEY existir,
# senão o agente host assume a passada semântica)
/graphify .

# Re-extrai só o que mudou (incremental, rápido)
/graphify --update

# Perguntas sobre o código (BFS amplo; --dfs rastreia um caminho; --budget limita tokens)
.venv/bin/graphify query "como funciona o login e a sessão do usuário?"
.venv/bin/graphify query "onde fica a função autenticar?"

# Caminho mais curto entre dois conceitos (neste repo, prefira --undirected;
# ver §6 exemplo real autenticar → registrar_login)
.venv/bin/graphify path "autenticar" "registrar_login" --undirected

# Explicação em linguagem simples de um nó
.venv/bin/graphify explain "CrudBase"

# Após editar código ou após git pull (AST-only, sem custo)
.venv/bin/graphify update .
```

Detalhe de cada verbo da skill (sintaxe completa em
`.opencode/skills/graphify/SKILL.md`): `/graphify <caminho>`,
`/graphify <caminho> --mode deep`, `/graphify <caminho> --update`,
`/graphify query "<pergunta>"`, `/graphify path "<A>" "<B>"`,
`/graphify explain "<conceito>"`, além de `--watch`, `--wiki`, `--obsidian`,
`--svg`, `--graphml`, `--neo4j`/`--falkordb`, `--mcp` e
`graphify hook install` / `graphify add <url>`.

## 4. Regra query-first (o hábito que economiza horas)

Quando `graphify-out/graph.json` existe:

1. **Pergunta sobre código → `query` primeiro.** Não abra `mod_*/` no escuro.
2. **Relação entre dois pontos → `path`.** Ex.: quem liga autenticação a sessão.
3. **Conceito isolado → `explain`.** Ex.: o que é `CrudBase`, onde mora.
4. **`GRAPH_REPORT.md` só para visão ampla** (revisão de arquitetura, god nodes,
   ciclos de import) ou quando `query`/`path`/`explain` não derem contexto.
5. **Cite `source_location`.** Toda afirmação sobre código deve vir com
   arquivo + linha vindos do grafo.

Por quê: o subgrafo de resposta costuma ter dezenas de nós contra milhares do
grafo cheio — muito menor que varrer tudo com busca textual.

## 5. Como ver o grafo

| Artefato | Onde | Como abrir |
|---|---|---|
| Grafo interativo | `graphify-out/graph.html` (~3 MB) | abra no navegador (`xdg-open graphify-out/graph.html`) |
| Relatório em linguagem simples | `graphify-out/GRAPH_REPORT.md` | leia no editor; seções God Nodes, Surprising Connections, Suggested Questions |
| Grafo bruto (GraphRAG) | `graphify-out/graph.json` (~3,8 MB) | via `query`/`path`/`explain`; não abra na mão |
| Controle incremental | `graphify-out/manifest.json` | hashes AST/semânticos por arquivo (o `--update` usa isto) |

O `graph.html` é gerado por padrão (`graphify export html`). Para pular a
visualização: `--no-viz`. Formatos extras: `--svg`, `--graphml`,
`--neo4j`/`--falkordb` (gera `cypher.txt`), `--wiki` (wiki navegável por
comunidade), `--obsidian` (vault).

## 6. Exemplos práticos reais deste projeto

Todos os comandos abaixo foram executados contra o grafo real
(`2841 nós · 6925 arestas · 132 comunidades`, gerado em 2026-09-17).

### 6.1 Login e sessão — `query`

```bash
.venv/bin/graphify query "como funciona o login e a sessão do usuário?"
```

Resposta (resumo): travessia BFS profundidade 2 a partir de
`Sessao`, `login()`, `usuario_logado()` — **334 nós encontrados**, 63 exibidos
no orçamento padrão. Nós-âncora reais:

- `Sessao` em `mod_intranet/models/__init__.py:98` (comunidade `repositorio.py`)
- `usuario_logado()` em `mod_intranet/telas.py:28`
- `pagina_restrita()` em `mod_intranet/telas.py:33` (o guarda de página)
- `.obter_sessao_ativa()` em `mod_intranet/repositorio.py:448`

Lição de novato: o fluxo canônico é
`autenticar` → `registrar_login` → `pagina_restrita` revalida a cada request →
`tb_sessoes`. Se a resposta vier truncada (`TRUNCATED`), estreite com
`--budget` maior ou `query "..." --dfs`, ou pergunte por um símbolo exato
(§6.2).

### 6.2 Onde mora `autenticar` — `query` por símbolo exato

```bash
.venv/bin/graphify query "onde fica a função autenticar?"
```

Resposta (resumo): **36 nós, 70 arestas** — âncora
`autenticar()` em `mod_intranet/autenticacao.py:274`
(comunidade `autenticacao.py`), vizinhos:

- `usuario_existe()` (`autenticacao.py:265`), `verificar_senha()` (`:252`),
  `_gest()` (`:260`), `perfil_global_de()` (`:557`)
- `registrar_login()` (`autenticacao.py:309`, comunidade `registrar_login`)
- `get_connection()` (`mod_intranet/bd_conexao.py:75`)
- `pagina_restrita()` (`mod_intranet/telas.py:33`)
- `init_db()` (`mod_gest_cad_usuario/bd_manipulador.py:70`)
- teste `test_login_e_sessao_em_banco()` (`assets/test/test_fase1_login.py:13`)

Ou seja: autenticação vive em `mod_intranet/autenticacao.py`, persiste sessão
via `Repositorio`/conexão central e é consumida pelo guarda `pagina_restrita`.

### 6.3 Ligando autenticação à sessão — `path` (com `--undirected`)

```bash
.venv/bin/graphify path "autenticar" "registrar_login" --undirected
```

Resposta real:

```text
Shortest path (2 hops):
  autenticar() <--calls [EXTRACTED]-- test_login_e_sessao_em_banco() --calls [EXTRACTED]--> registrar_login()
```

Sem `--undirected`, o grafo direcionado responde `No directed path found`.
Lição: **neste repo prefira `--undirected` para perguntas de relação** — as
arestas AST têm direção e o caminho útil quase sempre cruza um teste ou um
chamador comum. No código-fonte, a ligação direta está em
`mod_intranet/autenticacao.py` (`autenticar` em `:274`,
`registrar_login` em `:309`, mesmo módulo).

### 6.4 O que é `CrudBase` — `explain`

```bash
.venv/bin/graphify explain "CrudBase"
```

Resposta real (resumo):

```text
Node: CrudBase
  ID:        mod_intranet_crud_base_crudbase
  Source:    mod_intranet/crud_base.py L60
  Type:      code
  Community: CrudBase
  Degree:    19
```

Conexões (19, todas `EXTRACTED`): importa quem usa
(`mod_intranet/bd_manipulador.py:13`, `assets/test/teste_classes_crud.py:135`,
`teste_fluxo_blog.py:18`, `test_cobertura_total.py:218`) e métodos
(`_executar`, `_log`, `_conectar`, `transacao`, `atualizar`,
`executar_muitas`, `listar`, `obter`, `criar`, `excluir`, `criar_tabela`,
`__init__`). Lição: `CrudBase` é o **único ponto de acesso ao banco**
(`AGENTS.md` §4) — nunca `sqlite3` cru; toda conexão aplica
`PRAGMA journal_mode=WAL`.

### 6.5 God nodes e ciclos de import (lendo o relatório)

Top 5 nós mais conectados (`GRAPH_REPORT.md`, seção God Nodes):

1. `audit_log()` — 111 arestas
2. `notificar()` — 97 arestas
3. `get_config()` — 92 arestas
4. `botao()` — 90 arestas
5. `usuario_logado()` — 83 arestas

Tradução para novatos: quase todo fluxo toca auditoria, notificação toast,
configuração (`tb_config`), fábrica de botões e sessão. Ao depurar um caminho
estranho, procure primeiro por esses cinco.

Ciclos de import reais (seção Import Cycles do relatório):

```text
mod_intranet/autenticacao.py -> mod_intranet/bd_conexao.py
  -> mod_intranet/tema_modulo.py -> mod_intranet/autenticacao.py
mod_intranet/autenticacao.py -> mod_intranet/bd_manipulador.py
  -> mod_intranet/bd_conexao.py -> mod_intranet/tema_modulo.py
  -> mod_intranet/autenticacao.py
```

Não quebre esses ciclos com import novo sem `query` antes — use o grafo para
achar o ponto de corte (ex.: mover helper para `ui_comum`/`tema_modulo`).

Comunidades úteis como ponto de partida (seção Communities):

- `Community 22 "autenticacao.py"` (36 nós: `autenticar`, `registrar_login`,
  `sessao_ativa`, `validar_acesso_modulo`…)
- `Community 40 "CrudBase"` (13 nós: `listar`, `obter`, `criar`, `atualizar`,
  `excluir`, `transacao`…)
- `Community 29 "main.py"` (28 nós: `page_*`, rotas, agendador)
- `Community 0/1/2` (um `bd_manipulador.py` por módulo — isolamento total,
  `AGENTS.md` §2)

## 7. Workflow com git (grafo sempre fresco)

```bash
# Instala o hook: rebuild AST após commit/checkout (background)
.venv/bin/graphify hook install

# Rotina diária
git pull
.venv/bin/graphify update .        # re-extrai só o que mudou (manifest.json)

# Após editar código, antes de perguntar ao grafo
.venv/bin/graphify update .        # AST-only, sem custo de API

# Após mudar docs/ (AST sozinho NÃO atualiza docs — precisa passada semântica)
/graphify . --update                # via skill (subagents)
```

> **Nada é automático:** o plugin `tool.execute.before` só injeta lembrete e
> `hook install` exige repo git (com lag de background). O dono da atualização é
> o subagente `.opencode/agent/kbp-graphify.md` — os demais `kbp-*` devem
> acioná-lo após qualquer mudança (código → `update .`; docs → `/graphify . --update`).

Regras:

- `.gitignore` é respeitado automaticamente; `.graphifyignore` só exclui mais.
- Arquivos sujos em `graphify-out/` após hooks/updates incrementais são
  **esperados** — não é motivo para ignorar o grafo (`AGENTS.md` `## graphify`).
- Commite `graph.json` + `GRAPH_REPORT.md` + `manifest.json`. **Nunca**
  commite `cost.json`, `cache/`, `.graphify_*.json`, `.graphify_python`.
- Pule o grafo só se a tarefa for sobre saída obsoleta/incorreta do próprio
  grafo, ou se o usuário disser explicitamente para não usar.

## 8. Troubleshooting

| Sintoma | Causa provável | Correção |
|---|---|---|
| `/graphify` não dispara a skill | gatilho ausente no `AGENTS.md` | conferir seção `## graphify` no `AGENTS.md` (bug `#827`, fix `v0.7.16+`) |
| Plugin não carrega | entrada ausente no projeto | conferir `.opencode/plugins/graphify.js` + entrada em `.opencode/opencode.json` **do projeto** (bug `#1412` era no modo global `~/.opencode` vs `~/.config/opencode`; modo `--project` não é afetado) |
| `path` responde `No directed path found` | arestas direcionadas | repetir com `--undirected` (ex. §6.3) |
| `query` responde `TRUNCATED` | orçamento de tokens | aumentar `--budget N`, usar `--dfs`, filtrar `context_filter=['call']` ou `get_node` no símbolo exato |
| Passada semântica de `docs/` fraca | sem `GEMINI_API_KEY` | exportar `GEMINI_API_KEY` (ou `GOOGLE_API_KEY`); sem ela, o agente host assume (`pip install 'graphifyy[gemini]'` para o backend Gemini) |
| `graph.json` encolheu após rebuild | guarda anti-shrink `#479` | `to_json` recusa sobrescrever; se a remoção foi intencional, refaça com `--force` |
| Hook reinstalando tudo do zero | `manifest.json` apagado | não apague `manifest.json`; sem ele o `--update` vira full rebuild |

## 9. Referências

- Skill: `.opencode/skills/graphify/SKILL.md` (sintaxe completa + `references/:
  extraction-spec.md`, `query.md`, `update.md`, `hooks.md`, `exports.md`,
  `add-watch.md`, `github-and-merge.md`, `transcribe.md`)
- Wrapper interno: `.opencode/agent/kbp-graphify.md`
- Regra query-first: `AGENTS.md` (`## graphify`)
- Dependência dev: `requirements-dev.txt` (`graphifyy[sql,postgres,pdf]>=0.9.0`)
- Detalhe dev-only: `requisitos.md` (tabela de dependências de desenvolvimento)
- Saída versionada: `graphify-out/graph.json`, `graphify-out/GRAPH_REPORT.md`,
  `graphify-out/manifest.json`
- Upstream: `Graphify-Labs/graphify` (issues `#827` trigger, `#1412` path)
