# Contributions — Intranet Modular

> How to contribute a new module or change to the Intranet Modular. Follows the coding standards and the modular package layout.

---

# Contribuições — Intranet Modular

> Como contribuir com um novo módulo ou alteração na Intranet Modular. Segue os padrões de codificação e o layout de pacotes modular.

## Como adicionar um módulo (`mod_exemplo`)

1. Crie o pacote `mod_exemplo/` com `__init__.py`, `telas.py` (obrigatório: `mostrar_tela(nome, perfil)`), `manipulador_bd.py`.
2. Crie o banco próprio `db_mod_exemplo.db` (WAL) via `inicializar_bancos()`.
3. Registre o módulo em `tb_modulos` (`autenticacao.registrar_modulo`).
4. Toda escrita relevante deve registrar em `tb_auditoria` (central); operações de PDF registram `hash_arquivo` (SHA-256).
5. Valide o `.py` com `ast.parse` e suba o servidor para smoke test.

## Regras de contribuição

- Respeite `snake_case` e o modelo de pacote (ver [Padrões de Codificação](../padroes_codificacao/index.md)).
- Sem comentários a menos que solicitado; sem classes (estilo funcional).
- Nunca `git push`; `git commit` apenas com instrução do autor (padrão `AAMMDD HHMM ...`).
- Mantenha a documentação atualizada (cabeçalho EN+PT-BR) em `docs/`.

## Escopo

Edições restritas à raiz do projeto; não acesse arquivos fora dela.

Veja [Arquitetura](../arquitetura_de_software_das/index.md) e [Plano de Projeto](../plano_de_projeto/index.md).
