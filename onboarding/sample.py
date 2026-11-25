"""Build the made-up group's data: a clean system, the first data pull, and two live weeks.

`clean()` is what the data looks like once onboarding is finished: every order guide line decided by a
person, every pack readable, every menu item costed. The first pull is the clean system with the
PROBLEMS below planted, and with no mapping decisions yet. The eval plants each problem alone into the
clean system and checks that it is caught.
"""

from __future__ import annotations

import copy
import csv
import math
import random
from datetime import date, timedelta
from pathlib import Path

from .data import BASE_DAILY, CATALOG, EXTRA_PAR_ITEMS, LOCATIONS, ORDER_GUIDE, PILOT_WAVE, RECIPES

HISTORY_START = date(2026, 10, 5)  # seven days of sales history in the first pull
HISTORY_DAYS = 7
LIVE_START = date(2026, 10, 19)  # two live weeks for the pilot wave
LIVE_DAYS = 14
COUNT_DAYS = (1, 4, 8, 11, 14)  # live count schedule, counted at close

# Menu items not sold everywhere
ONLY_AT = {"Nopal Taco": {"L03", "L07", "L09"}, "Shrimp Taco": {"L01", "L02", "L05", "L06"}}

# Base units per case for packs a person has converted (limes sold by count, catalog tracks pounds)
CLEAN_CONVERSIONS = {"RD-62041": 40.0}

TABLES = ["locations", "catalog", "order_guide", "pos_sales", "recipes", "par_levels", "invoices", "counts"]


def _catalog_rows():
    return [{"item_id": i, "name": n, "family": f, "base_unit": u, "category": c, "ref_cost": cost} for i, n, f, u, c, cost in CATALOG]


def _guide_rows():
    return [{"vendor": v, "vendor_code": code, "description": d, "pack": p, "case_price": price} for v, code, d, p, price, _truth in ORDER_GUIDE]


def truth_map() -> dict[str, str]:
    """vendor code -> catalog item ('' = not stocked). Used by the eval and to build the clean decisions."""
    return {code: truth for _v, code, _d, _p, _price, truth in ORDER_GUIDE}


def menu_at(loc: str) -> list[str]:
    return [m for m in BASE_DAILY if m not in ONLY_AT or loc in ONLY_AT[m]]


def source_code(item_id: str, loc: str) -> str:
    """Which order guide line a location buys an item from."""
    if loc in ("L09", "L10") and item_id == "lime":
        return "RD-62041"
    if loc in ("L09", "L10") and item_id == "avocado":
        return "RD-64480"
    preferred = [code for _v, code, _d, _p, _price, truth in ORDER_GUIDE if truth == item_id]
    return preferred[0]


def _base_per_case(code: str) -> float:
    from .packs import base_per_case, parse_pack

    row = next(r for r in ORDER_GUIDE if r[1] == code)
    cat = next(c for c in CATALOG if c[0] == row[5])
    return base_per_case(parse_pack(row[3]), cat[2], cat[3], CLEAN_CONVERSIONS.get(code))


def _daily_qty(rng: random.Random, loc_factor: float, item: str) -> int:
    return max(0, round(BASE_DAILY[item] * loc_factor * rng.uniform(0.85, 1.15)))


def _usage(sales: dict[str, float]) -> dict[str, float]:
    use: dict[str, float] = {}
    for menu_item, qty in sales.items():
        for item_id, per in RECIPES.get(menu_item, {}).items():
            use[item_id] = use.get(item_id, 0) + per * qty
    return use


def _items_used(loc: str) -> list[str]:
    items = set(EXTRA_PAR_ITEMS)
    for m in menu_at(loc):
        items |= set(RECIPES[m])
    return sorted(items)


def _avg_daily_use(loc: str, factor: float) -> dict[str, float]:
    sales = {m: BASE_DAILY[m] * factor for m in menu_at(loc)}
    use = _usage(sales)
    for extra in EXTRA_PAR_ITEMS:  # items with no recipe line still get used (salt, oil, beans, radish, cotija)
        use.setdefault(extra, {"salt": 1.5, "canola_oil": 2.0, "pinto_beans": 6.0, "radish": 2.0, "cotija": 1.2}.get(extra, 1.0) * factor)
    return use


def _person_decisions() -> dict[str, str]:
    """A person decides every order guide line the rules cannot map correctly by themselves."""
    from .mapper import rule_match

    cat = _catalog_rows()
    return {code: truth for _v, code, desc, _p, _price, truth in ORDER_GUIDE if rule_match(desc, cat) is None or rule_match(desc, cat) != truth}


def clean() -> dict:
    """The finished system: every table plus person decisions and conversions."""
    rng = random.Random(7)
    ds = {
        "locations": [{"location_id": loc, "name": name, "pilot_wave": PILOT_WAVE.get(loc, 2)} for loc, name, _f in LOCATIONS],
        "catalog": _catalog_rows(),
        "order_guide": _guide_rows(),
        "recipes": [{"menu_item": m, "item_id": i, "qty_base": q} for m, parts in RECIPES.items() for i, q in parts.items()],
        "pos_sales": [],
        "par_levels": [],
        "invoices": [],
        "counts": [],
        "decisions": _person_decisions(),
        "conversions": dict(CLEAN_CONVERSIONS),
    }
    for loc, _name, factor in LOCATIONS:
        for d in range(HISTORY_DAYS):
            day = (HISTORY_START + timedelta(days=d)).isoformat()
            for m in menu_at(loc):
                ds["pos_sales"].append({"location_id": loc, "date": day, "menu_item": m, "qty": _daily_qty(rng, factor, m)})
        daily = _avg_daily_use(loc, factor)
        for item in _items_used(loc):
            ds["par_levels"].append({"location_id": loc, "item_id": item, "par_base": round(daily[item] * 3, 2)})
            ds["counts"].append({"location_id": loc, "date": (HISTORY_START + timedelta(days=6)).isoformat(), "item_id": item, "qty_base": round(daily[item] * 1.8, 2)})
        inv_no = 1000 + int(loc[1:]) * 100
        for item in _items_used(loc):
            code = source_code(item, loc)
            row = next(r for r in ORDER_GUIDE if r[1] == code)
            cases = max(1, math.ceil(daily[item] * 7 / _base_per_case(code)))
            ds["invoices"].append(
                {
                    "location_id": loc,
                    "date": (HISTORY_START + timedelta(days=1)).isoformat(),
                    "vendor": row[0],
                    "invoice_no": f"{row[0][:2].upper()}-{inv_no}",
                    "vendor_code": code,
                    "description": row[2],
                    "pack": row[3],
                    "cases": cases,
                    "case_price": row[4],
                }
            )
    return ds


# ---------------------------------------------------------------- planted problems for the first pull


def _p_pos_missing(ds):
    ds["pos_sales"] = [r for r in ds["pos_sales"] if r["location_id"] != "L04"]


def _add_sales(ds, loc, item, per_day):
    for d in range(HISTORY_DAYS):
        day = (HISTORY_START + timedelta(days=d)).isoformat()
        ds["pos_sales"].append({"location_id": loc, "date": day, "menu_item": item, "qty": per_day})


def _p_special_no_recipe(ds):
    _add_sales(ds, "L02", "Birria Quesataco", 70)
    _add_sales(ds, "L05", "Birria Quesataco", 60)


def _p_seasonal_no_recipe(ds):
    _add_sales(ds, "L07", "Agua de Pepino", 9)


def _p_recipe_item_missing(ds):
    ds["recipes"].append({"menu_item": "Nopal Taco", "item_id": "queso_fresco", "qty_base": 0.04})


def _p_conversion_missing(ds):
    ds["conversions"].pop("RD-62041", None)


def _p_invoice_pack_conflict(ds):
    for r in ds["invoices"]:
        if r["location_id"] == "L05" and r["vendor_code"] == "US-2207718":
            r["pack"] = "6/1 LB"


def _p_duplicate_code(ds):
    ds["order_guide"].append({"vendor": "Sysco", "vendor_code": "SY-5520771", "description": "OIL CANOLA CLEAR FRY", "pack": "4/1 GAL", "case_price": 33.60})


def _p_pars_all_missing(ds):
    ds["par_levels"] = [r for r in ds["par_levels"] if r["location_id"] != "L10"]


def _p_pars_some_missing(ds):
    drop = {"cotija", "radish", "cinnamon"}
    ds["par_levels"] = [r for r in ds["par_levels"] if not (r["location_id"] == "L06" and r["item_id"] in drop)]


def _p_price_outlier(ds):
    for r in ds["invoices"]:
        if r["location_id"] == "L08" and r["vendor_code"] == "US-3307714":
            r["case_price"] = round(r["case_price"] * 1.3, 2)


def _p_no_opening_count(ds):
    ds["counts"] = [r for r in ds["counts"] if r["location_id"] != "L09"]


def _p_unknown_code(ds):
    ds["invoices"].append(
        {
            "location_id": "L03",
            "date": (HISTORY_START + timedelta(days=3)).isoformat(),
            "vendor": "Sysco",
            "invoice_no": "SY-1388",
            "vendor_code": "SY-9930118",
            "description": "CHORIZO PORK BULK",
            "pack": "2/5 LB",
            "cases": 1,
            "case_price": 46.00,
        }
    )


# (id, what was planted, the check expected to catch it, location or "group")
PROBLEMS = [
    ("P01", "POS not connected at L04 (no sales rows)", "pos_connected", "L04", _p_pos_missing),
    ("P02", "New special sold at L02 and L05 with no recipe", "menu_item_costed", "L02,L05", _p_special_no_recipe),
    ("P03", "Seasonal drink sold at L07 with no recipe (small share)", "menu_item_costed", "L07", _p_seasonal_no_recipe),
    ("P04", "Nopal taco recipe uses an item that is not in the catalog", "recipe_items_in_catalog", "L03,L07,L09", _p_recipe_item_missing),
    ("P05", "Limes bought by count, catalog tracks pounds, no conversion", "pack_in_catalog_units", "L09,L10", _p_conversion_missing),
    ("P06", "Invoice pack for Oaxaca cheese differs from the order guide", "invoice_pack_matches", "L05", _p_invoice_pack_conflict),
    ("P07", "Canola oil code listed twice with different packs", "no_duplicate_codes", "group", _p_duplicate_code),
    ("P08", "No par levels at L10", "par_levels_set", "L10", _p_pars_all_missing),
    ("P09", "Three par levels missing at L06", "par_levels_set", "L06", _p_pars_some_missing),
    ("P10", "Avocados at L08 cost 30% more than the group median", "price_in_line", "L08", _p_price_outlier),
    ("P11", "No opening count at L09", "opening_count", "L09", _p_no_opening_count),
    ("P12", "Invoice line for a code in no order guide at L03", "invoice_codes_mapped", "L03", _p_unknown_code),
]


def plant(ds: dict, problem_ids: list[str] | None = None) -> dict:
    out = copy.deepcopy(ds)
    for pid, _what, _check, _where, fn in PROBLEMS:
        if problem_ids is None or pid in problem_ids:
            fn(out)
    return out


def first_pull() -> dict:
    """The data as it arrives at signature: all problems planted, nobody has decided any mapping yet,
    and three locations order lines the group does not stock."""
    ds = plant(clean())
    ds["decisions"] = {}
    for loc, code, cases in (("L06", "US-8801273", 2), ("L08", "SY-1023901", 1), ("L03", "RD-65502", 1)):
        row = next(r for r in ORDER_GUIDE if r[1] == code)
        ds["invoices"].append(
            {
                "location_id": loc,
                "date": (HISTORY_START + timedelta(days=4)).isoformat(),
                "vendor": row[0],
                "invoice_no": f"{row[0][:2].upper()}-{2000 + int(loc[1:])}",
                "vendor_code": code,
                "description": row[2],
                "pack": row[3],
                "cases": cases,
                "case_price": row[4],
            }
        )
    return ds


def after_fixes() -> dict:
    """Every fix applied. The avocado price at L08 stays: that is a buying decision for the owner, not a data fix."""
    return plant(clean(), ["P10"])


# ---------------------------------------------------------------- two live weeks for the pilot wave

INCIDENTS = [
    ("I1", "POS feed gap at L02 on day 6", "pos_feed_gap", "L02"),
    ("I2", "Oaxaca cheese used 30% over what L01 sold (days 9 to 11)", "count_variance", "L01"),
    ("I3", "Sysco delivery at L03 on day 8 with no invoice", "missing_invoice", "L03"),
    ("I4", "Avocado case price up 22% at L01 on day 12", "price_jump", "L01"),
    ("I5", "Scheduled count skipped at L03 on day 11", "count_skipped", "L03"),
    ("I6", "New vendor item on an L02 invoice on day 12, not in any order guide", "unmapped_line", "L02"),
    ("I7", "Masa used 25% under what L02 sold (days 12 to 14)", "count_variance", "L02"),
]

DELIVERY_DAYS = {"Sysco": (1, 4, 8, 11), "US Foods": (2, 5, 9, 12), "Restaurant Depot": (3, 10)}


def live(incidents: list[str] | None = None, seed: int = 11) -> dict:
    """Days 1 to 14 after go-live for L01 to L03: sales, purchase orders, invoices and counts.

    Inventory is simulated so the counts agree with sales and recipes to within a few percent; each
    incident then changes one thing, as it would in a real kitchen.
    """
    rng = random.Random(seed)
    want = set(incidents) if incidents is not None else {i[0] for i in INCIDENTS}
    ds = {"pos_sales": [], "purchase_orders": [], "invoices": [], "counts": [], "count_schedule": list(COUNT_DAYS)}
    for loc, _name, factor in LOCATIONS:
        if loc not in PILOT_WAVE:
            continue
        items = _items_used(loc)
        daily = _avg_daily_use(loc, factor)
        on_hand = {i: daily[i] * 3 for i in items}
        po_no = 5000 + int(loc[1:]) * 100
        for d in range(1, LIVE_DAYS + 1):
            day = (LIVE_START + timedelta(days=d - 1)).isoformat()
            # deliveries arrive in the morning, against purchase orders drafted for 3.5 to 7 days of use
            for vendor, days in DELIVERY_DAYS.items():
                if d not in days:
                    continue
                po_no += 1
                cover = 7 if vendor == "Restaurant Depot" else 3.5
                lines = [i for i in items if next(r for r in ORDER_GUIDE if r[1] == source_code(i, loc))[0] == vendor]
                if not lines:
                    continue
                for item in lines:
                    code = source_code(item, loc)
                    row = next(r for r in ORDER_GUIDE if r[1] == code)
                    per_case = _base_per_case(code)
                    cases = max(1, math.ceil(daily[item] * cover / per_case))
                    ds["purchase_orders"].append({"location_id": loc, "po_no": f"PO-{po_no}", "vendor": vendor, "delivery_day": d, "vendor_code": code, "cases": cases})
                    price = row[4]
                    if "I4" in want and loc == "L01" and code == "US-3307714" and d >= 12:
                        price = round(price * 1.22, 2)
                    skip_invoice = "I3" in want and loc == "L03" and vendor == "Sysco" and d == 8
                    if not skip_invoice:
                        ds["invoices"].append(
                            {
                                "location_id": loc,
                                "day": d,
                                "date": day,
                                "vendor": vendor,
                                "invoice_no": f"INV-{po_no}",
                                "po_no": f"PO-{po_no}",
                                "vendor_code": code,
                                "description": row[2],
                                "pack": row[3],
                                "cases": cases,
                                "case_price": price,
                            }
                        )
                    on_hand[item] += cases * per_case
            if "I6" in want and loc == "L02" and d == 12:
                ds["invoices"].append(
                    {
                        "location_id": loc,
                        "day": d,
                        "date": day,
                        "vendor": "Sysco",
                        "invoice_no": "INV-7712",
                        "po_no": "",
                        "vendor_code": "SY-5561120",
                        "description": "PEPPER CHIPOTLE IN ADOBO",
                        "pack": "12/7 OZ",
                        "cases": 1,
                        "case_price": 31.20,
                    }
                )
            # service
            sales = {m: _daily_qty(rng, factor, m) for m in menu_at(loc)}
            gap = "I1" in want and loc == "L02" and d == 6
            for m, q in sales.items():
                if not gap:
                    ds["pos_sales"].append({"location_id": loc, "day": d, "date": day, "menu_item": m, "qty": q})
            use = _usage(sales)
            for extra in EXTRA_PAR_ITEMS:
                if extra not in use:
                    use[extra] = _avg_daily_use(loc, factor)[extra] * rng.uniform(0.9, 1.1)
            for item in items:
                real = use.get(item, 0) * rng.uniform(0.98, 1.02)
                if "I2" in want and loc == "L01" and item == "oaxaca_cheese" and 9 <= d <= 11:
                    real *= 1.30
                if "I7" in want and loc == "L02" and item == "masa_harina" and 12 <= d <= 14:
                    real *= 0.75
                on_hand[item] = max(0.0, on_hand[item] - real)
            if d in COUNT_DAYS and not ("I5" in want and loc == "L03" and d == 11):
                for item in items:
                    ds["counts"].append({"location_id": loc, "day": d, "date": day, "item_id": item, "qty_base": round(on_hand[item] * rng.uniform(0.995, 1.005), 2)})
    return ds


# ---------------------------------------------------------------- CSV in and out


def write(ds: dict, folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for name, rows in ds.items():
        if name == "decisions":
            rows = [{"vendor_code": k, "item_id": v} for k, v in sorted(rows.items())]
            name = "mapping_decisions"
        elif name == "conversions":
            rows = [{"vendor_code": k, "base_per_case": v} for k, v in sorted(rows.items())]
        elif name == "count_schedule":
            rows = [{"day": d} for d in rows]
        if not rows:
            # keep the header so a reader knows the table exists and is empty
            headers = {"mapping_decisions": ["vendor_code", "item_id"], "conversions": ["vendor_code", "base_per_case"]}
            (folder / f"{name}.csv").write_text(",".join(headers.get(name, ["empty"])) + "\n")
            continue
        with (folder / f"{name}.csv").open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)


def read(folder: Path) -> dict:
    ds: dict = {}
    for path in sorted(folder.glob("*.csv")):
        with path.open() as f:
            rows = list(csv.DictReader(f))
        name = path.stem
        if name == "mapping_decisions":
            ds["decisions"] = {r["vendor_code"]: r["item_id"] for r in rows}
        elif name == "conversions":
            ds["conversions"] = {r["vendor_code"]: float(r["base_per_case"]) for r in rows}
        elif name == "count_schedule":
            ds["count_schedule"] = [int(r["day"]) for r in rows]
        else:
            ds[name] = rows
    return ds
