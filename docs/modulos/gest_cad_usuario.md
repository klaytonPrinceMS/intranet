# User Management Module — `mod_gest_cad_usuario`

> User management module: route `/users` (key `usuarios`) · own database `db_mod_gest_cad_usuario.db` · soft CRUD, bcrypt, multi-profile/role, revocable sessions, cross-module LGPD cleanup.

---

# Módulo Gestão de Usuários — `mod_gest_cad_usuario`

> Módulo de gestão de usuários: rota `/users` (chave `usuarios`) · banco próprio `db_mod_gest_cad_usuario.db` · soft CRUD, bcrypt, múltiplos perfis/papéis, sessões revogáveis, limpeza cruzada LGPD.

## Propósito

Soft CRUD completo de usuários: criar, editar, renomear, bloquear/desbloquear, excluir logicamente (com motivo) e excluir permanentemente (LGPD). Gerencia perfis globais (`comum`, `administrador_modulo`, `administrador_geral`) e papéis granulares por módulo, além de visualizar/revogar sessões ativas de todo o sistema. Acesso restrito ao administrador geral ou administrador do módulo `usuarios`.

## Banco de dados

Criador vigente: `init_db()` em `manipulador_bd.py:54-156` (executado no import e pelo bootstrap central).

- **`tb_usuarios`**: `id` PK AUTOINCREMENT, `user_nome` UNIQUE, `user_senha` (bcrypt), `user_email`, `user_fone`, `user_perfil`, `user_ativo`, `data_cadastro`, `user_deletado`, `user_nome_completo` (nome social, Decreto 8.727/2016), `user_motivo_exclusao`.
- **`tb_acesso_usuario`**: vínculo `usuário × módulo × papel` (`UNIQUE(user_nome, modulo_chave)`, FK CASCADE).

⚠️ `tb_modulo_perfil` existe apenas no `criador_bd.py` — **legado/morto** (aponta para o banco central); não confiar.

## Funcionalidades

- **CRUD soft**: criar (senha provisória mín. 6 + `forcar_troca`), editar (aplica só diferenças; login travado para `master`), renomear (replica em dependentes), bloquear/desbloquear, excluir em 2 estágios (soft com motivo ≥ 3 chars → DELETE físico na aba Excluídos).
- **Busca instantânea** (debounce 150 ms) insensível a acentos, com filtros situação/perfil e paginação 10/20/50/100.
- **Papéis por módulo**: seletores de acesso com módulos inativos marcados INDISPONÍVEL (vínculos órfãos).
- **Sessões Ativas**: todas as vivas do sistema (IP, dispositivo, MAC em tooltip), encerramento individual/em massa e histórico das 10 últimas por usuário.
- **Limpeza cruzada LGPD**: exclui postagens/comentários do Blog, remove arquivos/cota do Editor PDF e anonimiza empenhos como "(usuário excluído)"; auditoria sempre preservada.
- **Proteções**: vedado agir sobre a própria conta; `master` não é renomeado/excluído; último `administrador_geral` ativo protegido contra rebaixamento/bloqueio por outro admin (RF-26).
- **Aba Administração** (admin geral): aparência (`usuarios_*`) + política `usuarios_senha_min`.
- **Versionamento**: `versao_modulo:usuarios = 1.0.260827` no rodapé de `/users`.

## Permissões

| Ação | `comum` | Admin `usuarios` | `administrador_geral` |
|:---|:---:|:---:|:---:|
| Ver tela de gestão | ✗ | ✓ | ✓ |
| Criar/editar/bloquear/renomear | ✗ | ✓ | ✓ |
| Exclusão definitiva (aba Excluídos) | ✗ | ✗ | ✓ |
| Encerrar sessões | ✗ | ✓ | ✓ |
| Aba Administração | ✗ | ✗ | ✓ |

## Rota e integrações

- Rota: `/users` (chave `usuarios`) — gate duplo: `administrador_geral` ou `eh_admin_do_modulo(user, 'usuarios')`.
- Importa `autenticacao` (hash/papéis), `get_connection` central e `audit_log`; escreve/lê `tb_sessoes` central.
- Seed `master`/`master` com **auto-cura da troca obrigatória** a cada boot (`manipulador_bd.py:136-156`).

## Testes

```bash
.venv/bin/python test/test_fase1_login.py
.venv/bin/python test/test_fresh_install.py
```

## Pontos de atenção

- Tabela real é `tb_usuarios` (não `tb_usuario`); rota real é `/users` (não `/gestao-usuarios`).
- `criador_bd.py` é morto — não executar.
- Testes `testes/teste_fluxo_autenticacao.py`/`teste_fluxo_permissoes.py` citados no PLANO não existem (há `test/test_fase1_login.py`).

Ver [Análise do Módulo](../analise_mod_gest_cad_usuario.md).