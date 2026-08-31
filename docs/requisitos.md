# Intranet Modular — System Requirements

> Technical requirements to run the Intranet Modular: Linux/Windows host, Python 3.12, NiceGUI 3.15 (Tailwind served locally — no CDN), SQLite in WAL mode, APScheduler, nh3, PDF libraries (pymupdf, pikepdf, pypdf, pdfplumber, pytesseract), bcrypt, loguru and MkDocs (theme `readthedocs`).

---

# Intranet Modular — Requisitos do Sistema

> Requisitos técnicos para rodar a Intranet Modular: hospedeiro Linux/Windows, Python 3.12, NiceGUI 3.15 (Tailwind servido localmente — sem CDN), SQLite em modo WAL, APScheduler, nh3, bibliotecas de PDF (pymupdf, pikepdf, pypdf, pdfplumber, pytesseract), bcrypt, loguru e MkDocs (tema `readthedocs`).

## Sumário

1. [Visão geral](#visao-geral)
2. [Sistema operacional](#sistema-operacional)
3. [Linguagem e framework](#linguagem-e-framework)
4. [Dependências Python](#dependencias-python)
5. [Armazenamento](#armazenamento)
6. [Rede e interface](#rede-e-interface)
7. [Requisitos não funcionais relevantes](#requisitos-nao-funcionais-relevantes)

## Visão geral

| Categoria | Exigência |
|:---|:---|
| SO | Linux (recomendado) ou Windows |
| Python | **3.12** |
| Framework | **NiceGUI 3.15** |
| Banco | SQLite (stdlib) em **modo WAL** |
| UI | Tailwind CSS servido localmente pelo NiceGUI (**sem CDN**) |
| Internet | necessária apenas na instalação das dependências; em operação, o sistema deve rodar **sem internet** (rede interna) |

## Sistema operacional

- **Linux** — ambiente de referência do projeto (rotinas de MAC via `ip neigh`, caminhos em `rotinas.py` etc.).
- **Windows** — suportado; a detecção de MAC via ARP retorna `None` silenciosamente (coluna `mac` fica nula).

## Linguagem e framework

- **Python 3.12** — versão usada pelo projeto (há histórico de convenções do código baseadas nela, ex.: `datetime.now(localtime)`).
- **NiceGUI 3.15.0** — framework web (FastAPI/WebSockets); `ui.run(...)` no `main.py` com `reload=False`, `show=False`, porta `8080`.

## Dependências Python

Fonte: `requirements.txt` (raiz).

| Dependência | Versão mínima | Uso |
|:---|:---|:---|
| `nicegui` | `3.15.0` | framework web (páginas, componentes, Tailwind local) |
| `apscheduler` | `>=3.10,<4` | agendadores (backups, cleanups, monitor de pasta, poda) |
| `nh3` | `>=0.2` | sanitização HTML do Blog (gravação e renderização) |
| `pdfplumber` | `>=0.11` | extração de texto de PDF (fallback) |
| `pikepdf` | `>=9.0` | manipulação PDF (metadados, redução leve) |
| `pymupdf` | `>=1.24` | extração de texto, contagem de páginas, rasterização |
| `pytesseract` | `>=0.3` | OCR de PDFs escaneados (requer binário `tesseract` no SO) |
| `pypdf` | `>=5.0` | manipulação PDF (redução leve/fallback) |
| `bcrypt` | `>=5.0.0` | hash de senhas |
| `loguru` | `>=0.7.3` | observabilidade/logs por módulo |
| `mkdocs` | `>=1.6.1` | build da documentação embutida |
| `mkdocs-material` | `>=9.7.7` | presente no requirements; **o tema ativo é `readthedocs`** (ver `mkdocs.yml`) |

> ⚠️ **`pytesseract`** depende do binário **Tesseract OCR** instalado no sistema operacional (`apt install tesseract-ocr` no Debian/Ubuntu, com `por+eng`).

## Armazenamento

- **SQLite** (módulo `sqlite3` da stdlib) — sem servidor externo de banco.
- **Modo WAL obrigatório**: cada conexão executa `PRAGMA journal_mode=WAL` + `PRAGMA synchronous=NORMAL` (ex.: `mod_intranet/conexao_bd.py:27-31`).
- **Um banco por módulo** na raiz do projeto: `db_mod_intranet.db`, `db_mod_gest_cad_usuario.db`, `db_mod_blog.db`, `db_mod_edit_pdf.db`, `db_mod_renomear_empenho.db`, `db_mod_solicita_impressao.db`.
- Pastas de arquivos: `backup/` (backups), `editorPDF/` (arquivos temporários do editor), `doc/` (empenhos), `quarentena/`, `organizadorPasta/`, `logs/` (loguru), `assets/` (favicon), `site/` (docs compiladas).

## Rede e interface

- **Tailwind CSS local**: o NiceGUI embute/ serve o `tailwindcss.min.js` localmente (`ui.run(...)` sem CDN) — exigência para rede interna.
- **Porta**: `8080` (configurável no bloco `ui.run` de `main.py:333-339`).
- **Documentação**: servida na mesma porta em `/documentacao` (build MkDocs `docs/` → `site/`, montado pela própria aplicação — `mod_intranet/documentacao.py`).

## Requisitos não funcionais relevantes

| Requisito | Detalhe |
|:---|:---|
| Rastreabilidade LGPD | `tb_auditoria` com IP/user-agent/dispositivo; hash SHA-256 em operações com arquivos |
| Retenção de auditoria | poda automática diária > `auditoria_retencao_dias` (default 90) |
| Cotas de disco | editor PDF: global 10 GB default + por usuário + por lote |
| Expiração automática | arquivos do editor (default 10 min) e rascunhos de impressão (default 4 min) |
| Backups | por módulo a cada 12 h (configurável), retenção das 10 cópias mais recentes |
| Segurança da sessão | cookie HTTP-Only; sessões revogáveis; `storage_secret` placeholder precisa ser trocado em produção |

> Em conflito entre documentação e código, prevalece o **código executável** (`requirements.txt`, `mkdocs.yml`, `main.py`).