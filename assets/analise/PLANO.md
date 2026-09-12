# PLANO DE IMPLEMENTAÇÃO

> Checklist rastreável por fase. **Marcar `[x]` cada item concluído** para permitir retomada após interrupção. Versionamento: `1.0.AAMMDD`. Não executar `git commit` (responsabilidade do autor).
> Antes de Qualquer fase, obrigatorio, garantir que caso os bancos de dados db_mod_blog, db_mod_edit_pdf, db_modgest_cad_usuario, db_mod_intranet, db_mod_nomear_empenho, ou qualquer outro banco de dados nao exista na rais do sistema onde o script ou o exetuvel gerado no futuro estiver rodanto tiver os bancos de dados deve ser criado os bancos de dados do zero, e para o usuario deve ser inserio sempre o usuario master senha master inicialmente com permissao de administrador geral 

> **Todos os itens foram verificados em 11/09, implementados e documentados, e removidos deste plano.** Fases 0–9 concluídas. Documentação de referência: `docs/` (`analise_mod_*.md`, `modulos/*.md`, `arquitetura.md`, `requisitos.md`, `plano_de_projeto/index.md`).

> **4b (PLANO)** Quarentena e regras dinâmicas — `promover_quarentena` (alias de `mover_quarentena`), `reprocessar_fila` em lote sem reiniciar (botão "Reprocessar fila", `data-testid=empenhos-reprocessar-fila`), reprocessamento individual, separação de múltiplos documentos, regex dinâmicas validadas (`re.compile`, `REGEX_MAX_LEN=200`) e aplicadas sem reiniciar — **implementado e documentado** em `docs/analise_mod_renomear_empenho.md` / `docs/modulos/renomear_empenho.md` / `docs/manual_de_uso_renomear_empenho/index.md`.

> **4c (PLANO)** Organizador físico — `mod_renomear_empenho/organizadorPasta/caixa_NN/sub_X` com ~200 páginas por subpasta, 4 subpastas por caixa (configuráveis via `tb_config`), capas `capa.txt` + `capa.pdf` por caixa e `matrizDeDocumentos.txt` + `matrizDeDocumentos.pdf` geral, `validar_presenca_matriz` — **implementado e documentado** nos mesmos arquivos. Arquivo legado `mod_renomear_empenho_organizador.py` não existe (lógica em `bd_manipulador.py`, conforme AGENTS.md).

