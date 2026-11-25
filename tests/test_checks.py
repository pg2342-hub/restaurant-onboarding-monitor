from eval.run_eval import mapping_eval, monitor_eval, readiness_eval
from onboarding import checks, sample
from onboarding.mapper import rule_match
from onboarding.packs import base_per_case, parse_pack


def test_pack_parsing():
    assert base_per_case(parse_pack("4/10 LB"), "weight", "lb") == 40
    assert base_per_case(parse_pack("6/32 OZ"), "volume", "qt") == 6
    assert base_per_case(parse_pack("6/1 GAL"), "volume", "qt") == 24
    assert base_per_case(parse_pack("1/200 CT"), "weight", "lb") is None  # count pack, weight catalog
    assert base_per_case(parse_pack("1/200 CT"), "weight", "lb", 40.0) == 40.0
    assert parse_pack("CASE") is None


def test_rules_never_map_a_different_cut():
    cat = sample.clean()["catalog"]
    assert rule_match("CHICKEN THIGH BNLS SKLS", cat) == "chicken_thigh"
    assert rule_match("CHKN BRST BNLS SKLS", cat) is None
    assert rule_match("CHEESE, MOZZARELLA SHREDDED", cat) is None


def test_rules_make_no_wrong_mapping():
    truth = sample.truth_map()
    for row in sample.clean()["order_guide"]:
        hit = rule_match(row["description"], sample.clean()["catalog"])
        assert hit is None or hit == truth[row["vendor_code"]], row


def test_clean_system_is_go_everywhere():
    result = checks.run(sample.clean(), use_claude=False, recording={})
    assert result["findings"] == []
    assert {loc["verdict"] for loc in result["locations"]} == {"GO"}


def test_every_planted_readiness_problem_is_caught_alone():
    r = readiness_eval()
    assert r["clean_findings"] == 0
    assert r["caught"] == r["total"] == 12
    assert r["false_positives"] == 0


def test_every_live_incident_is_caught_and_quiet_weeks_stay_quiet():
    m = monitor_eval()
    assert m["clean_alerts"] == 0
    assert m["caught"] == m["total"] == 7
    assert m["false_positives"] == 0
    assert m["quiet_week_alerts"] == 0


def test_after_fixes_only_the_price_decision_remains():
    result = checks.run(sample.after_fixes(), use_claude=False, recording={})
    assert [f.check for f in result["findings"]] == ["price_in_line"]


def test_without_a_recording_unread_lines_go_to_a_person():
    mp = mapping_eval(recording={})
    assert mp["with_claude"]["wrong_auto"] == 0
    assert mp["with_claude"]["to_review"] == mp["lines_sent_to_claude"] == 15
    assert mp["gate_result"] == "PENDING"


def test_guardrails_reject_bad_claude_answers():
    ds = sample.first_pull()
    cat = ds["catalog"]
    from onboarding import claude_map

    rows = {r["vendor_code"]: r for r in ds["order_guide"]}
    fake = {}
    for code, item, conf in (("RD-60177", "hibiscus", "high"), ("RD-62041", "lime", "high"), ("US-2211150", "sour_cream", "high"), ("RD-61290", "pinto_beans", "medium")):
        key = claude_map.key_for(claude_map.request_for(rows[code], cat))
        fake[key] = {"key": key, "suggestion": {"item_id": item, "confidence": conf, "reason": "test"}}
    maps = {m["vendor_code"]: m for m in checks.run(ds, recording=fake)["mappings"]}
    assert maps["RD-60177"]["stage"] == "claude" and maps["RD-60177"]["item_id"] == "hibiscus"
    assert maps["RD-62041"]["stage"] == "claude" and maps["RD-62041"]["base_per_case"] is None  # count pack: blocks until converted
    assert maps["US-2211150"]["stage"] == "review"  # not a catalog item
    assert maps["RD-61290"]["stage"] == "review"  # not high confidence
