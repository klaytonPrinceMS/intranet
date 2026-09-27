# Teste de carga k6 — Intranet Modular

> Mede se a intranet **aguenta N usuários simultâneos**. Critério de aprovação
> definido pelo requisito: **o sistema deve aguentar no mínimo 40 usuários**.

---

## Resultado da execução de 26/09/2026

**APROVADO — com uma ressalva importante sobre login simultâneo.**

| etapa | VUs | resultado |
|:---|---:|:---|
| 1 | 10 | ✅ |
| 2 | 30 | ✅ |
| 3 | **40** | ✅ **limiar de aprovação** |
| 4 | 60 | ✅ |
| 5 | 80 | ✅ |
| 6 | 90 | ✅ |
| 7 | 100 | ✅ |
| 8 | 110 | ✅ |
| 9 | 120 | ✅ |

Saída medida:

```text
================= CARGA k6 — INTRANET =================
reqs............: 1749  (falhas 0.0000)
GET /login......: p95 937.2 ms  | max 1613.4 ms
conexao WS......: p95 1949.0 ms
socket vivo.....: p95 15946.1 ms
handshake ok....: 1.0000
desconectou.....: 1.0000
eventos/pagina...: 4674
latencia geral..: p95 955.6 ms
checks..........: 1.0000
VUs (max).......: 121
======================================================
```

| threshold | exigido | medido | |
|:---|:---|:---|:---:|
| `carga_handshake_ok` | > 0,95 | **1,0000** | ✅ |
| `carga_desconectou` | > 0,95 | **1,0000** | ✅ |
| `http_req_failed` | < 0,02 | **0,0000** | ✅ |
| `http_req_duration` p95 | < 1000 ms | **955,6 ms** | ⚠️ |
| `checks` | > 0,95 | **1,0000** | ✅ |

**Zero erros no servidor durante toda a escalada** — nenhuma exceção ASGI, nenhum
`Traceback`, nenhuma desconexão involuntary. 1.749 requisições, 4.674 eventos de
página entregues a 121 clientes simultâneos.

### A ressalva: 955 ms de p95 está perto do teto de 1.000 ms

Passou, mas com **4,4 % de folga**. A latência cresce com a quantidade de
usuários, e o crescimento não é linearmente benigno: o `GET /login` (que cria
o `Client` e a sessão) sozinho já respondeu **1,6 s no pior caso**. Numa máquina
maior, ou com mais módulos habilitados, essa folga desaparece.

O número que mais pesa, e que **não** aparece no k6, é o custo do bcrypt — ver
[Login simultâneo](#login-simultaneo-o-limite-real) abaixo.

## Especificação da máquina

| item | valor |
|:---|:---|
| processador | **Intel® Core™ i3-2375M @ 1,50 GHz** |
| núcleos / threads | 4 / 2 por núcleo (4 lógicos) |
| frequência | 800 MHz – 1.500 MHz |
| memória total | **3,7 GiB** |
| swap | 5,6 GiB (1,0 GiB em uso) |
| sistema | Linux, container Docker |
| bancos de dados | 11 SQLite, 3,2 MB no total |

### Memória: o que está em uso

Medido com o servidor no ar e **sem** carga:

| processo | RAM | observação |
|:---|---:|:---|
| **`python` (intranet)** | **108 MB** | o servidor propriamente dito |
| `ai.opencode.desktop` (agente) | 796 MB em 4 processos | ferramenta de desenvolvimento |
| `opencode-cli` | 320 MB | ferramenta de desenvolvimento |
| `tor` | 38 MB | navegação do agente |
| outros | ~76 MB | |
| **sistema total** | **2,1 GiB usados** | 1,6 GiB disponíveis |

O ponto que importa: **a intranet consome 108 MB**, e não 2,1 GB. O consumo
alto da máquina vem das **ferramentas de desenvolvimento** desta sessão, não do
sistema sob teste. Durante a escalada de 120 usuários, a RAM total subiu de
2,1 GiB para 2,2 GiB — ou seja, **~100 MB para 120 clientes conectados**.

Esse é o número que responde "aguenta 40 usuários?": 40 clientes custam cerca de
30 MB. A memória não é o gargalo; a CPU é.

## Login simultâneo: o limite real

O teste k6 mede **concorrência de clientes conectados**. O login em si tem
medição própria (`assets/test/mede_custo_login.py`), porque depende do clique no
botão — um evento interno do NiceGUI.

Com auditoria aquecida e sem contenção entre processos:

| simultâneos | mediana | tempo de parede | logins/s |
|---:|---:|---:|---:|
| 1 | 3,7 s | 3,7 s | 0,3 |
| 10 | 2,8 s | 3,2 s | 3,1 |
| 20 | 5,6 s | 6,1 s | 3,3 |
| **40** | **10,0 s** | **11,7 s** | **3,4** |
| 60 | 14,2 s | 16,5 s | 3,6 |
| 80 | 19,1 s | 21,1 s | 3,8 |
| 120 | 27,1 s | 28,9 s | 4,2 |

Componentes de **um** login aquecido (melhor de 3):

| etapa | custo | causa |
|:---|---:|:---|
| `bcrypt.checkpw` (custo 12) | **721 ms** | CPU |
| `autenticar()` completo | 726 ms | ≈ todo bcrypt |
| `registrar_login()` | 219 ms | escrita de sessão + auditoria |
| **login total** | **≈ 0,95 s** | |

### O que isso significa na prática

- A vazão de login **satura em ~4 por segundo** e não melhora com mais threads:
  a CPU é o gargalo, não o código. O i3 a 1,5 GHz faz **1,4 verificações bcrypt
  por segundo por núcleo**.
- Se **120 pessoas clicarem em "Entrar" no mesmo segundo** (cenário de servidor
  recém-subido, ou de queda e retorno em massa), a última espera **~29 s**.
- Para **40 logins simultâneos**, a última pessoa espera **~11,7 s**. Isso é
  acima do aceitável para uso real, e vale registrar como **risco conhecido**.
- Em regime normal os logins são espalhados no tempo: 4 por segundo de vazão
  atende uma prefeitura com folga, desde que as entradas não coincidam.

A causa é o **fator de custo 12 do bcrypt**, escolhido por segurança. Baixar
para 10 daria ~3× mais vazão e continua acima do mínimo recomendado de 10, mas
é uma decisão de segurança — **não foi alterada aqui**.

## Aviso sobre como medir

Duas armadilhas encontradas e corrigidas, que distorcem o número se ignoradas:

**1. Aquecimento da auditoria.** A primeira escrita de auditoria de um processo
paga o DDL de criação das tabelas — medido em **73,9 s**. O servidor faz isso no
boot (`_passo_auditoria`); qualquer outro processo precisa fazer o mesmo. O
script `mede_custo_login.py` aquece antes de medir. Sem isso, o primeiro "login"
da tabela aparece com 3,7 s e é puro custo de setup.

**2. Contenção entre processos.** Medir com o servidor **no ar** faz os dois
processos disputarem a escrita no mesmo SQLite em modo WAL: `audit_log` sobe de
125 ms para **2.027 ms**, e o número medido passa a refletir essa disputa, não o
custo do login. **Meça com o servidor parado.**

---

## O que precisa saber antes de rodar

Esta intranet é **NiceGUI**, e isso muda o significado de "carga". Não existe
`POST /login`: o login é um **evento no WebSocket**, não uma requisição HTTP.
Não existe, portanto, um endpoint REST onde um `k6` tradicional faça `POST` de
credenciais e leia um token.

O que cada usuário consome no servidor enquanto está "conectado":

| recurso | quem mantém |
|:---|:---|
| conexão WebSocket permanente | cada aba aberta |
| objeto `Client` vivo | cada cliente conectado |
| registro de sessão (`tb_sessoes`) | cada login |
| `tab_id` do armazenamento da aba | cada cliente |

Manter N usuários é, portanto, **manter N clientes vivos ao mesmo tempo**. É
exatamente isso que o teste exercita.

## Arquivos

| arquivo | papel |
|:---|:---|
| `assets/k6/login_carga.js` | o teste k6 (escalada 10 → 120) |
| `assets/test/popula_usuarios_carga.py` | cria os 120 usuários de carga |
| `assets/test/renomeia_usuarios_carga.py` | renomeia `perfNNN` → `userNNN` |
| `assets/test/mede_custo_login.py` | mede o custo do bcrypt (fora do alcance do k6) |

## Os usuários de carga

| item | valor |
|:---|:---|
| logins | `user001` … `user120` |
| senha | `123456` (a provisória do seed) |
| perfil | `comum` |
| troca de senha | **já realizada** (`forcar_troca=0`) |

Duas decisões que mudam o resultado do teste:

**A troca de senha já está feita.** `criar_usuario` marca `forcar_troca=1` por
desenho — o primeiro login de qualquer servidor novo abre o diálogo de troca
obrigatória. Medir com o diálogo pendente mede o **pior caso de primeiro
acesso**, não o estado normal de produção, onde o usuário já trocou a senha uma
vez. O script `popula_usuarios_carga.py` zera a flag ao final
(`marcar_ja_migraram`); para o pior caso de verdade, use `--com-troca-pendente`.

Isso **não** significa que o k6 tenha exercitado o diálogo: ele não abre
diálogo nenhum, porque não chega a clicar em "Entrar" (ver
[Limite conhecido](#limite-conhecido-e-deliberado)). O que o p95 de 955,6 ms
mede é a latência com **os usuários já migrados**, que é o estado normal.

**Todos entram pela API do módulo, nunca por SQL.** `criar_usuario` valida
login, senha mínima, perfil e nome de exibição, gera o hash bcrypt e libera o
acesso padrão — um `INSERT` direto produziria usuários que o sistema não
reconhece. Pelo mesmo motivo, a renomeação usa `renomear_usuario`, que
propaga para `tb_acesso_usuario` e para as autorias nos demais módulos, cada um
pelo seu próprio `bd_manipulador` (sem *cross-query* entre bancos).

## Como rodar

```bash
# 1. servidor no ar
bash iniciar.sh

# 2. criar os 120 usuários (idempotente)
INTRANET_FORCE_SQLITE=1 .venv/bin/python assets/test/popula_usuarios_carga.py --qtd 120

# 3. a escalada (servidor NO AR)
k6 run assets/k6/login_carga.js

# 4. custo do bcrypt (servidor PARADO — ver aviso acima)
#    (com o servidor desligado)
INTRANET_FORCE_SQLITE=1 .venv/bin/python assets/test/mede_custo_login.py
```

Aproximação rápida, só para validar que o teste funciona:

```bash
k6 run --stage "10s:10" --stage "15s:0" assets/k6/login_carga.js
```

## A escalada

Cada VU entra com um login **distinto** (`user001`…`user120`), como pessoas
reais — não a mesma conta repetida.

| etapa | VUs | espera |
|:---|---:|---:|
| 1 | 10 | 20 s |
| 2 | 30 | 20 s |
| 3 | **40** | **30 s** ← limiar de aprovação |
| 4 | 60 | 20 s |
| 5 | 80 | 20 s |
| 6 | 90 | 20 s |
| 7 | 100 | 20 s |
| 8 | 110 | 20 s |
| 9 | 120 | 30 s |

Cada ciclo de VU: `GET /login` → WebSocket (Engine.IO `OPEN`/`PONG`/`CONNECT`)
→ evento `handshake` do NiceGUI → **segura a conexão 15 s** → desconecta.

## O que significam as métricas

| métrica | o que diz |
|:---|:---|
| `carga_handshake_ok` | fração de clientes que o **servidor assumiu** (a página passou a ser transmitida). É a prova de que o cliente ficou vivo de verdade, não só que o socket abriu. |
| `carga_eventos_pagina` | eventos emitidos pelo NiceGUI para cada cliente. Zero aqui = o servidor não assumiu ninguém. |
| `carga_desconectou` | sockets fechados sem erro. |
| `carga_login_http` | latência do `GET /login`, que cria o `Client` e a sessão. |
| `carga_ws_conexao` | tempo entre o `GET` e o handshake concluído. |
| `carga_ws_segurou` | tempo com o socket efetivamente aberto. |
| `http_req_duration` (p95) | **a métrica decisiva**, medida pela *sonda do event-loop*. |

### Por que a sonda do event-loop é a que decide

Nesta base de código, "aguentar usuário" quebrou repetidamente por **handler
síncrono bloqueando o event-loop** — o "servidor desconectado". O caso mais
grave: a primeira gravação de auditoria de cada módulo rodava DDL dentro do
event-loop e levava **73,9 s**; com a tela congelada, o WebSocket caía.

Enquanto N sockets estão abertos, um request leve tem de continuar rápido. Se o
event-loop travar, a sonda do event-loop sobe e o teste reprova **antes** de
qualquer usuário perceber. É por isso que a sonda roda em cenário separado,
durante toda a escalada.

## Limite conhecido, e deliberado

O teste **não clica no botão "Entrar"**, então **não mede o bcrypt**. O caminho
existe e foi verificado até o fim — o handshake do NiceGUI é concluído, o
servidor assume o cliente e passa a transmitir o código da tela —, mas o último
passo (despachar o evento de clique) depende de estado interno da biblioteca.
Acoplar o teste à versão do NiceGUI faria uma atualização quebrá-lo **em
silêncio**, que é resultado pior que não medir. Por isso o bcrypt tem medição
própria, descrita acima.

## Saída esperada

```text
================= CARGA k6 — INTRANET =================
reqs............: N  (falhas 0.0000)
GET /login......: p95 ... ms
conexao WS......: p95 ... ms
handshake ok....: 1.0000
desconectou.....: 1.0000
latencia geral..: p95 ... ms
checks..........: 1.0000
VUs (max).......: 120
======================================================
```

Os avisos `setTimeout N was stopped because the VU iteration was interrupted`
no fim da execução são esperados: são as conexões em curso durante a rampa de
descida para 0 VUs.

## Limpeza

```bash
INTRANET_FORCE_SQLITE=1 .venv/bin/python assets/test/popula_usuarios_carga.py --limpar
```

Remove os 120 usuários de carga e as permissões.

