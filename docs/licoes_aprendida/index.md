# Lessons Learned — Intranet Modular

> Lessons learned during development. Seed document — to be expanded as the team records post-mortems and improvements.

---

# Lições Aprendidas — Intranet Modular

> Lições aprendidas durante o desenvolvimento. Documento-semente — expandir com registros de post-mortem e melhorias.

## Lições registradas (semente)

- **Integridade de `main.py`:** edições via PowerShell corromperam caracteres (`.`→`..`, `.`→`~`, `_`→`-`, `,`→`;;`). Mitigação: validar todo `.py` com `ast.parse` e revisar diffs.
- **`criador_bd.py` é legado/morto:** aponta para banco central e não reflete o banco por módulo. Usar `manipulador_bd.py` como fonte de verdade.
- **Sanitização de Blog:** `nh3` deve ser aplicado na gravação **e** na renderização para prevenir XSS.
- **Rastro de auditoria:** toda escrita relevante (incluindo PDF) deve registrar em `tb_auditoria` com `hash_arquivo` (SHA-256) para conformidade LGPD.
- **Ambiente virtual:** preferir `.venv/bin/python` (Linux) / `Scripts\python.exe` (Windows) para evitar conflitos de dependência.

## Sugestão de expansão

Adicionar retrospectivas por fase, decisões de arquitetura (ADR) e melhorias de desempenho (WAL, ProcessPoolExecutor).

Veja [Arquitetura](../arquitetura_de_software_das/index.md) e [Padrões de Codificação](../padroes_codificacao/index.md).
