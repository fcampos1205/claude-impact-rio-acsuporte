# ADR 001 — Monolito ou microsserviços?

**Status**: Aceito · 2026-05-24

## Contexto

Sistema combina três responsabilidades: API/webhook Telegram, scheduler de batches (05h e 22h), workers de motor de priorização e LLM. Em produção real, essas três rodariam separadas. No hackathon, temos 24-48h.

## Decisão

**Monolito FastAPI com APScheduler em-process e workers async no mesmo runtime.**

Um único `docker compose up` sobe DB + app. APScheduler dispara jobs no mesmo processo da API. Todas as funções de domínio são chamadas como funções Python diretas.

## Consequências

### Positivas

- Setup local 1-comando — crítico pra demo
- Logs unificados (1 stdout = 1 conjunto pra debug)
- Sem complexidade de mensageria, descoberta de serviços, locks distribuídos
- Refactor pra microsserviços é re-organização de entrypoints, não reescrita
- TDD muito mais rápido (sem mocks de fila/queue)

### Negativas

- Não escala horizontalmente como está — produção real com 6200 ACS precisaria separar
- Restart da API pára o scheduler — solução: deploy zero-downtime no futuro
- Limite de concorrência do processo único (mitigamos com `asyncio.Semaphore(5)`)

### Caminho de evolução pra produção

1. Extrair scheduler pra container separado (Celery beat + workers)
2. Extrair LLM workers (carga elástica)
3. API fica só com webhook + endpoints leves
4. Comunicação por Redis ou RabbitMQ
5. Banco continua sendo único Postgres (não precisa shardar até ~100k ACS)

## Alternativas consideradas

- **Microsserviços desde o início**: vetada pela falta de tempo do hackathon. Validamos a arquitetura primeiro, separamos depois.
- **Serverless (Lambda)**: cold start atrapalha resposta < 2s do bot. Vetada.
- **Apenas API, batches via cron externo**: complica o dev local. Vetada.

## Referências

- `docs/architecture/arquitetura.md` seção 6.1
- Discussão da decisão durante análise pré-código (chat de planejamento)
