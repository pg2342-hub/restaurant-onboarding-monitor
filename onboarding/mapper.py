"""Map every order guide line to one catalog item.

Three stages, in order:
1. A person's decision from mapping_decisions.csv, if one exists for the line (always wins).
2. Rules: expand distributor abbreviations; map only when every word of exactly one catalog name appears.
3. Claude: suggest an item for what the rules could not read. Code decides what is accepted:
   the item must exist in the catalog, the pack must be expressible in the catalog's unit (or a person
   has entered a conversion), and the confidence must be high. Anything else goes to the review queue.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import claude_map
from .packs import base_per_case, parse_pack

ABBREVIATIONS = {
    "bnls": "boneless",
    "skls": "skinless",
    "chkn": "chicken",
    "brst": "breast",
    "grnd": "ground",
    "frsh": "fresh",
    "grn": "green",
    "drd": "dried",
    "whl": "whole",
    "shrd": "shredded",
    "sheets": "sheets",
}
STOP = {"x", "oz", "lb", "ct", "the", "and", "of"}


def tokens(text: str) -> list[str]:
    raw = re.findall(r"[a-z0-9]+", text.lower())
    return [ABBREVIATIONS.get(t, t) for t in raw]


def _name_tokens(name: str) -> set[str]:
    return {t for t in tokens(name) if t not in STOP}


def rule_match(description: str, catalog: list[dict]) -> str | None:
    desc = set(tokens(description))
    hits = []
    for c in catalog:
        need = _name_tokens(c["name"])
        if need and need <= desc:
            hits.append((len(need), c["item_id"]))
    if not hits:
        return None
    hits.sort(reverse=True)
    if len(hits) > 1 and hits[0][0] == hits[1][0]:
        return None  # two catalog names fit equally well: let a person or Claude decide
    return hits[0][1]


@dataclass
class Mapping:
    vendor: str
    vendor_code: str
    description: str
    pack: str
    case_price: float
    item_id: str | None = None  # None = not mapped (review queue or not stocked)
    stage: str = ""  # decision | rules | claude | review | not_stocked
    base_per_case: float | None = None
    issues: list[str] = field(default_factory=list)
    claude: dict | None = None

    @property
    def unit_price(self) -> float | None:
        if self.base_per_case:
            return self.case_price / self.base_per_case
        return None


def _pack_check(m: Mapping, cat_row: dict, conversions: dict[str, float]) -> None:
    pack = parse_pack(m.pack)
    if pack is None:
        m.issues.append(f"pack '{m.pack}' cannot be read")
        return
    per_case = base_per_case(pack, cat_row["family"], cat_row["base_unit"], conversions.get(m.vendor_code))
    if per_case is None:
        m.issues.append(f"pack '{m.pack}' is sold by {pack.family} but the catalog tracks {cat_row['name']} by {cat_row['base_unit']}; needs a conversion")
        return
    m.base_per_case = per_case


def map_order_guide(
    order_guide: list[dict],
    catalog: list[dict],
    decisions: dict[str, str] | None = None,
    conversions: dict[str, float] | None = None,
    use_claude: bool = True,
    recording: dict | None = None,
) -> list[Mapping]:
    decisions = decisions or {}
    conversions = conversions or {}
    by_id = {c["item_id"]: c for c in catalog}
    recording = claude_map.load_recording() if recording is None else recording
    out: list[Mapping] = []
    for row in order_guide:
        m = Mapping(row["vendor"], row["vendor_code"], row["description"], row["pack"], float(row["case_price"]))
        if m.vendor_code in decisions:
            decided = decisions[m.vendor_code]
            if decided:
                m.item_id, m.stage = decided, "decision"
            else:
                m.stage = "not_stocked"
        else:
            hit = rule_match(m.description, catalog)
            if hit:
                m.item_id, m.stage = hit, "rules"
            elif use_claude:
                reply = claude_map.suggest(row, catalog, recording)
                if reply is None:
                    m.stage = "review"
                    m.issues.append("no Claude suggestion recorded yet")
                else:
                    m.claude = reply
                    s = reply["suggestion"]
                    if s["item_id"] == "NOT_IN_CATALOG":
                        m.stage = "review"
                        m.issues.append("Claude: not in the catalog; add it or stop ordering it")
                    elif s["item_id"] not in by_id:
                        m.stage = "review"
                        m.issues.append(f"Claude named '{s['item_id']}', which is not a catalog item")
                    elif s["confidence"] != "high":
                        m.stage = "review"
                        m.issues.append(f"Claude suggests {s['item_id']} with {s['confidence']} confidence; confirm")
                    else:
                        m.item_id, m.stage = s["item_id"], "claude"
            else:
                m.stage = "review"
        if m.item_id:
            _pack_check(m, by_id[m.item_id], conversions)
        out.append(m)
    _flag_duplicates(out)
    return out


def _flag_duplicates(maps: list[Mapping]) -> None:
    seen: dict[str, Mapping] = {}
    for m in maps:
        prev = seen.get(m.vendor_code)
        if prev and prev.pack != m.pack:
            m.issues.append(f"vendor code {m.vendor_code} is listed twice with different packs ('{prev.pack}' and '{m.pack}')")
        seen.setdefault(m.vendor_code, m)


def stage_counts(maps: list[Mapping]) -> dict[str, int]:
    counts = {"rules": 0, "claude": 0, "decision": 0, "review": 0, "not_stocked": 0}
    for m in maps:
        counts[m.stage] = counts.get(m.stage, 0) + 1
    return counts
