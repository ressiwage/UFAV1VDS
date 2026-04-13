"""
Интеграционные тесты — запускаются против живого стека (API + MySQL).
Переменная окружения API_URL задаёт базовый URL (по умолчанию http://localhost:8000).
"""
import os
import requests
import pytest

BASE = os.getenv("API_URL", "http://localhost:8000")


def _register(username, password):
    return requests.post(f"{BASE}/register", json={"username": username, "password": password})


def _login(username, password):
    return requests.post(f"{BASE}/login", json={"username": username, "password": password})


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# ── /register ─────────────────────────────────────────────────────────────────

def test_integration_register_success():
    r = _register("integ_user1", "pass1")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_integration_register_duplicate():
    _register("integ_dup", "pass")
    r = _register("integ_dup", "pass2")
    assert r.status_code == 400
    assert r.json()["detail"] == "User exists"


# ── /login ────────────────────────────────────────────────────────────────────

def test_integration_login_success():
    _register("integ_login", "secret")
    r = _login("integ_login", "secret")
    assert r.status_code == 200
    assert "token" in r.json()
    assert len(r.json()["token"]) > 10


def test_integration_login_wrong_password():
    _register("integ_badpass", "correct")
    r = _login("integ_badpass", "wrong")
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid credentials"


# ── /user ─────────────────────────────────────────────────────────────────────

def test_integration_get_user():
    _register("integ_me", "pw")
    token = _login("integ_me", "pw").json()["token"]
    r = requests.get(f"{BASE}/user", headers=_auth(token))
    assert r.status_code == 200
    assert r.json()["username"] == "integ_me"
    assert "id" in r.json()


def test_integration_get_user_bad_token():
    r = requests.get(f"{BASE}/user", headers=_auth("totallyfake"))
    assert r.status_code == 401


# ── /videos ───────────────────────────────────────────────────────────────────

def test_integration_get_videos():
    _register("integ_vid", "pw")
    token = _login("integ_vid", "pw").json()["token"]
    r = requests.get(f"{BASE}/videos", headers=_auth(token))
    assert r.status_code == 200
    assert "archive_1" in r.json()


def test_integration_get_videos_unauthorized():
    r = requests.get(f"{BASE}/videos", headers=_auth("bad"))
    assert r.status_code == 401


# ── / ─────────────────────────────────────────────────────────────────────────

def test_integration_index():
    r = requests.get(f"{BASE}/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "<html>" in r.text


# ── /upload ───────────────────────────────────────────────────────────────────
# Загружаем настоящий минимальный AV1-файл (IVF-контейнер, 1 кадр 2x2).
# Генерируем его ffmpeg'ом прямо в тесте, если доступен,
# иначе пропускаем тест.

@pytest.fixture(scope="module")
def av1_file(tmp_path_factory):
    import subprocess, shutil
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg not available in test environment")

    tmp = tmp_path_factory.mktemp("av1")
    out = tmp / "sample.ivf"
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "color=black:size=2x2:rate=1",
        "-t", "0.1",
        "-c:v", "libaom-av1", "-cpu-used", "8", "-crf", "63",
        "-f", "ivf", str(out),
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        pytest.skip("Could not generate AV1 test file")
    return out


def test_integration_upload_returns_jpeg(av1_file):
    _register("integ_upload", "pw")
    token = _login("integ_upload", "pw").json()["token"]

    with open(av1_file, "rb") as f:
        r = requests.post(
            f"{BASE}/upload",
            headers=_auth(token),
            files={"file": ("sample.ivf", f, "video/mp4")},
        )

    assert r.status_code == 200
    assert r.headers["content-type"] == "image/jpeg"
    # JPEG magic bytes
    assert r.content[:2] == b"\xff\xd8"


def test_integration_upload_unauthorized():
    with open(__file__, "rb") as f:  # любой файл — до auth не дойдёт
        r = requests.post(
            f"{BASE}/upload",
            headers=_auth("badtoken"),
            files={"file": ("x.av1", f, "video/mp4")},
        )
    assert r.status_code == 401