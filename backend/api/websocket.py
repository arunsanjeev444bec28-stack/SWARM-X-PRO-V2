import json
from typing import List
from fastapi import WebSocket, WebSocketDisconnect

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        from datetime import datetime, timezone
        from core.state import global_state
        if "timestamp" not in message:
            message = {**message, "timestamp": datetime.now(timezone.utc).isoformat()}
        global_state.events.append(message)
        global_state.events = global_state.events[-1000:]
        text_data = json.dumps(message)
        for connection in self.active_connections:
            try:
                await connection.send_text(text_data)
            except Exception:
                pass

manager = ConnectionManager()
