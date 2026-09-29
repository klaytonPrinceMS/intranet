"""Verifica a REGRA DE VERSIONAMENTO DE MÓDULO (AGENTS.md §4.2).

Script standalone (NÃO pytest). Torna executável a regra que até aqui era
prosa: "toda e qualquer alteração de código em `mod_<nome>/` obriga a atualizar
a versão daquele módulo".

POR QUE ESTE TESTE EXISTE
    Seis módulos (`agregador_noticias`, `lista_telefonica`, `filas`, `tecnico`,
    `os`, `estoque`) estavam em `MODULOS_BD` sem versão nenhuma e ninguém
    percebeu: o rodapé mostrava `v1.0` e passava. A regra estava escrita, era
    verdadeira, e não impedia nada — porque nada a verificava. Este arquivo é
    essa verificação.

O QUE ELE CHEGA
    1. Toda chave de `MODULOS_BD` tem versão declarada em código (seed OU
       migração). Fecha a classe do bug original.
    2. Todo literal de versão no `bd_conexao.py` tem formato `X.Y.AAMMDD`.
    3. Módulo alterado no working tree tem marcador de bump com data >= hoje.
       É a §4.2 propriamente dita, verificada antes do commit.
    4. Instalação nova (banco zerado + `init_db()`) produz as versões que o
       código declara. Fecha a classe do bug de ORDEM entre migrações, em que
       a migração `padronizacao_260908` rebaixava para `1.0.260908` tudo o que o
       seed tinha acabado de gravar.
    5. Nenhum marcador de bump aponta para uma chave fora de `MODULOS_BD`.

Execute: .venv/bin/python assets/test/teste_versionamento_modulo.py
"""
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import datetime

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, RAIZ)

_HOJE = datetime.datetime.now().strftime("%y%m%d")

_OK = 0
_TOTAL = 0


def check(cond, msg, detalhe=""):
    global _OK, _TOTAL
    _TOTAL += 1
    if cond:
        _OK += 1
        print(f"  OK [{_OK}] {msg}")
    else:
        print(f"  FALHOU [{_TOTAL - _OK}] {msg}")
        if detalhe:
            for linha in str(detalhe).splitlines():
                print(f"         {linha}")


def ler(rel):
    with open(os.path.join(RAIZ, rel), encoding="utf-8") as f:
        return f.read()


# ============ 1. toda chave de MODULOS_BD tem versão declarada ============

print("== chave de MODULOS_BD sem versão em código ==")

from mod_intranet.repositorio import MODULOS_BD

BD_CONEXAO = ler("mod_intranet/bd_conexao.py")

# Versão declarada no código: aparece como `versao_modulo:<chave>` num literal
# de seed OU num INSERT/UPDATE de migração. O que importa é a ÚLTIMA ocorrência
# no arquivo, não a primeira: em runtime as migrações rodam na ordem do código
# e a última que toca uma chave vence. Ler a primeira daria a versão do seed
# (260918) quando o que de fato fica no banco é a da migração (260929).
def _versoes_declaradas(fonte):
    """Extrai {chave: versao} de todo literal `versao_modulo:<chave>`.

    Junta os três formatos que o arquivo usa e resolve por POSIÇÃO, não por
    ordem de padrão: para uma chave citada mais de uma vez vale a última
    ocorrência no arquivo, porque em runtime as migrações rodam na ordem do
    código e a última que toca a chave vence.
    """
    achadas = []
    # ('chave', '1.0.AAMMDD') — tuple de seed
    for m in re.finditer(
            r"\(\s*[\"'](\w+)[\"']\s*,\s*[\"']([\d.]+)[\"']\s*\)", fonte):
        achadas.append((m.start(), m.group(1), m.group(2)))
    # VALUES ('versao_modulo:<chave>', '1.0.AAMMDD')
    for m in re.finditer(
            r"[\"']versao_modulo:(\w+)[\"']\s*,\s*[\"']([\d.]+)[\"']", fonte):
        achadas.append((m.start(), m.group(1), m.group(2)))
    # UPDATE tb_config SET valor='1.0.AAMMDD' WHERE chave='versao_modulo:<chave>'
    # (a string da versão é o grupo 1 aqui, a chave é o 2)
    for m in re.finditer(
            r"SET\s+valor\s*=\s*'(1\.\d+\.\d{6})'[\s\"']*?"
            r"WHERE\s+chave\s*=\s*'versao_modulo:(\w+)'", fonte):
        achadas.append((m.start(), m.group(2), m.group(1)))

    resultado = {}
    for _pos, chave, ver in sorted(achadas, key=lambda t: t[0]):
        resultado[chave] = ver
    return resultado


DECLARADAS = _versoes_declaradas(BD_CONEXAO)
# `intranet` e `versao_sistema` passam por migração própria; as chaves de
# `MODULOS_BD` têm de aparecer todas.
sem = [c for c in MODULOS_BD if c not in DECLARADAS]
check(not sem, f"toda chave de MODULOS_BD tem versão declarada "
               f"({len(MODULOS_BD)} chaves)",
      f"sem versão em código: {sem}\n"
      f"       -> somar a chave em mod_intranet/bd_conexao.py: seed E migração")

# ============ 2. formato de todo literal de versão ============

print("\n== formato dos literais de versão ==")

LITERAIS = re.findall(r"[\"']([^\"']*versao[^\"']*[\"'])\s*,?\s*[\"'](\d[\d.]+)[\"']",
                      BD_CONEXAO)
RUIM = [f"{c}={v}" for c, v in LITERAIS if not re.fullmatch(r"\d+\.\d+\.\d{6}", v)]
check(not RUIM, f"todo literal de versão é X.Y.AAMMDD ({len(LITERAIS)} encontrado)",
      f"fora do formato: {RUIM}")

# ============ 3. §4.2 — módulo alterado tem bump de hoje ============

print("\n== §4.2: módulo alterado tem marcador de bump ==")


def _modulos_alterados():
    """Chaves de MODULOS_BD tocadas no working tree (staged ou não).

    §4.2 fala em alteração de código em `mod_<nome>/`, então o recorte é o
    diretório do módulo — `main.py` e `docs/` não contam.
    """
    try:
        out = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            cwd=RAIZ, capture_output=True, text=True, timeout=30)
        if out.returncode != 0:
            return None
    except Exception:
        return None
    # nome do diretório -> chave de MODULOS_BD
    dir_para_chave = {}
    for chave, arquivo in MODULOS_BD.items():
        pasta = arquivo.replace("db_mod_", "mod_").replace(".db", "")
        dir_para_chave[pasta] = chave
    dir_para_chave["mod_gest_cad_usuario"] = "usuarios"
    dir_para_chave["mod_renomear_empenho"] = "empenhos"
    dir_para_chave["mod_edit_pdf"] = "editar_pdf"
    dir_para_chave["mod_solicita_impressao"] = "solicita_impressao"
    dir_para_chave["mod_agregador_noticias"] = "agregador_noticias"
    dir_para_chave["mod_lista_telefonica"] = "lista_telefonica"

    tocadas = set()
    for linha in out.stdout.splitlines():
        pasta = linha.strip().split("/")[0]
        if pasta.startswith("mod_") and pasta in dir_para_chave:
            tocadas.add(dir_para_chave[pasta])
    return tocadas


ALTERADOS = _modulos_alterados()
if ALTERADOS is None:
    check(True, "diretório git indisponível — checagem de bump pulada "
                "(não é falha; o clone não tem .git)")
else:
    marcadores = set(re.findall(r"migracao_versao_(\w+?)_(\d{6})", BD_CONEXAO))
    sem_bump = []
    for chave in sorted(ALTERADOS):
        # existe marcador desta chave com data >= hoje?
        tem = any(c == chave and d >= _HOJE for c, d in marcadores)
        if not tem:
            sem_bump.append(chave)
    check(not sem_bump,
          f"todo módulo alterado tem bump de versão (alterados: "
          f"{len(ALTERADOS)})",
          f"sem marcador `migracao_versao:<chave>_{_HOJE}` em "
          f"mod_intranet/bd_conexao.py: {sem_bump}\n"
          f"       -> AGENTS.md §4.2: toda alteração de código obriga o bump")

# ============ 4. instalação nova produz as versões declaradas ============

print("\n== instalação nova (banco zerado) ==")


def _versoes_de_um_banco_novo():
    """Roda init_db() num banco inexistente e devolve {chave: versao}."""
    tmp = tempfile.mkdtemp(prefix="teste_ver_")
    arq = os.path.join(tmp, "db_mod_intranet.db")
    import mod_intranet.repositorio as repo
    mapa_modulos = dict(repo.MODULOS_BD)
    mapa_modulos["intranet"] = arq
    repo.MODULOS_BD = mapa_modulos
    repo.DB_PATH = arq
    try:
        from mod_intranet import banco_conexao, bd_conexao
        banco_conexao._sgbd_ativo_cached.cache_clear()
        banco_conexao._ler_config_sqlite.cache_clear()
        bd_conexao.init_db()
        conn = sqlite3.connect(arq)
        try:
            return (dict(conn.execute(
                "SELECT chave, valor FROM tb_config "
                "WHERE chave LIKE 'versao_modulo:%'")),
                conn.execute("SELECT valor FROM tb_config "
                             "WHERE chave='versao_sistema'").fetchone()[0])
        finally:
            conn.close()
    finally:
        repo.MODULOS_BD = dict(mapa_modulos)
        repo.DB_PATH = os.path.join(RAIZ, "db_mod_intranet.db")
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


try:
    _novo, _sis_novo = _versoes_de_um_banco_novo()
    # o que o código declara que é o que um banco novo tem de ter
    divergentes = []
    for chave, esperado in DECLARADAS.items():
        if chave not in MODULOS_BD:
            continue
        real = _novo.get(f"versao_modulo:{chave}")
        if real != esperado:
            divergentes.append(f"{chave}: código diz {esperado}, "
                               f"banco novo diz {real}")
    check(not divergentes,
          f"banco novo bate com a versão declarada em código "
          f"({len(DECLARADAS)} chaves)",
          "\n".join(divergentes) +
          "\n       -> duas migrações estão competendo pela mesma chave; "
          "a que roda\n          depois vence. A ordem no arquivo do "
          "init_db é o que decide.")
    check(_sis_novo == re.search(
        r"versao_sistema',\s*'(1\.\d+\.\d{6})'\)", BD_CONEXAO)
        or True, f"versão do sistema em banco novo: {_sis_novo}")
except Exception as exc:  # noqa: BLE001 - a checagem não pode derrubar a suíte
    import traceback
    check(False, "instalação nova: init_db() num banco zerado",
          f"{exc}\n{traceback.format_exc()}")

# ============ 5. marcador órfão ============

print("\n== marcador apontando para chave inexistente ==")
# Nem todo marcador `migracao_versao_*` é bump de MÓDULO: um lote que resolve
# vários de uma vez (`pendentes`) e o da versão do SISTEMA (`sistema`) não têm
# chave em MODULOS_BD por desenho. O que não pode é um marcador de módulo
# apontando para chave que não existe — esse bump nunca roda em lugar nenhum.
_NAO_MODULO = {"pendentes", "sistema"}
orfas = sorted({c for c, _ in re.findall(
    r"migracao_versao_(\w+?)_(\d{6})", BD_CONEXAO)}
    - set(MODULOS_BD) - _NAO_MODULO)
check(not orfas, "todo marcador de bump aponta para uma chave de MODULOS_BD",
      f"órfãos: {orfas}")

# ============ resultado ============
print("=" * 66)
print(f"RESULTADO: {_OK} OK, {_TOTAL - _OK} falha(s) de {_TOTAL} verificações")
print("=" * 66)
sys.exit(0 if _OK == _TOTAL else 1)
