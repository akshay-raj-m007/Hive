"""
Build app/test_data/devices.json: Android model code -> marketing name, from Google's official
"Google Play supported devices" list (https://support.google.com/googleplay/answer/1727131).

Run from backend/:   ../venv/Scripts/python tools/build_devices.py [--file=supported_devices.csv]
"""

import csv
import io
import json
import sys
from pathlib import Path

import httpx

URL = "https://storage.googleapis.com/play_public/supported_devices.csv"
OUT = Path(__file__).resolve().parents[1] / "app" / "test_data" / "devices.json"


def main() -> None:
    local = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--file=")), None)
    raw = Path(local).read_bytes() if local else httpx.get(URL, timeout=120, follow_redirects=True).content
    text = raw.decode("utf-16") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else raw.decode("utf-8", "replace")
    rows = csv.DictReader(io.StringIO(text))
    models: dict[str, str] = {}
    for r in rows:
        model = (r.get("Model") or "").strip()
        brand = (r.get("Retail Branding") or "").strip()
        name = (r.get("Marketing Name") or "").strip()
        if not model or not name:
            continue
        # "Galaxy S23 Ultra" -> "Samsung Galaxy S23 Ultra"; avoid "Google Google Pixel"
        full = name if not brand or name.lower().startswith(brand.lower()) else f"{brand} {name}"
        models.setdefault(model.upper(), full)
    OUT.write_text(json.dumps({"source": URL, "count": len(models), "models": models},
                              ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUT.name}: {len(models):,} models")


if __name__ == "__main__":
    main()
