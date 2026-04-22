"""
Юнит-тесты для api.py.
mysql.connector и init_db мокаются до любого импорта приложения,
поэтому тесты не требуют реальной БД.
"""
import sys
import pytest
from unittest.mock import MagicMock, patch

# ── 1. Подменяем mysql.connector в sys.modules ДО импорта апи ─────────────────
_mock_connector = MagicMock()
_mock_connector.IntegrityError = type("IntegrityError", (Exception,), {})

_mock_mysql = MagicMock()
_mock_mysql.connector = _mock_connector

sys.modules.setdefault("mysql", _mock_mysql)
sys.modules.setdefault("mysql.connector", _mock_connector)

# ── 2. Импортируем модуль апи и сразу глушим init_db ─────────────────────────
import lab5.api.api as api_module  # noqa: E402
api_module.init_db = lambda: None   # lifespan не будет коннектиться

from fastapi.testclient import TestClient  # noqa: E402
from lab5.api.api import app              # noqa: E402

# ── Клиент ────────────────────────────────────────────────────────────────────

class ClientWrapper:
    def __init__(self, client):
        self.client = client

    def get(self, *args, **kwargs):
        res = self.client.get(*args, **kwargs)
        print("\n", args[0], res.status_code)
        return res

    def post(self, *args, **kwargs):
        return self.client.post(*args, **kwargs)


client = ClientWrapper(TestClient(app))

# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_conn(fetchone=None):
    """Мок соединения с нужным fetchone-результатом."""
    cursor = MagicMock()
    cursor.fetchone.return_value = fetchone
    conn = MagicMock()
    conn.cursor.return_value = cursor
    return conn, cursor


def _db_gen(conn):
    """Генератор для подмены Depends(get_db)."""
    yield conn


# ══════════════════════════════════════════════════════════════════════════════
# /register
# ══════════════════════════════════════════════════════════════════════════════

def test_register_success():
    conn, _ = _make_conn()
    with patch("lab5.api.api.get_db", return_value=_db_gen(conn)):
        r = client.post("/register", json={"username": "u1", "password": "p1"})
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_register_duplicate_user():
    conn, cursor = _make_conn()
    cursor.execute.side_effect = _mock_connector.IntegrityError("dup")
    with patch("lab5.api.api.get_db", return_value=_db_gen(conn)):
        r = client.post("/register", json={"username": "u1", "password": "p1"})
    assert r.status_code == 400
    assert r.json()["detail"] == "User exists"


# ══════════════════════════════════════════════════════════════════════════════
# /login
# ══════════════════════════════════════════════════════════════════════════════

def test_login_success():
    conn, _ = _make_conn(fetchone={"id": 1})
    with patch("lab5.api.api.get_db", return_value=_db_gen(conn)):
        r = client.post("/login", json={"username": "u1", "password": "p1"})
    assert r.status_code == 200
    assert "token" in r.json()
    assert len(r.json()["token"]) > 0


def test_login_invalid_credentials():
    conn, _ = _make_conn(fetchone=None)
    with patch("lab5.api.api.get_db", return_value=_db_gen(conn)):
        r = client.post("/login", json={"username": "u1", "password": "wrong"})
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid credentials"


# ══════════════════════════════════════════════════════════════════════════════
# /user
# ══════════════════════════════════════════════════════════════════════════════

def test_get_user_success():
    conn, _ = _make_conn(fetchone={"id": 1, "username": "u1"})
    with patch("lab5.api.api.get_db", return_value=_db_gen(conn)):
        r = client.get("/user", headers={"Authorization": "Bearer goodtoken"})
    assert r.status_code == 200
    assert r.json()["username"] == "u1"
    assert "id" in r.json()


def test_get_user_invalid_token():
    conn, _ = _make_conn(fetchone=None)
    with patch("lab5.api.api.get_db", return_value=_db_gen(conn)):
        r = client.get("/user", headers={"Authorization": "Bearer badtoken"})
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid token"


# ══════════════════════════════════════════════════════════════════════════════
# /upload
# ══════════════════════════════════════════════════════════════════════════════

def test_upload_video_success():
    conn, _ = _make_conn(fetchone={"id": 1, "username": "u1"})
    fake_jpeg = b"\xff\xd8\xff\xe0" + b"\x00" * 20

    with patch("lab5.api.api.get_db", return_value=_db_gen(conn)), \
         patch("lab5.api.api.subprocess.run") as mock_run, \
         patch("builtins.open", side_effect=lambda p, m="r", **kw: (
             __import__("io").BytesIO(fake_jpeg) if ("last_frame.jpg" in str(p) and "rb" in m)
             else __import__("builtins").__dict__["open"](p, m, **kw)
         )):
        mock_run.return_value = MagicMock(returncode=0)
        r = client.post(
            "/upload",
            files={"file": ("v.av1", b"data", "video/mp4")},
            headers={"Authorization": "Bearer goodtoken"},
        )

    assert r.status_code == 200
    assert r.headers["content-type"] == "image/jpeg"


def test_upload_video_unauthorized():
    conn, _ = _make_conn(fetchone=None)
    with patch("lab5.api.api.get_db", return_value=_db_gen(conn)):
        r = client.post(
            "/upload",
            files={"file": ("v.av1", b"data", "video/mp4")},
            headers={"Authorization": "Bearer badtoken"},
        )
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid token"


# ══════════════════════════════════════════════════════════════════════════════
# /videos
# ══════════════════════════════════════════════════════════════════════════════

def test_get_videos_success():
    conn, _ = _make_conn(fetchone={"id": 1, "username": "u1"})
    with patch("lab5.api.api.get_db", return_value=_db_gen(conn)):
        r = client.get("/videos", headers={"Authorization": "Bearer goodtoken"})
    assert r.status_code == 200
    assert "archive_1" in r.json()
    assert "archive_2" in r.json()


def test_get_videos_unauthorized():
    conn, _ = _make_conn(fetchone=None)
    with patch("lab5.api.api.get_db", return_value=_db_gen(conn)):
        r = client.get("/videos", headers={"Authorization": "Bearer badtoken"})
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid token"


# ══════════════════════════════════════════════════════════════════════════════
# /
# ══════════════════════════════════════════════════════════════════════════════

def test_index_page_returns_html():
    r = client.get("/")
    assert r.status_code == 200
    assert "<html>" in r.text
    assert "<body>" in r.text


def test_index_page_content_type():
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]