# Test Plan — Intranet Modular

> Test plan by flow, derived from `PLANO.md` (Fases 2.5 a 5). No automated framework; manual scripts in `test/`.

---

# Testes — Plano — Intranet Modular

> Plano de testes por fluxo, de `PLANO.md` (Fases 2.5 a 5). Sem framework automatizado; scripts manuais em `test/`.

## Fluxos cobertos

- **Boot** (`teste_boot.py`): servidor sobe, `/login` com Tailwind local.
- **Autenticação** (`teste_fluxo_autenticacao.py`): login master → senha provisória → troca obrigatória → sessão/logout → auditoria → soft delete (19/19 OK).
- **Permissões** (`teste_fluxo_permissoes.py`): concessão/atualização/revogação de perfil por módulo + admin geral vê tudo (13/13 OK).
- **Blog** (`teste_fluxo_blog.py`): sanitização XSS, conversores, CRUD, soft delete, config local, auditoria central (33/33 OK).
- **Renomeador** (`teste_fluxo_renameador.py`): documento-modelo `DOC_0201.pdf` ponta a ponta (31/31 OK); organizador (16/16); edição embutida (18/18).
- **Editor de PDF** (`test/test_editor_pdf.py`): 20 verificações.
- **Auditoria** (`test/test_auditoria.py`): índices, rastreabilidade IP/UA, poda por retenção, acesso exclusivo do admin geral e preferência de campos/ordem por usuário (12 verificações).

## Critérios de entrada/saída

- Bancos `db_mod_*` devem ser (re)criados do zero se ausentes; seed `master`/`master` com `administrador_geral`.
- Nenhuma falha em silêncio: recusas de upload/quota listadas nominalmente.

Veja [Testes — Casos](../testes_casos/index.md) e [Testes — Relatórios](../testes_relatorios/index.md).
