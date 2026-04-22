Да, FastAPI добавляет лишний слой. Для gateway, который делает **только** `/upload-target` и держит WebSocket соединения, это избыточно.

## Варианты

### 1. Чистый `asyncio` + `aiohttp` / `websockets`

Минимальный HTTP сервер без фреймворка:

```python
# gateway/main.py
import asyncio, json, time
from aiohttp import web, WSMsgType

replicas: dict[str, dict] = {}
STALE = 10

# --- WebSocket для реплик ---
async def replica_ws(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    replica_id = None

    async for msg in ws:
        if msg.type == WSMsgType.TEXT:
            data = json.loads(msg.data)

            if data["type"] == "register":
                replica_id = data["id"]
                replicas[replica_id] = {
                    "url": data["url"], "cpu": 0, "last_seen": time.time()
                }
            elif data["type"] == "heartbeat" and replica_id:
                replicas[replica_id]["cpu"] = data["cpu"]
                replicas[replica_id]["last_seen"] = time.time()

        elif msg.type == WSMsgType.ERROR:
            break

    if replica_id:
        replicas.pop(replica_id, None)
    return ws

# --- HTTP для фронтенда ---
async def upload_target(request):
    now = time.time()
    alive = {r: d for r, d in replicas.items() if now - d["last_seen"] < STALE}

    if not alive:
        return web.Response(status=503, text="no replicas")

    best = min(alive.values(), key=lambda x: x["cpu"])
    return web.json_response({"url": best["url"]})

app = web.Application()
app.router.add_get("/ws/replica", replica_ws)
app.router.add_get("/upload-target", upload_target)

if __name__ == "__main__":
    web.run_app(app, port=8080)
```

`aiohttp` — это голый event loop без middleware стека FastAPI. Латентность `/upload-target` будет ~0.1-0.3ms против ~1-2ms у FastAPI.

---

### 2. Если нужно ещё быстрее — `uvloop` + голый `asyncio`

```python
import uvloop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
web.run_app(app, port=8080, loop=uvloop.new_event_loop())
```

`uvloop` заменяет стандартный event loop на реализацию поверх `libuv` (тот же что в Node.js), даёт ещё 30-50% к throughput.

---

### 3. Если gateway под очень высокой нагрузкой — вынести на Go

```go
// Весь gateway в ~60 строк
var replicas sync.Map // map[string]*Replica

func uploadTarget(w http.ResponseWriter, r *http.Request) {
    var best *Replica
    replicas.Range(func(_, v any) bool {
        r := v.(*Replica)
        if time.Since(r.LastSeen) > 10*time.Second { return true }
        if best == nil || r.CPU < best.CPU { best = r }
        return true
    })
    if best == nil { http.Error(w, "no replicas", 503); return }
    json.NewEncoder(w).Encode(map[string]string{"url": best.URL})
}
```

Go здесь даёт нативные горутины и отсутствие GIL — при тысячах concurrent WebSocket соединений это важно.

---

## Что выбрать

| Нагрузка | Решение |
|---|---|
| до ~500 rps | aiohttp достаточно |
| 500–5000 rps | aiohttp + uvloop |
| 5000+ rps / много реплик | Go |

Для большинства задач **aiohttp + uvloop** — оптимальный баланс между простотой и производительностью. Go оправдан только если gateway реально становится узким местом.