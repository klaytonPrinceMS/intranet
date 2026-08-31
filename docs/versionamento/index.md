# Versioning — Intranet Modular

> Versioning scheme and current module versions. Format: `1.0.AAMMDD` (major.minor.date).

---

# Versionamento — Intranet Modular

> Esquema de versionamento e versões atuais dos módulos. Formato: `1.0.AAMMDD` (major.menor.data).

## Padrão

- `1` — mudanças de paradigma de projeto.
- `0` — mudanças complexas.
- `AAMMDD` — ano, mês e dia de alterações pontuais.

Ex.: `1.0.260829` = 29/ago/2026.

## Versões de módulo (semeadas em `tb_config`)

- `mod_solicita_impressao` — `versao_modulo:solicita_impressao = 1.0.260829` (seed Fase 7).
- Demais módulos versionados conforme seu `AAMMDD` de alteração (ver `analise_mod_*.md`).

## Versionamento do produto

- README: `version-1.0.260827` (badge).
- Build MkDocs em `site/`, montado em `/documentacao`.

Veja [Registro de Mudanças](../registro_de_mudancas/index.md) para o histórico de alterações.
