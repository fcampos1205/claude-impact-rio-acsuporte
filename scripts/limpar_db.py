"""Drop all tables and recreate schema. Use only in development."""

import asyncio

from sqlalchemy.ext.asyncio import create_async_engine

from app.models import Base


async def main() -> None:
    from app.config import settings

    engine = create_async_engine(settings.database_url, echo=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print("DB resetado.")


if __name__ == "__main__":
    asyncio.run(main())
