"""EN: Service Orders — own database (db_mod_os.db, WAL). The ONLY access point
to the module's data: boards (per user or per organisational unit), columns,
cards (service orders) with a stable sequential number per board, the event
timeline and the comments. Owns its schema in `init_db` (portable SQL, works on
SQLite and PostgreSQL). Cross-module data (users, organogram) arrives through
`mod_intranet.integracoes` — never by importing another module.

PT-BR: Ordens de Serviço — banco próprio (db_mod_os.db, WAL). ÚNICO ponto de
acesso aos dados do módulo: quadros (por servidor ou por unidade do
organograma), colunas, cartões (ordens de serviço) com número sequencial
estável por quadro, a linha do tempo de eventos e os comentários. Dono do
schema em `init_db` (SQL portátil, funciona em SQLite e PostgreSQL). O que vem
de outro módulo (usuários, organograma) entra por
`mod_intranet.integracoes` — nunca importando outro módulo de negócio.

TABLES (prefixo `tb_os_`)
    tb_os_quadro      quadro de ordens de serviço (privado ou da unidade)
    tb_os_coluna      colunas ordenáveis do quadro
    tb_os_ordem       cartão = a ordem de serviço (com o número do quadro)
    tb_os_comentario  comentários da ordem de serviço
    tb_os_evento      linha do tempo da ordem de serviço
    tb_os_convite     convite de usuário para o quadro, com papel
    tb_os_sequencia   contador do quadro (um por quadro, número nunca repete)
"""
import os
import re
import sys
import time
import unicodedata
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

CHAVE_MODULO = "os"
NOME_MODULO = "Ordens de Serviço"

# Vocabulário do quadro (língua ubíqua do domínio).
VISIBILIDADES = ("privado", "unidade")
PAPEIS = ("leitor", "editor", "administrador")
PRIORIDADES = ("baixa", "media", "alta", "urgente")
STATUS_CONVITE = ("pendente", "aceito", "recusado", "cancelado")

# A coluna de conclusão é a última do quadro; o sistema a cria marcada.
TIPOS_EVENTO = ("criacao", "edicao", "movimento", "responsavel",
                "prioridade", "comentario", "arquivamento",
                "conclusao", "reabertura", "numero")

LIMITE_COLUNAS_POR_QUADRO = 30
DIGITOS_MINIMO = 3
DIGITOS_MAXIMO = 8
DIGITOS_PADRAO = 4
PREFIXO_PADRAO_TAMANHO = 6

# Transação curta + retry de contenção (SQLite WAL "database is locked").
# busy_timeout=5000 herdado de banco_conexao.conexao; não reconfigurar aqui.
TENTATIVAS_LOCKED = 5
ESPERA_LOCKED_SEG = 0.05

_CORES_QUADRO = {
    "azul": "#1565C0", "verde": "#2E7D32", "roxo": "#6A1B9A",
    "laranja": "#EF6C00", "cinza": "#455A64", "teal": "#00838F",
}


def _log():
    """Logger escopado do módulo de Ordens de Serviço."""
    from mod_intranet import observabilidade
    return observabilidade.get_logger("os")


def _norm(texto):
    """Normaliza para comparação de nomes: sem acento, sem pontuação, minúsculo.

    Evenemente repetido nos módulos por decisão (o banco de cada um é seu) —
    a mesma regra de `mod_lista_telefonica` e `mod_gest_cad_usuario`."""
    try:
        limpo = unicodedata.normalize("NFKD", str(texto or "")) \
            .encode("ascii", "ignore").decode().lower()
        return " ".join(re.findall(r"[a-z0-9]+", limpo))
    except Exception:
        return str(texto or "").lower()


def _agora():
    """Data/hora local em texto (formato único do módulo)."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


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
    """Abre a conexão do módulo (WAL) via banco_conexao.conexao('os')."""
    try:
        from mod_intranet.banco_conexao import conexao
        conn = conexao(CHAVE_MODULO)
        if conn is None:
            raise RuntimeError("Falha ao abrir conexão mod_os")
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

DDL_QUADROS = """
CREATE TABLE IF NOT EXISTS tb_os_quadro (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    descricao TEXT NOT NULL DEFAULT '',
    cor TEXT NOT NULL DEFAULT '',
    dono_user_nome TEXT NOT NULL,
    unidade_id INTEGER,
    unidade_nome TEXT NOT NULL DEFAULT '',
    visibilidade TEXT NOT NULL DEFAULT 'privado',
    prefixo_numero TEXT NOT NULL DEFAULT '',
    digitos_numero INTEGER NOT NULL DEFAULT 4,
    ativo INTEGER NOT NULL DEFAULT 1,
    arquivado INTEGER NOT NULL DEFAULT 0,
    data_criacao TEXT NOT NULL DEFAULT ''
)
"""

DDL_COLUNAS = """
CREATE TABLE IF NOT EXISTS tb_os_coluna (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quadro_id INTEGER NOT NULL,
    nome TEXT NOT NULL,
    ordem INTEGER NOT NULL DEFAULT 0,
    cor TEXT NOT NULL DEFAULT '',
    conclusiva INTEGER NOT NULL DEFAULT 0,
    data_criacao TEXT NOT NULL DEFAULT ''
)
"""

DDL_ORDENS = """
CREATE TABLE IF NOT EXISTS tb_os_ordem (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quadro_id INTEGER NOT NULL,
    coluna_id INTEGER NOT NULL,
    numero_sequencial INTEGER NOT NULL DEFAULT 0,
    numero TEXT NOT NULL DEFAULT '',
    titulo TEXT NOT NULL,
    descricao TEXT NOT NULL DEFAULT '',
    ordem INTEGER NOT NULL DEFAULT 0,
    prioridade TEXT NOT NULL DEFAULT 'media',
    responsavel_user_nome TEXT NOT NULL DEFAULT '',
    rotulos TEXT NOT NULL DEFAULT '',
    data_vencimento TEXT NOT NULL DEFAULT '',
    criado_por TEXT NOT NULL DEFAULT '',
    criado_em TEXT NOT NULL DEFAULT '',
    movido_em TEXT NOT NULL DEFAULT '',
    concluido_em TEXT NOT NULL DEFAULT '',
    arquivado INTEGER NOT NULL DEFAULT 0
)
"""

DDL_COMENTARIOS = """
CREATE TABLE IF NOT EXISTS tb_os_comentario (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ordem_id INTEGER NOT NULL,
    quadro_id INTEGER NOT NULL,
    autor_user_nome TEXT NOT NULL DEFAULT '',
    texto TEXT NOT NULL DEFAULT '',
    criado_em TEXT NOT NULL DEFAULT ''
)
"""

DDL_EVENTOS = """
CREATE TABLE IF NOT EXISTS tb_os_evento (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ordem_id INTEGER NOT NULL,
    quadro_id INTEGER NOT NULL,
    tipo TEXT NOT NULL DEFAULT 'edicao',
    autor_user_nome TEXT NOT NULL DEFAULT '',
    texto TEXT NOT NULL DEFAULT '',
    criado_em TEXT NOT NULL DEFAULT ''
)
"""

DDL_CONVITES = """
CREATE TABLE IF NOT EXISTS tb_os_convite (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quadro_id INTEGER NOT NULL,
    convidado_user_nome TEXT NOT NULL,
    nome_exibicao TEXT NOT NULL DEFAULT '',
    unidade TEXT NOT NULL DEFAULT '',
    papel TEXT NOT NULL DEFAULT 'leitor',
    status TEXT NOT NULL DEFAULT 'pendente',
    convidado_por TEXT NOT NULL DEFAULT '',
    data_convite TEXT NOT NULL DEFAULT '',
    data_resposta TEXT NOT NULL DEFAULT '',
    recado TEXT NOT NULL DEFAULT ''
)
"""

DDL_SEQUENCIA = """
CREATE TABLE IF NOT EXISTS tb_os_sequencia (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quadro_id INTEGER NOT NULL UNIQUE,
    ultimo_numero INTEGER NOT NULL DEFAULT 0
)
"""

INDICES = (
    "CREATE INDEX IF NOT EXISTS ix_os_coluna_quadro ON tb_os_coluna(quadro_id, ordem)",
    "CREATE INDEX IF NOT EXISTS ix_os_ordem_quadro ON tb_os_ordem(quadro_id, arquivado)",
    "CREATE INDEX IF NOT EXISTS ix_os_ordem_coluna ON tb_os_ordem(coluna_id, ordem)",
    "CREATE INDEX IF NOT EXISTS ix_os_ordem_vencimento ON tb_os_ordem(data_vencimento)",
    "CREATE INDEX IF NOT EXISTS ix_os_ordem_numero ON tb_os_ordem(quadro_id, numero_sequencial)",
    "CREATE INDEX IF NOT EXISTS ix_os_evento_ordem ON tb_os_evento(ordem_id, id)",
    "CREATE INDEX IF NOT EXISTS ix_os_comentario_ordem ON tb_os_comentario(ordem_id, id)",
    "CREATE INDEX IF NOT EXISTS ix_os_convite_convidade ON tb_os_convite(convidado_user_nome, status)",
    "CREATE INDEX IF NOT EXISTS ix_os_convite_quadro ON tb_os_convite(quadro_id)",
)


def init_db():
    """Cria o schema do módulo (idempotente, portátil SQLite ↔ PostgreSQL).

    `CREATE TABLE IF NOT EXISTS` + `CREATE INDEX IF NOT EXISTS` — rodar mil
    vezes não muda nada. Sem `REFERENCES`: o tradutor de DDL do Postgres remove
    as chaves estrangeiras, então TODA cascata de `DELETE` é feita à mão, em
    transação curta, na ordem certa (ver `excluir_quadro`).

    Returns:
        bool: True quando o schema está no lugar.
    """
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        for ddl in (DDL_QUADROS, DDL_COLUNAS, DDL_ORDENS, DDL_COMENTARIOS,
                    DDL_EVENTOS, DDL_CONVITES, DDL_SEQUENCIA):
            cur.execute(ddl)
        for indice in INDICES:
            cur.execute(indice)
        _commit_com_retry(conn, contexto="init_db")
        return True
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


# ============ número da ordem de serviço ============

def _prefixo_do_nome(nome):
    """Prefixo padrão do quadro: primeira palavra do nome, até 6 caracteres.

    "Obras 2026" → "OBRAS"; "Manutenção_predial" → "MANUTE". Sem acento, sem
    espaço, em maiúsculas — é o que o chamador da prefeitura vai ditar ao
    telefone, então precisa caber em uma palavra falada."""
    try:
        limpo = unicodedata.normalize("NFKD", str(nome or "")) \
            .encode("ascii", "ignore").decode()
        partes = re.findall(r"[A-Za-z0-9]+", limpo)
        if not partes:
            return "OS"
        base = partes[0].upper()[:PREFIXO_PADRAO_TAMANHO]
        return base or "OS"
    except Exception:
        return "OS"


def normalizar_prefixo(prefixo):
    """Limpa o prefixo digitado à mão (sem acento, até 12 caracteres)."""
    try:
        limpo = unicodedata.normalize("NFKD", str(prefixo or "")) \
            .encode("ascii", "ignore").decode()
        base = re.sub(r"[^A-Za-z0-9]+", "", limpo).upper()[:12]
        return base
    except Exception:
        return ""


def validar_digitos(digitos):
    """Clamp do número de dígitos (3 a 8) — o quadro sempre fica com um valor válido."""
    try:
        valor = int(digitos)
    except (TypeError, ValueError):
        return DIGITOS_PADRAO
    return max(DIGITOS_MINIMO, min(DIGITOS_MAXIMO, valor))


def montar_numero(prefixo, sequencial, digitos):
    """Monta o número exibido: `PREFIXO-0001`."""
    try:
        dig = validar_digitos(digitos)
        return f"{(prefixo or 'OS').upper()}-{int(sequencial):0{dig}d}"
    except Exception:
        return f"OS-{int(sequencial or 0):0{DIGITOS_PADRAO}d}"


def _reservar_numero(cur, quadro_id):
    """Reserva o próximo número do quadro NA TRANSAÇÃO JÁ ABERTA.

    O `UPDATE ... = ultimo_numero + 1` followed de um `SELECT` na MESMA
    transação é o que serializa a reserva no próprio banco (o Python não
    segura nada): quem entra depois do primeiro UPDATE espera o commit do
    primeiro e lê o valor seguinte. Se a transação for desfeita, o contador
    volta junto — buraco nenhum, número repetido nenhum.
    """
    cur.execute("INSERT OR IGNORE INTO tb_os_sequencia (quadro_id, ultimo_numero) "
                "VALUES (?, 0)", (quadro_id,))
    cur.execute("UPDATE tb_os_sequencia SET ultimo_numero = ultimo_numero + 1 "
                "WHERE quadro_id = ?", (quadro_id,))
    cur.execute("SELECT ultimo_numero FROM tb_os_sequencia WHERE quadro_id = ?",
                (quadro_id,))
    linha = cur.fetchone()
    return int(linha[0]) if linha else 1


def alocar_numero_na_conexao(conn, quadro_id):
    """Reserva o próximo número do quadro na conexão/transação do chamador.

    Existe para deixar explícito (e testável) que a reserva acontece DENTRO
    da transação do INSERT do cartão: quem chamar e der rollback em seguida
    recebe o mesmo número na próxima tentativa. Nunca commitar por aqui."""
    try:
        return _reservar_numero(conn.cursor(), quadro_id)
    except Exception:
        _log().exception("alocar_numero_na_conexao falhou")
        raise


def proximo_numero(quadro_id):
    """Número que o próximo cartão receberia (somente leitura, não reserva)."""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT ultimo_numero FROM tb_os_sequencia WHERE quadro_id = ?",
                    (quadro_id,))
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


def definir_formato_numero(quadro_id, prefixo=None, digitos=None, ator="",
                           eh_admin_geral=False):
    """Ajusta o FORMATO do número do quadro. NÃO renumera o que já existe.

    O número guardado em cada ordem de serviço é o histórico — quem já tem
    `OBRAS-0007` continua com `OBRAS-0007` para sempre. O formato novo vale
    para os próximos cartões.

    Quem muda o formato muda o número de toda ordem de serviço que vier
    depois: é decisão de quem administra o quadro (dono ou administrador
    convidado), a mesma regra de `atualizar_quadro` — o leitor não renumera
    o quadro dos outros, e servidor de fora não renumera nada.

    Returns:
        tuple: (ok, mensagem)
    """
    conn = None
    try:
        quadro_id = int(quadro_id)
        if not pode_gerenciar(ator, quadro_id, eh_admin_geral):
            return (False, "Só quem administra o quadro pode alterar "
                           "o formato do número.")
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT prefixo_numero, digitos_numero FROM tb_os_quadro "
                    "WHERE id = ?", (quadro_id,))
        linha = cur.fetchone()
        if not linha:
            return (False, "Quadro não encontrado.")
        novo_prefixo = normalizar_prefixo(prefixo) if prefixo is not None \
            else (linha[0] or "")
        if not novo_prefixo:
            novo_prefixo = "OS"
        novos_digitos = validar_digitos(digitos) if digitos is not None \
            else validar_digitos(linha[1])
        cur.execute("UPDATE tb_os_quadro SET prefixo_numero = ?, digitos_numero = ? "
                    "WHERE id = ?", (novo_prefixo, novos_digitos, quadro_id))
        _commit_com_retry(conn, contexto="definir_formato_numero")
        _auditar(ator, "definir_formato_numero", f"quadro {quadro_id}",
                 f"prefixo={novo_prefixo} digitos={novos_digitos}")
        return (True, f"Número do quadro: {novo_prefixo}-{'0' * novos_digitos} "
                      f"a partir de agora (os anteriores mantêm o número).")
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


# ============ leitura: linhas -> dicionário ============

_CAMPOS_QUADRO = ("id", "nome", "descricao", "cor", "dono_user_nome",
                  "unidade_id", "unidade_nome", "visibilidade",
                  "prefixo_numero", "digitos_numero", "ativo", "arquivado",
                  "data_criacao")
_CAMPOS_COLUNA = ("id", "quadro_id", "nome", "ordem", "cor", "conclusiva",
                  "data_criacao")
_CAMPOS_ORDEM = ("id", "quadro_id", "coluna_id", "numero_sequencial", "numero",
                 "titulo", "descricao", "ordem", "prioridade",
                 "responsavel_user_nome", "rotulos", "data_vencimento",
                 "criado_por", "criado_em", "movido_em", "concluido_em",
                 "arquivado")
_CAMPOS_EVENTO = ("id", "ordem_id", "quadro_id", "tipo", "autor_user_nome",
                  "texto", "criado_em")
_CAMPOS_COMENTARIO = ("id", "ordem_id", "quadro_id", "autor_user_nome",
                      "texto", "criado_em")
_CAMPOS_CONVITE = ("id", "quadro_id", "convidado_user_nome", "nome_exibicao",
                   "unidade", "papel", "status", "convidado_por",
                   "data_convite", "data_resposta", "recado")


def _para_dict(campos, linha):
    """Converte a tupla do cursor em dicionário com nome de campo."""
    if not linha:
        return None
    try:
        return {campo: linha[i] for i, campo in enumerate(campos)}
    except Exception:
        return None


# ============ linha do tempo ============

def _registrar_evento(conn, ordem_id, quadro_id, tipo, ator, texto):
    """Grava UM evento da linha do tempo, na transação de quem chamou.

    Não commita: o evento entra junto com a mudança que ele descreve — ou
    entra junto do rollback dela, que é o comportamento honesto."""
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO tb_os_evento "
            "(ordem_id, quadro_id, tipo, autor_user_nome, texto, criado_em) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (int(ordem_id), int(quadro_id), tipo, ator or "", texto or "",
             _agora()))
        return True
    except Exception:
        _log().exception(f"_registrar_evento({tipo}) falhou")
        return False


def listar_eventos(ordem_id):
    """Linha do tempo da ordem de serviço, da mais antiga para a mais nova."""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT " + ", ".join(_CAMPOS_EVENTO) +
                    " FROM tb_os_evento WHERE ordem_id=? ORDER BY id ASC",
                    (int(ordem_id),))
        return [_para_dict(_CAMPOS_EVENTO, linha)
                for linha in cur.fetchall()]
    except Exception:
        _log().exception("listar_eventos falhou")
        return []
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def listar_comentarios(ordem_id):
    """Comentários da ordem de serviço, em ordem cronológica."""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT " + ", ".join(_CAMPOS_COMENTARIO) +
                    " FROM tb_os_comentario WHERE ordem_id=? ORDER BY id ASC",
                    (int(ordem_id),))
        return [_para_dict(_CAMPOS_COMENTARIO, linha)
                for linha in cur.fetchall()]
    except Exception:
        _log().exception("listar_comentarios falhou")
        return []
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def comentar_ordem(ordem_id, texto, ator="", eh_admin_geral=False):
    """Comenta a ordem de serviço. O comentário também é um evento da linha do tempo.

    Quem comenta precisa poder mexer no cartão (dono, administrador ou editor):
    é a mesma regra que a tela aplica ao esconder o campo de comentário de quem
    só lê. Sem essa conferência, qualquer pessoa — inclusive quem nem enxerga o
    quadro — escrevia na linha do tempo alheia.

    Returns:
        tuple: (ok, mensagem)
    """
    conn = None
    try:
        ordem_id = int(ordem_id)
        corpo = (texto or "").strip()
        if len(corpo) < 2:
            return (False, "Escreva o comentário antes de enviar.")
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT quadro_id, numero FROM tb_os_ordem WHERE id=?",
                    (ordem_id,))
        linha = cur.fetchone()
        if not linha:
            return (False, "Ordem de serviço não encontrada.")
        quadro_id, numero = linha[0], linha[1]
        if not pode_editar(ator, quadro_id, eh_admin_geral):
            return (False, "Você não pode comentar neste quadro.")
        cur.execute("INSERT INTO tb_os_comentario "
                    "(ordem_id, quadro_id, autor_user_nome, texto, criado_em) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (ordem_id, quadro_id, ator or "", corpo, _agora()))
        _registrar_evento(conn, ordem_id, quadro_id, "comentario", ator,
                          f"Comentou: {corpo[:180]}")
        _commit_com_retry(conn, contexto="comentar_ordem")
        _auditar(ator, "comentar_ordem", f"ordem {numero or ordem_id}",
                 f"quadro {quadro_id}")
        return (True, "Comentário registrado na linha do tempo.")
    except Exception:
        _rollback_seguro(conn, contexto="comentar_ordem")
        _log().exception("comentar_ordem falhou")
        return (False, "Erro ao registrar o comentário.")
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


# ============ quadros ============

COLUNAS_PADRAO = "Aberto,Em andamento,Aguardando,Concluído"


def colunas_padrao():
    """Lista de colunas que todo quadro novo recebe (última = de conclusão)."""
    bruto = (get_config("os_colunas_padrao", COLUNAS_PADRAO) or COLUNAS_PADRAO)
    nomes, vistos = [], set()
    for parte in str(bruto).split(","):
        nome = parte.strip()
        if not nome or nome.lower() in vistos:
            continue
        vistos.add(nome.lower())
        nomes.append(nome)
    if not nomes:
        nomes = COLUNAS_PADRAO.split(",")
    return nomes[:LIMITE_COLUNAS_POR_QUADRO]


def salvar_colunas_padrao(texto, ator=""):
    """Grava as colunas padrão do sistema (admin)."""
    try:
        nomes = [p.strip() for p in str(texto or "").split(",") if p.strip()]
        if not nomes:
            return (False, "Informe ao menos uma coluna (separe por vírgula).")
        if len(nomes) > LIMITE_COLUNAS_POR_QUADRO:
            return (False, f"No máximo {LIMITE_COLUNAS_POR_QUADRO} colunas.")
        if len(nomes) < 2:
            return (False, "O quadro precisa de pelo menos 2 colunas "
                           "(uma de trabalho e uma de conclusão).")
        valor = ", ".join(nomes)
        if not set_config("os_colunas_padrao", valor):
            return (False, "Erro ao gravar as colunas padrão.")
        _auditar(ator, "salvar_colunas_padrao", "mod_os", f"colunas={valor}")
        return (True, f"Colunas padrão salvas: {valor}")
    except Exception:
        _log().exception("salvar_colunas_padrao falhou")
        return (False, "Erro ao salvar as colunas padrão.")


def _criar_colunas_padrao(conn, quadro_id):
    """Cria as colunas padrão do quadro novo, na transação do chamador."""
    try:
        nomes = colunas_padrao()
        cur = conn.cursor()
        for indice, nome in enumerate(nomes):
            cur.execute(
                "INSERT INTO tb_os_coluna "
                "(quadro_id, nome, ordem, cor, conclusiva, data_criacao) "
                "VALUES (?, ?, ?, '', ?, ?)",
                (int(quadro_id), nome, indice + 1,
                 1 if indice == len(nomes) - 1 else 0, _agora()))
        return len(nomes)
    except Exception:
        _log().exception("_criar_colunas_padrao falhou")
        raise


def criar_quadro(user_nome, nome, descricao="", cor="", unidade_id=None,
                 unidade_nome="", visibilidade="privado", pode_criar_unidade=False,
                 prefixo_numero="", digitos_numero=DIGITOS_PADRAO, ator=None):
    """Cria um quadro de ordens de serviço — privado do dono ou da unidade.

    Um quadro privado nasce com as colunas padrão do sistema e com a
    sequência própria (nada mais é criado junto). Um quadro de unidade exige
    `pode_criar_unidade` (administrador do módulo ou administrador geral) e
    fica visível para todos os servidores daquela unidade.

    Returns:
        tuple: (ok, mensagem, quadro_id ou None)
    """
    conn = None
    try:
        dono = (ator or user_nome or "").strip()
        titulo = (nome or "").strip()
        if not dono:
            return (False, "Não foi possível identificar o dono do quadro.", None)
        if len(titulo) < 2:
            return (False, "Dê um nome ao quadro (mínimo 2 letras).", None)
        vis = (visibilidade or "privado").strip()
        if vis not in VISIBILIDADES:
            vis = "privado"
        if vis == "unidade" and not pode_criar_unidade:
            return (False, "Só o administrador cria quadro de unidade.", None)
        if vis == "unidade" and not (unidade_nome or "").strip():
            return (False, "Escolha a unidade do quadro de unidade.", None)
        cor_quadro = (cor or "").strip() or _CORES_QUADRO["azul"]
        prefixo = normalizar_prefixo(prefixo_numero) or _prefixo_do_nome(titulo)
        digitos = validar_digitos(digitos_numero)

        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO tb_os_quadro "
            "(nome, descricao, cor, dono_user_nome, unidade_id, unidade_nome, "
            " visibilidade, prefixo_numero, digitos_numero, ativo, arquivado, "
            " data_criacao) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0, ?)",
            (titulo, (descricao or "").strip(), cor_quadro, dono,
             int(unidade_id) if unidade_id else None,
             (unidade_nome or "").strip(), vis, prefixo, digitos, _agora()))
        quadro_id = int(cur.lastrowid)
        # Cada quadro tem a SUA sequência: é o que garante número único e
        # nunca reaproveitado, mesmo com quadro novo homônimo.
        cur.execute("INSERT OR IGNORE INTO tb_os_sequencia (quadro_id, ultimo_numero) "
                    "VALUES (?, 0)", (quadro_id,))
        _criar_colunas_padrao(conn, quadro_id)
        _commit_com_retry(conn, contexto="criar_quadro")
        _auditar(dono, "criar_quadro", f"quadro {quadro_id}",
                 f"nome={titulo} visibilidade={vis} unidade={unidade_nome or '-'}")
        return (True, f"Quadro criado. O número das ordens começa em "
                      f"{montar_numero(prefixo, 1, digitos)}.", quadro_id)
    except Exception:
        _rollback_seguro(conn, contexto="criar_quadro")
        _log().exception("criar_quadro falhou")
        return (False, "Erro ao criar o quadro.", None)
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def obter_quadro(quadro_id):
    """Dados do quadro por id, ou None."""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT " + ", ".join(_CAMPOS_QUADRO) +
                    " FROM tb_os_quadro WHERE id=?", (int(quadro_id),))
        return _para_dict(_CAMPOS_QUADRO, cur.fetchone())
    except Exception:
        _log().exception("obter_quadro falhou")
        return None
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def _unidade_do_usuario(user_nome):
    """`{'id', 'nome'}` da unidade do servidor, casada com o organograma — ou None.

    A lotação tem precedência sobre a unidade: é o setor onde a pessoa
    trabalha de fato, e é por ele que o quadro do setor aparece para ela. O
    casamento com o organograma é feito pelo NOME normalizado (o cadastro
    guarda texto livre), e o id do organograma vem junto para a comparação
    ser exata quando os dois lados concordarem."""
    try:
        integ = _integracoes()
        mapa = integ.unidades_por_usuario_gestao() or {}
        info = mapa.get(user_nome) or {}
        for campo in ("lotacao", "unidade"):
            nome = (info.get(campo) or "").strip()
            if not nome:
                continue
            achada = (integ.unidades_do_organograma_por_nome() or {}).get(
                _norm(nome))
            if achada:
                return {"id": achada.get("id"), "nome": nome}
        return None
    except Exception:
        try:
            _log().warning(f"_unidade_do_usuario({user_nome}) falhou — "
                           "servidor sem unidade reconhecida")
        except Exception:
            pass
        return None


def _mesma_unidade(quadro, unidade_usuario):
    """O quadro é desta unidade? Compara por id e, na falta, pelo nome normalizado."""
    if not unidade_usuario:
        return False
    if quadro.get("unidade_id") and unidade_usuario.get("id") \
            and int(quadro["unidade_id"]) == int(unidade_usuario["id"]):
        return True
    return _norm(quadro.get("unidade_nome") or "") == _norm(unidade_usuario.get("nome") or "")


def papeis_do_quadro(quadro_id):
    """`{user_nome: papel}` de quemAceitou convite — a base do controle de acesso."""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT convidado_user_nome, papel FROM tb_os_convite "
                    "WHERE quadro_id=? AND status='aceito'",
                    (int(quadro_id),))
        return {linha[0]: linha[1] for linha in cur.fetchall() if linha and linha[0]}
    except Exception:
        _log().exception("papeis_do_quadro falhou")
        return {}
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def papel_no_quadro(user_nome, quadro_id, eh_admin_geral=False):
    """Papel do usuário no quadro: 'dono' | 'administrador' | 'editor' |
    'leitor' | 'unidade' | None (não vê o quadro)."""
    try:
        quadro = obter_quadro(quadro_id)
        if not quadro:
            return None
        if (quadro.get("dono_user_nome") or "") == (user_nome or ""):
            return "dono"
        papeis = papeis_do_quadro(quadro_id)
        papel = papeis.get(user_nome)
        if papel:
            return papel
        if quadro.get("visibilidade") == "unidade":
            if _mesma_unidade(quadro, _unidade_do_usuario(user_nome)):
                return "unidade"
        if eh_admin_geral:
            return "administrador"
        return None
    except Exception:
        _log().exception("papel_no_quadro falhou")
        return None


# O que cada papel pode fazer. O dono e o administrador do quadro mandam;
# editor mexe em cartão; leitor só olha; unidade lê o quadro do seu setor.
_PODE_EDITAR = ("dono", "administrador", "editor")
_PODE_GERENCIAR = ("dono", "administrador")


def pode_ver(user_nome, quadro_id, eh_admin_geral=False):
    """Verdadeiro quando o usuário enxerga o quadro."""
    return papel_no_quadro(user_nome, quadro_id, eh_admin_geral) is not None


def pode_editar(user_nome, quadro_id, eh_admin_geral=False):
    """Verdadeiro quando o usuário pode criar e mover cartões."""
    return papel_no_quadro(user_nome, quadro_id, eh_admin_geral) in _PODE_EDITAR


def pode_gerenciar(user_nome, quadro_id, eh_admin_geral=False):
    """Verdadeiro quando o usuário gerencia o quadro (colunas, convites)."""
    return papel_no_quadro(user_nome, quadro_id, eh_admin_geral) in _PODE_GERENCIAR


def listar_quadros_visiveis(user_nome, eh_admin_geral=False,
                            incluir_arquivados=False):
    """Quadros que o usuário pode ver: os seus, os que aceitou e os da unidade.

    A unidade entra por nome normalizado: a lotação do servidor (ou a
    unidade, na falta dela) tem de bater com a unidade do quadro. É o que
    faz "cada unidade trata as suas atividades" sem o quadro saber de
    matrícula nenhuma.
    """
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        sql = "SELECT " + ", ".join(_CAMPOS_QUADRO) + " FROM tb_os_quadro WHERE 1=1"
        params = []
        if not incluir_arquivados:
            sql += " AND arquivado=0"
        sql += " ORDER BY nome ASC"
        cur.execute(sql, params)
        quadros = [_para_dict(_CAMPOS_QUADRO, linha)
                   for linha in cur.fetchall()]
        if not quadros:
            return []
        por_id = {q["id"]: q for q in quadros}
        papeis = {}
        for qid in por_id:
            papeis.update(papeis_do_quadro(qid))
        unidade_usuario = None if eh_admin_geral else _unidade_do_usuario(user_nome)
        visiveis = []
        for quadro in quadros:
            if (quadro.get("dono_user_nome") or "") == (user_nome or ""):
                visiveis.append(dict(quadro, meu_papel="dono"))
                continue
            papel = papeis.get(user_nome)
            if papel:
                visiveis.append(dict(quadro, meu_papel=papel))
                continue
            if quadro.get("visibilidade") == "unidade" \
                    and _mesma_unidade(quadro, unidade_usuario):
                visiveis.append(dict(quadro, meu_papel="unidade"))
                continue
            if eh_admin_geral:
                visiveis.append(dict(quadro, meu_papel="administrador"))
        return visiveis
    except Exception:
        _log().exception("listar_quadros_visiveis falhou")
        return []
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def atualizar_quadro(quadro_id, campos, ator="", eh_admin_geral=False):
    """Altera os dados do quadro (nome, descrição, cor, unidade, formato do número).

    `campos` é um dicionário; só as chaves conhecidas são usadas. O formato
    do número NÃO renumera ordens de serviço já criadas.

    Returns:
        tuple: (ok, mensagem)
    """
    conn = None
    try:
        quadro_id = int(quadro_id)
        if not pode_gerenciar(ator, quadro_id, eh_admin_geral):
            return (False, "Só quem administra o quadro pode alterá-lo.")
        atual = obter_quadro(quadro_id)
        if not atual:
            return (False, "Quadro não encontrado.")
        nome = (campos.get("nome", atual["nome"]) or "").strip()
        if len(nome) < 2:
            return (False, "Dê um nome ao quadro (mínimo 2 letras).")
        vis = campos.get("visibilidade", atual["visibilidade"])
        if vis not in VISIBILIDADES:
            vis = atual["visibilidade"]
        unidade_nome = (campos.get("unidade_nome", atual["unidade_nome"]) or "").strip()
        if vis == "unidade" and not unidade_nome:
            return (False, "Quadro de unidade precisa da unidade.")
        unidade_id = campos.get("unidade_id", atual["unidade_id"])
        prefixo = campos.get("prefixo_numero")
        prefixo = normalizar_prefixo(prefixo) if prefixo is not None \
            else (atual["prefixo_numero"] or "")
        digitos = validar_digitos(campos.get("digitos_numero",
                                             atual["digitos_numero"]))
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "UPDATE tb_os_quadro SET nome=?, descricao=?, cor=?, unidade_id=?, "
            "unidade_nome=?, visibilidade=?, prefixo_numero=?, digitos_numero=? "
            "WHERE id=?",
            (nome, (campos.get("descricao", atual["descricao"]) or "").strip(),
             (campos.get("cor", atual["cor"]) or "").strip(),
             int(unidade_id) if unidade_id else None, unidade_nome, vis,
             prefixo, digitos, quadro_id))
        _commit_com_retry(conn, contexto="atualizar_quadro")
        _auditar(ator, "atualizar_quadro", f"quadro {quadro_id}",
                 f"nome={nome} visibilidade={vis}")
        return (True, "Quadro atualizado.")
    except Exception:
        _rollback_seguro(conn, contexto="atualizar_quadro")
        _log().exception("atualizar_quadro falhou")
        return (False, "Erro ao atualizar o quadro.")
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def arquivar_quadro(quadro_id, arquivar=True, ator="", eh_admin_geral=False):
    """Arquiva (ou desarquiva) o quadro. Nenhum cartão é apagado."""
    conn = None
    try:
        quadro_id = int(quadro_id)
        if not pode_gerenciar(ator, quadro_id, eh_admin_geral):
            return (False, "Só quem administra o quadro pode arquivá-lo.")
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE tb_os_quadro SET arquivado=? WHERE id=?",
                    (1 if arquivar else 0, quadro_id))
        _commit_com_retry(conn, contexto="arquivar_quadro")
        _auditar(ator, "arquivar_quadro", f"quadro {quadro_id}",
                 "arquivado" if arquivar else "desarquivado")
        return (True, "Quadro arquivado." if arquivar else "Quadro restaurado.")
    except Exception:
        _rollback_seguro(conn, contexto="arquivar_quadro")
        _log().exception("arquivar_quadro falhou")
        return (False, "Erro ao arquivar o quadro.")
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def excluir_quadro(quadro_id, ator="", eh_admin_geral=False):
    """Exclui o quadro e TUDO que é dele, na ordem certa, em transação curta.

    O tradutor de DDL do Postgres remove as chaves estrangeiras, então a
    cascata é feita à mão: eventos e comentários, depois as ordens de
    serviço, depois convites, colunas, sequência e por fim o quadro.

    Returns:
        tuple: (ok, mensagem)
    """
    conn = None
    try:
        quadro_id = int(quadro_id)
        if not pode_gerenciar(ator, quadro_id, eh_admin_geral):
            return (False, "Só quem administra o quadro pode excluí-lo.")
        conn = get_connection()
        cur = conn.cursor()
        for tabela in ("tb_os_evento", "tb_os_comentario", "tb_os_ordem",
                       "tb_os_convite", "tb_os_coluna", "tb_os_sequencia"):
            cur.execute(f"DELETE FROM {tabela} WHERE quadro_id=?", (quadro_id,))
        cur.execute("DELETE FROM tb_os_quadro WHERE id=?", (quadro_id,))
        _commit_com_retry(conn, contexto="excluir_quadro")
        _auditar(ator, "excluir_quadro", f"quadro {quadro_id}")
        return (True, "Quadro excluído.")
    except Exception:
        _rollback_seguro(conn, contexto="excluir_quadro")
        _log().exception("excluir_quadro falhou")
        return (False, "Erro ao excluir o quadro.")
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


# ============ convites ============

def _ficha_do_convidado(user_nome):
    """(nome_exibicao, unidade) do servidor, pelo cadastro do módulo de usuários.

    A busca é feita pela FACHADA do núcleo: o módulo de ordens de serviço
    conhece o nome que a pessoa deve ler, nunca a matrícula crua sozinha.
    Falha aqui devolve vazio — o convite ainda é registrado pelo login.
    """
    try:
        alvo = (user_nome or "").strip()
        if not alvo:
            return ("", "")
        achados = _integracoes().buscar_usuarios_gestao(termo=alvo,
                                                        limite=20) or []
        for achado in achados:
            if str(achado.get("user_nome") or "").strip().lower() == alvo.lower():
                return (achado.get("nome_exibicao") or user_nome or "",
                        achado.get("unidade") or achado.get("lotacao") or "")
        if achados:
            return (achados[0].get("nome_exibicao") or user_nome or "",
                    achados[0].get("unidade") or achados[0].get("lotacao") or "")
        return (user_nome or "", "")
    except Exception:
        try:
            _log().warning(f"_ficha_do_convidado({user_nome}) falhou — "
                           "seguindo só com o login")
        except Exception:
            pass
        return (user_nome or "", "")


def convidar_usuario(quadro_id, convidado_user_nome, papel, ator="",
                     eh_admin_geral=False, recado=""):
    """Convida um servidor cadastrado para integrar o quadro, com papel.

    Convite repetido para quem já está dentro renova o papel (sem criar
    segunda linha). Para quem já tem convite pendente, o papel é atualizado
    e o convite continua pendente.

    Returns:
        tuple: (ok, mensagem)
    """
    conn = None
    try:
        quadro_id = int(quadro_id)
        convidado = (convidado_user_nome or "").strip()
        if not pode_gerenciar(ator, quadro_id, eh_admin_geral):
            return (False, "Só quem administra o quadro pode convidar.")
        if not convidado:
            return (False, "Escolha o servidor que vai participar do quadro.")
        if papel not in PAPEIS:
            return (False, "Papel inválido no quadro.")
        quadro = obter_quadro(quadro_id)
        if not quadro:
            return (False, "Quadro não encontrado.")
        if (quadro.get("dono_user_nome") or "") == convidado:
            return (False, "O dono do quadro já participa dele.")
        nome_exibicao, unidade = _ficha_do_convidado(convidado)
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, status FROM tb_os_convite "
                    "WHERE quadro_id=? AND convidado_user_nome=?",
                    (quadro_id, convidado))
        existente = cur.fetchone()
        if existente:
            cur.execute("UPDATE tb_os_convite SET papel=?, nome_exibicao=?, "
                        "unidade=?, recado=? WHERE id=?",
                        (papel, nome_exibicao, unidade, (recado or "").strip(),
                         existente[0]))
            mensagem = ("Papel do convite atualizado."
                        if existente[1] == "pendente"
                        else f"{nome_exibicao} já participa como {papel}.")
        else:
            cur.execute(
                "INSERT INTO tb_os_convite "
                "(quadro_id, convidado_user_nome, nome_exibicao, unidade, papel, "
                " status, convidado_por, data_convite, data_resposta, recado) "
                "VALUES (?, ?, ?, ?, ?, 'pendente', ?, ?, '', ?)",
                (quadro_id, convidado, nome_exibicao, unidade, papel, ator or "",
                 _agora(), (recado or "").strip()))
            mensagem = f"Convite pendente para {nome_exibicao} ({papel})."
        _commit_com_retry(conn, contexto="convidar_usuario")
        _auditar(ator, "convidar_usuario", f"quadro {quadro_id}",
                 f"convidado={convidado} papel={papel}")
        return (True, mensagem)
    except Exception:
        _rollback_seguro(conn, contexto="convidar_usuario")
        _log().exception("convidar_usuario falhou")
        return (False, "Erro ao enviar o convite.")
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def responder_convite(convite_id, user_nome, aceitar=True, recado=""):
    """Aceita (ou recusa) o convite recebido.

    Returns:
        tuple: (ok, mensagem, nome_quadro ou '')
    """
    conn = None
    try:
        convite_id = int(convite_id)
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT quadro_id, convidado_user_nome, nome_exibicao, status "
                    "FROM tb_os_convite WHERE id=?", (convite_id,))
        linha = cur.fetchone()
        if not linha:
            return (False, "Convite não encontrado.", "")
        quadro_id, convidado, _nome, status = linha
        if (convidado or "") != (user_nome or ""):
            return (False, "Este convite não é seu.", "")
        if status != "pendente":
            return (False, "Este convite já foi respondido.", "")
        novo_status = "aceito" if aceitar else "recusado"
        cur.execute("UPDATE tb_os_convite SET status=?, data_resposta=?, recado=? "
                    "WHERE id=?", (novo_status, _agora(), (recado or "").strip(),
                                   convite_id))
        quadro = obter_quadro(quadro_id)
        nome_quadro = (quadro or {}).get("nome") or ""
        _commit_com_retry(conn, contexto="responder_convite")
        _auditar(user_nome, "responder_convite", f"convite {convite_id}",
                 f"quadro={nome_quadro} resposta={novo_status}")
        verb = "aceito" if aceitar else "recusado"
        return (True, f"Convite {verb}: {nome_quadro}", nome_quadro)
    except Exception:
        _rollback_seguro(conn, contexto="responder_convite")
        _log().exception("responder_convite falhou")
        return (False, "Erro ao responder o convite.", "")
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def listar_convites_pendentes(user_nome):
    """Convites aguardando resposta de quem esta logado."""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT " + ", ".join(_CAMPOS_CONVITE) +
                    " FROM tb_os_convite WHERE convidado_user_nome=? "
                    "AND status='pendente' ORDER BY id DESC",
                    ((user_nome or "").strip(),))
        itens = [_para_dict(_CAMPOS_CONVITE, linha) for linha in cur.fetchall()]
        for item in itens:
            quadro = obter_quadro(item["quadro_id"])
            item["quadro_nome"] = (quadro or {}).get("nome") or "(quadro removido)"
        return itens
    except Exception:
        _log().exception("listar_convites_pendentes falhou")
        return []
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def listar_convites_quadro(quadro_id):
    """Todos os convites do quadro (pendentes, aceitos, recusados)."""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT " + ", ".join(_CAMPOS_CONVITE) +
                    " FROM tb_os_convite WHERE quadro_id=? ORDER BY id DESC",
                    (int(quadro_id),))
        return [_para_dict(_CAMPOS_CONVITE, linha) for linha in cur.fetchall()]
    except Exception:
        _log().exception("listar_convites_quadro falhou")
        return []
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def cancelar_convite(convite_id, ator="", eh_admin_geral=False):
    """Cancela um convite pendente (ou remove a participacao de quem aceitou)."""
    conn = None
    try:
        convite_id = int(convite_id)
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT quadro_id, convidado_user_nome, status FROM tb_os_convite "
                    "WHERE id=?", (convite_id,))
        linha = cur.fetchone()
        if not linha:
            return (False, "Convite não encontrado.")
        quadro_id, convidado, status = linha
        if status not in ("pendente", "aceito"):
            return (False, "Convite já respondido não pode ser cancelado.")
        if not pode_gerenciar(ator, quadro_id, eh_admin_geral):
            return (False, "Só quem administra o quadro pode cancelar o convite.")
        cur.execute("UPDATE tb_os_convite SET status='cancelado', data_resposta=? "
                    "WHERE id=?", (_agora(), convite_id))
        _commit_com_retry(conn, contexto="cancelar_convite")
        _auditar(ator, "cancelar_convite", f"convite {convite_id}",
                 f"convidado={convidado} status_anterior={status}")
        return (True, "Convite cancelado — o servidor não participa mais.")
    except Exception:
        _rollback_seguro(conn, contexto="cancelar_convite")
        _log().exception("cancelar_convite falhou")
        return (False, "Erro ao cancelar o convite.")
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


# ============ colunas ============

def listar_colunas(quadro_id):
    """Colunas do quadro na ordem em que aparecem no quadro."""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT " + ", ".join(_CAMPOS_COLUNA) +
                    " FROM tb_os_coluna WHERE quadro_id=? ORDER BY ordem ASC, id ASC",
                    (int(quadro_id),))
        return [_para_dict(_CAMPOS_COLUNA, linha) for linha in cur.fetchall()]
    except Exception:
        _log().exception("listar_colunas falhou")
        return []
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def _renumerar_colunas(cur, quadro_id):
    """Reescreve a ordem das colunas como 1..N, na ordem atual do banco."""
    cur.execute("SELECT id FROM tb_os_coluna WHERE quadro_id=? "
                "ORDER BY ordem ASC, id ASC", (int(quadro_id),))
    ids = [linha[0] for linha in cur.fetchall()]
    for indice, coluna_id in enumerate(ids, start=1):
        cur.execute("UPDATE tb_os_coluna SET ordem=? WHERE id=?",
                    (indice, coluna_id))
    return len(ids)


def _quadro_da_coluna(coluna_id):
    """Id do quadro de uma coluna, ou None."""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT quadro_id FROM tb_os_coluna WHERE id=?",
                    (int(coluna_id),))
        linha = cur.fetchone()
        return linha[0] if linha else None
    except Exception:
        _log().exception("_quadro_da_coluna falhou")
        return None
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def criar_coluna(quadro_id, nome, cor="", ator="", eh_admin_geral=False,
                 conclusiva=False):
    """Cria uma coluna nova no quadro (limite de 30 colunas por quadro)."""
    conn = None
    try:
        quadro_id = int(quadro_id)
        if not pode_gerenciar(ator, quadro_id, eh_admin_geral):
            return (False, "Só quem administra o quadro cria coluna.")
        titulo = (nome or "").strip()
        if len(titulo) < 1:
            return (False, "Dê um nome à coluna.")
        colunas = listar_colunas(quadro_id)
        if not colunas:
            return (False, "Quadro sem colunas — recrie o quadro.")
        if len(colunas) >= LIMITE_COLUNAS_POR_QUADRO:
            return (False, "O quadro chegou ao limite de "
                           f"{LIMITE_COLUNAS_POR_QUADRO} colunas.")
        if _norm(titulo) in {_norm(c["nome"]) for c in colunas}:
            return (False, "Já existe uma coluna com esse nome.")
        conn = get_connection()
        cur = conn.cursor()
        _renumerar_colunas(cur, quadro_id)
        if conclusiva:
            cur.execute("UPDATE tb_os_coluna SET conclusiva=0 WHERE quadro_id=?",
                        (quadro_id,))
        cur.execute("INSERT INTO tb_os_coluna "
                    "(quadro_id, nome, ordem, cor, conclusiva, data_criacao) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (quadro_id, titulo, len(colunas) + 1, (cor or "").strip(),
                     1 if conclusiva else 0, _agora()))
        _commit_com_retry(conn, contexto="criar_coluna")
        _auditar(ator, "criar_coluna", f"quadro {quadro_id}", f"nome={titulo}")
        return (True, f"Coluna criada: {titulo}")
    except Exception:
        _rollback_seguro(conn, contexto="criar_coluna")
        _log().exception("criar_coluna falhou")
        return (False, "Erro ao criar a coluna.")
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def renomear_coluna(coluna_id, nome, ator="", eh_admin_geral=False):
    """Renomeia uma coluna existente."""
    conn = None
    try:
        coluna_id = int(coluna_id)
        titulo = (nome or "").strip()
        if not titulo:
            return (False, "Informe o nome da coluna.")
        quadro_id = _quadro_da_coluna(coluna_id)
        if not quadro_id:
            return (False, "Coluna não encontrada.")
        if not pode_gerenciar(ator, quadro_id, eh_admin_geral):
            return (False, "Só quem administra o quadro renomeia coluna.")
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE tb_os_coluna SET nome=? WHERE id=?", (titulo, coluna_id))
        _commit_com_retry(conn, contexto="renomear_coluna")
        _auditar(ator, "renomear_coluna", f"coluna {coluna_id}", f"nome={titulo}")
        return (True, f"Coluna renomeada: {titulo}")
    except Exception:
        _rollback_seguro(conn, contexto="renomear_coluna")
        _log().exception("renomear_coluna falhou")
        return (False, "Erro ao renomear a coluna.")
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def mover_coluna(quadro_id, ordem_ids, ator="", eh_admin_geral=False):
    """Reordena as colunas do quadro. Recebe os ids na ordem desejada.

    A coluna de conclusão é sempre empurrada para o fim: é ela que marca a
    ordem de serviço como concluída, e ela precisa ser a mesma para todo
    mundo do quadro.
    """
    conn = None
    try:
        quadro_id = int(quadro_id)
        if not pode_gerenciar(ator, quadro_id, eh_admin_geral):
            return (False, "Só quem administra o quadro reordena as colunas.")
        colunas = listar_colunas(quadro_id)
        if len(colunas) < 2:
            return (False, "O quadro precisa de pelo menos 2 colunas "
                           "para reordenar.")
        conhecidos = {c["id"] for c in colunas}
        try:
            lista = [int(i) for i in (ordem_ids or [])]
        except (TypeError, ValueError):
            return (False, "Ordem das colunas inválida.")
        if len(lista) != len(colunas) or set(lista) != conhecidos:
            return (False, "Ordem das colunas inválida.")
        conclusivas = [c["id"] for c in colunas if c["conclusiva"]]
        outras = [i for i in lista if i not in conclusivas]
        finais = conclusivas or [lista[-1]]
        conn = get_connection()
        cur = conn.cursor()
        for posicao, coluna_id in enumerate(outras, start=1):
            cur.execute("UPDATE tb_os_coluna SET ordem=? WHERE id=?",
                        (posicao, coluna_id))
        posicao = len(outras)
        for coluna_id in finais:
            posicao += 1
            cur.execute("UPDATE tb_os_coluna SET ordem=? WHERE id=?",
                        (posicao, coluna_id))
        _commit_com_retry(conn, contexto="mover_coluna")
        _auditar(ator, "mover_coluna", f"quadro {quadro_id}",
                 "ordem=" + ">".join(str(i) for i in outras + finais))
        return (True, "Colunas reordenadas.")
    except Exception:
        _rollback_seguro(conn, contexto="mover_coluna")
        _log().exception("mover_coluna falhou")
        return (False, "Erro ao reordenar as colunas.")
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def excluir_coluna(coluna_id, ator="", eh_admin_geral=False):
    """Exclui uma coluna. Com ordens de serviço dentro, a coluna não vai."""
    conn = None
    try:
        coluna_id = int(coluna_id)
        quadro_id = _quadro_da_coluna(coluna_id)
        if not quadro_id:
            return (False, "Coluna não encontrada.")
        if not pode_gerenciar(ator, quadro_id, eh_admin_geral):
            return (False, "Só quem administra o quadro exclui coluna.")
        colunas = listar_colunas(quadro_id)
        if len(colunas) <= 2:
            return (False, "O quadro precisa de pelo menos 2 colunas.")
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM tb_os_ordem WHERE coluna_id=? "
                    "AND arquivado=0", (coluna_id,))
        total = (cur.fetchone() or [0])[0]
        if total:
            return (False, f"A coluna tem {total} ordem(ns) de serviço. "
                           "Mova ou arquive antes de excluir.")
        cur.execute("DELETE FROM tb_os_coluna WHERE id=?", (coluna_id,))
        _renumerar_colunas(cur, quadro_id)
        _commit_com_retry(conn, contexto="excluir_coluna")
        _auditar(ator, "excluir_coluna", f"coluna {coluna_id}")
        return (True, "Coluna excluída.")
    except Exception:
        _rollback_seguro(conn, contexto="excluir_coluna")
        _log().exception("excluir_coluna falhou")
        return (False, "Erro ao excluir a coluna.")
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


# ============ ordens de serviço (o cartão) ============

def _normalizar_prazo(data_vencimento):
    """Aceita `YYYY-MM-DD` ou `YYYY-MM-DD HH:MM` e devolve `YYYY-MM-DD`.

    O prazo é uma data, não um instante: o servidor precisa saber 'até
    quando', não 'que horas'."""
    bruto = (data_vencimento or "").strip()
    if not bruto:
        return ""
    try:
        return datetime.strptime(bruto[:10], "%Y-%m-%d").strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return ""


def _normalizar_rotulos(rotulos):
    """Rótulos separados por vírgula, sem repetição, até 8."""
    vistos, saida = set(), []
    for parte in str(rotulos or "").split(","):
        rotulo = parte.strip()[:30]
        chave = _norm(rotulo)
        if not rotulo or chave in vistos or len(saida) >= 8:
            continue
        vistos.add(chave)
        saida.append(rotulo)
    return ", ".join(saida)


def _reordenar_ordens(cur, coluna_id):
    """Reescreve a posição das ordens de serviço da coluna como 1..N.

    A posição é um INTEIRO e a reordenação é por TROCA de posições — nunca
    fração no meio, que é o que produz empate quando dois servidores
    mexem no mesmo cartão ao mesmo tempo."""
    cur.execute("SELECT id FROM tb_os_ordem WHERE coluna_id=? "
                "ORDER BY ordem ASC, id ASC", (int(coluna_id),))
    ids = [linha[0] for linha in cur.fetchall()]
    for posicao, ordem_id in enumerate(ids, start=1):
        cur.execute("UPDATE tb_os_ordem SET ordem=? WHERE id=?",
                    (posicao, ordem_id))
    return len(ids)


def _ultima_posicao(cur, coluna_id):
    cur.execute("SELECT MAX(ordem) FROM tb_os_ordem WHERE coluna_id=?",
                (int(coluna_id),))
    linha = cur.fetchone()
    return int(linha[0] or 0) if linha else 0


def obter_ordem(ordem_id):
    """Dados de uma ordem de serviço, ou None."""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT " + ", ".join(_CAMPOS_ORDEM) +
                    " FROM tb_os_ordem WHERE id=?", (int(ordem_id),))
        return _para_dict(_CAMPOS_ORDEM, cur.fetchone())
    except Exception:
        _log().exception("obter_ordem falhou")
        return None
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def _coluna(quadro_id, coluna_id, cur):
    """A coluna precisa PERTENCER ao quadro — é o que impede o cartão de
    cair num quadro alheio por parâmetro adulterado."""
    cur.execute("SELECT id, nome, conclusiva FROM tb_os_coluna "
                "WHERE id=? AND quadro_id=?", (int(coluna_id), int(quadro_id)))
    return cur.fetchone()


def criar_ordem_servico(quadro_id, coluna_id, titulo, descricao="",
                        prioridade="media", responsavel_user_nome="",
                        rotulos="", data_vencimento="", ator="",
                        eh_admin_geral=False):
    """Cria a ordem de serviço e RESERVA o número do quadro na mesma transação.

    O número é alocado dentro da transação do INSERT: `UPDATE ... SET
    ultimo_numero = ultimo_numero + 1` seguido do `SELECT` na MESMA
    transação é o que serializa a reserva no banco (o Python não segura
    nada). Se a transação falhar, o contador volta junto — buraco nenhum,
    número repetido nenhum. Duas pessoas criando cartão no mesmo quadro no
    mesmo instante recebem números diferentes, porque a segunda espera o
    commit da primeira.

    Returns:
        tuple: (ok, mensagem, numero_gerado ou '')
    """
    ultimo_erro = None
    for tentativa in range(1, TENTATIVAS_LOCKED + 1):
        conn = None
        try:
            quadro_id = int(quadro_id)
            coluna_id = int(coluna_id)
            nome_cartao = (titulo or "").strip()
            if not pode_editar(ator, quadro_id, eh_admin_geral):
                return (False, "Você não pode criar ordens de serviço "
                               "neste quadro.", "")
            if len(nome_cartao) < 3:
                return (False, "Dê um título à ordem de serviço "
                               "(mínimo 3 letras).", "")
            if prioridade not in PRIORIDADES:
                prioridade = "media"
            quadro = obter_quadro(quadro_id)
            if not quadro:
                return (False, "Quadro não encontrado.", "")
            if not quadro.get("ativo"):
                return (False, "Este quadro está desativado.", "")

            conn = get_connection()
            cur = conn.cursor()
            coluna = _coluna(quadro_id, coluna_id, cur)
            if not coluna:
                return (False, "Coluna não pertence a este quadro.", "")
            # ---- reserva do número (serializada pelo banco) ----
            sequencial = _reservar_numero(cur, quadro_id)
            numero = montar_numero(quadro.get("prefixo_numero") or "OS",
                                   sequencial, quadro.get("digitos_numero"))
            agora = _agora()
            cur.execute(
                "INSERT INTO tb_os_ordem "
                "(quadro_id, coluna_id, numero_sequencial, numero, titulo, "
                " descricao, ordem, prioridade, responsavel_user_nome, rotulos, "
                " data_vencimento, criado_por, criado_em, movido_em, "
                " concluido_em, arquivado) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)",
                (quadro_id, coluna_id, sequencial, numero, nome_cartao,
                 (descricao or "").strip(), _ultima_posicao(cur, coluna_id) + 1,
                 prioridade, (responsavel_user_nome or "").strip(),
                 _normalizar_rotulos(rotulos),
                 _normalizar_prazo(data_vencimento), ator or "", agora, agora,
                 agora if coluna[2] else ""))
            ordem_id = int(cur.lastrowid)
            _registrar_evento(
                conn, ordem_id, quadro_id, "criacao", ator,
                f"Criou a ordem de serviço {numero} na coluna “{coluna[1]}”")
            _reordenar_ordens(cur, coluna_id)
            _commit_com_retry(conn, contexto=f"criar_ordem_servico:{quadro_id}")
            _auditar(ator, "criar_ordem_servico", f"ordem {numero}",
                     f"quadro {quadro_id} coluna={coluna[1]}")
            return (True, f"Ordem de serviço {numero} criada.", numero)
        except Exception as exc:
            ultimo_erro = exc
            _rollback_seguro(conn, contexto="criar_ordem_servico")
            if _eh_bloqueio_banco(exc) and tentativa < TENTATIVAS_LOCKED:
                try:
                    _log().warning("criar_ordem_servico: quadro ocupado, "
                                   f"tentativa {tentativa}/{TENTATIVAS_LOCKED}")
                except Exception:
                    pass
                try:
                    time.sleep(ESPERA_LOCKED_SEG * tentativa)
                except Exception:
                    pass
                continue
            try:
                _log().exception("criar_ordem_servico falhou")
            except Exception:
                pass
            return (False, "Erro ao criar a ordem de serviço.", "")
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
    try:
        _log().error(f"criar_ordem_servico: quadro travado após "
                     f"{TENTATIVAS_LOCKED} tentativas ({ultimo_erro})")
    except Exception:
        pass
    return (False, "O quadro está muito movementado. Tente de novo.", "")


def listar_ordens(quadro_id, coluna_id=None, incluir_arquivadas=False,
                  responsavel="", atraso=False, nao_concluidas=False):
    """Ordens de serviço do quadro, na ordem em que aparecem nas colunas.

    Serve às visões: por coluna, por quadro, 'meus cartões', 'atrasados'
    (vencimento vencido e não concluído) e 'sem responsável'."""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        sql = "SELECT " + ", ".join(_CAMPOS_ORDEM) + " FROM tb_os_ordem WHERE quadro_id=?"
        params = [int(quadro_id)]
        if coluna_id:
            sql += " AND coluna_id=?"
            params.append(int(coluna_id))
        if not incluir_arquivadas:
            sql += " AND arquivado=0"
        if responsavel:
            sql += " AND responsavel_user_nome=?"
            params.append(responsavel)
        if nao_concluidas:
            sql += " AND concluido_em=''"
        if atraso:
            sql += (" AND data_vencimento<>'' AND data_vencimento<? "
                    " AND concluido_em=''")
            params.append(datetime.now().strftime("%Y-%m-%d"))
        sql += " ORDER BY ordem ASC, numero_sequencial ASC"
        cur.execute(sql, params)
        itens = [_para_dict(_CAMPOS_ORDEM, linha) for linha in cur.fetchall()]
        nomes_coluna = {c["id"]: c["nome"] for c in listar_colunas(quadro_id)}
        for item in itens:
            item["coluna_nome"] = nomes_coluna.get(item["coluna_id"], "(coluna removida)")
        # o atraso é calculado em Python: a data de hoje muda durante a
        # consulta e a comparação por texto varyria de fuso para fuso.
        hoje = datetime.now().strftime("%Y-%m-%d")
        for item in itens:
            item["atrasada"] = bool(item["data_vencimento"]
                                    and item["data_vencimento"] < hoje
                                    and not item["concluido_em"])
        return itens
    except Exception:
        _log().exception("listar_ordens falhou")
        return []
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def listar_minhas_ordens(user_nome, eh_admin_geral=False, atraso=False):
    """'Meus cartões': onde a pessoa é responsável, em todos os quadros que ela vê.

    Também entra o que ela criou sem responsável — do contrário a pessoa
    perde de vista a ordem de serviço que acabou de abrir."""
    itens = []
    try:
        for quadro in listar_quadros_visiveis(user_nome, eh_admin_geral):
            todos = listar_ordens(quadro["id"], atraso=atraso)
            for item in todos:
                if (item.get("responsavel_user_nome") or "") == (user_nome or "") \
                        or (item.get("criado_por") or "") == (user_nome or ""):
                    itens.append(dict(item, quadro_nome=quadro["nome"],
                                      quadro_cor=quadro.get("cor") or ""))
        return itens
    except Exception:
        _log().exception("listar_minhas_ordens falhou")
        return []


def listar_atrasadas(user_nome, eh_admin_geral=False):
    """Ordens de serviço com vencimento vencido e ainda não concluídas."""
    return listar_minhas_ordens(user_nome, eh_admin_geral, atraso=True)


def mover_ordem(ordem_id, coluna_destino_id, posicao=None, ator="",
                eh_admin_geral=False):
    """Move a ordem de serviço para outra coluna e/ou para outra posição.

    Concluir NÃO é apagar: chegar na coluna de conclusão marca `concluido_em`
    e registra o evento. Tirar de volta (reabrir) também vira evento — quem
    pegou o serviço depois precisa saber que ele voltou.

    Returns:
        tuple: (ok, mensagem)
    """
    conn = None
    try:
        ordem_id = int(ordem_id)
        atual = obter_ordem(ordem_id)
        if not atual:
            return (False, "Ordem de serviço não encontrada.")
        quadro_id = int(atual["quadro_id"])
        if not pode_editar(ator, quadro_id, eh_admin_geral):
            return (False, "Você não pode mover ordens de serviço "
                           "neste quadro.")
        destino = int(coluna_destino_id)
        agora = _agora()
        conn = get_connection()
        cur = conn.cursor()
        nova = _coluna(quadro_id, destino, cur)
        if not nova:
            return (False, "Coluna não pertence a este quadro.")
        origem_id = int(atual["coluna_id"])
        _reordenar_ordens(cur, origem_id)
        concluia_antes = bool(atual["concluido_em"])
        concluindo = bool(nova[2])
        concluida = agora if concluindo else ""
        cur.execute("UPDATE tb_os_ordem SET coluna_id=?, ordem=?, movido_em=?, "
                    "concluido_em=? WHERE id=?",
                    (destino, _ultima_posicao(cur, destino) + 1, agora,
                     concluida, ordem_id))
        _reordenar_ordens(cur, destino)
        if posicao is not None:
            _posicionar_ordem(cur, destino, ordem_id, int(posicao))
        cur.execute("SELECT nome FROM tb_os_coluna WHERE id=?", (origem_id,))
        linha_origem = cur.fetchone()
        nome_origem = (linha_origem[0] if linha_origem else "(coluna removida)")
        if destino != origem_id:
            _registrar_evento(
                conn, ordem_id, quadro_id, "movimento", ator,
                f"Moveu de “{nome_origem}” para “{nova[1]}”")
        else:
            _registrar_evento(conn, ordem_id, quadro_id, "movimento", ator,
                              f"Reordenou dentro de “{nova[1]}”")
        if concluindo and not concluia_antes:
            _registrar_evento(conn, ordem_id, quadro_id, "conclusao", ator,
                              f"Concluiu em {agora[:10]} (coluna “{nova[1]}”)")
        elif not concluindo and concluia_antes:
            _registrar_evento(conn, ordem_id, quadro_id, "reabertura", ator,
                              f"Reabriu a ordem de serviço (voltou para "
                              f"“{nova[1]}”)")
        _commit_com_retry(conn, contexto="mover_ordem")
        _auditar(ator, "mover_ordem", f"ordem {atual['numero']}",
                 f"de={nome_origem} para={nova[1]} concluida={bool(concluida)}")
        if concluindo and not concluia_antes:
            return (True, f"Ordem {atual['numero']} concluída em {agora[:10]}.")
        if not concluindo and concluia_antes:
            return (True, f"Ordem {atual['numero']} reaberta.")
        return (True, f"Ordem {atual['numero']} movida para “{nova[1]}”.")
    except Exception:
        _rollback_seguro(conn, contexto="mover_ordem")
        _log().exception("mover_ordem falhou")
        return (False, "Erro ao mover a ordem de serviço.")
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def _posicionar_ordem(cur, coluna_id, ordem_id, posicao):
    """Coloca a ordem de serviço numa posição exata da coluna (troca de inteiros)."""
    try:
        posicao = max(1, int(posicao))
    except (TypeError, ValueError):
        return 0
    cur.execute("SELECT id FROM tb_os_ordem WHERE coluna_id=? "
                "ORDER BY ordem ASC, id ASC", (int(coluna_id),))
    ids = [linha[0] for linha in cur.fetchall() if linha[0] != int(ordem_id)]
    ids.insert(min(posicao - 1, len(ids)), int(ordem_id))
    for indice, oid in enumerate(ids, start=1):
        cur.execute("UPDATE tb_os_ordem SET ordem=? WHERE id=?", (indice, oid))
    return len(ids)


def atualizar_ordem(ordem_id, campos, ator="", eh_admin_geral=False):
    """Edita a ordem de serviço e registra CADA mudança na linha do tempo.

    A responsável e a prioridade têm evento próprio (são as duas coisas que o
    chamador mais pergunta: 'de quem é?' e 'é urgente?'); título, descrição,
    rótulos e prazo entram como edição.

    Returns:
        tuple: (ok, mensagem)
    """
    conn = None
    try:
        ordem_id = int(ordem_id)
        atual = obter_ordem(ordem_id)
        if not atual:
            return (False, "Ordem de serviço não encontrada.")
        quadro_id = int(atual["quadro_id"])
        if not pode_editar(ator, quadro_id, eh_admin_geral):
            return (False, "Você não pode editar ordens de serviço "
                           "neste quadro.")
        titulo = (campos.get("titulo", atual["titulo"]) or "").strip()
        if len(titulo) < 3:
            return (False, "O título da ordem de serviço precisa de "
                           "pelo menos 3 letras.")
        descricao = (campos.get("descricao", atual["descricao"]) or "").strip()
        prioridade = (campos.get("prioridade", atual["prioridade"]) or "").strip()
        if prioridade not in PRIORIDADES:
            prioridade = atual["prioridade"]
        responsavel = (campos.get("responsavel_user_nome",
                                  atual["responsavel_user_nome"]) or "").strip()
        rotulos = _normalizar_rotulos(campos.get("rotulos", atual["rotulos"]))
        prazo = campos.get("data_vencimento", atual["data_vencimento"])
        prazo = _normalizar_prazo(prazo) if prazo is not None \
            else (atual["data_vencimento"] or "")

        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "UPDATE tb_os_ordem SET titulo=?, descricao=?, prioridade=?, "
            "responsavel_user_nome=?, rotulos=?, data_vencimento=? WHERE id=?",
            (titulo, descricao, prioridade, responsavel, rotulos, prazo, ordem_id))
        numero = atual["numero"] or ordem_id
        if titulo != atual["titulo"]:
            _registrar_evento(conn, ordem_id, quadro_id, "edicao", ator,
                              f"Título: “{atual['titulo']}” → “{titulo}”")
        elif descricao != atual["descricao"]:
            _registrar_evento(conn, ordem_id, quadro_id, "edicao", ator,
                              "Atualizou a descrição")
        elif rotulos != (atual["rotulos"] or ""):
            _registrar_evento(conn, ordem_id, quadro_id, "edicao", ator,
                              f"Rótulos: {rotulos or '(sem rótulo)'}")
        elif prazo != (atual["data_vencimento"] or ""):
            _registrar_evento(conn, ordem_id, quadro_id, "edicao", ator,
                              f"Prazo: {prazo or '(sem prazo)'}")
        if responsavel != (atual["responsavel_user_nome"] or ""):
            nome_antigo = _ficha_do_convidado(atual["responsavel_user_nome"])[0] \
                or "sem responsável"
            nome_novo = _ficha_do_convidado(responsavel)[0] or "sem responsável"
            _registrar_evento(conn, ordem_id, quadro_id, "responsavel", ator,
                              f"Responsável: {nome_antigo} → {nome_novo}")
        if prioridade != (atual["prioridade"] or ""):
            _registrar_evento(conn, ordem_id, quadro_id, "prioridade", ator,
                              f"Prioridade: {atual['prioridade']} → {prioridade}")
        _commit_com_retry(conn, contexto="atualizar_ordem")
        _auditar(ator, "atualizar_ordem", f"ordem {numero}",
                 f"quadro {quadro_id} responsavel={responsavel or '-'}")
        return (True, f"Ordem {numero} atualizada.")
    except Exception:
        _rollback_seguro(conn, contexto="atualizar_ordem")
        _log().exception("atualizar_ordem falhou")
        return (False, "Erro ao atualizar a ordem de serviço.")
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def arquivar_ordem(ordem_id, arquivar=True, ator="", eh_admin_geral=False):
    """Arquiva (ou restaura) a ordem de serviço. Arquivar não apaga nada."""
    conn = None
    try:
        ordem_id = int(ordem_id)
        atual = obter_ordem(ordem_id)
        if not atual:
            return (False, "Ordem de serviço não encontrada.")
        quadro_id = int(atual["quadro_id"])
        if not pode_editar(ator, quadro_id, eh_admin_geral):
            return (False, "Você não pode arquivar ordens de serviço "
                           "neste quadro.")
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE tb_os_ordem SET arquivado=? WHERE id=?",
                    (1 if arquivar else 0, ordem_id))
        _registrar_evento(
            conn, ordem_id, quadro_id, "arquivamento", ator,
            "Arquivou a ordem de serviço" if arquivar
            else "Restaurou a ordem de serviço do arquivo")
        _commit_com_retry(conn, contexto="arquivar_ordem")
        _auditar(ator, "arquivar_ordem", f"ordem {atual['numero']}",
                 "arquivado" if arquivar else "restaurado")
        return (True, f"Ordem {atual['numero']} arquivada."
                      if arquivar else f"Ordem {atual['numero']} restaurada.")
    except Exception:
        _rollback_seguro(conn, contexto="arquivar_ordem")
        _log().exception("arquivar_ordem falhou")
        return (False, "Erro ao arquivar a ordem de serviço.")
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def responsaveis_do_quadro(quadro_id, eh_admin_geral=False):
    """Quem pode receber uma ordem de serviço neste quadro: dono + convidados.

    Traz o nome de exibição (primeiro + último) e a unidade — o seletor nunca
    mostra a matrícula crua sozinha."""
    try:
        itens = []
        quadro = obter_quadro(quadro_id)
        if not quadro:
            return itens
        dono = quadro.get("dono_user_nome") or ""
        if dono:
            nome, unidade = _ficha_do_convidado(dono)
            itens.append({"user_nome": dono, "nome_exibicao": nome,
                          "unidade": unidade, "papel": "dono"})
        for convite in listar_convites_quadro(quadro_id):
            if convite.get("status") != "aceito":
                continue
            login = convite.get("convidado_user_nome") or ""
            nome = convite.get("nome_exibicao") or login
            if any(i["user_nome"] == login for i in itens):
                continue
            itens.append({"user_nome": login, "nome_exibicao": nome,
                          "unidade": convite.get("unidade") or "",
                          "papel": convite.get("papel") or "leitor"})
        return itens
    except Exception:
        _log().exception("responsaveis_do_quadro falhou")
        return []


def visao_geral():
    """Números do módulo para o painel de administração.

    `por_unidade` vem do nome da unidade gravada no quadro — o módulo não
    consulta o organograma de ninguém, só o que ele mesmo guardou."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        hoje = datetime.now().strftime("%Y-%m-%d")
        mes = datetime.now().strftime("%Y-%m")
        cur.execute("SELECT COUNT(*) FROM tb_os_quadro WHERE arquivado=0")
        quadros = int((cur.fetchone() or [0])[0])
        cur.execute("SELECT COUNT(*) FROM tb_os_quadro WHERE arquivado=0 "
                    "AND visibilidade='unidade'")
        quadros_unidade = int((cur.fetchone() or [0])[0])
        cur.execute("SELECT COUNT(*) FROM tb_os_ordem WHERE arquivado=0")
        cartoes = int((cur.fetchone() or [0])[0])
        cur.execute("SELECT COUNT(*) FROM tb_os_ordem WHERE arquivado=0 "
                    "AND concluido_em=''")
        abertos = int((cur.fetchone() or [0])[0])
        cur.execute("SELECT COUNT(*) FROM tb_os_ordem WHERE arquivado=0 "
                    "AND concluido_em='' AND data_vencimento<>'' "
                    "AND data_vencimento<?", (hoje,))
        atrasadas = int((cur.fetchone() or [0])[0])
        cur.execute("SELECT COUNT(*) FROM tb_os_ordem WHERE arquivado=0 "
                    "AND concluido_em LIKE ?", (mes + "%",))
        concluidas_mes = int((cur.fetchone() or [0])[0])
        cur.execute("SELECT COUNT(*) FROM tb_os_ordem WHERE arquivado=0 "
                    "AND concluido_em='' AND responsavel_user_nome=''")
        sem_responsavel = int((cur.fetchone() or [0])[0])
        cur.execute("SELECT unidade_nome, COUNT(*) FROM tb_os_quadro "
                    "WHERE arquivado=0 AND unidade_nome<>'' "
                    "GROUP BY unidade_nome ORDER BY COUNT(*) DESC")
        por_unidade = [{"unidade": linha[0], "quadros": int(linha[1])}
                       for linha in cur.fetchall()]
        return {"quadros": quadros, "quadros_unidade": quadros_unidade,
                "cartoes": cartoes, "abertos": abertos, "atrasadas": atrasadas,
                "concluidas_mes": concluidas_mes,
                "sem_responsavel": sem_responsavel, "por_unidade": por_unidade}
    except Exception:
        _log().exception("visao_geral falhou")
        return {"quadros": 0, "quadros_unidade": 0, "cartoes": 0, "abertos": 0,
                "atrasadas": 0, "concluidas_mes": 0, "sem_responsavel": 0,
                "por_unidade": []}
    finally:
        try:
            conn.close()
        except Exception:
            pass
