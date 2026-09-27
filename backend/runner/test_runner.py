"""Part 4 test: call the runner the way the control plane will, from VM 1 over the private network.

    python3 test_runner.py <photo> [<video>]
Reads RUNNER_URL and RUNNER_TOKEN from /etc/shltr/runner.env (copied from VM 2) or the environment.

Checks:
  R1  wrong token is refused (401)
  R2  photo  -> sandbox.started, log lines, depth.ready, sandbox.destroyed; room.glb downloads
  R3  video  -> the same plus frames.ready with evidence stills (if a video is given)
  R4  corrupted file -> case.error, and the sandbox is still destroyed
  R5  no sandboxes left running afterwards
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path


def load_env() -> tuple[str, str]:
    env = dict(os.environ)
    path = Path("/etc/shltr/runner.env")
    if path.exists():
        for line in path.read_text().splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                env.setdefault(k, v)
    url = env.get("RUNNER_URL") or f"http://{env.get('RUNNER_BIND', '10.40.0.4')}:{env.get('RUNNER_PORT', '8700')}"
    return url, env["RUNNER_TOKEN"]


URL, TOKEN = load_env()
results: dict[str, bool] = {}


def check(name: str, ok: bool, detail: str) -> None:
    results[name] = results.get(name, True) and ok
    print(f"  {'PASS' if ok else 'FAIL'}  {name:<34} {detail}", flush=True)


def request(path: str, token: str = TOKEN, body: bytes | None = None, ctype: str | None = None):
    req = urllib.request.Request(URL + path, data=body, method="POST" if body else "GET")
    req.add_header("Authorization", f"Bearer {token}")
    if ctype:
        req.add_header("Content-Type", ctype)
    return urllib.request.urlopen(req, timeout=400)


def upload(name: str, data: bytes) -> list[dict]:
    boundary = uuid.uuid4().hex
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{name}\"\r\n"
            f"Content-Type: application/octet-stream\r\n\r\n").encode() + data + f"\r\n--{boundary}--\r\n".encode()
    events, start = [], time.time()
    with request("/jobs/reconstruct", body=body, ctype=f"multipart/form-data; boundary={boundary}") as resp:
        for raw in resp:
            ev = json.loads(raw)
            events.append(ev)
            if ev["type"] != "log.line":
                print(f"        {time.time() - start:5.1f}s  {ev['type']:<18} {json.dumps(ev['data'])[:110]}", flush=True)
            else:
                print(f"        {time.time() - start:5.1f}s  log  {ev['data']['text'][:100]}", flush=True)
    return events


def types(events: list[dict]) -> list[str]:
    return [e["type"] for e in events if e["type"] != "log.line"]


def run_good(label: str, path: Path, expect_frames: bool) -> None:
    print(f"{label} · {path.name} ({path.stat().st_size // 1024} KB)")
    ev = upload(path.name, path.read_bytes())
    kinds = types(ev)
    need = ["sandbox.started", "depth.ready"] + (["frames.ready"] if expect_frames else []) + ["sandbox.destroyed"]
    check(f"{label} events in order", [k for k in kinds if k in need] == need, " -> ".join(kinds))
    ready = next((e for e in ev if e["type"] == "depth.ready"), None)
    if ready:
        with request(ready["data"]["glb_url"]) as resp:
            glb = resp.read()
        check(f"{label} room.glb downloads", glb[:4] == b"glTF", f"{len(glb) // 1024} KB, {ready['data']['vertices']} vertices, median {ready['data']['median_depth_m']} m")
    if expect_frames:
        fr = next((e for e in ev if e["type"] == "frames.ready"), None)
        n = len(fr["data"]["frames"]) if fr else 0
        check(f"{label} evidence stills", n > 0, f"{n} frames, sharpest at {fr['data']['best_t'] if fr else '?'} s")
    gone = next((e for e in ev if e["type"] == "sandbox.destroyed"), {}).get("data", {})
    check(f"{label} sandbox destroyed", bool(gone), f"{gone.get('sandbox_id')} after {gone.get('lifetime_s')} s")


def main() -> None:
    print(f"Runner at {URL}")
    try:
        request("/health", token="wrong")
        check("R1 wrong token refused", False, "request was accepted")
    except urllib.error.HTTPError as err:
        check("R1 wrong token refused", err.code == 401, f"HTTP {err.code}")
    with request("/health") as resp:
        health = json.loads(resp.read())
    print(f"  health: {health}")

    run_good("R2 photo", Path(sys.argv[1]), expect_frames=False)
    if len(sys.argv) > 2:
        run_good("R3 video", Path(sys.argv[2]), expect_frames=True)

    print("R4 · corrupted video (random bytes named .mp4)")
    ev = upload("broken.mp4", os.urandom(200_000))
    kinds = types(ev)
    check("R4 fails cleanly", "case.error" in kinds and "depth.ready" not in kinds, " -> ".join(kinds))
    check("R4 sandbox still destroyed", kinds[-1:] == ["sandbox.destroyed"], kinds[-1] if kinds else "no events")

    with request("/health") as resp:
        left = json.loads(resp.read())["sandboxes"]
    check("R5 nothing left running", left == 0, f"{left} sandboxes")

    failed = [k for k, v in results.items() if not v]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed" + (f"; failed: {', '.join(failed)}" if failed else ""))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
