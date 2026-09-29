"""EN: Stock — multi-unit inventory for the municipality (route /estoque).
A fixed central warehouse where everything enters, a decentralised warehouse per
secretariat of the organogram, and the control of what is AVAILABLE, what is IN
USE in a room, and what has been RETURNED instead of being wasted. Movements
(entry, transfer, devolution) always produce a numbered document; deliveries to
a room carry a destination and a date, so "in use" is a number and not a guess.
Own database only (db_mod_estoque.db); cross-module data (servers, organogram)
comes from `mod_intranet.integracoes`.

PT-BR: Estoque — controle de estoque multi-setorial para a prefeitura
(rota /estoque). Um estoque central fixo onde entra tudo, um almoxarifado
descentralizado por secretaria do organograma, e o controle do que está
DISPONÍVEL, do que está EM USO numa sala e do que VOLTOU em vez de se
perder. Toda movimentação (entrada, transferência, devolução) gera documento
numerado; a entrega para a sala tem destino e data, para "em uso" ser número
e não chute. Banco próprio (db_mod_estoque.db); o que vem de outro módulo
(servidores, organograma) entra por `mod_intranet.integracoes`.
"""
