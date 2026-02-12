"""
Agents Module
Multi-agent trading system with full reference-repo flow:

Core Agents (always enabled):
- MarketDataAgent (The Oracle)
- StrategyAgent (The Strategist + Critic + Prophet + Regime)
- RiskManagerAgent (The Guardian)
- ExecutionAgent (The Executor)
- SupervisorAgent (The Controller)

Optional Agents (configurable via AgentConfig):
- PredictAgent (The Prophet)
- ReflectionAgent (The Philosopher)
- RegimeDetector (Market State Detection)
- TriggerDetector (5m Pattern Detection)
- TriggerAgent / TriggerAgentLLM (5m Semantic)
- TrendAgent / TrendAgentLLM (1h Semantic)
- SetupAgent / SetupAgentLLM (15m Semantic)
- PositionAnalyzer (Price Position)
- AIPredictionFilter (AI Veto)
- MultiPeriodParserAgent (Multi-TF Summary)
- SymbolSelectorAgent (Symbol Selection)

Framework:
- AgentConfig (Configuration)
- AgentRegistry (Lazy init + discovery)
"""

from .base import BaseAgent, AgentType, AgentMessage, MessageType, AgentState
from .agent_config import AgentConfig
from .agent_registry import AgentRegistry
from .market_data_agent import MarketDataAgent
from .strategy_agent import StrategyAgent
from .risk_manager_agent import RiskManagerAgent
from .execution_agent import ExecutionAgent
from .backtest_agent import BacktestAgent, BacktestResult, BacktestTrade
from .supervisor_agent import SupervisorAgent
from .regime_detector import RegimeDetector, MarketRegime
from .predict_agent import PredictAgent, PredictResult
from .reflection_agent import ReflectionAgent, ReflectionAgentLLM, ReflectionResult
from .decision_core_agent import DecisionCoreAgent, OvertradingGuard, VoteResult

# New optional agents
from .trigger_detector_agent import TriggerDetector
from .trigger_agent import TriggerAgent, TriggerAgentLLM
from .trend_agent import TrendAgent, TrendAgentLLM
from .setup_agent import SetupAgent, SetupAgentLLM
from .position_analyzer_agent import PositionAnalyzer
from .ai_prediction_filter_agent import AIPredictionFilter
from .multi_period_agent import MultiPeriodParserAgent
from .symbol_selector_agent import SymbolSelectorAgent

__all__ = [
    # Framework
    "AgentConfig",
    "AgentRegistry",
    # Base
    "BaseAgent",
    "AgentType",
    "AgentMessage",
    "MessageType",
    "AgentState",
    # Core Agents
    "MarketDataAgent",
    "StrategyAgent",
    "RiskManagerAgent",
    "ExecutionAgent",
    "BacktestAgent",
    "BacktestResult",
    "BacktestTrade",
    "SupervisorAgent",
    # Optional Agents
    "RegimeDetector",
    "MarketRegime",
    "PredictAgent",
    "PredictResult",
    "ReflectionAgent",
    "ReflectionAgentLLM",
    "ReflectionResult",
    "DecisionCoreAgent",
    "OvertradingGuard",
    "VoteResult",
    "TriggerDetector",
    "TriggerAgent",
    "TriggerAgentLLM",
    "TrendAgent",
    "TrendAgentLLM",
    "SetupAgent",
    "SetupAgentLLM",
    "PositionAnalyzer",
    "AIPredictionFilter",
    "MultiPeriodParserAgent",
    "SymbolSelectorAgent",
]
