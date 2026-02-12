"""
Backtest Agent
Production-grade backtesting engine matching reference-repo output format.
Fetches real historical data from Angel One broker.
Calculates comprehensive metrics: Sharpe, Sortino, Calmar, drawdown duration, etc.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import math
import numpy as np
import pandas as pd
from loguru import logger

from .base import BaseAgent, AgentType, AgentMessage, MessageType
from ..broker import BrokerFactory, Candle


# ============================================
# Data Classes (matching reference-repo)
# ============================================

@dataclass
class BacktestTrade:
    """Individual trade record."""
    trade_id: int
    symbol: str
    side: str  # "long" or "short"
    action: str  # "open" or "close"
    quantity: float
    price: float
    timestamp: datetime
    pnl: float = 0.0
    pnl_pct: float = 0.0
    commission: float = 0.0
    slippage: float = 0.0
    entry_price: Optional[float] = None
    holding_time: Optional[float] = None  # hours
    close_reason: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "trade_id": self.trade_id,
            "symbol": self.symbol,
            "side": self.side,
            "action": self.action,
            "quantity": self.quantity,
            "price": round(self.price, 2),
            "timestamp": self.timestamp.isoformat() if hasattr(self.timestamp, 'isoformat') else str(self.timestamp),
            "pnl": round(self.pnl, 2),
            "pnl_pct": round(self.pnl_pct, 2),
            "commission": round(self.commission, 2),
            "entry_price": round(self.entry_price, 2) if self.entry_price else None,
            "holding_time": round(self.holding_time, 1) if self.holding_time else None,
            "close_reason": self.close_reason,
        }


@dataclass
class MetricsResult:
    """Performance metrics (matches reference-repo MetricsResult)."""
    total_return: float = 0.0
    annualized_return: float = 0.0
    final_equity: float = 0.0
    profit_amount: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    max_drawdown_duration: int = 0

    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    volatility: float = 0.0

    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_trade_pnl: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    avg_holding_time: float = 0.0

    long_trades: int = 0
    short_trades: int = 0
    long_win_rate: float = 0.0
    short_win_rate: float = 0.0
    long_pnl: float = 0.0
    short_pnl: float = 0.0

    start_date: str = ""
    end_date: str = ""
    total_days: int = 0
    trading_days: int = 0

    def to_dict(self) -> Dict:
        return {
            "total_return": f"{self.total_return:.2f}%",
            "final_equity": f"{self.final_equity:.2f}",
            "profit_amount": f"{self.profit_amount:+.2f}",
            "max_drawdown": f"₹{self.max_drawdown:.2f}",
            "max_drawdown_pct": f"{self.max_drawdown_pct:.2f}%",
            "max_drawdown_duration": f"{self.max_drawdown_duration} days",
            "sharpe_ratio": f"{self.sharpe_ratio:.2f}",
            "sortino_ratio": f"{self.sortino_ratio:.2f}",
            "calmar_ratio": f"{self.calmar_ratio:.2f}",
            "volatility": f"{self.volatility:.2f}%",
            "total_trades": self.total_trades,
            "win_rate": f"{self.win_rate:.1f}%",
            "profit_factor": f"{self.profit_factor:.2f}",
            "avg_trade_pnl": f"₹{self.avg_trade_pnl:.2f}",
            "avg_win": f"₹{self.avg_win:.2f}",
            "avg_loss": f"₹{self.avg_loss:.2f}",
            "largest_win": f"₹{self.largest_win:.2f}",
            "largest_loss": f"₹{self.largest_loss:.2f}",
            "avg_holding_time": f"{self.avg_holding_time:.1f}h",
            "long_trades": self.long_trades,
            "short_trades": self.short_trades,
            "long_win_rate": f"{self.long_win_rate:.1f}%",
            "short_win_rate": f"{self.short_win_rate:.1f}%",
            "long_pnl": f"₹{self.long_pnl:.2f}",
            "short_pnl": f"₹{self.short_pnl:.2f}",
            "period": f"{self.start_date} to {self.end_date}",
            "total_days": self.total_days,
            "trading_days": self.trading_days,
        }


@dataclass
class BacktestResult:
    """Full backtest result."""
    run_id: str
    config: Dict
    metrics: MetricsResult
    equity_curve: List[Dict] = field(default_factory=list)
    trades: List[BacktestTrade] = field(default_factory=list)
    decisions: List[Dict] = field(default_factory=list)
    duration_seconds: float = 0.0



# ============================================
# Backtest Agent
# ============================================

class BacktestAgent(BaseAgent):
    """
    Production backtesting engine.
    Fetches real historical data from broker, runs indicator-based strategy,
    calculates comprehensive metrics matching reference-repo format.
    """

    COMMISSION_RATE = 0.0003  # 0.03% per trade (Indian market typical)
    SLIPPAGE_RATE = 0.0001   # 0.01% slippage
    RISK_FREE_RATE = 0.06    # 6% (India RBI rate)
    TRADING_DAYS_PER_YEAR = 252  # Indian equity market

    def __init__(self, config: Dict = None):
        super().__init__(name="BacktestAgent", agent_type=AgentType.BACKTEST, config=config or {})
        self._results: Dict[str, BacktestResult] = {}

    async def initialize(self) -> None:
        self._is_active = True
        logger.info("BacktestAgent initialized")

    async def process_cycle(self) -> List[AgentMessage]:
        return []

    async def handle_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        if message.type == MessageType.COMMAND and message.payload.get("command") == "backtest":
            result = await self.run_backtest(**message.payload.get("params", {}))
            return AgentMessage(
                type=MessageType.STATE_UPDATE,
                source_agent=self.name,
                payload={"backtest_result": result.run_id}
            )
        return None

    async def shutdown(self) -> None:
        self._is_active = False
        logger.info("BacktestAgent shutdown")

    # ============================================
    # Data Fetching
    # ============================================

    def _get_data_broker(self):
        """Get the data broker for historical data."""
        return BrokerFactory.get_data_broker()

    async def _fetch_historical(
        self,
        symbol: str,
        exchange: str,
        interval: str,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """Fetch historical candle data and return as DataFrame."""
        broker = self._get_data_broker()
        if not broker:
            logger.warning("No data broker available for backtest")
            return pd.DataFrame()

        try:
            candles: List[Candle] = await broker.get_historical_data(
                symbol=symbol,
                exchange=exchange,
                interval=interval,
                from_date=start_date,
                to_date=end_date
            )

            if not candles:
                logger.warning(f"No historical data for {symbol}")
                return pd.DataFrame()

            data = [{
                "timestamp": c.timestamp,
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
                "volume": c.volume
            } for c in candles]

            df = pd.DataFrame(data)
            df.set_index("timestamp", inplace=True)
            df.sort_index(inplace=True)
            return df

        except Exception as e:
            logger.error(f"Historical data fetch error for {symbol}: {e}")
            return pd.DataFrame()

    # ============================================
    # Technical Indicators
    # ============================================

    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate technical indicators on OHLCV DataFrame."""
        if df.empty or len(df) < 26:
            return df

        close = df["close"]
        high = df["high"]
        low = df["low"]

        # EMA 9, 21
        df["ema9"] = close.ewm(span=9, adjust=False).mean()
        df["ema21"] = close.ewm(span=21, adjust=False).mean()

        # RSI 14
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0.0)).rolling(14).mean()
        rs = gain / loss.replace(0, np.nan)
        df["rsi"] = 100 - (100 / (1 + rs))

        # MACD
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        df["macd"] = ema12 - ema26
        df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
        df["macd_hist"] = df["macd"] - df["macd_signal"]

        # Bollinger Bands
        sma20 = close.rolling(20).mean()
        std20 = close.rolling(20).std()
        df["bb_upper"] = sma20 + 2 * std20
        df["bb_lower"] = sma20 - 2 * std20
        df["bb_mid"] = sma20

        # ATR 14
        tr = pd.concat([
            high - low,
            (high - close.shift()).abs(),
            (low - close.shift()).abs()
        ], axis=1).max(axis=1)
        df["atr"] = tr.rolling(14).mean()

        # Volume SMA
        df["vol_sma"] = df["volume"].rolling(20).mean()

        return df

    def _get_row_indicators(self, row) -> Dict:
        """Extract indicator values from a DataFrame row."""
        return {
            "ema9": row.get("ema9", 0),
            "ema21": row.get("ema21", 0),
            "rsi": row.get("rsi", 50),
            "macd": row.get("macd", 0),
            "macd_signal": row.get("macd_signal", 0),
            "macd_hist": row.get("macd_hist", 0),
            "bb_upper": row.get("bb_upper", 0),
            "bb_lower": row.get("bb_lower", 0),
            "atr": row.get("atr", 0),
            "volume": row.get("volume", 0),
            "vol_sma": row.get("vol_sma", 0),
        }

    # ============================================
    # Signal Generation & Exit Logic
    # ============================================

    def _generate_signal(self, indicators: Dict, price: float) -> str:
        """Generate trading signal from indicators. Returns 'long', 'short', or 'hold'."""
        rsi = indicators.get("rsi", 50)
        ema9 = indicators.get("ema9", 0)
        ema21 = indicators.get("ema21", 0)
        macd_hist = indicators.get("macd_hist", 0)
        bb_lower = indicators.get("bb_lower", 0)
        bb_upper = indicators.get("bb_upper", 0)

        bull_signals = 0
        bear_signals = 0

        # EMA crossover
        if ema9 > ema21:
            bull_signals += 1
        elif ema9 < ema21:
            bear_signals += 1

        # RSI
        if rsi < 35:
            bull_signals += 1
        elif rsi > 65:
            bear_signals += 1

        # MACD histogram
        if macd_hist > 0:
            bull_signals += 1
        elif macd_hist < 0:
            bear_signals += 1

        # Bollinger Bands
        if price <= bb_lower and bb_lower > 0:
            bull_signals += 1
        elif price >= bb_upper and bb_upper > 0:
            bear_signals += 1

        # Need at least 3 confirming signals
        if bull_signals >= 3:
            return "long"
        elif bear_signals >= 3:
            return "short"
        return "hold"

    def _check_exit(
        self,
        side: str,
        entry_price: float,
        current_price: float,
        indicators: Dict,
        stop_loss_pct: float,
        take_profit_pct: float
    ) -> Optional[str]:
        """Check if position should be closed. Returns reason or None."""
        if side == "long":
            pnl_pct = (current_price - entry_price) / entry_price * 100
        else:
            pnl_pct = (entry_price - current_price) / entry_price * 100

        if pnl_pct <= -stop_loss_pct:
            return "stop_loss"
        if pnl_pct >= take_profit_pct:
            return "take_profit"

        # Signal reversal exit
        rsi = indicators.get("rsi", 50)
        ema9 = indicators.get("ema9", 0)
        ema21 = indicators.get("ema21", 0)

        if side == "long" and ema9 < ema21 and rsi > 60:
            return "signal_reversal"
        if side == "short" and ema9 > ema21 and rsi < 40:
            return "signal_reversal"

        return None

    # ============================================
    # Core Backtest Engine
    # ============================================

    async def run_backtest(
        self,
        symbols: List[str] = None,
        exchange: str = "NSE",
        start_date: datetime = None,
        end_date: datetime = None,
        initial_capital: float = 100000,
        timeframe: str = "1h",
        stop_loss_pct: float = 2.0,
        take_profit_pct: float = 4.0,
        use_llm: bool = False,
        **kwargs
    ) -> BacktestResult:
        """Run backtest for one or more symbols."""
        import time as _time
        t0 = _time.time()

        symbols = symbols or ["RELIANCE"]
        start_date = start_date or datetime.now() - timedelta(days=90)
        end_date = end_date or datetime.now()

        run_id = f"bt_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        config = {
            "symbols": symbols,
            "exchange": exchange,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "initial_capital": initial_capital,
            "timeframe": timeframe,
            "stop_loss_pct": stop_loss_pct,
            "take_profit_pct": take_profit_pct,
        }

        logger.info(f"Backtest {run_id}: {symbols} | {start_date.date()} → {end_date.date()} | ₹{initial_capital:,.0f}")

        if len(symbols) == 1:
            result = await self._simulate_single(
                symbol=symbols[0], exchange=exchange,
                start_date=start_date, end_date=end_date,
                initial_capital=initial_capital, timeframe=timeframe,
                stop_loss_pct=stop_loss_pct, take_profit_pct=take_profit_pct,
            )
        else:
            result = await self._simulate_multi(
                symbols=symbols, exchange=exchange,
                start_date=start_date, end_date=end_date,
                initial_capital=initial_capital, timeframe=timeframe,
                stop_loss_pct=stop_loss_pct, take_profit_pct=take_profit_pct,
            )

        result.run_id = run_id
        result.config = config
        result.duration_seconds = _time.time() - t0
        self._results[run_id] = result

        logger.info(
            f"Backtest {run_id} done in {result.duration_seconds:.1f}s | "
            f"Return: {result.metrics.total_return:.2f}% | "
            f"Trades: {result.metrics.total_trades} | "
            f"Sharpe: {result.metrics.sharpe_ratio:.2f}"
        )
        return result

    async def _simulate_single(
        self,
        symbol: str,
        exchange: str,
        start_date: datetime,
        end_date: datetime,
        initial_capital: float,
        timeframe: str,
        stop_loss_pct: float,
        take_profit_pct: float,
    ) -> BacktestResult:
        """Run backtest on a single symbol."""
        df = await self._fetch_historical(symbol, exchange, timeframe, start_date, end_date)

        if df.empty:
            logger.warning(f"No data for {symbol}, returning empty result")
            return self._create_empty_result(initial_capital)

        df = self._calculate_indicators(df)
        # Drop rows where indicators aren't ready
        df = df.dropna(subset=["ema9", "ema21", "rsi", "macd", "atr"])

        if df.empty:
            return self._create_empty_result(initial_capital)

        equity = initial_capital
        peak_equity = initial_capital
        trades: List[BacktestTrade] = []
        equity_curve: List[Dict] = []
        trade_id = 0

        # Position state
        in_position = False
        position_side = ""
        entry_price = 0.0
        entry_time = None
        position_qty = 0.0

        for idx, row in df.iterrows():
            price = row["close"]
            indicators = self._get_row_indicators(row)

            # Check exit if in position
            if in_position:
                exit_reason = self._check_exit(
                    position_side, entry_price, price,
                    indicators, stop_loss_pct, take_profit_pct
                )
                if exit_reason:
                    # Close position
                    if position_side == "long":
                        raw_pnl = (price - entry_price) * position_qty
                    else:
                        raw_pnl = (entry_price - price) * position_qty

                    commission = price * position_qty * self.COMMISSION_RATE
                    pnl = raw_pnl - commission
                    pnl_pct = (pnl / (entry_price * position_qty)) * 100 if entry_price > 0 else 0
                    hold_hours = (idx - entry_time).total_seconds() / 3600 if entry_time else 0

                    trade_id += 1
                    trades.append(BacktestTrade(
                        trade_id=trade_id, symbol=symbol,
                        side=position_side, action="close",
                        quantity=position_qty, price=price,
                        timestamp=idx, pnl=pnl, pnl_pct=pnl_pct,
                        commission=commission, entry_price=entry_price,
                        holding_time=hold_hours, close_reason=exit_reason,
                    ))

                    equity += pnl
                    in_position = False

            # Check entry if not in position
            if not in_position:
                signal = self._generate_signal(indicators, price)
                if signal in ("long", "short"):
                    # Size: risk 2% of equity per trade
                    atr = indicators.get("atr", price * 0.01)
                    risk_amount = equity * 0.02
                    position_qty = max(1, int(risk_amount / (atr if atr > 0 else price * 0.01)))
                    # Cap at 10% of equity
                    max_qty = int(equity * 0.10 / price) if price > 0 else 1
                    position_qty = min(position_qty, max(1, max_qty))

                    entry_price = price
                    entry_time = idx
                    position_side = signal
                    in_position = True

                    trade_id += 1
                    commission = price * position_qty * self.COMMISSION_RATE
                    equity -= commission
                    trades.append(BacktestTrade(
                        trade_id=trade_id, symbol=symbol,
                        side=signal, action="open",
                        quantity=position_qty, price=price,
                        timestamp=idx, commission=commission,
                    ))

            # Track equity curve
            unrealized = 0.0
            if in_position:
                if position_side == "long":
                    unrealized = (price - entry_price) * position_qty
                else:
                    unrealized = (entry_price - price) * position_qty

            current_equity = equity + unrealized
            peak_equity = max(peak_equity, current_equity)
            drawdown = peak_equity - current_equity
            dd_pct = (drawdown / peak_equity * 100) if peak_equity > 0 else 0

            equity_curve.append({
                "timestamp": idx.isoformat() if hasattr(idx, 'isoformat') else str(idx),
                "equity": round(current_equity, 2),
                "drawdown": round(drawdown, 2),
                "drawdown_pct": round(dd_pct, 2),
            })

        # Force close any open position at end
        if in_position and len(df) > 0:
            last_price = df.iloc[-1]["close"]
            last_ts = df.index[-1]
            if position_side == "long":
                raw_pnl = (last_price - entry_price) * position_qty
            else:
                raw_pnl = (entry_price - last_price) * position_qty
            commission = last_price * position_qty * self.COMMISSION_RATE
            pnl = raw_pnl - commission
            pnl_pct = (pnl / (entry_price * position_qty)) * 100 if entry_price > 0 else 0
            hold_hours = (last_ts - entry_time).total_seconds() / 3600 if entry_time else 0

            trade_id += 1
            trades.append(BacktestTrade(
                trade_id=trade_id, symbol=symbol,
                side=position_side, action="close",
                quantity=position_qty, price=last_price,
                timestamp=last_ts, pnl=pnl, pnl_pct=pnl_pct,
                commission=commission, entry_price=entry_price,
                holding_time=hold_hours, close_reason="end_of_data",
            ))
            equity += pnl

        # Calculate metrics
        metrics = self._calculate_metrics(trades, equity_curve, initial_capital, equity)

        return BacktestResult(
            run_id="", config={}, metrics=metrics,
            equity_curve=equity_curve, trades=trades,
        )

    async def _simulate_multi(
        self,
        symbols: List[str],
        exchange: str,
        start_date: datetime,
        end_date: datetime,
        initial_capital: float,
        timeframe: str,
        stop_loss_pct: float,
        take_profit_pct: float,
    ) -> BacktestResult:
        """Run backtest across multiple symbols, splitting capital equally."""
        per_symbol_capital = initial_capital / len(symbols)
        all_trades: List[BacktestTrade] = []
        combined_equity_curves: List[List[Dict]] = []

        for symbol in symbols:
            result = await self._simulate_single(
                symbol=symbol, exchange=exchange,
                start_date=start_date, end_date=end_date,
                initial_capital=per_symbol_capital, timeframe=timeframe,
                stop_loss_pct=stop_loss_pct, take_profit_pct=take_profit_pct,
            )
            all_trades.extend(result.trades)
            combined_equity_curves.append(result.equity_curve)

        # Merge equity curves by summing equity at each timestamp
        merged_curve = []
        if combined_equity_curves:
            max_len = max(len(c) for c in combined_equity_curves)
            for i in range(max_len):
                total_eq = 0.0
                for curve in combined_equity_curves:
                    if i < len(curve):
                        total_eq += curve[i]["equity"]
                    elif curve:
                        total_eq += curve[-1]["equity"]
                peak = max(total_eq, merged_curve[-1]["equity"] if merged_curve else initial_capital)
                dd = peak - total_eq
                dd_pct = (dd / peak * 100) if peak > 0 else 0
                ts = combined_equity_curves[0][min(i, len(combined_equity_curves[0]) - 1)]["timestamp"] if combined_equity_curves[0] else ""
                merged_curve.append({
                    "timestamp": ts,
                    "equity": round(total_eq, 2),
                    "drawdown": round(dd, 2),
                    "drawdown_pct": round(dd_pct, 2),
                })

        final_equity = merged_curve[-1]["equity"] if merged_curve else initial_capital
        metrics = self._calculate_metrics(all_trades, merged_curve, initial_capital, final_equity)

        return BacktestResult(
            run_id="", config={}, metrics=metrics,
            equity_curve=merged_curve, trades=all_trades,
        )

    # ============================================
    # Metrics Calculation (reference-repo style)
    # ============================================

    def _calculate_metrics(
        self,
        trades: List[BacktestTrade],
        equity_curve: List[Dict],
        initial_capital: float,
        final_equity: float,
    ) -> MetricsResult:
        """Calculate comprehensive performance metrics."""
        closed_trades = [t for t in trades if t.action == "close"]
        pnls = [t.pnl for t in closed_trades]

        # Returns
        total_return = ((final_equity - initial_capital) / initial_capital * 100) if initial_capital > 0 else 0
        profit_amount = final_equity - initial_capital

        # Time
        if equity_curve:
            start_date = equity_curve[0].get("timestamp", "")[:10]
            end_date = equity_curve[-1].get("timestamp", "")[:10]
            try:
                d0 = datetime.fromisoformat(equity_curve[0]["timestamp"][:19])
                d1 = datetime.fromisoformat(equity_curve[-1]["timestamp"][:19])
                total_days = max((d1 - d0).days, 1)
            except Exception:
                total_days = 1
        else:
            start_date = end_date = ""
            total_days = 1

        trading_days = len(set(
            t.timestamp.date() if hasattr(t.timestamp, 'date') else t.timestamp
            for t in closed_trades
        )) if closed_trades else 0

        # Annualized return
        annualized_return = ((1 + total_return / 100) ** (365 / total_days) - 1) * 100 if total_days > 0 else 0

        # Max drawdown
        max_dd = 0.0
        max_dd_pct = 0.0
        max_dd_duration = 0
        if equity_curve:
            peak = initial_capital
            dd_start = None
            longest_dd = 0
            for pt in equity_curve:
                eq = pt["equity"]
                if eq > peak:
                    peak = eq
                    if dd_start is not None:
                        try:
                            dur = (datetime.fromisoformat(pt["timestamp"][:19]) - dd_start).days
                            longest_dd = max(longest_dd, dur)
                        except Exception:
                            pass
                    dd_start = None
                else:
                    dd = peak - eq
                    dd_pct = (dd / peak * 100) if peak > 0 else 0
                    if dd > max_dd:
                        max_dd = dd
                        max_dd_pct = dd_pct
                    if dd_start is None:
                        try:
                            dd_start = datetime.fromisoformat(pt["timestamp"][:19])
                        except Exception:
                            pass
            if dd_start is not None and equity_curve:
                try:
                    dur = (datetime.fromisoformat(equity_curve[-1]["timestamp"][:19]) - dd_start).days
                    longest_dd = max(longest_dd, dur)
                except Exception:
                    pass
            max_dd_duration = longest_dd

        # Risk metrics from equity curve
        sharpe = sortino = calmar = vol = 0.0
        if len(equity_curve) > 2:
            equities = [pt["equity"] for pt in equity_curve]
            returns = []
            for i in range(1, len(equities)):
                if equities[i - 1] > 0:
                    returns.append((equities[i] - equities[i - 1]) / equities[i - 1])
            if returns:
                arr = np.array(returns)
                daily_std = arr.std()
                vol = daily_std * np.sqrt(self.TRADING_DAYS_PER_YEAR) * 100

                risk_free_per_period = self.RISK_FREE_RATE * len(arr) / self.TRADING_DAYS_PER_YEAR
                excess = total_return / 100 - risk_free_per_period
                denom = daily_std * np.sqrt(len(arr))
                sharpe = (excess / denom) if denom > 0 else 0

                neg = arr[arr < 0]
                if len(neg) > 0:
                    down_std = neg.std()
                    sortino = (excess / (down_std * np.sqrt(len(arr)))) if down_std > 0 else 0

                calmar = (total_return / max_dd_pct) if max_dd_pct > 0 else 0

        # Trade stats
        winning = [p for p in pnls if p > 0]
        losing = [p for p in pnls if p < 0]
        total_win = sum(winning) if winning else 0
        total_loss_abs = abs(sum(losing)) if losing else 0

        win_rate = (len(winning) / len(pnls) * 100) if pnls else 0
        profit_factor = (total_win / total_loss_abs) if total_loss_abs > 0 else (float('inf') if total_win > 0 else 0)
        avg_pnl = (sum(pnls) / len(pnls)) if pnls else 0
        avg_win = (sum(winning) / len(winning)) if winning else 0
        avg_loss = (sum(losing) / len(losing)) if losing else 0
        largest_win = max(pnls) if pnls else 0
        largest_loss = min(pnls) if pnls else 0

        holding_times = [t.holding_time for t in closed_trades if t.holding_time is not None]
        avg_hold = (sum(holding_times) / len(holding_times)) if holding_times else 0

        # Long/Short stats
        long_closed = [t for t in closed_trades if t.side == "long"]
        short_closed = [t for t in closed_trades if t.side == "short"]
        long_wins = sum(1 for t in long_closed if t.pnl > 0)
        short_wins = sum(1 for t in short_closed if t.pnl > 0)

        return MetricsResult(
            total_return=round(total_return, 2),
            annualized_return=round(annualized_return, 2),
            final_equity=round(final_equity, 2),
            profit_amount=round(profit_amount, 2),
            max_drawdown=round(max_dd, 2),
            max_drawdown_pct=round(max_dd_pct, 2),
            max_drawdown_duration=max_dd_duration,
            sharpe_ratio=round(sharpe, 2),
            sortino_ratio=round(sortino, 2),
            calmar_ratio=round(calmar, 2),
            volatility=round(vol, 2),
            total_trades=len(closed_trades),
            winning_trades=len(winning),
            losing_trades=len(losing),
            win_rate=round(win_rate, 1),
            profit_factor=round(min(profit_factor, 999), 2),
            avg_trade_pnl=round(avg_pnl, 2),
            avg_win=round(avg_win, 2),
            avg_loss=round(avg_loss, 2),
            largest_win=round(largest_win, 2),
            largest_loss=round(largest_loss, 2),
            avg_holding_time=round(avg_hold, 1),
            long_trades=len(long_closed),
            short_trades=len(short_closed),
            long_win_rate=round((long_wins / len(long_closed) * 100) if long_closed else 0, 1),
            short_win_rate=round((short_wins / len(short_closed) * 100) if short_closed else 0, 1),
            long_pnl=round(sum(t.pnl for t in long_closed), 2),
            short_pnl=round(sum(t.pnl for t in short_closed), 2),
            start_date=start_date,
            end_date=end_date,
            total_days=total_days,
            trading_days=trading_days,
        )

    def _create_empty_result(self, initial_capital: float) -> BacktestResult:
        """Create an empty result when no data is available."""
        metrics = MetricsResult(final_equity=initial_capital)
        return BacktestResult(run_id="", config={}, metrics=metrics)

    # ============================================
    # Result Access
    # ============================================

    def get_result(self, run_id: str) -> Optional[BacktestResult]:
        return self._results.get(run_id)

    def get_all_results(self) -> Dict[str, BacktestResult]:
        return self._results
