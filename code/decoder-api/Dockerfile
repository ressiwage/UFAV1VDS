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
    pkg-config \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# libaom (AV1 codec)
RUN git clone --depth 1 https://aomedia.googlesource.com/aom /src/aom && \
    cmake -S /src/aom -B /src/aom/build \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX=/usr/local \
        -DENABLE_TESTS=OFF \
        -DENABLE_DOCS=OFF && \
    cmake --build /src/aom/build -j$(nproc) && \
    cmake --install /src/aom/build

# ffmpeg с поддержкой libaom
RUN curl -fsSL https://ffmpeg.org/releases/ffmpeg-7.1.tar.bz2 | tar -xj -C /src && \
    cd /src/ffmpeg-7.1 && \
    ./configure \
        --prefix=/usr/local \
        --disable-everything \
        --disable-doc \
        --disable-htmlpages \
        --disable-manpages \
        --disable-podpages \
        --disable-txtpages \
        --disable-network \
        --disable-autodetect \
        --disable-ffplay \
        --disable-ffprobe \
        --enable-demuxer=ivf \
        --enable-demuxer=mov \
        --enable-demuxer=matroska \
        --enable-libaom \
        --enable-decoder=libaom_av1 \
        --enable-muxer=image2 \
        --enable-encoder=mjpeg \
        --enable-filter=thumbnail \
        --enable-filter=scale \
        --enable-protocol=file \
        --extra-cflags="-I/usr/local/include" \
        --extra-ldflags="-L/usr/local/lib" && \
    make -j$(nproc) && \
    make install

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

# Копируем собранный ffmpeg + libaom из stage 1
COPY --from=ffmpeg-builder /usr/local/bin/ffmpeg   /usr/local/bin/ffmpeg
COPY --from=ffmpeg-builder /usr/local/lib           /usr/local/lib
COPY --from=ffmpeg-builder /usr/local/include       /usr/local/include

RUN ldconfig

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 7948

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7948"]