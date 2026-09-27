"""Shltr control plane (VM 1): the brain. Plans each case, sends risky work to the runner on
VM 2 (throwaway microVMs), asks glm-5.3 on Vultr Serverless Inference to read the damage and
to write the measuring code, and streams every step to the 3D front end (docs/EVENTS.md v1).

    POST /api/cases                   multipart: file (photo or video), title   -> {case_id, url}
    WS   /ws/cases/{case_id}          events, replayed from seq 1 on every connect
    GET  /api/cases/{case_id}/events  the same events as JSON (tests, debugging)
    GET  /api/cases/{case_id}/photo   the sanitized photo (waits until the sandbox has made it)
    GET  /api/cases/{case_id}/files/{path}   room.glb, depth.png, frames/... proxied from the runner
    GET  /start                       upload page;  /  the front end (frontend/dist)

The survivor's upload is stored and forwarded, never opened here. The model and the browser
only ever see the re-encoded photo.jpg made inside the no-network sandbox.
"""
import asyncio
import json
import os
import re
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

import agent

CASES = Path(os.environ.get("CASES_DIR", "/srv/shltr/cases"))
RUNNER = os.environ.get("RUNNER_URL") or f"http://{os.environ.get('RUNNER_BIND', '10.40.0.4')}:{os.environ.get('RUNNER_PORT', '8700')}"
RUNNER_AUTH = {"Authorization": f"Bearer {os.environ.get('RUNNER_TOKEN', '')}"}
FRONTEND = Path(os.environ.get("FRONTEND_DIST", "/opt/shltr/frontend/dist"))
STATIC = Path(__file__).with_name("static")
MAX_UPLOAD = 100 * 1024 * 1024
MEDIA_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".mp4", ".mov", ".m4v", ".webm"}
CASE_ID = re.compile(r"^c_[a-z0-9]{8}$")
FILE_PATH = re.compile(r"^(room\.glb|depth\.png|photo\.jpg|stats\.json|frames/frame_\d{2}\.jpg)$")

app = FastAPI(title="shltr-control")


class Case:
    def __init__(self, case_id: str, title: str):
        self.id = case_id
        self.title = title
        self.dir = CASES / case_id
        self.events: list[dict] = []
        self.listeners: set[asyncio.Queue] = set()
        self.recon_job: str | None = None
        self.photo_ready = asyncio.Event()
        self.answer: asyncio.Queue = asyncio.Queue()

    def emit(self, event_type: str, **data) -> dict:
        ev = {"type": event_type, "case_id": self.id, "seq": len(self.events) + 1,
              "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "data": data}
        self.events.append(ev)
        with (self.dir / "events.jsonl").open("a") as fh:
            fh.write(json.dumps(ev) + "\n")
        for q in list(self.listeners):
            q.put_nowait(ev)
        return ev

    def log(self, text: str) -> None:
        self.emit("log.line", sandbox_id="control", stream="stdout", text=text)


cases: dict[str, Case] = {}


def get_case(case_id: str) -> Case:
    if not CASE_ID.match(case_id):
        raise HTTPException(status_code=404)
    case = cases.get(case_id)
    if case is None and (CASES / case_id / "events.jsonl").exists():
        # Replay a case from disk after a restart (read-only: its pipeline is not resumed).
        meta = json.loads((CASES / case_id / "case.json").read_text())
        case = Case(case_id, meta.get("title", ""))
        case.recon_job = meta.get("recon_job")
        case.events = [json.loads(line) for line in (CASES / case_id / "events.jsonl").read_text().splitlines() if line]
        case.photo_ready.set()
        cases[case_id] = case
    if case is None:
        raise HTTPException(status_code=404)
    return case


def save_meta(case: Case) -> None:
    (case.dir / "case.json").write_text(json.dumps({"title": case.title, "recon_job": case.recon_job}))


# ---------------------------------------------------------------- HTTP API


@app.post("/api/cases")
async def create_case(file: UploadFile = File(...), title: str = Form(default="")) -> dict:
    ext = Path(file.filename or "").suffix.lower()
    if ext not in MEDIA_EXTS:
        raise HTTPException(status_code=415, detail="Send a photo (jpg, png, webp, heic) or a short video (mp4, mov, webm).")
    case = Case(f"c_{secrets.token_hex(4)}", (title or "Untitled home").strip()[:80])
    case.dir.mkdir(parents=True)
    upload = case.dir / f"upload{ext}"  # stored as-is and forwarded; never decoded on this server
    size = 0
    with upload.open("wb") as fh:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD:
                raise HTTPException(status_code=413, detail="The file is over 100 MB. Send a shorter video or a photo.")
            fh.write(chunk)
    cases[case.id] = case
    save_meta(case)
    asyncio.create_task(run_case(case, upload))
    return {"case_id": case.id, "url": f"/?source=ws&case={case.id}"}


@app.get("/api/cases/{case_id}/events")
async def case_events(case_id: str) -> JSONResponse:
    return JSONResponse(get_case(case_id).events)


@app.get("/api/cases/{case_id}/photo")
async def case_photo(case_id: str) -> Response:
    case = get_case(case_id)
    try:
        await asyncio.wait_for(case.photo_ready.wait(), timeout=90)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=404, detail="photo not ready") from None
    return await case_file(case_id, "photo.jpg")


@app.get("/api/cases/{case_id}/files/{path:path}")
async def case_file(case_id: str, path: str) -> Response:
    case = get_case(case_id)
    if not case.recon_job or not FILE_PATH.match(path):
        raise HTTPException(status_code=404)
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{RUNNER}/jobs/{case.recon_job}/files/{path}", headers=RUNNER_AUTH)
    if r.status_code != 200:
        raise HTTPException(status_code=404)
    kind = {"glb": "model/gltf-binary", "png": "image/png", "jpg": "image/jpeg", "json": "application/json"}[path.rsplit(".", 1)[-1]]
    return Response(r.content, media_type=kind, headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "max-age=3600"})


@app.websocket("/ws/cases/{case_id}")
async def case_socket(ws: WebSocket, case_id: str) -> None:
    try:
        case = get_case(case_id)
    except HTTPException:
        await ws.close(code=4404)
        return
    await ws.accept()
    queue: asyncio.Queue = asyncio.Queue()
    for ev in list(case.events):  # replay from seq 1 on every (re)connect
        await ws.send_json(ev)
    case.listeners.add(queue)

    async def pump() -> None:
        while True:
            await ws.send_json(await queue.get())

    sender = asyncio.create_task(pump())
    try:
        while True:
            msg = await ws.receive_json()
            if msg.get("type") in ("approve", "decline"):
                approved = msg["type"] == "approve"
                case.emit("approval.result", approved=approved)
                case.answer.put_nowait(approved)
    except (WebSocketDisconnect, RuntimeError, ValueError):
        pass
    finally:
        sender.cancel()
        case.listeners.discard(queue)


@app.get("/start")
async def start_page() -> FileResponse:
    return FileResponse(STATIC / "start.html")


@app.get("/api/health")
async def health() -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{RUNNER}/health", headers=RUNNER_AUTH)
    return {"ok": r.status_code == 200, "runner": r.json() if r.status_code == 200 else r.status_code, "model": agent.MODEL, "cases": len(cases)}


# ---------------------------------------------------------------- the case pipeline


async def runner_stream(path: str, **kwargs):
    """POST to the runner and yield its NDJSON events as they arrive."""
    async with httpx.AsyncClient(timeout=httpx.Timeout(400, connect=10)) as client:
        async with client.stream("POST", f"{RUNNER}{path}", headers=RUNNER_AUTH, **kwargs) as r:
            if r.status_code != 200:
                body = (await r.aread()).decode(errors="replace")[:300]
                raise RuntimeError(f"runner {path} returned HTTP {r.status_code}: {body}")
            async for line in r.aiter_lines():
                if line.strip():
                    yield json.loads(line)


async def run_case(case: Case, upload: Path) -> None:
    started = time.time()
    try:
        case.emit("case.created", title=case.title, photos=[{"id": "p1", "url": f"/api/cases/{case.id}/photo"}])
        case.emit("plan.ready", steps=agent.PLAN)
        case.log(f"case {case.id} opened on the control plane · {upload.stat().st_size // 1024} KB upload stored, not opened")

        # 1. Rebuild the room in a throwaway microVM on VM 2.
        case.log("dispatch → runner on VM 2 · new microVM · network off")
        base = f"/api/cases/{case.id}/files"
        stats = None
        with upload.open("rb") as fh:
            async for ev in runner_stream("/jobs/reconstruct", files={"file": (upload.name, fh)}, data={"case_id": case.id}):
                t, d = ev["type"], ev["data"]
                case.recon_job = ev["job_id"]
                if t == "depth.ready":
                    save_meta(case)
                    stats = d
                    case.photo_ready.set()
                    case.emit("depth.ready", glb_url=f"{base}/room.glb", depth_url=f"{base}/depth.png",
                              vertices=d.get("vertices"), median_depth_m=d.get("median_depth_m"),
                              source_kind=d.get("source_kind"), seconds=d.get("seconds"))
                elif t == "frames.ready":
                    case.emit("frames.ready", duration_s=d.get("duration_s"), best_t=d.get("best_t"),
                              frames=[{"url": f"{base}/{f['url'].split('/files/', 1)[1]}", "t": f["t"]} for f in d["frames"]])
                else:
                    case.emit(t, **d)
        if stats is None:
            case.photo_ready.set()
            case.emit("case.error", message="We couldn't rebuild the room from this file. Try a clearer photo or a shorter video.")
            return

        # 2. Read the damage from the sanitized photo (vision model).
        photo = await fetch_runner_file(case.recon_job, "photo.jpg")
        case.log(f"{agent.MODEL} via Vultr Inference · reading the damage in the photo")
        assessment = await agent.assess_damage(photo)
        items = assessment.get("items", [])
        case.log(f"{agent.MODEL}: {len(items)} damage item(s) · {assessment.get('room', '')[:120]}")
        if not items:
            case.emit("estimate.total", cost_usd=0, range_pct=0)
            case.log("no visible damage found")
            return

        # 3. Pattern A: the model writes the measuring code, a microVM runs it, errors go back for a retry.
        result = await measure_with_retries(case, items)
        if result is None:
            case.emit("case.error", message="The measuring code failed 3 times. The damage list is shown without prices.")
            return
        for item in result["items"]:
            case.emit("damage.found", id=str(item["id"]), label=item["label"], metric=item.get("metric", ""),
                      cost_usd=round(float(item["cost_usd"])), position=[round(float(c), 3) for c in item["position"]])
            await asyncio.sleep(0.6)  # pace the markers so the scene can follow them
        case.emit("estimate.total", cost_usd=round(float(result["total_usd"])), range_pct=25)
        case.log(f"case assessed in {time.time() - started:.0f} s")
    except Exception as err:  # noqa: BLE001 - every failure must reach the survivor's screen
        case.photo_ready.set()
        case.emit("case.error", message=f"Something went wrong on our side: {err}"[:300])


async def fetch_runner_file(job_id: str, path: str) -> bytes:
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{RUNNER}/jobs/{job_id}/files/{path}", headers=RUNNER_AUTH)
        r.raise_for_status()
        return r.content


async def measure_with_retries(case: Case, items: list[dict]) -> dict | None:
    inputs = json.dumps({"items": items, "prices": agent.PRICES})
    messages = agent.code_messages(items)
    for attempt in range(1, 4):
        code = await agent.write_code(messages)
        case.emit("code.attempt", attempt=attempt, code=code, status="running")
        output, exit_code, result = "", None, None
        async for ev in runner_stream("/jobs/code", data={"code": code, "from_job": case.recon_job, "inputs": inputs}):
            t, d = ev["type"], ev["data"]
            if t == "code.result":
                output, exit_code, result = d["output"], d["exit_code"], d["result"]
            else:
                case.emit(t, **d)
        problem = agent.check_result(result) if exit_code == 0 else None
        if exit_code == 0 and not problem:
            case.emit("code.attempt", attempt=attempt, code=code, status="passed")
            return result
        stderr = output[-1500:] if exit_code != 0 else problem
        case.emit("code.attempt", attempt=attempt, code=code, status="failed", stderr=stderr)
        case.log(f"attempt {attempt} failed · sending the error back to {agent.MODEL}")
        messages += [{"role": "assistant", "content": f"```python\n{code}\n```"},
                     {"role": "user", "content": agent.retry_prompt(stderr)}]
    return None


# The front end is served last so /api, /ws and /start take priority.
if FRONTEND.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")
