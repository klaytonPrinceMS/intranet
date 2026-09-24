# Phone Directory Module — `mod_lista_telefonica`

> Phone directory / expandable organogram module: route `/lista-telefonica` (key `lista_telefonica`) · own database `db_mod_lista_telefonica.db` (WAL) · hierarchy `Secretaria → Setor → Subsetor` · contacts alphabetically ordered · search by name/phone · `tel:` clickable on mobile · admin: delete branch, move, elevate/relegate, reorder/swap, transfer contacts.

---

# Módulo Lista Telefônica — `mod_lista_telefonica`

> Módulo de lista telefônica / organograma expansível: rota `/lista-telefonica` (chave `lista_telefonica`) · banco próprio `db_mod_lista_telefonica.db` (WAL) · hierarquia `Secretaria → Setor → Subsetor` · contatos em ordem alfabética · busca por nome/telefone · telefone clicável `tel:` no celular · admin: excluir ramo, mover, elevar/rebaixar, ordenar/comutar, transferir contatos.

## Propósito

Lista telefônica interna com **organograma genérico de 12 secretarias** expansível em 3 níveis. O usuário navega por Secretaria → Setor → Subsetor via selects em cascata e visualiza os contatos da unidade selecionada sempre em **ordem alfabética** (`nome COLLATE NOCASE`). A busca global encontra unidades e contatos por nome ou telefone (normalização sem acentos). No celular, o telefone é **clicável** (`tel:`) e oferece diálogo "Ligar agora" com fallback para desktop.

O organograma base é **genérico** e desacoplado de vínculo territorial, servindo como semente inicial editável pelo administrador (criar, mover, elevar, reordenar, excluir ramo).

## Banco de dados

Criador vigente: `init_db()` em `bd_manipulador.py:134-199` (bootstrap central `mod_intranet/bd_criador.py` + chamada no import `bd_manipulador.py:925` `init_db()`).

Conexão via `mod_intranet/banco_conexao.conexao("lista_telefonica")` (backend duplo SQLite/PostgreSQL, `PRAGMA journal_mode=WAL` + `foreign_keys=ON`). Índices `idx_unidade_parent`, `idx_contato_unidade`, `idx_contato_nome`.

| Tabela | Conteúdo |
|:---|:---|
| `tb_unidade` | `id` PK, `nome`, `tipo` (`secretaria`\|`setor`\|`subsetor` `CHECK`), `parent_id` FK CASCADE → `tb_unidade.id`, `ordem`, `telefone`, `ativo` (default 1) |
| `tb_contato` | `id` PK, `unidade_id` FK CASCADE → `tb_unidade.id`, `nome`, `telefone`, `user_nome` (vínculo opcional à base de usuários), `tipo` (`vinculado`\|`externo` default `externo`), `data_criacao` |

Semente idempotente (`bd_manipulador.py:164-185`): só semeia quando `COUNT(tb_unidade)==0`. Constante `ORGANOGRAMA_BASE` (`bd_manipulador.py:21-75`) com 12 secretarias e respectivos setores/subsetores:

- Gabinete, Administração, Finanças, Saúde, Educação, Obras e Infraestrutura, Agricultura, Meio Ambiente, Assistência Social, Cultura, Esporte e Lazer, Planejamento — cada uma com setores e subsetores (ex.: Administração → Recursos Humanos → Folha/Capacitação, Patrimônio → Compras/Licitações, T.I. → Suporte/Redes, etc.). Ordem semeada via `ordem` sequencial por nível.

⚠️ `bd_criador.py` é **legado/morto** — não executar (schema real em `bd_manipulador.py`).

Modelos tipados: `models/__init__.py` com dataclasses `Unidade` (`id`, `nome`, `tipo`, `parent_id`, `ordem`, `telefone`, `ativo`) e `Contato` (`id`, `unidade_id`, `nome`, `telefone`, `user_nome`, `tipo`) espelhando `tb_unidade`/`tb_contato` (sem `map_imperatively`; acesso ao banco segue via `banco_conexao.conexao("lista_telefonica")` + SQL direto no `bd_manipulador`).

## Telefones — DDI +55 via `mod_intranet.telefone`

Telefones são gravados como texto livre (validação mínima: ≥8 caracteres) e normalizados só na exibição/ligação via `mod_intranet.telefone` (não há `formatar_br`/`apenas_digitos` dentro do `mod_lista_telefonica`):

- Leitura: `obter_ddi(tel)` + `normalizar_telefone(ddi, tel)` (preserva `+`, DDI padrão `+55`) e `formatar_para_exibicao(tel)` para o formato BR (`telas.py:141-171`, `_dlg_ligar`, `telas_administracao.py:818-821`).
- Escrita/admin: `criar_campo_telefone(valor, testid_ddi, testid_numero)` com seletor de DDI + campo numérico (`telas_administracao.py:37-44` unidade `admin-unidade-ddi`/`admin-unidade-tel`, `telas_administracao.py:656-663` contato `admin-contato-ddi`/`admin-contato-tel`, edição via `_campo["obter"]()`/`_campo["definir"]()` com fallback para `ui.input` simples).
- Fallback sem o helper: `re.sub(r"[^0-9+]", "", tel or "")` para montar `tel:` (`ui.link(target="tel:...")` + `window.location.href='tel:...'` no diálogo "Ligar agora").

## Funcionalidades

### Organograma expansível — Secretaria → Setor → Subsetor

- **Navegação em cascata** (`telas.py:64-189`): `Secretaria *` (`listar_unidades(parent_id=None, tipo="secretaria")`) habilita `Setor` que habilita `Subsetor`; `clearable` com `disable()` até o pai ser escolhido. Mudança de Secretaria reseta Setor/Subsetor; mudança de Setor reseta Subsetor. Contatos renderizados via `render_contatos()` sempre da unidade mais específica selecionada (`subsetor > setor > secretaria`).
- **Listagem de contatos alfabética** (`listar_contatos` — `bd_manipulador.py:443-451`): `SELECT ... WHERE unidade_id=? ORDER BY nome COLLATE NOCASE ASC`; exibida com ícone `person` (vinculado) ou `badge` (externo), nome como `ui.link(target="tel:...")` + telefone monoespacado + `@user_nome` quando vinculado + botão `phone` (`botao_icone` `data-testid=lista-ligar`) que abre diálogo de ligação.
- **Telefone clicável `tel:`** (`telas.py:115-149`): `tel_limpo = re.sub(r"[^0-9+]", "", tel)`; nome como `ui.link(target=f"tel:{tel_limpo}")` com `tooltip "Toque para ligar (celular)"`; diálogo `_dlg_ligar` (`dialogo_card` 380px) mostra telefone e botão `Ligar agora` que executa `window.location.href='tel:...'` via `ui.run_javascript` (fail-soft; no desktop avisa que discador pode não estar configurado).
- **Cabeçalho temático** (`mostrar_tela` — `telas.py:40-46`): `ler_tema("lista_telefonica", cor_botao="#000000", texto_header="Organograma expansível — navegue por Secretaria, Setor e Subsetor. Contatos em ordem alfabética.")` + `ui.colors(primary=tema["cor_botao"])` + `cabecalho("Lista Telefônica", ..., chave_modulo="lista_telefonica")` (borda = cor do módulo via `PADROES_TEMA["lista_telefonica"]` → `#000000`).
- **Busca global** (`telas.py:49-224`): `campo_busca("🔍 Buscar — nome, telefone, unidade", ao_buscar)` (`data-testid=lista-busca`) → `estado["busca"]` → `render_busca.refresh()` (`@ui.refreshable`). `buscar_unidades(termo)` (`bd_manipulador.py:424-439`) e `buscar_contatos(termo)` (`bd_manipulador.py:454-469`) normalizam com `_norm` (`NFKD` sem acentos + `re.findall(r"[a-z0-9]+", s)`) e filtram em memória com `termo_n in _norm(nome/telefone/user_nome)`. Exibe até 10 unidades (com `_caminho_unidade` `"Sec > Setor > Subsetor"`) e 20 contatos (com `Ligar` `tel:` quando houver telefone). Sem resultados → "Nenhum resultado."
- **Responsividade**: `w-full p-6 gap-4`, `flex-nowrap` com `min-width:0`, `w-[380px]` dialogs, `border rounded` cards + `hover:bg-blue-50/50`.

### Administração (`/admin/lista_telefonica`)

`telas_administracao.py:15-398` — `bloco_aparencia` (cupê "Aparência" `lista_telefonica_*`, `com_texto_header=True`) + 2 cards + `painel_backup`.

**Card "Unidades — criar, mover, elevar/rebaixar, excluir ramo"** (`card_admin`, `account_tree`, `grade=False`):

- **Criar** (`telas_administracao.py:31-66`): `Nome *` (`data-testid=admin-unidade-nome`) + `Tipo` secretaria/setor/subsetor (`data-testid=admin-unidade-tipo`) + `Unidade pai` (`data-testid=admin-unidade-pai`, `clearable`) + `Telefone` (`data-testid=admin-unidade-tel`). `refresh_pai()` popula pai conforme tipo (secretaria → desabilita; setor → secretarias; subsetor → todos setores com caminho `"Sec > Setor"`). `criar_unidade` valida nome ≥2, tipo, parent (`secretaria` sem pai, `setor` sob `secretaria`, `subsetor` sob `setor`), duplicado no mesmo pai, ordem = `MAX(ordem)+1`; audita `criar_unidade`.
- **Listagem expansível** (`render_unidades` — `@ui.refreshable`, `telas_administracao.py:69-106`): secretarias com `ui.expansion("Nome (tel)", icon="apartment")` + row de ações: `edit` (editar nome/tel), `delete_forever` (excluir ramo cascata, `text-red-8`), `drive_file_move` (mover), `vertical_align_top` (elevar), `swap_vert` (reordenar secretarias). Setores aninhados (`expansion business` com `ml-4`) + subsetores (`row ml-8 border-b`).
- **Editar** (`_dlg_editar` — `telas_administracao.py:108-125`): `dialogo_card` 420px com `Nome` + `Telefone`; `editar_unidade(uid, nome, telefone)`.
- **Excluir ramo (cascata)** (`_dlg_excluir_ramo` — `telas_administracao.py:127-143`): `dialogo_card` com `border-2 border-red-6` + aviso "e TODOS os filhos/contatos — não pode ser desfeita"; `excluir_ramo(uid)` coleta ids recursivos com `_coletar_ramo_ids` e `DELETE FROM tb_unidade WHERE id=?` (FK CASCADE apaga filhos/contatos); audita `excluir_ramo` com `ids`.
- **Mover** (`_dlg_mover` — `telas_administracao.py:145-192`): valida tipo → novo pai (`secretaria` → raiz, `setor` → secretaria, `subsetor` → setor); evita ciclo subindo `parent_id` até raiz; ordem final = `MAX+1`; `mover_unidade(uid, novo_parent_id)`.
- **Elevar/rebaixar** (`_dlg_elevar` — `telas_administracao.py:194-220`): `setor→secretaria` (parent NULL) ou `subsetor→setor` (parent = avô); `secretaria→setor` e `setor→subsetor` pedem `Mover`; `elevar_rebaixar(uid, novo_tipo)`.
- **Reordenar (comutar)** (`_dlg_reordenar` — `telas_administracao.py:222-260`): lista irmãs (`listar_unidades(parent_id, tipo)`) com lista `ordem = [ids]` + botões `arrow_upward`/`arrow_downward` que comutam `ordem[i-1]↔ordem[i]` e re-renderizam; `Salvar ordem` → `reordenar_unidades(parent_id, ordem_ids)` (`UPDATE ordem = idx WHERE id AND coalesce(parent_id,-1)`).

**Card "Contatos — incluir via usuários ou externo, telefone, transferir"** (`contacts`, `grade=False` — `telas_administracao.py:262-410`, corrigido 19/09/2026 com busca `on_value_change`):

- **Criar contato** (`telas_administracao.py:282-350`): `sel_unidade` (`data-testid=admin-contato-unidade`, opções `caminho (tipo)`) + `Nome *`/`Telefone *` (`data-testid=admin-contato-nome`/`admin-contato-tel`) + linha de vínculo à base de usuários: `inp_busca_user` (`ui.input "Buscar usuário na base"`, placeholder "digite nome, login ou e-mail", `data-testid=admin-contato-busca`, `clearable`) + `sel_user` (`ui.select "Usuário encontrado (opcional)"`, `data-testid=admin-contato-user`, `clearable`). `inp_busca_user.on_value_change(ao_buscar_user)` filtra **em tempo real** `mod_gest_cad_usuario.listar_usuarios()` por `login`/`nome_completo`/`e-mail` com `_norm` (`NFKD` sem acentos + lower, `termo_n in _norm(campo)`), **exclui deletados** (`not r[8]`), mostra **20 primeiros quando vazio** e **até 30 filtrados** (`filtrados[:30]` → `opts[login]= "nome_trat (@login • perfil)"`); `sel_user.update()` a cada digitação + carga inicial `ao_buscar_user("")`. Botão `Usar usuário` (`person_search`, `variante="texto"`) preenche `Nome` com `nome_completo` (`row[9] or login`) e `Telefone` com `row[5]` quando vazio via `gest.obter_usuario(sel_user.value)`. `criar_contato(unidade_id, nome, telefone, user_nome=sel_user.value)` valida nome ≥2, tel ≥8, unidade existe, duplicado na unidade; tipo = `vinculado` se `user_nome` else `externo`; audita `criar_contato`. **Correção 19/09/2026:** antes o `sel_user` listava usuários sem busca filtrada; agora a busca é via `inp_busca_user` + `on_value_change` com `_norm` em 3 campos + limite 20/30 + exclusão de deletados.
- **Lista por unidade** (`render_contatos` — `@ui.refreshable`, `telas_administracao.py:341-395`): `listar_contatos(uid)` alfabético + `@user` badge; por contato: `edit` (nome/tel), `swap_horiz` (transferir — `dialogo_card` com `sel_dest` de todas unidades → `transferir_contato(cid, nova_unidade)` com checagem de duplicado no destino), `delete` (excluir direto via `excluir_contato` + `notificar` + `refresh`).

**Rodapé**: `painel_backup(usuario, "lista_telefonica")` (job `backup:lista_telefonica` 12h, `mod_intranet/rotinas.py:MAPA_BACKUPS`).

- **Versionamento**: `versao_modulo:lista_telefonica` no rodapé de `/lista-telefonica`.

## Permissões

| Ação | `comum` com `lista_telefonica` | `administrador_modulo`/`administrador_geral` | Sem acesso |
|:---|:---:|:---:|:---:|
| Ver `/lista-telefonica` (navegação + busca) | ✓ | ✓ | ✗ (tela "Acesso restrito — Somente usuários com acesso à Lista Telefônica") |
| Ver telefone / Ligar `tel:` | ✓ | ✓ | — |
| Criar/mover/elevar/excluir ramo | ✗ | ✓ | ✗ |
| Incluir/editar/transferir/excluir contato | ✗ | ✓ | ✗ |
| Reordenar / comutar | ✗ | ✓ | ✗ |
| Ver `/admin/lista_telefonica` | ✗ | ✓ | ✗ (redirect para `/lista-telefonica` + `ui.notify` "Acesso restrito a administradores") |

Gate: `_pode_ver(user, perfil)` (`telas.py:19-25`) — `administrador_geral` sempre; senão `autenticacao.validar_acesso_modulo(user, "lista_telefonica")`. Admin: `_eh_admin` (`telas.py:28`). `/admin/lista_telefonica` revalida `eh_admin_do_modulo`.

LGPD: `remover_vinculos_usuario(user_nome)` (`bd_manipulador.py:578-589`) remove `DELETE FROM tb_contato WHERE user_nome=?` (audita `remover_vinculos_lista`); `renomear_usuario` propaga `UPDATE tb_contato SET user_nome/nome WHERE user_nome/nome`.

## Rota e integrações

- Rota: `/lista-telefonica` (chave `lista_telefonica`, ícone `call`) — `main.py:752-763` (`pagina_restrita("Lista Telefônica", chave_modulo="lista_telefonica")` + `REGISTRO_MODULOS["lista_telefonica"] = page_lista_telefonica`); slug customizável em `/configuracoes` → aba Módulo (`rotas_modulos.montar_rotas_ativas()`).
- Admin: `/admin/lista_telefonica` — `main.py:869-880` (`eh_admin` + `ui.colors(primary=ler_tema("lista_telefonica"))` + `mostrar_administracao(nome)`; não-admin navega para `/lista-telefonica`).
- Cadastro central: `MODULOS_SISTEMA` (`autenticacao.py:24` → `("lista_telefonica","Lista Telefônica","call","/lista-telefonica")`), `MODULOS_BD` (`repositorio.py:67` → `lista_telefonica: db_mod_lista_telefonica.db`), `PADROES_TEMA["lista_telefonica"]` (`tema_modulo.py:79` → `#000000`), `PREFIXO_POR_CHAVE["lista_telefonica"]` → `lista_telefonica`.
- Auditoria: `audit_log` (núcleo) → `mod_auditoria` banco exclusivo `db_mod_auditoria.db`, tabela `tb_auditoria_lista_telefonica` (`criar_unidade`, `editar_unidade`, `excluir_ramo`, `mover_unidade`, `elevar_rebaixar`, `reordenar`, `criar_contato`, `editar_contato`, `excluir_contato`, `transferir_contato`).
- Backup do banco: job `backup:lista_telefonica` (`backup_horas:lista_telefonica` default 12h, `MAPA_BACKUPS` inclui `lista_telefonica: db_mod_lista_telefonica.db`).
- **Integração com Solicitação de Impressão**: `mod_solicita_impressao/bd_manipulador.py:364` importa `ORGANOGRAMA_BASE` da lista telefônica para semear automaticamente `tb_secretarias` (1000 cópias) e `tb_setores` (200 cópias, subsetores achatados como setores) + migração `UPDATE` para bancos existentes — ver [Módulo Solicitação de Impressão](solicitacao_impressao.md).

## Testes

```bash
# Smoke do módulo (import + init_db + CRUD mínimo)
.venv/bin/python -c "from mod_lista_telefonica.bd_manipulador import init_db, listar_unidades, buscar_contatos; init_db(); print(listar_unidades(tipo='secretaria')[:2]); print(buscar_contatos('a'))"
# Playwright (quando coberto)
.venv/bin/pytest assets/test/teste_lista_telefonica.py -k lista
```

Ver [Análise do Módulo](../analise_mod_lista_telefonica.md) e [Arquitetura](../arquitetura.md).

## Pontos de atenção

- Hierarquia estrita: `secretaria` (raiz, sem pai) → `setor` (pai `secretaria`) → `subsetor` (pai `setor`); validação em `criar_unidade`/`mover_unidade`/`elevar_rebaixar`; ciclo detectado subindo `parent_id` até raiz.
- `subsetor` não usado como unidade de impressão — no `mod_solicita_impressao` os subsetores do `ORGANOGRAMA_BASE` são **achatados como setores** (200 cópias cada) para manter modelo Secretaria→Setor da impressão.
- Ordem alfabética de contatos é **garantida no SQL** (`COLLATE NOCASE`), independente da ordem de inserção; reordenação de unidades é por `ordem` irmãs (comutação ↑/↓).
- `tel:` é suportado nativamente em mobile; em desktop o diálogo avisa que discador pode não estar configurado — `ui.run_javascript` é `try/except` (fail-soft).
- Busca normalizada sem acentos: `João` encontra `joao`; telefone busca também por `user_nome` vinculado.
- Nunca commitar `db_mod_lista_telefonica.db`; `bd_criador.py` morto — nunca executar.
- API real do `bd_manipulador` (todas com `try/except` + `notificar`/log): `get_connection` (WAL + `foreign_keys=ON` via `banco_conexao.conexao`), `_log`/`_audit` (auditoria via `audit_log`), `_norm` (NFKD sem acentos), `init_db`, `listar_unidades(parent_id, tipo, ativo)`, `listar_todas_unidades`, `obter_unidade(uid)`, `criar_unidade`, `editar_unidade`, `excluir_ramo` (+ `_coletar_ramo_ids` recursivo), `mover_unidade` (anti-ciclo), `elevar_rebaixar`, `reordenar_unidades`, `buscar_unidades`, `listar_contatos` (alfabético `COLLATE NOCASE`), `buscar_contatos`, `criar_contato`, `editar_contato`, `excluir_contato`, `transferir_contato`, `contar_unidades` (contagem de `tb_unidade`), `remover_vinculos_usuario`/`renomear_usuario` (LGPD).
- Tela pública (`telas.py`): API real é `mostrar_tela(user_nome, perfil_global)` + helpers `_pode_ver`/`_eh_admin`/`_caminho_unidade` + internos `render_contatos`/`render_busca`/`_dlg_ligar`; **não existe** `_mostrar_tela_segura` nem diálogo `duplicar` — edição/duplicação de unidades e contatos ocorre só nos diálogos do admin (`_dlg_editar`, `_dlg_excluir_ramo`, `_dlg_mover`, `_dlg_elevar`, `_dlg_reordenar`, `_editar`/`_transferir` de contato).
