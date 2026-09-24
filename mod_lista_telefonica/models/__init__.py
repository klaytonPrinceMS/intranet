"""EN: Models package for mod_lista_telefonica — dataclasses mirroring tb_unidade/tb_contato.
PT-BR: Pacote de modelos do mod_lista_telefonica — dataclasses espelhando tb_unidade/tb_contato.

DÍVIDA (AGENTS §3.1): hoje só dataclasses (sem Table + map_imperatively()).
Padrão a propagar é o mapeamento imperativo SQLAlchemy em models/__init__.py
(Table + dataclass + map_imperatively(), hoje só mod_intranet). Não migrar
agora sem testes de paridade SQLite↔PostgreSQL; bd_manipulador segue via
banco_conexao.conexao (portável) até a migração.
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
