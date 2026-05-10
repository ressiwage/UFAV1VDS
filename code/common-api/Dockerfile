# ──────────────────────────────────────────────
# Stage 1: сборка ffmpeg с libaom-av1
# ──────────────────────────────────────────────
FROM debian:bookworm-slim AS ffmpeg-builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    nasm \
    yasm \
    git \
    meson \
    pkg-config \
    ca-certificates \
    ninja-build \
    curl \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*


# ──────────────────────────────────────────────
# Stage 2: финальный образ
# ──────────────────────────────────────────────
FROM python:3.12-slim

# Системные зависимости для mysql-connector и libaom runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-libmysqlclient-dev \
    libgomp1 \
    pkg-config \
    gcc \
    && rm -rf /var/lib/apt/lists/*



RUN ldconfig

WORKDIR /app

COPY common-api/requirements.txt .
RUN pip install -r requirements.txt

COPY _shared/ ./_shared/
COPY common-api/ .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]