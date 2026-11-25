"""Go-live readiness: the checks that decide whether a location's numbers can be trusted on day one.

A location is NO-GO with any blocking finding, GO WITH FIXES with only warnings, and GO otherwise.
Group-level findings (order guide problems) are reported once, not per location.
"""

from __future__ import annotations

import statistics
from dataclasses import asdict, dataclass

from .mapper import Mapping, map_order_guide
from .packs import base_per_case, parse_pack

# check id: (plain name, owner, what the owner does)
CHECKS = {
    "pos_connected": ("POS connected", "POS admin (group)", "Connect the location's POS so sales arrive"),
    "menu_item_costed": ("Every item sold has a recipe", "Culinary lead", "Write the recipe so sales turn into ingredient use"),
    "recipe_items_in_catalog": ("Recipes use catalog items", "Culinary lead", "Add the ingredient to the catalog or fix the recipe"),
    "invoice_codes_mapped": ("Every invoice line maps to a catalog item", "Onboarding lead", "Decide the line: map it, add the item, or stop ordering it"),
    "pack_in_catalog_units": ("Packs convert to catalog units", "Onboarding lead", "Enter how many catalog units are in one case"),
    "invoice_pack_matches": (
        "Invoice packs match the order guide",
        "Onboarding lead with the vendor rep",
        "Confirm the real pack and fix the order guide or the invoice",
    ),
    "par_levels_set": ("Par levels set", "General manager", "Set a par for each item the kitchen orders"),
    "price_in_line": ("Prices in line with the group", "Owner or purchasing", "Ask the vendor about the price or accept it"),
    "opening_count": ("Opening count done", "General manager", "Do one full count so usage has a starting point"),
    "no_duplicate_codes": ("Each vendor code listed once", "Onboarding lead", "Keep the right pack and delete the other line"),
}

NO_RECIPE_BLOCK_SHARE = 0.02  # an item without a recipe blocks go-live once it is 2% or more of units sold
PRICE_OUTLIER = 0.25  # unit price this far over the group median is flagged


@dataclass
class Finding:
    check: str
    severity: str  # blocking | warning
    location: str  # L01.. or "group"
    detail: str

    @property
    def owner(self) -> str:
        return CHECKS[self.check][1]


def verdict(findings: list[Finding]) -> str:
    if any(f.severity == "blocking" for f in findings):
        return "NO-GO"
    if findings:
        return "GO WITH FIXES"
    return "GO"


def run(ds: dict, use_claude: bool = True, recording: dict | None = None) -> dict:
    catalog = ds["catalog"]
    by_id = {c["item_id"]: c for c in catalog}
    maps = map_order_guide(ds["order_guide"], catalog, ds.get("decisions", {}), ds.get("conversions", {}), use_claude, recording)
    by_code: dict[str, Mapping] = {}
    for m in maps:
        by_code.setdefault(m.vendor_code, m)
    recipes: dict[str, dict[str, float]] = {}
    for r in ds["recipes"]:
        recipes.setdefault(r["menu_item"], {})[r["item_id"]] = float(r["qty_base"])
    findings: list[Finding] = []

    # group level: duplicate codes
    for m in maps:
        for issue in m.issues:
            if "listed twice" in issue:
                findings.append(Finding("no_duplicate_codes", "warning", "group", issue))

    # unit prices per catalog item across the group, for the outlier check
    unit_prices: dict[str, list[tuple[str, float]]] = {}
    for inv in ds["invoices"]:
        m = by_code.get(inv["vendor_code"])
        if m and m.item_id and m.base_per_case and inv["pack"] == m.pack:
            unit_prices.setdefault(m.item_id, []).append((inv["location_id"], float(inv["case_price"]) / m.base_per_case))

    for loc_row in ds["locations"]:
        loc = loc_row["location_id"]
        sales = [r for r in ds["pos_sales"] if r["location_id"] == loc]
        if not sales:
            findings.append(Finding("pos_connected", "blocking", loc, "No sales rows from the POS for this location"))
        sold: dict[str, int] = {}
        for r in sales:
            sold[r["menu_item"]] = sold.get(r["menu_item"], 0) + int(r["qty"])
        total = sum(sold.values()) or 1
        used_items: set[str] = set()
        for item, qty in sorted(sold.items()):
            if item not in recipes:
                share = qty / total
                sev = "blocking" if share >= NO_RECIPE_BLOCK_SHARE else "warning"
                findings.append(Finding("menu_item_costed", sev, loc, f"{item}: {qty} sold ({share:.0%} of units) with no recipe"))
                continue
            for ing in recipes[item]:
                if ing not in by_id:
                    findings.append(Finding("recipe_items_in_catalog", "blocking", loc, f"{item} uses '{ing}', which is not in the catalog"))
                else:
                    used_items.add(ing)

        invoices = [r for r in ds["invoices"] if r["location_id"] == loc]
        for inv in invoices:
            code = inv["vendor_code"]
            m = by_code.get(code)
            label = f"{inv['vendor']} {code} {inv['description']}"
            if m is None:
                findings.append(Finding("invoice_codes_mapped", "blocking", loc, f"{label}: not in any order guide"))
                continue
            if m.stage == "review":
                findings.append(Finding("invoice_codes_mapped", "blocking", loc, f"{label}: waiting in the review queue ({'; '.join(m.issues) or 'no match'})"))
                continue
            if m.stage == "not_stocked":
                findings.append(Finding("invoice_codes_mapped", "warning", loc, f"{label}: the group does not stock this item; stop ordering it"))
                continue
            if m.base_per_case is None:
                findings.append(Finding("pack_in_catalog_units", "blocking", loc, f"{label}: {'; '.join(i for i in m.issues if 'listed twice' not in i)}"))
            if inv["pack"] != m.pack:
                pack = parse_pack(inv["pack"])
                cat = by_id[m.item_id]
                inv_base = base_per_case(pack, cat["family"], cat["base_unit"]) if pack else None
                guide_base = m.base_per_case
                findings.append(
                    Finding(
                        "invoice_pack_matches",
                        "blocking",
                        loc,
                        f"{label}: invoice says '{inv['pack']}' ({_fmt(inv_base)} {cat['base_unit']} a case), "
                        f"order guide says '{m.pack}' ({_fmt(guide_base)} {cat['base_unit']} a case)",
                    )
                )

        pars = {r["item_id"] for r in ds["par_levels"] if r["location_id"] == loc}
        needed = sorted(used_items)
        missing = [i for i in needed if i not in pars]
        if needed and len(missing) == len(needed):
            findings.append(Finding("par_levels_set", "blocking", loc, f"No par levels set ({len(needed)} items used in recipes)"))
        elif missing:
            names = ", ".join(by_id[i]["name"] for i in missing)
            findings.append(
                Finding(
                    "par_levels_set",
                    "warning",
                    loc,
                    f"{len(missing)} item{'s' if len(missing) != 1 else ''} used in recipes {'have' if len(missing) != 1 else 'has'} no par: {names}",
                )
            )

        if not any(r["location_id"] == loc for r in ds["counts"]):
            findings.append(Finding("opening_count", "blocking", loc, "No opening count on file"))

        for item_id, prices in unit_prices.items():
            mine = [p for lo, p in prices if lo == loc]
            others = [p for lo, p in prices if lo != loc]
            if not mine or len(others) < 3:
                continue
            med = statistics.median(others)
            if max(mine) > med * (1 + PRICE_OUTLIER):
                findings.append(
                    Finding(
                        "price_in_line",
                        "warning",
                        loc,
                        f"{by_id[item_id]['name']}: ${max(mine):.2f} per {by_id[item_id]['base_unit']} vs group median ${med:.2f} ({max(mine) / med - 1:+.0%})",
                    )
                )

    locations = []
    for loc_row in ds["locations"]:
        loc = loc_row["location_id"]
        mine = [f for f in findings if f.location == loc]
        locations.append(
            {
                "location_id": loc,
                "name": loc_row["name"],
                "pilot_wave": int(loc_row["pilot_wave"]),
                "verdict": verdict(mine),
                "blocking": sum(f.severity == "blocking" for f in mine),
                "warnings": sum(f.severity == "warning" for f in mine),
                "findings": [asdict(f) | {"owner": f.owner, "check_name": CHECKS[f.check][0]} for f in mine],
            }
        )
    fixes_by_owner: dict[str, list[dict]] = {}
    for f in findings:
        fixes_by_owner.setdefault(f.owner, []).append(asdict(f) | {"action": CHECKS[f.check][2]})
    return {
        "mappings": [_mapping_dict(m) for m in maps],
        "findings": findings,
        "locations": locations,
        "group_findings": [asdict(f) | {"owner": f.owner} for f in findings if f.location == "group"],
        "fixes_by_owner": fixes_by_owner,
    }


def _fmt(x: float | None) -> str:
    return "?" if x is None else (f"{x:g}")


def _mapping_dict(m: Mapping) -> dict:
    return {
        "vendor": m.vendor,
        "vendor_code": m.vendor_code,
        "description": m.description,
        "pack": m.pack,
        "item_id": m.item_id,
        "stage": m.stage,
        "base_per_case": m.base_per_case,
        "issues": m.issues,
        "claude": m.claude,
    }
