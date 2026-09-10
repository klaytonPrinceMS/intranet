# Security Scan Report — Intranet Modular (2026-09-06)

> First DevSecOps scan of the Intranet Modular codebase: bandit, semgrep, pip-audit, safety and gitleaks. 0 high-severity findings; 24 medium (bandit) and 31 (semgrep) findings analyzed — most are low/structural or false positives from internal constants; 1 real secret-in-code finding (default Grafana credentials).

---

# Relatório de Varredura de Segurança — Intranet Modular (06/09/2026)

> Primeira varredura DevSecOps do código do Intranet Modular: bandit, semgrep, pip-audit, safety e gitleaks. 0 achados de alta severidade; 24 médios (bandit) e 31 (semgrep) analisados — a maioria baixa/estrutural ou falso positivo de constantes internas; 1 achado real de segredo em código (credenciais padrão do Grafana).

## Escopo e ferramentas

- **Data**: 06/09/2026
- **Ambiente**: Linux, Python 3.12.4, venv `.venv`
- **Alvo**: `main.py`, `mod_intranet`, `mod_auditoria`, `mod_blog`,
  `mod_edit_pdf`, `mod_gest_cad_usuario`, `mod_renomear_empenho`,
  `mod_solicita_impressao`, `requirements.txt`, histórico git.

| Ferramenta | Versão |
|:---|:---|
| bandit | 1.9.4 |
| semgrep | 1.176.1 |
| pip-audit | 2.10.1 |
| safety | 3.8.1 |
| gitleaks | 8.24.3 |

## Resultados — bandit

Total: **0 High · 24 Medium · 86 Low** (18.675 linhas de código).

| Severidade | Quantidade | Descrição |
|:---|:---|:---|
| High | 0 | — |
| Medium | 22 | `B608` SQL injection (string-based query) |
| Medium | 2 | `B310` urlopen com scheme não auditado |
| Low | ~60 | `B110` try/except pass silencioso |
| Low | restante | sugestões de estilo/confiança |

### Análise dos achados médios

**B608 (SQL injection)** — `../../mod_auditoria/db_manipulador.py`, `mod_blog`,
`mod_edit_pdf`, `mod_gest_cad_usuario`, `mod_intranet/repositorio.py`,
`mod_renomear_empenho`, `mod_solicita_impressao`.

Status: **falso positivo / baixo risco na prática**. Os valores são sempre
passados por parâmetro `?`; apenas **nomes de tabela/coluna** são interpolados e
vêm de funções/constantes internas (`_nome_tabela()`, `PRAGMA`, dicionários
fixos), nunca de input do usuário. Exemplos confirmados:
`mod_auditoria/manipulador_bd.py:148`, `:168`, `:173` e
`mod_intranet/manipulador_bd.py:55-70`.

Ação recomendada: manter a regra (nunca interpolar input de usuário) e, se
desejado, adicionar `# nosec B608` com comentário nas linhas de tabela interna
para reduzir ruído.

**B310 (urlopen)** — `mod_intranet/grafana_sync.py:112` e `:136`.

Status: **baixo risco**. A URL vem de `obter_grafana_url()` (env `GRAFANA_URL`
ou chave `grafana_url` em `tb_config`), controlada por **administrador**, não
pelo usuário final. Ainda assim, `urllib` aceita `file://` — um admin com
config corrompida poderia fazer leitura de arquivo local.

Ação recomendada: **validar o scheme** (exigir `http`/`https`) em
`obter_grafana_url()` — hardening de baixo custo.

## Resultados — semgrep

Total: **31 resultados** (`--config auto`).

| Regra | Qtd | Análise |
|:---|:---|:---|
| `sqlalchemy-execute-raw-query` | 21 | Queries SQLAlchemy `text()`/raw; valores parametrizados — revisar caso a caso |
| `formatted-sql-query` | 8 | SQL com f-string; mesmo padrão do B608 — nomes internos |
| `dynamic-urllib-use-detected` | 2 | Mesmos pontos do B310 (`grafana_sync.py:112,136`) |

Status: os achados de SQL seguem o mesmo padrão do bandit (nomes de tabela
internos, valores por parâmetro). Ação: revisar cada `sqlalchemy-execute-raw-query`
para confirmar uso de bind params; aplicar guarda de scheme no urllib.

## Resultados — pip-audit / safety

`pip-audit -r requirements.txt`: **nenhuma vulnerabilidade conhecida**.

`safety check`: sem achados bloqueantes (executado via venv).

## Resultados — gitleaks

**1 achado real** + 36 falsos positivos:

| Achado | Arquivo | Análise |
|:---|:---|:---|
| **Credenciais padrão `master:master`** | `docker/verify-credentials.sh:66` | Script de verificação do Docker/Grafana usa basic auth com usuário/senha padrão `master:master` |
| `generic-api-key` (×36) | `site/search/search_index.json` e `search/search_index.json` | **Falsos positivos** — arquivos de build do mkdocs (texto HTML/JSON gerado) |

Ação recomendada: trocar credenciais padrão do Grafana em produção
(`docker/verify-credentials.sh` é para ambiente local de observabilidade);
configurar `.gitignore` para `site/` se não for publicado.

## Ações recomendadas (priorizadas)

1. **Alta**: trocar credenciais padrão do Grafana fora de dev
   (`docker/verify-credentials.sh`); validar scheme http/https em
   `obter_grafana_url()`.
2. **Média**: revisar os 21 `sqlalchemy-execute-raw-query` para confirmar bind
   params; documentar as regras de "nomes de tabela internos" como aceitas.
3. **Baixa**: reduzir ruído B608 com `# nosec` justificado; substituir
   `except: pass` silenciosos por loguru.warning (padrão do projeto); adicionar
   `site/` ao `.gitignore`.

## Próximos passos

- Adicionar esta rotina ao fluxo de toda alteração (subagente `qa_seguranca`).
- Rodar periodicamente (pré-release): `bandit`, `semgrep`, `pip-audit`, `gitleaks`.
- Integrar `k6` para carga quando houver endpoints críticos.
- Documentar novas varreduras em `docs/testes_relatorios/`.

Veja [Ferramentas de Segurança](../seguranca/ferramentas_de_seguranca.md) e
[Riscos de IA/ML](../seguranca/riscos_ia_ml.md).