"""
Agents Module
Multi-agent trading system with full reference-repo flow:
- MarketDataAgent (The Oracle)
- StrategyAgent (The Strategist + Critic + Prophet + Regime)
- RiskManagerAgent (The Guardian)
- ExecutionAgent (The Executor)
- ReflectionAgent (The Philosopher)
- RegimeDetector (Market State Detection)
- PredictAgent (The Prophet)
- SupervisorAgent (The Controller)
"""

from .base import BaseAgent, AgentType, AgentMessage, MessageType, AgentState
from .market_data_agent import MarketDataAgent
from .strategy_agent import StrategyAgent
from .risk_manager_agent import RiskManagerAgent
from .execution_agent import ExecutionAgent
from .backtest_agent import BacktestAgent, BacktestResult, BacktestTrade
from .supervisor_agent import SupervisorAgent
from .regime_detector import RegimeDetector, MarketRegime
from .predict_agent import PredictAgent, PredictResult
from .reflection_agent import ReflectionAgent, ReflectionResult

__all__ = [
    "BaseAgent",
    "AgentType",
    "AgentMessage",
    "MessageType",
    "AgentState",
    "MarketDataAgent",
    "StrategyAgent",
    "RiskManagerAgent",
    "ExecutionAgent",
    "BacktestAgent",
    "BacktestResult",
    "BacktestTrade",
    "SupervisorAgent",
    "RegimeDetector",
    "MarketRegime",
    "PredictAgent",
    "PredictResult",
    "ReflectionAgent",
    "ReflectionResult",
]
