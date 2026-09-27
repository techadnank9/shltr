# Photo sandbox: one room photo in (/in), depth map + 3D room out (/out).
# Runs with the network off, so the model weights are baked in at build time.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# CPU-only torch keeps the image small; the index serves amd64 and arm64 wheels.
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch==2.8.0 \
 && pip install transformers==4.56.1 huggingface_hub==0.35.0 numpy==2.3.3 pillow==11.3.0 trimesh==4.8.1

# ffmpeg decodes survivor videos. It only ever runs inside this no-network sandbox.
RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg \
 && rm -rf /var/lib/apt/lists/*

ARG MODEL_ID=depth-anything/Depth-Anything-V2-Metric-Indoor-Small-hf
RUN python -c "from huggingface_hub import snapshot_download; \
snapshot_download('${MODEL_ID}', local_dir='/opt/model', allow_patterns=['*.json', '*.safetensors'])"

# From here on nothing may reach the network.
ENV HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    HF_HOME=/tmp/hf \
    MODEL_DIR=/opt/model

COPY depth.py /app/depth.py
COPY prepare.py /app/prepare.py

RUN useradd --uid 10001 --no-create-home sandbox
USER 10001

# prepare.py takes a photo or a video, then calls depth.py.
ENTRYPOINT ["python", "/app/prepare.py"]
