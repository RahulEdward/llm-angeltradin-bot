"""
Market Data Agent
Responsible for fetching and distributing market data
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import pandas as pd
from loguru import logger

from .base import BaseAgent, AgentType, AgentMessage, MessageType
from ..broker import BaseBroker, BrokerFactory, Candle


class MarketDataAgent(BaseAgent):
    """
    Market Data Agent - The Oracle.
    
    Responsibilities:
    - Fetch real-time market quotes
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
        
        # Default config
        self.symbols: List[str] = config.get("symbols", [])
        self.exchanges: Dict[str, str] = config.get("exchanges", {})
        self.timeframes: List[str] = config.get("timeframes", ["5m", "15m", "1h"])
        self.update_interval: int = config.get("update_interval", 60)  # seconds
        
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
            
            if not await self._broker.is_connected():
                connected = await self._broker.connect()
                if not connected:
                    self.log_error("Failed to connect to broker")
                    return False
            
            logger.info(f"MarketDataAgent initialized with {len(self.symbols)} symbols")
            return True
            
        except Exception as e:
            self.log_error(f"Initialization error: {str(e)}")
            return False
    
    async def process_cycle(self) -> List[AgentMessage]:
        """Fetch and process market data."""
        messages = []
        
        try:
            # Fetch quotes for all symbols
            for symbol in self.symbols:
                exchange = self.exchanges.get(symbol, "NSE")
                
                # Get current quote
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
                        "timestamp": quote.timestamp.isoformat()
                    }
                
                # Fetch historical data for each timeframe
                for timeframe in self.timeframes:
                    await self._fetch_historical(symbol, exchange, timeframe)
                
                # Calculate indicators
                indicators = await self._calculate_indicators(symbol, exchange)
                self._indicators[f"{exchange}:{symbol}"] = indicators
            
            # Create market snapshot message
            snapshot = {
                "quotes": self._market_data,
                "indicators": self._indicators,
                "timestamp": datetime.now().isoformat()
            }
            
            messages.append(AgentMessage(
                type=MessageType.MARKET_UPDATE,
                source_agent=self.name,
                payload=snapshot,
                priority=1
            ))
            
            self.update_metrics(
                symbols_tracked=len(self.symbols),
                last_fetch=datetime.now().isoformat()
            )
            
        except Exception as e:
            self.log_error(f"Process cycle error: {str(e)}")
            messages.append(AgentMessage(
                type=MessageType.ERROR,
                source_agent=self.name,
                payload={"error": str(e)}
            ))
        
        return messages
    
    async def handle_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Handle incoming requests for market data."""
        if message.type == MessageType.STATE_UPDATE:
            # Data request
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
    
    async def _fetch_historical(
        self,
        symbol: str,
        exchange: str,
        timeframe: str
    ) -> None:
        """Fetch historical data for a symbol."""
        try:
            # Determine lookback based on timeframe
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
    
    async def _calculate_indicators(
        self,
        symbol: str,
        exchange: str
    ) -> Dict[str, Any]:
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
                tf_indicators["volume_sma_20"] = float(df["volume"].rolling(window=20).mean().iloc[-1])
                tf_indicators["relative_volume"] = float(df["volume"].iloc[-1] / df["volume"].rolling(window=20).mean().iloc[-1]) if df["volume"].rolling(window=20).mean().iloc[-1] > 0 else 1.0
                
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
    
    def get_historical_df(
        self,
        symbol: str,
        exchange: str,
        timeframe: str
    ) -> Optional[pd.DataFrame]:
        """Get historical data DataFrame."""
        key = f"{exchange}:{symbol}:{timeframe}"
        return self._historical_data.get(key)
