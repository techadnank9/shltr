"""Shared helpers for the infra scripts: load .env and make JSON HTTP calls.

Standard library only, so the checks run on any machine with Python 3.10+.
Keys are read from the repo-root .env and are never printed.
"""
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_env() -> dict:
    env = {}
    path = REPO_ROOT / ".env"
    if not path.exists():
        sys.exit(f"Missing {path}. Copy .env.example to .env and fill in your keys.")
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    # Real environment variables win over the file, so VM 1 can use either.
    for key in list(env):
        env[key] = os.environ.get(key, env[key])
    return env


def require(env: dict, key: str) -> str:
    value = env.get(key, "")
    if not value:
        sys.exit(f"{key} is empty in .env. Add it and run again.")
    return value


def http_json(method: str, url: str, token: str, body: dict | None = None, timeout: int = 90) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/json")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as err:
        detail = err.read().decode(errors="replace")[:400]
        hint = ""
        if "Unauthorized IP address" in detail:
            hint = ("\nFix: in the Vultr dashboard go to Account > API > Access Control and add the IP "
                    "shown above (or /32 of it), then run again.")
        elif err.code == 401:
            hint = "\nFix: the key in .env is wrong or expired. Copy it again from the Vultr dashboard."
        sys.exit(f"{method} {url} failed with HTTP {err.code}: {detail}{hint}")
