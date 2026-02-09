"""
Market Data Agent
Responsible for fetching and distributing market data
Supports both real broker data and simulated data for paper mode without broker
"""

import asyncio
import random
import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import pandas as pd
from loguru import logger

from .base import BaseAgent, AgentType, AgentMessage, MessageType
from ..broker import BaseBroker, BrokerFactory, Candle, Quote


# Realistic base prices for Indian blue-chip stocks
SIMULATED_BASE_PRICES = {
    "RELIANCE": 2450.0,
    "TCS": 3850.0,
    "INFY": 1580.0,
    "HDFCBANK": 1620.0,
    "ICICIBANK": 1050.0,
    "SBIN": 780.0,
    "KOTAKBANK": 1750.0,
    "TATAMOTORS": 720.0,
    "ONGC": 260.0,
    "HINDUNILVR": 2350.0,
}


class MarketDataAgent(BaseAgent):
    """
    Market Data Agent - The Oracle.
    
    Responsibilities:
    - Fetch real-time market quotes (from broker or simulated)
    - Fetch historical OHLCV data
    - Calculate technical indicators
    - Distribute market snapshots to other agents
    """
    
    def __init__(
        self,
        name: str = "MarketDataAgent",
        config: Optional[Dict[str, Any]] = None
    ):
        super().__init__(name, AgentType.MARKET_DATA, config)
        
        self.symbols: List[str] = config.get("symbols", [])
        self.exchanges: Dict[str, str] = config.get("exchanges", {})
        self.timeframes: List[str] = config.get("timeframes", ["5m", "15m", "1h"])
        self.update_interval: int = config.get("update_interval", 60)
        
        # Data storage
        self._market_data: Dict[str, Dict] = {}
        self._historical_data: Dict[str, pd.DataFrame] = {}
        self._indicators: Dict[str, Dict] = {}
        
        # Broker reference
        self._broker: Optional[BaseBroker] = None
        
        # Simulation state (for paper mode without broker)
        self._sim_prices: Dict[str, float] = {}
        self._sim_initialized: bool = False
    
    async def initialize(self) -> bool:
        """Initialize market data agent."""
        try:
            self._broker = BrokerFactory.get_instance()
            if not self._broker:
                self._broker = BrokerFactory.create()
            
            if self._broker:
                try:
                    if not await self._broker.is_connected():
                        connected = await self._broker.connect()
                        if not connected:
                            logger.warning("Broker not connected - will use simulated data")
                except Exception as e:
                    logger.warning(f"Broker connection check failed: {e}")
            else:
                logger.warning("No broker available - using simulated market data")
            
            # Initialize simulation prices
            self._init_simulation()
            
            logger.info(f"MarketDataAgent initialized with {len(self.symbols)} symbols")
            return True
            
        except Exception as e:
            self.log_error(f"Initialization error: {str(e)}")
            logger.warning(f"MarketDataAgent init error (non-fatal): {e}")
            self._init_simulation()
            return True
    
    def _init_simulation(self):
        """Initialize simulated price state for all symbols."""
        if self._sim_initialized:
            return
        for symbol in self.symbols:
            base = SIMULATED_BASE_PRICES.get(symbol, 1000.0 + random.uniform(-200, 200))
            self._sim_prices[symbol] = base
        self._sim_initialized = True
        logger.info(f"Simulation initialized for {len(self.symbols)} symbols")
    
    def _generate_simulated_quote(self, symbol: str, exchange: str) -> Dict[str, Any]:
        """Generate realistic simulated OHLCV quote with random walk."""
        base = self._sim_prices.get(symbol, 1000.0)
        
        # Random walk: small % change each cycle
        change_pct = random.gauss(0, 0.3) / 100  # ~0.3% std dev
        new_price = base * (1 + change_pct)
        self._sim_prices[symbol] = new_price
        
        # Generate OHLCV around the new price
        volatility = new_price * 0.005  # 0.5% intraday range
        high = new_price + abs(random.gauss(0, volatility))
        low = new_price - abs(random.gauss(0, volatility))
        open_price = new_price + random.gauss(0, volatility * 0.3)
        volume = random.randint(50000, 500000)
        
        spread = new_price * 0.0005  # 0.05% spread
        
        return {
            "symbol": symbol,
            "exchange": exchange,
            "ltp": round(new_price, 2),
            "open": round(open_price, 2),
            "high": round(high, 2),
            "low": round(low, 2),
            "close": round(new_price, 2),
            "volume": volume,
            "bid": round(new_price - spread, 2),
            "ask": round(new_price + spread, 2),
            "timestamp": datetime.now().isoformat(),
            "simulated": True
        }
    
    def _generate_simulated_historical(self, symbol: str, timeframe: str) -> pd.DataFrame:
        """Generate simulated historical OHLCV data."""
        periods_map = {"1m": 60, "5m": 100, "15m": 80, "1h": 50, "1d": 30}
        n_periods = periods_map.get(timeframe, 50)
        
        interval_map = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "1d": 1440}
        interval_mins = interval_map.get(timeframe, 5)
        
        base = self._sim_prices.get(symbol, 1000.0)
        price = base * (1 - random.uniform(0.02, 0.05))  # Start slightly lower
        
        rows = []
        now = datetime.now()
        for i in range(n_periods):
            ts = now - timedelta(minutes=interval_mins * (n_periods - i))
            change = random.gauss(0, 0.3) / 100
            price *= (1 + change)
            vol_factor = price * 0.005
            h = price + abs(random.gauss(0, vol_factor))
            l = price - abs(random.gauss(0, vol_factor))
            o = price + random.gauss(0, vol_factor * 0.3)
            v = random.randint(10000, 200000)
            rows.append({
                "timestamp": ts,
                "open": round(o, 2),
                "high": round(h, 2),
                "low": round(l, 2),
                "close": round(price, 2),
                "volume": v
            })
        
        df = pd.DataFrame(rows)
        df.set_index("timestamp", inplace=True)
        return df

    async def _try_get_broker(self) -> bool:
        """
        Try to get/refresh a REAL broker connection (one that can provide market data).
        Returns True only if a real data broker is available (not standalone paper).
        """
        # Always re-check factory for new connections
        connected_broker = BrokerFactory.get_connected_broker()
        if connected_broker:
            # Real broker was connected via Settings
            self._broker = BrokerFactory.get_instance()
            if not self._broker:
                self._broker = BrokerFactory.create()
        
        if not self._broker:
            self._broker = BrokerFactory.get_instance()
        
        if self._broker:
            # If it's a standalone PaperBroker, it can't provide real market data
            from ..broker.paper_broker import PaperBroker
            if isinstance(self._broker, PaperBroker) and self._broker._standalone:
                return False
            try:
                return await self._broker.is_connected()
            except Exception:
                return False
        return False
    
    async def process_cycle(self) -> List[AgentMessage]:
        """Fetch and process market data (real or simulated)."""
        messages = []
        
        broker_available = await self._try_get_broker()
        
        try:
            if broker_available:
                # Use real broker data
                await self._fetch_real_data()
            else:
                # Use simulated data
                self._fetch_simulated_data()
            
            # Calculate indicators for all symbols
            for symbol in self.symbols:
                exchange = self.exchanges.get(symbol, "NSE")
                indicators = await self._calculate_indicators(symbol, exchange)
                self._indicators[f"{exchange}:{symbol}"] = indicators
            
            # Create market snapshot message
            snapshot = {
                "quotes": self._market_data,
                "indicators": self._indicators,
                "timestamp": datetime.now().isoformat(),
                "source": "broker" if broker_available else "simulated"
            }
            
            messages.append(AgentMessage(
                type=MessageType.MARKET_UPDATE,
                source_agent=self.name,
                payload=snapshot,
                priority=1
            ))
            
            self.update_metrics(
                symbols_tracked=len(self.symbols),
                last_fetch=datetime.now().isoformat(),
                data_source="broker" if broker_available else "simulated"
            )
            
        except Exception as e:
            self.log_error(f"Process cycle error: {str(e)}")
            logger.error(f"MarketDataAgent cycle error: {e}")
            messages.append(AgentMessage(
                type=MessageType.ERROR,
                source_agent=self.name,
                payload={"error": str(e), "agent": "MarketDataAgent"}
            ))
        
        return messages
    
    async def _fetch_real_data(self):
        """Fetch real market data from broker."""
        for symbol in self.symbols:
            exchange = self.exchanges.get(symbol, "NSE")
            
            try:
                quote = await self._broker.get_quote(symbol, exchange)
                if quote:
                    self._market_data[f"{exchange}:{symbol}"] = {
                        "symbol": symbol,
                        "exchange": exchange,
                        "ltp": quote.ltp,
                        "open": quote.open,
                        "high": quote.high,
                        "low": quote.low,
                        "close": quote.close,
                        "volume": quote.volume,
                        "bid": quote.bid,
                        "ask": quote.ask,
                        "timestamp": quote.timestamp.isoformat(),
                        "simulated": False
                    }
                    # Update sim prices to track real prices
                    self._sim_prices[symbol] = quote.ltp
            except Exception as e:
                logger.warning(f"Real quote fetch failed for {symbol}: {e}")
                # Fallback to simulated for this symbol
                self._market_data[f"{exchange}:{symbol}"] = self._generate_simulated_quote(symbol, exchange)
            
            # Fetch historical data
            for timeframe in self.timeframes:
                await self._fetch_historical(symbol, exchange, timeframe)
        
        # Also sync prices to paper broker (in case paper mode with real data)
        self._sync_prices_to_paper_broker()
    
    def _fetch_simulated_data(self):
        """Generate simulated market data for all symbols."""
        for symbol in self.symbols:
            exchange = self.exchanges.get(symbol, "NSE")
            key = f"{exchange}:{symbol}"
            
            self._market_data[key] = self._generate_simulated_quote(symbol, exchange)
            
            # Generate historical data if not already present
            for timeframe in self.timeframes:
                hist_key = f"{exchange}:{symbol}:{timeframe}"
                if hist_key not in self._historical_data:
                    self._historical_data[hist_key] = self._generate_simulated_historical(symbol, timeframe)
                else:
                    # Append new candle to existing data
                    df = self._historical_data[hist_key]
                    quote = self._market_data[key]
                    new_row = pd.DataFrame([{
                        "timestamp": datetime.now(),
                        "open": quote["open"],
                        "high": quote["high"],
                        "low": quote["low"],
                        "close": quote["close"],
                        "volume": quote["volume"]
                    }]).set_index("timestamp")
                    self._historical_data[hist_key] = pd.concat([df, new_row]).tail(200)
        
        # Push simulated prices to PaperBroker so ExecutionAgent can fill orders
        self._sync_prices_to_paper_broker()
    
    def _sync_prices_to_paper_broker(self):
        """Push current simulated prices to PaperBroker for order execution."""
        try:
            broker = BrokerFactory.get_instance()
            if broker and hasattr(broker, 'update_simulated_prices'):
                # Build price dict: {"NSE:RELIANCE": {"ltp": ..., "bid": ..., "ask": ...}, ...}
                prices = {}
                for key, data in self._market_data.items():
                    prices[key] = {
                        "ltp": data.get("ltp", 0),
                        "bid": data.get("bid", data.get("ltp", 0)),
                        "ask": data.get("ask", data.get("ltp", 0)),
                        "open": data.get("open", 0),
                        "high": data.get("high", 0),
                        "low": data.get("low", 0),
                        "close": data.get("close", 0),
                        "volume": data.get("volume", 0),
                    }
                broker.update_simulated_prices(prices)
        except Exception as e:
            logger.debug(f"Price sync to paper broker: {e}")
    
    async def handle_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Handle incoming requests for market data."""
        if message.type == MessageType.STATE_UPDATE:
            symbol = message.payload.get("symbol")
            if symbol:
                data = self._market_data.get(symbol, {})
                return AgentMessage(
                    type=MessageType.MARKET_UPDATE,
                    source_agent=self.name,
                    target_agent=message.source_agent,
                    payload=data,
                    correlation_id=message.id
                )
        return None
    async def shutdown(self) -> None:
        """Cleanup market data agent."""
        self._market_data.clear()
        self._historical_data.clear()
        self._indicators.clear()
        logger.info("MarketDataAgent shutdown complete")
    
    async def _fetch_historical(self, symbol: str, exchange: str, timeframe: str) -> None:
        """Fetch historical data for a symbol from broker."""
        try:
            lookback_map = {
                "1m": timedelta(days=1),
                "5m": timedelta(days=5),
                "15m": timedelta(days=15),
                "1h": timedelta(days=30),
                "1d": timedelta(days=365)
            }
            lookback = lookback_map.get(timeframe, timedelta(days=5))
            
            to_date = datetime.now()
            from_date = to_date - lookback
            
            candles = await self._broker.get_historical_data(
                symbol, exchange, timeframe, from_date, to_date
            )
            
            if candles:
                df = pd.DataFrame([
                    {
                        "timestamp": c.timestamp,
                        "open": c.open,
                        "high": c.high,
                        "low": c.low,
                        "close": c.close,
                        "volume": c.volume
                    }
                    for c in candles
                ])
                df.set_index("timestamp", inplace=True)
                
                key = f"{exchange}:{symbol}:{timeframe}"
                self._historical_data[key] = df
                
        except Exception as e:
            self.log_error(f"Historical fetch error {symbol}: {str(e)}")
    
    async def _calculate_indicators(self, symbol: str, exchange: str) -> Dict[str, Any]:
        """Calculate technical indicators."""
        indicators = {}
        
        try:
            for timeframe in self.timeframes:
                key = f"{exchange}:{symbol}:{timeframe}"
                df = self._historical_data.get(key)
                
                if df is None or len(df) < 20:
                    continue
                
                tf_indicators = {}
                
                # EMA calculations
                tf_indicators["ema_9"] = float(df["close"].ewm(span=9).mean().iloc[-1])
                tf_indicators["ema_21"] = float(df["close"].ewm(span=21).mean().iloc[-1])
                tf_indicators["ema_50"] = float(df["close"].ewm(span=50).mean().iloc[-1]) if len(df) >= 50 else None
                
                # RSI
                delta = df["close"].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs))
                tf_indicators["rsi_14"] = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50
                
                # MACD
                ema_12 = df["close"].ewm(span=12).mean()
                ema_26 = df["close"].ewm(span=26).mean()
                macd_line = ema_12 - ema_26
                signal_line = macd_line.ewm(span=9).mean()
                tf_indicators["macd"] = float(macd_line.iloc[-1])
                tf_indicators["macd_signal"] = float(signal_line.iloc[-1])
                tf_indicators["macd_histogram"] = float(macd_line.iloc[-1] - signal_line.iloc[-1])
                
                # Bollinger Bands
                sma_20 = df["close"].rolling(window=20).mean()
                std_20 = df["close"].rolling(window=20).std()
                tf_indicators["bb_upper"] = float(sma_20.iloc[-1] + 2 * std_20.iloc[-1])
                tf_indicators["bb_middle"] = float(sma_20.iloc[-1])
                tf_indicators["bb_lower"] = float(sma_20.iloc[-1] - 2 * std_20.iloc[-1])
                
                # ATR
                high_low = df["high"] - df["low"]
                high_close = abs(df["high"] - df["close"].shift())
                low_close = abs(df["low"] - df["close"].shift())
                tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
                atr = tr.rolling(window=14).mean()
                tf_indicators["atr_14"] = float(atr.iloc[-1]) if not pd.isna(atr.iloc[-1]) else 0
                
                # Volume analysis
                vol_sma = df["volume"].rolling(window=20).mean().iloc[-1]
                tf_indicators["volume_sma_20"] = float(vol_sma) if not pd.isna(vol_sma) else 0
                tf_indicators["relative_volume"] = float(df["volume"].iloc[-1] / vol_sma) if vol_sma > 0 else 1.0
                
                # Trend determination
                close = df["close"].iloc[-1]
                tf_indicators["trend"] = "bullish" if close > tf_indicators["ema_21"] else "bearish"
                tf_indicators["momentum"] = "strong" if abs(tf_indicators["rsi_14"] - 50) > 20 else "weak"
                
                indicators[timeframe] = tf_indicators
                
        except Exception as e:
            self.log_error(f"Indicator calculation error: {str(e)}")
        
        return indicators
    
    def get_market_snapshot(self, symbol: str = None) -> Dict[str, Any]:
        """Get current market snapshot."""
        if symbol:
            return {
                "quote": self._market_data.get(symbol, {}),
                "indicators": self._indicators.get(symbol, {})
            }
        return {
            "quotes": self._market_data,
            "indicators": self._indicators
        }
    
    def get_historical_df(self, symbol: str, exchange: str, timeframe: str) -> Optional[pd.DataFrame]:
        """Get historical data DataFrame."""
        key = f"{exchange}:{symbol}:{timeframe}"
        return self._historical_data.get(key)
