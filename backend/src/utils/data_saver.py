"""
Data Saver — Structured data persistence with date-based organization.
Adapted from reference-repo for Indian equity markets.

Directory structure (Multi-Agent Framework):
data/
  kline/               (Shared K-line cache)
  live/                (Live trading data)
    agents/            (All Agent logs)
      trend_agent/
      setup_agent/
      trigger_agent/
      bull_bear/
      strategy_engine/
      reflection/
    market_data/       (Raw market data)
    analytics/         (Quant analysis)
    execution/         (Trade execution)
    risk/              (Risk audit)
  backtest/            (Backtest data)
    agents/
    analytics/
    results/
    trades/
"""

import json
import os
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional
from loguru import logger


class CustomJSONEncoder(json.JSONEncoder):
    """Custom JSON Encoder to handle datetime and numpy types."""

    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(obj, (np.integer, np.int32, np.int64)):
            return int(obj)
        if isinstance(obj, (np.floating, np.float32, np.float64)):
            return float(obj)
        if isinstance(obj, np.bool_):
            return bool(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, pd.Timestamp):
            return obj.strftime("%Y-%m-%d %H:%M:%S")
        return super().default(obj)


class DataSaver:
    """
    Data Saver — Agent-based file organization with live/backtest separation.
    Adapted for Indian equity trading (INR, NSE/BSE).
    """

    TRADE_COLUMNS = [
        "record_time", "open_cycle", "close_cycle", "action", "symbol",
        "price", "quantity", "cost", "exit_price", "pnl", "confidence", "status",
    ]

    def __init__(self, base_dir: str = "data", mode: str = "live"):
        self.base_dir = base_dir
        self.mode = mode
        self.mode_dir = os.path.join(base_dir, mode)
        self.kline_dir = os.path.join(base_dir, "kline")

        self.dirs = {
            # Agent logs
            "trend_agent": os.path.join(self.mode_dir, "agents", "trend_agent"),
            "setup_agent": os.path.join(self.mode_dir, "agents", "setup_agent"),
            "trigger_agent": os.path.join(self.mode_dir, "agents", "trigger_agent"),
            "bull_bear": os.path.join(self.mode_dir, "agents", "bull_bear"),
            "strategy_engine": os.path.join(self.mode_dir, "agents", "strategy_engine"),
            "reflection": os.path.join(self.mode_dir, "agents", "reflection"),
            # Data
            "market_data": os.path.join(self.mode_dir, "market_data"),
            "kline": self.kline_dir,
            # Analytics
            "indicators": os.path.join(self.mode_dir, "analytics", "indicators"),
            "predictions": os.path.join(self.mode_dir, "analytics", "predictions"),
            "regime": os.path.join(self.mode_dir, "analytics", "regime"),
            "analytics": os.path.join(self.mode_dir, "analytics"),
            # Execution
            "orders": os.path.join(self.mode_dir, "execution", "orders"),
            "trades": os.path.join(self.mode_dir, "execution", "trades"),
            # Risk
            "risk_audits": os.path.join(self.mode_dir, "risk", "audits"),
            # Backward compatibility
            "llm_logs": os.path.join(self.mode_dir, "agents", "strategy_engine"),
            "decisions": os.path.join(self.mode_dir, "agents", "strategy_engine"),
            "agent_context": os.path.join(self.mode_dir, "analytics"),
            "executions": os.path.join(self.mode_dir, "execution", "orders"),
            "features": os.path.join(self.mode_dir, "analytics"),
        }

    def clear_live_data(self) -> int:
        """Clear data/live directory (preserves all_trades.csv, kline cache, backtest)."""
        live_dir = os.path.join(self.base_dir, "live")
        if not os.path.exists(live_dir):
            logger.info("data/live does not exist, skipping cleanup")
            return 0

        files_deleted = 0
        for subdir in os.listdir(live_dir):
            subdir_path = os.path.join(live_dir, subdir)
            if not os.path.isdir(subdir_path):
                continue
            for root, dirs, files in os.walk(subdir_path, topdown=False):
                for file in files:
                    if file == "all_trades.csv":
                        continue
                    try:
                        os.remove(os.path.join(root, file))
                        files_deleted += 1
                    except Exception as e:
                        logger.warning(f"Cannot delete {file}: {e}")
                for d in dirs:
                    dir_path = os.path.join(root, d)
                    try:
                        if os.path.isdir(dir_path) and not os.listdir(dir_path):
                            os.rmdir(dir_path)
                    except Exception:
                        pass

        if files_deleted > 0:
            logger.info(f"Cleanup: deleted {files_deleted} files from data/live")
        return files_deleted

    def _get_date_folder(self, category: str, symbol: Optional[str] = None, date: Optional[str] = None) -> str:
        """Get or create date-based folder for a category."""
        if date is None:
            date = datetime.now().strftime("%Y%m%d")
        category_dir = self.dirs.get(category, os.path.join(self.base_dir, category))
        if symbol:
            target = os.path.join(category_dir, symbol, date)
        else:
            target = os.path.join(category_dir, date)
        os.makedirs(target, exist_ok=True)
        return target

    # ─── Save methods ───

    def save_market_data(self, klines: List[Dict], symbol: str, timeframe: str,
                         save_formats: List[str] = None, cycle_id: str = None) -> Dict[str, str]:
        """Save raw OHLCV data."""
        if save_formats is None:
            save_formats = ["json", "csv"]
        if not klines:
            return {}
        folder = self._get_date_folder("market_data", symbol=symbol)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = f"market_data_{symbol}_{timeframe}_{ts}"
        if cycle_id:
            base += f"_cycle_{cycle_id}"
        saved = {}
        if "json" in save_formats:
            path = os.path.join(folder, f"{base}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"metadata": {"symbol": symbol, "timeframe": timeframe, "count": len(klines)}, "klines": klines},
                          f, indent=2, cls=CustomJSONEncoder)
            saved["json"] = path
        if "csv" in save_formats:
            path = os.path.join(folder, f"{base}.csv")
            pd.DataFrame(klines).to_csv(path, index=False)
            saved["csv"] = path
        return saved

    def save_indicators(self, df: pd.DataFrame, symbol: str, timeframe: str,
                        snapshot_id: str, cycle_id: str = None) -> Dict[str, str]:
        """Save technical indicator data."""
        folder = self._get_date_folder("indicators", symbol=symbol)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        name = f"indicators_{symbol}_{timeframe}_{ts}"
        if cycle_id:
            name += f"_cycle_{cycle_id}"
        name += f"_snap_{snapshot_id}.csv"
        path = os.path.join(folder, name)
        try:
            df.to_csv(path, index=False)
            return {"csv": path}
        except Exception as e:
            logger.error(f"Failed to save indicators: {e}")
            return {}

    def save_features(self, features: pd.DataFrame, symbol: str, timeframe: str,
                      snapshot_id: str, version: str = "v1", cycle_id: str = None) -> Dict[str, str]:
        """Save feature data."""
        folder = self._get_date_folder("features", symbol=symbol)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        name = f"features_{symbol}_{timeframe}_{ts}"
        if cycle_id:
            name += f"_cycle_{cycle_id}"
        name += f"_snap_{snapshot_id}_{version}.csv"
        path = os.path.join(folder, name)
        try:
            features.to_csv(path, index=False)
            return {"csv": path}
        except Exception as e:
            logger.error(f"Failed to save features: {e}")
            return {}

    def save_context(self, context: Dict, symbol: str, identifier: str,
                     snapshot_id: str, cycle_id: str = None) -> Dict[str, str]:
        """Save agent context / analysis results."""
        folder = self._get_date_folder("agent_context", symbol=symbol)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        name = f"context_{symbol}_{identifier}_{ts}"
        if cycle_id:
            name += f"_cycle_{cycle_id}"
        name += f"_snap_{snapshot_id}.json"
        path = os.path.join(folder, name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(context, f, indent=2, ensure_ascii=False, cls=CustomJSONEncoder)
        return {"json": path}

    def save_llm_log(self, content: str, symbol: str, snapshot_id: str,
                     cycle_id: str = None) -> Dict[str, str]:
        """Save LLM interaction log."""
        folder = self._get_date_folder("llm_logs", symbol=symbol)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        name = f"llm_log_{ts}"
        if cycle_id:
            name += f"_{cycle_id}"
        name += f"_{snapshot_id}.md"
        path = os.path.join(folder, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return {"md": path}

    def save_trend_analysis(self, analysis: str, input_data: Dict, symbol: str,
                            cycle_id: str, model: str = "gemini") -> Dict[str, str]:
        """Save TrendAgent analysis log."""
        return self._save_agent_analysis("trend_agent", "trend", analysis, input_data, symbol, cycle_id, model)

    def save_setup_analysis(self, analysis: str, input_data: Dict, symbol: str,
                            cycle_id: str, model: str = "gemini") -> Dict[str, str]:
        """Save SetupAgent analysis log."""
        return self._save_agent_analysis("setup_agent", "setup", analysis, input_data, symbol, cycle_id, model)

    def save_trigger_analysis(self, analysis: str, input_data: Dict, symbol: str,
                              cycle_id: str, model: str = "gemini") -> Dict[str, str]:
        """Save TriggerAgent analysis log."""
        return self._save_agent_analysis("trigger_agent", "trigger", analysis, input_data, symbol, cycle_id, model)

    def _save_agent_analysis(self, category: str, prefix: str, analysis: str,
                             input_data: Dict, symbol: str, cycle_id: str, model: str) -> Dict[str, str]:
        """Common agent analysis saver."""
        folder = self._get_date_folder(category, symbol=symbol)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(folder, f"{prefix}_{ts}_{cycle_id}.json")
        data = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "cycle_id": cycle_id, "symbol": symbol,
            "input_data": input_data, "analysis": analysis,
            "model": model, "temperature": 0.3,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, cls=CustomJSONEncoder)
        return {"json": path}

    def save_bull_bear_perspectives(self, bull: Dict, bear: Dict, symbol: str,
                                    cycle_id: str) -> Dict[str, str]:
        """Save Bull/Bear adversarial analysis."""
        folder = self._get_date_folder("bull_bear", symbol=symbol)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(folder, f"perspectives_{ts}_{cycle_id}.json")
        data = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "cycle_id": cycle_id, "symbol": symbol,
            "bull_perspective": bull, "bear_perspective": bear,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, cls=CustomJSONEncoder)
        return {"json": path}

    def save_reflection(self, reflection: str, trades_analyzed: int, timestamp: str) -> Dict[str, str]:
        """Save ReflectionAgent log."""
        folder = self._get_date_folder("reflection")
        path = os.path.join(folder, f"reflection_{timestamp}.json")
        data = {"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "trades_analyzed": trades_analyzed, "reflection": reflection}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, cls=CustomJSONEncoder)
        return {"json": path}

    def save_decision(self, decision: Dict, symbol: str, snapshot_id: str,
                      cycle_id: str = None) -> Dict[str, str]:
        """Save decision result."""
        folder = self._get_date_folder("decisions", symbol=symbol)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        if cycle_id:
            decision["cycle_id"] = cycle_id
            name = f"decision_{symbol}_{ts}_{cycle_id}.json"
        else:
            name = f"decision_{symbol}_{ts}_{snapshot_id}.json"
        path = os.path.join(folder, name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(decision, f, indent=2, ensure_ascii=False, cls=CustomJSONEncoder)
        return {"json": path}

    def save_execution(self, record: Dict, symbol: str, cycle_id: str = None) -> Dict[str, str]:
        """Save execution record."""
        folder = self._get_date_folder("orders", symbol=symbol)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        if cycle_id:
            record["cycle_id"] = cycle_id
            name = f"execution_{symbol}_{ts}_{cycle_id}.json"
        else:
            name = f"order_{symbol}_{ts}.json"
        path = os.path.join(folder, name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2, ensure_ascii=False, cls=CustomJSONEncoder)
        # Append CSV
        csv_path = os.path.join(folder, f"orders_{symbol}.csv")
        df = pd.DataFrame([record])
        if os.path.exists(csv_path):
            df.to_csv(csv_path, mode="a", header=False, index=False)
        else:
            df.to_csv(csv_path, index=False)
        return {"json": path, "csv": csv_path}

    def save_risk_audit(self, audit_result: Dict, symbol: str, snapshot_id: str,
                        cycle_id: str = None) -> Dict[str, str]:
        """Save risk audit result."""
        folder = self._get_date_folder("risk_audits", symbol=symbol)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        if cycle_id:
            audit_result["cycle_id"] = cycle_id
            name = f"audit_{symbol}_{ts}_{cycle_id}_{snapshot_id}.json"
        else:
            name = f"risk_audit_{symbol}_{ts}_{snapshot_id}.json"
        path = os.path.join(folder, name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(audit_result, f, indent=2, ensure_ascii=False, cls=CustomJSONEncoder)
        return {"json": path}

    def save_prediction(self, prediction: Dict, symbol: str, snapshot_id: str,
                        cycle_id: str = None) -> Dict[str, str]:
        """Save Prophet prediction result."""
        folder = self._get_date_folder("predictions", symbol=symbol)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        if cycle_id:
            prediction["cycle_id"] = cycle_id
            name = f"prediction_{symbol}_{ts}_{cycle_id}_{snapshot_id}.json"
        else:
            name = f"prediction_{symbol}_{ts}_{snapshot_id}.json"
        path = os.path.join(folder, name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(prediction, f, indent=2, ensure_ascii=False, cls=CustomJSONEncoder)
        return {"json": path}

    # ─── Trade persistence ───

    def save_trade(self, trade_data: Dict):
        """Save trade record (append to single CSV)."""
        try:
            base_path = self.dirs.get("trades")
            os.makedirs(base_path, exist_ok=True)
            file_path = os.path.join(base_path, "all_trades.csv")
            trade_data["record_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for col in self.TRADE_COLUMNS:
                if col not in trade_data:
                    trade_data[col] = 0.0 if col in ("cost", "pnl", "exit_price", "price", "quantity") else "N/A"
            df = pd.DataFrame([{col: trade_data[col] for col in self.TRADE_COLUMNS}])
            if os.path.exists(file_path):
                df.to_csv(file_path, mode="a", header=False, index=False)
            else:
                df.to_csv(file_path, mode="w", header=True, index=False)
        except Exception as e:
            logger.error(f"Failed to save trade record: {e}")

    def get_recent_trades(self, limit: int = 10, days: int = 30) -> List[Dict]:
        """Get most recent trade records."""
        try:
            file_path = os.path.join(self.dirs.get("trades", ""), "all_trades.csv")
            if not os.path.exists(file_path):
                return []
            df = pd.read_csv(file_path)
            if df.empty:
                return []
            if "record_time" in df.columns:
                df["record_time"] = pd.to_datetime(df["record_time"], errors="coerce")
                cutoff = datetime.now() - pd.Timedelta(days=days)
                df = df[df["record_time"] >= cutoff]
            return df.tail(limit).to_dict("records") if not df.empty else []
        except Exception as e:
            logger.error(f"Failed to get recent trades: {e}")
            return []

    def update_trade_exit(self, symbol: str, exit_price: float, pnl: float,
                          exit_time: str, close_cycle: int = 0) -> bool:
        """Update trade record with exit info (in-place update for round-trip view)."""
        try:
            file_path = os.path.join(self.dirs.get("trades", ""), "all_trades.csv")
            if not os.path.exists(file_path):
                return False
            df = pd.read_csv(file_path)
            if df.empty:
                return False
            df["exit_price"] = pd.to_numeric(df["exit_price"], errors="coerce").fillna(0)
            mask = (df["symbol"] == symbol) & (df["exit_price"] == 0)
            if not mask.any():
                return False
            idx = df[mask].index[-1]
            df.at[idx, "exit_price"] = exit_price
            df.at[idx, "pnl"] = pnl
            df.at[idx, "close_cycle"] = close_cycle
            df.at[idx, "status"] = "CLOSED"
            df.to_csv(file_path, index=False)
            logger.info(f"Updated trade: {symbol} closed @ ₹{exit_price:.2f}, PnL: ₹{pnl:.2f}")
            return True
        except Exception as e:
            logger.error(f"Failed to update trade exit: {e}")
            return False

    def save_virtual_account(self, balance: float, positions: Dict):
        """Persist virtual/paper account state."""
        try:
            path = os.path.join(self.base_dir, "agents", "virtual_account.json")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            data = {"balance": balance, "positions": positions,
                    "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, cls=CustomJSONEncoder)
        except Exception as e:
            logger.error(f"Failed to save virtual account: {e}")

    def load_virtual_account(self) -> Optional[Dict]:
        """Load virtual/paper account state."""
        try:
            path = os.path.join(self.base_dir, "agents", "virtual_account.json")
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load virtual account: {e}")
        return None

    def list_files(self, category: str, symbol: Optional[str] = None,
                   date: Optional[str] = None) -> List[str]:
        """List files in a category folder."""
        folder = self._get_date_folder(category, symbol=symbol, date=date)
        if not os.path.exists(folder):
            return []
        return [os.path.join(folder, f) for f in os.listdir(folder)]

    # Backward-compatible aliases
    save_step1_klines = save_market_data
    save_step2_indicators = save_indicators
    save_step3_features = save_features
    save_step4_context = save_context
    save_step5_markdown = save_llm_log
    save_step6_decision = save_decision
    save_step7_execution = save_execution
