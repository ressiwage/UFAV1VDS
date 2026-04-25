from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, Form, File, Request, Response, Query
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

@app.post("/upload",openapi_extra={
        "requestBody": {
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "file": {
                                "type": "string",
                                "format": "binary",
                            }
                        },
                        "required": ["file"],
                    }
                }
            }
        }
    },)
async def upload_target(
    request: Request,
    neccessary_ram: int = Query(...),
    
):
    now = time.time()
    alive = {
        rid: data for rid, data in replicas.items()
        if now - data["last_seen"] < STALE_TIMEOUT
    }
    if not alive:
        return JSONResponse({"error": "no replicas available"}, status_code=503)

    ranked = sorted(list(alive.values()), key=server_rank_key)

    target_url = None
    for i in ranked:
        if i["ram"] >= neccessary_ram:
            target_url = f"{i['url']}/upload"
            break

    if target_url is None:
        target_url = f"{FALLBACK_QUEUE}/upload"

    headers = {
        key: value for key, value in request.headers.items()
        if key.lower() in ("content-type", "content-length")
    }

    async def body_stream():
        async for chunk in request.stream():
            yield chunk

    async with httpx.AsyncClient(timeout=None) as client:
        resp = await client.post(
            target_url,
            content=body_stream(),
            headers=headers,
        )

    return Response(
        content=resp.content,
        status_code=resp.status_code,
        media_type=resp.headers.get("content-type"),
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