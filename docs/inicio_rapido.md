# Intranet Modular — Guia de Início Rápido

> Passos para rodar a Intranet Modular localmente: criar o `.venv`, instalar `requirements.txt`, subir com `.venv/bin/python main.py`, acessar `http://localhost:8080`, entrar com o seed `master`/`master` (troca de senha obrigatória) e usar as contas de teste `qacomum`/`qamaster`.

## Sumário

1. [Pré-requisitos](#pre-requisitos)
2. [Passo 1 — Preparar o ambiente virtual](#passo-1-preparar-o-ambiente-virtual)
3. [Passo 2 — Subir o servidor](#passo-2-subir-o-servidor)
4. [Passo 3 — Primeiro acesso](#passo-3-primeiro-acesso)
5. [Passo 4 — Usuários de teste](#passo-4-usuarios-de-teste)
6. [Smoke test](#smoke-test)
7. [Solução de problemas](#solucao-de-problemas)

## Pré-requisitos

- **Python 3.12** instalado na máquina.
- Acesso ao código-fonte (este repositório).
- Rede interna (o sistema não depende de internet, mas o download de dependências na primeira instalação precisa dela).

## Passo 1 — Preparar o ambiente virtual

A partir da raiz do projeto:

```bash
python3.12 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
```

O `requirements.txt` instala todas as dependências (NiceGUI, APScheduler, nh3, libs de PDF, bcrypt, loguru e mkdocs).

## Passo 2 — Subir o servidor

```bash
.venv/bin/python main.py                 # sem argumentos → sobe direto com a configuração persistida (tb_config)
.venv/bin/python main.py --help          # ajuda em PT-BR — "Sem argumentos, sobe direto com a configuração persistida"
.venv/bin/python main.py --config        # abre o assistente interativo (alias -c)
```

- O servidor sobe na porta **8080** (`porta_site`, `reload=False`, `show=False`, `tailwind=True` — Tailwind local sem CDN); a documentação mkdocs sobe na porta **8000** (`porta_documentacao`).
- **Sem argumentos**, o boot carrega `config_persistida()` (`mod_intranet/ativacao.py:1284`) — lê `tb_config` (banco_tipo, postgres_url, otel_ativo, portas) com fallback em `_config_padrao()` — e sobe direto. O assistente só abre com `--config`/`-c`.
- No boot, `inicializar_bancos()` cria os bancos `db_mod_*` (SQLite WAL) caso não existam e o usuário seed `master`/`master`.
- Pastas operacionais são criadas automaticamente em runtime pelo boot/rotinas (`os.makedirs(..., exist_ok=True)`): na raiz, `backup/` e `logs/`; dentro dos módulos, `mod_edit_pdf/editorPDF/`, `mod_renomear_empenho/doc/`, `mod_renomear_empenho/organizadorPasta/`, `mod_renomear_empenho/quarentena/` (regra de ouro do AGENTS.md: artefatos de módulo vivem dentro de `mod_*`).
- A documentação é compilada (MkDocs) e servida em **http://localhost:8000** (porta mkdocs, separada do site).

Acesse no navegador:

```
http://localhost:8080          # site
http://localhost:8000          # documentação (mkdocs)
```

> **CLI Opção C (ativacao.py):** ativação com prefixo `--ativ-` (`--ativ-postgres` com aliases `--ativ-postgress` typo + `--postgres`, `-p`; `--ativ-otel` alias `--otel`, `-o`) e portas com prefixo `--porta-` (`--porta-docs` alias `--portadocumentacao`, `-d`; `--porta-db` alias `--portapostgres`, `-k`; `--porta-site` alias `--portasite`, `-s`; `--porta-grafana` alias `--portatelemetria`, `-t`), agrupadas por tipo e em ordem alfabética dentro do grupo, com contrações curtas `-c/-o/-p/-d/-k/-s/-t/-S` — ver [Manual de Instalação](manual_de_uso_instalacao/index.md#22-inicializacao-por-linha-de-comando-typer-opcao-c) e [Configurações](configuracoes.md#inicializacao-por-argumentos-de-linha-de-comando-opcao-c-092026).

## Passo 3 — Primeiro acesso

1. Abra `http://localhost:8080` (será redirecionado para `/login`).
2. Entre com o usuário **seed**:

| Usuário | Senha | Perfil |
|:---|:---|:---|
| `master` | `master` | `administrador_geral` |

3. **A troca de senha é obrigatória no 1º logon** — o sistema exibe o diálogo de troca e não permite prosseguir no fluxo normal (auto-cura idempotente: enquanto a senha for `master`, a troca é rearmada a cada boot — `mod_gest_cad_usuario/bd_manipulador.py:168-194`).

> ⚠️ **Segurança:** troque a senha do `master` imediatamente e não use a senha padrão em produção.

## Passo 4 — Usuários de teste

Os bancos já vêm com usuários de teste cadastrados (banco `db_mod_gest_cad_usuario.db`, tabela `tb_usuarios`):

| Usuário | Senha | Perfil | Acesso a módulos |
|:---|:---|:---|:---|
| `qacomum` | `123456` | `comum` | blog, editar_pdf (Edição de PDF), empenhos (Renomear Empenho) |
| `qamaster` | `123456` | `administrador_geral` | todos |

- Use **`qacomum`** para validar fluxos de usuário comum (permissões restritas, somente leitura no Blog, etc.).
- Use **`qamaster`** para validar fluxos de administrador geral (vê tudo, acesso à Auditoria e Configurações).

## Smoke test

Teste mínimo de bootstrap do servidor (sobe NiceGUI sem módulos):

```bash
.venv/bin/python assets/test/test_server.py
```

> O `test_server.py` acima é um **helper** (sobe a app na 8080 e bloqueia) — fica de **fora** da suíte automatizada (ver abaixo).

### Suíte completa de testes — pytest

O comando oficial de validação é `.venv/bin/pytest`: o `pytest.ini` (raiz) aponta o pytest apenas para o runner `assets/test/test_suite.py` (`testpaths = assets/test/test_suite.py`), que executa **TODOS** os scripts standalone de `assets/test/*.py` em subprocessos e falha se algum retornar código ≠ 0 (duração ≈3–5 min). Para rodar um único teste isolado:

```bash
.venv/bin/python assets/test/<arquivo>.py
```

Exemplo: `.venv/bin/python assets/test/teste_fluxo_blog.py`. Detalhes e lista de exclusões do runner: [Testes — Plano](testes_plano/index.md).

Testes existentes na pasta `assets/test/`:

| Script | Escopo |
|:---|:---|
| `assets/test/test_server.py` | bootstrap mínimo (smoke test) |
| `assets/test/test_editor_pdf.py` | editor PDF (32 verificações) |
| `assets/test/test_auditoria.py` | filtros/exportação da auditoria |
| `assets/test/test_fase1_login.py` | fase 1: login/autenticação |
| `assets/test/test_fresh_install.py` | instalação limpa |
| `assets/test/test_solicita_impressao.py` | módulo de solicitação de impressão |
| `assets/test/teste_fluxo_blog.py` | fluxo do Blog (33/33 OK) |
| `assets/test/teste_fluxo_autenticacao.py` | login → troca de senha → sessões → soft delete (19/19) |
| `assets/test/teste_fluxo_permissoes.py` | perfis/papéis por módulo (13/13) |
| `assets/test/teste_fluxo_renameador.py` | renomeador de empenhos (DOC + tipos especiais) |
| `assets/test/verifica_ui_comum.py` | equivalência visual dos componentes de UI (150 verificações) |

## Solução de problemas

| Problema | Causa provável | Solução |
|:---|:---|:---|
| "no such table: tb_config" na primeira subida | banco central não criado antes de importar módulo | a ordem correta está em `inicializar_bancos()` (central primeiro) — rodar `main.py` a partir da raiz |
| Caracteres estranhos / erro de sintaxe em `.py` | arquivo foi editado por ferramenta que corrompeu caracteres (histórico: PowerShell) | validar com `ast.parse` (abaixo) e corrigir |
| Porta 8080 ocupada | outro processo na porta | alterar `port` em `main.py` (bloco `ui.run`) |
| "FALTA telas.py em <módulo>" | estrutura do módulo incompleta | `main.py:65-67` valida `telas.py` obrigatório em cada `mod_*` |

Validação de sintaxe de qualquer arquivo Python (padrão do projeto):

```bash
.venv/bin/python -c "import ast; ast.parse(open('main.py', encoding='utf-8').read())"
```

> Em dúvida sobre configurações (`storage_secret`, portas, chaves de `tb_config`), veja [Configurações e Variáveis de Ambiente](configuracoes.md).

## Usar PostgreSQL (opcional, desde 08/09)

O padrão é **SQLite** (um arquivo por módulo, zero dependências). Para usar **PostgreSQL** (backend duplo, **um DATABASE `db_mod_<chave>` por módulo**, espelhando o arquivo SQLite):

1. Suba o container:
   ```bash
   cd assets/docker/postgres && docker compose up -d
   ```
2. Acesse `/configuracoes` → aba **Documentação** → card **"Banco de dados — SQLite ou PostgreSQL"** (ícone `storage`).
3. Selecione **PostgreSQL** e confira o DSN (`postgresql+psycopg2://intranet:intranet@localhost:5432/intranet`).
4. Clique **Aplicar** e **REINICIE o servidor** (`fuser -k 8080/tcp; .venv/bin/python main.py`).

No boot, os módulos recriam os bancos/tabelas no Postgres (`garantir_bancos_postgres` cria os DATABASE `db_mod_<chave>` ausentes; o schema entra pelos `init_db`). A migração de dados SQLite→PostgreSQL é manual. Para voltar ao SQLite, repita o passo 3 selecionando "SQLite" e reinicie.