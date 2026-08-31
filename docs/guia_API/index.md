# API Guide — Intranet Modular

> Routes (NiceGUI pages), key functions with `file:line` references, and per-module database tables. In case of conflict, the executable code prevails.

---

# Guia de API — Intranet Modular

> Rotas (páginas NiceGUI), funções-chave com referência `arquivo:linha` e tabelas de banco por módulo. Em conflito, prevalece o código executável.

## Rotas (páginas)

| Rota | Módulo | Acesso |
|:---|:---|:---|
| `/login` | `mod_intranet` | público |
| `/` | `mod_intranet` | usuários ativos |
| `/configuracoes` | `mod_intranet` | `administrador_geral` |
| `/users` | `mod_gest_cad_usuario` | admin de módulo / geral |
| `/blog` | `mod_blog` | comum (leitura) / admin (escrita) |
| `/edit-pdf` | `mod_edit_pdf` | liberados (aba Admin: geral) |
| `/renomear-empenho` | `mod_renomear_empenho` | liberados |
| `/auditoria` | `mod_auditoria` | `administrador_geral` |
| `/solicita-impressao` | `mod_solicita_impressao` | liberados |

## Funções-chave

### Autenticação (`mod_intranet/autenticacao.py`)
- `autenticar(user_nome, senha)` — `:179`
- `gerar_hash_senha` / `verificar_senha` — `:161` / `:157`
- `registrar_login` — `:224`; `sessao_ativa` — `:257`; `registrar_logout` — `:276`
- `precisa_trocar_senha` — `:299`; `trocar_senha_propria` — `:336`
- `registrar_modulo` — `:87`
- `CHAVE_POR_ROTA` — mapeamento rota → chave de módulo

### Bootstrap
- `inicializar_bancos()` (`mod_intranet/mod_intranet_inicializacao_bd.py`) — cria o central antes de importar `mod_gest_cad_usuario`.

### Gestão de usuários (`mod_gest_cad_usuario/manipulador_bd.py`)
- Seed `master` com auto-cura de troca obrigatória — `:136-156`

## Tabelas por módulo

- **Central** `db_mod_intranet.db`: `tb_auditoria`, `tb_config`, `tb_sessoes`, `tb_modulos`.
- `db_mod_gest_cad_usuario.db`: `tb_usuarios`.
- `db_mod_blog.db`: postagens/comentários (sanitizados por `nh3`).
- `db_mod_edit_pdf.db`: registros de arquivos (`hash_arquivo` SHA-256).
- `db_mod_renomear_empenho.db`: `tb_indexador_pesquisa_fts5`.
- `db_mod_solicita_impressao.db`: solicitações de impressão.
- `mod_auditoria`: sem banco próprio (lê o central).

Veja [Padrões de Codificação](../padroes_codificacao/index.md) para o modelo de módulo.
