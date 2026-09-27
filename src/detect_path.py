#!/usr/bin/env python3
"""
detect_path.py

Finds the most prominent contour (outline/edge) in an image and exports an
ordered, smoothed, evenly-resampled path of points. This path is what the
3D snake will slither along in blender_scene.py.

Usage:
    python3 detect_path.py --image assets/input.jpg --out build/path.json
"""

import argparse
import json
import sys

import cv2
import numpy as np


def parse_args():
    p = argparse.ArgumentParser(description="Detect a contour path in an image for snake animation.")
    p.add_argument("--image", required=True, help="Path to the input image.")
    p.add_argument("--out", required=True, help="Path to write the output path JSON.")
    p.add_argument("--num-points", type=int, default=240, help="Number of resampled points along the path.")
    p.add_argument("--canny-low", type=int, default=50, help="Canny edge detector low threshold.")
    p.add_argument("--canny-high", type=int, default=150, help="Canny edge detector high threshold.")
    p.add_argument("--blur-ksize", type=int, default=5, help="Gaussian blur kernel size (odd number).")
    p.add_argument("--smooth-window", type=int, default=7, help="Moving-average smoothing window (odd number).")
    p.add_argument("--min-area", type=float, default=200.0, help="Minimum contour area to be considered.")
    return p.parse_args()


def find_largest_contour(image, canny_low, canny_high, blur_ksize, min_area):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    if blur_ksize % 2 == 0:
        blur_ksize += 1
    blurred = cv2.GaussianBlur(gray, (blur_ksize, blur_ksize), 0)
    edges = cv2.Canny(blurred, canny_low, canny_high)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)

    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    if not contours:
        raise RuntimeError("No contours found. Try lowering --canny-low / --canny-high.")

    candidates = [c for c in contours if cv2.contourArea(c) >= min_area]
    if not candidates:
        candidates = contours  # fall back rather than failing outright

    best = max(candidates, key=lambda c: cv2.arcLength(c, True))
    return best.reshape(-1, 2).astype(np.float64)


def resample_by_arclength(points, num_points):
    diffs = np.diff(points, axis=0)
    seg_lengths = np.hypot(diffs[:, 0], diffs[:, 1])
    cumulative = np.concatenate([[0.0], np.cumsum(seg_lengths)])
    total_length = cumulative[-1]
    if total_length == 0:
        raise RuntimeError("Detected contour has zero length.")

    targets = np.linspace(0, total_length, num_points)
    resampled = np.empty((num_points, 2))
    resampled[:, 0] = np.interp(targets, cumulative, points[:, 0])
    resampled[:, 1] = np.interp(targets, cumulative, points[:, 1])
    return resampled


def smooth_path(points, window):
    if window < 3:
        return points
    if window % 2 == 0:
        window += 1
    kernel = np.ones(window) / window
    pad = window // 2
    padded_x = np.pad(points[:, 0], (pad, pad), mode="wrap")
    padded_y = np.pad(points[:, 1], (pad, pad), mode="wrap")
    x = np.convolve(padded_x, kernel, mode="valid")
    y = np.convolve(padded_y, kernel, mode="valid")
    return np.stack([x, y], axis=1)


def main():
    args = parse_args()
    image = cv2.imread(args.image)
    if image is None:
        print(f"ERROR: could not read image at {args.image}", file=sys.stderr)
        sys.exit(1)

    h, w = image.shape[:2]
    contour = find_largest_contour(image, args.canny_low, args.canny_high, args.blur_ksize, args.min_area)
    path = resample_by_arclength(contour, args.num_points)
    path = smooth_path(path, args.smooth_window)

    data = {
        "image_width": w,
        "image_height": h,
        "num_points": len(path),
        "points": path.tolist(),
    }
    with open(args.out, "w") as f:
        json.dump(data, f)

    print(f"Wrote {len(path)} path points to {args.out} (source image {w}x{h}).")


if __name__ == "__main__":
    main()
