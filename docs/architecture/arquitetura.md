# Arquitetura — ACS Primeira Infância v3.0

## 1. Visão geral

Sistema monolítico Python que combina três responsabilidades em um único processo:

- **API/Webhook** (FastAPI) — recebe webhooks do Telegram e endpoints de observabilidade
- **Scheduler** (APScheduler em-process) — roda os 2 batches diários (05h, 22h)
- **Workers de processamento** — motor de priorização, integração Claude, FSM da conversa

Para MVP de hackathon, o monolito é deliberado: um único `docker compose up` sobe tudo. Para produção, a estrutura permite quebrar em serviços (API, worker, scheduler) sem reescrita — só reorganização do entrypoint.

## 2. Diagrama de componentes

```
┌─────────────────────────────────────────────────────────────────────┐
│                         ACS (Telegram)                              │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ webhook POST /telegram/webhook
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  FastAPI (app/main.py)                                              │
│  ├── /telegram/webhook  → bot/webhook.py                            │
│  ├── /metrics           → observabilidade.py                        │
│  └── /healthz                                                       │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        ▼                      ▼                      ▼
┌──────────────┐      ┌──────────────┐      ┌──────────────────┐
│ Bot (FSM)    │      │ Motor        │      │ LLM (Claude API) │
│ bot/         │◄────►│ motor/       │◄────►│ llm/             │
│ fsm.py       │      │ priorizador  │      │ gerador_lista.py │
│ handlers.py  │      │ regras.py    │      │ cliente.py       │
│ historico.py │      │              │      │ (com fallback)   │
└──────┬───────┘      └──────┬───────┘      └─────────┬────────┘
       │                     │                        │
       └─────────────────────┼────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Database (PostgreSQL 16)                                           │
│  ├── profissionais · criancas · visitas · gestores                  │
│  ├── auditoria (LGPD log)                                           │
│  ├── chat_history (AES-256, retenção 90d)                           │
│  ├── lista_sugestoes (status: SUGERIDA/VISITADA/NAO_VISITADA)       │
│  └── fila_reposicao (override_topo, dias_pendente, score_ajustado)  │
└──────────────────────────────▲──────────────────────────────────────┘
                               │
┌──────────────────────────────┴──────────────────────────────────────┐
│  APScheduler (em-process)                                           │
│  ├── 05h00 → batch_manha (gera lista, chama Claude, envia 07h)      │
│  └── 22h00 → batch_noite (move SUGERIDA→NAO_VISITADA, atualiza fila)│
└─────────────────────────────────────────────────────────────────────┘
```

## 3. Stack tech (com justificativas)

### Camada de aplicação

| Tech | Versão | Por quê |
|---|---|---|
| Python | 3.12 | Async maduro, type hints melhorados, perf |
| FastAPI | ≥0.110 | Async nativo, Pydantic v2 integrado, OpenAPI grátis pra demo |
| python-telegram-bot | v21+ | API oficial, suporte async, conversation handlers úteis |
| transitions | ≥0.9 | FSM declarativa, serializável em JSON |

### Persistência

| Tech | Versão | Por quê |
|---|---|---|
| PostgreSQL | 16 | UUID nativo, `ON CONFLICT DO UPDATE`, JSONB, partial indexes |
| SQLAlchemy | 2.0 async | Padrão da indústria, type hints reais com `Mapped` |
| asyncpg | latest | Driver async mais rápido para Postgres |
| Alembic | latest | Migrations versionadas, autogenerate funciona bem com SQLAlchemy 2 |

### Agendamento

| Tech | Versão | Por quê |
|---|---|---|
| APScheduler | 3.10+ | Em-process, zero infra extra, suficiente pra 2 jobs |

**Não usar Celery + Redis no MVP.** Apenas 2 jobs cron por dia não justifica a complexidade. Migração futura é trivial (mesma interface declarativa).

### IA

| Tech | Versão | Por quê |
|---|---|---|
| anthropic | latest | SDK oficial, async, retry built-in |
| Modelo | `claude-haiku-4-5` | Custo/latência ideais para formatação de listas |

### Segurança

| Tech | Versão | Por quê |
|---|---|---|
| cryptography | latest | Fernet (AES-128-CBC + HMAC-SHA256) — padrão Python |
| python-jose | latest | JWT se precisar (improvável no MVP) |

### Observabilidade

| Tech | Versão | Por quê |
|---|---|---|
| structlog | latest | JSON logs, contexto estruturado, fácil de filtrar |
| prometheus-client | latest | Endpoint `/metrics` Prometheus-compatible |

### Dev

| Tech | Versão | Por quê |
|---|---|---|
| pytest | latest | Padrão Python |
| pytest-asyncio | latest | Suporte async em testes |
| testcontainers | latest | Postgres real efêmero por teste — sem mock |
| httpx | latest | Cliente HTTP async pra testes de API |
| ruff | latest | Lint + format ultrarrápido |
| mypy | latest | Type checking estático |
| docker compose | v2 | Orquestração local |

## 4. Estrutura de pastas

```
acs-primeira-infancia/
├── CLAUDE.md                       # Instruções para Claude Code (lido auto)
├── README.md
├── Makefile                        # Targets canônicos (use sempre)
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── .env.example
├── .gitignore
│
├── .claude/
│   └── skills/                     # Skills customizadas por fase
│       ├── acs-fase-bootstrap/
│       ├── acs-fase-modelos/
│       ├── acs-fase-seed/
│       ├── acs-fase-motor/
│       ├── acs-fase-llm/
│       ├── acs-fase-bot/
│       ├── acs-fase-batches/
│       ├── acs-fase-demo/
│       ├── acs-tdd-helper/         # TDD workflow
│       └── acs-lgpd-guard/         # LGPD enforcement
│
├── docs/
│   ├── PRD_v3.0.md
│   ├── architecture/
│   │   ├── arquitetura.md          # Este arquivo
│   │   ├── decisoes_design.md      # G1-G18 resolvidos
│   │   └── plano_implementacao.md  # 8 fases
│   └── adr/                        # Architecture Decision Records
│       ├── 001-monolito-vs-microservicos.md
│       ├── 002-apscheduler-vs-celery.md
│       ├── 003-criptografia-fernet.md
│       └── 004-fsm-transitions-lib.md
│
├── alembic/
│   ├── env.py
│   └── versions/
│
├── app/
│   ├── __init__.py
│   ├── main.py                     # FastAPI entry
│   ├── config.py                   # pydantic-settings
│   ├── db.py                       # engine + session factory
│   ├── observabilidade.py          # /metrics, /healthz
│   ├── auditoria.py                # helper LGPD
│   ├── crypto.py                   # Fernet wrapper
│   │
│   ├── models/                     # SQLAlchemy models
│   │   ├── __init__.py
│   │   ├── base.py                 # mixin (id, created_at, updated_at)
│   │   ├── profissional.py
│   │   ├── crianca.py
│   │   ├── visita.py
│   │   ├── gestor.py
│   │   ├── auditoria.py
│   │   ├── chat_history.py
│   │   ├── lista_sugestoes.py
│   │   └── fila_reposicao.py
│   │
│   ├── motor/                      # Priorização
│   │   ├── __init__.py
│   │   ├── regras.py               # funções puras de score
│   │   ├── priorizador.py          # pipeline completo
│   │   └── deduplicacao.py
│   │
│   ├── llm/                        # Claude API
│   │   ├── __init__.py
│   │   ├── cliente.py              # wrapper SDK
│   │   ├── prompts.py              # templates
│   │   ├── gerador_lista.py
│   │   └── fallback.py             # template determinístico
│   │
│   ├── bot/                        # Telegram + FSM
│   │   ├── __init__.py
│   │   ├── webhook.py              # FastAPI endpoint
│   │   ├── auth.py                 # chat_id → profissional_id
│   │   ├── fsm.py                  # estados Ficha Primeira Infância
│   │   ├── handlers.py             # handlers por estado
│   │   ├── comandos.py             # /start, /lista, /limpar_historico
│   │   └── historico.py            # contexto persistente
│   │
│   └── schedulers/                 # APScheduler jobs
│       ├── __init__.py
│       ├── scheduler.py            # bootstrap
│       ├── batch_manha.py          # 05h00
│       ├── batch_noite.py          # 22h00 (coração da v3.0)
│       └── limpeza_historico.py    # remove chat_history > 90d
│
├── scripts/
│   ├── seed.py                     # Popula DB com dataset hackathon
│   └── demo.py                     # Cenário end-to-end para pitch
│
└── tests/
    ├── conftest.py                 # fixtures globais (testcontainers)
    ├── unit/                       # funções puras
    │   ├── test_motor_regras.py
    │   ├── test_motor_priorizador.py
    │   ├── test_motor_deduplicacao.py
    │   ├── test_llm_fallback.py
    │   ├── test_crypto.py
    │   └── test_bot_fsm.py
    ├── integration/                # com Postgres real
    │   ├── test_models_constraints.py
    │   ├── test_batch_manha.py
    │   ├── test_batch_noite.py
    │   ├── test_batch_noite_idempotencia.py
    │   ├── test_chat_history_retencao.py
    │   ├── test_limpar_historico.py
    │   └── test_auditoria.py
    └── e2e/                        # ciclo completo
        ├── test_ciclo_diario.py
        ├── test_pendentes_no_topo.py
        └── test_escalonamento_risco.py
```

## 5. Fluxos principais

### Fluxo 1 — Manhã (05h → 07h)

```
05:00 ── APScheduler dispara batch_manha
         │
         ▼
         Para cada ACS ativo:
         │
         ├── motor.priorizador.gerar_lista(profissional_id)
         │   ├── busca crianças do ACS
         │   ├── filtra duplicatas (lista_sugestoes status=VISITADA no ciclo)
         │   ├── busca overrides da fila_reposicao
         │   ├── calcula scores (regras.py)
         │   ├── recalcula grupo_risco (snapshot)
         │   ├── combina: overrides ordenados primeiro + novos por score
         │   └── trunca em 15 itens
         │
         ├── llm.gerador_lista.formatar(lista)
         │   ├── tenta Claude API com retry
         │   └── em falha → fallback template
         │
         └── grava em lista_sugestoes (status=SUGERIDA, posicao_lista)

07:00 ── Envia mensagem Telegram pro ACS
         (já formatada, com marcações "PENDENTE DO DIA ANTERIOR")
```

### Fluxo 2 — Durante o dia (07h → 21h59)

```
ACS abre Telegram
     │
     ▼
ACS → /lista                                       (comando)
     │
     ▼
Bot busca lista_sugestoes do dia + chat_history (contexto)
     │
     ▼
Bot envia lista numerada
     │
     ▼
ACS → "vou na #3"                                  (texto livre)
     │
     ▼
FSM transita: S0_INICIO → S1_SELECAO_CRIANCA
     │
     ▼
Bot pergunta dados da Ficha Primeira Infância
     │
     ▼
FSM percorre S2 → S3 → ... → S8 (perguntas da ficha)
     │
     ▼
ACS → "encerrar visita"
     │
     ▼
Numa transação atômica:
     ├── INSERT INTO visitas
     ├── UPDATE lista_sugestoes SET status='VISITADA'
     ├── UPDATE fila_reposicao SET resolvida_em=NOW() (se houver)
     └── INSERT INTO auditoria (acao='VISITA_REGISTRADA')
```

### Fluxo 3 — Noite (22h00)

```
22:00 ── APScheduler dispara batch_noite (idempotente)
         │
         ▼
         BEGIN TRANSACTION
         │
         ├── Para cada lista_sugestoes WHERE status='SUGERIDA' AND data_sugestao=hoje:
         │       UPDATE status='NAO_VISITADA'
         │
         ├── Para cada não-visitada:
         │   ├── Calcula score_ajustado (regras 5.4 PRD)
         │   ├── Determina grupo_risco (snapshot atual)
         │   ├── Determina override_topo (true se risco OU dias_pendente≥3)
         │   └── INSERT INTO fila_reposicao
         │       ON CONFLICT (profissional_id, crianca_ref, data_origem)
         │       DO UPDATE SET dias_pendente=excluded.dias_pendente+1,
         │                     score_ajustado=excluded.score_ajustado
         │
         ├── Para cada gestor afetado:
         │   ├── Agrega notificações por equipe
         │   └── Envia 1 mensagem Telegram resumida
         │
         ├── Calcula taxa de cobertura por equipe
         ├── Se taxa < 60% → notifica gestor
         │
         ├── INSERT INTO auditoria (acao='BATCH_NOITE_COMPLETO', metadata={...})
         │
         COMMIT
         │
22:30 ── job_limpeza_historico (separado)
         DELETE FROM chat_history WHERE criado_em < NOW() - INTERVAL '90 days'
```

## 6. Decisões de arquitetura críticas

### 6.1 Monolito vs Microsserviços

**Decisão**: Monolito para MVP.

**Justificativa**: Hackathon tem 24-48h. Monolito = 1 deploy, 1 set de logs, 1 banco. Quando produzir, separar é refactor de entrypoint, não reescrita.

ADR completo: `docs/adr/001-monolito-vs-microservicos.md`

### 6.2 APScheduler vs Celery

**Decisão**: APScheduler em-process.

**Justificativa**: 2 jobs cron por dia não justifica Redis + worker. APScheduler tem AsyncIOScheduler nativo e roda no mesmo processo da FastAPI.

ADR: `docs/adr/002-apscheduler-vs-celery.md`

### 6.3 Criptografia em coluna vs em arquivo

**Decisão**: Fernet por coluna (`content_enc`).

**Justificativa**: Granularidade — `/limpar_historico` precisa apagar mensagens específicas, não rotacionar chave de tudo. Fernet inclui timestamp, evita ataques de replay.

ADR: `docs/adr/003-criptografia-fernet.md`

### 6.4 FSM com `transitions` lib vs implementação manual

**Decisão**: lib `transitions`.

**Justificativa**: Estado da FSM precisa ser serializável (persiste em `chat_history.estado_fsm`). A lib `transitions` faz isso nativamente com `MachineState`. Implementação manual com if/else vira spaghetti rápido com 8+ estados.

ADR: `docs/adr/004-fsm-transitions-lib.md`

## 7. Tabela de variáveis de ambiente

| Variável | Obrigatória | Default | Descrição |
|---|---|---|---|
| `DATABASE_URL` | Sim | — | `postgresql+asyncpg://user:pass@host:5432/dbname` |
| `TELEGRAM_BOT_TOKEN` | Sim | — | Token do BotFather |
| `TELEGRAM_WEBHOOK_URL` | Sim | — | URL pública pro webhook (ngrok em dev) |
| `ANTHROPIC_API_KEY` | Sim | — | Chave Claude API |
| `ANTHROPIC_MODEL` | Não | `claude-haiku-4-5` | Modelo Claude usado |
| `ENCRYPTION_KEY` | Sim | — | Chave Fernet base64 (gerar com `Fernet.generate_key()`) |
| `TELEGRAM_CHAT_ID_SALT` | Sim | — | Salt pro hash de chat_id |
| `BATCH_MANHA_HORA` | Não | `5` | Hora do batch manhã (24h format) |
| `BATCH_NOITE_HORA` | Não | `22` | Hora do batch noite |
| `LIMITE_LISTA_DIARIA` | Não | `15` | Máximo de crianças por ACS/dia |
| `CICLO_DEDUPLICACAO_DIAS` | Não | `30` | Janela do ciclo (dias) |
| `RETENCAO_CHAT_DIAS` | Não | `90` | Retenção LGPD |
| `SCORE_THRESHOLD_RISCO` | Não | `40` | Score que define grupo_risco |
| `LOG_LEVEL` | Não | `INFO` | DEBUG, INFO, WARNING, ERROR |
| `ENV` | Não | `dev` | dev, test, prod |

## 8. Critérios não-funcionais (do PRD)

| Critério | Meta | Como atingir |
|---|---|---|
| Geração de lista < 90s/equipe | Sim | Pool async, queries com partial indexes |
| Resposta bot < 2s | Sim | DB queries com `select` cacheado, FSM em memória |
| Idempotência batch | Sim | `ON CONFLICT DO UPDATE` em todas as escritas |
| Retomada após falha 05h | Sim | Lista do dia anterior reentregue com aviso |
| 99.5% uptime | N/A no MVP | Documentado como produção-only |

## 9. Próximo passo

Após ler este documento, leia em ordem:
1. `decisoes_design.md` — como resolvemos as 18 ambiguidades do PRD
2. `plano_implementacao.md` — 8 fases sequenciais
3. ADRs em `adr/` apenas quando precisar de contexto histórico de uma decisão
