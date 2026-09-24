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
- **`tb_acesso_usuario`** — vínculo usuário×módulo×papel (`UNIQUE(user_nome, modulo_chave)`, FK CASCADE para `tb_usuarios`); `modulo_chave` é texto livre — origem dos vínculos órfãos (ver `listar_vinculos_orfaos(chaves_ativas)`; na tela aparecem como badge `INDISPONÍVEL` nos seletores). Coluna `flags` (JSON TEXT, default `'{}'`) guarda permissões finas por vínculo.

**Flags finas (JSON por vínculo)** — catálogo `FLAGS_PERMISSAO`: `blog.publicar`, `blog.comentar`, `blog.configurar`. API: `obter_flags(user, modulo)` (fail-soft `{}`), `definir_flags(ator, user, modulo, flags)` (valida allowlist, exige vínculo prévio) e `tem_flag(user, modulo, flag)` (admin global/modular passa pelo papel). `duplicar_usuario` replica flags da origem junto com os papéis.

⚠️ `tb_modulo_perfil` existe apenas no `bd_criador.py` — **legado/morto** (aponta para o banco central); não confiar.

## Funcionalidades

- **CRUD soft**: criar (senha vazia/None → `123456` padrão inicial 18/09/2026 + mín. 6 + `forcar_troca`), editar (aplica só diferenças; login travado para `master`), renomear (replica em dependentes), bloquear/desbloquear, excluir em 2 estágios (soft com motivo ≥ 3 chars → DELETE físico, liberado nas linhas de excluídos via busca "excluído" **ou filtro Situação = Excluídos**).
- **Busca instantânea** (debounce 150 ms) insensível a acentos, com filtros situação/perfil e paginação 10/20/50/100. **Barra superior inline sem quebra 18/09/2026** (`telas.py:98-115` `flex-nowrap gap-4`, tabs `shrink overflow-x-auto`, busca `width:min(46%,620px) flex-nowrap shrink-0`). Busca em **todos os campos** (ID, login, perfil, e-mail, telefone, módulos:papel, nome completo) + palavras-chave de estado ("provisório", "bloqueado", "sessão", "excluído"). Filtro **Situação** (`SIT_OPCOES`) agora com 4 opções: `Todas`, `Ativos`, `Bloqueados`, **`Excluídos`** (`data-testid=usuarios-filtro-situacao`, `min-w-[170px]`, `tooltip` "Filtra por situação: Ativos, Bloqueados ou Excluídos (soft-delete)" — `telas.py:293`); lógica: `sit==excluidos` → só `user_deletado=1`; senão excluídos só entram quando `termo` contém `exclu` e `sit==""` (18/09/2026 `18690cb`). **A aba Excluídos foi removida** (redundante — substituída pelo filtro). Ordenação A→Z (nome/tratamento) ou numérica (ID) via seletor. **Senha padrão ao criar/duplicar** vazia caiu em `123456` (`bd_manipulador.py:366` + `telas.py:585/850`).
- **Papéis por módulo**: seletores de acesso com módulos inativos marcados INDISPONÍVEL (vínculos órfãos via `listar_vinculos_orfaos`). Tooltip no nome de tratamento expõe todos os campos (login, perfil, situação, contato, cadastro, acessos com nomes de exibição + badge de papel) — exibição compacta 4 colunas (ID | Tratamento | Senha provisória | Ações).
- **Duplicar usuário** (`duplicar_usuario` + `_dlg_duplicar`): novo login herda perfil global, papéis por módulo e flags finas da origem (pré-selecionados, ajustáveis antes de salvar).
- **Sessões Ativas**: todas as vivas do sistema lidas do `tb_sessoes` **central** (`id, usuario, modulo, login_timestamp, cookie_hash, ip, dispositivo, mac, logout_timestamp`; abertas = `logout_timestamp IS NULL`), com IP/dispositivo/MAC em tooltip, encerramento individual (`encerrar_sessao`) / em massa (`encerrar_todas_sessoes`, `_fechar_sessoes_central` em bloqueio/exclusão/reset) e histórico das 10 últimas encerradas por usuário (`listar_historico_sessoes`, duração calculada na tela). Agregados: `contar_sessoes_ativas(usuario)`, `sessoes_ativas_por_usuario()`.
- **Limpeza cruzada LGPD**: exclui postagens/comentários do Blog, remove arquivos/cota do Editor PDF e anonimiza empenhos como "(usuário excluído)"; auditoria sempre preservada.
- **Proteções**: vedado agir sobre a própria conta; `master` não é renomeado/excluído; último `administrador_geral` ativo protegido contra rebaixamento/bloqueio por outro admin (RF-26).
- **Aba Administração** (admin geral): card padrão **"Configurações de cores"** (`usuarios_*` — `cor_botao`, `cor_texto_botao`, `cor_fundo`, `cor_titulo`, `btn_tamanho`, `texto_header`) + card "Configurações específicas" com a política `usuarios_senha_min`; card "Configurações de cores" padronizado via `tema_modulo.bloco_aparencia` (prévia ao vivo, rodapé 2 botões) e tela em área cheia (`w-full`). **Padrão próprio do tema de botões (06/09)**: os campos de botão exibem o rótulo "vazio = padrão do módulo" (`tema_modulo.bloco_aparencia` — `tema_modulo.py:319-322`) — com `usuarios_cor_botao`/`usuarios_cor_texto_botao`/`usuarios_btn_tamanho` vazios (padrão atual do banco), os botões usam o padrão do PRÓPRIO módulo (`PADROES_TEMA["usuarios"]` = `#000000` — sem herança do tema do sistema); os inputs mostram o valor resolvido e o "Restaurar padrão" grava `""` para voltar ao padrão do próprio módulo. O cabeçalho usa `chave_modulo="usuarios"` (`telas.py:97`): a borda de destaque é a **mesma cor dos botões do módulo** (`usuarios_cor_botao`, vazia = padrão do próprio módulo), título/fundo seguem o tema — sem hex hardcoded. **Cupê "Edição do módulo" restaurado (06/09)**: `campo_modulo(ator, "usuarios")` (`telas.py:705`) volta a permitir ao admin renomear o módulo, trocar o ícone e ativar/desativar (havia sido removido acidentalmente; a edição também permanece em `/configuracoes`).
- **Responsividade (RNF-UI-01, 09/2026 — auditado 320/768/1024 `kbp-web-design`)**: barra superior `flex-nowrap` → `flex-wrap`, tabs `overflow-x-auto`, busca `flex-1 min-w` (`campo_busca` `grow min-w-[220px]`), dialogs `w-full max-w`; tabelas parcialmente com `overflow-x-auto`; proposta P0/P1/P2 por `container`/`row`/`grid` (header `flex-wrap` `truncate`, filtros `sm:grid-cols-2`).
- **Versionamento**: `versao_modulo:usuarios = 1.0.260918` no rodapé de `/users`.

## Permissões

| Ação | `comum` | Admin `usuarios` | `administrador_geral` |
|:---|:---:|:---:|:---:|
| Ver tela de gestão | ✗ | ✓ | ✓ |
| Criar/editar/bloquear/renomear | ✗ | ✓ | ✓ |
| Exclusão definitiva (via busca "excluído") | ✗ | ✗ | ✓ |
| Encerrar sessões | ✗ | ✓ | ✓ |
| Aba Administração | ✗ | ✗ | ✓ |

## Rota e integrações

- Rota: `/users` (chave `usuarios`) — gate duplo: `administrador_geral` ou `eh_admin_do_modulo(user, 'usuarios')`. Rota `/admin/usuarios` — painel `mostrar_administracao` em `telas_administracao.py` (só admin geral): cupê de cores `bloco_aparencia` + `usuarios_senha_min` (4–32, padrão 6, via `senha_minima()`/`set_config`, vale sem restart) + `painel_backup`.
- Importa `autenticacao` (hash/papéis), `get_connection` central e `audit_log`; escreve/lê `tb_sessoes` central.
- Seed idempotente em `init_db` (fonte única deste módulo): conta nativa `master` (`administrador_geral`) e contas de QA (`qacomum` perfil `comum`, `qamaster` `administrador_geral`); credenciais provisórias com **troca forçada no 1º login** (`marcar_trocar_senha`, auto-cura do `master` a cada boot) e renomeação obrigatória do `master` (`marcar_trocar_credenciais`). Por segurança, os valores das senhas provisórias **não são publicados nesta doc** — ver `bd_manipulador.py` (contexto interno).
- Acesso padrão de todo usuário novo (`ACESSO_PADRAO_NOVO_USUARIO`): papel `comum` em `editar_pdf`, `empenhos` e `solicita_impressao`; `usuarios`/`auditoria`/`blog` nascem sem vínculo (concessão manual do admin).

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