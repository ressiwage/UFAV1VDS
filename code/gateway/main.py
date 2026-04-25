from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, Form, File, Request, Response, Query, HTTPException, Header
from fastapi.responses import JSONResponse, RedirectResponse
from logic import server_rank_key, validate_bearer_via_common, issue_upload_otp
import asyncio, json, time, httpx, os
import redis.asyncio as aioredis
from contextlib import asynccontextmanager

redis_client: aioredis.Redis | None = None
@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_client
    redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
    yield
    await redis_client.aclose()

app = FastAPI(lifespan=lifespan)



# Хранилище состояний реплик
replicas: dict[str, dict] = {}
# { "api-1": { "url": "http://api-1:8001", "cpu": 34.2, "last_seen": 1713800000 } }
print(os.environ)
REDIS_URL = os.environ["REDIS_URL"]
FALLBACK_QUEUE = os.environ['QUEUEING_ROUTE']
COMMON_SERV = os.environ['COMMON_API'] #auth, archives
OTP_TTL = 60  # одноразовый токен живёт 60 секунд


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


@app.get("/upload")
async def upload_target(
    neccessary_ram: int = Query(...),    
    auth: str = Header(..., description="Bearer <access_token>"),
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

    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization header required")

    user = await validate_bearer_via_common(auth)

    otp = await issue_upload_otp(redis_client, user["id"], neccessary_ram, OTP_TTL)


    return {'url':f'{target_url}?token={otp}'}



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