"""Models package for mod_tecnico — dataclasses + SQLAlchemy imperative.

EN: Provides type-safe dataclasses for technical backups.
PT: Fornece dataclasses tipadas para backups técnicos (mapeamento imperativo
via Table + dataclass + map_imperatively quando expandido).
"""
from dataclasses import dataclass


@dataclass
class Backup:
    """Backup folder entry."""
    id: int
    pasta_nome: str
    owner: str
    ip: str
    hostname: str
    tamanho_total: int
    status: str
    data_criacao: str


@dataclass
class BackupArquivo:
    """File inside a backup."""
    id: int
    backup_id: int
    nome: str
    caminho_relativo: str
    tamanho: int
    hash_sha256: str
