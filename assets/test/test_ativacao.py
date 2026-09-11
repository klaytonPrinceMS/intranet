"""Testes funcionais do assistente de ativação (`mod_intranet/ativacao.py`).

Script standalone (NÃO pytest), no padrão da suíte: `sys.path` aponta para a
raiz, funções `check` com contadores e saída "RESULTADO: X OK, Y falha(s) de
Z". Cobre a regra de boot simples (sem assistente = SQLite apenas, sem
Postgres/OTel, ignorando a `tb_config`), o `_garantir_sdk_otel` + persistência
do `otel_ativo` no modo de ativação, a validação de portas/DSN/faixa,
`_compose_cmd`, `_mascarar_comando` (senhas nunca expostas), `_validar_senha`
(metacharacteres de shell) e `aplicar_portas` (best-effort com temp dir).
Usa `unittest.mock`/monkeypatch para não tocar no banco real nem no Docker.

Execute: .venv/bin/python assets/test/test_ativacao.py
"""
import os
import shutil
import socket
import sqlite3
import sys
import tempfile
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))))

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_OK = 0
_TOTAL = 0


def check(cond, msg):
    global _OK, _TOTAL
    _TOTAL += 1
    if cond:
        _OK += 1
        print(f"  OK [{_OK}] {msg}")
    else:
        print(f"  FALHOU [{_TOTAL - _OK}] {msg}")


def ler(rel):
    with open(os.path.join(RAIZ, rel), encoding="utf-8") as f:
        return f.read()


from mod_intranet import ativacao  # noqa: E402
from mod_intranet import repositorio as _repo  # noqa: E402

print("INICIANDO TESTES — ativacao.py (wizard de inicialização)")

# ================== _verificar_postgres (DSN) ==================
print("== _verificar_postgres (DSN) ==")
_fake_pg = mock.MagicMock()
_fake_pg.connect.side_effect = OSError("conexão recusada (inalcançável)")
with mock.patch.dict(sys.modules, {"psycopg2": _fake_pg}):
    try:
        r = ativacao._verificar_postgres(
            "postgresql+psycopg2://intranet:intranet@localhost:5432/intranet")
        check(r is False,
              "DSN postgresql+psycopg2:// inalcançável → False (sem erro de esquema)")
    except Exception as e:
        check(False, f"DSN postgresql+psycopg2:// sem erro de esquema ({e})")
_fake_ok = mock.MagicMock()
with mock.patch.dict(sys.modules, {"psycopg2": _fake_ok}):
    try:
        r = ativacao._verificar_postgres(
            "postgresql+psycopg2://intranet:intranet@localhost:5432/intranet")
        check(r is True,
              "DSN +psycopg2 acessível (mock) → True (esquema convertido p/ postgresql://)")
    except Exception as e:
        check(False, f"DSN +psycopg2 acessível (mock) → True ({e})")
check(ativacao._verificar_postgres(None) is False, "DSN None → False")
check(ativacao._verificar_postgres("") is False, "DSN vazio → False")

# ================== _porta_livre ==================
print("== _porta_livre ==")
_s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
_s.bind(("127.0.0.1", 0))
_porta_livre = _s.getsockname()[1]
_s.close()
check(ativacao._porta_livre(_porta_livre) is True,
      f"porta livre {_porta_livre} → True")
_s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
_s.bind(("127.0.0.1", 0))
_s.listen(1)
_porta_ocupada = _s.getsockname()[1]
try:
    check(ativacao._porta_livre(_porta_ocupada) is False,
          f"porta ocupada {_porta_ocupada} → False")
finally:
    _s.close()
check(ativacao._porta_livre(-1) is False, "porta -1 → False (inválida)")
check(ativacao._porta_livre(70000) is False, "porta 70000 → False (inválida)")

# ================== _compose_cmd ==================
print("== _compose_cmd ==")
with mock.patch.object(ativacao.shutil, "which", side_effect=lambda nome: {
        "docker": "/usr/bin/docker", "docker-compose": None}.get(nome)), \
        mock.patch.object(ativacao.subprocess, "run",
                          return_value=mock.MagicMock(returncode=0)):
    check(ativacao._compose_cmd() == ["docker", "compose"],
          "docker compose (plugin v2) preferido")
with mock.patch.object(ativacao.shutil, "which", side_effect=lambda nome: {
        "docker": None, "docker-compose": "/usr/bin/docker-compose"}.get(nome)):
    check(ativacao._compose_cmd() == ["docker-compose"],
          "docker-compose (v1) fallback")
with mock.patch.object(ativacao.shutil, "which", return_value=None):
    check(ativacao._compose_cmd() is None, "nenhum disponível → None")

# ================== _config_padrao ==================
print("== _config_padrao ==")
_cfg = ativacao._config_padrao()
check(_cfg["banco_tipo"] == "sqlite", "banco_tipo padrão sqlite")
check("localhost:5432" in _cfg["postgres_url"], "postgres_url padrão porta 5432")
check(_cfg["otel_ativo"] is False,
      "otel_ativo padrão False (boot simples, sem OTel)")
check(_cfg["subir_postgres"] is False, "subir_postgres padrão False")
check(_cfg["porta_site"] == 8080 and _cfg["porta_postgres"] == 5432
      and _cfg["porta_grafana"] == 3000, "portas padrão 8080/5432/3000")

# ================== boot padrão: SQLite sem Postgres/OTel ==================
print("== boot padrão (sem assistente): SQLite, sem Postgres/OTel ==")
_tmp = tempfile.mkdtemp(prefix="test_ativacao_")
_db = os.path.join(_tmp, "db_mod_intranet.db")
_original_db = _repo.DB_PATH
_repo.DB_PATH = _db
try:
    # Mesmo que tb_config tenha postgres/5444, o boot padrão (não-TTY/ENTER)
    # DEVE subir SQLite e sem OTel — Postgres/OTel só no modo de ativação.
    _conn = sqlite3.connect(_db)
    _conn.execute("CREATE TABLE IF NOT EXISTS tb_config ("
                  "chave TEXT PRIMARY KEY, valor TEXT NOT NULL)")
    _conn.execute("INSERT OR REPLACE INTO tb_config (chave, valor) "
                  "VALUES ('banco_tipo', 'postgres')")
    _conn.execute("INSERT OR REPLACE INTO tb_config (chave, valor) VALUES "
                  "('postgres_url', 'postgresql+psycopg2://intranet:intranet"
                  "@localhost:5444/intranet')")
    _conn.execute("INSERT OR REPLACE INTO tb_config (chave, valor) "
                  "VALUES ('otel_ativo', '1')")
    _conn.commit()
    _conn.close()
    _cfg0 = ativacao._config_padrao()
    check(_cfg0["banco_tipo"] == "sqlite" and _cfg0["otel_ativo"] is False
          and _cfg0["subir_postgres"] is False,
          "config padrão ignora tb_config (SQLite, sem OTel, sem Postgres)")
finally:
    _repo.DB_PATH = _original_db
    shutil.rmtree(_tmp, ignore_errors=True)

# ================== _porta_valida ==================
print("== _porta_valida ==")
check(ativacao._porta_valida("", 8080) == 8080, "vazio → padrão")
check(ativacao._porta_valida("70000", 8080) == 8080, "fora da faixa → padrão")
check(ativacao._porta_valida("abc", 8080) == 8080, "não numérico → padrão")
check(ativacao._porta_valida("9090", 8080) == 9090, "válida → o valor digitado")

# ================== perguntar(faixa=) ==================
print("== perguntar(faixa=) ==")
with mock.patch("builtins.input", return_value="70000"):
    _r = ativacao.perguntar("Porta", "5432", valido_num=True, faixa=(1, 65535))
    check(_r == "5432", "fora da faixa → avisa e usa padrão")
with mock.patch("builtins.input", return_value=""):
    _r = ativacao.perguntar("Porta", "5432", valido_num=True, faixa=(1, 65535))
    check(_r == "5432", "ENTER → padrão")
with mock.patch("builtins.input", return_value="9090"):
    _r = ativacao.perguntar("Porta", "5432", valido_num=True, faixa=(1, 65535))
    check(_r == "9090", "válido dentro da faixa → o valor digitado")
with mock.patch("builtins.input", side_effect=EOFError):
    _r = ativacao.perguntar("Porta", "5432", valido_num=True, faixa=(1, 65535))
    check(_r == "5432", "EOF (sem stdin) → padrão (fail-soft)")

# ================== _validar_senha ==================
print("== _validar_senha ==")
for _mc in (";", "|", "&", "$", "'", '"', "\\", " "):
    check(ativacao._validar_senha(f"senha{_mc}x") is False,
          f"metacharacter {_mc!r} rejeitado")
check(ativacao._validar_senha("senhaSegura123") is True,
      "senha sem metacharacter aceita")
check(ativacao._validar_senha(None) is True, "senha None → aceita (padrão)")

# ================== _mascarar_comando ==================
print("== _mascarar_comando ==")
_m = ativacao._mascarar_comando("usuario:senha | chpasswd")
check("usuario:***" in _m and "senha" not in _m,
      "usuario:senha | chpasswd → senha mascarada")
_m2 = ativacao._mascarar_comando(["sh", "-c", "echo 'u:segredo' | chpasswd"])
check("segredo" not in _m2 and ":***" in _m2,
      "lista com chpasswd → senha mascarada (join)")
_m3 = ativacao._mascarar_comando("curl -d password=segredo123 http://x")
check("password=***" in _m3 and "segredo123" not in _m3, "password=x → ***")
_m4 = ativacao._mascarar_comando("docker compose ps")
check("***" not in _m4, "comando sem credenciais fica intacto")

# ================== _garantir_sdk_otel ==================
print("== _garantir_sdk_otel ==")
with mock.patch.dict(sys.modules, {
        "opentelemetry": mock.MagicMock(),
        "opentelemetry.sdk": mock.MagicMock(),
        "opentelemetry.exporter.otlp.proto.grpc": mock.MagicMock()}):
    check(ativacao._garantir_sdk_otel() is True, "SDK OTel importável → True")
with mock.patch.dict(sys.modules, {"opentelemetry": None}), \
        mock.patch.object(ativacao, "_cmd", return_value=False) as _cmd_mock:
    check(ativacao._garantir_sdk_otel() is False,
          "SDK ausente + pip falha → False (fail-soft)")
    _cmd_mock.assert_called_once()
    _args = _cmd_mock.call_args.args[0]
    check(_args[0] == sys.executable and "-m" in _args and "install" in _args,
          "instala opentelemetry-api/sdk/exporter no interpretador atual")
with mock.patch.object(ativacao, "_garantir_sdk_otel", return_value=False):
    check(ativacao.iniciar_stack_otel({"porta_grafana": 3000}) is False,
          "iniciar_stack_otel sem SDK → False (sem tentar Docker)")

# ================== aplicar_portas (best-effort) ==================
print("== aplicar_portas ==")
_tmp2 = tempfile.mkdtemp(prefix="test_ativacao_portas_")
_raiz_fake = os.path.join(_tmp2, "raiz")
_docker_dir = os.path.join(_raiz_fake, "assets", "docker")
os.makedirs(os.path.join(_docker_dir, "postgres"), exist_ok=True)
with open(os.path.join(_docker_dir, "compose.yml"), "w", encoding="utf-8") as f:
    f.write('    ports:\n      - "3000:3000"\n')
with open(os.path.join(_docker_dir, "postgres", "docker-compose.yml"),
          "w", encoding="utf-8") as f:
    f.write('    ports:\n      - "5432:5432"\n')
_file_fake = os.path.join(_raiz_fake, "mod_intranet", "ativacao.py")
try:
    with mock.patch.object(ativacao, "__file__", _file_fake):
        ativacao.aplicar_portas({"porta_grafana": 3100, "porta_postgres": 5444})
    _txt = open(os.path.join(_docker_dir, "compose.yml"), encoding="utf-8").read()
    check('"3100:3000"' in _txt, "grafana: porta 3100 aplicada no compose.yml")
    _txt_pg = open(os.path.join(_docker_dir, "postgres", "docker-compose.yml"),
                   encoding="utf-8").read()
    check('"5444:5432"' in _txt_pg,
          "postgres: porta 5444 aplicada no docker-compose.yml")
    # arquivo ausente não quebra
    os.remove(os.path.join(_docker_dir, "postgres", "docker-compose.yml"))
    os.remove(os.path.join(_docker_dir, "compose.yml"))
    try:
        with mock.patch.object(ativacao, "__file__", _file_fake):
            ativacao.aplicar_portas({"porta_grafana": 3100,
                                     "porta_postgres": 5444})
        check(True, "arquivos ausentes → sem quebra (best-effort)")
    except Exception as e:
        check(False, f"arquivos ausentes → sem quebra ({e})")
finally:
    shutil.rmtree(_tmp2, ignore_errors=True)

# ================== fonte: fixes de QA aplicados ==================
print("== fonte: fixes de QA aplicados ==")
_SRC = ler("mod_intranet/ativacao.py")
check("def _config_padrao():" in _SRC and '"otel_ativo": False' in _SRC,
      "_config_padrao com otel_ativo False (boot simples sem OTel)")
check("Terminal não interativo — usando SQLite" in _SRC,
      "ramo não-TTY usa SQLite (configuração padrão)")
check('return _config_padrao()' in _SRC and '_config_persistida' not in _SRC,
      "_config_persistida removida (boot padrão não usa tb_config)")
check('set_config("otel_ativo"' in _SRC,
      "escolha otel_ativo persistida (set_config)")
check('if not _garantir_sdk_otel():' in _SRC,
      "iniciar_stack_otel garante o SDK OTel no início")
check('if _status_docker("intranet_postgres") == 0:' not in _SRC,
      "loop do Postgres sem _status_docker a cada 1s")
check("if i % 3 == 0:" not in _SRC,
      "loop do OTel sem _status_docker a cada 3 iterações")
# kbp-devSecOps: mudanças preservadas (não revertidas)
check("def _cmd(comando, timeout=600, entrada=None):" in _SRC,
      "_cmd preservado (lista/string via shlex + entrada)")
check("def perguntar(texto, padrao=\"\", validos=None, valido_num=False, "
      "faixa=None):" in _SRC, "perguntar(faixa=) preservado")
check("def _mascarar_comando(comando):" in _SRC,
      "_mascarar_comando preservado")
check("except Exception:" in _SRC and "return False  # erro/porta inválida"
      in _SRC, "_porta_livre retorna False em erro (preservado)")

print(f"RESULTADO: {_OK} OK, {_TOTAL - _OK} falha(s) de {_TOTAL} verificações")
sys.exit(0 if _OK == _TOTAL else 1)