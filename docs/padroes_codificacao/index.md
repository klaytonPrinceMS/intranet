# Coding Standards — Intranet Modular

> Mandatory coding standards, derived from the actual codebase (function-based, `snake_case`, module packages `mod_*`). Mirror an existing module when in doubt.

---

# Padrões de Codificação — Intranet Modular

> Padrões obrigatórios de codificação, extraídos do código real (funcional, `snake_case`, pacotes `mod_*`). Em dúvida, espelhe um módulo existente.

## 1. Nomenclatura

- **`snake_case`** para funções, variáveis e nomes de arquivo Python. Ex.: `autenticar` (`:179`), `gerar_hash_senha` (`:161`), `mod_intranet_inicializacao_bd.py`.
- **Não use `camelCase`** para funções/variáveis Python.
- Constantes em **`MAIUSCULAS_SNAKE`**.
- Pacote de módulo: **`mod_<nome>`** (minúsculas, underscore). Arquivos: **`mod_<nome>_<descricao>.py`**.
- Tabelas: **`tb_<nome>`**; colunas: `snake_case` com prefixo semântico (`user_nome`, `hash_arquivo`).

## 2. Estilo

- Projeto **funcional/procedural** — não há classes; prefira funções puras.
- `telas.py` **DEVE** expor `mostrar_tela(nome, perfil)`.
- Sem comentários a menos que solicitado (regra `AGENTS.md`).
- Valide com: `.venv/bin/python -c "import ast; ast.parse(open('<arquivo>', encoding='utf-8').read())"`.

## 3. Modelo de novo módulo

```
mod_exemplo/
  __init__.py
  telas.py            # mostrar_tela(nome, perfil)
  manipulador_bd.py   # acesso ao db_mod_exemplo.db (WAL)
  criador_bd.py       # legado/morto — não confiar
```
- Banco próprio criado por `inicializar_bancos()`; toda escrita relevante registra em `tb_auditoria` (central).
- Registre o módulo em `tb_modulos` (`autenticacao.registrar_modulo`).

## 4. Tela (NiceGUI)

- Funções que recebem `(nome, perfil)`; sem JavaScript direto.
- Respeite o layout de 4 partes; valide o papel do ator antes de qualquer escrita.
- Conteúdo HTML do Blog passa obrigatoriamente por `nh3`.

## 5. Banco

- `manipulador_bd.py` concentra acesso; **nunca cross-query** entre bancos.
- Toda conexão aplica `PRAGMA journal_mode=WAL`.
- Soft delete para entidades sensíveis, com coluna de motivo e auditoria.

## 6. Versionamento

- Padrão `1.0.AAMMDD` (major.menor.data) — ver [Versionamento](../versionamento/index.md).

## 7. Padrões aplicados no módulo `mod_renomear_empenho` (exemplo vivo)

> O módulo Renomeador de Empenho é referência concreta das convenções abaixo.

- **Duas camadas por módulo** (`manipulador_bd.py` + `telas.py`), com `mostrar_tela(usuario_logado, perfil)` obrigatório (`telas.py:45`).
- **Banco WAL próprio** (`db_mod_<nome>.db`) com `CREATOR` idempotente (`CREATE TABLE IF NOT EXISTS` + seeds condicionais) e **migração de coluna** para bancos antigos (`_migrar_coluna`, `manipulador_bd.py:278`).
- **Tabelas `tb_<nome>`**, colunas `snake_case` com prefixo semântico (`nome_arquivo_final`, `tipo_especial`, `motivo_recusa`).
- **Trilha de auditoria por arquivo** (hash SHA-256) no próprio banco do módulo + `audit_log` central com hash — ver `tb_arquivos_auditoria`/`tb_eventos_arquivos`.
- **Perfil por aba**: calcula `eh_admin = perfil == "administrador_geral" or eh_admin_do_modulo(usuario, "<chave>")` e restringe abas/funções a admin; valida o papel antes de qualquer escrita.
- **Configurações via `tb_config`** (chaves `empenhos_*`) lidas/aplicadas **sem reiniciar** — ver [Configurações](../configuracoes.md).
- **Tabs manuais** com `ui.tabs()`/`ui.tab_panels()` (padrão `mod_solicita_impressao`) em vez de helper de abas do módulo.
- **Segurança de caminho**: normaliza com `os.path.realpath` e mantém lista de **raízes protegidas** (`raizes_navegacao`/`pasta_navegavel`) para anti-travessia; evita `..` em navegação.
- **Idempotência/não-reprocessamento**: decide por nome padronizado e/ou registro no banco (`_arquivo_registrado_no_bd`).
- **Anti-colisão** ao gerar destinos: sufixa (`_v2`, `_v3`) em vez de sobrescrever.
- **Regex configuráveis** centralizadas em constantes/tabela (não espalhadas) com validação `re.compile` antes de persistir.
- **Import side-effect control**: o módulo dispara `init_db_empenho()` na importação; por isso `inicializar_bancos()` deve rodar antes (ordem de import importa — ver `AGENTS.md`).
- **Sem classes de negócio/ORM**; funções puras `snake_case`; validação de sintaxe via `ast.parse`.

> Regra de ouro: ao criar ou alterar um módulo, espelhe `mod_renomear_empenho`/`mod_solicita_impressao` e valide com `ast.parse` antes de submeter.
