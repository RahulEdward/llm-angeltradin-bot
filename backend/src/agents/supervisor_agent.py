"""
Supervisor Agent - Orchestrates the Full Multi-Agent Trading Pipeline
Reference-repo flow with all 7 agent functionalities:

  Step 1: MarketDataAgent (The Oracle) - Fetch multi-timeframe OHLCV
  Step 2: StrategyAgent (Strategist + Critic + Prophet + Regime) -
          Regime Detection → Quant Analysis → Trap Detection →
          Prediction → Weighted Voting → Overtrading Guard → Signal
  Step 3: RiskManagerAgent (The Guardian) - Enhanced risk audit with
          regime-aware blocking, position filtering, SL auto-correction
  Step 4: ExecutionAgent (The Executor) - Place order
  Step 5: ReflectionAgent (The Philosopher) - Trade retrospection every N trades

All steps broadcast to Agent Chatroom via WebSocket.
"""

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional
from loguru import logger

from .base import BaseAgent, AgentType, AgentMessage, MessageType
from .market_data_agent import MarketDataAgent
from .strategy_agent import StrategyAgent
from .risk_manager_agent import RiskManagerAgent
from .execution_agent import ExecutionAgent
from .backtest_agent import BacktestAgent
from .reflection_agent import ReflectionAgent
from ..config.settings import settings, TradingMode


class SupervisorAgent(BaseAgent):
    """
    Supervisor Agent - The Controller.
    Orchestrates the full multi-agent pipeline per cycle.
    Includes ReflectionAgent for trade retrospection.
    """

    def __init__(self, name: str = "SupervisorAgent", config: Optional[Dict[str, Any]] = None):
        super().__init__(name, AgentType.SUPERVISOR, config or {})

        self._agents: Dict[str, BaseAgent] = {}
        self._agent_order: List[str] = []

        self._is_running: bool = False
        self._cycle_interval: int = self.config.get("cycle_interval", 60)
        self._current_cycle: int = 0

        self._mode: TradingMode = settings.trading_mode
        self._symbols: List[str] = self.config.get("symbols", ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK"])

        # Reflection tracking
        self._total_executed_trades: int = 0
        self._recent_trades: List[Dict] = []

    async def initialize(self) -> bool:
        logger.info(f"Initializing SupervisorAgent in {self._mode.value} mode")

        symbols = self._symbols
        exchanges = self.config.get("exchanges", {s: "NSE" for s in symbols})

        # Create agents
        self._agents["market_data"] = MarketDataAgent(config={
            "symbols": symbols, "exchanges": exchanges,
            "timeframes": ["5m", "15m", "1h"]
        })

        self._agents["strategy"] = StrategyAgent(config={
            "use_llm": self.config.get("use_llm", True),
            "min_confidence": self.config.get("min_confidence", 0.6)
        })

        self._agents["risk_manager"] = RiskManagerAgent(config={
            "max_position_size": settings.max_position_size,
            "max_daily_loss": settings.max_daily_loss
        })

        self._agents["execution"] = ExecutionAgent()
        self._agents["backtest"] = BacktestAgent()

        # New: Reflection Agent (The Philosopher)
        use_llm = self.config.get("use_llm", True)
        llm_client = None
        if use_llm:
            try:
                from ..llm import LLMFactory
                llm_client = LLMFactory.get_or_create()
            except Exception:
                pass
        self._agents["reflection"] = ReflectionAgent(use_llm=bool(llm_client), llm_client=llm_client)

        self._agent_order = ["market_data", "strategy", "risk_manager", "execution"]

        # Initialize all agents
        for name, agent in self._agents.items():
            try:
                if hasattr(agent, 'initialize'):
                    success = await agent.initialize()
                    if not success:
                        logger.error(f"Failed to initialize {name}")
                    else:
                        logger.info(f"Initialized {name}")
            except Exception as e:
                logger.error(f"Failed to initialize {name}: {e}")

        logger.info("All agents initialized (Market + Strategy + Risk + Execution + Reflection)")
        return True

    async def process_cycle(self) -> List[AgentMessage]:
        """
        Run one full trading cycle through the multi-agent pipeline.
        """
        self._current_cycle += 1
        cycle_messages: List[AgentMessage] = []

        logger.info(f"━━━ Cycle #{self._current_cycle} ━━━")

        # ─── Step 1: The Oracle (MarketDataAgent) ───
        market_agent = self._agents.get("market_data")
        market_messages = []
        if market_agent and market_agent.state.is_active:
            try:
                market_messages = await market_agent.process_cycle()
                cycle_messages.extend(market_messages)
            except Exception as e:
                logger.error(f"MarketDataAgent error: {e}")
                cycle_messages.append(AgentMessage(
                    type=MessageType.ERROR, source_agent="MarketDataAgent",
                    payload={"agent": "MarketDataAgent", "error": str(e)}
                ))

        has_market_data = any(m.type == MessageType.MARKET_UPDATE for m in market_messages)
        if not has_market_data:
            cycle_messages.append(AgentMessage(
                type=MessageType.STATE_UPDATE, source_agent="MarketDataAgent",
                payload={"status": "waiting", "message": "⏳ Waiting for market data..."}
            ))
            return cycle_messages

        # Forward market data to strategy
        strategy_agent = self._agents.get("strategy")
        if strategy_agent:
            for msg in market_messages:
                if msg.type == MessageType.MARKET_UPDATE:
                    await strategy_agent.receive_message(msg)

        # ─── Step 2: The Strategist + Critic + Prophet + Regime ───
        strategy_messages = []
        if strategy_agent and strategy_agent.state.is_active:
            try:
                strategy_messages = await strategy_agent.process_cycle()
                cycle_messages.extend(strategy_messages)
            except Exception as e:
                logger.error(f"StrategyAgent error: {e}")
                cycle_messages.append(AgentMessage(
                    type=MessageType.ERROR, source_agent="StrategyAgent",
                    payload={"agent": "StrategyAgent", "error": str(e)}
                ))

        signals = [m for m in strategy_messages if m.type == MessageType.SIGNAL]
        if not signals:
            cycle_messages.append(AgentMessage(
                type=MessageType.STATE_UPDATE, source_agent="StrategyAgent",
                payload={"status": "hold", "message": "📊 No actionable signals. Holding."}
            ))
            # Still run reflection check even when no signals
            await self._maybe_reflect(cycle_messages)
            return cycle_messages

        # ─── Step 3: The Guardian (RiskManagerAgent) ───
        risk_agent = self._agents.get("risk_manager")
        risk_messages = []
        if risk_agent and risk_agent.state.is_active:
            for signal in signals:
                await risk_agent.receive_message(signal)
            try:
                risk_messages = await risk_agent.process_cycle()
                cycle_messages.extend(risk_messages)
            except Exception as e:
                logger.error(f"RiskManagerAgent error: {e}")

        decisions = [m for m in risk_messages if m.type == MessageType.DECISION]
        vetoes = [m for m in risk_messages if m.type == MessageType.VETO]

        if not decisions:
            for veto in vetoes:
                cycle_messages.append(AgentMessage(
                    type=MessageType.STATE_UPDATE, source_agent="RiskManagerAgent",
                    payload={"status": "vetoed", "message": f"🛡️ Vetoed: {veto.payload.get('reason', 'Risk limit')}"}
                ))
            await self._maybe_reflect(cycle_messages)
            return cycle_messages

        # ─── Step 4: The Executor (ExecutionAgent) ───
        exec_agent = self._agents.get("execution")
        if exec_agent and exec_agent.state.is_active:
            for decision in decisions:
                await exec_agent.receive_message(decision)
            try:
                exec_messages = await exec_agent.process_cycle()
                cycle_messages.extend(exec_messages)

                # Track executed trades for reflection
                for em in exec_messages:
                    if em.type == MessageType.EXECUTION and em.payload.get("success"):
                        self._total_executed_trades += 1
                        self._recent_trades.append(em.payload)
                        if len(self._recent_trades) > 100:
                            self._recent_trades = self._recent_trades[-100:]
            except Exception as e:
                logger.error(f"ExecutionAgent error: {e}")

        # ─── Step 5: The Philosopher (ReflectionAgent) ───
        await self._maybe_reflect(cycle_messages)

        return cycle_messages

    async def _maybe_reflect(self, cycle_messages: List[AgentMessage]):
        """Check if reflection should be triggered."""
        reflection_agent = self._agents.get("reflection")
        if not reflection_agent or not isinstance(reflection_agent, ReflectionAgent):
            return

        if reflection_agent.should_reflect(self._total_executed_trades) and self._recent_trades:
            try:
                result = await reflection_agent.generate_reflection(self._recent_trades[-20:])
                if result:
                    cycle_messages.append(AgentMessage(
                        type=MessageType.STATE_UPDATE, source_agent="ReflectionAgent",
                        payload={
                            "status": "reflection",
                            "message": f"🧠 Reflection #{result.reflection_id}: {result.summary[:150]}"
                        }
                    ))
                    # Add recommendations
                    for rec in result.recommendations[:2]:
                        cycle_messages.append(AgentMessage(
                            type=MessageType.STATE_UPDATE, source_agent="ReflectionAgent",
                            payload={"status": "recommendation", "message": f"💡 {rec}"}
                        ))
            except Exception as e:
                logger.warning(f"Reflection error: {e}")

    async def handle_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        payload = message.payload
        if payload.get("command") == "start":
            await self.start_loop()
        elif payload.get("command") == "stop":
            await self.stop_loop()
        elif payload.get("command") == "status":
            return AgentMessage(
                type=MessageType.STATE_UPDATE, source_agent=self.name,
                payload=self.get_system_status()
            )
        return None

    async def shutdown(self) -> None:
        self._is_running = False
        for name, agent in self._agents.items():
            try:
                if hasattr(agent, 'shutdown'):
                    await agent.shutdown()
                logger.info(f"Shutdown {name}")
            except Exception as e:
                logger.error(f"Error shutting down {name}: {e}")
        logger.info("SupervisorAgent shutdown complete")

    async def start_loop(self) -> None:
        if self._is_running:
            return
        self._is_running = True
        logger.info(f"Starting trading loop ({self._mode.value} mode)")
        while self._is_running:
            try:
                await self.process_cycle()
                await asyncio.sleep(self._cycle_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Loop error: {e}")
                await asyncio.sleep(5)

    async def stop_loop(self) -> None:
        self._is_running = False
        logger.info("Trading loop stopped")

    def get_system_status(self) -> Dict[str, Any]:
        return {
            "mode": self._mode.value,
            "is_running": self._is_running,
            "current_cycle": self._current_cycle,
            "cycle_count": self._current_cycle,
            "symbols": self._symbols,
            "total_trades": self._total_executed_trades,
            "agents": {name: agent.get_status() for name, agent in self._agents.items()
                       if hasattr(agent, 'get_status')},
        }

    def get_agent(self, name: str) -> Optional[BaseAgent]:
        return self._agents.get(name)

    async def run_backtest(self, **kwargs) -> Any:
        backtest_agent = self._agents.get("backtest")
        if backtest_agent and isinstance(backtest_agent, BacktestAgent):
            return await backtest_agent.run_backtest(**kwargs)
        raise RuntimeError("Backtest agent not available")
