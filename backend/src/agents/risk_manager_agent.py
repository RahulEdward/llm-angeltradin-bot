"""
Risk Manager Agent - The Guardian (Enhanced)
Full reference-repo RiskAuditAgent functionality:

1. Market regime-aware blocking (volatile → block low confidence, choppy → require higher)
2. Price position filtering (block long at resistance, short at support)
3. Stop-loss auto-correction (direction check + ATR-based dynamic SL)
4. Overtrading/duplicate position blocking
5. Daily loss limit + kill switch
6. Trap-based risk filtering
7. Confidence-based risk level assessment

Adapted for Indian equity markets (no leverage/futures).
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
    Enhanced with regime-aware blocking, position filtering, SL auto-correction.
    """

    def __init__(self, name: str = "RiskManagerAgent", config: Optional[Dict[str, Any]] = None):
        super().__init__(name, AgentType.RISK_MANAGER, config or {})

        self.max_position_size = self.config.get("max_position_size", settings.max_position_size)
        self.max_daily_loss = self.config.get("max_daily_loss", settings.max_daily_loss)
        self.max_trades_per_day = self.config.get("max_trades_per_day", settings.max_trades_per_day)
        self.max_drawdown_pct = self.config.get("max_drawdown_pct", 5.0)
        self.default_stop_loss_pct = self.config.get("stop_loss_pct", settings.default_stop_loss_pct)

        # State
        self._daily_pnl: float = 0.0
        self._daily_trades: int = 0
        self._current_date: date = date.today()
        self._open_positions: Dict[str, Dict] = {}
        self._peak_capital: float = 0.0
        self._current_capital: float = 0.0
        self._kill_switch_active: bool = False

        # Audit log
        self._audit_log: List[Dict] = []
        self._block_stats = {
            "total_checks": 0, "total_blocks": 0,
            "regime_blocks": 0, "position_blocks": 0,
            "sl_corrections": 0, "trap_blocks": 0,
        }

    async def initialize(self) -> bool:
        self._current_date = date.today()
        self._daily_pnl = 0.0
        self._daily_trades = 0
        logger.info(f"RiskManagerAgent initialized - Enhanced Guardian "
                     f"(Max loss: ₹{self.max_daily_loss}, Regime-aware, Position filtering)")
        return True

    async def process_cycle(self) -> List[AgentMessage]:
        messages = []
        if date.today() != self._current_date:
            self._reset_daily_stats()

        for msg in self.get_pending_messages():
            if msg.type == MessageType.SIGNAL:
                result = await self._evaluate_signal(msg.payload)
                if result["approved"]:
                    messages.append(AgentMessage(
                        type=MessageType.DECISION, source_agent=self.name,
                        payload={**msg.payload, "risk_assessment": result}, priority=2
                    ))
                else:
                    messages.append(AgentMessage(
                        type=MessageType.VETO, source_agent=self.name,
                        payload={"original_signal": msg.payload, "reason": result["reason"],
                                 "risk_level": result["risk_level"]}, priority=1
                    ))
            elif msg.type == MessageType.EXECUTION:
                self._track_execution(msg.payload)

        return messages

    async def handle_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        if message.type == MessageType.SIGNAL:
            result = await self._evaluate_signal(message.payload)
            return AgentMessage(
                type=MessageType.DECISION if result["approved"] else MessageType.VETO,
                source_agent=self.name, target_agent=message.source_agent,
                payload=result, correlation_id=message.id
            )
        return None

    async def shutdown(self) -> None:
        logger.info("RiskManagerAgent shutdown")

    async def _evaluate_signal(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """Full risk audit pipeline (reference-repo style)."""
        self._block_stats["total_checks"] += 1
        result = {
            "approved": True, "reason": "", "risk_level": "low",
            "position_size": signal.get("position_size", 1),
            "adjusted_stop_loss": signal.get("stop_loss"),
            "adjusted_take_profit": signal.get("take_profit"),
            "warnings": [],
        }

        action = signal.get("action", "").upper()
        symbol = signal.get("symbol", "")
        confidence = signal.get("confidence", 0.5)
        entry = signal.get("entry_price", 0)
        sl = signal.get("stop_loss")
        tp = signal.get("take_profit")
        regime = signal.get("regime", {})
        position = signal.get("position", {})
        traps = signal.get("traps", {})

        # ─── 0. Kill switch ───
        if self._kill_switch_active:
            return self._block("Kill switch active", "critical")

        # ─── 1. Daily loss limit ───
        if self._daily_pnl <= -self.max_daily_loss:
            self._activate_kill_switch("Daily loss limit exceeded")
            return self._block(f"Daily loss limit: ₹{abs(self._daily_pnl):.2f}", "critical")

        # ─── 2. Daily trade limit ───
        if self._daily_trades >= self.max_trades_per_day:
            return self._block(f"Daily trade limit: {self._daily_trades}", "high")

        # ─── 3. Drawdown check ───
        if self._peak_capital > 0:
            dd = (self._peak_capital - self._current_capital) / self._peak_capital * 100
            if dd >= self.max_drawdown_pct:
                return self._block(f"Max drawdown: {dd:.2f}%", "critical")

        # ─── 4. Regime-aware blocking (reference-repo) ───
        if regime:
            r_type = regime.get("regime", "").lower()
            if r_type == "volatile" and confidence < 0.7:
                self._block_stats["regime_blocks"] += 1
                return self._block(f"Volatile market + low confidence ({confidence:.0%})", "high")
            if r_type == "choppy" and confidence < 0.65:
                self._block_stats["regime_blocks"] += 1
                return self._block(f"Choppy market + low confidence ({confidence:.0%})", "high")
            if r_type == "unknown" and confidence < 0.6:
                self._block_stats["regime_blocks"] += 1
                return self._block(f"Unknown regime + low confidence ({confidence:.0%})", "medium")
            if r_type == "volatile_directionless" and confidence < 0.7:
                self._block_stats["regime_blocks"] += 1
                return self._block(f"Directionless market ({confidence:.0%})", "high")

        # ─── 5. Price position filtering (reference-repo) ───
        if position:
            pos_pct = position.get("position_pct", 50)
            loc = position.get("location", "middle")

            if loc == "middle" and confidence < 0.7:
                self._block_stats["position_blocks"] += 1
                return self._block(f"Price in middle zone ({pos_pct:.0f}%), poor R/R", "medium")

            if action == "BUY" and pos_pct > 80 and confidence < 0.75:
                self._block_stats["position_blocks"] += 1
                return self._block(f"BUY at high position ({pos_pct:.0f}%), pullback risk", "high")

            if action == "SELL" and pos_pct < 20 and confidence < 0.75:
                self._block_stats["position_blocks"] += 1
                return self._block(f"SELL at low position ({pos_pct:.0f}%), bounce risk", "high")

        # ─── 6. Trap-based blocking (reference-repo) ───
        if traps:
            if action == "BUY" and traps.get("bull_trap_risk"):
                self._block_stats["trap_blocks"] += 1
                return self._block("Bull trap detected - rapid rise slow fall pattern", "high")
            if action == "BUY" and traps.get("volume_divergence"):
                self._block_stats["trap_blocks"] += 1
                return self._block("Volume divergence at high - possible distribution", "high")
            if action == "BUY" and traps.get("fomo_top"):
                self._block_stats["trap_blocks"] += 1
                return self._block("FOMO top detected - overbought + high volume", "high")
            if action == "SELL" and traps.get("panic_bottom"):
                self._block_stats["trap_blocks"] += 1
                return self._block("Panic bottom detected - oversold + high volume", "high")

        # ─── 7. Duplicate position check ───
        if symbol in self._open_positions and action in ("BUY", "SELL"):
            existing = self._open_positions[symbol]
            if existing.get("side") == action:
                return self._block(f"Already have {action} position in {symbol}", "medium")

        # ─── 8. Stop-loss auto-correction (reference-repo) ───
        if entry and sl and action in ("BUY", "SELL"):
            corrected_sl = self._check_and_fix_sl(action, entry, sl)
            if corrected_sl != sl:
                result["adjusted_stop_loss"] = corrected_sl
                result["warnings"].append(f"SL corrected: ₹{sl:.2f} → ₹{corrected_sl:.2f}")
                self._block_stats["sl_corrections"] += 1

            # Validate SL distance
            sl_pct = abs(entry - (corrected_sl or sl)) / entry * 100
            if sl_pct > self.default_stop_loss_pct * 2.5:
                # Auto-correct to max allowed
                if action == "BUY":
                    result["adjusted_stop_loss"] = entry * (1 - self.default_stop_loss_pct * 2 / 100)
                else:
                    result["adjusted_stop_loss"] = entry * (1 + self.default_stop_loss_pct * 2 / 100)
                result["warnings"].append(f"SL too wide ({sl_pct:.1f}%), auto-corrected")

        # ─── 9. R/R ratio check ───
        final_sl = result.get("adjusted_stop_loss") or sl
        if entry and final_sl and tp:
            risk = abs(entry - final_sl)
            reward = abs(tp - entry)
            if risk > 0:
                rr = reward / risk
                if rr < 1.2:
                    result["warnings"].append(f"Poor R/R ratio ({rr:.2f})")
                    if rr < 0.8:
                        return self._block(f"R/R ratio too low ({rr:.2f})", "medium")

        # ─── 10. Position sizing ───
        if entry > 0:
            position_value = entry * signal.get("quantity", 1)
            if position_value > self.max_position_size:
                max_qty = int(self.max_position_size / entry)
                result["position_size"] = max(1, max_qty)
                result["risk_level"] = "medium"

        # ─── 11. Confidence-based risk level ───
        if confidence < 0.5:
            result["risk_level"] = "high"
        elif confidence < 0.7:
            result["risk_level"] = "medium"

        self._log_audit(signal, "PASSED", result["warnings"])
        return result

    def _check_and_fix_sl(self, action: str, entry: float, sl: float) -> float:
        """Auto-correct stop-loss direction errors."""
        if action == "BUY" and sl >= entry:
            return entry * (1 - self.default_stop_loss_pct / 100)
        if action == "SELL" and sl <= entry:
            return entry * (1 + self.default_stop_loss_pct / 100)
        return sl

    def _block(self, reason: str, risk_level: str) -> Dict:
        self._block_stats["total_blocks"] += 1
        self._log_audit({}, "BLOCKED", [reason])
        return {"approved": False, "reason": reason, "risk_level": risk_level}

    def _track_execution(self, execution: Dict[str, Any]) -> None:
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
        self._current_date = date.today()
        self._daily_pnl = 0.0
        self._daily_trades = 0
        self._kill_switch_active = False
        logger.info("Daily risk stats reset")

    def _activate_kill_switch(self, reason: str) -> None:
        self._kill_switch_active = True
        logger.critical(f"KILL SWITCH: {reason}")
        self.send_message(
            MessageType.RISK_ALERT,
            {"type": "kill_switch", "reason": reason, "timestamp": datetime.now().isoformat()},
            priority=1
        )

    def deactivate_kill_switch(self) -> None:
        self._kill_switch_active = False
        logger.info("Kill switch deactivated")

    def _log_audit(self, signal: Dict, result: str, warnings: List[str]):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "signal": {k: signal.get(k) for k in ("symbol", "action", "confidence") if k in signal},
            "result": result, "warnings": warnings,
        }
        self._audit_log.append(entry)
        if len(self._audit_log) > 500:
            self._audit_log = self._audit_log[-500:]

    def get_risk_status(self) -> Dict[str, Any]:
        return {
            "daily_pnl": self._daily_pnl,
            "daily_trades": self._daily_trades,
            "max_daily_loss": self.max_daily_loss,
            "max_trades": self.max_trades_per_day,
            "open_positions": len(self._open_positions),
            "kill_switch": self._kill_switch_active,
            "drawdown_pct": ((self._peak_capital - self._current_capital) / self._peak_capital * 100) if self._peak_capital > 0 else 0,
            "block_stats": self._block_stats,
        }
