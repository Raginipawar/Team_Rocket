from fastapi import APIRouter, Header, Request, HTTPException
from typing import Optional

router = APIRouter(prefix="/webhooks/telegram", tags=["webhooks"])

@router.post("")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: Optional[str] = Header(None)
):
    # Validate token
    if not x_telegram_bot_api_secret_token or x_telegram_bot_api_secret_token != "YOUR_SECRET_TOKEN":
        raise HTTPException(status_code=401, detail={"error": {"code": "UNAUTHORIZED", "message": "Invalid token"}})
    
    data = await request.json()
    # Handle callback queries and messages...
    return {"status": "ok"}
