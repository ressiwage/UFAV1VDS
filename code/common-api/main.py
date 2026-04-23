from fastapi import FastAPI, Depends, HTTPException, File, UploadFile, RedirectResponse
from fastapi.responses import HTMLResponse, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import mysql.connector
import hashlib, asyncio
import secrets
import subprocess
import tempfile
import os
from contextlib import asynccontextmanager



@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()   # создаёт таблицу users если её нет
    yield

app = FastAPI(lifespan=lifespan)
security = HTTPBearer()

# ─── MySQL connection ───────────────────────────────────────────────────────────

def get_rdb():
    conn = mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "db"),
        port=int(os.getenv("MYSQL_PORT", 3306)),
        user=os.getenv("MYSQL_USER", "appuser"),
        password=os.getenv("MYSQL_PASSWORD", "apppassword"),
        database=os.getenv("MYSQL_DATABASE", "appdb"),
    )
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    conn = mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "db"),
        port=int(os.getenv("MYSQL_PORT", 3306)),
        user=os.getenv("MYSQL_USER", "appuser"),
        password=os.getenv("MYSQL_PASSWORD", "apppassword"),
        database=os.getenv("MYSQL_DATABASE", "appdb"),
    )
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id     INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(255) UNIQUE NOT NULL,
            password VARCHAR(64)  NOT NULL,
            token    VARCHAR(255) UNIQUE
        )
    """)
    conn.commit()
    cursor.close()
    conn.close()


# ─── Models ────────────────────────────────────────────────────────────────────

class UserRegister(BaseModel):
    username: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str


# ─── Helpers ───────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    conn=Depends(get_rdb),
):
    token = credentials.credentials
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, username FROM users WHERE token = %s", (token,))
    user = cursor.fetchone()
    cursor.close()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user


# ─── Routes ────────────────────────────────────────────────────────────────────


@app.post("/register")
def register(user: UserRegister, conn=Depends(get_rdb)):
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
def login(user: UserLogin, conn=Depends(get_rdb)):
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



@app.get("/videos")
def get_videos(current_user: dict = Depends(get_current_user)):
    return {"archive_1": ["video_1", "video_2"], "archive_2": ["video_3"]}


@app.get("/", response_class=HTMLResponse)
def index():
    return RedirectResponse(
        url='/docs/', status_code=307
    )