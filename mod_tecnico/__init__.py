"""EN: Technical module — tools and backup for PC maintenance (route /tecnico).

PT-BR: Módulo Técnico — ferramentas e backup para manutenção de PCs (rota /tecnico).
Fornece listagem de executáveis em `software/`, download multi-seleção via
checkbox (zip recursivo) e fluxo de backup com pasta nomeada
`YYYYMMDD_HHMM_nomePc_ip` em `mod_tecnico/backup/` (acesso restrito ao dono).
Técnico acessa do PC a formatar (browser local) com `webkitdirectory`."""
