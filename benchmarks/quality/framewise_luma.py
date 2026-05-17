#!/usr/bin/env python3
"""
Per-frame Luma Difference calculator for two videos.

For each frame:
  luma_diff[i] = mean(|Y1[pixel] - Y2[pixel]|)  over all pixels

Then computes the cumulative mean and plots both curves.

Usage:
  python luma_diff.py video1.mp4 video2.mp4 [--output chart.png]
"""

import argparse
import sys
import numpy as np
import cv2
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from pathlib import Path



def bgr_to_luma(frame_bgr: np.ndarray) -> np.ndarray:
    """Convert a BGR uint8 frame to float32 luma (Y) using BT.601 coefficients."""
    b = frame_bgr[:, :, 0].astype(np.float32)
    g = frame_bgr[:, :, 1].astype(np.float32)
    r = frame_bgr[:, :, 2].astype(np.float32)
    return 0.299 * r + 0.587 * g + 0.114 * b   # range [0, 255]


def open_capture(path: str) -> cv2.VideoCapture:
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        sys.exit(f"[ERROR] Cannot open video: {path}")
    return cap


def video_info(cap: cv2.VideoCapture) -> dict:
    return {
        "frames": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
        "fps":    cap.get(cv2.CAP_PROP_FPS),
        "width":  int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
    }



def compute_luma_diffs(cap1: cv2.VideoCapture,
                       cap2: cv2.VideoCapture,
                       resize_to: tuple | None = None) -> np.ndarray:
    """
    Iterate both videos frame-by-frame, compute mean absolute luma difference
    per frame, and return a 1-D array of shape (N_frames,).
    """
    diffs = []
    frame_idx = 0

    while True:
        ok1, f1 = cap1.read()
        ok2, f2 = cap2.read()

        if not ok1 or not ok2:
            break  # stop when either video ends

        if resize_to is not None:
            f1 = cv2.resize(f1, resize_to, interpolation=cv2.INTER_AREA)
            f2 = cv2.resize(f2, resize_to, interpolation=cv2.INTER_AREA)
        elif f1.shape != f2.shape:
            # Resize video2 to match video1 if sizes differ
            f2 = cv2.resize(f2, (f1.shape[1], f1.shape[0]),
                            interpolation=cv2.INTER_AREA)

        y1 = bgr_to_luma(f1)
        y2 = bgr_to_luma(f2)

        mean_diff = np.mean(np.abs(y1 - y2))
        diffs.append(mean_diff)

        frame_idx += 1
        if frame_idx % 100 == 0:
            print(f"  Processed {frame_idx} frames …", flush=True)

    return np.array(diffs, dtype=np.float32)



def plot_results(diffs: np.ndarray,
                 fps: float,
                 video1_name: str,
                 video2_name: str,
                 output_path: str) -> None:
    n = len(diffs)
    frames = np.arange(1, n + 1)
    cumulative_mean = np.cumsum(diffs) / frames   # running mean
    overall_mean = float(np.mean(diffs))

    # Time axis (seconds)
    times = frames / fps if fps > 0 else frames

    fig, axes = plt.subplots(2, 1, figsize=(14, 9), facecolor="#0f0f13")
    fig.suptitle(
        f"Per-Frame Luma Difference\n"
        f"{Path(video1_name).name}  vs  {Path(video2_name).name}",
        color="#e8e8f0", fontsize=13, fontweight="bold", y=0.98
    )

    ax_color   = "#0f0f13"
    grid_color = "#2a2a3a"
    text_color = "#c0c0d0"
    accent1    = "#00d4ff"   # per-frame curve
    accent2    = "#ff6b6b"   # cumulative mean curve
    mean_color = "#f0c040"   # overall mean line

    # ── Top panel: per-frame luma diff ──────────────────────────────────────
    ax1 = axes[0]
    ax1.set_facecolor(ax_color)
    ax1.plot(times, diffs, color=accent1, linewidth=0.8,
             alpha=0.85, label="Per-frame luma diff")
    ax1.axhline(overall_mean, color=mean_color, linewidth=1.4,
                linestyle="--", label=f"Overall mean = {overall_mean:.3f}")
    ax1.fill_between(times, diffs, alpha=0.15, color=accent1)

    ax1.set_ylabel("Mean |ΔY| per frame  [0–255]", color=text_color, fontsize=10)
    ax1.set_xlim(times[0], times[-1])
    ax1.set_ylim(bottom=0)
    ax1.tick_params(colors=text_color, labelsize=8)
    ax1.xaxis.label.set_color(text_color)
    for spine in ax1.spines.values():
        spine.set_edgecolor(grid_color)
    ax1.grid(True, color=grid_color, linewidth=0.5)
    ax1.legend(fontsize=9, facecolor="#1c1c28", edgecolor=grid_color,
               labelcolor=text_color)

    # Annotate max
    max_idx = int(np.argmax(diffs))
    ax1.annotate(
        f"max {diffs[max_idx]:.2f} @ frame {max_idx + 1}",
        xy=(times[max_idx], diffs[max_idx]),
        xytext=(times[max_idx], diffs[max_idx] * 1.08),
        color=accent1, fontsize=8,
        arrowprops=dict(arrowstyle="->", color=accent1, lw=0.8),
    )

    # ── Bottom panel: cumulative (running) mean ──────────────────────────────
    ax2 = axes[1]
    ax2.set_facecolor(ax_color)
    ax2.plot(times, cumulative_mean, color=accent2, linewidth=1.2,
             label="Cumulative mean luma diff")
    ax2.fill_between(times, cumulative_mean, alpha=0.15, color=accent2)
    ax2.axhline(overall_mean, color=mean_color, linewidth=1.4,
                linestyle="--", label=f"Final mean = {overall_mean:.3f}")

    ax2.set_xlabel(
        "Time (s)" if fps > 0 else "Frame index",
        color=text_color, fontsize=10
    )
    ax2.set_ylabel("Cumulative mean |ΔY|  [0–255]", color=text_color, fontsize=10)
    ax2.set_xlim(times[0], times[-1])
    ax2.tick_params(colors=text_color, labelsize=8)
    for spine in ax2.spines.values():
        spine.set_edgecolor(grid_color)
    ax2.grid(True, color=grid_color, linewidth=0.5)
    ax2.legend(fontsize=9, facecolor="#1c1c28", edgecolor=grid_color,
               labelcolor=text_color)

    # Secondary x-axis showing frame numbers
    def time_to_frame(x):
        return x * fps if fps > 0 else x

    def frame_to_time(x):
        return x / fps if fps > 0 else x

    for ax in axes:
        ax2x = ax.secondary_xaxis("top", functions=(time_to_frame, frame_to_time))
        ax2x.set_xlabel("Frame", color=text_color, fontsize=8, labelpad=4)
        ax2x.tick_params(colors=text_color, labelsize=7)

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    plt.savefig(output_path, dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"\n[OK] Chart saved → {output_path}")




def print_stats(diffs: np.ndarray, fps: float) -> None:
    n = len(diffs)
    print("\n" + "─" * 50)
    print(f"  Total frames processed : {n}")
    print(f"  Duration               : {n / fps:.2f} s  ({fps:.3f} fps)")
    print(f"  Mean luma diff         : {np.mean(diffs):.4f}")
    print(f"  Median luma diff       : {np.median(diffs):.4f}")
    print(f"  Std dev                : {np.std(diffs):.4f}")
    print(f"  Min  (frame {np.argmin(diffs)+1:>6d})  : {np.min(diffs):.4f}")
    print(f"  Max  (frame {np.argmax(diffs)+1:>6d})  : {np.max(diffs):.4f}")
    print("─" * 50 + "\n")


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Compute per-frame luma difference between two videos and plot results."
    )
    parser.add_argument("video1", help="Path to the first video")
    parser.add_argument("video2", help="Path to the second video")
    parser.add_argument(
        "--output", "-o",
        default="luma_diff_chart.png",
        help="Output chart filename (default: luma_diff_chart.png)"
    )
    parser.add_argument(
        "--resize", "-r",
        nargs=2, type=int, metavar=("W", "H"),
        default=None,
        help="Resize both videos to WxH before comparison (e.g. --resize 1280 720)"
    )
    parser.add_argument(
        "--csv",
        default=None,
        help="Optional path to save per-frame diffs as a CSV file"
    )
    args = parser.parse_args()

    cap1 = open_capture(args.video1)
    cap2 = open_capture(args.video2)

    info1 = video_info(cap1)
    info2 = video_info(cap2)

    print(f"\nVideo 1: {args.video1}")
    print(f"  {info1['width']}×{info1['height']}, {info1['fps']:.3f} fps, "
          f"~{info1['frames']} frames")
    print(f"\nVideo 2: {args.video2}")
    print(f"  {info2['width']}×{info2['height']}, {info2['fps']:.3f} fps, "
          f"~{info2['frames']} frames")

    resize_to = tuple(args.resize) if args.resize else None
    if resize_to:
        print(f"\nResizing both to {resize_to[0]}×{resize_to[1]} for comparison.")

    print("\nComputing luma differences …")
    diffs = compute_luma_diffs(cap1, cap2, resize_to=resize_to)

    cap1.release()
    cap2.release()

    fps = info1["fps"] if info1["fps"] > 0 else 25.0
    print_stats(diffs, fps)

    if args.csv:
        import csv
        with open(args.csv, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["frame", "time_s", "luma_diff", "cumulative_mean"])
            cumulative = np.cumsum(diffs) / np.arange(1, len(diffs) + 1)
            for i, (d, c) in enumerate(zip(diffs, cumulative)):
                writer.writerow([i + 1, round((i + 1) / fps, 6),
                                 round(float(d), 6), round(float(c), 6)])
        print(f"[OK] CSV saved → {args.csv}")

    plot_results(diffs, fps, args.video1, args.video2, args.output)


if __name__ == "__main__":
    main()