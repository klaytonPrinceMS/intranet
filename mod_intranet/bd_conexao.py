"""Central database connection and configuration layer. Internally delegates
to `Repositorio` (SQLAlchemy ORM) while keeping raw sqlite3 `get_connection`
for backward compatibility.

Conexão e configurações centrais do Intranet (banco central db_mod_intranet.db).

Camada mais baixa: sem imports circulares — só os outros módulos dependem daqui.
Usa `Repositorio` (SQLAlchemy ORM) internamente para `get_config`/`set_config`;
mantém `get_connection` (sqlite3 raw) para compatibilidade com código
legado que ainda não foi migrado. Notificações pós-gravação (ex.: limpar
caches `lru_cache` de outros módulos) usam `registrar_hook_config` —
nunca import direto (nem lazy) de outro módulo aqui dentro.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

import sqlite3
from functools import lru_cache

_HOOKS_CONFIG = []  # lista de (fn, chaves_ou_None)


def registrar_hook_config(fn, apenas_chaves=None):
    """Registra fn() para rodar após cada gravação de config bem-sucedida.

    Usado por módulos com caches derivados de `tb_config` (ex.: tema,
    template de empenhos): em vez de `bd_conexao` importar o módulo
    (ciclo núcleo→módulo), o módulo se registra aqui no próprio import.
    `apenas_chaves` restringe o disparo (ex.: "empenhos_template_nome").
    Hooks nunca derrubam o `set_config` (cada um roda em try/except).
    """
    if isinstance(apenas_chaves, str):
        chaves = {apenas_chaves}
    elif apenas_chaves:
        chaves = set(apenas_chaves)
    else:
        chaves = None
    def _mesmo(a, b):
        return (getattr(a, "__func__", a) is getattr(b, "__func__", b)
                and getattr(a, "__self__", None) is getattr(b, "__self__", None))
    if callable(fn) and all(not _mesmo(f, fn) for f, _ in _HOOKS_CONFIG):
        _HOOKS_CONFIG.append((fn, chaves))

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "db_mod_intranet.db")

PADRAO_CONFIG = {
    "titulo_sistema": "INTRANET",
    "icone_sistema": "hub",
    "cor_principal": "#000000",
    "cor_fundo": "#EEEEEE",
    "texto_login_titulo": "INTRANET Básica",
    "texto_login_subtitulo": "Acesso restrito a usuários autorizados",
    "texto_login_hint": "Novos usuários? Procure o DTI para realizar o seu cadastro.",
    "texto_home_saudacao": "Olá",
    "texto_home_subtitulo": "Sua intranet corporativa é tudo em um só lugar.",
    "texto_rodape": "uso interno",
    # Observabilidade — loguru (aba Observabilidade)
    "log_ativo": "1",
    "log_nivel": "INFO",
    "log_rotacao": "1 month",
    "log_retencao": "4 months",
    "log_console": "auto",
    "log_otel_envio": "1",
    "log_otel_nivel": "DEBUG",
    # Observabilidade — telemetria OTel / stack remota
    "otel_ativo": "1",
    "otel_endpoint": "localhost:4317",
    "otel_auto_start_stack": "1",
    # Observabilidade — Grafana
    "grafana_url": "http://localhost:3000",
    # Documentação MkDocs — sobe no boot salvo docs_ativo=0 (admin religa sob demanda)
    "docs_ativo": "1",
    # SGBD — SQLite (padrão universal) ou PostgreSQL opcional em container
    # (docker/postgres/docker-compose.yml; engine via banco_conexao.py)
    "banco_tipo": "sqlite",
    "postgres_url": "postgresql+psycopg2://intranet:intranet@localhost:5432/intranet",
    # Usuário de operações normais (criado no banco PostgreSQL)
    "banco_usuario": "klayton",
    "banco_senha": "klayton",
    # Usuário de operações administrativas (criação de banco, migrations)
    "banco_admin_usuario": "master",
    "banco_admin_senha": "master",
    # Aparência do módulo Intranet (botões do sistema — mesmo contrato
    # de 6 chaves dos demais módulos, prefixo "intranet")
    "intranet_cor_botao": "#000000",
    "intranet_cor_texto_botao": "#FFFFFF",
    "intranet_cor_fundo": "",
    "intranet_cor_titulo": "#212121",
    "intranet_btn_tamanho": "medium",
    "intranet_texto_header": "",
    # Aparência dos cards do módulo Intranet (fundo + texto base)
    "intranet_cor_fundo_card": "#FFFFFF",
    "intranet_cor_texto_card": "",
    # Avisos do sistema (toasts): tempo de exibição em segundos (1-30, padrão 5)
    "notificacao_timeout": "5",
    # Card "Configurações gerais": intervalo do backup em horas e retenção de
    # sessão em dias. Viviam SÓ como literais espalhados (INSERT de banco novo
    # + `padrao=` da tela + dicionário do "Restaurar padrão"), então o card não
    # tinha fonte única de verdade e um padrão divergente quebrava a tela
    # quando a chave faltava no tb_config. Aqui ficam canônicos.
    "backup_interval_hours": "12",
    "sessao_retencao": "50",
    # Contador de acessos ao sistema (incrementado a cada login bem-sucedido)
    "contador_acessos_total": "0",
    "contador_acessos_inicio": "",
    # Validação de senha (`mod_intranet/validador_senha.py`).
    #
    # A sondagem de internet é o que garante o requisito de rede local: com
    # `senha_sondar_internet=0` a camada de vazamento nem tenta abrir socket,
    # e com `senha_consultar_vazamento=0` ela some de vez. As duas são 1 por
    # padrão porque a sondagem é barata e tem cache de 15 min — mas quem instala
    # em rede fechada tem o botão para desligar sem mexer em código.
    "senha_consultar_vazamento": "1",
    "senha_sondar_internet": "1",
    # 6 é o piso que já valia no código; subir barra o existente sem querer.
    "senha_tamanho_minimo": "6",
    # Tentativas de login (30/09/2026): 3 é o PISO, configurável pelo admin até
    # 20. Acima do piso, o login errado NÃO bloqueia a conta — aumenta a
    # espera (1s, 2,5s, 5s… até o teto), que encarece o ataque de dicionário
    # sem fechar o acesso de quem só esqueceu a senha.
    "login_tentativas_maximas": "3",
    "login_atraso_maximo_seg": "30",
}


def get_connection():
    """Legacy raw DBAPI connection (WAL + synchronous=NORMAL).

    Prefer `Repositorio` from `repositorio.py` for new code.
    EN: Returns a DBAPI connection (SQLite or PostgreSQL) for legacy callers.
    PT: Devolve conexão DBAPI (SQLite ou PostgreSQL) para código legado.
    """
    from mod_intranet.banco_conexao import conexao
    conn = conexao("intranet")
    if conn is None:
        raise RuntimeError("Falha ao abrir conexão do banco central")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_db():
    """Bootstrap do banco central: cria tabelas e semeia padrões (idempotente).

    Usa `conexao("intranet")` (SQLite ou PostgreSQL) — o sistema controla o
    backend. `INSERT OR IGNORE` virou `ON CONFLICT DO NOTHING` (portável).
    """
    from mod_intranet.banco_conexao import conexao

    conn = conexao("intranet")
    if conn is None:
        raise RuntimeError("Falha ao abrir conexão do banco central")
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_config (
            chave TEXT PRIMARY KEY,
            valor TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_sessoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT NOT NULL,
            modulo TEXT,
            login_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            logout_timestamp DATETIME,
            cookie_hash TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_modulos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chave TEXT NOT NULL UNIQUE,
            nome TEXT NOT NULL,
            icone TEXT,
            rota TEXT NOT NULL,
            ativo INTEGER NOT NULL DEFAULT 1,
            nativo INTEGER NOT NULL DEFAULT 0,
            ordem INTEGER NOT NULL DEFAULT 0
        )
    """)
    # Verificação de senha (`validador_senha.py`), 30/09/2026.
    #
    # `tb_senha_vazamento_cache` NÃO é o corpus de senhas vazadas, e sim a
    # memória das consultas já feitas: par (prefixo, sufixo) do SHA-1 e a
    # contagem devolvida. Existe para a segunda tentativa com a mesma senha sair
    # instantânea e sem repetir chamada — e para que o caminho que BLOQUEIA a
    # troca (que roda no event-loop e por isso não pode depender de rede)
    # consiga ler o veredito em vez de refazer a consulta.
    #
    # `tb_senha_padrao_organizacao` é configuração do PRÓPRIO órgão: as
    # palavras com as quais o público monta senha (nome da prefeitura, do
    # órgão, um termo do serviço). `tipo='exata'` compara a senha inteira;
    # `tipo='palavra'` reprova se a senha CONTER o padrão.
    #
    # A lista de senhas vazadas em texto plano fica de fora, de propósito: ver
    # `validador_senha.motivos_sem_corpus()`.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_senha_vazamento_cache (
            prefixo TEXT NOT NULL,
            sufixo TEXT NOT NULL,
            contagem INTEGER NOT NULL DEFAULT 0,
            data_consulta DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (prefixo, sufixo)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tb_senha_padrao_organizacao (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            padrao TEXT NOT NULL UNIQUE,
            descricao TEXT,
            tipo TEXT NOT NULL DEFAULT 'palavra',
            ativo INTEGER NOT NULL DEFAULT 1,
            data_cadastro DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("SELECT COUNT(*) FROM tb_config")
    if (cur.fetchone()[0] or 0) == 0:
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES ('versao_sistema', '1.0.260913')")
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES ('cotadisco_global_gb', '10')")
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES ('backup_interval_hours', '12')")
    for _chave_mod, _ver in (
        ("usuarios", "1.0.260918"),
        ("auditoria", "1.0.260908"),
        ("editar_pdf", "1.0.260908"),
        ("empenhos", "1.0.260913"),
        ("blog", "1.0.260908"),
        ("solicita_impressao", "1.0.260913"),
        # Módulos que entraram em MODULOS_BD sem linha correspondente aqui, e
        # por isso rodavam com a versão padrão '1.0' no rodapé. O seed acima
        # só alcança banco novo; a migração `migracao_versao_pendentes_260928`
        # é quem alcança o banco já em uso.
        ("agregador_noticias", "1.0.260928"),
        ("lista_telefonica", "1.0.260928"),
        ("filas", "1.0.260928"),
        ("tecnico", "1.0.260928"),
        ("os", "1.0.260928"),
        ("estoque", "1.0.260928"),
    ):
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES (?, ?) "
                    "ON CONFLICT DO NOTHING",
                    (f"versao_modulo:{_chave_mod}", _ver))
    for chave, valor in PADRAO_CONFIG.items():
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES (?, ?) "
                    "ON CONFLICT DO NOTHING", (chave, valor))
    # Semente dos padrões do órgão (30/09/2026). Genéricos de propósito: o
    # administrador edita, desativa ou apaga em `validador_senha` pela tela de
    # administração. O que entra aqui é o que o servidor DAQUI monta senha —
    # o nome da instituição e o termo do serviço —, não dado de terceiros.
    for _pad, _desc in (
        ("prefeitura", "Nome da instituição"),
        ("municipio", "Nome do município"),
        ("cidade", "Como o município é chamado"),
        ("servidor", "Cargo de quem usa o sistema"),
        ("detran", "Órgão"),
        ("tributos", "Área de atendimento"),
        ("camara", "Órgão"),
    ):
        cur.execute("INSERT INTO tb_senha_padrao_organizacao (padrao, descricao, "
                    "tipo, ativo) VALUES (?, ?, 'palavra', 1) "
                    "ON CONFLICT DO NOTHING", (_pad, _desc))
    # Migração ÚNICA (06/09): cores padrão por módulo. O banco existente guardou
    # valores antigos/customizados semeados (intranet/`cor_principal` = #1565C0,
    # blog/editpdf/empenhos/solicita com cores soltas) que sobrescrevem os
    # padrões do PRÓPRIO módulo. Zeramos as chaves `<prefixo>_cor_botao` para que
    # cada módulo caia no `PADROES_TEMA` (blog #000000, empenhos #000000,
    # editar_pdf #000000, solicita_impressao #000000, demais #000000). Guardado
    # pelo marcador `migracao_cores_padrao` — roda UMA vez para não apagar
    # futuras personalizações do admin.
    cur.execute("SELECT COUNT(*) FROM tb_config WHERE chave='migracao_cores_padrao'")
    migrado = (cur.fetchone()[0] or 0) > 0
    if not migrado:
        cur.execute("UPDATE tb_config SET valor='#000000' "
                    "WHERE chave='cor_principal' AND valor='#1565C0'")
        for _chave in ("intranet", "usuarios", "auditoria", "blog",
                       "editpdf", "empenhos", "solicita_impressao"):
            cur.execute("UPDATE tb_config SET valor='' WHERE chave=?",
                        (f"{_chave}_cor_botao",))
        cur.execute("INSERT INTO tb_config (chave, valor) "
                    "VALUES ('migracao_cores_padrao', '1') ON CONFLICT DO NOTHING")
    # Migração ÚNICA (08/09): padronização geral — TODOS os módulos na cor do
    # intranet (PRETO #000000, via `PADROES_TEMA`) e versão sistema+módulos em
    # 1.0.260908. Zera as chaves de cor de botão dos módulos (caem no padrão do
    # próprio módulo, agora #000000) e atualiza as versões. Guardado pelo
    # marcador `migracao_padronizacao_260908` — roda UMA vez.
    cur.execute("SELECT COUNT(*) FROM tb_config WHERE chave='migracao_padronizacao_260908'")
    if (cur.fetchone()[0] or 0) == 0:
        for _chave in ("intranet", "usuarios", "auditoria", "blog",
                       "editpdf", "empenhos", "solicita_impressao"):
            cur.execute("UPDATE tb_config SET valor='' WHERE chave=?",
                        (f"{_chave}_cor_botao",))
        cur.execute("UPDATE tb_config SET valor='1.0.260908' "
                    "WHERE chave='versao_sistema'")
        cur.execute("UPDATE tb_config SET valor='1.0.260908' "
                    "WHERE chave LIKE 'versao_modulo:%'")
    cur.execute("INSERT INTO tb_config (chave, valor) "
                     "VALUES ('migracao_padronizacao_260908', '1') ON CONFLICT DO NOTHING")
    # Migração 260913 — solicita_impressao: seeds iniciais + bump de versão.
    #
    # ESTA LINHA ERA SOLTA (sem marcador) e é a razão de a versão deste módulo
    # não conseguir segurar um bump: rodava a CADA `init_db`, e o
    # `valor != '1.0.260913'` faz dela um REBAIXAMENTO — ela escrevia 13/09
    # por cima de qualquer versão mais nova. Foi assim que o bump de 30/09
    # apareceu como 1.0.260930 numa rodada e como 1.0.260913 na seguinte.
    # A §4.2 é explícita: migração tem de ser idempotente e não pode
    # sobrescrever versão que já evoluiu (ou que o admin tenha mexido).
    # Agora tem marcador próprio e só cria a linha quando ela NÃO existe
    # (`ON CONFLICT DO NOTHING`) — nunca rebaixa, e quem vier depois (o bump
    # de 30/09, mais abaixo) tem a palavra final.
    cur.execute("SELECT COUNT(*) FROM tb_config "
                "WHERE chave='migracao_versao_solicita_impressao_260913'")
    if (cur.fetchone()[0] or 0) == 0:
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES "
                    "('versao_modulo:solicita_impressao', '1.0.260913') "
                    "ON CONFLICT DO NOTHING")
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES "
                    "('migracao_versao_solicita_impressao_260913', '1') "
                    "ON CONFLICT DO NOTHING")
    # Migração 13/09/2026 — bump versão do módulo empenhos (padrão PIC + contagem padronizada + CSS docs)
    cur.execute("SELECT COUNT(*) FROM tb_config WHERE chave='migracao_versao_empenhos_260913'")
    if (cur.fetchone()[0] or 0) == 0:
        cur.execute("UPDATE tb_config SET valor='1.0.260913' WHERE chave='versao_modulo:empenhos'")
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES ('migracao_versao_empenhos_260913', '1') ON CONFLICT DO NOTHING")
    # Migração 13/09/2026 — bump versão intranet/sistema (contagem padronizada + PIC + CSS docs)
    cur.execute("SELECT COUNT(*) FROM tb_config WHERE chave='migracao_versao_intranet_260913'")
    if (cur.fetchone()[0] or 0) == 0:
        cur.execute("UPDATE tb_config SET valor='1.0.260913' WHERE chave='versao_sistema'")
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES ('versao_sistema', '1.0.260913') ON CONFLICT DO NOTHING")
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES ('versao_modulo:intranet', '1.0.260913') ON CONFLICT DO NOTHING")
        cur.execute("UPDATE tb_config SET valor='1.0.260913' WHERE chave='versao_modulo:intranet'")
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES ('migracao_versao_intranet_260913', '1') ON CONFLICT DO NOTHING")
    # Migração 18/09/2026 — bump versão do módulo usuarios (acesso padrão
    # comum em editar_pdf/empenhos/solicita_impressao, nova ordem dos
    # módulos, blog indesativável, senha provisória 123456 no cadastro)
    cur.execute("SELECT COUNT(*) FROM tb_config WHERE chave='migracao_versao_usuarios_260918'")
    if (cur.fetchone()[0] or 0) == 0:
        cur.execute("UPDATE tb_config SET valor='1.0.260918' WHERE chave='versao_modulo:usuarios'")
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES ('migracao_versao_usuarios_260918', '1') ON CONFLICT DO NOTHING")
    # Migração 28/09/2026 — VERSÃO DOS MÓDULOS QUE ESTAVAM SEM VERSÃO.
    # Seis chaves de `MODULOS_BD` (repositorio.py) nunca chegaram ao tuple de
    # seed acima, então não tinham `versao_modulo:<chave>` em `tb_config`. Sem a
    # chave, `_obter_versao_modulo` (telas.py) devolve '1.0' e o rodapé mostra
    # `v<versao_sistema> · v1.0` — sem distinguir o código de hoje do de amanhã.
    #   os/estoque      — nasceram no commit 9a7d57d (28/09) sem linha de seed.
    #   agregador_noticias/lista_telefonica/filas/tecnico — débito anterior,
    #                     entraram em MODULOS_BD antes de o tuple existir.
    # `INSERT OR IGNORE` com um `UPDATE` só onde ainda é PLACEHOLDER.
    #
    # POR QUE A LISTA DE PLACEHOLDERS INCLUI '1.0.260908' — a ordem das
    # migrações importa e é fácil errar aqui: num banco NOVO, o seed acima grava
    # 1.0.260928 e a migração `migracao_padronizacao_260908` (mais acima, neste
    # mesmo `init_db`) roda `UPDATE ... WHERE chave LIKE 'versao_modulo:%'`,
    # rebaixando TUDO para 1.0.260908. Sem esta linha no filtro, a correção
    # nunca entraria numa instalação nova: o `INSERT` não faz nada (a chave já
    # existe) e o `UPDATE` não casa com 1.0.260908. O que NÃO entra é uma
    # versão que já evoluiu para outra data — essa é bump futuro, e bump
    # futuro não é da conta desta migração.
    cur.execute("SELECT COUNT(*) FROM tb_config "
                "WHERE chave='migracao_versao_pendentes_260928'")
    if (cur.fetchone()[0] or 0) == 0:
        for _chave_mod in ("agregador_noticias", "lista_telefonica", "filas",
                           "tecnico", "os", "estoque"):
            cur.execute("INSERT INTO tb_config (chave, valor) VALUES (?, '1.0.260928') "
                        "ON CONFLICT DO NOTHING",
                        (f"versao_modulo:{_chave_mod}",))
            cur.execute("UPDATE tb_config SET valor='1.0.260928' "
                        "WHERE chave=? AND (valor IS NULL OR valor='' "
                        "OR valor IN ('1.0', '1.0.260908'))",
                        (f"versao_modulo:{_chave_mod}",))
        cur.execute("INSERT INTO tb_config (chave, valor) "
                    "VALUES ('migracao_versao_pendentes_260928', '1') ON CONFLICT DO NOTHING")
    # Bumps de 29/09/2026 — DIÁLOGO DE FORMULÁRIO RESPONSIVO (AGENTS.md §4.2:
    # toda alteração de código obriga a atualizar a versão do módulo).
    #   mod_intranet        — base `dialogo_formulario` /
    #                         `LARGURA_DIALOGO_FORMULARIO` / `CSS_GRADE_*` em
    #                         `ui_comum`, e os diálogos de Meu Perfil, Troca de
    #                         senha e Seus telefones em `telas.py`
    #   mod_gest_cad_usuario — diálogos Novo usuário, Editar, Duplicar e Sessões
    #   mod_estoque         — 11 diálogos de movimentação/ajuste
    #   mod_lista_telefonica — diálogos Novo contato, Nova unidade e Reordenar
    #   mod_tecnico         — diálogo de listagem de arquivos
    #
    # Bump do `usuarios` em 30/09/2026 — PRIMEIRA CARGA DA FOLHA NO BOOT.
    # `mod_intranet/bd_criador.py` passou a chamar `carga_automatica()` logo
    # depois do `init_users()`, para que o cadastro de servidores nasça junto
    # com o banco em vez de ficar vazio até o agendador das 03:00. Marcador
    # PRÓPRIO (`carga_folha`), e não um dos de hoje, porque este é um desenho
    # novo — inicializador, não agendador — e a §4.2 exige um bump rastreável
    # por alteração, não por dia.
    cur.execute("SELECT COUNT(*) FROM tb_config "
                "WHERE chave='migracao_versao_usuarios_260930_carga_folha'")
    if (cur.fetchone()[0] or 0) == 0:
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES "
                    "('versao_modulo:usuarios', '1.0.260930') "
                    "ON CONFLICT DO NOTHING")
        cur.execute("UPDATE tb_config SET valor='1.0.260930' "
                    "WHERE chave='versao_modulo:usuarios'")
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES "
                    "('migracao_versao_usuarios_260930_carga_folha', '1') "
                    "ON CONFLICT DO NOTHING")

    # Bump do `usuarios` em 01/10/2026 — COLETA COM INTERVALO VARIÁVEL.
    # O intervalo fixo de 1,2 s virou espera sorteada na faixa 1 s–5 s, e a
    # `fonte_folha.json` passou a `origem: "csv"`: a folha é coletada UMA vez
    # para `dados/`, e a carga passa a ler o arquivo local — medido 0,02 s para
    # 1.165 servidores, contra ~88 s de coleta pela rede. É a decisão que tira
    # o boot e as 03:00 da dependência do servidor de terceiro.
    cur.execute("SELECT COUNT(*) FROM tb_config "
                "WHERE chave='migracao_versao_usuarios_261001_intervalo_csv'")
    if (cur.fetchone()[0] or 0) == 0:
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES "
                    "('versao_modulo:usuarios', '1.0.261001') "
                    "ON CONFLICT DO NOTHING")
        cur.execute("UPDATE tb_config SET valor='1.0.261001' "
                    "WHERE chave='versao_modulo:usuarios'")
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES "
                    "('migracao_versao_usuarios_261001_intervalo_csv', '1') "
                    "ON CONFLICT DO NOTHING")

    # Bump do `auditoria` em 01/10/2026 — CONEXÃO DE GRAVAÇÃO REUTILIZADA.
    # `registrar_auditoria` abria uma conexão nova do banco de auditoria a cada
    # registro (mais dois PRAGMA). Medido: **280 ms -> 2,4 ms** por registro, e
    # a carga da folha — que audita ~3 vezes por servidor — saiu de ~30 min
    # para minutos. A correção é uma conexão privada por thread, e NÃO um cache
    # em `get_auditoria_connection`, porque o contrato dela é "a chamada é dona
    # da conexão e pode fechá-la" (e há quem feche).
    cur.execute("SELECT COUNT(*) FROM tb_config "
                "WHERE chave='migracao_versao_auditoria_261001_conexao_gravacao'")
    if (cur.fetchone()[0] or 0) == 0:
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES "
                    "('versao_modulo:auditoria', '1.0.261001') "
                    "ON CONFLICT DO NOTHING")
        cur.execute("UPDATE tb_config SET valor='1.0.261001' "
                    "WHERE chave='versao_modulo:auditoria'")
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES "
                    "('migracao_versao_auditoria_261001_conexao_gravacao', '1') "
                    "ON CONFLICT DO NOTHING")

    # Bump do `intranet` em 01/10/2026 — a MENSAGEM da primeira carga da folha
    # dizia "~2 min" onde o medido é ~25–35 min. Parece comentário, mas é a
    # linha que alguém lê no console enquanto espera o servidor subir, e um
    # número errado ali faz o administrador achar que o boot travou e matar
    # o processo. A §4.2 não faz exceção para texto, então o bump vem junto.
    cur.execute("SELECT COUNT(*) FROM tb_config "
                "WHERE chave='migracao_versao_intranet_261001_tempo_carga_folha'")
    if (cur.fetchone()[0] or 0) == 0:
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES "
                    "('versao_modulo:intranet', '1.0.261001') "
                    "ON CONFLICT DO NOTHING")
        cur.execute("UPDATE tb_config SET valor='1.0.261001' "
                    "WHERE chave='versao_modulo:intranet'")
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES "
                    "('migracao_versao_intranet_261001_tempo_carga_folha', '1') "
                    "ON CONFLICT DO NOTHING")

    # Bump do `intranet` em 01/10/2026 — VIGIA DO SERVIDOR (arquivo novo).
    # `mod_intranet/vigia_servidor.py`: observa a porta 8080 e reinicia o
    # servidor se ela ficar muda. Não mata processo nenhum — um laço que
    # também "enferruja" processos transforma uma sondagem ruim em queda.
    # Mesma data do bump de cima, então a versão não muda de número; o
    # marcador é que torna a alteração rastreável.
    cur.execute("SELECT COUNT(*) FROM tb_config "
                "WHERE chave='migracao_versao_intranet_261001_vigia_servidor'")
    if (cur.fetchone()[0] or 0) == 0:
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES "
                    "('versao_modulo:intranet', '1.0.261001') "
                    "ON CONFLICT DO NOTHING")
        cur.execute("UPDATE tb_config SET valor='1.0.261001' "
                    "WHERE chave='versao_modulo:intranet'")
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES "
                    "('migracao_versao_intranet_261001_vigia_servidor', '1') "
                    "ON CONFLICT DO NOTHING")

    # POR QUE ESCRETO LITERAL E NÃO UM `for` COM f-string
    #     O marcador `migracao_versao_<chave>_<data>` é o que faz a §4.2
    #     verificável: é nele que o `teste_versionamento_modulo.py` procura para
    #     dizer "este módulo foi alterado e não ganhou bump". Numa f-string o
    #     código-fonte tem `{_chave_mod}` e não `intranet` — o marcador some da
    #     leitura estática, tanto para o teste quanto para quem lê o diff. Por
    #     isso os cinco blocos são escritos um a um, como já fazia
    #     `migracao_versao_usuarios_260918`. É verbosidade deliberada: um bump
    #     que não dá para ler não é rastreável.
    cur.execute("SELECT COUNT(*) FROM tb_config "
                "WHERE chave='migracao_versao_intranet_260929'")
    if (cur.fetchone()[0] or 0) == 0:
        cur.execute("INSERT INTO tb_config (chave, valor) "
                    "VALUES ('versao_modulo:intranet', '1.0.260929') "
                    "ON CONFLICT DO NOTHING")
        cur.execute("UPDATE tb_config SET valor='1.0.260929' "
                    "WHERE chave='versao_modulo:intranet'")
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES "
                    "('migracao_versao_intranet_260929', '1') ON CONFLICT DO NOTHING")

    # Bump do `usuarios` pela CORREÇÃO DE SEGURANÇA de 29/09/2026 (2ª do dia,
    # com marcador próprio — a de cima foi do `dialogo_formulario`).
    # `mod_gest_cad_usuario`: o seed de `master` voltava em todo reinício
    # depois da troca de credenciais; agora ele respeita a marca
    # `forcar_troca_credenciais:master`. O `bd_criador.py` legado, que tinha um
    # SEGUNDO `INSERT` de `master/master` sem essa marca, passou a levantar.
    # Bump do `usuarios` em 30/09/2026, marcador próprio: `bd_manipulador.py`
    # ganhou `tb_login_tentativas` e as funções de contagem do atraso
    # progressivo de login. O módulo do cadastro de usuários é o dono do login,
    # então a tabela mora no banco DELE, e não no central.
    cur.execute("SELECT COUNT(*) FROM tb_config "
                "WHERE chave='migracao_versao_usuarios_260930_tentativas_login'")
    if (cur.fetchone()[0] or 0) == 0:
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES "
                    "('versao_modulo:usuarios', '1.0.260930') "
                    "ON CONFLICT DO NOTHING")
        cur.execute("UPDATE tb_config SET valor='1.0.260930' "
                    "WHERE chave='versao_modulo:usuarios'")
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES "
                    "('migracao_versao_usuarios_260930_tentativas_login', '1') "
                    "ON CONFLICT DO NOTHING")

    cur.execute("SELECT COUNT(*) FROM tb_config "
                "WHERE chave='migracao_versao_usuarios_260929_seg'")
    if (cur.fetchone()[0] or 0) == 0:
        cur.execute("INSERT INTO tb_config (chave, valor) "
                    "VALUES ('versao_modulo:usuarios', '1.0.260929') "
                    "ON CONFLICT DO NOTHING")
        cur.execute("UPDATE tb_config SET valor='1.0.260929' "
                    "WHERE chave='versao_modulo:usuarios'")
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES "
                    "('migracao_versao_usuarios_260929_seg', '1') ON CONFLICT DO NOTHING")

    # Bump do `agregador_noticias` pela correção da EXIBIÇÃO de 29/09/2026.
    # A contagem de páginas era feita sobre o total cru (349) enquanto a fatia
    # vinha da amostra de 1 por tema (9 elementos): as páginas 2..30 saíam
    # vazias e caíam no cartão de "nenhuma notícia". Agora a contagem e a fatia
    # saem da MESMA lista, a página 1 continua sendo a amostra por tema e as
    # seguintes mostram o resto. Junto: tamanho de página configurável
    # (múltiplo de 3, mínimo 9, padrão 12) e os dois textos da tela — cabeçalho
    # e aviso de "sem novidade" — tirados do código e agora configuráveis,
    # vazios por padrão.
    cur.execute("SELECT COUNT(*) FROM tb_config "
                "WHERE chave='migracao_versao_agregador_noticias_260929'")
    if (cur.fetchone()[0] or 0) == 0:
        cur.execute("INSERT INTO tb_config (chave, valor) "
                    "VALUES ('versao_modulo:agregador_noticias', '1.0.260929') "
                    "ON CONFLICT DO NOTHING")
        cur.execute("UPDATE tb_config SET valor='1.0.260929' "
                    "WHERE chave='versao_modulo:agregador_noticias'")
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES "
                    "('migracao_versao_agregador_noticias_260929', '1') "
                    "ON CONFLICT DO NOTHING")

    # Segundo bump do `agregador_noticias` em 29/09/2026, com marcador
    # próprio: quantas notícias EU VOU LER virou escolha de quem lê.
    #   • saiu do painel admin (que é do administrador) para a barra da tela
    #     de notícias, visível a qualquer perfil, inclusive `comum`;
    #   • gravada em COOKIE do navegador (`noticias_por_pagina`), mesmo
    #     padrão do `estilo_visual` — é leitura de uma pessoa, não dado do
    #     sistema. Lida UMA VEZ no corpo da página, porque o timer redesenha
    #     a grade sem request e releria o padrão do módulo por baixo;
    #   • a amostra por tema virou ORDEM DE PRIORIDADE no topo, não o
    #     conteúdo da página 1 — antes o slider prometia 63 e a tela mostrava
    #     8, porque a primeira página era só a amostra;
    #   • o tooltip do controle ficou "Quantas notícias por página".
    # A coleta automática e o botão "Coletar agora" (só administrador) não
    # mudaram: quem só lê não dispara coleta.
    cur.execute("SELECT COUNT(*) FROM tb_config "
                "WHERE chave='migracao_versao_agregador_noticias_260929_leitura'")
    if (cur.fetchone()[0] or 0) == 0:
        cur.execute("INSERT INTO tb_config (chave, valor) "
                    "VALUES ('versao_modulo:agregador_noticias', '1.0.260929') "
                    "ON CONFLICT DO NOTHING")
        cur.execute("UPDATE tb_config SET valor='1.0.260929' "
                    "WHERE chave='versao_modulo:agregador_noticias'")
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES "
                    "('migracao_versao_agregador_noticias_260929_leitura', '1') "
                    "ON CONFLICT DO NOTHING")

    # Terceiro bump do `agregador_noticias`, agora em 30/09/2026, com marcador
    # próprio: o slider de "Por página" finalmente GRAVA.
    #
    # Ele gravava o cookie (a rota funcionava), mas arrastar o trilho não
    # mudava nada, por DUAS falhas encadeadas no mesmo controle:
    #   1. o `change` do Quasar chegava ao handler como
    #      `GenericEventArguments`, que não tem `.value` — o handler estourava
    #      ali, ANTES de gravar (`AttributeError` no log do servidor);
    #   2. trocado por `on_value_change` + atraso de 0,8s (que segura o
    #      arrasto e grava uma vez ao soltar o cursor), a chamada final
    #      passou `force_load=True`, que NÃO EXISTE nesta versão do NiceGUI —
    #      a assinatura é `to(target, new_tab=False)`, e o `TypeError`
    #      impedia a navegação para a rota do cookie.
    # Nenhuma das duas aparecia testando a rota direto pela URL: as duas só
    # nascem na interação real com o trilho.
    cur.execute("SELECT COUNT(*) FROM tb_config "
                "WHERE chave='migracao_versao_agregador_noticias_260930_slider'")
    if (cur.fetchone()[0] or 0) == 0:
        cur.execute("INSERT INTO tb_config (chave, valor) "
                    "VALUES ('versao_modulo:agregador_noticias', '1.0.260930') "
                    "ON CONFLICT DO NOTHING")
        cur.execute("UPDATE tb_config SET valor='1.0.260930' "
                    "WHERE chave='versao_modulo:agregador_noticias'")
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES "
                    "('migracao_versao_agregador_noticias_260930_slider', '1') "
                    "ON CONFLICT DO NOTHING")

    # Bump do `intranet` em 30/09/2026, com marcador próprio. O que mudou foi
    # `telas.py`: a troca de senha obrigatória das CONTAS DE TESTE
    # (`qacomum`/`qamaster`, senha `123456` — AGENTS.md §8.2) nasce
    # PRÉ-PREENCHIDA, para a troca virar um clique em vez de digitação de uma
    # senha que já se publica no §8.2. Mesmo espírito do diálogo de
    # credenciais do `master`, que já nasce preenchido.
    #
    # `intranet` não tem linha no tuple de seed de cima (linhas 171-188): a
    # chave nasce na migração `migracao_versao_intranet_260913` e é daqui para
    # frente que a cadeia 260913 -> 260929 -> 260930 a entrega. Banco novo sai
    # certo pela própria cadeia, banco em uso por este marcador.
    cur.execute("SELECT COUNT(*) FROM tb_config "
                "WHERE chave='migracao_versao_intranet_260930'")
    if (cur.fetchone()[0] or 0) == 0:
        cur.execute("INSERT INTO tb_config (chave, valor) "
                    "VALUES ('versao_modulo:intranet', '1.0.260930') "
                    "ON CONFLICT DO NOTHING")
        cur.execute("UPDATE tb_config SET valor='1.0.260930' "
                    "WHERE chave='versao_modulo:intranet'")
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES "
                    "('migracao_versao_intranet_260930', '1') ON CONFLICT DO NOTHING")

    # Bump do `intranet` em 30/09/2026, marcador próprio. Entrou
    # `validador_senha.py`: verificação de força e de vazamento na troca de
    # senha. O requisito que mandou no desenho foi rede local — o sistema não
    # pode travar quando não há internet, tem que ignorar. Daí a separação:
    # o caminho que BLOQUEIA é só o offline (entropia, teclado, sequência,
    # padrões do órgão) e a camada de vazamento é sondada, tem tempo máximo
    # próprio, não faz retry e falha para "indisponível" em vez de travar.
    cur.execute("SELECT COUNT(*) FROM tb_config "
                "WHERE chave='migracao_versao_intranet_260930_validador_senha'")
    if (cur.fetchone()[0] or 0) == 0:
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES "
                    "('versao_modulo:intranet', '1.0.260930') "
                    "ON CONFLICT DO NOTHING")
        cur.execute("UPDATE tb_config SET valor='1.0.260930' "
                    "WHERE chave='versao_modulo:intranet'")
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES "
                    "('migracao_versao_intranet_260930_validador_senha', '1') "
                    "ON CONFLICT DO NOTHING")

    # Bump do `intranet` em 30/09/2026, marcador próprio. Mesmo dia, outra
    # alteração: o diálogo de troca obrigatória ganhou título e boas-vindas no
    # TOPO, e a cor do botão passou a seguir o estilo escolhido pela pessoa.
    # `Dialogo` ganhou `sem_separador` e `dialogo_formulario` ganhou o mesmo
    # parâmetro, para o título nascer no cabeçalho do cartão em vez de depois
    # da coluna rolável; e o seletor de `--q-primary` passou a cobrir o portal
    # do modal (`.q-dialog`), que vive fora do `.q-layout`.
    cur.execute("SELECT COUNT(*) FROM tb_config "
                "WHERE chave='migracao_versao_intranet_260930_dialogo_topo'")
    if (cur.fetchone()[0] or 0) == 0:
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES "
                    "('versao_modulo:intranet', '1.0.260930') "
                    "ON CONFLICT DO NOTHING")
        cur.execute("UPDATE tb_config SET valor='1.0.260930' "
                    "WHERE chave='versao_modulo:intranet'")
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES "
                    "('migracao_versao_intranet_260930_dialogo_topo', '1') "
                    "ON CONFLICT DO NOTHING")

    # Bump do `intranet` em 30/09/2026, marcador próprio. Mesmo dia, terceira
    # alteração. A troca obrigatória PAROU de ser decorativa: o diálogo era um
    # modal sobre a página já montada (`_montar_layout` rodava antes, e
    # `pagina_restrita` devolvia o usuário, então o chamador desenhava a tela
    # inteira), e `persistent` só impedia fechar o modal — não impedia navegar.
    # Quem não quisesse trocar a senha clicava em "voltar" e navegava. Agora o
    # guard fica no servidor: enquanto houver pendência, a página não é montada
    # e a pessoa vai para a tela solta `/troca-obrigatoria`, sem menu. E essa
    # tela ganhou "Sair", que encerra a sessão de verdade para o caso de
    # máquina compartilhada.
    cur.execute("SELECT COUNT(*) FROM tb_config "
                "WHERE chave='migracao_versao_intranet_260930_troca_bloqueada'")
    if (cur.fetchone()[0] or 0) == 0:
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES "
                    "('versao_modulo:intranet', '1.0.260930') "
                    "ON CONFLICT DO NOTHING")
        cur.execute("UPDATE tb_config SET valor='1.0.260930' "
                    "WHERE chave='versao_modulo:intranet'")
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES "
                    "('migracao_versao_intranet_260930_troca_bloqueada', '1') "
                    "ON CONFLICT DO NOTHING")

    # Bump do `intranet` em 30/09/2026, marcador próprio. Mesmo dia, sexta
    # alteração. MEDIDOR DE DIFICULDADE na troca de senha + ACEITE DE RISCO
    # (checkbox e confirmação dupla com o texto da LGPD) + TENTATIVAS DE LOGIN
    # por atraso progressivo, sem bloquear a conta.
    cur.execute("SELECT COUNT(*) FROM tb_config "
                "WHERE chave='migracao_versao_intranet_260930_politica_senha'")
    if (cur.fetchone()[0] or 0) == 0:
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES "
                    "('versao_modulo:intranet', '1.0.260930') "
                    "ON CONFLICT DO NOTHING")
        cur.execute("UPDATE tb_config SET valor='1.0.260930' "
                    "WHERE chave='versao_modulo:intranet'")
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES "
                    "('migracao_versao_intranet_260930_politica_senha', '1') "
                    "ON CONFLICT DO NOTHING")

    # Bump do `intranet` em 30/09/2026, marcador próprio. Mesmo dia, quinta
    # alteração: A COR DE TODOS OS BOTÕES passou a ser a mesma para todos: a
    # pessoa escolhe o estilo e ele vale em toda a tela. A causa era o botão
    # padronizado escrever `background-color` INLINE com a cor do módulo —
    # e estilo inline vence CSS, então nenhuma custom property chegava nele.
    # Agora `preview_estilos.aplicar_no_botao` escreve a cor do estilo escolhido
    # por último, depois do `.style()` da fábrica.
    cur.execute("SELECT COUNT(*) FROM tb_config "
                "WHERE chave='migracao_versao_intranet_260930_cor_unica_botao'")
    if (cur.fetchone()[0] or 0) == 0:
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES "
                    "('versao_modulo:intranet', '1.0.260930') "
                    "ON CONFLICT DO NOTHING")
        cur.execute("UPDATE tb_config SET valor='1.0.260930' "
                    "WHERE chave='versao_modulo:intranet'")
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES "
                    "('migracao_versao_intranet_260930_cor_unica_botao', '1') "
                    "ON CONFLICT DO NOTHING")

    # Bump do `usuarios` em 30/09/2026, marcador próprio. O código deste módulo
    # mudou no mesmo dia, pela MESMA alteração que o do `intranet`: tirou da
    # tela as 13 cores de MARCA chumbadas das chamadas de botão (`teal-8`,
    # `green-8`, `orange-9`, `primary`, `indigo-8`, `red-8`, `amber-8`,
    # `deep-purple-8`) e deixou a cor do estilo escolhido chegar em todo botão.
    # As cores de ESTADO (`negative`, `warning`, `grey-*`) ficaram: o vermelho
    # de "excluir" é vermelho em qualquer estilo.
    cur.execute("SELECT COUNT(*) FROM tb_config "
                "WHERE chave='migracao_versao_usuarios_260930_cor_botao'")
    if (cur.fetchone()[0] or 0) == 0:
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES "
                    "('versao_modulo:usuarios', '1.0.260930') "
                    "ON CONFLICT DO NOTHING")
        cur.execute("UPDATE tb_config SET valor='1.0.260930' "
                    "WHERE chave='versao_modulo:usuarios'")
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES "
                    "('migracao_versao_usuarios_260930_cor_botao', '1') "
                    "ON CONFLICT DO NOTHING")

    # Bump do `empenhos` em 30/09/2026, marcador próprio. Mesmo motivo, mudou
    # uma chamada só: "Cancelar ZIP" estava com `cor="orange-9"` — laranja de
    # marca, para uma ação que não é estado nem alerta.
    cur.execute("SELECT COUNT(*) FROM tb_config "
                "WHERE chave='migracao_versao_empenhos_260930_cor_botao'")
    if (cur.fetchone()[0] or 0) == 0:
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES "
                    "('versao_modulo:empenhos', '1.0.260930') "
                    "ON CONFLICT DO NOTHING")
        cur.execute("UPDATE tb_config SET valor='1.0.260930' "
                    "WHERE chave='versao_modulo:empenhos'")
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES "
                    "('migracao_versao_empenhos_260930_cor_botao', '1') "
                    "ON CONFLICT DO NOTHING")

    # Bump do `solicita_impressao` em 30/09/2026, marcador próprio. Mesmo
    # motivo, 4 chamadas: "Reenviar", "Autorizar" (em duas telas) e
    # "Confirmar impressão", com `cor="primary"`/`cor="green-8"`. Este módulo
    # é a exceção da §4.2 — a versão dele mora na PRÓPRIA
    # `tb_configuracoes_modulo`; a migração de hoje escreve a central, que é a
    # que o rodapé lê, e a exceção segue de pé para quem mexer nele.
    cur.execute("SELECT COUNT(*) FROM tb_config "
                "WHERE chave='migracao_versao_solicita_impressao_260930_cor_botao'")
    if (cur.fetchone()[0] or 0) == 0:
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES "
                    "('versao_modulo:solicita_impressao', '1.0.260930') "
                    "ON CONFLICT DO NOTHING")
        cur.execute("UPDATE tb_config SET valor='1.0.260930' "
                    "WHERE chave='versao_modulo:solicita_impressao'")
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES "
                    "('migracao_versao_solicita_impressao_260930_cor_botao', '1') "
                    "ON CONFLICT DO NOTHING")

    # Bump do `intranet` em 30/09/2026, marcador próprio. Mesmo dia, quarta
    # alteração. Saiu da tela a referência interna que tinha vazado para o
    # usuário: o rótulo de veredito dizia "Conta de teste do AGENTS.md 8.2",
    # que é jargão de quem escreve o código, lido por servidor no balcão. A
    # isomorphicidade com a camada de bloqueio fica no código e em
    # `docs/modulos/intranet.md`; na tela, nada. E a situação da consulta
    # (`sem_internet`, `limite_requisicoes`) passou a ser traduzida por
    # `_SITUACAO_PT_BR` em vez de expor o identificador cru.
    cur.execute("SELECT COUNT(*) FROM tb_config "
                "WHERE chave='migracao_versao_intranet_260930_texto_pela_tela'")
    if (cur.fetchone()[0] or 0) == 0:
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES "
                    "('versao_modulo:intranet', '1.0.260930') "
                    "ON CONFLICT DO NOTHING")
        cur.execute("UPDATE tb_config SET valor='1.0.260930' "
                    "WHERE chave='versao_modulo:intranet'")
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES "
                    "('migracao_versao_intranet_260930_texto_pela_tela', '1') "
                    "ON CONFLICT DO NOTHING")

    cur.execute("SELECT COUNT(*) FROM tb_config "
                "WHERE chave='migracao_versao_usuarios_260929'")
    if (cur.fetchone()[0] or 0) == 0:
        cur.execute("INSERT INTO tb_config (chave, valor) "
                    "VALUES ('versao_modulo:usuarios', '1.0.260929') "
                    "ON CONFLICT DO NOTHING")
        cur.execute("UPDATE tb_config SET valor='1.0.260929' "
                    "WHERE chave='versao_modulo:usuarios'")
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES "
                    "('migracao_versao_usuarios_260929', '1') ON CONFLICT DO NOTHING")

    cur.execute("SELECT COUNT(*) FROM tb_config "
                "WHERE chave='migracao_versao_estoque_260929'")
    if (cur.fetchone()[0] or 0) == 0:
        cur.execute("INSERT INTO tb_config (chave, valor) "
                    "VALUES ('versao_modulo:estoque', '1.0.260929') "
                    "ON CONFLICT DO NOTHING")
        cur.execute("UPDATE tb_config SET valor='1.0.260929' "
                    "WHERE chave='versao_modulo:estoque'")
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES "
                    "('migracao_versao_estoque_260929', '1') ON CONFLICT DO NOTHING")

    cur.execute("SELECT COUNT(*) FROM tb_config "
                "WHERE chave='migracao_versao_lista_telefonica_260929'")
    if (cur.fetchone()[0] or 0) == 0:
        cur.execute("INSERT INTO tb_config (chave, valor) "
                    "VALUES ('versao_modulo:lista_telefonica', '1.0.260929') "
                    "ON CONFLICT DO NOTHING")
        cur.execute("UPDATE tb_config SET valor='1.0.260929' "
                    "WHERE chave='versao_modulo:lista_telefonica'")
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES "
                    "('migracao_versao_lista_telefonica_260929', '1') "
                    "ON CONFLICT DO NOTHING")

    cur.execute("SELECT COUNT(*) FROM tb_config "
                "WHERE chave='migracao_versao_tecnico_260929'")
    if (cur.fetchone()[0] or 0) == 0:
        cur.execute("INSERT INTO tb_config (chave, valor) "
                    "VALUES ('versao_modulo:tecnico', '1.0.260929') "
                    "ON CONFLICT DO NOTHING")
        cur.execute("UPDATE tb_config SET valor='1.0.260929' "
                    "WHERE chave='versao_modulo:tecnico'")
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES "
                    "('migracao_versao_tecnico_260929', '1') ON CONFLICT DO NOTHING")
    # A versão do SISTEMA também anda quando o núcleo muda: o aviso de
    # primeiro boot e a própria base de diálogos ficam em `mod_intranet`.
    cur.execute("SELECT COUNT(*) FROM tb_config "
                "WHERE chave='migracao_versao_sistema_260929'")
    if (cur.fetchone()[0] or 0) == 0:
        cur.execute("INSERT INTO tb_config (chave, valor) "
                    "VALUES ('versao_sistema', '1.0.260929') ON CONFLICT DO NOTHING")
        cur.execute("UPDATE tb_config SET valor='1.0.260929' "
                    "WHERE chave='versao_sistema'")
        cur.execute("INSERT INTO tb_config (chave, valor) "
                    "VALUES ('migracao_versao_sistema_260929', '1') ON CONFLICT DO NOTHING")
    # Migração ÚNICA (27/09/2026) — TEMA WHATSAPP como padrão do SISTEMA INTEIRO,
    # escolhido pelo responsável. Antes os 11 módulos usavam preto (#000000).
    # O que ela grava:
    #   cor_principal -> teal da marca (#075E54): é o que `_montar_layout` joga
    #     em `ui.colors(primary=)`, e portanto a cor do cabeçalho e de TODOS os
    #     elementos `bg-primary` de qualquer módulo.
    #   cor_fundo -> bege quente (#EAE6DF), o papel de parede do app.
    #   <prefixo>_cor_botao e <prefixo>_cor_titulo -> VAZIO, de propósito: é o
    #     que faz cada módulo cair no `PADROES_TEMA` (verde teal do botão e
    #     ardósia do título). Zerar em vez de gravar o valor é o que mantém
    #     esta aplicação em UM lugar só — trocar a paleta depois é editar o
    #     `PADROES_TEMA`, sem nova migração.
    #   <prefixo>_cor_fundo_card -> branco (#FFFFFF), o cartão sobre o fundo.
    # Guardada pelo marcador, então roda UMA vez e não apaga personalização
    # posterior do admin. SQL portátil: o proxy `_CursorPostgres` traduz.
    cur.execute("SELECT COUNT(*) FROM tb_config WHERE chave='migracao_tema_whatsapp_260927'")
    if (cur.fetchone()[0] or 0) == 0:
        for _chave, _valor in (("cor_principal", "#075E54"),
                               ("cor_fundo", "#EAE6DF"),
                               # Padrão de estilo do ADMINISTRADOR: o que vale
                               # para quem não fez escolha pessoal no navegador
                               # (cookie `estilo_visual` vazio ou `padrao`).
                               ("estilo_visual_padrao_sistema", "verde")):
            cur.execute("INSERT INTO tb_config (chave, valor) VALUES (?, ?) "
                        "ON CONFLICT DO NOTHING", (_chave, _valor))
            cur.execute("UPDATE tb_config SET valor=? WHERE chave=?",
                        (_valor, _chave))
        for _p in ("intranet", "blog", "usuarios", "auditoria", "editpdf",
                   "empenhos", "solicita_impressao", "tecnico", "filas",
                   "lista_telefonica", "agregador_noticias"):
            for _campo in ("cor_botao", "cor_titulo", "cor_texto_card",
                           "texto_header", "cor_fundo"):
                cur.execute("INSERT INTO tb_config (chave, valor) VALUES (?, '') "
                            "ON CONFLICT DO NOTHING", (f"{_p}_{_campo}",))
                cur.execute("UPDATE tb_config SET valor='' WHERE chave=?",
                            (f"{_p}_{_campo}",))
            for _campo in ("cor_fundo_card", "cor_texto_botao"):
                cur.execute("INSERT INTO tb_config (chave, valor) VALUES (?, '#FFFFFF') "
                            "ON CONFLICT DO NOTHING", (f"{_p}_{_campo}",))
                cur.execute("UPDATE tb_config SET valor='#FFFFFF' WHERE chave=?",
                            (f"{_p}_{_campo}",))
        cur.execute("INSERT INTO tb_config (chave, valor) "
                    "VALUES ('migracao_tema_whatsapp_260927', '1') ON CONFLICT DO NOTHING")
    # Migração ÚNICA (27/09/2026, 2ª rodada) — o menu de estilo visual entrou e
    # com ele a decisão de que o "Padrão" NÃO é uma cor do sistema, e sim a cor
    # que cada ADMINISTRADOR configurou para o seu módulo. Esta migração
    # desfaz o que a de cima fez:
    #   cor_principal/cor_fundo voltam ao preto/cinza de antes;
    #   as chaves por módulo continuam vazias, cair no PADROES_TEMA (preto);
    #   estilo_visual_padrao_sistema é SEMEADA com 'padrao' — a de cima tentou
    #   semear, mas o marcador já estava gravado quando ela rodou, então a
    #   linha nunca existiu e a chave ficava ausente para sempre.
    # O estilo "verde" (WhatsApp) continua existindo, agora como OPÇÃO do menu.
    cur.execute("SELECT COUNT(*) FROM tb_config WHERE chave='migracao_padrao_por_modulo_260927'")
    if (cur.fetchone()[0] or 0) == 0:
        for _chave, _valor in (("cor_principal", "#000000"),
                               ("cor_fundo", "#EEEEEE"),
                               ("estilo_visual_padrao_sistema", "padrao")):
            cur.execute("INSERT INTO tb_config (chave, valor) VALUES (?, ?) "
                        "ON CONFLICT DO NOTHING", (_chave, _valor))
            cur.execute("UPDATE tb_config SET valor=? WHERE chave=?",
                        (_valor, _chave))
        for _p in ("intranet", "blog", "usuarios", "auditoria", "editpdf",
                   "empenhos", "solicita_impressao", "tecnico", "filas",
                   "lista_telefonica", "agregador_noticias"):
            for _campo in ("cor_botao", "cor_titulo"):
                cur.execute("INSERT INTO tb_config (chave, valor) VALUES (?, '') "
                            "ON CONFLICT DO NOTHING", (f"{_p}_{_campo}",))
                cur.execute("UPDATE tb_config SET valor='' WHERE chave=?",
                            (f"{_p}_{_campo}",))
        cur.execute("INSERT INTO tb_config (chave, valor) "
                    "VALUES ('migracao_padrao_por_modulo_260927', '1') ON CONFLICT DO NOTHING")
    # Seed do contador de acessos (se ainda não existir) + data inicial da contagem
    try:
        cur.execute("SELECT valor FROM tb_config WHERE chave='contador_acessos_inicio'")
        row = cur.fetchone()
        if not row or not (row[0] or "").strip():
            import datetime as _dt
            hoje = _dt.datetime.now().strftime("%Y-%m-%d")
            cur.execute("INSERT INTO tb_config (chave, valor) VALUES ('contador_acessos_inicio', ?) ON CONFLICT DO NOTHING", (hoje,))
            cur.execute("UPDATE tb_config SET valor=? WHERE chave='contador_acessos_inicio' AND (valor IS NULL OR valor='')", (hoje,))
        cur.execute("INSERT INTO tb_config (chave, valor) VALUES ('contador_acessos_total', '0') ON CONFLICT DO NOTHING")
    except Exception:
        pass
    conn.commit()
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()


def incrementar_contador_acessos() -> int:
    """Increments the global access counter — login-only, never navigation/refresh.

    EN: Centralized counter for **successful logins only** (not page navigations,
    refreshes or tab switches). Called exclusively in `main.tentar_login`
    after `autenticacao.registrar_login` validates credentials. Persists in
    `tb_config` (`contador_acessos_total` + `contador_acessos_inicio`) via
    `get_config`/`set_config` (which delegate to `Repositorio`/SQLAlchemy and
    then to `banco_conexao.conexao`). `main._orquestrar_resumo_dados` only
    reads (`get_config`). Previously incremented inline in `main`; now this
    function is the single source of truth. Fail-soft — returns `0` on error.
    Returns the new total.

    PT-BR: Incrementa o contador global de acessos — **apenas logins**, nunca
    navegações, refreshes ou trocas de aba. Chamado somente em
    `main.tentar_login` após `autenticacao.registrar_login` validar as
    credenciais. Persiste em `tb_config` (`contador_acessos_total` +
    `contador_acessos_inicio`) via `get_config`/`set_config` (que delegam ao
    `Repositorio`/SQLAlchemy e então a `banco_conexao.conexao`).
    `main._orquestrar_resumo_dados` apenas lê (`get_config`). Antes contava
    inline em `main`; agora esta função é a única fonte da verdade. Fail-soft
    — retorna `0` em erro. Retorna o novo total.
    """
    import datetime as _dt
    try:
        total = get_config("contador_acessos_total", "0") or "0"
        try:
            novo = int(str(total).strip() or 0) + 1
        except Exception:
            novo = 1
        set_config("contador_acessos_total", str(novo))
        inicio = (get_config("contador_acessos_inicio", "") or "").strip()
        if not inicio:
            set_config("contador_acessos_inicio", _dt.datetime.now().strftime("%Y-%m-%d"))
        return novo
    except Exception:
        return 0


def get_config(chave, default=""):
    """Leitura pontual de configuração via Repositorio (SQLAlchemy ORM).

    Camada mais baixa: sem imports circulares. Delega para `Repositorio.obter_config`.
    """
    try:
        from mod_intranet.repositorio import Repositorio
        with Repositorio() as repo:
            return repo.obter_config(chave, default)
    except Exception:
        pass
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT valor FROM tb_config WHERE chave=?", (chave,))
        row = cur.fetchone()
        return row[0] if row else default
    finally:
        conn.close()


def set_config(chave, valor):
    """Gravação de configuração via Repositorio (SQLAlchemy ORM).

    Delega para `Repositorio.definir_config`.
    """
    try:
        from mod_intranet.repositorio import Repositorio
        with Repositorio() as repo:
            ok = repo.definir_config(chave, valor)
            if ok:
                try:
                    favicon_versao.cache_clear()
                except Exception:
                    pass
                for _fn, _chaves in list(_HOOKS_CONFIG):
                    if _chaves is not None and chave not in _chaves:
                        continue
                    try:
                        _fn()
                    except Exception:
                        pass
            return ok
    except Exception:
        pass
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO tb_config (chave, valor) VALUES (?, ?) "
            "ON CONFLICT (chave) DO UPDATE SET valor = EXCLUDED.valor",
            (chave, str(valor)))
        conn.commit()
    finally:
        conn.close()


@lru_cache(maxsize=1)
def favicon_versao():
    """mtime do favicon atual — muda quando o .ico é trocado (cache-busting da aba)."""
    try:
        return int(os.path.getmtime(os.path.join(BASE_DIR, "assets", "favicon_atual.ico")))
    except OSError:
        return 0
