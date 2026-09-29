"""Bot hospital agents that log in as hospital_staff and accept/reject requests.
hospital_params.json drives: accept_prob, reject_reasons, occupancy churn,
confirmation ping frequency, deliberate staleness.
"""
import json
import asyncio
import random
import websockets

class SimHospital:
    def __init__(self, hospital_id: str, params: dict):
        self.hospital_id = hospital_id
        self.params = params
        self.is_active = False
    
    async def run(self, api_base_url: str) -> None:
        """Listen on WS for hospital.request.new events, decide accept/reject"""
        self.is_active = True
        ws_url = api_base_url.replace("http", "ws") + f"/ws/hospital/{self.hospital_id}"
        
        try:
            async with websockets.connect(ws_url) as websocket:
                while self.is_active:
                    message = await websocket.recv()
                    data = json.loads(message)
                    
                    if data.get("type") == "hospital.request.new":
                        accepted, reason = await self._decide_request(data)
                        response = {
                            "type": "hospital.request.response",
                            "request_id": data.get("request_id"),
                            "accepted": accepted,
                            "reason_code": reason
                        }
                        await asyncio.sleep(self.params.get("latency", 2.0))
                        await websocket.send(json.dumps(response))
                        
        except Exception as e:
            print(f"Hospital {self.hospital_id} error: {e}")
    
    async def _decide_request(self, request: dict) -> tuple[bool, str | None]:
        """Accept/reject based on params. Returns (accepted, reason_code)."""
        accept_prob = self.params.get("accept_prob", 0.9)
        if random.random() < accept_prob:
            return True, None
        return False, "capacity_full"
    
    async def _do_occupancy_churn(self, db) -> None:
        """Simulate beds being filled/freed to make nowcast interesting"""
        pass
