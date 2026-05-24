"""APScheduler bootstrap — registers all batch jobs."""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings

_scheduler: AsyncIOScheduler | None = None


def criar_scheduler() -> AsyncIOScheduler:
    from app.db import SessionLocal
    from app.schedulers.batch_manha import executar_batch_manha
    from app.schedulers.batch_noite import executar_batch_noite
    from app.schedulers.limpeza_historico import executar_limpeza_historico

    scheduler = AsyncIOScheduler(timezone="America/Sao_Paulo")

    async def _job_batch_manha():
        async with SessionLocal() as session:
            await executar_batch_manha(session)
            await session.commit()

    async def _job_batch_noite():
        async with SessionLocal() as session:
            await executar_batch_noite(session)
            await session.commit()

    async def _job_limpeza():
        async with SessionLocal() as session:
            await executar_limpeza_historico(session)
            await session.commit()

    scheduler.add_job(_job_batch_manha, CronTrigger(hour=settings.batch_manha_hora, minute=0))
    scheduler.add_job(_job_batch_noite, CronTrigger(hour=settings.batch_noite_hora, minute=0))
    scheduler.add_job(_job_limpeza, CronTrigger(hour=3, minute=0))

    return scheduler
