# restaurant-onboarding-monitor

[![CI](https://github.com/pg2342-hub/restaurant-onboarding-monitor/actions/workflows/ci.yml/badge.svg)](https://github.com/pg2342-hub/restaurant-onboarding-monitor/actions/workflows/ci.yml)

Demo page: https://pranavgudise.dev/restaurant-onboarding-monitor/ (switch between the first data pull, the same group after fixes, and two live weeks; select a location or a day to see what is wrong and who fixes it)

A multi-location restaurant group signs on to a back-of-house system. Before a location goes live, its POS sales, distributor order guides, invoices, recipes, par levels and counts have to line up in one item catalog, or food cost, ordering and variance are wrong from day one. This tool does that onboarding work and then keeps watching:

1. **Map.** Every order guide line is mapped to a catalog item. Rules go first and are strict: they map a line only when every word of exactly one catalog name is in the description after expanding distributor abbreviations. Claude (`claude-opus-5-5`, structured output) suggests an item for the rest. Code decides what is accepted: the item must exist in the catalog, the pack must convert to the catalog's unit, and the confidence must be high. Everything else goes to a person, and a person's decision in `mapping_decisions.csv` always wins.
2. **Check readiness.** Ten checks per location say GO, GO WITH FIXES or NO-GO, and group every fix by its owner (POS admin, culinary lead, onboarding lead, general manager, purchasing).
3. **Monitor.** After go-live, six daily checks on the live data: POS feed gaps, counted usage that does not match sales times recipes, deliveries with no invoice, price jumps, skipped counts, and new invoice lines that are not mapped.

All data is made up: a ten-location taqueria group with invented locations, sales, recipes and counts. Sysco, US Foods and Restaurant Depot are real distributors; the codes, descriptions and prices are invented in the style of their order guides.

## Run it

```
pip install -e ".[dev]"
pytest -q                                         # no network, no key
python scripts/run_all.py                         # regenerates sample_data/, replays the recorded Claude run, writes reports/
python -m onboarding.report sample_data/first_pull
python -m onboarding.report sample_data/live --base sample_data/after_fixes
python docs/build_page.py                         # rebuilds the demo page from reports/results.json
```

The live Claude run is recorded in `recordings/mapping.jsonl` by the "Record a live run" workflow (needs the `ANTHROPIC_API_KEY` secret). Every other run replays it, so tests and the demo need no key. Locally, `MAPPER_LIVE=1 python scripts/run_all.py` records lines that have no reply yet.

## What it checks

| Before go-live | Severity | Owner |
|---|---|---|
| POS connected | blocking | POS admin |
| Every item sold has a recipe | blocking at 2% or more of units, else warning | Culinary lead |
| Recipes use catalog items | blocking | Culinary lead |
| Every invoice line maps to a catalog item | blocking (warning if the group decided not to stock it) | Onboarding lead |
| Packs convert to catalog units | blocking | Onboarding lead |
| Invoice packs match the order guide | blocking | Onboarding lead with the vendor rep |
| Par levels set | blocking if none, else warning | General manager |
| Opening count done | blocking | General manager |
| Prices in line with the group (25% over median) | warning | Owner or purchasing |
| Each vendor code listed once | warning (group) | Onboarding lead |

| Every day after go-live | Owner |
|---|---|
| POS feed gap | POS admin |
| Counted usage more than 15% (and $20) from sales times recipes | General manager |
| Delivery on a purchase order with no invoice | General manager |
| Case price more than 15% over the previous invoice | Owner or purchasing |
| Scheduled count skipped | General manager |
| Invoice line not mapped to a catalog item | Onboarding lead |

Usage checks hold for a window that contains a POS gap or an uninvoiced delivery, so one problem raises one alert, not a dozen.

## Eval

`eval/run_eval.py` plants known problems into the clean system one at a time.

| Run | Result |
|---|---|
| Clean system | 0 findings, 0 alerts |
| Readiness problems planted alone | 12 of 12 caught, 0 false positives |
| Live incidents planted alone | 7 of 7 caught, 0 false positives |
| 30 more simulated live weeks with nothing planted | 0 alerts |
| Order guide mapping, rules only | 22 of 37 lines mapped, 0 wrong, 15 to a person |
| Order guide mapping, rules then Claude | see `reports/results.json` (recorded run); gate: no wrong line reaches the catalog |

## Layout

```
onboarding/data.py       the made-up group: catalog, order guides, menu, recipes, locations
onboarding/sample.py     clean system, planted problems, first pull, after fixes, two live weeks
onboarding/packs.py      reads "4/10 LB", "6/32 OZ", "1/200 CT" into catalog units
onboarding/mapper.py     rules, Claude suggestion, guardrails, review queue
onboarding/claude_map.py the Claude call, recorded and replayed
onboarding/checks.py     go-live readiness checks and verdicts
onboarding/monitor.py    daily live checks
eval/run_eval.py         planted problem eval and mapping grade
scripts/run_all.py       regenerates everything; docs/build_page.py builds the demo
```
