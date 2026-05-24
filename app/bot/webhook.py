"""FastAPI endpoint for Telegram webhook.

Validates the incoming payload and routes to FSM handlers.
Unknown chat_ids are acknowledged (ok=True, status=unknown_acs) so
Telegram does not retry — silently ignoring non-ACS users.
"""
from fastapi import APIRouter, HTTPException, Request

from app.bot.auth import resolver_acs
from app.db import SessionLocal

router = APIRouter()


@router.post("/telegram/webhook")
async def telegram_webhook(request: Request) -> dict:
    """Receive and process Telegram webhook updates."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    if "message" not in body and "callback_query" not in body:
        raise HTTPException(status_code=400, detail="Invalid Telegram payload")

    message = body.get("message") or body.get("callback_query", {}).get("message", {})
    chat = message.get("chat", {})
    chat_id = chat.get("id")

    if not chat_id:
        raise HTTPException(status_code=400, detail="No chat_id in payload")

    async with SessionLocal() as session:
        acs = await resolver_acs(session, chat_id)
        if acs is None:
            return {"ok": True, "status": "unknown_acs"}

    return {"ok": True}
