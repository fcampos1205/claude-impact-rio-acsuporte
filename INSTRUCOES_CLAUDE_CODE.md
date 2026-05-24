# Como usar este repositório com Claude Code

Este repositório foi preparado pra **acelerar a implementação do MVP** do ACS Primeira Infância v3.0 usando Claude Code. Toda a estrutura de documentação, decisões de design, plano de implementação e testes está pré-mapeada.

## Setup rápido (uma vez só)

```bash
# 1. Instalar Claude Code (se ainda não tiver)
# Veja: https://docs.claude.com/en/docs/claude-code

# 2. Clonar e entrar no diretório
cd acs-primeira-infancia/

# 3. Iniciar sessão Claude Code
claude
```

Quando você inicia o Claude Code aqui, ele lê automaticamente:
- `CLAUDE.md` (regras + contexto)
- Skills disponíveis em `.claude/skills/`

## Primeira interação recomendada

Cole exatamente isso na sessão Claude Code:

```
Vamos implementar o MVP por fases. Comece pela Fase 0 (bootstrap).
Antes, valide que leu CLAUDE.md, PRD_v3.0.md e decisoes_design.md.
```

Claude Code vai carregar a skill `acs-fase-bootstrap` e seguir o checklist da Fase 0.

## Fluxo recomendado por fase

Para cada fase (0 a 7):

1. **Você pede**: `"implementar fase N"`
2. **Claude Code**:
   - Carrega `.claude/skills/acs-fase-N-*/SKILL.md`
   - Lê os testes pré-mapeados em `tests/`
   - Para cada teste: remove `@pytest.mark.skip` → red → implementa → green → refactor
   - Roda `make lint` e `make test-<camada>` ao final
3. **Você revisa**:
   - Olha o que ele implementou
   - Pede ajustes se necessário
   - Commita: `git commit -m "feat(fase-N): ..."`
4. **Próxima fase**: `"implementar fase N+1"`

## Comandos úteis durante a sessão

| Pedido ao Claude Code | O que ele faz |
|---|---|
| `"implementar fase 3"` | Carrega skill da fase 3, segue checklist |
| `"explicar decisão G7"` | Lê `decisoes_design.md` e explica |
| `"mostrar arquitetura"` | Resume `arquitetura.md` |
| `"rodar testes da fase atual"` | `make test-<camada>` da fase em progresso |
| `"adicionar ADR para X"` | Cria nota em `docs/adr/` |
| `"revisar conformidade LGPD"` | Aciona skill `acs-lgpd-guard` |
| `"refatorar mantendo testes verdes"` | Refactor com TDD |

## Quando Claude Code pode errar

**Não confie cegamente nessas situações:**

- **Constraints SQL**: revise o que Alembic gerou em `alembic/versions/`. Às vezes Alembic ignora partial indexes ou inverte ordem de campos compostos.
- **Detalhes de async**: erros sutis em `await` podem passar pelo lint. Rode a feature antes de seguir.
- **Mocks excessivos**: se ele mockou Postgres num teste de integration, recuse e peça pra usar testcontainers.
- **Esquecer auditoria**: lembre-o sempre que tocar em dado pessoal.

## Estrutura de dependências entre fases

```
Fase 0 ─► Fase 1 ─► Fase 2 ─► Fase 3 ─► Fase 4 ─► Fase 5 ─► Fase 6 ─► Fase 7
(infra)   (models)  (seed)    (motor)  (LLM)     (bot)     (batches) (demo)
```

Não pule. Cada fase tem critérios de aceitação que validam pra próxima.

## Skills disponíveis

10 skills customizadas em `.claude/skills/`:

| Skill | Quando carrega |
|---|---|
| `acs-fase-bootstrap` | "implementar fase 0", "criar Docker", "configurar Postgres" |
| `acs-fase-modelos` | "implementar fase 1", "criar tabelas", "schema" |
| `acs-fase-seed` | "implementar fase 2", "popular DB", "seed" |
| `acs-fase-motor` | "implementar fase 3", "regras de score", "priorizador" |
| `acs-fase-llm` | "implementar fase 4", "integrar Claude", "prompts" |
| `acs-fase-bot` | "implementar fase 5", "bot Telegram", "FSM", "ficha" |
| `acs-fase-batches` | "implementar fase 6", "scheduler", "batch 22h" |
| `acs-fase-demo` | "implementar fase 7", "demo pitch", "métricas" |
| `acs-tdd-helper` | sempre que implementar comportamento testável |
| `acs-lgpd-guard` | sempre que tocar em dado pessoal/chat/auditoria |

## Tempo estimado

- **Total**: ~10h de Claude Code ativo
- **Plus**: ~3-4h de você revisando, testando manualmente, ajustando UX
- **Hackathon de 24h**: viável com folga
- **Hackathon de 48h**: viável com tempo pra polir pitch + gravar vídeo

## Se algo der errado

1. **Cobrança injusta de contexto**: o Claude Code pode tentar reinventar decisões já tomadas em `decisoes_design.md`. Sempre cite o gap (G1, G2, ...) e peça pra ele seguir o documento.
2. **Teste flakey**: revise as fixtures em `tests/conftest.py`. Se uma fixture session-scoped não está sendo limpa entre testes, ajuste o escopo.
3. **Migration Alembic incorreta**: delete o arquivo e refaça `make revision MSG="..."`. Confira manualmente o resultado.
4. **Bot Telegram não responde**: verifique `TELEGRAM_WEBHOOK_URL` (precisa ser HTTPS) e que o ngrok está rodando.

## Boa sorte!

Esta estrutura representa ~8h de planejamento. O trabalho a partir daqui é executar. Você está bem-equipado.

Quando todos os 134 testes passarem e `make demo` rodar limpo em < 60s, você tem um MVP pronto pra pitch.
