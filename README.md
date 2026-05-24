# ACS Primeira Infância v3.0

Sistema de priorização de visitas domiciliares de Agentes Comunitários de Saúde (ACS) para crianças de 0-6 anos, com canal Telegram, motor híbrido de regras + IA e ciclo de retroalimentação noturno.

Projeto do **Claude Impact Lab Rio 2026** — hackathon Prefeitura do Rio + Anthropic.

## O que faz

Todo dia às 05h, o sistema gera uma lista priorizada de até 15 crianças que cada ACS deve visitar, considerando vacinação, consultas, vulnerabilidade e tempo sem visita. Às 22h, crianças não visitadas voltam pra fila — com escalonamento automático pra grupos de risco. ACS interage só pelo Telegram, em linguagem natural, guiado por uma FSM da Ficha Primeira Infância.

## Setup local (4 comandos)

```bash
git clone <repo>
cd acs-primeira-infancia
cp .env.example .env  # preencher TELEGRAM_BOT_TOKEN e ANTHROPIC_API_KEY
make up && make migrate && make seed
```

Pronto. `curl localhost:8000/healthz` deve retornar `ok`.

## Demonstração (60 segundos)

```bash
make demo
```

Executa o cenário completo: Dia 1 batch → visitas parciais → batch noturno → Dia 2 batch com pendentes no topo. Veja a saída no terminal.

## Comandos canônicos

| Comando | O que faz |
|---|---|
| `make up` | Sobe Postgres + app via Docker |
| `make down` | Desce containers |
| `make migrate` | Aplica migrations Alembic |
| `make revision MSG="descricao"` | Cria nova migration |
| `make seed` | Popula DB com dataset hackathon (~150 crianças) |
| `make test` | Roda todos os 134 testes |
| `make test-unit` | Só testes unitários |
| `make test-integration` | Testes com Postgres real (testcontainers) |
| `make test-e2e` | Testes end-to-end |
| `make test-coverage` | Cobertura (gera `htmlcov/index.html`) |
| `make lint` | ruff + mypy |
| `make demo` | Cenário de pitch (60s) |
| `make demo-reset` | Reset DB + seed + demo |
| `make clean` | Remove containers e volumes |

## Para o Claude Code

Este projeto foi estruturado pra implementação assistida por Claude Code com TDD.

- `CLAUDE.md` — instruções persistentes (lidas automaticamente em toda sessão)
- `.claude/skills/` — 10 skills customizadas: 8 fases + TDD helper + LGPD guard
- Os 134 testes do MVP estão pré-mapeados como `@pytest.mark.skip` aguardando implementação

Comando inicial pro Claude Code:
```
"implementar fase 0"
```

Ele carrega a skill `acs-fase-bootstrap` e segue o checklist.

## Documentação

| Documento | Propósito |
|---|---|
| `docs/PRD_v3.0.md` | Product Requirements Document oficial |
| `docs/architecture/arquitetura.md` | Stack, fluxos, diagramas |
| `docs/architecture/decisoes_design.md` | Resolução dos 18 gaps do PRD (G1–G18) |
| `docs/architecture/plano_implementacao.md` | 8 fases sequenciais |
| `docs/adr/` | Architecture Decision Records |

## Estrutura de pastas

```
.
├── CLAUDE.md                       # Instruções pro Claude Code
├── .claude/skills/                 # 10 skills customizadas
├── docs/                           # PRD + arquitetura + ADRs
├── app/                            # Código de produção
│   ├── main.py                     # FastAPI entry
│   ├── config.py · db.py · crypto.py · auditoria.py
│   ├── models/                     # SQLAlchemy
│   ├── motor/                      # Priorização (puro)
│   ├── llm/                        # Claude API + fallback
│   ├── bot/                        # Telegram + FSM
│   └── schedulers/                 # APScheduler jobs
├── tests/                          # 134 testes pré-mapeados
│   ├── conftest.py                 # Fixtures globais
│   ├── unit/                       # Sem DB
│   ├── integration/                # Postgres real (testcontainers)
│   └── e2e/                        # Ciclo completo
├── scripts/                        # seed.py, demo.py, limpar_db.py
├── alembic/                        # Migrations versionadas
├── Makefile · Dockerfile · docker-compose.yml
├── pyproject.toml · pytest.ini · alembic.ini
└── .env.example
```

## Stack

Python 3.12 · FastAPI · python-telegram-bot v21 · transitions · SQLAlchemy 2.0 async · PostgreSQL 16 · Alembic · APScheduler · cryptography (Fernet) · anthropic SDK · pytest · testcontainers · ruff · mypy · structlog · prometheus-client.

## Conformidade LGPD

Crianças (0-6 anos) + dados de saúde = especialmente protegidos.

- Chat criptografado AES-256 (Fernet), retenção 90 dias
- `/limpar_historico` apaga conteúdo, mantém auditoria sem expor texto
- `telegram_chat_id` sempre hasheado com salt
- Logs estruturados nunca incluem nome ou conteúdo
- Cada ação sensível grava em `auditoria`

Detalhes na skill `.claude/skills/acs-lgpd-guard/SKILL.md`.

## Status

🚧 **MVP em construção** — repositório inicializado, esperando implementação fase por fase.

Status de cada fase é mantido pelo Claude Code via commits convencionais: `feat(fase-N): ...`.

## Licença

A definir junto com a Prefeitura do Rio (decisão do hackathon).
