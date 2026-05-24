"""ACS authentication: hash telegram chat_id to look up Profissional."""
import hashlib
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.models.profissional import Profissional


def hash_chat_id(chat_id: int) -> str:
    """SHA-256 of str(chat_id) + salt. Used for lookup, never store raw chat_id."""
    salted = f"{chat_id}{settings.telegram_chat_id_salt}"
    return hashlib.sha256(salted.encode()).hexdigest()


async def resolver_acs(session: AsyncSession, chat_id: int) -> Profissional | None:
    """Lookup ACS by hashed chat_id. Returns None if not found."""
    hashed = hash_chat_id(chat_id)
    result = await session.execute(
        select(Profissional).where(Profissional.telegram_chat_id_hash == hashed)
    )
    return result.scalar_one_or_none()
