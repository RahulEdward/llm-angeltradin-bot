"""
Risk Manager Agent
Responsible for risk assessment, position sizing, and veto power
"""

from datetime import datetime, date
from typing import Any, Dict, List, Optional
from loguru import logger

from .base import BaseAgent, AgentType, AgentMessage, MessageType
from ..config.settings import settings


class RiskManagerAgent(BaseAgent):
    """
    Risk Manager Agent - The Guardian.
    Has VETO power over trades that exceed risk parameters.
    """
    
    def __init__(self, name: str = "RiskManagerAgent", config: Optional[Dict[str, Any]] = None):
        super().__init__(name, AgentType.RISK_MANAGER, config or {})
        
        # Risk parameters
        self.max_position_size = self.config.get("max_position_size", settings.max_position_size)
        self.max_daily_loss = self.config.get("max_daily_loss", settings.max_daily_loss)
        self.max_trades_per_day = self.config.get("max_trades_per_day", settings.max_trades_per_day)
        self.max_drawdown_pct = self.config.get("max_drawdown_pct", 5.0)
        self.default_stop_loss_pct = self.config.get("stop_loss_pct", settings.default_stop_loss_pct)
        
        # State tracking
        self._daily_pnl: float = 0.0
        self._daily_trades: int = 0
        self._current_date: date = date.today()
        self._open_positions: Dict[str, Dict] = {}
        self._peak_capital: float = 0.0
        self._current_capital: float = 0.0
        self._kill_switch_active: bool = False
    
    async def initialize(self) -> bool:
        self._current_date = date.today()
        self._daily_pnl = 0.0
        self._daily_trades = 0
        logger.info(f"RiskManagerAgent initialized - Max loss: ₹{self.max_daily_loss}")
        return True
    
    async def process_cycle(self) -> List[AgentMessage]:
        messages = []
        
        # Reset daily counters if new day
        if date.today() != self._current_date:
            self._reset_daily_stats()
        
        # Process pending signals
        for msg in self.get_pending_messages():
            if msg.type == MessageType.SIGNAL:
                result = await self._evaluate_signal(msg.payload)
                
                if result["approved"]:
                    # Forward approved signal as decision
                    messages.append(AgentMessage(
                        type=MessageType.DECISION,
                        source_agent=self.name,
                        payload={**msg.payload, "risk_assessment": result},
                        priority=2
                    ))
                else:
                    # Send veto
                    messages.append(AgentMessage(
                        type=MessageType.VETO,
                        source_agent=self.name,
                        payload={
                            "original_signal": msg.payload,
                            "reason": result["reason"],
                            "risk_level": result["risk_level"]
                        },
                        priority=1
                    ))
            
            elif msg.type == MessageType.EXECUTION:
                # Track executed trades
                self._track_execution(msg.payload)
        
        return messages
    
    async def handle_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        if message.type == MessageType.SIGNAL:
            result = await self._evaluate_signal(message.payload)
            return AgentMessage(
                type=MessageType.DECISION if result["approved"] else MessageType.VETO,
                source_agent=self.name,
                target_agent=message.source_agent,
                payload=result,
                correlation_id=message.id
            )
        return None
    
    async def shutdown(self) -> None:
        logger.info("RiskManagerAgent shutdown")
    
    async def _evaluate_signal(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate trading signal against risk parameters."""
        result = {
            "approved": True,
            "reason": "",
            "risk_level": "low",
            "position_size": signal.get("position_size", 1),
            "adjusted_stop_loss": signal.get("stop_loss"),
            "adjusted_take_profit": signal.get("take_profit")
        }
        
        # Check kill switch
        if self._kill_switch_active:
            result["approved"] = False
            result["reason"] = "Kill switch active - trading halted"
            result["risk_level"] = "critical"
            return result
        
        # Check daily loss limit
        if self._daily_pnl <= -self.max_daily_loss:
            result["approved"] = False
            result["reason"] = f"Daily loss limit reached: ₹{abs(self._daily_pnl):.2f}"
            result["risk_level"] = "critical"
            self._activate_kill_switch("Daily loss limit exceeded")
            return result
        
        # Check daily trade limit
        if self._daily_trades >= self.max_trades_per_day:
            result["approved"] = False
            result["reason"] = f"Daily trade limit reached: {self._daily_trades}"
            result["risk_level"] = "high"
            return result
        
        # Check drawdown
        if self._peak_capital > 0:
            current_dd = (self._peak_capital - self._current_capital) / self._peak_capital * 100
            if current_dd >= self.max_drawdown_pct:
                result["approved"] = False
                result["reason"] = f"Max drawdown reached: {current_dd:.2f}%"
                result["risk_level"] = "critical"
                return result
        
        # Validate stop loss
        entry = signal.get("entry_price", 0)
        sl = signal.get("stop_loss")
        action = signal.get("action", "").upper()
        
        if entry and sl:
            sl_pct = abs(entry - sl) / entry * 100
            if sl_pct > self.default_stop_loss_pct * 2:
                # Adjust stop loss if too wide
                if action == "BUY":
                    result["adjusted_stop_loss"] = entry * (1 - self.default_stop_loss_pct / 100)
                else:
                    result["adjusted_stop_loss"] = entry * (1 + self.default_stop_loss_pct / 100)
                result["risk_level"] = "medium"
        
        # Check position size
        position_value = entry * signal.get("quantity", 1)
        if position_value > self.max_position_size:
            max_qty = int(self.max_position_size / entry)
            result["position_size"] = max_qty
            result["risk_level"] = "medium"
        
        # Confidence-based risk level
        confidence = signal.get("confidence", 0.5)
        if confidence < 0.5:
            result["risk_level"] = "high"
        elif confidence < 0.7:
            result["risk_level"] = "medium"
        
        return result
    
    def _track_execution(self, execution: Dict[str, Any]) -> None:
        """Track executed trade for risk monitoring."""
        self._daily_trades += 1
        
        pnl = execution.get("pnl", 0)
        self._daily_pnl += pnl
        self._current_capital += pnl
        
        if self._current_capital > self._peak_capital:
            self._peak_capital = self._current_capital
        
        symbol = execution.get("symbol", "")
        if execution.get("is_open", False):
            self._open_positions[symbol] = execution
        elif symbol in self._open_positions:
            del self._open_positions[symbol]
    
    def _reset_daily_stats(self) -> None:
        """Reset daily statistics."""
        self._current_date = date.today()
        self._daily_pnl = 0.0
        self._daily_trades = 0
        self._kill_switch_active = False
        logger.info("Daily risk stats reset")
    
    def _activate_kill_switch(self, reason: str) -> None:
        """Activate kill switch to halt all trading."""
        self._kill_switch_active = True
        logger.critical(f"KILL SWITCH ACTIVATED: {reason}")
        
        self.send_message(
            MessageType.RISK_ALERT,
            {"type": "kill_switch", "reason": reason, "timestamp": datetime.now().isoformat()},
            priority=1
        )
    
    def deactivate_kill_switch(self) -> None:
        """Manually deactivate kill switch."""
        self._kill_switch_active = False
        logger.info("Kill switch deactivated manually")
    
    def get_risk_status(self) -> Dict[str, Any]:
        """Get current risk status."""
        return {
            "daily_pnl": self._daily_pnl,
            "daily_trades": self._daily_trades,
            "max_daily_loss": self.max_daily_loss,
            "max_trades": self.max_trades_per_day,
            "open_positions": len(self._open_positions),
            "kill_switch": self._kill_switch_active,
            "drawdown_pct": ((self._peak_capital - self._current_capital) / self._peak_capital * 100) if self._peak_capital > 0 else 0
        }
