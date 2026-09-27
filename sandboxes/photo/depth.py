"""Photo sandbox entrypoint: room photo in, metric depth map and 3D room out.

Reads the first photo (sorted by name) from IN_DIR and writes to OUT_DIR:
  depth.png   colourised depth map (near = warm, far = cool)
  room.glb    textured triangle mesh (written directly, no trimesh) in metres; y up, camera at the origin looking down -z.
              The photo itself (at most TEXTURE_SIDE px, JPEG) is the mesh's baseColor texture.
  stats.json  {"width", "height", "median_depth_m", "vertices", "seconds", ...}

Runs offline with the Depth Anything V2 metric indoor weights baked into the image.
"""

import io
import json
import math
import os
import struct
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

IN_DIR = Path(os.environ.get("IN_DIR", "/in"))
OUT_DIR = Path(os.environ.get("OUT_DIR", "/out"))
MODEL_DIR = os.environ.get("MODEL_DIR", "/opt/model")
MODEL_ID = os.environ.get("MODEL_ID", "depth-anything/Depth-Anything-V2-Metric-Indoor-Large-hf")

# The photo is decoded at most this big; it becomes the mesh texture. A 12 MP
# phone photo is decoded at reduced size (JPEG draft mode), so memory stays low.
TEXTURE_SIDE = int(os.environ.get("TEXTURE_SIDE", "2048"))
TEXTURE_QUALITY = int(os.environ.get("TEXTURE_QUALITY", "85"))
# Short side of the image the depth model sees (a multiple of 14; 518 is the
# model's training size). Larger is sharper but slower (roughly quadratic).
INFER_SIZE = int(os.environ.get("INFER_SIZE", "518"))
# Long side of the mesh grid in pixels (one vertex per pixel). 640 gives about
# 270k vertices and a 10-13 MB room.glb.
MESH_SIDE = int(os.environ.get("MESH_SIDE", "640"))
# Kept for compatibility: take every Nth pixel of the mesh grid.
MESH_STEP = int(os.environ.get("MESH_STEP", "1"))
# A triangle is dropped when the depth around any of its corners (3x3 window)
# varies by more than this ratio, so object edges don't smear into "curtains".
EDGE_RATIO = float(os.environ.get("EDGE_RATIO", "1.08"))
# Also write the photo's colours per vertex (glTF COLOR_0). The current front end
# draws the room with vertex colours; set 0 once it uses the texture instead.
# Standard glTF viewers multiply COLOR_0 by the texture, so the room looks darker there.
VERTEX_COLORS = os.environ.get("VERTEX_COLORS", "1") == "1"
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
    img.draft("RGB", (TEXTURE_SIDE, TEXTURE_SIDE))  # JPEG: decode at reduced size, saves memory
    focal_35 = None
    try:
        exif = img.getexif().get_ifd(0x8769)  # Exif sub-IFD
        focal_35 = float(exif.get(0xA405) or 0) or None  # FocalLengthIn35mmFilm
    except Exception:
        pass
    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((TEXTURE_SIDE, TEXTURE_SIDE), Image.LANCZOS)
    return img, focal_35 or DEFAULT_FOCAL_35MM, focal_35 is not None


def estimate_depth(img, out_hw):
    """Metric depth in metres, resampled to out_hw (height, width). Returns (depth, model input size)."""
    import torch
    from transformers import AutoImageProcessor, AutoModelForDepthEstimation

    torch.set_num_threads(max(1, os.cpu_count() or 1))
    processor = AutoImageProcessor.from_pretrained(MODEL_DIR)
    model = AutoModelForDepthEstimation.from_pretrained(MODEL_DIR).eval()
    # keep_aspect_ratio + ensure_multiple_of=14 (from the model config) turn this
    # into "short side = INFER_SIZE, both sides multiples of 14".
    inputs = processor(images=img, size={"height": INFER_SIZE, "width": INFER_SIZE}, return_tensors="pt")
    in_hw = tuple(inputs["pixel_values"].shape[-2:])
    with torch.inference_mode():
        pred = model(**inputs).predicted_depth  # (1, h, w), metres
    depth = torch.nn.functional.interpolate(
        pred.unsqueeze(1), size=out_hw, mode="bilinear", align_corners=False, antialias=True
    )[0, 0]
    return depth.clamp(min=0.05).numpy().astype(np.float32), in_hw


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


def edge_mask(z):
    """True where the depth in a 3x3 window around a pixel varies by more than EDGE_RATIO."""
    p = np.pad(z, 1, mode="edge")
    h, w = z.shape
    shifts = [p[dy:dy + h, dx:dx + w] for dy in range(3) for dx in range(3)]
    return np.maximum.reduce(shifts) / np.minimum.reduce(shifts) > EDGE_RATIO


def jpeg_bytes(img):
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=TEXTURE_QUALITY)
    return buf.getvalue()


def write_glb(verts, uv, colours, faces, texture_jpeg):
    """Serialise one textured mesh as binary glTF 2.0.

    POSITION float32, TEXCOORD_0 normalised uint16, optional COLOR_0 (RGBA uint8),
    uint32 indices, and the photo as an embedded JPEG baseColor texture.
    """
    chunks, views, accessors = [], [], []

    def add(arr, target, comp, kind, normalized=False, minmax=False):
        data = np.ascontiguousarray(arr).tobytes()
        offset = sum(len(c) for c in chunks)
        chunks.append(data + bytes(-len(data) % 4))  # zero padding to 4 bytes
        view = {"buffer": 0, "byteOffset": offset, "byteLength": len(data)}
        if target:
            view["target"] = target
        views.append(view)
        if kind is None:
            return len(views) - 1
        acc = {"bufferView": len(views) - 1, "componentType": comp, "count": int(len(arr)), "type": kind}
        if normalized:
            acc["normalized"] = True
        if minmax:
            acc["min"] = arr.min(0).tolist()
            acc["max"] = arr.max(0).tolist()
        accessors.append(acc)
        return len(accessors) - 1

    attrs = {"POSITION": add(verts.astype(np.float32), 34962, 5126, "VEC3", minmax=True)}
    uv16 = np.round(np.clip(uv, 0, 1) * 65535).astype(np.uint16)
    attrs["TEXCOORD_0"] = add(uv16, 34962, 5123, "VEC2", normalized=True)
    if colours is not None:
        rgba = np.column_stack([colours, np.full(len(colours), 255, np.uint8)]).astype(np.uint8)
        attrs["COLOR_0"] = add(rgba, 34962, 5121, "VEC4", normalized=True)
    idx = faces.astype(np.uint32).ravel()
    indices = add(idx.reshape(-1, 1), 34963, 5125, "SCALAR")
    accessors[indices]["count"] = int(len(idx))
    image_view = add(np.frombuffer(texture_jpeg, np.uint8), None, None, None)

    binary = b"".join(chunks)
    gltf = {
        "asset": {"version": "2.0", "generator": "shltr photo sandbox depth.py"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0, "name": "room"}],
        "meshes": [{"name": "room", "primitives": [{"attributes": attrs, "indices": indices, "material": 0, "mode": 4}]}],
        "materials": [{
            "name": "photo",
            "pbrMetallicRoughness": {"baseColorTexture": {"index": 0}, "metallicFactor": 0.0, "roughnessFactor": 1.0},
            "doubleSided": True,
        }],
        "textures": [{"sampler": 0, "source": 0}],
        "samplers": [{"magFilter": 9729, "minFilter": 9987, "wrapS": 33071, "wrapT": 33071}],
        "images": [{"bufferView": image_view, "mimeType": "image/jpeg"}],
        "accessors": accessors,
        "bufferViews": views,
        "buffers": [{"byteLength": len(binary)}],
    }
    js = json.dumps(gltf, separators=(",", ":")).encode()
    js += b" " * (-len(js) % 4)
    total = 12 + 8 + len(js) + 8 + len(binary)
    return b"".join([
        struct.pack("<4sII", b"glTF", 2, total),
        struct.pack("<I4s", len(js), b"JSON"), js,
        struct.pack("<I4s", len(binary), b"BIN" + bytes(1)), binary,
    ])


def build_mesh(tex_img, depth, focal_35):
    """Back-project the depth grid into a triangle mesh textured with the photo. Returns (glb, info)."""
    h, w = depth.shape
    # A 35 mm-equivalent focal length is relative to the 43.27 mm diagonal of a
    # 36x24 mm frame; scale it to this grid's diagonal in pixels.
    f_px = focal_35 / 43.27 * math.hypot(w, h)
    cx, cy = (w - 1) / 2, (h - 1) / 2

    vs = np.arange(0, h, MESH_STEP)
    us = np.arange(0, w, MESH_STEP)
    uu, vv = np.meshgrid(us, vs)
    z = depth[vv, uu]
    x = (uu - cx) / f_px * z
    y = -(vv - cy) / f_px * z  # image rows go down, y goes up
    verts = np.stack([x, y, -z], axis=-1).reshape(-1, 3)
    # Pixel centres in texture space; glTF puts (0, 0) at the image's top-left.
    uv = np.stack([(uu + 0.5) / w, (vv + 0.5) / h], axis=-1).reshape(-1, 2)

    gh, gw = z.shape
    idx = np.arange(gh * gw).reshape(gh, gw)
    a, b = idx[:-1, :-1].ravel(), idx[:-1, 1:].ravel()
    c, d = idx[1:, :-1].ravel(), idx[1:, 1:].ravel()
    # Counter-clockwise as seen from the camera, so normals face the viewer.
    faces = np.concatenate([np.stack([a, c, b], 1), np.stack([b, c, d], 1)])
    edges = edge_mask(z).ravel()
    faces = faces[~edges[faces].any(1)]

    # Drop vertices no triangle uses, and renumber.
    used = np.zeros(len(verts), bool)
    used[faces.ravel()] = True
    remap = np.cumsum(used) - 1
    faces = remap[faces]
    verts, uv = verts[used], uv[used]

    colours = None
    if VERTEX_COLORS:
        small = np.asarray(tex_img.resize((w, h), Image.BILINEAR))
        colours = small[vv, uu].reshape(-1, 3)[used]
    glb = write_glb(verts, uv, colours, faces, jpeg_bytes(tex_img))
    return glb, {"vertices": int(len(verts)), "faces": int(len(faces)), "focal_px": f_px}


def main():
    t0 = time.monotonic()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    photos = find_photos()
    photo = photos[0]
    if len(photos) > 1:
        log(f"{len(photos)} photos found; reconstructing {photo.name} only")

    img, focal_35, focal_from_exif = load_photo(photo)
    log(f"{photo.name}: {img.width}x{img.height}, focal {focal_35:g} mm (35 mm eq.)")

    scale = MESH_SIDE / max(img.size)
    mesh_w, mesh_h = max(2, round(img.width * scale)), max(2, round(img.height * scale))
    t1 = time.monotonic()
    depth, in_hw = estimate_depth(img, (mesh_h, mesh_w))
    t_model = time.monotonic() - t1
    median = float(np.median(depth))
    log(f"model input {in_hw[1]}x{in_hw[0]} in {t_model:.1f} s; depth {depth.min():.2f}-{depth.max():.2f} m, median {median:.2f} m")

    colourise(depth).save(OUT_DIR / "depth.png")
    glb, mesh = build_mesh(img, depth, focal_35)
    (OUT_DIR / "room.glb").write_bytes(glb)

    # width, height and focal_px describe the mesh grid, so a vertex's pixel is
    # (x / -z * focal_px + (width - 1) / 2, ...), exactly as before (geom.py relies on it).
    stats = {
        "width": mesh_w,
        "height": mesh_h,
        "median_depth_m": round(median, 3),
        "min_depth_m": round(float(depth.min()), 3),
        "max_depth_m": round(float(depth.max()), 3),
        "vertices": mesh["vertices"],
        "faces": mesh["faces"],
        "focal_px": round(mesh["focal_px"], 1),
        "focal_from_exif": focal_from_exif,
        "photo": photo.name,
        "model": MODEL_ID,
        "model_input": [int(in_hw[1]), int(in_hw[0])],
        "mesh_grid": [mesh_w, mesh_h],
        "texture": "jpeg",
        "texture_size": [img.width, img.height],
        "vertex_colors": VERTEX_COLORS,
        "glb_bytes": len(glb),
        "model_seconds": round(t_model, 2),
        "seconds": round(time.monotonic() - t0, 2),
    }
    (OUT_DIR / "stats.json").write_text(json.dumps(stats, indent=2) + "\n")
    log(json.dumps(stats))


if __name__ == "__main__":
    main()
