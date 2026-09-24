"""EN: Models package for mod_agregador_noticias — Noticia dataclass ONLY (no DB access here).

PT-BR: Pacote de modelos do mod_agregador_noticias — SOMENTE dataclass Noticia
(espelho de leitura da tb_noticia, sem acesso a banco). Acesso real SEMPRE via
bd_manipulador + banco_conexao.conexao; este models NÃO é importado em runtime
e NÃO abre conexão (evita cross-query entre bancos).
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
    
