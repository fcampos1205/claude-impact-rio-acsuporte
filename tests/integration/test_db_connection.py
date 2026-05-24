"""Testes de conexão com DB — Fase 0. 2 testes."""


async def test_engine_conecta_ao_postgres(engine):
    from sqlalchemy import select
    async with engine.connect() as conn:
        result = await conn.execute(select(1))
        assert result.scalar() == 1


async def test_session_factory_cria_sessao_async(db_session):
    from sqlalchemy import select
    result = await db_session.execute(select(1))
    assert result.scalar() == 1
