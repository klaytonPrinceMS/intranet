# Versioning — Intranet Modular

> Versioning scheme and current module versions. Format: `1.0.AAMMDD` (major.minor.date).

---

# Versionamento — Intranet Modular

> Esquema de versionamento e versões atuais dos módulos. Formato: `1.0.AAMMDD` (major.menor.data).

## Padrão

- `1` — mudanças de paradigma de projeto.
- `0` — mudanças complexas.
- `AAMMDD` — ano, mês e dia de alterações pontuais.

Ex.: `1.0.260908` = 08/set/2026.

## Versões de módulo (semeadas em `tb_config`)

- Todos os módulos — `versao_modulo:<chave> = 1.0.260908` (versão única desde 08/09; migração `migracao_padronizacao_260908` atualiza bancos existentes).
- Demais módulos versionados conforme seu `AAMMDD` de alteração (ver `analise_mod_*.md`).

## Versionamento do produto

- README: `version-1.0.260908` (badge).
- Build MkDocs em `site/`, montado em `/documentacao`.

Veja [Registro de Mudanças](../registro_de_mudancas/index.md) para o histórico de alterações.
