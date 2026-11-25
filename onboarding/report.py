"""Command line: readiness report for a folder of CSVs, or the live monitor for a live folder.

python -m onboarding.report sample_data/first_pull
python -m onboarding.report sample_data/live --base sample_data/after_fixes
"""

from __future__ import annotations

import argparse
from pathlib import Path

from . import checks, monitor, sample


def readiness_markdown(result: dict, title: str) -> str:
    lines = [f"# {title}", "", "| Location | Wave | Verdict | Blocking | Warnings |", "|---|---|---|---|---|"]
    for loc in result["locations"]:
        lines.append(f"| {loc['location_id']} {loc['name']} | {loc['pilot_wave']} | {loc['verdict']} | {loc['blocking']} | {loc['warnings']} |")
    lines += ["", "## Fixes by owner", ""]
    for owner, fixes in sorted(result["fixes_by_owner"].items()):
        lines.append(f"### {owner}")
        for f in fixes:
            lines.append(f"- {f['location']}: {f['detail']} ({f['severity']})")
        lines.append("")
    queue = [m for m in result["mappings"] if m["stage"] == "review"]
    if queue:
        lines += ["## Review queue", ""]
        for m in queue:
            lines.append(f"- {m['vendor']} {m['vendor_code']} {m['description']} ({m['pack']}): {'; '.join(m['issues'])}")
    return "\n".join(lines) + "\n"


def monitor_markdown(result: dict) -> str:
    lines = ["# Live monitor", "", "| Day | Location | Alert | Owner | Detail |", "|---|---|---|---|---|"]
    for a in result["alerts"]:
        lines.append(f"| {a['day']} | {a['location']} | {a['alert_name']} | {a['owner']} | {a['detail']} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("folder", type=Path)
    p.add_argument("--base", type=Path, help="onboarded system folder (for a live folder)")
    args = p.parse_args()
    ds = sample.read(args.folder)
    if "purchase_orders" in ds:
        base = sample.read(args.base or args.folder.parent / "after_fixes")
        maps = checks.run(base)["mappings"]
        print(monitor_markdown(monitor.run(ds, base, maps)))
    else:
        print(readiness_markdown(checks.run(ds), f"Go-live readiness: {args.folder.name}"))


if __name__ == "__main__":
    main()
