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
from _shared._common.db.relational import engine, SessionLocal, get_db
from _shared._common.db.redis import redis_client, REDIS_URL
from _shared._common.db.nats import js_connect
from _shared._common.models.models import UserLogin, UserRegister, Base
from nats.js import JetStreamContext
from fastapi.middleware.cors import CORSMiddleware



DAV1D_PATH = os.environ.get('DAV1D_PATH', '')

js: JetStreamContext

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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # или ["*"] для дев
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
async def upload_video_old(
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





import io
from PIL import Image

@app.post("/upload")
async def upload_video(
    file: UploadFile = File(...),
    token: str = Query(..., description="Одноразовый токен из /upload/token"),
    # current_user: dict = Depends(get_current_user),
):
    """Принимает AV1-видео, декодирует через dav1d и возвращает первый кадр в виде JPEG."""
    print(file)
    payload = await consume_upload_otp(redis_client, token)
    necessary_ram = payload["necessary_ram"]
    print(payload)
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, "input.obu")

        with open(input_path, "wb") as f:
            while chunk := await file.read(8192):
                f.write(chunk)

        # Шаг 1: декодируем весь поток в /dev/null (прогрев / валидация)
        result = subprocess.run(
            [DAV1D_PATH, "-i", input_path, "-o", "/dev/null"],
            capture_output=True,
        )
        if result.returncode != 0:
            raise HTTPException(
                status_code=422,
                detail=f"dav1d decode failed: {result.stderr.decode()}",
            )

        # Шаг 2: декодируем только первый кадр в y4m-контейнер
        frame_y4m = os.path.join(tmpdir, "frame.y4m")
        result = subprocess.run(
            [DAV1D_PATH, "-i", input_path, "-o", frame_y4m, "--threads", "1", "--limit", "1"],
            capture_output=True,
        )
        if result.returncode != 0:
            raise HTTPException(
                status_code=422,
                detail=f"dav1d first-frame decode failed: {result.stderr.decode()}",
            )

        # Шаг 3: читаем y4m и конвертируем в JPEG через Pillow
        frame_bytes = _y4m_to_jpeg(frame_y4m)
    try:
        await js.add_stream(name="NOTIFS", subjects=["notifications"])
    except Exception:
        pass
    await js.publish('notifications', payload = json.dumps({'user_id':payload['user_id'], 'payload':'123 test'}).encode())
    return Response(content=frame_bytes, media_type="image/jpeg")


def _y4m_to_jpeg(y4m_path: str, quality: int = 85) -> bytes:
    """Парсит первый кадр из Y4M-файла и возвращает JPEG-байты."""
    with open(y4m_path, "rb") as f:
        raw = f.read()

    # --- разбор заголовка файла ---
    header_end = raw.index(b"\n")
    header = raw[:header_end].decode()
    # пример: YUV4MPEG2 W1920 H1080 F30:1 Ip A0:0 C420jpeg
    params = {
        token[0]:token[1:]
        for token in header.split()
        if len(token) > 1 and token[0] in "WHC"
    }
    width = int(params["W"])
    height = int(params["H"])
    color_space = params.get("C", "420")  # 420 / 444 / mono …

    # --- первый кадр ---
    frame_start = raw.index(b"FRAME", header_end) + len(b"FRAME")
    # пропускаем необязательные параметры кадра до \n
    frame_start = raw.index(b"\n", frame_start) + 1

    if color_space.startswith("420"):
        y_size = width * height
        uv_size = (width // 2) * (height // 2)
        y  = raw[frame_start : frame_start + y_size]
        cb = raw[frame_start + y_size : frame_start + y_size + uv_size]
        cr = raw[frame_start + y_size + uv_size : frame_start + y_size + uv_size * 2]

        y_plane  = Image.frombytes("L", (width, height), y)
        cb_plane = Image.frombytes("L", (width // 2, height // 2), cb).resize((width, height), Image.BILINEAR)
        cr_plane = Image.frombytes("L", (width // 2, height // 2), cr).resize((width, height), Image.BILINEAR)
        img = Image.merge("YCbCr", (y_plane, cb_plane, cr_plane)).convert("RGB")

    elif color_space.startswith("444"):
        plane_size = width * height
        y  = raw[frame_start : frame_start + plane_size]
        cb = raw[frame_start + plane_size : frame_start + plane_size * 2]
        cr = raw[frame_start + plane_size * 2 : frame_start + plane_size * 3]

        y_plane  = Image.frombytes("L", (width, height), y)
        cb_plane = Image.frombytes("L", (width, height), cb)
        cr_plane = Image.frombytes("L", (width, height), cr)
        img = Image.merge("YCbCr", (y_plane, cb_plane, cr_plane)).convert("RGB")

    elif color_space.startswith("mono"):
        y = raw[frame_start : frame_start + width * height]
        img = Image.frombytes("L", (width, height), y).convert("RGB")

    else:
        raise ValueError(f"Неподдерживаемый цветовой формат Y4M: {color_space}")

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


@app.get("/videos")
def get_videos(current_user: dict = Depends(get_current_user)):
    return {"archive_1": ["video_1", "video_2"], "archive_2": ["video_3"]}


@app.get("/", response_class=HTMLResponse)
def index():
    return "<html><body></body></html>"