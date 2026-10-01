"""EN: Open data module — own DB (db_mod_dados_abertos.db, WAL) and the sheet summary.

PT-BR: Módulo de Dados Abertos — banco próprio (db_mod_dados_abertos.db, WAL)
e o resumo da folha de servidores.

O banco do módulo guarda o **REGISTRO** das fontes (`tb_fontes`) e o
histórico de consulta (`tb_consultas`). Ele **não** guarda a folha: a folha é
pública, é de outro módulo (a coleta mora em `mod_gest_cad_usuario/dados/`) e
é lida pela costura `mod_intranet.integracoes.folha_de_servidores_publica()`.
Guardar aqui seria copiar dado de terceiro e envelhecer sem nunca ser corrigido
— o portal é quem atualiza.

Isolamento total: este módulo abre só o banco dele (`banco_conexao.conexao`) e
alcança a folha só pela fachada do núcleo. Nunca `sqlite3` em banco alheio,
nunca import direto de outro módulo de negócio.
"""

import os
import sys
from collections import Counter
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD_DIR = os.path.join(BASE_DIR, "mod_dados_abertos")

# Fonte semeada no primeiro boot. `chave` é o identificador estável da fonte —
# é ela que o card da tela e a URL da tela usam, e é por ela que o registro é
# reconciliado nos boots seguintes (INSERT OR IGNORE nunca renomeia nada).
FONTE_SERVIDORES = {
    "chave": "servidores_publicos",
    "nome": "Servidores Públicos",
    "descricao": "Relação de servidores, vínculo, lotação e remuneração, "
                 "publicada pelo portal de transparência.",
    "icone": "badge",
    "ordem": 10,
}


def _log():
    """EN: Open-data scoped logger.

    PT-BR: Logger escopado do módulo de dados abertos.
    """
    from mod_intranet import observabilidade
    return observabilidade.get_logger("dados_abertos")


def get_connection():
    """EN: Opens the module's own connection (WAL) via banco_conexao.conexao.

    PT-BR: Abre a conexão do banco PRÓPRIO do módulo (WAL) via
    `banco_conexao.conexao` — no Postgres, o DATABASE `db_mod_dados_abertos`.
    """
    from mod_intranet.banco_conexao import conexao
    conn = conexao("dados_abertos")
    if conn is None:
        raise RuntimeError("Falha ao abrir conexão mod_dados_abertos")
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
    except Exception as e:
        try:
            _log().warning(f"get_connection PRAGMA falhou (ignorado): {e}")
        except Exception:
            pass
    return conn


def _conexao_segura():
    """EN: Connection or None (never raises) for read paths.

    PT-BR: Conexão ou None (nunca levanta) para os caminhos de leitura.
    """
    try:
        return get_connection()
    except Exception as e:
        try:
            _log().warning(f"_conexao_segura: falha ao abrir ({e})")
        except Exception:
            pass
        return None


def _audit(ator, acao, alvo, detalhe=""):
    """EN: Forwards an open-data event to the central audit_log (fail-soft).

    PT-BR: Encaminha evento de dados abertos ao `audit_log` central (fail-soft).
    Consultar dado público é leitura, mas **quem** consultou é informação que a
    LGPD exige guardar — por isso o acesso ao card é auditado.
    """
    try:
        from mod_intranet.integracoes import registrar_auditoria
        registrar_auditoria(ator or "sistema", "dados_abertos", acao,
                            f"Fonte: {alvo}" + (f" | {detalhe}" if detalhe else ""))
    except Exception as e:
        try:
            _log().warning(f"_audit falhou ({acao}/{alvo}): {e}")
        except Exception:
            pass


# ================= SCHEMA =================

def init_db():
    """EN: Creates/migrates the module schema and seeds the source registry.

    PT-BR: Cria/migra o schema do módulo e semeia o registro de fontes.

    Idempotente (rodar duas vezes não muda nada): DDL `IF NOT EXISTS`, semeia
    `INSERT OR IGNORE` e migração de coluna por `PRAGMA table_info`
    (portátil SQLite↔PG pelo proxy). Fail-soft no `init_db`: falha aqui não
    pode derrubar o boot — o módulo simply mostra "fonte indisponível".
    """
    try:
        _init_db_seguro()
    except Exception as e:
        try:
            _log().exception(f"init_db: falha no bootstrap | {e}")
        except Exception:
            pass


def _init_db_seguro():
    """EN: Real bootstrap inside a protected wrapper.

    PT-BR: Bootstrap real dentro de um wrapper protegido.
    """
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tb_fontes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chave TEXT NOT NULL UNIQUE,
                nome TEXT NOT NULL,
                descricao TEXT DEFAULT '',
                icone TEXT DEFAULT 'public',
                ordem INTEGER NOT NULL DEFAULT 0,
                ativo INTEGER NOT NULL DEFAULT 1
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tb_consultas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fonte_chave TEXT NOT NULL,
                usuario TEXT,
                data_consulta DATETIME DEFAULT CURRENT_TIMESTAMP,
                detalhes TEXT DEFAULT ''
            )
        """)
        # Índices: a tela lista as fontes ativas por ordem, e a auditoria de
        # consulta filtra por fonte. Criados separadamente porque `CREATE INDEX
        # IF NOT EXISTS` é o mesmo DDL nos dois backends pelo proxy.
        cur.execute("CREATE INDEX IF NOT EXISTS ix_fontes_ativo "
                    "ON tb_fontes (ativo, ordem)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_consultas_fonte "
                    "ON tb_consultas (fonte_chave, data_consulta)")
        _commit(conn)

        cur.execute(
            "INSERT OR IGNORE INTO tb_fontes (chave, nome, descricao, icone, "
            "ordem, ativo) VALUES (?, ?, ?, ?, ?, 1)",
            (FONTE_SERVIDORES["chave"], FONTE_SERVIDORES["nome"],
             FONTE_SERVIDORES["descricao"], FONTE_SERVIDORES["icone"],
             FONTE_SERVIDORES["ordem"]),
        )
        _commit(conn)
    finally:
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass


def _commit(conn):
    """EN: Commits with a retry on `database is locked` (WAL, busy_timeout).

    PT-BR: Grava com repetição em `database is locked` (WAL, busy_timeout).
    """
    import time
    ultimo = None
    for tentativa in range(4):
        try:
            conn.commit()
            return True
        except Exception as e:
            ultimo = e
            if "locked" not in str(e).lower() and "busy" not in str(e).lower():
                break
            time.sleep(0.4 * (tentativa + 1))
    try:
        _log().warning(f"_commit falhou apos 4 tentativas: {ultimo}")
    except Exception:
        pass
    return False


def _rollback(conn):
    """EN: Best-effort rollback (never raises).

    PT-BR: Rollback no melhor esforço (nunca levanta).
    """
    try:
        conn.rollback()
    except Exception:
        pass


# ================= REGISTRO DE FONTES =================

def listar_fontes(somente_ativas=True):
    """EN: Registered data sources as dicts (chave, nome, descricao, icone).

    PT-BR: Fontes de dados cadastradas como dicionários, na ordem de exibição.

    É o que dirige a grade de cards da tela principal: a tela não conhece
    nenhuma fonte por nome, então os próximos conjuntos de dados entram aqui
    sem que ela mude. Lista vazia em falha (fail-soft).
    """
    conn = _conexao_segura()
    if conn is None:
        return []
    try:
        cur = conn.cursor()
        sql = ("SELECT chave, nome, descricao, icone, ordem, ativo "
               "FROM tb_fontes")
        if somente_ativas:
            sql += " WHERE ativo=1"
        sql += " ORDER BY ordem, nome"
        saida = []
        for linha in cur.fetchall():
            saida.append({
                "chave": linha[0], "nome": linha[1], "descricao": linha[2] or "",
                "icone": linha[3] or "public", "ordem": linha[4],
                "ativo": bool(linha[5]),
            })
        return saida
    except Exception as e:
        try:
            _log().warning(f"listar_fontes: falha ({e})")
        except Exception:
            pass
        return []
    finally:
        try:
            conn.close()
        except Exception:
            pass


def registrar_consulta(ator, fonte_chave, detalhe=""):
    """EN: Records that someone opened a dataset (fail-soft).

    PT-BR: Registra que alguém abriu um conjunto de dados (fail-soft).

    Dado aberto é público, mas **quem pediu** é informação que a LGPD exige
    guardar — e é o que permite responder depois "quem viu a folha de
    remuneration e quando".
    """
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO tb_consultas (fonte_chave, usuario, detalhes) "
            "VALUES (?, ?, ?)",
            (fonte_chave or "?", ator or "sistema", (detalhe or "")[:500]))
        _commit(conn)
        _audit(ator, "consulta_dado_aberto", fonte_chave, detalhe)
        return True
    except Exception as e:
        _rollback(conn)
        try:
            _log().warning(f"registrar_consulta: falha ({e})")
        except Exception:
            pass
        return False
    finally:
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass


def registrar_fonte(ator, chave, nome, descricao="", icone="public",
                    ordem=100) -> bool:
    """EN: Registers one source in the register (idempotent by key).

    PT-BR: Registra uma fonte no registro (idempotente pela chave).

    Registrar cria o CARD na tela principal; não cria o leitor. O que o card
    mostra é decisão de quem implementa a leitura da fonte — e enquanto ela não
    existir, a tela diz isso em vez de mostrar zero.

    `INSERT OR IGNORE`: registrar duas vezes a mesma chave não duplica nem
    sobrescreve a descrição que o administrador já ajustou.
    """
    conn = None
    try:
        chave = (chave or "").strip()
        nome = (nome or "").strip()
        if not chave or not nome:
            return False
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT OR IGNORE INTO tb_fontes (chave, nome, descricao, icone, "
            "ordem, ativo) VALUES (?, ?, ?, ?, ?, 1)",
            (chave, nome, (descricao or "").strip(), icone or "public", ordem))
        _commit(conn)
        _audit(ator, "registrar_fonte", chave, nome)
        return True
    except Exception as e:
        _rollback(conn)
        try:
            _log().warning(f"registrar_fonte('{chave}'): falha ({e})")
        except Exception:
            pass
        return False
    finally:
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass


def alternar_fonte_ativa(ator, chave, ativo) -> bool:
    """EN: Switches one source on/off (off hides the card; nothing is deleted).

    PT-BR: Liga ou desliga uma fonte (desligada esconde o card; não apaga).

    Desligar e não apagar é a mesma escolha do organograma: o conjunto de
    dados volta, e apagar o registro perderia a descrição e a ordem que o
    administrador ajustou.
    """
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE tb_fontes SET ativo=? WHERE chave=?",
                    (1 if ativo else 0, (chave or "").strip()))
        _commit(conn)
        _audit(ator, "alternar_fonte", chave,
               f"ativo={1 if ativo else 0}")
        return True
    except Exception as e:
        _rollback(conn)
        try:
            _log().warning(f"alternar_fonte_ativa('{chave}'): falha ({e})")
        except Exception:
            pass
        return False
    finally:
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass


# ================= RESUMO DA FOLHA =================

def _numero(valor):
    """EN: 'R$ 3.419,86' -> 3419.86 (0 when unreadable).

    PT-BR: 'R$ 3.419,86' -> 3419.86 (0 quando não dá para ler).
    """
    try:
        txt = str(valor or "").replace("R$", "").replace(" ", "")
        if not txt:
            return 0.0
        return float(txt.replace(".", "").replace(",", "."))
    except (TypeError, ValueError):
        return 0.0


def _contar(campos, rotulo):
    """EN: `[(valor, quantidade), ...]` ordered by count (empty values folded).

    PT-BR: `[(valor, quantidade), ...]` ordenada por contagem (vazio agrupado).
    """
    c = Counter()
    for linha in campos or []:
        c[(linha or "").strip() or "(não informado)"] += 1
    return [(v, q) for v, q in c.most_common()]


def resumo_da_folha():
    """EN: Aggregate summary of the published server sheet.

    PT-BR: Resumo agregado da folha de servidores publicada.

    Lê a folha pela **fachada** (`integracoes.folha_de_servidores_publica()`) e
    devolve só agregados: contagem, situação, vínculo, secretaria, cargo,
    lotação e os números da remuneração (mediana, média, total, mínimo,
    máximo).

    **Devolve agregados, e não a lista de servidores.** Salário de cada
    pessoa, linha a linha, é a lista do que cada servidor ganha. A folha é
    pública, mas o que este painel serve é para ler a FORMA da força de
    trabalho — quantos são, em qual cargo, em qual situação — e não para
    ranquear gente. Quem precisa da folha linha a linha segue o link da
    FONTE, publicado no cabeçalho: o portal de origem, que é onde a lei diz
    que o dado mora.

    `{"disponivel": False, ...}` quando a folha não pôde ser lida — a tela
    desenha o estado "fonte indisponível" em vez de zeros que parecem dado.
    """
    vazio = {"disponivel": False, "motivo": "", "total": 0}
    try:
        from mod_intranet import integracoes
        folha = integracoes.folha_de_servidores_publica() or {}
        servidores = folha.get("servidores") or []
        if not servidores:
            return {**vazio, "motivo": folha.get("erro") or
                    "a fonte não devolveu nenhum servidor"}
    except Exception as e:
        try:
            _log().exception(f"resumo_da_folha: falha ao ler a folha | {e}")
        except Exception:
            pass
        return {**vazio, "motivo": "falha ao ler a fonte"}

    try:
        remuneracoes = [_numero(s.get("remuneracao")) for s in servidores]
        remuneracoes = [r for r in remuneracoes if r > 0]
        remuneracoes.sort()

        def _percentil(lista, fracao):
            """Percentil porrank mais próximo (p25/p75)."""
            if not lista:
                return 0.0
            pos = min(len(lista) - 1, int(fracao * (len(lista) - 1)))
            return lista[pos]

        def _mediana(lista):
            """Mediana DE VERDADE: com n PAR, a média dos dois centrais.

            A folha tem 650 servidores — par. Pegar só o elemento central
            (o de baixo) não é a mediana, e a diferença aparece na tela: o
            número que a prefeitura publica tem de bater com o que qualquer
           planilha mostra para a mesma lista.
            """
            if not lista:
                return 0.0
            meio = len(lista) // 2
            if len(lista) % 2:
                return lista[meio]
            return (lista[meio - 1] + lista[meio]) / 2

        soma = sum(remuneracoes)
        media = (soma / len(remuneracoes)) if remuneracoes else 0.0

        return {
            "disponivel": True,
            "motivo": "",
            "origem": folha.get("origem") or "",
            "url": folha.get("url") or "",
            "aviso": folha.get("aviso") or "",
            "competencia": folha.get("competencia") or "",
            "coletado_em": folha.get("coletado_em") or "",
            "total": len(servidores),
            "total_com_remuneracao": len(remuneracoes),
            "situacao": _contar([s.get("situacao") for s in servidores], "situacao"),
            "vinculo": _contar([s.get("vinculo") for s in servidores], "vinculo"),
            "unidade": _contar([s.get("unidade") for s in servidores], "unidade"),
            "lotacao": _contar([s.get("lotacao") for s in servidores], "lotacao"),
            "cargo": _contar([s.get("cargo") for s in servidores], "cargo"),
            "remuneracao": {
                "mediana": _mediana(remuneracoes),
                "p25": _percentil(remuneracoes, 0.25),
                "p75": _percentil(remuneracoes, 0.75),
                "minimo": remuneracoes[0] if remuneracoes else 0.0,
                "maximo": remuneracoes[-1] if remuneracoes else 0.0,
                "media": media,
                "total": soma,
            },
            "consultado_em": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
    except Exception as e:
        try:
            _log().exception(f"resumo_da_folha: falha ao agregar | {e}")
        except Exception:
            pass
        return {**vazio, "motivo": "falha ao agregar os dados da fonte"}