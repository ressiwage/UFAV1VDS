from fastapi import FastAPI, Depends, HTTPException, File, UploadFile, Query
from fastapi.responses import HTMLResponse, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import mysql.connector
import hashlib, asyncio, json
import secrets
import subprocess
import tempfile
import os
from reporter.reporter import report_loop
from contextlib import asynccontextmanager
import redis.asyncio as aioredis
from _common.db.relational import engine, SessionLocal, get_db
from _common.db.redis import redis_client, REDIS_URL
from _common.db.nats import js_connect
from _common.models.models import UserLogin, UserRegister, Base

DAV1D_PATH = os.environ.get('DAV1D_PATH', '')


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
    asyncio.create_task(report_loop())

    yield

app = FastAPI(lifespan=lifespan)
security = HTTPBearer()


# ─── Helpers ───────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    conn=Depends(get_db),
):
    token = credentials.credentials
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, username FROM users WHERE token = %s", (token,))
    user = cursor.fetchone()
    cursor.close()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user

async def consume_upload_otp(redis_client, token: str) -> dict:
    """
    Атомарно читает и удаляет токен (GETDEL).
    Возвращает payload или кидает 401.
    """
    raw = await redis_client.getdel(f"otp:upload:{token}")
    if raw is None:
        raise HTTPException(status_code=401, detail="Invalid or expired upload token")
    return json.loads(raw)

# ─── Routes ────────────────────────────────────────────────────────────────────


@app.post("/register")
def register(user: UserRegister, conn=Depends(get_db)):
    cursor = conn.cursor()
    try:
        hashed = hash_password(user.password)
        cursor.execute(
            "INSERT INTO users (username, password) VALUES (%s, %s)",
            (user.username, hashed),
        )
        conn.commit()
        return {"status": "ok"}
    except mysql.connector.IntegrityError:
        raise HTTPException(status_code=400, detail="User exists")
    finally:
        cursor.close()


@app.post("/login")
def login(user: UserLogin, conn=Depends(get_db)):
    cursor = conn.cursor(dictionary=True)
    hashed = hash_password(user.password)
    cursor.execute(
        "SELECT id FROM users WHERE username = %s AND password = %s",
        (user.username, hashed),
    )
    result = cursor.fetchone()
    if not result:
        cursor.close()
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = secrets.token_urlsafe(32)
    cursor.execute("UPDATE users SET token = %s WHERE id = %s", (token, result["id"]))
    conn.commit()
    cursor.close()
    return {"token": token}


@app.get("/user")
def get_user(current_user: dict = Depends(get_current_user)):
    return current_user


@app.post("/upload_old")
async def upload_video(
    file: UploadFile = File(...),
    # current_user: dict = Depends(get_current_user),
):
    """
    Принимает AV1-видео, декодирует через ffmpeg (libaom) и возвращает
    последний кадр в виде JPEG.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, "input.av1")
        output_path = os.path.join(tmpdir, "last_frame.jpg")

        # Сохраняем загруженный файл чанками
        with open(input_path, "wb") as f:
            while chunk := await file.read(8192):
                f.write(chunk)

        # ffmpeg: декодируем AV1 → извлекаем последний кадр
        # -sseof -0.1  перематывает к концу файла, затем берём 1 кадр
        cmd = [
            "ffmpeg",
            "-y",
            "-c:v", "libdav1d",   # явно указываем декодер
            "-i", input_path,
            "-sseof", "-10",        # перемотка к концу
            "-vframes", "1",         # один кадр
            "-q:v", "2",             # качество JPEG
            output_path,
        ]
        result = subprocess.run(cmd, capture_output=True)

        if result.returncode != 0:
            # Если -sseof не дал кадра (очень короткое видео), пробуем без него
            cmd_fallback = [
                "ffmpeg",
                "-y",
                "-c:v", "libdav1d",
                "-i", input_path,
                "-vf", "thumbnail",  # выбирает «лучший» кадр (часто последний)
                "-vframes", "1",
                "-q:v", "2",
                output_path,
            ]
            result2 = subprocess.run(cmd_fallback, capture_output=True)
            if result2.returncode != 0:
                raise HTTPException(
                    status_code=422,
                    detail=f"FFmpeg failed: {result2.stderr.decode()}",
                )

        with open(output_path, "rb") as f:
            frame_bytes = f.read()

    return Response(content=frame_bytes, media_type="image/jpeg")


@app.post("/upload")
async def upload_video(
    file: UploadFile = File(...),
    upload_token: str = Query(..., description="Одноразовый токен из /upload/token"),
    # current_user: dict = Depends(get_current_user),
):
    """
    Принимает AV1-видео, декодирует через ffmpeg (libaom) и возвращает
    последний кадр в виде JPEG.
    """
    payload = await consume_upload_otp(redis_client, upload_token)
    necessary_ram = payload["necessary_ram"]
    print(payload)
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, "input.av1")
        output_path = os.path.join(tmpdir, "last_frame.jpg")

        # Сохраняем загруженный файл чанками
        with open(input_path, "wb") as f:
            while chunk := await file.read(8192):
                f.write(chunk)

        # ffmpeg: декодируем AV1 → извлекаем последний кадр
        # -sseof -0.1  перематывает к концу файла, затем берём 1 кадр
        cmd = [
            "ffmpeg",
            "-y",
            "-c:v", "libdav1d",   # явно указываем декодер
            "-i", input_path,
            "-sseof", "-10",        # перемотка к концу
            "-vframes", "1",         # один кадр
            "-q:v", "2",             # качество JPEG
            output_path,
        ]
        result = subprocess.run(cmd, capture_output=True)

        if result.returncode != 0:
            # Если -sseof не дал кадра (очень короткое видео), пробуем без него
            cmd_fallback = [
                "ffmpeg",
                "-y",
                "-c:v", "libdav1d",
                "-i", input_path,
                "-vf", "thumbnail",  # выбирает «лучший» кадр (часто последний)
                "-vframes", "1",
                "-q:v", "2",
                output_path,
            ]
            result2 = subprocess.run(cmd_fallback, capture_output=True)
            if result2.returncode != 0:
                raise HTTPException(
                    status_code=422,
                    detail=f"FFmpeg failed: {result2.stderr.decode()}",
                )

        with open(output_path, "rb") as f:
            frame_bytes = f.read()

    return Response(content=frame_bytes, media_type="image/jpeg")


@app.get("/videos")
def get_videos(current_user: dict = Depends(get_current_user)):
    return {"archive_1": ["video_1", "video_2"], "archive_2": ["video_3"]}


@app.get("/", response_class=HTMLResponse)
def index():
    return "<html><body></body></html>"