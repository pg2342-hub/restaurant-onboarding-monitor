"""Build docs/index.html from reports/results.json and docs/template.html, then add the shared chrome."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from onboarding.checks import CHECKS  # noqa: E402
from onboarding.monitor import ALERTS  # noqa: E402


def page_data(r: dict) -> dict:
    ev = r["eval"]
    mp = ev["mapping"]
    first = r["first_pull"]
    return {
        "first": first,
        "fixed": r["after_fixes"],
        "live": r["live"],
        "mapping": {
            "lines": r["order_guide_lines"],
            "stages": first["stages"],
            "replies": mp["claude_replies"],
            "right": mp["claude_right"],
            "wrong": mp["with_claude"]["wrong_auto"],
            "suggestions": mp["suggestions"],
            "gate": mp["gate"],
            "gate_result": mp["gate_result"],
            "cost": mp["cost_usd"],
            "latency": mp["mean_latency_s"],
            "model": r["model"],
        },
        "eval": {
            "r_caught": ev["readiness"]["caught"],
            "r_total": ev["readiness"]["total"],
            "r_fp": ev["readiness"]["false_positives"],
            "r_clean": ev["readiness"]["clean_findings"],
            "m_caught": ev["monitor"]["caught"],
            "m_total": ev["monitor"]["total"],
            "m_fp": ev["monitor"]["false_positives"],
            "quiet": ev["monitor"]["quiet_week_alerts"],
            "quiet_weeks": ev["monitor"]["quiet_weeks_checked"],
        },
        "issues": [f"Readiness: {p['problem']}" for p in ev["readiness"]["planted"]] + [f"Live: {p['incident']}" for p in ev["monitor"]["planted"]],
        "checks": [{"name": v[0], "when": "Before go-live", "owner": v[1]} for v in CHECKS.values()]
        + [{"name": v[0], "when": "Every day after go-live", "owner": v[1]} for v in ALERTS.values()],
    }


def main() -> None:
    r = json.loads((ROOT / "reports" / "results.json").read_text())
    tpl = (ROOT / "docs" / "template.html").read_text()
    data = json.dumps(page_data(r), separators=(",", ":")).replace("</", "<\\/")
    out = ROOT / "docs" / "index.html"
    out.write_text(tpl.replace("/*DATA*/null", data))
    subprocess.run([sys.executable, str(ROOT / "scripts" / "demo_chrome.py"), str(out), "--repo", "restaurant-onboarding-monitor"], check=True)
    (ROOT / "docs" / ".nojekyll").touch()


if __name__ == "__main__":
    main()
