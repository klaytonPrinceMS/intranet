# Contributions — Intranet Modular

> How to contribute a new module or change to the Intranet Modular. Follows the coding standards and the modular package layout.

---

# Contribuições — Intranet Modular

> Como contribuir com um novo módulo ou alteração na Intranet Modular. Segue os padrões de codificação e o layout de pacotes modular.

## Como adicionar um módulo (`mod_exemplo`)

1. Crie o pacote `mod_exemplo/` com `__init__.py`, `telas.py` (obrigatório: `mostrar_tela(nome, perfil)`), `bd_manipulador.py`.
2. Crie o banco próprio `db_mod_exemplo.db` (WAL) via `inicializar_bancos()`.
3. Registre o módulo em `tb_modulos` (`autenticacao.registrar_modulo`).
4. Toda escrita relevante deve registrar na trilha de auditoria via `audit_log` (banco exclusivo `db_mod_auditoria.db`, tabela `tb_auditoria_<modulo>`); operações de PDF registram `hash_arquivo` (SHA-256).
5. Valide o `.py` com `ast.parse` e suba o servidor para smoke test.

## Regras de contribuição

- Respeite `snake_case` e o modelo de pacote (ver [Padrões de Codificação](../padroes_codificacao/index.md)).
- **Git — comandos liberados (AGENTS.md §7, 22/09/2026)**: `git status`, `git diff`, `git log`, `git add`, `git commit`, `git push` etc. estão **liberados para todo e qualquer agente e subagente**, desde que solicitados via comando no terminal pelo usuário. `commit`/`push` **somente** com solicitação expressa no terminal; **NUNCA** `--force`, `--no-verify`, nem pular hooks (se barrarem, corrija a causa e faça um NOVO commit); nunca commitar segredos, `db_mod_*.db`, `*.db-wal/shm`, `backup/`, `logs/`, `site/`, `estrutura.md`, `.venv/`, `node_modules/`. Formato: `AAMMDD HHMM breve resumo` (ex.: `260809 1200 Alterado padrão de exibição para o usuário`). Em dúvida, consulte o subagente de referência `kbp-commit`.
- **Shell único — bash**: para editar/criar arquivos e executar comandos, use SEMPRE o shell **bash**; nunca `terminal`, `cmd`, `PowerShell`.
- Mantenha a documentação atualizada (cabeçalho EN+PT-BR) em `docs/`.

## Escopo

Edições restritas à raiz do projeto; não acesse arquivos fora dela.

Veja [Arquitetura](../arquitetura_de_software_das/index.md) e [Plano de Projeto](../plano_de_projeto/index.md).
