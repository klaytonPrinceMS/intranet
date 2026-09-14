# Lessons Learned — Intranet Modular

> Lessons learned during development. Seed document — to be expanded as the team records post-mortems and improvements.

---

# Lições Aprendidas — Intranet Modular

> Lições aprendidas durante o desenvolvimento. Documento-semente — expandir com registros de post-mortem e melhorias.

## Lições registradas (semente)

- **Integridade de `main.py`:** edições via PowerShell corromperam caracteres (`.`→`..`, `.`→`~`, `_`→`-`, `,`→`;;`). Mitigação: validar todo `.py` com `ast.parse` e revisar diffs.
- **`bd_criador.py` é legado/morto:** aponta para banco central e não reflete o banco por módulo. Usar `bd_manipulador.py` como fonte de verdade.
- **Sanitização de Blog:** `nh3` deve ser aplicado na gravação **e** na renderização para prevenir XSS.
- **Rastro de auditoria:** toda escrita relevante (incluindo PDF) deve registrar na trilha de auditoria (`audit_log` → banco exclusivo `db_mod_auditoria.db`) com `hash_arquivo` (SHA-256) para conformidade LGPD.
- **Ambiente virtual:** preferir `.venv/bin/python` (Linux) / `Scripts\python.exe` (Windows) para evitar conflitos de dependência.
- **Encoding UTF-8 + WSL (sessão "Ç não reconhecido no OpenCode via WSL", 14/09/2026):** todo `.py`/`.md` do projeto é **UTF-8 sem BOM**; ferramentas que reescrevem encoding por fora (PowerShell, edição via WSL com locale divergente) já corromperam caracteres — validar com `ast.parse(open(..., encoding='utf-8').read())` após qualquer alteração e revisar o diff antes de seguir (mesma mitigação da integridade do `main.py` acima).
- **Toggles `hidden sm:*`/`md:*` não funcionam neste stack (sessão header 14/09/2026):** o `tailwindcss.min.js` embutido no NiceGUI 3.15 resolve `hidden` acima de `sm:flex`/`md:block` mesmo em 1280 px — usar um único elemento sempre visível com `max-width` + ellipsis em vez de dois elementos desktop/mobile.
- **Scripts auxiliares e CWD (sessão 14/09/2026):** `fresh_install_test*.py`/`diag_db.py` criavam `.db` de 0 bytes na pasta anterior quando rodados com outro CWD — todo script standalone resolve caminhos por **absoluto a partir da raiz** (`_RAIZ`), nunca por CWD relativo.

## Sugestão de expansão

Adicionar retrospectivas por fase, decisões de arquitetura (ADR) e melhorias de desempenho (WAL, ProcessPoolExecutor).

Veja [Arquitetura](../arquitetura_de_software_das/index.md) e [Padrões de Codificação](../padroes_codificacao/index.md).
