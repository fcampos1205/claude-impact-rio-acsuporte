"""Prompt templates for Claude API calls.

G7: motivo_pendencia() generates dynamic text based on dias_pendente.
LGPD: prompts use initials only, never full names.
"""

SYSTEM_PROMPT_LISTA = """
Você é um assistente para Agentes Comunitários de Saúde (ACS) que cuida de crianças de 0-6 anos.
Formate a lista de visitas de forma clara, empática e objetiva para o Telegram.
Use APENAS as iniciais das crianças para identificação — NUNCA invente dados ou nomes completos.
Destaque crianças em grupo de risco com 🔴 e pendências com ⏰.
Responda APENAS com a mensagem formatada, sem explicações adicionais.
"""


def motivo_pendencia(dias: int) -> str:
    """G7 — dynamic pending reason text based on dias_pendente."""
    if dias == 1:
        return "PENDENTE DO DIA ANTERIOR"
    elif dias == 2:
        return f"PENDENTE HÁ {dias} DIAS"
    else:
        return f"PENDENTE HÁ {dias} DIAS · OVERRIDE"


def montar_prompt_usuario(lista_priorizada: object) -> str:
    """Build the user prompt from a ListaPriorizada.

    LGPD: uses crianca_ref (UUID) as identifier, no personal data.
    """
    linhas = []
    for i, item in enumerate(lista_priorizada.itens, 1):  # type: ignore[union-attr]
        prefix = "🔴 " if item.grupo_risco else ""
        if item.eh_pendencia:
            motivo = motivo_pendencia(item.dias_pendente)
            linhas.append(
                f"{i}. {prefix}Criança {str(item.crianca_ref)[:8]}... — {motivo} (score: {item.score})"
            )
        else:
            motivo_str = ", ".join(item.motivos) if item.motivos else "Visita de rotina"
            linhas.append(
                f"{i}. {prefix}Criança {str(item.crianca_ref)[:8]}... — {motivo_str} (score: {item.score})"
            )

    return "Formate esta lista de visitas domiciliares para enviar via Telegram:\n\n" + "\n".join(linhas)
