"""
Data Utilities
Data saving, loading, and logging utilities
"""

import json
import csv
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd
from loguru import logger


class DataSaver:
    """Save structured data for auditing and analysis."""
    
    def __init__(self, base_path: str = "data"):
        self.base_path = Path(base_path)
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Create required directories."""
        dirs = [
            "market_data",
            "indicators", 
            "decisions",
            "execution",
            "backtest"
        ]
        for d in dirs:
            (self.base_path / d).mkdir(parents=True, exist_ok=True)
    
    def _get_dated_path(self, subdir: str, filename: str) -> Path:
        """Get path with date-based organization."""
        date_str = datetime.now().strftime("%Y-%m-%d")
        path = self.base_path / subdir / date_str
        path.mkdir(parents=True, exist_ok=True)
        return path / filename
    
    def save_json(self, data: Dict, subdir: str, filename: str) -> str:
        """Save data as JSON."""
        filepath = self._get_dated_path(subdir, f"{filename}.json")
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, default=str)
        return str(filepath)
    
    def save_csv(self, data: List[Dict], subdir: str, filename: str) -> str:
        """Save data as CSV."""
        if not data:
            return ""
        filepath = self._get_dated_path(subdir, f"{filename}.csv")
        
        with open(filepath, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
        return str(filepath)
    
    def save_parquet(self, df: pd.DataFrame, subdir: str, filename: str) -> str:
        """Save DataFrame as Parquet."""
        filepath = self._get_dated_path(subdir, f"{filename}.parquet")
        df.to_parquet(filepath)
        return str(filepath)
    
    def load_json(self, filepath: str) -> Optional[Dict]:
        """Load JSON file."""
        try:
            with open(filepath) as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading JSON: {e}")
            return None
    
    def load_parquet(self, filepath: str) -> Optional[pd.DataFrame]:
        """Load Parquet file."""
        try:
            return pd.read_parquet(filepath)
        except Exception as e:
            logger.error(f"Error loading Parquet: {e}")
            return None


class TradeLogger:
    """Log trades for audit trail."""
    
    def __init__(self, log_path: str = "logs/trades.log"):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Setup dedicated logger
        logger.add(
            str(self.log_path),
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {message}",
            rotation="1 day",
            retention="30 days",
            level="INFO"
        )
    
    def log_signal(self, signal: Dict) -> None:
        """Log trading signal."""
        logger.info(f"SIGNAL | {signal.get('action')} | {signal.get('symbol')} | "
                   f"Confidence: {signal.get('confidence', 0):.2f} | "
                   f"Entry: {signal.get('entry_price', 0):.2f} | "
                   f"Reasoning: {signal.get('reasoning', '')[:100]}")
    
    def log_decision(self, decision: Dict) -> None:
        """Log risk-approved decision."""
        logger.info(f"DECISION | {decision.get('action')} | {decision.get('symbol')} | "
                   f"Risk Level: {decision.get('risk_assessment', {}).get('risk_level', 'N/A')}")
    
    def log_execution(self, execution: Dict) -> None:
        """Log order execution."""
        logger.info(f"EXECUTION | Order: {execution.get('order_id')} | "
                   f"{execution.get('symbol')} | {execution.get('action')} | "
                   f"Qty: {execution.get('quantity')} | "
                   f"Price: {execution.get('fill_price', 0):.2f} | "
                   f"Success: {execution.get('success')}")
    
    def log_veto(self, veto: Dict) -> None:
        """Log vetoed trade."""
        logger.warning(f"VETO | {veto.get('original_signal', {}).get('symbol')} | "
                      f"Reason: {veto.get('reason')}")
    
    def log_error(self, error: str, context: Optional[Dict] = None) -> None:
        """Log error."""
        logger.error(f"ERROR | {error} | Context: {context}")


class AgentLogger:
    """Log agent activities."""
    
    def __init__(self, log_path: str = "logs/agents.log"):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
    
    def log_cycle(self, agent_name: str, messages_count: int, duration_ms: float) -> None:
        """Log agent cycle."""
        logger.debug(f"CYCLE | {agent_name} | Messages: {messages_count} | Duration: {duration_ms:.2f}ms")
    
    def log_message(self, message: Dict) -> None:
        """Log agent message."""
        logger.info(f"MESSAGE | From: {message.get('source_agent')} | "
                   f"Type: {message.get('type')} | "
                   f"To: {message.get('target_agent', 'broadcast')}")


# Singleton instances
_data_saver: Optional[DataSaver] = None
_trade_logger: Optional[TradeLogger] = None
_agent_logger: Optional[AgentLogger] = None


def get_data_saver() -> DataSaver:
    """Get or create DataSaver instance."""
    global _data_saver
    if _data_saver is None:
        _data_saver = DataSaver()
    return _data_saver


def get_trade_logger() -> TradeLogger:
    """Get or create TradeLogger instance."""
    global _trade_logger
    if _trade_logger is None:
        _trade_logger = TradeLogger()
    return _trade_logger


def get_agent_logger() -> AgentLogger:
    """Get or create AgentLogger instance."""
    global _agent_logger
    if _agent_logger is None:
        _agent_logger = AgentLogger()
    return _agent_logger
