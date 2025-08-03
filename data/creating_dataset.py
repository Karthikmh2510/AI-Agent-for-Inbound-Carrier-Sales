import pandas as pd
from datetime import datetime, timedelta
import random, string, json, os, textwrap

# Helper functions
def random_id():
    return "L" + ''.join(random.choices(string.digits, k=4))

cities = [
    ("Chicago", "IL"), ("Atlanta", "GA"), ("Dallas", "TX"), ("Los Angeles", "CA"),
    ("Denver", "CO"), ("Phoenix", "AZ"), ("Memphis", "TN"), ("Seattle", "WA"),
    ("Columbus", "OH"), ("Newark", "NJ"), ("Miami", "FL"), ("Boston", "MA"),
    ("Minneapolis", "MN"), ("Kansas City", "MO"), ("Salt Lake City", "UT"),
    ("Portland", "OR"), ("Charlotte", "NC"), ("Houston", "TX"), ("Orlando", "FL"),
    ("Pittsburgh", "PA"), ("Richmond", "VA"), ("San Diego", "CA"), ("Detroit", "MI"),
    ("Nashville", "TN"), ("Tampa", "FL"), ("Indianapolis", "IN"), ("St. Louis", "MO"),
    ("Raleigh", "NC"), ("Baltimore", "MD"), ("Las Vegas", "NV")
]

equipment_types = ["Van", "Reefer", "Flatbed", "Stepdeck", "PowerOnly"]
commodity_types = ["General Goods", "Frozen Food", "Steel Coils", "Electronics", "Produce", "Furniture", "Paper Products"]

rows = []
base_date = datetime(2025, 8, 3, 8, 0)

for i in range(30):
    origin = random.choice(cities)
    dest = random.choice([c for c in cities if c != origin])
    pickup = base_date + timedelta(hours=random.randint(0, 96))
    delivery = pickup + timedelta(hours=random.randint(18, 48))
    eq = random.choice(equipment_types)
    rate = random.randint(1500, 4000)
    notes = random.choice(["", "No hazmat", "Keep at 38°F", "Tarps required", "High value—call before delivery"])
    weight = random.randint(15000, 45000)
    commodity = random.choice(commodity_types)
    num_pieces = random.randint(5, 40)
    miles = random.randint(300, 2000)
    dims = random.choice(["48x102x96", "53x102x110", "45x96x90", "40x100x100"])
    
    row = {
        "load_id": random_id(),
        "origin": f"{origin[0]},{origin[1]}",
        "destination": f"{dest[0]},{dest[1]}",
        "pickup_datetime": pickup.isoformat(timespec='minutes'),
        "delivery_datetime": delivery.isoformat(timespec='minutes'),
        "equipment_type": eq,
        "loadboard_rate": rate,
        "notes": notes,
        "weight": weight,
        "commodity_type": commodity,
        "num_of_pieces": num_pieces,
        "miles": miles,
        "dimensions": dims
    }
    rows.append(row)

df = pd.DataFrame(rows)

# Save CSV
csv_path = "data/loads.csv"
df.to_csv(csv_path, index=False)

# Save JSON
json_path = "data/loads.json"
df.to_json(json_path, orient='records')



