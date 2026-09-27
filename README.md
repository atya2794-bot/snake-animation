# Snake Cinematic

Detects the strongest contour (outline) in an image, then renders a 3D
cinematic video of a snake slithering along that contour — drawing itself
onto the image — before the camera pushes in for a finishing shot.

Pipeline:

1. **`src/detect_path.py`** (plain Python + OpenCV) — finds the largest
   edge/contour in your image and exports it as a smoothed, evenly-spaced
   list of points (`build/path.json`).
2. **`src/blender_scene.py`** (runs inside Blender) — builds a 3D scene:
   your image on a backdrop plane, a beveled curve ("the snake") that
   reveals itself along the detected path with a snake-skin shader,
   three-point cinematic lighting, and an animated camera move. Renders
   straight to an `.mp4`.

## Option A — Run it locally

Requirements: Python 3.9+, and [Blender](https://www.blender.org/download/)
(4.x) installed.

```bash
pip install -r requirements.txt

# put your image at assets/input.jpg, then:
./run_local.sh
```

The finished video lands at `output/snake_cinematic.mp4`.

Useful overrides (environment variables):

```bash
IMAGE=my_photo.jpg DURATION=15 RES_X=2560 RES_Y=1440 SAMPLES=96 ./run_local.sh
```

If `blender` isn't on your `PATH`:

```bash
BLENDER_BIN=/Applications/Blender.app/Contents/MacOS/Blender ./run_local.sh
```

Rendering is CPU-bound and can take anywhere from a few minutes to well
over an hour depending on resolution, sample count, and your machine —
`SAMPLES` and `RES_X`/`RES_Y` are the main knobs to trade quality for speed.

## Option B — Build and render on GitHub Actions (no local Blender needed)

This repo includes `.github/workflows/render.yml`, which installs Blender
on a GitHub-hosted runner, runs the same pipeline, and uploads the finished
video as a downloadable build artifact. I can't push to GitHub myself from
here, so:

1. Create a new (or use an existing) GitHub repository.
2. Push this project to it:
   ```bash
   git init
   git add .
   git commit -m "Snake cinematic video pipeline"
   git branch -M main
   git remote add origin https://github.com/<you>/<your-repo>.git
   git push -u origin main
   ```
3. Add your source image to the repo at `assets/input.jpg` (replace the
   placeholder file in `assets/`), commit, and push.
4. In the repo on GitHub: **Actions** tab → **Render Snake Cinematic Video**
   → **Run workflow**. You can optionally override the image path,
   duration, resolution, and sample count in the dialog.
5. When the run finishes (Cycles CPU rendering at 1080p for ~12s of video
   can take roughly 1–3 hours on GitHub's free runners — the workflow's
   timeout is set to 3 hours), open the run's summary page and download the
   **snake-cinematic-video** artifact (a zip containing the `.mp4`).

The workflow also re-runs automatically on any push that touches
`assets/**`, so swapping in a new image and pushing is enough to kick off a
new render.

## Tuning the detected path

If the snake traces the wrong thing (background clutter, noise, or too
short/faint an edge), adjust `detect_path.py`'s thresholds:

```bash
python3 src/detect_path.py --image assets/input.jpg --out build/path.json \
    --canny-low 30 --canny-high 100 --min-area 500 --num-points 300
```

- Lower `--canny-low`/`--canny-high` → picks up fainter edges (but more noise).
- Raise `--min-area` → ignores small stray contours.
- `--num-points` → more points = smoother, longer snake path.

## Tuning the render

In `blender_scene.py` / the workflow inputs:

- `--duration` / `--fps` → total video length.
- `--draw-fraction` (script default 0.7) → what fraction of the video is
  spent on the snake drawing itself before the camera's finishing push-in.
- `--samples` → Cycles render samples; lower is faster/noisier, higher is
  slower/cleaner.
- `--resolution-x` / `--resolution-y` → output resolution.

## Project layout

```
snake-cinematic/
├── assets/                  # put your input image here
├── src/
│   ├── detect_path.py       # OpenCV contour detection → path.json
│   └── blender_scene.py     # Blender scene build + cinematic render
├── run_local.sh             # local end-to-end pipeline runner
├── requirements.txt
├── .github/workflows/render.yml   # CI: renders on GitHub's runners
└── README.md
```
