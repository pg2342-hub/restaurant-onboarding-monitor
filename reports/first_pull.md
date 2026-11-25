# Go-live readiness: first data pull

| Location | Wave | Verdict | Blocking | Warnings |
|---|---|---|---|---|
| L01 Westside | 1 | GO | 0 | 0 |
| L02 Harbor | 1 | NO-GO | 1 | 0 |
| L03 Midtown East | 1 | NO-GO | 4 | 0 |
| L04 Northgate | 2 | NO-GO | 1 | 0 |
| L05 Canal | 2 | NO-GO | 2 | 0 |
| L06 Riverside | 2 | NO-GO | 1 | 1 |
| L07 Union | 2 | NO-GO | 2 | 1 |
| L08 Park Row | 2 | NO-GO | 1 | 1 |
| L09 Eastbank | 2 | NO-GO | 4 | 0 |
| L10 Hillcrest | 2 | NO-GO | 2 | 0 |

## Fixes by owner

### Culinary lead
- L02: Birria Quesataco: 490 sold (8% of units) with no recipe (blocking)
- L03: Nopal Taco uses 'queso_fresco', which is not in the catalog (blocking)
- L05: Birria Quesataco: 420 sold (6% of units) with no recipe (blocking)
- L07: Agua de Pepino: 63 sold (1% of units) with no recipe (warning)
- L07: Nopal Taco uses 'queso_fresco', which is not in the catalog (blocking)
- L09: Nopal Taco uses 'queso_fresco', which is not in the catalog (blocking)

### General manager
- L06: 1 item used in recipes has no par: cinnamon sticks (warning)
- L09: No opening count on file (blocking)
- L10: No par levels set (21 items used in recipes) (blocking)

### Onboarding lead
- group: vendor code SY-5520771 is listed twice with different packs ('6/1 GAL' and '4/1 GAL') (warning)
- L03: US Foods US-6608830 CACTUS LEAVES, CLEANED DICED: waiting in the review queue (Claude: not in the catalog; add it or stop ordering it) (blocking)
- L03: Sysco SY-9930118 CHORIZO PORK BULK: not in any order guide (blocking)
- L03: Restaurant Depot RD-65502 PULPO COCIDO: waiting in the review queue (Claude: not in the catalog; add it or stop ordering it) (blocking)
- L06: US Foods US-8801273 CHEESE, MOZZARELLA SHREDDED: waiting in the review queue (Claude: not in the catalog; add it or stop ordering it) (blocking)
- L07: US Foods US-6608830 CACTUS LEAVES, CLEANED DICED: waiting in the review queue (Claude: not in the catalog; add it or stop ordering it) (blocking)
- L08: Sysco SY-1023901 CHKN BRST BNLS SKLS: waiting in the review queue (Claude: not in the catalog; add it or stop ordering it) (blocking)
- L09: Restaurant Depot RD-62041 LIMONES 200CT: pack '1/200 CT' is sold by count but the catalog tracks lime by lb; needs a conversion (blocking)
- L09: US Foods US-6608830 CACTUS LEAVES, CLEANED DICED: waiting in the review queue (Claude: not in the catalog; add it or stop ordering it) (blocking)
- L10: Restaurant Depot RD-62041 LIMONES 200CT: pack '1/200 CT' is sold by count but the catalog tracks lime by lb; needs a conversion (blocking)

### Onboarding lead with the vendor rep
- L05: US Foods US-2207718 CHEESE, OAXACA QUESILLO STRING: invoice says '6/1 LB' (6 lb a case), order guide says '6/5 LB' (30 lb a case) (blocking)

### Owner or purchasing
- L08: avocado hass: $1.62 per each vs group median $1.25 (+30%) (warning)

### POS admin (group)
- L04: No sales rows from the POS for this location (blocking)

## Review queue

- Sysco SY-1023901 CHKN BRST BNLS SKLS (4/10 LB): Claude: not in the catalog; add it or stop ordering it
- US Foods US-6608830 CACTUS LEAVES, CLEANED DICED (4/5 LB): Claude: not in the catalog; add it or stop ordering it
- US Foods US-8801273 CHEESE, MOZZARELLA SHREDDED (4/5 LB): Claude: not in the catalog; add it or stop ordering it
- Restaurant Depot RD-65502 PULPO COCIDO (1/4 LB): Claude: not in the catalog; add it or stop ordering it
