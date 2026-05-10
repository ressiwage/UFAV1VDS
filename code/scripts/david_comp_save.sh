#!/usr/bin/env bash
# =============================================================================
# dav1d_encode.sh
# Декодирует OBU-файл через dav1d, обрезает 5-минутные клипы и сохраняет
# сравнение (оригинал | декодированное | разница яркостей) как H.264 видео.
# =============================================================================
set -euo pipefail

# ---------------------------------------------------------------------------
# Настройки — при необходимости измените под свою среду
# ---------------------------------------------------------------------------
OBU_FILE="${1:-/path/to/reference.obu}"   # эталонный OBU (можно передать аргументом)
OUTPUT_VIDEO="comparison_$(date +%Y%m%d_%H%M%S).mp4"  # имя выходного файла
DAV1D_BIN="code/decoder/build/tools/dav1d"               # путь к dav1d
ORIG_VIDEO="code/tvav.obu"                               # оригинальное 30-минутное видео
DECODED_RAW="code/test/decoded_dav1d.y4m"                # промежуточный y4m от dav1d
DECODED_CLIP="code/test/decoded_5min.mp4"                # обрезанный декодированный клип
ORIG_CLIP="code/test/original_5min.mp4"                  # обрезанный оригинальный клип
CLIP_DURATION=60                                        # 5 минут в секундах

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
    info "Декодирую $OBU_FILE через dav1d (y4m)..."
    "$DAV1D_BIN" \
        --input  "$OBU_FILE" \
        --threads 6 \
        --output "$DECODED_RAW" 
    ok "Декодирование завершено → $DECODED_RAW"
}

# ---------------------------------------------------------------------------
# 2. Нарезка первых CLIP_DURATION секунд (уже в H.264)
# ---------------------------------------------------------------------------
trim_clips() {
    info "Нарезаю первые ${CLIP_DURATION}с из оригинала (H.264)..."
    ffmpeg -y -i "$ORIG_VIDEO" \
        -t "$CLIP_DURATION" \
        -c:v libx264 -crf 18 -preset fast \
        -an "$ORIG_CLIP" \
        -loglevel warning
    ok "Оригинальный клип → $ORIG_CLIP"

    info "Нарезаю первые ${CLIP_DURATION}с из декодированного y4m (H.264)..."
    ffmpeg -y -i "$DECODED_RAW" \
        -t "$CLIP_DURATION" \
        -c:v libx264 -crf 18 -preset fast \
        -an "$DECODED_CLIP" \
        -loglevel warning
    ok "Декодированный клип → $DECODED_CLIP"
}

# ---------------------------------------------------------------------------
# 3. Кодирование сравнения (оригинал | декодированное | разница) в H.264
# ---------------------------------------------------------------------------
encode_comparison() {
    info "Создаю видео сравнения и кодирую его в H.264..."
    info "  Левый:  оригинал"
    info "  Центр:  декодированное"
    info "  Правый: разница яркостей (усиленная, фуксия)"
    info "Выходной файл: $OUTPUT_VIDEO"

    # Порог яркостной разницы (оставлено из оригинального скрипта)
    local THRESH=1

    ffmpeg -hide_banner -loglevel warning \
        -i "$ORIG_CLIP" \
        -i "$DECODED_CLIP" \
        -filter_complex "
            movie='${ORIG_CLIP}',   setpts=PTS-STARTPTS [A];
        movie='${DECODED_CLIP}',setpts=PTS-STARTPTS [B];

        [A] split=2 [A1][A2];
        [B] split=2 [B1][B2];

        [A1][B1] blend=all_mode=subtract,
                 format=yuv420p,
                 lutyuv=y='val*25':u=128:v=128
                 [luma_mask];

[luma_mask] lutrgb=
    r='val':
    g='0':
    b='val'
    [with_fuchsia];


        [A2][B2] hstack=inputs=2 [top_row];

        [with_fuchsia] pad=iw*2:ih:(ow-iw)/2:0:black [bottom_row];

        [top_row][bottom_row] vstack=inputs=2
        " \
        -map "[out]" \
        -c:v libx264 -crf 18 -preset fast \
        "$OUTPUT_VIDEO"

    ok "Сравнение сохранено как $OUTPUT_VIDEO"
}

# ---------------------------------------------------------------------------
# Точка входа
# ---------------------------------------------------------------------------
main() {
    check_deps
    decode_obu
    trim_clips
    encode_comparison

    info "Готово. Выходной файл: $OUTPUT_VIDEO"
}

main "$@"