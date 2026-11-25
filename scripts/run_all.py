"""Regenerate the sample data, run everything, and write reports/ and reports/results.json.

Replays recordings/mapping.jsonl. With MAPPER_LIVE=1 and ANTHROPIC_API_KEY set, lines with no
recorded reply are sent to Claude and the replies are appended to the recording.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from eval import run_eval  # noqa: E402
from onboarding import checks, monitor, sample  # noqa: E402
from onboarding.claude_map import MODEL, load_recording  # noqa: E402
from onboarding.data import CATALOG  # noqa: E402
from onboarding.mapper import stage_counts  # noqa: E402
from onboarding.report import monitor_markdown, readiness_markdown  # noqa: E402


def _state(result: dict) -> dict:
    maps = result["mappings"]
    return {
        "locations": result["locations"],
        "group_findings": result["group_findings"],
        "stages": stage_counts_from(maps),
        "review_queue": [m for m in maps if m["stage"] == "review"],
        "by_owner": {o: len(f) for o, f in sorted(result["fixes_by_owner"].items())},
    }


def stage_counts_from(maps: list[dict]) -> dict:
    class _M:  # stage_counts takes objects with a .stage
        def __init__(self, s):
            self.stage = s

    return stage_counts([_M(m["stage"]) for m in maps])


def main() -> dict:
    data = ROOT / "sample_data"
    first, fixed, live = sample.first_pull(), sample.after_fixes(), sample.live()
    sample.write(first, data / "first_pull")
    sample.write(fixed, data / "after_fixes")
    sample.write(live, data / "live")

    recording = load_recording()
    r_first = checks.run(first, recording=recording)
    r_fixed = checks.run(fixed, recording=recording)
    r_live = monitor.run(live, fixed, r_fixed["mappings"])

    reports = ROOT / "reports"
    reports.mkdir(exist_ok=True)
    (reports / "first_pull.md").write_text(readiness_markdown(r_first, "Go-live readiness: first data pull"))
    (reports / "after_fixes.md").write_text(readiness_markdown(r_fixed, "Go-live readiness: after fixes"))
    (reports / "live.md").write_text(monitor_markdown(r_live))

    ev = run_eval.main()
    results = {
        "model": MODEL,
        "catalog_items": len(CATALOG),
        "order_guide_lines": len(first["order_guide"]),
        "first_pull": _state(r_first),
        "after_fixes": _state(r_fixed),
        "live": r_live,
        "incidents": [{"id": i, "what": w, "kind": k, "location": loc} for i, w, k, loc in sample.INCIDENTS],
        "eval": ev,
    }
    (reports / "results.json").write_text(json.dumps(results, indent=2, sort_keys=True) + "\n")
    return results


if __name__ == "__main__":
    main()
