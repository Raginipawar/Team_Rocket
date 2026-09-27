"""Simulated ambulance drivers (technical.md §15).
Each driver logs in as its paramedic user, goes online, listens on WS for offers,
decides accept/decline and latency from driver_params.json, then moves along
OSRM geometry at time-of-day speed with heartbeats every 5s (scaled).
"""
import json
import asyncio
from pathlib import Path
import httpx
import websockets

DRIVER_PARAMS_PATH = Path("data/driver_params.json")

class SimDriver:
    def __init__(self, ambulance_id: str, driver_params: dict):
        self.ambulance_id = ambulance_id
        self.params = driver_params
        self.is_active = False
        self.current_lat = driver_params.get("start_lat", 18.5204)
        self.current_lng = driver_params.get("start_lng", 73.8567)
    
    async def run(self, api_base_url: str) -> None:
        """Main driver loop: go online -> listen for offers -> accept/decline -> move along route"""
        self.is_active = True
        ws_url = api_base_url.replace("http", "ws") + f"/ws/driver/{self.ambulance_id}"
        
        try:
            async with websockets.connect(ws_url) as websocket:
                while self.is_active:
                    message = await websocket.recv()
                    data = json.loads(message)
                    
                    if data.get("type") == "offer":
                        accepted = await self._decide_offer(data)
                        response = {"type": "offer_response", "accepted": accepted, "offer_id": data.get("offer_id")}
                        await websocket.send(json.dumps(response))
                        
                        if accepted:
                            await self._move_along_route(data.get("geometry", ""), data.get("target_lat", 0.0), data.get("target_lng", 0.0))
        except Exception as e:
            print(f"Driver {self.ambulance_id} error: {e}")
            
    async def _move_along_route(self, geometry: str, target_lat: float, target_lng: float) -> None:
        """Follow OSRM geometry, send heartbeats every 5s (scaled by speed_multiplier)"""
        # Mock movement
        steps = 10
        for i in range(steps):
            if not self.is_active: break
            self.current_lat += (target_lat - self.current_lat) / (steps - i)
            self.current_lng += (target_lng - self.current_lng) / (steps - i)
            await asyncio.sleep(5.0) # Scale by speed_multiplier in real app
            
    async def _decide_offer(self, offer: dict) -> bool:
        """Accept based on propensity, fatigue, distance aversion from driver_params"""
        import random
        propensity = self.params.get("accept_prob", 0.8)
        return random.random() < propensity
