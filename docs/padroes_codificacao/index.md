# Coding Standards — Intranet Modular

> Mandatory coding standards, derived from the actual codebase (function-based, `snake_case`, module packages `mod_*`). Mirror an existing module when in doubt.

---

# Padrões de Codificação — Intranet Modular

> Padrões obrigatórios de codificação, extraídos do código real (funcional, `snake_case`, pacotes `mod_*`). Em dúvida, espelhe um módulo existente.

## 1. Nomenclatura

- **`snake_case`** para funções, variáveis e nomes de arquivo Python. Ex.: `autenticar` (`:179`), `gerar_hash_senha` (`:161`), `bd_criador.py`.
- **Não use `camelCase`** para funções/variáveis Python.
- Constantes em **`MAIUSCULAS_SNAKE`**.
- Pacote de módulo: **`mod_<nome>`** (minúsculas, underscore). Arquivos: **`mod_<nome>_<descricao>.py`**.
- Tabelas: **`tb_<nome>`**; colunas: `snake_case` com prefixo semântico (`user_nome`, `hash_arquivo`).

## 2. Estilo

- Projeto **funcional/procedural** nas regras de negócio — prefira funções puras; classes ficam restritas aos **componentes reutilizáveis do núcleo** (`mod_intranet`: `CrudBase`, `GradeTabela`/`PainelLista`, `FormularioBuilder`, classes de `ui_comum` — 06/09). Nos módulos `mod_*`, não crie classes de negócio.
- `telas.py` **DEVE** expor `mostrar_tela(nome, perfil)`.
- Sem comentários a menos que solicitado (regra `../../AGENTSadf.md`).
- Valide com: `.venv/bin/python -c "import ast; ast.parse(open('<arquivo>', encoding='utf-8').read())"`.

## 3. Modelo de novo módulo

```
mod_exemplo/
  __init__.py
  telas.py            # mostrar_tela(nome, perfil)  — abas de negócio
  administracao.py    # mostrar_administracao(...)  — painel admin standalone
  manipulador_bd.py   # acesso ao db_mod_exemplo.db (WAL)
  criador_bd.py       # legado/morto — não confiar
```
- Banco próprio criado por `inicializar_bancos()`; toda escrita relevante registra na trilha de auditoria via `audit_log` (banco exclusivo `db_mod_auditoria.db`, tabela `tb_auditoria_<modulo>`).
- Registre o módulo em `tb_modulos` (`autenticacao.registrar_modulo`).
- **Painel admin em arquivo dedicado (`telas_administracao.py`)** — desde 06/09, cada módulo expõe `mostrar_administracao(...)` em `mod_<nome>/administracao.py`, isolado do `telas.py` e sem tabs de navegação. A rota `main.py:439` (`@ui.page("/admin/{chave_modulo}")`) faz o dispatch e chama o `mostrar_administracao` correspondente. Isso permite: (1) admin abrir direto pela URL `/admin/blog` etc., (2) o admin do módulo ser **standalone** (não depende do estado das telas de negócio) e (3) o cupê "Administração" do drawer ser contextual por módulo. O arquivo recebe como parâmetro o ator/flags de permissão e o que precisar de tema/BD; toda a lógica de configuração (aparência, cotas, textos, regex, pastas monitoradas, Quarentena, etc.) vive nele.

## 4. Tela (NiceGUI)

- Funções que recebem `(nome, perfil)`; sem JavaScript direto.
- Respeite o layout de 4 partes; valide o papel do ator antes de qualquer escrita.
- Conteúdo HTML do Blog passa obrigatoriamente por `nh3`.

## 5. Banco

### 5.1 `CrudBase` — camada de acesso legado

`db_manipulador.py` concentra acesso; **nunca cross-query** entre bancos.
Toda conexão aplica `PRAGMA journal_mode=WAL`.
**Use `CrudBase` (`mod_intranet/crud_base.py`) — nunca `sqlite3` cru** (06/09): conexão WAL/synchronous/foreign_keys padronizada, atalhos `listar`/`obter`/`criar`/`atualizar`/`excluir`/`executar_muitas`/`criar_tabela` e transação atômica `crud.transacao()` (commit/rollback); auditoria das escritas via `audit_reg` (wrapper fail-soft de `audit_log`). Piloto: `../../mod_blog/bd_manipulador.py` 100% migrado.

### 5.2 SQLAlchemy ORM + Dataclasses — padrão novo (piloto: `mod_intranet`, 07/09)

O `mod_intranet` usa **SQLAlchemy 2.0 ORM + Dataclasses** como arquitetura piloto, propagável aos demais módulos. Estrutura:

```
mod_intranet/
  models/
    __init__.py   # Table metadata + dataclass + map_imperatively()
  repositorio.py  # Classe Repositorio (CRUD tipado via Session ORM)
  conexao_bd.py  # get_config/set_config delegam para Repositorio
```

**Criando models de um novo módulo:**

1. `models/__init__.py` — defina `Table` e dataclass, mapeie com `registry.map_imperatively()`:

```python
from sqlalchemy import Table, Column, Integer, String
from dataclasses import dataclass
from mod_intranet.models import metadata

tb_postagens = Table("tb_postagens", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("titulo", String(255), nullable=False),
    Column("conteudo", String, nullable=False),
    Column("ativo", Integer, default=1),
)

@dataclass
class Postagem:
    id: Optional[int] = None
    titulo: str = ""
    conteudo: str = ""
    ativo: int = 1

from sqlalchemy.orm import registry
registry().map_imperatively(Postagem, tb_postagens)
```

2. `repositorio.py` — crie `Repositorio` local vinculado ao banco do módulo:

```python
from mod_intranet.repositorio import Repositorio
from .models import Postagem

class RepositorioBlog(Repositorio):
    def __init__(self, sessao=None):
        super().__init__(sessao, chave_db="blog")  # banco do módulo

    def listar_ativas(self) -> list[Postagem]:
        if self.sessoes is None:
            return []
        return self.sessoes.query(Postagem).filter_by(ativo=1).all()
```

3. `db_manipulador.py` — use `RepositorioBlog` em vez de `CrudBase`:

```python
from .repositorio import RepositorioBlog
_repo = RepositorioBlog()
```

4. `autenticacao.py`/`db_manipulador.py` — use `Repositorio`:

```python
from mod_intranet.repositorio import Repositorio
with Repositorio() as repo:
    mods = repo.listar_modulos()
    repo.definir_config("minha_chave", "valor")
```

**Regras:**
- `Repositorio` é context manager (`with Repositorio() as repo`); fecha a sessão no `__exit__`.
- Fail-soft: métodos retornam `padrao`/`False`/`[]` em vez de lançar exceção.
- Se SQLAlchemy não estiver instalado, `engine()` retorna `None` e `Repositorio` opera em modo degradado.
- `get_config`/`set_config` em `bd_conexao.py` já delegam para `Repositorio` automaticamente.
- **Multi-banco:** `engine(chave)`/`sessaodb(chave)`/`Repositorio(chave_db=...)` operam em qualquer banco de `MODULOS_BD` (7 bancos); chave desconhecida cai no central. Helpers genéricos `consultar`/`executar`/`ultimo_id` migram SQL cru gradualmente.
- **Criação condicional:** `create_all` + log só quando o arquivo do banco não existe; módulos ≠ intranet nunca rodam `create_all` (schema via `init_db` do módulo, garantido por `garantir_bancos()` no passo 0 do boot).
- **Não use `mapper()`** (removido em SQLAlchemy 2.0) — use `registry().map_imperatively()`.
- Credential pattern: `postgres_url(como_admin=False)` usa `klayton/klayton`; `postgres_url(como_admin=True)` usa `master/master` (chaves `banco_usuario`/`banco_senha`/`banco_admin_usuario`/`banco_admin_senha` em `tb_config`).

Soft delete para entidades sensíveis, com coluna de motivo e auditoria.

## 6. Versionamento

- Padrão `1.0.AAMMDD` (major.menor.data) — ver [Versionamento](../versionamento/index.md).

## 7. Padrões aplicados no módulo `mod_renomear_empenho` (exemplo vivo)

> O módulo Renomeador de Empenho é referência concreta das convenções abaixo.

- **Duas camadas por módulo** (`db_manipulador.py` + `telas.py`), com `mostrar_tela(usuario_logado, perfil)` obrigatório (`telas.py:45`).
- **Banco WAL próprio** (`db_mod_<nome>.db`) com `CREATOR` idempotente (`CREATE TABLE IF NOT EXISTS` + seeds condicionais) e **migração de coluna** para bancos antigos (`_migrar_coluna`, `manipulador_bd.py:278`).
- **Tabelas `tb_<nome>`**, colunas `snake_case` com prefixo semântico (`nome_arquivo_final`, `tipo_especial`, `motivo_recusa`).
- **Trilha de auditoria por arquivo** (hash SHA-256) no próprio banco do módulo + `audit_log` central com hash — ver `tb_arquivos_auditoria`/`tb_eventos_arquivos`.
- **Perfil por aba**: calcula `eh_admin = perfil == "administrador_geral" or eh_admin_do_modulo(usuario, "<chave>")` e restringe abas/funções a admin; valida o papel antes de qualquer escrita.
- **Configurações via `tb_config`** (chaves `empenhos_*`) lidas/aplicadas **sem reiniciar** — ver [Configurações](../configuracoes.md).
- **Tabs via helpers do núcleo**: use `aba_modulo.menu_modulo(...)` para menus de módulo (ícone em cima, nome embaixo — padrão Renomeador de Empenhos, `telas.py:89`) e `aba_modulo.abas(...)` para principal + "Administração" (blog/auditoria); `ui.tabs` cru apenas em casos especiais (ex.: `mod_solicita_impressao`).
- **Segurança de caminho**: normaliza com `os.path.realpath` e mantém lista de **raízes protegidas** (`raizes_navegacao`/`pasta_navegavel`) para anti-travessia; evita `..` em navegação.
- **Idempotência/não-reprocessamento**: decide por nome padronizado e/ou registro no banco (`_arquivo_registrado_no_bd`).
- **Anti-colisão** ao gerar destinos: sufixa (`_v2`, `_v3`) em vez de sobrescrever.
- **Regex configuráveis** centralizadas em constantes/tabela (não espalhadas) com validação `re.compile` antes de persistir.
- **Import side-effect control**: o módulo dispara `init_db_empenho()` na importação; por isso `inicializar_bancos()` deve rodar antes (ordem de import importa — ver `../../AGENTSadf.md`).
- **Sem classes de negócio/ORM**; funções puras `snake_case`; validação de sintaxe via `ast.parse`.

> Regra de ouro: ao criar ou alterar um módulo, espelhe `mod_renomear_empenho`/`mod_solicita_impressao` e valide com `ast.parse` antes de submeter.

## 8. Componentes de UI padronizados (`mod_intranet/ui_comum.py`)

- **Fonte única de botões, diálogos e rodapés**: importe de `mod_intranet.ui_comum` — `botao()` (variantes `primario`/`secundario` (aliases `solido`/`contorno`)/`texto`/`neutro`/`restaurar`/`restaurar_fill`/`perigo`/`icone`), `botao_icone()`, `dialogo_card()`, `rodape_dialogo()`, `rodape_salvar_restaurar()`, paleta `CORES` e `notificar` (reexportado de `tema_modulo`).
- **Nada de `ui.button` cru nem hex solto** (`#C62828`, `#EF6C00`, `#2E7D32`…): use `botao(variante=...)` e `CORES[...]`. `tema_modulo.botao()` e `_botao_padrao` (`tela_configuracoes.py`) apenas delegam à fábrica central.
- **Migração de botões CONCLUÍDA nos módulos (06/09)**: ~120 botões crus (`ui.button`) migrados para `ui_comum.botao/botao_icone(chave_modulo=...)` em 12 arquivos — `mod_auditoria` (telas+admin), `mod_edit_pdf` (telas), `mod_gest_cad_usuario` (telas), `mod_renomear_empenho` (telas+admin), `mod_solicita_impressao` (telas+admin). Efeito: ao alterar cor/tamanho dos botões do módulo na administração (`<prefixo>_cor_botao`/`cor_texto_botao`/`btn_tamanho`), a cor aplica em TODOS os botões do módulo (a fábrica lê o tema a cada render). Mapeamento de variantes: `unelevated`→`"solido"`; `flat`→`"texto"`; `outline`→`"contorno"`; ícone `round/dense`→`botao_icone`; ações destrutivas→`"perigo"` ou `cor="negative"`; "Restaurar padrão"→`"restaurar"`; verde→`texto` com `cor="green-8"`; laranja→`cor="orange-9"`; Resetar cota (solicita_impressao)→`"restaurar_fill"` (família restaurar).
- **Exceções INTENCIONAIS de `ui.button` cru** (documentadas como tais): `ui_comum.py:163` (a própria fábrica), `ui_comum.py:326` (Cancelar de `rodape_dialogo` — padrão de diálogo) e `tela_configuracoes.py:493,497` (preview AO VIVO da aba Cores — usa valores não salvos dos campos).
- **`rodape_salvar_restaurar` na fábrica (06/09)** (`ui_comum.py:338`): "Restaurar padrão" usa a variante `restaurar` (antes `flat` cinza) e o botão de salvar usa `solido` do tema do módulo — ambos via `botao(chave_modulo=...)`. "Restaurar padrão" tem aparência ÚNICA no projeto (contorno âmbar), inclusive nos sites que usavam contorno/primário em empenhos e edit_pdf. Contraste WCAG: a variante `restaurar` usa `text-color=amber-10` (escurecida de `amber-9`, ~3,8:1 em card branco — melhora o AA do anterior ~2,2:1). **Padrão de 2 botões por card (06/09)**: o rótulo padrão do salvar é **"Aplicar"** (antes "Salvar") — grava EXCLUSIVAMENTE o card em questão; novo parâmetro `acoes_extra` aceita tuplas `(rotulo, icone, on_click[, tooltip[, variante]])` (variante default `solido`) renderizadas antes do "Restaurar padrão"; a row usa `flex-wrap` (responsividade mobile).
- **Painéis de administração no padrão `card_admin` (06/09)** (`ui_comum.py:781`): `ui.card` w-full com borda esquerda temática (cor_botao do módulo, fallback `#607D8B`) + fundo `estilo_cartao`; dentro, `ui.expansion` como cabeçalho retrátil — **o título do card é colorido com a cor de título do módulo** (`<prefixo>_cor_titulo` via `ler_tema`, fail-soft → `#212121`) via `header-style`; `grade=True` (padrão) cria a grade responsiva do projeto (1 campo/linha em tela pequena, 2 em média `sm:`, 3 em grande `md:`) e o `with` do chamador entra na grade; `grade=False` para conteúdo livre (tabelas/textareas). Aplicado em: blog (2 seções), auditoria, empenhos (8 seções, `grade=False`), `tema_modulo.bloco_aparencia` (card_admin próprio; `com_card=False` para callers que já têm card: gest_cad_usuario, edit_pdf, solicita_impressao admin + telas).
- **Fail-soft obrigatório**: falha de tema/BD cai nos padrões com registro loguru (`observabilidade.get_logger("intranet")`); variante inválida levanta `ValueError` (erro de programação — falha rápida).
- **Helpers de tela em `mod_intranet/aba_modulo.py`**: `cabecalho(titulo, subtitulo, ..., chave_modulo=None)` (card de cabeçalho com cores resolvidas pelo tema do módulo — **a borda de destaque é a MESMA cor dos botões do módulo**, `<prefixo>_cor_botao`; parâmetros explícitos vencem; sem chave → defaults `ui_comum.CORES`), `menu_modulo(itens, valor=None)` (abas de menu com ícone em cima/nome embaixo), `campo_busca(placeholder, on_change, valor_inicial, tooltip)` (`outlined dense clearable debounce='150'`) e `barra_acoes(busca, acoes)` (barra branca com busca à esquerda e botões `ui_comum.botao` primários à direita; itens malformados ignorados com loguru). Não recrie `ui.tabs`/`ui.input` crus.
- **Classes do núcleo em telas novas (06/09)**: em vez de `ui.grid`/`ui.input`/`ui.button` crus, use os componentes padronizados — `GradeTabela` (`ui_painel.py:30`, grid com cabeçalho caption + células + coluna de ações), `PainelLista` (`ui_painel.py:93`, busca + filtro + paginação client-side + `atualizar()`) e `FormularioBuilder` (`ui_form.py:32`, construtor fluente com `build()`/`valores()`). `ui_comum.py` é orientado a classes internamente (`BotaoFabrica`/`Dialogo`/`Cartao`/`CampoBase`) — as funções `botao`/`dialogo_card`/`campo_*` permanecem como wrappers finos; ambos os estilos são aceitos, comportamento idêntico.
- **Equivalência comprovada**: `test/verifica_ui_comum.py` (**188 verificações** byte-a-byte, stub de nicegui, tema fixado via monkeypatch sem tocar no banco — inclui checks de migração dos botões dos módulos: perigo/solido/botao_icone, rodapé e variante restaurar) e `test/teste_classes_crud.py` (**68 verificações** — CrudBase em SQLite real, gancho de auditoria, `banco_conexao`, equivalência wrapper↔classe, GradeTabela/PainelLista/FormularioBuilder) — TODO código de teste fica em `test/`, nunca em `/tmp`.

## 9. Configurabilidade (regra de projeto)

- **Toda e qualquer configuração passível de alteração** (cores, padrões, tamanhos, tempos, pastas, textos…) deve ser **configurável pelo usuário** na área de configuração do módulo: chaves em `tb_config` (prefixo `<modulo>_*`) + cupê "Administração" do módulo / painel central `/configuracoes`, aplicando **sem restart** sempre que possível. Não fixe em código valores que o administrador possa querer ajustar.
- **Tema de botões por módulo — vazio = padrão do módulo (06/09)**: chave de botão do módulo **VAZIA** (`<prefixo>_cor_botao`/`cor_texto_botao`/`btn_tamanho`) = **padrão do módulo** — precedência em `tema_modulo.ler_tema` (`tema_modulo.py:94-126`): (1) chave do módulo não vazia → (2) default do parâmetro → (3) `PADROES_TEMA` (mapa único com **TODOS os módulos em `#000000`** — blog, usuarios, auditoria, editar_pdf, empenhos, solicita_impressao, intranet; a cor do intranet). O tema do sistema (`intranet_*`, card "Botões do sistema" em `/configuracoes`) **NÃO é herdado** por outros módulos; `cor_fundo`/`cor_titulo`/`texto_header` seguem a mesma regra. Para voltar ao padrão, "Restaurar padrão" grava `""` (detalhes em [Configurações](../configuracoes.md)).
- **Card padrão "Configurações de cores" — `bloco_aparencia` (06/09)** (`tema_modulo.py:297-483`): todo módulo deve expor o card PADRÃO **"Configurações de cores"** via `tema_modulo.bloco_aparencia(usuario_logado, chave_modulo, tema, ...)` — card recolhível `card_admin` (`aberto=False`) com **PRÉVIA AO VIVO** (exemplo de cabeçalho/card/botões que atualiza a cada troca de cor) e os campos no padrão do intranet ("Cor geral do módulo", "Cor do texto do módulo", "Cor de fundo da página", "Cor dos títulos", "Cor de fundo dos cards", "Cor do texto dos cards", "Tamanho dos botões" + opcional "Texto do cabeçalho" via `com_texto_header`). Rodapé padrão de 2 botões (Restaurar padrão + Aplicar) recarregando após 1 s; `salvar_tema` grava também `cor_fundo_card`/`cor_texto_card` (`tema_modulo.py:129-153`). `com_card=False` para chamadores que já fornecem o card (evita card dentro de card — ex.: solicita_impressao admin).
- **"Cor geral do módulo" — padrão ÚNICO de tema (06/09)**: a chave `<prefixo>_cor_botao` é chamada de **"Cor geral do módulo"** (rótulo renomeado de "Cor dos botões" em TODOS os painéis — `tema_modulo.bloco_aparencia` `tema_modulo.py:318-323`, aba Cores do sistema `tela_configuracoes.py:517-526`, admins de blog `mod_blog/administracao.py:56`, auditoria `mod_auditoria/administracao.py:111` e empenhos `mod_renomear_empenho/administracao.py:99` + `telas.py:699`) e define a cor dos **botões E dos menus/abas/destaques** da tela do módulo: `ui.colors(primary=cor_botao)` (tinge tabs/menus/Quasar) + `cabecalho(chave_modulo=...)` (borda de destaque) + `ui_comum.botao(chave_modulo=...)` (botões). A cor é aplicada às telas de TODOS os módulos — antes só blog e gest_cad tinham `ui.colors(primary=...)`; agora auditoria (`mod_auditoria/telas.py:126`), edit_pdf (`mod_edit_pdf/telas.py:89`), empenhos (`mod_renomear_empenho/telas.py:65`) e solicita_impressao (`mod_solicita_impressao/telas.py:53`) também aplicam. Nas rotas de admin (`main.py:484-523`) os hexes fixos foram substituídos por `ler_tema(<modulo>, cor_botao=<default>)["cor_botao"]` (auditoria/editar_pdf/solicita_impressao); empenhos usa `empenhos_cor_botao` com default alinhado a `#000000` (antes `#6D4C41`). `ui.color_input`/`ui.select` crus do admin de auditoria e empenhos (admin + telas) migraram para as fábricas `campo_cor`/`campo_selecao` com os novos rótulos. Coberto por `test/teste_aba_config_intranet.py` (164 verificações — rótulos "Cor geral do módulo"/"Cor do texto do módulo").
- Exemplo vivo: o botão "Novo usuário" da Gestão de Usuários obedece ao tema do módulo (`usuarios_cor_botao` via `ui_comum.botao(chave_modulo="usuarios")` — `mod_gest_cad_usuario/telas.py:110`), ajustável na aba Administração; com a chave vazia (padrão), usa o padrão do PRÓPRIO módulo (`PADROES_TEMA["usuarios"]` = `#000000`).
- Detalhes e checklist: [Convenções de Código](../convencoes_codigo.md) → seção "Configurabilidade (regra de projeto)".
- Guia de migração passo a passo ("como migrar um módulo"): [Convenções de Código](../convencoes_codigo.md) → seção "Componentes de UI padronizados".

## 10. PostgreSQL opcional (08/09) — backend duplo ATIVO

- **SQLite segue o padrão universal** (`banco_tipo = 'sqlite'`) — servidores simples não instalam nada extra; todos os módulos operam na camada única `banco_conexao.conexao(chave)`.
- **Backend duplo controlado pelo sistema**: `banco_tipo` = `sqlite`|`postgres` e `postgres_url` (DSN) na `tb_config` central, lidos **DIRETO do arquivo SQLite central** (`_ler_config_sqlite` — seletor de boot). No Postgres, **um SCHEMA por módulo** no banco `intranet` preserva o isolamento.
- **Ativação pelo admin, sem código**: `/configuracoes` → card **"Banco de dados — SQLite ou PostgreSQL"** → `salvar_backend()`; **reiniciar o servidor** para aplicar.
- **Camada única**: `conexao(chave)` (`banco_conexao.py:488`) devolve conexão DBAPI do backend ativo — sqlite (arquivo, WAL) ou postgres (proxy psycopg2 com tradução `?`→`%s`, DDL, `ON CONFLICT`, `PRAGMA`/`sqlite_master`/FTS5 degradados, `lastrowid` via `RETURNING`, SAVEPOINT por statement). `repositorio.engine/sessaodb` roteiam para o Postgres quando ativo; `CrudBase._conectar` também roteia (módulo em `SCHEMAS`).
- **Fail-soft**: sem driver instalado, o sistema segue de pé em SQLite (exception registrada no loguru); DSN nunca logado com credenciais (`_dsn_publico`).
- **Container pronto**: `assets/docker/postgres/docker-compose.yml` (postgres:16-alpine, base `intranet`, porta 5432, volume persistente, healthcheck).
- **Dependências**: `requirements.txt` — `sqlalchemy>=2.0` e `psycopg2-binary>=2.9` habilitadas (instalar para usar `banco_tipo='postgres'`).
- **Migração de dados SQLite→PostgreSQL permanece manual** — o Postgres inicia com os schemas vazios (recriados pelos `init_db`); detalhes em [Configurações](../configuracoes.md).

## 11. Administração do módulo em arquivo dedicado — `telas_administracao.py` (06/09)

- **Padrão**: cada módulo expõe `mostrar_administracao(...)` em `mod_<nome>/administracao.py` — **arquivo separado** do `telas.py`, isolado do estado das telas de negócio, sem tabs de navegação. A rota `@ui.page("/admin/{chave_modulo}")` em `main.py:439` faz o dispatch por `chave_modulo` e chama o `mostrar_administracao` correspondente.
- **Assinatura canônica** (varia por módulo conforme o que precisa renderizar):
  - `../../mod_blog/telas_administracao.py` — `mostrar_administracao(usuario_logado, pode_publicar)` (aparência, tags HTML, largura imagem, gestão de inativos, `campo_modulo`).
  - `../../mod_gest_cad_usuario/telas_administracao.py` — `mostrar_administracao(ator)` (aparência, tamanho mínimo senha, `campo_modulo`).
  - `../../mod_auditoria/telas_administracao.py` — `mostrar_administracao(usuario_logado, eh_admin_geral)` (retenção LGPD, aparência, `campo_modulo`).
  - `../../mod_edit_pdf/telas_administracao.py` — `mostrar_administracao(usuario_logado, eh_admin)` (cotas GB/usuário, lotes, textos, aparência, manutenção).
  - `../../mod_renomear_empenho/telas_administracao.py` — `mostrar_administracao(...)` (pastas, aparência, template, regex, auditoria, Quarentena, regras) — recebe também `t_cor_botao`/`t_cor_texto_botao`/`t_cor_fundo`/`t_cor_titulo`/`t_tamanho`/`texto_header` já resolvidos e os callables `_btn_cls`/`_btn_style` + `get_config`/`set_config`.
  - `../../mod_solicita_impressao/telas_administracao.py` — `mostrar_administracao(usuario_logado, eh_admin)` com **6 sub-abas** (Solicitações, Secretarias, Setores, Responsáveis, Cotas, Config).
- **Botão "Administração" do drawer é contextual** (`layout_tela.py:184-200`): dentro de um módulo, navega para `/admin/{chave_modulo}`; no Home, navega para `/configuracoes`. Tooltip muda conforme o contexto ("Configurações de {nome_modulo}" vs "Configurações gerais do sistema").
- **Por que arquivo separado**:
  1. O admin do módulo fica **standalone** — não depende do estado das abas de negócio (cota, filtros, login refresh, etc.).
  2. Permite URL direta (`/admin/blog`, `/admin/auditoria` etc.) e acesso contextual pelo drawer.
  3. `telas.py` continua focado em fluxo de negócio; `telas_administracao.py` concentra TODA a configuração do módulo.
- **Fail-soft + loguru obrigatórios** (regra geral do projeto): todo `mostrar_administracao` envolve leituras/gravações em `try/except`, registrando via `observabilidade.get_logger("<modulo>")` — `_FMT` do `observabilidade.py` já garante `{module}:{function}:{line}` no log.
- **Migração de admin embutido no `telas.py`**: ao criar um novo módulo, **não** coloque o painel de administração como aba dentro de `mostrar_tela` — extraia para `mod_<nome>/administracao.py` e adicione a entrada correspondente no `dispatch` de `main.py:439-524`. Módulos já migrados (06/09): `blog`, `usuarios`, `auditoria`, `editar_pdf`, `empenhos`, `solicita_impressao`.

## 12. SQLAlchemy ORM + Dataclasses (07/09) — padrão a propagar

O `mod_intranet` é o **módulo piloto** da arquitetura de acesso a dados com SQLAlchemy 2.0 ORM + Dataclasses. Os demais módulos devem migrar seguindo este padrão.

### Estrutura por módulo

```
mod_<nome>/
  models/
    __init__.py    # Table definitions + dataclasses + registry.map_imperatively()
  repositorio.py   # Repositorio local com CRUD tipado via Session
  manipulador_bd.py  # usa Repositorio para todas as operações de BD
  telas.py         # usa Repositorio / CrudBase para acesso a dados
```

### Camadas (de baixo para cima)

1. **`models/__init__.py`** — define `Table` SQLAlchemy e dataclasses:
   - Um `Table` por tabela (`Column` com tipos explícitos).
   - Uma `@dataclass` por tabela com campos correspondentes.
   - `from sqlalchemy.orm import registry` + `map_imperatively()`.
   - `metadata.create_all(engine)` cria as tabelas.

   ```python
   # Exemplo mínimo
   from dataclasses import dataclass
   from typing import Optional
   from sqlalchemy import Table, Column, String, Integer
   from sqlalchemy.orm import registry

   _metadata = MetaData()

   tb_exemplo = Table("tb_exemplo", _metadata,
       Column("id", Integer, primary_key=True, autoincrement=True),
       Column("nome", String(100), nullable=False),
   )

   @dataclass
   class Exemplo:
       id: Optional[int] = None
       nome: str = ""

   _reg = registry()
   _reg.map_imperatively(Exemplo, tb_exemplo)
   ```

2. **`repositorio.py`** — engine POR banco + `Session` factory + classe `Repositorio`:
   - `MODULOS_BD`: mapa chave→arquivo de TODOS os bancos dos módulos (o SQLAlchemy trabalha com todos; o núcleo hospeda o mapa central em `mod_intranet/repositorio.py:57-65`).
   - `caminho_db(chave)`: caminho do banco; chave desconhecida → central (fail-soft).
   - `engine(chave)`: um engine por banco, cacheado por chave (dict + `_lock`); event listener para pragmas WAL/`synchronous`/`foreign_keys`; **criação condicional** — `create_all` + log só quando o ARQUIVO não existe (e só no banco central; módulos recebem o schema via `init_db` próprio).
   - `sessaodb(chave)`: `sessionmaker(bind=engine, expire_on_commit=False)` por banco, factory cacheada.
   - `garantir_bancos()`: percorre `MODULOS_BD` e força a primeira conexão dos bancos ausentes (chamado no passo 0 do boot, antes dos `init_db`).
   - `Repositorio(chave_db="intranet")`: context manager com `fechar()` automático; métodos CRUD fail-soft com loguru; helpers genéricos `consultar`/`executar`/`ultimo_id` para migrar SQL cru gradualmente.
   - Retornar dataclasses (não dicionários nem tuplas) nos métodos tipados.
   - Sempre fazer `session.commit()` após escritas.

   ```python
   def _log():
       from mod_intranet import observabilidade
       return observabilidade.get_logger("intranet")

   def engine(chave: str = "intranet"):
       if chave not in MODULOS_BD:
           chave = "intranet"
       if chave in _engines:
           return _engines[chave]
       with _lock:
           if chave in _engines:
               return _engines[chave]
           path = caminho_db(chave)
           novo_banco = not os.path.exists(path)
           _eng = create_engine(_uri(path), ...)
           @event.listens_for(_eng, "connect")
           def _set_pragmas(dbapi_conn, _):
               cur = dbapi_conn.cursor()
               cur.execute("PRAGMA journal_mode=WAL")
               cur.execute("PRAGMA synchronous=NORMAL")
               cur.execute("PRAGMA foreign_keys=ON")
               cur.close()
           if chave == "intranet" and novo_banco:
               metadata.create_all(_eng)   # UMA vez, só no central
           elif novo_banco:
               _eng.connect().close()      # cria o arquivo; schema via init_db
           _engines[chave] = _eng
           return _eng

   class Repositorio:
       def __init__(self, sessao: Optional[Session] = None,
                    chave_db: str = "intranet"):
           if chave_db not in MODULOS_BD:
               chave_db = "intranet"
           self.chave_db = chave_db
           self._sessao = sessao

       @property
       def sessoes(self) -> Optional[Session]:
           if self._sessao is None:
               self._sessao = sessaodb(self.chave_db)
           return self._sessao

       # ---- helpers genéricos (SQL cru no banco vinculado) ----
       def consultar(self, sql, params=None) -> list[dict]:
           if self.sessoes is None:
               return []
           try:
               rows = self.sessoes.execute(text(sql), params or {}).mappings().all()
               return [dict(r) for r in rows]
           except Exception as ex:
               _log().warning(f"consultar({self.chave_db}): {ex}")
               return []

       def executar(self, sql, params=None) -> int:
           if self.sessoes is None:
               return -1
           try:
               res = self.sessoes.execute(text(sql), params or {})
               self.sessoes.commit()
               return res.rowcount if res.rowcount is not None else 0
           except Exception as ex:
               _log().warning(f"executar({self.chave_db}): {ex}")
               try:
                   self.sessoes.rollback()
               except Exception:
                   pass
               return -1

       def ultimo_id(self):
           if self.sessoes is None:
               return None
           try:
               return self.sessoes.execute(
                   text("SELECT last_insert_rowid()")).scalar()
           except Exception as ex:
               _log().warning(f"ultimo_id({self.chave_db}): {ex}")
               return None

       # ---- métodos tipados (ORM/dataclass) ----
       def obter(self, id_) -> Optional[Exemplo]:
           if self.sessoes is None:
               return None
           try:
               return self.sessoes.get(Exemplo, id_)
           except Exception as ex:
               _log().warning(f"obter: {ex}")
               return None

       def criar(self, nome: str) -> bool:
           if self.sessoes is None:
               return False
           try:
               self.sessoes.add(Exemplo(nome=nome))
               self.sessoes.commit()
               return True
           except Exception as ex:
               _log().warning(f"criar: {ex}")
               return False

       def fechar(self):
           if self._sessao:
               self._sessao.close()
               self._sessao = None

       def __enter__(self):
           return self

       def __exit__(self, *args):
           self.fechar()
   ```

3. **`db_manipulador.py`** — usa `Repositorio` para todo acesso:
   ```python
   from mod_<nome>.repositorio import Repositorio

   def obter_exemplo(id_) -> Optional[Exemplo]:
       with Repositorio() as repo:
           return repo.obter(id_)
   ```

### Regras obrigatórias

| Regra | Detalhe |
|:---|:---|
| **Docstrings bilíngues EN+PT** | Cada função/classe/módulo com docstring no padrão do projeto |
| **Try/except em tudo** | Toda função/ação em `try/except`; `except Exception` genérico para fail-soft |
| **Loguru com nome da função** | `_log().info/warning/error/exception(...)` — o `_FMT` garante `{function}` |
| **Fail-soft** | Falha retorna valor seguro (`padrao`/`False`/`[]`/`None`), nunca derruba a aplicação |
| **SQLAlchemy opcional** | `engine()` retorna `None` se indisponível; `Repositorio` opera em modo degradado |
| **Multi-banco** | `engine(chave)`/`sessaodb(chave)`/`Repositorio(chave_db=...)` operam em qualquer banco de `MODULOS_BD`; chave desconhecida → central (fail-soft) |
| **Criação condicional** | `create_all` + log só quando o arquivo do banco NÃO existe; módulos ≠ intranet nunca rodam `create_all` (schema é do `init_db` do módulo) |
| **WAL sempre** | Event listener no `engine` para `PRAGMA journal_mode=WAL` |
| **Commit explícito** | `session.commit()` após cada escrita; rollback automático no `except` |
| **Sem cross-query** | Cada módulo acessa apenas seu banco próprio |

### Piloto: `mod_intranet`

Arquivos migrados no núcleo (07/09, multi-banco em 06/09):
- `models/__init__.py` — `Configuracao`, `Sessao`, `Modulo` + tabelas + `map_imperatively`
- `repositorio.py` — `MODULOS_BD` (7 bancos) + `caminho_db()` + `engine(chave)` por banco (criação condicional) + `sessaodb(chave)` + `garantir_bancos()` + `Repositorio(chave_db=...)` com helpers genéricos `consultar`/`executar`/`ultimo_id`
- `bd_conexao.py` — `get_config`/`set_config` delegam para `Repositorio` (fallback sqlite3)
- `autenticacao.py` — todas as operações de sessão e módulo via `Repositorio`
- `db_manipulador.py` — `garantir_rastreabilidade` usa `Repositorio`
- `bd_criador.py` — `inicializar_bancos()` chama `garantir_bancos()` no passo 0 do boot (antes dos `init_db`)

### Propagação para módulos existentes

Ao migrar um módulo `mod_*` existente:

1. Criar `mod_<nome>/models/__init__.py` com as tabelas e dataclasses.
2. Registrar o banco do módulo em `MODULOS_BD` (`mod_intranet/repositorio.py:57-65`) e usar `engine(chave)`/`sessaodb(chave)`/`Repositorio(chave_db=...)` — não criar engine próprio.
3. Refatorar `db_manipulador.py` para usar `Repositorio` (métodos tipados ou helpers genéricos `consultar`/`executar`/`ultimo_id`) em vez de sqlite3 direto.
4. Manter `CrudBase` para operações que não se beneficiam do ORM (ex.: FTS5, DDL complexo).
5. Atualizar docstrings para EN+PT-BR.
6. Garantir que todos os `except` usem loguru.

> Ver detalhes em [Arquitetura — Arquitetura de acesso a dados do núcleo](../arquitetura.md#arquitetura-de-acesso-a-dados-do-nucleo-backend-duplo-0809) e [Módulo Núcleo — Repositório](../modulos/intranet.md#repositorio-mod_intranetrepositoriopy-0709-multi-banco-0609).
