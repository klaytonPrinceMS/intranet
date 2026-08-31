# Intranet Modular — Coding Conventions

> Coding standards extracted from the actual codebase: `snake_case` for Python functions/variables, `UPPER_SNAKE` for constants, module packages `mod_*`, database tables `tb_*`, kebab-case URL routes, per-module WAL databases, the `manipulador_bd.py` pattern and the NiceGUI screen pattern. When in doubt, mirror an existing module.

---

# Intranet Modular — Convenções de Criação de Código

> Padrões de código extraídos da base real: `snake_case` para funções/variáveis Python, `MAIUSCULAS_SNAKE` para constantes, pacotes de módulo `mod_*`, tabelas `tb_*`, rotas kebab-case, bancos WAL por módulo, padrão de `manipulador_bd.py` e padrão de tela NiceGUI. Em dúvida, espelhe um módulo existente.

## Sumário

1. [Visão geral](#visao-geral)
2. [Nomenclatura](#nomenclatura)
3. [Estilo de código](#estilo-de-codigo)
4. [Modelo de classes e objetos](#modelo-de-classes-e-objetos)
5. [Estrutura de um novo módulo `mod_*`](#estrutura-de-um-novo-modulo-mod_)
6. [Padrão de manipulador de banco](#padrao-de-manipulador-de-banco)
7. [Padrão de tela NiceGUI](#padrao-de-tela-nicegui)
8. [Auditoria e versionamento](#auditoria-e-versionamento)
9. [Checklist de aceite](#checklist-de-aceite)

## Visão geral

A Intranet Modular é um projeto **funcional/procedural** em Python: a base é composta quase inteiramente por **funções** e módulos, com apenas **uma classe** em todo o código (`_FormatadorBlog(HTMLParser)` — `mod_blog/manipulador_bd.py:373`). As convenções abaixo refletem o que **já existe** no repositório — não invente um padrão novo.

## Nomenclatura

| Item | Padrão | Exemplo real |
|:---|:---|:---|
| Funções e variáveis Python | `snake_case` | `autenticar`, `gerar_hash_senha`, `pagina_restrita`, `validar_acesso_modulo` |
| Constantes | `MAIUSCULAS_SNAKE` | `MODULOS_SISTEMA`, `CHAVE_POR_ROTA`, `PADRAO_CONFIG`, `DB_PATH`, `SESSION_COOKIE_NAME` |
| Classes (raras) | `CamelCase` (herança stdlib) | `_FormatadorBlog(HTMLParser)` — prefixo `_` para internas |
| Pacote de módulo | `mod_<nome>` (minúsculas) | `mod_blog`, `mod_gest_cad_usuario`, `mod_edit_pdf` |
| Arquivo de módulo | `mod_<nome>_<descricao>.py` | `mod_renomear_empenho_organizador.py`, `mod_intranet_inicializacao_bd.py` |
| Tabelas | `tb_<nome>` | `tb_usuarios`, `tb_postagens`, `tb_auditoria`, `tb_cota_disco` |
| Colunas | `snake_case` com prefixo semântico | `user_nome`, `user_senha`, `hash_arquivo`, `data_criacao` |
| Chaves de config | `<modulo>_<chave>` (snake_case em minúsculas) | `editpdf_lote_mb`, `empenhos_pasta_monitorada`, `backup_horas:<chave>`, `versao_modulo:<chave>` |
| Chaves de módulo | `snake_case` | `editar_pdf`, `solicita_impressao`, `renomear_empenho` |
| Rotas URL | **kebab-case** | `/edit-pdf`, `/renomear-empenho`, `/solicita-impressao` |
| Bancos | `db_mod_<nome>.db` | `db_mod_blog.db`, `db_mod_gest_cad_usuario.db` |

> ❌ **Não use `camelCase` para funções/variáveis Python.** O nome de arquivo de saída de PDF usa `dataHora_usuario_operacao_nomeArquivo.pdf` — isso é **nomenclatura de arquivo gerado**, não código.

## Estilo de código

- **Funcional/procedural**: prefira funções a classes. Cada tela é uma função; cada regra de banco é uma função no `manipulador_bd.py`.
- **Interface de tela obrigatória**: `telas.py` **DEVE** expor `mostrar_tela(usuario_logado, perfil)` (nome do parâmetro pode variar: `user_nome`, `usuario_logado`).
- Sem comentários supérfluos — o padrão do projeto mantém docstrings curtos em funções de núcleo e cabeçalhos de arquivo.
- **Validação obrigatória** após alterar qualquer `.py`:

```bash
.venv/bin/python -c "import ast; ast.parse(open('<arquivo>', encoding='utf-8').read())"
```

- Histórico de **caracteres corrompidos** em `main.py` (edição via PowerShell): evite ferramentas que reescrevam encoding por fora; confira imports (`get_config`, `get_connection`) ao mexer no topo dos arquivos.

## Modelo de classes e objetos

- **Default: funções.** O projeto não usa classes para regras de negócio (sem ORM, sem DTOs, sem "service objects").
- **Única exceção observada**: subclasses de classes da stdlib para tarefas específicas (`_FormatadorBlog(HTMLParser)`). Nesse caso use `CamelCase` + underscore inicial para indicar uso interno.
- **Componentes de UI** não são classes próprias: usa-se a API do NiceGUI (`ui.card()`, `ui.button(...)`, `ui.input(...)`) dentro de funções, tipicamente em blocos `with`.
- **Handlers de eventos**: funções aninhadas (`def tentar_login(): ...`) dentro da função de página — padrão presente em `main.py:87-107`.

## Estrutura de um novo módulo `mod_*`

```text
mod_<nome>/
  __init__.py
  telas.py            # OBRIGATÓRIO: expõe mostrar_tela(usuario_logado, perfil)
  manipulador_bd.py   # init_db* + queries + regras (criador vigente das tabelas)
  criador_bd.py       # NÃO crie/use — padrão legado/morto do projeto
  src/                # opcional: assets JS/CSS do módulo (ex.: mod_solicita_impressao/src/impressao.js)
```

Passos para criar:

1. **Estrutura**: crie `mod_<nome>/` com `__init__.py`, `telas.py` e `manipulador_bd.py`. **Não** crie `criador_bd.py` (é código morto em todos os módulos).
2. **Banco**: declare `DB_PATH` no `manipulador_bd.py` apontando para `db_mod_<nome>.db` na raiz; crie `init_db()` com `PRAGMA journal_mode=WAL` e `foreign_keys=ON` quando houver FKs.
3. **Bootstrap**: adicione a chamada `init_<nome>()` em `inicializar_bancos()` (`mod_intranet/mod_intranet_inicializacao_bd.py`) — **após** o banco central.
4. **Registro**: adicione `(chave, nome, ícone, rota)` em `MODULOS_SISTEMA` (`mod_intranet/autenticacao.py:15-22`) para semear `tb_modulos`, e registre a rota `@ui.page("/<rota>")` no `main.py` usando `pagina_restrita(título, chave_modulo="<chave>")`.
5. **Versão**: semeie `versao_modulo:<chave>` em `conexao_bd.init_db()` (formato `1.0.AAMMDD`) para o rodapé.
6. **Logs**: rotule os logs com `observabilidade.get_logger("<modulo>")`.

## Padrão de manipulador de banco

Template baseado no código real (`mod_blog/manipulador_bd.py` é o exemplo mais simples):

```python
"""<Módulo> — acesso ao db_mod_<nome>.db (WAL)."""
import os, sqlite3, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "db_mod_<nome>.db")

def _log():
    from mod_intranet import observabilidade
    return observabilidade.get_logger("<nome>")

def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn

def init_db():
    """Cria as tabelas (idempotente). Executado no import e pelo bootstrap."""
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS tb_exemplo (...) ")
        conn.commit()
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        conn.close()

# ... demais funções (listar/criar/atualizar/excluir) ...
# Escritas relevantes chamam audit_log do núcleo:
# from mod_intranet.manipulador_bd import audit_log
# audit_log(usuario, "<chave_modulo>", "criar_x", "descrição", hash_arquivo=None)
```

Regras:

- Toda conexão aplica `PRAGMA journal_mode=WAL` + `synchronous=NORMAL`.
- Nunca **cross-query** entre bancos de módulos (exceção documentada: limpeza cruzada LGPD da exclusão de usuário).
- Config do módulo em `tb_config` central (prefixo `<modulo>_*`) ou, quando isolada, numa `tb_config` local.
- Soft delete para entidades sensíveis com coluna `ativo`/`user_deletado` + motivo + auditoria.

## Padrão de tela NiceGUI

```python
# mod_<nome>/telas.py
from nicegui import ui

def mostrar_tela(usuario_logado: str, perfil: str):
    """Tela principal do módulo. `perfil` é o perfil global do usuário."""
    # 1. Gate de permissão (dupla camada: a rota já passou por pagina_restrita)
    if not <tem_permissao>(usuario_logado, perfil):
        ui.label("Acesso restrito").classes("text-h6 text-negative")
        return
    # 2. Cabeçalho/abas padronizadas (helper do núcleo)
    from mod_intranet.aba_modulo import cabecalho, abas
    # 3. Componentes NiceGUI dentro de funções/blocos with
    with ui.card().classes("w-full"):
        ui.label("Título").classes("text-h6")
        # ... ui.input / ui.button / ui.table / callbacks como funções aninhadas
```

Regras:

- Recebe `(usuario_logado, perfil)` (assinatura variável — ver `mostrar_tela` em cada `telas.py`).
- Valida o **papel do ator** antes de **qualquer escrita** (UI esconde e backend bloqueia).
- Use o layout de 4 partes via `pagina_restrita` na rota (o `telas.py` **não** monta header/drawer).
- Aparência/tema por módulo: bloco "Administração" com `ui.color_input` e chaves `tb_config` com prefixo do módulo.
- Conteúdo HTML do Blog passa obrigatoriamente por `nh3` (gravação e renderização).

## Auditoria e versionamento

- **Auditoria**: toda ação relevante (criar/editar/excluir/publicar/imprimir/autorizar/configurar/renomear) grava `audit_log(usuario, modulo, acao, descricao, hash_arquivo=None)` — `mod_intranet/manipulador_bd.py:66`.
- **Hash SHA-256** em operações com arquivos (editor PDF, empenhos, impressão).
- **Versionamento**: `1.0.AAMMDD`; versão global `versao_sistema` + por módulo `versao_modulo:<chave>` (exibidos da esquerda para a direita no rodapé). Atualize a chave do módulo quando alterar código dele — sem mexer na global nem nas dos outros.

## Checklist de aceite

- [ ] `telas.py` expõe `mostrar_tela(usuario_logado, perfil)` com gate de permissão.
- [ ] `manipulador_bd.py` tem `init_db*()` com WAL; bootstrap atualizado em `inicializar_bancos()`.
- [ ] Módulo registrado em `MODULOS_SISTEMA` + rota no `main.py` com `pagina_restrita(título, chave_modulo="<chave>")`.
- [ ] `versao_modulo:<chave>` semeada e log rotulado com `get_logger("<modulo>")`.
- [ ] Auditoria em todas as escritas; hash SHA-256 em operações com arquivos.
- [ ] `ast.parse` passou em todos os arquivos alterados.
- [ ] No `mkdocs.yml`, documentação do módulo adicionada ao `nav` (se houver).

> Convenções documentadas também em [Padrões de Codificação](padroes_codificacao/index.md) — este documento é a referência oficial unificada.