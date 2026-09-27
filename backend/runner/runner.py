"""Shltr runner: lives on VM 2 (the sandbox host) and runs untrusted work in throwaway microVMs.

It listens only on the private network (VM 2 has no public ports), and every request needs
the shared RUNNER_TOKEN. VM 1's control plane is its only client.

    GET  /health                       status, Microsandbox version, sandboxes running
    POST /jobs/reconstruct             multipart: file (photo or video), case_id (optional)
                                       -> newline-delimited JSON events, streamed live
    GET  /jobs/{job_id}/files/{path}   outputs: room.glb, depth.png, stats.json, frames/...

Events use the docs/EVENTS.md types, without seq/ts (the control plane adds those):
    {"type": "sandbox.started", "job_id": "...", "data": {...}}
"""
import asyncio
import json
import os
import re
import secrets
import shutil
import time
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

TOKEN = os.environ.get("RUNNER_TOKEN", "")
JOBS = Path(os.environ.get("RUNNER_JOBS", "/srv/shltr/jobs"))
MSB = os.environ.get("MSB_BIN", "/root/.local/bin/msb")
IMAGE = os.environ.get("PHOTO_IMAGE", "shltr-photo:latest")
MAX_UPLOAD = int(os.environ.get("MAX_UPLOAD_MB", "100")) * 1024 * 1024
LIMITS = {"cpus": 4, "memory_mb": 3072, "timeout_s": 180, "network": "none"}
SANDBOX_UID = 10001  # the non-root user inside the photo image
PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".bmp", ".tif", ".tiff"}
VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi", ".3gp"}
JOB_ID = re.compile(r"^[a-z0-9]{12}$")

if not TOKEN:
    raise SystemExit("RUNNER_TOKEN is not set; refusing to start without authentication.")

app = FastAPI(title="shltr-runner")
slots = asyncio.Semaphore(int(os.environ.get("RUNNER_SLOTS", "1")))  # 4 CPUs: one heavy job at a time


def authorised(authorization: str = Header(default="")) -> None:
    if not secrets.compare_digest(authorization, f"Bearer {TOKEN}"):
        raise HTTPException(status_code=401, detail="missing or wrong runner token")


def event(event_type: str, job_id: str, /, **data) -> bytes:
    # Positional-only parameters, so event fields such as `kind` can never collide with them.
    return (json.dumps({"type": event_type, "job_id": job_id, "data": data}) + "\n").encode()


async def msb(*args: str) -> tuple[int, str]:
    proc = await asyncio.create_subprocess_exec(MSB, *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    out, _ = await proc.communicate()
    return proc.returncode, out.decode(errors="replace")


@app.get("/health", dependencies=[Depends(authorised)])
async def health() -> dict:
    _, version = await msb("--version")
    _, listing = await msb("list")
    running = 0 if "No sandboxes" in listing else max(0, len(listing.strip().splitlines()) - 1)
    return {"ok": True, "microsandbox": version.strip(), "image": IMAGE, "sandboxes": running, "limits": LIMITS}


@app.post("/jobs/reconstruct", dependencies=[Depends(authorised)])
async def reconstruct(file: UploadFile = File(...), case_id: str = Form(default="")) -> StreamingResponse:
    ext = Path(file.filename or "").suffix.lower()
    if ext not in PHOTO_EXTS | VIDEO_EXTS:
        raise HTTPException(status_code=415, detail=f"unsupported file type '{ext}'; send a photo or a short video")

    job_id = secrets.token_hex(6)
    in_dir, out_dir = JOBS / job_id / "in", JOBS / job_id / "out"
    in_dir.mkdir(parents=True)
    out_dir.mkdir(parents=True)
    # The survivor's file name is never used as a path; only the checked extension survives.
    target = in_dir / f"input{ext}"
    size = 0
    with target.open("wb") as fh:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD:
                shutil.rmtree(JOBS / job_id, ignore_errors=True)
                raise HTTPException(status_code=413, detail=f"file is over {MAX_UPLOAD // 2**20} MB")
            fh.write(chunk)
    for d in (in_dir, out_dir):
        os.chown(d, SANDBOX_UID, SANDBOX_UID)
    os.chown(target, SANDBOX_UID, SANDBOX_UID)
    kind = "video" if ext in VIDEO_EXTS else "photo"
    return StreamingResponse(run_job(job_id, kind, size, in_dir, out_dir), media_type="application/x-ndjson")


async def run_job(job_id: str, kind: str, size: int, in_dir: Path, out_dir: Path):
    name = f"sbx-{job_id}"
    async with slots:
        started = time.time()
        yield event("sandbox.started", job_id, sandbox_id=name, kind="photo", input=kind, bytes=size, limits=LIMITS)
        cmd = [
            MSB, "run", "--name", name, "--no-net",
            "--cpus", str(LIMITS["cpus"]), "--memory", f"{LIMITS['memory_mb']}M",
            "--max-duration", f"{LIMITS['timeout_s']}s",
            # uid/gid map the shared folder to the image's non-root user inside the microVM;
            # without it the sandbox user cannot write /out.
            "-v", f"{in_dir}:/in:ro", "-v", f"{out_dir}:/out:uid={SANDBOX_UID},gid={SANDBOX_UID}",
            IMAGE,
        ]
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        try:
            async for raw in proc.stdout:
                line = raw.decode(errors="replace").rstrip()
                if line:
                    yield event("log.line", job_id, sandbox_id=name, stream="stdout", text=line[:500])
            code = await asyncio.wait_for(proc.wait(), timeout=LIMITS["timeout_s"] + 30)
        except asyncio.TimeoutError:
            proc.kill()
            code = -9
        finally:
            # Destroy the microVM no matter how the run ended.
            await msb("stop", name)
            await msb("remove", "-f", name)

        stats_path = out_dir / "stats.json"
        if code == 0 and stats_path.exists():
            stats = json.loads(stats_path.read_text())
            base = f"/jobs/{job_id}/files"
            yield event("depth.ready", job_id, glb_url=f"{base}/room.glb", depth_url=f"{base}/depth.png",
                        vertices=stats.get("vertices"), median_depth_m=stats.get("median_depth_m"),
                        source_kind=stats.get("source_kind", kind), seconds=stats.get("seconds"))
            frames_path = out_dir / "frames.json"
            if frames_path.exists():
                meta = json.loads(frames_path.read_text())
                yield event("frames.ready", job_id, duration_s=meta.get("duration_s"), best_t=meta["best"]["t"],
                            frames=[{"url": f"{base}/{f['file']}", "t": f["t"]} for f in meta["frames"]])
        else:
            reason = "time limit reached, sandbox killed" if code in (-9, 137) else f"sandbox exited with code {code}"
            yield event("case.error", job_id, sandbox_id=name, message=f"Reconstruction failed: {reason}")
        yield event("sandbox.destroyed", job_id, sandbox_id=name, lifetime_s=round(time.time() - started, 1), exit_code=code)


@app.get("/jobs/{job_id}/files/{path:path}", dependencies=[Depends(authorised)])
async def job_file(job_id: str, path: str) -> FileResponse:
    if not JOB_ID.match(job_id):
        raise HTTPException(status_code=404)
    root = (JOBS / job_id / "out").resolve()
    target = (root / path).resolve()
    if root not in target.parents or not target.is_file():  # blocks ../ escapes
        raise HTTPException(status_code=404)
    return FileResponse(target)
