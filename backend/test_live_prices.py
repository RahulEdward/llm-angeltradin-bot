"""
Live Price Test - Connects to Angel One and shows real-time prices.
Run: python test_live_prices.py
"""

import asyncio
import json
import sys
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from cryptography.fernet import Fernet

DATA_DIR = Path(__file__).parent / "data"
ENCRYPTION_KEY_FILE = DATA_DIR / ".encryption_key"
BROKER_FILE = DATA_DIR / "broker_accounts.json"

def get_key():
    return ENCRYPTION_KEY_FILE.read_bytes()

def decrypt(val):
    return Fernet(get_key()).decrypt(val.encode()).decode()

def load_accounts():
    if not BROKER_FILE.exists():
        return []
    return json.loads(BROKER_FILE.read_text())

def load_nse_symbol_map():
    """Load symbol -> token mapping for NSE only."""
    symbols_file = DATA_DIR / "symbols.json"
    if not symbols_file.exists():
        return {}
    
    data = json.loads(symbols_file.read_text(encoding="utf-8"))
    nse_map = {}
    for entry in data:
        if entry.get("exchange") == "NSE":
            name = entry.get("name", "")
            token = entry.get("token", "")
            trading_sym = entry.get("symbol", "")  # e.g. RELIANCE-EQ
            if name and token:
                nse_map[name] = {"token": token, "trading_symbol": trading_sym}
    return nse_map


async def main():
    accounts = load_accounts()
    if not accounts:
        print("❌ No broker accounts saved. Save Angel One credentials in Settings first.")
        return

    acc = accounts[0]
    client_id = acc["client_id"]
    api_key = decrypt(acc["api_key_encrypted"])
    pin = decrypt(acc["pin_encrypted"])

    print("=" * 70)
    print(f"  ANGEL ONE LIVE PRICE FEED - Client: {client_id}")
    print("=" * 70)

    totp_input = input("\nEnter TOTP code (6-digit): ").strip()
    if not totp_input or len(totp_input) != 6:
        print("❌ Invalid TOTP. Must be 6 digits.")
        return

    try:
        from SmartApi import SmartConnect
    except ImportError:
        print("❌ SmartApi not installed. Run: pip install smartapi-python")
        return

    print("\n⏳ Connecting to Angel One...")
    smart_api = SmartConnect(api_key=api_key)

    try:
        session = smart_api.generateSession(
            clientCode=client_id, password=pin, totp=totp_input
        )
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return

    if not session.get("status"):
        print(f"❌ Login failed: {session.get('message', 'Unknown error')}")
        return

    print(f"✅ Connected to Angel One - {client_id}\n")

    # Load NSE symbol map
    nse_map = load_nse_symbol_map()
    
    watch_symbols = ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK",
                     "SBIN", "WIPRO", "BAJFINANCE", "LT", "TATAMOTORS"]

    # Resolve NSE tokens
    resolved = {}
    for sym in watch_symbols:
        info = nse_map.get(sym)
        if info:
            resolved[sym] = info
            print(f"  ✅ {sym:<15} token={info['token']:<8} ({info['trading_symbol']})")
        else:
            print(f"  ⚠️  {sym:<15} NOT FOUND in symbols.json")

    if not resolved:
        print("\n❌ No NSE symbols resolved. Run the app and fetch symbols first.")
        return

    print(f"\n📊 Resolved {len(resolved)}/{len(watch_symbols)} NSE symbols\n")
    print("─" * 70)
    print(f"  {'Symbol':<15} {'LTP':>10} {'Open':>10} {'High':>10} {'Low':>10}")
    print("─" * 70)

    cycle = 0
    try:
        while True:
            cycle += 1
            now = datetime.now().strftime("%H:%M:%S")
            print(f"\n  ━━━ Cycle #{cycle} | {now} ━━━")

            for sym, info in resolved.items():
                try:
                    resp = smart_api.ltpData("NSE", info["trading_symbol"], info["token"])

                    if resp and resp.get("status") and resp.get("data"):
                        d = resp["data"]
                        ltp = float(d.get("ltp", 0))
                        opn = float(d.get("open", 0))
                        high = float(d.get("high", 0))
                        low = float(d.get("low", 0))
                        print(f"  {sym:<15} ₹{ltp:>9.2f} ₹{opn:>9.2f} ₹{high:>9.2f} ₹{low:>9.2f}")
                    else:
                        msg = resp.get("message", "No data") if resp else "No response"
                        print(f"  {sym:<15} -- {msg}")
                except Exception as e:
                    print(f"  {sym:<15} ❌ {e}")

            print(f"\n  Next refresh in 10s... (Ctrl+C to stop)")
            time.sleep(10)

    except KeyboardInterrupt:
        print("\n\n🛑 Stopped")

    try:
        smart_api.terminateSession(client_id)
        print("✅ Disconnected")
    except:
        pass


if __name__ == "__main__":
    asyncio.run(main())
