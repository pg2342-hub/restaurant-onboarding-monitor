"""The made-up restaurant group: catalog, vendor order guides, menu, recipes, and locations.

Everything here is invented for the demo. Vendor names (Sysco, US Foods, Restaurant Depot) are real
distributors and appear because their order guides are what a group exports at onboarding; the item
codes, descriptions, and prices are made up in their style.
"""

from __future__ import annotations

# item_id, name, family (weight | volume | count), base unit, category, reference cost per base unit ($)
CATALOG = [
    ("chicken_thigh", "chicken thigh boneless skinless", "weight", "lb", "protein", 3.10),
    ("beef_skirt", "beef skirt steak", "weight", "lb", "protein", 9.80),
    ("pork_shoulder", "pork shoulder boneless", "weight", "lb", "protein", 3.40),
    ("shrimp", "shrimp peeled deveined 21/25", "weight", "lb", "protein", 8.90),
    ("oaxaca_cheese", "oaxaca cheese", "weight", "lb", "dairy", 5.60),
    ("cotija", "cotija cheese crumbled", "weight", "lb", "dairy", 6.20),
    ("crema", "mexican crema", "volume", "qt", "dairy", 4.80),
    ("white_onion", "white onion", "weight", "lb", "produce", 0.95),
    ("cilantro", "cilantro", "count", "bunch", "produce", 0.55),
    ("lime", "lime", "weight", "lb", "produce", 1.30),
    ("avocado", "avocado hass", "count", "each", "produce", 1.25),
    ("jalapeno", "jalapeno pepper", "weight", "lb", "produce", 1.40),
    ("roma_tomato", "roma tomato", "weight", "lb", "produce", 1.20),
    ("pineapple", "pineapple", "count", "each", "produce", 2.60),
    ("radish", "radish", "weight", "lb", "produce", 1.10),
    ("cabbage", "green cabbage", "weight", "lb", "produce", 0.70),
    ("nopales", "nopales cactus paddles cleaned", "weight", "lb", "produce", 2.40),
    ("masa_harina", "corn masa flour", "weight", "lb", "dry", 0.85),
    ("guajillo", "guajillo chile dried", "weight", "lb", "dry", 7.50),
    ("pinto_beans", "pinto beans dried", "weight", "lb", "dry", 1.05),
    ("rice", "long grain rice", "weight", "lb", "dry", 0.75),
    ("salt", "kosher salt", "weight", "lb", "dry", 0.60),
    ("canola_oil", "canola oil", "volume", "qt", "dry", 2.10),
    ("cumin", "ground cumin", "weight", "lb", "dry", 6.80),
    ("sugar", "cane sugar", "weight", "lb", "dry", 0.70),
    ("hibiscus", "hibiscus flowers dried", "weight", "lb", "dry", 9.50),
    ("cinnamon", "cinnamon sticks", "weight", "lb", "dry", 11.00),
    ("tortilla_chips", "tortilla chips", "weight", "lb", "dry", 2.30),
    ("foil_sheet", "foil sheets 12 x 14", "count", "each", "paper", 0.03),
    ("clamshell", "clamshell 8 x 8", "count", "each", "paper", 0.22),
    ("cup_16oz", "cup 16 oz", "count", "each", "paper", 0.09),
]

CATALOG_BY_ID = {row[0]: row for row in CATALOG}

# Group order guides as exported from each distributor at onboarding.
# vendor, vendor code, description (distributor style), pack, case price, truth item_id ("" = not in catalog)
# The truth column never reaches the mapper; the eval uses it to grade.
ORDER_GUIDE = [
    # Sysco: mostly plain abbreviations that the rules can read
    ("Sysco", "SY-1023467", "CHICKEN THIGH BNLS SKLS", "4/10 LB", 124.00, "chicken_thigh"),
    ("Sysco", "SY-1188021", "BEEF SKIRT STEAK OUTSIDE", "2/12 LB", 235.20, "beef_skirt"),
    ("Sysco", "SY-1004418", "PORK SHOULDER BNLS", "2/9 LB", 61.20, "pork_shoulder"),
    ("Sysco", "SY-4410552", "ONION WHITE JUMBO", "1/50 LB", 47.50, "white_onion"),
    ("Sysco", "SY-4402217", "TOMATO ROMA", "1/25 LB", 30.00, "roma_tomato"),
    ("Sysco", "SY-4419930", "CABBAGE GREEN", "1/50 LB", 35.00, "cabbage"),
    ("Sysco", "SY-5501190", "SALT KOSHER", "12/3 LB", 21.60, "salt"),
    ("Sysco", "SY-5520771", "OIL CANOLA", "6/1 GAL", 50.40, "canola_oil"),
    ("Sysco", "SY-5533109", "RICE LONG GRAIN", "1/50 LB", 37.50, "rice"),
    ("Sysco", "SY-5540218", "SUGAR CANE", "1/25 LB", 17.50, "sugar"),
    ("Sysco", "SY-7710245", "FOIL SHEETS 12 X 14", "1/500 CT", 15.00, "foil_sheet"),
    ("Sysco", "SY-7713360", "CLAMSHELL 8 X 8", "1/200 CT", 44.00, "clamshell"),
    ("Sysco", "SY-7715802", "CUP 16 OZ", "1/1000 CT", 90.00, "cup_16oz"),
    ("Sysco", "SY-1023901", "CHKN BRST BNLS SKLS", "4/10 LB", 132.00, ""),  # breast, not thigh: not stocked
    ("Sysco", "SY-4415506", "PEPPER JALAP GRN FRSH", "1/10 LB", 14.00, "jalapeno"),
    ("Sysco", "SY-5547710", "CHILE GUAJ DRD WHL", "6/1 LB", 45.00, "guajillo"),
    ("Sysco", "SY-5549902", "SPICE CUMIN GRND", "1/5 LB", 34.00, "cumin"),
    # US Foods: comma style
    ("US Foods", "US-2207718", "CHEESE, OAXACA QUESILLO STRING", "6/5 LB", 168.00, "oaxaca_cheese"),
    ("US Foods", "US-2209301", "CHEESE, COTIJA CRUMBLED", "4/5 LB", 124.00, "cotija"),
    ("US Foods", "US-2211150", "CRMA MEXICANA", "6/32 OZ", 28.80, "crema"),
    ("US Foods", "US-3307714", "AVOCADO, HASS 48 CT", "1/48 CT", 60.00, "avocado"),
    ("US Foods", "US-3309920", "LIME, PERSIAN 110 CT", "1/40 LB", 52.00, "lime"),
    ("US Foods", "US-3311208", "CILANTRO", "1/60 BU", 33.00, "cilantro"),
    ("US Foods", "US-3312415", "RADISH, RED", "1/25 LB", 27.50, "radish"),
    ("US Foods", "US-3313702", "PINEAPPLE, GOLD 7 CT", "1/7 CT", 18.20, "pineapple"),
    ("US Foods", "US-6604412", "SHRIMP, P&D TAIL OFF 21-25", "5/2 LB", 89.00, "shrimp"),
    ("US Foods", "US-6608830", "CACTUS LEAVES, CLEANED DICED", "4/5 LB", 48.00, "nopales"),
    ("US Foods", "US-8801273", "CHEESE, MOZZARELLA SHREDDED", "4/5 LB", 72.00, ""),  # not on the menu
    # Restaurant Depot: brand names and Spanish names the rules cannot read
    ("Restaurant Depot", "RD-58812", "MASECA INSTANT MASA", "1/50 LB", 42.50, "masa_harina"),
    ("Restaurant Depot", "RD-60177", "FLOR DE JAMAICA", "1/5 LB", 47.50, "hibiscus"),
    ("Restaurant Depot", "RD-60433", "CANELA ENTERA", "1/1 LB", 11.00, "cinnamon"),
    ("Restaurant Depot", "RD-61290", "FRIJOL PINTO", "1/25 LB", 26.25, "pinto_beans"),
    ("Restaurant Depot", "RD-62041", "LIMONES 200CT", "1/200 CT", 48.00, "lime"),  # sold by count, catalog is by weight
    ("Restaurant Depot", "RD-63305", "TOTOPOS RESTAURANT STYLE", "1/10 LB", 23.00, "tortilla_chips"),
    ("Restaurant Depot", "RD-64480", "AGUACATE HASS 60CT", "1/60 CT", 72.00, "avocado"),
    ("Restaurant Depot", "RD-65502", "PULPO COCIDO", "1/4 LB", 58.00, ""),  # octopus: not in the catalog yet
]

# Menu item, menu group
MENU = [
    ("Carne Asada Taco", "Tacos"),
    ("Pollo Asado Taco", "Tacos"),
    ("Adobada Taco", "Tacos"),
    ("Nopal Taco", "Tacos"),
    ("Shrimp Taco", "Tacos"),
    ("Quesadilla", "Plates"),
    ("Guacamole and Chips", "Sides"),
    ("Agua de Jamaica", "Drinks"),
    ("Horchata", "Drinks"),
]

# Recipes in catalog base units per menu item sold. Tortillas are pressed in house from masa.
RECIPES = {
    "Carne Asada Taco": {
        "beef_skirt": 0.20,
        "masa_harina": 0.07,
        "white_onion": 0.02,
        "cilantro": 0.02,
        "lime": 0.03,
        "foil_sheet": 1,
    },
    "Pollo Asado Taco": {
        "chicken_thigh": 0.20,
        "masa_harina": 0.07,
        "white_onion": 0.02,
        "cilantro": 0.02,
        "lime": 0.03,
        "foil_sheet": 1,
    },
    "Adobada Taco": {
        "pork_shoulder": 0.22,
        "guajillo": 0.008,
        "pineapple": 0.04,
        "masa_harina": 0.07,
        "cumin": 0.002,
        "foil_sheet": 1,
    },
    "Nopal Taco": {"nopales": 0.16, "oaxaca_cheese": 0.05, "masa_harina": 0.07, "roma_tomato": 0.03, "foil_sheet": 1},
    "Shrimp Taco": {"shrimp": 0.14, "cabbage": 0.04, "crema": 0.02, "masa_harina": 0.07, "lime": 0.03, "foil_sheet": 1},
    "Quesadilla": {"oaxaca_cheese": 0.18, "masa_harina": 0.12, "jalapeno": 0.02, "clamshell": 1},
    "Guacamole and Chips": {"avocado": 1.5, "white_onion": 0.03, "jalapeno": 0.02, "lime": 0.05, "tortilla_chips": 0.25, "clamshell": 1},
    "Agua de Jamaica": {"hibiscus": 0.02, "sugar": 0.08, "cup_16oz": 1},
    "Horchata": {"rice": 0.06, "cinnamon": 0.003, "sugar": 0.08, "cup_16oz": 1},
}

# Items the kitchen counts and orders against a par (everything in recipes plus salt, oil, beans, radish, cotija).
EXTRA_PAR_ITEMS = ["salt", "canola_oil", "pinto_beans", "radish", "cotija", "lime"]

# location_id, neighborhood-style name (invented), daily volume factor, preferred vendor for produce
LOCATIONS = [
    ("L01", "Westside", 1.20),
    ("L02", "Harbor", 1.05),
    ("L03", "Midtown East", 0.95),
    ("L04", "Northgate", 0.90),
    ("L05", "Canal", 1.10),
    ("L06", "Riverside", 0.85),
    ("L07", "Union", 1.00),
    ("L08", "Park Row", 0.80),
    ("L09", "Eastbank", 0.75),
    ("L10", "Hillcrest", 0.70),
]
PILOT_WAVE = {"L01": 1, "L02": 1, "L03": 1}  # the rest are wave 2

# Base daily units sold per menu item at a 1.0 location
BASE_DAILY = {
    "Carne Asada Taco": 180,
    "Pollo Asado Taco": 150,
    "Adobada Taco": 160,
    "Nopal Taco": 45,
    "Shrimp Taco": 40,
    "Quesadilla": 55,
    "Guacamole and Chips": 50,
    "Agua de Jamaica": 70,
    "Horchata": 85,
}
