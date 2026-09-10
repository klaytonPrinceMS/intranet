# Security Tools & Practices — Intranet Modular

> Security and DevSecOps tools used in the Intranet Modular project, how to install/run them and what they cover. SAST, dependency audit, secret scanning, load testing and Kali tools.

---

# Ferramentas e Práticas de Segurança — Intranet Modular

> Ferramentas de segurança e DevSecOps usadas no projeto Intranet Modular, como instalar/executar e o que cobrem. SAST, auditoria de dependências, varredura de segredos, teste de carga e ferramentas Kali.

## Propósito

Garantir que o código do projeto seja revisto por **QA + Segurança da Informação**
antes de chegar ao usuário. As ferramentas abaixo compõem a rotina de
**DevSecOps** do projeto (ver o subagente `.opencode/agent/qa_seguranca.md`).

Todas as ferramentas de segurança de desenvolvimento estão em
`requirements-dev.txt` (não poluem o `requirements.txt` de produção). O venv é
obrigatório: `source .venv/bin/activate`.

## Ferramentas e instalação

### Python (PyPI) — via `requirements-dev.txt`

```bash
pip install -r requirements-dev.txt
```

| Ferramenta | Versão testada | Papel |
|:---|:---|:---|
| `bandit` | 1.9.4 | SAST Python (SQLi, `pass` silencioso, urlopen, subprocess) |
| `semgrep` | 1.176.1 | SAST multi-regra (SQLAlchemy raw, formatted SQL, urllib dinâmico) |
| `pip-audit` | 2.10.1 | CVEs das dependências (PyPI/OSV) |
| `safety` | 3.8.1 | CVEs conhecidas |
| `pytest` | 8.x | Testes funcionais (já no projeto) |
| `pytest-playwright` | 0.9.0 | E2E headless (test/e2e) |
| `pytest-cov` | 7.1.0 | Cobertura |

### Binários externos (não-PyPI)

| Ferramenta | Instalação | Papel |
|:---|:---|:---|
| `gitleaks` 8.24.3 | Binário Go (ver abaixo) | Varredura de segredos no histórico git |
| `k6` | Binário oficial Grafana | Teste de carga/performance (opcional) |

**gitleaks** (binário em `~/.local/bin/gitleaks`, linkado em `.venv/bin/gitleaks`):

```bash
curl -sL -o /tmp/gitleaks.tgz https://github.com/gitleaks/gitleaks/releases/download/v8.24.3/gitleaks_8.24.3_linux_x64.tar.gz
tar -xzf /tmp/gitleaks.tgz gitleaks && install gitleaks ~/.local/bin/
```

**k6** (se necessário para carga): seguir a instalação oficial
(https://grafana.com/docs/k6/latest/set-up/install/) — no Debian/Ubuntu:

```bash
sudo gpg -k 0xABB0D86A2D2B9F3C   # chave do repositório grafana
echo "deb https://packages.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list
sudo apt-get update && sudo apt-get install k6
```

### Ferramentas Kali (host)

Disponíveis no host (confirmadas): `nmap`, `sqlmap`, `wpscan`, `john`,
`msfconsole`, `dirb`, `dnsrecon`, `recon-ng`, `theharvester`, `sslscan`.

Não instaladas (solicitar ao usuário se necessário): `nikto`, `hydra`,
`gobuster`, `hashcat`.

> Testes com ferramentas Kali devem ser direcionados **apenas a ambientes
> próprios** (localhost/staging). Nunca contra terceiros sem autorização.

## Comandos de uso

### SAST — Bandit

```bash
bandit -r main.py mod_* -q
# saída JSON para relatório:
bandit -r main.py mod_* -q -f json -o /tmp/bandit_out.json
```

### SAST — Semgrep

```bash
semgrep scan --config auto --error --timeout=30 -j 4 --quiet main.py mod_* \
  --output /tmp/semgrep_out.json --json
```

### Auditoria de dependências

```bash
pip-audit -r requirements.txt
pip-audit -r requirements-dev.txt
safety check
```

### Segredos no git

```bash
gitleaks detect --source . --redact
gitleaks detect --source . --redact --report-format json --report-path /tmp/gitleaks.json
```

> `site/` (build do mkdocs) e `search/search_index.json` geram **falsos positivos**
> (conteúdo HTML/texto). Filtrar ao interpretar resultados.

### Rede / serviços (Kali)

```bash
nmap -sV -p- localhost          # serviços expostos
sslscan localhost:8080          # TLS/SSL
sqlmap -u <url> --batch         # SQLi (endpoints próprios)
```

## Resultado da primeira varredura (06/09/2026)

| Ferramenta | Resultado |
|:---|:---|
| `bandit` | 0 High, 24 Medium, 86 Low — ver `docs/testes_relatorios/seguranca_2026-09-06.md` |
| `semgrep` | 31 resultados (SQLAlchemy raw 21, formatted SQL 8, urllib dinâmico 2) |
| `pip-audit` | Nenhuma vulnerabilidade conhecida |
| `gitleaks` | 1 achado real (credenciais padrão `master:master` em `docker/verify-credentials.sh:66`); demais são falsos positivos de `site/` |

Veja também: [Relatório de Segurança (06/09)](../testes_relatorios/seguranca_2026-09-06.md),
[Riscos de IA/ML](../seguranca/riscos_ia_ml.md) e
[Análise de Risco](../analise_de_risco/index.md).