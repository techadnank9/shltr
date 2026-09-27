"""Download a dataset listed in a manifest.json (standard library only).

Usage, from the repo root:
    python datasets/fetch.py                                   # FEMA interiors -> test-photos/fema/
    python datasets/fetch.py datasets/fema-interiors/manifest.json test-photos/fema

Each image is downloaded from its `download_url` (a 1920 px Wikimedia Commons
thumbnail, to keep downloads small) and saved as `<name>.jpg`. The script checks
that the file is a JPEG of the expected width and height, and skips files that
are already present and correct. `original_url` in the manifest is the full-size file.
"""
import json
import struct
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
USER_AGENT = "ShltrDatasetFetch/0.1 (https://github.com/techadnank9/shltr; hackathon test dataset)"


def jpeg_size(data: bytes):
    """Return (width, height) from a JPEG's SOF marker, or None."""
    if data[:2] != b"\xff\xd8":
        return None
    i = 2
    while i + 9 < len(data):
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        (length,) = struct.unpack(">H", data[i + 2:i + 4])
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            h, w = struct.unpack(">HH", data[i + 5:i + 9])
            return w, h
        i += 2 + length
    return None


def fetch(url: str) -> bytes:
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except Exception as e:  # network hiccup or 429: back off and retry
            if attempt == 2:
                raise
            print(f"  retry after error: {e}")
            time.sleep(3 * (attempt + 1))
    raise RuntimeError("unreachable")


def main() -> int:
    manifest = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "datasets/fema-interiors/manifest.json"
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "test-photos/fema"
    out_dir.mkdir(parents=True, exist_ok=True)
    images = json.loads(manifest.read_text(encoding="utf-8"))["images"]
    bad = 0
    for img in images:
        dest = out_dir / f"{img['name']}.jpg"
        want = (img["download_width"], img["download_height"])
        if dest.exists() and jpeg_size(dest.read_bytes()) == want:
            print(f"ok    {dest.name} (already here)")
            continue
        data = fetch(img["download_url"])
        got = jpeg_size(data)
        if got != want:
            print(f"FAIL  {dest.name}: expected {want}, got {got}")
            bad += 1
            continue
        dest.write_bytes(data)
        print(f"ok    {dest.name} {got[0]}x{got[1]} {len(data) // 1024} KB  ({img['license']}, {img['author'][:40]})")
        time.sleep(1)  # be polite to Commons
    print(f"{len(images) - bad}/{len(images)} images in {out_dir}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
