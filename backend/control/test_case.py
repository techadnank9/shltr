"""Part 6 end-to-end test: run one full case through the public URL, like a survivor would.

    python backend/control/test_case.py <photo or video> [https://45-76-251-95.sslip.io]

Uploads the file, follows the case's events until it finishes, then checks the pieces:
  E1 upload accepted            E2 3D room built in a microVM     E3 sanitized photo served
  E4 damage found by the model  E5 code attempt passed (Pattern A, retries allowed)
  E6 markers have 3D positions and prices, and the total matches   E7 every sandbox destroyed
"""
import json
import sys
import time
import urllib.request
import uuid
from pathlib import Path

BASE = (sys.argv[2] if len(sys.argv) > 2 else "https://45-76-251-95.sslip.io").rstrip("/")
results: dict[str, bool] = {}


def check(name: str, ok: bool, detail: str) -> None:
    results[name] = ok
    print(f"  {'PASS' if ok else 'FAIL'}  {name:<32} {detail}", flush=True)


def get(path: str, timeout: int = 100) -> bytes:
    with urllib.request.urlopen(BASE + path, timeout=timeout) as resp:
        return resp.read()


def main() -> None:
    path = Path(sys.argv[1])
    boundary = uuid.uuid4().hex
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"title\"\r\n\r\nTest · {path.name}\r\n"
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{path.name}\"\r\n"
            "Content-Type: application/octet-stream\r\n\r\n").encode() + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(BASE + "/api/cases", data=body, method="POST",
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    start = time.time()
    created = json.loads(urllib.request.urlopen(req, timeout=120).read())
    case_id = created["case_id"]
    check("E1 upload accepted", bool(case_id), f"{case_id} · watch it live: {BASE}{created['url']}")

    seen, events = 0, []
    while time.time() - start < 420:
        events = json.loads(get(f"/api/cases/{case_id}/events"))
        for ev in events[seen:]:
            d = ev["data"]
            if ev["type"] == "log.line":
                print(f"   {time.time() - start:6.1f}s  log   [{d['sandbox_id']}] {d['text'][:100]}")
            elif ev["type"] == "code.attempt":
                extra = f" · {d.get('stderr', '')[-160:]!r}" if d["status"] == "failed" else ""
                print(f"   {time.time() - start:6.1f}s  code.attempt #{d['attempt']} {d['status']}{extra}")
            else:
                print(f"   {time.time() - start:6.1f}s  {ev['type']:<18} {json.dumps(d)[:110]}")
        seen = len(events)
        kinds = [e["type"] for e in events]
        if "estimate.total" in kinds or "case.error" in kinds:
            break
        time.sleep(2)
    kinds = [e["type"] for e in events]
    data = {e["type"]: e["data"] for e in events}

    depth = data.get("depth.ready")
    if depth:
        glb = get(depth["glb_url"])
        check("E2 3D room built in a microVM", glb[:4] == b"glTF", f"{len(glb) // 1024} KB, {depth['vertices']} vertices")
    else:
        check("E2 3D room built in a microVM", False, "no depth.ready")
    photo = get(f"/api/cases/{case_id}/photo")
    check("E3 sanitized photo served", photo[:3] == b"\xff\xd8\xff", f"{len(photo) // 1024} KB JPEG from the sandbox")
    damages = [e["data"] for e in events if e["type"] == "damage.found"]
    check("E4 damage found by the model", len(damages) > 0, ", ".join(d["label"] for d in damages) or "none")
    attempts = [e["data"] for e in events if e["type"] == "code.attempt" and e["data"]["status"] != "running"]
    check("E5 Pattern A code passed", any(a["status"] == "passed" for a in attempts),
          " → ".join(f"#{a['attempt']} {a['status']}" for a in attempts) or "no attempts")
    total = data.get("estimate.total", {}).get("cost_usd")
    item_sum = sum(d["cost_usd"] for d in damages)
    positions_ok = bool(damages) and all(len(d["position"]) == 3 for d in damages)
    total_ok = total is not None and abs(total - item_sum) <= 10 * max(1, len(damages))  # per-item rounding
    check("E6 priced 3D markers", positions_ok and total_ok,
          f"total ${total} · " + "; ".join(f"{d['label']} ${d['cost_usd']} @ {d['position']}" for d in damages)[:220])
    started = [e["data"]["sandbox_id"] for e in events if e["type"] == "sandbox.started"]
    destroyed = [e["data"]["sandbox_id"] for e in events if e["type"] == "sandbox.destroyed"]
    check("E7 every sandbox destroyed", bool(started) and sorted(started) == sorted(destroyed), f"{len(started)} started, {len(destroyed)} destroyed")
    if "case.error" in kinds:
        print("  case.error:", data["case.error"]["message"])

    failed = [k for k, v in results.items() if not v]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed in {time.time() - start:.0f} s" + (f"; failed: {', '.join(failed)}" if failed else ""))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
