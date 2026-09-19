"""Models package for mod_agregador_noticias — dataclasses (imperativo)."""

from dataclasses import dataclass


@dataclass
class Noticia:
    id: int
    titulo: str
    fonte: str
    tema: str
    url: str
    imagem_url: str
    descricao: str
    data_publicacao: str
    data_coleta: str
