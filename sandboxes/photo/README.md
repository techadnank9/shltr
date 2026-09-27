# Photo sandbox

One room photo in, a 3D room out. Runs Depth Anything V2 (metric, indoor, small) on CPU inside a container with **no network**; the weights are baked into the image at build time.

## Build

```
docker build -t shltr-photo sandboxes/photo
```

About 2 minutes the first time (CPU torch plus about 100 MB of weights).

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
| `room.glb` | Coloured triangle mesh in metres. y up, camera at the origin looking down -z. Triangles across depth jumps are dropped so object edges don't smear |
| `stats.json` | `width`, `height`, `median_depth_m`, `min_depth_m`, `max_depth_m`, `vertices`, `faces`, `focal_px`, `focal_from_exif`, `photo`, `seconds` |

## How it works

1. EXIF rotation is applied, and the photo is shrunk to 518 px on its long side (the model's native size). A 12 MP phone photo therefore stays well under 2 GB.
2. The model predicts depth in metres for each pixel.
3. Every second pixel is back-projected with a pinhole camera. The focal length comes from the EXIF `FocalLengthIn35mmFilm` tag, or defaults to 26 mm (a typical phone main camera). The grid is then triangulated.

## Settings (environment variables)

| Variable | Default | Effect |
|---|---|---|
| `MAX_SIDE` | 518 | Long side of the photo before inference |
| `MESH_STEP` | 2 | Mesh grid step in pixels (1 = about 200k vertices) |
| `EDGE_RATIO` | 1.08 | Drop a triangle whose far corner is this much deeper than its near corner |
| `IN_DIR` / `OUT_DIR` / `MODEL_DIR` | `/in` / `/out` / `/opt/model` | Paths |

## Test

Passes when the run finishes in under 60 s with `--network none`, `out/room.glb` looks like the room in a glTF viewer (https://gltf-viewer.donmccurdy.com), and `median_depth_m` is roughly 2–5 m for a normal room.

## Notes for the microVM (Part 4)

- The container runs as UID 10001 with a read-only root. It needs a writable `/tmp` (tmpfs) and a writable `/out`, and it reads `/in`.
- The network can stay off completely: `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1` are set, and the weights are in `/opt/model`.
- Peak memory is well under 2 GB. torch uses every CPU it can see, so the microVM's CPU count sets the speed.
- The image works on amd64 and arm64 (CPU torch wheels exist for both). Build it on VM 2 (amd64), or build it with `--platform linux/amd64`.

## Video (added in Part 4)

The entry point is now `prepare.py`, which accepts a photo or a short video in `/in`:

- **Photo:** runs `depth.py` exactly as before, and adds `"source_kind": "photo"` to `stats.json`.
- **Video** (`.mp4`, `.mov`, `.m4v`, `.webm`, `.mkv`, `.avi`, `.3gp`): `ffmpeg` extracts 1 frame per second (at most 30, at most 1280 px wide) inside the sandbox. Each frame gets a sharpness score, the sharpest one goes through `depth.py`, and up to 6 sharp frames spread across the video are saved as `/out/frames/frame_NN.jpg` with `/out/frames.json` (`source`, `kind`, `duration_s`, `best`, `frames: [{file, t, sharpness}]`). `stats.json` gains `source_kind`, `source` and `best_frame_t`.

Settings: `MAX_FRAMES` (30) and `EVIDENCE_FRAMES` (6). A corrupted video exits non-zero with ffmpeg's error, and the runner reports it as `case.error`.

In a Microsandbox microVM, mount the output folder with `uid=10001,gid=10001` (for example `-v /srv/job/out:/out:uid=10001,gid=10001`) so the image's non-root user can write to it.
