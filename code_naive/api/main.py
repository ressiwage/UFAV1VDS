from fastapi import FastAPI, Depends, HTTPException, File, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from contextlib import asynccontextmanager
import hashlib, secrets, os, random, subprocess, tempfile
import redis.asyncio as aioredis
from nats.js import JetStreamContext
from nats.aio.client import Client
from fastapi.middleware.cors import CORSMiddleware

from _shared._common.models.models import UserLogin, UserRegister, RefreshRequest, Base, User
from _shared._common.db.relational import engine, SessionLocal, get_db


ACCESS_TOKEN_TTL = int(os.getenv("ACCESS_TOKEN_TTL", 900))
DAV1D_PATH = os.environ.get("DAV1D_PATH", "")
FFMPEG_PATH = 'FFMPEG'



# ─── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    
    yield



app = FastAPI(lifespan=lifespan)
security = HTTPBearer()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
):
    token = credentials.credentials



    result = await db.execute(select(User).where(User.access_token == token))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


    return {"id": user.id, "username": user.name}


# ─── Auth routes ──────────────────────────────────────────────────────────────

@app.post("/register")
async def register(body: UserRegister, db: AsyncSession = Depends(get_db)):
    user = User(
        id=str(random.randint(10**35, 10**36 - 1)),
        name=body.username,
        pwd_hash=hash_password(body.password),
        n_mail=False, n_phone=False, n_TG=False,
        cn_mail=False, cn_phone=False, cn_TG=False,
    )
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
            User.name == body.username,
            User.pwd_hash == hash_password(body.password),
        )
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token = secrets.token_urlsafe(32)
    refresh_token = secrets.token_urlsafe(48)

    user.access_token = access_token
    user.refresh_token = refresh_token
    await db.commit()


    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_TTL,
    }


@app.post("/refresh")
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.refresh_token == body.refresh_token))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    new_access = secrets.token_urlsafe(32)
    new_refresh = secrets.token_urlsafe(48)

    user.access_token = new_access
    user.refresh_token = new_refresh
    await db.commit()


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


# ─── Video routes ─────────────────────────────────────────────────────────────
import io
from PIL import Image
@app.post("/upload")
async def upload_video(file: UploadFile = File(...)):
    """Принимает MP4/MKV с AV1-видео, извлекает OBU-поток через ffmpeg,
    декодирует первый кадр через dav1d и возвращает его в виде JPEG."""
    with tempfile.TemporaryDirectory() as tmpdir:
        input_container = os.path.join(tmpdir, "input." + file.filename.split('.')[-1])
        with open(input_container, "wb") as f:
            while chunk := await file.read(8192):
                f.write(chunk)
        obu_path = os.path.join(tmpdir, "stream.obu")
        result = subprocess.run(
            [FFMPEG_PATH, "-i", input_container, "-c", "copy", "-f", "av1", obu_path],
            capture_output=True,
        )
        if result.returncode != 0:
            raise HTTPException(
                status_code=422,
                detail=f"ffmpeg conversion to OBU failed: {result.stderr.decode()}"
            )
        result = subprocess.run(
            [DAV1D_PATH, "-i", obu_path, "-o", "/dev/null"],
            capture_output=True,
        )
        if result.returncode != 0:
            raise HTTPException(
                status_code=422,
                detail=f"dav1d decode failed: {result.stderr.decode()}",
            )
        frame_y4m = os.path.join(tmpdir, "frame.y4m")
        result = subprocess.run(
            [DAV1D_PATH, "-i", obu_path, "-o", frame_y4m, "--threads", "1", "--limit", "1"],
            capture_output=True,
        )
        if result.returncode != 0:
            raise HTTPException(
                status_code=422,
                detail=f"dav1d first-frame decode failed: {result.stderr.decode()}",
            )    
        frame_bytes = _y4m_to_jpeg(frame_y4m)
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

# ─── Root ─────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def index():
    return RedirectResponse(url="/docs/", status_code=307)