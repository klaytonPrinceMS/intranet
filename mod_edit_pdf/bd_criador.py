"""Legacy database creator — mod_edit_pdf (kept only for compatibility).

Criador de BD LEGADO do módulo Editor de PDF, mantido apenas por
compatibilidade histórica. O criador VIGENTE do esquema é `init_db_pdf()` em
`mod_edit_pdf/db_manipulador.py` (banco próprio `db_mod_edit_pdf.db`). Este
arquivo conecta no banco CENTRAL e cria um esquema DIVERGENTE (colunas
`caminho_arquivo`/`hash_sha256` que não existem no esquema real) — não usar
como fonte de verdade.

ISOLADO/MORTO (devSecOps): `init_db()` NUNCA deve ser executado — levanta
RuntimeError fail-loud para impedir divergência de schema. Nenhum módulo
importa este arquivo.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

_LEGADO_MORTO = True  # marcador de isolamento — não remover


def init_db(*args, **kwargs):
    """BLOQUEADO — legado divergente isolado (não executar).

    Levanta RuntimeError fail-loud para impedir criação do schema divergente
    no banco central. O schema vigente vive em `bd_manipulador.init_db_pdf()`."""
    try:
        print("[edit_pdf][bd_criador] BLOQUEADO: legado divergente, use init_db_pdf()")
    except Exception:
        pass
    raise RuntimeError("mod_edit_pdf.bd_criador.init_db() isolado/morto — usar bd_manipulador.init_db_pdf()")