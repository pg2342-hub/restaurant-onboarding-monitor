"""After go-live: daily checks on the live data, so wrong numbers are caught before a manager trusts them.

Each alert names the location, the day, the owner and the first thing to check.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

VARIANCE_PCT = 0.15  # counted usage this far from what sales and recipes say
VARIANCE_DOLLARS = 20.0  # and worth at least this much at reference cost
PRICE_JUMP = 0.15  # case price this far over the previous invoice for the same line

ALERTS = {
    "pos_feed_gap": ("POS feed gap", "POS admin (group)", "Check the POS connection for that day and backfill the sales"),
    "count_variance": ("Usage does not match sales", "General manager", "Recount the item, then check portioning, waste log and the recipe yield"),
    "missing_invoice": ("Delivery with no invoice", "General manager", "Find the delivery slip and get the invoice from the vendor"),
    "price_jump": ("Price jump", "Owner or purchasing", "Ask the vendor rep whether the new price holds or was a mistake"),
    "count_skipped": ("Scheduled count skipped", "General manager", "Do the count today so the next variance window is not twice as long"),
    "unmapped_line": ("New line on an invoice", "Onboarding lead", "Map the line to a catalog item or tell the location to stop ordering it"),
}


@dataclass
class Alert:
    kind: str
    location: str
    day: int
    detail: str

    @property
    def owner(self) -> str:
        return ALERTS[self.kind][1]


def run(live: dict, base: dict, maps: list[dict]) -> dict:
    """live: the live tables; base: the onboarded system (catalog, recipes, order guide); maps: mapper output."""
    by_code = {m["vendor_code"]: m for m in maps}
    cat = {c["item_id"]: c for c in base["catalog"]}
    recipes: dict[str, dict[str, float]] = {}
    for r in base["recipes"]:
        recipes.setdefault(r["menu_item"], {})[r["item_id"]] = float(r["qty_base"])
    schedule = [int(d) for d in live.get("count_schedule", [])]
    locs = sorted({r["location_id"] for r in live["purchase_orders"]})
    days = sorted({int(r["delivery_day"]) for r in live["purchase_orders"]} | {int(r["day"]) for r in live["counts"]} | set(schedule))
    last_day = max(days) if days else 0
    alerts: list[Alert] = []

    for loc in locs:
        sales = [r for r in live["pos_sales"] if r["location_id"] == loc]
        sale_days = {int(r["day"]) for r in sales}
        gap_days = [d for d in range(1, last_day + 1) if d not in sale_days]
        for d in gap_days:
            alerts.append(Alert("pos_feed_gap", loc, d, "No sales rows arrived for the day; usage checks that span it are held"))

        invoices = [r for r in live["invoices"] if r["location_id"] == loc]
        pos_with_invoice = {r["po_no"] for r in invoices if r["po_no"]}
        pos = {}
        for r in live["purchase_orders"]:
            if r["location_id"] == loc:
                pos.setdefault(r["po_no"], r)
        unreceived: set[tuple[int, str]] = set()  # (day, item) received with no invoice: usage checks hold
        for po_no, r in sorted(pos.items()):
            if po_no not in pos_with_invoice:
                alerts.append(Alert("missing_invoice", loc, int(r["delivery_day"]), f"{r['vendor']} {po_no} was due on day {r['delivery_day']}; no invoice"))
                for line in live["purchase_orders"]:
                    m = by_code.get(line["vendor_code"])
                    if line["po_no"] == po_no and line["location_id"] == loc and m and m.get("item_id"):
                        unreceived.add((int(r["delivery_day"]), m["item_id"]))

        last_price: dict[str, tuple[int, float]] = {}
        for inv in sorted(invoices, key=lambda r: int(r["day"])):
            code = inv["vendor_code"]
            m = by_code.get(code)
            if m is None or not m.get("item_id"):
                alerts.append(
                    Alert("unmapped_line", loc, int(inv["day"]), f"{inv['vendor']} {code} {inv['description']} ({inv['pack']}) is not mapped to a catalog item")
                )
                continue
            price = float(inv["case_price"])
            if code in last_price and price > last_price[code][1] * (1 + PRICE_JUMP):
                prev_day, prev = last_price[code]
                alerts.append(
                    Alert("price_jump", loc, int(inv["day"]), f"{inv['description']}: ${price:.2f} a case, was ${prev:.2f} on day {prev_day} ({price / prev - 1:+.0%})")
                )
            last_price[code] = (int(inv["day"]), price)

        counts: dict[int, dict[str, float]] = {}
        for r in live["counts"]:
            if r["location_id"] == loc:
                counts.setdefault(int(r["day"]), {})[r["item_id"]] = float(r["qty_base"])
        for d in schedule:
            if d <= last_day and d not in counts:
                alerts.append(Alert("count_skipped", loc, d, f"No count on day {d}; the next usage check covers a longer window"))

        count_days = sorted(counts)
        for a, b in zip(count_days, count_days[1:], strict=False):
            if any(a < g <= b for g in gap_days):
                continue  # sales are incomplete for this window; the POS gap alert covers it
            theo: dict[str, float] = {}
            for r in sales:
                if a < int(r["day"]) <= b:
                    for item, per in recipes.get(r["menu_item"], {}).items():
                        theo[item] = theo.get(item, 0) + per * int(r["qty"])
            received: dict[str, float] = {}
            for inv in invoices:
                if a < int(inv["day"]) <= b:
                    m = by_code.get(inv["vendor_code"])
                    if m and m.get("item_id") and m.get("base_per_case"):
                        received[m["item_id"]] = received.get(m["item_id"], 0) + int(inv["cases"]) * m["base_per_case"]
            for item, expected in sorted(theo.items()):
                if item not in counts[a] or item not in counts[b] or expected <= 0:
                    continue
                if any(a < d <= b and i == item for d, i in unreceived):
                    continue  # a delivery in this window has no invoice; the missing invoice alert covers it
                actual = counts[a][item] + received.get(item, 0) - counts[b][item]
                diff = actual - expected
                dollars = abs(diff) * float(cat[item]["ref_cost"])
                if abs(diff) / expected > VARIANCE_PCT and dollars >= VARIANCE_DOLLARS:
                    unit = cat[item]["base_unit"]
                    direction = "more" if diff > 0 else "less"
                    alerts.append(
                        Alert(
                            "count_variance",
                            loc,
                            b,
                            f"{cat[item]['name']}: counts show {actual:.1f} {unit} used on days {a + 1} to {b}, sales and recipes say "
                            f"{expected:.1f} ({abs(diff) / expected:.0%} {direction}, about ${dollars:.0f})",
                        )
                    )

    alerts.sort(key=lambda x: (x.day, x.location, x.kind))
    return {
        "alerts": [asdict(a) | {"owner": a.owner, "alert_name": ALERTS[a.kind][0], "first_check": ALERTS[a.kind][2]} for a in alerts],
        "locations": locs,
        "days": last_day,
    }
