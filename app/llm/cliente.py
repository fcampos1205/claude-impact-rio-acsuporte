"""Claude API client with exponential backoff retry.

G15: In case of persistent API failure, raises LLMUnavailableError.
Caller (gerador_lista.py) must catch this and use fallback.
"""
import asyncio

import anthropic

from app.config import settings


class LLMUnavailableError(Exception):
    """Raised when Claude API is unreachable after max_retries attempts."""


class ClaudeClient:
    def __init__(self) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def chamar(
        self,
        system: str,
        user: str,
        max_tokens: int = 2000,
        max_retries: int = 3,
        backoff_base: float = 1.0,
    ) -> str:
        """Call Claude API with exponential backoff.

        Raises LLMUnavailableError after max_retries failures.
        """
        last_error: Exception | None = None
        for attempt in range(max_retries):
            try:
                response = await self._client.messages.create(
                    model=settings.anthropic_model,
                    max_tokens=max_tokens,
                    system=system,
                    messages=[{"role": "user", "content": user}],
                )
                return response.content[0].text
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    await asyncio.sleep(backoff_base * (2**attempt))
        raise LLMUnavailableError(f"Claude API unavailable after {max_retries} retries") from last_error
