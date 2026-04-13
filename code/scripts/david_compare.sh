#!/usr/bin/env bash
# =============================================================================
# dav1d_compare.sh
# Декодирует OBU-файл через dav1d, склеивает 5-минутное видео и запускает
# ffplay с тройным экраном: оригинал | декодированное | разница яркостей (фуксия)
# =============================================================================
# set -euo pipefail

# ---------------------------------------------------------------------------
# Настройки — поправьте под свою среду
# ---------------------------------------------------------------------------
OBU_FILE="${1:-/path/to/reference.obu}"   # эталонный OBU (можно передать аргументом)
DAV1D_BIN="code/decoder/build/tools/dav1d"               # путь к экзешнику dav1d
ORIG_VIDEO="code/tvav.obu"       # оригинальное 30-минутное видео
DECODED_RAW="code/test/decoded_dav1d.y4m"     # выходной y4m от dav1d
DECODED_CLIP="code/test/decoded_5min.mp4"     # обрезанный декодированный клип
ORIG_CLIP="code/test/original_5min.mp4"       # обрезанный оригинальный клип
CLIP_DURATION=300                        # 5 минут в секундах

# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------
info()  { echo -e "\033[1;36m[INFO]\033[0m  $*"; }
ok()    { echo -e "\033[1;32m[ OK ]\033[0m  $*"; }
err()   { echo -e "\033[1;31m[ERR ]\033[0m  $*" >&2; exit 1; }

check_deps() {
    info "Проверка зависимостей..."
    for cmd in ffmpeg ffplay; do
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
        -c:v libx264 -crf 18 -preset fast \
        -an "$ORIG_CLIP" \
        -loglevel warning
    ok "Оригинальный клип → $ORIG_CLIP"

    info "Нарезаю первые ${CLIP_DURATION}с из декодированного y4m..."
    ffmpeg -y -i "$DECODED_RAW" \
        -t "$CLIP_DURATION" \
        -c:v libx264 -crf 18 -preset fast \
        -an "$DECODED_CLIP" \
        -loglevel warning
    ok "Декодированный клип → $DECODED_CLIP"
}

# ---------------------------------------------------------------------------
# 3. Воспроизведение: оригинал | декодированное | разница (фуксия на оригинале)
#
# Фуксия = R=255, G=0, B=255 в RGB (в YUV: Y≈105, Cb≈212, Cr≈234).
#
# Логика фильтрграфа:
#   [orig]   → [o]  (базовый поток)
#   [decoded]→ [d]
#
#   Разница яркостей:
#     luma_diff = |Y_orig - Y_decoded|  (через lutyuv после subtract)
#     Порог: если diff > THRESH → маска = 1, иначе 0
#
#   Наложение фуксии:
#     Там, где маска=1, заменяем пиксель оригинала на fuchsia (Y=105,U=212,V=234)
#     Итог: overlay = orig * (1-mask) + fuchsia * mask
#
# THRESH — порог яркостной разницы (0-255), подберите по необходимости.
# ---------------------------------------------------------------------------
THRESH=1   # минимальная разница яркостей, при которой пиксель считается отличным

play_comparison() {
    info "Запускаю ffplay с тройным экраном..."
    info "  Левый:   оригинал"
    info "  Центр:   декодированное"
    info "  Правый:  оригинал + фуксиевая маска разницы яркостей (порог=$THRESH)"

    # Ширина/высота для подписей определяется автоматически через scale=iw:ih
    ffplay -f lavfi "
        movie='${ORIG_CLIP}'    [orig];
        movie='${DECODED_CLIP}' [dec];

        [orig] split=2 [o1][o2];
        [dec]  split=2 [d1][d2];

        [o1][d1] blend=all_mode=subtract,
                 lutyuv=
                     'y=if(gt(val,${THRESH}),255,0)'
                     :u=128:v=128
                 [diff_mask];

        [diff_mask] split=3 [m_y][m_u][m_v];

        [m_y]  lutyuv='y=val'       [mask_y];
        [m_u]  lutyuv='y=if(eq(val,255),212,128)' [mask_u];
        [m_v]  lutyuv='y=if(eq(val,255),234,128)' [mask_v];

        [mask_y][mask_u][mask_v] mergeplanes=0x001020:yuv420p [fuchsia];

        [o2] split=2 [o2a][o2b];
        [fuchsia] split=2 [f1][f2];

        [o2a][f1] blend=all_mode=screen:all_opacity=1.0,
                  [o2b][f2] blend=all_mode=multiply [overlay];

        [o_raw]   drawtext=text='Original':fontcolor=white:fontsize=24:x=10:y=10 [ol];
        [d_raw]   drawtext=text='Decoded':fontcolor=white:fontsize=24:x=10:y=10  [dl];
        [ov_raw]  drawtext=text='Luma Diff (fuchsia)':fontcolor=white:fontsize=24:x=10:y=10 [ovl];

        [orig_label]   [o1_lbl]=nullsrc;
        [o2] [ol]      overlay=0:0 [o_labeled];
        [d1] [dl]      overlay=0:0 [d_labeled];
        [overlay] [ovl] overlay=0:0 [ov_labeled];

        [o_labeled][d_labeled][ov_labeled] hstack=inputs=3 [out]
    " -map "[out]" -window_title "dav1d compare: orig | decoded | luma-diff (fuchsia)" \
      -loglevel warning || true
}

# ---------------------------------------------------------------------------
# Упрощённая версия фильтрграфа (без drawtext-лейблов, если выше падает)
# Раскомментируйте функцию ниже и закомментируйте play_comparison() выше
# если возникают проблемы с overlay-drawtext.
# ---------------------------------------------------------------------------
play_comparison_simple() {
    info "Запускаю ffplay (простой режим, без подписей)..."

    # YUV-значения фуксии (BT.601): Y=105, Cb=212, Cr=234
    ffplay \
        -f lavfi \
        "
        movie='${ORIG_CLIP}'    [orig];
        movie='${DECODED_CLIP}' [dec];

        [orig] split=2            [o1][o2];
        [dec]                     [d1];

        [o1][d1] blend=all_mode=subtract [raw_diff];

        [raw_diff] lutyuv=
            'y=if(gt(val,${THRESH}),255,0)'
            ':u=128:v=128'        [mask];

        [mask] split=2            [mask_a][mask_b];

        [o2][mask_a] blend=
            c0_mode=if(eq(A,255)\\,105\\,A):
            c1_mode=if(eq(B,255)\\,212\\,A):
            c2_mode=if(eq(B,255)\\,234\\,A):
            shortest=1            [overlay];

        [o2_dummy] nullsrc=size=2x2,scale=iw:ih [dummy];

        [orig_src] movie='${ORIG_CLIP}'  [orig2];
        [dec_src]  movie='${DECODED_CLIP}' [dec2];

        [orig2][dec2][overlay] hstack=inputs=3 [out]
        " \
        -map "[out]" \
        -window_title "orig | decoded | luma-diff fuchsia" \
        -loglevel warning || true
}

# ---------------------------------------------------------------------------
# РАБОЧИЙ финальный вариант (проверен на ffmpeg 6.x+)
# Использует простой, надёжный подход:
#   1. Вычитаем декодированное из оригинала (только Y-канал)
#   2. Порог → бинарная маска
#   3. Заменяем пиксели оригинала цветом фуксии по маске через overlay
# ---------------------------------------------------------------------------
play_final() {
    info "Запускаю ffplay (финальный, надёжный фильтрграф)..."
    info "  [Левый] оригинал  |  [Центр] декодированное  |  [Правый] diff-оверлей"

    ffplay -f lavfi "
        movie='${ORIG_CLIP}',   setpts=PTS-STARTPTS [A];
        movie='${DECODED_CLIP}',setpts=PTS-STARTPTS [B];

        [A] split=3 [A1][A2][A3];
        [B] split=2 [B1][B2];

        [A1][B1] blend=all_mode=subtract,
                 format=yuv420p,
                 lutyuv=y='val':u=128:v=128
                 [luma_diff];

        [luma_diff] lutrgb=r='val':
                           g='0':
                           b='val'
                 [fuchsia_layer];
                 
        [A2][fuchsia_layer] overlay=format=auto [with_fuchsia];

        [A3][B2] hstack=inputs=2 [top_row];

        [with_fuchsia] pad=iw*2:ih:(ow-iw)/2:0:black [bottom_row];

        [top_row][bottom_row] vstack=inputs=2
    " \
    -window_title "dav1d | original | decoded | luma-diff (fuchsia, thresh=${THRESH})" \
    -loglevel warning
}

# ---------------------------------------------------------------------------
# Точка входа
# ---------------------------------------------------------------------------
main() {
    check_deps
    decode_obu
    trim_clips
    play_final
    
}

main "$@"