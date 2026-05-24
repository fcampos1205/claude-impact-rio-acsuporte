"""Testes do comando /limpar_historico — Fase 5. G10. 4 testes."""


async def test_limpar_historico_apaga_mensagens(db_session, seed_minimal):
    """Após limpar, contagem de ChatHistory pro ACS é zero."""
    from app.bot.historico import carregar_contexto, limpar_historico, salvar_mensagem

    acs = seed_minimal["acs_list"][0]
    await salvar_mensagem(db_session, acs.id, "user", "msg1")
    await salvar_mensagem(db_session, acs.id, "user", "msg2")

    count = await limpar_historico(db_session, acs.id)
    assert count == 2

    mensagens = await carregar_contexto(db_session, acs.id)
    assert mensagens == []


async def test_limpar_historico_mantem_profissional_id(db_session, seed_minimal):
    """ACS continua existindo após limpar histórico (cascade=False)."""
    from sqlalchemy import select

    from app.bot.historico import limpar_historico, salvar_mensagem
    from app.models.profissional import Profissional

    acs = seed_minimal["acs_list"][0]
    await salvar_mensagem(db_session, acs.id, "user", "msg")
    await limpar_historico(db_session, acs.id)

    result = await db_session.execute(select(Profissional).where(Profissional.id == acs.id))
    assert result.scalar_one() is not None


async def test_limpar_historico_registra_auditoria_sem_conteudo(db_session, seed_minimal):
    """G10 — Auditoria registra acao=LIMPAR_HISTORICO sem expor conteúdo."""
    from sqlalchemy import select

    from app.bot.comandos import cmd_limpar_historico
    from app.bot.historico import salvar_mensagem
    from app.models.auditoria import Auditoria

    acs = seed_minimal["acs_list"][0]
    await salvar_mensagem(db_session, acs.id, "user", "conteudo sensivel")

    await cmd_limpar_historico(db_session, acs.id)

    result = await db_session.execute(
        select(Auditoria).where(Auditoria.acao == "LIMPAR_HISTORICO")
    )
    audit = result.scalar_one()
    assert audit.profissional_id == acs.id
    # Must NOT contain the message content anywhere in audit metadata
    assert "conteudo sensivel" not in str(audit.metadata_json)


async def test_limpar_historico_idempotente(db_session, seed_minimal):
    """Rodar limpar 2x não dá erro; 2ª retorna 0 mensagens apagadas."""
    from app.bot.historico import limpar_historico

    acs = seed_minimal["acs_list"][0]
    await limpar_historico(db_session, acs.id)  # first call, nothing to delete
    count2 = await limpar_historico(db_session, acs.id)  # second call
    assert count2 == 0
