"""Download the drone flyover set (FloodNet, Hurricane Harvey) listed in manifest.json.

Standard library only. From the repo root:
    python datasets/drone/fetch.py
    -> test-photos/drone/harvey-fort-bend-tx/floodnet-<n>.jpg  (16 images, 1600x1070, about 7 MB total)

Each image is fetched from its `download_url` (a 1600 px Google Drive thumbnail of the
public FloodNet folder; no account needed). `original_url` is the full 4592x3072 file
(about 8 MB each). The download, size check and skip-if-present logic are shared with
the FEMA set in datasets/fetch.py.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import fetch as shared  # datasets/fetch.py  # noqa: E402

if __name__ == "__main__":
    import json

    area = json.loads((HERE / "manifest.json").read_text(encoding="utf-8"))["name"]
    sys.argv = [sys.argv[0], str(HERE / "manifest.json"), str(HERE.parent.parent / "test-photos" / "drone" / area)]
    sys.exit(shared.main())
