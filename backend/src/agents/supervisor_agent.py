"""
Supervisor Agent
Orchestrates all agents and manages the trading loop
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
from ..config.settings import settings, TradingMode


class SupervisorAgent(BaseAgent):
    """
    Supervisor Agent - The Controller.
    Orchestrates all agents and manages the trading cycle.
    """
    
    def __init__(self, name: str = "SupervisorAgent", config: Optional[Dict[str, Any]] = None):
        super().__init__(name, AgentType.SUPERVISOR, config or {})
        
        # Agent instances
        self._agents: Dict[str, BaseAgent] = {}
        self._agent_order: List[str] = []
        
        # Loop control
        self._is_running: bool = False
        self._cycle_interval: int = self.config.get("cycle_interval", 60)
        self._current_cycle: int = 0
        
        # Mode
        self._mode: TradingMode = settings.trading_mode
    
    async def initialize(self) -> bool:
        """Initialize all agents."""
        logger.info(f"Initializing SupervisorAgent in {self._mode.value} mode")
        
        # Get symbols from config
        symbols = self.config.get("symbols", ["RELIANCE", "TCS", "INFY"])
        exchanges = self.config.get("exchanges", {s: "NSE" for s in symbols})
        
        # Create agents
        self._agents["market_data"] = MarketDataAgent(config={
            "symbols": symbols,
            "exchanges": exchanges,
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
        
        # Define processing order
        self._agent_order = ["market_data", "strategy", "risk_manager", "execution"]
        
        # Set up dependencies
        self._agents["strategy"].add_dependency("market_data", self._agents["market_data"])
        self._agents["risk_manager"].add_dependency("strategy", self._agents["strategy"])
        self._agents["execution"].add_dependency("risk_manager", self._agents["risk_manager"])
        
        # Initialize all agents
        for name, agent in self._agents.items():
            try:
                success = await agent.initialize()
                if not success:
                    logger.error(f"Failed to initialize {name}")
                    return False
                logger.info(f"Initialized {name}")
            except Exception as e:
                logger.error(f"Error initializing {name}: {e}")
                return False
        
        logger.info("All agents initialized successfully")
        return True
    
    async def process_cycle(self) -> List[AgentMessage]:
        """Run one trading cycle through all agents."""
        self._current_cycle += 1
        cycle_messages: List[AgentMessage] = []
        
        logger.debug(f"Starting cycle {self._current_cycle}")
        
        for agent_name in self._agent_order:
            agent = self._agents.get(agent_name)
            if not agent or not agent.state.is_active:
                continue
            
            try:
                # Process agent
                messages = await agent.process_cycle()
                
                # Route messages to target agents
                for msg in messages:
                    cycle_messages.append(msg)
                    
                    if msg.target_agent:
                        # Direct message
                        target = self._agents.get(msg.target_agent)
                        if target:
                            await target.receive_message(msg)
                    else:
                        # Broadcast to next agents
                        idx = self._agent_order.index(agent_name)
                        for next_name in self._agent_order[idx+1:]:
                            next_agent = self._agents.get(next_name)
                            if next_agent:
                                await next_agent.receive_message(msg)
                
            except Exception as e:
                logger.error(f"Error in {agent_name}: {e}")
                cycle_messages.append(AgentMessage(
                    type=MessageType.ERROR,
                    source_agent=self.name,
                    payload={"agent": agent_name, "error": str(e)}
                ))
        
        return cycle_messages
    
    async def handle_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Handle control messages."""
        payload = message.payload
        
        if payload.get("command") == "start":
            await self.start_loop()
        elif payload.get("command") == "stop":
            await self.stop_loop()
        elif payload.get("command") == "status":
            return AgentMessage(
                type=MessageType.STATE_UPDATE,
                source_agent=self.name,
                payload=self.get_system_status()
            )
        
        return None
    
    async def shutdown(self) -> None:
        """Shutdown all agents."""
        self._is_running = False
        
        for name, agent in self._agents.items():
            try:
                await agent.shutdown()
                logger.info(f"Shutdown {name}")
            except Exception as e:
                logger.error(f"Error shutting down {name}: {e}")
        
        logger.info("SupervisorAgent shutdown complete")
    
    async def start_loop(self) -> None:
        """Start the main trading loop."""
        if self._is_running:
            logger.warning("Trading loop already running")
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
        """Stop the trading loop."""
        self._is_running = False
        logger.info("Trading loop stopped")
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get status of all agents."""
        return {
            "mode": self._mode.value,
            "is_running": self._is_running,
            "current_cycle": self._current_cycle,
            "agents": {
                name: agent.get_status()
                for name, agent in self._agents.items()
            }
        }
    
    def get_agent(self, name: str) -> Optional[BaseAgent]:
        """Get an agent by name."""
        return self._agents.get(name)
    
    async def run_backtest(self, **kwargs) -> Any:
        """Run a backtest through the backtest agent."""
        backtest_agent = self._agents.get("backtest")
        if backtest_agent and isinstance(backtest_agent, BacktestAgent):
            return await backtest_agent.run_backtest(**kwargs)
        raise RuntimeError("Backtest agent not available")
