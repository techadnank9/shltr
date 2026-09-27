"""Entry point of the photo sandbox. Accepts a photo or a short video in /in.

Photo: runs depth.py on it, unchanged.
Video: decodes it here, inside the no-network sandbox (video decoders are a classic
attack surface, so untrusted files are only ever opened in a throwaway microVM):
  1. ffmpeg extracts 1 frame per second (at most MAX_FRAMES), scaled to at most 1280 px
  2. each frame gets a sharpness score, so motion-blurred frames are skipped
  3. the sharpest frame is reconstructed in 3D by depth.py
  4. up to EVIDENCE_FRAMES sharp frames spread across the video are kept as evidence stills

Extra outputs for a video, next to depth.py's depth.png, room.glb and stats.json:
  /out/frames/frame_01.jpg ...   evidence stills
  /out/frames.json               {"source", "kind", "duration_s", "best", "frames": [{"file", "t", "sharpness"}]}
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

IN_DIR = Path(os.environ.get("IN_DIR", "/in"))
OUT_DIR = Path(os.environ.get("OUT_DIR", "/out"))
WORK = Path(os.environ.get("WORK_DIR", "/tmp/prepare"))
MAX_FRAMES = int(os.environ.get("MAX_FRAMES", "30"))
EVIDENCE_FRAMES = int(os.environ.get("EVIDENCE_FRAMES", "6"))
VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi", ".3gp"}
DEPTH = [sys.executable, "/app/depth.py"]


def log(msg: str) -> None:
    print(f"[prepare] {msg}", flush=True)


def sharpness(path: Path) -> float:
    """Variance of the Laplacian on a small greyscale copy: higher means sharper."""
    img = Image.open(path).convert("L")
    img.thumbnail((320, 320))
    a = np.asarray(img, dtype=np.float32)
    lap = 4 * a[1:-1, 1:-1] - a[:-2, 1:-1] - a[2:, 1:-1] - a[1:-1, :-2] - a[1:-1, 2:]
    return float(lap.var())


def duration_of(video: Path) -> float | None:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)],
        capture_output=True, text=True,
    )
    try:
        return round(float(out.stdout.strip()), 2)
    except ValueError:
        return None


def run_depth(in_dir: Path) -> None:
    result = subprocess.run(DEPTH, env={**os.environ, "IN_DIR": str(in_dir), "OUT_DIR": str(OUT_DIR)})
    if result.returncode:
        sys.exit(result.returncode)


def handle_video(video: Path) -> None:
    frames_dir = WORK / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    duration = duration_of(video)
    log(f"{video.name}: video, {duration if duration is not None else '?'} s; extracting 1 frame per second")
    cmd = [
        "ffmpeg", "-v", "error", "-nostdin", "-i", str(video),
        "-vf", "fps=1,scale='min(1280,iw)':-2", "-frames:v", str(MAX_FRAMES), "-q:v", "3",
        str(frames_dir / "f_%03d.jpg"),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    frames = sorted(frames_dir.glob("f_*.jpg"))
    if result.returncode or not frames:
        sys.exit(f"could not decode {video.name}: {result.stderr.strip()[:300] or 'no frames'}")

    scored = [{"path": p, "t": float(i), "sharpness": round(sharpness(p), 1)} for i, p in enumerate(frames)]
    best = max(scored, key=lambda f: f["sharpness"])
    log(f"{len(scored)} frames; sharpest at {best['t']:.0f} s (score {best['sharpness']})")

    # Evidence: the sharpest frame in each of EVIDENCE_FRAMES equal slices of the video.
    n = min(EVIDENCE_FRAMES, len(scored))
    picks = []
    for k in range(n):
        chunk = scored[k * len(scored) // n:(k + 1) * len(scored) // n]
        if chunk:
            picks.append(max(chunk, key=lambda f: f["sharpness"]))
    out_frames = OUT_DIR / "frames"
    out_frames.mkdir(parents=True, exist_ok=True)
    listed = []
    for i, f in enumerate(picks, 1):
        name = f"frame_{i:02d}.jpg"
        shutil.copyfile(f["path"], out_frames / name)
        listed.append({"file": f"frames/{name}", "t": f["t"], "sharpness": f["sharpness"]})

    best_dir = WORK / "best"
    best_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(best["path"], best_dir / "best.jpg")
    run_depth(best_dir)

    meta = {
        "source": video.name, "kind": "video", "duration_s": duration,
        "best": {"t": best["t"], "sharpness": best["sharpness"]}, "frames": listed,
    }
    (OUT_DIR / "frames.json").write_text(json.dumps(meta, indent=2) + "\n")
    stats_path = OUT_DIR / "stats.json"
    stats = json.loads(stats_path.read_text())
    stats.update({"source_kind": "video", "source": video.name, "best_frame_t": best["t"]})
    stats_path.write_text(json.dumps(stats, indent=2) + "\n")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in IN_DIR.iterdir() if p.is_file())
    if not files:
        sys.exit(f"nothing to process in {IN_DIR}")
    videos = [p for p in files if p.suffix.lower() in VIDEO_EXTS]
    if videos:
        handle_video(videos[0])
        return
    run_depth(IN_DIR)
    stats_path = OUT_DIR / "stats.json"
    if stats_path.exists():
        stats = json.loads(stats_path.read_text())
        stats["source_kind"] = "photo"
        stats_path.write_text(json.dumps(stats, indent=2) + "\n")


if __name__ == "__main__":
    main()
