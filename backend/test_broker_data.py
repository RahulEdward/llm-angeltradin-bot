"""
Test script to verify broker connection and live data fetching.
Run: python test_broker_data.py
"""

import asyncio
from src.broker import BrokerFactory, AngelOneBroker
from src.config.settings import settings

async def test_broker():
    print("=" * 60)
    print("BROKER CONNECTION TEST")
    print("=" * 60)
    
    # Check if broker is connected
    broker = BrokerFactory.get_connected_broker()
    
    if not broker:
        print("\n❌ NO BROKER CONNECTED")
        print("   Go to Settings → Enter Angel One credentials → Connect")
        print("   Paper trading and Live trading both require broker connection")
        print("   for real market data.")
        return
    
    print(f"\n✅ Broker connected: {type(broker).__name__}")
    
    # Test connection
    try:
        is_connected = await broker.is_connected()
        print(f"   Connection status: {'Connected' if is_connected else 'Disconnected'}")
    except Exception as e:
        print(f"   Connection check error: {e}")
        return
    
    # Test quote fetch
    print("\n" + "-" * 60)
    print("TESTING LIVE QUOTE FETCH")
    print("-" * 60)
    
    symbols = ["RELIANCE", "TCS", "INFY"]
    
    for symbol in symbols:
        try:
            quote = await broker.get_quote(symbol, "NSE")
            if quote:
                print(f"\n✅ {symbol}:")
                print(f"   LTP: ₹{quote.ltp:.2f}")
                print(f"   Open: ₹{quote.open:.2f}")
                print(f"   High: ₹{quote.high:.2f}")
                print(f"   Low: ₹{quote.low:.2f}")
                print(f"   Volume: {quote.volume:,}")
            else:
                print(f"\n⚠️ {symbol}: No quote data received")
        except Exception as e:
            print(f"\n❌ {symbol}: Error - {e}")
    
    # Test historical data
    print("\n" + "-" * 60)
    print("TESTING HISTORICAL DATA FETCH")
    print("-" * 60)
    
    from datetime import datetime, timedelta
    
    try:
        candles = await broker.get_historical_data(
            symbol="RELIANCE",
            exchange="NSE",
            interval="5m",
            from_date=datetime.now() - timedelta(days=5),
            to_date=datetime.now()
        )
        
        if candles:
            print(f"\n✅ RELIANCE 5m candles: {len(candles)} bars")
            print(f"   First: {candles[0].timestamp} - O:{candles[0].open:.2f} H:{candles[0].high:.2f} L:{candles[0].low:.2f} C:{candles[0].close:.2f}")
            print(f"   Last:  {candles[-1].timestamp} - O:{candles[-1].open:.2f} H:{candles[-1].high:.2f} L:{candles[-1].low:.2f} C:{candles[-1].close:.2f}")
        else:
            print("\n⚠️ No historical data received")
    except Exception as e:
        print(f"\n❌ Historical data error: {e}")
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_broker())
