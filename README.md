# ACS — Inteligência no Território

**Claude Impact Lab Rio 2026** · Desafio Saúde Pública · Prefeitura do Rio \+ Anthropic

Sistema que entrega duas coisas ao Agente Comunitário de Saúde, hoje sem ferramenta digital:

1. **De manhã** — a lista priorizada de pacientes a visitar, com motivo, lacuna de cuidado e o que verificar na visita, em linguagem clara e sem jargão clínico.  
2. **Durante o dia** — uma forma simples e guiada de registrar a visita pelo celular (Telegram), eliminando a ficha em papel que hoje precisa ser digitada no sistema no fim do dia.

---

## Identificação

| Campo | Valor |
| :---- | :---- |
| **Nome da equipe** | `[PREENCHER]` |
| **Membros** | `[PREENCHER]` |
| **Tema** | Saúde Pública — Inteligência no Território |
| **Repositório** | `[PREENCHER]` |
| **Vídeo demo (60s)** | `[PREENCHER]` |
| **Aplicação publicada** | `[PREENCHER ou "ver vídeo demo"]` |

---

## A solução em uma frase

Um ACS abre o celular **às 5h da manhã** e recebe a lista do dia já priorizada por risco, com o que observar em cada visita. Ao registrar cada visita, ele conversa com o bot — sem papel, sem digitação no fim do dia. Toda a inteligência roda em um motor que **nunca viu** nome, CPF ou endereço de ninguém.

---

## Por que isso importa

Os 6.200 ACS do Rio visitam 4,5 milhões de moradores. Hoje:

- **Não recebem lista priorizada.** Decidem quem visitar por memória, anotações em papel e conhecimento informal do território.  
- **Preenchem fichas em papel.** Cada visita gera uma ficha física que, no fim do dia ou da semana, precisa ser digitada manualmente no sistema da SMS-Rio — retrabalho, atraso e erro de transcrição.  
- **Urgências, internações e agendamentos ficam invisíveis em campo.** Os dados existem, mas não chegam à mão de quem está visitando.

Análise dos 4 datasets fornecidos pela SMS-Rio (97.938 pacientes, 159.599 visitas, 100.503 eventos clínicos, 49 equipes):

| Achado | Por que importa |
| :---- | :---- |
| **48.838 pacientes (50%) nunca visitados** | A lacuna não é exceção, é o caso médio |
| **57 crianças 0–6 anos foram à urgência sem nunca terem sido visitadas** | A criança chegou ao serviço sem que a atenção primária soubesse de sua existência |
| **28.835 urgências/internações vs 71.668 agendamentos** | Sistema reativo (1:2,5) — ACS bem priorizado inverte essa relação |
| **Picos de urgência em março, junho e dezembro** | Sazonalidade respiratória explícita; ativa ajuste automático no motor |

**Por que o MVP foca em 0–6 anos:** maior retorno epidemiológico no curto prazo e alinhamento direto com a meta da cidade do Rio de **redução da mortalidade materna e infantil**. **O motor é geral e cobre toda a base** — gestantes, hipertensos, diabéticos, idosos vulneráveis. Outras fichas entram com config, não com código novo.

---

## O valor da automação da ficha

A digitalização da ficha não é detalhe técnico — é onde o ACS recupera tempo de trabalho.

| Hoje (papel) | Com a solução (Telegram) |
| :---- | :---- |
| ACS leva ficha física em prancheta | Celular já no bolso · zero material extra |
| Preenchimento durante a visita por escrito | Bot conduz a coleta em perguntas curtas · FSM de 14 estados |
| Risco de campo deixado em branco ou ilegível | Validação no momento · não avança sem o dado obrigatório |
| Digitação manual no sistema ao final do dia/semana | Dado já entra no banco no momento do registro · sem retrabalho |
| Tempo de defasagem dado → sistema: horas a dias | Defasagem: segundos |
| Auditoria depende de papel arquivado | Tabela `auditoria` registra cada ação com timestamp e ACS |

O efeito secundário: o motor de priorização do dia seguinte usa **dados do dia que acabou**, não da semana passada.

---

## O que o ACS recebe por paciente

Para cada paciente da lista, o bot entrega três informações curtas:

| Campo | O que é | Exemplo |
| :---- | :---- | :---- |
| **Motivo da priorização** | Por que este paciente está nesta posição da lista | "urgência há 8 dias, nunca visitado, criança menor de 6 anos" |
| **Lacuna de cuidado** | O que está faltando, em termos concretos | "sem nenhum contato com o sistema desde o nascimento" |
| **O que verificar na visita** | Observações práticas — não é prescrição clínica | "Confirmar se a família ainda mora no endereço · perguntar sobre vacinação em dia · observar condições do domicílio · acionar a equipe se a família não for encontrada" |

O ACS **não faz diagnóstico nem conduta clínica**. O sistema apenas o orienta sobre **o que olhar** e **quando acionar a equipe de saúde**. A decisão clínica continua com a UBS.

---

## Como ler este projeto (mapa para a banca)

| Critério | Onde a evidência está |
| :---- | :---- |
| **Impacto Real (40)** | Achado dos 57 \+ régua derivada dos dados \+ eliminação do papel \+ LGPD-by-design que permite implantação imediata na SMS-Rio |
| **Engenharia (20)** | 3 camadas independentes · Claude isolado da PII · guardrail anti-prompt-injection · cron idempotente · auditoria completa |
| **Produto (20)** | Substitui papel sem exigir aprendizado de software novo (conversa, não app) · linguagem sem jargão clínico · FSM guia o ACS passo a passo |
| **Ideia (10)** | Une priorização inteligente e coleta digital em um único canal · fila de reposição com escalonamento · ajuste sazonal automático · ordenação determinística vs refinamento de linguagem |
| **Apresentação (10)** | Demo ao vivo do ciclo completo · seção de status honesta (abaixo) |

---

## Arquitetura

Três camadas independentes. A Camada 3 (Claude API) **nunca recebe dado identificável**.

┌─────────────────────────────────────────────────────────────────┐

│  CAMADA 1 — CANAL                                               │

│  Bot de mensageria · FSM Python pura (14 estados) · sem IA      │

│  Entrega lista priorizada \+ coleta da ficha de visita           │

│  Auth: SHA-256 do chat\_id · aviso LGPD obrigatório no /start    │

└────────────────────────────┬────────────────────────────────────┘

                             │ payloads sanitizados

┌────────────────────────────▼────────────────────────────────────┐

│  CAMADA 2 — BACKEND                                             │

│  FastAPI · PostgreSQL · 7 tabelas · AES-256 em repouso          │

│  Cálculo de scores · deduplicação · fila de reposição · cron    │

└────────────────────────────┬────────────────────────────────────┘

                             │ vetores anonimizados (hashes \+ scores)

┌────────────────────────────▼────────────────────────────────────┐

│  CAMADA 3 — INTELIGÊNCIA                                        │

│  Claude API · system prompt versionado · roda às 05h            │

│  Ordena lista · gera texto da lista em linguagem natural        │

└─────────────────────────────────────────────────────────────────┘

### Como o Claude foi usado

| Onde | Para quê |
| :---- | :---- |
| **Construção** | Geração de código nas 3 camadas, refinamento iterativo do system prompt, exploração dos parquets, redação do PRD |
| **Em produção (Camada 3\)** | Ordenação final da lista e geração dos três campos por paciente: motivo da priorização, lacuna de cuidado, o que verificar na visita |
| **Onde NÃO foi usado** | Cálculo de score (determinístico em Python), autenticação, persistência, deduplicação, fila de reposição, coleta da ficha (FSM determinística) |

Separação deliberada: lógica crítica e auditável fica fora do modelo. **O ranking é reproduzível sem chamar a API.** O Claude formata e refina; ele não decide o que é crítico.

### Canal: Telegram como POC, app interno como produto

O bot Telegram foi escolhido para o MVP porque:

- **É conversa, não app.** O ACS não precisa aprender a usar software novo — usa o teclado do celular respondendo perguntas.  
- **A FSM guia passo a passo.** Não há tela em branco. Cada estado faz uma pergunta com opções claras.  
- **Permite demonstração ao vivo em minutos**, sem deploy de app mobile.

**Para implantação na SMS-Rio, a Camada 1 deve migrar para um app interno.** Telegram envolve servidores fora do controle da Prefeitura e é incompatível com os requisitos plenos de LGPD para dados sensíveis de saúde. O contrato de payload entre Camada 1 e Camada 2 é desacoplado do canal — o app interno futuro **herda a mesma UX de conversa guiada** e não exige reescrever Camadas 2 ou 3\.

---

## Régua de priorização — geral

Quatro níveis, derivados do cruzamento `visitas × eventos_clinicos × pacientes`. Aplicação **na ordem exata** — nível superior nunca cede posição para inferior, independentemente de score.

| Nível | Critério (qualquer um ativa) | SLA |
| :---- | :---- | :---- |
| **CRÍTICO** | Urgência/internação ≤ 30 dias · gestante sem contato \> 15 dias · criança 0–6 sem contato \> 45 dias · condição de risco \+ nunca contatado \+ vulnerabilidade | **48h — busca ativa** |
| **ALTO** | Hipertenso/diabético sem contato 31–90 dias · idoso 66+ vulnerável sem contato \> 60 dias · sem nenhum registro de contato (sem condição crítica) | 5 dias úteis |
| **MÉDIO** | Condição crônica em acompanhamento 30–60 dias · família vulnerável sem visita recente sem urgência ativa | 30 dias |
| **BAIXO** | Sem fatores de risco ativos · contato recente | Rotina |

**Score composto:** 12 critérios. **Desempate dentro do mesmo nível:** 7 critérios em cascata (gestante → criança 0–6 → nunca contatado → maior lacuna → mais comorbidades → vulnerabilidade → distância). Distância geográfica é o **último** critério — nunca rebaixa CRÍTICO para favorecer ALTO mais próximo.

**Ajuste sazonal automático:** em março, junho e dezembro (picos respiratórios nos dados), pacientes 0–6 com score 85–99 e qualquer urgência nos últimos 60 dias são promovidos de ALTO para CRÍTICO. As observações da visita incluem atenção a sinais respiratórios.

Especificação completa (hierarquia, regras de desempate em cascata, ajuste sazonal, guardrails de segurança, exemplos de payload válido/inválido/adversarial): [`docs/acs_priorizacao_system_prompt.md`](http://./docs/acs_priorizacao_system_prompt.md).

---

## Ciclo operacional de 24h

| Horário | Processo |
| :---- | :---- |
| **05h00** | Batch de priorização gera a lista do dia e a entrega ao ACS · pendentes do dia anterior aparecem no topo marcados `(PENDENTE DO DIA ANTERIOR)` |
| **05h–21h** | Operação de campo · cada visita é registrada via FSM no Telegram e entra direto no banco — sem ficha de papel intermediária |
| **22h00** | Batch noturno: identifica não-visitadas · calcula score ajustado · seta `override_topo = true` para grupos de risco · notifica gestor se `dias_pendente ≥ 2` |

Paciente de risco não visitado entra **no topo** da lista do dia seguinte, antes de qualquer candidato novo. O ciclo se fecha em 24h sem o ACS precisar saber que isso aconteceu.

---

## Segurança e LGPD

LGPD não é checklist — é design.

| Princípio | Implementação |
| :---- | :---- |
| **Minimização** | Camada 3 recebe **apenas** hashes SHA-256, scores numéricos, booleanos e faixas etárias. Nunca nome, CPF, endereço literal ou telefone. |
| **Criptografia em repouso** | Conteúdos sensíveis cifrados em **AES-256** no PostgreSQL |
| **Pseudonimização** | `profissional_id` (UUID interno) substitui `telegram_chat_id` em todas as tabelas |
| **Retenção** | Histórico de chat: 90 dias, descarte automático (LGPD art. 15\) · comando `/limpar_historico` (LGPD art. 18, VI) |
| **Auditabilidade** | Tabela `auditoria` registra toda ação sensível com timestamp UTC e `profissional_id` |
| **Anti prompt injection** | System prompt da Camada 3 descarta campos que contenham instruções embutidas e gera alerta em `alertas_sistema` |
| **Validação de payload** | Se o JSON enviado à Camada 3 contiver qualquer campo identificável, o modelo **aborta** e retorna erro padronizado |

**Sobre os dados:** o dataset da SMS-Rio já vem anonimizado pela Prefeitura (SHA-256, ruído geográfico de 100m, date shifting, k-anonymity ≥ 5). Os números deste README refletem essa amostra — não representam indicadores reais da cidade.

---

## Modelo de dados

Sete tabelas PostgreSQL:

| Tabela | Propósito |
| :---- | :---- |
| `profissionais` | Cadastro de ACS · hash do chat\_id |
| `pacientes` | Cadastro pseudonimizado · campos clínicos e demográficos |
| `visitas` | Registros de visita com dados FSM criptografados |
| `auditoria` | Log LGPD de todas as ações sensíveis |
| `chat_history` | Histórico por ACS · AES-256 · retenção 90 dias |
| `lista_sugestoes` | Sugestões diárias · status · deduplicação por ciclo de 30 dias |
| `fila_reposicao` | Não-visitados · score ajustado · `override_topo` · `dias_pendente` |

Schema completo, relacionamentos e índices no [PRD v3.0](http://./docs/PRD_ACS_Primeira_Infancia_v3.docx).

---

## Stack

| Camada | Tecnologias |
| :---- | :---- |
| Canal | `python-telegram-bot` · FSM customizada · `cryptography` (SHA-256) |
| Backend | FastAPI · SQLAlchemy · PostgreSQL 15 · APScheduler · `cryptography.fernet` (AES-256) |
| Inteligência | Anthropic API · system prompt versionado · JSON-only parsing |
| Análise | Pandas · PyArrow |
| Infra | Docker \+ docker-compose (subir tudo com 1 comando) |

---

## Como rodar localmente

git clone \[URL\_DO\_REPO\] && cd \[REPO\]

cp .env.example .env  \# editar: ANTHROPIC\_API\_KEY, TELEGRAM\_BOT\_TOKEN, DB\_PASSWORD, ENCRYPTION\_KEY

docker-compose up \-d

docker-compose exec backend python scripts/load\_data.py

docker-compose exec backend python scripts/run\_priorizacao.py \--equipe\_id \[HASH\]

\# Falar com @\[NOME\_DO\_BOT\] no Telegram → /start

---

## Estado atual — honestidade sobre escopo

| Componente | Status |
| :---- | :---- |
| Análise dos 4 parquets | ✅ Completa |
| System prompt da Camada 3 (v2.0, versionado) | ✅ Testado com payloads sintéticos cobrindo todos os níveis, sazonal e adversariais |
| Backend FastAPI \+ 7 tabelas \+ AES-256 \+ auditoria | ✅ Funcional |
| Motor de priorização (Camada 2 ↔ 3\) | ✅ Funcional · executado sobre dados reais anonimizados · cron configurado |
| Bot Telegram com FSM (14 estados) | ✅ Funcional · entrega lista priorizada \+ coleta digital da ficha · aviso LGPD no `/start` |
| Deduplicação e fila de reposição | ✅ Funcional · cron 22h configurado e validado por execução manual |
| Notificações ao gestor (1 e 2 dias) | ✅ Funcional |
| App interno (substituir Telegram) | ❌ Roadmap — Telegram é POC |
| Dashboard de gestão | ❌ Fora de escopo v3.0 |
| Integração com prontuário eletrônico SMS-Rio | ❌ Depende de acesso da Prefeitura |

---

## Roadmap

- **v3.1 (2 semanas):** métricas de cobertura em tempo real para gestor de unidade; múltiplos turnos por ACS no mesmo dia.  
- **v4.0 (1 trimestre):** **app interno substituindo Telegram** (requisito LGPD pleno), herdando a UX de conversa guiada; expansão para outras fichas (Crônico, Gestante, Tuberculose, Ficha A); realocação automática entre ACS da mesma equipe.  
- **Integração SMS-Rio:** substituir parquets anonimizados pelas fontes vivas do prontuário; ampliar do MVP 0–6 para o cadastro completo.

---

## Documentação complementar

- 📄 [PRD v3.0](http://./docs/PRD_ACS_Primeira_Infancia_v3.docx) — especificação funcional, modelo de dados detalhado, regras de batch  
- 🤖 [System prompt da Camada 3](http://./docs/acs_priorizacao_system_prompt.md) — contrato com a Claude API, hierarquia, desempate, guardrails, exemplos  
- 📊 [Notebooks de análise](http://./analise/) — exploração dos 4 parquets, derivação da régua, detecção da sazonalidade

## Referências oficiais do hackathon

- [Regras e critérios](https://github.com/taicor-ai/claude-impact-lab-rio)  
- [Briefing e dados do desafio](https://github.com/prefeitura-rio/claude-impact-lab-saude)

---

**Construído em 24/05/2026 no Claude Impact Lab Rio.** `[NOME DA EQUIPE]` · Rio de Janeiro  
