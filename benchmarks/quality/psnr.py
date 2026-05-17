"""
PSNR (Peak Signal-to-Noise Ratio) Calculator
=============================================
Поддерживает: изображения (PNG, JPEG, BMP, TIFF) и видео (через покадровое сравнение).
"""

import numpy as np
import sys
import os
from pathlib import Path


def compute_mse(img1: np.ndarray, img2: np.ndarray) -> float:
    """Среднеквадратичная ошибка между двумя массивами."""
    if img1.shape != img2.shape:
        raise ValueError(
            f"Размеры изображений не совпадают: {img1.shape} vs {img2.shape}"
        )
    return float(np.mean((img1.astype(np.float64) - img2.astype(np.float64)) ** 2))


def compute_psnr(img1: np.ndarray, img2: np.ndarray, max_val: float = 255.0) -> float:
    """
    Вычисляет PSNR в дБ.

    Args:
        img1:    оригинальное изображение (numpy array)
        img2:    искажённое/сжатое изображение (numpy array)
        max_val: максимально возможное значение пикселя (255 для uint8)

    Returns:
        PSNR в дБ (float('inf') если изображения идентичны)
    """
    mse = compute_mse(img1, img2)
    if mse == 0:
        return float("inf")
    return 10.0 * np.log10((max_val**2) / mse)


def psnr_from_files(path1: str, path2: str) -> dict:
    """
    Загружает два изображения с диска и считает PSNR.

    Returns:
        dict с полями: psnr, mse, shape, channels
    """
    try:
        from PIL import Image
    except ImportError:
        raise ImportError("Установите Pillow: pip install Pillow")

    img1 = np.array(Image.open(path1).convert("RGB"))
    img2 = np.array(Image.open(path2).convert("RGB"))

    psnr_total = compute_psnr(img1, img2)

    # Покальный PSNR по каналам (R, G, B)
    channel_names = ["R", "G", "B"]
    channel_psnr = {
        ch: compute_psnr(img1[:, :, i], img2[:, :, i])
        for i, ch in enumerate(channel_names)
    }

    return {
        "psnr_db": psnr_total,
        "mse": compute_mse(img1, img2),
        "shape": img1.shape,
        "channels": channel_psnr,
    }


def psnr_video(path1: str, path2: str, max_frames: int = None) -> dict:
    """
    Покадровый PSNR для двух видеофайлов.

    Args:
        path1:      путь к оригинальному видео
        path2:      путь к искажённому видео
        max_frames: ограничить количество анализируемых кадров (None = все)

    Returns:
        dict с per-frame PSNR и средним значением
    """
    try:
        import cv2
    except ImportError:
        raise ImportError("Установите OpenCV: pip install opencv-python")

    cap1 = cv2.VideoCapture(path1)
    cap2 = cv2.VideoCapture(path2)

    frame_psnr = []
    frame_idx = 0

    while True:
        ret1, frame1 = cap1.read()
        ret2, frame2 = cap2.read()

        if not ret1 or not ret2:
            break
        if max_frames and frame_idx >= max_frames:
            break

        p = compute_psnr(frame1, frame2)
        frame_psnr.append(p)
        frame_idx += 1

    cap1.release()
    cap2.release()

    finite_vals = [v for v in frame_psnr if v != float("inf")]
    return {
        "frame_psnr": frame_psnr,
        "mean_psnr": float(np.mean(finite_vals)) if finite_vals else float("inf"),
        "min_psnr": float(np.min(finite_vals)) if finite_vals else float("inf"),
        "max_psnr": float(np.max(finite_vals)) if finite_vals else float("inf"),
        "total_frames": len(frame_psnr),
    }


def psnr_from_arrays(original: np.ndarray, compressed: np.ndarray,
                     max_val: float = 255.0) -> float:
    """Удобная обёртка для работы напрямую с numpy-массивами."""
    return compute_psnr(original, compressed, max_val)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print_result(result: dict, file1: str, file2: str):
    print(f"\n{'='*50}")
    print(f"  Файл 1 : {file1}")
    print(f"  Файл 2 : {file2}")
    print(f"{'='*50}")
    if "frame_psnr" in result:
        print(f"  Кадров      : {result['total_frames']}")
        print(f"  Средний PSNR: {result['mean_psnr']:.4f} дБ")
        print(f"  Мин. PSNR   : {result['min_psnr']:.4f} дБ")
        print(f"  Макс. PSNR  : {result['max_psnr']:.4f} дБ")
    else:
        psnr = result["psnr_db"]
        psnr_str = f"{psnr:.4f} дБ" if psnr != float("inf") else "∞ (идентичны)"
        print(f"  Размер      : {result['shape']}")
        print(f"  MSE         : {result['mse']:.4f}")
        print(f"  PSNR        : {psnr_str}")
        print(f"  Каналы:")
        for ch, val in result["channels"].items():
            v_str = f"{val:.4f} дБ" if val != float("inf") else "∞"
            print(f"    {ch}: {v_str}")
    print(f"{'='*50}\n")


def main():
    if len(sys.argv) < 3:
        print("Использование:")
        print("  python psnr.py <файл1> <файл2> [--video] [--frames N]")
        print("\nПримеры:")
        print("  python psnr.py original.png compressed.png")
        print("  python psnr.py original.mp4 compressed.mp4 --video")
        print("  python psnr.py original.mp4 compressed.mp4 --video --frames 100")
        sys.exit(1)

    file1, file2 = sys.argv[1], sys.argv[2]
    is_video = "--video" in sys.argv
    max_frames = None
    if "--frames" in sys.argv:
        idx = sys.argv.index("--frames")
        max_frames = int(sys.argv[idx + 1])

    for f in (file1, file2):
        if not os.path.exists(f):
            print(f"Ошибка: файл не найден — {f}")
            sys.exit(1)

    if is_video:
        result = psnr_video(file1, file2, max_frames=max_frames)
    else:
        result = psnr_from_files(file1, file2)

    _print_result(result, file1, file2)


# ---------------------------------------------------------------------------
# Демо (запуск без аргументов — создаёт тестовые данные)
# ---------------------------------------------------------------------------

def _demo():
    print("=== Демо-режим: генерация тестовых изображений ===\n")

    rng = np.random.default_rng(42)
    original = rng.integers(0, 256, size=(256, 256, 3), dtype=np.uint8)

    test_cases = [
        ("Без шума (идентичные)",  original.copy(),                       None),
        ("Слабый шум (σ=5)",       np.clip(original.astype(int) + rng.integers(-5,  6, original.shape), 0, 255).astype(np.uint8), None),
        ("Средний шум (σ=15)",     np.clip(original.astype(int) + rng.integers(-15, 16, original.shape), 0, 255).astype(np.uint8), None),
        ("Сильный шум (σ=40)",     np.clip(original.astype(int) + rng.integers(-40, 41, original.shape), 0, 255).astype(np.uint8), None),
        ("Случайное изображение",  rng.integers(0, 256, size=original.shape, dtype=np.uint8), None),
    ]

    print(f"{'Случай':<30} {'MSE':>10} {'PSNR (дБ)':>12}")
    print("-" * 55)

    for name, distorted, _ in test_cases:
        mse  = compute_mse(original, distorted)
        psnr = compute_psnr(original, distorted)
        psnr_str = f"{psnr:>12.4f}" if psnr != float("inf") else f"{'∞ (идент.)':>12}"
        print(f"{name:<30} {mse:>10.2f} {psnr_str}")

    print("\nТипичные значения PSNR:")
    print("  > 40 дБ  — отличное качество (почти неразличимо)")
    print("  30–40 дБ — хорошее качество")
    print("  20–30 дБ — приемлемое качество")
    print("  < 20 дБ  — низкое качество, шум хорошо заметен")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        _demo()
    else:
        main()