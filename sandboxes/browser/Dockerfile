# Browser sandbox: Chromium driven by Playwright, run inside a throwaway microVM.
# The microVM's network allowlist decides what it can reach; everything else fails.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

RUN pip install playwright==1.55.0 \
 && playwright install --with-deps chromium \
 && chmod -R a+rX /ms-playwright \
 && rm -rf /var/lib/apt/lists/*

COPY browse.py /app/browse.py

RUN useradd --uid 10001 --create-home sandbox
USER 10001
WORKDIR /home/sandbox

ENTRYPOINT ["python", "/app/browse.py"]
