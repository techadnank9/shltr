"""Rebuild the survivor's photo from room.glb vertex colours, and print 3D points
at chosen pixels so damage markers can sit on real surfaces.

Run inside the Part 2 image (it has numpy, Pillow and trimesh):
  docker run --rm --entrypoint python -v "$PWD/frontend:/f" shltr-photo /f/scripts/room_photo.py
"""
import json
import sys

import numpy as np
import trimesh
from PIL import Image

W, H, F = 518, 296, 358.5  # from design/samples/flooded-room-stats.json
mesh = trimesh.load("/f/public/demo/room.glb", force="mesh")
v = np.asarray(mesh.vertices)
c = np.asarray(mesh.visual.vertex_colors)[:, :3]
print("bounds", v.min(0).round(2).tolist(), v.max(0).round(2).tolist(), len(v))

z = -v[:, 2]
u = v[:, 0] / z * F + (W - 1) / 2
w = -v[:, 1] / z * F + (H - 1) / 2
img = np.zeros((H, W, 3), np.uint8)
order = np.argsort(-z)  # far first, near overwrites
for dx in (0, 1):
    for dy in (0, 1):
        ui = np.clip(np.round(u[order]).astype(int) + dx, 0, W - 1)
        vi = np.clip(np.round(w[order]).astype(int) + dy, 0, H - 1)
        img[vi, ui] = c[order]
Image.fromarray(img).resize((W * 2, H * 2), Image.LANCZOS).save("/f/public/demo/photo.jpg", quality=88)

# 3D point nearest each requested pixel: python room_photo.py '[[u,v],...]'
if len(sys.argv) > 1:
    for pu, pv in json.loads(sys.argv[1]):
        i = np.argmin((u - pu) ** 2 + (w - pv) ** 2)
        print([pu, pv], v[i].round(2).tolist())
