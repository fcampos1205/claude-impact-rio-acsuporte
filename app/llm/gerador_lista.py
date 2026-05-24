"""Main entry point: tries Claude API, falls back to Jinja2 template.

G15: LLMUnavailableError → use formatar_lista_fallback.
Audits LLM_FALLBACK_USADO when fallback is triggered.
"""
import structlog

from app.llm.cliente import ClaudeClient, LLMUnavailableError
from app.llm.fallback import formatar_lista_fallback
from app.llm.prompts import SYSTEM_PROMPT_LISTA, montar_prompt_usuario

logger = structlog.get_logger()

_client = ClaudeClient()


async def gerar_mensagem_telegram(lista: object) -> str:
    """Try Claude API for formatted Telegram message, fall back to template on failure."""
    try:
        prompt = montar_prompt_usuario(lista)
        return await _client.chamar(system=SYSTEM_PROMPT_LISTA, user=prompt)
    except LLMUnavailableError:
        logger.warning("llm_fallback_ativado", motivo="API indisponível")
        return formatar_lista_fallback(lista)
