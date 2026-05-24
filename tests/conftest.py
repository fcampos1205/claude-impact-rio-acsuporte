"""Fixtures globais — disponíveis em todos os testes.

Use SEMPRE as fixtures daqui antes de inventar novas. Documentado em
`.claude/skills/acs-tdd-helper/SKILL.md` (Regra R3).
"""
import asyncio
from datetime import date, datetime, UTC
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

# Marcar todos os testes deste projeto como async-compatible
pytestmark = pytest.mark.asyncio


@pytest.fixture(scope="session")
def event_loop():
    """Loop único pra sessão de teste."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def postgres_url():
    """URL de um Postgres efêmero via testcontainers.

    Disponível para todos os testes da sessão. Auto-destruído ao fim.
    """
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:16-alpine") as pg:
        url = pg.get_connection_url().replace("psycopg2", "asyncpg")
        yield url


@pytest_asyncio.fixture(scope="session")
async def engine(postgres_url) -> AsyncEngine:
    """Engine SQLAlchemy async ligado ao Postgres efêmero."""
    eng = create_async_engine(postgres_url, echo=False)

    # Cria todas as tabelas
    from app.models.base import Base

    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield eng

    await eng.dispose()


@pytest_asyncio.fixture
async def db_session(engine) -> AsyncSession:
    """Sessão async por teste. Rollback automático ao fim."""
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.connect() as conn:
        trans = await conn.begin()
        session = SessionLocal(bind=conn)

        try:
            yield session
        finally:
            await session.close()
            await trans.rollback()


@pytest_asyncio.fixture
async def clean_db(engine):
    """Garante DB limpo. Use quando precisar de tabelas vazias entre testes."""
    from app.models.base import Base

    async with engine.begin() as conn:
        # Limpa todas as tabelas (sem dropar)
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())
    yield


@pytest.fixture
def frozen_time(monkeypatch):
    """Congela datetime.now() / date.today() em uma data fixa.

    Use no lugar de freezegun para evitar conflitos com SQLAlchemy.
    """
    DATA_FIXA = datetime(2026, 5, 24, 10, 0, 0, tzinfo=UTC)

    class _FakeDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return DATA_FIXA if tz else DATA_FIXA.replace(tzinfo=None)

        @classmethod
        def utcnow(cls):
            return DATA_FIXA.replace(tzinfo=None)

    class _FakeDate(date):
        @classmethod
        def today(cls):
            return DATA_FIXA.date()

    # Patch só em módulos da app — sqlalchemy.func.now() segue normal
    import datetime as _dt_module
    monkeypatch.setattr(_dt_module, "datetime", _FakeDatetime)
    monkeypatch.setattr(_dt_module, "date", _FakeDate)

    return DATA_FIXA


@pytest_asyncio.fixture
async def seed_minimal(db_session):
    """1 equipe, 2 ACS, 10 crianças. SEM histórico de visitas. SEM sugestões.

    Use para testes que precisam de mínimo de estrutura.
    """
    from app.models import Equipe, Profissional, Crianca

    equipe = Equipe(
        nome="ESF Test",
        endereco_latitude=-22.9,
        endereco_longitude=-43.2,
    )
    db_session.add(equipe)
    await db_session.flush()

    acs_list = []
    for i in range(2):
        acs = Profissional(
            nome=f"ACS Test {i}",
            telegram_chat_id_hash=f"hash_test_{i}",
            equipe_id=equipe.id,
            ativo=True,
        )
        db_session.add(acs)
        acs_list.append(acs)
    await db_session.flush()

    criancas = []
    for i in range(10):
        c = Crianca(
            profissional_id=acs_list[i % 2].id,
            equipe_id=equipe.id,
            faixa_etaria="0-6",
            sexo="M" if i % 2 == 0 else "F",
            raca_cor="parda",
            situacao_vulnerabilidade=False,
            endereco_latitude=-22.9,
            endereco_longitude=-43.2,
            vacinacao_em_dia=True,
        )
        db_session.add(c)
        criancas.append(c)
    await db_session.flush()

    return {"equipe": equipe, "acs_list": acs_list, "criancas": criancas}


@pytest_asyncio.fixture
async def seed_com_risco(db_session, seed_minimal):
    """Seed mínimo + 3 crianças propositalmente em grupo de risco."""
    from app.models import Crianca
    from datetime import date, timedelta

    risco = []
    for i in range(3):
        c = Crianca(
            profissional_id=seed_minimal["acs_list"][0].id,
            equipe_id=seed_minimal["equipe"].id,
            faixa_etaria="0-6",
            sexo="M",
            raca_cor="parda",
            situacao_vulnerabilidade=True,
            endereco_latitude=-22.9,
            endereco_longitude=-43.2,
            vacinacao_em_dia=False,
            ultima_consulta=date.today() - timedelta(days=180),
        )
        db_session.add(c)
        risco.append(c)
    await db_session.flush()

    return {**seed_minimal, "criancas_risco": risco}


@pytest.fixture
def mock_claude_api(monkeypatch):
    """Mock do ClaudeClient. Retorna texto pré-definido sem chamar API real."""
    async def _fake_chamar(self, system, user, max_tokens=2000):
        return "Mensagem mockada do Claude API"

    from app.llm.cliente import ClaudeClient
    monkeypatch.setattr(ClaudeClient, "chamar", _fake_chamar)
    yield


@pytest.fixture
def mock_claude_api_falha(monkeypatch):
    """Mock do ClaudeClient que sempre falha. Use pra testar fallback (G15)."""
    from app.llm.cliente import ClaudeClient, LLMUnavailableError

    async def _fake_chamar_falha(self, system, user, max_tokens=2000):
        raise LLMUnavailableError("API mockada offline")

    monkeypatch.setattr(ClaudeClient, "chamar", _fake_chamar_falha)
    yield


@pytest.fixture
def mock_telegram_bot(monkeypatch):
    """Mock do Telegram Application. Captura mensagens enviadas em lista."""
    sent_messages = []

    async def _fake_send_message(self, chat_id, text, **kwargs):
        sent_messages.append({"chat_id": chat_id, "text": text, **kwargs})

    # Patch quando bot.py existir
    try:
        from telegram.ext import ExtBot
        monkeypatch.setattr(ExtBot, "send_message", _fake_send_message)
    except ImportError:
        pass

    yield sent_messages
