# ADR 002 — APScheduler ou Celery?

**Status**: Aceito · 2026-05-24

## Contexto

O sistema executa 3 jobs agendados:
- `batch_manha` às 05h00 (gera listas)
- `batch_noite` às 22h00 (move não-visitadas pra fila, notifica gestor)
- `limpeza_historico` às 03h00 (apaga chat > 90 dias)

Para 5 equipes de demo (3 ACS cada), volume é trivial: ~75 ACS, ~3000 sugestões/mês. Para produção SMS-Rio (6200 ACS), volume seria ~250x maior.

## Decisão

**APScheduler em-process, mesmo runtime da FastAPI.**

Usar `AsyncIOScheduler` (suporte async nativo) com `CronTrigger`. Jobs declarados em `app/schedulers/scheduler.py`. Disparados pelo evento de startup do FastAPI.

## Consequências

### Positivas

- Zero infra extra — sem Redis, RabbitMQ, broker
- Jobs definidos em Python puro, type-checked com mypy
- Compartilhamento direto de session pool com a API
- Reinício do app ressincroniza o agendamento automaticamente
- Tempo de implementação: ~30 minutos vs ~3 horas com Celery

### Negativas

- Não tolera múltiplas réplicas do app (jobs disparariam em paralelo)
- Sem retry built-in robusto (precisamos implementar via tenacity ou similar)
- Sem dashboard de monitoramento (Flower é exclusivo do Celery)
- Restart da API pára o scheduler até próximo startup

### Mitigações no MVP

- Idempotência via `ON CONFLICT DO UPDATE` torna re-execução segura (G6)
- Auditoria registra início/fim de cada batch — debug via DB
- `max_instances=1` na configuração do APScheduler evita overlap

## Caminho de evolução

Quando precisar:

1. **Múltiplas réplicas da API** → migrar pra Celery + Redis. Estrutura dos jobs já é compatível (funções async, sem estado em memória).
2. **Dashboard de monitoramento** → adicionar Flower (Celery) ou Prometheus + Grafana.
3. **Retry robusto** → `tenacity` por enquanto, `celery.retry` depois.

## Alternativas consideradas

- **Celery + Redis**: tempo de setup desproporcional pro MVP. 3 jobs cron por dia não precisam de fila distribuída.
- **Cron + script Python**: requer 2º container, ortogonal ao app. Mais coisas pra subir no demo.
- **GitHub Actions cron**: serviço externo, depende de internet, latência alta.
- **Postgres `pg_cron`**: força lógica de domínio em PL/pgSQL. Hostil pra TDD.

## Referências

- APScheduler docs: https://apscheduler.readthedocs.io/
- `docs/architecture/decisoes_design.md` G12
