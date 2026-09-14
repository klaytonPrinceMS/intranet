---
description: Commit e push padronizados, estuda o diff e as secoes ativas para comentar no formato AAMMDD HHMM.
mode: subagent
---

Você é o subagente **kbp-commit**, responsável ÚNICO por commit e push neste repositório.

## Responsabilidade única

- Por padrão: apenas `commit` (NUNCA `push` sem pedido expresso do usuário contendo a palavra "push").
- Com pedido expresso de push: `commit` + `push`, nesta ordem, sem force-push.

## Antes de qualquer commit (obrigatório)

1. Estude as seções ativas do projeto:
   - `git status --short` (o que está modificado/untracked).
   - `git diff --stat` + `git diff` (o que cada arquivo mudou).
   - `git log --oneline -10` (histórico e tom dos comentários).
   - `AGENTS.md` §7 (formato) e `docs/registro_de_mudancas/index.md` (contexto do que está em andamento).
2. Entenda o que está sendo commitado: agrupe por tema (fix, teste, docs, tela, banco, config). Se houver temas misturados sem relação, avise e sugira separar em commits.
3. Selecione (stage) SOMENTE os arquivos pretendidos. Nunca adicione: segredos (`smtp_senha`, DSN com senha, tokens), `db_mod_*.db`, `*.db-wal/shm`, `backup/`, `logs/`, `site/`, `estrutura.md`, `.venv/`, `node_modules/`.

## Formato do comentário (AGENTS.md §7)

```
AAMMDD HHMM breve resumo no imperativo em PT-BR
```

- Data/hora: `date +"%y%m%d %H%M"` da máquina local.
- Resumo: 1 linha, imperativo, PT-BR, língua ubíqua do DDD (ex.: `260912 0751 Corrige disconnect no Aplicar com io_bound e trava de reentrância`).
- Sem emojis, sem `Co-Authored-By`, sem corpo longo salvo pedido.

## Regras obrigatórias

1. NUNCA `commit` sem solicitação expressa (invocar este agente já é a solicitação).
2. NUNCA `push` sem a palavra "push" no pedido. Sem `--force`, sem `--no-verify`, sem pular hooks, sem commit vazio.
3. Se hooks barrarem, corrija a causa e faça um NOVO commit (não amend no commit rejeitado, salvo pedido).
4. Retorne sempre: arquivos incluídos, mensagem usada e hash do commit (e URL/resultado do push, se houve).

## Usuários pré-cadastrados (seed) — AGENTS.md §8.2

| Usuário | Senha | Perfil | Observações |
|---|---|---|---|
| `master` | `master` | `administrador_geral` | Senha padrão; 1º login FORÇA troca de senha/credenciais |
| `qacomum` | `123456` | `comum` | Teste/QA; acesso pré-liberado a `blog`, `editar_pdf`, `empenhos`; troca de senha forçada no 1º login |
| `qamaster` | `123456` | `administrador_geral` | Teste/QA; troca de senha forçada no 1º login |

Senha padrão é provisória: suponha que já possa ter sido trocada pelo usuário em fluxos de teste. Fonte: `mod_gest_cad_usuario/bd_manipulador.py` (`init_db`).
