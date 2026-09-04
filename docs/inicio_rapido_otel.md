# Guia Rápido - Grafana OTel LGTM

## O que é?

Stack completa de observabilidade para monitoramento da Intranet:

- **Grafana** → Dashboard visual (http://localhost:3000)
- **Loki** → Armazenamento de logs
- **Tempo** → Rastreamento de traces
- **Mimir** → Métricas (compatível com Prometheus)
- **OTel Collector** → Receptor central de telemetria

---

## Credenciais (master/master)

Todos os serviços usam as mesmas credenciais do usuário master da Intranet:

| Serviço | Usuário | Senha | URL |
|---------|---------|-------|-----|
| **Grafana** | master | master | http://localhost:3000 |
| Loki | (interno) | (interno) | http://localhost:3100 |
| Tempo | (interno) | (interno) | http://localhost:3200 |
| Mimir | (interno) | (interno) | http://localhost:9009 |

**NOTA:** Serviços internos (Loki, Tempo, Mimir) não requerem autenticação pois só são acessíveis pela rede Docker. O Grafana é o ponto de entrada único.

---

## Como Ativar?

### Opção 1: Automática (Recomendado)

Basta rodar o `main.py`. O sistema detecta o Docker automaticamente:

```bash
.venv/bin/python main.py
```

**Se o Docker estiver disponível:**
- A stack OTel é iniciada automaticamente
- Logs aparecem no terminal
- Grafana disponível em http://localhost:3000

**Se o Docker NÃO estiver disponível:**
- O sistema funciona normalmente
- Apenas aviso no terminal (sem erros)

### Opção 2: Manual

```bash
# Navegar até a pasta docker
cd docker

# Iniciar stack
./start.sh

# Ou usar docker compose
docker compose up -d
```

---

## Pré-requisitos

1. **Docker Desktop** ou **Docker Engine** instalado
2. **Docker Compose** disponível (já incluído no Docker Desktop v2+)

### Verificar se o Docker está disponível

```bash
docker --version
docker compose version
docker info
```

### Instalar Docker (se necessário)

- **Windows/Mac:** [Docker Desktop](https://docs.docker.com/desktop/)
- **Linux:** [Docker Engine](https://docs.docker.com/engine/install/)

---

## Acessar os Serviços

| Serviço | URL | Credenciais |
|---------|-----|-------------|
| **Grafana** | http://localhost:3000 | master / master |
| Loki | http://localhost:3100 | (interno) |
| Tempo | http://localhost:3200 | (interno) |
| Mimir | http://localhost:9009 | (interno) |

**Acesse o Grafana com:** master / master (mesmo usuário da Intranet)

---

## Comandos Úteis

```bash
# Ver status da stack
cd docker && ./start.sh status

# Ver logs em tempo real
cd docker && ./start.sh logs

# Parar stack
cd docker && ./start.sh stop

# Testar integração
cd docker && ./start.sh test
```

---

## Estrutura

```
intranet/
├── docker/
│   ├── compose.yml          # Configuração Docker
│   ├── start.sh             # Script de inicialização
│   ├── README.md            # Documentação completa
│   └── config/              # Configurações dos serviços
├── mod_intranet/
│   ├── docker_detector.py   # Detecção automática do Docker
│   └── otel_integracao.py   # Integração com OpenTelemetry
└── main.py                  # Ponto de entrada (auto-inicia OTel)
```

---

## Fluxo Automático

```
main.py inicia
    ↓
Verifica: Docker disponível?
    ↓
    ├── SIM → Inicia stack OTel (Grafana, Loki, Tempo, Mimir)
    │        ↓
    │        Configura OpenTelemetry SDK
    │        ↓
    │        Sistema envia logs/traces/métricas
    │
    └── NÃO → Sistema funciona normalmente
             (sem telemetria, sem erros)
```

---

## Solução de Problemas

| Problema | Solução |
|----------|---------|
| Docker não encontrado | Instale o Docker Desktop ou Engine |
| Docker não rodando | Inicie o Docker Desktop |
| Porta em uso | Verifique com `netstat -tulpn \| grep :3000` |
| Containers não iniciam | Veja logs: `docker compose logs` |
| Sem dados no Grafana | Verifique se a Intranet está rodando |

---

## Documentação Completa

Consulte o [README completo](docker/README.md) para mais detalhes.