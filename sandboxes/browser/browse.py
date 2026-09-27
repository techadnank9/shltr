"""Browser sandbox task runner (Pattern B). Reads /in/task.json, writes /out/report.json and /out/shots/.

Modes
  inspect  open a suspicious link and record what it tries: every request (and which failed or were
           blocked), forced downloads (kept here, reported by name, size and sha256, destroyed with the
           microVM), forms, and a screenshot.
  fill     open the aid portal and run the planned steps (fill / select / check / upload / click),
           screenshot after each step, and stop before the final submit. Saves the browser state.
  submit   after the survivor approves: restore the saved state, click submit, screenshot the receipt.

task.json
  {"mode": "inspect", "url": "http://disaster-relief-claims.help/",
   "host_map": {"disaster-relief-claims.help": "10.40.0.3:8080"}}
  {"mode": "fill", "url": "...", "host_map": {...},
   "steps": [{"title": "Applicant", "actions": [{"fill": "#name", "value": "..."}, {"click": "#next"}]}],
   "stop_before": "#submit"}
  {"mode": "submit", "url": "...", "host_map": {...}, "click": "#submit"}   (state from /in/state.json)

host_map points a lookalike domain at our own demo server, so the address bar shows the realistic name
while the page comes from inside the private network. The microVM's allowlist blocks everything else.
"""
import hashlib
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

IN, OUT = Path("/in"), Path("/out")
SHOTS = OUT / "shots"
QUARANTINE = Path("/tmp/quarantine")

FORMS_JS = """
() => [...document.querySelectorAll('input, select, textarea, button')].slice(0, 60).map(el => ({
  tag: el.tagName.toLowerCase(), type: el.type || '', id: el.id || '', name: el.name || '',
  label: (el.labels && el.labels[0] ? el.labels[0].innerText : el.getAttribute('aria-label') || el.placeholder || el.innerText || '').trim().slice(0, 80),
  action: el.form ? el.form.getAttribute('action') || '' : ''
}))
"""


def log(msg: str) -> None:
    print(f"[browser] {msg}", flush=True)


def launch(pw, task: dict):
    rules = ", ".join(f"MAP {host} {target}" for host, target in task.get("host_map", {}).items())
    args = [f"--host-resolver-rules={rules}"] if rules else []
    browser = pw.chromium.launch(args=args)
    state = IN / "state.json"
    context = browser.new_context(
        viewport={"width": 1280, "height": 900}, accept_downloads=True,
        storage_state=str(state) if task["mode"] == "submit" and state.exists() else None,
    )
    return browser, context


def watch(page, report: dict) -> None:
    def on_request(req):
        report["requests"].append({"url": req.url[:300], "method": req.method, "type": req.resource_type})

    def on_failed(req):
        report["blocked"].append({"url": req.url[:300], "method": req.method, "error": (req.failure or "")[:120],
                                  "post_data": (req.post_data or "")[:300]})

    def on_download(dl):
        QUARANTINE.mkdir(parents=True, exist_ok=True)
        target = QUARANTINE / Path(dl.suggested_filename).name
        try:
            dl.save_as(target)
            data = target.read_bytes()
            report["downloads"].append({"name": target.name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                                        "kept": "inside the sandbox only; destroyed with it"})
        except Exception as err:  # noqa: BLE001 - a failed download is still a finding
            report["downloads"].append({"name": target.name, "error": str(err)[:200]})
        log(f"download attempt captured: {target.name}")

    page.on("request", on_request)
    page.on("requestfailed", on_failed)
    page.on("download", on_download)


def shot(page, n: int, name: str) -> str:
    SHOTS.mkdir(parents=True, exist_ok=True)
    path = SHOTS / f"{n:02d}-{name}.png"
    page.screenshot(path=str(path), full_page=False)
    return f"shots/{path.name}"


def inspect(page, task: dict, report: dict) -> None:
    log(f"opening {task['url']}")
    resp = page.goto(task["url"], wait_until="load", timeout=30000)
    report["status"] = resp.status if resp else None
    page.wait_for_timeout(3500)  # let background scripts try their tricks
    report["final_url"] = page.url
    report["title"] = page.title()[:200]
    report["visible_text"] = page.inner_text("body")[:4000]
    report["forms"] = page.evaluate(FORMS_JS)
    report["screenshots"].append({"title": "Page as the survivor would see it", "file": shot(page, 1, "page")})
    log(f"{len(report['requests'])} requests, {len(report['blocked'])} blocked, "
        f"{len(report['downloads'])} downloads")


FRAME = {"n": 0}


def frame(page, title: str) -> str:
    """Live view: a screenshot after every action plus a progress line. The runner watches
    /out while the browser runs and streams each new frame to the survivor's screen."""
    FRAME["n"] += 1
    n = FRAME["n"]
    file = shot(page, n, "frame")
    with (OUT / "progress.jsonl").open("a") as fh:
        fh.write(json.dumps({"n": n, "title": title, "file": file, "url": page.url}) + "\n")
    return file


def describe(action: dict) -> str:
    for key, verb in (("fill", "Typing"), ("select", "Choosing"), ("upload", "Attaching"), ("click", "Clicking"), ("check", "Ticking")):
        if key in action:
            what = action.get("label") or action[key]
            return f"{verb} {what}" + (f": {action['value']}" if key in ("fill", "select") and action.get("value") else "")
    return "Working"


def run_action(page, action: dict) -> None:
    if "ensure" in action:  # add a table row if it isn't there yet
        if page.locator(action["ensure"]).count() == 0:
            page.click(action["add"], timeout=8000)
        return
    if "fill" in action:
        page.fill(action["fill"], str(action.get("value", "")), timeout=8000)
    elif "select" in action:
        page.select_option(action["select"], str(action.get("value", "")), timeout=8000)
    elif "check" in action:
        page.check(action["check"], timeout=8000)
    elif "upload" in action:
        files = action["file"] if isinstance(action["file"], list) else [action["file"]]
        page.set_input_files(action["upload"], [str(IN / Path(f).name) for f in files if (IN / Path(f).name).exists()], timeout=8000)
    elif "click" in action:
        page.click(action["click"], timeout=8000)
        page.wait_for_load_state("load")
    else:
        raise ValueError(f"unknown action {action}")


def run_steps(page, task: dict, report: dict, stop: str | None) -> None:
    page.goto(task["url"], wait_until="load", timeout=30000)
    frame(page, "Opened the aid portal")
    pace = int(task.get("pace_ms", 400))  # human pace, so the live view is watchable
    for n, step in enumerate(task["steps"], 1):
        captured = False
        for action in step["actions"]:
            if "click" in action and not captured:
                # The step's evidence shot is taken before it is left (its Continue / Submit click).
                report["screenshots"].append({"title": step.get("title", f"Step {n}"), "file": shot(page, 50 + n, "step"),
                                              "url": page.url, "heading": page.inner_text("body")[:300]})
                captured = True
            if stop and action.get("click") == stop:
                break
            run_action(page, action)
            if "ensure" not in action:
                page.wait_for_timeout(pace)
                frame(page, f"Step {n} · {describe(action)}")
        if not captured:
            report["screenshots"].append({"title": step.get("title", f"Step {n}"), "file": shot(page, 50 + n, "step"),
                                          "url": page.url, "heading": page.inner_text("body")[:300]})
        log(f"step {n} done: {step.get('title', '')}")


def fill(page, task: dict, report: dict) -> None:
    stop = task.get("stop_before")
    run_steps(page, task, report, stop)
    report["paused_before"] = stop
    report["final_url"] = page.url
    frame(page, "Paused before Submit · waiting for your approval")


def submit(page, task: dict, report: dict) -> None:
    """After approval: replay the same steps in a fresh microVM (the portal keeps no state), then submit."""
    run_steps(page, task, report, None)
    report["final_url"] = page.url
    report["visible_text"] = page.inner_text("body")[:2000]
    receipt = page.locator("#receipt-number")
    report["receipt_id"] = receipt.inner_text().strip() if receipt.count() else ""
    report["screenshots"].append({"title": "Receipt", "file": shot(page, 90, "receipt")})
    frame(page, f"Submitted · receipt {report['receipt_id']}")
    log(f"submitted, receipt {report['receipt_id']}")


def main() -> None:
    task = json.loads((IN / "task.json").read_text())
    report = {"mode": task["mode"], "url": task.get("url"), "requests": [], "blocked": [], "downloads": [],
              "screenshots": [], "started": time.time()}
    with sync_playwright() as pw:
        browser, context = launch(pw, task)
        page = context.new_page()
        watch(page, report)
        try:
            {"inspect": inspect, "fill": fill, "submit": submit}[task["mode"]](page, task, report)
        except Exception as err:  # noqa: BLE001 - report what happened, then fail
            report["error"] = f"{type(err).__name__}: {err}"[:500]
            try:
                report["screenshots"].append({"title": "Where it stopped", "file": shot(page, 99, "error")})
            except Exception:  # noqa: BLE001
                pass
        finally:
            report["seconds"] = round(time.time() - report.pop("started"), 1)
            (OUT / "report.json").write_text(json.dumps(report, indent=2))
            browser.close()
    sys.exit(1 if "error" in report else 0)


if __name__ == "__main__":
    main()
