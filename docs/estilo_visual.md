> **EN — Visual style switcher (4 named patterns) where "Padrão" means *no imposition at all*, and the system theme is back to black (27/09/2026).** The login page is **fixed** on the `verde` (WhatsApp) pattern — it does not read `?estilo=` and has no switcher. Inside the modules the user picks one of four named patterns (`azul`, `verde`, `roxo`, `preto` — the former `light` was renamed because it pinned `--q-primary` to `#111111` and turned the whole screen black, a misleading name) plus the special `padrao` option. The choice lives in a **browser cookie** (`estilo_visual`), never in the database, and is resolved on the server by `estilo_efetivo()`, which now simply returns `ler_estilo()` and **may return `""`**: the empty string is a valid, meaningful answer meaning *no style is being imposed*, so the colour that shows is the **module administrator's** (`tema_modulo.ler_tema`). In `mod_intranet/telas.py` `_montar_layout` only calls `aplicar()` when the value is truthy, so the module's own `ui.colors(primary=cores)` prevails. `estilo_padrao_sistema()` no longer takes part in the resolution and was **removed** (dead code that would still have returned `"verde"`, silently reintroducing the rejected semantics). The system theme was **reverted to black**: the 11 modules' `PADROES_TEMA` entries are back to `cor_botao #000000` / `cor_texto_botao #FFFFFF` / `cor_titulo #212121`, `ui_comum.CORES` is back to `primaria #1565C0` / `titulo #212121` / `fundo #EEEEEE`, and a new idempotent migration (`migracao_padrao_por_modulo_260927`) restores `cor_principal #000000` / `cor_fundo #EEEEEE`, seeds `estilo_visual_padrao_sistema = 'padrao'` and blanks `<prefixo>_cor_botao`/`<prefixo>_cor_titulo`. The WhatsApp "Verde" therefore became a plain **menu option**, not the system colour. The footer switcher is centred **exactly** in the middle of the screen by a three-column CSS grid scoped to `[data-testid="rodape-sistema"] > .nicegui-row:first-child`, is no longer `position: fixed` (the `.pe-alternador-fixo` mode was removed), and when no style is imposed the `estilo-atual` label reads **"cor do módulo"**. This page also records the **Quasar cascade-layer trap** (`.bg-primary`/`.text-primary` are `!important` *inside a layer*, so the only way to recolour is to override the `--q-primary` **token**) and the NiceGUI 3.15 `context.request` → `context.client.request` move.

# Estilo Visual e Tema do Sistema

> Documenta a feature de **ESTILO VISUAL** (27/09/2026) na sua forma **revisada**: os
> 4 estilos nomeados (`azul`/`verde`/`roxo`/`preto`), a opção **"Padrão" como ausência
> de imposição**, o menu de estilo no rodapé em grade de 3 colunas e o **retorno do
> tema do sistema ao preto**. Referência de código:
> `mod_intranet/preview_estilos.py`, `mod_intranet/tema_modulo.py` (`PADROES_TEMA`),
> `mod_intranet/ui_comum.py` (`CORES`), `mod_intranet/telas.py` (`_montar_layout`),
> `mod_intranet/bd_conexao.py` (`init_db`, migração `migracao_padrao_por_modulo_260927`),
> `assets/css/preview-estilos-v1.css` e `main.py` (`page_login`).
>
> !!! warning "Documento normativo"
>     A feature está marcada como **PROVISÓRIA** no código (`preview_estilos.py`,
>     `assets/css/preview-estilos-v1.css` e os blocos `# ===== PROVISÓRIO =====` do
>     `main.py`). A decisão de **semântica** — "Padrão" significa *não impor cor* e o
>     tema do sistema é o preto que o administrador configurou — é definitiva; a
>     remoção do mecanismo de troca (se o responsável decidir) está descrita em
>     [Como reverter](#11-como-reverter-a-feature).

---

## 1. A decisão em uma frase

O **responsável** entrou no menu de estilo e definiu que o **"Padrão" não é uma cor
do sistema**: é a **ausência de imposição**. Quem não escolheu nada vê **a cor que o
administrador configurou para o módulo**. O tema do sistema **voltou ao preto** que
tinha antes da experiência, e o WhatsApp virou apenas **uma opção** do menu.

| Onde | O que vale | Origem |
|:---|:---|:---|
| **Login** (`/login`) | **sempre `verde`** (WhatsApp), para todo mundo | constante `PADRAO_LOGIN` (`preview_estilos.py:116`) — **não** segue preferência nem `?estilo=` |
| **Módulos internos** (todas as telas com `pagina_restrita`) | escolha do usuário no cookie **ou** `""` (nada imposto) | `estilo_efetivo()` (`preview_estilos.py:503`) |
| **Com `""`** | a **cor do módulo** — o que o administrador configurou | `tema_modulo.ler_tema(chave_modulo)` + `ui.colors(primary=cores)` em `telas.py:240` |
| **Paleta de botões/títulos** (independente do estilo) | **preto** em todos os 11 módulos | `PADROES_TEMA` (`tema_modulo.py:65-88`) |

!!! info "Por que o login é fixo"
    O login é a única tela que **não pode** quebrar e a única em que a identidade
    visual precisa ser uniforme. A preferência de estilo é uma escolha de
    *conforto de leitura dentro do sistema*, não de marca — por isso ela vale
    para os módulos e não para a porta de entrada. Consequência prática: o
    `?estilo=` deixou de ser lido e **o alternador não é montado no login**
    (embora a folha de estilo e a rota de troca continuem carregadas, porque são
    as mesmas dos módulos).

## 2. Os 4 estilos nomeados

Definidos em `PADROES` (`preview_estilos.py:84-93`). Cada um é um **design
próprio** (nenhum framework genérico reproduz painel dividido/faixa gradiente/
aro de avatar), e a identidade vem de custom properties `--pe-*` injetadas no
`:root` por `_defs_css()`.

| Chave | Rótulo | Descrição (tooltip) | Família | Fundo | Primária | `--q-primary` | Raio |
|:---|:---|:---|:---|:---|:---|:---|:---|
| `azul` | **Azul** | azul de marca, nome grande e cartões brancos | Feed | `#f0f2f5` | `#1668d8` | `#1668d8` | `8px` |
| `verde` | **Verde** | tela dividida, painel verde e botão em pílula | Mensageiro | `#eae6df` | `#075e54` | `#0f7a6d` (+ acento `#25d366`) | `10px` |
| `roxo` | **Roxo** | faixa gradiente roxo para rosa, bem arredondado | Bolhas | `#f4f5fb` | `#7c3aed` | `#7c3aed` (+ `#db2777`) | `22px` |
| `preto` | **Preto** | preto, aro colorido no avatar, bem monocromático | Monocromático | `#fafafa` | `#111111` | `#111111` (+ `#e1306c`) | `14px` |

Derivados: `CHAVES` (tupla das 4 chaves), `ROTULOS` e `DESCRICOES`
(`preview_estilos.py:94-96`). A paleta completa (com `escuro`, `superficie`,
`primaria_texto`, `sombra`) está em `_CORES` (`preview_estilos.py:131-168`); a
entrada `preto` é `_CORES["preto"]` (`preview_estilos.py:161-167`).

### 2.1 Por que `light` virou `preto`

A chave anterior se chamava `light` com a descrição "monocromático **claro**", mas a
paleta **não** era clara: `primaria` e `primaria_q` são `#111111` (quase preto), e
como `_defs_css()` escreve esse valor em `--q-primary` com `!important`, o botão, o
cabeçalho e todo elemento `bg-primary` da tela ficavam **pretos** — a tela **inteira**
saía preta. O nome prometia o oposto do que acontecia, o que é o pior tipo de engano
numa etiqueta de menu. A correção foi só de nomenclatura: chave `preto`, rótulo
**"Preto"**, descrição "preto, aro colorido no avatar, bem monocromatico"
(`preview_estilos.py:91-92`). A paleta em si **não** mudou.

Tudo que acompanha a chave mudou junto: a classe CSS `pe-preto` (era `pe-light`),
a função de layout `_login_preto` (`preview_estilos.py:365`, era `_login_light`), o
item de `_LAYOUTS` (`preview_estilos.py:388`) e o `data-testid` `estilo-preto`.

!!! warning "O valor `#111111` é escuro, mas o FUNDO continua claro"
    A paleta `preto` é "monocromático" no sentido de **interface sem cor de marca**,
    não de "tela escura": `fundo` é `#fafafa` e `superficie` é `#ffffff`
    (`preview_estilos.py:163`). O que é `#111111` é a cor de **ação** (botão e
    `--q-primary`). Ou seja, o estilo não impõe tema escuro — `escuro` é `False` em
    todas as 4 paletas.

### 2.2 A opção "Padrão" NÃO é um estilo

`OPCAO_PADRAO` (`preview_estilos.py:98-105`) não é um quinto estilo — é a
**ausência de escolha pessoal**:

```python
# preview_estilos.py:101-105
CHAVE_PADRAO = "padrao"
OPCAO_PADRAO = {
    "chave": CHAVE_PADRAO, "rotulo": "Padrão",
    "descricao": "segue o padrão definido pelo administrador",
}
```

Fica no **fim** da lista (`preview_estilos.py:625`, `tuple(PADROES) + (OPCAO_PADRAO,)`)
para os quatro estilos ficarem juntos no começo. Ao clicar nela, o cookie passa a
guardar `padrao`, e `ler_estilo()` normaliza esse valor para `""` — assim o código
tem **um único jeito** de dizer "não escolheu" (ver
[resolução](#4-hierarquia-de-resolucao-do-estilo)).

!!! danger "O vazio é a resposta, não uma falha"
    `estilo_efetivo()` devolver `""` **não** é degradação nem erro: é a resposta
    correta ao clique em "Padrão". Um `""` que caísse num estilo qualquer seria uma
    mentira — o usuário pediu para não ter cor imposta e receberia uma.

### 2.3 Defaults do protótipo e o que sobrou

```python
PADRAO_PADRAO = "verde"   # preview_estilos.py:109 — fallback interno de aplicar()/tela_login()
PADRAO_LOGIN  = "verde"   # preview_estilos.py:116 — estilo FIXO do login
PADRAO_ADM    = None      # preview_estilos.py:124
```

Com a virada de semântica, o papel desses defaults mudou:

- **`PADRAO_LOGIN`** continua valendo e é o que faz o login aparecer sempre no
  WhatsApp (`main.py:248`).
- **`PADRAO_PADRAO`** virou apenas a **rede de segurança interna** de
  `aplicar()` (`:241`) e `tela_login()` (`:405`), para um `padrao` fora da lista
  nunca deixar a tela sem estilo. **Não** é mais o "padrão do sistema" no sentido
  do menu — ver [§4.2](#42-o-que-sobrou-de-estilo_padrao_sistema-removido).
- **`PADRAO_ADM` = `None`** (`:124`) é o que mantém a cor do administrador **fora**
  da paleta de qualquer estilo. Continua `None` de propósito: se fosse ligado a um
  estilo, a cor da prefeitura (`#000000`) entraria na paleta e zeraria a identidade
  do estilo escolhido. É a constante que **materializa** a decisão do responsável.

## 3. A preferência vive no COOKIE do navegador

!!! danger "Não está no banco — e essa é a decisão, não uma omissão"
    A escolha de estilo **não** vai para `tb_config` nem para tabela de usuário.
    Ela pertence **ao navegador**: fica só neste computador, neste perfil de
    navegador, e não viaja com o usuário para outra máquina nem aparece para
    outra pessoa que use o mesmo login.

| Item | Valor | Onde |
|:---|:---|:---|
| Nome do cookie | `estilo_visual` | `COOKIE_ESTILO` (`preview_estilos.py:443`) |
| Rota de troca | `GET /estilo-visual/{chave}?volta=<caminho>` | `ROTA_TROCA` (`preview_estilos.py:444`) + `montar_rota_troca()` (`:541`) |
| Registro no boot | `_pv_rotas.montar_rota_troca()` | `main.py:160` (junto de `montar_rotas_static()` em `main.py:159`, bloco `main.py:152-162`) |
| Validade | 365 dias (`max_age=60*60*24*365`), `samesite=lax`, `path=/` | `montar_rota_troca()` (`preview_estilos.py:568-570`) |
| Resposta | `303 See Other` com `Set-Cookie` | `montar_rota_troca()` (`preview_estilos.py:555-571`) |
| Chave legada no banco | `estilo_visual_padrao_sistema` (valor `'padrao'`) `CONFIG_PADRAO_SISTEMA` foi **removida**, ver [§4.2](#42-o-que-sobrou-de-estilo_padrao_sistema-removido) |

### 3.1 Por que cookie e não `localStorage`

O estilo é aplicado na **renderização, no servidor**. Com `localStorage` só existe
JavaScript rodando no cliente; o servidor teria de desenhar a tela no padrão
errado e o navegador trocaria depois. O resultado seria um **piscar de layout**
em toda troca de estilo, mais um round-trip. O cookie é lido **no request**, então
a página **já nasce** no estilo certo. De brinde, evita JavaScript direto — que o
projeto proíbe (AGENTS.md §5).

### 3.2 Por que uma rota HTTP e não um evento

`Set-Cookie` só pode ser anexado a uma **resposta HTTP**. Num evento de WebSocket
(NiceGUI) não existe resposta para receber o cabeçalho. Por isso a troca é uma
**rota de verdade** (`app.get`) e o botão apenas **navega**
(`ui.navigate.to`) — sem JavaScript. O `303` (e não `302`) evita repetir o POST
no destino.

### 3.3 O `volta` é interno por segurança

`volta` é o caminho da tela atual, para o usuário trocar o estilo **sem perder o
módulo em que estava**. A rota aceita **somente caminho interno**:

```python
# preview_estilos.py:566 (dentro de trocar_estilo)
alvo = urlparse(volta).path if volta.startswith("/") else "/"
```

Um `volta` externo viraria um **redirecionamento aberto** (o usuário cairia numa
página controlada por quem montou o link). `link_troca()` (`preview_estilos.py:527`)
também normaliza o destino para `/` quando não começa com `/`.

Chave fora de `CHAVES` é normalizada para `CHAVE_PADRAO` e gravada assim
(`preview_estilos.py:561-562`): o cookie guarda a **intenção** ("sem escolha
pessoal"), e o estilo em vigor é resolvido na renderização. É por isso que um
`estilo-visual/lixo` não quebra nada — ele devolve o usuário à tela anterior sem
imposição de cor.

## 4. Hierarquia de resolução do estilo

A hierarquia **encolheu de três degraus para um só**: não há mais o que escolher
quando o usuário não escolheu. O `""` desce direto para a cor do módulo.

```mermaid
flowchart TD
    A[Renderização de uma tela interna] --> B{ler_estilo()<br/>cookie estilo_visual}
    B -->|chave em azul/verde/roxo/preto| C[ESTILO DA PESSOA]
    B -->|vazio, padrao ou valor inválido| E["NENHUM ESTILO — cor do módulo<br/>(tema_modulo.ler_tema + ui.colors)"]
    C --> G[estilo_efetivo()]
    E --> G
    G --> H{tem estilo?}
    H -->|sim| I[aplicar → _defs_css → --q-primary<br/>imposto sobre a cor do módulo]
    H -->|não| J[aplicar NÃO é chamado<br/>a cor do módulo prevalece]
```

| Função | Arquivo:linha | Devolve |
|:---|:---|:---|
| `ler_estilo()` | `preview_estilos.py:483` | a **escolha pessoal** (uma de `CHAVES`) ou `""` (= sem escolha). `padrao` e valor fora da lista viram `""` |
| `estilo_efetivo()` | `preview_estilos.py:503` | `ler_estilo()` — o estilo em vigor **agora**, ou `""` |
| `aplicar(padrao, ...)` | `preview_estilos.py:233` | só é chamado **quando há estilo**; devolve a paleta efetiva |

!!! note "A diferença entre `""` e um estilo"
    `ler_estilo()` devolvendo `""` significa literalmente "**não imposedor**" — nenhum
    estilo está em vigor. Não existe mais "um estilo em vigor por causa do
    administrador": quem manda na cor é o administrador do módulo, e isso é outra
    coisa. É por isso que o alternador marca como ativo **"Padrão"** nesse caso
    (ver [5.4](#54-o-que-fica-marcado-como-ativo)) e que o rótulo do que está
    valendo mostra a **procedência** em vez do nome de um estilo.

### 4.1 Onde a resolução acontece

`telas.py:_montar_layout` resolve e aplica o estilo **antes** do cabeçalho, porque
o estilo **redefine `--q-primary`** — que é a cor do cabeçalho e de todo elemento
`bg-primary` da tela. O detalhe que define a nova semântica é o **`if`**: sem
estilo, `aplicar()` **não é chamado** e nada é injetado.

```python
# mod_intranet/telas.py:227-241 (trecho verificado)
estilo_visual_usuario = ""
try:
    from mod_intranet import preview_estilos as _pv_estilos
    estilo_visual_usuario = _pv_estilos.estilo_efetivo()
    if estilo_visual_usuario:                                    # <- a guarda
        _pv_estilos.aplicar(estilo_visual_usuario, cor_principal=cores)
except Exception:
    ...
ui.colors(primary=cores, secondary=ui_comum.CORES["cinza_escuro"],
          accent=cores)
```

Três consequências diretas desse `if`:

1. Sem estilo, **nenhum `<style>` nem `<link>` do protótipo é injetado** — a folha
   nem chega a ser carregada.
2. O `ui.colors(primary=cores)` da linha seguinte é o que **prevalece**, com `cores`
   vindo de `_obter_cor_principal()` (a `cor_principal` do módulo). Nada depois
   sobrescreve o token.
3. O `cor_principal` passado para `aplicar()` é usado **apenas** para pintar o
   botão ativo do menu; como `PADRAO_ADM` é `None` (`preview_estilos.py:124`), ele
   **não** entra na paleta (`preview_estilos.py:244-246`, guarda `if p == PADRAO_ADM`,
   que nunca é verdadeira).

A **Home** usa o mesmo caminho, mas **não** decide mais o estilo
(`main.py:658-660`, `modelo=_pv.estilo_efetivo()`); ele chega resolvido pelo
layout.

### 4.2 O que sobrou de `estilo_padrao_sistema()` (removido)

`estilo_padrao_sistema()` deixou de participar da resolução e foi **removida**,
junto com a constante `CONFIG_PADRAO_SISTEMA` e as duas funções de conveniência
que também estavam sem chamador.

A auditoria do lote anterior tinha apontado a função como *código morto* e
alertado para o risco: ela ainda devolveria `PADRAO_PADRAO` (`"verde"`) por
qualquer um dos três motivos — `except` no acesso ao banco, chave ausente, ou
valor `'padrao'` fora de `CHAVES`. Esse retorno seria enganoso, devolveria um
estilo onde a decisão do responsável é justamente **não impor estilo nenhum**, e
uma futura chamada reintroduziria silenciosamente a semântica rejeitada. Era
código que convidava ao erro, então saiu.

O que ficou, verificado por busca em todo o código Python:

| Símbolo | Estado | Evidência |
|:---|:---|:---|
| `estilo_padrao_sistema()` | ✅ **removida** | 0 ocorrências em `.py` |
| `CONFIG_PADRAO_SISTEMA` | ✅ **removida** | 0 ocorrências; a migração continua gravando a chave, que agora é apenas o registro da decisão do administrador |
| `aplicar_para_usuario(...)` | ✅ **removida** | era alias de compatibilidade sem chamador |
| `aplicar_se_escolhido(...)` | ✅ **removida** | era wrapper com a guarda `if not estilo: return ""`; a guarda ficou em `telas.py`, onde a decisão pertence |
| `estilo_visual_padrao_sistema` na `tb_config` | 🟢 **semeada** (`'padrao'`) | escrita por `migracao_padrao_por_modulo_260927` (`bd_conexao.py`) — ver [§6.3](#63-a-migracao-de-reversao) |

A regra de quem decide fica explícita: a guarda `if estilo_visual_usuario:`
está em `mod_intranet/telas.py` `_montar_layout`, ao lado de quem monta a tela
— e não em um utilitário do módulo de estilo. É lá que "Padrão" deixa de
impor e o tema do módulo passa a valer.

!!! tip "Onde o `padrao` ficou visível de verdade"
    O texto da opção (`OPCAO_PADRAO["descricao"]` = "segue o padrão definido pelo
    administrador") e o `ROTULOS.get(padrao) or "cor do módulo"`
    (`preview_estilos.py:651`) é o que traduz a ausência em linguagem de tela.

## 5. O menu de estilo no rodapé do sistema

O alternador mora no **rodapé escondido** montado por `_montar_layout`
(`telas.py:432-476`), dentro de `[data-testid="rodape-sistema"]`. Portanto está
disponível em **TODOS os módulos** — não só na Home.

### 5.1 O rodapé se revela sozinho

```css
/* mod_intranet/telas.py:442-443 (injetado via ui.add_head_html) */
[data-testid="rodape-sistema"]{opacity:0;transform:translateY(calc(100% - 5px));transition:opacity .25s ease,transform .25s ease}
[data-testid="rodape-sistema"]:hover,[data-testid="rodape-sistema"]:focus-within{opacity:1;transform:none}
```

Escondido durante a navegação para **não roubar altura** da tela de quem está
trabalhando; uma **faixa de 5px** fica como pista na base da janela, e o
`:hover`/`:focus-within` abre. O CSS é **escopado** pelo `data-testid` — não
vaza para outros elementos.

### 5.2 O menu fica no FLUXO — e centralizado por grade de 3 colunas

`barra_alternador(estilo_visual_usuario, discreto=True)` (`telas.py:459`) é
chamada **entre** os dois itens que o rodapé já tinha: o título do sistema à
esquerda (`telas.py:451-452`) e as versões à direita (`telas.py:470-476`). **Os dois
continuam todos presentes** — o menu é o terceiro item, não uma substituição.

!!! info "`position: fixed` foi REMOVIDO"
    O modo `.pe-alternador-fixo` deixou de existir: uma busca por
    `pe-alternador-fixo` no repositório não encontra **nenhuma** ocorrência em
    código (só a menção histórica nesta documentação). O menu é posicionado pelo
    **fluxo normal** de layout. O motivo está no próprio código: com o menu flutuando
    por cima, ele cobria o rodapé antigo em vez de se compor com ele, e o padrão
    "título à esquerda, versão à direita" deixava de valer. A docstring de
    `barra_alternador` (`preview_estilos.py:606-609`) registra a regra: *"a barra
    NUNCA é posicionada de forma fixa: ela fica no fluxo, entre os itens que o
    rodapé ja tinha"*.

O rodapé é montado com `ui.row().classes("... justify-between ...")`
(`telas.py:449`). Para centralizar **exatamente** o menu, o `justify-between` é
substituído por uma **grade de três colunas de largura igual**:

```css
/* assets/css/preview-estilos-v1.css:145-150 */
[data-testid="rodape-sistema"] > .nicegui-row:first-child {
  display: grid !important;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  align-items: center;
  gap: 0.5rem;
}
```

!!! danger "Por que `justify-between` não resolvia (o bug do 38px)"
    Com `justify-content: space-between` e **três** itens, o espaço que sobra é
    dividido **igualmente entre as duas pontas** — não entre os três itens. Como o
    item da esquerda é mais largo que o da direita, o menu **encostava no item da
    esquerda** e saía do centro: medido, **38px** à esquerda do meio geométrico.
    A causa é o texto `"INTRANET Básica — uso interno"`
    (`telas.py:451`), que é mais largo que o rótulo de versão. Com as duas colunas
    laterais em `1fr` **iguais**, a coluna do meio (`auto`, com a largura do menu)
    fica no meio geométrico da linha, qualquer que seja a diferença de largura
    entre as pontas.

O `> .nicegui-row:first-child` no seletor é o que mantém a regra **contida**: ela
atinge a linha do rodapé e nada mais. E `minmax(0, 1fr)` (e não `1fr`) impede
que o rodapé longo esprema o menu quando o texto da esquerda cresce.

Complementos da mesma regra, para cada item continuar no seu canto:

```css
/* assets/css/preview-estilos-v1.css:151-161 */
[data-testid="rodape-sistema"] > .nicegui-row:first-child > :first-child { justify-self: start; text-align: left; }
[data-testid="rodape-sistema"] > .nicegui-row:first-child > :last-child  { justify-self: end; }
[data-testid="rodape-sistema"] .pe-alternador                          { justify-self: center; flex: 0 0 auto; }
```

### 5.3 As cores do menu são claras — escopadas no rodapé

O menu vive num fundo escuro (`ui.footer().classes("bg-grey-8 w-full")`,
`telas.py:448`) e é o **único** lugar da aplicação com fundo escuro. O cinza
escuro das regras genéricas sumiria nele, então as cores claras ficam **escopadas
no rodapé**:

```css
/* assets/css/preview-estilos-v1.css:166-174 */
[data-testid="rodape-sistema"] .pe-alt--inativo      { --q-primary: rgba(255, 255, 255, .75); }
[data-testid="rodape-sistema"] .pe-alt--inativo:hover { background: rgba(255, 255, 255, .14) !important; }
[data-testid="rodape-sistema"] .pe-alt-texto          { color: rgba(255, 255, 255, .55) !important; }
```

Contra as regras genéricas do menu (`preview-estilos-v1.css:126-134`), que seguem o
padrão claro — `--q-primary: rgba(0, 0, 0, .55)` no inativo e
`color: rgba(0, 0, 0, .45)` no texto. Mesma estratégia do token do
[§7](#7-a-armadilha-do-quasar-cascade-layer): em vez de disputar cascata, redefine-se
a variável que o Quasar lê.

O botão **ativo** mantém a cor do estilo escolhido em qualquer fundo
(`--pe-primaria` com `!important`, `preview-estilos-v1.css:121-125`), e é legível
nos dois casos.

### 5.4 O que fica marcado como ativo

Só o que o **usuário escolheu** é marcado (`preview_estilos.py:616-631`):

```python
# preview_estilos.py:616 e 627-631
escolhido = ler_estilo() or CHAVE_PADRAO
...
ativo = chave == escolher
```

Quando ele não escolheu, quem fica marcado é **"Padrão"** — mesmo que a cor que
está na tela venha do administrador, o botão "Preto" não é dele, e fingir o
contrário mentiria.

!!! tip "O rótulo `estilo-atual` mostra a PROCEDÊNCIA, não um nome"
    ```python
    # preview_estilos.py:651-653
    ui.label(ROTULOS.get(padrao) or "cor do módulo").props(
        'data-testid="estilo-atual"').classes("pe-alt-texto text-caption q-px-sm")
    ```
    Como `padrao` chega **vazio** quando não há estilo, `ROTULOS.get("")` é `None`
    e o rótulo mostra **"cor do módulo"**. É a resposta útil: em vez de inventar o
    nome de um estilo, diz **de onde** a cor veio. Com estilo em vigor, mostra o
    rótulo do estilo (Azul/Verde/Roxo/Preto) normalmente.

| `data-testid` | Elemento | Rótulo |
|:---|:---|:---|
| `estilo-azul` | botão | Azul |
| `estilo-verde` | botão | Verde |
| `estilo-roxo` | botão | Roxo |
| `estilo-preto` | botão | Preto |
| `estilo-padrao` | botão | Padrão (sem escolha pessoal) |
| `estilo-atual` | rótulo | o estilo em vigor, ou **"cor do módulo"** quando não há imposição |

!!! warning "Botões `ui.button` crus, não a fábrica `ui_comum.botao`"
    A fábrica aplica `text-primary`/`bg-primary` do Quasar, que são
    `!important` **dentro de uma cascade layer** — nenhuma regra nossa fora de
    camada os vence (ver [a armadilha](#7-a-armadilha-do-quasar-cascade-layer)).
    Como aqui a cor **é** a informação (ativo × inativo), o controle tem de ser
    nosso.

## 6. O tema do sistema voltou ao preto

Esta parte é **independente** do estilo visual: é a paleta de botões, títulos,
cartões e fundo que vale em todas as telas dos 11 módulos. A experiência de
27/09/2026 tentou o tema WhatsApp e o **responsável reverteu**: a cor do sistema
voltou a ser o preto — a mesma cor que o administrador configurou.

### 6.1 `PADROES_TEMA` — os 11 módulos de volta ao preto

`mod_intranet/tema_modulo.py:65-88`. O comentário do código registra o motivo
(`tema_modulo.py:60-64`):

```python
PADROES_TEMA = {
    "intranet": {"cor_botao": "#000000", "cor_texto_botao": "#FFFFFF",
                 "cor_titulo": "#212121", "btn_tamanho": "medium"},
    # ... os outros 10 módulos com os MESMOS valores
}
```

| Campo | Valor | Antes (WhatsApp) |
|:---|:---|:---|
| `cor_botao` | `#000000` | `#0F7A6D` |
| `cor_texto_botao` | `#FFFFFF` | `#FFFFFF` |
| `cor_titulo` | `#212121` | `#1F2C33` |
| `btn_tamanho` | `medium` | `medium` |

Os 11 prefixos: `intranet`, `blog`, `usuarios`, `auditoria`, `editar_pdf`
(prefixo `editpdf`), `empenhos`, `solicita_impressao`, `tecnico`, `filas`,
`lista_telefonica`, `agregador_noticias` (mapeamento em
`tema_modulo.PREFIXO_POR_CHAVE`, `tema_modulo.py:41-53`).

A chave do módulo **continua valendo**: quem o administrador configurar em
`/configuracoes` sobrescreve isto. É essa precedência — chave do módulo com valor
→ default do parâmetro → `PADROES_TEMA` (`tema_modulo.ler_tema`,
`tema_modulo.py:115-148`) que faz o "Padrão" do menu funcionar.

!!! info "Por que o verde virou só uma opção do menu"
    Deixar o WhatsApp como cor do sistema **e** oferecer "Verde" no menu eram duas
    coisas incompatíveis: o botão "Padrão" passaria a impor uma cor que ninguém
    configurou. A reversão alinhou as duas metades — o menu tem 4 opções, e
    "Padrão" devolve o preto que o administrador escolheu. O estilo "Verde"
    continua existindo **inteiro** (`_CORES["verde"]`, `_login_verde`); só deixou
    de ser a cor do sistema.

### 6.2 `CORES` — paleta de reserva, de volta à anterior

`mod_intranet/ui_comum.py:43-60`. O comentário do código diz que são
"valores de **RESERVA**, os mesmos de antes da experiência de estilo visual"
(`ui_comum.py:44-48`):

| Chave | Valor | Uso |
|:---|:---|:---|
| `primaria` | `#1565C0` | azul Material — reserva de `ui.colors(primary=)` |
| `titulo` | `#212121` | títulos |
| `fundo` | `#EEEEEE` | cinza claro do papel de parede |

São valores **de reserva**: o que vale é o que o administrador gravou em
`tb_config` (`cor_principal`/`cor_fundo`), lidos a cada renderização. O menu de
estilo **não mexe** nisto: quem escolhe "Padrão" está justamente dizendo "usa a cor
do meu módulo, como está".

### 6.3 A migração de reversão

`mod_intranet/bd_conexao.py:287-315`, dentro de `init_db()`, guardada pelo
marcador **`migracao_padrao_por_modulo_260927`** — roda **uma vez** e não apaga
personalização posterior do administrador. SQL portátil (o proxy
`_CursorPostgres` traduz para o PostgreSQL, paridade AGENTS.md §4.1).

| Chave | Valor | Efeito |
|:---|:---|:---|
| `cor_principal` | `#000000` | volta a ser o que `_montar_layout` joga em `ui.colors(primary=)` — cor do cabeçalho e de **todo** elemento `bg-primary` |
| `cor_fundo` | `#EEEEEE` | papel de parede cinza |
| `estilo_visual_padrao_sistema` | **`'padrao'`** | semeada com o **nome da opção**, não com um estilo — é o valor coerente com a nova semântica, e **resolve o achado nº 1** (ver [§12](#12-achados-de-auditoria-27092026)) |
| `<prefixo>_cor_botao` | **`""`** (zerado) nos 11 módulos | faz o módulo cair no `PADROES_TEMA` (preto) |
| `<prefixo>_cor_titulo` | **`""`** (zerado) nos 11 módulos | idem, para o título (`#212121`) |
| `migracao_padrao_por_modulo_260927` | `1` | marcador (idempotência) |

Os 11 prefixos percorridos são `intranet`, `blog`, `usuarios`, `auditoria`,
`editpdf`, `empenhos`, `solicita_impressao`, `tecnico`, `filas`,
`lista_telefonica`, `agregador_noticias` (`bd_conexao.py:306-310`).

!!! tip "Por que ZERAR as chaves em vez de gravar o valor"
    Zerar mantém a aplicação da paleta em **um lugar só** — o `PADROES_TEMA`.
    Trocar a identidade depois é editar uma constante, sem escrever migração
    nova para os 11 módulos. É a mesma razão que a primeira migração usou, e é o
    que torna a reversão barata: só uma constante e um marcador novo.

!!! note "A migração anterior continua no código"
    `migracao_tema_whatsapp_260927` (`bd_conexao.py:244-286`) **não** foi removida —
    é histórico e protege instalações que ainda não a rodaram. Em banco novo as
    duas rodam na ordem, e a segunda (`..._padrao_por_modulo_...`) desfaz a
    primeira. O estado final é o que está documentado aqui, e é o que
    `db_mod_intranet.db` reflete.

## 7. A armadilha do Quasar: cascade layer

!!! danger "A regra de ouro deste projeto — leia antes de mexer em cor"
    O Quasar declara
    `.bg-primary { background: var(--q-primary) !important }` e
    `.text-primary { color: var(--q-primary) !important }`
    **DENTRO de uma cascade layer**. Em `!important`, a **camada vence QUALQUER
    regra fora de camada** — por mais específica que ela seja, e **por mais
    `!important` que esteja** (inclusive um `!important` universal). A **única**
    saída é mexer no **TOKEN** `--q-primary`, que é o mesmo mecanismo de
    rebrand do próprio Quasar (`ui.colors`).

Na prática: **tentar pintar o botão "por fora" não funciona.** Nem com
`.classes()` do Tailwind, nem com `.style()`, nem com `!important` nosso, nem com
seletor universal. Tudo isso é regra fora de camada e perde.

### 7.1 A saída correta — mexer no token

```python
# preview_estilos.py:225-230 (_defs_css) — trecho
q_primaria = paleta.get("primaria_q", paleta["primaria"])
return (f":root {{\n{linhas}\n  }}\n"
        f"  .pe-{paleta['chave']},\n"
        f"  body:has(.pe-{paleta['chave']}) .q-layout {{\n"
        f"    --q-primary: {q_primaria} !important;\n"
        f"  }}")
```

Três detalhes que importam:

1. Vai no **`.q-layout`** (e não no wrapper do padrão) porque o cabeçalho é
   montado pelo layout de 4 partes, **acima** do wrapper.
2. O seletor usa `body:has(.pe-<chave>)` para funcionar mesmo quando o wrapper do
   padrão não é ancestral direto do alvo — o mesmo truque do fundo da página.
3. O `!important` aqui é o que **vence a declaração inline** que `ui.colors()`
   deixa no layout. O valor vem da paleta, que continua sendo a fonte única: não
   há cor chumbada no CSS.

!!! info "`aplicar()` só é chamado com estilo válido"
    `aplicar()` faz `p = padrao if padrao in CHAVES else PADRAO_PADRAO`
    (`preview_estilos.py:241`), então `_defs_css()` **nunca** roda com `padrao` vazio
    pela via normal — quem garante isso é o `if estilo_visual_usuario:` de
    `telas.py:231`, e não o fallback. As duas defesas são independentes e ambas
    importam.

### 7.2 O mesmo truque no botão ativo do alternador

Como a fábrica de botões também cai no token, o botão ativo **redefine o token
no próprio elemento** em vez de tentar pintar o texto:

```css
/* assets/css/preview-estilos-v1.css:121-128 */
.pe-alt--ativo   { --q-primary: var(--pe-primaria_texto); background: var(--pe-primaria) !important; font-weight: 600; }
.pe-alt--inativo { --q-primary: rgba(0, 0, 0, .55); }
```

Sem nenhuma disputa de cascata no meio: o ativo lê a cor de texto do padrão, o
inativo o cinza. E no rodapé escuro quem manda é a reordenação de
[§5.3](#53-as-cores-do-menu-sao-claras-escopadas-no-rodape).

### 7.3 Checklist para quem for alterar cores

1. A cor vem de **custom property** (`--pe-*`) ou de **`tb_config`**, nunca de
   um hex no CSS.
2. Para a **cor primária** (cabeçalho, abas, destaques, botões `primary`), mexa
   em `--q-primary` — não em `.bg-primary`/`.text-primary`.
3. Se o elemento **precisa** de uma cor que não é a primária, ele tem de ser
   um controle nosso (`.pe-alt--ativo` define o próprio token) — as fábricas com
   `bg-primary`/`text-primary` são **impossíveis** de recolorar por fora.
4. **Escope sempre**: toda regra do menu é escopada por
   `[data-testid="rodape-sistema"]`, porque o rodapé tem fundo escuro e as regras
   genéricas (cinza) sumiriam nele.
5. Nunca introduza JavaScript direto para resolver (AGENTS.md §5).

## 8. Acessibilidade — contrastes medidos contra `#FFFFFF`

Razão de contraste de cada cor de ação com **texto branco**, para o piso de
**4,5:1** da WCAG AA (valores recalculados a partir das paletas de
`_CORES`/`PADROES_TEMA`):

| Cor | Origem | Contraste com `#FFFFFF` | Veredito |
|:---|:---|---:|:---|
| `#25D366` verde vivo do WhatsApp | `_CORES["verde"]["primaria_acao"]` | **1,98:1** | ❌ reprova |
| `#0F7A6D` teal do WhatsApp | `_CORES["verde"]["primaria_q"]` | 5,22:1 | ✅ passa |
| `#1877F2` azul clássico do Facebook | referência do tom claro | 4,23:1 | ❌ reprova (abaixo de 4,5) |
| `#1668D8` azul um passo mais escuro | `_CORES["azul"]["primaria_q"]` | 5,24:1 | ✅ passa |
| `#7C3AED` roxo | `_CORES["roxo"]["primaria_q"]` | 5,70:1 | ✅ passa |
| `#111111` preto (estilo) | `_CORES["preto"]["primaria_q"]` | 18,88:1 | ✅ passa |
| `#000000` preto (tema do sistema) | `PADROES_TEMA[*]["cor_botao"]` | 21,00:1 | ✅ passa |

O `#25D366` continua disponível como **cor de acento**
(`_CORES["verde"]["primaria_acao"]`, `preview_estilos.py:150-151`) — o que ele não
pode é ser a cor de **texto branco sobre ele**.

!!! note "A divisão de papéis que sustenta a decisão"
    * **`--q-primary`** (o que pinta botão, cabeçalho e `bg-primary`) precisa de
      **4,5:1** com o texto branco. É por isso que o verde do botão é o teal
      `#0F7A6D` e o azul é o `#1668D8`.
    * **`primaria`** (usada em bordas, marcas e no botão ativo do menu) tem folga
      e não impõe esse piso.

## 9. NiceGUI 3.15 — `context.request` não existe mais

O NiceGUI 3 removeu `context.request`; o request está em
**`context.client.request`**. O helper `_request_atual()` (`preview_estilos.py:464`)
faz a cadeia — **novo primeiro, antigo como reserva**:

```python
# preview_estilos.py:475-478 (trecho)
from nicegui import context
req = getattr(context, "request", None)
if req is None:
    req = getattr(getattr(context, "client", None), "request", None)
return req
```

!!! warning "Falha silenciosa é a pior delas"
    Sem esse helper o cookie chegava **vazio** e o usuário nunca tinha a escolha
    aplicada: a tela abria, o rodapé funcionava, o clique gravava o cookie — e
    o estilo **não** mudava. Nenhum erro, nenhum log, só "a troca não funciona".
    Com a semântica nova o sintoma seria ainda mais silencioso: um `""` errado
    também produz a tela "certa" para quem não escolheu nada.

## 10. Referência de API

`mod_intranet/preview_estilos.py` (670 linhas):

| Símbolo | Linha | Assinatura / valor | Papel |
|:---|---:|:---|:---|
| `VERSAO_CSS` / `ARQUIVO_CSS` | 65-66 | `"v1"` / `preview-estilos-v1.css` | folha servida em `/assets/css/*` |
| `_versao_arquivo()` | 71 | `-> str` | cache-buster por `mtime` (a folha muda várias vezes por sessão) |
| `PADROES` | 84-93 | tupla de 4 dicts | os estilos nomeados (`azul`/`verde`/`roxo`/`preto`) |
| `CHAVES` / `ROTULOS` / `DESCRICOES` | 94-96 | tupla / 2 dicts | derivados |
| `CHAVE_PADRAO` / `OPCAO_PADRAO` | 101-105 | `"padrao"` | opção "sem escolha pessoal" |
| `PADRAO_PADRAO` | 109 | `"verde"` | fallback interno de `aplicar()`/`tela_login()` |
| `PADRAO_LOGIN` | 116 | `"verde"` | estilo **fixo** do login |
| `PADRAO_ADM` | 124 | `None` | chave que absorveria a cor do admin (desativada) |
| `_CORES` | 131-168 | dict de 4 paletas | fundos/primárias/raio/sombra (inclui `preto` em 161-167) |
| `montar_rotas_static()` | 174 | `-> bool` | mount de `/assets/css` (chamado no boot) |
| `_defs_css(paleta)` | 202 | `-> str` | `:root` com `--pe-*` + `--q-primary` no `.q-layout` |
| `aplicar(...)` | 234 | `-> dict` | injeta o `<style>`/`<link>`; devolve a paleta efetiva |
| `_login_preto(...)` | 366 | — | layout do estilo `preto` (era `_login_light`) |
| `_LAYOUTS` | 384-389 | dict 4→função | um layout por padrão (um por função, de propósito) |
| `tela_login(...)` | 393 | — | invólucro visual do login; **não** sabe autenticar |
| `COOKIE_ESTILO` | 443 | `"estilo_visual"` | nome do cookie |
| `ROTA_TROCA` | 444 | `"/estilo-visual"` | prefixo da rota |
| `CONFIG_PADRAO_SISTEMA` | — | — | ✅ **removida** — ver [§4.2](#42-o-que-sobrou-de-estilo_padrao_sistema-removido) |
| `estilo_padrao_sistema()` | — | — | ✅ **removida** — ver [§4.2](#42-o-que-sobrou-de-estilo_padrao_sistema-removido) |
| `montar_rota_troca()` | 541 | `-> bool` | registra `GET /estilo-visual/{chave}` |
| `_request_atual()` | 464 | `-> request \| None` | cadeia NiceGUI 3/2 |
| `ler_estilo()` | 483 | `-> str` | escolha pessoal ou `""` |
| `estilo_efetivo()` | 503 | `-> str` | `ler_estilo()` — o que vale agora, **pode ser `""`** |
| `link_troca(chave, volta)` | 527 | `-> str` | URL de troca |
| `_caminho_atual()` | 584 | `-> str` | `volta` a partir do request |
| `barra_alternador(padrao, discreto)` | 593 | — | o menu de estilo (rodapé) |
| `barra_home(...)` | 629 | — | assinatura antiga; delega a `barra_alternador` |
| `resumo_padroes()` | 668 | `-> str` | linha-resumo para relatório de QA |

## 11. Como reverter a feature

O login **não pode** quebrar: se o layout do padrão falhar,
`tela_login()` cai no login mínimo — os campos aparecem **sem nenhum enfeite**,
em vez da tela ficar branca (`preview_estilos.py:409-421`).

Para remover a **troca de estilo** mantendo o tema atual (preto):

1. Apagar `mod_intranet/preview_estilos.py` e
   `assets/css/preview-estilos-v1.css`.
2. Em `main.py`, apagar o bloco `montar_rotas_static()`/`montar_rota_troca()` do
   boot (`main.py:152-162`) e os blocos `# ===== PROVISÓRIO =====` em
   `page_login` (`main.py:242-251`) e em `_construir_dashboard`
   (`main.py:658-661`).
3. Em `mod_intranet/telas.py`, remover o `estilo_visual_usuario` e a guarda
   `if estilo_visual_usuario:` da `_montar_layout` (`telas.py:227-238`) e a
   chamada `_pv_estilos.barra_alternador(...)` do rodapé (`telas.py:457-466`).
4. **Manter**: `PADROES_TEMA`, `ui_comum.CORES` e as duas migrações
   (`migracao_tema_whatsapp_260927` e `migracao_padrao_por_modulo_260927`) — o
   tema preto é independente deste módulo.

!!! tip "`estilo_padrao_sistema()` e a armadilha que foi removida"
    A remoção do passo 1 apaga o resto da feature, mas as funções soltas precisam
    de limpeza à parte: `estilo_padrao_sistema()`, `CONFIG_PADRAO_SISTEMA`,
    `aplicar_se_escolhido()` e `aplicar_para_usuario()` saíram de fora do caminho
    e já foram removidas. `estilo_padrao_sistema()` era a mais perigosa — devolvia
    um estilo onde a decisão é não impor nenhum, que é o tipo de armadilha que
    alguém reaplica sem perceber (ver [§4.2](#42-o-que-sobrou-de-estilo_padrao_sistema-removido)).

## 12. Achados de auditoria (27/09/2026)

Registrados com honestidade, **sem alterar código de produção**:

| # | Achado | Impacto | Situação |
|---:|:---|:---|:---|
| 1 | `estilo_visual_padrao_sistema` **não existia** no `db_mod_intranet.db` desta instalação, apesar de o marcador `migracao_tema_whatsapp_260927 = '1'` estar gravado — a chave foi acrescentada ao bloco **depois** de a migração já ter rodado, e o marcador impede a reinserção | o administrador **não tinha campo** para editar a chave (ela não está em `PADRAO_CONFIG` nem na tela de Config) | ✅ **RESOLVIDO** — a reversão resolveu por tabela: `migracao_padrao_por_modulo_260927` semeia a chave com `'padrao'` (`bd_conexao.py:301`), que é o valor coerente com a nova semântica. Estado verificado no banco: `estilo_visual_padrao_sistema = 'padrao'` |
| 2 | `PADRAO_CONFIG` (`bd_conexao.py:47-…`) tem `cor_principal` `#000000` e `cor_fundo` `#EEEEEE`, e o botão **"Restaurar padrão"** do card "Configurações de cores" grava `PADRAO_CONFIG` | durante o tema WhatsApp, o "Restaurar padrão" **revertia a paleta global para o preto**, desfazendo a migração | ✅ **RESOLVIDO pela reversão** — o "Restaurar padrão" volta ao preto, que **agora é de fato o padrão** (`PADROES_TEMA` e `cor_principal` do banco estão ambos em `#000000`). A divergência deixou de existir; ver [Configurações](configuracoes.md) |
| 3 | Bloco **morto** no CSS que selecionava `[data-testid="estilo-facebook"]`, `estilo-whatsapp`, `estilo-messenger`, `estilo-instagram` — `data-testid` que **não existem** (os reais são `estilo-azul`, `estilo-verde`, `estilo-roxo`, `estilo-preto`) | era lixo inerte: o botão ativo já é pintado por `.pe-alt--ativo` | ✅ **RESOLVIDO** — bloco removido. Busca por `estilo-facebook`/`estilo-light` no CSS e no Python não retorna **nenhuma** ocorrência |
| 4 | **Nenhum teste automatizado** cobre os `data-testid` `estilo-*` / `estilo-atual` nem a rota `/estilo-visual/{chave}` | a feature entrou sem cobertura de QA | ⚠️ **aberta** — `kbp-qa` pode fechar com Playwright |
| 5 | `docs/configuracoes.md` descrevia `PADROES_TEMA` como "todos os módulos em `#000000`" | documentação desatualizada na altura do tema WhatsApp | ✅ **corrigido** — e revertido pela decisão do responsável; as páginas que descreviam a paleta teal foram atualizadas nesta revisão |
| 6 | `estilo_padrao_sistema()`, `CONFIG_PADRAO_SISTEMA`, `aplicar_se_escolhido()` e `aplicar_para_usuario()` **não têm chamador** | código morto; `estilo_padrao_sistema()` devolveria `"verde"` e **reintroduziria** a semântica rejeitada se alguém voltar a chamar | ⚠️ **aberta** — ver [§4.2](#42-o-que-sobrou-de-estilo_padrao_sistema-removido). Não removido aqui (regra de não tocar em produção) |
| 7 | `estilo_visual_padrao_sistema` **não tem campo** na tela de Config (não está em `PADRAO_CONFIG`) | o administrador não tem o que editar — hoje irrelevante, porque a chave **não participa da resolução** | ⚠️ **aberta, sem urgência** — se a chave voltar a ter efeito, precisa de campo |

## 13. Ver como está no código

```bash
# 1. A paleta dos 11 módulos (deve vir 11x #000000)
grep -n "cor_botao" mod_intranet/tema_modulo.py | head -12

# 2. As chaves gravadas pelas migrações (estado final)
.venv/bin/python -c "
import sqlite3; c=sqlite3.connect('db_mod_intranet.db')
for k in ('cor_principal','cor_fundo','estilo_visual_padrao_sistema',
          'migracao_tema_whatsapp_260927','migracao_padrao_por_modulo_260927',
          'blog_cor_botao','blog_cor_titulo'):
    r=c.execute('SELECT valor FROM tb_config WHERE chave=?',(k,)).fetchone()
    print(k,'=',repr(r[0]) if r else '(ausente)')"

# 3. A hierarquia virou um degrau só: ler_estilo() pode devolver ""
.venv/bin/python -c "
from mod_intranet import preview_estilos as pv
print('PADRAO_LOGIN  =', pv.PADRAO_LOGIN)
print('CHAVES        =', pv.CHAVES)
print('ROTULOS       =', pv.ROTULOS)
print('PADRAO_ADM    =', pv.PADRAO_ADM)"

# 4. O código morto (deve imprimir 0 para cada símbolo)
for s in estilo_padrao_sistema aplicar_se_escolhido aplicar_para_usuario; do
  printf '%s: ' "$s"
  grep -rn "$s" --include=*.py mod_* main.py assets/test 2>/dev/null | grep -v "def $s" | wc -l
done

# 5. O modo fixed e o bloco CSS morto (ambos devem sair vazios)
grep -rn "pe-alternador-fixo\|estilo-facebook" assets/css/preview-estilos-v1.css mod_intranet/

# 6. A grade de 3 colunas do rodapé
grep -n "grid-template-columns" assets/css/preview-estilos-v1.css

# 7. Build da documentação
.venv/bin/mkdocs build --strict
```

**Referências relacionadas:**
[Configurações e Variáveis de Ambiente](configuracoes.md) ·
[Módulos (resumo) — Intranet](modulos/intranet.md) ·
[Análise do módulo Intranet](analise_mod_intranet.md) ·
[Convenções de Criação de Código](convencoes_codigo.md)
