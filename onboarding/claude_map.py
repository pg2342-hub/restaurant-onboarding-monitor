"""Claude step of the mapper: suggest a catalog item for vendor items the rules could not read.

Live mode (MAPPER_LIVE=1 and ANTHROPIC_API_KEY set) calls the API and appends every reply to
recordings/mapping.jsonl. Every other run replays that file, so tests and the demo never need a key.
Replies are keyed by a hash of the request, so a changed catalog or prompt needs a fresh recording.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

MODEL = "claude-opus-5-5"
ROOT = Path(__file__).resolve().parent.parent
RECORDING = ROOT / "recordings" / "mapping.jsonl"

SYSTEM = (
    "You map lines from a food distributor's order guide to a restaurant group's inventory catalog. "
    "Distributor descriptions use abbreviations, brand names and Spanish names. "
    "Pick the one catalog item that is the same product. If the product is not in the catalog, "
    "or is a different cut, variety or form from every catalog item (for example breast when the catalog has thigh), "
    "answer NOT_IN_CATALOG. A wrong match corrupts food cost and ordering for every location, "
    "so use high confidence only when the description clearly names the catalog product."
)


class Suggestion(BaseModel):
    item_id: str = Field(description="A catalog item_id from the list, or NOT_IN_CATALOG")
    confidence: Literal["high", "medium", "low"]
    reason: str = Field(description="One short sentence on what in the description decided it")


def _catalog_block(catalog: list[dict]) -> str:
    return "\n".join(f"{c['item_id']}: {c['name']} (tracked by {c['base_unit']})" for c in catalog)


def request_for(vendor_row: dict, catalog: list[dict]) -> dict:
    user = (
        f"Catalog:\n{_catalog_block(catalog)}\n\n"
        f"Order guide line\nvendor: {vendor_row['vendor']}\ncode: {vendor_row['vendor_code']}\n"
        f"description: {vendor_row['description']}\npack: {vendor_row['pack']}\n\n"
        "Which catalog item is this?"
    )
    return {"model": MODEL, "system": SYSTEM, "user": user}


def key_for(request: dict) -> str:
    return hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()[:16]


def load_recording(path: Path = RECORDING) -> dict[str, dict]:
    if not path.exists():
        return {}
    out = {}
    for line in path.read_text().splitlines():
        if line.strip():
            rec = json.loads(line)
            out[rec["key"]] = rec
    return out


def live_enabled() -> bool:
    return os.environ.get("MAPPER_LIVE") == "1" and bool(os.environ.get("ANTHROPIC_API_KEY"))


def _call_live(request: dict) -> dict:
    import anthropic  # imported lazily so replay runs need no SDK setup

    client = anthropic.Anthropic()
    started = time.time()
    response = client.messages.parse(
        model=request["model"],
        max_tokens=4000,
        system=request["system"],
        output_config={"effort": "low"},
        messages=[{"role": "user", "content": request["user"]}],
        output_format=Suggestion,
    )
    latency = round(time.time() - started, 2)
    usage = response.usage
    if response.stop_reason == "refusal" or response.parsed_output is None:
        parsed = {"item_id": "NOT_IN_CATALOG", "confidence": "low", "reason": f"no usable answer ({response.stop_reason})"}
    else:
        parsed = response.parsed_output.model_dump()
    # Opus 5.5 list price: $4 per million input tokens, $20 per million output tokens
    cost = (usage.input_tokens * 4 + usage.output_tokens * 20) / 1_000_000
    return {
        "suggestion": parsed,
        "latency_s": latency,
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "cost_usd": round(cost, 5),
    }


def suggest(vendor_row: dict, catalog: list[dict], recording: dict[str, dict]) -> dict | None:
    """Return the recorded (or, in live mode, fresh) reply for this line, or None if neither exists."""
    request = request_for(vendor_row, catalog)
    key = key_for(request)
    if key in recording:
        return recording[key]
    if not live_enabled():
        return None
    reply = _call_live(request)
    rec = {"key": key, "vendor_code": vendor_row["vendor_code"], "description": vendor_row["description"], **reply}
    RECORDING.parent.mkdir(exist_ok=True)
    with RECORDING.open("a") as f:
        f.write(json.dumps(rec) + "\n")
    recording[key] = rec
    return rec
