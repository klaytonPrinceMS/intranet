"""Guarda de 90 % — interrompe o teste de carga se a máquina saturar.

EN: Watchdog process for the load test. Samples RAM and CPU from /proc once a
    second; the moment either crosses the threshold (90 % by default) it kills
    the k6 and Playwright processes by PID, prints what triggered it, writes the
    JSON time series and exits non-zero.

PT-BR: Processo vigia do teste de carga. Amostra RAM e CPU de /proc a cada 1 s;
no instante em que qualquer uma cruzar o limite (90 % por padrão) derruba os
processos do k6 e do Playwright por PID, imprime o que disparou, grava a série
temporal em JSON e sai com código diferente de zero.

POR QUE 90 %
------------
90 % é a margem entre "o teste ainda mede algo real" e "o próprio teste vira a
causa da indisponibilidade que ele deveria detectar". A medição é feita nesta
máquina com 3,7 GiB de RAM, e o consumo já vem quase todo de Ferramenta de
desenvolvimento, não do sistema sob teste: com o servidor no ar a base é
~2.184 MB de 3.795 MB (58 %), e o OpenCode sozinho consome ~1,1 GiB. Nessas
condições, a 90 % o sistema já está trocando página, o Chromium headless começa
a ser morto pelo OOM killer, e o k6 começa a reportar timeout — ou seja, os
números que apareceriam a partir dali não descreveriam a intranet, descreveriam
a máquina em colapso. Um guarda que deixa passar mediria o próprio colapso como
se fosse falha do sistema.

Por que 90 e não 70: a 70 % o teste dispararia durante a escalada legítima de
120 VUs + 20 navegadores, que é a carga que o teste existe para medir, e o
resultado seria sempre "reprovado" sem informação sobre a intranet.
Por que não 95: entre 90 e 95 % o Chromium já perde contexto e o k6 estoura o
`timeout` de 30 s no `GET /login` (medido: 30.000 ms = o timeout exato), o que
transforma uma saturação de memória em uma mentira sobre a latência do login.

O QUE ESTE PROCESSO NÃO FAZ
---------------------------
Não toca no servidor da intranet. O alvo é o equipamento de carga (k6 e
Playwright); derrubar o servidor invalidaria a medição que ainda está em curso
e exigiria reiniciá-lo — o que este teste nunca faz por conta própria.

Leitura de CPU: `/proc/stat` traz os jiffies acumulados de TODAS as CPUs da
máquina, e são cumulativos. Então o guarda compara duas leituras: o que
avançou no intervalo é o que a máquina usou no intervalo. Usar o valor
absoluto como "porcentagem" daria um número sem sentido nenhum.

Uso:
    .venv/bin/python assets/test/guarda_recursos.py --k6-pid 12345 --py-pid 12346
    .venv/bin/python assets/test/guarda_recursos.py --por-cento 85 --json /tmp/serie.json
    .venv/bin/python assets/test/guarda_recursos.py --so-observar     # só relata, não mata
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
LOG_PADRAO = RAIZ / "logs" / "carga_recursos.log"

INTERVALO_S = 1.0
POR_CENTO_PADRAO = 90
# Margem acima do limite para derrubar o processo: um único sample estourado
# pode ser uma alocação momentânea. Exigimos `amostras_consecutivas` acima do
# gatilho para derrubar — um pico de 1 s não derruba a bateria de 15 min.
AMOSTRAS_CONSECUTIVAS_PADRAO = 3


def agora_iso() -> str:
    """Data/hora UTC em ISO-8601, para o log e para o JSON."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ler_meminfo() -> dict:
    """Lê `/proc/meminfo` e devolve os números que interessam, em bytes.

    Usa `MemAvailable` (e não `MemFree`): `MemFree` ignora a página de cache,
    que o kernel devolve sob pressão — medir por `MemFree` acusaria saturação
    numa máquina saudável, que é o pior erro possível num guarda.
    """
    dados = {"total": 0, "disponivel": 0, "usada": 0, "swap_total": 0,
             "swap_livre": 0, "buffer_cache": 0}
    try:
        with open("/proc/meminfo", "r", encoding="utf-8") as fh:
            for linha in fh:
                chave, _, resto = linha.partition(":")
                partes = resto.split()
                if not partes:
                    continue
                valor = int(partes[0]) * 1024          # /proc/meminfo vem em kB
                if chave == "MemTotal":
                    dados["total"] = valor
                elif chave == "MemAvailable":
                    dados["disponivel"] = valor
                elif chave == "Buffers":
                    dados["buffer_cache"] += valor
                elif chave == "Cached":
                    dados["buffer_cache"] += valor
                elif chave == "SwapTotal":
                    dados["swap_total"] = valor
                elif chave == "SwapFree":
                    dados["swap_livre"] = valor
    except Exception:
        return dados
    # `usada` = total - disponível: é o número que o `free` mostra e o que
    # importa. Inclui o cache, porque cache ocupado é memória ocupada.
    dados["usada"] = max(0, dados["total"] - dados["disponivel"])
    return dados


def ler_swap_usada() -> int:
    """Swap em uso, em bytes (`SwapTotal - SwapFree`).

    Existe como função separada porque a série de swap é informativa: o teste
    pode passar de 90 % de RAM e cair no swap sem ter disparado o gatilho, e é
    justamente esse caso que o relatório precisa mostrar.
    """
    try:
        total = livre = 0
        with open("/proc/meminfo", "r", encoding="utf-8") as fh:
            for linha in fh:
                if linha.startswith("SwapTotal:"):
                    total = int(linha.split()[1]) * 1024
                elif linha.startswith("SwapFree:"):
                    livre = int(linha.split()[1]) * 1024
                    break
        return max(0, total - livre)
    except Exception:
        return 0


def ler_cpu() -> dict:
    """Acumula os jiffies de CPU de `/proc/stat` (todas as CPUs da máquina)."""
    try:
        with open("/proc/stat", "r", encoding="utf-8") as fh:
            for linha in fh:
                if not linha.startswith("cpu "):
                    continue
                campos = [int(x) for x in linha.split()[1:] if x.isdigit()]
                # user nice system idle iowait irq softirq steal ...
                ocioso = campos[3] + (campos[4] if len(campos) > 4 else 0)
                total = sum(campos)
                return {"total": total, "ocioso": ocioso, "cpus": len(campos)}
    except Exception:
        pass
    return {"total": 0, "ocioso": 0, "cpus": 0}


def porcento_cpu(anterior: dict, atual: dict) -> float:
    """% de CPU usado no intervalo entre duas leituras de `/proc/stat`.

    Devolve -1.0 quando não dá para calcular (primeira amostra, ou contador que
    não avançou). `total` e `ocioso` são cumulativos, então a diferença entre
    duas leituras é o que aconteceu no intervalo — ler o absoluto e usar como
    "porcentagem" daria um número sem sentido.
    """
    if not anterior or not atual:
        return -1.0
    d_total = atual["total"] - anterior["total"]
    d_ocioso = atual["ocioso"] - anterior["ocioso"]
    if d_total <= 0:
        return -1.0
    return 100.0 * (d_total - d_ocioso) / d_total


def porcento_memoria(mem: dict) -> float:
    """% de RAM em uso, sobre o total."""
    if not mem or not mem.get("total"):
        return -1.0
    return 100.0 * mem["usada"] / mem["total"]


def processo_vivo(pid: int) -> bool:
    """True se o PID existe e não é zombie.

    `os.kill(pid, 0)` levanta em processo morto, mas em filho já coletado
    (zombie) também não — daí checar o estado em `/proc/<pid>/stat`.
    """
    if not pid or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except Exception:
        return False
    try:
        with open(f"/proc/{pid}/stat", "r", encoding="utf-8") as fh:
            estado = fh.read().rsplit(")", 1)[-1].split()[0]
        return estado != "Z"
    except Exception:
        return True


def nome_processo(pid: int) -> str:
    """Nome do processo pelo /proc (para a mensagem do guarda)."""
    try:
        with open(f"/proc/{pid}/comm", "r", encoding="utf-8") as fh:
            return fh.read().strip()
    except Exception:
        return f"pid {pid}"


def derrubar(pid: int, sig=signal.SIGTERM) -> str:
    """Manda sinal para o PID. Devolve o que aconteceu (texto para o log)."""
    if not processo_vivo(pid):
        return f"pid {pid} já não existe (encerrou sozinho)"
    nome = nome_processo(pid)
    try:
        os.kill(pid, sig)
        return f"pid {pid} ({nome}) recebeu {sig.name}"
    except Exception as exc:
        return f"pid {pid} ({nome}) NÃO recebeu sinal: {exc}"


class Guarda:
    """Vigia a máquina e interrompe a carga ao cruzar o limite."""

    def __init__(self, por_cento: int, pids: list, log_path: Path,
                 json_path: str, apenas_observar: bool,
                 amostras_consecutivas: int, por_cento_cpu: int = 0) -> None:
        self.por_cento = por_cento
        # Limiar de CPU separado, e NÃO opcional por acaso: ver o comentário de
        # POR QUE 90 %. O argumento dos 90 % é de MEMÓRIA (OOM killer). O de CPU
        # é mais frágil nesta máquina, porque a ferramenta de desenvolvimento
        # da sessão (OpenCode) consome CPU sozinha — medido: 2 VUs do k6 + 2
        # navegadoresrexaram 99,5 % de CPU, e quase todo esse consumo não era
        # do teste. Com 120 VUs + 20 navegadores, um gatilho único de 90 %
        # mataria a bateria em minutos por causa de ruído que não é carga.
        self.por_cento_cpu = por_cento_cpu if por_cento_cpu > 0 else por_cento
        self.pids = pids
        self.log_path = log_path
        self.json_path = json_path
        self.apenas_observar = apenas_observar
        self.amostras_consecutivas = amostras_consecutivas
        self.serie: list = []
        self.sequencia = 0
        self.max_mem = 0.0
        self.max_cpu = 0.0
        self.disparou: dict = {}

    # --- log ---------------------------------------------------------------
    def registrar(self, mensagem: str, para_arquivo: bool = True) -> None:
        """Escreve no stdout e, opcionalmente, no arquivo (append incremental).

        O log é em append e com `flush`: o guarda pode ser morto a qualquer
        momento (é o próprio objetivo dele) e o diagnóstico precisa ter
        sobrado no disco até a última amostra.
        """
        linha = f"[{agora_iso()}] {mensagem}"
        try:
            print(linha, flush=True)
        except Exception:
            pass
        if para_arquivo:
            try:
                self.log_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.log_path, "a", encoding="utf-8") as fh:
                    fh.write(linha + "\n")
            except Exception:
                pass

    # --- amostras ----------------------------------------------------------
    def amostrar(self) -> dict:
        """Toma uma amostra de RAM/CPU e devolve o dicionário da série."""
        anterior = self.serie[-1]["cpu_raw"] if self.serie else {}
        mem = ler_meminfo()
        mem["swap_usada"] = max(0, mem["swap_total"] - mem["swap_livre"])
        cpu = ler_cpu()
        pct_mem = porcento_memoria(mem)
        pct_cpu = porcento_cpu(anterior, cpu)
        self.sequencia += 1
        amostra = {
            "t": round(time.time(), 2),
            "instante": agora_iso(),
            "mem_pct": round(pct_mem, 2),
            "cpu_pct": round(pct_cpu, 2),
            "mem_total_mb": round(mem["total"] / 1048576, 1),
            "mem_usada_mb": round(mem["usada"] / 1048576, 1),
            "mem_disponivel_mb": round(mem["disponivel"] / 1048576, 1),
            "swap_usada_mb": round(mem["swap_usada"] / 1048576, 1),
            "pids_vivos": [p for p in self.pids if processo_vivo(p)],
            "cpu_raw": cpu,
        }
        self.serie.append(amostra)
        if pct_mem > self.max_mem:
            self.max_mem = pct_mem
        if pct_cpu > self.max_cpu:
            self.max_cpu = pct_cpu
        return amostra

    # --- decisão -----------------------------------------------------------
    def excedeu(self, amostra: dict) -> bool:
        """True se a amostra passou do limite de RAM ou do limite de CPU."""
        return (amostra["mem_pct"] >= self.por_cento
                or amostra["cpu_pct"] >= self.por_cento_cpu)

    def salvar_json(self) -> None:
        """Grava a série temporal completa em JSON (para o relatório)."""
        if not self.json_path:
            return
        try:
            destino = Path(self.json_path)
            destino.parent.mkdir(parents=True, exist_ok=True)
            documento = {
                "meta": {
                    "inicio": self.serie[0]["instante"] if self.serie else "",
                    "fim": agora_iso(),
                    "amostras": len(self.serie),
                    "intervalo_s": INTERVALO_S,
                    "por_cento_mem": self.por_cento,
                    "por_cento_cpu": self.por_cento_cpu,
                    "apenas_observar": self.apenas_observar,
                    "pids": self.pids,
                    "max_mem_pct": round(self.max_mem, 2),
                    "max_cpu_pct": round(self.max_cpu, 2),
                    "disparou": self.disparou or {},
                },
                # sem `cpu_raw`: é dado cumulativo do /proc, ruído no relatório
                "serie": [{k: v for k, v in a.items() if k != "cpu_raw"}
                          for a in self.serie],
            }
            destino.write_text(json.dumps(documento, ensure_ascii=False, indent=2),
                               encoding="utf-8")
            self.registrar(f"série temporal gravada em {destino}")
        except Exception as exc:
            self.registrar(f"[erro] não foi possível gravar o JSON: {exc}")

    def interromper(self, amostra: dict, motivo: str) -> int:
        """Aplica o gatilho: derruba os alvos e sai com código 2."""
        self.disparou = {
            "instante": amostra["instante"],
            "motivo": motivo,
            "mem_pct": amostra["mem_pct"],
            "cpu_pct": amostra["cpu_pct"],
            "por_cento_mem": self.por_cento,
            "por_cento_cpu": self.por_cento_cpu,
            "mem_usada_mb": amostra["mem_usada_mb"],
            "mem_total_mb": amostra["mem_total_mb"],
            "swap_usada_mb": amostra["swap_usada_mb"],
        }
        self.registrar("")
        self.registrar("=" * 68)
        self.registrar(f"!! INTERROMPIDO — {motivo} cruzou o limite "
                       f"(RAM {self.por_cento} % / CPU {self.por_cento_cpu} %)")
        self.registrar(f"   RAM : {amostra['mem_pct']} % "
                       f"({amostra['mem_usada_mb']} / {amostra['mem_total_mb']} MB), "
                       f"disponível {amostra['mem_disponivel_mb']} MB, "
                       f"swap {amostra['swap_usada_mb']} MB")
        self.registrar(f"   CPU : {amostra['cpu_pct']} %")
        self.registrar(f"   séries até aqui: RAM máx {round(self.max_mem, 2)} %, "
                       f"CPU máx {round(self.max_cpu, 2)} %")
        if self.apenas_observar:
            self.registrar("   --so-observar: NÃO derruba nada (era para diagnóstico)")
        else:
            for pid in self.pids:
                self.registrar("   " + derrubar(pid))
            # 2ª passada após 2 s: quem ignorou o SIGTERM (o k6 trata o sinal
            # para fechar os sockets) leva SIGKILL. Sem isso, um k6 preso
            # continuaria martelando o servidor já sobrecarregado.
            time.sleep(2)
            for pid in self.pids:
                if processo_vivo(pid):
                    self.registrar("   " + derrubar(pid, signal.SIGKILL))
        self.registrar("=" * 68)
        self.salvar_json()
        return 2

    # --- laço --------------------------------------------------------------
    def rodar(self, segundos: float = 0.0) -> int:
        """Amostra até o gatilho, até o prazo, ou até os PIDs saírem.

        Devolve 0 se nada disparou, 2 se o gatilho disparou.
        """
        inicio = time.time()
        self.registrar(f"guarda iniciada: RAM {self.por_cento} % / "
                       f"CPU {self.por_cento_cpu} % (RAM+CPU de /proc, 1 amostra/s)")
        self.registrar("  pids sob vigilância: "
                       + ", ".join(f"{p} ({nome_processo(p)})" for p in self.pids))
        self.registrar(f"  arquivo de log    : {self.log_path}")
        consecutivas = 0
        while True:
            amostra = self.amostrar()
            if self.excedeu(amostra):
                consecutivas += 1
                self.registrar(f"  ⚠ amostra {consecutivas}/{self.amostras_consecutivas} "
                               f"acima do limite: RAM {amostra['mem_pct']} % "
                               f"(limite {self.por_cento}) / "
                               f"CPU {amostra['cpu_pct']} % "
                               f"(limite {self.por_cento_cpu})")
            else:
                consecutivas = 0

            if consecutivas >= self.amostras_consecutivas:
                qual = ("RAM" if amostra["mem_pct"] >= self.por_cento else "CPU")
                return self.interromper(amostra, qual)

            # imprime a linha da série a cada 10 s, para o stdout não virar
            # um rio (o arquivo tem tudo, amostra por amostra)
            if self.sequencia % 10 == 1:
                self.registrar(f"  RAM {amostra['mem_pct']:5.1f} % "
                               f"({amostra['mem_usada_mb']:.0f} MB)  |  "
                               f"CPU {amostra['cpu_pct']:5.1f} %  |  "
                               f"pids vivos {len(amostra['pids_vivos'])}")

            # prazo em segundos (0 = sem prazo; o guarda roda até o gatilho)
            if segundos and (time.time() - inicio) >= segundos:
                self.registrar(f"prazo de {segundos}s atingido sem gatilho "
                               f"(RAM máx {round(self.max_mem, 2)} %, "
                               f"CPU máx {round(self.max_cpu, 2)} %)")
                self.salvar_json()
                return 0
            # se todos os PIDs saíram, o ensaio acabou: não há o que vigiar
            if self.pids and not any(processo_vivo(p) for p in self.pids):
                self.registrar("todos os processos vigiados encerraram — guarda saindo")
                self.salvar_json()
                return 0
            time.sleep(INTERVALO_S)


def rodar_ate_o_servidor_responder(espera_s: float = 600.0) -> int:
    """Ajuda de diagnóstico: imprime a carga do servidor a cada 5 s.

    Não é o guarda; é o "termômetro" para olhar enquanto a bateria roda. A
    chamada `curl` é deliberadamente ausente: o guarda lê /proc para não
    depender de rede (e para não virar mais um cliente do servidor sob teste).
    """
    fim = time.time() + espera_s
    while time.time() < fim:
        try:
            saida = subprocess.run(
                ["ps", "-o", "pid,rss,pcpu,cmd", "-p", "34411"],
                capture_output=True, text=True, timeout=5)
            print(saida.stdout.strip(), flush=True)
        except Exception:
            pass
        time.sleep(5)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Guarda de 90 % de RAM/CPU do teste de carga")
    ap.add_argument("--por-cento", type=int, default=POR_CENTO_PADRAO,
                    help=f"gatilho de RAM em %% (padrão {POR_CENTO_PADRAO})")
    ap.add_argument("--por-cento-cpu", type=int, default=0,
                    help="gatilho de CPU em %% (0 = igual a --por-cento). "
                         "Sugestão nesta máquina: 98, porque a CPU aqui é "
                         "compartilhada com a ferramenta de desenvolvimento")
    ap.add_argument("--k6-pid", type=int, default=0,
                    help="PID do processo k6 (derrubado ao disparar)")
    ap.add_argument("--py-pid", type=int, default=0,
                    help="PID do processo Playwright (derrubado ao disparar)")
    ap.add_argument("--pids", default="",
                    help="outros PIDs a vigiar/derrubar, separados por vírgula")
    ap.add_argument("--json", default=str(RAIZ / "logs" / "carga_recursos.json"),
                    help="onde gravar a série temporal ('' desliga)")
    ap.add_argument("--log", default=str(LOG_PADRAO),
                    help="arquivo de log incremental")
    ap.add_argument("--segundos", type=float, default=0.0,
                    help="prazo máximo de vigília (0 = até o gatilho)")
    ap.add_argument("--so-observar", action="store_true",
                    help="relata o gatilho mas NÃO derruba nada (diagnóstico)")
    ap.add_argument("--amostras-consecutivas", type=int,
                    default=AMOSTRAS_CONSECUTIVAS_PADRAO,
                    help=f"amostras acima do gatilho antes de derrubar "
                         f"(padrão {AMOSTRAS_CONSECUTIVAS_PADRAO})")
    ap.add_argument("--temperatura", action="store_true",
                    help="só mostra a carga do servidor a cada 5 s e sai")
    args = ap.parse_args()

    if args.temperatura:
        return rodar_ate_o_servidor_responder(60.0)

    pids = [p for p in (args.k6_pid, args.py_pid) if p > 0]
    if args.pids:
        for bruto in args.pids.split(","):
            try:
                pids.append(int(bruto.strip()))
            except ValueError:
                print(f"  [aviso] PID inválido ignorado: {bruto!r}", flush=True)

    if not pids:
        print("  [erro] informe --k6-pid e/ou --py-pid (ou --pids). Sem alvo "
              "o guarda não tem o que interromper.", flush=True)
        return 1
    if not any(processo_vivo(p) for p in pids):
        print(f"  [erro] nenhum dos PIDs {pids} está vivo. O guarda não pode "
              f"derrubar processo que não existe.", flush=True)
        return 1

    guarda = Guarda(por_cento=args.por_cento, pids=pids, log_path=Path(args.log),
                    json_path=args.json, apenas_observar=args.so_observar,
                    amostras_consecutivas=max(1, args.amostras_consecutivas),
                    por_cento_cpu=args.por_cento_cpu)
    return guarda.rodar(args.segundos)


if __name__ == "__main__":
    sys.exit(main())
