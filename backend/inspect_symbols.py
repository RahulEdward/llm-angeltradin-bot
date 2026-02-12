import requests
import json

url = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
print(f"Fetching sample from {url}...")
r = requests.get(url, timeout=60)
data = r.json()
print(f"Total items: {len(data)}")
print("First 2 items:")
print(json.dumps(data[:2], indent=2))

# Check unique exchange segments and instrument types
exchanges = set()
types = set()
for item in data[:5000]: # Check first 5000
    exchanges.add(item.get("exch_seg"))
    types.add(item.get("instrumenttype"))

print(f"\nUnique Exchanges (sample): {exchanges}")
print(f"Unique Instrument Types (sample): {types}")
