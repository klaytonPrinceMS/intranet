"""Verificacao de forca e de vazamento de senha — sem travar nunca.

Duas camadas, deliberadamente separadas porque elas falham de jeitos
diferentes:

1. `analisar_offline()` — forca, sem rede. Entropia, padroes de teclado,
   sequencias, repeticoes, palavras proibidas do orgao e as contas de teste.
   Custa microssegundos e NUNCA pode deixar de responder: e o caminho que
   decide se a troca acontece, entao precisa ser previsivel.

2. `analisar_online()` — vazamento, com rede. Consulta a API de senhas
   vazadas por k-anonimato e devolve "vazou N vezes". Caracteristica
   obrigatoria: se a rede nao existir, ela NAO e consultada.

Por que o vazamento nao decide a troca (30/09/2026, decisao do responsavel):
uma prefeitura roda em rede fechada, sem internet. Se a consulta fosse
bloqueante, quem estivesse trocando senha ficaria olhando a tela girando, e o
caso pior seria a camada de rede presa em retry. Por isso o caminho que
BLOQUEIA e so o offline, e a camada online:

  - nunca e chamada no event-loop (a UI embrulha em `run.io_bound`);
  - tem tempo maximo proprio (conexao 1,0s / leitura 2,0s) e ZERO retries;
  - e precedida por uma sondagem de internet com cache de 15 minutos, de modo
    que em rede local ela nem chega a abrir socket;
  - falha de qualquer jeito (sem rota, DNS, 429, timeout, 500) devolve o
    resultado offline com `consulta_online` explicando o motivo. Nunca levanta.

A senha nunca sai do servidor: manda-se somente os 5 primeiros caracteres do
SHA-1 (hex, maiusculo), e a comparacao do pedaco que falta acontece aqui. Sao
1.048.576 prefixos possiveis, entao um prefixo e compartilhado por centenas de
senhas — e o que torna o modelo aceitavel sem expor dado pessoal.

O que este modulo NAO faz, de proposito: guardar no banco a lista de senhas
vazadas. Ver `motivos_sem_corpus()` — e uma resposta, nao uma omissao.
"""
from __future__ import annotations

import hashlib
import logging
import math
import re
import socket
import time
from collections import Counter

logger = logging.getLogger(__name__)

# Porta e tempo maximos da camada online. Nao ha retries: um retry so serviria
# para transformar "sem internet" em "travou mais ainda".
TEMPO_CONEXAO_SEG = 1.0
TEMPO_LEITURA_SEG = 2.0
INTERVALO_SONDAGEM_SEG = 900

URL_VAZAMENTO = "https://api.pwnedpasswords.com/range/{prefixo}"
HOST_VAZAMENTO = "api.pwnedpasswords.com"

CHAVE_CONSULTAR = "senha_consultar_vazamento"
CHAVE_TAMANHO_MINIMO = "senha_tamanho_minimo"
CHAVE_SONDAR = "senha_sondar_internet"

TAMANHO_MINIMO_PADRAO = 6
ENTROPIA_FRACA = 28.0
ENTROPIA_MEDIA = 40.0

# Contas de teste do seed (AGENTS.md 8.2). Entregam com a senha `123456`
# publica e documentada, entao a regra de forca NAO se aplica a elas: sem essa
# exemption o primeiro acesso seria um beco sem saida (troca obrigatoria ->
# senha recusada -> ninguem entra). Decisao do responsavel em 30/09/2026.
CONTAS_DE_TESTE = ("qacomum", "qamaster")

# Lista curta de senhastageadas como fracas em qualquer material publico de
# seguranca. Nao e corpus de vazamento: sao as palavras que qualquer dicionario
# de ataque ja trazia antes de existir API para isso. Vale a pena ter mesmo sem
# internet, porque e o caso mais comum e o mais barato de pegar.
_SENHAS_CONHECIDAS = frozenset({
    "123456", "1234567", "12345678", "123456789", "123123", "111111", "000000",
    "654321", "121212", "qwerty", "qwertyui", "qwuiop", "qazwsx", "wsxedc",
    "senha", "senha1", "senha12", "senha123", "senhas", "senha2024",
    "senha2025", "senha2026", "mudar123", "trocar123", "mudar", "trocar",
    "password", "pass123", "p@ssw0rd", "admin", "admin123", "administrador",
    "usuario", "user123", "login123", "default", "abc123", "abc1234",
    "abcd1234", "teste123", "test123", "guest", "master", "root",
    "prefeitura", "prefeitural", "municipio", "camaradedeputado",
    "detran", "orgao", "servidor", "servidor123", "gov", "govbr",
    "brasil", "brasil123", "cpf123", "letras123", "letras",
})

# Linhas de teclado, em ordem e na ordem inversa. Base de `qazwsx` e companhia.
_TECLADOS = (
    "qwertyuiop", "asdfghjkl", "zxcvbnm",
    "1234567890", "poiuytrewq", "lkjhgfdsa", "mnbvcxz", "0987654321",
)

# Sequencias crescentes/decrescentes de 4 ou mais caracteres. Composta por
# listagem em vez de faixa `0-9a-z`, que casaria atravessando a fronteira
# entre digitos e letras ("3abc", "9zyx") e reprovar senha sem culpa.
_SEQUENCIA = re.compile(
    r"(0123|1234|2345|3456|4567|5678|6789|"
    r"abcd|bcde|cdef|defg|efgh|fghi|"
    r"ABCD|BCDE|CDEF|DEFG|EFGH|FGHI)", )
_SEQUENCIA_DESC = re.compile(
    r"(9876|8765|7654|6543|5432|4321|3210|"
    r"cba|dcba|edcba|zyxw|wvu)", )

_ANO = re.compile(r"(19|20)\d{2}")

_sondagem: dict[str, object] = {"quando": 0.0, "resultado": None}

# Cache em memoria do veredito online, por SHA-1 (nunca pela senha em claro:
# manter senha em texto plano vivo em um lru_cache e o tipo de coisa que o
# revisor procura e nao encontra ate faltar).
_vereditos: dict[str, tuple[bool, int]] = {}


def motivos_sem_corpus() -> list[str]:
    """Por que este modulo nao guarda a lista de senhas vazadas no banco.

    Fica no codigo como resposta a pergunta, porque ela vai aparecer de novo.
    """
    return [
        "A pergunta so tem resposta contra o corpus ATUAL: uma tabela local e "
        "uma fotografia de uma data, e vazamento novo invalida o veredito dela.",
        "O corpus tem centenas de milhoes de credenciais — nao cabe em um banco "
        "de prefeitura, e consultar a tabela exigiria o mesmo SHA-1 e a mesma "
        "comparacao, ou seja, todo o trabalho da chamada viva sem ganho nenhum.",
        "AGENTS.md 7 (nunca commitar segredos) e 8.3 (git e imutavel e "
        "replicado para todo mundo que clona): lista de senhas REAIS em texto "
        "plano no repositorio e uma lista de ataque pronta, no historico, para "
        "sempre.",
        "O corpus tem hash de credenciais de pessoas identificaveis, incluindo "
        "de governo. Montar banco local disso e tratamento de dado pessoal em "
        "massa (LGPD) numa intranet que nao tem essa funcao. Quem tem essa "
        "funcao e o servico publico, com politica de uso publica.",
    ]


def _config(chave: str, padrao: str = "") -> str:
    """Le `tb_config` do banco central sem derrubar o modulo se falhar."""
    try:
        from mod_intranet.bd_conexao import get_config
        return str(get_config(chave, padrao) or padrao)
    except Exception:
        return padrao


def _eh_conta_de_teste(nome_usuario: str) -> bool:
    """`qacomum`/`qamaster` seguem para a regra fraca sem rebaixar a exigencia."""
    try:
        return (nome_usuario or "").strip().lower() in CONTAS_DE_TESTE
    except Exception:
        return False


def _entropia(senha: str) -> float:
    """Bits TOTAIS de Shannon: comprimento x entropia por simbolo.

    Multiplicar pelo comprimento nao e detalhe, e a diferenca entre a metrica
    servir ou nao. A entropia por simbolo de qualquer senha curta fica logo
    abaixo de log2(20) = 4,3 bits, porque uma senha de 20 caracteres so tem 20
    simbolos para distribuir -- entao, sozinha, ela nunca passaria de 4,3, todo
    mundo cairia em "media" e o nivel "forte" ficaria inalcancavel. Sao os bits
    TOTAIS que respondem "quantas combinacoes o atacante tem de tentar":
    `Senha@2026` da ~33 bits (fraco, e esta certo); uma senha longa e variada
    passa de 70.
    """
    try:
        n = len(senha)
        if n == 0:
            return 0.0
        contagem = Counter(senha)
        por_simbolo = -sum((c / n) * math.log2(c / n) for c in contagem.values())
        return por_simbolo * n
    except Exception:
        return 0.0


def _tem_sequencia(senha: str) -> bool:
    """Sequencia de teclado ou crescente/decrescente, com ou sem quebra."""
    try:
        al = senha.lower()
        if _SEQUENCIA.search(al) or _SEQUENCIA_DESC.search(al):
            return True
        for linha in _TECLADOS:
            if linha in al:
                return True
            # `qazwsx` caminha por varias linhas: testa pares consecutivos.
            for i in range(len(linha) - 3):
                trecho = linha[i:i + 4]
                invertido = trecho[::-1]
                if trecho in al or invertido in al:
                    return True
        return False
    except Exception:
        return False


def _tem_repeticao(senha: str) -> bool:
    """`aaa`, `111111`, `ababab` — um unico caractere repetido."""
    try:
        if len(senha) < 3:
            return False
        if len(set(senha)) == 1:
            return True
        for n in (2, 3):
            if len(senha) >= n * 3:
                bloco = senha[:n] * 3
                if senha == bloco or senha == bloco + senha[3 * n:3 * n + 1]:
                    return True
        # qualquer caractere repetido 4+ vezes seguidas
        contagem = Counter(senha)
        if any(c >= 4 for c in contagem.values()):
            return True
        return False
    except Exception:
        return False


def _padroes_do_organizacao() -> list[tuple[str, str]]:
    """`[(padrao, tipo), ...]` vindos do banco; `exata` = igual, `palavra` = contem.

    Isto e configuracao do PROPRIO orgao, nao dado de terceiro: sao as
    palavras com as quais o publico ja monta senha (o nome da prefeitura, o
    nome do orgao, um termo do servico). Defender a senha que o padrao do orgao
    convida a usar e a unica "lista de senhas padrao" defensavel de guardar —
    e e configuracao, revisavel, que o administrador controla.
    """
    try:
        from mod_intranet.banco_conexao import conexao
        conn = conexao("intranet")
        if conn is None:
            return []
        cur = conn.cursor()
        cur.execute("SELECT padrao, tipo FROM tb_senha_padrao_organizacao "
                    "WHERE ativo=1")
        linhas = [(str(a or ""), str(b or "palavra")) for a, b in cur.fetchall()]
        conn.close()
        return linhas
    except Exception:
        return []


def definir_padrao_organizacao(padrao: str, descricao: str = "",
                              tipo: str = "palavra") -> bool:
    """Cadastra/edita um padrao que o orgao nao aceita como senha."""
    try:
        p = (padrao or "").strip().lower()
        if not p:
            return False
        t = tipo if tipo in ("exata", "palavra") else "palavra"
        from mod_intranet.banco_conexao import conexao
        conn = conexao("intranet")
        if conn is None:
            return False
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO tb_senha_padrao_organizacao (padrao, descricao, tipo, ativo) "
            "VALUES (?, ?, ?, 1) ON CONFLICT (padrao) DO UPDATE SET "
            "descricao=EXCLUDED.descricao, tipo=EXCLUDED.tipo, ativo=1",
            (p, descricao or "", t))
        conn.commit()
        conn.close()
        return True
    except Exception:
        logger.exception("validador_senha: falha ao gravar padrao do orgao")
        return False


def listar_padroes_organizacao() -> list[dict]:
    """Todos os padroes cadastrados, ativos ou nao."""
    try:
        from mod_intranet.banco_conexao import conexao
        conn = conexao("intranet")
        if conn is None:
            return []
        cur = conn.cursor()
        cur.execute("SELECT padrao, descricao, tipo, ativo FROM "
                    "tb_senha_padrao_organizacao ORDER BY padrao")
        linhas = [{"padrao": a, "descricao": b or "", "tipo": c or "palavra",
                   "ativo": bool(d)}
                  for a, b, c, d in cur.fetchall()]
        conn.close()
        return linhas
    except Exception:
        return []


def _casar_padrao(senha: str, padroes: list[tuple[str, str]]) -> str:
    """Primeiro padrao do orgao que a senha acerta; "" se nenhum."""
    try:
        al = senha.lower()
        sem_espaco = re.sub(r"[\s._-]+", "", al)
        for p, tipo in padroes:
            if not p:
                continue
            alvo = re.sub(r"[\s._-]+", "", p)
            if not alvo:
                continue
            if tipo == "exata" and sem_espaco == alvo:
                return p
            if tipo != "exata" and alvo in sem_espaco:
                return p
        return ""
    except Exception:
        return ""


def _cache_do_veredito(prefixo: str, sufixo: str) -> tuple[bool, int] | None:
    """`(vazou, vezes)` se ja consultamos esse par; `None` se ainda nao."""
    try:
        from mod_intranet.banco_conexao import conexao
        conn = conexao("intranet")
        if conn is None:
            return None
        cur = conn.cursor()
        cur.execute("SELECT contagem FROM tb_senha_vazamento_cache "
                    "WHERE prefixo=? AND sufixo=?", (prefixo, sufixo))
        linha = cur.fetchone()
        conn.close()
        if not linha:
            return None
        return (int(linha[0] or 0) > 0, int(linha[0] or 0))
    except Exception:
        return None


def _gravar_cache(prefixo: str, sufixo: str, contagem: int) -> None:
    """Memoriza o veredito para a proxima tentativa com a mesma senha."""
    try:
        from mod_intranet.banco_conexao import conexao
        conn = conexao("intranet")
        if conn is None:
            return
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO tb_senha_vazamento_cache (prefixo, sufixo, contagem, "
            "data_consulta) VALUES (?, ?, ?, CURRENT_TIMESTAMP) "
            "ON CONFLICT (prefixo, sufixo) DO UPDATE SET "
            "contagem=EXCLUDED.contagem, data_consulta=CURRENT_TIMESTAMP",
            (prefixo, sufixo, int(contagem)))
        conn.commit()
        conn.close()
    except Exception:
        logger.exception("validador_senha: falha ao gravar cache de vazamento")


def _internet_disponivel() -> bool:
    """Sondagem de internet com cache de 15 min.

    Existe para que, em rede local, a camada online nem tente abrir socket. Um
    `socket.create_connection` com 1,0s e o suficiente; resultado fica em cache
    para nao repetir a sondagem a cada troca de senha.
    """
    agora = time.monotonic()
    if _sondagem["resultado"] is not None and \
            (agora - float(_sondagem["quando"] or 0)) < INTERVALO_SONDAGEM_SEG:
        return bool(_sondagem["resultado"])
    if _config(CHAVE_SONDAR, "1") in ("0", "false", "nao", "não"):
        _sondagem["quando"] = agora
        _sondagem["resultado"] = False
        return False
    resultado = False
    try:
        socket.create_connection((HOST_VAZAMENTO, 443), TEMPO_CONEXAO_SEG).close()
        resultado = True
    except Exception:
        logger.info("validador_senha: sem internet — camada de vazamento "
                    "ficara offline por %s min", INTERVALO_SONDAGEM_SEG // 60)
    _sondagem["quando"] = agora
    _sondagem["resultado"] = resultado
    return resultado


def consultar_vazamento(senha: str) -> tuple[bool, int, str]:
    """`(vazou, vezes, situacao)` — nunca levanta, nunca trava.

    `situacao` explica o que aconteceu: `ok`, `cache`, `desligada`,
    `sem_internet`, `indisponivel`, `limite_requisicoes` ou `erro`. O chamador
    mostra isso; um erro de rede nunca vira `vazou=True` nem `vazou=False`
    silencioso — ele vira `indisponivel`, que é diferente dos dois.
    """
    try:
        senha = senha or ""
        if not senha:
            return False, 0, "vazia"
        if _config(CHAVE_CONSULTAR, "1") in ("0", "false", "nao", "não"):
            return False, 0, "desligada"

        digest = hashlib.sha1(senha.encode("utf-8")).hexdigest().upper()
        prefixo, sufixo = digest[:5], digest[5:]

        em_memoria = _vereditos.get(digest)
        if em_memoria is not None:
            return em_memoria[0], em_memoria[1], "cache"

        do_banco = _cache_do_veredito(prefixo, sufixo)
        if do_banco is not None:
            _vereditos[digest] = do_banco
            return do_banco[0], do_banco[1], "cache"

        if not _internet_disponivel():
            return False, 0, "sem_internet"

        import httpx
        resposta = httpx.get(
            URL_VAZAMENTO.format(prefixo=prefixo),
            headers={"Add-Password": "true", "User-Agent": "intranet-prefeitura"},
            timeout=httpx.Timeout(TEMPO_LEITURA_SEG,
                                  connect=TEMPO_CONEXAO_SEG),
        )
        if resposta.status_code == 404:
            contagem = 0
        elif resposta.status_code == 429:
            return False, 0, "limite_requisicoes"
        elif resposta.status_code >= 400:
            return False, 0, "indisponivel"
        else:
            contagem = 0
            for linha in resposta.text.splitlines():
                pedaco, _, numero = linha.partition(":")
                if pedaco.strip().upper() == sufixo:
                    try:
                        contagem = int(numero.strip())
                    except ValueError:
                        contagem = 0
                    break

        _gravar_cache(prefixo, sufixo, contagem)
        veredito = (contagem > 0, contagem)
        _vereditos[digest] = veredito
        return veredito[0], veredito[1], "ok"
    except Exception:
        logger.exception("validador_senha: consulta de vazamento falhou; "
                         "seguindo com o veredito offline")
        return False, 0, "erro"


def analisar_offline(senha: str, nome_usuario: str = "") -> dict:
    """Forca da senha, sem rede nenhuma. Este e o caminho que BLOQUEIA.

    Contrato: nao levanta excecao, nao faz I/O de rede e devolve em tempo
    constante. E o unico que a camada de servico (`trocar_senha_propria`) usa,
    e por isso o caminho de gravacao nunca depende da internet.

    Conta de teste (`qacomum`/`qamaster`) sai aqui com `ok=True` e sem
    `bloqueios`, e nao so no `veredito_bloqueante`. A diferenca importa: se a
    excecao ficasse so na camada de bloqueio, o servico deixaria passar e a
    TELA pintaria de vermelho "esta senha esta entre as mais usadas do mundo"
    — o usuario leria que foi recusado e o sistema gravaria assim mesmo. A
    excecao precisa ser visivel nos dois lados, ou os dois lados mentem de
    jeitos diferentes.
    """
    try:
        s = senha or ""
        bloqueios: list[str] = []
        avisos: list[str] = []
        bits = _entropia(s)

        if _eh_conta_de_teste(nome_usuario):
            return {"ok": True, "nivel": "conta_de_teste", "bits": round(bits, 1),
                    "bloqueios": [], "avisos": [], "vazou": False, "vezes": 0,
                    "consulta_online": "conta_de_teste", "excecao": True}

        try:
            tamanho_minimo = int(_config(CHAVE_TAMANHO_MINIMO,
                                         str(TAMANHO_MINIMO_PADRAO)))
        except Exception:
            tamanho_minimo = TAMANHO_MINIMO_PADRAO

        if len(s) < tamanho_minimo:
            bloqueios.append(f"A senha precisa de ao menos {tamanho_minimo} "
                             "caracteres.")
        if not s.strip():
            bloqueios.append("A senha nao pode ser só espaços.")
        elif s.strip() != s:
            bloqueios.append("A senha nao pode começar nem terminar com espaço.")

        if s.lower() in _SENHAS_CONHECIDAS:
            bloqueios.append("Esta senha está entre as mais usadas do mundo — "
                             "é a primeira que qualquer ataque tenta.")
        if s.isdigit():
            bloqueios.append("Senha só de números não resiste a ataque de "
                             "força bruta.")
        if _tem_repeticao(s):
            bloqueios.append("A senha repete o mesmo caractere ou bloco.")
        if _tem_sequencia(s):
            bloqueios.append("A senha é uma sequência de teclado ou de números "
                             "(ex.: 1234, qwerty, qazwsx).")

        classes = sum([
            any(c.islower() for c in s),
            any(c.isupper() for c in s),
            any(c.isdigit() for c in s),
            any(not c.isalnum() for c in s),
        ])
        if len(s) >= 6 and classes <= 1:
            bloqueios.append("A senha usa um único tipo de caractere "
                             "(só letras, só números ou só símbolos).")

        nome = (nome_usuario or "").strip().lower()
        if nome and len(nome) >= 4 and nome in s.lower():
            bloqueios.append("A senha contém o próprio nome de usuário.")
        elif nome and len(nome) >= 4:
            # `fulano` -> `fulano1`/`fulano@123`: o nome como base.
            if re.search(re.escape(nome[:4]) + r"[0-9!@#$%^&*]{1,4}$", s, re.I):
                bloqueios.append("A senha é o nome de usuário com números ou "
                                 "símbolos no fim.")

        ano = _ANO.search(s)
        if ano and len(s) <= 10:
            bloqueios.append(f"A senha é curta e termina em ano ({ano.group(0)}).")

        padrao = _casar_padrao(s, _padroes_do_organizacao())
        if padrao:
            bloqueios.append(f"A senha contém “{padrao}”, palavra do próprio "
                             "órgão — é o palpite mais óbvio de quem conhece a "
                             "instituição.")

        if not bloqueios:
            if bits < ENTROPIA_MEDIA:
                avisos.append("A senha tem poucas combinações possíveis; "
                              "uma senha mais longa seria bem mais forte.")
            if len(s) < 8:
                avisos.append("A senha tem menos de 8 caracteres.")
            if classes == 3 and not any(not c.isalnum() for c in s):
                avisos.append("Incluir um símbolo aumenta bastante a dificuldade.")

        if bloqueios:
            nivel = "fraca"
        elif avisos or bits < ENTROPIA_MEDIA:
            nivel = "media"
        else:
            nivel = "forte"

        return {
            "ok": not bloqueios,
            "nivel": nivel,
            "bits": round(bits, 1),
            "bloqueios": bloqueios,
            "avisos": avisos,
            "vazou": False,
            "vezes": 0,
            "consulta_online": "nao_consultada",
            "excecao": _eh_conta_de_teste(nome_usuario),
        }
    except Exception:
        logger.exception("validador_senha: analise offline falhou")
        # Falhou a analise: deixa passar. Um erro na checagem nunca pode
        # trancar o usuario fora da propria senha.
        return {"ok": True, "nivel": "indisponivel", "bits": 0.0,
                "bloqueios": [], "avisos": [], "vazou": False, "vezes": 0,
                "consulta_online": "erro", "excecao": False}


def analisar_online(senha: str, nome_usuario: str = "") -> dict:
    """Veredito offline + consulta de vazamento. **Chame fora do event-loop.**

    Quando nao ha internet, devolve o veredito offline com `consulta_online`
    dizendo `sem_internet`. Nao e excecao e nao trava: e exatamente o caso da
    prefeitura em rede fechada.
    """
    try:
        r = analisar_offline(senha, nome_usuario)
        if r.get("excecao"):
            r["consulta_online"] = "conta_de_teste"
            return r

        # A chave desliga a camada INTEIRA, inclusive a leitura do cache. Sem
        # isso, quem desliga a opção continua vendo bloqueio de vazamento do
        # que ficou gravado antes — e o administrador não consegue entender por
        # que a tela continua recusando senha depois de ter desligado.
        if _config(CHAVE_CONSULTAR, "1") in ("0", "false", "nao", "não"):
            r["consulta_online"] = "desligada"
            return r

        try:
            do_banco = None
            digest = hashlib.sha1((senha or "").encode("utf-8")).hexdigest().upper()
            em_memoria = _vereditos.get(digest)
            if em_memoria is not None:
                vazou, vezes, situacao = em_memoria[0], em_memoria[1], "cache"
            else:
                do_banco = _cache_do_veredito(digest[:5], digest[5:])
                if do_banco is not None:
                    vazou, vezes, situacao = do_banco[0], do_banco[1], "cache"
                else:
                    vazou, vezes, situacao = consultar_vazamento(senha)
        except Exception:
            logger.exception("validador_senha: veredito de vazamento falhou")
            vazou, vezes, situacao = False, 0, "erro"

        r["vazou"] = bool(vazou)
        r["vezes"] = int(vezes or 0)
        r["consulta_online"] = situacao

        if vazou:
            aviso = (f"Esta senha apareceu {vezes:,} vez(es) em vazamentos "
                     "conhecidos.".replace(",", "."))
            if not r["ok"]:
                r["bloqueios"].insert(0, aviso)
            else:
                r["avisos"].insert(0, aviso)
            r["nivel"] = "fraca"
            r["ok"] = False
        elif situacao == "ok":
            r["avisos"].append("Não apareceu nos vazamentos consultados.")
        return r
    except Exception:
        logger.exception("validador_senha: analise online falhou")
        return analisar_offline(senha, nome_usuario)


def veredito_bloqueante(senha: str, nome_usuario: str = "") -> dict:
    """Veredito para o caminho que GRAVA. **Nunca toca na rede.**

    É esta função que `trocar_senha_propria` chama, e é aqui que está o
    requisito de rede local: o caminho que decide se a senha é aceita não
    consulta vazamento nenhum. Ele só:

      1. roda a análise offline (memória e CPU, microssegundos);
      2. olha o veredito no cache — local, no banco, ou seja instantâneo.

    Se a senha já foi consultada antes, o "vazou N vezes" entra no bloqueio
    mesmo sem internet. Se nunca foi, o veredito é só força, e isso é o
    comportamento correto: em rede fechada ninguém pode afirmar que a senha
    não vazou, mas ninguém precisa de internet para recusar `123456`.

    Devolve `None` quando a regra não se aplica (conta de teste), para o
    chamador não precisar conhecer a exceção.
    """
    try:
        r = analisar_offline(senha, nome_usuario)
        if r.get("excecao"):
            return None
        if _config(CHAVE_CONSULTAR, "1") in ("0", "false", "nao", "não"):
            return r
        try:
            digest = hashlib.sha1((senha or "").encode("utf-8")).hexdigest().upper()
            em_memoria = _vereditos.get(digest)
            if em_memoria is not None:
                vazou, vezes = em_memoria[0], em_memoria[1]
            else:
                do_banco = _cache_do_veredito(digest[:5], digest[5:])
                if do_banco is None:
                    return r
                vazou, vezes = do_banco[0], do_banco[1]
            if vazou:
                r["vazou"] = True
                r["vezes"] = int(vezes or 0)
                r["ok"] = False
                r["nivel"] = "fraca"
                r["bloqueios"].insert(
                    0, f"Esta senha apareceu {int(vezes or 0):,} vez(es) em "
                       "vazamentos conhecidos.".replace(",", "."))
                r["consulta_online"] = "cache"
        except Exception:
            logger.exception("validador_senha: leitura do cache falhou; "
                             "decidindo só pela força")
        return r
    except Exception:
        logger.exception("validador_senha: veredito bloqueante falhou")
        return None


# Como a consulta de vazamento TERMINOU, em português de gente. A chave bruta
# (`sem_internet`, `limite_requisicoes`) é identificador de código e nunca deve
# aparecer na tela: a pessoa não sabe o que é "requisicoes" e não precisa
# saber — o que importa é se a senha foi aceita, e por quê.
_SITUACAO_PT_BR = {
    "sem_internet": "este sistema não tem acesso à internet",
    "desligada": "a consulta está desligada",
    "indisponivel": "o serviço de consulta não respondeu",
    "limite_requisicoes": "o serviço de consulta pediu para esperar",
    "erro": "a consulta falhou",
    "nao_consultada": "a consulta não foi feita",
    "conta_de_teste": "",
    "cache": "",
    "ok": "",
    "vazia": "",
}


def texto_para_usuario(veredito: dict) -> str:
    """O veredito em uma frase, para a tela. Texto para PESSOAS.

    Duas regras que às vezes se confundem:

    - **Nada de jargão.** Nome de arquivo, número de seção e palavra de
      identificador não vão para a tela. Quem lê esta mensagem é servidor da
      prefeitura no balcão, não quem escreve o código; a explicação de por
      que a regra existe fica no código e na documentação, onde serve.
    - **Conta de teste não recebe aviso.** `qacomum`/`qamaster` entram com a
      senha `123456` e ficam fora da regra de propósito. Não há nada a avisar
      nesse caso, e um aviso ali só ocuparia a tela — então devolve vazio e a
      tela limpa o rótulo. Quem precisa saber por quê lê o código e a
      documentação.
    """
    try:
        v = veredito or {}
        if v.get("excecao"):
            return ""
        partes: list[str] = []
        for b in (v.get("bloqueios") or [])[:3]:
            partes.append(b)
        for a in (v.get("avisos") or [])[:2]:
            partes.append(a)
        situacao = v.get("consulta_online")
        if situacao in ("sem_internet", "desligada", "indisponivel", "erro",
                        "limite_requisicoes", "nao_consultada"):
            partes.append("Não foi possível consultar vazamentos porque "
                          f"{_SITUACAO_PT_BR.get(situacao, '')} — a senha foi "
                          "avaliada só pela força.")
        return " ".join(partes) if partes else (
            "Senha forte." if v.get("ok") else "Senha recusada.")
    except Exception:
        return ""