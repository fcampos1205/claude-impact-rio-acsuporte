"""LGPD audit helper — all data access/mutations must be logged here.

Rules (CLAUDE.md Regra 3):
- NEVER log message content, CPF, or full name.
- Log profissional_id, crianca_ref (UUID), acao, timestamp.
- Every action that reads/writes/exports personal data records here.
"""

from __future__ import annotations

import uuid
from datetime import datetime, UTC
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auditoria import Auditoria


async def registrar(
    session: AsyncSession,
    acao: str,
    profissional_id: uuid.UUID | None = None,
    metadata: dict[str, Any] | None = None,
) -> Auditoria:
    """Persist an audit record. Does NOT commit — caller owns the transaction."""
    entry = Auditoria(
        acao=acao,
        profissional_id=profissional_id,
        metadata_json=metadata or {},
        criado_em=datetime.now(UTC).replace(tzinfo=None),
    )
    session.add(entry)
    await session.flush()
    return entry
