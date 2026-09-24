"""EN: Models package for mod_agregador_noticias — Noticia dataclass (imperative pattern pending).

PT-BR: Pacote de modelos do mod_agregador_noticias — dataclass Noticia (padrão imperativo pendente).
Acesso real via bd_manipulador + banco_conexao.conexao; models não é importado em runtime.
"""

from dataclasses import dataclass


@dataclass
class Noticia:
    """EN: News item mirror of tb_noticia. PT-BR: Notícia espelho da tb_noticia."""

    id: int = 0
    titulo: str = ""
    fonte: str = ""
    tema: str = "Geral"
    url: str = ""
    imagem_url: str = ""
    fonte_icon_url: str = ""
    descricao: str = ""
    data_publicacao: str = ""
    data_coleta: str = ""
    
