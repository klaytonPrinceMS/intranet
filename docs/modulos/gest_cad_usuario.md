# User Management Module — `mod_gest_cad_usuario`

> User management module: route `/users` (key `usuarios`) · own database `db_mod_gest_cad_usuario.db` · soft CRUD, bcrypt, multi-profile/role, revocable sessions, cross-module LGPD cleanup.

---

# Módulo Gestão de Usuários — `mod_gest_cad_usuario`

> Módulo de gestão de usuários: rota `/users` (chave `usuarios`) · banco próprio `db_mod_gest_cad_usuario.db` · soft CRUD, bcrypt, múltiplos perfis/papéis, sessões revogáveis, limpeza cruzada LGPD.

## Propósito

Soft CRUD completo de usuários: criar, editar, renomear, bloquear/desbloquear, excluir logicamente (com motivo) e excluir permanentemente (LGPD). Gerencia perfis globais (`comum`, `administrador_modulo`, `administrador_geral`) e papéis granulares por módulo, além de visualizar/revogar sessões ativas de todo o sistema. Acesso restrito ao administrador geral ou administrador do módulo `usuarios`.

## Banco de dados

Criador vigente: `init_db()` em `bd_manipulador.py:61-215` (executado no import e pelo bootstrap central).

- **`tb_usuarios`**: `id` PK AUTOINCREMENT, `user_nome` UNIQUE, `user_senha` (bcrypt), `user_email`, `user_fone`, `user_perfil`, `user_ativo`, `data_cadastro`, `user_deletado`, `user_nome_completo` (nome social, Decreto 8.727/2016), `user_motivo_exclusao`.
- **`tb_acesso_usuario`**: vínculo `usuário × módulo × papel` (`UNIQUE(user_nome, modulo_chave)`, FK CASCADE).

⚠️ `tb_modulo_perfil` existe apenas no `bd_criador.py` — **legado/morto** (aponta para o banco central); não confiar.

## Funcionalidades

- **CRUD soft**: criar (senha provisória mín. 6 + `forcar_troca`), editar (aplica só diferenças; login travado para `master`), renomear (replica em dependentes), bloquear/desbloquear, excluir em 2 estágios (soft com motivo ≥ 3 chars → DELETE físico, liberado nas linhas de excluídos via busca "excluído").
- **Busca instantânea** (debounce 150 ms) insensível a acentos, com filtros situação/perfil e paginação 10/20/50/100. Busca em **todos os campos** (ID, login, perfil, e-mail, telefone, módulos:papel, nome completo) + palavras-chave de estado ("provisório", "bloqueado", "sessão", "excluído"). Buscar "excluído" revela soft-deleted na lista — **a aba Excluídos foi removida** (redundante). Ordenação A→Z (nome/tratamento) ou numérica (ID) via seletor.
- **Papéis por módulo**: seletores de acesso com módulos inativos marcados INDISPONÍVEL (vínculos órfãos). Tooltip no nome de tratamento expõe todos os campos (login, perfil, situação, contato, cadastro, acessos com nomes de exibição + badge de papel) — exibição compacta 4 colunas (ID | Tratamento | Senha provisória | Ações).
- **Sessões Ativas**: todas as vivas do sistema (IP, dispositivo, MAC em tooltip), encerramento individual/em massa e histórico das 10 últimas por usuário.
- **Limpeza cruzada LGPD**: exclui postagens/comentários do Blog, remove arquivos/cota do Editor PDF e anonimiza empenhos como "(usuário excluído)"; auditoria sempre preservada.
- **Proteções**: vedado agir sobre a própria conta; `master` não é renomeado/excluído; último `administrador_geral` ativo protegido contra rebaixamento/bloqueio por outro admin (RF-26).
- **Aba Administração** (admin geral): card padrão **"Configurações de cores"** (`usuarios_*` — `cor_botao`, `cor_texto_botao`, `cor_fundo`, `cor_titulo`, `btn_tamanho`, `texto_header`) + card "Configurações específicas" com a política `usuarios_senha_min`; card "Configurações de cores" padronizado via `tema_modulo.bloco_aparencia` (prévia ao vivo, rodapé 2 botões) e tela em área cheia (`w-full`). **Padrão próprio do tema de botões (06/09)**: os campos de botão exibem o rótulo "vazio = padrão do módulo" (`tema_modulo.bloco_aparencia` — `tema_modulo.py:319-322`) — com `usuarios_cor_botao`/`usuarios_cor_texto_botao`/`usuarios_btn_tamanho` vazios (padrão atual do banco), os botões usam o padrão do PRÓPRIO módulo (`PADROES_TEMA["usuarios"]` = `#000000` — sem herança do tema do sistema); os inputs mostram o valor resolvido e o "Restaurar padrão" grava `""` para voltar ao padrão do próprio módulo. O cabeçalho usa `chave_modulo="usuarios"` (`telas.py:97`): a borda de destaque é a **mesma cor dos botões do módulo** (`usuarios_cor_botao`, vazia = padrão do próprio módulo), título/fundo seguem o tema — sem hex hardcoded. **Cupê "Edição do módulo" restaurado (06/09)**: `campo_modulo(ator, "usuarios")` (`telas.py:705`) volta a permitir ao admin renomear o módulo, trocar o ícone e ativar/desativar (havia sido removido acidentalmente; a edição também permanece em `/configuracoes`).
- **Responsividade (RNF-UI-01, 09/2026 — auditado 320/768/1024 `kbp-web-design`)**: barra superior `flex-nowrap` → `flex-wrap`, tabs `overflow-x-auto`, busca `flex-1 min-w` (`campo_busca` `grow min-w-[220px]`), dialogs `w-full max-w`; tabelas parcialmente com `overflow-x-auto`; proposta P0/P1/P2 por `container`/`row`/`grid` (header `flex-wrap` `truncate`, filtros `sm:grid-cols-2`).
- **Versionamento**: `versao_modulo:usuarios = 1.0.260908` no rodapé de `/users`.

## Permissões

| Ação | `comum` | Admin `usuarios` | `administrador_geral` |
|:---|:---:|:---:|:---:|
| Ver tela de gestão | ✗ | ✓ | ✓ |
| Criar/editar/bloquear/renomear | ✗ | ✓ | ✓ |
| Exclusão definitiva (via busca "excluído") | ✗ | ✗ | ✓ |
| Encerrar sessões | ✗ | ✓ | ✓ |
| Aba Administração | ✗ | ✗ | ✓ |

## Rota e integrações

- Rota: `/users` (chave `usuarios`) — gate duplo: `administrador_geral` ou `eh_admin_do_modulo(user, 'usuarios')`.
- Importa `autenticacao` (hash/papéis), `get_connection` central e `audit_log`; escreve/lê `tb_sessoes` central.
- Seed `master`/`master` com **auto-cura da troca obrigatória** a cada boot (`bd_manipulador.py:168-194`).

## Testes

```bash
.venv/bin/python assets/test/teste_boot.py            # 16 verificações
.venv/bin/python assets/test/teste_fluxo_autenticacao.py  # login, troca obrigatória, sessão/auditoria (19 OK)
.venv/bin/python assets/test/teste_fluxo_permissoes.py    # perfis/papéis por módulo (13 OK)
.venv/bin/python assets/test/test_fase1_login.py
.venv/bin/python assets/test/test_fresh_install.py
```

## Pontos de atenção

- Tabela real é `tb_usuarios` (não `tb_usuario`); rota real é `/users` (não `/gestao-usuarios`).
- `bd_criador.py` é morto — não executar.
- Todos os testes de fluxo existem em `assets/test/` (local canónico; `test/` e `testes/` não existem na raiz): `teste_boot.py`, `teste_fluxo_autenticacao.py`, `teste_fluxo_permissoes.py` (Fase 2.5).

Ver [Análise do Módulo](../analise_mod_gest_cad_usuario.md).