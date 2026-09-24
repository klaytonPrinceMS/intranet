"""Models package for mod_filas — partial dataclasses (imperative mapping pending).

EN: Partial dataclasses Fila/Chamada for the Filas module; full
    Table + map_imperatively() mapping still pending (see AGENTS.md §3.1).

Pacote de modelos do mod_filas — dataclasses parciais Fila/Chamada;
mapeamento completo Table + map_imperatively() ainda pendente (ver AGENTS.md §3.1).

DÍVIDA TÉCNICA (devSecOps 2026-09-24, escopo mod_filas/):
- Falta Table() + map_imperatively() para tb_fila/tb_chamada/tb_midia/
  tb_tv_estado (padrão imperativo obrigatório §3.1). Hoje o acesso real é via
  mod_intranet/banco_conexao.conexao (bd_manipulador.get_connection), sem
  sqlite3 cru e sem cross-query — por isso o runtime segue íntegro.
- Não ampliar este pacote sem antes criar models/ por tabela com o padrão
  Table + dataclass + map_imperatively() (espelho SQLite↔PostgreSQL).
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
