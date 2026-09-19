# Filas — `mod_filas` (Esqueleto TV + Carrossel Notícias)

> Queue/call manager skeleton: routes `/filas` + `/tv` (public) · own database `db_mod_filas.db` · tables `tb_fila`/`tb_chamada`/`tb_config_filas` · next password A000→A001 · TV 3s + beep + **news carousel** from `mod_agregador_noticias` (`listar_para_tv` 7s/120s).

---

# Filas — `mod_filas` (Esqueleto TV + Carrossel Notícias)

> Gestor de filas/chamadas (esqueleto, TV): rotas `/filas` + `/tv` (pública) · banco próprio `db_mod_filas.db` · tabelas `tb_fila`/`tb_chamada`/`tb_config_filas` · próxima senha A000→A001 · TV 3s + beep + **carrossel de notícias** do `mod_agregador_noticias` (`listar_para_tv` 7s/120s).

## Propósito

Esqueleto do futuro gestor de chamadas com TV — já com fluxo mínimo operante (fila "Geral" + incremento + display). A título de conhecimento; regras finais (múltiplas filas, prioridade, guichês, áudio) serão iteradas sem quebrar o contrato atual.

## Banco próprio

Conexão WAL + `foreign_keys=ON` via `banco_conexao.conexao("filas")`. Criador: `init_db()` em `bd_manipulador.py:34-68`.

**`tb_fila`**: `id` PK, `nome` UNIQUE (`Geral` seed `A000`/`ativa`/`01`), `senha_atual` TEXT, `status` TEXT, `guiche` TEXT, `data_criacao`.

**`tb_chamada`**: `id` PK, `fila_id` FK CASCADE → `tb_fila`, `senha` TEXT, `guiche` TEXT (snapshot), `chamado_em` DATETIME, `chamado_por` TEXT.

**`tb_config_filas`**: `filas_modo_tv` (`1`), `filas_senha_prefixo` (`A`), `filas_guiche_padrao` (`01`).

⚠️ `bd_criador.py` legado/morto.

## Fluxo da tela

- `mostrar_tela(nome, perfil)` (`telas.py:24-71`): gate `_pode_acessar` (admin geral ou `validar_acesso_modulo(user,"filas")`), `ler_tema("filas")` + `cabecalho(chave_modulo="filas")`, dois cards: "Filas (esqueleto)" (lista + `Chamar próximo` → `gerar_senha` + `Abrir TV`) e "Última chamada (preview TV)" (ultima + histórico 5).
- `mostrar_tv()` (`telas.py:72-137`): `w-full h-screen bg-black text-white`, topo `lbl_topo` `"FILA — AGUARDE CHAMADA"` + `lbl_senha` 10vw + `lbl_guiche` 4vw; **rodapé notícias** `card bg-grey-900 min-height:18vh` com `lbl_n_titulo` 1.6vw + `lbl_n_desc` 1vw + `lbl_n_fonte`; `ui.timer(3.0, refresh_chamada)` + `ui.timer(7.0, _mostrar_noticia)` + `ui.timer(120.0, carregar_noticias)` + `carregar_noticias()` imediata (`listar_para_tv` 10); `habilitado()==False` → placeholder desabilitado; vazio → placeholder aguarde. Beep `AudioContext` no `refresh_chamada`.
- Rota `/tv` pública (sem `pagina_restrita`) — proposital para TV sem sessão, agora com **carrossel de notícias** do Agregador.

## Regras de negócio relevantes

- **Incremento** (`gerar_senha`): `SELECT senha_atual` → regex `([A-Za-z]*)(\d+)` → `pref` + `num+1:03d` (ex.: `A000→A001`, sem letra → `A001`); `UPDATE tb_fila` + `INSERT tb_chamada (..., SELECT guiche FROM tb_fila, ...)` + `audit_log` `gerar_senha`.
- **Última chamada**: `SELECT senha,guiche,chamado_em ORDER BY id DESC LIMIT 1`; histórico `listar_chamadas(limite)`.
- **LGPD**: `remover_vinculos_usuario` (esqueleto 0), `renomear_usuario` (`UPDATE tb_chamada SET chamado_por`).

## Integrações com o núcleo

`autenticacao.validar_acesso_modulo`/`perfil_global_de`, `banco_conexao.conexao`, `tema_modulo.ler_tema`, `ui_comum.botao`, `rotinas.painel_backup`. Auditoria → `tb_auditoria_filas`. `MODULOS_SISTEMA`/`MODULOS_BD`/`PADROES_TEMA` com `filas`. **Integração Agregador**: `mod_filas/telas.py:103-136` consome `mod_agregador_noticias.bd_manipulador.listar_para_tv(limite=10)` → carrossel título+descrição (`7s` rotate, `120s` reload) no rodapé da TV (`bg-grey-900`). Ver `mod_agregador_noticias`.

## Pontos de atenção

- Esqueleto — sem múltiplas filas dinâmicas ainda; `status`/`guiche` já previstos para expansão.
- `/tv` pública — adicionar gate se expor fora da rede interna.
- `tb_chamada.guiche` snapshot — não retroage.

## Status

| Item | Situação |
|:---|:---|
| Banco WAL + seed `Geral` | Implementado |
| `gerar_senha` + `ultima_chamada` | Implementado |
| Painel `/filas` + preview | Implementado |
| TV `/tv` 3s + beep + carrossel notícias (Agregador) | Implementado (`mostrar_tv` `noticias_tv` 7s/120s + `listar_para_tv`) |
| Admin `/admin/filas` | Implementado (aparência + backup) |
| Regras avançadas (prioridade etc.) | Pendente (esqueleto) |
| Integração TV Agregador | Implementado (19/09/2026) |
