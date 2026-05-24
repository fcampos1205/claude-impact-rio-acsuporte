"""Deterministic Jinja2 fallback when Claude API is unavailable.

G15: Called by gerador_lista.py when LLMUnavailableError is raised.
No external calls — pure template rendering.
"""
from jinja2 import Template

from app.llm.prompts import motivo_pendencia

TEMPLATE = Template(
    """
*📋 Lista de Visitas — {{ data }}*

{% for item in itens %}
{{ loop.index }}. {% if item.grupo_risco %}🔴 {% endif %}{% if item.eh_pendencia %}⏰ {% endif %}Criança {{ item.crianca_ref_short }}
   _{{ item.motivo_display }}_
{% else %}
_Nenhuma visita programada para hoje._
{% endfor %}
""".strip()
)


def formatar_lista_fallback(lista: object) -> str:
    """Format visit list using Jinja2 template. Always succeeds — no external calls."""
    # Handle None or plain empty list
    if lista is None:
        return "📋 *Lista de Visitas*\n\n_Nenhuma visita programada para hoje._"

    if isinstance(lista, list):
        if not lista:
            return "📋 *Lista de Visitas*\n\n_Nenhuma visita programada para hoje._"
        # Non-empty plain list — treat items as-is (not expected in production)
        itens_raw = lista
        data_str = "hoje"
    else:
        if not hasattr(lista, "itens") or not lista.itens:  # type: ignore[union-attr]
            return "📋 *Lista de Visitas*\n\n_Nenhuma visita programada para hoje._"
        itens_raw = lista.itens  # type: ignore[union-attr]
        data_attr = getattr(lista, "data", None)
        data_str = data_attr.strftime("%d/%m/%Y") if data_attr else "hoje"

    items_data = []
    for item in itens_raw:
        if item.eh_pendencia:
            motivo_display = motivo_pendencia(item.dias_pendente)
        else:
            motivo_display = ", ".join(item.motivos) if item.motivos else "Visita de rotina"

        items_data.append(
            {
                "grupo_risco": item.grupo_risco,
                "eh_pendencia": item.eh_pendencia,
                "crianca_ref_short": str(item.crianca_ref)[:8] + "...",
                "motivo_display": motivo_display,
            }
        )

    return TEMPLATE.render(itens=items_data, data=data_str)
