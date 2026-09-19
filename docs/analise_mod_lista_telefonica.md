# Lista Telefônica — `mod_lista_telefonica`

> Phone directory / expandable organogram: route `/lista-telefonica` (key `lista_telefonica`) · own database `db_mod_lista_telefonica.db` · hierarchy Secretaria→Setor→Subsetor (generic 12 secretarias) · contacts alphabetically ordered · search by name/phone · tel: clickable on mobile · admin: branch delete, move, elevate/relegate, reorder/swap, transfer, appearance.

---

# Lista Telefônica — `mod_lista_telefonica`

> Lista telefônica / organograma expansível: rota `/lista-telefonica` (chave `lista_telefonica`) · banco próprio `db_mod_lista_telefonica.db` · hierarquia Secretaria→Setor→Subsetor (12 secretarias genéricas) · contatos em ordem alfabética · busca por nome/telefone · telefone clicável `tel:` no celular · admin: excluir ramo, mover, elevar/rebaixar, ordenar/comutar, transferir, aparência.

## Propósito

Módulo de **organograma expansível** com lista telefônica interna. O organograma base (`ORGANOGRAMA_BASE` — `bd_manipulador.py:21-75`) traz **12 secretarias genéricas** desacopladas de vínculo territorial, cada uma com setores e subsetores, servindo como semente editável. O usuário navega por Secretaria → Setor → Subsetor via selects em cascata e visualiza contatos da unidade selecionada sempre em **ordem alfabética**. A busca global localiza unidades e contatos por nome/telefone com normalização sem acentos. No celular, o telefone é **clicável** (`tel:`) com diálogo "Ligar agora".

O administrador gerencia todo o organograma (criar, mover entre ramos, elevar `setor→secretaria` e rebaixar inverso, ordenar/comutar irmãs, excluir ramo em cascata) e os contatos (incluir vinculado à base de usuários ou externo, editar, transferir entre unidades, excluir), além do cupê de aparência.

## Banco próprio

Conexão WAL + `foreign_keys=ON` via `mod_intranet/banco_conexao.conexao("lista_telefonica")`. Criador vigente: `init_db()` em `bd_manipulador.py:106-157`, executado no import (`bd_manipulador.py:603` `init_db()`) e pelo bootstrap central (`mod_intranet/bd_criador.py:64` `init_lista`).

**`tb_unidade`**:

| Coluna | Observação |
|:---|:---|
| `id` | PK AUTOINCREMENT |
| `nome` | TEXT NOT NULL |
| `tipo` | `CHECK(tipo IN ('secretaria','setor','subsetor'))` |
| `parent_id` | `REFERENCES tb_unidade(id) ON DELETE CASCADE` — NULL para secretaria (raiz) |
| `ordem` | `INTEGER DEFAULT 0` — posição entre irmãs |
| `telefone` | `TEXT DEFAULT ''` |
| `ativo` | `INTEGER DEFAULT 1` |

Índice `idx_unidade_parent(parent_id)`.

**`tb_contato`**:

| Coluna | Observação |
|:---|:---|
| `id` | PK AUTOINCREMENT |
| `unidade_id` | `REFERENCES tb_unidade(id) ON DELETE CASCADE` |
| `nome` | TEXT NOT NULL |
| `telefone` | TEXT NOT NULL DEFAULT '' |
| `user_nome` | TEXT — login vinculado da base `gest_cad_usuario` (opcional) |
| `tipo` | `CHECK(tipo IN ('vinculado','externo'))` DEFAULT `externo` — `vinculado` quando `user_nome` preenchido |
| `data_criacao` | `DATETIME DEFAULT CURRENT_TIMESTAMP` |

Índices `idx_contato_unidade(unidade_id)`, `idx_contato_nome(nome)`.

**Semente** (`bd_manipulador.py:135-155`): idempotente — `SELECT COUNT(*) FROM tb_unidade` → se 0, itera `ORGANOGRAMA_BASE` semeando secretarias (`ordem_sec` 1..12, `tipo='secretaria'`, `parent NULL`), setores (`tipo='setor'`, `parent=sec_id`, `ordem_set`) e subsetores (`tipo='subsetor'`, `parent=set_id`, `ordem_sub`). Log `info "Organograma base semeado: 12 secretarias"`.

`ORGANOGRAMA_BASE` genérico: Gabinete (Assessoria[Comunicação,Jurídico], Controle Interno), Administração (RH[Folha,Capacitação], Patrimônio e Almoxarifado[Compras,Licitações], T.I.[Suporte,Redes]), Finanças (Contabilidade, Tesouraria, Tributação[Cadastro,Fiscalização]), Saúde (Atenção Primária[ESF,Vigilância Sanitária], Assistência Farmacêutica, Regulação[Transporte Sanitário]), Educação (Pedagógico[Ensino Infantil,Fundamental], Transporte Escolar, Merenda), Obras e Infraestrutura (Engenharia[Projetos,Fiscalização], Serviços Urbanos[Limpeza,Iluminação]), Agricultura (Assistência Rural, Abastecimento), Meio Ambiente (Licenciamento, Fiscalização Ambiental), Assistência Social (CRAS, CREAS, Conselho Tutelar), Cultura (Biblioteca, Eventos), Esporte e Lazer (Esportes, Juventude), Planejamento (Projetos, Convênios).

⚠️ `bd_criador.py` é **código legado/morto**: não é importado; não executar.

## Fluxo da tela

- Gate `_pode_ver` (`telas.py:19-25`): `administrador_geral` sempre; senão `autenticacao.validar_acesso_modulo(user, "lista_telefonica")`; sem acesso → coluna `block` 64px + "Acesso restrito".
- `mostrar_tela(user_nome, perfil_global)` (`telas.py:32-224`): `ler_tema("lista_telefonica", cor_botao="#000000", texto_header="Organograma expansível — navegue por Secretaria, Setor e Subsetor. Contatos em ordem alfabética.")` + `ui.colors(primary)` + `cabecalho(... chave_modulo="lista_telefonica")` + `estado = {secretaria,setor,subsetor,busca}`.
  - **Barra de busca** (`telas.py:49-63`): `campo_busca("🔍 Buscar — nome, telefone, unidade", ao_buscar, tooltip="Pesquisa em unidades e contatos (sem acentos)")` `data-testid=lista-busca` + `estado["busca"]` + `render_busca.refresh()`.
  - **Navegação expansível** (`telas.py:65-189`): `card` com label + selects `sel_sec` (`data-testid=lista-select-secretaria`, `with_input=True`, `outlined dense clearable w-full`), `sel_set`/`sel_sub` desabilitados até o pai; `secretarias = listar_unidades(parent_id=None, tipo="secretaria")`; `ao_sec` reseta `set/sub`, popula `set` via `listar_unidades(parent_id=e.value, tipo="setor")`; `ao_set` popula `sub`; `ao_sub` só `render_contatos()`; `unidade_selecionada()` prefere `sub > set > sec`; `wrap_contatos` (`column w-full gap-2 mt-2`) + `render_contatos()` que limpa e mostra `Contatos — Nome (tipo)` + `Telefone da unidade` + `N contatos — ordem alfabética` + `column gap-1` de `row border rounded px-3 py-2 hover:bg-blue-50/50` com ícone, nome como `ui.link(target="tel:tel_limpo")` + telefone `font-mono` + `@user_n` + `botao_icone("phone", _acao_tel, data-testid=lista-ligar)` → `_dlg_ligar` (`dialogo_card` 380px, `tel` sanitizado, `ui.run_javascript("window.location.href='tel:...'")` fail-soft, botão `Ligar agora` `call`).
  - **Busca** (`@ui.refreshable render_busca` — `telas.py:192-224`): se `termo`, `buscar_unidades(termo)` + `buscar_contatos(termo)` → `card p-4` com até 10 unidades (`account_tree` + `nome (tipo)` + `tel` + `caminho`) e 20 contatos (`nome` + `tel` `font-mono` + `Ligar` `tel:` link).
  - Helper `_caminho_unidade(uid)` (`telas.py:227-243`): sobe `parent_id` até raiz e `join " > "`.
- Responsividade: `w-full p-6 gap-4`, `flex-nowrap bg-white rounded-lg shadow-sm`, `min-width:0`, `hover:bg-blue-50/50`.

## Regras de negócio relevantes

- **Hierarquia estrita** (validada em `criar_unidade` `bd_manipulador.py:206-247` e `mover_unidade` `bd_manipulador.py:303-350`): `secretaria` nunca tem pai; `setor` exige pai `secretaria`; `subsetor` exige pai `setor`; nome ≥2, duplicado no mesmo `parent+tipo` bloqueia; ordem = `MAX+1` entre irmãs.
- **Mover** (`mover_unidade`): valida novo pai por tipo; evita `uid==novo_parent` e **ciclo** subindo `parent_id` do destino até raiz (se encontrar `uid` → bloqueia "criaria ciclo"); atualiza `parent_id` + `ordem = MAX+1` no destino; audita `mover_unidade`.
- **Elevar/rebaixar** (`elevar_rebaixar` — `bd_manipulador.py:353-404`): `setor→secretaria` (parent NULL), `subsetor→setor` (parent = avô), `secretaria→setor` e `setor→subsetor` exigem `Mover` (mensagem orienta); troca `tipo` + `parent_id` após checar duplicado no destino; audita `elevar_rebaixar`.
- **Excluir ramo (cascata)** (`excluir_ramo` — `bd_manipulador.py:272-290`): coleta recursiva `_coletar_ramo_ids(cur, uid)` (`SELECT id WHERE parent_id=?` + recursão) + `ids.append(uid)` + `DELETE FROM tb_unidade WHERE id=?` (FK CASCADE apaga filhos e `tb_contato`); audita `excluir_ramo` com `ids`.
- **Reordenar/comutar** (`reordenar_unidades` — `bd_manipulador.py:407-421`): `UPDATE tb_unidade SET ordem=? WHERE id=? AND coalesce(parent_id,-1)=coalesce(?, -1)` por `idx` 1-based; audita `reordenar`.
- **Contatos alfabéticos** (`listar_contatos` — `bd_manipulador.py:443-451`): `ORDER BY nome COLLATE NOCASE ASC`; `criar_contato` (`bd_manipulador.py:472-497`) valida nome ≥2, tel ≥8, unidade existe, duplicado `nome` na unidade bloqueia, tipo `vinculado` se `user_nome` senão `externo`; `editar_contato` (`500-523`), `excluir_contato` (`526-539`), `transferir_contato` (`542-565`) valida destino, evita mesma unidade, bloqueia duplicado no destino, audita com `old→new`.
- **Busca normalizada** (`_norm` — `bd_manipulador.py:101-103`): `NFKD` → ascii → lower → `re.findall(r"[a-z0-9]+", s)` → `join " "`; `buscar_unidades`/`buscar_contatos` filtram em memória com `termo_n in _norm(campo)` sobre `nome`/`telefone`/`user_nome`; índice de unidade busca também `telefone`.
- **Sanitização de telefone para `tel:`** (`telas.py:117`): `re.sub(r"[^0-9+]", "", tel or "")` — preserva `+` inicial e dígitos; `tel_limpo` usado em `ui.link(target="tel:...")` e `window.location.href='tel:...'`.
- **Integração usuários** (`telas_administracao.py:288-340`, corrigido 19/09/2026): criação de contato pode vincular `user_nome` da base `mod_gest_cad_usuario` via **campo `Buscar usuário na base`** (`inp_busca_user`, `data-testid=admin-contato-busca`, `clearable`) + **select `Usuário encontrado`** (`sel_user`, `data-testid=admin-contato-user`, `clearable`). `inp_busca_user.on_value_change(ao_buscar_user)` filtra **em tempo real** `gest.listar_usuarios()` por **`login` + `nome_completo` (`r[9]`) + `e-mail` (`r[4]`)** com `_norm` (`NFKD` sem acentos → lower, `termo_n in _norm(campo)`), **exclui deletados** (`not r[8]`), mostra **20 primeiros quando vazio** (`todos[:20]`) e **até 30 filtrados** (`filtrados[:30]` → `opts[login]= "nome_trat (@login • perfil)"` com `nome_trat=(r[9] or r[1])`); `sel_user.set_options(opts)` + `update()` a cada digitação + carga inicial `ao_buscar_user("")`. Botão `Usar usuário` preenche `Nome`/`Telefone` a partir de `gest.obter_usuario(sel_user.value)` (`row[9]` nome completo + `row[5]` telefone). `criar_contato` grava `user_nome` e `tipo='vinculado'`; `renomear_usuario`/`remover_vinculos` LGPD em `bd_manipulador.py:592-600`.
- **LGPD**: `remover_vinculos_usuario(user_nome)` (`578-589`) → `DELETE FROM tb_contato WHERE user_nome=?` + `audit remover_vinculos_lista`; `renomear_usuario(nome_atual, novo_nome)` (`592-600`) → `UPDATE tb_contato SET user_nome/nome WHERE user_nome/nome AND tipo='vinculado'`.

## Integrações com o núcleo

Importa `autenticacao.validar_acesso_modulo`/`eh_admin_do_modulo`, `banco_conexao.conexao`, `tema_modulo.ler_tema`/`notificar`/`bloco_aparencia`, `ui_comum.botao`/`botao_icone`/`card_admin`/`dialogo_card`/`rodape_salvar_restaurar`, `observabilidade.get_logger`. Grava via `audit_log` → `tb_auditoria_lista_telefonica`. Backup via `rotinas.painel_backup`/`MAPA_BACKUPS` (`lista_telefonica: db_mod_lista_telefonica.db`). `PREFIXO_POR_CHAVE`/`PADROES_TEMA`/`MODULOS_SISTEMA`/`MODULOS_BD` com `lista_telefonica`. `ORGANOGRAMA_BASE` exportado para `mod_solicita_impressao` semear cotas (1000/200).

## Pontos de atenção

- Organograma genérico e desacoplado — semente só quando `tb_unidade` vazia (bancos já semeados não são sobrescritos).
- `subsetor` não é usado como unidade de impressão — em `mod_solicita_impressao` os subsetores são achatados como `tb_setores` (200 cópias cada) para manter o modelo Secretaria→Setor da impressão.
- `telephone` como texto livre (não validado por regex rígida, só ≥8 chars); `tel:` usa `re.sub` para extrair dígitos/`+`.
- `_coletar_ramo_ids` é recursiva em Python (não `WITH RECURSIVE` SQL) — organograma de ~12 secretarias é pequeno, recursion depth seguro.
- `reordenar_unidades` usa `coalesce(parent_id,-1)` para tratar `NULL` (secretarias raiz) sem `IS NULL` dinâmico.
- `bd_criador.py` morto — nunca executar; schema real é `init_db()` do `bd_manipulador`.

## Status

| Item | Situação |
|:---|:---|
| Banco WAL + `tb_unidade`/`tb_contato` + semente 12 secretarias | Implementado (`init_db` + `ORGANOGRAMA_BASE`) |
| Organograma expansível Secretaria→Setor→Subsetor (cascata) | Implementado (`telas.py` selects `clearable` + `disable` + `render_contatos`) |
| Contatos alfabéticos (`COLLATE NOCASE`) + `tel:` clicável | Implementado (`listar_contatos` + `ui.link tel:` + `_dlg_ligar`) |
| Busca por nome/telefone (sem acentos) | Implementado (`_norm` + `buscar_*`) |
| Admin: criar/mover/elevar/excluir ramo/reordenar/comutar/transferir | Implementado (`telas_administracao.py` 398 linhas + `bd_manipulador` 603 linhas) |
| Vínculo a usuários (vinculado/externo) + LGPD | Implementado (`criar_contato` + `remover/renomear`) |
| Aparência + backup | Implementado (`bloco_aparencia` + `painel_backup`) |
| Integração `solicita_impressao` (ORGANOGRAMA_BASE → 1000/200) | Implementado (`mod_solicita_impressao/bd_manipulador.py:364`) |
