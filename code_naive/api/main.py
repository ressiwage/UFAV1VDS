from fastapi import FastAPI, Depends, HTTPException, File, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from contextlib import asynccontextmanager
import hashlib, secrets, os, random, subprocess, tempfile
from pathlib import Path
from fastapi.middleware.cors import CORSMiddleware
from _shared._common.models.models import UserLogin, UserRegister, RefreshRequest, Base, User
from _shared._common.db.relational import engine, SessionLocal, get_db


ACCESS_TOKEN_TTL = int(os.getenv("ACCESS_TOKEN_TTL", 900))
DAV1D_PATH = os.environ.get("DAV1D_PATH", "dav1d")
FFMPEG_PATH = os.environ.get("FFMPEG_PATH", "ffmpeg")


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

@app.post("/upload")
async def upload_video(file: UploadFile = File(...)):
    """
    Принимает MP4/MKV (с AV1 видео), извлекает raw AV1 OBU через ffmpeg,
    декодирует первый кадр через dav1d и возвращает JPEG.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    ext = Path(file.filename).suffix.lower()
    if ext not in {".mp4", ".mkv", ".webm", ".mov"}:
        raise HTTPException(status_code=422, detail="Supported formats: MP4, MKV, WebM, MOV")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        input_path = tmp_path / f"input{ext}"
        obu_path = tmp_path / "stream.obu"
        y4m_path = tmp_path / "frame.y4m"

        # Сохраняем загруженный файл
        with open(input_path, "wb") as f:
            chunk = await file.read()
            f.write(chunk)

        # 1. Извлекаем raw AV1 OBU (Annex-B / OBU)
        result = subprocess.run(
            [
                FFMPEG_PATH,
                "-i", str(input_path),
                "-c:v", "copy",
                str(obu_path)
            ],
            capture_output=True,
            text=True,
        )
        print(result.stderr, result.stdout)

        if result.returncode != 0:
            raise HTTPException(
                status_code=422,
                detail=f"ffmpeg OBU extraction failed: {result.stderr.strip()}"
            )

        dec = subprocess.run(
            [
                DAV1D_PATH,
                "-i", str(obu_path),
                "-o", '/dev/null',
                "--threads", "1",
            ],
            capture_output=True,
            text=True,
        )
        print(dec.stdout, dec.stderr)


        if not obu_path.exists() or obu_path.stat().st_size == 0:
            raise HTTPException(status_code=422, detail="Failed to extract AV1 bitstream (empty OBU)")

        # 2. Декодируем первый кадр через dav1d
        result = subprocess.run(
            [
                DAV1D_PATH,
                "-i", str(obu_path),
                "-o", str(y4m_path),
                "--limit", "1",
                "--threads", "1",
            ],
            capture_output=True,
            text=True,
        )

        
        if result.returncode != 0:
            raise HTTPException(
                status_code=422,
                detail=f"dav1d decode failed: {result.stderr.strip()}"
            )

        if not y4m_path.exists() or y4m_path.stat().st_size == 0:
            raise HTTPException(status_code=422, detail="dav1d did not produce output frame")

        # 3. Конвертируем Y4M → JPEG
        frame_bytes = _y4m_to_jpeg(str(y4m_path))

    return Response(content=frame_bytes, media_type="image/jpeg")


def _y4m_to_jpeg(y4m_path: str, quality: int = 85) -> bytes:
    """Парсит первый кадр Y4M и возвращает JPEG."""
    import io
    from PIL import Image

    with open(y4m_path, "rb") as f:
        raw = f.read()

    # Заголовок файла
    header_end = raw.index(b"\n") + 1
    header = raw[:header_end].decode("ascii", errors="ignore").strip()

    # Парсим параметры (W1920 H1080 C420jpeg ...)
    params = {}
    for token in header.split():
        if token.startswith("W"):
            params["W"] = int(token[1:])
        elif token.startswith("H"):
            params["H"] = int(token[1:])
        elif token.startswith("C"):
            params["C"] = token[1:]

    width = params.get("W")
    height = params.get("H")
    color_space = params.get("C", "420")

    if not width or not height:
        raise ValueError("Не удалось определить разрешение из Y4M")

    # Находим начало первого FRAME
    frame_marker_pos = raw.find(b"FRAME", header_end)
    if frame_marker_pos == -1:
        raise ValueError("FRAME marker not found in Y4M")

    frame_start = raw.index(b"\n", frame_marker_pos) + 1

    # Обработка разных цветовых форматов
    if color_space.startswith("420"):
        y_size = width * height
        uv_size = (width // 2) * (height // 2)

        y = raw[frame_start : frame_start + y_size]
        u = raw[frame_start + y_size : frame_start + y_size + uv_size]
        v = raw[frame_start + y_size + uv_size : frame_start + y_size + uv_size * 2]

        y_plane = Image.frombytes("L", (width, height), y)
        u_plane = Image.frombytes("L", (width // 2, height // 2), u).resize((width, height), Image.BILINEAR)
        v_plane = Image.frombytes("L", (width // 2, height // 2), v).resize((width, height), Image.BILINEAR)

        img = Image.merge("YCbCr", (y_plane, u_plane, v_plane)).convert("RGB")

    elif color_space.startswith("444"):
        plane_size = width * height
        y = raw[frame_start : frame_start + plane_size]
        u = raw[frame_start + plane_size : frame_start + plane_size * 2]
        v = raw[frame_start + plane_size * 2 : frame_start + plane_size * 3]

        y_plane = Image.frombytes("L", (width, height), y)
        u_plane = Image.frombytes("L", (width, height), u)
        v_plane = Image.frombytes("L", (width, height), v)

        img = Image.merge("YCbCr", (y_plane, u_plane, v_plane)).convert("RGB")

    elif color_space.startswith(("mono", "400")):
        y = raw[frame_start : frame_start + width * height]
        img = Image.frombytes("L", (width, height), y).convert("RGB")
    else:
        raise ValueError(f"Неподдерживаемый цветовой формат: {color_space}")

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()


# ─── Root ─────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def index():
    return RedirectResponse(url="/docs/", status_code=307)