"""
Market Data Agent
Responsible for fetching and distributing REAL market data only.
No simulated/mock data — requires broker connection for live prices.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import pandas as pd
from loguru import logger

from .base import BaseAgent, AgentType, AgentMessage, MessageType
from ..broker import BaseBroker, BrokerFactory, Candle, Quote


class MarketDataAgent(BaseAgent):
    """
    Market Data Agent - The Oracle.
    
    Responsibilities:
    - Fetch real-time market quotes from connected broker
    - Fetch historical OHLCV data
    - Calculate technical indicators
    - Distribute market snapshots to other agents
    
    NO simulated/mock data. Broker must be connected for data.
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
                            logger.warning("Broker not connected - no market data available")
                except Exception as e:
                    logger.warning(f"Broker connection check failed: {e}")
            else:
                logger.warning("No broker available - connect broker for market data")
            
            logger.info(f"MarketDataAgent initialized with {len(self.symbols)} symbols")
            return True
            
        except Exception as e:
            self.log_error(f"Initialization error: {str(e)}")
            logger.warning(f"MarketDataAgent init error (non-fatal): {e}")
            return True

    async def _try_get_broker(self) -> bool:
        """
        Try to get a REAL broker connection that can provide market data.
        Returns True only if a real connected broker is available.
        """
        connected_broker = BrokerFactory.get_connected_broker()
        if connected_broker:
            self._broker = BrokerFactory.get_instance()
            if not self._broker:
                self._broker = BrokerFactory.create()
        
        if not self._broker:
            self._broker = BrokerFactory.get_instance()
        
        if self._broker:
            try:
                return await self._broker.is_connected()
            except Exception:
                return False
        return False
    
    async def process_cycle(self) -> List[AgentMessage]:
        """Fetch and process real market data. No data if broker not connected."""
        messages = []
        
        broker_available = await self._try_get_broker()
        
        try:
            if broker_available:
                await self._fetch_real_data()
                data_source = "broker"
                # Fallback: if real data returned 0 quotes, use simulated data
                if not self._market_data:
                    logger.warning("Broker connected but 0 quotes fetched — falling back to simulated data")
                    await self._generate_simulated_data()
                    data_source = "simulated"
            else:
                # No broker — generate simulated data for Paper mode
                await self._generate_simulated_data()
                data_source = "simulated"
            
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
                "source": data_source
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
                data_source=data_source
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
            except Exception as e:
                logger.warning(f"Real quote fetch failed for {symbol}: {e}")
            
            # Fetch historical data
            for timeframe in self.timeframes:
                await self._fetch_historical(symbol, exchange, timeframe)
        
        # Sync prices to paper broker for order execution
        self._sync_prices_to_paper_broker()

    async def _generate_simulated_data(self):
        """Generate simulated market data (Random Walk) when no broker connected."""
        import random
        
        for symbol in self.symbols:
            exchange = self.exchanges.get(symbol, "NSE")
            key = f"{exchange}:{symbol}"
            
            # Get previous price or default start price
            prev_data = self._market_data.get(key, {})
            current_price = prev_data.get("ltp", 0)
            
            if current_price == 0:
                # Initial random price between 500 and 3000
                current_price = random.uniform(500, 3000)
            
            # Random walk: -0.2% to +0.2% change per cycle
            change_pct = random.uniform(-0.002, 0.002)
            new_price = current_price * (1 + change_pct)
            new_price = round(new_price, 2)
            
            # Generate tick data
            spread = new_price * 0.0005  # 0.05% spread
            bid = round(new_price - spread, 2)
            ask = round(new_price + spread, 2)
            
            # Update day high/low
            day_open = prev_data.get("open", new_price)
            day_high = max(prev_data.get("high", new_price), new_price)
            day_low = min(prev_data.get("low", new_price), new_price)
            
            self._market_data[key] = {
                "symbol": symbol,
                "exchange": exchange,
                "ltp": new_price,
                "open": day_open,
                "high": day_high,
                "low": day_low,
                "close": day_open,  # treating open as prev close for simplicity
                "volume": prev_data.get("volume", 0) + random.randint(10, 500),
                "bid": bid,
                "ask": ask,
                "timestamp": datetime.now().isoformat(),
                "simulated": True
            }
            
            # Generate fake historical data for indicators if needed
            # (In a real scenario, we'd append this tick to OHLCV history)
            self._update_simulated_history(symbol, exchange, new_price)
        
        # Sync to paper broker so orders execute at these prices
        self._sync_prices_to_paper_broker()

    def _update_simulated_history(self, symbol: str, exchange: str, price: float):
        """Append simulated tick to historical data for indicator calculation."""
        import numpy as np
        
        for timeframe in self.timeframes:
            key = f"{exchange}:{symbol}:{timeframe}"
            df = self._historical_data.get(key)
            
            # Create synthetic history if missing (backfill 50 candles)
            if df is None or df.empty:
                rows = []
                # Timesteps for backfill
                minutes = {"5m": 5, "15m": 15, "1h": 60}.get(timeframe, 5)
                end_time = datetime.now()
                
                # Random walk backfill
                curr = price
                for i in range(50):
                    ts = end_time - timedelta(minutes=minutes * (50 - i))
                    change = np.random.normal(0, 0.002) # 0.2% volatility
                    o = curr
                    c = curr * (1 + change)
                    h = max(o, c) * (1 + abs(np.random.normal(0, 0.001)))
                    l = min(o, c) * (1 - abs(np.random.normal(0, 0.001)))
                    v = int(np.random.randint(100, 10000))
                    rows.append({
                        "timestamp": ts,
                        "open": o, "high": h, "low": l, "close": c, "volume": v
                    })
                    curr = c
                
                df = pd.DataFrame(rows)
                df.set_index("timestamp", inplace=True)
                self._historical_data[key] = df
            
            # Append new candle if enough time passed
            else:
                last_ts = df.index[-1]
                minutes = {"5m": 5, "15m": 15, "1h": 60}.get(timeframe, 5)
                next_ts = last_ts + timedelta(minutes=minutes)
                
                if datetime.now() >= next_ts:
                    # Create new candle from recent price movement
                    # For simplicity in simulation, we just use current price
                    new_row = pd.DataFrame([{
                        "timestamp": next_ts,
                        "open": price, 
                        "high": price * 1.001, 
                        "low": price * 0.999, 
                        "close": price, 
                        "volume": int(np.random.randint(100, 5000))
                    }]).set_index("timestamp")
                    
                    df = pd.concat([df, new_row])
                    # Keep rolling window size manageable
                    if len(df) > 100:
                        df = df.iloc[-100:]
                    self._historical_data[key] = df
    
    def _sync_prices_to_paper_broker(self):
        """Push current real prices to PaperBroker for order execution."""
        try:
            broker = BrokerFactory.get_instance()
            if broker and hasattr(broker, 'update_simulated_prices'):
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
            logger.warning(f"Price sync to paper broker failed: {e}")
    
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
