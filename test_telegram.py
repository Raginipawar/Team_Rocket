import asyncio
import httpx
import os

TELEGRAM_BOT_TOKEN = "8601512992:AAGCwTItRVvPG1VucJc_dJQ-NZlmdSDXu9U"
TELEGRAM_GROUP_CHAT_ID = "-1004301736544"

async def test_telegram():
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_GROUP_CHAT_ID,
        "text": "Hello from GoldenHour Ops! The bot integration is successfully connected and group privacy is correctly configured."
    }
    
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.post(url, json=payload)
        print("Status Code:", response.status_code)
        print("Response:", response.text)

if __name__ == '__main__':
    asyncio.run(test_telegram())
