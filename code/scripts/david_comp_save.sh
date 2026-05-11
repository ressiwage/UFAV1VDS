#!/usr/bin/env bash
# =============================================================================
# dav1d_compare.sh
# Декодирует OBU-файл через dav1d, склеивает 5-минутное видео и 
# КОДИРУЕТ сравнительное видео (оригинал | decoded | diff)
# =============================================================================
# set -euo pipefail

# ---------------------------------------------------------------------------
# Настройки — поправьте под свою среду
# ---------------------------------------------------------------------------
OBU_FILE=code/tvav2.1.obu   # эталонный OBU (можно передать аргументом)
DAV1D_BIN="code/decoder/build/tools/dav1d"               
ORIG_VIDEO="code/test/tvav_david_reference_30m.y4m"       
# ORIG_VIDEO=code/tvav2.1.obu
DECODED_RAW="code/test/decoded_dav1d.y4m"     
# DECODED_RAW=code/tvav2.1.obu
DECODED_CLIP="code/test/decoded_5min.mp4"     
ORIG_CLIP="code/test/clip.mp4"
CLIP_DURATION=30                        

OUTPUT_COMPARISON="code/test/comparison_5min${NUM_ITER}.mp4"   # ← Новый файл

# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------
info()  { echo -e "\033[1;36m[INFO]\033[0m  $*"; }
ok()    { echo -e "\033[1;32m[ OK ]\033[0m  $*"; }
err()   { echo -e "\033[1;31m[ERR ]\033[0m  $*" >&2; exit 1; }

check_deps() {
    info "Проверка зависимостей..."
    for cmd in ffmpeg; do
        command -v "$cmd" &>/dev/null || err "Не найден: $cmd"
    done
    [[ -x "$DAV1D_BIN" ]] || err "dav1d не найден или не исполняем: $DAV1D_BIN"
    [[ -f "$OBU_FILE"  ]] || err "OBU-файл не найден: $OBU_FILE"
    [[ -f "$ORIG_VIDEO" ]] || err "Оригинальное видео не найдено: $ORIG_VIDEO"
    ok "Все зависимости на месте"
}

# ---------------------------------------------------------------------------
# 1. Декодирование OBU через dav1d → y4m
# ---------------------------------------------------------------------------
decode_obu() {
    info "Декодирую $OBU_FILE через dav1d..."
    "$DAV1D_BIN" \
        --input  "$OBU_FILE" \
        --threads 6 \
        --output "$DECODED_RAW" 
    ok "Декодирование завершено → $DECODED_RAW"
}

# ---------------------------------------------------------------------------
# 2. Нарезка первых 5 минут
# ---------------------------------------------------------------------------
trim_clips() {
    info "Нарезаю первые ${CLIP_DURATION}с из оригинала..."
    ffmpeg -y -i "$ORIG_VIDEO" \
        -t "$CLIP_DURATION" \
        -vf "fps=25" \
        -c:v h264  \
        -an "$ORIG_CLIP" \
        -loglevel warning
    ok "Оригинальный клип → $ORIG_CLIP"

    info "Нарезаю первые ${CLIP_DURATION}с из декодированного y4m..."
    ffmpeg -y -i "$DECODED_RAW" \
        -t "$CLIP_DURATION" \
        -vf "fps=25" \
        -c:v h264 \
        -an "$DECODED_CLIP" \
        -loglevel warning
    ok "Декодированный клип → $DECODED_CLIP"
}

# ---------------------------------------------------------------------------
# 3. Кодирование сравнительного видео (3 экрана)
# ---------------------------------------------------------------------------
encode_comparison() {
    info "Кодирую сравнительное видео (оригинал | decoded | luma diff)..."
    info "Выход: $OUTPUT_COMPARISON"

    ffmpeg -y -hide_banner -loglevel warning \
        -i "$ORIG_CLIP" \
        -i "$DECODED_CLIP" \
        -filter_complex "
            [0:v]setpts=PTS-STARTPTS, fps=25[A];
            [1:v]setpts=PTS-STARTPTS, fps=25[B];

            [A]split=2[A1][A2];
            [B]split=2[B1][B2];

            [A1][B1]blend=all_mode=subtract,format=yuv420p,
                     lutyuv=y='val*25':u=128:v=128[luma_mask];

            [luma_mask]lutrgb=r=val:g=0:b=val[with_fuchsia];

            [A2][B2]hstack=inputs=2[top];
            [with_fuchsia]pad=iw*2:ih:(ow-iw)/2:0:black[bottom];

            [top][bottom]vstack=inputs=2[out]
        " \
        -map "[out]" \
        -c:v h264  \
        -pix_fmt yuv420p \
        "$OUTPUT_COMPARISON"

    ok "Сравнительное видео сохранено: $OUTPUT_COMPARISON"
}

# ---------------------------------------------------------------------------
# Точка входа
# ---------------------------------------------------------------------------
main() {
    check_deps
    decode_obu
    trim_clips
    encode_comparison
}

main "$@"