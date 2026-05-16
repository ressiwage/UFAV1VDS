import asyncio, psutil, websockets, os, json, time
from utils.hw import get_avg_load, get_cpu_count, get_free_disk, get_free_ram

IPS = {
  'msk-1-vm-zcps': '194.87.131.81',
  '7624415-eg826155.twc1.net': '72.56.39.104',
  'default': 'localhost'
}
GATEWAY_WS = os.environ["GATEWAY_WS_URL"]  # ws://gateway:8080/ws/replica
REPLICA_ID  = os.environ["REPLICA_ID"]      # api-1, api-2, ...
PUBLIC_URL  = f"http://{IPS[os.environ['HOSTNAME']]}:7948"       # http://api-1:8001

async def report_loop():
    print("создаю хуйню")
    while True:
        try:
            print(f'регистрирую хуйню {GATEWAY_WS} {REPLICA_ID} {PUBLIC_URL}')
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
                    await asyncio.sleep(0.2)
        except:
            time.sleep(1)
        break