# gateway/main.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
import asyncio, json, time

app = FastAPI()

# Хранилище состояний реплик
replicas: dict[str, dict] = {}
# { "api-1": { "url": "http://api-1:8001", "cpu": 34.2, "last_seen": 1713800000 } }

@app.websocket("/ws/replica")
async def replica_ws(ws: WebSocket):
    await ws.accept()
    replica_id = None
    try:
        async for raw in ws.iter_text():
            msg = json.loads(raw)

            if msg["type"] == "register":
                replica_id = msg["id"]
                replicas[replica_id] = {
                    "url": msg["url"],
                    "cpu": 0,
                    "last_seen": time.time()
                }

            elif msg["type"] == "heartbeat" and replica_id:
                replicas[replica_id]["cpu"] = msg["cpu"]
                replicas[replica_id]["last_seen"] = time.time()

    except WebSocketDisconnect:
        if replica_id:
            replicas.pop(replica_id, None)


STALE_TIMEOUT = 10  # секунд без heartbeat — реплика считается мёртвой

@app.get("/upload-target")
def upload_target():
    now = time.time()
    alive = {
        rid: data for rid, data in replicas.items()
        if now - data["last_seen"] < STALE_TIMEOUT
    }
    if not alive:
        return JSONResponse({"error": "no replicas available"}, status_code=503)
    print(alive)
    best = min(alive.items(), key=lambda x: x[1]["cpu"])
    return {"url": best[1]["url"]}