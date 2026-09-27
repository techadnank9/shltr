"""Photo sandbox entrypoint: room photo in, metric depth map and 3D room out.

Reads the first photo (sorted by name) from IN_DIR and writes to OUT_DIR:
  depth.png   colourised depth map (near = warm, far = cool)
  room.glb    coloured triangle mesh in metres; y up, camera at the origin looking down -z
  stats.json  {"width", "height", "median_depth_m", "vertices", "seconds", ...}

Runs offline with the Depth Anything V2 metric indoor weights baked into the image.
"""

import json
import math
import os
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

IN_DIR = Path(os.environ.get("IN_DIR", "/in"))
OUT_DIR = Path(os.environ.get("OUT_DIR", "/out"))
MODEL_DIR = os.environ.get("MODEL_DIR", "/opt/model")

# Long side the photo is shrunk to before inference. Phone photos (12+ MP)
# would blow the 2 GB memory limit; 518 is the model's native input size.
MAX_SIDE = int(os.environ.get("MAX_SIDE", "518"))
# Mesh grid step in pixels. 2 gives ~50k vertices for a 518x388 depth map.
MESH_STEP = int(os.environ.get("MESH_STEP", "2"))
# A triangle is dropped when its far corner is this much deeper than its near
# corner, so object edges don't smear into long "curtains".
EDGE_RATIO = float(os.environ.get("EDGE_RATIO", "1.08"))
# Used when the photo has no EXIF focal length: a typical phone main camera.
DEFAULT_FOCAL_35MM = 26.0

PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


def log(msg):
    print(f"[photo] {msg}", flush=True)


def find_photos():
    photos = sorted(p for p in IN_DIR.iterdir() if p.is_file() and p.suffix.lower() in PHOTO_EXTS)
    if not photos:
        sys.exit(f"no photos found in {IN_DIR}")
    return photos


def load_photo(path):
    """Open, apply EXIF rotation, read the 35 mm-equivalent focal length, downscale."""
    img = Image.open(path)
    img.draft("RGB", (MAX_SIDE * 2, MAX_SIDE * 2))  # JPEG: decode at reduced size, saves memory
    focal_35 = None
    try:
        exif = img.getexif().get_ifd(0x8769)  # Exif sub-IFD
        focal_35 = float(exif.get(0xA405) or 0) or None  # FocalLengthIn35mmFilm
    except Exception:
        pass
    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
    return img, focal_35 or DEFAULT_FOCAL_35MM, focal_35 is not None


def estimate_depth(img):
    import torch
    from transformers import AutoImageProcessor, AutoModelForDepthEstimation

    torch.set_num_threads(max(1, os.cpu_count() or 1))
    processor = AutoImageProcessor.from_pretrained(MODEL_DIR)
    model = AutoModelForDepthEstimation.from_pretrained(MODEL_DIR).eval()
    inputs = processor(images=img, return_tensors="pt")
    with torch.inference_mode():
        pred = model(**inputs).predicted_depth  # (1, h, w), metres
    depth = torch.nn.functional.interpolate(
        pred.unsqueeze(1), size=(img.height, img.width), mode="bicubic", align_corners=False
    )[0, 0]
    return depth.clamp(min=0.05).numpy().astype(np.float32)


def colourise(depth):
    """Map depth to a turbo-like ramp; near is red/yellow, far is blue."""
    lo, hi = np.percentile(depth, [2, 98])
    t = np.clip((depth - lo) / max(hi - lo, 1e-6), 0, 1)
    stops = np.array(
        [[122, 4, 3], [249, 117, 29], [239, 216, 55], [100, 253, 106], [40, 188, 235], [48, 18, 59]],
        dtype=np.float32,
    )
    x = t * (len(stops) - 1)
    i = np.minimum(x.astype(int), len(stops) - 2)
    f = (x - i)[..., None]
    rgb = stops[i] * (1 - f) + stops[i + 1] * f
    return Image.fromarray(rgb.astype(np.uint8))


def build_mesh(img, depth, focal_35):
    """Back-project a grid of depth pixels into a coloured triangle mesh."""
    import trimesh

    h, w = depth.shape
    # A 35 mm-equivalent focal length is relative to the 43.27 mm diagonal of a
    # 36x24 mm frame; scale it to this image's diagonal in pixels.
    f_px = focal_35 / 43.27 * math.hypot(w, h)
    cx, cy = (w - 1) / 2, (h - 1) / 2

    vs = np.arange(0, h, MESH_STEP)
    us = np.arange(0, w, MESH_STEP)
    uu, vv = np.meshgrid(us, vs)
    z = depth[vv, uu]
    x = (uu - cx) / f_px * z
    y = -(vv - cy) / f_px * z  # image rows go down, y goes up
    verts = np.stack([x, y, -z], axis=-1).reshape(-1, 3)
    colours = np.asarray(img)[vv, uu].reshape(-1, 3)

    gh, gw = z.shape
    idx = np.arange(gh * gw).reshape(gh, gw)
    a, b = idx[:-1, :-1].ravel(), idx[:-1, 1:].ravel()
    c, d = idx[1:, :-1].ravel(), idx[1:, 1:].ravel()
    # Counter-clockwise as seen from the camera, so normals face the viewer.
    faces = np.concatenate([np.stack([a, c, b], 1), np.stack([b, c, d], 1)])
    zf = z.ravel()[faces]
    faces = faces[zf.max(1) / zf.min(1) < EDGE_RATIO]

    mesh = trimesh.Trimesh(
        vertices=verts,
        faces=faces,
        vertex_colors=np.column_stack([colours, np.full(len(colours), 255, np.uint8)]),
        process=False,
    )
    mesh.remove_unreferenced_vertices()
    return mesh, f_px


def main():
    t0 = time.monotonic()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    photos = find_photos()
    photo = photos[0]
    if len(photos) > 1:
        log(f"{len(photos)} photos found; reconstructing {photo.name} only")

    img, focal_35, focal_from_exif = load_photo(photo)
    log(f"{photo.name}: {img.width}x{img.height}, focal {focal_35:g} mm (35 mm eq.)")

    depth = estimate_depth(img)
    median = float(np.median(depth))
    log(f"depth {depth.min():.2f}-{depth.max():.2f} m, median {median:.2f} m")

    colourise(depth).save(OUT_DIR / "depth.png")
    mesh, f_px = build_mesh(img, depth, focal_35)
    mesh.export(OUT_DIR / "room.glb")

    stats = {
        "width": img.width,
        "height": img.height,
        "median_depth_m": round(median, 3),
        "min_depth_m": round(float(depth.min()), 3),
        "max_depth_m": round(float(depth.max()), 3),
        "vertices": int(len(mesh.vertices)),
        "faces": int(len(mesh.faces)),
        "focal_px": round(f_px, 1),
        "focal_from_exif": focal_from_exif,
        "photo": photo.name,
        "seconds": round(time.monotonic() - t0, 2),
    }
    (OUT_DIR / "stats.json").write_text(json.dumps(stats, indent=2) + "\n")
    log(json.dumps(stats))


if __name__ == "__main__":
    main()
