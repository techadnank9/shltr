"""Part 1: smoke tests T1-T3 against Vultr Serverless Inference.

T1  plain chat         the model answers
T2  image input        the model reads a picture (a generated test image, or --photo)
T3  tool calling       the model returns a structured tool call

    python infra/check_inference.py
    python infra/check_inference.py --photo test-photos/room.jpg
    python infra/check_inference.py --model qwen3.8-27b
"""
import argparse
import base64
import json
import struct
import sys
import time
import zlib
from pathlib import Path

from common import http_json, load_env, require


def test_png() -> bytes:
    """A 64x64 PNG: red top half, blue bottom half. Built with the standard library."""
    w, h = 64, 64
    rows = b"".join(
        b"\x00" + (b"\xe0\x30\x30" if y < h // 2 else b"\x20\x50\xd0") * w for y in range(h)
    )

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


def chat(base: str, key: str, model: str, messages: list, **extra) -> dict:
    body = {"model": model, "messages": messages, "max_tokens": 800, "temperature": 0, **extra}
    start = time.time()
    resp = http_json("POST", f"{base}/chat/completions", key, body)
    resp["_seconds"] = round(time.time() - start, 1)
    return resp


def text_of(resp: dict) -> str:
    msg = resp["choices"][0]["message"]
    return (msg.get("content") or "").strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", help="override VULTR_MODEL from .env")
    parser.add_argument("--photo", help="path to a real room photo for T2 (jpg or png)")
    args = parser.parse_args()

    env = load_env()
    key = require(env, "VULTR_INFERENCE_KEY")
    base = env.get("VULTR_INFERENCE_BASE_URL") or "https://api.vultrinference.com/v1"
    model = args.model or env.get("VULTR_MODEL") or "glm-5.3"
    print(f"Model {model} at {base}\n")
    results = {}

    # T1: plain chat
    try:
        r = chat(base, key, model, [{"role": "user", "content": "Reply with exactly: SHLTR ONLINE"}])
        answer = text_of(r)
        results["T1"] = "SHLTR ONLINE" in answer.upper()
        print(f"T1 chat        {'PASS' if results['T1'] else 'FAIL'}  ({r['_seconds']} s) -> {answer[:80]!r}")
    except Exception as err:  # noqa: BLE001 - report every failure and keep going
        results["T1"] = False
        print(f"T1 chat        FAIL  {err}")

    # T2: image input
    if args.photo:
        data = Path(args.photo).read_bytes()
        mime = "image/png" if args.photo.lower().endswith(".png") else "image/jpeg"
        question = "Describe this room in one sentence. Mention any visible damage."
        expect = None
    else:
        data, mime = test_png(), "image/png"
        question = "This image has two colored halves. Name the color of the top half and the bottom half, in that order."
        expect = ("red", "blue")
    image_url = f"data:{mime};base64,{base64.b64encode(data).decode()}"
    try:
        r = chat(base, key, model, [{
            "role": "user",
            "content": [
                {"type": "text", "text": question},
                {"type": "image_url", "image_url": {"url": image_url}},
            ],
        }])
        answer = text_of(r)
        low = answer.lower()
        results["T2"] = bool(answer) if expect is None else (expect[0] in low and expect[1] in low and low.index(expect[0]) < low.index(expect[1]))
        print(f"T2 image       {'PASS' if results['T2'] else 'FAIL'}  ({r['_seconds']} s) -> {answer[:120]!r}")
    except Exception as err:  # noqa: BLE001
        results["T2"] = False
        print(f"T2 image       FAIL  {err}")

    # T3: tool calling
    tools = [{
        "type": "function",
        "function": {
            "name": "estimate_drywall_cost",
            "description": "Estimate the cost to replace flood-damaged drywall.",
            "parameters": {
                "type": "object",
                "properties": {
                    "area_m2": {"type": "number", "description": "Damaged wall area in square metres"},
                    "price_per_m2_usd": {"type": "number", "description": "Replacement price per square metre"},
                },
                "required": ["area_m2", "price_per_m2_usd"],
            },
        },
    }]
    try:
        r = chat(base, key, model, [{
            "role": "user",
            "content": "Floodwater reached 0.91 m on a wall 6 m wide. Drywall costs $90 per square metre. Use the tool to estimate the cost.",
        }], tools=tools, tool_choice="auto")
        calls = r["choices"][0]["message"].get("tool_calls") or []
        ok = bool(calls) and calls[0]["function"]["name"] == "estimate_drywall_cost"
        shown = calls[0]["function"]["arguments"] if calls else text_of(r)[:80]
        if ok:
            json.loads(calls[0]["function"]["arguments"])  # arguments must be valid JSON
        results["T3"] = ok
        print(f"T3 tool call   {'PASS' if ok else 'FAIL'}  ({r['_seconds']} s) -> {shown}")
    except Exception as err:  # noqa: BLE001
        results["T3"] = False
        print(f"T3 tool call   FAIL  {err}")

    passed = sum(results.values())
    print(f"\n{passed}/3 passed")
    sys.exit(0 if passed == 3 else 1)


if __name__ == "__main__":
    main()
