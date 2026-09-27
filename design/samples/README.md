# Sample room

Real output from the Part 2 photo sandbox, for building the front end before the backend exists.

| File | What it is |
|---|---|
| `flooded-room.glb` | 3D mesh in metres: y up, camera at the origin looking down -z, vertex colours from the photo. 38,104 vertices, 74,520 faces |
| `flooded-room-depth.png` | The depth map (red is near, blue is far) |
| `flooded-room-stats.json` | `stats.json` from the same run |

**Source image:** generated on Sept 27, 2026 with Vultr Serverless Inference `z-image-turbo` (prompt: a flooded living room seen from the doorway). It's generated, so we have the rights to use it, but it's for development only. The live demo uses real photos.

**How it was made:** the exact Part 2 test command (network off, read-only, 2 GB, 2 CPUs), 33.5 s on a Windows laptop.
