from typing import List

class Escalation:
    pass

async def send_escalation_alert(escalation: Escalation, ops_link: str) -> List[int]:
    # returns message_ids
    return []

async def edit_escalation_message(chat_id: int, message_id: int, text: str, keyboard=None) -> None:
    pass

async def send_ops_link(chat_id: int, link: str) -> None:
    pass

async def send_sms_fallback(phone: str, message: str) -> None:
    pass

async def is_allowed_user(telegram_user_id: int) -> bool:
    return True
