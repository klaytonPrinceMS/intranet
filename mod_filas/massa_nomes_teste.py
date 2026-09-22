"""Test name-mass generator for the single queue name list (mod_filas).

EN: On-demand generator of a fake 70-person name mass for the queue's single
    name list (midia/*.txt). Default split: 10 gestante (#gestante), 10 idoso
    (#idoso), 50 comum/adult (no priority tag); exactly 12 lines carry a
    Manchester color tag (#vermelho/#laranja/#amarelo/#verde/#azul) spread
    across the 3 groups. One name per line plus tags, ready for
    importar_nomes/csv_para_tags. Uses faker pt_BR when available, otherwise a
    seeded deterministic fallback list.

Módulo Filas — gerador de massa de teste da lista única de nomes da fila.
    Gera sob demanda um arquivo em mod_filas/midia/ com 70 pessoas fictícias
    PT-BR: 10 gestantes (#gestante), 10 idosas (#idoso), 50 adultas/comuns
    (sem tag prioritária); exatamente 12 linhas com cor de Manchester
    (#vermelho/#laranja/#amarelo/#verde/#azul) espalhadas entre os 3 grupos.
    Uma pessoa por linha + tags, pronto para importar_nomes/csv_para_tags.
    Usa faker pt_BR quando disponível, senão lista determinística com semente.
    Língua ubíqua: fila, nome, gestante, idoso, comum, manchester.
"""

import argparse
import os
import random
import sys

PASTA_MIDIA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "midia")
ARQUIVO_PADRAO = "massa_nomes_teste_70.txt"
SEMENTE_PADRAO = 42

TOTAL_GESTANTE = 10
TOTAL_IDOSO = 10
TOTAL_COMUM = 50
TOTAL_ESPERADO = 70

DISTRIBUICAO_MANCHESTER = {
    "vermelho": 3,
    "laranja": 3,
    "amarelo": 2,
    "verde": 2,
    "azul": 2,
}
TOTAL_MANCHESTER = 12

CORES_GESTANTE = ["vermelho", "laranja", "amarelo", "azul"]
CORES_IDOSO = ["vermelho", "laranja", "verde", "azul"]
CORES_COMUM = ["vermelho", "laranja", "amarelo", "verde"]

# Fallback determinístico (sem faker): nomes fictícios PT-BR.
_NOMES_FEMININOS = [
    "Ana", "Maria", "Francisca", "Juliana", "Patricia", "Camila", "Beatriz",
    "Larissa", "Fernanda", "Gabriela", "Renata", "Aline", "Bruna", "Daniela",
    "Eduarda", "Fabiana", "Graziela", "Helena", "Ingrid", "Jessica",
]
_NOMES_MASCULINOS = [
    "Joao", "Jose", "Carlos", "Paulo", "Marcos", "Lucas", "Gabriel", "Rafael",
    "Diego", "Thiago", "Bruno", "Felipe", "Rodrigo", "Anderson", "Marcelo",
    "Ricardo", "Fernando", "Gustavo", "Leonardo", "Vinicius",
]
_SOBRENOMES = [
    "Silva", "Santos", "Oliveira", "Souza", "Costa", "Pereira", "Almeida",
    "Carvalho", "Ferreira", "Rodrigues", "Gomes", "Martins", "Araujo",
    "Barbosa", "Cardoso", "Teixeira", "Moreira", "Correia", "Pinto", "Ribeiro",
]


class GeradorMassaNomes:
    """Gerador determinístico da massa de nomes da fila (70 pessoas)."""

    def __init__(self, semente: int = SEMENTE_PADRAO):
        self.semente = int(semente)

    def gerar_nomes_base(self, quantidade: int, so_femininos: bool = False) -> list:
        """Gera N nomes fictícios PT-BR únicos (faker pt_BR ou fallback).

        Garante: mínimo nome + sobrenome (2 palavras) e, com so_femininos=True
        (gestantes), primeiro nome obrigatoriamente feminino.
        """
        def _tem_sobrenome(nome: str) -> bool:
            return len((nome or "").strip().split()) >= 2

        def _completar_sobrenome(nome: str, rnd=None) -> str:
            nome = (nome or "").strip()
            if _tem_sobrenome(nome):
                return nome
            extra = (rnd.choice(_SOBRENOMES) if rnd else "Silva")
            return f"{nome} {extra}".strip()
        try:
            from faker import Faker

            Faker.seed(self.semente)
            fake = Faker("pt_BR")
            fake.seed_instance(self.semente + (1 if so_femininos else 0))
            nomes = []
            vistos = set()
            tentativas = 0
            _rnd_extra = random.Random(self.semente + 999)
            while len(nomes) < quantidade and tentativas < quantidade * 50:
                tentativas += 1
                if so_femininos:
                    # gestante: primeiro nome obrigatoriamente feminino + sobrenome.
                    nome = f"{fake.first_name_female()} {fake.last_name()}"
                else:
                    nome = fake.name()
                nome = _completar_sobrenome(nome.strip(), _rnd_extra)
                # faker pode gerar nome com título/acentos — mantém, só deduplica.
                chave = nome.strip().lower()
                if chave and chave not in vistos:
                    vistos.add(chave)
                    nomes.append(nome.strip())
            return nomes
        except Exception:
            pass
        # Fallback determinístico sem faker.
        rnd = random.Random(self.semente + (1 if so_femininos else 0))
        femininos = list(_NOMES_FEMININOS)
        masculinos = list(_NOMES_MASCULINOS)
        sobrenomes = list(_SOBRENOMES)
        rnd.shuffle(femininos)
        rnd.shuffle(masculinos)
        rnd.shuffle(sobrenomes)
        nomes = []
        vistos = set()
        i = 0
        while len(nomes) < quantidade:
            if so_femininos or (i % 2 == 0 and femininos):
                primeiro = femininos[(i // 2) % len(femininos)]
            else:
                primeiro = masculinos[(i // 2) % len(masculinos)]
            nome = f"{primeiro} {sobrenomes[i % len(sobrenomes)]} {sobrenomes[(i * 7 + 3) % len(sobrenomes)]}"
            chave = nome.lower()
            if chave not in vistos:
                vistos.add(chave)
                nomes.append(nome)
            i += 1
            if i > quantidade * 10:  # segurança: varia com sobrenome extra (mantém nome+sobrenome).
                nome = f"{primeiro} {sobrenomes[i % len(sobrenomes)]} {sobrenomes[(i * 3 + 1) % len(sobrenomes)]}"
                if nome.lower() not in vistos:
                    vistos.add(nome.lower())
                    nomes.append(nome)
        return nomes[:quantidade]

    def montar_linhas(self) -> list:
        """Monta as 70 linhas (nome + tags) com distribuição exata e embaralhada."""
        rnd = random.Random(self.semente)
        nomes_gestante = self.gerar_nomes_base(TOTAL_GESTANTE, so_femininos=True)
        # Semente distinta para cada grupo não repetir nomes entre grupos.
        ger_idoso = GeradorMassaNomes(self.semente + 1000)
        ger_comum = GeradorMassaNomes(self.semente + 2000)
        nomes_idoso = ger_idoso.gerar_nomes_base(TOTAL_IDOSO)
        nomes_comum = ger_comum.gerar_nomes_base(TOTAL_COMUM)
        # Garante unicidade global entre os 3 grupos (língua ubíqua: fila sem duplicada).
        vistos = set()
        unicos_gest, unicos_idoso, unicos_comum = [], [], []
        for nome in nomes_gestante + nomes_idoso + nomes_comum:
            chave = nome.strip().lower()
            if chave in vistos:
                extra = _SOBRENOMES[len(vistos) % len(_SOBRENOMES)]
                nome = f"{nome.strip()} {extra}"
                chave = nome.strip().lower()
            vistos.add(chave)
            if len(unicos_gest) < TOTAL_GESTANTE:
                unicos_gest.append(nome)
            elif len(unicos_idoso) < TOTAL_IDOSO:
                unicos_idoso.append(nome)
            else:
                unicos_comum.append(nome)

        idx_gest = rnd.sample(range(TOTAL_GESTANTE), len(CORES_GESTANTE))
        idx_idoso = rnd.sample(range(TOTAL_IDOSO), len(CORES_IDOSO))
        idx_comum = rnd.sample(range(TOTAL_COMUM), len(CORES_COMUM))
        cor_por_gest = dict(zip(idx_gest, CORES_GESTANTE))
        cor_por_idoso = dict(zip(idx_idoso, CORES_IDOSO))
        cor_por_comum = dict(zip(idx_comum, CORES_COMUM))

        linhas = []
        for i, nome in enumerate(unicos_gest):
            cor = cor_por_gest.get(i, "")
            linha = f"{nome} #gestante" + (f" #{cor}" if cor else "")
            linhas.append(linha)
        for i, nome in enumerate(unicos_idoso):
            cor = cor_por_idoso.get(i, "")
            linha = f"{nome} #idoso" + (f" #{cor}" if cor else "")
            linhas.append(linha)
        for i, nome in enumerate(unicos_comum):
            cor = cor_por_comum.get(i, "")
            linha = f"{nome}" + (f" #{cor}" if cor else "")
            linhas.append(linha)
        # Espalha os 3 grupos + cores ao longo do arquivo (ordem de chegada mista).
        rnd.shuffle(linhas)
        return linhas

    def salvar_massa(self, caminho_saida: str = "") -> str:
        """Salva a massa em mod_filas/midia/ e retorna o caminho final."""
        os.makedirs(PASTA_MIDIA, exist_ok=True)
        if not caminho_saida:
            caminho_saida = os.path.join(PASTA_MIDIA, ARQUIVO_PADRAO)
        linhas = self.montar_linhas()
        with open(caminho_saida, "w", encoding="utf-8") as f:
            f.write("\n".join(linhas) + "\n")
        return caminho_saida


def contar_distribuicao(linhas: list) -> dict:
    """Conta gestante/idoso/comum + cores Manchester nas linhas geradas."""
    baixa = [(l or "").lower() for l in linhas]
    cont = {
        "total": len(linhas),
        "gestante": sum(1 for l in baixa if "#gestante" in l),
        "idoso": sum(1 for l in baixa if "#idoso" in l),
        "vermelho": sum(1 for l in baixa if "#vermelho" in l),
        "laranja": sum(1 for l in baixa if "#laranja" in l),
        "amarelo": sum(1 for l in baixa if "#amarelo" in l),
        "verde": sum(1 for l in baixa if "#verde" in l),
        "azul": sum(1 for l in baixa if "#azul" in l),
    }
    cont["manchester"] = (
        cont["vermelho"] + cont["laranja"] + cont["amarelo"] + cont["verde"] + cont["azul"]
    )
    cont["comum"] = cont["total"] - cont["gestante"] - cont["idoso"]
    return cont


def validar_massa(caminho: str) -> dict:
    """Lê o arquivo gerado e retorna a distribuição real (para o aceite)."""
    with open(caminho, encoding="utf-8") as f:
        linhas = [l.strip() for l in f if l.strip()]
    return contar_distribuicao(linhas)


def gerar_massa_teste(semente: int = SEMENTE_PADRAO, caminho_saida: str = "") -> str:
    """Atalho funcional: gera e salva a massa de 70 nomes; retorna o caminho."""
    return GeradorMassaNomes(semente).salvar_massa(caminho_saida)


def main() -> int:
    parser = argparse.ArgumentParser(description="Gera massa de 70 nomes da fila em mod_filas/midia/")
    parser.add_argument("--semente", type=int, default=SEMENTE_PADRAO, help="Semente determinística (padrão 42)")
    parser.add_argument("--saida", type=str, default="", help="Arquivo de saída (padrão mod_filas/midia/massa_nomes_teste_70.txt)")
    args = parser.parse_args()
    caminho = gerar_massa_teste(semente=args.semente, caminho_saida=args.saida)
    cont = validar_massa(caminho)
    print(f"Massa salva em: {caminho}")
    print(
        "Distribuição: total={total} gestante={gestante} idoso={idoso} comum={comum} "
        "manchester={manchester} (vermelho={vermelho} laranja={laranja} amarelo={amarelo} "
        "verde={verde} azul={azul})".format(**cont)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
