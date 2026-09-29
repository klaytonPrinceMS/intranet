"""EN: Stock — own database (db_mod_estoque.db, WAL). The ONLY access point to
the module's data: warehouses (one fixed central plus one per secretariat of the
organogram), the item catalogue with a stable sequential number per warehouse,
the available balance per item per warehouse, the numbered movement documents
(entry, transfer, devolution), the deliveries to a room (what is IN USE and what
has been standing still), the collection requests that bring unused items back,
and the deposit tasks that call other registered servers in. Owns its schema in
`init_db` (portable SQL, works on SQLite and PostgreSQL). Cross-module data
(servers, organogram) arrives through `mod_intranet.integracoes` — never by
importing another module.

PT-BR: Estoque — banco próprio (db_mod_estoque.db, WAL). ÚNICO ponto de acesso
aos dados do módulo: almoxarifados (um central fixo e um por secretaria do
organograma), o catálogo de itens com número sequencial estável por almoxarifado,
o saldo disponível por item e por almoxarifado, os documentos de movimentação
numerados (entrada, transferência, devolução), as entregas para a sala (o que
está EM USO e o que está PARADO), os pedidos de recolhimento que devolvem o que
não foi usado, e as tarefas de depósito que chamam outros servidores
cadastrados. Dono do schema em `init_db` (SQL portátil, funciona em SQLite e
PostgreSQL). O que vem de outro módulo (servidores, organograma) entra por
`mod_intranet.integracoes` — nunca importando outro módulo de negócio.

TABLES (prefixo `tb_estoque_`)
    tb_estoque_almoxarifado  almoxarifado (o central é fixo; os outros, por
                             secretaria do organograma)
    tb_estoque_item          item do catálogo, com o número do almoxarifado
    tb_estoque_saldo         quanto do item está DISPONÍVEL em cada almoxarifado
    tb_estoque_documento     documento numerado de saída/entrada/devolução
    tb_estoque_movimento     linha do documento: o que saiu, de onde, para onde
    tb_estoque_entrega       item entregue a uma SALA (o que está EM USO)
    tb_estoque_recolhimento  pedido de recolhimento/devolução do que não foi usado
    tb_estoque_tarefa        tarefa de depósito (receber, conferir, inventariar)
    tb_estoque_convite       servidores chamados para tratar o depósito
    tb_estoque_usuario       vínculo com o servidor já cadastrado e o papel dele
    tb_estoque_sequencia     contador por almoxarifado (item e documento)
"""
import os
import re
import sys
import time
import unicodedata
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

CHAVE_MODULO = "estoque"
NOME_MODULO = "Estoque"

# Vocabulário do almoxarifado (língua ubíqua do domínio).
# O central é ÚNICO e FIXO: nasce com o primeiro `init_db` e não se apaga nem
# se renomeia — é para onde entra tudo e de onde sai para as secretarias.
PAPEL_CONSULTA = "consulta"
PAPEL_OPERADOR = "operador"
PAPEL_ADMINISTRADOR = "administrador"
PAPEIS = (PAPEL_CONSULTA, PAPEL_OPERADOR, PAPEL_ADMINISTRADOR)

# De onde o item entra no estoque central. A nota de empenho é o documento que
# amarra a saída de dinheiro do município ao material que chega.
ORIGENS_ENTRADA = ("nota_empenho", "empenho", "compra", "doacao", "outro")

# O que aconteceu com a quantidade. `saida` tira do almoxarifado (transferência
# enviada ou entrega para a sala); `entrada` põe nele; `devolucao` traz de volta
# o que não foi usado; `baixa` consome o que já estava entregue em uma sala.
TIPOS_MOVIMENTO = ("entrada", "saida", "devolucao", "baixa")

TIPOS_DOCUMENTO = ("entrada", "transferencia", "devolucao", "recolhimento")

# O que uma entrega para a sala pode virar: continua em uso, voltou para o
# almoxarifado (recolhido) ou foi consumido sem voltar (consumido).
SITUACAO_ENTREGA = ("em_uso", "recolhido", "consumido")

# "Quem pode chamar quem" para tratar o depósito: o responsável convida
# servidores já cadastrados para uma tarefa (receber, conferir, inventariar).
TIPOS_TAREFA = ("receber", "conferir", "inventariar")
SITUACAO_TAREFA = ("aberta", "em_andamento", "concluida", "cancelada")
SITUACAO_CONVITE = ("pendente", "aceito", "recusado", "cancelado")

# O pedido de recolhimento: o almoxarifado da secretaria pede para o central
# recolher o que foi entregue e não foi usado; quem está com o item também
# pode abrir o mesmo pedido para devolver por não uso.
TIPOS_RECOLHIMENTO = ("recolhimento", "devolucao")
SITUACAO_RECOLHIMENTO = ("aberto", "atendido", "recusado")

UNIDADES_MEDIDA = ("UN", "CX", "PC", "KT", "L", "KG", "M", "M2", "JG", "PGC")

# Item parado = entregue a uma sala e sem baixa há N dias. O padrão é 30, mas
# quem administra o módulo ajusta (é o número que decide quando perguntar).
DIAS_PARADO_PADRAO = 30

# Transação curta + retry de contenção (SQLite WAL "database is locked").
# busy_timeout=5000 herdado de banco_conexao.conexao; não reconfigurar aqui.
TENTATIVAS_LOCKED = 5
ESPERA_LOCKED_SEG = 0.05

# Quantidade é REAL (meio quilo de tinta é meio quilo), arredondada para evitar
# ruído de ponto flutuante no saldo.
CASAS_DECIMAIS = 3

DIGITOS_MINIMO = 3
DIGITOS_MAXIMO = 8
DIGITOS_PADRAO = 4
PREFIXO_PADRAO_TAMANHO = 6

_CORES_ALMOXARIFADO = {
    "azul": "#1565C0", "verde": "#2E7D32", "roxo": "#6A1B9A",
    "laranja": "#EF6C00", "cinza": "#455A64", "teal": "#00838F",
}


def _log():
    """Logger escopado do módulo de Estoque."""
    from mod_intranet import observabilidade
    return observabilidade.get_logger("estoque")


def _norm(texto):
    """Normaliza para comparação de nomes: sem acento, sem pontuação, minúsculo.

    Evenemente repetido nos módulos por decisão (o banco de cada um é seu) —
    a mesma regra de `mod_os` e `mod_lista_telefonica`. É o que faz
    "Resma A4" e "resma  a4" casarem como o mesmo item."""
    try:
        limpo = unicodedata.normalize("NFKD", str(texto or "")) \
            .encode("ascii", "ignore").decode().lower()
        return " ".join(re.findall(r"[a-z0-9]+", limpo))
    except Exception:
        return str(texto or "").lower()


def _agora():
    """Data/hora local em texto (formato único do módulo)."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _hoje():
    """Data de hoje no formato do módulo (`YYYY-MM-DD`)."""
    return datetime.now().strftime("%Y-%m-%d")


def _dias_ate(quando):
    """Dias corridos entre a data `quando` e hoje. Negativo = ainda vai vir."""
    try:
        alvo = datetime.strptime(str(quando)[:10], "%Y-%m-%d").date()
        return (datetime.now().date() - alvo).days
    except (ValueError, TypeError):
        return 0


def _normalizar_data(valor):
    """Aceita `YYYY-MM-DD` ou `YYYY-MM-DD HH:MM` e devolve `YYYY-MM-DD`."""
    bruto = str(valor or "").strip()
    if not bruto:
        return ""
    try:
        return datetime.strptime(bruto[:10], "%Y-%m-%d").strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return ""


def _arred(valor):
    """Arredonda a quantidade para o casas de casa do módulo."""
    try:
        return round(float(valor or 0), CASAS_DECIMAIS)
    except (TypeError, ValueError):
        return 0.0


def _para_numero(valor):
    """Converte o que o servidor digitou em número; 0 quando não é número."""
    try:
        texto = str(valor or "").strip().replace(",", ".")
        if not texto:
            return 0.0
        return _arred(float(texto))
    except (TypeError, ValueError):
        return 0.0


def _como_id(valor):
    """Converte um id vindo da tela em inteiro, ou None quando não é id.

    A tela às vezes entrega o id como texto (`ui.select` devolve string) e
    às vezes o nome vem no lugar do id. Virar `None` é o comportamento
    honesto: a função que recebeu decide o que fazer com um id ausente, em vez
    de estourar `int()` no meio de uma transação."""
    try:
        if valor is None or str(valor).strip() == "":
            return None
        return int(valor)
    except (TypeError, ValueError):
        return None


# ============ conexão e transações ============

def _eh_bloqueio_banco(exc):
    """Verdadeiro quando o erro é contenção transitória (passível de retry)."""
    try:
        texto = str(exc or "").lower()
        return ("database is locked" in texto or "database table is locked" in texto
                or "locked" in texto or "busy" in texto or "deadlock" in texto
                or "could not obtain lock" in texto)
    except Exception:
        return False


def _rollback_seguro(conn, contexto=""):
    """Rollback best-effort que nunca derruba o chamador (AGENTS §3.2)."""
    try:
        if conn is not None:
            conn.rollback()
    except Exception as exc:
        try:
            _log().warning(f"_rollback_seguro[{contexto}]: {exc}")
        except Exception:
            pass


def _commit_com_retry(conn, contexto="", tentativas=None, espera_s=None):
    """Commit com retry curto em contenção ("database is locked")."""
    try:
        tentativas = tentativas or TENTATIVAS_LOCKED
        espera_s = espera_s if espera_s is not None else ESPERA_LOCKED_SEG
        for tentativa in range(1, tentativas + 1):
            try:
                conn.commit()
                return True
            except Exception as exc:
                if _eh_bloqueio_banco(exc) and tentativa < tentativas:
                    try:
                        _log().warning(f"_commit_com_retry[{contexto}] locked "
                                       f"tentativa {tentativa}/{tentativas}: {exc}")
                    except Exception:
                        pass
                    try:
                        time.sleep(espera_s * tentativa)
                    except Exception:
                        pass
                    continue
                raise
        return True
    except Exception:
        raise


def get_connection():
    """Abre a conexão do módulo (WAL) via banco_conexao.conexao('estoque')."""
    try:
        from mod_intranet.banco_conexao import conexao
        conn = conexao(CHAVE_MODULO)
        if conn is None:
            raise RuntimeError("Falha ao abrir conexão mod_estoque")
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
        except Exception as exc:
            try:
                _log().warning(f"get_connection: PRAGMA ignorado ({exc})")
            except Exception:
                pass
        return conn
    except Exception:
        try:
            _log().exception("get_connection falhou")
        except Exception:
            pass
        raise


def _integracoes():
    """Fachada do núcleo (import lazy: o módulo de negócio nunca abre outro banco)."""
    from mod_intranet import integracoes
    return integracoes


def _auditar(ator, acao, alvo, detalhe=""):
    """Grava na auditoria central (fail-soft). O orquestrador é o núcleo."""
    try:
        _integracoes().registrar_auditoria(ator or "sistema", CHAVE_MODULO,
                                           acao,
                                           f"Alvo: {alvo}" + (f" | {detalhe}" if detalhe else ""))
    except Exception:
        try:
            _log().exception(f"_auditar({acao}) falhou")
        except Exception:
            pass


def get_config(chave, padrao=""):
    """Lê uma chave da configuração central (fail-soft)."""
    try:
        from mod_intranet.bd_conexao import get_config as _get
        return _get(chave, padrao)
    except Exception:
        return padrao


def set_config(chave, valor):
    """Grava uma chave da configuração central (fail-soft)."""
    try:
        from mod_intranet.bd_conexao import set_config as _set
        _set(chave, valor)
        return True
    except Exception:
        try:
            _log().exception(f"set_config({chave}) falhou")
        except Exception:
            pass
        return False


# ============ schema ============

DDL_ALMOXARIFADOS = """
CREATE TABLE IF NOT EXISTS tb_estoque_almoxarifado (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    sigla TEXT NOT NULL DEFAULT '',
    unidade_id INTEGER,
    unidade_nome TEXT NOT NULL DEFAULT '',
    responsavel_user_nome TEXT NOT NULL DEFAULT '',
    responsavel_nome TEXT NOT NULL DEFAULT '',
    prefixo_item TEXT NOT NULL DEFAULT 'IT',
    prefixo_documento TEXT NOT NULL DEFAULT 'DOC',
    digitos_numero INTEGER NOT NULL DEFAULT 4,
    cor TEXT NOT NULL DEFAULT '',
    central INTEGER NOT NULL DEFAULT 0,
    ativo INTEGER NOT NULL DEFAULT 1,
    bloqueado INTEGER NOT NULL DEFAULT 0,
    ordem INTEGER NOT NULL DEFAULT 0,
    data_criacao TEXT NOT NULL DEFAULT ''
)
"""

DDL_ITENS = """
CREATE TABLE IF NOT EXISTS tb_estoque_item (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    almoxarifado_id INTEGER NOT NULL,
    numero_sequencial INTEGER NOT NULL DEFAULT 0,
    numero TEXT NOT NULL DEFAULT '',
    descricao TEXT NOT NULL,
    unidade_medida TEXT NOT NULL DEFAULT 'UN',
    origem_padrao TEXT NOT NULL DEFAULT '',
    ativo INTEGER NOT NULL DEFAULT 1,
    criado_por TEXT NOT NULL DEFAULT '',
    criado_em TEXT NOT NULL DEFAULT '',
    atualizado_em TEXT NOT NULL DEFAULT ''
)
"""

DDL_SALDOS = """
CREATE TABLE IF NOT EXISTS tb_estoque_saldo (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    almoxarifado_id INTEGER NOT NULL,
    quantidade REAL NOT NULL DEFAULT 0,
    atualizado_em TEXT NOT NULL DEFAULT '',
    UNIQUE (item_id, almoxarifado_id)
)
"""

DDL_DOCUMENTOS = """
CREATE TABLE IF NOT EXISTS tb_estoque_documento (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    numero_sequencial INTEGER NOT NULL DEFAULT 0,
    numero TEXT NOT NULL DEFAULT '',
    tipo TEXT NOT NULL DEFAULT 'transferencia',
    almoxarifado_id INTEGER NOT NULL,
    almoxarifado_destino_id INTEGER,
    data_documento TEXT NOT NULL DEFAULT '',
    responsavel_user_nome TEXT NOT NULL DEFAULT '',
    criado_por TEXT NOT NULL DEFAULT '',
    criado_em TEXT NOT NULL DEFAULT '',
    observacao TEXT NOT NULL DEFAULT ''
)
"""

DDL_MOVIMENTOS = """
CREATE TABLE IF NOT EXISTS tb_estoque_movimento (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    documento_id INTEGER,
    documento_numero TEXT NOT NULL DEFAULT '',
    tipo TEXT NOT NULL DEFAULT 'entrada',
    item_id INTEGER NOT NULL,
    item_numero TEXT NOT NULL DEFAULT '',
    descricao TEXT NOT NULL DEFAULT '',
    unidade_medida TEXT NOT NULL DEFAULT '',
    almoxarifado_origem_id INTEGER,
    almoxarifado_destino_id INTEGER,
    quantidade REAL NOT NULL DEFAULT 0,
    data_movimento TEXT NOT NULL DEFAULT '',
    origem TEXT NOT NULL DEFAULT '',
    nota_empenho TEXT NOT NULL DEFAULT '',
    responsavel_user_nome TEXT NOT NULL DEFAULT '',
    usuario_actor TEXT NOT NULL DEFAULT '',
    criado_em TEXT NOT NULL DEFAULT '',
    observacao TEXT NOT NULL DEFAULT ''
)
"""

DDL_ENTREGAS = """
CREATE TABLE IF NOT EXISTS tb_estoque_entrega (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    item_numero TEXT NOT NULL DEFAULT '',
    descricao TEXT NOT NULL DEFAULT '',
    unidade_medida TEXT NOT NULL DEFAULT '',
    almoxarifado_id INTEGER NOT NULL,
    quantidade REAL NOT NULL DEFAULT 0,
    destino_sala TEXT NOT NULL DEFAULT '',
    destino_departamento TEXT NOT NULL DEFAULT '',
    responsavel_user_nome TEXT NOT NULL DEFAULT '',
    responsavel_nome TEXT NOT NULL DEFAULT '',
    data_entrega TEXT NOT NULL DEFAULT '',
    data_baixa TEXT NOT NULL DEFAULT '',
    situacao TEXT NOT NULL DEFAULT 'em_uso',
    documento_id INTEGER,
    criado_por TEXT NOT NULL DEFAULT '',
    criado_em TEXT NOT NULL DEFAULT '',
    atualizado_em TEXT NOT NULL DEFAULT ''
)
"""

DDL_RECOLHIMENTOS = """
CREATE TABLE IF NOT EXISTS tb_estoque_recolhimento (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    almoxarifado_id INTEGER NOT NULL,
    item_id INTEGER NOT NULL,
    entrega_id INTEGER,
    tipo_pedido TEXT NOT NULL DEFAULT 'recolhimento',
    quantidade REAL NOT NULL DEFAULT 0,
    destino_sala TEXT NOT NULL DEFAULT '',
    solicitante_user_nome TEXT NOT NULL DEFAULT '',
    solicitante_nome TEXT NOT NULL DEFAULT '',
    motivo TEXT NOT NULL DEFAULT '',
    situacao TEXT NOT NULL DEFAULT 'aberto',
    documento_id INTEGER,
    data_abertura TEXT NOT NULL DEFAULT '',
    data_atendimento TEXT NOT NULL DEFAULT '',
    atendido_por TEXT NOT NULL DEFAULT '',
    parecer TEXT NOT NULL DEFAULT ''
)
"""

DDL_TAREFAS = """
CREATE TABLE IF NOT EXISTS tb_estoque_tarefa (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    numero_sequencial INTEGER NOT NULL DEFAULT 0,
    numero TEXT NOT NULL DEFAULT '',
    titulo TEXT NOT NULL,
    descricao TEXT NOT NULL DEFAULT '',
    tipo TEXT NOT NULL DEFAULT 'receber',
    almoxarifado_id INTEGER,
    responsavel_user_nome TEXT NOT NULL DEFAULT '',
    responsavel_nome TEXT NOT NULL DEFAULT '',
    atendente_user_nome TEXT NOT NULL DEFAULT '',
    necessarios_convidados INTEGER NOT NULL DEFAULT 1,
    situacao TEXT NOT NULL DEFAULT 'aberta',
    criado_por TEXT NOT NULL DEFAULT '',
    criado_em TEXT NOT NULL DEFAULT '',
    data_conclusao TEXT NOT NULL DEFAULT ''
)
"""

DDL_CONVITES = """
CREATE TABLE IF NOT EXISTS tb_estoque_convite (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tarefa_id INTEGER NOT NULL,
    convidado_user_nome TEXT NOT NULL,
    nome_exibicao TEXT NOT NULL DEFAULT '',
    unidade TEXT NOT NULL DEFAULT '',
    papel TEXT NOT NULL DEFAULT 'participa',
    situacao TEXT NOT NULL DEFAULT 'pendente',
    convidado_por TEXT NOT NULL DEFAULT '',
    data_convite TEXT NOT NULL DEFAULT '',
    data_resposta TEXT NOT NULL DEFAULT '',
    recado TEXT NOT NULL DEFAULT ''
)
"""

DDL_USUARIOS = """
CREATE TABLE IF NOT EXISTS tb_estoque_usuario (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_nome TEXT NOT NULL UNIQUE,
    nome_exibicao TEXT NOT NULL DEFAULT '',
    unidade TEXT NOT NULL DEFAULT '',
    papel TEXT NOT NULL DEFAULT 'consulta',
    ativo INTEGER NOT NULL DEFAULT 1,
    criado_por TEXT NOT NULL DEFAULT '',
    criado_em TEXT NOT NULL DEFAULT ''
)
"""

DDL_SEQUENCIA = """
CREATE TABLE IF NOT EXISTS tb_estoque_sequencia (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    almoxarifado_id INTEGER NOT NULL,
    tipo TEXT NOT NULL DEFAULT 'item',
    ultimo_numero INTEGER NOT NULL DEFAULT 0,
    UNIQUE (almoxarifado_id, tipo)
)
"""

INDICES = (
    "CREATE INDEX IF NOT EXISTS ix_estoque_item_almoxarifado "
    "ON tb_estoque_item(almoxarifado_id, ativo)",
    "CREATE INDEX IF NOT EXISTS ix_estoque_item_numero "
    "ON tb_estoque_item(almoxarifado_id, numero_sequencial)",
    "CREATE INDEX IF NOT EXISTS ix_estoque_saldo_item "
    "ON tb_estoque_saldo(item_id, almoxarifado_id)",
    "CREATE INDEX IF NOT EXISTS ix_estoque_saldo_almoxarifado "
    "ON tb_estoque_saldo(almoxarifado_id)",
    "CREATE INDEX IF NOT EXISTS ix_estoque_documento_almoxarifado "
    "ON tb_estoque_documento(almoxarifado_id, numero_sequencial)",
    "CREATE INDEX IF NOT EXISTS ix_estoque_movimento_item "
    "ON tb_estoque_movimento(item_id, id)",
    "CREATE INDEX IF NOT EXISTS ix_estoque_movimento_data "
    "ON tb_estoque_movimento(data_movimento)",
    "CREATE INDEX IF NOT EXISTS ix_estoque_movimento_almoxarifado "
    "ON tb_estoque_movimento(almoxarifado_destino_id, tipo)",
    "CREATE INDEX IF NOT EXISTS ix_estoque_entrega_situacao "
    "ON tb_estoque_entrega(situacao, data_entrega)",
    "CREATE INDEX IF NOT EXISTS ix_estoque_entrega_almoxarifado "
    "ON tb_estoque_entrega(almoxarifado_id, situacao)",
    "CREATE INDEX IF NOT EXISTS ix_estoque_recolhimento_situacao "
    "ON tb_estoque_recolhimento(situacao, id)",
    "CREATE INDEX IF NOT EXISTS ix_estoque_recolhimento_solicitante "
    "ON tb_estoque_recolhimento(solicitante_user_nome, situacao)",
    "CREATE INDEX IF NOT EXISTS ix_estoque_tarefa_situacao "
    "ON tb_estoque_tarefa(situacao, id)",
    "CREATE INDEX IF NOT EXISTS ix_estoque_convite_convidade "
    "ON tb_estoque_convite(convidado_user_nome, situacao)",
    "CREATE INDEX IF NOT EXISTS ix_estoque_convite_tarefa "
    "ON tb_estoque_convite(tarefa_id)",
)

_NOMES_CAMPOS = {
    "almoxarifado": ("id", "nome", "sigla", "unidade_id", "unidade_nome",
                     "responsavel_user_nome", "responsavel_nome",
                     "prefixo_item", "prefixo_documento", "digitos_numero",
                     "cor", "central", "ativo", "bloqueado", "ordem",
                     "data_criacao"),
    "item": ("id", "almoxarifado_id", "numero_sequencial", "numero",
             "descricao", "unidade_medida", "origem_padrao", "ativo",
             "criado_por", "criado_em", "atualizado_em"),
    "documento": ("id", "numero_sequencial", "numero", "tipo", "almoxarifado_id",
                  "almoxarifado_destino_id", "data_documento",
                  "responsavel_user_nome", "criado_por", "criado_em",
                  "observacao"),
    "movimento": ("id", "documento_id", "documento_numero", "tipo", "item_id",
                  "item_numero", "descricao", "unidade_medida",
                  "almoxarifado_origem_id", "almoxarifado_destino_id",
                  "quantidade", "data_movimento", "origem", "nota_empenho",
                  "responsavel_user_nome", "usuario_actor", "criado_em",
                  "observacao"),
    "entrega": ("id", "item_id", "item_numero", "descricao", "unidade_medida",
                "almoxarifado_id", "quantidade", "destino_sala",
                "destino_departamento", "responsavel_user_nome",
                "responsavel_nome", "data_entrega", "data_baixa", "situacao",
                "documento_id", "criado_por", "criado_em", "atualizado_em"),
    "recolhimento": ("id", "almoxarifado_id", "item_id", "entrega_id",
                     "tipo_pedido", "quantidade", "destino_sala",
                     "solicitante_user_nome", "solicitante_nome", "motivo",
                     "situacao", "documento_id", "data_abertura",
                     "data_atendimento", "atendido_por", "parecer"),
    "tarefa": ("id", "numero_sequencial", "numero", "titulo", "descricao",
               "tipo", "almoxarifado_id", "responsavel_user_nome",
               "responsavel_nome", "atendente_user_nome",
               "necessarios_convidados", "situacao", "criado_por", "criado_em",
               "data_conclusao"),
    "convite": ("id", "tarefa_id", "convidado_user_nome", "nome_exibicao",
                "unidade", "papel", "situacao", "convidado_por", "data_convite",
                "data_resposta", "recado"),
    "usuario": ("id", "user_nome", "nome_exibicao", "unidade", "papel", "ativo",
                "criado_por", "criado_em"),
}


def _consolidar_chaves(cur):
    """Junta linhas duplicadas de SALDO e de SEQUÊNCIA e cria a chave única.

    POR QUE ISTO EXISTE
        O saldo de um item num almoxarifado e o contador de número são UNO só.
        Sem `UNIQUE` na tabela, o `INSERT OR IGNORE` que garante a linha nunca
        ignorava nada e nascia uma linha nova a cada chamada — e como o
        `UPDATE ... WHERE item_id=? AND almoxarifado_id=?` mexe em TODAS as
        linhas do par, o saldo passava a contar em dobro, em triplo. Um
        almoxarifado que recebeu 4 mostrava 8, e nenhuma conferência por soma
        revelaria: cada linha sozinha está certa.

    A ordem importa e é a mesma nos dois backends:
        1. cada linha duplicada recebe a SOMA do seu grupo (nada se perde);
        2. as cópias são apagadas, sobrando a de id maior;
        3. só então a chave única é criada — criar antes falharia.

    Idempotente: banco já limpo não tem o que consolidar, e o `CREATE UNIQUE
    INDEX IF NOT EXISTS` não faz nada. É o que faz rodar `init_db` mil vezes
    não mudar nada, inclusive num banco criado antes desta regra.
    """
    try:
        # ---- saldo: junta por (item, almoxarifado) ----
        cur.execute(
            "UPDATE tb_estoque_saldo SET quantidade = ("
            "  SELECT COALESCE(SUM(grupo.quantidade), 0) FROM tb_estoque_saldo grupo"
            "  WHERE grupo.item_id = tb_estoque_saldo.item_id"
            "    AND grupo.almoxarifado_id = tb_estoque_saldo.almoxarifado_id)")
        cur.execute("DELETE FROM tb_estoque_saldo WHERE id NOT IN "
                    "(SELECT MAX(id) FROM tb_estoque_saldo "
                    "GROUP BY item_id, almoxarifado_id)")
        # ---- sequência: NUNCA volta, então o contador fica com o MAIOR valor ----
        cur.execute(
            "UPDATE tb_estoque_sequencia SET ultimo_numero = ("
            "  SELECT MAX(grupo.ultimo_numero) FROM tb_estoque_sequencia grupo"
            "  WHERE grupo.almoxarifado_id = tb_estoque_sequencia.almoxarifado_id"
            "    AND grupo.tipo = tb_estoque_sequencia.tipo)")
        cur.execute("DELETE FROM tb_estoque_sequencia WHERE id NOT IN "
                    "(SELECT MAX(id) FROM tb_estoque_sequencia "
                    "GROUP BY almoxarifado_id, tipo)")
        # ---- agora sim, a chave única (e só agora: antes falharia) ----
        # `CREATE UNIQUE INDEX IF NOT EXISTS` e não só o `UNIQUE` do DDL: num
        # banco criado antes desta regra a TABELA já existe sem a restrição, e
        # `CREATE TABLE IF NOT EXISTS` não altera tabela que já está lá. O
        # índice é o que garante a unicidade nos dois casos — banco novo e banco
        # antigo — e vale igual no SQLite e no PostgreSQL.
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_estoque_saldo_chave "
                    "ON tb_estoque_saldo(item_id, almoxarifado_id)")
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_estoque_sequencia_chave "
                    "ON tb_estoque_sequencia(almoxarifado_id, tipo)")
        return True
    except Exception:
        _log().exception("_consolidar_chaves falhou")
        raise


def init_db():
    """Cria o schema do módulo (idempotente, portátil SQLite ↔ PostgreSQL).

    `CREATE TABLE IF NOT EXISTS` + `CREATE INDEX IF NOT EXISTS` — rodar mil
    vezes não muda nada. Sem `REFERENCES`: o tradutor de DDL do Postgres remove
    as chaves estrangeiras, então TODA cascata de `DELETE` é feita à mão, em
    transação curta, na ordem certa (ver `excluir_almoxarifado`).

    Garante também o ESTOQUE CENTRAL: ele é único e fixo, nasce com o primeiro
    `init_db` e nunca é apagado nem renomeado — é para onde entra tudo.

    Returns:
        bool: True quando o schema está no lugar.
    """
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        for ddl in (DDL_ALMOXARIFADOS, DDL_ITENS, DDL_SALDOS, DDL_DOCUMENTOS,
                    DDL_MOVIMENTOS, DDL_ENTREGAS, DDL_RECOLHIMENTOS,
                    DDL_TAREFAS, DDL_CONVITES, DDL_USUARIOS, DDL_SEQUENCIA):
            cur.execute(ddl)
        # consolida ANTES dos índices: a chave única de saldo e de sequência só
        # pode nascer depois que as cópias foram juntadas (ver a função)
        _consolidar_chaves(cur)
        for indice in INDICES:
            cur.execute(indice)
        _commit_com_retry(conn, contexto="init_db")
    except Exception:
        _rollback_seguro(conn, contexto="init_db")
        try:
            _log().exception("init_db falhou")
        except Exception:
            pass
        return False
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
    # O central é criado FORA da transação do schema: é um dado de negócio, e
    # ele precisa existir mesmo quando a segunda chamada acha tudo no lugar.
    return garantir_estoque_central() is not None


def garantir_estoque_central():
    """Devolve o almoxarifado CENTRAL, criando-o se ainda não existir.

    O central é único e fixo: não se apaga, não se renomeia, não se desativa.
    É a coluna "Estoque Central" do quadro de almoxarifados — o lugar por onde
    entra tudo. A criação é idempotente, então chamar a cada `init_db` é seguro.
    """
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT " + ", ".join(_NOMES_CAMPOS["almoxarifado"]) +
                    " FROM tb_estoque_almoxarifado WHERE central=1 "
                    "ORDER BY id ASC")
        linha = cur.fetchone()
        if linha:
            return _para_dict(_NOMES_CAMPOS["almoxarifado"], linha)
        cur.execute("SELECT COUNT(*) FROM tb_estoque_almoxarifado")
        total = int((cur.fetchone() or [0])[0] or 0)
        cur.execute(
            "INSERT INTO tb_estoque_almoxarifado "
            "(nome, sigla, unidade_id, unidade_nome, responsavel_user_nome, "
            " responsavel_nome, prefixo_item, prefixo_documento, digitos_numero, "
            " cor, central, ativo, bloqueado, ordem, data_criacao) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 1, 0, ?, ?)",
            (NOME_CENTRAL, "CEN", None, "", "", "",
             _prefixo_item_padrao(), _prefixo_documento_padrao(),
             _digitos_padrao(), _CORES_ALMOXARIFADO["azul"], total, _agora()))
        almoxarifado_id = int(cur.lastrowid)
        cur.execute("INSERT OR IGNORE INTO tb_estoque_sequencia "
                    "(almoxarifado_id, tipo, ultimo_numero) VALUES (?, 'item', 0)",
                    (almoxarifado_id,))
        cur.execute("INSERT OR IGNORE INTO tb_estoque_sequencia "
                    "(almoxarifado_id, tipo, ultimo_numero) "
                    "VALUES (?, 'documento', 0)", (almoxarifado_id,))
        _commit_com_retry(conn, contexto="garantir_estoque_central")
        cur.execute("SELECT " + ", ".join(_NOMES_CAMPOS["almoxarifado"]) +
                    " FROM tb_estoque_almoxarifado WHERE id=?", (almoxarifado_id,))
        return _para_dict(_NOMES_CAMPOS["almoxarifado"], cur.fetchone())
    except Exception:
        _rollback_seguro(conn, contexto="garantir_estoque_central")
        try:
            _log().exception("garantir_estoque_central falhou")
        except Exception:
            pass
        return None
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


# ============ leitura: linhas -> dicionário ============

def _para_dict(campos, linha):
    """Converte a tupla do cursor em dicionário com nome de campo."""
    if not linha:
        return None
    try:
        return {campo: linha[i] for i, campo in enumerate(campos)}
    except Exception:
        return None


# ============ número do item e do documento ============

NOME_CENTRAL = "Estoque Central"


def _prefixo_item_padrao():
    """Prefixo padrão do número do item, lido da configuração (fallback 'IT')."""
    return normalizar_prefixo(get_config("estoque_prefixo_item", "IT")) or "IT"


def _prefixo_documento_padrao():
    """Prefixo padrão do número do documento (fallback 'DOC')."""
    return normalizar_prefixo(get_config("estoque_prefixo_documento", "DOC")) or "DOC"


def _digitos_padrao():
    """Dígitos padrão do número, lidos da configuração (fallback 4)."""
    try:
        return validar_digitos(int(get_config("estoque_digitos_padrao",
                                              str(DIGITOS_PADRAO))))
    except (TypeError, ValueError):
        return DIGITOS_PADRAO


def _prefixo_do_nome(nome):
    """Prefixo tirado do nome: primeira palavra, até 6 caracteres, em maiúsculas.

    "Almoxarifado da Saúde" → "ALMOXA"; "Manutenção_predial" → "MANUTE". Sem
    acento e sem espaço: é o que o servidor dita ao telefone."""
    try:
        limpo = unicodedata.normalize("NFKD", str(nome or "")) \
            .encode("ascii", "ignore").decode()
        partes = re.findall(r"[A-Za-z0-9]+", limpo)
        if not partes:
            return "IT"
        return partes[0].upper()[:PREFIXO_PADRAO_TAMANHO] or "IT"
    except Exception:
        return "IT"


def normalizar_prefixo(prefixo):
    """Limpa o prefixo digitado à mão (sem acento, até 12 caracteres)."""
    try:
        limpo = unicodedata.normalize("NFKD", str(prefixo or "")) \
            .encode("ascii", "ignore").decode()
        return re.sub(r"[^A-Za-z0-9]+", "", limpo).upper()[:12]
    except Exception:
        return ""


def validar_digitos(digitos):
    """Clamp do número de dígitos (3 a 8) — o almoxarifado fica sempre válido."""
    try:
        valor = int(digitos)
    except (TypeError, ValueError):
        return DIGITOS_PADRAO
    return max(DIGITOS_MINIMO, min(DIGITOS_MAXIMO, valor))


def montar_numero(prefixo, sequencial, digitos):
    """Monta o número exibido: `PREFIXO-0001`."""
    try:
        dig = validar_digitos(digitos)
        return f"{(prefixo or 'IT').upper()}-{int(sequencial):0{dig}d}"
    except Exception:
        return f"IT-{int(sequencial or 0):0{DIGITOS_PADRAO}d}"


def _reservar_numero(cur, almoxarifado_id, tipo):
    """Reserva o próximo número do almoxarifado NA TRANSAÇÃO JÁ ABERTA.

    O `UPDATE ... SET ultimo_numero = ultimo_numero + 1` seguido do `SELECT`
    na MESMA transação é o que serializa a reserva no próprio banco (o Python
    não segura nada): quem entra depois do primeiro UPDATE espera o commit do
    primeiro e lê o valor seguinte. Se a transação for desfeita, o contador
    volta junto — buraco nenhum, número repetido nenhum.

    `tipo` separa as duas contagens: o item e o documento têm números
    independentes, porque um não é o outro e comparar `IT-0001` com `DOC-0001`
    não diz nada sobre o mesmo objeto.
    """
    cur.execute("INSERT OR IGNORE INTO tb_estoque_sequencia "
                "(almoxarifado_id, tipo, ultimo_numero) VALUES (?, ?, 0)",
                (int(almoxarifado_id), tipo))
    cur.execute("UPDATE tb_estoque_sequencia SET ultimo_numero = ultimo_numero + 1 "
                "WHERE almoxarifado_id=? AND tipo=?",
                (int(almoxarifado_id), tipo))
    cur.execute("SELECT ultimo_numero FROM tb_estoque_sequencia "
                "WHERE almoxarifado_id=? AND tipo=?",
                (int(almoxarifado_id), tipo))
    linha = cur.fetchone()
    return int(linha[0]) if linha else 1


def alocar_numero_na_conexao(conn, almoxarifado_id, tipo="item"):
    """Reserva o próximo número na conexão/transação do chamador.

    Existe para deixar explícito (e testável) que a reserva acontece DENTRO
    da transação do INSERT: quem chamar e der rollback em seguida recebe o
    mesmo número na próxima tentativa. Nunca commitar por aqui."""
    try:
        return _reservar_numero(conn.cursor(), almoxarifado_id, tipo)
    except Exception:
        _log().exception("alocar_numero_na_conexao falhou")
        raise


def proximo_numero(almoxarifado_id, tipo="item"):
    """Número que o próximo item (ou documento) receberia. Não reserva nada."""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT ultimo_numero FROM tb_estoque_sequencia "
                    "WHERE almoxarifado_id=? AND tipo=?",
                    (int(almoxarifado_id), tipo))
        linha = cur.fetchone()
        return int(linha[0]) if linha else 0
    except Exception:
        _log().exception("proximo_numero falhou")
        return 0
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def definir_formato_numero(almoxarifado_id, prefixo_item=None,
                           prefixo_documento=None, digitos=None, ator="",
                           eh_admin_geral=False):
    """Ajusta o FORMATO do número do almoxarifado. NÃO renumera o que já existe.

    O número guardado em cada item e em cada documento é o histórico — quem já
    tem `IT-0007` continua com `IT-0007` para sempre. O formato novo vale para
    os próximos.

    Returns:
        tuple: (ok, mensagem)
    """
    conn = None
    try:
        almoxarifado_id = int(almoxarifado_id)
        if not pode_administrar(ator, eh_admin_geral):
            return (False, "Só quem administra o módulo altera o formato do número.")
        atual = obter_almoxarifado(almoxarifado_id)
        if not atual:
            return (False, "Almoxarifado não encontrado.")
        novo_item = normalizar_prefixo(prefixo_item) if prefixo_item is not None \
            else (atual["prefixo_item"] or "")
        novo_doc = normalizar_prefixo(prefixo_documento) if prefixo_documento is not None \
            else (atual["prefixo_documento"] or "")
        novos_digitos = validar_digitos(digitos) if digitos is not None \
            else validar_digitos(atual["digitos_numero"])
        conn = get_connection()
        cur = conn.cursor()
        prefixo_item_gravado = novo_item or "IT"
        prefixo_doc_gravado = novo_doc or "DOC"
        cur.execute("UPDATE tb_estoque_almoxarifado SET prefixo_item=?, "
                    "prefixo_documento=?, digitos_numero=? WHERE id=?",
                    (prefixo_item_gravado, prefixo_doc_gravado, novos_digitos,
                     almoxarifado_id))
        _commit_com_retry(conn, contexto="definir_formato_numero")
        _auditar(ator, "definir_formato_numero", f"almoxarifado {almoxarifado_id}",
                 f"item={prefixo_item_gravado} documento={prefixo_doc_gravado} "
                 f"digitos={novos_digitos}")
        return (True, f"Número do almoxarifado: item {prefixo_item_gravado}-"
                      f"{'0' * novos_digitos}, documento {prefixo_doc_gravado}-"
                      f"{'0' * novos_digitos} a partir de agora "
                      f"(os anteriores mantêm o número).")
    except Exception:
        _rollback_seguro(conn, contexto="definir_formato_numero")
        _log().exception("definir_formato_numero falhou")
        return (False, "Erro ao alterar o formato do número.")
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


# ============ almoxarifados ============

def criar_almoxarifado(nome, unidade_id=None, unidade_nome="",
                       responsavel_user_nome="", sigla="", cor="",
                       prefixo_item="", prefixo_documento="",
                       digitos_numero=DIGITOS_PADRAO, ator="",
                       eh_admin_geral=False):
    """Cria um almoxarifado descentralizado, ligado a uma secretaria.

    Cada secretaria do organograma pode ter o seu. Quem decide quais
    secretarias têm almoxarifado é o ADMINISTRADOR do módulo: secretaria sem
    almoxarifado simplesmente não tem, e nada aparece para ela.

    Returns:
        tuple: (ok, mensagem, almoxarifado_id ou None)
    """
    conn = None
    try:
        titulo = (nome or "").strip()
        unidade_id = _como_id(unidade_id)
        if not pode_administrar(ator, eh_admin_geral):
            return (False, "Só o administrador do módulo cria almoxarifado.", None)
        if len(titulo) < 2:
            return (False, "Dê um nome ao almoxarifado (mínimo 2 letras).", None)
        if not (unidade_nome or "").strip() and not unidade_id:
            return (False, "Escolha a secretaria do almoxarifado.", None)
        nome_unidade = (unidade_nome or "").strip()
        sigla_calc = normalizar_prefixo(sigla)[:6] or _prefixo_do_nome(titulo)
        nome_resp, _unidade_resp = _ficha_do_servidor(responsavel_user_nome)

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM tb_estoque_almoxarifado "
                    "WHERE unidade_id IS NOT NULL AND unidade_id=? AND central=0",
                    (unidade_id if unidade_id is not None else -1,))
        if cur.fetchone():
            return (False, f"A secretaria {nome_unidade} já tem almoxarifado.", None)
        if _norm(nome_unidade) and nome_unidade:
            cur.execute("SELECT id FROM tb_estoque_almoxarifado "
                        "WHERE central=0 AND unidade_nome=?",
                        (nome_unidade,))
            if cur.fetchone():
                return (False, f"A secretaria {nome_unidade} já tem almoxarifado.", None)
        cur.execute("SELECT COALESCE(MAX(ordem), 0) FROM tb_estoque_almoxarifado")
        ordem = int((cur.fetchone() or [0])[0] or 0) + 1
        prefixo_it = normalizar_prefixo(prefixo_item) or _prefixo_item_padrao()
        prefixo_dc = normalizar_prefixo(prefixo_documento) or _prefixo_documento_padrao()
        cur.execute(
            "INSERT INTO tb_estoque_almoxarifado "
            "(nome, sigla, unidade_id, unidade_nome, responsavel_user_nome, "
            " responsavel_nome, prefixo_item, prefixo_documento, digitos_numero, "
            " cor, central, ativo, bloqueado, ordem, data_criacao) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 1, 0, ?, ?)",
            (titulo, sigla_calc, unidade_id,
             nome_unidade, (responsavel_user_nome or "").strip(), nome_resp,
             prefixo_it, prefixo_dc, validar_digitos(digitos_numero),
             (cor or "").strip() or _CORES_ALMOXARIFADO["verde"], ordem, _agora()))
        almoxarifado_id = int(cur.lastrowid)
        for tipo in ("item", "documento"):
            cur.execute("INSERT OR IGNORE INTO tb_estoque_sequencia "
                        "(almoxarifado_id, tipo, ultimo_numero) VALUES (?, ?, 0)",
                        (almoxarifado_id, tipo))
        _commit_com_retry(conn, contexto="criar_almoxarifado")
        _auditar(ator, "criar_almoxarifado", f"almoxarifado {almoxarifado_id}",
                 f"nome={titulo} secretaria={nome_unidade or '-'}")
        return (True, f"Almoxarifado criado para {nome_unidade or titulo}. "
                      f"O primeiro item sai {montar_numero(prefixo_it, 1, digitos_numero)}.",
                almoxarifado_id)
    except Exception:
        _rollback_seguro(conn, contexto="criar_almoxarifado")
        _log().exception("criar_almoxarifado falhou")
        return (False, "Erro ao criar o almoxarifado.", None)
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def obter_almoxarifado(almoxarifado_id):
    """Dados de um almoxarifado por id, ou None."""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT " + ", ".join(_NOMES_CAMPOS["almoxarifado"]) +
                    " FROM tb_estoque_almoxarifado WHERE id=?",
                    (int(almoxarifado_id),))
        return _para_dict(_NOMES_CAMPOS["almoxarifado"], cur.fetchone())
    except Exception:
        _log().exception("obter_almoxarifado falhou")
        return None
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def listar_almoxarifados(incluir_inativos=True, apenas_ativos=False):
    """Almoxarifados na ordem do quadro — o central primeiro, sempre.

    O central é fixo e não se apaga: ele volta no topo da lista mesmo com
    `ordem` mudada, porque é a coluna de onde entra tudo.
    """
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        sql = "SELECT " + ", ".join(_NOMES_CAMPOS["almoxarifado"]) + \
              " FROM tb_estoque_almoxarifado WHERE 1=1"
        if apenas_ativos:
            sql += " AND ativo=1"
        elif not incluir_inativos:
            sql += " AND ativo=1"
        sql += " ORDER BY central DESC, ordem ASC, nome ASC"
        cur.execute(sql)
        return [_para_dict(_NOMES_CAMPOS["almoxarifado"], linha)
                for linha in cur.fetchall()]
    except Exception:
        _log().exception("listar_almoxarifados falhou")
        return []
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def listar_almoxarifados_descentralizados(ativo=True):
    """Só os almoxarifados de secretaria (sem o central)."""
    return [a for a in listar_almoxarifados()
            if not a.get("central") and (not ativo or a.get("ativo"))]


def atualizar_almoxarifado(almoxarifado_id, campos, ator="", eh_admin_geral=False):
    """Altera os dados do almoxarifado (nome, responsável, sigla, cor, ativo).

    O CENTRAL NÃO MUDA: nem nome, nem secretaria, nem exclusão. Ele é a âncora
    do módulo — quem apaga o central apaga o referência de todos os saldos.

    Returns:
        tuple: (ok, mensagem)
    """
    conn = None
    try:
        almoxarifado_id = int(almoxarifado_id)
        if not pode_administrar(ator, eh_admin_geral):
            return (False, "Só o administrador do módulo altera o almoxarifado.")
        atual = obter_almoxarifado(almoxarifado_id)
        if not atual:
            return (False, "Almoxarifado não encontrado.")
        if atual.get("central"):
            return (False, "O estoque central é fixo: não se renomeia nem se altera.")
        nome = (campos.get("nome", atual["nome"]) or "").strip()
        if len(nome) < 2:
            return (False, "Dê um nome ao almoxarifado (mínimo 2 letras).")
        responsavel = (campos.get("responsavel_user_nome",
                                  atual["responsavel_user_nome"]) or "").strip()
        nome_resp = (campos.get("responsavel_nome")
                     or _ficha_do_servidor(responsavel)[0]
                     or atual["responsavel_nome"] or "")
        unidade_nome = (campos.get("unidade_nome", atual["unidade_nome"])
                        or "").strip()
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "UPDATE tb_estoque_almoxarifado SET nome=?, sigla=?, unidade_nome=?, "
            " responsavel_user_nome=?, responsavel_nome=?, cor=?, ativo=?, "
            " bloqueado=? WHERE id=?",
            (nome,
             normalizar_prefixo(campos.get("sigla", atual["sigla"]))[:6]
             or atual["sigla"], unidade_nome, responsavel, nome_resp,
             (campos.get("cor", atual["cor"]) or "").strip(),
             1 if campos.get("ativo", atual["ativo"]) else 0,
             1 if campos.get("bloqueado", atual["bloqueado"]) else 0,
             almoxarifado_id))
        _commit_com_retry(conn, contexto="atualizar_almoxarifado")
        _auditar(ator, "atualizar_almoxarifado", f"almoxarifado {almoxarifado_id}",
                 f"nome={nome} responsavel={responsavel or '-'}")
        return (True, "Almoxarifado atualizado.")
    except Exception:
        _rollback_seguro(conn, contexto="atualizar_almoxarifado")
        _log().exception("atualizar_almoxarifado falhou")
        return (False, "Erro ao atualizar o almoxarifado.")
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def excluir_almoxarifado(almoxarifado_id, ator="", eh_admin_geral=False):
    """Exclui o almoxarifado e TUDO que é dele, na ordem certa, em transação curta.

    O tradutor de DDL do Postgres remove as chaves estrangeiras, então a
    cascata é feita à mão: saldos, entregas, movimentos, documentos, recolhimentos
    e convites de tarefas primeiro; depois o almoxarifado e a sequência.

    O CENTRAL NÃO VAI: é fixo. E almoxarifado com saldo não vai — quem
    apaga um almoxarifado com material dentro apaga material.

    Returns:
        tuple: (ok, mensagem)
    """
    conn = None
    try:
        almoxarifado_id = int(almoxarifado_id)
        if not pode_administrar(ator, eh_admin_geral):
            return (False, "Só o administrador do módulo exclui almoxarifado.")
        atual = obter_almoxarifado(almoxarifado_id)
        if not atual:
            return (False, "Almoxarifado não encontrado.")
        if atual.get("central"):
            return (False, "O estoque central é fixo e não pode ser excluído.")
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COALESCE(SUM(quantidade), 0) FROM tb_estoque_saldo "
                    "WHERE almoxarifado_id=?", (almoxarifado_id,))
        saldo = _arred((cur.fetchone() or [0])[0])
        if saldo > 0:
            return (False, f"O almoxarifado ainda tem {saldo:g} unidade(s) em "
                           "estoque. Transfira ou devolva antes de excluir.")
        cur.execute("SELECT COUNT(*) FROM tb_estoque_entrega "
                    "WHERE almoxarifado_id=? AND situacao='em_uso'",
                    (almoxarifado_id,))
        em_uso = int((cur.fetchone() or [0])[0] or 0)
        if em_uso:
            return (False, f"Há {em_uso} entrega(s) em uso linked a este "
                           "almoxarifado. Recolha antes de excluir.")
        # ordem da cascata: o que aponta para o almoxarifado sai antes dele
        for tabela, coluna in (("tb_estoque_saldo", "almoxarifado_id"),
                               ("tb_estoque_entrega", "almoxarifado_id"),
                               ("tb_estoque_recolhimento", "almoxarifado_id"),
                               ("tb_estoque_tarefa", "almoxarifado_id")):
            cur.execute(f"DELETE FROM {tabela} WHERE {coluna}=?", (almoxarifado_id,))
        for tabela, coluna in (("tb_estoque_movimento", "almoxarifado_origem_id"),
                               ("tb_estoque_movimento", "almoxarifado_destino_id"),
                               ("tb_estoque_documento", "almoxarifado_id"),
                               ("tb_estoque_documento", "almoxarifado_destino_id"),
                               ("tb_estoque_item", "almoxarifado_id")):
            cur.execute(f"DELETE FROM {tabela} WHERE {coluna}=?", (almoxarifado_id,))
        cur.execute("DELETE FROM tb_estoque_sequencia WHERE almoxarifado_id=?",
                    (almoxarifado_id,))
        cur.execute("DELETE FROM tb_estoque_almoxarifado WHERE id=?",
                    (almoxarifado_id,))
        _commit_com_retry(conn, contexto="excluir_almoxarifado")
        _auditar(ator, "excluir_almoxarifado", f"almoxarifado {almoxarifado_id}",
                 f"nome={atual['nome']}")
        return (True, f"Almoxarifado {atual['nome']} excluído.")
    except Exception:
        _rollback_seguro(conn, contexto="excluir_almoxarifado")
        _log().exception("excluir_almoxarifado falhou")
        return (False, "Erro ao excluir o almoxarifado.")
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def reordenar_almoxarifados(ordem_ids, ator="", eh_admin_geral=False):
    """Reordena os almoxarifados descentralizados. Recebe os ids na ordem nova.

    O CENTRAL NÃO SE MOVE: é fixo e sempre primeiro — é a coluna de onde entra
    tudo, e um quadro de almoxarifados que a troca de posição faz perder de vista
    é um quadro em que ninguém confia.

    Returns:
        tuple: (ok, mensagem)
    """
    conn = None
    try:
        if not pode_administrar(ator, eh_admin_geral):
            return (False, "Só o administrador do módulo reordena os almoxarifados.")
        descentralizados = listar_almoxarifados_descentralizados()
        conhecidos = {a["id"] for a in descentralizados}
        try:
            lista = [int(i) for i in (ordem_ids or [])]
        except (TypeError, ValueError):
            return (False, "Ordem dos almoxarifados inválida.")
        if set(lista) != conhecidos or len(lista) != len(conhecidos):
            return (False, "A lista de almoxarifados não bate com a do banco.")
        conn = get_connection()
        cur = conn.cursor()
        for posicao, almoxarifado_id in enumerate(lista, start=1):
            cur.execute("UPDATE tb_estoque_almoxarifado SET ordem=? WHERE id=?",
                        (posicao, almoxarifado_id))
        _commit_com_retry(conn, contexto="reordenar_almoxarifados")
        _auditar(ator, "reordenar_almoxarifados", "mod_estoque",
                 "ordem=" + ">".join(str(i) for i in lista))
        return (True, "Almoxarifados reordenados.")
    except Exception:
        _rollback_seguro(conn, contexto="reordenar_almoxarifados")
        _log().exception("reordenar_almoxarifados falhou")
        return (False, "Erro ao reordenar os almoxarifados.")
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def _ficha_do_servidor(user_nome):
    """(nome_exibicao, unidade) do servidor, pelo cadastro de usuários.

    A busca é feita pela FACHADA do núcleo: o módulo de estoque conhece o nome
    que a pessoa deve ler, nunca a matrícula crua sozinha. Falha aqui devolve
    vazio — o vínculo ainda é gravado pelo login."""
    try:
        alvo = (user_nome or "").strip()
        if not alvo:
            return ("", "")
        achados = _integracoes().buscar_usuarios_gestao(termo=alvo, limite=20) or []
        for achado in achados:
            if str(achado.get("user_nome") or "").strip().lower() == alvo.lower():
                return (achado.get("nome_exibicao") or alvo,
                        achado.get("unidade") or achado.get("lotacao") or "")
        if achados:
            return (achados[0].get("nome_exibicao") or alvo,
                    achados[0].get("unidade") or achados[0].get("lotacao") or "")
        return (alvo, "")
    except Exception:
        try:
            _log().warning(f"_ficha_do_servidor({user_nome}) falhou — "
                           "seguindo só com o login")
        except Exception:
            pass
        return (user_nome or "", "")


def sugerir_secretaria(user_nome):
    """`(unidade_id, unidade_nome)` do servidor, para sugerir a secretaria dele.

    A lotação tem precedência sobre a unidade: é o setor onde a pessoa
    trabalha de fato. Serve para o administrador criar o almoxarifado da
    secretaria com um clique, sem o servidor ter que escolher à mão.
    """
    try:
        mapa = _integracoes().unidades_por_usuario_gestao() or {}
        info = mapa.get((user_nome or "").strip()) or {}
        for campo in ("lotacao", "unidade"):
            nome = (info.get(campo) or "").strip()
            if not nome:
                continue
            consulta = _integracoes().unidades_do_organograma_por_nome() or {}
            achada = consulta.get(_norm(nome))
            if achada:
                return (achada.get("id"), achada.get("nome") or nome)
            return (None, nome)
        return (None, "")
    except Exception:
        try:
            _log().warning(f"sugerir_secretaria({user_nome}) falhou")
        except Exception:
            pass
        return (None, "")


# ============ vínculo de servidores e papéis ============

def vincular_usuario(user_nome, papel=PAPEL_CONSULTA, ator="", eh_admin_geral=False):
    """Liga um servidor JÁ CADASTRADO ao módulo de estoque, com um papel.

    Este módulo NÃO cria usuário: a lista daqui é um VÍNCULO com o login de quem
    já existe no cadastro. Quem é escolhido e com que papel é decisão do
    administrador do módulo.

    Returns:
        tuple: (ok, mensagem)
    """
    conn = None
    try:
        alvo = (user_nome or "").strip()
        if not pode_administrar(ator, eh_admin_geral):
            return (False, "Só o administrador do módulo escolhe quem opera.")
        if not alvo:
            return (False, "Escolha o servidor que vai operar o módulo.")
        if papel not in PAPEIS:
            return (False, "Papel inválido: use consulta, operador ou administrador.")
        nome_exibicao, unidade = _ficha_do_servidor(alvo)
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM tb_estoque_usuario WHERE user_nome=?", (alvo,))
        existente = cur.fetchone()
        if existente:
            cur.execute("UPDATE tb_estoque_usuario SET nome_exibicao=?, unidade=?, "
                        "papel=?, ativo=1 WHERE id=?",
                        (nome_exibicao, unidade, papel, existente[0]))
            mensagem = f"{nome_exibicao} já participava; papel agora é {papel}."
        else:
            cur.execute("INSERT INTO tb_estoque_usuario "
                        "(user_nome, nome_exibicao, unidade, papel, ativo, "
                        " criado_por, criado_em) VALUES (?, ?, ?, ?, 1, ?, ?)",
                        (alvo, nome_exibicao, unidade, papel, ator or "", _agora()))
            mensagem = f"{nome_exibicao} entrou no módulo como {papel}."
        _commit_com_retry(conn, contexto="vincular_usuario")
        _auditar(ator, "vincular_usuario", f"servidor {alvo}", f"papel={papel}")
        return (True, mensagem)
    except Exception:
        _rollback_seguro(conn, contexto="vincular_usuario")
        _log().exception("vincular_usuario falhou")
        return (False, "Erro ao vincular o servidor ao módulo.")
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def remover_vinculo(user_nome, ator="", eh_admin_geral=False):
    """Tira o servidor da lista de quem opera o módulo. O cadastro é dele."""
    conn = None
    try:
        alvo = (user_nome or "").strip()
        if not pode_administrar(ator, eh_admin_geral):
            return (False, "Só o administrador do módulo retira quem opera.")
        if not alvo:
            return (False, "Escolha o servidor que sai do módulo.")
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM tb_estoque_usuario WHERE user_nome=?", (alvo,))
        apagados = cur.rowcount if cur.rowcount is not None else 0
        _commit_com_retry(conn, contexto="remover_vinculo")
        _auditar(ator, "remover_vinculo", f"servidor {alvo}")
        if not apagados:
            return (False, "Esse servidor não estava na lista do módulo.")
        return (True, f"Servidor {alvo} saiu do módulo de estoque.")
    except Exception:
        _rollback_seguro(conn, contexto="remover_vinculo")
        _log().exception("remover_vinculo falhou")
        return (False, "Erro ao retirar o servidor do módulo.")
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def listar_usuarios_vinculados(incluir_inativos=True):
    """Quem opera o módulo, com nome de exibição, unidade e papel."""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        sql = "SELECT " + ", ".join(_NOMES_CAMPOS["usuario"]) + \
              " FROM tb_estoque_usuario WHERE 1=1"
        if not incluir_inativos:
            sql += " AND ativo=1"
        sql += " ORDER BY nome_exibicao ASC, user_nome ASC"
        cur.execute(sql)
        return [_para_dict(_NOMES_CAMPOS["usuario"], linha)
                for linha in cur.fetchall()]
    except Exception:
        _log().exception("listar_usuarios_vinculados falhou")
        return []
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def papel_no_estoque(user_nome, eh_admin_geral=False):
    """Papel do servidor no módulo: 'consulta' | 'operador' | 'administrador'.

    A fonte é o VÍNCULO em `tb_estoque_usuario` — quem escolheu e com que
    papel. Quem tem acesso liberado ao módulo mas não foi vinculado entra como
    CONSULTA: melhor o servidor olhar e perguntar do que movimentar material
    alheio por uma liberação padrão.

    O administrador geral (`administrador_geral`) administra o módulo inteiro
    sem precisar de vínculo aqui.
    """
    try:
        if eh_admin_geral:
            return PAPEL_ADMINISTRADOR
        alvo = (user_nome or "").strip()
        if not alvo:
            return None
        for vinculado in listar_usuarios_vinculados():
            if (vinculado.get("user_nome") or "") == alvo:
                if not vinculado.get("ativo"):
                    return None
                papel = vinculado.get("papel") or PAPEL_CONSULTA
                return papel if papel in PAPEIS else PAPEL_CONSULTA
        # Sem vínculo: quem o cadastro diz que é administrador do módulo é
        # administrador aqui; o resto que chegou com acesso padrão é consulta.
        papel_cadastro = _integracoes().obter_papel_gestao(alvo, CHAVE_MODULO)
        if papel_cadastro == "administrador":
            return PAPEL_ADMINISTRADOR
        return PAPEL_CONSULTA
    except Exception:
        _log().exception(f"papel_no_estoque({user_nome}) falhou")
        return None


_PODE_MOVIMENTAR = (PAPEL_OPERADOR, PAPEL_ADMINISTRADOR)


def pode_consultar(user_nome, eh_admin_geral=False):
    """Verdadeiro quando o servidor enxerga o módulo."""
    return papel_no_estoque(user_nome, eh_admin_geral) is not None


def pode_movimentar(user_nome, eh_admin_geral=False):
    """Verdadeiro quando o servidor movimenta estoque (entra, transfere, devolve)."""
    return papel_no_estoque(user_nome, eh_admin_geral) in _PODE_MOVIMENTAR


def pode_administrar(user_nome, eh_admin_geral=False):
    """Verdadeiro quando o servidor cria almoxarifado, cadastra item e gerencia."""
    return papel_no_estoque(user_nome, eh_admin_geral) == PAPEL_ADMINISTRADOR


# ============ item e saldo ============

def cadastrar_item(descricao, unidade_medida="UN", almoxarifado_id=None,
                   origem_padrao="", ator="", eh_admin_geral=False):
    """Cadastra um item no catálogo e RESERVA o número do almoxarifado.

    O número é alocado dentro da transação do INSERT: `UPDATE ... SET
    ultimo_numero = ultimo_numero + 1` seguido do `SELECT` na MESMA transação
    é o que serializa a reserva no banco (o Python não segura nada). Se a
    transação falhar, o contador volta junto — buraco nenhum, número repetido
    nenhum. Item repetido no mesmo almoxarifado NÃO cria segunda linha: o
    catálogo é um só, com o mesmo número, e o saldo é que muda.

    Returns:
        tuple: (ok, mensagem, item_id ou None)
    """
    ultimo_erro = None
    for tentativa in range(1, TENTATIVAS_LOCKED + 1):
        conn = None
        try:
            nome = (descricao or "").strip()
            if not pode_administrar(ator, eh_admin_geral):
                return (False, "Só o administrador do módulo cadastra item.", None)
            if len(nome) < 3:
                return (False, "Descreva o item (mínimo 3 letras).", None)
            if not almoxarifado_id:
                central = garantir_estoque_central()
                if not central:
                    return (False, "Estoque central indisponível.", None)
                almoxarifado_id = central["id"]
            almoxarifado = obter_almoxarifado(almoxarifado_id)
            if not almoxarifado:
                return (False, "Almoxarifado não encontrado.", None)
            if not almoxarifado.get("ativo"):
                return (False, "Este almoxarifado está desativado.", None)
            unidade = (unidade_medida or "UN").strip().upper()[:8] or "UN"

            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT id, numero FROM tb_estoque_item "
                        "WHERE almoxarifado_id=? AND descricao=?",
                        (int(almoxarifado_id), nome))
            existente = cur.fetchone()
            if existente:
                cur.execute("UPDATE tb_estoque_item SET unidade_medida=?, "
                            "ativo=1, atualizado_em=? WHERE id=?",
                            (unidade, _agora(), existente[0]))
                _commit_com_retry(conn, contexto="cadastrar_item:repetido")
                return (False, f"O item {existente[1]} já está cadastrado neste "
                               f"almoxarifado — a quantidade dele muda por "
                               f"entrada, transferência ou devolução.", existente[0])
            # ---- reserva do número (serializada pelo banco) ----
            sequencial = _reservar_numero(cur, almoxarifado_id, "item")
            numero = montar_numero(almoxarifado.get("prefixo_item") or "IT",
                                   sequencial, almoxarifado.get("digitos_numero"))
            agora = _agora()
            cur.execute(
                "INSERT INTO tb_estoque_item "
                "(almoxarifado_id, numero_sequencial, numero, descricao, "
                " unidade_medida, origem_padrao, ativo, criado_por, criado_em, "
                " atualizado_em) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?)",
                (int(almoxarifado_id), sequencial, numero, nome, unidade,
                 (origem_padrao or "").strip(), ator or "", agora, agora))
            item_id = int(cur.lastrowid)
            _zerar_saldo(cur, item_id, int(almoxarifado_id), agora)
            _commit_com_retry(conn,
                              contexto=f"cadastrar_item:{almoxarifado_id}")
            _auditar(ator, "cadastrar_item", f"item {numero}",
                     f"descricao={nome} unidade={unidade}")
            return (True, f"Item {numero} cadastrado: {nome} ({unidade}). "
                          f"Agora entre a quantidade pelo central.", item_id)
        except Exception as exc:
            ultimo_erro = exc
            _rollback_seguro(conn, contexto="cadastrar_item")
            if _eh_bloqueio_banco(exc) and tentativa < TENTATIVAS_LOCKED:
                try:
                    _log().warning("cadastrar_item: almoxarifado ocupado, "
                                   f"tentativa {tentativa}/{TENTATIVAS_LOCKED}")
                except Exception:
                    pass
                try:
                    time.sleep(ESPERA_LOCKED_SEG * tentativa)
                except Exception:
                    pass
                continue
            try:
                _log().exception("cadastrar_item falhou")
            except Exception:
                pass
            return (False, "Erro ao cadastrar o item.", None)
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
    try:
        _log().error(f"cadastrar_item: almoxarifado travado após "
                     f"{TENTATIVAS_LOCKED} tentativas ({ultimo_erro})")
    except Exception:
        pass
    return (False, "O almoxarifado está muito movimentado. Tente de novo.", None)


def obter_item(item_id):
    """Dados de um item do catálogo, ou None."""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT " + ", ".join(_NOMES_CAMPOS["item"]) +
                    " FROM tb_estoque_item WHERE id=?", (int(item_id),))
        return _para_dict(_NOMES_CAMPOS["item"], cur.fetchone())
    except Exception:
        _log().exception("obter_item falhou")
        return None
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def _zerar_saldo(cur, item_id, almoxarifado_id, agora):
    """Garante a linha de saldo do item no almoxarifado, com quantidade zero."""
    cur.execute("INSERT OR IGNORE INTO tb_estoque_saldo "
                "(item_id, almoxarifado_id, quantidade, atualizado_em) "
                "VALUES (?, ?, 0, ?)", (int(item_id), int(almoxarifado_id), agora))
    return True


def saldo_item(item_id, almoxarifado_id):
    """Quanto do item está DISPONÍVEL naquele almoxarifado (0 quando não há)."""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT quantidade FROM tb_estoque_saldo "
                    "WHERE item_id=? AND almoxarifado_id=?",
                    (int(item_id), int(almoxarifado_id)))
        linha = cur.fetchone()
        return _arred(linha[0]) if linha else 0.0
    except Exception:
        _log().exception("saldo_item falhou")
        return 0.0
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def _saldos_por_almoxarifado(cur, item_id):
    """`{almoxarifado_id: quantidade}` de um item — quem tem quanto."""
    try:
        cur.execute("SELECT almoxarifado_id, quantidade FROM tb_estoque_saldo "
                    "WHERE item_id=? AND quantidade>0", (int(item_id),))
        return {int(linha[0]): _arred(linha[1]) for linha in cur.fetchall()}
    except Exception:
        _log().exception("_saldos_por_almoxarifado falhou")
        return {}


def _saldos_item(cur, item_id):
    """`{almoxarifado_id: quantidade}` incluindo os saldos zerados."""
    try:
        cur.execute("SELECT almoxarifado_id, quantidade FROM tb_estoque_saldo "
                    "WHERE item_id=?", (int(item_id),))
        return {int(linha[0]): _arred(linha[1]) for linha in cur.fetchall()}
    except Exception:
        _log().exception("_saldos_item falhou")
        return {}


def _nome_do_almoxarifado(almoxarifado_id):
    """Nome do almoxarifado (para as mensagens de erro do servidor)."""
    almoxarifado = obter_almoxarifado(almoxarifado_id) or {}
    return almoxarifado.get("nome") or f"almoxarifado {almoxarifado_id}"


def _nomes_almoxarifados(ids):
    """`{id: nome}` de uma lista de almoxarifados, numa consulta só."""
    try:
        distintos = sorted({int(i) for i in (ids or []) if i})
    except (TypeError, ValueError):
        return {}
    if not distintos:
        return {}
    marcadores = ",".join(["?"] * len(distintos))
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(f"SELECT id, nome FROM tb_estoque_almoxarifado "
                    f"WHERE id IN ({marcadores})", tuple(distintos))
        return {int(linha[0]): linha[1] for linha in cur.fetchall()}
    except Exception:
        _log().exception("_nomes_almoxarifados falhou")
        return {}
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def listar_itens(almoxarifado_id=None, apenas_com_saldo=False, termo="",
                 incluir_inativos=False):
    """Itens do catálogo com o que está DISPONÍVEL em cada almoxarifado.

    Cada item vem com `saldos` (`{id_do_almoxarifado: quantidade}`) e
    `disponivel_no_almoxarifado` quando o filtro é de um almoxarifado só — é o
    número que a transferência de hoje precisa mostrar.
    """
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        sql = "SELECT " + ", ".join(_NOMES_CAMPOS["item"]) + \
              " FROM tb_estoque_item WHERE 1=1"
        params = []
        if not incluir_inativos:
            sql += " AND ativo=1"
        if termo:
            sql += " AND descricao LIKE ?"
            params.append(f"%{termo}%")
        sql += " ORDER BY descricao ASC, numero ASC"
        cur.execute(sql, params)
        itens = [_para_dict(_NOMES_CAMPOS["item"], linha) for linha in cur.fetchall()]
        if not itens:
            return []
        saldos = {}
        ids = [item["id"] for item in itens]
        for bloco in range(0, len(ids), 400):
            parte = ids[bloco:bloco + 400]
            marcadores = ",".join(["?"] * len(parte))
            cur.execute(f"SELECT item_id, almoxarifado_id, quantidade "
                        f"FROM tb_estoque_saldo WHERE item_id IN ({marcadores})",
                        tuple(parte))
            for linha in cur.fetchall():
                saldos.setdefault(int(linha[0]), {})[int(linha[1])] = _arred(linha[2])
        for item in itens:
            do_item = saldos.get(item["id"], {})
            item["saldos"] = do_item
            item["disponivel_total"] = _arred(sum(do_item.values()))
            if almoxarifado_id:
                item["disponivel_no_almoxarifado"] = _arred(
                    do_item.get(int(almoxarifado_id), 0.0))
            else:
                item["disponivel_no_almoxarifado"] = item["disponivel_total"]
            if apenas_com_saldo and item["disponivel_total"] <= 0:
                continue
        return itens
    except Exception:
        _log().exception("listar_itens falhou")
        return []
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def listar_itens_disponiveis(almoxarifado_id, termo=""):
    """Itens com saldo POSITIVO naquele almoxarifado — o que dá para mandar."""
    try:
        return [item for item in listar_itens(almoxarifado_id=almoxarifado_id,
                                              termo=termo)
                if _arred(item.get("disponivel_no_almoxarifado", 0)) > 0]
    except Exception:
        _log().exception("listar_itens_disponiveis falhou")
        return []


def _buscar_item_igual(cur, descricao, unidade_medida=""):
    """Item do catálogo com a MESMA descrição normalizada (qualquer almoxarifado).

    É o que faz "Resma A4" ser o mesmo material em toda a prefeitura: a
    transferência não cria um item novo, ela muda de QUEM TEM QUANTO — o
    catálogo é um só, com o mesmo número.

    A comparação é feita em Python de propósito: "Resma A4", "resma  a4" e
    "Resma-A4" são o mesmo material, e normalizar isso em SQL exigiria uma
    coluna extra que ninguém manteria. O catálogo de um município tem centenas
    de itens, não milhões — a varredura aqui é barata e a resposta é certa.
    """
    alvo = _norm(descricao)
    if not alvo:
        return None
    try:
        cur.execute("SELECT " + ", ".join(_NOMES_CAMPOS["item"]) +
                    " FROM tb_estoque_item WHERE ativo=1 ORDER BY id ASC")
        for linha in cur.fetchall():
            item = _para_dict(_NOMES_CAMPOS["item"], linha)
            if _norm(item["descricao"]) != alvo:
                continue
            if unidade_medida and (item["unidade_medida"] or "").upper() \
                    != unidade_medida.upper():
                continue
            return item
        return None
    except Exception:
        _log().exception("_buscar_item_igual falhou")
        raise


def _baixar_saldo(cur, item_id, almoxarifado_id, quantidade, agora):
    """Tira do saldo; devolve o que está disponível. Recusa estoque negativo.

    O `WHERE quantidade >= ?` faz a conferência NA MESMA INSTRUÇÃO que baixa: dois
    servidores clicando em "transferir" ao mesmo tempo não conseguem deixar o
    saldo negativo entre os dois. Devolve `(ok, disponivel_antes)`.
    """
    try:
        cur.execute("SELECT quantidade FROM tb_estoque_saldo "
                    "WHERE item_id=? AND almoxarifado_id=?",
                    (int(item_id), int(almoxarifado_id)))
        linha = cur.fetchone()
        disponivel = _arred(linha[0]) if linha else 0.0
        cur.execute("UPDATE tb_estoque_saldo SET quantidade=quantidade-?, "
                    "atualizado_em=? WHERE item_id=? AND almoxarifado_id=? "
                    "AND quantidade>=?",
                    (_arred(quantidade), agora, int(item_id), int(almoxarifado_id),
                     _arred(quantidade)))
        if cur.rowcount:
            return (True, disponivel)
        return (False, disponivel)
    except Exception:
        _log().exception("_baixar_saldo falhou")
        raise


def _somar_saldo(cur, item_id, almoxarifado_id, quantidade, agora):
    """Põe no saldo do almoxarifado, criando a linha se ainda não existir."""
    try:
        cur.execute("INSERT OR IGNORE INTO tb_estoque_saldo "
                    "(item_id, almoxarifado_id, quantidade, atualizado_em) "
                    "VALUES (?, ?, 0, ?)",
                    (int(item_id), int(almoxarifado_id), agora))
        cur.execute("UPDATE tb_estoque_saldo SET quantidade=quantidade+?, "
                    "atualizado_em=? WHERE item_id=? AND almoxarifado_id=?",
                    (_arred(quantidade), agora, int(item_id), int(almoxarifado_id)))
        return True
    except Exception:
        _log().exception("_somar_saldo falhou")
        raise


def _abrir_documento(cur, almoxarifado, tipo, destino_id, data_documento,
                     responsavel, ator, observacao):
    """Cria o documento numerado NA TRANSAÇÃO do chamador e devolve (id, numero).

    O número do documento sai do contador de DOCUMENTO do almoxarifado — uma
    contagem separada da do item, porque `IT-0001` e `DOC-0001` não são a mesma
    coisa e comparar os dois não diz nada."""
    sequencial = _reservar_numero(cur, almoxarifado["id"], "documento")
    numero = montar_numero(almoxarifado.get("prefixo_documento") or "DOC",
                           sequencial, almoxarifado.get("digitos_numero"))
    agora = _agora()
    cur.execute(
        "INSERT INTO tb_estoque_documento "
        "(numero_sequencial, numero, tipo, almoxarifado_id, "
        " almoxarifado_destino_id, data_documento, responsavel_user_nome, "
        " criado_por, criado_em, observacao) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (sequencial, numero, tipo, int(almoxarifado["id"]),
         int(destino_id) if destino_id else None,
         data_documento or _hoje(), responsavel or "", ator or "", agora,
         (observacao or "").strip()))
    return (int(cur.lastrowid), numero)


def _lancar_movimento(cur, documento_id, documento_numero, tipo, item,
                      origem_id, destino_id, quantidade, data_movimento,
                      origem="", nota_empenho="", responsavel="", ator="",
                      observacao=""):
    """Grava UMA linha de movimentação, na transação de quem chamou.

    Não commita: o movimento entra junto com a mudança que ele descreve — ou
    entra junto do rollback dela, que é o comportamento honesto."""
    try:
        agora = _agora()
        cur.execute(
            "INSERT INTO tb_estoque_movimento "
            "(documento_id, documento_numero, tipo, item_id, item_numero, "
            " descricao, unidade_medida, almoxarifado_origem_id, "
            " almoxarifado_destino_id, quantidade, data_movimento, origem, "
            " nota_empenho, responsavel_user_nome, usuario_actor, criado_em, "
            " observacao) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (int(documento_id) if documento_id else None, documento_numero or "",
             tipo, int(item["id"]), item.get("numero") or "", item["descricao"],
             item.get("unidade_medida") or "", int(origem_id) if origem_id else None,
             int(destino_id) if destino_id else None, _arred(quantidade),
             data_movimento or _hoje(), origem or "", nota_empenho or "",
             responsavel or "", ator or "", agora, (observacao or "").strip()))
        return True
    except Exception:
        _log().exception(f"_lancar_movimento({tipo}) falhou")
        return False


# ============ entrada no estoque central ============

def registrar_entrada(descricao, quantidade, unidade_medida="UN",
                      almoxarifado_id=None, data_entrada="", origem="",
                      nota_empenho="", responsavel_user_nome="", observacao="",
                      ator="", eh_admin_geral=False):
    """Registra a ENTRADA de material no almoxarifado (por padrão, o central).

    É por aqui que tudo entra: compra, nota de empenho, empenho, doação. Se o
    item ainda não existe no catálogo, ele é cadastrado agora — com o número
    do almoxarifado — e a quantidade entra junto. Se já existe, a quantidade
    SOMA: o mesmo material continua com o mesmo número.

    Returns:
        tuple: (ok, mensagem)
    """
    ultimo_erro = None
    for tentativa in range(1, TENTATIVAS_LOCKED + 1):
        conn = None
        try:
            nome = (descricao or "").strip()
            qtd = _para_numero(quantidade)
            if not pode_movimentar(ator, eh_admin_geral):
                return (False, "Você só pode consultar o estoque.")
            if len(nome) < 2:
                return (False, "Descreva o item que entrou (mínimo 2 letras).")
            if qtd <= 0:
                return (False, "Informe a quantidade que entrou (maior que zero).")
            if not almoxarifado_id:
                central = garantir_estoque_central()
                if not central:
                    return (False, "Estoque central indisponível.")
                almoxarifado_id = central["id"]
            almoxarifado = obter_almoxarifado(almoxarifado_id)
            if not almoxarifado:
                return (False, "Almoxarifado não encontrado.")
            if not almoxarifado.get("ativo"):
                return (False, f"O almoxarifado {almoxarifado['nome']} está desativado.")
            if almoxarifado.get("bloqueado"):
                return (False, f"O almoxarifado {almoxarifado['nome']} está "
                               "bloqueado para movimentação.")
            unidade = (unidade_medida or "UN").strip().upper()[:8] or "UN"
            tipo_origem = (origem or "").strip()
            if tipo_origem and tipo_origem not in ORIGENS_ENTRADA:
                tipo_origem = "outro"
            data = _normalizar_data(data_entrada) or _hoje()
            nome_resp, _unidade_resp = _ficha_do_servidor(responsavel_user_nome)

            conn = get_connection()
            cur = conn.cursor()
            agora = _agora()
            item = _buscar_item_igual(cur, nome, unidade)
            if item is None:
                sequencial = _reservar_numero(cur, almoxarifado_id, "item")
                numero_item = montar_numero(almoxarifado.get("prefixo_item") or "IT",
                                            sequencial,
                                            almoxarifado.get("digitos_numero"))
                cur.execute(
                    "INSERT INTO tb_estoque_item "
                    "(almoxarifado_id, numero_sequencial, numero, descricao, "
                    " unidade_medida, origem_padrao, ativo, criado_por, "
                    " criado_em, atualizado_em) "
                    "VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?)",
                    (int(almoxarifado_id), sequencial, numero_item, nome, unidade,
                     tipo_origem, ator or "", agora, agora))
                item = {"id": int(cur.lastrowid), "numero": numero_item,
                        "descricao": nome, "unidade_medida": unidade}
                _zerar_saldo(cur, item["id"], almoxarifado_id, agora)
            else:
                cur.execute("UPDATE tb_estoque_item SET atualizado_em=? WHERE id=?",
                            (agora, item["id"]))
            documento_id, numero_doc = _abrir_documento(
                cur, almoxarifado, "entrada", None, data, nome_resp, ator,
                observacao or f"Entrada de {nome}")
            _somar_saldo(cur, item["id"], almoxarifado_id, qtd, agora)
            _lancar_movimento(cur, documento_id, numero_doc, "entrada", item,
                              None, almoxarifado_id, qtd, data, tipo_origem,
                              nota_empenho, nome_resp, ator, observacao)
            _commit_com_retry(conn, contexto=f"registrar_entrada:{almoxarifado_id}")
            _auditar(ator, "registrar_entrada", f"item {item['numero']}",
                     f"quantidade={qtd:g} almoxarifado={almoxarifado['nome']} "
                     f"documento={numero_doc} origem={tipo_origem or '-'}")
            return (True, f"Entrada registrada: {qtd:g} {unidade} de {nome} "
                          f"({item['numero']}) em {almoxarifado['nome']}. "
                          f"Documento {numero_doc}.")
        except Exception as exc:
            ultimo_erro = exc
            _rollback_seguro(conn, contexto="registrar_entrada")
            if _eh_bloqueio_banco(exc) and tentativa < TENTATIVAS_LOCKED:
                try:
                    _log().warning("registrar_entrada: almoxarifado ocupado, "
                                   f"tentativa {tentativa}/{TENTATIVAS_LOCKED}")
                except Exception:
                    pass
                try:
                    time.sleep(ESPERA_LOCKED_SEG * tentativa)
                except Exception:
                    pass
                continue
            try:
                _log().exception("registrar_entrada falhou")
            except Exception:
                pass
            return (False, "Erro ao registrar a entrada.")
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
    try:
        _log().error(f"registrar_entrada: almoxarifado travado após "
                     f"{TENTATIVAS_LOCKED} tentativas ({ultimo_erro})")
    except Exception:
        pass
    return (False, "O almoxarifado está muito movimentado. Tente de novo.")


# ============ transferência e devolução ============

def transferir(item_id, quantidade, almoxarifado_destino_id,
               almoxarifado_origem_id=None, data_movimento="", responsavel="",
               observacao="", ator="", eh_admin_geral=False):
    """Transfere material de um almoxarifado para outro (GERA DOCUMENTO DE SAÍDA).

    Serve para os dois movimentos do dia a dia:
      - CENTRAL → almoxarifado de secretaria: é a distribuição;
      - almoxarifado → almoxarifado: é a Empréstimo entre setores.

    ESTOQUE NEGATIVO É PROIBIDO: quando a quantidade pedida passaria do que
    existe, a transferência é recusada e a mensagem diz quanto tem. A
    conferência é feita no próprio `UPDATE` do saldo (com `quantidade >= ?`),
    então dois servidores clicando ao mesmo tempo não conseguem furar.

    Returns:
        tuple: (ok, mensagem, numero_documento ou '')
    """
    ultimo_erro = None
    for tentativa in range(1, TENTATIVAS_LOCKED + 1):
        conn = None
        try:
            qtd = _para_numero(quantidade)
            if not pode_movimentar(ator, eh_admin_geral):
                return (False, "Você só pode consultar o estoque.", "")
            if qtd <= 0:
                return (False, "Informe a quantidade a transferir (maior que zero).", "")
            item = obter_item(item_id)
            if not item:
                return (False, "Item não encontrado.", "")
            if not item.get("ativo"):
                return (False, "Este item está desativado.", "")
            if not almoxarifado_origem_id:
                return (False, "Escolha o almoxarifado de ORIGEM.", "")
            origem = obter_almoxarifado(almoxarifado_origem_id)
            if not origem:
                return (False, "Almoxarifado de origem não encontrado.", "")
            destino = obter_almoxarifado(almoxarifado_destino_id)
            if not destino:
                return (False, "Almoxarifado de destino não encontrado.", "")
            if int(origem["id"]) == int(destino["id"]):
                return (False, "Origem e destino são o mesmo almoxarifado.", "")
            if not destino.get("ativo"):
                return (False, f"O almoxarifado {destino['nome']} está desativado.")
            if destino.get("bloqueado"):
                return (False, f"O almoxarifado {destino['nome']} está bloqueado "
                               "para recebimento.")
            if origem.get("bloqueado"):
                return (False, f"O almoxarifado {origem['nome']} está bloqueado "
                               "para movimentação.")
            data = _normalizar_data(data_movimento) or _hoje()
            nome_resp = _ficha_do_servidor(responsavel)[0]

            conn = get_connection()
            cur = conn.cursor()
            agora = _agora()
            _zerar_saldo(cur, item["id"], origem["id"], agora)
            baixou, tinha = _baixar_saldo(cur, item["id"], origem["id"], qtd, agora)
            if not baixou:
                _rollback_seguro(conn, contexto="transferir:negativo")
                return (False, f"Não há {qtd:g} {item['unidade_medida']} de "
                               f"“{item['descricao']}” em {origem['nome']}: "
                               f"o disponível é {tinha:g}. "
                               f"A transferência foi recusada para o estoque "
                               f"não ficar negativo.", "")
            documento_id, numero_doc = _abrir_documento(
                cur, origem, "transferencia", destino["id"], data, nome_resp,
                ator, observacao or f"Transferência para {destino['nome']}")
            _somar_saldo(cur, item["id"], destino["id"], qtd, agora)
            _lancar_movimento(cur, documento_id, numero_doc, "saida", item,
                              origem["id"], destino["id"], qtd, data, "",
                              "", nome_resp, ator, observacao)
            _lancar_movimento(cur, documento_id, numero_doc, "entrada", item,
                              origem["id"], destino["id"], qtd, data, "",
                              "", nome_resp, ator,
                              f"Recebido de {origem['nome']}")
            _commit_com_retry(conn, contexto=f"transferir:{origem['id']}")
            _auditar(ator, "transferir", f"item {item['numero']}",
                     f"quantidade={qtd:g} de={origem['nome']} para={destino['nome']} "
                     f"documento={numero_doc}")
            return (True, f"Transferência concluída: {qtd:g} {item['unidade_medida']} "
                          f"de “{item['descricao']}” de {origem['nome']} para "
                          f"{destino['nome']}. Documento de saída {numero_doc}.",
                numero_doc)
        except Exception as exc:
            ultimo_erro = exc
            _rollback_seguro(conn, contexto="transferir")
            if _eh_bloqueio_banco(exc) and tentativa < TENTATIVAS_LOCKED:
                try:
                    _log().warning("transferir: almoxarifado ocupado, "
                                   f"tentativa {tentativa}/{TENTATIVAS_LOCKED}")
                except Exception:
                    pass
                try:
                    time.sleep(ESPERA_LOCKED_SEG * tentativa)
                except Exception:
                    pass
                continue
            try:
                _log().exception("transferir falhou")
            except Exception:
                pass
            return (False, "Erro ao transferir o material.", "")
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
    try:
        _log().error(f"transferir: almoxarifado travado após "
                     f"{TENTATIVAS_LOCKED} tentativas ({ultimo_erro})")
    except Exception:
        pass
    return (False, "O almoxarifado está muito movimentado. Tente de novo.", "")


def devolver(almoxarifado_origem_id, quantidade, item_id,
             almoxarifado_destino_id=None, data_movimento="", responsavel="",
             observacao="", ator="", eh_admin_geral=False):
    """DEVOLVE material ao estoque, normalmente do almoxarifado para o CENTRAL.

    A devolução é a transferência com o sentido invertido e o nome certo: o
    almoxarifado da secretaria manda de volta o que sobrou, e o item VOLTA a
    ficar DISPONÍVEL no destino. É a operação que evita transformar sobra em
    perda — e por isso ela não pode ficar escondida dentro de "transferir":
    quem devolve precisa ver na tela que está devolvendo.

    Returns:
        tuple: (ok, mensagem, numero_documento ou '')
    """
    try:
        destino_id = almoxarifado_destino_id
        destino_nome = ""
        if not destino_id:
            central = garantir_estoque_central()
            if not central:
                return (False, "Estoque central indisponível.", "")
            destino_id = central["id"]
        destino_nome = (obter_almoxarifado(destino_id) or {}).get("nome", "")
        ok, mensagem, numero = transferir(
            item_id, quantidade, destino_id, almoxarifado_origem_id,
            data_movimento=data_movimento, responsavel=responsavel,
            observacao=observacao or "Devolução ao estoque",
            ator=ator, eh_admin_geral=eh_admin_geral)
        if not ok:
            return (False, mensagem, numero)
        return (True, f"Devolução registrada. {mensagem} "
                      f"O item voltou a ficar disponível em {destino_nome}.",
                numero)
    except Exception:
        _log().exception("devolver falhou")
        return (False, "Erro ao registrar a devolução.", "")


def _com_item_para_movimento(cur, item_id, descricao=""):
    """Item do catálogo: o `item_id` quando vem, o de mesma descrição quando não.

    Devolve `(ok, item, mensagem)`. É o atalho da tela: o servidor escolhe pelo
    item já cadastrado, e o módulo descobre o material pelo nome quando o
    cadastro não tem id gravado."""
    try:
        if item_id:
            cur.execute("SELECT " + ", ".join(_NOMES_CAMPOS["item"]) +
                        " FROM tb_estoque_item WHERE id=?", (int(item_id),))
            item = _para_dict(_NOMES_CAMPOS["item"], cur.fetchone())
            if not item:
                return (False, None, "Item não encontrado.")
            return (True, item, "")
        nome = (descricao or "").strip()
        if len(nome) < 2:
            return (False, None, "Escolha o item do estoque.")
        achado = _buscar_item_igual(cur, nome)
        if not achado:
            return (False, None, f"O item “{nome}” não está no catálogo. "
                                 f"Cadastre-o antes de movimentar.")
        return (True, achado, "")
    except Exception:
        _log().exception("_com_item_para_movimento falhou")
        raise


# ============ entrega para a sala (o que está EM USO) ============

def entregar_item(quantidade, almoxarifado_id, destino_sala,
                  destino_departamento="", responsavel_user_nome="",
                  data_entrega="", item_id=None, descricao="",
                  observacao="", ator="", eh_admin_geral=False):
    """Entrega material do almoxarifado a uma SALA e ele passa a contar como EM USO.

    A entrega tem DESTINO (sala, departamento, responsável) e DATA. Sem os dois
    o número "em uso" não é número, é chute: não se sabe de onde saiu nem há
    quanto tempo está fora.

    A quantidade sai do DISPONÍVEL do almoxarifado e entra na entrega. Ficar
    parado na sala é o que o painel marca depois de N dias — é o indicador de
    desperdício, e é o que dispara o pedido de recolhimento.

    Returns:
        tuple: (ok, mensagem)
    """
    ultimo_erro = None
    for tentativa in range(1, TENTATIVAS_LOCKED + 1):
        conn = None
        try:
            qtd = _para_numero(quantidade)
            sala = (destino_sala or "").strip()
            if not pode_movimentar(ator, eh_admin_geral):
                return (False, "Você só pode consultar o estoque.")
            if qtd <= 0:
                return (False, "Informe a quantidade entregue (maior que zero).")
            if len(sala) < 2:
                return (False, "Informe a sala de destino (mínimo 2 letras).")
            almoxarifado = obter_almoxarifado(almoxarifado_id)
            if not almoxarifado:
                return (False, "Almoxarifado não encontrado.")
            if not almoxarifado.get("ativo"):
                return (False, f"O almoxarifado {almoxarifado['nome']} está desativado.")
            if almoxarifado.get("bloqueado"):
                return (False, f"O almoxarifado {almoxarifado['nome']} está "
                               "bloqueado para movimentação.")
            data = _normalizar_data(data_entrega) or _hoje()
            nome_resp, _unidade_resp = _ficha_do_servidor(responsavel_user_nome)

            conn = get_connection()
            cur = conn.cursor()
            tem_item, item, msg = _com_item_para_movimento(cur, item_id, descricao)
            if not tem_item:
                _rollback_seguro(conn, contexto="entregar_item")
                return (False, msg)
            agora = _agora()
            _zerar_saldo(cur, item["id"], almoxarifado["id"], agora)
            baixou, tinha = _baixar_saldo(cur, item["id"], almoxarifado["id"],
                                          qtd, agora)
            if not baixou:
                _rollback_seguro(conn, contexto="entregar_item:negativo")
                return (False, f"Não há {qtd:g} {item['unidade_medida']} de "
                               f"“{item['descricao']}” disponíveis em "
                               f"{almoxarifado['nome']}: o disponível é "
                               f"{tinha:g}. A entrega foi recusada.", )
            documento_id, numero_doc = _abrir_documento(
                cur, almoxarifado, "transferencia", None, data, nome_resp, ator,
                observacao or f"Entrega para {sala}")
            cur.execute(
                "INSERT INTO tb_estoque_entrega "
                "(item_id, item_numero, descricao, unidade_medida, "
                " almoxarifado_id, quantidade, destino_sala, destino_departamento, "
                " responsavel_user_nome, responsavel_nome, data_entrega, "
                " data_baixa, situacao, documento_id, criado_por, criado_em, "
                " atualizado_em) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '', 'em_uso', ?, ?, ?, ?)",
                (int(item["id"]), item["numero"], item["descricao"],
                 item["unidade_medida"], int(almoxarifado["id"]), qtd, sala,
                 (destino_departamento or "").strip(), responsavel_user_nome or "",
                 nome_resp, data, documento_id, ator or "", agora, agora))
            _lancar_movimento(cur, documento_id, numero_doc, "saida", item,
                              almoxarifado["id"], None, qtd, data, "uso",
                              "", nome_resp, ator,
                              f"Entregue em {sala}"
                              + (f" ({destino_departamento})"
                                 if (destino_departamento or "").strip() else ""))
            _commit_com_retry(conn, contexto=f"entregar_item:{almoxarifado['id']}")
            _auditar(ator, "entregar_item", f"item {item['numero']}",
                     f"quantidade={qtd:g} sala={sala} "
                     f"almoxarifado={almoxarifado['nome']} documento={numero_doc}")
            return (True, f"{qtd:g} {item['unidade_medida']} de "
                          f"“{item['descricao']}” entregue em {sala}. "
                          f"Agora está EM USO e o painel passa a contar os "
                          f"dias parado. Documento {numero_doc}.")
        except Exception as exc:
            ultimo_erro = exc
            _rollback_seguro(conn, contexto="entregar_item")
            if _eh_bloqueio_banco(exc) and tentativa < TENTATIVAS_LOCKED:
                try:
                    _log().warning("entregar_item: almoxarifado ocupado, "
                                   f"tentativa {tentativa}/{TENTATIVAS_LOCKED}")
                except Exception:
                    pass
                try:
                    time.sleep(ESPERA_LOCKED_SEG * tentativa)
                except Exception:
                    pass
                continue
            try:
                _log().exception("entregar_item falhou")
            except Exception:
                pass
            return (False, "Erro ao registrar a entrega.")
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
    try:
        _log().error(f"entregar_item: almoxarifado travado após "
                     f"{TENTATIVAS_LOCKED} tentativas ({ultimo_erro})")
    except Exception:
        pass
    return (False, "O almoxarifado está muito movimentado. Tente de novo.")


def listar_entregas(almoxarifado_id=None, situacao="em_uso", apenas_parados=False,
                    dias=None):
    """O que está EM USO: entregas com destino, data e quantos dias estão paradas.

    `apenas_parados=True` devolve só o que está sem baixa há mais de N dias
    (padrão `dias_parado()`), que é o indicador de desperdício."""
    conn = None
    try:
        limite = validar_dias(dias)
        conn = get_connection()
        cur = conn.cursor()
        sql = "SELECT " + ", ".join(_NOMES_CAMPOS["entrega"]) + \
              " FROM tb_estoque_entrega WHERE 1=1"
        params = []
        if almoxarifado_id:
            sql += " AND almoxarifado_id=?"
            params.append(int(almoxarifado_id))
        if situacao:
            sql += " AND situacao=?"
            params.append(situacao)
        sql += " ORDER BY data_entrega ASC, id ASC"
        cur.execute(sql, params)
        entregas = [_para_dict(_NOMES_CAMPOS["entrega"], linha)
                    for linha in cur.fetchall()]
        nomes = _nomes_almoxarifados([e["almoxarifado_id"] for e in entregas])
        for entrega in entregas:
            entrega["almoxarifado_nome"] = nomes.get(entrega["almoxarifado_id"], "")
            entrega["dias_parado"] = _dias_ate(entrega["data_entrega"])
            entrega["parado"] = (entrega["situacao"] == "em_uso"
                                 and entrega["dias_parado"] >= limite)
        if apenas_parados:
            entregas = [e for e in entregas if e["parado"]]
        return entregas
    except Exception:
        _log().exception("listar_entregas falhou")
        return []
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def obter_entrega(entrega_id):
    """Dados de uma entrega por id, ou None."""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT " + ", ".join(_NOMES_CAMPOS["entrega"]) +
                    " FROM tb_estoque_entrega WHERE id=?", (int(entrega_id),))
        return _para_dict(_NOMES_CAMPOS["entrega"], cur.fetchone())
    except Exception:
        _log().exception("obter_entrega falhou")
        return None
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def dar_baixa_entrega(entrega_id, quantidade, devolver_ao_almoxarifado=True,
                      data_baixa="", observacao="", ator="", eh_admin_geral=False):
    """Dá BAIXA numa entrega: o material volta ao disponível OU foi consumido.

    `devolver_ao_almoxarifado=True` devolve a quantidade ao DISPONÍVEL do
    almoxarifado (é a devolução por não uso — o que evita o desperdício).
    `False` marca como CONSUMIDO: saiu da sala e não volta mais.

    A baixa é sempre um evento: quem pegou o material depois precisa saber
    que ele voltou (ou que foi consumido).

    Returns:
        tuple: (ok, mensagem)
    """
    ultimo_erro = None
    for tentativa in range(1, TENTATIVAS_LOCKED + 1):
        conn = None
        try:
            qtd = _para_numero(quantidade)
            if not pode_movimentar(ator, eh_admin_geral):
                return (False, "Você só pode consultar o estoque.")
            if qtd <= 0:
                return (False, "Informe a quantidade da baixa (maior que zero).")
            entrega = obter_entrega(entrega_id)
            if not entrega:
                return (False, "Entrega não encontrada.")
            if entrega["situacao"] != "em_uso":
                return (False, f"Esta entrega já foi baixada como "
                               f"{entrega['situacao']}.")
            if qtd > _arred(entrega["quantidade"]):
                return (False, f"A entrega tem {_arred(entrega['quantidade']):g} "
                               f"{entrega['unidade_medida']}, e a baixa pede "
                               f"{qtd:g}. A baixa foi recusada.")
            almoxarifado = obter_almoxarifado(entrega["almoxarifado_id"]) or {}
            data = _normalizar_data(data_baixa) or _hoje()
            agora = _agora()
            item = obter_item(entrega["item_id"]) or {
                "id": entrega["item_id"], "numero": entrega["item_numero"],
                "descricao": entrega["descricao"],
                "unidade_medida": entrega["unidade_medida"]}

            conn = get_connection()
            cur = conn.cursor()
            documento_id = entrega.get("documento_id")
            documento_numero = ""
            if documento_id:
                cur.execute("SELECT numero FROM tb_estoque_documento WHERE id=?",
                            (int(documento_id),))
                linha = cur.fetchone()
                documento_numero = linha[0] if linha else ""
            novo = _arred(entrega["quantidade"]) - qtd
            situacao = "recolhido" if novo <= 0 else "em_uso"
            cur.execute("UPDATE tb_estoque_entrega SET quantidade=?, situacao=?, "
                        "data_baixa=?, atualizado_em=? WHERE id=?",
                        (novo, situacao, data if novo <= 0 else "", agora,
                         int(entrega_id)))
            if devolver_ao_almoxarifado:
                _somar_saldo(cur, entrega["item_id"], almoxarifado.get("id"),
                             qtd, agora)
                _lancar_movimento(cur, documento_id, documento_numero,
                                  "devolucao", item, None,
                                  almoxarifado.get("id"), qtd, data, "devolucao",
                                  "", "", ator,
                                  f"Voltou de {entrega['destino_sala']}")
                texto = (f"{qtd:g} {item['unidade_medida']} de "
                         f"“{item['descricao']}” voltaram para o disponível de "
                         f"{almoxarifado.get('nome', 'almoxarifado')}")
            else:
                _lancar_movimento(cur, documento_id, documento_numero, "baixa",
                                  item, almoxarifado.get("id"), None, qtd, data,
                                  "consumo", "", "", ator,
                                  f"Consumido em {entrega['destino_sala']}")
                texto = (f"{qtd:g} {item['unidade_medida']} de "
                         f"“{item['descricao']}” marcados como consumidos")
            if novo <= 0:
                texto += f". A entrega para {entrega['destino_sala']} foi encerrada"
            _commit_com_retry(conn, contexto=f"dar_baixa_entrega:{entrega_id}")
            _auditar(ator, "dar_baixa_entrega", f"entrega {entrega_id}",
                     f"quantidade={qtd:g} devolver={bool(devolver_ao_almoxarifado)} "
                     f"sala={entrega['destino_sala']}")
            return (True, texto + ".")
        except Exception as exc:
            ultimo_erro = exc
            _rollback_seguro(conn, contexto="dar_baixa_entrega")
            if _eh_bloqueio_banco(exc) and tentativa < TENTATIVAS_LOCKED:
                try:
                    _log().warning("dar_baixa_entrega: entrega ocupada, "
                                   f"tentativa {tentativa}/{TENTATIVAS_LOCKED}")
                except Exception:
                    pass
                try:
                    time.sleep(ESPERA_LOCKED_SEG * tentativa)
                except Exception:
                    pass
                continue
            try:
                _log().exception("dar_baixa_entrega falhou")
            except Exception:
                pass
            return (False, "Erro ao dar baixa na entrega.")
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
    try:
        _log().error(f"dar_baixa_entrega: travado após {TENTATIVAS_LOCKED} "
                     f"tentativas ({ultimo_erro})")
    except Exception:
        pass
    return (False, "O estoque está muito movimentado. Tente de novo.")


# ============ pedido de recolhimento (o ponto que evita desperdício) ============

def abrir_pedido_recolhimento(almoxarifado_id, item_id, quantidade,
                              tipo_pedido="recolhimento", destino_sala="",
                              motivo="", solicitante_user_nome="", ator="",
                              eh_admin_geral=False):
    """Abre o PEDIDO DE RECOLHIMENTO do que foi entregue e não foi usado.

    Quem abre pode ser o almoxarifado da secretaria (recolhimento: o central
    recolhe da sala) OU quem está com o item parado (devolução por não uso) —
    é o mesmo pedido, muda quem pede. O CENTRAL é quem atende: recolhe e
    devolve a quantidade ao DISPONÍVEL da secretaria.

    A quantidade não pode ser maior do que a entrega em aberto: o pedido
    aponta para a entrega, não para o item inteiro.

    Returns:
        tuple: (ok, mensagem, pedido_id ou None)
    """
    try:
        qtd = _para_numero(quantidade)
        solicitante = (solicitante_user_nome or ator or "").strip()
        if not pode_consultar(solicitante, eh_admin_geral) \
                and not pode_consultar(ator, eh_admin_geral):
            return (False, "Servidor sem vínculo com o módulo de estoque.", None)
        if qtd <= 0:
            return (False, "Informe a quantidade a recolher (maior que zero).", None)
        tipo = (tipo_pedido or "recolhimento").strip()
        if tipo not in TIPOS_RECOLHIMENTO:
            tipo = "recolhimento"
        almoxarifado = obter_almoxarifado(almoxarifado_id)
        if not almoxarifado:
            return (False, "Almoxarifado não encontrado.", None)
        item = obter_item(item_id)
        if not item:
            return (False, "Item não encontrado.", None)
        # a entrega em aberto é a origem do pedido: o que está em uso na sala
        entregas = [e for e in listar_entregas(almoxarifado_id=almoxarifado["id"])
                    if e["item_id"] == item["id"] and e["situacao"] == "em_uso"]
        if not entregas:
            return (False, f"Não há entrega em aberto de “{item['descricao']}” "
                           f"neste almoxarifado. Nada a recolher.", None)
        em_aberto = sum(_arred(e["quantidade"]) for e in entregas)
        if qtd > em_aberto:
            return (False, f"Só há {em_aberto:g} {item['unidade_medida']} de "
                           f"“{item['descricao']}” em uso. O pedido foi recusado.", None)
        entrega = entregas[0]
        nome_solicitante, _unidade = _ficha_do_servidor(solicitante)
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO tb_estoque_recolhimento "
            "(almoxarifado_id, item_id, entrega_id, tipo_pedido, quantidade, "
            " destino_sala, solicitante_user_nome, solicitante_nome, motivo, "
            " situacao, data_abertura) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'aberto', ?)",
            (int(almoxarifado["id"]), int(item["id"]), int(entrega["id"]), tipo,
             qtd, (destino_sala or "").strip() or entrega["destino_sala"],
             solicitante, nome_solicitante, (motivo or "").strip(), _agora()))
        pedido_id = int(cur.lastrowid)
        _commit_com_retry(conn, contexto="abrir_pedido_recolhimento")
        _auditar(ator or solicitante, "abrir_pedido_recolhimento",
                 f"pedido {pedido_id}",
                 f"item={item['numero']} quantidade={qtd:g} tipo={tipo} "
                 f"almoxarifado={almoxarifado['nome']}")
        return (True, f"Pedido de recolhimento {tipo} aberto: {qtd:g} "
                      f"{item['unidade_medida']} de “{item['descricao']}” de "
                      f"{entrega['destino_sala']}. O central atende e devolve "
                      f"ao disponível.", pedido_id)
    except Exception:
        _log().exception("abrir_pedido_recolhimento falhou")
        return (False, "Erro ao abrir o pedido de recolhimento.", None)


def pode_atender_recolhimento(user_nome, almoxarifado_id, eh_admin_geral=False):
    """Verdadeiro quando quem está na tela pode ATENDER o pedido de recolher.

    Atender é ato do CENTRAL (recolhe e devolve ao disponível) ou de quem
    administra o módulo. Quem é só consulta ou opera um almoxarifado que não é
    o da origem não atende pedido de terceiro."""
    try:
        papel = papel_no_estoque(user_nome, eh_admin_geral)
        if papel == PAPEL_ADMINISTRADOR:
            return True
        if papel != PAPEL_OPERADOR:
            return False
        almoxarifado = obter_almoxarifado(almoxarifado_id) or {}
        # o responsável do almoxarifado de origem atende o próprio recolhimento
        if (almoxarifado.get("responsavel_user_nome") or "") == (user_nome or ""):
            return True
        # o operador do CENTRAL é quem recolhe para todos
        return bool(almoxarifado.get("central"))
    except Exception:
        _log().exception("pode_atender_recolhimento falhou")
        return False


def listar_pedidos_recolhimento(situacao="aberto", almoxarifado_id=None,
                                 solicitante=""):
    """Pedidos de recolhimento, dos mais recentes para os mais antigos."""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        sql = "SELECT " + ", ".join(_NOMES_CAMPOS["recolhimento"]) + \
              " FROM tb_estoque_recolhimento WHERE 1=1"
        params = []
        if situacao:
            sql += " AND situacao=?"
            params.append(situacao)
        if almoxarifado_id:
            sql += " AND almoxarifado_id=?"
            params.append(int(almoxarifado_id))
        if solicitante:
            sql += " AND solicitante_user_nome=?"
            params.append(solicitante)
        sql += " ORDER BY id DESC"
        cur.execute(sql, params)
        pedidos = [_para_dict(_NOMES_CAMPOS["recolhimento"], linha)
                   for linha in cur.fetchall()]
        if not pedidos:
            return []
        itens = {}
        ids = sorted({p["item_id"] for p in pedidos})
        if ids:
            marcadores = ",".join(["?"] * len(ids))
            cur.execute(f"SELECT id, numero, descricao, unidade_medida "
                        f"FROM tb_estoque_item WHERE id IN ({marcadores})",
                        tuple(ids))
            itens = {int(linha[0]): {"numero": linha[1], "descricao": linha[2],
                                    "unidade_medida": linha[3]}
                     for linha in cur.fetchall()}
        nomes = _nomes_almoxarifados([p["almoxarifado_id"] for p in pedidos])
        for pedido in pedidos:
            ficha = itens.get(pedido["item_id"], {})
            pedido["item_numero"] = ficha.get("numero", "")
            pedido["item_descricao"] = ficha.get("descricao", "")
            pedido["unidade_medida"] = ficha.get("unidade_medida", "")
            pedido["almoxarifado_nome"] = nomes.get(pedido["almoxarifado_id"], "")
        return pedidos
    except Exception:
        _log().exception("listar_pedidos_recolhimento falhou")
        return []
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def atender_pedido_recolhimento(pedido_id, quantidade=None, parecer="",
                                ator="", eh_admin_geral=False):
    """O CENTRAL atende o pedido: recolhe e devolve ao DISPONÍVEL da secretaria.

    Aceitar o pedido dá baixa na entrega com DEVOLUÇÃO — a quantidade volta
    para o disponível do almoxarifado de origem, e não vai para o central: o
    material está na secretaria, o que falta é o recolhimento. Todo
    recolhimento passa por aceite, gera documento e evento.

    Returns:
        tuple: (ok, mensagem)
    """
    try:
        pedido = None
        for linha in listar_pedidos_recolhimento(situacao=""):
            if int(linha["id"]) == int(pedido_id):
                pedido = linha
                break
        if not pedido:
            return (False, "Pedido de recolhimento não encontrado.")
        if pedido["situacao"] != "aberto":
            return (False, f"Este pedido já foi {pedido['situacao']}.")
        if not pode_atender_recolhimento(ator, pedido["almoxarifado_id"],
                                         eh_admin_geral):
            return (False, "Você não pode atender pedidos de recolhimento. "
                           "O atendimento é do estoque central.")
        qtd = _para_numero(quantidade) if quantidade is not None \
            else _arred(pedido["quantidade"])
        if qtd <= 0:
            return (False, "Informe a quantidade que vai voltar "
                           "(maior que zero).")
        if qtd > _arred(pedido["quantidade"]):
            return (False, f"O pedido é de {_arred(pedido['quantidade']):g} "
                           f"{pedido['unidade_medida']} e o atendimento pede "
                           f"{qtd:g}. O atendimento foi recusado.")
        entrega_id = pedido.get("entrega_id")
        if not entrega_id:
            return (False, "Este pedido não aponta para uma entrega em aberto.")
        ok_baixa, msg_baixa = dar_baixa_entrega(
            entrega_id, qtd, devolver_ao_almoxarifado=True, ator=ator,
            observacao="Recolhimento atendido pelo estoque central",
            eh_admin_geral=eh_admin_geral)
        if not ok_baixa:
            return (False, msg_baixa)
        # A baixa da entrega é a que mexe no ESTOQUE e já foi confirmada; o
        # estado do pedido é bookkeeping e vem logo depois. Se esta gravação
        # falhar, o material voltou ao disponível de qualquer jeito — então a
        # mensagem diz as duas coisas em vez de mentir que deu tudo certo.
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("UPDATE tb_estoque_recolhimento SET situacao='atendido', "
                        "quantidade=?, data_atendimento=?, atendido_por=?, "
                        "parecer=? WHERE id=?",
                        (qtd, _agora(), ator or "", (parecer or "").strip(),
                         int(pedido_id)))
            _commit_com_retry(conn, contexto="atender_pedido_recolhimento")
        except Exception:
            _rollback_seguro(conn, contexto="atender_pedido_recolhimento")
            _log().exception("atender_pedido_recolhimento: pedido {pedido_id} "
                             "atendido no estoque mas estado não gravado")
            return (True, f"{msg_baixa} ATENÇÃO: o material voltou ao "
                          f"disponível, mas o estado do pedido não foi gravado. "
                          f"Fale com o administrador do módulo.")
        _auditar(ator, "atender_pedido_recolhimento", f"pedido {pedido_id}",
                 f"quantidade={qtd:g} item={pedido['item_numero']}")
        return (True, f"Recolhimento atendido: {msg_baixa}")
    except Exception:
        _log().exception("atender_pedido_recolhimento falhou")
        return (False, "Erro ao atender o pedido de recolhimento.")


def recusar_pedido_recolhimento(pedido_id, parecer="", ator="",
                                eh_admin_geral=False):
    """Recusa o pedido de recolhimento. O item continua em uso na sala.

    Returns:
        tuple: (ok, mensagem)
    """
    conn = None
    try:
        pedido = None
        for linha in listar_pedidos_recolhimento(situacao=""):
            if int(linha["id"]) == int(pedido_id):
                pedido = linha
                break
        if not pedido:
            return (False, "Pedido de recolhimento não encontrado.")
        if pedido["situacao"] != "aberto":
            return (False, f"Este pedido já foi {pedido['situacao']}.")
        if not pode_atender_recolhimento(ator, pedido["almoxarifado_id"],
                                         eh_admin_geral):
            return (False, "Você não pode decidir pedidos de recolhimento.")
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE tb_estoque_recolhimento SET situacao='recusado', "
                    "data_atendimento=?, atendido_por=?, parecer=? WHERE id=?",
                    (_agora(), ator or "", (parecer or "").strip(), int(pedido_id)))
        _commit_com_retry(conn, contexto="recusar_pedido_recolhimento")
        _auditar(ator, "recusar_pedido_recolhimento", f"pedido {pedido_id}",
                 f"item={pedido['item_numero']}")
        return (True, "Pedido recusado — o material continua em uso na sala.")
    except Exception:
        _rollback_seguro(conn, contexto="recusar_pedido_recolhimento")
        _log().exception("recusar_pedido_recolhimento falhou")
        return (False, "Erro ao recusar o pedido.")
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


# ============ tarefa de depósito (chamar para tratar o depósito) ============

def criar_tarefa_deposito(titulo, tipo="receber", descricao="",
                         almoxarifado_id=None, responsavel_user_nome="",
                         necessarios_convidados=1, ator="", eh_admin_geral=False):
    """Abre uma TAREFA DE DEPÓSITO: quem pode chamar quem para tratar o depósito.

    A tarefa existe para o responsável de um almoxarifado não fazer sozinho o
    recebimento, a conferência e a inventariagem: ele CHAMA outros servidores
    já cadastrados para a tarefa, com um número de necessários, e o que
    aceita fica na lista. O número da tarefa sai do contador de ITEM do
    almoxarifado (é a identificação do depósito, não um documento de saída).

    Returns:
        tuple: (ok, mensagem, tarefa_id ou None)
    """
    conn = None
    try:
        nome = (titulo or "").strip()
        if not pode_movimentar(ator, eh_admin_geral):
            return (False, "Você só pode consultar o estoque.", None)
        if len(nome) < 3:
            return (False, "Dê um título à tarefa de depósito "
                           "(mínimo 3 letras).", None)
        tipo_tarefa = (tipo or "receber").strip()
        if tipo_tarefa not in TIPOS_TAREFA:
            tipo_tarefa = "receber"
        if not almoxarifado_id:
            central = garantir_estoque_central()
            if not central:
                return (False, "Estoque central indisponível.", None)
            almoxarifado_id = central["id"]
        almoxarifado = obter_almoxarifado(almoxarifado_id)
        if not almoxarifado:
            return (False, "Almoxarifado não encontrado.", None)
        responsavel = (responsavel_user_nome or ator or "").strip()
        nome_resp, _unidade = _ficha_do_servidor(responsavel)
        try:
            necessarios = max(1, int(necessarios_convidados))
        except (TypeError, ValueError):
            necessarios = 1
        necessarios = min(necessarios, 20)

        conn = get_connection()
        cur = conn.cursor()
        sequencial = _reservar_numero(cur, almoxarifado_id, "item")
        numero = montar_numero(almoxarifado.get("prefixo_item") or "IT", sequencial,
                               almoxarifado.get("digitos_numero"))
        cur.execute(
            "INSERT INTO tb_estoque_tarefa "
            "(numero_sequencial, numero, titulo, descricao, tipo, "
            " almoxarifado_id, responsavel_user_nome, responsavel_nome, "
            " atendente_user_nome, necessarios_convidados, situacao, criado_por, "
            " criado_em) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, '', ?, 'aberta', ?, ?)",
            (sequencial, numero, nome, (descricao or "").strip(), tipo_tarefa,
             int(almoxarifado["id"]), responsavel, nome_resp, necessarios,
             ator or "", _agora()))
        tarefa_id = int(cur.lastrowid)
        _commit_com_retry(conn, contexto="criar_tarefa_deposito")
        _auditar(ator, "criar_tarefa_deposito", f"tarefa {numero}",
                 f"tipo={tipo_tarefa} almoxarifado={almoxarifado['nome']} "
                 f"necessarios={necessarios}")
        return (True, f"Tarefa de depósito {numero} aberta: {nome}. "
                      f"Chame {necessarios} servidor(es) para tratar.", tarefa_id)
    except Exception:
        _rollback_seguro(conn, contexto="criar_tarefa_deposito")
        _log().exception("criar_tarefa_deposito falhou")
        return (False, "Erro ao abrir a tarefa de depósito.", None)
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def obter_tarefa(tarefa_id):
    """Dados de uma tarefa de depósito por id, ou None."""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT " + ", ".join(_NOMES_CAMPOS["tarefa"]) +
                    " FROM tb_estoque_tarefa WHERE id=?", (int(tarefa_id),))
        return _para_dict(_NOMES_CAMPOS["tarefa"], cur.fetchone())
    except Exception:
        _log().exception("obter_tarefa falhou")
        return None
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def listar_tarefas(almoxarifado_id=None, situacao=""):
    """Tarefas de depósito, com quantos convidados já aceitaram."""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        sql = "SELECT " + ", ".join(_NOMES_CAMPOS["tarefa"]) + \
              " FROM tb_estoque_tarefa WHERE 1=1"
        params = []
        if almoxarifado_id:
            sql += " AND almoxarifado_id=?"
            params.append(int(almoxarifado_id))
        if situacao:
            sql += " AND situacao=?"
            params.append(situacao)
        sql += " ORDER BY id DESC"
        cur.execute(sql, params)
        tarefas = [_para_dict(_NOMES_CAMPOS["tarefa"], linha)
                   for linha in cur.fetchall()]
        if not tarefas:
            return []
        nomes = _nomes_almoxarifados([t["almoxarifado_id"] for t in tarefas])
        for tarefa in tarefas:
            tarefa["almoxarifado_nome"] = nomes.get(tarefa["almoxarifado_id"], "")
            aceitos = 0
            pendentes = 0
            for convite in listar_convites_tarefa(tarefa["id"]):
                if convite["situacao"] == "aceito":
                    aceitos += 1
                elif convite["situacao"] == "pendente":
                    pendentes += 1
            tarefa["aceitos"] = aceitos
            tarefa["convites_pendentes"] = pendentes
            tarefa["atendendo"] = bool(tarefa.get("atendente_user_nome"))
        return tarefas
    except Exception:
        _log().exception("listar_tarefas falhou")
        return []
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def pode_convidar_para_tarefa(user_nome, tarefa, eh_admin_geral=False):
    """Verdadeiro quando quem está na tela pode CHAMAR servidores para a tarefa.

    Chamar é ato de quem RESPONSÁVEL pela tarefa (o dono do depósito) ou de
    quem administra o módulo. Quem só foi convidado não convida-outro: senão
    a tarefa cresce sozinha, e o depósito deixa de ter dono."""
    try:
        papel = papel_no_estoque(user_nome, eh_admin_geral)
        if papel == PAPEL_ADMINISTRADOR:
            return True
        if papel != PAPEL_OPERADOR:
            return False
        if not tarefa:
            return False
        return (tarefa.get("responsavel_user_nome") or "") == (user_nome or "")
    except Exception:
        _log().exception("pode_convidar_para_tarefa falhou")
        return False


def convidar_para_tarefa(tarefa_id, convidado_user_nome, papel="participa",
                         recado="", ator="", eh_admin_geral=False):
    """CHAMA um servidor já cadastrado para tratar o depósito.

    "Quem pode chamar quem" para tratar o depósito: o responsável da tarefa
    convida servidores cadastrados, e o convidado ACEITA antes de contar.
    Convite repetido renova o estado, sem criar segunda linha.

    Returns:
        tuple: (ok, mensagem)
    """
    conn = None
    try:
        tarefa_id = int(tarefa_id)
        convidado = (convidado_user_nome or "").strip()
        tarefa = obter_tarefa(tarefa_id)
        if not tarefa:
            return (False, "Tarefa de depósito não encontrada.")
        if not pode_convidar_para_tarefa(ator, tarefa, eh_admin_geral):
            return (False, "Só quem responde pela tarefa pode chamar servidores.")
        if not convidado:
            return (False, "Escolha o servidor que vai tratar o depósito.")
        if convidado == (tarefa.get("responsavel_user_nome") or ""):
            return (False, "Quem responde pela tarefa já está nela.")
        if tarefa["situacao"] in ("concluida", "cancelada"):
            return (False, f"A tarefa {tarefa['numero']} já foi "
                           f"{tarefa['situacao']}.")
        nome_exibicao, unidade = _ficha_do_servidor(convidado)
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, situacao FROM tb_estoque_convite "
                    "WHERE tarefa_id=? AND convidado_user_nome=?",
                    (tarefa_id, convidado))
        existente = cur.fetchone()
        if existente:
            if existente[1] == "pendente":
                cur.execute("UPDATE tb_estoque_convite SET nome_exibicao=?, "
                            "unidade=?, papel=?, recado=?, situacao='pendente' "
                            "WHERE id=?",
                            (nome_exibicao, unidade, (papel or "participa"),
                             (recado or "").strip(), existente[0]))
                mensagem = (f"Convite de {nome_exibicao} renovado — ele ainda "
                            f"não respondeu.")
            else:
                cur.execute("UPDATE tb_estoque_convite SET nome_exibicao=?, "
                            "unidade=?, papel=? WHERE id=?",
                            (nome_exibicao, unidade, (papel or "participa"),
                             existente[0]))
                mensagem = f"{nome_exibicao} já estava convidado ({existente[1]})."
        else:
            cur.execute(
                "INSERT INTO tb_estoque_convite "
                "(tarefa_id, convidado_user_nome, nome_exibicao, unidade, papel, "
                " situacao, convidado_por, data_convite, data_resposta, recado) "
                "VALUES (?, ?, ?, ?, ?, 'pendente', ?, ?, '', ?)",
                (tarefa_id, convidado, nome_exibicao, unidade,
                 (papel or "participa"), ator or "", _agora(), (recado or "").strip()))
            mensagem = f"Convite pendente para {nome_exibicao} tratar o depósito."
        _commit_com_retry(conn, contexto="convidar_para_tarefa")
        _auditar(ator, "convidar_para_tarefa", f"tarefa {tarefa['numero']}",
                 f"convidado={convidado} papel={papel}")
        return (True, mensagem)
    except Exception:
        _rollback_seguro(conn, contexto="convidar_para_tarefa")
        _log().exception("convidar_para_tarefa falhou")
        return (False, "Erro ao enviar o convite.")
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def listar_convites_tarefa(tarefa_id):
    """Quem foi CHAMADO para tratar o depósito, com o estado do convite."""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT " + ", ".join(_NOMES_CAMPOS["convite"]) +
                    " FROM tb_estoque_convite WHERE tarefa_id=? ORDER BY id ASC",
                    (int(tarefa_id),))
        return [_para_dict(_NOMES_CAMPOS["convite"], linha)
                for linha in cur.fetchall()]
    except Exception:
        _log().exception("listar_convites_tarefa falhou")
        return []
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def listar_convites_pendentes(user_nome):
    """Convites de depósito aguardando resposta de quem está na tela."""
    convites = []
    try:
        alvo = (user_nome or "").strip()
        if not alvo:
            return []
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT " + ", ".join(_NOMES_CAMPOS["convite"]) +
                    " FROM tb_estoque_convite WHERE convidado_user_nome=? "
                    "AND situacao='pendente' ORDER BY id DESC", (alvo,))
        convites = [_para_dict(_NOMES_CAMPOS["convite"], linha)
                    for linha in cur.fetchall()]
        if not convites:
            return []
        ids = [c["tarefa_id"] for c in convites]
        marcadores = ",".join(["?"] * len(ids))
        cur.execute(f"SELECT id, numero, titulo, tipo FROM tb_estoque_tarefa "
                    f"WHERE id IN ({marcadores})", tuple(ids))
        tarefas = {int(linha[0]): {"numero": linha[1], "titulo": linha[2],
                                   "tipo": linha[3]}
                   for linha in cur.fetchall()}
        for convite in convites:
            ficha = tarefas.get(convite["tarefa_id"], {})
            convite["tarefa_numero"] = ficha.get("numero", "")
            convite["tarefa_titulo"] = ficha.get("titulo", "")
            convite["tarefa_tipo"] = ficha.get("tipo", "")
        return convites
    except Exception:
        _log().exception("listar_convites_pendentes falhou")
        return []
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def responder_convite_tarefa(convite_id, user_nome, aceitar=True, recado=""):
    """Aceita (ou recusa) o convite de tratar o depósito.

    Só o próprio convidado responde. O aceite é o que coloca a pessoa na lista
    de quem está tratando — sem ele, o convidado é só um nome na lista.

    Returns:
        tuple: (ok, mensagem, numero_tarefa ou '')
    """
    conn = None
    try:
        convite_id = int(convite_id)
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT tarefa_id, convidado_user_nome, situacao "
                    "FROM tb_estoque_convite WHERE id=?", (convite_id,))
        linha = cur.fetchone()
        if not linha:
            return (False, "Convite não encontrado.", "")
        tarefa_id, convidado, situacao = linha
        if (convidado or "") != (user_nome or ""):
            return (False, "Este convite não é seu.", "")
        if situacao != "pendente":
            return (False, f"Este convite já foi {situacao}.", "")
        novo = "aceito" if aceitar else "recusado"
        cur.execute("UPDATE tb_estoque_convite SET situacao=?, data_resposta=?, "
                    "recado=? WHERE id=?",
                    (novo, _agora(), (recado or "").strip(), convite_id))
        tarefa = obter_tarefa(tarefa_id) or {}
        _commit_com_retry(conn, contexto="responder_convite_tarefa")
        _auditar(user_nome, "responder_convite_tarefa", f"convite {convite_id}",
                 f"tarefa={tarefa.get('numero', '')} resposta={novo}")
        verbo = "aceito" if aceitar else "recusado"
        return (True, f"Convite {verbo}: {tarefa.get('titulo', 'depósito')} "
                      f"({tarefa.get('numero', '')})", tarefa.get("numero", ""))
    except Exception:
        _rollback_seguro(conn, contexto="responder_convite_tarefa")
        _log().exception("responder_convite_tarefa falhou")
        return (False, "Erro ao responder o convite.", "")
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def _aceitou_tarefa(tarefa_id, user_nome):
    """Verdadeiro quando o servidor ACEITOU o convite desta tarefa.

    É esta conferência que segura quem pode "estar atendendo": estar no
    atendente significa que a pessoa foi chamada e topou. Sem ela, qualquer
    servidor com acesso padrão ao módulo poderia assumir o depósito de
    qualquer secretaria — e o depósito ficaria sem dono de verdade."""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM tb_estoque_convite "
                    "WHERE tarefa_id=? AND convidado_user_nome=? "
                    "AND situacao='aceito'",
                    (int(tarefa_id), (user_nome or "").strip()))
        return bool(int((cur.fetchone() or [0])[0] or 0))
    except Exception:
        _log().exception("_aceitou_tarefa falhou")
        return False
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def assumir_tarefa(tarefa_id, user_nome, eh_admin_geral=False):
    """Marca QUEM ESTÁ ATENDENDO o depósito agora.

    A tarefa tem responsável (quem chamou) e atendente (quem está tratando
    agora) — as duas coisas não são a mesma: quem abre nem sempre é quem pode
    estar no almoxarifado hoje.

    Quem entra como atendente é quem RESPONDE pela tarefa, quem administra o
    módulo, ou quem ACEITOU o convite. Estar no atendente é ato de quem topou
    tratar o depósito, e não de quem simplesmente tem acesso à tela.

    Returns:
        tuple: (ok, mensagem)
    """
    conn = None
    try:
        tarefa_id = int(tarefa_id)
        alvo = (user_nome or "").strip()
        tarefa = obter_tarefa(tarefa_id)
        if not tarefa:
            return (False, "Tarefa de depósito não encontrada.")
        if not pode_consultar(alvo, eh_admin_geral):
            return (False, "Servidor sem vínculo com o módulo de estoque.")
        if not ((tarefa.get("responsavel_user_nome") or "") == alvo
                or pode_administrar(alvo, eh_admin_geral)
                or _aceitou_tarefa(tarefa_id, alvo)):
            return (False, "Só assume o depósito quem responde pela tarefa, "
                           "quem administra o módulo, ou quem aceitou o convite.")
        if tarefa["situacao"] in ("concluida", "cancelada"):
            return (False, f"A tarefa {tarefa['numero']} já foi {tarefa['situacao']}.")
        nome_alvo, _unidade = _ficha_do_servidor(alvo)
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE tb_estoque_tarefa SET atendente_user_nome=?, "
                    "situacao='em_andamento' WHERE id=?", (alvo, tarefa_id))
        _commit_com_retry(conn, contexto="assumir_tarefa")
        _auditar(alvo, "assumir_tarefa", f"tarefa {tarefa['numero']}",
                 f"anterior={tarefa.get('atendente_user_nome') or '-'}")
        return (True, f"{nome_alvo} está atendendo o depósito "
                      f"{tarefa['numero']}.")
    except Exception:
        _rollback_seguro(conn, contexto="assumir_tarefa")
        _log().exception("assumir_tarefa falhou")
        return (False, "Erro ao assumir a tarefa.")
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def concluir_tarefa(tarefa_id, ator="", eh_admin_geral=False):
    """Conclui a tarefa de depósito.

    Returns:
        tuple: (ok, mensagem)
    """
    conn = None
    try:
        tarefa_id = int(tarefa_id)
        tarefa = obter_tarefa(tarefa_id)
        if not tarefa:
            return (False, "Tarefa de depósito não encontrada.")
        if tarefa["situacao"] == "concluida":
            return (False, f"A tarefa {tarefa['numero']} já foi concluída.")
        if not pode_movimentar(ator, eh_admin_geral):
            return (False, "Você só pode consultar o estoque.")
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE tb_estoque_tarefa SET situacao='concluida', "
                    "data_conclusao=? WHERE id=?", (_agora(), tarefa_id))
        cur.execute("UPDATE tb_estoque_convite SET situacao='cancelado', "
                    "data_resposta=? WHERE tarefa_id=? AND situacao='pendente'",
                    (_agora(), tarefa_id))
        _commit_com_retry(conn, contexto="concluir_tarefa")
        _auditar(ator, "concluir_tarefa", f"tarefa {tarefa['numero']}")
        return (True, f"Depósito {tarefa['numero']} concluído.")
    except Exception:
        _rollback_seguro(conn, contexto="concluir_tarefa")
        _log().exception("concluir_tarefa falhou")
        return (False, "Erro ao concluir a tarefa.")
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def cancelar_convite_tarefa(convite_id, ator="", eh_admin_geral=False):
    """Cancela o convite de um servidor para o depósito.

    Returns:
        tuple: (ok, mensagem)
    """
    conn = None
    try:
        convite_id = int(convite_id)
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT tarefa_id, convidado_user_nome, situacao "
                    "FROM tb_estoque_convite WHERE id=?", (convite_id,))
        linha = cur.fetchone()
        if not linha:
            return (False, "Convite não encontrado.")
        tarefa_id, convidado, situacao = linha
        if situacao not in ("pendente", "aceito"):
            return (False, f"Convite {situacao} não pode ser cancelado.")
        tarefa = obter_tarefa(tarefa_id) or {}
        if not pode_convidar_para_tarefa(ator, tarefa, eh_admin_geral):
            return (False, "Só quem responde pela tarefa cancela o convite.")
        cur.execute("UPDATE tb_estoque_convite SET situacao='cancelado', "
                    "data_resposta=? WHERE id=?", (_agora(), convite_id))
        _commit_com_retry(conn, contexto="cancelar_convite_tarefa")
        _auditar(ator, "cancelar_convite_tarefa", f"convite {convite_id}",
                 f"convidado={convidado}")
        return (True, f"Convite de {convidado} cancelado — não trata mais o depósito.")
    except Exception:
        _rollback_seguro(conn, contexto="cancelar_convite_tarefa")
        _log().exception("cancelar_convite_tarefa falhou")
        return (False, "Erro ao cancelar o convite.")
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


# ============ painel por secretaria ============

def validar_dias(dias=None):
    """Clamp dos dias de item parado (7 a 365). O padrão vem da configuração."""
    if dias is None:
        dias = get_config("estoque_dias_parado", str(DIAS_PARADO_PADRAO))
    try:
        valor = int(dias)
    except (TypeError, ValueError):
        return DIAS_PARADO_PADRAO
    return max(7, min(365, valor))


def dias_parado():
    """Quantos dias uma entrega parada espera antes de virar pedido."""
    return validar_dias(None)


def salvar_dias_parado(dias, ator="", eh_admin_geral=False):
    """Grava o número de dias de item PARADO (padrão 30).

    Returns:
        tuple: (ok, mensagem)
    """
    try:
        if not pode_administrar(ator, eh_admin_geral):
            return (False, "Só o administrador do módulo ajusta este número.")
        valor = validar_dias(dias)
        if not set_config("estoque_dias_parado", str(valor)):
            return (False, "Erro ao gravar o número de dias parado.")
        _auditar(ator, "salvar_dias_parado", "mod_estoque", f"dias={valor}")
        return (True, f"Item parado passa a contar a partir de {valor} dias "
                      f"sem baixa.")
    except Exception:
        _log().exception("salvar_dias_parado falhou")
        return (False, "Erro ao gravar o número de dias parado.")


def painel_almoxarifado(almoxarifado_id, dias=None):
    """Os quatro números que o gestor da secretaria precisa ver.

    - RECEBIDO: quanto entrou no almoxarifado (entrada + o que veio de outro);
    - DISPONÍVEL: o que está no almoxarifado, ainda não entregue a ninguém;
    - EM USO: o que foi entregue a uma sala e não voltou;
    - PARADO: o que está em uso e sem baixa há mais de N dias — este é o
      número de DESPERDÍCIO, e é o que dispara o pedido de recolhimento.

    Sem destino e sem data de entrega o "em uso" não seria número, e sem o
    "parado" o painel não diria nada sobre o que se perde.
    """
    conn = None
    try:
        limite = validar_dias(dias)
        almoxarifado = obter_almoxarifado(almoxarifado_id)
        if not almoxarifado:
            return None
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COALESCE(SUM(quantidade), 0) FROM tb_estoque_saldo "
                    "WHERE almoxarifado_id=?", (int(almoxarifado_id),))
        disponivel = _arred((cur.fetchone() or [0])[0])
        cur.execute("SELECT COALESCE(SUM(quantidade), 0) FROM tb_estoque_entrega "
                    "WHERE almoxarifado_id=? AND situacao='em_uso'",
                    (int(almoxarifado_id),))
        em_uso = _arred((cur.fetchone() or [0])[0])
        # "parado" é calculado em Python: a data de hoje muda durante a
        # consulta e a comparação por texto varyria de fuso para fuso.
        cur.execute("SELECT COALESCE(SUM(quantidade), 0) FROM tb_estoque_entrega "
                    "WHERE almoxarifado_id=? AND situacao='em_uso' "
                    "AND data_entrega<>'' AND substr(data_entrega,1,10) < ?",
                    (int(almoxarifado_id),
                     (datetime.now() - timedelta(days=limite))
                     .strftime("%Y-%m-%d")))
        parado = _arred((cur.fetchone() or [0])[0])
        # recebido: entradas do próprio almoxarifado + o que veio por
        # transferência de outro (o que saiu dele NÃO é recebimento dele)
        cur.execute("SELECT COALESCE(SUM(quantidade), 0) FROM tb_estoque_movimento "
                    "WHERE tipo='entrada' AND almoxarifado_destino_id=?",
                    (int(almoxarifado_id),))
        recebido = _arred((cur.fetchone() or [0])[0])
        cur.execute("SELECT COALESCE(SUM(quantidade), 0) FROM tb_estoque_movimento "
                    "WHERE tipo='entrada' AND almoxarifado_destino_id=? "
                    "AND almoxarifado_origem_id IS NULL", (int(almoxarifado_id),))
        recebido_direto = _arred((cur.fetchone() or [0])[0])
        cur.execute("SELECT COALESCE(SUM(quantidade), 0) FROM tb_estoque_movimento "
                    "WHERE tipo='devolucao' AND almoxarifado_destino_id=?",
                    (int(almoxarifado_id),))
        devolvido = _arred((cur.fetchone() or [0])[0])
        cur.execute("SELECT COALESCE(SUM(quantidade), 0) FROM tb_estoque_movimento "
                    "WHERE tipo='saida' AND almoxarifado_origem_id=?",
                    (int(almoxarifado_id),))
        saida = _arred((cur.fetchone() or [0])[0])
        cur.execute("SELECT COUNT(*) FROM tb_estoque_item WHERE ativo=1")
        itens_catalogo = int((cur.fetchone() or [0])[0] or 0)
        return {"almoxarifado": almoxarifado, "recebido": recebido,
                "recebido_direto": recebido_direto, "devolvido": devolvido,
                "disponivel": disponivel, "em_uso": em_uso, "parado": parado,
                "saida": saida, "itens_catalogo": itens_catalogo,
                "dias_limite": limite}
    except Exception:
        _log().exception("painel_almoxarifado falhou")
        return None
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def listar_movimentos(almoxarifado_id=None, item_id=None, tipo="", limite=200):
    """Histórico de movimentação, do mais recente para o mais antigo.

    Serve à auditoria e à conferência: quem mexeu, quando, de onde, para onde e
    com qual documento."""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        sql = "SELECT " + ", ".join(_NOMES_CAMPOS["movimento"]) + \
              " FROM tb_estoque_movimento WHERE 1=1"
        params = []
        if almoxarifado_id:
            sql += (" AND (almoxarifado_origem_id=? OR almoxarifado_destino_id=?)")
            params.extend([int(almoxarifado_id), int(almoxarifado_id)])
        if item_id:
            sql += " AND item_id=?"
            params.append(int(item_id))
        if tipo:
            sql += " AND tipo=?"
            params.append(tipo)
        sql += " ORDER BY id DESC"
        try:
            total = max(1, min(1000, int(limite)))
        except (TypeError, ValueError):
            total = 200
        sql += f" LIMIT {total}"
        cur.execute(sql, params)
        movimentos = [_para_dict(_NOMES_CAMPOS["movimento"], linha)
                      for linha in cur.fetchall()]
        ids = set()
        for movimento in movimentos:
            if movimento["almoxarifado_origem_id"]:
                ids.add(movimento["almoxarifado_origem_id"])
            if movimento["almoxarifado_destino_id"]:
                ids.add(movimento["almoxarifado_destino_id"])
        nomes = _nomes_almoxarifados(list(ids))
        for movimento in movimentos:
            movimento["origem_nome"] = nomes.get(movimento["almoxarifado_origem_id"],
                                                 "")
            movimento["destino_nome"] = nomes.get(movimento["almoxarifado_destino_id"],
                                                  "")
        return movimentos
    except Exception:
        _log().exception("listar_movimentos falhou")
        return []
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def listar_documentos(almoxarifado_id=None, limite=100):
    """Documentos de saída/entrada/devolução, do mais recente para o mais antigo."""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        sql = "SELECT " + ", ".join(_NOMES_CAMPOS["documento"]) + \
              " FROM tb_estoque_documento WHERE 1=1"
        params = []
        if almoxarifado_id:
            sql += " AND almoxarifado_id=?"
            params.append(int(almoxarifado_id))
        sql += " ORDER BY id DESC"
        try:
            total = max(1, min(500, int(limite)))
        except (TypeError, ValueError):
            total = 100
        sql += f" LIMIT {total}"
        cur.execute(sql, params)
        documentos = [_para_dict(_NOMES_CAMPOS["documento"], linha)
                      for linha in cur.fetchall()]
        if not documentos:
            return []
        nomes = _nomes_almoxarifados(
            [d["almoxarifado_id"] for d in documentos]
            + [d["almoxarifado_destino_id"] for d in documentos
               if d.get("almoxarifado_destino_id")])
        for documento in documentos:
            documento["almoxarifado_nome"] = nomes.get(documento["almoxarifado_id"], "")
            documento["destino_nome"] = nomes.get(
                documento["almoxarifado_destino_id"], "")
        return documentos
    except Exception:
        _log().exception("listar_documentos falhou")
        return []
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def visao_geral():
    """Números do módulo para o painel de administração.

    `parado` é o número que importa: material em uso sem baixa há mais de N
    dias é o que se perde se ninguém recolher. Um painel de módulo que só
    mostra "quantos almoxarifados existem" informa que o sistema está no ar,
    e não se ele está servindo a alguém."""
    try:
        limite = dias_parado()
        conn = get_connection()
        cur = conn.cursor()

        def _um(sql, params=()):
            try:
                cur.execute(sql, params)
                linha = cur.fetchone()
                return _arred((linha[0] if linha else 0) or 0)
            except Exception:
                return 0

        almoxarifados = _um("SELECT COUNT(*) FROM tb_estoque_almoxarifado "
                            "WHERE central=0 AND ativo=1")
        almoxarifados_total = _um("SELECT COUNT(*) FROM tb_estoque_almoxarifado")
        itens = _um("SELECT COUNT(*) FROM tb_estoque_item WHERE ativo=1")
        disponivel = _um("SELECT COALESCE(SUM(quantidade), 0) FROM tb_estoque_saldo")
        em_uso = _um("SELECT COALESCE(SUM(quantidade), 0) FROM tb_estoque_entrega "
                     "WHERE situacao='em_uso'")
        parado = _um("SELECT COALESCE(SUM(quantidade), 0) FROM tb_estoque_entrega "
                     "WHERE situacao='em_uso' AND data_entrega<>'' "
                     "AND substr(data_entrega,1,10) < ?",
                     ((datetime.now() - timedelta(days=limite))
                      .strftime("%Y-%m-%d"),))
        pedidos = _um("SELECT COUNT(*) FROM tb_estoque_recolhimento "
                      "WHERE situacao='aberto'")
        tarefas = _um("SELECT COUNT(*) FROM tb_estoque_tarefa "
                      "WHERE situacao IN ('aberta','em_andamento')")
        convites = _um("SELECT COUNT(*) FROM tb_estoque_convite "
                       "WHERE situacao='pendente'")
        servidores = _um("SELECT COUNT(*) FROM tb_estoque_usuario WHERE ativo=1")
        documentos = _um("SELECT COUNT(*) FROM tb_estoque_documento")
        por_almoxarifado = []
        for almoxarifado in listar_almoxarifados():
            painel = painel_almoxarifado(almoxarifado["id"], dias=limite)
            if painel:
                por_almoxarifado.append({
                    "id": almoxarifado["id"], "nome": almoxarifado["nome"],
                    "central": bool(almoxarifado["central"]),
                    "recebido": painel["recebido"], "disponivel": painel["disponivel"],
                    "em_uso": painel["em_uso"], "parado": painel["parado"]})
        return {"almoxarifados": almoxarifados,
                "almoxarifados_total": almoxarifados_total, "itens": itens,
                "disponivel": disponivel, "em_uso": em_uso, "parado": parado,
                "pedidos": pedidos, "tarefas": tarefas, "convites": convites,
                "servidores": servidores, "documentos": documentos,
                "dias_parado": limite, "por_almoxarifado": por_almoxarifado}
    except Exception:
        _log().exception("visao_geral falhou")
        return {"almoxarifados": 0, "almoxarifados_total": 0, "itens": 0,
                "disponivel": 0, "em_uso": 0, "parado": 0, "pedidos": 0,
                "tarefas": 0, "convites": 0, "servidores": 0, "documentos": 0,
                "dias_parado": DIAS_PARADO_PADRAO, "por_almoxarifado": []}
