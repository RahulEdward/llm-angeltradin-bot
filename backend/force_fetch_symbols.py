import asyncio
import json
import os
import time
from pathlib import Path
import requests

async def fetch_symbols():
    try:
        instruments_url = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
        print(f"Fetching symbols from {instruments_url}...")
        
        response = requests.get(instruments_url, timeout=120)
        
        if response.ok:
            instruments = response.json()
            print(f"Downloaded {len(instruments)} instruments. Filtering NSE/BSE...")

            # Filter NSE + BSE equity symbols
            # Inspection showed instrumenttype is "" for equity
            equity_symbols = [
                {
                    "token": inst["token"],
                    "symbol": inst["symbol"],
                    "name": inst.get("name", inst["symbol"]),
                    "exchange": inst["exch_seg"],
                    "lotsize": inst.get("lotsize", "1"),
                    "tick_size": inst.get("tick_size", "0.05")
                }
                for inst in instruments
                if inst.get("exch_seg") in ("NSE", "BSE") and inst.get("instrumenttype") == ""
            ]

            if equity_symbols:
                symbols_file = Path("data/symbols.json")
                symbols_file.parent.mkdir(parents=True, exist_ok=True)
                symbols_file.write_text(json.dumps(equity_symbols, indent=2))
                print(f"Fetched and saved {len(equity_symbols)} NSE+BSE equity symbols to {symbols_file}")
            else:
                print("No equity symbols found in ScripMaster data")
        else:
            print(f"Symbol fetch HTTP error: {response.status_code}")
            
    except Exception as e:
        print(f"Symbol fetch failed: {e}")

if __name__ == "__main__":
    asyncio.run(fetch_symbols())
