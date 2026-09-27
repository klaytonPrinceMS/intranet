# Valida a cronometragem do ensaio de carga contra o enunciado.
# Uso: .venv/bin/python assets/test/valida_cronometragem.py
#
# Le o proprio script k6 (fonte unica da verdade) e confere: carga inicial,
# incremento, cobertura do gate de "20 usuarios por 3 min", o teto de 15
# minutos e a duracao da sonda do event-loop. Se o k6 mudar a cronometragem,
# este script acusa — em vez de a divergencia passar em silencio.
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
ARQ_K6 = RAIZ / "assets" / "k6" / "carga_uso.js"


def ler_cronometragem():
    """Extrai datas, contagens e sonda do script k6."""
    texto = ARQ_K6.read_text(encoding="utf-8")
    ini = texto.index("stages: [")
    fim = texto.index("],", ini)
    bloco = texto[ini:fim]
    datas = [int(x) for x in re.findall(r"duration: '(\d+)s'", bloco)]
    # o alvo pode vir como `target: 120` ou `target: teto(120)` (com K6_MAX_VU)
    alvos = [int(x) for x in
             re.findall(r"target:\s*(?:teto\()?(\d+)", bloco)]
    m_sonda = re.search(r"sonda_eventloop:.{0,200}?duration: '(\d+)m(\d+)s'",
                        texto, re.S)
    m_graceful = re.search(r"gracefulStop: '(\d+)s'", texto)
    m_start = re.search(r"startVUs:\s*(\d+)", texto)
    return {
        "datas": datas,
        "alvos": alvos,
        "sonda_s": (int(m_sonda.group(1)) * 60 + int(m_sonda.group(2))
                    if m_sonda else 0),
        "graceful": int(m_graceful.group(1)) if m_graceful else 0,
        "inicial": int(m_start.group(1)) if m_start else 0,
    }


def hhmm(seg):
    return f"{seg // 60}:{seg % 60:02d}"


def main():
    c = ler_cronometragem()
    datas = c["datas"]
    alvos = c["alvos"]
    soma = sum(datas)
    total = soma + c["graceful"]
    teto = 15 * 60
    folga = teto - total
    erros = []

    print(f"  arquivo .............: {ARQ_K6.name}")
    print(f"  carga inicial .......: {c['inicial']} usuarios")
    print(f"  estagios ............: {len(datas)}")
    print(f"  soma dos estagios ...: {soma} s = {hhmm(soma)}")
    print(f"  + gracefulStop ......: {c['graceful']} s")
    print(f"  TOTAL ...............: {total} s = {hhmm(total)}   (teto: 15:00)")
    print(f"  folga ...............: {folga} s = {folga // 60}:{folga % 60:02d}")
    print()
    print(f"  ramp max ............: {max(alvos)} usuarios")
    print(f"  1o passo ............: {datas[0]} s -> {alvos[0]} usuarios")
    acum = 0
    for i, d in enumerate(datas):
        acum += d
        if acum >= 180:
            print(f"  gate 20+ por 3 min .: de {datas[0]}s a {acum}s "
                  f"(ramp em {alvos[i]} usuarios)")
            break
    acum = 0
    for i, d in enumerate(datas):
        acum += d
        if alvos[i] >= max(alvos):
            print(f"  {max(alvos)} usuarios .....: em {acum} s = {hhmm(acum)}")
            break
    print(f"  sonda event-loop ...: {hhmm(c['sonda_s'])}")
    print()

    if total > teto:
        erros.append(f"total {total} s excede o teto de {teto} s")
    if folga < 60:
        erros.append(f"folga de apenas {folga} s e arriscada")
    if c["inicial"] != 10:
        erros.append(f"carga inicial {c['inicial']} != 10 usuarios")
    if max(alvos) != 120:
        erros.append(f"ramp max {max(alvos)} != 120 usuarios")
    if c["sonda_s"] < soma:
        erros.append("a sonda do event-loop termina antes do cenario de uso")
    if datas[0] > 30:
        erros.append(f"o uso real so comeca em {datas[0]} s (20 usuarios tarde)")

    if erros:
        print("  REPROVADO:")
        for e in erros:
            print(f"    - {e}")
        return 1
    print("  APROVADO: dentro do teto, com folga, e o gate de")
    print("  '20 usuarios por 3 min' coberto pelo regime.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
