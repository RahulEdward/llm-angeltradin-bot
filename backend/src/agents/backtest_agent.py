"""
Backtest Agent
Production-grade backtesting engine for strategy validation
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
import pandas as pd
from loguru import logger

from .base import BaseAgent, AgentType, AgentMessage, MessageType
from ..broker import BrokerFactory, Candle


@dataclass
class BacktestTrade:
    """Individual backtest trade record."""
    symbol: str
    side: str
    entry_time: datetime
    entry_price: float
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    quantity: int = 1
    pnl: float = 0.0
    pnl_pct: float = 0.0
    exit_reason: str = ""
    reasoning: str = ""


@dataclass
class BacktestResult:
    """Backtest run results."""
    run_id: str
    symbol: str
    start_date: datetime
    end_date: datetime
    initial_capital: float
    final_capital: float
    total_return_pct: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    max_drawdown_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    profit_factor: float
    avg_win: float
    avg_loss: float
    equity_curve: List[Dict] = field(default_factory=list)
    trades: List[BacktestTrade] = field(default_factory=list)


class BacktestAgent(BaseAgent):
    """
    Backtest Agent - Historical simulation engine.
    Uses SAME strategy and risk logic as live trading.
    """
    
    def __init__(self, name: str = "BacktestAgent", config: Optional[Dict[str, Any]] = None):
        super().__init__(name, AgentType.BACKTEST, config or {})
        
        self._results: Dict[str, BacktestResult] = {}
        self._current_run: Optional[str] = None
        self._is_running: bool = False
    
    async def initialize(self) -> bool:
        logger.info("BacktestAgent initialized")
        return True
    
    async def process_cycle(self) -> List[AgentMessage]:
        return []  # Backtest runs on-demand
    
    async def handle_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        return None
    
    async def shutdown(self) -> None:
        self._is_running = False
        logger.info("BacktestAgent shutdown")
    
    async def run_backtest(
        self,
        symbol: str,
        exchange: str,
        start_date: datetime,
        end_date: datetime,
        initial_capital: float = 1000000.0,
        timeframe: str = "5m",
        stop_loss_pct: float = 2.0,
        take_profit_pct: float = 4.0,
        use_llm: bool = False,
        strategy_config: Optional[Dict] = None
    ) -> BacktestResult:
        """Run a complete backtest."""
        run_id = f"BT_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self._current_run = run_id
        self._is_running = True
        
        logger.info(f"Starting backtest {run_id}: {symbol} from {start_date} to {end_date}")
        
        # Get historical data
        broker = BrokerFactory.get_data_broker()
        if not broker or not await broker.is_connected():
            broker = BrokerFactory.create()
            await broker.connect()
        
        candles = await broker.get_historical_data(symbol, exchange, timeframe, start_date, end_date)
        
        if not candles:
            logger.error("No historical data available")
            return self._create_empty_result(run_id, symbol, start_date, end_date, initial_capital)
        
        # Convert to DataFrame
        df = pd.DataFrame([{
            "timestamp": c.timestamp, "open": c.open, "high": c.high,
            "low": c.low, "close": c.close, "volume": c.volume
        } for c in candles])
        df.set_index("timestamp", inplace=True)
        
        # Calculate indicators
        df = self._calculate_indicators(df)
        
        # Run simulation
        result = await self._simulate(
            run_id, symbol, df, initial_capital,
            stop_loss_pct, take_profit_pct, use_llm
        )
        
        self._results[run_id] = result
        self._is_running = False
        
        logger.info(f"Backtest {run_id} complete: {result.total_return_pct:.2f}% return, {result.win_rate:.1f}% win rate")
        
        return result
    
    async def _simulate(
        self,
        run_id: str,
        symbol: str,
        df: pd.DataFrame,
        initial_capital: float,
        stop_loss_pct: float,
        take_profit_pct: float,
        use_llm: bool
    ) -> BacktestResult:
        """Run candle-by-candle simulation."""
        capital = initial_capital
        peak_capital = initial_capital
        trades: List[BacktestTrade] = []
        equity_curve: List[Dict] = []
        current_trade: Optional[BacktestTrade] = None
        
        for i in range(50, len(df)):  # Start after enough data for indicators
            if not self._is_running:
                break
            
            row = df.iloc[i]
            timestamp = df.index[i]
            
            # Get current indicators
            indicators = {
                "ema_9": row.get("ema_9", row["close"]),
                "ema_21": row.get("ema_21", row["close"]),
                "rsi_14": row.get("rsi_14", 50),
                "macd": row.get("macd", 0),
                "macd_signal": row.get("macd_signal", 0),
                "bb_upper": row.get("bb_upper", row["close"] * 1.02),
                "bb_lower": row.get("bb_lower", row["close"] * 0.98),
                "atr_14": row.get("atr_14", row["close"] * 0.02)
            }
            
            # Check existing trade
            if current_trade:
                exit_price, exit_reason = self._check_exit(
                    current_trade, row, stop_loss_pct, take_profit_pct
                )
                
                if exit_price:
                    current_trade.exit_time = timestamp
                    current_trade.exit_price = exit_price
                    current_trade.exit_reason = exit_reason
                    
                    if current_trade.side == "BUY":
                        current_trade.pnl = (exit_price - current_trade.entry_price) * current_trade.quantity
                    else:
                        current_trade.pnl = (current_trade.entry_price - exit_price) * current_trade.quantity
                    
                    current_trade.pnl_pct = current_trade.pnl / (current_trade.entry_price * current_trade.quantity) * 100
                    capital += current_trade.pnl
                    trades.append(current_trade)
                    current_trade = None
            
            # Check for new entry
            if not current_trade:
                signal = self._generate_signal(row, indicators, df.iloc[i-20:i])
                
                if signal["action"] in ["BUY", "SELL"]:
                    quantity = int(capital * 0.1 / row["close"])  # 10% position size
                    if quantity > 0:
                        current_trade = BacktestTrade(
                            symbol=symbol,
                            side=signal["action"],
                            entry_time=timestamp,
                            entry_price=row["close"],
                            quantity=quantity,
                            reasoning=signal.get("reasoning", "")
                        )
            
            # Track equity
            unrealized_pnl = 0
            if current_trade:
                if current_trade.side == "BUY":
                    unrealized_pnl = (row["close"] - current_trade.entry_price) * current_trade.quantity
                else:
                    unrealized_pnl = (current_trade.entry_price - row["close"]) * current_trade.quantity
            
            current_equity = capital + unrealized_pnl
            peak_capital = max(peak_capital, current_equity)
            
            equity_curve.append({
                "timestamp": timestamp.isoformat() if hasattr(timestamp, 'isoformat') else str(timestamp),
                "equity": current_equity,
                "drawdown_pct": (peak_capital - current_equity) / peak_capital * 100
            })
        
        # Close any open trade at end
        if current_trade:
            last_price = df.iloc[-1]["close"]
            current_trade.exit_time = df.index[-1]
            current_trade.exit_price = last_price
            current_trade.exit_reason = "end_of_test"
            if current_trade.side == "BUY":
                current_trade.pnl = (last_price - current_trade.entry_price) * current_trade.quantity
            else:
                current_trade.pnl = (current_trade.entry_price - last_price) * current_trade.quantity
            capital += current_trade.pnl
            trades.append(current_trade)
        
        # Calculate metrics
        return self._calculate_metrics(
            run_id, symbol, df.index[0], df.index[-1],
            initial_capital, capital, trades, equity_curve
        )
    
    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate technical indicators."""
        df["ema_9"] = df["close"].ewm(span=9).mean()
        df["ema_21"] = df["close"].ewm(span=21).mean()
        df["ema_50"] = df["close"].ewm(span=50).mean()
        
        # RSI
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df["rsi_14"] = 100 - (100 / (1 + rs))
        
        # MACD
        ema_12 = df["close"].ewm(span=12).mean()
        ema_26 = df["close"].ewm(span=26).mean()
        df["macd"] = ema_12 - ema_26
        df["macd_signal"] = df["macd"].ewm(span=9).mean()
        
        # Bollinger Bands
        df["bb_middle"] = df["close"].rolling(window=20).mean()
        bb_std = df["close"].rolling(window=20).std()
        df["bb_upper"] = df["bb_middle"] + 2 * bb_std
        df["bb_lower"] = df["bb_middle"] - 2 * bb_std
        
        # ATR
        high_low = df["high"] - df["low"]
        high_close = abs(df["high"] - df["close"].shift())
        low_close = abs(df["low"] - df["close"].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df["atr_14"] = tr.rolling(window=14).mean()
        
        return df
    
    def _generate_signal(self, row: pd.Series, indicators: Dict, history: pd.DataFrame) -> Dict:
        """Generate trading signal using same logic as live."""
        close = row["close"]
        ema_9 = indicators["ema_9"]
        ema_21 = indicators["ema_21"]
        rsi = indicators["rsi_14"]
        macd = indicators["macd"]
        macd_signal = indicators["macd_signal"]
        
        signal = {"action": "HOLD", "confidence": 0, "reasoning": ""}
        
        # Trend alignment
        trend_bullish = close > ema_21 and ema_9 > ema_21
        trend_bearish = close < ema_21 and ema_9 < ema_21
        
        # Momentum
        macd_bullish = macd > macd_signal
        macd_bearish = macd < macd_signal
        
        # RSI conditions
        rsi_oversold = rsi < 35
        rsi_overbought = rsi > 65
        
        # Generate signals
        if trend_bullish and macd_bullish and rsi_oversold:
            signal = {
                "action": "BUY",
                "confidence": 0.7,
                "reasoning": f"Bullish: EMA crossover, MACD positive, RSI oversold ({rsi:.1f})"
            }
        elif trend_bearish and macd_bearish and rsi_overbought:
            signal = {
                "action": "SELL",
                "confidence": 0.7,
                "reasoning": f"Bearish: EMA crossover, MACD negative, RSI overbought ({rsi:.1f})"
            }
        
        return signal
    
    def _check_exit(
        self,
        trade: BacktestTrade,
        row: pd.Series,
        sl_pct: float,
        tp_pct: float
    ) -> tuple:
        """Check for exit conditions."""
        high = row["high"]
        low = row["low"]
        
        if trade.side == "BUY":
            sl_price = trade.entry_price * (1 - sl_pct / 100)
            tp_price = trade.entry_price * (1 + tp_pct / 100)
            
            if low <= sl_price:
                return sl_price, "stop_loss"
            if high >= tp_price:
                return tp_price, "take_profit"
        else:
            sl_price = trade.entry_price * (1 + sl_pct / 100)
            tp_price = trade.entry_price * (1 - tp_pct / 100)
            
            if high >= sl_price:
                return sl_price, "stop_loss"
            if low <= tp_price:
                return tp_price, "take_profit"
        
        return None, ""
    
    def _calculate_metrics(
        self,
        run_id: str,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        initial_capital: float,
        final_capital: float,
        trades: List[BacktestTrade],
        equity_curve: List[Dict]
    ) -> BacktestResult:
        """Calculate performance metrics."""
        total_trades = len(trades)
        winning_trades = len([t for t in trades if t.pnl > 0])
        losing_trades = len([t for t in trades if t.pnl < 0])
        
        wins = [t.pnl for t in trades if t.pnl > 0]
        losses = [abs(t.pnl) for t in trades if t.pnl < 0]
        
        avg_win = sum(wins) / len(wins) if wins else 0
        avg_loss = sum(losses) / len(losses) if losses else 0
        
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        profit_factor = (sum(wins) / sum(losses)) if sum(losses) > 0 else float('inf')
        
        # Calculate max drawdown
        max_dd = max([e["drawdown_pct"] for e in equity_curve]) if equity_curve else 0
        
        # Sharpe ratio (simplified)
        returns = [(equity_curve[i]["equity"] - equity_curve[i-1]["equity"]) / equity_curve[i-1]["equity"]
                   for i in range(1, len(equity_curve)) if equity_curve[i-1]["equity"] > 0]
        
        if returns:
            avg_return = sum(returns) / len(returns)
            std_return = (sum((r - avg_return) ** 2 for r in returns) / len(returns)) ** 0.5
            sharpe = (avg_return / std_return * (252 ** 0.5)) if std_return > 0 else 0
        else:
            sharpe = 0
        
        # Sortino (using only negative returns)
        neg_returns = [r for r in returns if r < 0]
        if neg_returns:
            downside_std = (sum(r ** 2 for r in neg_returns) / len(neg_returns)) ** 0.5
            sortino = (avg_return / downside_std * (252 ** 0.5)) if downside_std > 0 else 0
        else:
            sortino = sharpe
        
        return BacktestResult(
            run_id=run_id,
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            final_capital=final_capital,
            total_return_pct=((final_capital - initial_capital) / initial_capital) * 100,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            max_drawdown_pct=max_dd,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            profit_factor=profit_factor,
            avg_win=avg_win,
            avg_loss=avg_loss,
            equity_curve=equity_curve,
            trades=trades
        )
    
    def _create_empty_result(self, run_id, symbol, start, end, capital) -> BacktestResult:
        return BacktestResult(
            run_id=run_id, symbol=symbol, start_date=start, end_date=end,
            initial_capital=capital, final_capital=capital, total_return_pct=0,
            total_trades=0, winning_trades=0, losing_trades=0, win_rate=0,
            max_drawdown_pct=0, sharpe_ratio=0, sortino_ratio=0, profit_factor=0,
            avg_win=0, avg_loss=0
        )
    
    def get_result(self, run_id: str) -> Optional[BacktestResult]:
        return self._results.get(run_id)
    
    def get_all_results(self) -> Dict[str, BacktestResult]:
        return self._results
