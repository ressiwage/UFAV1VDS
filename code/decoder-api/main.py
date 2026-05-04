import asyncio
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

from _shared._common.db.relational import engine
from _shared._common.db.redis import REDIS_URL
from _shared._common.db.nats import js_connect
from _shared._common.models.models import Base
from reporter.reporter import report_loop

from routers import auth, user, video
from db import dependencies


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    dependencies.redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)

    js, nc = await js_connect()
    try:
        await js.find_stream_name_by_subject("events.>")
    except Exception:
        await js.add_stream(name="events", subjects=["events.>"])

    await js.publish("events.startup", b"service started")
    asyncio.create_task(report_loop())

    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(user.router)
app.include_router(video.router)


@app.get("/", response_class=HTMLResponse)
def index():
    return "<html><body></body></html>"