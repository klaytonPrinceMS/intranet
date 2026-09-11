# Intranet Modular — Coding Conventions

> Coding standards extracted from the actual codebase: `snake_case` for Python functions/variables, `UPPER_SNAKE` for constants, module packages `mod_*`, database tables `tb_*`, kebab-case URL routes, per-module WAL databases, the `bd_manipulador.py` pattern and the NiceGUI screen pattern. When in doubt, mirror an existing module.

---

# Intranet Modular — Convenções de Criação de Código

> Padrões de código extraídos da base real: `snake_case` para funções/variáveis Python, `MAIUSCULAS_SNAKE` para constantes, pacotes de módulo `mod_*`, tabelas `tb_*`, rotas kebab-case, bancos WAL por módulo, padrão de `bd_manipulador.py` e padrão de tela NiceGUI. Em dúvida, espelhe um módulo existente.

## Fundamentação — Domain-Driven Design (DDD) · Língua Ubíqua

O uso de **Português BR** em funções, tabelas e documentação segue o **Domain-Driven Design (DDD)** e a sua **Língua Ubíqua**: o vocabulário é o mesmo usado pelos especialistas do negócio no dia a dia (servidores da prefeitura, almoxarifado, secretarias). Ex.: `solicitacao_impressao`, `empenho`, `quarentena`, `autorizar_grupo`, `cota_paginas_mensal` são termos do domínio, não abstrações técnicas. Funções/tabelas/colunas/documentação devem sempre usar esse vocabulário — em conflito entre nome técnico e termo do negócio, vence o termo do negócio.

## Sumário

1. [Visão geral](#visao-geral)
2. [Nomenclatura](#nomenclatura)
3. [Estilo de código](#estilo-de-codigo)
4. [Modelo de classes e objetos](#modelo-de-classes-e-objetos)
5. [Estrutura de um novo módulo `mod_*`](#estrutura-de-um-novo-modulo-mod_)
6. [Padrão de manipulador de banco](#padrao-de-manipulador-de-banco)
7. [Padrão de tela NiceGUI](#padrao-de-tela-nicegui)
8. [PostgreSQL opcional](#postgresql-opcional-0809)
9. [Configurabilidade (regra de projeto)](#configurabilidade-regra-de-projeto)
10. [Auditoria e versionamento](#auditoria-e-versionamento)
11. [Checklist de aceite](#checklist-de-aceite)

## Visão geral

A Intranet Modular é um projeto **funcional/procedural** em Python: as regras de negócio são **funções** e módulos; **classes ficam restritas aos componentes reutilizáveis do núcleo `mod_intranet`** (desde 06/09: `CrudBase` em `crud_base.py`, `GradeTabela`/`PainelLista` em `ui_painel.py`, `FormularioBuilder` em `ui_form.py` e `BotaoFabrica`/`Dialogo`/`Cartao`/`CampoBase`/`CampoCor`/`CampoTexto`/`CampoSelecao` em `ui_comum.py` — além da exceção histórica `_FormatadorBlog(HTMLParser)`, `mod_blog/bd_manipulador.py:373`). As convenções abaixo refletem o que **já existe** no repositório — não invente um padrão novo.

## Nomenclatura

| Item | Padrão | Exemplo real |
|:---|:---|:---|
| Funções e variáveis Python | `snake_case` | `autenticar`, `gerar_hash_senha`, `pagina_restrita`, `validar_acesso_modulo` |
| Constantes | `MAIUSCULAS_SNAKE` | `MODULOS_SISTEMA`, `CHAVE_POR_ROTA`, `PADRAO_CONFIG`, `DB_PATH`, `SESSION_COOKIE_NAME` |
| Classes | `CamelCase` (componentes do núcleo) | `CrudBase`, `GradeTabela`, `PainelLista`, `FormularioBuilder`, `BotaoFabrica`, `Dialogo`, `Cartao`, `CampoBase`; prefixo `_` para internas (`_FormatadorBlog`) |
| Pacote de módulo | `mod_<nome>` (minúsculas) | `mod_blog`, `mod_gest_cad_usuario`, `mod_edit_pdf` |
| Arquivo de módulo | `mod_<nome>_<descricao>.py` | `mod_renomear_empenho_organizador.py`, `bd_criador.py` |
| Tabelas | `tb_<nome>` | `tb_usuarios`, `tb_postagens`, `tb_auditoria`, `tb_cota_disco` |
| Colunas | `snake_case` com prefixo semântico | `user_nome`, `user_senha`, `hash_arquivo`, `data_criacao` |
| Chaves de config | `<modulo>_<chave>` (snake_case em minúsculas) | `editpdf_lote_mb`, `empenhos_pasta_monitorada`, `backup_horas:<chave>`, `versao_modulo:<chave>` |
| Chaves de módulo | `snake_case` | `editar_pdf`, `solicita_impressao`, `renomear_empenho` |
| Rotas URL | **kebab-case** | `/edit-pdf`, `/renomear-empenho`, `/solicita-impressao` |
| Bancos | `db_mod_<nome>.db` | `db_mod_blog.db`, `db_mod_gest_cad_usuario.db` |

> ❌ **Não use `camelCase` para funções/variáveis Python.** O nome de arquivo de saída de PDF usa `dataHora_usuario_operacao_nomeArquivo.pdf` — isso é **nomenclatura de arquivo gerado**, não código.

## Estilo de código

- **Funcional/procedural**: prefira funções a classes. Cada tela é uma função; cada regra de banco é uma função no `bd_manipulador.py`.
- **Interface de tela obrigatória**: `telas.py` **DEVE** expor `mostrar_tela(usuario_logado, perfil)` (nome do parâmetro pode variar: `user_nome`, `usuario_logado`).
- Sem comentários supérfluos — o padrão do projeto mantém docstrings curtos em funções de núcleo e cabeçalhos de arquivo.
- **Validação obrigatória** após alterar qualquer `.py`:

```bash
.venv/bin/python -c "import ast; ast.parse(open('<arquivo>', encoding='utf-8').read())"
```

- Histórico de **caracteres corrompidos** em `main.py` (edição via PowerShell): evite ferramentas que reescrevam encoding por fora; confira imports (`get_config`, `get_connection`) ao mexer no topo dos arquivos.

### Suíte de testes — pytest

A suíte é **baseada em scripts standalone** em `assets/test/*.py` (checagens/asserts próprios; rodam com `.venv/bin/python assets/test/<arquivo>.py`). O comando oficial de validação é `.venv/bin/pytest`: o `pytest.ini` (raiz) limita a coleta do pytest ao runner `assets/test/test_suite.py` (`testpaths = assets/test/test_suite.py`, `pytest.ini:2`) — sem isso, o pytest tentava coletar os scripts standalone e quebrava (`INTERNALERROR` por `sys.exit` no import de `test_dashboard.py`). O runner executa TODA a suíte em subprocessos (`test_suite_standalone()`, `assets/test/test_suite.py:50`), falha se algum script retornar código ≠ 0 (≈3–5 min) e limpa as variáveis `PYTEST_*` do ambiente (`_env_limpo()`, `assets/test/test_suite.py:34`). `addopts = -p no:cacheprovider` (`pytest.ini:3`) desativa o cache `.pytest_cache/`. Detalhes e exclusões: [Testes — Plano](testes_plano/index.md).

## Modelo de classes e objetos

- **Default: funções.** Os módulos `mod_*` não usam classes para regras de negócio (sem ORM, sem DTOs, sem "service objects").
- **Classes no núcleo (06/09)**: componentes reutilizáveis de acesso a dados e UI vivem como classes em `mod_intranet` — `CrudBase`/`audit_reg` (`crud_base.py`), `GradeTabela`/`PainelLista` (`ui_painel.py`), `FormularioBuilder` (`ui_form.py`) e `BotaoFabrica`/`Dialogo`/`Cartao`/`CampoBase`+subclasses (`ui_comum.py`, com **wrappers finos funcionais** `botao`/`dialogo_card`/`campo_*` preservando a API antiga, byte-idêntica — provas em `test/verifica_ui_comum.py`, 187 OK). Regra: **não crie classes nos módulos** — importe as do núcleo.
- **Exceção histórica**: subclasses de classes da stdlib para tarefas específicas (`_FormatadorBlog(HTMLParser)`). Use `CamelCase` + underscore inicial para indicar uso interno.
- **Handlers de eventos**: funções aninhadas (`def tentar_login(): ...`) dentro da função de página — padrão presente em `main.py:87-107`.

## Estrutura de um novo módulo `mod_*`

```text
mod_<nome>/
  __init__.py
  telas.py            # OBRIGATÓRIO: expõe mostrar_tela(usuario_logado, perfil)
  bd_manipulador.py   # init_db* + queries + regras (criador vigente das tabelas)
  bd_criador.py       # NÃO crie/use — padrão legado/morto do projeto
  src/                # opcional: assets JS/CSS do módulo (ex.: mod_solicita_impressao/src/impressao.js)
```

Passos para criar:

1. **Estrutura**: crie `mod_<nome>/` com `__init__.py`, `telas.py` e `bd_manipulador.py`. **Não** crie `bd_criador.py` (é código morto em todos os módulos).
2. **Banco**: declare `DB_PATH` no `bd_manipulador.py` apontando para `db_mod_<nome>.db` na raiz; crie `init_db()` com `PRAGMA journal_mode=WAL` e `foreign_keys=ON` quando houver FKs.
3. **Bootstrap**: adicione a chamada `init_<nome>()` em `inicializar_bancos()` (`../mod_intranet/bd_criador.py`) — **após** o banco central.
4. **Registro**: adicione `(chave, nome, ícone, rota)` em `MODULOS_SISTEMA` (`mod_intranet/autenticacao.py:15-22`) para semear `tb_modulos`, e registre a rota `@ui.page("/<rota>")` no `main.py` usando `pagina_restrita(título, chave_modulo="<chave>")`.
5. **Versão**: semeie `versao_modulo:<chave>` em `bd_conexao.init_db()` (formato `1.0.AAMMDD`) para o rodapé.
6. **Logs**: rotule os logs com `observabilidade.get_logger("<modulo>")`.

## Padrão de manipulador de banco

Template baseado no código real (`../mod_blog/bd_manipulador.py` é o exemplo mais simples):

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
# from mod_intranet.bd_manipulador import audit_log
# audit_log(usuario, "<chave_modulo>", "criar_x", "descrição", hash_arquivo=None)
```

Regras:

- **Padrão vigente (06/09): use `CrudBase` — nunca `sqlite3` cru em código novo.** Instancie `_crud = CrudBase(DB_PATH, "<nome>", foreign_keys=True)` (com FKs), use os atalhos `listar`/`obter`/`criar`/`atualizar`/`excluir`/`executar_muitas`/`criar_tabela` e envolva sequências multi-instrução em `with _crud.transacao() as cur:` (commit/rollback atômicos — `mod_intranet/crud_base.py:60,135`). Auditoria das escritas via `audit_reg(ator, "<modulo>", "<acao>", "<alvo>")` (`crud_base.py:43`, wrapper fail-soft de `audit_log`). Piloto: `../mod_blog/bd_manipulador.py` **100% migrado** (`_crud = CrudBase(DB_BLOG_PATH, "blog")` — `bd_manipulador.py:49`), incluindo `mod_blog/telas.py` (`audit_reg` — `telas.py:135`); no núcleo, `garantir_rastreabilidade()` usa `CrudBase.transacao` (`mod_intranet/bd_manipulador.py:49-51`). O template `_conn()` cru abaixo permanece apenas nos módulos ainda não migrados (auditoria, edit_pdf, gest_cad_usuario, renomear_empenho, solicita_impressao) — migre ao tocar neles.
- Toda conexão aplica `PRAGMA journal_mode=WAL` + `synchronous=NORMAL` (o `CrudBase` já faz).
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

### Componentes de UI padronizados — `mod_intranet/ui_comum.py`

O núcleo expõe uma **fábrica central de componentes de UI** (`mod_intranet/ui_comum.py`) que unifica as variantes de botão do tema (`tema_modulo.botao`) com as variantes semânticas do painel de configurações (`_botao_padrao`), para que o mesmo dado tenha a mesma aparência em qualquer tela. `mod_intranet` é o módulo base: os demais módulos `mod_*` devem importar os componentes daqui em vez de criar `ui.button` crus ou repetir hexes soltos — hoje são 41 ocorrências dos hexes semânticos `#C62828`/`#EF6C00`/`#2E7D32` e 136 `ui.button(...)` diretos nos módulos de negócio.

| Símbolo | Uso |
|:---|:---|
| `CORES` (`ui_comum.py:37`) | paleta semântica única: `primaria`, `sucesso`, `alerta`, `perigo`, `info`, `neutro`, `destaque`, `cinza_escuro`, `titulo`, `branco` |
| `botao(...)` (`ui_comum.py:52`) | fábrica única de botões — variantes `primario` (alias `solido`), `secundario` (alias `contorno`), `texto`, `neutro`, `restaurar`, `restaurar_fill`, `perigo`, `icone`; parâmetros `icone`, `on_click`, `tooltip`, `cor` (override), `chave_modulo`, `extra_classes`, `compacto`, `no_caps` (default `True`; `False` remove o token `no-caps` das props — botões UPPERCASE herdados do Quasar) |
| `botao_icone(...)` (`ui_comum.py:153`) | ação de linha de tabela (`flat round dense size=sm`) |
| `dialogo_card(...)` (`ui_comum.py:176`) | context manager `ui.dialog` + `ui.card` com estilo do tema; faz `yield (dlg, card)` |
| `rodape_dialogo(dlg, acoes)` (`ui_comum.py:204`) | rodapé de diálogo: "Cancelar" + ações compactas `(rotulo, on_click[, kwargs])` alinhadas à direita |
| `rodape_salvar_restaurar(...)` (`ui_comum.py:231`) | rodapé dos cupês de aparência/módulo (já padrão via `tema_modulo`) |
| `campo_texto(rotulo, valor=None, *, ..., senha=False, placeholder=None)` (`ui_comum.py:314`) | campo de texto padronizado (`ui.textarea` quando `multiline`, senão `ui.input`; props `outlined dense`, classes `w-full`, tooltip, `ao_mudar`, valor opcional de `tb_config` via `chave`/`padrao`). `senha=True` cria o input com `password=True, password_toggle_button=True` (campo de senha com botão exibir/ocultar; sem efeito com `multiline`); `placeholder` é repassado ao construtor quando informado; **sem valor resolvido (`valor=None` sem `chave`) o kwarg `value` NÃO é repassado** — réplica crua byte-idêntica (`ui.input` sem `value` usa `''`, não `None`) |
| `campo_selecao(rotulo, opcoes, valor=None, *, ..., tooltip=None)` (`ui_comum.py:374`) | campo de seleção padronizado (`ui.select(opcoes, label=rotulo, value=valor_resolvido)`; props `outlined dense`, classes `w-full`, `ao_mudar`, valor opcional de `tb_config` via `chave`/`padrao`); `tooltip` só quando informado |
| `notificar` | reexportado de `tema_modulo` (toast com tempo configurável) |

Regras:

- **Fonte única das variantes é `ui_comum.botao`**: `tema_modulo.botao()` (`tema_modulo.py:128`) e `_botao_padrao` (`tela_configuracoes.py:78`) são delegações — não crie uma terceira fábrica.
- Variantes de tema (`primario`/`secundario`/`icone`) leem as chaves `<prefixo>_cor_botao`/`cor_texto_botao`/`btn_tamanho` (valem sem restart); **chave vazia = padrão do PRÓPRIO módulo** (`PADROES_TEMA` — o tema do sistema `intranet_*` NÃO é herdado; detalhes e precedência em [Configurabilidade](#configurabilidade-regra-de-projeto)); variantes semânticas (`restaurar`, `restaurar_fill`, `perigo`, `neutro`) são fixas.
- `cor=` sobrescreve a cor da variante mantendo formato/tamanho; `compacto=True` produz o visual de rodapé de diálogo (sem `size=md`, `btn_cls` e sombra); `no_caps=False` remove o token `no-caps` das props da variante (default `True` — saída byte-idêntica), preservando o caixa-alto (UPPERCASE) dos módulos que o herdaram do Quasar.
- **Fail-soft**: variante inválida levanta `ValueError` (erro de programação — falha rápida intencional); falha de tema/BD cai nos padrões com registro loguru (`_log()` → `observabilidade.get_logger("intranet")`) e a renderização nunca derruba a tela.

#### Como migrar um módulo para `ui_comum`

1. **Importe** do núcleo: `from mod_intranet import ui_comum` (ou símbolos específicos: `botao`, `botao_icone`, `dialogo_card`, `rodape_dialogo`, `rodape_salvar_restaurar`, `CORES`, `notificar`).
2. **Botões**: troque `ui.button("Salvar", on_click=...).props("unelevated no-caps")...` por `ui_comum.botao("Salvar", on_click=...)` (primário do tema) ou escolha a semântica — `ui_comum.botao("Excluir", variante="perigo", ...)`. Módulo com botões UPPERCASE legados do Quasar: passe `no_caps=False` para manter o caixa-alto (o edit_pdf padronizou TODOS os botões em `primario` sem `no_caps` em 06/09 — sem exceções). Ações de linha: `ui_comum.botao_icone("delete", on_click=..., tooltip="Excluir")`.
3. **Cores**: substitua hexes soltos por `ui_comum.CORES["perigo"]`, `CORES["alerta"]`, `CORES["sucesso"]` etc.
4. **Diálogos**: troque `with ui.dialog() as dlg, ui.card() as card: ...` por `with ui_comum.dialogo_card("Título") as (dlg, card): ...` e feche com `ui_comum.rodape_dialogo(dlg, [("Salvar", salvar)])`.
5. **Rodapés de cupê admin**: use `ui_comum.rodape_salvar_restaurar(salvar, restaurar)` — ou simplesmente `tema_modulo.bloco_aparencia`, que já o usa. **Campos de texto/seleção**: troque `ui.input`/`ui.select` crus por `ui_comum.campo_texto(...)`/`ui_comum.campo_selecao(...)` (senhas com `senha=True`; `placeholder`/`tooltip` opcionais). O cupê "Edição do módulo" (`tema_modulo.campo_modulo`) foi **restaurado em 06/09** após remoção acidental — os 6 módulos de negócio voltam a usá-lo na aba Administração (a edição também permanece disponível no painel central `/configuracoes`).
6. **Avisos**: use `ui_comum.notificar(...)` em vez de `ui.notify` cru.
7. **Telas**: troque `ui.tabs()`/`ui.tab()` crus por `aba_modulo.menu_modulo(...)`, inputs de busca crus por `aba_modulo.campo_busca(...)` e barras de ações por `aba_modulo.barra_acoes(...)` (ver tabela acima).

!!! tip "Migração gradual e por tela"
    O visual é idêntico (comprovado por prova byte-a-byte em `test/verifica_ui_comum.py` — **187 verificações** — e suítes de teste; ver [Análise do Núcleo](analise_mod_intranet.md)), então cada `ui.button` substituído não muda a aparência: só elimina duplicação. Migre um arquivo por vez e valide com `ast.parse` + suítes.

#### Helpers de tela padronizados — `mod_intranet/aba_modulo.py`

Além da fábrica de botões, o núcleo padroniza os **componentes de tela** repetidos entre os módulos em `mod_intranet/aba_modulo.py` — não recrie `ui.tabs`/`ui.input` crus:

| Símbolo | Uso |
|:---|:---|
| `cabecalho(titulo, subtitulo="", cor_borda=None, cor_titulo=None, cor_fundo=None, *, chave_modulo=None)` (`aba_modulo.py:33`) | card de cabeçalho do módulo (título + subtítulo opcional, aceita HTML como `<code>`); com `chave_modulo` as cores vêm do tema do módulo (`tema_modulo.ler_tema`) — **a cor de destaque da borda esquerda é a MESMA cor geral do módulo** (`<prefixo>_cor_botao`, vazia = padrão do próprio módulo via `PADROES_TEMA`, editável no cupê Aparência, campo "Cor geral do módulo"); `cor_titulo`/`cor_fundo` idem; parâmetros explícitos vencem o tema (retrocompatível); sem chave → defaults `ui_comum.CORES` (byte-idêntico); `cor_fundo` vazio/`""` = herda (não pinta o `.q-page`); falha ao ler tema → warning loguru + defaults (fail-soft) |
| `menu_modulo(itens, valor=None)` (`aba_modulo.py:102`) | barra de abas de menu do módulo (padrão Renomeador de Empenhos): `ui.tabs` `w-full` com `ui.tab` posicional `(chave, rotulo, icone)` — ícone em cima, nome embaixo; `valor=None` ativa o 1º item; retorna o `ui.tabs` para `ui.tab_panels` |
| `campo_busca(placeholder, on_change=None, *, valor_inicial="", tooltip=None)` (`aba_modulo.py:120`) | campo de pesquisa padrão (padrão Gestão de Usuários): props `outlined dense clearable debounce='150'` + classes `w-full grow min-w-[220px]`; `tooltip` só quando informado |
| `barra_acoes(busca=None, acoes=())` (`aba_modulo.py:137`) | barra branca (`bg-white rounded-lg shadow-sm px-3 py-1`): com `busca` (dict de kwargs de `campo_busca`) o campo fica à esquerda e os botões à direita; sem `busca`, botões alinhados à direita. `acoes` = tuplas `(rotulo, icone, on_click[, tooltip])` viram `ui_comum.botao` variante `primario` com `extra_classes="shrink-0"`; itens malformados ignorados com loguru (fail-soft) |
| `abas(...)` (`aba_modulo.py:82`) | barra principal + "Administração"/"Observabilidade" — permanece para os usos atuais (blog, auditoria); para menus de módulo use `menu_modulo` |

**Regra do cabeçalho (06/09): cor de destaque = cor dos botões do módulo.** A borda esquerda do `cabecalho` usa `tema["cor_botao"]` — a mesma chave que colore os botões via `ui_comum.botao(chave_modulo=...)` — garantindo identidade visual única por módulo (título e fundo seguem `cor_titulo`/`cor_fundo` do tema). Módulos migrados (zero `cor_borda="#..."` hardcoded nas telas): renomear_empenho (`chave_modulo="empenhos"` — `mod_renomear_empenho/telas.py:85`), auditoria (`mod_auditoria/telas.py:345`), blog (`mod_blog/telas.py:159`), solicita_impressao (`mod_solicita_impressao/telas.py:49`) e gest_cad_usuario (`mod_gest_cad_usuario/telas.py:97`). Exceção registrada: `mod_edit_pdf` mantém header custom (estrutura diferente — label de admin + cota com `ui.linear_progress`, `mod_edit_pdf/telas.py:610-625`).

Equivalência visual dos helpers e dos pilotos comprovada por `test/verifica_ui_comum.py` (**187 verificações** byte-a-byte).

#### Componentes de dados e tela reutilizáveis — classes do núcleo (06/09)

Em telas e manipuladores novos, importe do núcleo em vez de replicar o boilerplate — `sqlite3` cru, `ui.grid`/`ui.input` crus e closures de campos repetidas estão fora do padrão:

| Símbolo | Uso |
|:---|:---|
| `CrudBase(db_path, modulo, *, foreign_keys=False, synchronous="NORMAL")` (`mod_intranet/crud_base.py:60`) | base CRUD do banco do módulo (WAL + pragmas, fechamento garantido, commit/rollback): `listar`, `obter`, `criar` (→ `lastrowid`), `atualizar`/`excluir` (→ `rowcount`), `executar_muitas`, `criar_tabela` (DDL idempotente) |
| `CrudBase.transacao()` (`mod_intranet/crud_base.py:135`) | context manager de transação atômica multi-instrução (commit no fim; rollback + repasse da exceção em falha) |
| `audit_reg(ator, modulo, acao, alvo="", detalhe="", hash_arquivo=None)` (`mod_intranet/crud_base.py:43`) | auditoria fail-soft das escritas (wrapper de `audit_log`); falha de auditoria não interrompe a operação de negócio |
| `GradeTabela(colunas, ...)` (`mod_intranet/ui_painel.py:30`) | tabela em `ui.grid` padronizada — `colunas` = pares `(rotulo, largura_css)`; `montar(dados, celulas, acoes=None)` com cabeçalho caption, células por linha e coluna de ações |
| `PainelLista(colunas, dados, *, filtrar=None, por_pagina=10, ...)` (`mod_intranet/ui_painel.py:93`) | painel de listagem completo: `campo_busca` + filtro callável + paginação client-side + `GradeTabela`; `dados` é CALLABLE — após CRUD chamar `atualizar()` |
| `FormularioBuilder(...)` (`mod_intranet/ui_form.py:32`) | construtor fluente de formulários (`campo_texto`/`campo_senha`/`campo_selecao`/`campo_numero`/`campo_data`); `build()` monta num column `w-full gap-2`; leitura por `valores()`/`valor()`/`elemento()` |
| `ui_comum.Dialogo(...)` (`mod_intranet/ui_comum.py:224`) | diálogo temático como context manager (alternativa orientada a objetos ao `dialogo_card`; expõe `abrir()`/`fechar()`; pilotado em `tela_configuracoes.confirmar` — `tela_configuracoes.py:154-160`) |

## PostgreSQL opcional (08/09)

Servidores simples seguem com **SQLite** (padrão universal, zero dependências extras); demandas maiores ativam PostgreSQL **pelo admin, sem tocar em código** (suporte **ativo** desde 08/09 — não é mais fase futura):

- **Backend duplo controlado pelo sistema**: `banco_tipo` = `sqlite` (padrão) \| `postgres` e `postgres_url` (DSN) na `tb_config` central. No Postgres, **um SCHEMA por módulo** no banco `intranet` preserva o isolamento (ver [Backend duplo](arquitetura.md#arquitetura-de-acesso-a-dados-do-nucleo-backend-duplo-0809)).
- **Seletor no boot**: `banco_tipo`/`postgres_url` são lidos **DIRETO do arquivo SQLite central** (`_ler_config_sqlite` — `banco_conexao.py:57`), autoritativo no boot, sem recursão.
- **Toggle no admin**: `/configuracoes` → card **"Banco de dados — SQLite ou PostgreSQL"** (ícone `storage`) → `salvar_backend()` (`banco_conexao.py:128`); **reiniciar o servidor** para aplicar.
- **Camada única**: todos os módulos conectam via `banco_conexao.conexao(chave)` — sqlite (arquivo, WAL) ou postgres (proxy psycopg2 com tradução `?`→`%s`, DDL, `INSERT OR IGNORE/REPLACE`→`ON CONFLICT`, `PRAGMA`/`sqlite_master`/FTS5 degradados, `lastrowid` via `RETURNING`); `repositorio.engine/sessaodb` roteiam para o Postgres quando ativo; `CrudBase._conectar` também roteia pelo backend ativo.
- **Container pronto**: `assets/docker/postgres/docker-compose.yml` — `postgres:16-alpine`, usuário/senha/base `intranet`, porta `5432`, volume persistente, healthcheck.
- **Dependências**: `requirements.txt` — `sqlalchemy>=2.0` e `psycopg2-binary>=2.9` habilitadas (instalar para usar `banco_tipo='postgres'`).
- **Migração de dados SQLite→PostgreSQL permanece manual** — o Postgres inicia com os schemas vazios, recriados pelos `init_db` dos módulos; os bancos SQLite existentes não são movidos automaticamente.

## Configurabilidade (regra de projeto)

**Toda e qualquer configuração passável de alteração** (cores, padrões, tamanhos, tempos, pastas, textos…) deve ser pensada como **configurável pelo usuário** na área de configuração do módulo — chaves em `tb_config` (prefixo `<modulo>_*`) + cupê "Administração" do próprio módulo (ou o painel central `/configuracoes`) — e aplicada **sem restart** sempre que possível. Não fixe em código valores que o administrador possa querer ajustar.

- Chaves de aparência por módulo: `<chave>_cor_botao`, `cor_texto_botao`, `cor_fundo`, `cor_titulo`, `btn_tamanho`, `texto_header` (lidas por `tema_modulo.ler_tema`, valem sem restart).
- **Padrão próprio do tema de BOTÕES (06/09)**: chave do módulo **VAZIA = padrão do PRÓPRIO módulo** — o tema do sistema (`intranet_*`) **NÃO é herdado**. Precedência para `cor_botao`, `cor_texto_botao` e `btn_tamanho` (`tema_modulo.py:94-126`):

  1. Chave do módulo (`<prefixo>_cor_botao` etc.) **não vazia** → usa o valor do módulo;
  2. Default do parâmetro em `ler_tema` (quando o chamador informa);
  3. Padrão do módulo — mapa `PADROES_TEMA` (`tema_modulo.py:53-68`): **TODOS os módulos em `#000000`** — blog, usuarios, auditoria, editar_pdf, empenhos, solicita_impressao e intranet (a cor do intranet; texto `#FFFFFF`, título `#212121`, tamanho `medium`).

  `cor_fundo`, `cor_titulo` e `texto_header` seguem a mesma regra (vazio = default do parâmetro). Com isso, **todos os módulos usam a cor do intranet (`#000000`)** por padrão; o override por módulo continua possível no cupê "Aparência" da Administração de cada módulo — os inputs exibem o valor **resolvido** (rótulo "vazio = padrão do módulo"), e o "Restaurar padrão" grava `""` para voltar ao padrão do módulo. O card "Botões do sistema" (`intranet_*`) vale apenas para o próprio módulo `intranet`.
- Config específica de comportamento: `usuarios_senha_min`, `empenhos_pasta_monitorada`, `blog_tags_permitidas`, `log_*`, `smtp_*`, `backup_horas:<modulo>` etc.
- **Exemplo vivo (05/09)**: o botão "Novo usuário" da Gestão de Usuários deixou de usar `color=primary` (cor da página) e passou a `ui_comum.botao(chave_modulo="usuarios")` — a cor segue o tema do módulo (`usuarios_cor_botao`) e, com a chave vazia (padrão), usa o padrão do PRÓPRIO módulo (`PADROES_TEMA["usuarios"]` = `#000000`), ajustável pelo admin na aba Administração (`mod_gest_cad_usuario/telas.py:110-112`).

!!! tip "Como decidir"
    Antes de escrever um literal no código (hex, tamanho, tempo, texto, caminho), pergunte: "o administrador pode querer mudar isto?" Se sim → chave em `tb_config` + campo no cupê Administração do módulo, lida a cada render (sem restart).

## Auditoria e versionamento

- **Auditoria**: toda ação relevante (criar/editar/excluir/publicar/imprimir/autorizar/configurar/renomear) grava `audit_log(usuario, modulo, acao, descricao, hash_arquivo=None)` — `mod_intranet/bd_manipulador.py:70`; nos módulos prefira o wrapper `audit_reg(ator, modulo, acao, alvo, ...)` (`mod_intranet/crud_base.py:43`, fail-soft). A gravação é desacoplada por gancho: `registrar_hook_auditoria(fn)` (`bd_manipulador.py:26`) é chamado pelo `mod_auditoria` no import (`mod_auditoria/db_manipulador.py:376-377`) — sem dependência cíclica núcleo↔auditoria.
- **Hash SHA-256** em operações com arquivos (editor PDF, empenhos, impressão).
- **Versionamento**: `1.0.AAMMDD`; versão global `versao_sistema` + por módulo `versao_modulo:<chave>` (exibidos da esquerda para a direita no rodapé). Atualize a chave do módulo quando alterar código dele — sem mexer na global nem nas dos outros.

## Checklist de aceite

- [ ] `telas.py` expõe `mostrar_tela(usuario_logado, perfil)` com gate de permissão.
- [ ] `bd_manipulador.py` tem `init_db*()` com WAL; bootstrap atualizado em `inicializar_bancos()`.
- [ ] Módulo registrado em `MODULOS_SISTEMA` + rota no `main.py` com `pagina_restrita(título, chave_modulo="<chave>")`.
- [ ] `versao_modulo:<chave>` semeada e log rotulado com `get_logger("<modulo>")`.
- [ ] Auditoria em todas as escritas; hash SHA-256 em operações com arquivos.
- [ ] `ast.parse` passou em todos os arquivos alterados.
- [ ] Valores ajustáveis (cores, tempos, textos, pastas…) em `tb_config` + cupê Administração — nada de literais hardcoded (ver [Configurabilidade](#configurabilidade-regra-de-projeto)).
- [ ] Componentes de UI via `mod_intranet/ui_comum` (`botao`/`botao_icone`/`CORES`/`dialogo_card`/`rodape_dialogo`/`notificar`) — sem `ui.button` cru nem hexes soltos; botões UPPERCASE legados do Quasar usam `no_caps=False` (o edit_pdf padronizou todos em `primario` sem `no_caps` em 06/09 — sem exceções cruas).
- [ ] Acesso a dados via `CrudBase` + `audit_reg` (nunca `sqlite3` cru em código novo); telas novas usam `FormularioBuilder`/`GradeTabela`/`PainelLista` do núcleo em vez de replicar grids/inputs crus.
- [ ] Código de teste gravado em `test/` (nunca em `/tmp` — se perde ao reiniciar a máquina).
- [ ] Suíte validada com `.venv/bin/pytest` (suíte completa via runner `assets/test/test_suite.py`, ≈3–5 min) — scripts standalone nunca coletados diretamente pelo pytest (o `pytest.ini` limita a coleta ao runner).
- [ ] No `mkdocs.yml`, documentação do módulo adicionada ao `nav` (se houver).

> Convenções documentadas também em [Padrões de Codificação](padroes_codificacao/index.md) — este documento é a referência oficial unificada.