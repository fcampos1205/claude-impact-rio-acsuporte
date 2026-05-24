# PRD — ACS Primeira Infância v3.0

**Histórico de chat por ACS · Deduplicação · Fila de reposição noturna**
Claude Impact Lab 2026 — 24 mai 2026 — Rio de Janeiro

---

## 1. Contexto e objetivo

A v3.0 incorpora três mecanismos novos sobre a base da v2.0: histórico de conversas persistente e único por ACS, deduplicação de sugestões para não repetir pacientes já visitados no mesmo ciclo, e fila de reposição noturna que reintroduz automaticamente pacientes não visitados no dia — com escalonamento de prioridade para grupos de risco.

### Novidades da v3.0 em relação a v2.0

1. **Histórico de chat único por ACS**: cada profissional tem contexto persistente entre sessões
2. **Deduplicação de sugestões**: pacientes já visitados não reaparecem na lista até o próximo ciclo
3. **Fila de reposição noturna**: não visitados voltam à fila; grupo de risco sobe ao topo do dia seguinte

## 2. Mudanças em relação a v2.0

| Componente | v2.0 | v3.0 (esta versão) |
|---|---|---|
| Histórico de chat | Sessão em memória · expirava em 30 min | **Persistente no banco · único por ACS · retenção 90d** |
| Sugestões de visita | Sem controle de duplicatas | **Deduplicação: paciente visitado sai da fila até próximo ciclo** |
| Fim do dia | Não tratado | **Batch 22h: verifica visitados · reintroduz não visitados na fila** |
| Grupo de risco não visitado | Não tratado | **Score override: entrada direta no topo da lista do dia seguinte** |
| Nova tabela de banco | Nenhuma adicional | **chat_history · lista_sugestoes · fila_reposicao** |
| Canal · FSM · Motor · LGPD | Conforme v2.0 | Inalterados — herdam v2.0 |

## 3. Histórico de chat persistente por ACS

### 3.1 Modelo de dados

Uma nova tabela `chat_history` armazena o histórico de mensagens de cada ACS de forma persistente e criptografada. Cada linha representa uma mensagem (ACS ou bot) vinculada ao `profissional_id` — nunca ao `telegram_chat_id` bruto.

| Coluna | Tipo | Descrição |
|---|---|---|
| id | UUID | Identificador único da mensagem |
| profissional_id | UUID | Vincula ao ACS — nunca o chat_id Telegram |
| role | ENUM | `user` (ACS) ou `assistant` (bot) |
| content_enc | TEXT | Conteúdo da mensagem criptografado AES-256 |
| session_token | UUID | Agrupa mensagens da mesma sessão de coleta |
| estado_fsm | VARCHAR | Estado da FSM no momento da mensagem (ex: `S7_CONSULTAS`) |
| criado_em | TIMESTAMP | Data e hora UTC da mensagem |

### 3.2 Comportamento do histórico

- O histórico é carregado ao iniciar qualquer sessão autenticada do ACS
- O bot usa o histórico para personalizar a abertura: *"Olá! Ontem você visitou 3 crianças. Quer continuar com as pendentes?"*
- O histórico de mensagens é separado do histórico de visitas — são tabelas distintas com propósitos diferentes
- Retenção do histórico de chat: 90 dias corridos — após esse prazo, mensagens são descartadas automaticamente (LGPD art. 15)
- O ACS pode solicitar `/limpar_historico` a qualquer momento — o conteúdo é apagado mas o vínculo `profissional_id` permanece

**LGPD — histórico de chat:** O histórico contém dados sensíveis de saúde (menções a condições clínicas das crianças). Retenção limitada a 90 dias · criptografia AES-256 · acesso restrito ao próprio ACS e ao administrador da unidade. O direito de exclusão (art. 18, VI) é atendido pelo comando `/limpar_historico`.

## 4. Deduplicação de sugestões de visita

### 4.1 Problema que resolve

Sem deduplicação, o motor poderia sugerir a mesma criança em dias consecutivos mesmo após uma visita bem-sucedida, gerando re-trabalho para o ACS e distorcendo as métricas de cobertura. A deduplicação garante que cada criança apareça na lista apenas uma vez por ciclo de visitas.

### 4.2 Tabela `lista_sugestoes`

| Coluna | Tipo | Descrição |
|---|---|---|
| id | UUID | Identificador único do registro |
| profissional_id | UUID | ACS que recebeu a sugestão |
| crianca_ref | UUID | Referência interna da criança sugerida |
| data_sugestao | DATE | Data em que a sugestão foi enviada ao ACS |
| posicao_lista | INT | Posição na lista do dia (1, 2, 3...) |
| status | ENUM | `SUGERIDA` · `VISITADA` · `NAO_VISITADA` · `CANCELADA` |
| score_no_dia | INT | Score calculado pelo motor no dia da sugestão |
| grupo_risco | BOOLEAN | True se score >= 40 no momento da sugestão |
| atualizado_em | TIMESTAMP | Última atualização do status |

### 4.3 Regra de deduplicação no motor

Ao gerar a lista diária (batch 05h), o motor aplica o seguinte filtro antes de ranquear:

- Busca em `lista_sugestoes` todos os `crianca_ref` com status `VISITADA` para o `profissional_id` no ciclo atual
- Remove esses `crianca_ref` do conjunto candidato antes de calcular o ranking
- Crianças com status `NAO_VISITADA` são tratadas pela fila de reposição (seção 5) — entram com score ajustado, não como candidatas novas
- O ciclo de deduplicação se reinicia a cada 30 dias corridos por `profissional_id` — garantindo que crianças de baixo risco sem visita há mais de um mês voltem à lista normal

**Definição de ciclo de visitas:** Ciclo = janela de 30 dias corridos a partir da primeira sugestão do ACS no mês. Dentro do ciclo: criança visitada não reaparece na lista até o ciclo seguinte. Criança `NAO_VISITADA` com `grupo_risco = true`: tratada pela fila de reposição (seção 5). Criança `NAO_VISITADA` sem risco: volta ao pool normal com penalidade de score -5 pts/dia de atraso.

## 5. Fila de reposição noturna

### 5.1 Visão geral do processo

Um segundo batch Python roda diariamente às 22h. Ele verifica quais crianças sugeridas no dia não foram visitadas (status `SUGERIDA` ainda ativo após as 21h59) e as reintroduz na fila de prioridade com lógica de escalonamento de risco.

### 5.2 Tabela `fila_reposicao`

| Coluna | Tipo | Descrição |
|---|---|---|
| id | UUID | Identificador único |
| profissional_id | UUID | ACS responsável pela criança |
| crianca_ref | UUID | Criança que não foi visitada |
| data_origem | DATE | Data do dia em que não foi visitada |
| score_original | INT | Score que tinha no dia da sugestão perdida |
| score_ajustado | INT | Score recalculado com bonus de urgência (+20 base, +10 por dia adicional) |
| grupo_risco | BOOLEAN | Determina posicionamento: topo (true) ou fila normal ajustada (false) |
| override_topo | BOOLEAN | True = entra antes de qualquer candidato novo na lista do dia seguinte |
| dias_pendente | INT | Contador de dias consecutivos sem visita (incrementado a cada batch noturno) |
| resolvida_em | TIMESTAMP | Preenchido quando a visita é finalmente registrada |

### 5.3 Lógica do batch noturno (22h)

Quatro passos sequenciais:

1. **Identificar não visitadas**: `SELECT * FROM lista_sugestoes WHERE data_sugestao = hoje AND status = 'SUGERIDA'`
2. **Atualizar status**: `UPDATE lista_sugestoes SET status = 'NAO_VISITADA', atualizado_em = NOW()`
3. **Calcular score ajustado** e inserir/atualizar `fila_reposicao`
4. **Marcar `override_topo = true`** para todas com `grupo_risco = true`

### 5.4 Regras de escalonamento de prioridade

| Situação | Override | Comportamento no dia seguinte |
|---|---|---|
| Não visitada + `grupo_risco = true` | **TOPO** | Entra antes de todos os candidatos novos · posição 1, 2... até esgotar reposições críticas |
| Não visitada + `grupo_risco = false` + 1 dia pendente | **NÃO** | Volta ao pool com `score_ajustado = score_original + 20` (prioridade elevada mas não override) |
| Não visitada + `grupo_risco = false` + 2 dias pendentes | **NÃO** | `score_ajustado = score_original + 30` · notificação ao gestor da equipe |
| Não visitada + `grupo_risco = false` + 3+ dias pendentes | **TOPO** | Independente do risco, passa a `override_topo = true` · alerta ao gestor |

**Comportamento do topo da lista:** O motor gera a lista em duas partes: primeiro os overrides de topo (`fila_reposicao` onde `override_topo = true`), depois os candidatos novos ranqueados por score. Isso garante que crianças críticas sejam sempre visitadas antes de qualquer nova sugestão ser processada. O ACS vê claramente o motivo: *"(PENDENTE DO DIA ANTERIOR)"*.

## 6. Modelo de dados completo — v3.0

| Tabela | Propósito e novidades v3.0 |
|---|---|
| profissionais | Cadastro de ACS · telegram_chat_id hash · ativo · inalterado |
| criancas | Cadastro pseudonimizado 0-6 anos · inalterado |
| visitas | Registros de visita com dados FSM criptografados · inalterado |
| auditoria | Log LGPD de todas as ações · inalterado |
| **chat_history** | NOVO — Histórico de mensagens por ACS · AES-256 · retenção 90 dias |
| **lista_sugestoes** | NOVO — Controle de sugestões diárias por ACS · status de visita · deduplicação |
| **fila_reposicao** | NOVO — Crianças não visitadas · score ajustado · override de topo · dias pendente |

## 7. Ciclo operacional diário — visão geral

| Horário | Processo | O que acontece |
|---|---|---|
| **05h00** | Batch de priorização | 1. Lê `fila_reposicao` (overrides de topo) · 2. Gera candidatos novos sem duplicatas · 3. Claude API ordena e formata · 4. Grava `lista_sugestoes` com status SUGERIDA |
| **07h00** | Envio da lista | Bot envia lista ao ACS via Telegram · pendentes do dia anterior aparecem no topo marcados como *"(PENDENTE DO DIA ANTERIOR)"* |
| **07h–21h** | Operação de campo | ACS visita crianças · registra via FSM · cada registro atualiza `lista_sugestoes` para status `VISITADA` e insere em `visitas` |
| **21h59** | Fechamento do dia | Janela de registro encerra · visitas registradas após esse horário contam para o dia seguinte |
| **22h00** | Batch noturno | 1. Identifica `NAO_VISITADAS` · 2. Atualiza status em `lista_sugestoes` · 3. Calcula `score_ajustado` · 4. Seta `override_topo` para grupos de risco · 5. Notifica gestor se `dias_pendente >= 2` |
| **22h–05h** | Janela off | Sistema em modo de leitura · sem notificações ao ACS · manutenção e backup |

## 8. Output — lista do dia com reposição

O formato da lista é idêntico à v2.0, com a adição de uma seção de pendências no topo quando existirem overrides. Enviada via Telegram às 07h.

### Exemplo de lista com reposição noturna

| # | Criança | Risco | Motivo | Obs. |
|---|---|---|---|---|
| **1** | L.M.S., 4m | **CRÍTICO** | PENDENTE DO DIA ANTERIOR · sinais de risco não atendidos | 2º dia consecutivo sem visita · gestor notificado |
| **2** | F.K.A., 8m | **CRÍTICO** | PENDENTE DO DIA ANTERIOR · insegurança alimentar | Grupo de risco · override de topo ativo |
| **3** | J.O.R., 2a | **Alto** | Vacinação atrasada · sem visita há 38 dias | Candidato novo · não pendente |
| **4** | A.B.C., 5a | **Médio** | Consulta em atraso há 30 dias | Candidato novo · primeira sugestão |

## 9. Notificações automáticas ao gestor da equipe

O batch noturno aciona notificações Telegram ao gestor da unidade nos seguintes casos:

| Gatilho | Conteúdo da notificação |
|---|---|
| Criança de risco não visitada por 1 dia | *"[Iniciais] não foi visitada hoje. Grupo de risco. Entrada no topo da lista de amanhã."* |
| Qualquer criança não visitada por 2 dias | *"[Iniciais] está há 2 dias sem visita. Verificar com [ACS iniciais]."* |
| Qualquer criança não visitada por 3+ dias | *"ATENÇÃO: [Iniciais] há 3+ dias sem visita. Override ativo. Avaliar realocação."* |
| Taxa de cobertura < 60% no dia | *"Equipe [X] visitou X% das crianças sugeridas hoje. Média esperada: 80%."* |

## 10. Requisitos não-funcionais e conformidade LGPD

| Requisito | Especificação v3.0 |
|---|---|
| Histórico de chat (LGPD) | AES-256 · retenção 90 dias · `/limpar_historico` disponível · acesso restrito por `profissional_id` |
| Deduplicação | Ciclo de 30 dias por ACS · índice composto (`profissional_id`, `crianca_ref`, `data`) para performance |
| Batch noturno (22h) | Idempotente · falhas registradas em auditoria · reexecutável sem duplicar `fila_reposicao` |
| Batch manhã (05h) | Ordem determinística: overrides de topo primeiro · candidatos novos por score decrescente |
| Performance | Geração da lista completa (reposição + novos) < 90s por equipe · resposta bot < 2s |
| Disponibilidade | 99,5% uptime · se batch 05h falhar, lista do dia anterior é reentregue com aviso |

## 11. Fora do escopo (v3.0)

- Outras fichas (Crônico, Gestante, TB, Ficha A) — previstas para v4.0
- Realocação automática de crianças entre ACS da mesma equipe
- Painel de gestão com métricas históricas de cobertura
- Integração direta com prontuário eletrônico (PE) da SMS-Rio
- Notificação ao responsável legal da criança
