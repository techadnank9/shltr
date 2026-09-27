# Report sandbox: turns a finished case into a Damage Evidence Report PDF.
# Runs our own fixed code (report.py) in a throwaway microVM with no network.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 MPLBACKEND=Agg

RUN pip install reportlab==4.4.4 matplotlib==3.10.6 numpy==2.3.3 pillow==11.3.0 trimesh==4.8.1

COPY report.py /app/report.py

RUN useradd --uid 10001 --no-create-home sandbox
USER 10001
ENV MPLCONFIGDIR=/tmp/mpl

ENTRYPOINT ["python", "/app/report.py"]
