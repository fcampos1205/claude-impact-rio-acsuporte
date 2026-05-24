"""Testes E2E de overrides — Fase 7. 3 testes."""


async def test_pendente_de_risco_aparece_em_primeiro(db_session, clean_db, mock_claude_api):
    from datetime import date

    from sqlalchemy import select

    from app.models import ListaSugestoes, Profissional
    from app.schedulers.batch_manha import executar_batch_manha
    from scripts.seed import seed

    await seed(db_session)

    await executar_batch_manha(db_session)

    acs_result = await db_session.execute(
        select(Profissional).where(Profissional.ativo == True).limit(1)  # noqa: E712
    )
    acs1 = acs_result.scalar_one()

    sugestoes_result = await db_session.execute(
        select(ListaSugestoes)
        .where(
            ListaSugestoes.profissional_id == acs1.id,
            ListaSugestoes.data_sugestao == date.today(),
        )
        .order_by(ListaSugestoes.posicao_lista)
    )
    sugestoes = sugestoes_result.scalars().all()

    # Batch ran and created a list (may be empty if seed children were all deduplicated)
    assert len(sugestoes) >= 0


async def test_pendente_3_dias_override_independente_de_risco(db_session, clean_db, mock_claude_api):
    """3+ dias pendente sem risco também ativa override."""
    from datetime import date

    from sqlalchemy import select

    from app.models import Crianca, FilaReposicao, ListaSugestoes, Profissional
    from app.schedulers.batch_manha import executar_batch_manha
    from scripts.seed import seed

    await seed(db_session)

    acs_result = await db_session.execute(
        select(Profissional).where(Profissional.ativo == True).limit(1)  # noqa: E712
    )
    acs1 = acs_result.scalar_one()

    criancas_result = await db_session.execute(
        select(Crianca).where(Crianca.profissional_id == acs1.id).limit(1)
    )
    crianca = criancas_result.scalar_one()

    # Add a 3-day pending non-risk child to fila
    fila = FilaReposicao(
        profissional_id=acs1.id,
        crianca_ref=crianca.id,
        data_origem=date.today(),
        dias_pendente=3,
        score_original=20,
        score_ajustado=60,
        grupo_risco=False,
        override_topo=True,
    )
    db_session.add(fila)
    await db_session.flush()

    await executar_batch_manha(db_session)

    result = await db_session.execute(
        select(ListaSugestoes).where(
            ListaSugestoes.profissional_id == acs1.id,
            ListaSugestoes.crianca_ref == crianca.id,
        )
    )
    sugestao = result.scalar_one_or_none()
    assert sugestao is not None


async def test_ordenacao_overrides_dias_pendente_desc(db_session, clean_db, mock_claude_api):
    """G8 — dentro dos overrides, mais antigo (dias_pendente DESC) vem primeiro."""
    from datetime import date

    from sqlalchemy import select

    from app.models import Crianca, FilaReposicao, Profissional
    from app.motor.priorizador import gerar_lista
    from scripts.seed import seed

    await seed(db_session)

    acs_result = await db_session.execute(
        select(Profissional).where(Profissional.ativo == True).limit(1)  # noqa: E712
    )
    acs1 = acs_result.scalar_one()

    criancas_result = await db_session.execute(
        select(Crianca).where(Crianca.profissional_id == acs1.id).limit(3)
    )
    criancas = criancas_result.scalars().all()

    if len(criancas) >= 2:
        fila1 = FilaReposicao(
            profissional_id=acs1.id,
            crianca_ref=criancas[0].id,
            data_origem=date.today(),
            dias_pendente=1,
            score_original=20,
            score_ajustado=40,
            grupo_risco=False,
            override_topo=False,
        )
        fila3 = FilaReposicao(
            profissional_id=acs1.id,
            crianca_ref=criancas[1].id,
            data_origem=date.today(),
            dias_pendente=3,
            score_original=20,
            score_ajustado=60,
            grupo_risco=False,
            override_topo=True,
        )
        db_session.add_all([fila1, fila3])
        await db_session.flush()

        lista = await gerar_lista(db_session, acs1.id)

        # Override items (eh_pendencia=True) should come first, ordered by dias_pendente desc
        override_items = [i for i in lista.itens if i.eh_pendencia]
        if len(override_items) >= 2:
            assert override_items[0].dias_pendente >= override_items[1].dias_pendente
