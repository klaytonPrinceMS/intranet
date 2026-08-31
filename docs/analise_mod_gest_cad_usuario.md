# Gestão de Usuários — `mod_gest_cad_usuario`

> User management module: route `/users` (key `usuarios`) · own database `db_mod_gest_cad_usuario.db` · soft CRUD, bcrypt, multi-profile/role, revocable sessions, cross-module LGPD cleanup.

---

# Gestão de Usuários — `mod_gest_cad_usuario`

> Módulo de gestão de usuários: rota `/users` (chave `usuarios`) · banco próprio `db_mod_gest_cad_usuario.db` · soft CRUD, bcrypt, múltiplos perfis/papéis, sessões revogáveis, limpeza cruzada LGPD.

## Propósito

Soft CRUD completo de usuários: criar, editar, renomear, bloquear/desbloquear, excluir logicamente (com motivo) e excluir permanentemente (LGPD). Gerencia perfis globais (`comum`, `administrador_modulo`, `administrador_geral`) e papéis granulares por módulo, além da visualização e revogação de sessões ativas de todo o sistema. Acesso restrito ao administrador geral ou administrador do módulo `usuarios`.

## Banco próprio

Conexão com WAL + `foreign_keys=ON`. Criador vigente: `init_db()` em `manipulador_bd.py:37-156`, executado no import do módulo e pelo bootstrap central.

**`tb_usuarios`** (após migrações):

| Coluna | Observação |
|:---|:---|
| `id` | PK AUTOINCREMENT — renomeio de login preserva o ID |
| `user_nome` | UNIQUE NOT NULL |
| `user_senha` | hash bcrypt |
| `user_email`, `user_fone` | contato |
| `user_perfil` | global, default `comum` |
| `user_ativo` | 0/1 |
| `data_cadastro` | timestamp |
| `modulo_acesso` | legado CSV (migrado para linhas) |
| `user_deletado` | soft delete |
| `user_nome_completo` | nome social/tratamento (Decreto 8.727/2016) |
| `user_motivo_exclusao` | motivo da exclusão lógica |

**`tb_acesso_usuario`** — vínculo usuário×módulo×papel (`UNIQUE(user_nome, modulo_chave)`, FK CASCADE para `tb_usuarios`); `modulo_chave` é texto livre — origem dos vínculos órfãos.

⚠️ `tb_modulo_perfil` existe apenas no `criador_bd.py`, que é **código legado/morto**: usa a conexão do banco **central** (criaria as tabelas em `db_mod_intranet.db`) e não é importado por ninguém.

## Fluxo da tela

- Gate duplo: `administrador_geral` ou `eh_admin_do_modulo(user,'usuarios')`; caso contrário painel "Acesso restrito".
- Abas: **Usuários** | **Excluídos** (só admin geral) | **Sessões Ativas**.
- Busca instantânea (debounce 150 ms) insensível a acentos/pontuação, localiza também pelo nome completo/social.
- Lista com filtros situação/perfil, paginação client-side 10/20/50/100 e badges: `ativo`, `bloqueado`, `excluído (soft)`, `senha provisória`. Ações ocultas na própria linha do ator ("use Meu Perfil").
- Diálogos: Novo usuário (senha provisória mín. 6 + seletores de acesso por módulo registrado, inativos marcados INDISPONÍVEL), Editar (login travado p/ master; aplica só diferenças), Redefinir senha, Excluir lógico (motivo ≥3 chars obrigatório), Exclusão definitiva (digitar o login; aviso LGPD listando a limpeza cruzada).
- Aba Sessões Ativas: todas as vivas do sistema (IP, dispositivo, MAC em tooltip) com encerramento individual/em massa; diálogo por usuário mostra histórico das 10 últimas com duração calculada.

## Regras de negócio relevantes

- **Exclusão em dois estágios**: estágio 1 = soft delete com motivo, encerra sessões, reversível ("Restaurar" limpa o motivo); estágio 2 = DELETE físico, exclusivo da aba Excluídos (admin geral revalidado no backend).
- **Limpeza cruzada LGPD**: exclui postagens/comentários do Blog, remove arquivos/cota do editorPDF e anonimiza autoria de empenhos como "(usuário excluído)". Auditoria sempre preservada. Nota: implementa cross-query SQLite ad-hoc aos bancos vizinhos (contrariando a convenção geral do projeto).
- **Proteções**: vedado agir sobre a própria conta (bloquear/excluir/rebaixar); `master` não é renomeado nem excluído; último admin geral ativo protegido contra **exclusão definitiva**; RF-26: `editar_usuario`/`bloquear_usuario` bloqueiam **rebaixar ou bloquear** o último `administrador_geral` ativo quando o ator é OUTRO admin (`manipulador_bd.py:292-305`).
- **Senha provisória**: criação/redefinição marcam `forcar_troca`; redefinição derruba todas as sessões. O admin digita a senha manualmente (não é gerada aleatória como diz o PLANO 2.5).
- **Auto-cura do master**: enquanto a senha for `master`, a troca é rearmada a cada boot (`manipulador_bd.py:136-156`) — corrige o roadmap do README que dizia o contrário.

## Integrações com o núcleo

Importa `autenticacao` (hash/verificação de senha, papéis, troca pendente), `get_connection` central e `audit_log`. Ações auditadas: `criar_usuario`, `editar_usuario`, `renomear_usuario`, `alterar_senha`, `soft_delete`, `excluir_definitivo`, `definir_acesso`, `remover_acesso`, `encerrar_sessao`, `encerrar_todas_sessoes`. Escreve/lê diretamente `tb_sessoes` central. Nenhuma chave `tb_config` usada.

## Pontos de atenção

- `criador_bd.py` é morto e aponta para o banco central — não executar.
- `listar_vinculos_orfaos()` existe mas não é chamada pela tela (órfãos aparecem apenas como badge INDISPONÍVEL nos seletores).
- Renomear usuário replica o nome nas tabelas dependentes e nas sessões centrais.

## Status — Fases 2 e 2.5 do PLANO.md

**Implementado:** CRUD completo (criar, editar, renomear, bloquear/desbloquear, soft delete, exclusão definitiva LGPD); hash **bcrypt**; múltiplos perfis globais (`comum`, `administrador_modulo`, `administrador_geral`) e papéis granulares por módulo (`tb_acesso_usuario`); seed `master`/`master` com troca obrigatória de senha no 1º login (auto-cura idempotente em boot); senha provisória (`forcar_troca`); nome completo/social (`user_nome_completo`, Decreto 8.727/2016); exclusão em 2 estágios com motivo; limpeza cruzada LGPD (Blog/editorPDF/empenhos anonimizados, auditoria preservada); proteções (vedado agir sobre a própria conta, `master` não renomeável/excluível); lista paginada (10/20/50/100), busca instantânea (debounce 150 ms), filtros situação/perfil e badges (ativo/bloqueado/excluído/senha provisória); alerta de módulos inexistentes (vínculos órfãos como INDISPONÍVEL); gestão/revogação de sessões ativas + histórico; auditoria central LGPD.

**Desvios aceitáveis:** tabela chama-se `tb_usuarios` (não `tb_usuario`); não há tabela `tb_perfil` separada; rota real é `/users` (não `/gestao-usuarios`).

**Parcial/Pendente (RF-26 finalizado e documentado; abaixo os gaps reais):**

- **Proteção do último `administrador_geral` contra bloqueio/rebaixamento por OUTRO admin** (RF-26): `editar_usuario`/`bloquear_usuario` bloqueiam rebaixar ou bloquear o último `administrador_geral` ativo quando o ator é outro admin — **REALIZADO** (`mod_gest_cad_usuario/manipulador_bd.py`).
- Testes `testes/teste_fluxo_autenticacao.py` e `testes/teste_fluxo_permissoes.py` citados na Fase 2.5 não existem (há apenas `test/test_fase1_login.py` e `test/validar_fase1_login.py`).
- Senha provisória aleatória revelada ao admin não implementada (o admin digita a senha manualmente).

### Adições recentes (26/08)

- **Aba "Administração"** (exclusiva do admin geral, nas tabs existentes): bloco **Aparência** (prefixo usuarios_* — cor do botão/texto, fundo da página, cor do título, tamanho via ui.color_input; a cor do botão também define a primária da tela) e **config específica**: usuarios_senha_min (política de senha mínima, aplicada em criar_usuario/alterar_senha_admin via senha_minima()). Salvo via set_config, vale sem reiniciar.
- **Versionamento**: versao_modulo:usuarios = 1.0.260827 (seed em conexao_bd.init_db()), exibido no rodapé em /users (rota → chave usuarios).
