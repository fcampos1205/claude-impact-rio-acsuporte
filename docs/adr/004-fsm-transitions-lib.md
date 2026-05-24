# ADR 004 — Implementação da FSM com a lib `transitions`

**Status**: Aceito · 2026-05-24

## Contexto

A Ficha Primeira Infância tem 8 estados sequenciais com 1 ramo alternativo (responsável ausente). Estado precisa **persistir** entre mensagens (cada mensagem do ACS no Telegram é uma nova requisição HTTP — sem estado em memória).

Estados:
```
S0_INICIO → S1_SELECAO_CRIANCA → S2_RESPONSAVEL_PRESENTE → S3_VACINACAO_EM_DIA
  → S4_CONSULTAS_EM_DIA → S5_ALEITAMENTO → S6_DESENVOLVIMENTO
  → S7_OBSERVACOES → S8_ENCERRAMENTO

S1 → S8 (responsável ausente)
* → S0 (cancelar)
```

## Decisão

**Usar a biblioteca `transitions` (especificamente `transitions.extensions.asyncio.AsyncMachine`).**

FSM declarativa: estados + transições como dados, callbacks são funções Python. Estado serializado como string (nome do estado), persistido em `chat_history.estado_fsm`.

## Consequências

### Positivas

- **Declarativa**: estados e transições visíveis num só lugar — fácil de revisar e diagramar
- **Serializável**: `fsm.state` retorna string, restaurada com `FichaFSM(estado_inicial=...)`
- **Validação built-in**: tentar transição inválida levanta erro — feedback ao usuário
- **Suporte async**: callbacks podem ser corotinas — integra naturalmente com SQLAlchemy async
- **Maturidade**: 10+ anos de uso, 5k+ stars no GitHub, manutenção ativa
- **Diagrama auto-gerado**: `transitions-anyio` pode gerar PlantUML, útil para docs

### Negativas

- Curva de aprendizado para quem não conhece a lib (~30 min)
- Erros sutis com `auto_transitions=True` (libera triggers `to_<estado>()` que confundem) — desativamos
- Stack trace de transição falha não é super legível — mitigamos com asserts antes do trigger

## Alternativas consideradas

### Implementação manual (if/else em handlers)

```python
async def handler(msg, estado_atual):
    if estado_atual == "S0":
        # ...
    elif estado_atual == "S1":
        # ...
```

- Vantagem: zero dependência
- Desvantagem: vira spaghetti com 8 estados + ramos. Difícil de adicionar estado novo.

Rejeitado por manutenibilidade.

### Statechart oficial (lib `statechart`)

- Mais poderoso (suporta nested states, parallel regions)
- Excesso de capacidade para 8 estados lineares
- Comunidade menor

Rejeitado por over-engineering.

### Redux-style (state como dict imutável)

- Conceitualmente elegante
- Quebra com SQLAlchemy ORM (modelo é mutável)
- Padrão pouco usado em Python

Rejeitado por fricção com stack.

### `python-statemachine` (concorrente do `transitions`)

- Similar em features
- Comunidade menor
- Suporte async menos maduro

Rejeitado.

## Padrão de serialização

```python
# Salvar
chat_msg.estado_fsm = fsm.state  # string

# Restaurar
fsm = FichaFSM.restaurar(chat_msg.estado_fsm)
```

Estado é puro nome (string). **Dados coletados** durante a FSM (vacinação, consultas) ficam em outra estrutura — não no FSM em si.

## Referências

- `transitions` docs: https://github.com/pytransitions/transitions
- `docs/architecture/decisoes_design.md` (não tem gap específico de FSM, mas contexto geral)
- PRD seção referente a Ficha Primeira Infância
