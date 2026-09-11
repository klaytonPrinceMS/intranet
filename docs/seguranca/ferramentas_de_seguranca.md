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

## Scanner local de portas e serviços (11/09)

O projeto inclui um **scanner de portas embutido** — `mod_intranet/port_scanner.py` —
usado pelo assistente de ativação e pela CLI (`--scan-ports`) para diagnóstico de
**segurança/instalação**:

| Função | Descrição |
|:---|:---|
| `escanear_portas(host="127.0.0.1", inicio=1, fim=65535, threads=250, timeout=0.05)` (`port_scanner.py:26`) | varre portas LISTEN com **thread pool** (`ThreadPoolExecutor` `:42`) e timeout curto por porta |
| `portas_com_servico()` (`:122`) | `dict {porta: servico}` — Linux via `ss -ltnp` (`:58`) enriquecido com `docker ps` (`:106`, containers rodando como root que o `ss` sem sudo não mostra), fallback `lsof` (`:75`); Windows via `netstat -ano` + `tasklist` (`:89`) |
| `resumo_portas()` (`:144`) | string PT-BR para o console (`Nenhuma porta LISTEN detectada (ou sem permissão).` ou `Portas em uso no servidor: ...`) |

**Limites de segurança (importante):**

- **Apenas `127.0.0.1`** — varredura **LOCAL** (a máquina do instalador), com
  `threads=250` e `timeout=0.05`. **Nunca atinge redes externas** — não há varredura
  de outros hosts, sub-redes ou serviços remotos (fora do escopo de legislação de
  segurança da informação).
- Processos de **outros usuários sem permissão** aparecem como `"desconhecido"`
  (o `ss -ltnp`/`netstat` sem sudo não revela o nome do processo).
- Propósito: diagnosticar **portas ocupadas** durante a instalação (ex.: Postgres
  nativo na 5432, Grafana na 3000) e listar o que escuta no servidor — ver
  [Manual de Instalação](../manual_de_uso_instalacao/index.md#21-assistente-de-ativacao-boot).
- Ativado pelo assistente (`_msg_porta_em_uso`, `ativacao.py:190`, com cache por
  processo `_portas_em_uso_cached` `:171`) e pela CLI (`cli_opcoes(['--scan-ports'])`,
  `ativacao.py:885` — imprime o resumo e encerra com **exit 0**).
- Coberto por `assets/test/test_ativacao.py` (90 verificações — inclui
  `_msg_porta_em_uso`, reuso de container e `--scan-ports`).

## Saneamento do assistente de ativação (11/09)

O assistente de boot (`mod_intranet/ativacao.py`) recebe **entrada do usuário no terminal** (senhas, usuários, portas) e executa comandos de instalação/configuração — por isso aplica saneamento rigoroso (revisado pelo kbp-devSecOps):

| Prática | Implementação |
|:---|:---|
| **Nunca `shell=True` para entrada do usuário** | `_cmd` (`ativacao.py:245`) aceita **lista de args** (ou string via `shlex.split` quando não há operadores de shell); `shell=True` só para comandos **estáticos** internos (com `&&`/`|` etc.), sem nunca interpolar entrada do usuário |
| **Credenciais por stdin, nunca no argv** | `entrada=` do `subprocess.run` (`:262-264`) — ex.: a senha do WSL via `chpasswd` é enviada por stdin (`:510-511`), não aparece na linha de comando (evita vazamento em `/proc/<pid>/cmdline`, logs e histórico) |
| **Mascaramento no print** | `_mascarar_comando` (`:232`) remove a senha do comando exibido: `usuario:senha | chpasswd` → `usuario:***`, `-p <senha>` → `-p ***`, `password=<senha>` → `password=***` |
| **Whitelist de distro WSL** | `configurar_docker_windows` (`:465`) aceita apenas `{debian, ubuntu, alpine}` (`:480-482`), com revalidação antes do comando |
| **Usuário WSL com regex** | `^[a-z_][a-z0-9_-]{0,31}$` (`:491`) — padrão de nomes de usuário Linux |
| **Senha sem metacharacters de shell** | `_validar_senha` (`:460`) rejeita `[;|&\n$'"\\ ]` — evita injeção via `chpasswd`/shell |
| **Portas validadas** | `perguntar(..., faixa=(1,65535))` + `_porta_valida` (`:113`) em todas as portas; `_porta_livre` (`:361`) retorna `False` em erro — porta inválida **nunca** é considerada "livre" |

Coberto por `test/test_ativacao.py` (57 verificações — `_mascarar_comando`, `_validar_senha`, `_porta_valida`/`_porta_livre`, `_compose_cmd`, `aplicar_portas`).

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