"""Phone model names for mobile visitors.

1. Google's official "Play supported devices" list (app/test_data/devices.json, built by tools/build_devices.py)
   maps model codes such as SM-S918B to "Samsung Galaxy S23 Ultra".
2. iPhones: iOS does not reveal the exact model, so only "Apple iPhone" can be said.
3. Only if the code is not in Google's list AND the visitor opted in to AI, the AI is asked for an estimate,
   which is always labelled as such.
"""

import logging
import re
from functools import lru_cache

from . import llm
from .catalog import load

log = logging.getLogger(__name__)


@lru_cache
def _models() -> dict[str, str]:
    try:
        return load("devices.json")["models"]
    except FileNotFoundError:
        return {}


def is_mobile(p: dict) -> bool:
    factors = [str(f).lower() for f in (p.get("ch_form_factors") or [])]
    return bool({"mobile", "tablet"} & set(factors)) or p.get("ua_device_kind") in ("mobile", "tablet") \
        or p.get("is_mobile_hint") is True


def identify(p: dict) -> dict | None:
    """Return {"code", "name", "how"} for mobile visitors, or None for desktops."""
    if not p or not is_mobile(p):
        return None
    code = (p.get("ch_model") or p.get("ua_device_model") or "").strip()
    if code.lower() in ("", "k", "other", "generic smartphone"):
        code = ""
    if code and (name := _models().get(code.upper())):
        return {"code": code, "name": name, "how": "Google Play device list"}
    if (p.get("ua_os") == "iOS") or "iphone" in str(p.get("ua_device_family", "")).lower():
        return {"code": None, "name": "Apple iPhone", "how": "iOS does not reveal the exact model"}
    if code:
        return {"code": code, "name": None, "how": None}
    return {"code": None, "name": None, "how": None}


PROMPT = ("You identify mobile phones. Given an Android model code (and maybe a brand), reply with the phone's "
          "commercial name only, for example 'Samsung Galaxy S23 Ultra'. If you are not sure, reply exactly UNKNOWN.")


async def ai_estimate(code: str, brand: str | None) -> str | None:
    out = await llm.chat(PROMPT, f"Model code: {code}" + (f"\nBrand: {brand}" if brand else ""), max_tokens=30,
                         temperature=0.0)
    if not out:
        return None
    name = out.strip().strip('".').splitlines()[0]
    if "unknown" in name.lower() or not 2 <= len(name.split()) <= 6 or not re.search(r"[A-Za-z]", name):
        return None
    return name


async def describe(p: dict, use_ai: bool) -> dict | None:
    info = identify(p)
    if info and not info["name"] and info["code"] and use_ai and llm.enabled():
        guess = await ai_estimate(info["code"], p.get("ua_device_brand"))
        if guess:
            info.update(name=guess, how="AI estimate (not in Google's device list)")
    return info
