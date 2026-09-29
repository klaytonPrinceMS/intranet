"""Fachada de integração entre módulos — API pública do núcleo.

EN: Facade for cross-module integration — the single public seam that lets a
    business module reach another module WITHOUT importing it directly.
    Keeps the DAS rule of AGENTS.md §2 ("never cross-query between databases"):
    a module talks to `mod_intranet`, and the core owns the coupling. Every
    function is fail-soft: if the target module is absent, disabled or raises,
    it returns a neutral value and logs — it NEVER breaks the caller's screen.

PT-BR: Fachada de integração entre módulos — costura pública única para um
    módulo de negócio alcançar outro SEM importá-lo diretamente. Preserva a
    regra do AGENTS.md §2 ("nunca faça cross-query entre bancos"): o módulo
    fala com o `mod_intranet`, e o núcleo possui o acoplamento. Toda função é
    fail-soft: se o módulo de destino estiver ausente, desabilitado ou lançar
    exceção, devolve valor neutro e registra no log — NUNCA quebra a tela.

Usage:
    from mod_intranet import integracoes
    integracoes.listar_usuarios_gestao(filtro_ativo=True)

Imports are LAZY (inside the functions) on purpose: a top-level import of a
business module here would close a top-level import cycle with `main.py`.
"""
import logging

logger = logging.getLogger(__name__)


# ================== Gestão de usuários (mod_gest_cad_usuario) ==================


def obter_usuario_gestao(user_nome: str):
    """EN: One user row from the user registry, or None.

    PT-BR: Uma linha da cadastro de usuários pelo nome, ou None. Usado por
    Filas e Lista Telefônica sem que eles conheçam o módulo de gestão."""
    try:
        nome = (user_nome or "").strip()
        if not nome:
            return None
        from mod_gest_cad_usuario.bd_manipulador import obter_usuario
        return obter_usuario(nome)
    except Exception as exc:
        logger.warning("integracoes.obter_usuario_gestao('%s'): falha (%s) — devolvendo None",
                       user_nome, exc)
        return None


def listar_usuarios_gestao(filtro_ativo=None) -> list:
    """EN: User rows from the registry (per-module access aggregated).

    PT-BR: Linhas do cadastro de usuários (acesso por módulo agregado). Lista
    vazia em qualquer falha — a tela que chama decide o que fazer."""
    try:
        from mod_gest_cad_usuario.bd_manipulador import listar_usuarios
        return list(listar_usuarios(filtro_ativo=filtro_ativo) or [])
    except Exception as exc:
        logger.warning("integracoes.listar_usuarios_gestao(filtro_ativo=%s): falha (%s) — devolvendo []",
                       filtro_ativo, exc)
        return []


# ================== Agregador de notícias (mod_agregador_noticias) ==================


def agregador_habilitado() -> bool:
    """EN: Whether the news aggregator is switched on in its own config.

    PT-BR: Se o agregador de notícias está ligado na configuração do módulo.
    Falso quando o módulo não responde — a TV Filas cai no aviso de pausa."""
    try:
        from mod_agregador_noticias.bd_manipulador import habilitado
        return bool(habilitado())
    except Exception as exc:
        logger.warning("integracoes.agregador_habilitado: falha (%s) — devolvendo False", exc)
        return False


def listar_noticias_para_tv(limite: int = 200) -> list:
    """EN: Up to `limite` recent headlines for the Filas TV carousel (censorship filtered).

    PT-BR: Até `limite` manchetes recentes para o carrossel da TV Filas
    (censura já filtrada na origem). Lista vazia em qualquer falha."""
    try:
        from mod_agregador_noticias.bd_manipulador import listar_para_tv
        return list(listar_para_tv(limite=limite) or [])
    except Exception as exc:
        logger.warning("integracoes.listar_noticias_para_tv(limite=%s): falha (%s) — devolvendo []",
                       limite, exc)
        return []


def limpar_noticias_censuradas() -> int:
    """EN: Drop already-collected headlines whose title is censored; returns how many.

    PT-BR: Remove as notícias já coletadas cujo título está censurado e devolve
    quantas saíram. Usado pelo admin do Blog ao salvar a lista de censura —
    quem orquestra é o núcleo, não o Blog conhecendo o Agregador."""
    try:
        from mod_agregador_noticias.bd_manipulador import limpar_censuradas
        return int(limpar_censuradas() or 0)
    except Exception as exc:
        logger.warning("integracoes.limpar_noticias_censuradas: falha (%s) — devolvendo 0", exc)
        return 0


# ================== Lista telefônica (mod_lista_telefonica) ==================


def obter_organograma_base():
    """EN: The shared organogram seed (secretaria -> sector -> subsector).

    PT-BR: A semente do organograma compartilhado (secretaria → setor → subsetor),
    fonte única das cotas por área. Devolve `None` quando o módulo não responde,
    para o chamador manter o seu próprio fallback local."""
    try:
        from mod_lista_telefonica.bd_manipulador import ORGANOGRAMA_BASE
        return ORGANOGRAMA_BASE
    except Exception as exc:
        logger.warning("integracoes.obter_organograma_base: falha (%s) — devolvendo None", exc)
        return None


def espelhar_cadastro_na_lista_telefonica(ator="sistema") -> dict:
    """EN: Mirror registered servers into the phone directory.

    PT-BR: Espelha no diretório telefônico os servidores cadastrados.

    ESTA FUNÇÃO É A COSTURA
        O cadastro de usuários é dono de nome, matrícula, secretaria, cargo e
        do telefone que a pessoa autorizou; a lista telefônica é dona dos
        contatos. Nenhum dos dois pode abrir o banco do outro. Então quem
        busca é o módulo do cadastro (que só publica o que é público e
        autorizado), quem grava é o da lista (que só escreve no banco dele),
        e a ligação entre os dois acontece AQUI, no núcleo — o único lugar do
        sistema autorizado a conhecer os dois de perto.

    Devolve o resumo `{criados, atualizados, sem_unidade, sem_telefone,
    ja_iguais}`. Em qualquer falha, devolve o mesmo formato com `erro=True` e
    zeros — a tela que chama decide o que fazer, e uma falha aqui nunca pode
    derrubar a lista.
    """
    vazio = {"criados": 0, "atualizados": 0, "sem_unidade": 0,
             "sem_telefone": 0, "ja_iguais": 0}
    try:
        from mod_gest_cad_usuario import leitura_lista
        servidores = leitura_lista.listar_para_lista_telefonica()
        from mod_lista_telefonica.bd_manipulador import sincronizar_contatos_do_cadastro
        return sincronizar_contatos_do_cadastro(servidores, ator=ator)
    except Exception as exc:
        logger.warning("integracoes.espelhar_cadastro_na_lista_telefonica: "
                       "falha (%s)", exc)
        return {**vazio, "erro": True}


def telefones_de_recado_para_lista() -> dict:
    """EN: `{user_nome: True}` — who answers on the SECTOR's line (message phone).

    PT-BR: Quem atende no telefone do SETOR (deixa recado).

    Existe pela mesma razão de `espelhar_cadastro_na_lista_telefonica`: a lista
    telefônica precisa saber, para cada cartão, se o número é da pessoa ou do
    setor — e não pode abrir o banco do cadastro. A costura é aqui.

    A chave é a **matrícula** (`user_nome`), que é o que o contato vinculado
    guarda — por isso o cartão resolve o "deixe recado" sem tocar em banco
    nenhum durante o desenho."""
    try:
        from mod_gest_cad_usuario import leitura_lista
        return {u["user_nome"]: True
                for u in leitura_lista.listar_para_lista_telefonica()
                if u.get("recado")}
    except Exception as exc:
        logger.warning("integracoes.telefones_de_recado_para_lista: falha (%s)",
                       exc)
        return {}


# ================== Módulos do sistema ==================


def modulo_habilitado(chave: str) -> bool:
    """EN: Whether a business module is switched on (`tb_modulos.ativo`).

    PT-BR: Se um módulo de negócio está ligado (`tb_modulos.ativo`).
    Módulo desconhecido conta como desligado."""
    try:
        from mod_intranet.autenticacao import modulos_registrados
        alvo = (chave or "").strip()
        if not alvo:
            return False
        for linha in modulos_registrados() or []:
            # linha = (chave, nome, icone, rota, ativo)
            if len(linha) >= 5 and linha[0] == alvo:
                return bool(linha[4])
        return False
    except Exception as exc:
        logger.warning("integracoes.modulo_habilitado('%s'): falha (%s) — devolvendo False",
                       chave, exc)
        return False


def registrar_auditoria(usuario, modulo, acao, descricao):
    """EN: Writes one audit row on behalf of a business module (fail-soft).

    PT-BR: Grava UM registro de auditoria em nome de um módulo de negócio
    (fail-soft). Existe para que o módulo de negócio NUNCA importe
    `mod_intranet.bd_manipulador`: quem possui o acoplamento é o núcleo, e
    a função devolve `True`/`False` em vez de propagar a exceção — uma
    auditoria que falhou não pode derrubar a tela do servidor."""
    try:
        from mod_intranet.bd_manipulador import audit_log
        audit_log(usuario or "sistema", modulo, acao, descricao)
        return True
    except Exception as exc:
        logger.warning("integracoes.registrar_auditoria('%s', '%s'): "
                       "falha (%s) — devolvendo False", modulo, acao, exc)
        return False


def buscar_usuarios_gestao(termo="", limite=50):
    """EN: Active users matching `termo` — dicts with display name and unit.

    PT-BR: Usuários ATIVOS que casam com o termo — dicionários com nome de
    exibição (primeiro + último), cargo, unidade e lotação. Serve para o
    seletor de quem participa de um quadro/convite: a tela mostra o nome que
    a pessoa deve ler e a unidade dela, nunca a matrícula crua sozinha. Lista
    vazia em qualquer falha — o seletor fica vazio, a tela não quebra."""
    try:
        from mod_gest_cad_usuario import leitura_lista
        return list(leitura_lista.buscar_usuarios_para_lista(termo=termo,
                                                             limite=limite) or [])
    except Exception as exc:
        logger.warning("integracoes.buscar_usuarios_gestao(termo=%r): "
                       "falha (%s) — devolvendo []", termo, exc)
        return []


def conceder_acesso_gestao(ator, user_nome, modulo_chave, papel="comum"):
    """EN: Grants/revokes a user's per-module role in the user registry.

    PT-BR: Concede (ou remove) o papel do usuário num módulo, no cadastro de
    usuários. `papel=None` remove o vínculo. O módulo de negócio só pede —
    quem escreve em `tb_acesso_usuario` é o módulo dono do cadastro.
    Devolve (ok, mensagem); em falha, o mesmo formato com erro."""
    try:
        from mod_gest_cad_usuario.bd_manipulador import definir_acesso
        return definir_acesso(ator, user_nome, modulo_chave, papel)
    except Exception as exc:
        logger.warning("integracoes.conceder_acesso_gestao(%r, %r): "
                       "falha (%s)", user_nome, modulo_chave, exc)
        return (False, "Erro ao alterar o acesso do servidor")


def obter_papel_gestao(user_nome, modulo_chave):
    """EN: The user's effective role in a module, or None.

    PT-BR: Papel efetivo do usuário no módulo, ou None quando não tem
    vínculo. None também quando o cadastro não responde (fail-soft)."""
    try:
        from mod_gest_cad_usuario.bd_manipulador import obter_papel_no_modulo
        return obter_papel_no_modulo(user_nome, modulo_chave)
    except Exception as exc:
        logger.warning("integracoes.obter_papel_gestao(%r, %r): falha (%s)",
                       user_nome, modulo_chave, exc)
        return None


# ================== Unidades do organograma (mod_lista_telefonica) ==================


def sincronizar_organograma_cadastro(plano, aplicar=True, ator="sistema"):
    """EN: Writes the organogram coming from the payroll sheet into the phone
    directory. The core is the one that stitches, per AGENTS.md §2.

    PT-BR: Grava no organograma da lista telefônica o plano que a folha de
    servidores trouxe. `plano` é uma lista flat de
    `(nome, tipo, nome_do_pai_ou_None, ordem)`, de raiz para a folha.

    Existe porque o módulo de cadastro de usuários tem a FOLHA e o módulo da
    lista telefônica tem o BANCO, e nenhum dos dois pode falar direto com o
    outro. Quem tem o banco expõe a escrita (`sincronizar_organograma`); quem
    tem a folha monta o plano; o núcleo costura. Nenhum dado de servidor
    atravessa direto — só o organograma, que é estrutura, não cadastro.
    """
    vazio = {"secretarias_criadas": 0, "setores_criados": 0,
             "reativadas": 0, "desativadas": 0, "erros": []}
    try:
        from mod_lista_telefonica.bd_manipulador import sincronizar_organograma
        return sincronizar_organograma(plano, aplicar=aplicar, ator=ator)
    except Exception as exc:
        logger.warning("integracoes.sincronizar_organograma_cadastro: falha (%s) "
                       "— organograma nao alterado", exc)
        return {**vazio, "erros": [str(exc)]}


def listar_unidades_organograma(tipo=None, ativo=1):
    """EN: Organogram units of the phone directory as dicts (id, name, kind...).

    PT-BR: Unidades do organograma da lista telefônica como dicionários
    (`id`, `nome`, `tipo`, `parent_id`, `ordem`, `telefone`, `ativo`).
    É o seletor de unidade do quadro de ordens de serviço: cada secretaria,
    setor ou subsetor pode ter o seu. Lista vazia em qualquer falha — o
    quadro particular continua disponível."""
    try:
        from mod_lista_telefonica.bd_manipulador import listar_todas_unidades
        saida = []
        for linha in listar_todas_unidades() or []:
            if not linha or len(linha) < 7:
                continue
            if tipo and linha[2] != tipo:
                continue
            if ativo is not None and not linha[6]:
                continue
            saida.append({"id": linha[0], "nome": linha[1], "tipo": linha[2],
                          "parent_id": linha[3], "ordem": linha[4],
                          "telefone": linha[5], "ativo": linha[6]})
        return saida
    except Exception as exc:
        logger.warning("integracoes.listar_unidades_organograma(tipo=%r): "
                       "falha (%s) — devolvendo []", tipo, exc)
        return []


def _norm_unidade(texto):
    """Compara nomes de unidade sem acento e sem pontuação (NFKD + [a-z0-9])."""
    try:
        import re
        import unicodedata
        limpo = unicodedata.normalize("NFKD", str(texto or "")) \
            .encode("ascii", "ignore").decode().lower()
        return " ".join(re.findall(r"[a-z0-9]+", limpo))
    except Exception:
        return str(texto or "").lower()


def unidades_por_usuario_gestao():
    """EN: `{matricula: {nome_exibicao, unidade, lotacao, cargo}}` for the organogram.

    PT-BR: `{matricula: {nome_exibicao, unidade, lotacao, cargo}}` — quem é o
    servidor e de qual setor ele é, para o quadro da unidade saber a quem se
    mostrar.

    O nome da unidade guardado é o do CADASTRO do servidor (lotação, com a
    unidade como reserva); casar isso com as unidades do organograma é tarefa
    do módulo que DETÉM o organograma, não deste. Por isso o campo `unidade`
    sai com o valor do cadastro e quem compara é o chamador, com a normalização
    que ele quiser. Dicionário vazio em qualquer falha."""
    try:
        from mod_gest_cad_usuario import leitura_lista
        saida = {}
        for servidor in leitura_lista.listar_para_lista_telefonica() or []:
            matricula = servidor.get("user_nome")
            if not matricula:
                continue
            saida[matricula] = {
                "nome_exibicao": servidor.get("nome_exibicao") or matricula,
                "unidade": servidor.get("unidade") or "",
                "lotacao": servidor.get("lotacao") or "",
                "cargo": servidor.get("cargo") or "",
            }
        return saida
    except Exception as exc:
        logger.warning("integracoes.unidades_por_usuario_gestao: "
                       "falha (%s) — devolvendo {}", exc)
        return {}


def unidades_do_organograma_por_nome():
    """EN: `{nome normalizado: {id, nome, tipo}}` of the ACTIVE units.

    PT-BR: `{nome normalizado: {id, nome, tipo}}` das unidades ATIVAS do
    organograma, com o nome já normalizado (sem acento, sem pontuação).

    É a peça que fecha o casamento: o cadastro do servidor traz `lotacao`/
    `unidade` como TEXTO, e o organograma tem a unidade com id. Casa-se por
    nome normalizado — a lotação tem precedência, porque é o setor onde a
    pessoa trabalha de fato. Dicionário vazio em qualquer falha."""
    try:
        consulta = {}
        for unidade in listar_unidades_organograma(ativo=1):
            chave = _norm_unidade(unidade.get("nome"))
            if chave and chave not in consulta:
                consulta[chave] = {"id": unidade.get("id"),
                                   "nome": unidade.get("nome"),
                                   "tipo": unidade.get("tipo")}
        return consulta
    except Exception as exc:
        logger.warning("integracoes.unidades_do_organograma_por_nome: "
                       "falha (%s) — devolvendo {}", exc)
        return {}
