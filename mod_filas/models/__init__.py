"""Models package for mod_filas — partial dataclasses (imperative mapping pending).

EN: Partial dataclasses Fila/Chamada for the Filas module; full
    Table + map_imperatively() mapping still pending (see AGENTS.md §3.1).

Pacote de modelos do mod_filas — dataclasses parciais Fila/Chamada;
mapeamento completo Table + map_imperatively() ainda pendente (ver AGENTS.md §3.1).
"""

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
