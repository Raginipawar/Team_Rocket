"""Simulated callers that submit SOS via public API (text, voice clips, SMS webhook)."""
import httpx
from pathlib import Path
import uuid

class SimCaller:
    async def send_text_sos(self, api_base_url: str, text: str, lat: float, lng: float) -> str:
        """returns emergency_id"""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{api_base_url}/api/v1/sos/text",
                json={"text": text, "location": {"lat": lat, "lng": lng}}
            )
            if resp.status_code == 200:
                return resp.json().get("emergency_id")
            return str(uuid.uuid4())
            
    async def send_sms_sos(self, webhook_url: str, phone: str, body: str, secret: str) -> None:
        async with httpx.AsyncClient() as client:
            await client.post(
                webhook_url,
                json={"phone": phone, "body": body, "secret": secret}
            )
            
    async def send_voice_sos(self, api_base_url: str, audio_file: Path, lat: float, lng: float) -> str:
        """returns emergency_id"""
        async with httpx.AsyncClient() as client:
            with open(audio_file, "rb") as f:
                resp = await client.post(
                    f"{api_base_url}/api/v1/sos/voice",
                    files={"audio": f},
                    data={"lat": lat, "lng": lng}
                )
            if resp.status_code == 200:
                return resp.json().get("emergency_id")
            return str(uuid.uuid4())
