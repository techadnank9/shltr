# Photo sandbox

One room photo in, a 3D room out. Runs Depth Anything V2 (metric, indoor, **large** by default) on CPU inside a container with **no network**; the weights are baked into the image at build time. The 3D room is textured with the photo itself.

## Build

```
# Large (default): 1.3 GB of weights, 1.6 GB image
docker build -t shltr-photo sandboxes/photo
# Small: 100 MB of weights, about 2.5x faster, blurrier depth
docker build --build-arg MODEL_ID=depth-anything/Depth-Anything-V2-Metric-Indoor-Small-hf -t shltr-photo sandboxes/photo
```

About 2 minutes the first time (CPU torch plus the weights). The model name is kept in the image as `MODEL_ID` and reported in `stats.json`.

## Run

Put a photo of a room in `test-photos/` (git ignores it and `out/`), then:

```
docker run --rm --network none --read-only --memory 2g --cpus 2 --tmpfs /tmp \
  -v "$PWD/test-photos:/in:ro" -v "$PWD/out:/out" shltr-photo
```

If `/in` holds several photos, only the first one (sorted by name) is reconstructed.

## Outputs in `/out`

| File | What |
|---|---|
| `depth.png` | Colourised depth map: near is red/yellow, far is blue |
| `room.glb` | Textured triangle mesh in metres. y up, camera at the origin looking down -z. The photo (at most 2048 px, JPEG) is embedded as the material's `baseColorTexture`, with one UV per vertex; the photo's colours are also written per vertex (`COLOR_0`) for the current front end. Triangles across depth jumps are dropped so object edges don't smear. About 10-12 MB |
| `photo.jpg` | Sanitized copy of the input photo (or of the sharpest video frame), written by `prepare.py`: decoded inside the sandbox, EXIF rotation applied, re-encoded as a fresh RGB JPEG (quality 85, long side at most 1600 px) with **no EXIF, GPS, ICC profile or comments**. The control plane, the vision model and the browser use this copy and never decode the raw upload |
| `stats.json` | `width`, `height` (the mesh grid), `median_depth_m`, `min_depth_m`, `max_depth_m`, `vertices`, `faces`, `focal_px` (for the mesh grid), `focal_from_exif`, `photo`, `seconds`, plus `model`, `model_input` [w, h], `mesh_grid` [w, h], `texture` (`"jpeg"`), `texture_size` [w, h], `vertex_colors`, `glb_bytes`, `model_seconds`, and from `prepare.py` `source_kind` and `photo_file` (`"photo.jpg"`) |

A pixel of the mesh grid `(px, py)` at depth `z` is the vertex `((px - (width-1)/2) / focal_px * z, -(py - (height-1)/2) / focal_px * z, -z)`, as before; `backend/runner/geom.py` relies on this.

## How it works

1. EXIF rotation is applied, and the photo is decoded at most 2048 px on its long side (JPEG draft mode, so a 12 MP phone photo stays small in memory). This is the texture.
2. The model sees the photo with its short side at 518 px (both sides multiples of 14, for example 784x518) and predicts depth in metres.
3. The depth map is resampled to a 640 px mesh grid (for example 640x426), and every grid pixel is back-projected with a pinhole camera. The focal length comes from the EXIF `FocalLengthIn35mmFilm` tag, or defaults to 26 mm (a typical phone main camera). The grid is triangulated; a triangle is dropped when the depth in a 3x3 window around any of its corners varies by more than 8%, which cuts the mesh at object edges instead of stretching a sheet across them.
4. `room.glb` is written directly (no trimesh): positions (float32), UVs (normalized uint16), vertex colours (RGBA uint8, optional), uint32 indices and the JPEG texture.

## Settings (environment variables)

| Variable | Default | Effect |
|---|---|---|
| `TEXTURE_SIDE` | 2048 | Long side of the decoded photo, which becomes the texture |
| `TEXTURE_QUALITY` | 85 | JPEG quality of the texture |
| `INFER_SIZE` | 518 | Short side of the model input (a multiple of 14). Time grows roughly with its square |
| `MESH_SIDE` | 640 | Long side of the mesh grid, one vertex per pixel (about 260k vertices, 12 MB). 768 would be about 17 MB |
| `MESH_STEP` | 1 | Take every Nth pixel of the mesh grid |
| `EDGE_RATIO` | 1.08 | Drop triangles where the depth in a 3x3 window varies by more than this ratio |
| `VERTEX_COLORS` | 1 | Also write `COLOR_0`. The front end draws vertex colours today; set 0 once it uses the texture. Standard glTF viewers multiply `COLOR_0` by the texture, so the room looks darker there while this is 1 |
| `MODEL_ID` | set by the build | Reported in `stats.json` |
| `IN_DIR` / `OUT_DIR` / `MODEL_DIR` | `/in` / `/out` / `/opt/model` | Paths |

## Test

Test photos: `python datasets/fetch.py` downloads five public-domain FEMA photos of flood-damaged rooms into `test-photos/fema/` (see `datasets/README.md`).

Passes when the run finishes in under 60 s with `--network none`, `out/room.glb` looks like the room in a glTF viewer (https://gltf-viewer.donmccurdy.com), and `median_depth_m` is roughly 2–5 m for a normal room.

## Notes for the microVM (Part 4)

- The container runs as UID 10001 with a read-only root. It needs a writable `/tmp` (tmpfs) and a writable `/out`, and it reads `/in`.
- The network can stay off completely: `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1` are set, and the weights are in `/opt/model`.
- Peak memory fits the runner's 3 GB microVM with the Large model (tested on all five FEMA photos, a 1792x1024 PNG and a video). torch uses every CPU it can see, so the microVM's CPU count sets the speed.
- The image works on amd64 and arm64 (CPU torch wheels exist for both). Build it on VM 2 (amd64), or build it with `--platform linux/amd64`.

## Video (added in Part 4)

The entry point is now `prepare.py`, which accepts a photo or a short video in `/in`:

- **Photo:** runs `depth.py` exactly as before, and adds `"source_kind": "photo"` to `stats.json`.
- **Video** (`.mp4`, `.mov`, `.m4v`, `.webm`, `.mkv`, `.avi`, `.3gp`): `ffmpeg` extracts 1 frame per second (at most 30, at most 1280 px wide) inside the sandbox. Each frame gets a sharpness score, the sharpest one goes through `depth.py`, and up to 6 sharp frames spread across the video are saved as `/out/frames/frame_NN.jpg` with `/out/frames.json` (`source`, `kind`, `duration_s`, `best`, `frames: [{file, t, sharpness}]`). `stats.json` gains `source_kind`, `source` and `best_frame_t`.

Settings: `MAX_FRAMES` (30) and `EVIDENCE_FRAMES` (6). A corrupted video exits non-zero with ffmpeg's error, and the runner reports it as `case.error`.

In a Microsandbox microVM, mount the output folder with `uid=10001,gid=10001` (for example `-v /srv/job/out:/out:uid=10001,gid=10001`) so the image's non-root user can write to it.

## Quality settings (Sept 27, photo quality pass)

Measured in a microVM on VM 2 (`--no-net --cpus 4 --memory 3072M`), wall time including the microVM boot:

| | Before | After |
|---|---|---|
| Model | Metric-Indoor **Small** | Metric-Indoor **Large** |
| Model input | 518x350 (from a 518 px photo) | 784x518 (from a 2048 px photo) |
| Mesh | 518 px grid, step 2: about 38-44k vertices | 640 px grid, step 1: about 225-268k vertices |
| Colour | Vertex colours from the 518 px photo | The photo as a 2048 px JPEG texture, plus vertex colours |
| room.glb | 1.5-1.8 MB | 10-12.4 MB |
| Time per photo | 7.8 s | 22.5-25.4 s (Small with the new mesh and texture: 9.1 s) |

Large vs Small on the same photo (acy-la): 22.6 s vs 9.1 s. Large resolves doorways, studs and the far wall that Small blurs into one patch, so Large is the default. Build with the Small `MODEL_ID` if speed matters more.
