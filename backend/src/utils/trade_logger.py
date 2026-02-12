"""
Trade Logger — Detailed open/close position logging with daily summaries.
Adapted for Indian equity markets (INR, delivery-based).
"""

import json
import os
from datetime import datetime
from typing import Dict, Optional, List
from pathlib import Path
from loguru import logger


class TradeLogger:
    """
    Trade Logger — Records detailed open/close position data.
    Supports daily summaries and CSV export.
    """

    def __init__(self, log_dir: str = "data/live/execution/tracking"):
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)

        self.trades: Dict[str, Dict] = {}       # trade_id -> record
        self.daily_stats: Dict[str, Dict] = {}  # date -> stats
        self._summary_file = os.path.join(log_dir, "summary.json")
        self._load_summary()

    def _load_summary(self):
        """Load existing summary from disk."""
        try:
            if os.path.exists(self._summary_file):
                with open(self._summary_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.trades = data.get("trades", {})
                    self.daily_stats = data.get("daily_stats", {})
        except Exception as e:
            logger.warning(f"Could not load trade summary: {e}")

    def _save_summary(self):
        """Persist summary to disk."""
        try:
            data = {"trades": self.trades, "daily_stats": self.daily_stats,
                    "updated_at": datetime.now().isoformat()}
            with open(self._summary_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.warning(f"Could not save trade summary: {e}")

    def log_open_position(self, symbol: str, side: str, decision: Dict,
                          execution_result: Dict, market_state: Dict,
                          account_info: Dict) -> str:
        """
        Log position open.

        Args:
            symbol: Trading symbol (e.g., RELIANCE)
            side: Direction (LONG only for Indian equity delivery)
            decision: Decision dict from strategy agent
            execution_result: Execution result from broker
            market_state: Current market state
            account_info: Account balance info

        Returns:
            trade_id: Unique trade identifier
        """
        trade_id = f"{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        entry_price = execution_result.get("fill_price", execution_result.get("price", 0))
        quantity = execution_result.get("quantity", 0)

        record = {
            "trade_id": trade_id,
            "symbol": symbol,
            "side": side,
            "status": "OPEN",
            "open_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "close_time": None,
            "entry_price": entry_price,
            "exit_price": None,
            "quantity": quantity,
            "cost": entry_price * quantity,
            "pnl": 0,
            "pnl_pct": 0,
            "close_reason": None,
            # Decision context
            "confidence": decision.get("confidence", 0),
            "stop_loss": decision.get("stop_loss", 0),
            "take_profit": decision.get("take_profit", 0),
            "regime": decision.get("regime", "unknown"),
            "reasoning": decision.get("reasoning", "")[:200],
            # Market context
            "market_summary": self._extract_market_summary(market_state),
            # Risk
            "max_loss": self._calculate_max_loss(execution_result, decision),
            "potential_profit": self._calculate_potential_profit(execution_result, decision),
            # Account
            "account_balance": account_info.get("balance", 0),
        }

        self.trades[trade_id] = record

        # Save individual log
        self._save_trade_log(record)
        self._save_summary()

        logger.info(
            f"📗 OPEN {side} {symbol} @ ₹{entry_price:.2f} x {quantity} "
            f"| SL: ₹{record['stop_loss']:.2f} | TP: ₹{record['take_profit']:.2f} "
            f"| Conf: {record['confidence']:.0%}"
        )
        return trade_id

    def log_close_position(self, trade_id: str, close_price: float,
                           close_reason: str, pnl: float, pnl_pct: float,
                           account_balance_after: float) -> bool:
        """
        Log position close.

        Args:
            trade_id: Trade ID from log_open_position
            close_price: Exit price
            close_reason: STOP_LOSS, TAKE_PROFIT, MANUAL, SIGNAL
            pnl: Profit/loss in INR
            pnl_pct: Profit/loss %
            account_balance_after: Balance after close
        """
        if trade_id not in self.trades:
            logger.warning(f"Trade {trade_id} not found")
            return False

        record = self.trades[trade_id]
        record.update({
            "status": "CLOSED",
            "close_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "exit_price": close_price,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "close_reason": close_reason,
            "account_balance_after": account_balance_after,
        })

        # Calculate hold duration
        try:
            open_time = datetime.strptime(record["open_time"], "%Y-%m-%d %H:%M:%S")
            close_time = datetime.strptime(record["close_time"], "%Y-%m-%d %H:%M:%S")
            record["hold_duration_min"] = (close_time - open_time).total_seconds() / 60
        except Exception:
            record["hold_duration_min"] = 0

        self._update_daily_stats(record)
        self._save_trade_log(record)
        self._save_summary()

        emoji = "📗" if pnl >= 0 else "📕"
        logger.info(
            f"{emoji} CLOSE {record['symbol']} @ ₹{close_price:.2f} "
            f"| {close_reason} | PnL: ₹{pnl:.2f} ({pnl_pct:+.2f}%) "
            f"| Duration: {record['hold_duration_min']:.0f}min"
        )
        return True

    def _extract_market_summary(self, market_state: Dict) -> Dict:
        """Extract market state summary."""
        return {
            "regime": market_state.get("regime", "unknown"),
            "trend": market_state.get("trend_direction", "neutral"),
            "adx": market_state.get("adx", 0),
            "atr_pct": market_state.get("atr_pct", 0),
        }

    def _calculate_max_loss(self, execution_result: Dict, decision: Dict) -> float:
        """Calculate max potential loss."""
        entry = execution_result.get("fill_price", execution_result.get("price", 0))
        sl = decision.get("stop_loss", 0)
        qty = execution_result.get("quantity", 0)
        if entry and sl and qty:
            return abs(entry - sl) * qty
        return 0

    def _calculate_potential_profit(self, execution_result: Dict, decision: Dict) -> float:
        """Calculate potential profit."""
        entry = execution_result.get("fill_price", execution_result.get("price", 0))
        tp = decision.get("take_profit", 0)
        qty = execution_result.get("quantity", 0)
        if entry and tp and qty:
            return abs(tp - entry) * qty
        return 0

    def _update_daily_stats(self, record: Dict):
        """Update daily statistics."""
        date = datetime.now().strftime("%Y%m%d")
        if date not in self.daily_stats:
            self.daily_stats[date] = {
                "total_trades": 0, "wins": 0, "losses": 0,
                "total_pnl": 0, "max_win": 0, "max_loss": 0,
            }
        stats = self.daily_stats[date]
        stats["total_trades"] += 1
        pnl = record.get("pnl", 0)
        stats["total_pnl"] += pnl
        if pnl >= 0:
            stats["wins"] += 1
            stats["max_win"] = max(stats["max_win"], pnl)
        else:
            stats["losses"] += 1
            stats["max_loss"] = min(stats["max_loss"], pnl)

    def _save_trade_log(self, record: Dict):
        """Save individual trade log file."""
        try:
            trade_id = record.get("trade_id", "unknown")
            path = os.path.join(self.log_dir, f"{trade_id}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(record, f, indent=2, default=str)
        except Exception as e:
            logger.warning(f"Failed to save trade log: {e}")

    def get_open_positions(self) -> List[Dict]:
        """Get all open positions."""
        return [t for t in self.trades.values() if t.get("status") == "OPEN"]

    def get_daily_summary(self, date: Optional[str] = None) -> Dict:
        """Get daily trade summary."""
        if date is None:
            date = datetime.now().strftime("%Y%m%d")
        stats = self.daily_stats.get(date, {
            "total_trades": 0, "wins": 0, "losses": 0,
            "total_pnl": 0, "max_win": 0, "max_loss": 0,
        })
        total = stats.get("total_trades", 0)
        wins = stats.get("wins", 0)
        stats["win_rate"] = (wins / total * 100) if total > 0 else 0
        return stats

    def export_to_csv(self, output_file: str = "data/trade_history.csv"):
        """Export all trades to CSV for Excel analysis."""
        try:
            import pandas as pd
            records = list(self.trades.values())
            if not records:
                logger.info("No trades to export")
                return
            df = pd.DataFrame(records)
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            df.to_csv(output_file, index=False)
            logger.info(f"Exported {len(records)} trades to {output_file}")
        except Exception as e:
            logger.error(f"Failed to export trades: {e}")


# Global instance
trade_logger = TradeLogger()
