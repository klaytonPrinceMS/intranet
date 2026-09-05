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
- Abas: **Usuários** | **Sessões Ativas** | **Administração** (só admin geral). A aba **Excluídos** foi **removida**: usuários excluídos (soft) são acessados pela busca por "excluído" na aba Usuários.
- Busca instantânea (debounce 150 ms) insensível a acentos/pontuação, localiza também pelo nome completo/social.
- Lista com filtros situação/perfil, paginação client-side 10/20/50/100 e badges: `ativo`, `bloqueado`, `excluído (soft)`, `senha provisória`. Ações ocultas na própria linha do ator ("use Meu Perfil").
- Diálogos: Novo usuário (senha provisória mín. 6 + seletores de acesso por módulo registrado, inativos marcados INDISPONÍVEL), Editar (login travado p/ master; aplica só diferenças), Redefinir senha, Excluir lógico (motivo ≥3 chars obrigatório), Exclusão definitiva (digitar o login; aviso LGPD listando a limpeza cruzada).
- Aba Sessões Ativas: todas as vivas do sistema (IP, dispositivo, MAC em tooltip) com encerramento individual/em massa; diálogo por usuário mostra histórico das 10 últimas com duração calculada.

## Regras de negócio relevantes

- **Exclusão em dois estágios**: estágio 1 = soft delete com motivo, encerra sessões, reversível ("Restaurar" limpa o motivo); estágio 2 = DELETE físico, acessível nas linhas de usuários excluídos via busca "excluído" (admin geral revalidado no backend).
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

**Implementado:** CRUD completo (criar, editar, renomear, bloquear/desbloquear, soft delete, exclusão definitiva LGPD); hash **bcrypt**; múltiplos perfis globais (`comum`, `administrador_modulo`, `administrador_geral`) e papéis granulares por módulo (`tb_acesso_usuario`); seed `master`/`master` com troca obrigatória de senha no 1º login (auto-cura idempotente em boot); senha provisória (`forcar_troca`); nome completo/social (`user_nome_completo`, Decreto 8.727/2016); exclusão em 2 estágios com motivo; limpeza cruzada LGPD (Blog/editorPDF/empenhos anonimizados, auditoria preservada); proteções (vedado agir sobre a própria conta, `master` não renomeável/excluível); lista paginada (10/20/50/100), busca instantânea em todos os campos + palavras-chave de estado (debounce 150 ms), filtros situação/perfil, ordenação A→Z/numérica e exibição compacta com hover (tooltip com nomes de módulos); alerta de módulos inexistentes (vínculos órfãos como INDISPONÍVEL); gestão/revogação de sessões ativas + histórico; auditoria central LGPD.

**Desvios aceitáveis:** tabela chama-se `tb_usuarios` (não `tb_usuario`); não há tabela `tb_perfil` separada; rota real é `/users` (não `/gestao-usuarios`).

**Proteção do último `administrador_geral` contra bloqueio/rebaixamento por OUTRO admin** (RF-26): `editar_usuario`/`bloquear_usuario` bloqueiam rebaixar ou bloquear o último `administrador_geral` ativo quando o ator é outro admin — **REALIZADO** (`mod_gest_cad_usuario/manipulador_bd.py`).

## Fase 2.5 — Testes do fluxo completo

A Fase 2.5 do PLANO.md foi **concluída** com scripts standalone em `test/`
(no padrão do projeto, não em `testes/` como o PLANO chegou a citar). Todos
autocontidos (criam usuários de nome único e os removem definitivamente ao
fim — LGPD), sem destruir dados do desenvolvedor:

| Script | Cobertura | Resultado |
|:---|:---|:---|
| `test/teste_boot.py` | Bootstrap cria os bancos do zero + seed `master`; `main.py` importa; Tailwind **local** (sem CDN) + CSS custom no `/login`; HTTP real em `/login` (200 + Tailwind local) quando o servidor está no ar | 16/16 OK |
| `test/teste_fluxo_autenticacao.py` | Login → senha provisória → troca obrigatória no 1º acesso → sessão/logout (revogação) → trilha de auditoria central → soft delete → restauração | 19/19 OK |
| `test/teste_fluxo_permissoes.py` | Concessão/atualização/revogação de perfil por módulo + admin geral vê tudo (auditoria exclusiva) | 13/13 OK |

Os testes refletem o comportamento atual do núcleo:
- **Auditoria** agora é gravada no banco exclusivo `db_mod_auditoria.db` (tabela
  por módulo, ex. `tb_auditoria_blog`), e não mais na `tb_auditoria` central
  (legado migrado via `migrar_dados_existentes`).
- **Senha provisória** é digitada pelo administrador (não gerada aleatória):
  geração aleatória continua **não implementada** — desvio documentado.
- Controle granular é aplicado via `validar_acesso_modulo`/`listar_modulos_permitidos`,
  usados no menu lateral, cards do dashboard e página `/modulo/{slug}`

### Adições recentes (05/09)

Oito melhorias na tela de usuários (`mod_gest_cad_usuario/telas.py`), todas na aba **Usuários** e no diálogo de edição:

1. **Botão "Salvar alterações" no diálogo de edição** — `_dlg_editar` definia a função `salvar()` internamente, mas nunca a conectava a um botão. Adicionada linha de ações com "Cancelar" (flat) + "Salvar alterações" (primário, ícone `save`) (`telas.py:621-624`), seguindo o padrão dos diálogos Novo/Duplicar.

2. **Busca em qualquer campo** — A função `_filtrar` agora pesquisa em **todos** os campos do registro: ID numérico, login, perfil global, e-mail, telefone, string módulos:papel e nome completo/tratamento (`telas.py:236-244`). O placeholder e o tooltip do campo de busca foram atualizados para refletir a abrangência (`telas.py:108-112`).

3. **Ordenação alfabética ou numérica** — Seletor "Ordenar por" (`ORDEM_OPCOES`) na barra de filtros, com opções `A→Z (nome)` e `Numérica (ID)` (`telas.py:195`, `telas.py:282-284`). A função `_chave_ordenacao` ordena por nome de tratamento/login (alfabética, via `_norm` que ignora acentos) ou por ID (`telas.py:197-203`). Limpar filtros restaura `nome` como ordem padrão (`telas.py:286`). A ordenação é aplicada no final de `_filtrar` (`telas.py:253`).

4. **Exibição compacta** — A tabela encolheu de 8 colunas para 4: `[ID][Tratamento][Senha provisória][Ações]`, com grid `60px 1fr 150px 220px` (`telas.py:310-311`). Os demais campos (login @, perfil global, situação, e-mail, telefone, cadastro, módulos:papel) são expostos em tooltip ao passar o mouse no nome de tratamento, com ícone `info_outline` como dica visual (`telas.py:329-360`).

5. **Nomes de módulos no tooltip** — Os acessos do usuário no tooltip exibem o **nome de exibição** do módulo (via `_nomes_modulos()`, que usa `autenticacao.modulos_registrados()` com cache lazy em `_MAP_MODULOS`) ao invés da chave bruta (ex. `blog` em vez de `blog:comum`). Cada linha de acesso exibe ícone do módulo + nome + badge do papel usando `ROTULOS_PAPEL` ("Comum"/"Administrador") (`telas.py:25-34`, `telas.py:346-358`).

6. **Busca por palavras-chave de estado** — Digitar "provisório" ("provisor"), "bloqueado" ("bloque"), "sessão" ("sess") ou "excluído" ("exclu") filtra pelos estados computados: senha provisória pendente (`autenticacao.usuarios_com_troca_pendente()`), bloqueado (`user_ativo=0`), sessão ativa (`gest.sessoes_ativas_por_usuario()`) e excluído (`user_deletado=1`). As consultas extras (troca pendente, sessões) só rodam quando um token de estado está presente, evitando custo desnecessário (`telas.py:213-234`).

7. **Busca "excluído" revela excluídos + aba Excluídos removida** — Quando o termo de busca contém "exclu", a base do filtro em `_filtrar` inclui soft-deleted (`user_deletado=1`), fazendo-os aparecer na aba Usuários (`telas.py:207-211`). Como isso tornou essa aba redundante, a aba "Excluídos" foi **removida do menu** (agora são 3 abas: Usuários | Sessões Ativas | Administração). Nas linhas de excluídos que aparecem na busca, o botão de exclusão é o permanente (`delete_forever`, `_dlg_excluir_definitivo`) com aviso LGPD, mantendo também "Restaurar conta" (`telas.py:396-405`).

8. **Tabulação consistente** — O grid da tabela mudou de `60px 1fr auto` (implícito) para `60px 1fr 150px 220px` tanto no cabeçalho quanto nas linhas (`telas.py:311`, `telas.py:325`). O badge "senha provisória" virou coluna própria ao invés de ficar embutido na coluna situação, alinhando as ações de todas as linhas à mesma posição horizontal (`telas.py:362-368`).

### Adições recentes (26/08)

- **Aba "Administração"** (exclusiva do admin geral, nas tabs existentes): bloco **Aparência** (prefixo usuarios_* — cor do botão/texto, fundo da página, cor do título, tamanho via ui.color_input; a cor do botão também define a primária da tela) e **config específica**: usuarios_senha_min (política de senha mínima, aplicada em criar_usuario/alterar_senha_admin via senha_minima()). Salvo via set_config, vale sem reiniciar.
- **Versionamento**: versao_modulo:usuarios = 1.0.260827 (seed em conexao_bd.init_db()), exibido no rodapé em /users (rota → chave usuarios).
- **Edição do módulo** (`campo_modulo` do helper `mod_intranet/tema_modulo.py`): permite ao admin editar **nome de exibição, ícone e status (ativo/inativo)** do módulo de usuários em `tb_modulos`.
