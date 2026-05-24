# Instruções para Claude Code — Projeto ACS Primeira Infância

> **Este arquivo é lido automaticamente em toda sessão do Claude Code neste repositório.** Leia inteiro antes de qualquer ação.

## Contexto do projeto

MVP de hackathon (Claude Impact Lab Rio 2026). Sistema que prioriza visitas domiciliares de Agentes Comunitários de Saúde (ACS) para crianças de 0-6 anos (Primeira Infância), com canal Telegram e ciclo de retroalimentação noturno.

Objetivo do código: **demonstrar end-to-end no pitch**, não substituir produção. Decisões de design favorecem clareza e demonstrabilidade sobre robustez extrema.

## Documentação obrigatória — leia antes de codar

A leitura é sequencial. Não pule.

1. `docs/PRD_v3.0.md` — Product Requirements Document oficial (referência da v3.0)
2. `docs/architecture/arquitetura.md` — Decisões de arquitetura, stack, fluxos
3. `docs/architecture/decisoes_design.md` — Resolução dos 18 gaps lógicos identificados no PRD. **Use estas decisões como verdade. Não reinvente.**
4. `docs/architecture/plano_implementacao.md` — 8 fases sequenciais. Cada fase é o seu prompt de trabalho.
5. `docs/adr/` — Architecture Decision Records detalhados quando precisar de justificativa

## Regras de execução

### Regra 1 — TDD obrigatório (red → green → refactor)

Para cada função pública ou comportamento de negócio:

1. Leia o teste correspondente em `tests/` (já estão escritos como esqueletos com `@pytest.mark.skip(reason="aguardando implementação")`)
2. Remova o skip
3. Rode `pytest <arquivo_teste> -v` — confirme que FALHA (red)
4. Implemente o mínimo para passar
5. Rode novamente — confirme que PASSA (green)
6. Refatore mantendo verde

Nunca escreva código de produção sem ter o teste falhando antes. Se o teste não existe ainda para o que você está fazendo, pare e escreva o teste primeiro.

### Regra 2 — Skills das fases

Quando o usuário disser "implementar fase N" ou similar, a skill `acs-fase-N-*` correspondente é carregada automaticamente. Ela tem o checklist da fase. Siga-o em ordem.

Skills disponíveis em `.claude/skills/`:
- `acs-fase-bootstrap` — Fase 0 (infra)
- `acs-fase-modelos` — Fase 1 (DB)
- `acs-fase-seed` — Fase 2 (dados)
- `acs-fase-motor` — Fase 3 (priorização)
- `acs-fase-llm` — Fase 4 (Claude API)
- `acs-fase-bot` — Fase 5 (Telegram + FSM)
- `acs-fase-batches` — Fase 6 (jobs 05h e 22h)
- `acs-fase-demo` — Fase 7 (orquestração demo)
- `acs-tdd-helper` — TDD workflow (carrega sempre que envolver testes)
- `acs-lgpd-guard` — LGPD enforcement (carrega sempre que envolver dados pessoais)

### Regra 3 — LGPD não-negociável

Crianças são titulares de dados especialmente protegidos (saúde + menores). Sempre que tocar em dados pessoais:

- Mensagens do chat: criptografar com Fernet/AES-256 antes de gravar
- Logs: nunca logar `content`, `cpf`, `nome completo`. Pode logar `profissional_id`, `crianca_ref` (UUID), `acao`, `timestamp`
- Auditoria: toda ação que lê/escreve/exporta dados pessoais grava em `auditoria`
- Comando `/limpar_historico`: apaga conteúdo, mantém registro em `auditoria` (sem o conteúdo) com `acao='LIMPAR_HISTORICO'` e contagem
- Retenção: chat_history = 90 dias absoluto (job de limpeza automático)

A skill `acs-lgpd-guard` tem checklist completo. Carregue quando trabalhar com chat, auditoria, /limpar_historico, ou exportação.

### Regra 4 — Comandos preferenciais

Use sempre os targets do Makefile, nunca chame ferramentas direto:

- `make up` / `make down` — sobe/desce Docker
- `make migrate` — aplica migrations
- `make revision MSG="descricao"` — cria nova migration
- `make test` — roda toda a suíte
- `make test-unit` / `make test-integration` / `make test-e2e` — por camada
- `make lint` — ruff + mypy
- `make seed` — popula DB com dados de demo
- `make demo` — roda cenário end-to-end pra pitch

### Regra 5 — Quando você não souber

- **Conflito entre PRD e decisões_design.md**: `decisoes_design.md` vence. PRD pode estar desatualizado.
- **Ambiguidade nova (não coberta)**: pare e pergunte ao usuário. Não invente.
- **Erro de teste de integração com Postgres**: rode `make down && make up && make migrate` para resetar.
- **Mocks**: prefira `testcontainers-postgres` (Postgres real efêmero) a mockar SQLAlchemy. A Claude API mocka via `httpx.MockTransport`.

## Stack de uma olhada

| Camada | Tech |
|---|---|
| Web | FastAPI + Uvicorn |
| Bot | python-telegram-bot v21 (async) |
| FSM | `transitions` lib |
| DB | PostgreSQL 16 |
| ORM | SQLAlchemy 2.0 async + Alembic |
| Scheduler | APScheduler (em-process) |
| Crypto | cryptography (Fernet) |
| LLM | anthropic SDK (claude-haiku-4-5) |
| Config | pydantic-settings |
| Test | pytest + pytest-asyncio + testcontainers |
| Lint | ruff + mypy |
| Log | structlog (JSON) |

## Anti-padrões — não faça

- **Não use SQLite** — Postgres é requerido (UUID nativo, ON CONFLICT, JSONB)
- **Não use Celery + Redis** — APScheduler basta no MVP
- **Não use Django ORM** — SQLAlchemy 2.0 é o padrão
- **Não use psycopg2 síncrono** — async psycopg ou asyncpg
- **Não logue conteúdo de mensagens** — viola LGPD
- **Não escreva tests com `unittest.TestCase`** — pytest funcional puro
- **Não rode migrations manualmente com SQL** — sempre via Alembic
- **Não armazene chat_id Telegram bruto** — sempre hash com salt
- **Não confie em `datetime.now()` em testes** — use `freezegun` ou injeção de clock

## Definição de "pronto" para qualquer fase

Antes de marcar uma fase como completa:

1. Todos os testes da fase passam (`make test-unit` + `make test-integration` da pasta correspondente)
2. `make lint` retorna 0 erros
3. README da fase tem comando de validação manual que funciona
4. Não há `@pytest.mark.skip` pendente na pasta da fase
5. Auditoria registra ações da fase quando aplicável
6. ADR criado em `docs/adr/` se houve decisão de design nova

## Em caso de dúvida sobre o que fazer agora

Se você acabou de entrar neste repo:
1. Leia este arquivo (você está fazendo isso)
2. Leia `docs/PRD_v3.0.md`
3. Leia `docs/architecture/decisoes_design.md`
4. Pergunte ao usuário: "qual fase devo começar?"
5. Carregue a skill da fase respondida e siga seu checklist
