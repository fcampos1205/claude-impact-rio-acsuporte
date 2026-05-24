"""Message handlers for each FSM state."""


async def handle_message(session, profissional, message_text: str, fsm_state: str) -> str:
    """Route incoming message to appropriate handler based on FSM state."""
    return f"Mensagem recebida no estado {fsm_state}"
