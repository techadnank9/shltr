# Sample room

Real output from the Part 2 photo sandbox, for building the front end before the backend exists.

| File | What it is |
|---|---|
| `flooded-room.glb` | 3D mesh in metres: y up, camera at the origin looking down -z, vertex colours from the photo. 38,104 vertices, 74,520 faces |
| `flooded-room-depth.png` | The depth map (red is near, blue is far) |
| `flooded-room-stats.json` | `stats.json` from the same run |

**Source image:** generated on Sept 27, 2026 with Vultr Serverless Inference `z-image-turbo` (prompt: a flooded living room seen from the doorway). It's generated, so we have the rights to use it, but it's for development only. The live demo uses real photos.

**How it was made:** the exact Part 2 test command (network off, read-only, 2 GB, 2 CPUs), 33.5 s on a Windows laptop.

## FEMA sample (photo quality pass)

| File | What it is |
|---|---|
| `fema-belfry-ky.glb` | 3D room from a real flood-damaged room, built by the current photo sandbox (Depth Anything V2 Metric-Indoor Large). The photo is the texture (1920 px JPEG, `baseColorTexture`; the sandbox keeps up to 2048 px), with vertex colours as well, so standard glTF viewers show it a little darker than the photo. 268,282 vertices, 12.2 MB |
| `fema-belfry-ky-depth.png` | Its depth map (red is near, blue is far) |
| `fema-belfry-ky-stats.json` | `stats.json` from the same run |

**Source image:** "FEMA - 41326 - Damaged home interior in Kentucky.jpg", Belfry, KY, June 6, 2009, photo by Rob Melendez / FEMA, https://commons.wikimedia.org/wiki/File:FEMA_-_41326_-_Damaged_home_interior_in_Kentucky.jpg. A US federal government work, so public domain; details in `datasets/README.md`.

**How it was made:** a microVM on VM 2 (`--no-net --cpus 4 --memory 3072M`), 22.7 s including the microVM boot, from the 1920 px Commons thumbnail that `datasets/fetch.py` downloads.
