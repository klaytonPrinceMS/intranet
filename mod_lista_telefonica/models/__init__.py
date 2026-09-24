"""EN: Models package for mod_lista_telefonica — dataclasses mirroring tb_unidade/tb_contato.
PT-BR: Pacote de modelos do mod_lista_telefonica — dataclasses espelhando tb_unidade/tb_contato.
"""

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
