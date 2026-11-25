"""Eval: plant each known problem alone into the clean system and check it is caught, with nothing extra.

Readiness: 12 planted problems. Monitor: 7 planted incidents over two live weeks.
Mapping: every order guide line has a known answer; the eval grades where each line ended up.
Writes eval/results/eval_results.json.
"""

from __future__ import annotations

import json
from pathlib import Path

from onboarding import checks, monitor, sample
from onboarding.claude_map import load_recording

OUT = Path(__file__).resolve().parent / "results" / "eval_results.json"


def readiness_eval() -> dict:
    base = sample.clean()
    clean_findings = checks.run(base, use_claude=False, recording={})["findings"]
    rows = []
    for pid, what, check, where, _fn in sample.PROBLEMS:
        found = checks.run(sample.plant(base, [pid]), use_claude=False, recording={})["findings"]
        expected_locs = set(where.split(","))
        hit_locs = {f.location for f in found if f.check == check}
        extra = [f for f in found if f.check != check or f.location not in expected_locs]
        rows.append({"id": pid, "problem": what, "check": check, "caught": hit_locs == expected_locs, "extra_findings": len(extra)})
    together = checks.run(sample.plant(base), use_claude=False, recording={})
    return {
        "clean_findings": len(clean_findings),
        "planted": rows,
        "caught": sum(r["caught"] for r in rows),
        "total": len(rows),
        "false_positives": sum(r["extra_findings"] for r in rows),
        "all_together_findings": len(together["findings"]),
    }


def monitor_eval() -> dict:
    base = sample.clean()
    maps = checks.run(base, use_claude=False, recording={})["mappings"]
    clean_alerts = monitor.run(sample.live([]), base, maps)["alerts"]
    rows = []
    for iid, what, kind, loc in sample.INCIDENTS:
        alerts = monitor.run(sample.live([iid]), base, maps)["alerts"]
        hit = [a for a in alerts if a["kind"] == kind and a["location"] == loc]
        extra = [a for a in alerts if not (a["kind"] == kind and a["location"] == loc)]
        rows.append({"id": iid, "incident": what, "alert": kind, "caught": len(hit) == 1, "extra_alerts": len(extra)})
    together = monitor.run(sample.live(), base, maps)["alerts"]
    # The same checks on other random weeks with no incident should stay quiet
    quiet = sum(len(monitor.run(sample.live([], seed=s), base, maps)["alerts"]) for s in range(100, 130))
    return {
        "clean_alerts": len(clean_alerts),
        "planted": rows,
        "caught": sum(r["caught"] for r in rows),
        "total": len(rows),
        "false_positives": sum(r["extra_alerts"] for r in rows),
        "all_together_alerts": len(together),
        "quiet_weeks_checked": 30,
        "quiet_week_alerts": quiet,
    }


def mapping_eval(recording: dict | None = None) -> dict:
    """Grade the first pull's mapping (no person decisions yet) against the answer key."""
    truth = sample.truth_map()
    ds = sample.first_pull()
    recording = load_recording() if recording is None else recording

    def grade(maps):
        out = {"lines": len(maps), "correct_auto": 0, "wrong_auto": 0, "to_review": 0, "wrong_lines": []}
        for m in maps:
            if m["stage"] in ("rules", "claude"):
                if m["item_id"] == truth[m["vendor_code"]]:
                    out["correct_auto"] += 1
                else:
                    out["wrong_auto"] += 1
                    out["wrong_lines"].append(f"{m['vendor_code']} {m['description']} -> {m['item_id']}")
            else:
                out["to_review"] += 1
        return out

    rules_only = checks.run(ds, use_claude=False, recording={})["mappings"]
    with_claude = checks.run(ds, use_claude=True, recording=recording)["mappings"]
    sent = [m for m in with_claude if m["claude"]]
    suggestions = []
    for m in sent:
        s = m["claude"]["suggestion"]
        right = (s["item_id"] == "NOT_IN_CATALOG" and truth[m["vendor_code"]] == "") or s["item_id"] == truth[m["vendor_code"]]
        suggestions.append(
            {
                "vendor_code": m["vendor_code"],
                "description": m["description"],
                "truth": truth[m["vendor_code"]] or "NOT_IN_CATALOG",
                "suggested": s["item_id"],
                "confidence": s["confidence"],
                "reason": s["reason"],
                "right": right,
                "stage": m["stage"],
                "cost_usd": m["claude"].get("cost_usd"),
                "latency_s": m["claude"].get("latency_s"),
            }
        )
    lines_for_claude = sum(1 for m in rules_only if m["stage"] == "review")
    graded = grade(with_claude)
    gate_go = bool(sent) and len(sent) == lines_for_claude and graded["wrong_auto"] == 0
    return {
        "rules_only": grade(rules_only),
        "with_claude": graded,
        "lines_sent_to_claude": lines_for_claude,
        "claude_replies": len(sent),
        "claude_right": sum(s["right"] for s in suggestions),
        "suggestions": suggestions,
        "cost_usd": round(sum(s["cost_usd"] or 0 for s in suggestions), 4),
        "mean_latency_s": round(sum(s["latency_s"] or 0 for s in suggestions) / len(suggestions), 2) if suggestions else None,
        "gate": "no wrong line reaches the catalog, and every line the rules could not read gets a Claude reply",
        "gate_result": "GO" if gate_go else ("PENDING" if not sent else "NO-GO"),
    }


def main() -> dict:
    results = {"readiness": readiness_eval(), "monitor": monitor_eval(), "mapping": mapping_eval()}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(results, indent=2) + "\n")
    r, m, mp = results["readiness"], results["monitor"], results["mapping"]
    print(f"readiness: clean {r['clean_findings']} findings; {r['caught']} of {r['total']} planted caught; {r['false_positives']} extra")
    print(
        f"monitor: clean {m['clean_alerts']} alerts; {m['caught']} of {m['total']} incidents caught; {m['false_positives']} extra; "
        f"{m['quiet_week_alerts']} alerts in {m['quiet_weeks_checked']} quiet weeks"
    )
    print(f"mapping: rules only {mp['rules_only']}; with Claude {mp['with_claude']}; gate {mp['gate_result']}")
    return results


if __name__ == "__main__":
    main()
