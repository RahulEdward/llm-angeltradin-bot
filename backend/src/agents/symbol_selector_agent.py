"""
Symbol Selector Agent - Adapted for Indian Markets (Angel One)
===============================================================

Selects trading symbols based on:
1. User-configured watchlist (primary mode)
2. Volume-based selection from NSE/BSE
3. Momentum-based filtering

Note: Disabled by default. In the Indian market context, users typically
select symbols via the UI rather than automated selection.
"""

import json
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
import threading
from loguru import logger


def calculate_adx(candles: List[Dict], period: int = 14) -> float:
    """
    Calculate ADX trend strength indicator.
    
    ADX > 25: Strong trend
    ADX 20-25: Trend forming
    ADX < 20: No trend / sideways
    """
    if len(candles) < period + 2:
        return 0.0
    
    try:
        highs = [float(k.get('high', 0)) for k in candles]
        lows = [float(k.get('low', 0)) for k in candles]
        closes = [float(k.get('close', 0)) for k in candles]
        
        tr_list, plus_dm_list, minus_dm_list = [], [], []
        for i in range(1, len(candles)):
            high_diff = highs[i] - highs[i-1]
            low_diff = lows[i-1] - lows[i]
            
            tr = max(highs[i] - lows[i], 
                     abs(highs[i] - closes[i-1]), 
                     abs(lows[i] - closes[i-1]))
            
            plus_dm = high_diff if high_diff > low_diff and high_diff > 0 else 0
            minus_dm = low_diff if low_diff > high_diff and low_diff > 0 else 0
            
            tr_list.append(tr)
            plus_dm_list.append(plus_dm)
            minus_dm_list.append(minus_dm)
        
        if len(tr_list) < period:
            return 0.0
        
        def smooth(values, p):
            if len(values) < p:
                return []
            result = [sum(values[:p])]
            for v in values[p:]:
                result.append(result[-1] - result[-1]/p + v)
            return result
        
        atr = smooth(tr_list, period)
        if not atr:
            return 0.0
        
        s_plus_dm = smooth(plus_dm_list, period)
        s_minus_dm = smooth(minus_dm_list, period)
        
        if not s_plus_dm or not s_minus_dm:
            return 0.0
        
        plus_di = [(pdm / atr[i] * 100) if atr[i] > 0 else 0 
                   for i, pdm in enumerate(s_plus_dm)]
        minus_di = [(mdm / atr[i] * 100) if atr[i] > 0 else 0 
                    for i, mdm in enumerate(s_minus_dm)]
        
        dx = []
        for i in range(len(plus_di)):
            di_sum = plus_di[i] + minus_di[i]
            if di_sum > 0:
                dx.append(abs(plus_di[i] - minus_di[i]) / di_sum * 100)
            else:
                dx.append(0)
        
        if len(dx) >= period:
            adx = sum(dx[-period:]) / period
            return round(adx, 1)
        return 0.0
        
    except Exception:
        return 0.0


# Default Nifty 50 candidates for Indian markets
NIFTY50_CANDIDATES = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK",
    "HINDUNILVR", "ITC", "SBIN", "BHARTIARTL", "KOTAKBANK",
    "BAJFINANCE", "LICI", "LT", "HCLTECH", "ASIANPAINT",
    "AXISBANK", "MARUTI", "SUNPHARMA", "TITAN", "DMART",
    "ULTRACEMCO", "BAJAJFINSV", "WIPRO", "ONGC", "NTPC",
    "JSWSTEEL", "POWERGRID", "M&M", "ADANIENT", "TATAMOTORS",
    "TECHM", "TATASTEEL", "NESTLEIND", "INDUSINDBK", "COALINDIA",
    "HDFCLIFE", "BAJAJ-AUTO", "GRASIM", "CIPLA", "BRITANNIA",
    "DIVISLAB", "DRREDDY", "EICHERMOT", "SBILIFE", "APOLLOHOSP",
    "HEROMOTOCO", "TATACONSUM", "BPCL", "HINDALCO", "UPL"
]

FALLBACK_SYMBOLS = ["RELIANCE", "TCS", "HDFCBANK"]


class SymbolSelectorAgent:
    """
    Symbol Selector for Indian Markets (Angel One)
    
    Modes:
    1. Manual (default): User selects symbols via UI
    2. Auto: Uses momentum and volume to select from Nifty 50
    
    Note: This is disabled by default in AgentConfig.
    """
    
    def __init__(
        self,
        candidate_symbols: Optional[List[str]] = None,
        cache_dir: str = "config",
        refresh_interval_hours: int = 6
    ):
        self.candidates = candidate_symbols or NIFTY50_CANDIDATES
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / "auto_symbol_cache.json"
        self.refresh_interval = refresh_interval_hours
        
        self._refresh_thread: Optional[threading.Thread] = None
        self._stop_refresh = threading.Event()
        
        logger.info(f"🔝 SymbolSelectorAgent initialized with {len(self.candidates)} candidates")
    
    async def select_by_momentum(
        self,
        candidates: Optional[List[str]] = None,
        top_n: int = 3
    ) -> List[str]:
        """
        Select top symbols by recent price momentum.
        
        Uses Angel One market data to calculate momentum.
        Falls back to default candidates if broker unavailable.
        """
        symbols_to_scan = candidates or self.candidates
        
        try:
            from src.broker.factory import BrokerFactory
            broker = BrokerFactory.get_broker()
            
            results = []
            for symbol in symbols_to_scan[:20]:  # Limit API calls
                try:
                    quote = await asyncio.to_thread(broker.get_ltp, symbol)
                    if quote and quote.get('ltp'):
                        results.append({
                            'symbol': symbol,
                            'ltp': float(quote['ltp']),
                            'change_pct': float(quote.get('change_pct', 0)),
                        })
                except Exception as e:
                    logger.debug(f"Skip {symbol}: {e}")
            
            if not results:
                logger.warning("No momentum data available, using fallback symbols")
                return FALLBACK_SYMBOLS[:top_n]
            
            # Rank by absolute momentum
            results.sort(key=lambda x: abs(x['change_pct']), reverse=True)
            selected = [r['symbol'] for r in results[:top_n]]
            
            logger.info(f"🎯 Selected symbols by momentum: {selected}")
            return selected
            
        except Exception as e:
            logger.error(f"❌ Symbol selection failed: {e}")
            return FALLBACK_SYMBOLS[:top_n]
    
    def get_symbols(self, force_refresh: bool = False) -> List[str]:
        """
        Synchronous wrapper for symbol selection.
        
        For the Indian market context, this typically returns
        user-configured symbols from the UI/database.
        """
        # Check cache first
        if not force_refresh and self._is_cache_valid():
            cached = self._load_cache()
            symbols = cached.get('symbols', [])
            if symbols:
                logger.info(f"🔝 Using cached symbols: {symbols}")
                return symbols
        
        # Fallback to default
        return FALLBACK_SYMBOLS
    
    def _is_cache_valid(self) -> bool:
        if not self.cache_file.exists():
            return False
        try:
            cache = self._load_cache()
            valid_until = datetime.fromisoformat(cache["valid_until"])
            return datetime.now() < valid_until
        except Exception:
            return False
    
    def _load_cache(self) -> Dict:
        with open(self.cache_file, 'r') as f:
            return json.load(f)
    
    def _save_cache(self, symbols: List[str]):
        now = datetime.now()
        cache_data = {
            "timestamp": now.isoformat(),
            "valid_until": (now + timedelta(hours=self.refresh_interval)).isoformat(),
            "symbols": symbols
        }
        with open(self.cache_file, 'w') as f:
            json.dump(cache_data, f, indent=2)
        logger.info(f"💾 Symbol cache saved: valid until {cache_data['valid_until']}")
    
    def start_auto_refresh(self):
        """Start background thread for auto-refresh."""
        if self._refresh_thread and self._refresh_thread.is_alive():
            logger.warning("Auto-refresh thread already running")
            return
        
        def refresh_loop():
            while not self._stop_refresh.is_set():
                if self._stop_refresh.wait(timeout=self.refresh_interval * 3600):
                    break
                logger.info(f"🔄 Symbol auto-refresh triggered ({self.refresh_interval}h interval)")
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    symbols = loop.run_until_complete(self.select_by_momentum())
                    self._save_cache(symbols)
                    loop.close()
                except Exception as e:
                    logger.error(f"❌ Auto-refresh failed: {e}")
        
        self._refresh_thread = threading.Thread(target=refresh_loop, daemon=True, name="SymbolSelector-Refresh")
        self._refresh_thread.start()
        logger.info(f"🔄 Symbol auto-refresh started ({self.refresh_interval}h interval)")
    
    def stop_auto_refresh(self):
        if self._refresh_thread and self._refresh_thread.is_alive():
            self._stop_refresh.set()
            self._refresh_thread.join(timeout=5)
            logger.info("🛑 Symbol auto-refresh stopped")
