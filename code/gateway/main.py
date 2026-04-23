from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, Form, File, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from logic import server_rank_key
import asyncio, json, time, httpx, os

app = FastAPI()

# Хранилище состояний реплик
replicas: dict[str, dict] = {}
# { "api-1": { "url": "http://api-1:8001", "cpu": 34.2, "last_seen": 1713800000 } }

FALLBACK_QUEUE = os.environ['QUEUEING_ROUTE']
COMMON_SERV = os.environ['COMMON_API'] #auth, archives

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
                replicas[replica_id] = {**replicas[replica_id], **msg}
                replicas[replica_id]["last_seen"] = time.time()

    except WebSocketDisconnect:
        if replica_id:
            replicas.pop(replica_id, None)


STALE_TIMEOUT = 10  # секунд без heartbeat — реплика считается мёртвой

@app.post("/upload")
async def upload_target(
    file: UploadFile = File(...),
    neccessary_ram: int = Form(...) # в байтах
):
    '''проксирование запросов на декодирование на реплики'''
    now = time.time()
    alive = {
        rid: data for rid, data in replicas.items()
        if now - data["last_seen"] < STALE_TIMEOUT
    }
    if not alive:
        return JSONResponse({"error": "no replicas available"}, status_code=503)
    print(alive)
    ranked = sorted(list(replicas.values()), key=server_rank_key)
    for i in ranked:
        if i['ram'] >= neccessary_ram:
            return RedirectResponse(
                url=f"{i['url']}/process",
                status_code=307 
            )
    
    return RedirectResponse(
        url=FALLBACK_QUEUE,
        status_code=307 
    )


@app.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"]
)
async def proxy(path: str, request: Request):
    '''всё остальное втупую проксируем на основное апи'''
    url = f"{COMMON_SERV}/{path}"
    if request.url.query:
        url += f"?{request.url.query}"

    async with httpx.AsyncClient() as client:
        response = await client.request(
            method=request.method,
            url=url,
            headers={k: v for k, v in request.headers.items()
                     if k.lower() != "host"},
            content=request.stream(),
            timeout=30.0
        )

    return Response(
        content=response.content,
        status_code=response.status_code,
        headers=dict(response.headers),
        media_type=response.headers.get("content-type")
    )