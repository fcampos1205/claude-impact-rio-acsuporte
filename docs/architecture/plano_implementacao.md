# Plano de Implementação Sequencial

8 fases, ~10h de Claude Code. TDD em todas. Cada fase tem **entregáveis**, **testes pré-mapeados** (com `@pytest.mark.skip` aguardando implementação) e **critérios de aceitação** verificáveis.

## Visão geral do fluxo de cada fase

```
1. Ler skill da fase (.claude/skills/acs-fase-N-*)
2. Ler testes pré-mapeados (tests/...) — entender o que provam
3. Para cada teste skipped:
   a. Remover @pytest.mark.skip
   b. Rodar — confirmar RED (falha)
   c. Implementar mínimo necessário
   d. Rodar — confirmar GREEN
   e. Refatorar mantendo GREEN
4. Rodar make lint
5. Atualizar README da fase com comando manual de validação
6. Criar ADR se decisão de design nova surgiu
7. Marcar fase como concluída
```

---

## Fase 0 — Bootstrap e infraestrutura *(30 min)*

**Skill**: `acs-fase-bootstrap`

### Entregáveis

- `pyproject.toml` com todas as dependências
- `Dockerfile` Python 3.12 slim
- `docker-compose.yml` com `db` (postgres:16) e `app`
- `.env.example` documentado
- `Makefile` com targets canônicos
- `alembic.ini` + `alembic/env.py` configurados
- `app/config.py` (pydantic-settings)
- `app/db.py` (engine async + session factory)
- `app/main.py` (FastAPI app vazia com `/healthz`)
- `README.md` raiz com 4 comandos de setup

### Testes pré-mapeados

**`tests/unit/test_config.py`** — 4 testes:
- `test_config_carrega_de_env`
- `test_config_falha_sem_database_url`
- `test_config_usa_defaults_quando_aplicavel`
- `test_config_valida_formato_database_url`

**`tests/integration/test_db_connection.py`** — 2 testes:
- `test_engine_conecta_ao_postgres`
- `test_session_factory_cria_sessao_async`

### Critérios de aceitação

- [ ] `make up` sobe Postgres + app sem erros
- [ ] `make migrate` cria tabela `alembic_version` (sem outras tabelas ainda)
- [ ] `curl localhost:8000/healthz` retorna `{"status":"ok"}`
- [ ] `make test-unit -k test_config` → 4 passa
- [ ] `make test-integration -k test_db_connection` → 2 passa
- [ ] `make lint` → 0 erros
- [ ] `psql $DATABASE_URL -c "\dt"` mostra apenas `alembic_version`

---

## Fase 1 — Modelo de dados completo *(1h)*

**Skill**: `acs-fase-modelos`

### Entregáveis

`app/models/`:
- `base.py` — Declarative base + TimestampMixin
- `profissional.py`
- `crianca.py`
- `visita.py`
- `gestor.py` *(novo — G11)*
- `auditoria.py`
- `chat_history.py`
- `lista_sugestoes.py`
- `fila_reposicao.py`

`app/crypto.py` — Wrapper Fernet com `encrypt(s) -> bytes` e `decrypt(b) -> str`.

Migration Alembic: `alembic/versions/20260524_NNNN_initial_v3_schema.py` gerada via `alembic revision --autogenerate -m "initial v3.0 schema"`.

### Constraints e índices obrigatórios

```sql
-- lista_sugestoes
UNIQUE (profissional_id, crianca_ref, data_sugestao);
INDEX (profissional_id, data_sugestao, status);

-- fila_reposicao
UNIQUE (profissional_id, crianca_ref, data_origem);
INDEX (profissional_id) WHERE resolvida_em IS NULL;  -- partial

-- chat_history
INDEX (profissional_id, criado_em DESC);
INDEX (criado_em) WHERE criado_em < NOW();  -- pra cleanup eficiente
```

### Testes pré-mapeados

**`tests/unit/test_crypto.py`** — 5 testes:
- `test_encrypt_retorna_bytes`
- `test_decrypt_recupera_texto_original`
- `test_decrypt_falha_com_chave_errada`
- `test_encrypt_mesma_string_gera_bytes_diferentes` (timestamp interno do Fernet)
- `test_decrypt_com_payload_corrompido_levanta_erro`

**`tests/integration/test_models_constraints.py`** — 12 testes:
- `test_profissional_criar_e_recuperar`
- `test_lista_sugestoes_unique_constraint`
- `test_fila_reposicao_unique_constraint`
- `test_chat_history_persiste_criptografado`
- `test_chat_history_descriptografia_funcional`
- `test_timestamps_created_at_setado_automaticamente`
- `test_timestamps_updated_at_atualiza_em_update`
- `test_visita_relacao_profissional_crianca`
- `test_gestor_pode_ter_multiplas_equipes`
- `test_auditoria_grava_metadata_jsonb`
- `test_fila_reposicao_partial_index_resolvida_em_null`
- `test_cascade_delete_nao_remove_chat_history` (chat persiste mesmo se ACS inativado)

### Critérios de aceitação

- [ ] `make migrate` aplica migration sem erro
- [ ] `psql -c "\dt"` mostra 8 tabelas
- [ ] `psql -c "\d+ lista_sugestoes"` mostra UNIQUE constraint e índice composto
- [ ] `make test-unit tests/unit/test_crypto.py` → 5 passa
- [ ] `make test-integration tests/integration/test_models_constraints.py` → 12 passa
- [ ] `make lint` → 0 erros

---

## Fase 2 — Seed de dados realistas *(45 min)*

**Skill**: `acs-fase-seed`

### Entregáveis

`scripts/seed.py`:
- Baixa parquets do dataset hackathon (Google Drive URLs do README)
- Filtra `pacientes` para `faixa_etaria = '0-6'`
- Cria 1 equipe + 3 ACS + 1 gestor (dados sintéticos pra demo)
- Distribui ~150 crianças entre os 3 ACS
- Gera ~30 dias de histórico de `visitas` (realista)
- Marca propositalmente 5 crianças como alto risco (vacinação atrasada, etc.)

`scripts/limpar_db.py` — drop all tables + recria (útil em dev).

### Testes pré-mapeados

**`tests/integration/test_seed.py`** — 6 testes:
- `test_seed_popula_equipe_3_acs_1_gestor`
- `test_seed_distribui_criancas_entre_acs`
- `test_seed_gera_historico_visitas_30_dias`
- `test_seed_marca_5_criancas_alto_risco`
- `test_seed_idempotente_segunda_execucao_nao_duplica`
- `test_seed_respeita_faixa_etaria_0_6`

### Critérios de aceitação

- [ ] `make seed` retorna sem erro em < 30s
- [ ] `psql -c "SELECT count(*) FROM criancas"` retorna ~150
- [ ] `psql -c "SELECT count(*) FROM profissionais WHERE ativo=true"` retorna 3
- [ ] `make seed` 2ª vez não duplica (idempotente)
- [ ] `make test-integration tests/integration/test_seed.py` → 6 passa

---

## Fase 3 — Motor de priorização *(2h)*

**Skill**: `acs-fase-motor`

### Entregáveis

`app/motor/regras.py` — funções puras:
- `score_vacinacao_atrasada(crianca, hoje) -> tuple[int, str]`
- `score_consulta_pendente(crianca, eventos_clinicos, hoje) -> tuple[int, str]`
- `score_tempo_sem_visita(crianca, ultima_visita, hoje) -> tuple[int, str]`
- `score_vulnerabilidade(crianca) -> tuple[int, str]`
- `calcular_score_total(crianca, contexto) -> ScoreResult`
- `determinar_grupo_risco(score: int) -> bool` (threshold 40)

`app/motor/deduplicacao.py`:
- `obter_visitadas_no_ciclo(profissional_id, ciclo_dias=30) -> set[UUID]`
- `filtrar_candidatos(candidatos, visitadas) -> list`

`app/motor/priorizador.py`:
- `gerar_lista(profissional_id, data=today) -> ListaPriorizada` — pipeline completo

### Testes pré-mapeados

**`tests/unit/test_motor_regras.py`** — 18 testes:

```python
# score_vacinacao_atrasada
test_vacinacao_em_dia_score_zero
test_vacinacao_atrasada_30_dias_score_20
test_vacinacao_atrasada_60_dias_score_35
test_vacinacao_atrasada_acima_threshold_grupo_risco

# score_consulta_pendente
test_consulta_em_dia_score_zero
test_consulta_atrasada_30_dias_score_15
test_consulta_atrasada_com_evento_urgencia_recente_score_alto

# score_tempo_sem_visita
test_sem_visita_ha_15_dias_score_zero
test_sem_visita_ha_38_dias_score_10
test_sem_visita_ha_90_dias_score_25

# score_vulnerabilidade
test_situacao_vulnerabilidade_true_bonus
test_situacao_vulnerabilidade_false_zero

# Integração das regras
test_calcular_score_total_soma_componentes
test_score_total_com_motivos_concatenados

# Grupo de risco
test_score_39_nao_eh_risco
test_score_40_eh_risco
test_score_100_eh_risco

# G3 — risco vence
test_score_ajustado_risco_vence

# G4 — recálculo
test_grupo_risco_recalculado_no_batch_noite
```

**`tests/unit/test_motor_deduplicacao.py`** — 5 testes:
- `test_obter_visitadas_no_ciclo_30_dias`
- `test_filtrar_candidatos_remove_visitadas`
- `test_filtrar_mantem_nao_visitadas`
- `test_filtrar_ciclo_reinicia_apos_30_dias`
- `test_ciclo_inicia_na_primeira_sugestao_do_mes`

**`tests/unit/test_motor_priorizador.py`** — 8 testes:
- `test_gerar_lista_retorna_max_15_itens`
- `test_overrides_primeiro_candidatos_novos_depois`
- `test_limite_15_com_minimo_3_novos` *(G9)*
- `test_ordem_dentro_overrides_dias_pendente_desc` *(G8)*
- `test_dedupe_aplicado_antes_do_ranking`
- `test_lista_vazia_quando_acs_sem_criancas`
- `test_acs_inativo_retorna_lista_vazia` *(G17)*
- `test_truncamento_quando_muitos_overrides`

### Critérios de aceitação

- [ ] `make test-unit tests/unit/test_motor_regras.py` → 18 passa
- [ ] `make test-unit tests/unit/test_motor_deduplicacao.py` → 5 passa
- [ ] `make test-unit tests/unit/test_motor_priorizador.py` → 8 passa
- [ ] `python -m app.motor.priorizador --acs <uuid>` printa lista ranqueada em < 2s
- [ ] `make lint` → 0 erros

---

## Fase 4 — Integração Claude API *(1h)*

**Skill**: `acs-fase-llm`

### Entregáveis

`app/llm/cliente.py`:
- `class ClaudeClient` com `async chamar(prompt, max_retries=3, backoff_base=1.0)`
- Retry exponencial; depois de N falhas, levanta `LLMUnavailableError`

`app/llm/prompts.py`:
- `SYSTEM_PROMPT_LISTA` — system prompt pra formatação
- `montar_prompt_usuario(lista_priorizada) -> str`
- `motivo_pendencia(dias: int) -> str` *(G7)*

`app/llm/fallback.py`:
- `formatar_lista_fallback(lista) -> str` — template Jinja2 determinístico

`app/llm/gerador_lista.py`:
- `async gerar_mensagem_telegram(lista) -> str` — tenta Claude, fallback se falhar

### Testes pré-mapeados

**`tests/unit/test_llm_prompts.py`** — 6 testes:
- `test_motivo_pendencia_1_dia`
- `test_motivo_pendencia_2_dias`
- `test_motivo_pendencia_5_dias_com_override`
- `test_montar_prompt_inclui_todos_candidatos`
- `test_system_prompt_contem_instrucoes_lgpd`
- `test_prompt_nao_vaza_dados_pessoais_completos` (só iniciais)

**`tests/unit/test_llm_fallback.py`** — 5 testes:
- `test_fallback_gera_mensagem_valida`
- `test_fallback_formato_telegram_markdown`
- `test_fallback_inclui_motivo_de_cada_crianca`
- `test_fallback_quando_lista_vazia`
- `test_fallback_quando_claude_api_offline` (mock httpx)

**`tests/integration/test_llm_cliente.py`** — 3 testes (com mock):
- `test_cliente_retry_3_vezes_em_500`
- `test_cliente_levanta_unavailable_apos_max_retries`
- `test_cliente_sucesso_em_segunda_tentativa`

### Critérios de aceitação

- [ ] `make test-unit tests/unit/test_llm_prompts.py` → 6 passa
- [ ] `make test-unit tests/unit/test_llm_fallback.py` → 5 passa
- [ ] `make test-integration tests/integration/test_llm_cliente.py` → 3 passa
- [ ] `python -m scripts.demo_llm` (script auxiliar) gera mensagem realista em < 3s
- [ ] Teste manual com `ANTHROPIC_API_KEY` inválida → fallback ativa, auditoria registra
- [ ] `make lint` → 0 erros

---

## Fase 5 — Bot Telegram + FSM *(2h)*

**Skill**: `acs-fase-bot`

### Entregáveis

`app/bot/webhook.py`:
- Endpoint FastAPI `POST /telegram/webhook`
- Valida payload Telegram

`app/bot/auth.py`:
- `async resolver_acs(chat_id: int) -> Profissional | None` — hash + lookup

`app/bot/fsm.py` — Estados Ficha Primeira Infância:
- `S0_INICIO`
- `S1_SELECAO_CRIANCA` (ACS escolheu # da lista)
- `S2_RESPONSAVEL_PRESENTE`
- `S3_VACINACAO_EM_DIA`
- `S4_CONSULTAS_EM_DIA`
- `S5_ALEITAMENTO`
- `S6_DESENVOLVIMENTO`
- `S7_OBSERVACOES_LIVRES`
- `S8_ENCERRAMENTO`

`app/bot/handlers.py` — handler async por estado.

`app/bot/comandos.py`:
- `/start` — onboarding
- `/lista` — re-exibe lista do dia
- `/limpar_historico` — apaga `chat_history` do ACS *(G10)*

`app/bot/historico.py`:
- `async carregar_contexto(profissional_id, n_ultimas=20) -> list[Message]` — descriptografa
- `async salvar_mensagem(profissional_id, role, content, estado_fsm)` — criptografa

### Testes pré-mapeados

**`tests/unit/test_bot_fsm.py`** — 12 testes:
- `test_fsm_estado_inicial_s0`
- `test_fsm_transicao_s0_para_s1_com_selecao`
- `test_fsm_s1_para_s2_com_responsavel_presente`
- `test_fsm_s2_nao_pode_voltar_a_s0`
- `test_fsm_serializa_estado_em_string`
- `test_fsm_restaura_estado_de_string`
- `test_fsm_s8_finaliza_e_grava_visita`
- `test_fsm_input_invalido_nao_transita`
- `test_fsm_pode_cancelar_em_qualquer_estado`
- `test_fsm_perguntas_de_alerta_no_estado_s5`
- `test_fsm_ramo_alternativo_responsavel_ausente`
- `test_fsm_timeout_inatividade_retorna_s0`

**`tests/integration/test_bot_historico.py`** — 5 testes:
- `test_salvar_mensagem_criptografa_conteudo`
- `test_carregar_contexto_descriptografa`
- `test_carregar_contexto_respeita_ordem_temporal`
- `test_carregar_contexto_limita_n_ultimas`
- `test_carregar_contexto_apos_limpar_retorna_vazio`

**`tests/integration/test_limpar_historico.py`** — 4 testes:
- `test_limpar_historico_apaga_mensagens` *(G10)*
- `test_limpar_historico_mantem_profissional_id`
- `test_limpar_historico_registra_auditoria_sem_conteudo`
- `test_limpar_historico_idempotente`

**`tests/integration/test_bot_webhook.py`** — 4 testes:
- `test_webhook_recebe_payload_telegram_valido`
- `test_webhook_recusa_payload_invalido`
- `test_webhook_resolve_acs_por_chat_id`
- `test_webhook_rejeita_chat_id_desconhecido`

### Critérios de aceitação

- [ ] `make test-unit tests/unit/test_bot_fsm.py` → 12 passa
- [ ] `make test-integration tests/integration/test_bot_historico.py` → 5 passa
- [ ] `make test-integration tests/integration/test_limpar_historico.py` → 4 passa
- [ ] `make test-integration tests/integration/test_bot_webhook.py` → 4 passa
- [ ] Teste manual: enviar mensagem via Telegram real → bot responde com lista
- [ ] Teste manual: `/limpar_historico` apaga conteúdo, mas auditoria registra
- [ ] `make lint` → 0 erros

---

## Fase 6 — Batches agendados *(1h30)*

**Skill**: `acs-fase-batches`

### Entregáveis

`app/schedulers/scheduler.py`:
- Bootstrap do AsyncIOScheduler
- Registra 3 jobs: `batch_manha` (05h), `batch_noite` (22h), `limpeza_historico` (03h)

`app/schedulers/batch_manha.py`:
- Para cada equipe (com `Semaphore(5)`):
  - Para cada ACS ativo:
    - Chama `motor.priorizador.gerar_lista()`
    - Chama `llm.gerador_lista.gerar_mensagem_telegram()`
    - INSERT em `lista_sugestoes` com `status='SUGERIDA'`
- Job auxiliar 07h: envia listas pendentes via Telegram

`app/schedulers/batch_noite.py`:
1. SELECT sugestões SUGERIDAS com corte 2min *(G2)*
2. UPDATE para NAO_VISITADA
3. Calcula `score_ajustado` com regras 5.4 *(G3 — risco vence)*
4. INSERT ON CONFLICT DO UPDATE em `fila_reposicao` *(G6)*
5. Para cada gestor: agrega notificações *(G11)*
6. Calcula taxa cobertura por equipe *(G18)*
7. Notifica gestores se cobertura < 60%
8. Audita execução

`app/schedulers/limpeza_historico.py`:
- DELETE chat_history > 90 dias *(G5)*
- Audita

`migrations/triggers.sql`:
- Trigger que mantém `updated_at` atualizado

### Testes pré-mapeados

**`tests/integration/test_batch_manha.py`** — 8 testes:
- `test_batch_manha_gera_lista_para_cada_acs_ativo` *(G17)*
- `test_batch_manha_pula_acs_inativo` *(G17)*
- `test_batch_manha_overrides_aparecem_primeiro` *(G8)*
- `test_batch_manha_dedupe_aplicado` *(G1)*
- `test_batch_manha_chama_llm_e_usa_fallback_em_falha`
- `test_batch_manha_respeita_limite_15` *(G9)*
- `test_batch_manha_idempotente_no_mesmo_dia`
- `test_batch_manha_persiste_status_sugerida`

**`tests/integration/test_batch_noite.py`** — 10 testes:
- `test_batch_noite_move_sugerida_para_nao_visitada`
- `test_batch_noite_corte_rigido_22h` *(G2)*
- `test_batch_noite_calcula_score_ajustado`
- `test_batch_noite_risco_seta_override_topo` *(G3)*
- `test_batch_noite_3_dias_pendentes_seta_override` *(G3)*
- `test_batch_noite_recalcula_grupo_risco` *(G4)*
- `test_batch_noite_notificacao_gestor_agregada` *(G11)*
- `test_batch_noite_visita_resolve_fila` *(G1)*
- `test_batch_noite_taxa_cobertura_abaixo_60_notifica` *(G18)*
- `test_batch_noite_audita_execucao`

**`tests/integration/test_batch_noite_idempotencia.py`** — 4 testes:
- `test_executar_duas_vezes_nao_duplica` *(G6)*
- `test_executar_apos_falha_parcial_recupera`
- `test_dias_pendente_incrementa_a_cada_execucao`
- `test_score_ajustado_atualiza_em_reexecucao`

**`tests/integration/test_chat_history_retencao.py`** — 3 testes:
- `test_limpeza_apos_90_dias` *(G5)*
- `test_limpeza_nao_remove_mensagens_recentes`
- `test_limpeza_audita_quantidade_removida`

### Critérios de aceitação

- [ ] `make test-integration tests/integration/test_batch_manha.py` → 8 passa
- [ ] `make test-integration tests/integration/test_batch_noite.py` → 10 passa
- [ ] `make test-integration tests/integration/test_batch_noite_idempotencia.py` → 4 passa
- [ ] `make test-integration tests/integration/test_chat_history_retencao.py` → 3 passa
- [ ] `python -m app.schedulers.batch_noite` manualmente: roda em < 10s, idempotente
- [ ] `python -m app.schedulers.batch_manha` manualmente: gera listas pros 3 ACS
- [ ] `make lint` → 0 erros

---

## Fase 7 — Demo end-to-end + observabilidade *(1h)*

**Skill**: `acs-fase-demo`

### Entregáveis

`scripts/demo.py`:
- Cenário pré-roteirizado pra pitch:
  1. Reset DB + seed
  2. Roda batch 05h → mostra lista pros 3 ACS
  3. Simula ACS-1 visitando 8 das 15 crianças (chama FSM via API direta)
  4. Roda batch 22h → mostra 7 indo pra fila_reposicao, com 2 críticas em override
  5. Roda batch 05h do dia+1 → mostra lista nova com pendentes no topo
  6. Imprime tabela final estilo PRD seção 8

`app/observabilidade.py`:
- `/metrics` Prometheus-compatible:
  - `acs_sugestoes_total` (counter, por status)
  - `acs_visitas_total` (counter)
  - `acs_fila_reposicao_ativa` (gauge)
  - `acs_taxa_cobertura` (gauge, por equipe)
  - `acs_llm_fallback_total` (counter)
  - `acs_batch_duration_seconds` (histogram)
- `/healthz` retorna `{"status": "ok", "db": "connected", "scheduler": "running"}`

### Testes pré-mapeados

**`tests/e2e/test_ciclo_diario.py`** — 4 testes:
- `test_ciclo_completo_dia_1` — seed → batch_manha → visitas → batch_noite
- `test_ciclo_dia_2_pendentes_no_topo` *(continuação do dia 1)*
- `test_taxa_cobertura_calculada_corretamente`
- `test_metricas_prometheus_atualizadas`

**`tests/e2e/test_pendentes_no_topo.py`** — 3 testes:
- `test_pendente_de_risco_aparece_em_primeiro`
- `test_pendente_3_dias_override_independente_de_risco`
- `test_ordenacao_overrides_dias_pendente_desc`

**`tests/e2e/test_escalonamento_risco.py`** — 3 testes:
- `test_risco_nao_visitado_1_dia_override_topo`
- `test_sem_risco_2_dias_score_30_sem_override`
- `test_sem_risco_3_dias_override_ativado`

### Critérios de aceitação

- [ ] `make test-e2e` → 10 testes passam em < 60s
- [ ] `make demo` roda cenário completo em < 60s, imprime 4 etapas claras
- [ ] `curl localhost:8000/metrics` retorna formato Prometheus válido
- [ ] `curl localhost:8000/healthz` retorna status ok
- [ ] README atualizado com instruções de pitch (passo-a-passo pra demo)
- [ ] `make lint` → 0 erros

---

## Visão consolidada — testes totais por fase

| Fase | Unit | Integration | E2E | Total |
|---|---|---|---|---|
| 0 | 4 | 2 | 0 | 6 |
| 1 | 5 | 12 | 0 | 17 |
| 2 | 0 | 6 | 0 | 6 |
| 3 | 31 | 0 | 0 | 31 |
| 4 | 11 | 3 | 0 | 14 |
| 5 | 12 | 13 | 0 | 25 |
| 6 | 0 | 25 | 0 | 25 |
| 7 | 0 | 0 | 10 | 10 |
| **Total** | **63** | **61** | **10** | **134** |

134 testes pré-mapeados. Quando todos passarem, o MVP está completo.

## Ordem dependencial

```
Fase 0 ─► Fase 1 ─► Fase 2 ─► Fase 3 ─► Fase 4 ─► Fase 5 ─► Fase 6 ─► Fase 7
                              ▲                                 │
                              └─────────────────────────────────┘
                              (Fase 6 depende do motor da Fase 3)
```

Fases 3, 4, 5 podem ser feitas em paralelo se houver mais de uma pessoa (mas pra Claude Code solo, ordem sequencial é mais segura).
