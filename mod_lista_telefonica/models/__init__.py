"""Models package for mod_lista_telefonica — dataclasses + SQLAlchemy imperativo."""

from dataclasses import dataclass


@dataclass
class Unidade:
    id: int
    nome: str
    tipo: str  # secretaria | setor | subsetor
    parent_id: int | None
    ordem: int
    telefone: str
    ativo: int


@dataclass
class Contato:
    id: int
    unidade_id: int
    nome: str
    telefone: str
    user_nome: str | None
    tipo: str  # vinculado | externo
