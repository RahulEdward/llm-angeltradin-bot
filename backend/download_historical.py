"""
Download Historical Data from Angel One - Multiple timeframes, saved as CSV.
Run: python download_historical.py

Creates: backend/data/historical/<SYMBOL>/<SYMBOL>_<timeframe>.csv
"""

import asyncio
import json
import sys
import time
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent))

from cryptography.fernet import Fernet

DATA_DIR = Path(__file__).parent / "data"
HIST_DIR = DATA_DIR / "historical"
ENCRYPTION_KEY_FILE = DATA_DIR / ".encryption_key"
BROKER_FILE = DATA_DIR / "broker_accounts.json"

def decrypt(val):
    key = ENCRYPTION_KEY_FILE.read_bytes()
    return Fernet(key).decrypt(val.encode()).decode()

def load_accounts():
    if not BROKER_FILE.exists():
        return []
    return json.loads(BROKER_FILE.read_text())

def load_nse_token(symbol):
    """Get NSE token for a symbol."""
    sf = DATA_DIR / "symbols.json"
    if not sf.exists():
        return None, None
    data = json.loads(sf.read_text(encoding="utf-8"))
    for entry in data:
        if entry.get("name") == symbol and entry.get("exchange") == "NSE":
            return entry.get("token", ""), entry.get("symbol", "")
    return None, None

# Angel One interval names
INTERVAL_MAP = {
    "1m":  "ONE_MINUTE",
    "3m":  "THREE_MINUTE",
    "5m":  "FIVE_MINUTE",
    "10m": "TEN_MINUTE",
    "15m": "FIFTEEN_MINUTE",
    "30m": "THIRTY_MINUTE",
    "1h":  "ONE_HOUR",
    "1d":  "ONE_DAY",
}

# Max lookback per timeframe (Angel One limits)
LOOKBACK_DAYS = {
    "1m":  30,
    "3m":  90,
    "5m":  90,
    "10m": 90,
    "15m": 180,
    "30m": 180,
    "1h":  365,
    "1d":  730,
}

SYMBOLS = ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK",
           "SBIN", "WIPRO", "BAJFINANCE", "LT", "TATASTEEL"]

TIMEFRAMES = ["5m", "15m", "1h", "1d"]

MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds


def fetch_with_retry(smart_api, params, retries=MAX_RETRIES):
    """Fetch candle data with retry on rate limit."""
    for attempt in range(retries):
        try:
            resp = smart_api.getCandleData(params)
            if resp and resp.get("status") and resp.get("data"):
                return resp
            # Rate limited or error - wait and retry
            msg = resp.get("message", "") if resp else ""
            if "Something Went Wrong" in msg or "AB1004" in str(resp):
                if attempt < retries - 1:
                    wait = RETRY_DELAY * (attempt + 1)
                    print(f"⏳ Rate limited, waiting {wait}s...", end=" ", flush=True)
                    time.sleep(wait)
                    continue
            return resp  # Non-retryable error
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(RETRY_DELAY)
                continue
            raise e
    return None


async def main():
    accounts = load_accounts()
    if not accounts:
        print("❌ No broker accounts saved.")
        return

    acc = accounts[0]
    client_id = acc["client_id"]
    api_key = decrypt(acc["api_key_encrypted"])
    pin = decrypt(acc["pin_encrypted"])

    print("=" * 70)
    print("  ANGEL ONE HISTORICAL DATA DOWNLOADER")
    print("=" * 70)

    totp = input("\nEnter TOTP code (6-digit): ").strip()
    if len(totp) != 6:
        print("❌ Invalid TOTP")
        return

    try:
        from SmartApi import SmartConnect
    except ImportError:
        print("❌ pip install smartapi-python")
        return

    print("\n⏳ Connecting...")
    smart_api = SmartConnect(api_key=api_key)

    try:
        session = smart_api.generateSession(clientCode=client_id, password=pin, totp=totp)
    except Exception as e:
        print(f"❌ {e}")
        return

    if not session.get("status"):
        print(f"❌ {session.get('message')}")
        return

    print(f"✅ Connected - {client_id}\n")

    # Create output directory
    HIST_DIR.mkdir(parents=True, exist_ok=True)

    total_files = 0
    total_rows = 0

    for symbol in SYMBOLS:
        token, trading_sym = load_nse_token(symbol)
        if not token:
            print(f"⚠️  {symbol}: No NSE token found, skipping")
            continue

        # Create symbol directory
        sym_dir = HIST_DIR / symbol
        sym_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n{'─' * 70}")
        print(f"  📊 {symbol} (token={token}, {trading_sym})")
        print(f"{'─' * 70}")

        for tf in TIMEFRAMES:
            angel_interval = INTERVAL_MAP.get(tf)
            lookback = LOOKBACK_DAYS.get(tf, 90)

            to_date = datetime.now()
            from_date = to_date - timedelta(days=lookback)

            print(f"  ⏳ {tf:>4} | {from_date.strftime('%Y-%m-%d')} → {to_date.strftime('%Y-%m-%d')} ({lookback} days)...", end=" ")

            try:
                params = {
                    "exchange": "NSE",
                    "symboltoken": token,
                    "interval": angel_interval,
                    "fromdate": from_date.strftime("%Y-%m-%d 09:15"),
                    "todate": to_date.strftime("%Y-%m-%d 15:30"),
                }

                resp = fetch_with_retry(smart_api, params)

                if not resp or not resp.get("status") or not resp.get("data"):
                    msg = resp.get("message", "No data") if resp else "No response"
                    print(f"❌ {msg}")
                    continue

                rows = resp["data"]

                # Write CSV
                csv_path = sym_dir / f"{symbol}_{tf}.csv"
                with open(csv_path, "w") as f:
                    f.write("timestamp,open,high,low,close,volume\n")
                    for row in rows:
                        ts = row[0]
                        o, h, l, c, v = row[1], row[2], row[3], row[4], row[5]
                        f.write(f"{ts},{o},{h},{l},{c},{v}\n")

                total_files += 1
                total_rows += len(rows)
                print(f"✅ {len(rows):>6} candles → {csv_path.name}")

            except Exception as e:
                print(f"❌ {e}")

            # Rate limit - 2s between requests to avoid Angel One throttling
            time.sleep(2)

    # Logout
    try:
        smart_api.terminateSession(client_id)
    except:
        pass

    print(f"\n{'=' * 70}")
    print(f"  ✅ DOWNLOAD COMPLETE")
    print(f"  📁 Directory: {HIST_DIR}")
    print(f"  📄 Files: {total_files}")
    print(f"  📊 Total candles: {total_rows:,}")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    asyncio.run(main())
