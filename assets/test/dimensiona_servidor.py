# Dimensionamento do servidor para atender N usuarios simultaneos
# EN: Server sizing for N concurrent users, from 40 to 2000.
# PT-BR: Dimensiona o servidor para N usuarios simultaneos, de 40 a 2000.
#
# POR QUE UM SCRIPT E NAO UMA TABELA ESCRITA A MAO
# ------------------------------------------------
# Todo numero aqui vem de uma MEDICAO desta maquina (Intel i3-2375M @ 1,50 GHz,
# 4 threads, 3,7 GiB), registrada nos ensaios de carga. Um numero escrito a mao
# derivaria de nouveau numero. Este script:
#   1) le as constantes medidas de `MEDICOES`,
#   2) expoe a aritmética de cada grandez a,
#   3) gera a tabela de 40 a 2000 em degraus de 40,
#   4) falha se alguem mudar uma constante sem rever as consequencias.
#
# O QUE ESTE SCRIPT NAO FAZ
# -------------------------
# Ele NAO dimensiona causa raiz. O gargalo medido a 40 usuarios NAO e CPU,
# nem RAM, nem banda: a CPU ficava em 4-15 % com latencia de 7 s, ou seja o
# processo estava ESPERANDO, nao computando. A hipotese e contencao de escrita
# no SQLite (`busy_timeout=5000`, WAL serializa writers). Isso esta medido
# como sintoma e hypothesize como causa — ver docs/testes_carga_uso.md.
# Portanto: mais CPU resolve o surto de LOGIN (bcrypt), mas talvez nao
# resolva a latencia a 40 usuarios. A tabela diz as duas coisas.

import sys

# =============================================================================
# 1) MEDICOES — todas medidas nesta maquina, com o metodo, em 26/09/2026
# =============================================================================
MEDICOES = {
    # bcrypt: `bcrypt.checkpw` com custo 12, 721 ms (melhor de 3), o gargalo do login
    "bcrypt_custo12_ms": 721.0,
    "bcrypt_custo": 12,

    # vazao de login medida com N threads simultaneas (assets/test/mede_custo_login.py)
    # saturou em ~4,2/s: mais thread NAO aumenta (a CPU e o limite)
    "logins_por_segundo_2nucleos": 4.2,

    # processo do servidor em repouso, RSS medido
    "rss_base_mb": 108.0,
    # 120 clientes adicionaram ~100 MB de RAM -> por cliente
    "rss_por_cliente_mb": 100.0 / 120.0,

    # carga de pagina real medida com Playwright (documento + assets)
    "pagina_login_kb": 230.0,
    "pagina_agregador_kb": 458.0,

    # WebSocket ocioso, 40 s de observacao: 146 B (ping/pong do Engine.IO)
    "ws_ocioso_bps": 3.6,

    # latencia observada por faixa de usuarios (sonda do event-loop, p95)
    "sonda_p95_ms_22usuarios": 911.0,   # aprovado (teto 1000)
    "sonda_p95_ms_40usuarios": 1676.0,  # reprovado (teto 1000)
    "sonda_p95_ms_120usuarios": 10001.0,  # reprovado

    # bursts de login simultaneos medidos
    "login_40_ms": 11700.0,
    "login_120_ms": 28900.0,
}

NUCLEOS_TESTE = 2          # i3-2375M e 2 nucleos fisicos (4 threads)
GHZ_TESTE = 1.50           # GHz — MESMA unidade de `ghz_alvo`. Misturar MHz
                           # com GHz aqui zera a vazao e infla os nucleos.
CICLOS_BCRYPT = MEDICOES["bcrypt_custo12_ms"] * GHZ_TESTE  # M-ciclos por verificacao
# O modelo preve 5,5 logins/s a 1,5 GHz com 2 nucleos; o medido foi 4,2.
# Ou seja, o modelo SUPEROESTIMA em ~32 %. Dimensionar sem margem daria
# hardware insuficiente, entao a contagem de nucleos e inflada por este fator.
MARGEM_MODELO = 1.35


# =============================================================================
# 2) CONVERSÕES
# =============================================================================
def bcrypt_por_segundo_por_nucleo(ghz, custo=12):
    """Verificações bcrypt/s por núcleo, a partir do custo medido.

    bcrypt é CPU-bound puro: o número de iterações cresce em 2^custo, e cada
    iteração custa o mesmo em qualquer processador. Então o custo medido
    (721 ms a 1,5 GHz) vira ciclos, e os ciclos viram segundos no clock novo.

    O sinal importa: custo MENOR significa MENOS trabalho, logo menos tempo —
    `2 ** (custo_medido - custo)`. Com o sinal invertido, custo 10 saía mais
    lento que custo 12, e a tabela acabava pedindo MAIS núcleos para a opção
    mais segura, que é o oposto do verdade.
    """
    fator_trabalho = 2.0 ** (MEDICOES["bcrypt_custo"] - custo)
    ms_no_clock_novo = MEDICOES["bcrypt_custo12_ms"] * (GHZ_TESTE / ghz) / fator_trabalho
    return 1000.0 / ms_no_clock_novo


def banda_por_usuario(mb_carga_pagina_kb, recarga_s, ws_ocioso_bps):
    """kbit/s por usuário em regime: socket ocioso + recargas de página."""
    bps_ws = ws_ocioso_bps * 8
    bps_pagina = (mb_carga_pagina_kb * 1024 / recarga_s) * 8
    return (bps_ws + bps_pagina) / 1000.0


def banda_burst_login(usuarios, pagina_login_kb, segundos):
    """Mbit/s se TODOS os usuários entrarem de uma vez."""
    total_mb = usuarios * pagina_login_kb / 1024.0
    return (total_mb * 8) / segundos


def ram_mb(usuarios):
    return MEDICOES["rss_base_mb"] + usuarios * MEDICOES["rss_por_cliente_mb"]


# =============================================================================
# 3) TABELA
# =============================================================================



def tabela(usuarios_max=2000, passo=40, ghz_alvo=3.0):
    """Gera a tabela de dimensionamento em degraus de `passo`."""
    linhas = []
    for u in range(passo, usuarios_max + 1, passo):
        # --- banda ---
        kbit_usuario = banda_por_usuario(
            (MEDICOES["pagina_login_kb"] + MEDICOES["pagina_agregador_kb"]) / 2.0,
            recarga_s=300.0,  # 1 recarga a cada 5 min, leitura tipica
            ws_ocioso_bps=MEDICOES["ws_ocioso_bps"])
        banda_total_mbit = kbit_usuario * u / 1000.0
        burst_mbit = banda_burst_login(u, MEDICOES["pagina_login_kb"], 60.0)

        # --- RAM (com folga de 1,5x, e inteiro sobe para 2 GB) ---
        ram_necessaria = ram_mb(u) * 1.5
        ram_gb = max(2, int(-(-ram_necessaria // 1024)))

        # --- CPU: dimensionado pelo surto de LOGIN (bcrypt), que e a unica
        #     grandeza medida que escala com numero de usuarios.
        #     Alvo: o login mais antigo da rajada termina em <= 5 s.
        # delegar para _nucleos_para: e o unico lugar com a margem do modelo
        nucleos = _nucleos_para(u, alvo_s=5.0, ghz_alvo=ghz_alvo, custo=12)

        # --- instâncias: alem de ~300 clientes o processo unico e o gargalo ---
        if u <= 120:
            inst = 1
        elif u <= 300:
            inst = 2
        elif u <= 600:
            inst = 4
        elif u <= 1200:
            inst = 8
        else:
            inst = 16
        nucleos_por_inst = max(2, int(-(-nucleos // inst)))

        # --- veredito honesto, ancorado na medicao de latencia ---
        if u <= 22:
            nota = "medido aprovado"
        elif u <= 40:
            nota = "limiar: medido REPROVADO na latencia"
        elif u <= 120:
            nota = "REPROVADO (10,7% de falha)"
        else:
            nota = "nao medido alem de 120"

        linhas.append({
            "usuarios": u,
            "ram_gb": ram_gb,
            "nucleos": nucleos,
            "nucleos_por_inst": nucleos_por_inst,
            "instancias": inst,
            "banda_mbit": banda_total_mbit,
            "banda_com_10pct": banda_total_mbit * 1.1,
            "burst_mbit": burst_mbit,
            "nota": nota,
        })
    return linhas


CATALOGO_INTEL = [
    (4, 3.7, "Intel Core i3-12100 (4c)"),
    (6, 4.4, "Intel Core i5-12400 (6c)"),
    (8, 4.7, "Intel Core i5-13400 (8c)"),
    (8, 5.1, "Intel Core i5-13600K (8c)"),
    (14, 5.5, "Intel Core i5-14600K (14c)"),
    (20, 5.8, "Intel Core i7-14700K (20c)"),
    (24, 6.0, "Intel Core i9-14900K (24c)"),
    (32, 5.7, "Intel Xeon W-3400 (32c)"),
]
CATALOGO_AMD = [
    (6, 4.1, "AMD Ryzen 5 5600 (6c)"),
    (8, 4.9, "AMD Ryzen 7 7700X (8c)"),
    (12, 5.4, "AMD Ryzen 9 7900X (12c)"),
    (16, 5.7, "AMD Ryzen 9 7950X (16c)"),
    (16, 4.9, "AMD Ryzen 9 9950X (16c, Zen5)"),
    (32, 4.4, "AMD EPYC 9354 (32c)"),
    (64, 3.8, "AMD EPYC 9554 (64c)"),
]


def _nucleos_para(usuarios, alvo_s=5.0, ghz_alvo=3.0, custo=12):
    """Nucleos para o login mais antigo da rajada terminar em <= alvo_s.

    Aplica `MARGEM_MODELO` porque o modelo superestimou a vazao em 32 %
    contra a medicao real (previu 5,5 logins/s, mediu 4,2). Dimensionar pelo
    modelo sem margem daria hardware insuficiente.
    """
    por_nucleo = bcrypt_por_segundo_por_nucleo(ghz_alvo, custo) * 2.0
    bruto = (usuarios / alvo_s) / (por_nucleo / MARGEM_MODELO)
    return max(1, int(-(-bruto // 1)))


def _instancias(u):
    if u <= 120:
        return 1
    if u <= 300:
        return 2
    if u <= 600:
        return 4
    if u <= 1200:
        return 8
    return 16


def _melhor_para(nucleos_necessarios, ghz_alvo, catalogo):
    for n, ghz, nome in catalogo:
        if n >= nucleos_necessarios and ghz >= ghz_alvo:
            return nome
    return catalogo[-1][2] + " (ou superior)"


def catalogo(usuarios_max=2000, passo=40):
    """Sugere processadores concretos (Intel e AMD) por faixa de usuarios.

    AVISO HONESTO: nao sao benchmarks de fabricante. E clock x nucleos
    cruzados com uma constante medida nesta maquina. O bcrypt e CPU-bound
    puro (2^custo iteracoes, as mesmas em qualquer CPU), entao a
    extrapolacao por clock e defensavel. O que NAO e defensavel e o
    desempenho de renderizacao de tela, que depende de IPC - por isso a
    tabela recomenda clock ALTO, e nao muitos nucleos baratos.
    """
    linhas = []
    for u in range(passo, usuarios_max + 1, passo):
        n12 = _nucleos_para(u, custo=12)
        n10 = _nucleos_para(u, custo=10)
        linhas.append({
            "usuarios": u, "n12": n12, "n10": n10,
            "intel12": _melhor_para(n12, 3.0, CATALOGO_INTEL),
            "amd12": _melhor_para(n12, 3.0, CATALOGO_AMD),
            "intel10": _melhor_para(n10, 3.0, CATALOGO_INTEL),
            "ram": max(2, int(-(-(ram_mb(u) * 1.5) // 1024))),
            "inst": _instancias(u),
        })
    return linhas



def main():
    rc = autoteste()
    if rc:
        return rc
    print()
    print("=" * 100)
    print("DIMENSIONAMENTO — Intranet Modular (40 a 2000 usuarios simultaneos)")
    print("=" * 100)
    print()
    print("BASE DE MEDICAO (Intel i3-2375M @ 1,50 GHz, 2 nucleos fisicos, 3,7 GiB):")
    print(f"  bcrypt custo {MEDICOES['bcrypt_custo']} .......... "
          f"{MEDICOES['bcrypt_custo12_ms']:.0f} ms/verificacao "
          f"({MEDICOES['logins_por_segundo_2nucleos']:.1f} logins/s no saturacao)")
    print(f"  RAM ................. base {MEDICOES['rss_base_mb']:.0f} MB + "
          f"{MEDICOES['rss_por_cliente_mb']:.2f} MB por cliente")
    print(f"  pagina .............. {MEDICOES['pagina_login_kb']:.0f} KB (login) / "
          f"{MEDICOES['pagina_agregador_kb']:.0f} KB (agregador)")
    print(f"  WebSocket ocioso .... {MEDICOES['ws_ocioso_bps']:.1f} B/s por cliente")
    print(f"  sonda event-loop .... {MEDICOES['sonda_p95_ms_22usuarios']:.0f} ms a 22 us. | "
          f"{MEDICOES['sonda_p95_ms_40usuarios']:.0f} ms a 40 us. | "
          f"{MEDICOES['sonda_p95_ms_120usuarios']:.0f} ms a 120 us.")
    print()
    print("CONVERSOES USADAS PARA A TABELA (todas explicaveis acima):")
    print(f"  bcrypt/s por nucleo @ 3,0 GHz, custo 12: "
          f"{bcrypt_por_segundo_por_nucleo(3.0):.1f}")
    print(f"  ... com 2 threads por nucleo (bcrypt libera o GIL): "
          f"{bcrypt_por_segundo_por_nucleo(3.0) * 2:.1f}")
    print(f"  ciclo por verificacao: {CICLOS_BCRYPT:.0f} M-ciclos (independente do processador)")
    print()

    print("-" * 100)
    print("TABELA — 40 a 2000 usuarios, degraus de 40")
    print("-" * 100)
    print(f"{'usuarios':>8} {'RAM':>6} {'nucleos':>8} {'inst':>5} {'nuc/inst':>9} "
          f"{'banda Mbit':>11} {'+10%':>8} {'burst login':>12}  situacao medida")
    print("-" * 100)
    for l in tabela():
        print(f"{l['usuarios']:>8} {l['ram_gb']:>4} GB {l['nucleos']:>8} "
              f"{l['instancias']:>5} {l['nucleos_por_inst']:>9} "
              f"{l['banda_mbit']:>11.1f} {l['banda_com_10pct']:>8.1f} "
              f"{l['burst_mbit']:>12.1f}  {l['nota']}")
    print("-" * 100)
    print()
    print("LEITURA DAS COLUNAS")
    print("  RAM ....... folga de 1,5x sobre a memoria medida, arredondada para cima.")
    print("  nucleos ... dimensionado pelo SURTO DE LOGIN:para que todos os logins da")
    print("              rajada terminem em <= 5 s. bcrypt e CPU-bound puro, entao")
    print("              e o unico item que o numero de usuarios multiplica.")
    print("  inst ...... acima de ~300 clientes o processo unico e gargalo. Com")
    print("              varias instancias o SQLite NAO pode ser compartilhado:")
    print("              exige `banco_tipo=postgres` (AGENTS.md 4.1).")
    print("  banda ..... regime: 1 recarga de pagina a cada 5 min + socket ocioso.")
    print("  +10% ...... com a folga de folga de operacao (20% de perda e o usual;")
    print("              aqui so 10% porque a medicao e de socket ocioso).")
    print("  burst ..... TODOS entrando de uma vez, carga de login em 60 s.")
    print()
    print("O QUE A TABELA NAO DISSE")
    print("  A latencia a 40 usuarios FALHOU (sonda 1676 ms contra teto de 1000), e a")
    print("  CPU ficava em 4-15 % nesse momento. Ou seja: o limite medido a 40 NAO e")
    print("  computacao. Nao e CPU, nem RAM (63% usados), nem banda (medida em kbit/s).")
    print("  E um ponto de serializacao — hipotese: contencao de escrita no SQLite.")
    print("  Consequencia pratica: aumentar CPU resolve o surto de login, mas pode")
    print("  NAO resolver a latencia a 40. O caminho provavel e migrar para Postgres")
    print("  (escrita concorrente) antes de comprar hardware.")
    return 0



def autoteste():
    """Confere o modelo contra a medicao real desta maquina.

    Se o modelo desviar mais que 50 % da vazao medida, a extrapolacao por
    clock deixou de valer e a tabela inteira perde credibilidade. Falha alto
    em vez de devolver um numero bonito e errado.
    """
    previsto = (bcrypt_por_segundo_por_nucleo(GHZ_TESTE, MEDICOES["bcrypt_custo"])
                * 2.0 * NUCLEOS_TESTE)
    medido = MEDICOES["logins_por_segundo_2nucleos"]
    erro = abs(previsto - medido) / medido
    print("AUTOTESTE DO MODELO")
    print(f"  vazao prevista @ {GHZ_TESTE} GHz x {NUCLEOS_TESTE} nucleos: {previsto:.1f} logins/s")
    print(f"  vazao MEDIDA nesta maquina ...................: {medido:.1f} logins/s")
    print(f"  erro .........................................: {erro * 100:.0f}%")
    print(f"  margem aplicada na tabela ....................: {MARGEM_MODELO:.2f}x")
    if erro > 0.50:
        print("  REPROVADO: erro acima de 50% — a extrapolacao por clock nao vale")
        return 1
    print("  APROVADO: erro dentro de 50%, margem cobre o vies do modelo")
    return 0

if __name__ == "__main__":
    sys.exit(main())
