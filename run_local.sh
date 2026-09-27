#!/usr/bin/env bash
# Run the full pipeline locally: detect the contour path, then render the
# 3D cinematic snake video with Blender.
#
# Requirements: Python 3 with the packages in requirements.txt, and Blender
# installed (either on your PATH as `blender`, or point BLENDER_BIN at the
# executable).
#
# Usage:
#   ./run_local.sh
#   IMAGE=my_photo.jpg DURATION=15 ./run_local.sh

set -euo pipefail

IMAGE="${IMAGE:-assets/input.jpg}"
PATH_JSON="${PATH_JSON:-build/path.json}"
OUTPUT="${OUTPUT:-output/snake_cinematic.mp4}"
DURATION="${DURATION:-12}"
FPS="${FPS:-24}"
RES_X="${RES_X:-1920}"
RES_Y="${RES_Y:-1080}"
SAMPLES="${SAMPLES:-64}"
BLENDER_BIN="${BLENDER_BIN:-blender}"

if [ ! -f "$IMAGE" ]; then
    echo "ERROR: input image not found at $IMAGE" >&2
    echo "Place your image there, or set IMAGE=path/to/your.jpg" >&2
    exit 1
fi

if ! command -v "$BLENDER_BIN" >/dev/null 2>&1; then
    echo "ERROR: Blender executable '$BLENDER_BIN' not found on PATH." >&2
    echo "Install Blender (https://www.blender.org/download/) or set BLENDER_BIN=/path/to/blender" >&2
    exit 1
fi

mkdir -p build output

echo "==> Step 1/2: detecting contour path in $IMAGE"
python3 src/detect_path.py --image "$IMAGE" --out "$PATH_JSON"

echo "==> Step 2/2: rendering 3D cinematic snake video with Blender (this can take a while)"
"$BLENDER_BIN" -b -P src/blender_scene.py -- \
    --image "$IMAGE" \
    --path "$PATH_JSON" \
    --out "$OUTPUT" \
    --duration "$DURATION" \
    --fps "$FPS" \
    --resolution-x "$RES_X" \
    --resolution-y "$RES_Y" \
    --samples "$SAMPLES"

echo "==> Done. Video written to $OUTPUT"
