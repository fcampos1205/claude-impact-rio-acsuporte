# ADR 003 — Criptografia em coluna com Fernet (AES-256)

**Status**: Aceito · 2026-05-24

## Contexto

`chat_history` armazena mensagens trocadas entre ACS e bot. Conteúdo é dado sensível (LGPD art. 11 — saúde) e relacionado a crianças (LGPD art. 14 — especialmente protegido). Precisa ser criptografado em repouso.

Opções comuns:
1. Criptografia full-disk (Postgres + volume Docker)
2. Criptografia da conexão (TLS) — mas dado em repouso fica plain
3. Criptografia da coluna — campo a campo
4. TDE (Transparent Data Encryption) do Postgres — Enterprise only

## Decisão

**Criptografia por coluna usando Fernet (AES-128-CBC + HMAC-SHA256) da biblioteca `cryptography` Python.**

Wrapper em `app/crypto.py`. Aplicado nos campos:
- `chat_history.content_enc`
- `visitas.dados_fsm_enc` (se contiver observações livres)

Chave única no `.env` (`ENCRYPTION_KEY`). Geração: `Fernet.generate_key()`.

## Consequências

### Positivas

- Granularidade — `/limpar_historico` apaga linhas específicas sem rotacionar chave
- Replay protection — Fernet embute timestamp; ataques de replay falham
- Integridade incluída — HMAC-SHA256 detecta tampering
- Padrão da biblioteca `cryptography` (Python) — FIPS-aceitável
- Não exige extensão Postgres
- Auditável: linhas no DB são bytes binários, impossíveis de ler por dump

### Negativas

- Queries de busca em conteúdo são impossíveis sem descriptografar — aceito (nunca buscamos texto livre por substring)
- Performance: descriptografar 20 mensagens por sessão custa ~5ms — irrelevante
- Rotação de chave exige re-criptografar todas as linhas — documentado como procedimento operacional
- Backup do banco precisa proteger chave separadamente

## Alternativas consideradas

### Postgres `pgcrypto` (`PGP_SYM_ENCRYPT`)

- Vantagem: criptografia no DB, mais robusta contra dump direto
- Desvantagem: chave passa pelo log de query do Postgres; difícil tirar dos logs

Rejeitado por exposição de chave em logs.

### Full-disk encryption (LUKS)

- Vantagem: zero código de aplicação
- Desvantagem: protege contra furto físico, não contra acesso ao Postgres rodando

Insuficiente sozinha.

### TDE (Transparent Data Encryption)

- Vantagem: padrão enterprise
- Desvantagem: só Postgres Enterprise; não temos Postgres community com isso

Não aplicável.

### AES-256-GCM customizado

- Vantagem: 256 bits de chave (vs 128 do Fernet)
- Desvantagem: implementação manual aumenta risco de erros sutis (nonce, padding)

128 bits do Fernet é considerado seguro pela NIST para dados não-Estado-Nação. Fica.

## Rotação de chave (procedimento futuro)

1. Gerar nova chave (`Fernet.generate_key()`)
2. Adicionar nova chave ao código suportando *multi-fernet* (`MultiFernet([nova, antiga])`)
3. Re-criptografar todas as linhas em batch (script de migração)
4. Remover chave antiga

No MVP, rotação não está implementada — documentado como follow-up.

## Referências

- LGPD art. 6º VII (segurança), art. 47 (medidas técnicas)
- `cryptography.io/en/latest/fernet/`
- `docs/architecture/decisoes_design.md` G5
