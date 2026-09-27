# Teste de carga e uso — Intranet Modular

> Mede se a intranet **aguenta N usuários que estão de fato usando o sistema**,
> não apenas N sockets abertos. É o complemento do
> [teste de carga k6](testes_carga_k6.md): aquele segura clientes, este faz
> gente entrar, navegar, ler e pedir impressão.

---

## O resumo, em uma frase

**120 usuários de protocolo (k6) + 20 navegadores reais (Playwright), ao mesmo
tempo, por 15 minutos, com um vigia que interrompe tudo se a máquina passar de
90 %.**

| peça | volume | o que ela responde |
|---|---:|---|
| `assets/k6/carga_uso.js` | 120 VUs | quantos clientes o servidor segura **enquanto eles usam** |
| `assets/test/carga_uso_navegador.py` | 20 navegadores | eles conseguem **trabalhar** (clique, tela, upload) |
| `assets/test/guarda_recursos.py` | 1 processo | a máquina está aguentando, ou o teste é que está matando o sistema? |

!!! warning "O que já foi medido e o que falta"
    O **protocolo** (k6) já rodou na cronometragem completa: a 120 usuários
    **REPROVADO** e a 40 usuários **funcionalmente aprovado** com a latência acima
    do teto — os dois resultados, com todos os números, estão na seção
    **Critérios de aprovação**, mais abaixo. O que **ainda não** foi
    medido é a camada de navegador real em paralelo (20 navegadores com os 120
    do k6 ao mesmo tempo): o `carga_uso_navegador.py` foi validado com 1 a 4
    usuários. Essa bateria completa é o que o **agente principal** executa.

## A máquina

| item | valor |
|:---|:---|
| processador | Intel® Core™ i3-2375M @ 1,50 GHz (4 threads) |
| memória | **3,7 GiB** (3.795 MB), swap 5,6 GiB |
| consumo base com o servidor no ar | **~2.184 MB (58 %)** |
| consumo do OpenCode sozinho | ~1,1 GiB (é ele, não a intranet) |
| RSS do servidor, sem carga | 105 MB |
| RSS do servidor, **depois** de 120 VUs | 201 MB (medido) |

O consumo alto da máquina vem das **ferramentas de desenvolvimento** da sessão,
não do sistema sob teste. Isso é decisivo para entender o guarda de 90 %.

## Por que a arquitetura é dividida em duas

Esta intranet é **NiceGUI**, e NiceGUI não tem `POST /login`: o login é um
**evento no WebSocket**. O k6 consegue abrir o WebSocket e fazer o handshake,
mas não consegue clicar no botão "Entrar" sem acoplar o teste ao despacho
interno da biblioteca — acoplamento que quebraria a medição **em silêncio** num
upgrade, resultado pior que não medir.

Medido nesta sessão, com o cookie de sessão que o k6 obtém em `GET /login`:

| rota | bytes devolvidos | o que é |
|:---|---:|:---|
| `/` | 8 761 | stub de redirecionamento |
| `/blog` | **8 761** | **o mesmo stub** |
| `/edit-pdf` | 8 761 | o mesmo stub |
| `/renomear-empenho` | 8 761 | o mesmo stub |
| `/tv` | 14 606 | **tela real** (pública por projeto) |

Ou seja: **o k6 não renderiza tela de módulo.** Ele mede o número de clientes
que o servidor segura e a saúde do event-loop; quem mede a tela renderizada,
o clique e o upload é o Playwright com 20 navegadores. Por isso o script k6
publica a métrica `carga_uso_render_modulo`, que deve marcar ~0,1 (só `/tv`):
é o próprio limite do protocolo virando número, e não uma nota de rodapé.

## O que o teste mede

### k6 — `assets/k6/carga_uso.js` (120 VUs)

| métrica | o que diz |
|:---|:---|
| `carga_uso_handshake_ok` | fração de clientes que o **servidor assumiu** (passou a transmitir a tela). É a prova de que o cliente ficou vivo, não só que o socket abriu. |
| `carga_uso_ciclo_completo` | fração de ciclos que percorrem o roteiro inteiro de uso |
| `carga_uso_pensamento` | think time de cada passo — o threshold `min>10000` **impõe** a exigência dos 10 s |
| `carga_uso_leitura_blog` | tempo de leitura do post; threshold `min>55000` impõe o minuto |
| `carga_uso_rota_200` | fração de rotas que responderam 200 |
| `carga_uso_render_modulo` | fração de páginas que renderizaram de verdade (só `/tv` — ver acima) |
| `carga_uso_desconectou` | sockets fechados sem erro |
| `carga_uso_sonda_eventloop` | **a métrica decisiva**: p95 do `GET /favicon.ico`, que tem de continuar rápido com 120 sockets abertos |
| `carga_uso_ciclo` | duração do ciclo de uso completo (p95) |

### Playwright — `assets/test/carga_uso_navegador.py` (20 navegadores)

Cada navegador faz login **distinto** (`user001`…`user020`) e percorre:

1. **Painel** — abre a inicial, lê, e clica em botões inofensivos
2. **Agregador de Notícias** — busca e filtro de tema (a antiga tela pura
   `/agregador-noticias-puro` foi removida em 26/09/2026)
3. **Blog** — abre o feed, expande o post e **lê por 60 s**
4. **Editor de PDF** — abre a biblioteca e atualiza a lista
5. **Renomeador de Empenhos** — busca e lê a lista
6. **Solicitação de Impressão** — seleciona secretaria, **anexa um PDF de
   verdade** e (só para `--enviar` usuários) envia e **cancela** em seguida
7. **Filas e Lista Telefônica** — abre e filtra
8. **Gate de permissões** — mede para onde cada rota restrita manda o usuário

Cada passo é conferido pela **URL final**: se o gate redirecionou, o relatório
diz `BLOQUEADO pelo gate: /blog -> /` em vez de dizer que abriu. (Na primeira
versão não havia essa checagem, e o teste reportava "tela abriu" para o
Agregador de Notícias que estava bloqueado — o relatório mentia de forma
convincente.)

## O que o teste NÃO mede, e por quê

| não mede | motivo |
|:---|:---|
| **renderização de tela de módulo pelo k6** | o k6 não clica em "Entrar" (limite do protocolo). Medido: 8761 bytes de stub. Quem mede é o Playwright. |
| **custo do bcrypt do login** | o login exige o evento do WebSocket. Tem medição própria: `assets/test/mede_custo_login.py` (~0,95 s por login, ~4/s de vazão). |
| **autorização e confirmação de impressão** | `_eh_responsavel` decide quem vê a aba "Autorização"; `userNNN` é `comum` e não tem vínculo. A aba **não aparece**. A aprovação exige `administrador_geral` ou responsável vinculado — então o teste **mede o gate** em vez de forçá-lo. |
| **exclusão, recusa, recuo, cancelamento definitivo** | o filtro de cliques é por **allowlist** (`Atualizar`, `Buscar`, `Filtrar`, `Expandir`…) com uma denylist explícita por cima. O erro de uma denylist é clicar em "Confirmar exclusão" sem perceber que a palavra perigosa estava escrita de outro jeito. |
| **relatórios de 20+ navegadores** | o limite é memória, não CPU: ~37 MB por página em 3,7 GiB. 20 é o teto medido; 120 navegadores derrubariam a máquina e o teste mediria o colapso. |
| **uso administrativo** | `/configuracoes`, `/auditoria`, `/tecnico`, `/users` e `/admin/*` não são uso de servidor: são telas de administração. `/auditoria`, `/tecnico` e `/users` entram apenas como **gate medido**. |

## A cronometragem exigida, e onde ela está no código

Tudo em `options.scenarios.uso.stages`, em `assets/k6/carga_uso.js`.

| tempo | o que acontece | VUs |
|:---|:---|---:|
| 0:00 | `startVUs: 10` — já começa com 10 | 10 |
| 0:00–0:15 | rampa | 10 → 20 |
| 0:15–0:30 | rampa | 20 → 30 |
| 0:30–0:45 | rampa | 30 → 40 |
| 0:45–1:00 | rampa | 40 → 50 |
| 1:00–1:15 | rampa | 50 → 60 |
| 1:15–1:30 | rampa | 60 → 70 |
| 1:30–1:45 | rampa | 70 → 80 |
| 1:45–2:00 | rampa | 80 → 90 |
| 2:00–2:15 | rampa | 90 → 100 |
| 2:15–2:30 | rampa | 100 → 110 |
| 2:30–2:45 | rampa — **120 alcançado** | 110 → 120 |
| 2:45–11:45 | **regime: 9 minutos com 120** | 120 |
| 11:45–12:15 | descida | 120 → 60 |
| 12:15–12:35 | descida | 60 → 30 |
| 12:35–12:55 | descida | 30 → 10 |
| 12:55–13:15 | descida | 10 → 0 |

**A conta do deadline (15 min no máximo):**

```text
11 × 15 s ....................... 165 s   escalada (0:00 → 2:45)
9 × 60 s ........................ 540 s   regime (2:45 → 11:45)
30 + 20 + 20 + 20 ...............  90 s   descida (11:45 → 13:15)
                                 ─────
                                  795 s = 13:15  de estágios
gracefulStop ....................  20 s
                                 ─────
                                  815 s = 13:35      folga de 1:25
```

**Por que 15 s por degrau, e não os 20 s do enunciado.** Com 20 s a soma
batia **900 s = 15:00 exatos, sem nenhuma folga**: um único segundo de atraso
num estágio estouraria o teto. O passo de 15 s mantém os **mesmos 120
usuários** e o mesmo gate de "20 usuários por 3 min", e devolve **1:25 de
margem**. A escolha foi do responsável, em 26/09/2026, ao ver a soma.

`assets/test/valida_cronometragem.py` confere essa conta lendo o próprio
script k6 — se alguém mexer na cronometragem sem recalcular, ele reprova:

```bash
.venv/bin/python assets/test/valida_cronometragem.py
```

**O uso real começa às 0:20, não às 0:00.** Os VUs 1 a 10 já estão no ar às
0:00, então eles recebem `ESPERA_INICIAL_VU_BAIXO` (20 s) antes do primeiro
passo — é assim que os 10 primeiros entram no ciclo junto com o 11º e o 12º
usuário. A constante é `ESPERA_INICIAL_VU_BAIXO_MS` / `VU_QUE_ESPERA`.

**O roteiro de uso** é a constante `PASSOS` (9 rotas, 171 s de think time):

| rota | ação | think time |
|:---|:---|---:|
| `/` | abrir e ler o painel | 12 s |
| `/agregador-noticias` | ler as notícias | 15 s |
| `/blog` | **ler o post** | **60 s** |
| `/filas` | olhar as filas | 12 s |
| `/lista-telefonica` | procurar na lista | 12 s |
| `/renomear-empenho` | **buscar empenhos** | 18 s |
| `/edit-pdf` | abrir o editor | 15 s |
| `/solicita-impressao` | abrir a solicitação | 15 s |
| `/tv` | ver a TV das filas | 12 s |

O mínimo de 10 s entre eventos não é um comentário: é o threshold
`'carga_uso_pensamento': ['min>10000']`, e o minuto de leitura é o threshold
`'carga_uso_leitura_blog'`. Se alguém encurtar o think time, o ensaio
**reprova**.

## O guarda de 90 %

```bash
.venv/bin/python assets/test/guarda_recursos.py --k6-pid <PID> --py-pid <PID>
```

Amostra RAM e CPU a cada 1 s lendo `/proc/meminfo` e `/proc/stat`, sem nenhuma
dependência externa. Ao cruzar o limite em **3 amostras consecutivas**, derruba
o k6 e o Playwright por PID (SIGTERM, depois SIGKILL para quem ignorar), imprime
os valores medidos, grava a série temporal em JSON e **sai com código 2**.

### Por que 90 % na RAM

90 % é a margem entre *"o teste ainda mede algo real"* e *"o próprio teste vira
a causa da indisponibilidade que ele deveria detectar"*.

Nesta máquina de 3,7 GiB o consumo já vem quase todo de ferramenta de
desenvolvimento: com o servidor no ar a base é ~2.184 MB de 3.795 MB (58 %),
e o OpenCode sozinho consome ~1,1 GiB. Nessas condições, a 90 % o sistema já
está trocando página, o Chromium headless começa a ser morto pelo OOM killer, e
o k6 passa a reportar timeout — medido: `GET /login` com p95 de **30.000 ms**,
exatamente o `timeout` configurado. A partir dali os números não descreveriam a
intranet, descreveriam a máquina em colapso. Um guarda que deixasse passar
mediria o próprio colapso e culparia o sistema.

### Por que a CPU usa outro limite: 98 %

O enunciado pedia 90 % para RAM **e** CPU. Medindo a máquina, isso inviabilizaria
o teste:

| processo | CPU |
|:---|---:|
| OpenCode desktop | 49 % |
| OpenCode CLI | 44 % |
| Xorg | 19 % |
| **soma da ferramenta, antes do teste** | **~112 %** |

Em 4 núcleos, ~112 % já é carga de base. Um gatilho único de 90 % de CPU
**dispararia em segundos**, derrubando a bateria antes de ela medir qualquer
coisa — e o relatório culparia o sistema por um problema que é da própria
ferramenta de teste.

A decisão (responsável, 26/09/2026) foi **separar os limiares**: **RAM a 90 %**
(é o que protege a máquina do OOM killer) e **CPU a 98 %**, que só dispara em
saturação real do processador. Os dois são configuráveis:

```bash
--por-cento 90 --por-cento-cpu 98
```

**Por que não 70:** a 70 % o guarda dispararia durante a escalada legítima de
120 VUs + 20 navegadores, que é exatamente a carga que o teste existe para
medir — o resultado seria sempre "reprovado" sem informação sobre a intranet.

**Por que não 95:** entre 90 e 95 % o Chromium já perde contexto e o `GET
/login` estoura o timeout, transformando uma saturação de memória numa mentira
sobre a latência do login.

**Três amostras consecutivas**, e não uma: um pico isolado de 1 s é alocação
momentânea, e derrubar uma bateria de 15 minutos por causa disso seria dishonesto
na direção oposta.

### O que o guarda não faz

Não toca no servidor da intranet. O alvo é o equipamento de carga. Derrubar o
servidor invalidaria a medição em curso e exigiria reiniciá-lo — e o teste nunca
faz isso por conta própria.

### Opções

| opção | efeito |
|:---|:---|
| `--por-cento 85` | ajusta o gatilho de **RAM** |
| `--por-cento-cpu 98` | ajusta o gatilho de **CPU** (0 = igual ao de RAM) |
| `--json saida.json` | grava a série temporal (padrão `logs/carga_recursos.json`) |
| `--so-observar` | relata o gatilho mas **não** derruba nada (diagnóstico) |
| `--segundos 900` | vigília com prazo |
| `--temperatura` | mostra a carga do servidor a cada 5 s e sai |
| `--amostras-consecutivas 5` | mais tolerância a picos |

### Atenção: o gatilho de CPU precisa ser separado nesta máquina

Medido na validação integrada (2 VUs do k6 + 2 navegadores, carga mínima): a
**CPU passou de 90 % várias vezes** — 87,9 %, 98,3 %, 99,5 %, 95,7 % — e boa
parte desse consumo era da ferramenta de desenvolvimento da sessão, não do
teste. Com 120 VUs + 20 navegadores, um gatilho único de 90 % mataria a
bateria em minutos por causa de ruído.

O argumento dos 90 % é de **memória** (OOM killer, página trocando). O de CPU é
mais frágil porque a CPU é o recurso compartilhado com o resto da sessão. Por
isso o guarda tem dois limiares, e a recomendação nesta máquina é:

```bash
.venv/bin/python assets/test/guarda_recursos.py \
    --k6-pid <PID_K6> --py-pid <PID_PY> \
    --por-cento 90 --por-cento-cpu 98
```

RAM continua em 90 % (que é o que protege a máquina de verdade) e a CPU só
dispara quando ela está realmente saturada.

## Como rodar

### 0. Pré-requisitos

```bash
# servidor no ar
.venv/bin/python main.py

# os 120 usuários de carga (idempotente)
INTRANET_FORCE_SQLITE=1 .venv/bin/python assets/test/popula_usuarios_carga.py --qtd 120

# >>> OBRIGATÓRIO PARA O USO SER REAL <<<
# Sem isto, blog/notícias/filas/lista redirecionam para / e o roteiro de uso
# mede a tela inicial. Leva ~2,5 min para 120 usuários.
INTRANET_FORCE_SQLITE=1 .venv/bin/python assets/test/libera_modulos_carga.py
INTRANET_FORCE_SQLITE=1 .venv/bin/python assets/test/libera_modulos_carga.py --listar
```

!!! danger "Por que o `libera_modulos_carga.py` é obrigatório"
    `criar_usuario` libera por padrão **três** vínculos: `editar_pdf`, `empenhos`
    e `solicita_impressao`. O gate de `pagina_restrita` exige vínculo em **todo**
    módulo. Sem o script, `userNNN` é redirecionado para `/` em `/blog`,
    `/agregador-noticias`, `/filas`,
    `/lista-telefonica`, `/auditoria`, `/tecnico` e `/users` — **medido com
    navegador real**. Reverter: `--restaurar`.

### 1. A bateria completa (3 terminais)

```bash
# terminal 1 — o vigia (primeiro, para não haver pico sem quem olhe).
# --por-cento-cpu 98 porque a CPU é compartilhada com a ferramenta da sessão.
.venv/bin/python assets/test/guarda_recursos.py \
    --k6-pid <PID_K6> --py-pid <PID_PY> --por-cento 90 --por-cento-cpu 98 &

# terminal 2 — 120 usuários de protocolo, 15 minutos
k6 run assets/k6/carga_uso.js

# terminal 3 — 20 navegadores reais, ao mesmo tempo
.venv/bin/python assets/test/carga_uso_navegador.py --usuarios 20
```

Passar os PIDs à mão é chato; a forma prática é subir cada processo com `&` e
passar `$!`, ou usar `--pids` com a lista. Para conferir sem derrubar nada,
comece com `--so-observar`.

### 2. Validação rápida (minutos, não 15)

```bash
# k6: 2 VUs, roteiro inteiro em ~5 s (think time 50× menor)
K6_PENSA_ESCALA=0.02 k6 run --stage "35s:2" --stage "8s:0" assets/k6/carga_uso.js

# Playwright: 1 usuário, leitura de blog de 8 s
.venv/bin/python assets/test/carga_uso_navegador.py --usuarios 1 --minutos 3 --blog-s 8 --enviar 1
```

`K6_PENSA_ESCALA` encolhe os tempos de pensar (e os thresholds junto, senão o
ensaio de fumaça reprovaria por "pensou rápido demais", que é o que ele fez de
propósito). **Nunca use a escala no ensaio de 15 minutos.**

### 3. Relatórios

| arquivo | quem escreve |
|:---|:---|
| `logs/carga_uso_navegador.json` | o script Playwright (um objeto por usuário, com cada passo) |
| `logs/carga_recursos.json` | o guarda (série temporal de RAM/CPU, 1 amostra/s) |
| `logs/carga_recursos.log` | o guarda (log incremental) |

## As armadilhas desta sessão

Estas não são opinião; foram medidas nesta máquina, e cada uma custou um
ensaio para ser descoberta.

### 1. `sleep()` no k6 **bloqueia** a entrega do WebSocket

Medido: com `sleep(5)` antes de ler o estado, chegam **zero** mensagens; sem
`sleep`, o mesmo código recebe 6. Não é a API — as duas se comportam igual
(`k6/experimental/websockets` e `k6/websockets`). Por isso o ciclo de uso é
dirigido por **`setTimeout`**, nunca por `sleep`.

### 2. Deixar o VU reentrar em laço é um **spin de 299 % de CPU**

Medido com 120 VUs: 62 000 iterações/s só incrementando um contador, consumindo
**299 % de CPU** (3 dos 4 threads). Numa máquina de 4 threads isso *come* o
servidor sob teste e a medição vira lixo. Com `sleep(1)`, o mesmo cenário cai
para **12 %**.

A saída, que é a que o script usa: a função do VU instala o WebSocket e
**devolve**; enquanto o socket está aberto, o k6 mantém a iteração viva, o
event-loop fica livre e a cadeia de `setTimeout` conduz o ciclo. Medido no
ciclo completo: **3 % de CPU**, 15 304 ms de ciclo sem deriva. O socket aberto é
o pino que impede o spin — por isso ele só fecha no fim do ciclo.

### 3. A API nova `k6/websockets` funciona — com `addEventListener`

`login_carga.js` usa `k6/experimental/websockets`, que está **depreciada** e some
numa versão futura. O que se acreditava é que a API nova não invocaria o
handler. **Medido: ela invoca**, com `addEventListener('message', fn)` — o que
não dispara é a atribuição `ws.onmessage = fn`. Resultado do ensaio:
`onopen 1, onmessage 6, handshake 1`. `carga_uso.js` já nasce na API nova.

### 4. Uma sessão do protocolo k6 não abre tela de módulo

Detalhado no início: 8761 bytes de stub em toda rota autenticada. O
`render_modulo` do k6 só marca `/tv`.

### 5. O redirecionamento do gate é **client-side**

`pagina_restrita` responde **HTTP 200** e manda `ui.navigate.to('/')` para o
navegador. `curl` não vê nada; o k6 não vê nada. Só um navegador de verdade
observa o gate. É por isso que a medição de gate está no Playwright.

### 6. Meça o custo de login com o **servidor parado**

Disputa de escrita no mesmo SQLite em modo WAL faz `audit_log` ir de 125 ms
para **2.027 ms**, e o número medido passa a descrever a disputa, não o login.
Detalhe em [testes_carga_k6](testes_carga_k6.md).

### 7. Aqueça a auditoria antes de medir

A primeira escrita de auditoria de um processo paga o DDL de criação das
tabelas: **73,9 s** medidos. Sem aquecimento, o primeiro login aparece com
3,7 s e é puro custo de setup.

### 8. O checkbox do rascunho **já vem marcado** — clicar nele desmarca

Achado do roteiro de envio: o módulo cria o rascunho com `sel=True`, e
`enviar()` exige `r["sel"]`. A primeira versão do teste clicava no checkbox
"para marcar" e o **desmarcava**; o módulo respondia *"Marque ao menos um
arquivo para enviar"* e nada era enviado. Agora só se clica quando
`aria-checked != "true"`.

### 9. A notificação do Quasar é efêmera

`tema_modulo.notificar()` respeita `notificacao_timeout`: em ~3 s a
notificação já sumiu. A primeira versão esperava 4,5 s e lia "sem notificação"
para um envio que **tinha dado certo**. Por isso a confirmação do envio é feita
na **lista** ("Minhas Solicitações"), que é o estado, e não na notificação.

### 10. Cuidado com o falso positivo por texto solto

O título da tela é "Solicitação de Impressão". Uma verificação por
"solicitação no corpo" passa mesmo quando **nada** foi enviado. Use
`ui.notify` (`.q-notification`) ou o estado na lista.

### 11. Uma navegação lenta sob carga é **medição**, não falha de script

Com 4 navegadores em paralelo, um `page.goto` estourou 30 s. O script repetia
uma vez e, se ainda assim falhasse, registrava `DEMORA MEDIDA (>45 s)` em vez
de contar como erro — porque a verdade é que a intranet demorou, e isso é
justamente o que o teste existe para ver.

## Saída esperada

```text
=============== CARGA E USO — INTRANET (k6) ===============
ciclos de uso....: N  (logins distintos user001..user120)
reqs.............: N  (falhas 0.0000)
GET /login.......: p95 ... ms  | max ... ms
conexao WS.......: p95 ... ms
ciclo de uso.....: p95 ... s  (em 9 passos, ~171 s de think time)
ciclo completo...: ...
handshake ok.....: ...
render real......: ...  (so /tv: as demais sao stub, o k6 nao clica em Entrar)
desconectou......: ...
--- uso ---
pensamento min...: ... ms  (exigido >= 10000 ms na escala 1)
leitura blog.....: min ... ms  (exigido ~60000 ms = 1 min na escala 1)
--- sonda do event-loop (a decisiva) ---
sonda /favicon...: p95 ... ms  (teto: 1000 ms)
VUs (max)........: 120
=========================================================
```

Os avisos `setTimeout N was stopped because the VU iteration was interrupted` no
fim são **esperados**: são as cadeias em curso durante a rampa de descida.

## Critérios de aprovação

| threshold | exigido |
|:---|:---|
| `carga_uso_handshake_ok` | > 0,95 |
| `carga_uso_ciclo_completo` | > 0,90 |
| `carga_uso_rota_200` | > 0,99 |
| `carga_uso_desconectou` | > 0,95 |
| `carga_uso_pensamento` | `min` > 10 000 ms |
| `http_req_duration{classe:sonda}` | p95 < 1 000 ms |
| `http_req_duration{classe:login}` | p95 < 2 000 ms |
| `http_req_duration{classe:pagina}` | p95 < 3 000 ms |
| `http_req_failed` | < 0,02 |
| `checks` | > 0,95 |

(A leitura de blog saiu da lista de thresholds: por protocolo o k6 não
completa o login, então o blog não renderiza e o tempo seria sempre 0 — um
threshold impossível, que reprovaria sem defeito. A exigência de 1 min é
medida na camada de navegador real.)

Mais, do lado do navegador: `logins_ok = 20/20`, `pdf_anexado ≥ 20`,
`cancelamentos = envios` (a fila de autorização precisa voltar limpa) e
`erros = 0`.

### Resultado medido em 26/09/2026 — a 120 usuários, REPROVADO

O ensaio completo com os 120 usuários **falhou**, e a tabela de thresholds
diz exatamente por quê:

| métrica | exigido | medido a 120 | |
|:---|:---|:---|:---:|
| `http_req_failed` | < 0,02 | **0,1068** | ❌ |
| `carga_uso_ciclo_completo` | > 0,90 | **0,4006** | ❌ |
| `carga_uso_handshake_ok` | > 0,95 | **0,8368** | ❌ |
| `carga_uso_rota_200` | > 0,99 | **0,8822** | ❌ |
| sonda do event-loop p95 | < 1 000 ms | **10 001 ms** | ❌ |
| `GET /login` p95 | < 2 000 ms | **30 000 ms** (timeout) | ❌ |
| latência de página p95 | < 3 000 ms | **20 000 ms** | ❌ |
| `carga_uso_pensamento` min | > 10 000 ms | 12 009 ms | ✅ |

**O que isso NÃO foi:** não foi queda. O servidor terminou a bateria com
**zero `ERROR`, zero `CRITICAL`, zero `Traceback`**, stayed de pé, e respondeu
todos os 3.679 requests que não estouraram timeout. Imediatamente depois, o
`GET /login` ocioso voltou a **135 ms**. RAM ficou em ~63 % — não houve
pressão de memória. Foi **fila e latência**, não indisponibilidade.

### Isolamento da causa

Quatro medições separam as variáveis:

| cenário | resultado | leitura |
|:---|:---|:---|
| 120 sockets abertos, HTTP leve (`login_carga.js`) | p95 **937 ms** | ✅ 120 conexões cabem |
| 40 `GET /login` concorrentes, sem socket | lote inteiro em **4,2 s** | ✅ HTTP não é o gargalo |
| 40 VUs com ciclo de uso completo | p95 de página **17,7 s** | ❌ degradação de 75× |
| 120 VUs com ciclo de uso completo | p95 de página **20 s**, 10,7 % de falha | ❌ colapso |

O HTTP sozinho e o socket sozinho aguentam. O que não aguenta é a **combinação
de muitos sockets abertos com recargas de página repetidas** — cada VU faz 9
navegações por ciclo, e é aí que o event-loop satura. A sonda do event-loop
(subindo para 10 s) é exatamente esse sintoma: o loop para de atender
requisição leve enquanto os clientes estão conectados.

Isto contrasta com `testes_carga_k6.md`, onde 120 conexões passam com p95 de
955 ms: **a diferença é o trabalho por usuário**, não o número de usuários.

### O gate de aprovação (40 VUs) — funcionalmente APROVADO, latência acima do teto

O enunciado aprova com **20 usuários por 3 min**. Rodando o ensaio completo com
`-e K6_MAX_VU=40` (mesma cronometragem, com a sonda do event-loop ativa):

| threshold | exigido | medido a 40 | |
|:---|:---|:---|:---:|
| `http_req_failed` | < 0,02 | **0,0035** | ✅ |
| `carga_uso_ciclo_completo` | > 0,90 | **1,0000** | ✅ |
| `carga_uso_handshake_ok` | > 0,95 | **0,9861** | ✅ |
| `carga_uso_rota_200` | > 0,99 | **1,0000** | ✅ |
| `carga_uso_desconectou` | > 0,95 | **0,9861** | ✅ |
| `carga_uso_pensamento` min | > 10 000 ms | **12 008 ms** | ✅ |
| `checks` | > 0,95 | **0,9888** | ✅ |
| sonda do event-loop p95 | < 1 000 ms | **1 676 ms** | ❌ |
| `GET /login` p95 | < 2 000 ms | **11 008 ms** | ❌ |
| latência de página p95 | < 3 000 ms | **6 950 ms** | ❌ |

**Leitura:** a 40 usuários o sistema está **funcionalmente íntegro** — 144
ciclos de uso completos, 1.995 requisições com 0,35 % de falha, todo mundo
conecta, navega e desconecta, e o think time mínimo é respeitado. **A
aprovação funcional do enunciado é cumprida.**

O que **não** passa é a **latência**: a sonda do event-loop fica em 1,68 s
contra o teto de 1 s. A degradação é gradual entre 40 e 120, não um degrau:
a 40 o sistema funciona com folga de correção; a 120 colapsa.

### A pista mais útil: CPU baixa com latência alta

Durante o ensaio de 40 VUs, o guarda mediu **CPU entre 4 % e 15 %** — a maior
parte do tempo o servidor estava **ocioso**, e mesmo assim a página levava
6,9 s. Servidor ocioso com latência alta é a assinatura de **espera por lock**,
não de falta de CPU: o processo está bloqueado, não calculando.

A hipótese mais provável é **contenção de escrita no SQLite**. O `banco_conexao`
usa `busy_timeout=5000` (5 s) e `synchronous=NORMAL`; em modo WAL as escritas
são serializadas. Cada navegação de página cria um `Client` no servidor e cada
handshake grava sessão, e `tb_sessoes` já tinha 760 linhas ao fim do ensaio.
Um writer que espera o `busy_timeout` consomeCPU zero e devolve latência de
segundos — exatamente o observado.

**Isso não foi confirmado.** O caminho para confirmar é medir o tempo de
espera por lock (`/proc/<pid>/wchan` ou `PRAGMA locking_mode`) durante a
bateria, ou repetir o ensaio com `banco_tipo=postgres`, que não serializa
escritas. Fica registrado como **hipótese a confirmar**, não como diagnóstico.

## Limpeza

```bash
# devolve os usuários ao acesso padrão (só os 4 módulos de leitura)
INTRANET_FORCE_SQLITE=1 .venv/bin/python assets/test/libera_modulos_carga.py --restaurar

# remove os 120 usuários de carga
INTRANET_FORCE_SQLITE=1 .venv/bin/python assets/test/popula_usuarios_carga.py --limpar
```

Os rascunhos da Solicitação de Impressão expiram sozinhos
(`tempo_expira_rascunho_min`); os PDFs de teste reaproveitados são os mesmos
de `assets/test/pdf/`, que não são apagados.

## Arquivos

| arquivo | papel |
|:---|:---|
| `assets/k6/carga_uso.js` | o ensaio de 120 usuários (protocolo) |
| `assets/test/carga_uso_navegador.py` | os 20 navegadores reais |
| `assets/test/guarda_recursos.py` | o vigia de 90 % |
| `assets/test/libera_modulos_carga.py` | libera blog/notícias/filas/lista para os usuários de carga |
| `assets/k6/login_carga.js` | o outro teste (sockets abertos, sem uso) — **não editar** |
| `assets/test/popula_usuarios_carga.py` | cria os 120 usuários |
| `assets/test/mede_custo_login.py` | mede o bcrypt, com o servidor **parado** |
