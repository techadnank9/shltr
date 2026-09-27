#!/usr/bin/env bash
# Multi-view room scan on a Vultr CPU server (VM 2, or a bigger temporary one).
#   setup                  install docker + ffmpeg, pull OpenDroneMap
#   run <name> [fps]       /root/scan/<name>/in holds a phone video or photos;
#                          writes /root/scan/<name>/<name>.glb and stats.json
# ODM runs with --network none: the photos never leave the box during reconstruction.
set -euo pipefail
cmd=${1:?setup or run}

if [ "$cmd" = setup ]; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -q && apt-get install -yq docker.io ffmpeg >/dev/null
  systemctl enable --now docker
  docker pull -q opendronemap/odm:latest
  docker pull -q python:3.12-slim
  echo "setup done"
  exit 0
fi

name=${2:?name}; fps=${3:-3}
base=/root/scan/$name; in=$base/in; img=$base/project/images
mkdir -p "$img"
start=$(date +%s)

# 1. frames: every video is sampled at <fps>, photos are copied; everything is scaled to 2400 px
shopt -s nullglob nocaseglob
for v in "$in"/*.{mp4,mov,m4v}; do
  ffmpeg -loglevel error -i "$v" -vf "fps=$fps,scale='min(2400,iw)':-2" -q:v 2 "$img/$(basename "${v%.*}")_%04d.jpg"
done
for p in "$in"/*.{jpg,jpeg,png,heic}; do
  ffmpeg -loglevel error -i "$p" -vf "scale='min(2400,iw)':-2" -q:v 2 "$img/$(basename "${p%.*}").jpg"
done
n=$(ls "$img" | wc -l)
echo "images: $n"

# 2. reconstruct (no network inside the container)
docker run --rm --network none -v "$base/project:/datasets/code" opendronemap/odm:latest \
  --project-path /datasets --feature-quality "${FEATURES:-high}" --min-num-features 12000 --pc-quality "${PC:-medium}" \
  --use-3dmesh --mesh-size "${MESH:-250000}" --mesh-octree-depth 11 --auto-boundary \
  --skip-orthophoto --skip-report --max-concurrency "$(nproc)" 2>&1 | tail -n 25
[ -f "$base/project/odm_texturing/odm_textured_model_geo.obj" ] || {
  echo "no textured model: the photos do not overlap enough (shoot slower, one step between shots)"; exit 2; }

# 3. textured OBJ -> GLB (textures capped at 4096 px)
docker run --rm -v "$base:/w" python:3.12-slim sh -c '
pip install -q trimesh pillow numpy >/dev/null 2>&1
python - <<EOF
import trimesh
from PIL import Image
s = trimesh.load("/w/project/odm_texturing/odm_textured_model_geo.obj", force="scene")
for g in s.geometry.values():
    im = getattr(getattr(g.visual, "material", None), "image", None)
    if im is not None and max(im.size) > 4096:
        im.thumbnail((4096, 4096), Image.LANCZOS)
        g.visual.material.image = im
s.export("/w/out.glb")
print("vertices", sum(len(g.vertices) for g in s.geometry.values()))
EOF' | tee "$base/convert.txt"
mv "$base/out.glb" "$base/$name.glb"
verts=$(awk '/vertices/{print $2}' "$base/convert.txt")
mins=$(( ($(date +%s) - start + 59) / 60 ))
echo "{\"images\": $n, \"vertices\": $verts, \"minutes\": $mins}" > "$base/stats.json"
ls -la "$base/$name.glb"; cat "$base/stats.json"
