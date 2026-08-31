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
