import requests
import json

url = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
print("Fetching...")
data = requests.get(url).json()

reliance = None
for item in data:
    if item['symbol'] == 'RELIANCE-EQ' or item['symbol'] == 'RELIANCE':
        print("\nFOUND RELIANCE:", json.dumps(item, indent=2))
        reliance = item
        break
    if item['name'] == 'RELIANCE INDUSTRIES': # Sometimes name is different
        print("\nFOUND RELIANCE NAME:", json.dumps(item, indent=2))
        break

if not reliance:
    print("Reliance not found!")
