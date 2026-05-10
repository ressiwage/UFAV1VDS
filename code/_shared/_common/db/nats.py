import os
import nats
from nats.errors import TimeoutError
from nats.js import JetStreamContext
from nats.aio.client import Client
from typing import Tuple

NATS_URL = os.environ["NATS_URL"]
print(NATS_URL)

async def js_connect()  -> Tuple[JetStreamContext, Client]:
    nc = await nats.connect(NATS_URL)
    js = nc.jetstream()
    return js, nc