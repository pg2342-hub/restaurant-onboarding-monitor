"""Grades the recorded live Claude run once it exists (recordings/mapping.jsonl)."""

import pytest

from eval.run_eval import mapping_eval
from onboarding.claude_map import RECORDING, load_recording

pytestmark = pytest.mark.skipif(not RECORDING.exists(), reason="no recorded live run yet")


def test_recorded_run_passes_the_gate():
    mp = mapping_eval(load_recording())
    assert mp["claude_replies"] == mp["lines_sent_to_claude"]
    assert mp["with_claude"]["wrong_auto"] == 0, mp["with_claude"]["wrong_lines"]
    assert mp["gate_result"] == "GO"
