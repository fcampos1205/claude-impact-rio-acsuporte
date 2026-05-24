# Decisões de Design — Resolução dos Gaps do PRD v3.0

> **Documento canônico.** Quando o PRD for ambíguo, este documento vence. Quando o código precisar de uma escolha, esta é a escolha.

## Por que este documento existe

A análise do PRD v3.0 identificou 18 gaps lógicos (G1–G18) — ambiguidades, contradições e lacunas que, se deixadas pro Claude Code resolver no chute, produziriam bugs sutis ou comportamento divergente do PRD.

Cada decisão abaixo está alinhada com o objetivo do MVP: **demonstrar end-to-end no pitch do hackathon**. Quando há trade-off entre "correto para produção" e "demonstrável e simples", o segundo vence (com nota de evolução).

---

## 🔴 Gaps críticos (resolvidos)

### G1 — Resolução da fila quando há visita

**Problema**: O PRD não define explicitamente como `fila_reposicao` é "resolvida" quando a visita acontece. Risco: a fila incha indefinidamente.

**Decisão**: Quando uma visita é registrada (FSM completa), uma única transação atômica executa:

```sql
BEGIN;
  INSERT INTO visitas (...) VALUES (...);
  UPDATE lista_sugestoes
    SET status = 'VISITADA', atualizado_em = NOW()
    WHERE profissional_id = $1 AND crianca_ref = $2 AND data_sugestao = CURRENT_DATE;
  UPDATE fila_reposicao
    SET resolvida_em = NOW()
    WHERE profissional_id = $1 AND crianca_ref = $2 AND resolvida_em IS NULL;
  INSERT INTO auditoria (acao, profissional_id, metadata) VALUES (...);
COMMIT;
```

**Critério na query do motor**: `WHERE resolvida_em IS NULL` para considerar fila ativa.

**Teste pré-mapeado**: `tests/integration/test_batch_noite.py::test_visita_resolve_fila`

---

### G2 — Race condition no corte 21h59 / batch 22h

**Problema**: O que acontece com visitas registradas durante o batch noturno?

**Decisão**: Corte rígido por timestamp:

- Batch 22h filtra: `WHERE data_sugestao = CURRENT_DATE - 1 AND status = 'SUGERIDA' AND atualizado_em < (CURRENT_DATE)::timestamp - INTERVAL '2 minutes'` (corte às 23:58 do dia anterior, margem de segurança)
- Visitas registradas após 22h: aceitas, mas `data_visita = CURRENT_DATE` (não o dia que estava sendo processado)
- Bot, durante janela 22h–05h, exibe aviso: *"Sistema em manutenção — visita será registrada como amanhã"*

**Para o MVP**: simples e demonstrável. Para produção, evoluir para advisory lock no `profissional_id`.

**Teste pré-mapeado**: `tests/integration/test_batch_noite.py::test_corte_rigido_22h`

---

### G3 — Sobreposição risco + escalonamento

**Problema**: Para criança de risco não visitada por 2 dias, qual regra aplica? Penalidade -5/dia (seção 4.3) ou escalonamento +30 (seção 5.4)?

**Decisão**: **Risco sempre vence.** Hierarquia:

1. Se `grupo_risco = true` → `override_topo = true`, score_ajustado é irrelevante (mas calculado pra observabilidade: `score_original + 50` fixo, sem incremento diário)
2. Se `grupo_risco = false`:
   - 1 dia pendente → `score_ajustado = score_original + 20`
   - 2 dias → `score_ajustado = score_original + 30`
   - 3+ dias → `override_topo = true` E `score_ajustado = score_original + 40 + (dias_pendente - 3) * 10`

Penalidade -5/dia de atraso da seção 4.3 é **deletada da implementação** (conflita com o escalonamento e não agrega — está coberto pela ausência da criança).

**Teste pré-mapeado**: `tests/unit/test_motor_regras.py::test_score_ajustado_risco_vence`

---

### G4 — `grupo_risco` snapshot ou recálculo?

**Problema**: Score muda dia a dia. A flag `grupo_risco` é fotografia do dia (imutável) ou recalculada?

**Decisão**: **Recalcula no batch noturno.**

- Na geração da `lista_sugestoes` (batch manhã): `grupo_risco = score_calculado >= 40` → grava snapshot
- No batch noturno, ao mover pra `fila_reposicao`: **recalcula** com regras atuais → grava novo snapshot
- Na `lista_sugestoes` do dia seguinte: usa o `grupo_risco` da `fila_reposicao` (recalculado)

Garante que criança que virou risco entre a sugestão e o batch noturno sobe pro topo no dia seguinte.

**Teste pré-mapeado**: `tests/unit/test_motor_regras.py::test_grupo_risco_recalculado_no_batch_noite`

---

### G5 — Histórico 90 dias vs "nunca expira"

**Problema**: PRD diz "nunca expira" na tabela comparativa e "90 dias" no parágrafo seguinte. Contradição.

**Decisão**: **90 dias é o correto.** A linha "nunca expira" é erro de redação — interpretamos como "persistente entre sessões" (vs v2.0 que expirava em 30min).

Implementação:
- Job `limpeza_historico` roda diariamente às 03h (longe dos batches críticos)
- `DELETE FROM chat_history WHERE criado_em < NOW() - INTERVAL '90 days'`
- Idempotente (DELETE sem registros = no-op)
- Auditoria registra: `acao='LIMPEZA_AUTOMATICA_CHAT', metadata={"linhas_removidas": N}`

**TODO documentar no PRD v3.1**: corrigir contradição.

**Teste pré-mapeado**: `tests/integration/test_chat_history_retencao.py::test_limpeza_apos_90_dias`

---

### G6 — Idempotência do batch 22h

**Problema**: PRD diz "idempotente" mas não especifica mecanismo.

**Decisão**: `UNIQUE` constraint + `ON CONFLICT DO UPDATE`:

```sql
ALTER TABLE fila_reposicao
  ADD CONSTRAINT unique_fila_acs_crianca_origem
  UNIQUE (profissional_id, crianca_ref, data_origem);
```

No INSERT do batch:

```sql
INSERT INTO fila_reposicao (profissional_id, crianca_ref, data_origem, ...)
VALUES (...)
ON CONFLICT (profissional_id, crianca_ref, data_origem)
DO UPDATE SET
  dias_pendente = fila_reposicao.dias_pendente + 1,
  score_ajustado = EXCLUDED.score_ajustado,
  grupo_risco = EXCLUDED.grupo_risco,
  override_topo = EXCLUDED.override_topo,
  updated_at = NOW();
```

**Teste pré-mapeado**: `tests/integration/test_batch_noite_idempotencia.py::test_executar_duas_vezes_nao_duplica`

---

## 🟡 Ambiguidades resolvidas

### G7 — Display de pendências

**Decisão**: Texto dinâmico baseado em `dias_pendente`:

- `dias_pendente = 1` → `"PENDENTE DO DIA ANTERIOR"`
- `dias_pendente = 2` → `"PENDENTE HÁ 2 DIAS"`
- `dias_pendente = N (N>=3)` → `"PENDENTE HÁ N DIAS · OVERRIDE"`

Implementado em `app/llm/prompts.py::motivo_pendencia(dias)`.

**Teste**: `tests/unit/test_llm_fallback.py::test_motivo_pendencia_formatacao`

---

### G8 — Ordem dentro do bloco override

**Decisão**: `ORDER BY dias_pendente DESC, grupo_risco DESC, score_ajustado DESC, created_at ASC`

Mais antigo primeiro (mais urgente). Risco desempata. Score finaliza. `created_at ASC` é tiebreaker determinístico (FIFO pra casos iguais).

**Teste**: `tests/integration/test_batch_manha.py::test_ordem_overrides`

---

### G9 — Tamanho máximo da lista

**Decisão**: Config `LIMITE_LISTA_DIARIA = 15`. Overrides consomem do total. Se 15 overrides, lista é 100% pendência.

Mas: limite mínimo de **3 candidatos novos** garantido. Se overrides > 12, força truncamento de overrides (mantém os 12 mais críticos por `dias_pendente DESC`).

**Justificativa do mínimo de 3**: evita situação onde ACS só recebe pendências e nunca avança para novos casos.

**Teste**: `tests/unit/test_motor_priorizador.py::test_limite_15_com_minimo_3_novos`

---

### G10 — Auditoria do `/limpar_historico`

**Decisão**: Sim, comando é auditado. Mas o registro **não contém conteúdo**:

```python
auditoria.registrar(
    acao="LIMPAR_HISTORICO",
    profissional_id=profissional_id,
    metadata={
        "mensagens_apagadas": 47,
        "periodo_inicio": "2026-02-01",
        "periodo_fim": "2026-05-24"
    }
)
```

Justificativa: direito ao esquecimento preservado (conteúdo some), accountability mantida (sabemos que apagamento ocorreu).

**Teste**: `tests/integration/test_limpar_historico.py::test_apaga_conteudo_mantem_auditoria`

---

### G11 — Notificação ao gestor (gap de tabela)

**Decisão**: Adicionar tabela `gestores` (não estava no PRD):

```python
class Gestor(Base):
    id: UUID
    nome: str
    telegram_chat_id_hash: str
    equipes_ids: list[UUID]  # JSONB array
    ativo: bool
```

Throttling: 1 mensagem agregada por gestor por execução do batch. Formato:

```
📊 Equipe ESF-12 — Resumo 24/05/2026

🔴 Risco — 3 crianças não visitadas:
  • A.B.C. — 2º dia (ACS: JR)
  • D.E.F. — 1º dia (ACS: MV)
  • G.H.I. — 1º dia (ACS: JR)

🟡 Override (3+ dias):
  • J.K.L. — 4º dia (ACS: AC)

📈 Cobertura: 67% (meta 80%)
```

**Teste**: `tests/integration/test_batch_noite.py::test_notificacao_gestor_agregada`

---

### G12 — Performance < 90s/equipe (concorrência)

**Decisão MVP**: Asyncio nativo com semáforo limitando a 5 equipes concorrentes. Para 5 equipes de demo, ~10s total. Documentar como ponto de evolução pra produção:

```python
# app/schedulers/batch_manha.py
semaforo = asyncio.Semaphore(5)

async def processar_equipe(equipe_id):
    async with semaforo:
        ...

await asyncio.gather(*[processar_equipe(e) for e in equipes])
```

ADR futuro: migrar pra Celery + workers paralelos quando exceder 50 equipes.

**Teste**: não tem teste de carga no MVP (over-engineering pra demo).

---

### G13 — Vocabulário unificado

**Decisão**: Apenas `override_topo` (boolean) é usado no código. "Score override" do PRD é o mesmo conceito — apenas vocabulário inconsistente do PRD que ignoramos.

Constante em `app/motor/constants.py`:
```python
OVERRIDE_TOPO = "override_topo"  # campo único, sem aliases
```

---

## 🟢 Pontos de polimento

### G14 — Migrations versionadas

**Decisão**: Alembic com `--autogenerate`. Toda mudança de schema gera migration nomeada e versionada.

Política de naming: `YYYYMMDD_HHMM_descricao_curta.py` (ex: `20260524_1430_initial_v3_schema.py`).

---

### G15 — Claude API offline durante batch 05h

**Decisão**: Fallback determinístico em `app/llm/fallback.py`:

```python
def formatar_lista_fallback(lista: list[CandidatoSugestao]) -> str:
    """Gera mensagem Telegram sem chamar Claude API. Usa Jinja2 + motivo da regra."""
    ...
```

Trigger:
- 3 retries com backoff exponencial (1s, 2s, 4s)
- Em falha persistente: log `WARNING`, audita `acao='LLM_FALLBACK_USADO'`, usa template

**Teste**: `tests/unit/test_llm_fallback.py::test_fallback_quando_claude_api_offline`

---

### G16 — Timestamps consistentes

**Decisão**: Mixin em `app/models/base.py`:

```python
class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now()
    )
```

Aplicado em **todas as tabelas**. Trigger Postgres backup para `updated_at` em caso de UPDATE via SQL bruto.

---

### G17 — ACS de férias / inativo

**Decisão**: Flag `ativo` em `profissionais` (já no PRD).

Comportamento:
- Batch manhã: `WHERE p.ativo = true` na query de ACS — não gera lista pro ACS inativo
- Batch noite: idem — não move sugestões pra fila se ACS inativo
- Quando ACS volta (`ativo = true` novamente): no próximo batch manhã, pendências antigas já estão na `fila_reposicao` e voltam normalmente

**Teste**: `tests/integration/test_batch_manha.py::test_acs_inativo_nao_gera_lista`

---

### G18 — Métrica de cobertura

**Decisão**: Denominador = `count(lista_sugestoes WHERE data_sugestao = ontem)` (excluindo CANCELADAS).

Numerador = `count WHERE status = 'VISITADA'`.

Thresholds:
- `< 60%` → notificação ao gestor da equipe (texto: *"Cobertura X% abaixo da meta de 80%"*)
- `60-79%` → silencioso (registra em métrica, sem notificar)
- `>= 80%` → silencioso (meta atingida)

Granularidade: por equipe, não por ACS (ACS individual pode ter dia ruim por motivos válidos; equipe agregada é o nível certo).

**Teste**: `tests/integration/test_batch_noite.py::test_taxa_cobertura_abaixo_60_notifica`

---

## Resumo executivo

| Gap | Severidade | Decisão sintética |
|---|---|---|
| G1 | 🔴 | Transação atômica resolve `fila_reposicao.resolvida_em` no INSERT da visita |
| G2 | 🔴 | Corte rígido por timestamp com margem 2min; visitas tardias contam pro dia seguinte |
| G3 | 🔴 | Risco vence; penalidade -5/dia removida da implementação |
| G4 | 🔴 | `grupo_risco` recalculado no batch noturno (snapshot atualizado) |
| G5 | 🔴 | 90 dias é a regra; "nunca expira" é erro do PRD |
| G6 | 🔴 | UNIQUE constraint + ON CONFLICT DO UPDATE |
| G7 | 🟡 | Texto dinâmico por `dias_pendente` |
| G8 | 🟡 | ORDER BY dias_pendente, grupo_risco, score_ajustado, created_at |
| G9 | 🟡 | Limite 15 com mínimo 3 candidatos novos |
| G10 | 🟡 | `/limpar_historico` auditado sem conteúdo |
| G11 | 🟡 | Nova tabela `gestores`; 1 mensagem agregada por gestor |
| G12 | 🟡 | asyncio.Semaphore(5); Celery deixado pra produção |
| G13 | 🟡 | Vocabulário unificado em `override_topo` |
| G14 | 🟢 | Alembic autogenerate |
| G15 | 🟢 | Fallback Jinja2 quando Claude API falha |
| G16 | 🟢 | TimestampMixin em todos os modelos |
| G17 | 🟢 | Flag `ativo` filtra ACS inativo nos batches |
| G18 | 🟢 | Cobertura por equipe; < 60% notifica gestor |

Use este mapa quando bater alguma dúvida durante a implementação.
