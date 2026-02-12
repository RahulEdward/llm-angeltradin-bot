import requests
import json

url = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
print("Fetching...")
data = requests.get(url).json()

types = set()
segments = set()
eq_sample = None

for item in data:
    t = item.get("instrumenttype")
    s = item.get("exch_seg")
    types.add(t)
    segments.add(s)
    if t == "EQ" and not eq_sample:
        eq_sample = item

print(f"Unique Types: {types}")
print(f"Unique Segments: {segments}")
print(f"\nSample EQ item: {json.dumps(eq_sample, indent=2)}")
