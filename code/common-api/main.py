from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, select
import hashlib
import secrets
import os
import redis.asyncio as aioredis
from nats.js import JetStreamContext
from nats.aio.client import Client
from contextlib import asynccontextmanager
from _common.models.models import UserLogin, UserRegister, RefreshRequest, Base, User
from _common.db.relational import engine, SessionLocal, get_db
from _common.db.redis import redis_client, REDIS_URL
from _common.db.nats import js_connect

# ACCESS_TOKEN_TTL — время жизни access-токена в секундах (15 минут)
ACCESS_TOKEN_TTL = int(os.getenv("ACCESS_TOKEN_TTL", 900))


nc: Client|None = None
js: JetStreamContext | None = None


# ─── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_client, nc, js

    # Инициализация БД
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Инициализация Redis
    redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)

    # Инициализация NATS + JetStream
    js, nc = await js_connect()

    # Создаём stream если не существует (базовый пример)
    try:
        await js.find_stream_name_by_subject("events.>")
    except Exception:
        await js.add_stream(name="events", subjects=["events.>"])

    # Публикуем тестовое сообщение при старте
    await js.publish("events.startup", b"service started")

    yield

    # Cleanup
    await redis_client.aclose()
    await nc.drain()


app = FastAPI(lifespan=lifespan)
security = HTTPBearer()




# ─── Helpers ──────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
):
    token = credentials.credentials

    # 1. Сначала смотрим в Redis (быстрый путь)
    cached_user_id = await redis_client.get(f"access:{token}")
    if cached_user_id:
        # Достаём username из второго ключа
        username = await redis_client.get(f"user_id:{cached_user_id}:username")
        if username:
            return {"id": int(cached_user_id), "username": username}

    # 2. Промах кэша — идём в БД
    result = await db.execute(
        select(User).where(User.access_token == token)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    # Прогреваем кэш для следующих запросов
    await redis_client.setex(f"access:{token}", ACCESS_TOKEN_TTL, user.id)
    await redis_client.setex(f"user_id:{user.id}:username", ACCESS_TOKEN_TTL, user.username)

    return {"id": user.id, "username": user.username}


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.post("/register")
async def register(body: UserRegister, db: AsyncSession = Depends(get_db)):
    user = User(username=body.username, password=hash_password(body.password))
    db.add(user)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=400, detail="User already exists")
    return {"status": "ok"}


@app.post("/login")
async def login(body: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User).where(
            User.username == body.username,
            User.password == hash_password(body.password),
        )
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token = secrets.token_urlsafe(32)
    refresh_token = secrets.token_urlsafe(48)

    # Инвалидируем старый access-токен в Redis если был
    if user.access_token:
        await redis_client.delete(f"access:{user.access_token}")

    user.access_token = access_token
    user.refresh_token = refresh_token
    await db.commit()

    # Кэшируем новый access-токен
    await redis_client.setex(f"access:{access_token}", ACCESS_TOKEN_TTL, user.id)
    await redis_client.setex(f"user_id:{user.id}:username", ACCESS_TOKEN_TTL, user.username)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_TTL,
    }


@app.post("/refresh")
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """Обменивает refresh_token на новую пару токенов."""
    result = await db.execute(
        select(User).where(User.refresh_token == body.refresh_token)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    # Инвалидируем старый access-токен в Redis
    if user.access_token:
        await redis_client.delete(f"access:{user.access_token}")

    new_access = secrets.token_urlsafe(32)
    new_refresh = secrets.token_urlsafe(48)

    user.access_token = new_access
    user.refresh_token = new_refresh
    await db.commit()

    await redis_client.setex(f"access:{new_access}", ACCESS_TOKEN_TTL, user.id)
    await redis_client.setex(f"user_id:{user.id}:username", ACCESS_TOKEN_TTL, user.username)

    return {
        "access_token": new_access,
        "refresh_token": new_refresh,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_TTL,
    }


@app.post("/logout")
async def logout(
    current_user: dict = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
):
    token = credentials.credentials
    await redis_client.delete(f"access:{token}")
    await redis_client.delete(f"user_id:{current_user['id']}:username")

    result = await db.execute(select(User).where(User.id == current_user["id"]))
    user = result.scalar_one_or_none()
    if user:
        user.access_token = None
        user.refresh_token = None
        await db.commit()

    return {"status": "ok"}


@app.get("/user")
async def get_user(current_user: dict = Depends(get_current_user)):
    return current_user


@app.get("/videos")
async def get_videos(current_user: dict = Depends(get_current_user)):
    return {"archive_1": ["video_1", "video_2"], "archive_2": ["video_3"]}


@app.get("/", response_class=HTMLResponse)
def index():
    return RedirectResponse(url="/docs/", status_code=307)