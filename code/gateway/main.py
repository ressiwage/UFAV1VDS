from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, Form, File, Request, Response, Query, HTTPException, Header
from fastapi.responses import JSONResponse, RedirectResponse
from logic import server_rank_key, validate_bearer_via_common, issue_upload_otp
import asyncio, json, time, httpx, os
import redis.asyncio as aioredis
from nats.js import JetStreamContext
from contextlib import asynccontextmanager
from _shared._common.db.nats import js_connect
from nats.errors import TimeoutError as NTimeoutError
from fastapi.middleware.cors import CORSMiddleware


redis_client: aioredis.Redis | None = None
js: JetStreamContext

clients = {} # id:websocket
async def broadcast_loop():
    """Один цикл на всё приложение"""
    global js
    try:
        await js.add_stream(name="NOTIFS", subjects=["notifications"])
    except Exception:
        pass
    psub = await js.pull_subscribe('notifications')
    try:
        while True:
            try:
                msgs = await psub.fetch(batch=1, timeout=None)
                msg = msgs[0]
                await msg.ack()
                print(msgs, msg, clients)
            except NTimeoutError:
                await asyncio.sleep(1)
                continue

            if clients:
                dead = set()
                client_ = clients.get(json.loads(msg.data.decode())['user_id']) or clients.get(str(json.loads(msg.data.decode())['user_id']))
                if client_ is not None:
   
                    result = await client_.send_json({ **json.loads(msg.data.decode())})
                    if isinstance(result, Exception):
                        print(result)
                        dead.add(json.loads(msg.data.decode())['user_id'])
                
                for i in clients:
                    if i in dead:
                        del clients[i]

    finally:
        await psub.unsubscribe()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_client, js, nc 
    js, nc = await js_connect()
    redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
    asyncio.create_task(broadcast_loop())
    yield
    await redis_client.aclose()

app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # или ["*"] для дев
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
        print('disconnect')
        if replica_id:
            replicas.pop(replica_id, None)


@app.websocket("/ws/client_notification")
async def client_ws(ws: WebSocket, token: str = Query(...)):
    global clients
    print(clients, 'from ws')
    await ws.accept()
    print('accepted', 'from ws')
    user = await validate_bearer_via_common(f'Bearer {token}')
    if not user:
        await ws.send_json({"type": "error", "detail": "Unauthorized"})
        await ws.close(code=4001)
        return

    clients[user['id']] = ws
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        if user['id'] in clients:
            del clients[user['id']]


'''
^^^
import { useEffect, useRef, useState } from "react";

function useServerStream(token: string | null) {
  const [data, setData] = useState(null);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!token) return;

    const ws = new WebSocket(
      `wss://your-api.com/ws/client?token=${encodeURIComponent(token)}`
    );
    wsRef.current = ws;

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.type === "error") {
        setError(msg.detail);
        ws.close();
      } else if (msg.type === "update") {
        setData(msg);
      }
    };

    ws.onerror = () => setError("Connection error");

    ws.onclose = (event) => {
      if (event.code === 4001) setError("Unauthorized");
    };

    return () => ws.close();
  }, [token]);

  return { data, error };
}

'''


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
async def upload_target_old(
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

    print(request.method, url, request.headers)
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