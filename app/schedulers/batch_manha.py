"""Morning batch — runs at 05:00 daily.

For each active ACS:
  1. gerar_lista() — prioritized visit list
  2. gerar_mensagem_telegram() — format via Claude or fallback
  3. INSERT lista_sugestoes with status=SUGERIDA (idempotent via ON CONFLICT DO NOTHING)
  4. Audit the batch run
"""
import asyncio
import structlog
from datetime import date

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models import Profissional, ListaSugestoes
from app.motor.priorizador import gerar_lista
from app.llm.gerador_lista import gerar_mensagem_telegram
from app.auditoria import registrar

logger = structlog.get_logger()


async def executar_batch_manha(session, data_alvo: date | None = None) -> dict:
    """Execute morning batch. Returns stats dict."""
    hoje = data_alvo or date.today()
    stats = {"acs_processados": 0, "listas_geradas": 0, "erros": 0}

    # Get all active ACS
    result = await session.execute(
        select(Profissional).where(Profissional.ativo == True)  # noqa: E712
    )
    acs_list = result.scalars().all()

    semaforo = asyncio.Semaphore(5)

    async def processar_acs(acs):
        async with semaforo:
            try:
                lista = await gerar_lista(session, acs.id, hoje)
                if not lista.itens:
                    return

                mensagem = await gerar_mensagem_telegram(lista)

                # Insert with ON CONFLICT DO NOTHING for idempotency
                for pos, item in enumerate(lista.itens):
                    stmt = pg_insert(ListaSugestoes).values(
                        profissional_id=acs.id,
                        crianca_ref=item.crianca_ref,
                        data_sugestao=hoje,
                        status="SUGERIDA",
                        posicao_lista=pos + 1,
                        score=item.score,
                        grupo_risco=item.grupo_risco,
                        override_topo=item.override_topo,
                        motivos=item.motivos,
                        mensagem_formatada=mensagem if pos == 0 else None,
                    ).on_conflict_do_nothing(
                        index_elements=["profissional_id", "crianca_ref", "data_sugestao"]
                    )
                    await session.execute(stmt)

                stats["listas_geradas"] += 1
                logger.info("batch_manha_acs_ok", acs_id=str(acs.id), itens=len(lista.itens))
            except Exception as e:
                stats["erros"] += 1
                logger.error("batch_manha_acs_erro", acs_id=str(acs.id), erro=str(e))
            finally:
                stats["acs_processados"] += 1

    await asyncio.gather(*[processar_acs(acs) for acs in acs_list])
    await session.flush()

    await registrar(session, acao="BATCH_MANHA_COMPLETO", metadata=stats)
    return stats
