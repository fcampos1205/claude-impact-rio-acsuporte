"""Testes do histórico de chat persistente — Fase 5. 5 testes. LGPD."""


async def test_salvar_mensagem_criptografa_conteudo(db_session, seed_minimal):
    """content_enc nunca contém o texto original em bytes."""
    from sqlalchemy import select

    from app.bot.historico import salvar_mensagem
    from app.models.chat_history import ChatHistory

    acs = seed_minimal["acs_list"][0]
    await salvar_mensagem(db_session, acs.id, "user", "mensagem secreta")

    result = await db_session.execute(
        select(ChatHistory).where(ChatHistory.profissional_id == acs.id)
    )
    row = result.scalar_one()
    # content_enc must be bytes but must NOT contain the plaintext
    assert isinstance(row.content_enc, bytes)
    assert b"mensagem secreta" not in row.content_enc


async def test_carregar_contexto_descriptografa(db_session, seed_minimal):
    from app.bot.historico import carregar_contexto, salvar_mensagem

    acs = seed_minimal["acs_list"][0]
    await salvar_mensagem(db_session, acs.id, "user", "Ola ACS!")

    mensagens = await carregar_contexto(db_session, acs.id)
    assert len(mensagens) == 1
    assert mensagens[0]["content"] == "Ola ACS!"


async def test_carregar_contexto_respeita_ordem_temporal(db_session, seed_minimal):
    from app.bot.historico import carregar_contexto, salvar_mensagem

    acs = seed_minimal["acs_list"][0]
    await salvar_mensagem(db_session, acs.id, "user", "primeira")
    await salvar_mensagem(db_session, acs.id, "assistant", "segunda")
    await salvar_mensagem(db_session, acs.id, "user", "terceira")

    mensagens = await carregar_contexto(db_session, acs.id)
    assert mensagens[0]["content"] == "primeira"
    assert mensagens[2]["content"] == "terceira"


async def test_carregar_contexto_limita_n_ultimas(db_session, seed_minimal):
    from app.bot.historico import carregar_contexto, salvar_mensagem

    acs = seed_minimal["acs_list"][0]
    for i in range(5):
        await salvar_mensagem(db_session, acs.id, "user", f"mensagem {i}")

    mensagens = await carregar_contexto(db_session, acs.id, n_ultimas=3)
    assert len(mensagens) == 3


async def test_carregar_contexto_apos_limpar_retorna_vazio(db_session, seed_minimal):
    from app.bot.historico import carregar_contexto, limpar_historico, salvar_mensagem

    acs = seed_minimal["acs_list"][0]
    await salvar_mensagem(db_session, acs.id, "user", "mensagem")
    await limpar_historico(db_session, acs.id)

    mensagens = await carregar_contexto(db_session, acs.id)
    assert mensagens == []
