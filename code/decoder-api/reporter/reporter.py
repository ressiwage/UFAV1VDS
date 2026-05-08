import asyncio, psutil, websockets, os, json
from utils.hw import get_avg_load, get_cpu_count, get_free_disk, get_free_ram

GATEWAY_WS = os.environ["GATEWAY_WS_URL"]  # ws://gateway:8080/ws/replica
REPLICA_ID  = os.environ["REPLICA_ID"]      # api-1, api-2, ...
PUBLIC_URL  = os.environ["PUBLIC_URL"]       # http://api-1:8001

async def report_loop():
    print("создаю хуйню")
    async with websockets.connect(GATEWAY_WS) as ws:
        # Регистрация
        await ws.send(json.dumps({
            "type": "register",
            "id": REPLICA_ID,
            "url": PUBLIC_URL
        }))
        while True:
            payload = json.dumps({
                "type": "heartbeat",
                "id": REPLICA_ID,
                "cpu": get_avg_load(),
                "ram": get_free_ram(),
                "num_cpu": get_cpu_count(),
                "disk": get_free_disk()
            })
            # print('sending payload', payload)
            await ws.send(payload)
            await asyncio.sleep(2)