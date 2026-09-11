# AGENTS.md — Diretrizes de Desenvolvimento Assistido por Agente

> Este documento é a **única fonte de verdade** para agentes (Codex CLI, Cursor, Claude Code, etc.) atuando neste repositório. Siga-o à risca.

## 1. Visão Geral e Regra de Ouro

Este repositório contém uma aplicação Python com entry point na raiz (`main.py`).

**REGRA DE OURO - PROIBIDO FORA DA RAIZ:**
É **expressamente proibido** criar, editar, mover ou manter arquivos fora da pasta raiz do projeto ou fora da pasta do seu respectivo módulo `mod_*`. Todo artefato usado por um módulo DEVE viver dentro de `mod_<nome>/`.

> Em caso de dúvida, reinicie o servidor de desenvolvimento em vez de executar a versão de produção.

## 2. Arquitetura de Software (DAS) — Intranet Modular

- **Entry point único:** `main.py` na raiz. Obrigatoriamente carrega `mod_gest_cad_usuario` e `mod_auditoria`.
- **Layout modular:** Cada funcionalidade é um pacote `mod_<nome>`.
- **Isolamento total:** Cada módulo deve criar, controlar e gerir seu próprio banco de dados. **Nunca faça cross-query entre bancos.**

### 2.1 Estrutura Padrão de um Módulo

```
mod_<nome>/
├── __init__.py              # Encapsulamento, exposição pública e bootstrap do módulo
├── models/
│   └── __init__.py          # (padrão a propagar) Mapeamento SQLAlchemy imperativo: Table + dataclass + map_imperatively() — hoje só mod_intranet
├── bd_criador.py            # LEGADO/MORTO — criador antigo do banco; NÃO confiar nem executar (schema real via init_db* do bd_manipulador)
├── bd_manipulador.py        # ÚNICO ponto de acesso ao DB do módulo (init_db*, queries, regras; conexão via mod_intranet/banco_conexao.conexao)
├── telas.py                 # Renderiza as telas de negócio (mostrar_tela(nome, perfil)) — usada pelo main.py
└── telas_administracao.py   # Painel de administração standalone (mostrar_administracao) — rota /admin/{chave_modulo}
```

> `mod_intranet` é o núcleo e acrescenta `bd_conexao.py` (delega `get_config`/`set_config` ao `Repositorio`), `repositorio.py`, `models/`, `banco_conexao.py` (backend duplo SQLite/PostgreSQL) e demais serviços. Os módulos de negócio NÃO têm `bd_conexao.py` próprio — usam o central `mod_intranet/bd_conexao`.

### 2.2 Estrutura Obrigatória da Raiz

Permitido na raiz apenas:

```
.
├── .pastasOcultas/          # Pastas não monitoradas (.git, .venv, etc)
├── assets/                  # css/, docker/, grafana/, legacy/, test/
├── backup/                  # Backups de bancos
├── docs/                    # Toda documentação MkDocs (obrigatório)
├── mod_*/                   # Um diretório por módulo
├── site/                    # Saída do mkdocs build
├── logs/
├── .gitattributes
├── .gitignore
├── gh-pages
├── LICENSE
├── main.py                  # Entry point
├── mkdocs.yml
├── pytest.ini               # Configuração do pytest (roda a suíte standalone via assets/test/test_suite.py)
├── README.md
├── requirements.txt         # Dependências de execução
└── requirements-dev.txt     # Dependências de desenvolvimento
```

**Regras:**
- Nenhuma pasta extra na raiz além de novos `mod_*`.
- Se um módulo usa pastas como `doc/`, `organizadorPasta/`, `quarentena/`, elas devem estar DENTRO de `mod_<nome>/`.
- Na conversão `main.py` -> executável (PyInstaller/py-to-exe), toda pasta usada deve ser criada e gerenciada dentro do respectivo `mod_*`.
- `db_mod_*.db` nunca deve ser commitado.

## 3. Convenções de Codificação

> **Fundamento: Domain-Driven Design (DDD) — Língua Ubíqua.** O padrão de criar
> funções/documentação **em Português BR** não é arbitrário: reflete a **língua
> ubíqua** do DDD — o vocabulário exatamente como os especialistas do domínio
> (servidores da prefeitura, almoxarifado, secretarias) falam no dia a dia.
> Ex.: `solicitacao_impressao`, `empenho`, `quarentena`, `autorizar_grupo`,
> `cota_paginas_mensal` são termos do negócio, não abstrações técnicas. Toda
> função, tabela, coluna e documentação deve usar esse vocabulário do domínio.

| Elemento | Padrão Obrigatório | Exemplo Correto |
|---|---|---|
| Idioma / semântica | Português BR | `calcular_total`, `usuario_ativo` |
| Classes | `PascalCase` | `GerenciadorUsuario` |
| Classes internas/privadas | `_PascalCase` | `_GerenciadorInterno` |
| Funções / Métodos | `snake_case` | `obter_usuario_por_id()` |
| Variáveis / Constantes | `MAIUSCULAS_SNAKE` | `TENTATIVAS_MAXIMAS` |
| Pacote de módulo | `mod_<nome>` minúsculas | `mod_renomear_empenho` |
| Arquivo fora do módulo | `mod_<nome>_<descricao>.py` | `mod_gest_relatorio.py` |
| Arquivo dentro do módulo | `snake_case.py` | `relatorio.py` |
| Banco de dados | `db_mod_<nome>.db` | `db_mod_gest.db` |
| Tabelas | `tb_<nome>` | `tb_usuario` |
| Colunas | `snake_case` | `nome_usuario`, `hash_arquivo` |
| Async | Sempre `asyncio` | `async def`, `await` |

> **PascalCase obrigatório (PEP 8 CapWords):**
> Classes DEVEM usar `PascalCase` (ex: `GerenciadorUsuario`). Se for interna/privada: `_PascalCase` (ex: `_GerenciadorInterno`).
> **NUNCA** use `camelCase` (`gerenciadorUsuario`) e **NUNCA** use `snake_case` (`gerenciador_usuario`) para classes.
> Se o agente encontrar `camelCase` em classe, deve corrigir automaticamente para `PascalCase`.

### 3.1 SQLAlchemy — Padrão Imperativo Obrigatório

Não use Declarative. Use mapeamento imperativo em `models/__init__.py`:
`Table` + `dataclass` + `map_imperatively()`.

## 4. Padrão de Acesso a Dados — CrudBase

> **Atualização: Uso obrigatório**

- `db_manipulador.py` é o ÚNICO local que acessa o banco.
- **NUNCA use `sqlite3` cru.** Use sempre `CrudBase`.
- Toda conexão DEVE aplicar `PRAGMA journal_mode=WAL`.
- `CrudBase` fornece: `listar()`, `obter()`, `criar()`, `atualizar()`, `excluir()`, `executar_muitas()`, `criar_tabela()` e transação atômica `crud.transacao()`.

## 5. Padrão de Telas — NiceGUI

- Assinatura: `def tela_xxx(nome: str, perfil: str):`
- **Sem JavaScript direto.**
- Respeite o layout de 4 partes da intranet.
- Valide o papel do ator antes de qualquer escrita.
- Gestão de estado: `ui.notify()`, `ui.spinner()`, desabilitar botões durante requisições

### Boas Práticas NiceGUI + Bootstrap/Tailwind
- Use `.classes()` para Tailwind e `.props()` para Quasar
- Prefira componentes com CSS do Bootstrap
- Evite `gap-*` em `ui.row()` — use `.style('gap: 1rem')`
- `.style('min-width: 0')` para evitar colapso flex
- `ui.scroll_area()` precisa de pai com altura explícita

## 6. Dependências e Execução

1. Atualize `requirements.txt`, `requirements-dev.txt`, `package-lock.json`, `compose.yml`
2. Reinicie:
```bash
fuser -k 8080/tcp || lsof -ti:8080 | xargs kill -9
.venv/bin/python main.py
```
3. Porta padrão: `8080`

## 7. Git — Commit e Push

**NUNCA execute `commit` ou `push` sem solicitação expressa do usuário.**

Formato: `AAMMDD HHMM breve resumo`
Exemplo: `260809 1200 Alterado padrão de exibição para o usuário`

## 8. Subagentes Autorizados

Autorização exclusiva para criar/editar se não existirem:

**kbp-web-design:** Frontend NiceGUI, responsivo, Bootstrap/Tailwind/Quasar, mobile-first, a11y
**kbp-doc:** Audita `/docs`, gera `estrutura.md` na raiz (NÃO commitar), padrão MkDocs tema readthedocs, docstring bilíngue EN no topo / PT-BR abaixo
**kbp-qa:** QA Sênior, data-testid via `.props('data-testid=...')`, pytest-playwright, pirâmide testes
**kbp-devSecOps:** Segurança, bandit 1.9.4, semgrep 1.176.1, pip-audit 2.10.1, safety 3.8.1, gitleaks 8.24.3, k6 — apenas localhost/staging

## 9. Skills

**seo-checklist:** Title 50-60 chars, meta 150-160 + CTA, H2/H3, keyword nos 100 primeiros chars, alt text

## 10. ADK

Orquestração em grafos, BaseNode com streaming e human-in-the-loop, contexto 1:1 com telemetria

## 11. Comandos Úteis

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python main.py
.venv/bin/pytest
.venv/bin/bandit -r mod_*/
.venv/bin/mkdocs serve
```
