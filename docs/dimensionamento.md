# Dimensionamento do servidor (40 a 2.000 usuários)

> Dimensiona hardware, RAM e banda para N usuários **simultâneos**, com base
> em medições feitas nesta máquina. Gerado por
> `assets/test/dimensiona_servidor.py` — os números não são escrita à mão.

---

## Base de medição

Toda a tabela sai de medições reais, nesta máquina:

| grandeza | medida | como |
|:---|---:|:---|
| processador | Intel Core i3-2375M @ 1,50 GHz, 2 núcleos (4 threads) | `lscpu` |
| memória | 3,7 GiB | `free` |
| **bcrypt custo 12** | **721 ms** por verificação | `bcrypt.checkpw`, melhor de 3 |
| vazão de login | **4,2 /s** (satura) | `assets/test/mede_custo_login.py` |
| RAM do servidor | 108 MB em repouso | RSS do processo |
| RAM por cliente | 0,83 MB | 120 clientes → +100 MB |
| carga de página | 230 KB (login) / 458 KB (agregador) | Playwright, doc + assets |
| WebSocket ocioso | 3,6 B/s por cliente | 40 s de observação |
| sonda do event-loop | 911 ms a 22 us. · 1.676 ms a 40 us. · 10.001 ms a 120 us. | ensaios k6 |

### O modelo, e o quanto ele erra

bcrypt é **CPU-bound puro**: `2^custo` iterações, as mesmas em qualquer
processador. Então o custo medido (721 ms a 1,5 GHz = 1.082 M-ciclos) vira
ciclos, e os ciclos viram segundos no clock novo. Isso é defensável.

O modelo **não** é benchmark de fabricante, e o script se autoconfere. Saída
do autoteste (transcrita com vírgula decimal):

```text
vazao prevista @ 1,5 GHz x 2 nucleos: 5,5 logins/s
vazao MEDIDA nesta maquina ..........: 4,2 logins/s
erro ...............................: 32%
margem aplicada na tabela ..........: 1,35x
```

Os valores conferem com a execução real do script; o block acima está
transcrito em PT-BR, o script imprime ponto decimal. O autoteste falha se o
erro passar de 50 %.

O modelo **superestima em 32 %**. Dimensionar por ele sem margem daria
hardware insuficiente, então a contagem de núcleos é inflada por 1,35×. O
script falha alto se o erro passar de 50 %.

| custo | bcrypt/s por núcleo a 3 GHz |
|---:|---:|
| 10 | 11,1 |
| 11 | 5,6 |
| **12 (atual)** | **2,8** |
| 13 | 1,4 |

## A tabela

Dimensionada para o **pior caso**: todos os usuários entrando **no mesmo
segundo**, com o login mais antigo da rajada terminando em até 5 s. Login é a
única grandeza medida que multiplica pelo número de usuários.

```bash
.venv/bin/python assets/test/dimensiona_servidor.py
```

**Trecho** da tabela (o script sai com os 50 degraus, de 40 a 2.000, em passos
de 40 — por isso 1.520 aparece e 1.500 não):

| usuários | RAM | núcleos | instâncias | banda (Mbit) | +10 % | burst de login | situação medida |
|---:|---:|---:|---:|---:|---:|---:|:---|
| 40 | 2 GB | 2 | 1 | 0,4 | 0,4 | 1,2 | **medido: reprovado na latência (sonda 1.676 ms)** |
| 80 | 2 GB | 4 | 1 | 0,8 | 0,8 | 2,4 | não medido (interpolação) |
| 120 | 2 GB | 6 | 1 | 1,1 | 1,2 | 3,6 | **medido: reprovado (10,7 % falha)** |
| 160 | 2 GB | 8 | 2 | 1,5 | 1,7 | 4,8 | não medido |
| 200 | 2 GB | 10 | 2 | 1,9 | 2,1 | 6,0 | não medido |
| 240 | 2 GB | 12 | 2 | 2,3 | 2,5 | 7,2 | não medido |
| 280 | 2 GB | 14 | 2 | 2,6 | 2,9 | 8,4 | não medido |
| 320 | 2 GB | 16 | 4 | 3,0 | 3,3 | 9,6 | não medido |
| 400 | 2 GB | 20 | 4 | 3,8 | 4,1 | 12,0 | não medido |
| 480 | 2 GB | 24 | 4 | 4,5 | 5,0 | 14,4 | não medido |
| 600 | 2 GB | 30 | 4 | 5,7 | 6,2 | 18,0 | não medido |
| 800 | 2 GB | 39 | 8 | 7,5 | 8,3 | 24,0 | não medido |
| 1.000 | 2 GB | 49 | 8 | 9,4 | 10,4 | 29,9 | não medido |
| 1.200 | 2 GB | 59 | 8 | 11,3 | 12,4 | 35,9 | não medido |
| 1.520 | 3 GB | 74 | 16 | 14,3 | 15,8 | 45,5 | não medido |
| 2.000 | 3 GB | 98 | 16 | 18,8 | 20,7 | 59,9 | não medido |

!!! warning "Só três pontos da coluna de situação são medido de verdade"
    A coluna `situacao medida` do script marca 40, 80 e 120, mas **só 40 e 120
    foram ensaiados**. Os 10,7 % de falha são a medição da carga a **120
    usuários**; a linha de 80 herdou esse rótulo por Ser o único outro degrau
    abaixo de 120, e não porque existisse um ensaio a 80. Aqui a linha de 80
    está corrigida para "não medido" — e o `dimensiona_servidor.py` também
    precisa ser corrigido, senão volta a gerar o rótulo errado na próxima
    execução (é o `nota` em `tabela()`, ramo `elif u <= 120`).

Os valores de RAM, núcleos, instâncias, banda e burst **são todos gerados** —
não há número escrito à mão nesta tabela.

### Como ler as colunas

- **RAM** — folga de 1,5× sobre o medido, arredondada para cima. Não é o
  gargalo: 2.000 usuários gastam ~1,8 GB.
- **núcleos** — pelo surto de login (ver acima).
- **instâncias** — acima de ~300 clientes o processo único é gargalo.
- **banda** — regime: 1 recarga de página a cada 5 min + socket ocioso.
- **burst de login** — todos entrando de uma vez, carga de login em 60 s.

## Processadores recomendados

| usuários | Intel | AMD | RAM | instâncias |
|---:|:---|:---|---:|---:|
| 40 | Core i3-12100 (4c) | Ryzen 5 5600 (6c) | 2 GB | 1 |
| 120 | Core i5-12400 (6c) | Ryzen 5 5600 (6c) | 2 GB | 1 |
| 160 | Core i5-13400 (8c) | Ryzen 7 7700X (8c) | 2 GB | 2 |
| 320 | Core i7-14700K (20c) | Ryzen 9 7950X (16c) | 2 GB | 4 |
| 480 | Core i9-14900K (24c) | **EPYC 9354 (32c)** | 2 GB | 4 |
| 640 | Xeon W-3400 (32c) | EPYC 9354 (32c) | 2 GB | 8 |
| 1.000 | Xeon W-3400 (32c) | EPYC 9554 (64c) | 2 GB | 8 |
| 2.000 | Xeon W-3400 (32c) | EPYC 9554 (64c) | 3 GB | 16 |

A escolha de AMD a 480 usuários não é "o mais rápido": é o **primeiro do
catálogo com ≥ 24 núcleos**, porque `_melhor_para` filtra por contagem de
núcleos antes de clock. Ryzen 9 9950X (16c) tem clock maior e não serve para
24 núcleos.

**Aviso honesto:** estes não são benchmarks de fabricante. São clock ×
núcleos cruzados com a constante medida aqui. A extrapolação por clock é
defensável para o bcrypt; **não** é para a renderização de tela, que depende
de IPC. Por isso a tabela recomenda **clock alto**, não muitos núcleos
baratos.

### A alavanca mais forte não é o processador

Baixar o custo do bcrypt de 12 para 10 dá **4× mais vazão de login**:

| usuários | núcleos (custo 12) | núcleos (custo 10) |
|---:|---:|---:|
| 120 | 6 | 2 |
| 400 | 20 | 5 |
| 1.000 | 49 | 13 |
| 2.000 | 98 | 25 |

Custo 10 continua acima do mínimo recomendado de segurança. **Não foi
alterado** — é decisão de segurança, e a tabela mostra as duas colunas para
a decisão ser informada.

## Banda na rede interna

O consumo de banda é **irrelevante** nesta escala. Medido:

| componente | por usuário |
|:---|---:|
| WebSocket ocioso (ping/pong) | 29 bit/s |
| recarga de página (a cada 5 min, média 344 KB) | ~9,3 kbit/s |
| **total em regime** | **~9,4 kbit/s** |

| usuários | banda em regime | +10 % | burst de login (60 s) |
|---:|---:|---:|---:|
| 40 | 0,4 Mbit/s | 0,4 | 1,2 Mbit/s |
| 120 | 1,1 Mbit/s | 1,2 | 3,6 Mbit/s |
| 400 | 3,8 Mbit/s | 4,1 | 12,0 Mbit/s |
| 1.000 | 9,4 Mbit/s | 10,4 | 29,9 Mbit/s |
| 2.000 | 18,8 Mbit/s | 20,7 | 59,9 Mbit/s |

**Recomendação de rede:**

- **100 Mbit/s** por segmento de rede é o suficiente e sobra — cobre o burst de login
  (que é o pior caso de banda) com folga de 40 % em 2.000 usuários.
- O **switch precisa de backplane** de pelo menos 1 Gbit/s para 2.000 clientes
  somando 20 Mbit/s em regime — mas 60 Mbit/s no burst de login, se todos
  entrarem juntos, é burst de 1 segundo, não carga sustentada.
- O gargalo **não é a rede**. Numa rede de 1 Gbit/s sobrariam **940 Mbit/s** no
  pior caso (1.000 − 59,9 do burst de login) e 979 Mbit/s em regime
  (1.000 − 20,7).

## O que esta tabela NÃO resolve

O teste mediu que a **latência a 40 usuários falha** (sonda 1.676 ms contra
teto de 1.000 ms) e que a **CPU ficava em 4–15 %** nesse momento. Servidor
ocioso com latência alta é **espera por lock**, não falta de computação.

O script de dimensionamento assume que o gargalo é computação. **A medição
contradiz isso.** Se a causa for mesmo contenção de escrita no SQLite
(`busy_timeout=5000`, WAL serializa writers), comprar o processador da tabela
**não resolve a latência a 40 usuários** — resolve o surto de login e nada
mais.

O caminho provável é **migrar para Postgres** (`banco_tipo=postgres`,
escrita concorrente) antes de investir em hardware. Isso também é
**obrigatório** a partir de ~300 usuários, porque várias instâncias não
compartilham um SQLite — o AGENTS.md §4.1 já exige paridade entre os dois
backends.

**Ordem recomendada:**

1. Migrar para Postgres e medir de novo (elimina a contenção de escrita).
2. Reexecutar o ensaio a 40 e 120 e confirmar a sonda do event-loop.
3. Só então dimensionar o hardware — a tabela acima é válida para o surto de
   login, mas o dimensionamento total depende do passo 1.
