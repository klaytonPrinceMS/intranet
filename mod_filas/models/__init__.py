"""Models package for mod_filas — esqueleto."""

from dataclasses import dataclass


@dataclass
class Fila:
    id: int
    nome: str
    senha_atual: str
    status: str
    guiche: str


@dataclass
class Chamada:
    id: int
    fila_id: int
    senha: str
    guiche: str
    chamado_em: str
    chamado_por: str
