# Filas — `mod_filas` (Esqueleto TV)

> Queue/call manager skeleton: routes `/filas` + `/tv` (public) · own database `db_mod_filas.db` · tables `tb_fila`/`tb_chamada`/`tb_config_filas` · next password A000→A001 · TV 3s + beep.

---

# Filas — `mod_filas` (Esqueleto TV)

> Gestor de filas/chamadas (esqueleto, TV): rotas `/filas` + `/tv` (pública) · banco próprio `db_mod_filas.db` · tabelas `tb_fila`/`tb_chamada`/`tb_config_filas` · próxima senha A000→A001 · TV 3s + beep.

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
- `mostrar_tv()` (`telas.py:72-93`): `w-full h-screen bg-black text-white`, `lbl_senha` 10vw + `lbl_guiche` 4vw + `FILA — AGUARDE CHAMADA`; `ui.timer(3.0, refresh)` + `refresh()` imediato + beep `AudioContext`.
- Rota `/tv` pública (sem `pagina_restrita`) — proposital para TV sem sessão.

## Regras de negócio relevantes

- **Incremento** (`gerar_senha`): `SELECT senha_atual` → regex `([A-Za-z]*)(\d+)` → `pref` + `num+1:03d` (ex.: `A000→A001`, sem letra → `A001`); `UPDATE tb_fila` + `INSERT tb_chamada (..., SELECT guiche FROM tb_fila, ...)` + `audit_log` `gerar_senha`.
- **Última chamada**: `SELECT senha,guiche,chamado_em ORDER BY id DESC LIMIT 1`; histórico `listar_chamadas(limite)`.
- **LGPD**: `remover_vinculos_usuario` (esqueleto 0), `renomear_usuario` (`UPDATE tb_chamada SET chamado_por`).

## Integrações com o núcleo

`autenticacao.validar_acesso_modulo`/`perfil_global_de`, `banco_conexao.conexao`, `tema_modulo.ler_tema`, `ui_comum.botao`, `rotinas.painel_backup`. Auditoria → `tb_auditoria_filas`. `MODULOS_SISTEMA`/`MODULOS_BD`/`PADROES_TEMA` com `filas`.

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
| TV `/tv` 3s + beep | Implementado |
| Admin `/admin/filas` | Implementado (aparência + backup) |
| Regras avançadas (prioridade etc.) | Pendente (esqueleto) |
