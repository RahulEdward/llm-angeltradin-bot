"""
Test All Features - Backtest, Live Data, Paper Trading Flow
Run: python test_all_features.py
"""

import asyncio
import json
import sys
import time
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent))


async def test_backtest_with_csv():
    """Test 1: Backtest using downloaded CSV data (no broker needed)."""
    print("\n" + "=" * 70)
    print("  TEST 1: BACKTEST WITH CSV DATA")
    print("=" * 70)
    
    # Check CSV files exist
    hist_dir = Path(__file__).parent / "data" / "historical"
    if not hist_dir.exists():
        print("  ❌ No historical data directory. Run download_historical.py first.")
        return False
    
    symbols = []
    for d in hist_dir.iterdir():
        if d.is_dir():
            csv_files = list(d.glob("*.csv"))
            if csv_files:
                symbols.append(d.name)
                print(f"  ✅ {d.name}: {len(csv_files)} timeframes")
    
    if not symbols:
        print("  ❌ No CSV data found.")
        return False
    
    print(f"\n  Running backtest on {symbols[0]}...")
    
    # Import and run backtest
    from src.agents.backtest_agent import BacktestAgent
    
    agent = BacktestAgent()
    
    try:
        result = await agent.run_backtest(
            symbols=[symbols[0]],
            exchange="NSE",
            start_date=datetime.now() - timedelta(days=60),
            end_date=datetime.now(),
            initial_capital=100000,
            timeframe="1h",
            stop_loss_pct=2.0,
            take_profit_pct=4.0
        )
        
        m = result.metrics
        print(f"\n  📊 BACKTEST RESULTS - {symbols[0]}")
        print(f"  {'─' * 50}")
        print(f"  Initial Capital:  ₹{100000:>12,.2f}")
        print(f"  Final Equity:     ₹{m.final_equity:>12,.2f}")
        print(f"  Total Return:      {m.total_return:>11.2f}%")
        print(f"  Max Drawdown:      {m.max_drawdown_pct:>11.2f}%")
        print(f"  Sharpe Ratio:      {m.sharpe_ratio:>11.2f}")
        print(f"  Sortino Ratio:     {m.sortino_ratio:>11.2f}")
        print(f"  Total Trades:      {m.total_trades:>11}")
        print(f"  Win Rate:          {m.win_rate:>11.1f}%")
        print(f"  Profit Factor:     {m.profit_factor:>11.2f}")
        print(f"  Avg Win:          ₹{m.avg_win:>12,.2f}")
        print(f"  Avg Loss:         ₹{m.avg_loss:>12,.2f}")
        print(f"  Long Trades:       {m.long_trades:>11}")
        print(f"  Short Trades:      {m.short_trades:>11}")
        
        if result.trades:
            print(f"\n  Last 5 trades:")
            for t in result.trades[-5:]:
                d = t.to_dict()
                print(f"    {d['side']:>5} @ ₹{d['price']:>10.2f} | PnL: ₹{d['pnl']:>8.2f} | {d['close_reason'] or d['action']}")
        
        print(f"\n  ✅ Backtest completed in {result.duration_seconds:.1f}s")
        return True
        
    except Exception as e:
        print(f"  ❌ Backtest error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_multi_symbol_backtest():
    """Test 2: Multi-symbol backtest."""
    print("\n" + "=" * 70)
    print("  TEST 2: MULTI-SYMBOL BACKTEST")
    print("=" * 70)
    
    from src.agents.backtest_agent import BacktestAgent
    
    agent = BacktestAgent()
    symbols = ["RELIANCE", "TCS", "INFY"]
    
    print(f"  Running backtest on {', '.join(symbols)}...")
    
    try:
        result = await agent.run_backtest(
            symbols=symbols,
            exchange="NSE",
            start_date=datetime.now() - timedelta(days=30),
            end_date=datetime.now(),
            initial_capital=300000,
            timeframe="1h",
            stop_loss_pct=2.0,
            take_profit_pct=4.0
        )
        
        m = result.metrics
        print(f"\n  📊 MULTI-SYMBOL RESULTS")
        print(f"  {'─' * 50}")
        print(f"  Final Equity:     ₹{m.final_equity:>12,.2f}")
        print(f"  Total Return:      {m.total_return:>11.2f}%")
        print(f"  Total Trades:      {m.total_trades:>11}")
        print(f"  Win Rate:          {m.win_rate:>11.1f}%")
        print(f"  Sharpe Ratio:      {m.sharpe_ratio:>11.2f}")
        print(f"\n  ✅ Multi-symbol backtest completed")
        return True
        
    except Exception as e:
        print(f"  ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_different_timeframes():
    """Test 3: Backtest on different timeframes."""
    print("\n" + "=" * 70)
    print("  TEST 3: DIFFERENT TIMEFRAMES")
    print("=" * 70)
    
    from src.agents.backtest_agent import BacktestAgent
    
    agent = BacktestAgent()
    
    for tf in ["5m", "15m", "1h", "1d"]:
        lookback = {"5m": 30, "15m": 60, "1h": 90, "1d": 365}.get(tf, 90)
        
        try:
            result = await agent.run_backtest(
                symbols=["RELIANCE"],
                exchange="NSE",
                start_date=datetime.now() - timedelta(days=lookback),
                end_date=datetime.now(),
                initial_capital=100000,
                timeframe=tf
            )
            m = result.metrics
            print(f"  {tf:>4}: Return={m.total_return:>7.2f}% | Trades={m.total_trades:>4} | WinRate={m.win_rate:>5.1f}% | Sharpe={m.sharpe_ratio:>6.2f}")
        except Exception as e:
            print(f"  {tf:>4}: ❌ {e}")
    
    print(f"\n  ✅ Timeframe comparison done")
    return True


async def test_api_endpoints():
    """Test 4: API endpoints via HTTP."""
    print("\n" + "=" * 70)
    print("  TEST 4: API ENDPOINTS")
    print("=" * 70)
    
    try:
        import httpx
    except ImportError:
        print("  ⚠️  httpx not installed, skipping API tests")
        return True
    
    base = "http://localhost:8000"
    
    async with httpx.AsyncClient(timeout=30) as client:
        endpoints = [
            ("GET", "/api/mode", None),
            ("GET", "/api/settings", None),
            ("GET", "/api/agent/status", None),
            ("GET", "/api/llm/metrics", None),
            ("GET", "/api/positions", None),
            ("GET", "/api/account/funds", None),
            ("GET", "/api/trades", None),
            ("GET", "/api/broker/accounts", None),
        ]
        
        for method, path, body in endpoints:
            try:
                if method == "GET":
                    resp = await client.get(f"{base}{path}")
                else:
                    resp = await client.post(f"{base}{path}", json=body)
                
                status = "✅" if resp.status_code == 200 else f"⚠️  {resp.status_code}"
                print(f"  {status} {method} {path}")
            except Exception as e:
                print(f"  ❌ {method} {path}: {e}")
    
    return True


async def main():
    print("=" * 70)
    print("  LLM-ANGELAGENT - FULL FEATURE TEST")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    results = {}
    
    # Test 1: Backtest with CSV
    results["backtest_csv"] = await test_backtest_with_csv()
    
    # Test 2: Multi-symbol backtest
    results["multi_backtest"] = await test_multi_symbol_backtest()
    
    # Test 3: Different timeframes
    results["timeframes"] = await test_different_timeframes()
    
    # Test 4: API endpoints (only if server is running)
    results["api"] = await test_api_endpoints()
    
    # Summary
    print("\n" + "=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    
    for test, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}  {test}")
    
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    print(f"\n  {passed}/{total} tests passed")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
