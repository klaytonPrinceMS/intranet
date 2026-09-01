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
.venv/bin/python main.py
```

- O servidor sobe na porta **8080** (`reload=False`, `show=False`, `tailwind=True` — Tailwind local sem CDN).
- No boot, `inicializar_bancos()` cria os bancos `db_mod_*` (SQLite WAL) caso não existam e o usuário seed `master`/`master`.
- Pastas operacionais (`backup/`, `organizadorPasta/`, `quarentena/`) são criadas automaticamente em runtime pelo boot/rotinas (`os.makedirs(..., exist_ok=True)`).
- A documentação é compilada (MkDocs) e servida em `http://localhost:8080/documentacao`.

Acesse no navegador:

```
http://localhost:8080
```

## Passo 3 — Primeiro acesso

1. Abra `http://localhost:8080` (será redirecionado para `/login`).
2. Entre com o usuário **seed**:

| Usuário | Senha | Perfil |
|:---|:---|:---|
| `master` | `master` | `administrador_geral` |

3. **A troca de senha é obrigatória no 1º logon** — o sistema exibe o diálogo de troca e não permite prosseguir no fluxo normal (auto-cura idempotente: enquanto a senha for `master`, a troca é rearmada a cada boot — `mod_gest_cad_usuario/manipulador_bd.py:136-156`).

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
.venv/bin/python test/test_server.py
```

Testes existentes na pasta `test/`:

| Script | Escopo |
|:---|:---|
| `test/test_server.py` | bootstrap mínimo (smoke test) |
| `test/test_editor_pdf.py` | editor PDF (32 verificações) |
| `test/test_auditoria.py` | filtros/exportação da auditoria |
| `test/test_fase1_login.py` | fase 1: login/autenticação |
| `test/test_fresh_install.py` | instalação limpa |
| `test/test_solicita_impressao.py` | módulo de solicitação de impressão |
| `testes/teste_fluxo_blog.py` | fluxo do Blog (33/33 OK) |

## Solução de problemas

| Problema | Causa provável | Solução |
|:---|:---|:---|
| "no such table: tb_config" na primeira subida | banco central não criado antes de importar módulo | a ordem correta está em `inicializar_bancos()` (central primeiro) — rodar `main.py` a partir da raiz |
| Caracteres estranhos / erro de sintaxe em `.py` | arquivo foi editado por ferramenta que corrompeu caracteres (histórico: PowerShell) | validar com `ast.parse` (abaixo) e corrigir |
| Porta 8080 ocupada | outro processo na porta | alterar `port` em `main.py` (bloco `ui.run`) |
| "FALTA telas.py em <módulo>" | estrutura do módulo incompleta | `main.py:22-24` valida `telas.py` obrigatório em cada `mod_*` |

Validação de sintaxe de qualquer arquivo Python (padrão do projeto):

```bash
.venv/bin/python -c "import ast; ast.parse(open('main.py', encoding='utf-8').read())"
```

> Em dúvida sobre configurações (`storage_secret`, portas, chaves de `tb_config`), veja [Configurações e Variáveis de Ambiente](configuracoes.md).