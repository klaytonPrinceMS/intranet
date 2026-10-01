"""EN: Open data module — public datasets published by the municipality.

PT-BR: Módulo de Dados Abertos — datasets públicos publicados pela prefeitura.

Tela principal em `/dados-abertos`: uma grade de CARDS, um por conjunto de
dados público. Hoje existe **um** card — "Servidores Públicos" — que lê o
arquivo de origem da folha (Portal da Transparência) pela costura pública
`mod_intranet.integracoes.folha_de_servidores_publica()`.

A grade é dirigida por REGISTRO (`tb_fontes` no banco do próprio módulo), não
por uma lista escrita na tela: os próximos conjuntos de dados entram por
`/admin/dados_abertos` ou por `init_db`, sem que a tela principal mude.

NÃO entra em `ACESSO_PADRAO_NOVO_USUARIO` (decisão de 01/10/2026): dado ser
público por lei não significa que a intranet o exponha a todo mundo sem
decisão do administrador. O módulo nasce desligado para o perfil comum e quem
libera é o administrador, por módulo.
"""