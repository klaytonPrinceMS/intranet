# Software Metrics — Intranet Modular

> Software metrics for the Intranet Modular. Seed document based on test counts from `PLANO.md` and module version seeds.

---

# Métricas de Software — Intranet Modular

> Métricas de software do sistema. Documento-semente baseado nas contagens de teste de `PLANO.md` e versões de módulo.

## Cobertura de testes (de `PLANO.md`)

| Fluxo | Resultado |
|:---|:---|
| Autenticação (`teste_fluxo_autenticacao.py`) | 19/19 OK |
| Permissões (`teste_fluxo_permissoes.py`) | 13/13 OK |
| Blog (`teste_fluxo_blog.py`) | 33/33 OK |
| Renomeador — documento-modelo (`teste_fluxo_renameador.py`) | 31/31 OK |
| Renomeador — organizador | 16/16 OK |
| Renomeador — edição embutida | 18/18 OK |
| Editor de PDF (`test/test_editor_pdf.py`) | 20 verificações |

## Versionamento de módulos

- `mod_solicita_impressao`: `1.0.260829` (seed em `tb_config`).

## Sugestão de expansão

Incluir: linhas de código por módulo, cobertura de auditoria (%), tempo de backup, taxa de expiração de arquivos do editor, MTTR de incidentes.

Veja [Testes — Relatórios](../testes_relatorios/index.md) e [Versionamento](../versionamento/index.md).
