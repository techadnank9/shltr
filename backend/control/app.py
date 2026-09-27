"""Shltr control plane (VM 1): the brain. Plans each case, sends risky work to the runner on
VM 2 (throwaway microVMs), asks glm-5.3 on Vultr Serverless Inference to read the damage and
to write the measuring code, and streams every step to the 3D front end (docs/EVENTS.md v1).

    POST /api/cases                   multipart: file (photo or video), title   -> {case_id, url}
    WS   /ws/cases/{case_id}          events, replayed from seq 1 on every connect
    GET  /api/cases/{case_id}/events  the same events as JSON (tests, debugging)
    GET  /api/cases/{case_id}/photo   the sanitized photo (waits until the sandbox has made it)
    GET  /api/cases/{case_id}/files/{path}   room.glb, depth.png, frames/... proxied from the runner
    GET  /start                       upload page;  /capture  guided phone recorder;  /  the front end (frontend/dist)

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
from urllib.parse import urlparse

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
JOB_ID = re.compile(r"^[a-z0-9]{12}$")
SHOT_PATH = re.compile(r"^(shots/\d{2}-[a-z]+\.png|report\.pdf)$")
# Our demo sites on VM 1's private address. Lookalike domains are mapped to it inside the browser
# sandbox, so the address bar shows the realistic name while nothing leaves our network.
SITES_TARGET = os.environ.get("SITES_TARGET", "10.40.0.3:8080")
DEMO_HOSTS = {"disaster-relief-claims.help", "relief-payments.help", "aid.shltr-demo.org"}
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
        self.jobs: set[str] = set()  # browser jobs whose screenshots this case may serve
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
        case.jobs = set(meta.get("jobs", []))
        case.events =[json.loads(line) for line in (CASES / case_id / "events.jsonl").read_text().splitlines() if line]
        case.photo_ready.set()
        cases[case_id] = case
    if case is None:
        raise HTTPException(status_code=404)
    return case


def save_meta(case: Case) -> None:
    (case.dir / "case.json").write_text(json.dumps({"title": case.title, "recon_job": case.recon_job, "jobs": sorted(case.jobs)}))


# ---------------------------------------------------------------- HTTP API


@app.post("/api/cases")
async def create_case(file: UploadFile = File(...), title: str = Form(default=""),
                      name: str = Form(default=""), phone: str = Form(default="")) -> dict:
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
    case.applicant = {"name": name.strip()[:80], "phone": phone.strip()[:30]}
    cases[case.id] = case
    save_meta(case)
    asyncio.create_task(run_case(case, upload))
    return {"case_id": case.id, "url": f"/case/{case.id}", "url_3d": f"/?source=ws&case={case.id}"}


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
            elif msg.get("type") == "check_link":
                asyncio.create_task(check_link(case, str(msg.get("url", ""))[:500]))
    except (WebSocketDisconnect, RuntimeError, ValueError):
        pass
    finally:
        sender.cancel()
        case.listeners.discard(queue)


@app.post("/api/cases/{case_id}/check-link")
async def check_link_api(case_id: str, body: dict) -> dict:
    """Same as the WebSocket's check_link message; used by tests."""
    case = get_case(case_id)
    asyncio.create_task(check_link(case, str(body.get("url", ""))[:500]))
    return {"ok": True}


@app.get("/api/cases/{case_id}/jobs/{job_id}/files/{path:path}")
async def job_file(case_id: str, job_id: str, path: str) -> Response:
    case = get_case(case_id)
    if not JOB_ID.match(job_id) or job_id not in case.jobs or not SHOT_PATH.match(path):
        raise HTTPException(status_code=404)
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{RUNNER}/jobs/{job_id}/files/{path}", headers=RUNNER_AUTH)
    if r.status_code != 200:
        raise HTTPException(status_code=404)
    kind = "application/pdf" if path.endswith(".pdf") else "image/png"
    headers = {"X-Content-Type-Options": "nosniff"}
    if kind == "application/pdf":
        headers["Content-Disposition"] = f'inline; filename="shltr-{case_id}-damage-report.pdf"'
    return Response(r.content, media_type=kind, headers=headers)


@app.post("/api/cases/{case_id}/claim")
async def claim_api(case_id: str) -> dict:
    """(Re)start filling the aid application for a finished case."""
    case = get_case(case_id)
    asyncio.create_task(file_claim(case))
    return {"ok": True}


@app.post("/api/cases/{case_id}/answer")
async def answer_api(case_id: str, body: dict) -> dict:
    """Same as the WebSocket's approve / decline messages."""
    case = get_case(case_id)
    approved = bool(body.get("approved"))
    case.emit("approval.result", approved=approved)
    case.answer.put_nowait(approved)
    return {"ok": True}


@app.post("/api/cases/{case_id}/report")
async def report_api(case_id: str) -> dict:
    """(Re)build the Damage Evidence Report, for example after a link check added security events."""
    case = get_case(case_id)
    asyncio.create_task(generate_report(case))
    return {"ok": True}


@app.get("/case/{case_id}")
async def case_page(case_id: str) -> FileResponse:
    """Case control room: follows one case end to end, live."""
    get_case(case_id)
    return FileResponse(STATIC / "case.html")


@app.get("/start")
async def start_page() -> FileResponse:
    return FileResponse(STATIC / "start.html")


@app.get("/capture")
async def capture_page() -> FileResponse:
    """Guided walkthrough recorder for a phone. Uploads to /api/cases just as /start does."""
    return FileResponse(STATIC / "capture.html")


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
        case.room_summary = assessment.get("room", "")
        await generate_report(case)
        await file_claim(case)
    except Exception as err:  # noqa: BLE001 - every failure must reach the survivor's screen
        case.photo_ready.set()
        case.emit("case.error", message=f"Something went wrong on our side: {err}"[:300])


async def generate_report(case: Case) -> None:
    """Build the Damage Evidence Report PDF in a fresh no-network microVM from the case so far."""
    try:
        if not case.recon_job:
            return
        evs = case.events
        total = next((e["data"] for e in reversed(evs) if e["type"] == "estimate.total"), {})
        data = {
            "case_id": case.id, "title": case.title, "model": agent.MODEL,
            "created": next((e["ts"] for e in evs if e["type"] == "case.created"), ""),
            "damages": [{k: e["data"].get(k) for k in ("label", "metric", "cost_usd")} for e in evs if e["type"] == "damage.found"],
            "total_usd": total.get("cost_usd", 0), "range_pct": total.get("range_pct", 25),
            "threats": [dict(t) for t in dict.fromkeys(  # each distinct attack once, in order
                tuple((k, e["data"].get(k)) for k in ("kind", "detail")) for e in evs
                if e["type"] == "threat.contained" and e["data"].get("kind") != "prompt_injection")],
            "sandboxes": sorted({e["data"]["sandbox_id"] for e in evs if e["type"] == "sandbox.started"}),
            "room_summary": getattr(case, "room_summary", ""),
        }
        case.log("building the Damage Evidence Report in a new microVM")
        meta, job = None, None
        async for ev in runner_stream("/jobs/report", data={"data": json.dumps(data), "from_job": case.recon_job}):
            t, d = ev["type"], ev["data"]
            job = ev["job_id"]
            if t == "report.result":
                meta = d.get("meta")
            else:
                case.emit(t, **d)
        if not meta:
            case.emit("case.error", message="The PDF report could not be built. The case itself is complete.")
            return
        case.jobs.add(job)
        save_meta(case)
        case.emit("report.ready", pdf_url=f"/api/cases/{case.id}/jobs/{job}/files/report.pdf",
                  pages=meta.get("pages"), bytes=meta.get("bytes"), sha256=meta.get("sha256"), evidence=meta.get("evidence", {}))
    except Exception as err:  # noqa: BLE001
        case.emit("case.error", message=f"The PDF report failed on our side: {err}"[:300])


PORTAL_HOST = "aid.shltr-demo.org"


def claim_steps(case: Case) -> list[dict]:
    """The aid form plan, from the case's real data only (ids from sites/README.md)."""
    who = getattr(case, "applicant", {}) or {}
    damages = [e["data"] for e in case.events if e["type"] == "damage.found"]
    step1 = [{"fill": "#applicant-name", "value": who.get("name") or "Survivor", "label": "name"},
             {"fill": "#applicant-phone", "value": who.get("phone") or "", "label": "phone"},
             {"fill": "#applicant-address", "value": case.title, "label": "address"},
             {"click": "#to-step-2", "label": "Continue"}]
    step2 = [{"select": "#damage-type", "value": "flood", "label": "cause of damage"},
             {"upload": "#evidence-upload", "file": ["photo.jpg", "room.glb"], "label": "photo and 3D room as evidence"},
             {"click": "#to-step-3", "label": "Continue"}]
    step3 = []
    for i, d in enumerate(damages, 1):
        if i > 3:
            step3.append({"ensure": f"#loss-item-{i}", "add": "#add-loss"})
        step3 += [{"fill": f"#loss-item-{i}", "value": f"{d['label']} ({d.get('metric', '')})"[:80], "label": f"loss {i}"},
                  {"fill": f"#loss-cost-{i}", "value": str(round(d["cost_usd"])), "label": f"cost {i}"}]
    step3.append({"click": "#to-step-4", "label": "Continue to review"})
    step4 = [{"click": "#submit-application", "label": "Submit"}]
    return [{"title": "Applicant", "actions": step1}, {"title": "Property and damage", "actions": step2},
            {"title": "Losses", "actions": step3}, {"title": "Review", "actions": step4}]


async def browse_with_frames(case: Case, task: dict) -> tuple[dict | None, str | None]:
    """Run a browser task, streaming its live frames to the case. Returns (report, job id)."""
    report, job = None, None
    async for ev in runner_stream("/jobs/browse", data={"task": json.dumps(task), "allow": SITES_TARGET, "from_job": case.recon_job}):
        t, d = ev["type"], ev["data"]
        if job is None:
            job = ev["job_id"]
            case.jobs.add(job)  # so its frames can be served while it runs
            save_meta(case)
        if t == "browse.result":
            report = d.get("report")
        elif t == "browser.frame":
            case.emit("browser.frame", sandbox_id=d["sandbox_id"], n=d["n"], title=d["title"], url=d["url"],
                      screenshot_url=f"/api/cases/{case.id}/jobs/{job}/files/{d['file']}")
        else:
            case.emit(t, **d)
    return report, job


async def file_claim(case: Case) -> None:
    """Pattern B: fill the (mock) aid portal live in a browser microVM, check every step with the
    vision model, pause for the survivor's approval, then submit in a fresh microVM."""
    try:
        steps = claim_steps(case)
        total = next((e["data"]["cost_usd"] for e in reversed(case.events) if e["type"] == "estimate.total"), 0)
        task = {"mode": "fill", "url": f"http://{PORTAL_HOST}/portal/", "host_map": {PORTAL_HOST: SITES_TARGET},
                "steps": steps, "stop_before": "#submit-application"}
        case.log("filling in the aid application in a browser microVM · you can watch it live")
        report, job = await browse_with_frames(case, task)
        if not report or report.get("error"):
            case.emit("case.error", message=f"The aid form could not be filled: {(report or {}).get('error', 'no report')}"[:300])
            return
        expectations = [
            f"Step 1 of 4 (applicant) with the name filled in and the address '{case.title}'.",
            "Step 2 of 4 (property and damage) with the cause of damage set to Flood and evidence files attached.",
            f"Step 3 of 4 (losses) listing the loss items with a total of about ${total:,.0f}.",
            "Step 4 of 4, the review page, showing the applicant, the damage and the losses, with a Submit button.",
        ]
        shots = [s for s in report.get("screenshots", []) if s["file"].startswith("shots/5")]
        for n, (s, expect) in enumerate(zip(shots, expectations), 1):
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.get(f"{RUNNER}/jobs/{job}/files/{s['file']}", headers=RUNNER_AUTH)
            check = await agent.verify_step(r.content, expect)
            case.emit("form.step", n=n, total=4, title=s["title"], verified=check["verified"], note=check["note"],
                      screenshot_url=f"/api/cases/{case.id}/jobs/{job}/files/{s['file']}")
        while not case.answer.empty():  # ignore any answer given before the question was asked
            case.answer.get_nowait()
        items = sum(1 for e in case.events if e["type"] == "damage.found")
        case.emit("approval.needed", summary=f"Submit the aid application for {case.title} with {items} loss items?",
                  amount_usd=total)
        approved = await case.answer.get()
        if not approved:
            case.log("you chose not to submit · the draft stays here, nothing was sent")
            return
        case.log("approved · submitting in a fresh browser microVM")
        report, job = await browse_with_frames(case, {**task, "mode": "submit"})
        if not report or not report.get("receipt_id"):
            case.emit("case.error", message="The application could not be submitted. Nothing was charged or sent.")
            return
        receipt = next((s["file"] for s in report["screenshots"] if s["title"] == "Receipt"), None)
        case.emit("claim.submitted", receipt_id=report["receipt_id"],
                  screenshot_url=f"/api/cases/{case.id}/jobs/{job}/files/{receipt}" if receipt else None)
    except Exception as err:  # noqa: BLE001
        case.emit("case.error", message=f"The claim step failed on our side: {err}"[:300])


async def check_link(case: Case, url: str) -> None:
    """Pattern B containment: open a suspicious link in a throwaway browser microVM, report every
    attack it tried as threat.contained, then let the vision model judge the page."""
    try:
        parsed = urlparse(url if "://" in url else f"http://{url}")
        host = (parsed.hostname or "").lower()
        if host not in DEMO_HOSTS:
            case.emit("link.checked", url=url, verdict="not_checked",
                      reasons=["This demo only opens our own demo links, never real outside sites."], advice="", screenshot_url=None)
            return
        target = f"http://{host}{parsed.path or '/'}"
        case.log(f"opening {host} in a throwaway browser microVM · network allowlist: our demo server only")
        task = {"mode": "inspect", "url": target, "host_map": {host: SITES_TARGET}}
        report, job = None, None
        async for ev in runner_stream("/jobs/browse", data={"task": json.dumps(task), "allow": SITES_TARGET}):
            t, d = ev["type"], ev["data"]
            job = ev["job_id"]
            if t == "browse.result":
                report = d.get("report")
            else:
                case.emit(t, **d)
        if not report:
            case.emit("case.error", message="We couldn't open that link safely. Don't open it yourself.")
            return
        case.jobs.add(job)
        save_meta(case)
        sid = f"sbx-{job}"
        for dl in report.get("downloads", []):
            case.emit("threat.contained", sandbox_id=sid, kind="download",
                      detail=f"{dl.get('name')} ({dl.get('bytes', '?')} bytes) was captured inside the sandbox and destroyed with it; it never reached your phone")
        allowed_prefix = f"http://{host}"
        for b in report.get("blocked", []):
            if b.get("url", "").startswith(allowed_prefix):
                continue
            carrying = " carrying page data" if b.get("post_data") else ""
            case.emit("threat.contained", sandbox_id=sid, kind="exfiltration",
                      detail=f"{b.get('method')} {b.get('url')}{carrying} was blocked: not on the sandbox's network allowlist")
        shot = next((s["file"] for s in report.get("screenshots", [])), None)
        shot_url = f"/api/cases/{case.id}/jobs/{job}/files/{shot}" if shot else None
        verdict = {"verdict": "unsure", "reasons": [], "advice": ""}
        if shot:
            case.log(f"{agent.MODEL} · judging the page from its screenshot and what it tried to do")
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.get(f"{RUNNER}/jobs/{job}/files/{shot}", headers=RUNNER_AUTH)
            verdict = await agent.judge_link(r.content, target, report)
        case.emit("link.checked", url=url, screenshot_url=shot_url, **verdict)
    except Exception as err:  # noqa: BLE001
        case.emit("case.error", message=f"The link check failed on our side: {err}"[:300])


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
