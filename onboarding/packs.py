"""Read distributor pack strings ("4/10 LB", "6/32 OZ", "1/200 CT") into catalog base units."""

from __future__ import annotations

import re
from dataclasses import dataclass

PACK_RE = re.compile(r"^\s*(?:(\d+)\s*/\s*)?(\d+(?:\.\d+)?)\s*(LB|OZ|GAL|QT|CT|EA|BU|DZ)\s*$", re.IGNORECASE)

UNIT_FAMILY = {"LB": "weight", "OZ": "weight", "GAL": "volume", "QT": "volume", "CT": "count", "EA": "count", "BU": "count", "DZ": "count"}


@dataclass(frozen=True)
class Pack:
    cases_inner: int  # units per case, e.g. 4 in "4/10 LB"
    size: float  # size of each unit, e.g. 10 in "4/10 LB"
    unit: str  # LB, OZ, GAL, QT, CT, EA, BU, DZ

    @property
    def family(self) -> str:
        return UNIT_FAMILY[self.unit]


def parse_pack(text: str) -> Pack | None:
    m = PACK_RE.match(text or "")
    if not m:
        return None
    inner = int(m.group(1)) if m.group(1) else 1
    return Pack(inner, float(m.group(2)), m.group(3).upper())


def base_per_case(pack: Pack, family: str, base_unit: str, conversion: float | None = None) -> float | None:
    """Catalog base units in one case, or None when the pack cannot be expressed in the catalog's unit.

    `conversion` is a person-entered factor (base units per case) for packs sold in a different family,
    such as limes sold by count for a catalog that tracks limes by weight.
    """
    if conversion:
        return conversion
    total = pack.cases_inner * pack.size
    if family == "weight":
        if pack.unit == "LB":
            return total
        if pack.unit == "OZ":
            return total / 16
        return None
    if family == "volume":
        if pack.unit == "GAL":
            return total * 4
        if pack.unit == "QT":
            return total
        if pack.unit == "OZ":  # fluid ounces on liquid items
            return total / 32
        return None
    if family == "count":
        if pack.unit in ("CT", "EA", "BU"):
            return total
        if pack.unit == "DZ":
            return total * 12
        return None
    return None
