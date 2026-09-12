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
import io
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

# ================== cli_opcoes / config_do_cli (Typer) ==================
print("== cli_opcoes / config_do_cli (Typer) ==")
_opts = ativacao.cli_opcoes(
    ["--postgres", "--portapostgres", "5444", "--otel",
     "--portatelemetria", "3100", "--portasite", "8081",
     "--portadocumentacao", "8001"])
check(_opts == {"postgres": True, "portapostgres": 5444, "otel": True,
                "portatelemetria": 3100, "portasite": 8081,
                "portadocumentacao": 8001, "config": False},
      "cli_opcoes parseia todos os flags")
check(ativacao.cli_opcoes([]) == {"postgres": False, "portapostgres": 5432,
                                  "otel": False, "portatelemetria": 3000,
                                  "portasite": 8080, "portadocumentacao": 8000,
                                  "config": False},
      "cli_opcoes sem args → defaults")
check(ativacao.cli_opcoes(["--config"])["config"] is True,
      "cli_opcoes --config abre o assistente")
_cfgcli = ativacao.config_do_cli(postgres=True, portapostgres=5444, otel=True,
                                 portatelemetria=3100, portasite=8081,
                                 portadocumentacao=8001)
check(_cfgcli["banco_tipo"] == "postgres" and _cfgcli["subir_postgres"] is True
      and _cfgcli["otel_ativo"] is True, "config_do_cli ativa postgres+otel")
check(_cfgcli["porta_postgres"] == 5444 and _cfgcli["porta_grafana"] == 3100
      and _cfgcli["porta_site"] == 8081, "config_do_cli aplica a porta do site")
check(_cfgcli["porta_documentacao"] == 8001,
      "config_do_cli aplica a porta da documentação (mkdocs)")
check("localhost:5444" in _cfgcli["postgres_url"],
      "config_do_cli monta postgres_url na porta informada")
_cfgcli2 = ativacao.config_do_cli(portadocumentacao=9090)
check(_cfgcli2["banco_tipo"] == "sqlite" and _cfgcli2["otel_ativo"] is False
      and _cfgcli2["porta_site"] == 8080 and _cfgcli2["porta_documentacao"] == 9090,
      "config_do_cli só com porta da documentação → site 8080, doc 9090")

# ================== _porta_valida ==================
print("== _porta_valida ==")
check(ativacao._porta_valida("", 8080) == 8080, "vazio → padrão")
check(ativacao._porta_valida("70000", 8080) == 8080, "fora da faixa → padrão")
check(ativacao._porta_valida("abc", 8080) == 8080, "não numérico → padrão")
check(ativacao._porta_valida("9090", 8080) == 9090, "válida → o valor digitado")

# ================== perguntar(faixa=) ==================
print("== perguntar(faixa=) ==")
with mock.patch("builtins.input", side_effect=["70000", ""]):
    _r = ativacao.perguntar("Porta", "5432", valido_num=True, faixa=(1, 65535))
    check(_r == "5432", "fora da faixa → repete até resposta válida (ENTER = padrão)")
with mock.patch("builtins.input", side_effect=["abc", "9090"]):
    _r = ativacao.perguntar("Porta", "5432", valido_num=True, faixa=(1, 65535))
    check(_r == "9090", "inválido (não numérico) → repete até valor válido")
with mock.patch("builtins.input", return_value=""):
    _r = ativacao.perguntar("Porta", "5432", valido_num=True, faixa=(1, 65535))
    check(_r == "5432", "ENTER → padrão")
with mock.patch("builtins.input", return_value="9090"):
    _r = ativacao.perguntar("Porta", "5432", valido_num=True, faixa=(1, 65535))
    check(_r == "9090", "válido dentro da faixa → o valor digitado")
with mock.patch("builtins.input", side_effect=EOFError):
    _r = ativacao.perguntar("Porta", "5432", valido_num=True, faixa=(1, 65535))
    check(_r == "5432", "EOF (sem stdin) → padrão (fail-soft)")
with mock.patch("builtins.input", side_effect=["x", "sim"]):
    _r = ativacao.perguntar("Subir?", "nao", validos={"sim", "nao"})
    check(_r == "sim", "validos: inválido → repete até opção válida")
with mock.patch("builtins.input", return_value="nao"):
    _r = ativacao.perguntar("Subir?", "nao", validos={"sim", "nao"})
    check(_r == "nao", "validos: opção válida → o valor digitado")

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

# ================== _sim_nao estrito (somente 1/ENTER) ==================
print("== _sim_nao estrito (somente 1/ENTER) ==")
with mock.patch("builtins.input", side_effect=["s", "1"]):
    check(ativacao._sim_nao("Ativar?") is True,
          "['s','1'] → True (recusa 's', repete até '1')")
with mock.patch("builtins.input", side_effect=["sim", "nao", ""]):
    check(ativacao._sim_nao("Ativar?") is False,
          "['sim','nao',''] → False (recusa sim/nao, ENTER = não ativar)")
with mock.patch("builtins.input", side_effect=["x", "y", "0"]):
    check(ativacao._sim_nao("Ativar?") is False,
          "['x','y','0'] → False (recusa x/y, '0' = não ativar)")
with mock.patch("builtins.input", return_value="1"):
    check(ativacao._sim_nao("Ativar?") is True, "['1'] → True")
with mock.patch("builtins.input", return_value=""):
    check(ativacao._sim_nao("Ativar?") is False, "[''] (ENTER) → False")
with mock.patch("builtins.input", return_value="0"):
    check(ativacao._sim_nao("Ativar?") is False, "['0'] → False")
with mock.patch("builtins.input", side_effect=EOFError):
    check(ativacao._sim_nao("Ativar?") is False,
          "EOFError → False (padrão, sem loop)")
with mock.patch("builtins.input", side_effect=KeyboardInterrupt):
    check(ativacao._sim_nao("Ativar?") is False,
          "KeyboardInterrupt → False (padrão, sem loop)")

# ================== _escolha_1_enter (somente 1/ENTER) ==================
print("== _escolha_1_enter (somente 1/ENTER) ==")
with mock.patch("builtins.input", side_effect=["postgres", "1"]):
    check(ativacao._escolha_1_enter("Banco de dados", "SQLite (básico)",
                                    "PostgreSQL") == "1",
          "['postgres','1'] → '1' (recusa 'postgres', repete até 1)")
with mock.patch("builtins.input", side_effect=["abc", ""]):
    check(ativacao._escolha_1_enter("Banco de dados", "SQLite (básico)",
                                    "PostgreSQL") == "",
          "['abc',''] → '' (recusa 'abc', ENTER = sqlite)")
with mock.patch("builtins.input", side_effect=["s", ""]):
    check(ativacao._escolha_1_enter("Banco de dados", "SQLite (básico)",
                                    "PostgreSQL") == "",
          "['s',''] → '' (recusa 's', ENTER = sqlite)")
with mock.patch("builtins.input", return_value="0"):
    check(ativacao._escolha_1_enter("Banco de dados", "SQLite (básico)",
                                    "PostgreSQL") == "",
          "['0'] → '' (sqlite)")
_buf_aviso = io.StringIO()
with mock.patch("builtins.input", side_effect=["x", "1"]), \
        mock.patch("sys.stdout", _buf_aviso):
    _r_aviso = ativacao._escolha_1_enter("Banco de dados", "SQLite (básico)",
                                         "PostgreSQL")
check(_r_aviso == "1"
      and "Opção inválida — digite 1 para" in _buf_aviso.getvalue(),
      "tecla inválida emite aviso 'Opção inválida — digite 1 para' e repete")


def _rodar_iniciar(entradas):
    """Roda iniciar() com _TTY=True e serviços mockados; devolve (cfg, saída)."""
    _buf = io.StringIO()
    with mock.patch.object(ativacao, "_TTY", True), \
            mock.patch.object(ativacao, "banner"), \
            mock.patch.object(ativacao, "_porta_livre", return_value=True), \
            mock.patch.object(ativacao, "_verificar_postgres",
                              return_value=True), \
            mock.patch.object(ativacao, "iniciar_postgres",
                              return_value=True), \
            mock.patch.object(ativacao, "iniciar_stack_otel"), \
            mock.patch.object(ativacao, "aplicar_banco"), \
            mock.patch.object(ativacao, "aplicar_portas"), \
            mock.patch("mod_intranet.bd_conexao.set_config"), \
            mock.patch("sys.stdout", _buf), \
            mock.patch("builtins.input", side_effect=entradas):
        _cfg = ativacao.iniciar()
    return _cfg, _buf.getvalue()


# ================== regressão do fluxo completo (iniciar) ==================
print("== regressão do fluxo completo (iniciar) ==")
_cfg_pg, _ = _rodar_iniciar(["1", "1", "1", "", "0", "", ""])
check(_cfg_pg["banco_tipo"] == "postgres" and _cfg_pg["subir_postgres"] is True
      and _cfg_pg["otel_ativo"] is False,
      "fluxo ['1','1','1','','0','',''] → postgres, sobe Postgres, sem OTel")
check(_cfg_pg["porta_site"] == 8080 and _cfg_pg["porta_documentacao"] == 8000,
      "fluxo aplica portas padrão do site (8080) e da documentação (mkdocs 8000)")
_cfg_sql, _ = _rodar_iniciar(["2", "1", "", "", ""])
check(_cfg_sql["banco_tipo"] == "sqlite" and _cfg_sql["otel_ativo"] is False
      and _cfg_sql["subir_postgres"] is False,
      "fluxo ['2','1','','',''] → menu recusa '2', sqlite, sem OTel/Postgres")
_cfg_s, _saida_s = _rodar_iniciar(["1", "s", "", "", ""])
check(_cfg_s["banco_tipo"] == "sqlite",
      "fluxo ['1','s','','',''] → 's' recusado no banco, sqlite selecionado")
check("Opção inválida — digite 1 para" in _saida_s,
      "fluxo do banco recusa 's' com aviso 'Opção inválida — digite 1 para'")

# ================== portas/serviços e reuso de container ==================
print("== portas/serviços (scanner) e reuso de container ==")
with mock.patch.object(ativacao, "_portas_scan_cache",
                       {5432: "postgres", 3000: "grafana"}):
    _m = ativacao._msg_porta_em_uso(5432)
check("Portas em uso no servidor" in _m and "5432: postgres" in _m
      and "Portas livres (exemplos)" in _m,
      "_msg_porta_em_uso mostra todas as portas em uso + serviços e livres")
_cfg_r = {"porta_postgres": 5432,
          "postgres_url": "postgresql+psycopg2://intranet:intranet@localhost:5432/intranet"}
with mock.patch.object(ativacao, "_postgres_docker_ativo", return_value=5444), \
        mock.patch.object(ativacao, "_verificar_postgres", return_value=True), \
        mock.patch.object(ativacao, "docker_instalado", return_value=True):
    _ok = ativacao.iniciar_postgres(_cfg_r)
check(_ok is True and _cfg_r["porta_postgres"] == 5444
      and "5444" in _cfg_r["postgres_url"],
      "iniciar_postgres reusa container ativo (conecta, não baixa/subir)")
with mock.patch.object(ativacao, "_postgres_docker_ativo", return_value=None), \
        mock.patch.object(ativacao, "_detectar_postgres_rodando",
                          return_value=None), \
        mock.patch.object(ativacao, "_porta_livre", return_value=False):
    _ok2 = ativacao.iniciar_postgres({"porta_postgres": 5432})
check(_ok2 is False, "iniciar_postgres sem container ativo e porta ocupada → False")
with mock.patch.object(ativacao, "_garantir_sdk_otel", return_value=False):
    check(ativacao.iniciar_stack_otel({}) is False,
          "iniciar_stack_otel sem SDK → False")
import contextlib
try:
    ativacao.cli_opcoes(["--scan-ports"])
    _saiu = False
except SystemExit as _e:
    _saiu = _e.code == 0
check(_saiu, "cli_opcoes(['--scan-ports']) imprime portas e sai com exit 0")

# ================== espera adaptativa (race do pull no terminal) ==================
print("== espera adaptativa: pull em terminal separado (race) ==")


class _Relogio:
    """Relógio fake: avança 1 s por chamada (simula o tempo real do loop)."""

    def __init__(self):
        self.t = 0.0

    def __call__(self):
        self.t += 1.0
        return self.t


_cfg_pull = {"porta_postgres": 5432,
             "postgres_url": "postgresql+psycopg2://intranet:intranet"
                             "@localhost:5432/intranet"}

# 1) abrir_terminal → True (pull no terminal) e _verificar_postgres só True
#    APÓS 60 iterações → o helper DEVE esperar (não desiste em 30 s).
_contador_lento = {"n": 0}


def _verificar_lento(_dsn):
    _contador_lento["n"] += 1
    return _contador_lento["n"] >= 60  # só online após 60 verificações (> 30 antigas)


with mock.patch.object(ativacao, "_postgres_docker_ativo", return_value=None), \
        mock.patch.object(ativacao, "_detectar_postgres_rodando",
                          return_value=None), \
        mock.patch.object(ativacao, "_porta_livre", return_value=True), \
        mock.patch.object(ativacao, "_garantir_docker_compose",
                          return_value=["docker", "compose"]), \
        mock.patch.object(ativacao, "_cmd", return_value=True), \
        mock.patch.object(ativacao, "abrir_terminal", return_value=True), \
        mock.patch.object(ativacao, "_verificar_postgres",
                          side_effect=_verificar_lento), \
        mock.patch.object(ativacao, "_container_existe", return_value=True), \
        mock.patch.object(ativacao, "_pull_em_andamento", return_value=False), \
        mock.patch.object(ativacao, "_imagem_baixada", return_value=True), \
        mock.patch.object(ativacao.time, "sleep"):
    _ok_pull = ativacao.iniciar_postgres(_cfg_pull)
check(_ok_pull is True and _contador_lento["n"] >= 60,
      "pull no terminal: verificar só True após 60 iterações → espera (não desiste em 30 s)")

# 2) _verificar_postgres sempre False e container nunca aparece → falha após
#    o timeout generoso (~180 s) com mensagem clara (pull ainda em andamento).
_contador_nunca = {"n": 0}


def _verificar_nunca(_dsn):
    _contador_nunca["n"] += 1
    return False


_buf_falha = io.StringIO()
with mock.patch.object(ativacao, "_postgres_docker_ativo", return_value=None), \
        mock.patch.object(ativacao, "_detectar_postgres_rodando",
                          return_value=None), \
        mock.patch.object(ativacao, "_porta_livre", return_value=True), \
        mock.patch.object(ativacao, "_garantir_docker_compose",
                          return_value=["docker", "compose"]), \
        mock.patch.object(ativacao, "_cmd", return_value=True), \
        mock.patch.object(ativacao, "abrir_terminal", return_value=True), \
        mock.patch.object(ativacao, "_verificar_postgres",
                          side_effect=_verificar_nunca), \
        mock.patch.object(ativacao, "_container_existe", return_value=False), \
        mock.patch.object(ativacao, "_pull_em_andamento", return_value=True), \
        mock.patch.object(ativacao, "_imagem_baixada", return_value=False), \
        mock.patch.object(ativacao.time, "sleep"), \
        mock.patch.object(ativacao.time, "monotonic", _Relogio()), \
        mock.patch("sys.stdout", _buf_falha):
    _ok_never = ativacao.iniciar_postgres(_cfg_pull)
check(_ok_never is False and _contador_nunca["n"] >= 180
      and ativacao._ultimo_motivo == "timeout"
      and "tempo limite esgotado" in _buf_falha.getvalue(),
      "container nunca aparece → falha após ~180 s com mensagem clara "
      "(timeout, pull ainda em andamento)")

# 3) abrir_terminal → False (fallback console) → comportamento atual
#    preservado: pull + up no console principal.
_chamadas_fallback = {"cmd": 0, "pre_pull": 0, "term": 0}


def _cmd_fallback(*_args, **_kwargs):
    _chamadas_fallback["cmd"] += 1
    return True


def _pre_pull_fallback(_imagens):
    _chamadas_fallback["pre_pull"] += 1


def _abrir_fallback(_comando):
    _chamadas_fallback["term"] += 1
    return False


with mock.patch.object(ativacao, "_postgres_docker_ativo", return_value=None), \
        mock.patch.object(ativacao, "_detectar_postgres_rodando",
                          return_value=None), \
        mock.patch.object(ativacao, "_porta_livre", return_value=True), \
        mock.patch.object(ativacao, "_garantir_docker_compose",
                          return_value=["docker", "compose"]), \
        mock.patch.object(ativacao, "_cmd", side_effect=_cmd_fallback), \
        mock.patch.object(ativacao, "abrir_terminal",
                          side_effect=_abrir_fallback), \
        mock.patch.object(ativacao, "_pre_pull", side_effect=_pre_pull_fallback), \
        mock.patch.object(ativacao, "_verificar_postgres", return_value=True), \
        mock.patch.object(ativacao, "_container_existe", return_value=True), \
        mock.patch.object(ativacao, "_pull_em_andamento", return_value=False), \
        mock.patch.object(ativacao, "_imagem_baixada", return_value=True), \
        mock.patch.object(ativacao.time, "sleep"):
    _ok_fallback = ativacao.iniciar_postgres(_cfg_pull)
check(_ok_fallback is True and _chamadas_fallback["pre_pull"] == 1
      and _chamadas_fallback["cmd"] == 2  # down + up -d
      and _chamadas_fallback["term"] == 2,  # comando_terminal + ps
      "fallback (sem terminal): pull+up no console e abrir_terminal chamado 2×")

# 4) helper direto: pull parou sem nada chegar (sem internet) → falha CEDO
#    com motivo pull_falhou (não espera o timeout inteiro).
with mock.patch.object(ativacao, "_container_existe", return_value=False), \
        mock.patch.object(ativacao, "_pull_em_andamento", return_value=False), \
        mock.patch.object(ativacao, "_imagem_baixada", return_value=False), \
        mock.patch.object(ativacao.time, "sleep"), \
        mock.patch.object(ativacao.time, "monotonic", _Relogio()):
    _ok_early = ativacao._aguardar_container(
        "intranet_postgres", timeout=180,
        verificar=lambda: False, imagem="postgres:16-alpine",
        rotulo="PostgreSQL", passo=1.0)
check(_ok_early is False and ativacao._ultimo_motivo == "pull_falhou",
      "helper: pull parou sem container/imagem → falha cedo (pull_falhou, rede?)")

# 5) helper direto: pull EM ANDAMENTO (container não existe) → NÃO desiste e
#    retorna online quando verificar responde.
_verif_depois = {"n": 0}


def _verificar_depois(_dsn=None):
    _verif_depois["n"] += 1
    return _verif_depois["n"] >= 5


with mock.patch.object(ativacao, "_container_existe", return_value=False), \
        mock.patch.object(ativacao, "_pull_em_andamento", return_value=True), \
        mock.patch.object(ativacao, "_imagem_baixada", return_value=False), \
        mock.patch.object(ativacao.time, "sleep"), \
        mock.patch.object(ativacao.time, "monotonic", _Relogio()):
    _ok_depois = ativacao._aguardar_container(
        "intranet_postgres", timeout=180,
        verificar=_verificar_depois, imagem="postgres:16-alpine",
        rotulo="PostgreSQL", passo=1.0)
check(_ok_depois is True and ativacao._ultimo_motivo == "online"
      and _verif_depois["n"] == 5,
      "helper: pull em andamento não desiste e retorna online quando responde")

# 6) iniciar_stack_otel: pull no terminal → espera adaptativa (~240 s),
#    sem desistir no loop antigo de 80 s.
_contador_otel = {"n": 0}


def _servicos_nunca(_porta):
    _contador_otel["n"] += 1
    return False


with mock.patch.object(ativacao, "_garantir_sdk_otel", return_value=True), \
        mock.patch.object(ativacao, "_otel_docker_ativo", return_value=False), \
        mock.patch.object(ativacao, "_detectar_otel_rodando", return_value={}), \
        mock.patch.object(ativacao, "_garantir_docker_compose",
                          return_value=["docker", "compose"]), \
        mock.patch.object(ativacao, "_cmd", return_value=True), \
        mock.patch.object(ativacao, "abrir_terminal", return_value=True), \
        mock.patch.object(ativacao, "_servicos_otel_online",
                          side_effect=_servicos_nunca), \
        mock.patch.object(ativacao, "_container_existe", return_value=False), \
        mock.patch.object(ativacao, "_pull_em_andamento", return_value=True), \
        mock.patch.object(ativacao, "_imagem_baixada", return_value=False), \
        mock.patch.object(ativacao.time, "sleep"), \
        mock.patch.object(ativacao.time, "monotonic", _Relogio()):
    _ok_otel = ativacao.iniciar_stack_otel({"porta_grafana": 3000})
check(_ok_otel is False and _contador_otel["n"] >= 240
      and ativacao._ultimo_motivo == "timeout",
      "iniciar_stack_otel: pull em andamento → espera ~240 s e falha com "
      "timeout (não desiste em 80 s)")

# 7) fonte: helper presente e timeouts generosos aplicados
_SRC2 = ler("mod_intranet/ativacao.py")
check("def _aguardar_container(container, timeout, verificar, imagem=None," in _SRC2,
      "_aguardar_container criado (espera adaptativa com detecção de progresso)")
check("timeout = 180 if terminal_aberto else 30" in _SRC2,
      "iniciar_postgres usa ~180 s quando o pull roda no terminal")
check("timeout = 240 if terminal_aberto else 80" in _SRC2,
      "iniciar_stack_otel usa ~240 s quando o pull roda no terminal")
check("_motivo_legivel(_ultimo_motivo)" in _SRC2,
      "mensagem de falha do Postgres indica o motivo (pull em andamento × falhou)")
check('for i in range(30):' not in _SRC2 and 'for i in range(40):' not in _SRC2,
      "loops cegos de 30×1 s / 40×2 s removidos")

# ================== reuso: Postgres JÁ rodando em porta ocupada ==================
print("== reuso: Postgres já rodando (antes do pull) ==")
_cfg_r1 = {"porta_postgres": 5432,
           "postgres_url": "postgresql+psycopg2://intranet:intranet@localhost:5432/intranet"}
_chamadas_sem_pull = {"pre_pull": 0, "cmd": 0, "term": 0, "docker_compose": 0}


def _cmd_sem_pull(*_a, **_k):
    _chamadas_sem_pull["cmd"] += 1
    return True


def _pre_pull_sem_pull(_imagens):
    _chamadas_sem_pull["pre_pull"] += 1


def _abrir_sem_pull(_comando):
    _chamadas_sem_pull["term"] += 1
    return False


def _garantir_sem_pull():
    _chamadas_sem_pull["docker_compose"] += 1
    return ["docker", "compose"]


# 5432 ocupada + _verificar_postgres True → detecta 5432 e REUSA (sem pull).
with mock.patch.object(ativacao, "_postgres_docker_ativo", return_value=None), \
        mock.patch.object(ativacao, "_detectar_postgres_rodando",
                          return_value=5432), \
        mock.patch.object(ativacao, "_verificar_postgres", return_value=True), \
        mock.patch.object(ativacao, "_porta_livre", return_value=False), \
        mock.patch.object(ativacao, "_garantir_docker_compose",
                          side_effect=_garantir_sem_pull), \
        mock.patch.object(ativacao, "_cmd", side_effect=_cmd_sem_pull), \
        mock.patch.object(ativacao, "_pre_pull",
                          side_effect=_pre_pull_sem_pull), \
        mock.patch.object(ativacao, "abrir_terminal",
                          side_effect=_abrir_sem_pull):
    _ok_r1 = ativacao.iniciar_postgres(_cfg_r1)
check(_ok_r1 is True and _cfg_r1["porta_postgres"] == 5432
      and _chamadas_sem_pull["pre_pull"] == 0
      and _chamadas_sem_pull["cmd"] == 0
      and _chamadas_sem_pull["term"] == 0
      and _chamadas_sem_pull["docker_compose"] == 0,
      "postgres detectado em 5432 → reusa SEM pull/up/terminal/docker compose")
_buf_r1 = io.StringIO()
with mock.patch.object(ativacao, "_postgres_docker_ativo", return_value=None), \
        mock.patch.object(ativacao, "_detectar_postgres_rodando",
                          return_value=5432), \
        mock.patch.object(ativacao, "_verificar_postgres", return_value=True), \
        mock.patch("sys.stdout", _buf_r1):
    ativacao.iniciar_postgres(_cfg_r1)
check("Serviço PostgreSQL já ativo na porta 5432" in _buf_r1.getvalue()
      and "sem download" in _buf_r1.getvalue(),
      "mensagem clara de reuso do PostgreSQL (porta 5432, sem download)")

# Postgres nativo com creds diferentes (_verificar_postgres False) → NÃO reusa.
_cfg_r2 = {"porta_postgres": 5432,
           "postgres_url": "postgresql+psycopg2://intranet:intranet@localhost:5432/intranet"}
_chamadas_nativo = {"pre_pull": 0, "cmd": 0, "term": 0}


def _cmd_nativo(*_a, **_k):
    _chamadas_nativo["cmd"] += 1
    return True


def _pre_pull_nativo(_imagens):
    _chamadas_nativo["pre_pull"] += 1


def _abrir_nativo(_comando):
    _chamadas_nativo["term"] += 1
    return False


with mock.patch.object(ativacao, "_postgres_docker_ativo", return_value=None), \
        mock.patch.object(ativacao, "_detectar_postgres_rodando",
                          return_value=None), \
        mock.patch.object(ativacao, "_porta_livre", return_value=True), \
        mock.patch.object(ativacao, "_garantir_docker_compose",
                          return_value=["docker", "compose"]), \
        mock.patch.object(ativacao, "_cmd", side_effect=_cmd_nativo), \
        mock.patch.object(ativacao, "_pre_pull", side_effect=_pre_pull_nativo), \
        mock.patch.object(ativacao, "abrir_terminal",
                          side_effect=_abrir_nativo), \
        mock.patch.object(ativacao, "_verificar_postgres", return_value=True), \
        mock.patch.object(ativacao, "_container_existe", return_value=True), \
        mock.patch.object(ativacao, "_pull_em_andamento", return_value=False), \
        mock.patch.object(ativacao, "_imagem_baixada", return_value=True), \
        mock.patch.object(ativacao.time, "sleep"):
    _ok_nativo = ativacao.iniciar_postgres(_cfg_r2)
check(_ok_nativo is True and _chamadas_nativo["pre_pull"] == 1
      and _chamadas_nativo["cmd"] == 2,  # down + up -d
      "postgres nativo com creds diferentes → NÃO reusa → segue para pull/up")
# helper: _detectar_postgres_rodando não reusa quando o probe falha (False).
with mock.patch.object(ativacao, "_portas_em_uso_cached",
                       return_value={5432: "postgres"}), \
        mock.patch.object(ativacao, "_probe_postgres_porta",
                          return_value=False):
    check(ativacao._detectar_postgres_rodando() is None,
          "_detectar_postgres_rodando: probe False (creds diferentes) → None (não reusa)")

# ================== reuso: stack OTel completa/incompleta ==================
print("== reuso: stack OTel (completa/incompleta) ==")
_chamadas_otel = {"pre_pull": 0, "cmd": 0, "term": 0}


def _cmd_otel(*_a, **_k):
    _chamadas_otel["cmd"] += 1
    return True


def _pre_pull_otel(_imagens):
    _chamadas_otel["pre_pull"] += 1


def _abrir_otel(_comando):
    _chamadas_otel["term"] += 1
    return False


# Stack COMPLETA (grafana+loki+tempo+mimir via detecção por scan) → NÃO pull.
_cfg_otel1 = {"porta_grafana": 3000}
with mock.patch.object(ativacao, "_garantir_sdk_otel", return_value=True), \
        mock.patch.object(ativacao, "_otel_docker_ativo", return_value=False), \
        mock.patch.object(ativacao, "_detectar_otel_rodando",
                          return_value={"grafana": 3000, "loki": 3100,
                                        "tempo": 3200, "mimir": 9009,
                                        "collector": 4317}), \
        mock.patch.object(ativacao, "_servicos_otel_online", return_value=True), \
        mock.patch.object(ativacao, "_garantir_docker_compose",
                          return_value=["docker", "compose"]), \
        mock.patch.object(ativacao, "_cmd", side_effect=_cmd_otel), \
        mock.patch.object(ativacao, "_pre_pull", side_effect=_pre_pull_otel), \
        mock.patch.object(ativacao, "abrir_terminal",
                          side_effect=_abrir_otel):
    _ok_otel1 = ativacao.iniciar_stack_otel(_cfg_otel1)
check(_ok_otel1 is True and _chamadas_otel["pre_pull"] == 0
      and _chamadas_otel["cmd"] == 0 and _chamadas_otel["term"] == 0,
      "stack OTel completa → reusa (apenas verifica grafana, SEM pull)")
_buf_otel = io.StringIO()
with mock.patch.object(ativacao, "_garantir_sdk_otel", return_value=True), \
        mock.patch.object(ativacao, "_otel_docker_ativo", return_value=False), \
        mock.patch.object(ativacao, "_detectar_otel_rodando",
                          return_value={"grafana": 3000, "loki": 3100,
                                        "tempo": 3200, "mimir": 9009,
                                        "collector": 4317}), \
        mock.patch.object(ativacao, "_servicos_otel_online", return_value=True), \
        mock.patch("sys.stdout", _buf_otel):
    ativacao.iniciar_stack_otel(_cfg_otel1)
check("Stack OpenTelemetry já ativa nas portas" in _buf_otel.getvalue()
      and "sem download" in _buf_otel.getvalue(),
      "mensagem clara de reuso da stack OTel (sem download)")
# Stack INCOMPLETA (só grafana) → avisa e segue para pull.
_chamadas_otel2 = {"pre_pull": 0, "cmd": 0, "term": 0}


def _cmd_otel2(*_a, **_k):
    _chamadas_otel2["cmd"] += 1
    return True


def _pre_pull_otel2(_imagens):
    _chamadas_otel2["pre_pull"] += 1


def _abrir_otel2(_comando):
    _chamadas_otel2["term"] += 1
    return False


_buf_otel2 = io.StringIO()
with mock.patch.object(ativacao, "_garantir_sdk_otel", return_value=True), \
        mock.patch.object(ativacao, "_otel_docker_ativo", return_value=False), \
        mock.patch.object(ativacao, "_detectar_otel_rodando",
                          return_value={"grafana": 3000}), \
        mock.patch.object(ativacao, "_servicos_otel_online", return_value=True), \
        mock.patch.object(ativacao, "_garantir_docker_compose",
                          return_value=["docker", "compose"]), \
        mock.patch.object(ativacao, "_cmd", side_effect=_cmd_otel2), \
        mock.patch.object(ativacao, "_pre_pull", side_effect=_pre_pull_otel2), \
        mock.patch.object(ativacao, "abrir_terminal",
                          side_effect=_abrir_otel2), \
        mock.patch.object(ativacao, "_container_existe", return_value=True), \
        mock.patch.object(ativacao, "_pull_em_andamento", return_value=False), \
        mock.patch.object(ativacao, "_imagem_baixada", return_value=True), \
        mock.patch.object(ativacao.time, "sleep"), \
        mock.patch("sys.stdout", _buf_otel2):
    _ok_otel2 = ativacao.iniciar_stack_otel(_cfg_otel1)
check(_ok_otel2 is True and _chamadas_otel2["pre_pull"] == 1,
      "stack OTel incompleta (só grafana) → segue para pull dos serviços")
check("mas a stack OTel está incompleta" in _buf_otel2.getvalue()
      and "faltam" in _buf_otel2.getvalue()
      and "será feito o pull dos serviços faltantes" in _buf_otel2.getvalue(),
      "aviso de stack incompleta (faltam loki/tempo/mimir) com pull")

# helper: _detectar_otel_rodando identifica por docker ps / nome do processo.
with mock.patch.object(ativacao, "_portas_docker_servicos_otel",
                       return_value={}), \
        mock.patch.object(ativacao, "_servicos_por_nome",
                          return_value={"grafana": 3000, "loki": 3100}), \
        mock.patch.object(ativacao, "_probe_servicos_http", return_value={}):
    check(ativacao._detectar_otel_rodando() == {"grafana": 3000, "loki": 3100},
          "_detectar_otel_rodando usa nome do processo (grafana+loki)")

# ================== fonte: detecção de reuso presente ==================
print("== fonte: detecção de reuso antes do pull ==")
_SRC3 = ler("mod_intranet/ativacao.py")
check("def _detectar_postgres_rodando():" in _SRC3,
      "_detectar_postgres_rodando criado (probe nas portas ocupadas)")
check("def _detectar_otel_rodando():" in _SRC3,
      "_detectar_otel_rodando criado (identifica grafana/loki/tempo/mimir)")
check("_detectar_postgres_rodando()" in _SRC3
      and "porta_detectada = _detectar_postgres_rodando()" in _SRC3,
      "iniciar_postgres chama a detecção antes do pull/up")
check('Serviço PostgreSQL já ativo na porta' in _SRC3
      and "sem download" in _SRC3,
      "mensagem de reuso do PostgreSQL (sem download)")
check('Stack OpenTelemetry já ativa nas portas' in _SRC3
      and "sem download" in _SRC3,
      "mensagem de reuso da stack OTel (sem download)")
check('mas a stack OTel está incompleta' in _SRC3
      and "será feito o pull dos serviços faltantes" in _SRC3,
      "aviso de stack OTel incompleta (segue para pull)")
check("concurrent.futures.ThreadPoolExecutor" in _SRC3,
      "probe HTTP usa threads (concurrent.futures)")
check("connect_timeout=" in _SRC3,
      "probe do Postgres usa timeout curto (connect_timeout)")

print(f"RESULTADO: {_OK} OK, {_TOTAL - _OK} falha(s) de {_TOTAL} verificações")
sys.exit(0 if _OK == _TOTAL else 1)